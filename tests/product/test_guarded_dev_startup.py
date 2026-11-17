"""Stub-level tests for the local-environment bootstrap: configurable guarded runtime (M-3 startup refusal, config safety
checks), role-recording order (L-1) and the `dev_env.py` state/teardown logic. No PostgreSQL, socket server or network."""
from __future__ import annotations

import json
import os
import socket as socket_module
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import dev_env  # noqa: E402
import guarded_pg_provision  # noqa: E402
from persistence.guarded_workspace_context import GuardedWorkspaceError  # noqa: E402
from web_api import guarded_dev  # noqa: E402

TAG = "0a1b2c3d"
DB = "finweb_dev_env_" + TAG
CONTEXT = "c" * 64


def good_config(socket_path):
    return dict(schema="finweb.f3.app_config/1", socket=str(socket_path), database=DB, product_schema=DB + "_f3",
        executor_role=DB + "_f3_executor", context_id=CONTEXT)


class Scratch(unittest.TestCase):
    def make_dir(self, mode=0o700):
        base = Path(tempfile.mkdtemp(prefix="fwdev")).resolve()
        self.addCleanup(self.rmtree, base)
        os.chmod(base, mode)
        return base

    @staticmethod
    def rmtree(path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)


class FakeConn:
    """Answers the privilege query: True only for signatures in `ok`."""
    def __init__(self, ok):
        self.ok, self.closed, self.queries = ok, False, []

    def execute(self, query, params=()):
        self.queries.append(params)
        return SimpleNamespace(fetchone=lambda: (params[0] in self.ok,))

    def close(self):
        self.closed = True


class FakeStore:
    def __init__(self, schema, ok):
        self.schema, self.conn = schema, FakeConn(ok)

    def connect(self):
        return self.conn


class ReportInstalledCheck(unittest.TestCase):
    ALL = ['"s1".' + signature for signature in guarded_dev.REPORT_FUNCTIONS]

    def test_all_four_functions_executable_passes_and_closes_the_connection(self):
        store = FakeStore("s1", set(self.ALL))
        guarded_dev.require_report_installed(store)
        self.assertTrue(store.conn.closed)
        self.assertEqual([q[0] for q in store.conn.queries], self.ALL)
        self.assertEqual(len(self.ALL), 4)

    def test_any_missing_or_unexecutable_function_is_a_distinct_startup_refusal(self):
        for missing in range(4):
            store = FakeStore("s1", set(self.ALL) - {self.ALL[missing]})
            with self.assertRaises(GuardedWorkspaceError) as caught:
                guarded_dev.require_report_installed(store)
            self.assertEqual(caught.exception.code, "F3_CSV_REPORT_NOT_INSTALLED")
            self.assertTrue(store.conn.closed)
        with self.assertRaises(GuardedWorkspaceError) as caught:
            guarded_dev.require_report_installed(FakeStore("s1", set()))
        self.assertEqual(caught.exception.code, "F3_CSV_REPORT_NOT_INSTALLED")
        self.assertNotEqual(caught.exception.code, "F3_STORAGE_UNAVAILABLE")

    def test_create_local_app_refuses_before_building_a_profile_or_an_app(self):
        built = []
        config = dict(socket="s", database="d", product_schema="schema", executor_role="r", context_id=CONTEXT)
        def refuse(store):
            raise GuardedWorkspaceError("F3_CSV_REPORT_NOT_INSTALLED")
        with patch.dict(os.environ), patch.object(guarded_dev, "load_config", lambda: config), patch.object(guarded_dev, "executor_dsn", lambda c: "dsn"), \
                patch.object(guarded_dev, "WebAccountStore", lambda dsn, schema: SimpleNamespace(dsn=dsn, schema=schema)), \
                patch.object(guarded_dev, "require_report_installed", refuse), \
                patch.object(guarded_dev, "build_profile", lambda *a: built.append("profile")), \
                patch.object(guarded_dev, "create_app", lambda **kw: built.append("app")):
            with self.assertRaises(GuardedWorkspaceError) as caught:
                guarded_dev.create_local_app()
        self.assertEqual(caught.exception.code, "F3_CSV_REPORT_NOT_INSTALLED")
        self.assertEqual(built, [])

    def test_create_local_app_checks_the_store_it_serves(self):
        seen = []
        config = dict(socket="s", database="d", product_schema="schema", executor_role="r", context_id=CONTEXT)
        with patch.dict(os.environ), patch.object(guarded_dev, "load_config", lambda: config), patch.object(guarded_dev, "executor_dsn", lambda c: "dsn"), \
                patch.object(guarded_dev, "WebAccountStore", lambda dsn, schema: SimpleNamespace(dsn=dsn, schema=schema)), \
                patch.object(guarded_dev, "require_report_installed", lambda store: seen.append(store)), \
                patch.object(guarded_dev, "build_profile", lambda store, ctx: ("PROFILE", store)), \
                patch.object(guarded_dev, "create_app", lambda **kw: kw):
            created = guarded_dev.create_local_app()
        self.assertEqual(len(seen), 1)
        self.assertIs(created["account_store"], seen[0])
        self.assertIs(created["guarded_profile"][1], seen[0])


