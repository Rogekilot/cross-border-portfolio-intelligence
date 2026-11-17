"""market-data/1.2 rules over calendars: freshness (Ruling 5.2, Example 5-A), calendar coverage gaps
(Ruling 5.3), price of date (Rulings 2.1, 2.2, 2.4 item 4a), FX (Rulings 1.1, 1.3-1.6, Examples 1-A and
1-B, Ruling 1.1a), the market with no admitted source (4.7), synthetic data (4.8) and conformance.

Every expected value is derived by hand from the inputs shown, or is a figure of the Quant's worked
examples (cited). No expected value is read from the code under test."""

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

from marketdata import contracts as c  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.conventions import placeholder_conventions  # noqa: E402
from marketdata.market11 import (  # noqa: E402
    UNBUILT,
    market11_conventions,
    market11_conventions_with_injected_parity_for_tests,
)
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from marketdata.store import FXFileWindow  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S = SufficiencyState
R = ReasonCode
REAL = c.UsageScope.INTERNAL_DEVELOPMENT_ONLY


def state_of(lookup, fx=False):
    st = (fx_input_state if fx else price_input_state)(lookup)
    return st.state, st.reason


class Example5ATests(unittest.TestCase):
    """Example 5-A: an A-share across a holiday. Assumed C_XSHG: sessions 28, 29, 30 Apr; closed 1-5 May;
    sessions 6, 7, 8, 9, 12 May. Last print 30 Apr."""

    SESSIONS = [D(2025, 4, 28), D(2025, 4, 29), D(2025, 4, 30), D(2025, 5, 6), D(2025, 5, 7), D(2025, 5, 8),
                D(2025, 5, 9), D(2025, 5, 12)]

    def setUp(self):
        self.cal = k.exchange_calendar("SSE_SZSE", ("XSHG", "XSHE"), self.SESSIONS,
                                       covers=(D(2025, 4, 28), D(2025, 5, 12)))
        self.conv = market11_conventions(CalendarSet([self.cal]))
        self.store = k.store([k.quote_reading(D(2025, 4, 30), "100.00", ccy=k.CNY, source="x", group="x")], mic="XSHG")

    def look(self, day):
        return self.store.quote_on(k.LID, day, self.conv)

    def test_5_may_a_holiday_is_not_staleness(self):
        lk = self.look(D(2025, 5, 5))
        self.assertEqual((lk.outcome, lk.missed_count, lk.freshness.state), (LookupOutcome.FOUND, 0, c.FreshnessState.CURRENT))
        self.assertEqual((lk.date_used, lk.selected.observation.price), (D(2025, 4, 30), Decimal("100.00")))
        self.assertEqual(state_of(lk), (S.AVAILABLE, None))

    def test_6_may_one_session_missed_is_available_with_stale_data(self):
        lk = self.look(D(2025, 5, 6))
        self.assertEqual((lk.outcome, lk.missed_count, lk.freshness.state), (LookupOutcome.FOUND, 1, c.FreshnessState.STALE))
        self.assertEqual(state_of(lk), (S.AVAILABLE, R.STALE_DATA))

    def test_9_may_four_sessions_missed_is_limited_with_stale_data(self):
        lk = self.look(D(2025, 5, 9))
        self.assertEqual((lk.outcome, lk.missed_count), (LookupOutcome.FOUND, 4))
        self.assertEqual(state_of(lk), (S.LIMITED, R.STALE_DATA))

    def test_12_may_five_sessions_missed_withholds_the_number(self):
        lk = self.look(D(2025, 5, 12))
        self.assertEqual((lk.outcome, lk.selected, lk.missed_count, lk.date_used),
                         (LookupOutcome.STALE_BEYOND_LIMIT, None, 5, None))
        self.assertIs(lk.freshness.state, c.FreshnessState.STALE)
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.STALE_DATA))  # a print exists: not MISSING_PRICE_HISTORY
        self.assertEqual(len(lk.readings), 1)  # the reading stays in lineage; it is not the value used

    def test_the_calendar_file_is_part_of_the_lineage_of_the_result(self):
        lk = self.look(D(2025, 5, 6))
        self.assertIn(k.SHA2, {r.file_sha256 for r in lk.consumed})  # the exact calendar file that was counted

    def test_a_print_dated_the_as_of_date_is_current_only_when_a_governing_calendar_covers_that_date(self):
        # C2-1 (CP2 review of 39733e9; Rulings 5.3, 1.6, 5.2): this test used to say "needs no calendar". An empty
        # interval (last print = as-of) is CURRENT only when ONE calendar governs the MIC and covers the date; with none
        # the count cannot be made: UNKNOWN, INSUFFICIENT_DATA, no reason code, cause CALENDAR_COVERAGE_GAP.
        bare = k.store([k.quote_reading(D(2025, 4, 30), "100.00")], mic="XNYS")
        lk = bare.quote_on(k.LID, D(2025, 4, 30), market11_conventions(CalendarSet()))
        self.assertEqual((lk.outcome, lk.selected, lk.freshness.state),
                         (LookupOutcome.FRESHNESS_UNKNOWN, None, c.FreshnessState.UNKNOWN))
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, None))
        self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in lk.lineage_notes), lk.lineage_notes)
        ny = k.exchange_calendar("NY", ("XNYS",), [D(2025, 4, 29), D(2025, 4, 30)], covers=(D(2025, 4, 28), D(2025, 4, 30)))
        covered = bare.quote_on(k.LID, D(2025, 4, 30), market11_conventions(CalendarSet([ny])))
        self.assertEqual((covered.outcome, covered.missed_count, covered.freshness.state),
                         (LookupOutcome.FOUND, 0, c.FreshnessState.CURRENT))
        self.assertIn(k.SHA2, {r.file_sha256 for r in covered.consumed})  # the calendar that vouched for it is in lineage


