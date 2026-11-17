"""CP1-C: deterministic point-in-time replay of the ledger (`ledger-replay/1.3`).

`reconstruct(events, as_of, ledger_version)` is a PURE function. It reads only
the events it is handed. It has no wall clock, no randomness, no I/O, no FX and
no price. It returns the replayed state `S(D, L)` of
`methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` §0: account-level positions keyed
`(account, listing)` and cash keyed `(account, currency)`, in NATIVE currency
only. Nothing is ever converted or summed across currencies (PRD §8.1, Tech Plan
§13.E); a reporting-currency view is a CP2/CP3 computation on top of this.

Convention map (section of the methodology document -> code)
------------------------------------------------------------
- §0.1 two axes: `as_of` (D, inclusive, `event_date <= D`) and `ledger_version`
  (L, `ledger_seq <= L`). `_select_live` and the `event_date` filter in `reconstruct`.
- §0.2 effect table: `_apply_cash` (cash side), `_apply_position` (position side).
- §0.3 the event currency is the cash currency moved: cash is always keyed on
  `event.currency` (and `bought_amount.currency` for a conversion).
- §1.1 `event_date` governs both legs; `settlement_date` is never read.
- §1.3 negative cash is a valid signed state; never clamped.
- §2.1 (i)-(iv): `_select_live`. A REVERSAL known at L removes its target at
  every D; the reversal's own `event_date` is never read.
- §3.1/§3.2 order `(event_date, rank, ledger_seq)`, rank 0 = SPLIT (start of its
  date), rank 1 = everything else: `_sort_key`.
- §3.3 only end-of-day states are validated: `_end_of_day_check`.
- §4 dividends: cash credit only; no entitlement check against holdings.
- §5/§5A `INTEREST_CHARGED` debits cash; `CURRENCY_CONVERSION` moves two cash keys
  and stores/computes no rate.
- §6 transfers: cash form moves cash; security form moves units. Basis on an
  internal in-leg is carried per Ruling 0.4.5 (see "Basis" below).
- §6.4 unknown basis stays unknown, never zero: `MISSING_COST_BASIS` / `ReplayDetail.UNKNOWN_BASIS`.
- §7 split: exact rational arithmetic. Integral result -> applied. Any other result
  -> the position is UNRESOLVED from that date on; nothing is rounded or truncated.
- 3.4 (1.3) two or more live SPLITs of one position on one date, with units held at the
  start of that day: none applied; quantity and basis `LEDGER_INCONSISTENT` (detail
  `MULTIPLE_SAME_DAY_SPLITS`) from that date, sticky, out-legs inherit it. With no units
  held at the start of the day nothing is flagged. Independent of `ledger_seq`.
- §8 snapshot horizon: an account with live `OPENING_*` events is
  `NOT_RECONSTRUCTABLE` for `D < S`, which is different from an empty state.
- §9 negative end-of-day quantity: inconsistency; no quantity presented; the
  cash effect stays; sticky from that date on.

Basis (ledger-replay/1.2 and 1.3, Ruling 0.4) and the Quant boundary (PD-0021 §9)
--------------------------------------------------------------------------
No depletion METHOD is chosen. Replay computes remaining or carried basis only where
every admissible method agrees, and reports the rest as unresolved:
- 0.4.1 lots: `_Lot` = units + exact `Fraction` unit cost + basis currency, or unknown
  basis. A split rescales lots (`_Lot.rescaled`, `_Position.apply_split`).
- 0.4.2/0.4.3/R2: basis is resolved per DAY at end of day (`_resolve_position`) from the
  candidate set (start-of-day lots + every same-day acquisition, whatever its
  `ledger_seq`). Case 1 no depletion: sum. Case 2 the position ends the day at exactly
  0: lots emptied, unresolved status cleared. Case 3 exactly one candidate lot:
  remaining = c x (U - q_dep) (unknown stays unknown, R3). Case 4 otherwise:
  `UNRESOLVED_CONVENTION` / `LOT_DEPLETION`, sticky until a day ends at 0.
- 0.4.4: stop conditions are exactly "two or more candidate lots after a depletion"
  (a, a', a'', b), a non-integral split (e), a negative quantity (f) and a same-day
  acquisition plus depletion with units held (g); (b') single unknown lot, (c) split
  between acquisition and depletion, (d) partial single-lot transfer stay determinate.
- 0.4.5/R5: internal security pairs are matched per day (`_pair_transfers`) and resolved
  at the out-leg's date after the source's candidate set is known, sources before
  receivers (`_resolve_day`). Decided by the source's same-day candidate set, not by
  whether it ends the day at 0 (1.3, R7): one candidate lot -> every out-leg carries
  c x q; several lots -> lots carried intact only for a sole whole move, else unresolved.
  A flagged source hands its OWN reason and detail to the receiver (1.3, R9); the
  receiver's quantity is always its recorded in-leg quantity.
- 0.4.6/R4: unit costs are `Fraction`s, never rounded. A basis emitted AVAILABLE only if
  it terminates at the reported date (`_to_decimal`), else INSUFFICIENT_DATA with
  reason `UNRESOLVED_CONVENTION` and detail `BASIS_NOT_EXACT` (missing piece: a money
  rounding convention, OI-8). Never an exception; the Inexact trap is not on this path.
- 0.4.8: no unit basis is emitted.
- Fee capitalization: FEE/TAX never touch basis (note 1 of §0.2).
- Fractional split convention: see §7 above.
- Return denominators: not present at all.

Sufficiency state (PD-0025). Every value that can be insufficient is a
`product_contract.metric_state.MetricResult` (value `Decimal` or None). Only
`AVAILABLE` and `INSUFFICIENT_DATA` are used; `LIMITED` is not, because "partially
known basis" is a CP3 ruling (§6.4). Situations map to reason codes:
UNRESOLVED_CONVENTION (lot depletion, fractional split), LEDGER_INCONSISTENT
(negative quantity), NOT_RECONSTRUCTABLE (before a snapshot), MISSING_COST_BASIS
(unknown basis). A value can have several situations at once; the reason code is
the highest-priority one (`_REASON_PRIORITY`) and ALL of them are kept in the
separate, non-state `ReplayDetail` field (`quantity_detail`, `basis_detail`), which
also says WHICH convention is unresolved.

Output shape (OI-5; fixed so two runs are byte-identical, T10)
--------------------------------------------------------------
- `ReplayedState.accounts`: one `AccountState` per account that has at least one
  live event with `ledger_seq <= L` (live = not reversed as of L), sorted by
  `account_id` (UUID integer value), regardless of `as_of`. An account whose
  events all lie after `as_of` is present with empty positions and cash.
- `AccountState.positions`: sorted by `listing_id`. A position is emitted iff its
  quantity is non-zero OR it is UNRESOLVED/INCONSISTENT (a flagged position is
  never omitted, since omission would read as "held nothing"). Fully closed
  positions are NOT emitted.
- `AccountState.cash`: sorted by currency code. Only NON-ZERO balances are emitted.
  Absent means zero on a reconstructed account. Use the accessors on
  `ReplayedState`, which distinguish zero from not-reconstructable.
- A `NOT_RECONSTRUCTABLE` account has status `NOT_RECONSTRUCTABLE`, its
  `snapshot_date`, and empty tuples (empty is meaningless there; the status is
  authoritative).
- Decimals are canonicalised (no exponent, no trailing zeros) so the same numeric
  state has one representation; `ReplayedState.canonical_json()` is the
  byte-identical serialisation.
- All arithmetic (quantities, cash, unit costs) is exact `Fraction`: nothing is ever
  rounded and the global decimal context is never read. Conversion to `Decimal` at the
  output is exact or a STATE: a value that cannot be written exactly in the private
  200-digit context (or a basis that does not terminate) is `INSUFFICIENT_DATA`, never an
  exception and never a number (C1C-6). Reason code `CALCULATION_ERROR`
  (detail `VALUE_NOT_REPRESENTABLE`) for a too-large value, `UNRESOLVED_CONVENTION`
  (detail `BASIS_NOT_EXACT`) for a non-terminating basis. The damage is scoped to the
  one `(account, currency)` cash balance, one position quantity, or one position basis.
"""

from __future__ import annotations

import dataclasses
import datetime
import decimal
import itertools
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from domain.currency import CurrencyCode, Money
from domain.ledger import EventType, LedgerEvent
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState

# R6: an ID is claimed only when every ruling it adds is implemented below. 1.2 added the
# per-lot model (R1), per-day judgement (R2) and exact rationals with non-terminating basis
# as a state (R4); 1.3 adds carried basis from the source's candidate set (R7), Ruling 3.4
# same-day split pairs (R8) and the source's own cause across transfers (R9).
CONVENTION_SET_ID = "ledger-replay/1.3"


class ReplayInputError(ValueError):
    """The events handed to `reconstruct` violate an assumption the ledger
    guarantees (duplicate sequence, several snapshot dates, an event inside a
    snapshot, a wrong argument type). Replay stops rather than choosing. It is never
    raised for a number that is merely too large or non-terminating (a state, C1C-6)."""


class UnknownAccountError(LookupError):
    """An accessor named an account that has no live event at this ledger version."""


# --- exact arithmetic --------------------------------------------------------

