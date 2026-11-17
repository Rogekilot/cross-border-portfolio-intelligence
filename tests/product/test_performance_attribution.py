"""CP3e unit tests for the attribution entry (`performance/1.8` Rulings 9.1 to 9.6) beyond what the part-4 golden items reach: a split day, the base and zero-capital rules, the Carino link
itself, identity I-9, the I-4 fault path, entry-order and internal-transfer independence, account scope, the groupings and `reproduce`. Every expected value is derived by hand in the test.
"""

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402

from domain.currency import Money  # noqa: E402
from domain.ledger import EventType, SplitRatio  # noqa: E402
from performance import attribution  # noqa: E402
from performance import engine  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.numerics import carino_link  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402

D, F = datetime.date, Fraction
USD = mp.USD
AVAILABLE, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.INSUFFICIENT_DATA
PRICES = {D(2025, 2, 3): "37.50", D(2025, 2, 4): "40.00", D(2025, 2, 5): "40.00", D(2025, 2, 6): "40.00", D(2025, 2, 7): "40.00"}


def attribute(ledger, end, base=None, scope=None, port=None, events=None):
    spec = WindowSpec(WindowRule.CUSTOM, None, base) if base is not None else WindowSpec(WindowRule.SINCE_INCEPTION)
    return engine.compute_attribution(events if events is not None else ledger.rows, ledger.version, spec, end, USD, port or mp.market(evidence=None, prices=PRICES), mp.Ident(),
                                      mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(), account_scope=scope)


def metric(res, metric_id, **subject):
    found = [m for m in res.metrics if m.metric_id == metric_id and all(dict(m.subject).get(k) == v for k, v in subject.items())]
    assert len(found) == 1, (metric_id, subject, len(found))
    return found[0]


def lines_of(res):
    return {name: exact for name, _shown, exact in metric(res, "attribution_money").breakdown}


def post_split_ledger():
    """A1 holds 200 units from before 02-03 (4:1 split recorded on 02-03 of 50 units), 2,500 USD of cash: V(02-03) = 2,500 + 200 x 37.50 = 10,000."""
    L = mp.base_ledger()
    L.add(mp.A1, EventType.SPLIT, D(2025, 2, 3), USD, listing_id=mp.LISTING, split_ratio=SplitRatio(Decimal(4), Decimal(1)))
    return L


class DailyLinesTests(unittest.TestCase):
    def test_a_split_day_is_neutral_the_ratio_scales_the_quantity_and_divides_the_start_price(self):
        # the raw close falls 150.00 -> 37.50 with the 4:1 split recorded: q0 = 50 x 4 = 200, P0 = 150 / 4 = 37.50 = P1, so there is no price effect (metamorphic check 11.3 #3)
        prices = {D(2025, 1, 31): "150.00", **PRICES}
        res = attribute(post_split_ledger(), D(2025, 2, 3), base=D(2025, 1, 31), port=mp.market(evidence=None, prices=prices))
        self.assertEqual(metric(res, "attribution_money").result.sufficiency_state, AVAILABLE)
        self.assertEqual(set(lines_of(res).values()), {F(0)})
        self.assertEqual(metric(res, "attribution_money").exact, 0)
        self.assertEqual(metric(res, "attribution_return").exact, 0)

    def test_a_price_move_is_the_price_line_and_with_one_active_day_the_component_is_the_twr_exactly(self):
        # 02-04: 200 units x (40.00 - 37.50) = 500 on a base of 10,000: r = 1/20; 02-05 flat
        res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3))
        self.assertEqual(lines_of(res)["attr.price"], 500)
        self.assertEqual({k: v for k, v in lines_of(res).items() if k != "attr.price"}, {name: F(0) for name in attribution.LINE_IDS if name != "attr.price"})
        ret = metric(res, "attribution_return")
        self.assertEqual((ret.exact, ret.result.value), (F(1, 20), Decimal("0.050000000000")))
        self.assertEqual(ret.breakdown[0][:2], ("attr.price", Decimal("0.050000000000")))
        self.assertLessEqual(abs(ret.breakdown[0][2] - F(1, 20)), F(1, 10 ** 45))
        self.assertEqual([e for _n, _s, e in ret.breakdown[1:]], [F(0)] * 7)  # a line that is 0 every day stays exactly 0

    def test_a_purchase_without_capital_has_money_lines_and_no_percentage_components_non_positive_base(self):
        # a purchase recorded with no deposit: the first day's base is 0 while its gain is not (Ruling 9.5): the percentages are INSUFFICIENT_DATA with detail NON_POSITIVE_BASE and no
        # reason, the money lines (which need no base) are available: the trade result 50 x 37.50 - 7,500 = -5,625
        L = mp.pk.Ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 2, 3), USD, listing_id=mp.LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
        res = attribute(L, D(2025, 2, 4))
        money, ret = metric(res, "attribution_money"), metric(res, "attribution_return")
        # G = -5,625 (02-03) + 50 x (40 - 37.50) = 125 (02-04) = -5,500, all of it price
        self.assertEqual((money.result.sufficiency_state, money.exact, lines_of(res)["attr.price"]), (AVAILABLE, F(-5500), F(-5500)))
        self.assertEqual((ret.result.sufficiency_state, ret.result.reason_code, ret.result.value, ret.breakdown, ret.details), (INSUFFICIENT, None, None, (), ("NON_POSITIVE_BASE",)))
        self.assertTrue(ret.causes)

    def test_a_day_with_no_capital_and_no_gain_contributes_nothing_and_is_not_a_failure(self):
        L = mp.pk.Ledger()
        L.add(mp.A1, EventType.DEPOSIT, D(2025, 2, 4), USD, amount=Money(Decimal(1000), USD))
        L.add(mp.A1, EventType.WITHDRAWAL, D(2025, 2, 5), USD, amount=Money(Decimal(1000), USD))
        res = attribute(L, D(2025, 2, 7))
        ret = metric(res, "attribution_return")
        self.assertEqual((ret.result.sufficiency_state, ret.exact, dict(ret.lineage)["zero_capital_days"]), (AVAILABLE, F(0), "2"))  # 02-06 and 02-07: 0 / 0
        self.assertEqual(set(lines_of(res).values()), {F(0)})
        self.assertEqual([c for _n, _s, c in ret.breakdown], [F(0)] * 8)


