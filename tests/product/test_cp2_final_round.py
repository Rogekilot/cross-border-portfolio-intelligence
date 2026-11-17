"""CP2 final round (re-check section 26 of `reviews/TECH_REVIEW.md`; conventions `market-data/1.5`): one regression test per item.

    C2-14  an off-calendar FX fixing is excluded on EVERY as-of date          C2-15  overlapping linking windows fail closed
    ns     the reserved `finweb.` namespace folds invisible characters        refused  a refused profile blocks every file kind
    1.5    FIGI levels, A.6 attachment, the composite uniqueness test, symbol change on exchange-level FIGIs, delivered_dp

(The grant-spec test, "the application role holds no CREATE anywhere", is in `test_postgres_least_privilege.py`.)
Every expected value is derived by hand from the inputs shown. All data is synthetic.
"""

import datetime
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import test_cp2_fix_round_marketdata as fr  # noqa: E402
import test_corporate_actions_service as f8t  # noqa: E402

k = x.k
c = x.c
kit = x.kit

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.instrument import Instrument, Listing, SecurityType  # noqa: E402
from marketdata.adapters.base import AdapterOutput  # noqa: E402
from marketdata.exchange_codes import A6, ATTACHING  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data, ingest_file  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord, TermsCheck  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry, SymbolChangeStatus  # noqa: E402
from persistence import ledger_store  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S, R = SufficiencyState, ReasonCode
state_of = fr.state_of


# --- C2-14 -------------------------------------------------------------------------------------------------------------