# Private context: never the thread's global one. Inexact is trapped, so a result
# that would need rounding raises instead of being silently rounded.
_CTX = decimal.Context(
    prec=200,
    rounding=decimal.ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow,
           decimal.Inexact],
)


def canonical_decimal(value: Decimal) -> Decimal:
    """One representation per numeric value: no exponent form, no trailing zeros,
    no negative zero. Exact (never rounds)."""
    if value == 0:
        return Decimal(0)
    try:
        return Decimal(format(_CTX.normalize(value), "f"))
    except decimal.DecimalException as exc:
        raise ReplayInputError(f"cannot canonicalise {value!r}: {exc!r}") from exc


# --- vocabulary local to replay ---------------------------------------------


@unique
class ReplayDetail(Enum):
    """WHICH situation blocks a value. NOT a sufficiency state and NOT a reason
    code: the state and reason code live on the `MetricResult` (PD-0025); this
    only preserves detail the reason code does not, chiefly which convention is
    unresolved. Listed in a fixed order (by value) wherever it appears."""

    BEFORE_SNAPSHOT = "BEFORE_SNAPSHOT"  # §8 -> NOT_RECONSTRUCTABLE
    NEGATIVE_QUANTITY = "NEGATIVE_QUANTITY"  # §9 -> LEDGER_INCONSISTENT
    # Ruling 3.4: two or more live same-day SPLITs on a position holding units -> none applied.
    MULTIPLE_SAME_DAY_SPLITS = "MULTIPLE_SAME_DAY_SPLITS"  # -> LEDGER_INCONSISTENT
    SPLIT_FRACTION = "SPLIT_FRACTION"  # §7 -> UNRESOLVED_CONVENTION
    LOT_DEPLETION = "LOT_DEPLETION"  # 0.4.3 case 4 / 0.4.5 (c) -> UNRESOLVED_CONVENTION
    # 0.4.6: the exact basis does not terminate at this date. The missing piece is a money
    # rounding convention (OI-8), so the reason code is UNRESOLVED_CONVENTION.
    BASIS_NOT_EXACT = "BASIS_NOT_EXACT"
    # C1C-6: an exact value that is too large to write in the replay's exact-Decimal context
    # (more than 200 significant digits). Reason code CALCULATION_ERROR ("cannot be properly
    # computed"): a limit of this engine's exact arithmetic, not of the data's meaning.
    VALUE_NOT_REPRESENTABLE = "VALUE_NOT_REPRESENTABLE"
    UNKNOWN_BASIS = "UNKNOWN_BASIS"  # §6.4 -> MISSING_COST_BASIS


# Highest priority first: the single reason code shown when several details apply.
_REASON_PRIORITY: Tuple[Tuple[ReplayDetail, ReasonCode], ...] = (
    (ReplayDetail.BEFORE_SNAPSHOT, ReasonCode.NOT_RECONSTRUCTABLE),
    (ReplayDetail.NEGATIVE_QUANTITY, ReasonCode.LEDGER_INCONSISTENT),
    (ReplayDetail.MULTIPLE_SAME_DAY_SPLITS, ReasonCode.LEDGER_INCONSISTENT),
    (ReplayDetail.SPLIT_FRACTION, ReasonCode.UNRESOLVED_CONVENTION),
    (ReplayDetail.LOT_DEPLETION, ReasonCode.UNRESOLVED_CONVENTION),
    (ReplayDetail.BASIS_NOT_EXACT, ReasonCode.UNRESOLVED_CONVENTION),
    (ReplayDetail.VALUE_NOT_REPRESENTABLE, ReasonCode.CALCULATION_ERROR),
    (ReplayDetail.UNKNOWN_BASIS, ReasonCode.MISSING_COST_BASIS),
)


def _sorted_details(details: Iterable[ReplayDetail]) -> Tuple[ReplayDetail, ...]:
    return tuple(sorted(set(details), key=lambda x: x.value))


def _insufficient(details: Iterable[ReplayDetail]) -> MetricResult:
    """INSUFFICIENT_DATA, no value, reason code = highest-priority detail."""
    found = set(details)
    if not found:
        raise ValueError("an insufficient result needs at least one detail")
    for detail, reason in _REASON_PRIORITY:
        if detail in found:
            return MetricResult(None, SufficiencyState.INSUFFICIENT_DATA, reason)
    raise ValueError("unmapped detail")  # pragma: no cover


def _available(value: Decimal) -> MetricResult:
    return MetricResult(canonical_decimal(value), SufficiencyState.AVAILABLE)


