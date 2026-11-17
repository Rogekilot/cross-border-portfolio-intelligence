# Feature PRD — Increment 1: Product Contract and Architecture Proposal (CP0)

**Increment ID:** `INC-001`
**Technical checkpoint:** CP0 (source PRD §38.3)
**Human Approval Gate:** **HG1 — Product & Architecture Approval** (source PRD §38.4, §38.5)
**Workflow:** `feature-development`
**Authored by:** `product_manager`, session `fin-web-9d`, worker `pm-01`, 2026-09-03
**Authoritative source:** `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` (v1.1, 2026-09-02)
**Scope decision:** `decisions/product/PD-0004-increment-1-scope-and-hg1-ordering.md`
**Status:** authored — **not approved**. HG1 has not been reached and no gate is approved.

> **Nothing in this document is an approval.** It is a specification of what must be
> produced and the bar it must meet. HG1 belongs to the designated human product owner
> alone (source PRD §38.1, §38.6).

---

## 0. How to read this document

This is an **increment** PRD. It does not restate the product PRD; it selects a slice of
it and makes that slice executable. Where this document and
`Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` disagree, the source PRD wins and the
disagreement is a defect in this document — report it rather than resolving it locally.

Every claim below carries its evidence standing, per the `prd-authoring` skill:

| Marker | Meaning |
|---|---|
| **[F]** | Fact — stated in the source PRD or observable in the repository |
| **[A]** | Assumption — believed, not verified; may be wrong |
| **[J]** | Judgment — a product decision I made within PM authority |
| **[E]** | Estimate — a quantity I inferred, not measured |

Unmarked prose is connective tissue and carries no independent claim.

---

## 1. Problem

**[F]** A sophisticated self-directed investor holding securities across the US, Mainland
China, and Hong Kong cannot get a consistent analytical picture of their portfolio. Each
brokerage shows one market, in one currency, with its own conventions. Nothing tells
them how much of their return was the security and how much was the exchange rate, what
their real exposure is once listing geography is separated from economic geography, or
whether a metric they are reading is even supported by enough data to mean anything
(source PRD §1, §2.2).

**[F]** The failure mode this product exists to avoid is not "missing features." It is
*confident wrongness* — a number that looks authoritative and is not. The source PRD
encodes that as twelve non-negotiable principles (P1–P12, §3) and as a whole section on
data-sufficiency states (§32) whose purpose is to make "I cannot justify this number"
a first-class output rather than a blank cell.

### The problem *this increment* solves

**[F]** No product contract exists. `specs/FEATURE_PRD.md` held a placeholder
(`decisions/product/PD-0001-prd-reset.md`), and the only prior content was an unrelated
reference scaffold about "a simple onboarding flow" that had been sitting behind a task
shard marked `complete`.

**[J]** So the problem for INC-001 is: **an engineering effort is about to begin against a
product that has never been written down for it.** Until the mission, scope boundaries,
canonical vocabulary, architecture, and sequencing exist as durable artifacts, every
downstream decision is guesswork that will be expensive to unwind, and HG1 — the gate
whose whole purpose is to catch a wrong interpretation before it becomes expensive — has
nothing to review.

---

## 2. Users and context

**[F]** **Primary user (source PRD §4.1):** sophisticated self-directed investor. Holds or
considers holding securities across countries; may use multiple brokerages; understands
diversification, beta, benchmark, volatility at least conceptually; wants professional
analytics without institutional complexity; values both numerical detail and concise
interpretation.

**[F]** **Not V1 primary (§4.2):** beginner retail investors, finance students, wealth
managers, family offices, institutional PMs.

**[F]** **Launch jurisdiction (§4.3):** Mainland China-based investors are the formal V1
commercial assumption. This does not limit *holdings* — US, Mainland China, and Hong Kong
listings are all in V1 scope. Legal, market-data, hosting, privacy, and financial-services
review for Mainland China is a **separate pre-commercial gate** (HG7) and must not be
assumed satisfied.

