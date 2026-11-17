# PD-0014 — Freshness gains a comparability dimension; every material financial claim must be traceable to the facts it describes

**Status:** accepted
**Date:** 2026-09-06
**Decided by:** the designated **human product owner**, on a narrow authorization to reopen an
accepted foundation.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Supersedes:** `designs/FEATURE_DESIGN.md` §D3.2's universal "not degraded" justification, to
the minimum extent required. **Amends:** §D5's freshness contract.
**Evidence:** `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md`;
`reviews/gates/HG1_ROUND4_P1_CONTRADICTIONS.md`.

> **Scope of the authorization, in the owner's words:** *"a narrow authorization, not permission
> to reopen the broader accepted architecture or begin Priorities A–E."* Everything not named
> below stays accepted and closed: the C+B direction, the four-surface IA, the metric-state
> vocabulary (PD-0006, PD-0007), the deterministic-analytics boundary, the Proof Packet
> architecture, the OCR safety model, scenario isolation, AI grounding.

---

# Part 1 — The comparability contradiction

## 1.1 What was contradictory

`designs/FEATURE_DESIGN.md` §D3.2 justifies rendering `AVAILABLE` + `STALE_DATA` without
degrading the value, on the reasoning that staleness is not degradation. `js/data.js:450`
applies that rule faithfully, producing:

> "One input market (Mainland China A-shares) is priced as of a stale print; the comparison
> remains computable and is not degraded — see the freshness indicator."

`quant_analyst` established that the rule **is correct for a single-leg metric and wrong for a
two-leg comparison**, and stopped rather than resolving it. That judgment is upheld here.

**Why it is a genuine contradiction and not a wording preference.** A benchmark-relative figure
subtracts two returns. If one leg carries a stale print, the two legs are measured at
*different effective instants*, and their difference is no longer a like-for-like comparison —
however deterministically it computes. Asserting "not degraded" is the interface claiming an
absence of harm the data does not support, in the one product area where cross-market timing
is the differentiator. **`data.js:450` is a contract defect, not a designer error.**

## 1.2 The amended contract — three distinctions

Freshness and comparability are now distinguished along three axes:

**1. Single-leg metric computability.** A metric computed from one series, whose inputs are
stale, remains `AVAILABLE`. Staleness is disclosed; the value is not degraded. **§D3.2's
original reasoning survives here, unchanged, and this is the majority case.**

**2. Multi-leg / benchmark-relative temporal comparability.** Where a metric combines two or
more series whose effective timestamps differ materially, the value may remain `AVAILABLE` —
it is computable and deterministic — but the surface **must disclose that temporal
comparability is limited**. "Not degraded" is not available as a claim for this class.

**3. Market-session-aware freshness.** Freshness is measured in **local trading sessions, not
wall-clock age.** A quote is not stale because hours have passed; it is stale because sessions
have passed without it updating. `quant_analyst` demonstrated why this is not academic: under
session-aware measurement the Mainland China A-share print in the current fixture **is not
stale at all** — Shanghai was on holiday. Wall-clock measurement was manufacturing a staleness
warning out of a market closure, in a product spanning three markets with different calendars.

## 1.3 The principle preserved

**A metric may remain computable while its interpretation or comparability is limited.** That
separation is the point of the amendment, not a casualty of it. This does **not** introduce a
new sufficiency state, and does **not** alter `AVAILABLE` / `LIMITED` / `INSUFFICIENT_DATA` or
their reason codes. `quant_analyst` was explicit that this is a *comparability* question, not a
*sufficiency* one, and did not touch PD-0006 or PD-0007. Neither does this decision.

**Comparability is therefore a disclosure dimension alongside freshness (§D5), not a fourth
metric state.**

# Part 2 — The claim-traceability invariant

## 2.1 The control gap this closes

Every P1 control this project built guards the **AI** path: provenance chips, the
`checkNarrativeSafety` scanner, the rule that a numeral may enter narrative only through a
chip. **Hardcoded interpretation was never guarded** — and four hardcoded strings in
`js/data.js` were found asserting the opposite of the values beside them, after three design
passes, two independent reviews, four rounds of human inspection and a PM verification regime
had all passed over them.

**No visual verification catches this class.** DOM overflow checks, screenshots and reading
prose for plausibility all passed. Only recomputing the numbers and comparing them to the
sentences found it.

## 2.2 The invariant

**Every material financial claim must be traceable to, and consistent with, the structured
deterministic facts it describes — regardless of whether it originates from AI, static fixture
copy, rule-engine copy, or UI code.**

The origin of a sentence does not change what it asserts. P1 has always meant that the engine
owns financial facts; this states plainly that a hand-authored sentence is as much an assertion
as a generated one.

**Preference order:** derive claims from structured states and documented rules. Independently
hardcoding a numerical interpretation is the exception, not the default.

**Where hardcoded explanatory text remains necessary, it must carry a semantic assertion test**
that recomputes the relevant metric and verifies the claim still holds.

## 2.3 Testable examples — these four are binding

1. `beta < 1` may not produce *"historically moved more than the benchmark"* unless another
   explicitly named measure supports it.
2. *"X and Y contribute the most"* must agree with the ranked risk-contribution values.
3. *"move together strongly"* must satisfy a **documented correlation classification rule** —
   which means such a rule must exist and be owned by `quant_analyst`.
4. Observation-count caveats must use **the same evidence object the Proof Packet exposes.**

## 2.4 The rule that makes it enforceable

**The Proof Packet must not be able to refute the sentence that links to it.**

This is the sharpest formulation and the one to test against. The beta caveat claiming 24
observations while its own packet reported 252 is exactly the failure it forbids — and it is
worse than a wrong number, because the evidence path is the mechanism this product offers as
proof. A reader who followed P9 correctly arrived at a refutation.

## 2.5 One internally coherent analytical system

**The prototype may not maintain parallel truths.** Named instances, all confirmed:

- one portfolio weighting scheme for risk (40/30/20/10) and another for exposure (≈48/35/10/6);
- one observation count in the UI (24) and another in Evidence (252);
- one return definition for headline performance (no FX applied) and another implicitly assumed
  by FX attribution (FX subtracted).

**There must be one canonical synthetic portfolio state from which every HG1 analytical surface
derives.** Synthetic data may be invented; it may not be internally inconsistent.

# 3 — Authority boundaries this decision sets

**`quant_analyst` remains engaged and holds methodology authority.** `product_manager` and
`designer` may **not** independently invent resolutions for: CAPM/Jensen-alpha methodology; FX
attribution mathematics; VaR convention; Sortino methodology; or statistical sufficiency. Those
are specified by `quant_analyst` and implemented by `designer`.

**Corrected outputs require independent verification by `quant_analyst` before HG1 is
returned.** The producer does not certify its own correction.

**One explicit prohibition, because it is the easy mistake:** the ex-post SML slopes downward
**correctly** — a negative realized market premium legitimately produces it. `quant_analyst`
established this. **Do not "fix" the mathematics to make the chart look conventional.** Fix the
labelling and the methodological explanation.

# 4 — What this decision does not do

- It does not approve HG1. **HG1 remains `REVISION_REQUIRED` and unapproved.**
- It does not authorize Priorities A–E.
- It does not add a metric state, alter the sufficiency vocabulary, or reopen PD-0006/PD-0007.
- It does not reopen the C+B direction, the four-surface IA, the Proof Packet architecture, the
  OCR safety model, scenario isolation, or AI grounding.
- It does not add analytical breadth (feedback log §26).