def _to_decimal(value: Fraction) -> Tuple[Optional[Decimal], Optional[ReplayDetail]]:
    """The exact Decimal of `value`, or (None, why). Never rounds, never raises.
    A denominator with a prime factor other than 2 or 5 does not terminate
    (`BASIS_NOT_EXACT`: the missing piece is a money-rounding convention, OI-8); a
    terminating value with more digits than the exact context holds is
    `VALUE_NOT_REPRESENTABLE`."""
    rest = value.denominator
    twos = fives = 0
    while rest % 2 == 0:
        rest //= 2
        twos += 1
    while rest % 5 == 0:
        rest //= 5
        fives += 1
    if rest != 1:
        return None, ReplayDetail.BASIS_NOT_EXACT
    k = max(twos, fives)
    scaled = value.numerator * (10 ** k // value.denominator)
    try:
        # No int -> str conversion anywhere (CPython caps that at 4,300 digits, R3-1):
        # Decimal(int) and scaleb are exact, and the private context traps Inexact.
        return canonical_decimal(Decimal(scaled).scaleb(-k, _CTX)), None
    except (ReplayInputError, ValueError, ArithmeticError):
        # Whatever the reason, a value that cannot be written exactly is a state (R3-1).
        return None, ReplayDetail.VALUE_NOT_REPRESENTABLE


#: Cheap fail-closed magnitude bound (R3-1). A finite `Decimal` with more than this many
#: coefficient digits, or an exponent of larger absolute value, is not worth exact rational
#: arithmetic (thousands-of-digit reductions dominate the runtime): its key becomes a
#: VALUE_NOT_REPRESENTABLE state without arithmetic. Far beyond any real amount; storage
#: is expected to bound values at append (a CP1-B migration), making this unreachable.
_MAX_DECIMAL_SPAN = 2000


def _too_extreme(value: Decimal) -> bool:
    parts = value.as_tuple()
    exponent = parts.exponent
    return len(parts.digits) > _MAX_DECIMAL_SPAN or (
        isinstance(exponent, int) and abs(exponent) > _MAX_DECIMAL_SPAN
    )


def _available_fraction(value: Fraction) -> MetricResult:
    """AVAILABLE if `value` (a sum of Decimals, hence terminating) is writable, else
    INSUFFICIENT_DATA / CALCULATION_ERROR (VALUE_NOT_REPRESENTABLE)."""
    dec, why = _to_decimal(value)
    if dec is None:
        return _insufficient([why or ReplayDetail.VALUE_NOT_REPRESENTABLE])
    return _available(dec)


@unique
class AccountStatus(Enum):
    RECONSTRUCTED = "RECONSTRUCTED"
    NOT_RECONSTRUCTABLE = "NOT_RECONSTRUCTABLE"


@dataclass(frozen=True)
class SequencedEvent:
    """An event as stored: the domain event plus the storage-assigned
    `ledger_seq` (per-portfolio, commit-ordered, gappy; Tech Plan §14.2)."""

    ledger_seq: int
    event: LedgerEvent

    def __post_init__(self) -> None:
        if isinstance(self.ledger_seq, bool) or not isinstance(self.ledger_seq, int):
            raise ReplayInputError(f"ledger_seq must be an int, got {self.ledger_seq!r}")
        if self.ledger_seq < 1:
            raise ReplayInputError(f"ledger_seq must be >= 1, got {self.ledger_seq}")
        if not isinstance(self.event, LedgerEvent):
            raise ReplayInputError(f"event must be a LedgerEvent, got {type(self.event)!r}")


@dataclass(frozen=True)
class BasisAmount:
    """Total cost basis in one currency. A presented value always has its currency. When
    the basis is not presented for ANY reason (unknown, unresolved, inconsistent, not
    exactly representable, ...) the position has exactly one entry with no value and
    `currency` None: an AVAILABLE entry is never emitted beside an insufficient one
    (C1C-4). Units acquired in different currencies keep separate AVAILABLE entries,
    never summed."""

    currency: Optional[CurrencyCode]
    result: MetricResult

    def __post_init__(self) -> None:
        if self.result.value is not None and self.currency is None:
            raise ValueError("a presented basis value needs its currency")


@dataclass(frozen=True)
class PositionState:
    """Account-level position in one listing.

    `quantity` and every `cost_basis[i].result` are `MetricResult`s. `cost_basis`
    is sorted by currency code and is never empty: either one `BasisAmount` per
    basis currency (all AVAILABLE) or exactly one with no value (INSUFFICIENT_DATA).
    `quantity_detail` / `basis_detail` are non-state details (see `ReplayDetail`),
    empty when the result is AVAILABLE."""

    account_id: uuid.UUID
    listing_id: uuid.UUID
    quantity: MetricResult
    cost_basis: Tuple[BasisAmount, ...]
    quantity_detail: Tuple[ReplayDetail, ...] = ()
    basis_detail: Tuple[ReplayDetail, ...] = ()


@dataclass(frozen=True)
class CashBalance:
    """A signed, non-zero native-currency balance for `(account, currency)`."""

    account_id: uuid.UUID
    balance: Money


@dataclass(frozen=True)
class AccountState:
    account_id: uuid.UUID
    status: AccountStatus
    snapshot_date: Optional[datetime.date]
    positions: Tuple[PositionState, ...]
    cash: Tuple[CashBalance, ...]
    # C1C-6: currencies whose balance is too large to write exactly (VALUE_NOT_REPRESENTABLE).
    unrepresentable_cash: Tuple[CurrencyCode, ...] = ()

    @property
    def has_inconsistency(self) -> bool:
        """§9: the account contains at least one negative-quantity position."""
        return any(
            p.quantity.reason_code is ReasonCode.LEDGER_INCONSISTENT
            or ReplayDetail.NEGATIVE_QUANTITY in p.quantity_detail
            for p in self.positions
        )


@dataclass(frozen=True)
class ReplayedState:
    convention_set: str
    as_of: datetime.date
    ledger_version: int
    accounts: Tuple[AccountState, ...]

    # -- lookups -------------------------------------------------------------

    def account(self, account_id: uuid.UUID) -> AccountState:
        for state in self.accounts:
            if state.account_id == account_id:
                return state
        raise UnknownAccountError(f"account {account_id} has no live event at L={self.ledger_version}")

    def position_quantity(self, account_id: uuid.UUID, listing_id: uuid.UUID) -> MetricResult:
        """Zero (AVAILABLE) for a reconstructed account that holds nothing;
        NOT_RECONSTRUCTABLE (no value) for a not-reconstructable account."""
        state = self.account(account_id)
        if state.status is AccountStatus.NOT_RECONSTRUCTABLE:
            return _insufficient([ReplayDetail.BEFORE_SNAPSHOT])
        for position in state.positions:
            if position.listing_id == listing_id:
                return position.quantity
        return _available(Decimal(0))

    def position_basis(
        self, account_id: uuid.UUID, listing_id: uuid.UUID
    ) -> Tuple[BasisAmount, ...]:
        """The position's `cost_basis` entries; `()` for a reconstructed account
        holding nothing; one no-value NOT_RECONSTRUCTABLE entry before a snapshot."""
        state = self.account(account_id)
        if state.status is AccountStatus.NOT_RECONSTRUCTABLE:
            return (BasisAmount(None, _insufficient([ReplayDetail.BEFORE_SNAPSHOT])),)
        for position in state.positions:
            if position.listing_id == listing_id:
                return position.cost_basis
        return ()

    def cash_balance(self, account_id: uuid.UUID, currency: CurrencyCode) -> MetricResult:
        """The signed balance in `currency` (a Decimal; the currency is the argument)."""
        state = self.account(account_id)
        if state.status is AccountStatus.NOT_RECONSTRUCTABLE:
            return _insufficient([ReplayDetail.BEFORE_SNAPSHOT])
        if currency in state.unrepresentable_cash:
            return _insufficient([ReplayDetail.VALUE_NOT_REPRESENTABLE])
        for entry in state.cash:
            if entry.balance.currency == currency:
                return _available(entry.balance.amount)
        return _available(Decimal(0))

    # -- portfolio-level sums: one key dimension only (§0.1) -----------------

    def portfolio_cash(self, currency: CurrencyCode) -> MetricResult:
        """Sum of one currency's balances over accounts (a Decimal in `currency`).
        NOT_RECONSTRUCTABLE if any account is not reconstructable; CALCULATION_ERROR if a
        balance (or the exact sum) is too large to write. Never sums across currencies."""
        total = Fraction(0)
        for state in self.accounts:
            if state.status is AccountStatus.NOT_RECONSTRUCTABLE:
                return _insufficient([ReplayDetail.BEFORE_SNAPSHOT])
            if currency in state.unrepresentable_cash:
                return _insufficient([ReplayDetail.VALUE_NOT_REPRESENTABLE])
            for entry in state.cash:
                if entry.balance.currency == currency:
                    total += Fraction(entry.balance.amount)
        return _available_fraction(total)

    def portfolio_cash_currencies(self) -> Tuple[CurrencyCode, ...]:
        found = {e.balance.currency for a in self.accounts for e in a.cash}
        found.update(c for a in self.accounts for c in a.unrepresentable_cash)
        return tuple(sorted(found, key=lambda c: c.code))

    def portfolio_position_quantity(self, listing_id: uuid.UUID) -> MetricResult:
        """Sum over accounts for one listing (listings are never merged, §0.1).
        INSUFFICIENT if any account is not reconstructable or holds the listing
        in a flagged state; the details are unioned."""
        total = Fraction(0)
        details: Set[ReplayDetail] = set()
        for state in self.accounts:
            if state.status is AccountStatus.NOT_RECONSTRUCTABLE:
                details.add(ReplayDetail.BEFORE_SNAPSHOT)
                continue
            for position in state.positions:
                if position.listing_id != listing_id:
                    continue
                if position.quantity.value is None:
                    details.update(position.quantity_detail)
                else:
                    total += Fraction(position.quantity.value)
        if details:
            return _insufficient(details)
        return _available_fraction(total)

    # -- serialisation --------------------------------------------------------

    def to_canonical_dict(self) -> Dict[str, Any]:
        def dec(d: Decimal) -> str:
            return format(canonical_decimal(d), "f")

        def stated(result: MetricResult, detail: Tuple[ReplayDetail, ...]) -> Dict[str, Any]:
            return {
                "value": None if result.value is None else dec(result.value),
                "state": result.sufficiency_state.value,
                "reason": None if result.reason_code is None else result.reason_code.value,
                "detail": [x.value for x in detail],
            }

        def basis(p: PositionState) -> List[Dict[str, Any]]:
            out = []
            for entry in p.cost_basis:
                item = stated(entry.result, p.basis_detail)
                item["currency"] = None if entry.currency is None else entry.currency.code
                out.append(item)
            return out

        return {
            "convention_set": self.convention_set,
            "as_of": self.as_of.isoformat(),
            "ledger_version": self.ledger_version,
            "accounts": [
                {
                    "account_id": str(a.account_id),
                    "status": a.status.value,
                    "snapshot_date": None if a.snapshot_date is None else a.snapshot_date.isoformat(),
                    "positions": [
                        {
                            "listing_id": str(p.listing_id),
                            "quantity": stated(p.quantity, p.quantity_detail),
                            "cost_basis": basis(p),
                        }
                        for p in a.positions
                    ],
                    "cash": [
                        {"currency": c.balance.currency.code, "amount": dec(c.balance.amount)}
                        for c in a.cash
                    ],
                    "unrepresentable_cash": [c.code for c in a.unrepresentable_cash],
                }
                for a in self.accounts
            ],
        }

    def canonical_json(self) -> str:
        """Byte-identical for equal states (sorted keys, fixed separators, ASCII)."""
        return json.dumps(
            self.to_canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )


# --- the fold ----------------------------------------------------------------

_OPENING = (EventType.OPENING_POSITION, EventType.OPENING_CASH)
_POSITION_EVENTS = (
    EventType.BUY, EventType.SELL, EventType.SPLIT, EventType.OPENING_POSITION,
    EventType.TRANSFER_IN, EventType.TRANSFER_OUT,
)


def _rank(event: LedgerEvent) -> int:
    return 0 if event.event_type is EventType.SPLIT else 1


def _sort_key(item: SequencedEvent) -> Tuple[datetime.date, int, int]:
    """§3.1: `(event_date ASC, rank ASC, ledger_seq ASC)`."""
    return (item.event.event_date, _rank(item.event), item.ledger_seq)


@dataclass(frozen=True)
class _Lot:
    """0.4.1: `units` and an exact rational unit cost in one basis currency, or an
    unknown basis (`cost is None`, `currency is None`). Never a rounded decimal."""

    units: Fraction
    cost: Optional[Fraction]
    currency: Optional[CurrencyCode]
    # ledger-replay/1.4 Ruling 0.5.1 (FIFO/1 mode only; the `none` mode never sets or reads them, so its output is byte-identical):
    acq: Optional[datetime.date] = None  # the acquisition date `a` (1.5: `acquired_on` for a RECORDED lot)
    kind: Optional[str] = None  # DATE_TRADE / DATE_ENTRY / DATE_RECORDED
    origin: Optional[uuid.UUID] = None  # the acquiring event
    origin_type: Optional[str] = None
    hops: Tuple["Hop", ...] = ()  # the carry history

    def rescaled(self, new_units: Fraction, old_units: Fraction) -> "_Lot":
        """A split rescales the lot: units x n/o, unit cost x o/n; total basis unchanged. Every other attribute is unchanged (0.5.7)."""
        cost = None if self.cost is None else self.cost * old_units / new_units
        return dataclasses.replace(self, units=self.units * new_units / old_units, cost=cost)


def _lot_from_basis(quantity: Decimal, basis: Optional[Money]) -> _Lot:
    units = Fraction(quantity)
    if basis is None:
        return _Lot(units, None, None)
    return _Lot(units, Fraction(basis.amount) / units, basis.currency)


class _Carry:
    """What an internal out-leg hands to its in-leg (0.4.5). When `unresolved`, `causes`
    is the SOURCE's true cause (C1C-5), so the receiver reports why, not "lot depletion"."""

    __slots__ = ("lots", "unresolved", "causes")

    def __init__(self, lots: List[_Lot], unresolved: bool, causes: Iterable[ReplayDetail] = ()) -> None:
        self.lots = lots
        self.unresolved = unresolved
        self.causes = frozenset(causes)


class _Position:
    __slots__ = ("qty", "unresolved_split", "inconsistent", "multi_split", "poisoned", "lots",
                 "unresolved_depletion",
                 "unresolved_causes", "unknown_flag", "acq", "carry_in", "dep", "out_legs", "fifo_deps")

    def __init__(self) -> None:
        self.qty = Fraction(0)  # running quantity, exact rational (C1C-6: no width limit)
        self.unresolved_split = False  # sticky (§7)
        self.poisoned = False  # sticky: an extreme magnitude (R3-1), nothing tracked afterwards
        self.inconsistent = False  # sticky (§9)
        self.multi_split = False  # sticky (Ruling 3.4): several same-day splits, none applied
        # Lots at the end of the previous day (0.4.1). Empty while `unresolved_depletion`.
        self.lots: List[_Lot] = []
        # Total basis unresolved, sticky until a day ends at exactly 0 (0.4.3 case 4), and
        # WHY (LOT_DEPLETION, or a cause inherited across an internal transfer, C1C-5).
        self.unresolved_depletion = False
        self.unresolved_causes: Set[ReplayDetail] = set()
        self.unknown_flag = False  # some unknown-basis lot is inside an unresolved position
        # Same-day accumulators (0.4.2), consumed by `_resolve_position` at end of day.
        self.acq: List[_Lot] = []
        self.carry_in: List[uuid.UUID] = []  # internal in-leg event ids
        self.dep = Fraction(0)  # total units removed by the day's depleting events
        self.out_legs: List[Tuple[uuid.UUID, Fraction]] = []  # internal out-legs (id, q)
        # FIFO/1 only (0.5.5): every depleting event of the day, (event_id, units, event type, is an internal out-leg), in the order applied.
        self.fifo_deps: List[Tuple[uuid.UUID, Fraction, EventType, bool]] = []

    def clear_day(self) -> None:
        self.acq = []
        self.carry_in = []
        self.dep = Fraction(0)
        self.out_legs = []
        self.fifo_deps = []

    def reset_basis(self) -> None:
        """0.4.3 case 2: nothing remains; earlier unresolved status is cleared."""
        self.lots = []
        self.unresolved_depletion = False
        self.unresolved_causes = set()
        self.unknown_flag = False

    def apply_split(self, new_units: Decimal, old_units: Decimal) -> None:
        if self.unresolved_split or self.poisoned:
            return
        if _too_extreme(new_units) or _too_extreme(old_units):
            self.poisoned = True
            self.lots = []
            return
        n, o = Fraction(new_units), Fraction(old_units)
        exact = self.qty * n / o
        if exact.denominator == 1:
            self.qty = exact
            self.lots = [lot.rescaled(n, o) for lot in self.lots]
        else:
            # §7 condition 2: no rounding, no truncation, no cash in lieu.
            self.unresolved_split = True
            self.lots = []


def _make_unresolved(position: _Position, extra: List[_Lot], causes: Iterable[ReplayDetail]) -> None:
    """0.4.3 case 4: the total basis is unresolved (sticky). Remember whether an
    unknown-basis lot is involved (so both causes can be reported, 0.4.4 (b)) and the
    cause of the unresolved status."""
    if any(lot.cost is None for lot in position.lots + extra):
        position.unknown_flag = True
    position.lots = []
    position.unresolved_depletion = True
    position.unresolved_causes |= set(causes)


def _pair_transfers(
    events: List[LedgerEvent], by_event_id: bool = False,
) -> Tuple[Dict[uuid.UUID, uuid.UUID], Dict[uuid.UUID, Tuple[uuid.UUID, uuid.UUID]]]:
    """Ruling 6.2 matching of the day's internal security legs, in `ledger_seq` order:
    reciprocal accounts, same listing, quantity and currency (the date is the day).
    Returns (out_leg_id -> in_leg_id, in_leg_id -> source (account, listing)).
    `by_event_id` (FIFO/1, ledger-replay/1.4 0.5.6, B4): legs are matched in ASCENDING `event_id` order (UUID integer) instead, so the in-leg id a lot's hop
    records does not depend on entry order. Values never depend on the pairing (0.4.5), so the `none` mode keeps `ledger_seq` order."""
    outs = [e for e in events if e.event_type is EventType.TRANSFER_OUT
            and e.counterparty_account_id is not None and e.listing_id is not None]
    ins = [e for e in events if e.event_type is EventType.TRANSFER_IN
           and e.counterparty_account_id is not None and e.listing_id is not None]
    if by_event_id:
        outs.sort(key=lambda e: e.event_id.int)
        ins.sort(key=lambda e: e.event_id.int)
    used: Set[uuid.UUID] = set()
    out_to_in: Dict[uuid.UUID, uuid.UUID] = {}
    in_to_src: Dict[uuid.UUID, Tuple[uuid.UUID, uuid.UUID]] = {}
    for out in outs:
        for leg in ins:
            if leg.event_id in used:
                continue
            if (leg.account_id == out.counterparty_account_id
                    and leg.counterparty_account_id == out.account_id
                    and leg.listing_id == out.listing_id
                    and leg.quantity == out.quantity
                    and leg.currency == out.currency):
                used.add(leg.event_id)
                out_to_in[out.event_id] = leg.event_id
                assert out.listing_id is not None
                in_to_src[leg.event_id] = (out.account_id, out.listing_id)
                break
    return out_to_in, in_to_src


def _resolve_day(
    positions: Dict[Tuple[uuid.UUID, uuid.UUID], "_Position"],
    keys: Set[Tuple[uuid.UUID, uuid.UUID]],
    out_to_in: Dict[uuid.UUID, uuid.UUID],
    in_to_src: Dict[uuid.UUID, Tuple[uuid.UUID, uuid.UUID]],
    fifo: Optional["_FifoCtx"] = None,
    day: Optional[datetime.date] = None,
) -> None:
    """End-of-day basis resolution (0.4.2-0.4.5, R2, R5). A position is resolved only
    after every source of an internal in-leg it received today (transitive, sorted,
    deterministic). A same-day cycle is broken by resolving the first key; its missing
    carried basis is then unresolved. With `fifo` the FIFO/1 resolution (0.5) runs instead."""
    carried: Dict[uuid.UUID, _Carry] = {}
    pending = sorted(keys, key=lambda k: (k[0].int, k[1].int))
    while pending:
        pick = next(
            (k for k in pending
             if all(in_to_src.get(i) not in pending for i in positions[k].carry_in)),
            pending[0],
        )
        pending.remove(pick)
        if fifo is None:
            _resolve_position(positions[pick], carried, out_to_in)
        else:
            assert day is not None
            _resolve_position_fifo(positions[pick], pick, day, carried, out_to_in, fifo)


def _resolve_position(
    p: "_Position", carried: Dict[uuid.UUID, _Carry], out_to_in: Dict[uuid.UUID, uuid.UUID]
) -> None:
    incoming_unresolved = False
    incoming_causes: Set[ReplayDetail] = set()
    incoming_lots: List[_Lot] = []
    for in_id in p.carry_in:
        got = carried.get(in_id)
        if got is None:
            # No resolvable source (unmatched leg, or a same-day cycle): which lots moved is
            # not knowable, which is a lot-selection question.
            incoming_unresolved = True
            incoming_causes.add(ReplayDetail.LOT_DEPLETION)
        elif got.unresolved:
            incoming_unresolved = True
            incoming_causes |= got.causes  # the source's true cause (C1C-5)
        else:
            incoming_lots.extend(got.lots)
    acquired = p.acq + incoming_lots  # 0.4.2: every same-day acquisition, whatever its seq
    q_dep = p.dep
    out_legs = list(p.out_legs)

    def give(leg_lots: Optional[List[_Lot]], out_id: uuid.UUID,
             causes: Iterable[ReplayDetail] = ()) -> None:
        dest = out_to_in.get(out_id)
        if dest is not None:
            carried[dest] = _Carry([] if leg_lots is None else leg_lots, leg_lots is None, causes)

    def give_all_unresolved(causes: Iterable[ReplayDetail]) -> None:
        for out_id, _q in out_legs:
            give(None, out_id, causes)

    lot_selection = {ReplayDetail.LOT_DEPLETION}
    try:
        if p.qty < 0:
            p.inconsistent = True  # §9, judged at end of day only
        if p.unresolved_split or p.inconsistent or p.multi_split or p.poisoned:
            dead: Set[ReplayDetail] = set()  # 0.4.5 (c): inherit the source's own cause
            if p.poisoned:
                dead.add(ReplayDetail.VALUE_NOT_REPRESENTABLE)
            if p.unresolved_split:
                dead.add(ReplayDetail.SPLIT_FRACTION)
            if p.inconsistent:
                dead.add(ReplayDetail.NEGATIVE_QUANTITY)
            if p.multi_split:
                dead.add(ReplayDetail.MULTIPLE_SAME_DAY_SPLITS)
            give_all_unresolved(dead)
            return
        base_unresolved = p.unresolved_depletion or incoming_unresolved
        status_causes = p.unresolved_causes | incoming_causes
        if p.qty == 0 and q_dep > 0:
            # 0.4.3 case 2: the position ends the day at exactly 0; 0.4.5 decides what each
            # internal out-leg carries. Nothing is "lot selection" when every unit leaves.
            candidates = p.lots + acquired
            if base_unresolved:
                give_all_unresolved(status_causes)
            elif len(out_legs) == 1 and q_dep == out_legs[0][1]:
                give(list(candidates), out_legs[0][0])  # (a) whole move: every lot intact
            elif len(candidates) == 1:
                lot = candidates[0]  # (b) partial moves out of one lot, whatever else leaves
                for out_id, q in out_legs:
                    give([_Lot(q, lot.cost, lot.currency)], out_id)
            else:
                give_all_unresolved(lot_selection)  # (c)
            p.reset_basis()
        elif q_dep == 0:
            # 0.4.3 case 1: no depletion today; total = sum of lots.
            if base_unresolved:
                _make_unresolved(p, acquired, status_causes)
            else:
                p.lots = p.lots + acquired
        else:
            # 0 < q_dep < U
            if base_unresolved:
                _make_unresolved(p, acquired, status_causes)
                give_all_unresolved(status_causes)
            else:
                candidates = p.lots + acquired
                if len(candidates) == 1 and candidates[0].units > q_dep:
                    lot = candidates[0]  # 0.4.3 case 3 / 0.4.5 (b)
                    p.lots = [_Lot(lot.units - q_dep, lot.cost, lot.currency)]
                    for out_id, q in out_legs:
                        give([_Lot(q, lot.cost, lot.currency)], out_id)
                else:
                    _make_unresolved(p, candidates, lot_selection)  # 0.4.3 case 4 / 0.4.5 (c)
                    give_all_unresolved(lot_selection)
    finally:
        p.clear_day()


# --- the FIFO/1 mode of the one lot fold (ledger-replay/1.4 Ruling 0.5; 1.5 Ruling 0.6) --------------------------------------------------------------------------

#: A state of the FIFO mode cites ledger-replay/1.5 and the lot method FIFO/1 (B7); the `none` mode's `CONVENTION_SET_ID` stays ledger-replay/1.3.
FIFO_CONVENTION_SET_ID = "ledger-replay/1.5"
LOT_METHOD_ID = "FIFO/1"

#: The date kinds of a lot (0.5.1, 0.6.1). TRADE: `a` is the date the units were bought (a BUY). ENTRY: only the date the units entered this portfolio. RECORDED: the
#: date the USER says the units were acquired (`acquired_on`).
DATE_TRADE, DATE_ENTRY, DATE_RECORDED = "TRADE", "ENTRY", "RECORDED"


@dataclass(frozen=True)
class Hop:
    """One internal move in a lot's carry history (0.5.1): the source position's account (and listing), the out-leg and in-leg event ids, and the date `T`."""

    source_account_id: uuid.UUID
    listing_id: uuid.UUID
    out_event_id: uuid.UUID
    in_event_id: uuid.UUID
    date: datetime.date


@dataclass(frozen=True)
class Lot:
    """A lot or a relieved portion of one, with every 0.5.14 attribute. `basis_currency`, `unit_cost` and `basis` are None for an unknown basis. Exact rationals.
    Identity (0.5.1) is (origin event id, the out-leg ids of its hops, in order)."""

    origin_event_id: uuid.UUID
    origin_event_type: str
    hops: Tuple[Hop, ...]
    acquisition_date: datetime.date
    date_kind: str
    basis_currency: Optional[CurrencyCode]
    units: Fraction
    unit_cost: Optional[Fraction]

    @property
    def basis(self) -> Optional[Fraction]:
        return None if self.unit_cost is None else self.unit_cost * self.units

    @property
    def identity(self) -> Tuple[uuid.UUID, Tuple[uuid.UUID, ...]]:
        return (self.origin_event_id, tuple(h.out_event_id for h in self.hops))

    @property
    def sort_key(self) -> Tuple[datetime.date, int, Tuple[int, ...]]:
        """0.5.14: by (a; origin event id as a UUID integer; hop out-leg ids)."""
        return (self.acquisition_date, self.origin_event_id.int, tuple(h.out_event_id.int for h in self.hops))

    def scaled(self, units: Fraction) -> "Lot":
        return dataclasses.replace(self, units=units)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_event_id": str(self.origin_event_id), "origin_event_type": self.origin_event_type,
            "carry": [{"from_account_id": str(h.source_account_id), "listing_id": str(h.listing_id), "out_event_id": str(h.out_event_id),
                       "in_event_id": str(h.in_event_id), "date": h.date.isoformat()} for h in self.hops],
            "acquisition_date": self.acquisition_date.isoformat(), "date_kind": self.date_kind,
            "basis_currency": None if self.basis_currency is None else self.basis_currency.code,
            "units": _frac_text(self.units), "unit_cost": None if self.unit_cost is None else _frac_text(self.unit_cost),
            "basis": None if self.basis is None else _frac_text(self.basis),
        }


