"""F1 R8 code-side blockers, no database (install plan section 14: G4, G8, G7, G9).

  * G4: the candidate registry's v1 manifest read accepts what the v1 download tool writes (reviewed request keys, a free-text anchor) and still refuses a
    secret-shaped or unknown key. Invented manifests only: the three real manifests live in the gitignored vendor folder, which a test may not read
    without the vendor gate (pinned), so they were checked once, read-only, by the engineer's run recorded in the plan.
  * G8: the real identity, conventions and policy are ONE product-side definition (`real_service.real_identity`), and the launcher's `WorldInputs` yields the
    digests the qualification run put in the proposal.
  * G7 / G9: `real_tools.r8_files` writes the expiry-evidence file and the launcher's contexts file offline, by exclusive create.
"""
from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import marketdata_exit_kit as x  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.manifest_v2 import V1_REQUEST_KEYS, read_registry_manifest_metadata  # noqa: E402
from marketdata.acquisition import PUBLIC_PARAMETER_KEYS  # noqa: E402
from performance.engine import performance_conventions  # noqa: E402
from persistence import real_digests as q  # noqa: E402
from marketdata.acquisition import AcquisitionError  # noqa: E402
from persistence import real_proposal  # noqa: E402
from persistence.real_workspace_store import _read_evidence  # noqa: E402  (the publish's own reader of the evidence file)
from performance_service.service import policy_reference  # noqa: E402
from real_service import real_identity, worlds  # noqa: E402
from real_tools import r8_files, real_inputs  # noqa: E402
from test_real_qualification import TEST_SWITCH, run as qualify  # noqa: E402
from web_api import real_launcher  # noqa: E402


def manifest_bytes(**changes):
    """An invented v1 manifest (the exit kit's mock world) with `changes` applied, in the canonical form the store writes."""
    world = x.build_world("mock")
    try:
        store = FileStore(world.root)
        index = store.index()
        obj = json.loads(index[sorted(index)[0]].read_text("utf-8"))
    finally:
        world.close()
    obj.update(changes)
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


class RegistryV1ManifestReadTests(unittest.TestCase):
    def test_the_manifest_the_v1_tool_writes_is_accepted_with_reviewed_request_keys_and_a_free_text_anchor(self):
        request = [[k, "v"] for k in sorted(V1_REQUEST_KEYS)]
        for label, changes in (("plain", {}), ("every reviewed key", {"request": request}),
                               ("an anchor with spaces", {"adjustment_anchor": "TIME_SERIES_DAILY as returned; label unverified"}),
                               ("a call anchor", {"adjustment_anchor": "stock_zh_a_hist adjust=qfq"})):
            with self.subTest(label):
                self.assertEqual(read_registry_manifest_metadata(manifest_bytes(**changes)).source_id, "mock.synthetic")

    def test_a_secret_shaped_unknown_or_repeated_key_or_value_is_refused(self):
        for label, changes in (("apikey", {"request": [["apikey", "k"]]}), ("token", {"request": [["token", "k"]]}), ("an unknown key", {"request": [["newkey", "v"]]}),
                               ("a repeated key", {"request": [["symbol", "a"], ["symbol", "b"]]}),
                               ("a key-like value", {"request": [["symbol", "apikey=1"]]}), ("a query string", {"request": [["endpoint", "https://h/p?x=1"]]}),
                               ("a secret anchor", {"adjustment_anchor": "call with token abc"}),
                               ("URL userinfo", {"request": [["endpoint", "https://user:hunter2@api.example.com/v1"]]}),
                               ("a fragment key", {"request": [["endpoint", "https://h/p#key=abc"]]}), ("a matrix key", {"request": [["endpoint", "https://h/p;key=abc"]]}),
                               ("access_key", {"request": [["symbol", "access_key abc"]]}), ("credential=", {"request": [["symbol", "credential=abc"]]}),
                               ("an anchor ending key=", {"adjustment_anchor": "label key=ABC"}), ("a non-text value", {"request": [["symbol", 1]]})):
            with self.subTest(label), self.assertRaises(AcquisitionError):
                read_registry_manifest_metadata(manifest_bytes(**changes))

    def test_the_v2_acquisition_allow_list_is_not_widened(self):
        self.assertFalse({"function", "outputsize", "idType", "origin"} <= set(PUBLIC_PARAMETER_KEYS), sorted(PUBLIC_PARAMETER_KEYS))
        self.assertFalse(any("key" in k.lower() or "token" in k.lower() for k in V1_REQUEST_KEYS))


