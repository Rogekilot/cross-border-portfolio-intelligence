"""Shared field-type-validation helper for CP1-A domain types (CP1-A
correction round, finding F1 — "type-validate every annotated field,
content-validate nothing new").

Python does not enforce type annotations, and every module in this package
uses `from __future__ import annotations`, so every annotation here is an
inert string at runtime — nothing about a class definition stops a caller
from constructing e.g. `Portfolio(portfolio_id="not-a-uuid", ...)`. Before
this correction round, none of `domain.portfolio`, `domain.instrument`, or
`domain.cash` validated field types at all, so a wrongly-typed ID or
currency constructed silently and split identity/lookup keys downstream (a
`str` `user_id` compares unequal to the correctly-typed `uuid.UUID` a
different code path constructed, for example).

This module defines one exception and three small, explicit helpers, each
invoked **per field, by name, from the owning class's own
`__post_init__`**. It contains no generic/reflective validator that walks
`dataclasses.fields(...)` or `typing.get_type_hints(...)` — both are
explicitly out of scope for this round, and postponed annotations make
`dataclasses.fields(...).type` a string rather than a type object, so a
`dataclasses.fields`-driven validator could not even resolve the expected
type here without reintroducing `typing.get_type_hints`. Calling these
helpers explicitly, one line per field, keeps a validation failure
unambiguous about which field failed, in which class, and keeps the whole
mechanism auditable by reading each `__post_init__` directly.

**Content boundary.** These helpers check only whether a value IS an
instance of the expected Python/domain type (or, for `bool`, exactly that
type — see `require_exact_bool`). None of them inspects what a `str` value
*says* — ticker syntax, MIC/exchange vocabulary, FIGI format, domicile
vocabulary, name rules, uniqueness, or ISO-4217 membership are all out of
this round's scope, and out of this module's job.

**No coercion, ever.** Every helper below raises on a type mismatch; none of
them converts, casts, or accepts a differently-typed-but-equivalent value (a
`str` UUID, a raw `"USD"` string, a truthy int for `is_active`). Wrong type
means rejection, always.
"""

from __future__ import annotations

from typing import Type


class DomainFieldTypeError(TypeError):
    """Raised when a CP1-A domain entity/value field receives a value of the
    wrong Python/domain type at construction — including via
    `dataclasses.replace(...)`, which re-invokes `__init__`/`__post_init__`
    exactly like ordinary construction, so a replacement supplying a wrong
    type is rejected the same way a fresh construction is.

    Chosen as a `TypeError` subclass, deliberately: every violation this
    module raises is a wrong Python/domain *type* supplied for a field —
    never a type-correct value this module judges invalid on content (that
    is a `ValueError` concern, and out of this module's scope entirely; see
    `domain.currency.Money`'s non-finite-`Decimal` check for the one place
    CP1-A raises a content-level `ValueError` instead, a genuinely different
    failure shape — a finite/non-finite `Decimal` is still, unambiguously, a
    `Decimal`).

    The message always names the class, the field, the expected type, and
    the received type, so a test can assert on the failure deterministically
    without parsing free text for identity.
    """


def require_type(entity: object, field_name: str, value: object, expected: Type) -> None:
    """Raise `DomainFieldTypeError` unless `isinstance(value, expected)`.

    Not used for `bool`-typed fields: `isinstance(True, int)` is `True`
    because `bool` subclasses `int` in Python, which is the *reverse* of the
    hazard this round closes (a caller passing `1`/`0`/`"true"` where a
    `bool` is required) — that direction needs `require_exact_bool` instead.
    """

    if not isinstance(value, expected):
        raise DomainFieldTypeError(
            f"{entity.__class__.__name__}.{field_name} must be a "
            f"{expected.__name__}, got {type(value).__name__} ({value!r})"
        )


def require_optional_type(
    entity: object, field_name: str, value: object, expected: Type
) -> None:
    """Like `require_type`, but `None` is also accepted — for the two fields
    whose annotation is `Optional[...]` (`Listing.figi`,
    `Issuer.issuer_domicile`). `None` is an ordinary, valid state for both (a
    missing FIGI, an unrecorded domicile) and must never be rejected;
    anything else that is not `expected` still is.
    """

    if value is not None and not isinstance(value, expected):
        raise DomainFieldTypeError(
            f"{entity.__class__.__name__}.{field_name} must be a "
            f"{expected.__name__} or None, got {type(value).__name__} "
            f"({value!r})"
        )


def require_exact_bool(entity: object, field_name: str, value: object) -> None:
    """Raise `DomainFieldTypeError` unless `type(value) is bool` exactly —
    not `isinstance(value, bool)`. `bool` subclasses `int` in Python, so an
    `isinstance`-based int check would accept a `bool` as an `int` and (more
    importantly for this round's defect) an `isinstance(x, bool)` check
    alone would still leave `1`/`0` rejected correctly — but the exact-type
    form is used here anyway, deliberately, as the unambiguous, documented
    way to reject every non-`bool` value this round names: `1`, `0` are
    `int`, not `bool` (`type(1) is bool` is `False`); `"true"` is `str`, not
    `bool` (`type("true") is bool` is `False`). Only an actual `bool`
    (`True`/`False`) passes.
    """

    if type(value) is not bool:
        raise DomainFieldTypeError(
            f"{entity.__class__.__name__}.{field_name} must be a bool, got "
            f"{type(value).__name__} ({value!r})"
        )
