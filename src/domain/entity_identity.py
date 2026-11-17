"""Shared identity-equality helper for CP1-A entities.

**The problem this module exists to solve.** A default frozen-dataclass
`__eq__` compares every field. For a value type (e.g. `domain.currency.
CurrencyCode`, `domain.cash.CashKey`) that is exactly right — two instances
with the same field values genuinely are the same value. For an **entity**
with its own internal, immutable ID (`User`, `Portfolio`, `Account`, `Issuer`,
`Instrument`, `Listing` — every type in `domain.portfolio` and
`domain.instrument`), field-by-field comparison is wrong for two independent
reasons this increment's hard invariants name explicitly:

1. **A correction must not look like a different entity.** Correcting an
   external identifier (a ticker, a FIGI) via `dataclasses.replace(...)`
   produces a new Python object carrying the corrected attribute and the
   same internal ID. Field-by-field equality would make that object compare
   *unequal* to the pre-correction one, which is backwards — it is the same
   row, corrected.
2. **Shared attribute values must not look like the same entity.** Two
   different `Listing`s that happen to share a ticker (tickers are reused
   across exchanges and over time, and are explicitly a "user-facing
   lookup/search attribute, not the database primary key" — PRD §10.1) would
   compare *equal* under field-by-field comparison, which is simply wrong.

**The fix.** Every entity type is declared `@dataclass(frozen=True, eq=False)`
and defines its own `__eq__`/`__hash__` via `identity_eq`/`identity_hash`
below, naming its own internal-ID field explicitly (e.g. `"listing_id"`).
Identity — the internal ID — is what "the same entity" means in this model,
never a ticker, FIGI, name, or any other attribute.

Two instances of *different* entity classes are never equal, even if (by
programmer error) they were somehow constructed with numerically-equal ID
values in different fields — `identity_eq` requires an exact class match
first. Comparison against an object of an unrelated type returns
`NotImplemented` (not an exception and not `True`/`False` directly) so Python
falls back to its normal protocol, which correctly resolves to `False` for
`==` and raises `TypeError` only for ordering operators these entities do not
define in the first place.
"""

from __future__ import annotations

from typing import Any


def identity_eq(entity: object, other: object, id_field: str) -> Any:
    """`entity.__eq__` body: `other` must be the exact same class as `entity`
    and carry an equal value in `id_field`. Returns `NotImplemented` for any
    other type, per the standard `__eq__` protocol."""

    if other.__class__ is not entity.__class__:
        return NotImplemented
    return getattr(entity, id_field) == getattr(other, id_field)


def identity_hash(entity: object, id_field: str) -> int:
    """`entity.__hash__` body: hashes on `(class, id value)` so two entities
    of different classes never collide by coincidence, and two instances of
    the same entity with the same ID (e.g. before/after an external-
    identifier correction) hash identically — required for `identity_eq`
    equal objects to remain usable as `set`/`dict` keys."""

    return hash((entity.__class__, getattr(entity, id_field)))
