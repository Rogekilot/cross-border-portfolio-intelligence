"""CP1-A — domain identities and currency foundation.

Authority: `implementation/FEATURE_TECH_PLAN.md` §3 (T3 domain model) and §13
(the Phase-B addendum — §13.A architecture, §13.C identity, §13.E currency),
synchronized for Engineer reading at
`specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md` §2.1-§2.2 (`PD-0021`).

This package carries:

- `domain.currency` — `CurrencyCode` (a normalized three-letter uppercase
  currency-code primitive; format normalization only, not ISO-4217
  membership validation) and `Money` (a `decimal.Decimal`-only native
  monetary primitive that refuses to combine different currencies).
- `domain.entity_identity` — the shared identity-equality helper used by
  every entity below (see its module docstring for the rationale).
- `domain.portfolio` — `User`, `Portfolio`, `Account`.
- `domain.instrument` — `Issuer`, `Instrument`, `Listing`, `SecurityType`.
- `domain.cash` — `CashKey`, the `(account_id, currency)` cash-keying
  dimension.
- `domain.ledger` — (CP1-B step 1) `LedgerEvent`, `EventType`, `SplitRatio`,
  `IdempotencyKey`, the per-type `FIELD_RULES`, and the list of cross-event
  rules deferred to persistence (`CROSS_EVENT_RULES_DEFERRED`). Pure
  in-memory types: no storage, no positions, no balances.

**What this package is not, by CP1-A's declared scope:**

- **Persistence-independent.** No PostgreSQL tables, SQLAlchemy models,
  Alembic migrations, SQL repositories, sessions, or connection code. These
  objects are designed to map cleanly to PostgreSQL later — nothing more.
- **No CP1-C/D leakage.** (CP1-A itself had no `LedgerEvent`; the ledger
  event types arrived with CP1-B step 1 in `domain.ledger`.) No point-in-time
  reconstruction, no `Position`, no golden fixture. No authoritative cash
  balance is stored anywhere here — `domain.cash.CashKey` is a keying
  dimension only; balances are derived state, CP1-C's job.
- **No FX engine and no conversion boundary type.** Reporting currency
  (`Portfolio.reporting_currency`) and native/trading currency
  (`Listing.trading_currency`) coexist without any conversion function
  anywhere in this package (P8; Tech Plan §13.E).
- **No methodology decisions.** No cost basis, no lot-depletion method, no
  cross-listing economic-equivalence ratio (e.g. ADR-vs-ordinary), no return
  or fractional-share convention. Those remain `quant_analyst`'s authority
  (Tech Plan §13.E's Quant boundary) and are not decided here.
"""