class CarinoTests(unittest.TestCase):
    def test_the_components_sum_to_the_twr_and_a_zero_line_stays_zero(self):
        # two days: r = 1/10 (all from line 1) and r = 1/10 (line 1: 1/20, line 2: 1/20); the TWR is 1.1 x 1.1 - 1 = 21/100
        daily = [(F(1, 10), (F(1, 10), F(0))), (F(1, 10), (F(1, 20), F(1, 20)))]
        link = carino_link(daily, F(21, 100))
        self.assertIsNotNone(link)
        self.assertEqual(len(link.components), 2)
        self.assertLess(abs(link.residual), Decimal("1e-45"))
        self.assertGreater(link.components[0], link.components[1])
        zero = carino_link([(F(1, 10), (F(1, 10), F(0))), (F(1, 10), (F(1, 10), F(0)))], F(21, 100))
        self.assertEqual(zero.components[1], 0)
        # a single active day: kappa_D = kappa, so C_k = c_k exactly in real arithmetic
        one = carino_link([(F(1, 20), (F(1, 40), F(1, 40)))], F(1, 20))
        self.assertLess(abs(one.components[0] - Decimal("0.025")), Decimal("1e-45"))

    def test_a_total_loss_has_no_logarithm(self):
        self.assertIsNone(carino_link([(F(-1), (F(-1),))], F(-1)))
        self.assertIsNone(carino_link([(F(1, 10), (F(1, 10),)), (F(-1), (F(-1),))], F(-1)))
        self.assertIsNone(carino_link([(F(1, 10), (F(1, 10),))], F(-3, 2)))


