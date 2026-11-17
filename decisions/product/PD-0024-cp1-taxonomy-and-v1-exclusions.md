# PD-0024 — CP1 ledger taxonomy additions; margin and short positions excluded from V1

**Status:** accepted
**Date:** 2026-09-30
**Decided by:** the designated **human product owner**, answering four questions put by the
main session in a Claude Code session on 2026-09-30.
**Recorded by:** that main session. **Recorded, not decided.**
**Raised by:** `quant-analyst`, `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (convention
set `ledger-replay/1.0`), findings F3 and F4 and owner items O1–O3.
**Reopens:** nothing. **Supersedes:** nothing. PRD §9.5 lists a *minimum* taxonomy; §1 and
§2 below add to it and remove nothing.

---

## 1. Currency conversion inside one account — added in CP1

Question: *"Currency conversion inside one account (e.g. converting USD cash to HKD in the
same brokerage account) can't be recorded correctly with the current event types.
Cross-border users do this routinely. Should CP1 add an FX conversion event?"*

Owner's answer, verbatim: **"Add it in CP1 (Recommended)"**

The option as presented: a new event that moves cash from one currency to another in one
account, recording both amounts as given (no rate is computed).

Consequences: the Quant defines its replay effect and flow classification first; the
engineer then implements it in `src/domain/ledger.py` and the schema. The event records
the two amounts the source reports. **No FX rate is computed, stored or implied by the
engine**, and it does not become an FX observation (tech plan §13.E: FX observations belong
to the market-data layer).

## 2. Interest charged — `INTEREST_CHARGED` added

Question: *"Interest charged (e.g. margin or debit interest) has no event type. INTEREST is
credits only, and folding it into FEE loses a distinction later attribution needs. Add a
new type?"*

Owner's answer, verbatim: **"Add INTEREST_CHARGED (Recommended)"**

The option as presented: a cash-only event type.

## 3. Margin accounts — not in V1

Question: *"Does V1 support margin accounts, i.e. sustained broker-financed negative cash
balances?"*

Owner's answer, verbatim: **"Not in V1 (Recommended)"**

The option as presented: a negative cash balance is still recorded and shown as a valid
ledger state (e.g. between trade and settlement), but V1 does not claim to model
financing, margin requirements or leverage analytics.

## 4. Short positions — not in V1

Question: *"Does V1 support short positions?"*

Owner's answer, verbatim: **"Not in V1 (Recommended)"**

The option as presented: a negative share quantity is flagged as a data inconsistency,
with no quantity shown and never clamped to zero (the Quant's convention in
`ledger-replay/1.0` §9).

## 5. What this decision does not do

It does not approve any gate, does not add any other corporate-action type, does not
decide lot depletion, fee capitalization or the fractional-split convention, and does not
change any product invariant.
