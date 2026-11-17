"""CP3d unit tests that pin what the part-3 golden items do not reach: the gain aggregates' weights and limiting reasons (Ruling 3.10), the lot-book taint's expiry boundary and its
fixed point over a chain whose hops run against the canonical account order, and the event-level taint of a sale. Added after mutation evidence showed these survived the golden items.
"""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_performance_midpoint as mp  # noqa: E402

from domain.currency import Money  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from domain.replay import live_events  # noqa: E402
from performance.gains import _aggregate  # noqa: E402
from performance.inputs import SuppressionInput  # noqa: E402
from performance.states import Valued  # noqa: E402
from performance.taint import carried_taint  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402

D, F = datetime.date, Fraction
AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA
ENV = SimpleNamespace(conventions=mp.PERF)


def ok(exact):
    return Valued(AVAILABLE, None, Fraction(exact), ())


def out(reason):
    return Valued(INSUFFICIENT, reason, None, ())


class AggregateTests(unittest.TestCase):
    def test_the_excluded_weight_is_gross_even_when_a_weight_base_is_negative(self):
        # a short position's market value is negative: the weight is over |MV|, so 100 / (100 + 100 + 200) = 1/4, never the net 100 / 200 style figure
        items = [("a", ok(10), F(100), None), ("b", out("SOURCE_CONFLICT"), F(-100), None), ("c", ok(5), F(-200), None)]
        got = _aggregate(ENV, items, "ref")
        self.assertEqual((got.state, got.exact, got.excluded_weight), (LIMITED, F(15), F(1, 4)))

    def test_a_source_conflict_exclusion_limits_and_does_not_empty_the_aggregate(self):
        got = _aggregate(ENV, [("a", ok(10), F(100), None), ("b", out("SOURCE_CONFLICT"), F(100), None)], "ref")
        self.assertEqual((got.state, got.exact, got.excluded_weight), (LIMITED, F(10), F(1, 2)))
        for reason in ("MISSING_COST_BASIS", "UNRESOLVED_CONVENTION", "UNSUPPORTED_ASSET"):
            self.assertEqual(_aggregate(ENV, [("a", ok(10), F(100), None), ("b", out(reason), F(100), None)], "ref").state, LIMITED, reason)

    def test_an_exclusion_for_any_other_reason_gives_no_number_and_an_empty_set_is_zero(self):
        got = _aggregate(ENV, [("a", ok(10), F(100), None), ("b", out("STALE_DATA"), F(100), None)], "ref")
        self.assertEqual((got.state, got.exact, got.excluded_weight), (INSUFFICIENT, None, None))
        empty = _aggregate(ENV, [], "ref")
        self.assertEqual((empty.state, empty.exact), (AVAILABLE, F(0)))


class TaintBoundaryTests(unittest.TestCase):
    """A CONFLICT_DATE source (Y = 02-03 < X = 02-10) taints what A1 hands A2 on 02-05 until X: a sale ON 02-10 relieves an untainted lot, a sale on 02-09 a tainted one."""

    def taint_for(self, sale_day):
        L = mp.internal_transfer(mp.base_ledger(), D(2025, 2, 5))
        L.add(mp.A2, EventType.SELL, sale_day, mp.USD, listing_id=mp.LISTING, quantity=Decimal(50), amount=Money(Decimal(1875), mp.USD))
        s = SuppressionInput(mp.A1, mp.LISTING, D(2025, 2, 3), D(2025, 2, 10), "SOURCE_CONFLICT", "split dated off its ex-date", D(2025, 2, 10), "CONFLICT_DATE")
        sale = [i.event.event_id for i in L.rows if i.event.event_type is EventType.SELL]
        self.leg = [i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_IN]
        return carried_taint(live_events(L.rows, L.version), (s,)), sale

    def test_a_sale_the_day_before_the_expiry_is_tainted_and_on_the_expiry_it_is_not(self):
        # the receiving leg (02-05, inside the interval) carries the taint whatever the sale does (CP3-18); the sale's own relief is tainted only before the expiry
        taint, sale = self.taint_for(D(2025, 2, 9))
        self.assertEqual(set(taint.event_taints), set(sale) | set(self.leg))
        taint, sale = self.taint_for(D(2025, 2, 10))
        self.assertEqual(set(taint.event_taints), set(self.leg))