class IdentityNineTests(unittest.TestCase):
    def valuation(self, ledger, day):
        run = engine._Run(tuple(ledger.rows), ledger.version, USD, mp.market(evidence=None, prices=PRICES), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, (), None, None, None)
        return run, run.valuation(day)

    def test_the_replayed_cash_equals_the_sum_of_the_cash_effects_and_a_tampered_balance_fails(self):
        L = mp.base_ledger()
        L.add(mp.A1, EventType.FEE, D(2025, 2, 4), USD, amount=Money(Decimal(3), USD))
        run, val = self.valuation(L, D(2025, 2, 5))
        self.assertEqual(attribution.cash_effects(run.live, D(2025, 2, 5)), {(mp.A1, "USD"): F(10000 - 7500 - 3)})
        self.assertEqual(attribution.cash_identity(run.live, val, None), "PASS")
        tampered = dataclasses.replace(val, cash=tuple(dataclasses.replace(c, amount=c.amount + 1) for c in val.cash))
        self.assertEqual(attribution.cash_identity(run.live, tampered, None), "FAIL")
        self.assertEqual(attribution.cash_identity(run.live, dataclasses.replace(val, cash=()), None), "FAIL")

    def test_the_cash_table_covers_every_cash_event_type(self):
        L = mp.pk.Ledger()
        hk = pk.HKD
        L.add(mp.A1, EventType.DEPOSIT, D(2025, 2, 3), USD, amount=Money(Decimal(1000), USD))
        L.add(mp.A1, EventType.CURRENCY_CONVERSION, D(2025, 2, 3), USD, amount=Money(Decimal(100), USD), bought_amount=Money(Decimal(780), hk))
        L.add(mp.A1, EventType.DIVIDEND, D(2025, 2, 4), hk, listing_id=mp.LISTING, amount=Money(Decimal(20), hk))
        L.add(mp.A1, EventType.TAX, D(2025, 2, 4), hk, listing_id=mp.LISTING, amount=Money(Decimal(2), hk))
        L.add(mp.A1, EventType.INTEREST, D(2025, 2, 4), USD, amount=Money(Decimal(1), USD))
        L.add(mp.A1, EventType.INTEREST_CHARGED, D(2025, 2, 4), USD, amount=Money(Decimal(4), USD))
        L.add(mp.A1, EventType.WITHDRAWAL, D(2025, 2, 5), USD, amount=Money(Decimal(50), USD))
        L.add(mp.A1, EventType.SELL, D(2025, 2, 5), USD, listing_id=mp.LISTING, quantity=Decimal(1), amount=Money(Decimal(30), USD))
        L.add(mp.A1, EventType.BUY, D(2025, 2, 6), USD, listing_id=mp.LISTING, quantity=Decimal(1), amount=Money(Decimal(10), USD))
        L.add(mp.A1, EventType.TRANSFER_OUT, D(2025, 2, 6), USD, amount=Money(Decimal(7), USD))
        L.add(mp.A1, EventType.TRANSFER_IN, D(2025, 2, 6), USD, amount=Money(Decimal(2), USD))
        got = attribution.cash_effects(L.rows, D(2025, 2, 6))
        self.assertEqual(got, {(mp.A1, "USD"): F(1000 - 100 + 1 - 4 - 50 + 30 - 10 - 7 + 2), (mp.A1, "HKD"): F(780 + 20 - 2)})
        self.assertEqual(attribution.cash_effects(L.rows, D(2025, 2, 4)), {(mp.A1, "USD"): F(1000 - 100 + 1 - 4), (mp.A1, "HKD"): F(780 + 20 - 2)})  # later events are not counted


