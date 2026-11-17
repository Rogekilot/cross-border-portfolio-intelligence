"""CP1-B step 1 tests for `domain.ledger` — the append-only ledger event
domain model (PRD §9; Tech Plan §13.C-§13.E; PD-0021 §1, §7).

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 -m unittest discover -s tests/product -v
"""

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, CurrencyMismatchError, Money  # noqa: E402
from domain.field_validation import DomainFieldTypeError  # noqa: E402
from domain.ledger import (  # noqa: E402
    CONDITIONAL_FIELDS,
    CROSS_EVENT_RULES_DEFERRED,
    FIELD_RULES,
    FORBIDDEN,
    REQUIRED,
    EventType,
    IdempotencyKey,
    LedgerEvent,
    LedgerEventRuleError,
    SplitRatio,
    validate_correction_pair,
    validate_internal_transfer_pair,
)

# Fixed, deterministic UUID literals — no randomness anywhere in this file.
_E1 = uuid.UUID("e1000000-0000-0000-0000-000000000001")
_E2 = uuid.UUID("e1000000-0000-0000-0000-000000000002")
_E3 = uuid.UUID("e1000000-0000-0000-0000-000000000003")
_ACC = uuid.UUID("a3333333-3333-3333-3333-333333333333")
_ACC2 = uuid.UUID("a4444444-4444-4444-4444-444444444444")
_ACC3 = uuid.UUID("a5555555-5555-5555-5555-555555555555")
_LISTING = uuid.UUID("b3333333-3333-3333-3333-333333333333")
_LISTING2 = uuid.UUID("b4444444-4444-4444-4444-444444444444")

_USD = CurrencyCode("USD")
_HKD = CurrencyCode("HKD")
_D = datetime.date(2024, 3, 15)
_D2 = datetime.date(2024, 3, 17)


def usd(x: str) -> Money:
    return Money(Decimal(x), _USD)


def ev(event_type: EventType, **kw) -> LedgerEvent:
    base = dict(event_id=_E1, account_id=_ACC, event_type=event_type,
                event_date=_D, currency=_USD)
    base.update(kw)
    return LedgerEvent(**base)


def buy(**kw) -> LedgerEvent:
    args = dict(listing_id=_LISTING, quantity=Decimal("10"), amount=usd("1500"))
    args.update(kw)
    return ev(EventType.BUY, **args)


class TaxonomyTests(unittest.TestCase):
    def test_prd_9_5_minimum_taxonomy_present(self) -> None:
        names = {t.value for t in EventType}
        for required in ("BUY", "SELL", "DIVIDEND", "INTEREST", "FEE", "TAX",
                         "DEPOSIT", "WITHDRAWAL", "TRANSFER_IN", "TRANSFER_OUT",
                         "SPLIT"):
            self.assertIn(required, names)

    def test_snapshot_and_reversal_types_present(self) -> None:
        for name in ("OPENING_POSITION", "OPENING_CASH", "REVERSAL"):
            self.assertIn(name, {t.value for t in EventType})

    def test_every_type_has_a_rule_row_covering_every_conditional_field(self) -> None:
        for t in EventType:
            self.assertEqual(set(FIELD_RULES[t]), set(CONDITIONAL_FIELDS), t)


