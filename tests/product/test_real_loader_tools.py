"""F1 R8, no database: the loader's window tool (`real_tools.loader_window`) and the offline qualify command (`real_tools.qualify_run`).

Everything runs on INVENTED data (a synthetic store in a temporary directory, the `TEST_SWITCH` scope reached through the tools' `build` seam, the only way a test
scope reaches them) with a FAKE connection that records every statement it is sent. The REAL scope is reached only to show REFUSALS; no vendor payload is read,
no sidecar is invented, and no password exists (a prompt is a function the test passes, and the sentinel it returns never appears in any output).

What this shows: inputs are checked before any connection or prompt; the tool loads only the reviewed proposal; a name and a scope that disagree, and a real
target reached as any role but the real loader, are refused before anything is sent; every outcome of a load, a registration and a reconcile maps to its
`CommandResult` status (0 done, 2 refused, 4 unknown, 5 lock timeout); an UNKNOWN result says that the loader window stays open (TR6R-L1); the offline command
writes the proposal and the seed file, by exclusive create, and nothing when anything is refused. The PostgreSQL counterpart is
`test_postgres_real_loader_tool`.
"""
from __future__ import annotations

import hashlib
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

import marketdata_exit_kit as x  # noqa: E402
from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.resolver import InstrumentEntry  # noqa: E402
from persistence import real_loader, real_preflight as pf, real_provenance_store as provstore  # noqa: E402
from persistence.real_provenance import ProvenanceError  # noqa: E402
from persistence.real_scope import resolve_scope  # noqa: E402
from real_provenance_fixtures import encode  # noqa: E402
from real_tools import candidates as cand, identity_seed, loader_window, qualify_run, real_inputs  # noqa: E402
from test_real_qualification import TEST_SWITCH, run as qualify  # noqa: E402

SENTINEL = "pw-sentinel-not-a-real-password"
SOCKET = "/nonexistent/dir/.s.PGSQL.5432"
TEST_DB = "finweb_dev_env_0a1b2c3d"
SCHEMA = "finweb_t"
LOADER = "tool_loader"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class FakeLoaderConnection:
    """Records every statement as text. Answers the role read; never answers a write (there is none to answer)."""

    def __init__(self, *, user=LOADER, superuser=False, session_user=None, role="none"):
        self.row = (user, session_user or user, role, superuser, True)
        self.statements, self.closed = [], False
        self.autocommit = True

    def execute(self, query, params=()):
        text = " ".join(str(query).split())
        self.statements.append(text)
        row = self.row
        return types.SimpleNamespace(fetchone=lambda: row if "pg_roles" in text else None, fetchall=lambda: [])

    def close(self):
        self.closed = True

    def writes(self):
        return [s for s in self.statements if s.upper().split(" ")[0] in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "GRANT", "REVOKE", "DROP", "TRUNCATE", "COPY")]


class Fixture(unittest.TestCase):
    """One invented world per class, its qualification, the reviewed proposal file, and the tools' seams."""

    @classmethod
    def setUpClass(cls):
        cls.world = x.build_world("mock")
        cls.ident = x.identity()
        cls.store = FileStore(cls.world.root)
        cls.result = qualify(cls.world, resolver=cls.ident)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proposal_path = str(Path(cls.tmp.name, "proposal.json"))
        Path(cls.proposal_path).write_bytes(cls.result.proposal)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.world.close()

    def setUp(self):
        self.out = io.StringIO()
        self.asked, self.opened = [], []

    def build(self, args):
        return real_inputs.Rebuilt(TEST_SWITCH, self.store, self.result, self.ident)

    def prompt(self, role):
        self.asked.append(role)
        return SENTINEL

    def argv(self, command, *, database=TEST_DB, user=LOADER, proposal=None, extra=()):
        return [command, "--socket", SOCKET, "--database", database, "--user", user, "--schema", SCHEMA, "--store-root", str(self.world.root),
                "--release-name", "invented", "--file", "a" * 64, "--proposal", proposal or self.proposal_path] + list(extra)

    def connector(self, **kw):
        def connect(args, prompt):
            self.opened.append(args)
            self.conn = FakeLoaderConnection(**kw)
            return self.conn
        return connect

    def tool(self, command, *, connect=None, build=None, extra=(), **argv_kw):
        return loader_window.main(self.argv(command, extra=extra, **argv_kw), connect=connect or self.connector(), out=self.out, prompt=self.prompt,
                                  build=build or self.build)


