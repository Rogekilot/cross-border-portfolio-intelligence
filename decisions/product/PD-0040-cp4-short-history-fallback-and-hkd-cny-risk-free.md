# PD-0040 — CP4: default view on short history; HKD/CNY risk-free sources

**Status:** accepted
**Date:** 2026-10-02
**Decided by:** the designated **human product owner**, answering two questions put by the main
session in a Claude Code session on 2026-10-02.
**Recorded by:** the main session (PM). **Recorded, not decided.**
**Source of the questions:** `risk/1.0` §13 (`methodology/CP4_RISK_CONVENTIONS.md`), OD-R1 and OD-R2,
written by `quant-analyst`.

---

## The decisions

| # | Question put | Owner's answer, verbatim | Option text the owner selected |
|---|---|---|---|
| OD-R1 | "When a portfolio is younger than 3 years, the default 3Y risk request is refused. What should the default view show?" | **"Labelled fallback (Recommended)"** | Automatically show the maximum available window with its true dates, observation count and LIMITED state (e.g. 'since 2025-03-07, 41 weekly observations'). The 3Y refusal stays visible in the evidence. |
| OD-R2 | "Where should HKD and CNY risk-free rates come from? (USD uses US Treasury 13-week bills, as you chose.)" | **"Sovereign bills, none meanwhile (Recommended)"** | Look for HKMA Exchange Fund Bills (91-day) and ChinaBond 3M series and attest their terms; until then HKD/CNY-reporting portfolios show no Sharpe, Sortino, downside deviation or alpha. |

## Consequences

**OD-R1:**
- When the default 3Y request is refused, the default view sends `MAX_AVAILABLE`. The result carries
  its actual window, observation count and state.
- The 3Y refusal stays in the evidence.
- No result is labelled with a window it did not use (`risk/1.0` Ruling 7.2 is unchanged).
- This is a request-composition rule for the default view. It sits in the service layer, not in the
  method.

**OD-R2:**
- **USD:** US Treasury Daily Treasury Bill Rates, 13-week coupon equivalent. **Owner action:** attest
  its terms against `risk/1.0` Ruling 4.6 and register its publication calendar, drafted by the session
  as under PD-0034.
- **HKD and CNY:** the HKMA Exchange Fund Bills (91-day) and ChinaBond 3M series are sought.
  **Owner action:** check and attest their terms when found.
- **Until then:** a portfolio reporting in HKD or CNY shows Sharpe, Sortino, downside deviation and
  alpha as `INSUFFICIENT_DATA`, detail `NO_RISK_FREE_SOURCE`. The other metrics are unaffected.
- HIBOR and SHIBOR are not adopted.
- The source details in `risk/1.0` §14 are from memory and must be confirmed at attestation.

## What this decision does not do

It admits no source and approves no HG3 result.

---

## Addendum, 2026-10-02: the fallback trigger (OD-R1 scope, `risk/1.2` OI-R8)

`risk/1.2` Ruling 7.7 read OD-R1 as also covering a 3-year history that contains a gap. The main
session put that reading to the owner.

**Question put:** "PD-0040's fallback (show the longest available window when 3Y is refused): should it
also apply when 3 years of history exist but contain a gap (e.g. a period with no capital or
unpriceable data), not only when the portfolio is younger than 3 years?"

**Owner's answer, verbatim:** **"Gaps too (Recommended)"**

**The option text the owner selected:** "The Quant's reading: any history refusal (too young, a gap, a
zero-capital period) falls back to the longest clean window ending today, labelled with its true dates
and state. A missing benchmark is never a fallback trigger."

**Consequences:**
- Ruling 7.7 stands as written.
- The fallback shows the result's **true** state. That may be `INSUFFICIENT_DATA` (fixture R9-Z1).
  OD-R1's option text gave "LIMITED" as an example, not as a promise of a number (P5).
