"""Append-only ledger event domain model (CP1-B step 1; PRD §9.1-§9.7;
Tech Plan §3.1, §6.2, §13.C-§13.E; PD-0021 §1, §7, §10).

This module defines the *shape and the in-memory validity rules* of a ledger
fact. It stores nothing, orders nothing, and derives nothing.

**Append-only by construction.** `LedgerEvent` is a frozen dataclass. A
correction is never a mutation: it is a new event that references the event
it reverses (`EventType.REVERSAL`, `reverses_event_id`) and, optionally, a
replacement event that names the reversed event it corrects
(`corrects_event_id`). `dataclasses.replace(event, ...)` still constructs a
*new* object that is re-validated; it is not a persistence operation and
must not be used to "edit" a stored event (the persistence step forbids
UPDATE/DELETE, Tech Plan §13.D).

**Identity.** Like the CP1-A entities, an event is identified by its own
internal `event_id` (`domain.entity_identity`), not by its content. Two
events with the same content but different IDs are different facts.
`has_same_content` exists so the persistence step can distinguish an
idempotent re-submission from a key conflict.

**Security references (PD-0021 §1.1).** A security event carries the internal
`listing_id` only. There is deliberately no ticker, FIGI, MIC or vendor
field on an event, so an external-identifier correction can never require a
ledger migration.

**Currency (Tech Plan §13.E).** Every event carries `currency`, the
currency the fact was denominated in. Every `Money` on an event must be in
that currency, with ONE type-specific exception (ledger-replay/1.1 F11):
`CURRENCY_CONVERSION.bought_amount` is the bought side of a conversion and
MUST be in a currency different from the event currency (the sold side, which
`currency` and `amount` carry). No reporting-currency value exists on an event.
No FX rate is stored, computed or implied anywhere: a conversion records the
two amounts the source reports and nothing else (PD-0024 §1; §5A.7).

**No derived state.** There is no position, no cash balance, no "current
shares" field (PRD §9.1). Quantities are per-event facts, always positive;
direction is carried by the event type.

**Replay conventions.** Which date governs replay, reversal as-of semantics,
transfer matching and the snapshot horizon are answered by the Quant's
`methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (ledger-replay/1.1); this module
only records facts and checks the rules of that document that fit one event
(F2: no cost_basis on an internal TRANSFER_IN; F5: optional DIVIDEND ex_date,
not after the pay date) or a pair (`validate_internal_transfer_pair`,
`validate_correction_pair`). Still undecided and not decided here: lot
depletion, split fractional treatment, return denominators.

**Quant boundary (PD-0021 §9).** Nothing here decides: lot depletion (SELL
records a fact and selects no lots), split fractional-share treatment (SPLIT
records the ratio as given), return denominators, whether trade or
settlement date governs as-of inclusion (both dates are recorded when the
fact has them; replay chooses, CP1-C), the as-of semantics of a reversal, or
cost-basis method. Cost basis is optional and is never derived or defaulted
(PRD §9.3).

**Taxonomy (PRD §9.5).** `SYMBOL_CHANGE` is not an event type: under
PD-0021 §1.4 a ticker change is an identity-attribute update on the
`Listing`, and `listing_id` does not change. `CORPORATE_ACTION` beyond `SPLIT`
(merger, spin-off, ...) is not modelled: it needs economic-continuity
methodology (PRD §12.4) and the CP2 market-data `CorporateAction` contract.
Both are recorded as deferred in `implementation/FEATURE_TECH_PLAN.md`.

**Deferred to the persistence step (they need storage).** See
`CROSS_EVENT_RULES_DEFERRED` below.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from types import MappingProxyType
from typing import Any, Mapping, Optional

from domain.currency import CurrencyCode, CurrencyMismatchError, Money
from domain.entity_identity import identity_eq, identity_hash
from domain.field_validation import (
    DomainFieldTypeError,
    require_optional_type,
    require_type,
)


class LedgerEventRuleError(ValueError):
    """A type-correct `LedgerEvent` / `SplitRatio` / `IdempotencyKey` that
    violates a content or per-event-type rule (missing required field,
    forbidden field present, non-positive quantity, self-reference, ...).
    Wrong Python types raise `DomainFieldTypeError` instead."""


@unique
class EventType(Enum):
    """PRD §9.5 minimum taxonomy, plus the two synthetic snapshot types
    (PRD §9.2) and `REVERSAL` (Tech Plan §13.D)."""

    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    FEE = "FEE"
    TAX = "TAX"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    SPLIT = "SPLIT"
    INTEREST_CHARGED = "INTEREST_CHARGED"  # PD-0024 §2; ledger-replay/1.1 §5
    CURRENCY_CONVERSION = "CURRENCY_CONVERSION"  # PD-0024 §1; ledger-replay/1.1 §5A
    OPENING_POSITION = "OPENING_POSITION"  # synthetic, snapshot-only (PRD §9.2)
    OPENING_CASH = "OPENING_CASH"  # synthetic, snapshot-only (PRD §9.2)
    REVERSAL = "REVERSAL"


#: Bounds on every quantity, amount, cost basis and split-ratio component (migration 0008,
#: R3-1): value < 1E30 (at most 30 integer digits) and at most 24 decimals of scale. ENFORCED
#: BY THE DATABASE (CHECK) at append; this module states the same limits so a test can
#: compare them, but the event constructors deliberately do not reject them: replay must
#: still be able to represent (and refuse to be crashed by) values from older or foreign
#: data, and an event the database would refuse is refused there with a typed error.
NUMERIC_LIMIT = Decimal("1E30")
NUMERIC_MAX_SCALE = 24


def numeric_bounds_violation(value: Decimal) -> Optional[str]:
    """A message when `value` is outside the ledger's numeric bounds, else None. Non-finite
    values are left to the callers' own finiteness checks. Scale is the STORED scale, as in
    PostgreSQL's `scale()`: an exponent below zero counts, trailing zeros included."""
    if not value.is_finite():
        return None
    if value.copy_abs() >= NUMERIC_LIMIT:  # copy_abs: `abs()` would round to context precision
        return f"must be below 1E30 (at most 30 integer digits), got {value!r}"
    scale = max(0, -value.as_tuple().exponent)
    if scale > NUMERIC_MAX_SCALE:
        return f"must have at most {NUMERIC_MAX_SCALE} decimal places, got {value!r}"
    return None