class InputsAreCheckedBeforeAnythingIsSentTests(Fixture):
    def assertRefusedBeforeAConnection(self, status, text):
        self.assertEqual(status, loader_window.EXIT_REFUSED, self.out.getvalue())
        self.assertIn(text, self.out.getvalue())
        self.assertEqual((self.opened, self.asked), ([], []))                    # no connection opened, no password asked

    def test_a_proposal_that_is_not_the_one_rebuilt_is_refused_and_nothing_is_loaded_that_was_not_reviewed(self):
        other = qualify(self.world, resolver=self.ident, policy=f8b.ConfirmationPolicy(frozenset({"a.feed"}), frozenset({"a.filing"})))
        self.assertNotEqual(other.proposal, self.result.proposal)
        path = str(Path(self.tmp.name, "other.json"))
        Path(path).write_bytes(other.proposal)
        for command in loader_window.COMMANDS:
            with self.subTest(command):
                self.out.seek(0), self.out.truncate()
                extra = ("--candidate", "bound") if command == "reconcile" else ()
                self.assertRefusedBeforeAConnection(self.tool(command, proposal=path, extra=extra), "RW_LOADER_PROPOSAL_DIFFERS")

    def test_a_missing_or_malformed_proposal_file_is_refused(self):
        self.assertRefusedBeforeAConnection(self.tool("load", proposal="/nonexistent/proposal.json"), "RW_INPUT_UNREADABLE")
        bad = Path(self.tmp.name, "bad.json")
        bad.write_bytes(b"{}")
        self.out.seek(0), self.out.truncate()
        self.assertRefusedBeforeAConnection(self.tool("load", proposal=str(bad)), "LOADER_INPUT")

    def test_a_name_and_a_scope_that_disagree_are_refused(self):
        """A test scope against a name in the reserved REAL namespace; the REAL scope against any other name (a stub of the REAL qualification: no sidecar exists)."""
        self.assertRefusedBeforeAConnection(self.tool("load", database=pf.REAL_DATABASE), "RW_LOADER_TARGET_SCOPE")
        real = types.SimpleNamespace(scope=resolve_scope("REAL"), qualification=types.SimpleNamespace(proposal=b"p"))
        args = types.SimpleNamespace(database=TEST_DB, user=LOADER, proposal="p")
        self.assertIn("RW_LOADER_TARGET_SCOPE", loader_window._agreement(args, real, b"p"))

    def test_a_real_target_is_reached_as_the_real_loader_role_only(self):
        real = types.SimpleNamespace(scope=resolve_scope("REAL"), qualification=types.SimpleNamespace(proposal=b"p"))
        for user in (pf.REAL_ROLES["owner"], pf.REAL_ROLES["publisher"], pf.REAL_ROLES["executor"], "postgres", LOADER):
            with self.subTest(user):
                args = types.SimpleNamespace(database=pf.REAL_DATABASE, user=user, proposal="p")
                self.assertIn("RW_LOADER_ROLE", loader_window._agreement(args, real, b"p"))
        args = types.SimpleNamespace(database=pf.REAL_DATABASE, user=pf.REAL_ROLES["loader"], proposal="p")
        self.assertIsNone(loader_window._agreement(args, real, b"p"))

    def test_an_identifier_that_is_not_one_and_a_lock_timeout_out_of_range_are_refused(self):
        self.assertRefusedBeforeAConnection(self.tool("load", user='x"; DROP'), "LOADER_INPUT")
        self.out.seek(0), self.out.truncate()
        self.assertRefusedBeforeAConnection(self.tool("load", extra=("--lock-timeout-ms", "0")), "RW_INPUT_LOCK_TIMEOUT")

    def test_the_parser_has_no_credential_option_and_reconcile_needs_its_candidate(self):
        for flag in ("--password", "--passfile", "--dsn", "--env", "--test-switch", "--scope", "--no-gate"):
            with self.assertRaises(SystemExit):
                with mock.patch("sys.stderr", io.StringIO()):
                    loader_window.main(self.argv("load", extra=(flag, "x")), connect=self.connector(), out=self.out, build=self.build)
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr", io.StringIO()):
                loader_window.main(self.argv("reconcile"), connect=self.connector(), out=self.out, build=self.build)
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr", io.StringIO()):
                loader_window.main(self.argv("reconcile", extra=("--candidate", "both")), connect=self.connector(), out=self.out, build=self.build)


