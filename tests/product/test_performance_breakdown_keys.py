"""performance/1.10 Ruling 9.6: every contribution has exactly ONE key in each grouping (listing, market, currency, account, component), so every grouping sums to the line exactly.

One test per keying rule, on the golden portfolios that carry the case (the values are the Quant's derivations in `CP3_GOLDEN_PART4_DERIVATION.md`):
- P21 (HKD dividend accrued from its ex-date, a receivable revalued by FX, a withholding): a receivable's FX goes to its dividend's listing and market; paid, it is cash (`none`); the dividend (income) and
  its withholding are events keyed by their listing and currency; the component of an event is `event`;
- P12 (Example W': a conversion, a fee on a listing, a dividend, a withholding): a conversion result is `none` by listing, market and currency and `event` by component.
"""

import sys
import unittest
import uuid
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp3_golden_part4_kit as p4  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from performance import attribution  # noqa: E402

F = Fraction
H700 = "c0000000-0000-4000-8000-000000000700"
DIVIDEND_EVENT = "e2b00000-0000-4000-8000-000000000003"
SINCE = {"rule": "SINCE_INCEPTION"}


class _Shared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        cls.runner, cls.market = p4.build_runner(cls.ids, verify_identities=True)
        cls.addClassCleanup(cls.market.close)

    def attribution(self, prefix, assertion_id):
        p = next(x for x in p4.FIXTURE["portfolios"] if x["name"].split()[0] == prefix)
        a = next(x for x in p["assertions"] if x["id"] == assertion_id)
        return self.runner.attribution(p, a, SINCE)

    def parts(self, res, line, group):
        m = next(x for x in res.metrics if x.metric_id == "attribution_breakdown" and dict(x.subject) == {"group_by": group, "line": line})
        return {name: exact for name, _shown, exact in m.breakdown}