### The user of *this increment*

**[J]** INC-001 has no end-user-facing surface. Its consumers are:

1. the **human product owner**, who must be able to answer HG1's inspection question —
   *"Does this architecture actually represent what I asked for, and is it capable of
   delivering the product without introducing hidden scope or foundational shortcuts?"*
   (source PRD §38.4) — without reading the repository;
2. the **downstream roles** of every later increment, who must be able to start work
   from these artifacts alone, with no access to this conversation.

**[J]** That second consumer is the harder bar and it is the one that governs. An artifact
that only a reader who was present can follow has failed.

---

## 3. Scope

INC-001 delivers CP0 (source PRD §38.3) in full. Deliverables are assigned to the
workflow tasks that own them.

### 3.1 `ux_planning` — designer — writes `designs/FEATURE_DESIGN.md`

**[F]** Source PRD §6 defines eleven primary surfaces (Overview, Holdings, Performance,
Exposure, Risk & Analytics, Insights, Scenario Lab, AI Analyst, Transactions, Portfolio
Settings / Policy, Methodology & Evidence) and a four-level depth model
(**Quick → Simple → Investor → Professional/Methodology**) using progressive disclosure
rather than separate retail and professional products.

Required:

- **D1.** The information architecture: the eleven surfaces, what each is *for*, and what
  belongs on each — at the level of information hierarchy, not visual design.
- **D2.** The interaction contract for the depth model: how a user moves between the four
  levels, and what is guaranteed to be preserved across that movement. **[F]** All layers
  must use the same underlying facts (§6), and simplification may drop precision but never
  a caveat that changes the conclusion (P3).
- **D3.** The **presentation contract for metric states** (§32): how each state is
  rendered so it can never be mistaken for a number. **[F]** §32 is explicit that zero,
  blank, or fabricated fallback values are forbidden. This is a design deliverable
  because "N/A" rendered badly is indistinguishable from a bug.
- **D4.** The **evidence-inspection affordance** (P9, FR-032): how a user gets from a
  claim to the methodology and inputs behind it. Structure only — the Proof Packet's
  contents are a later increment.
- **D5.** The **freshness disclosure pattern** (P10, FR-033, NFR-008): how the product
  shows that cross-market prices are not simultaneously real time, without implying
  they are.

**Out for the designer in this increment:** visual design, component library, typography,
color, copywriting, and any screen that presents a computed financial number. There are
no computed numbers yet, by design.

### 3.2 `tech_planning` — engineer — writes `implementation/FEATURE_TECH_PLAN.md`

Required, tracking source PRD §38.3 CP0 item by item:

- **T1.** Proposed system architecture, with service and module boundaries. **[F]** §37
  offers a directional decomposition and states it is *not* a mandatory technology stack.
  Treat it as a starting reference to accept, amend, or reject with reasons — not as a
  constraint.
- **T2.** Proposed technology stack and major dependencies, with the reasoning.
- **T3.** Initial domain model: the entities, their relationships, and their boundaries.
  **[F]** Must preserve the identity layering the source PRD requires — security identity
  across exchange, issuer, currency, and listing (§10, rule §44.10) — and must not conflate
  listing geography with economic exposure (§10.4, rule §44.12).
- **T4.** The **P1 boundary made structural**: where the deterministic engine ends and the
  AI layer begins, and what prevents the AI layer from originating a number it presents
  (P1, §22.3, NFR-002). A convention is not an answer here; the question is what makes
  the violation hard.
- **T5.** The **vendor-independence boundary** (P11, NFR-003): the normalized internal
  contracts, and why substituting a market-data vendor would not reach core analytics.
- **T6.** The **determinism and reproducibility strategy** (P12, NFR-001, NFR-010, §34):
  how identical inputs plus an as-of date plus a methodology version yield an identical
  output, and how a calculation is reproduced for audit. **[F]** Day-count, annualization,
  compounding, and FX-fixing conventions are part of the method and belong in
  `methodology/` — naming *which* conventions is `quant_analyst`'s authority, not the
  engineer's and not mine.
