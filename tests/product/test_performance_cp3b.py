"""CP3b: `performance/1.0` valuation rulings (1.4 to 1.7), rounding (2.1 to 2.5), flows (4.1 to 4.5), windows (5.4), the TWR in segment form (5.1 to 5.6)
and annualization (7.1 to 7.2). Every expected value is derived by hand from the inputs shown; the worked examples are the Quant's (Example W, V-2, V-3, R-1,
R-2, A-1), reproduced from the convention document. Market data are synthetic (`performance_kit`).
"""

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from marketdata import market11  # noqa: E402
from marketdata.profiles import ECB_FIXING_TIME  # noqa: E402
from performance import current, numerics  # noqa: E402
from performance.conventions import FlowClass, FlowTiming  # noqa: E402
from performance.engine import compute_current, performance_conventions  # noqa: E402
compute, compute_window, reproduce = pk.compute, pk.compute_window, pk.reproduce  # the engine's pure entries with `suppressions` STATED (none), see performance_kit
from performance.flows import ValuedFlow  # noqa: E402
from performance.ledger_view import ClassifiedEvent, Inception, classify_events  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.numerics import RoundingPoint  # noqa: E402
from performance.periods import WindowRule, WindowSpec, add_months, resolve_window, sub_months, year_fraction  # noqa: E402
from performance.results import DECIMAL_PREC50, Cause, Part, WindowUsed  # noqa: E402
from performance.returns import annualize, absolute_gain, ratio, twr_segments  # noqa: E402
from performance.rounding import CURRENCY_NO_MINOR_UNIT, PerformanceRounding  # noqa: E402
from performance.states import REASON_PRIORITY, PerformanceAggregation, Valued, build_metric, insufficient_part, limited_part  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
USD, HKD = pk.USD, pk.HKD
AVAILABLE, LIMITED, INSUFFICIENT = (SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA)
F = Fraction
PERF = performance_conventions()


def metric(result, metric_id):
    (m,) = [m for m in result.metrics if m.metric_id == metric_id]
    return m


# ===== rounding mechanisms (Rulings 2.2, 2.3, 2.4) =====================================================================

class RoundingTests(unittest.TestCase):
    def test_half_away_from_zero_at_the_quantum(self):
        # 2.675 = 2675/1000 sits exactly on a half at 2 decimals: away from zero gives 2.68 (half-even would give 2.68 too; the negative shows the rule)
        self.assertEqual(numerics.round_half_up(F(2675, 1000), 2), F(268, 100))
        self.assertEqual(numerics.round_half_up(F(-2675, 1000), 2), F(-268, 100))  # not -2.67 (half up) and not half-even
        self.assertEqual(numerics.round_half_up(F(5, 1000), 2), F(1, 100))          # 0.005 -> 0.01
        self.assertEqual(numerics.round_half_up(F(-5, 1000), 2), F(-1, 100))
        self.assertEqual(numerics.round_half_up(F(2, 1000), 2), F(0))               # below a half: down
        self.assertEqual(numerics.round_half_up(F(25, 10), 0), F(3))                # 2.5 -> 3 (half-even would give 2)
        self.assertEqual(numerics.round_half_up(F(1, 3), 12), F(333333333333, 10 ** 12))

    def test_the_minor_unit_table_and_the_fail_closed_rule(self):
        rule = PerformanceRounding()
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_MONEY, F(5, 2), CurrencyCode("JPY")).stated, F(3))   # JPY has 0 decimals
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_MONEY, F(1, 3), CurrencyCode("HKD")).stated, F(33, 100))
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_MONEY, F(1, 3), CurrencyCode("CNH")).stated, F(33, 100))  # DECLARED row
        unknown = rule.apply(RoundingPoint.PRESENT_MONEY, F(1, 3), CurrencyCode("XYZ"))
        self.assertEqual((unknown.stated, unknown.detail), (None, CURRENCY_NO_MINOR_UNIT))  # never defaults to 2
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_RETURN, F(1, 3), None).stated, F(333333333333, 10 ** 12))
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_RATE, F(1, 3), None).stated, F(333333, 10 ** 6))
        self.assertEqual(rule.apply(RoundingPoint.PRESENT_FACT, F(7, 2), None).stated, F(7, 2))   # a recorded fact: exactly
        self.assertIsNone(rule.apply(RoundingPoint.PRESENT_FACT, F(1, 3), None).stated)           # not a decimal: a defect, not a rounding

    def test_a_currency_missing_from_the_table_makes_the_metric_insufficient_with_unresolved_convention(self):
        valued = Valued(AVAILABLE, None, F(1, 3), ())
        m = build_metric("gain_absolute", "REPORTING", (), valued, CurrencyCode("XYZ"), PerformanceRounding(), WindowUsed(D(2025, 1, 3), D(2025, 1, 3)),
                         "t", False, False)
        self.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code),
                         (None, INSUFFICIENT, ReasonCode.UNRESOLVED_CONVENTION))
        self.assertIn(CURRENCY_NO_MINOR_UNIT, m.details)
        self.assertIsNone(m.exact)  # no number leaks

    def test_example_r1_removed_plus_remaining_and_proceeds(self):
        # one lot of 3 units for 100.00 USD; sell 1 for 40.00. Basis object (total 100.00): exact [100/3, 200/3]; floors 33.33 + 66.66 = 99.99;
        # the shortfall 1 goes to the larger remainder (0.00666 > 0.00333): 33.33 + 66.67 = 100.00
        self.assertEqual(numerics.apportion(F(100), [F(100, 3), F(200, 3)], 2), (F(3333, 100), F(6667, 100)))
        # proceeds object (total 40.00): exact [100/3 removed basis, 20/3 realized]; floors 33.33 + 6.66 = 39.99; realized has the larger remainder
        self.assertEqual(numerics.apportion(F(40), [F(100, 3), F(20, 3)], 2), (F(3333, 100), F(667, 100)))

    def test_example_r2_eight_lines_apportioned_to_the_displayed_total(self):
        lines = [F(1800, 7), F(-3979, 273), F(-100, 273), F(1000, 39), F(-9, 7), F(-100, 39), F(0), F(-80, 7)]
        total = F(9850, 39)
        self.assertEqual(sum(lines, F(0)), total)  # 68,950/273 = 9,850/39 (hand: 70,200 - 3,979 - 100 + 7,000 - 351 - 700 + 0 - 3,120)
        shown = numerics.apportion(total, lines, 2)
        self.assertEqual([float(s) for s in shown], [257.14, -14.57, -0.37, 25.64, -1.29, -2.56, 0.0, -11.43]) if False else None
        self.assertEqual(shown, tuple(F(v, 100) for v in (25714, -1457, -37, 2564, -129, -256, 0, -1143)))
        self.assertEqual(sum(shown, F(0)), F(25256, 100))  # 252.56: the displayed parts sum EXACTLY to the displayed total
        self.assertEqual(numerics.round_half_up(total, 2), F(25256, 100))
        for exact, s in zip(lines, shown):  # each displayed part is within one quantum of its exact value
            self.assertLess(abs(exact - s), F(1, 100))

    def test_ties_go_in_the_fixed_line_order_and_unreconciled_parts_are_a_defect(self):
        # [1/3, 1/3, 1/3] to total 1: floors 0.33 x 3 = 0.99, shortfall 1, equal remainders: the FIRST line gets it
        self.assertEqual(numerics.apportion(F(1), [F(1, 3)] * 3, 2), (F(34, 100), F(33, 100), F(33, 100)))
        with self.assertRaises(ValueError):
            numerics.apportion(F(1), [F(1, 3), F(1, 3)], 2)


