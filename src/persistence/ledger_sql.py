"""Renders the ledger CHECK constraints from `domain.ledger.FIELD_RULES`.

Choice (engineer-proposed): the migration file stays static, checksummed SQL,
but the block of per-event-type constraints inside it is delimited by markers
and must equal `render_generated_region()` byte for byte. A unit test
compares them, so changing `FIELD_RULES` (or the SQL) without the other fails
the default suite. To regenerate after a rule change, print
`render_generated_region()` and put it in a NEW migration (applied files are
immutable).

Only REQUIRED and FORBIDDEN rows produce SQL; OPTIONAL is the absence of a
constraint. `split_ratio` is stored as two columns, `split_new` and
`split_old`, which are present or absent together.

The transfer-shape rule is not in FIELD_RULES (`LedgerEvent.
_validate_transfer_shape`); it is rendered here by hand and exercised by the
integration tests.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from domain.ledger import CONDITIONAL_FIELDS, FIELD_RULES, FORBIDDEN, REQUIRED, EventType

BEGIN_MARKER = "-- BEGIN GENERATED: persistence.ledger_sql.render_generated_region (do not edit)"
END_MARKER = "-- END GENERATED"

COLUMNS_FOR_FIELD: Dict[str, Tuple[str, ...]] = {
    "listing_id": ("listing_id",),
    "quantity": ("quantity",),
    "amount": ("amount",),
    "cost_basis": ("cost_basis",),
    "bought_amount": ("bought_amount", "bought_currency"),
    "split_ratio": ("split_new", "split_old"),
    "counterparty_account_id": ("counterparty_account_id",),
    "settlement_date": ("settlement_date",),
    "ex_date": ("ex_date",),
    "reverses_event_id": ("reverses_event_id",),
    "corrects_event_id": ("corrects_event_id",),
    "source_reference": ("source_reference",),
    "acquired_on": ("acquired_on",),
}


def render_event_type_check() -> str:
    names = ", ".join("'" + t.value + "'" for t in EventType)
    return f"    CONSTRAINT ledger_event_type_valid CHECK (event_type IN ({names})),"


def render_presence_checks() -> List[str]:
    lines: List[str] = []
    for event_type in EventType:
        rules = FIELD_RULES[event_type]
        clauses: List[str] = []
        for field in CONDITIONAL_FIELDS:
            rule = rules[field]
            if rule == REQUIRED:
                clauses.extend(f"{c} IS NOT NULL" for c in COLUMNS_FOR_FIELD[field])
            elif rule == FORBIDDEN:
                clauses.extend(f"{c} IS NULL" for c in COLUMNS_FOR_FIELD[field])
        lines.append(
            f"    CONSTRAINT ledger_event_fields_{event_type.value.lower()} "
            f"CHECK (event_type <> '{event_type.value}' OR ("
            + " AND ".join(clauses)
            + ")),"
        )
    return lines


def render_transfer_shape_check() -> str:
    return (
        "    CONSTRAINT ledger_event_transfer_shape CHECK ("
        "event_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT') OR ("
        "(listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL) OR "
        "(listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL "
        "AND cost_basis IS NULL))),"
    )


def render_internal_transfer_in_check() -> str:
    """ledger-replay/1.0 §6.3 (F2): an internal TRANSFER_IN carries no basis."""
    return (
        "    CONSTRAINT ledger_event_internal_transfer_in_no_cost_basis CHECK ("
        "event_type <> 'TRANSFER_IN' OR counterparty_account_id IS NULL "
        "OR cost_basis IS NULL),"
    )


def render_generated_region() -> str:
    lines = [render_event_type_check()]
    lines.extend(render_presence_checks())
    lines.append(render_transfer_shape_check())
    lines.append(render_internal_transfer_in_check())
    return "\n".join(lines)


def extract_generated_region(sql_text: str) -> str:
    """The text between the markers, or raise ValueError if absent."""
    lines = sql_text.split("\n")
    try:
        start = lines.index(BEGIN_MARKER)
        end = lines.index(END_MARKER)
    except ValueError:
        raise ValueError("generated-region markers not found") from None
    return "\n".join(lines[start + 1:end])


# --- replacement regions (CP1B-4) -------------------------------------------------------
#
# Migration 0002 holds the ORIGINAL generated region (frozen; it no longer equals
# `render_generated_region()` once FIELD_RULES changes, and must never be edited to
# make it so). A later migration that changes FIELD_RULES REPLACES the per-type
# constraints with one ALTER TABLE, delimited by the markers below and equal to
# `render_replace_region()`. The drift test compares FIELD_RULES with the region of the
# LATEST migration that has any generated region, so a rule change is satisfied by adding
# a new migration, never by editing an old one.

REPLACE_BEGIN_MARKER = (
    "-- BEGIN GENERATED-REPLACE: persistence.ledger_sql.render_replace_region (do not edit)"
)
REPLACE_END_MARKER = "-- END GENERATED-REPLACE"


def _generated_constraints() -> List[Tuple[str, str]]:
    """(name, `CONSTRAINT name CHECK (...)`) for every generated constraint."""
    out: List[Tuple[str, str]] = []
    for line in render_generated_region().split("\n"):
        text = line.strip().rstrip(",")
        name = text.split(" ")[1]
        out.append((name, text))
    return out


def render_replace_region() -> str:
    constraints = _generated_constraints()
    lines = ["ALTER TABLE ledger_event"]
    lines.extend("    DROP CONSTRAINT %s," % name for name, _ in constraints)
    adds = ["    ADD " + text for _, text in constraints]
    lines.append(",\n".join(adds) + ";")
    return "\n".join(lines)


def extract_replace_region(sql_text: str) -> str:
    lines = sql_text.split("\n")
    try:
        start = lines.index(REPLACE_BEGIN_MARKER)
        end = lines.index(REPLACE_END_MARKER)
    except ValueError:
        raise ValueError("generated-replace markers not found") from None
    return "\n".join(lines[start + 1:end])


def latest_generated_region(migration_texts: Sequence[str]) -> Tuple[str, str]:
    """`(kind, region)` from the newest migration text that carries a generated
    region: kind is "create" (0002 form) or "replace". Raises ValueError if none."""
    for text in reversed(list(migration_texts)):
        if REPLACE_BEGIN_MARKER in text:
            return "replace", extract_replace_region(text)
        if BEGIN_MARKER in text:
            return "create", extract_generated_region(text)
    raise ValueError("no migration carries a generated region")


# --- blank source_reference (CP1B-7) ---------------------------------------------------

def _whitespace_ranges() -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    start = prev = None
    for code in range(0x110000):
        if not chr(code).isspace():
            continue
        if start is None:
            start = prev = code
        elif code == prev + 1:
            prev = code
        else:
            ranges.append((start, prev))
            start = prev = code
    if start is not None:
        ranges.append((start, prev))
    return ranges


def render_blank_pattern() -> str:
    """A PostgreSQL ARE matching exactly the strings Python's `str.strip()` reduces to
    empty (every code point with `str.isspace()`), so SQL and Python agree on "blank".
    Escapes are `\\xHH..` (an ARE hex escape takes every following hex digit, which is
    safe here because each item starts with a backslash or ends the class)."""
    parts = []
    for lo, hi in _whitespace_ranges():
        parts.append("\\x%02x" % lo if lo == hi else "\\x%02x-\\x%02x" % (lo, hi))
    return "^[" + "".join(parts) + "]*$"
