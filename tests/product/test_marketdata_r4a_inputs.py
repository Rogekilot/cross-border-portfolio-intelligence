"""F1 increment R4a (code part), 2026-10-25: the inputs and policy for the HG4 single-date data version `M`.

Authority: `implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.1 (row R4a) and 7.1a; `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (market-data/1.16)
section 11 items 23 and 24, Ruling 6.5 items 3 and 6, Ruling 7.3 items 9 and 10; PD-0066 decisions 2 to 4 and 10; PD-0067 decision 6.

What this file shows, and what it does not:

- the label source of an UNDECLARED `TIME_SERIES_DAILY` manifest is profile DATA and reads DECLARED (PD-0066 decision 3). A vendor's declaration is not a
  verification: the label status stays UNVERIFIABLE (items 1 to 6 of `LabelSourceTests`);
- A.6 `UW` (XNAS, segment XNGS) is OBSERVED, so the exchange-level FIGI `BBG000B9Y5X2` attaches to AAPL on XNAS, and Ruling 7.3 item 10's two level checks
  fail closed. The real OpenFIGI file is read from the data root, read only, with its payload and manifest hashes asserted (`A6AndRuling73Tests`);
- `M` holds no corporate-action file, and the F8-B confirmation policy is still validated when it is configured and cited in the manifest with its digest
  (`ConfirmationPolicyWithNoCorporateActionFileTests`). The ids tried there are the engineer's PROPOSAL; the PM decides, and no `src/` constant names them;
- the Ruling 6.5 claim-limit list carries "the dividend component is UNVERIFIABLE" as an item of its own (`ClaimLimitTests`).

It does not show: a real release or any number. (The label names market-data/1.16 from the label increment of 2026-10-25; see `ReleaseLabelIsMovedTests`.)
"""

import dataclasses
import datetime
import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import marketdata_cp2c1_kit as k  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_marketdata_cp2c1_ingest as ing  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402
from vendor_files import needs_vendor_files  # noqa: E402  (the vendor-payload gate; see vendor_files.py; the gated set is pinned in test_vendor_files_flag)

kit = k.kit

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from marketdata import claim_limits as cl  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata import precision as p  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.store import InMemoryMarketData, SeriesExclusion  # noqa: E402
from marketdata.adapters.alphavantage import COLUMNS, AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.daily_csv import translate_daily_csv  # noqa: E402
from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.adapters.openfigi import OpenFigiIdentityAdapter  # noqa: E402
from marketdata.exchange_codes import A6, ATTACHING, OBSERVED  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.manifest import FileManifest, ManifestError  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from performance_service import service as svc  # noqa: E402

ROOT = HERE.parents[1]
DATA = ROOT / "data" / "marketdata"
D = datetime.date
USD = mp.USD


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- 1. The label source ---------------------------------------------------------------------------------------------------------------------

class LabelSourceTests(ing.WorldCase):
    """market-data/1.16 section 11 item 23. The strings below are written out by hand from the item's format
    `PROFILE_CALL_ADJUSTMENT:<source>:TIME_SERIES_DAILY:<status>`; they are not taken from the code's output."""

    US = "PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED"
    CN = "PROFILE_CALL_ADJUSTMENT:alphavantage.cn:TIME_SERIES_DAILY:DECLARED"

    def test_1_both_alpha_vantage_profiles_declare_the_call_on_the_owners_reading(self):
        for source in ("alphavantage.us", "alphavantage.cn"):
            entry = prof.SOURCES[source].call_adjustment["TIME_SERIES_DAILY"]
            self.assertEqual((entry.adjustment, entry.status, entry.reference), ("RAW", "DECLARED", "PD-0066 decision 3"), source)
            self.assertEqual(set(prof.SOURCES[source].call_adjustment), {"TIME_SERIES_DAILY"})  # no other call is documented

    def test_2_the_status_is_one_of_two_and_a_declared_one_names_its_decision(self):
        self.assertEqual(prof.CALL_ADJUSTMENT_STATUSES, ("DECLARED", "MEMORY"))
        prof.CallAdjustment("RAW", "MEMORY")  # a recollection needs no decision
        for args in (("RAW", "VERIFIED", "x"), ("RAW", "OBSERVED", "x"), ("RAW", "DECLARED"), ("RAW", "DECLARED", "  "), ("", "MEMORY"), ("RAW", "")):
            with self.assertRaises(ValueError, msg=args):
                prof.CallAdjustment(*args)

    def test_3_an_undeclared_manifest_of_the_call_carries_the_declared_source_through_the_real_path_and_stays_unverifiable(self):
        built, ident = self.world([ing.av_spec(), ing.nyse_cal(), ing.ecb_cal()])
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        lk = built.store.quote_on(aapl, D(2025, 1, 8), market11_conventions(built.calendars))
        lin = lk.selected.observation.lineage
        self.assertEqual((lin.adjustment_status, lin.adjustment_label_source, lin.label_status),
                         (c.AdjustmentStatus.RAW, self.US, c.LabelStatus.UNVERIFIABLE))  # a vendor's declaration is not a verification

    def test_4_a_manifest_that_declares_its_own_label_has_no_label_source(self):
        built, ident = self.world([ing.av_spec(adjustment=c.AdjustmentStatus.RAW), ing.nyse_cal(), ing.ecb_cal()])
        lk = built.store.quote_on(kit.listing_id(ident, "AAPL", "XNAS"), D(2025, 1, 8), market11_conventions(built.calendars))
        self.assertIsNone(lk.selected.observation.lineage.adjustment_label_source)

    def test_5_the_cn_route_reads_the_same_way(self):
        payload = k.av_csv([("2025-01-02", "10.1200", "10.2000", "10.0000", "10.1200", "1000")])
        manifest = FileManifest(
            file_sha256="c" * 64, size_bytes=len(payload), payload_filename="x.csv", payload_format="alphavantage_csv_daily/1",
            source_id="synthetic.alphavantage.cn", data_kind=ing.DataKind.QUOTE, retrieval_time=k.NOW, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=k.CNY,
            source_identifiers=("609999.SHH",), request=(("function", "TIME_SERIES_DAILY"),), market="CN")
        (q,) = AlphaVantageQuoteAdapter("synthetic.alphavantage.cn", route="alphavantage.cn").translate(manifest, payload).quotes
        self.assertEqual(q.lineage.adjustment_label_source, self.CN)

    def test_6_the_status_is_read_from_the_profile_and_not_written_in_the_adapter(self):
        # the negative control: a profile whose entry is MEMORY gives MEMORY, and a profile with no entry at all falls back to MEMORY (the
        # recollection), so DECLARED appears only where a profile says so
        payload = k.av_csv([("2025-01-02", "100.0000", "101.0000", "99.0000", "100.0000", "1000")])
        manifest = FileManifest(
            file_sha256="a" * 64, size_bytes=len(payload), payload_filename="x.csv", payload_format="alphavantage_csv_daily/1",
            source_id="alphavantage.us", data_kind=ing.DataKind.QUOTE, retrieval_time=k.NOW, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=k.USD,
            source_identifiers=("AAPL",), request=(("function", "TIME_SERIES_DAILY"),), market="US")
        real = prof.SOURCES["alphavantage.us"]
        for call_adjustment, expected in (({"TIME_SERIES_DAILY": prof.CallAdjustment("RAW", "MEMORY")}, "MEMORY"), ({}, "MEMORY"),
                                          (real.call_adjustment, "DECLARED")):
            with self.subTest(expected=expected, entries=len(call_adjustment)):
                profile = dataclasses.replace(real, call_adjustment=call_adjustment)
                out = translate_daily_csv(AlphaVantageQuoteAdapter(), manifest, payload, COLUMNS, profile, "US",
                                          adjustment_override=c.AdjustmentStatus.RAW)
                (q,) = out.quotes
                self.assertEqual(q.lineage.adjustment_label_source, f"PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:{expected}")

    def test_7_only_the_documented_call_is_read_as_raw(self):
        # unchanged by the move: an UNDECLARED manifest of another function is not read through the profile, so it has no label source
        payload = k.av_csv([("2025-01-02", "100.0000", "101.0000", "99.0000", "100.0000", "1000")])
        manifest = FileManifest(
            file_sha256="a" * 64, size_bytes=len(payload), payload_filename="x.csv", payload_format="alphavantage_csv_daily/1",
            source_id="alphavantage.us", data_kind=ing.DataKind.QUOTE, retrieval_time=k.NOW, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=k.USD,
            source_identifiers=("AAPL",), request=(("function", "TIME_SERIES_DAILY_ADJUSTED"),), market="US")
        out = AlphaVantageQuoteAdapter().translate(manifest, payload)
        self.assertEqual(out.quotes, ())  # not a raw quote: its rows are verification-only
        self.assertTrue(all(q.lineage.adjustment_label_source is None for q in out.adjusted + out.reference))


# --- 2. A.6 and Ruling 7.3 -------------------------------------------------------------------------------------------------------------------

UW_PAYLOAD_SHA = "b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc"
UW_MANIFEST_SHA = "7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738"
XNGS_MANIFEST_SHA = "cb4d862d37e628b31c7a009f53d461188583e2090934de2bb080c08e21963c8d"
UW_PATH = DATA / "files" / "openfigi" / "identity" / "2026-10-23" / "AAPL_UW.json.manifest.json"
XNGS_PATH = DATA / "observations" / "openfigi" / "identity" / "2026-10-23" / "AAPL_XNGS.json"
US_PATH = DATA / "files" / "openfigi" / "identity" / "2026-10-01" / "AAPL_US.json.manifest.json"
FIGI, COMPOSITE, SHARE = "BBG000B9Y5X2", "BBG000B9XRY4", "BBG001S5N8V8"  # written out from Ruling 7.3 item 9 / PD-0066 decision 4


def real_assertion(manifest_path: Path) -> c.IdentityAssertion:
    verified = FileStore(DATA).read_verified(manifest_path)
    (assertion,) = OpenFigiIdentityAdapter().translate(verified.manifest, verified.payload).identities
    return assertion


