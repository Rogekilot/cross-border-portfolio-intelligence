"""Test V2 under market-data/1.2 (a'): the bound is derived from the series' profiles carried on the rows,
never a caller input; Test V0 (calendar alignment); and the Ruling 1.1a provenance check. All numbers are
SYNTHETIC and every expected value is derived by hand next to its input."""

import dataclasses
import datetime
import inspect
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

from marketdata import contracts as c  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.verification import PriceRow, check_provenance, verify_adjustment_v2, verify_v0  # noqa: E402

D = datetime.date
DAYS = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)]
HALF_CENT = Fraction(1, 200)  # delta_j: half a unit of the 2 decimals the adjusted series delivers (profile adjusted_dp 2)


def rows(closes, bound, transform=lambda v: v):
    out = []
    for day, close in zip(DAYS, closes):
        v = Decimal(close)
        o, h, l_, cl = (transform(v + off) for off in (Decimal(0), Decimal(1), Decimal(-1), Decimal(0)))
        out.append(PriceRow(day, o, h, l_, cl, bound))
    return out


REF = ("200.00", "210.00", "248.00", "230.50", "225.25")  # lo = 200.00, hi = 248.00, Delta = 48


class V2BoundTests(unittest.TestCase):
    def v2(self, shift, bound_adj=HALF_CENT, tweak=None):
        ref = rows(REF, Fraction(0))  # recovered raw closes: delta_r = 0
        adj = rows(REF, bound_adj, lambda v: v - Decimal(shift))
        if tweak is not None:
            i, delta = tweak
            adj[i] = dataclasses.replace(adj[i], close=adj[i].close + Decimal(delta))
        return verify_adjustment_v2(ref, adj, [], D(2026, 10, 1))

    def test_the_bound_is_not_a_parameter_of_the_test(self):
        self.assertEqual(list(inspect.signature(verify_adjustment_v2).parameters), ["reference", "adjusted", "events", "vintage"])

    def test_a_pure_cash_offset_is_subtractive_with_the_bounds_derived_by_hand(self):
        r = self.v2("7.58")
        (fit,) = r.fits
        self.assertEqual((r.method, r.status), (c.AdjustmentMethod.SUBTRACTIVE, c.LabelStatus.UNVERIFIABLE))
        self.assertEqual((fit.a, fit.b), (Fraction(1), Fraction(379, 50)))  # a = 48/48; b = 248 - 240.42 = 7.58
        # e_lo = e_hi = 1/200 (delta_r = 0); u_a = (1/200 + 1/200) / 48 = 1/4800; u_b = 1/200 + 200 x (1/4800) = 7/150
        self.assertEqual(fit.bound_a, Fraction(1, 4800))
        self.assertEqual(fit.bound_b, Fraction(7, 150))
        self.assertEqual(fit.kind, "SUBTRACTIVE")

    def test_an_offset_below_u_b_is_not_a_nonzero_b_and_one_above_it_is(self):
        # u_b = 7/150 = 0.04666...: 0.04 < u_b -> b = 0 -> IDENTITY; 0.05 > u_b -> SUBTRACTIVE
        small = self.v2("0.04")
        self.assertEqual((small.fits[0].kind, small.method, small.status),
                         ("IDENTITY", c.AdjustmentMethod.UNKNOWN, c.LabelStatus.UNVERIFIABLE))
        big = self.v2("0.05")
        self.assertEqual((big.fits[0].kind, big.method), ("SUBTRACTIVE", c.AdjustmentMethod.SUBTRACTIVE))

    def test_the_residual_bound_is_e_i_plus_the_larger_anchor_error_which_is_one_cent_here(self):
        ok = self.v2("7.58", tweak=(3, "0.009"))  # row 3 is off the fit by 0.009 <= 0.005 + 0.005
        self.assertEqual(ok.method, c.AdjustmentMethod.SUBTRACTIVE)
        broken = self.v2("7.58", tweak=(3, "0.011"))  # 0.011 > 0.01
        self.assertEqual((broken.method, broken.status), (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.CONTRADICTED))
        self.assertIn("not affine", broken.reason)

    def test_a_larger_delivered_precision_bound_tolerates_what_a_tighter_one_does_not(self):
        # the same data with the adjusted series delivering whole units (delta_j = 1/2): the 0.011 miss is within e + e = 1
        loose = self.v2("7.58", bound_adj=Fraction(1, 2), tweak=(3, "0.011"))
        self.assertEqual(loose.method, c.AdjustmentMethod.SUBTRACTIVE)

    def test_a_proportional_series_is_told_apart_by_a_not_equal_one_and_b_equal_zero(self):
        closes = ("100.00", "90.00", "80.00", "110.00", "120.00")  # lo = 80, hi = 120, Delta = 40
        ref = rows(closes, Fraction(0))
        adj = rows(closes, HALF_CENT, lambda v: v * Decimal("0.99"))  # every value stays on 2 decimals
        r = verify_adjustment_v2(ref, adj, [], D(2026, 10, 1))
        (fit,) = r.fits
        self.assertEqual((fit.a, fit.b, fit.kind), (Fraction(99, 100), Fraction(0), "PROPORTIONAL"))
        self.assertEqual(fit.bound_a, Fraction(1, 4000))  # (1/200 + 1/200) / 40; |a - 1| = 1/100 > 1/4000
        self.assertEqual(r.method, c.AdjustmentMethod.PROPORTIONAL)

    def test_the_reference_precision_enters_through_the_row_bound_e_i_equals_delta_j_plus_abs_a_times_delta_r(self):
        # delta_r = 1/100 on the reference rows, a = 1: e = 1/200 + 1/100 = 3/200; u_a = (3/200 + 3/200) / 48 = 1/1600
        ref = rows(REF, Fraction(1, 100))
        adj = rows(REF, HALF_CENT, lambda v: v - Decimal("7.58"))
        (fit,) = verify_adjustment_v2(ref, adj, [], D(2026, 10, 1)).fits
        self.assertEqual(fit.bound_a, Fraction(1, 1600))
        self.assertEqual(fit.bound_b, Fraction(3, 200) + Fraction(200, 1600))  # e_lo + |ref_lo| u_a = 3/200 + 1/8


