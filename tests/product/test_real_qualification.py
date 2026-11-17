"""F1 R4b: the qualification run (design 6.4, 7.1 R4b row; disposition note 5.3 obligations 1 and 2). Pure tests: no database.

Everything runs on INVENTED `TEST_SWITCH` data: a synthetic store in a temporary directory (`marketdata_exit_kit.build_world`), invented sources
with `synthetic = true`, no network, no download. The REAL scope is reached only to show its REFUSALS (it needs a sidecar per member, and an
invented source is synthetic, so the run stops): invented data is never marked `synthetic = false`, and no sidecar file is written for an invented
payload (design 4.2). The only read of the real `data/marketdata` is one read-only check that the confirmation table's digests are the files'.

The expected values are derived in the test from the store's own bytes and the engine's own registry digest (`performance.engine.registry_digest_of`,
the function the seal compares with), not from the run's output.
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(HERE))

import marketdata_exit_kit as x  # noqa: E402
from vendor_files import needs_vendor_files  # noqa: E402  (the vendor-payload gate; see vendor_files.py; the gated set is pinned in test_vendor_files_flag)
from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from performance.engine import performance_conventions, registry_digest_of  # noqa: E402
from persistence import market_data_store as mds, real_loader, real_proposal as rp, real_provenance as prov, real_sidecar as sc  # noqa: E402
from persistence.real_scope import resolve_scope  # noqa: E402
from real_tools import candidates as cand, qualification as q  # noqa: E402

TEST_SWITCH = resolve_scope("TEST_SWITCH", test_switch=True)
SYNTHETIC = resolve_scope("SYNTHETIC_TEST")
REAL = resolve_scope("REAL")
# the policy of the decided option B (PD-0072 / R4a proposal B); its digest is computed by hand in test_marketdata_r4a_inputs
POLICY = f8b.ConfirmationPolicy(frozenset({"none.admitted.feed"}), frozenset({"none.admitted.filing"}))
POLICY_DIGEST = "f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(world, scope=TEST_SWITCH, *, release=None, resolver=None, policy=POLICY, **kw):
    return q.qualify(scope, FileStore(world.root), release or world.release, world.adapters, resolver or x.identity(),
                     market_conventions=market11_conventions(world.built.calendars), perf_conventions=performance_conventions(), policy=policy,
                     catalog_calendars={}, **kw)


def tree_state(root):
    """Every file under `root` with its digest: what 'the run changed nothing' means."""
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(Path(root).rglob("*")) if p.is_file()}


class WorldCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = x.build_world("mock")

    @classmethod
    def tearDownClass(cls):
        cls.world.close()


class ReproducibleRunTests(WorldCase):
    def test_two_runs_over_the_same_store_write_the_same_bytes(self):
        a, b = run(self.world), run(self.world)
        self.assertEqual(a.proposal, b.proposal)
        self.assertEqual(a.context_id, b.context_id)

    def test_two_runs_over_two_stores_built_the_same_way_write_the_same_bytes(self):
        other = x.build_world("mock")
        try:
            self.assertEqual(run(self.world).proposal, run(other).proposal)
        finally:
            other.close()

    def test_a_different_input_moves_the_context(self):
        base = run(self.world)
        other_policy = f8b.ConfirmationPolicy(frozenset({"a.feed"}), frozenset({"a.filing"}))
        self.assertNotEqual(run(self.world, policy=other_policy).context_id, base.context_id)
        self.assertNotEqual(run(self.world, scope=SYNTHETIC).context_id, base.context_id)

    def test_the_run_changes_nothing_in_the_store_and_writes_no_file(self):
        before = tree_state(self.world.root)
        result = run(self.world)
        self.assertEqual(tree_state(self.world.root), before)
        self.assertTrue(result.proposal)


class ProposalContentTests(WorldCase):
    def setUp(self):
        self.result = run(self.world)
        self.document = json.loads(self.result.proposal)
        self.snapshot = self.document["snapshot"]

    def test_the_output_passes_the_proposal_verifier(self):
        verified = rp.verify_proposal(self.result.proposal)
        self.assertEqual(verified.scope.name, "TEST_SWITCH")
        self.assertEqual(verified.snapshot.context_id, self.result.context_id)
        self.assertEqual(self.document["context_id"], sha(canonical_json(self.snapshot).encode("utf-8")))
        self.assertEqual(self.snapshot["origin"], {"ledger_origin": "INVENTED_TEST_LEDGER", "market_origin": "SYNTHETIC_TEST", "personal_holdings": False, "synthetic": True})

    def test_the_members_are_the_releases_own_files_one_per_file_every_data_kind_included(self):
        """Obligation 2 (R3 disposition): one member per file of the release, the payload hash and the manifest's source, whatever the data kind."""
        expected = sorted((m.file_sha256, m.source_id) for m in self.world.manifests)
        self.assertEqual(sorted((m["payload_sha256"], m["source_id"]) for m in self.snapshot["members"]), expected)
        self.assertEqual({m.file_sha256 for m in self.world.manifests}, set(self.world.release.files))
        self.assertEqual(len(self.snapshot["members"]), len(self.world.release.files))
        kinds = {m.data_kind.value for m in self.world.manifests}
        self.assertTrue({"QUOTE", "FX", "CALENDAR"} <= kinds)                                      # calendars and FX files are members too

    def test_a_member_names_the_bytes_of_its_manifest_file_and_the_adapter_that_read_it(self):
        index = FileStore(self.world.root).index()
        for member in self.snapshot["members"]:
            path = index[member["payload_sha256"]]
            self.assertEqual(member["manifest_sha256"], sha(path.read_bytes()))                       # the digest of the manifest FILE (design 6.3)
            self.assertIsNone(member["acquisition_record_sha256"])                                    # the legacy null: a test scope has no sidecar
        by_sha = {s.file_sha256: s for s in self.world.built.summaries}
        for member in self.snapshot["members"]:
            self.assertEqual((member["adapter_id"], member["adapter_version"]),
                             (by_sha[member["payload_sha256"]].adapter_id, by_sha[member["payload_sha256"]].adapter_version))

    def test_used_source_digest_is_the_engine_digest_the_seal_compares_with(self):
        """Obligation 1: the engine's own `registry_digest_of(port)` is the value a service puts in `manifest.source_registry_digest`."""
        self.assertEqual(self.snapshot["registry"]["used_source_digest"], registry_digest_of(self.result.built.store))
        sources_with_a_file = {m.source_id for m in self.world.manifests}
        self.assertEqual({r["source_id"] for r in self.snapshot["source_records"]} >= sources_with_a_file, True)
        registry = FileStore(self.world.root).load_registry()
        from marketdata.manifest import source_registry_digest
        self.assertEqual(self.snapshot["registry"]["used_source_digest"], source_registry_digest([registry.get(s) for s in sorted(sources_with_a_file)]))
        # the store holds more sources than the release uses, so the full-registry digest differs
        self.assertGreater(len(self.snapshot["source_records"]), len(sources_with_a_file))
        self.assertNotEqual(self.snapshot["registry"]["full_registry_digest"], self.snapshot["registry"]["used_source_digest"])

    def test_the_proposal_carries_the_full_registry_of_the_store(self):
        ids = sorted(item["source_id"] for item in json.loads((self.world.root / "SOURCES.json").read_text("utf-8"))["sources"])
        self.assertEqual([r["source_id"] for r in self.snapshot["source_records"]], ids)
        self.assertTrue(all(r["terms_check"] is None for r in self.snapshot["source_records"]))       # a test scope stores no terms check

    def test_the_release_and_f8b_digests_are_derived_independently(self):
        release = self.world.release
        self.assertEqual(self.snapshot["release"]["release_id"], release.release_id)
        self.assertEqual(self.snapshot["release"]["release_digest"], sha(canonical_json({**release.content_obj(), "release_id": release.release_id}).encode("utf-8")))
        self.assertEqual(self.snapshot["f8b_policy_digest"], POLICY_DIGEST)
        self.assertEqual(self.snapshot["f8b_policy_digest"], sha(canonical_json({"feed": ["none.admitted.feed"], "filing": ["none.admitted.filing"]}).encode("utf-8")))

    def test_the_projection_digest_is_the_digest_the_loader_will_store(self):
        built = self.result.built
        contents = mds.stored_contents(built.store.export())
        self.assertEqual(self.snapshot["projection_digest"], sha(canonical_json(mds.projection_obj(self.world.release, contents, built.calendars)).encode("utf-8")))

    def test_the_calendar_convention_profile_and_identity_digests_are_defined_over_plain_data(self):
        built = self.result.built
        calendars = [mds.observation_obj(c) for c in built.calendars.calendars()]
        self.assertEqual(self.snapshot["calendar_digest"], sha(canonical_json(calendars).encode("utf-8")))
        conventions = {"market": market11_conventions(built.calendars).ids(), "performance": performance_conventions().ids(),
                       "release": [list(p) for p in self.world.release.conventions]}
        self.assertEqual(self.snapshot["convention_digest"], sha(canonical_json(conventions).encode("utf-8")))
        from marketdata import profiles
        sources = sorted({m.source_id for m in self.world.manifests})
        entries = [[s, None] if s not in profiles.SOURCES else [s, profiles.SOURCES[s].status, profiles.SOURCES[s].role, sorted(profiles.SOURCES[s].markets),
                                                              profiles.SOURCES[s].admitted] for s in sources]
        self.assertEqual(self.snapshot["profile_digest"], sha(canonical_json({"profile_set": profiles.PROFILE_SET_VERSION, "sources": entries}).encode("utf-8")))
        ident = x.identity()
        # hand-derived (TR4B-M2): the rows of x.identity() written out as plain data, in the order of their canonical-JSON text; not read back
        # through the function under test. The ids are the SequentialIds of the kit (1001, 1002, ... in hex: 0x3e9 is 1001).
        def u(n):
            return "00000000-0000-0000-0000-%012x" % n
        by_hand = {
            "issuers": [[u(0x3e9), "Apple Inc.", None], [u(0x3ec), "Tencent Holdings", None], [u(0x3ef), "Kweichow Moutai", None]],
            "instruments": [[u(0x3ea), u(0x3e9), "COMMON_STOCK", None], [u(0x3ed), u(0x3ec), "COMMON_STOCK", None],
                            [u(0x3f0), u(0x3ef), "COMMON_STOCK", None]],
            "listings": [[u(0x3eb), u(0x3ea), "XNAS", "NASDAQ", "AAPL", "USD", None, True, None],
                         [u(0x3ee), u(0x3ed), "XHKG", "HKEX", "0700", "HKD", None, True, None],
                         [u(0x3f1), u(0x3f0), "XSHG", "SSE", "600519", "CNY", None, True, None]],
            "identifiers": [[u(0x3eb), "TICKER", "AAPL", "XNAS", None, None, "register"],
                            [u(0x3eb), "VENDOR", "AAPL", "synthetic.alphavantage_us", None, None, "register"],
                            [u(0x3eb), "VENDOR", "AAPL", "synthetic.tsv_us", None, None, "register"],
                            [u(0x3ee), "TICKER", "0700", "XHKG", None, None, "register"],
                            [u(0x3ee), "VENDOR", "00700", "synthetic.sina_hk", None, None, "register"],
                            [u(0x3f1), "TICKER", "600519", "XSHG", None, None, "register"],
                            [u(0x3f1), "VENDOR", "600519", "synthetic.eastmoney_cn", None, None, "register"]]}
        self.assertEqual([len(by_hand[k]) for k in ("issuers", "instruments", "listings", "identifiers")], [3, 3, 3, 7])
        expected = sha(canonical_json(by_hand).encode("utf-8"))
        self.assertEqual(q.identity_digest(ident), expected)
        self.assertEqual(self.snapshot["identity_digest"], expected)

    def test_each_digest_moves_with_its_input(self):
        base = self.snapshot
        ident = x.identity()
        ident.add_vendor_id(x.lid(ident, "AAPL", "XNAS"), "synthetic.other", "AAPL-OTHER")
        self.assertNotEqual(q.identity_digest(ident), base["identity_digest"])
        changed = run(self.world, resolver=x.identity())
        self.assertEqual(changed.proposal, self.result.proposal)                                       # control: the same identity, the same bytes
        self.assertNotEqual(q.profile_digest(["mock.synthetic", "alphavantage.us"]), q.profile_digest(["mock.synthetic"]))
        self.assertNotEqual(q.release_digest(self.world.release), q.release_digest(MarketDataRelease(
            name="renamed", files=self.world.release.files, source_precedence=(), created_for="x")))


