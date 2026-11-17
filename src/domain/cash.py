"""Cash keying — `(account_id, currency)` (PRD §9.4; Tech Plan §13.E).

`CashKey` names the dimension a cash position is keyed on. It is a **key**,
not a balance: CP1-A does not store or compute an authoritative cash amount.
Per this increment's scope, balances are derived state produced in CP1-C from
ledger events, the same way `Position` is derived (Tech Plan §3.1). Storing
an independent mutable balance here would recreate exactly the "independent
mutable current value that can silently diverge from the ledger" PRD §9.1
forbids for positions, and PRD §9.4 requires cash to participate in the same
derived-state discipline as securities.

`CashKey` is a **value object** — its equality is its two fields, not an
internal ID (contrast `domain.instrument`/`domain.portfolio`'s entities,
which use `domain.entity_identity`'s identity-based equality). Two
`CashKey`s naming the same account and currency **are** the same key, which
is exactly the property that lets later ledger/cash code use it as a
dictionary/lookup key without inventing a separate identity for it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.currency import CurrencyCode
from domain.field_validation import require_type


@dataclass(frozen=True)
class CashKey:
    """`(account_id, currency)` — the keying dimension for a cash position.
    Carries no balance/amount field by design; see module docstring."""

    account_id: uuid.UUID
    currency: CurrencyCode

    def __post_init__(self) -> None:
        require_type(self, "account_id", self.account_id, uuid.UUID)
        require_type(self, "currency", self.currency, CurrencyCode)