# ===== windows and the year fraction (Rulings 5.4, 7.1) ================================================================

class WindowTests(unittest.TestCase):
    def test_end_of_month_rule_examples(self):
        self.assertEqual(sub_months(D(2024, 2, 29), 12), D(2023, 2, 28))   # the last day of its month -> the last day of the target month
        self.assertEqual(sub_months(D(2025, 3, 31), 1), D(2025, 2, 28))
        self.assertEqual(add_months(D(2024, 1, 31), 13), D(2025, 2, 28))
        self.assertEqual(add_months(D(2025, 1, 30), 1), D(2025, 2, 28))    # not the last day of January: same day, clamped
        self.assertEqual(add_months(D(2025, 1, 15), 1), D(2025, 2, 15))
        self.assertEqual(sub_months(D(2025, 3, 3), 1), D(2025, 2, 3))

    def test_year_fraction_examples(self):
        self.assertEqual(year_fraction(D(2023, 2, 28), D(2024, 2, 29)), F(1))      # m = 12, r = 0 (366 days)
        self.assertEqual(year_fraction(D(2024, 2, 29), D(2025, 2, 28)), F(1))      # m = 12, r = 0 (365 days)
        # B 2024-01-31, E 2025-03-05: add_months(B, 13) = 2025-02-28 (month-end rule), r = 5: 13/12 + 5/365 = (13 x 365 + 5 x 12)/4,380 = 4,805/4,380 = 961/876
        self.assertEqual(year_fraction(D(2024, 1, 31), D(2025, 3, 5)), F(961, 876))
        self.assertEqual(year_fraction(D(2022, 1, 1), D(2025, 1, 1)), F(3))        # every whole-year window is exactly 1, 3 or 5
        self.assertEqual(year_fraction(D(2025, 3, 31), D(2025, 4, 3)), F(3, 365))  # m = 0, r = 3

    def test_windows_resolve_and_the_before_inception_rules(self):
        young = Inception(D(2025, 3, 31), False)
        # a "1M" window for a portfolio that began 2025-03-31 would reach back before inception: INSUFFICIENT, no reason, detail WINDOW_BEFORE_INCEPTION
        r = resolve_window(WindowSpec(WindowRule.TRAILING_MONTHS, 1), D(2025, 4, 3), young, "NOT_RECONSTRUCTABLE")
        self.assertIsNone(r.window)
        self.assertEqual((r.reason, r.cause.detail), (None, "WINDOW_BEFORE_INCEPTION"))
        self.assertEqual(resolve_window(WindowSpec(WindowRule.YTD), D(2025, 4, 3), young, "X").cause.detail, "WINDOW_BEFORE_INCEPTION")
        ok = resolve_window(WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), young, "X").window
        self.assertEqual((ok.start, ok.end, ok.days, ok.rule), (D(2025, 3, 31), D(2025, 4, 3), 3, "SINCE_INCEPTION"))
        ytd = resolve_window(WindowSpec(WindowRule.YTD), D(2025, 4, 3), Inception(D(2024, 6, 1), False), "X").window
        self.assertEqual((ytd.start, ytd.rule), (D(2024, 12, 31), "YTD"))
        t3 = resolve_window(WindowSpec(WindowRule.TRAILING_MONTHS, 1), D(2025, 3, 31), Inception(D(2024, 1, 1), False), "X").window
        self.assertEqual((t3.start, t3.months), (D(2025, 2, 28), 1))
        # a snapshot: a window before the snapshot date S is NOT_RECONSTRUCTABLE; since inception is "since S"
        snap = Inception(D(2025, 4, 1), True)
        before = resolve_window(WindowSpec(WindowRule.CUSTOM, custom_base=D(2025, 3, 31)), D(2025, 4, 3), snap, "NOT_RECONSTRUCTABLE")
        self.assertEqual((before.window, before.reason), (None, "NOT_RECONSTRUCTABLE"))
        since = resolve_window(WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), snap, "X").window
        self.assertTrue(since.since_snapshot)
        self.assertEqual(resolve_window(WindowSpec(WindowRule.CUSTOM, custom_base=D(2025, 4, 3)), D(2025, 4, 3), young, "X").cause.detail,
                         "WINDOW_NOT_POSITIVE")
        self.assertEqual(resolve_window(WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), Inception(None, False), "X").cause.detail,
                         "NO_LIVE_LEDGER_EVENTS")


# ===== reason priority and totals (Rulings 1.4, 1.5) ===================================================================

class PriorityTests(unittest.TestCase):
    RULING_ORDER = ["CALCULATION_ERROR", "LEDGER_INCONSISTENT", "NOT_RECONSTRUCTABLE", "SOURCE_CONFLICT", "UNRESOLVED_CONVENTION",
                    "UNSUPPORTED_ASSET", "MISSING_BENCHMARK", "MISSING_COST_BASIS", "MISSING_PRICE_HISTORY", "MISSING_FX_HISTORY"]  # performance/1.2 Q2: MISSING_BENCHMARK is 7th

    def test_the_priority_order_is_the_rulings_and_the_stale_code_comes_last(self):
        ordered = [c.value for c in REASON_PRIORITY]
        self.assertEqual(ordered[:10], self.RULING_ORDER)
        self.assertEqual(ordered.index("MISSING_BENCHMARK"), 6)
        self.assertEqual(ordered[-1], "STALE_DATA")
        agg = PerformanceAggregation()
        for i, higher in enumerate(self.RULING_ORDER):
            for lower in self.RULING_ORDER[i + 1:] + ["STALE_DATA"]:
                parts = [insufficient_part("a", lower, "x"), insufficient_part("b", higher, "y")]
                self.assertEqual(agg.combine(parts).reason, higher, (higher, lower))

    def test_example_v2d_a_missing_price_outranks_staleness_and_lineage_lists_both(self):
        agg = PerformanceAggregation().combine([limited_part("h", "STALE_DATA", "3 sessions missed"),
                                                  insufficient_part("a-share", "MISSING_PRICE_HISTORY", "NO_ADMITTED_SOURCE")])
        self.assertEqual((agg.state, agg.reason), (INSUFFICIENT, "MISSING_PRICE_HISTORY"))
        self.assertEqual({c.ref for c in agg.causes}, {"h", "a-share"})

    def test_states_combine_worst_of_and_a_one_session_stale_part_keeps_available_with_stale_data(self):
        agg = PerformanceAggregation()
        clean = Part("c", AVAILABLE)
        stale1 = Part("s", AVAILABLE, "STALE_DATA", ())
        self.assertEqual((agg.combine([clean, stale1]).state, agg.combine([clean, stale1]).reason), (AVAILABLE, "STALE_DATA"))
        self.assertEqual((agg.combine([clean]).state, agg.combine([clean]).reason), (AVAILABLE, None))
        lim = agg.combine([clean, limited_part("l", "STALE_DATA", "n")])
        self.assertEqual((lim.state, lim.reason), (LIMITED, "STALE_DATA"))
        self.assertEqual(agg.combine([insufficient_part("i", None, "freshness unknown"), clean]).state, INSUFFICIENT)


# ===== pure TWR over given valuations: Example W, zero capital, non-positive base =======================================

