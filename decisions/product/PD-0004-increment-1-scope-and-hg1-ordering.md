# PD-0004 — Increment 1 is CP0, and how that reconciles with the workflow DAG

**Status:** decided (product scope, within PM authority)
**Date:** 2026-09-03
**Decided by:** `product_manager`, session `fin-web-9d`, worker `pm-01`
**Task:** `feature-development/prd`
**Supersedes:** nothing
**Related:** [PD-0001](PD-0001-prd-reset.md), `specs/FEATURE_PRD.md`

---

## Context

`workflows/feature-development.json` is a fixed DAG:

```
prd → {ux_planning, tech_planning} → implement → {design_review, technical_review} → pm_acceptance
```

`pm_acceptance` is the only task with `human_gate: true`. The workflow description states
the DAG shape is stable across increments and "only the increment's scope changes."

`Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` §38.3 defines CP0 as a **product
contract and architecture proposal** checkpoint, whose deliverables are documents:
canonical terms, architecture proposal, domain model, service boundaries, ADRs, and an
implementation sequence. §38.5 maps CP0 to **HG1**. §38.4 HG1 carries a hard-stop:

> CP1 implementation may not begin until HG1 is `APPROVED` or `APPROVED_WITH_CONDITIONS`.

## Decision

**Increment 1 is CP0, and its human gate is HG1.**

The first increment is not a feature. It is the product contract and architecture
proposal that every later increment executes against. This is the correct first
increment because CP0 is the PRD's own first checkpoint, because nothing downstream can
be specified without it, and because `specs/FEATURE_PRD.md` currently holds a placeholder
(PD-0001) — no approved product contract exists at all.

## The conflict this had to resolve

CP0 is a checkpoint with no feature to build, but the DAG can only reach its human gate
*through* `implement`. Read naively, the harness would require implementation before the
gate whose entire purpose is to approve the architecture **before** expensive
implementation begins. That inverts HG1.

I did not resolve this by weakening HG1, and I did not attempt to change the DAG —
workflow structure is `harness_architect` authority, not mine.

**Resolution:** `implement` in this increment is scoped to executable artifacts that are
genuinely CP0 and that are **not** CP1–CP3 work. Concretely it may deliver the canonical
vocabulary, the metric-state model, and the methodology-registry schema and its
validator, with tests. It may **not** deliver ledger events, positions, cash, instrument
resolution, pricing, FX, corporate actions, or any analytic calculation — those are CP1
and later, and HG1 gates them.

This keeps both rules intact: the DAG completes, and no CP1 implementation precedes HG1.

## Why this is not a loophole

The test applied to every candidate `implement` deliverable was: *does building this
commit the product to a financial-accounting or analytics decision that HG1 exists to
review?* The three admitted deliverables fail that test in the right direction — they
encode the PRD's own stated invariants (§32 states, §33 registry, P1/P5) as structure,
and encoding them **before** HG1 is what makes HG1 reviewable rather than theoretical.
PRD §44 rule 4 requires formulas and thresholds to live in the methodology registry
rather than feature code; creating that registry is a precondition for obeying the rule,
not an early exercise of it.

The registry ships with its schema and validator but with **no metric entries**. Every
entry is a methodology decision owned by `quant_analyst` and is out of scope here.

## Alternatives rejected

- **Fold a thin CP1 slice into increment 1** so `implement` has real feature work.
  Rejected: directly violates the §38.4 HG1 hard-stop.
- **Skip `implement` / mark it not-applicable.** Rejected: `design_review` and
  `technical_review` depend on it, so `pm_acceptance` and therefore HG1 become
  unreachable. It also puts a task into a state the DAG recomputation does not model.
- **Ask the Architect to add a documentation-only workflow variant.** Rejected for now
  as disproportionate: it changes harness structure to solve a first-increment problem
  that scope discipline already solves. Worth revisiting if a later increment is again
  documentation-only.

## Consequences

- `design_review` and `technical_review` in this increment review **documents and a
  contract skeleton**, not a feature. Their briefs in `specs/FEATURE_PRD.md` say so.
- `pm_acceptance` assembles the HG1 Gate Review Package (PRD §38.2, fourteen elements)
  and drives the project to `AWAITING_HUMAN_REVIEW`. It does not decide the gate.
- The next increment cannot begin until the human product owner decides HG1.

## Open item this decision does not close

Whether the fixed DAG is the right shape for a documentation-only checkpoint is a
harness-design question, recorded here for the Architect and the human owner. This
decision routes around it for increment 1 only, by scoping, and does not claim to have
fixed it.