- **T7.** Implementation sequence and dependency graph across CP1–CP11, with the HG gates
  marked as blocking (§38.5).
- **T8.** Unresolved technical choices **logged, not guessed** (§38.3, rule §44.17).
  Anything hard to reverse is proposed as an ADR.

**Out for the engineer in this increment:** implementing any of it. T1–T8 are proposals
for HG1 to approve or reject.

### 3.3 `implement` — engineer — writes `src/`, `tests/product/`

**[J]** Narrowly scoped, for the reason set out in PD-0004: HG1 hard-stops CP1
implementation, so this task delivers only CP0-appropriate structure carrying no
financial logic.

- **I1.** **Canonical product vocabulary** as code. The terms the source PRD uses with
  precision and that downstream code must not redefine locally.
- **I2.** **Metric-state model** (§32). The state enumeration, and the structural rule
  that a metric carrying a non-`AVAILABLE` sufficiency state **cannot** also carry a
  presentable number. **[J]** This is the single highest-leverage thing that can be built
  before HG1: P5 is enforced by construction or it is enforced by everyone remembering.
- **I3.** **Methodology registry schema and validator** (§33), with the fifteen required
  fields, plus **zero metric entries**. **[F]** Every entry is a methodology decision owned
  by `quant_analyst` (source PRD §33, §44.4) and is out of scope here.
- **I4.** Tests in `tests/product/` covering I1–I3, including the negative cases: a metric
  state that tries to carry both `INSUFFICIENT_DATA` and a value must fail, and a registry
  entry missing a required field must fail validation.

**Explicitly out for `implement`:** ledger events, positions, cash, accounts, portfolios,
instrument resolution, prices, FX, corporate actions, benchmarks, and every analytic
calculation. All of that is CP1 or later and is gated by HG1.

### 3.4 `design_review` / `technical_review`

**[J]** These review documents and a contract skeleton, not a feature. The review question
is not "does it work" but **"could a competent stranger execute the next increment from
these artifacts, and does the proposal actually satisfy P1–P12?"** Reviewers must record
`not_run` for any check they could not execute (workflow `fallback`, source PRD §38.6);
an unexecuted check recorded as passing is a governance failure, not a rounding error.

### 3.5 `pm_acceptance`

**[J]** Assembles the HG1 Gate Review Package with all fourteen elements of source PRD
§38.2, drives the project to `AWAITING_HUMAN_REVIEW`, and stops. It records the human's
decision verbatim. It does not make it.

---

## 3.6 What V1 *is* — added 2026-09-03 after `technical_review`

**[F]** `review-01` found AC-01 satisfiable only in one direction: this document listed
what V1 excludes but never restated what it includes, so a reader with no access to the
source PRD could correctly restate the out-of-scope boundary and **not** the in-scope one.
AC-01 requires both. Restated verbatim from source PRD §5.1 and §5.2:

**Supported asset types — V1 supports exactly:** exchange-listed common stocks;
exchange-listed ETFs; cash balances; multiple currencies.

**Supported listing markets:** United States; Mainland China; Hong Kong.

Nothing else is in V1. This is not a floor to build on — §5.3's exclusions are the
complement of this list, and adding an asset type to it is a material scope change
requiring approval (`roles/product_manager.json`).

---

## 4. Out of scope

**[F]** Out of V1 entirely (source PRD §5.3), and therefore out of this increment: bonds,
mutual funds, options, futures, crypto, private assets, real estate, structured products,
live broker integrations, order execution, automatic trading, personalized buy/sell
recommendations, tax-loss harvesting, tax-return preparation, jurisdiction-specific tax
advice, advanced ETF look-through, complex corporate reorganizations, institutional
portfolio-management workflows.