class ValidConstructionTests(unittest.TestCase):
    def test_buy(self) -> None:
        e = buy(settlement_date=_D2, source_reference="CSV-1")
        self.assertEqual(e.listing_id, _LISTING)
        self.assertTrue(e.is_security_event)

    def test_sell_carries_no_lot_selection(self) -> None:
        e = ev(EventType.SELL, listing_id=_LISTING, quantity=Decimal("4"), amount=usd("700"))
        self.assertIsNone(e.cost_basis)
        for f in dataclasses.fields(LedgerEvent):
            self.assertNotIn("lot", f.name)

    def test_dividend_requires_listing(self) -> None:
        ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("12.50"))
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.DIVIDEND, amount=usd("12.50"))

    def test_interest_fee_tax_listing_optional(self) -> None:
        for t in (EventType.INTEREST, EventType.FEE, EventType.TAX):
            ev(t, amount=usd("1"))
            ev(t, amount=usd("1"), listing_id=_LISTING)

    def test_deposit_withdrawal_are_cash_only(self) -> None:
        for t in (EventType.DEPOSIT, EventType.WITHDRAWAL):
            e = ev(t, amount=usd("1000"))
            self.assertFalse(e.is_security_event)
            with self.assertRaises(LedgerEventRuleError):
                ev(t, amount=usd("1000"), listing_id=_LISTING)
            with self.assertRaises(LedgerEventRuleError):
                ev(t, amount=usd("1000"), quantity=Decimal("1"))

    def test_split_records_ratio_only(self) -> None:
        e = ev(EventType.SPLIT, listing_id=_LISTING,
               split_ratio=SplitRatio(Decimal("2"), Decimal("1")))
        self.assertEqual(e.split_ratio.new_units, Decimal("2"))
        for kw in (dict(quantity=Decimal("1")), dict(amount=usd("1"))):
            with self.assertRaises(LedgerEventRuleError):
                ev(EventType.SPLIT, listing_id=_LISTING,
                   split_ratio=SplitRatio(Decimal("2"), Decimal("1")), **kw)

    def test_reverse_split_ratio_allowed(self) -> None:
        SplitRatio(Decimal("1"), Decimal("10"))

    def test_fractional_quantity_is_recorded_not_judged(self) -> None:
        self.assertEqual(buy(quantity=Decimal("0.0001")).quantity, Decimal("0.0001"))

    def test_hkd_and_cny_events_are_native(self) -> None:
        e = ev(EventType.BUY, currency=_HKD, listing_id=_LISTING,
               quantity=Decimal("100"), amount=Money(Decimal("5000"), _HKD))
        self.assertEqual(e.currency, _HKD)


class SnapshotTests(unittest.TestCase):
    def test_opening_position_cost_basis_may_be_absent(self) -> None:
        e = ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("50"))
        self.assertIsNone(e.cost_basis)

    def test_opening_position_with_stated_cost_basis(self) -> None:
        e = ev(EventType.OPENING_POSITION, listing_id=_LISTING,
               quantity=Decimal("50"), cost_basis=usd("4000"))
        self.assertEqual(e.cost_basis, usd("4000"))

    def test_opening_position_needs_listing_and_quantity_no_amount(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_POSITION, quantity=Decimal("50"))
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING,
               quantity=Decimal("1"), amount=usd("1"))

    def test_opening_cash(self) -> None:
        ev(EventType.OPENING_CASH, amount=usd("2500"))
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_CASH, amount=usd("2500"), listing_id=_LISTING)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_CASH)

    def test_no_type_derives_or_defaults_cost_basis(self) -> None:
        self.assertIsNone(buy().cost_basis)
        self.assertEqual(FIELD_RULES[EventType.BUY]["cost_basis"], FORBIDDEN)
        self.assertEqual(FIELD_RULES[EventType.SELL]["cost_basis"], FORBIDDEN)


