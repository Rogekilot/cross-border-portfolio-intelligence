"""CP2 fix round (review of 39733e9, `reviews/TECH_REVIEW.md` section 25; conventions `market-data/1.4`): one regression test
per finding that lives in the market-data layer. Each test reproduces the reviewer's failure scenario and passes now.

    C2-1   same-day lookup with no calendar coverage           C2-9   REFUTED file, date-set check, both directions
    C2-4   identity: exchange against the listing's MIC        C2-10  CN class table, precision bound (storage helper)
    C2-12  profile admission follows the profile status        C2-13  the terms gate inside `ingest_file`

(C2-2, C2-3, C2-7, C2-8 and the F8-B half of C2-10 are in `test_corporate_actions_service.py`; C2-5, C2-6 and the stored
precision bound on a real server are in `test_postgres_cp2_fix_round.py`; C2-11 is in `test_marketdata_cp2c2_exit.py`.)

Every expected value is derived by hand from the inputs shown. All data is synthetic.
"""

import datetime
import math
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_exit_kit as x  # noqa: E402
import test_marketdata_cp2c2_identity_and_class as idt  # noqa: E402

k = x.k
c = x.c
kit = x.kit

from domain.instrument import SecurityType  # noqa: E402
from marketdata.adapters.base import AdapterOutput, IssueCode  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.exchange_codes import A6, CodeTable  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data, ingest_file  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    DataKind,
    MarketDataRelease,
    SourceRecord,
    SourceTermsNotAttestedError,
    TermsCheck,
)
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry, SymbolChangeStatus  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from marketdata.store import FXFileWindow  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S, R = SufficiencyState, ReasonCode
SUNDAY = D(2025, 1, 5)
A6_WITHOUT_XNAS = CodeTable("test", {m: e for m, e in A6.exchange.items() if m != "XNAS"}, A6.composite)


def state_of(lookup, fx=False):
    st = (fx_input_state if fx else price_input_state)(lookup)
    return st.state, st.reason


# --- C2-1 --------------------------------------------------------------------------------------------------------------

