"""Append and read the user's benchmark selection (PD-0039 D5; migration 0015; tech plan 17.5).

WRITE (the user-facing service is the only caller; the engine never writes a selection):
- `append_selection` appends a SELECT, a CLEAR or a REVERSAL in one transaction. Idempotent on `selection_id`: the same id with the same content is a no-op returning the STORED row (`created` False);
  the same id with different content is `DuplicateSelectionIdError`.
- `append_correction(reversal, replacement)` appends the reversal and then its replacement in ONE transaction, so `reversal.selection_seq < replacement.selection_seq` and no committed state shows the
  withdrawal without its replacement. The database independently refuses a replacement whose target was not reversed, or was reversed by an EARLIER transaction.
- A database rule that rejects a row (foreign key, CHECK, trigger, partial unique index) is `SelectionRuleRejectedError` carrying the constraint name.
- The insert uses `ON CONFLICT DO NOTHING RETURNING selection_seq` (as the ledger does), so a resubmission consumes a `selection_seq` value: the sequence has gaps and is an ordering, not a count.

READ (what a computation uses):
- `current_selection_version` is the portfolio's greatest committed `selection_seq` (0 for none): the KNOWLEDGE VERSION a benchmark-dependent manifest pins. It is a stable pin: within one portfolio the
  sequence value is drawn under a per-portfolio lock held to commit, so no row with `selection_seq <= S` can become visible after `S` was read.
- `selection_in_force(portfolio, version=None)` resolves the selection in force at `version` (the current one by default) with `domain.benchmark_selection.resolve_selection`; a version above the current is
  refused (it could not be reproduced), and a version INSIDE an atomic append (between a reversal and its replacement) is refused: no committed state ever had that content (the C1C-2 rule). CP4M-9: there is ONE
  check and ONE error type (`SelectionVersionNotPinnableError`; `SelectionVersionNotABoundaryError` is its old name, kept as an alias). `load_selections` states the boundary fact on each row it returns
  (`SequencedSelection.atomic_with_seq`, the greatest sequence of the other rows of the same transaction, read from `append_xid`), and the domain's `check_pinnable` judges a version from the rows at or below it,
  so a caller that passes exactly what `load_selections` returned to the engine gets the same refusal as one that goes through `selection_in_force`.
- `selection_pin(...)` is the pin data a manifest records: the version, the state and the row's id, sequence, benchmark id and digest.

`conn` is a psycopg 3 connection; this module does not import the driver. It never reads a clock and never writes outside `benchmark_selection`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

from domain.catalogs import BenchmarkCatalog, admit_selection
from domain.benchmark_selection import (
    NOT_STATED,
    BenchmarkSelection,
    Origin,
    RecordType,
    SelectionInForce,
    SelectionPin,
    SelectionVersionNotPinnableError,
    SequencedSelection,
    check_pinnable,
    pin_of,
    resolve_selection,
    validate_correction_pair,
)
from persistence.ledger_replay_store import PortfolioNotFoundError

COLUMNS: Tuple[str, ...] = (
    "selection_id", "portfolio_id", "record_type", "selected_on", "benchmark_id", "catalog_version", "origin", "reverses_selection_id", "corrects_selection_id",
)
_COLUMN_LIST = ", ".join(COLUMNS)
INSERT_SQL = f"INSERT INTO benchmark_selection ({_COLUMN_LIST}) VALUES ({', '.join(['%s'] * len(COLUMNS))}) ON CONFLICT DO NOTHING RETURNING selection_seq"
_SELECT = f"SELECT selection_seq, {_COLUMN_LIST} FROM benchmark_selection WHERE "
SELECT_BY_ID_SQL = _SELECT + "selection_id = %s"
#: the rows at or below a version, each with its BOUNDARY FACT: the greatest `selection_seq` of the OTHER rows appended by the same transaction (None when it was appended alone)
LOAD_SQL = (f"SELECT selection_seq, {_COLUMN_LIST}, (SELECT MAX(o.selection_seq) FROM benchmark_selection o WHERE o.portfolio_id = benchmark_selection.portfolio_id "
            "AND o.append_xid = benchmark_selection.append_xid AND o.selection_seq <> benchmark_selection.selection_seq) "
            "FROM benchmark_selection WHERE portfolio_id = %s AND selection_seq <= %s ORDER BY selection_seq")
VERSION_SQL = "SELECT COALESCE(MAX(selection_seq), 0) FROM benchmark_selection WHERE portfolio_id = %s"
PORTFOLIO_EXISTS_SQL = "SELECT 1 FROM portfolio WHERE portfolio_id = %s"
_REVERSED_ONCE = "benchmark_selection_reversed_once"
_CORRECTED_ONCE = "benchmark_selection_corrected_once"
_RETRYABLE_SQLSTATES = ("40P01", "40001")


class SelectionStoreError(Exception):
    """Base class for selection store failures."""


class DuplicateSelectionIdError(SelectionStoreError):
    """`selection_id` already stored with different content."""

    def __init__(self, selection_id: uuid.UUID) -> None:
        super().__init__(f"selection_id {selection_id} already exists with different content")
        self.selection_id = selection_id


class SelectionRuleRejectedError(SelectionStoreError):
    """A database-enforced rule rejected the append."""

    def __init__(self, constraint_name: Optional[str], message: str) -> None:
        super().__init__(f"{constraint_name or 'database rule'}: {message}")
        self.constraint_name = constraint_name


class SelectionConcurrencyError(SelectionStoreError):
    """The database aborted a statement (deadlock or serialization failure). Nothing was appended by this call; whether retrying is safe depends on who owns the transaction."""

    def __init__(self, sqlstate: str, message: str, transaction_owned: bool) -> None:
        super().__init__(f"{sqlstate}: {message}")
        self.sqlstate = sqlstate
        self.transaction_owned = transaction_owned


class SelectionVersionNotCommittedError(ValueError):
    """The requested version is above the portfolio's greatest committed `selection_seq`."""


