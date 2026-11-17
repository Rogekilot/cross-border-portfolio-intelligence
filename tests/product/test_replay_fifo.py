"""The FIFO/1 mode of the one lot fold (`ledger-replay/1.4` Ruling 0.5, `1.5` Ruling 0.6): `domain.replay.reconstruct_fifo`.

Every expected value is derived by hand in the methodology's own examples (F-A to F-L), cited by name. The `none` mode (`reconstruct`) is untouched and is compared where Ruling
0.5.13 says the two modes agree.
"""

import datetime
import itertools
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, SplitRatio  # noqa: E402
from domain.replay import (  # noqa: E402
    DATE_ENTRY, DATE_RECORDED, DATE_TRADE, FIFO_CONVENTION_SET_ID, LOT_METHOD_ID, ReplayDetail, reconstruct, reconstruct_fifo,
)

D = datetime.date
F = Fraction
USD, HKD = CurrencyCode("USD"), CurrencyCode("HKD")
A1, A2, A3 = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)
U = uuid.UUID(int=900)  # the listing


class Book:
    """A hand-written ledger with consecutive ledger_seq (`pk.Ledger`), with small helpers."""

    def __init__(self, base=4000):
        self.L = pk.Ledger(base)

    def buy(self, account, day, units, cost, listing=U, ccy=USD):
        self.L.add(account, EventType.BUY, day, ccy, listing_id=listing, quantity=Decimal(units), amount=Money(Decimal(cost), ccy))
        return self.L.rows[-1].event.event_id

    def sell(self, account, day, units, proceeds, listing=U, ccy=USD):
        self.L.add(account, EventType.SELL, day, ccy, listing_id=listing, quantity=Decimal(units), amount=Money(Decimal(proceeds), ccy))
        return self.L.rows[-1].event.event_id

    def opening(self, account, day, units, cost=None, acquired_on=None, listing=U, ccy=USD):
        kw = dict(listing_id=listing, quantity=Decimal(units))
        if cost is not None:
            kw["cost_basis"] = Money(Decimal(cost), ccy)
        if acquired_on is not None:
            kw["acquired_on"] = acquired_on
        self.L.add(account, EventType.OPENING_POSITION, day, ccy, **kw)
        return self.L.rows[-1].event.event_id

    def transfer_in(self, account, day, units, cost=None, acquired_on=None, listing=U, ccy=USD):
        kw = dict(listing_id=listing, quantity=Decimal(units))
        if cost is not None:
            kw["cost_basis"] = Money(Decimal(cost), ccy)
        if acquired_on is not None:
            kw["acquired_on"] = acquired_on
        self.L.add(account, EventType.TRANSFER_IN, day, ccy, **kw)
        return self.L.rows[-1].event.event_id

    def move(self, source, receiver, day, units, listing=U, ccy=USD):
        self.L.add(source, EventType.TRANSFER_OUT, day, ccy, listing_id=listing, quantity=Decimal(units), counterparty_account_id=receiver)
        out = self.L.rows[-1].event.event_id
        self.L.add(receiver, EventType.TRANSFER_IN, day, ccy, listing_id=listing, quantity=Decimal(units), counterparty_account_id=source)
        return out, self.L.rows[-1].event.event_id

    def split(self, account, day, n, o, listing=U):
        self.L.add(account, EventType.SPLIT, day, USD, listing_id=listing, split_ratio=SplitRatio(Decimal(n), Decimal(o)))

    def fifo(self, day, version=None):
        return reconstruct_fifo(self.L.rows, day, self.L.version if version is None else version)

    def none(self, day):
        return reconstruct(self.L.rows, day, self.L.version)


def book_of(state, account, listing=U):
    return state.book(account, listing)


