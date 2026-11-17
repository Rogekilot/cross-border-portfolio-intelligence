"""F1 R7, no database: the START of the real-mode launcher and of the admission probe (design 1.2 rules 5.1 and 5.2; technical TR3R-L3).

R6 could not write these: the tools did not exist. Each case is a fact set in and a start (or a refusal to start) out, on a FAKE connection that records
every statement it is sent. The failing facts are R6's own case list (`test_real_preflight.ByCommandTests.FAILING`), judged by `pf.decide` and handed to the
tools through the one seam (`real_tool_gate._run_gate`). A tool that is refused must write nothing: no statement but the read of the install-kind rows
and the session settings reaches the connection, the app is never built, the server is never started and the probe never calls the gateway.
The static counterpart (options, environment reads, file reads, the credential route) is `test_real_preflight_static`.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg.pq import TransactionStatus  # noqa: E402

import test_real_preflight as rp  # noqa: E402
from persistence import real_preflight as pf, real_tool_gate  # noqa: E402
from persistence.real_workspace_context import RealWorkspaceError  # noqa: E402
from real_tools import admission_probe, loader_window  # noqa: E402
from web_api import real_launcher  # noqa: E402

SENTINEL = rp.SENTINEL
SOCKET = rp.SOCKET_DIR + "/.s.PGSQL." + rp.PORT
WRITES = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "GRANT", "REVOKE", "DROP", "TRUNCATE", "COPY", "SELECT \"", "RW_ADMIT")
REAL_NAME = pf.REAL_DATABASE
TEST_NAME = "finweb_dev_env_0a1b2c3d"
SCHEMA = "finweb"
EXECUTOR = "tool_executor"
ACCOUNT = "tool_account"


def contexts_file(tmp, **changes):
    member = {"role": "CORPORATE_ACTION", "payload_sha256": "1" * 64, "manifest_sha256": "2" * 64, "envelope_sha256": "3" * 64, "witness_sha256": "4" * 64}
    witness = {"expected_envelope_sha256": "3" * 64, "expected_manifest_sha256": "2" * 64, "actor_agent_id": "/root/invented_collector",
               "actor_role": "engineer", "approved_full_request_sha256": "5" * 64}
    value = {"schema": real_launcher.CONTEXTS_SCHEMA, "contexts": [{"context_id": "c" * 64, "generation": 2, "provenance": {
        "context_sha256": "6" * 64, "members": [member], "witnesses": [witness]}}]}
    value.update(changes)
    path = Path(tmp, "contexts.json")
    path.write_text(json.dumps(value))
    return str(path)


class ToolConnection:
    """Records every statement as text. Answers the install-kind read, the role self-check and the session settings; refuses the rest by recording."""

    def __init__(self, kinds=("TEST",), user=EXECUTOR, superuser=False, owner=False):
        self.kinds, self.user, self.superuser, self.owner = kinds, user, superuser, owner
        self.statements, self.closed, self.forced_rollback, self.in_transaction = [], False, [], False
        outer = self

        class Info:
            @property
            def transaction_status(self):
                return TransactionStatus.INTRANS if outer.in_transaction else TransactionStatus.IDLE
        self.info = Info()

    def transaction(self, force_rollback=False):
        outer = self

        class Tx:
            def __enter__(self):
                outer.in_transaction = True
                return outer

            def __exit__(self, *a):
                outer.in_transaction = False
                outer.forced_rollback.append(force_rollback)
                return False
        return Tx()

    def execute(self, query, params=()):
        text = " ".join((query if isinstance(query, str) else query.as_string(None)).split())
        self.statements.append(text)
        if "rw_install_info" in text:
            return types.SimpleNamespace(fetchall=lambda: [(k, 600) for k in self.kinds], fetchone=lambda: None)
        if "pg_roles r JOIN pg_namespace" in text:
            row = (self.user, self.superuser, self.owner) if "current_user::text" in text else (self.superuser, self.owner)
            return types.SimpleNamespace(fetchone=lambda: row, fetchall=lambda: [])
        return types.SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    def close(self):
        self.closed = True

    def writes(self):
        return [s for s in self.statements if s.upper().startswith(WRITES) and not s.upper().startswith("SET ")]


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = io.StringIO()
        self.connections = []

    def factory(self, **kw):
        def connect(args, *rest):
            conn = ToolConnection(**kw)
            self.connections.append(conn)
            return conn
        return connect

    def gate_decision(self, facts):
        return mock.patch.object(real_tool_gate, "_run_gate", return_value=pf.decide(facts, vantage="runtime"))

    def launch(self, database, kinds, *, facts=None, extra=(), connect=None, serve=None, file=None, **conn_kw):
        argv = ["--socket", SOCKET, "--database", database, "--user", EXECUTOR, "--schema", SCHEMA, "--account-user", ACCOUNT,
                "--contexts-file", file or contexts_file(self.tmp.name)] + list(extra)
        served = serve if serve is not None else mock.Mock()
        with self.gate_decision(facts if facts is not None else rp.clean()) as gate:
            status = real_launcher.main(argv, connect=connect or self.factory(kinds=kinds, **conn_kw), prompt=lambda role: SENTINEL, serve=served, out=self.out)
        return status, served, gate

    def probe(self, database, kinds, *, facts=None, purpose="ARCHIVE_EXPORT", admit=None, **conn_kw):
        owner, root = uuid.uuid4(), uuid.uuid4()
        argv = ["--socket", SOCKET, "--database", database, "--user", EXECUTOR, "--schema", SCHEMA, "--purpose", purpose, "--owner-id", str(owner),
                "--root-id", str(root), "--context", "c" * 64, "--generation", "2"]
        with self.gate_decision(facts if facts is not None else rp.clean()) as gate, mock.patch.object(admission_probe.store, "admit", new=admit or mock.Mock(
                side_effect=AssertionError("the gateway was called"))) as admitted:
            status = admission_probe.main(argv, connect=lambda args, prompt: self.factory(kinds=kinds, **conn_kw)(args), out=self.out)
        return status, admitted, gate


class TheDecisionComesFromTheDatabaseTests(Case):
    """5.2 by command: the name and the rows read, and nothing else, decide whether the gate runs (the table of R6's `ByCommandTests`, for `serve`/`admit`)."""

    CASES = {
        (REAL_NAME, ("REAL",)): ("REAL", True),
        (TEST_NAME, ("TEST",)): ("TEST", False),
        (REAL_NAME, ("TEST",)): ("REFUSE", False),
        (TEST_NAME, ("REAL",)): ("REFUSE", False),
        (REAL_NAME, ()): ("REFUSE", False),
        (TEST_NAME, ("TEST", "TEST")): ("REFUSE", False),
    }

    def test_the_launcher_runs_the_gate_for_a_real_install_and_none_for_a_test_install_and_refuses_every_other_pairing(self):
        for (database, kinds), (decision, gated) in self.CASES.items():
            with self.subTest(database=database, kinds=kinds):
                self.out.seek(0), self.out.truncate()
                status, served, gate = self.launch(database, kinds)
                self.assertEqual(gate.call_count, 1 if gated else 0)
                if decision == "REFUSE":
                    self.assertEqual(status, real_launcher.EXIT_REFUSED)
                    served.assert_not_called()
                else:
                    self.assertEqual(status, real_launcher.EXIT_OK, self.out.getvalue())
                    served.assert_called_once()
                    self.assertIn("%s target" % decision, self.out.getvalue())

    def test_the_probe_follows_the_same_table(self):
        for (database, kinds), (decision, gated) in self.CASES.items():
            with self.subTest(database=database, kinds=kinds):
                self.out.seek(0), self.out.truncate()
                lease = types.SimpleNamespace(purpose="ARCHIVE_EXPORT", context_id="c" * 64, generation=2, complete_by="t")
                status, admitted, gate = self.probe(database, kinds, admit=mock.Mock(return_value=lease))
                self.assertEqual(gate.call_count, 1 if gated else 0)
                if decision == "REFUSE":
                    self.assertEqual(status, admission_probe.EXIT_NOT_RUN)
                    admitted.assert_not_called()
                else:
                    self.assertEqual(status, admission_probe.EXIT_ADMITTED, self.out.getvalue())

    def test_no_argument_moves_a_run_to_another_row(self):
        """The parsers have no option that could: the command is a constant, the options are pinned by the static test, and an unknown option exits."""
        for flag in ("--preflight", "--no-preflight", "--test", "--kind", "--password", "--force"):
            with self.assertRaises(SystemExit):
                with mock.patch("sys.stderr", io.StringIO()):
                    real_launcher.main(["--socket", SOCKET, "--database", REAL_NAME, "--user", "u", "--schema", "s", "--account-user", "a",
                                        "--contexts-file", "f", flag, "x"])
            with self.assertRaises(SystemExit):
                with mock.patch("sys.stderr", io.StringIO()):
                    admission_probe.main(["--socket", SOCKET, "--database", REAL_NAME, "--user", "u", "--schema", "s", "--purpose", "ARCHIVE_READ",
                                          "--owner-id", "x", "--root-id", "y", "--context", "z", "--generation", "1", flag, "x"])


class EveryFailingFactRefusesToStartAndWritesNothingTests(Case):
    """R6's case list (`ByCommandTests.FAILING`), on fake facts: each makes the launcher and the probe refuse to start over a REAL install."""

    def test_the_launcher_refuses_each_failing_fact_and_writes_nothing(self):
        for label, make in rp.ByCommandTests.FAILING.items():
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                self.connections.clear()
                status, served, gate = self.launch(REAL_NAME, ("REAL",), facts=make(rp.clean()))
                self.assertEqual(status, real_launcher.EXIT_REFUSED, label)
                self.assertEqual(gate.call_count, 1)
                served.assert_not_called()                                                # the server was never started
                self.assertEqual(len(self.connections), 1, "only the executor's own connection was opened; the account role was not touched")
                conn = self.connections[0]
                self.assertEqual(conn.writes(), [], conn.statements)
                self.assertTrue(conn.closed)
                self.assertIn("PF_PREFLIGHT_REFUSED", self.out.getvalue())
                self.assertIn("Nothing was started and nothing was written", self.out.getvalue())
                self.assertNotIn(SENTINEL, self.out.getvalue())

    def test_the_probe_refuses_each_failing_fact_and_never_calls_the_gateway(self):
        for label, make in rp.ByCommandTests.FAILING.items():
            for purpose in admission_probe.PURPOSES:
                with self.subTest(label, purpose=purpose):
                    self.out.seek(0), self.out.truncate()
                    self.connections.clear()
                    status, admitted, gate = self.probe(REAL_NAME, ("REAL",), facts=make(rp.clean()), purpose=purpose)
                    self.assertEqual(status, admission_probe.EXIT_NOT_RUN, label)
                    admitted.assert_not_called()
                    self.assertEqual(self.connections[0].writes(), [])
                    self.assertNotIn(True, self.connections[0].forced_rollback)         # no admission transaction was even opened
                    self.assertIn("The probe did not run; nothing was written", self.out.getvalue())
                    self.assertNotIn(SENTINEL, self.out.getvalue())

    def test_a_gate_that_cannot_gather_its_facts_is_a_refusal_for_both_tools(self):
        with mock.patch.object(pf, "gather_facts", side_effect=RuntimeError("boom")):
            decision = real_tool_gate.start_gate(ToolConnection(("REAL",)), "serve", database=REAL_NAME, schema=SCHEMA, socket=SOCKET)
        self.assertFalse(decision.proceed)
        self.assertEqual(decision.code, "PF_PREFLIGHT_REFUSED")
        self.assertIn("PF_NOT_INSPECTED", "\n".join(decision.lines))

    def test_the_gate_serves_only_the_two_start_commands(self):
        for command in ("publish", "renew", "withdraw", "status", "x"):
            with self.assertRaises(ValueError):
                real_tool_gate.start_gate(ToolConnection(("REAL",)), command, database=REAL_NAME, schema=SCHEMA, socket=SOCKET)
        self.assertEqual(real_tool_gate.START_COMMANDS, ("serve", "admit"))
        self.assertTrue(set(real_tool_gate.START_COMMANDS) <= set(pf.GATED_COMMANDS))
        self.assertFalse(set(real_tool_gate.START_COMMANDS) & set(pf.NEVER_GATED_COMMANDS))

    def test_a_passing_set_of_facts_starts_both_tools(self):
        status, served, gate = self.launch(REAL_NAME, ("REAL",))
        self.assertEqual((status, gate.call_count), (real_launcher.EXIT_OK, 1))
        served.assert_called_once()


class LauncherStartTests(Case):
    def test_inputs_are_checked_before_any_connection_is_opened(self):
        bad_files = {"not json": "{", "wrong schema": json.dumps({"schema": "x", "contexts": []}),
                     "no contexts": json.dumps({"schema": real_launcher.CONTEXTS_SCHEMA, "contexts": []})}
        for label, text in bad_files.items():
            with self.subTest(label):
                path = Path(self.tmp.name, "bad.json")
                path.write_text(text)
                connect = mock.Mock(side_effect=AssertionError("a connection was opened"))
                status, served, _ = self.launch(TEST_NAME, ("TEST",), connect=connect, file=str(path))
                self.assertEqual(status, real_launcher.EXIT_REFUSED)
                served.assert_not_called()
        status, served, _ = self.launch(TEST_NAME, ("TEST",), file=str(Path(self.tmp.name, "missing.json")), connect=mock.Mock(side_effect=AssertionError("opened")))
        self.assertEqual(status, real_launcher.EXIT_REFUSED)
        for extra in (["--port", "80"], ["--port", "70000"]):
            status, served, _ = self.launch(TEST_NAME, ("TEST",), extra=extra, connect=mock.Mock(side_effect=AssertionError("opened")))
            self.assertEqual(status, real_launcher.EXIT_REFUSED)

    def test_the_contexts_file_is_strict(self):
        good = json.loads(Path(contexts_file(self.tmp.name)).read_text())
        pins = real_launcher.parse_contexts(json.dumps(good).encode())
        self.assertEqual(list(pins), ["c" * 64])
        pin = pins["c" * 64]
        self.assertEqual((pin.generation, pin.link.context_sha256), (2, "6" * 64))
        self.assertEqual([m.role for m in pin.link.members], ["CORPORATE_ACTION"])

        def broken(mutate):
            value = json.loads(json.dumps(good))
            mutate(value)
            return json.dumps(value).encode()
        defects = {
            "an extra key": lambda v: v.update(extra=1),
            "an extra context key": lambda v: v["contexts"][0].update(extra=1),
            "generation zero": lambda v: v["contexts"][0].update(generation=0),
            "generation a bool": lambda v: v["contexts"][0].update(generation=True),
            "a context id in capitals": lambda v: v["contexts"][0].update(context_id="C" * 64),
            "a short link digest": lambda v: v["contexts"][0]["provenance"].update(context_sha256="6" * 63),
            "no members": lambda v: v["contexts"][0]["provenance"].update(members=[]),
            "an extra member key": lambda v: v["contexts"][0]["provenance"]["members"][0].update(extra=1),
            "a bad role": lambda v: v["contexts"][0]["provenance"]["members"][0].update(role="NOT_A_KIND"),
            "a bad witness": lambda v: v["contexts"][0]["provenance"]["witnesses"][0].update(actor_agent_id="not an agent"),
            "a duplicate context": lambda v: v["contexts"].append(json.loads(json.dumps(v["contexts"][0]))),
            "nine contexts": lambda v: v.update(contexts=[dict(v["contexts"][0], context_id=("%x" % i) * 64) for i in range(9)]),
        }
        for label, mutate in defects.items():
            with self.subTest(label):
                with self.assertRaises(real_launcher.LaunchError) as caught:
                    real_launcher.parse_contexts(broken(mutate))
                self.assertEqual(caught.exception.code, "LAUNCH_CONTEXTS_SHAPE")

    def test_a_connection_that_fails_is_a_refusal_with_its_own_code_and_nothing_was_sent(self):
        def connect(*a):
            raise psycopg.OperationalError('connection failed: password authentication failed for user "x"')
        status, served, gate = self.launch(REAL_NAME, ("REAL",), connect=connect)
        self.assertEqual(status, real_launcher.EXIT_REFUSED)
        self.assertEqual(gate.call_count, 0)
        served.assert_not_called()
        self.assertIn("LAUNCH_CONNECT_FAILED", self.out.getvalue())

    def test_the_executor_role_must_be_the_named_one_and_no_superuser_and_not_the_schema_owner(self):
        for label, kw in {"another role": dict(user="somebody_else"), "a superuser": dict(superuser=True), "the schema owner": dict(owner=True)}.items():
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                status, served, _ = self.launch(TEST_NAME, ("TEST",), **kw)
                self.assertEqual(status, real_launcher.EXIT_REFUSED, label)
                self.assertIn("LAUNCH_ROLE", self.out.getvalue())
                served.assert_not_called()

    def test_an_account_role_that_is_a_superuser_or_the_schema_owner_is_refused_before_the_server_starts(self):
        opened = []

        def connect(args, user, prompt, autocommit):
            conn = ToolConnection(kinds=("TEST",), superuser=(user == ACCOUNT))
            opened.append((user, conn))
            return conn
        status, served, _ = self.launch(TEST_NAME, ("TEST",), connect=connect)
        self.assertEqual(status, real_launcher.EXIT_REFUSED)
        self.assertIn("LAUNCH_ACCOUNT_ROLE", self.out.getvalue())
        served.assert_not_called()

    def test_a_started_launcher_serves_loopback_only_and_the_app_is_the_real_mode_app(self):
        served = mock.Mock()
        status, served, _ = self.launch(TEST_NAME, ("TEST",), serve=served, extra=["--port", "8123"])
        self.assertEqual(status, real_launcher.EXIT_OK)
        app, port = served.call_args[0]
        self.assertEqual(port, 8123)
        self.assertEqual(real_launcher.LOOPBACK, "127.0.0.1")
        paths = {r.path for r in app.routes}
        self.assertIn("/api/real/v1/roots", paths)
        self.assertIn("/api/{path:path}", paths)
        self.assertNotIn("/api/v1/portfolios", paths)

    def test_the_launcher_writes_nothing_before_it_serves_even_when_it_starts(self):
        status, served, _ = self.launch(TEST_NAME, ("TEST",))
        self.assertEqual(status, real_launcher.EXIT_OK)
        for conn in self.connections:
            self.assertEqual(conn.writes(), [], conn.statements)

    def test_the_password_is_typed_once_per_role_kept_in_memory_and_never_printed(self):
        asked = []
        ask = real_launcher.remembered(lambda role: asked.append(role) or SENTINEL)
        self.assertEqual((ask("a"), ask("a"), ask("b")), (SENTINEL, SENTINEL, SENTINEL))
        self.assertEqual(asked, ["a", "b"])
        self.launch(REAL_NAME, ("REAL",))
        self.assertNotIn(SENTINEL, self.out.getvalue())

    def test_a_real_name_is_reached_with_scram_and_the_prompt_and_a_test_name_with_no_credential(self):
        captured = []

        def fake_connect(conninfo, **kw):
            captured.append(conninfo)
            return ToolConnection()
        args = types.SimpleNamespace(socket=SOCKET, database=REAL_NAME)
        asked = []
        with mock.patch.object(psycopg, "connect", fake_connect):
            real_launcher.default_connect(args, EXECUTOR, lambda role: asked.append(role) or SENTINEL, True)
        self.assertEqual(asked, [EXECUTOR])
        self.assertIn("require_auth='scram-sha-256'", captured[0])
        self.assertIn("passfile='/dev/null'", captured[0])
        captured.clear(), asked.clear()
        args = types.SimpleNamespace(socket=SOCKET, database=TEST_NAME)
        with mock.patch.object(psycopg, "connect", fake_connect):
            real_launcher.default_connect(args, EXECUTOR, lambda role: self.fail("a prompt for a TEST database"), True)
        self.assertNotIn("password", captured[0])
        self.assertNotIn("require_auth", captured[0])
        self.assertIn("passfile='/dev/null'", captured[0])


class AccountRolePasswordTests(Case):
    def test_the_account_roles_password_comes_from_the_prompt_alone(self):
        """PD-0078 consequence 2: over a REAL target the account connection asks the prompt for the account role, uses scram and carries no password in
        the connection string; there is no option, file or environment route (the static test pins the options and the reads)."""
        captured = []

        def fake_connect(conninfo, **kw):
            captured.append(conninfo)
            return ToolConnection()
        args = types.SimpleNamespace(socket=SOCKET, database=REAL_NAME)
        asked = []
        with mock.patch.object(psycopg, "connect", fake_connect):
            real_launcher.default_connect(args, ACCOUNT, lambda role: asked.append(role) or SENTINEL, True)
        self.assertEqual(asked, [ACCOUNT])
        self.assertIn("require_auth='scram-sha-256'", captured[0])
        self.assertNotIn(SENTINEL, captured[0].replace("password='%s'" % SENTINEL, ""))
        self.assertIn("passfile='/dev/null'", captured[0])
        parser = real_launcher._build_parser()
        options = {o for a in parser._actions for o in a.option_strings}
        self.assertIn("--account-user", options)
        self.assertFalse({o for o in options if "pass" in o or "secret" in o or "credential" in o})

    def test_the_launcher_asks_for_the_account_roles_password_over_a_real_target_when_it_opens_the_account_store(self):
        asked = []

        def connect(args, user, prompt, autocommit):
            prompt(user)
            asked.append(user)
            return ToolConnection(kinds=("REAL",), user=user)
        status, served, _ = self.launch(REAL_NAME, ("REAL",), connect=connect)
        self.assertEqual(status, real_launcher.EXIT_OK, self.out.getvalue())
        self.assertIn(ACCOUNT, asked)
        self.assertIn(EXECUTOR, asked)


class ProbeTests(Case):
    def lease(self, purpose="ARCHIVE_EXPORT"):
        return types.SimpleNamespace(purpose=purpose, context_id="c" * 64, generation=2, complete_by="2026-01-05T00:00:00+00:00")

    def test_the_output_says_what_it_is_and_the_transaction_is_rolled_back_whatever_the_outcome(self):
        for purpose in admission_probe.PURPOSES:
            with self.subTest("admitted", purpose=purpose):
                self.out.seek(0), self.out.truncate()
                self.connections.clear()
                status, admitted, _ = self.probe(TEST_NAME, ("TEST",), purpose=purpose, admit=mock.Mock(return_value=self.lease(purpose)))
                text = self.out.getvalue()
                self.assertEqual(status, admission_probe.EXIT_ADMITTED)
                self.assertTrue(text.startswith("direct gateway admission, not a product route"), text)
                self.assertIn("ADMITTED purpose=%s" % purpose, text)
                kw = admitted.call_args.kwargs
                self.assertEqual((kw["purpose"], kw["context_id"], kw["generation"]), (purpose, "c" * 64, 2))
                self.assertNotIn("new_root", kw)                                       # the gateway's default: no root is registered
                self.assertEqual([f for f in self.connections[0].forced_rollback if f], [True])   # ONE transaction forced to roll back (the gate's read is the other)
                self.assertEqual(self.connections[0].writes(), [])
        with self.subTest("refused"):
            self.out.seek(0), self.out.truncate()
            self.connections.clear()
            status, admitted, _ = self.probe(TEST_NAME, ("TEST",), admit=mock.Mock(side_effect=RealWorkspaceError("RW_RIGHT_REFUSED")))
            self.assertEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY)
            self.assertIn("REFUSED RW_RIGHT_REFUSED", self.out.getvalue())
            self.assertIn("direct gateway admission, not a product route", self.out.getvalue())
            self.assertEqual([f for f in self.connections[0].forced_rollback if f], [True])
        with self.subTest("a database error"):
            self.out.seek(0), self.out.truncate()
            self.connections.clear()
            status, _a, _ = self.probe(TEST_NAME, ("TEST",), admit=mock.Mock(side_effect=psycopg.OperationalError("boom")))
            self.assertEqual(status, admission_probe.EXIT_DATABASE_ERROR)                  # TR7-L-4: not a gateway refusal
            self.assertNotEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY)
            self.assertIn("DATABASE_ERROR OperationalError", self.out.getvalue())
            self.assertIn("NOT a gateway refusal", self.out.getvalue())
            self.assertNotIn("REFUSED", self.out.getvalue())
            self.assertEqual([f for f in self.connections[0].forced_rollback if f], [True])

    def test_the_probe_runs_as_the_named_executor_role_only(self):
        """TR7-L-4 (design 1.2 5.1): another login, a superuser or the schema owner is refused before the gateway is called."""
        for label, kw in (("another role", dict(user="finweb_real_publisher")), ("a superuser", dict(superuser=True)), ("the schema owner", dict(owner=True))):
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                self.connections.clear()
                status, admitted, _ = self.probe(TEST_NAME, ("TEST",), **kw)
                self.assertEqual(status, admission_probe.EXIT_NOT_RUN)
                self.assertIn("REFUSED PROBE_ROLE", self.out.getvalue())
                admitted.assert_not_called()
                self.assertEqual(self.connections[0].writes(), [])
                self.assertEqual([f for f in self.connections[0].forced_rollback if f], [])    # no admission transaction was even opened
        with self.subTest("the executor"):
            self.out.seek(0), self.out.truncate()
            status, _a, _ = self.probe(TEST_NAME, ("TEST",), admit=mock.Mock(return_value=self.lease()))
            self.assertEqual(status, admission_probe.EXIT_ADMITTED)
        with self.subTest("the role cannot be read"):
            class Unreadable(ToolConnection):
                def execute(self, query, params=()):
                    if "pg_roles r JOIN pg_namespace" in " ".join(str(query).split()):
                        raise psycopg.OperationalError("no catalog")
                    return super().execute(query, params)
            conn = Unreadable()
            self.assertFalse(admission_probe._is_the_executor(conn, types.SimpleNamespace(schema=SCHEMA, user=EXECUTOR)))

    def test_create_cannot_be_selected_and_a_bad_input_sends_nothing(self):
        base = ["--socket", SOCKET, "--database", TEST_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "--owner-id", str(uuid.uuid4()),
                "--root-id", str(uuid.uuid4()), "--context", "c" * 64, "--generation", "2"]
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr", io.StringIO()):
                admission_probe.main(base + ["--purpose", "EXECUTE_CREATE"], connect=mock.Mock(side_effect=AssertionError("opened")), out=self.out)
        for change in ({"--owner-id": "x"}, {"--root-id": str(uuid.uuid4()).upper()}, {"--context": "C" * 64}, {"--generation": "0"}, {"--schema": "A;DROP"}):
            argv = list(base) + ["--purpose", "ARCHIVE_READ"]
            for key, value in change.items():
                argv[argv.index(key) + 1] = value
            out = io.StringIO()
            status = admission_probe.main(argv, connect=mock.Mock(side_effect=AssertionError("opened")), out=out)
            self.assertEqual(status, admission_probe.EXIT_NOT_RUN, change)
            self.assertIn("PROBE_INPUT", out.getvalue())
        # a purpose that got past the parser is still refused by the constant tuple
        self.assertNotIn("EXECUTE_CREATE", admission_probe.PURPOSES)

    def test_a_connection_that_fails_is_not_run_and_nothing_was_sent(self):
        def connect(args, prompt):
            raise psycopg.OperationalError("connection failed")
        out = io.StringIO()
        argv = ["--socket", SOCKET, "--database", REAL_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "--purpose", "ARCHIVE_READ", "--owner-id",
                str(uuid.uuid4()), "--root-id", str(uuid.uuid4()), "--context", "c" * 64, "--generation", "1"]
        self.assertEqual(admission_probe.main(argv, connect=connect, out=out), admission_probe.EXIT_NOT_RUN)
        self.assertIn("PROBE_CONNECT_FAILED", out.getvalue())

    def test_the_probe_is_deterministic_in_its_operation_id(self):
        owner, root = uuid.uuid4(), uuid.uuid4()
        seen = []
        for _ in range(2):
            self.probe(TEST_NAME, ("TEST",), admit=mock.Mock(side_effect=lambda *a, **k: seen.append(k["operation_id"]) or self.lease()))
        self.assertEqual(len(set(seen)), 2)            # two different roots here; the id is a function of (root, generation, purpose), never of the clock
        self.assertEqual(admission_probe.real_tails.entry_operation_id(root, 2, "probe:ARCHIVE_EXPORT"),
                         admission_probe.real_tails.entry_operation_id(root, 2, "probe:ARCHIVE_EXPORT"))