class V0Tests(unittest.TestCase):
    def calendars(self):
        cal = k.exchange_calendar("NY", ("XNYS",), [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)],
                                  covers=(D(2025, 1, 1), D(2025, 1, 10)))
        return CalendarSet([cal])

    def test_every_date_a_listed_session_is_verified(self):
        r = verify_v0([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], self.calendars(), "XNYS")
        self.assertEqual((r.status, r.off_calendar, r.uncovered), (c.LabelStatus.VERIFIED, (), ()))

    def test_a_date_on_a_non_session_inside_the_coverage_contradicts_the_series(self):
        # 4 January 2025 is a Saturday the calendar does not list: the signature of a UTC date shift
        r = verify_v0([D(2025, 1, 2), D(2025, 1, 4)], self.calendars(), "XNYS")
        self.assertEqual((r.status, r.off_calendar), (c.LabelStatus.CONTRADICTED, (D(2025, 1, 4),)))

    def test_a_date_outside_the_coverage_is_unverifiable_never_judged_against_weekdays(self):
        r = verify_v0([D(2025, 1, 2), D(2025, 1, 13)], self.calendars(), "XNYS")  # the 13th is a Monday outside coverage
        self.assertEqual((r.status, r.off_calendar, r.uncovered), (c.LabelStatus.UNVERIFIABLE, (), (D(2025, 1, 13),)))
        mixed = verify_v0([D(2025, 1, 4), D(2025, 1, 13)], self.calendars(), "XNYS")
        self.assertEqual(mixed.status, c.LabelStatus.CONTRADICTED)  # a covered non-session decides

    def test_no_governing_calendar_is_unverifiable_with_the_gap_cause(self):
        r = verify_v0([D(2025, 1, 2)], self.calendars(), "XHKG")
        self.assertEqual(r.status, c.LabelStatus.UNVERIFIABLE)
        self.assertIn("CALENDAR_COVERAGE_GAP", r.reason)