class FifoBasicsTests(unittest.TestCase):
    def test_f_a_example_04_c_under_fifo_lot1_is_relieved_first_and_none_stays_unresolved(self):
        b = Book()
        b.buy(A1, D(2025, 3, 3), 100, 1000)
        b.buy(A1, D(2025, 3, 4), 100, 1200)
        sale = b.sell(A1, D(2025, 3, 5), 50, 700)
        st = b.fifo(D(2025, 3, 31))
        relief = st.relief(sale)
        self.assertEqual([(p.units, p.basis, p.acquisition_date) for p in relief.portions], [(F(50), F(500), D(2025, 3, 3))])
        book = book_of(st, A1)
        self.assertEqual([(lot.units, lot.basis) for lot in book.lots], [(F(50), F(500)), (F(100), F(1200))])  # remaining 1,700, AVAILABLE
        self.assertEqual(sum(lot.basis for lot in book.lots), F(1700))
        none = b.none(D(2025, 3, 31)).account(A1).positions[0]
        self.assertIn(ReplayDetail.LOT_DEPLETION, none.basis_detail)  # the none mode (ledger-replay/1.3) reports it unresolved
        self.assertEqual((st.state.convention_set, st.lot_method, b.none(D(2025, 3, 31)).convention_set), (FIFO_CONVENTION_SET_ID, LOT_METHOD_ID, "ledger-replay/1.3"))
        self.assertEqual(st.conservation_failures, ())

    def test_f_b_example_04_d_same_day_buy_and_sale_in_either_entry_order(self):
        results = []
        for sale_first in (True, False):
            b = Book()
            b.buy(A1, D(2025, 3, 3), 100, 1000)
            if sale_first:
                s = b.sell(A1, D(2025, 3, 5), 100, 1100)
                b.buy(A1, D(2025, 3, 5), 50, 600)
            else:
                b.buy(A1, D(2025, 3, 5), 50, 600)
                s = b.sell(A1, D(2025, 3, 5), 100, 1100)
            st = b.fifo(D(2025, 3, 31))
            relief = st.relief(s)
            self.assertEqual([p.basis for p in relief.portions], [F(1000)])  # A whole: the start-of-day lot is older than the same-day buy
            self.assertEqual([(lot.units, lot.basis, lot.date_kind) for lot in book_of(st, A1).lots], [(F(50), F(600), DATE_TRADE)])
            results.append(st.canonical_json().replace(str(s), "S"))
        self.assertEqual(len(results), 2)

    def test_f_c_one_dates_lots_pro_rata_with_fractional_lot_units_in_any_entry_order(self):
        outs = set()
        for order in itertools.permutations(range(3)):
            b = Book()
            l0 = b.buy(A1, D(2025, 3, 3), 30, 270)
            steps = [lambda: b.sell(A1, D(2025, 3, 5), 80, 880), lambda: b.buy(A1, D(2025, 3, 5), 100, 1040), lambda: b.buy(A1, D(2025, 3, 5), 50, 580)]
            made = {}
            for i in order:
                made[i] = steps[i]()
            st = b.fifo(D(2025, 3, 5))
            relief = st.relief(made[0])
            by_origin = {p.origin_event_id: p for p in relief.portions}
            self.assertEqual(by_origin[l0].units, F(30))
            self.assertEqual(by_origin[made[1]].units, F(100, 3))
            self.assertEqual(by_origin[made[1]].basis, F(1040, 3))
            self.assertEqual(by_origin[made[2]].units, F(50, 3))
            self.assertEqual(by_origin[made[2]].basis, F(580, 3))
            self.assertEqual(sum(p.basis for p in relief.portions), F(810))
            book = book_of(st, A1)
            self.assertEqual({lot.origin_event_id: (lot.units, lot.basis) for lot in book.lots},
                             {made[1]: (F(200, 3), F(2080, 3)), made[2]: (F(100, 3), F(1160, 3))})
            self.assertEqual(sum(lot.basis for lot in book.lots), F(1080))
            # 03-10: sell 40 from the one group (U_g = 100)
            sale2 = b.sell(A1, D(2025, 3, 10), 40, 480)
            st2 = b.fifo(D(2025, 3, 31))
            self.assertEqual(sum(p.basis for p in st2.relief(sale2).portions), F(432))
            self.assertEqual(sum(lot.basis for lot in book_of(st2, A1).lots), F(648))
            outs.add(tuple((p.units, p.basis) for p in sorted(st2.relief(sale2).portions, key=lambda p: p.unit_cost)))
        self.assertEqual(len(outs), 1)  # the entry order changes no value

    def test_unknown_basis_stays_with_its_units_and_mixed_never_unresolves_f_f(self):
        b = Book()
        x = b.transfer_in(A1, D(2025, 3, 3), 10)  # no cost_basis: an unknown ENTRY lot
        y = b.buy(A1, D(2025, 3, 4), 10, 1000)
        s = b.sell(A1, D(2025, 3, 5), 10, 1200)
        st = b.fifo(D(2025, 3, 31))
        relief = st.relief(s)
        self.assertEqual([(p.origin_event_id, p.unit_cost, p.basis_currency, p.date_kind) for p in relief.portions], [(x, None, None, DATE_ENTRY)])
        self.assertTrue(relief.has_unknown_basis)
        self.assertEqual([(lot.origin_event_id, lot.basis) for lot in book_of(st, A1).lots], [(y, F(1000))])  # the remaining Y is known
        b2 = Book()
        b2.transfer_in(A1, D(2025, 3, 3), 10)
        y2 = b2.buy(A1, D(2025, 3, 4), 10, 1000)
        s2 = b2.sell(A1, D(2025, 3, 5), 15, 1800)
        st2 = b2.fifo(D(2025, 3, 31))
        self.assertEqual([(p.units, p.basis) for p in st2.relief(s2).portions], [(F(10), None), (F(5), F(500))])  # the known portion is still exposed
        self.assertEqual([(lot.origin_event_id, lot.units, lot.basis) for lot in book_of(st2, A1).lots], [(y2, F(5), F(500))])
        none = b2.none(D(2025, 3, 31)).account(A1).positions[0]
        self.assertIn(ReplayDetail.LOT_DEPLETION, none.basis_detail)  # none: unresolved

    def test_a_split_rescales_units_and_cost_and_keeps_every_other_attribute(self):
        b = Book()
        buy = b.buy(A1, D(2025, 1, 6), 50, 7500)
        b.split(A1, D(2025, 2, 3), 4, 1)
        sale = b.sell(A1, D(2025, 3, 3), 50, 2250)
        st = b.fifo(D(2025, 3, 4))
        (portion,) = st.relief(sale).portions
        self.assertEqual((portion.units, portion.unit_cost, portion.basis, portion.acquisition_date, portion.origin_event_id), (F(50), F(75, 2), F(1875), D(2025, 1, 6), buy))
        (lot,) = book_of(st, A1).lots
        self.assertEqual((lot.units, lot.basis), (F(150), F(5625)))  # Example 0.4-A: remaining basis 5,625
        none = b.none(D(2025, 3, 4)).account(A1).positions[0]
        self.assertEqual(none.cost_basis[0].result.value, Decimal("5625"))  # 0.5.13: where none is determinate, FIFO agrees

    def test_a_correction_that_redates_a_purchase_changes_the_relief_at_the_new_ledger_version_f_h(self):
        b = Book()
        a = b.buy(A1, D(2025, 3, 3), 100, 900)  # seq 1
        bb = b.buy(A1, D(2025, 3, 5), 100, 1100)  # seq 2
        sale = b.sell(A1, D(2025, 3, 10), 100, 1200)  # seq 3
        v_old = b.L.version
        b.L.add(A1, EventType.REVERSAL, D(2025, 3, 3), USD, reverses_event_id=a)
        b.L.add(A1, EventType.BUY, D(2025, 3, 6), USD, listing_id=U, quantity=Decimal(100), amount=Money(Decimal(1120), USD), corrects_event_id=a)
        a2 = b.L.rows[-1].event.event_id
        old, new = b.fifo(D(2025, 3, 31), v_old), b.fifo(D(2025, 3, 31))
        self.assertEqual([(p.origin_event_id, p.basis) for p in old.relief(sale).portions], [(a, F(900))])  # the old L still reproduces 900
        self.assertEqual([(p.origin_event_id, p.basis) for p in new.relief(sale).portions], [(bb, F(1100))])  # A' is dated after B
        self.assertEqual([(lot.origin_event_id, lot.basis) for lot in book_of(new, A1).lots], [(a2, F(1120))])
        early = b.fifo(D(2025, 3, 5))
        self.assertEqual([(lot.origin_event_id, lot.basis) for lot in book_of(early, A1).lots], [(bb, F(1100))])  # A never existed; A' is dated after D

    def test_a_flagged_position_relieves_nothing_and_presents_no_book(self):
        b = Book()
        b.buy(A1, D(2025, 3, 3), 10, 100)
        s = b.sell(A1, D(2025, 3, 5), 15, 200)  # ends at -5: LEDGER_INCONSISTENT
        st = b.fifo(D(2025, 3, 31))
        relief = st.relief(s)
        self.assertTrue(relief.withheld)
        self.assertEqual(relief.causes, (ReplayDetail.NEGATIVE_QUANTITY,))
        book = book_of(st, A1)
        self.assertEqual((book.lots, book.quantity, book.causes), ((), None, (ReplayDetail.NEGATIVE_QUANTITY,)))