**[F]** V1.5 candidates (§5.4), out of this increment: ETF look-through, underlying-security
overlap, look-through sector/country exposure, broker/account synchronization, expanded
market coverage, sophisticated factor/risk decomposition.

**[J]** Out of **INC-001** specifically, though in V1 — deferred to CP1+ and gated by HG1:

| Deferred | Checkpoint | Gate |
|---|---|---|
| Ledger, positions, cash, point-in-time reconstruction | CP1 | HG2 |
| Market-data normalization, adapters, freshness, FX history | CP2 | HG2 |
| Performance engine, FX attribution | CP3 | HG2 |
| Risk and benchmark engine | CP4 | HG3 |
| Diversification, correlation, drift | CP5 | HG3 |
| Insight engine, Proof Packets | CP6 | HG5 |
| Core web UX implementation | CP7 | HG4 |
| Scenario Lab | CP8 | HG5 |
| AI Analyst | CP9 | HG5 |
| Integration and validation | CP10 | HG6 |
| Pre-commercial hardening, China regulatory review | CP11 | HG7 |

**[J]** Also out of scope: **any metric entry in the methodology registry.** The registry's
structure is in; its contents are `quant_analyst`'s and belong to the increment that
implements the metric.

**[F]** And out of scope by product posture (§31): individualized buy/sell instructions,
automatic rebalancing, execution, custody, brokerage, tax advice — in V1 and in this
increment. Advisory and execution capability must remain *separable* from the analytics
core so a later regulatory expansion cannot contaminate it.

---

## 5. Binding invariants

**[F]** P1–P12 (source PRD §3) bind every downstream role and are not negotiable by any
agent. The ones with direct force in INC-001:

| Principle | Force in this increment |
|---|---|
| **P1** engine owns facts, AI owns explanation | T4 must make the boundary structural, not conventional |
| **P3** simplification preserves uncertainty | D2 must guarantee caveat survival across depth levels |
| **P4** every judgment needs a reference point | Vocabulary (I1) must carry the reference-point concept |
| **P5** no metric without sufficient data | I2 enforces it by construction; D3 renders it |
| **P9** insights auditable | D4 structure; T6 reproducibility |
| **P10** freshness always visible | D5 disclosure pattern |
| **P11** vendor independence | T5 normalized contracts |
| **P12** deterministic reconstruction | T6 strategy (implementation is CP1) |

**[F]** P2, P6, P7, P8 have no implementable surface in INC-001 — there are no metrics,
forecasts, personalized constraints, or scenarios yet. They still bind every *proposal*:
an architecture that makes P8 (actual/hypothetical separation) hard to achieve later is
a defect discoverable now, and HG1 is where it should be caught.

---

## 6. Acceptance criteria

Each is observable and testable, and cites the source PRD requirement it serves. "Testable"
for a document means a reviewer can answer yes or no without inferring intent.

### Product contract

- **AC-01** (§38.3, §44.1) `specs/FEATURE_PRD.md` states the product mission, primary user,
  V1 scope, and out-of-scope, and a reader with no access to this session can restate all
  four correctly. **Test:** `technical_review` confirms each is present and unambiguous.
- **AC-02** (§38.3, §44.2) P1–P12 are referenced by the artifacts that bind downstream
  roles, and each of P1, P3, P4, P5, P9, P10, P11, P12 maps to at least one named
  deliverable. **Test:** the §5 table resolves to real sections of D*/T*/I*.
- **AC-03** (§5.3, §5.4) The V1 / V1.5 / out-of-scope matrix is explicit and complete
  against source PRD §5. **Test:** every item in §5.3 and §5.4 appears in §4 above.

### Design

- **AC-04** (§6) All eleven surfaces are specified with purpose and information hierarchy.
  **Test:** count is eleven; each names what it is for. Zero unnamed surfaces.
- **AC-05** (§6, P3) The Quick → Simple → Investor → Professional transition is specified,
  including what is preserved. **Test:** the spec states, for at least three worked
  examples drawn from P3 (beta 1.30, correlation 0.80, negative alpha), what each depth
  level says — and none of the simpler renderings is one P3 forbids.