@dataclass(frozen=True)
class SplitRatio:
    """`new_units` for every `old_units` held, exactly as reported (2-for-1
    is `(2, 1)`; a 1-for-10 reverse split is `(1, 10)`). Recorded, not
    applied: no position is derived and no fractional-share treatment is
    chosen here."""

    new_units: Decimal
    old_units: Decimal

    def __post_init__(self) -> None:
        require_type(self, "new_units", self.new_units, Decimal)
        require_type(self, "old_units", self.old_units, Decimal)
        for name in ("new_units", "old_units"):
            value = getattr(self, name)
            if not value.is_finite() or value <= 0:
                raise LedgerEventRuleError(
                    f"SplitRatio.{name} must be a finite Decimal > 0, got {value!r}"
                )


@dataclass(frozen=True)
class IdempotencyKey:
    """`(account_id, source_reference)` — Tech Plan §13.D. Enforcement
    (uniqueness) is the persistence step's job. `source_reference` is used
    verbatim (no normalization); it must not be blank."""

    account_id: uuid.UUID
    source_reference: str

    def __post_init__(self) -> None:
        require_type(self, "account_id", self.account_id, uuid.UUID)
        require_type(self, "source_reference", self.source_reference, str)
        if not self.source_reference.strip():
            raise LedgerEventRuleError("IdempotencyKey.source_reference must not be blank")


# --- per-event-type field rules -------------------------------------------

REQUIRED = "REQUIRED"
OPTIONAL = "OPTIONAL"
FORBIDDEN = "FORBIDDEN"

#: Fields whose presence is governed per event type. (`event_id`, `account_id`,
#: `event_type`, `event_date`, `currency` are required on every event.)
CONDITIONAL_FIELDS = (
    "listing_id",
    "quantity",
    "amount",
    "cost_basis",
    "bought_amount",
    "split_ratio",
    "counterparty_account_id",
    "settlement_date",
    "ex_date",
    "reverses_event_id",
    "corrects_event_id",
    "source_reference",
    "acquired_on",  # PD-0036 §1: optional, OPENING_POSITION and external security TRANSFER_IN only
)


def _rules(**overrides: str) -> Mapping[str, str]:
    base = {name: FORBIDDEN for name in CONDITIONAL_FIELDS}
    base["source_reference"] = OPTIONAL
    for name, rule in overrides.items():
        if name not in base:
            raise AssertionError(name)
        base[name] = rule
    return MappingProxyType(base)