#: the requested version falls inside an atomic append (between a reversal and its replacement): the SAME error as the domain's, whichever path found it (CP4M-9)
SelectionVersionNotABoundaryError = SelectionVersionNotPinnableError


@dataclass(frozen=True)
class AppendedSelection:
    selection: BenchmarkSelection  # as stored (the pre-existing row on a no-op)
    selection_seq: int
    created: bool


@dataclass(frozen=True)
class CorrectionAppended:
    reversal: AppendedSelection
    replacement: AppendedSelection


def to_row(s: BenchmarkSelection) -> Tuple[Any, ...]:
    return (s.selection_id, s.portfolio_id, s.record_type.value, s.selected_on, s.benchmark_id, s.catalog_version, None if s.origin is None else s.origin.value,
            s.reverses_selection_id, s.corrects_selection_id)


def from_row(row: Sequence[Any]) -> SequencedSelection:
    seq, selection_id, portfolio_id, record_type, selected_on, benchmark_id, catalog_version, origin, reverses, corrects, *partner = tuple(row)  # `partner`: the boundary fact of `LOAD_SQL`, absent from a plain read
    return SequencedSelection(int(seq), BenchmarkSelection(
        selection_id=selection_id, portfolio_id=portfolio_id, record_type=RecordType(record_type), selected_on=selected_on, benchmark_id=benchmark_id,
        catalog_version=catalog_version, origin=None if origin is None else Origin(origin), reverses_selection_id=reverses, corrects_selection_id=corrects),
        atomic_with_seq=(int(partner[0]) if partner[0] is not None else None) if partner else NOT_STATED)  # a plain read states no boundary fact: NOT_STATED, never "alone"


def get_selection(conn: Any, selection_id: uuid.UUID) -> Optional[AppendedSelection]:
    row = conn.execute(SELECT_BY_ID_SQL, (selection_id,)).fetchone()
    if row is None:
        return None
    stored = from_row(row)
    return AppendedSelection(stored.selection, stored.selection_seq, False)


def _store_owns_transaction(conn: Any) -> bool:
    status = getattr(getattr(conn, "info", None), "transaction_status", None)
    return True if status is None else int(status) == 0


def _append_one(conn: Any, s: BenchmarkSelection) -> AppendedSelection:
    row = conn.execute(INSERT_SQL, to_row(s)).fetchone()
    if row is not None:
        return AppendedSelection(s, int(row[0]), True)
    existing = get_selection(conn, s.selection_id)
    if existing is not None:
        if existing.selection.has_same_content(s):
            return existing
        raise DuplicateSelectionIdError(s.selection_id)
    if s.reverses_selection_id is not None:
        already = conn.execute("SELECT selection_id FROM benchmark_selection WHERE reverses_selection_id = %s", (s.reverses_selection_id,)).fetchone()
        if already is not None:
            raise SelectionRuleRejectedError(_REVERSED_ONCE, f"selection {s.reverses_selection_id} is already reversed by {already[0]}")
    if s.corrects_selection_id is not None:
        already = conn.execute("SELECT selection_id FROM benchmark_selection WHERE corrects_selection_id = %s", (s.corrects_selection_id,)).fetchone()
        if already is not None:
            raise SelectionRuleRejectedError(_CORRECTED_ONCE, f"selection {s.corrects_selection_id} is already corrected by {already[0]}")
    raise SelectionStoreError("the insert was skipped by a unique rule but no conflicting row was found")


