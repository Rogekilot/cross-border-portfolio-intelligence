"""Idempotent append of a `LedgerEvent` (Tech Plan §13.D).

Contract:

- New event -> inserted; `AppendResult.created` is True.
- Same idempotency key `(account_id, source_reference)` and the same content ->
  no-op; the EXISTING stored event is returned (`created` False), including its
  own `event_id`, which may differ from the submitted one.
- Same key, different content -> `IdempotencyConflictError`.
- Same `event_id` (with no key match): same content -> no-op returning the
  stored event; different content -> `DuplicateEventIdError`.
- An event with no `source_reference` has no idempotency key; resubmitting it
  under a new `event_id` appends a second event, by design.
- A rejection by a database rule (foreign key, CHECK, trigger, partial unique
  index) -> `LedgerRuleRejectedError` carrying the constraint name.

**"Same content" at the storage boundary** is exactly
`LedgerEvent.has_same_content`: every field except `event_id`, with `Decimal`
compared NUMERICALLY. `Decimal("1.0")` and `Decimal("1.00")` are the same
content: scale is a representation choice (a CSV re-import may format the same
number differently), not a different fact, and treating it as a conflict would
create spurious errors. NUMERIC preserves the scale that was first stored, and
a no-op returns that stored value unchanged; the resubmitted scale is
discarded, never written over the original (append-only).

The insert uses `ON CONFLICT DO NOTHING` (no conflict target) so a unique
violation is not an error but an empty `RETURNING`; the code then finds out
which unique rule fired. Consequence: a resubmission still consumes a
`ledger_seq` value, so `ledger_seq` has gaps and is an ordering, not a count.
Within one portfolio ledger_seq order equals commit order (migration 0003: the
value is drawn under a per-portfolio lock); across portfolios it does not.

Multi-event writes: `append_batch` (one transaction), `append_correction`
(reversal then replacement) and `append_internal_transfer` (both legs). All
events of one batch must belong to one portfolio. Use READ COMMITTED (the
default); the database rejects appends under other isolation levels.

`conn` is a psycopg 3 connection; this module does not import the driver. The
append runs in `conn.transaction()` (a savepoint if the caller already holds a
transaction).
"""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Optional, Sequence, Tuple

from domain.currency import CurrencyCode, Money
from domain.ledger import (
    EventType,
    LedgerEvent,
    SplitRatio,
    validate_correction_pair,
    validate_internal_transfer_pair,
)

EVENT_COLUMNS: Tuple[str, ...] = (
    "event_id", "account_id", "event_type", "event_date", "currency",
    "listing_id", "quantity", "amount", "cost_basis", "bought_amount",
    "bought_currency", "split_new", "split_old",
    "counterparty_account_id", "settlement_date", "ex_date", "reverses_event_id",
    "corrects_event_id", "source_reference", "acquired_on",
)

_COLUMN_LIST = ", ".join(EVENT_COLUMNS)
_PLACEHOLDERS = ", ".join(["%s"] * len(EVENT_COLUMNS))

INSERT_SQL = (
    f"INSERT INTO ledger_event ({_COLUMN_LIST}) VALUES ({_PLACEHOLDERS}) "
    "ON CONFLICT DO NOTHING RETURNING ledger_seq"
)
_INSERT_SQL_NO_ACQUIRED_ON = (
    f"INSERT INTO ledger_event ({', '.join(EVENT_COLUMNS[:-1])}) VALUES ({', '.join(['%s'] * (len(EVENT_COLUMNS) - 1))}) "
    "ON CONFLICT DO NOTHING RETURNING ledger_seq"
)
_SELECT = f"SELECT ledger_seq, {_COLUMN_LIST} FROM ledger_event WHERE "
SELECT_BY_KEY_SQL = _SELECT + "account_id = %s AND source_reference = %s"
SELECT_BY_EVENT_ID_SQL = _SELECT + "event_id = %s"
_REVERSED_ONCE = "ledger_event_reversed_once"
_CORRECTED_ONCE = "ledger_event_corrected_once"


class LedgerStoreError(Exception):
    """Base class for append failures."""


