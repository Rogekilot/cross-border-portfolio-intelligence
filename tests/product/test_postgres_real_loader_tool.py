"""F1 R8, PostgreSQL: the loader's window tool (`real_tools.loader_window`) against disposable TEST installs.

All data is invented (`TEST_SWITCH`, synthetic sources, no network, no vendor payload) and every database is a disposable `finweb_it_rw_<hex>` of the real-gateway
kit; no database named in the reserved real namespace is ever created. The tool is run through its own `main`, on the loader role's connection (the seam the other
gated tools' tests use) with a prompt that must never be asked (an injected connection asks none), so these tests show the tool's behaviour against the gateway; the
password route itself is pinned by `test_real_preflight_static` and shown without a database in `test_real_tools_start`.

What is shown, with the expected values read FROM the database:
  * `load` (window 1): the release is in `md_release` with the proposal's projection digest, the UNBOUND candidate is registered, and an identical re-run reports
    "already loaded" and adds nothing (one registration, one release);
  * `register-bound` (window 2, step (4a)): REFUSED before the publish (the registration's financial context is a foreign key to the snapshot), DONE after it, and
    an identical re-run reconciles and adds nothing;
  * an UNKNOWN registration (the acknowledgement is lost after a commit): status 4 and "the window stays open"; `reconcile` then answers definitely, and before any
    registration it says "not found", which is not definite;
  * `check` prints the state it reads and writes nothing;
  * the tool refuses a session that is not the loader (the publisher, the owner after `SET ROLE`, a superuser) before it sends a write.

An install is shared by the tests of a class and a release is written once, so each class holds ONE test.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

from persistence import real_provenance_store as provstore  # noqa: E402
from real_gateway_kit import KIT, setUpModule, tearDownModule  # noqa: E402,F401
from real_tools import loader_window, real_inputs  # noqa: E402
from test_postgres_real_loader import MD_TABLES  # noqa: E402
from test_postgres_real_qualification import QualifiedChainCase, TEST_SWITCH  # noqa: E402

SOCKET = "/unused/.s.PGSQL.5432"            # the injected connection never uses it; the tool only validates the shape


class WindowCase(QualifiedChainCase):
    """A qualified invented release, the proposal file the owner 'reviewed', and the tool's seams."""

    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.proposal_path = str(Path(self.directory.name, "proposal.json"))
        Path(self.proposal_path).write_bytes(self.result.proposal)
        self.asked = []

    def build(self, args):
        return real_inputs.Rebuilt(TEST_SWITCH, self.store, self.result, self.ident)

    def window(self, command, *, extra=(), connect=None, user=None):
        out = io.StringIO()
        argv = [command, "--socket", SOCKET, "--database", KIT.prov.db, "--user", user or self.inst.roles["loader"], "--schema", self.s, "--store-root",
                str(self.world.root), "--release-name", "invented", "--file", "a" * 64, "--proposal", self.proposal_path] + list(extra)
        status = loader_window.main(argv, connect=connect or (lambda args, prompt: self.inst.connect("loader")), out=out,
                                    prompt=lambda role: self.asked.append(role) or "never asked", build=self.build)
        return status, out.getvalue()

    def registrations(self):
        return self.count("rwp_registration"), self.count("rwp_context")

    def md_counts(self):
        return {t: self.count(t) for t in MD_TABLES}