class C2_14_AnOffCalendarFixingIsNeverAdmissible(unittest.TestCase):
    """Probes P8a and P8b. ECB calendar 2, 3, 6, 7 January; fixings dated 2025-01-03 (1.08) and SATURDAY 2025-01-04 (1.20).
    Before the fix: as of 01-04 UNKNOWN, but as of 01-05 `FOUND 6/5 date_used 2025-01-04 missed 0 AVAILABLE` and as of 01-06
    `AVAILABLE + STALE_DATA`, the Saturday rate used as a print (the OFF_CALENDAR_DATE test ran only when the date equalled
    the as-of day)."""

    CAL = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7)]

    def conv(self, calendars=True):
        cal = [k.ecb_calendar(self.CAL, covers=(D(2025, 1, 1), D(2025, 1, 31)))] if calendars else []
        return market11_conventions(fr.CalendarSet(cal))

    def store(self):
        return k.store([k.fx_reading(D(2025, 1, 3), "USD", "1.08"), k.fx_reading(D(2025, 1, 4), "USD", "1.20")])

    def test_the_saturday_fixing_is_never_the_rate_used_on_any_as_of_date(self):
        # as of the 4th and 5th no fixing day has passed since the 3rd (the calendar lists none): 0 missed. As of the 6th: {6} = 1.
        for day, missed, st in ((D(2025, 1, 4), 0, (S.AVAILABLE, None)), (D(2025, 1, 5), 0, (S.AVAILABLE, None)),
                                (D(2025, 1, 6), 1, (S.AVAILABLE, R.STALE_DATA))):
            lk = self.store().fx_on(k.EUR, k.USD, day, self.conv())
            self.assertEqual((lk.outcome, lk.rate, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, Fraction(108, 100), D(2025, 1, 3), missed), day)
            self.assertEqual(state_of(lk, fx=True), st, day)
            self.assertTrue(any(n.startswith("OFF_CALENDAR_DATE") and "2025-01-04" in n for n in lk.lineage_notes), (day, lk.lineage_notes))

    def test_a_cross_through_a_saturday_leg_falls_back_to_the_last_fixing_where_every_leg_exists(self):
        st = k.store([k.fx_reading(D(2025, 1, 3), "USD", "1.0810"), k.fx_reading(D(2025, 1, 3), "CNY", "7.8100"),
                      k.fx_reading(D(2025, 1, 4), "USD", "1.2000"), k.fx_reading(D(2025, 1, 4), "CNY", "7.8100")])
        lk = st.fx_on(k.CNY, k.USD, D(2025, 1, 5), self.conv())
        self.assertEqual((lk.outcome, lk.date_used, lk.rate), (LookupOutcome.FOUND, D(2025, 1, 3), Fraction(10810, 78100)))  # not 120/781

    def test_with_no_earlier_valid_fixing_there_is_no_history_with_the_cause_in_lineage(self):
        st = k.store([k.fx_reading(D(2025, 1, 4), "USD", "1.20")])
        lk = st.fx_on(k.EUR, k.USD, D(2025, 1, 5), self.conv())
        self.assertEqual((lk.outcome, lk.rate, state_of(lk, fx=True)), (LookupOutcome.NO_HISTORY, None, (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY)))
        self.assertTrue(any(n.startswith("OFF_CALENDAR_DATE") for n in lk.lineage_notes))

    def test_where_no_calendar_covers_the_date_it_is_not_excluded_and_freshness_is_unknown(self):
        for conv in (self.conv(calendars=False),
                     market11_conventions(fr.CalendarSet([k.ecb_calendar([D(2024, 1, 2)], covers=(D(2024, 1, 1), D(2024, 1, 31)))]))):
            lk = self.store().fx_on(k.EUR, k.USD, D(2025, 1, 5), conv)
            self.assertEqual((lk.outcome, state_of(lk, fx=True)), (LookupOutcome.FRESHNESS_UNKNOWN, (S.INSUFFICIENT_DATA, None)))

    def test_a_listed_fixing_day_is_still_used_and_carries_no_off_calendar_note(self):
        st = k.store([k.fx_reading(D(2025, 1, 3), "USD", "1.08"), k.fx_reading(D(2025, 1, 6), "USD", "1.09")])
        lk = st.fx_on(k.EUR, k.USD, D(2025, 1, 6), self.conv())
        self.assertEqual((lk.outcome, lk.date_used, lk.rate, lk.lineage_notes), (LookupOutcome.FOUND, D(2025, 1, 6), Fraction(109, 100), ()))

    # -- through the real build path (P8b) and the price side ---------------------------------------------------------------

    def build(self, us_rows, ecb_rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        x.write_registry(root)
        specs, adapters = x.world_specs("formats")
        out = []
        for spec in specs:
            if spec["source_id"] == x.SRC_US:
                spec = dict(spec, payload=x.av_us_csv(us_rows))
            if spec["source_id"] == x.SRC_ECB:
                spec = dict(spec, payload=k.ecb_csv(ecb_rows, ["USD", "HKD", "CNY"]))
            out.append(spec)
        manifests = [kit.write_file(root, **spec) for spec in out]
        release = MarketDataRelease.from_manifests("c2-14", manifests, [])
        files = FileStore(root)
        ident = x.identity()
        return build_in_memory_market_data(release, files, files.load_registry(), adapters, ident, catalog_calendars={}), ident

    def test_the_build_path_ecb_file_with_a_saturday_row_falls_back_to_friday(self):
        rows = [("2025-01-03", ["1.0810", "8.4100", "7.8100"]), ("2025-01-04", ["1.2000", "8.4100", "7.8100"])]
        built, _ = self.build([(D(2025, 1, 3), "151.10", 1200)], rows)
        lk = built.store.fx_on(k.CNY, k.USD, D(2025, 1, 5), market11_conventions(built.calendars))
        # market-data/1.7 (C2-16) supersedes the C2-14 row-level fallback at build: one Saturday row excludes the WHOLE series of
        # that file (it used to fall back to 1081/7810 of the 3rd), so no fixing of that file is used: no rate at all
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        self.assertTrue(any("V0_FX_OFF_CALENDAR" in n for n in lk.lineage_notes), lk.lineage_notes)

    def test_the_price_side_drops_a_series_with_a_saturday_row_at_build_and_never_uses_it_on_a_later_day(self):
        built, ident = self.build([(D(2025, 1, 3), "151.10", 1200), (D(2025, 1, 4), "199.99", 900)],
                                  [("2025-01-03", ["1.0810", "8.4100", "7.8100"])])
        v0 = [r for r in built.label_results if r.test == "V0" and r.listing_id == x.lid(ident, "AAPL", "XNAS")]
        self.assertEqual([(r.status, r.admitted) for r in v0], [(c.LabelStatus.CONTRADICTED, False)])
        lk = built.store.quote_on(x.lid(ident, "AAPL", "XNAS"), D(2025, 1, 6), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))