- **AC-06** (§32, P5, FR-028) Every metric state has a specified rendering, and none of
  them renders as zero, blank, or a fallback value. **Test:** enumerate the states from
  §32; each has a rendering; a reviewer confirms none is mistakable for a number.
- **AC-07** (P9, FR-032) The path from a displayed claim to its evidence is specified and
  reachable from every surface that displays a claim. **Test:** trace it for one surface.
- **AC-08** (P10, FR-033, NFR-008) The freshness pattern distinguishes per-market price
  freshness from FX freshness and never implies uniform real-time data. **Test:** the spec
  shows a mixed-freshness cross-market case.

### Technical

- **AC-09** (§38.3, §37) Architecture, stack, dependencies, and module boundaries are
  documented with reasoning. **Test:** each major boundary states what is on each side and
  why the split is there.
- **AC-10** (P1, §22.3, NFR-002) The plan names the specific mechanism preventing the AI
  layer from originating a presented number. **Test:** the mechanism is a structural
  control, not a guideline. A reviewer must be able to describe how a violation would fail.
- **AC-11** (P11, NFR-003) Normalized internal contracts for Instrument, SecurityPrice,
  FXRate, CorporateAction, BenchmarkSeries are specified (§11.1), and the plan explains why
  a vendor swap does not reach core analytics. **Test:** all five are present.
- **AC-12** (P12, NFR-001, NFR-010, §34) The determinism and reproducibility strategy names
  the versioned inputs required to reproduce a calculation, and states that conventions
  live in `methodology/`. **Test:** the six §34 inputs are enumerated.
- **AC-13** (§38.3, §44.17) Unresolved technical choices are logged as open questions or
  ADR proposals. **Test:** at least the stack and persistence choices are explicit —
  logged, or decided with reasons. Zero silent defaults.
- **AC-14** (§38.5) The implementation sequence covers CP1–CP11 with HG gates marked
  blocking. **Test:** the §38.5 mapping is reproduced correctly.

### Implementation

- **AC-15 — CORRECTED 2026-09-04 by `decisions/product/PD-0007-limited-carries-a-value.md`.**
  (§32, P5) **`value is None` ⇔ `sufficiency_state is INSUFFICIENT_DATA`.** `AVAILABLE`
  and `LIMITED` both **require** a value; `INSUFFICIENT_DATA` forbids one. `LIMITED` is
  the state for a metric that is *computable* on a basis weak enough that the caveat
  changes the conclusion, and it renders the value plus a mandatory non-dismissible
  qualifier (`designs/FEATURE_DESIGN.md` §D3.2). **Test:** automated negative tests in
  `tests/product/` fail the construction of `INSUFFICIENT_DATA` + value, `AVAILABLE` +
  `None`, and `LIMITED` + `None`; a positive test proves `LIMITED` + value constructs.
  This is still the one acceptance criterion in INC-001 that a machine decides.

  *This criterion was corrected twice. PD-0007's first ruling ("`LIMITED` may carry a
  value, and normally does") left `LIMITED` permitted-but-not-required, which
  `designer-04` showed left a branch §D3.2 has no rule for (BF-4). The amendment made it
  a total equivalence. `engineer-02` flagged that this section still stated the first
  ruling and correctly declined to edit it — `specs/` is outside its write authority.*
  *Original wording, struck — it conflated "weak but computable" with "not computable",
  which would collapse `LIMITED` into `INSUFFICIENT_DATA` and leave the three-state
  vocabulary carrying two states' worth of meaning. Found by `designer-04` in
  `design_review` round 2 (BF-3):*
  ~~A metric state carrying a non-`AVAILABLE` sufficiency state cannot also carry a
  presentable value. Test: an automated negative test in `tests/product/` fails the
  construction.~~ **(End of superseded text.** `review-01` N-18: the strikethrough was
  opened and never closed, so on some renderers the superseded wording would have shown
  with literal `~~` markers and no strike at all, directly beneath the corrected version,
  inside the document the gate package is built from. Closed 2026-09-04.**)**
