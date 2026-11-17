"""CP3c: the MWR / IRR solver, the MWR states, annualized MWR, identity I-6, and the income, fee, tax, financing and conversion-result amounts
(`performance/1.4` Rulings 6.1 to 6.4, 7, 8.1 to 8.6). Every expected value is derived by hand from the inputs shown; Examples W, M-2 and M-3 are the conventions' own.
"""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402
import test_performance_cp3b as t3b  # noqa: E402

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from performance import numerics  # noqa: E402
from performance.conventions import FlowClass  # noqa: E402
from performance.engine import performance_conventions  # noqa: E402
from performance.numerics import irr_is_unique, solve_irr  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance.returns import annualize, mwr_period  # noqa: E402
from performance.states import Valued  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402

D = datetime.date
F = Fraction
PERF = performance_conventions()
USD, HKD, CNH = pk.USD, pk.HKD, CurrencyCode("CNH")
AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA
TOL = F(1, 10 ** 12)


def rho12(root):
    """The root `g` as the period MWR `g - 1` presented to 12 decimals (Ruling 2.2: half away from zero)."""
    return numerics.round_half_up(root.g - 1, 12)


def sol(flows):
    return solve_irr([(F(t), F(c)) for t, c in flows])


class SolverTests(unittest.TestCase):
    def test_example_w_the_conventions_period_mwr(self):
        # flows -10,000 (tau 0), +1,000 (2/3), +360,850/39 (1): Ruling 6.2 Example W gives rho = 0.026119591042 (bracket [1, 2], 100 halvings)
        root = sol([(0, -10000), (F(2, 3), 1000), (1, F(360850, 39))])
        self.assertEqual(rho12(root), F(26119591042, 10 ** 12))
        self.assertFalse(root.rational)

    def test_example_m2_interleaved_flows_have_a_unique_root(self):
        flows = [(F(0), F(-10000)), (F(1, 2), F(2000)), (F(3, 4), F(-3000)), (F(1), F(12000))]
        root = solve_irr(flows)
        self.assertEqual(rho12(root), F(102593873725, 10 ** 12))
        self.assertTrue(irr_is_unique(flows, root.g))  # K = 10,000; 8,500.447...; 11,710.551...: all >= 0

    def test_example_m3_g_is_zero_so_g_is_exactly_one_and_the_uniqueness_test_fails(self):
        flows = [(F(0), F(-1800)), (F(1, 3), F(6050)), (F(2, 3), F(-6750)), (F(1), F(2500))]
        root = solve_irr(flows)
        self.assertEqual((root.g, root.rational), (F(1), True))  # G = 2,500 - 1,800 - 700 = 0 exactly
        self.assertFalse(irr_is_unique(flows, root.g))  # K_1 = 1,800 - 6,050 = -4,250 < 0
        # the three roots the test is guarding against really are roots: g = 1, 1,000/729 and 125/64 (y = g^(-1/3) = 1, 9/10, 4/5)
        for g, y in ((F(1), F(1)), (F(1000, 729), F(9, 10)), (F(125, 64), F(4, 5))):
            self.assertEqual(sum(cf * y ** k for (tau, cf), k in zip(flows, range(4))), 0)

    def test_a_known_closed_form_with_an_interior_flow(self):
        # -100 at 0, -100 at 1/2, +231 at 1: with y = g^(-1/2), 231 y^2 - 100 y - 100 = 0, y = 10/11 (320^2 = 102,400), so g = (11/10)^2 = 121/100 exactly
        flows = [(F(0), F(-100)), (F(1, 2), F(-100)), (F(1), F(231))]
        root = solve_irr(flows)
        self.assertLess(abs(root.g - F(121, 100)), F(1, 10 ** 28))  # the stop rule: |g_hi - g_lo| <= 1E-30 g_hi
        self.assertTrue(irr_is_unique(flows, root.g))

    def test_a_loss_is_bracketed_downward_from_one(self):
        # -100 at 0, -100 at 1/2, +100 at 1: G = -100 < 0; with y = g^(-1/2), y^2 - y - 1 = 0, y = (1 + sqrt 5)/2, so g = 1/y^2 = (3 - sqrt 5)/2 = 0.381966011250...
        flows = [(F(0), F(-100)), (F(1, 2), F(-100)), (F(1), F(100))]
        root = solve_irr(flows)
        self.assertEqual(numerics.round_half_up(root.g, 12), F(381966011250, 10 ** 12))  # the bracket [1/4, 1] (f(1/2) < 0 < f(1/4))
        self.assertTrue(irr_is_unique(flows, root.g))

    def test_the_two_time_case_is_the_exact_ratio_and_a_break_even_is_exactly_one(self):
        self.assertEqual(sol([(0, -12800), (1, F(41492936, 3125))]), numerics.IrrRoot(F(41492936, 3125) / 12800, True))  # P7-R1: I-6, the MWR IS the TWR
        self.assertEqual(sol([(0, -100), (F(1, 3), 50), (1, 50)]), numerics.IrrRoot(F(1), True))  # G = 0

    def test_out_of_range_is_a_detail_not_a_number(self):
        root = sol([(0, -1), (F(1, 2), -1), (1, 2 ** 200)])  # the root is about 2^200: beyond the 2^64 bracket
        self.assertEqual((root.g, root.detail), (None, "IRR_OUT_OF_RANGE"))

    def test_the_solver_is_deterministic_and_a_pure_function_of_the_flows(self):
        flows = [(F(0), F(-10000)), (F(2, 3), F(1000)), (F(1), F(360850, 39))]
        self.assertEqual(solve_irr(flows), solve_irr(list(flows)))
        self.assertEqual(numerics.IRR_STOP, Decimal(10) ** -30)
        self.assertEqual((numerics.IRR_MAX_ITERATIONS, numerics.IRR_BRACKET_EXPONENT), (400, 64))