class IdempotencyConflictError(LedgerStoreError):
    """Same `(account_id, source_reference)`, different content."""

    def __init__(self, existing_event_id: uuid.UUID, account_id: uuid.UUID,
                 source_reference: str) -> None:
        super().__init__(
            f"source reference {source_reference!r} in account {account_id} is "
            f"already recorded as event {existing_event_id} with different content"
        )
        self.existing_event_id = existing_event_id
        self.account_id = account_id
        self.source_reference = source_reference


class DuplicateEventIdError(LedgerStoreError):
    """`event_id` already stored with different content."""

    def __init__(self, event_id: uuid.UUID) -> None:
        super().__init__(f"event_id {event_id} already exists with different content")
        self.event_id = event_id


class LedgerRuleRejectedError(LedgerStoreError):
    """A database-enforced ledger rule rejected the append."""

    def __init__(self, constraint_name: Optional[str], message: str) -> None:
        super().__init__(f"{constraint_name or 'database rule'}: {message}")
        self.constraint_name = constraint_name


#: Migration 0007 (ledger-replay Ruling 3.4 / F12): one live SPLIT per (account, listing,
#: event_date), carrying the combined ratio.
SAME_DAY_SPLIT_CONSTRAINT = "ledger_event_split_once_per_day"


#: Migration 0008 (R3-1): value < 1E30 and scale <= 24 on every numeric column. Violations
#: surface as `LedgerValueOutOfRangeError`, like a NUMERIC overflow.
NUMERIC_BOUND_CONSTRAINTS = frozenset({
    "ledger_event_quantity_bounds", "ledger_event_amount_bounds",
    "ledger_event_cost_basis_bounds", "ledger_event_bought_amount_bounds",
    "ledger_event_split_new_bounds", "ledger_event_split_old_bounds",
})


class SameDaySplitError(LedgerRuleRejectedError):
    """A second live SPLIT was appended for the same account, listing and ex-date. Reverse
    the existing split and append ONE split with the combined ratio (`append_correction`
    does both atomically)."""


#: 40P01 deadlock_detected and 40001 serialization_failure: nothing was written and the
#: whole call may be retried. 22003 numeric_value_out_of_range: a Decimal beyond
#: PostgreSQL NUMERIC's limits (the server refuses instead of rounding).
_RETRYABLE_SQLSTATES = ("40P01", "40001")
_NUMERIC_OUT_OF_RANGE = "22003"


class LedgerConcurrencyError(LedgerStoreError):
    """The database aborted a statement (deadlock or serialization failure). Most likely
    cause: an `append_batch` spanning two portfolios.

    What that means depends on who owns the transaction (`transaction_owned`):

    - the store opened it (the connection was idle): the whole transaction rolled back,
      nothing was appended, and repeating the same call is safe (`retry_safe` True);
    - the CALLER already had a transaction open: only the store's savepoint rolled back.
      The caller's transaction is still open and still holds its EARLIER appends and
      their portfolio locks, so retrying inside it can recreate the same deadlock and a
      later commit would write those earlier appends. The caller must roll back its WHOLE
      transaction before any retry (`retry_safe` False)."""

    def __init__(self, sqlstate: str, message: str, transaction_owned: bool = True) -> None:
        advice = (
            "the transaction was rolled back and nothing was appended; retrying the same "
            "call is safe"
            if transaction_owned else
            "only this call's savepoint was rolled back; the enclosing transaction is STILL "
            "OPEN and holds earlier appends and locks: roll back the WHOLE transaction "
            "before retrying, and do not retry inside it"
        )
        super().__init__(f"{sqlstate}: {message} ({advice})")
        self.sqlstate = sqlstate
        self.transaction_owned = transaction_owned

    @property
    def retry_safe(self) -> bool:
        """True only when the store owned (and therefore rolled back) the transaction."""
        return self.transaction_owned


class LedgerValueOutOfRangeError(LedgerStoreError):
    """A quantity or amount is outside PostgreSQL NUMERIC's range."""


@dataclass(frozen=True)
class AppendResult:
    event: LedgerEvent  # the event as stored (the pre-existing one on a no-op)
    ledger_seq: int
    created: bool


