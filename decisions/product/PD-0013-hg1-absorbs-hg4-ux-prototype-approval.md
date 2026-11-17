# PD-0013 — HG1 absorbs HG4's UX Prototype Approval

**Status:** accepted
**Date:** 2026-09-06
**Decided by:** the designated **human product owner**, in answer to a direct escalation.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Supersedes:** the §38.5 gate-mapping row for HG4, as it applies to UX prototype approval.
**Evidence for the escalation:** `reviews/gates/HG1_ROUND4_VERIFICATION.md` §2.

---

## 1. The mismatch that prompted this

The owner's round-4 feedback log (§25) suspected gate-mapping drift and asked for independent
verification. **The suspicion was correct.**

`Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` §38.5 maps:

| Human Gate | Technical coverage | Primary decision |
|---|---|---|
| **HG1 — Product & Architecture** | CP0 | Approve interpretation, architecture, stack, domain model, and plan before substantive build |
| **HG4 — UX Prototype Approval** | CP7 | Approve information architecture, usability, and progressive explanation |

Three rounds of HG1 review have in practice been decided **primarily on UX prototype quality**
— information architecture, chart ergonomics, typography, table alignment, semantic color —
which §38.5 assigns to HG4/CP7.

**No prior decision record superseded that mapping.** `PD-0004` was checked specifically: it
settles only that CP0's increment is gated by HG1 and how the DAG completes without violating
§38.4's CP1 hard-stop. It never mentions HG4. The drift was real and undocumented.

## 2. The decision

**Intentional. HG1 absorbs HG4's UX Prototype Approval.** The owner deliberately wants the UX
prototype settled before any downstream technical work begins, and has confirmed the current
practice as the intended one.

**HG1's decision basis is therefore, from CP0 onward:**

- CP0's original scope — interpretation, architecture, stack, domain model, and plan; **plus**
- information architecture, usability, and progressive explanation, formerly HG4/CP7.

**What HG4/CP7 retains:** usability validation **against real data** — the questions that
cannot be answered by a synthetic prototype, once the real market-data spine, ingestion and
calculation engine exist. HG4 is not deleted; it is narrowed.

## 3. Why this is defensible, and the one thing it costs

**[J] It is the right ordering for this product.** §38.4's hard-stop exists so that CP1
implementation does not begin against an unapproved product interpretation. The UX *is* a large
part of the interpretation here — the metric-state rendering, the evidence path, the
scenario/actual separation and the AI boundary are all product contracts that only become
inspectable when rendered. Approving architecture while deferring whether the product can
*present* its own contracts would gate the cheaper question and defer the harder one.

**[J] The cost, stated plainly:** HG1 is now a materially heavier gate than §38.5 describes,
and it has taken four rounds partly for that reason. A reader of §38.5 alone would not predict
that. **This record is what stops that from being invisible** — which is precisely what §25
asked for: *"Do not silently change gate semantics."*

**[F] One consequence worth naming:** approving HG1 on UX grounds must not be mistaken for
approving CP0's architecture, stack and domain model. **HG1 now requires both.** The Gate
Review Package's fourteen elements already cover the CP0 half, and both independent reviews of
it have passed; the UX half is what the current revision cycle is resolving.

## 4. What this does not do

- It does not approve HG1. **HG1 remains `REVISION_REQUIRED` and unapproved.**
- It does not delete HG4 — it narrows it to usability validation against real data.
- It does not change HG2, HG3, HG5, HG6 or HG7.
- It does not alter §38.4's hard-stop: CP1 may not begin until HG1 is `APPROVED` or
  `APPROVED_WITH_CONDITIONS`.
- It does not change the `feature-development` DAG, whose shape is fixed by the state layer.