class EventTaintOfATransferOutTests(unittest.TestCase):
    def test_the_transfer_out_of_the_last_tainted_units_carries_a_one_day_event_taint_after_the_position_suppression_ended(self):
        # A2 holds the carried units from 02-05 and sends them all out on 02-07: its carried suppression is [02-05, 02-07) and the outflow itself is tainted for 02-07 only.
        # (In a window the engine's use of this taint is masked by the suppressed V_B of the same units, so the derivation is what is pinned here.)
        L = mp.internal_transfer(mp.base_ledger(), D(2025, 2, 5))
        mp.transfer_out(L, D(2025, 2, 7), account=mp.A2)
        taint = carried_taint(live_events(L.rows, L.version), mp.detect(L, mp.market()))
        (out_id,) = [i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_OUT and i.event.account_id == mp.A2]
        self.assertEqual([(c.first_date, c.end_exclusive) for c in taint.suppressions], [(D(2025, 2, 5), D(2025, 2, 7))])
        (leg_id,) = [i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_IN and i.event.account_id == mp.A2]
        # the outflow of 02-07 is tainted for that day only; the receiving leg of 02-05 carries the taint of the units it delivered (CP3-18)
        self.assertEqual({k: (v.first_date, v.end_exclusive) for k, v in taint.event_taints.items()},
                         {out_id: (D(2025, 2, 7), D(2025, 2, 8)), leg_id: (D(2025, 2, 5), D(2025, 2, 6))})


class TaintChainTests(unittest.TestCase):
    def test_a_chain_whose_hops_run_against_the_canonical_account_order_is_taken_to_its_fixed_point(self):
        # A1 -> A3 on 02-05 and A3 -> A2 on 02-06 (the lot's first hop is already out of the F8-suppressed A1; the fixed point itself is pinned by the next class)
        L = mp.base_ledger()
        mp.internal_transfer(L, D(2025, 2, 5), mp.A1, mp.A3)
        mp.internal_transfer(L, D(2025, 2, 6), mp.A3, mp.A2)
        sup = mp.detect(L, mp.market())
        got = carried_taint(live_events(L.rows, L.version), sup).suppressions
        self.assertEqual({c.account_id: (c.first_date, c.end_exclusive) for c in got}, {mp.A3: (D(2025, 2, 5), D(2025, 2, 6)), mp.A2: (D(2025, 2, 6), None)})


class TaintFixedPointTests(unittest.TestCase):
    def test_an_untainted_lot_passing_through_a_position_that_holds_tainted_units_is_tainted_by_the_hop_and_needs_a_second_pass(self):
        # A3 receives 30 clean units (recorded acquisition date 12-10) AFTER the ex-date, then 50 tainted units from A1 on 02-05; on 02-06 it sends 30 on to A2. FIFO relieves the
        # older clean lot, but A3 is suppressed on 02-06 (its book holds the tainted lot), so the lot leaving it is tainted by that hop: a fact only a second pass can see.
        L = mp.base_ledger()
        L.add(mp.A3, EventType.TRANSFER_IN, D(2025, 2, 4), mp.USD, listing_id=mp.LISTING, quantity=Decimal(30), acquired_on=D(2024, 12, 10))
        mp.internal_transfer(L, D(2025, 2, 5), mp.A1, mp.A3, quantity=50)
        mp.internal_transfer(L, D(2025, 2, 6), mp.A3, mp.A2, quantity=30)
        sup = mp.detect(L, mp.market())
        self.assertEqual([s.account_id for s in sup], [mp.A1])  # A3 holds nothing on the ex-date: the F8 suppression is A1's alone
        got = carried_taint(live_events(L.rows, L.version), sup).suppressions
        self.assertEqual({c.account_id: (c.first_date, c.end_exclusive) for c in got}, {mp.A3: (D(2025, 2, 5), None), mp.A2: (D(2025, 2, 6), None)})


if __name__ == "__main__":
    unittest.main()