def event_to_row(event: LedgerEvent) -> Tuple[Any, ...]:
    """Column values in `EVENT_COLUMNS` order. Money is unpacked: the single
    `currency` column serves `amount` and `cost_basis`; `bought_amount` (a
    CURRENCY_CONVERSION's bought side) uses its own `bought_currency`. No rate
    is derived or stored."""
    ratio = event.split_ratio
    return (
        event.event_id, event.account_id, event.event_type.value, event.event_date,
        str(event.currency), event.listing_id, event.quantity,
        None if event.amount is None else event.amount.amount,
        None if event.cost_basis is None else event.cost_basis.amount,
        None if event.bought_amount is None else event.bought_amount.amount,
        None if event.bought_amount is None else str(event.bought_amount.currency),
        None if ratio is None else ratio.new_units,
        None if ratio is None else ratio.old_units,
        event.counterparty_account_id, event.settlement_date, event.ex_date,
        event.reverses_event_id, event.corrects_event_id, event.source_reference,
        event.acquired_on,
    )


def row_to_event(row: Tuple[Any, ...]) -> Tuple[int, LedgerEvent]:
    """Inverse of `event_to_row` for a `SELECT ledger_seq, <EVENT_COLUMNS>` row.
    Returns `(ledger_seq, event)`; the event is re-validated by the domain."""
    seq = row[0]
    (event_id, account_id, event_type, event_date, currency, listing_id, quantity,
     amount, cost_basis, bought_amount, bought_currency, split_new, split_old,
     counterparty, settlement_date,
     ex_date, reverses, corrects, source_reference, acquired_on) = row[1:]
    code = CurrencyCode(currency)
    event = LedgerEvent(
        event_id=event_id,
        account_id=account_id,
        event_type=EventType(event_type),
        event_date=event_date,
        currency=code,
        listing_id=listing_id,
        quantity=quantity,
        amount=None if amount is None else Money(Decimal(amount), code),
        cost_basis=None if cost_basis is None else Money(Decimal(cost_basis), code),
        bought_amount=None if bought_amount is None
        else Money(Decimal(bought_amount), CurrencyCode(bought_currency)),
        split_ratio=None if split_new is None else SplitRatio(split_new, split_old),
        counterparty_account_id=counterparty,
        settlement_date=settlement_date,
        ex_date=ex_date,
        reverses_event_id=reverses,
        corrects_event_id=corrects,
        source_reference=source_reference,
        acquired_on=acquired_on,
    )
    return seq, event


def get_event(conn: Any, event_id: uuid.UUID) -> Optional[AppendResult]:
    row = conn.execute(SELECT_BY_EVENT_ID_SQL, (event_id,)).fetchone()
    if row is None:
        return None
    seq, stored = row_to_event(row)
    return AppendResult(stored, seq, False)


def _find_existing(conn: Any, event: LedgerEvent) -> Tuple[Optional[AppendResult], str]:
    if event.source_reference is not None:
        row = conn.execute(
            SELECT_BY_KEY_SQL, (event.account_id, event.source_reference)
        ).fetchone()
        if row is not None:
            seq, stored = row_to_event(row)
            return AppendResult(stored, seq, False), "key"
    return get_event(conn, event.event_id), "event_id"


def _append_one(conn: Any, event: LedgerEvent) -> AppendResult:
    if event.acquired_on is None:
        # PD-0036: an event with no `acquired_on` is inserted without naming the column (it defaults to NULL), so the store still works on a database that has
        # not applied 0014 (the migration tests apply partial batches) and a stored row never differs because of the new column.
        row = conn.execute(_INSERT_SQL_NO_ACQUIRED_ON, event_to_row(event)[:-1]).fetchone()
    else:
        row = conn.execute(INSERT_SQL, event_to_row(event)).fetchone()
    if row is not None:
        return AppendResult(event, row[0], True)
    return _resolve_no_insert(conn, event)


def _store_owns_transaction(conn: Any) -> bool:
    """True when no transaction is open on `conn`, so the `conn.transaction()` the store
    opens is the OUTERMOST one (a real BEGIN/COMMIT) rather than a savepoint inside the
    caller's. psycopg reports this as `conn.info.transaction_status` (IDLE == 0). A test
    double without `info` is treated as store-owned."""
    status = getattr(getattr(conn, "info", None), "transaction_status", None)
    if status is None:
        return True
    return int(status) == 0


