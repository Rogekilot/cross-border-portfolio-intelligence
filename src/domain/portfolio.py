"""Portfolio-context domain entities — `User`, `Portfolio`, `Account`
(Tech Plan §3.1, §13.A/§13.E; PRD §7.2, §7.3, §8.1).

**Canonical identity.** Every entity below carries its own immutable
`uuid.UUID` (`user_id`, `portfolio_id`, `account_id`) — the internal ID, per
`domain.instrument`'s identity ruling applied consistently across the whole
model (PD-0021 §2.1), is the only join/persistence key. None of the three
currently has an external identifier of the kind `Issuer`/`Instrument`/
`Listing` correct (no ticker/FIGI equivalent here) — they exist purely for
internal identity and ownership/containment structure.

**Entity equality.** All three types use `eq=False` plus an explicit,
`*_id`-based `__eq__`/`__hash__` (`domain.entity_identity`) rather than the
default frozen-dataclass field-by-field comparison, for the same reason
`domain.instrument` gives in full: identity, not attribute content, is what
"the same entity" means for a row with its own internal ID. See
`domain.entity_identity`'s module docstring for the complete rationale.

**Scope.** No ledger, no cash balance, no position: those are CP1-B/CP1-C.
`Account` here is deliberately thin — an identity/containment record only.
See `domain.cash.CashKey` for the `(account_id, currency)` keying this
supports, and this module's own `Account` docstring for why there is no
single account-level currency field.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from domain.currency import CurrencyCode
from domain.entity_identity import identity_eq, identity_hash
from domain.field_validation import require_type


@dataclass(frozen=True, eq=False)
class User:
    """A stable, immutable internal identity. No auth/profile infrastructure
    — CP1-A's `User` carries nothing but its own ID; the PRD's onboarding/
    auth model is out of this increment's scope."""

    user_id: uuid.UUID

    def __post_init__(self) -> None:
        require_type(self, "user_id", self.user_id, uuid.UUID)

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "user_id")

    def __hash__(self) -> int:
        return identity_hash(self, "user_id")


@dataclass(frozen=True, eq=False)
class Portfolio:
    """Owned by exactly one `User` (`user_id`); exactly one reporting
    currency (PRD §8.1, FR-001).

    `reporting_currency` **names** the currency later reporting-currency
    figures will be computed in (Tech Plan §13.E) — it does not compute, and
    this module does not build, any FX conversion. A `Portfolio`'s
    `reporting_currency` and any `Listing`'s `trading_currency`
    (`domain.instrument`) coexist independently; nothing in this module ever
    reads one to rewrite the other.
    """

    portfolio_id: uuid.UUID
    user_id: uuid.UUID
    reporting_currency: CurrencyCode

    def __post_init__(self) -> None:
        require_type(self, "portfolio_id", self.portfolio_id, uuid.UUID)
        require_type(self, "user_id", self.user_id, uuid.UUID)
        require_type(
            self, "reporting_currency", self.reporting_currency, CurrencyCode
        )

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "portfolio_id")

    def __hash__(self) -> int:
        return identity_hash(self, "portfolio_id")


@dataclass(frozen=True, eq=False)
class Account:
    """A manual account container (PRD §7.3) — an organizational/accounting
    object, not a live brokerage integration. Scoped to one `Portfolio`
    (`portfolio_id`).

    **Deliberately has no account-level currency field.** PRD §7.3's own
    examples (US Broker, Futu HK, China Brokerage, Cash Account) are ordinary
    containers that can hold cash and instruments in more than one currency;
    currency is not a property of the account. It is a property of each cash
    position, keyed `(account_id, currency)` — see `domain.cash.CashKey`.

    `name` is the minimal identity/type information CP1-A needs for later
    event/cash association: the account label a user assigned (e.g. "Futu
    HK"). This module does not introduce an account-type taxonomy (e.g.
    brokerage vs. cash-only, or any enum resembling one) — the PRD does not
    define one, and nothing in CP1-A's scope needs one: later ledger/cash
    code associates by `account_id`, not by a type field.
    """

    account_id: uuid.UUID
    portfolio_id: uuid.UUID
    name: str

    def __post_init__(self) -> None:
        require_type(self, "account_id", self.account_id, uuid.UUID)
        require_type(self, "portfolio_id", self.portfolio_id, uuid.UUID)
        require_type(self, "name", self.name, str)

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "account_id")

    def __hash__(self) -> int:
        return identity_hash(self, "account_id")