class A6AndRuling73Tests(unittest.TestCase):
    def registry(self, *entries):
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments(list(entries) or [InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD)])
        return reg

    def aapl(self, reg):
        return reg.listing(kit.listing_id(reg, "AAPL", "XNAS"))

    def test_1_uw_is_observed_and_the_other_us_codes_stay_memory(self):
        self.assertEqual(A6.version, "market-data/1.16#a6/2")  # the version that introduced the content (section 11 item 32), not the governing set
        self.assertEqual([(e.code, e.status, e.segment_mic) for e in A6.exchange["XNAS"]],
                         [("UW", "OBSERVED", "XNGS"), ("UQ", "MEMORY", "XNMS"), ("UR", "MEMORY", "XNCM")])
        self.assertEqual({(m, e.code) for m, es in A6.exchange.items() for e in es if e.status in ATTACHING}, {("XNAS", "UW"), ("XHKG", "HK")})
        for mic, code in (("XNYS", "UN"), ("ARCX", "UP"), ("BATS", "UF"), ("XASE", "UA")):
            self.assertEqual(A6.entry_for(mic, code).status, "MEMORY", (mic, code))
        self.assertEqual(OBSERVED, "OBSERVED")

    @needs_vendor_files
    def test_2_the_files_are_the_ones_the_owner_confirmed(self):
        # PD-0066 decision 9 and 1.16 Ruling 7.3 item 9, re-hashed here: payload and the two manifests
        self.assertEqual(sha256_file(UW_PATH.with_name("AAPL_UW.json")), UW_PAYLOAD_SHA)
        self.assertEqual(sha256_file(UW_PATH), UW_MANIFEST_SHA)
        self.assertEqual(sha256_file(XNGS_PATH), UW_PAYLOAD_SHA)  # byte-identical
        self.assertEqual(sha256_file(XNGS_PATH.with_name("AAPL_XNGS.json.manifest.json")), XNGS_MANIFEST_SHA)

    @needs_vendor_files
    def test_3_the_owners_record_attaches_all_three_levels_to_aapl_on_xnas_and_to_nothing_else(self):
        reg = self.registry(InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD),
                            InstrumentEntry("Tencent Holdings", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "700", k.HKD))
        record = real_assertion(UW_PATH)
        self.assertEqual((record.figi, record.composite_figi, record.share_class_figi, record.exch_code), (FIGI, COMPOSITE, SHARE, "UW"))
        ((_, res, added),) = reg.apply_identity_assertions([record])
        self.assertEqual((res.status, added), (c.ResolutionStatus.RESOLVED, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI")))
        listing = self.aapl(reg)
        self.assertEqual((listing.figi, listing.composite_figi), (FIGI, COMPOSITE))
        instrument = next(i for i in reg.snapshot()[1] if i.instrument_id == listing.instrument_id)
        self.assertEqual(instrument.share_class_figi, SHARE)
        self.assertTrue(all("market-data/1.16#a6/2" in r.asserted_by for r in reg.identifier_rows(listing.listing_id) if r.scheme != "TICKER"))
        other = reg.listing(kit.listing_id(reg, "700", "XHKG"))
        self.assertEqual((other.figi, other.composite_figi, reg.assertion_quarantine()), (None, None, ()))  # nothing else attached
        # and the identity resolves by that exchange-level FIGI
        self.assertEqual(reg.resolve(c.ExternalIdentifiers(figi=FIGI), None).listing_id, listing.listing_id)

    @needs_vendor_files
    def test_4_the_composite_record_observed_earlier_agrees_with_it(self):
        # AAPL_US.json (2026-10-01, figi = compositeFIGI) fills composite_figi first; the exchange-level record then attaches, the levels being equal
        reg = self.registry()
        composite = real_assertion(US_PATH)
        self.assertEqual((composite.figi, composite.composite_figi, composite.share_class_figi), (COMPOSITE, COMPOSITE, SHARE))
        reg.apply_identity_assertions([composite])
        self.assertEqual((self.aapl(reg).figi, self.aapl(reg).composite_figi), (None, COMPOSITE))
        ((_, _, added),) = reg.apply_identity_assertions([real_assertion(UW_PATH)])
        self.assertEqual(added, ("FIGI", "SHARE_CLASS_FIGI"))  # the composite row is already there
        self.assertEqual((self.aapl(reg).figi, self.aapl(reg).composite_figi), (FIGI, COMPOSITE))

    @needs_vendor_files
    def test_5_a_stored_composite_that_differs_attaches_nothing(self):
        reg = self.registry()
        wrong = dataclasses.replace(real_assertion(US_PATH), figi="BBG000XXXXX9", composite_figi="BBG000XXXXX9")  # a hand-entered composite
        reg.apply_identity_assertions([wrong])
        self.assertEqual(self.aapl(reg).composite_figi, "BBG000XXXXX9")
        before = reg.identifier_rows()
        ((_, res, added),) = reg.apply_identity_assertions([real_assertion(UW_PATH)])
        self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))
        self.assertEqual(reg.assertion_quarantine()[-1].verdict, "COMPOSITE_CONFLICT")
        self.assertEqual((self.aapl(reg).figi, reg.identifier_rows()), (None, before))  # no Listing.figi and no identifier row of any level

    @needs_vendor_files
    def test_6_a_share_class_that_differs_attaches_nothing_and_adds_no_second_row(self):
        # Ruling 7.3 item 10, the share-class half (new behaviour, section 11 item 24, review C-9). Before it, the FIGI attached and a second
        # SHARE_CLASS_FIGI row was added beside the instrument's old value.
        reg = self.registry()
        reg.apply_identity_assertions([real_assertion(UW_PATH)])
        rows = reg.identifier_rows()
        other_class = dataclasses.replace(real_assertion(UW_PATH), share_class_figi="BBG001XXXXX9")
        ((_, res, added),) = reg.apply_identity_assertions([other_class])
        self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))
        (quarantined,) = reg.assertion_quarantine()
        self.assertEqual((quarantined.verdict, quarantined.assertion), ("SHARE_CLASS_CONFLICT", other_class))  # kept as unmatched evidence for a human
        self.assertIn("BBG001S5N8V8", quarantined.reason)
        self.assertEqual(reg.identifier_rows(), rows)
        (instrument,) = reg.snapshot()[1]
        self.assertEqual(instrument.share_class_figi, SHARE)

    @needs_vendor_files
    def test_7_a_share_class_with_nothing_stored_to_compare_still_attaches(self):
        # the control for test 6: the same record, no stored share class, attaches (the check compares with a stored value and invents none)
        reg = self.registry()
        ((_, _, added),) = reg.apply_identity_assertions([dataclasses.replace(real_assertion(UW_PATH), share_class_figi="BBG001XXXXX9")])
        self.assertEqual(added, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI"))

    @needs_vendor_files
    def test_8_the_memory_codes_attach_nothing_for_their_own_mic(self):
        for mic, code in (("XNAS", "UQ"), ("XNAS", "UR"), ("XNYS", "UN"), ("ARCX", "UP")):
            with self.subTest(mic=mic, code=code):
                reg = self.registry(InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, mic, "EX", "AAPL", k.USD))
                ((_, res, added),) = reg.apply_identity_assertions([dataclasses.replace(real_assertion(UW_PATH), exch_code=code)])
                self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))
                self.assertEqual(reg.assertion_quarantine()[0].verdict, "EXCHANGE_UNVERIFIABLE")
                self.assertIsNone(reg.listing(kit.listing_id(reg, "AAPL", mic)).figi)

    @needs_vendor_files
    def test_9_the_uw_record_does_not_attach_to_a_listing_of_another_mic(self):
        reg = self.registry(InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNYS", "NYSE", "AAPL", k.USD))
        ((_, _, added),) = reg.apply_identity_assertions([real_assertion(UW_PATH)])
        self.assertEqual(added, ())
        self.assertEqual(reg.assertion_quarantine()[0].verdict, "EXCHANGE_MISMATCH")  # UW is a Nasdaq code, not an NYSE one

    @needs_vendor_files
    def test_10_the_data_root_builds_and_maps_the_payload_to_the_uw_manifest_only(self):
        # section 11 item 24, fix round 2: read only, on the real data root (no file is written)
        index = FileStore(DATA).index()
        self.assertEqual(index[UW_PAYLOAD_SHA], UW_PATH)
        self.assertFalse([p for p in index.values() if "observations" in p.parts])  # nothing under observations/ is indexed
        self.assertTrue(XNGS_PATH.exists())  # the evidence is kept, outside the indexed root

    @needs_vendor_files
    def test_11_two_manifests_of_one_payload_are_still_refused_before_any_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a", "b"):
                folder = Path(tmp) / "files" / "openfigi" / "identity" / name
                folder.mkdir(parents=True)
                (folder / "AAPL_UW.json").write_bytes(UW_PATH.with_name("AAPL_UW.json").read_bytes())
                (folder / "AAPL_UW.json.manifest.json").write_bytes(UW_PATH.read_bytes())
            with self.assertRaises(ManifestError) as caught:
                FileStore(Path(tmp)).index()
            self.assertIn(UW_PAYLOAD_SHA, str(caught.exception))


# --- 3. The confirmation policy with no corporate-action file in M ------------------------------------------------------------------------------

# A PROPOSAL, not a decision (design 7.1a item 1: "R4a's plan proposes them and the PM decides"). Two candidate pairs of ids, each with its digest
# computed by hand outside this code: sha256 over the canonical JSON `{"feed":[...],"filing":[...]}` (sorted keys, no spaces, UTF-8).
PROPOSAL_A = (("alphavantage.us",), ("sec.edgar",), "6f1031f0239eefc7d5e77193276c49051a9c304a1498da1ed22f7d3e313001f3")
PROPOSAL_B = (("none.admitted.feed",), ("none.admitted.filing",), "f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1")


def policy(feed, filing):
    return f8b.ConfirmationPolicy(frozenset(feed), frozenset(filing))


class ConfirmationPolicyWithNoCorporateActionFileTests(unittest.TestCase):
    """Ruling 6.5 item 3 and Ruling 6.4d item 1: the policy must be valid when configured, whatever `M` holds."""

    def compute(self, pol):
        L = mp.base_ledger()
        port = mp.market(None, real_quotes=True)  # REAL closes, and no corporate-action record of any source
        with rc.pinned(L):
            return svc.compute_for_portfolio(None, ca.PORTFOLIO, ca.EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=pol), L, port

    def test_1_the_manifest_cites_the_policy_digest_and_both_roles_although_m_holds_no_corporate_action_record(self):
        for feed, filing, digest in (PROPOSAL_A, PROPOSAL_B):
            with self.subTest(feed=feed):
                res, L, port = self.compute(policy(feed, filing))
                self.assertEqual(svc.policy_unmatched_keys(L.rows, L.version, port, policy(feed, filing)), ())  # Ruling 6.4d case (d): no key
                self.assertEqual(dict(res.manifest.detection_policy), {"digest": digest, "feed": ",".join(feed), "filing": ",".join(filing)})
                for metric in res.metrics:
                    self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, metric.details)

    def test_2_the_digest_is_the_sha256_of_the_canonical_role_sets_computed_independently(self):
        for feed, filing, digest in (PROPOSAL_A, PROPOSAL_B):
            text = json.dumps({"feed": sorted(feed), "filing": sorted(filing)}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), digest)
            self.assertEqual(dict(svc.policy_reference(policy(feed, filing)))["digest"], digest)

    def test_3_the_digest_moves_with_every_id_and_with_the_role_it_is_in_and_not_with_the_order(self):
        base = dict(svc.policy_reference(policy(("a.feed", "b.feed"), ("a.filing",))))["digest"]
        same = dict(svc.policy_reference(policy(("b.feed", "a.feed"), ("a.filing",))))["digest"]
        self.assertEqual(base, same)
        for other in (policy(("a.feed",), ("a.filing",)), policy(("a.feed", "b.feed"), ("b.filing",)), policy(("a.feed", "b.feed", "c.feed"), ("a.filing",)),
                      policy(("a.filing",), ("a.feed", "b.feed")), policy(("a.feed", "b.feed"), ("a.filing", "c.filing"))):
            self.assertNotEqual(dict(svc.policy_reference(other))["digest"], base)

    def test_4_a_policy_that_is_not_valid_is_refused_when_it_is_configured_whatever_m_holds(self):
        # before any market data exists at all: the refusal is at construction, so an invalid policy never reaches detection or a number
        for feed, filing in ((frozenset(), frozenset({"x.filing"})), (frozenset({"x.feed"}), frozenset()), (frozenset(), frozenset()),
                             (frozenset({"x.both", "x.feed"}), frozenset({"x.both"}))):
            with self.assertRaises(ValueError, msg=(feed, filing)):
                f8b.ConfirmationPolicy(feed, filing)

    def test_5_the_proposed_ids_are_valid_and_overlap_nowhere(self):
        for feed, filing, _ in (PROPOSAL_A, PROPOSAL_B):
            pol = policy(feed, filing)
            self.assertTrue(pol.feed_sources and pol.filing_sources and not (pol.feed_sources & pol.filing_sources))

    def test_7_a_corroborated_split_dated_before_any_holding_and_outside_the_calendar_changes_nothing(self):
        # section 11 item 22 (Ruling 6.5 item 4; Example 6-E row (iv)): the feed and the filing agree on (4, 1) at 2020-08-31; the ledger starts on
        # 2024-12-20 and the test calendar covers 2024-06-03 to 2026-06-30. No account holds units at the start of that ex-date, so no window is
        # evaluated and the calendar is not needed: every metric of the valuation equals the one computed with no corporate-action record.
        old = D(2020, 8, 31)
        self.assertLess(old, D(2024, 6, 3))
        evidence = [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), day=old, listing=mp.LISTING),
                    ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), day=old, listing=mp.LISTING)]
        pol = policy((ca.FEED,), (ca.FILING,))

        def values(extra):
            L = mp.base_ledger()
            port = mp.market(None, real_quotes=True, extra=extra)
            with rc.pinned(L):
                res = svc.compute_for_portfolio(None, ca.PORTFOLIO, ca.EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=pol)
            return [(m.metric_id, m.view, m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value,
                     str(m.result.value)) for m in res.metrics]

        without, with_split = values([]), values(evidence)
        self.assertEqual(with_split, without)
        # NON-VACUITY (the Quant's note, answer (c)): "with equals without" also passes if the 2020 records never reach detection. They do: the key
        # (listing, 2020-08-31) is CORROBORATED under this policy, and it is UNMATCHED under a policy that omits the filing source.
        port = mp.market(None, real_quotes=True, extra=evidence)
        readings = port.corporate_actions(mp.LISTING, datetime.date.min, datetime.date.max).readings
        (finding,) = f8b.corroborate(mp.LISTING, readings, pol)
        self.assertEqual((finding.ex_date, finding.status), (old, f8b.Corroboration.CORROBORATED))
        L = mp.base_ledger()
        self.assertEqual(svc.policy_unmatched_keys(L.rows, L.version, port, pol), ())
        without_filing = policy((ca.FEED,), ("other.filing",))
        (key,) = svc.policy_unmatched_keys(L.rows, L.version, port, without_filing)
        self.assertEqual((key.listing, key.ex_date, key.unclassified_sources), (mp.LISTING, old, (ca.FILING,)))
        self.assertEqual([row for row in without if row[0] == "portfolio_value" and row[1] == "REPORTING"],
                         [("portfolio_value", "REPORTING", "AVAILABLE", None, "4375.00")])  # 50 x 37.50 + 2500.00, by hand from the kit's close and ledger
        self.assertTrue(all(row[2] == "AVAILABLE" and row[3] is None for row in with_split))

    def test_6_a_record_from_a_source_the_policy_does_not_name_is_refused_even_though_the_policy_is_valid(self):
        # the control for test 1: with a corporate-action record in M from a source in neither role, the policy test fires (Ruling 6.4d). It is the
        # reason the policy is carried at all if a split file is ever added to M (OP-3, deferred).
        L = mp.base_ledger()
        port = mp.market(None, real_quotes=True, extra=[ca.split_reading("stray.feed", "d" * 64, (2, 1), day=D(2023, 6, 1), listing=mp.LISTING)])
        keys = svc.policy_unmatched_keys(L.rows, L.version, port, policy(*PROPOSAL_A[:2]))
        self.assertEqual([(str(k_.listing), k_.ex_date, k_.unclassified_sources) for k_ in keys], [(str(mp.LISTING), D(2023, 6, 1), ("stray.feed",))])