# --- C2-15 -------------------------------------------------------------------------------------------------------------

class C2_15_OverlappingWindowsFailClosedWhateverTheOrderOrRange(unittest.TestCase):
    """Probes P2r and P2s. Corroborated 2:1 on 2025-02-03 and 3:1 on 2025-02-17, TEN sessions apart, 50 units, NO ledger split.
    Before the fix: run 1 appended the first and called the second CONFLICT_RATIO; run 2 (same ledger and release) made both
    CONFLICT_RATIO; a run over 2025-02-10..02-28 only appended the 3:1 with no suppression. Ruling 6.4a item 6 states the
    intent: 'a listing that splits twice within 40 sessions is rare enough that failing closed costs little'."""

    FEB17 = D(2025, 2, 17)

    def port(self):
        return f8t.port_with([f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (2, 1)), f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (2, 1)),
                              f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (3, 1), day=self.FEB17),
                              f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (3, 1), day=self.FEB17)])

    def check(self, report, ledger, expect_dates):
        self.assertEqual(sorted((o.ex_date, o.decision, o.linking) for o in report.outcomes),
                         [(d, f8b.SplitDecision.CONFLICT_RATIO, "CONFLICT_RATIO") for d in expect_dates])
        self.assertEqual(ledger.appended, [])  # NOTHING is appended for either
        # valuation suppressed from the EARLIER ex-date, open-ended, SOURCE_CONFLICT
        self.assertEqual([(s.first_date, s.end_exclusive, s.reason_code) for s in report.suppressions],
                         [(f8t.EX, None, ReasonCode.SOURCE_CONFLICT)] * len(expect_dates))

    def test_the_first_run_a_rerun_and_a_run_over_only_the_second_split_all_give_the_same_outcome(self):
        ledger = f8t.ledger_with_holdings()
        both = (f8t.EX, self.FEB17)
        self.check(f8t.run(ledger, self.port()), ledger, both)                               # run 1
        self.check(f8t.run(ledger, self.port()), ledger, both)                               # run 2: same ledger, same release
        fresh = f8t.ledger_with_holdings()
        # the range holds only the second split; the first is NOT in the range, but the whole release places the windows
        self.check(f8t.run(fresh, self.port(), start=D(2025, 2, 10), end=D(2025, 2, 28)), fresh, (self.FEB17,))
        self.assertEqual(f8t.quantity_on(ledger, D(2025, 3, 1)), Decimal(50))  # nothing was applied: 50, flagged (evidence: 300)

    def test_the_decision_does_not_depend_on_the_order_the_evidence_is_listed(self):
        a = f8t.run(f8t.ledger_with_holdings(), self.port())
        reordered = f8t.port_with(list(reversed(list(self.port().corporate_actions(f8t.LISTING, D(2025, 1, 1), D(2025, 12, 31)).readings))))
        b = f8t.run(f8t.ledger_with_holdings(), reordered)
        self.assertEqual([(o.ex_date, o.decision) for o in a.outcomes], [(o.ex_date, o.decision) for o in b.outcomes])

    def test_windows_that_do_not_overlap_are_both_appended(self):
        # Feb 3 and Mon Apr 7: W(Feb 3) ends Mar 3; W(Apr 7) opens on the 20th session before Apr 7 (hand: Mar 31..Apr 4 = 5,
        # Mar 24..28 = 10, Mar 17..21 = 15, Mar 10..14 = 20) = Mar 10: the windows are disjoint (the test name's 41 is loose: 46)
        apr7 = D(2025, 4, 7)
        port = f8t.port_with([f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (2, 1)), f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (2, 1)),
                              f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (2, 1), day=apr7),
                              f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (2, 1), day=apr7)])
        ledger = f8t.ledger_with_holdings()
        report = f8t.run(ledger, port)
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED] * 2)
        self.assertEqual(f8t.quantity_on(ledger, D(2025, 4, 8)), Decimal(200))  # 50 x 2 x 2


# --- the reserved namespace -------------------------------------------------------------------------------------------