- **AC-16** (§33, §44.4) The registry schema requires all fifteen fields of §33 and
  rejects an entry missing any of them. **Test:** automated, one negative case per
  required field, or a single parameterized case covering all fifteen.
- **AC-17** (§33) The registry contains zero metric entries. **Test:** automated; a
  non-empty registry fails this increment.
- **AC-18** (NFR-001) Tests in `tests/product/` are deterministic and pass on repeat runs.
  **Test:** run twice; identical results.

### Governance

- **AC-19** (§38.2) The HG1 Gate Review Package contains all fourteen required elements,
  including reproduction instructions and the human decision block. **Test:** count is
  fourteen.
- **AC-20** (§38.1, §44.22) On reaching HG1 the project is in `AWAITING_HUMAN_REVIEW` and
  no downstream task has been dispatched. **Test:** `project-state.json` shows the gate
  active; every CP1 task shard is `blocked`.
- **AC-21** (§44.20) Every deliverable states its own known limitations and unresolved
  items. **Test:** each artifact has such a section, non-empty.

---

## 7. Constraints

**[F]** **Regulatory (§31, §41.2).** V1 posture is analytics, education, evidence-backed
interpretation, and hypothetical scenarios. Not advice, execution, custody, or tax
guidance. Specialist review for Mainland China is a pre-commercial gate; technical
availability of data never implies legal redistributability.

**[F]** **Licensing (§11.4, §41.1).** Benchmark and market-data licensing is separable and
unresolved. No design or plan may assume redistribution rights.

**[F]** **Scale (NFR-007).** Approximately 500 holdings per portfolio in V1. Architecture
proposals must be viable at that size; **[J]** they need not be optimized for it in CP0.

**[F]** **Environment.** No network egress and no market-data credentials are provisioned
in this workspace; vendor access is a human provisioning step (`CLAUDE.md`, handoff §7.7).
**[J]** Therefore no deliverable in INC-001 may depend on a live vendor call, and any
verification requiring one must be recorded `not_run`.

**[F]** **Surface.** The shell cannot mutate the filesystem here; `tech_planning` and
`implement` must use Write/Edit or approved helpers (workflow `fallback` on both tasks).

**[F]** **Governance.** HG1 is a blocking dependency. Passing tests, an internal reviewer's
PASS, elapsed time, and absence of objection are **never** approval (§38.1, §44.23).

---

## 8. Assumptions

Labeled as assumptions, per the source PRD's own instruction (§22) and the authoring skill.
Each is wrong-able; if one is wrong, the work it supports needs revisiting.

- **~~[A] A-01~~ → [F] A-01, CLOSED 2026-09-03.** Source PRD v1.1 dated 2026-09-02 is the
  authoritative governing product mandate. This is no longer an assumption: the human
  product owner decided it explicitly and reserved the right to supersede it explicitly.
  See `decisions/product/PD-0005-v1-1-prd-is-the-governing-mandate.md`. The "Draft v1.1"
  string in that file's own header does not limit its authority.
- **[A] A-02.** The eleven surfaces of §6 are the intended V1 information architecture and
  not an illustrative list. Read as authoritative because §6 states them without hedging.
- **[A] A-03.** "Responsive web application" (§1) means a browser-delivered client with no
  V1 native mobile app. Stated as the product surface but never elaborated.
- **[A] A-04.** No existing codebase, schema, or vendor contract constrains the
  architecture. `src/` does not exist and the workspace holds only harness material.