class CoverageGapTests(unittest.TestCase):
    """Ruling 5.3: an interval not wholly inside the coverage cannot be counted. Freshness UNKNOWN, the number
    is withheld, INSUFFICIENT_DATA with NO reason code, cause CALENDAR_COVERAGE_GAP in lineage. Never weekdays."""

    def conv(self, *calendars):
        return market11_conventions(CalendarSet(calendars))

    def cal(self, **kw):
        return k.exchange_calendar("NY", ("XNYS",), [D(2025, 4, 28), D(2025, 4, 29), D(2025, 4, 30)],
                                   covers=(D(2025, 4, 28), D(2025, 4, 30)), **kw)

    def look(self, day, conv, print_day=D(2025, 4, 28), mic="XNYS"):
        return k.store([k.quote_reading(print_day, "10.00")], mic=mic).quote_on(k.LID, day, conv)

    def test_an_interval_past_the_end_of_the_coverage_is_unknown_and_names_the_uncovered_dates(self):
        lk = self.look(D(2025, 5, 2), self.conv(self.cal()))
        self.assertEqual((lk.outcome, lk.selected, lk.missed_count), (LookupOutcome.FRESHNESS_UNKNOWN, None, None))
        self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)
        self.assertEqual(len(lk.lineage_notes), 1)
        self.assertIn("CALENDAR_COVERAGE_GAP", lk.lineage_notes[0])
        self.assertIn("uncovered 2025-05-01..2025-05-02", lk.lineage_notes[0])
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, None))  # no reason code: a configuration gap

    def test_an_interval_before_the_start_of_the_coverage_is_unknown(self):
        lk = self.look(D(2025, 4, 30), self.conv(self.cal()), print_day=D(2025, 4, 20))
        self.assertEqual(lk.outcome, LookupOutcome.FRESHNESS_UNKNOWN)
        self.assertIn("uncovered 2025-04-21..2025-04-27", lk.lineage_notes[0])

    def test_no_calendar_for_the_mic_two_calendars_for_the_mic_and_an_unknown_exchange_are_all_unknown(self):
        other = k.exchange_calendar("NY2", ("XNYS",), [D(2025, 4, 28), D(2025, 4, 30)], sha=k.SHA)
        cases = (
            (self.look(D(2025, 4, 30), self.conv(self.cal()), mic="XHKG"), "no calendar in the market-data version governs XHKG"),
            (self.look(D(2025, 4, 30), self.conv(self.cal(), other)), "2 calendars govern XNYS"),
            (self.look(D(2025, 4, 30), self.conv(self.cal()), mic=None), "the listing's exchange is not known"),
        )
        for lk, text in cases:
            self.assertEqual(lk.outcome, LookupOutcome.FRESHNESS_UNKNOWN, text)
            self.assertIn(text, lk.lineage_notes[0])
            self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, None))

    def test_a_count_past_actual_through_is_made_and_says_so_with_no_state_effect(self):
        scheduled = self.cal(actual_through=D(2025, 4, 28))
        lk = self.look(D(2025, 4, 30), self.conv(scheduled))
        self.assertEqual((lk.outcome, lk.missed_count), (LookupOutcome.FOUND, 2))  # {29, 30}
        self.assertIn("COUNTED_PAST_ACTUAL_THROUGH", lk.lineage_notes[0])
        self.assertEqual(state_of(lk), (S.LIMITED, R.STALE_DATA))
        checked = self.look(D(2025, 4, 30), self.conv(self.cal()))  # actual_through = coverage end
        self.assertEqual((checked.missed_count, checked.lineage_notes), (2, ()))

    def test_weekdays_are_never_inferred(self):
        # 2025-04-29 is a Tuesday that the calendar does NOT list: it is no session, and nothing fills it
        cal = k.exchange_calendar("NY", ("XNYS",), [D(2025, 4, 28), D(2025, 4, 30)], covers=(D(2025, 4, 28), D(2025, 4, 30)))
        lk = self.look(D(2025, 4, 30), self.conv(cal))
        self.assertEqual(lk.missed_count, 1)  # only the 30th


