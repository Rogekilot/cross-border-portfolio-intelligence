"""CP1-B step 2 — PostgreSQL persistence for the append-only ledger.

Modules:

- `persistence.migrator` — numbered plain-SQL migrations (`migrations/*.sql`)
  applied by a small runner with checksums (PD-0023 §3; no SQLAlchemy, no
  Alembic).
- `persistence.ledger_sql` — renders the per-event-type CHECK constraints from
  `domain.ledger.FIELD_RULES`, so the SQL cannot silently drift from the
  domain model.
- `persistence.ledger_store` — `append_event`, the idempotent append.
- `persistence.connection` — libpq connection-string building and the lazy
  `psycopg` import.

`psycopg` (PD-0023 §3) is imported only inside `connection.connect`. Importing
this package never requires it, so the default test suite runs on an
environment without the driver.

Not here (CP1-C): positions, cash balances, replay. Nothing in this package
encodes lot depletion, split fractional treatment, which date governs replay,
or reversal as-of semantics (PD-0021 §9).
"""