#: C2-8 (review of 39733e9): `finweb.` is a RESERVED namespace of `source_reference`, for references the system writes
#: (F8-B's `finweb.f8b/1;...` marks a system-appended split; PD-0030 section 2: distinguishable from a user's entry).
#: Every ordinary append path (`append_event`, `append_batch`, `append_correction`, `append_internal_transfer`: what an
#: import, a UI or an API reaches) REFUSES a reference in it, so a user entry can never carry a system marker. The one
#: way in is `append_system_event`, which names the exact system namespace it writes. This keeps the marker out of
#: user-entered data; it is not a boundary against code running inside this process (nothing in Python is).
RESERVED_SOURCE_REFERENCE_NAMESPACE = "finweb."


class ReservedSourceReferenceError(LedgerStoreError):
    """A source_reference in the reserved system namespace was offered through a non-system append path."""

    def __init__(self, source_reference: str) -> None:
        super().__init__(
            f"source_reference {source_reference!r} is in the reserved system namespace "
            f"{RESERVED_SOURCE_REFERENCE_NAMESPACE!r}: only a system writer may use it")
        self.source_reference = source_reference


def is_reserved_source_reference(text: Optional[str]) -> bool:
    """True for a reference in the reserved namespace, however it is spelled: leading blanks, case and compatibility
    forms (a ligature, a full-width letter) are folded first, so a lookalike cannot slip past the check."""
    if text is None:
        return False
    return fold_reference(text).startswith(RESERVED_SOURCE_REFERENCE_NAMESPACE)


#: Default-ignorable code points outside category Cf (Python has no property for them): the combining grapheme joiner,
#: the Hangul fillers, the Khmer inherent vowels, the Mongolian free variation selectors, variation selectors and the
#: halfwidth Hangul filler (Unicode DerivedCoreProperties, Default_Ignorable_Code_Point).
_IGNORABLE = frozenset(
    [0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0]
    + list(range(0x180B, 0x1810)) + list(range(0xFE00, 0xFE10)) + list(range(0xE0100, 0xE01F0)))


def fold_reference(text: str) -> str:
    """The form a reference is compared in for the reserved-namespace test (C2-8, hardened in the CP2 final round):
    NFKC (full-width forms, ligatures, NBSP); every format character (category Cf: zero-width space and joiners,
    BOM, soft hyphen, bidi marks) and every other default-ignorable code point REMOVED, so a marker with an invisible
    character inside it is still the marker; the ideographic full stop U+3002 (and its halfwidth form, which NFKC maps
    to it) read as '.'; then blanks stripped and case folded. RESIDUAL, by design: a homoglyph from another script
    (a Cyrillic i for the Latin one) does not fold to the marker. It is harmless: a system event is recognised only by
    `parse_source_reference`'s exact-ASCII grammar and the deterministic event id, which no homoglyph satisfies."""
    folded = unicodedata.normalize("NFKC", text)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf" and ord(ch) not in _IGNORABLE)
    folded = folded.replace("。", ".")
    return folded.strip().casefold()


def _refuse_reserved(events: Sequence[LedgerEvent]) -> None:
    for event in events:
        if is_reserved_source_reference(event.source_reference):
            raise ReservedSourceReferenceError(str(event.source_reference))


def append_batch(conn: Any, events: Sequence[LedgerEvent]) -> List[AppendResult]:
    """Append `events` in order in ONE transaction: all commit or none. A source_reference in the reserved system
    namespace is refused (C2-8; see `append_system_event`). Every
    event of a batch should belong to one portfolio: the per-portfolio append
    lock is taken per event, so a batch spanning portfolios is ALLOWED but can
    deadlock against another such batch; PostgreSQL aborts one, surfaced here as
    `LedgerConcurrencyError`, which is safe to retry ONLY when this call owned the
    transaction (`error.retry_safe`); inside a caller-owned transaction the caller must
    roll back its whole transaction first. Commit-time rules (internal transfer pairing) raise
    `LedgerRuleRejectedError` when the transaction ends, which is inside this
    call when it owns the transaction and at the caller's commit otherwise."""
    _refuse_reserved(events)
    return _append_batch(conn, events)


def append_system_event(conn: Any, event: LedgerEvent, *, namespace: str) -> AppendResult:
    """The ONLY append path that accepts a reserved-namespace `source_reference` (C2-8): a SYSTEM writer (today F8-B)
    names the exact namespace it writes (`finweb.f8b/1`), and the event's reference must start with it. Otherwise
    identical to `append_event` (idempotent, guarded, one transaction)."""
    if not is_reserved_source_reference(namespace) or namespace != namespace.strip():
        raise ReservedSourceReferenceError(namespace)
    if event.source_reference is None or not event.source_reference.startswith(namespace):
        raise ReservedSourceReferenceError(str(event.source_reference))
    return _append_batch(conn, [event])[0]


