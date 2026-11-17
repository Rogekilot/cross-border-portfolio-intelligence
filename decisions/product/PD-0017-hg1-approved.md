# PD-0017 — HG1 is APPROVED

**Status:** accepted
**Date:** 2026-09-13
**Decided by:** the designated **human product owner**, in a direct instruction to `pm-01`.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-61`. **Recorded, not decided.**
**Gate:** HG1 — Product & Architecture Approval (source PRD §38.4, mapped to CP0 by §38.5),
absorbing HG4's UX Prototype Approval per PD-0013.
**Consolidated evidence package:** `reviews/gates/HG1_STAGE5_UX_EVIDENCE_PACKAGE.md`
**Companion CP0 package:** `reviews/gates/HG1_GATE_REVIEW.md`

---

## 1. The decision, verbatim

```
HG1 = APPROVED
```

No conditions were attached. The owner did not select `APPROVED_WITH_CONDITIONS`,
`REVISION_REQUIRED`, or `REJECTED`.

## 2. Stated approval basis

The owner recorded the basis as the **final independent Stage-5 verdict**:

```
CLEAR WITH MINOR DEBT
```

That verdict was issued by `review-08`, a fresh advisory `technical_reviewer`, after two
prior independent reviewers (`review-06`, `review-07`) had each returned **HOLD** and two
bounded correction rounds had been run. The full arc, the blocking findings, how each was
finally verified, the reviewer identities and their advisory status, and the residual
debt are consolidated in `reviews/gates/HG1_STAGE5_UX_EVIDENCE_PACKAGE.md`.

## 3. What this approval does and does not do

**Does:** satisfies the §38.4 hard stop that gates CP1 —

> CP1 implementation may not begin until HG1 is `APPROVED` or `APPROVED_WITH_CONDITIONS`.

**Does not:** close the `pm_acceptance` task. Under PD-0004's resolution the DAG is
`prd → {ux_planning, tech_planning} → implement → {design_review, technical_review} →
pm_acceptance`, and `pm_acceptance` is the task carrying HG1. Its dependencies
`design_review` and `technical_review` are `blocked` behind `implement`, which is `ready`
and not complete. A gate decision is not a dependency satisfaction, and `_deps.py` may
never set a status to `complete`. The shard is therefore left as the graph describes it;
nothing was forced.

**Does not:** clear any residual debt. The six items in §8–§9 of the evidence package
remain open, including three explicitly unverified areas. Approval was given with that
debt visible and named.

**Does not:** convert any advisory review into `technical_review`. That task remains
`blocked` and unsatisfied. No advisory reviewer produced a shard, execution record or
handoff, and none may.

## 4. Residual debt accepted into the approval

Open, not cleared:

1. holdings-table row caveat clipping and horizontal-scroll discoverability (bears on P9);
2. identical inspector 简明 → 专业 content;
3. Scenario Lab machine-input raw enums.

Explicitly unverified, no claim in either direction:

4. responsive / narrow-window behaviour — `resize_window` is unreliable on this provider,
   reproduced by three independent reviewers;
5. native `<select>` interaction — `browser_interaction` remains
   `workflow_capability / degraded`;
6. the locale regression's `selfTest()` injected-defect direction was never executed.

No product revision was created for any of these, by the owner's instruction.

## 5. What is not evidence for this decision

Recorded because §38.1 requires it: none of the following was treated as approval, and
none of it approved anything — the green selfcheck run (48 passed), the reviewers'
verdicts including the final CLEAR WITH MINOR DEBT, the elapsed review rounds, or the
absence of further objection. Those are inputs the owner weighed. The decision in §1 is
the owner's and is recorded here by an agent that did not make it.
