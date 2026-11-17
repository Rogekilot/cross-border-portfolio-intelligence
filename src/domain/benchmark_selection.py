"""The user's primary-benchmark selection (PD-0039 D5; PRD FR-017, FR-018, UAT-03; tech plan 17.5).

A SELECTION is the user's explicit choice of ONE primary benchmark for ONE portfolio: a standing instruction, not a historical fact. It is USER DATA: the engine reads it and never writes it, and the system
never creates a selection on its own (FR-017: recommend, but require an explicit selection; the recommendation is not built in CP4). Rows are immutable because results CITE them (the pin below).

Three record types, in the shape of the ledger (a correction is a reversal plus a replacement, never an edit):
- `SELECT`   the user chooses benchmark `benchmark_id` (`origin`: `USER_CHOSEN`, or `RECOMMENDATION_ACCEPTED` when the user accepted a suggestion: still an explicit act);
- `CLEAR`    the user removes the benchmark: the portfolio then has none (relative metrics are MISSING_BENCHMARK; nothing is guessed);
- `REVERSAL` withdraws a SELECT or CLEAR recorded in error. A replacement carries `corrects_selection_id`.

ORDER AND RESOLUTION (`risk/1.4` Ruling 5.6 (1.1) and (1.4)). A pinned version `S` is a sequence number: the known records are those with `selection_seq <= S`; version 0, or a portfolio with no record, has none
(`NONE`), and the engine NEVER substitutes a benchmark. `selected_on` is the user's session date, passed in (no clock is read here): data the user sees, not an ordering input.
1. A REVERSAL VOIDS the record it names, as if it had not been recorded (it is not a CLEAR and not "no selection"). A record is LIVE if it is a SELECT or CLEAR that no known REVERSAL names.
2. A live record's POSITION is its own `selection_seq`, except that a REPLACEMENT (a record with `corrects_selection_id`) takes the position of the record it corrects, followed back to the original of the chain: a
   correction says what the original should have been, it is not a new instruction issued now. So correcting a superseded record does not override a later choice, and correcting the latest record puts the
   replacement in force (R13-V8, R13-V10).
3. The record in force is the live one with the LATEST position (a SELECT is `IN_FORCE`, a CLEAR `CLEARED`); none live is `NONE`, not CLEARED.
4. A version that holds the REVERSAL of a correction pair but not its replacement (appended with it, atomically) names a state that never existed: it is NOT PINNABLE (`SelectionVersionNotPinnableError`). Here that is
   judged by ONE check for every path (`check_pinnable`, CP4M-9) and refused with ONE error type, whatever rows the caller supplied: a loader states, on each row, the sequence of the row appended in the same transaction
   (`atomic_with_seq`, set by the store from `append_xid`), so a log truncated at the version is judged as the whole log is.
5. A REVERSAL of a REVERSAL is refused at append (migration 0015). A change of mind is a new SELECT or a CLEAR.
A computation uses the selection in force at the request's knowledge version (the current one), not the one in force at an as-of date: a benchmark choice is a viewing preference (PM ruling 2026-10-02, Q3).

THE PIN. `SelectionPin` is what a benchmark-dependent manifest records (the risk manifest is CP4c): the portfolio, the version `S`, the state (`NONE`, `CLEARED`, `IN_FORCE`) and, when a row is in force, its id,
sequence, benchmark id, catalog version, origin, date and a digest of the whole row, and (1.4) its POSITION whenever that differs from its sequence (a replacement). Changing the selection changes the pin (the UAT-03 foundation): a result computed against one pin is not the result for another.

THE BENCHMARK ID names a benchmark CATALOG entry (the committed `BENCHMARKS.json`, read by `domain.catalogs`). This module and the database validate only the FORMAT; the catalog check is `domain.catalogs.admit_selection`
(a SELECT must name an entry, and the row records `catalog_version` = the catalog's id), which the user-facing service applies through `append_selection(..., catalog=...)`. The committed catalog has no entries yet
(PD-0039 D1), so no real benchmark can be selected today.

Pure: no I/O, no clock, no randomness. Whether a stored database row obeys these rules is also enforced by migration 0015; a differential test feeds every field combination to both.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Optional, Sequence, Tuple, Union

#: PENDING: the id is checked against a catalog entry when one exists. Until then: a short ASCII identifier (migration 0015 states the same pattern).
BENCHMARK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
CATALOG_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,63}")
MIN_SELECTED_ON = datetime.date(1, 1, 1)
MAX_SELECTED_ON = datetime.date(9999, 12, 31)
PIN_SCHEMA = "finweb.benchmark_selection_pin/1"

REQUIRED, FORBIDDEN, OPTIONAL = "REQUIRED", "FORBIDDEN", "OPTIONAL"


class BenchmarkSelectionError(ValueError):
    """A selection that breaks a rule of its record type."""


@unique
class RecordType(Enum):
    SELECT = "SELECT"
    CLEAR = "CLEAR"
    REVERSAL = "REVERSAL"


@unique
class Origin(Enum):
    USER_CHOSEN = "USER_CHOSEN"
    RECOMMENDATION_ACCEPTED = "RECOMMENDATION_ACCEPTED"


#: field presence per record type; migration 0015 states the same table as CHECK constraints (`benchmark_selection_fields_*`) and a differential test compares the two.
FIELDS: Tuple[str, ...] = ("benchmark_id", "catalog_version", "origin", "reverses_selection_id", "corrects_selection_id")
FIELD_RULES: Dict[RecordType, Dict[str, str]] = {
    RecordType.SELECT: {"benchmark_id": REQUIRED, "catalog_version": OPTIONAL, "origin": REQUIRED, "reverses_selection_id": FORBIDDEN, "corrects_selection_id": OPTIONAL},
    RecordType.CLEAR: {"benchmark_id": FORBIDDEN, "catalog_version": FORBIDDEN, "origin": FORBIDDEN, "reverses_selection_id": FORBIDDEN, "corrects_selection_id": OPTIONAL},
    RecordType.REVERSAL: {"benchmark_id": FORBIDDEN, "catalog_version": FORBIDDEN, "origin": FORBIDDEN, "reverses_selection_id": REQUIRED, "corrects_selection_id": FORBIDDEN},
}


def is_benchmark_id(text: object) -> bool:
    return isinstance(text, str) and BENCHMARK_ID_PATTERN.fullmatch(text) is not None


@dataclass(frozen=True)
class BenchmarkSelection:
    selection_id: uuid.UUID
    portfolio_id: uuid.UUID
    record_type: RecordType
    selected_on: datetime.date
    benchmark_id: Optional[str] = None
    catalog_version: Optional[str] = None
    origin: Optional[Origin] = None
    reverses_selection_id: Optional[uuid.UUID] = None
    corrects_selection_id: Optional[uuid.UUID] = None

    def __post_init__(self) -> None:
        for name in ("selection_id", "portfolio_id"):
            if not isinstance(getattr(self, name), uuid.UUID):
                raise BenchmarkSelectionError(f"{name} must be a UUID")
        if not isinstance(self.record_type, RecordType):
            raise BenchmarkSelectionError("record_type must be a RecordType")
        if type(self.selected_on) is not datetime.date:  # a datetime is a date subclass: refused, the choice has a date and no time of day
            raise BenchmarkSelectionError("selected_on must be a date (not a datetime)")
        if not MIN_SELECTED_ON <= self.selected_on <= MAX_SELECTED_ON:
            raise BenchmarkSelectionError("selected_on is out of range")
        if self.origin is not None and not isinstance(self.origin, Origin):
            raise BenchmarkSelectionError("origin must be an Origin")
        for name in ("reverses_selection_id", "corrects_selection_id"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, uuid.UUID):
                raise BenchmarkSelectionError(f"{name} must be a UUID")
        for name, rule in FIELD_RULES[self.record_type].items():
            present = getattr(self, name) is not None
            if rule == REQUIRED and not present:
                raise BenchmarkSelectionError(f"{self.record_type.value} requires {name}")
            if rule == FORBIDDEN and present:
                raise BenchmarkSelectionError(f"{self.record_type.value} forbids {name}")
        if self.benchmark_id is not None and not is_benchmark_id(self.benchmark_id):
            raise BenchmarkSelectionError("benchmark_id must be a short ASCII identifier (letters, digits and . _ : -, at most 64 characters, starting with a letter or digit)")
        if self.catalog_version is not None and (not isinstance(self.catalog_version, str) or CATALOG_VERSION_PATTERN.fullmatch(self.catalog_version) is None):
            raise BenchmarkSelectionError("catalog_version must be a short ASCII identifier")
        if self.reverses_selection_id == self.selection_id:
            raise BenchmarkSelectionError("a selection cannot reverse itself")
        if self.corrects_selection_id == self.selection_id:
            raise BenchmarkSelectionError("a selection cannot correct itself")

    def has_same_content(self, other: "BenchmarkSelection") -> bool:
        return self == other

    def to_obj(self) -> Dict[str, Any]:
        return {
            "selection_id": str(self.selection_id), "portfolio_id": str(self.portfolio_id), "record_type": self.record_type.value, "selected_on": self.selected_on.isoformat(),
            "benchmark_id": self.benchmark_id, "catalog_version": self.catalog_version, "origin": None if self.origin is None else self.origin.value,
            "reverses_selection_id": None if self.reverses_selection_id is None else str(self.reverses_selection_id),
            "corrects_selection_id": None if self.corrects_selection_id is None else str(self.corrects_selection_id),
        }


class _NotStated:
    """The type of `NOT_STATED`: the boundary fact was never stated by the loader. Distinct from None ("appended alone"), so a loader that forgets the fact fails closed instead of reading as "no partner"."""

    _instance = None

    def __new__(cls) -> "_NotStated":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NOT_STATED"

    def __reduce__(self) -> str:
        return "NOT_STATED"


NOT_STATED = _NotStated()


@dataclass(frozen=True)
class SequencedSelection:
    """A stored row with its place in the log. `atomic_with_seq` is the BOUNDARY FACT a loader states (CP4M-9): the `selection_seq` of the other row appended in the SAME transaction (a REVERSAL's replacement, a
    replacement's REVERSAL), or None for a row appended alone. With it the question "does a version cut a correction pair?" is answered from the rows at or below the version alone, so a log truncated at the version
    (what `load_selections` returns) cannot be mistaken for one that never had the replacement. It is a fact about the log, not about the record: it is not in `to_obj` and so not in a row digest or a pin."""

    selection_seq: int
    selection: BenchmarkSelection
    atomic_with_seq: Union[int, None, _NotStated] = NOT_STATED  # NOT_STATED (the default) is NOT "appended alone": a REVERSAL whose fact is not stated cannot be judged and is refused (CP4M-10 point 6)

    def to_obj(self) -> Dict[str, Any]:
        return dict(self.selection.to_obj(), selection_seq=self.selection_seq)

    @property
    def digest(self) -> str:
        return _digest(self.to_obj())


def validate_correction_pair(reversal: BenchmarkSelection, replacement: BenchmarkSelection) -> None:
    """A correction is a REVERSAL of a row and a SELECT or CLEAR that names that row in `corrects_selection_id`, in one portfolio."""
    if reversal.record_type is not RecordType.REVERSAL:
        raise BenchmarkSelectionError("the first record of a correction must be a REVERSAL")
    if replacement.record_type is RecordType.REVERSAL:
        raise BenchmarkSelectionError("the replacement of a correction must be a SELECT or a CLEAR")
    if reversal.portfolio_id != replacement.portfolio_id:
        raise BenchmarkSelectionError("a correction stays inside one portfolio")
    if replacement.corrects_selection_id != reversal.reverses_selection_id:
        raise BenchmarkSelectionError("the replacement must correct the row the reversal withdraws")


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


@unique
class SelectionState(Enum):
    NONE = "NONE"          # no live SELECT or CLEAR at the version: no benchmark has been selected
    CLEARED = "CLEARED"    # the selection in force is a CLEAR: the user removed the benchmark
    IN_FORCE = "IN_FORCE"  # the selection in force is a SELECT


@dataclass(frozen=True)
class SelectionInForce:
    portfolio_id: uuid.UUID
    version: int
    state: SelectionState
    row: Optional[SequencedSelection]
    position: Optional[int] = None  # the row's position in the order (Ruling 5.6 (1.4)); equals its selection_seq unless it is a replacement


class SelectionVersionNotPinnableError(BenchmarkSelectionError):
    """The version holds the REVERSAL of a correction pair without its replacement: no committed state ever had that content (Ruling 5.6 (1.4) item 3.2)."""


def position_of(row: SequencedSelection, by_id: Dict[uuid.UUID, SequencedSelection]) -> int:
    """A record's position: its own sequence, or, for a replacement, the position of the record it corrects, followed back along the chain to the original (Ruling 5.6 (1.4) item 3.4)."""
    seen = {row.selection.selection_id}
    current = row
    while current.selection.corrects_selection_id is not None:
        target = by_id.get(current.selection.corrects_selection_id)
        if target is None or target.selection.selection_id in seen:
            break
        seen.add(target.selection.selection_id)
        current = target
    return current.selection_seq


def check_pinnable(rows: Sequence[SequencedSelection], version: int, portfolio_id: Optional[uuid.UUID] = None) -> None:
    """The ONE check, for every path (the engine, the store, the kit): a version that holds the REVERSAL of a correction pair without its replacement names a state that never existed (Ruling 5.6 (1.4) item 3.2).
    Two facts decide it, and either is enough. (1) The BOUNDARY FACT a loader states on each row (`atomic_with_seq`): a row at or below the version whose partner lies above it cuts a pair. This needs nothing above
    the version, so it holds for a log truncated at the version, which is what `load_selections` returns. (2) For rows without the fact, the rows above the version that the caller happened to give: a replacement
    above the version whose target a row at or below it reversed. Raises `SelectionVersionNotPinnableError`, whatever the caller supplied."""
    for r in rows:
        if r.selection_seq <= version and r.selection.record_type is RecordType.REVERSAL and r.atomic_with_seq is NOT_STATED:
            raise SelectionVersionNotPinnableError(f"row {r.selection_seq} is a REVERSAL and its boundary fact (`atomic_with_seq`: the row appended with it, or None for none) was not stated by the loader: "
                                                   f"whether version {version} cuts a correction pair cannot be judged, so it is refused")
        if r.selection_seq <= version and isinstance(r.atomic_with_seq, int) and r.atomic_with_seq > version:
            raise SelectionVersionNotPinnableError(f"version {version} cuts an atomic append: row {r.selection_seq} was appended with row {r.atomic_with_seq}; no committed state had that content")
    known_reversed = {r.selection.reverses_selection_id for r in rows if r.selection_seq <= version and r.selection.record_type is RecordType.REVERSAL}
    unseen = {r.selection.corrects_selection_id for r in rows if r.selection_seq > version and r.selection.corrects_selection_id is not None
              and (portfolio_id is None or r.selection.portfolio_id == portfolio_id)}
    if known_reversed & unseen:
        raise SelectionVersionNotPinnableError(f"version {version} holds the reversal of a correction pair without its replacement: no committed state had that content")


def resolve_selection(portfolio_id: uuid.UUID, rows: Sequence[SequencedSelection], version: int) -> SelectionInForce:
    """The selection in force at knowledge version `version` (see the module docstring). Pure over the rows given: a row with `selection_seq > version` is ignored, and so is a reversal beyond the version."""
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(f"version must be an int >= 0, got {version!r}")
    known = [r for r in rows if r.selection_seq <= version]
    if any(r.selection.portfolio_id != portfolio_id for r in known):
        raise BenchmarkSelectionError("a row of another portfolio was given")
    if len({r.selection_seq for r in known}) != len(known) or len({r.selection.selection_id for r in known}) != len(known):
        raise BenchmarkSelectionError("duplicate selection_seq or selection_id")
    reversed_ids = {r.selection.reverses_selection_id for r in known if r.selection.record_type is RecordType.REVERSAL}
    check_pinnable(rows, version, portfolio_id)
    live = [r for r in known if r.selection.record_type is not RecordType.REVERSAL and r.selection.selection_id not in reversed_ids]
    if not live:
        return SelectionInForce(portfolio_id, version, SelectionState.NONE, None)
    by_id = {r.selection.selection_id: r for r in known}
    positions = {r.selection.selection_id: position_of(r, by_id) for r in live}
    chosen = max(live, key=lambda r: (positions[r.selection.selection_id], r.selection_seq))  # the live record with the LATEST POSITION (Ruling 5.6 (1.4)): a replacement takes the position of the record it corrects
    state = SelectionState.IN_FORCE if chosen.selection.record_type is RecordType.SELECT else SelectionState.CLEARED
    return SelectionInForce(portfolio_id, version, state, chosen, positions[chosen.selection.selection_id])


@dataclass(frozen=True)
class SelectionPin:
    """What a benchmark-dependent manifest records. `selection_id` and the rest are None unless a SELECT is in force; `row_digest` is the digest of the whole row in force (None for NONE; a CLEAR has one too,
    and `record_type` says which)."""

    portfolio_id: str
    version: int
    state: str
    record_type: Optional[str]
    selection_id: Optional[str]
    selection_seq: Optional[int]
    benchmark_id: Optional[str]
    catalog_version: Optional[str]
    origin: Optional[str]
    selected_on: Optional[str]
    row_digest: Optional[str]
    position: Optional[int] = None  # Ruling 5.6 (1.4): present only when it differs from `selection_seq` (a replacement)

    def to_obj(self) -> Dict[str, Any]:
        out = {"schema": PIN_SCHEMA, "portfolio_id": self.portfolio_id, "version": self.version, "state": self.state, "record_type": self.record_type, "selection_id": self.selection_id,
               "selection_seq": self.selection_seq, "benchmark_id": self.benchmark_id, "catalog_version": self.catalog_version, "origin": self.origin, "selected_on": self.selected_on,
               "row_digest": self.row_digest}
        if self.position is not None:  # additive-when-present: every pin of a record in its own position serialises exactly as before
            out["position"] = self.position
        return out

    @property
    def digest(self) -> str:
        return _digest(self.to_obj())


def pin_of(in_force: SelectionInForce) -> SelectionPin:
    row = in_force.row
    if row is None:
        return SelectionPin(str(in_force.portfolio_id), in_force.version, in_force.state.value, None, None, None, None, None, None, None, None)
    s = row.selection
    return SelectionPin(str(in_force.portfolio_id), in_force.version, in_force.state.value, s.record_type.value, str(s.selection_id), row.selection_seq, s.benchmark_id, s.catalog_version,
                        None if s.origin is None else s.origin.value, s.selected_on.isoformat(), row.digest,
                        None if in_force.position is None or in_force.position == row.selection_seq else in_force.position)
