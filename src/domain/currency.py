"""Currency primitives (Tech Plan §13.E; `specs/PHASE_B_CP1_IMPLEMENTATION_
AUTHORITY.md` §2.2).

`CurrencyCode` — a normalized three-letter uppercase code. **This is format
normalization only.** Construction strips surrounding whitespace, upper-cases,
and requires exactly three ASCII alphabetic characters after normalization.
It is **not** a complete ISO-4217 validator: this module carries no list of
currencies that actually exist, so a syntactically well-formed but unassigned
code (e.g. `"ZZZ"`) constructs successfully. Do not read successful
construction as "this is a real ISO-4217 currency." No currency is
hard-coded — `USD`, `HKD`, `CNY`, and any other well-formed three-letter code
are equally valid inputs; this module defines no enum of supported
currencies. This is the shared primitive `LedgerEvent.currency` (CP1-B) will
use.

`Money` — CP1-A's minimal native monetary primitive: a `decimal.Decimal`
amount plus a `CurrencyCode`. `Decimal` only — a `float` (or any other
non-`Decimal` type, including `int`) is rejected at construction, per this
increment's hard invariant that money is never represented as a `float`.
Combining two `Money` values of different currencies raises
`CurrencyMismatchError` rather than converting — there is no FX rate
available at this layer, and no implicit FX is ever performed (P8). **This
module implements no FX engine and no conversion function of any kind** —
if a conversion boundary type is ever genuinely required, that is a decision
for a later increment, not something to add here silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class InvalidCurrencyCodeError(ValueError):
    """Raised when a `CurrencyCode` cannot be normalized to exactly three
    ASCII alphabetic characters. Format validation only — see module
    docstring; this is never raised because a code is not a real, assigned
    ISO-4217 currency."""


class InvalidMoneyAmountError(TypeError):
    """Raised when a `Money.amount` is not a `decimal.Decimal` — most
    commonly when a caller passes a `float`, which this product never uses
    to represent money."""


class NonFiniteMoneyAmountError(ValueError):
    """Raised when a `Money.amount` IS a `decimal.Decimal` — the type check
    `InvalidMoneyAmountError` guards passes — but is not finite:
    `Decimal("NaN")`, `Decimal("sNaN")`, `Decimal("Infinity")`, or
    `Decimal("-Infinity")`. Deliberately a `ValueError`, not a
    `TypeError`/`InvalidMoneyAmountError`: the received value's Python type
    is correct (it genuinely is a `Decimal`); what is wrong is its content —
    a monetary amount that is not a real, finite number. This module raises
    no scale/precision/rounding rule of any kind; this is the one content
    check CP1-A's `Money` makes, and it is exactly "finite or not,"
    nothing more."""


class CurrencyMismatchError(ValueError):
    """Raised when an operation would combine two `Money` values carrying
    different currencies. Refused rather than silently converted: CP1-A has
    no FX rate available at this layer, and P8 forbids inventing one."""


@dataclass(frozen=True)
class CurrencyCode:
    """A normalized three-letter uppercase currency code.

    Equality/hash are the default frozen-dataclass, field-based behaviour —
    deliberately, unlike the identity-based equality used by
    `domain.instrument`/`domain.portfolio`'s entities: a `CurrencyCode` is a
    **value**, not an entity with an internal identity distinct from its own
    value. Two `CurrencyCode("usd")` and `CurrencyCode("USD")` are, and
    should be treated as, the same value.
    """

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise InvalidCurrencyCodeError(
                f"currency code must be a str, got {type(self.code)!r}"
            )
        normalized = self.code.strip().upper()
        if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
            raise InvalidCurrencyCodeError(
                "currency code must normalize to exactly three ASCII "
                f"alphabetic characters, got {self.code!r} (normalized: "
                f"{normalized!r}). This is format validation only — see "
                "module docstring; it is not an ISO-4217 membership check."
            )
        # Normalizing a frozen dataclass's own field inside __post_init__,
        # before construction returns to the caller, is the standard,
        # documented technique for a frozen dataclass with a derived/
        # normalized field. This is not the same vector as a caller reaching
        # past this type's public interface after construction (see
        # product_contract/metric_state.py's module docstring for that,
        # different, concern).
        object.__setattr__(self, "code", normalized)

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True)
class Money:
    """`decimal.Decimal` amount + `CurrencyCode`. CP1-A's minimal native
    monetary primitive — not a ledger entry and not a balance; it carries a
    single native-currency amount and refuses to combine across currencies.
    """

    amount: Decimal
    currency: CurrencyCode

    def __post_init__(self) -> None:
        if isinstance(self.amount, float):
            raise InvalidMoneyAmountError(
                "Money.amount must be a decimal.Decimal, never a float "
                f"(got {self.amount!r}); construct with Decimal('...') "
                "instead."
            )
        if not isinstance(self.amount, Decimal):
            raise InvalidMoneyAmountError(
                f"Money.amount must be a decimal.Decimal, got "
                f"{type(self.amount)!r}"
            )
        # is_finite() is a quiet Decimal predicate — unaffected by context,
        # raises no signal, and performs no comparison, including against an
        # sNaN payload (Python decimal docs: "This operation is unaffected
        # by context and is quiet"). Placed after the Decimal type check
        # above so float/int amounts keep raising InvalidMoneyAmountError
        # exactly as before; a type-correct but non-finite Decimal now
        # raises NonFiniteMoneyAmountError instead of constructing silently.
        if not self.amount.is_finite():
            raise NonFiniteMoneyAmountError(
                "Money.amount must be a finite decimal.Decimal (NaN, sNaN, "
                f"Infinity and -Infinity are all rejected), got {self.amount!r}"
            )
        if not isinstance(self.currency, CurrencyCode):
            raise TypeError(
                f"Money.currency must be a CurrencyCode, got "
                f"{type(self.currency)!r}"
            )

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"cannot combine Money in {self.currency} with Money in "
                f"{other.currency} — no implicit FX conversion is performed "
                "by this primitive (P8)."
            )

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)