# --- 4. The Ruling 6.5 claim limits ----------------------------------------------------------------------------------------------------------

class ClaimLimitTests(unittest.TestCase):
    """Ruling 6.5 item 6 (1.16): one numbered list, so that a shortened rendering can be checked item by item. The ids are written out from the
    Quant's list (C-1 to C-6 may claim; N-1 to N-9 may not)."""

    def test_1_the_list_is_the_quants_fifteen_items_in_order(self):
        self.assertEqual(cl.CLAIM_LIMIT_IDS, tuple(f"C-{i}" for i in range(1, 7)) + tuple(f"N-{i}" for i in range(1, 10)))
        self.assertEqual([i.kind for i in cl.CLAIM_LIMITS], [cl.MAY_CLAIM] * 6 + [cl.MAY_NOT_CLAIM] * 9)
        self.assertEqual(len(set(cl.CLAIM_LIMIT_IDS)), 15)

    def test_2_the_dividend_component_is_an_item_of_its_own_and_says_unverifiable(self):
        item = cl.claim_limit(cl.DIVIDEND_COMPONENT_LIMIT_ID)
        self.assertEqual((item.limit_id, item.kind), ("N-2", cl.MAY_NOT_CLAIM))
        self.assertIn("dividend component", item.statement)
        self.assertIn("UNVERIFIABLE", item.statement)
        self.assertEqual(item.required_terms, ("dividend component", "UNVERIFIABLE"))
        # not folded into the split item or the verified-as-traded item (PD-0066 decision 2; the F1 final check F-2)
        for other in ("N-1", "N-3"):
            self.assertNotIn("dividend", cl.claim_limit(other).statement)

    def test_3_a_rendering_that_drops_any_item_is_incomplete_and_the_check_can_fail(self):
        self.assertEqual(cl.missing_claim_limits(cl.CLAIM_LIMIT_IDS), frozenset())
        for dropped in cl.CLAIM_LIMIT_IDS:
            with self.subTest(dropped=dropped):
                self.assertEqual(cl.missing_claim_limits(i for i in cl.CLAIM_LIMIT_IDS if i != dropped), frozenset({dropped}))
        self.assertEqual(cl.unknown_claim_limits(cl.CLAIM_LIMIT_IDS + ("N-10",)), frozenset({"N-10"}))

    def test_4_the_label_source_is_a_slot_never_a_constant_here(self):
        # a stored result that cites market-data/1.15 or earlier says MEMORY, so the text may not hard-code either word
        for item in cl.CLAIM_LIMITS:
            self.assertNotIn("DECLARED", item.statement, item.limit_id)
            self.assertNotIn("MEMORY", item.statement, item.limit_id)
        self.assertIn("{label_source}", cl.claim_limit("C-1").statement)
        self.assertIn("{label_source}", cl.claim_limit("C-6").statement)

    def test_5_the_statements_name_no_vendor_and_no_place_only_slots(self):
        for item in cl.CLAIM_LIMITS:
            text = item.statement.lower()
            for word in ("alpha vantage", "alphavantage", "nasdaq", "xnas", "aapl", "openfigi", "2026"):
                self.assertNotIn(word, text, (item.limit_id, word))

    def test_6_the_c1_statement_carries_the_caveat_that_a_declaration_is_not_a_verification(self):
        c1 = cl.claim_limit("C-1")
        self.assertIn("not a verification", c1.statement)
        self.assertIn("not a verification", c1.required_terms)

    def test_7_a_slot_the_statement_uses_but_does_not_declare_is_refused(self):
        with self.assertRaises(ValueError):
            cl.ClaimLimit("X-1", cl.MAY_CLAIM, "The value is {oops}.", ())
        with self.assertRaises(ValueError):
            cl.ClaimLimit("X-2", cl.MAY_CLAIM, "No slot here.", ("unused",))


# --- 4a. The 1.16 gate items built here (25, 26, 28, 34; 27 is in test_marketdata_listing_market_gate) ----------------------------------------

def _cell(day, close, volume="120000"):
    return (day, "49.6000", "50.9000", "49.5000", close, volume)