class IdentityIsOneDefinitionTests(unittest.TestCase):
    def test_the_tools_and_the_launcher_use_the_same_objects(self):
        self.assertIs(real_inputs.REAL_INSTRUMENTS, real_identity.REAL_INSTRUMENTS)
        self.assertIs(real_inputs.REAL_POLICY, real_identity.REAL_POLICY)
        self.assertIs(real_inputs.real_resolver, real_identity.real_resolver)

    def test_the_launcher_builds_its_service_on_the_real_world_inputs_and_their_identity_digest_is_the_tools(self):
        built = {}

        class Spy:
            def __init__(self, schema, **kw):
                built.update(kw)
        with mock.patch("real_service.service.RealWorkspaceService", Spy), \
                mock.patch("web_api.real_mode_routes.create_real_mode_app", lambda **kw: object()):
            real_launcher.build(types.SimpleNamespace(schema="finweb_t", user="u", port=8765), lambda *a, **k: None, lambda role: "x", {}, object())
        inputs = built["world_inputs"]
        self.assertIs(type(inputs), worlds.WorldInputs)
        self.assertEqual(q.identity_digest(inputs.resolver), q.identity_digest(real_inputs.real_resolver()))
        self.assertEqual(dict(policy_reference(inputs.policy))["digest"], dict(policy_reference(real_inputs.REAL_POLICY))["digest"])
        # ids are a function of the registration order: a second build gives the same digest, so the proposal's is the one a later create rebuilds
        self.assertEqual(q.identity_digest(real_identity.real_resolver()), q.identity_digest(real_identity.real_resolver()))

    def test_the_identity_digest_in_a_proposal_equals_the_one_the_create_rebuilds(self):
        """Qualify with the tools' resolver and compare the snapshot's digest with the digest of the launcher's own `WorldInputs` resolver."""
        world = x.build_world("mock")
        try:
            result = qualify(world, resolver=real_identity.real_resolver())
            content = real_proposal.verify_proposal(result.proposal).snapshot.content
        finally:
            world.close()
        self.assertEqual(content["identity_digest"], q.identity_digest(real_identity.real_world_inputs().resolver))

    def test_market_conventions_as_a_function_of_the_calendars_give_the_digest_of_the_conventions_built_from_them(self):
        world = x.build_world("mock")
        try:
            calendars = world.built.calendars
            inputs = real_identity.real_world_inputs()
            fixed = market11_conventions(calendars)
            self.assertEqual(q.convention_digest(worlds.market_conventions_for(inputs, calendars), inputs.perf_conventions, world.release),
                             q.convention_digest(fixed, performance_conventions(), world.release))
            held = worlds.WorldInputs(real_identity.real_resolver(), fixed, performance_conventions(), real_identity.REAL_POLICY)
            self.assertIs(worlds.market_conventions_for(held, calendars), fixed)         # a conventions object is used as it is
        finally:
            world.close()


