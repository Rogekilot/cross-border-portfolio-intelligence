# PD-0036 — Optional "acquired on" date for entry lots; no new reason codes for uncomputable returns

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, answering two questions put by the main
session in a Claude Code session on 2026-10-01.
**Recorded by:** that main session. **Recorded, not decided.**
**Raised by:** `quant-analyst`: PF-1 / ledger-replay OI-11 (with `ledger-replay/1.4`) and OD-P5
(`performance/1.1`).

---

## 1. PF-1 — an optional "acquired on" date: added

Question: *"Should opening positions and incoming transfers from outside the portfolio get an
optional 'acquired on' date? Without it, such lots sort by their entry date for FIFO and get no
reporting-currency cost basis when held in a foreign currency. Because the ledger is append-only,
this can't be filled in for old entries later. It's an additive ledger field plus a new migration."*

Owner's answer, verbatim: **"Add the optional field now (Recommended)"**

As presented: users may record the original purchase date on opening positions and external
transfers in; FIFO order and reporting-currency basis use it when present; blank stays allowed and
is handled as today.

Consequences:
- `LedgerEvent` gains an optional `acquired_on` date, permitted only on `OPENING_POSITION` and
  external `TRANSFER_IN` (security form, no counterparty). It must not be later than the event
  date. It is additive, so existing events and the CP1 fixture are unchanged.
- The schema change is a new migration (0014+). 0001–0013 stay frozen.
- How FIFO order (`ledger-replay/1.4` Ruling 0.5) and acquisition-date FX (`performance` Ruling
  3.7) use the date is the `quant-analyst`'s to specify, as a new convention-set id. Until then,
  the field is recorded but not read.
- A user-supplied date is a user fact, never inferred or fabricated (PRD §9.3).

## 2. OD-P5 — reason codes for uncomputable returns: none added

Question: *"For returns that can't be computed (zero/negative starting value, money-weighted return
with no unique solution, history too short), should the product get new reason codes? The Quant
recommends none: show 'insufficient data' with a specific detail instead."*

Owner's answer, verbatim: **"No new codes (Recommended)"**

Consequences: these results stay `INSUFFICIENT_DATA` with no reason code and a specific detail
(e.g. `NON_POSITIVE_BASE`, `IRR_UNIQUENESS_NOT_ESTABLISHED`, `PERIOD_SHORTER_THAN_ONE_YEAR`), as
PD-0006 and the engine already do. `CALCULATION_ERROR` is never used for them.

## 3. What this decision does not do

It sets no convention (the Quant's), changes no existing ledger event, and approves no gate.
