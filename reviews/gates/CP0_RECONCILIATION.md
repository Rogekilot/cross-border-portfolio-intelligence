# CP0 reconciliation — UX planning and technical planning as one proposal

**Increment:** INC-001 (CP0), gate **HG1**
**Reconciled by:** `product_manager`, worker `pm-01`, session `fin-web-09`, 2026-09-03
**Inputs:** `designs/FEATURE_DESIGN.md` (`designer-01`), `implementation/FEATURE_TECH_PLAN.md` (`engineer-01`)
**Status:** PM reconciliation. **Not a review** — `design_review` and `technical_review` are
distinct tasks owned by distinct identities and have not run. I commissioned both of these
artifacts, so I am the producer's parent, not its auditor.

> Purpose: state where the two proposals form one coherent product, where they genuinely
> disagree, and what neither of them covers. Disagreements are preserved, not resolved by
> preference. Where I resolved something, it is because it was mine to resolve, and it says so.

---

## 1. Where the two proposals agree, and it counts for something

These were produced **concurrently, by cold-started workers who could not read each other's
output** — I told each that the other's file was being written and was not authoritative.
Agreement reached independently is worth more than agreement reached by one reading the other.

| Concern | Design says | Technical plan says | Assessment |
|---|---|---|---|
| **P8** actual vs. hypothetical | `SCENARIO`-typed claims structurally never reach Overview or Holdings | Scenario Lab is a separate module writing only to its own hypothetical-state store; "no path from Scenario Lab back into Portfolio Service's ledger" | **Converged independently.** Same separation, derived at two layers. This is the strongest structural agreement in the increment. |
| **P1** engine owns facts | Nothing in the IA implies the AI layer produces a number; AI Analyst consumes claims | Three stacked controls: credential/network isolation, typed `MetricResult` requiring a state, output-time grounding check; plus an import-boundary lint | **Coherent.** The design does not depend on a control the plan does not provide. |
| **§32 state model** | D3 built on sufficiency + reason codes | T3 `MetricResult` = `sufficiency_state` required + `reason_code` nullable | **Identical shape**, reached separately. Now fixed by PD-0006. |
| **P9** evidence path | D4 requires a claim → methodology → inputs path reachable from every claim-bearing surface, at every depth level | Methodology Registry promoted to a first-class shared service "read by every Analytics/Insight/AI consumer"; Computation Manifest pins the inputs | **Coherent and mutually supporting.** D4's affordance has something real to point at. |

## 2. Material disagreements — preserved, not resolved

### 2.1 The cost of OQ-01 was assessed very differently, and both were right

- **Designer** (`§D3.5`): a flat nine-state reading means D3 "would need **rework**, not just
  relabeling" — the rendering table could expand from three renderings plus six attachable
  reasons to nine independent renderings. Called it "the single largest open risk to this
  document."
- **Engineer** (`§9`): the same change is "a **field-shape migration inside one entity type**,
  not an architectural rework — no module boundary, no service split, and no other T1–T8
  decision changes." Assessed it as low-risk-to-defer.

Neither is wrong. The same decision is cheap in the data model and expensive in the
presentation contract, because the design layer is where nine peers must each be given a
distinct non-numeric treatment. **I am recording this rather than averaging it**, because the
divergence is the finding: a question routed to engineering for a cost estimate would have
come back "low risk," and that answer would have been true and misleading. PD-0006 settles
*which* reading; it does not retroactively make the two estimates agree.

The engineer explicitly declined to self-certify its own decoupling claim and flagged it for
`technical_review`. That is the correct disposition and it stands.

### 2.2 The design assumes a copy owner that this increment does not have

The design states that wording which changes what a statistic asserts is `quant_analyst`'s
call, and that a wording pass is "required before implementation" by "whoever owns copy
(**unassigned in this increment**)." The technical plan does not model a copy or content
pipeline at all. This is not a contradiction, but it is an unowned dependency sitting between
two artifacts that each assume someone else holds it. **Unresolved; raised at HG1.**

## 3. Gaps neither proposal covers — found by reconciling them

### 3.1 Freshness has a presentation contract and no data contract *(material)*

`designs/FEATURE_DESIGN.md` §D5 makes freshness **two independent axes** — per-market price
freshness and FX freshness — and forbids a single blended "live" label. `PD-0006` then leans on
exactly that separation to resolve the `STALE_DATA` modeling gap.