def _frac_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


@dataclass(frozen=True)
class Relief:
    """The relief record of one depleting event (0.5.14 item 2): its share `q_e / q_dep` of every relieved portion. For an internal out-leg these are exactly the lots
    its in-leg delivers, BEFORE the hop is appended. When replay withholds it (0.5.9: a flagged position, an opaque lot, a same-day cycle) `portions` is empty and
    `causes` holds the position's own details."""

    event_id: uuid.UUID
    event_type: str
    event_date: datetime.date
    account_id: uuid.UUID
    listing_id: uuid.UUID
    internal: bool
    portions: Tuple[Lot, ...]
    causes: Tuple[ReplayDetail, ...] = ()

    @property
    def withheld(self) -> bool:
        return bool(self.causes)

    @property
    def has_unknown_basis(self) -> bool:
        return any(p.unit_cost is None for p in self.portions)


@dataclass(frozen=True)
class DayBook:
    """A position's END-OF-DAY lot book on a day on which the position was touched (the input of the taint rule, 0.5.14). `causes` is non-empty when no lot
    book is presented (flagged, opaque, unresolved)."""

    date: datetime.date
    lots: Tuple[Lot, ...]
    causes: Tuple[ReplayDetail, ...] = ()


@dataclass(frozen=True)
class LotBook:
    account_id: uuid.UUID
    listing_id: uuid.UUID
    quantity: Optional[Fraction]
    lots: Tuple[Lot, ...]
    causes: Tuple[ReplayDetail, ...] = ()