_TRADE = dict(
    listing_id=REQUIRED, quantity=REQUIRED, amount=REQUIRED,
    settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
)
_CASH_ATTRIBUTABLE = dict(
    listing_id=OPTIONAL, amount=REQUIRED,
    settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
)
_CASH_ONLY = dict(
    amount=REQUIRED, settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
)

#: Table form of the per-type rules, public so the persistence step can derive
#: CHECK constraints from the same source. TRANSFER_IN/OUT additionally obey
#: the shape rule in `_validate_transfer_shape`.
FIELD_RULES: Mapping[EventType, Mapping[str, str]] = MappingProxyType({
    EventType.BUY: _rules(**_TRADE),
    EventType.SELL: _rules(**_TRADE),
    # ex_date: optional, recorded only; CP1 replay never reads it (ledger-replay/1.0 §4).
    EventType.DIVIDEND: _rules(
        listing_id=REQUIRED, amount=REQUIRED, ex_date=OPTIONAL,
        settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
    ),
    EventType.INTEREST: _rules(**_CASH_ATTRIBUTABLE),
    EventType.FEE: _rules(**_CASH_ATTRIBUTABLE),
    EventType.TAX: _rules(**_CASH_ATTRIBUTABLE),
    EventType.DEPOSIT: _rules(**_CASH_ONLY),
    EventType.WITHDRAWAL: _rules(**_CASH_ONLY),
    EventType.TRANSFER_IN: _rules(
        listing_id=OPTIONAL, quantity=OPTIONAL, amount=OPTIONAL,
        cost_basis=OPTIONAL, counterparty_account_id=OPTIONAL,
        settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
        acquired_on=OPTIONAL,  # external security form only: `_validate_transfer_shape` and migration 0014
    ),
    EventType.TRANSFER_OUT: _rules(
        listing_id=OPTIONAL, quantity=OPTIONAL, amount=OPTIONAL,
        counterparty_account_id=OPTIONAL,
        settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
    ),
    EventType.SPLIT: _rules(
        listing_id=REQUIRED, split_ratio=REQUIRED, corrects_event_id=OPTIONAL,
    ),
    # ledger-replay/1.1 §5.2: cash-only, no listing (a security-attributable charge is a FEE).
    EventType.INTEREST_CHARGED: _rules(**_CASH_ONLY),
    # ledger-replay/1.1 §5A.2: one event, two amounts; `currency`/`amount` are the SOLD
    # side, `bought_amount` the bought side. There is no rate field, by design (§5A.7).
    EventType.CURRENCY_CONVERSION: _rules(
        amount=REQUIRED, bought_amount=REQUIRED,
        settlement_date=OPTIONAL, corrects_event_id=OPTIONAL,
    ),
    EventType.OPENING_POSITION: _rules(
        listing_id=REQUIRED, quantity=REQUIRED, cost_basis=OPTIONAL,
        corrects_event_id=OPTIONAL,  # CP1B-6: a corrected opening keeps its audit link
        acquired_on=OPTIONAL,  # PD-0036 §1: the date the user says these units were acquired
    ),
    EventType.OPENING_CASH: _rules(amount=REQUIRED, corrects_event_id=OPTIONAL),
    EventType.REVERSAL: _rules(reverses_event_id=REQUIRED),
})