class PriceOfDateTests(unittest.TestCase):
    CAL = None

    def setUp(self):
        days = [D(2025, 4, 28), D(2025, 4, 29), D(2025, 4, 30)]
        self.conv = market11_conventions(CalendarSet([k.exchange_calendar("NY", ("XNYS",), days)]))

    def look(self, readings, day=D(2025, 4, 30), listing=k.LID):
        return k.store(readings).quote_on(listing, day, self.conv)

    def test_a_zero_volume_row_is_not_a_print_and_the_session_counts_as_missed(self):
        lk = self.look([k.quote_reading(D(2025, 4, 29), "50.00", "100"), k.quote_reading(D(2025, 4, 30), "50.00", "0")])
        self.assertEqual((lk.outcome, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, D(2025, 4, 29), 1))
        self.assertEqual(state_of(lk), (S.AVAILABLE, R.STALE_DATA))

    def test_a_row_with_no_reported_volume_is_not_a_print(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.00", None)])
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))

    def test_an_unrecovered_reading_is_not_an_admissible_print_it_counts_as_missed(self):
        lk = self.look([k.quote_reading(D(2025, 4, 29), "50.00", "100"),
                        k.quote_reading(D(2025, 4, 30), "50.1234", "100", recovered=False, bound="0.00005")])
        self.assertEqual((lk.outcome, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, D(2025, 4, 29), 1))
        self.assertEqual(lk.selected.observation.price, Decimal("50.00"))

    def test_only_unrecovered_readings_means_no_admissible_print_and_missing_price_history(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.1234", "100", recovered=False, bound="0.00005")])
        self.assertEqual((lk.outcome, lk.selected, lk.reconciliation), (LookupOutcome.NO_HISTORY, None, None))
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))  # and no reconciliation status

    def test_no_print_on_or_before_the_date_is_missing_price_history_and_never_look_ahead(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.00")], day=D(2025, 4, 29))
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))

    def test_a_listing_is_valued_only_at_its_own_price_never_a_sibling_listing(self):
        sibling = k.quote_reading(D(2025, 4, 30), "999.00", listing=k.OTHER_LID)  # another listing, same issuer
        own_missing = self.look([sibling])
        self.assertEqual((own_missing.outcome, own_missing.selected), (LookupOutcome.NOT_IN_RELEASE, None))
        own = self.look([sibling, k.quote_reading(D(2025, 4, 29), "50.00")])
        self.assertEqual(own.selected.observation.price, Decimal("50.00"))  # not 999: no substitution

    def test_the_session_date_is_the_source_local_label_and_the_result_says_which_date_was_used(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.00")])
        self.assertEqual(lk.date_used, D(2025, 4, 30))
        text = (Path(__file__).resolve().parents[2] / "src" / "marketdata" / "market11.py").read_text(encoding="utf-8")
        for banned in ("astimezone", "utcfromtimestamp", "timezone.utc"):
            self.assertNotIn(banned, text)  # a date is never derived through UTC (Ruling 2.2)

    def test_two_readings_of_one_upstream_that_differ_are_a_disagreement_and_no_value(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.00", sha=k.SHA), k.quote_reading(D(2025, 4, 30), "50.01", sha=k.SHA2)])
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_SELECTION, None))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.DISAGREEMENT)
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))

    def test_two_readings_of_one_upstream_that_agree_are_single_source_and_a_value_is_used(self):
        lk = self.look([k.quote_reading(D(2025, 4, 30), "50.00", sha=k.SHA), k.quote_reading(D(2025, 4, 30), "50.0000", sha=k.SHA2)])
        self.assertEqual((lk.outcome, lk.reconciliation.status), (LookupOutcome.FOUND, c.ReconciliationStatus.SINGLE_SOURCE))


