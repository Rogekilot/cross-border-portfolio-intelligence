---
name: human-gate-package
description: Use when a Human Approval Gate (HG1-HG7) is reached and a Gate Review Package must be assembled, or when deciding whether the project may proceed past a gate. Covers what the package must contain and what may never be treated as approval.
---

# Human gate packages

A Human Approval Gate is a **blocking dependency**, not a milestone (PRD §38.1). When
one is reached the project enters `AWAITING_HUMAN_REVIEW` and stays there.

## What is never approval

None of the following may be treated as a gate decision, in any combination:

- passing tests, or a green validation run;
- an internal reviewer returning PASS;
- elapsed time, a deadline, or a schedule;
- silence, or the absence of objection;
- the previous gate having been approved;
- your own assessment that the work is obviously fine.

Only an explicit decision from the designated human product owner transitions a gate.
While the gate is active you may prepare material, reproduce results, answer questions,
and perform explicitly requested remediation. You may not begin downstream work.

## The four decisions

- `APPROVED` — proceed to the next authorized stage.
- `APPROVED_WITH_CONDITIONS` — record each condition as a binding requirement with
  traceable follow-up work, and proceed only within those conditions.
- `REVISION_REQUIRED` — create remediation work, stay at the gate, return with a
  revised package.
- `REJECTED` — stop the affected workstream. Do not redesign around the rejection
  unless explicitly instructed.

Record the decision verbatim, including conditions. Paraphrasing a condition is how it
stops binding anything.

## Package contents (PRD §38.2)

Write to `reviews/gates/HG<n>_GATE_REVIEW.md` (PRD §38.2 suggests `docs/reviews/`; this
project keeps gate packages in `reviews/gates/`). Record the owner's decision verbatim in
a new `decisions/product/PD-NNNN-*.md` and update `STATUS.md`. All fourteen elements are
required:

1. Gate name and ID
2. Objective — what this gate validates
3. Required deliverables
4. Actual deliverables, with file references
5. Runnable demo, screenshots, or sample outputs where applicable
6. Tests performed **and their results**
7. Proof of work — calculations, fixtures, rationale, traceability
8. Known limitations and incomplete items
9. Deviations from the PRD
10. New assumptions introduced since the previous gate
11. Open risks and unresolved decisions
12. Reproduction / inspection instructions — exact steps
13. Agent recommendation, with reasons
14. Human decision block

The decision block:

```text
[ ] APPROVED
[ ] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Human comments:

Decision date:
Approver:
```

## The test that matters

A reviewer must be able to verify the deliverable **without searching the repository**
and without asking you what you meant. If reproducing your result requires knowledge
that exists only in this conversation, the package is incomplete — sections 4, 7 and 12
are where that usually shows up.

Sections 8, 9 and 10 are the ones under pressure to be empty. An empty limitations
section on real work is a signal you have not looked, not a signal of quality.