#: Rules that need more than this one event and are therefore NOT checked
#: here. The persistence layer enforces them at append/commit time; CP1-C
#: replay may assume they hold. Convention set: ledger-replay/1.0
#: (`methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md`).
CROSS_EVENT_RULES_DEFERRED = (
    "reverses_event_id / corrects_event_id must reference an existing event",
    "a reversal must be in the same account and the same currency as its target "
    "(for a CURRENCY_CONVERSION that is the sold currency, the event currency)",
    "a reversal target must not itself be a REVERSAL",
    "an event may be reversed at most once",
    "corrects_event_id must name an event that is reversed (by an appended REVERSAL) "
    "and that REVERSAL must have been inserted by the SAME transaction as the "
    "replacement (F10 atomicity, enforced with pg_xact_status; CP1B-5)",
    "account.account_id and account.portfolio_id are immutable (CP1B-3)",
    "recorded_at is set by the database, never by the inserting role (CP1B-8)",
    "a same-key/same-content or same-event_id resubmission is decided as an "
    "idempotent no-op BEFORE the snapshot and cross-event rules run (CP1B-2)",
    "trigger functions pin search_path (schema, pg_temp) so TEMP objects cannot "
    "shadow the ledger tables or sequence (CP1B-1)",
    "a reversed event may be corrected at most once, and the replacement must be "
    "in the same account as the event it corrects (same account)",
    "(account_id, source_reference) uniqueness; same key + same content is a "
    "no-op, same key + different content is a conflict (see has_same_content)",
    "counterparty_account_id must be an account in the same portfolio",
    "internal transfer legs must match (ledger-replay/1.0 §6.2: reciprocal "
    "counterparties, same event_date, same currency, same amount or same "
    "listing and quantity): per matching group, live TRANSFER_OUT legs equal "
    "live TRANSFER_IN legs at commit; reversing a leg needs its partner "
    "reversed in the same transaction",
    "snapshot accounts (§8): all live OPENING_* events of an account share one "
    "event_date S; every other non-REVERSAL event in the account is dated after "
    "S (a SPLIT dated S is the only exception)",
    "ledger_seq is commit-stable per portfolio (§2.3): appends to one "
    "portfolio are serialized and the sequence value is drawn under that lock",
    "a replacement becomes visible after its reversal (reversal has the lower "
    "ledger_seq): implied by the corrects rule plus the per-portfolio lock",
    "event.account_id / listing_id / counterparty_account_id must reference "
    "existing rows",
    "an event referencing a listing does not check the listing's trading "
    "currency: the event currency is the currency the fact was denominated "
    "in, which may differ",
    "append order / sequence position (ledger_version) is assigned by storage",
)