class Example1BTests(unittest.TestCase):
    """Example 1-B: Easter 2025. Fixing dates 14-17, 22-25, 28-30 Apr (21 Apr, Easter Monday, and 18 Apr are
    TARGET closing days). The rate of each fixing day dd is written 1.08dd so the date used is visible."""

    FIXINGS = [D(2025, 4, d) for d in (14, 15, 16, 17, 22, 23, 24, 25, 28, 29, 30)]
    CAL = k.ecb_calendar(FIXINGS, covers=(D(2025, 4, 1), D(2025, 4, 30)))

    def lookup(self, held_days, as_of):
        readings = [k.fx_reading(d, "USD", f"1.08{d.day:02d}") for d in held_days]
        conv = market11_conventions(CalendarSet([self.CAL]))
        return k.store(readings).fx_on(k.EUR, k.USD, as_of, conv)

    def held(self, *missing):
        return [d for d in self.FIXINGS if d.day not in missing]

    def test_i_saturday_19_april_uses_the_17th_and_is_current(self):
        lk = self.lookup(self.held(), D(2025, 4, 19))
        self.assertEqual((lk.outcome, lk.rate, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, Fraction(10817, 10000), D(2025, 4, 17), 0))
        self.assertIs(lk.leg_freshness[0].state, c.FreshnessState.CURRENT)
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, None))

    def test_ii_easter_monday_21_april_is_4_calendar_days_old_and_not_stale(self):
        lk = self.lookup(self.held(), D(2025, 4, 21))
        self.assertEqual((lk.date_used, lk.missed_count), (D(2025, 4, 17), 0))
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, None))

    def test_iii_one_missing_fixing_is_stale_but_available(self):
        lk = self.lookup(self.held(22), D(2025, 4, 22))
        self.assertEqual((lk.outcome, lk.rate, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, Fraction(10817, 10000), D(2025, 4, 17), 1))
        self.assertIs(lk.leg_freshness[0].state, c.FreshnessState.STALE)
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, R.STALE_DATA))

    def test_iv_two_missing_fixings_is_limited(self):
        lk = self.lookup(self.held(22, 23), D(2025, 4, 23))
        self.assertEqual((lk.outcome, lk.missed_count, lk.date_used), (LookupOutcome.FOUND, 2, D(2025, 4, 17)))
        self.assertEqual(state_of(lk, fx=True), (S.LIMITED, R.STALE_DATA))

    def test_v_five_missing_fixings_gives_no_rate_and_missing_fx_history(self):
        lk = self.lookup(self.held(22, 23, 24, 25, 28), D(2025, 4, 28))
        self.assertEqual((lk.outcome, lk.rate, lk.legs, lk.missed_count), (LookupOutcome.STALE_BEYOND_LIMIT, None, (), 5))
        self.assertIs(lk.leg_freshness[0].state, c.FreshnessState.STALE)
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))

    def test_a_later_fixing_in_the_version_is_never_used_for_an_earlier_date(self):
        lk = self.lookup(self.held(), D(2025, 4, 16))
        self.assertEqual(lk.date_used, D(2025, 4, 16))  # not the 17th: no look-ahead
        none = self.lookup([D(2025, 4, 17)], D(2025, 4, 16))
        self.assertEqual((none.outcome, none.rate), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(state_of(none, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))

    def test_no_ecb_calendar_for_the_interval_is_unknown_with_no_code(self):
        readings = [k.fx_reading(D(2025, 4, 17), "USD", "1.0817")]
        lk = k.store(readings).fx_on(k.EUR, k.USD, D(2025, 4, 19), market11_conventions(CalendarSet()))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.FRESHNESS_UNKNOWN, None))
        self.assertIn("CALENDAR_COVERAGE_GAP", lk.lineage_notes[0])
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, None))


