# PD-0011 — HG1 round 3 supersedes round 2; the gate is reopened and A–E are gated behind it

**Status:** accepted
**Date:** 2026-09-05
**Decided by:** the designated **human product owner**.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Canonical record:** `reviews/PM_ACCEPTANCE.md` — the round-3 instruction verbatim.
**Supersedes:** `PD-0010-hg1-conditions-and-checkpoint-restructure.md`, in full.
**Reopens:** HG1 itself. Reopens no product contract.

---

## 1. The decision

**HG1 is `REVISION_REQUIRED`, for one bounded visual-polish pass only.** The round-2
`APPROVED WITH CONDITIONS` recorded earlier the same day is withdrawn.

The owner was explicit about which message governs: *"Now totally rely on this message as my
conclusion to the prototype."*

## 2. What was reversed, and what was not

**Reversed:**

- `pm_acceptance` moved `complete` → `awaiting_human`; `human_gate.active` `false` → `true`;
  `runtime_phase` `complete` → `blocked`. Done via `scripts/update_task_state.py`; both
  readiness and conformance re-verified afterwards.
- `reviews/PM_ACCEPTANCE.md` rewritten. It had recorded an approval; it now opens by stating
  that **no acceptance stands**, and carries the full decision history so the withdrawn round
  is visible rather than erased.
- `HG1_GATE_REVIEW.md` §15 marked superseded by a new §16.
- `PD-0010` superseded by this record.

**Not reversed, because the owner reaffirmed it in round 3:**

- The **C+B direction is the accepted continuing design direction.**
- The substance of the conditions.
- Post-HG1 Priorities A–E, with refinements (§4).
- **All Checkpoint A design work already completed.** The owner said *"You may keep some work
  done or reverse it"*, and round 3's conditions are substantively the same as round 2's. The
  work is what the current conditions ask for. Kept; inventory in `PM_ACCEPTANCE.md` §4.

**Never started, and correctly so:** any Priority A–E work. It was blocked by environment
(no egress by policy, no vendor credentials) before it was blocked by the gate. **Nothing had
to be unwound.** Had that work begun on the strength of a decision that was withdrawn hours
later, this reversal would have been expensive instead of clerical.

## 3. Why the difference between the two rounds is material

Round 2 attached conditions **to an approval**: the gate closed and work proceeded within
constraints. Round 3 makes the same substance **prerequisites to approval**: the gate stays
open and nothing downstream proceeds.

**[J]** This is not a semantic distinction and must not be smoothed over. Under round 2, §38.4
no longer blocked anything. Under round 3 it blocks everything past the polish pass. An agent
reading only the condition text — which barely changed — would draw exactly the wrong
conclusion about what it may do. That is why `PM_ACCEPTANCE.md` leads with the gate state
rather than with the conditions.

## 4. What round 3 added to Priorities A–E

Round 3 kept A–E and sharpened them. New or strengthened, relative to `PD-0010`:

| Area | What round 3 added |
|---|---|
| **Sequencing** | An explicit dependency order: market/reference data + security resolution → deterministic calculation spine → Proof Packets/evidence → real AI. *"Do not interpret Priorities A–E as five unrelated parallel feature projects."* |
| **OCR track** | May run in parallel, **but** its security-resolution and ledger-commit stages must integrate with the same canonical identity and portfolio contracts — *"rather than create a second ingestion architecture."* |
| **Priority A** | *"Do not merely demonstrate that an API responds."* The proof must establish provider response → normalized internal object → provenance/source → timestamp/freshness → deterministic downstream consumption. Provider limitations evaluated explicitly, **not hidden behind adapters.** A real primary/fallback provider decision must emerge. Adds market/calendar handling. |
| **Priority C** | **A source-image retention, redaction/access and deletion policy is now a required part of the implementation plan** — *"rather than treating OCR uploads like ordinary harmless files."* This directly answers OCR-OQ-2 and OCR-OQ-3 from PD-0009 §4, which were the owner's to answer, and confirms the §30.1 privacy-posture concern raised in PD-0009 §2.6 was the right call. |
| **Priority D** | A **fixed historical valuation date/window** for the canonical run, so results stay reproducible while live markets move. A **golden cross-border portfolio fixture** with independently reproducible expected values, as a **permanent regression asset**. And: *"Do not certify the calculation engine merely because its own implementation tests pass"* — PRD §38.6 restated by the owner. |
| **Priority E** | The adversarial question *"Which stock should I sell?"* must exercise the V1 advisory boundary rather than *"quietly turn the product into a personalized trade-recommendation engine."* |
| **Review budget** | Independent review is to be spent on data-source correctness, instrument identity, cross-border FX and corporate actions, calculation reproducibility, OCR uncertainty and canonical-state protection, and AI deterministic-boundary enforcement — *"higher-risk than whether another card is ten pixels too tall."* |

**[F]** The owner also confirmed two things this project had already recorded independently,
which is worth noting because it means the records were right: **OCR confidence ≠ metric
sufficiency** must not collapse into one state model (PD-0009 §2.4, `OCR_INGESTION_ADDENDUM`
§4.1), and **the confirmed staged batch — not the image, not an OCR rerun — is the replayable
deterministic input** (PD-0009 §2.7, OCR-OQ-5).

## 5. Harness behavior the owner set for this pass

**[F]** *"Keep this final UI pass bounded. It should primarily be Designer-owned, with PM
browser verification. Do not trigger repeated multi-round technical review merely for visual
sizing, typography or color-token corrections unless the pass changes an accepted product
invariant."*

**[J]** This is a direct instruction about how to spend the review budget, and it is the
correct call: a `technical_reviewer` round on chart typography would burn the budget the owner
wants reserved for provider correctness and calculation reproducibility. **The conditional
matters and is retained:** if the pass changes an accepted product invariant, review is back
on. Nothing in a polish pass should — and if something does, that is itself the finding.

## 6. What this decision does not do

- It does not approve HG1. **HG1 is open and unapproved.**
- It does not authorize any Priority A–E work.
- It does not authorize new prototype functionality: *"Do not add significant new prototype
  functionality during this pass."*
- It does not reopen any product contract — not the metric-state rules, the deterministic
  boundary, the Proof Packet architecture, scenario isolation, freshness, or AI grounding.
- It does not add mutual funds to V1.
- It does not close PD-0009's open questions, though it answers the substance of OCR-OQ-2 and
  OCR-OQ-3 by requiring a retention/redaction/deletion policy in the Priority C plan.
- It does not establish an accessibility standard. Condition 2's *"color must never be the
  only encoding"* is a specific rule, not a standard; the gap remains open.
