# HG1 Gate Review Package — INC-001 (CP0)

**Assembled by:** `product_manager`, worker `pm-01`, sessions `fin-web-09` → `fin-web-77`, 2026-09-04
**Standard:** source PRD §38.2, all fourteen required elements
**Decision belongs to:** the designated human product owner, and to no one else (§38.1, §38.6)

> **Nothing in this package is an approval, and no agent has approved anything.**
> Passing tests, two reviewers' clearance, elapsed time, and absence of objection are
> **never** approval (§38.1, §44.23). Element 14 is empty and only you may fill it.

---

## 1. Gate name and ID

**HG1 — Product & Architecture Approval.** Source PRD §38.4, mapped to technical
checkpoint **CP0** by §38.5. The first of seven human gates.

## 2. Objective — what this gate validates

§38.4's inspection question, verbatim:

> *"Does this architecture actually represent what I asked for, and is it capable of
> delivering the product without introducing hidden scope or foundational shortcuts?"*

§38.4 also carries the hard stop this gate exists to enforce:

> **CP1 implementation may not begin until HG1 is `APPROVED` or `APPROVED_WITH_CONDITIONS`.**

That stop has been honoured. No CP1 content exists — verified by two independent reviewers
and by me.

## 3. Required deliverables

From `specs/FEATURE_PRD.md` §3, which selects CP0 out of the source PRD and makes it
executable:

| Group | Required |
|---|---|
| **Design (D1–D5)** | Information architecture for the eleven §6 surfaces; the four-level depth-model interaction contract; metric-state presentation contract; evidence-inspection affordance; freshness disclosure pattern |
| **Technical (T1–T8)** | Architecture and module boundaries; stack and dependencies; domain model; the P1 boundary made structural; vendor-independence contracts; determinism/reproducibility strategy; CP1–CP11 sequence with gates marked blocking; unresolved choices logged not guessed |
| **Implementation (I1–I4)** | Canonical vocabulary; metric-state model enforcing P5 by construction; methodology-registry schema and validator with **zero** entries; tests including negative cases |
| **Governance** | Both reviews; this package; project in `AWAITING_HUMAN_REVIEW` with no CP1 dispatched |

## 4. Actual deliverables

| Artifact | Lines | Produced by |
|---|---|---|
| `specs/FEATURE_PRD.md` | 500 | `pm-01` |
| `designs/FEATURE_DESIGN.md` | 1,132 | `designer-01`, reworked by `designer-03` (4 passes) |
| `implementation/FEATURE_TECH_PLAN.md` | 1,171 | `engineer-01`, reworked by `engineer-02` (4 passes) |
| `src/product_contract/` | 429 | `engineer-02` |
| `tests/product/` | 658 | `engineer-02` |
| `reviews/DESIGN_REVIEW.md` | 1,175 | `designer-02` (r1), `designer-04` (r2–r5) |
| `reviews/TECH_REVIEW.md` | 1,963 | `review-01` (r1–r5) |
| `reviews/gates/CP0_RECONCILIATION.md` | — | `pm-01` |
| `reviews/gates/LIVE_CERTIFICATION_EVIDENCE_INC-001.md` | — | `pm-01` |
| `decisions/product/PD-0004…PD-0008` | 5 records | `pm-01` |

Provenance: 6 records under `runtime/executions/`, 6 handoffs under `artifacts/handoffs/`,
every completed shard linked to a matching execution record. Runtime readiness passes.

## 5. Runnable demo / sample outputs

**Not applicable, by design.** CP0 has no user-facing surface and presents no computed
financial number — `specs/FEATURE_PRD.md` §3.1 places every screen showing a computed value
out of scope for this increment. What *is* runnable is the test suite (element 12).

## 6. Tests performed and results

Executed by me and independently re-executed by `review-01`; neither of us accepted the
producer's report.