class FaultPathTests(unittest.TestCase):
    def test_a_failed_identity_is_an_engine_fault_with_no_number_and_no_breakdown(self):
        original = attribution.daily_lines

        def broken(*args, **kwargs):
            data = original(*args, **kwargs)
            data.days[0].add(attribution.PRICE, attribution.Component("position", "x"), F(1))  # a line that no longer sums to g_D
            return dataclasses.replace(data, i4="FAIL", i4_failure="I-4: forced")

        with mock.patch.object(attribution, "daily_lines", broken):
            res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3))
        for m in res.metrics:
            self.assertEqual((m.result.sufficiency_state, m.result.reason_code.value, m.result.value, m.breakdown), (INSUFFICIENT, "CALCULATION_ERROR", None, ()), m.metric_id)
            self.assertIn("IDENTITY_FAILED", m.details)
        self.assertEqual({m.metric_id for m in res.metrics}, {"attribution_money", "attribution_return"})  # no breakdown from a result that failed its identity

    def assert_fault(self, res, note):
        for m in res.metrics:
            self.assertEqual((m.result.sufficiency_state, m.result.reason_code.value, m.result.value, m.breakdown), (INSUFFICIENT, "CALCULATION_ERROR", None, ()), m.metric_id)
            self.assertIn("IDENTITY_FAILED", m.details)
            self.assertTrue(any(note in c.note for c in m.causes), (m.metric_id, note))

    def test_each_identity_that_fails_is_named_and_gives_no_number(self):
        original_returns, original_lines = attribution.daily_returns, attribution.daily_lines

        def wrong_product(data):
            r = original_returns(data)
            return dataclasses.replace(r, product=r.product + F(1, 100))

        def wrong_i3(*args, **kwargs):
            return dataclasses.replace(original_lines(*args, **kwargs), i3="FAIL")

        args = dict(base=D(2025, 2, 3))
        with mock.patch.object(attribution, "daily_returns", wrong_product):
            self.assert_fault(attribute(post_split_ledger(), D(2025, 2, 5), **args), "I-2")
        with mock.patch.object(attribution, "daily_lines", wrong_i3):
            self.assert_fault(attribute(post_split_ledger(), D(2025, 2, 5), **args), "I-3")
        with mock.patch.object(attribution, "cash_identity", lambda *a, **k: "FAIL"):
            self.assert_fault(attribute(post_split_ledger(), D(2025, 2, 5), **args), "I-9")

    def test_linked_components_that_miss_the_twr_by_more_than_1e_40_are_a_fault_in_the_percentages_only(self):
        from performance.numerics import CarinoResult  # noqa: PLC0415

        real = engine.carino_link

        def off(daily, twr):
            r = real(daily, twr)
            return CarinoResult(r.components, Decimal("1e-10"))

        with mock.patch.object(engine, "carino_link", off):
            res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3))
        ret = metric(res, "attribution_return")
        self.assertEqual((ret.result.sufficiency_state, ret.result.reason_code.value, ret.result.value), (INSUFFICIENT, "CALCULATION_ERROR", None))
        self.assertTrue(any("Carino" in c.note for c in ret.causes))
        self.assertEqual(metric(res, "attribution_money").result.sufficiency_state, AVAILABLE)  # the money lines are exact and unaffected

    def test_a_line_that_does_not_sum_to_the_days_gain_fails_i4_for_real(self):
        # an income item the ledger's cash never received: the lines then exceed g_D by 1 on 02-04 (a genuine I-4 failure, found by the engine's own check)
        real = attribution.income_lines.line_items

        def with_phantom(live, line, base, end, account_scope=None):
            items = real(live, line, base, end, account_scope)
            if line == attribution.income_lines.INCOME:
                items = items + (attribution.income_lines.LineItem(uuid.UUID(int=99), D(2025, 2, 4), ((USD, F(1)),)),)
            return items

        with mock.patch.object(attribution.income_lines, "line_items", with_phantom):
            res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3))
        self.assert_fault(res, "I-4")

    def test_a_window_before_inception_refuses_with_the_windows_state(self):
        res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2024, 1, 1))
        for m in res.metrics:
            self.assertEqual((m.result.sufficiency_state, m.result.value, m.breakdown), (INSUFFICIENT, None, ()))
            self.assertIn("WINDOW_BEFORE_INCEPTION", m.details)
        self.assertEqual(res.manifest.identities_run, ("I-2", "I-3", "I-4", "I-9"))


class IndependenceTests(unittest.TestCase):
    def test_entry_order_within_a_day_and_an_internal_transfer_pair_change_no_line(self):
        plain = post_split_ledger()
        base = attribute(plain, D(2025, 2, 5), base=D(2025, 2, 3))
        # an internal transfer pair inserted on 02-04 (metamorphic check 11.3 #2): the portfolio-level lines are identical
        moved = post_split_ledger()
        mp.internal_transfer(moved, D(2025, 2, 4), mp.A1, mp.A2, quantity=50)
        after = attribute(moved, D(2025, 2, 5), base=D(2025, 2, 3))
        self.assertEqual(lines_of(after), lines_of(base))
        self.assertEqual(metric(after, "attribution_return").breakdown, metric(base, "attribution_return").breakdown)
        # events listed in another order (ledger_seq unchanged): the same bytes
        shuffled = list(reversed(moved.rows))
        self.assertEqual(attribute(moved, D(2025, 2, 5), base=D(2025, 2, 3), events=shuffled).result_digest, after.result_digest)

    def test_account_scope_sums_to_the_portfolio_and_an_internal_transfer_is_a_flow_of_the_account(self):
        L = post_split_ledger()
        mp.internal_transfer(L, D(2025, 2, 4), mp.A1, mp.A2, quantity=50)
        whole = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3))
        a1 = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3), scope=mp.A1)
        a2 = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3), scope=mp.A2)
        for res in (a1, a2):
            self.assertEqual(dict(metric(res, "attribution_money").lineage)["identity:I-4"], "PASS")
        self.assertEqual({k: lines_of(a1)[k] + lines_of(a2)[k] for k in attribution.LINE_IDS}, lines_of(whole))  # internal flows cancel (Ruling 4.5)