class LoadTests(WindowCase):
    INSTALL = "ldtload"

    def test_load_projects_the_release_registers_the_unbound_candidate_and_an_identical_rerun_adds_nothing(self):
        self.assertEqual(self.md_counts(), {t: 0 for t in MD_TABLES})
        status, text = self.window("load")
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("loaded release %s" % self.release_id, text)
        self.assertIn("unbound registered", text)
        (digest,), = self.owner.execute(f"SELECT projection_digest FROM {self.s}.md_release WHERE release_id=%s", (self.release_id,)).fetchall()
        self.assertEqual(digest, self.snapshot["projection_digest"])                       # read from the database, not from the tool's output
        self.assertEqual(self.registrations(), (1, 1))
        loaded = self.md_counts()
        self.assertGreater(loaded["md_file"], 0)
        # the registered candidate is the UNBOUND one: its context holds no financial context
        unbound = loader_window.cand.build_candidate(TEST_SWITCH, self.store, self.result)
        read = self.provenance().load_context(TEST_SWITCH, unbound.context_sha256, expected_members=unbound.members, witnesses=unbound.witnesses)
        self.assertIsNone(read.financial_context_sha256)
        # an identical re-run reconciles: the release is already loaded, the registration is the same operation, nothing is added
        status, text = self.window("load")
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("already loaded", text)
        self.assertEqual((self.md_counts(), self.registrations()), (loaded, (1, 1)))
        self.assertEqual(self.asked, [])                                                    # no password was asked: the connection was the seam's


class UnknownTests(WindowCase):
    INSTALL = "ldtunk"

    def test_an_unknown_registration_says_the_window_stays_open_and_reconcile_settles_it(self):
        # reconcile before anything is registered: not found, which is NOT a definite answer
        status, text = self.window("reconcile", extra=("--candidate", "unbound"))
        self.assertEqual(status, loader_window.EXIT_UNKNOWN, text)
        self.assertIn("NOT a definite answer", text)
        self.assertIn("THE LOADER WINDOW STAYS OPEN", text)
        self.assertIn("run the identical `loader_window load` command again", text)           # TR8T-L-1: the exit
        # the acknowledgement of the registration's commit is lost: the commit happened, the tool cannot know
        def lost(_self):
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        with mock.patch.object(provstore.RealProvenanceStore, "_after_commit", lost):
            status, text = self.window("load")
        self.assertEqual(status, loader_window.EXIT_UNKNOWN, text)
        self.assertIn("THE LOAD COMMITTED; whether the unbound registration committed is NOT known", text)       # TR8T-L-2: it did commit, and the tool must not say it did not
        self.assertNotIn("registration did not", text)
        self.assertNotIn("was not recorded", text)
        self.assertIn("THE LOADER WINDOW STAYS OPEN", text)
        self.assertIn("reconcile --candidate unbound", text)
        self.assertEqual(self.registrations(), (1, 1))                                      # it did commit: only the loader can tell, and reconcile does
        status, text = self.window("reconcile", extra=("--candidate", "unbound"))
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("unbound reconciled", text)
        self.assertNotIn("STAYS OPEN", text)
        self.assertEqual(self.registrations(), (1, 1))                                      # reconciling writes nothing
        # a reconcile of the bound candidate, which was never registered, is not found
        status, text = self.window("reconcile", extra=("--candidate", "bound"))
        self.assertEqual(status, loader_window.EXIT_UNKNOWN, text)