class Example1ATests(unittest.TestCase):
    """Example 1-A: x_USD = 1.0823, x_HKD = 8.4512, x_CNY = 7.8243 (units per EUR), all on one fixing date.
    Crosses are exact ratios of two same-date legs (Ruling 1.3); no rounded Decimal exists anywhere."""

    DAY = D(2025, 1, 2)
    CAL = k.ecb_calendar([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], covers=(D(2025, 1, 1), D(2025, 1, 10)))

    def conv(self, parity=None):
        # Ruling 1.5a (1.3): the product builder takes no parity mapping; a test injects one only through the
        # test-only builder, never through the product path
        if parity is None:
            return market11_conventions(CalendarSet([self.CAL]))
        return market11_conventions_with_injected_parity_for_tests(CalendarSet([self.CAL]), parity)

    def store(self, usd="1.0823", hkd="8.4512", cny="7.8243", extra=()):
        return k.store([k.fx_reading(self.DAY, "USD", usd), k.fx_reading(self.DAY, "HKD", hkd),
                        k.fx_reading(self.DAY, "CNY", cny), *extra])

    def test_the_three_crosses_are_the_quants_exact_fractions(self):
        st, conv = self.store(), self.conv()
        usd_hkd = st.fx_on(k.USD, k.HKD, self.DAY, conv)
        usd_cny = st.fx_on(k.USD, k.CNY, self.DAY, conv)
        hkd_cny = st.fx_on(k.HKD, k.CNY, self.DAY, conv)
        self.assertEqual(usd_hkd.rate, Fraction(84512, 10823))  # 8.4512 / 1.0823 (the Quant: 84512 / 10823)
        self.assertEqual(usd_cny.rate, Fraction(78243, 10823))
        self.assertEqual(hkd_cny.rate, Fraction(78243, 84512))
        for lk in (usd_hkd, usd_cny, hkd_cny):
            self.assertIsInstance(lk.rate, Fraction)
            self.assertEqual((lk.outcome, lk.missed_count, lk.date_used), (LookupOutcome.FOUND, 0, self.DAY))

    def test_the_exact_triangle_closes(self):
        st, conv = self.store(), self.conv()
        a = st.fx_on(k.USD, k.HKD, self.DAY, conv).rate
        b = st.fx_on(k.HKD, k.CNY, self.DAY, conv).rate
        self.assertEqual(a * b, st.fx_on(k.USD, k.CNY, self.DAY, conv).rate)  # (84512/10823) x (78243/84512) = 78243/10823

    def test_ten_thousand_hkd_to_usd_is_6764375_over_5282(self):
        lk = self.store().fx_on(k.HKD, k.USD, self.DAY, self.conv())
        self.assertEqual(lk.rate, Fraction(10823, 84512))
        self.assertEqual(Fraction(10000) * lk.rate, Fraction(6764375, 5282))  # the Quant's exact conversion

    def test_a_cross_is_two_linked_same_date_legs_with_both_lineage_records(self):
        lk = self.store().fx_on(k.USD, k.HKD, self.DAY, self.conv())
        self.assertEqual((lk.cross.numerator.rate, lk.cross.denominator.rate), (Decimal("8.4512"), Decimal("1.0823")))
        self.assertEqual((lk.cross.numerator.quote_currency, lk.cross.denominator.quote_currency), (k.HKD, k.USD))
        self.assertEqual(lk.cross.fixing_date, self.DAY)
        self.assertEqual(lk.cross.as_fraction(), lk.rate)
        self.assertEqual(len(lk.legs), 2)
        self.assertEqual({leg.observation.lineage.source_record_ref for leg in lk.legs}, {"r"})
        self.assertIn("exact cross", lk.selection_basis)

    def test_legs_of_two_dates_are_never_combined_the_latest_common_date_is_used(self):
        later = k.fx_reading(D(2025, 1, 3), "USD", "1.0900")  # USD has a newer fixing; HKD does not
        lk = self.store(extra=[later]).fx_on(k.USD, k.HKD, D(2025, 1, 3), self.conv())
        self.assertEqual((lk.date_used, lk.rate, lk.missed_count), (self.DAY, Fraction(84512, 10823), 1))  # not 8.4512/1.09
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, R.STALE_DATA))

    def test_a_rate_with_eur_as_base_is_the_published_quote_and_the_reverse_a_labelled_exact_inverse(self):
        st, conv = self.store(), self.conv()
        direct = st.fx_on(k.EUR, k.USD, self.DAY, conv)
        inverse = st.fx_on(k.USD, k.EUR, self.DAY, conv)
        self.assertEqual((direct.rate, direct.cross), (Fraction(10823, 10000), None))
        self.assertEqual(inverse.rate, Fraction(10000, 10823))
        self.assertIn("inverse", inverse.selection_basis)

    def test_the_hkd_peg_band_runs_where_data_exist_and_the_cny_check_is_unverifiable_never_fabricated(self):
        lk = self.store().fx_on(k.HKD, k.CNY, self.DAY, self.conv())
        self.assertEqual(lk.checks, (("HKD_PEG_BAND", "PASS"), ("CNY_PARITY_BAND", "UNVERIFIABLE")))  # 7.8085 in 7.75..7.85
        self.assertEqual(self.store().fx_on(k.USD, k.CNY, self.DAY, self.conv()).checks, (("CNY_PARITY_BAND", "UNVERIFIABLE"),))
        self.assertEqual(self.store().fx_on(k.USD, k.EUR, self.DAY, self.conv()).checks, ())  # neither currency is checked

    def test_the_peg_band_edges_are_exact_and_inclusive(self):
        # 7.85 x 1.0823 = 8.496055 and 7.75 x 1.0823 = 8.387825 (hand arithmetic)
        for hkd, want in (("8.496055", "PASS"), ("8.496056", "FAIL"), ("8.387825", "PASS"), ("8.387824", "FAIL")):
            lk = self.store(hkd=hkd).fx_on(k.EUR, k.HKD, self.DAY, self.conv())
            self.assertEqual(lk.checks, (("HKD_PEG_BAND", want),), hkd)

    def test_a_breached_peg_band_makes_the_observation_implausible_with_no_rate_and_a_source_conflict(self):
        lk = self.store(hkd="8.6000").fx_on(k.USD, k.HKD, self.DAY, self.conv())
        self.assertEqual((lk.outcome, lk.rate, lk.legs), (LookupOutcome.NO_SELECTION, None, ()))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.IMPLAUSIBLE)
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))
        self.assertTrue(any("HKD_PEG_BAND" in f for f in lk.reconciliation.flags))

    def test_the_cny_band_uses_a_central_parity_series_only_when_one_is_in_the_version(self):
        # CNY per USD = 7.8243 / 1.0823 = 7.2293...; the band is +-2 % of the parity (hand arithmetic)
        ok = self.store().fx_on(k.USD, k.CNY, self.DAY, self.conv({self.DAY: Decimal("7.2")}))  # |7.2293 - 7.2| = 0.029 <= 0.144
        self.assertEqual(ok.checks, (("CNY_PARITY_BAND", "PASS"),))
        bad = self.store().fx_on(k.USD, k.CNY, self.DAY, self.conv({self.DAY: Decimal("7.0")}))  # 0.229 > 0.14
        self.assertEqual((bad.outcome, bad.rate, bad.checks), (LookupOutcome.NO_SELECTION, None, (("CNY_PARITY_BAND", "FAIL"),)))
        self.assertEqual(state_of(bad, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))
        other_day = self.store().fx_on(k.USD, k.CNY, self.DAY, self.conv({D(2025, 1, 3): Decimal("7.0")}))
        self.assertEqual(other_day.checks, (("CNY_PARITY_BAND", "UNVERIFIABLE"),))  # no parity for THIS date

    def test_cnh_is_strict_even_when_a_cnh_series_is_in_the_version(self):
        cnh = k.fx_reading(self.DAY, "CNH", "7.9000")
        st = self.store(extra=[cnh])
        for base, quote in ((k.CNH, k.USD), (k.USD, k.CNH), (k.CNH, k.CNY), (k.CNH, k.EUR)):
            lk = st.fx_on(base, quote, self.DAY, self.conv())
            self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NOT_IN_RELEASE, None), (base, quote))
            self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))
        self.assertEqual(st.fx_on(k.CNY, k.USD, self.DAY, self.conv()).rate, Fraction(10823, 78243))  # CNY is unaffected

    def test_same_currency_is_one_and_an_absent_leg_is_missing_fx_history(self):
        st = self.store()
        self.assertEqual(st.fx_on(k.USD, k.USD, self.DAY, self.conv()).outcome, LookupOutcome.SAME_CURRENCY)
        jpy = st.fx_on(k.USD, k.CurrencyCode("JPY"), self.DAY, self.conv())
        self.assertEqual((jpy.outcome, jpy.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        self.assertEqual(state_of(jpy, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))


class FxTransportCheckTests(unittest.TestCase):
    """Ruling 1.1a items 2 and 4: the ECB's own file and its re-server share one upstream. Agreement is
    SINGLE_SOURCE, a value difference or a date present in one and absent in the other (inside both coverages)
    is a DISAGREEMENT; Frankfurter-derived rates carry provenance UNCONFIRMED until the check passes."""

    E, F = "e" * 64, "f" * 64

    def conv(self):
        # C2-1 (CP2 review): a rate dated the as-of date is CURRENT only under a governing, covering calendar, so these
        # tests, which look up ON a fixing date, now carry the ECB fixing calendar (invented synthetic dates). No
        # expected value below moved.
        fixings = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7)]
        return market11_conventions(CalendarSet([k.ecb_calendar(fixings, covers=(D(2025, 1, 1), D(2025, 1, 31)))]))

    def ecb(self, day, rate, provenance=None):
        return k.fx_reading(day, "USD", rate, source="ecb.eurofxref", sha=self.E, provenance=provenance)

    def frank(self, day, rate, provenance="UNCONFIRMED"):
        return k.fx_reading(day, "USD", rate, source="frankfurter.ecb", sha=self.F, provenance=provenance)

    def look(self, readings, day, windows=None):
        return k.store(readings, precedence=("ecb.eurofxref", "frankfurter.ecb"), fx_windows=windows).fx_on(
            k.EUR, k.USD, day, self.conv())

    def test_equal_values_are_single_source_never_corroborated_and_the_ecb_file_is_primary(self):
        lk = self.look([self.frank(D(2025, 1, 2), "1.08170"), self.ecb(D(2025, 1, 2), "1.0817")], D(2025, 1, 2))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.FOUND, Fraction(10817, 10000)))
        self.assertIs(lk.leg_reconciliations[0].status, c.ReconciliationStatus.SINGLE_SOURCE)
        self.assertEqual(lk.legs[0].source_id, "ecb.eurofxref")
        self.assertEqual(lk.lineage_notes, ())  # the ECB-direct reading carries no UNCONFIRMED provenance

    def test_a_value_difference_is_a_disagreement_and_a_source_conflict(self):
        lk = self.look([self.frank(D(2025, 1, 2), "1.0818"), self.ecb(D(2025, 1, 2), "1.0817")], D(2025, 1, 2))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NO_SELECTION, None))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.DISAGREEMENT)
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))

    # the coverage windows of Ruling 1.1a item 5 (1.3), as the build path derives them from a manifest
    WINDOWS = {"e" * 64: FXFileWindow(None, D(2025, 1, 6)),  # a full-history file: starts at its first held date
               "f" * 64: FXFileWindow(D(2025, 1, 2), D(2025, 1, 6))}  # a request-bounded file: 2..6 Jan

    def test_a_date_absent_from_one_file_inside_both_coverages_is_a_disagreement(self):
        # the ECB file holds 2, 3, 6 Jan; the re-server holds 2 and 6 (its coverage 2..6 includes the 3rd)
        readings = [self.ecb(D(2025, 1, 2), "1.0817"), self.ecb(D(2025, 1, 3), "1.0818"), self.ecb(D(2025, 1, 6), "1.0819"),
                    self.frank(D(2025, 1, 2), "1.0817"), self.frank(D(2025, 1, 6), "1.0819")]
        gap = self.look(readings, D(2025, 1, 3), self.WINDOWS)
        self.assertEqual((gap.outcome, gap.rate), (LookupOutcome.NO_SELECTION, None))
        self.assertTrue(any("1.1a" in f for f in gap.reconciliation.flags))
        self.assertEqual(state_of(gap, fx=True), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))
        fine = self.look(readings, D(2025, 1, 6), self.WINDOWS)  # both files hold the 6th
        self.assertEqual((fine.outcome, fine.rate), (LookupOutcome.FOUND, Fraction(10819, 10000)))
        # market-data/1.3 (Ruling 1.1a item 5): with no coverage window the date-set part is UNVERIFIABLE and
        # does not run: the held dates are never read as the coverage (1.2 flagged this case from held dates)
        unknown = self.look(readings, D(2025, 1, 3))
        self.assertEqual((unknown.outcome, unknown.rate), (LookupOutcome.FOUND, Fraction(10818, 10000)))

    def test_a_date_outside_the_other_files_coverage_is_not_a_disagreement(self):
        readings = [self.ecb(D(2025, 1, 2), "1.0817"), self.ecb(D(2025, 1, 7), "1.0820"),
                    self.frank(D(2025, 1, 2), "1.0817"), self.frank(D(2025, 1, 6), "1.0819")]
        windows = {"e" * 64: FXFileWindow(None, D(2025, 1, 7)), "f" * 64: FXFileWindow(D(2025, 1, 2), D(2025, 1, 6))}
        lk = self.look(readings, D(2025, 1, 7), windows)  # the re-server's coverage ends on the 6th
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.FOUND, Fraction(10820, 10000)))

    def test_frankfurter_derived_rates_carry_provenance_unconfirmed_in_the_result(self):
        lk = self.look([self.frank(D(2025, 1, 2), "1.0817")], D(2025, 1, 2))
        self.assertEqual(lk.outcome, LookupOutcome.FOUND)
        self.assertEqual(len(lk.lineage_notes), 1)
        self.assertIn("provenance: UNCONFIRMED (frankfurter.ecb)", lk.lineage_notes[0])
        self.assertIn("not evidence", lk.lineage_notes[0])
        # market-data/1.3 (Ruling 1.1a item 6): a REFUTED re-server file supplies NO rate on any date. Alone it
        # leaves no rate at all (the 1.2 expectation, a rate carrying a REFUTED note, was wrong); against the
        # ECB's own file it can only make a DISAGREEMENT where the values differ.
        refuted = self.look([self.frank(D(2025, 1, 2), "1.0817", provenance="REFUTED")], D(2025, 1, 2))
        self.assertEqual((refuted.outcome, refuted.rate), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(state_of(refuted, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))
        confirmed = self.look([self.frank(D(2025, 1, 2), "1.0817", provenance="CONFIRMED")], D(2025, 1, 2))
        self.assertEqual(confirmed.lineage_notes, ())


class NoAdmittedSourceAndSyntheticTests(unittest.TestCase):
    """Ruling 4.7: a market with no admitted source resolves to MISSING_PRICE_HISTORY with the cause
    NO_ADMITTED_SOURCE and freshness UNKNOWN. Ruling 4.8: synthetic data never meets real data."""

    def conv(self):
        return market11_conventions(CalendarSet())

    def test_a_listing_on_cn_or_hk_with_no_reading_is_missing_price_history_with_the_cause(self):
        for mic, market in (("XSHG", "CN"), ("XSHE", "CN"), ("XHKG", "HK")):
            lk = k.store([], mic=mic).quote_on(k.LID, D(2025, 4, 30), self.conv())
            # market-data/1.3 section 9B #3: NO_ADMITTED_SOURCE is one cause of NO_HISTORY (it was NOT_IN_RELEASE
            # in 1.2): the same (state, reason) pair, with its own lineage cause
            self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None), mic)
            self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)  # nothing was ever printed: not STALE
            self.assertIn(f"NO_ADMITTED_SOURCE: market {market}", lk.lineage_notes[0])
            self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))

    def test_us_has_an_admitted_source_so_an_empty_us_listing_carries_no_such_cause(self):
        lk = k.store([], mic="XNYS").quote_on(k.LID, D(2025, 4, 30), self.conv())
        self.assertEqual((lk.lineage_notes, lk.freshness), ((), None))
        self.assertEqual(state_of(lk), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))

    def test_synthetic_data_marks_every_result_and_a_real_only_version_is_not_marked(self):
        days = [D(2025, 4, 30)]
        conv = market11_conventions(CalendarSet([k.exchange_calendar("NY", ("XNYS",), days)]))
        synthetic = k.store([k.quote_reading(D(2025, 4, 30), "10.00")]).quote_on(k.LID, D(2025, 4, 30), conv)
        real = k.store([k.quote_reading(D(2025, 4, 30), "10.00", usage=REAL)]).quote_on(k.LID, D(2025, 4, 30), conv)
        self.assertEqual((synthetic.synthetic, real.synthetic), (True, False))

    def test_synthetic_and_real_readings_are_never_reconciled_and_the_real_one_is_used(self):
        # C2-1: the lookup is ON the print date, so a governing calendar covering it is part of the setup (no value moved)
        conv = market11_conventions(CalendarSet([k.exchange_calendar("NY", ("XNYS",), [D(2025, 4, 30)])]))
        real = k.quote_reading(D(2025, 4, 30), "10.00", usage=REAL, source="alphavantage.us", group="alphavantage")
        fake = k.quote_reading(D(2025, 4, 30), "10.01", source="synthetic.vendor", group="synthetic.vendor", sha=k.SHA2)
        lk = k.store([real, fake]).quote_on(k.LID, D(2025, 4, 30), conv)
        self.assertEqual((lk.outcome, lk.selected.observation.price), (LookupOutcome.FOUND, Decimal("10.00")))
        self.assertEqual(lk.reconciliation.readings, (real,))  # the synthetic reading is not in the comparison
        self.assertTrue(any("4.8" in f for f in lk.reconciliation.flags))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.SINGLE_SOURCE)  # it corroborated nothing
        self.assertTrue(lk.synthetic)  # the version holds a synthetic file, so the result says so