class GroupingTests(unittest.TestCase):
    def test_every_grouping_sums_to_every_line_and_names_its_parts(self):
        L = post_split_ledger()
        mp.internal_transfer(L, D(2025, 2, 4), mp.A1, mp.A2, quantity=50)
        late = {D(2025, 2, 3): "37.50", D(2025, 2, 4): "37.50", D(2025, 2, 5): "40.00"}  # the price moves on 02-05, after 50 units moved to A2 on 02-04
        res = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3), port=mp.market(evidence=None, prices=late))
        price = lines_of(res)["attr.price"]
        self.assertEqual(price, 500)
        names = {}
        for group in attribution.GROUPS:
            m = metric(res, "attribution_breakdown", group_by=group, line="attr.price")
            self.assertEqual(sum((e for _n, _s, e in m.breakdown), F(0)), price, group)
            names[group] = [n for n, _s, _e in m.breakdown]
        self.assertEqual(names["listing"], [f"listing:{mp.LISTING}"])
        self.assertEqual(names["currency"], ["currency:USD"])
        self.assertEqual(names["market"], [f"market:{mp.MIC}"])
        self.assertEqual(names["account"], sorted(f"account:{a}" for a in (mp.A1, mp.A2)))  # 150 units in A1, 50 in A2 from 02-04
        self.assertEqual([e for _n, _s, e in metric(res, "attribution_breakdown", group_by="account", line="attr.price").breakdown], [F(375), F(125)])  # 150 x 2.50 and 50 x 2.50
        # cash has no listing: the FX line of a cash-only grouping falls in the `none` part, so every grouping still sums to the line
        fx = metric(res, "attribution_breakdown", group_by="listing", line="attr.fx")
        self.assertEqual(fx.breakdown, ())


class ZeroPartTests(unittest.TestCase):
    def test_a_component_whose_days_cancel_to_exactly_zero_is_not_listed_and_the_line_is_zero(self):
        # +500 on 02-04 and -500 on 02-05 on the same position: the window line is exactly 0 and no part is listed (a part that is exactly 0 is omitted)
        there_and_back = {D(2025, 2, 3): "37.50", D(2025, 2, 4): "40.00", D(2025, 2, 5): "37.50"}
        res = attribute(post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3), port=mp.market(evidence=None, prices=there_and_back))
        self.assertEqual(lines_of(res)["attr.price"], 0)
        for group in attribution.GROUPS:
            self.assertEqual(metric(res, "attribution_breakdown", group_by=group, line="attr.price").breakdown, (), group)
        ret = metric(res, "attribution_return")
        self.assertEqual(ret.exact, F(0))  # 1.05 x (1 - 1/21) = 1: the TWR is exactly 0 though the days are not