class TransferTests(unittest.TestCase):
    def test_internal_security_transfer_in_carries_no_basis(self) -> None:
        """ledger-replay/1.0 §6.3 (F2)."""
        e = ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"),
               counterparty_account_id=_ACC2)
        self.assertTrue(e.is_internal_transfer)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"),
               counterparty_account_id=_ACC2, cost_basis=usd("100"))

    def test_external_security_transfer_in_may_carry_basis(self) -> None:
        e = ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"),
               cost_basis=usd("100"))
        self.assertFalse(e.is_internal_transfer)
        ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"))

    def test_external_transfer_has_no_counterparty(self) -> None:
        e = ev(EventType.TRANSFER_OUT, listing_id=_LISTING, quantity=Decimal("5"))
        self.assertIsNone(e.counterparty_account_id)

    def test_cash_transfer(self) -> None:
        ev(EventType.TRANSFER_OUT, amount=usd("100"), counterparty_account_id=_ACC2)

    def test_transfer_out_forbids_cost_basis(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.TRANSFER_OUT, listing_id=_LISTING, quantity=Decimal("5"),
               cost_basis=usd("100"))

    def test_bad_transfer_shapes(self) -> None:
        cases = [
            dict(),  # nothing
            dict(listing_id=_LISTING),  # listing without quantity
            dict(quantity=Decimal("1")),  # quantity without listing
            dict(listing_id=_LISTING, quantity=Decimal("1"), amount=usd("1")),
            dict(amount=usd("1"), cost_basis=usd("1")),
        ]
        for kw in cases:
            with self.assertRaises(LedgerEventRuleError, msg=str(kw)):
                ev(EventType.TRANSFER_IN, **kw)

    def test_counterparty_cannot_be_own_account(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.TRANSFER_IN, amount=usd("1"), counterparty_account_id=_ACC)

    def test_counterparty_forbidden_outside_transfers(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            buy(counterparty_account_id=_ACC2)


class ValueRuleTests(unittest.TestCase):
    def test_quantity_must_be_positive_and_finite(self) -> None:
        for q in (Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")):
            with self.assertRaises(LedgerEventRuleError, msg=str(q)):
                buy(quantity=q)

    def test_amount_must_be_positive(self) -> None:
        for a in ("0", "-5"):
            with self.assertRaises(LedgerEventRuleError):
                buy(amount=usd(a))

    def test_cost_basis_zero_is_a_stated_fact_negative_is_not(self) -> None:
        ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("1"),
           cost_basis=usd("0"))
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("1"),
               cost_basis=usd("-1"))

    def test_split_ratio_must_be_positive_finite_decimals(self) -> None:
        for n, o in ((Decimal("0"), Decimal("1")), (Decimal("1"), Decimal("-1")),
                     (Decimal("NaN"), Decimal("1"))):
            with self.assertRaises(LedgerEventRuleError):
                SplitRatio(n, o)

    def test_money_currency_must_match_event_currency(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            buy(amount=Money(Decimal("1500"), _HKD))
        with self.assertRaises(CurrencyMismatchError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("1"),
               cost_basis=Money(Decimal("1"), _HKD))

    def test_settlement_may_not_precede_event_date(self) -> None:
        buy(settlement_date=_D)
        with self.assertRaises(LedgerEventRuleError):
            buy(settlement_date=datetime.date(2024, 3, 14))

    def test_settlement_forbidden_on_split_and_opening(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_CASH, amount=usd("1"), settlement_date=_D2)

    def test_blank_source_reference_rejected(self) -> None:
        for s in ("", "   "):
            with self.assertRaises(LedgerEventRuleError):
                buy(source_reference=s)


class RuntimeTypingTests(unittest.TestCase):
    """CP1-A F1/F2 strictness applied to ledger fields."""

    def test_ids_must_be_uuid_not_str(self) -> None:
        for field in ("event_id", "account_id", "listing_id"):
            with self.assertRaises(DomainFieldTypeError, msg=field):
                buy(**{field: str(_LISTING)})

    def test_listing_reference_cannot_be_a_ticker_string(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            buy(listing_id="BABA")

    def test_event_type_must_be_enum_not_str(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            ev("BUY", listing_id=_LISTING, quantity=Decimal("1"), amount=usd("1"))

    def test_currency_must_be_currency_code_not_str(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            buy(currency="USD")

    def test_quantity_never_float_int_or_str(self) -> None:
        for q in (1.5, 1, "1", True):
            with self.assertRaises(DomainFieldTypeError, msg=repr(q)):
                buy(quantity=q)

    def test_amount_must_be_money(self) -> None:
        for a in (Decimal("1"), 1.0, "1"):
            with self.assertRaises(DomainFieldTypeError, msg=repr(a)):
                buy(amount=a)

    def test_money_itself_still_rejects_float_and_nonfinite(self) -> None:
        with self.assertRaises(TypeError):
            Money(1.5, _USD)
        with self.assertRaises(ValueError):
            Money(Decimal("NaN"), _USD)

    def test_dates_must_be_date_not_datetime_or_str(self) -> None:
        for d in (datetime.datetime(2024, 3, 15, 9, 30), "2024-03-15", 20240315):
            with self.assertRaises(DomainFieldTypeError, msg=repr(d)):
                buy(event_date=d)
        with self.assertRaises(DomainFieldTypeError):
            buy(settlement_date=datetime.datetime(2024, 3, 16, 0, 0))

    def test_source_reference_must_be_str(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            buy(source_reference=123)

    def test_replace_revalidates(self) -> None:
        e = buy()
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(e, quantity=2.0)
        with self.assertRaises(LedgerEventRuleError):
            dataclasses.replace(e, quantity=Decimal("0"))


class ImmutabilityAndIdentityTests(unittest.TestCase):
    def test_frozen(self) -> None:
        e = buy()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            e.quantity = Decimal("99")  # type: ignore[misc]

    def test_identity_is_event_id(self) -> None:
        self.assertEqual(buy(), buy(quantity=Decimal("11")))
        self.assertNotEqual(buy(), buy(event_id=_E2))
        self.assertEqual(hash(buy()), hash(buy(quantity=Decimal("11"))))

    def test_has_same_content_ignores_event_id_only(self) -> None:
        self.assertTrue(buy().has_same_content(buy(event_id=_E2)))
        self.assertFalse(buy().has_same_content(buy(event_id=_E2, quantity=Decimal("11"))))
        self.assertFalse(buy().has_same_content(buy(event_id=_E2, source_reference="x")))
        self.assertFalse(buy().has_same_content("not an event"))  # type: ignore[arg-type]

    def test_no_external_identifier_or_derived_state_fields(self) -> None:
        names = {f.name for f in dataclasses.fields(LedgerEvent)}
        for banned in ("ticker", "figi", "mic", "exchange", "vendor_id", "symbol",
                       "reporting_currency", "fx_rate", "reporting_amount",
                       "position", "current_shares", "balance", "lot_id"):
            self.assertNotIn(banned, names)


class ReversalAndCorrectionTests(unittest.TestCase):
    def test_reversal_references_target_and_carries_no_economics(self) -> None:
        r = ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=_E1)
        self.assertEqual(r.reverses_event_id, _E1)
        self.assertEqual(r.currency, _USD)
        for kw in (dict(amount=usd("1")), dict(quantity=Decimal("1")),
                   dict(listing_id=_LISTING), dict(corrects_event_id=_E3),
                   dict(settlement_date=_D2)):
            with self.assertRaises(LedgerEventRuleError, msg=str(kw)):
                ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=_E1, **kw)

    def test_reversal_requires_target(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.REVERSAL, event_id=_E2)

    def test_event_cannot_reverse_itself(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=_E2)

    def test_only_reversals_may_reverse(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            buy(event_id=_E2, reverses_event_id=_E1)

    def test_replacement_event_links_to_reversed_event(self) -> None:
        e = buy(event_id=_E3, corrects_event_id=_E1, quantity=Decimal("12"))
        self.assertEqual(e.corrects_event_id, _E1)

    def test_event_cannot_correct_itself(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            buy(event_id=_E3, corrects_event_id=_E3)

    def test_original_is_untouched_by_correction(self) -> None:
        original = buy()
        before = dataclasses.astuple(original)
        ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=original.event_id)
        buy(event_id=_E3, corrects_event_id=original.event_id, quantity=Decimal("12"))
        self.assertEqual(dataclasses.astuple(original), before)

    def test_cross_event_rules_are_declared_deferred(self) -> None:
        text = " ".join(CROSS_EVENT_RULES_DEFERRED)
        for phrase in ("existing event", "at most once", "REVERSAL",
                       "uniqueness", "same account"):
            self.assertIn(phrase, text)

    def test_openings_may_carry_the_correction_link_but_reversals_may_not(self) -> None:
        """CP1B-6: a corrected snapshot keeps its audit link."""
        ev(EventType.OPENING_CASH, amount=usd("1"), corrects_event_id=_E2)
        ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("1"),
           corrects_event_id=_E2)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.REVERSAL, reverses_event_id=_E3, corrects_event_id=_E2)
        with self.assertRaises(LedgerEventRuleError):  # still not a self-reference
            ev(EventType.OPENING_CASH, amount=usd("1"), corrects_event_id=_E1)
        rev = ev(EventType.REVERSAL, event_id=_E3, reverses_event_id=_E2)
        rep = ev(EventType.OPENING_CASH, event_id=_E1, amount=usd("2"), corrects_event_id=_E2)
        validate_correction_pair(rev, rep)


def hkd(x: str) -> Money:
    return Money(Decimal(x), _HKD)


def conversion(**kw) -> LedgerEvent:
    base = dict(amount=usd("1000"), bought_amount=hkd("7780"))
    base.update(kw)
    return ev(EventType.CURRENCY_CONVERSION, **base)


class InterestChargedTests(unittest.TestCase):
    """ledger-replay/1.1 §5.2 (PD-0024 §2)."""

    def test_valid_shape_and_example_5a(self) -> None:
        e = ev(EventType.INTEREST_CHARGED, currency=_HKD, amount=hkd("3.50"),
               event_date=datetime.date(2025, 5, 31))
        self.assertEqual(e.amount.amount, Decimal("3.50"))
        ev(EventType.INTEREST_CHARGED, amount=usd("1"), settlement_date=_D2,
           corrects_event_id=_E3, source_reference="S")

    def test_listing_forbidden_amount_required_positive(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.INTEREST_CHARGED, amount=usd("1"), listing_id=_LISTING)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.INTEREST_CHARGED)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.INTEREST_CHARGED, amount=usd("0"))

    def test_every_other_conditional_field_is_forbidden(self) -> None:
        rules = FIELD_RULES[EventType.INTEREST_CHARGED]
        self.assertEqual(
            {k for k, v in rules.items() if v == FORBIDDEN},
            {"listing_id", "quantity", "cost_basis", "bought_amount", "split_ratio",
             "counterparty_account_id", "ex_date", "reverses_event_id", "acquired_on"},
        )
        self.assertEqual(rules, FIELD_RULES[EventType.WITHDRAWAL])  # same shape as _CASH_ONLY
        for kw in (dict(quantity=Decimal("1")), dict(cost_basis=usd("1")),
                   dict(bought_amount=hkd("1")), dict(counterparty_account_id=_ACC2),
                   dict(ex_date=_D), dict(reverses_event_id=_E2)):
            with self.assertRaises(LedgerEventRuleError, msg=str(kw)):
                ev(EventType.INTEREST_CHARGED, amount=usd("1"), **kw)

    def test_amount_must_be_in_event_currency(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            ev(EventType.INTEREST_CHARGED, amount=hkd("1"))


class CurrencyConversionTests(unittest.TestCase):
    """ledger-replay/1.1 §5A.2 and F11 (PD-0024 §1). Amounts from Example 5A-A."""

    def test_valid_conversion_records_both_sides_as_given(self) -> None:
        e = conversion(event_date=datetime.date(2025, 4, 2),
                       settlement_date=datetime.date(2025, 4, 4))
        self.assertEqual(e.currency, _USD)  # sold side
        self.assertEqual(e.amount, usd("1000"))
        self.assertEqual(e.bought_amount, hkd("7780"))
        self.assertFalse(e.is_security_event)

    def test_bought_currency_must_differ_from_event_currency(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            conversion(bought_amount=usd("7780"))

    def test_bought_amount_is_exempt_from_the_event_currency_rule_only(self) -> None:
        conversion()  # a bought amount in another currency is the required shape
        with self.assertRaises(CurrencyMismatchError):
            conversion(amount=hkd("1000"))  # the sold amount must still be in `currency`

    def test_bought_amount_required_positive_and_typed(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.CURRENCY_CONVERSION, amount=usd("1000"))
        with self.assertRaises(LedgerEventRuleError):
            conversion(bought_amount=hkd("0"))
        for bad in (Decimal("7780"), 7780.0, "7780"):
            with self.assertRaises(DomainFieldTypeError, msg=repr(bad)):
                conversion(bought_amount=bad)
        with self.assertRaises(TypeError):
            Money(7780.0, _HKD)  # Money itself refuses float
        for non_finite in ("NaN", "Infinity"):
            with self.assertRaises(ValueError):
                Money(Decimal(non_finite), _HKD)  # ...and non-finite amounts

    def test_amount_required(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.CURRENCY_CONVERSION, bought_amount=hkd("1"))

    def test_forbidden_fields(self) -> None:
        rules = FIELD_RULES[EventType.CURRENCY_CONVERSION]
        self.assertEqual(
            {k for k, v in rules.items() if v == FORBIDDEN},
            {"listing_id", "quantity", "cost_basis", "split_ratio",
             "counterparty_account_id", "ex_date", "reverses_event_id", "acquired_on"},
        )
        for kw in (dict(listing_id=_LISTING), dict(quantity=Decimal("1")),
                   dict(cost_basis=usd("1")), dict(counterparty_account_id=_ACC2),
                   dict(ex_date=_D), dict(reverses_event_id=_E2)):
            with self.assertRaises(LedgerEventRuleError, msg=str(kw)):
                conversion(**kw)

    def test_optional_fields(self) -> None:
        conversion(settlement_date=_D2, corrects_event_id=_E3, source_reference="FX-1")
        with self.assertRaises(LedgerEventRuleError):
            conversion(settlement_date=datetime.date(2024, 3, 1))

    def test_bought_amount_forbidden_on_every_other_type(self) -> None:
        for t in EventType:
            if t is EventType.CURRENCY_CONVERSION:
                continue
            self.assertEqual(FIELD_RULES[t]["bought_amount"], FORBIDDEN, t)
        with self.assertRaises(LedgerEventRuleError):
            buy(bought_amount=hkd("1"))
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.DEPOSIT, amount=usd("1"), bought_amount=hkd("1"))

    def test_no_rate_field_or_derived_rate(self) -> None:
        names = {f.name for f in dataclasses.fields(LedgerEvent)}
        self.assertFalse([n for n in names if "rate" in n])
        self.assertFalse([n for n in dir(LedgerEvent) if "rate" in n.lower()])
        self.assertFalse([n for n in dir(Money) if "rate" in n.lower()])

    def test_content_comparison_covers_bought_amount(self) -> None:
        a = conversion()
        self.assertTrue(a.has_same_content(conversion(event_id=_E2)))
        self.assertTrue(a.has_same_content(conversion(
            event_id=_E2, bought_amount=hkd("7780.00"))))
        self.assertFalse(a.has_same_content(conversion(
            event_id=_E2, bought_amount=hkd("7750"))))

    def test_correction_pair_of_a_conversion_validates(self) -> None:
        """Example 5A-B: reverse the conversion, replace it with 7,750 HKD."""
        rev = ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=_E1,
                 event_date=datetime.date(2025, 4, 10))
        rep = conversion(event_id=_E3, corrects_event_id=_E1, bought_amount=hkd("7750"),
                         event_date=datetime.date(2025, 4, 2))
        validate_correction_pair(rev, rep)


