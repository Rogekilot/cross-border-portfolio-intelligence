# PD-0038 — HG2 (Financial Core Proof): APPROVED WITH CONDITIONS

**Status:** accepted
**Date:** 2026-10-02
**Decided by:** the designated **human product owner** (the product owner), answering the gate question
put by the main session in a Claude Code session on 2026-10-02.
**Recorded by:** that session. **Recorded, not decided.**
**Gate package:** `reviews/gates/HG2_GATE_REVIEW.md` (§14 filled in from this PD).
**Evidence:** `reviews/gates/HG2_EVIDENCE/synthetic/` (pack A) and
`reviews/gates/HG2_EVIDENCE/real_slice/` (pack B, local and git-ignored).

---

## Before the decision

At the owner's choice ("Run slice first"), the real-slice steps of package §12.3 were run:

- **Calendars:** the owner checked the NYSE and ECB calendars ("calendars checked") and
  registered them.
- **FX:** the owner downloaded Frankfurter FX for 2026-05-08..09-30: 104 rows, exactly the
  calendar's fixing days.
- **Build:** the main session built pack B. It excluded the January 2025 FX vintage, a choice
  recorded in the pack.
- **Pack B result** (all AVAILABLE):
  - value 10,480.33 USD / 9,229.70 EUR / 70,265.74 CNY;
  - G 480.33; TWR = MWR 0.048033 since inception;
  - 0 identity failures; 21 of 21 computations reproduced.
- **Main-session hand check:** the headline figures were recomputed from the raw Alpha Vantage
  and Frankfurter files without engine code. All match.

## The decision

Question: *"With the real slice in front of you (10,480.33 USD / 9,229.70 EUR / 70,265.74
CNY, matching my hand check; 0 identity failures; 21/21 reproduced), what is your HG2
decision?"*

Owner's answer, verbatim: **"Approve with conditions (Recommended)"**

**HG2 = APPROVED WITH CONDITIONS.** The conditions, as presented with the option:

1. **Fix CP3-15 and CP3-21 as the first CP4 task.**
   - CP3-15: the detection-policy check runs per (listing, ex-date).
   - CP3-21: the vintage-disagreement report compares decimals by value.
2. **Apply the minor-unit confirmation (PD-0037)** so the engine marks itself conformant:
   - the `quant-analyst` marks the rows CONFIRMED;
   - the `engineer` updates `src/performance/rounding.py`.
3. **Before CP4 results are presented as real:** a real CN/HK price source, or an explicit
   owner decision to go without one.
4. **Register the HK and CN calendars** (`HKEX_SESSIONS`, `CN_A_SESSIONS`, after the owner has
   checked them) **before any real HK or CN data is used.**

## Consequences

- **CP4–CP9 may proceed as production-intended work** (PRD §38.4), subject to the
  conditions:
  - conditions 1 and 2 come first in CP4;
  - condition 3 gates presenting CP4 results as real;
  - condition 4 gates real HK/CN data.
- The convention sets the gate covered (`ledger-replay/1.5`, `market-data/1.10`,
  `performance/1.10`) were open to challenge here. The owner raised none.
- Still open and unchanged:
  - OQ-04b: a licensed launch vendor before private beta;
  - PD-0032: personal/academic use, internal-only data;
  - the max-drawdown methodology debt (a CP4 matter);
  - the LOW residuals in package §8.
- The real-slice pack is computed from internal-use payloads. It stays local and is not
  committed (PD-0027/0028).

## What this decision does not do

It does not approve any later gate (HG3+). It does not admit a CN/HK source or a launch vendor,
and it does not ratify methodology beyond what the gate covered.