@dataclass(frozen=True, eq=False)
class LedgerEvent:
    """One immutable ledger fact. See module docstring.

    `event_date` is the date the source reports for the fact (trade date for
    BUY/SELL). `settlement_date`, when the fact has one, is recorded
    separately; this model does not say which one governs replay.
    `amount` is a positive magnitude (gross consideration for BUY/SELL, the
    cash amount otherwise); direction comes from `event_type`. `cost_basis`
    is the total basis in the event currency where the user supplied one;
    `None` means unknown, never zero.
    """

    event_id: uuid.UUID
    account_id: uuid.UUID
    event_type: EventType
    event_date: datetime.date
    currency: CurrencyCode
    listing_id: Optional[uuid.UUID] = None
    quantity: Optional[Decimal] = None
    amount: Optional[Money] = None
    cost_basis: Optional[Money] = None
    bought_amount: Optional[Money] = None
    split_ratio: Optional[SplitRatio] = None
    counterparty_account_id: Optional[uuid.UUID] = None
    settlement_date: Optional[datetime.date] = None
    ex_date: Optional[datetime.date] = None
    reverses_event_id: Optional[uuid.UUID] = None
    corrects_event_id: Optional[uuid.UUID] = None
    source_reference: Optional[str] = None
    #: PD-0036 §1 (ledger-replay/1.5 Ruling 0.6): the date the USER says the units were acquired. Optional and user-supplied, allowed only on an
    #: OPENING_POSITION and on an external security TRANSFER_IN, never after `event_date`. Never inferred. The `none` replay mode never reads it.
    acquired_on: Optional[datetime.date] = None

    def __post_init__(self) -> None:
        require_type(self, "event_id", self.event_id, uuid.UUID)
        require_type(self, "account_id", self.account_id, uuid.UUID)
        require_type(self, "event_type", self.event_type, EventType)
        _require_date(self, "event_date", self.event_date)
        require_type(self, "currency", self.currency, CurrencyCode)
        require_optional_type(self, "listing_id", self.listing_id, uuid.UUID)
        require_optional_type(self, "quantity", self.quantity, Decimal)
        require_optional_type(self, "amount", self.amount, Money)
        require_optional_type(self, "cost_basis", self.cost_basis, Money)
        require_optional_type(self, "bought_amount", self.bought_amount, Money)
        require_optional_type(self, "split_ratio", self.split_ratio, SplitRatio)
        require_optional_type(
            self, "counterparty_account_id", self.counterparty_account_id, uuid.UUID
        )
        if self.settlement_date is not None:
            _require_date(self, "settlement_date", self.settlement_date)
        if self.ex_date is not None:
            _require_date(self, "ex_date", self.ex_date)
        if self.acquired_on is not None:
            _require_date(self, "acquired_on", self.acquired_on)
        require_optional_type(self, "reverses_event_id", self.reverses_event_id, uuid.UUID)
        require_optional_type(self, "corrects_event_id", self.corrects_event_id, uuid.UUID)
        require_optional_type(self, "source_reference", self.source_reference, str)

        self._validate_presence()
        self._validate_values()
        if self.event_type in (EventType.TRANSFER_IN, EventType.TRANSFER_OUT):
            self._validate_transfer_shape()

    # -- validation ---------------------------------------------------------

    def _fail(self, message: str) -> None:
        raise LedgerEventRuleError(f"LedgerEvent({self.event_type.value}): {message}")

    def _validate_presence(self) -> None:
        rules = FIELD_RULES[self.event_type]
        for name in CONDITIONAL_FIELDS:
            present = getattr(self, name) is not None
            if rules[name] == REQUIRED and not present:
                self._fail(f"{name} is required")
            if rules[name] == FORBIDDEN and present:
                self._fail(f"{name} is not allowed")

    def _validate_values(self) -> None:
        if self.quantity is not None:
            if not self.quantity.is_finite() or self.quantity <= 0:
                self._fail(f"quantity must be a finite Decimal > 0, got {self.quantity!r}")
        if self.amount is not None:
            self._require_event_currency("amount", self.amount)
            if self.amount.amount <= 0:
                self._fail(f"amount must be > 0, got {self.amount.amount!r}")
        if self.cost_basis is not None:
            self._require_event_currency("cost_basis", self.cost_basis)
            if self.cost_basis.amount < 0:
                self._fail(f"cost_basis must be >= 0, got {self.cost_basis.amount!r}")
        if self.bought_amount is not None:
            # The one Money exempt from the event-currency rule (F11): it must
            # differ from it. Presence is limited to CURRENCY_CONVERSION by FIELD_RULES.
            if self.bought_amount.currency == self.currency:
                self._fail("bought_amount must be in a currency different from the event currency")
            if self.bought_amount.amount <= 0:
                self._fail(f"bought_amount must be > 0, got {self.bought_amount.amount!r}")
        if self.settlement_date is not None and self.settlement_date < self.event_date:
            self._fail("settlement_date must not precede event_date")
        # ledger-replay/1.0 §4: ex-date is on or before the pay date (event_date).
        if self.ex_date is not None and self.ex_date > self.event_date:
            self._fail("ex_date must not be after event_date (the pay date)")
        # PD-0036 §1: the recorded acquisition date is not later than the event it comes with.
        if self.acquired_on is not None and self.acquired_on > self.event_date:
            self._fail("acquired_on must not be after event_date")
        if self.counterparty_account_id == self.account_id:
            self._fail("counterparty_account_id must differ from account_id")
        if self.reverses_event_id == self.event_id:
            self._fail("an event cannot reverse itself")
        if self.corrects_event_id == self.event_id:
            self._fail("an event cannot correct itself")
        if self.source_reference is not None and not self.source_reference.strip():
            self._fail("source_reference must not be blank when given")

    def _require_event_currency(self, name: str, money: Money) -> None:
        if money.currency != self.currency:
            raise CurrencyMismatchError(
                f"LedgerEvent({self.event_type.value}).{name} is in "
                f"{money.currency} but the event currency is {self.currency}; "
                "no conversion is performed (P8)"
            )

    def _validate_transfer_shape(self) -> None:
        security_form = self.listing_id is not None or self.quantity is not None
        if security_form:
            if self.listing_id is None or self.quantity is None:
                self._fail("a security transfer needs both listing_id and quantity")
            if self.amount is not None:
                self._fail("a security transfer carries no amount (use cost_basis)")
        else:
            if self.amount is None:
                self._fail("a transfer needs listing_id+quantity or an amount")
            if self.cost_basis is not None:
                self._fail("cost_basis applies to security transfers only")
        # ledger-replay/1.0 §6.3 (F2): on an internal transfer the receiving
        # basis is carried from the source, never declared.
        if (
            self.event_type is EventType.TRANSFER_IN
            and self.counterparty_account_id is not None
            and self.cost_basis is not None
        ):
            self._fail("an internal TRANSFER_IN carries no cost_basis (basis is carried)")
        # PD-0036 §1: acquired_on belongs to an EXTERNAL SECURITY in-leg (an internal one carries its source lot's date; a cash transfer has no lot).
        if self.acquired_on is not None and not (
            self.event_type is EventType.TRANSFER_IN and security_form and self.counterparty_account_id is None
        ):
            self._fail("acquired_on is allowed only on an external security TRANSFER_IN")

    # -- derived views (no storage, no state) -------------------------------

    @property
    def idempotency_key(self) -> Optional[IdempotencyKey]:
        """`(account_id, source_reference)`, or `None` when the event has no
        source reference (persistence then has no natural key to dedupe on)."""
        if self.source_reference is None:
            return None
        return IdempotencyKey(self.account_id, self.source_reference)

    @property
    def is_security_event(self) -> bool:
        return self.listing_id is not None

    @property
    def is_internal_transfer(self) -> bool:
        """A transfer leg naming a counterparty account (ledger-replay/1.0 §6.1)."""
        return (
            self.event_type in (EventType.TRANSFER_IN, EventType.TRANSFER_OUT)
            and self.counterparty_account_id is not None
        )

    def has_same_content(self, other: "LedgerEvent") -> bool:
        """True when every field except `event_id` is equal. Decimal equality
        is numeric (`Decimal("1.0") == Decimal("1.00")`)."""
        if not isinstance(other, LedgerEvent):
            return False
        return all(
            getattr(self, f.name) == getattr(other, f.name)
            for f in dataclasses.fields(self)
            if f.name != "event_id"
        )

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "event_id")

    def __hash__(self) -> int:
        return identity_hash(self, "event_id")