def vf(day, cls, amount, n=[0]):
    n[0] += 1
    timing = {FlowClass.EXTERNAL_INFLOW_CASH: FlowTiming.START}.get(cls, FlowTiming.END)
    ev = ClassifiedEvent(n[0], uuid.UUID(int=n[0]), pk.A1, day, "X", cls, timing, "USD", None, None, None, False)
    return ValuedFlow(ev, cls, timing, Valued(AVAILABLE, None, F(amount), ()))


def valuations(table: Dict[datetime.date, Fraction], calls=None):
    def v(day):
        if calls is not None:
            calls.append(day)
        if day not in table:
            raise AssertionError(f"the valuation of {day} was requested but is not an input of the TWR (Ruling 5.2)")
        value = table[day]
        return Valued(INSUFFICIENT, None, None, (Cause(f"v@{day}", "INSUFFICIENT_DATA", None, "no value"),)) if value is None \
            else Valued(AVAILABLE, None, value, ())
    return v


class TwrPureTests(unittest.TestCase):
    V = {D(2025, 3, 31): F(0), D(2025, 4, 1): F(70811, 7), D(2025, 4, 2): F(359950, 39), D(2025, 4, 3): F(360850, 39)}
    FLOWS = (vf(D(2025, 4, 1), FlowClass.EXTERNAL_INFLOW_CASH, 10000), vf(D(2025, 4, 2), FlowClass.EXTERNAL_OUTFLOW_CASH, 1000))

    def test_example_w_segment_form(self):
        # 1 + TWR = [(V2 + O2)/(V0 + I1)] x [V3/V2] = (398,950/39 / 10,000) x (360,850/359,950) = 7,979/7,800 x 7,217/7,199
        #         = 57,584,443 / 56,152,200  =>  TWR = 1,432,243 / 56,152,200   (7,979 x 7,217 = 57,584,443 ; 7,800 x 7,199 = 56,152,200)
        out = twr_segments(D(2025, 3, 31), D(2025, 4, 3), self.FLOWS, valuations(self.V), PERF)
        self.assertEqual((out.valued.state, out.valued.exact), (AVAILABLE, F(1432243, 56152200)))
        self.assertEqual(F(7979, 7800) * F(7217, 7199), F(57584443, 56152200))
        # G = V3 - V0 - (10,000 - 1,000) = 360,850/39 - 351,000/39 = 9,850/39
        g = absolute_gain(D(2025, 3, 31), D(2025, 4, 3), self.FLOWS, valuations(self.V), PERF)
        self.assertEqual(g.exact, F(9850, 39))

    def test_only_the_flow_day_valuations_are_inputs_and_an_interior_gap_does_not_touch_the_twr(self):
        # a longer window starting 03-28 over an empty portfolio: the days 03-29 and 03-30 are NOT inputs (Ruling 5.2). The run 03-28..03-31 is 0/0 = 1.
        table = dict(self.V)
        table[D(2025, 3, 28)] = F(0)
        calls = []
        out = twr_segments(D(2025, 3, 28), D(2025, 4, 3), self.FLOWS, valuations(table, calls), PERF)
        self.assertEqual(out.valued.exact, F(1432243, 56152200))
        self.assertEqual(sorted(set(calls)), sorted(table))  # exactly B, E and d-1, d of each flow day; 03-29 and 03-30 never asked
        self.assertIn("ZERO_CAPITAL_RUN", out.details)
        # an INSUFFICIENT valuation on an interior NON-flow day (04-02 is a flow day, so use a window whose flows skip a day) does not matter
        flows = (vf(D(2025, 4, 1), FlowClass.EXTERNAL_INFLOW_CASH, 10000),)
        table2 = {D(2025, 3, 31): F(0), D(2025, 4, 1): F(70811, 7), D(2025, 4, 3): F(360850, 39)}  # 04-02 is not a key: asking for it would fail
        out2 = twr_segments(D(2025, 3, 31), D(2025, 4, 3), flows, valuations(table2), PERF)
        # 1 + TWR = [V1/(V0 + 10,000)] x [V3/V1] = V3/10,000 = 360,850/(39 x 10,000) = 36,085/39,000 = 7,217/7,800 ; TWR = 7,217/7,800 - 1 = -583/7,800
        self.assertEqual(out2.valued.exact, F(-583, 7800))

    def test_a_required_valuation_that_is_insufficient_makes_the_twr_insufficient_with_its_cause(self):
        table = dict(self.V)
        table[D(2025, 4, 2)] = None  # a flow day's valuation: required
        out = twr_segments(D(2025, 3, 31), D(2025, 4, 3), self.FLOWS, valuations(table), PERF)
        self.assertEqual((out.valued.state, out.valued.exact), (INSUFFICIENT, None))
        self.assertTrue(any(c.ref == "v@2025-04-02" for c in out.valued.causes))

    def test_zero_over_zero_is_one_and_any_other_non_positive_base_is_insufficient_with_the_detail(self):
        self.assertEqual(ratio(F(0), F(0)), (F(1), "ZERO_CAPITAL_RUN"))
        self.assertEqual(ratio(F(3), F(2)), (F(3, 2), ""))
        self.assertEqual(ratio(F(3), F(0)), (None, "NON_POSITIVE_BASE"))
        self.assertEqual(ratio(F(3), F(-5)), (None, "NON_POSITIVE_BASE"))
        # a purchase recorded before its funding deposit: V(d-1) = -5, an inflow of 5 gives a base of 0 and a non-zero numerator
        table = {D(2025, 4, 1): F(-5), D(2025, 4, 2): F(3), D(2025, 3, 31): F(-5)}
        flows = (vf(D(2025, 4, 2), FlowClass.EXTERNAL_INFLOW_CASH, 5),)
        out = twr_segments(D(2025, 3, 31), D(2025, 4, 2), flows, valuations(table), PERF)
        self.assertEqual((out.valued.state, out.valued.exact, out.valued.reason), (INSUFFICIENT, None, None))  # reason none (Ruling 5.3)
        self.assertIn("NON_POSITIVE_BASE", out.details)
        self.assertTrue(any(c.detail == "NON_POSITIVE_BASE" for c in out.valued.causes))

    def test_a_limited_input_gives_limited_stale_data_and_stale_propagates(self):
        def v(day):
            if day == D(2025, 4, 3):
                return Valued(LIMITED, "STALE_DATA", self.V[day], (Cause("v", "LIMITED", "STALE_DATA", "3 sessions"),))
            return valuations(self.V)(day)

        out = twr_segments(D(2025, 3, 31), D(2025, 4, 3), self.FLOWS, v, PERF)
        self.assertEqual((out.valued.state, out.valued.reason, out.valued.exact), (LIMITED, "STALE_DATA", F(1432243, 56152200)))

    def test_no_flows_is_the_ratio_of_the_end_values(self):
        out = twr_segments(D(2025, 3, 31), D(2025, 4, 2), (), valuations({D(2025, 3, 31): F(100), D(2025, 4, 2): F(105)}), PERF)
        self.assertEqual(out.valued.exact, F(1, 20))  # 105/100 - 1; with no flow inside the window TWR = the end ratio (identity I-6 for the TWR side)


# ===== annualization (Ruling 7) ============================================================================================