class ReservedNamespaceFoldingTests(unittest.TestCase):
    """Review section 26: ZWSP, BOM, soft hyphen and the ideographic full stop passed the reserved check. Fold before the check."""

    REF = f8t.REF_41

    def event(self, ref):
        return f8t.LedgerEvent(f8t.eid(), f8t.A1, f8t.EventType.SPLIT, f8t.EX, f8t.USD, listing_id=f8t.LISTING,
                               split_ratio=f8t.SplitRatio(Decimal(4), Decimal(1)), source_reference=ref)

    def test_invisible_characters_and_the_ideographic_full_stop_are_folded_and_refused(self):
        marker = "finweb.f8b/1"
        forms = {
            "zero-width space": marker[:3] + "​" + marker[3:],
            "zero-width joiner": marker[:5] + "‍" + marker[5:],
            "BOM first": "﻿" + self.REF,
            "soft hyphen": marker[:4] + "­" + marker[4:],
            "ideographic full stop": "finweb。f8b/1;x",
            "halfwidth ideographic full stop": "finweb｡f8b/1;x",
            "variation selector": marker[:2] + "️" + marker[2:],
            "combining grapheme joiner": marker[:2] + "͏" + marker[2:],
            "NBSP and upper case": " FINWEB.F8B/1;x",
            "full-width letters": "ｆｉｎｗｅｂ.f8b/1;x",
            "ligature": "ﬁnweb.f8b/1;x",
        }
        for name, text in forms.items():
            self.assertTrue(ledger_store.is_reserved_source_reference(text), name)
            with self.assertRaises(ledger_store.ReservedSourceReferenceError, msg=name):
                ledger_store.append_event(None, self.event(text))  # refused before the connection is touched
        self.assertEqual(ledger_store.fold_reference("​F­inweb。f8b/1"), "finweb.f8b/1")

    def test_ordinary_references_are_untouched(self):
        for fine in ("broker-statement-2025-02-03", "my finweb.f8b/1 note", "f8b/1", "finweb", "fin web.f8b", "x​finweb.f8b"):
            self.assertFalse(ledger_store.is_reserved_source_reference(fine), fine)

    def test_cyrillic_lookalikes_are_a_documented_residual_and_harmless(self):
        # a Cyrillic i (U+0456) for the Latin one is NOT folded to the marker, so the append path stores it; but it is no
        # forgery: the system recognises only the exact-ASCII grammar and the deterministic event id
        look = self.REF.replace("finweb", "fіnweb")
        self.assertFalse(ledger_store.is_reserved_source_reference(look))
        self.assertIsNone(f8b.parse_source_reference(look))
        self.assertFalse(f8b.is_system_event(self.event(look)))
        # and every folded form above is not a system event either, by the same grammar
        for form in ("﻿" + self.REF, "finweb。f8b/1;x", self.REF[:3] + "​" + self.REF[3:]):
            self.assertIsNone(f8b.parse_source_reference(form))


# --- refused profiles block every kind of file ------------------------------------------------------------------------

class RefusedProfileBlocksEveryKindTests(unittest.TestCase):
    ATTESTED = TermsCheck("owner", D(2026, 10, 1), True)

    def verified(self, source_id, kind):
        record = SourceRecord(source_id, source_id, "up", source_id, terms_check=self.ATTESTED)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[record])
        manifest = kit.write_file(root, source_id, kind, "spy/1", b"payload", "p", "bin",
                                  usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, currency=k.USD, retrieved_by="human")
        files = FileStore(root)
        return files.read_verified(files.index()[manifest.file_sha256]), files.load_registry().get(source_id)

    def test_a_corporate_action_and_an_identity_file_from_a_refused_source_are_refused_before_parsing(self):
        for kind in (DataKind.CORPORATE_ACTION, DataKind.IDENTITY, DataKind.BENCHMARK):
            verified, source = self.verified("akshare.cn", kind)  # attested terms, REFUSED profile
            spy = fr.SpyAdapter("akshare.cn", kind)
            with self.assertRaises(ProfileNotAdmittedError, msg=kind) as cm:
                ingest_file(verified, spy, fr.idt.us_registry()[0], source)
            self.assertIn("REFUSED", str(cm.exception))
            self.assertEqual(spy.calls, 0, kind)  # it used to be 1: the payload was parsed

    def test_a_source_with_no_profile_at_all_is_not_blocked_for_these_kinds(self):
        verified, source = self.verified("openfigi", DataKind.IDENTITY)  # no precision profile, not refused
        spy = fr.SpyAdapter("openfigi", DataKind.IDENTITY)
        ingest_file(verified, spy, fr.idt.us_registry()[0], source)
        self.assertEqual(spy.calls, 1)