class ConformanceTests(unittest.TestCase):
    def test_the_market11_set_is_conformant_with_no_placeholder_and_still_lists_what_is_open(self):
        conv = market11_conventions(CalendarSet())
        self.assertTrue(conv.is_conformant)
        self.assertEqual(conv.placeholder_ids(), ())
        self.assertEqual(conv.ids()["convention_set"], "market-data/1.16")  # section 11 item 13 (1.7; 1.11; 1.12; 1.13; 1.14; 1.15; 1.16)
        for name in ("freshness", "fx", "price_of_date", "reconciliation"):
            self.assertTrue(conv.ids()[name].startswith("market-data/1.16#"), name)
        items = conv.visible_open_items()
        for fragment in ("profile TO_OBSERVE: akshare_sina.cn", "profile TO_OBSERVE: akshare.hk", "akshare.us"):
            self.assertTrue(any(fragment in i for i in items), fragment)
        self.assertFalse(any("alphavantage.us" in i for i in items))  # its profile is OBSERVED in 1.2
        # market-data/1.15 MD-OI-14: the A-share route is pending observation, and a result must not hide that
        self.assertTrue(any("profile TO_OBSERVE: alphavantage.cn" in i and "not admitted" in i for i in items))
        self.assertTrue(set(UNBUILT) <= set(items))

    def test_a_placeholder_still_makes_the_set_non_conformant_and_is_listed(self):
        conv = placeholder_conventions()
        self.assertFalse(conv.is_conformant)
        self.assertTrue(any(i.startswith("placeholder rule injected: placeholder/") for i in conv.visible_open_items()))
        mixed = dataclasses.replace(market11_conventions(CalendarSet()), fx=conv.fx)
        self.assertFalse(mixed.is_conformant)
        self.assertEqual(mixed.placeholder_ids(), (conv.fx.rule_id,))


if __name__ == "__main__":
    unittest.main()