class LoaderWindowToolStartTests(Case):
    """R8: the loader's window tool is a tool of the real path (the static test lists it and pins its password route); this is its START, without a database.
    It runs NO preflight gate (design 1.2 rule 5.1 names none for it; see its docstring and the report to the PM), so, unlike the launcher and the probe, no
    case here puts a failing gate in its way."""

    def test_a_real_name_is_reached_with_scram_and_the_prompt_and_a_test_name_with_no_credential(self):
        captured = []

        def fake_connect(conninfo, **kw):
            captured.append((conninfo, kw))
            return ToolConnection()
        asked = []
        for database, real in ((REAL_NAME, True), (TEST_NAME, False)):
            captured.clear(), asked.clear()
            args = types.SimpleNamespace(socket=SOCKET, database=database, user="tool_loader")
            with mock.patch.object(psycopg, "connect", fake_connect):
                loader_window._default_connect(args, lambda role: asked.append(role) or SENTINEL)
            conninfo, kw = captured[0]
            self.assertEqual(kw, {"autocommit": True})
            self.assertIn("passfile='/dev/null'", conninfo)
            if real:
                self.assertEqual(asked, ["tool_loader"])
                self.assertIn("require_auth='scram-sha-256'", conninfo)
                self.assertIn("password='%s'" % SENTINEL, conninfo)
            else:
                self.assertEqual(asked, [])
                self.assertNotIn("password", conninfo.replace("passfile", ""))
                self.assertNotIn("require_auth", conninfo)



if __name__ == "__main__":
    unittest.main()
