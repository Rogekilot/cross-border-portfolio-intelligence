# PD-0030 — CP2: two new reason codes; confirmed splits appended to the ledger (F8-B); CNH stays strict

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, answering three questions put by the main
session in a Claude Code session on 2026-10-01.
**Recorded by:** that main session. **Recorded, not decided.**
**Raised by:** `quant-analyst`, `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (`market-data/1.0`)
§10, items OD-1, OD-2 and OD-3.
**Amends:** PD-0006 / PD-0025 (the reason-code vocabulary; §1 only). Resolves STATUS F8 (§2).
Extends the scope of OQ-04b (PD-0028) (§3).

---

## 1. OD-1 — reason codes `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` added

Question: *"OD-1 (amends PD-0006/PD-0025): when two data sources disagree on a price, or a listing
has no price history at all, the metric is suppressed, but today it can't say why. Add reason
codes?"*

Owner's answer, verbatim: **"Add SOURCE_CONFLICT + MISSING_PRICE_HISTORY (Recommended)"**

The option as presented: both require a non-AVAILABLE state; the UI and AI layer can then tell the
user "sources disagree" or "no price history" instead of a bare "insufficient data".

Consequences: `src/product_contract/vocabulary.py` gains both codes, and `MetricResult` enforces
`sufficiency_state != AVAILABLE` for each. Design surfaces that render reason codes must cover them
before CP7 (design task, not part of this decision).

## 2. OD-2 (F8) — a confirmed split missing from the ledger is appended to it (F8-B)

Question: *"OD-2 (F8, user-visible): when the corporate-action feed and the issuer's filing both
confirm a stock split that the user's ledger is missing, what should happen?"*

Owner's answer, verbatim: **"Append it to the ledger (Recommended)"**

The option as presented (F8-B): the system appends a SPLIT event to the user's ledger once feed and
filing agree. It is visible, reversible by the user, and a no-op if the split is already recorded.
Positions still take splits only from the ledger, so replay stays reproducible.

Consequences and conditions carried with it:
- Positions take splits **only** from ledger `SPLIT` events. The corporate-action feed never
  applies a split directly (`market-data/1.0` §6).
- The appended event is an ordinary append-only `LedgerEvent` through the normal store path:
  idempotent, one live split per position per ex-date (migration 0007), reversible by the user
  through `REVERSAL`, never an edit of existing rows.
- It is **attributable**: its `source_reference` (or an equivalent recorded field) identifies the
  corporate-action evidence (feed record and filing) and the market-data version it came from, so
  the event is auditable back to its inputs (P9) and distinguishable from a user-entered event.
- A split whose feed and filing disagree, or that is only in one of them, is **not** appended; it
  is detected and flagged (the F8-A behaviour), as `market-data/1.0` §6 specifies.
- When the user's ledger already records the split differently (other date or ratio), the system
  does not append; valuation for the affected dates is suppressed and flagged per §6.
- Implementation belongs to a later CP2 increment; until it lands, F8-A applies.

## 3. OD-3 — CNH stays strict; CNH added to OQ-04b

Question: *"OD-3 (optional): no free source publishes an offshore CNH rate. How should CNH amounts
(RMB held at offshore brokers, HKEX RMB counters) be handled until the launch vendor?"*

Owner's answer, verbatim: **"Stay strict; add CNH to OQ-04b (Recommended)"**

The option as presented: CNH amounts are not converted (`INSUFFICIENT_DATA`, `MISSING_FX_HISTORY`)
until a licensed vendor supplies CNH; the CNY rate is never silently substituted.

Consequence: OQ-04b's scope (PD-0028) now includes an offshore CNH rate source.

## 4. What this decision does not do

It sets no tolerance or threshold (those are the Quant's, in `market-data/1.0`), selects no vendor,
and approves no gate.