@dataclass(frozen=True)
class FifoState:
    """The FIFO/1 replay of `S(D, L)`: the ordinary replayed state (same quantities, cash and flags as the `none` mode; basis emitted per 0.5.11), plus the exact lot
    books, the relief records of every depleting event dated `<= D`, and each touched position's end-of-day books by day."""

    state: ReplayedState
    lot_method: str
    books: Dict[Tuple[uuid.UUID, uuid.UUID], LotBook]
    reliefs: Dict[uuid.UUID, Relief]
    history: Dict[Tuple[uuid.UUID, uuid.UUID], Tuple[DayBook, ...]]
    conservation_failures: Tuple[str, ...] = ()  # identity I-5; non-empty is an engine fault

    def book(self, account_id: uuid.UUID, listing_id: uuid.UUID) -> Optional[LotBook]:
        return self.books.get((account_id, listing_id))

    def relief(self, event_id: uuid.UUID) -> Optional[Relief]:
        return self.reliefs.get(event_id)

    def book_on(self, account_id: uuid.UUID, listing_id: uuid.UUID, day: datetime.date) -> Optional[DayBook]:
        """The position's end-of-day lot book on `day`: the last recorded one dated `<= day`, or None before its first event."""
        found: Optional[DayBook] = None
        for entry in self.history.get((account_id, listing_id), ()):
            if entry.date <= day:
                found = entry
            else:
                break
        return found

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.to_canonical_dict(), "lot_method": self.lot_method,
            "books": [{"account_id": str(k[0]), "listing_id": str(k[1]), "quantity": None if b.quantity is None else _frac_text(b.quantity),
                       "lots": [lot.to_dict() for lot in b.lots], "causes": [c.value for c in b.causes]}
                      for k, b in sorted(self.books.items(), key=lambda kv: (kv[0][0].int, kv[0][1].int))],
            "reliefs": [{"event_id": str(r.event_id), "event_type": r.event_type, "date": r.event_date.isoformat(), "internal": r.internal,
                         "portions": [p.to_dict() for p in r.portions], "causes": [c.value for c in r.causes]}
                        for r in sorted(self.reliefs.values(), key=lambda r: (r.event_date, r.event_id.int))],
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _public(lot: _Lot) -> Lot:
    assert lot.acq is not None and lot.kind is not None and lot.origin is not None and lot.origin_type is not None
    return Lot(lot.origin, lot.origin_type, lot.hops, lot.acq, lot.kind, lot.currency, lot.units, lot.cost)


def _lot_key(lot: _Lot) -> Tuple[datetime.date, int, Tuple[int, ...]]:
    assert lot.acq is not None and lot.origin is not None
    return (lot.acq, lot.origin.int, tuple(h.out_event_id.int for h in lot.hops))