class C2_1_SameDayLookupNeedsACalendar(unittest.TestCase):
    """The reviewer's probes P1a, P1b, P1d and P1b-build. Before the fix `CalendarSet.count_after` returned 0 for an empty
    interval before looking for a calendar, so a print or fixing dated the as-of date was CURRENT / AVAILABLE with no
    calendar at all (Ruling 5.3 item 2; coverage-gap table; Rulings 1.6 and 5.2: UNKNOWN maps to INSUFFICIENT_DATA)."""

    def assert_unknown(self, lk, fx=False, cause="CALENDAR_COVERAGE_GAP"):
        self.assertEqual(lk.outcome, LookupOutcome.FRESHNESS_UNKNOWN)
        self.assertIsNone(lk.rate if fx else lk.selected)
        self.assertEqual(state_of(lk, fx), (S.INSUFFICIENT_DATA, None))  # no reason code (Ruling 5.2 table, last row)
        self.assertTrue(any(cause in n for n in lk.lineage_notes), lk.lineage_notes)
        if fx:
            self.assertTrue(all(f.state is c.FreshnessState.UNKNOWN for f in lk.leg_freshness) or not lk.leg_freshness)
        else:
            self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)

    # -- prices ------------------------------------------------------------------------------------------------------

    def test_a_price_dated_the_as_of_date_with_no_calendar_in_m_is_unknown_not_current(self):
        # P1a: a USD close dated Sunday 2025-01-05 and no calendar: it used to be `FOUND CURRENT 0 AVAILABLE None 100.00`
        st = k.store([k.quote_reading(SUNDAY, "100.00")], mic="XNYS")
        lk = st.quote_on(k.LID, SUNDAY, market11_conventions(CalendarSet()))
        self.assert_unknown(lk)
        self.assertIn("no calendar in the market-data version governs XNYS", " ".join(lk.lineage_notes))

    def test_a_price_dated_the_as_of_date_outside_the_calendars_coverage_is_unknown_with_the_uncovered_date(self):
        # P1b: an NYSE calendar covering only January 2024: identical wrong output before, and no notes at all
        ny = k.exchange_calendar("NY", ("XNYS",), [D(2024, 1, 2), D(2024, 1, 3)], covers=(D(2024, 1, 1), D(2024, 1, 31)))
        st = k.store([k.quote_reading(SUNDAY, "100.00")], mic="XNYS")
        lk = st.quote_on(k.LID, SUNDAY, market11_conventions(CalendarSet([ny])))
        self.assert_unknown(lk)
        note = " ".join(lk.lineage_notes)
        self.assertIn("covers 2024-01-01..2024-01-31", note)
        self.assertIn("uncovered 2025-01-05..2025-01-05", note)

    def test_a_price_dated_a_non_session_inside_a_covering_calendar_is_unknown_off_calendar(self):
        # the covering calendar is COMPLETE inside its coverage (Ruling 5.3 item 4) and does not list Sunday the 5th
        ny = k.exchange_calendar("NY", ("XNYS",), [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        st = k.store([k.quote_reading(SUNDAY, "100.00")], mic="XNYS")
        lk = st.quote_on(k.LID, SUNDAY, market11_conventions(CalendarSet([ny])))
        self.assert_unknown(lk, cause="OFF_CALENDAR_DATE")

    def test_several_calendars_for_one_mic_are_also_unknown(self):
        a = k.exchange_calendar("NY_A", ("XNYS",), [D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)), sha="a" * 64)
        b = k.exchange_calendar("NY_B", ("XNYS",), [D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)), sha="b" * 64)
        st = k.store([k.quote_reading(D(2025, 1, 3), "100.00")], mic="XNYS")
        self.assert_unknown(st.quote_on(k.LID, D(2025, 1, 3), market11_conventions(CalendarSet([a, b]))))

    def test_with_one_governing_calendar_that_covers_and_lists_the_date_the_price_is_current(self):
        ny = k.exchange_calendar("NY", ("XNYS",), [D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        st = k.store([k.quote_reading(D(2025, 1, 3), "100.00")], mic="XNYS")
        lk = st.quote_on(k.LID, D(2025, 1, 3), market11_conventions(CalendarSet([ny])))
        self.assertEqual((lk.outcome, lk.missed_count, lk.freshness.state), (LookupOutcome.FOUND, 0, c.FreshnessState.CURRENT))
        self.assertEqual(state_of(lk), (S.AVAILABLE, None))
        self.assertIn(k.SHA2, {r.file_sha256 for r in lk.consumed})  # the calendar that vouched for it is cited

    # -- both FX legs ------------------------------------------------------------------------------------------------

    def fx_store(self, day):
        usd = k.fx_reading(day, "USD", "1.0810")
        hkd = k.fx_reading(day, "HKD", "8.4100")
        return k.store([usd, hkd], precedence=("ecb.eurofxref",))

    def test_a_fixing_dated_the_as_of_date_with_no_ecb_calendar_is_unknown_for_a_direct_rate_and_for_a_cross(self):
        st, conv = self.fx_store(SUNDAY), market11_conventions(CalendarSet())
        self.assert_unknown(st.fx_on(k.EUR, k.USD, SUNDAY, conv), fx=True)   # one leg: the published USD quote
        self.assert_unknown(st.fx_on(k.EUR, k.HKD, SUNDAY, conv), fx=True)   # the other leg alone
        cross = st.fx_on(k.HKD, k.USD, SUNDAY, conv)                           # both legs: x_USD / x_HKD
        self.assert_unknown(cross, fx=True)
        self.assertIsNone(cross.cross)

    def test_the_same_fixings_with_an_ecb_calendar_covering_only_another_year_are_unknown_too(self):
        ecb = k.ecb_calendar([D(2024, 1, 2), D(2024, 1, 3)], covers=(D(2024, 1, 1), D(2024, 1, 31)))
        self.assert_unknown(self.fx_store(SUNDAY).fx_on(k.HKD, k.USD, SUNDAY, market11_conventions(CalendarSet([ecb]))), fx=True)

    def test_a_fixing_dated_a_non_fixing_day_inside_the_ecb_calendar_is_unknown_off_calendar(self):
        ecb = k.ecb_calendar([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        # C2-14 (CP2 final round): an off-calendar fixing is excluded on EVERY as-of date (it used to be UNKNOWN here only);
        # with no earlier valid fixing the lookup has no history, with the cause in lineage
        lk = self.fx_store(SUNDAY).fx_on(k.HKD, k.USD, SUNDAY, market11_conventions(CalendarSet([ecb])))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))
        self.assertTrue(any("OFF_CALENDAR_DATE" in n for n in lk.lineage_notes), lk.lineage_notes)

    def test_with_an_ecb_calendar_that_covers_and_lists_the_fixing_both_legs_are_current(self):
        ecb = k.ecb_calendar([D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        lk = self.fx_store(D(2025, 1, 3)).fx_on(k.HKD, k.USD, D(2025, 1, 3), market11_conventions(CalendarSet([ecb])))
        self.assertEqual((lk.outcome, lk.missed_count, lk.rate), (LookupOutcome.FOUND, 0, Fraction(10810, 84100)))  # 1.0810 / 8.4100
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, None))

    # -- through the real build path (P1b-build) ---------------------------------------------------------------------

    def build_sunday_world(self, with_calendars):
        """The exit kit's "formats" world with its AAPL row and its ECB fixing moved to Sunday 2025-01-05."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        x.write_registry(root)
        specs, adapters = x.world_specs("formats")
        out = []
        for spec in specs:
            if spec["source_id"] == x.SRC_CAL and not with_calendars:
                continue  # the reviewer's probe removed the calendar files
            if spec["source_id"] == x.SRC_US:
                spec = dict(spec, payload=x.av_us_csv([(SUNDAY, "151.10", 1200)]))
            if spec["source_id"] == x.SRC_ECB:
                spec = dict(spec, payload=k.ecb_csv([(SUNDAY.isoformat(), ["1.0810", "8.4100", "7.8100"])], ["USD", "HKD", "CNY"]))
            out.append(spec)
        manifests = [kit.write_file(root, **spec) for spec in out]
        release = MarketDataRelease.from_manifests("c2-1", manifests, [])
        files = FileStore(root)
        ident = x.identity()
        return build_in_memory_market_data(release, files, files.load_registry(), adapters, ident, catalog_calendars={}), ident

    def test_the_build_path_with_no_calendar_files_gives_unknown_for_the_price_and_both_crosses(self):
        built, ident = self.build_sunday_world(with_calendars=False)
        self.assertEqual({r.status for r in built.label_results if r.test == "V0"}, {c.LabelStatus.UNVERIFIABLE})
        conv = market11_conventions(built.calendars)
        aapl = built.store.quote_on(x.lid(ident, "AAPL", "XNAS"), SUNDAY, conv)
        self.assert_unknown(aapl)  # it was `FOUND (2025-01-05, 151.1000) AVAILABLE`
        for ccy in (k.HKD, k.CNY):  # both FX crosses were `FOUND ... AVAILABLE`
            self.assert_unknown(built.store.fx_on(ccy, k.USD, SUNDAY, conv), fx=True)

    def test_the_build_path_with_calendar_files_catches_the_sunday_series_at_v0_and_the_fixing_off_calendar(self):
        built, ident = self.build_sunday_world(with_calendars=True)  # the kit's calendars list 2, 3, 6, 7 January
        v0 = [r for r in built.label_results if r.test == "V0" and r.listing_id == x.lid(ident, "AAPL", "XNAS")]
        self.assertEqual([(r.status, r.admitted) for r in v0], [(c.LabelStatus.CONTRADICTED, False)])
        conv = market11_conventions(built.calendars)
        aapl = built.store.quote_on(x.lid(ident, "AAPL", "XNAS"), SUNDAY, conv)
        self.assertEqual(state_of(aapl), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))  # dropped: no value, no CURRENT
        lk = built.store.fx_on(k.HKD, k.USD, SUNDAY, conv)  # C2-14: excluded, no earlier fixing: no history (was UNKNOWN)
        # 1.7 (C2-16): the whole ECB series (one Sunday row) is excluded at build, so the pair has no series at all
        self.assertEqual((lk.outcome, state_of(lk, fx=True)), (LookupOutcome.NOT_IN_RELEASE, (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY)))
        self.assertTrue(any("V0_FX_OFF_CALENDAR" in n for n in lk.lineage_notes), lk.lineage_notes)


# --- calendars: the linking window (Ruling 6.4a item 1) -----------------------------------------------------------------

class SessionWindowTests(unittest.TestCase):
    """`CalendarSet.session_window`: the 20th session before to the 20th session after a date, in the governing calendar."""

    @staticmethod
    def weekdays(first, last):
        out, day = [], first
        while day <= last:
            if day.weekday() < 5:
                out.append(day)
            day += datetime.timedelta(days=1)
        return out

    def calendars(self, first=D(2024, 6, 3), last=D(2026, 6, 30)):
        return CalendarSet([k.exchange_calendar("T", ("XTST",), self.weekdays(first, last), covers=(first, last))])

    def test_the_window_of_monday_3_february_2025_is_6_january_to_3_march(self):
        # by hand, every weekday a session: before 3 Feb: Jan 31..27 = 5, 24..20 = 10, 17..13 = 15, 10..6 = 20 -> 6 Jan;
        # after: Feb 4..7 = 4, 10..14 = 9, 17..21 = 14, 24..28 = 19, Mar 3 = 20 -> 3 Mar
        w = self.calendars().session_window("XTST", D(2025, 2, 3), 20)
        self.assertEqual((w.start, w.end, w.evaluable), (D(2025, 1, 6), D(2025, 3, 3), True))
        self.assertTrue(w.contains(D(2025, 1, 6)) and w.contains(D(2025, 3, 3)))   # a CLOSED interval
        self.assertFalse(w.contains(D(2025, 1, 3)) or w.contains(D(2025, 3, 4)))   # one session outside is outside

    def test_a_date_that_is_not_a_session_still_has_a_window(self):
        # Saturday 1 Feb 2025: before it Jan 31..27 = 5, 24..20 = 10, 17..13 = 15, 10..6 = 20 -> 6 Jan; after it Feb 3..7 = 5,
        # 10..14 = 10, 17..21 = 15, 24..28 = 20 -> 28 Feb
        w = self.calendars().session_window("XTST", D(2025, 2, 1), 20)
        self.assertEqual((w.start, w.end), (D(2025, 1, 6), D(2025, 2, 28)))

    def test_a_window_the_calendar_does_not_cover_cannot_be_evaluated_and_says_why(self):
        for cal, day in ((self.calendars(D(2025, 1, 20), D(2025, 2, 14)), D(2025, 2, 3)),   # too few sessions each side
                         (self.calendars(), D(2026, 12, 1)),                                   # the date itself is uncovered
                         (self.calendars(D(2025, 1, 6), D(2026, 6, 30)), D(2025, 1, 20))):     # 10 sessions before only
            w = cal.session_window("XTST", day, 20)
            self.assertFalse(w.evaluable)
            self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in w.notes), w.notes)
        none = CalendarSet().session_window("XTST", D(2025, 2, 3), 20)
        self.assertEqual((none.evaluable, none.notes[0].startswith("CALENDAR_COVERAGE_GAP")), (False, True))
        self.assertFalse(self.calendars().session_window(None, D(2025, 2, 3), 20).evaluable)  # the MIC is unknown


# --- C2-9 --------------------------------------------------------------------------------------------------------------

class C2_9_RefutedFileDateSetCheckInBothDirections(unittest.TestCase):
    """Ruling 1.1a item 6 as clarified in 1.4. ECB-direct (E) and Frankfurter (F) files cover 2025-01-02..08 and 7 January is a
    fixing day. A REFUTED file takes part in the date-set check in BOTH directions: a date that only one of them holds
    inside both coverages is a DISAGREEMENT with no rate and no carry-forward over it. Before the fix, F holding the date
    and E lacking it gave `FOUND date_used 2025-01-06, missed 1, AVAILABLE + STALE_DATA`, while the mirror case gave
    `INSUFFICIENT_DATA + SOURCE_CONFLICT` (probe P5)."""

    E, F = "e" * 64, "f" * 64
    FIXINGS = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)]
    ALL = FIXINGS
    WINDOWS = {"e" * 64: FXFileWindow(None, D(2025, 1, 8)), "f" * 64: FXFileWindow(D(2025, 1, 2), D(2025, 1, 8))}

    def conv(self):
        return market11_conventions(CalendarSet([k.ecb_calendar(self.FIXINGS, covers=(D(2025, 1, 1), D(2025, 1, 31)))]))

    def look(self, ecb_days, frank_days, windows=None, day=D(2025, 1, 7)):
        rate = lambda d: "1.08%02d" % d.day  # noqa: E731  a distinct, equal-in-both-files value per date
        readings = [k.fx_reading(d, "USD", rate(d), source="ecb.eurofxref", sha=self.E) for d in ecb_days]
        readings += [k.fx_reading(d, "USD", rate(d), source="frankfurter.ecb", sha=self.F, provenance="REFUTED") for d in frank_days]
        st = k.store(readings, precedence=("ecb.eurofxref", "frankfurter.ecb"), fx_windows=windows or self.WINDOWS)
        return st.fx_on(k.EUR, k.USD, day, self.conv())

    def test_a_date_only_the_refuted_file_holds_is_a_source_conflict_not_a_carried_forward_rate(self):
        # E lacks 7 January, F (REFUTED) holds it
        lk = self.look([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 8)], self.ALL)
        self.assertEqual((lk.outcome, lk.rate, lk.date_used), (LookupOutcome.NO_SELECTION, None, None))
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.DISAGREEMENT)
        self.assertTrue(any("1.1a item 6" in f for f in lk.reconciliation.flags), lk.reconciliation.flags)

    def test_the_mirror_case_a_date_only_the_publishers_file_holds_is_the_same_source_conflict(self):
        lk = self.look(self.ALL, [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 8)])
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NO_SELECTION, None))
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))

    def test_both_directions_give_one_and_the_same_state(self):
        a = self.look([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 8)], self.ALL)
        b = self.look(self.ALL, [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 8)])
        self.assertEqual((a.outcome, state_of(a, fx=True)), (b.outcome, state_of(b, fx=True)))

    def test_no_rate_is_carried_forward_over_the_conflicted_date_to_a_later_as_of(self):
        # as of 8 January both files hold the 8th: the 8th resolves; as of the 7th it is withheld (above). The conflict is
        # about the 7th only, and the 8th is not made unusable by it
        ecb = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 8)]
        lk = self.look(ecb, self.ALL, day=D(2025, 1, 8))
        self.assertEqual((lk.outcome, lk.date_used, lk.rate), (LookupOutcome.FOUND, D(2025, 1, 8), Fraction(10808, 10000)))

    def test_a_refuted_only_date_outside_the_publishers_coverage_is_not_a_conflict_and_the_earlier_fixing_is_carried(self):
        # E was retrieved before the 7th was published: its coverage ends 6 January, so its lack of the 7th is no mismatch
        # inside both coverages; F's 7th is a refuted rate and supplies none: the 6th is carried forward, 1 missed
        windows = {"e" * 64: FXFileWindow(None, D(2025, 1, 6)), "f" * 64: FXFileWindow(D(2025, 1, 2), D(2025, 1, 8))}
        lk = self.look([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], self.ALL, windows)
        self.assertEqual((lk.outcome, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, D(2025, 1, 6), 1))
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, R.STALE_DATA))

    def test_with_no_coverage_window_the_date_set_part_does_not_run_and_nothing_is_invented(self):
        lk = self.look([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], self.ALL, windows={"e" * 64: FXFileWindow(None, None),
                                                                                         "f" * 64: FXFileWindow(None, None)})
        self.assertEqual((lk.outcome, lk.date_used), (LookupOutcome.FOUND, D(2025, 1, 6)))


# --- C2-10: the CN security class ----------------------------------------------------------------------------------------

class C2_10_CnSecurityClassFromMicTypeAndCurrency(unittest.TestCase):
    """Appendix A.1 (1.4): the class is derived from (MIC, SecurityType, trading currency); B-shares are identified by their
    currency, and any other combination is strict 2 decimals flagged SECURITY_CLASS_UNRESOLVED. Before the fix a
    `COMMON_STOCK` on a mainland exchange was always an A-share, and a refusal cited "A_SHARE"."""

    def build(self, rows):
        """rows: (ticker, mic, exchange, SecurityType, currency, close text)."""
        # RE-RECORDED for market-data/1.16 item 26: the Eastmoney profile (delivered_dp 2) now refuses a 3-decimal close at the profile check,
        # before the class grid is reached; this test is about the class grid, so it runs against a hypothetical wider profile (finding for the Quant)
        self.enterContext(gate_kit.delivered_dp("akshare.cn", 8))
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([InstrumentEntry(f"Issuer {t}", st, mic, exchange, t, ccy, vendor_ids=((idt.SRC_CN, t),))
                                  for t, mic, exchange, st, ccy, _ in rows])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SourceRecord(idt.SRC_CN, idt.SRC_CN, "synthetic", "synthetic.cn", synthetic=True)])
        manifests = [kit.write_file(root, idt.SRC_CN, DataKind.QUOTE, "akshare_csv_cn_daily/1", idt.eastmoney(t, close), t, "csv",
                                    currency=ccy, adjustment=c.AdjustmentStatus.RAW, source_identifiers=(t,),
                                    request=(("function", "stock_zh_a_hist"),), market="CN") for t, _, _, _, ccy, close in rows]
        files = FileStore(root)
        from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: PLC0415
        from marketdata.adapters.base import AdapterRegistry  # noqa: PLC0415

        built = build_in_memory_market_data(MarketDataRelease.from_manifests("cn", manifests, []), files, files.load_registry(),
                                            AdapterRegistry([AkshareCnQuoteAdapter(idt.SRC_CN)]), reg, catalog_calendars={})
        return built, reg

    def look(self, built, reg, ticker, mic):
        cal = k.exchange_calendar("SSE", ("XSHG", "XSHE"), [D(2025, 1, 2), D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        return built.store.quote_on(kit.listing_id(reg, ticker, mic), D(2025, 1, 3), market11_conventions(CalendarSet([cal])))

    def test_each_row_of_the_table_decides_the_grid_of_its_own_listing(self):
        CS, ETF = SecurityType.COMMON_STOCK, SecurityType.ETF
        # every close is 1.234 / 4.123 (3 decimals): on the grid of 3-decimal classes only (hand-checked against A.1)
        built, reg = self.build([
            ("600001", "XSHG", "SSE", CS, k.CNY, "1.234"),      # A_SHARE, 2 dp: NOT recovered
            ("510001", "XSHG", "SSE", ETF, k.CNY, "4.123"),     # FUND_ETF_LOF_BOND, 3 dp: recovered
            ("900901", "XSHG", "SSE", CS, k.USD, "1.234"),      # B_SHARE_SSE (USD on XSHG), 3 dp: recovered
            ("200012", "XSHE", "SZSE", CS, k.HKD, "1.234"),     # B_SHARE_SZSE (HKD on XSHE), 2 dp: NOT recovered
            ("000001", "XSHE", "SZSE", CS, k.CNY, "1.23"),      # A_SHARE, 2 dp: recovered
        ])
        recovered = {t: self.look(built, reg, t, mic).outcome is LookupOutcome.FOUND
                     for t, mic in (("600001", "XSHG"), ("510001", "XSHG"), ("900901", "XSHG"), ("200012", "XSHE"), ("000001", "XSHE"))}
        self.assertEqual(recovered, {"600001": False, "510001": True, "900901": True, "200012": False, "000001": True})
        by_ref = {i.row_ref: i for _, i in built.issues if i.code is IssueCode.PRICE_NOT_RECOVERED}
        self.assertIn("security class A_SHARE", by_ref["600001@2025-01-03"].detail)
        self.assertIn("security class B_SHARE_SZSE", by_ref["200012@2025-01-03"].detail)  # the B-share refusal names ITS class
        self.assertEqual([i for _, i in built.issues if i.code is IssueCode.SECURITY_CLASS_UNRESOLVED], [])

    def test_any_other_combination_is_strict_two_decimals_and_flagged_security_class_unresolved(self):
        CS, ETF = SecurityType.COMMON_STOCK, SecurityType.ETF
        built, reg = self.build([
            ("600002", "XSHG", "SSE", CS, k.HKD, "1.234"),   # a HKD stock on XSHG: not in the table
            ("510002", "XSHE", "SZSE", ETF, k.USD, "1.23"),  # an ETF in USD: not in the table (a 2 dp close passes strict 2)
        ])
        self.assertEqual(self.look(built, reg, "600002", "XSHG").outcome, LookupOutcome.NO_HISTORY)  # strict 2 dp refuses 1.234
        self.assertEqual(self.look(built, reg, "510002", "XSHE").outcome, LookupOutcome.FOUND)       # 1.23 is on the strict grid
        unresolved = [i for _, i in built.issues if i.code is IssueCode.SECURITY_CLASS_UNRESOLVED]
        self.assertEqual(sorted(i.row_ref for i in unresolved), ["510002@2025-01-03", "600002@2025-01-03"])  # one per listing
        (refused,) = [i for _, i in built.issues if i.code is IssueCode.PRICE_NOT_RECOVERED]
        self.assertIn("SECURITY_CLASS_UNRESOLVED", refused.detail)


# --- C2-10: the stored precision bound (section 9C item 6) ---------------------------------------------------------------

class PrecisionBoundForStorageTests(unittest.TestCase):
    """A bound with at most 100 decimals is stored exactly; one with more is rounded toward +infinity (never down, never
    refused). Exact decimal expansions of 2^-k have k decimals. (The database half is in the PostgreSQL tests.)"""

    def test_a_bound_of_at_most_100_decimals_is_unchanged(self):
        for text in ("0", "0.5", "1E-100", "0.0000000000000000001"):
            d = Decimal(text)
            self.assertEqual(mds.bound_for_storage(d).as_tuple(), d.as_tuple(), text)
        two_pow_100 = Decimal((0, tuple(int(ch) for ch in str(5 ** 100)), -100))  # 2^-100: 100 decimals, exactly
        self.assertEqual(mds.bound_for_storage(two_pow_100).as_tuple(), two_pow_100.as_tuple())
        self.assertEqual(Fraction(two_pow_100), Fraction(1, 2 ** 100))

    def test_a_bound_beyond_100_decimals_is_rounded_up_never_down(self):
        cases = {
            "1E-101": Fraction(1, 10 ** 100),  # the smallest 100-decimal value at or above it
            "2^-120": Fraction(math.ceil(Fraction(1, 2 ** 120) * 10 ** 100), 10 ** 100),
            "2^-200": Fraction(math.ceil(Fraction(1, 2 ** 200) * 10 ** 100), 10 ** 100),
        }
        for name, expected in cases.items():
            if name.startswith("2^-"):
                k_ = int(name[3:])
                bound = Decimal((0, tuple(int(ch) for ch in str(5 ** k_)), -k_))
            else:
                bound = Decimal(name)
            stored = mds.bound_for_storage(bound)
            self.assertEqual(Fraction(stored), expected, name)
            self.assertGreaterEqual(Fraction(stored), Fraction(bound), name)
            self.assertLessEqual(-stored.as_tuple().exponent, 100, name)

    def test_trailing_zeros_beyond_100_decimals_do_not_change_the_value(self):
        padded = Decimal("0.5" + "0" * 119)  # 120 stored decimals, exactly one half
        stored = mds.bound_for_storage(padded)
        self.assertEqual(Fraction(stored), Fraction(1, 2))
        self.assertLessEqual(-stored.as_tuple().exponent, 100)


# --- C2-4 --------------------------------------------------------------------------------------------------------------

class C2_4_IdentityChecksTheExchangeAgainstTheListingsMic(unittest.TestCase):
    """Ruling 7.2 item 3 and PD-0021 section 1: FIGI identity is on the SAME MIC. The reviewer's probe P6: an XNAS listing
    `OLD` with no stored FIGI and an assertion (BBGLONDON001, OLD, LN) was RESOLVED and the London FIGI was added to the XNAS
    listing; two `LN` assertions sharing one FIGI then CONFIRMED a symbol change on it."""

    LONDON = "BBGLONDON001"
    EFFECTIVE = D(2025, 3, 3)

    def registry(self, codes=None, code_table=None):
        reg = InMemoryIdentityRegistry(kit.SequentialIds(), exchange_codes=codes, code_table=code_table)
        reg.register_instruments([InstrumentEntry("Old Name Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "OLD", k.USD,
                                                  valid_from=D(2020, 1, 1))])  # NO stored FIGI
        return reg, kit.listing_id(reg, "OLD", "XNAS")

    @staticmethod
    def assertion(figi, ticker, exch):
        # C2-17 (CP2 final check): an exchange-level record needs a security type to attach, so these carry one
        return c.IdentityAssertion(figi, ticker, exch, c.SourceTiming(), k.lineage("synthetic.figi", k.SHA),
                                   security_type="Common Stock")

    def test_a_figi_from_another_exchange_is_not_attached_and_is_quarantined(self):
        reg, lid = self.registry({"XNAS": ("US",)})
        ((a, res, added),) = reg.apply_identity_assertions([self.assertion(self.LONDON, "OLD", "LN")])
        self.assertEqual((added, res.status, res.listing_id), ((), c.ResolutionStatus.CONFLICT, None))  # was RESOLVED + 1 FIGI
        self.assertEqual([r.scheme for r in reg.identifier_rows(lid)], ["TICKER"])  # no FIGI row was planted
        (q,) = reg.assertion_quarantine()
        self.assertEqual((q.verdict, q.listing_id, q.assertion), ("EXCHANGE_MISMATCH", lid, a))
        self.assertIn("evidence from another venue", q.reason)

    def test_two_assertions_on_another_exchange_do_not_confirm_a_symbol_change(self):
        reg, lid = self.registry({"XNAS": ("US",)})
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [self.assertion(self.LONDON, "OLD", "LN"),
                                                                          self.assertion(self.LONDON, "NEW", "LN")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.QUARANTINED, False))  # was CONFIRMED True
        self.assertEqual(reg.listing(lid).ticker, "OLD")  # the XNAS listing's ticker did not become NEW
        self.assertEqual(reg.quarantine(), (decision,))

    def test_without_a_mic_to_exchange_code_mapping_nothing_is_attached_and_nothing_is_confirmed(self):
        # 1.5: the default table is A.6, whose XNAS codes UQ and UR are MEMORY: a MEMORY entry does not attach (Ruling 7.3
        # item 6), so the exchange cannot be proved to be the MIC (this test used "no mapping at all", the 1.4 empty table).
        # Re-recorded 2026-10-25 (F1 R4a, market-data/1.16 A.6, PD-0066 decision 4): the code used here was UW, which is OBSERVED
        # since 1.16 and attaches; it is UQ now, a code that is still MEMORY, so the test keeps what it was written to show.
        reg, lid = self.registry()
        ((_, res, added),) = reg.apply_identity_assertions([self.assertion("BBG000AAAAA1", "OLD", "UQ")])
        self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))
        self.assertEqual(reg.assertion_quarantine()[0].verdict, "EXCHANGE_UNVERIFIABLE")
        self.assertIn("status MEMORY", reg.assertion_quarantine()[0].reason)
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [self.assertion("BBG000AAAAA1", "OLD", "UQ"),
                                                                          self.assertion("BBG000AAAAA1", "NEW", "UQ")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.UNCONFIRMED, False))
        self.assertIn("status MEMORY", decision.reason)
        # a MIC the table does not know at all is the same
        other, other_lid = self.registry(code_table=A6_WITHOUT_XNAS)
        self.assertEqual(other.propose_symbol_change(other_lid, "NEW", self.EFFECTIVE, [self.assertion("BBG000AAAAA1", "OLD", "UQ"),
                         self.assertion("BBG000AAAAA1", "NEW", "UQ")]).status, SymbolChangeStatus.UNCONFIRMED)

    def test_the_planted_figi_cannot_then_make_a_later_confirmation_look_consistent(self):
        # the reviewer's note: "the stored-FIGI guard does not help, because the first call can plant the wrong FIGI"
        reg, lid = self.registry({"XNAS": ("US",)})
        reg.apply_identity_assertions([self.assertion(self.LONDON, "OLD", "LN")])
        self.assertEqual([r for r in reg.identifier_rows(lid) if r.scheme == "FIGI"], [])
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [self.assertion(self.LONDON, "OLD", "LN"),
                                                                          self.assertion(self.LONDON, "NEW", "LN")])
        self.assertFalse(decision.applied)

    def test_the_same_venue_still_works(self):
        reg, lid = self.registry({"XNAS": ("US",)})
        ((_, res, added),) = reg.apply_identity_assertions([self.assertion("BBG000AAAAA1", "OLD", "US")])
        self.assertEqual((res.status, added), (c.ResolutionStatus.RESOLVED, ("FIGI",)))
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [self.assertion("BBG000AAAAA1", "OLD", "US"),
                                                                          self.assertion("BBG000AAAAA1", "NEW", "US")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.CONFIRMED, True))
        self.assertEqual(reg.assertion_quarantine(), ())


# --- C2-12 / C2-13 ----------------------------------------------------------------------------------------------------

class SpyAdapter:
    """Records whether `translate` was reached: the terms and profile gates must refuse BEFORE the payload is parsed."""

    adapter_version = "0.0.1"
    payload_formats = ("spy/1",)

    def __init__(self, source_id, kind):
        self.source_id, self.data_kind, self.adapter_id, self.calls = source_id, kind, f"{source_id}.spy", 0

    def translate(self, manifest, payload):
        self.calls += 1
        return AdapterOutput()


class C2_12_13_AdmissionAndTheTermsGateInsideIngestFile(unittest.TestCase):
    def verified(self, record, kind=DataKind.QUOTE):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[record])
        manifest = kit.write_file(root, record.source_id, kind, "spy/1", b"payload", "p", "bin",
                                  usage_scope=c.UsageScope.SYNTHETIC_TEST if record.synthetic else c.UsageScope.INTERNAL_DEVELOPMENT_ONLY,
                                  currency=k.USD, retrieved_by="human")
        files = FileStore(root)
        return files.read_verified(files.index()[manifest.file_sha256]), files.load_registry().get(record.source_id)

    ATTESTED = TermsCheck("owner", D(2026, 10, 1), True)

    def test_c2_13_ingest_file_itself_refuses_a_source_without_an_attestation_before_parsing(self):
        for name, terms in (("no check at all", None), ("a negative check", TermsCheck("owner", D(2026, 10, 1), False))):
            record = SourceRecord("alphavantage.us", "AV", "alphavantage", "alphavantage", terms_check=terms)
            verified, source = self.verified(record)
            spy = SpyAdapter("alphavantage.us", DataKind.QUOTE)
            with self.assertRaises(SourceTermsNotAttestedError, msg=name):
                ingest_file(verified, spy, idt.us_registry()[0], source)  # the build path is NOT involved
            self.assertEqual(spy.calls, 0, name)  # the payload was never parsed

    def test_c2_13_a_synthetic_source_is_exempt_and_an_attested_one_passes_the_gate(self):
        for record in (SourceRecord("synthetic.q", "q", "synthetic", "synthetic.q", synthetic=True),
                       SourceRecord("alphavantage.us", "AV", "alphavantage", "alphavantage", terms_check=self.ATTESTED)):
            verified, source = self.verified(record)
            spy = SpyAdapter(record.source_id, DataKind.QUOTE)
            ingest_file(verified, spy, idt.us_registry()[0], source)
            self.assertEqual(spy.calls, 1, record.source_id)

    def test_c2_12_an_attested_but_refused_profile_is_not_admitted_for_real_data(self):
        # attested terms are not enough: the profile's `refused` flag (PD-0031/0032) is enforced, before the payload is parsed
        record = SourceRecord("akshare.cn", "AKShare CN", "eastmoney", "eastmoney", terms_check=self.ATTESTED)
        verified, source = self.verified(record)
        spy = SpyAdapter("akshare.cn", DataKind.QUOTE)
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            ingest_file(verified, spy, idt.us_registry()[0], source)
        self.assertIn("REFUSED", str(cm.exception))
        self.assertEqual(spy.calls, 0)

    def test_c2_12_an_attested_memory_profile_is_not_admitted_for_real_data_until_profiled(self):
        record = SourceRecord("ecb.eurofxref", "ECB", "ecb", "ecb", terms_check=self.ATTESTED)  # profile status MEMORY
        verified, source = self.verified(record, DataKind.FX)
        spy = SpyAdapter("ecb.eurofxref", DataKind.FX)
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            ingest_file(verified, spy, idt.us_registry()[0], source)
        self.assertIn("MEMORY", str(cm.exception))
        self.assertEqual(spy.calls, 0)


if __name__ == "__main__":
    unittest.main()