def vals(table):
    return t3b.valuations({D(2025, 3, 10) + datetime.timedelta(days=i): v for i, v in table.items()})


class MwrPeriodTests(unittest.TestCase):
    B, E = D(2025, 3, 10), D(2025, 3, 14)

    def flows(self, *specs):
        return tuple(t3b.vf(day, cls, amount) for day, cls, amount in specs)

    def run_mwr(self, v_b, v_e, flows):
        return mwr_period(self.B, self.E, flows, lambda d: Valued(AVAILABLE, None, F({self.B: v_b, self.E: v_e}[d]), ()), PERF)

    def test_example_m2_through_the_period_function(self):
        out = self.run_mwr(10000, 12000, self.flows((D(2025, 3, 12), FlowClass.EXTERNAL_OUTFLOW_CASH, 2000), (D(2025, 3, 14), FlowClass.EXTERNAL_INFLOW_CASH, 3000)))
        self.assertEqual(out.valued.state, AVAILABLE)
        # inflow dated 03-14 is at the START of the day: k = 03-14 - 1 - 03-10 = 3 of 4; the outflow dated 03-12 at its end: k = 2
        self.assertEqual([(t, c) for t, c in out.flows], [(F(0), F(-10000)), (F(1, 2), F(2000)), (F(3, 4), F(-3000)), (F(1), F(12000))])
        self.assertEqual(numerics.round_half_up(out.valued.exact, 12), F(102593873725, 10 ** 12))
        self.assertTrue(out.interior)

    def test_the_states_of_ruling_64(self):
        out = self.run_mwr(0, 0, ())
        self.assertEqual((out.valued.state, out.valued.reason, out.details), (INSUFFICIENT, None, ("NO_CAPITAL",)))  # every flow is 0
        out = self.run_mwr(0, 500, self.flows((D(2025, 3, 12), FlowClass.EXTERNAL_OUTFLOW_CASH, 100)))
        self.assertEqual(out.details, ("NO_CAPITAL",))  # V_B = 0 with no inflow
        out = self.run_mwr(-10, 10, ())
        self.assertEqual((out.valued.state, out.details), (INSUFFICIENT, ("IRR_NOT_DEFINED",)))  # the first non-zero flow (+10) is positive
        out = self.run_mwr(100, 0, ())
        self.assertEqual(out.details, ("IRR_NOT_DEFINED",))  # no positive flow
        out = self.run_mwr(1800, 2500, self.flows((D(2025, 3, 11), FlowClass.EXTERNAL_OUTFLOW_CASH, 6050), (D(2025, 3, 13), FlowClass.EXTERNAL_INFLOW_CASH, 6750)))
        self.assertEqual((out.valued.state, out.valued.reason, out.details), (INSUFFICIENT, None, ("IRR_UNIQUENESS_NOT_ESTABLISHED",)))
        self.assertTrue(all(c.reason is None for c in out.valued.causes))  # no reason code, ever, for these (Ruling 6.4)

    def test_a_negative_base_day_is_just_a_flow_pattern_so_the_mwr_can_exist_where_the_twr_does_not(self):
        # V_B = 0, a deposit of 1,000 on 03-12 (k = 1 of 4) and V_E = 1,020: f = -1000 g^(-1/4) + 1020 g^(-1) = 0, g^(3/4) = 1.02
        out = self.run_mwr(0, 1020, self.flows((D(2025, 3, 12), FlowClass.EXTERNAL_INFLOW_CASH, 1000)))
        self.assertEqual(out.valued.state, AVAILABLE)
        self.assertEqual(out.flows, ((F(1, 4), F(-1000)), (F(1), F(1020))))
        import decimal  # noqa: PLC0415  (a test, outside the product: an independent library evaluation of 1.02 ** (4/3))

        independent = decimal.Context(prec=40).power(Decimal("1.02"), decimal.Context(prec=40).divide(Decimal(4), Decimal(3)))
        self.assertLess(abs(Decimal(out.valued.exact.numerator) / Decimal(out.valued.exact.denominator) + 1 - independent), Decimal("1e-25"))

    def test_a_limited_input_makes_the_mwr_limited_and_an_insufficient_one_suppresses_it(self):
        from performance.results import Cause  # noqa: PLC0415

        def limited(day):
            exact = F({self.B: 10000, self.E: 11000}[day])
            return Valued(LIMITED, "STALE_DATA", exact, (Cause("v", "LIMITED", "STALE_DATA", "3 sessions"),)) if day == self.E else Valued(AVAILABLE, None, exact, ())

        out = mwr_period(self.B, self.E, (), limited, PERF)
        self.assertEqual((out.valued.state, out.valued.reason, out.valued.exact), (LIMITED, "STALE_DATA", F(1, 10)))
        self.assertTrue(out.rational)  # no interior flow: g = V_E / V_B exactly (I-6)

        def missing(day):
            return Valued(INSUFFICIENT, "MISSING_PRICE_HISTORY", None, (Cause("v", "INSUFFICIENT_DATA", "MISSING_PRICE_HISTORY", "none"),)) if day == self.E \
                else Valued(AVAILABLE, None, F(10000), ())

        self.assertEqual(mwr_period(self.B, self.E, (), missing, PERF).valued.reason, "MISSING_PRICE_HISTORY")

    def test_interior_valuations_are_not_inputs_of_the_mwr(self):
        calls = []

        def valuation(day):
            calls.append(day)
            return Valued(AVAILABLE, None, F({self.B: 10000, self.E: 11000}[day]), ())  # asking for any other day would raise a KeyError

        mwr_period(self.B, self.E, (), valuation, PERF)
        self.assertEqual(sorted(set(calls)), [self.B, self.E])