| Suite | Command | Result |
|---|---|---|
| Product | `python3 -m unittest discover -s tests/product -p "test_*.py"` | **50 tests, OK, exit 0** — run 4× including varied `PYTHONHASHSEED`, identical |
| Repository canonical | `python3 -m unittest discover -s tests -p "test_*.py"` | **406 tests, 0 errors**, 5–6 failures |
| Runtime readiness | `python3 scripts/validate_runtime.py --mode readiness` | **PASS**, 1 warning (ADR-0018, documented) |
| Harness validation | `python3 scripts/validate_harness.py` | **PASS**, 0 warnings |

**The canonical suite's 5–6 failures are not product defects and I am not hiding them.**
They are pre-existing harness tests that assert against live mutable registry and checksum
state, so they fail as delivery proceeds. `review-01` established that **no harness test
imports product code**, and that two of them assert a file does not exist which exists
*because the reviewer itself created it*. The count drifted 6→5→6 across the increment for
that reason. I did not reconstruct the exact sequence; `review-01` recorded that `not_run`
rather than asserting it.

**A mutation test was run on the highest-value invariant.** With PD-0006's five-reason-code
coupling temporarily disabled, exactly the three tests asserting it failed (15 subtests =
5 codes × 3 tests) and nothing else did; restoring returned 50/50, and no trace of the
disabled state persists. This was done because `review-01` found those tests had silently
stopped discriminating (N-21) — they would have passed with the coupling deleted.

## 7. Proof of work

**Acceptance criteria — AC-01…AC-21.** All satisfied. The contested ones:

| AC | Status | Evidence |
|---|---|---|
| AC-01 | Satisfied | Required a correction: the PRD listed what V1 excludes but never what it includes. §3.6 added, restating source §5.1/§5.2 verbatim. |
| AC-09 | Satisfied | Regressed mid-increment and repaired — the Rendering Service carried every P1 guarantee while appearing in no diagram, boundary table, or deviation list. |
| AC-10 | **Satisfied — after three failures** | Round 1: no mechanism catching the ordinary violation. Round 2: right mechanism, blocklist polarity that failed open. Round 3: allowlist polarity, three enumerations too wide. Verified by hand-evaluating 14 candidate strings. |
| AC-15 | Satisfied | **Corrected twice.** See §7.1 below — this is the most important thing in this package. |
| AC-16 | Satisfied | Fifteen §33 fields, verified against source line 1277 by me and independently by `review-01`, field by field. |
| AC-17 | Satisfied | Registry ships `entries=()`. Hidden-entry search across `src/` clean. |
| AC-18 | Satisfied | Determinism confirmed across 4 runs with varied hash seeds. |

### 7.1 The pattern you should weigh most heavily

**Three separate contract decisions of mine drifted from the design, and each was corrected
back toward it.**

| Finding | Design said | My contract said | Right |
|---|---|---|---|
| BF-1 | `AVAILABLE`+`STALE_DATA` needs a rendering | PD-0006 created the state without telling the design | design |
| BF-3 | `LIMITED` renders the computed value plus a qualifier | AC-15 forbade `LIMITED` carrying a value | **design** |
| BF-4 | `LIMITED` always has a value to render | PD-0007 permitted `LIMITED` without one | **design** |

`designer-01` wrote §D3.2 directly from source PRD §32 before any of these decisions
existed, and encoded the correct rule from the start. **The design was a more faithful
reading of the source PRD than my acceptance criteria were.** `review-01` independently
found source §9.3 supports it — *"Unavailable/**limited** without cost basis"* — evidence I
had not cited.

The final rule is a total equivalence: **`value is None` ⇔ `sufficiency_state is
INSUFFICIENT_DATA`**, machine-enforced, verified as an exact bijection against §D3.2's rows
in both directions.

### 7.2 Structural controls, not conventions