class TheSessionIsTheLoaderTests(Fixture):
    def test_a_session_that_is_not_the_named_loader_logged_in_as_itself_is_refused_and_sends_nothing_but_the_read(self):
        cases = {"a superuser": dict(superuser=True), "another role": dict(user="somebody_else"), "SET ROLE in force": dict(role="finweb_owner"),
                 "a session user that differs": dict(session_user="postgres")}
        for label, kw in cases.items():
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                status = self.tool("load", connect=self.connector(**kw))
                self.assertEqual(status, loader_window.EXIT_REFUSED)
                self.assertIn("LOADER_ROLE", self.out.getvalue())
                self.assertEqual(len(self.conn.statements), 1, self.conn.statements)          # the role read alone: no SET, no load
                self.assertTrue(self.conn.closed)

    def test_a_connection_that_fails_is_a_refusal_with_nothing_sent(self):
        def failing(args, prompt):
            raise psycopg.OperationalError("connection refused")
        self.assertEqual(self.tool("load", connect=failing), loader_window.EXIT_REFUSED)
        self.assertIn("LOADER_CONNECT_FAILED", self.out.getvalue())


class EveryOutcomeIsItsStatusTests(Fixture):
    """The `CommandResult` conventions of the publisher tool: 0 done, 2 refused, 4 unknown, 5 lock timeout."""

    def committed(self):
        return provstore.CommittedRegistration(uuid.uuid4(), b"response", sha(b"response"))

    def loaded(self, created=True):
        return types.SimpleNamespace(created=created, release_id=self.result.release.release_id, projection_digest="d" * 64)

    def run_load(self, *, load, register=None):
        register = register if register is not None else mock.Mock(return_value=self.committed())
        load = load if isinstance(load, mock.Mock) else mock.Mock(**({"side_effect": load} if isinstance(load, BaseException) else {"return_value": load}))
        with mock.patch.object(loader_window.q, "load_qualified", load), mock.patch.object(loader_window.cand, "register_candidate", register):
            status = self.tool("load")
        return status, load, register

    def test_a_load_and_its_registration_that_both_commit_are_done_and_the_window_may_close(self):
        status, load, register = self.run_load(load=self.loaded())
        self.assertEqual(status, loader_window.EXIT_DONE, self.out.getvalue())
        register.assert_called_once()
        self.assertEqual(register.call_args.args[2].bound_to, None)                    # the UNBOUND candidate: before the publish
        text = self.out.getvalue()
        self.assertIn("loaded release", text)
        self.assertIn("unbound registered", text)
        self.assertIn("closing it", text)
        self.assertNotIn("STAYS OPEN", text)
        self.assertNotIn(SENTINEL, text)

    def test_an_identical_rerun_reports_the_release_as_already_loaded_and_registers_it_again_by_the_same_operation(self):
        status, _load, register = self.run_load(load=self.loaded(created=False))
        self.assertEqual(status, loader_window.EXIT_DONE)
        self.assertIn("already loaded", self.out.getvalue())
        operation = cand.registration_operation_id(register.call_args.args[2].context_sha256)
        self.assertEqual(operation, cand.registration_operation_id(cand.build_candidate(TEST_SWITCH, self.store, self.result).context_sha256))

    def test_each_refusal_of_the_load_is_status_2_and_registers_nothing(self):
        for error in (real_loader.RealLoaderError("RW_LOADER_NO_IDENTITY", "x"), ValueError("typed"), psycopg.errors.InsufficientPrivilege("denied")):
            with self.subTest(type(error).__name__):
                self.out.seek(0), self.out.truncate()
                status, _load, register = self.run_load(load=error)
                self.assertEqual(status, loader_window.EXIT_REFUSED)
                register.assert_not_called()
                self.assertIn("nothing was recorded by this step", self.out.getvalue())

    def test_a_lock_timeout_of_the_load_is_status_5(self):
        status, _load, register = self.run_load(load=psycopg.errors.LockNotAvailable("lock"))
        self.assertEqual(status, loader_window.EXIT_LOCK_TIMEOUT)
        register.assert_not_called()

    def test_a_load_whose_outcome_is_not_known_is_status_4_and_says_the_window_stays_open(self):
        for error in (psycopg.OperationalError("server closed the connection"), psycopg.InterfaceError("closed")):
            with self.subTest(type(error).__name__):
                self.out.seek(0), self.out.truncate()
                status, _load, register = self.run_load(load=error)
                self.assertEqual(status, loader_window.EXIT_UNKNOWN)
                self.assertIn("THE LOADER WINDOW STAYS OPEN", self.out.getvalue())
                register.assert_not_called()

    def test_every_outcome_of_the_unbound_registration_after_a_committed_load(self):
        cases = {"refused": (ProvenanceError("RW_PROV_ROLE_REFUSED"), loader_window.EXIT_REFUSED),
                 "lock timeout": (ProvenanceError("RW_PROV_LOCK_TIMEOUT"), loader_window.EXIT_LOCK_TIMEOUT),
                 "unknown": (None, loader_window.EXIT_UNKNOWN)}
        for label, (error, status_expected) in cases.items():
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                register = mock.Mock(side_effect=error) if error is not None else mock.Mock(return_value=provstore.UnknownRegistration(uuid.uuid4()))
                status, _load, _register = self.run_load(load=self.loaded(), register=register)
                self.assertEqual(status, status_expected, self.out.getvalue())
                text = self.out.getvalue()
                if label == "unknown":
                    self.assertIn("THE LOAD COMMITTED; whether the unbound registration committed is NOT known", text)
                    self.assertNotIn("registration did not", text)
                else:
                    self.assertIn("THE LOAD COMMITTED; the unbound registration was not recorded", text)
                self.assertEqual("THE LOADER WINDOW STAYS OPEN" in text, label == "unknown")

    def test_an_unknown_registration_says_the_window_stays_open_until_reconcile_answers_definitely(self):
        """TR6R-L1: the only way to resolve an UNKNOWN registration is the loader, so the tool says that the window stays (or is reopened) and names the command."""
        with mock.patch.object(loader_window.cand, "register_candidate", mock.Mock(return_value=provstore.UnknownRegistration(uuid.uuid4()))):
            status = self.tool("register-bound")
        self.assertEqual(status, loader_window.EXIT_UNKNOWN)
        text = self.out.getvalue()
        self.assertIn("THE LOADER WINDOW STAYS OPEN", text)
        self.assertIn("do not set the loader NOLOGIN", text)
        self.assertIn("TR6R-L1", text)
        self.assertIn("reconcile --candidate bound", text)
        self.assertIn("reopens it", text)
        self.assertIn("retries nothing", text)

    def test_register_bound_registers_the_candidate_bound_to_the_published_context(self):
        register = mock.Mock(return_value=self.committed())
        with mock.patch.object(loader_window.cand, "register_candidate", register):
            self.assertEqual(self.tool("register-bound"), loader_window.EXIT_DONE, self.out.getvalue())
        built = register.call_args.args[2]
        self.assertEqual(built.bound_to, self.result.context_id)
        self.assertEqual(built.context_sha256, cand.build_candidate(TEST_SWITCH, self.store, self.result, financial_context=self.result.context_id).context_sha256)
        self.assertNotEqual(built.context_sha256, cand.build_candidate(TEST_SWITCH, self.store, self.result).context_sha256)
        self.assertEqual(self.conn.writes(), [])

    def test_reconcile_maps_committed_not_found_and_a_conflict(self):
        committed = self.committed()
        cases = {("bound", "committed"): (committed, loader_window.EXIT_DONE), ("unbound", "not found"): (provstore.UnknownRegistration(uuid.uuid4()), loader_window.EXIT_UNKNOWN),
                 ("bound", "conflict"): (ProvenanceError("RW_PROV_OPERATION_CONFLICT"), loader_window.EXIT_REFUSED)}
        for (which, label), (value, expected) in cases.items():
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                mocked = mock.Mock(side_effect=value) if isinstance(value, BaseException) else mock.Mock(return_value=value)
                with mock.patch.object(loader_window.cand, "reconcile_candidate", mocked):
                    status = self.tool("reconcile", extra=("--candidate", which))
                self.assertEqual(status, expected, self.out.getvalue())
                text = self.out.getvalue()
                if label == "not found":
                    self.assertIn("NOT a definite answer", text)
                    self.assertIn("THE LOADER WINDOW STAYS OPEN", text)
                    self.assertIn("run the identical `loader_window %s` command again" % ("register-bound" if which == "bound" else "load"), text)
                    self.assertIn("Only then may the owner close", text)
                    self.assertNotIn("Run `loader_window reconcile", text)               # no loop back to itself
                if label == "committed":
                    self.assertIn("reconciled", text)
                    self.assertNotIn("STAYS OPEN", text)

    def test_check_prints_and_writes_nothing(self):
        class Store:
            def __init__(self):
                self.calls = 0

            def load_context(self, *a, **k):
                self.calls += 1
                raise ProvenanceError("RW_PROV_INPUT_MISSING")
        with mock.patch.object(provstore, "RealProvenanceStore", lambda *a, **k: Store()):
            status = self.tool("check")
        self.assertEqual(status, loader_window.EXIT_DONE, self.out.getvalue())
        text = self.out.getvalue()
        self.assertIn("not registered", text)
        self.assertIn("print only", text)
        self.assertEqual(self.conn.writes(), [])

    def test_the_password_is_never_printed(self):
        self.run_load(load=self.loaded())
        self.assertNotIn(SENTINEL, self.out.getvalue())