- **~~[A] A-05~~ → [J] A-05, CLOSED 2026-09-03 by `decisions/product/PD-0006-metric-state-vocabulary-is-layered.md`.**
  No longer an assumption: the layered reading is now a recorded product-contract decision,
  taken because §32 labels its list *"suggested conceptual states"* and so delegates the
  shape. PD-0006 additionally resolves a `STALE_DATA` modeling gap that this assumption,
  as originally written, did not see. Original text follows.
  The nine states of §32 are a single vocabulary rather than two. **[J]** I am
  treating `AVAILABLE` / `LIMITED` / `INSUFFICIENT_DATA` as *sufficiency* states and the
  remaining six (`STALE_DATA`, `UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`,
  `MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`) as *reason* codes that
  explain a non-`AVAILABLE` sufficiency state. This reconciles §32's nine with the three
  named in `CLAUDE.md`. See OQ-01 — it needs confirming, not assuming.
- **[A] A-06.** A single human product owner holds all seven gates. Nothing names a
  distinct approver per gate.

---

## 9. Open questions

Every question has an owner and a decision point. **[J]** None of these blocks authoring;
all of OQ-01–OQ-04 should be resolved at or before HG1.

| ID | Question | Owner | Needed by | If unresolved |
|---|---|---|---|---|
| ~~**OQ-01**~~ | ~~Is the §32 state vocabulary nine states, or three sufficiency states plus six reason codes (A-05)?~~ **CLOSED 2026-09-03 as a PM product-contract decision — §32 says "suggested conceptual states", which delegates the shape. Layered model adopted; `STALE_DATA` modeling gap resolved onto the D5 freshness axis. Presented to HG1 for confirmation, not decided by the owner. See PD-0006.** | ~~human product owner~~ → `product_manager` | — | — |
| ~~**OQ-02**~~ | ~~Technology stack and persistence — chosen by the engineer in T2/T13, or reserved to the human?~~ **CLOSED 2026-09-22 by the human product owner. `PD-0020` resolved the architecture direction (Python-first backend; TypeScript-SPA architectural class, specific framework still human-undecided; PostgreSQL-class relational persistence; first-class append-only ledger/event model; modular monolith). `PD-0021` established the CP1 identity and entry preconditions (immutable internal Issuer/Instrument/Listing IDs as persistence and join keys, with FIGI/MIC retained as external resolution primitives). See `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md` for the implementation-facing synchronization.** | ~~human product owner~~ → **decided** | ~~HG1~~ — | — |
| ~~**OQ-03**~~ | ~~Is the draft status of source PRD v1.1 (A-01) intentional? Is a newer version pending?~~ **CLOSED 2026-09-03 by the human product owner: v1.1 is the authoritative governing mandate unless explicitly superseded. See PD-0005.** | human product owner | — | — |
| **OQ-04** | Which market-data vendors are realistically available for the launch jurisdiction? Bears on T5's adapter shape and §41.1 risk. | human product owner | HG1 (informational), CP2 (blocking) | T5 stays vendor-agnostic, which is required anyway |
| **OQ-05** | Does the fixed workflow DAG need a documentation-only variant for checkpoints with no feature to build? | `harness_architect` + human owner | before the next documentation-only increment | PD-0004 scopes around it for INC-001 only |

**[J]** OQ-05 is a harness question, not a product one. It is recorded here because this
increment is where it surfaced, not because I can decide it.

### 9.1 Phase-B authority note — synchronization, not a new decision

**[F] Added 2026-09-22 by `product_manager`, worker `pm-01`, session `fin-web-e5`.**

> **The implementation-facing synchronization of the accepted Phase-B decisions lives at
> `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md`.** That file carries the Engineer-readable
> statement of `PD-0020` and `PD-0021`. The **primary technical implementation contract**
> remains `implementation/FEATURE_TECH_PLAN.md`.

**Why this note exists.** `decisions/product/` is outside the `engineer` role's
`read_paths` (`security-policy.json`), so an Engineer cannot lawfully read `PD-0020` or
`PD-0021`. This document **is** a declared read of the `implement` task, so the pointer above
is the discoverability bridge between the accepted decisions and the role that must implement
them. A dispatch message is not a substitute: it is not durable and it is not a declared
input.