- **P5 by construction:** a frozen dataclass rejecting the invalid object before it exists;
  `__init_subclass__` seals subclassing; `__reduce__` routes copy/pickle through the
  constructor. `object.__setattr__` and `object.__new__` remain unsealable in pure Python —
  **stated honestly and pinned by tests** rather than papered over.
- **P1 boundary:** provenance-bound rendering — the AI emits no numbers, only citations to
  logged tool calls that a deterministic Rendering Service resolves. Labels derive from the
  cited call's own methodology reference, not from AI prose.

## 8. Known limitations and incomplete items

1. **N-6 — the tech plan promises a JSON Schema under `schemas/` that `implement` did not
   deliver.** A plan/implementation mismatch. Harmless now (registry ships empty), a **CP1
   precondition**.
2. **N-3 — the registry has no key or version discipline**, while T6's determinism argument
   depends on entries being immutable once published. Also a CP1 precondition.
3. **N-2, N-4, N-5, N-7, N-8, N-9** — open since review round 1, unaddressed by any rework;
   all non-blocking for CP0. N-9: `value` is the only unvalidated field on `MetricResult`.
4. **Caveat-compression has no verification checkpoint.** D2.2 guarantees the caveat *slot*
   is non-empty, not that compressed wording preserves meaning. **No owner is assigned.**
5. **Freshness has a presentation contract and no data contract.** The carrier exists — the
   Computation Manifest pins per-market and FX references separately — but nothing declares
   it a *display-time* dependency. CP1–CP2 item.
6. **AC-10 residuals:** qualitative mischaracterization carrying no number; the fused
   number-word vocabulary is finite and not claimed exhaustive; N-19 (`grew by 1950`);
   N-20 (an over-large selector carries an implicit existence claim).
7. **No accessibility standard exists anywhere in the mandate.** The designer holds an
   accessibility veto and has nothing to exercise it against. **I declined to invent one** —
   naming a conformance target unconsidered would be the silent default AC-13 exists to catch.
8. **Instrument identity has no fallback** for securities lacking a FIGI. ADR-P5 keys every
   ledger join off it. CP1-blocking.
9. **Effective model and reasoning effort are unobservable in this surface** (ADR-0018), so
   every worker records `unobservable_in_surface` rather than a guess.

## 9. Deviations from this PRD

1. **This file is at `reviews/gates/`, not §38.2's recommended `docs/reviews/`.**
   `roles/product_manager.json` directs gate packages to `reviews/gates/`, and `docs/` is
   outside my write authority. §38.2 says "recommended filename," so this is a permitted
   deviation, declared rather than silent.
2. **`implement` ran before HG1.** Deliberate, reasoned in `PD-0004`: the fixed DAG reaches
   its gate only through `implement`, so it was scoped to CP0-appropriate structure carrying
   no financial logic. The §38.4 hard stop is intact — no ledger, positions, pricing, FX,
   corporate actions, benchmarks, or analytics exist.
3. **Three declared amendments to §37's reference decomposition** (splitting the API layer,
   promoting Scenario Lab, adding a Methodology Registry), which §38.3 invites. Declared in
   plan §12.
4. **OQ-01's owner was reassigned from you to me** — see §11 item 1.

## 10. New assumptions introduced since the previous gate

This is the first gate; the baseline is the source PRD. Assumptions A-02, A-03, A-04, A-06
of `specs/FEATURE_PRD.md` §8 stand unchanged. A-01 and A-05 have been **closed** — A-01 by
your PD-0005 decision, A-05 by PD-0006.

No new assumption was introduced silently. Every judgment made since is a numbered decision
record with its reasoning and its known limitations.

## 11. Open risks and unresolved decisions

**Requiring your decision at this gate:**

1. **PD-0006 — I reassigned OQ-01's owner from you to me** on the strength of §32's phrase
   *"suggested conceptual states,"* which I read as delegating the vocabulary's shape.
   Confirm or overturn. **If you intended §32 as prescriptive, that decision is the error.**