But `implementation/FEATURE_TECH_PLAN.md`'s `MetricResult` carries `sufficiency_state` and
`reason_code` and **names no freshness fields**. So the design requires per-claim, per-axis
freshness disclosure that the proposed contract has no place to carry. The information exists
in the Market Data Layer; nothing specified routes it to the claim.

This is a genuine seam, not a misreading, and it is the direct consequence of a decision I
made in PD-0006 — I moved ordinary staleness off the sufficiency axis without a contract to
move it onto. **Owned by me; routed to `technical_review` to size, and flagged at HG1.** It
does not block `implement`: I1–I3 do not build `MetricResult`'s freshness fields, and
inventing them now would exceed CP0 scope.

### 3.2 The design's "claim object" and the plan's Insight Engine output are unjoined

D2's caveat-preservation mechanism rests on **one shared claim object** — conclusion, reference
point, caveat set, methodology pointer — rendered at four depths. The plan has an Insight
Engine producing Observation / Attention / Warning with a comparison basis and Proof Packets.
These are plainly meant to be the same thing and **neither document says so**. Until one
names the other, P3's structural guarantee is asserted in the design and unimplemented in the
architecture. **Raised at HG1; a naming task for CP6/CP7, not for this increment.**

### 3.3 No accessibility standard exists to design or build against

The designer holds an accessibility veto under `roles/designer.json` and correctly reported it
has nothing to exercise it against: neither the source PRD nor `specs/FEATURE_PRD.md` cites a
standard. The technical plan is silent. **This is a product gap and therefore mine.** I am not
inventing a standard at CP0 to close it — naming WCAG-something without a considered
conformance target would be a silent default of exactly the kind AC-13 exists to prevent.
**Escalated to HG1 as a decision the owner should make before CP7.**

### 3.4 Instrument identity has no fallback scheme

The engineer logged that §10.1's "use FIGI + MIC **where available**" implies a fallback for
instruments lacking a FIGI, and that the plan does not specify one. ADR-P5 keys every
downstream ledger event, position, and analytics join off that identity and is expensive to
change after CP1 data exists. **Not a CP0 defect** — it is correctly logged rather than
guessed — but it is a CP1-blocking item and should be visible at HG1 rather than discovered
at CP1 start.

## 4. Corrections I made as PM

| # | Item | Resolution |
|---|---|---|
| 1 | Designer flagged AC-16's "fifteen fields" as possibly a miscount (read as 14 bullets + a lead sentence) | **Checked the source myself.** §33 lists fifteen bullets; `metric name` is the first bullet. AC-16 is correct as written. `implement` builds to fifteen. |
| 2 | OQ-01 unresolved and blocking I2 | **Closed as a PM product-contract decision** (PD-0006). §32 says *"suggested conceptual states"*, which delegates the shape. Presented to HG1 for confirmation. |
| 3 | `STALE_DATA` does not behave like the other five reason codes | **Resolved in PD-0006** onto the D5 freshness axis. Created gap 3.1 above, which I am disclosing rather than leaving for a reviewer to find. |
| 4 | `implement` went mechanically `ready` when both planning shards completed | **Not clearance.** A DAG artifact. Both the engineer and I flagged it. `implement` proceeds only within PD-0004's CP0 scoping; CP1 stays hard-stopped by §38.4. |

## 5. Verified against the v1.1 mandate

Spot-checked directly against `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` rather than
trusting either worker's citation:

- **§32** (line 1252) — nine items, labelled *"Suggested conceptual states."* Confirms PD-0006's
  premise that the shape is delegated. **Verified.**
- **§33** (line 1277) — fifteen bullets. **Verified**; correction 1 above.
- **§34** — six inputs. Matches T6 and AC-12. **Verified.**
- **§37 deviations** — the plan declares three amendments (splitting the API layer, promoting
  Scenario Lab, adding a Methodology Registry box) and claims no others. §38.3 invites
  amendment with reasons, and the increment brief said so explicitly. **In scope; declared,
  not silent.**

Full AC-01…AC-21 traceability is assembled in the HG1 package, not here. Nothing in this
section is a review finding.

## 6. Scope discipline held

Neither worker exceeded its brief. The designer produced no visual design, no component
library, and no screen presenting a computed number. The engineer implemented nothing, logged
seven open items rather than guessing them, and explicitly refused to manufacture a frontend
framework, deployment target, or AI provider choice — noting correctly that inventing a
default to satisfy "zero silent defaults" would itself be the failure AC-13 tests for. Both
declined to self-certify, and both said so in writing.