@dataclass
class _FifoCtx:
    """What the FIFO resolution records as the fold runs."""

    reliefs: Dict[uuid.UUID, Relief]
    history: Dict[Tuple[uuid.UUID, uuid.UUID], List[DayBook]]
    conservation_failures: List[str] = dataclasses.field(default_factory=list)  # identity I-5, checked at every relief (a failure is an engine fault)


def reason_code_of(details: Iterable[ReplayDetail]) -> ReasonCode:
    """The reason code replay shows for a set of details (its priority order). Used by CP3 to give a gain the reason of a withheld relief record (performance 3.8 (1.5))."""
    found = set(details)
    for detail, reason in _REASON_PRIORITY:
        if detail in found:
            return reason
    raise ValueError("no details")


def _basis_by_currency(lots: Iterable[_Lot]) -> Tuple[Dict[Optional[CurrencyCode], Fraction], Fraction]:
    """(known basis per basis currency, units): the quantities identity I-5 conserves. An unknown lot counts under the key None (its units, no basis)."""
    out: Dict[Optional[CurrencyCode], Fraction] = {}
    units = Fraction(0)
    for lot in lots:
        units += lot.units
        key = lot.currency if lot.cost is not None else None
        out[key] = out.get(key, Fraction(0)) + (lot.cost * lot.units if lot.cost is not None else Fraction(0))
    return out, units


def _fifo_relieve(candidates: List[_Lot], q_dep: Fraction) -> Tuple[List[_Lot], List[_Lot]]:
    """0.5.4: relieve `q_dep` units from the candidate set. Group by acquisition date, oldest first; relieve whole groups while the need is at least the group's units; the
    first group that is not wholly needed gives each lot `need x u / U_g`. Returns `(relieved portions, remaining lots)`. Depends only on the multiset of lots and their
    dates, never on `ledger_seq`, lot identity order, unit cost, currency or known/unknown basis."""
    ordered = sorted(candidates, key=_lot_key)
    relieved: List[_Lot] = []
    remaining: List[_Lot] = []
    need = q_dep
    for _a, group_iter in itertools.groupby(ordered, key=lambda lot: lot.acq):
        group = list(group_iter)
        if need == 0:
            remaining.extend(group)
            continue
        group_units = sum((lot.units for lot in group), Fraction(0))
        if need >= group_units:
            relieved.extend(group)
            need -= group_units
            continue
        for lot in group:
            part = need * lot.units / group_units
            relieved.append(dataclasses.replace(lot, units=part))
            rest = lot.units - part
            if rest != 0:
                remaining.append(dataclasses.replace(lot, units=rest))
        need = Fraction(0)
    return relieved, remaining


def _resolve_position_fifo(
    p: "_Position", key: Tuple[uuid.UUID, uuid.UUID], day: datetime.date, carried: Dict[uuid.UUID, _Carry],
    out_to_in: Dict[uuid.UUID, uuid.UUID], ctx: _FifoCtx,
) -> None:
    """End-of-day resolution of one position under FIFO/1 (0.5.3 to 0.5.9). The candidate set is the start-of-day lots (rescaled by a split of the day), every lot created
    on the day and every carried lot delivered by an in-leg of the day."""
    account, listing = key
    incoming_unresolved = False
    incoming_causes: Set[ReplayDetail] = set()
    incoming_lots: List[_Lot] = []
    for in_id in p.carry_in:
        got = carried.get(in_id)
        if got is None:
            incoming_unresolved = True  # an unmatched leg or a same-day cycle (0.5.9 (b), (c))
            incoming_causes.add(ReplayDetail.LOT_DEPLETION)
        elif got.unresolved:
            incoming_unresolved = True
            incoming_causes |= got.causes
        else:
            incoming_lots.extend(got.lots)
    acquired = p.acq + incoming_lots
    deps = list(p.fifo_deps)
    q_dep = p.dep
    out_legs = list(p.out_legs)

    def give(leg_lots: Optional[List[_Lot]], out_id: uuid.UUID, causes: Iterable[ReplayDetail] = ()) -> None:
        dest = out_to_in.get(out_id)
        if dest is not None:
            carried[dest] = _Carry([] if leg_lots is None else leg_lots, leg_lots is None, causes)

    def give_all_unresolved(causes: Iterable[ReplayDetail]) -> None:
        for out_id, _q in out_legs:
            give(None, out_id, causes)

    def withhold(causes: Iterable[ReplayDetail]) -> Tuple[ReplayDetail, ...]:
        found = _sorted_details(causes)
        for event_id, _units, kind, internal in deps:
            ctx.reliefs[event_id] = Relief(event_id, kind.value, day, account, listing, internal, (), found)
        return found

    def record(lots: Tuple[_Lot, ...], causes: Tuple[ReplayDetail, ...]) -> None:
        ctx.history.setdefault(key, []).append(DayBook(day, tuple(sorted((_public(lot) for lot in lots), key=lambda x: x.sort_key)), causes))

    try:
        if p.qty < 0:
            p.inconsistent = True  # §9, judged at end of day only
        if p.unresolved_split or p.inconsistent or p.multi_split or p.poisoned:
            dead: Set[ReplayDetail] = set()  # 0.5.9 (a): relieve nothing, present no book, hand on an opaque lot with the position's own cause
            if p.poisoned:
                dead.add(ReplayDetail.VALUE_NOT_REPRESENTABLE)
            if p.unresolved_split:
                dead.add(ReplayDetail.SPLIT_FRACTION)
            if p.inconsistent:
                dead.add(ReplayDetail.NEGATIVE_QUANTITY)
            if p.multi_split:
                dead.add(ReplayDetail.MULTIPLE_SAME_DAY_SPLITS)
            record((), withhold(dead))
            give_all_unresolved(dead)
            return
        base_unresolved = p.unresolved_depletion or incoming_unresolved
        status_causes = p.unresolved_causes | incoming_causes
        if base_unresolved:
            # 0.5.9 (b): a position holding an opaque lot (or a cycle, or an unrepresentable basis) presents no book and relieves nothing, until it ends a day at 0
            found = withhold(status_causes or {ReplayDetail.LOT_DEPLETION})
            give_all_unresolved(status_causes)
            if p.qty == 0 and q_dep > 0:
                p.reset_basis()
                record((), ())
            else:
                _make_unresolved(p, acquired, status_causes)
                record((), found)
            return
        candidates = p.lots + acquired
        if q_dep > 0:
            relieved, remaining = _fifo_relieve(candidates, q_dep)
            # Identity I-5 (lot conservation), exactly: relieved + remaining = the candidate set, in units and in known basis per currency
            before, before_units = _basis_by_currency(candidates)
            after, after_units = _basis_by_currency(relieved + remaining)
            if before != after or before_units != after_units or sum((r.units for r in relieved), Fraction(0)) != q_dep:
                ctx.conservation_failures.append(f"I-5 {account}/{listing} {day.isoformat()}: relieved + remaining differs from the candidate set")
            for event_id, units, kind, internal in deps:
                share = units / q_dep  # 0.5.5: every depleting event takes q_e / q_dep of EVERY relieved portion
                mine = [dataclasses.replace(portion, units=portion.units * share) for portion in relieved]
                ctx.reliefs[event_id] = Relief(event_id, kind.value, day, account, listing, internal, tuple(_public(m) for m in sorted(mine, key=_lot_key)))
                if internal:
                    in_id = out_to_in.get(event_id)
                    if in_id is not None:
                        hop = Hop(account, listing, event_id, in_id, day)
                        give([dataclasses.replace(m, hops=m.hops + (hop,)) for m in mine], event_id)
            p.lots = remaining
        else:
            p.lots = candidates
        if p.qty == 0:
            p.reset_basis()  # 0.5.9 (d): ending a day at exactly 0 empties the book
        record(tuple(p.lots), ())
    finally:
        p.clear_day()


def _select_live(items: List[SequencedEvent], ledger_version: int) -> List[SequencedEvent]:
    """§2.1 (i), (iii), (iv). (ii), the date bound, is applied later."""
    in_version = [i for i in items if i.ledger_seq <= ledger_version]
    reversed_ids = {
        i.event.reverses_event_id for i in in_version if i.event.event_type is EventType.REVERSAL
    }
    return [
        i
        for i in in_version
        if i.event.event_type is not EventType.REVERSAL and i.event.event_id not in reversed_ids
    ]


def live_events(events: Iterable[SequencedEvent], ledger_version: int) -> Tuple[SequencedEvent, ...]:
    """The events that are LIVE at ledger version L: `ledger_seq <= L`, no REVERSAL event itself, and not reversed by a
    reversal known at L (§2.1 (i), (iii), (iv)); the date bound (ii) is not applied. The same code `reconstruct` uses
    (`_select_live`), exposed so that every reader of the ledger agrees with replay about which events count (CP3a;
    PM-approved, additive: no convention changes). Returned in `ledger_seq` order."""
    if isinstance(ledger_version, bool) or not isinstance(ledger_version, int) or ledger_version < 0:
        raise ReplayInputError(f"ledger_version must be an int >= 0, got {ledger_version!r}")
    items = list(events)
    for item in items:
        if not isinstance(item, SequencedEvent):
            raise ReplayInputError(f"events must be SequencedEvent, got {type(item)!r}")
    return tuple(sorted(_select_live(items, ledger_version), key=lambda i: i.ledger_seq))