class BreakdownObjectTests(unittest.TestCase):
    """performance/1.9 Ruling 9.6: a breakdown is a decomposition object: fixed part order, zero parts omitted, `none` last, parts apportioned to the line's display value."""

    def data(self, contributions):
        day = attribution.DayLines(D(2025, 2, 4), F(100), F(0))
        for line, component, amount in contributions:
            day.add(line, component, amount)
        return attribution.AttributionData((day,), (), attribution.EMPTY_FRESHNESS, "PASS", "PASS")

    def test_the_part_order_is_positions_then_cash_then_receivables_by_id_or_code_and_none_last_and_zero_parts_are_omitted(self):
        a, l2, l5, e1, e9 = str(uuid.UUID(int=1)), str(uuid.UUID(int=2)), str(uuid.UUID(int=5)), str(uuid.UUID(int=1000)), str(uuid.UUID(int=9))
        C = attribution.Component
        data = self.data([
            (attribution.FX, C("receivable", a, l2, "HKD", e9), F(1)), (attribution.FX, C("cash", a, "", "USD"), F(2)), (attribution.FX, C("cash", a, "", "CNY"), F(3)),
            (attribution.FX, C("position", a, l5, "USD"), F(4)), (attribution.FX, C("position", a, l2, "HKD"), F(5)), (attribution.FX, C("receivable", a, l5, "HKD", e1), F(6)),
            (attribution.FX, C("event", a, l2, "HKD", e1), F(7)), (attribution.FX, C("position", a, str(uuid.UUID(int=7)), "USD"), F(0)),  # an exact 0 part is omitted
        ])
        market = lambda listing: "XNYS"  # noqa: E731
        names = [n for n, _e in attribution.breakdown_parts(data, attribution.FX, "component", market)]
        self.assertEqual(names, [f"position:{l2}", f"position:{l5}", "cash:CNY", "cash:USD", f"receivable:{e9}", f"receivable:{e1}", f"event:{e1}"])  # positions, cash, receivables, events
        listing = attribution.breakdown_parts(data, attribution.FX, "listing", market)
        self.assertEqual([n for n, _e in listing], [f"listing:{l2}", f"listing:{l5}", "listing:none"])  # a receivable carries its dividend's listing; cash has none: last
        self.assertEqual(dict(listing), {f"listing:{l2}": F(1 + 5 + 7), f"listing:{l5}": F(4 + 6), "listing:none": F(2 + 3)})
        self.assertEqual([n for n, _e in attribution.breakdown_parts(data, attribution.FX, "market", market)], ["market:XNYS", "market:none"])
        self.assertEqual([n for n, _e in attribution.breakdown_parts(data, attribution.FX, "currency", market)], ["currency:CNY", "currency:HKD", "currency:USD"])
        total = sum((e for _n, e in attribution.breakdown_parts(data, attribution.FX, "component", market)), F(0))
        self.assertEqual(total, F(1 + 2 + 3 + 4 + 5 + 6 + 7))  # every grouping sums to the whole line

    def test_apportioning_to_a_displayed_total_sums_exactly_and_breaks_ties_in_the_fixed_order(self):
        from performance.numerics import apportion_displayed  # noqa: PLC0415

        self.assertEqual(apportion_displayed(F(1), [F(1, 3)] * 3, 2), (F(34, 100), F(33, 100), F(33, 100)))  # the shortfall of 1 cent goes to the first of three equal remainders
        shown = apportion_displayed(F(125, 100), [F(7, 10), F(11, 20)], 2)  # a displayed total that is not the rounding of the exact one (1.25 against 1.25): floors 0.70 + 0.55
        self.assertEqual((sum(shown, F(0)), shown), (F(125, 100), (F(70, 100), F(55, 100))))
        with self.assertRaises(ValueError):
            apportion_displayed(F(5), [F(1, 3)] * 3, 2)  # a total no apportionment can reach is a defect, never a presented number

    def test_through_the_entry_the_apportioned_parts_sum_to_the_lines_display_value_and_the_exact_parts_to_the_line(self):
        L = post_split_ledger()
        mp.internal_transfer(L, D(2025, 2, 4), mp.A1, mp.A2, quantity=50)
        late = {D(2025, 2, 3): "37.50", D(2025, 2, 4): "37.50", D(2025, 2, 5): "37.73"}  # 200 x 0.23 = 46 over two accounts: 150 x 0.23 = 34.50 and 50 x 0.23 = 11.50
        res = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3), port=mp.market(evidence=None, prices=late))
        shown = {name: s for name, s, _e in metric(res, "attribution_money").breakdown}
        for group in attribution.GROUPS:
            m = metric(res, "attribution_breakdown", group_by=group, line="attr.price")
            self.assertEqual(sum((s for _n, s, _e in m.breakdown), Decimal(0)), shown["attr.price"], group)
            self.assertEqual(sum((e for _n, _s, e in m.breakdown), F(0)), lines_of(res)["attr.price"], group)
            self.assertEqual(dict(m.lineage)["displayed_total"], str(shown["attr.price"]))
        parts = metric(res, "attribution_breakdown", group_by="account", line="attr.price").breakdown
        self.assertEqual([(n[-1], s) for n, s, _e in parts], [("1", Decimal("34.50")), ("2", Decimal("11.50"))])  # by account id: A1 then A2