class BoundRegistrationTests(WindowCase):
    INSTALL = "ldtbound"

    def test_register_bound_is_refused_before_a_publish_done_after_it_and_an_identical_rerun_reconciles(self):
        self.assertEqual(self.window("load")[0], loader_window.EXIT_DONE)
        self.assertEqual(self.registrations(), (1, 1))
        # BEFORE the publish: the snapshot the registration is bound to does not exist, and the database refuses
        status, text = self.window("register-bound")
        self.assertEqual(status, loader_window.EXIT_REFUSED, text)
        self.assertIn("refused: the registration of the bound candidate", text)
        self.assertIn("nothing was recorded by this step", text)
        self.assertIn("RW_PROV_INPUT_MISSING", text)
        self.assertIn("has not been published", text)
        self.assertEqual(self.registrations(), (1, 1))
        # the owner's publish (a separate act; here the product publisher tool on the publisher role)
        published = self.publish_proposal()
        self.assertEqual((published.status, published.outcome), (0, "PUBLISHED"), published.text)
        # AFTER it
        status, text = self.window("register-bound")
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("bound registered", text)
        self.assertEqual(self.registrations(), (2, 2))
        bound = loader_window.cand.build_candidate(TEST_SWITCH, self.store, self.result, financial_context=self.result.context_id)
        read = self.provenance().load_context(TEST_SWITCH, bound.context_sha256, expected_members=bound.members, witnesses=bound.witnesses)
        self.assertEqual(read.financial_context_sha256, self.result.context_id)
        # an identical re-run reconciles and never duplicates; reconcile answers definitely
        status, text = self.window("register-bound")
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertEqual(self.registrations(), (2, 2))
        status, text = self.window("reconcile", extra=("--candidate", "bound"))
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("bound reconciled", text)
        self.assertEqual(self.registrations(), (2, 2))
        # check prints what it reads and writes nothing
        before = (self.registrations(), self.md_counts())
        status, text = self.window("check")
        self.assertEqual(status, loader_window.EXIT_DONE, text)
        self.assertIn("unbound candidate", text)
        self.assertIn("bound candidate", text)
        self.assertEqual(text.count(": registered"), 2, text)
        self.assertIn("equal to the proposal's", text)
        self.assertIn("may log in True, superuser False", text)
        self.assertEqual((self.registrations(), self.md_counts()), before)


class NotTheLoaderTests(WindowCase):
    INSTALL = "ldtrole"

    def test_a_session_that_is_not_the_loader_is_refused_before_anything_is_written(self):
        before = (self.md_counts(), self.registrations())
        # A TEST target takes the NAMED role, whichever it is (the install kind cannot be read as the loader, and only a real name fixes the role, in
        # `_agreement`); a role that is not the loader then stops at the database's own grants. Every other case stops at the tool's session check.
        cases = {
            "the publisher role, named": (lambda args, prompt: self.inst.connect("publisher"), self.inst.roles["publisher"], "InsufficientPrivilege"),
            "the owner after SET ROLE": (lambda args, prompt: self.inst.connect("owner"), self.inst.roles["owner"], "LOADER_ROLE"),
            "the superuser": (lambda args, prompt: self.inst.connect("admin"), KIT.prov.admin_user, "LOADER_ROLE"),
            "the loader with a user option that names another role": (lambda args, prompt: self.inst.connect("loader"), self.inst.roles["publisher"], "LOADER_ROLE"),
        }
        for label, (connect, user, expected) in cases.items():
            with self.subTest(label):
                status, text = self.window("load", connect=connect, user=user)
                self.assertEqual(status, loader_window.EXIT_REFUSED, text)
                self.assertIn(expected, text)
        self.assertEqual((self.md_counts(), self.registrations()), before)


class DefaultConnectionTests(WindowCase):
    INSTALL = "ldtconn"

    def test_a_test_database_is_reached_with_no_credential_by_the_tools_own_connection(self):
        """The default connection of a name outside the reserved namespace carries no password and no passfile (the dev cluster's roles authenticate by the socket).
        If the cluster asks the role for a password this test reports the refusal rather than passing."""
        socket = os.environ["FINWEB_PG_SOCKET"]
        out = io.StringIO()
        argv = ["check", "--socket", socket, "--database", KIT.prov.db, "--user", self.inst.roles["loader"], "--schema", self.s, "--store-root", str(self.world.root),
                "--release-name", "invented", "--file", "a" * 64, "--proposal", self.proposal_path]
        status = loader_window.main(argv, out=out, prompt=lambda role: self.fail("a password was asked for a TEST database"), build=self.build)
        self.assertEqual(status, loader_window.EXIT_DONE, out.getvalue())
        self.assertIn("release %s: not loaded" % self.release_id, out.getvalue())
        self.assertEqual(json.loads(self.result.proposal)["snapshot"]["release"]["release_id"], self.release_id)


if __name__ == "__main__":
    import unittest
    unittest.main()