class AnnualizationTests(unittest.TestCase):
    def test_example_a1_three_years_at_0331_is_exactly_ten_percent(self):
        # (1.331)^(1/3) - 1: 1.1^3 = 1.331, so 0.1 exactly; exp(ln(1.331)/3) at precision 50, presented at 12 decimals
        out = annualize(Valued(AVAILABLE, None, F(331, 1000), ()), F(3), PERF)
        self.assertEqual(out.valued.state, AVAILABLE)
        self.assertLess(abs(out.valued.exact - F(1, 10)), F(1, 10 ** 40))  # the 50-digit step is within 1e-40 of the true root
        m = build_metric("return_annualized", "PERIOD", (), out.valued, None, PerformanceRounding(), WindowUsed(D(2022, 1, 1), D(2025, 1, 1)), "t",
                         False, False, point=RoundingPoint.PRESENT_RETURN, unit="RATE_PER_YEAR", numeric_basis=DECIMAL_PREC50)
        self.assertEqual(m.result.value, Decimal("0.100000000000"))
        self.assertEqual(m.numeric_basis, DECIMAL_PREC50)

    def test_a_window_shorter_than_one_year_is_insufficient_never_annualized(self):
        out = annualize(Valued(AVAILABLE, None, F(5, 100), ()), F(200, 365), PERF)  # a 200-day window: Y < 1
        self.assertEqual((out.valued.state, out.valued.exact, out.valued.reason), (INSUFFICIENT, None, None))
        self.assertEqual(out.details, ("PERIOD_SHORTER_THAN_ONE_YEAR",))
        self.assertEqual(annualize(Valued(AVAILABLE, None, F(5, 100), ()), F(1), PERF).valued.exact is not None, True)  # exactly one year: allowed

    def test_total_loss_and_an_insufficient_twr(self):
        self.assertEqual(annualize(Valued(AVAILABLE, None, F(-1), ()), F(2), PERF).details, ("TOTAL_LOSS",))
        bad = annualize(Valued(INSUFFICIENT, "SOURCE_CONFLICT", None, (Cause("a", "INSUFFICIENT_DATA", "SOURCE_CONFLICT", ""),)), F(2), PERF)
        self.assertEqual((bad.valued.state, bad.valued.reason), (INSUFFICIENT, "SOURCE_CONFLICT"))  # the TWR's state is inherited

    def test_the_annualized_figure_inherits_a_limited_state_and_exactly_one_year_gives_the_twr_itself(self):
        out = annualize(Valued(LIMITED, "STALE_DATA", F(1, 10), (Cause("v", "LIMITED", "STALE_DATA", "n"),)), F(1), PERF)
        self.assertEqual((out.valued.state, out.valued.reason), (LIMITED, "STALE_DATA"))
        self.assertLess(abs(out.valued.exact - F(1, 10)), F(1, 10 ** 40))  # (1.1)^(1/1) - 1 = 0.1


# ===== the engine over Example W =====================================================================================

class ExampleWEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = pk.world_w()
        cls.ledger = pk.example_w_ledger(cls.w.h)

    def run_window(self, spec=None, end=D(2025, 4, 3), **kw):
        return compute_window(self.ledger.rows, self.ledger.version, spec or WindowSpec(WindowRule.SINCE_INCEPTION), end, USD, self.w.store,
                              self.w.ident, self.w.market, PERF, **kw)

    def test_the_valuations_of_example_w(self):
        # V1 = 5,000 + (790 + 39,000) x 9/70 = 70,811/7 ; V2 = 4,000 + (790 + 40,000) x 5/39 = 359,950/39 ; V3 = 4,000 + (970 + 40,000) x 5/39 = 360,850/39
        for day, exact in ((D(2025, 4, 1), F(70811, 7)), (D(2025, 4, 2), F(359950, 39)), (D(2025, 4, 3), F(360850, 39))):
            res = compute(self.ledger.rows, self.ledger.version, day, USD, self.w.store, self.w.ident, self.w.market, PERF)
            total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
            self.assertEqual((total.exact, total.result.sufficiency_state), (exact, AVAILABLE), day)
        # Example V-1 (2025-04-02): H 200,000/39 -> 5,128.21 ; cash HKD 3,950/39 -> 101.28 ; cash USD 4,000 ; total 9,229.49
        res = compute(self.ledger.rows, self.ledger.version, D(2025, 4, 2), USD, self.w.store, self.w.ident, self.w.market, PERF)
        shown = {m.subject[0][1] if m.metric_id == "cash_value" else "h": m.result.value for m in res.metrics
                 if m.view == "REPORTING" and m.metric_id in ("holding_value", "cash_value")}
        self.assertEqual(shown["h"], Decimal("5128.21"))
        self.assertEqual(shown["HKD" if "HKD" in shown else "h"], Decimal("101.28") if "HKD" in shown else Decimal("5128.21"))
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual(total.result.value, Decimal("9229.49"))
        # the displayed breakdown sums to the displayed total: 5,128.21 + 101.28 + 4,000.00 = 9,229.49
        self.assertEqual(sum(d for _r, d, _e in total.breakdown), Decimal("9229.49"))

    def test_twr_gain_and_identities_i2_i3_hold_exactly(self):
        res = self.run_window(verify_identities=True)
        twr, gain, ann = metric(res, "return_twr"), metric(res, "gain_absolute"), metric(res, "return_annualized")
        self.assertEqual((twr.exact, twr.result.value, twr.result.sufficiency_state), (F(1432243, 56152200), Decimal("0.025506444983"), AVAILABLE))
        self.assertEqual((gain.exact, gain.result.value), (F(9850, 39), Decimal("252.56")))  # 9,850/39 = 252.5641...
        self.assertEqual(twr.window, WindowUsed(D(2025, 3, 31), D(2025, 4, 3), None, "SINCE_INCEPTION"))
        self.assertEqual((twr.window.days, twr.unit, ann.result.value), (3, "RATIO", None))
        self.assertEqual(ann.details, ("PERIOD_SHORTER_THAN_ONE_YEAR",))  # 3 days: never annualized
        self.assertEqual(twr.details, ())
        self.assertIn(("flow_days", "2"), twr.lineage)
        self.assertTrue(res.manifest.synthetic and twr.synthetic)
        self.assertEqual((res.manifest.window.rule, res.manifest.as_of), ("SINCE_INCEPTION", D(2025, 4, 3)))

    def test_a_window_before_inception_is_insufficient_for_all_three_metrics_with_the_detail(self):
        res = self.run_window(WindowSpec(WindowRule.TRAILING_MONTHS, 12))
        for m in res.metrics:
            self.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code), (None, INSUFFICIENT, None), m.metric_id)
            self.assertIn("WINDOW_BEFORE_INCEPTION", m.details)

    def test_reproduce_a_window_manifest_and_a_changed_ledger_is_named(self):
        res = self.run_window()
        report = reproduce(res.manifest, res.result_digest, self.ledger.rows, self.w.store, self.w.ident, self.w.market, PERF)
        self.assertEqual(report.status, ReproductionStatus.REPRODUCED)
        again = self.run_window()
        self.assertEqual(res.canonical_json(), again.canonical_json())
        altered = list(self.ledger.rows)
        altered[0] = type(altered[0])(1, dataclasses.replace(altered[0].event, amount=self.ledger.money("10001", USD)))
        self.assertEqual(reproduce(res.manifest, res.result_digest, altered, self.w.store, self.w.ident, self.w.market, PERF).status,
                         ReproductionStatus.LEDGER_DIGEST_MISMATCH)

    def test_the_manifest_cites_the_new_convention_ids_and_the_files_read_including_flow_dates(self):
        res = self.run_window()
        conv = dict(res.manifest.conventions)
        self.assertEqual((conv["performance.convention_set"], conv["market_data.convention_set"]), ("performance/1.12", "market-data/1.16"))
        self.assertEqual(conv["performance.windows"], "performance/1.12#5.4")
        self.assertEqual(conv["performance.lot_method"], "FIFO/1")
        self.assertTrue(res.manifest.consumed_files())
        refs = {r.kind.value: (r.range_start, r.range_end) for r in res.manifest.data_set_refs}
        self.assertEqual(refs["FX"], (D(2025, 3, 31), D(2025, 4, 3)))