class ProvenanceTests(unittest.TestCase):
    """Ruling 1.1a item 3 with the coverage of item 5 (1.3): equal as decimals, and the same set of dates inside
    the overlap of the two files' COVERAGES (windows (start, end); start None = first date held for the currency)."""

    def build(self, rows_):
        return {(D(2025, 1, d), ccy): Decimal(v) for d, ccy, v in rows_}

    @staticmethod
    def win(start, end):
        return (None if start is None else D(2025, 1, start), None if end is None else D(2025, 1, end))

    def test_equal_values_and_the_same_dates_on_the_overlap_confirm_with_trailing_zeros_ignored(self):
        direct = self.build([(2, "USD", "1.0800"), (3, "USD", "1.0810"), (6, "USD", "1.0820"), (7, "USD", "1.0830")])
        declared = self.build([(2, "USD", "1.08"), (3, "USD", "1.081"), (6, "USD", "1.0820")])
        # declared: requested 2..6; direct: full history, first held 2, through 7 -> overlap [2, 6]
        r = check_provenance(declared, direct, self.win(2, 6), self.win(None, 7))
        self.assertEqual((r.status, r.window), ("CONFIRMED", (D(2025, 1, 2), D(2025, 1, 6))))
        self.assertEqual(r.confirmed_dates, (D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)))

    def test_without_coverage_windows_the_date_set_part_is_unverifiable_never_read_from_held_dates(self):
        # market-data/1.3: the held dates are NOT a coverage (a missing edge date would be invisible), so with no
        # window the date-set part does not run: nothing is confirmed, and nothing is refuted by a date.
        direct = self.build([(2, "USD", "1.08"), (3, "USD", "1.081"), (6, "USD", "1.082")])
        declared = self.build([(2, "USD", "1.08"), (6, "USD", "1.082")])
        r = check_provenance(declared, direct)
        self.assertEqual((r.status, r.confirmed_dates), ("UNCONFIRMED", ()))
        # an unknown end (no ECB calendar to fix D_ret) is the same
        self.assertEqual(check_provenance(declared, direct, self.win(2, 6), self.win(None, None)).status, "UNCONFIRMED")

    def test_a_missing_edge_date_is_seen_through_the_requested_window(self):
        # the Quant's example: requested through the 8th, the 8th missing from the declared file
        direct = self.build([(2, "USD", "1.08"), (3, "USD", "1.081"), (8, "USD", "1.0823")])
        declared = self.build([(2, "USD", "1.08"), (3, "USD", "1.081")])
        r = check_provenance(declared, direct, self.win(1, 8), self.win(None, 8))
        self.assertEqual(r.status, "REFUTED")
        self.assertIn("2025-01-08/USD", r.reason)
        # under the held-dates reading (declared coverage 2..3) the same pair would have been confirmed
        self.assertEqual(check_provenance(declared, direct, self.win(2, 3), self.win(None, 8)).status, "CONFIRMED")

    def test_one_differing_value_refutes_the_declared_file(self):
        direct = self.build([(2, "USD", "1.0800"), (3, "USD", "1.0810")])
        declared = self.build([(2, "USD", "1.0800"), (3, "USD", "1.0811")])
        self.assertEqual(check_provenance(declared, direct).status, "REFUTED")

    def test_a_date_present_in_one_file_and_absent_in_the_other_within_the_overlap_refutes(self):
        direct = self.build([(2, "USD", "1.08"), (3, "USD", "1.081"), (6, "USD", "1.082")])
        declared = self.build([(2, "USD", "1.08"), (6, "USD", "1.082")])
        r = check_provenance(declared, direct, self.win(2, 6), self.win(None, 6))
        self.assertEqual(r.status, "REFUTED")
        self.assertIn("2025-01-03", r.reason)

    def test_dates_outside_the_overlap_neither_confirm_nor_refute(self):
        direct = self.build([(2, "USD", "1.08"), (3, "USD", "1.081")])
        declared = self.build([(3, "USD", "1.081"), (6, "USD", "9.99")])  # the 6th is outside the direct file's span
        # declared: requested 3..6; direct: first held 2, through 3 -> overlap [3, 3]
        r = check_provenance(declared, direct, self.win(3, 6), self.win(None, 3))
        self.assertEqual((r.status, r.confirmed_dates), ("CONFIRMED", (D(2025, 1, 3),)))

    def test_no_overlap_or_no_common_currency_is_unconfirmed(self):
        direct = self.build([(2, "USD", "1.08")])
        self.assertEqual(check_provenance(self.build([(6, "USD", "1.08")]), direct).status, "UNCONFIRMED")
        self.assertEqual(check_provenance(self.build([(2, "HKD", "8.4")]), direct).status, "UNCONFIRMED")


if __name__ == "__main__":
    unittest.main()