class CandidateReconcileTests(Fixture):
    def test_reconcile_candidate_asks_the_store_for_the_operation_and_request_digest_of_the_identical_register(self):
        built = cand.build_candidate(TEST_SWITCH, self.store, self.result)
        operation = uuid.uuid5(cand.OPERATION_NAMESPACE, built.context_sha256)
        b = built.bundle
        request = encode(dict(schema="finweb.provenance_registration/1", scope=TEST_SWITCH.name, operation_id=str(operation), context_sha256=built.context_sha256,
                              payload_sha256s=[k for k, _ in b.payloads], manifest_sha256s=[k for k, _ in b.manifests], envelope_sha256s=[k for k, _ in b.envelopes],
                              witness_sha256s=[k for k, _ in b.witnesses]))                          # built here from the documented format
        seen = {}

        class Store:
            def reconcile(self, scope, operation_id, **kw):
                seen.update(kw, operation_id=operation_id)
                return provstore.UnknownRegistration(operation_id)

            def register(self, scope, operation_id, bundle, **kw):
                seen["register_operation"] = operation_id
                return provstore.UnknownRegistration(operation_id)
        self.assertIsInstance(cand.reconcile_candidate(Store(), TEST_SWITCH, built), provstore.UnknownRegistration)
        cand.register_candidate(Store(), TEST_SWITCH, built)
        self.assertEqual(seen["operation_id"], operation)
        self.assertEqual(seen["register_operation"], operation)                                      # the same operation id as the register
        self.assertEqual(seen["expected_request_sha256"], sha(request))
        self.assertEqual((seen["expected_context_sha256"], seen["expected_members"], seen["witnesses"]), (built.context_sha256, built.members, built.witnesses))

    def test_a_candidate_that_could_not_be_registered_cannot_be_reconciled(self):
        built = cand.build_candidate(TEST_SWITCH, self.store, self.result)
        with self.assertRaises(cand.CandidateError):
            cand.reconcile_candidate(object(), TEST_SWITCH, object())
        with self.assertRaises(Exception):
            cand.reconcile_candidate(object(), resolve_scope("SYNTHETIC_TEST"), built)           # another scope: the bundle's own scope field is refused