class RuntimeConfig(Scratch):
    def setUp(self):
        self.runtime = self.make_dir()
        self.sock = self.runtime / "x.sock"
        self.patches = [patch.dict(os.environ, {guarded_dev.RUNTIME_ENV: str(self.runtime)}),
            patch.object(guarded_dev, "_checked_socket", lambda value: value)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write(self, value, mode=0o600, raw=None):
        path = self.runtime / guarded_dev.CONFIG_NAME
        path.write_bytes(raw if raw is not None else json.dumps(value).encode())
        os.chmod(path, mode)
        return path

    def test_valid_config_loads(self):
        value = good_config("/ok/.s.PGSQL.5432")
        self.write(value)
        self.assertEqual(guarded_dev.load_config(), value)

    def test_no_default_runtime_missing_variable_refuses(self):
        with patch.dict(os.environ):
            os.environ.pop(guarded_dev.RUNTIME_ENV)
            with self.assertRaises(ValueError) as caught:
                guarded_dev.load_config()
            self.assertIn("F3_RUNTIME_DIR_REQUIRED", str(caught.exception))
            with self.assertRaises(ValueError):
                guarded_dev.create_local_app()

    def test_missing_config_file_refuses(self):
        with self.assertRaises(OSError):
            guarded_dev.load_config()

    def test_runtime_variable_must_be_absolute_and_resolved(self):
        with patch.dict(os.environ, {guarded_dev.RUNTIME_ENV: "relative/dir"}), self.assertRaises(ValueError):
            guarded_dev.load_config()
        link = self.runtime.parent / (self.runtime.name + "-link")
        link.symlink_to(self.runtime)
        self.addCleanup(link.unlink)
        with patch.dict(os.environ, {guarded_dev.RUNTIME_ENV: str(link)}), self.assertRaises(ValueError):
            guarded_dev.load_config()

    def test_other_config_paths_are_refused(self):
        self.write(good_config("/ok/.s.PGSQL.5432"))
        with self.assertRaises(ValueError):
            guarded_dev.load_config(Path("/tmp/unapproved.json"))
        guarded_dev.load_config(self.runtime / guarded_dev.CONFIG_NAME)

    def test_directory_ownership_mode_and_file_mode_are_enforced(self):
        self.write(good_config("/ok/.s.PGSQL.5432"))
        os.chmod(self.runtime, 0o755)
        with self.assertRaises(ValueError):
            guarded_dev.load_config()
        os.chmod(self.runtime, 0o700)
        os.chmod(self.runtime / guarded_dev.CONFIG_NAME, 0o644)
        with self.assertRaises(ValueError):
            guarded_dev.load_config()

    def test_config_symlink_is_not_followed(self):
        target = self.make_dir() / "real.json"
        target.write_bytes(json.dumps(good_config("/ok/.s.PGSQL.5432")).encode())
        os.chmod(target, 0o600)
        (self.runtime / guarded_dev.CONFIG_NAME).symlink_to(target)
        with self.assertRaises(OSError):
            guarded_dev.load_config()

    def test_exact_key_set_schema_tag_names_and_context_are_enforced(self):
        base = good_config("/ok/.s.PGSQL.5432")
        variants = [dict(base, extra="x"), {k: v for k, v in base.items() if k != "context_id"}, dict(base, schema="finweb.f3.app_config/2"),
            dict(base, database="finweb_f3_a1"), dict(base, database=DB + "0"), dict(base, product_schema="f3_a1"),
            dict(base, product_schema="finweb_dev_env_ffffffff_f3"), dict(base, executor_role="f3_a1_executor"),
            dict(base, executor_role=DB + "_f3_legacy"), dict(base, context_id="C" * 64), dict(base, context_id="c" * 63), dict(base, context_id=5)]
        for index, variant in enumerate(variants):
            self.write(variant)
            with self.subTest(index=index), self.assertRaises(ValueError):
                guarded_dev.load_config()
        self.write(None, raw=b'{"schema":"a","schema":"b"}')
        with self.assertRaises(ValueError):
            guarded_dev.load_config()
        self.write(None, raw=b"[]")
        with self.assertRaises(ValueError):
            guarded_dev.load_config()


class SocketCheck(Scratch):
    def test_socket_must_be_a_resolved_pgsql_socket_in_an_owned_private_directory(self):
        base = self.make_dir()
        with self.assertRaises(ValueError):
            guarded_dev._checked_socket(5)
        with self.assertRaises(ValueError):
            guarded_dev._checked_socket("relative/.s.PGSQL.5432")
        with self.assertRaises(ValueError):
            guarded_dev._checked_socket(str(base / "not-a-pg-socket-name"))
        regular = base / ".s.PGSQL.5432"
        regular.write_bytes(b"")
        with self.assertRaises(ValueError):          # a regular file, not a socket
            guarded_dev._checked_socket(str(regular))
        open_dir = self.make_dir(0o755)
        (open_dir / ".s.PGSQL.5432").write_bytes(b"")
        with self.assertRaises(ValueError):          # directory not 0700
            guarded_dev._checked_socket(str(open_dir / ".s.PGSQL.5432"))

    def test_a_real_unix_socket_inside_a_private_directory_is_accepted(self):
        base = Path(tempfile.mkdtemp(prefix="fw")).resolve()
        self.addCleanup(self.rmtree, base)
        path = base / ".s.PGSQL.5999"
        server = socket_module.socket(socket_module.AF_UNIX)
        self.addCleanup(server.close)
        try:
            server.bind(str(path))
        except PermissionError as exc:
            self.skipTest("this environment forbids binding a Unix socket (%r); the positive case runs outside the sandbox" % (exc,))
        self.assertEqual(guarded_dev._checked_socket(str(path)), str(path))


class RoleRecordingOrder(unittest.TestCase):
    """L-1: a role is recorded for cleanup only after CREATE ROLE succeeded."""
    class Conn:
        def __init__(self, fail):
            self.fail, self.statements = fail, []

        def execute(self, statement):
            self.statements.append(statement)
            if self.fail:
                raise RuntimeError('role "x" already exists')

    def prov(self):
        return guarded_pg_provision.Provisioner("/s/.s.PGSQL.1", "d", "u", "finweb_it_guarded_0a1b2c3d")

    def test_failed_create_role_is_not_recorded(self):
        prov, seen = self.prov(), []
        prov.on_created = lambda kind, name: seen.append((kind, name))
        with self.assertRaises(RuntimeError):
            prov.create_role(self.Conn(True), "finweb_it_guarded_0a1b2c3d_ws_owner", "NOLOGIN")
        self.assertEqual(prov.created_roles, [])
        self.assertEqual(seen, [])

    def test_successful_create_role_is_recorded_after_the_statement(self):
        prov, seen = self.prov(), []
        conn = self.Conn(False)
        prov.on_created = lambda kind, name: seen.append((kind, name, len(conn.statements)))
        self.assertIsNone(prov.create_role(conn, "finweb_it_guarded_0a1b2c3d_ws_owner", "NOLOGIN"))
        self.assertIsNotNone(prov.create_role(conn, "finweb_it_guarded_0a1b2c3d_ws_issuer", "PASSWORD"))
        self.assertEqual(prov.created_roles, ["finweb_it_guarded_0a1b2c3d_ws_owner", "finweb_it_guarded_0a1b2c3d_ws_issuer"])
        self.assertEqual([item[2] for item in seen], [1, 2])    # recorded only once its statement had run

    def test_a_name_outside_the_run_prefix_is_refused_before_any_statement(self):
        prov, conn = self.prov(), self.Conn(False)
        with self.assertRaises(RuntimeError):
            prov.create_role(conn, "finweb_cp7_app", "NOLOGIN")
        with self.assertRaises(RuntimeError):
            prov.create_role(conn, "finweb_it_guarded_ffffffff_ws_owner", "NOLOGIN")
        self.assertEqual(conn.statements, [])
        self.assertEqual(prov.created_roles, [])


class StubProvisioner:
    instances = []
    fail_at = None

    def __init__(self, socket, database, admin_user, own):
        self.own, self.errors, self.connections, self.dropped = own, [], [], None
        self.on_created = lambda kind, name: None
        StubProvisioner.instances.append(self)

    def preflight(self):
        if StubProvisioner.fail_at == "preflight":
            raise RuntimeError("REFUSED: preflight")

    def refuse_if_prefix_exists(self):
        pass

    def create_database(self):
        self.on_created("database", self.own)

    def provision_f3(self, tag, *, http, plan):
        self.on_created("role", "%s_%s_owner" % (self.own, tag))
        raise RuntimeError("boom after one role")

    def close_connections(self):
        pass

    def drop_objects(self, *, db_created, roles):
        self.dropped = (db_created, list(roles))


class DevEnvBase(Scratch):
    def setUp(self):
        import contextlib
        import io
        for stream in (contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO())):
            stream.__enter__()
            self.addCleanup(stream.__exit__, None, None, None)
        StubProvisioner.instances, StubProvisioner.fail_at = [], None
        for item in (patch.object(dev_env, "Provisioner", StubProvisioner), patch.object(dev_env, "check_socket", lambda value: value),
                patch.object(dev_env, "require_private_socket", lambda value: None)):
            item.start()
            self.addCleanup(item.stop)
        self.parent = self.make_dir()
        self.args = SimpleNamespace(socket="/s/.s.PGSQL.1", database="admin_db", admin_user="admin", runtime_dir=str(self.parent / "rt"))