# ===== flow-date FX, in-kind flows, scope =============================================================================

class FlowTests(unittest.TestCase):
    def test_a_foreign_cash_flow_is_translated_at_its_own_dates_fixing(self):
        # DEPOSIT 7,800 HKD on 04-01 (X = 9/70): I^C = 7,800 x 9/70 = 70,200/70 = 7,020/7. V1 = 7,020/7. On 04-02 (X = 5/39) V2 = 7,800 x 5/39 = 1,000.
        # TWR = (V1/I^C) x (V2/V1) = 1 x 1,000/(7,020/7) = 7,000/7,020 = 350/351 - 1 = -1/351 ; G = V2 - 0 - I^C = 1,000 - 7,020/7 = -20/7.
        # (translated at the VALUATION date's rate the flow would be 1,000, G = 0 and TWR = 0: the flow date matters, PRD 8.3)
        w = pk.world_w()
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), HKD, amount=pk.Money(Decimal(7800), HKD))
        res = compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF,
                             verify_identities=True)
        self.assertEqual(metric(res, "return_twr").exact, F(-1, 351))
        self.assertEqual(metric(res, "return_twr").result.value, Decimal("-0.002849002849"))   # -1/351 = -0.002849002849002...
        self.assertEqual(metric(res, "gain_absolute").exact, F(-20, 7))
        self.assertEqual(metric(res, "gain_absolute").result.value, Decimal("-2.86"))          # -2.857142... half away from zero

    def test_an_in_kind_transfer_is_valued_at_the_close_and_fixing_of_its_date_at_the_end_of_the_day(self):
        # TRANSFER_IN H 100 on 04-02 (external, in kind): I^K = 100 x 400.00 x 5/39 = 200,000/39 at the 04-02 close and fixing. V(04-01) = 0 (nothing yet).
        # 04-02: base beta = V1 + I^C = 0, numerator V2 + O - I^K = 0: 0/0 -> 1 (ZERO_CAPITAL_RUN). 04-03 close 410.00: V3 = 100 x 410 x 5/39 = 205,000/39.
        # 1 + TWR = V3/V2 = 205,000/200,000 = 41/40 -> TWR = 1/40 ; G = V3 - V1 - I^K = 205,000/39 - 200,000/39 = 5,000/39 = 128.205...
        w = pk.world_w(closes={**pk.H_CLOSES, D(2025, 4, 3): "410.00"})
        L = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 4, 2), HKD, listing_id=w.h, quantity=Decimal(100))
        res = compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), USD, w.store, w.ident, w.market, PERF,
                             verify_identities=True)
        twr, gain = metric(res, "return_twr"), metric(res, "gain_absolute")
        self.assertEqual((twr.exact, twr.result.value), (F(1, 40), Decimal("0.025")))
        self.assertIn("ZERO_CAPITAL_RUN", twr.details)
        self.assertEqual((gain.exact, gain.result.value), (F(5000, 39), Decimal("128.21")))
        classes = [c.flow_class for c in classify_events(L.rows, L.version, PERF.flows)]
        self.assertEqual(classes, [FlowClass.EXTERNAL_INFLOW_KIND])
        self.assertEqual(classify_events(L.rows, L.version, PERF.flows)[0].timing, FlowTiming.END)  # in kind: the END of the day (Ruling 4.2)

    def test_internal_transfers_are_neutral_at_portfolio_level_and_flows_at_account_scope(self):
        w = pk.world_w()
        L = pk.Ledger()
        usd = lambda a: pk.Money(Decimal(a), USD)  # noqa: E731
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=usd(1000))
        L.add(pk.A1, EventType.TRANSFER_OUT, D(2025, 4, 2), USD, amount=usd(600), counterparty_account_id=pk.A2)
        L.add(pk.A2, EventType.TRANSFER_IN, D(2025, 4, 2), USD, amount=usd(600), counterparty_account_id=pk.A1)
        by_scope = {None: [FlowClass.EXTERNAL_INFLOW_CASH, FlowClass.INTERNAL_TRANSFER, FlowClass.INTERNAL_TRANSFER],
                    pk.A1: [FlowClass.EXTERNAL_INFLOW_CASH, FlowClass.EXTERNAL_OUTFLOW_CASH], pk.A2: [FlowClass.EXTERNAL_INFLOW_CASH]}
        for scope, expected in by_scope.items():
            self.assertEqual([c.flow_class for c in classify_events(L.rows, L.version, PERF.flows, scope)], expected, scope)
        run = lambda scope: compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 2), USD, w.store, w.ident,  # noqa: E731
                                           w.market, PERF, account_scope=scope, verify_identities=True)
        # portfolio: V1 = V2 = 1,000, one deposit of 1,000: TWR = 1,000/1,000 x 1,000/1,000 - 1 = 0 ; G = 1,000 - 0 - 1,000 = 0
        p = run(None)
        self.assertEqual((metric(p, "return_twr").exact, metric(p, "gain_absolute").exact), (F(0), F(0)))
        # account A1: V1 = 1,000, V2 = 400; flows I^C 1,000 (04-01), O 600 (04-02): day 2 factor (400 + 600)/(1,000) = 1 ; G = 400 - 0 - (1,000 - 600) = 0
        a1 = run(pk.A1)
        self.assertEqual((metric(a1, "return_twr").exact, metric(a1, "gain_absolute").exact), (F(0), F(0)))
        self.assertEqual(a1.manifest.scope, f"ACCOUNT:{pk.A1}")
        # account A2: inception = the day before its first event = 04-01; I^C 600 on 04-02: factor (600 + 0)/(0 + 600) = 1 ; G = 600 - 0 - 600 = 0
        a2 = run(pk.A2)
        self.assertEqual((metric(a2, "return_twr").exact, metric(a2, "gain_absolute").exact), (F(0), F(0)))
        self.assertEqual(a2.metrics[0].window.start, D(2025, 4, 1))

    def test_a_flow_that_cannot_be_translated_makes_every_return_over_its_window_insufficient(self):
        w = pk.world_w()
        cnh = CurrencyCode("CNH")
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), cnh, amount=pk.Money(Decimal(1000), cnh))
        res = compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        for mid in ("return_twr", "gain_absolute"):
            m = metric(res, mid)
            self.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code), (None, INSUFFICIENT, ReasonCode.MISSING_FX_HISTORY))


# ===== valuation rulings: CNH, stale weight, freshness, partial, current mode ==================================================