class DuplicateSessionDateTests(ing.WorldCase):
    """market-data/1.16 section 11 item 25, Test V0 for a session date written twice, in every market. Example 3-E (a) and (a'), moved into the January 2025 world of
    the ingest tests (the structure is the example's: three sessions, one of them written twice, a clean control). The expected outcomes are the example's."""

    SIX, SEVEN, EIGHT = "2025-01-06", "2025-01-07", "2025-01-08"
    CLEAN = [_cell(SIX, "49.7000"), _cell(SEVEN, "50.0000"), _cell(EIGHT, "50.5000")]
    # (a): the 7th written twice, in two spellings, with identical values; the file order is the example's (the 7th, then 20250107)
    TWICE = [_cell(SIX, "49.7000"), _cell(SEVEN, "50.0000"), _cell("20250107", "50.0000"), _cell(EIGHT, "50.5000")]

    def lookup(self, rows, day=D(2025, 1, 8)):
        built, ident = self.world([ing.av_spec(rows=rows), ing.nyse_cal(), ing.ecb_cal()])
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        return built, aapl, built.store.quote_on(aapl, day, market11_conventions(built.calendars))

    def assert_contradicted(self, built, aapl, lk, dates_text):
        st = ing.price_input_state(lk)
        self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                         (ing.LookupOutcome.NO_HISTORY, None, ing.S.INSUFFICIENT_DATA, ing.R.MISSING_PRICE_HISTORY))
        (note,) = lk.lineage_notes  # the cause is the series' own failure, and it is the only cause listed
        self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
        self.assertIn("DUPLICATE_SESSION_DATE", note)
        self.assertIn(dates_text, note)
        # the file STAYS in M: it is a file of the release, its summary and its issue are kept, and the exclusion names it
        (exclusion,) = [e for e in built.store.export().exclusions if e.listing_id == aapl]
        self.assertEqual((exclusion.test, exclusion.currency), ("V0", None))
        self.assertIn(exclusion.file_sha256, {m.file_sha256 for m in built.manifests})
        self.assertIn(exclusion.file_sha256, {s.file_sha256 for s in built.summaries})
        self.assertIn((exclusion.file_sha256, ing.IssueCode.DUPLICATE_SESSION_DATE), [(sha, i.code) for sha, i in built.issues])
        self.assertEqual([(r.test, r.status, r.admitted) for r in built.label_results if r.test == "V0"], [("V0", c.LabelStatus.CONTRADICTED, False)])
        self.assertEqual(built.store.quotes(aapl, D(2025, 1, 1), D(2025, 1, 31)).readings, ())  # no reading of the series at all

    def test_1_the_control_without_the_second_spelling_is_a_current_available_close(self):
        built, aapl, lk = self.lookup(self.CLEAN)
        st = ing.price_input_state(lk)
        self.assertEqual((lk.outcome, lk.selected.observation.price, st.state, st.reason), (ing.LookupOutcome.FOUND, Decimal("50.5"), ing.S.AVAILABLE, None))
        self.assertEqual(Decimal(100) * lk.selected.observation.price, Decimal("5050.00"))  # Example 3-E (c): 100 units
        self.assertEqual([e for e in built.store.export().exclusions if e.listing_id == aapl], [])

    def test_2_example_3_e_a_one_session_in_two_spellings_with_identical_values_contradicts_the_series(self):
        built, aapl, lk = self.lookup(self.TWICE)
        self.assert_contradicted(built, aapl, lk, "2025-01-07")
        # the whole series is out, not only the repeated date: the 6th is no longer served either
        other = built.store.quote_on(aapl, D(2025, 1, 6), market11_conventions(built.calendars))
        self.assertEqual((other.outcome, other.selected), (ing.LookupOutcome.NO_HISTORY, None))

    def test_3_example_3_e_a_prime_a_different_close_in_the_second_row_gives_the_same_result(self):
        different = [_cell(self.SIX, "49.7000"), _cell(self.SEVEN, "50.0000"), ("20250107", "49.6000", "50.2500", "49.5000", "50.2500", "110000"),
                     _cell(self.EIGHT, "50.5000")]
        built, aapl, lk = self.lookup(different)
        self.assert_contradicted(built, aapl, lk, "2025-01-07")

    def test_4_the_key_is_the_parsed_date_so_the_same_spelling_twice_counts_as_well(self):
        built, aapl, lk = self.lookup([_cell(self.SIX, "49.7000"), _cell(self.SEVEN, "50.0000"), _cell(self.SEVEN, "50.0000"), _cell(self.EIGHT, "50.5000")])
        self.assert_contradicted(built, aapl, lk, "2025-01-07")

    def test_5_a_repeated_date_outside_every_calendar_still_contradicts_it(self):
        # 2024-12-30 is not in the NYSE sessions file's coverage: V0 against the calendar could not judge it, but the file's own dating is contradictory
        rows = [_cell("2024-12-30", "49.0000"), _cell("2024-12-30", "49.0000")] + self.CLEAN
        built, aapl, lk = self.lookup(rows)
        self.assert_contradicted(built, aapl, lk, "2024-12-30")

    def test_6_the_lineage_names_every_repeated_date(self):
        rows = [_cell(self.SIX, "49.7000"), _cell(self.SIX, "49.7000"), _cell(self.SEVEN, "50.0000"), _cell(self.SEVEN, "50.0000"), _cell(self.EIGHT, "50.5000")]
        built, aapl, lk = self.lookup(rows)
        self.assert_contradicted(built, aapl, lk, "2025-01-06, 2025-01-07")


class DeliveredDecimalsTests(ing.WorldCase):
    """market-data/1.16 section 11 item 26, A.4 item 7 on every route. Example 3-E (b) and (c) (a close written `50.50000` against `delivered_dp 4`, and `50.5000`)."""

    def lookup(self, close):
        rows = [_cell("2025-01-06", "49.7000"), _cell("2025-01-07", "50.0000"), _cell("2025-01-08", close)]
        built, ident = self.world([ing.av_spec(rows=rows), ing.nyse_cal(), ing.ecb_cal()])
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        return built, aapl, built.store.quote_on(aapl, D(2025, 1, 8), market11_conventions(built.calendars))

    def test_1_example_3_e_b_a_close_that_shows_five_decimals_fails_the_profile_check_and_the_file_is_not_admitted(self):
        built, aapl, lk = self.lookup("50.50000")
        failed = [i for _, i in built.issues if i.code is ing.IssueCode.PROFILE_CHECK_FAILED]
        self.assertEqual(len(failed), 1)
        self.assertIn("50.50000 shows 5 decimals but the profile delivers 4", failed[0].detail)
        self.assertEqual(built.store.quotes(aapl, D(2025, 1, 1), D(2025, 1, 31)).readings, ())  # no reading; the text is not repaired to 50.5000
        st = ing.price_input_state(lk)
        self.assertEqual((st.state, st.reason, lk.selected), (ing.S.INSUFFICIENT_DATA, ing.R.MISSING_PRICE_HISTORY, None))

    def test_2_example_3_e_c_the_same_close_written_with_four_decimals_or_fewer_is_admitted(self):
        for close in ("50.5000", "50.5", "50.50"):
            with self.subTest(close=close):
                built, aapl, lk = self.lookup(close)
                st = ing.price_input_state(lk)
                self.assertEqual((lk.outcome, lk.selected.observation.price, st.state, st.reason),
                                 (ing.LookupOutcome.FOUND, Decimal("50.5"), ing.S.AVAILABLE, None), close)
                self.assertEqual([i for _, i in built.issues if i.code is ing.IssueCode.PROFILE_CHECK_FAILED], [])

    def test_3_the_count_is_of_the_text_not_of_the_value(self):
        # 50.5 has one decimal as a value and shows five as text; it is the text that is counted (the grid check counts the value's)
        field = prof.FieldProfile(prof.NumberFormat.TEXT_DECIMAL, prof.OBSERVED, delivered_dp=4)
        self.assertIsNone(p.check_field_format(["50.5000", "50.5", "50"], field))
        self.assertIn("shows 5 decimals", p.check_field_format(["50.50000"], field))
        self.assertIn("shows 5 decimals", p.check_field_format(["50.5000", "50.50000"], field))  # one bad text fails the file

    def test_4_it_applies_to_a_float64_field_and_not_to_an_integral_or_a_float32_one(self):
        f64 = prof.FieldProfile(prof.NumberFormat.FLOAT64, prof.OBSERVED, delivered_dp=2)
        self.assertIn("shows 3 decimals", p.check_field_format(["10.255"], f64))
        self.assertIsNone(p.check_field_format(["10.25"], f64))
        integral = prof.FieldProfile(prof.NumberFormat.TEXT_DECIMAL, prof.OBSERVED, integral=True, delivered_dp=0)
        self.assertIsNone(p.check_field_format(["120000", "120000.00"], integral))  # an integral field is exempt
        f32 = prof.FieldProfile(prof.NumberFormat.FLOAT32, prof.OBSERVED, delivered_dp=2)
        self.assertIsNone(p.check_field_format(["474.20001"], f32))  # the float32 rendering's decimals are not the source's (HK Sina files)

    @needs_vendor_files
    def test_5_the_stored_aapl_file_passes_every_price_text_shows_exactly_four_decimals(self):
        folder = DATA / "files" / "alphavantage.us" / "quote" / "2026-10-01"
        payload = (folder / "AAPL_compact.csv").read_bytes()
        manifest = FileManifest.from_json((folder / "AAPL_compact.csv.manifest.json").read_text(encoding="utf-8"))
        lines = payload.decode("utf-8").strip().splitlines()[1:]
        texts = [cell for line in lines for cell in line.split(",")[1:5]]
        self.assertEqual((len(lines), len(texts), {len(t.split(".")[1]) for t in texts}), (100, 400, {4}))  # counted from the bytes, not through src/
        out = AlphaVantageQuoteAdapter().translate(manifest, payload)
        self.assertEqual(len(out.quotes), 100)
        self.assertEqual([i for i in out.issues if i.code in (ing.IssueCode.PROFILE_CHECK_FAILED, ing.IssueCode.DUPLICATE_SESSION_DATE)], [])


class NoAdmittedSourceExclusivityTests(unittest.TestCase):
    """market-data/1.16 section 11 item 28, Ruling 4.7 item 1: `NO_ADMITTED_SOURCE` is the cause only when M holds no series of the listing at all. The
    synthetic-world case of Example 7A-G2 (c) through the real path is `test_marketdata_alphavantage_cn.World.test_g2_c_...`; here the store is built by hand."""

    CN = uuid.UUID(int=0xC1)
    OTHER = uuid.UUID(int=0xC2)

    def store(self, *exclusions):
        return InMemoryMarketData(k.RELEASE, [], exchange_of=lambda _l: "XSHG", exclusions=list(exclusions))

    def lookup(self, store, listing):
        return store.quote_on(listing, D(2026, 9, 30), market11_conventions(CalendarSet([])))

    def test_1_a_listing_with_no_series_keeps_no_admitted_source(self):
        lk = self.lookup(self.store(), self.CN)
        self.assertEqual(lk.outcome, ing.LookupOutcome.NO_HISTORY)
        self.assertEqual(len(lk.lineage_notes), 1)
        self.assertTrue(lk.lineage_notes[0].startswith("NO_ADMITTED_SOURCE: market CN"), lk.lineage_notes)
        self.assertEqual(lk.freshness.state, c.FreshnessState.UNKNOWN)

    def test_2_an_excluded_series_is_the_cause_and_no_admitted_source_is_not_added(self):
        lk = self.lookup(self.store(SeriesExclusion(self.CN, "a" * 64, "V0", "DUPLICATE_SESSION_DATE: two rows for one session date: 2026-09-25")), self.CN)
        self.assertEqual(lk.outcome, ing.LookupOutcome.NO_HISTORY)
        (note,) = lk.lineage_notes
        self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file aaaaaaaaaaaa: "), note)
        self.assertEqual(lk.freshness.state, c.FreshnessState.UNKNOWN)  # the market still has no admitted source, so nothing was ever printed for it

    def test_3_the_exclusion_of_one_listing_does_not_change_the_cause_of_another(self):
        lk = self.lookup(self.store(SeriesExclusion(self.CN, "a" * 64, "V0", "x")), self.OTHER)
        (note,) = lk.lineage_notes
        self.assertTrue(note.startswith("NO_ADMITTED_SOURCE"), note)

    def test_4_two_excluded_series_are_two_causes_and_still_no_third(self):
        lk = self.lookup(self.store(SeriesExclusion(self.CN, "a" * 64, "V0", "x"), SeriesExclusion(self.CN, "b" * 64, "V0", "y")), self.CN)
        self.assertEqual([n.split(":")[0] for n in lk.lineage_notes], ["SERIES_CONTRADICTED", "SERIES_CONTRADICTED"])