class DevEnvLifecycle(DevEnvBase):
    def test_a_failure_before_anything_is_created_cleans_up_without_touching_the_cluster(self):
        StubProvisioner.fail_at = "preflight"
        with self.assertRaises(RuntimeError):
            dev_env.up(self.args)
        self.assertEqual(len(StubProvisioner.instances), 1)         # teardown did not even construct a provisioner
        self.assertFalse((self.parent / "rt").exists())

    def test_a_failure_after_a_role_was_created_drops_exactly_that_role(self):
        with self.assertRaises(RuntimeError):
            dev_env.up(self.args)
        first, second = StubProvisioner.instances
        self.assertTrue(first.own.startswith("finweb_dev_env_"))
        self.assertEqual(second.dropped, (True, [first.own + "_f3_owner"]))
        self.assertFalse((self.parent / "rt").exists())

    def test_a_non_empty_runtime_directory_is_refused_untouched(self):
        runtime = self.parent / "rt"
        runtime.mkdir(mode=0o700)
        (runtime / "keep.txt").write_text("x")
        with self.assertRaises(dev_env.DevEnvError):
            dev_env.up(self.args)
        self.assertEqual(StubProvisioner.instances, [])
        self.assertEqual([p.name for p in runtime.iterdir()], ["keep.txt"])

    def test_state_file_is_private_and_down_refuses_foreign_names_and_mismatched_arguments(self):
        runtime = self.parent / "rt"
        runtime.mkdir(mode=0o700)
        state = dev_env.State(runtime, "/s/.s.PGSQL.1", "admin_db", "admin", "finweb_dev_env_" + TAG)
        state.record("database", "finweb_dev_env_" + TAG)
        state.record("role", "finweb_dev_env_%s_f3_owner" % TAG)
        self.assertEqual(stat.S_IMODE((runtime / dev_env.STATE_NAME).stat().st_mode), 0o600)
        loaded = dev_env.load_state(runtime)
        self.assertEqual(loaded["roles"], ["finweb_dev_env_%s_f3_owner" % TAG])
        with self.assertRaises(dev_env.DevEnvError):                       # arguments differ from the recorded ones
            dev_env.down(SimpleNamespace(socket="/s/.s.PGSQL.1", database="other", admin_user="admin", runtime_dir=str(runtime)))
        state.data["roles"].append("finweb_cp7_app")                        # a retained role must never be accepted
        state.save()
        with self.assertRaises(dev_env.DevEnvError):
            dev_env.load_state(runtime)
        self.assertEqual(StubProvisioner.instances, [])

    def test_down_drops_what_was_recorded_and_removes_its_files(self):
        runtime = self.parent / "rt"
        runtime.mkdir(mode=0o700)
        state = dev_env.State(runtime, "/s/.s.PGSQL.1", "admin_db", "admin", "finweb_dev_env_" + TAG)
        state.data["runtime_created"] = True
        state.record("database", "finweb_dev_env_" + TAG)
        state.record("role", "finweb_dev_env_%s_acct_app" % TAG)
        state.data["files"].append(dev_env.CONFIG_NAME)
        state.save()
        (runtime / dev_env.CONFIG_NAME).write_text("{}")
        self.assertEqual(dev_env.down(SimpleNamespace(socket="/s/.s.PGSQL.1", database="admin_db", admin_user="admin", runtime_dir=str(runtime))), 0)
        self.assertEqual(StubProvisioner.instances[0].dropped, (True, ["finweb_dev_env_%s_acct_app" % TAG]))
        self.assertFalse(runtime.exists())