class KeyingRuleTests(_Shared):
    def test_a_receivables_fx_goes_to_its_dividends_listing_and_market_and_a_paid_one_is_cash_none(self):
        res = self.attribution("P21", "P21-A1")
        listing = self.parts(res, "attr.fx", "listing")
        self.assertEqual(listing, {f"listing:{H700}": F(-280, 39) + F(-16, 39), "listing:none": F(-40, 39)})  # position + receivable; the HKD cash is none
        self.assertEqual(self.parts(res, "attr.fx", "market"), {"market:XHKG": F(-296, 39), "market:none": F(-40, 39)})
        self.assertEqual(self.parts(res, "attr.fx", "component"), {f"position:{H700}": F(-280, 39), "cash:HKD": F(-40, 39), f"receivable:{DIVIDEND_EVENT}": F(-16, 39)})
        self.assertEqual(self.parts(res, "attr.fx", "currency"), {"currency:HKD": F(-336, 39)})  # position, cash and receivable are all HKD

    def test_income_and_withholding_events_are_keyed_by_listing_currency_and_event(self):
        res = self.attribution("P21", "P21-A1")
        for line, exact in (("attr.income", F(10000, 39)), ("attr.taxes", F(-128, 5))):
            self.assertEqual(self.parts(res, line, "listing"), {f"listing:{H700}": exact}, line)  # the listing the event names (Ruling 8.4)
            self.assertEqual(self.parts(res, line, "market"), {"market:XHKG": exact}, line)
            self.assertEqual(self.parts(res, line, "currency"), {"currency:HKD": exact}, line)  # the event currency
        income_event = [n for n in self.parts(res, "attr.income", "component")]
        self.assertEqual(income_event, [f"event:{DIVIDEND_EVENT}"])  # a new component kind keyed by event id
        self.assertEqual(list(self.parts(res, "attr.taxes", "component")), ["event:e2b00000-0000-4000-8000-000000000004"])

    def test_a_conversion_result_is_none_by_listing_market_and_currency_and_an_event_by_component(self):
        res = self.attribution("P12", "P12-A1")
        conversion = F(-1000, 39)
        self.assertEqual(self.parts(res, "attr.conversion", "listing"), {"listing:none": conversion})
        self.assertEqual(self.parts(res, "attr.conversion", "market"), {"market:none": conversion})
        self.assertEqual(self.parts(res, "attr.conversion", "currency"), {"currency:none": conversion})
        (name,) = self.parts(res, "attr.conversion", "component")
        self.assertTrue(name.startswith("event:"))
        (account,) = self.parts(res, "attr.conversion", "account")
        self.assertTrue(account.startswith("account:"))

    def test_a_fee_names_its_listing_and_its_currency(self):
        res = self.attribution("P12", "P12-A1")
        fee = F(-50, 39)
        (listing,) = self.parts(res, "attr.fees", "listing")
        self.assertTrue(listing.startswith("listing:") and listing != "listing:none")  # the fee names the listing it was paid on
        self.assertEqual(self.parts(res, "attr.fees", "currency"), {"currency:HKD": fee})
        self.assertEqual(list(self.parts(res, "attr.fees", "market")), [f"market:{next(iter(self.parts(res, 'attr.fees', 'market'))).split(':')[1]}"])
        self.assertNotEqual(next(iter(self.parts(res, "attr.fees", "market"))), "market:none")

    def test_the_component_order_runs_positions_cash_receivables_then_events_and_none_is_last(self):
        C = attribution.Component
        a, e1, e2 = str(uuid.UUID(int=1)), str(uuid.UUID(int=10)), str(uuid.UUID(int=20))
        l1 = str(uuid.UUID(int=5))
        keys = [C("event", a, "", "", e1).part("component", str)[1], C("receivable", a, l1, "HKD", e2).part("component", str)[1], C("cash", a, "", "USD").part("component", str)[1],
                C("position", a, l1, "HKD").part("component", str)[1]]
        self.assertEqual(sorted(keys), [keys[3], keys[2], keys[1], keys[0]])  # position < cash < receivable < event
        self.assertGreater(C("cash", a, "", "USD").part("listing", str)[1], C("position", a, l1, "HKD").part("listing", str)[1])  # none sorts last
        self.assertGreater(C("cash", a, "", "USD").part("market", str)[1], C("position", a, l1, "HKD").part("market", lambda _l: "XNYS")[1])
        self.assertEqual(C("cash", a, "", "USD").part("market", str)[0], "market:none")
        self.assertEqual(C("receivable", a, l1, "HKD", e2).part("market", lambda _l: "XHKG")[0], "market:XHKG")


class EveryGroupingSumsTests(_Shared):
    def test_every_grouping_of_every_line_sums_exactly_to_the_line_and_to_its_display_value(self):
        from decimal import Decimal  # noqa: PLC0415

        for prefix, aid in (("P21", "P21-A1"), ("P12", "P12-A1"), ("P1", "P1-A1")):  # receivable, events and a conversion; P1 has fees, financing and a conversion over 180 days
            res = self.attribution(prefix, aid)
            money = next(m for m in res.metrics if m.metric_id == "attribution_money")
            lines = {n: (s, e) for n, s, e in money.breakdown}
            groups = [m for m in res.metrics if m.metric_id == "attribution_breakdown"]
            self.assertEqual(len(groups), 8 * 5, aid)
            for m in groups:
                sub = dict(m.subject)
                shown_line, exact_line = lines[sub["line"]]
                self.assertEqual(sum((e for _n, _s, e in m.breakdown), F(0)), exact_line, (aid, sub))
                self.assertEqual(sum((s for _n, s, _e in m.breakdown), Decimal(0)), shown_line, (aid, sub))
                names = [n for n, _s, _e in m.breakdown]
                if f"{sub['group_by']}:none" in names:
                    self.assertEqual(names[-1], f"{sub['group_by']}:none", (aid, sub))  # none is last


if __name__ == "__main__":
    unittest.main()