def _snapshot_dates(live: List[SequencedEvent]) -> Dict[uuid.UUID, datetime.date]:
    """§8: one snapshot date per account, validated against the account's other
    events (the persistence layer enforces this; replay refuses to guess if it is
    ever violated)."""
    dates: Dict[uuid.UUID, Set[datetime.date]] = {}
    for item in live:
        if item.event.event_type in _OPENING:
            dates.setdefault(item.event.account_id, set()).add(item.event.event_date)
    result: Dict[uuid.UUID, datetime.date] = {}
    for account_id, found in dates.items():
        if len(found) != 1:
            raise ReplayInputError(
                f"account {account_id} has OPENING events on several dates: {sorted(found)}"
            )
        result[account_id] = next(iter(found))
    for item in live:
        event = item.event
        snap = result.get(event.account_id)
        if snap is None or event.event_type in _OPENING:
            continue
        allowed = event.event_date > snap or (
            event.event_type is EventType.SPLIT and event.event_date == snap
        )
        if not allowed:
            raise ReplayInputError(
                f"event {event.event_id} ({event.event_type.value}) dated {event.event_date} lies "
                f"inside the snapshot dated {snap} of account {event.account_id}"
            )
    return result


def reconstruct(
    events: Iterable[SequencedEvent], as_of: datetime.date, ledger_version: int
) -> ReplayedState:
    """The replayed state `S(as_of, ledger_version)` in the `none` mode (`ledger-replay/1.3`); see the module docstring."""
    return _fold(events, as_of, ledger_version, False)[0]


def reconstruct_fifo(
    events: Iterable[SequencedEvent], as_of: datetime.date, ledger_version: int
) -> FifoState:
    """The FIFO/1 mode of the one lot fold (ledger-replay/1.4 Ruling 0.5, 1.5 Ruling 0.6): the same quantities, cash and flags as `reconstruct`, with exact lot books,
    relief records and carry histories. The state cites `ledger-replay/1.5` and `FIFO/1`. The `none` mode is untouched."""
    state, ctx, positions = _fold(events, as_of, ledger_version, True)
    assert ctx is not None
    books: Dict[Tuple[uuid.UUID, uuid.UUID], LotBook] = {}
    reconstructable = {a.account_id for a in state.accounts if a.status is AccountStatus.RECONSTRUCTED}
    for (account, listing), position in sorted(positions.items(), key=lambda kv: (kv[0][0].int, kv[0][1].int)):
        if account not in reconstructable:
            continue
        flagged = position.unresolved_split or position.inconsistent or position.multi_split or position.poisoned
        causes: Set[ReplayDetail] = set()
        if position.poisoned:
            causes.add(ReplayDetail.VALUE_NOT_REPRESENTABLE)
        if position.multi_split:
            causes.add(ReplayDetail.MULTIPLE_SAME_DAY_SPLITS)
        if position.unresolved_split:
            causes.add(ReplayDetail.SPLIT_FRACTION)
        if position.inconsistent:
            causes.add(ReplayDetail.NEGATIVE_QUANTITY)
        if not flagged and position.unresolved_depletion:
            causes |= position.unresolved_causes or {ReplayDetail.LOT_DEPLETION}
        lots = () if causes else tuple(sorted((_public(lot) for lot in position.lots), key=lambda x: x.sort_key))
        quantity = None if flagged else position.qty
        if quantity == 0 and not causes:
            continue  # a closed position has no book (as `none` does not emit it)
        books[(account, listing)] = LotBook(account, listing, quantity, lots, _sorted_details(causes))
    history = {k: tuple(v) for k, v in ctx.history.items()}
    return FifoState(state, LOT_METHOD_ID, books, dict(ctx.reliefs), history, tuple(ctx.conservation_failures))


def _fold(
    events: Iterable[SequencedEvent], as_of: datetime.date, ledger_version: int, fifo: bool
) -> Tuple[ReplayedState, Optional[_FifoCtx], Dict[Tuple[uuid.UUID, uuid.UUID], _Position]]:
    if isinstance(as_of, datetime.datetime) or not isinstance(as_of, datetime.date):
        raise ReplayInputError(f"as_of must be a datetime.date (not a datetime), got {as_of!r}")
    if isinstance(ledger_version, bool) or not isinstance(ledger_version, int) or ledger_version < 0:
        raise ReplayInputError(f"ledger_version must be an int >= 0, got {ledger_version!r}")
    items = list(events)
    for item in items:
        if not isinstance(item, SequencedEvent):
            raise ReplayInputError(f"events must be SequencedEvent, got {type(item)!r}")
    if len({i.ledger_seq for i in items}) != len(items):
        raise ReplayInputError("duplicate ledger_seq in the input events")
    if len({i.event.event_id for i in items}) != len(items):
        raise ReplayInputError("duplicate event_id in the input events")

    live = _select_live(items, ledger_version)
    snapshots = _snapshot_dates(live)
    account_ids = sorted({i.event.account_id for i in live}, key=lambda a: a.int)
    not_reconstructable = {a for a, s in snapshots.items() if as_of < s}

    included = sorted(
        (
            i
            for i in live
            if i.event.event_date <= as_of and i.event.account_id not in not_reconstructable
        ),
        key=_sort_key,
    )

    positions: Dict[Tuple[uuid.UUID, uuid.UUID], _Position] = {}
    cash: _Cash = {}

    # Day by day (§3.3, 0.4.2): the day's events update quantities, cash and the day's
    # accumulators in (rank, ledger_seq) order; basis is then resolved once, from the
    # whole candidate set, so it cannot depend on same-day entry order.
    ctx = _FifoCtx({}, {}) if fifo else None
    for day, group in itertools.groupby(included, key=lambda i: i.event.event_date):
        day_events = [i.event for i in group]
        out_to_in, in_to_src = _pair_transfers(day_events, by_event_id=fifo)
        touched: Set[Tuple[uuid.UUID, uuid.UUID]] = set()
        same_day_splits: Dict[Tuple[uuid.UUID, uuid.UUID], int] = {}
        for event in day_events:
            if event.event_type is EventType.SPLIT and event.listing_id is not None:
                split_key = (event.account_id, event.listing_id)
                same_day_splits[split_key] = same_day_splits.get(split_key, 0) + 1
        for event in day_events:
            _apply_cash(cash, event)
            _apply_position(positions, touched, event, same_day_splits, fifo)
        _resolve_day(positions, touched, out_to_in, in_to_src, ctx, day)
        _end_of_day_check(positions, touched)

    accounts = tuple(
        _account_state(a, snapshots.get(a), a in not_reconstructable, positions, cash)
        for a in account_ids
    )
    return ReplayedState(FIFO_CONVENTION_SET_ID if fifo else CONVENTION_SET_ID, as_of, ledger_version, accounts), ctx, positions


_Cash = Dict[Tuple[uuid.UUID, CurrencyCode], Optional[Fraction]]


def _cash_move(cash: "_Cash", account: uuid.UUID, currency: CurrencyCode, delta: Decimal,
               sign: int) -> None:
    """Exact and unbounded, except that an extreme amount (`_too_extreme`) poisons its own
    `(account, currency)` key: the stored `None` becomes VALUE_NOT_REPRESENTABLE at output."""
    key = (account, currency)
    current = cash.get(key, Fraction(0))
    if current is None or _too_extreme(delta):
        cash[key] = None
    else:
        cash[key] = current + sign * Fraction(delta)


def _cash_add(cash: "_Cash", account: uuid.UUID, currency: CurrencyCode, delta: Decimal) -> None:
    _cash_move(cash, account, currency, delta, 1)


def _cash_sub(cash: "_Cash", account: uuid.UUID, currency: CurrencyCode, delta: Decimal) -> None:
    _cash_move(cash, account, currency, delta, -1)


def _apply_cash(cash: "_Cash", event: LedgerEvent) -> None:
    """§0.2 cash column. Direction comes from the type; amounts are magnitudes."""
    kind = event.event_type
    account, currency = event.account_id, event.currency
    amount = None if event.amount is None else event.amount.amount
    if kind in (EventType.SELL, EventType.DIVIDEND, EventType.INTEREST, EventType.DEPOSIT,
                EventType.OPENING_CASH):
        assert amount is not None
        _cash_add(cash, account, currency, amount)
    elif kind in (EventType.BUY, EventType.FEE, EventType.TAX, EventType.WITHDRAWAL,
                  EventType.INTEREST_CHARGED):
        assert amount is not None
        _cash_sub(cash, account, currency, amount)
    elif kind is EventType.TRANSFER_IN and amount is not None:
        _cash_add(cash, account, currency, amount)
    elif kind is EventType.TRANSFER_OUT and amount is not None:
        _cash_sub(cash, account, currency, amount)
    elif kind is EventType.CURRENCY_CONVERSION:
        assert amount is not None and event.bought_amount is not None
        _cash_sub(cash, account, currency, amount)
        _cash_add(cash, account, event.bought_amount.currency, event.bought_amount.amount)
    elif kind in (EventType.SPLIT, EventType.OPENING_POSITION, EventType.TRANSFER_IN,
                  EventType.TRANSFER_OUT):
        return  # no cash effect (security-form transfers have no amount)
    else:  # pragma: no cover - REVERSAL never reaches the fold
        raise ReplayInputError(f"event type {kind} has no replay rule")