class TeardownDeletesOnlyItsOwnConfig(DevEnvBase):
    """L-1: the state file's `files` list is never used as a path."""
    def state_with(self, files):
        runtime = self.parent / "rt"
        runtime.mkdir(mode=0o700)
        state = dev_env.State(runtime, "/s/.s.PGSQL.1", "admin_db", "admin", "finweb_dev_env_" + TAG)
        state.data["files"] = files
        state.save()
        return runtime

    def down(self, runtime):
        return dev_env.down(SimpleNamespace(socket="/s/.s.PGSQL.1", database="admin_db", admin_user="admin", runtime_dir=str(runtime)))

    def victim(self):
        path = self.parent / "victim.txt"
        path.write_text("keep me")
        return path

    def assert_survives(self, victim):
        self.assertEqual(victim.read_text(), "keep me")

    def test_absolute_path_is_refused_and_nothing_is_deleted(self):
        victim = self.victim()
        runtime = self.state_with([str(victim)])
        with self.assertRaises(dev_env.DevEnvError):
            self.down(runtime)
        self.assert_survives(victim)
        self.assertTrue((runtime / dev_env.STATE_NAME).exists())

    def test_dotdot_relative_path_is_refused_and_nothing_is_deleted(self):
        victim = self.victim()
        runtime = self.state_with(["../victim.txt"])
        with self.assertRaises(dev_env.DevEnvError):
            self.down(runtime)
        self.assert_survives(victim)

    def test_teardown_itself_ignores_the_files_list_even_if_validation_were_bypassed(self):
        victim = self.victim()
        runtime = self.state_with([])
        data = dev_env.load_state(runtime)
        data["files"] = [str(victim), "../victim.txt"]
        self.assertEqual(dev_env.teardown(runtime, data), [])
        self.assert_survives(victim)

    def test_symlink_named_as_the_config_is_not_followed_or_deleted(self):
        victim = self.victim()
        runtime = self.state_with([dev_env.CONFIG_NAME])
        (runtime / dev_env.CONFIG_NAME).symlink_to(victim)
        self.assertEqual(self.down(runtime), 1)                  # refused: not a regular file; reported, state kept
        self.assert_survives(victim)
        self.assertTrue((runtime / dev_env.CONFIG_NAME).is_symlink())
        self.assertTrue((runtime / dev_env.STATE_NAME).exists())

    def test_symlink_entry_in_files_pointing_outside_is_refused(self):
        victim = self.victim()
        runtime = self.state_with(["link.json"])
        (runtime / "link.json").symlink_to(victim)
        with self.assertRaises(dev_env.DevEnvError):
            self.down(runtime)
        self.assert_survives(victim)

    def test_the_regular_config_is_still_removed(self):
        runtime = self.state_with([dev_env.CONFIG_NAME])
        (runtime / dev_env.CONFIG_NAME).write_text("{}")
        self.assertEqual(self.down(runtime), 0)
        self.assertFalse((runtime / dev_env.CONFIG_NAME).exists())
        self.assertFalse((runtime / dev_env.STATE_NAME).exists())