class EngineMwrTests(unittest.TestCase):
    """Example W through the engine (pk.world_w: the conventions' own ECB steps 9/70 then 5/39)."""

    def setUp(self):
        self.w = pk.world_w()
        self.L = pk.example_w_ledger(self.w.h)

    def window(self, spec=None, end=D(2025, 4, 3), **kw):
        return pk.compute_window(self.L.rows, self.L.version, spec or WindowSpec(WindowRule.SINCE_INCEPTION), end, USD, self.w.store, self.w.ident, self.w.market, PERF, **kw)

    def metric(self, res, metric_id):
        (m,) = [m for m in res.metrics if m.metric_id == metric_id]
        return m

    def test_example_w_mwr_is_above_the_twr_and_carries_its_lineage(self):
        res = self.window(verify_identities=True)
        mwr, twr = self.metric(res, "return_mwr"), self.metric(res, "return_twr")
        self.assertEqual((mwr.result.value, mwr.result.sufficiency_state), (Decimal("0.026119591042"), AVAILABLE))
        self.assertEqual(twr.result.value, Decimal("0.025506444983"))
        self.assertGreater(mwr.exact, twr.exact)  # the conventions' remark: less capital was invested on the lowest-return day
        self.assertTrue(mwr.numeric_basis.startswith("DECIMAL_PREC50"))  # an irrational root: presented with the tie rule
        self.assertEqual(dict(mwr.lineage)["identity:I-6"], "NOT_APPLICABLE")  # a flow strictly inside the window
        self.assertEqual(res.manifest.identities_run, ("I-2", "I-3", "I-6"))
        # annualization needs Y >= 1: a 3-day window gives the period figure only
        ann = self.metric(res, "return_mwr_annualized")
        self.assertEqual((ann.result.sufficiency_state, ann.result.reason_code, ann.result.value), (INSUFFICIENT, None, None))
        self.assertIn("PERIOD_SHORTER_THAN_ONE_YEAR", ann.details)

    def test_identity_i6_with_no_interior_flow_the_mwr_is_the_twr_exactly(self):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=Money(Decimal(1000), USD))
        res = pk.compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), USD, self.w.store, self.w.ident, self.w.market, PERF)
        mwr, twr = self.metric(res, "return_mwr"), self.metric(res, "return_twr")
        self.assertEqual((mwr.exact, mwr.numeric_basis), (twr.exact, "RATIONAL"))
        self.assertEqual(dict(mwr.lineage)["identity:I-6"], "PASS")

    def test_a_refused_window_refuses_the_mwr_and_every_amount_too(self):
        res = self.window(WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 1)))  # before inception (03-31)
        names = {m.metric_id for m in res.metrics}
        self.assertTrue({"return_mwr", "return_mwr_annualized", "income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount"} <= names)
        for m in res.metrics:
            self.assertEqual((m.result.value, m.result.sufficiency_state), (None, INSUFFICIENT), m.metric_id)