class ValuationRulingTests(unittest.TestCase):
    def test_a_cnh_amount_makes_the_total_insufficient_and_the_partial_figure_excludes_it(self):
        # market-data/1.8: an aggregate that includes a CNH amount is INSUFFICIENT_DATA + MISSING_FX_HISTORY (not LIMITED). Example V-2(c).
        w = pk.world_w()
        cnh = CurrencyCode("CNH")
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 4, 2), USD, amount=pk.Money(Decimal(4000), USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 2), cnh, amount=pk.Money(Decimal(1000), cnh))
        res = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual((total.result.value, total.result.sufficiency_state, total.result.reason_code),
                         (None, INSUFFICIENT, ReasonCode.MISSING_FX_HISTORY))
        native_cnh = [m for m in res.metrics if m.metric_id == "cash_value" and m.view == "NATIVE" and m.currency == "CNH"][0]
        self.assertEqual((native_cnh.result.value, native_cnh.result.sufficiency_state), (Decimal("1000"), AVAILABLE))  # in CNH it is a fact
        (part,) = [m for m in res.metrics if m.partial]
        self.assertEqual((part.result.value, [e.kind for e in part.excluded], [e.native for e in part.excluded]), (Decimal("4000.00"), ["CASH"], ["1000"]))
        self.assertEqual(market11.FX_CALENDAR_KEY, current.ECB_CALENDAR_ID)

    def test_example_v2a_stale_three_sessions_is_limited_with_the_stale_weight_and_the_freshness_vector(self):
        # H's last print is 2025-03-28; as of 2025-04-02 the sessions 03-31, 04-01, 04-02 are missed: 3 (LIMITED + STALE_DATA, market-data table).
        # total = 200,000/39 (H) + 3,950/39 (HKD 790) + 4,000 = 359,950/39 = 9,229.487... -> 9,229.49 LIMITED + STALE_DATA
        # stale weight = (200,000/39) / (359,950/39) = 200,000/359,950 = 4,000/7,199 = 0.5556327267676... -> 0.555632726768 (12 decimals)
        w = pk.world_w(closes={D(2025, 3, 28): "400.00"})
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(4000), USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), HKD, amount=pk.Money(Decimal(790), HKD))
        L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
        res = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual((total.result.value, total.result.sufficiency_state, total.result.reason_code),
                         (Decimal("9229.49"), LIMITED, ReasonCode.STALE_DATA))
        self.assertEqual((total.exact, total.stale_weight), (F(359950, 39), F(4000, 7199)))
        self.assertEqual(total.stale_weight_presented, Decimal("0.555632726768"))
        # performance/1.2 Ruling 1.6 (Q1): ONE entry per exchange CALENDAR (keyed by calendar id), listing the MICs it governs among the holdings
        fresh = {(e.kind, e.key): (e.date_used, e.missed, e.state) for e in total.freshness.entries}
        self.assertEqual(fresh, {("EXCHANGE_CALENDAR", "HKEX_SESSIONS"): (D(2025, 3, 28), 3, "STALE"), ("CURRENCY", "HKD"): (D(2025, 4, 2), 0, "CURRENT")})
        self.assertEqual({(e.key, e.mics) for e in total.freshness.entries if e.kind == "EXCHANGE_CALENDAR"}, {("HKEX_SESSIONS", ("XHKG",))})
        self.assertEqual((total.freshness.summary, total.freshness.delays), ("STALE", ("END_OF_DAY",)))
        h = [m for m in res.metrics if m.metric_id == "holding_value" and m.view == "NATIVE"][0]
        self.assertEqual((h.result.value, h.result.sufficiency_state, h.result.reason_code), (Decimal("40000.00"), LIMITED, ReasonCode.STALE_DATA))
        # Example V-2(d): add an A-share with no admitted source: INSUFFICIENT + MISSING_PRICE_HISTORY (priority 8 over STALE_DATA 10), lineage lists both
        cn = pk.x.lid(w.ident, "600519", "XSHG")
        L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), pk.CNY, listing_id=cn, quantity=Decimal(100))
        res2 = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        total2 = [m for m in res2.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual((total2.result.value, total2.result.reason_code), (None, ReasonCode.MISSING_PRICE_HISTORY))
        self.assertTrue({"STALE_DATA", "MISSING_PRICE_HISTORY"} <= {c.reason for c in total2.causes})

    def test_the_freshness_of_a_value_dated_the_as_of_date_is_current(self):
        w = pk.world_w()
        res = compute(pk.example_w_ledger(w.h).rows, 7, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual((total.freshness.summary, total.result.reason_code), ("CURRENT", None))


def choose(t, rows, version, w, reporting=USD):
    return current.choose_current_date(t, rows, version, w.calendars, w.ident.exchange_mic, reporting, w.ident.trading_currency)


class CurrentModeTests(unittest.TestCase):
    T = datetime.datetime(2025, 4, 2, 14, 30, tzinfo=datetime.timezone.utc)

    def ledger(self, w, with_us=False):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(4000), USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), HKD, amount=pk.Money(Decimal(790), HKD))
        L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
        if with_us:
            L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), USD, listing_id=w.aapl, quantity=Decimal(10))
        return L

    def test_example_v3_the_latest_date_whose_every_close_and_fixing_has_happened(self):
        # t = 2025-04-02 14:30 UTC. HKEX close 16:10 Asia/Hong_Kong (UTC+8) = 08:10 UTC <= t ; ECB publication 16:00 Europe/Berlin (CEST, UTC+2) = 14:00 UTC <= t.
        w = pk.World(pk.example_w_readings(pk.x.lid(pk.x.identity(), "0700", "XHKG")))
        L = self.ledger(w)
        got = choose(self.T, L.rows, L.version, w)
        self.assertEqual((got.date, got.causes), (D(2025, 4, 2), ()))
        # add a NYSE listing: its close of 04-02 is 16:00 EDT (UTC-4) = 20:00 UTC > t, so 04-02 is not eligible: D_c = 2025-04-01
        L2 = self.ledger(w, with_us=True)
        got2 = choose(self.T, L2.rows, L2.version, w)
        self.assertEqual(got2.date, D(2025, 4, 1))
        # after the US close (21:00 UTC) the same portfolio is current as of 04-02 again
        late = datetime.datetime(2025, 4, 2, 21, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(choose(late, L2.rows, L2.version, w).date, D(2025, 4, 2))
        # Friday 2025-04-04 after every close (HK 08:10, ECB 14:00, NYSE 20:00 UTC): current as of 04-04
        fri = datetime.datetime(2025, 4, 4, 23, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(choose(fri, L2.rows, L2.version, w).date, D(2025, 4, 4))
        # Saturday 04-05 is past the calendars' coverage (they end 04-04): the choice cannot be made and fails closed (never a weekday guess)
        sat = datetime.datetime(2025, 4, 5, 12, 0, tzinfo=datetime.timezone.utc)
        self.assertIsNone(choose(sat, L2.rows, L2.version, w).date)

    def test_a_position_in_a_foreign_listing_needs_the_days_fixing_even_with_no_foreign_cash(self):
        # performance/1.1 Ruling 1.7 (finding 1): only H 100 is held (HKD listing, R = USD), no cash. At t = 2025-04-02 13:00 UTC the HKEX close (08:10 UTC) has
        # happened but the ECB publication (16:00 CEST = 14:00 UTC) has not, and H's value in USD needs the 04-02 fixing: so D_c = 2025-04-01. (Looking only at
        # cash would have chosen 04-02 and valued H with a fixing that did not yet exist.)
        w = pk.World(pk.example_w_readings(pk.x.lid(pk.x.identity(), "0700", "XHKG")))
        L = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
        t = datetime.datetime(2025, 4, 2, 13, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(choose(t, L.rows, L.version, w).date, D(2025, 4, 1))
        # after the publication the position is current as of 04-02
        self.assertEqual(choose(self.T, L.rows, L.version, w).date, D(2025, 4, 2))
        # a USD-listed position needs no fixing at all (R = USD): the 04-02 NYSE close at 20:00 UTC is what decides
        L_us = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), USD, listing_id=w.aapl, quantity=Decimal(10))
        self.assertEqual(choose(datetime.datetime(2025, 4, 2, 20, 30, tzinfo=datetime.timezone.utc), L_us.rows, L_us.version, w).date,
                         D(2025, 4, 2))

    def test_the_hkex_close_is_calendar_data_a_1600_close_would_make_the_date_eligible_earlier(self):
        # 16:10 HKT = 08:10 UTC. At t = 08:05 UTC on 2025-04-02 the 16:10 close has not happened (D_c = 04-01) but a 16:00 close (08:00 UTC) has: the rule is
        # `scheduled_close <= t` and the close time is DATA (market-data/1.8), never a constant in the engine.
        t = datetime.datetime(2025, 4, 2, 8, 5, tzinfo=datetime.timezone.utc)
        probe = pk.x.lid(pk.x.identity(), "0700", "XHKG")
        events_w = pk.World(pk.example_w_readings(probe))
        L = self.ledger(events_w)
        hk_only = [e for e in L.rows if e.event.event_type is not EventType.DEPOSIT or e.event.currency == HKD]
        # 4,000 USD cash is a foreign amount, so the ECB is also needed: on 04-02 its publication (14:00 UTC) is after t, so use HKD cash only
        hk_only = [e for e in L.rows if not (e.event.currency == USD)]
        self.assertEqual(choose(t, hk_only, L.version, events_w, HKD).date, D(2025, 4, 1))
        early = pk.World(pk.example_w_readings(probe), hk_close=datetime.time(16, 0))
        self.assertEqual(choose(t, hk_only, L.version, early, HKD).date, D(2025, 4, 2))

    def test_a_calendar_that_does_not_cover_the_candidate_date_fails_closed_with_no_code(self):
        w = pk.World(pk.example_w_readings(pk.x.lid(pk.x.identity(), "0700", "XHKG")), calendar_to=D(2025, 4, 1))
        L = self.ledger(w)
        got = choose(self.T, L.rows, L.version, w)
        self.assertIsNone(got.date)
        self.assertEqual(got.causes[0].detail, "CALENDAR_COVERAGE_GAP")
        res = compute_current(L.rows, L.version, self.T, USD, w.ident, w.market_at, PERF, suppressions=())
        (m,) = res.metrics
        self.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code), (None, INSUFFICIENT, None))
        self.assertIn("CALENDAR_COVERAGE_GAP", m.details)
        self.assertEqual(res.manifest.as_of_rule, "D_c(t)")

    def test_current_value_is_the_historical_valuation_at_d_c_with_both_recorded_in_the_manifest(self):
        probe = pk.x.lid(pk.x.identity(), "0700", "XHKG")
        w = pk.World(pk.example_w_readings(probe))
        L = self.ledger(w)
        res = compute_current(L.rows, L.version, self.T, USD, w.ident, w.market_at, PERF, suppressions=())
        self.assertEqual((res.manifest.as_of, res.manifest.instant, res.manifest.as_of_rule, res.manifest.valuation_mode),
                         (D(2025, 4, 2), self.T, "D_c(t)", "CURRENT_AT_INSTANT"))  # the Current value of PD-0015 Part 1, not "historical" (performance/1.12 build note)
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        # 04-02: H 100 x 400.00 x 5/39 = 200,000/39 ; HKD 790 x 5/39 = 3,950/39 ; USD 4,000: 359,950/39 = 9,229.49
        self.assertEqual((total.exact, total.result.value), (F(359950, 39), Decimal("9229.49")))
        self.assertEqual(reproduce(res.manifest, res.result_digest, L.rows, w.store, w.ident, w.market, PERF, market_at=w.market_at).status,
                         ReproductionStatus.REPRODUCED)
        # a LIVE request is still refused with an explicit state
        from performance.inputs import ValuationMode  # noqa: PLC0415

        refused = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF, mode=ValuationMode.CURRENT_LIVE)
        self.assertIn("UNSUPPORTED_VALUATION_MODE", refused.metrics[0].details)

    def test_only_files_retrieved_at_or_before_the_instant_are_read(self):
        probe = pk.x.lid(pk.x.identity(), "0700", "XHKG")
        late = datetime.datetime(2025, 4, 2, 15, 0, tzinfo=datetime.timezone.utc)  # after t = 14:30
        readings = [r for r in pk.example_w_readings(probe) if not (hasattr(r.observation, "price") and r.observation.value_date == D(2025, 4, 2))]
        late_sha = "9" * 64
        readings.append(pk.quote(probe, D(2025, 4, 2), "999.00", HKD, "HK", retrieved=late, sha=late_sha))
        w = pk.World(readings)
        L = self.ledger(w)
        res = compute_current(L.rows, L.version, self.T, USD, w.ident, w.market_at, PERF, suppressions=())
        h = [m for m in res.metrics if m.metric_id == "holding_value" and m.view == "NATIVE"][0]
        # performance/1.2 Ruling 1.7 (Q6): M_t is a DERIVED release without the late file, so its 999.00 can neither be the value nor be seen at all: the last print
        # in M_t is 04-01's 390.00, one session stale (AVAILABLE with stale data, the freshness vector says so)
        self.assertEqual(h.exact, F(39000))
        self.assertNotEqual(h.exact, F(99900))
        # t, M and the excluded file hashes are in the manifest; the release id is M_t's, the parent is M's
        self.assertEqual(res.manifest.excluded_files, (late_sha,))
        self.assertEqual(res.manifest.parent_release_id, w.store.release_id())
        self.assertNotEqual(res.manifest.release_id, res.manifest.parent_release_id)
        self.assertEqual(res.manifest.instant, self.T)
        # the derived release is a deterministic function of (M, t)
        again = compute_current(L.rows, L.version, self.T, USD, w.ident, w.market_at, PERF, suppressions=())
        self.assertEqual(again.result_digest, res.result_digest)
        # a later instant includes the file
        after = compute_current(L.rows, L.version, datetime.datetime(2025, 4, 2, 16, 0, tzinfo=datetime.timezone.utc), USD, w.ident, w.market_at, PERF,
                                suppressions=())
        h2 = [m for m in after.metrics if m.metric_id == "holding_value" and m.view == "NATIVE"][0]
        self.assertEqual((after.manifest.excluded_files, h2.exact), ((), F(99900)))