class UpAppliesTheLaunchersSocketRule(Scratch):
    """L-2: a socket the launcher would refuse creates nothing and opens no PostgreSQL connection."""
    def run_up(self, socket_path):
        parent = self.make_dir()
        args = SimpleNamespace(socket=str(socket_path), database="admin_db", admin_user="admin", runtime_dir=str(parent / "rt"))
        StubProvisioner.instances = []
        with patch.object(dev_env, "Provisioner", StubProvisioner), patch.object(dev_env, "check_socket", lambda value: value), \
                patch("psycopg.connect", side_effect=AssertionError("a PostgreSQL connection was attempted")) as connect:
            with self.assertRaises(dev_env.DevEnvError) as caught:
                dev_env.up(args)
        self.assertEqual(StubProvisioner.instances, [])
        connect.assert_not_called()
        self.assertFalse((parent / "rt").exists())
        return str(caught.exception)

    def test_a_socket_directly_in_the_shared_tmp_is_refused_before_anything_is_created(self):
        message = self.run_up(Path("/tmp").resolve() / ".s.PGSQL.5432")
        self.assertIn("owned 0700 directory", message)
        self.assertIn("CP7", message)

    def test_a_socket_in_a_directory_that_is_not_0700_is_refused(self):
        open_dir = self.make_dir(0o755)
        (open_dir / ".s.PGSQL.5432").write_bytes(b"")
        self.assertIn("REFUSED", self.run_up(open_dir / ".s.PGSQL.5432"))

    def test_the_check_is_the_launchers_own_function(self):
        with patch.object(guarded_dev, "_checked_socket", side_effect=ValueError("sentinel")) as checked:
            with self.assertRaises(dev_env.DevEnvError) as caught:
                dev_env.require_private_socket("/x/.s.PGSQL.1")
        checked.assert_called_once_with("/x/.s.PGSQL.1")
        self.assertIn("sentinel", str(caught.exception))

    def test_help_and_docstrings_do_not_claim_the_shared_tmp_cluster_works(self):
        for text in (dev_env.__doc__, guarded_dev._checked_socket.__doc__):
            self.assertIn("private-socket cluster such as the CP7 cluster", " ".join(text.split()))
            self.assertNotIn("shared development cluster keeps its socket", " ".join(text.split()))