2. **PD-0007 — AC-15 corrected twice**, ending at the total equivalence (§7.1).
3. **PD-0008 — the AI may not free-type a count of your portfolio.** "top 3 holdings" is a
   selection; "you hold 7 positions" is a claim and must come through a slot.
4. **OQ-02 — stack and persistence.** Python, TypeScript SPA, PostgreSQL-class store,
   modular monolith with AI Orchestration isolated. **Proposals. HG1 may reject any of it.**
5. **N-17 / NF-5 — routed to `quant_analyst`, who was never engaged in this increment.**
   Which reason codes may pair with which sufficiency states. R-15 changed its shape:
   `LIMITED` + `CALCULATION_ERROR` now *requires* a value, so a calculation-errored metric
   presenting no number is illegal and the only legal form presents one. **Two independent
   reviewers found this; neither they nor I have authority to settle it.**

**Risks:**

- **§41.3 false precision** — mitigated structurally by AC-15, which took three attempts.
- **§41.4 AI overreach** — mitigated by the P1 boundary, which took three attempts and
  retains two disclosed residuals.
- **OQ-04 vendor availability** unresolved; no network egress or credentials here. Blocking
  by CP2.
- **OQ-05** — the fixed DAG has no documentation-only variant. Architect's, not mine.
- **Harness finding F-D** — registry doctrine and `validate_runtime` are unsatisfiable
  together once a delegated worker finishes. It blocked the readiness gate mid-increment;
  repaired by re-registering workers as `done`. Architect's.

## 12. Reproduction / inspection instructions

```bash
cd "/Users/<os-user>/Desktop/Fin Web"

# 1. The one acceptance criterion a machine decides (AC-15, AC-16, AC-17, AC-18)
python3 -m unittest discover -s tests/product -p "test_*.py"     # expect: 50 tests, OK
python3 -m unittest discover -s tests/product -p "test_*.py"     # run twice: identical

# 2. Product tests inside the repository suite
python3 -m unittest discover -s tests -p "test_*.py"             # expect: 406 tests, 0 errors
#    5-6 failures are pre-existing harness-state fixtures — see element 6

# 3. Governance state
python3 scripts/validate_runtime.py --mode readiness             # expect: PASS, 1 warning
python3 scripts/validate_harness.py                              # expect: PASS, 0 warnings

# 4. AC-17 — the registry must be empty
grep -n "EMPTY_METHODOLOGY_REGISTRY" src/product_contract/methodology_registry.py
```

**To read rather than run**, in this order: `specs/FEATURE_PRD.md` (what was asked) →
`decisions/product/PD-0004…PD-0008` (what I decided and why) →
`reviews/gates/CP0_RECONCILIATION.md` (where the two plans disagreed) →
`designs/FEATURE_DESIGN.md` §D3.2 (the table that was right three times) →
`reviews/TECH_REVIEW.md` §§13–17 and `reviews/DESIGN_REVIEW.md` (what the reviewers
attacked, including what they could not test).

## 13. Agent recommendation

**Recommendation: PROCEED — as `APPROVED_WITH_CONDITIONS`, not `APPROVED`.**

*Reasons to proceed.* Every acceptance criterion is satisfied. The two hardest — AC-10 and
AC-15 — were each wrong more than once and were caught by independent review rather than by
their authors. Both reviewers ended clear, having demonstrated they were still looking:
`review-01`'s final round found a defect invisible in both the test count and the pass/fail,
and `designer-04`'s two-way check came back clean only on its fourth attempt. Role
separation held throughout — reviewers reported and never fixed, producers stayed inside
their write grants, and a worker flagged a defect in my file rather than editing across the
boundary.

*Reasons for conditions rather than clean approval.* Five open items are genuinely yours or
`quant_analyst`'s and cannot be closed by any agent here: the reason-code coherence question
(item 5 above), the unowned caveat-compression checkpoint, the absent accessibility standard,
the FIGI fallback, and confirmation of PD-0006/0007/0008. Two CP1 preconditions (N-6, N-3)
should be attached as conditions rather than left to be rediscovered.