class FixingDateStatedTwiceTests(ing.WorldCase):
    """market-data/1.16 section 11 item 34, Test V0-FX. A fixing date stated twice in an ECB file excludes EVERY currency series read from that file, whole, whatever the
    values and wherever the date lies; the old rule (the first row wins) is gone. The synthetic file is the ingest tests' ECB file with 2025-01-02 stated again."""

    DUP_USD = ("2025-01-02", ["9.9900", "8.4000", "7.8000"])  # the same fixing again, with another USD value than 1.0800
    DUP_EQUAL = ("2025-01-02", ["1.0800", "8.4000", "7.8000"])  # the same fixing again, row for row equal

    def lookups(self, extra_rows, specs_extra=(), **spec_kw):
        built, ident = self.world([ing.ecb_spec(rows=ing.ECB_ROWS + list(extra_rows), **spec_kw), *specs_extra])
        return built, market11_conventions(built.calendars)

    def assert_every_currency_excluded(self, built, conv):
        for quote in (k.USD, k.HKD, k.CNY):
            lk = built.store.fx_on(k.EUR, quote, D(2025, 1, 8), conv)
            self.assertEqual((lk.outcome, lk.rate, lk.legs), (ing.LookupOutcome.NOT_IN_RELEASE, None, ()), quote.code)
            self.assertEqual(ing.fx_input_state(lk).reason, ing.R.MISSING_FX_HISTORY, quote.code)
            self.assertTrue(any(n.startswith("V0_FX_DUPLICATE_DATE: the " + quote.code + " series of file ") for n in lk.lineage_notes), (quote.code, lk.lineage_notes))
            self.assertEqual(built.store.fx_series(k.EUR, quote, D(2025, 1, 1), D(2025, 1, 31)).readings, ())
        self.assertEqual(sorted(e.currency for e in built.store.export().exclusions if e.listing_id is None), ["CNY", "HKD", "USD"])
        self.assertEqual({(r.test, r.status, r.admitted) for r in built.label_results if r.test.startswith("V0_FX")},
                         {("V0_FX_DUPLICATE_DATE", c.LabelStatus.CONTRADICTED, False)})
        (file_sha,) = {e.file_sha256 for e in built.store.export().exclusions}
        self.assertIn(file_sha, {s.file_sha256 for s in built.summaries})  # the file stays in M
        self.assertIn(file_sha, {m.file_sha256 for m in built.manifests})

    def test_1_control_a_file_with_one_row_per_date_is_served(self):
        built, conv = self.lookups([], specs_extra=[ing.ecb_cal()])
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 8), conv)
        self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.FOUND, Fraction(10823, 10000)))
        self.assertEqual(built.store.export().exclusions, ())

    def test_2_usd_1_08_then_9_99_on_one_date_excludes_usd_and_every_other_currency_of_the_file(self):
        built, conv = self.lookups([self.DUP_USD])
        self.assert_every_currency_excluded(built, conv)

    def test_3_equal_rows_count_as_well(self):
        built, conv = self.lookups([self.DUP_EQUAL])
        self.assert_every_currency_excluded(built, conv)

    def test_4_a_row_where_a_currency_is_not_available_counts_as_a_statement_of_the_date(self):
        built, conv = self.lookups([("2025-01-02", ["N/A", "8.4000", "7.8000"])])
        self.assert_every_currency_excluded(built, conv)

    def test_5_the_exclusion_holds_with_the_fixing_calendar_registered_and_with_none(self):
        with_calendar, conv = self.lookups([self.DUP_USD], specs_extra=[ing.ecb_cal()])
        self.assert_every_currency_excluded(with_calendar, conv)
        # outside the calendar's coverage (2025-01-01..31): the date is not a calendar question, it is a defect of the file's dating
        outside, conv = self.lookups([("2024-12-30", ["1.0700", "8.3000", "7.7000"]), ("2024-12-30", ["1.0700", "8.3000", "7.7000"])],
                                     specs_extra=[ing.ecb_cal()])
        self.assert_every_currency_excluded(outside, conv)

    def test_6_a_repeated_date_outside_the_read_window_still_excludes_the_file(self):
        built, conv = self.lookups([self.DUP_USD], request=(("read_start", "2025-01-06"), ("read_end", "2025-01-08")))
        self.assert_every_currency_excluded(built, conv)

    # --- the Frankfurter route (the Quant's finding F-2): the rule is not limited to the ECB's own format ---------------------------------------------

    def frank(self, body):
        text = '{"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-01-03","rates":{' + body + "}}"
        return dict(source_id="frankfurter.ecb", kind=ing.DataKind.FX, payload_format="frankfurter_json_timeseries/1", payload=text.encode("utf-8"),
                    label="frank", ext="json", source_identifiers=("CNY", "USD"), request=(("start", "2025-01-02"), ("end", "2025-01-03")))

    def frank_world(self, body):
        built, _ident = self.world([self.frank(body), ing.ecb_cal()])
        return built, market11_conventions(built.calendars)

    def assert_frankfurter_excluded(self, built, conv):
        for quote in (k.USD, k.CNY):
            for day in (D(2025, 1, 2), D(2025, 1, 3)):  # the WHOLE series: the other date of the file is not served either
                lk = built.store.fx_on(k.EUR, quote, day, conv)
                self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.NOT_IN_RELEASE, None), (quote.code, day))
            self.assertTrue(any(n.startswith("V0_FX_DUPLICATE_DATE: the " + quote.code + " series of file ") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(sorted(e.currency for e in built.store.export().exclusions if e.listing_id is None), ["CNY", "USD"])
        (sha,) = {e.file_sha256 for e in built.store.export().exclusions}
        self.assertIn(sha, {s.file_sha256 for s in built.summaries})  # the file stays in M

    CONTROL = '"2025-01-02":{"CNY":7.8000,"USD":1.0800},"2025-01-03":{"CNY":7.8100,"USD":1.0810}'

    def test_7a_control_a_frankfurter_file_with_one_key_per_date_is_served(self):
        built, conv = self.frank_world(self.CONTROL)
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), conv)
        self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.FOUND, Fraction(10810, 10000)))
        self.assertEqual(built.store.export().exclusions, ())

    def test_7b_probe_i_one_date_key_twice_with_two_values_excludes_every_currency_series(self):
        # json.loads would keep the LAST value (9.99) and serve it: one of two statements chosen by the parser's order
        built, conv = self.frank_world('"2025-01-02":{"CNY":7.8000,"USD":1.0800},"2025-01-02":{"CNY":7.8000,"USD":9.9900},'
                                       '"2025-01-03":{"CNY":7.8100,"USD":1.0810}')
        self.assert_frankfurter_excluded(built, conv)

    def test_7c_probe_ii_one_date_in_two_spellings_excludes_them_too(self):
        built, conv = self.frank_world('"2025-01-02":{"CNY":7.8000,"USD":1.0800},"20250102":{"CNY":7.8000,"USD":9.9900},'
                                       '"2025-01-03":{"CNY":7.8100,"USD":1.0810}')
        self.assert_frankfurter_excluded(built, conv)

    def test_7d_equal_values_count_as_well(self):
        for second in ('"2025-01-02"', '"20250102"'):
            built, conv = self.frank_world('"2025-01-02":{"CNY":7.8000,"USD":1.0800},' + second + ':{"CNY":7.8000,"USD":1.0800},'
                                           '"2025-01-03":{"CNY":7.8100,"USD":1.0810}')
            self.assert_frankfurter_excluded(built, conv)

    @needs_vendor_files
    def test_7e_the_two_stored_frankfurter_files_state_no_date_twice_so_nothing_on_disk_is_excluded(self):
        from marketdata.adapters.frankfurter import FrankfurterFxAdapter  # noqa: PLC0415

        for folder, name, names, distinct in (("2026-10-01", "EUR_2025-01-02_2025-01-08.json", 5, 5), ("2026-10-02", "EUR_2026-05-08_2026-09-30.json", 104, 104)):
            base = DATA / "files" / "frankfurter.ecb" / "fx" / folder
            payload = (base / name).read_bytes()
            seen = []
            json.loads(payload, object_pairs_hook=lambda pairs: seen.append([n for n, _ in pairs]) or dict(pairs))
            date_names = max(seen, key=len)  # the `rates` object holds the most names
            self.assertEqual((len(date_names), len({datetime.date.fromisoformat(n) for n in date_names})), (names, distinct), name)
            manifest = FileManifest.from_json((base / (name + ".manifest.json")).read_text(encoding="utf-8"))
            out = FrankfurterFxAdapter().translate(manifest, payload)
            self.assertEqual((out.contradicted, len(out.fx) > 0), ((), True), name)

    def test_7_only_the_files_own_series_are_excluded(self):
        # a second, clean ECB-format file from a Frankfurter-style second source is not touched by the first file's defect
        built, ident = self.world([ing.ecb_spec(rows=ing.ECB_ROWS + [self.DUP_USD], label="ecb"), ing.ecb_cal(),
                                   ing.frank_spec({"2025-01-02": {"USD": "1.0800"}, "2025-01-03": {"USD": "1.0810"}}, start="2025-01-02", end="2025-01-03")])
        conv = market11_conventions(built.calendars)
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), conv)
        self.assertEqual((lk.outcome, lk.rate, [leg.source_id for leg in lk.legs]), (ing.LookupOutcome.FOUND, Fraction(10810, 10000), ["frankfurter.ecb"]))
        self.assertEqual(sorted((e.currency, e.test) for e in built.store.export().exclusions if e.listing_id is None),
                         [("CNY", "V0_FX_DUPLICATE_DATE"), ("HKD", "V0_FX_DUPLICATE_DATE"), ("USD", "V0_FX_DUPLICATE_DATE")])


# --- 4b. The review fix round (2026-10-25): HIGH-1, MEDIUM-2/3, LOW-4/5 and the repeated header column -----------------------------------------