class ExDateTests(unittest.TestCase):
    """F5: optional DIVIDEND ex_date, not read by CP1 replay."""

    def test_dividend_ex_date_optional_and_bounded_by_pay_date(self) -> None:
        ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("1"))
        e = ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("1"),
               ex_date=datetime.date(2024, 3, 1))
        self.assertEqual(e.ex_date, datetime.date(2024, 3, 1))
        ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("1"), ex_date=_D)  # equal ok
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("1"), ex_date=_D2)

    def test_ex_date_forbidden_on_other_types_and_type_checked(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            buy(ex_date=datetime.date(2024, 3, 1))
        with self.assertRaises(DomainFieldTypeError):
            ev(EventType.DIVIDEND, listing_id=_LISTING, amount=usd("1"),
               ex_date=datetime.datetime(2024, 3, 1, 0, 0))


class PairAndCorrectionValidationTests(unittest.TestCase):
    def _out(self, **kw):
        base = dict(event_id=_E1, account_id=_ACC, counterparty_account_id=_ACC2,
                    listing_id=_LISTING, quantity=Decimal("50"))
        base.update(kw)
        return ev(EventType.TRANSFER_OUT, **base)

    def _in(self, **kw):
        base = dict(event_id=_E2, account_id=_ACC2, counterparty_account_id=_ACC,
                    listing_id=_LISTING, quantity=Decimal("50"))
        base.update(kw)
        return ev(EventType.TRANSFER_IN, **base)

    def test_matching_security_and_cash_pairs_pass(self) -> None:
        validate_internal_transfer_pair(self._out(), self._in())
        cash_out = self._out(listing_id=None, quantity=None, amount=usd("1000"))
        cash_in = self._in(listing_id=None, quantity=None, amount=usd("1000"))
        validate_internal_transfer_pair(cash_out, cash_in)

    def test_each_mismatch_is_refused(self) -> None:
        cases = [
            (self._out(), self._in(account_id=_ACC3)),  # not reciprocal
            (self._out(counterparty_account_id=_ACC3), self._in()),
            (self._out(), self._in(event_date=_D2)),  # date differs
            (self._out(), self._in(currency=_HKD)),
            (self._out(), self._in(quantity=Decimal("49"))),
            (self._out(), self._in(listing_id=_LISTING2)),
            (self._out(), self._in(listing_id=None, quantity=None, amount=usd("1"))),
            (self._out(listing_id=None, quantity=None, amount=usd("1")),
             self._in(listing_id=None, quantity=None, amount=usd("2"))),
        ]
        for out, inn in cases:
            with self.assertRaises(LedgerEventRuleError):
                validate_internal_transfer_pair(out, inn)

    def test_scale_is_not_a_mismatch(self) -> None:
        validate_internal_transfer_pair(
            self._out(quantity=Decimal("50.0")), self._in(quantity=Decimal("50.00")))

    def test_wrong_types_refused(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            validate_internal_transfer_pair(self._in(), self._out())

    def test_correction_pair(self) -> None:
        rev = ev(EventType.REVERSAL, event_id=_E2, reverses_event_id=_E1)
        rep = buy(event_id=_E3, corrects_event_id=_E1)
        validate_correction_pair(rev, rep)
        for bad_rev, bad_rep in (
            (buy(event_id=_E2), rep),
            (rev, buy(event_id=_E3)),  # no corrects link
            (rev, buy(event_id=_E3, corrects_event_id=_E2)),  # different target
            (rev, buy(event_id=_E3, corrects_event_id=_E1, account_id=_ACC2)),
        ):
            with self.assertRaises(LedgerEventRuleError):
                validate_correction_pair(bad_rev, bad_rep)


class IdempotencyKeyTests(unittest.TestCase):
    def test_key_is_account_and_source_reference(self) -> None:
        k = buy(source_reference="BRK-77").idempotency_key
        self.assertEqual(k, IdempotencyKey(_ACC, "BRK-77"))

    def test_same_reference_different_account_is_a_different_key(self) -> None:
        self.assertNotEqual(IdempotencyKey(_ACC, "X"), IdempotencyKey(_ACC2, "X"))
        self.assertNotEqual(
            buy(source_reference="X").idempotency_key,
            buy(account_id=_ACC2, source_reference="X").idempotency_key,
        )

    def test_no_source_reference_means_no_key(self) -> None:
        self.assertIsNone(buy().idempotency_key)

    def test_key_hashable_for_lookup(self) -> None:
        self.assertEqual(len({IdempotencyKey(_ACC, "X"), IdempotencyKey(_ACC, "X")}), 1)

    def test_key_type_and_blank_validation(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            IdempotencyKey(str(_ACC), "X")  # type: ignore[arg-type]
        with self.assertRaises(DomainFieldTypeError):
            IdempotencyKey(_ACC, 5)  # type: ignore[arg-type]
        with self.assertRaises(LedgerEventRuleError):
            IdempotencyKey(_ACC, "  ")

    def test_source_reference_is_not_normalized(self) -> None:
        self.assertNotEqual(IdempotencyKey(_ACC, "x"), IdempotencyKey(_ACC, "X"))


class RuleTableTests(unittest.TestCase):
    def test_required_fields_are_enforced_for_every_type(self) -> None:
        """Drop each REQUIRED conditional field from a known-valid event: must fail."""
        valid = {
            EventType.BUY: dict(listing_id=_LISTING, quantity=Decimal("1"), amount=usd("1")),
            EventType.SELL: dict(listing_id=_LISTING, quantity=Decimal("1"), amount=usd("1")),
            EventType.DIVIDEND: dict(listing_id=_LISTING, amount=usd("1")),
            EventType.INTEREST: dict(amount=usd("1")),
            EventType.FEE: dict(amount=usd("1")),
            EventType.TAX: dict(amount=usd("1")),
            EventType.DEPOSIT: dict(amount=usd("1")),
            EventType.WITHDRAWAL: dict(amount=usd("1")),
            EventType.SPLIT: dict(listing_id=_LISTING,
                                  split_ratio=SplitRatio(Decimal("2"), Decimal("1"))),
            EventType.OPENING_POSITION: dict(listing_id=_LISTING, quantity=Decimal("1")),
            EventType.OPENING_CASH: dict(amount=usd("1")),
            EventType.INTEREST_CHARGED: dict(amount=usd("1")),
            EventType.CURRENCY_CONVERSION: dict(
                amount=usd("1"), bought_amount=Money(Decimal("7.78"), _HKD)),
            EventType.REVERSAL: dict(reverses_event_id=_E2),
        }
        # TRANSFER_IN/OUT have no REQUIRED field (shape rule instead); all others covered.
        self.assertEqual(set(EventType) - set(valid),
                         {EventType.TRANSFER_IN, EventType.TRANSFER_OUT})
        for t, kw in valid.items():
            ev(t, **kw)
            for name, rule in FIELD_RULES[t].items():
                if rule == REQUIRED:
                    trimmed = {k: v for k, v in kw.items() if k != name}
                    with self.assertRaises(LedgerEventRuleError, msg=f"{t} {name}"):
                        ev(t, **trimmed)


class AcquiredOnTests(unittest.TestCase):
    """PD-0036 §1: an optional user-supplied acquisition date, only on OPENING_POSITION and an external security TRANSFER_IN, never after the event date."""

    EARLIER = datetime.date(2024, 1, 4)

    def test_allowed_on_an_opening_position_and_an_external_security_transfer_in(self) -> None:
        e = ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"), cost_basis=usd("100"), acquired_on=self.EARLIER)
        self.assertEqual(e.acquired_on, self.EARLIER)
        t = ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"), acquired_on=self.EARLIER)
        self.assertEqual(t.acquired_on, self.EARLIER)
        self.assertEqual(ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"), acquired_on=_D).acquired_on, _D)  # equal to the event date: allowed

    def test_never_after_the_event_date(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"), acquired_on=_D + datetime.timedelta(days=1))

    def test_not_on_an_internal_in_leg_a_cash_transfer_or_any_other_type(self) -> None:
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.TRANSFER_IN, listing_id=_LISTING, quantity=Decimal("5"), counterparty_account_id=_ACC2, acquired_on=self.EARLIER)
        with self.assertRaises(LedgerEventRuleError):
            ev(EventType.TRANSFER_IN, amount=usd("5"), acquired_on=self.EARLIER)
        with self.assertRaises(LedgerEventRuleError):
            buy(acquired_on=self.EARLIER)
        for t in EventType:
            expected = "OPTIONAL" if t in (EventType.OPENING_POSITION, EventType.TRANSFER_IN) else "FORBIDDEN"
            self.assertEqual(FIELD_RULES[t]["acquired_on"], expected, t)

    def test_it_is_content_and_a_datetime_is_not_a_date(self) -> None:
        a = ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"), acquired_on=self.EARLIER)
        b = ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"))
        self.assertFalse(a.has_same_content(b))  # a re-submission that adds a date is a different fact (a correction, not an idempotent no-op)
        with self.assertRaises(DomainFieldTypeError):
            ev(EventType.OPENING_POSITION, listing_id=_LISTING, quantity=Decimal("5"), acquired_on=datetime.datetime(2024, 1, 4))


if __name__ == "__main__":
    unittest.main()