def _apply_position(
    positions: Dict[Tuple[uuid.UUID, uuid.UUID], _Position],
    touched: Set[Tuple[uuid.UUID, uuid.UUID]],
    event: LedgerEvent,
    same_day_splits: Dict[Tuple[uuid.UUID, uuid.UUID], int],
    fifo: bool = False,
) -> None:
    kind = event.event_type
    if kind not in _POSITION_EVENTS or event.listing_id is None:
        return  # e.g. a DIVIDEND/FEE/TAX naming a listing changes cash only (§0.2, §4)
    key = (event.account_id, event.listing_id)
    if kind is EventType.SPLIT:
        existing = positions.get(key)
        if existing is None:
            return  # 0 units scaled is 0 units
        if same_day_splits.get(key, 0) >= 2:
            # Ruling 3.4: not combined, not applied in ledger_seq order. Splits are rank 0, so
            # `qty` here is the start-of-day quantity. With units held the position is
            # LEDGER_INCONSISTENT from this date (sticky); with none, the splits scale nothing.
            if existing.qty != 0:
                existing.multi_split = True
                touched.add(key)
            return
        assert event.split_ratio is not None
        existing.apply_split(event.split_ratio.new_units, event.split_ratio.old_units)
        touched.add(key)
        return
    position = positions.setdefault(key, _Position())
    touched.add(key)
    quantity = event.quantity
    assert quantity is not None
    if not position.poisoned and _too_extreme(quantity):
        position.poisoned = True  # R3-1: fail closed for THIS position only, no arithmetic
        position.lots = []
    # An extreme BASIS (a BUY's amount, an opening or external in-leg's cost_basis; never a
    # SELL's proceeds) makes only this position's basis a VALUE_NOT_REPRESENTABLE state
    # (unresolved status, so it clears when the position ends a day at 0); the quantity is
    # still tracked. The acquisition then adds no lot.
    basis_money = event.amount if kind is EventType.BUY else (
        event.cost_basis if kind in (EventType.OPENING_POSITION, EventType.TRANSFER_IN) else None)
    extreme_basis = basis_money is not None and _too_extreme(basis_money.amount)
    if extreme_basis and not position.poisoned:
        _make_unresolved(position, [], {ReplayDetail.VALUE_NOT_REPRESENTABLE})
    units = Fraction(1) if position.poisoned else Fraction(quantity)
    if position.unresolved_split or position.poisoned:
        # Quantity is no longer defined (§7, or an extreme magnitude); nothing to track. An
        # internal out-leg is still recorded so its receiver inherits the source's TRUE cause
        # (C1C-5).
        if kind is EventType.TRANSFER_OUT and event.counterparty_account_id is not None:
            position.out_legs.append((event.event_id, units))
        if fifo and kind in (EventType.SELL, EventType.TRANSFER_OUT):
            position.fifo_deps.append((event.event_id, units, kind, event.counterparty_account_id is not None))
        return
    if kind is EventType.BUY:
        assert event.amount is not None
        position.qty += units
        if not extreme_basis:
            lot = _lot_from_basis(quantity, event.amount)  # gross consideration (§0.2 note 1)
            if fifo:  # 0.5.1: a BUY lot is dated by its trade date
                lot = dataclasses.replace(lot, acq=event.event_date, kind=DATE_TRADE, origin=event.event_id, origin_type=kind.value)
            position.acq.append(lot)
    elif kind is EventType.OPENING_POSITION or (
        kind is EventType.TRANSFER_IN and event.counterparty_account_id is None
    ):
        # Basis from the event, or unknown (§6.4): never zero, never market value.
        position.qty += units
        if not extreme_basis:
            lot = _lot_from_basis(quantity, event.cost_basis)
            if fifo:
                # 0.5.1 / 0.6.1: ENTRY (the date the units entered this portfolio) unless the user recorded `acquired_on`, then RECORDED at that date
                recorded = event.acquired_on is not None
                lot = dataclasses.replace(
                    lot, acq=event.acquired_on if recorded else event.event_date, kind=DATE_RECORDED if recorded else DATE_ENTRY,
                    origin=event.event_id, origin_type=kind.value)
            position.acq.append(lot)
    elif kind is EventType.TRANSFER_IN:  # internal: lots carried from the source (0.4.5)
        position.qty += units
        position.carry_in.append(event.event_id)
    elif kind in (EventType.SELL, EventType.TRANSFER_OUT):
        position.qty -= units
        position.dep += units
        if kind is EventType.TRANSFER_OUT and event.counterparty_account_id is not None:
            position.out_legs.append((event.event_id, units))
        if fifo:
            position.fifo_deps.append((event.event_id, units, kind, event.counterparty_account_id is not None))
    else:  # pragma: no cover - only these types carry a listing and a quantity
        raise ReplayInputError(f"event type {kind} has no position rule")


def _end_of_day_check(
    positions: Dict[Tuple[uuid.UUID, uuid.UUID], _Position],
    touched: Set[Tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """§3.3/§9: only end-of-day quantities are validated; a negative one is
    flagged (sticky), never clamped."""
    for key in touched:
        position = positions[key]
        if not (position.unresolved_split or position.poisoned) and position.qty < 0:
            position.inconsistent = True
    touched.clear()


def _position_state(
    account: uuid.UUID, listing: uuid.UUID, position: _Position
) -> Optional[PositionState]:
    flagged = (position.unresolved_split or position.inconsistent or position.multi_split
               or position.poisoned)
    if position.qty == 0 and not flagged:
        return None  # closed position: not emitted
    quantity_details: Set[ReplayDetail] = set()
    if position.poisoned:
        quantity_details.add(ReplayDetail.VALUE_NOT_REPRESENTABLE)
    if position.multi_split:
        quantity_details.add(ReplayDetail.MULTIPLE_SAME_DAY_SPLITS)
    if position.unresolved_split:
        quantity_details.add(ReplayDetail.SPLIT_FRACTION)
    if position.inconsistent:
        quantity_details.add(ReplayDetail.NEGATIVE_QUANTITY)
    basis_details = set(quantity_details)  # a flagged quantity suppresses the basis too
    if quantity_details:
        quantity = _insufficient(quantity_details)
    else:
        quantity = _available_fraction(position.qty)
        if quantity.value is None:  # C1C-6: too large to write exactly; scoped to this quantity
            quantity_details.add(ReplayDetail.VALUE_NOT_REPRESENTABLE)

    if position.unresolved_depletion:
        basis_details |= position.unresolved_causes or {ReplayDetail.LOT_DEPLETION}
    if position.unknown_flag or any(lot.cost is None for lot in position.lots):
        basis_details.add(ReplayDetail.UNKNOWN_BASIS)
    if not basis_details and not position.lots:
        basis_details.add(ReplayDetail.LOT_DEPLETION)  # defensive: nothing to state a basis from
    basis: Tuple[BasisAmount, ...]
    if not basis_details:
        # 0.4.1/0.4.6: total basis per currency = sum of c x u, exact rationals; emitted
        # only if it terminates at this date and is writable, otherwise INSUFFICIENT_DATA
        # (a state, never an exception; no rounding).
        totals: Dict[CurrencyCode, Fraction] = {}
        for lot in position.lots:
            assert lot.cost is not None and lot.currency is not None
            totals[lot.currency] = totals.get(lot.currency, Fraction(0)) + lot.cost * lot.units
        amounts: List[Tuple[CurrencyCode, Decimal]] = []
        for currency, total in sorted(totals.items(), key=lambda kv: kv[0].code):
            exact, why = _to_decimal(total)
            if exact is None:
                assert why is not None
                basis_details.add(why)
            else:
                amounts.append((currency, exact))
        if not basis_details:
            basis = tuple(BasisAmount(c, _available(a)) for c, a in amounts)
    if basis_details:
        # C1C-4: if any currency entry cannot be presented, present none (never a partial
        # basis), and the details then describe exactly this single no-value entry.
        basis = (BasisAmount(None, _insufficient(basis_details)),)
    return PositionState(
        account, listing, quantity, basis,
        _sorted_details(quantity_details), _sorted_details(basis_details),
    )


def _account_state(
    account: uuid.UUID,
    snapshot: Optional[datetime.date],
    not_reconstructable: bool,
    positions: Dict[Tuple[uuid.UUID, uuid.UUID], _Position],
    cash: "_Cash",
) -> AccountState:
    if not_reconstructable:
        return AccountState(account, AccountStatus.NOT_RECONSTRUCTABLE, snapshot, (), ())
    states = []
    for (acct, listing), position in sorted(positions.items(), key=lambda kv: (kv[0][0].int, kv[0][1].int)):
        if acct != account:
            continue
        state = _position_state(acct, listing, position)
        if state is not None:
            states.append(state)
    balances: List[CashBalance] = []
    unrepresentable: List[CurrencyCode] = []
    for (acct, currency), amount in sorted(cash.items(), key=lambda kv: (kv[0][0].int, kv[0][1].code)):
        if acct != account or (amount is not None and amount == 0):
            continue
        dec, _why = (None, None) if amount is None else _to_decimal(amount)
        if dec is None:  # C1C-6: this one balance becomes a state, nothing else is affected
            unrepresentable.append(currency)
        else:
            balances.append(CashBalance(account, Money(dec, currency)))
    return AccountState(account, AccountStatus.RECONSTRUCTED, snapshot, tuple(states),
                        tuple(balances), tuple(unrepresentable))