class UnreadableDateRowTests(ing.WorldCase):
    """Addendum A.2 (the Quant's ruling on MEDIUM-2). A row whose date is blank or cannot be read STATES NOTHING: it is refused alone (`UNPARSEABLE_ROW`) and takes
    no part in the duplicate count, whether there is one, two with the same label or two with different labels. The series' other rows are judged as if the row
    were absent. A row whose date PARSES but whose other fields are bad does state that session and counts (case (iv))."""

    SIX, SEVEN, EIGHT = "2025-01-06", "2025-01-07", "2025-01-08"
    CLEAN = [_cell(SIX, "49.7000"), _cell(SEVEN, "50.0000"), _cell(EIGHT, "50.5000")]

    def lookup(self, rows):
        built, ident = self.world([ing.av_spec(rows=rows), ing.nyse_cal(), ing.ecb_cal()])
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        return built, aapl, built.store.quote_on(aapl, D(2025, 1, 8), market11_conventions(built.calendars))

    def assert_served(self, rows, unparseable):
        built, aapl, lk = self.lookup(rows)
        st = ing.price_input_state(lk)
        # the Quant's hand check on Example 3-E (c): 100 x 50.50 = 5,050.00, CURRENT, AVAILABLE
        self.assertEqual((lk.outcome, lk.selected.observation.price, st.state, st.reason), (ing.LookupOutcome.FOUND, Decimal("50.5"), ing.S.AVAILABLE, None))
        self.assertEqual(Decimal(100) * lk.selected.observation.price, Decimal("5050.00"))
        self.assertEqual([e for e in built.store.export().exclusions if e.listing_id == aapl], [])  # no silent removal of the series
        self.assertEqual(len(built.store.quotes(aapl, D(2025, 1, 1), D(2025, 1, 31)).readings), 3)
        self.assertEqual(sum(1 for _s, i in built.issues if i.code is ing.IssueCode.UNPARSEABLE_ROW), unparseable)
        self.assertEqual([i for _s, i in built.issues if i.code is ing.IssueCode.DUPLICATE_SESSION_DATE], [])

    def test_1_one_blank_date_row_is_refused_alone(self):
        self.assert_served(self.CLEAN + [_cell("", "50.0000")], 1)

    def test_2_two_rows_with_the_same_blank_label_are_two_refusals_and_not_a_duplicate(self):
        self.assert_served(self.CLEAN + [_cell("", "50.0000"), _cell("", "50.0000")], 2)

    def test_3_two_rows_with_the_same_unparseable_label_likewise(self):
        self.assert_served(self.CLEAN + [_cell("2025-13-01", "50.0000"), _cell("2025-13-01", "50.0000")], 2)

    def test_4_two_rows_with_different_unparseable_labels_likewise(self):
        self.assert_served(self.CLEAN + [_cell("2025-13-01", "50.0000"), _cell("not a date", "50.0000")], 2)

    def test_5_a_label_that_is_not_a_date_never_joins_the_key_of_a_real_date(self):
        # `2025-01-07x` is not 2025-01-07: the clean 7th is stated once
        self.assert_served(self.CLEAN + [_cell("2025-01-07x", "50.0000")], 1)

    def test_6_case_iv_a_row_whose_date_parses_but_whose_other_field_is_bad_still_counts(self):
        # the low (51.5) is above the open and the close: refused as ROW_INCONSISTENT, yet it states the 7th, so the 7th is stated twice
        bad = (self.SEVEN, "49.6000", "50.9000", "51.5000", "50.0000", "110000")
        built, aapl, lk = self.lookup(self.CLEAN + [bad])
        DuplicateSessionDateTests.assert_contradicted(self, built, aapl, lk, "2025-01-07")
        self.assertIn(ing.IssueCode.ROW_INCONSISTENT, [i.code for _s, i in built.issues])  # the row is refused for its own bad field as well