def _append_batch(conn: Any, events: Sequence[LedgerEvent]) -> List[AppendResult]:
    owned = _store_owns_transaction(conn)
    try:
        with conn.transaction():
            return [_append_one(conn, event) for event in events]
    except LedgerStoreError:
        raise
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None)
        if isinstance(sqlstate, str) and sqlstate.startswith("23"):
            diag = getattr(exc, "diag", None)
            name = getattr(diag, "constraint_name", None)
            if name == SAME_DAY_SPLIT_CONSTRAINT:
                raise SameDaySplitError(name, str(exc)) from exc
            if name in NUMERIC_BOUND_CONSTRAINTS:
                raise LedgerValueOutOfRangeError(f"{name}: {exc}") from exc
            raise LedgerRuleRejectedError(name, str(exc)) from exc
        if sqlstate in _RETRYABLE_SQLSTATES:
            raise LedgerConcurrencyError(sqlstate, str(exc), transaction_owned=owned) from exc
        if sqlstate == _NUMERIC_OUT_OF_RANGE:
            raise LedgerValueOutOfRangeError(str(exc)) from exc
        raise


def append_event(conn: Any, event: LedgerEvent) -> AppendResult:
    return append_batch(conn, [event])[0]


@dataclass(frozen=True)
class CorrectionResult:
    reversal: AppendResult
    replacement: AppendResult


def append_correction(
    conn: Any, reversal: LedgerEvent, replacement: LedgerEvent
) -> CorrectionResult:
    """Reverse an event and append its replacement atomically, reversal first,
    so `reversal.ledger_seq < replacement.ledger_seq` (F10; ledger-replay
    §2.3). The database independently refuses a replacement whose target is not
    reversed, or whose reversal was committed by an EARLIER transaction
    (`ledger_event_correction_same_transaction`, migration 0004), so a
    replacement can never be visible at an `L` without being atomic with its
    reversal."""
    validate_correction_pair(reversal, replacement)
    first, second = append_batch(conn, [reversal, replacement])
    if first.ledger_seq >= second.ledger_seq:
        raise LedgerStoreError("replacement must have a higher ledger_seq than its reversal")
    return CorrectionResult(first, second)


def append_internal_transfer(
    conn: Any, transfer_out: LedgerEvent, transfer_in: LedgerEvent
) -> Tuple[AppendResult, AppendResult]:
    """Append both legs of an internal transfer in one transaction after
    checking the pair (ledger-replay/1.0 §6.2). Legs appended any other way
    are still checked by the database at commit (see migration 0003)."""
    validate_internal_transfer_pair(transfer_out, transfer_in)
    out_result, in_result = append_batch(conn, [transfer_out, transfer_in])
    return out_result, in_result


def _resolve_no_insert(conn: Any, event: LedgerEvent) -> AppendResult:
    existing, via = _find_existing(conn, event)
    if existing is not None:
        if existing.event.has_same_content(event):
            return existing
        if via == "key":
            raise IdempotencyConflictError(
                existing.event.event_id, event.account_id, event.source_reference or ""
            )
        raise DuplicateEventIdError(event.event_id)
    if event.reverses_event_id is not None:
        already = conn.execute(
            "SELECT event_id FROM ledger_event WHERE reverses_event_id = %s",
            (event.reverses_event_id,),
        ).fetchone()
        if already is not None:
            raise LedgerRuleRejectedError(
                _REVERSED_ONCE,
                f"event {event.reverses_event_id} is already reversed by {already[0]}",
            )
    if event.corrects_event_id is not None:
        already = conn.execute(
            "SELECT event_id FROM ledger_event WHERE corrects_event_id = %s",
            (event.corrects_event_id,),
        ).fetchone()
        if already is not None:
            raise LedgerRuleRejectedError(
                _CORRECTED_ONCE,
                f"event {event.corrects_event_id} is already corrected by {already[0]}",
            )
    raise LedgerStoreError(
        "insert was skipped by a unique rule but no conflicting row was found"
    )