# --- market-data/1.5: FIGI levels --------------------------------------------------------------------------------------

def assertion(figi, ticker, exch, composite=None, share=None, security_type=None):
    return c.IdentityAssertion(figi, ticker, exch, c.SourceTiming(), k.lineage("synthetic.figi", k.SHA),
                               composite_figi=composite, share_class_figi=share, security_type=security_type)


class Figi15Tests(unittest.TestCase):
    """Ruling 7.3, Appendix A.6. The record values are the Quant's observed examples (700 HK, AAPL US)."""

    TENCENT = ("BBG000BJ35N5", "BBG000BJ35F4", "BBG001S8C4T6")  # figi, compositeFIGI, shareClassFIGI of 700 on exchCode HK
    AAPL = "BBG000B9XRY4"  # figi = compositeFIGI of AAPL on exchCode US

    def registry(self, entries, **kw):
        reg = InMemoryIdentityRegistry(kit.SequentialIds(), **kw)
        reg.register_instruments(entries)
        return reg

    def hk(self):
        return InstrumentEntry("Tencent Holdings", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "700", k.HKD)

    def us(self, mic="XNAS", ticker="AAPL"):
        return InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, mic, "EX", ticker, k.USD)

    def test_the_domain_additions_are_additive_and_default_to_none(self):
        # Listing.figi stays the exchange-level FIGI; the composite and share-class levels are separate attributes
        reg = self.registry([self.hk()])
        listing = reg.listing(kit.listing_id(reg, "700", "XHKG"))
        self.assertEqual((listing.figi, listing.composite_figi), (None, None))
        instrument = [i for i in reg.snapshot()[1]][0]
        self.assertIsNone(instrument.share_class_figi)
        old_style = Listing(uuid.uuid4(), uuid.uuid4(), "XNYS", "NYSE", "X", k.USD, "BBG000000001", True)  # the CP1 positional shape
        self.assertEqual((old_style.figi, old_style.composite_figi), ("BBG000000001", None))
        self.assertIsNone(Instrument(uuid.uuid4(), uuid.uuid4(), SecurityType.ETF).share_class_figi)

    def test_an_exchange_level_hk_record_fills_all_three_levels_in_their_own_fields(self):
        figi, comp, share = self.TENCENT
        reg = self.registry([self.hk()])
        ((_, res, added),) = reg.apply_identity_assertions([assertion(figi, "700", "HK", comp, share, "Common Stock")])
        self.assertEqual((res.status, added), (c.ResolutionStatus.RESOLVED, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI")))
        listing = reg.listing(kit.listing_id(reg, "700", "XHKG"))
        self.assertEqual((listing.figi, listing.composite_figi), (figi, comp))
        (instrument,) = reg.snapshot()[1]
        self.assertEqual(instrument.share_class_figi, share)
        # versioned. Re-recorded 2026-10-25 (F1 R4a): the A.6 table id was market-data/1.5#a6/1; A.6's content changed in 1.16 (`UW` MEMORY ->
        # OBSERVED, PD-0066 decision 4), so the id is market-data/1.16#a6/2 (section 11 item 32: the id names the version that introduced the content)
        self.assertTrue(all("market-data/1.16#a6/2" in r.asserted_by for r in reg.identifier_rows() if r.scheme != "TICKER"))

    def test_the_level_is_read_from_the_record_figi_equal_to_composite_means_composite(self):
        figi, comp, _ = self.TENCENT
        reg = self.registry([self.hk()])
        # the same code "HK" but figi == compositeFIGI: composite-level, so it never fills the exchange-level field, and "HK"
        # is a TO_CONFIRM composite code: nothing attaches at all
        reg.apply_identity_assertions([assertion(comp, "700", "HK", comp)])
        listing = reg.listing(kit.listing_id(reg, "700", "XHKG"))
        self.assertEqual((listing.figi, listing.composite_figi), (None, None))

    def test_memory_and_to_confirm_codes_never_attach_an_exchange_level_figi(self):
        statuses = {(m, e.code): e.status for m, es in A6.exchange.items() for e in es}
        # re-recorded 2026-10-25 (F1 R4a, market-data/1.16 A.6, PD-0066 decision 4): `UW` (XNAS) joins `HK` (XHKG) as OBSERVED; these two attach, nothing else
        self.assertEqual({k_: v for k_, v in statuses.items() if v in ATTACHING}, {("XHKG", "HK"): "OBSERVED", ("XNAS", "UW"): "OBSERVED"})
        reg = self.registry([self.us()])
        # an exchange-level record (figi != compositeFIGI) with the MEMORY Nasdaq code UQ (it was UW before 1.16)
        ((_, res, added),) = reg.apply_identity_assertions([assertion("BBG000XXXXX1", "AAPL", "UQ", "BBG000B9XRY4", None, "Common Stock")])
        self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))
        self.assertIn("MEMORY", reg.assertion_quarantine()[0].reason)
        self.assertIsNone(reg.listing(kit.listing_id(reg, "AAPL", "XNAS")).figi)

    def test_a_confirmed_code_attaches_exactly_like_an_observed_one(self):
        # a human confirmed UQ (the status CONFIRMED). Re-recorded 2026-10-25 (F1 R4a): the code was UW, which is OBSERVED since 1.16 and attaches
        # without a confirmation, so the test would no longer have shown the CONFIRMED status at work; UQ is still MEMORY.
        reg = self.registry([self.us()], exchange_codes={"XNAS": ("UQ",)})
        ((_, _, added),) = reg.apply_identity_assertions([assertion("BBG000XXXXX1", "AAPL", "UQ", "BBG000B9XRY4", "BBG001S5N8V8", "Common Stock")])
        self.assertEqual(added, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI"))
        self.assertEqual(reg.listing(kit.listing_id(reg, "AAPL", "XNAS")).figi, "BBG000XXXXX1")

    def test_a_security_type_the_instrument_does_not_have_is_not_attached(self):
        figi, comp, share = self.TENCENT
        reg = self.registry([self.hk()])
        ((_, res, added),) = reg.apply_identity_assertions([assertion(figi, "700", "HK", comp, share, "ETP")])  # an ETP for a COMMON_STOCK
        self.assertEqual((added, reg.assertion_quarantine()[0].verdict), ((), "SECURITY_TYPE_MISMATCH"))

    def test_the_us_composite_fills_composite_figi_only_under_the_uniqueness_test(self):
        # one active listing of the US with the ticker: attached, in composite_figi, and Listing.figi stays empty
        reg = self.registry([self.us()])
        ((_, res, added),) = reg.apply_identity_assertions([assertion(self.AAPL, "AAPL", "US", self.AAPL, None, "Common Stock")])
        listing = reg.listing(kit.listing_id(reg, "AAPL", "XNAS"))
        self.assertEqual((res.status, res.listing_id, added), (c.ResolutionStatus.RESOLVED, listing.listing_id, ("COMPOSITE_FIGI",)))
        self.assertEqual((listing.figi, listing.composite_figi), (None, self.AAPL))
        # two active US listings with the ticker: attaches NOTHING, quarantined for a human
        two = self.registry([self.us("XNAS"), self.us("XNYS")])
        ((_, res2, added2),) = two.apply_identity_assertions([assertion(self.AAPL, "AAPL", "US", self.AAPL)])
        self.assertEqual((res2.status, added2), (c.ResolutionStatus.AMBIGUOUS, ()))
        self.assertEqual(two.assertion_quarantine()[0].verdict, "COMPOSITE_NOT_UNIQUE")
        self.assertEqual([two.listing(i).composite_figi for i in (kit.listing_id(two, "AAPL", "XNAS"), kit.listing_id(two, "AAPL", "XNYS"))],
                         [None, None])
        # no US listing with the ticker (the only AAPL is on XHKG, another country): nothing
        none = self.registry([self.us("XHKG")])
        ((_, res3, added3),) = none.apply_identity_assertions([assertion(self.AAPL, "AAPL", "US", self.AAPL)])
        self.assertEqual((res3.status, added3), (c.ResolutionStatus.UNRESOLVED, ()))

    def test_a_composite_code_that_is_memory_or_unknown_attaches_nothing(self):
        reg = self.registry([InstrumentEntry("Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", k.CNY)])
        for code in ("CH", "ZZ"):  # CH is MEMORY in A.6; ZZ is not in the table
            ((_, res, added),) = reg.apply_identity_assertions([assertion("BBG000XXXXX2", "600519", code, "BBG000XXXXX2")])
            self.assertEqual((res.status, added), (c.ResolutionStatus.UNRESOLVED, ()), code)
        self.assertIsNone(reg.listing(kit.listing_id(reg, "600519", "XSHG")).composite_figi)

    def test_a_symbol_change_needs_equal_exchange_level_figis_equal_composites_alone_are_not_enough(self):
        figi, comp, share = self.TENCENT
        eff = D(2025, 3, 3)
        # exchange level, same FIGI, the observed HK code: CONFIRMED
        reg = self.registry([self.hk()])
        lid = kit.listing_id(reg, "700", "XHKG")
        ok = reg.propose_symbol_change(lid, "701", eff, [assertion(figi, "700", "HK", comp, share), assertion(figi, "701", "HK", comp, share)])
        self.assertEqual((ok.status, ok.applied), (SymbolChangeStatus.CONFIRMED, True))
        # equal COMPOSITE FIGIs only (both records composite-level): unconfirmed, a venue move keeps the composite
        reg2 = self.registry([self.us()])
        lid2 = kit.listing_id(reg2, "AAPL", "XNAS")
        only = reg2.propose_symbol_change(lid2, "AAPL2", eff, [assertion(self.AAPL, "AAPL", "US", self.AAPL), assertion(self.AAPL, "AAPL2", "US", self.AAPL)])
        self.assertEqual((only.status, only.applied), (SymbolChangeStatus.UNCONFIRMED, False))
        self.assertIn("COMPOSITE", only.reason)
        # same composite, DIFFERENT exchange-level FIGIs (a move to another venue): not a symbol change
        reg3 = self.registry([self.hk()])
        moved = reg3.propose_symbol_change(kit.listing_id(reg3, "700", "XHKG"), "701", eff,
                                           [assertion("BBG000AAAAA1", "700", "HK", comp), assertion("BBG000AAAAA2", "701", "HK", comp)])
        self.assertEqual((moved.status, moved.applied), (SymbolChangeStatus.QUARANTINED, False))

    def test_a6_is_versioned_data_with_the_statuses_of_the_appendix(self):
        # re-recorded 2026-10-25 (F1 R4a, market-data/1.16 Appendix A.6 and section 11 item 32): the table's content changed (`UW` MEMORY ->
        # OBSERVED, PD-0066 decision 4), so its id is market-data/1.16#a6/2 (was market-data/1.5#a6/1); every other entry is as before
        self.assertEqual(A6.version, "market-data/1.16#a6/2")
        self.assertEqual({m: [(e.code, e.status) for e in es] for m, es in A6.exchange.items()}, {
            "XNAS": [("UW", "OBSERVED"), ("UQ", "MEMORY"), ("UR", "MEMORY")], "XNYS": [("UN", "MEMORY")], "ARCX": [("UP", "MEMORY")],
            "BATS": [("UF", "MEMORY")], "XASE": [("UA", "MEMORY")], "XHKG": [("HK", "OBSERVED")], "XSHG": [("CG", "MEMORY")],
            "XSHE": [("CS", "MEMORY")]})
        self.assertEqual({code: (e.status, e.mics) for code, e in A6.composite.items()}, {
            "US": ("OBSERVED", ("XNYS", "XNAS", "ARCX", "BATS", "XASE")), "CH": ("MEMORY", ("XSHG", "XSHE")), "HK": ("TO_CONFIRM", ())})


if __name__ == "__main__":
    unittest.main()
