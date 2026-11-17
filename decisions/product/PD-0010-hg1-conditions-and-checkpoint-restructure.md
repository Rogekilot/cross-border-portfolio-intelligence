# PD-0010 — HG1 approved with conditions; the next phase becomes five explicit proofs

**Status:** accepted
**Date:** 2026-09-05
**Decided by:** the designated **human product owner**, at HG1 round 2.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Decision record:** `reviews/PM_ACCEPTANCE.md` — the verbatim decision and all five conditions.
**Supersedes:** the "CP1 next" recommendation in `reviews/gates/HG1_GATE_REVIEW.md` §13.
**Reopens:** nothing.

---

## 1. What changed

Two things, and only the second is a change of plan:

1. **HG1 is decided: `APPROVED WITH CONDITIONS`.** The Direction C foundation with Direction
   B's analytical visualization language is the accepted product-design direction. The
   four-surface IA, contextual AI, rich Overview, progressive disclosure, chart-led
   analytics, evidence-as-expandable-layer, Portfolio-owned ingestion workflows, and
   Analytics-owned risk/exposure are now **approved baseline**.
2. **The next phase is restructured.** The §38.5 sequence had CP1 (ledger, positions, cash,
   point-in-time reconstruction) as the next checkpoint. The owner replaced that with five
   explicit proofs and gave the reason in one line: *"Do not hide all five inside one
   'implementation complete' milestone."*

| Checkpoint | Proves |
|---|---|
| **A** | UI cleanup — typography, charts, holdings alignment, semantic colors. Human visual inspection. |
| **B** | Real data adapters — security search, prices, historical series, FX, corporate actions for US/HK/CN. |
| **C** | Ingestion — manual + CSV + OCR → confirmed staged portfolio. |
| **D** | Quantitative — a real multi-market portfolio produces reproducible valuation, performance and risk outputs. |
| **E** | AI integration — a real model API consuming only controlled deterministic tools, producing evidence-backed explanations. |

**This is a better structure than the one it replaces, and worth saying why:** each
checkpoint fails independently and visibly. The previous framing would have discovered a
market-data problem, an OCR problem and a determinism problem inside a single CP1 that
either passed or did not.

## 2. The restructure does not weaken any gate discipline

- **`APPROVED WITH CONDITIONS` is not `APPROVED`.** Work proceeds *only within* the five
  conditions. Anything outside them is unauthorized by this decision.
- **HG2 is not open, not reached, and not approved.** §38.4's rule that a gate is a blocking
  dependency is untouched.
- **Condition 4 is a standing constraint with no completion state.** *"Do not gradually move
  those capabilities back into separate pages merely because implementation becomes easier
  that way."* Any future proposal that migrates a listed Overview capability onto a separate
  page violates an approved gate condition and is escalated, not absorbed. The owner
  anticipated a specific failure mode — architecture eroding under implementation
  convenience — and pre-committed against it. That is the kind of condition that only works
  if it is quoted rather than summarized.

## 3. Checkpoints B–E cannot start in this environment

**[F]** Every one of B, C, D and E requires reaching an external service: a market-data
vendor, an OCR engine, or a model API. This harness provides none.

- **[F]** Egress is denied by project policy. `platform-capabilities.json` is precise, and
  so is this record: a `curl` probe was refused by `permissions.deny` **before any request
  was attempted**, so what is established is a **policy block, not a network failure**.
  Reachability is deliberately recorded as unknown rather than inferred — the negative
  evidence was preserved rather than overstated.
- **[F]** No market-data vendor credentials are provisioned, and none may be committed to
  the repository (§30.1 requires server-side-only keys).
- **[F]** `platform-capabilities.json` states the governing fallback: *"No workflow task may
  depend on network egress… vendor access is a delivery-time concern requiring explicit
  human provisioning."*

**[J] This is a human provisioning step and must not be routed around.** An agent that
responds to this by building a mock adapter and calling it a data-adapter proof has defeated
the entire purpose of Checkpoint B, which exists precisely to replace mocks with evidence.
If provisioning does not happen, the honest outcome is *"Checkpoint B not run"*, not a
simulated pass.

**[J]** Checkpoint A is unaffected and can begin immediately. It is design work on an
existing artifact and needs no external service.

## 4. Preconditions that must be met before specific checkpoints

| Precondition | Blocks | Owner |
|---|---|---|
| `quant_analyst` has **never been engaged** in this project | **D** | `product_manager` to engage |
| **N-6** — the JSON Schema under `schemas/` the tech plan promised and `implement` did not deliver | **D** | `engineer` |
| **N-3** — methodology registry has no key or version discipline, while T6's determinism argument depends on entries being immutable once published | **D** | `engineer` + `quant_analyst` |
| **N-17 / NF-5** — which reason codes may pair with which sufficiency states | **D** | `quant_analyst` |
| Instrument identity has **no FIGI fallback**, though ADR-P5 keys every ledger join off it | **B** | `engineer` + owner |
| **OCR-OQ-1 … OCR-OQ-7** (PD-0009 §4), four of which are the owner's | **C** | mixed |
| PRD §30.1's privacy posture, which a brokerage screenshot breaks (PD-0009 §2.6) | **C** | owner + `harness_architect` |

**[J]** Checkpoint D is the one most at risk of being attempted without its preconditions.
It is quantitative proof against real inputs — the methodology, the conventions, and the
independently-derived expected values belong to `quant_analyst`, not to the Engineer who
implements the engine and not to the PM. Engaging that role is a precondition, not a
nice-to-have.

## 5. The fund-search scope question — raised by the owner, deliberately not closed

**[F]** The owner raised it themselves and drew the line: *"If 'fund search' means ETFs,
that is already within V1. If it means mutual funds, that would change the currently locked
asset scope and should be raised as a separate product decision rather than silently
added."*

**[F]** PRD §5.3 lists **mutual funds** as explicitly out of V1. **[J]** So the owner's
instinct matches the document exactly: ETFs need no decision, mutual funds need a new one,
and this decision record adds neither. Checkpoint B's security search covers **ETFs only**
unless and until a separate product decision says otherwise. An agent that quietly widens it
to mutual funds while implementing search has made a scope change the owner explicitly
reserved.

## 6. Condition 2's accessibility line

**[F]** Condition 2 closes with: *"ensure color is not the only encoding—labels, icons, line
style or symbols should carry the same information for accessibility."*

**[J]** This is the **first accessibility requirement this project has ever had.** It is
narrow, specific, and binding, and it is not a standard. The open item recorded across two
session handoffs — *no accessibility standard exists anywhere in the mandate* — stays open.
Satisfying Condition 2 does not close it, and the redundant-encoding rule should not be
reported as though it did.

## 7. What this decision does not do

- It does not approve HG2, or any future gate.
- It does not authorize work outside the five conditions.
- It does not close the open items in `reviews/PM_ACCEPTANCE.md` §6.
- It does not permit a simulated pass on any of Checkpoints B–E.
- It does not add mutual funds to V1.
- It does not establish an accessibility standard.