class CarryTests(unittest.TestCase):
    def build_p16(self):
        b = Book()
        a = b.buy(A1, D(2025, 3, 3), 100, 900)  # T1: 100 at 9
        bb = b.buy(A1, D(2025, 3, 5), 100, 1100)  # T1: 100 at 11
        o = b.buy(A2, D(2025, 3, 6), 100, 1120)  # T2: 100 at 56/5
        out1, in1 = b.move(A1, A2, D(2025, 3, 7), 150)
        s1 = b.sell(A2, D(2025, 3, 10), 120, 1440)
        s2 = b.sell(A2, D(2025, 3, 12), 40, 520)
        out2, in2 = b.move(A2, A1, D(2025, 3, 12), 50)
        s3 = b.sell(A1, D(2025, 3, 14), 60, 780)
        return b, dict(a=a, b=bb, o=o, out1=out1, in1=in1, s1=s1, s2=s2, out2=out2, in2=in2, s3=s3)

    def test_f_d_a_partial_move_carries_the_oldest_units_and_the_receiver_relieves_carried_lots_first(self):
        b, ids = self.build_p16()
        st = b.fifo(D(2025, 3, 7))
        self.assertEqual([(p.origin_event_id, p.units, p.basis) for p in st.relief(ids["out1"]).portions], [(ids["a"], F(100), F(900)), (ids["b"], F(50), F(550))])
        t1, t2 = book_of(st, A1), book_of(st, A2)
        self.assertEqual([(lot.origin_event_id, lot.units, lot.basis) for lot in t1.lots], [(ids["b"], F(50), F(550))])
        got = {(lot.origin_event_id, tuple(h.out_event_id for h in lot.hops)): (lot.units, lot.basis, lot.acquisition_date) for lot in t2.lots}
        self.assertEqual(got, {(ids["a"], (ids["out1"],)): (F(100), F(900), D(2025, 3, 3)), (ids["b"], (ids["out1"],)): (F(50), F(550), D(2025, 3, 5)),
                               (ids["o"], ()): (F(100), F(1120), D(2025, 3, 6))})
        hop = t2.lots[0].hops[0]
        self.assertEqual((hop.source_account_id, hop.out_event_id, hop.in_event_id, hop.date), (A1, ids["out1"], ids["in1"], D(2025, 3, 7)))
        self.assertEqual(sum(lot.basis for lot in t1.lots) + sum(lot.basis for lot in t2.lots), F(3120))  # the portfolio total is unchanged
        none = b.none(D(2025, 3, 7))
        self.assertIn(ReplayDetail.LOT_DEPLETION, none.account(A1).positions[0].basis_detail)  # none: both sides unresolved
        # 03-10: the receiver relieves a' 100 (900) then b' 20 (220): 1,120, not its own `o` first
        st10 = b.fifo(D(2025, 3, 10))
        self.assertEqual(sum(p.basis for p in st10.relief(ids["s1"]).portions), F(1120))

    def test_f_e_a_sale_and_a_move_on_one_day_each_take_their_share_of_every_portion(self):
        b, ids = self.build_p16()
        st = b.fifo(D(2025, 3, 12))
        sale = {p.origin_event_id: p for p in st.relief(ids["s2"]).portions}
        move = {p.origin_event_id: p for p in st.relief(ids["out2"]).portions}
        self.assertEqual((sale[ids["b"]].units, sale[ids["b"]].basis, sale[ids["o"]].units, sale[ids["o"]].basis), (F(40, 3), F(440, 3), F(80, 3), F(896, 3)))
        self.assertEqual((move[ids["b"]].units, move[ids["b"]].basis, move[ids["o"]].units, move[ids["o"]].basis), (F(50, 3), F(550, 3), F(100, 3), F(1120, 3)))
        self.assertEqual(sum(p.basis for p in sale.values()), F(1336, 3))
        t1 = book_of(st, A1)
        self.assertEqual(sum(lot.basis for lot in t1.lots), F(3320, 3))
        two_hops = [lot for lot in t1.lots if len(lot.hops) == 2]
        self.assertEqual([(lot.units, lot.basis, tuple(h.date for h in lot.hops)) for lot in two_hops], [(F(50, 3), F(550, 3), (D(2025, 3, 7), D(2025, 3, 12)))])
        # 03-14: T1 sells 60; b and b'' share a = 03-05 and are relieved pro rata: 45 and 15, 660
        st14 = b.fifo(D(2025, 3, 14))
        parts = {(p.origin_event_id, len(p.hops)): (p.units, p.basis) for p in st14.relief(ids["s3"]).portions}
        self.assertEqual(parts, {(ids["b"], 0): (F(45), F(495)), (ids["b"], 2): (F(15), F(165))})
        self.assertEqual(sum(lot.basis for lot in book_of(st14, A1).lots), F(1340, 3))

    def test_the_whole_fold_is_independent_of_entry_order_within_a_day_carry_histories_included(self):
        b, ids = self.build_p16()
        base = b.fifo(D(2025, 3, 31)).canonical_json()
        rows = list(b.L.rows)
        from domain.replay import SequencedEvent  # noqa: PLC0415

        for order in itertools.islice(itertools.permutations([r for r in rows if r.event.event_date == D(2025, 3, 12)]), 6):
            others = [r for r in rows if r.event.event_date != D(2025, 3, 12)]
            seqs = sorted(r.ledger_seq for r in rows if r.event.event_date == D(2025, 3, 12))
            shuffled = others + [SequencedEvent(s, r.event) for s, r in zip(seqs, order)]
            self.assertEqual(reconstruct_fifo(shuffled, D(2025, 3, 31), b.L.version).canonical_json(), base)

    def test_f_j_the_none_mode_values_are_reproduced_where_it_is_determinate(self):
        b = Book()
        b.buy(A1, D(2025, 3, 1), 100, 1000)
        b.sell(A1, D(2025, 3, 5), 40, 500)
        b.move(A1, A3, D(2025, 3, 5), 60)  # G1: one candidate lot, 40 sold and 60 moved each take c = 10
        st = b.fifo(D(2025, 3, 31))
        (lot,) = book_of(st, A3).lots
        self.assertEqual((lot.units, lot.basis), (F(60), F(600)))
        none = b.none(D(2025, 3, 31)).account(A3).positions[0]
        self.assertEqual(none.cost_basis[0].result.value, Decimal("600"))
        for pos_fifo, pos_none in zip(st.state.accounts, b.none(D(2025, 3, 31)).accounts):  # quantities and cash are identical in both modes
            self.assertEqual([p.quantity for p in pos_fifo.positions], [p.quantity for p in pos_none.positions])
            self.assertEqual(pos_fifo.cash, pos_none.cash)

    def test_an_opaque_lot_makes_the_receiver_basis_unresolved_until_it_ends_a_day_at_zero_f_g(self):
        b = Book()
        b.buy(A3, D(2025, 3, 1), 20, 200)
        b.buy(A1, D(2025, 3, 2), 10, 100)
        b.sell(A1, D(2025, 3, 5), 15, 150)  # with the move below A1 ends at -10
        out, inn = b.move(A1, A3, D(2025, 3, 5), 5)
        later = b.sell(A3, D(2025, 3, 8), 10, 120)
        st = b.fifo(D(2025, 3, 31))
        self.assertEqual(book_of(st, A1).causes, (ReplayDetail.NEGATIVE_QUANTITY,))
        t3 = book_of(st, A3)
        self.assertEqual((t3.quantity, t3.lots, t3.causes), (F(15), (), (ReplayDetail.NEGATIVE_QUANTITY,)))  # its quantity is AVAILABLE; its book is withheld
        self.assertEqual(st.relief(later).causes, (ReplayDetail.NEGATIVE_QUANTITY,))


