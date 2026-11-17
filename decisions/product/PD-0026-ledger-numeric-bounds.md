# PD-0026 — Ledger numeric bounds: below 10^30, at most 24 decimal places

**Status:** accepted
**Date:** 2026-09-30
**Decided by:** the designated **human product owner**, answering a question put by the main
session in a Claude Code session on 2026-09-30.
**Recorded by:** that main session. **Recorded, not decided.**
**Raised by:** technical review finding R3-1 (`reviews/TECH_REVIEW.md` §21): unbounded
`NUMERIC` let the ledger store values replay could not handle (a `1E+5000` deposit made
replay raise for the whole portfolio; 5,000 extreme values took 84 s to replay).
**Implemented by:** `src/persistence/migrations/0008_bounds_append_xid_and_lock_scope.sql`
(engineer), with `domain.ledger.numeric_bounds_violation` as the Python statement of the
same bound, used by tests.

---

## The decision

Question: *"Migration 0008 caps every stored quantity and amount (quantity, amount, bought
amount, cost basis, split ratios) at below 10^30 (at most 30 integer digits) and at most 24
decimal places. Anything larger is refused when recorded. The largest realistic values (a
JPY or CNY portfolio in the trillions, a 10^15 token supply) need about 16 digits, and the
finest (18-decimal crypto units) fit with 6 digits to spare. Approve these limits?"*

Owner's answer, verbatim: **"Approve as proposed (Recommended)"**

The option as presented: below 10^30, at most 24 decimals; recorded as a PD; replay still
handles any older, larger rows safely as a scoped "calculation error" state.

## Consequences

- `ledger_event.quantity`, `amount`, `bought_amount`, `cost_basis`, `split_new` and
  `split_old` must each be below 10^30 in absolute value and have a stored scale of at most
  24 (trailing zeros count, as PostgreSQL `scale()` counts them). Named CHECK constraints;
  a violation is the typed `LedgerValueOutOfRangeError`.
- The bound applies at append, in the database. Domain constructors do not enforce it, so
  replay stays robust for rows stored before 0008 (it reports `CALCULATION_ERROR` /
  `VALUE_NOT_REPRESENTABLE` for that value only).
- Changing the bound later is a new migration and a new PD.

## What this decision does not do

It sets no rounding convention (still open as Quant OI-8), changes no sufficiency
threshold, and approves no gate.