**What this edit is, and is not.** The OQ-02 row above **synchronizes an already-decided
human ruling**; the decision itself is `PD-0020`/`PD-0021` and lives there. **No new PRD or
spec scope decision is made by this edit**, and nothing else in this document was changed.

**Why no `prd` task revision was opened.** `prd` is `complete` and is upstream of
`ux_planning` and `tech_planning`, which are also `complete`. `workflows/feature-development.json`
declares a `revalidation` block for **`implement` only** — `prd`, `ux_planning` and
`tech_planning` have none, and under ADR-0030 a task with no `revalidation` block is not
restorable. Reopening `prd` would therefore demote two completed planning tasks into a state
from which only genuinely redoing them restores completion, destroying design and
technical-planning history for a status synchronization that required no new decision. The
edit was made under the Product Manager's own `specs/` write authority instead, per
`PD-0021` §6.2 Route S1.

---

## 10. Risks

**[F]** Source PRD §41 names six product risks. The two with live force in INC-001:

- **[F] §41.3 False precision.** The risk that the product shows a number it cannot
  justify. **[J]** AC-15 is the direct structural mitigation and is why I2 is in this
  increment rather than deferred.
- **[F] §41.4 AI overreach.** The risk that the AI layer originates or reframes a
  financial fact. **[J]** AC-10 forces the plan to answer this structurally at CP0, when
  the boundary is cheap to place, rather than at CP9 when it is not.

**[J] R-01, increment-specific.** CP0's deliverables are documents, and documents can be
internally consistent and still wrong about the product. This is precisely the risk HG1
exists to catch (§38.6 item 1), which is why the acceptance criteria above are written to
be answerable by a reader rather than by their author.

---

## 11. Traceability

| Deliverable | Source PRD | Acceptance |
|---|---|---|
| D1 information architecture | §6 | AC-04 |
| D2 depth model contract | §6, P2, P3 | AC-05 |
| D3 metric-state presentation | §32, P5, FR-028 | AC-06 |
| D4 evidence affordance | §21, P9, FR-032 | AC-07 |
| D5 freshness disclosure | P10, FR-033, NFR-008 | AC-08 |
| T1 architecture | §37, §38.3 | AC-09 |
| T2 stack | §38.3 | AC-09, AC-13 |
| T3 domain model | §10, §38.3 | AC-09 |
| T4 P1 boundary | P1, §22.3, NFR-002 | AC-10 |
| T5 vendor independence | P11, §11.1, NFR-003 | AC-11 |
| T6 determinism | P12, §34, NFR-001, NFR-010 | AC-12 |
| T7 sequence | §38.3, §38.5 | AC-14 |
| T8 unresolved choices | §38.3, §44.17 | AC-13 |
| I1 vocabulary | §38.3 | AC-01 |
| I2 metric-state model | §32, P5 | AC-15 |
| I3 registry schema | §33, §44.4 | AC-16, AC-17 |
| I4 tests | NFR-001 | AC-18 |
| HG1 package | §38.2 | AC-19, AC-20 |

---

## 12. Definition of done for INC-001

All of, and none inferred from another:

1. AC-01 through AC-21 satisfied, or explicitly recorded as not satisfied with reasons.
2. Every artifact persisted; every task shard transitioned via
   `scripts/update_task_state.py` with genuine execution provenance.
3. Both reviews completed, with unexecuted checks recorded `not_run`.
4. The HG1 Gate Review Package assembled to §38.2's fourteen elements.
5. Project in `AWAITING_HUMAN_REVIEW`, no CP1 work dispatched.
6. **The human product owner has recorded an HG1 decision.**

**[F]** Item 6 is not something this increment can complete on its own, and no agent may
substitute for it (§38.1, §44.23). Until it exists, INC-001 is `READY_FOR_HUMAN_REVIEW`
at most — never `complete`.