class OfflineQualifyTests(Fixture):
    def qualify_run(self, proposal_out, seed_out, *, build=None, extra=()):
        argv = ["--store-root", str(self.world.root), "--release-name", "invented", "--file", "a" * 64, "--proposal-out", proposal_out, "--seed-out", seed_out] + list(extra)
        return qualify_run.main(argv, out=self.out, build=build or self.build)

    def paths(self, name):
        directory = Path(tempfile.mkdtemp(dir=self.tmp.name, prefix=name))
        return str(directory / "p.json"), str(directory / "seed.json")

    def test_it_writes_the_proposal_and_the_seed_and_opens_no_connection(self):
        proposal_out, seed_out = self.paths("ok")
        with mock.patch.object(psycopg, "connect", side_effect=AssertionError("a connection was opened")), \
                mock.patch.object(pf, "terminal_prompt", side_effect=AssertionError("a password was asked")):
            self.assertEqual(self.qualify_run(proposal_out, seed_out), qualify_run.EXIT_DONE, self.out.getvalue())
        self.assertEqual(Path(proposal_out).read_bytes(), self.result.proposal)
        seed = Path(seed_out).read_bytes()
        self.assertEqual(seed, identity_seed.seed_bytes(self.ident))
        expected = json.loads(self.result.proposal)["snapshot"]["identity_digest"]
        self.assertEqual(identity_seed.check_digest(identity_seed.read_seed(seed), expected), expected)         # the file the owner-run seed tool accepts
        self.assertIn("No connection was opened, no password was asked", self.out.getvalue())

    def test_two_runs_write_the_same_bytes(self):
        a, b = self.paths("a"), self.paths("b")
        self.assertEqual(self.qualify_run(*a), 0)
        self.assertEqual(self.qualify_run(*b), 0)
        self.assertEqual((Path(a[0]).read_bytes(), Path(a[1]).read_bytes()), (Path(b[0]).read_bytes(), Path(b[1]).read_bytes()))

    def test_an_existing_output_is_never_overwritten_and_nothing_is_written(self):
        proposal_out, seed_out = self.paths("exists")
        Path(seed_out).write_bytes(b"owner's file")
        self.assertEqual(self.qualify_run(proposal_out, seed_out), qualify_run.EXIT_REFUSED)
        self.assertIn("RW_INPUT_OUTPUT_EXISTS", self.out.getvalue())
        self.assertFalse(Path(proposal_out).exists())
        self.assertEqual(Path(seed_out).read_bytes(), b"owner's file")
        same = Path(self.paths("same")[0])
        self.out.seek(0), self.out.truncate()
        self.assertEqual(self.qualify_run(str(same), str(same)), qualify_run.EXIT_REFUSED)
        self.assertIn("RW_INPUT_OUTPUT_TWICE", self.out.getvalue())

    def test_a_refused_qualification_writes_nothing(self):
        from persistence import real_sidecar

        def refusing(args):
            raise real_sidecar.SidecarError("RW_O5_FAILED", "O5 failed: no sidecar")
        proposal_out, seed_out = self.paths("refused")
        self.assertEqual(self.qualify_run(proposal_out, seed_out, build=refusing), qualify_run.EXIT_REFUSED)
        self.assertIn("RW_O5_FAILED", self.out.getvalue())
        self.assertEqual((Path(proposal_out).exists(), Path(seed_out).exists()), (False, False))

    def test_a_seed_that_does_not_match_the_proposals_identity_digest_is_not_written(self):
        proposal_out, seed_out = self.paths("seed")
        other = x.identity()
        other.register_instruments([InstrumentEntry("Other", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "OTHR", CurrencyCode("USD"))])
        wrong = real_inputs.Rebuilt(TEST_SWITCH, self.store, self.result, other)
        self.assertEqual(self.qualify_run(proposal_out, seed_out, build=lambda args: wrong), qualify_run.EXIT_REFUSED)
        self.assertIn("RW_SEED_DIGEST_DIFFERS", self.out.getvalue())
        self.assertEqual((Path(proposal_out).exists(), Path(seed_out).exists()), (False, False))

    def test_the_real_scope_over_a_store_without_the_files_is_refused_before_anything_is_written(self):
        """No vendor payload is read: the named file is not in the invented store, so the run refuses at the release cut."""
        proposal_out, seed_out = self.paths("real")
        self.assertEqual(self.qualify_run(proposal_out, seed_out, build=real_inputs.rebuild_real), qualify_run.EXIT_REFUSED)
        self.assertIn("RW_INPUT_FILE_MISSING", self.out.getvalue())
        self.assertEqual((Path(proposal_out).exists(), Path(seed_out).exists()), (False, False))

    def test_the_options_have_no_connection_or_credential_input(self):
        for flag in ("--socket", "--user", "--database", "--password"):
            with self.assertRaises(SystemExit):
                with mock.patch("sys.stderr", io.StringIO()):
                    qualify_run.main(["--store-root", "s", "--release-name", "n", "--file", "a" * 64, "--proposal-out", "p", "--seed-out", "s", flag, "x"])