class _PermutedIdentity:
    """The same identity rows as `base`, handed out in another order: what a registry that registered them differently, or a database that returns
    them unordered, would give the digest. Only the two reads the digest uses."""

    def __init__(self, base, permute):
        self._base, self._permute = base, permute

    def snapshot(self):
        return tuple(tuple(self._permute(group)) for group in self._base.snapshot())

    def identifier_rows(self):
        return tuple(self._permute(self._base.identifier_rows()))


def _permutations_of(rows):
    """Distinct deterministic orders of a sequence: reversed, rotated by one and by two, and an order set by the digest of each element."""
    rows = list(rows)
    n = len(rows)
    yield list(reversed(rows))
    for k in (1, 2):
        yield rows[k % n:] + rows[:k % n] if n else rows
    yield sorted(rows, key=lambda row: hashlib.sha256(repr(row).encode("utf-8")).hexdigest())


class DigestOrderIndependenceTests(WorldCase):
    """TR4B-M2 (P12, P9): every digest of the proposal is a function of the SET of its inputs, not of the order they were registered or returned in."""

    def test_the_identity_digest_does_not_depend_on_the_order_the_rows_were_registered_in(self):
        """The reviewer's case: one registry registers an instrument's vendor ids in one order, a second registry the same ids in the other order."""
        def registry(vendor_ids):
            reg = x.InMemoryIdentityRegistry(x.kit.SequentialIds())
            reg.register_instruments([x.InstrumentEntry("Apple Inc.", x.SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", x.USD, vendor_ids=vendor_ids)])
            return reg
        forward = registry(((x.SRC_US, "AAPL"), (x.SRC_TSV, "AAPL")))
        backward = registry(((x.SRC_TSV, "AAPL"), (x.SRC_US, "AAPL")))
        self.assertNotEqual(forward.identifier_rows(), backward.identifier_rows())                       # control: the registries really were filled in another order
        self.assertEqual(sorted(map(repr, forward.identifier_rows())), sorted(map(repr, backward.identifier_rows())))   # ... with the same rows
        self.assertEqual(q.identity_digest(forward), q.identity_digest(backward))

    def test_the_identity_digest_is_the_same_for_every_order_of_its_rows(self):
        base = x.identity()
        expected = q.identity_digest(base)
        count = 0
        for permute in (lambda rows: reversed(list(rows)), lambda rows: list(rows)[1:] + list(rows)[:1], lambda rows: list(rows)[2:] + list(rows)[:2],
                        lambda rows: sorted(rows, key=lambda row: hashlib.sha256(repr(row).encode("utf-8")).hexdigest())):
            self.assertEqual(q.identity_digest(_PermutedIdentity(base, permute)), expected)
            count += 1
        self.assertEqual(count, 4)
        # control: the permutations really move the rows (a reversed list of 7 identifier rows is not the original order)
        self.assertNotEqual(list(_PermutedIdentity(base, lambda rows: reversed(list(rows))).identifier_rows()), list(base.identifier_rows()))

    def test_a_changed_row_still_changes_the_identity_digest(self):
        """Sensitivity control: sorting must not have made the digest blind to a row."""
        base = x.identity()
        digest = q.identity_digest(base)
        extra = x.identity()
        extra.add_vendor_id(x.lid(extra, "AAPL", "XNAS"), "synthetic.other", "AAPL-OTHER")
        self.assertNotEqual(q.identity_digest(extra), digest)
        self.assertNotEqual(q.identity_digest(_PermutedIdentity(extra, lambda rows: reversed(list(rows)))), digest)
        again = x.identity()
        again.add_vendor_id(x.lid(again, "AAPL", "XNAS"), "synthetic.other", "AAPL-OTHER2")
        self.assertNotEqual(q.identity_digest(again), q.identity_digest(extra))                       # the value of a row takes part

    def test_the_calendar_digest_does_not_depend_on_the_order_the_calendars_were_given_in(self):
        from marketdata.calendars import CalendarSet
        result = run(self.world)
        built = result.built
        contents = mds.stored_contents(built.store.export())
        days = list(built.calendars.calendars())
        self.assertGreater(len(days), 1)
        expected = q.calendar_digest(self.world.release, contents, built.calendars)
        for order in _permutations_of(days):
            self.assertEqual(q.calendar_digest(self.world.release, contents, CalendarSet(order)), expected)
        self.assertNotEqual(q.calendar_digest(self.world.release, contents, CalendarSet(days[1:])), expected)   # sensitivity

    def test_the_profile_digest_does_not_depend_on_the_order_or_repetition_of_the_source_ids(self):
        ids = ["mock.synthetic", "alphavantage.us", "eastmoney.cn", "sina.hk"]
        expected = q.profile_digest(ids)
        for order in _permutations_of(ids):
            self.assertEqual(q.profile_digest(order), expected)
        self.assertEqual(q.profile_digest(ids + ids), expected)
        self.assertNotEqual(q.profile_digest(ids[:3]), expected)

    def test_the_convention_digest_does_not_depend_on_the_conventions_object_it_was_built_by(self):
        """The id lists are built in a defined order inside the convention sets; two separately built sets give the same digest, a different release a different one."""
        calendars = self.world.built.calendars
        a = q.convention_digest(market11_conventions(calendars), performance_conventions(), self.world.release)
        b = q.convention_digest(market11_conventions(calendars), performance_conventions(), self.world.release)
        self.assertEqual(a, b)
        self.assertEqual(a, sha(canonical_json({"market": market11_conventions(calendars).ids(), "performance": performance_conventions().ids(),
                                                "release": [list(p) for p in self.world.release.conventions]}).encode("utf-8")))


class ReleaseOwnRowsTests(WorldCase):
    def test_a_file_of_the_store_outside_the_release_is_not_a_member(self):
        dropped = next(m for m in self.world.manifests if m.data_kind.value == "FX")
        kept = [m for m in self.world.manifests if m is not dropped]
        release = MarketDataRelease.from_manifests("subset", kept, [])
        result = run(self.world, release=release)
        members = json.loads(result.proposal)["snapshot"]["members"]
        self.assertEqual(sorted(m["payload_sha256"] for m in members), sorted(m.file_sha256 for m in kept))
        self.assertNotIn(dropped.file_sha256, {m["payload_sha256"] for m in members})
        self.assertEqual(len(members), len(self.world.manifests) - 1)
        # the used-source digest follows the release's own files, not the store's
        self.assertEqual(json.loads(result.proposal)["snapshot"]["registry"]["used_source_digest"], registry_digest_of(result.built.store))

    def test_a_release_that_names_a_file_the_store_lacks_stops_the_run(self):
        release = MarketDataRelease(name="ghost", files=tuple(sorted(self.world.release.files + ("f" * 64,))), source_precedence=())
        with self.assertRaises(Exception) as caught:
            run(self.world, release=release)
        self.assertEqual(type(caught.exception).__name__, "ReleaseFileMissingError")


class ScopeAndSidecarTests(WorldCase):
    def test_a_test_scope_takes_no_sidecar_and_stores_no_digest_of_one(self):
        invented = sc.encode_sidecar(payload_sha256="a" * 64, manifest_sha256="b" * 64, pd_id="PD-9001", git_commit="a" * 40, doc_sha256="b" * 64,
                                     request="invented", tool="invented", terms_check_reference="invented")
        for scope in (TEST_SWITCH, SYNTHETIC):
            with self.assertRaises(q.QualificationError) as caught:
                run(self.world, scope, sidecars=[invented])
            self.assertEqual(caught.exception.code, "RW_O5_SIDECAR_IN_TEST_SCOPE")
            result = run(self.world, scope)
            self.assertTrue(result.o5_bypassed)
            self.assertTrue(all(m.acquisition_record_sha256 is None for m in result.members))

    def test_the_real_scope_refuses_without_a_valid_sidecar_for_every_member_and_lists_every_failure(self):
        with self.assertRaises(sc.SidecarError) as caught:
            run(self.world, REAL)
        self.assertEqual(caught.exception.code, sc.O5_FAILED)
        members = {m.file_sha256 for m in self.world.manifests}
        self.assertEqual({sha for sha, _code in caught.exception.failures}, members)                        # every member, not the first
        self.assertEqual({code for _sha, code in caught.exception.failures}, {sc.O5_LEGACY_NULL, sc.O5_MISSING})

    def test_the_real_scope_with_valid_in_memory_sidecars_still_refuses_synthetic_sources_and_writes_nothing(self):
        """The control of design 4.2: O5 holds (each member has a valid sidecar, in memory), and the run is still refused, by the origin of the
        invented sources: nothing about the invented data is accepted as real, and nothing is written."""
        index = FileStore(self.world.root).index()
        sidecars = [sc.encode_sidecar(payload_sha256=m.file_sha256, manifest_sha256=sha(index[m.file_sha256].read_bytes()), pd_id="PD-9001",
                                      git_commit="a" * 40, doc_sha256="b" * 64, request="invented request", tool="invented tool",
                                      terms_check_reference="invented reference") for m in self.world.manifests]
        before = tree_state(self.world.root)
        with self.assertRaises(q.QualificationError) as caught:
            run(self.world, REAL, sidecars=sidecars)
        self.assertEqual(caught.exception.code, "RW_ORIGIN_MIXED")
        self.assertEqual(tree_state(self.world.root), before)

    def test_the_real_scope_refuses_sidecars_that_match_every_file_but_fail_a_predicate_each(self):
        """Every sidecar names its file's digests, so the member's slot is filled and the proposal writer alone would accept it; only O5 judges the
        approver role and the decision triple. The run lists both for every member and writes nothing."""
        index = FileStore(self.world.root).index()
        for label, change, code in (("a role that is not the owner's", dict(approver_role="a person"), sc.O5_ROLE),
                                    ("a decision triple that is missing", dict(pd_id=None, git_commit=None, doc_sha256=None), sc.O5_TRIPLE)):
            with self.subTest(label):
                sidecars = [sc.encode_sidecar(**{**dict(payload_sha256=m.file_sha256, manifest_sha256=sha(index[m.file_sha256].read_bytes()),
                                                         pd_id="PD-9001", git_commit="a" * 40, doc_sha256="b" * 64, request="invented request",
                                                         tool="invented tool", terms_check_reference="invented reference"), **change})
                            for m in self.world.manifests]
                with self.assertRaises(sc.SidecarError) as caught:
                    run(self.world, REAL, sidecars=sidecars)
                self.assertEqual({(s, c) for s, c in caught.exception.failures}, {(m.file_sha256, code) for m in self.world.manifests})

    def test_a_real_scope_run_that_fails_o5_is_not_hidden_by_a_partial_set_of_sidecars(self):
        index = FileStore(self.world.root).index()
        first = self.world.manifests[0]
        one = [sc.encode_sidecar(payload_sha256=first.file_sha256, manifest_sha256=sha(index[first.file_sha256].read_bytes()), pd_id="PD-9001",
                                 git_commit="a" * 40, doc_sha256="b" * 64, request="invented", tool="invented", terms_check_reference="invented")]
        with self.assertRaises(sc.SidecarError) as caught:
            run(self.world, REAL, sidecars=one)
        failed = {sha_ for sha_, _code in caught.exception.failures}
        self.assertNotIn(first.file_sha256, failed)
        self.assertEqual(failed, {m.file_sha256 for m in self.world.manifests} - {first.file_sha256})


class ConfirmationTableTests(WorldCase):
    PAYLOAD_AV = "066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb"
    PAYLOAD_UW = "b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc"
    MANIFEST_AV = "268535ddc8b6284a144cbe810668a3586a9e574f257b438794bbe08c1f0efb82"
    MANIFEST_UW = "7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738"
    MANIFEST_XNGS = "cb4d862d37e628b31c7a009f53d461188583e2090934de2bb080c08e21963c8d"            # evidence only, never a member (design 6.3)

    def test_the_table_is_the_two_rows_of_design_6_3(self):
        self.assertEqual({k: v[0] for k, v in q.HG4_CONFIRMATION_TABLE.items()}, {self.PAYLOAD_AV: self.MANIFEST_AV, self.PAYLOAD_UW: self.MANIFEST_UW})

    @needs_vendor_files
    def test_the_table_equals_the_real_files(self):
        """READ-ONLY: the digests are recomputed from the owner's files under `data/marketdata`; nothing is copied or written. A missing file is an error; a cloud run
        sets the vendor-payload flag described in tests/product/vendor_files.py, which skips this test."""
        root = HERE.parents[1] / "data" / "marketdata" / "files"
        files = {self.PAYLOAD_AV: root / "alphavantage.us/quote/2026-10-01/AAPL_compact.csv", self.PAYLOAD_UW: root / "openfigi/identity/2026-10-23/AAPL_UW.json"}
        for payload, path in files.items():
            self.assertEqual(sha(path.read_bytes()), payload)
            self.assertEqual(sha(Path(str(path) + ".manifest.json").read_bytes()), q.HG4_CONFIRMATION_TABLE[payload][0])

    def test_every_member_is_listed_against_the_table_with_its_status_in_the_real_scope(self):
        # the classification is the run's; the REAL run cannot finish on invented data, so the function the run uses is called directly
        for payload, manifest, registered, expected in (
                (self.PAYLOAD_AV, self.MANIFEST_AV, frozenset(), q.CONFIRMED), (self.PAYLOAD_UW, self.MANIFEST_UW, frozenset(), q.CONFIRMED),
                (self.PAYLOAD_UW, self.MANIFEST_XNGS, frozenset(), q.MANIFEST_DIFFERS),
                ("d" * 64, "e" * 64, frozenset(), q.NOT_CONFIRMED), ("d" * 64, "e" * 64, frozenset({"d" * 64}), q.REGISTERED_CHECK)):
            self.assertEqual(q.classify(REAL, payload, manifest, q.HG4_CONFIRMATION_TABLE, registered), expected)
        for scope in (TEST_SWITCH, SYNTHETIC):
            self.assertEqual(q.classify(scope, self.PAYLOAD_AV, self.MANIFEST_AV, q.HG4_CONFIRMATION_TABLE, frozenset()), q.TEST_SCOPE)

    def test_a_test_scope_listing_names_every_member_and_marks_the_table_as_not_applicable(self):
        result = run(self.world)
        self.assertEqual({r.payload_sha256 for r in result.rows}, {m.file_sha256 for m in self.world.manifests})
        self.assertEqual({r.confirmation for r in result.rows}, {q.TEST_SCOPE})
        self.assertEqual(result.table_rows_without_member, ())
        text = "\n".join(result.lines())
        self.assertIn("scope TEST_SWITCH", text)
        self.assertIn("bypassed in a test scope", text)
        for row in result.rows:
            self.assertIn(row.payload_sha256[:12], text)
        self.assertFalse(result.needs_review)


class ReviewFlagTests(unittest.TestCase):
    def test_a_series_the_label_test_contradicts_is_carried_as_needs_review(self):
        """A Saturday print in the invented US file: test V0 contradicts the series (the engine's method, unchanged). The run carries it; it
        decides nothing about admissibility itself."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        x.write_registry(root)
        specs, adapters = x.world_specs(x.NO_CN_HK)
        for spec in specs:
            if spec["source_id"] == x.SRC_US:
                spec["payload"] = x.av_us_csv(x._rows("AAPL", "XNAS") + [(datetime.date(2025, 1, 4), "150.00", 1000)])
        manifests = [x.kit.write_file(root, **spec) for spec in specs]
        release = MarketDataRelease.from_manifests("review", manifests, [])
        built = build_in_memory_market_data(release, FileStore(root), FileStore(root).load_registry(), adapters, x.identity(), catalog_calendars={})
        result = q.qualify(TEST_SWITCH, FileStore(root), release, adapters, x.identity(), market_conventions=market11_conventions(built.calendars),
                           perf_conventions=performance_conventions(), policy=POLICY, catalog_calendars={})
        self.assertTrue(result.needs_review)
        self.assertTrue(any("not admitted" in line for line in result.review_lines), result.review_lines)
        self.assertIn("needs review", "\n".join(result.lines()))
        rp.verify_proposal(result.proposal)                                                              # still a valid proposal: the owner reviews it


class SavingAProposalTests(WorldCase):
    def test_save_writes_a_new_file_once_and_the_file_verifies(self):
        result = run(self.world)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "proposal.json")
            q.save_proposal(path, result)
            self.assertEqual(path.read_bytes(), result.proposal)
            self.assertEqual(rp.verify_proposal(path.read_bytes()).snapshot.context_id, result.context_id)
            with self.assertRaises(FileExistsError):
                q.save_proposal(path, result)                                                              # never overwrites
            self.assertEqual(path.read_bytes(), result.proposal)
            with self.assertRaises(q.QualificationError):
                q.save_proposal(Path(tmp, "other.json"), result.proposal)

    def test_an_edited_proposal_is_refused_and_nothing_live_changes(self):
        """T01: a proposal edit changes nothing live. The edit fails verification; the publisher sends no statement; the store is untouched."""
        from persistence.real_workspace_store import RealPublisher, EXIT_REFUSED
        from test_real_publisher_tool import FakeConnection, LATER
        import real_gateway_fixtures as fx
        result = run(self.world)
        before = tree_state(self.world.root)
        document = json.loads(result.proposal)
        for label, edit in (("a member's source", lambda d: d["snapshot"]["members"][0].update(source_id="syn.other")),
                            ("the used-source digest", lambda d: d["snapshot"]["registry"].update(used_source_digest="0" * 64)),
                            ("a digest", lambda d: d["snapshot"].update(identity_digest="1" * 64)),
                            ("the scope", lambda d: d["snapshot"].update(scope="REAL"))):
            edited = json.loads(json.dumps(document))
            edit(edited)
            data = canonical_json(edited).encode("utf-8")
            with self.assertRaises(rp.ProposalError, msg=label):
                rp.verify_proposal(data)
            conn = FakeConnection()
            outcome = RealPublisher(conn, "rw_t").publish(data, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR, sources=("a",)),
                                                          actor=fx.ACTOR, ref=fx.REF)
            self.assertEqual(outcome.status, EXIT_REFUSED, label)
            self.assertEqual(conn.log, [], label)
        self.assertEqual(tree_state(self.world.root), before)


class LoaderEntryTests(WorldCase):
    def test_load_goes_through_the_r3_entry_point_and_needs_the_identitys_exchange_lookup(self):
        class Untouched:
            def __getattr__(self, name):
                raise AssertionError("the connection was touched: " + name)
        result = run(self.world)
        with self.assertRaises(TypeError):
            q.load_qualified(Untouched(), result)
        with self.assertRaises(real_loader.RealLoaderError) as caught:
            q.load_qualified(Untouched(), result, exchange_of=None)
        self.assertEqual(caught.exception.code, real_loader.LOADER_NO_IDENTITY)


class CandidateTests(WorldCase):
    """The provenance candidate of a qualified release (design 2.3 item 1, 3.3 item 1): pure, in memory; the registration itself is in the PG module."""

    def built(self, scope=TEST_SWITCH, **kw):
        result = run(self.world, scope)
        return result, cand.build_candidate(scope, FileStore(self.world.root), result, **kw)

    def test_the_candidate_holds_every_member_file_and_validates_in_memory_in_both_test_scopes(self):
        for scope in (TEST_SWITCH, SYNTHETIC):
            with self.subTest(scope.name):
                result, built = self.built(scope)
                validated = prov.validate_bundle(scope, built.bundle, expected_context_sha256=built.context_sha256, expected_members=built.members,
                                                 witnesses=built.witnesses)
                self.assertEqual(sorted(m.payload_sha256 for m in built.members), sorted(self.world.release.files))
                self.assertEqual({m.manifest_sha256 for m in built.members}, {m.manifest_sha256 for m in result.members})
                self.assertEqual({d["source_id"] for d in validated.source_records}, {m.source_id for m in self.world.manifests})
                self.assertTrue(all(d["synthetic"] is True and d["terms_check"] is None and d["terms_url"] is None for d in validated.source_records))
                self.assertEqual(built.witnesses, ())                                                    # v1 files: no envelope, no witness
                self.assertEqual(built.bundle.envelopes, ())

    def test_the_bytes_are_the_files_bytes(self):
        result, built = self.built()
        index = FileStore(self.world.root).index()
        self.assertEqual(dict(built.bundle.payloads), {m.payload_sha256: (index[m.payload_sha256].parent / next(
            x.payload_filename for x in self.world.manifests if x.file_sha256 == m.payload_sha256)).read_bytes() for m in built.members})
        self.assertEqual(dict(built.bundle.manifests), {m.manifest_sha256: index[m.payload_sha256].read_bytes() for m in built.members})
        for key, raw in list(built.bundle.payloads) + list(built.bundle.manifests):
            self.assertEqual(sha(raw), key)

    def test_unbound_and_bound_candidates_differ_only_in_the_financial_context(self):
        _result, unbound = self.built()
        _result, bound = self.built(financial_context="c" * 64)
        self.assertIsNone(json.loads(unbound.bundle.context_bytes)["financial_context_sha256"])
        self.assertEqual(json.loads(bound.bundle.context_bytes)["financial_context_sha256"], "c" * 64)
        self.assertNotEqual(unbound.context_sha256, bound.context_sha256)
        self.assertEqual(unbound.context_sha256, sha(unbound.bundle.context_bytes))
        self.assertEqual({**json.loads(unbound.bundle.context_bytes), "financial_context_sha256": "c" * 64}, json.loads(bound.bundle.context_bytes))
        self.assertEqual(unbound.bundle.payloads, bound.bundle.payloads)
        self.assertEqual(self.built()[1].context_sha256, unbound.context_sha256)                        # deterministic
        for bad in ("short", 5, "C" * 63):
            with self.assertRaises(cand.CandidateError):
                self.built(financial_context=bad)

    def test_the_operation_id_is_a_function_of_the_context_bytes(self):
        _r, a = self.built()
        _r, b = self.built(financial_context="c" * 64)
        self.assertEqual(cand.registration_operation_id(a.context_sha256), cand.registration_operation_id(a.context_sha256))
        self.assertNotEqual(cand.registration_operation_id(a.context_sha256), cand.registration_operation_id(b.context_sha256))

    def test_a_candidate_of_another_scope_than_the_qualification_is_refused(self):
        result = run(self.world, TEST_SWITCH)
        with self.assertRaises(cand.CandidateError) as caught:
            cand.build_candidate(SYNTHETIC, FileStore(self.world.root), result)
        self.assertEqual(caught.exception.code, "RW_CAND_SCOPE")

    def test_a_manifest_file_changed_after_the_qualification_is_refused(self):
        # a store of its own, so that the shared one is never touched
        world = x.build_world("mock")
        try:
            result = run(world)
            path = FileStore(world.root).index()[result.members[0].payload_sha256]
            path.write_text(path.read_text("utf-8") + " ", encoding="utf-8")
            with self.assertRaises(cand.CandidateError) as caught:
                cand.build_candidate(TEST_SWITCH, FileStore(world.root), result)
            self.assertEqual(caught.exception.code, "RW_CAND_MANIFEST")
        finally:
            world.close()

    def test_registration_needs_a_built_candidate_and_builds_nothing_by_itself(self):
        with self.assertRaises(cand.CandidateError):
            cand.register_candidate(object(), TEST_SWITCH, b"not a candidate")


class StaticTests(unittest.TestCase):
    """No R4b code calls `write_release` itself (R3 disposition, obligation 3; closes R4a review LOW-7 for the real path), and the run writes nothing."""

    @staticmethod
    def calls(path, names):
        tree = ast.parse(path.read_text("utf8"))
        return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                and ((isinstance(n.func, ast.Name) and n.func.id in names) or (isinstance(n.func, ast.Attribute) and n.func.attr in names))]

    def test_no_r4b_module_calls_write_release(self):
        paths = sorted((SRC / "real_tools").rglob("*.py")) + sorted((SRC / "persistence").glob("real_*.py"))
        self.assertTrue(any(p.name == "qualification.py" for p in paths))
        offenders = {str(p.relative_to(SRC)): self.calls(p, {"write_release"}) for p in paths if self.calls(p, {"write_release"})}
        self.assertEqual(set(offenders), {"persistence/real_loader.py"})                                  # the R3 entry point, the one place
        self.assertEqual(len(offenders["persistence/real_loader.py"]), 1)

    def test_the_run_reaches_the_projection_only_through_load_release(self):
        tree = ast.parse((SRC / "real_tools" / "qualification.py").read_text("utf8"))
        self.assertEqual(self.calls(SRC / "real_tools" / "qualification.py", {"load_release"}).__len__(), 1)
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for name in ("write_release", "_insert_release_rows", "execute", "cursor", "commit", "rollback"):
            self.assertNotIn(name, names, name)
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        self.assertNotIn("write_release", imports)

    def test_the_only_write_of_the_run_is_the_exclusive_create_of_a_proposal_file(self):
        tree = ast.parse((SRC / "real_tools" / "qualification.py").read_text("utf8"))
        opens = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
        self.assertEqual(len(opens), 1)
        self.assertEqual(opens[0].args[1].value, "xb")
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for forbidden in ("write_text", "write_bytes", "mkdir", "unlink", "rename", "replace", "environ", "getenv", "psycopg", "connect", "socket", "urlopen",
                          "now", "today", "time"):
            self.assertNotIn(forbidden, names, forbidden)

    def test_nothing_in_the_product_imports_the_tools_package(self):
        for path in sorted(SRC.rglob("*.py")):
            if "real_tools" in path.parts:
                continue
            tree = ast.parse(path.read_text("utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module == "real_tools" or node.module.startswith("real_tools."), str(path))
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(a.name == "real_tools" or a.name.startswith("real_tools.") for a in node.names), str(path))


if __name__ == "__main__":
    unittest.main()