*What I am least confident about.* My own contract drafting. Three of my decisions had to be
corrected back toward a design written before them, and I did not catch any of the three —
independent reviewers did, on the fourth and fifth passes. **Weight the reviews more heavily
than my acceptance criteria when deciding.**

**Proposed next-stage scope, if approved:** CP1 (§38.5) — ledger, positions, cash,
point-in-time reconstruction — gated by HG2, with N-6 and N-3 closed first and
`quant_analyst` engaged before any metric entry is written.

## 14. Human decision block

```text
[ ] APPROVED
[ ] APPROVED WITH CONDITIONS
[X] REVISION REQUIRED
[ ] REJECTED

Conditions (if APPROVED WITH CONDITIONS):
    n/a — this is not an approval. HG1 REMAINS UNAPPROVED AND ACTIVE.

Human comments:
    Scope of the revision: UX/UI and information architecture ONLY.

Decided by: the designated human product owner
Date: 2026-09-04
```

**Decision round 1: `REVISION_REQUIRED`.** Recorded — not made — by `product_manager`,
worker `pm-01`, session `fin-web-12`, on 2026-09-04, from the owner's instruction given
directly in the interactive session. Per PRD §38.4 / line 1553 and §44.25, a
`REVISION_REQUIRED` decision **creates remediation work, remains at the current gate, and
returns with a revised Gate Review Package.** It is not approval and confers no authority to
begin CP1.

**Gate state after this decision, unchanged and required to stay so:**
`state/tasks/pm_acceptance.json` = `awaiting_human`; `project-state.human_gate.active` =
`true`; `reviews/PM_ACCEPTANCE.md` still **absent**, because no acceptance has occurred.

**The decision text, verbatim as given by the owner.** Reproduced without paraphrase; a
paraphrased instruction stops binding (see the `human-gate-package` skill).

> HG1 decision: `REVISION_REQUIRED` — UX/UI and information architecture only.
> The underlying financial contracts, metric-state rules, deterministic analytics
> boundaries, Proof Packet/evidence architecture, scenario isolation, AI-grounding
> principles, and current functional coverage are accepted as the baseline. Do not reopen
> them unless the redesign exposes a genuine contradiction that prevents the UX from
> representing the validated product logic correctly.
> The current visual prototype is not accepted as the product-design baseline. It is too
> text-heavy, visually sparse, fragmented across too many top-level destinations, and does
> not provide a strong portfolio understanding on first use.
> This is a presentation, interaction-design, and information-architecture revision, not a
> reset of the validated product logic.
> […] Return first with the three design directions for human selection. Do not proceed
> downstream until I choose one.

The full instruction — the six redesign objectives, the three-direction exploration mandate,
the per-direction deliverable list, the seven success criteria, and the harness/role
constraints — is reproduced in full and without elision in
**`reviews/gates/HG1_REVISION_CYCLE_01.md` §2**, which is the remediation contract this
decision creates. That file, not this block, is what the revision work is executed against.

**Round 2 of this gate is not yet open.** The next decision the owner makes is a *direction
selection* among three UX/IA directions, which is an input to the revision — **not** an HG1
decision. HG1 itself is decided again only when a revised Gate Review Package is returned.
No agent may fill a future decision block, infer it, or treat its absence as any kind of
answer (§38.1, §44.23).

---

## 15. Round 2 — HG1 IS DECIDED

```text
[ ] APPROVED
[X] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Conditions: five, binding. Reproduced verbatim in reviews/PM_ACCEPTANCE.md §1.

Decided by: the designated human product owner
Date: 2026-09-05
```

**Decision round 2: `APPROVED WITH CONDITIONS`, 2026-09-05.** Recorded — not made — by
`product_manager`, worker `pm-01`, session `fin-web-12`.