class LastPrintDateTests(unittest.TestCase):
    """performance/1.9 Ruling 1.1b: `price_date_used` only where a close values the holding; `last_print_date` whenever a print exists, withheld or not; never a value beside it."""

    def holding(self, ledger, day, port, suppressions=(), view="REPORTING"):
        res = engine.compute(ledger.rows, ledger.version, day, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=suppressions)
        return metric(res, "holding_value", account=str(mp.A1)) if False else next(m for m in res.metrics if m.metric_id == "holding_value" and m.view == view)

    def test_a_valued_holding_reports_both_and_they_are_equal(self):
        m = self.holding(mp.base_ledger(), D(2025, 2, 5), mp.market(evidence=None, prices=PRICES))
        lin = dict(m.lineage)
        self.assertEqual((lin["price_date_used"], lin["last_print_date"]), ("2025-02-05", "2025-02-05"))

    def test_a_split_suppressed_holding_reports_the_last_print_and_no_close_and_no_value(self):
        L = mp.base_ledger()
        port = mp.market("real", real_quotes=True)
        sup = mp.detect(L, port)
        for view in ("NATIVE", "REPORTING"):
            m = self.holding(L, D(2025, 2, 5), port, sup, view)
            lin = dict(m.lineage)
            self.assertEqual((m.result.value, m.result.sufficiency_state), (None, INSUFFICIENT), view)
            self.assertNotIn("price_date_used", lin, view)  # no close values it
            self.assertEqual(lin["last_print_date"], "2025-02-05", view)

    def test_a_holding_with_no_print_at_or_before_the_date_reports_neither(self):
        m = self.holding(mp.base_ledger(), D(2025, 1, 15), mp.market(evidence=None, prices=PRICES))
        lin = dict(m.lineage)
        self.assertEqual((m.result.value, "price_date_used" in lin, "last_print_date" in lin), (None, False, False))


class MoneyIsIndependentOfTheBaseTests(unittest.TestCase):
    """performance/1.9 Ruling 9.5: NON_POSITIVE_BASE, NEGATIVE_VALUE and TOTAL_LOSS suppress only the percentage lines; the money lines stay AVAILABLE and sum to G."""

    def test_a_total_loss_has_no_percentage_components_and_the_money_lines_stay_available_and_sum_to_g(self):
        L = mp.pk.Ledger()
        L.add(mp.A1, EventType.DEPOSIT, D(2025, 2, 3), USD, amount=Money(Decimal(10000), USD))
        L.add(mp.A1, EventType.FEE, D(2025, 2, 4), USD, amount=Money(Decimal(10000), USD))  # the whole value is spent on 02-04: r = -1
        res = attribute(L, D(2025, 2, 4))
        money, ret = metric(res, "attribution_money"), metric(res, "attribution_return")
        self.assertEqual((money.result.sufficiency_state, money.exact, lines_of(res)["attr.fees"]), (AVAILABLE, F(-10000), F(-10000)))
        self.assertEqual((ret.result.sufficiency_state, ret.result.reason_code, ret.result.value, ret.breakdown, ret.details), (INSUFFICIENT, None, None, (), ("TOTAL_LOSS",)))
        self.assertTrue(ret.causes)

    def test_a_non_positive_base_leaves_money_available_and_the_breakdowns_present(self):
        L = mp.pk.Ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 2, 3), USD, listing_id=mp.LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
        res = attribute(L, D(2025, 2, 4))
        self.assertEqual(metric(res, "attribution_money").result.sufficiency_state, AVAILABLE)
        self.assertEqual(metric(res, "attribution_return").details, ("NON_POSITIVE_BASE",))
        self.assertEqual(len([m for m in res.metrics if m.metric_id == "attribution_breakdown"]), 8 * 5)  # a money attribution has its drill-downs
        self.assertEqual(metric(res, "attribution_money").exact, metric(res, "attribution_breakdown", group_by="listing", line="attr.price").exact)


class ReproduceTests(unittest.TestCase):
    def test_an_attribution_manifest_is_reproduced_and_a_wrong_digest_is_named(self):
        L = post_split_ledger()
        port = mp.market(evidence=None, prices=PRICES)
        res = attribute(L, D(2025, 2, 5), base=D(2025, 2, 3), port=port)
        ok = engine.reproduce(res.manifest, res.result_digest, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        self.assertEqual(ok.status, ReproductionStatus.REPRODUCED)
        bad = engine.reproduce(res.manifest, "0" * 64, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        self.assertEqual(bad.status, ReproductionStatus.RESULT_DIFFERS)
        self.assertEqual(engine.reproduce(res.manifest, None, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=()).status, ReproductionStatus.RESULT_NOT_COMPARED)


if __name__ == "__main__":
    unittest.main()
