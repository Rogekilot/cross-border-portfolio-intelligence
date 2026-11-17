"""CP1-C unit tests for `domain.replay` (ledger-replay/1.3).

Every EXPECTED value below is copied from the worked example named in the test,
in `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (hand-derived by the Quant),
never taken from this code's output. Under 1.2 the remaining or carried basis is a
number wherever every admissible depletion method agrees (Ruling 0.4) and an
explicit unresolved state elsewhere; the review-fix tests (C1C-1..C1C-6) are marked.
"""

import dataclasses
import datetime
import decimal
import re
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, CurrencyMismatchError, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from domain.replay import (  # noqa: E402
    CONVENTION_SET_ID,
    AccountStatus,
    ReplayDetail,
    ReplayInputError,
    SequencedEvent,
    UnknownAccountError,
    reconstruct,
)
from product_contract.metric_state import MetricResult  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

USD, HKD, CNY = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("CNY")
A1, A2, A3 = (uuid.UUID(int=(0xA << 120) + i) for i in (1, 2, 3))
U, H, M = (uuid.UUID(int=(0xB << 120) + i) for i in (1, 2, 3))  # U@XNYS, H@XHKG, M@XNYS


def d(text):
    return datetime.date.fromisoformat(text)


def eid(seq):
    return uuid.UUID(int=(0xE << 120) + seq)


def E(seq, kind, acct, date, ccy=USD, listing=None, q=None, amt=None, basis=None,
      bought=None, ratio=None, cp=None, settle=None, reverses=None, corrects=None):
    """`amt`/`basis` are strings in `ccy`; `bought` is (string, CurrencyCode)."""
    return SequencedEvent(seq, LedgerEvent(
        event_id=eid(seq), account_id=acct, event_type=kind, event_date=d(date), currency=ccy,
        listing_id=listing,
        quantity=None if q is None else Decimal(q),
        amount=None if amt is None else Money(Decimal(amt), ccy),
        cost_basis=None if basis is None else Money(Decimal(basis), ccy),
        bought_amount=None if bought is None else Money(Decimal(bought[0]), bought[1]),
        split_ratio=None if ratio is None else SplitRatio(Decimal(ratio[0]), Decimal(ratio[1])),
        counterparty_account_id=cp,
        settlement_date=None if settle is None else d(settle),
        reverses_event_id=None if reverses is None else eid(reverses),
        corrects_event_id=None if corrects is None else eid(corrects),
    ))


def deposit(seq, acct, date, amt, ccy=USD):
    return E(seq, EventType.DEPOSIT, acct, date, ccy, amt=amt)


def unbounded(item, **fields):
    """A copy of `item` with fields set WITHOUT the domain's numeric bounds (migration 0008
    bounds new rows; rows stored earlier can hold any NUMERIC, and replay must still never
    raise for them). Amounts and cost bases are given as strings in the event currency."""
    event = item.event
    clone = object.__new__(LedgerEvent)
    for field in dataclasses.fields(LedgerEvent):
        object.__setattr__(clone, field.name, getattr(event, field.name))
    for name, value in fields.items():
        if name in ("amount", "cost_basis"):
            value = Money(Decimal(value), event.currency)
        elif name == "quantity":
            value = Decimal(value)
        object.__setattr__(clone, name, value)
    return SequencedEvent(item.ledger_seq, clone)


def big_deposit(seq, acct, date, amt, ccy=USD):
    return unbounded(deposit(seq, acct, date, "1", ccy), amount=amt)


def buy(seq, acct, listing, date, q, amt, ccy=USD, **kw):
    return E(seq, EventType.BUY, acct, date, ccy, listing=listing, q=q, amt=amt, **kw)


def sell(seq, acct, listing, date, q, amt, ccy=USD):
    return E(seq, EventType.SELL, acct, date, ccy, listing=listing, q=q, amt=amt)


class BasisView:
    """Test-side convenience over `position_basis`: `.value` is the tuple of Money
    (None when not presented); state, reason and details come from the real objects."""

    def __init__(self, entries, detail):
        self.entries, self.causes = entries, detail
        first = entries[0].result
        self.sufficiency_state, self.reason_code = first.sufficiency_state, first.reason_code
        self.value = None if first.value is None else tuple(
            Money(e.result.value, e.currency) for e in entries)


class View:
    """Delegates to a `ReplayedState`; only `position_basis` is adapted."""

    def __init__(self, state):
        self._s = state

    def __getattr__(self, name):
        return getattr(self._s, name)

    def position_basis(self, acct, listing):
        entries = self._s.position_basis(acct, listing)
        detail = ()
        for p in self._s.account(acct).positions:
            if p.listing_id == listing:
                detail = p.basis_detail
        return BasisView(entries, detail)


def S(events, day, version=None):
    events = list(events)
    if version is None:
        version = max(e.ledger_seq for e in events)
    return View(reconstruct(events, d(day), version))


def qty(state, acct, listing):
    sv = state.position_quantity(acct, listing)
    return sv.value


def bal(state, acct, ccy):
    return state.cash_balance(acct, ccy).value


def usd(x):
    return Money(Decimal(x), USD)


def hkd(x):
    return Money(Decimal(x), HKD)


class Example1Tests(unittest.TestCase):
    """§1: trade date governs both legs; settlement_date is never read."""

    def events(self, settle="2025-01-10"):
        return [
            deposit(1, A2, "2025-01-06", "20000", HKD),
            buy(2, A2, H, "2025-01-08", "500", "17500", HKD, settle=settle),
        ]

    def test_example_1a_rows(self):
        for settle in ("2025-01-10", None):  # removing settlement_date changes nothing
            evs = self.events(settle)
            for day, h, cash in (("2025-01-07", 0, "20000"), ("2025-01-08", 500, "2500"),
                                 ("2025-01-09", 500, "2500"), ("2025-01-10", 500, "2500")):
                with self.subTest(day=day, settle=settle):
                    state = S(evs, day, 2)
                    self.assertEqual(qty(state, A2, H), Decimal(h))
                    self.assertEqual(bal(state, A2, HKD), Decimal(cash))

    def test_example_1b_negative_trade_date_cash_is_a_valid_state(self):
        evs = [buy(1, A1, U, "2025-01-08", "10", "1000"), deposit(2, A1, "2025-01-09", "1000")]
        s8 = S(evs, "2025-01-08", 2)
        self.assertEqual(qty(s8, A1, U), Decimal(10))
        self.assertEqual(bal(s8, A1, USD), Decimal(-1000))
        self.assertEqual(s8.cash_balance(A1, USD).sufficiency_state, SufficiencyState.AVAILABLE)
        s9 = S(evs, "2025-01-09", 2)
        self.assertEqual(bal(s9, A1, USD), Decimal(0))


class Example2Tests(unittest.TestCase):
    """§2: reversal is retroactive in economic time, effective by ledger version."""

    def events(self):
        return [
            deposit(1, A1, "2025-01-02", "10000"),
            buy(2, A1, U, "2025-01-06", "50", "7500"),
            E(3, EventType.REVERSAL, A1, "2025-01-20", reverses=2),
            buy(4, A1, U, "2025-01-07", "40", "6000", corrects=2),
        ]

    def test_example_2a_rows(self):
        for day, version, u, usd_cash in (
            ("2025-01-10", 2, "50", "2500"),
            ("2025-01-10", 4, "40", "4000"),
            ("2025-01-06", 4, "0", "10000"),
            ("2025-01-25", 4, "40", "4000"),
        ):
            with self.subTest(day=day, version=version):
                state = S(self.events(), day, version)
                self.assertEqual(qty(state, A1, U), Decimal(u))
                self.assertEqual(bal(state, A1, USD), Decimal(usd_cash))

    def test_rejected_effective_from_reversal_date_result_never_appears(self):
        # Rejected alternative gave U = 90, USD = -3,500 at (2025-01-10, 4).
        state = S(self.events(), "2025-01-10", 4)
        self.assertNotEqual(qty(state, A1, U), Decimal(90))
        self.assertNotEqual(bal(state, A1, USD), Decimal(-3500))

    def test_reversal_event_date_is_never_read(self):
        evs = self.events()
        evs[2] = E(3, EventType.REVERSAL, A1, "2024-12-01", reverses=2)  # dated before the target
        state = S(evs, "2025-01-10", 4)
        self.assertEqual(qty(state, A1, U), Decimal(40))

    def test_events_above_the_pin_do_not_exist(self):
        state = S(self.events(), "2025-01-10", 1)
        self.assertEqual(qty(state, A1, U), Decimal(0))
        self.assertEqual(bal(state, A1, USD), Decimal(10000))
        self.assertEqual(state.ledger_version, 1)