class AmountLinesTests(unittest.TestCase):
    """USD reporting; HKD at 9/70 on 04-01 and 5/39 on 04-02 and 04-03 (pk.FIXINGS). A1 holds nothing that matters: the lines are read from the events."""

    def setUp(self):
        self.w = pk.world_w()

    def run_lines(self, events, base_day=D(2025, 3, 31), end=D(2025, 4, 3), start=None):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=Money(Decimal(100000), USD))  # inception 03-24; the window starts at `start`
        for day, etype, ccy, amount, kw in events:
            L.add(pk.A1, etype, day, ccy, amount=Money(Decimal(amount), ccy), **kw)
        spec = WindowSpec(WindowRule.CUSTOM, None, start or base_day)
        res = pk.compute_window(L.rows, L.version, spec, end, USD, self.w.store, self.w.ident, self.w.market, PERF)
        return {m.metric_id: m for m in res.metrics}, L

    def test_a_window_with_no_such_event_has_amount_zero_and_is_available_not_missing(self):
        by, _ = self.run_lines([])
        for key in ("income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount"):
            self.assertEqual((by[key].exact, by[key].result.sufficiency_state), (F(0), AVAILABLE), key)

    def test_signs_income_positive_and_every_cost_negative_and_financing_never_netted_against_interest(self):
        by, _ = self.run_lines([
            (D(2025, 4, 2), EventType.FEE, USD, "2", {}), (D(2025, 4, 2), EventType.TAX, USD, "1.5", {}),
            (D(2025, 4, 2), EventType.INTEREST_CHARGED, USD, "3.5", {}), (D(2025, 4, 2), EventType.INTEREST, USD, "10", {})])
        self.assertEqual(by["fees_amount"].exact, F(-2))
        self.assertEqual(by["fees_amount"].result.value, Decimal("-2.00"))
        self.assertEqual(by["taxes_amount"].exact, F(-3, 2))
        self.assertEqual(by["financing_amount"].exact, F(-7, 2))
        self.assertEqual(by["income_amount"].exact, F(10))  # the 3.50 of interest charged is NOT netted into it

    def test_an_accrued_dividend_is_income_on_its_ex_date_at_that_dates_fixing_and_the_pay_date_credit_is_not_income_again(self):
        ev = [(D(2025, 4, 3), EventType.DIVIDEND, HKD, "200", dict(listing_id=self.w.h, ex_date=D(2025, 4, 1)))]
        in_window, _ = self.run_lines(ev, base_day=D(2025, 3, 31), end=D(2025, 4, 3))
        self.assertEqual(in_window["income_amount"].exact, F(200) * F(9, 70))  # 04-01 fixing 9/70 = 180/7, not 04-03's 5/39
        self.assertNotIn("INCOME_CASH_BASIS", in_window["income_amount"].details)
        after_ex, _ = self.run_lines(ev, base_day=D(2025, 4, 1), end=D(2025, 4, 3))  # the ex-date is the BASE: not in (B, E]
        self.assertEqual(after_ex["income_amount"].exact, F(0))  # although the 200 HKD was credited on 04-03, inside the window

    def test_a_dividend_with_no_ex_date_is_cash_basis_on_the_pay_date_with_lineage(self):
        ev = [(D(2025, 4, 3), EventType.DIVIDEND, HKD, "200", dict(listing_id=self.w.h))]
        by, _ = self.run_lines(ev)
        self.assertEqual(by["income_amount"].exact, F(200) * F(5, 39))
        self.assertEqual(by["income_amount"].details, ("INCOME_CASH_BASIS",))
        self.assertEqual(by["income_amount"].result.sufficiency_state, AVAILABLE)  # lineage, no state change
        same_day = [(D(2025, 4, 3), EventType.DIVIDEND, HKD, "200", dict(listing_id=self.w.h, ex_date=D(2025, 4, 3)))]
        self.assertEqual(self.run_lines(same_day)[0]["income_amount"].details, ("INCOME_CASH_BASIS",))  # ex_date == pay date: cash basis too

    def test_a_cnh_dividend_suppresses_only_the_income_line(self):
        ev = [(D(2025, 4, 2), EventType.DIVIDEND, CNH, "500", dict(listing_id=self.w.h)), (D(2025, 4, 2), EventType.FEE, USD, "2", {}),
              (D(2025, 4, 2), EventType.TAX, HKD, "20", {})]
        by, _ = self.run_lines(ev)
        inc = by["income_amount"]
        self.assertEqual((inc.result.value, inc.result.sufficiency_state.value, inc.result.reason_code.value), (None, "INSUFFICIENT_DATA", "MISSING_FX_HISTORY"))
        self.assertEqual((by["fees_amount"].exact, by["taxes_amount"].exact), (F(-2), F(-20) * F(5, 39)))  # the other lines are unaffected
        self.assertEqual(by["fees_amount"].result.sufficiency_state, AVAILABLE)

    def test_the_conversion_result_is_minus_sold_plus_bought_each_at_its_own_dates_fixing(self):
        # 5,000 USD sold for 38,800 HKD on 04-01: -5,000 x 1 + 38,800 x 9/70 = -5,000 + 34,920/7 = -80/7 (the dealer's spread plus timing)
        by, L = self.run_lines([(D(2025, 4, 1), EventType.CURRENCY_CONVERSION, USD, "5000", dict(bought_amount=Money(Decimal(38800), HKD)))])
        self.assertEqual(by["conversion_result_amount"].exact, F(-80, 7))
        self.assertEqual(by["conversion_result_amount"].result.value, Decimal("-11.43"))
        self.assertEqual(by["fees_amount"].exact, F(0))  # not a fee
        # it is never used as a rate: the same conversion at a different execution price changes the line, not any other figure
        by2, _ = self.run_lines([(D(2025, 4, 1), EventType.CURRENCY_CONVERSION, USD, "5000", dict(bought_amount=Money(Decimal(38000), HKD)))])
        self.assertEqual(by2["conversion_result_amount"].exact, F(-5000) + F(38000) * F(9, 70))

    def test_a_reversed_event_is_not_a_line(self):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=Money(Decimal(100000), USD))
        fee = L.add(pk.A1, EventType.FEE, D(2025, 4, 2), USD, amount=Money(Decimal(2), USD))
        e = L.rows[-1].event
        L.add(pk.A1, EventType.REVERSAL, D(2025, 4, 2), USD, reverses_event_id=e.event_id)
        res = pk.compute_window(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 31)), D(2025, 4, 3), USD, self.w.store, self.w.ident, self.w.market, PERF)
        (fees,) = [m for m in res.metrics if m.metric_id == "fees_amount"]
        self.assertEqual(fees.exact, F(0))

    def test_the_lines_are_money_facts_never_annualized_and_part_of_the_manifests_data_cited(self):
        by, _ = self.run_lines([(D(2025, 4, 2), EventType.TAX, HKD, "20", {})])
        self.assertEqual(by["taxes_amount"].unit, "CURRENCY_AMOUNT")
        self.assertEqual(by["taxes_amount"].currency, "USD")
        # the fixing used is cited (a hidden input otherwise): the manifest of the same run lists FX files
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=Money(Decimal(1), USD))
        L.add(pk.A1, EventType.TAX, D(2025, 4, 2), HKD, amount=Money(Decimal(20), HKD))
        res = pk.compute_window(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 31)), D(2025, 4, 3), USD, self.w.store, self.w.ident, self.w.market, PERF)
        self.assertTrue([r for r in res.manifest.data_set_refs if r.kind.value == "FX"])


if __name__ == "__main__":
    unittest.main()