class PrintedCommands(unittest.TestCase):
    def test_commands_name_the_variables_and_ports_the_launchers_read(self):
        text = dev_env.commands(Path("/rt"), "/s/.s.PGSQL.1", DB, DB + "_acct", DB + "_acct_app")
        for needle in ("FINWEB_CP7_PG_SOCKET=/s/.s.PGSQL.1", "FINWEB_CP7_PG_DATABASE=" + DB, "FINWEB_CP7_PG_USER=" + DB + "_acct_app",
                "FINWEB_CP7_PG_SCHEMA=" + DB + "_acct", "web_api.account_dev:app", "--port 8000", "FINWEB_F3_RUNTIME_DIR=/rt",
                "web_api.guarded_dev:create_local_app --factory", "--port 8003", "vite.f3.config.ts", "playwright test"):
            self.assertIn(needle, text)

    def test_account_dev_reads_the_variables_the_commands_set(self):
        source = (HERE.parents[1] / "src/web_api/account_dev.py").read_text()
        for name in ("FINWEB_CP7_PG_SOCKET", "FINWEB_CP7_PG_DATABASE", "FINWEB_CP7_PG_USER", "FINWEB_CP7_PG_SCHEMA"):
            self.assertIn(name, source)
        self.assertEqual(guarded_dev.RUNTIME_ENV, "FINWEB_F3_RUNTIME_DIR")


if __name__ == "__main__":
    unittest.main()