class RecordedLotTests(unittest.TestCase):
    """Ruling 0.6 (`acquired_on`): F-K, F-L, F-M."""

    def build(self):
        b = Book()
        s = D(2025, 3, 31)
        o1 = b.opening(A1, s, 400, 14000, acquired_on=D(2025, 1, 4), ccy=HKD)
        o2 = b.opening(A1, s, 600, 18000, acquired_on=D(2025, 1, 8), ccy=HKD)
        o3 = b.opening(A1, s, 200, 7600, ccy=HKD)
        o4 = b.opening(A1, s, 100, 3200, acquired_on=D(2024, 12, 16), ccy=HKD)
        s1 = b.sell(A1, D(2025, 4, 7), 450, 16200, ccy=HKD)
        s2 = b.sell(A1, D(2025, 4, 10), 250, 9000, ccy=HKD)
        out, inn = b.move(A1, A2, D(2025, 4, 15), 100, ccy=HKD)
        return b, dict(o1=o1, o2=o2, o3=o3, o4=o4, s1=s1, s2=s2, out=out)

    def test_f_k_opening_lots_are_ordered_by_their_recorded_dates_whatever_the_entry_order(self):
        b, ids = self.build()
        st = b.fifo(D(2025, 4, 10))
        first = {p.origin_event_id: (p.units, p.basis) for p in st.relief(ids["s1"]).portions}
        self.assertEqual(first, {ids["o4"]: (F(100), F(3200)), ids["o1"]: (F(350), F(12250))})
        second = {p.origin_event_id: (p.units, p.basis) for p in st.relief(ids["s2"]).portions}
        self.assertEqual(second, {ids["o1"]: (F(50), F(1750)), ids["o2"]: (F(200), F(6000))})
        kinds = {p.origin_event_id: (p.date_kind, p.acquisition_date) for p in st.relief(ids["s1"]).portions}
        self.assertEqual(kinds, {ids["o4"]: (DATE_RECORDED, D(2024, 12, 16)), ids["o1"]: (DATE_RECORDED, D(2025, 1, 4))})
        entry = [lot for lot in book_of(st, A1).lots if lot.origin_event_id == ids["o3"]]
        self.assertEqual([(lot.date_kind, lot.acquisition_date) for lot in entry], [(DATE_ENTRY, D(2025, 3, 31))])  # an ENTRY lot is never given a RECORDED date

    def test_f_l_a_carried_recorded_lot_keeps_its_date_and_kind(self):
        b, ids = self.build()
        st = b.fifo(D(2025, 4, 15))
        self.assertEqual([(p.origin_event_id, p.units, p.basis) for p in st.relief(ids["out"]).portions], [(ids["o2"], F(100), F(3000))])
        (carried,) = book_of(st, A2).lots
        self.assertEqual((carried.origin_event_id, carried.acquisition_date, carried.date_kind, len(carried.hops)), (ids["o2"], D(2025, 1, 8), DATE_RECORDED, 1))
        q1 = {lot.origin_event_id: lot.units for lot in book_of(st, A1).lots}
        self.assertEqual(q1, {ids["o2"]: F(300), ids["o3"]: F(200)})

    def test_f_m_the_snapshot_horizon_is_unchanged_and_the_none_mode_never_reads_the_date(self):
        b, ids = self.build()
        before = b.fifo(D(2025, 3, 30))
        self.assertEqual(before.state.accounts[0].status.value, "NOT_RECONSTRUCTABLE")
        # the none mode ignores acquired_on: the same ledger without the field gives byte-identical none output
        import dataclasses  # noqa: PLC0415
        from domain.replay import SequencedEvent  # noqa: PLC0415

        stripped = [SequencedEvent(r.ledger_seq, dataclasses.replace(r.event, acquired_on=None)) for r in b.L.rows]
        self.assertEqual(reconstruct(b.L.rows, D(2025, 4, 30), b.L.version).canonical_json(), reconstruct(stripped, D(2025, 4, 30), b.L.version).canonical_json())
        # while the FIFO mode reads it: the relief changes
        self.assertNotEqual(b.fifo(D(2025, 4, 30)).canonical_json(), reconstruct_fifo(stripped, D(2025, 4, 30), b.L.version).canonical_json())

    def test_acquired_on_equal_to_the_event_date_is_recorded_not_entry(self):
        b = Book()
        o = b.opening(A1, D(2025, 3, 31), 10, 100, acquired_on=D(2025, 3, 31))
        (lot,) = book_of(b.fifo(D(2025, 3, 31)), A1).lots
        self.assertEqual((lot.origin_event_id, lot.date_kind), (o, DATE_RECORDED))


if __name__ == "__main__":
    unittest.main()