**The canonical record is `reviews/PM_ACCEPTANCE.md`.** It carries the owner's decision
verbatim and in full: what is now accepted baseline, all five conditions, Priorities A–E,
and the five required checkpoints. Read that file, not this block. A paraphrased condition
stops binding, so nothing is summarized there and nothing is summarized here.

**What the decision changed:**

- The Direction C foundation with Direction B's analytical visualization language is the
  **accepted product-design direction**. The four-surface IA, contextual AI, rich Overview,
  progressive disclosure, chart-led analytics, evidence-as-expandable-layer,
  Portfolio-owned ingestion workflows, and Analytics-owned risk/exposure are approved
  baseline.
- **`APPROVED WITH CONDITIONS` is not `APPROVED`.** Downstream work is authorized **only
  within the five conditions**.
- The next phase is **restructured into five explicit proofs** (Checkpoints A–E), replacing
  this package's §13 recommendation of "CP1 next". Recorded as
  `decisions/product/PD-0010-hg1-conditions-and-checkpoint-restructure.md`.
- **HG2 is not open, not reached, and not approved.**

**§13's recommendation is superseded but not deleted.** It recommended
`APPROVED_WITH_CONDITIONS` and the owner reached the same outcome by a different and longer
route — through a `REVISION_REQUIRED` round that §13 did not anticipate. The record of what
was recommended, and of the three contract-drafting errors §7.1 disclosed, stays visible on
purpose.

> **§15 IS SUPERSEDED. READ §16.** The round-2 approval recorded above was withdrawn by the
> owner on the same day, before any downstream work began. **HG1 is not approved.**

---

## 16. Round 3 — SUPERSEDES §15. HG1 IS NOT APPROVED

```text
[ ] APPROVED
[ ] APPROVED WITH CONDITIONS
[X] REVISION REQUIRED
[ ] REJECTED

Scope: ONE bounded visual-polish pass only (Conditions 1-4).

Decided by: the designated human product owner
Date: 2026-09-05
```

**Decision round 3: `REVISION_REQUIRED`, 2026-09-05.** Recorded — not made — by
`product_manager`, worker `pm-01`, session `fin-web-12`, on the owner's instruction
*"Now totally rely on this message as my conclusion to the prototype."*

**The canonical record is `reviews/PM_ACCEPTANCE.md`**, which carries the owner's round-3
instruction verbatim and in full, and which now opens by stating that **no acceptance
stands**. Read that file, not this block.

**What happened, stated plainly because a reversed gate decision is exactly the thing a later
session must not misread:** round 2 returned `APPROVED WITH CONDITIONS`; I recorded it, moved
`pm_acceptance` to `complete`, and the gate closed. The owner then superseded that decision
the same day. **The gate has been reopened** — `pm_acceptance` = `awaiting_human`,
`human_gate.active` = `true`, `runtime_phase` = `blocked`. No downstream work had begun, so
nothing had to be unwound beyond the state itself.

**What survived the reversal, because the owner reaffirmed it:**

- The **C+B direction remains the accepted continuing design direction.**
- The substance of the conditions — visual polish, semantic color, five-second chart
  interpretability, Overview as command center.
- Post-HG1 Priorities A–E, now with a stated dependency order and additional requirements
  (source-image retention and redaction policy, a fixed historical valuation date, a golden
  cross-border fixture, an explicit primary/fallback provider decision).

**What changed:** the conditions are now prerequisites **to** approval, not conditions
attached to one. **Priorities A–E are not authorized:** *"Do not begin Priorities A–E until
HG1 is explicitly approved."*

The final HG1 decision will be made primarily on five things: chart ergonomics; typography
consistency; holdings/table alignment; semantic color consistency; and preservation of
Overview as the command center.

Recorded as `decisions/product/PD-0011-hg1-round-3-supersedes-round-2.md`, which supersedes
`PD-0010`.