# ===== market-data/1.8 alignment ===================================================================================

class MarketData18Tests(unittest.TestCase):
    def test_the_ecb_fixing_instant_is_1410_and_the_convention_id_is_18_everywhere(self):
        from marketdata import manifest as mdm, profiles  # noqa: PLC0415
        from marketdata.adapters import frankfurter  # noqa: PLC0415

        self.assertEqual((ECB_FIXING_TIME.hour, ECB_FIXING_TIME.minute), (14, 10))
        self.assertEqual((frankfurter.FIXING_TIME.hour, frankfurter.FIXING_TIME.minute), (14, 10))
        self.assertEqual((mdm.CONVENTION_SET_ID, profiles.CONVENTION_SET), ("market-data/1.16", "market-data/1.16"))
        self.assertTrue(profiles.PROFILE_SET_VERSION.startswith("market-data/1.16#"))
        w = pk.world_w()
        self.assertTrue(all(v.startswith("market-data/1.16") for k, v in w.market.ids().items() if k != "freshness" or True))


# ===== performance/1.1: the Quant's five findings against CP3a ====================================================================

class Finding2ReasonAtOwnSeverityTests(unittest.TestCase):
    def test_a_suppressed_result_never_borrows_stale_data_from_an_available_input(self):
        agg = PerformanceAggregation()
        stale_ok = Part("s", AVAILABLE, "STALE_DATA", (Cause("s", "AVAILABLE", "STALE_DATA", "1 session"),))
        out = agg.combine([insufficient_part("a", None, "no code"), stale_ok])
        self.assertEqual((out.state, out.reason), (INSUFFICIENT, None))             # not STALE_DATA
        self.assertIn("s", {c.ref for c in out.causes})                              # but the cause stays in lineage
        # a LIMITED result takes its code from the LIMITED causes; an INSUFFICIENT cause with a code outranks nothing of a lower level
        lim = agg.combine([limited_part("l", "STALE_DATA", "3"), stale_ok])
        self.assertEqual((lim.state, lim.reason), (LIMITED, "STALE_DATA"))
        both = agg.combine([insufficient_part("a", "MISSING_FX_HISTORY", "x"), limited_part("l", "STALE_DATA", "3")])
        self.assertEqual((both.state, both.reason), (INSUFFICIENT, "MISSING_FX_HISTORY"))

    def test_a_twr_suppressed_by_a_non_positive_base_has_no_reason_even_beside_a_stale_valuation(self):
        table = {D(2025, 3, 31): F(-5), D(2025, 4, 1): F(-5), D(2025, 4, 2): F(3)}

        def v(day):  # every valuation is AVAILABLE + STALE_DATA
            return Valued(AVAILABLE, "STALE_DATA", table[day], (Cause(f"v@{day}", "AVAILABLE", "STALE_DATA", "1 session"),))

        flows = (vf(D(2025, 4, 2), FlowClass.EXTERNAL_INFLOW_CASH, 5),)
        out = twr_segments(D(2025, 3, 31), D(2025, 4, 2), flows, v, PERF)
        self.assertEqual((out.valued.state, out.valued.reason, out.details), (INSUFFICIENT, None, ("NON_POSITIVE_BASE",)))