class HeaderNamesAColumnTwiceTests(ing.WorldCase):
    """Addendum A.3 (observation) and A.1: `csv.DictReader` keeps the LAST of two same-named columns, so a header with `close` twice would serve one of two
    statements of every close by position. Every row states that field twice, so every series of the file is contradicted (Test V0): no reading, the file in M."""

    ROWS = [("2025-01-06", "49.6000", "50.9000", "49.5000", "49.7000", "120000"), ("2025-01-07", "49.6000", "50.9000", "49.5000", "50.0000", "120000"),
            ("2025-01-08", "49.6000", "50.9000", "49.5000", "50.5000", "120000")]
    HEADER = ["timestamp", "open", "high", "low", "close", "volume"]

    def payload(self, repeat, extra_value="99.0000"):
        """The header with column `repeat` named twice (the second copy at the end), every row with a second value for it."""
        at = self.HEADER.index(repeat) if repeat in self.HEADER else None
        lines = [",".join(self.HEADER + [repeat])]
        for row in self.ROWS:
            lines.append(",".join(list(row) + [row[at] if at is not None else extra_value]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def lookup(self, payload):
        built, ident = self.world([ing.av_spec(payload=payload), ing.nyse_cal(), ing.ecb_cal()])
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        return built, aapl, built.store.quote_on(aapl, D(2025, 1, 8), market11_conventions(built.calendars))

    def test_1_every_read_column_repeated_contradicts_the_series(self):
        for column in self.HEADER:
            with self.subTest(column=column):
                built, aapl, lk = self.lookup(self.payload(column))
                st = ing.price_input_state(lk)
                self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                                 (ing.LookupOutcome.NO_HISTORY, None, ing.S.INSUFFICIENT_DATA, ing.R.MISSING_PRICE_HISTORY), column)
                (note,) = lk.lineage_notes
                self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
                (exclusion,) = [e for e in built.store.export().exclusions if e.listing_id == aapl]
                self.assertIn(exclusion.file_sha256, {s.file_sha256 for s in built.summaries})  # the file stays in M
                self.assertIn((f"header/{column}", ing.IssueCode.DUPLICATE_SESSION_DATE), [(i.row_ref, i.code) for _s, i in built.issues])
                self.assertEqual(built.store.quotes(aapl, D(2025, 1, 1), D(2025, 1, 31)).readings, ())

    def test_2_the_control_without_a_repeated_column_and_with_a_repeated_column_nobody_reads_is_served(self):
        built, aapl, lk = self.lookup(k.av_csv(self.ROWS))
        self.assertEqual((lk.outcome, lk.selected.observation.price), (ing.LookupOutcome.FOUND, Decimal("50.5")))
        lines = ["timestamp,open,high,low,close,volume,note,note"] + [",".join(list(r) + ["a", "b"]) for r in reversed(self.ROWS)]
        built, aapl, lk = self.lookup(("\n".join(lines) + "\n").encode("utf-8"))
        self.assertEqual((lk.outcome, lk.selected.observation.price), (ing.LookupOutcome.FOUND, Decimal("50.5")))
        self.assertEqual(built.store.export().exclusions, ())


class MockRouteDuplicateDatesTests(ing.WorldCase):
    """HIGH-1 of the review (2026-10-25). Tests V0 and V0-FX (1.16) are written for EVERY route, and the golden worlds that cite 1.16 are mock synthetic files. A
    mock quote file that states AAPL/XNAS 2025-01-07 twice is CONTRADICTED whatever the values (Example 3-E (a), (a')), and a mock FX file that states one pair
    on one date twice excludes every currency series of the file (V0-FX). The expected outcomes are the Quant's, not the code's."""

    ADAPTERS = ing.ADAPTERS + (MockSyntheticAdapter(ing.DataKind.QUOTE), MockSyntheticAdapter(ing.DataKind.FX))

    @staticmethod
    def q(day, close, ticker="AAPL", mic="XNAS"):
        return {"ticker": ticker, "mic": mic, "date": day, "close": Decimal(close), "volume": Decimal(1000)}

    @staticmethod
    def f(day, rate, quote="USD", base="EUR"):
        return {"base": base, "quote": quote, "date": day, "rate": Decimal(rate), "rate_basis": "x"}

    def quote_world(self, quotes, ident=None):
        spec = dict(source_id="mock.synthetic", kind=ing.DataKind.QUOTE, payload_format=MOCK_FORMAT, payload=make_synthetic_payload(quotes=tuple(quotes)),
                    label="m", ext="json", currency=k.USD)
        built, ident = self.world([spec, ing.nyse_cal(), ing.ecb_cal()], adapters=self.ADAPTERS, ident=ident)
        return built, ident, market11_conventions(built.calendars)

    def fx_world(self, rates):
        spec = dict(source_id="mock.synthetic", kind=ing.DataKind.FX, payload_format=MOCK_FORMAT, payload=make_synthetic_payload(fx=tuple(rates)),
                    label="mfx", ext="json")
        built, ident = self.world([spec, ing.ecb_cal()], adapters=self.ADAPTERS)
        return built, market11_conventions(built.calendars)

    def assert_quote_series_contradicted(self, built, ident, conv, ticker="AAPL", dates="2025-01-07"):
        listing = kit.listing_id(ident, ticker, "XNAS")
        for day in (D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)):  # the WHOLE series: no reading on any date
            lk = built.store.quote_on(listing, day, conv)
            st = ing.price_input_state(lk)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (ing.LookupOutcome.NO_HISTORY, None, ing.S.INSUFFICIENT_DATA, ing.R.MISSING_PRICE_HISTORY), day)
            (note,) = lk.lineage_notes
            self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
            self.assertIn("DUPLICATE_SESSION_DATE", note)
            self.assertIn(dates, note)
        self.assertEqual(built.store.quotes(listing, D(2025, 1, 1), D(2025, 1, 31)).readings, ())
        (exclusion,) = [e for e in built.store.export().exclusions if e.listing_id == listing]
        self.assertEqual(exclusion.test, "V0")
        self.assertIn(exclusion.file_sha256, {s.file_sha256 for s in built.summaries})  # the file stays in M

    def test_1_control_a_mock_quote_file_with_one_row_per_session_is_served(self):
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("2025-01-08", "102")])
        listing = kit.listing_id(ident, "AAPL", "XNAS")
        self.assertEqual((built.store.quote_on(listing, D(2025, 1, 8), conv).selected.observation.price,
                          built.store.quote_on(listing, D(2025, 1, 7), conv).selected.observation.price), (Decimal(102), Decimal(101)))
        self.assertEqual(built.store.export().exclusions, ())

    def test_2_the_reviewers_case_the_7th_twice_with_two_closes_contradicts_the_series_on_every_date(self):
        # before: FOUND 102 on the 8th and NO_SELECTION on the 7th, with no exclusion and no issue
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("2025-01-07", "150"), self.q("2025-01-08", "102")])
        self.assert_quote_series_contradicted(built, ident, conv)

    def test_3_equal_rows_count_as_well(self):
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("2025-01-07", "101"), self.q("2025-01-08", "102")])
        self.assert_quote_series_contradicted(built, ident, conv)

    def test_4_one_session_in_two_spellings_is_one_session_stated_twice(self):
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("20250107", "101"), self.q("2025-01-08", "102")])
        self.assert_quote_series_contradicted(built, ident, conv)

    def test_5_a_repeated_row_that_fails_its_own_check_still_states_the_session(self):
        bad = dict(self.q("2025-01-07", "0"))  # NON_POSITIVE_VALUE: refused as a row, yet it states the 7th
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), bad, self.q("2025-01-08", "102")])
        self.assert_quote_series_contradicted(built, ident, conv)
        self.assertIn(ing.IssueCode.NON_POSITIVE_VALUE, [i.code for _s, i in built.issues])

    def test_6_only_the_series_that_repeats_is_excluded(self):
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD),
                                  InstrumentEntry("Microsoft", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "MSFT", k.USD)])
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("2025-01-07", "150"), self.q("2025-01-08", "102"),
                                               self.q("2025-01-06", "200", "MSFT"), self.q("2025-01-07", "201", "MSFT"), self.q("2025-01-08", "202", "MSFT")], ident=reg)
        self.assert_quote_series_contradicted(built, ident, conv)
        msft = built.store.quote_on(kit.listing_id(ident, "MSFT", "XNAS"), D(2025, 1, 8), conv)
        self.assertEqual((msft.outcome, msft.selected.observation.price), (ing.LookupOutcome.FOUND, Decimal(202)))
        self.assertFalse(any(n.startswith("NO_ADMITTED_SOURCE") for n in msft.lineage_notes), msft.lineage_notes)

    def test_7_unreadable_dates_state_nothing_on_the_mock_route_either(self):
        built, ident, conv = self.quote_world([self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("", "5"), self.q("", "6"),
                                               self.q("2025-13-01", "7"), self.q("2025-13-01", "8"), self.q("2025-01-08", "102")])
        listing = kit.listing_id(ident, "AAPL", "XNAS")
        lk = built.store.quote_on(listing, D(2025, 1, 8), conv)
        self.assertEqual((lk.outcome, lk.selected.observation.price), (ing.LookupOutcome.FOUND, Decimal(102)))
        self.assertEqual(built.store.export().exclusions, ())
        # each of the four rows is refused alone (a blank date is MISSING_FIELD in the mock row reader, a non-date UNPARSEABLE_ROW), none is a duplicate
        self.assertEqual(sorted(i.code.value for _s, i in built.issues if i.code in (ing.IssueCode.UNPARSEABLE_ROW, ing.IssueCode.MISSING_FIELD)),
                         ["MISSING_FIELD", "MISSING_FIELD", "UNPARSEABLE_ROW", "UNPARSEABLE_ROW"])
        self.assertEqual([i for _s, i in built.issues if i.code is ing.IssueCode.DUPLICATE_SESSION_DATE], [])

    def test_8_a_route_that_lists_no_statements_is_judged_on_the_quotes_it_emits(self):
        """Ingestion owns the duplicate test: an adapter that forgets to list `dated_statements` (a future route) is still judged, on its own quotes."""
        class Forgetful(MockSyntheticAdapter):
            def translate(self, manifest, payload):
                return dataclasses.replace(super().translate(manifest, payload), dated_statements=None)

        spec = dict(source_id="mock.synthetic", kind=ing.DataKind.QUOTE, payload_format=MOCK_FORMAT, label="m", ext="json", currency=k.USD,
                    payload=make_synthetic_payload(quotes=(self.q("2025-01-06", "100"), self.q("2025-01-07", "101"), self.q("2025-01-07", "150"),
                                                           self.q("2025-01-08", "102"))))
        built, ident = self.world([spec, ing.nyse_cal(), ing.ecb_cal()], adapters=ing.ADAPTERS + (Forgetful(ing.DataKind.QUOTE),))
        self.assert_quote_series_contradicted(built, ident, market11_conventions(built.calendars))

    # --- FX in the long layout: the key is (pair, date), the unit every currency series of the file ----------------------------------------------

    def assert_every_currency_excluded(self, built, conv, quotes=("USD", "HKD")):
        for quote in quotes:
            for day in (D(2025, 1, 7), D(2025, 1, 8)):
                lk = built.store.fx_on(k.EUR, k.CurrencyCode(quote), day, conv)
                self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.NOT_IN_RELEASE, None), (quote, day))
            self.assertTrue(any(n.startswith(f"V0_FX_DUPLICATE_DATE: the {quote} series of file ") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(sorted(e.currency for e in built.store.export().exclusions if e.listing_id is None), sorted(quotes))

    def test_9_control_two_currencies_on_every_date_are_not_a_date_stated_twice(self):
        # (HKD per USD is 8.50/1.09 = 7.798 and 8.60/1.10 = 7.818, inside the 7.75..7.85 peg band, so the plausibility check passes)
        built, conv = self.fx_world([self.f("2025-01-07", "1.09"), self.f("2025-01-07", "8.50", "HKD"), self.f("2025-01-08", "1.10"), self.f("2025-01-08", "8.60", "HKD")])
        self.assertEqual(built.store.fx_on(k.EUR, k.USD, D(2025, 1, 8), conv).outcome, ing.LookupOutcome.FOUND)
        self.assertEqual(built.store.fx_on(k.EUR, k.HKD, D(2025, 1, 8), conv).outcome, ing.LookupOutcome.FOUND)
        self.assertEqual(built.store.export().exclusions, ())

    def test_10_the_reviewers_case_one_pair_on_one_date_twice_excludes_every_currency_series_of_the_file(self):
        # before: FOUND 11/10 on the 8th and NO_SELECTION on the 7th. HKD is stated once on both dates and is excluded as well (the unit is the file's series)
        built, conv = self.fx_world([self.f("2025-01-07", "1.09"), self.f("2025-01-07", "9.99"), self.f("2025-01-07", "8.4", "HKD"), self.f("2025-01-08", "1.10"),
                                     self.f("2025-01-08", "8.5", "HKD")])
        self.assert_every_currency_excluded(built, conv)
        (usd,) = [e for e in built.store.export().exclusions if e.currency == "USD"]
        self.assertIn("2025-01-07", usd.reason)
        self.assertIn("EUR/USD", usd.reason)  # the detail names the pair stated twice

    def test_12_an_fx_route_that_names_nothing_is_judged_on_the_observations_it_emits(self):
        """Ingestion judges what an FX adapter emitted: a (pair, date) emitted twice excludes every currency series of the file, whole, even from an adapter
        that forgot to name the series (a future route)."""
        class Forgetful(MockSyntheticAdapter):
            def _duplicated_fixings(self, rows):
                return (), []

        spec = dict(source_id="mock.synthetic", kind=ing.DataKind.FX, payload_format=MOCK_FORMAT, label="mfx", ext="json",
                    payload=make_synthetic_payload(fx=(self.f("2025-01-07", "1.09"), self.f("2025-01-07", "9.99"), self.f("2025-01-07", "8.4", "HKD"),
                                                       self.f("2025-01-08", "1.10"), self.f("2025-01-08", "8.5", "HKD"))))
        built, _ident = self.world([spec, ing.ecb_cal()], adapters=ing.ADAPTERS + (Forgetful(ing.DataKind.FX),))
        self.assert_every_currency_excluded(built, market11_conventions(built.calendars))

    def test_11_equal_rows_and_two_spellings_count_as_well(self):
        for second in ("2025-01-07", "20250107"):
            built, conv = self.fx_world([self.f("2025-01-07", "1.09"), self.f(second, "1.09"), self.f("2025-01-08", "1.10"), self.f("2025-01-08", "8.5", "HKD")])
            self.assert_every_currency_excluded(built, conv)


class CurrencyStatedTwiceTests(ing.WorldCase):
    """LOW-4 and MEDIUM-3 of the review, with Addendum A.3: a fixing is a (date, currency), whatever the layout. One currency stated twice for one date is the
    V0-FX duplicate: every currency series of the file is excluded, the file stays in M, the lineage carries `V0_FX_DUPLICATE_DATE`, the dates and the currency."""

    frank = FixingDateStatedTwiceTests.frank
    frank_world = FixingDateStatedTwiceTests.frank_world
    assert_frankfurter_excluded = FixingDateStatedTwiceTests.assert_frankfurter_excluded

    def assert_names(self, built, currency, *words):
        (usd,) = [e for e in built.store.export().exclusions if e.currency == currency]
        for word in words:
            self.assertIn(word, usd.reason)

    # --- Frankfurter: the second level (a currency in a date) and the top level (a repeated `rates` member) ----------------------------------

    def test_1_frankfurter_one_currency_twice_in_one_date_excludes_every_currency_series(self):
        built, conv = self.frank_world('"2025-01-02":{"CNY":7.8000,"USD":1.0800,"USD":9.9900},"2025-01-03":{"CNY":7.8100,"USD":1.0810}')
        self.assert_frankfurter_excluded(built, conv)
        self.assert_names(built, "CNY", "2025-01-02", "USD")

    def test_2_frankfurter_the_same_currency_in_two_spellings_counts(self):
        built, conv = self.frank_world('"2025-01-02":{"CNY":7.8000,"USD":1.0800,"usd":9.9900},"2025-01-03":{"CNY":7.8100,"USD":1.0810}')
        self.assert_frankfurter_excluded(built, conv)

    def test_3_frankfurter_two_currencies_once_each_is_a_control(self):
        built, conv = self.frank_world(FixingDateStatedTwiceTests.CONTROL)
        self.assertEqual(built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), conv).outcome, ing.LookupOutcome.FOUND)
        self.assertEqual(built.store.export().exclusions, ())

    def test_4_medium_3_a_date_in_two_rates_members_is_a_date_stated_twice(self):
        # json.loads keeps the LAST `rates` member and serves 9.99 for the 2nd; the first member is silently dropped
        text = ('{"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-01-03",'
                '"rates":{"2025-01-02":{"CNY":7.8000,"USD":1.0800}},'
                '"rates":{"2025-01-02":{"CNY":7.8000,"USD":9.9900},"2025-01-03":{"CNY":7.8100,"USD":1.0810}}}')
        spec = dict(FixingDateStatedTwiceTests.frank(self, ""), payload=text.encode("utf-8"))
        built, _ident = self.world([spec, ing.ecb_cal()])
        self.assert_frankfurter_excluded(built, market11_conventions(built.calendars))

    def test_5_medium_3_a_second_rates_member_with_other_dates_refuses_the_file_and_serves_nothing(self):
        # the text does not settle which member stands, and the parser's order must not decide: fail closed (a choice the contract does not cover)
        text = ('{"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-01-03",'
                '"rates":{"2025-01-02":{"CNY":7.8000,"USD":1.0800}},"rates":{"2025-01-03":{"CNY":7.8100,"USD":1.0810}}}')
        spec = dict(FixingDateStatedTwiceTests.frank(self, ""), payload=text.encode("utf-8"))
        built, _ident = self.world([spec, ing.ecb_cal()])
        conv = market11_conventions(built.calendars)
        for day in (D(2025, 1, 2), D(2025, 1, 3)):
            lk = built.store.fx_on(k.EUR, k.USD, day, conv)
            self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.NOT_IN_RELEASE, None), day)
        self.assertIn(ing.IssueCode.UNKNOWN_FORMAT, [i.code for _s, i in built.issues])
        self.assertTrue(any("'rates' is stated more than once" in i.detail or "more than once" in i.detail for _s, i in built.issues))

    def test_6_medium_3_a_repeated_base_or_amount_refuses_the_file(self):
        for member in ('"base":"USD",', '"amount":2.0,'):
            text = ('{' + member + '"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-01-03",'
                    '"rates":{"2025-01-02":{"CNY":7.8000,"USD":1.0800},"2025-01-03":{"CNY":7.8100,"USD":1.0810}}}')
            spec = dict(FixingDateStatedTwiceTests.frank(self, ""), payload=text.encode("utf-8"))
            built, _ident = self.world([spec, ing.ecb_cal()])
            self.assertEqual(built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), market11_conventions(built.calendars)).outcome, ing.LookupOutcome.NOT_IN_RELEASE, member)
            self.assertIn(ing.IssueCode.UNKNOWN_FORMAT, [i.code for _s, i in built.issues], member)

    # --- ECB: a header that names a currency twice ---------------------------------------------------------------------------------------------

    def ecb_world(self, currencies, **kw):
        rows = [(d, [v[0], v[0], v[1]]) for d, v in ing.ECB_ROWS]  # USD, USD, HKD (the second USD column carries the same number)
        rows = [(d, [v[0], "9.9900", v[2]]) if d == "2025-01-02" else (d, v) for d, v in rows]
        built, _ident = self.world([ing.ecb_spec(rows=rows, currencies=currencies, **kw), ing.ecb_cal()])
        return built, market11_conventions(built.calendars)

    def test_7_ecb_a_header_with_usd_twice_excludes_every_currency_series_of_the_file(self):
        built, conv = self.ecb_world(("USD", "USD", "HKD"))
        for quote in (k.USD, k.HKD):
            for day in (D(2025, 1, 2), D(2025, 1, 8)):
                lk = built.store.fx_on(k.EUR, quote, day, conv)
                self.assertEqual((lk.outcome, lk.rate), (ing.LookupOutcome.NOT_IN_RELEASE, None), (quote.code, day))
            self.assertTrue(any(n.startswith(f"V0_FX_DUPLICATE_DATE: the {quote.code} series of file ") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(sorted(e.currency for e in built.store.export().exclusions if e.listing_id is None), ["HKD", "USD"])
        self.assert_names(built, "HKD", "stated twice: USD", "2025-01-02", "2025-01-08")  # every date of the file, and the currency stated twice
        (sha,) = {e.file_sha256 for e in built.store.export().exclusions}
        self.assertIn(sha, {s.file_sha256 for s in built.summaries})  # the file stays in M

    def test_8_ecb_a_repeated_column_that_is_not_read_changes_nothing(self):
        built, conv = self.ecb_world(("USD", "USD", "HKD"), source_identifiers=("HKD",))
        self.assertEqual(built.store.fx_on(k.EUR, k.HKD, D(2025, 1, 8), conv).outcome, ing.LookupOutcome.FOUND)
        self.assertEqual(built.store.export().exclusions, ())


class AdapterSweepTests(unittest.TestCase):
    """HIGH-1 asked for the sweep: for EVERY adapter in `src/marketdata/adapters/`, do items 25 (Test V0 duplicate session date) and 34 (Test V0-FX) run there? The
    table below is that answer. A new adapter class that is not in the table fails the first test, so the claim the label makes ("in every market, on every route")
    cannot go stale silently. The behaviours themselves are tested through the real path in the classes above."""

    # class name -> (data kind, how items 25 / 34 run for it)
    TABLE = {
        "AlphaVantageQuoteAdapter": ("QUOTE", "25: translate_daily_csv lists the dated statements; ingestion judges per listing"),
        "AkshareCnQuoteAdapter": ("QUOTE", "25: translate_daily_csv, as above"),
        "AkshareSinaQuoteAdapter": ("QUOTE", "25: translate_daily_csv, as above"),
        "MockSyntheticAdapter": ("QUOTE/FX/CORPORATE_ACTION/BENCHMARK", "25: lists dated statements (QUOTE); 34: names the contradicted currency series (FX); the other two kinds are outside items 25 and 34"),
        "EcbEurofxrefFxAdapter": ("FX", "34: names every currency series when a date or a currency is stated twice"),
        "FrankfurterFxAdapter": ("FX", "34: the same, at every object level it reads"),
        "CalendarFileAdapter": ("CALENDAR", "outside items 25 and 34 (a calendar is not a price or an FX series)"),
        "OpenFigiIdentityAdapter": ("IDENTITY", "outside items 25 and 34"),
        "SyntheticRiskFreeAdapter": ("RISK_FREE", "outside items 25 and 34: a series' dates must be strictly increasing (contract), so a repeated date is refused"),
        "EodhdSplitCandidateAdapter": ("CORPORATE_ACTION", "outside items 25 and 34"),
    }

    def adapter_classes(self):
        import importlib  # noqa: PLC0415
        import inspect  # noqa: PLC0415
        import pkgutil  # noqa: PLC0415

        import marketdata.adapters as package  # noqa: PLC0415

        found = {}
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"marketdata.adapters.{info.name}")
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module.__name__ and hasattr(cls, "translate") and name != "SourceAdapter":
                    found[name] = module
        return found

    def test_1_every_adapter_class_is_in_the_table(self):
        self.assertEqual(sorted(self.adapter_classes()), sorted(self.TABLE))

    def test_2_every_price_adapter_lists_dated_statements_and_every_fx_adapter_names_contradicted_series(self):
        import inspect  # noqa: PLC0415

        for name, module in self.adapter_classes().items():
            kinds = self.TABLE[name][0]
            source = inspect.getsource(module)
            if "QUOTE" in kinds:
                self.assertTrue("translate_daily_csv(" in source or "DatedStatement(" in source, name)
            if "FX" in kinds:
                self.assertIn("ContradictedSeries(", source, name)

    def test_3_ingestion_judges_what_an_adapter_emitted_whatever_it_listed(self):
        """The safety net is in `ingest_file`, so a route that is not in this table is still judged: the fallbacks are tested in `MockRouteDuplicateDatesTests`
        (tests 8 and 12) and their mutations fail them."""
        import inspect  # noqa: PLC0415

        from marketdata import ingest as ingest_module  # noqa: PLC0415

        source = inspect.getsource(ingest_module.ingest_file)
        self.assertIn("out.dated_statements", source)
        self.assertIn("seen_fx", source)


# --- 5. What this increment does NOT do ------------------------------------------------------------------------------------------------------

class ReleaseLabelIsMovedTests(unittest.TestCase):
    """The code label is market-data/1.16 (the F1 R4a label increment, 2026-10-25, CP2 section 11 item 35 and its gate 'When a manifest may cite 1.16': items 23 to
    28 and 32 to 35 are built; each unbuilt behaviour of items 17 to 20, 29 and 30 has a 'not built' line; the three registries are re-issued). These assertions
    state the moved state, and the PROFILE CONTENT that the profile-set id `market-data/1.16#profiles/5` stands for (Quant answer (b)), so that content cannot
    change under an unchanged id: the id and the content move together or the test fails. (This class replaces `ReleaseLabelIsNotMovedYetTests`, which stated the
    1.15 state and the known id/content inconsistency of the working tree; the inconsistency is closed by this increment.)"""

    def test_the_eight_label_constants_name_1_16_and_the_profile_counter_is_5(self):
        from marketdata import manifest, market11, reconciliation  # noqa: PLC0415

        values = {manifest.CONVENTION_SET_ID, prof.CONVENTION_SET, market11.FRESHNESS_ID.split("#")[0], market11.PRICE_OF_DATE_ID.split("#")[0],
                  market11.FX_ID.split("#")[0], reconciliation.RULE_ID.split("#")[0], reconciliation.TOLERANCE_REF.split("#")[0],
                  prof.PROFILE_SET_VERSION.split("#")[0]}
        self.assertEqual(values, {"market-data/1.16"})
        self.assertEqual(prof.PROFILE_SET_VERSION, "market-data/1.16#profiles/5")

    def test_the_a6_table_id_names_the_version_that_introduced_its_content(self):
        self.assertEqual(A6.version, "market-data/1.16#a6/2")

    def test_the_profile_content_of_profiles_5_is_the_three_changes_of_answer_b(self):
        # (1) the two Alpha Vantage TIME_SERIES_DAILY calls carry the DECLARED label source with its reference, as data (item 23)
        for source in ("alphavantage.us", "alphavantage.cn"):
            entry = prof.SOURCES[source].call_adjustment["TIME_SERIES_DAILY"]
            self.assertEqual((entry.adjustment, entry.status, entry.reference), ("RAW", "DECLARED", "PD-0066 decision 3"), source)
        # (2) the three other US venues are MICs of the US market with a zone (Ruling 2.2 item 1; Ruling 4.7 item 6)
        for mic in ("ARCX", "BATS", "XASE"):
            self.assertEqual(prof.MIC_MARKET[mic], "US", mic)
            self.assertEqual(prof.EXCHANGE_ZONES[mic], "America/New_York", mic)
        # nothing else of the venue tables moved: the five venues of 1.15 and BJSE (unmapped on purpose, LISTING_EXCHANGE_UNKNOWN)
        self.assertEqual(prof.MIC_MARKET, {"XNYS": "US", "XNAS": "US", "ARCX": "US", "BATS": "US", "XASE": "US", "XHKG": "HK", "XSHG": "CN", "XSHE": "CN"})
        self.assertNotIn("BJSE", prof.MIC_MARKET)
        # (3) the gate in the Ruling's order: unmapped MIC, then no profile, then coverage, then admission
        self.assertEqual(prof.listing_market_refusal("akshare.cn", "BJSE")[0], "LISTING_EXCHANGE_UNKNOWN")
        self.assertEqual(prof.listing_market_refusal("no.such.source", "XNAS")[0], "SOURCE_NOT_ADMITTED")


if __name__ == "__main__":
    unittest.main()