def _append_all(conn: Any, selections: Sequence[BenchmarkSelection]) -> Tuple[AppendedSelection, ...]:
    owned = _store_owns_transaction(conn)
    try:
        with conn.transaction():
            return tuple(_append_one(conn, s) for s in selections)
    except SelectionStoreError:
        raise
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None)
        if isinstance(sqlstate, str) and sqlstate.startswith("23"):
            name = getattr(getattr(exc, "diag", None), "constraint_name", None)
            raise SelectionRuleRejectedError(name, str(exc)) from exc
        if sqlstate in _RETRYABLE_SQLSTATES:
            raise SelectionConcurrencyError(sqlstate, str(exc), owned) from exc
        raise


def append_selection(conn: Any, selection: BenchmarkSelection, *, catalog: Optional[BenchmarkCatalog] = None) -> AppendedSelection:
    """Append one record. With `catalog` (the user-facing service ALWAYS passes it) a SELECT must name an entry of the catalog, and the stored row carries `catalog_version` = the catalog's id
    (`BenchmarkNotInCatalogError` otherwise, before anything is written). Without it only the id's FORMAT is checked (a CLEAR and a REVERSAL name no benchmark, so they never need it)."""
    if catalog is not None:
        selection = admit_selection(selection, catalog)
    return _append_all(conn, [selection])[0]


def append_correction(conn: Any, reversal: BenchmarkSelection, replacement: BenchmarkSelection, *, catalog: Optional[BenchmarkCatalog] = None) -> CorrectionAppended:
    validate_correction_pair(reversal, replacement)
    if catalog is not None:
        replacement = admit_selection(replacement, catalog)
    first, second = _append_all(conn, [reversal, replacement])
    if first.selection_seq >= second.selection_seq:
        raise SelectionStoreError("the replacement must have a higher selection_seq than its reversal")
    return CorrectionAppended(first, second)


# --- reads -----------------------------------------------------------------------------------------------------------------------------------

def _require_portfolio(conn: Any, portfolio_id: uuid.UUID) -> None:
    if conn.execute(PORTFOLIO_EXISTS_SQL, (portfolio_id,)).fetchone() is None:
        raise PortfolioNotFoundError(f"portfolio {portfolio_id} does not exist")


def current_selection_version(conn: Any, portfolio_id: uuid.UUID) -> int:
    """The portfolio's greatest committed `selection_seq`, or 0 if it has no selection rows."""
    _require_portfolio(conn, portfolio_id)
    return int(conn.execute(VERSION_SQL, (portfolio_id,)).fetchone()[0])


def load_selections(conn: Any, portfolio_id: uuid.UUID, version: int) -> Tuple[SequencedSelection, ...]:
    """All rows of the portfolio with `selection_seq <= version`, in order (REVERSAL rows included). A low-level read: it does not check the version; go through `selection_in_force`."""
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(f"version must be an int >= 0, got {version!r}")
    _require_portfolio(conn, portfolio_id)
    return tuple(from_row(r) for r in conn.execute(LOAD_SQL, (portfolio_id, version)).fetchall())


def require_committed_boundary(conn: Any, portfolio_id: uuid.UUID, version: int) -> None:
    """Refuse a version that splits an atomic append (C1C-2). 0 and the current maximum are boundaries by construction. The rows of one transaction are contiguous within a portfolio (the trigger takes the
    portfolio lock, THEN draws the sequence), so a row at or below the version whose same-transaction partner lies above it cuts that transaction. This is the domain's `check_pinnable` on the rows `load_selections`
    returns (CP4M-9: one check, one error type), not a second rule."""
    if version == 0:
        return
    check_pinnable(load_selections(conn, portfolio_id, version), version, portfolio_id)


def selection_in_force(conn: Any, portfolio_id: uuid.UUID, version: Optional[int] = None) -> SelectionInForce:
    """The selection in force at knowledge version `version` (None: the current version, which is then the one pinned)."""
    current = current_selection_version(conn, portfolio_id)
    pin = current if version is None else version
    if isinstance(pin, bool) or not isinstance(pin, int) or pin < 0:
        raise ValueError(f"version must be an int >= 0, got {pin!r}")
    if pin > current:
        raise SelectionVersionNotCommittedError(f"selection version {pin} is above the portfolio's greatest committed {current}")
    if pin != current:
        require_committed_boundary(conn, portfolio_id, pin)
    return resolve_selection(portfolio_id, load_selections(conn, portfolio_id, pin), pin)


def selection_pin(conn: Any, portfolio_id: uuid.UUID, version: Optional[int] = None) -> SelectionPin:
    """The pin data a benchmark-dependent manifest records (the version, the state and the row in force)."""
    return pin_of(selection_in_force(conn, portfolio_id, version))