class Example3Tests(unittest.TestCase):
    """§3: SPLIT applies at the start of its date."""

    def events(self):
        return [
            deposit(1, A1, "2025-01-02", "10000"),
            buy(2, A1, U, "2025-01-06", "50", "7500"),
            sell(3, A1, U, "2025-02-03", "100", "4500"),
            E(4, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("4", "1")),
        ]

    def test_example_3a_quantity_and_cash(self):
        state = S(self.events(), "2025-02-03", 4)
        self.assertEqual(qty(state, A1, U), Decimal(100))  # 50*4/1 - 100
        self.assertEqual(bal(state, A1, USD), Decimal(7000))  # 10000 - 7500 + 4500
        self.assertFalse(state.account(A1).has_inconsistency)  # rejected order would give -200

    def test_example_3a_remaining_basis_is_3750(self):
        # Ruling 0.4.3 case 3: one candidate lot (the rescaled lot); 7,500 x 100 / 200 = 3,750.
        basis = S(self.events(), "2025-02-03", 4).position_basis(A1, U)
        self.assertEqual(basis.value, (usd("3750"),))
        self.assertEqual(basis.sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertEqual(basis.causes, ())

    def test_split_ordering_is_independent_of_ledger_seq(self):
        evs = self.events()
        swapped = [evs[0], evs[1], E(4, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("4", "1")),
                   sell(3, A1, U, "2025-02-03", "100", "4500")]
        self.assertEqual(S(evs, "2025-02-03", 4).canonical_json(),
                         S(swapped, "2025-02-03", 4).canonical_json())

    def test_day_before_the_split_is_unsplit(self):
        self.assertEqual(qty(S(self.events(), "2025-02-02", 4), A1, U), Decimal(50))


class Example4Tests(unittest.TestCase):
    """§4: dividends are a cash credit only; no entitlement check."""

    def events(self):
        return [
            deposit(1, A2, "2025-04-01", "20000", HKD),
            buy(2, A2, H, "2025-04-01", "500", "17500", HKD),
            sell(3, A2, H, "2025-05-20", "500", "18000", HKD),
            E(4, EventType.DIVIDEND, A2, "2025-05-30", HKD, listing=H, amt="1000"),
            E(5, EventType.TAX, A2, "2025-05-30", HKD, listing=H, amt="100"),
        ]

    def test_example_4a_rows(self):
        s25 = S(self.events(), "2025-05-25", 5)
        self.assertEqual(qty(s25, A2, H), Decimal(0))
        self.assertEqual(bal(s25, A2, HKD), Decimal(20500))
        s30 = S(self.events(), "2025-05-30", 5)
        self.assertEqual(qty(s30, A2, H), Decimal(0))  # accepted although H = 0 on the pay date
        self.assertEqual(bal(s30, A2, HKD), Decimal(21400))
        self.assertFalse(s30.account(A2).has_inconsistency)

    def test_net_form_gives_the_same_balance_and_net_plus_tax_is_100_short(self):
        base = self.events()[:3]
        net = base + [E(4, EventType.DIVIDEND, A2, "2025-05-30", HKD, listing=H, amt="900")]
        self.assertEqual(bal(S(net, "2025-05-30", 4), A2, HKD), Decimal(21400))
        invalid = net + [E(5, EventType.TAX, A2, "2025-05-30", HKD, listing=H, amt="100")]
        self.assertEqual(bal(S(invalid, "2025-05-30", 5), A2, HKD), Decimal(21300))

    def test_fee_and_tax_never_change_basis(self):
        evs = [buy(1, A1, U, "2025-01-06", "10", "1500"),
               E(2, EventType.FEE, A1, "2025-01-06", listing=U, amt="5")]
        basis = S(evs, "2025-01-06", 2).position_basis(A1, U)
        self.assertEqual(basis.value, (usd("1500"),))


class Example5Tests(unittest.TestCase):
    def test_example_5a_interest_charged(self):
        evs = [
            deposit(1, A2, "2025-05-02", "5000", HKD),
            buy(2, A2, H, "2025-05-05", "200", "7000", HKD),
            deposit(3, A2, "2025-05-08", "2000", HKD),
            E(4, EventType.INTEREST_CHARGED, A2, "2025-05-31", HKD, amt="3.50"),
        ]
        for day, cash in (("2025-05-05", "-2000"), ("2025-05-08", "0"), ("2025-05-31", "-3.50")):
            with self.subTest(day=day):
                state = S(evs, day, 4)
                self.assertEqual(qty(state, A2, H), Decimal(200))
                self.assertEqual(bal(state, A2, HKD), Decimal(cash))

    def test_interest_credit_is_positive(self):
        evs = [E(1, EventType.INTEREST, A1, "2025-01-31", amt="3.50")]
        self.assertEqual(bal(S(evs, "2025-01-31", 1), A1, USD), Decimal("3.5"))


class Example5ATests(unittest.TestCase):
    """§5A: one conversion event moves two cash keys; no rate anywhere."""

    def events(self, order=(1, 2, 3, 4)):
        base = {
            1: lambda s: deposit(s, A1, "2025-04-01", "10000"),
            2: lambda s: E(s, EventType.CURRENCY_CONVERSION, A1, "2025-04-02", USD, amt="1000",
                           bought=("7780", HKD), settle="2025-04-04"),
            3: lambda s: E(s, EventType.FEE, A1, "2025-04-02", USD, amt="2"),
            4: lambda s: buy(s, A1, H, "2025-04-02", "200", "7000", HKD),
        }
        return [base[kind](seq) for seq, kind in enumerate(order, start=1)]

    def test_example_5a_a_rows(self):
        evs = self.events()
        s1 = S(evs, "2025-04-01", 4)
        self.assertEqual((bal(s1, A1, USD), bal(s1, A1, HKD), qty(s1, A1, H)),
                         (Decimal(10000), Decimal(0), Decimal(0)))
        for day in ("2025-04-02", "2025-04-04"):
            s = S(evs, day, 4)
            self.assertEqual(bal(s, A1, USD), Decimal(8998))
            self.assertEqual(bal(s, A1, HKD), Decimal(780))
            self.assertEqual(qty(s, A1, H), Decimal(200))
        self.assertEqual(S(evs, "2025-04-02", 4).position_basis(A1, H).value, (hkd("7000"),))

    def test_order_independence_within_a_day(self):
        a = S(self.events((1, 2, 3, 4)), "2025-04-02", 4)
        b = S(self.events((1, 4, 3, 2)), "2025-04-02", 4)  # BUY folded before the conversion
        self.assertEqual(a.canonical_json(), b.canonical_json())

    def test_conversion_is_not_a_position_and_stores_no_rate(self):
        state = S(self.events(), "2025-04-02", 4)
        self.assertEqual(len(state.account(A1).positions), 1)
        self.assertNotIn("rate", state.canonical_json().lower())

    def test_example_5a_b_correction_removes_both_legs(self):
        evs = self.events() + [
            E(5, EventType.REVERSAL, A1, "2025-04-10", USD, reverses=2),
            E(6, EventType.CURRENCY_CONVERSION, A1, "2025-04-02", USD, amt="1000",
              bought=("7750", HKD), corrects=2),
        ]
        s4 = S(evs, "2025-04-02", 4)
        self.assertEqual((bal(s4, A1, USD), bal(s4, A1, HKD)), (Decimal(8998), Decimal(780)))
        s6 = S(evs, "2025-04-02", 6)
        self.assertEqual((bal(s6, A1, USD), bal(s6, A1, HKD)), (Decimal(8998), Decimal(750)))
        # The forbidden intermediate (reversal visible without its replacement): both legs vanish.
        s5 = S(evs, "2025-04-02", 5)
        self.assertEqual((bal(s5, A1, USD), bal(s5, A1, HKD)), (Decimal(9998), Decimal(-7000)))

    def test_example_5a_c_commission_recordings(self):
        def usd_after(conv_amt, fee):
            evs = [deposit(1, A1, "2025-04-01", "10000"),
                   E(2, EventType.CURRENCY_CONVERSION, A1, "2025-04-02", USD, amt=conv_amt,
                     bought=("7780", HKD))]
            if fee:
                evs.append(E(3, EventType.FEE, A1, "2025-04-02", USD, amt=fee))
            return bal(S(evs, "2025-04-02"), A1, USD)

        self.assertEqual(usd_after("1002", None), Decimal(8998))
        self.assertEqual(usd_after("1000", "2"), Decimal(8998))
        self.assertEqual(usd_after("1002", "2"), Decimal(8996))  # the invalid double count


class TransferTests(unittest.TestCase):
    def test_example_6a_internal_cash_transfer_is_neutral(self):
        evs = [
            deposit(1, A1, "2025-02-01", "2500"),
            E(2, EventType.TRANSFER_OUT, A1, "2025-02-10", amt="1000", cp=A3),
            E(3, EventType.TRANSFER_IN, A3, "2025-02-10", amt="1000", cp=A1),
        ]
        before = S(evs, "2025-02-09", 3)
        self.assertEqual(bal(before, A1, USD), Decimal(2500))
        self.assertEqual(bal(before, A3, USD), Decimal(0))
        after = S(evs, "2025-02-10", 3)
        self.assertEqual(bal(after, A1, USD), Decimal(1500))
        self.assertEqual(bal(after, A3, USD), Decimal(1000))
        self.assertEqual(after.portfolio_cash(USD).value, Decimal(2500))
        self.assertEqual(before.portfolio_cash(USD).value, Decimal(2500))

    def test_external_cash_transfer_moves_the_balance(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-02-10", amt="700"),
               E(2, EventType.TRANSFER_OUT, A1, "2025-02-11", amt="200")]
        self.assertEqual(bal(S(evs, "2025-02-11", 2), A1, USD), Decimal(500))

    def test_example_6b_external_in_kind_without_basis(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-03-10", listing=M, q="10")]
        state = S(evs, "2025-03-10", 1)
        self.assertEqual(qty(state, A1, M), Decimal(10))
        basis = state.position_basis(A1, M)
        self.assertIsNone(basis.value)  # unknown, not zero
        self.assertEqual(basis.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertEqual(basis.reason_code, ReasonCode.MISSING_COST_BASIS)
        self.assertEqual(basis.causes, (ReplayDetail.UNKNOWN_BASIS,))

    def test_external_in_kind_with_basis_and_a_known_zero_basis(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-03-10", listing=M, q="10", basis="0")]
        basis = S(evs, "2025-03-10", 1).position_basis(A1, M)
        self.assertEqual(basis.value, (usd("0"),))  # a stated zero is known; absence is not

    def test_example_6c_partial_internal_security_transfer(self):
        evs = [
            buy(1, A1, U, "2025-03-01", "150", "5625"),
            E(2, EventType.TRANSFER_OUT, A1, "2025-03-15", listing=U, q="50", cp=A3),
            E(3, EventType.TRANSFER_IN, A3, "2025-03-15", listing=U, q="50", cp=A1),
        ]
        state = S(evs, "2025-03-15", 3)
        self.assertEqual(qty(state, A1, U), Decimal(100))
        self.assertEqual(qty(state, A3, U), Decimal(50))
        self.assertEqual(state.portfolio_position_quantity(U).value, Decimal(150))
        # Example 6-C / Ruling 0.4.5 (b): 5,625 x 100/150 = 3,750 and 5,625 x 50/150 = 1,875.
        self.assertEqual(state.position_basis(A1, U).value, (usd("3750"),))
        self.assertEqual(state.position_basis(A3, U).value, (usd("1875"),))
        self.assertEqual(state.position_basis(A3, U).sufficiency_state, SufficiencyState.AVAILABLE)
        before = S(evs, "2025-03-14", 3)
        self.assertEqual(before.position_basis(A1, U).value, (usd("5625"),))

    def test_whole_position_transfer_out_leaves_no_source_position(self):
        evs = [
            buy(1, A1, U, "2025-03-01", "150", "5625"),
            E(2, EventType.TRANSFER_OUT, A1, "2025-03-15", listing=U, q="150", cp=A3),
            E(3, EventType.TRANSFER_IN, A3, "2025-03-15", listing=U, q="150", cp=A1),
        ]
        state = S(evs, "2025-03-15", 3)
        self.assertEqual(state.account(A1).positions, ())
        self.assertEqual(qty(state, A3, U), Decimal(150))

    def test_example_6d_mixed_basis_is_unknown_never_the_known_part(self):
        evs = [
            buy(1, A1, U, "2025-03-01", "150", "5625"),
            E(2, EventType.TRANSFER_IN, A1, "2025-03-12", listing=U, q="20"),
        ]
        state = S(evs, "2025-03-12", 2)
        self.assertEqual(qty(state, A1, U), Decimal(170))
        basis = state.position_basis(A1, U)
        self.assertIsNone(basis.value)  # 5,625 is not presented as the basis of 170 units
        self.assertEqual(basis.reason_code, ReasonCode.MISSING_COST_BASIS)
        self.assertEqual(S(evs, "2025-03-11", 2).position_basis(A1, U).value, (usd("5625"),))


class SplitTests(unittest.TestCase):
    """§7 and Example 7-A."""

    def run_split(self, q, ratio, extra=()):
        evs = [buy(1, A1, U, "2025-01-06", q, "7500"),
               E(2, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=ratio)] + list(extra)
        return S(evs, "2025-02-03", max(e.ledger_seq for e in evs))

    def test_example_7a_integral_results(self):
        s = self.run_split("50", ("4", "1"))
        self.assertEqual(qty(s, A1, U), Decimal(200))
        self.assertEqual(s.position_basis(A1, U).value, (usd("7500"),))  # total basis unchanged
        s = self.run_split("10.5", ("2", "1"))
        self.assertEqual(qty(s, A1, U), Decimal(21))

    def test_example_7a_unresolved_results(self):
        for q, ratio in (("101", ("3", "2")), ("100", ("1", "3"))):
            with self.subTest(q=q, ratio=ratio):
                s = self.run_split(q, ratio)
                quantity = s.position_quantity(A1, U)
                self.assertIsNone(quantity.value)  # no rounded, truncated or retained-fraction number
                self.assertEqual(quantity.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
                self.assertEqual(quantity.reason_code, ReasonCode.UNRESOLVED_CONVENTION)
                # which convention is unresolved is kept in the separate detail field
                self.assertEqual(s.account(A1).positions[0].quantity_detail,
                                 (ReplayDetail.SPLIT_FRACTION,))
                self.assertIsNone(s.position_basis(A1, U).value)
                self.assertFalse(s.account(A1).has_inconsistency)  # distinguishable from §9
                self.assertEqual(len(s.account(A1).positions), 1)  # not omitted like a zero

    def test_unresolved_is_from_the_split_date_on_and_sticky(self):
        evs = [buy(1, A1, U, "2025-01-06", "101", "7500"),
               E(2, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("3", "2")),
               sell(3, A1, U, "2025-03-03", "10", "500")]
        self.assertEqual(qty(S(evs, "2025-02-02", 3), A1, U), Decimal(101))
        for day in ("2025-02-03", "2025-03-03", "2025-06-01"):
            self.assertIsNone(S(evs, day, 3).position_quantity(A1, U).value)

    def test_split_on_a_listing_not_held_is_a_no_op(self):
        evs = [E(1, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("3", "2"))]
        self.assertEqual(S(evs, "2025-02-03", 1).account(A1).positions, ())

    def test_reverse_split_that_is_integral(self):
        evs = [buy(1, A1, U, "2025-01-06", "100", "7500"),
               E(2, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("1", "10"))]
        self.assertEqual(qty(S(evs, "2025-02-03", 2), A1, U), Decimal(10))


class DepletionBoundaryTests(unittest.TestCase):
    def test_partial_sell_of_a_single_lot_keeps_its_unit_cost(self):
        # c = 7,500 / 50 = 150; 40 units remain: 150 x 40 = 6,000.
        evs = [buy(1, A1, U, "2025-01-06", "50", "7500"), sell(2, A1, U, "2025-03-03", "10", "450")]
        state = S(evs, "2025-03-03", 2)
        self.assertEqual(qty(state, A1, U), Decimal(40))
        self.assertEqual(state.position_basis(A1, U).value, (usd("6000"),))

    def test_full_sell_leaves_nothing_and_a_new_buy_starts_clean(self):
        evs = [buy(1, A1, U, "2025-01-06", "50", "7500"), sell(2, A1, U, "2025-03-03", "50", "2250"),
               buy(3, A1, U, "2025-04-01", "5", "300")]
        self.assertEqual(S(evs, "2025-03-03", 3).account(A1).positions, ())
        state = S(evs, "2025-04-01", 3)
        self.assertEqual(state.position_basis(A1, U).value, (usd("300"),))

    def test_basis_in_two_currencies_is_kept_separately_never_summed(self):
        evs = [buy(1, A1, H, "2025-01-06", "100", "3500", HKD),
               buy(2, A1, H, "2025-01-07", "100", "3000", CNY)]
        basis = S(evs, "2025-01-07", 2).position_basis(A1, H).value
        self.assertEqual(basis, (Money(Decimal(3000), CNY), Money(Decimal(3500), HKD)))


class SnapshotTests(unittest.TestCase):
    """§8 and Example 8-A."""

    def events(self):
        return [
            E(1, EventType.OPENING_POSITION, A2, "2025-06-30", HKD, listing=H, q="500"),
            E(2, EventType.OPENING_CASH, A2, "2025-06-30", HKD, amt="3000"),
        ]

    def test_before_the_snapshot_is_not_reconstructable_which_is_not_empty(self):
        state = S(self.events(), "2025-06-29", 2)
        account = state.account(A2)
        self.assertEqual(account.status, AccountStatus.NOT_RECONSTRUCTABLE)
        self.assertEqual(account.snapshot_date, d("2025-06-30"))
        for sv in (state.position_quantity(A2, H), state.cash_balance(A2, HKD)):
            self.assertIsNone(sv.value)
            self.assertEqual(sv.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
            self.assertEqual(sv.reason_code, ReasonCode.NOT_RECONSTRUCTABLE)
        self.assertIsNone(state.portfolio_cash(HKD).value)

    def test_on_the_snapshot_date(self):
        state = S(self.events(), "2025-06-30", 2)
        self.assertEqual(state.account(A2).status, AccountStatus.RECONSTRUCTED)
        self.assertEqual(qty(state, A2, H), Decimal(500))
        self.assertEqual(bal(state, A2, HKD), Decimal(3000))
        basis = state.position_basis(A2, H)
        self.assertIsNone(basis.value)  # opening position without basis: unknown
        self.assertEqual(basis.reason_code, ReasonCode.MISSING_COST_BASIS)

    def test_opening_position_with_basis(self):
        evs = [E(1, EventType.OPENING_POSITION, A2, "2025-06-30", HKD, listing=H, q="500", basis="17500")]
        self.assertEqual(S(evs, "2025-06-30", 1).position_basis(A2, H).value, (hkd("17500"),))

    def test_account_without_snapshot_is_empty_before_its_first_event(self):
        evs = [deposit(1, A1, "2025-06-30", "10")]
        state = S(evs, "2025-01-01", 1)
        self.assertEqual(state.account(A1).status, AccountStatus.RECONSTRUCTED)
        self.assertEqual(state.account(A1).cash, ())

    def test_trade_inside_the_snapshot_is_refused(self):
        evs = self.events() + [buy(3, A2, H, "2025-06-30", "1", "35", HKD)]
        with self.assertRaises(ReplayInputError):
            S(evs, "2025-07-01", 3)

    def test_trade_after_the_snapshot_and_split_on_the_snapshot_date(self):
        evs = self.events() + [
            E(3, EventType.SPLIT, A2, "2025-06-30", listing=H, ratio=("2", "1")),
            buy(4, A2, H, "2025-07-01", "10", "350", HKD),
        ]
        state = S(evs, "2025-07-01", 4)
        self.assertEqual(qty(state, A2, H), Decimal(510))  # split applied to zero, then 500 opened

    def test_two_snapshot_dates_refused(self):
        evs = [E(1, EventType.OPENING_CASH, A2, "2025-06-30", HKD, amt="1"),
               E(2, EventType.OPENING_CASH, A2, "2025-07-01", HKD, amt="1")]
        with self.assertRaises(ReplayInputError):
            S(evs, "2025-07-01", 2)

    def test_reversed_opening_events_do_not_define_a_snapshot(self):
        evs = self.events() + [E(3, EventType.REVERSAL, A2, "2025-07-05", HKD, reverses=1),
                               E(4, EventType.REVERSAL, A2, "2025-07-05", HKD, reverses=2)]
        state = S(evs, "2025-06-29", 4)
        self.assertEqual(state.accounts, ())  # no live event at all
        with self.assertRaises(UnknownAccountError):
            state.account(A2)


class NegativeQuantityTests(unittest.TestCase):
    """§9 and Example 9-A."""

    def events(self, extra=()):
        return [buy(1, A1, U, "2025-03-01", "10", "1500"),
                sell(2, A1, U, "2025-04-01", "15", "2100")] + list(extra)

    def test_example_9a(self):
        state = S(self.events(), "2025-04-01", 2)
        quantity = state.position_quantity(A1, U)
        self.assertIsNone(quantity.value)  # not -5, not 0
        self.assertEqual(quantity.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        self.assertTrue(state.account(A1).has_inconsistency)
        self.assertEqual(bal(state, A1, USD), Decimal(-1500 + 2100))  # cash effect stays
        self.assertEqual(S(self.events(), "2025-03-31", 2).position_quantity(A1, U).value, Decimal(10))

    def test_flag_is_sticky_and_never_clamped(self):
        evs = self.events([buy(3, A1, U, "2025-05-01", "100", "9000")])
        self.assertIsNone(S(evs, "2025-05-01", 3).position_quantity(A1, U).value)

    def test_only_end_of_day_is_validated(self):
        evs = [buy(1, A1, U, "2025-03-01", "10", "1500"),
               sell(2, A1, U, "2025-04-01", "15", "2100"),
               buy(3, A1, U, "2025-04-01", "5", "700")]  # same day: end of day is 0
        state = S(evs, "2025-04-01", 3)
        self.assertFalse(state.account(A1).has_inconsistency)
        self.assertEqual(state.account(A1).positions, ())

    def test_unrelated_position_is_unaffected(self):
        evs = self.events([buy(3, A1, M, "2025-04-02", "3", "300")])
        state = S(evs, "2025-04-02", 3)
        self.assertEqual(qty(state, A1, M), Decimal(3))


class B0bFixtureConsistencyTests(unittest.TestCase):
    """§10: the Quant's re-derivation of B0b T1-T8 for events E1-E8."""

    def events(self):
        return [
            deposit(1, A1, "2025-01-02", "10000"),
            buy(2, A1, U, "2025-01-06", "50", "7500"),
            deposit(3, A2, "2025-01-06", "20000", HKD),
            buy(4, A2, H, "2025-01-08", "500", "17500", HKD),
            E(5, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("4", "1")),
            E(6, EventType.TRANSFER_OUT, A1, "2025-02-10", amt="1000", cp=A3),
            E(7, EventType.TRANSFER_IN, A3, "2025-02-10", amt="1000", cp=A1),
            sell(8, A1, U, "2025-03-03", "50", "2250"),
            E(9, EventType.TRANSFER_IN, A1, "2025-03-10", listing=M, q="10"),
        ]

    def test_t1_to_t8(self):
        evs = self.events()
        s = S(evs, "2025-01-05")
        self.assertEqual((qty(s, A1, U), bal(s, A1, USD)), (Decimal(0), Decimal(10000)))  # T1
        s = S(evs, "2025-01-07")
        self.assertEqual((qty(s, A1, U), bal(s, A1, USD)), (Decimal(50), Decimal(2500)))  # T2
        s = S(evs, "2025-01-09")
        self.assertEqual((qty(s, A2, H), bal(s, A2, HKD)), (Decimal(500), Decimal(2500)))  # T3
        s = S(evs, "2025-02-02")
        self.assertEqual(qty(s, A1, U), Decimal(50))  # T4
        self.assertEqual(s.position_basis(A1, U).value, (usd("7500"),))
        s = S(evs, "2025-02-03")
        self.assertEqual(qty(s, A1, U), Decimal(200))  # T5: split is inclusive on its date
        self.assertEqual(s.position_basis(A1, U).value, (usd("7500"),))
        before, after = S(evs, "2025-02-09"), S(evs, "2025-02-11")
        self.assertEqual(before.portfolio_cash(USD).value, Decimal(2500))  # T6
        self.assertEqual(after.portfolio_cash(USD).value, Decimal(2500))
        self.assertEqual((bal(after, A1, USD), bal(after, A3, USD)), (Decimal(1500), Decimal(1000)))
        s = S(evs, "2025-03-04")
        self.assertEqual(qty(s, A1, U), Decimal(150))  # T7
        self.assertEqual(bal(s, A1, USD), Decimal(3750))
        # T7 (§10, Example 0.4-A): remaining basis 5,625 USD, AVAILABLE; not the unresolved state.
        self.assertEqual(s.position_basis(A1, U).value, (usd("5625"),))
        self.assertEqual(s.position_basis(A1, U).sufficiency_state, SufficiencyState.AVAILABLE)
        s = S(evs, "2025-03-11")
        self.assertEqual(qty(s, A1, M), Decimal(10))  # T8
        self.assertIsNone(s.position_basis(A1, M).value)  # cost_basis is not 0 and not invented

    def test_t9_currencies_are_never_summed(self):
        state = S(self.events(), "2025-03-11")
        self.assertEqual(state.portfolio_cash_currencies(), (HKD, USD))
        self.assertEqual(state.portfolio_cash(HKD).value, Decimal(2500))
        self.assertEqual(state.portfolio_cash(USD).value, Decimal(3750 + 1000))  # A1 + A3
        self.assertFalse(hasattr(state, "reporting_currency"))
        # One currency per call; no method sums across currencies.
        self.assertFalse(hasattr(state, "portfolio_cash_total"))

    def test_t10_two_runs_and_any_input_order_are_byte_identical(self):
        evs = self.events()
        first = S(evs, "2025-03-11").canonical_json()
        self.assertEqual(first, S(list(evs), "2025-03-11").canonical_json())
        self.assertEqual(first, S(list(reversed(evs)), "2025-03-11").canonical_json())
        self.assertEqual(first.encode("utf-8"), S(evs, "2025-03-11").canonical_json().encode("utf-8"))
        self.assertTrue(first.isascii())


class OutputShapeTests(unittest.TestCase):
    def test_zero_position_and_zero_cash_are_not_emitted_but_read_as_zero(self):
        evs = [deposit(1, A1, "2025-01-02", "100"), E(2, EventType.WITHDRAWAL, A1, "2025-01-03", amt="100"),
               buy(3, A1, U, "2025-01-04", "1", "0.5"), sell(4, A1, U, "2025-01-05", "1", "0.5")]
        state = S(evs, "2025-01-05", 4)
        account = state.account(A1)
        self.assertEqual((account.positions, account.cash), ((), ()))
        self.assertEqual(state.cash_balance(A1, USD).value, Decimal(0))
        self.assertEqual(state.cash_balance(A1, USD).sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertEqual(qty(state, A1, U), Decimal(0))

    def test_accounts_positions_and_cash_are_sorted(self):
        evs = [deposit(1, A3, "2025-01-02", "1"), deposit(2, A1, "2025-01-02", "1"),
               deposit(3, A1, "2025-01-02", "1", HKD), deposit(4, A1, "2025-01-02", "1", CNY),
               buy(5, A1, M, "2025-01-02", "1", "1"), buy(6, A1, U, "2025-01-02", "1", "1")]
        state = S(evs, "2025-01-02", 6)
        self.assertEqual([a.account_id for a in state.accounts], [A1, A3])
        self.assertEqual([p.listing_id for p in state.account(A1).positions], [U, M])
        self.assertEqual([c.balance.currency.code for c in state.account(A1).cash], ["CNY", "HKD", "USD"])

    def test_account_with_only_later_events_is_present_and_empty(self):
        state = S([deposit(1, A1, "2025-06-01", "5")], "2025-01-01", 1)
        self.assertEqual(state.account(A1).cash, ())
        self.assertEqual(state.cash_balance(A1, USD).value, Decimal(0))

    def test_unknown_account_is_an_error_not_an_empty_state(self):
        state = S([deposit(1, A1, "2025-06-01", "5")], "2025-06-01", 1)
        with self.assertRaises(UnknownAccountError):
            state.account(A2)

    def test_empty_ledger(self):
        state = reconstruct([], d("2025-01-01"), 0)
        self.assertEqual(state.accounts, ())
        self.assertEqual(state.convention_set, CONVENTION_SET_ID)
        self.assertEqual(CONVENTION_SET_ID, "ledger-replay/1.3")

    def test_portfolio_position_sum_carries_the_flag(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "1"), buy(2, A3, U, "2025-01-02", "5", "1"),
               sell(3, A3, U, "2025-01-03", "9", "1")]
        state = S(evs, "2025-01-03", 3)
        total = state.portfolio_position_quantity(U)
        self.assertIsNone(total.value)
        self.assertEqual(total.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        self.assertEqual(S(evs, "2025-01-02", 3).portfolio_position_quantity(U).value, Decimal(15))
        self.assertEqual(S(evs, "2025-01-02", 3).portfolio_position_quantity(M).value, Decimal(0))


class ExactnessTests(unittest.TestCase):
    def test_result_does_not_depend_on_the_global_decimal_context(self):
        big = "123456789012345678901234567890.123456789012345678901234567890"
        evs = [big_deposit(1, A1, "2025-01-02", big),
               E(2, EventType.WITHDRAWAL, A1, "2025-01-03", amt="0.000000000000000000000000001")]
        # 27th decimal place: 7 - 1 = 6 (digit-wise, no carry).
        expected = Decimal("123456789012345678901234567890.123456789012345678901234566890")
        with decimal.localcontext() as ctx:
            ctx.prec = 3
            self.assertEqual(bal(S(evs, "2025-01-03", 2), A1, USD), expected)
        self.assertEqual(bal(S(evs, "2025-01-03", 2), A1, USD), expected)

    def test_scale_of_inputs_does_not_change_the_serialised_state(self):
        a = [deposit(1, A1, "2025-01-02", "2500.00")]
        b = [deposit(1, A1, "2025-01-02", "2.5E+3")]
        self.assertEqual(S(a, "2025-01-02", 1).canonical_json(), S(b, "2025-01-02", 1).canonical_json())
        self.assertIn('"amount":"2500"', S(a, "2025-01-02", 1).canonical_json())

    def test_c1c6_unwritable_balance_is_a_narrow_state_not_an_exception(self):
        # 1E+150 plus 1E-60 needs 211 digits: not writable in the exact 200-digit context.
        # Reason code CALCULATION_ERROR (detail VALUE_NOT_REPRESENTABLE); no ReasonCode added.
        evs = [big_deposit(1, A1, "2025-01-02", "1E+150"),
               big_deposit(2, A1, "2025-01-03", "1E-60"),
               deposit(3, A1, "2025-01-03", "5", HKD),  # same account, other currency
               deposit(4, A3, "2025-01-03", "7"),  # another account, same currency
               buy(5, A1, U, "2025-01-03", "10", "1", HKD)]
        before = S(evs, "2025-01-02")
        self.assertEqual(bal(before, A1, USD), Decimal("1E+150"))  # earlier dates still work
        state = S(evs, "2025-06-30")
        bad = state.cash_balance(A1, USD)
        self.assertIsNone(bad.value)
        self.assertEqual(bad.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertEqual(bad.reason_code, ReasonCode.CALCULATION_ERROR)
        self.assertEqual(state.account(A1).unrepresentable_cash, (USD,))
        self.assertEqual(bal(state, A1, HKD), Decimal(4))  # other currency: unaffected
        self.assertEqual(bal(state, A3, USD), Decimal(7))  # other account: unaffected
        self.assertEqual(qty(state, A1, U), Decimal(10))  # positions unaffected
        portfolio = state.portfolio_cash(USD)  # a sum over an unwritable balance is a state too
        self.assertEqual(portfolio.reason_code, ReasonCode.CALCULATION_ERROR)
        self.assertEqual(state.portfolio_cash(HKD).value, Decimal(4))
        self.assertIn('"unrepresentable_cash":["USD"]', state.canonical_json())  # serialises

    def test_r3_1_extreme_magnitudes_are_states_never_exceptions(self):
        # Above CPython's 4,300-digit int-to-string limit; storable NUMERIC values.
        for magnitude in ("1E+5000", "1E+131071", "1E-16383"):
            with self.subTest(magnitude=magnitude):
                evs = [big_deposit(1, A1, "2025-01-02", magnitude),
                       deposit(2, A1, "2025-01-02", "5", HKD),
                       deposit(3, A3, "2025-01-02", "7"),
                       unbounded(buy(4, A1, U, "2025-01-02", "1", "1"), quantity=magnitude),
                       buy(5, A1, M, "2025-01-02", "10", "100"),
                       unbounded(buy(6, A3, H, "2025-01-02", "1", "1", HKD), amount=magnitude)]
                state = S(evs, "2025-01-02")  # no exception for the portfolio
                bad = state.cash_balance(A1, USD)
                self.assertIsNone(bad.value)
                self.assertEqual(bad.reason_code, ReasonCode.CALCULATION_ERROR)
                self.assertEqual(bal(state, A1, HKD), Decimal(5))  # untouched key
                self.assertEqual(bal(state, A3, USD), Decimal(7))  # other account
                self.assertIsNone(qty(state, A1, U))  # the extreme position only
                self.assertEqual(state.account(A1).positions[0].quantity.reason_code, ReasonCode.CALCULATION_ERROR)
                self.assertEqual(qty(state, A1, M), Decimal(10))  # unaffected position
                self.assertEqual(state.position_basis(A1, M).value, (usd("100"),))
                self.assertIsNone(state.position_basis(A3, H).value)  # extreme basis: that basis only
                self.assertEqual(qty(state, A3, H), Decimal(1))
                self.assertIn("VALUE_NOT_REPRESENTABLE", state.canonical_json())

    def test_r3_1_to_decimal_never_raises_on_huge_terminating_values(self):
        from fractions import Fraction
        from domain.replay import _to_decimal
        value, why = _to_decimal(Fraction(10 ** 5000))  # no int -> str conversion
        self.assertIsNone(why)
        self.assertEqual(value, Decimal("1E+5000"))
        none, why = _to_decimal(Fraction(10 ** 5000 + 1))  # 5,001 significant digits
        self.assertIsNone(none)
        self.assertEqual(why, ReplayDetail.VALUE_NOT_REPRESENTABLE)

    def test_r3_1_thousands_of_extreme_deposits_are_cheap(self):
        import time
        evs = [big_deposit(i + 1, A1, "2025-01-02", "1E+131071" if i % 2 == 0 else "1E-16383")
               for i in range(2000)]
        start = time.monotonic()
        state = S(evs, "2025-01-02")
        self.assertLess(time.monotonic() - start, 5.0)  # fail-closed pre-check, no big-int math
        self.assertIsNone(state.cash_balance(A1, USD).value)

    def test_c1c6_a_too_large_sum_is_never_rounded(self):
        evs = [big_deposit(1, A1, "2025-01-02", "1" + "0" * 250), deposit(2, A1, "2025-01-02", "1")]
        result = S(evs, "2025-01-02", 2).cash_balance(A1, USD)
        self.assertIsNone(result.value)  # no rounded 1E+250
        self.assertEqual(result.reason_code, ReasonCode.CALCULATION_ERROR)

    def test_c1c6_two_representable_balances_whose_sum_is_not(self):
        big = "1" + "0" * 150
        evs = [big_deposit(1, A1, "2025-01-02", big),
               big_deposit(2, A3, "2025-01-02", "0." + "0" * 59 + "1")]
        state = S(evs, "2025-01-02", 2)
        self.assertIsNotNone(state.cash_balance(A1, USD).value)
        self.assertIsNotNone(state.cash_balance(A3, USD).value)
        self.assertIsNone(state.portfolio_cash(USD).value)  # exact sum has 211 digits

    def test_c1c6_a_too_large_terminating_basis_is_not_labelled_non_terminating(self):
        evs = [unbounded(buy(1, A1, U, "2025-01-02", "1", "1"), amount="1" + "0" * 150 + "." + "0" * 59 + "1")]
        basis = S(evs, "2025-01-02").position_basis(A1, U)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.causes, (ReplayDetail.VALUE_NOT_REPRESENTABLE,))
        self.assertEqual(basis.reason_code, ReasonCode.CALCULATION_ERROR)


class InputValidationTests(unittest.TestCase):
    def test_bad_arguments(self):
        evs = [deposit(1, A1, "2025-01-02", "1")]
        with self.assertRaises(ReplayInputError):
            reconstruct(evs, datetime.datetime(2025, 1, 2), 1)
        with self.assertRaises(ReplayInputError):
            reconstruct(evs, "2025-01-02", 1)
        for bad in (True, -1, 1.0, "1"):
            with self.subTest(version=bad), self.assertRaises(ReplayInputError):
                reconstruct(evs, d("2025-01-02"), bad)
        with self.assertRaises(ReplayInputError):
            reconstruct([evs[0].event], d("2025-01-02"), 1)

    def test_duplicates_refused(self):
        with self.assertRaises(ReplayInputError):
            reconstruct([deposit(1, A1, "2025-01-02", "1"), deposit(1, A1, "2025-01-03", "1")], d("2025-02-01"), 1)
        dup = SequencedEvent(2, deposit(1, A1, "2025-01-02", "1").event)  # same event_id, other seq
        with self.assertRaises(ReplayInputError):
            reconstruct([deposit(1, A1, "2025-01-02", "1"), dup], d("2025-02-01"), 2)

    def test_sequenced_event_rules(self):
        event = deposit(1, A1, "2025-01-02", "1").event
        for bad in (0, -3, True, 1.5):
            with self.subTest(seq=bad), self.assertRaises(ReplayInputError):
                SequencedEvent(bad, event)
        with self.assertRaises(ReplayInputError):
            SequencedEvent(1, "not an event")


class MetricEnvelopeTests(unittest.TestCase):
    """PD-0025: replay output is `MetricResult` itself; details sit beside it."""

    def test_replay_values_are_metric_results_with_decimal_values(self):
        state = S(NegativeQuantityTests().events(), "2025-03-01", 2)
        result = state.position_quantity(A1, U)
        self.assertIsInstance(result, MetricResult)
        self.assertIsInstance(result.value, Decimal)
        self.assertIsInstance(state.cash_balance(A1, USD), MetricResult)
        self.assertIsInstance(state.cash_balance(A1, USD).value, Decimal)

    def test_insufficient_results_carry_a_reason_code_never_a_value(self):
        state = S(NegativeQuantityTests().events(), "2025-04-01", 2)
        position = state.account(A1).positions[0]
        self.assertEqual(position.quantity.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertIsNone(position.quantity.value)
        self.assertEqual(position.quantity.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        self.assertEqual(position.quantity_detail, (ReplayDetail.NEGATIVE_QUANTITY,))
        self.assertEqual(position.cost_basis[0].result.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        self.assertIsNone(position.cost_basis[0].currency)

    def test_detail_keeps_which_convention_and_priority_picks_the_reason(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-01-02", listing=U, q="10"),  # unknown lot
               buy(2, A1, U, "2025-01-02", "5", "100"),  # plus a known lot (0.4.4 (b))
               sell(3, A1, U, "2025-01-03", "4", "1")]  # then a depletion
        position = S(evs, "2025-01-03", 3).account(A1).positions[0]
        self.assertEqual(position.basis_detail, (ReplayDetail.LOT_DEPLETION, ReplayDetail.UNKNOWN_BASIS))
        self.assertEqual(position.cost_basis[0].result.reason_code, ReasonCode.UNRESOLVED_CONVENTION)

    def test_only_existing_states_are_used(self):
        self.assertEqual({s.name for s in SufficiencyState}, {"AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"})
        state = S(NegativeQuantityTests().events(), "2025-04-01", 2)
        for position in state.account(A1).positions:
            self.assertIn(position.quantity.sufficiency_state, tuple(SufficiencyState))

    def test_no_replay_specific_state_type_remains(self):
        import domain.replay as replay_module
        self.assertFalse(hasattr(replay_module, "StatedValue"))
        self.assertFalse(hasattr(replay_module, "ReplayCause"))


def xfer(seq, acct, other, kind, day, q, listing=U):
    return E(seq, kind, acct, day, listing=listing, q=q, cp=other)


def move(seq, src, dst, day, q, listing=U):
    """Both legs of an internal security transfer (out first)."""
    return [xfer(seq, src, dst, EventType.TRANSFER_OUT, day, q, listing),
            xfer(seq + 1, dst, src, EventType.TRANSFER_IN, day, q, listing)]


class Ruling04Tests(unittest.TestCase):
    """Ruling 0.4 (ledger-replay/1.3): expected values are the document's examples."""

    def assertBasis(self, state, acct, listing, money):
        basis = state.position_basis(acct, listing)
        self.assertEqual(basis.value, money)
        self.assertEqual(basis.sufficiency_state, SufficiencyState.AVAILABLE)

    def assertUnresolved(self, state, acct, listing, *details):
        basis = state.position_basis(acct, listing)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertEqual(basis.reason_code, ReasonCode.UNRESOLVED_CONVENTION)
        self.assertEqual(basis.causes, tuple(details))

    def test_example_0_4_a_split_then_sale_is_5625(self):
        evs = [buy(1, A1, U, "2025-01-06", "50", "7500"),
               E(2, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("4", "1")),
               sell(3, A1, U, "2025-03-03", "50", "2250")]
        s5 = S(evs, "2025-02-03")  # T5: quantity 200, total basis 7,500, both AVAILABLE
        self.assertEqual(qty(s5, A1, U), Decimal(200))
        self.assertBasis(s5, A1, U, (usd("7500"),))
        self.assertEqual(s5.position_quantity(A1, U).sufficiency_state, SufficiencyState.AVAILABLE)
        s7 = S(evs, "2025-03-03")  # T7 path
        self.assertEqual(qty(s7, A1, U), Decimal(150))
        self.assertBasis(s7, A1, U, (usd("5625"),))

    def test_example_0_4_b_non_terminating_then_terminating_again(self):
        evs = [buy(1, A1, U, "2025-01-02", "6", "100"), sell(2, A1, U, "2025-01-03", "2", "40"),
               sell(3, A1, U, "2025-01-04", "1", "20")]
        day1 = S(evs, "2025-01-03")  # 4 x 50/3 = 200/3 = 66.666...: not exactly representable
        self.assertEqual(qty(day1, A1, U), Decimal(4))
        self.assertEqual(day1.position_quantity(A1, U).sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertUnresolved(day1, A1, U, ReplayDetail.BASIS_NOT_EXACT)
        entry = day1.account(A1).positions[0].cost_basis[0]
        self.assertIsNone(entry.currency)  # C1C-4: one no-value entry, no partial currency entry
        day2 = S(evs, "2025-01-04")  # 3 x 50/3 = 50, not 66.67 x 3/4 = 50.0025
        self.assertEqual(qty(day2, A1, U), Decimal(3))
        self.assertBasis(day2, A1, U, (usd("50"),))
        self.assertNotIn("50.0025", day2.canonical_json())

    def test_non_terminating_basis_never_raises_and_reason_is_unresolved_convention(self):
        evs = [buy(1, A1, U, "2025-01-02", "3", "100"), sell(2, A1, U, "2025-01-03", "1", "40")]
        state = S(evs, "2025-01-03")  # 2 x 100/3 = 200/3
        result = state.account(A1).positions[0].cost_basis[0].result
        self.assertIsNone(result.value)
        self.assertEqual(result.reason_code, ReasonCode.UNRESOLVED_CONVENTION)

    def test_example_0_4_c_two_lots_unresolved_after_a_sale(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"), buy(2, A1, U, "2025-01-03", "100", "1200"),
               sell(3, A1, U, "2025-01-04", "50", "700")]
        before = S(evs, "2025-01-03")
        self.assertBasis(before, A1, U, (usd("2200"),))  # case 1: total known before any sale
        after = S(evs, "2025-01-04")
        self.assertEqual(qty(after, A1, U), Decimal(150))
        self.assertUnresolved(after, A1, U, ReplayDetail.LOT_DEPLETION)  # 1,700 / 1,650 / 1,600

    def test_example_0_4_d_same_day_acquisition_and_depletion(self):
        def evs(order):
            base = [buy(1, A1, U, "2025-01-02", "100", "1000")]
            same_day = {"sell": lambda s: sell(s, A1, U, "2025-01-10", "100", "1300"),
                        "buy": lambda s: buy(s, A1, U, "2025-01-10", "50", "600")}
            return base + [same_day[k](2 + i) for i, k in enumerate(order)]
        sell_first, buy_first = S(evs(("sell", "buy")), "2025-01-10"), S(evs(("buy", "sell")), "2025-01-10")
        self.assertEqual(qty(sell_first, A1, U), Decimal(50))
        self.assertUnresolved(sell_first, A1, U, ReplayDetail.LOT_DEPLETION)
        # R2: identical output whichever was typed first.
        self.assertEqual(sell_first.canonical_json(), buy_first.canonical_json())
        # Contrast: starting the day at 0, BUY 100 for 1,000 then SELL 40 is one lot: 600.
        one = [buy(1, A1, M, "2025-01-10", "100", "1000"), sell(2, A1, M, "2025-01-10", "40", "500")]
        self.assertBasis(S(one, "2025-01-10"), A1, M, (usd("600"),))
        swapped = [SequencedEvent(2, one[0].event), SequencedEvent(1, one[1].event)]  # SELL typed first
        self.assertBasis(S(swapped, "2025-01-10"), A1, M, (usd("600"),))

    def test_r2_sell_all_then_buy_equals_buy_then_sell_all(self):
        def run(sell_seq, buy_seq):
            evs = [buy(1, A1, U, "2025-01-02", "100", "1000"),
                   sell(sell_seq, A1, U, "2025-01-10", "100", "1300"),
                   buy(buy_seq, A1, U, "2025-01-10", "50", "600")]
            return S(evs, "2025-01-10", 3).canonical_json()
        self.assertEqual(run(2, 3), run(3, 2))
        # ...and a position that ends the day at 0 resets only at end of day.
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"),
               sell(2, A1, U, "2025-01-10", "100", "1300")]
        self.assertEqual(S(evs, "2025-01-10").account(A1).positions, ())

    def test_example_0_4_e_single_unknown_lot_stays_unknown(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-01-02", listing=M, q="10"),
               sell(2, A1, M, "2025-01-03", "4", "1")]
        state = S(evs, "2025-01-03")
        self.assertEqual(qty(state, A1, M), Decimal(6))
        basis = state.position_basis(A1, M)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.reason_code, ReasonCode.MISSING_COST_BASIS)
        self.assertEqual(basis.causes, (ReplayDetail.UNKNOWN_BASIS,))  # R3: no depletion cause

    def _two_lot_a1(self):
        return [buy(1, A1, U, "2025-01-02", "100", "1000"), buy(2, A1, U, "2025-01-03", "100", "1200")]

    def test_example_0_4_f_whole_move_carries_every_lot_intact(self):
        evs = self._two_lot_a1() + move(3, A1, A3, "2025-01-10", "200")
        state = S(evs, "2025-01-10")
        self.assertEqual(state.account(A1).positions, ())
        self.assertEqual(qty(state, A3, U), Decimal(200))
        self.assertBasis(state, A3, U, (usd("2200"),))
        later = S(evs + [sell(5, A3, U, "2025-01-11", "50", "700")], "2025-01-11")
        self.assertEqual(qty(later, A3, U), Decimal(150))
        self.assertUnresolved(later, A3, U, ReplayDetail.LOT_DEPLETION)  # two lots, then a sale

    def test_example_0_4_f_partial_move_of_two_lots_is_unresolved_both_sides(self):
        state = S(self._two_lot_a1() + move(3, A1, A3, "2025-01-10", "50"), "2025-01-10")
        self.assertEqual((qty(state, A1, U), qty(state, A3, U)), (Decimal(150), Decimal(50)))
        self.assertUnresolved(state, A1, U, ReplayDetail.LOT_DEPLETION)
        self.assertUnresolved(state, A3, U, ReplayDetail.LOT_DEPLETION)
        self.assertEqual(state.portfolio_position_quantity(U).value, Decimal(200))

    # -- 0.4.4 stop conditions, one case each ---------------------------------

    def test_stop_a_prime_two_lots_with_identical_unit_cost_are_unresolved_by_rule(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"), buy(2, A1, U, "2025-01-03", "100", "1000"),
               sell(3, A1, U, "2025-01-04", "50", "600")]
        self.assertUnresolved(S(evs, "2025-01-04"), A1, U, ReplayDetail.LOT_DEPLETION)

    def test_stop_a_double_prime_lots_in_different_currencies(self):
        evs = [buy(1, A1, H, "2025-01-02", "100", "1000", HKD), buy(2, A1, H, "2025-01-03", "100", "700", CNY)]
        before = S(evs, "2025-01-03").position_basis(A1, H).value
        self.assertEqual(before, (Money(Decimal(700), CNY), Money(Decimal(1000), HKD)))  # never summed
        evs.append(sell(3, A1, H, "2025-01-04", "50", "400", HKD))
        self.assertUnresolved(S(evs, "2025-01-04"), A1, H, ReplayDetail.LOT_DEPLETION)

    def test_stop_b_known_plus_unknown_lot_then_sale_reports_both_causes(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"),
               E(2, EventType.TRANSFER_IN, A1, "2025-01-03", listing=U, q="10"),
               sell(3, A1, U, "2025-01-04", "5", "60")]
        basis = S(evs, "2025-01-04").position_basis(A1, U)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.causes, (ReplayDetail.LOT_DEPLETION, ReplayDetail.UNKNOWN_BASIS))
        self.assertEqual(basis.reason_code, ReasonCode.UNRESOLVED_CONVENTION)

    def test_stop_c_a_split_between_acquisition_and_sale_stays_determinate(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "1000"),
               E(2, EventType.SPLIT, A1, "2025-01-05", listing=U, ratio=("2", "1")),
               sell(3, A1, U, "2025-01-06", "5", "300")]
        self.assertBasis(S(evs, "2025-01-06"), A1, U, (usd("750"),))  # c = 100 / 2 = 50; 15 x 50

    def test_stop_d_partial_internal_transfer_of_a_single_lot(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000")] + move(2, A1, A3, "2025-01-10", "30")
        state = S(evs, "2025-01-10")
        self.assertBasis(state, A1, U, (usd("700"),))
        self.assertBasis(state, A3, U, (usd("300"),))

    def test_stop_e_non_integral_split_carries_the_split_cause_not_a_basis(self):
        evs = [buy(1, A1, U, "2025-01-02", "101", "1000"),
               E(2, EventType.SPLIT, A1, "2025-01-05", listing=U, ratio=("3", "2"))]
        basis = S(evs, "2025-01-05").position_basis(A1, U)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.causes, (ReplayDetail.SPLIT_FRACTION,))

    def test_stop_f_negative_quantity_presents_no_basis(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "100"), sell(2, A1, U, "2025-01-03", "15", "200")]
        basis = S(evs, "2025-01-03").position_basis(A1, U)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.reason_code, ReasonCode.LEDGER_INCONSISTENT)

    def test_stop_g_same_day_acquisition_and_depletion_with_units_held(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"), buy(2, A1, U, "2025-01-10", "50", "600"),
               sell(3, A1, U, "2025-01-10", "20", "250")]
        self.assertUnresolved(S(evs, "2025-01-10"), A1, U, ReplayDetail.LOT_DEPLETION)

    def test_stop_h_a_reversed_acquisition_never_existed(self):
        evs = self._two_lot_a1() + [E(3, EventType.REVERSAL, A1, "2025-01-20", reverses=2),
                                    sell(4, A1, U, "2025-01-05", "50", "600")]
        self.assertBasis(S(evs, "2025-01-05", 4), A1, U, (usd("500"),))  # one lot, c = 10
        # Pinned before the reversal (L = 2 plus the sale, as if seq 3 were the sale): two lots.
        unreversed = self._two_lot_a1() + [sell(3, A1, U, "2025-01-05", "50", "600")]
        self.assertUnresolved(S(unreversed, "2025-01-05"), A1, U, ReplayDetail.LOT_DEPLETION)

    # -- statuses and the rest of 0.4.3 / 0.4.5 ---------------------------------

    def test_unresolved_is_sticky_until_a_day_ends_at_zero(self):
        evs = self._two_lot_a1() + [sell(3, A1, U, "2025-01-04", "50", "600"),
                                    buy(4, A1, U, "2025-01-05", "10", "150")]
        self.assertUnresolved(S(evs, "2025-01-05"), A1, U, ReplayDetail.LOT_DEPLETION)
        evs += [sell(5, A1, U, "2025-01-06", "160", "2000"), buy(6, A1, U, "2025-01-07", "5", "80")]
        self.assertEqual(S(evs, "2025-01-06").account(A1).positions, ())
        self.assertBasis(S(evs, "2025-01-07"), A1, U, (usd("80"),))

    def test_negative_flag_stays_after_the_quantity_returns_to_zero_or_above(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "100"), sell(2, A1, U, "2025-01-03", "15", "200"),
               buy(3, A1, U, "2025-01-04", "5", "60")]
        state = S(evs, "2025-01-04")  # quantity is back to exactly 0, still flagged
        (position,) = state.account(A1).positions
        self.assertIsNone(position.quantity.value)
        self.assertEqual(position.quantity.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        self.assertTrue(state.account(A1).has_inconsistency)
        more = S(evs + [buy(4, A1, U, "2025-01-05", "20", "300")], "2025-01-05")
        self.assertIsNone(more.position_quantity(A1, U).value)

    def test_several_partial_out_legs_of_one_lot(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000")] + move(2, A1, A3, "2025-01-10", "30") \
            + move(4, A1, A2, "2025-01-10", "20")
        state = S(evs, "2025-01-10")
        self.assertBasis(state, A1, U, (usd("500"),))
        self.assertBasis(state, A3, U, (usd("300"),))
        self.assertBasis(state, A2, U, (usd("200"),))

    def test_c1c1_partial_move_of_a_single_lot_when_the_source_ends_at_zero(self):
        # Example 0.4-G, G1 (Ruling 0.4.5 (a)): one lot 100 U for 1,000 USD (c = 10). SELL 40
        # plus a move of 60 the same day: A3 gets 60 units at 60 x 10 = 600 USD, AVAILABLE.
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000"), sell(2, A1, U, "2025-01-10", "40", "500")] \
            + move(3, A1, A3, "2025-01-10", "60")
        state = S(evs, "2025-01-10")
        self.assertEqual(state.account(A1).positions, ())
        self.assertEqual(qty(state, A3, U), Decimal(60))
        self.assertBasis(state, A3, U, (usd("600"),))
        # Same result whichever leg was typed first (0.4.2).
        swapped = [evs[0], SequencedEvent(20, evs[1].event)] + evs[2:]
        self.assertEqual(S(swapped, "2025-01-10", 20).canonical_json(),
                         S(evs, "2025-01-10", 20).canonical_json())

    def test_c1c1_two_moves_that_together_empty_a_single_lot(self):
        # Example 0.4-G, G2: A3 300 USD and A2 700 USD (qty 30 and 70), both AVAILABLE.
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000")] + move(2, A1, A3, "2025-01-10", "30") \
            + move(4, A1, A2, "2025-01-10", "70")
        state = S(evs, "2025-01-10")
        self.assertEqual(state.account(A1).positions, ())
        self.assertBasis(state, A3, U, (usd("300"),))
        self.assertBasis(state, A2, U, (usd("700"),))

    def test_whole_move_of_two_lots_plus_another_depletion_is_still_unresolved(self):
        # Two candidate lots and a move that is not whole: which lots moved is lot selection.
        evs = self._two_lot_a1() + [sell(3, A1, U, "2025-01-10", "40", "500")] \
            + move(4, A1, A3, "2025-01-10", "160")
        state = S(evs, "2025-01-10")
        self.assertEqual(state.account(A1).positions, ())
        self.assertEqual(qty(state, A3, U), Decimal(160))
        self.assertUnresolved(state, A3, U, ReplayDetail.LOT_DEPLETION)

    def test_example_0_4_g_boundary_cases(self):
        one_lot = [buy(1, A1, U, "2025-01-02", "100", "1000")]
        # G3 (control): 30 + 20 out; A1 keeps 50 units at 500; A3 300, A2 200.
        g3 = S(one_lot + move(2, A1, A3, "2025-01-10", "30") + move(4, A1, A2, "2025-01-10", "20"),
               "2025-01-10")
        self.assertEqual(qty(g3, A1, U), Decimal(50))
        self.assertBasis(g3, A1, U, (usd("500"),))
        self.assertBasis(g3, A3, U, (usd("300"),))
        self.assertBasis(g3, A2, U, (usd("200"),))
        # G4: SELL 70 plus a move of 30: A3 qty 30, 300 USD.
        g4 = S(one_lot + [sell(2, A1, U, "2025-01-10", "70", "900")] + move(3, A1, A3, "2025-01-10", "30"),
               "2025-01-10")
        self.assertEqual(qty(g4, A3, U), Decimal(30))
        self.assertBasis(g4, A3, U, (usd("300"),))
        # G5: a whole move: 100 units, 1,000 USD.
        g5 = S(one_lot + move(2, A1, A3, "2025-01-10", "100"), "2025-01-10")
        self.assertEqual(qty(g5, A3, U), Decimal(100))
        self.assertBasis(g5, A3, U, (usd("1000"),))
        # G6: a same-day BUY makes two candidate lots: A3's 60 units are unresolved (lot
        # depletion); A1 keeps 20 units, also unresolved; the portfolio quantity is 80.
        g6 = S(one_lot + [sell(2, A1, U, "2025-01-10", "40", "500"), buy(3, A1, U, "2025-01-10", "20", "240")]
               + move(4, A1, A3, "2025-01-10", "60"), "2025-01-10")
        self.assertEqual(qty(g6, A3, U), Decimal(60))
        self.assertUnresolved(g6, A3, U, ReplayDetail.LOT_DEPLETION)
        self.assertEqual(qty(g6, A1, U), Decimal(20))
        self.assertUnresolved(g6, A1, U, ReplayDetail.LOT_DEPLETION)
        self.assertEqual(g6.portfolio_position_quantity(U).value, Decimal(80))

    def test_example_0_4_g_g7_non_terminating_carried_value(self):
        lot = [buy(1, A1, U, "2025-01-02", "3", "100")]
        # SELL 1 plus a move of 2: A3's basis 2 x 100/3 does not terminate; quantity AVAILABLE.
        g7 = S(lot + [sell(2, A1, U, "2025-01-10", "1", "40")] + move(3, A1, A3, "2025-01-10", "2"),
               "2025-01-10")
        self.assertEqual(qty(g7, A3, U), Decimal(2))
        self.assertEqual(g7.position_quantity(A3, U).sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertUnresolved(g7, A3, U, ReplayDetail.BASIS_NOT_EXACT)
        # A move of all 3 alone: 3 x 100/3 = 100 USD.
        whole = S(lot + move(2, A1, A3, "2025-01-10", "3"), "2025-01-10")
        self.assertBasis(whole, A3, U, (usd("100"),))

    def test_example_0_4_g_g8_unknown_basis_arrives_unknown(self):
        evs = [E(1, EventType.TRANSFER_IN, A1, "2025-01-02", listing=U, q="10"),
               sell(2, A1, U, "2025-01-10", "4", "1")] + move(3, A1, A3, "2025-01-10", "6")
        state = S(evs, "2025-01-10")
        self.assertEqual(qty(state, A3, U), Decimal(6))
        basis = state.position_basis(A3, U)
        self.assertIsNone(basis.value)
        self.assertEqual(basis.reason_code, ReasonCode.MISSING_COST_BASIS)
        self.assertEqual(basis.causes, (ReplayDetail.UNKNOWN_BASIS,))  # not depletion, not inconsistency

    # -- Ruling 3.4 / Example 3-B ---------------------------------------------

    def test_example_3b_i_two_same_day_splits_apply_neither_in_either_seq_order(self):
        base = buy(1, A1, U, "2025-01-02", "3", "300")
        halve = lambda seq: E(seq, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("1", "2"))  # noqa: E731
        double = lambda seq: E(seq, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("2", "1"))  # noqa: E731
        outputs = []
        for pair in ((halve(11), double(12)), (double(11), halve(12))):
            state = S([base, *pair], "2025-02-03", 12)
            position = state.account(A1).positions[0]
            self.assertIsNone(position.quantity.value)
            self.assertEqual(position.quantity.reason_code, ReasonCode.LEDGER_INCONSISTENT)
            self.assertEqual(position.quantity_detail, (ReplayDetail.MULTIPLE_SAME_DAY_SPLITS,))
            basis = state.position_basis(A1, U)
            self.assertIsNone(basis.value)
            self.assertEqual(basis.reason_code, ReasonCode.LEDGER_INCONSISTENT)
            self.assertTrue(state.account(A1).has_inconsistency)
            self.assertIsNone(S([base, *pair], "2025-06-30", 12).position_quantity(A1, U).value)  # every D >= d
            self.assertEqual(qty(S([base, *pair], "2025-02-02", 12), A1, U), Decimal(3))  # before d
            outputs.append(state.canonical_json())
        self.assertEqual(outputs[0], outputs[1])  # order-independent (swapping the two events' seqs)

    def test_example_3b_ii_a_share_distribution_recorded_as_two_events(self):
        base = buy(1, A2, H, "2025-01-02", "1000", "10000", CNY)
        two = [base, E(2, EventType.SPLIT, A2, "2025-04-01", listing=H, ratio=("13", "10")),
               E(3, EventType.SPLIT, A2, "2025-04-01", listing=H, ratio=("12", "10"))]
        bad = S(two, "2025-04-01")
        self.assertIsNone(bad.position_quantity(A2, H).value)  # neither 1,560 nor 1,500
        self.assertEqual(bad.position_quantity(A2, H).reason_code, ReasonCode.LEDGER_INCONSISTENT)
        one = S([base, E(2, EventType.SPLIT, A2, "2025-04-01", listing=H, ratio=("15", "10"))], "2025-04-01")
        self.assertEqual(qty(one, A2, H), Decimal(1500))
        self.assertEqual(one.position_basis(A2, H).value, (Money(Decimal(10000), CNY),))

    def test_example_3b_iii_duplicate_entry_then_a_reversal_clears_it(self):
        evs = [buy(1, A1, U, "2025-01-02", "1000", "5000"),
               E(2, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("2", "1")),
               E(3, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("2", "1")),
               E(4, EventType.REVERSAL, A1, "2025-02-10", reverses=3)]
        flagged = S(evs, "2025-02-03", 3)  # not 4,000 and not 2,000
        self.assertIsNone(flagged.position_quantity(A1, U).value)
        self.assertEqual(flagged.position_quantity(A1, U).reason_code, ReasonCode.LEDGER_INCONSISTENT)
        cleared = S(evs, "2025-02-03", 4)  # a new L: one live SPLIT remains
        self.assertEqual(qty(cleared, A1, U), Decimal(2000))
        self.assertBasis(cleared, A1, U, (usd("5000"),))

    def test_example_3b_iv_no_units_at_the_start_of_the_day_is_not_flagged(self):
        evs = [E(1, EventType.SPLIT, A3, "2025-02-03", listing=U, ratio=("2", "1")),
               E(2, EventType.SPLIT, A3, "2025-02-03", listing=U, ratio=("3", "1")),
               buy(3, A3, U, "2025-02-03", "100", "1000")]
        state = S(evs, "2025-02-03")
        self.assertEqual(qty(state, A3, U), Decimal(100))
        self.assertFalse(state.account(A3).has_inconsistency)
        self.assertBasis(state, A3, U, (usd("1000"),))

    def test_ruling_3_4_flag_is_sticky_leaves_cash_alone_and_out_legs_inherit(self):
        evs = [deposit(1, A1, "2025-01-01", "500"), buy(2, A1, U, "2025-01-02", "10", "100"),
               E(3, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("2", "1")),
               E(4, EventType.SPLIT, A1, "2025-02-03", listing=U, ratio=("2", "1"))] \
            + move(5, A1, A3, "2025-02-10", "4")
        state = S(evs, "2025-02-10")
        self.assertEqual(bal(state, A1, USD), Decimal(400))  # cash unaffected
        self.assertIsNone(state.position_quantity(A1, U).value)  # still flagged days later
        self.assertEqual(qty(state, A3, U), Decimal(4))  # receiver's quantity is the recorded in-leg
        basis = state.position_basis(A3, U)
        self.assertEqual(basis.causes, (ReplayDetail.MULTIPLE_SAME_DAY_SPLITS,))
        self.assertEqual(basis.reason_code, ReasonCode.LEDGER_INCONSISTENT)

    def test_c1c4_multi_currency_basis_never_mixes_available_with_insufficient(self):
        evs = [buy(1, A1, U, "2025-01-02", "6", "100"), sell(2, A1, U, "2025-01-03", "2", "40"),
               buy(3, A1, U, "2025-01-04", "1", "10", CNY)]
        state = S(evs, "2025-01-04")
        (entry,) = state.account(A1).positions[0].cost_basis  # one no-value entry only
        self.assertIsNone(entry.result.value)
        self.assertIsNone(entry.currency)
        self.assertEqual(entry.result.reason_code, ReasonCode.UNRESOLVED_CONVENTION)
        self.assertEqual(state.account(A1).positions[0].basis_detail, (ReplayDetail.BASIS_NOT_EXACT,))
        self.assertNotIn('"state":"AVAILABLE","value":"10"', state.canonical_json())
        # Control: when every currency terminates, every entry is AVAILABLE and details are empty.
        ok = S([buy(1, A1, U, "2025-01-02", "6", "100"), buy(2, A1, U, "2025-01-04", "1", "10", CNY)],
               "2025-01-04").account(A1).positions[0]
        self.assertEqual([e.result.sufficiency_state for e in ok.cost_basis],
                         [SufficiencyState.AVAILABLE] * 2)
        self.assertEqual(ok.basis_detail, ())

    def test_c1c5_receiver_inherits_a_split_cause(self):
        evs = [buy(1, A1, U, "2025-01-02", "101", "1000"),
               E(2, EventType.SPLIT, A1, "2025-01-05", listing=U, ratio=("3", "2"))] \
            + move(3, A1, A3, "2025-01-06", "10")
        state = S(evs, "2025-01-06")
        self.assertEqual(state.account(A1).positions[0].quantity_detail, (ReplayDetail.SPLIT_FRACTION,))
        self.assertEqual(qty(state, A3, U), Decimal(10))
        basis = state.position_basis(A3, U)
        self.assertEqual(basis.causes, (ReplayDetail.SPLIT_FRACTION,))  # not LOT_DEPLETION
        self.assertEqual(basis.reason_code, ReasonCode.UNRESOLVED_CONVENTION)

    def test_c1c5_receiver_inherits_an_inconsistency(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "100"), sell(2, A1, U, "2025-01-10", "15", "200")] \
            + move(3, A1, A3, "2025-01-10", "5")
        state = S(evs, "2025-01-10")
        self.assertEqual(state.account(A1).positions[0].quantity.reason_code, ReasonCode.LEDGER_INCONSISTENT)
        basis = state.position_basis(A3, U)
        self.assertEqual(basis.causes, (ReplayDetail.NEGATIVE_QUANTITY,))
        self.assertEqual(basis.reason_code, ReasonCode.LEDGER_INCONSISTENT)  # the true cause

    def test_c1c5_the_cause_survives_a_second_hop(self):
        evs = [buy(1, A1, U, "2025-01-02", "10", "100"), sell(2, A1, U, "2025-01-10", "15", "200")] \
            + move(3, A1, A3, "2025-01-10", "5") + move(5, A3, A2, "2025-01-11", "5")
        state = S(evs, "2025-01-11")
        self.assertEqual(state.position_basis(A2, U).causes, (ReplayDetail.NEGATIVE_QUANTITY,))
        self.assertEqual(state.account(A3).positions, ())

    def test_same_day_chain_of_whole_moves_carries_through(self):
        evs = [buy(1, A1, U, "2025-01-02", "100", "1000")] + move(2, A1, A3, "2025-01-10", "100") \
            + move(4, A3, A2, "2025-01-10", "100")
        state = S(evs, "2025-01-10")
        self.assertEqual((state.account(A1).positions, state.account(A3).positions), ((), ()))
        self.assertBasis(state, A2, U, (usd("1000"),))

    def test_status_is_inherited_across_an_internal_move(self):
        evs = self._two_lot_a1() + [sell(3, A1, U, "2025-01-04", "50", "600")] \
            + move(4, A1, A3, "2025-01-10", "20")
        state = S(evs, "2025-01-10")
        self.assertUnresolved(state, A1, U, ReplayDetail.LOT_DEPLETION)
        self.assertUnresolved(state, A3, U, ReplayDetail.LOT_DEPLETION)
        self.assertEqual(qty(state, A3, U), Decimal(20))  # the receiver's quantity is a recorded fact

    def test_receiver_with_units_gets_a_second_lot(self):
        evs = [buy(1, A3, U, "2025-01-02", "10", "500"), buy(2, A1, U, "2025-01-02", "100", "1000")] \
            + move(3, A1, A3, "2025-01-10", "100")
        state = S(evs, "2025-01-10")
        self.assertBasis(state, A3, U, (usd("1500"),))  # determinate before any depletion
        later = S(evs + [sell(5, A3, U, "2025-01-11", "5", "60")], "2025-01-11")
        self.assertUnresolved(later, A3, U, ReplayDetail.LOT_DEPLETION)

    def test_output_never_depends_on_ledger_seq_within_a_day(self):
        base = [buy(1, A1, U, "2025-01-02", "100", "1000")]
        day = [buy(20, A1, U, "2025-01-10", "50", "600"), sell(21, A1, U, "2025-01-10", "100", "1300")]
        first = base + [SequencedEvent(2, day[0].event), SequencedEvent(3, day[1].event)]
        second = base + [SequencedEvent(3, day[0].event), SequencedEvent(2, day[1].event)]
        self.assertEqual(S(first, "2025-01-10").canonical_json(), S(second, "2025-01-10").canonical_json())


class PurityTests(unittest.TestCase):
    def test_replay_source_has_no_clock_randomness_io_rounding_or_fx(self):
        source = (_SRC / "domain" / "replay.py").read_text(encoding="utf-8")
        code = "\n".join(re.sub(r"#.*", "", line) for line in source.splitlines())
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        for token in (r"import random", r"import time", r"\.now\(", r"\.today\(", r"uuid4", r"os\.environ",
                      r"psycopg", r"open\(", r"quantize", r"\bround\(", r"to_integral", r"float\("):
            with self.subTest(token=token):
                self.assertIsNone(re.search(token, code))


if __name__ == "__main__":
    unittest.main()