class R8FilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = x.build_world("mock")
        cls.ident = x.identity()
        cls.store = FileStore(cls.world.root)
        cls.result = qualify(cls.world, resolver=cls.ident)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proposal = str(Path(cls.tmp.name, "proposal.json"))
        Path(cls.proposal).write_bytes(cls.result.proposal)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.world.close()

    def setUp(self):
        self.out = io.StringIO()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return str(Path(self.dir.name, name))

    def build(self, args):
        return real_inputs.Rebuilt(TEST_SWITCH, self.store, self.result, self.ident)

    def contexts(self, generation="3", proposal=None, out=None):
        return r8_files.main(["contexts", "--store-root", str(self.world.root), "--release-name", "invented", "--file", "a" * 64,
                              "--proposal", proposal or self.proposal, "--generation", generation, "--out", out or self.path("C.json")], out=self.out, build=self.build)

    TRIPLES = {"alphavantage": ("PD-0066", "1" * 40, "a" * 64), "openfigi": ("PD-0068", "2" * 40, "b" * 64), "calendar": ("PD-0072", "3" * 40, "c" * 64)}

    def evidence(self, out=None, sha=None):
        argv = ["evidence", "--out", out or self.path("E.json")]
        for prefix, (pd, commit, doc) in self.TRIPLES.items():
            argv += ["--%s-pd" % prefix, pd, "--%s-commit" % prefix, commit, "--%s-sha" % prefix, sha if (sha and prefix == "openfigi") else doc]
        return r8_files.main(argv, out=self.out)

    def test_the_evidence_file_has_the_three_entries_of_pd_0068_answer_4(self):
        self.assertEqual(self.evidence(), r8_files.EXIT_DONE, self.out.getvalue())
        entries = json.loads(Path(self.path("E.json")).read_text("utf-8"))
        by = {e["source_id"]: e for e in entries}
        self.assertEqual(sorted(by), ["alphavantage.us", "calendar.manual", "openfigi"])
        self.assertEqual(by["alphavantage.us"]["basis"], "LEASE_TERM")
        self.assertEqual(by["alphavantage.us"]["term_end_not_after"], "2027-10-01T00:00:00Z")
        self.assertEqual([by[s]["basis"] for s in ("calendar.manual", "openfigi")], ["NOT_ASSESSED"] * 2)
        # TR8T-M-2: each entry cites its OWN decision
        for prefix, source in r8_files.SOURCE_PREFIXES:
            entry = by[source]
            self.assertEqual((entry["pd_id"], entry["git_commit"], entry["doc_sha256"]), self.TRIPLES[prefix], source)
        self.assertEqual(len(_read_evidence(self.path("E.json"))), 3)           # the publish's own reader accepts it

    def test_the_document_needs_a_triple_for_each_of_the_three_sources_and_no_other(self):
        good = {s: ("PD-0066", "1" * 40, "a" * 64) for s in ("alphavantage.us", "openfigi", "calendar.manual")}
        real_inputs.evidence_document(good)
        for bad in ({k: v for k, v in good.items() if k != "openfigi"}, {**good, "other": good["openfigi"]}, ("PD-0066", "1" * 40, "a" * 64)):
            with self.assertRaises(real_inputs.InputError):
                real_inputs.evidence_document(bad)

    def test_a_malformed_decision_triple_is_refused_and_nothing_is_written(self):
        for kwargs in ({"sha": "B" * 64}, {"sha": "b" * 63}):
            self.out.seek(0), self.out.truncate()
            self.assertEqual(self.evidence(**kwargs), r8_files.EXIT_REFUSED)
            self.assertFalse(Path(self.path("E.json")).exists())

    def test_the_contexts_file_is_parsed_by_the_launcher_names_the_reviewed_context_and_is_mode_0600(self):
        self.assertEqual(self.contexts(), r8_files.EXIT_DONE, self.out.getvalue())
        target = Path(self.path("C.json"))
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o600)
        pins = real_launcher.parse_contexts(target.read_bytes())
        self.assertEqual(sorted(pins), [self.result.context_id])
        (pin,) = pins.values()
        self.assertEqual(pin.generation, 3)
        self.assertNotIn(b"password", target.read_bytes().lower())

    def test_an_existing_output_is_never_overwritten(self):
        for command in (self.evidence, self.contexts):
            target = Path(self.path("exists.json"))
            target.write_bytes(b"keep")
            self.out.seek(0), self.out.truncate()
            self.assertEqual(command(out=str(target)), r8_files.EXIT_REFUSED)
            self.assertIn("RW_INPUT_OUTPUT_EXISTS", self.out.getvalue())
            self.assertEqual(target.read_bytes(), b"keep")
            target.unlink()

    def test_a_proposal_that_is_not_the_one_rebuilt_a_bad_generation_and_a_missing_proposal_write_nothing(self):
        other = Path(self.path("other.json"))
        other.write_bytes(b"{}")
        for label, kwargs in (("not a proposal", {"proposal": str(other)}), ("missing", {"proposal": self.path("none.json")}), ("zero", {"generation": "0"}),
                              ("text", {"generation": "x"})):
            with self.subTest(label):
                self.out.seek(0), self.out.truncate()
                try:
                    with mock.patch("sys.stderr", io.StringIO()):
                        status = self.contexts(**kwargs)
                except SystemExit:
                    status = r8_files.EXIT_REFUSED
                self.assertEqual(status, r8_files.EXIT_REFUSED)
                self.assertFalse(Path(self.path("C.json")).exists())

    def test_the_real_scope_without_sidecars_is_refused_before_anything_is_written(self):
        self.out.seek(0), self.out.truncate()
        status = r8_files.main(["contexts", "--store-root", str(self.world.root), "--release-name", "invented", "--file", "a" * 64,
                                "--proposal", self.proposal, "--generation", "1", "--out", self.path("C.json")], out=self.out)
        self.assertEqual(status, r8_files.EXIT_REFUSED)
        self.assertFalse(Path(self.path("C.json")).exists())


if __name__ == "__main__":
    unittest.main()