def validate_internal_transfer_pair(transfer_out: LedgerEvent, transfer_in: LedgerEvent) -> None:
    """ledger-replay/1.0 §6.2 "matched", checkable on the two events alone:
    one TRANSFER_OUT and one TRANSFER_IN, each naming the other's account as
    counterparty, same event_date, same currency, and either the same amount
    (cash form) or the same listing_id and quantity (security form). (Same
    portfolio needs storage and is enforced by the database.)"""
    if transfer_out.event_type is not EventType.TRANSFER_OUT:
        raise LedgerEventRuleError("first leg must be a TRANSFER_OUT")
    if transfer_in.event_type is not EventType.TRANSFER_IN:
        raise LedgerEventRuleError("second leg must be a TRANSFER_IN")
    if transfer_out.counterparty_account_id != transfer_in.account_id:
        raise LedgerEventRuleError("TRANSFER_OUT counterparty must be the TRANSFER_IN account")
    if transfer_in.counterparty_account_id != transfer_out.account_id:
        raise LedgerEventRuleError("TRANSFER_IN counterparty must be the TRANSFER_OUT account")
    if transfer_out.event_date != transfer_in.event_date:
        raise LedgerEventRuleError("both legs of an internal transfer carry the same event_date")
    if transfer_out.currency != transfer_in.currency:
        raise LedgerEventRuleError("both legs of an internal transfer share one currency")
    if (transfer_out.amount is None) != (transfer_in.amount is None):
        raise LedgerEventRuleError("both legs must be cash form or both security form")
    if transfer_out.amount != transfer_in.amount:
        raise LedgerEventRuleError("legs must move the same amount")
    if (transfer_out.listing_id, transfer_out.quantity) != (
        transfer_in.listing_id, transfer_in.quantity
    ):
        raise LedgerEventRuleError("legs must move the same listing and quantity")


def validate_correction_pair(reversal: LedgerEvent, replacement: LedgerEvent) -> None:
    """A correction is a REVERSAL plus a replacement naming the reversed event
    in `corrects_event_id`, in the same account (Tech Plan §13.D, F10)."""
    if reversal.event_type is not EventType.REVERSAL:
        raise LedgerEventRuleError("the first event of a correction must be a REVERSAL")
    if replacement.event_type is EventType.REVERSAL:
        raise LedgerEventRuleError("the replacement of a correction cannot be a REVERSAL")
    if replacement.corrects_event_id != reversal.reverses_event_id:
        raise LedgerEventRuleError(
            "replacement.corrects_event_id must equal reversal.reverses_event_id"
        )
    if replacement.account_id != reversal.account_id:
        raise LedgerEventRuleError("a replacement must be in the account of the event it corrects")


def _require_date(entity: object, field_name: str, value: object) -> None:
    # datetime is a subclass of date; a timestamp is not a calendar date.
    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise DomainFieldTypeError(
            f"{entity.__class__.__name__}.{field_name} must be a datetime.date "
            f"(not a datetime), got {type(value).__name__} ({value!r})"
        )
