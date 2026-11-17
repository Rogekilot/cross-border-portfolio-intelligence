---
name: prd-authoring
description: Use when writing or revising a product requirements document, feature spec, or acceptance criteria — and when reviewing whether a PRD is complete enough for design and engineering to start without asking follow-up questions.
---

# PRD authoring

A PRD is a contract that downstream roles execute against without a transcript. Its
quality is measured by one thing: **can a designer and an engineer start work from it
alone?**

## Required content

- **Problem** — whose problem, observed how. Not a solution restated as a need.
- **Users and context** — who, doing what, under what constraints.
- **Scope** — and an explicit out-of-scope list. The exclusions prevent more rework
  than the inclusions.
- **Acceptance criteria** — observable, testable conditions. "Fast" is not one;
  "p95 under 300ms on the reference dataset" is.
- **Constraints** — regulatory, technical, contractual, deadline.
- **Open questions** — with an owner and a decision-needed-by date.
- **Assumptions** — labeled as assumptions, not stated as fact.

## Evidence discipline

Mark every claim with its standing: fact, assumption, estimate, judgment, hypothesis.
A PRD that presents estimates as facts transfers false confidence to everyone
downstream, and they cannot recover it once it is in the contract.

## What a PM does not decide

- Technical architecture — the Engineer's authority.
- Interaction design — the Designer's authority.
- Whether a legal or compliance exception is acceptable — escalate.

Assigning work is not the same as rewriting someone's permanent authority.
Assign the feature; do not redefine the specialist's remit.

## Completion check

Before marking a PRD task complete:

1. every acceptance criterion is observable and testable;
2. out-of-scope is explicit;
3. every open question has an owner;
4. assumptions are labeled;
5. the artifact is persisted and `STATUS.md` updated;
6. the handoff names what was decided, what was assumed, and what is unresolved.

No hook enforces any of these. They are your judgment, and (1) through (4) are the part
that matters most.