class Finding3NegativeFactorTests(unittest.TestCase):
    def test_a_negative_factor_is_negative_value_never_presented_and_a_factor_of_zero_is_a_real_total_loss(self):
        self.assertEqual(ratio(F(-3), F(5)), (None, "NEGATIVE_VALUE"))
        self.assertEqual(ratio(F(0), F(5)), (F(0), ""))   # exactly 0: a real -100 %
        # deposit 5 on 04-02 over an empty base: beta = 0 + 5 = 5 > 0 ; V(04-02) = -3 -> numerator -3: the value fell below zero
        flows = (vf(D(2025, 4, 2), FlowClass.EXTERNAL_INFLOW_CASH, 5),)
        neg = twr_segments(D(2025, 4, 1), D(2025, 4, 2), flows, valuations({D(2025, 4, 1): F(0), D(2025, 4, 2): F(-3)}), PERF)
        self.assertEqual((neg.valued.state, neg.valued.exact, neg.valued.reason, neg.details), (INSUFFICIENT, None, None, ("NEGATIVE_VALUE",)))
        self.assertTrue(any(c.detail == "NEGATIVE_VALUE" for c in neg.valued.causes))
        # V(04-02) = 0: factor 0/5 = 0, TWR = -1 AVAILABLE; annualization refuses it (TOTAL_LOSS) even for a long window
        loss = twr_segments(D(2025, 4, 1), D(2025, 4, 2), flows, valuations({D(2025, 4, 1): F(0), D(2025, 4, 2): F(0)}), PERF)
        self.assertEqual((loss.valued.state, loss.valued.exact), (AVAILABLE, F(-1)))
        self.assertEqual(annualize(loss.valued, F(2), PERF).details, ("TOTAL_LOSS",))


class Finding4PartialUnknownSetTests(unittest.TestCase):
    def test_a_holding_with_an_unknown_quantity_makes_the_partial_figure_insufficient_not_excluded(self):
        # a SELL of 10 units never bought: the position is -10 at the end of the day (ledger-replay 9: LEDGER_INCONSISTENT, no quantity). The set of holdings is unknown,
        # so a partial sum cannot state what it leaves out (Ruling 1.4a): INSUFFICIENT_DATA with that reason and no value; the total has the same reason.
        w = pk.world_w()
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=pk.Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.SELL, D(2025, 4, 1), HKD, listing_id=w.h, quantity=Decimal(10), amount=pk.Money(Decimal(3900), HKD))
        res = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        total = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"][0]
        self.assertEqual((total.result.value, total.result.reason_code), (None, ReasonCode.LEDGER_INCONSISTENT))
        (part,) = [m for m in res.metrics if m.partial]
        self.assertEqual((part.result.value, part.result.sufficiency_state, part.result.reason_code),
                         (None, INSUFFICIENT, ReasonCode.LEDGER_INCONSISTENT))
        self.assertEqual(part.excluded, ())  # not "excluded": the set itself is unknown
        self.assertIsNone(part.exact)

    def test_nothing_valued_is_no_valued_component_never_zero(self):
        w = pk.world_w()
        cn = pk.x.lid(w.ident, "600519", "XSHG")
        L = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), pk.CNY, listing_id=cn, quantity=Decimal(100))
        res = compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, PERF)
        (part,) = [m for m in res.metrics if m.partial]
        self.assertEqual((part.result.value, part.result.sufficiency_state), (None, INSUFFICIENT))
        self.assertIn("NO_VALUED_COMPONENT", part.details)


class Finding5TieRuleTests(unittest.TestCase):
    def test_a_rounding_boundary_inside_the_bracket_is_an_undecidable_tie_rounded_half_up_with_lineage(self):
        rule = PerformanceRounding()
        P = RoundingPoint.PRESENT_RETURN
        half = F(5, 10 ** 13)  # 0.5e-12: exactly on the half of the 12-decimal quantum
        tie = numerics.present(half, P, None, rule, numerics.IRRATIONAL_WIDTH)
        self.assertEqual((tie.tie, tie.stated), (True, F(1, 10 ** 12)))
        neg = numerics.present(-half, P, None, rule, numerics.IRRATIONAL_WIDTH)
        self.assertEqual((neg.tie, neg.stated), (True, F(-1, 10 ** 12)))                 # away from zero
        near = numerics.present(half + F(1, 10 ** 30), P, None, rule, numerics.IRRATIONAL_WIDTH)  # 1e-30 above the half: decidable
        self.assertEqual((near.tie, near.stated), (False, F(1, 10 ** 12)))
        below = numerics.present(half - F(1, 10 ** 30), P, None, rule, numerics.IRRATIONAL_WIDTH)
        self.assertEqual((below.tie, below.stated), (False, F(0)))                       # 1e-30 below: decidably rounds down
        self.assertFalse(numerics.present(half, P, None, rule).tie)                      # an exact rational has no tie: width 0
        # through the metric: a transcendental-basis metric records PRESENTATION_TIE
        valued = Valued(AVAILABLE, None, half, ())
        m = build_metric("return_annualized", "PERIOD", (), valued, None, rule, WindowUsed(D(2022, 1, 1), D(2025, 1, 1)), "t", False, False,
                         point=P, unit="RATE_PER_YEAR", numeric_basis=DECIMAL_PREC50)
        self.assertEqual((m.result.value, m.details), (Decimal("0.000000000001"), ("PRESENTATION_TIE",)))
        exact_basis = build_metric("return_twr", "PERIOD", (), valued, None, rule, WindowUsed(D(2022, 1, 1), D(2025, 1, 1)), "t", False, False, point=P)
        self.assertEqual(exact_basis.details, ())  # rational (tier E) results never tie


if __name__ == "__main__":
    unittest.main()
