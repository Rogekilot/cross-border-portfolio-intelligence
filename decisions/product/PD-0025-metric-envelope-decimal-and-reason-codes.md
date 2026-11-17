# PD-0025 — Metric envelope: exact `Decimal` values, and three new reason codes

**Status:** accepted
**Date:** 2026-09-30
**Decided by:** the designated **human product owner**, answering two questions put by the
main session in a Claude Code session on 2026-09-30.
**Recorded by:** that main session. **Recorded, not decided.**
**Amends:** PD-0006 (metric-state vocabulary; confirmed at HG1) by adding three reason
codes; the envelope shape set by PD-0006 and PD-0007 (`sufficiency_state` + nullable
`reason_code`; `value is None` iff `INSUFFICIENT_DATA`) is unchanged.
**Raised by:** the CP1-C `engineer` report (replay needs states the vocabulary cannot express,
and exact values the envelope cannot carry).

---

## 1. Reason codes — three added

Question: *"The metric-state vocabulary (PD-0006, confirmed at HG1) has no reason code for
three situations replay now produces: a result blocked by an unresolved methodology
convention (e.g. fractional split), a ledger inconsistency (e.g. negative share quantity),
and a date before a snapshot account's history begins. How should these be expressed?"*

Owner's answer, verbatim: **"Add 3 reason codes (Recommended)"**

The option as presented: add `UNRESOLVED_CONVENTION`, `LEDGER_INCONSISTENT` and
`NOT_RECONSTRUCTABLE` to `ReasonCode`, each requiring a non-`AVAILABLE` state; the UI and
AI layer see one vocabulary; the engineer's separate `ReplayCause` enum is removed.

Consequences: `src/product_contract/vocabulary.py` gains the three codes, and
`metric_state.MetricResult` enforces that each requires `sufficiency_state != AVAILABLE`
(as for the existing codes other than `STALE_DATA`). Design surfaces that render reason
codes (`designs/FEATURE_DESIGN.md` §D3) must cover them before CP7; that is a design task,
not part of this decision.

## 2. Metric value type — `Decimal` only

Question: *"The approved metric envelope (MetricResult) types its value as float, but
money, quantities and cost basis must be exact Decimals. How should the envelope carry
values?"*

Owner's answer, verbatim: **"Decimal only (Recommended)"**

The option as presented: `MetricResult.value` becomes `Decimal` everywhere, statistics
included; one exact type; no float can leak into a financial fact; existing tests are
updated to match.

Consequences: `MetricResult.value` is `Optional[Decimal]`, finite, and a `float` is
rejected at runtime. The CP1-C `StatedValue` duplicate envelope is removed in favour of
`MetricResult`. Statistical methods (later checkpoints) produce `Decimal` under a precision
and rounding convention the Quant records in the methodology registry.

## 3. What this decision does not do

It does not set any sufficiency threshold (those remain the Quant's), does not change the
PD-0007 value/state rule, and does not approve any gate.