class RealInputsTests(unittest.TestCase):
    def test_the_real_identity_is_deterministic_and_its_ids_are_a_function_of_the_registration_order(self):
        a, b = real_inputs.real_resolver(), real_inputs.real_resolver()
        self.assertEqual(identity_seed.seed_bytes(a), identity_seed.seed_bytes(b))
        listing = a.snapshot()[2][0]
        self.assertEqual(listing.listing_id.version, 5)
        self.assertEqual(listing.listing_id, b.snapshot()[2][0].listing_id)
        self.assertEqual((listing.ticker, listing.mic), ("AAPL", "XNAS"))
        self.assertEqual(a.exchange_mic(listing.listing_id), "XNAS")

    def test_a_release_is_cut_from_exactly_the_named_files_and_refuses_what_it_cannot_cut(self):
        world = x.build_world("mock")
        try:
            store = FileStore(world.root)
            shas = sorted(world.release.files)
            release = real_inputs.cut_release(store, "invented", shas)
            self.assertEqual(release.files, tuple(shas))
            self.assertEqual(real_inputs.cut_release(store, "invented", list(reversed(shas))).release_id, release.release_id)
            for label, args in {"a short hash": (store, "n", ["abc"]), "upper case": (store, "n", [shas[0].upper()]), "a duplicate": (store, "n", [shas[0], shas[0]]),
                                "no file": (store, "n", []), "a blank name": (store, " ", shas[:1]), "a file the store lacks": (store, "n", ["f" * 64])}.items():
                with self.subTest(label), self.assertRaises(real_inputs.InputError):
                    real_inputs.cut_release(*args)
        finally:
            world.close()


if __name__ == "__main__":
    unittest.main()
