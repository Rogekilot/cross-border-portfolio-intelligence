# Technical Plan — Increment 1 (INC-001), CP0 Architecture Proposal

**Increment:** `INC-001` | **Checkpoint:** CP0 | **Gate:** HG1 — Product & Architecture Approval
**Workflow task:** `feature-development/tech_planning` | **Role:** `engineer` | **Worker:** `engineer-01`
**Authored:** 2026-09-03
**Authoritative inputs:** `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` (v1.1, governing per
`decisions/product/PD-0005-...md`), `specs/FEATURE_PRD.md` (increment scope),
`decisions/product/PD-0004-...md` (CP0/HG1 sequencing)

**Status:** proposal — not approved. Everything in this document is a recommendation for
HG1 to approve, amend, or reject. Nothing here is implemented, and nothing here commits
the codebase to anything (§38.4 hard-stop: CP1 implementation may not begin until HG1 is
`APPROVED` or `APPROVED_WITH_CONDITIONS`).

Evidence markers, consistent with `specs/FEATURE_PRD.md`: **[F]** fact from source
material, **[A]** assumption (believed, may be wrong), **[J]** judgment within engineer
authority, **[E]** estimate. Unmarked prose is connective tissue.

---

## 0. How this plan is organized

Sections 1–8 map one-to-one to T1–T8 of `specs/FEATURE_PRD.md` §3.2. Section 9 works
through OQ-01's effect on T3/T4 explicitly, as the brief requires. Section 10 is the
required "known limitations and unresolved items" (AC-21). Section 11 is a traceability
table back to AC-09…AC-14.

---

## 1. T1 — Proposed system architecture, service and module boundaries

### 1.1 Disposition on source PRD §37

**[F]** §37 is explicit that its diagram is "directional, not a mandatory technology
stack." I accept its **decomposition into bounded contexts** (Portfolio, Instrument,
Market Data, Analytics, Insight, AI Orchestration) and its stated ordering rule ("AI
orchestration layer should be downstream of the deterministic analytical truth layer").
I amend it in four ways, each with a reason tied to a PRD requirement §37 does not
itself resolve:

1. **[J] Add an explicit Methodology Registry as a first-class shared service/library**,
   not a sub-bullet of Analytics Engine as §37 implies. §33 requires it centralized and
   versioned, and T6 (determinism) and every analytics module depend on it as a
   read dependency, not an internal detail of one engine. Making it a boundary now
   avoids every future engine re-embedding its own copy of a formula (§44 rule 4).
2. **[J] Split "Application/API Layer" into two API surfaces with different trust
   levels**: a **Query/Command API** (used by the web client, has full read access to
   computed facts and write access to ledger/policy mutations) and a **Tool Gateway**
   (the *only* interface the AI Orchestration layer may call — read-only, fixed
   function signatures per §22.2). §37's single "Application/API Layer" box does not
   show this distinction, and T4 depends on it existing as a drawn boundary, not an
   internal convention. See §4 below.
3. **[J] Draw "Advisory/Execution" as an explicitly absent module**, not an omitted one.
   §31 requires advisory/execution capability to stay *separable* from the analytics
   core "so future regulatory expansion does not contaminate it." The structural
   answer at CP0 is: no such module exists in V1, and the two boundaries above (Tool
   Gateway; Query/Command API) are the only surfaces anything resembling advisory logic
   could ever attach to — and both are read-only with respect to executing a trade.
   There is no execution adapter, no brokerage credential store, and no order-routing
   concept anywhere in this proposal. If a future increment adds one, it attaches
   behind a new gateway, not inside Analytics or AI Orchestration.
4. **[J] Name Scenario Lab as a boundary of its own**, not folded into "Analytics
   Engine → Scenario calculations" as §37's bullet does. P8 (§3, FR-030) requires actual
   and hypothetical state to be *strictly* separated; giving Scenario its own module
   with its own (non-persistent, or separately-namespaced) state store makes "scenario
   output cannot be written back to the ledger" a boundary a code reviewer can see,
   rather than a discipline every analytics function must individually remember.
5. **[J] Add a Rendering Service as a fifth boundary, on the trusted side, between
   AI Orchestration and the client.** **[Added 2026-09-04, closing
   `reviews/TECH_REVIEW.md` B-5.]** §4.3's P1 mechanism (provenance-bound rendering)
   made this component load-bearing — it is the only thing that turns an AI-authored
   template into displayed text, and every P1 guarantee in §4 passes through it — but
   the rework that introduced it in §4 did not draw it here, in §1.2's diagram, §1.3's
   boundary table, or §1.4's dependency rules, while §12 continued to assert
   completeness. `review-01` is right that this fails this section's own stated test
   (item 2 above: a boundary T4 depends on must be *drawn*, not left as an internal
   convention) and is corrected below, in §1.2, §1.3, §1.4, and §12.

**On T4's dependency on a drawn boundary, restated for this newly-added one:** the
Rendering Service is not optional scaffolding — it is where §4.3's slot resolution,
§4.3a's value-shape/number-word scan, and §4.3b's label-binding (see §4 below) all
execute, on the trusted side of the P1 line, with no code path for AI Orchestration
to reach the client except through it.

### 1.2 Proposed bounded contexts

```
                          Responsive Web Client
                                   |
                     -------------+-------------------------------+
                     |                                             |
              Query/Command API                          Rendering Service  <-- (Added
                     |                                    (trusted; resolves     2026-09-04,
                     |                                    {{slot:...}} tokens    closes B-5)
                     |                                    against the audit
                     |                                    trail; scans/rejects
                     |                                    free text per §4.3a;
                     |                                    binds labels per
                     |                                    §4.3b; the ONLY path
                     |                                    from AI Orchestration
                     |                                    output to the client)
                     |                                             |
                     |                                       Tool Gateway  <-- AI Orchestration
                     |                                       (read-only,        can call ONLY
                     |                                        fixed fns,         this box, and
                     |                                        §22.2 list)        emits templates
                     |                                             |             ONLY to the
                     |                                             |             Rendering
                     |                                             |             Service; see T4
        +------------+---------+----------------+------------------+
        |            |         |                |                  |
   Portfolio    Instrument   Market Data    Analytics Engine   Insight Engine
    Service      Service       Layer         (Performance,      (Fact/Interp/
   (Accounts,   (Issuer/     (Vendor          Risk, Attrib-      Pref-dependent,
    Ledger,      Listing,     adapters,        ution, Diver-      Observation/
    Position     FIGI/MIC     normalized       sification,        Attention/
    Engine,      mapping)     Instrument/      Drift, Scenario    Warning,
    Snapshots)                Price/FX/CA/     calculations)      Proof Packets)
                               Benchmark
                               contracts)
                                                     |
                                          Methodology Registry
                                       (schema + versioned entries;
                                        read by every Analytics/
                                        Insight/AI consumer; also read
                                        by the Rendering Service for
                                        §4.3b label-binding)

   Scenario Lab: separate module, reads Portfolio+Analytics as of a snapshot,
   writes only to its own hypothetical-state store. No path from Scenario Lab
   back into Portfolio Service's ledger.

   AI Orchestration: separate module (proposed: separate process — see §4),
   calls Tool Gateway only, and its output is a template, not displayed text.
   No DB credential, no import of Analytics/Insight/Portfolio internals, and
   (added 2026-09-04) no network path to the client that bypasses the
   Rendering Service.

   Rendering Service: separate trusted component, on the same trust side as
   the Query/Command API (holds no AI-model credential, is not reachable by
   AI-authored code as anything but a template consumer). This is where §4's
   P1 mechanism actually executes; see §4.3–§4.3b.

   Advisory/Execution: does not exist. No module, no adapter, no interface stub.
```

### 1.3 Reasoning for the split (AC-09: "each major boundary states what is on
each side and why")

| Boundary | On one side | On the other | Why split here |
|---|---|---|---|
| Query/Command API vs Tool Gateway | Full-trust web client access | Read-only, fixed-signature AI access | T4 — makes the P1 boundary a network/credential fact, not a code convention |
| Portfolio Service vs Instrument Service | Ledger, positions, cash (owns *what the user holds*) | Issuer/listing identity, FIGI/MIC (owns *what a security is*) | §10.3: listing-level and issuer-level concerns have different lifecycles — a listing can be delisted without the issuer's ledger history changing |
| Instrument Service vs Market Data Layer | Static identity metadata | Time-varying price/FX/CA data | Identity rarely changes; price/FX/CA data are high-churn and vendor-sourced — coupling them would force every identity read through a vendor adapter |
| Market Data Layer vs Analytics Engine | Vendor-shaped raw data, adapted to normalized contracts | Vendor-agnostic computation over normalized contracts only | T5 / P11 — this is the vendor-independence seam |
| Analytics Engine vs Insight Engine | Computes metrics + states | Interprets metrics into Observation/Attention/Warning with a comparison basis | §20: interpretation carries a severity/taxonomy model analytics does not; keeping them separate stops severity logic from leaking into a metric calculation |
| Insight Engine vs AI Orchestration | Deterministic, rule-based interpretation | Natural-language explanation of already-interpreted facts | P1 — the hard line the whole product depends on |
| Portfolio Service (actual) vs Scenario Lab (hypothetical) | Real ledger, real positions | Hypothetical state, never persisted to the ledger | P8 / FR-030 |
| **AI Orchestration vs Rendering Service** **[Added 2026-09-04, closes B-5; slot shape corrected 2026-09-05, closes N-13]** | Authors a template: connective prose + `{{slot: tool_call_id, field_path}}` citations only — no AI-authored label or identity reference; no display authority | Resolves every citation against the session's Tool Gateway audit trail, formats the value, renders the label from **the cited call's own `methodology_ref` and Computation Manifest** (§4.3b) — never from anything the AI supplied — and scans surrounding free text against §4.3a's allowlist; rejects (does not render) anything it cannot resolve or that fails the scan | This is now the single most important trust boundary in the system, per `review-01`'s B-5 — every P1 guarantee in §4 passes through it, and it must be a drawn module boundary, not an internal convention, by this section's own stated test (item 2) |

### 1.4 Deployment shape (ties to T2)

**[J]** I propose a **modular monolith** for V1 — one deployable backend process
internally organized into the bounded contexts above, each with enforced one-directional
dependency rules (e.g., `analytics` may import `market_data` contracts and
`methodology_registry`, never the reverse; `ai_orchestration` may import only
`tool_gateway`'s public interface; **[added 2026-09-04, closes B-5]** `ai_orchestration`
may not import anything from the client-facing transport layer or hold any credential
that would let it deliver a response to the client directly — its only lawful output
sink is the `rendering_service`'s template-intake interface, and `rendering_service` in
turn may import `methodology_registry` (for §4.3b's label-binding) and the Tool
Gateway's audit-trail reader, but never `ai_orchestration`'s internals) — with **one
deliberate exception**: AI Orchestration is proposed as a *separate process* even within
the monolith's deployment unit, because T4's structural guarantee depends on it holding
no shared database credential (§4). **[SUPERSEDED FOR V1, 2026-09-22, by `PD-0020` —
see §13.B.]** The separate-process exception above is proposal history, not the active
V1 decision: for V1 the AI module runs inside the one deployable, behind the boundary
restated in §13.B, and process-level isolation is deferred to CP9 hardening. The Rendering Service is **not** a separate process
— it needs no isolation from the database (it is on the trusted side already) and
runs wherever the Query/Command API does; the only property it needs is that
AI Orchestration cannot address the client except through it.
Reasoning: at NFR-007 scale (~500 holdings, single-portfolio-at-a-time analytics,
no live market-data ingestion pipeline in V1), a distributed microservice architecture
adds operational complexity (service discovery, network partition handling, distributed
tracing) that buys nothing at this scale and works against NFR-006 responsiveness. The
module boundaries above are drawn so that any one context *could* be extracted into its
own service later without a rewrite — that extractability, not present-day
distribution, is what the boundaries are for.

---

## 2. T2 — Proposed technology stack and major dependencies

**[F]** OQ-02 in `specs/FEATURE_PRD.md` leaves open whether stack/persistence are the
engineer's call or the human owner's. Per the increment brief, I propose with reasoning;
HG1 decides. AC-13 requires zero silent defaults, so I am explicit rather than vague
even where I expect HG1 to overrule me.

| Layer | Proposal | Reasoning |
|---|---|---|
| Backend language/runtime | **[J]** Python 3.x, statically type-checked (mypy), with immutable/frozen domain models (e.g. `dataclass(frozen=True)` or an equivalent validation library) | Finance analytics benefit from Python's numerical ecosystem (precise decimal arithmetic via `decimal.Decimal` for money, `numpy`/`pandas`-class libraries for returns/volatility/correlation math) and it is a language every downstream role (`quant_analyst`, engineer) can review fixtures in without a second toolchain. Static typing is proposed as non-negotiable *practice*, not just a library, because P1's boundary partly rests on the AI module's dependency graph being lint-checkable (§4). |
| Web client | **[J]** TypeScript + a component-based SPA framework (framework choice itself left open — logged, §8) | Matches the designer's four-depth-level, eleven-surface information architecture (`specs/FEATURE_PRD.md` §3.1) more naturally with a component model than server-rendered templates; TypeScript for the same static-typing reasoning as the backend, particularly to keep `MetricResult`'s state field from being silently coerced to a number in UI code (P5). |
| Primary persistence | **[J] proposed, not decided:** PostgreSQL (or equivalent relational engine with strong transactional/ACID guarantees) | The ledger (§9) is the one dataset in this product that must never lose an event and must support point-in-time reconstruction (P12) — an append-only, foreign-key-constrained relational schema is the conservative choice for correctness over a NoSQL store's eventual-consistency tradeoffs. At ~500 holdings/portfolio (NFR-007) and V1's data volumes, a relational engine is not a scale risk. |
| Time-series price/FX storage | **[J] logged as open, not decided (§8)** — proposed default: same relational store, with `(instrument_id, as_of_date)`-keyed tables and appropriate indexing; a dedicated time-series database is a V1.5 optimization if profiling shows a need | No load data exists yet (no vendor access — OQ-04, no network egress in this workspace) to justify the added operational surface of a specialized store before there is evidence it's needed. |
| Methodology registry storage | **[J]** Versioned rows in the relational store, validated against the JSON Schema `implement` will deliver under `schemas/` (§33's fifteen fields), with immutable-once-published version records | Matches §33's "store/version" requirement and T6's need for a stable version identifier every calculation can cite. |
| AI Orchestration runtime | **[J]** A separate deployable process (even at V1 scale) — language-agnostic to this proposal but naturally the same backend language for shared type contracts. **[SUPERSEDED FOR V1, 2026-09-22, by `PD-0020` — see §13.B. Kept as proposal history, not the active decision.]** | See §4 — this is a structural requirement of the P1 boundary, not a convenience choice. **[Superseded premise: §13.B shows the P1 boundary's decisive mechanism (Control 3, provenance-bound rendering) does not in fact depend on process separation; only Control 1's isolation strength does.]** |
| Job/queue infrastructure | **[J] explicitly deferred, not silently dropped** | V1 has no live market-data ingestion pipeline (holdings are manual/CSV-imported per FR-005–FR-007); nothing in CP0–CP11 as scoped requires asynchronous background processing. If CP2's vendor adapters need scheduled refresh later, this is revisited then — flagged in §8 as an open item so it is not mistaken for an oversight. |

**[A]** I assume no existing codebase, schema, or vendor contract constrains this
choice (`specs/FEATURE_PRD.md` A-04) — `src/` does not exist in this workspace.

**[J] Unresolved-verification note:** I did not, and could not, execute any dependency
install, package fetch, or toolchain probe — this workspace has no network egress and
the shell cannot mutate the filesystem outside granted write paths (`CLAUDE.md`, §7 of
the increment PRD). Every stack choice above is a reasoned proposal, not a verified
build. Recorded as **not run**, not as a passing check.

---

## 3. T3 — Initial domain model

### 3.1 Entities and relationships

**[F]** This must preserve identity layering across exchange/issuer/currency/listing
(§10, rule §44.10) and must not conflate listing geography with economic exposure
(§10.4, rule §44.12). Proposed core entities (fields abbreviated; full field lists are
CP1 work, not CP0):

- **User** — owns one or more Portfolios.
- **Portfolio** — one reporting currency (§8.1, FR-001); owns Accounts and a
  reporting-currency policy.
- **Account** — a manual brokerage/account container (§7.3, FR-004); scopes Ledger
  Events.
- **LedgerEvent** — append-only, event-sourced (§9.7, P12); typed per the minimum
  transaction taxonomy (§9.5); references an Account and, where applicable, a Listing.
- **Position** — *derived*, never directly written; produced by the Position Engine
  from LedgerEvents as of a given date (§9, FR-013).
- **Issuer** — economic entity (e.g. "Alibaba"); owns one or more Listings (§10.3).
- **Listing** — a specific exchange listing of an Issuer (e.g. BABA/NYSE, 9988/HKEX);
  carries FIGI + MIC as canonical identity primitives (§10.1), ticker (search
  attribute, not primary key), exchange, trading currency, security type, status.
- **EconomicGeography** — a set of fields attached to Issuer/Listing, kept *structurally
  distinct* from Listing's own `listing_country`: `issuer_domicile`,
  `revenue_geography` (may be `INSUFFICIENT_DATA` in V1 per §10.4 — "may be incomplete
  in V1, but the schema must support it"), `trading_currency`. **[J]** This is the
  concrete structural answer to §44.12: `listing_country` and `revenue_geography` are
  different columns on different conceptual axes, never one field with two meanings,
  so no downstream query can accidentally read one as the other.
- **CashBalance** — per-currency cash position, first-class alongside securities (§9.4).
- **SecurityPrice / FXRate / CorporateAction / BenchmarkSeries** — normalized market-data
  contracts owned by the Market Data Layer (§11.1); see T5.
- **BenchmarkSelection** — user-selected primary benchmark per Portfolio, required
  explicit selection (§13.1, FR-017); never defaulted silently.
- **PortfolioPolicy** — optional user-defined constraints/objectives (§25, FR-031, P7);
  absent unless the user sets it.
- **MethodologyRegistryEntry** — versioned metric definition (§33); referenced by ID +
  version from every MetricResult.
- **MetricResult** — the envelope every computed number travels in: a value (nullable
  only for `INSUFFICIENT_DATA` — see below), a state (§32 — shape settled by
  `decisions/product/PD-0006-...md`: `sufficiency_state` + nullable `reason_code`, per
  its second amendment; OQ-01 is closed, see §9 below), a `methodology_ref` (registry
  ID + version), and the T6 computation-context reference. **[Corrected 2026-09-05,
  closing `reviews/TECH_REVIEW.md` round-4 B-6 — the statement below was the sole
  remaining instance of AC-15's superseded, pre-`decisions/product/PD-0007` wording
  anywhere in `specs/`, `implementation/`, `designs/`, `decisions/`, `reviews/gates/`,
  or `src/`.]** ~~A MetricResult cannot carry both a non-`AVAILABLE` state and a
  presentable value~~ — **`value is None` if and only if `sufficiency_state is
  INSUFFICIENT_DATA`; `AVAILABLE` and `LIMITED` both require a value** (PD-0007 and
  its 2026-09-04 amendment, which corrected AC-15 itself after the design's §D3.2 was
  found to specify rendering for states the original wording could not construct) —
  this is I2's job in `implement`, and matches `src/product_contract/metric_state.py`
  exactly; the *type* is declared here as a CP0 domain-model decision so `implement`
  has a contract to build against.
- **ScenarioState** — a hypothetical Portfolio snapshot; references a base Portfolio
  snapshot for comparison but is never reachable from Portfolio's own write path (P8).
- **Insight** — Fact/Interpretation/Preference-dependent taxonomy (§20.2), with a
  severity (Observation/Attention/Warning, §20.1) and a required comparison basis
  reference (P4).
- **ProofPacket** — machine-readable evidence attached to an Insight or AI claim (§21,
  FR-024): pointers to the MetricResults, methodology versions, and timestamps behind
  the claim (P9).

### 3.2 Relationship summary

```
User 1--* Portfolio 1--* Account 1--* LedgerEvent
Portfolio 1--1 ReportingCurrencyPolicy
Issuer 1--* Listing
Listing 1--* SecurityPrice, CorporateAction
LedgerEvent *--1 Listing (where applicable)
Position = f(LedgerEvent[], SecurityPrice[], FXRate[], CorporateAction[], as_of_date)  [derived, not stored as a source of truth]
Portfolio 1--1 BenchmarkSelection --1 BenchmarkSeries
Portfolio 0--1 PortfolioPolicy
MetricResult *--1 MethodologyRegistryEntry
Insight *--* MetricResult (comparison basis)
ProofPacket 1--1 Insight or AI claim; *--* MetricResult, MethodologyRegistryEntry
ScenarioState --1 Portfolio (base snapshot, read-only reference)
```

### 3.3 Why this satisfies §44.10 / §44.12 structurally

- Identity is layered as **Issuer → Listing → (FIGI+MIC canonical key)**, never
  collapsed to a single "symbol" field — satisfies §44.10.
- Economic geography fields live on a distinct entity/field group from listing
  geography, and revenue-geography is permitted to independently carry
  `INSUFFICIENT_DATA` without blocking listing-level display — satisfies §44.12 and
  §10.4's "schema must support it" requirement even though V1 population is incomplete.

---

## 4. T4 — The P1 boundary made structural

> **Reworked 2026-09-04 by `engineer-02`, following `reviews/TECH_REVIEW.md` B-1
> (`review-01`, HOLD).** The original §4 below claimed three controls "stacked" against
> P1 and was wrong: against the failure mode P1 and §41.4 actually name — the AI
> *originating* a number, including by doing arithmetic on values it was legitimately
> given — only one of the four named controls was ever live, and that one's central
> term ("material") was undefined. `review-01`'s worked example (two legitimate tool
> calls returning `0.0840` and `0.0610`; the AI writes "you beat your benchmark by 2.3
> percentage points") is reproduced below because the rework has to survive it, not
> just cite it. This section keeps the honest catch of each original control, adds one
> new control aimed at the failure mode the old stack missed, gives a decidable
> definition of "material," resolves the network-destination contradiction with §8.2,
> and states plainly what is still not solved. AC-10's bar — "a reviewer must be able
> to describe how a violation would fail" — is the test applied throughout.

### 4.0 The failure mode, restated precisely

P1 is violated when a **number reaches the user that the deterministic engine did not
compute and return as a `MetricResult`.** That has (at least) three distinct routes,
and a mechanism that only closes one of them is not a P1 boundary, it is a boundary
against one route:

1. **Direct access** — the AI process reads a data store or calls something other than
   the Tool Gateway. (Old Control 1's actual target.)
2. **Derived arithmetic** — the AI process receives legitimate `MetricResult`s and
   computes a new number from them (a spread, a ratio, a rounding, a sum) that no
   `MetricResult` carries. (`review-01`'s worked example. Nothing in the original §4
   caught this.)
3. **Fabrication** — the AI process states a number with no computation behind it at
   all (hallucination). (Overlaps route 2's detection surface but has no "legitimate
   inputs" to point to.)

### 4.1 Control 1 — Credential/data-store isolation (catches route 1 only; renamed and
rescoped, not removed)

AI Orchestration is proposed as a **separate runtime process** (§1.4) with its own
service identity that holds **no database credential** of any kind, to any store — not
read-only, not scoped. It cannot query the ledger, prices, or analytics tables even if
its code tried to.

**How a violation fails:** if AI-layer code (or a compromised prompt-injected
instruction) attempts to open a database connection, the attempt fails at the
credential layer before it reaches data — an authentication failure, not a bad answer.

**What this control does NOT catch, stated honestly (per B-1):** route 2 and route 3.
`review-01`'s worked example touches no database and calls nothing outside the Tool
Gateway; Control 1 never engages. This section previously described Control 1 as
reaching "exactly one network destination," which §4.1a below corrects.

### 4.1a Network destinations, corrected (resolves B-1b against §8.2)

**[F] Corrected claim.** AI Orchestration reaches **two** network destinations, not
one, and the original claim was false the moment §8.2 leaves the LLM provider
undecided: the Tool Gateway, and — if CP9 uses a hosted model, which §8.2 has not yet
ruled out — the **LLM provider API**. Asserting "exactly one" while leaving the second
open was the plan contradicting itself, and `review-01` was right to flag it.

**[J] The corrected structural claim** is not "only one destination exists" but "only
one destination can be a *source of financial facts*, and the design does not depend on
the second destination being incapable of carrying untrusted text either direction":

- **Tool Gateway** — the only destination that can return a `MetricResult` or any
  other portfolio-derived value. Bidirectional, trusted, schema-validated (Control 2).
- **LLM provider** (if hosted; open per §8.2) — can receive prompt text (including
  already-fetched tool results, which is an §41.1/§41.2-relevant data-handling fact in
  its own right and belongs in that risk log, not manufactured here) and returns
  **draft response text**. This channel is untrusted in both directions: a compromised
  or merely fluent model can put a fabricated or derived number in its completion.
  Control 1 makes no claim about this channel at all — it was never the right control
  for it.

The honest fix is not to shrink the AI process to one destination (CP9 cannot function
without reaching a model unless the model runs in-process, which is a CP9 stack
decision, not a CP0 one) — it is to stop asking Control 1 to guard a channel it cannot
see into, and to put the actual guard on what the *response* is allowed to contain,
regardless of which network path produced the draft. That is Control 3, reworked below.
This also means **the P1 boundary's soundness cannot depend on which LLM provider CP9
picks** — §8.2's row asserting "no bearing on the T4 structural boundary" is corrected
in §8.2 below to say why that is true *for the reworked Control 3* and was not true for
the original Control 1 framing.

### 4.2 Control 2 — Typed contract requiring a state (a P5 control, not a P1 control —
corrected per B-1)

Every Tool Gateway response is a `MetricResult`-shaped, schema-validated object that
**requires** a `state` field (§32) alongside any value.

**How a violation fails:** a Tool Gateway response missing a `state` field fails schema
validation server-side before the AI process ever sees it.

**What this actually is, stated without the earlier overclaim:** this constrains what
the AI process *receives*, not what it *emits*. It guarantees the AI never receives an
ungoverned bare number from the Tool Gateway — that is a real guarantee, and it is P5's
guarantee ("no metric without sufficient data" travels intact into the AI layer), not
P1's. `review-01`'s B-1 finding is correct: presenting it as one of the P1 stack was a
mislabel. It remains in this plan because it is still required (AC-15's envelope has to
reach the AI layer intact for Control 3 below to have anything to cite), just not
counted toward P1's control count anymore.

### 4.3 Control 3 — Provenance-bound rendering (replaces the old "output-time grounding
check"; this is the control aimed at routes 2 and 3)

**[J]** The old Control 3 scanned already-generated free text for numbers and asked
whether each one was "material" — a term this plan left undefined, which is exactly why
`review-01` could show it fails in three directions at once (B-1a). The rework does not
patch that definition; it removes the need for the definition by changing *what the AI
process is allowed to emit* in the first place.

**Mechanism.** AI Orchestration never emits final user-facing text directly. It emits a
**response template**: ordinary natural-language text plus zero or more **value-slot
tokens**, each of the form `{{slot: tool_call_id, field_path}}` — **[Corrected
2026-09-05, closing `reviews/TECH_REVIEW.md` round-3 N-13: the slot carries no
AI-authored `label_ref`. See §4.3b for why.]** — where `tool_call_id` must name an
actual Tool Gateway call already made and logged in the audit trail (§22.8) for the
current session, and `field_path` must name an actual field on that call's returned
`MetricResult` (or other Tool Gateway response object). A separate, deterministic
**Rendering Service** (§1.1 item 5, §1.2, §1.3, §1.4) — not the LLM, cannot run
arbitrary code, a drawn module boundary on the trusted side, not the AI process — is
the only thing that turns a template into displayed text, and is the only path from AI
Orchestration to the client (§1.2):

- For each `{{slot: ...}}` token, the Rendering Service looks up the cited call in the
  session's audit trail, copies the field's value **verbatim** (formatted by a
  deterministic formatter keyed to the field's declared display type — e.g. a return
  field always renders via the same percentage formatter used everywhere else in the
  product), and substitutes it. The LLM never writes the digits that reach the user for
  any cited value; it writes a citation, and formatting happens on the trusted side.
  It also renders the value's *label* — entirely from the cited call's own
  `methodology_ref` (§3.1's `MetricResult` field) and the call's own pinned parameters,
  never from an AI-supplied name — see §4.3b.
- The Rendering Service then scans the **surrounding free text** (everything not
  inside a resolved slot) against §4.3a's **allowlist** — not the blocklist round 1's
  rework used — and if any part of the free text fails the allowlist, the render is
  rejected outright: logged as a grounding violation, response blocked, same failure
  signature as Control 2's schema rejection (a hard error at render time, not a
  judgment call).

**How a violation fails, against all three routes:**
- **Route 1 (direct access):** unchanged from Control 1 — connection/credential
  failure before data is reached.
- **Route 2 (derived arithmetic) — the case Control 3 previously missed entirely, and
  the case the blocklist version of §4.3a (below, superseded) still missed for bare
  integers and spelled-out units.** `review-01`'s worked example: the AI cannot write
  `2.3` as free text (it has no `tool_call_id`/`field_path` that produced `2.3` — no
  `MetricResult` field holds it), and if it writes `2.3`, `8 percent`, or "eight percent"
  as free text anyway, §4.3a's allowlist scan catches all three and the render is
  rejected. If the AI instead wants to *make the comparison*, the structural answer is
  that it must call `compare_benchmark()` — already in the fixed §22.2 function list —
  which computes the excess-return figure **in the deterministic Analytics Engine** and
  returns it as its own `MetricResult` with its own citable field. The arithmetic still
  happens; it happens on the correct side of the P1 line, because that is now the only
  side capable of producing a citable value.
- **Route 3 (fabrication):** a fabricated number has no `tool_call_id` to cite (the
  audit trail only contains calls that actually happened), so it is free text and is
  caught by the same allowlist scan as route 2.

### 4.3a A decidable definition of "material" — **allowlist polarity**
**[Revised 2026-09-04, closing `reviews/TECH_REVIEW.md` B-4; supersedes the blocklist
version below, kept struck-through for the record per this document's own practice of
not silently editing out a wrong decision]**

> ~~**[J]** "Material numeric claim" is replaced by a definition with no judgment call
> at render time: a **value-shaped token** is any substring of the free (non-slot) text
> matching at least one of: a decimal number (`-?\d+\.\d+`); a percentage (a number,
> decimal or integer, immediately followed by `%`); a currency amount (a number
> preceded by a currency symbol or followed by an ISO currency code); a comma-grouped
> integer of four or more digits (`\d{1,3}(,\d{3})+`). Deliberately not value-shaped,
> and therefore not blocked as free text: a bare integer with none of the above
> markers.~~ **Retracted.** `review-01`'s B-4: this is a **blocklist of number
> shapes**, so anything not enumerated passes by default — a bare integer ("8", "6",
> "2") or a spelled-out number word ("eight", "two") carries no marker in this list and
> sails through. The worked failure, verbatim: *"You're up about **8 percent** versus
> **6 percent** for the benchmark — you beat it by roughly **2 percentage points**."*
> No decimal point, no `%` glyph, no currency symbol, no comma grouping — every digit
> is bare, so the blocklist accepts the sentence and an AI-originated derived number
> reaches the user. `review-01` also showed the blocklist's own residual reasoning
> (§4.5 item 2, "a written-out number reads as anomalous prose") is false for "2
> percentage points," which uses digits, not spelled words, and reads as completely
> ordinary prose. **A blocklist fails open by construction; this control needs to fail
> closed.**

**The corrected rule: an allowlist.** Free text (everything outside a resolved
`{{slot: ...}}` token) may contain **no digit character and no member of a closed
number-word vocabulary**, full stop, **unless** the surrounding text matches one of
four enumerated **non-claim forms** below. Anything containing a digit or a number-word
that does not match one of the four is rejected — logged as a grounding violation, same
hard-error signature as before. There is no default-permit case; every digit and every
number-word is guilty until an enumerated form clears it.

**The closed number-word vocabulary** (finite, therefore decidable, if long): the
English cardinal number words zero through twenty; the tens (twenty, thirty, …,
ninety) and their hyphenated compounds; the scale words hundred, thousand, million,
billion, trillion, **dozen** (added 2026-09-05, R-12 — see below); ordinal words first
through twelfth (spelled, as opposed to the digit-plus-suffix forms handled by the
ordinal/count non-claim form below); the fraction words half, third, quarter; and
**fused multiplier/quantity words, added 2026-09-05 (R-12):** `twice`, `double`,
`doubled`, `triple`, `tripled`, `quadruple`, `quadrupled`, `halve`, `halved`, and the
`-fold` compounds `twofold`, `threefold`, `fourfold`, `fivefold`, `tenfold`.

**Corrected reasoning for why unit/quantity words (percent, percentage, basis
point(s)/bp(s), dollar(s), cent(s), yuan, renminbi, RMB, USD/HKD/CNY, times, ratio, "x"
as a multiplier) are still not separately listed — narrowed 2026-09-05 per
`reviews/TECH_REVIEW.md` round-3 N-15, which found the prior version of this paragraph
gave a false reason.** ~~No unit or quantity word needs listing because the number
next to it would be caught.~~ **That premise holds only where the quantity is
expressed as a separate number token next to a unit word** — "8 percent," "2
percentage points" are both caught this way, correctly, because "8" and "2" are
themselves listed or digit-form tokens. **It is false for *fused* number-unit words,
where there is no separate number to catch:** "your HK exposure is **twice** your US
exposure," "your tech sleeve **doubled** this year," "you hold a **dozen** technology
positions." Each states a quantity claim with no digit and no separately-catchable
number word. `review-01` is explicit that these are core English, not the "regional
variant" this paragraph previously blamed — that blame was the misdiagnosis, corrected
here rather than repeated. This document now lists the fused forms it can enumerate
(above); it does not claim the list is exhaustive, and that residual is corrected in
§4.5 to name the real cause rather than a wrong one.

**Matching is whole-token, not substring — specified explicitly, closing a gap
`review-01` found undecided in round 3.** The number-word vocabulary above is checked
against whole, word-boundary-anchored tokens in the free text, never as a substring
search. Substring matching is untenable ("one" occurs inside "money," "component,"
"zone"); whole-token matching is what every example in this section assumes. **Disclosed
cost of this choice, not hidden:** whole-token matching lets a fused compound through
if it is not itself a listed token — "twofold," "tenfold," "half-yearly" are not equal
to any single vocabulary word even though they are built from one. §4.3a's fused-word
additions below close the ones this document can enumerate; the general shape of the
gap is logged in §4.5, corrected to name it accurately (R-12).

**The four non-claim forms — each with its recognition rule, decidable with no judgment
call, and each corrected 2026-09-05 per `reviews/TECH_REVIEW.md` round-3 (R-10) and
`decisions/product/PD-0008-...md` (R-11) after `review-01` broke three of the four by
hand:**

1. **Ticker/listing fragments — corrected, adjacency guard added.** ~~A digit run with
   no intervening whitespace against a fixed exchange-suffix pattern: immediately
   followed by `.HK`, `.SS`, `.SZ`, `.US`, or 1–4 uppercase letters with no separating
   space.~~ **Retracted: the "or 1–4 uppercase letters with no separating space"
   branch was the leak.** `review-01` showed it also exempts `250BP`, `12M`, `3X`,
   `8K` — fused number-unit shorthand arriving through the door this form left open,
   the same blind spot named in R-12 but reachable here without even a word list, and
   asymmetric with Form 2 below, which already had a guard. **Corrected rule:** a digit
   run immediately followed by a **literal period** and then one of a fixed,
   enumerated exchange-suffix list — `HK`, `SS`, `SZ`, `US` (extendable only by adding
   a named entry, reviewable line-by-line, never by widening the letter class) — e.g.
   `9988.HK`, `601398.SS`. A digit run followed by letters with **no period** is no
   longer exempted by this form at all — `250BP`, `12M`, `3X`, `8K` all fail it now,
   as does a genuine dotless ticker shape if this product ever uses one (logged as a
   narrowing, not a loss: no example in this document ever required a dotless form).
   `BABA` contains no digit and needs no rule.
2. **Calendar years — corrected, calendar-context guard added.** ~~A bare 4-digit
   integer in the range 1900–2099, with no digit immediately adjacent on either side,
   and not immediately preceded or followed by a currency symbol, `%`, or a
   number-word.~~ **Retracted: the guard excluded value-shaped neighbors but not a
   bare figure that is itself a market value.** `review-01`: "the Hang Seng closed at
   **1950**" and "your position is worth **1975**" both clear the old guard — an
   index level and a security value, market facts the deterministic side owns, sitting
   in the same numeric range as a year. **Corrected rule:** everything the old guard
   required, **plus** the 4-digit integer must be immediately preceded (allowing at
   most one intervening article, e.g. "the") by a fixed calendar-context marker:
   `in`, `since`, `by`, `as of`, `through`, `during`, `before`, `after`, `until`,
   `year`, `FY`, `fiscal year`, `vs.` (case-insensitive). "in 2026," "since 2020,"
   "FY2026" clear it. "closed at 1950" and "worth 1975" do not — "at" and "worth" are
   not calendar-context markers — and are rejected, which is the correct outcome for
   both. **Disclosed residual:** a sentence that happens to combine a calendar marker
   with a value coincidentally (e.g. "since 1975 shares are worth more") is not
   examined by this document beyond noting the risk exists; it is a narrow overlap
   case, not the ordinary shape of either a date or a value claim.
3. **Ordinal/count phrases — split per PD-0008, not merely corrected.** ~~A bare
   integer immediately preceded by "top"/"bottom"/"first"/"last", or immediately
   followed by one of `holdings`, `positions`, `accounts`, `listings`, `currencies`,
   `markets`.~~ **Retracted: the "immediately followed by a structural noun" branch
   was not a grammar oversight but a product-contract question decided the wrong way
   by default.** `review-01`'s N-16, routed to and ruled on by the product owner in
   `decisions/product/PD-0008-the-ai-may-not-free-type-portfolio-counts.md`: the old
   rule's six nouns are all portfolio nouns, so it exempted "you hold **7 positions**,"
   "**5 accounts**," "**12 holdings**" — counts of the user's own data, which P1
   reserves to the deterministic engine regardless of whether the AI arrived at the
   number by counting or by arithmetic. PD-0008's test: *does the number assert
   something about the portfolio that could be false?* A selector asserts nothing; a
   count does. **Corrected rule:** a bare integer is exempt under this form **only**
   when immediately preceded by one of `top`, `bottom`, `first`, `last`
   (case-insensitive) — "top 3 holdings," "bottom 5 performers." The digit here is a
   *selection parameter*: it says which slice of an answer to discuss, not what the
   answer is, and remains true regardless of how many holdings, positions, or accounts
   actually exist. **The "bare integer immediately followed by a structural noun,
   with no selector word" case is no longer exempt under any form.** "You hold 7
   positions," "5 accounts," "12 holdings," "3 currencies" must now be delivered
   through a slot citing an actual Tool Gateway count field — the same treatment as
   any other portfolio fact.
4. **Tenor/window descriptors, unbound to any slot — unchanged; `review-01` could not
   make this one leak.** A bare integer immediately followed by a hyphen and one of
   `year(s)`, `month(s)`, `week(s)`, `day(s)`, `quarter(s)` (e.g. "5-year window",
   "3-month lookback") **when that phrase is not immediately adjacent to a resolved
   slot.** Where a tenor phrase sits immediately next to a slot (e.g. "Your 3-year
   {{slot: ...}}"), §4.3b's label-binding governs instead and the free-text tenor
   claim for *that specific slot* is not independently trusted — this is exactly
   `review-01`'s N-10 finding (§4.3b below), and this exemption is scoped to avoid
   re-opening it. `review-01` confirmed "a quarter of your portfolio" correctly fails
   this form (a fraction word, not an integer-hyphen shape) and is rejected as a
   number-word claim, which is the rule working as intended.

**This closes `review-01`'s exact B-4 sentence, and the round-3 leaks in forms 1–3 are
closed against the exact strings `review-01` used to find them.** "8", "6", "2" (digit
form) or "eight", "six", "two" (word form): none is a ticker fragment, none clears the
year guard, none is preceded by a selector word, none is followed by a tenor
hyphen-word. `250BP`, `12M`, `3X`, `8K` fail the corrected Form 1 (no period). "closed
at 1950" and "worth 1975" fail the corrected Form 2 (no calendar marker). "you hold 7
positions" and "5 accounts" fail the corrected Form 3 (no selector word). All are
rejected, closing the exact evasions found by hand in round 3 in addition to the round-2
worked sentence.

**Re-verifying B-1a's three original cases still hold under the allowlist (they do,
and for a cleaner reason than before):**
1. **Reformatting:** still does not arise — the AI never free-types a cited number at
   all; the Rendering Service formats it. No equivalence matching, so no rule to loosen.
2. **Non-claims ("9988.HK", "2026", "top 3 holdings"):** each clears one of the four
   forms by name, explicitly, above — no longer merely "not on a blocklist" but
   "affirmatively matches an enumerated exemption," which is the stronger and correct
   framing for an allowlist.
3. **Cross-turn citation:** unchanged from the prior revision — session-scoped audit
   trail, not request-scoped.

**False rejections still push the correct direction, now more forcefully.** An
allowlist is *more* prone to false rejections than the retracted blocklist (e.g., "top
three holdings" spelled out, above) — and that is the point: every false rejection
under this design means legitimate prose was blocked, and the only way to unblock it is
to either rephrase with an enumerated form or add a Tool Gateway field/slot, never to
loosen what counts as a claim. The failure mode this design cannot produce is the one
`review-01` warned about for the blocklist: there is no dial that, turned to reduce
false rejections, also lets a real financial figure through, because reducing false
rejections here means *adding to the enumerated non-claim list*, which is reviewable
line-by-line at HG1/CP9, not a numeric-tolerance parameter tuned at runtime.

**Disclosed limitation of the allowlist itself, stated rather than hidden, and
corrected 2026-09-05 (R-12, N-15) to name the true cause:** the number-word vocabulary
above is large but finite. The gap is not, as an earlier version of this section
argued, "a regional English variant or a compound this plan did not anticipate" — that
was a misdiagnosis `review-01` corrected. The real cause is **fused number-unit
words**, where a quantity is stated with no separate, independently-catchable number
token (`twice`, `doubled`, `tripled`, `dozen`, and the `-fold` family) — core,
everyday English, not an edge case. This document now enumerates the fused forms it
can (above); a fused form not on that list would still evade the scan. Also disclosed
here: whole-token matching (specified above) means a fused compound built from a
listed word but not itself listed — "twofold" is listed, but a novel coinage like
"umptyfold" would not be — still evades. Both are completeness risks in an enumerable,
closed vocabulary — qualitatively different from the retracted blocklist's polarity
defect (every digit-bearing expression still fails closed by default), and closable by
extending a list rather than redesigning a mechanism, but not claimed to be
exhaustively enumerated in this document. Flagged in §4.5 with the correct diagnosis.

### 4.3b Label-bound citations — closes `review-01`'s N-10; **corrected 2026-09-05 to
resolve N-13 (§1.3 and this section previously specified two different mechanisms)**

**[J]** Provenance-bound rendering (§4.3) binds a **value** to its source but, as
originally specified, left the **label** — what the value is claimed to be a measure
of — as free AI prose. `review-01`'s N-10 finding: a response can be entirely
grounded and still false. Worked example: AI Orchestration calls `calculate_risk()`
twice, once for a 1-year window and once for 3-year, then emits `"Your **3-year** beta
is {{slot: call_7, value}}"` where `call_7` is the *1-year* call. Every digit is
verbatim from a logged tool call; no numeric token sits in free text; §4.3a's scan (in
either polarity) has nothing to catch, because the defect is not in the number — it is
in which number the sentence claims to be.

**N-13, stated so the correction is checkable: the first version of this section
contradicted §1.3.** §1.3's boundary row states the label is rendered "from the cited
call's `MethodologyRegistryEntry`" — a trusted derivation the AI cannot influence. This
section's first version instead had the slot carry an AI-authored `label_ref`
component naming *which* registry entry to render the label from — meaning the AI
still chose metric identity, even though the window became trusted. `review-01`'s
failure scenario: cite a real, logged call whose `field_path` returns a beta value,
but set `label_ref` to the Sharpe Ratio entry; the display reads "Sharpe Ratio
(1-year)" over a beta value, fully grounded by §4.3a's scan (no free-text number
exists to catch) and still false. **§1.3's reading is the one this plan intends, and
this section is corrected to match it, not the other way round** — the fix costs
nothing new: §3.1 already declares `MetricResult.methodology_ref` (registry ID +
version) as a field every Tool Gateway response carries, populated by the Analytics
Engine at computation time, never by AI Orchestration.

**Mechanism, corrected.** The slot token carries no `label_ref` and no other
AI-authored identity component (§4.3's definition above is corrected to match: back to
`{{slot: tool_call_id, field_path}}`, two components). When the Rendering Service
resolves a slot, it reads the cited call's own `methodology_ref` — a field on the
`MetricResult` the Tool Gateway actually returned, populated deterministically, never
supplied by the template — looks up that registry entry's `metric_name`, and reads the
same call's own pinned window/tenor/benchmark parameters from its Computation Manifest
(§6.2). The Rendering Service renders the **label text itself** — "1-Year Beta," not
"3-Year Beta," for a call whose own Computation Manifest pins a 1-year window — **from
data that already exists on the cited call, never from anything the AI wrote or
chose.** The AI's role is reduced to sequencing which already-computed, already-labeled
fact to present and supplying connective prose that makes no claim about *what* the
figure measures. Free text that names a tenor, benchmark, or metric term contradicting
the adjacent slot's own `methodology_ref`/Computation Manifest metadata is rejected by
the same direct string-comparison this section specified before — the comparison target
changed (the cited call's own trusted metadata, not an AI-authored reference), the
mechanism did not.

**Does this close N-10, and does it also close N-13?** For the exact N-10 worked
example, yes, as before: the label "1-Year Beta" is derived from `call_7`'s own pinned
window, so the AI cannot cause the display to say "3-year" for a 1-year value. **N-13
is closed because the AI no longer chooses which registry entry backs a label at
all** — there is no `label_ref` for it to set to the wrong entry; the entry is read off
the same `MetricResult` the value itself came from, so a mismatched-metric-identity
render (Sharpe label over a beta value) is no longer constructible through this
mechanism, because the label and the value are now sourced from the identical trusted
object rather than from two independently-suppliable references. **Not claimed to be
closed for every composition:** a claim that combines two *different, both-legitimately
cited* slots with a connecting word that mischaracterizes their relationship (e.g.
"your beta *relative to* the Hang Seng" citing a value actually computed relative to
the S&P 500) is a benchmark-identity instance of the same family and is caught by this
mechanism only if benchmark identity is part of the cited call's pinned Computation
Manifest metadata (it should be — `compare_benchmark()`'s Computation Manifest already
carries `benchmark_series_ref`, §6.2) and only if the Rendering Service's
string-comparison extends to benchmark names, which this document requires but does
not claim to have verified against every §22.2 function's parameter shape. That
residual is logged in §4.5, not hidden.

### 4.4 Control 4 — Import-boundary lint (unchanged; honest scope)

**[J]** A CI-enforced import-boundary lint rule: the `ai_orchestration` package may not
import anything from `analytics_engine`, `portfolio_service`, `market_data`, or any
database driver package. **Stated honestly:** this catches an *accidental* future
violation of route 1 at build time (a developer imports something they should not have
been able to). It has no bearing on routes 2 or 3, was never claimed to, and is not
part of the count that answers B-1 — it is defense-in-depth for Control 1's route only.

### 4.5 What this rework does not solve — logged for HG1, not papered over

**[J]** Per the brief: an honest "not yet solved" is worth more than a control that
reads as sufficient and is not. **Revised again 2026-09-05** following
`reviews/TECH_REVIEW.md` round 3 (§14.4's N-13/N-15/N-16) and
`decisions/product/PD-0007`/`PD-0008`. Round 3's CLEAR TO GATE verdict noted this list
disclosed only one of five live residuals at the time and said explicitly: "either
§4.5 gains the other four or the package cites §14.4." This revision gains them —
three of the four are now **closed** by the corrections in §4.3a/§4.3b above rather
than merely disclosed, and the list below reflects the current state, not round 3's.

1. **Qualitative mischaracterization without a number.** "You significantly
   outperformed" attached to a citable, correctly-grounded, but small or negative
   figure is not caught by anything above — there is no numeric token or number-word to
   scan and no slot to misuse. P1's text is about the AI not *computing a number it
   presents*; a qualitative claim is a different failure (closer to an
   interpretation-accuracy problem than an origination problem, and arguably `Insight
   Engine` territory — the AI should be quoting an already-computed Insight severity,
   not inventing its own characterization — but T4 as scoped does not build that
   check). **Open question for HG1**, unchanged across all three rounds. The one
   residual this document has never claimed to address.
2. **The number-word vocabulary is finite and its known gap is fused number-unit
   words — corrected 2026-09-05 to name the true cause (R-12, N-15).** §4.3a's
   allowlist closes `review-01`'s round-2 sentence in both digit and spelled-word form,
   and closes the three round-3 exemption leaks (forms 1–3) explicitly (item 4 below).
   What remains open: the vocabulary is large but finite, and its real gap — stated
   correctly this time, not attributed to "regional English variants," which was a
   misdiagnosis this document made and `review-01` corrected — is **fused
   number-unit words**, quantities stated with no separate, independently-catchable
   number token: `twice`, `doubled`, `tripled`, `dozen`, and the `-fold` family. §4.3a
   now enumerates the fused forms this document can (added 2026-09-05); it does not
   claim that list is exhaustive, and whole-token matching (specified in §4.3a) means
   an unlisted coinage built from a listed word (e.g. a novel `-fold` compound) would
   still evade the scan. Closable by extending an enumerated list, reviewable
   line-by-line at CP9 — not an open-ended semantic gap.
3. **Label-bound citations, §4.3b — closed for the worked example and for N-13; one
   compound-claim case remains open.** `review-01`'s N-10 (a true value rendered under
   a false label) is closed: §4.3b now derives a slot's label entirely from the cited
   call's own `methodology_ref` and Computation Manifest, never from anything the AI
   supplies. `review-01`'s N-13 (§4.3b and §1.3 specified two different mechanisms) is
   also closed: the AI-authored `label_ref` component is removed; §1.3's trusted-derivation
   reading is now the only one the document states. **Not claimed closed:** a claim
   relating *two* separately-legitimate slots with a connecting word that
   mischaracterizes their relationship (e.g. "beta *relative to* the Hang Seng" citing
   an S&P 500 comparison) is caught only if benchmark identity is part of the cited
   call's pinned Computation Manifest metadata and the Rendering Service's
   string-comparison extends to benchmark names — both required by this document but
   not verified against every §22.2 function's parameter shape.
4. **The three round-3 exemption leaks — closed, not disclosed.** `review-01` broke
   three of the four non-claim forms by hand: Form 1 (ticker fragments) had no
   adjacency guard and exempted fused shorthand (`250BP`, `12M`, `3X`, `8K`) through a
   generic uppercase-letter class; Form 2 (calendar years) exempted any bare 4-digit
   integer in range, including index levels and prices ("closed at 1950," "worth
   1975"); Form 3 (ordinal/count phrases) exempted counts of the user's own portfolio
   ("you hold 7 positions," "5 accounts") because its six nouns were all portfolio
   nouns — a product decision, not a grammar bug, per `decisions/product/PD-0008`.
   §4.3a now requires a literal period plus a fixed exchange-suffix list for Form 1, a
   calendar-context marker for Form 2, and a preceding selector word
   (top/bottom/first/last) for Form 3, with the bare-noun-adjacency case removed from
   the exemption entirely. Form 4 (tenor descriptors) was attacked and did not leak;
   unchanged.

All four are recorded again in §10 (AC-21) and should be carried to HG1 as open items
alongside ADR-P4's revision, not silently accepted as covered — items 2 and 3 as
residuals, item 4 as a record of what round 3 found and this revision closed, item 1
as the one this document has never had an answer for. **AC-10 self-assessment (§11):**
B-4's exact worked sentence, B-5's missing architecture, and the round-3 form leaks
(N-15 partially, N-16) are closed by the corrections above; N-13 is closed; one
residual (item 1) and one bounded completeness gap (item 2) remain open by design, not
by omission. **This is not self-certified as AC-10 "satisfied"** — that determination
is `technical_review`'s, per `roles/engineer.json`'s limits on declaring my own work
reviewed — but it is reported as genuinely reworked against every specific defect
found across three review rounds, with the two residuals that remain named precisely
enough for the owner to weigh them at HG1.

**[J] Dependency on OQ-01/PD-0006, updated:** Control 2's schema field-shape question is
resolved by `decisions/product/PD-0006-...md` (sufficiency state + reason code); this no
longer depends on OQ-01, which is closed. Control 3's slot mechanism is indifferent to
that field's internal shape either way — it cites whichever fields the `MetricResult`
type exposes.

---

## 5. T5 — Vendor-independence boundary

**[F]** AC-11 requires the five normalized contracts of §11.1 and an explanation of why
a vendor swap does not reach core analytics.

### 5.1 The five contracts (as specified in §11.1, reproduced with the boundary they enforce)

| Contract | Required fields (§11.1) | Boundary it enforces |
|---|---|---|
| **Instrument** | identity and metadata | Analytics never sees a vendor's instrument-master shape |
| **SecurityPrice** | instrument_id, timestamp, price, currency, source, freshness, adjustment status | Freshness (P10) and adjustment/lineage (§11.3) travel with the price, not bolted on later |
| **FXRate** | currency pair, timestamp, rate, source, freshness | Historical FX correctness (NFR-009) is enforceable because every rate is dated and sourced |
| **CorporateAction** | instrument, event type, effective date, ratio/amount, currency, source | Position Engine consumes one shape regardless of which vendor reported a split/dividend |
| **BenchmarkSeries** | benchmark ID, provider, values/returns, currency, source, licensing metadata | §11.4 — licensing is data carried on the contract, not a side-channel the analytics code must separately track |

### 5.2 Why a vendor swap does not reach core analytics

**[J]** The mechanism is a **Port/Adapter pattern**: the Market Data Layer defines a
`MarketDataPort` interface expressed purely in terms of the five normalized contracts
above. A vendor integration is a concrete adapter class implementing that port,
translating vendor-specific payloads into the normalized types. Analytics Engine,
Portfolio Service, and Insight Engine depend **only** on the port's normalized types —
never on an adapter class, a vendor SDK type, or a vendor's field names. Swapping a
vendor means writing (or generating) a new adapter that satisfies the same port;
zero lines change in Analytics, Portfolio, or Insight code, because those layers never
had a compile-time or runtime dependency on the vendor in the first place. This is the
concrete answer to NFR-003 ("substitution must not require rewriting core analytics")
and CP2's exit criterion ("same internal analytics contract can consume test data from
more than one adapter/mock without business-logic change").

**[A]** OQ-04 (which vendors are available for the launch jurisdiction) is unresolved
and does not need resolving for this boundary to be correct — the port is defined
against the contract shape, not against any specific vendor's capabilities. If a
chosen vendor cannot supply a required field (e.g. adjustment status), that surfaces as
a `LIMITED`/`INSUFFICIENT_DATA` state on the resulting MetricResult, not as a schema
change.

---

## 6. T6 — Determinism and reproducibility strategy

**[F]** AC-12 requires the six §34 inputs enumerated and a statement that conventions
live in `methodology/`. Naming *which* day-count/annualization/compounding/FX-fixing
convention applies to a given metric is `quant_analyst`'s authority — this section
specifies the mechanism that makes any such choice reproducible, not the choice itself.

### 6.1 The six versioned inputs (§34, reproduced)

1. portfolio snapshot/ledger version;
2. market-data version/timestamps;
3. FX series (version/timestamps);
4. corporate actions (version);
5. benchmark series (version);
6. methodology version.

### 6.2 Proposed mechanism: an immutable Computation Manifest

**[J]** Every stored MetricResult, Insight, and Proof Packet carries a **Computation
Manifest** — a small, immutable record pinning exactly the six inputs above at the
moment of calculation:

- `ledger_version` — the LedgerEvent sequence position (or content hash) the snapshot
  was built from;
- `market_data_snapshot_ref` — the set of SecurityPrice/FXRate `(source, timestamp)`
  pairs actually consumed;
- `fx_series_ref` — same, scoped to the FXRate series used;
- `corporate_action_set_ref` — the CorporateAction records applied, by ID/version;
- `benchmark_series_ref` — the BenchmarkSeries version compared against;
- `methodology_version` — the exact `MethodologyRegistryEntry` version(s) invoked.

Reproduction is: given the same six references, re-running the same methodology
version against the same pinned data must yield the same output (NFR-001, NFR-010).
This works because every one of the six inputs is itself append-only/immutable-once-
published in the proposed persistence model (§2): LedgerEvents are never edited in
place (corrections are new offsetting events), price/FX/CA/benchmark records are keyed
by `(instrument_id/pair, as_of, source)` and never overwritten, and
MethodologyRegistryEntry versions are immutable once published — a convention change
creates a new version rather than mutating an existing one.

### 6.3 Where conventions live

**[F]** Day-count, annualization, compounding, and FX-fixing conventions are **method**,
not architecture (P12, §34) — they are fields inside a `MethodologyRegistryEntry`
(§33's fifteen required fields already include annualization convention, FX treatment,
etc.), stored under the methodology registry this plan proposes (§1.1, §2). **This
plan does not propose values for any of them** — that is `quant_analyst`'s authority
per the increment brief, and doing so here would be exactly the "invented financial
formula in feature code" that rule §44.4 forbids.

### 6.4 Audit reproduction path

A Proof Packet's evidence trail (P9) is: claim → Computation Manifest → (ledger
snapshot, market-data snapshot, FX snapshot, corporate actions, benchmark series,
methodology version) → re-executable calculation. **[J]** CP1–CP4 own building the
actual re-execution tooling; CP0's obligation is that the manifest shape exists and
that nothing in the proposed architecture requires mutating a historical input to
serve a current read (which would silently break reproducibility).

---

## 7. T7 — Implementation sequence and dependency graph (CP1–CP11, HG gates blocking)

**[F]** AC-14 requires the §38.5 mapping reproduced correctly, including each gate's
actual hard-stop rule (§38.4) — not just which checkpoints it covers.

### 7.1 Gate-to-checkpoint mapping (§38.5, reproduced)

| Human Gate | Technical coverage | Hard-stop rule (§38.4, verbatim effect) |
|---|---|---|
| **HG1** — Product & Architecture | CP0 | CP1 implementation may not begin until HG1 is `APPROVED` or `APPROVED_WITH_CONDITIONS`. |
| **HG2** — Financial Core Proof | CP1–CP3 | CP4–CP9 may not proceed **as production-intended work** until HG2 is approved; limited isolated prototypes only if explicitly requested for evaluation. |
| **HG3** — Professional Analytics Proof | CP4–CP5 | Analytics may not be treated as approved product truth until HG3 is approved. |
| **HG4** — UX Prototype Approval | CP7 | Major UX implementation direction may not be considered final until HG4 is approved. |
| **HG5** — Intelligence, Scenario & AI | CP6 + CP8 + CP9 | AI/intelligence functionality may not be considered product-ready until HG5 is approved. |
| **HG6** — Integrated V1 Acceptance | CP10 | No pre-commercial hardening (CP11) should begin automatically after HG6; requires explicit human approval to continue. |
| **HG7** — Commercial Readiness | CP11 | Deployment to commercial production requires a separate explicit human launch authorization even after `APPROVED`. |

### 7.2 Proposed dependency graph

```
CP0 (this increment) ──HG1 (blocking)──> CP1
CP1 (ledger/domain foundation)
   └─> CP2 (market-data normalization)     [can start once Instrument/Listing model
   │                                        from CP1 is stable; parallelizable with
   │                                        the tail of CP1]
   └─> CP3 (performance engine)  <── depends on CP1 (positions) + CP2 (prices/FX)
                │
      CP1+CP2+CP3 ──HG2 (blocking: CP4-CP9 not production-intended until approved)──>
                │
         ┌──────┴───────┐
       CP4              CP5
   (risk/benchmark)  (diversification/drift)   <- both depend on CP3's return series
         └──────┬───────┘
        CP4+CP5 ──HG3 (blocking: analytics not "approved product truth" until approved)──>
                │
              CP6 (insight engine) <- depends on CP4+CP5 metrics + T6 manifest shape
                │
        ┌───────┼────────────────┐
      CP7                       CP8                 CP9
  (core web UX)          (scenario lab)        (AI analyst)
  depends on CP3-CP6      depends on CP1+CP3+     depends on CP6 (insights to
  (has data to show)      CP4 (recalculation      explain) + T4's Tool Gateway
                           against hypothetical    (already specified at CP0)
                           state)
        │                       │                     │
      CP7 ──HG4 (blocking:    CP6+CP8+CP9 ──HG5 (blocking: AI/intelligence not
      UX direction not          product-ready until approved)──┐
      final until approved)                                     │
        └───────────────────────┴─────────────────────┬─────────┘
                                                        v
                                              CP10 (integration & validation)
                                                        │
                                      CP10 ──HG6 (blocking: CP11 does not
                                              start automatically)──>
                                                        │
                                              CP11 (pre-commercial hardening)
                                                        │
                                      CP11 ──HG7 (blocking: separate launch
                                              authorization required)──> commercial launch
```

**[J]** Two sequencing notes not visible in the table alone:
- CP2 and the tail of CP1 can overlap (Instrument/Listing identity from CP1 is a
  prerequisite for Market Data adapters to attach prices to *something*, but CP1's
  ledger/position work and CP2's adapter-building work touch different modules and
  could be parallel workers once CP1's domain model is fixed).
- CP4 and CP5 both depend on CP3's return series but not on each other — they can run
  as parallel workstreams inside the HG2→HG3 span.

---

## 8. T8 — Unresolved technical choices, logged not guessed

**[F]** Rule §44.17: architectural trade-offs that are hard to reverse are proposed as
ADRs. AC-13 requires zero silent defaults — stack and persistence are explicit above
(§2) even where framed as proposals. This section is the complete log of what remains
genuinely open, plus ADR proposals for the hard-to-reverse ones.

### 8.1 Proposed ADRs (proposals only — `decisions/accepted/` is not this task's
authority; HG1 decides whether these become real ADRs)

| # | Proposed ADR | Why it's hard to reverse |
|---|---|---|
| ADR-P1 | Modular monolith (single deployable, internally bounded) for V1, with AI Orchestration as the one separate process **[SUPERSEDED IN PART 2026-09-22 by `PD-0020` — see §13.B. The "AI Orchestration as the one separate process" clause is no longer the active V1 decision. Active V1 decision: modular monolith, AI Orchestration behind a hard internal boundary inside the one deployable, separate-process isolation deferred to CP9. The rest of this ADR row (single deployable, internally bounded, for V1) is unaffected and remains active.]** | Distribution boundaries are expensive to retrofit; cheap to relax from monolith→services later if the module boundaries (§1.2) were drawn correctly, expensive to introduce distribution the plan didn't anticipate |
| ADR-P2 | Backend language/runtime = statically-typed Python | Rewriting the analytics core in a different language later is a multi-checkpoint cost, not a refactor |
| ADR-P3 | Relational persistence (PostgreSQL-class) for ledger + market-data + methodology registry | Migrating an append-only financial ledger between storage paradigms after CP1 data exists is high-risk |
| ADR-P4 | **[Revised 2026-09-04 post `technical_review` B-1]** P1 boundary mechanism as specified in §4: credential/data-store isolation (route 1) + provenance-bound rendering with a decidable value-shape definition (routes 2–3) + typed contract (P5, not counted toward P1) + import lint (defense-in-depth, route 1 only). Qualitative mischaracterization (§4.5) is an open item, not part of this ADR's claim. | This *is* the compliance boundary for P1/NFR-002; changing it after CP9 exists means re-auditing every AI code path |
| ADR-P5 | Issuer/Listing split with FIGI+MIC canonical identity (§3.1) **[SUPERSEDED/CLARIFIED IN PART 2026-09-22 by `PD-0021` — see §13.C. "FIGI+MIC canonical identity" no longer reads as the complete active persistence-key rule. Active V1 decision: immutable internal Issuer/Instrument/Listing IDs are the canonical persistence and join keys (PD-0021 Option A); FIGI+MIC remain canonical identity primitives for external resolution, matching, normalization and evidence — not physical primary/foreign keys. The Issuer/Listing split itself (§3.1, §10.3) is unaffected and remains active.]** | Every downstream ledger event, position, and analytics join keys off this; changing it after CP1 data exists requires a data migration, not a schema tweak |
| ADR-P6 | Computation Manifest as the reproducibility mechanism (§6.2) | Retrofitting audit trails onto calculations that were run without one is not possible after the fact — the inputs may no longer be pinned |

### 8.2 Open questions logged, not guessed (not proposed as ADRs — genuinely undecided)

| Open item | What's undecided | Why it's not guessed here | Resolves by |
|---|---|---|---|
| Frontend SPA framework | Which component framework (React-class vs. alternative) | No product requirement in scope forces a specific one; picking one now would be a silent default the brief forbids | HG1, or deferred to CP7 start if HG1 prefers |
| Time-series storage specialization | Relational-store-only vs. dedicated time-series DB for price/FX history | No load profile exists yet (no vendor data, no network egress) to justify the added operational surface | Revisit at CP2 with real or representative data volumes |
| Job/queue infrastructure | Whether V1 needs asynchronous background processing at all | Nothing in CP0–CP11 scope as written requires it (no live ingestion pipeline); premature to add | Revisit if CP2 vendor adapters require scheduled refresh |
| ~~§32 state-vocabulary shape (OQ-01)~~ | ~~Flat 9-state enum vs. 3 sufficiency states + 6 reason codes (A-05)~~ | **[Closed 2026-09-03 by `decisions/product/PD-0006-...md` as a PM product-contract decision, not the human owner's — §9 below is updated accordingly. Row kept, struck, per N-11 (`reviews/TECH_REVIEW.md` §13.6) so this table's own history is visible rather than silently deleted.]** | ~~Before `implement` builds I2, ideally at/before HG1~~ **Resolved** |
| Market-data vendor selection (OQ-04) | Which vendors are available for the launch jurisdiction | No network egress/credentials in this workspace; a human provisioning step | HG1 (informational), blocking by CP2 |
| Deployment/hosting target | Cloud provider, region, Mainland China hosting constraints | Out of CP0 scope and entangled with HG7's regulatory review (§41.2); guessing here would presuppose an unmade legal decision | HG7, informed earlier by §31's specialist review |
| AI model/provider for AI Orchestration | Which LLM provider/model powers CP9 | **[Corrected 2026-09-04 per `technical_review` B-1b — the prior claim in this row was wrong.]** No requirement in CP0-scoped material forces a choice. Provider selection *does* bear on network topology — a hosted provider is a second network destination (§4.1a) — but it does not bear on Control 3, because §4's rendering control does not rely on network-destination counting to catch AI-originated numbers; it constrains what the *response* may contain regardless of which model produced the draft. | CP9 |

**[J]** I deliberately did **not** guess at the frontend framework, the deployment
target, or the AI model provider, even though AC-13 asks for "zero silent defaults" —
the instruction is to make choices explicit or log them, not to manufacture a choice
where none is required yet. A default here would itself have been the silent-default
failure mode AC-13 is checking for.

---

## 9. OQ-01 and its effect on T3 and T4 — **closed 2026-09-03; section kept as a record**

**[Corrected 2026-09-04, per `reviews/TECH_REVIEW.md` §13.6 N-11: this section's
opening previously still read "this is unresolved" after PD-0006 had already closed
it, one of four stale references the finding named. Corrected below, not deleted, so
the reasoning that justified treating this as low-risk-to-defer remains checkable.]**

~~**[F]** `specs/FEATURE_PRD.md` OQ-01 asks whether §32's nine states are a single flat
vocabulary or three sufficiency states (`AVAILABLE`/`LIMITED`/`INSUFFICIENT_DATA`) plus
six reason codes (A-05's reading). This is unresolved and the brief requires me to plan
to A-05's reading while marking the dependency, not to assume it silently.~~ **OQ-01 is
closed.** `decisions/product/PD-0006-metric-state-vocabulary-is-layered.md` (2026-09-03,
amended twice since) rules the layered reading — `sufficiency_state` +
nullable `reason_code`, with a targeted coupling for five of the six reason codes — as a
PM product-contract decision, not the human owner's, on the grounds that §32 itself
calls its list "suggested conceptual states." `implement` has built to this shape
(`src/product_contract/metric_state.py`). The analysis below is retained because it
predicted correctly that this would be a low-cost decision to have gotten this far
without waiting on, not because the dependency is still live.

**Where it bit, for the record:**

- **T3 `MetricResult` entity (§3.1):** proposed shape under A-05 is two fields —
  `sufficiency_state: enum{AVAILABLE, LIMITED, INSUFFICIENT_DATA}` (required) and
  `reason_code: enum{STALE_DATA, UNSUPPORTED_ASSET, MISSING_BENCHMARK,
  MISSING_COST_BASIS, MISSING_FX_HISTORY, CALCULATION_ERROR} | null` (present only
  when `sufficiency_state != AVAILABLE`, and even then optional — a state can be
  `INSUFFICIENT_DATA` without a specific named reason). This is the shape PD-0006
  confirmed and `implement` built, including the targeted coupling PD-0006's second
  amendment added (`STALE_DATA` exempt, the other five not) — see
  `src/product_contract/metric_state.py`. The alternative this section originally
  hedged against — a flat nine-value enum — did not happen; the paragraph is kept only
  to show the hedge was reasoned, not to describe a live fork.
- **T4 Control 2 (§4.2):** the Tool Gateway's schema validation ("requires a `state`
  field") is written generically enough that it validates either shape — "the response
  must carry a sufficiency signal" is the actual structural requirement; which shape
  that signal takes does not change controls 1, 3, 3b, or 4, and changes control 2's
  schema definition only.

**[J]** I am treating this as low-risk-to-defer specifically because I designed the
manifest/contract boundaries (T4, T6) to be indifferent to the field's internal shape.
If a future reviewer disagrees that the shapes are truly this decoupled, that is a
finding for `technical_review`, not something I can self-certify.

---

## 10. Known limitations and unresolved items (AC-21)

This section is required non-empty and honest; it is not a restatement of §8's log.

1. **This plan proposes; it does not verify.** No dependency was installed, no code
   was compiled, no schema was executed against a real database. Every claim about
   feasibility is reasoned, not tested. The environment provides no network egress
   and no ability to install a toolchain, so no such verification was possible in this
   task — recorded as **not run**, not as a passing check.
2. **The reworked P1 boundary (§4) is a design, not a running system, and two things
   in it are explicitly not solved (§4.5, revised 2026-09-05 after three
   `technical_review` rounds).** Its soundness depends on `implement`/CP1+ actually
   building the Rendering Service and import-boundary lint exactly as specified — a
   later engineer skipping the Rendering Service (e.g., "just filter obviously wrong
   numbers" from free text, which is the exact design this rework replaced) would
   silently weaken the guarantee this plan claims. `technical_review` round 3 verdict
   was **CLEAR TO GATE** with AC-10 satisfied and AC-09 restored, and this document was
   further corrected afterward to close three exemption leaks it found by hand
   (§4.3a forms 1–3) and one specification inconsistency (§4.3b vs. §1.3, N-13) —
   `technical_review` should treat both the mechanism and this closure history as a
   checkable commitment at CP9, not a CP0-only concern. What remains open, per §4.5:
   (a) qualitative mischaracterization without a numeric token is not caught by any
   control in §4 — unchanged across all rounds; (b) §4.3a's allowlist checks free text
   against a large but finite, and not claimed-exhaustive, number-word vocabulary — its
   correctly-diagnosed gap (2026-09-05 correction) is *fused* number-unit words
   ("twice," "doubled," "dozen"), not "regional variants" as an earlier, wrong version
   of this item claimed. Both are logged in §4.5, not resolved here.
3. **Scale reasoning is not load-tested.** NFR-007's ~500 holdings figure is treated
   as a design constraint, not benchmarked against the proposed relational schema.
   §7 of the increment brief explicitly permits this ("need not be optimized for it
   at CP0").
4. **~~OQ-01, OQ-02, and OQ-04 are genuinely open~~ [Corrected 2026-09-04, N-11:
   OQ-01 closed 2026-09-03 by PD-0006 — this item still called it open after the
   fact.] OQ-02 and OQ-04 are genuinely open**, and this plan's proposals under OQ-02
   (stack/persistence) are proposals for HG1, not decisions. If HG1 rejects the
   monolith-with-isolated-AI-process shape, §4's controls need re-deriving against
   whatever deployment shape HG1 prefers — the *requirement* (credential/data-store
   isolation, a typed P5 contract, and provenance-bound rendering with label-binding —
   §4.1–§4.3b, renamed from the pre-rework "credential isolation + typed contract +
   grounding check") does not depend on monolith-vs-microservice, but this document has
   not separately verified that for every alternative deployment shape.
   **[RESOLVED 2026-09-22 — `OQ-02` closed by `PD-0020`/`PD-0021` (human product owner);
   the alternative deployment shape this item anticipated (modular monolith with AI
   Orchestration integrated rather than a separate process) is the one the human owner
   actually chose. §13.B below performs exactly the re-derivation this item flagged as
   outstanding, against that shape specifically, and states which parts of §4.1's
   guarantee hold at the same strength and which are honestly weaker without a separate
   process. This item is closed by that re-derivation, not by asserting the requirement
   was topology-independent without re-checking it.]**
5. **The domain model (T3) does not yet cover corporate-action mechanics, cash-flow
   treatment nuance, or the full instrument metadata list** at field-by-field
   precision — §38.3 scopes that detail to CP1 ("User/Portfolio/Account model;
   Instrument/Issuer/Listing model; Ledger event schema... unit tests"), not CP0.
   This plan gives boundaries and the entities CP1 must refine, not CP1's schema.
6. **No vendor has been evaluated.** T5's port/adapter claim ("swapping a vendor
   reaches zero analytics code") is architecturally sound but has not been proven
   against a real second vendor's payload shape, because no vendor is available in
   this environment (OQ-04, no network egress).
7. **I am not a domain expert on FIGI/MIC data quality edge cases** (e.g., instruments
   without a FIGI, delisted/relisted securities, dual-class shares) — §10.1 says "use
   FIGI + MIC where available," implying a fallback path exists, but this plan does
   not specify what that fallback identity scheme is. Logged here rather than guessed;
   CP1 needs to resolve it with `quant_analyst`/product input if data quality issues
   surface.
8. **This document was authored by the same role (`engineer`) that will implement
   CP1+.** Per `roles/engineer.json`, I cannot declare my own work reviewed —
   `technical_review` is a distinct identity and its findings, not my confidence, are
   what should inform HG1.

---

## 11. Traceability to acceptance criteria

| AC | Requirement | Where addressed | Self-assessment |
|---|---|---|---|
| AC-09 | Architecture, stack, dependencies, module boundaries documented with reasoning; each boundary states what's on each side and why | §1, §2 | **Regressed, repaired, and the repair was independently confirmed.** `review-01`'s round-2 B-5: the §4 rework introduced a Rendering Service that carried every P1 guarantee but was never drawn in the architecture. Closed 2026-09-04 (§1.1 item 5, §1.2, §1.3, §1.4, §12) and `technical_review` round 3 confirmed **AC-09 restored** ("present in all six places, with the regression acknowledged rather than papered over" — `reviews/TECH_REVIEW.md` §14.1/E3-2). Round-4 corrections (§4.3a/§4.3b) touched no architecture boundary, so this verified state is unchanged. |
| AC-10 | Specific mechanism preventing AI from originating a presented number; structural, not a guideline; a reviewer can describe how a violation fails | §4 (reworked across three review rounds; corrected a fourth time 2026-09-05 after CLEAR TO GATE) | **`technical_review` round 3 verdict: AC-10 satisfied, CLEAR TO GATE** (`reviews/TECH_REVIEW.md` §14.0/§14.2) — the allowlist closed `review-01`'s round-2 worked sentence in both digit and word form, hand-verified against fourteen strings. That verdict also found, and this document has since corrected: three exemption leaks in §4.3a's non-claim forms (Form 1 admitted fused shorthand like `250BP`/`12M`; Form 2 admitted bare index levels like "closed at 1950"; Form 3 admitted counts of the user's own portfolio, a product question `decisions/product/PD-0008` has since ruled on) — all three closed 2026-09-05, not merely disclosed; and a specification inconsistency between §4.3b and §1.3 over how a citation's label is derived (N-13) — closed by removing the AI-authored `label_ref` and deriving the label entirely from the cited call's own `methodology_ref`. Two residuals remain, named in §4.5: qualitative mischaracterization without any number (unchanged across all rounds, routed to Insight Engine territory, not a T4 control), and the number-word vocabulary's fused-word gap (correctly diagnosed 2026-09-05; previously misdiagnosed as "regional variants"). **Not self-certified** — this is a report of what was reworked against every specific defect found, not a claim that a fourth review round would find nothing; `technical_review`'s next verdict is the one that matters, per `roles/engineer.json`'s limits on declaring my own work reviewed. |
| AC-11 | Five normalized contracts (Instrument, SecurityPrice, FXRate, CorporateAction, BenchmarkSeries) specified; explains why a vendor swap doesn't reach core analytics | §5 | Satisfied |
| AC-12 | Six §34 inputs enumerated; conventions live in `methodology/` | §6.1, §6.3 | Satisfied |
| AC-13 | Unresolved choices logged as open questions or ADR proposals; stack and persistence explicit; zero silent defaults | §2, §8 | Satisfied |
| AC-14 | §38.5 mapping reproduced correctly, CP1–CP11 sequence with HG gates marked blocking | §7 | Satisfied |
| AC-21 | Known limitations and unresolved items, non-empty | §10 | Satisfied |

---

## 12. Explicit deviations from source material (required by the HG1 package per §38.2)

- **§37's single "Application/API Layer" box is split into two** (Query/Command API,
  Tool Gateway) — an amendment, not a rejection, made to give T4 a structural anchor.
  See §1.1 item 2.
- **§37 shows Scenario as a sub-bullet of Analytics Engine; this plan promotes it to a
  sibling module** — see §1.1 item 4.
- **§37 does not show a Methodology Registry box; this plan adds one as a first-class
  shared service** — see §1.1 item 1.
- **§37 does not show a Rendering Service; this plan adds one as a fifth boundary,
  on the trusted side, between AI Orchestration and the client.** **[Added 2026-09-04,
  closing `reviews/TECH_REVIEW.md` B-5.]** This deviation was introduced by the §4
  rework (provenance-bound rendering) and was missed from this list at the time — B-5
  is the finding that caught the omission. See §1.1 item 5, §1.2, §1.3, §1.4.
- No other deviation from source PRD content is claimed. Where this plan makes a
  choice source material left open (stack, persistence, deployment shape), it is
  logged as a proposal in §2/§8, not presented as if the source material specified it.
  **[Note added 2026-09-04]:** this line itself was false between the §4 rework and
  this correction, because it asserted completeness while the Rendering Service
  deviation above existed and was not listed — recorded here rather than silently
  fixed, per this document's own practice of showing corrections rather than erasing
  the trail that produced them.

---

## 13. Phase B / PD-0020 + PD-0021 — Architecture addendum and supersession record

**Added 2026-09-22, `engineer`, `tech_planning` reconciliation round.** **Authority:**
`decisions/product/PD-0020-phase-b-architecture-and-sequencing.md` and
`decisions/product/PD-0021-cp1-identity-and-entry-preconditions.md`, both human-accepted
and synchronized for Engineer reading at
`specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md`. This section does not introduce a new
product or architecture decision of its own — everything decided here was already
decided by the human product owner in PD-0020/PD-0021. What this section does is what
§0's evidence-marker discipline requires: reconcile this document's CP0 proposal history
against those decisions, mark what changed, mark what didn't, and close the one item
(§10 item 4) this document itself flagged as needing exactly this re-derivation. Per
this document's own established practice (§4.3a, §12), **nothing below deletes or
rewrites earlier proposal text** — superseded clauses are marked in place (§8.1's ADR
index, §1.4, §2, §10 item 4, above) and preserved as proposal history, not erased.

### 13.A Architecture — confirmed, narrowed, and unaffected items

**[F]** PD-0020 ratifies, independently of this document's CP0 proposals, the following,
none of which changes what §1–§2 already proposed:

- **Backend/runtime:** Python-first — matches ADR-P2 (§8.1) and §2's Python row exactly.
  No change.
- **Frontend architectural class:** TypeScript SPA — matches §2's web-client row exactly.
  **The specific framework remains human-undecided** (§8.2's open row is unchanged and
  still open; PD-0020 explicitly declines to close it). Nothing in this addendum selects
  one, and nothing here authorizes a Python-rendered frontend in its place.
- **Persistence:** PostgreSQL-class relational — matches ADR-P3 (§8.1) and §2's
  persistence row exactly, and was decided independently of this document's proposal,
  not merely rubber-stamping it.
- **Ledger:** first-class append-only event model, `PostgreSQL → append-only
  ledger/event tables → deterministic point-in-time reconstruction` — matches §3.1's
  `LedgerEvent` entity and §6.2's Computation Manifest mechanism exactly. **Explicitly
  not authorized:** Kafka, a dedicated event-store product, distributed event sourcing,
  or service-per-domain. This document never proposed any of those; no change required.
- **Topology:** modular monolith, no microservices/sharding/distributed
  transactions/dedicated queues/time-series database **without evidence** — matches
  §1.4's modular-monolith proposal and §8.2's "no load profile exists yet" reasoning for
  deferring a dedicated time-series store. The one topology item PD-0020 changes is the
  AI Orchestration exception — see §13.B, which is why it is broken out separately
  rather than listed here as confirmed.
- **Dev environment:** human-provisioned, harness retained for governance/review,
  conditional on E0 — new machinery (E0/E0b) that this CP0 document did not previously
  contain; specified fully in §13.F–§13.I below.

### 13.B AI-orchestration topology and the P1 boundary — the central item

**[F] The decision.** PD-0020 decides differently from §1.4/§2's CP0 proposal: **modular
monolith for V1, AI orchestration behind a hard internal boundary, separate-process
isolation deferred to CP9.** The prior proposal — AI Orchestration as a separate
deployable process even at V1 scale, described in §1.4 as "one deliberate exception" and
in §2's stack table as "a structural requirement of the P1 boundary, not a convenience
choice" — is **superseded for V1**. It is marked in place at §1.4, at §2's AI
Orchestration runtime row, and at ADR-P1's index row (§8.1) above; it is preserved as
proposal history, not deleted, per this document's own §4.3a/§12 practice.

#### 13.B.1 The active V1 P1 enforcement mechanism, restated concretely for one deployable

**[J]** The shape is: **AI module → fixed-signature Tool Gateway / application-service
boundary → approved deterministic data/tools.** This is not a new mechanism invented to
fit the monolith — it is §4's existing ADR-P4 mechanism (Controls 1–4, §4.1–§4.4),
restated with its Control 1 half now enforced by module/application-boundary discipline
inside one process rather than by process separation, and its Control 2–4 half
(provenance-bound rendering, §4.3–§4.3b; the typed P5 contract, §4.2; import-boundary
lint, §4.4) **completely unaffected**, because none of those three ever depended on
process topology in the first place — they constrain what the AI module is given and
what it is allowed to emit, not which process it runs in. Concretely, for V1:

- The `ai_orchestration` module has **no direct database handle** of any kind, at any
  scope — not a pooled connection, not a read replica handle, not an ORM session.
- `ai_orchestration` **does not import any persistence implementation** — no
  `sqlalchemy`/driver-level import, no repository class, no query-builder — enforced by
  Control 4's import-boundary lint (§4.4), which is unchanged and remains the concrete
  build-time check for this.
- `ai_orchestration` **does not directly access market-data adapters** — it cannot import
  `market_data`'s adapter classes or vendor SDK types, matching §4.4's existing rule and
  §1.4's existing dependency table (`ai_orchestration` may import only `tool_gateway`'s
  public interface).
- `ai_orchestration` **receives only fixed, typed Tool Gateway contracts** — the §22.2
  fixed function list, each returning a schema-validated `MetricResult`-shaped object
  that requires a `state` field (Control 2, §4.2) — never an open query surface, never an
  ORM object, never a raw row.
- **Tool results remain deterministic and evidence-backed** — every value the AI module
  receives already carries a `methodology_ref` and traces to a Computation Manifest
  (§6.2); nothing about the monolith topology changes what the Tool Gateway is allowed to
  return.
- **Import-boundary lint/static enforcement as defence-in-depth** — Control 4 (§4.4),
  unchanged, now carries more of the practical weight for Control 1's guarantee than it
  did when a process boundary was also present, because it is no longer backed by an OS
  process boundary as a second, independent line of defense against an accidental
  violation. This is the honest cost named in §13.B.2 below, not hidden here.
- **Persistence/application infrastructure alone holds or receives the database
  credential and connection configuration.** The database credential and connection
  string are configured only in the persistence/application-infrastructure layer (the
  modules that already own database access in §1.2/§1.4 — Portfolio Service, Instrument
  Service, Market Data Layer, and the Tool Gateway's own audit-trail reader) — never
  passed to, imported by, or reachable from `ai_orchestration`'s module namespace,
  process environment, or configuration scope.
- **The AI module receives no DB handle and no connection string** — restated because it
  is the load-bearing half of Control 1 inside one process: even though the AI module
  now shares an OS process and address space with the code that *does* hold a DB
  credential, the AI module's own code, imports, and runtime configuration are never
  given that credential or a handle constructed from it. A credential the AI module never
  receives cannot be exfiltrated or misused by AI-authored/AI-influenced code running in
  that module, regardless of what else shares the process.
- **AI/provider credentials confer no database authority.** Whatever credential
  `ai_orchestration` holds to reach an LLM provider (§4.1a's second network
  destination, if CP9 uses a hosted model) is scoped only to that provider's API and
  grants nothing against the database, the Tool Gateway's internals, or any other
  module's credential.
- **No hidden shared mutable state bypasses the boundary** — the monolith's shared
  process memory must not be used as an undeclared side channel between
  `ai_orchestration` and a persistence-holding module (e.g., no shared cache object, no
  module-level global, no singleton registry that either module can read or write
  outside the Tool Gateway's own typed interface). This is a new requirement this
  document did not need to state under the separate-process proposal, because a process
  boundary made it structurally impossible by default; inside one process it must be
  stated and enforced (by the same Control 4 lint extended to flag any such shared
  mutable object, and by code review/tests) rather than assumed.

This restates and narrows §4.1's control, and correspondingly narrows ADR-P4's index
claim (§8.1): route 1 (direct access) is still structurally closed for V1 — the AI module
still cannot reach the database or a market-data adapter through any lawful code path —
but by module/import/configuration discipline rather than by OS-process/credential
separation. Controls 2–4 and the whole of §4.3/§4.3a/§4.3b (which do the actual work
against routes 2 and 3, per ADR-P4's own accounting) are untouched by this change, which
is the reason §13.B.5 below concludes P1 is preserved rather than weakened wholesale.

#### 13.B.2 What is still enforceable in a modular monolith vs. what is genuinely weaker — stated honestly, not blended

**[J] Still enforceable at the same strength inside one process, per §13.B.1:**

- module/import dependency restrictions (Control 4's lint rule, §4.4);
- the typed, fixed-signature Tool Gateway contract (Control 2, §4.2);
- no persistence imports and no persistence handle reachable from the AI module;
- only the persistence/application-infrastructure layer receives DB connection
  configuration — the AI module's configuration scope never includes it;
- the deterministic, evidence-backed tool/result boundary and provenance-bound
  rendering (Control 3, §4.3–§4.3b) — **this is the control that does the actual work
  against routes 2 and 3 per ADR-P4, and it is entirely unaffected by process topology**,
  because it constrains the Rendering Service's behavior on the trusted side and the
  Tool Gateway's audit trail, neither of which changes shape when the AI module moves
  from a separate process into the same process;
- static lint / code review / tests as defense-in-depth against an *accidental*
  violation of the above.

**[J] Genuinely weaker than a separate process — not claimed otherwise:**

- **same-process memory isolation** — a separate process gives the OS's own address-space
  separation as a structural backstop; inside one process, a memory-safety bug,
  a debugger attached to the process, or a sufficiently privileged in-process exploit
  can in principle reach data the module boundary was designed to keep the AI code away
  from, in a way no import-lint rule can prevent, because the lint operates on source
  code, not on running memory;
- **OS/process fault containment** — a crash, a runaway loop, or a resource-exhaustion
  event inside `ai_orchestration` can affect the whole deployable, not just an isolated
  process, because they now share a process;
- **network-level isolation** — a separate process can be placed behind its own network
  segment/firewall rule with no route to the database's port at all; inside one process
  there is no network hop to deny in the first place, so this line of defense does not
  exist for V1 and is not being claimed;
- **independent process/service identity** — a separate process can run under its own OS
  user/service account, independently auditable and independently revocable; inside one
  process, the AI module's code runs under the same OS identity as everything else in the
  deployable;
- **process-level credential isolation** — this is the one most important to state
  precisely: **ordinary application configuration scoping (§13.B.1's "AI module receives
  no connection string") does not produce the same guarantee as a separate service
  identity.** A separate process's OS-level identity means the database credential is
  never even loadable into that process's memory space under any code path, by
  construction of the deployment, independent of what the application code does.
  Module-level configuration scoping inside one process is a code-level and
  configuration-level discipline — enforced by how the codebase is written, reviewed,
  and linted — not an OS-level guarantee that holds even against a bug in the
  application's own configuration-loading code. **This document does not claim ordinary
  application configuration produces the same credential boundary as a separate service
  identity, and PD-0020's decision to defer process isolation to CP9 is, honestly, a
  decision to accept this specific gap for V1**, not a decision that the gap does not
  exist.

#### 13.B.3 Upgrade path preserved

**[J]** The internal Tool Gateway / application-service boundary specified in §13.B.1 is
designed so that CP9 hardening — moving `ai_orchestration` back out to its own process
or service — is an *infrastructure* change, not a contract change: the Tool Gateway's
fixed-signature interface, the `MetricResult` typed contract, the Computation Manifest,
and the Rendering Service's provenance-bound rendering mechanism (§4.3–§4.3b) are all
already expressed as boundaries between modules communicating through typed
calls/returned objects, not as in-process function calls that assume shared memory.
Extracting `ai_orchestration` into its own process at CP9 means giving it its own OS
process/service identity and routing its existing Tool Gateway calls over a process or
network boundary instead of an in-process call — the product-facing deterministic
contract (what a `MetricResult` looks like, what a rendered response is allowed to
contain) does not change. This is consistent with §1.4's own reasoning for the module
boundaries generally ("drawn so that any one context *could* be extracted into its own
service later without a rewrite") — PD-0020 simply moves AI Orchestration from "extract
now" to "extract at CP9" within that same design, rather than requiring a different
design.

#### 13.B.4 §10 item 4 (the OQ-02 re-derivation note) — resolved

See the marker added directly on §10 item 4, above. That item said: if HG1/the human
rejects the monolith-with-isolated-AI-process shape, §4's controls need re-deriving
against whatever shape is preferred, and this document had not separately verified the
requirement (credential/data-store isolation, typed contract, provenance-bound
rendering) held for a shape other than "monolith with AI Orchestration as a separate
process." **This section is that re-derivation, performed against the exact shape
PD-0020 chose** (modular monolith, AI Orchestration integrated, isolation deferred to
CP9). The result: the typed-contract and provenance-bound-rendering halves of the
requirement (§4.2–§4.3b) hold unchanged, because they never depended on process
topology; the credential/data-store-isolation half (§4.1) holds at module/configuration
strength rather than OS-process strength, and §13.B.2 states precisely which specific
guarantees (memory isolation, fault containment, network isolation, independent
identity, process-level credential isolation) are the ones given up. §10 item 4 is
closed by this analysis, not by asserting the outcome without performing it.

#### 13.B.5 Conclusion — P1 is preserved for V1, at a stated and honest cost

**[J]** P1/NFR-002 can be satisfied at V1 under the modular-monolith shape, **not**
because the monolith reproduces every guarantee a separate process gave, but because the
control doing the actual work against P1's named failure mode (§4.0's routes 2 and 3 —
derived arithmetic and fabrication, which is what ADR-P4/`review-01`'s B-1 finding
established as the case the original separate-process framing never actually caught
either, per §4.1's own "what this control does NOT catch" admission) is
Control 3/provenance-bound rendering, and that control is topology-independent. What is
lost is specifically route 1's *depth* of defense — from an OS-enforced, independently-
identified process boundary down to a code-level/configuration-level module boundary —
which §13.B.2 names precisely rather than glosses over. This is not a case of finding P1
cannot be preserved and needing to escalate: the human product owner has already made
this exact trade-off, explicitly, in PD-0020 ("AI orchestration behind a hard internal
boundary, separate-process isolation deferred to CP9"), with full knowledge that
isolation is being deferred, not skipped. Nothing above weakens what PD-0020 already
decided to weaken, and nothing above weakens anything further than that.

### 13.C Identity

**[F]** PD-0021 §2.1 (Option A): immutable internal database identities are the
canonical persistence and join keys. Distinct durable internal identities for **Issuer**,
**Instrument**, **Listing**. **Ledger events reference the internal `listing_id`** —
never ticker, never FIGI, never a FIGI+MIC composite, never a vendor identifier. Internal
IDs stay stable when FIGI is unavailable, arrives later, or changes; when vendor mappings
disagree; when a ticker changes; when something is delisted; when a provider is replaced.

**FIGI + MIC remain authoritative resolution primitives** for real-world identification,
matching, security resolution, normalization, and evidence/provenance — **not** for
physical database primary keys. PRD §10.1's "use FIGI + MIC as canonical identity
primitives where available" is read this way, per PD-0021. **Option C (a deterministic
natural-key uniqueness scheme to make internal IDs less opaque) is not adopted** — it may
be additive hardening later; it is not part of this ruling.

**[J] Relation to this document's existing §3.1 domain model.** §3.1's `Listing` entity
already states it "carries FIGI + MIC as canonical identity primitives (§10.1)," which
this addendum does not need to rewrite (per this document's own practice of not
rewriting historical text), but which reads ambiguously as to whether FIGI+MIC are the
physical key. PD-0021 resolves that ambiguity: `Listing`'s physical persistence key is
its own immutable internal `listing_id` (and correspondingly `Issuer.issuer_id`,
`Instrument.instrument_id` where the model distinguishes instrument from listing);
FIGI and MIC are attributes on `Listing` used for external resolution, vendor mapping,
and evidence — never the join target for `LedgerEvent`, `Position`, or any other
internal foreign key. §3.2's relationship summary line `LedgerEvent *--1 Listing (where
applicable)` already models this correctly at the entity-relationship level (it was
already a foreign key to the `Listing` entity, not to a FIGI/MIC value) — PD-0021 makes
explicit what was previously only implicit: that foreign key is the internal
`listing_id`, by decision, not by the accident of the entity relationship diagram not
having specified a key column.

**The decisive invariant, restated:** a correction to external identity (a FIGI
correcting itself, a vendor mapping changing, a ticker changing) must be capable of
becoming an **identity/resolution attribute update** on the existing `Listing` row — not
a migration of every historical `LedgerEvent` row that references it. This is the
concrete reason the internal ID, not FIGI/MIC, is the join key: `LedgerEvent.listing_id`
never needs to change when the FIGI attached to that same `Listing` row is corrected.

**ADR index:** see ADR-P5's row (§8.1, above), marked superseded/clarified in part by
this section.

### 13.D Ledger

**[F/J]** Confirmed unchanged, restated for Phase B completeness: append-only event
model (§3.1 `LedgerEvent`, §6.2 Computation Manifest's `ledger_version` reference);
deterministic point-in-time reconstruction (§6.2, §9.7 of the source PRD); mutable
current holdings are **not** authoritative — `Position` (§3.1) is explicitly derived,
never directly written, matching PRD §9.1's "do not maintain an independent mutable
'current shares' value that can silently diverge from the ledger," which
`specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md` §3 carries forward as a standing
constraint. **Correction/reversal pattern:** a `LedgerEvent` row is never `UPDATE`d or
`DELETE`d once appended — the domain model already assumes this (§6.2: "LedgerEvents are
never edited in place (corrections are new offsetting events)"); this addendum makes the
consequence explicit for CP1 schema design: a correction to a previously-recorded
transaction is implemented as a new reversal/offsetting `LedgerEvent` referencing the
event it corrects, never as a mutation of the original row. **Idempotency direction:**
ledger ingestion (manual entry or CSV import, per FR-005–FR-007) must be idempotent on
the *append* direction — re-submitting the same source transaction must not create a
duplicate `LedgerEvent`, which CP1 schema design should support with a natural or
supplied idempotency key scoped to (account, source reference) — while a *correction*
is never idempotent-by-overwrite; it is always a new event, per the paragraph above.
This is domain-model guidance for CP1, not a schema this document specifies at
field-by-field precision (§10 item 5 already scopes that detail to CP1, not CP0/this
addendum).

### 13.E Currency (CP1 scope, mandatory)

**[F]** PD-0021 §2.2: **CP1-A must include the reporting/native currency domain model**,
not defer it. This addendum extends §3.1's entity list with the fields PD-0021 requires,
without rewriting §3.1's existing entries:

- **Portfolio reporting currency** — already implied by §3.1's `Portfolio`
  ("`ReportingCurrencyPolicy`," §3.2) and PRD FR-001 ("one reporting currency"); PD-0021
  confirms this stays in CP1-A scope, not deferred.
- **Listing trading/native currency** — already present: §3.1's `Listing` entity lists
  `trading_currency` explicitly (also carried on `EconomicGeography`, §3.1). Confirmed,
  unchanged.
- **`LedgerEvent` currency** — **new, made explicit by this addendum.** §3.1's
  `LedgerEvent` entry did not previously state a currency field. Each `LedgerEvent` must
  carry the currency the underlying transaction was denominated in at the time it
  occurred (e.g. a BUY executed in HKD, a DIVIDEND paid in USD) — this is the currency
  the historical fact is recorded in, and per the invariant below, it is never rewritten.
- **Account/cash currency representation** — already present: §3.1's `CashBalance` is
  "per-currency cash position, first-class alongside securities (§9.4)." PD-0021 confirms
  an `Account` may hold multiple `CashBalance` rows, one per currency, consistent with
  PRD §9.4's requirement that cash participates in portfolio value, allocation, weights,
  reporting-currency conversion, and currency exposure without being collapsed to one
  currency at the account level.
- **Historical ledger facts are never rewritten into reporting currency** — the
  decisive invariant: a `LedgerEvent`'s own currency field (above) is immutable once
  appended, exactly as the event itself is (§13.D). Reporting-currency figures (e.g. "this
  portfolio is worth $X reporting-currency as of date D") are *computed*, at read time or
  computation time, from the ledger's native-currency facts plus an `FXRate` (§3.1) — they
  are never written back onto the `LedgerEvent` row, and a later correction to an
  `FXRate` used for a past reporting-currency display never mutates a historical
  `LedgerEvent`.
- **The boundary where later FX conversion enters** — FX conversion is **not** a ledger
  concern. It belongs to the normalized observation layer this document already draws in
  §1.2/§5 (Market Data Layer, `FXRate` contract, §11.1) and, per §13.H below, to the CP2
  seam's FX-observation type specifically. The Ledger/Position Engine (Portfolio Service,
  §1.2) produces native-currency positions and cash balances from `LedgerEvent`s alone;
  a reporting-currency view is a downstream computation that reads those native-currency
  facts plus `FXRate` observations, never a property the ledger itself computes or
  stores.
- **Behaviour when an FX observation is unavailable** — this is a P5 sufficiency-state
  case, not a special currency-specific failure mode: a reporting-currency-denominated
  `MetricResult` that requires an `FXRate` observation which does not exist for the
  needed `(currency_pair, as_of_date)` must report `INSUFFICIENT_DATA` (or `LIMITED`
  with `MISSING_FX_HISTORY` as its reason code, per §3.1's `MetricResult`/PD-0006 shape,
  §9 above) rather than fabricate, interpolate silently, or fall back to a stale rate
  without marking it. The native-currency figure, which requires no FX observation,
  remains available independently — a missing FX observation degrades only the
  reporting-currency-denominated view of a fact, never the native-currency fact itself.

**[F]** Holdings and cash across USD, HKD, CNY and other supported currencies must be
representable without premature conversion — satisfied structurally by the two points
above (native-currency `LedgerEvent`/`CashBalance` facts; reporting-currency figures
computed downstream, never stored back). **Deferred is presentation only** (UI controls,
labels, native-vs-reporting display switching) — that deferral does not reach this
domain model, and nothing above is presentation.

### 13.F E0 — the connectivity precondition, and its opt-in gate

**[F]** PD-0021 §2.3: E0 is a bounded first `implement` increment whose sole purpose is
to determine whether the actual governed Engineer runtime can reach the human-provisioned
PostgreSQL endpoint. File-based test under `tests/product/`, invoked via `python3 -m
unittest` — no `python3 -c`, no `node -e`, no shell/interpreter workaround. Two
transports tested independently: Unix-domain socket and loopback TCP, each classified as
`TRANSPORT_REACHABLE` / `PERMITTED_NO_LISTENER` / `SOCKET_MISSING` / `POLICY_DENIED` /
`RUNTIME_ERROR` / timeout-or-other, with raw evidence recorded. **Send no credentials, no
PostgreSQL startup packet, no application query. E0 pass = transport reachability only**
— it does not establish protocol success, authentication, server identity/version, role
permissions, schema access, transaction behaviour, migrations, or `Decimal`/`NUMERIC`
correctness (that is E0b, §13.G below).

**[J] The opt-in gate — load-bearing, specified concretely.** The E0 test (proposed file:
`tests/product/test_postgres_connectivity_preflight.py`) must be **skipped by default**
under ordinary test discovery:

- Ordinary test discovery (`python3 -m unittest discover -s tests/product -t .`, with no
  extra environment set) **must not attempt any PostgreSQL connectivity** — the test
  method(s) must call `self.skipTest(...)` immediately, before opening any socket, unless
  the opt-in below is present.
- The preflight **runs only when an explicit opt-in environment variable is set**, e.g.
  `FINWEB_PG_PREFLIGHT=1`. Socket path/host/port come from environment variables (e.g.
  `FINWEB_PG_SOCKET`, `FINWEB_PG_HOST`, `FINWEB_PG_PORT`), never hardcoded to a value
  that assumes a provisioned database exists.
- Absent the opt-in, the test raises `unittest.SkipTest` with a message **naming exactly
  what must be set** to run it (the opt-in variable and the transport variables it reads)
  — not a bare "skipped," so a future maintainer reading test output knows how to opt in
  rather than concluding the test is dead code.

**[J] Why this is documented here, not left to be discovered the hard way.** `implement`'s
only revalidation suite (`workflows/feature-development.json`, `implement.revalidation`)
runs `python3 -m unittest discover -s tests/product -t . -v`. Default `unittest`
discovery matches `test*.py`, so `test_postgres_connectivity_preflight.py` **will be
collected** during any future `implement` revalidation run (including an
ADR-0030 `revalidate_task.py` restoration check) unless it is gated exactly as specified
above. An ungated version of this test would fail on any machine without a provisioned,
reachable PostgreSQL endpoint at the exact socket/host/port the test assumes — which
includes, by construction, every machine that is not the one E0 was originally run on —
and would cause `revalidate_task.py` to refuse restoration of otherwise-legitimately-
completed implementation work, because "every check the workflow declares for the task
passes when re-run" (per `CLAUDE.md`'s ADR-0030 summary) would never be satisfiable
again. This is a permanent, self-inflicted revalidation hazard if the gate is ever
removed as "unnecessary test skipping" by someone who does not have this context — hence
recorded here, in the primary technical implementation contract, not only in the test
file's own comments.

### 13.G E0b — separate, inside CP1-B

**[F]** PD-0021 §2.4: after the necessary application dependency (a PostgreSQL driver)
exists, E0b covers what E0 explicitly does not: driver-level connection, actual
PostgreSQL server and version, application-role access, rollback behaviour, and the
**exact `Decimal` ↔ `NUMERIC` round trip** (load-bearing for this product specifically,
because every money and share-quantity value in the domain model uses `decimal.Decimal`,
§2's T2 stack proposal). **E0b is not part of E0** — it is CP1-B scope, gated on the same
opt-in discipline as §13.F for the same reason (it also requires a real, reachable,
provisioned database and must not run under ordinary `implement` revalidation by
default).

### 13.H CP2 seam — types only

**[J]** To prevent CP1 from painting itself into a dead end at CP2, the following types
are named now, as **types only** — no adapter, no vendor payload handling, no vendor
selection (OQ-04 remains open, §13.J):

- **`QuoteObservation`** — the CP2-facing shape that will populate `SecurityPrice`
  (§3.1, §5.1/§11.1): an observed price for a `listing_id`, at a timestamp, with
  currency, source, and freshness state (§11.2).
- **`FXObservation`** — the CP2-facing shape that will populate `FXRate` (§3.1, §5.1):
  an observed rate for a currency pair, at a timestamp, with source and freshness state
  — this is the type §13.E's "boundary where FX conversion enters" resolves through.
- **`CorporateActionObservation`** — the CP2-facing shape that will populate
  `CorporateAction` (§3.1, §5.1): an observed corporate action for a `listing_id`
  (event type, effective date, ratio/amount, currency, source), consumed by the Position
  Engine per §9.7/§12 of the source PRD.
- **Freshness** — a shared state (not a per-type reinvention) attached to every
  observation type above: source time, freshness state, delayed/EOD/live status where
  known (§11.2) — this is a property of the *observation*, not of the internal identity
  it resolves to.
- **Lineage/source** — likewise shared: whether a series is raw, split-adjusted,
  dividend-adjusted, or total-return-adjusted (§11.3), carried on the observation, not
  inferred later.
- **Instrument resolution** — the type that maps an external identifier (FIGI, MIC,
  ticker, vendor-specific ID) arriving on an observation to an internal `listing_id`.
  This is the concrete connection point named below.

**[J] How CP1's internal identity model connects to CP2 instrument resolution.** §13.C
establishes that `listing_id` (internal, immutable) is the persistence/join key and that
FIGI+MIC are resolution primitives, not keys. The CP2 seam is exactly where that
resolution happens: an **instrument resolution** step takes an incoming observation's
external identifiers (FIGI where available, MIC, ticker, vendor ID) and resolves them to
an existing internal `listing_id` — creating a new `Issuer`/`Listing` row only when
resolution genuinely fails to match an existing one, updating the `Listing`'s FIGI/MIC/
ticker *attributes* (never its `listing_id`) when a correction arrives, per §13.C's
decisive invariant. `QuoteObservation`, `FXObservation`, and
`CorporateActionObservation` all carry a resolved `listing_id` (or, pre-resolution, the
raw external identifiers an adapter will resolve) — never a bare ticker or FIGI as the
field CP1's ledger/position code joins against. This is why CP1's identity ruling
(PD-0021 §2.1) had to be settled before CP2 adapter work could safely begin: CP2's
adapters resolve *into* CP1's key space, not the other way around.

**Not specified here, and not authorized:** any adapter implementation, any vendor
payload shape, any vendor selection. This section names the types CP1 must leave room
for; building them is CP2 work.

### 13.I Development environment

**[F]** PD-0020/PD-0021, synchronized: Python 3.12 as the product target runtime;
`uv` for dependency/environment management; PostgreSQL 16 or 17 as the target server
version; a **native** (non-containerized) database instance is what E0/E0b test against
— Docker is **not required for CP1**; frontend tooling remains deferred, consistent with
§13.A's "frontend framework remains human-undecided" and PD-0021 §2.6 (return for a
human decision before production frontend scaffolding, CP7 implementation, or
framework-specific design becoming load-bearing; this must not block backend/domain
work).

### 13.J P0 / OQ-04

**[F]** OQ-04 (market-data vendor selection) **remains open** — unchanged from §8.2/§9 of
the source `specs/FEATURE_PRD.md`, this document does not select one, and this addendum
does not either. **P0 is human-owned** — PD-0020 authorizes it as a human-owned parallel
market-data provisioning/commercial workstream, run in parallel with CP1, not by the
Engineer. **OQ-04 does not block CP1** — CP1 (ledger, identity, domain model, currency,
E0/E0b) does not require a selected vendor; §13.H's CP2-seam types are deliberately
vendor-agnostic so CP1 does not need to guess at one. **OQ-04 must close before CP2
exit** — per PD-0020's sequencing row and the source PRD's CP2 exit criterion (§38.3:
"same internal analytics contract can consume test data from more than one
adapter/mock"), which requires at least one real or representative vendor shape to
validate against.

## 14. CP1-B step 1 — ledger event domain model (engineer-proposed design choices)

**[Engineer-proposed; not yet reviewed. Not product law.]** Code: `src/domain/ledger.py`.
Choices the approved documents do not already make:

- **Correction shape.** `REVERSAL` is an event type carrying only `reverses_event_id`
  (no economics, so no sign convention is chosen). A corrected fact is a new ordinary
  event whose optional `corrects_event_id` names the reversed event. Cross-event checks
  are listed in `CROSS_EVENT_RULES_DEFERRED` for the persistence step.
- **Taxonomy.** `SYMBOL_CHANGE` is not an event type (PD-0021 §1.4: a ticker change is a
  `Listing` attribute update). Corporate actions other than `SPLIT` are not modelled
  (need PRD §12.4 methodology and the CP2 `CorporateAction` contract). Snapshot
  holdings use `OPENING_POSITION` / `OPENING_CASH` (PRD §9.2).
- **Transfers.** `counterparty_account_id` present = internal move (PRD §9.6); absent =
  external. Security form (`listing_id`+`quantity`) or cash form (`amount`).
- **Amounts** are positive magnitudes; direction comes from the type. Prices are not
  stored (would need a rounding convention); fees are separate `FEE` events.
- **Dates.** `event_date` plus optional `settlement_date`; which one governs replay is
  left to CP1-C / Quant.
- **Currency is required on every event**, including non-monetary ones (`SPLIT`,
  `REVERSAL`); every `Money` on an event must match it.

### 14.1 CP1-B step 2 — schema and runner (engineer-proposed)

Code: `src/persistence/` (`migrations/000N_*.sql`, `migrator.py`, `ledger_sql.py`,
`ledger_store.py`, `connection.py`). Plain SQL, psycopg 3 imported lazily (PD-0023 §3).

- The per-type CHECKs in `0002_ledger_event.sql` sit between markers and must equal
  `ledger_sql.render_generated_region()` (unit-tested against `FIELD_RULES`). A rule change
  is a new migration; applied files are immutable (SHA-256 checked).
- Cross-event rules are enforced by composite FK, partial unique index and a BEFORE INSERT
  trigger; UPDATE/DELETE/TRUNCATE are rejected by triggers. The transfer opposite-leg rule
  is not enforceable (no pairing key exists) and is left to CP1-C reconciliation.
- Idempotent append: "same content" is `LedgerEvent.has_same_content` (numeric `Decimal`
  equality; the first-stored scale is kept and returned).
- `ledger_seq` is ordered and gappy. Step 2c (below) makes it commit-stable per portfolio.

### 14.2 CP1-B step 2c — tightened to `ledger-replay/1.0` (engineer-proposed mechanisms)

Migrations 0001-0003 were edited in place (never applied anywhere). **From the first real
apply onward, changes are new numbered migration files only.**

| Rule | Where enforced |
|---|---|
| F2: no `cost_basis` on an internal `TRANSFER_IN` | `LedgerEvent` + CHECK `ledger_event_internal_transfer_in_no_cost_basis` (generated region) |
| F5: optional `DIVIDEND.ex_date <= event_date`; forbidden on other types; never read by CP1 replay | `LedgerEvent`, `FIELD_RULES`, CHECKs |
| F1: internal transfer legs match (reciprocal accounts, same date, currency, amount or listing+quantity) | Python `validate_internal_transfer_pair` in `append_internal_transfer`; database: deferred constraint trigger (per matching group, live OUT legs = live IN legs at commit; reversing a leg needs its partner reversed in the same transaction); same portfolio by BEFORE INSERT trigger |
| F6: one snapshot date per account; other events after it (SPLIT on it allowed); reversed events do not count | BEFORE INSERT trigger |
| F7: `ledger_seq` commit-stable per portfolio | trigger takes `pg_advisory_xact_lock(hash(portfolio))`, then draws the sequence (no column default), READ COMMITTED required |
| F10: correction appended reversal-first in one transaction | `append_correction`; the database independently requires the target to be reversed already, which forces the lower `ledger_seq` |
| 10b: reversed event corrected at most once; replacement in the same account | unique index `ledger_event_corrected_once`; composite FK `ledger_event_correction_target_fk` |

Step 2d (PD-0024, `ledger-replay/1.1`):

| Rule | Where enforced |
|---|---|
| `INTEREST_CHARGED`: cash-only, `amount` required, `listing_id` forbidden (same shape as `DEPOSIT`) | `FIELD_RULES` + generated CHECK `ledger_event_fields_interest_charged` |
| `CURRENCY_CONVERSION`: `currency`/`amount` = sold side; `bought_amount` required, in a different currency; listing, quantity, cost basis, split, counterparty, ex-date, reverses all forbidden | `FIELD_RULES` + generated CHECK `ledger_event_fields_currency_conversion`; `LedgerEvent` (`bought_amount.currency != currency`, `> 0`, finite via `Money`); static CHECKs `ledger_event_bought_amount_positive`, `ledger_event_bought_currency_differs`, `ledger_event_bought_pair` |
| `bought_amount` forbidden on every other type; the only `Money` exempt from the event-currency rule (F11) | `CONDITIONAL_FIELDS` / `FIELD_RULES`; `_validate_values` (module docstring updated) |
| Schema: `bought_amount numeric` + `bought_currency text`; **no rate column and no computed rate anywhere** (5A.7) | migration 0002; unit tests assert no field or column name contains "rate" |
| Reversal of a conversion carries the sold (event) currency; correction = reversal + replacement conversion, atomic | existing composite FK `ledger_event_reversal_target_fk`; `append_correction` (unit and integration tests) |
| Conversion is one row, so it needs no pairing and cannot exist half-applied | single-row insert |

Not enforced: pairing is by counts, not an identity link (identical same-day twins are
interchangeable); privileged roles can disable triggers; `ledger_seq` order across
portfolios is not commit order; batches spanning portfolios may deadlock.

### 14.2a CP1-B review fixes (migrations 0004 and 0005; engineer-proposed)

Answers `reviews/TECH_REVIEW.md` "CP1-B review (809d4d8)". 0001-0003 are frozen and pinned in
`src/persistence/migrations/CHECKSUMS` (checked by the runner and the default suite).

| Finding | Fix |
|---|---|
| CP1B-1 HIGH | every trigger function gets `SET search_path = <ledger schema>, pg_temp` (0004; schema from `current_schema()` at apply time; chosen over schema-qualifying because migrations are schema-agnostic); tested with TEMP-shadow attacks as `finweb_app` plus a control showing the attacks succeed on a 0003-only schema; does not rely on revoking TEMPORARY (`REVOKE TEMPORARY ... FROM PUBLIC` is in the production grant spec as defence in depth, not applied) |
| CP1B-2 | idempotency (same `event_id` or same `(account, source_reference)`) is decided in the trigger before the state-dependent rules; skipping the rules cannot admit a duplicate (`ON CONFLICT DO NOTHING` drops it, a plain INSERT hits the unique constraint) |
| CP1B-3 | `account_id` and `portfolio_id` immutable (trigger) |
| CP1B-4 | `CHECKSUMS` manifest; the generated-region drift test compares FIELD_RULES with the LATEST migration region (`GENERATED-REPLACE` form), so a rule change is a new migration |
| CP1B-5 | a replacement's reversal must have been inserted by the same transaction (`pg_xact_status(xmin) = 'in progress'`); limitation: relies on the transaction-status API, and would misjudge only rows visible to us but not ours and not committed, which cannot occur |
| CP1B-6 | `corrects_event_id` optional on `OPENING_*` (FIELD_RULES + 0005) |
| CP1B-7 | SQL blank check is the exact class of `str.isspace()` code points (generated, unit- and DB-tested) |
| CP1B-8 | `recorded_at := now()` in the trigger |
| 0006 (re-review) | epoch-safe same-transaction check (`ledger_full_xid`), inline schema-rename guard, proconfig pin test, `LedgerConcurrencyError.retry_safe` |
| 0007 (F12) | one live SPLIT per (account, listing, event_date): checked in `ledger_event_before_insert` under the portfolio lock after the idempotency return; reversed splits do not count; `SameDaySplitError` (`ledger_event_split_once_per_day`) |
| 0008 (R3-1..4) | numeric bounds (value < 1E30, scale <= 24) by CHECK + `LedgerValueOutOfRangeError`; `append_xid xid8` and `portfolio_id` set by the trigger (NULL only for pre-0008 rows), index `(portfolio_id, ledger_seq) INCLUDE (append_xid)`; same-transaction correction check compares `append_xid` with `pg_current_xact_id()` (no xmin arithmetic, no `pg_xact_status`); advisory-lock keys scoped by schema (portfolio lock and migrator) |
| 0008 (R4-1) | the six numeric-bound CHECKs are `NOT VALID` (new rows only; a ledger already holding an out-of-bound row, e.g. a 28-decimal deposit legal before 0008, still upgrades and replays). **Known limitation:** the CHECKs run before `ON CONFLICT`, so resubmitting a stored event whose value is written at scale > 24 (or >= 1E30) gets the typed `LedgerValueOutOfRangeError`, not an idempotent no-op. It cannot be fixed cheaply: the row is checked before the trigger's conflict decision, and exempting it would need the CHECKs to become trigger logic; such rows predate 0008 and re-import of them can be pre-normalised by the caller. Pinned by a test. |
| Observations | 40P01/40001 -> `LedgerConcurrencyError`, 22003 -> `LedgerValueOutOfRangeError`; cross-portfolio batches remain allowed and documented |

### 14.3 CP1-C — deterministic replay (engineer-proposed; not yet reviewed, not product law)

Code: `src/domain/replay.py` (pure), `src/persistence/ledger_replay_store.py` (read),
`src/marketdata/contracts.py` (CP2 seam, types only). Convention set: `ledger-replay/1.3`
(unratified until CP1-D). The module docstring of `replay.py` maps every section of the
convention document to code.

- **Function.** `reconstruct(events: Iterable[SequencedEvent], as_of, ledger_version) ->
  ReplayedState`. Pure: reads only its arguments, no clock, no randomness, no I/O. Native
  currency only; no FX, price or valuation. All arithmetic is exact `Fraction` (never rounded);
  conversion to `Decimal` at the output uses a private 200-digit context that traps inexact
  results, and a value that cannot be written exactly, or an extreme magnitude (more than
  2,000 coefficient digits or exponent digits), is an `INSUFFICIENT_DATA` state
  (`CALCULATION_ERROR`, detail `VALUE_NOT_REPRESENTABLE`) scoped to that one cash balance,
  position quantity or basis. `ReplayInputError` is raised only for inputs that break a ledger
  guarantee (duplicate `ledger_seq` or `event_id`, several snapshot dates, an event inside a
  snapshot, a wrong argument type). No int-to-string conversion is used, so CPython's
  4,300-digit limit is never reached.
- **Manifest pin.** `ledger_version` = the portfolio's max committed `ledger_seq`
  (`ledger_replay_store.current_ledger_version`; 0 if empty). Commit-stable by the per-portfolio
  lock (§14.2). `replay()` refuses a pin above the current maximum, and (C1C-2) a pin that
  splits an atomic append (for example a reversal's own seq inside an atomic correction):
  `require_committed_boundary` judges `L` by `ledger_event.append_xid` (migration 0008: the
  full xid8 of the top-level appending transaction, equal for every row of one append including
  savepoint rows, never shared by different transactions, independent of the clock). `L` is
  refused iff the last portfolio row at or below `L` and the first row above it share one
  non-NULL `append_xid`: two probes on the index `(portfolio_id, ledger_seq) INCLUDE
  (append_xid)`. Adjacent rows suffice because the rows of one transaction are contiguous in
  a portfolio (xid stamped, per-portfolio lock taken and held to commit, then the sequence
  value drawn), so a straddling equal pair implies an equal adjacent pair. `recorded_at` is no
  longer used, except as a fallback for pre-0008 rows (NULL `append_xid` and `portfolio_id`),
  and then only between two adjacent pre-0008 rows: if any post-0008 row is at or below `L`
  the xid rule alone applies; a pre-0008 row next to a post-0008 row is a boundary by
  definition (different transactions); a pre-0008 row above a post-0008 row breaks the
  ordering premise and is refused (fail closed). A portfolio that is partly pre-0008 is
  therefore judged by xid wherever a post-0008 row lies below `L`, and by `recorded_at` only
  inside its pre-0008 prefix (with the old limit: two different pre-0008 transactions with an
  equal `recorded_at` make that pin refuse, fail closed).
- **Output shape (OI-5).** Accounts sorted by id, one per account with a live event at L (present
  even if all its events are after D); positions sorted by listing, emitted only if non-zero or
  flagged; cash sorted by currency, only non-zero balances; a not-reconstructable account (D
  before its snapshot) carries a status and empty tuples. Decimals canonical (no exponent, no
  trailing zeros); `canonical_json()` is the byte-identical serialisation (T10).
- **State envelope (PD-0025).** Replay output is `MetricResult` (`Decimal` value). Only
  `AVAILABLE` and `INSUFFICIENT_DATA` are used. Situations are reason codes
  (`UNRESOLVED_CONVENTION`, `LEDGER_INCONSISTENT`, `NOT_RECONSTRUCTABLE`, `MISSING_COST_BASIS`);
  when several apply the highest-priority one is the reason code and all are kept in the
  non-state `ReplayDetail` fields.
- **Review fixes (`ledger-replay/1.3`).** Carried basis is decided by the source's same-day
  candidate set (one lot: every out-leg carries `c x q`, also when the source ends at 0); a
  flagged source hands its own reason and detail to the receiver; two or more live same-day
  `SPLIT`s on a position holding units apply neither and flag `LEDGER_INCONSISTENT` (detail
  `MULTIPLE_SAME_DAY_SPLITS`, sticky). A multi-currency basis is one no-value entry if any
  currency cannot be presented (never a partial entry). Arithmetic is exact `Fraction`
  throughout; a value too large to write in the 200-digit exact context is a state
  (`CALCULATION_ERROR`, detail `VALUE_NOT_REPRESENTABLE`) scoped to that one cash balance,
  quantity or basis, never an exception for the portfolio. Proposal (not implemented): bound
  `numeric` magnitude and scale at append in a later CP1-B migration, so the limit is never
  reached by admissible data.
- **Basis under `ledger-replay/1.2` (Ruling 0.4).** A per-lot model (units, exact `Fraction`
  unit cost, currency, or unknown). Basis is resolved per day at end of day from the candidate
  set (start-of-day lots plus every same-day acquisition), so it never depends on same-day
  `ledger_seq`. Determinate cases are computed (one candidate lot, whole-position moves, partial
  moves of a single lot); everything else is `UNRESOLVED_CONVENTION` / `LOT_DEPLETION`, sticky
  until a day ends at 0. A basis that does not terminate at the reported date is
  `INSUFFICIENT_DATA`, reason `UNRESOLVED_CONVENTION`, detail `BASIS_NOT_EXACT` (rounding
  convention is OI-8). No unit basis is emitted. Internal pairs are matched per day and
  resolved sources-before-receivers. FEE/TAX never touch basis; a non-integral split is sticky
  and unresolved.
- **Engineer choices the documents did not fix.** Inconsistent (§9) and unresolved (§7) flags are
  sticky from the date they arise. Basis is kept per currency and never summed; a
  non-terminating currency entry keeps its currency with no value. Unresolved-split
  positions also suppress basis. The known part of a partially known basis is not emitted at all.
  A same-day cycle of internal transfers is broken deterministically and its carried basis is
  unresolved.
  Input that breaks a ledger guarantee (two snapshot dates, a trade inside a snapshot, duplicate
  `ledger_seq`/`event_id`) raises `ReplayInputError` rather than being repaired.
- **CP2 seam.** `QuoteObservation`, `FXObservation`, `CorporateActionObservation`, shared
  `Freshness` and `Lineage`, `ExternalIdentifiers` and `InstrumentResolution`; types only, no
  adapter, no vendor, no conversion function; `domain` does not import `marketdata`.
- **Production grant spec (CP1D-1; supersedes the four-grant list in §14.2 and STATUS item 10e).**
  The one application role must append AND read what it serves. Replay reads start with
  "does the portfolio exist" (`SELECT 1 FROM portfolio`), so an unknown portfolio is a typed
  error and never an empty ledger. Final exact spec, run by the schema owner, nothing else:
  `GRANT USAGE ON SCHEMA <s>`; `GRANT SELECT, INSERT ON <s>.ledger_event`;
  `GRANT SELECT ON <s>.account`; `GRANT SELECT ON <s>.portfolio`;
  `GRANT USAGE ON SEQUENCE <s>.ledger_event_ledger_seq_seq`. Appends need no `portfolio`
  grant; reads do. No UPDATE, DELETE, TRUNCATE, TRIGGER or REFERENCES. The existence check is
  deliberately not routed through `ledger_event.portfolio_id`, which is NULL on pre-0008 rows.
  Tests: `APP_GRANTS` and the exact-privilege test in `test_postgres_least_privilege.py`, and
  the golden fixture replayed as `finweb_app` under exactly these grants in
  `test_cp1_reconstruction.py` (opt-in with `FINWEB_PG_APP_USER`). The defence-in-depth
  `REVOKE TEMPORARY ON DATABASE ... FROM PUBLIC` remains a documented production step.

## 15. CP2 — market-data normalization (engineer-proposed; not yet reviewed, not product law)

**Added 2026-10-01 by `engineer`. Plan only: no product code, migration or dependency is
written or changed by this section.** Authority and inputs: PRD §8, §10, §11, §12 and §38.3
(CP2 deliverables and exit criterion); PD-0020 (modular monolith, PostgreSQL, Python);
PD-0021 §1 (`listing_id` is the join key; FIGI/MIC/ticker are resolution attributes);
PD-0027 and PD-0028 (free development sources, internal use only, human-run downloads to
files, two sources per market where available, an AI is never a source, no purchase; OQ-04a
closed, OQ-04b open until private beta); §5, §6, §13.E, §13.H of this plan; STATUS items 5,
6, 12 (F8), 15, 16. Evidence markers as in §0: **[F]** fact from a source document, **[J]**
engineer judgment, **[A]** assumption to verify, **[Q]** depends on the `quant-analyst`
(`methodology/CP2_MARKET_DATA_CONVENTIONS.md`, being written in parallel; this section reads
none of its content and decides none of its subjects), **[H]** a human step.

**Exit criterion [F]:** "same internal analytics contract can consume test data from more than
one adapter/mock without business-logic change" (PRD §38.3).

### 15.0 Summary of the shape

1. **Files are the evidence of record; PostgreSQL holds a derived, append-only, rebuildable
   projection; a pure core sits under both.** Every source file is saved by a human, immutable,
   SHA-256 hashed and accompanied by a lineage manifest. An adapter is a pure function from
   those bytes to unresolved observations. Resolution turns external identifiers into
   `listing_id`. Observations are loaded into `md_*` tables (CP2c) or an in-memory store
   (CP2a/CP2b); both implement the same `MarketDataPort`.
2. **A `MarketDataRelease` is the market-data pin.** An immutable, hashed list of file hashes,
   source precedence and convention-set ids. A port is bound to exactly one release. Adding a
   download changes nothing until a new release is cut. The Computation Manifest cites the
   `release_id` and the files actually consumed. This is the market-data analogue of the
   ledger's `ledger_version` (§14.3).
3. **Analytics sees only `MarketDataPort` results.** Adapters, files, vendors and the database
   are behind it. Conventions (FX fixing, price-of-date, reconciliation, freshness thresholds)
   enter as injected, versioned pure functions, so the Quant's document plugs in without
   touching the port.
4. **Nothing the contracts or the Quant have not decided is decided here.** Where a state needs
   a rule, this section defines the data shape and a plug point only.

### 15.1 The port and the adapter interface

Two different interfaces, never mixed.

**`MarketDataPort` (read side; what analytics depends on).** Defined in
`src/marketdata/port.py` purely in the normalized types. Bound to one `MarketDataRelease`.
Methods are pure reads (same release, same arguments, same result). Sketch:

| Method | Returns |
|---|---|
| `quotes(listing_id, start, end)` | `QuoteSeries`: for each date, the candidate `QuoteReading`s from each source in the release (not a chosen value) |
| `quote_on(listing_id, as_of, rule)` | `QuoteLookup`: `rule` is an injected price-of-date function **[Q]**; result carries the chosen reading (or none), `Reconciliation`, assessed `Freshness`, and the files used |
| `fx_series(base, quote, start, end)` | `FXSeries` of published pairs only, as published (no derivation) |
| `fx_on(base, quote, as_of, rule)` | `FXLookup`; derivation through EUR, inversion, CNY/CNH handling are in the injected `rule` **[Q]** and the result carries the leg observations that were used |
| `corporate_actions(listing_id, start, end)` | `CorporateActionSet` with per-source readings |
| `benchmark(benchmark_id, start, end)` | `BenchmarkSeries` (§11.1) |
| `release_ref()` / `consumed_files()` | the `release_id` and the sorted set of `(file_sha256, adapter_id, adapter_version)` that the calls so far read, for the Computation Manifest |

Lookup results are typed outcomes, not exceptions and not `None`: `FOUND`, `NO_OBSERVATION`,
`SOURCE_DISAGREEMENT_UNRESOLVED`, `NOT_IN_RELEASE`. Mapping an outcome to a `MetricResult`
state (`MISSING_FX_HISTORY` and the like, §13.E) is the consumer's job; the port never emits a
`MetricResult` and never invents a fill.

**`InstrumentResolverPort` (identity; read) and `IdentityRegistry` (identity; write).**
Resolution returns `InstrumentResolution` (15.6). Creating or correcting identity is a separate
write interface used only by ingestion, never by analytics. The analytics port exposes no write.

**`SourceAdapter` (source side; what a vendor integration implements).**

```
adapter_id: str                # "akshare.prices.cn_daily"
adapter_version: str           # pinned in lineage; any parsing change bumps it
data_kind: DataKind            # QUOTE | FX | CORPORATE_ACTION | BENCHMARK | IDENTITY
def translate(manifest: FileManifest, payload: bytes) -> AdapterOutput
```

`AdapterOutput` is a tuple of **unresolved** observations (they carry `ExternalIdentifiers`, not a
`listing_id`) plus a tuple of `AdapterIssue(row_ref, code, detail)`. Rules, each tested:

- Pure: bytes and manifest in, values out. No clock, no randomness, no network, no filesystem,
  no environment, no third-party import (stdlib `csv`/`json`/`decimal` only). A row is either
  translated or reported as an issue; nothing is dropped silently.
- Prices and rates are parsed from the saved text into `Decimal` exactly (`Decimal(text)`), with
  no rounding and no float. A source that wrote floats gives their shortest repr text; that is
  what is stored.
- The adapter never defaults a lineage field. An adjustment label the manifest does not state is
  `UNDECLARED` (15.2), never `RAW`.
- Output order is deterministic (file row order); a digest of the canonical output is recorded
  per load.
- An adapter never imports another adapter, `persistence` or `domain.replay`.

**Seam types in `src/marketdata/contracts.py`: kept, changed, added.** Everything below is
proposed; the existing 21 contract tests are updated in the same commit, and the module
docstring's "provisional label" notes are replaced by what is decided.

| Type | Disposition | Reason |
|---|---|---|
| `ObservationRuleError`, `DataDelayStatus`, `CorporateActionType`, `_require_*` helpers | **Kept** | no gap |
| `AdjustmentStatus` | **Changed**: add `UNDECLARED` (source did not say; also what an adapter yields when the manifest is silent) | an adapter must not be forced to choose `RAW`; PRD §11.3 forbids blindly mixing |
| `FreshnessState` | **Kept as a label set**; assignment moves to read time (below). The set may need a member for "not assessed"; **[Q]** | a state assigned at ingest would go stale |
| `Freshness` | **Changed**: add `assessed_as_of: date` and `policy_id: str` (the freshness-policy convention-set id) | a state without its reference date is not auditable |
| *new* `SourceTiming` (`source_time`, `delay_status`) | **Added** | the intrinsic, stored half of freshness |
| `Lineage` | **Changed**: add `source_id` (the registered source; `source` stays as the opaque label), `file_sha256`, `adapter_id`, `adapter_version`, `source_record_ref` (the source's own symbol/row identifier), `retrieved_at`, `usage_scope`, and optional `adjustment_anchor` (what the adjustment is anchored to, as the source states it) | PRD §11.3 and PD-0027 condition 3; `usage_scope` carries PD-0028 structurally |
| `QuoteObservation` | **Changed**: add `value_date: date` (the market's calendar date the value is for); `observed_at` becomes optional (daily files rarely carry an instant); `freshness: Freshness` becomes `timing: SourceTiming` on stored observations (read results carry `Freshness`) | a daily close is a date, not an instant; whether "price of date D" can be filled is **[Q]** |
| `FXObservation` | **Changed**: add `value_date: date`, `rate_basis: str` (opaque source label, e.g. a fixing name), same `observed_at`/`timing` change. Pairs stay exactly as published: a source's CNH stays `CNH`, EUR-based stays EUR-based; the adapter never maps or crosses | fixing, cross and CNY/CNH rules are **[Q]** |
| `CorporateActionObservation` | **Changed**: add `declared_currency` check, `source_record_ref`; same timing change. `CorporateActionType` stays {SPLIT, CASH_DIVIDEND}; a record that is neither (bonus issue, transfer of reserves, rights, spin-off, ticker change) is an `AdapterIssue(code=UNMAPPED_ACTION)`, never coerced | PRD §12.3 puts the rest later; PRD §12.2 ticker change is an identity attribute update, not a corporate-action row (15.6) |
| *new* `BenchmarkSeries` (§11.1) | **Added**: `benchmark_id`, `provider`, `points` (date, `Decimal`), `value_kind` (LEVEL or RETURN), `currency`, `lineage`, `LicensingMetadata(license_status, display_permitted, terms_ref)`. Every PD-0027 series is `INTERNAL_DEVELOPMENT_ONLY`, `display_permitted=False` | PRD §11.4: licensing is data on the contract; PD-0028: no external display |
| `ExternalIdentifiers` | **Kept** | plus an optional `source_id` scope so a vendor id is read as "vendor id *in this source's scheme*" |
| `InstrumentResolution` | **Changed**: add `status` (`RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`), `candidates: tuple[uuid]`, `matched_on`, `evidence_refs`; keep `listing_id is None` for every non-RESOLVED status and add the rule "RESOLVED implies one `listing_id`, none of the others carries one" | PD-0021 and §13.H: ambiguity is a state, not a guess |
| *new* `Reconciliation`, `FieldDifference`, `QuoteReading`/`FXReading`/`ActionReading` | **Added** (15.8) | PD-0027 condition 4 |
| *new* `FileManifest`, `MarketDataRelease`, `DataSetRef`, `AdjustmentVerification` | **Added** in `marketdata/manifest.py` (15.3, 15.4) | auditability |

### 15.2 Adapters, one per source

Each adapter lives in `src/marketdata/adapters/` and is a pure translator (15.1). **No adapter
imports its vendor's library; vendor libraries exist only in the human-run download tool
(15.4).** A source that is a library over upstream websites (AKShare) is recorded with an
`upstream_provider` and an `independence_group` in the source registry (15.3). Two files whose
upstream is the same are one source for reconciliation purposes, however many libraries fetched
them. **[J]** This matters: AKShare's functions wrap third-party sites, so "AKShare vs AKShare"
is not an independent check.

| Data kind | Primary | Independent second | Notes |
|---|---|---|---|
| CN daily quotes | AKShare | **BaoStock** | |
| HK daily quotes | AKShare | none confirmed | `SINGLE_SOURCE` is a first-class state (15.8); a yfinance adapter is written only if the human clears its terms and wants HK reconciled |
| US daily quotes | AKShare | **Alpha Vantage** (yfinance only as the fallback) | see the recommendation below |
| FX USD/HKD/CNY | ECB via Frankfurter (EUR-based) | CFETS CNY central parity as published | USD/HKD has no second published source in PD-0027; a derived-cross comparison from CFETS legs is possible and is a **[Q]** question |
| Corporate actions | AKShare and the BaoStock dividend endpoint (CN); AKShare (HK, US) | Alpha Vantage splits/dividends (US); `manual_filings` (HKEXnews, cninfo, SEC EDGAR), transcribed by a human | an AI reading a filing and typing the result is an AI as a source and is not permitted (PD-0027 condition 5); the manual adapter reads only a human-made file |
| Benchmarks | AKShare index series | BaoStock index series (CN) | price-return level proxies only; total-return series are not obtainable free (PD-0028 gap) |
| Identity | OpenFIGI saved responses | the human universe file (below) | |

Adapter list (one translator per source and data kind; format variants are chosen by
`manifest.payload_format`, not by sniffing): `akshare.quotes.{cn,hk,us}`,
`baostock.quotes.cn`, `alphavantage.quotes.us`, `akshare.actions`, `baostock.actions.cn`,
`alphavantage.actions.us`, `frankfurter.fx`, `cfets.fx` (CFETS parity as saved by the download
tool; whether it is fetched through AKShare or directly is a download-tool detail recorded in
`upstream_provider`), `akshare.benchmarks`, `baostock.benchmarks.cn`, `openfigi.identity`,
`manual_filings.actions`, `universe.identity`, and **`mock.synthetic`**.

**Recommendation 1, China second source: BaoStock over Tushare. [J]**
- BaoStock needs no key (a free anonymous login), so there is nothing to keep out of the
  repository or the model context (STATUS 16e). Tushare needs a token and a points-based quota.
- It returns raw and adjusted series with an explicit adjust flag, plus adjustment factors,
  which is exactly what the adjustment verification (STATUS 16c) needs as evidence.
- Its upstream is separate from AKShare's, so it can be an independent check **[A]**: the human
  confirms the upstream from the source's own documentation, and the registry records it.
- Cost: A-shares and some indices only (no HK, no US); its terms still need the human check.
- Tushare stays a later optional adapter if BaoStock coverage or terms disappoint; the port
  needs no change for it.

**Recommendation 2, US second source: Alpha Vantage as the default, yfinance not written
unless needed. [J]**
- PD-0027 makes yfinance the fallback because Yahoo's terms restrict this kind of access to
  personal use. Writing it first would build on the weaker legal footing and on an unofficial
  scraper whose `Close` is already split-adjusted and whose `Adj Close` is split-and-dividend
  adjusted: a trap the verification step exists to catch.
- Alpha Vantage is an official keyed API. Its limits are operational: **[A, to verify by the
  human]** about 25 calls a day on the free tier and possibly only a recent window of daily
  history (not full depth) without a paid plan. If the free tier cannot return enough history to
  reconcile, then US is covered over the window it can serve, and the rest is `SINGLE_SOURCE`.
  This is honest and shows as a state, not a failure. If that window is useless, the fallback is
  to write `yfinance.quotes` after the human clears its terms; that is a new adapter and no port
  change.
- Alpha Vantage also covers splits and dividends, giving US corporate actions a second source.

### 15.3 File-based ingestion model

**Where the files live. [J]** `data/marketdata/` at the repository root (override with
`FINWEB_MARKETDATA_DIR`), **git-ignored for payloads**, because (a) the files are large,
(b) PD-0027/PD-0028 keep them internal-only and committing vendor data to history is the kind
of redistribution PRD §4.3 warns about, and (c) git is not a content store we want rewritten.
The agent sandbox can read the directory (inside the project) while the human writes it from
outside the sandbox. **Committed:** the source registry, the release files and the manifests'
index (no payload bytes), so history records which hashes the evidence used. **Not committed:**
payload files. The human is responsible for backing them up; the content hash proves a restored
copy is the same file. A restored file with a different hash is a different file.

```
data/marketdata/
  SOURCES.json                      # registry: source_id, name, upstream_provider,
                                    #   independence_group, terms_url, terms_check
                                    #   {checked_by, checked_on, usage_scope, notes}  [H]
  files/<source_id>/<data_kind>/<YYYY-MM-DD>/<label>.<ext>            # payload, 0444, never rewritten
  files/<source_id>/<data_kind>/<YYYY-MM-DD>/<label>.<ext>.manifest.json
  releases/<release_id>.json        # MarketDataRelease; committed
  verification/<file_sha256>.<rule_id>.json   # AdjustmentVerification records; committed
  quarantine/                       # resolution exceptions and rejected rows (reports)
tests/product/fixtures/marketdata/  # committed: small hand-written synthetic files
```

**Immutability.** The download tool creates files with exclusive-create mode, refuses to
overwrite, and sets them read-only. The loader verifies the SHA-256 of the exact bytes against
the manifest on every read and refuses a mismatch with a typed error (`FILE_HASH_MISMATCH`).
A re-download is a new file with a new date and (if the source changed) a new hash. Old files
are never edited; a corrected file is a new file.

**Content hash. [F, STATUS 16b]** SHA-256 of the raw bytes; no newline or encoding
normalisation. The hash is the file's identity (`file_sha256`). The path is a human aid only.

**Lineage manifest per file** (`finweb.marketdata.file_manifest/1`, JSON, written by the tool,
never by hand; a hand-made file such as a filings transcription is registered through the same
tool's `register-file` command so it is hashed and described the same way):

| Field | Meaning |
|---|---|
| `schema`, `file_sha256`, `size_bytes`, `payload_filename`, `payload_format` | identity and format key for the adapter |
| `source_id` | key into `SOURCES.json` |
| `data_kind`, `market` | e.g. QUOTE, `CN` |
| `retrieval_time_utc` | ISO-8601 instant, set by the tool; the only clock reading in the system, and it is data |
| `retrieved_by` | `human`; the tool refuses to run otherwise (15.4) |
| `request` | the call made: function name and **whitelisted** parameters (symbol, dates, adjust flag); never keys, headers or URLs carrying a token |
| `declared_adjustment` | `RAW`, `SPLIT_ADJUSTED`, `DIVIDEND_ADJUSTED`, `TOTAL_RETURN_ADJUSTED` or `UNDECLARED`, **as the call implies**; trusted by nothing, see verification below |
| `adjustment_anchor` | what the source says the adjustment is anchored to, if anything |
| `declared_currency` | required for QUOTE and BENCHMARK; an adapter never infers currency |
| `source_identifiers` | the source's own symbol scheme and the symbols requested (e.g. `sh600519`) |
| `script` | `{name, version, script_sha256}` and `libraries` `{name: version}` (from `importlib.metadata` at run time) |
| `usage_scope` | `INTERNAL_DEVELOPMENT_ONLY` for every PD-0027 file (PD-0028) |
| `coverage` | symbols and date range requested, plus what was returned |

**Terms check gate. [H]** Before any file from a source is loaded, `SOURCES.json` must hold a
human `terms_check` for that source. The loader refuses a file whose source has none
(`SOURCE_TERMS_NOT_ATTESTED`). The mock and fixture sources are exempt because they are
synthetic. Agents have no network, so only the human can do this.

**Adjustment verification (STATUS 16c).** A declared label is never trusted. A separate record
`AdjustmentVerification(file_sha256, rule_id, status, evidence)` with `status` in {`VERIFIED`,
`CONTRADICTED`, `NOT_VERIFIABLE`} is appended by a pure checker that implements the Quant's
rule **[Q]** (comparing raw and adjusted series against corporate-action data). CP2 stores and
exposes the record; what an unverified or contradicted label does to a metric state is a CP3
decision with the Quant. Verification records are separate files so the immutable manifest never
changes.

**Releases and how a Computation Manifest cites exact files.** `MarketDataRelease`:
`{schema, name, created_for, files: [file_sha256...] (sorted), source_precedence:
[source_id...], conventions: {fx_fixing, price_of_date, reconciliation, freshness,
adjustment_verification: convention_set_id...}, release_id = sha256(canonical JSON of the rest)}`.
The release is an input chosen by a human or a script, committed, and immutable. A port is
constructed from one release, so every lookup is deterministic for that release and the
as-of date. The Computation Manifest's `market_data_snapshot_ref`, `fx_series_ref`,
`corporate_action_set_ref` and `benchmark_series_ref` (§6.2) each become a `DataSetRef`:
`{kind, release_id, consumed: [(file_sha256, adapter_id, adapter_version)...] sorted,
convention_ids, request_range}` plus its own `ref_id` (the hash of its canonical JSON). Replay
of a claim is: load the release, verify every cited hash, run the cited adapter versions, apply
the cited conventions. Normalisation is deterministic: stable ordering by `(file_sha256, row
order)`, canonical JSON with no float, a per-load `normalized_digest` recorded for the rebuild
check in 15.5.

### 15.4 The human-run download tool

- **Where.** `src/marketdata_tools/` (package `marketdata_tools`, entry
  `python -m marketdata_tools.download`). It is in `src/` because that is the engineer's write
  path; it is outside the product packages: **nothing in the product imports `marketdata_tools`**
  (import-boundary test). It imports `marketdata.manifest` only, so manifests and hashes are
  produced by the same code the loader verifies with. Alternative if the owner prefers a
  `scripts/` directory: the main session adds it to the engineer's write paths; nothing else
  changes.
- **What it does.** Subcommands: `fetch <source> <kind> ...` (calls the vendor library or
  stdlib HTTP, saves the raw response bytes unmodified, writes the manifest), `register-file`
  (hash and describe a hand-made file), `verify` (re-hash every file against its manifest),
  `probe` (tiny first run: 3 symbols per source and 5 days, to learn the real response shapes).
  It saves what the source returned (for example a DataFrame written as CSV with UTF-8 and the
  source's own column names), not a cleaned version. It writes nothing but under
  `data/marketdata/`.
- **What it needs. [H]** The vendor libraries, as an **optional dependency group that the owner
  installs, never core**: `[dependency-groups] marketdata-download = ["akshare", "baostock"]`
  (pandas, numpy and others arrive transitively, and a Python 3.12 wheel must exist for each:
  **[A]**). Alpha Vantage, Frankfurter, CFETS (if direct) and OpenFIGI are plain HTTP and use
  the standard library, so they add nothing. Core runtime stays `psycopg` only; product code
  never imports pandas (parquet is not used for the same reason). **Proposal only:** this round
  does not edit `pyproject.toml`. When the owner approves, the engineer adds the group and the
  owner runs `uv lock`. Run it in a separate environment so the sandboxed test environment is
  untouched: `UV_PROJECT_ENVIRONMENT=.venv-download uv sync --group marketdata-download`
  (the group is not a default group, so `uv sync --check --frozen` for the test environment is
  unaffected **[A]**, to be confirmed by the owner's first `uv lock`).
- **Keys (STATUS 16e).** Alpha Vantage, Tushare (if ever) and OpenFIGI (optional, for the higher
  rate limit) keys are read **only** from environment variables set by the human in their own
  terminal (optionally from the macOS Keychain via `security find-generic-password`). Never
  from a file in the repository, never a `.env` (the agents' tooling does not read them, and
  neither may we write them), never accepted as a command-line argument (it would land in shell
  history and process listings), never printed, never written into a manifest (`request` is a
  whitelist, so a key cannot leak by omission of a filter), and never present in any process an
  agent runs. A key kept in a plain file outside the repository is not recommended: the agent
  sandbox can read most of the disk, so only the process environment and the Keychain keep the
  key out of model context.
- **Agents never run it.** Four layers, none of them a control on its own: (1) the dispatch
  instructions and this plan say so; (2) the sandbox has no network, so a fetch fails anyway;
  (3) the tool refuses unless `FINWEB_HUMAN_DOWNLOAD=1` is set and stdin is a terminal (an
  agent's shell has no terminal; this is a speed bump, not a security control); (4) every
  manifest records `retrieved_by: human`, and a reviewer checks the files' presence against a
  human-confirmed run log. If the owner wants a hard control, a permission rule denying the
  command pattern is a main-session settings change.
- **Untested against the network.** The engineer cannot run the tool. Library function names
  and response columns change between versions and the engineer's memory of them may be stale.
  Therefore the tool is deliberately thin (each source about 30 lines, no transformation) and
  the first human step is `probe`, whose saved files the engineer reads before writing any
  adapter (15.10).

### 15.5 Storage: PostgreSQL projection, files remain authoritative

**Decision [J]:** store normalized observations in PostgreSQL (migrations 0009 and later, CP2c),
as an append-only projection of the files. **Files are the record; the tables are rebuildable
from them.** CP2a and CP2b do not need the database: the in-memory store builds from the same
adapters, so if PostgreSQL storage were dropped, the port, adapters and exit test stand.

Why a database at all, rather than files plus a loader:
- **CP3 needs joins and range reads.** Valuation joins positions (by `listing_id`) with prices
  and FX over date ranges across many listings. Re-parsing every file per run is slow and each
  consumer would re-implement selection.
- **Immutability is enforceable.** The same append-only trigger pattern as the ledger
  (migration 0003): no UPDATE, DELETE or TRUNCATE; the application role gets SELECT and INSERT.
  A file on disk can be edited by anyone with a shell.
- **Auditability is a foreign key.** Every observation row names its `load_id` and so its
  `file_sha256`. A claim's manifest cites a release; a release cites hashes; a hash resolves to
  a registered file and a row-level lineage.

Why not the database alone: the database would then be the only copy, and a source that changes
or vanishes would take the evidence with it (PD-0027: saved files keep CP2 reproducible). So the
rule is: **no row exists without a file; no file is edited; the projection can be rebuilt in a
scratch schema and its canonical digest compared** (a CP2c test and an operational check).

**Determinism cost and answer.** The same release and as-of date must give the same output. The
release pins which loads count; loads are immutable; resolution results are stored on the rows
at load time. A later identity correction (an attribute update, 15.6) leaves `listing_id`
unchanged, so stored rows stay valid; a correction that moves a vendor symbol between listings
needs a new load of that file and therefore a new release. No query reads "latest".

Tables (names proposed; migrations 0001-0008 are frozen, so these are new numbered files and
new `CHECKSUMS` lines; none is written now):

| Migration | Tables | Key and notes |
|---|---|---|
| 0009 | `md_source`, `md_file`, `md_load`, `md_release`, `md_release_file` | `md_file(file_sha256 PK, source_id, data_kind, retrieval_time, declared_adjustment, usage_scope, manifest jsonb)`; `md_load(load_id uuid PK, file_sha256 FK, adapter_id, adapter_version, loaded_at, row_count, issue_count, normalized_digest)`; a `(file_sha256, adapter_id, adapter_version)` unique, so re-loading is a no-op |
| 0010 | `md_quote`, `md_fx_rate`, `md_corporate_action`, `md_benchmark`, `md_benchmark_point` | `md_quote(load_id FK, listing_id FK to listing, value_date, price numeric, currency, adjustment_status, source_time, delay_status, source_record_ref)`, PK `(load_id, listing_id, value_date)`; `md_fx_rate` keyed `(load_id, base, quote, value_date, rate_basis)`; **never a ticker or FIGI column on any observation table** (PD-0021); numeric columns obey the PD-0026 bounds (below 1E30, at most 24 decimals) by CHECK |
| 0011 | `listing_identifier`, `md_resolution_exception`, `md_adjustment_verification` | see 15.6; the identifier table is temporal and append-only |
| 0012 | append-only triggers, grants | same pattern and tests as 0003/0004: pinned `search_path`, UPDATE/DELETE/TRUNCATE refused, SELECT/INSERT for `finweb_app`; the grant spec in §14.3 gains the new tables, with a negative control as in CP1D-3 |

Open item: whether `md_load` rows may be marked superseded. Proposed: no; supersession is a new
release, so no table is ever updated.

### 15.6 Instrument resolution

**Mechanism [F, PD-0021, §13.C, §13.H].** The key is `listing_id`. `ExternalIdentifiers` (FIGI,
MIC, ticker, vendor id) are resolution attributes. An adapter emits unresolved observations; a
`Resolver` maps them; ingestion stores the resolved `listing_id`.

**Matching order (data, deterministic, evidence recorded).** (1) FIGI exact match. (2) MIC plus
ticker, valid on the observation's `value_date` (symbol history, below). (3) `(source_id,
vendor_id)` from a mapping asserted for that source. A match at a lower step is not accepted
when a higher step is present and disagrees. Each result records `matched_on` and the evidence
rows.

**States, never a guess.**

| Status | When | Effect |
|---|---|---|
| `RESOLVED` | exactly one listing, no disagreement between the steps that matched | rows load |
| `UNRESOLVED` | no candidate | rows are not loaded; one `md_resolution_exception` per distinct identifier set |
| `AMBIGUOUS` | more than one candidate at the matching step (a ticker reused across venues, or a vendor id mapping to two listings) | exception; not loaded; candidates listed |
| `CONFLICT` | steps disagree (the ticker and MIC point to listing A, the FIGI to listing B), or the file asserts a FIGI different from the stored one | exception; not loaded; nothing is overwritten |

An exception is a row (and a report in `quarantine/`) that a human resolves by writing an
**identity file** (15.2: the `universe.identity` format), which is a new file and flows through
the same hashing, adapter and append-only path. An unresolved observation never reaches
analytics, and its count is visible in the load summary, so missing data shows as missing.

**Creation only when resolution fails.** Price, FX and corporate-action ingestion **never**
creates identity. Creation is a separate explicit step, `register_instruments(identity_file)`,
which, for each entry that resolves to `UNRESOLVED`, creates `Issuer`, `Instrument` and `Listing`
with new internal ids. Creation needs the issuer name, security type (`COMMON_STOCK` or `ETF`),
MIC, ticker and trading currency; price files do not carry them, so they come from the human
universe file and, where wanted, OpenFIGI saved responses. An entry that resolves is not
created; an `AMBIGUOUS` or `CONFLICT` entry is reported, not created. There is no writer for
these entities in CP1 (migration 0001 only defines the tables), so an `IdentityRegistry` write
path is a CP2c deliverable.

**Symbol changes and corrections are attribute updates (PRD §12.2, PD-0021).** A temporal,
append-only `listing_identifier(listing_id, scheme, value, valid_from, valid_to, asserted_by,
source_file_sha256)` records every identifier a listing has had (FIGI, `TICKER`, vendor id per
source). A ticker change closes the old row and opens a new one; `listing.ticker` keeps the
current value as a denormalised convenience. `listing_id` never changes and no ledger row, no
`md_*` row and no manifest is touched. A change goes through an identity file with a source
reference, never inferred from a price series. **Caveat [A, STATUS 16d]:** free sources report
ticker changes and delistings poorly; see 15.11.

**Ledger interaction.** A ledger event already holds a `listing_id`. If a human enters a trade
for a symbol that has no listing, the ledger path is unchanged (CP1); the market-data side would
report that listing as having no observations (`NOT_IN_RELEASE`), not create one.

### 15.7 Historical FX through the port, and the CP3 hand-off

- **Shape.** `fx_series` returns observations for the pairs the sources actually publish, dated
  (`value_date`), with `rate_basis`, `Lineage` and `SourceTiming`. Nothing is derived, inverted
  or crossed inside the port or an adapter. The ECB file is EUR-based; CFETS publishes CNY
  central parity against selected currencies; CNH and CNY remain distinct codes if a source
  publishes both.
- **Derivation.** A pure function `fx.rate_for(port, from_ccy, to_ccy, as_of, rule)` applies the
  Quant's fixing, cross and CNY/CNH rules **[Q]** through an injected `rule` object, and returns
  `FXRateResult(rate, legs, rule_id)` or an outcome (`NO_OBSERVATION`, `NO_PATH`, ...). The
  result always carries the exact `FXObservation` legs, so a derived rate is as auditable as a
  published one. No derivation rule is written until the Quant's document exists.
- **Unavailable FX** maps to `MISSING_FX_HISTORY` or `INSUFFICIENT_DATA` at the consumer, per
  §13.E. The port never falls back to a later or latest rate without that being the injected
  rule's explicit, labelled behaviour.
- **CP3 consumption (§13.E preserved).** The ledger and `reconstruct` stay native-currency; no
  rate enters them. CP3's valuation reads `ReplayedState` (native positions and cash) and calls
  `MarketDataPort` for quotes and `fx.rate_for` for each `(currency, valuation date)` and each
  cash-flow date (OI-1 cost basis at the transaction-date rate, STATUS item 11). CP3 owns
  money rounding (OI-8) and the arithmetic; CP2 supplies observations plus the data
  shape. A `DataSetRef` for the FX series goes into the Computation Manifest's `fx_series_ref`.
- **Live FX (PD-0028 gap).** The ECB publishes once a day. Snapshot FX is therefore a dated
  observation whose freshness is assessed, never labelled live.

### 15.8 Two-source disagreement and freshness: data shape only

**Readings, not a chosen value.** Each source's value is carried as a reading with its lineage:

```
QuoteReading(source_id, observation, load_id)        # same for FX and actions
Reconciliation(
    state,                    # SINGLE_SOURCE | AGREE | DISAGREE | NOT_COMPARABLE   (names provisional) [Q]
    readings,                 # every reading from the release, sorted by source precedence
    differences,              # FieldDifference(field, by_source, absolute, relative), exact Decimal
    rule_id,                  # convention-set id of the reconciliation rule [Q]
    tolerance_ref,            # id of the tolerance used, from the Quant's set; engineer code holds no tolerance
    selected_source,          # Optional; set only when the rule says which reading is used
    selection_basis,          # the rule's stated basis; empty if none selected
)
```
Rules that are structural, not methodological: a `DISAGREE` is never reduced to a number
silently; the lookup returns it with all readings; "selected" exists only when the injected rule
chooses one and says why; `NOT_COMPARABLE` is returned when the two readings differ in
`adjustment_status` or `currency` (blindly mixing is forbidden by PRD §11.3). Two readings from
the same `independence_group` count as one source, so the state is `SINGLE_SOURCE`. A same-source
difference between two retrievals (a revision) is reported as a `SOURCE_REVISION` difference
within one source, not as a cross-source disagreement. The tolerance values, the rule for
selecting one value, and what the state does to a metric are the Quant's.

**Freshness.** Stored: `SourceTiming` (`source_time`, `delay_status`), intrinsic to the file.
Assigned at read time: `assess_freshness(timing, as_of, policy) -> Freshness`, a pure function
where `policy` is the Quant's threshold set **[Q]** (and whether age is in calendar days or
trading days; a trading calendar source is an open question, 15.11). Until the Quant's policy is
implemented, CP2a ships a policy that returns `UNKNOWN` for everything: honest, and it
infers no threshold (the module docstring forbids inferring one). `Freshness` records
`assessed_as_of` and `policy_id` so a state is reproducible. `END_OF_DAY` versus `DELAYED` versus
`LIVE` is what the source declares, and is `UNKNOWN` when it does not.

### 15.9 The CP2 exit test

**Consumer under test (business logic).** `marketdata/consumption.py::assemble_valuation_inputs(
port, resolver, state: ReplayedState, as_of, reporting_currency, conventions) ->
ValuationInputs`. For each held listing it collects the quote lookup, and for each currency other
than the reporting currency the FX lookup, each with outcome, freshness, reconciliation and
consumed files; it also returns the aggregate `consumed_files()`. It performs no valuation
arithmetic and chooses no convention (CP3 builds valuation on it). It is the first real
analytics-facing consumer of the port and exactly the "same internal analytics contract". It
depends on `MarketDataPort`, `domain.replay` results and the injected convention objects only.

**Fixtures.** A hand-written synthetic set in `tests/product/fixtures/marketdata/`, no vendor
data: three listings (one per market: US USD, HK HKD, CN CNY), a short daily window with one
SPLIT and one CASH_DIVIDEND, FX for USD/HKD/CNY, one benchmark. The same logical facts are
written out three ways: (1) in the AKShare-shaped file format, (2) in the BaoStock-shaped
format for the CN listing and the Alpha Vantage-shaped format for the US listing, (3) the mock's
canonical synthetic format. Format shapes are copied from what the human `probe` returns
(structure only, invented numbers). **Expected values are authored by the `quant-analyst`**
(derived independently, not from code output), including a row where two sources disagree and
a row with an adjustment label mismatch. Optionally the P1/P2 positions of the CP1 golden fixture
supply the `ReplayedState`, tying CP1 to CP2.

**The test.** One test body, written once, parametrised over three ports: (A) AKShare-fixture
adapters, (B) BaoStock plus Alpha Vantage plus Frankfurter/CFETS adapters, (C) the mock. Each
port is built through the full real path: files, hash verification, adapter, resolver, store,
release. The body calls only `assemble_valuation_inputs`.

**What proves "without business-logic change".**
1. **Same code.** The test pins the SHA-256 of `consumption.py`, `port.py` and `fx.py` source
   text (as `FIXTURE_PINS` pins the CP1 fixture); the pin is computed before and after adapters
   are added. The consumer file is not edited when adapters are added.
2. **No adapter in the dependency.** A static AST scan fails the build if `consumption.py`,
   `fx.py`, `reconcile.py`, `freshness.py`, `domain` or any future analytics module imports
   `marketdata.adapters` or a vendor name. Adapters may import only `contracts`, `manifest` and
   stdlib.
3. **Same output.** For data that is the same fact in all three, the canonical JSON of the
   consumer's value part (outcome, price, currency, rate, reconciliation state) is
   byte-identical across ports; only the lineage part differs, and it lists the right file
   hashes and adapter ids. Where the sources disagree, the output differs only in the flagged
   `Reconciliation` fields, as the Quant's fixture expects.
4. **A fourth adapter needs no consumer change.** A test-local adapter for an invented format is
   registered and run through the same body without any production edit.
5. **Negative controls.** An adapter that emits a vendor-shaped extra field, a float, a naive
   timestamp, a ticker as key, or an adjustment label it was not given is refused at contract
   construction or as an `AdapterIssue`; a file with a wrong hash is refused; a file from a
   source with no terms attestation is refused; a stale release id in a manifest is detected.
6. **Determinism.** The consumer output is byte-identical across runs, across processes with
   different `PYTHONHASHSEED`, and against a store rebuilt from the same files (and, in CP2c, in
   PostgreSQL as `finweb_app`).

**Two levels of exit evidence, for the PM to confirm.** (a) *Technical exit*: the fixture test
above; it needs no download. (b) *Real-data evidence for HG2* (PD-0027 condition 4): an opt-in
test and a reconciliation report over the human-downloaded files, giving counts of agreeing,
disagreeing and single-source observations and the unresolved identities. It is not a blocking
criterion unless the PM says so, because it depends on the human run and on source availability.

### 15.10 Sequencing: small increments

| Increment | Contents | Needs from the human | Needs from the Quant |
|---|---|---|---|
| **CP2a: contracts, port, mock, file model** | contract changes (15.1) with updated tests; `port.py`; `manifest.py` (`FileManifest`, hashing, `MarketDataRelease`, `DataSetRef`); `FileStore` verification; in-memory store; `mock.synthetic` adapter; resolver protocols with an in-memory resolver; freshness policy returning `UNKNOWN`; reconcile and FX plug-in protocols; the import-boundary tests; the download tool v0 (written, untested against the network) | nothing to start; **owner approval** of the optional dependency group (a `pyproject.toml` proposal) so `uv lock` can run | nothing (all plug points are protocols) |
| *Human gate between* | terms-of-use check per source; install the download group; run `probe`; keep the key in the environment | terms check [H]; `probe` run [H] | |
| **CP2b: file adapters, ingestion** | adapters from the real `probe` shapes; ingestion pipeline (verify, translate, resolve, quarantine, summary); `AdapterIssue` reporting; synthetic shape fixtures; load summary and normalized digest | the `probe` files; any source whose terms fail is dropped | the adjustment-verification rule and adjustment labelling ([Q], STATUS 16c) so verification records can be produced; price-of-date for the lookup rule if the fixtures need a fill |
| *Human gate between* | the full download run for the chosen symbol and date set; cut a release | full `fetch` run [H] | the symbol set is the owner's (for HG2 it is probably the CP1 golden listings plus benchmarks) |
| **CP2c: resolution, FX, storage, exit test** | `IdentityRegistry`, identity-file ingestion, symbol history; FX derivation per the Quant's conventions; reconciliation and freshness implementations; migrations 0009-0012 and the PostgreSQL store; `assemble_valuation_inputs`; the exit test of 15.9; the real-data reconciliation report | the full-run files | **the full CP2 conventions document** (FX fixing, cross rates, CNY/CNH, price-of-date, adjustment verification, two-source reconciliation, freshness thresholds, F8), plus the exit fixture's expected values |

**Proposed first increment: CP2a.** It is entirely inside the engineer's write paths, depends on
neither the human's download nor the Quant's document, and delivers the port, contracts, release
and manifest shape, the mock and the first half of the exit test (consumer plus mock plus a
hand-made second format) so the exit criterion's structure is exercised early. The one thing the
main session should schedule in parallel is the **human terms check and `probe` run**, because
CP2b cannot start without real file shapes.

### 15.11 Risks and open questions

1. **Terms of use per source [H].** Agents have no network and cannot judge terms. For each
   source (AKShare and its upstream sites, BaoStock, Alpha Vantage, Frankfurter/ECB, CFETS,
   OpenFIGI, filings sites, and Yahoo only if yfinance is considered) the human records
   whether internal development use is permitted, in `SOURCES.json`. The loader refuses an
   unattested source. If a source fails, its adapter is not used; the exit test uses synthetic
   fixtures so it is unaffected.
2. **Adapters are written against shapes the engineer cannot see.** Mitigated by the `probe`
   run before CP2b. Residual risk: a vendor changes columns later. The saved files and pinned
   adapter versions keep old evidence reproducible; a new shape is a new `payload_format` or
   adapter version.
3. **Weak ticker-change and delisting coverage [STATUS 16d].** Free sources do not reliably
   report symbol changes, delistings or the history of a code. Consequences: a delisted
   listing may have prices that stop with no corporate-action record; a re-used ticker can
   attach to the wrong listing if matching ignored dates (hence the date-valid `TICKER` rows
   and the `AMBIGUOUS` state). Position: the platform does not infer a delisting or a symbol
   change; `is_active` and symbol history change only by an identity file with a source.
   Rows that stop appearing are visible as `NO_OBSERVATION` plus freshness, not explained away.
4. **F8: splits from the ledger or from a corporate-action feed [Q; STATUS 12].** The port
   carries corporate-action observations with per-source readings; whether the position
   engine applies a split from the ledger (`SPLIT` event, CP1) or from the feed is unresolved.
   CP2 delivers the feed shape and its reconciliation and does not wire it into replay. A
   disagreement between a feed split and a ledger `SPLIT` is a state to report, and the rule
   is the Quant's. Free-source split data is the weakest part (point 3), which argues against
   an automatic feed-driven position change in V1; this is advice, not a decision.
5. **Alpha Vantage free-tier depth and rate limit [A, H].** If daily history is limited,
   US reconciliation covers only that window; this is shown as `SINGLE_SOURCE` outside it. If
   it is unusable, the yfinance fallback needs a terms decision first.
6. **HK has no confirmed second source.** `SINGLE_SOURCE` is the honest result. HG2's
   reconciliation evidence for HK will be thin; the owner should know before HG2.
7. **Adjusted series are anchored to the retrieval date.** A forward-adjusted series fetched in
   January differs from one fetched in June if an action happened between. Hence
   `retrieval_time`, `adjustment_anchor` and the release pin: series from different retrievals
   are never mixed in one release unless the Quant's rule says so.
8. **Float-origin text.** Sources that computed in binary floats produce long decimals; the
   stored value is the exact decimal text received. Whether to round, and to what, is a
   convention (OI-8 related) for the Quant; the adapter does not round.
9. **A trading calendar.** Age-in-trading-days needs holiday calendars for NYSE, HKEX, SSE and
   SZSE. Source: a human-downloaded calendar file per exchange, as a `CALENDAR` data kind, or
   the Quant chooses calendar days. Open until the freshness convention is read.
10. **Mapping non-terminating corporate-action forms.** Mainland bonus shares and
    capitalisation-of-reserves records are not a pure split and are not mapped (they become
    `UNMAPPED_ACTION` issues). Whether CP2 needs them is a PRD §12.2 scope question for the PM.
11. **Conflict with the B0b plan [flag].** `PHASE_B0B_IMPLEMENTATION_PLAN.md` §17 says the CP2a
    fixture corpus should be "captured from a real provider response ... committed as data".
    PD-0027/PD-0028 make vendor data internal-only; committing it is the redistribution risk
    PRD §4.3 warns about. This plan commits only hand-written synthetic files that imitate
    structure. The main session should confirm this reading.
12. **`.gitignore` and settings changes are main-session actions.** Ignore `data/marketdata/files/`,
    `data/marketdata/quarantine/` and `.venv-download/`; commit `SOURCES.json`, releases and
    verification records. The engineer cannot write those paths.
13. **Selection precedence is a data choice.** PD-0027 names AKShare as primary; that is recorded
    in the release's `source_precedence`. Whether precedence decides a value when sources
    disagree is the reconciliation rule's business **[Q]**, not the port's.
14. **A database that holds vendor data is not "internal" by default.** The development
    database stays on the owner's machine. Any shared or deployed instance, demo or page that
    shows a PD-0027 value is excluded by PD-0028; `usage_scope` travels on every row and every
    `DataSetRef` so a later display layer has something to refuse on.
15. **No quantity of free data closes OQ-04b.** Nothing in CP2 is a vendor choice. A licensed
    vendor is a new adapter and a new release, with display rights as `LicensingMetadata`.

### 15.12 Decisions made where the contracts did not cover (engineer choices for review)

- Files are the record, PostgreSQL a derived projection, with an in-memory store as the
  fallback and the base for CP2a/CP2b.
- A `MarketDataRelease` is the pin; no query reads "latest".
- Port bound to a release; read results are typed outcomes, never `None` or exceptions for
  missing data.
- Freshness stored as `SourceTiming`, assessed at read time; default policy `UNKNOWN`.
- Resolution matching order and the four statuses; identity creation only in an explicit
  registration step from a human file, never during price ingestion.
- Payload files not in git; synthetic hand-written fixtures in git.
- Download tool in `src/marketdata_tools/`, optional dependency group, keys only from the
  environment or Keychain.
- BaoStock over Tushare; Alpha Vantage over yfinance, with yfinance written only on need and
  after a terms decision.
- An adapter yields `UNDECLARED` rather than guessing `RAW`; never infers currency; never
  crosses, inverts or maps CNY/CNH.

### 15.13 CP2a as built, and alignment with `market-data/1.0` (engineer; 2026-10-01; not yet reviewed)

Where this subsection differs from §15.1-§15.12 it supersedes them: those were written before
the Quant's conventions (`methodology/CP2_MARKET_DATA_CONVENTIONS.md`), PD-0029 and PD-0030.

**Code.** `src/marketdata/`: `contracts.py` (changed), `canonical.py`, `manifest.py`, `files.py`,
`port.py`, `conventions.py`, `store.py`, `resolver.py`, `ingest.py`, `consumption.py`,
`adapters/{base,mock}.py`; `src/marketdata_tools/download.py` (human-run, untested against the
network); `product_contract` gains the two PD-0030 reason codes. Tests: `test_marketdata_*.py`
and the shared `marketdata_testkit.py` (synthetic data only).

**Findings MD1-MD8 against the contracts.**

| Finding | Done in CP2a |
|---|---|
| MD1 freshness at read time | observations store `SourceTiming` only; `Freshness` carries `assessed_as_of` and `policy_id`; `FreshnessPolicy` is injected; placeholder returns UNKNOWN |
| MD2 cross is not a rounded Decimal | `ExactRatioRate` holds the two same-date legs and gives the exact `Fraction`; `FXLookup.rate` is a `Fraction`; legs stay as readings; the placeholder FX rule does NOT derive crosses (CP2b/CP2c) |
| MD3 lineage | `Lineage` gains upstream, independence group, adjustment method, anchor, `label_status` (None = not yet tested), precision profile id, verbatim number text, plus the file hash, adapter id/version, retrieval time, usage scope; reconciliation status and the date used live on the resolved lookup (`date_used`, `missed_count`, `Reconciliation`), because they belong to (datum, as-of), not to the stored observation |
| MD4 quotes | `value_date` is the session date (property `session_date`); `volume` stored; `QuoteObservation.is_print` is "volume reported and > 0"; `price_kind` defaults to `SOURCE_CLOSE` (official-ness is never assumed). Not decided: admissibility of a no-volume source as a valuation source (CP2b/c) |
| MD5 corporate actions | `effective_date` is documented as the ex-date; `pay_date`, `record_date`, `paid_currency`, `issuer_fx_rate`; types SPLIT, CASH_DIVIDEND, SYMBOL_CHANGE, UNSUPPORTED (stored, flagged); a dividend without a pay date is refused as a row issue |
| MD6 ticker history | `InMemoryIdentityRegistry`: temporal identifier rows; `change_ticker` is an attribute update; dated resolution (Example 7-A holds). The FIGI-equality test (Ruling 7.2 point 3) is NOT implemented (CP2c, with OpenFIGI files) |
| MD7/MD8 | no change; every PD-0027 file declares END_OF_DAY |
| Ruling 0.1 | `MarketDataRelease.from_manifests` raises `TwoVintagesError`; the same check runs on the loaded data in `build_in_memory_market_data`; the series key is (source, subject, adjustment status, anchor). A release has no other supported builder |
| Ruling 4.3 names | `ReconciliationStatus` = CORROBORATED, SINGLE_SOURCE, DISAGREEMENT, IMPLAUSIBLE, RESOLVED_BY_EVIDENCE. `Reconciliation.status` is Optional: None = "not assessed", which the placeholder returns when several independent sources report (assessing needs the declared precision profiles, Ruling 4.2). A DISAGREEMENT/IMPLAUSIBLE datum cannot carry a selected source |
| `market-data/1.0` recorded | `CONVENTION_SET_ID` in `MarketDataRelease` and `DataSetRef`; `ConventionSet.ids()` also lists each rule id and `is_conformant` is False while any `placeholder/...` is injected; every `ValuationInputs` says so |

**Placeholders left for the Quant's rules (to be replaced in CP2b/CP2c; all in
`marketdata/conventions.py`, listed in `PLACEHOLDER_IDS`).**
1. `placeholder/freshness-unassessed/0`: always UNKNOWN. Real rule: Ruling 5.2 (needs `C_m`, `C_ECB`
   calendar files as `DataKind.CALENDAR` members of the release; the kind exists, no loader yet).
2. `placeholder/price-of-date-exact/0`: exact-date reading only. Real rule: Rulings 2.1-2.2, 5.2
   (session lookup `s(D)`, print rule, no sibling substitution, `missed_count`).
3. `placeholder/reconciliation-structural/0`: SINGLE_SOURCE or not assessed. Real rule: Rulings
   4.2-4.3 and 4.5 (precision profiles, CORROBORATED/DISAGREEMENT, bands of Ruling 1.5,
   `RESOLVED_BY_EVIDENCE` from a human `DataKind.RESOLUTION_RECORD` file).
4. `placeholder/fx-published-pair-exact/0`: the published pair on the exact date. Real rule:
   Rulings 1.1, 1.3, 1.6 (EUR crosses as `ExactRatioRate`, carry-forward over non-fixing days,
   missed-fixing count, 14:15 Europe/Berlin `observed_at`).
Also deferred and not stubbed: label tests V0-V3 (they set `Lineage.label_status`), number
normalization of Ruling 2.4 (CP2b, in each real adapter, with the verbatim text kept in lineage),
the FIGI-equality check, per-source precision profiles (declared in the CP2b tech-plan update
once real file shapes exist).

**OD-1 (PD-0030 §1, done).** `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` are in `ReasonCode`
and in `MetricResult`'s coupled set (non-AVAILABLE required). Nothing in `marketdata` emits a
`MetricResult` or names a `ReasonCode` (a test enforces it); mapping a lookup outcome to
`(sufficiency, reason)` is the CP3 consumer's job per Ruling 4.4 (price DISAGREEMENT ->
`INSUFFICIENT_DATA` + `SOURCE_CONFLICT`; no print at all -> `MISSING_PRICE_HISTORY`).

**OD-3 (done).** CNH stays strict: `CurrencyCode("CNH")` is distinct from CNY, no rule maps one
to the other, and a test shows a CNH lookup returns `NOT_IN_RELEASE` while CNY data exists.

**F8-B (PD-0030 §2): how it lands, in a later increment (CP2c or after); NOT built.** Until
then F8-A applies: the port returns split readings and nothing applies them; a test pins that
`marketdata` imports no persistence and no ledger append.
- *Where.* A separate application service outside the market-data layer (it needs both the port
  and the ledger store), `corporate_actions_service`, so `marketdata` stays free of persistence.
  It reads corroborated SPLIT readings (feed record and filing agree, ex-date equal, ratio equal
  as an exact rational: Ruling 4.5), compares them with the replayed ledger, and appends only
  when the position held units before the ex-date and no live `SPLIT` exists for that position
  and ex-date.
- *Append path.* The existing `append` in `persistence/ledger_store.py`, through the normal
  guards: idempotent on `(account, source_reference)`, one live split per position per ex-date
  (migration 0007), reversible with `REVERSAL`, never an update.
- *Provenance.* `source_reference` is a deterministic string that encodes the evidence: a fixed
  prefix, the feed record's file hash and row reference, the filing's file hash and reference,
  and the `release_id` (and so the convention set). A user-entered event has none of that prefix,
  so the two are distinguishable. Because the key is derived from the evidence, re-running with
  the same evidence is the idempotent no-op; new evidence with the same ex-date and ratio does
  not create a second split (migration 0007 refuses it, and the service checks first). A field
  limit on `source_reference` may force storing a hash of the evidence with the full list in a
  market-data-side record: to be checked against `LedgerEvent` before CP2c.
- *Never append when:* feed and filing disagree or only one exists (flag, F8-A); the ledger
  already holds a SPLIT for that position and ex-date with another ratio or date (flag, suppress
  valuation for the affected dates per `market-data/1.0` §6); the position is not held before
  the ex-date; the series that corroborates it is itself `CONTRADICTED`/`DISAGREEMENT`.
- *Files touched later:* a new service module, possibly one read-only SQL helper in
  `persistence`, new tests including a DB test as `finweb_app` (it needs the existing grants
  only: SELECT/INSERT on `ledger_event`). No migration is expected.

**Engineer choices in CP2a the contracts did not fix (for review).**
- `value_date` is the field name for both session and fixing dates, with `session_date` and
  `fixing_date` properties, to keep one generic date field on shared helper code.
- The consumer returns `value_obj()` (facts only) and `lineage_obj()` (provenance) separately, so
  "same facts from different adapters" is a byte comparison.
- The terms-of-use gate sits in the loader (`require_attested`), not in the adapter; a synthetic
  source is exempt, and a file is `SYNTHETIC_TEST` if and only if its source is synthetic.
- Ingestion, not the adapter, sets upstream and independence group (they come from the registry).
- Nothing selects a source by precedence; the release records it as data only.
- The consumer's "first half" exit evidence uses test-local adapters for two invented formats
  plus one novel adapter; the real source formats wait for the human `probe` run (CP2b).
- No pinned hash of the consumer source is committed (it would block legitimate CP2c edits); the
  test hashes the file before and after building every port instead, and the AST boundary test
  carries the structural claim.

**Download tool v0 and PD-0029.** `pyproject.toml` gains `[dependency-groups]
marketdata-download = ["akshare>=1.14,<2", "baostock>=0.8.9,<0.9"]`. Bounds: akshare is a fast
1.x library whose function names change between minors, so a 1.x floor with the next major as the
cap; baostock has had one stable 0.8.x line, so it is capped at the next minor. `uv.lock` is not
edited; the owner relocks.

### 15.14 CP2b first adapters (engineer; 2026-10-01; not yet reviewed)

Adapters written from the real probe files (tests use synthetic files of the same structure):
`akshare.cn.quotes`, `akshare_sina.{hk,us}.quotes`, `frankfurter.ecb.fx` (EUR-based as published,
`observed_at` 14:15 Europe/Berlin, a rebased or scaled payload refused), `openfigi.identity`
(`IdentityAssertion` evidence: matches existing identity only, never creates it). Precision is
data in `marketdata/precision.py`: Ruling 2.4 (US 4, HK 3, CN 3 decimals, 1e-9 tolerance) plus ONE
flagged placeholder, `placeholder/precision/akshare_sina.hk/0` (tolerance 1e-6), because Sina HK
prints float32-style artifacts (474.20001) that the 1e-9 tolerance rejects. No tick table is
implemented. Volume units recorded in the adapters: Eastmoney A-share lots of 100 (inferred),
Sina HK/US shares (HK evidenced by 成交额/(收盘×成交量) = 1.00; US by recollection). Needed from the
Quant: the Sina HK tolerance (or a tick-grid rule), declared per-source decimals for the Ruling
4.2 bound, and a ruling on the subtractive-looking qfq adjustment seen in the first Eastmoney qfq
file. Tool v0.1.1: one request per step, a pause between steps, EXISTS skip, throttling hint for
Eastmoney disconnects, a Sina CN route (`stock_zh_a_daily`).

### 15.15 CP2b aligned to `market-data/1.1` (engineer; 2026-10-01; not yet reviewed)

Supersedes §15.14's precision paragraph (the 1.0 fixed-decimal rounding and the
`placeholder/precision/akshare_sina.hk/0` profile are gone). Convention set recorded everywhere:
`market-data/1.1`.

- `marketdata/profiles.py`: Appendix A as versioned data (`market-data/1.1#profiles/1`), every entry
  with its Quant status; a TO_OBSERVE or missing profile is not admitted (ingest refuses a real,
  non-synthetic QUOTE/FX source). `marketdata/precision.py`: Ruling 2.4 (shortest round trip in the
  declared format, `max_dp` validation, float32 recoverability `ulp < 10^-dp`, not-recovered values
  kept with a half-ulp bound and never used, per-file float32 fingerprint check failing closed) and
  Ruling 2.6 (median turnover unit check). `adapters/daily_csv.py` is the shared rule set (row
  ordering 4.6(2), 涨跌额 check 4.6(3), vendor-derived columns never read).
- Ruling 2.5 is structural: a vendor-ADJUSTED row is an `AdjustedQuote` (not a `QuoteObservation`,
  not a `SourceReading`), reachable only through `store.adjusted_series` (`VerificationPort`), never
  through `MarketDataPort` or the consumer (boundary test). Its label is (status, method, anchor,
  vintage); the method is set only by `verification.verify_adjustment_v2` (affine fit; event check
  only where confirmed events are supplied; none => UNVERIFIABLE).
- `reconciliation.Market11Reconciler` replaces the placeholder: upstream independence, 4.2 bound
  (0 for recovered values), statuses of 4.3, primary order by market (A.5, data), the 4.6 shared
  library safeguards, no winner by order/recency/majority. `states.py` maps outcomes to
  (sufficiency, reason) per 4.4, the only module naming `SOURCE_CONFLICT` / `MISSING_PRICE_HISTORY`.
- Still placeholders: freshness, price of date, FX (no crossing, carry-forward or calendars).
- Judgment calls for the Quant: V2's per-row bound is an input (a half unit of the market's
  `max_dp` reproduces Example 3-C); CN `max_dp` defaults to the A_SHARE value (2, MEMORY) unless the
  manifest request carries `security_class`; the 8-digit float32 signature misfires on integer
  volumes of 8+ digits, so integral fields use the spacing test of A.4(2).

### 15.16 CP2c-1 as built: terms gate, Alpha Vantage, ECB-direct, calendars, and the `market-data/1.2` rules (engineer; 2026-10-01; not yet reviewed)

Convention set recorded everywhere: **`market-data/1.2`** (the Quant issued it while this increment was
under way; every 1.1 behaviour below was re-read against it). Supersedes the "still placeholders" line of
§15.15 and the V2-bound judgment call (corrected by 1.2 §9A #1). Not built: the PostgreSQL store, F8-B and the
full exit test (CP2c-2).

**1. Download-time terms gate** (`src/marketdata_tools/download.py`, tool v0.2.0). Before any request,
`probe` and `fetch` read the committed `SOURCES.json` and apply the owner's recorded verdict
(`terms_refusal`): no `terms_check`, a negative check, an unknown source and an unreadable registry all
refuse (fail closed). `probe` prints `REFUSED (terms: PD-0031/PD-0032) <step>: <reason>` for such a step, ahead
of a missing-key skip and of an existing-file skip, makes no request and is not a failure; `fetch` raises
`TermsRefusedError` (exit 2) with the same prefix. `register-file` and `verify` are not gated
(`register-file` gains `--identifiers`, so a calendar file's subject is part of its series key). The gate is
injectable (`gate=`) for tests. The registry is read at the start of the run; the tool never edits it.

**2. Alpha Vantage `alphavantage.us.quotes`** (`adapters/alphavantage.py`, over the shared
`daily_csv`). Profile transcribed from 1.2 A.3 / Example A-1 (status OBSERVED; the placeholder is gone): close
TEXT_DECIMAL with 4 delivered decimals and the US grid check; open/high/low TEXT_DECIMAL, not grid-checked, used
only in the row check; volume integral SHARE, DECLARED_UNVERIFIED; rows newest first (the parser now sorts every
daily file by date and assumes no order); upstream and independence group `alphavantage`. The real manifest says
`UNDECLARED`; the profile (`call_adjustment`, MEMORY) documents `TIME_SERIES_DAILY` as as-traded, so an UNDECLARED
manifest of that call is read as RAW and any other function stays verification-only. Ingestion sets every RAW quote
series' label status to UNVERIFIABLE (Test V1 needs a decisive corroborated split, none is in M). Read-only smoke
check of the real admitted file: 100 quotes, 0 issues, all closes recovered, RAW. Tests use synthetic copies only.

**3. ECB-direct `ecb.eurofxref.fx`** (`adapters/ecb_eurofxref.py`; tool route `fetch --source ecb_eurofxref`).
Reads the ECB's own `eurofxref-hist` CSV (`Date,USD,JPY,...,`; newest first; trailing comma; `N/A`), EUR-based,
stored exactly as the published text, `observed_at` and `source_time` 14:15 Europe/Berlin. The format is RECALLED
(profile status MEMORY): no real file has been seen, so the adapter is tested on synthetic data only and the first
real file must be profiled by A.4. The saved bytes are exactly the ECB's (a ZIP is unpacked to its single CSV);
the manifest's `source_identifiers` and `request` pairs `read_start`/`read_end` declare the window the adapter
translates. **SOURCES.json entry the owner must add and attest** (this session did not edit the file):

    {"source_id": "ecb.eurofxref",
     "name": "ECB euro foreign exchange reference rates (the ECB's own eurofxref-hist file)",
     "upstream_provider": "European Central Bank",
     "independence_group": "ecb",
     "terms_url": "https://www.ecb.europa.eu/home/disclaimer/html/index.en.html",
     "terms_check": null}

with, once the owner has read the terms, `"terms_check": {"checked_by": ..., "checked_on": ...,
"permits_internal_development_use": true, "notes": "ECB: reproduction permitted provided the source is
acknowledged; credit the ECB wherever rates appear (PD-0031's reading for frankfurter.ecb). Market-data/1.2
Ruling 1.1a."}`. Calendars need one entry too, because the loader attests every file's source:
`{"source_id": "calendar.manual", "name": "Hand-made calendar files", "upstream_provider": "the project owner,
from the publishers' notices", "independence_group": "calendar", "terms_url": null, "terms_check": null}` and an
owner attestation that the files are self-made from public notices.

**4. Calendar file format** (`adapters/calendar_file.py`; `finweb.marketdata.calendar/1`; payload format
`finweb_calendar_json/1`; source `calendar.manual`; kind `CALENDAR`). One JSON file per calendar, hand-made, never
derived from a price or rate file, registered like any file:

    python -m marketdata_tools.download register-file --path cal.json --source calendar.manual \
        --kind CALENDAR --format finweb_calendar_json/1 --adjustment RAW --label NYSE_2026 \
        --ext json --identifiers NYSE_SESSIONS

Keys (all required; an unknown key refuses the file): `schema`; `calendar_id`; `kind` (`EXCHANGE_SESSIONS` |
`ECB_FIXINGS`); `applies_to` (the MICs governed, or `["ECB"]`); `timezone` (IANA; must equal the Ruling 2.2 zone
of every MIC); `coverage` `{from, to}` (one contiguous closed interval); `dates` (explicit sorted list of actual
session or fixing dates inside the coverage; never a weekday rule); `actual_through`; `close` `{default,
overrides:[{date,time}]}` (exchange only) or `fixing` `{time: "14:15", publication: "16:00"}` (ECB only; a
different time is refused as a convention change); `evidence` (publisher reference), `prepared_by`,
`prepared_on`, `version`. The loader computes the content hash and verifies it on every read; a second file with
one `calendar_id` is `TwoVintagesError`. Inside the coverage a date is a session iff listed; a MIC governed by
zero or several calendars, and any interval not wholly inside the coverage, cannot be counted. A real file is made
by the human; committed tests use synthetic calendars with invented dates and the evidence text "synthetic: not a
real holiday list".

**5. Rules** (`marketdata/market11.py`, `calendars.py`, `states.py`; `market11_conventions(calendars)` is the
conforming set, `is_conformant` True). The `placeholder/...` classes remain only as injectable stand-ins for the
mechanics tests; no product path builds them.
- *Freshness* (5.2, 1.6): missed = sessions (fixing days) `d` of the governing calendar with `last_print < d <= D`;
  0 CURRENT; 1 STALE (AVAILABLE + STALE_DATA); 2-4 STALE (LIMITED + STALE_DATA); 5 or more: the number is withheld
  (price: INSUFFICIENT_DATA + STALE_DATA; FX: INSUFFICIENT_DATA + MISSING_FX_HISTORY). A count that cannot be made
  is UNKNOWN, the number is withheld and the state has no reason code; the cause `CALENDAR_COVERAGE_GAP` (calendar
  and uncovered dates) goes to lineage; `COUNTED_PAST_ACTUAL_THROUGH` is noted with no state effect; an empty
  interval (print dated D) needs no calendar. Thresholds are the named constants `LIMITED_FROM`/`NO_VALUE_FROM`.
- *Price of date* (2.1, 2.2, 2.4 item 4a): the latest ADMISSIBLE print on or before D: RAW, volume > 0 and
  RECOVERED; the session date is the source's local label (nothing goes through UTC); an unrecovered reading is not
  a print, may confirm another source's recovered value, and its session counts as missed; no sibling substitution;
  no admissible print on or before D: `NO_HISTORY` (MISSING_PRICE_HISTORY).
- *FX* (1.1, 1.3-1.6, 1.1a): EUR-based quotes; a rate with EUR as base is the published quote, with EUR as quote
  the labelled exact inverse; any other pair is the exact ratio `x_q / x_b` of two SAME-DATE legs held as an
  `ExactRatioRate` (the lookup's `cross`); the date used is the latest date on which every leg exists. CNH is strict
  even when a CNH series is in M (PD-0030). HKD peg band 7.75..7.85 (inclusive, exact) runs where a USD leg exists;
  the CNY +-2 % band runs only with a central-parity series in M and is otherwise `UNVERIFIABLE` (no source is
  admitted; nothing is fabricated); a breach makes the leg IMPLAUSIBLE (INSUFFICIENT_DATA + SOURCE_CONFLICT). Each
  leg is reconciled alone; one upstream's two files (the ECB file and its re-server) must be equal as decimals, and
  a date present in one and absent in the other inside both files' coverage is a DISAGREEMENT (1.1a item 4).
- *Port*: `LookupOutcome` gains `NO_HISTORY`, `STALE_BEYOND_LIMIT`, `FRESHNESS_UNKNOWN`; `QuoteLookup`/`FXLookup`
  carry `date_used`, `missed_count`, `lineage_notes`, `synthetic`, and FX also `cross`, `leg_reconciliations`,
  `checks`; the calendar files actually counted are in `consumed`. `states.py` holds the whole 5.2/1.6/4.4 table.
  `ValuationInputs` gains `open_items` and `synthetic`; `resolution_obj()` carries how each input was resolved,
  apart from `value_obj()` (unchanged), so the value part stays byte-identical across adapters.

**6. 1.2 rulings applied.** *4.7*: a listing on a market with no admitted source (CN, HK today; data in
`profiles.PRIMARY_ORDER`, A.5) with nothing in M resolves to MISSING_PRICE_HISTORY, freshness UNKNOWN, lineage cause
`NO_ADMITTED_SOURCE market=...`; a file from a refused source is refused from its MANIFEST ALONE, before its payload
is read or parsed (spy test). *4.8*: lineage `is_synthetic` follows the usage scope; synthetic and real readings are
never reconciled together (the real set is used and the exclusion is flagged); every result says `synthetic`
if M holds any synthetic file. *4.3 / 4.1a*: one-upstream agreement SINGLE_SOURCE, disagreement DISAGREEMENT; a
non-RAW reading is left out of the reading set with a note; a currency other than the listing's is refused at ingest
(already so). *2.4 item 4a*: an unrecovered single reading carries no status. *V2 (a')*: rows carry their own
bound (`PriceRow.bound`: 0 for a recovered raw close; half a unit of the source's `adjusted_dp` for an adjusted
row); the residual test is `e_i + max(e_lo, e_hi)`, `u_a = (e_lo + e_hi)/Delta`, `u_b = e_lo + |ref_lo| u_a`; the
function takes no bound argument. *9A #2*: the adapter no longer reads `security_class` from the request (strict
2 decimals, flagged "security class unknown"). *9A #6 / Ruling 3.1*: at ingest, after every file is loaded, V0 (a
CONTRADICTED series is not admitted; an uncovered part is UNVERIFIABLE), V2 (RAW reference rows are supplied by the
daily parsers on a verification-only channel, so adjusted rows get method, label status and, only with confirmed
events, the anchor; no confirmed event is in M, so the event check is UNVERIFIABLE), and `observed_at` = the scheduled
close from the calendar. *1.1a*: a re-server's declared upstream carries `provenance: UNCONFIRMED`, turned CONFIRMED
(equal on the whole overlap, same dates) or REFUTED (any difference) by `check_provenance` when an ECB-direct file
is in M; every resolved rate from an UNCONFIRMED or REFUTED file notes it. *A.5*: primary order is
`{CN: (), HK: (), US: (alphavantage), FX: (ecb)}`.

**7. Existing tests changed because a ruling changed (no other expected value moved).** Convention-set strings
`market-data/1.1` -> `1.2` (manifest, release, data-set ref, exit test, pipeline tests); `PROFILE_SET_VERSION` and
profile ids; the A.5 primary-order test; `alphavantage.us` is no longer TO_OBSERVE; an unrecovered single reading
has status None (was SINGLE_SOURCE); the reconciliation mechanics tests keep the 1.1 order by injecting it (the
default is data); V2 tests stamp the same per-row bound on the rows (the test no longer takes it); the two probe
test helpers pass an open gate. The import-boundary test lists gain `market11`, `calendars`, `states`.

**8. Engineer choices the contracts did not fix (for the Quant or the PM).**
- `is_conformant` True means "no placeholder rule is injected", not "everything is built": `visible_open_items()`
  lists the profiles still TO_OBSERVE and `UNBUILT` (Current mode, V1/V3, resolution records, parity series, CN
  class from identity, FIGI-equality, F8-B, PostgreSQL), and every `ValuationInputs` carries it.
- The ECB-direct file was not added to `probe` (the plan is capped at 12 steps by an existing test); use `fetch`.
- A V0 CONTRADICTED series is dropped per (listing, file); the V2 reference bound for raw open/high/low is the
  close's bound (the ruling states it for the close only); a REFUTED re-server file stays in M, flagged.
- Reading "coverage" of a file for the 1.1a date check as the first and last date the file holds for that pair.
- The raw-OHLC reference channel (`AdapterOutput.reference`, resolved to verification-only `AdjustedQuote`s with a
  RAW label) is separate from `adjusted` so no existing count or digest changed.
- The `placeholder_*` classes were kept (retired as a default) because their mechanics tests still prove the
  plug points.

**9. Not built here.** Current mode (instant `t`); V1 and V3 (they need corroborated corporate actions); human
resolution records; a central-parity series and its adapter (no source); CN security class from
`Instrument.security_type`; the FIGI-equality test; F8-B; the PostgreSQL store; the full exit test.
(CP2c-2 below builds the security class, the FIGI-equality test, F8-B, the PostgreSQL store and the exit test.)

### 15.17 CP2c-2 as built: the PostgreSQL store, F8-B, FIGI equality, the CN security class and the full exit test (engineer; 2026-10-01; not yet reviewed)

Convention set recorded everywhere: **`market-data/1.3`** (the Quant issued it while this increment was under way; the
change note and section 9B were applied first, in the CP2c-1 code). Supersedes the "not built" lines of 15.16 §9 and the
planned table list of 15.5 (see 2 below for what changed from the plan).

**1. `market-data/1.3` applied to CP2c-1 (section 9B; each point has a test in `test_marketdata_cp2c2_conventions13.py`).**
- *Ruling 2.4 item 4a (clarification).* Unrecovered readings that agree give no value and NO reconciliation status
  (`Market11Reconciler` returned CORROBORATED in 1.2); the agreement is the lineage flag `UNRECOVERED_READINGS_AGREE`. A
  `NO_HISTORY` price carries its cause(s) as lineage notes, kept apart: `NO_PRINT_ON_OR_BEFORE_AS_OF`, `NO_PRINT`,
  `NO_RAW_READING`, `ONLY_UNRECOVERED_READINGS`, `NO_ADMITTED_SOURCE`, `SERIES_CONTRADICTED`. `NO_ADMITTED_SOURCE` and a fully
  contradicted listing are now `NO_HISTORY` (they were `NOT_IN_RELEASE`); a listing the version holds nothing for and
  with no cause stays `NOT_IN_RELEASE`. All map to the same pair `INSUFFICIENT_DATA + MISSING_PRICE_HISTORY`.
- *V2 (a'), delta_r per field.* `PriceRow.field_bounds` and `UnresolvedAdjustedQuote/AdjustedQuote.field_bounds` carry the
  bounds of open, high and low from each field's own profile (`precision.field_bound`: `delivered_dp` if declared, else half
  an ulp in the declared binary format, else half a unit of the text's decimals). The close's bound is no longer copied to
  them; a reference row with no per-field bounds makes V2 `UNVERIFIABLE` (fail closed).
- *Ruling 1.1a item 5, coverage.* `fx_file_window(manifest, calendars)` computes `[start, end]` at ingest: the requested start
  (`start`/`read_start`; none = a full-history file, whose start is the first date held for the currency) and
  `min(requested end, D_ret)`, `D_ret` = the latest fixing of the ECB calendar at 16:00 Berlin at or before the retrieval
  time (inclusive). It goes to the store as `FXFileWindow`. Both the date-set check at resolution and the provenance check
  (`verification.check_provenance(..., declared_window, direct_window)`) use it; with no window or no `D_ret` the date-set
  part is UNVERIFIABLE (nothing is invented, nothing is CONFIRMED beyond what it verified). The Quant's worked example
  (a Frankfurter file requested 2025-01-01..2025-01-08 that lacks the 8th) is a test.
- *Section 3 consequences and Ruling 1.1a item 6.* A V0-contradicted series is dropped per (listing, file); the failure is
  kept as `SeriesExclusion` (stored, and the cause of `NO_HISTORY`). A REFUTED re-server file stays in the version, flagged
  (with the full differing (date, currency) list in the `PROVENANCE` label result), supplies no rate on any date
  (`_FXView.dates` skips dates only it holds; the reconciler never uses it), and a value difference from the ECB file is
  `DISAGREEMENT`/`SOURCE_CONFLICT`; agreement is `SINGLE_SOURCE` on the ECB value. Within one upstream the publisher's own file
  (`PREFERRED_FX`) now sorts before a re-server (A.5), whatever the release's precedence says.
- *Ruling 1.5a.* `market11_conventions(calendars)` takes no parity mapping; `Market11FX(_test_central_parity=...)` is
  keyword-only and underscore-named, built only by `market11_conventions_with_injected_parity_for_tests`; a test scans `src/`
  to prove nothing else names either. A CNY result without a parity series carries `PARITY_CHECK_NOT_RUN`.
- *Section 9B #4 (a).* `Lineage.adjustment_label_source` says a RAW label came from the profile's documentation of the call
  (status MEMORY), not from the file. (Not in the engineer brief's list; done because 9B names it.)
- *Typed outcomes.* `states.py` already mapped each outcome to one pair; a table test now runs missed counts 0 to 7 for price
  and 0 to 5 for FX and checks that a number is withheld only at `INSUFFICIENT_DATA`.
- *Ids.* `CONVENTION_SET_ID`, `profiles.CONVENTION_SET`, the rule ids and `PROFILE_SET_VERSION` are `market-data/1.3`.

**2. The PostgreSQL store (migrations 0009-0011; `src/persistence/market_data_store.py`).** An append-only, rebuildable
projection of a release; implements the same `MarketDataPort` as `InMemoryMarketData`.

| Migration | Contents |
|---|---|
| `0009_market_data_files_and_releases.sql` | `md_file` (`file_sha256` PK, source, kind, usage scope, retrieval time, manifest JSON), `md_release` (`release_id` PK, `convention_set_id`, canonical release JSON, `contains_synthetic`, `projection_digest`, trigger-set `append_xid`), `md_release_file` (order, FX coverage window) |
| `0010_market_data_observations.sql` | `md_quote`, `md_fx_rate`, `md_corporate_action`, `md_benchmark`, `md_benchmark_point`, `md_adjusted_quote` (verification-only), `md_calendar`, `md_series_exclusion`; every row has `release_id`, `file_sha256` (composite FK to the release's file), `row_ordinal` and full lineage JSON |
| `0011_market_data_append_only_and_sealed_releases.sql` | `md_reject_mutation`, `md_release_stamp`, `md_require_open_release`: triggers, pins |

- *Keys and lineage.* `listing_id uuid` (FK to `listing`) is the only identity key; NO table has a ticker, FIGI or vendor-id
  column (a test reads `information_schema`). A SYMBOL_CHANGE's tickers sit in the action's `detail` JSON, not in a key
  column. `file_sha256` and the convention-set id are stored (`md_file`, `md_release.convention_set_id`).
- *Append-only.* UPDATE and DELETE are refused by a row trigger and TRUNCATE by a statement trigger, for every role (typed
  `MarketDataImmutableError`; constraint `md_append_only`). A TRUNCATE of a table another md table references is refused
  first by PostgreSQL's own foreign-key rule; the trigger is proved by truncating all tables together.
- *Sealed release.* The release row stamps the full transaction id (`pg_current_xact_id()`, the 0008 pattern); a child row
  is accepted only from that same transaction (`md_release_sealed`, typed `ReleaseSealedError`), so once the creating
  transaction commits nothing can be added to a release and "same release, same output" cannot be broken by a later insert.
  Observation rows belong to a RELEASE, not to a file, because the projection depends on the whole version (the calendars,
  the other files' provenance verdicts, the V0 admissions).
- *Security patterns of CP1-B, unchanged.* Every function is `SET search_path = <schema>, pg_temp`, and every function starts
  with the inline schema-rename guard (`md_search_path_pin_stale`); nothing relies on revoking TEMPORARY. Tests: the pin is
  read from `pg_proc.proconfig`; a renamed schema makes every function fail closed; a TEMP-table shadowing attack run as the
  app role is refused as shipped, and a CONTROL with the pin removed shows the attack succeeds (so the test can fail).
- *Numeric bounds.* Every price, rate, volume, split ratio, dividend amount and benchmark value: below 1E30 and at most 24
  decimals (PD-0026's bound, so a split ratio F8-B copies into the ledger always fits). `precision_bound` (a derived half-ulp,
  2^-53 has 53 decimals) has scale limit 100 and the same value limit: an engineer choice, flagged. Typed
  `MarketDataValueOutOfRangeError`; a refused write leaves nothing (whole transaction).
- *Reading.* `read_release(conn, release_id, exchange_of)` loads the release's rows (one query per table, ordered by
  `row_ordinal`), rebuilds an `InMemoryMarketData` from them and delegates every port method to it, so every rule lives in one
  place, and refuses a projection whose digest differs from the recorded one (`ProjectionDigestMismatchError`; proved by
  disabling the triggers as the owner and tampering). Eager and whole-release: fine for a CP2 release, a lazy per-listing
  read is a CP3 optimisation if sizes need it. `exchange_of` is supplied by the caller exactly as for the in-memory store, so
  no grant on `listing` is needed.
- *Rebuild.* `write_release` is idempotent (same release, same digest: no-op) and refuses the same release id with a different
  projection (`ReleaseConflictError`). Rebuilding the same files in a fresh schema gives the same digest and the same
  consumer bytes (tests).
- *Final grant spec* (run by the schema owner; `APP_GRANTS` in `test_postgres_least_privilege.py`, imported by every
  database test): `GRANT USAGE ON SCHEMA <s>`; `GRANT SELECT, INSERT ON <s>.ledger_event`; `GRANT SELECT ON <s>.account`;
  `GRANT SELECT ON <s>.portfolio`; `GRANT USAGE ON SEQUENCE <s>.ledger_event_ledger_seq_seq`; **new:** `GRANT SELECT ON`
  the eleven `md_*` tables (`md_file, md_release, md_release_file, md_quote, md_fx_rate, md_corporate_action, md_benchmark,
  md_benchmark_point, md_adjusted_quote, md_calendar, md_series_exclusion`). Six statements. The role holds exactly those
  table privileges (an exact-set test); **negative control:** with only the schema USAGE a read of `md_release` is
  `42501`; the role cannot INSERT, UPDATE, DELETE or TRUNCATE any md table (`42501`). Loading a release is a privileged step
  (the owner or a loader role holding INSERT on the md tables, SELECT on `md_release` and `md_file`).
- *Changed from the 15.5 plan.* No `md_source`, `md_load`, `listing_identifier` or `md_resolution_exception` table: the identity
  registry stays in memory (no identity writer exists), a resolution is stored as the `listing_id` on each row, and the
  per-file summary digest stays a build result. `md_adjustment_verification` became `md_adjusted_quote` plus the label results
  kept in the build. Existing tests changed only by the new counts: 8 -> 11 migrations (three assertions), the table-name
  set, the pending list after 0007, and `schema_migrations` count in the least-privilege test.

**3. F8-B (`src/corporate_actions_service/split_confirmation.py`; PD-0030 section 2; Ruling 6.4).** A service outside
`marketdata`; it reads the market-data port and appends through `persistence.ledger_store.append_event` (the existing path;
nothing else writes).
- *Corroboration (Ruling 4.5).* For each ex-date of a listing's SPLIT readings, a record from a configured FEED source and one
  from a configured FILING source (`ConfirmationPolicy`: the human's configuration, nothing inferred from names) agree on the
  ex-date and, as an exact rational, the ratio. Not corroborated, never appended, reported: `FEED_ONLY`, `FILING_ONLY`,
  `DISAGREEMENT`, `SYNTHETIC_MIXED` (Ruling 4.8). The ratio appended is the filing's own form (15/10 against 3/2 gives 3/2).
- *Decisions per account* (replay at the day before the ex-date, at the current ledger version, so an earlier append is seen):
  `APPENDED`; `ALREADY_RECORDED` (an equal live split on the ex-date; or the same evidence already recorded); `CONFLICT_RATIO`
  (a live split on the ex-date with another ratio); `CONFLICT_DATE` (a live split with the same ratio on another date that no
  corroborated split explains); `REVERSED_BY_USER`; `POSITION_UNKNOWN` (the replayed quantity is flagged); `NOT_HELD`. A
  conflict appends nothing and yields a `ValuationSuppression` (reason `SOURCE_CONFLICT`): `[min(X, Y), max(X, Y))` for a
  different date (Example 6-A: 29 January to 2 February), open-ended from the ex-date for a different ratio or a user reversal.
  The replayed quantity is not touched.
- *Provenance and distinguishability.* `source_reference` =
  `finweb.f8b/1;md=<convention set>;rel=<release id>;feed=<sha256>[+...];filing=<sha256>[+...];ex=<date>;ratio=<new>/<old>`:
  one line, no spaces, fixed ASCII alphabet, 266 characters for one file per role. A user-entered event never starts with
  `finweb.f8b/1`; `parse_source_reference` reads it back. **Constraint check (the 15.13 open point):** the ledger's constraints
  are non-blank and not whitespace-only (CHECK), unique `(account_id, source_reference)` (a btree entry limit of about 2.7 KB,
  applied AFTER compression, and reported by the driver as an untyped error, not as a `LedgerStoreError`: a 8,000-character hash
  string is refused by the database). The service therefore bounds its own reference at `MAX_SOURCE_REFERENCE_CHARS` (1024) and
  REFUSES a longer one (`SourceReferenceError`), never truncating; the alphabet excludes NUL and every whitespace code point.
  The longest allowed reference is accepted by the real database (test).
- *Idempotent and reversible.* `event_id = uuid5(account, source_reference)`; an identical resubmission is a no-op (the ledger's
  `created=False`); new evidence (a new release) for the same split finds the live equal split and appends nothing; migration
  0007 is the backstop and is tested. A split the user reversed is never appended again, by this release or a later one
  (`REVERSED_BY_USER`), because the user's reversal is final until the user records the split themselves.
- *Not atomic across accounts:* each append is atomic and independent and every one is idempotent, so a stopped run is finished
  by running it again.
- *Tests.* 25 unit tests over an in-memory ledger (`test_corporate_actions_service.py`) and 8 opt-in database tests as
  `finweb_app`, reading the PostgreSQL store (`test_postgres_corporate_actions_service.py`).

**4. FIGI equality (`InMemoryIdentityRegistry.propose_symbol_change`; Ruling 7.2 item 3).** Deterministic from saved identity
assertions: both tickers must have an assertion with the SAME FIGI and the same exchange code (the source's own code, never a
MIC), and a stored FIGI must agree. CONFIRMED applies `change_ticker` (an attribute update; `listing_id` unchanged);
different FIGIs, a venue change or a FIGI contradicting the stored one are QUARANTINED (kept in `quarantine()` for a human,
nothing applied, never a new listing); a ticker with no assertion is UNCONFIRMED (nothing applied; the old ticker often no
longer resolves; a filing or notice as the other accepted evidence is not built). A ticker matches exactly as published (no zero
padding: "700" is not "0700").

**5. CN security class (`profiles.security_class_for`, `ingest._classify_close`).** `InstrumentResolverPort` gains
`security_type(listing_id)`. After a CN listing is resolved, the close's verbatim text and its profile (found from the lineage's
`precision_profile_id`) are re-judged with the class from the identity record: `COMMON_STOCK` -> `A_SHARE` (2 decimals), `ETF` ->
`FUND_ETF_LOF_BOND` (3). An unknown type keeps the strict 2 and says "security class unknown"; a refusal under a known class says
which. The reference rows of V2 follow the same decision. The adapter still passes no class (it cannot know it).

**6. The CP2 exit test (`test_marketdata_cp2c2_exit.py`, `marketdata_exit_kit.py`; opt-in half over PostgreSQL).** One consumer,
`assemble_valuation_inputs`, unchanged, over four complete synthetic versions and over both stores:
(a) the mock; (b) synthetic mainland and Hong Kong files in the real Eastmoney and Sina CSV layouts through their real parsers,
with a synthetic Alpha Vantage-layout US file and a synthetic ECB `eurofxref-hist` FX file; (c) the same with the Frankfurter JSON
layout for FX; (d) the same as (b) with the US quotes through a test-local TSV adapter (the fourth adapter). Every source id is a
synthetic id (`synthetic.*`, registered `synthetic: true`), so nothing is attested as real (Ruling 4.8). The adapters of the real
formats now take a `source_id` (default: the real one) so a fixture can use its own synthetic id while the parser and its
profile stay the format's. Expected values are hand-derived in `marketdata_exit_kit.expected_value_obj` (HKD->USD 1081/8410,
CNY->USD 1081/7810 from the 2025-01-03 fixing, prices 151.1, 332.6, 1502, positions 10, 100, 2).
The six checks of 15.9: (1) the SHA-256 of the analytics modules (`consumption`, `port`, `conventions`, `states`, `market11`,
`calendars`, `reconciliation`, `store`, `canonical`, `manifest`, `contracts`, `profiles`) is the same before and after adapters
and the database store are built and run (15.9 named `fx.py`, which does not exist; no hash is committed, as 15.13 decided);
(2) an AST scan: none of them, and the database store, imports an adapter, ingestion, the file store or a vendor name; (3) the
value part and the resolution part (date used, missed count, cross legs, checks, causes) are byte-identical across the four
worlds and across the two stores, while the lineage part differs and names exactly the right files and adapters; (4) the `novel`
world; (5) negative controls: a changed byte (hash mismatch), an unattested source (refused before its payload is read), a
tampered release id, a float price, a naive timestamp, a ticker as the key, a vendor-shaped extra field (the control "an
adjustment label it was not given" is NOT enforced at ingest, because an UNDECLARED call may legitimately be read through its
profile: it is recorded in lineage instead, 1 above); (6) determinism across builds, across processes with `PYTHONHASHSEED`
1, 2 and random, and, over PostgreSQL, a stored release read in another process, and a projection rebuilt in a fresh schema.
Ruling 4.7 has its own test: a version with no mainland or Hong Kong file gives those listings `NO_HISTORY` +
`MISSING_PRICE_HISTORY` with the cause `NO_ADMITTED_SOURCE` and freshness UNKNOWN, and the committed `SOURCES.json` is read to
show that no mainland or Hong Kong price source is attested.

**7. Engineer choices the contracts did not fix (for the Quant or the PM).**
- The F8-B linking rule for an off-date split: any live ledger SPLIT of the position with an EQUAL ratio that no corroborated
  split explains is the "same ratio, other date" case (CONFLICT_DATE). A split with a different ratio on a different date is NOT
  linkable without a window (no number exists in the conventions) and is not treated as a conflict. Ruling 6.4 item 3 read
  literally ("a split with a different ratio or date exists") would block on any other split of the position; that would block a
  genuine second split for ever, so "explained by a corroborated split" was added. **For the Quant.**
- A user reversal of a system-appended split is final and suppresses valuation (REVERSED_BY_USER). **For the Quant/owner.**
- A REFUTED re-server file still takes part in the date-set check (a date present in one file and absent in the other inside
  both coverages is a DISAGREEMENT), although item 6 speaks only of value differences. **For the Quant.**
- A float64 field with no declared `delivered_dp` gets half an ulp in binary64 as its V2 reference bound (the format's own
  guarantee). **For the Quant.**
- `COMMON_STOCK` on a mainland exchange is an A share; B shares and LOF/bond funds cannot be told apart by `SecurityType`.
- The coverage of a request-bounded FX file uses `start`/`end`, and of a full-history file `read_start`/`read_end` as its
  requested end (the adapter translates only that window).
- `precision_bound` has scale limit 100 where PD-0026's 24 applies to the ledger.
- The projection is keyed by release, so two releases that share a file store its rows twice (their post-processing can differ).

**8. Not built.** A real corporate-action FEED adapter and an issuer-FILING adapter: F8-B has no real input until the human
provides them (the tests use the mock adapter as two sources); an identity writer to PostgreSQL (the tests write identity rows
directly); lazy per-listing reads in the PostgreSQL store; Current mode, V1 and V3, human resolution records, a central-parity
source.

### 15.18 CP2 fix round: the findings C2-1 to C2-13 of the independent review of `39733e9`, and `market-data/1.4` (engineer; 2026-10-01; not yet re-reviewed)

Convention set recorded everywhere: **`market-data/1.4`** (`CONVENTION_SET_ID`, the rule ids, the profile set `market-data/1.4#profiles/2`;
section 11 item 13). Source of the findings: `reviews/TECH_REVIEW.md` section 25. Migrations 0001-0011 are untouched; the one schema
change is **0012** (with its `CHECKSUMS` line). Each finding below has a regression test that reproduces the reviewer's failure
scenario; a scratch-copy mutation run showed the new tests fail on the old behaviour (C2-1, C2-2, C2-3, C2-5, C2-7, C2-8, C2-9, C2-11 M1).

| Finding | Fix | Regression test |
|---|---|---|
| **C2-1** (MEDIUM) same-day lookup with no calendar | `CalendarSet.count_after` no longer returns 0 for an empty interval before looking for a calendar. The count is 0 only when ONE calendar governs the MIC (or ECB), its coverage contains the date AND it lists the date; otherwise freshness UNKNOWN, INSUFFICIENT_DATA, no reason code, lineage `CALENDAR_COVERAGE_GAP` (or `OFF_CALENDAR_DATE`). The calendar is now cited in `consumed` for a same-day lookup. | `test_cp2_fix_round_marketdata.C2_1_*`: prices (no calendar, a calendar covering only January 2024, several calendars), a direct rate and a cross (both legs), the build path of the reviewer's P1b-build with and without calendar files |
| **C2-2** (MEDIUM) F8-B appends from synthetic evidence | `Corroboration.SYNTHETIC_EVIDENCE`: all-synthetic evidence, or ANY synthetic file in the market-data version (`port.contains_synthetic`), is reported and never appended. | `test_corporate_actions_service.C2_2_*` (P2a: both synthetic; real evidence in a synthetic version; real control) |
| **C2-3** (MEDIUM) off-date linking depends on the window | Ruling 6.4a built as written (`WINDOW_SESSIONS = 20`, `CalendarSet.session_window`). MATCHED / CONFLICT_DATE / CONFLICT_RATIO / NOT_RECORDED; outside every window only an `UNCORROBORATED_LEDGER_SPLIT` lineage flag (`SplitReport.lineage_flags`); overlapping windows give CONFLICT_RATIO with nothing appended; an uncovered window gives `CALENDAR_COVERAGE_GAP`, nothing appended, suppression from X with NO reason code (`ValuationSuppression.reason_code` is Optional). The corroborated splits of the WHOLE release place the windows; the caller's range only chooses which splits are acted on. | `C2_3_LinkingWindowTests` (the reviewer's two-split scenario over two ranges gives the same appended event and 200 on 2025-09-01; closed-interval edges; two candidates; overlap; gap; flags) |
| **C2-4** (MEDIUM) identity ignores the exchange | `apply_identity_assertions` attaches a FIGI only when the assertion's exchange code is one of the codes of the listing's MIC; otherwise a CONFLICT resolution and a `QuarantinedAssertion` (`assertion_quarantine()`). `propose_symbol_change` quarantines a foreign exchange code and cannot CONFIRM (it is UNCONFIRMED) for a MIC with no mapping. | `C2_4_*` (P6: the London FIGI, the two-`LN` confirmation, no mapping, planted FIGI, same-venue control) |
| **C2-5** (LOW) TEMP shadowing of reads | Every read of `read_release` is schema-qualified with `pinned_schema(conn)`: the first non-temporary schema of `current_schemas(false)` (none: fail closed). | `test_postgres_cp2_fix_round.ReadPathHardeningDbTests` as `finweb_app`: the shadow works against an unqualified reader (control, 1511) and `read_release` returns 151.10 and the honest digest; `pg_temp` first in the path; no non-temporary schema |
| **C2-6** (LOW) release key not verified | `read_release` checks that the stored content IS the release the key names, the convention set the row says, and that `md_release_file` lists exactly `release.files` (`ReleaseKeyMismatchError`); migration 0012 adds `md_release_key_matches_content` (NOT VALID, so an upgrade over an old release cannot fail on it). | same file: the CHECK refuses a new mismatched row; the read-side check with the CHECK dropped in a scratch schema; a release with no file rows |
| **C2-7** (LOW) same upstream corroborates | Feed and filing corroborate only when their `independence_group` sets are disjoint (`SAME_UPSTREAM` otherwise). | `C2_7_*` |
| **C2-8** (LOW) forged `finweb.f8b/1` | See choice 4 below. | `C2_8_*` |
| **C2-9** (LOW) refuted-file asymmetry | A date only a REFUTED re-server file holds, later than the date used, is tested by the date-set check: inside both coverages it is DISAGREEMENT (SOURCE_CONFLICT) and nothing is carried forward over it. Outside the publisher file's coverage it is not a conflict and the earlier fixing is carried (1 missed). | `C2_9_*` (both directions give one state; the carry-forward control) |
| **C2-10** (LOW) rulings the conventions reserve | Ruling 6.4b: reversal final inside the reversed event's window only, cause `SYSTEM_SPLIT_REVERSED_BY_USER`. V2 (a'): no half-ulp default; `field_bound` returns None for a text or float64 field with no declared `delivered_dp`, the reference row then carries no field bounds and V2 stops with `PROFILE_INCOMPLETE` (float32 keeps half an ulp of binary32). A.1: `security_class_for(mic, security_type, currency)` over `CN_CLASS_TABLE`; anything else is strict 2 dp, flagged `SECURITY_CLASS_UNRESOLVED` (once per listing and file as an ingest issue, and in the refusal text). | `C2_10_UserReversal*`, `C2_10_CnSecurityClass*`, `V2AtIngestTests.test_the_real_eastmoney_profile_stops_v2_with_profile_incomplete`, `V2PerFieldBoundTests` |
| **C2-11** (LOW) exit checks | Check 1 compares the analytics modules with COMMITTED pins (`ANALYTICS_PINS` in the exit test), so a committed edit fails it until the pin moves in the same commit; a negative control proves it can fail. Check 2 and the boundary test add `sina`, `eastmoney`, `eurofxref`; `ecb` is added for the consumer-facing modules (`consumption`, `port`, `states`) only, because the convention modules must name the publisher the conventions define. New check 3b: every adapter's OWN output (the port's raw readings) is compared with hand-written prices and fixings in every world and both stores, which catches the reviewer's x10/÷10 compensating pair; check 3c: the consumer-side modules contain no `source_id`, `independence_group`, `startswith` or `endswith`. | the exit test; scratch run of M1: checks 1, 2, 3b, 3c and the boundary test fail (the hand-derived value check alone still passes, as the reviewer found) |
| **C2-12** (LOW) admission | `SourceProfile.admitted` is False for TO_OBSERVE, MEMORY and `refused`; `not_admitted_reason` says which; `profile_open_items()` lists MEMORY profiles. | `C2_12_13_*` (an attested refused profile and an attested MEMORY profile are refused before the payload is parsed) |
| **C2-13** (LOW) terms gate | `ingest_file` raises `SourceTermsNotAttestedError` itself before calling the adapter (synthetic sources exempt, as before). | `C2_12_13_*` (spy adapter: 0 calls) |
| precision_bound | `bound_for_storage` / `stored_contents`: stored exactly, or rounded toward +infinity to 100 decimals, BEFORE the projection digest is taken (so the digest, the rows and a read-back agree). The main session ruled PD-0026 does not cover this metadata. | `PrecisionBoundForStorageTests`; `test_postgres_market_data_store...scale_of_a_half_ulp` (1E-101 and 2^-120 stored as the hand-computed ceiling, read back, same digest) |

**Choices the contracts did not cover (for the Quant or the PM).**
1. *C2-1 also requires the date to be a listed session.* The brief and Ruling 5.3 name coverage; the reviewer's remedy also says "is a
   session or fixing day". Inside its coverage a calendar is complete (5.3 item 4), so a print or fixing dated a non-session has no session
   date (5.2 table, last row): UNKNOWN, with its own lineage cause `OFF_CALENDAR_DATE`. It matters for FX, which has no Test V0: an
   ECB file shifted onto a Sunday would otherwise be CURRENT under a covering calendar. Easy to drop to coverage only (one `if`).
2. *The MIC to exchange-code table is data the registry is given, empty by default.* No convention states it (the Quant's A.1 has none),
   so no table is invented: with none, no FIGI is attached and no symbol change is CONFIRMED. **Open: the Quant or the human should
   supply the table** (OpenFIGI codes against MICs) and decide whether the composite code `US` denotes an exchange-level listing (the
   reviewer's note on `exchCode US`). `IdentityEvidence.resolution` at ingest is still exchange-blind (it only says what matched); only
   the writer (`apply_identity_assertions`) is gated.
3. *F8-B needs the calendar and the listing's MIC.* `confirm_splits(..., calendars=, exchange_of=)` are required keyword arguments
   (`PostgresMarketData.calendars()` supplies the calendars of a release). A corroborated split whose own window cannot be evaluated is
   a gap outcome; another split's unevaluable window is ignored when deciding this one (it can only turn a MATCHED into a conflict,
   never cause an append, because any candidate in this window already prevents one).
4. *C2-8: the marker is made unforgeable at the append path, and the service does not trust the string.* `ledger_store` reserves the
   namespace `finweb.` (folded: blanks, case, compatibility forms): `append_event`, `append_batch`, `append_correction` and
   `append_internal_transfer` refuse it (`ReservedSourceReferenceError`, before the connection is touched); only
   `append_system_event(conn, event, namespace=...)` writes it. The service's `is_system_event` additionally requires the strict
   reference grammar (exact keys once each in order, bounded, hashes and date valid) and the DETERMINISTIC event id of
   (account, reference). It is not a boundary against code inside this process; it keeps the marker out of every user-entered path.
   A user entry that imitates it and is reversed no longer counts as a reversed system split (the service appends).
5. *C2-10, Eastmoney and Sina US profiles.* Appendix A.3 declares no `delivered_dp` for their open, high and low (FLOAT64), so under 1.4
   V2 never runs on them (PROFILE_INCOMPLETE): the Quant's Example 3-C (the real 600519 qfq file, SUBTRACTIVE) cannot be reproduced
   from the profile. Both sources are REFUSED, so no real file is affected; the V2-at-ingest tests declare `delivered_dp` 2 in a test
   profile, and one test pins the real profile's PROFILE_INCOMPLETE. **For the Quant:** declare `delivered_dp` for those fields, or accept.
6. *The stored digest of an extreme bound differs from the in-memory digest.* Rounding a bound beyond 100 decimals up changes the
   projection (and so its digest) relative to the in-memory store; it happens only for a bound below about 1e-100, never for a real
   source, and the PostgreSQL store reads back exactly what it stored.

**Existing tests changed because a finding or 1.4 changed the behaviour (no other expected value moved).** Convention-set strings
`1.3` -> `1.4` (manifest, release, data-set ref, profile ids `1.4#profiles/2`, exit and pipeline tests); migration counts 11 -> 12 (four
assertions); C2-1: the lookups that sit ON a print or fixing date now carry a covering calendar (`test_a_print_dated_the_as_of_date...`
was rewritten, the FX transport-check tests, the synthetic-and-real test, the CN class tests, the Alpha Vantage real-path test), the
exit test lists the calendar adapter among the cited ones and one ingest test counts 4 cited files, not 2; C2-2: the F8-B unit and
database tests use evidence of the REAL usage scope (attested test sources) and a synthetic weekday calendar for the window (C2-3);
C2-4: identity tests give the registry an exchange-code table; C2-8: the database F8-B tests write the marker through
`append_system_event`; C2-10: the half-ulp field-bound assertion, the Eastmoney V2 tests (test profile), the CN class mapping test and
the "security class unknown" text became `SECURITY_CLASS_UNRESOLVED`; C2-12: two tests asserted MEMORY and refused profiles admitted;
precision bound: the scale-101 refusal became the rounded-up store; C2-11: check 1 and the vendor lists.

**Not done / open.** The MIC-to-exchange-code table (2); the Eastmoney/Sina `delivered_dp` (5); `IdentityEvidence` at ingest is
exchange-blind (2); a real feed or filing adapter and an identity writer to PostgreSQL still do not exist; and nothing here was
re-reviewed. (Items 2 and 5 are answered by `market-data/1.5`, §15.19.)

### 15.19 CP2 final round: C2-14, C2-15, namespace folding, refused kinds, the grant note and `market-data/1.5` (engineer; 2026-10-01; not yet re-reviewed)

Convention set recorded everywhere: **`market-data/1.5`** (`CONVENTION_SET_ID`, rule ids, profile set `market-data/1.5#profiles/3`, A.6 table
`market-data/1.5#a6/1`). Migrations 0001-0012 are frozen; this round adds NO migration (see 3). Source: re-check section 26.

1. **C2-14 (off-calendar FX fixing).** `Market11FX.resolve` now wraps its rule in a `_CalendarFilteredView`: every fixing date that is NOT a
   listed fixing day of the governing ECB calendar (inside its coverage, where it is complete) is removed from the dates the rule may
   use, on ANY as-of date, and the lookup falls back to the previous valid fixing (counted by missed fixings), or has no history when
   there is none (`NO_HISTORY`, MISSING_FX_HISTORY). Where no calendar covers the date nothing is excluded and freshness is UNKNOWN as
   before. Lineage note `OFF_CALENDAR_DATE: n fixing date(s) ...` lists what was dropped. **Why at lookup, not at build:** the
   `md_series_exclusion` table is keyed by listing and a new exclusion kind would need a migration; the lookup-time rule is the same for
   the in-memory and PostgreSQL stores (the PG store rebuilds the in-memory one) and needs no schema change. **Prices:** the only path
   that admits a print is the build, where Test V0 CONTRADICTS and drops a series with any date on a non-session inside the calendar's
   coverage; a test proves a Saturday row drops the series and no later as-of uses it. The empty-interval check of the fix round stays.
   Tests: `test_cp2_final_round.C2_14_*` (P8a at three as-of dates, a cross, no history, no calendar, a control, P8b through the build,
   the price side). Mutation: passing no calendar to the view fails 4 of 7.
2. **C2-15 (overlapping windows).** When a corroborated split's window overlaps another corroborated split's window of the same
   listing, BOTH are CONFLICT_RATIO, nothing is appended for either, whatever the ledger holds, and valuation is suppressed from the earlier
   ex-date (`AccountOutcome.suppress_from`). Windows come from the whole release, so the first run, a re-run and a run over only the second
   split agree. **For the Quant:** Ruling 6.4a item 5 is worded around "a ledger split inside the overlap"; the main session and the
   reviewer read the rule, and item 6 ("splits twice within 40 sessions ... failing closed costs little"), as failing closed on the
   overlap alone. That reading is implemented; the narrower one is what C2-15 showed to be non-idempotent. Tests: `C2_15_*` (the reviewer's
   ten-sessions-apart pair over all three runs, evidence order, a non-overlapping pair still appended); the older overlap and "explained"
   tests were adjusted (their expectations were the old rule). Mutation: dropping the overlap branch fails the main test.
3. **Reserved namespace.** `ledger_store.fold_reference`: NFKC, removal of every Cf character and of the other default-ignorable code points
   (a table of the non-Cf ones), the ideographic full stop (and its halfwidth form) read as '.', then strip and casefold. Tests: the
   reviewer's examples (ZWSP, ZWJ, BOM, soft hyphen, U+3002, U+FF61, variation selector, CGJ, NBSP, full-width, ligature). **Residual:**
   a Cyrillic or other homoglyph does not fold to the marker; it is harmless because the system recognises only the exact-ASCII grammar and
   the deterministic id (tested). **No database guard (0013), by choice:** the only role that writes ledger events is `finweb_app`, for
   user and system paths alike, so a trigger cannot tell the two apart; a session setting a system flag could be set by the same raw SQL
   the guard is meant to stop. It would add a trigger to a frozen, pin-protected function set without closing the stated hole. The
   Python rule keeps the marker out of every user-entered path; raw SQL as the application role remains out of scope (as the reviewer notes).
4. **Refused profiles.** `ingest_file` also raises `ProfileNotAdmittedError` for any non-synthetic CORPORATE_ACTION, IDENTITY, BENCHMARK or
   CALENDAR file whose source has a `refused` profile, before parsing (such kinds have no precision profile, so only `refused` is tested;
   a source with no profile, like `openfigi`, is not blocked). Test: `RefusedProfileBlocksEveryKindTests` (spy adapter 0 calls).
5. **Grant note.** `NEVER_GRANT` in `test_postgres_least_privilege.py` states that the application role must never hold CREATE on any schema
   or database, because `pinned_schema` relies on it, and `test_the_application_role_holds_no_create_anywhere` asserts it for every schema
   of the database and the database itself.
6. **`market-data/1.5`.**
   - *Domain (additive).* `Listing.composite_figi` (last field, default None) and `Instrument.share_class_figi` (last field, default None);
     `Listing.figi` is the exchange-level FIGI only. Frozen-dataclass equality is by id, so nothing in CP1 moves; the old positional
     construction still works (tested). The PostgreSQL `listing` and `instrument` tables are unchanged (the identity registry is in memory).
   - *A.6 as versioned data:* `marketdata/exchange_codes.py` (`CodeTable`, `A6`, version `market-data/1.5#a6/1`, statuses as the Quant
     gave them: only `HK` on XHKG is OBSERVED today; the US composite `US` is OBSERVED). The registry takes `code_table=` (default A6);
     `exchange_codes=` (MIC -> codes) replaces entries with CONFIRMED ones (tests; a human who has confirmed codes). The table version
     is recorded in the `asserted_by` of every FIGI row an assertion attaches.
   - *Level from the record:* `figi == compositeFIGI` is composite-level (`_is_composite`).
   - *Exchange-level attach:* only through an A.6 entry with status OBSERVED or CONFIRMED; MEMORY, TO_CONFIRM, an unknown MIC and another
     venue's code are quarantined (verdicts EXCHANGE_UNVERIFIABLE / EXCHANGE_MISMATCH); a security type inconsistent with the instrument
     (Common Stock with COMMON_STOCK, ETP with ETF) is quarantined (SECURITY_TYPE_MISMATCH). An attached record fills `figi`,
     `composite_figi` and the instrument's `share_class_figi` (item 7).
   - *Composite attach:* a composite record fills `composite_figi` only when its code is a known composite code with an attaching status
     and EXACTLY ONE active listing of that country (a MIC the code spans) carries the ticker; several is AMBIGUOUS + quarantine
     (COMPOSITE_NOT_UNIQUE), none is UNRESOLVED, a conflicting stored composite is quarantined and not overwritten.
   - *Symbol change:* only equal EXCHANGE-level FIGIs confirm; equal composites alone are UNCONFIRMED (a venue move keeps the composite).
   - *`delivered_dp`:* Eastmoney open/high/low/close 2 and Sina-US 4 are declared (A.3, A.4 item 7). The V2-at-ingest tests now run on the
     REAL profile without a patch (synthetic copies of Example 3-C: adj = raw - 7.50, SUBTRACTIVE, the same results); a stand-in profile
     without the declaration keeps the 1.4 PROFILE_INCOMPLETE rule tested. Mutation: removing the declaration fails 4 of 7 V2 tests.
   - *Not built:* resolving an observation that carries only a composite FIGI through `composite_figi` (Ruling 7.3 item 4, last bullet;
     `ExternalIdentifiers` has no composite field; not in the brief), and moving A.6 entries to OBSERVED (needs the human's downloads).

**Existing tests changed because 1.5 or a finding changed the behaviour (no other expected value moved).** Convention-set and profile-set
strings; the OpenFIGI evidence tests (a composite record no longer fills `figi`; the "no mapping" test now uses the MEMORY code `UW`);
the V2 tests no longer patch the profile; the field-bound assertions for Eastmoney and Sina-US; the two off-calendar FX tests (UNKNOWN ->
no history); the overlapping-window and "explained split" tests (C2-15); the exit-test pins of `market11`, `reconciliation`, `manifest` and
`profiles`.

### 15.20 CP2 closing round: C2-16 to C2-18, the ticker date, `market-data/1.6` and `1.7` (engineer; 2026-10-01; not yet re-reviewed)

Convention set recorded everywhere: **`market-data/1.7`** (1.6's changes are included; `CONVENTION_SET_ID`, rule ids, profile set
`market-data/1.7#profiles/3`, content unchanged). One migration: **0013** (with its `CHECKSUMS` line). `ANALYTICS_PINS` updated in the same
change (`market11`, `reconciliation`, `store`, `manifest`, `profiles`). Tests: `test_cp2_closing_round.py` (16), `FxSeriesExclusionDbTests`
(opt-in). Each mutation below was run in a scratch copy and made the named tests fail.

1. **C2-16 / Test V0-FX (1.7).** `ingest._admit_fx_series`, per (file, currency) series, inside the ECB calendar's coverage (rows outside it
   are not judged): any row on a non-fixing day excludes the WHOLE series (`V0_FX_OFF_CALENDAR`); any row after `D_ret` (new helper
   `fx_d_ret`, the same value Ruling 1.1a item 5's window uses) excludes it (`V0_FX_AFTER_RETRIEVAL`). The file stays in M; the series supplies
   no readings, so its dates are simply missing (missed fixings, then MISSING_FX_HISTORY at 5); a cross whose leg is excluded uses the
   remaining admitted legs, and with none the pair is NOT_IN_RELEASE (MISSING_FX_HISTORY). The exclusion is recorded as a `SeriesExclusion`
   with `listing_id None` and a `currency`, so the lookup's lineage notes carry `V0_FX_OFF_CALENDAR: ...` in both stores; **migration 0013**
   makes `md_series_exclusion.listing_id` nullable, adds `currency` and a CHECK that exactly one of the two is set (existing rows satisfy
   it; no grant changes). The projection digest includes the currency only when set, so a price-only projection keeps its digest. The
   lookup-time row filter of C2-14 stays as a second line (a store built without the build path). **Prices:** `_admit_by_calendar` also
   contradicts a series with a row inside the calendar's coverage dated after the latest session whose scheduled close is at or before the
   file's retrieval time (`_latest_closed_session`). Tests: P13 (every row one day early; as of Monday 6 January it served 1.02, now no rate),
   fallback to another valid series with 1 missed fixing, 5 missed gives MISSING_FX_HISTORY, rows outside coverage not judged, no calendar
   nothing judged, a correctly dated row after D_ret (a shift landing only on valid days), the price equivalent, and the PostgreSQL round trip
   with the same digest and lineage. Mutations: off-calendar rule off (3 of 7 fail), after-retrieval FX off (1), price after-retrieval off (1).
   The C2-14 build-path test and one C2-1 build test changed (a Saturday or Sunday row now excludes the whole series: NOT_IN_RELEASE).
2. **C2-17.** An exchange-level record with no security type is not consistent with the instrument, so it is quarantined
   (SECURITY_TYPE_MISMATCH). Test and mutation: `Figi16Tests` (1 fails when it attaches again). The identity tests that attach now give their
   records a type.
3. **C2-18.** An exchange-level record whose `compositeFIGI` differs from the composite the listing already holds is quarantined
   (`COMPOSITE_CONFLICT`); nothing is attached and no second composite row is added. Test and mutation as above.
4. **Ticker valid on the assertion date.** Exchange-level and composite attaches match the ticker valid ON the assertion's date (its source
   time, else its retrieval time), through the listing's ticker history (`_ticker_on`), not any date. Test and mutation as above.
5. **`market-data/1.6`.** Ruling 6.4a item 5: for every account holding units at the start of X1 OR of X2, both splits are CONFLICT_RATIO with
   cause `OVERLAPPING_SPLIT_WINDOWS`, nothing appended, valuation INSUFFICIENT_DATA + SOURCE_CONFLICT from X1, decided from the whole
   release (`_pair_partners`, `_pair_accounts`, `_pair_outcome`). If the calendar cannot cover both windows and cannot show the ex-dates more
   than 40 sessions apart, both splits take the coverage-gap outcome from X1 with no reason code and nothing is appended. A calendar that does
   show 41 or more sessions between them decides "disjoint". Tests: `C2_15_Item5_1_6Tests` (an account that sold before X2, an account that
   bought after X1, a second-split-only range, the gap pair, a decided-disjoint pair). Mutations: considering only the account holding at its
   own ex-date (2 fail); treating an unknown session count as disjoint (1 error). **Resolution record: not built.** `DataKind.RESOLUTION_RECORD`
   exists, but there is no record format, contract or adapter (`market11.UNBUILT` already lists "human resolution records"), so the midpoint-cut
   clearing path ("distinct") and the "one not real" path have nowhere to read from; building a format would be a new feature. The overlapping
   pair therefore stays failed closed until a record format exists. **Composite-only observation:** a test pins that it stays unresolved
   (`listing_id None`) even after the composite is attached, with and without a date (Ruling 7.3 item 4, 1.6).

**Existing tests changed because 1.7 or a finding changed the behaviour (no other expected value moved).** The convention and profile-set
strings; the three migration counts (13); the C2-14 and C2-1 build-path FX tests (whole-series exclusion); the same-venue identity test (its
record carries a security type); the exit-test pins.

## 16. CP3 — performance engine (engineer-proposed; not yet reviewed, not product law)

**Added 2026-10-01 by `engineer`. Plan only: no product code, migration or dependency is written or
changed by this section.** Authority and inputs: PRD §8, §9, §14, §15, §32, §34 and §38.3 (CP3) and §38.4
(HG2); PD-0006/0007 (layered states; `LIMITED` carries a value), PD-0015 (two valuation-time modes),
PD-0021 (§1 `listing_id`; OI-1), PD-0025 (`MetricResult.value` is `Decimal`), PD-0026 (ledger bounds),
PD-0030 to PD-0034; §6 and §13.E of this plan; §14.3 (replay) and §15.9, §15.13 to §15.20 (the market-data
consumer, the release pin, the state mapping); `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (`ledger-replay/1.3`)
and `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (`market-data/1.7`). Evidence markers as in §15: **[F]** fact
from a source document, **[J]** engineer judgment, **[A]** assumption to verify, **[Q]** depends on the
`quant-analyst`, **[H]** a human or PM step.

**Exit criterion [F]:** "known test portfolios reconcile and unsupported calculations return explicit
availability states" (PRD §38.3). **HG2 [F]** follows (PRD §38.4): the evidence list is in 16.10.

**What this section does not decide.** A fresh `quant-analyst` is writing
`methodology/CP3_PERFORMANCE_CONVENTIONS.md` in parallel (valuation, money rounding, lot depletion, cash flows,
TWR, MWR, annualization, income, FX attribution, denominators, reconciliation, HG2 data). This plan reads none
of its content. Every place where a method, convention, tolerance or sufficiency threshold is needed is a **plug
point**: a named, versioned, injected rule that is a **placeholder** until the Quant's document is implemented,
exactly as CP2a did (§15.13). The convention set reports `is_conformant == False` while any placeholder is
injected, and every result says so. Where this plan states a default behaviour it is a structural default (a
state may not be dropped; nothing is rounded silently), never a financial value. If the Quant's document and
this plan disagree, the document wins for method and this plan is amended.

### 16.0 Summary of the shape

1. **A pure engine over three pinned inputs.** `performance` (a new package) is a pure function of (a) the
   live ledger events at a pinned `ledger_version` L, (b) a `MarketDataPort` bound to one release M, and (c) an
   injected `PerformanceConventionSet`. No clock, no randomness, no I/O, no float. Same inputs, same canonical
   bytes (P12, NFR-001).
2. **It builds on CP1 and CP2, and adds no second analytics stack.** Positions come from `reconstruct` (§14.3).
   Prices and FX come from the port through the CP2 state mapping (`marketdata.states`). Valuation at a date reuses
   `assemble_valuation_inputs` (§15.9); the engine adds the arithmetic that §15.9 deliberately left out.
3. **Exact arithmetic everywhere inside; `Decimal` only at the envelope.** Internal values are `Fraction`.
   `MetricResult` (PD-0025) carries a `Decimal` produced by one presentation function that applies the Quant's
   rounding convention. A value that cannot be presented without a convention is `INSUFFICIENT_DATA` +
   `UNRESOLVED_CONVENTION`, as in CP1 (§14.3, Ruling 0.4.6). Irrational results (annualization, IRR) use
   bracketed exact numerics with certified rounding (16.6), so no library's transcendental functions are in the
   path.
4. **Every number travels in a `ComputedMetric`**: the `MetricResult`, the exact rational, every contributing
   cause (so a total's state is explained), the window actually used (PRD §14), the unit and currency, the method
   id, and the manifest id.
5. **A Computation Manifest pins every input**, and a result is reproduced by re-running with it (16.2).
6. **Results are computed on demand and not stored in CP3** (16.7).
7. **Unsupported means a state, never an exception and never a number.** A table-driven availability matrix test
   is the exit evidence (16.8).

### 16.1 Module boundaries

**Where it lives [J].** A new top-level package `src/performance/` (the deterministic engine) with two thin
neighbours outside it, mirroring `marketdata` / `marketdata_tools` and `corporate_actions_service`:

```
src/performance/               pure engine (no persistence, no adapters, no vendors, no clock, no float)
  conventions.py               PerformanceConventionSet: rule slots, ids, placeholders, is_conformant, open items
  numerics.py                  Fraction helpers; certified roots and rounding; RoundingPoint hooks; presentation
  ledger_view.py               the live event stream at L, ordered as replay orders it; flow classification
  flows.py                     CashFlow extraction (16.4)
  valuation.py                 positions x price-of-date x FX; native and reporting views; state propagation (16.3)
  periods.py                   Window, Frequency, Timeline (16.4)
  lots.py                      lot book per the Quant's depletion ruling; realized / unrealized (16.5; option A or B)
  returns.py                   TWR, simple return, annualization
  mwr.py                       deterministic IRR solver
  income.py                    dividends, interest, fees, taxes
  attribution.py               security / FX / income / fees / taxes decomposition and its reconciliation check
  reconciliation.py            the reconciliation checks (16.8) as pure functions returning findings
  states.py                    the only performance module that names a ReasonCode: cause -> (state, reason)
  results.py                   ComputedMetric, Cause, WindowUsed; canonical encoding
  manifest.py                  ComputationManifest, result digest, reproduce()
  engine.py                    orchestration: the public entry `compute(...)`
  evidence.py                  HG2 evidence-pack builder (pure; returns a structure) (16.10)
src/performance_service/       the I/O edge: loads events (persistence.ledger_replay_store), reads a release
                               (persistence.market_data_store), supplies F8-B suppressions, calls the engine
src/performance_tools/         human/CI command line: build an evidence pack to a directory; seed the demonstration
                               portfolio; never imported by product code (like marketdata_tools)
```

**Public surface.** Only `performance.engine`, `performance.results`, `performance.manifest` and
`performance.conventions` are importable by other packages; a static test checks it. The future AI layer reads
`ComputedMetric.to_canonical_dict()` and the manifest (P1: it never calls `compute`'s internals, never receives
a `Fraction`, and has no path to a number that did not come out of a `ComputedMetric`). The AI layer does not
exist yet; the test is written against the package-name rules below and extended when CP9 adds its package.

**Import boundaries, each an AST test in the style of `test_marketdata_boundaries.py` [J]:**
- `performance` may import: stdlib (no `time`, `random`, `secrets`, `socket`, `http`, `urllib`, `subprocess`,
  `multiprocessing`, `asyncio`, `sqlite3`, `math`, `statistics`, `numpy`/`pandas`), `domain.*`,
  `product_contract.*`, and from `marketdata` only the analytics-facing modules: `contracts`, `manifest`,
  `canonical`, `port`, `conventions`, `calendars`, `states`, `consumption`. **Not** `marketdata.adapters`,
  `ingest`, `files`, `store`, `resolver` (implementation), `verification`, `profiles` or `marketdata_tools`; **not**
  `persistence`, `corporate_actions_service`, `performance_service` or `performance_tools`.
- Nothing in `domain`, `marketdata`, `persistence` or `product_contract` imports `performance`.
- `performance` names no vendor word (`VENDOR_WORDS` in the existing test is reused), and never reaches a
  vendor-adjusted series (the Ruling 2.5 test is extended to `performance`: no `AdjustedQuote`,
  `adjusted_series`, `marketdata.verification`).
- Only `performance/states.py` names a `ReasonCode`; every other module passes `Cause` values (the same discipline
  as `marketdata/states.py`).
- Advisory, scenario and execution capability stay separable (PRD §31, P8): `performance` imports no package named
  `ai*`, `advisory*`, `scenario*`, `execution*`, `order*` or `broker*`; and each `ComputedMetric` carries
  `portfolio_state = ACTUAL`. A hypothetical portfolio never goes through `compute` (CP8 has its own entry and its
  own manifest kind), so a scenario figure cannot be shaped like a holding.
- No `float` anywhere in `performance`: a test scans annotations, calls to `float(`, float literals, `math` and
  `/` applied outside `Fraction` construction is covered by the property tests rather than the scan (an AST scan
  cannot type-check division; the scan bans the name `float`, float literals and the imports above).
- Determinism hygiene as for `marketdata`: no clock calls, no `uuid4`, no iteration over a `set` or an unordered
  `dict` that reaches output (every output tuple is sorted by a stated key).

**One CP1 change is proposed and needs a PM decision (open question 1):** a public, pure
`domain.replay.live_events(events, ledger_version)` (the existing private `_select_live`, exposed, same code, no
behaviour change), so the engine and replay cannot disagree about which events are live at L (reversals,
corrections). The alternative, reimplementing reversal handling in `performance`, is rejected: two readers of
"which events are live" is exactly the divergence the CP1 reviews spent three rounds closing. The change is
additive, `CONVENTION_SET_ID` is unchanged, and the CP1 golden and replay tests are re-run unchanged as the proof.

### 16.2 Inputs, the Computation Manifest, and reproducibility

**Inputs [F].**
1. **CP1 replay at (D, L).** `reconstruct(events, D, L)` gives native-currency positions and cash at date D as
   known at ledger version L (§14.3: `event_date <= D`, `ledger_seq <= L`, reversals retroactive in economic time
   and effective by version). L is one number for a whole computation: every valuation date in a window is
   replayed "as known at L", so a series is internally consistent. A later L may restate an earlier date (a
   correction); both are reproducible from their manifests.
2. **CP2 market data through the port pinned to release M.** `quote_on` / `fx_on` with the injected
   `market-data/1.7` conventions; the typed outcome and the lookup's `date_used`, `missed_count`, `freshness`,
   `reconciliation`, `lineage_notes`, `synthetic` and `consumed` are kept per input and mapped to
   `(state, reason)` only through `marketdata.states.price_input_state` / `fx_input_state` (the only module that
   knows the CP2 table; CP3 does not re-implement it).
3. **A `PerformanceConventionSet`** (16.9 plug points; the Quant's ids).
4. **F8-B valuation suppressions** (`SplitReport.suppressions`; PD-0030 §2, `market-data/1.6`). Quantity and RAW
   price are in different units on a suppressed date, so valuation of that `(account, listing, date)` is
   `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` (or no code for a calendar coverage gap). The engine takes the
   suppressions as an input (`SplitSuppressions`), never computes or applies splits. See open question 4 on how
   they are produced without the engine writing to the ledger.
5. **Reporting currency** from the portfolio, **window / frequency** from the caller (PRD §14), **valuation mode**.
   Only HISTORICAL_AS_OF is implemented (PD-0015; Current mode is `UNBUILT` in CP2, §15.16 item 9). "Current value"
   in CP3 is the as-of-D valuation with the freshness the port reports; the engine never reads a clock, so "now" is
   the caller's D. A `CURRENT` request is refused as a typed `UnsupportedValuationModeError` at the engine entry
   (a programming-contract refusal, not a metric state; see open question 7).

**Computation Manifest** (`finweb.computation_manifest/1`; extends §6.2, which pre-dates CP1/CP2). Immutable,
canonical JSON (the `marketdata.canonical` encoder: no float, sorted keys, ASCII), `manifest_id = sha256(canonical
JSON of the other fields)`. Fields:

| Field | Meaning |
|---|---|
| `schema`, `engine_id` | `performance/<engine_version>`: a constant bumped on any change to a computation, like an adapter version; the exit test pins the source hashes of the engine modules as `ANALYTICS_PINS` does for market data |
| `state_kind` | `ACTUAL` (P8) |
| `portfolio_id`, `reporting_currency` | |
| `ledger_version` L; `ledger_digest` | L is the pin; `ledger_digest` is `sha256` of the canonical encoding of the live events with `ledger_seq <= L`, so a restored or tampered ledger is detected instead of trusted (CP1 review R3-2: the pin guard depends on `recorded_at`) |
| `as_of` D; `window` (`start`, `end`, `frequency`, `lookback_label`) | the window the caller asked for; the window actually used is in each result |
| `valuation_mode` | HISTORICAL_AS_OF |
| `conventions` | `{ledger_replay: "ledger-replay/1.3", market_data: "market-data/1.7", performance: "performance/<n>", and each performance rule id}` plus `is_conformant`, `open_items` (placeholders and unbuilt rules, listed so no result can hide them), each as the convention sets already do (§15.13) |
| `market_data` | `release_id`; the `DataSetRef` list (quote, FX, corporate-action, calendar, benchmark where used), each with its sorted `consumed` `(file_sha256, adapter_id, adapter_version)` and `range_start/range_end` merged over every date the run looked up; `contains_synthetic` |
| `calendar_files` | the `FileRef`s of the calendar files actually counted (they are in `consumed` today; the manifest lists them apart so an audit can name them) |
| `split_suppressions_digest` | the digest of the `SplitReport` the run was given (16.2 input 4) |
| `methodology` | the registry entry ids and versions invoked (PRD §33; the registry is empty until populated, so the Quant's document ids stand in until then, flagged) |
| `numerics` | the declared presentation precision and rounding table id, and the solver tolerance ids, all from the convention set |

**Result envelope.** `ComputationResult(manifest_id, metrics, result_digest)`, with `result_digest = sha256(canonical
JSON of the metrics)`. The digest is outside the manifest, so the manifest identifies the *question* and the digest
the *answer*.

**Reproducibility, stated as a procedure [F, §6.4].** Given a manifest: (1) load the ledger events with
`ledger_seq <= L` and verify `ledger_digest`; (2) load release `release_id` and verify every cited file hash
(`read_release` already checks the projection digest, §15.17); (3) construct the cited convention set by id
(an unknown id is refused, not defaulted); (4) run `compute` with the manifest's own parameters; (5) compare the
manifest the run produces with the given one (the consumed-file set must be equal in both directions: a file the
re-run reads that the manifest does not cite is a hidden input, a defect) and compare `result_digest`.
`reproduce(manifest, events, port, conventions)` implements it and returns a typed report (`REPRODUCED`,
`LEDGER_DIGEST_MISMATCH`, `FILE_NOT_CITED`, `RESULT_DIFFERS`, ...). The CP2 pattern of "no query reads latest"
carries over: the engine has no way to say "latest" because the port is bound to M and D is an argument.

### 16.3 The valuation layer

**Shape.** For a date D: positions `(account, listing)` and cash `(account, currency)` from replay at (D, L),
priced and converted:

```
HoldingValuation(account_id, listing_id, quantity: MetricResult (from replay, untouched),
                 native_currency, native_price (Fraction|None), native_value (Fraction|None),
                 price_input: InputState, price_date_used, price_missed_count,
                 fx_rate (Fraction|None), fx_input: InputState, fx_date_used,
                 reporting_value (Fraction|None), state, reason, causes: tuple[Cause])
CashValuation(account_id, currency, native_amount, fx..., reporting_value, state, reason, causes)
PortfolioValuation(as_of, ledger_version, native_view, reporting_view, holdings, cash,
                   total: ComputedMetric, priced_subtotal: Optional[...], excluded: tuple[...])
```

- **Arithmetic is exact:** `native_value = quantity x price`; `reporting_value = native_value x fx_rate`, `fx_rate` the
  port's exact `Fraction` (an `ExactRatioRate` cross is already exact, Ruling 1.3). The price is the RAW as-traded
  close of date D from the port, and the quantity is the replayed quantity at D (post-split on and after the ex-date), so
  the two are in the same unit by construction. No adjusted series is read (Ruling 2.5); the engine derives its own
  return basis from RAW price x as-of quantity, plus ledger flows.
- **Two views, because a missing rate must not hide a native fact (§13.E).** The *native view* (per-holding native
  value, per-currency native totals) needs no FX and is computed whenever the price is available. The *reporting
  view* additionally needs FX; a missing, stale or conflicting rate degrades only the reporting view.
- **State propagation.** Each holding and cash entry gets its `(state, reason)` from the *worst-of* its inputs
  (quantity from replay: `NOT_RECONSTRUCTABLE`, `LEDGER_INCONSISTENT`, `UNRESOLVED_CONVENTION`; price via
  `price_input_state`; FX via `fx_input_state`; F8-B suppression), and keeps **every** contributing `Cause`
  (`input_ref`, state, reason, note) so no total's state is unexplained. Structural default (not a threshold): any
  `INSUFFICIENT_DATA` input makes the entry `INSUFFICIENT_DATA` with no value; else any `LIMITED` makes it
  `LIMITED` with the value; else `AVAILABLE` (a one-session-stale input stays `AVAILABLE` + `STALE_DATA`, PD-0006).
  `AVAILABLE` and `LIMITED` carry a value and `INSUFFICIENT_DATA` does not (PD-0007), so the `MetricResult`
  coupling rules are met by construction, and the existing envelope validator is the guard.
- **Totals.** `total = sum of entry reporting values`. The aggregation rule is a plug point **[Q]**
  (`AggregationRule`): the structural default above (worst-of) holds, and the Quant has proposed (Ruling 4.7 item 3,
  for CP3 to adopt or replace) that a market-value aggregate including any unpriced holding is `INSUFFICIENT_DATA` +
  `MISSING_PRICE_HISTORY`, never a partial total presented as the total. The engine implements the rule as
  data: `AggregationRule.combine(entries) -> (state, reason, excluded)`; "value of priced holdings" with an
  unpriced count is a separate metric id that exists only if the Quant and design admit it (MD-OI-11), and an
  `excluded` weight is stated as a number only by the Quant's measurement rule (MD-OI-4; weights are CP4/CP5).
  The single reason code shown when several causes apply comes from an ordered table in `performance/states.py`
  (replay's `_REASON_PRIORITY` is the precedent): an **engineer choice, flagged for the Quant**; the full cause
  list is always kept, so the choice affects presentation only.
- **Cash** is a first-class asset (PRD §9.4): a cash balance in currency C needs FX C to reporting at D; cash in the
  reporting currency needs none. Negative cash is a valid signed state (Ruling 1.3) and is valued, not clamped.
- **Freshness and timestamps (P10).** The valuation keeps `date_used`, `missed_count`, freshness state and the
  rate's fixing date per input; the HG2 pack prints them (16.10). A same-day lookup needs a covering calendar
  (C2-1), so **registered calendar files are a precondition of any valuation** (otherwise every price is
  `INSUFFICIENT_DATA` with no reason code, "freshness UNKNOWN"): the PD-0034 calendar drafts must be registered
  by the owner before CP3 produces real values **[H]**.
- **Mapping to metric ids.** `portfolio_value`, `holding_value`, `cash_value` and `currency_exposure_native`, each a
  `ComputedMetric`. Gain/loss and returns (16.5) are separate metrics built on these.
- **The reporting-currency conversion of basis (OI-1)** is a CP3 computation: the replay's native basis and the
  lot's acquisition date are translated at the **transaction-date** rate (HG1 round 4 §7.3; the Quant's OI-6 says
  a purchase funded by a conversion still uses the market rate of the BUY date, never the user's conversion
  rate). Each lot date needs an `fx_on` lookup; a missing one is `MISSING_FX_HISTORY` for that lot's
  reporting-currency basis, while the native basis stays available.

### 16.4 Cash-flow extraction and the period / frequency engine

**Extraction.** `performance.ledger_view` takes `live_events(events, L)` and orders it exactly as replay does
`(event_date, rank, ledger_seq)`. Each event is classified into a `FlowClass` by a **table that is data** (an
injected `FlowTable`, the Quant's):

| `FlowClass` (names proposed) | Events (draft, from PRD §9.5/§9.6 only) | Treatment |
|---|---|---|
| `EXTERNAL` | `DEPOSIT`, `WITHDRAWAL`; an unpaired `TRANSFER_IN`/`TRANSFER_OUT` | enters or leaves the portfolio: not a gain or loss (PRD §9.6) |
| `INTERNAL` | a paired transfer between accounts of the same portfolio (the pairing is replay's `_pair_transfers`, exposed read-only); `BUY`/`SELL` (cash and security swap); `CURRENCY_CONVERSION` | not return |
| `INCOME` | `DIVIDEND`, `INTEREST` | return component |
| `COST` | `FEE`, `TAX`, `INTEREST_CHARGED` | return component |
| `NON_FLOW` | `SPLIT`, `REVERSAL` (already applied by live selection) | none |
| `OPENING` | `OPENING_POSITION`, `OPENING_CASH` | the start state of a snapshot-only account, not a flow inside the window |

The table's *values* are **[Q]**; the engineer's draft above uses only what PRD §9.5/§9.6 says and marks every row
the PRD does not settle as a placeholder (for example, whether an external security `TRANSFER_IN` is valued at the
market price of its date and treated as a flow of that value; whether `FEE`/`TAX` are flows or costs for the TWR
denominator; whether a pay-date or ex-date governs income timing, §4 of the CP1 conventions; the timing of a flow
within its day: start or end of day, OI-2). A `FlowTable` row that is a placeholder makes the convention set
non-conformant. Extraction yields `CashFlow(date, account, currency, native_amount, flow_class, event_id,
reporting_amount (Fraction|None), fx_input, cause)` with the reporting amount converted at the **flow date's**
rate (PRD §8.3: "historical FX corresponding to the valuation/cash-flow date; never today's rate"), so each flow
has its own FX lookup and its own state. Every flow keeps its `event_id`, so any figure traces to the ledger
(P9).

**Window, frequency and the timeline (PRD §14).**
- `Window(start, end, lookback_label, frequency)`: lookback `1Y/3Y/5Y/MAX`, frequency `DAILY/WEEKLY/MONTHLY`,
  defaults `3Y`/`WEEKLY`/reporting currency; "maximum available" resolves to the earliest date for which the
  portfolio is reconstructable and priced, and the **window actually used** is stated in every `ComputedMetric`
  (PRD §14 "every metric must state the actual window/frequency used"). A snapshot-only account is
  `NOT_RECONSTRUCTABLE` before its snapshot date S (CP1 §8), so a window may begin only at or after S; a request
  that starts earlier is shortened to S with the shortening stated, or is `INSUFFICIENT_DATA`/`NOT_RECONSTRUCTABLE`,
  whichever the Quant rules **[Q]**.
- **True TWR does not depend on the sampling frequency [J].** Chain-linking at every external-flow date is exact, so
  the engine's *valuation boundaries* are `{window start, window end} union {every EXTERNAL flow date in the window}`
  (plus the Quant's boundary rule for split or corporate-action dates, if any). The *frequency* governs the
  **sampled series** the engine also emits (dates, value, cumulative TWR, period return), which CP4 (volatility,
  beta, correlation) and the charts consume. A week's end date is a calendar-rule question **[Q]**
  (`SamplingCalendarRule`, built on the CP2 `CalendarSet`: last session of the week of which calendar? a common
  session across US/HK/CN?). Until it is ruled the series emitter is a placeholder that returns the daily series
  and says so; it is not needed for CP3's headline metrics.
- **Cost.** Each boundary needs a replay at (date, L) and one lookup per held listing and currency. First
  implementation: call `reconstruct` per boundary date (correct, simple). Measure before optimising; if needed,
  `reconstruct_series(events, dates, L)` (one fold, snapshots at the dates) is added with a test that it equals
  repeated `reconstruct` byte for byte (16.8). See risk 8.
- A boundary whose valuation is `INSUFFICIENT_DATA` makes every metric that needs it `INSUFFICIENT_DATA` with that
  boundary's cause listed. The engine does not skip a boundary, shorten the chain or interpolate; whether a coarser
  chain is acceptable is a method choice **[Q]** and defaults to "no".

### 16.5 Metric families as pure functions

Each family is a pure function `f(valuations, flows, window, conventions) -> ComputedMetric` (or a small tuple of
them) with the states below. Formulas, denominators, tolerances and every threshold are **[Q]** and are read from
the convention set; the engineer fixes the *interfaces, the states and the numerics*.

| Metric id (proposed) | Inputs | Unavailable / limited states it returns (never an exception, never a number) |
|---|---|---|
| `portfolio_value`, `holding_value`, `cash_value` | 16.3 | `INSUFFICIENT_DATA` with `NOT_RECONSTRUCTABLE`, `LEDGER_INCONSISTENT`, `UNRESOLVED_CONVENTION`, `MISSING_PRICE_HISTORY`, `SOURCE_CONFLICT`, `STALE_DATA`, `MISSING_FX_HISTORY` as the inputs say; `LIMITED` for 2-4 missed sessions or fixings (the CP2 table) |
| `absolute_gain_loss` | value at end, value at start, `EXTERNAL` flows | as value; plus `INSUFFICIENT_DATA` if the start state is not reconstructable |
| `simple_return` | the Quant's denominator | `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION` until a denominator is ruled; a zero or negative denominator is a state (`CALCULATION_ERROR` is reserved for an engine limit, so this case needs a code the Quant names, open question 6) |
| `twr` | boundary valuations, `EXTERNAL` flows, flow-timing rule | any boundary `INSUFFICIENT_DATA` -> `INSUFFICIENT_DATA` (cause listed); a zero starting value for a sub-period -> the Quant's rule; a window with no history -> `INSUFFICIENT_DATA` |
| `annualized_return` | TWR (or MWR) and the window length in the Quant's day count | `INSUFFICIENT_DATA` when the window is shorter than the Quant's minimum (a sufficiency threshold, **[Q]**), and `LIMITED` where the Quant rules so |
| `mwr_irr` | dated `EXTERNAL` flows (reporting amounts) and the terminal value | `INSUFFICIENT_DATA` when there is no sign change, no unique root under the Quant's bracket, the history is partial (snapshot-only or missing early history: PRD §9.3 "exact money-weighted return unavailable without transaction history"), or the solver does not certify within the Quant's tolerance (`UNRESOLVED_CONVENTION`, never a guess) |
| `income_total`, `income_by_type`, `fees_total`, `taxes_total` | `INCOME` and `COST` flows at flow-date FX | `MISSING_FX_HISTORY` for a flow without a rate; native-currency totals stay available; a dividend whose recorded amount disagrees with the corporate-action expectation is flagged per the Quant (the CP1 §4.1 note: "the CP3 check of recorded against expected") |
| `realized_gain_loss`, `unrealized_gain_loss` (native and reporting) | the lot book (below), prices, FX at lot dates | `MISSING_COST_BASIS` where a lot's basis is unknown (never fabricated, PRD §9.3); `UNRESOLVED_CONVENTION` where depletion is not ruled; `LIMITED` for a partly known basis only if the Quant rules (CP1 §6.4 reserved it) |
| `fx_attribution` (security, FX, income, fees, taxes, residual) | all of the above | `MISSING_FX_HISTORY`; `INSUFFICIENT_DATA` if any component is; `CALCULATION_ERROR` if the reconciliation residual exceeds the tolerance (the check failed: an engine defect or a method gap, loud) |

**Lots, realized and unrealized (depends on the Quant's depletion ruling).** CP1 deliberately reports remaining basis
only where every admissible depletion method agrees and `UNRESOLVED_CONVENTION` otherwise (§14.3). Realized gain
needs a method. Two designs, a PM/Quant decision (open question 2):
- **Option A (recommended): one lot engine, in `domain`.** The Quant's ruling becomes `ledger-replay/1.4`, replay
  emits per-lot state and realized lots, and CP3 consumes them. There is one truth for "cost basis", so a position
  cannot show "basis unresolved" beside "realized gain available". Cost: a reviewed CP1 module changes (additive
  output, a new convention-set id, the CP1 golden re-ratified by the Quant).
- **Option B: a CP3-local `lots.py`** with the ruled method, cross-checked against replay wherever replay's remaining
  basis is `AVAILABLE` (the two must agree exactly: test R3 in 16.8). Cost: two lot engines, and the unresolved cases
  of replay stay unresolved while CP3 resolves them: a visible inconsistency the UI must explain.
Either way the lot book is exact `Fraction`, keyed `(account, listing)`, ordered as replay orders events, carries the
acquisition date and currency (for the OI-1 translation) and unknown basis as unknown, and money rounding applies only
at the Quant's named points (16.6).

**FX attribution and its reconciliation check.** Decomposition `security movement + FX movement + income - fees -
known taxes` (PRD §8.4, §15.2), by the method the Quant rules (it must decide how multi-period components link:
arithmetic, geometric or log-linked). The engine implements the ruled method and always computes the **reconciliation
residual** `reported total return - sum(components)` as an exact `Fraction`. It is never absorbed into a component,
never hidden, and compared with the Quant's tolerance (PRD §15.2: "must reconcile within documented numerical
tolerance"). A component named "interaction" or "other" exists only if the Quant defines it. With exact arithmetic
and an exactly additive method the tolerance is 0; with certified-rounded irrational steps it is the stated bound.

### 16.6 Exact arithmetic, numerics and rounding

- **Exact core [J].** Quantities, prices, rates, flows, values and ratios are `Fraction`s; sums and products are
  exact; nothing reads the global `decimal` context (the private-context discipline of `replay.py` is reused for
  the one conversion at the envelope). Magnitude guards as in CP1 (`_MAX_DECIMAL_SPAN`): an absurd input is a state
  (`CALCULATION_ERROR` + detail), not a hang or an exception. Chained products over hundreds of boundaries create
  large rationals; a size guard (bits of numerator and denominator) turns a runaway into `CALCULATION_ERROR`
  (risk 8).
- **Rounding is a convention, applied only at named points [Q].** `numerics.RoundingPoint` is an enum of the places
  a convention may round (proposed names: `FX_CONVERSION`, `CASH_FLOW_TO_REPORTING`, `LOT_ALLOCATION`, `PRESENTATION`,
  `RATE_DISPLAY`). The convention set maps each point to `EXACT` or a rule (ISO 4217 minor unit, rounding mode,
  allocation rule that keeps removed plus remaining equal to the original: OI-8). **No rounding literal and no
  `quantize` appears in the engine**; a test greps for them. **Engineer position (advice, not a ruling):** keep
  everything exact internally and round at presentation only, because it keeps TWR invariant under an extra
  zero-flow boundary and keeps the reconciliation residual exactly zero for an additive method. If the Quant
  rules that real cash is booked in minor units at specified points (a converted flow, an allocated sale part),
  those are `RoundingPoint`s with the rule, and the reconciliation tolerance then expresses the accumulated rounding
  (at most N half-units), which the Quant states.
- **The envelope is `Decimal` (PD-0025), so presentation is one function:** `present(exact, point, spec) ->
  MetricResult`. If `spec` rounds, the value is `AVAILABLE` (or the incoming state) with the rounded `Decimal`, and
  the exact rational stays in `ComputedMetric.exact`. If there is no rule and the exact value does not terminate, the
  result is `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION` (the CP1 precedent). Returns and rates need a *return
  presentation precision* (significant digits or decimals): **[Q]**.
- **Irrational results with no library in the path.** Annualization `(1+R)^(1/y) - 1` and IRR need roots. The engine
  uses **certified numerics** (`numerics.py`), exact integer/Fraction arithmetic only:
  - `rational_root(x, n, eps)` returns a bracket `[lo, hi]` of dyadic rationals with `lo^n <= x <= hi^n`, `hi - lo < eps`
    (integer bisection; `n` and `eps` from the convention set).
  - **IRR as a polynomial root [A, to be confirmed against the Quant's day count].** If the day count is Actual/365
    (or any fixed denominator q), then with `y = (1+r)^(1/q)` each flow's discount factor is `y^(-days_i)`, an integer
    power, so `NPV(y) = sum CF_i * y^(-days_i)` is a rational function of `y`. The solver brackets and bisects `y` with
    exact `Fraction` evaluation (sign test only), then reports `r = y^q - 1` as a certified bracket. No `exp`, `ln` or
    `**` with a fractional exponent is ever evaluated. A convention with a non-fixed denominator (Actual/Actual
    periods) is handled by the Quant's stated period fractions being rational; a genuinely irrational exponent is not
    supported and is reported `UNRESOLVED_CONVENTION`.
  - **Certified rounding.** A presented value is the round of a *bracket*. If the bracket does not straddle a rounding
    boundary of the Quant's precision, the rounded value is determined and identical on every machine; if it does,
    the bracket is refined (bounded steps) and an unresolvable tie is `UNRESOLVED_CONVENTION`, never a coin flip. The
    tolerance, root bracket, maximum iterations and the starting bracket for IRR are **[Q]** (a "no unique root" rule
    needs the Quant: Descartes' sign-change count on the flow series is a cheap, exact, deterministic screen the engine
    can run, and the ruling says what to do on several sign changes).
  - **Why not `Decimal.ln/exp/power` or `float` [J]:** the C `decimal` module's `power` is documented as "almost always
    correctly rounded" and depends on the libmpdec version; a different Python build could change the last digit of an
    audit-critical number. The certified approach has no such dependence. No third-party solver is needed.
- **No new dependency is proposed.** `fractions`, `decimal`, `itertools` and integer arithmetic suffice.

### 16.7 Storage: results are not persisted in CP3

**Decision [J]: compute on demand from the manifest; store nothing in CP3.** Reasons:
1. **Everything an answer depends on is already immutable and pinned.** The ledger is append-only with a version pin
   (CP1, migration 0003/0004/0008), a release is sealed and digest-checked (CP2, 0009 to 0013), and the conventions are
   versioned ids. A stored result would be a *second copy* of a value that can always be recomputed, and a second copy
   is the way a number and its evidence come to disagree (P9). The manifest plus the digest *is* the audit record.
2. **A stored result needs its own immutability, supersession and migration story** (append-only table, grants,
   guard triggers, review rounds), for no CP3 requirement. PRD §38.3 CP3 asks for correct, reconciling,
   explicitly-stated metrics, not for a results store.
3. **Reproducibility is a CP3 deliverable** and is tested by recomputing in a new process (16.8); a cache would let a
   bug hide behind a stale value.
4. **Performance is unmeasured.** The first implementation replays per boundary; if a window is too slow for
   NFR-006 the answer is the incremental `reconstruct_series` (a pure optimisation with an equivalence test), then,
   only if still needed, a **derived, rebuildable result cache keyed by `manifest_id`**, append-only, never an input to
   anything, built when CP7's UI or CP6's Proof Packets need it.
What *is* persisted for HG2 is a file artifact, not a table: the evidence pack (16.10) written by the tool to a
directory (manifest, result digest and the rendered sections), so the gate package cites hashes.
No migration is proposed in CP3. (If a result cache is later added it is a new numbered migration with its own
`CHECKSUMS` line; 0001 to 0013 stay frozen.)

### 16.8 Testing

1. **Golden fixture `cp3_golden/1` [Q authors; H none].** It extends `cp1_golden` (the same portfolios and events
   where useful, plus the synthetic market data that valuation needs: RAW closes, ECB-format fixings, calendars) with
   **hand-derived** expected values from the Quant: valuations at each date, flow classification, TWR per
   sub-period and linked, IRR (a case with a closed form and a case that needs the solver), annualized return,
   realized and unrealized per lot, income, the FX attribution components and the residual, and the expected state of
   each unsupported case. As for `cp1_golden`, the engineer's loader reads only the Quant's JSON, pins its counts and
   hash (`FIXTURE_PINS`), and never derives an expected value from engine output. The market-data half goes through
   the **real path** (synthetic files in the real parsers' layouts -> ingest -> release -> port, as the CP2 exit test
   does, both stores), so the golden test also proves CP2 feeds CP3.
2. **Reconciliation tests (internal consistency, exact, tolerance from the convention set)** over the golden
   portfolios and generated variants. These prove the engine is self-consistent; they do **not** replace hand-derived
   values (a consistently wrong method reconciles perfectly):
   - **R1 value bridge:** `V_end - V_start = EXTERNAL flows + security effect + FX effect + income - fees - taxes`
     (residual exactly 0, or within the Quant's tolerance).
   - **R2 cash:** the sum of cash-affecting flows per currency reproduces the replayed cash change per currency.
   - **R3 lot cross-check:** the lot book's remaining units and basis equal replay's wherever replay is `AVAILABLE`.
   - **R4 TWR invariance:** adding a boundary on a date with no flow leaves TWR unchanged (exact).
   - **R5 no flows:** TWR equals the price-and-FX return of the held value.
   - **R6 IRR:** NPV at the certified rate is within the bracket's width; a single deposit and terminal value gives the
     closed-form annualized return; no sign change gives a state.
   - **R7 deposits are not gains:** adding an `EXTERNAL` deposit and changing nothing else leaves TWR unchanged and moves
     gain/loss by 0.
   - **R8 internal transfer:** a paired transfer between accounts changes no return and no total (PRD §9.6).
   - **R9 identity:** reporting currency equal to a holding's native currency has zero FX effect for it; a portfolio
     with constant FX has zero FX attribution.
   - **R10 same-input same-output:** event order shuffled within the ledger's own ordering rules, reversal handling, and
     L-pin behaviour (a later L restates, an earlier L does not change).
   - **R11 series equivalence** if `reconstruct_series` is built: byte-identical to repeated `reconstruct`.
3. **Determinism.** The golden result's canonical JSON is byte-identical across runs, across processes with
   `PYTHONHASHSEED` 1, 2 and random (the CP2 exit pattern), against the PostgreSQL store, and after a manifest
   round trip through `reproduce` (16.2). `ANALYTICS_PINS`-style hashes of the engine modules are committed (so an edit
   fails until the pin moves in the same commit) with a negative control showing the pin check can fail.
4. **Exit-criterion test: the availability matrix.** A table `METRIC x CONDITION -> expected (state, reason)`,
   authored by the Quant where it is a method question and by the engineer for pure plumbing, covering every metric id in
   16.5 against: snapshot-only portfolio (before and after S); missing cost basis; unknown basis in one lot; no price for
   a holding (no admitted source; contradicted series; stale 1, 2-4, 5 sessions); missing FX history (and CNH); FX
   disagreement; F8-B suppression; unresolved depletion; non-terminating value without a presentation rule; no sign change;
   empty window; window shorter than the minimum; single flow; zero denominator; synthetic market data. The test asserts
   that no combination returns an exception, a bare `None`, a zero or a value with a non-`AVAILABLE`/`LIMITED` state, and
   that **every `INSUFFICIENT_DATA` names its causes**. It also asserts that adding a metric id without a matrix row
   fails (so a new metric cannot ship without its unsupported cases).
5. **Mutation evidence per increment** (as in the CP2 fix rounds): a scratch-copy mutation of each rule (wrong flow
   class, flow-date FX replaced by valuation-date FX, a dropped cause, a rounded intermediate, the residual folded into a
   component) must fail a named test. Reported with each increment.
6. **Boundary tests** of 16.1; a test that every `ComputedMetric` carries a manifest id, window and method id;
   a test that no module in `performance` calls `quantize`, `round`, `float` or reads the decimal context.
7. **Reviewer and Quant roles.** The golden values are the Quant's; the engineer reports actual results, and a fixture
   that disagrees with the code is a finding for the Quant, not a value to adjust (CLAUDE.md). An independent
   `technical-reviewer` pass follows CP3f and precedes HG2.

### 16.9 Plug points and the dependency list on the Quant's CP3 document

Each is an injected, versioned, id-bearing rule in `PerformanceConventionSet`, and each starts as a clearly named
placeholder (`placeholder/<name>/0`) that makes `is_conformant` False. None is decided here.

| Plug point | What the Quant's document must supply |
|---|---|
| `ValuationRule` | valuation cutoff relative to the as-of date label (MD-OI-1, OI-2 of the CP1 conventions); the as-of semantics of a flow within its day; whether a stale-but-available price needs a caveat in the value |
| `AggregationRule` | state lattice of totals; the unpriced-holding rule (Ruling 4.7 item 3 proposal) and "value of priced holdings" (MD-OI-11); the single reason code shown (priority table) |
| `RoundingTable` (OI-8) | ISO 4217 minor-unit table as reference data, rounding mode, allocation rule, which `RoundingPoint`s are exact, and the return presentation precision |
| `LotDepletionRule` | the method for every case CP1 reserved (0.4.4, 0.4.5 (c), §7 condition 3), equal-unit-cost multi-lot (OI-9), fee capitalization (Note 1), partial-basis state (§6.4) |
| `FlowTable` | the class of every event type; external security transfers; income timing (pay or ex date, §4); debit interest; fee and tax treatment |
| `TwrRule` | sub-period definition, flow timing, start/end valuation, zero or negative start value, chain-linking |
| `MwrRule` | the cash-flow sign and dating convention, day count, bracket, tolerance, root-selection, partial-history sufficiency |
| `AnnualizationRule` | day count, compounding, minimum window length, `LIMITED` band |
| `WindowRule` | lookbacks, frequencies, week and month end dates, "maximum available", the shortening rule near a snapshot date |
| `IncomeRule` | income return definition; recorded-versus-expected dividend check; withholding |
| `AttributionRule` | decomposition and linking method, the FX effect definition (local-price effect, translation effect, cross term), the tolerance |
| `ReconciliationRule` | tolerance values and which checks are blocking (R1 to R11 map to Quant-owned names) |
| `SufficiencyRules` | every threshold that moves `AVAILABLE`/`LIMITED`/`INSUFFICIENT_DATA` for a CP3 metric |
| `DenominatorRule` | the denominator of every percentage |
| `HG2DataRule` | the HG2 demonstration portfolio's required content and the numerical tolerances to state (16.10) |

The engineer needs the document's **ids** (`performance/<n>`, one per rule) and **fixture** to replace a placeholder;
until then the placeholder's behaviour is "return `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION` with the rule name in
the cause", which is honest and never a number. Mechanical plumbing (valuation of positions at the port's price and
rate, cause propagation, manifest, canonical encoding, boundaries) does not wait for the document.

### 16.10 HG2 support: the evidence pack the engine must be able to produce

**Context [F].** PRD §38.4 HG2 requires a demonstration portfolio with representative US, Mainland China and Hong
Kong holdings plus USD/HKD/CNY cash and meaningful transaction history. **No admissible real CN or HK price source
exists** (PD-0031; STATUS 17, open: written permission, a paid personal-use plan, or synthetic prices), US real prices
are limited to the last 100 sessions (Alpha Vantage free tier, PD-0032), and FX is the ECB's. Under Ruling 4.8 any
market-data version that contains a synthetic file marks **every** result computed from it as synthetic, and such a
result may never be presented as a real market fact.

**What the engine must be able to produce, stated so the owner can choose without the engine changing [J]:**
- **Demonstration A (the committed proof): a fully synthetic, hand-derivable portfolio** (US, CN, HK holdings;
  USD, HKD, CNY cash; deposits, withdrawals, an internal transfer, buys, partial sells, dividends, a fee, a tax, a
  split, a conversion, a snapshot-only account; a missing-cost-basis holding; a holding with no admitted price
  source) on synthetic prices and synthetic or ECB-format FX. Every output is labelled `synthetic`. Its expected values
  are the Quant's (the `cp3_golden` fixture can be the same data, so the HG2 pack is also a regression test).
- **Demonstration B (optional real slice):** the same engine over real US prices (last 100 sessions) and real ECB
  fixings for a US-only portfolio, to show the real data path end to end; needs the owner's downloads and registered
  calendars **[H]**. It is a slice, not the cross-border proof, and is labelled real or synthetic per input.
- Mixed releases (real US plus synthetic CN/HK) are allowed by the port but every result is `synthetic` (Ruling 4.8);
  the pack says which holdings used which.

**Evidence sections, one per PRD §38.4 item, each generated by `performance.evidence` as structured data with the
manifest ids and the exact reproduction command, and rendered to Markdown and JSON by `performance_tools`:**
1. reconstructed positions from ledger events (per account, per date, with the events that produced them);
2. current portfolio value (as of D; native and reporting view; the state of the total and its causes);
3. reporting and native currencies (per holding, per cash balance);
4. price and FX timestamps (`date_used`, `observed_at`, fixing date, missed counts, freshness, reconciliation status,
   source files);
5. historical FX handling (the rate used for each flow date and for each valuation date; the transaction-date basis
   translation of OI-1);
6. deposits versus investment gains (the value bridge R1 with `EXTERNAL` flows separated);
7. internal transfers (paired transfers shown with zero return effect, R8);
8. dividends (income by type and currency; recorded-versus-expected check);
9. splits (the position before and after, and that the price used is the as-traded close of the date);
10. missing cost basis behaviour (the metrics that return `MISSING_COST_BASIS`, and the ones that stay available);
11. TWR (per sub-period and linked, with each boundary valuation);
12. MWR/IRR where supported (the flow list, the certified bracket, the NPV check) and the unsupported cases with states;
13. realized and unrealized gain where supported (per lot);
14. FX attribution (components, residual, tolerance, pass or fail);
15. reconciliation proof (R1 to R11, each with its exact residual);
16. known numerical tolerances (every tolerance and rounding rule from the convention set, with the ids).
Every section also lists the placeholders still injected (`open_items`) so the pack cannot claim conformance it
does not have. The pack is **generated, not written**: the main session assembles `reviews/gates/HG2_GATE_REVIEW.md`
from it (skill `human-gate-package`) and stops at the gate. Nothing in the pack is a judgment that the owner
"should" trust it (the owner decides, CLAUDE.md).

**Demonstration seeding [H/PM].** There is no PostgreSQL identity writer (§15.17 item 8: the tests write identity rows
directly), so loading a demonstration portfolio into the database needs either a small seeder run as the owner role
(`performance_tools/seed_demo`) or the identity writer CP2 deferred. The engine itself does not need a database:
Demonstration A also runs fully in memory (events and a release built in a test kit), which is how the golden test
runs; the PostgreSQL path is the second world in the exit test, as for CP2.

### 16.11 Increments

| Increment | Contents | Needs from the human | Needs from the Quant |
|---|---|---|---|
| **CP3a: spine and valuation** | package skeleton and the 16.1 boundary tests; `live_events` exposure (after PM approval); `conventions.py` with every rule slot as a placeholder and `is_conformant`; `numerics.py` (exact helpers, `RoundingPoint`, `present`, certified roots, size guards) with its own unit tests; `results.py` (`ComputedMetric`, `Cause`, canonical encoding); `states.py`; `manifest.py` with `reproduce`; `ledger_view` and flow classification structure with the PRD-only draft table; valuation (16.3) over the CP2 consumer, native and reporting views, state propagation, `portfolio_value`/`holding_value`/`cash_value`; `performance_service` loader; tests on the CP2 synthetic worlds and the CP1 golden portfolios (value only, hand-checkable by the engineer for plumbing, flagged as such) | PM decision on the `live_events` change; the calendar files registered (PD-0034) before any real value | none to start; the valuation/aggregation/rounding rulings replace placeholders as they arrive |
| **CP3b: flows, windows, TWR, annualization** | `flows.py` (flow-date FX per flow), `periods.py` (window, timeline, sampled series placeholder), `returns.py`, annualization with certified roots; `absolute_gain_loss`, `simple_return`, `twr`, `annualized_return`; availability-matrix rows for them; mutation evidence | none | `FlowTable`, `TwrRule`, `AnnualizationRule`, `WindowRule`, `DenominatorRule`, the return presentation precision; `cp3_golden` part 1 (valuations, TWR, annualized) |
| **CP3c: MWR/IRR, income, fees, taxes** | `mwr.py` (bracketed solver, Descartes screen), `income.py`; the metrics and matrix rows | none | `MwrRule`, `IncomeRule`, the partial-history sufficiency rule; `cp3_golden` part 2 |
| **CP3d: lots, realized, unrealized, reporting-currency basis** | per option A or B (open question 2); OI-1 translation at lot-date FX; `MISSING_COST_BASIS` paths; R3 | PM/Quant decision on option A versus B; for A, a `ledger-replay/1.4` re-ratification | `LotDepletionRule`, `RoundingTable` (OI-8), fee capitalization, partial-basis state; `cp3_golden` part 3 |
| **CP3e: FX attribution and reconciliation** | `attribution.py`, `reconciliation.py` (R1 to R11 as findings), the residual check as a state | none | `AttributionRule`, `ReconciliationRule` tolerances; `cp3_golden` part 4 |
| **CP3f: exit test, determinism, evidence** | the availability matrix test; determinism across processes and stores; engine-module pins; `evidence.py`, `performance_tools` (pack and seeder); Demonstration A end to end; the `reproduce` test over a stored manifest; engineer self-validation | STATUS 17 (the owner chooses the CN/HK price route or confirms synthetic for HG2); demonstration seeding route; optional Demonstration B downloads | `HG2DataRule` and the demonstration content; final fixture ratification |
| *Independent review* | fresh `technical-reviewer` over CP3a to CP3f, then fix rounds | | answers to review findings that are method questions |
| **HG2** | the main session assembles `reviews/gates/HG2_GATE_REVIEW.md` from the pack; the owner decides | the owner's decision | |

**Proposed first increment: CP3a.** It depends on no Quant ruling beyond the placeholders, delivers the manifest, the
valuation layer and the numerics that every later increment needs, and exercises the CP1 and CP2 seams against the
data kits that already exist. The one thing to schedule in parallel is the owner's calendar registration and, before
CP3f, the STATUS 17 decision.

### 16.12 Risks and open questions

**Open questions for the PM or the Quant (each marked):**
1. **[PM] `live_events` is a small change to reviewed CP1 code** (additive, no convention change). Approve, or accept
   reimplementation risk? Recommended: approve.
2. **[Quant, PM] One lot engine or two (16.5).** Does the depletion ruling become `ledger-replay/1.4` (option A), or is it a
   CP3-local method that leaves replay's "unresolved" in place (option B)? A also changes the CP1 golden's meaning of
   "unresolved" and needs re-ratification.
3. **[Quant] Is the engine's valuation of a post-split date consistent with F8-B's suppression?** The plan values with
   as-of quantity x RAW close of D and suppresses where F8-B says units differ; confirm no other split-date rule is
   wanted (for example, a boundary on every split date).
4. **[PM] Who runs F8-B, and when?** `confirm_splits` appends to the ledger. A performance read must not write. Proposed:
   an explicit service step ("apply confirmed splits"), run before and logged, after which L is read; the engine takes
   the resulting `SplitReport.suppressions` as input and records its digest in the manifest. A small `dry_run`
   `LedgerAccess` (an `append` that raises) in `performance_service` would let a read compute suppressions without
   writing; the CP2 service logic that calls `append` before reporting needs a read-only mode. Needs a decision and a
   small CP2-service change in CP3a or CP3b.
5. **[Quant] Reason-code selection for a total with several causes (priority table)** is an engineer default, flagged.
6. **[Quant, owner] A reason code for "zero or negative denominator", "no sign change in IRR flows" and "history too
   short"?** The vocabulary has no such code; using `CALCULATION_ERROR` for a data condition would misuse it
   (PD-0006: it is for an engine limit), and an `INSUFFICIENT_DATA` with no code is allowed ("not enough observations is a
   complete answer", PD-0006). The plan uses no code unless the Quant names one; adding a code is an owner decision
   (as PD-0025 and PD-0030 did).
7. **[PM] Current mode.** Not built in CP2 or here; no live source is admitted. The engine refuses a `CURRENT` request.
   Confirm that CP3 and HG2 are HISTORICAL_AS_OF only (PD-0015 put full Current-mode computation after HG1; no
   requirement in PRD §38.3 CP3 or HG2 names live data).
8. **[Owner] STATUS 17** before CP3f.
9. **[Quant] Does a result from a synthetic release need extra marking in the value itself** (the `synthetic` flag is on
   every `ComputedMetric` and in the manifest; Ruling 4.8 says no real-fact presentation)?

**Risks:**
1. **The Quant's document may change the shapes.** Mitigation: every method is a plug point; the first increment builds
   only mechanics. A later method change is a new convention id, not a code rewrite.
2. **A chain of exact rationals grows.** Hundreds of boundaries multiply denominators (each fixing and price has several
   digits). Mitigation: Python integers are fast to thousands of digits; a bit-size guard yields `CALCULATION_ERROR`
   rather than a hang; the measure-first rule for a 5-year daily window; reduction only by `Fraction`'s own gcd (exact).
3. **Calendars not registered.** Without them every valuation is `INSUFFICIENT_DATA` (C2-1), correctly. The HG2 pack lists
   it as an open item; the owner registers the PD-0034 drafts **[H]**.
4. **Real data are thin.** CN and HK have no admissible price source; US real history is 100 sessions; ECB FX covers the
   window. The cross-border proof is on synthetic data, labelled as such. If the owner wants real data the route is
   STATUS 17, a new source, ingestion and a new release, not an engine change.
5. **Reconciliation can pass on a wrong method.** Hence hand-derived golden values from the Quant and mutation evidence;
   the consistency checks are not the proof of correctness.
6. **Two readers of the ledger.** Mitigated by `live_events` and R3; the CP1 golden and replay suites re-run unchanged
   after the exposure.
7. **Restatement.** A correction at a later L changes past figures; the manifest pins L and the UI/AI must show which L a
   figure used (CP7/CP9 obligation recorded here).
8. **Cost per date.** Replay per boundary is O(events) and the port is eager and whole-release for PostgreSQL (§15.17).
   Measure at the PRD §29.2 portfolio size first; add `reconstruct_series` and a lazy per-listing port read only if
   needed, each with an equivalence test.
9. **Hidden float.** A `float` creeping in through a standard-library helper (`math`, `statistics`, `round`): banned by
   import and name scans, and by comparing the golden digest across Python builds when available.
10. **Evidence pack vs. real claims.** A synthetic pack must never read as a real market result (P8, Ruling 4.8): every
    section and every metric carries `synthetic`, and a test fails if a synthetic release produces an unmarked output.

### 16.13 Decisions made where the contracts did not cover (engineer choices for review)

- `performance` is a new pure package, with `performance_service` (I/O) and `performance_tools` (human/CI) outside it;
  public surface limited to four modules; boundary tests as listed.
- Exact `Fraction` internally; `Decimal` only through one presentation function; certified bracketed numerics for roots,
  no `Decimal.power`, no `float`, no new dependency.
- Rounding only at named, Quant-ruled points; engineer's recommendation (advice) is presentation-only.
- A `ComputedMetric` wrapper carries `MetricResult` + exact rational + all causes + window + method + manifest id
  (`MetricResult` itself is unchanged and cannot be subclassed).
- State propagation keeps every cause and shows one reason code by a priority table (flagged); worst-of is the structural
  default and the Quant's aggregation rule replaces it.
- Native view always available when the price is; reporting view degrades alone (§13.E).
- True TWR boundaries are the external flow dates; frequency governs the sampled series only.
- Results not persisted; the manifest plus a result digest is the audit record; evidence pack as a file artifact.
- The engine takes F8-B suppressions as an input and never writes to the ledger; a separate step applies splits.
- A `CURRENT` valuation mode is refused; only HISTORICAL_AS_OF exists.
- A manifest `ledger_digest` in addition to the version pin.
- Unsupported-metric coverage enforced by a table-driven matrix test that fails when a metric has no row.

### 16.14 CP3a as built (engineer; 2026-10-01; not yet reviewed)

Built to 16.11 CP3a, under the PM rulings of the CP3a brief (1 `live_events` approved; 2 one lot engine in `domain`, depletion NOT
implemented here; 3 a performance computation never writes the ledger; 4 historical as-of only, `CURRENT_LIVE` refused with a
state; 5 no reason code yet for zero denominator / no sign change / history too short: `INSUFFICIENT_DATA` with no code plus a
lineage cause). No migration; 0001 to 0013 untouched. No dependency added. Quant conventions arrived: none read; nothing the
Quant owns is hard-coded.

**Code.**
- `src/performance/`: `numerics.py` (exact `Fraction`; `RoundingPoint`, `RoundingRule`, placeholder `ExactOnlyRounding`; `present`
  is the one path to a `Decimal`; size guard `MAX_BITS`; no root solver, nothing needs one yet), `results.py` (`Cause`, `Part`,
  `Aggregate`, `WindowUsed`, `ComputedMetric`, `metrics_digest`), `conventions.py` (`PerformanceConventionSet`, `FlowTable`,
  `FlowClass`, the PRD-only draft table, `UNBUILT_IN_CP3A`), `states.py` (the only module naming a reason code:
  `WorstOfAggregation`, `REASON_PRIORITY`, `build_metric`), `inputs.py` (`ValuationMode`, `SuppressionInput`), `ledger_view.py`
  (`ledger_digest`, `classify_events`), `valuation.py` (`value_portfolio`), `manifest.py` (`ComputationManifest`, `seal`,
  `ReproductionStatus`), `engine.py` (`compute`, `reproduce`, `placeholder_conventions`).
- `src/performance_service/service.py`: `ReadOnlyLedgerAccess` (its `append` raises), `detect_split_suppressions`,
  `suppressions_from_report`, `compute_for_portfolio` (pin default = current committed version; a pin inside an atomic append is
  refused by the CP1 store).
- CP1 change (PM-approved, additive): `domain.replay.live_events(events, L)`, the existing `_select_live` exposed, returned in
  `ledger_seq` order; `CONVENTION_SET_ID` unchanged.
- CP2 service change (additive): `confirm_splits(..., dry_run=False)`. With `dry_run=True` the decision runs unchanged and
  `access.append` is never called; where the normal run would append the outcome is the new `SplitDecision.WOULD_APPEND` (cause
  `SPLIT_NOT_APPLIED`) and `_suppression_for` returns a suppression from the ex-date, open-ended, `SOURCE_CONFLICT` (quantity
  pre-split, price post-split). The default path is byte-for-byte unchanged (the 25 unit and 8 database tests still pass).
- Metrics emitted: `holding_value` (per account and listing), `cash_value` (per account and currency), `portfolio_value` (REPORTING
  and one NATIVE per currency), each in a NATIVE and a REPORTING view where both apply.

**How the plan was refined in building.**
- Public surface is five modules: `engine`, `results`, `manifest`, `conventions`, `inputs` (the service needs `SuppressionInput`
  and `ValuationMode`).
- `reproduce` lives in `engine.py` (it must call `compute`), not in `manifest.py`; it returns typed statuses
  `REPRODUCED`, `LEDGER_DIGEST_MISMATCH`, `RELEASE_MISMATCH`, `CONVENTION_MISMATCH`, `SUPPRESSIONS_MISMATCH`, `FILE_NOT_CITED`,
  `FILE_NOT_READ`, `MANIFEST_DIFFERS`, `RESULT_DIFFERS`.
- `ComputedMetric.exact` is None exactly when the `MetricResult` has no value, so an exact rational can never leak a suppressed
  number (INSUFFICIENT_DATA carries no number anywhere in the outward type). The engine-internal `Valued` keeps exactness only
  inside the engine.
- With the placeholder rounding rule a value that does not terminate (every HKD and CNY conversion: the exact ratio of two ECB
  quotes) is `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION` with the cause `ROUNDING_RULE_MISSING`, as in CP1. That is the honest
  state until the Quant's OI-8 ruling; native values and USD-denominated values present exactly now.
- An account before its snapshot, an entry with no native currency, and a ledger with no live event each block the totals they
  can affect (stated causes); an empty ledger is `INSUFFICIENT_DATA` (cause `NO_LIVE_LEDGER_EVENTS`), never a zero.
- `is_conformant` is False while any placeholder or `test/...` id is injected OR any `UNBUILT_IN_CP3A` slot remains, so it is False
  for all of CP3a. Every manifest lists the open items.
- The `convention_set_id` of the performance set is `performance/unratified-cp3a`; the Quant's id replaces it.

**Engineer choices the contracts did not cover (for the Quant or the PM).**
1. `REASON_PRIORITY` (which one reason code is shown for a total with several causes); all causes are kept.
2. A dry-run `WOULD_APPEND` suppresses valuation from the ex-date with `SOURCE_CONFLICT` (the reason code the service already uses
   for "corporate action not recorded"). A Quant ruling on whether an unapplied corroborated split should be a different code is
   welcome.
3. Native totals include every account-level blocker and every entry with no native currency (conservative).
4. `calendar_files` in the manifest are the consumed files whose adapter id ends in `.calendar`.
5. The test stand-in rounding rule (`test/round-half-even-2dp`) lives only in tests and marks the set non-conformant.

**Tests (hand-derived; arithmetic shown in the files).** `test_performance_cp3a.py` (24 tests, 2 of them opt-in database tests) and
`test_performance_boundaries.py` (10 tests: stdlib/domain/product_contract/analytics-facing marketdata imports only, no persistence,
adapters, vendors or capability words, nothing below imports `performance`, only `states.py` names a reason code, no float, no
`round`/`quantize`/clock/context, one exact decimal context, no adjusted series, no append path). Coverage: the exact legs and totals
of the synthetic exit-kit world against by-hand rationals; presentation with and without a rounding rule; byte-identical value
parts across the four adapter worlds; no-admitted-source, stale, suppression, snapshot and empty-ledger states; `CURRENT_LIVE`
refusal; manifest content and `reproduce` statuses; `live_events` against replay; flow table; numerics and envelope invariants;
detect-only F8-B; determinism across `PYTHONHASHSEED` 1, 2 and random processes; and, opt-in, valuation read through the PostgreSQL
market-data store and the real ledger as `finweb_app`, equal byte for byte to the in-memory result, plus a pinned earlier ledger
version. Mutation evidence (the original edit, run, revert): ignoring the FX rate fails 6 tests, ignoring suppressions fails 1,
dropping the STALE_DATA cause fails 1.

**Not built in CP3a (per scope).** Flow-date FX and flow extraction amounts, windows and the timeline, TWR, MWR, annualization,
income, lots, attribution, reconciliation, the availability matrix, the evidence pack, `performance_tools`.

### 16.15 CP3b: alignment to `performance/1.1` and `market-data/1.8`, flows, windows, TWR, annualization; `cp3_golden` part 1 wired (engineer; 2026-10-01; not yet reviewed)

Convention sets recorded everywhere: **`performance/1.1`**, `ledger-replay/1.3`, **`market-data/1.8`**, lot method `FIFO/1` (named in every manifest; it lands with the
lot engine, CP3d), minor-unit table `minor-units/1`. No migration (0001 to 0013 untouched), no dependency, no network. The Quant's "must not decide" list was
respected: no rounding mode, quantum, minor unit, threshold, priority, window rule, year fraction or flow class is chosen in code; each is transcribed from the ruling.

**Part 1: alignment (what changed).**
- *market-data/1.8.* `ECB_FIXING_TIME` is 14:10 (`marketdata/profiles.py`; the Frankfurter and ECB adapters and the calendar adapter's convention check read it); the doc
  and calendar-format comments say 14:10; `CONVENTION_SET_ID`, `profiles.CONVENTION_SET`, `PROFILE_SET_VERSION` (`market-data/1.8#profiles/3`), the reconciliation and
  `market11` rule ids are 1.8; the exit-test `ANALYTICS_PINS` of `contracts`, `manifest`, `market11`, `profiles` and `reconciliation` moved in the same change; the tests that
  asserted 1.7 or 14:15 (13:15 UTC in winter, 12:15 in summer) assert 1.8 and 14:10 (13:10 and 12:10 UTC). The HKEX close (16:10, 12:10 on half days) is calendar DATA:
  nothing in code encodes it (a test shows a 16:00 close changes `D_c`). The CNH aggregate rule needed no code change (the CP2 lookup already gives
  INSUFFICIENT_DATA + MISSING_FX_HISTORY and the total's aggregation makes any INSUFFICIENT part the total's state); a test pins Example V-2(c).
- *Valuation (Rulings 1.1 to 1.7).* `PerformanceAggregation` replaces the provisional worst-of: Ruling 1.4 (any INSUFFICIENT part: INSUFFICIENT, no value, every unvalued
  component listed; else any LIMITED: LIMITED + STALE_DATA with the **stale weight** `sum|v| LIMITED / sum|v| all`, gross; else AVAILABLE, + STALE_DATA if a part carries it) and
  Ruling 1.5 as clarified in 1.1: the reason is chosen only from causes at the result's OWN state level, in the Ruling 1.5 order (`REASON_PRIORITY`; the provisional table is gone).
  **Freshness vector** (Ruling 1.6): per exchange (by MIC) the oldest session used and the largest missed count, per currency the fixing date and missed count, the delay status, and
  the summary UNKNOWN/STALE/CURRENT. Dividend **receivables** (Rulings 1.3, 8.1: `ex_date <= D < pay date`, valued at that day's rate; income RECOGNITION is CP3c) are components of the total. A
  currency needed only by a receivable gets its own FX lookup (`valuation.extend_fx`). **`current.py`**: `D_c(t)` of Ruling 1.7 as the way "current value" is computed
  (`compute_current`): the latest date whose every close and fixing has happened; `t` is an input; a calendar that does not cover the candidate fails closed (no date, no reason code,
  cause CALENDAR_COVERAGE_GAP); a position whose LISTING currency differs from the reporting currency needs that day's fixing even with no foreign cash (Quant finding 1); only readings
  retrieved at or before `t` are used (a selected reading retrieved later makes its input INSUFFICIENT, detail `RETRIEVED_AFTER_CURRENT_INSTANT`); `D_c(t)` and `t` are in the manifest
  (`as_of_rule`, `instant`). A `CURRENT_LIVE` request is still refused with an explicit state.
- *Rounding (Rulings 2.1 to 2.5).* `placeholder/rounding-table/0` is gone. `numerics.py` holds the mechanisms only (`round_half_up` half away from zero, `floor_to`, largest-remainder
  `apportion`, tie rule); `rounding.py` holds the policy as data: `minor-units/1` (USD, HKD, CNY, EUR 2; CNH 2 DECLARED; JPY 0; GBP, CHF, SGD, AUD, CAD 2; status per row), quanta 10^-minor for derived
  money, 10^-12 for returns, weights and shares, 10^-6 for rates, recorded facts exact; a currency missing from the table FAILS CLOSED (INSUFFICIENT_DATA + UNRESOLVED_CONVENTION, detail
  `CURRENCY_NO_MINOR_UNIT`). HKD and CNY reporting values now present. The portfolio total carries an apportioned `breakdown` (Ruling 2.4: the displayed lines sum EXACTLY to the displayed total).
  **Irrational results**: annualization uses `Decimal` prec 50 `ln`/`exp` (Ruling 2.1 (b)) and the presented value is guarded by the TIE RULE: a result is only known to within 1e-40, so if
  `[v - 1e-40, v + 1e-40]` contains a rounding boundary the value presented is that boundary rounded half-up (away from zero) and lineage records `PRESENTATION_TIE`. Certified exact
  bracketing (Ruling 2.1 (a), preferred) is NOT built: for a multi-year window the exponent `p/q` has `p` in the tens of thousands and the exact bracket needs numbers of millions of bits;
  `Decimal` is conformant under (b). `Y = 1` is exact (no transcendental step; the annualized figure is the period figure, the fixture asserts the exact rational).
- *Partial total (PD-0035 section 2, Ruling 1.4a).* `portfolio_value_priced_holdings`: emitted only when the total is suppressed by unvalued components; the sum of the valued ones; the excluded
  count and list (component, native quantity or amount, reason); `NO_VALUED_COMPONENT` when nothing can be valued; not emitted before a snapshot or with no events; and
  **INSUFFICIENT_DATA with that reason (no excluded list) when a holding's quantity is unknown** (Quant finding 4). It feeds no total, return, gain, weight or denominator (a test scans
  `returns`, `flows`, `periods`, `ledger_view`).
- *Flow table (Rulings 4.1 to 4.5).* `FlowClass` is the ruling's table (external cash in/out, external in-kind in/out, internal transfer, exchange, conversion, income, fee, tax, financing, none,
  opening); `FlowTiming` START for cash inflows and END for the rest; internal transfer pairs are found by `ledger_view.paired_transfer_legs` (cash or security form), neutral at portfolio level and a flow
  of each account at account scope; `inception_of` is `I0` of Ruling 4.4.
- *The Quant's five findings against CP3a, each with a regression test and a scratch-copy mutation that fails it:* (1) `current.py` requires the fixing for a foreign-currency listing;
  (2) the reason comes only from causes at the result's own severity; (3) `ratio` never returns a negative factor (`NEGATIVE_VALUE`; a factor of exactly 0 is a real total loss, TWR = -1);
  (4) the partial figure over an unknown set; (5) `performance/1.1` ids and the tie rule.

**Part 2: CP3b.** `flows.py` (a cash flow is `amount x X(c to R, d)` at ITS OWN date's fixing; an in-kind flow is `q x P(listing, d) x X(c(listing) to R, d)`; each carries its state; `DataUse` records
what was read for the manifest), `periods.py` (`add_months`/`sub_months` with the end-of-month rule, `year_fraction` = `m/12 + r/365` exact, `WindowSpec` TRAILING_MONTHS / YTD / SINCE_INCEPTION /
CUSTOM, validity `B >= I0` and `B < E`; a refused window still declares its base, end and days; `WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT` + NOT_RECONSTRUCTABLE, `WINDOW_NOT_POSITIVE`),
`returns.py` (`twr_segments`: the segment form of Ruling 5.2, whose only inputs are `V_B`, `V_E` and, per flow day, `V(d-1)` and `V(d)`; `0/0` is 1 with `ZERO_CAPITAL_RUN`; a base <= 0 is
`NON_POSITIVE_BASE` with no reason; `absolute_gain` G; `daily_twr_factor` and `daily_gain_sum` for identities I-2 and I-3; `annualize` only for `Y >= 1`, `PERIOD_SHORTER_THAN_ONE_YEAR`,
`TOTAL_LOSS`), `engine.compute_window` (portfolio or ACCOUNT scope; `verify_identities=True` values every day and requires the daily product and the daily gain sum to equal the segment results
EXACTLY, else INSUFFICIENT_DATA + CALCULATION_ERROR `IDENTITY_FAILED`; off by default because it values every day of the window). A zero-day run (a flow day directly after the previous boundary)
has no factor and flags nothing. `reproduce` re-runs window, Current-mode and as-of manifests.

**`cp3_golden` part 1 (`methodology/fixtures/cp3_golden/cp3_golden_part1.json`, 93 items, wired).** `tests/product/cp3_golden_kit.py` expands the compact market-data block mechanically into real CP2
layouts (four calendar files, one ECB `eurofxref-hist` CSV, one RAW price file per listing in the Alpha Vantage, Sina HK and Eastmoney layouts) under SYNTHETIC source ids, ingests them through the real
adapters, resolver, calendars and checks into one release, and binds the port; `Market` reports every ingest issue (none). It reads P1 and P2 events from `cp1_golden/1.1` and P3 to P6 from the part-1 file.
`test_cp3_golden_part1.py`: shape and `FIXTURE_PINS` (counts per assertion, total 93, content hash); a no-float scan; guard tests that every kind of perturbation of a real item is reported and that the
tolerance is used only for the one transcendental item; every item compared (state, reason, details, presented value, exact rational, window, lineage dates, stale share, partial list) with the
runtime identities on; the structural assertions S-1 to S-6; and, opt-in, the same assertions through PostgreSQL as `finweb_app` (random ids per run). **Result: all 93 items match.** Two engine
defects were found by the fixture while wiring and fixed in the ENGINE, with no fixture change: (a) a one-year annualized figure was the 50-digit root (an inexact rational) where the fixture, and
Ruling 7.1, say it equals the period TWR exactly (`Y = 1` is now exact); (b) a result that needed no market lookup (before the first event, a refused window) was not marked synthetic although M holds
synthetic files (S-1, Ruling 4.8): every result computed against a version that holds any synthetic file is now synthetic.

**Tests.** `test_performance_cp3b.py` (rounding, windows, year fraction, priority, pure TWR over Example W and its edge cases, annualization, Example W through the engine, flow-date FX, in-kind flows,
scope, CNH, stale weight and freshness, partial figure, Current mode, the five findings), `test_performance_cp3a.py` updated, `test_performance_boundaries.py` extended (two decimal contexts only; `ln`/`exp`
only in `numerics`), `test_cp3_golden_part1.py`, `cp3_golden_kit.py`, `performance_kit.py`. Mutation evidence (scratch copy under `$TMPDIR`, never the real files): a flow translated at the next day's
fixing, a base without the day's cash inflow, truncation instead of half-up, reason borrowed across severities, a negative factor allowed, `current.py` looking only at cash, the partial figure treating an unknown
set as excluded, an ECB constant of 14:15, a reversed largest-remainder order, the `Y = 1` shortcut and the tie rule removed: each fails at least one named test.

**Questions for the Quant (not decisions).**
1. Ruling 1.6 says "for each exchange calendar governing a non-zero position"; the vector is keyed by MIC (XNYS and XNAS share one calendar and would appear as two entries). By calendar id instead?
2. Ruling 1.5 does not place `MISSING_BENCHMARK` (a CP4 code); it sits after MISSING_FX_HISTORY and before STALE_DATA until ruled.
3. The stale weight is undefined when the gross value `sum|v|` is 0 and a part is LIMITED; the engine states no weight.
4. Ruling 5.3 is silent on a zero-day run (a flow on the day after the previous boundary): no factor, no `ZERO_CAPITAL_RUN`. Confirm (the fixture P5-R1 has a non-empty run).
5. The runtime identities I-2 and I-3 are computed on request (every day is valued); I-1 holds by construction. Must they run in every product call?
6. Ruling 1.7: "only files retrieved at or before `t` are read". The engine can only refuse a SELECTED reading retrieved later; a later-retrieved file in M can still enter reconciliation. How should Current mode
   restrict M itself?
7. `NEGATIVE_GROWTH_FACTOR` in annualization is unreachable after Ruling 5.3 (1.1) and not in the convention's detail list; keep as a defensive refusal or remove?
8. `D_c(t)` with no non-zero position and no foreign amount is vacuously `UTC-date(t)`; confirm.
9. The partial figure with some accounts reconstructable and one before its snapshot: not emitted (the ruling's "not emitted before a snapshot"). Confirm for the mixed case.
10. Annualization with exponent `1/Y`, `Y = p/q` large: certified bracketing is preferred but needs roots of numbers of millions of bits; is the `Decimal` path with the stated tie rule acceptable as the product path?

**Not built (CP3c to CP3e).** MWR/IRR, income recognition and the income, fee, tax and financing metrics, the lot engine (FIFO/1) and realized/unrealized gains, attribution, runtime identities I-4 to I-9,
the availability matrix, the HG2 evidence pack, `performance_tools`. `is_conformant` stays False (open items are listed in every manifest).

### 16.16 CP3 midpoint fix round: review §28 of 0059d64, `performance/1.2` and `1.3`, `market-data/1.9`, `cp3_golden/1.2-part1` (engineer; 2026-10-01; not yet reviewed)

Convention sets recorded everywhere: **`performance/1.3`** (1.2 was superseded before it was released), `ledger-replay/1.3`, **`market-data/1.9`**, `FIFO/1`, `minor-units/1`; `ENGINE_ID`
is `performance/cp3-0.3`. The fixture is `cp3_golden/1.2-part1` (wording and ids only; the pin that is the hash of the ASSERTIONS is unchanged, 93 items, 39 assertions). No migration (0001 to 0013
untouched), no dependency. `ANALYTICS_PINS` of `manifest`, `profiles`, `reconciliation` and `market11` moved with the id; `market11` also gained a read-only `calendars` property on the freshness policy (no rule changed).

**Review findings.**
- *CP3-1 (in-kind flows and suppressions).* `value_flow` takes the suppressions (required keyword) and `_value_in_kind` applies the same `(account, listing, covers(d))` test the valuation applies: an in-kind
  flow of a suppressed position is INSUFFICIENT_DATA with the suppression's reason (SOURCE_CONFLICT), so Ruling 4.3 makes every return over its window INSUFFICIENT_DATA, and `gain_absolute` with it. Probes (a) and (b)
  reproduced: with the suppression ignored the numbers are the reviewer's `-5625`; with it, INSUFFICIENT_DATA + SOURCE_CONFLICT at 02-03 and at 02-05. Control: a flow dated before the suppression is valued normally.
- *CP3-2 (Ruling 6.4c, the suppression follows the units).* `performance/taint.py` derives the carried suppressions from the live events and the F8 suppressions at the ledger version, per version, and the engine adds
  them to the input suppressions, so they apply in every holding, every portfolio total, at account scope and to in-kind flows. **Conservative rule** (the Quant fixes it until `ledger-replay/1.4` has the FIFO lot
  fold): an internal security transfer dated `T` out of a position suppressed on `T` suppresses the receiver from `T` to the end of the first day `>= T` on which the receiver ends at 0 units (open-ended if never);
  several hops are followed; a `CONFLICT_DATE` source whose ledger split came early (`Y < X`) ends at `X`. F8-B is unchanged except that its suppressions now carry the split's ex-date and the decision (two optional
  fields). Once the source split is appended nothing is suppressed, nothing carried, and the review's total is 10,000 AVAILABLE; the lineage note `TRANSFER_AFTER_UNRECORDED_SPLIT` (the transfer was recorded before
  the split: its quantity is read in post-split units) is on the receiver's holding, with no state effect. Probe reproduced: the 02-06 total was AVAILABLE 4,375, now INSUFFICIENT_DATA + SOURCE_CONFLICT.
  `TODO(ledger-replay/1.4)`: replace the zero-day rule by the lot-identity rule.
- *CP3-3 (Ruling 4.8 item 4, synthetic evidence).* `confirm_splits` no longer rewrites a corroborated finding to `SYNTHETIC_EVIDENCE` because M holds some synthetic file. Corroboration happens within one world
  (synthetic feed with synthetic filing; a mixed pair is `SYNTHETIC_MIXED` and does not corroborate); a synthetic finding is `NOT_RECORDED_APPEND_BARRED`: it never appends (dry run or not) and it drives detection and
  suppression exactly like real evidence. The bar depends on the evidence, not on M. The CP2 C2-2 tests were rewritten. Probe reproduced: the holding was AVAILABLE 1,875 and the TWR AVAILABLE -0.5625; now
  INSUFFICIENT_DATA + SOURCE_CONFLICT.
- *PM ruling (synthetic M for a user portfolio).* The `performance_service` entries REFUSE when M (or `M_t`) holds any synthetic file: one INSUFFICIENT_DATA `portfolio_value`, no number, cause
  `SYNTHETIC_MARKET_DATA_REFUSED`, manifest and metric marked synthetic. Tests and fixtures call the engine directly and stay allowed.
- *CP3-4 (detection composed with computation).* **Choice:** the pure engine entries (`compute`, `compute_window`, `compute_current`, `reproduce`) REQUIRE `suppressions` (no default: omission is a TypeError and an
  empty tuple is an explicit statement), and the SERVICE entries (`compute_for_portfolio`, new `compute_window_for_portfolio`, new `compute_current_for_portfolio`) have NO `suppressions` parameter: they read the ledger at the pin,
  run F8-B read-only (`dry_run=True` over a `PinnedLedgerAccess` that cannot append) for every listing of the ledger over the whole release, and compute; the confirmation policy (which registered sources are feeds and
  filings) is a required argument because it is a human's registration. Reason: with a required-but-explicit pure entry the engine stays pure and testable (fixtures state their own suppressions), and the product
  path cannot forget detection because it has nowhere to put a value. The manifest records `split_detection` (`F8B_DRY_RUN` or `CALLER_SUPPLIED`) beside the suppressions digest. Tests that have no corroborated split use
  thin wrappers in `performance_kit` that state "none" by name.
- *CP3-5 (`MAX_BITS`).* The bound is derived, not chosen, and documented where it lives: a window is at most 100 years (36,600 days); a daily factor needs at most about 2,000 bits for 20 currencies (observed about 20
  bits per day); 36,600 x 2,000 = 73.2 million bits < `2**27`, so no valid input is refused and a runaway one still is. The reviewer's 5-year daily-flow probe (1,827 daily factors of 5-digit ECB ratios; the product is
  over `2**15` bits wide) is AVAILABLE.
- *CP3-6 (identity registry, pins).* `RecordingResolver` records every `(method, listing) -> answer` the computation asks of the resolver; its digest is `identity_digest` in the manifest (so it is in `manifest_id`), and
  `reproduce` returns the typed `IDENTITY_MISMATCH` before comparing results. With no expected digest `reproduce` returns `RESULT_NOT_COMPARED` (never `REPRODUCED`: nothing was compared). The tech plan's claim of
  engine source-hash pins is now TRUE: `ENGINE_PINS` in `test_performance_boundaries.py` pins every module of the package and `ENGINE_ID`; a changed module is named, a module without a pin and a pin without a module
  fail; the same commit must update the pin and bump `ENGINE_ID`.
- *CP3-7 (receivable in Current mode).* `choose_current_date` counts an accrued receivable in a foreign currency as an amount needing that day's fixing. Probe reproduced (`D_c` 04-01, not 04-02).
- *CP3-8 (surviving mutants).* Tests added for M1 (in-kind inflow timing, an engine-level window with a non-zero return that day), M2 (stale weight over a negative component), M8 (receivable in the total, in Current and
  historical mode) and M9 (the state of `V(D_j-1)` in the TWR). A side finding closed: when the identity I-1 FAILS the breakdown was computed first and raised; it is now skipped and the failure is reported.

**`performance/1.2` and `1.3`.** Q1: the freshness vector has one entry per exchange CALENDAR (kind `EXCHANGE_CALENDAR`, keyed by calendar id, with the MICs it governs among the holdings); a MIC with no single governing calendar
falls back to a MIC-keyed `EXCHANGE` entry. Q2: `MISSING_BENCHMARK` is 7th in the reason order. Q3: a LIMITED total whose gross value is 0 states no stale share and carries the lineage cause `STALE_SHARE_UNDEFINED`. Q5: identity
policy: I-1 runs in every call that produces the values it relates; I-2 and I-3 run in a window call on request; the manifest's `identities_run` is part of the question and the lineage says `PASS`, `FAIL`, `NOT_COMPUTABLE` (an
interior day has no value) or `NOT_RUN` for each. Q6 (below). Q7: `NEGATIVE_GROWTH_FACTOR` is `CALCULATION_ERROR` (an engine fault); `TOTAL_LOSS` stays a real outcome.

**Q6: `M_t` (Current mode).** Current mode now computes over `M_t`: the files of `M` retrieved at or before `t` (a calendar file by its registration time, i.e. its manifest's `retrieval_time`), with EVERY CP2 step re-run over
exactly those files. `MarketAtInstant.view(t)` returns a `MarketView` (port, calendars, conventions, `M`'s id, the hashes of the files left out, `t`). The service's `DerivedReleaseView` builds `M_t` as a derived release
through the real CP2 build path (`build_in_memory_market_data`: ingest, V0 and V0-FX admission, provenance, the one-vintage rule) and cuts a new `MarketDataRelease` of the retained files (a deterministic function of `(M, t)`; its
id is `M_t`'s). The manifest carries `t`, `parent_release_id` (`M`), `release_id` (`M_t`) and `excluded_files`; `reproduce` compares the port with `M`. The old read-time refusal (`RETRIEVED_AFTER_CURRENT_INSTANT`) stays as defence
in depth only. The engine still never reads a clock.

**Tests.** New `test_performance_midpoint.py` (CP3-1 to CP3-8, the Q items, `M_t`; the review's probe set-up is the shared harness), engine pins and negative control in `test_performance_boundaries.py`, a named S-4 test in
`test_cp3_golden_part1.py`, `performance_kit` wrappers and `InMemoryMarketAt`, updated CP2 and CP3 tests for the ids, calendar-keyed freshness, `M_t`, and the new reproduction statuses.

**Mutations (scratch copy under `$TMPDIR`, one mutation at a time, full default suite; the engine-pin test also fails on every mutation of an engine module, and is left out of each line).** Each fails the test named.
CP3-1: the in-kind flow ignores the suppression (5 midpoint tests); only `first_date == day` (2). CP3-2: carried suppressions dropped (3); the end rule at the start of the zero day (2); no further hops (1); no `X` end for
`CONFLICT_DATE` (1). CP3-3: synthetic evidence does not suppress (2 midpoint and 1 F8-B test); synthetic evidence appends (2 and 1). CP3-4: the service skips detection (2); the service does not refuse synthetic M (1).
CP3-5: `MAX_BITS = 2**15` (2). CP3-6: identity digest dropped from the manifest (2); `reproduce` ignores it (1); a missing expected digest reported as reproduced (1); an edit to any engine module (the pin test, naming it).
CP3-7: receivable not counted as foreign (1). M1: in-kind inflow as start-of-day cash (1 midpoint and 1 cp3b); M2: signed denominator (1); M8: receivables dropped from the total (2); M9: `V(D_j-1)` state dropped (1).
S-4: the partial figure substituted for a suppressed end value fails `test_s4_named_mutation_target_a_suppressed_end_value_is_never_replaced_by_the_priced_holdings_figure` and the golden item P3-R4 (its reason becomes
MISSING_FX_HISTORY, not a number; the same mutation shows numbers in the synthetic probe). Q1 (calendar keying): 1; Q2 (order): 1; Q3: 1; Q5: 1; Q6 (a later view): 2; Q7: 1.

**Not done / for the Quant and the PM.** The zero-day taint rule is conservative by design (`TODO(ledger-replay/1.4)`). A transfer whose receiver later sells part of the carried units stays suppressed to the end of the
first zero-day: the stated cost of the conservative rule. `compute_current_for_portfolio` runs detection over `M_t` (what a computation at `t` could have read); confirm that is the intent. The service has database tests
only through a test double that reports "no synthetic file" (the only available data is synthetic); a real-data end-to-end path waits for HG2's real source terms.

### 16.17 CP3 re-check fixes (review §29) and CP3c: MWR/IRR, income and cost lines; `cp3_golden` part 2 (engineer; 2026-10-01; not yet reviewed)

Conventions recorded everywhere: **`performance/1.4`**, `ledger-replay/1.3`, **`market-data/1.10`**; fixtures `cp3_golden/1.3-part1` and `cp3_golden/1.1-part2` (wording only; content hash of the assertions unchanged). `ENGINE_ID` is `performance/cp3c-0.4`. CP3d moves to performance/1.5 and ledger-replay/1.4 next; nothing of those is built here. No migration, no dependency.

**Part A: re-check findings.**
- *CP3-9 (same-day chain in reverse order).* `taint.carried_suppressions` takes each day's transfer pairs to a FIXED POINT in a canonical order that does not use `ledger_seq` (by account ids), until no new carried suppression appears; a carried suppression is keyed by (receiver, listing, day), so a cycle ends. The result is independent of entry order (Ruling 11.3(1)). Tests: the review's probe in both orders (pure and through PostgreSQL as `finweb_app`), every permutation of a three-hop chain (pure and PostgreSQL), a chain whose account ids run against the hops (canonical order alone would miss it), a two-day chain and a cycle.
- *CP3-10 (synthetic gate).* `contains_synthetic` is a REQUIRED member of the `MarketDataPort` Protocol. The service gate reads it with fail-closed default (a port that cannot say is treated as synthetic), and, separately, refuses whenever the computed result is itself marked synthetic (the data read says so), so a wrapper that hides or lies is refused; the engine's own default is fail-closed too.
- *CP3-11 (confirmation policy).* **Choice: refuse, with the explicit state `DETECTION_POLICY_UNMATCHED` (no number).** A policy that names no source occurring among the corporate-action records of the ledger's listings in M cannot corroborate anything, so detection would silently find nothing; the service refuses and the message names the sources M holds. Where M holds no corporate-action record at all there is nothing to miss, and the computation proceeds. A policy that recognises at least one source is not refused (corroboration itself needs both roles). Reason for refusing rather than a lineage note: a number would be shown that is mixed-unit by misconfiguration (P5). The policy (digest, feed ids, filing ids) is cited in the manifest (`detection_policy`, part of `manifest_id`, kept by `reproduce`), on a refusal too.
- *ENGINE_PINS coupling.* `ENGINE_PIN_HISTORY` records `ENGINE_ID -> digest of the pin set`; the current id must be the last entry and match the digest of `ENGINE_PINS`, and no digest may repeat. New hashes without a new id and entry fail; an id bump without a change fails.
- *Current mode.* Detection runs over `M_t` (performance/1.4 Ruling 1.7); a test shows evidence retrieved after `t` is not seen at `t` (holding 1,875 AVAILABLE at t, nothing was known) and is seen later (SOURCE_CONFLICT), with the excluded hashes cited.

**Part B: CP3c.**
- *MWR (Rulings 6.1 to 6.4; `returns.mwr_period`, `numerics.solve_irr`, `numerics.irr_is_unique`).* Investor flows: `-V_B` at 0, a cash inflow dated `D` at `(D-1-B)/n`, in-kind inflow and outflow at `(D-B)/n`, `V_E` at 1, amounts at one time summed exactly. The solver is Ruling 6.2 as written: `f` in Decimal prec 50 summed in increasing tau; `G = 0` gives `g = 1`; bracket from 1 by powers of 2 up to 2^64 (`IRR_OUT_OF_RANGE`); bisection until `g_hi - g_lo <= 1E-30 g_hi` or 400 iterations; the uniqueness test of Ruling 6.3 (`IRR_UNIQUENESS_NOT_ESTABLISHED`); `NO_CAPITAL`, `IRR_NOT_DEFINED` in the table's order; no reason code for any of them; LIMITED inputs make the MWR LIMITED; inputs are `V_B`, `V_E` and the flows only (an interior negative-base day is just a flow pattern). **Decision:** when every flow is at tau 0 or 1 the root is the exact ratio (the equation is `CF_0 + CF_1/g = 0`), returned as an exact rational, so the MWR IS the TWR (identity I-6) rather than within 1E-30; otherwise the Decimal route. The uniqueness test compares strictly (`K_j < 0` fails) at a non-unit root; an exactly-zero running balance at a non-unit root could be misjudged by 1E-47 (noted, no case in the fixtures). Annualized MWR reuses `annualize` on `g* - 1` (Y >= 1; `PERIOD_SHORTER_THAN_ONE_YEAR`; Y = 1 keeps the MWR's own numeric basis).
- *Identity I-6* runs in every window call (`identities_run` always lists it): `f(1) = G` always, and MWR = TWR exactly with no interior flow; lineage PASS, FAIL (a CALCULATION_ERROR), NOT_APPLICABLE or NOT_COMPUTABLE.
- *Lines (Rulings 8.1 to 8.6; `lines.py`).* Income (dividends accrued on the ex-date when `ex_date < event_date`, else cash basis with lineage `INCOME_CASH_BASIS`; interest on its booking date), fees, known taxes, financing costs and the conversion result (`-amount x X(sold) + bought x X(bought)` at the event date), each in R at its own date's fixing, signs as the ruling (costs negative), an empty window 0 AVAILABLE, an untranslatable piece suppresses only its own line, reversed events excluded, account scope honoured. New metrics: `return_mwr`, `return_mwr_annualized`, `income_amount`, `fees_amount`, `taxes_amount`, `financing_amount`, `conversion_result_amount`; a refused window refuses all of them. Receivables were already in the valuation; part 2 checks `receivable_value` incl. `emitted: false`.
- *`cp3_golden` part 2 wired* (`cp3_golden_part2_kit.py`, `test_cp3_golden_part2.py`). `cp3_golden_kit.Market` takes the additions (five listings, their price files, the corporate-action pair expanded into a real mock-layout FEED file and FILING file under synthetic source ids with only the fixture's ex-date and ratio); the runner runs the F8-B dry run over the pinned ledger and hands the engine its suppressions; kinds `mwr`, `annualized_mwr`, the amount lines, `receivable_value` (incl. `emitted: false`) and `split_outcome` are mapped mechanically. `FIXTURE_PINS` pins counts (78 items, 25 assertions) and the content hash. Structural checks S2-1 to S2-5; pure and PostgreSQL paths. **Result: all 78 items match on both paths; no mismatch.** Guard tests show the checker fails on a wrong state, value, exact, reason, year fraction, tolerance, `split_outcome` and `emitted`.

**Not built.** Lots, gains (CP3d), attribution (CP3e), availability matrix, the HG2 pack. `is_conformant` stays False.

### 16.18 CP3d: `acquired_on`, FIFO/1 in the one lot engine, gains, taint by lot book; `cp3_golden` part 3 (engineer; 2026-10-01; not yet reviewed)

Conventions recorded everywhere: **`performance/1.8`**, **`ledger-replay/1.5`** (FIFO/1 mode; the `none` mode stays ledger-replay/1.3 content), **`market-data/1.10`**. `ENGINE_ID` is `performance/cp3d-0.5`. Fixtures: `cp3_golden/1.2-part3` (new), `cp3_golden/1.4-part1` and `cp3_golden/1.2-part2` (re-pinned only; no edit). Part 4 (`1.1-part4`) is CP3e and is not wired.

**`acquired_on` (PD-0036), migration 0014.** Optional date on OPENING_POSITION and on external security TRANSFER_IN (FIELD_RULES `OPTIONAL`, forbidden elsewhere); not after `event_date`; the `none` mode never reads it. `0014_acquired_on.sql` adds the column, replaces the generated CHECK region (equal to `render_replace_region()`, pinned search_path kept) and adds two hand CHECKs (not after the event date; external security TRANSFER_IN only). 0001 to 0013 are untouched; CHECKSUMS has the new line. The store inserts the column only when it is set, so a database at 0013 still accepts every event that does not use it.

**FIFO/1 in `domain.replay` (the one lot engine).** `reconstruct` is the unchanged `none` fold; `reconstruct_fifo` is the same fold with lot identity (origin event id, out-leg ids of hops), acquisition date and kind (TRADE, ENTRY, RECORDED), basis currency, unit cost and carry history. Relief takes the oldest acquisition date first; lots of one date are relieved pro rata; every depleting event of the day takes `q_e / q_dep` of each portion; a position with a flag, an opaque lot or a same-day cycle withholds book and relief; ending a day at zero empties the book; each position's end-of-day books are kept (`FifoState.history`) for the taint. A relief record names its portions with attributes and hop history. `FifoState.conservation_failures` is the I-5 fold check.

**Taint by lot book (performance/1.5 Ruling 1.1a), `taint.py` rewritten.** A lot is tainted when one of its hops leaves a position suppressed on the hop date, until the expiry rule (`X` for a `CONFLICT_DATE` before it); a position is suppressed on a day iff its end-of-day book holds a tainted lot; a sale or transfer out whose relief holds a tainted portion is suppressed at event level (its realized gain is `SOURCE_CONFLICT`, its in-kind flow suppressed). A fixed point over carried suppressions; transit accounts carry none; same-day cycles stay unresolved. This replaces the zero-day conservative rule of 16.14 to 16.17: a receiver that relieves the carried units ends the taint when the tainted units leave its book, not at the first zero day.

**Gains (`gains.py`, `engine.compute_gains`, `GAINS_METHOD_ID = performance.gains/cp3d`).** Per sale a realized gain (reporting currency at the fixing of the acquisition date for TRADE/RECORDED lots; native only when every known portion's basis currency is the sale's, else `UNSUPPORTED_ASSET` / `MIXED_CURRENCY_BASIS`; ENTRY lots whose basis currency is not R give `MISSING_COST_BASIS` / `ACQUISITION_DATE_UNKNOWN`; unknown basis gives `MISSING_COST_BASIS` / `UNKNOWN_BASIS`; suppressed or tainted portions `SOURCE_CONFLICT`; a withheld relief gives replay's own reason), per position `basis.remaining`, the unrealized gain and the since-acquisition split (`LOCAL_AT_ACQUISITION_FX`, `FX_ON_COST`, `INTERACTION`, apportioned by the registry's rounding, parts sum to the total: I-8), and the two aggregates (3.10): a sum that excludes unavailable items is LIMITED and carries a gross `excluded_weight` (positions by `|MV_R|`, sales by `|proceeds_R|`); excluded for a reason that does not limit gives INSUFFICIENT_DATA; an empty set is 0 AVAILABLE. Labels: the broker-difference caveat on every gain figure (lineage `caveat.lot_method`) and "as recorded by you" where a figure rests on a RECORDED lot. I-5 and I-8 run in each call and are listed in the manifest's `identities_run`; I-7 (method independence) is the part-3 structural test S3-3, because it needs two methods' totals.

**Version-minimum policy (PM ruling OI-P11).** `cp3_golden_kit.cites_at_least` compares the same family's dotted version as integers; every cp3_golden checker (S-1, S2-1, S3-1) accepts the fixture's version or later; the exact pins on fixture ids and content hashes are unchanged.

**Part 3 wired** (`cp3_golden_part3_kit.py`, `test_cp3_golden_part3.py`): the market data of parts 1 and 2 plus two listings and a corroborated synthetic split; kinds `lot_book`, `relief`, `replay_basis`, the gain kinds, `split_outcome`; pure and PostgreSQL paths; S3-1 to S3-7. **Result: all 167 items match on both paths; no mismatch.** Two loader notes (not engine decisions): a closed position's absent `lot_book` is read as an empty book, and a NATIVE remaining basis with several currencies is one metric per currency, compared numerically.

**Decisions the contracts did not cover.** `calendar_gap` lineage: a rate lookup that is INSUFFICIENT with a calendar gap adds a `CALENDAR_COVERAGE_GAP` cause (distinct ref) so the item the fixture expects (P20-L3) can be explained; the since-acquisition split for a Southbound listing (basis currency not the listing's) is `UNSUPPORTED_ASSET` / `MIXED_CURRENCY_BASIS`, not a split; `compute_gains` is a separate entry from the window computation, so the window results are unchanged. The engine's `_convention_pairs` cites ledger-replay/1.5 in every manifest.

**Not built.** Attribution and I-4/I-9 (CP3e), the availability matrix, the HG2 pack. `is_conformant` stays False.

### 16.19 CP3e: attribution, identities I-2/I-3/I-4/I-9, the availability matrix; `cp3_golden` part 4 (engineer; 2026-10-01; not yet reviewed)

Conventions recorded everywhere: **`performance/1.8`**, `ledger-replay/1.5`, `market-data/1.10`. `ENGINE_ID` is `performance/cp3e-0.6`. Fixture `cp3_golden/1.1-part4` (28 items; minimum versions per PM ruling OI-P11). No migration, no dependency, `window` results unchanged (`compute_window` calls the shared `_window_flows` helper and nothing else moved).

**Module and entry.** `src/performance/attribution.py` (daily lines, window sums, daily returns, breakdowns, the cash identity) and `engine.compute_attribution(events, L, spec, end, R, port, resolver, market, conventions, *, suppressions, ...)`; `reproduce` re-asks an attribution manifest (recognised by `I-4` in `identities_run`). `numerics.carino_link` holds the only new `ln` (the boundary test that confines `ln`/`exp` to `numerics` still passes).

**The daily lines (Ruling 9.1).** For every calendar day of `(B, E]`, per position held at the start (split ratio `sigma`, `q0 = q sigma`, `P0 = P / sigma`), per start cash balance, per start receivable, per trade (against the close) and per income, fee, tax, financing and conversion event (`lines.line_items`, each piece at its own date's fixing). Every contribution is kept per component (kind, account, listing, currency, event) so every grouping sums exactly to its line. Lines use the fixed identifiers `attr.price ... attr.conversion` in Ruling 9.2's order.

**States (Ruling 9.5).** Every day's valuation, every flow and every extra lookup (a trade-day close, the close of a position closed that day) is a part of the aggregation: INSUFFICIENT gives INSUFFICIENT_DATA with the first reason (P22 STALE_DATA, P13 SOURCE_CONFLICT) and no breakdown, LIMITED gives LIMITED + STALE_DATA (P3-A2). The percentage components need `beta_D > 0` or `beta_D = g_D = 0`: otherwise INSUFFICIENT_DATA, no reason, detail `NON_POSITIVE_BASE` or `NEGATIVE_VALUE`; `TOTAL_LOSS` when a day's return or the TWR is -1 (no logarithm).

**Identities, in every call.** I-4 (the eight lines sum to `g_D` on every day), I-3 (`sum g_D = G`), I-2 (the daily product equals the segment TWR exactly) and I-9 (cash: the replayed balance equals the sum of the events' cash effects, restated from the event table at B and E). A failure makes the affected metrics INSUFFICIENT_DATA + CALCULATION_ERROR, detail `IDENTITY_FAILED`, with the identity named; the Carino residual bound (1e-40, Ruling 11.2) is checked the same way (percentages only). `identities_run` is `("I-2", "I-3", "I-4", "I-9")`.

**Metrics.** `attribution_money` (value `G`, `breakdown` = the eight lines with their Ruling 2.4 apportioned display value and exact value), `attribution_return` (value = the TWR, `breakdown` = the eight linked components: presented to 1e-12 with the 50-digit width, `exact` the exact rational of the Decimal), and `attribution_breakdown` (every line by `listing`, `component`, `currency`, `account` and `market`; each part presented on its own, as the fixture states). A part with nothing to say under a grouping falls in `<group>:none` (a cash balance has no listing), so each grouping sums to the whole line.

**The availability matrix (16.8 item 4).** `performance/registry.py` lists the 24 metric ids; `build_metric` refuses an unregistered id; `tests/product/test_performance_availability_matrix.py` holds the table METRIC x CONDITION -> allowed (state, reason) (24 ids x 8 conditions: baseline, split suppression, interior five-session gap, stale interior, CNH flow, window before inception, non-positive base, unknown basis) and fails for an id without a row, a row without an id, a cell the engine does not meet, an unexpected metric, an exception, a value beside a non-AVAILABLE/LIMITED state, a number beside INSUFFICIENT_DATA, or an INSUFFICIENT_DATA metric without causes. Cells come from the rulings and from the fixtures' asserted states, not from the engine's output; two cells of my own were wrong on the first run (a spent cash balance is not emitted; the partial figure is emitted beside a CNH-suppressed total) and were corrected against Rulings 1.3 and 1.4a. Not exercised in the matrix (no scenario): FX disagreement, the 2-4-session stale band as its own condition, an unresolved depletion and a non-terminating value without a presentation rule: those are covered by their own unit tests and by the golden fixtures.

**Part 4 wired** (`cp3_golden_part4_kit.py`, `test_cp3_golden_part4.py`): SYNG added to the release as in the earlier parts; S4-1 to S4-8; pure and PostgreSQL paths. **Result: 27 of 28 items match; one mismatch, reported to the Quant and not adjusted** (P22-V1 `price_date_used`: expected `2025-03-07`, actual none: market-data's lookup withholds the selected reading at 5 missed sessions, so the lineage has no date). It is listed in `KNOWN_FINDINGS` so the suite fails if the finding is resolved without removing the entry, and if any other mismatch appears.

**Decisions the contracts did not cover.** (1) NON_POSITIVE_BASE and NEGATIVE_VALUE make the PERCENTAGE attribution INSUFFICIENT but leave the MONEY attribution available, because the money lines need no base (Ruling 9.3) and are exact; Ruling 9.5 says "the attribution" without separating them: question for the Quant. (2) A part that is exactly 0 is omitted from a breakdown. (3) Breakdown parts are presented independently (as the fixture says), not apportioned; they may differ from the apportioned line by up to (k+1)/2 quanta: question for the Quant whether a published breakdown is a decomposition object under Ruling 2.4 item 3. (4) The percentage components are linked per line only (Cariño per breakdown part is linear and not published). (5) The attribution manifest's window rule is the requested rule and `reproduce` is extended by one branch. (6) The conventions' open item "attribution ..." is replaced by "HG2 evidence pack and the performance tools (CP3f); identity I-7 runs in the test suite and the evidence pack only", so `is_conformant` stays False.

**Superseded by 16.20 (CP3f):** the Quant's rulings of `performance/1.9` closed the P22-V1 finding (the engine was right), confirmed the money/percentage separation under a non-positive base, and made a breakdown a decomposition object; attribution and gains now go through `performance_service`; the evidence pack and the exit test exist.

**Not built (as of CP3e).** The HG2 evidence pack and `performance_tools` (CP3f); attribution through `performance_service` (the service's policy gate wraps `compute_window` only); account-level Cariño breakdown percentages.

### 16.20 CP3f: service paths, the CP3 exit test, the HG2 evidence pack; the `performance/1.9` rulings (engineer; 2026-10-01; not yet reviewed)

Conventions recorded everywhere: **`performance/1.9`**, `ledger-replay/1.5`, `market-data/1.10`. `ENGINE_ID` is `performance/cp3f-0.7`. Fixture `cp3_golden/1.2-part4` (28 items; pinned); parts 1 to 3 are **not relabelled**: Ruling 11.6 accepts their minimum versions (`performance/1.6`) under 1.9, and the 1.9 change note lists them as unaffected. `KNOWN_FINDINGS` is **empty**. No migration, no dependency.

**1. The `performance/1.9` rulings built.**
- *Ruling 1.1b (P22-V1).* The engine was right and the fixture was wrong: `price_date_used` is reported only for a view that HAS a value; a new holding lineage field `last_print_date` (the session of the last print the lookup considered, `HoldingValuation.last_print_date`) is reported whenever a print exists, valued or withheld (5 missed sessions, split suppression, unresolved quantity) and never beside a value. P22-V1 now matches.
- *Ruling 9.5 (1.9).* Confirmed as built: NON_POSITIVE_BASE, NEGATIVE_VALUE and TOTAL_LOSS suppress only the percentage components; the money attribution stays AVAILABLE and sums to `G`. Tests: a non-positive base and a total loss (the whole value spent on a fee, `r = -1`) keep the money lines and all 40 breakdowns.
- *Ruling 9.6 (1.9).* A breakdown is a decomposition object: its parts are apportioned (`numerics.apportion_displayed`, Ruling 2.4 item 3 over a total that is already a display value) to the line's apportioned display value in the money attribution, in the fixed order (component: positions by listing id, then cash by currency code, then receivables by event id; listing and account by id as UUID integers; currency by code; `none` last), parts that are exactly 0 omitted, a component without the grouping key in `<group>:none`. The exact parts stay in the breakdown's exact column and sum to the line; the displayed total is in lineage (`displayed_total`). P6 is 5.63, -5.75, 6.87 = 6.75.
- Reading choices (flagged for the Quant): a receivable has no listing key (so it falls in `listing:none`, as the ruling's example says) although its dividend names a listing; an income or cost event belongs to the listing the ledger names (Ruling 8.4) and has no currency or component key; `market` (not in the 1.9 list of four groupings) follows the same rules.

**2. Service paths.** `performance_service.service` gains `compute_gains_for_portfolio`, `compute_attribution_for_portfolio` and the Current-mode `compute_gains_current_for_portfolio` and `compute_attribution_current_for_portfolio`, behind the same gate as `compute_window_for_portfolio`: the synthetic-M refusal (`SYNTHETIC_MARKET_DATA_REFUSED`), detection always run (`F8B_DRY_RUN`, no `suppressions` parameter), `DETECTION_POLICY_UNMATCHED`, the finish check on a synthetic result, and for Current mode the gate and the detection over `M_t` with `D_c(t)` chosen from `M_t`'s calendars (an unchosen date is `compute_current`'s explicit state). `compute_gains` and `compute_attribution` take `as_of_rule`, `instant` and `view` (so the manifest records `t`, `M` and the left-out hashes); `reproduce` re-asks gains and attribution manifests, Current mode included (it asks the identity registry the date choice asked, and refuses a different `D_c(t)`); a refused gains window now records its DECLARED window so its manifest can be reproduced. Found by the exit test and fixed: a since-acquisition metric that is INSUFFICIENT (a suppressed lot) carried `identity:I-8 = FAIL`; it is `NOT_COMPUTABLE`, and FAIL only for the real identity failure.

**3. The CP3 exit test** (`tests/product/test_cp3_exit.py`; PRD 38.3 and Ruling 11.4): (a) all four golden parts, 366 items, on the pure path and the database path (the existing database tests re-run; a skipped path is reported as skipped); (b) identities I-1 to I-9 on every golden window (525 computations: every assertion's valuation, and every distinct window's window, gains and attribution): none FAIL, PASS counts shown, I-9 at every asserted date, I-7 by the part-3 structural test; (c) the availability matrix complete; (d) determinism across processes and `PYTHONHASHSEED` 1, 2 and random for every metric family; (e) `reproduce()` gives REPRODUCED for every one of the 525 golden manifests with its expected digest and RESULT_NOT_COMPARED (never REPRODUCED) without one. It states the open-finding rule: the exit criterion fails while a `KNOWN_FINDINGS` entry exists. About 85 s.

**4. The HG2 evidence pack** (`src/performance_tools/`: `pack.py`, `synthetic.py`, `real_slice.py`, `evidence_pack.py`; never imported by product code, enforced by a test): a directory of JSON (the 16 PRD 38.4 items, `00_inputs`, `00_manifests`, `00_open_items`) and one `SUMMARY.md`. Every number shows its state, reason, detail, manifest id and expected digest; every manifest is re-run and compared (`REPRODUCED`, `RESULT_DIFFERS`, or `RESULT_NOT_COMPARED`, never counted as reproduced); every file is labelled synthetic where any result is (Ruling 4.8) with the PD-0035 caveat; identities I-1 to I-9 are tabulated (I-7 stated per window, `NOT_APPLICABLE` with its reason where its domain does not hold); the tolerances and the convention set's open items are listed; output is byte-deterministic; no network, clock or environment is read.
- *Demonstration A (synthetic).* No golden portfolio holds US, CN and HK positions with USD, HKD and CNY cash. The subject is golden P1 (US AAPL and MSFT, HK 0700, USD and HKD cash, a 4:1 split, an internal transfer, a conversion and its correction, fees, financing, a missing and an unresolved basis) EXTENDED with a CN account (CNY deposit and SYNA, as P3 buys it), a HK dividend accrued from its ex-date with its withholding, and a USD withdrawal, on the golden synthetic release. Windows: since inception, from 2025-03-31, trailing 1 month, YTD (an explicit WINDOW_BEFORE_INCEPTION). The loader reuses the golden kit from `tests/product` at run time (a human/CI tool). No new expected value: the pack reports what the engine computes.
- *Demonstration B (real slice).* Only files that are terms-attested and in {Alpha Vantage, Frankfurter/ECB, `ecb.eurofxref`, `calendar.manual`} are read, through `build_in_memory_market_data`; the AKShare files are listed NOT ADMITTED (`SOURCE_TERMS_NOT_ATTESTED`) and never read; calendar DRAFTS are never read. The ledger is hypothetical (a deposit and three trades in AAPL at the real closes of the dates named) and labelled so; the instrument is registered by the tool's own configuration. Today no calendar is registered, so every freshness is UNKNOWN, the value is INSUFFICIENT_DATA with CALENDAR_COVERAGE_GAP, split detection is `NOT_RUN_NO_CALENDARS` and the pack says so. **What the real slice still needs from the owner:** (1) check and register the calendar drafts (NYSE_SESSIONS and ECB at least; the HKEX and CN drafts only when real HK and CN prices exist) with the download tool, per `calendars/drafts/REVIEW.md`; (2) an ECB file for the price window (the Frankfurter file on disk covers 2025-01-02 to 2025-01-08; the AAPL prices run 2026-05-08 to 2026-09-30) if real FX handling is to be shown, since a USD-only slice needs none; (3) nothing else for US prices (the Alpha Vantage file is admitted); CN and HK stay synthetic (STATUS 17).

**5. Decisions the contracts did not cover.** The pack is built from engine entries, not from a new `performance.evidence` module (the plan's 16.10 sketch), so the pinned engine did not grow; the pack's I-7 evidence is computed from the ledger's own trades and the engine's valuation, labelled as the pack's check; the as-of date of a subject is stated by the subject (Current mode is not exercised by the pack); the exit test shares ONE universe of 525 computations across its statements.

**Not built.** The owner's actions above; Current-mode evidence in the pack; account-scope evidence; `is_conformant` stays False (open items listed in section 16 of every pack).

### 16.21 CP3f fix round: DB-path id order, `performance/1.10` grouping keys, real ECB FX in the real slice (engineer; 2026-10-01; not yet reviewed)

Conventions recorded everywhere: **`performance/1.10`**, `ledger-replay/1.5`, `market-data/1.10`. `ENGINE_ID` is `performance/cp3f-0.8`. No fixture changes (the 1.10 note leaves parts 1 to 4 unaffected); no migration.

**1. A flaky database-path golden test (found by the coordinator).** Ruling 9.6 orders breakdown parts by id as a UUID integer, and the database path generates random listing ids, so `P3-A1` `attr.price` by listing passed or failed by coin flip: the checker compared the fixture's own order. The kit now re-sorts the fixture's parts under the ids of the run by the 9.6 keys (`part_order_key`, `expected_parts`); the order assertion is NOT weakened (the actual order must equal the re-sorted one). New tests force two mappings with OPPOSITE id order (`ForcedIds`) and fail deterministically for a checker that assumes the fixture's order (`test_a_checker_that_assumed_the_fixtures_order_would_fail_under_the_reversed_mapping`), and one asserts the fixture's own order is the 9.6 order under its own ids. Other places that could pass only by random ids were audited: part 3's lot and relief comparison is by identity set; the money lines apportion in registry order; an apportionment tie between two PARTS is broken by kind first (position, cash, receivable, event: P6 and P21 tie position against cash by that, never by ids), and by id only between two listings or two receivables (no golden tie there). The part-order and tie assertions in the DB-env suite were run repeatedly (see the report).

**2. `performance/1.10` Ruling 9.6.** One key per contribution per grouping (`attribution.Component.part`): a receivable's FX goes to the listing and market its dividend names (cash, once paid, is `none` there); an income, fee, tax or financing event is keyed by its listing (else `none`), its own currency and its `event_id` (component kind `event`, ordered after receivables); a conversion result is `none` by listing, market and currency and `event` by component; the market key is the listing's MIC (it was already), ordered by code, `none` last. Tests: one per rule on golden P21 and P12 (values are the Quant's derivations), the component order, and an every-grouping-sums-to-the-line test on P21, P12 and P1 (40 breakdowns each, exact and displayed).

**3. The real slice exercises real ECB FX.** `PackSubject.extra_reporting` gives the same ledger in other reporting currencies; the real slice reports EUR (a direct ECB quote, inverted exactly) and CNY (a cross through EUR from two legs; market-data allows it, with the lineage note PARITY_CHECK_NOT_RUN: no central-parity source is admitted). The pack adds `17_fx_views.json` (not a PRD item): per view the value with its state and causes, and for every ledger date the rate the port gives: outcome, exact rate, fixing date used, the fixing date and INSTANT (14:10 Europe/Berlin) and source of each leg, the missed-fixing count, the freshness of each rate and the lineage notes; the summary has a table. USD reporting is unchanged.
- *What it shows today.* No calendar is registered and the ECB data on disk (Frankfurter, 2025-01-02 to 2025-01-08) does not cover 2026-05-08 to 2026-09-30, so the EUR and CNY views are INSUFFICIENT_DATA with the cause CALENDAR_COVERAGE_GAP (freshness UNKNOWN); with calendars registered the cause becomes staleness of the January 2025 file. Tests (`test_performance_real_fx.py`) build their OWN file sets in a temp directory (files shaped like Alpha Vantage, Frankfurter, the ECB history file and the calendar files, with real manifests; no real payload is read): (a) no calendar and no covering data, (b) calendars but no covering data, (c) calendars and a covering FX file: the EUR value is the USD value divided by the file's USD quote and the CNY value is that times the file's CNY quote, exactly, with fixing dates, 14:10 instants, source and CURRENT freshness shown, (d) the ECB's own history file is refused by name.
- *Found while doing it (the owner must be told).* (i) `ecb.eurofxref` (the ECB's own history file, `fetch --source ecb_eurofxref`) has precision profile MEMORY: the ingest path REFUSES it (`ProfileNotAdmittedError`, market-data Appendix A.4, MD-OI-12: not admitted until its first real file is profiled), and a release naming it would abort the build; the pack now classifies it `PROFILE_NOT_ADMITTED`, lists it, and never reads it. (ii) The route admitted today is Frankfurter: `fetch --source frankfurter_fx --symbols USD,CNY --start 2026-05-08 --end 2026-09-30` writes source id `frankfurter.ecb`, kind FX, payload format `frankfurter_json_timeseries/1`. (iii) Two admitted files of one series (the existing January 2025 file and a new window file) are two vintages (Ruling 0.1) and would fail the release build; the real slice keeps the LATER retrieval and lists the other `SUPERSEDED`. (iv) Frankfurter data carries the lineage note `provenance: UNCONFIRMED (frankfurter.ecb)`: not evidence that the value is the ECB reference rate (Ruling 1.1a); it did not change the state in the tests.
- *What the real slice reads once the owner registers the calendars and fetches FX:* calendar files of source `calendar.manual`, kind CALENDAR, format `finweb_calendar_json/1` (NYSE_SESSIONS and ECB at least); FX files of source `frankfurter.ecb` (admitted) or `ecb.eurofxref` (kind FX, format `ecb_eurofxref_hist_csv/1`, refused until profiled); quotes of `alphavantage.us`.

**4. Decisions the contracts did not cover.** `none` keys for an event whose `event_id` the engine cannot resolve fall under `none` (cannot occur from a committed ledger); the superseded-vintage rule is a pack choice, not a market-data rule (a release still fails closed); the EUR and CNY views are the pack's own reporting views of a USD ledger (a hypothetical demonstration ledger), not a claim that a EUR investor held it.

**Superseded in part by 16.22:** the "keep the later retrieval / SUPERSEDED" vintage choice of item 3 (iii) is REMOVED (CP3-12); the policy rule of 16.5's CP3-11 is completed (CP3-15).

### 16.22 CP3 final-review fix round (TECH_REVIEW section 30; engineer; 2026-10-02; not yet reviewed)

Conventions recorded everywhere: `performance/1.10`, `ledger-replay/1.5`, `market-data/1.10`. `ENGINE_ID` is `performance/cp3f-0.9`. No fixture change, no migration, `KNOWN_FINDINGS` empty.

**CP3-12 (MEDIUM): vintages.** The real slice no longer picks a vintage. Two admitted files that contribute to one series (market-data `series_keys`) are a CONFLICT: both files are listed by source, retrieval time and sha256 (`vintage_conflicts` in `REAL_SLICE_REPORT.json`, `00_inputs.json` and a SUMMARY section), NEITHER is in M, and so nothing that depends on the series has a number (a conflict in the quotes means the slice is not built, status `VINTAGE_CONFLICT`; one in the FX files leaves the USD view and gives INSUFFICIENT_DATA FX views). The operator resolves it explicitly and by hash: `--exclude-file SHA256` (repeatable) removes files from M, `--use-file SHA256` (repeatable) names exactly the files of M among the admitted ones; an unknown sha256 is `SELECTION_UNKNOWN_FILE`, never ignored. The choice is recorded (`file_set_chosen_by_operator`: the options and the files in M) in `00_inputs.json` and as "File set chosen by the operator" in SUMMARY.md; a human naming the vintage satisfies Ruling 0.1 (at most one vintage of a series in M), an automatic choice would not. THIS REPLACES the SUPERSEDED rule of 16.21 item 3 (iii). Tests: the reviewer's revised-close scenario (two Alpha Vantage files, the later with a revised close) is not built and never shows the revised value; two Frankfurter vintages leave the FX views INSUFFICIENT with both files named; `--exclude-file` and `--use-file` each build with exactly the selected files and record them.

**CP3-13 (MEDIUM): what the FX source is.** Wherever the pack names the FX source it says what it is: "ECB reference rates as republished by Frankfurter (source `frankfurter.ecb`); provenance UNCONFIRMED: not evidence that a value is the ECB reference rate for its date (market-data Ruling 1.1a)": the real-slice subject name, description and notes, the 17 and 05 files (`fx_source`, `fx_sources_in_m`, per-rate `source`), the summary table and heading, the labels, and `00_open_items.json`. The PD-0035 caveat keeps the owner's words and is FOLLOWED by "Qualification for the FX in this pack: ..." whenever an admitted FX file is `frankfurter.ecb`. In the engine, every metric computed from rates carries lineage entries `fx_note:provenance` (the lookups' `provenance: UNCONFIRMED (frankfurter.ecb)` notes) and, for a CNY cross, `fx_note:parity` (`PARITY_CHECK_NOT_RUN`): `DataUse.fx_notes` collects the notes of every FX lookup (valuation, flows, lines, gains, attribution) and `_with_fx_lineage` attaches them to each metric of a valuation, window, gains and attribution result. Lineage notes only: no reason code, no state change (PD-0036).

**CP3-14 (MEDIUM): attribution and the suppressions.** `attribution.Lookups.guard(account, listing, day, event_id)` joins an INSUFFICIENT part with the suppression's reason (SOURCE_CONFLICT) to the attribution's state whenever a close is used for a position that is suppressed on the day (a position closed out that day; a trade's result) or for a trade whose relief holds a tainted portion (`event_taints`); `Lookups` now receives the run's suppressions and event taints. Tests: the review's set-up (A1 to A2 on the ex-date 02-03, A2 sells; and a sale in the suppressed account itself) gives INSUFFICIENT_DATA + SOURCE_CONFLICT for the money and the percentage attribution, consistent with the realized gain, through the service and through PostgreSQL as `finweb_app` (the dry run writes nothing); the world with the split recorded still gives a number.

**CP3-15 (LOW): the policy.** `policy_matches_nothing` now refuses (DETECTION_POLICY_UNMATCHED, naming the unmatched role) when EACH role must resolve to a source M holds and a role resolves to none while M holds corporate-action records of a source the policy names in NO role (a misspelt or missing registration). The previous `not refused` test of a half-matching policy is replaced by the refusal test; a policy whose roles are matched, or an M with no corporate-action record, or an M whose only records are of sources the policy names, is not refused. Reading choice: "resolve to a source in the release's terms registry" is implemented as "a source that M holds records of", because the service has the port and not the registry; a lone feed record of a named source stays valued (no policy could corroborate it).

**CP3-16 (LOW): Carino.** `numerics._carino_kappa` evaluates kappa = ln(1 + r) / r by its series `sum (-r)^k / (k + 1)` (14 terms, error below |r|^14 / 15 < 1E-55) for |r| < 1E-4, and the direct form above it (46 correct digits), for both `kappa_D` and `kappa`, so a TWR below 1E-50 no longer rounds `1 + r` to 1 and divides by 0 (the Ruling 11.2 tolerance holds: residuals are below 1E-40). The review's 1E28 / 1E-24 scenario returns AVAILABLE with a TWR of about 8E-53 and a residual below 1E-40.

**CP3-17 (LOW): surviving mutants.** A16: Example W's FX breakdown is -14.28 + -0.29 = -14.57 under the bar -14.57 (the line's own rounding is -14.58: the test asserts both). A17: a position closed out on a day whose close is 1 session stale gives AVAILABLE + STALE_DATA, 3 sessions LIMITED + STALE_DATA.

**Decisions the contracts did not cover.** (1) The vintage conflict excludes EVERY file of the conflicting series from M (a conflict in FX leaves the slice with USD only); (2) the policy rule reads "registry" as "what M holds" (above); (3) the fx lineage entries use the keys `fx_note:provenance` and `fx_note:parity`, joined by " | " when several notes apply; (4) `attribution` guard parts are added whenever a suppressed close would be USED, never for a position that keeps its end-of-day valuation (its own valuation already carries the suppression).

### 16.23 TECH_REVIEW section 31 fix round (CP3-15 per listing, CP3-18 to CP3-20; engineer; 2026-10-02; not yet reviewed)

`ENGINE_ID` `performance/cp3f-0.10` (pins recorded in `ENGINE_PIN_HISTORY`); conventions unchanged (performance/1.10, ledger-replay/1.5, market-data/1.10).

**CP3-18 (MEDIUM): the receiving leg carries the taint.** At account scope an internal paired transfer is an in-kind flow of each account (Ruling 4.5), valued at q x P x X. Where the receiver sold the units the same day it ends the day without the tainted lot, so no carried suppression covered the in-leg and it was valued at the RAW close (A2 scope `gain_absolute` AVAILABLE 5,625 while the attribution and the realized gain were SOURCE_CONFLICT). `taint.carried_taint` now also taints the in-leg's event id (`event_taints`): for each live out/in pair, the lot the out-leg relieves is given the hop of the transfer (the lot as delivered) and tested by the same `lot_taint` rule (market-data Ruling 6.4c rule 6; same expiry rule for a `CONFLICT_DATE` source), and the in-leg is suppressed for its own date. `value_flow` already suppresses an in-kind flow whose event is in `event_taints`, so G, TWR, MWR, the gains and the attribution of that scope agree: no number, SOURCE_CONFLICT. At the A1 scope the out-leg was already suppressed (the source's position is suppressed that day). At portfolio scope the pair is not a flow: G stays AVAILABLE (value-based, no flow valued), the attribution and the gains are SOURCE_CONFLICT as before. Tested pure and through PostgreSQL as `finweb_app` at A1, A2 and portfolio scope. Consequence: `event_taints` holds the in-leg id also where the receiver keeps the lot (redundant with the carried suppression, harmless); three older tests that pinned the exact key set of `event_taints` now include the in-leg id. Reading choice: "the receiving leg carries the taint" is read as "the in-leg's own flow is suppressed", with no new state for a receiver that holds nothing.

**CP3-15 (per listing).** `policy_matches_nothing` is evaluated per listing, not over the union: for each listing, if M holds records from a source no role names while a role resolves to no source M holds for that listing, the run is refused (DETECTION_POLICY_UNMATCHED) naming the role and the listing. The two consistent cases stay unrefused (M holds no corporate-action record of the listing; a role names a source with no records while the other sources are named). The reviewer's probe (L1 confirmed split from test.feed/test.filing missing from the ledger, L2 an old record from other.filing; roles `{other.filing}` or `{test.filling, other.filing}`) is refused.

**CP3-19 (LOW): the operator's selection.** `files_in_m` is computed after the conflict check (`finish_operator_selection`): the record of M is exactly M, so naming both vintages with `--use-file` leaves both out. Every file the operator names is reported in `named_files` with `in_m` and its reason (unattested, PROFILE_NOT_ADMITTED, refused source, VINTAGE_CONFLICT, ...), in 00_inputs.json and SUMMARY.md. The conflict report states whether the vintages disagree on any shared date and lists the dates with both values (`disagreement`: read through the file's adapter after the store verifies the file; `comparable: false` with the reason where it cannot be read); two vintages with no shared date say so. Reporting only: the tool never uses it to choose a vintage.

**CP3-20 (LOW): mutants.** B1 (event taints not handed to `Lookups`): no scenario kills it by output alone after CP3-18, because the tainted sale is also refused by the in-leg's tainted flow (account scope) and by the source's suppressed close-out or valuation (portfolio scope); it is killed by a seam test that captures what the engine hands `Lookups` (suppressions, and event taints holding the sale and the in-leg). B3 (close-out guard) and B4 (trade guard) are killed by the spy tests of what each call site asks the guard; no scenario separates them by output: a close-out of a suppressed position coincides with a tainted trade of the receiver, a same-account sale is covered by both, and an unpaired transfer-out is refused by its suppressed flow. B2 (the guard's taint branch) is killed by a unit test of the guard.

**Docstring.** `numerics._carino_kappa`: the truncation after 14 terms is below 7E-58 (|r| < 1E-4); rounding at precision 50 dominates, with a total error of at most about 5E-50 (the earlier text said 1E-55).

**Decisions the contracts did not cover.** (1) The in-leg's taint is computed from the out-leg's relief (the lot as delivered), not from the receiver's end-of-day book; (2) the vintage comparison keys quotes by identifiers and date and FX by pair and date, and compares the value text of the source; (3) `comparable: false` is reported rather than raising where a vintage cannot be read.

### 16.24 CP4 part A: HG2 conditions 1 and 2 (CP3-15 per (listing, ex-date) under market-data/1.11 Ruling 6.4d, CP3-21, PD-0037 under performance/1.11) and two small items (engineer; 2026-10-02; not yet reviewed)

`ENGINE_ID` `performance/cp4-0.11`, one id for the whole round (nothing was committed between the two steps; pins and history in `test_performance_boundaries`). Conventions now cited: **performance/1.11**, **market-data/1.11**, ledger-replay/1.5 (unchanged), minor-unit table **`minor-units/1.1`**.

**CP3-15 (market-data/1.11 Ruling 6.4d; the ruling text, not the summary, is what is implemented).**
- `split_confirmation.unmatched_policy_keys(listings, readings_of, policy)` (pure): for each listing and each ex-date `X` on which the readings hold a `SPLIT` record of that listing (exact ex-date equality, real or synthetic, no window), `U` = the sources with a record for the key that are named in neither role; the key is UNMATCHED iff `U` is not empty (`if foreign:`, so case (c), both roles matched and an unclassified source present, refuses too). A key whose sources are all classified is never unmatched (case (e), `FEED_ONLY`/`FILING_ONLY`). Each key is a `UnmatchedKey(listing, ex_date, unclassified_sources (sorted), unmatched_roles (subset of feed, filing in that order; empty in case (c)))`; all keys are returned, ordered by (listing id as text, ex-date).
- Performance service: `policy_unmatched_keys(events, pin, port, policy)` takes the listings of every ledger event at the pin (live or reversed; `i.ledger_seq <= pin`) and `port` = M (M_t in Current mode, as the gate already ran over `view.port`). `policy_matches_nothing` (kept as the text of the reason) renders the keys as a JSON array in the cause: `...unmatched_keys=[{"ex_date":...,"listing":...,"unclassified_sources":[...],"unmatched_roles":[...]}]`. The refusal is `INSUFFICIENT_DATA`, reason code null, cause and detail `DETECTION_POLICY_UNMATCHED`; the manifest cites the policy digest and both roles' source ids (unchanged); the synthetic refusal still comes first.
- F8-B append run: `confirm_splits` runs the same test over the listings of the ledger at its version before anything else (dry run too) and raises `DetectionPolicyUnmatchedError(keys)`, so nothing is appended.
- Policy validity (item 1): `ConfirmationPolicy.__post_init__` already refuses an empty role or a source in both roles when the policy is built, before any computation (existing code and test; unchanged).
- Behaviour change to note: a source that is neither feed nor filing was silently ignored by the F8-B run (an old test asserted it); it now refuses the run.
- Tests: every row of Example 6-D (Q1 to Q4, case (c) with `third.feed`, case (e)), plus cases (b), (d), (f), exact-date equality, a reversed event's listing and the synthetic-first order, pure; the append run (appends nothing, both modes); and through PostgreSQL as `finweb_app` in a disposable `finweb_it_*` schema (all three performance entries, the two-listing ledger for Q4, and the F8-B run over `PostgresLedgerAccess`). The method-level wording of the old per-listing tests changed to the JSON fields.
- Convention text: market-data Ruling 6.4d now states the test, so there is no per-listing wording left to change; nothing for the Quant.

**market-data/1.11 ids.** `CONVENTION_SET_ID`, `profiles.CONVENTION_SET`, `PROFILE_SET_VERSION` (`market-data/1.11#profiles/3`), `reconciliation.RULE_ID`/`TOLERANCE_REF`, and the three `market11` slot ids moved from 1.10 to 1.11 (and the `taint.py` docstring). A lineage `precision_profile_id` carries the governing set, so one written under 1.10 no longer resolves through `field_profile_of` (it is recomputed at ingest; same as the 1.9 to 1.10 bump). `ANALYTICS_PINS` of the CP2 exit test re-recorded for manifest, market11, profiles and reconciliation (id only). The CP3 golden fixtures keep citing `market-data/1.10` (their own minimum; accepted by `cites_at_least`, Ruling 11.6).

**performance/1.11 (HG2 condition 2, PD-0037).** `rounding.py`: `MINOR_UNIT_TABLE_VERSION = "minor-units/1.1"`; status `CONFIRMED` for the ten ISO rows (decimals unchanged), CNH stays `DECLARED`; `open_items()` flags MEMORY rows only and returns `()` with none; `rule_id` `performance/1.11#2.2-2.4`. `conventions.py`: `CONVENTION_SET_ID` and every slot id (`flow_table`, `valuation`, `windows`, `twr`, `annualization`) `performance/1.11#...`, and `states.py` (aggregation) likewise; `UNBUILT_IN_CP3B` is empty (the HG2 evidence-pack entry is removed, per section 16 item 16). `performance_conventions().is_conformant` is now True (a placeholder rule still makes it False; tested). The pack (`pack.py`) cites `performance/1.11` and prints "none" when there are no open items. No computed value, state or reason changes; the only outputs that change are the cited ids, `conformant` and the open-items list, and the money exponent below.

**CP3-21.** `real_slice.vintage_disagreement` compares the two vintages' values as `Decimal` (`decimal_value`), per market-data Ruling 1.1a item 3 (trailing zeros ignored): 200.00 and 200.0000 agree; text that is not a number compares as itself. The report still shows each file's value as written. Reporting only: M is unchanged (both vintages are excluded whatever the result).

**`register-file` docstring.** The module and `run_register` docstrings now say `register-file` is human-only (the existing `require_human` gate, tested), and that only `verify` is unguarded; the terms gate is what does not apply to it.

**Money presented with its minor units (Ruling 2.2).** The real slice showed EUR `9229.7`: the value was correct (`MetricResult.value` is a `Decimal`, equal to 9229.70) but `to_decimal_exact` gives the shortest exact Decimal, so a money amount quantized to two places lost its trailing zero in `MetricResult.value` itself, not only in the pack's rendering (the pack prints `str(value)`). `numerics.to_decimal_money(value, decimals)` carries a money amount with exactly `decimals` places (JPY: none; zero is `0.00`) and never rounds (a value off the quantum is returned as the exact Decimal). It is used in `present` for `PRESENT_MONEY` (when the rule has `money_decimals`) and for the apportioned breakdowns (valuation components, since-acquisition lines, attribution lines and their breakdown parts, and the `displayed_total` lineage text). Returns, rates and recorded facts are unchanged (not padded). No number changes; equal as Decimals. Reading choice: Ruling 2.2's quantum 10^-minor_unit is read as the Decimal exponent, which its own example column (4,000.00) supports.

**Market-data open item "not built: Current mode (instant t) ... historical mode only" (`market11.UNBUILT`).** Checked, not removed. It looks stale in part: `engine.compute_current`, `performance.current` (D_c(t) by scheduled close and the 16:00 Berlin fixing), `MarketView`/`MarketAtInstant` (M_t, files retrieved at or before t) and a production `performance_service.derived_release` implement what Ruling 2.2 item 6 and Ruling 1.6 (Current mode) ask for, at the performance layer. But the market-data policies themselves (`Market11Freshness.assess_in`, `Market11FX.resolve`, the price-of-date selector) still take a DATE `as_of`, not an instant, so the text "for prices and FX (Rulings 1.6, 2.2 item 6, 5.2)" is true of the market-data layer taken alone. A question for the Quant: is Current mode "built" when the performance layer chooses the date, or only when the market-data policies take `t`?

**Decisions the contracts did not cover.** (1) F8-B refusal is an exception (`DetectionPolicyUnmatchedError`), not a report: Ruling 6.4d says "the append run is refused" and nothing else; (2) the F8-B run takes the listings from the ledger at its version, as Ruling 6.4d item 2 says, not from the caller's `listing_ids`; (3) the keys are carried as JSON in the cause note (the cause type has no structured field); (4) the exponent reading of Ruling 2.2 above; (5) tests that pinned the old ids or a False `is_conformant` were updated (tech plan list below), and `S-5` of the CP3 golden structure compared the text `96.5` and now compares `96.50`; (6) one ENGINE_ID for both steps.

**Tests changed for the 1.11 ids.** `test_performance_cp3a` (rounding id, convention ids, `is_conformant` True, no HG2 open item, two places), `test_performance_cp3b`, `test_performance_evidence_pack` (open items empty, "none" in SUMMARY), `test_cp3_golden_part1` (`minor-units/1.1`, `96.50`), `test_marketdata_*` and the two PostgreSQL store/F8-B tests (ids), `test_corporate_actions_service` (the unclassified-source test now expects the refusal), `test_performance_recheck` and `test_performance_final_review` (the JSON fields of the refusal).

### 16.25 CP4 part A round 2: review section 33 (CP4-1, 2, 3, 4, 5) and `performance/1.12` (engineer; 2026-10-02; not yet reviewed)

`ENGINE_ID` `performance/cp4-0.12` (a new history entry; `cp4-0.11` stays as the reviewed state). Conventions now cited: **performance/1.12**, market-data/1.11, ledger-replay/1.5, `minor-units/1.1`. No fixture changes (Ruling 11.6).

**CP4-1 (F8-B, one ledger read).** `confirm_splits` tests the policy on EVERY load a decision reads: an initial load, and again on the fresh load inside the per-finding loop, over the listings that load names and no earlier test covered (M is fixed for the run, so a tested listing stays tested). A listing a concurrent writer names between two loads is therefore tested before the decision that would append for it; the refusal raises before that append. Tests: a `RacingLedger` whose 2nd or 3rd `load` first sees a BUY of B (the reviewer's interleaving: B's 4:1 split with an unclassified 2:1 `third.feed` was appended; now `DetectionPolicyUnmatchedError` naming (B, ex-date, [third.feed], [])), the same world without the race, and a classified world that still appends.

**CP4-2 and Ruling 1.7 (1.12) item 5 (a Current-mode refusal is a Current-mode result).** `service._current_fields` gives every Current-mode refusal (the synthetic refusal, `DETECTION_POLICY_UNMATCHED`, at the gate and in `_finish`; and for gains and attribution) the fields a computed Current-mode manifest records: `as_of_rule` `D_c(t)`, `instant` t, `as_of` = the `D_c(t)` that `choose_current_date` gives (the UTC date of t, with the cause in `as_of_causes`, if none), `parent_release_id` M, `excluded_files` (the hashes M_t leaves out) and `release_id` M_t. `engine.refuse` and `_manifest` take the new optional arguments; `compute_current`'s coverage-gap manifest now also records M_t's `release_id`. A historical refusal is unchanged. `valuation_mode` stays `HISTORICAL_AS_OF` as in every computed Current-mode manifest (the composition of Ruling 1.7 (1.12) item 1: `as_of_rule` marks the mode); the enum has no "Current" value, only `CURRENT_LIVE` (refused, no live source). Tests: pure (policy refusal, synthetic refusal, excluded files, coverage gap) and through PostgreSQL as `finweb_app` for the three Current entries.

**CP4-3 and Ruling 2.2 (1.12) (the exponent of a recorded fact).** `numerics.present`, `PRESENT_FACT` with a currency: exactly `max(minor_unit(k), d(v))` decimals (`shortest_decimals`), never rounded; a currency outside the table: the shortest exact form and the detail `CURRENCY_NO_MINOR_UNIT` (carried to `ComputedMetric.details` by `build_metric`), state unchanged; no currency (a quantity): unchanged. `REPORTING` stays derived. `engine.py:260/267` (native cash, native receivable) are fixed by this. Cases tested: 0.125 USD `"0.125"`, JPY 5000 `"5000"`, JPY 12.5 `"12.5"`, 0 USD `"0.00"`, recorded 2248.0000 (and 2248, 2248.0) `"2248.00"`, 2.5 USD `"2.50"`, and through the engine the native/reporting pair of a 0.125 USD cash balance (`"0.125"` and `"0.13"`) and a 780.5 HKD receivable (`"780.50"`). Equivalent mutant: `max(minor, d)` against `minor` alone gives the same text because `to_decimal_money` returns the exact value when it is off the quantum; the `max` is kept as the ruling's wording.

**Ruling 1.7 (1.12) item 2 (`D_c(t)` tests the events dated `D`).** `current.choose_current_date`: for each candidate day, every LIVE ledger event dated that day adds the MIC of the listing it names to the exchange set and sets `foreign` when its amount's currency, or its listing's currency, is not `R` (an unknown currency is foreign). A reversed event is not live (`live_events`). `D_c(t)` stays a function of (t, L, M_t). Q8 follows: nothing held and no live event dated `D` gives the UTC date of t. Tests: Example 1.7-C both rows (the full HKD withdrawal, and the in-kind transfer of the last US units: `D_c` = 2026-10-01 at t = 12:00 UTC; 10-02 after the 14:00 UTC publication, respectively the 20:00 UTC close), a same-day SELL of the last unit, a reversed deposit, the listing-currency and unknown-currency cases (isolated through an HKEX listing whose close is already past), and Q8.

**Ruling 1.7 (1.12) item 1 (the calendar check).** A test asserts, for every calendar the code knows (the four drafts under `data/marketdata/calendars/drafts/`, the registered NYSE and ECB files under `data/marketdata/files/calendar.manual/`, the synthetic calendars of `World`, `ca.CALENDARS`, a 2025-2026 NYSE/HKEX/CN-A/ECB set and the real-slice test double), that each scheduled close (default and early closes), fixing time and publication falls on the same UTC date as its local session date; a negative control (Tokyo 07:00, Auckland 09:00, Los Angeles 17:30) proves it can fail. **No calendar failed.** (Half days: HKEX 12:10 HKT = 04:10 UTC and NYSE 13:00 are also on the same date.)

**Ruling 1.7 (1.12) item 4 (`source_registry_digest`).** `ComputationManifest.source_registry_digest` (part of the manifest id): the SHA-256 of the canonical JSON of the full `SourceRecord`s (`SourceRecord.to_obj`: every field, `terms_check` included), for every source with a file in the M the port read (M_t in Current mode), sorted by `source_id` (`marketdata.manifest.source_registry_digest`). `build_in_memory_market_data` collects the records of the sources with a file in the release and hands them to `InMemoryMarketData(source_records=...)`; the port reports them through `source_registry_records()`; `engine.registry_digest_of(port)` is `""` for a port that reports none. `PostgresMarketData` has no registry in its projection, so `read_release(..., registry=SourceRegistry)` takes the registry in force now, reads the source ids of the release's files from `md_file`, and reports the records (a source the registry lacks is `UnknownSourceError`, nothing is read); without a registry it reports none. `reproduce()` compares the digest after `identity_digest` and reports the new status `SOURCE_REGISTRY_MISMATCH`. Tests: the digest changes with every field, is order-independent; every manifest of a pack carries the build path's digest; a changed `independence_group` or `synthetic` flag changes it and `reproduce` reports the mismatch; the PostgreSQL projection and the in-memory build give the same manifest and result digest (`test_performance_cp3a`).

**CP4-4 (the pack summary).** `synthetic.py` no longer carries the stale limitation "is_conformant is False while ..."; `pack.py` lists, beside the conformance statement, the `market_data:` open items every manifest carries (`16_tolerances.market_data_open_items_in_manifests`, and a SUMMARY block). Tested on the synthetic pack.

**`market11.UNBUILT`.** The Current-mode item is removed: Ruling 1.7 (1.12) item 2 and item 5 are both built and tested, and the Quant rules that the source registry and the identity resolver are pinned by digest, not scoped to t (item 4). Four items remain.

**CP4-5 (mutants).** New behaviour tests kill: m1 (since-acquisition breakdown without minor units), m3 (attribution breakdown parts without minor units, and the `displayed_total` lineage), m9 (the F8-B key set from the caller's list: pure, and through PostgreSQL with a transfer-only listing the caller did not name) and m12 (a listing named only by a `TRANSFER_IN`: pure, and through PostgreSQL on all three entries). The vacuous "writes nothing" assertion now compares the ledger version before and after six computations. Also: the stale `performance_conventions` docstring ("`is_conformant` is False until CP3c to CP3e land") in `engine.py` is corrected.

**Decisions the contracts did not cover.** (1) `valuation_mode` of a Current-mode refusal is `HISTORICAL_AS_OF`, like a computed Current-mode manifest, since the enum has no Current value (the Quant's text says "Current": a question: add `CURRENT` to the manifest, or accept `as_of_rule` as the marker?); (2) a port that reports no registry records gives `source_registry_digest = ""` (nothing pinned), not the digest of an empty list; (3) the Postgres projection takes the registry as an argument rather than storing it (no migration), so a caller that omits it gets `""` and the same computation over the in-memory build gets a digest (the test that compares them passes the registry); (4) a refusal at the F8-B gate for a listing named between loads is raised before that finding's append, but findings decided earlier in the same run were already appended (the run is not one transaction); (5) `engine.registry_digest_of` treats an empty record list as "no records known". (Decisions (2), (3), (4) and (5) are superseded by §16.26.)

### 16.26 CP4 part A round 3: review section 34 (CP4-6 to CP4-9) and the Quant's build-note rulings (engineer; 2026-10-02; not yet reviewed)

`ENGINE_ID` `performance/cp4-0.13`. Conventions unchanged in id: performance/1.12, market-data/1.11, `minor-units/1.1` (the Quant ruled with no ruling-text change). No fixture change.

**CP4-6 (F8-B all or nothing; main-session ruling).** `LedgerAccess.atomic(portfolio_id)` is part of the access protocol; `confirm_splits` wraps the whole run (`_confirm_splits`) in it and refuses an access that has none (`TypeError`: no other design is chosen). `PostgresLedgerAccess.atomic` opens ONE transaction (a savepoint if the caller holds one) and takes the portfolio's ledger advisory lock FIRST (`pg_advisory_xact_lock(hashtextextended('finweb.ledger.portfolio:<schema>:<portfolio>', 0))`, the key the append trigger takes, migration 0008; the schema comes from `pinned_schema`, so a TEMP shadow is never reached), so loads and appends are one unit, no concurrent writer can name a new listing mid-run, and any exception rolls back every append of the run. The read-only accesses (`ReadOnlyLedgerAccess`, `PinnedLedgerAccess`) have a no-op `atomic`. The per-load policy test of CP4-1 stays (an access without a lock still gets it). The port could do this, so nothing is reported as impossible. Tests: the reviewer's reproduction in memory (L1's split decided, then B's case (c) refuses on the next load: the rows equal the rows before plus the concurrent writer's BUY, `appended` is empty, the version falls back); any exception after the first of two appends; an access without `atomic`; and through PostgreSQL as `finweb_app` (a failure on the second append leaves the version unchanged and no `finweb.f8b` row; the unfailed run appends both and is idempotent; a policy refusal appends nothing). The in-memory `FakeLedger.atomic` removes only the events the run appended (a concurrent writer's stay).

**CP4-7 (every refusal carries both digests).** `service._refusal_record` gives every refusal, Current or historical: `identity_digest` (a recording resolver is asked the exchange and currency of every listing the ledger names, plus whatever `D_c(t)` asks) and `source_registry_digest` of the port it read (`M_t` in Current mode); a refusal of an already computed result (the synthetic belt-and-braces refusal) carries that result's digests. `engine.refuse` / `_manifest` take `identity_digest` and `source_registry_digest`. The refusal's identity digest pins the facts the REFUSAL asked; it is not equal to the computed manifest's, which asks for more (the registry digest is equal, tested).

**`valuation_mode` (the Quant's ruling).** `ValuationMode.CURRENT_AT_INSTANT` (PD-0015 Part 1's Current / Latest mode on end-of-day data); `CURRENT_LIVE` stays and is refused. `engine._checked_mode` enforces the table at manifest build: `HISTORICAL_AS_OF` with `CALLER`, no instant, no parent release; `CURRENT_AT_INSTANT` with `D_c(t)`, the instant `t`, and the parent release `M`. A call site that carries all the Current fields but names no mode (the gains and attribution entries share one builder) is read as Current; any other combination raises `ManifestInvariantError` (an engine fault, before a manifest exists), including an explicit `CURRENT_AT_INSTANT` with no instant. `compute` no longer refuses `CURRENT_AT_INSTANT` as unsupported; only `CURRENT_LIVE` is refused. Every Current-mode manifest, computed or refused (including the coverage-gap manifest), records the Current value; `reproduce()` returns `MANIFEST_DIFFERS` for a manifest whose `valuation_mode` disagrees with its `as_of_rule` (before recomputing) and for a re-run whose mode differs. The window metrics have no Current entry point; the three Current entries (valuation, gains, attribution) and the four historical entries are tested computed and refused, pure and through PostgreSQL.

**CP4-8 and the Quant's ruling (the registry digest is never "").**
- `registry_digest_of(port)`: no market-data file read (`port` None, or a version that serves no observation) gives `source_registry_digest(())`, the empty-list hash. A port that serves file observations must report their sources' records: `InMemoryMarketData.source_registry_records()` raises `SourceRegistryNotPinnedError` (new, `marketdata.manifest`) when a served source has no record; a port with no `source_registry_records` is refused with the same error. The error is raised while the manifest is built, so no result and no value exists.
- `persistence.market_data_store.read_release(..., *, registry)`: the registry is REQUIRED (omitting it is a `TypeError`). Every source with a file in the release is checked with `require_attested` (a withdrawn attestation fails closed, market-data Ruling 4.7; an unknown source is `UnknownSourceError`).
- **One registry, used consistently (decision):** the stored rows are checked against the pinned records and a disagreement is refused (`RegistryDisagreesWithStoredRowsError`): each stored reading's `independence_group` must equal the record's, and its lineage `independence_group` and `upstream`, when set, must equal the record's (ingest always sets them). The alternative (ignore the stored values and re-derive from the registry) would change what reconciliation read at ingest and is a larger change to the projection; refusing is the narrower fail-closed choice: a registry that changed since ingest means the release must be re-ingested.
- `reproduce()`: a manifest with `source_registry_digest == ""` returns `SOURCE_REGISTRY_MISMATCH` with the detail "registry not pinned" before anything is recomputed; a re-run whose digest is "" does the same; "" against "" is never a match. Never `REPRODUCED` or `RESULT_NOT_COMPARED`.
- Test doubles: `k.records_for(readings)` supplies the records a double that serves observations must carry; every double in the suite was changed to pass it. The PostgreSQL tests pass `k.registry_for(world.store)`.
- Tested through PostgreSQL: omitting the registry, a missing source, a withdrawn attestation, a changed `independence_group` and a changed upstream, and the digest equal to the in-memory build's.

**CP4-9.** `choose_current_date` tests every field of a live event dated `D` that holds a `Money` (`dataclasses.fields`, so a currency-bearing field added later is seen): `amount`, `bought_amount`, `cost_basis`. A basis is in the event's own currency, so a foreign basis is a TRANSFER_IN / OPENING_POSITION in a currency other than R. Tests: the reviewer's USD to HKD conversion closing a -78 HKD balance to zero (`D_c` = 2026-10-01 at 12:00 UTC; 10-02 after the 14:00 UTC publication; the HKD-sold control), a USD-basis TRANSFER_IN of an HKD listing in an HKD portfolio (10-01; control in R: 10-02), a guard that exactly three fields hold `Money`, and an engine-level run (`compute_current` at the chosen date records `D_c` = 10-01 and every REPORTING value `CURRENT`; a window ending on 10-02 would translate the 10-02 conversion at the 10-01 fixing and is `STALE`).

**`market11.UNBUILT`.** The Current-mode item stays removed: items 2 (events dated `D`), 3, 4 (registry pinned, now never empty and fail-closed) and 5 (refusals) are built and tested.

**Mutants** (copies under `$TMPDIR`): killed: the atomic wrapper removed; the Postgres transaction removed; each refusal digest dropped; the Current value not recorded; the invariant fault removed; the empty-list hash replaced by ""; the "" check in `reproduce` removed; the early mode check removed; the served-source check removed; `require_attested` replaced by `get`; the registry made optional; the stored-row consistency check removed; `D_c(t)` limited to `amount`. **Survivor:** the late check "the re-run's valuation_mode differs" in `reproduce` (a redundant second guard: the early check and the manifest-id comparison already refuse every mode difference a re-run can produce).

**Decisions the contracts did not cover.** (1) the refusal's identity digest covers the ledger's listings plus the date choice (above); (2) the stored-row consistency check refuses on mismatch rather than re-deriving (above), and compares the lineage fields only when set (hand-made projections in the store tests carry none); (3) `read_release` requires the registry as a keyword (a call without it is a `TypeError`, not a defaulted empty registry); (4) a version that serves no observation is the empty-list digest, including a store built with no files; (5) the F8-B access protocol now has `atomic`, so any other implementation (none in `src/`) must supply it; (6) one `ENGINE_ID` (`cp4-0.13`) for the whole round.

### 16.27 CP4 part A round 4: review section 35 (CP4-10, CP4-11) and the lock-schema residual (engineer; 2026-10-02; not yet reviewed)

No engine module changed, so `ENGINE_ID` stays `performance/cp4-0.13` and `ENGINE_PINS` are unchanged. `ANALYTICS_PINS["store"]` was re-recorded (`marketdata/store.py`).

**CP4-10 (a file is SYNTHETIC_TEST if and only if its source is synthetic).** `read_release` now reads `(source_id, usage_scope)` of every file of the release from `md_file` and, after `require_attested`, refuses (`RegistryDisagreesWithStoredRowsError`, before any value) when a source's registry `synthetic` flag disagrees with the usage scope of any stored file of it (calendars and benchmarks included), as `ingest_file` does. Both directions: a registry calling synthetic rows real is refused, and the harmful mirror, a real source edited to `synthetic: true` with its terms check removed (which `terms_attested` would pass), is refused; an honestly real registry over real rows still needs its passing terms check. **The in-memory path had a gap for directly built stores:** the build path checks per file at ingest, but `InMemoryMarketData(source_records=...)` accepted any records, so `source_registry_records()` now also refuses a served reading whose `lineage.is_synthetic` differs from its record's `synthetic` (`SourceRegistryNotPinnedError`). The earlier test that flipped a double's `synthetic` flag to show a digest change now expects that refusal (the digest change is shown with `independence_group`). Tested through PostgreSQL as `finweb_app` (both directions, and the consistent registry reads) and in memory.

**CP4-11 (the F8-B lock is tested).** `Cp4_11LockTests`: while one connection is inside `PostgresLedgerAccess.atomic(portfolio)`, an append on a second connection (`lock_timeout` 300 ms, set on that connection, so the server bounds the wait and no sleep synchronises anything) fails with sqlstate `55P03`; an append for another portfolio is not blocked (the lock is per portfolio); after the context ends the append succeeds; a run that raises releases the lock. The reviewer's mutant r1 (lock removed) and a wrong lock key are both killed.

**Lock schema (the residual).** It was cheap, so it is done: `PostgresLedgerAccess.ledger_schema()` finds the schema FROM THE APPEND TRIGGER ITSELF (`ledger_event_before_insert` on `ledger_event`, among the non-temporary schemas of `current_schemas(false)`), the value the trigger's key uses (`TG_TABLE_SCHEMA`), instead of `pinned_schema`'s first search-path schema; exactly one candidate is required (none or several fail closed, `RuntimeError`). Tested: it equals the schema of the tables; a TEMP shadow of `ledger_event` with `pg_temp` first on the path does not change it (the shadow is excluded by its schema name, `pg_temp*`; it is not true in general that a TEMP table could not carry a trigger); a search path with no ledger schema fails closed; and (CP4-12) two schemas holding a ledger on one search path, in both orders, make `ledger_schema()` and `atomic` raise `RuntimeError` (the insert goes to the first schema's table, so a lock named for another would not block a concurrent append). The mirror test's comment is corrected: only the FILE records (`md_file.usage_scope`) are stored as real there; the readings inside are still synthetic. The lock test above proves in practice that the key equals the trigger's.

**Mutants** (copies): killed: lock removed; lock key changed; the PostgreSQL synthetic check removed (both PostgreSQL tests); the in-memory check removed. The earlier survivor (accepting several candidate schemas, `len(rows) < 1`) is killed by the CP4-12 test with two `PgSchema` instances.

**Decisions the contracts did not cover.** (1) The PostgreSQL check compares per file (the usage scope of every file of the release), the in-memory check per reading; (2) the in-memory check lives in `source_registry_records()` (the single place every manifest passes through), not in the constructor, so a double can still be built and fail only when a manifest needs its registry.

---

## 17. CP4 — risk and benchmark engine (engineer-proposed; PLAN ONLY; not yet reviewed, not product law)

**Added 2026-10-02 by `engineer`. Plan only: no product code, migration or dependency is written or changed by this section.**
(The stray line `EOF` that ended §16.27 was removed when this section was appended.)

Authority and inputs: PRD §13, §14, §16.3, §17.2, §11.1 to §11.4, §33 (the methodology registry; PRD §34 is the
reproducibility requirement, and this plan uses both), §38.3 (CP4) and §38.4 (HG3); FR-017, FR-018, UAT-03; PD-0006,
PD-0014, PD-0015, PD-0025, PD-0027, PD-0031 to PD-0033, PD-0035, PD-0036, PD-0038 (HG2 conditions 3 and 4), PD-0039
(D1 to D5); `reviews/CP4_PLAN.md` (the working plan, §5 the Quant's questions, §6 the build sequence); §15 and §16 of this
plan; `methodology/CP3_PERFORMANCE_CONVENTIONS.md` (`performance/1.12`) and `methodology/CP2_MARKET_DATA_CONVENTIONS.md`
(`market-data/1.11`). Evidence markers as in §15 and §16: **[F]** fact from a source document or from the code as read
on 2026-10-02, **[J]** engineer judgment, **[A]** assumption to verify, **[Q]** depends on the `quant-analyst`'s `risk/1.0`,
**[H]** a human (owner) step, **[PM]** a decision for the main session.

**What this section does not decide.** The Quant is writing `risk/1.0` (`methodology/CP4_RISK_CONVENTIONS.md`) in
parallel. This plan reads none of its content. Every place where a financial method, convention, tolerance or sufficiency
threshold is needed is a **plug point** (17.2): a named, versioned, injected rule that is a **placeholder** until the Quant's
text is implemented, exactly as in CP3a (§16, intro). While any slot is a placeholder, `RiskConventionSet.is_conformant` is
False, every result says so, and a metric that needs an unruled slot is `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION`
(the CP1 and CP3a pattern). Where this plan states a default it is structural (a state may not be dropped; a number is never
formed from an input that is not available; nothing is rounded silently), never a financial value. If `risk/1.0` and this
plan disagree, the document wins for method and this plan is amended. If a fixture disagrees with the code, that is a finding
for the Quant, not a value to adjust.

**Scope [F] (PD-0039 D3):** volatility, downside deviation, maximum drawdown, Sharpe, Sortino, beta, Jensen's alpha with
R-squared, active return, tracking error, information ratio, the methodology registry and the sufficiency checks. VaR,
Expected Shortfall and rolling analytics are out (after HG3). **Data [F] (D1, D2):** CP4 is built and proved on synthetic
benchmark and risk-free series behind source-independent contracts; real data waits on owner steps (17.4.4, 17.12).

### 17.0 Summary of the shape

1. **One return definition.** A risk return series is a series of period TWRs from the CP3 engine (segment form, flows
   neutralised, FX at flow-date and valuation-date fixings, the same states and freshness). There is no second return
   definition (PD-0014 section 2.5). The new object is `ReturnSeries` in `src/performance/series.py` (17.3). It is built
   from **boundary valuations** (the primitive), so any consecutive pair of boundaries gives an exact period return, and the
   linking identity `product of (1 + r_k) = 1 + TWR(B, E]` holds exactly and is a runtime identity (I-10, 17.3.5).
2. **The statistics live in a new pure package `src/risk/`** that imports `performance` (results, numerics, series,
   manifest) and never the reverse. Same AST boundary rules as `performance`. Exact `Fraction` intermediates; at most one
   certified square root per reported number; no float; no `math`.
3. **Two new market-data inputs, one contract each.** `BenchmarkSeries` already exists as a normalized kind (contract,
   `DataKind.BENCHMARK`, `md_benchmark` tables, `port.benchmark`, the mock adapter) [F]; what is missing is the analytics
   read (levels to period returns with price-of-date, freshness and currency translation) and the lineage policy. A
   **risk-free rate series is a new kind** (`DataKind.RISK_FREE`, new contract, new tables, new migration). Both are read
   through the one `MarketDataPort`, pinned by the one release `M` (and `M_t` in Current mode).
4. **Benchmark selection is user data** (migration 0015, dated, append-only, CP1-style corrections, `SELECT, INSERT` only
   for `finweb_app`). The engine never selects a benchmark; a benchmark-dependent result cites the exact selection row it used.
5. **Manifests are partitioned by dependency.** A new `finweb.risk_manifest/1` carries only the inputs a metric group
   depends on, derived mechanically from the registry's `benchmark_dependency` and `risk_free_rate_dependency` fields. So a
   change of benchmark changes the benchmark-dependent manifests and leaves the independent ones (volatility, drawdown)
   byte-identical (UAT-03, in both directions). CP3 manifests, canonical dicts and the committed HG2 pack stay
   **byte-identical** (a test regenerates the synthetic pack and compares).
6. **A populated methodology registry** (17.6): one `MethodologyEntry` per metric and version, a superset of the PRD §33
   fifteen fields, read by the engine for its thresholds (the engine holds no threshold), by the evidence views, and later
   by the AI layer. A test ties the data to the `risk/1.0` text.
7. **Results are not stored in CP4** (17.8), as in CP3. A bounded in-process memo keyed by the full question digest is the
   only caching allowed, and it is outside the manifest and provably output-neutral.
8. **Unsupported means a state, never an exception and never a number.** A METRIC x CONDITION availability matrix for the
   risk ids (17.9) is the exit evidence, with cells written from the Quant's fixtures, never from the engine's output.
9. **Cost is a measured gate, not an assumption** (17.3.4): exact rational arithmetic over a 3-year daily series is
   expensive, and CP4b ends with a measured budget and a mitigation ladder decided with data.

### 17.1 What exists today, as read [F]

- `performance.engine`: `compute_window` (TWR, annualization, MWR, lines), `compute_current`, `compute_gains`,
  `compute_attribution`, `reproduce`; a private `_Run` holding live events at L, a per-day valuation cache, and the data read
  for the manifest; `twr_segments(base, end, flows, valuation, conventions)` in `performance.returns`, which needs only
  `V_B`, `V_E` and, per flow day, `V_{D-1}` and `V_D`, and returns a `ReturnOutcome` with a `Valued` (state, reason, exact,
  causes, freshness) and details (`ZERO_CAPITAL_RUN`, `NON_POSITIVE_BASE`, `NEGATIVE_VALUE`).
- `performance.periods`: half-open windows `(B, E]`, `resolve_window` (a window that starts before inception is
  `INSUFFICIENT_DATA` + `WINDOW_BEFORE_INCEPTION`, deliberately, `performance/1.0` Ruling 5.4), the end-of-month rule.
- `performance.numerics`: `present(value, point, currency, rule, width)` with a certified `width` bracket and the tie rule
  (a bracket straddling a rounding boundary rounds half-up away from zero and sets `tie`), `growth_root`, `carino_link`,
  `solve_irr`, `MAX_BITS` and `within_bounds`.
- `performance.registry.METRIC_IDS` (24 ids): `build_metric` refuses an id that is not in it; the availability-matrix test
  fails for an id without a row. `ComputedMetric` (exact, state, causes, `window: WindowUsed` with `frequency`, `method_id`,
  `numeric_basis`, `lineage`, `details`) and `ComputationManifest` (`methodology` is empty "while the registry is empty").
- `marketdata`: `BenchmarkSeries` / `BenchmarkPoint` / `BenchmarkValueKind(LEVEL, RETURN)` / `LicensingMetadata`;
  `Lineage.adjustment_status` (`RAW`, `SPLIT_ADJUSTED`, `DIVIDEND_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`, `UNDECLARED`);
  `port.benchmark(benchmark_id, start, end) -> BenchmarkSet` (one series per source, no price-of-date, no freshness);
  `InMemoryMarketData.benchmark`; `md_benchmark` and `md_benchmark_point` (migration 0010); `ingest_file` accepting
  benchmark output; the mock adapter producing benchmarks; `SourceRecord` with `synthetic` and `terms_attested`.
- `product_contract.methodology_registry`: the schema (`REQUIRED_FIELDS`, 15 fields) and validator, and
  `EMPTY_METHODOLOGY_REGISTRY` (zero entries; AC-17 asserts this). **This conflicts with a populated registry: see 17.6.5 and
  open question Q1.**
- Grants are specified by `tests/product/test_postgres_least_privilege.py` (`APP_GRANTS`, `MD_TABLES`), not by migrations [F].

### 17.2 Plug points: the dependency on `risk/1.0`

Each row is an injected slot of `RiskConventionSet` (or of the registry, row P-15). Until the Quant's text is implemented
the slot is `placeholder/<slot>/0`. The right column is the CP4_PLAN section 5 question it answers.

| ID | Slot | What the engine expects | CP4_PLAN section 5 |
|---|---|---|---|
| P-1 | `boundary_rule` | `(frequency, window (B,E], calendars) -> sorted dates`; which close ends a week across US/CN/HK, holiday weeks, month-end | Q2 |
| P-2 | `return_form` | simple, or log (log needs a certified `ln`, so it is a separate numeric path) | Q2 |
| P-3 | `annualization` | periods per year by frequency; arithmetic or geometric; where the square root is applied | Q3 |
| P-4 | `estimators` | divisor (n-1 or n) for variance, covariance and tracking error | Q4, Q7 |
| P-5 | `downside` | threshold (0, the period risk-free rate, or a user value); denominator; zero-return periods | Q4 |
| P-6 | `risk_free` | tenor; rate basis to period accrual (simple or compounded, day-count, de-annualization); the series per reporting currency; behaviour with no series | Q5 |
| P-7 | `excess_return` | per period or annualized; Sharpe, Sortino and alpha formulas | Q5, Q6 |
| P-8 | `regression` | OLS of excess returns with intercept; alpha annualization; R-squared definition | Q6 |
| P-9 | `benchmark_treatment` | currency (translate levels at boundary fixings, or native, explicit); accepted adjustment bases (total return, price return); a `RETURN`-kind series compounding; price-of-date and freshness thresholds in sessions | Q6, Q9 |
| P-10 | `relative` | active return arithmetic or geometric; tracking error and information ratio annualization | Q7 |
| P-11 | `drawdown` | the M1-F6 window convention (peak-to-trough inside the window or running maximum over history), peak and trough ties, which outputs are reported | Q1 |
| P-12 | `sufficiency` | minimum observations per metric and frequency; short-window policy (refuse as CP3 does, or clip to inception and label the actual window); gap policy (suppress, drop with disclosure, or bridge by merging adjacent periods); eligibility of zero-capital periods; a stale-share threshold | Q8 |
| P-13 | `comparability` | the PD-0014 rule: measure, thresholds in sessions, and whether it moves the state to `LIMITED` or is a disclosure beside `AVAILABLE` | Q9 |
| P-14 | `risk_rounding` | presentation points and decimals for volatility, ratios, beta; declared tolerance for transcendental outputs; the certified enclosure width | Q3 |
| P-15 | `registry_appendix` | a machine-readable registry appendix in `risk/1.0` (17.6.3) | Q10 |
| P-16 | `source_disagreement` | what two benchmark sources that differ on a date do (default: fail closed, `SOURCE_CONFLICT`, with the tolerance from the Quant) | Q8 |
| P-17 | `details_vocabulary` | the fixed detail names for risk (the engine proposes names in 17.7.7) | Q8 |
| P-18 | `scope` | portfolio scope only, or account scope as well (default until ruled: portfolio only; an account-scope request is refused with the detail `SCOPE_NOT_SUPPORTED`) | not asked: added |
| P-19 | `fixture_format` | `cp4_golden` assertion shape: expected value, state, reason, details, tolerance per assertion, convention minimums (Ruling 11.6 of `performance/1.8`) | section 7 |
| P-20 | `hg1_reconciliation` | which HG1 prototype rulings `risk/1.0` adopts or supersedes; the engine implements only what `risk/1.0` states | Q11 |

No new reason code is planned. The precedent is PD-0036 (OD-P5): `INSUFFICIENT_DATA` with no code and a specific detail name.
`MISSING_BENCHMARK` already exists and is used for a missing, unselected or unreadable benchmark. A missing risk-free series
is `INSUFFICIENT_DATA` with the detail `RISK_FREE_SERIES_MISSING`. If the Quant asks for a code (CP4_PLAN D4), the owner
decides, and it enters `REASON_PRIORITY` only through that decision. **[PM]**

### 17.3 The periodic return series spine (CP4b)

#### 17.3.1 Objects

```
src/performance/series.py        (pure; imports performance.* and marketdata analytics modules only)
  Frequency                      DAILY | WEEKLY | MONTHLY
  BoundaryRule (Protocol)        [Q P-1] (frequency, window, calendars) -> Tuple[date, ...]   (supplied by the convention set)
  BoundarySet                    sorted dates b_0 < b_1 < ... < b_n, the frequency, the rule id, the calendars cited
  BoundaryValue                  one date: Valued total (state, reason, exact, causes, freshness) and the price dates used
  PeriodReturn                   (start, end, Valued, details, flow_days, zero_capital: bool, merged_from: int)
  ReturnSeries                   BoundarySet + the boundary values + the flows + the per-period returns, WindowUsed
                                 (requested and used), frequency, state summary, observation counts
  link_identity(series)          I-10: product of (1 + r_k) == 1 + TWR(b_0, b_n] exactly, per consecutive eligible run
```

`PeriodReturn` is not a new return formula. It calls `twr_segments(b_{k-1}, b_k, flows, valuation, conventions)` with the
same `valuation` callable (`_Run.total`) that CP3 uses, so the state, reason priority, freshness vector, `ZERO_CAPITAL_RUN`,
`NON_POSITIVE_BASE` and `NEGATIVE_VALUE` behaviour are CP3's, not re-implemented (`performance/1.1` Rulings 5.3 and 5.5).

#### 17.3.2 How a daily, weekly or monthly series is produced

1. **Window.** `resolve_window(spec, end, inception, ...)` as in CP3 (`TRAILING_MONTHS` 12, 36, 60, `SINCE_INCEPTION`
   for "max"). The PRD default is `TRAILING_MONTHS 36`, weekly, in the reporting currency. CP3 refuses a window that starts
   before inception. PRD section 14 says a metric must "state the actual window it used". Which of the two applies to a short
   history is **P-12** (refuse as CP3, or clip to inception and label). The plan supports both: `WindowUsed` gains optional
   `requested_months` and `requested_start` fields (additive; serialised only when present, so CP3 canonical dicts do not
   change), and `resolve_series_window(spec, end, inception, policy)` returns either the CP3 refusal or the clipped window with
   the requested one retained.
2. **Boundaries.** `BoundaryRule` (P-1) returns the dates. The engine never decides what a week is. The calendars it needs are
   `CALENDAR` files already in `M`, so they are cited in the manifest as CP3 cites them. Monthly can reuse
   `periods.add_months` (end-of-month rule) if the Quant adopts it.
3. **Valuations.** Only the dates `twr_segments` requires are valued: the boundaries, and for each flow day `D` both `D-1`
   and `D`. A daily series needs every boundary. A weekly or monthly series values far fewer days. All go through
   `_Run.valuation` and its per-day cache, so a date needed by two periods, or by two metrics in one call, is valued once.
4. **Flows.** `_window_flows` is called once for `(b_0, b_n]`; per-period flow lists are slices. `group_flows` is hoisted so
   it is not recomputed per period.
5. **Merging** (only if P-12 selects gap bridging): a boundary whose valuation is `INSUFFICIENT_DATA` can be removed and its
   two neighbouring periods merged into one longer period (`period_return(i, j)`, a TWR over `(b_i, b_j]`, which is well
   defined). The merged period is flagged (`merged_from = 2`) because it changes the observation's horizon. Because the series
   keeps the boundary values, the policy is applied after the values exist and no valuation is repeated.

#### 17.3.3 Per-period state and freshness

- Each period carries its own `Valued` (state, reason, causes, freshness). Nothing is averaged or hidden.
- The series carries a `SeriesAssessment`: counts by state (`AVAILABLE`, `AVAILABLE+STALE_DATA`, `LIMITED`,
  `INSUFFICIENT_DATA`), counts of `ZERO_CAPITAL_RUN` periods, the union freshness vector, and the first and last boundary that
  failed. A statistic reads the assessment and the rule of P-12; it never re-derives states.
- The default aggregation until P-12 is ruled is the existing `PerformanceAggregation.combine` over all periods' parts (worst
  state wins, reason chosen by the Ruling 1.5 order, every cause kept). A stricter or looser rule (for example a stale-share
  threshold) is the Quant's and is plugged in.
- A zero-capital period (`ZERO_CAPITAL_RUN`, return exactly 0) must **not** silently count as an observation: it would bias
  volatility, beta and Sharpe for a young or empty portfolio. The series flags it, and P-12 says whether it is eligible.
  This is a case the CP3 spine hides inside a valid-looking 0 and the risk layer must not.

#### 17.3.4 Cost, and a measured gate

[J] Estimated work for a 3-year daily series over L live events and N listings: about 750 session dates (about 1,100 calendar
days if every calendar day is valued) times (one `reconstruct(events, D, L)` fold of O(L) plus N `quote_on` and the FX
lookups). The in-run cache removes repeats; the benchmark leg adds one lookup per boundary. A weekly series is about 157
boundaries. Two costs are not obvious:

- **`reconstruct` is called per date and folds the whole ledger each time.** An incremental fold that yields the position
  state at many dates in one pass, `domain.replay.reconstruct_series(events, dates, L)`, would be an **additive CP1 change**
  with one proof: for every date it returns exactly what `reconstruct` returns (a property test over the existing CP1
  fixtures and random ledgers). Not built unless the measurement says it is needed. **[PM]**
- **Exact rational growth.** Period returns are ratios of sums of products of decimal prices, quantities and FX rates, so their
  denominators are not powers of ten once an FX cross appears. Summing hundreds of such `Fraction`s builds a common denominator
  of tens to hundreds of thousands of bits, and `Fraction`'s gcd on each addition is quadratic. A naive loop could take
  minutes for daily statistics.

**Gate at the end of CP4b (before CP4c starts):** a test-tool run (`risk_tools`, not in the default suite) builds a worst-case
3-year daily series (30 listings, three currencies, 2,000 ledger events, 40 flow days), prints timings for the spine and for the
exact sums the statistics will need (mean and sum of squares of 756 returns), and records bit lengths. The budget is a **[PM]**
decision (a proposed starting point: a full weekly 3-year risk set in a few seconds, daily in tens of seconds, on the
development machine). Mitigation ladder, in order, each one output-neutral and proved by byte-identical results against the
naive path: (1) pairwise (tree) summation, which keeps operands the same size; (2) integer accumulators over an explicit common
denominator, normalised once; (3) `reconstruct_series`; (4) only if all fail and the Quant agrees it is within the declared
tolerance policy, exact rationals replaced by certified rational **enclosures** with bounded bit length (outward rounding),
with the presented value still certified or flagged as a tie. The plan does not round a return before a statistic: that would
be a method choice, and it is the Quant's.

#### 17.3.5 Identities (self-consistency, like I-2/I-3 in CP3)

- **I-10 (linking):** for a run of consecutive eligible periods covering `(b_i, b_j]`, `product(1 + r_k) = 1 + TWR(b_i, b_j]`
  exactly. It holds by construction of segment TWR (a flow-free run collapses to the ratio of end values and the daily
  product equals the segment product, I-2), so it is a cheap exact check on the series builder.
- **I-11 (boundary coverage):** every date in `required(period)` has a boundary value, and no valuation outside the required
  set was read (the cache's key set equals the required set; a hidden-input guard).
- Both run in `verify_identities=True` mode and in the CP4 exit test. A failure is an engine fault, not a metric:
  `INSUFFICIENT_DATA` + `CALCULATION_ERROR`, as in CP3.

#### 17.3.6 The benchmark leg and the risk-free leg on the same boundaries

- `BenchmarkLeg`: from a `BenchmarkSeries` of kind `LEVEL`, the period return on `(b_{k-1}, b_k]` is `L(b_k) / L(b_{k-1}) - 1`
  with the level of the date from a **price-of-date read** (the last print on or before the boundary, with `date_used`,
  `missed_count` and freshness in sessions, like `quote_on`; P-9 gives the freshness thresholds and the calendar). For kind
  `RETURN`, the source's returns are compounded exactly over the period. If P-9 says translate to the reporting currency, the
  level is multiplied by the boundary fixing from `port.fx_on` through the same `marketdata.states.fx_input_state` mapping the
  valuation uses (never a second FX reader). Each benchmark period carries a `Valued` like a portfolio period.
- `RiskFreeLeg`: from a `RiskFreeSeries`, the period risk-free return on `(b_{k-1}, b_k]` per P-6. If the accrual is a
  non-integer power it is a certified numeric (precision 50, as `annualize`), and the leg says so in its `numeric_basis`.
- `JointSeries` (in `risk`, 17.7): the intersection of eligible periods across the legs, with the per-leg effective dates kept
  for the PD-0014 disclosure. The spine itself knows nothing about a benchmark or a rate; it only produces portfolio periods.

### 17.4 Market-data kinds (CP4b)

#### 17.4.1 BenchmarkSeries: what is new

The contract, storage and port read exist [F]. New work:

- **Analytics read.** `MarketDataPort` gains `benchmark_levels_on(...)`/`benchmark_period_input(...)` returning a typed
  lookup (`LookupOutcome`, `date_used`, `missed_count`, freshness, consumed files, `synthetic`, lineage notes,
  `adjustment_status`, licensing), the benchmark analogue of `QuoteLookup`. The existing `benchmark(...)` stays (verification and
  fixtures use it). Both implementations (`InMemoryMarketData`, the PostgreSQL read path) and the Current-mode view
  `DerivedReleaseView` (which must apply the same `retrieved_at <= t` filter to benchmark files) are extended, and every test
  double of the port is updated. **[J]** This widens the `Protocol`; the alternative, a separate `ReferenceRatesPort`, was rejected
  because it would add a second release pin and a second Current-mode filter, and the whole design rests on one `M`.
- **Lineage policy (PRD section 11.3).** The engine only uses a benchmark whose `adjustment_status` is accepted by P-9
  (`TOTAL_RETURN_ADJUSTED` is the natural basis for a comparison with a portfolio whose TWR includes income; a price-only
  series, `RAW` or `SPLIT_ADJUSTED`, is either refused or used with a disclosure, as the Quant rules). `UNDECLARED` is never
  used (fail closed), and a **basis mismatch is never silent**: the result carries `benchmark_basis` and the comparability
  note. Raw, split-adjusted, dividend-adjusted and total-return series are never mixed within one benchmark id: two files for one
  `benchmark_id` with different adjustment statuses are `SOURCE_CONFLICT`, not merged.
- **Catalog.** `benchmark_id` needs reference data the series does not carry: display name, the calendar for freshness, the
  currency, the expected adjustment basis, the markets it represents (for a future recommender). **[J]** A committed, versioned
  data file `data/marketdata/BENCHMARKS.json` (a catalog record, not a source), read by the same loader pattern as
  `SOURCES.json`, with a `catalog_digest` cited in the risk manifest. It lists the benchmarks CP4 knows, synthetic ones
  included. Its content for real indices is **[PM]/[Q]** (which indices, which are recommended for which portfolios is a
  judgment the engine does not make; FR-017 "recommend" is presentation and is not built in CP4).
- **Licensing.** `LicensingMetadata` already says `display_permitted` only with `LICENSED`. The risk result carries the
  benchmark's `license_status`, so a result derived from an `INTERNAL_DEVELOPMENT_ONLY` index cannot be presented as
  displayable by a later layer.

#### 17.4.2 RiskFreeSeries: a new kind

**[J]** A separate kind, not a `BenchmarkSeries` with a rate flag. A rate series is not a benchmark; reusing the type would make
a rate selectable as a benchmark and would mix two units in one table. The new pieces:

- `DataKind.RISK_FREE` and a contract `RiskFreeSeries(series_id, provider, currency, tenor, points, rate_unit, rate_basis,
  day_count_declared, timing, lineage, licensing)` with `RiskFreePoint(value_date, rate: Decimal)`. `rate_unit` is
  `PERCENT_PER_ANNUM` (the converting rule, percent to ratio, is exact: 4.25 percent is 17/400). `rate_basis` is what the
  source declares (for example bank discount, coupon-equivalent, simple annualized); an **undeclared basis is refused**
  (fail closed, as an undeclared adjustment is). A rate may be negative (EUR has been), so only finiteness is checked
  structurally; plausibility bounds are not the engineer's to choose.
- Port reads: `risk_free_on(currency, as_of, conventions)` returning the same typed lookup (outcome, `date_used`,
  `missed_count`, freshness in sessions, consumed, synthetic, lineage) and `risk_free_series(currency, start, end)`. **Which
  series serves which currency** is a slot (`P-6`), a small catalog row in `BENCHMARKS.json`'s sibling `RISK_FREE.json`
  (series id per reporting currency); a currency with no series gives the detail `RISK_FREE_SERIES_MISSING`.
- **Migration 0016** (a second migration, **[PM]**; PD-0039 names 0015 for the selection): `md_risk_free` and `md_risk_free_point`
  (same shape as `md_benchmark`, plus tenor, unit, basis, day count; `abs(value) < 1E30 AND scale(value) <= 24` as 0010), the
  `md_file.data_kind` CHECK widened to admit `RISK_FREE` (drop and re-add the constraint; the auto name is
  `md_file_data_kind_check` **[A]**, to be read from the catalog, not assumed), append-only and sealed-release triggers extended
  to the two tables (the 0011 pattern, with the pinned `search_path` block repeated for any replaced function), `MD_TABLES`
  extended so `finweb_app` has `SELECT` only. **Compatibility proof:** every existing release's `projection_digest` is
  byte-identical after the migration (the new tables are empty for them), and the release row, file and observation counts
  for the synthetic pack do not change. 0001 to 0015 are never edited.
- Source-registry and `M_t` coverage: `source_registry_records()` and the CP4-10 usage-scope check must include sources whose
  only files are benchmark or risk-free files (so their terms checks are pinned in `source_registry_digest`).

Rejected: storing the risk-free rate as a column of the benchmark table (type confusion), a declared constant per currency
(PD-0039 D2 rejects it), and reading the rate from the FX tables.

#### 17.4.3 Source adapters for synthetic files, and the terms gate

- Synthetic benchmark and risk-free files are produced by hand-authored JSON through a typed synthetic adapter pair:
  `adapters/synthetic_benchmark.py` and `adapters/synthetic_risk_free.py` **[J]** (the mock adapter already carries a
  `benchmarks` shape; the risk-free kind needs its own parser, and keeping the two typed avoids growing the mock). Adapters are
  pure (bytes plus manifest in, observations out) under the existing adapter import allow-list, with the AST boundary test.
- Sources `synthetic.benchmark` and `synthetic.riskfree` are entered in `SOURCES.json` with `synthetic: true`, so
  `terms_attested` is true by construction and every reading carries `usage_scope SYNTHETIC_TEST`, which makes `contains_synthetic`
  true for the release (market-data Ruling 4.8) and every dependent result synthetic; the product service refuses a user
  portfolio against it (the PM ruling of 2026-10-01 carries over unchanged).
- The **terms gate is by source, not by kind** [F] (`SOURCE_TERMS_NOT_ATTESTED` in `ingest`), so it already applies to the new
  kinds. A test asserts it per kind: a real-flagged source with no passing `terms_check` is refused for a benchmark file and for
  a risk-free file; and the CP4-10 rule (a file is `SYNTHETIC_TEST` if and only if its source is synthetic) holds for both.

#### 17.4.4 A real adapter for US Treasury daily bill rates (later; needs the owner)

Not built in CP4b. Built only after the owner supplies the items below, against a real file, with committed tests on a
hand-made synthetic file in the same format (real captures stay local and git-ignored, the 2026-10-01 PM ruling).

**What I need from the owner [H]:**
1. **A real file.** Download the "Daily Treasury Bill Rates" for at least one full calendar year from the Treasury's
   interest-rate data page (CSV preferred; the request URL and parameters recorded in the file manifest, as the other human
   downloads do), and register it with the human-only `register-file`. **[A]** I recall one row per business day with columns
   per tenor (4, 6, 8, 13, 17, 26 and 52 weeks), each in a "bank discount" and a "coupon equivalent" variant, but I have not
   seen the file and the layout must be read from it, not assumed (the MD-OI-12 discipline: a MEMORY profile does not admit
   real data until the first real file has been profiled).
2. **A `SOURCES.json` entry** for the source, for example `source_id` `ustreasury.billrates`, `upstream_provider` "U.S. Department
   of the Treasury", `independence_group` `ustreasury`, `terms_url`, and `terms_check` with `checked_by`, `checked_on`,
   `permits_internal_development_use` and `notes` (the attestation). Only the owner decides this (PD-0031, PD-0039 D2); the
   engineer and the main session do not draft the verdict. Without a passing check, the loader refuses the file.
3. **Confirmation of the tenor** the project will use (the Quant sets the convention, P-6; the owner confirms nothing
   about method) and, if needed, the business-day calendar the series follows (see below).

**What I need from the Quant:** a precision-profile entry (market-data Appendix A.3 form) for the Treasury file: the column(s)
read, `NumberFormat` (text decimal), `delivered_dp` (rates appear to be quoted to two or three decimals **[A]**), the unit
(percent), the declared rate basis and day count, and a calendar rule. Profiles are the Quant's transcription
(`marketdata/profiles.py` is "a transcription of Appendix A"); the engineer adds the entry and the adapter only to that text.
**Precision profiles for the synthetic sources** (benchmark levels and rates, all `TEXT_DECIMAL`, `DECLARED`) are written the
same way and are needed for CP4b.

**Freshness calendar.** Freshness of a rate is counted in sessions of some calendar (PD-0014). Treasury publishes on business
days; whether the existing `NYSE_SESSIONS` or a Treasury calendar governs is a Quant ruling (P-9, P-6). The ECB-style rule
applies: a calendar is registered by the owner before real data is used (HG2 condition 4 pattern).

Other reporting currencies: no free public series is admitted for CNY or HKD, and EUR would need a separate source (the
D2 note names the ECB's euro short-term rate). Until a series exists, Sharpe, Sortino and alpha in those currencies are
`INSUFFICIENT_DATA` with `RISK_FREE_SERIES_MISSING`. That is the correct P5 behaviour and the plan does not invent a rate.

### 17.5 Benchmark selection storage (CP4b; migration 0015)

#### 17.5.1 Model

A **selection** is the user's explicit choice of one primary benchmark for one portfolio (FR-017: "recommend but require
explicit selection"). It is a standing instruction, not a historical fact, so "the latest live row wins" is its natural
correction; but because results cite it and must stay reproducible, rows are immutable.

`benchmark_selection` (one table), **[J]** shaped like the ledger:

| Column | Rule |
|---|---|
| `selection_id uuid` PRIMARY KEY | client-supplied; resubmitting the same id with identical content is an idempotent no-op returning the existing row, with different content an error (the CP1 `_find_existing` rule) |
| `portfolio_id uuid` NOT NULL, FK `portfolio` | the owner |
| `selection_seq bigint` NOT NULL UNIQUE | drawn by the trigger from a sequence **after** taking the per-portfolio advisory lock (`finweb.benchmark_selection.portfolio:<id>`), so within a portfolio the order equals commit order (the 0003 ordering, a distinct lock namespace so it never contends with the ledger lock) |
| `record_type text` | `SELECT`, `CLEAR` (the user removes the benchmark: the portfolio then has none), `REVERSAL` |
| `benchmark_id text` | present exactly when `record_type = 'SELECT'`; not a foreign key (the catalog is a file); the service checks it against the catalog and the compute path re-checks it (`BENCHMARK_ID_UNKNOWN` gives `MISSING_BENCHMARK`) |
| `catalog_version text` | the catalog version the id was checked against (audit) |
| `origin text` | `USER_CHOSEN` or `RECOMMENDATION_ACCEPTED`, present for `SELECT`; the system never creates a row on its own (a test asserts no code path other than the user-facing service appends) |
| `selected_on date` NOT NULL | the user's session date, passed in by the service (no clock in the engine, domain or compute path). It is the economic date of the choice |
| `reverses_selection_id`, `corrects_selection_id uuid` | the CP1 correction pair (see below) |
| `recorded_at timestamptz` NOT NULL | stamped by the trigger; **never a computation input** (the R3-2 rule) |
| `append_xid xid8` | stamped by the trigger (the 0008 pattern) so a reversal and its correction can be tied to one transaction |

**Dated, append-only, corrections in the CP1 style.** Append-only: `UPDATE`, `DELETE` and `TRUNCATE` are refused for every role by
trigger (the 0003 and 0011 pattern). A mistaken row is never edited. A `REVERSAL` names the row it withdraws (it cannot reverse
a reversal; the target must belong to the same portfolio, enforced by a composite foreign key as for the ledger). A
`corrects_selection_id` row is a replacement and may be appended only for a row that has been reversed, once per row, in the
same portfolio (the unique-index and trigger rules of 0002, 0003 and 0006, with the epoch-safe `xid8` comparison of 0006 and
0008). Resolution **[J]**:

> `selection_in_force(portfolio, S)` = among rows with `selection_seq <= S` that are `SELECT` or `CLEAR` and are not reversed by
> a `REVERSAL` with `selection_seq <= S`, the one with the greatest `(selected_on, selection_seq)`; none gives "no benchmark
> selected".

A non-correction insert must have `selected_on` not earlier than the latest live row's (trigger rule), so a back-dated plain
selection cannot slip behind a later one. A correction row carries its own `selected_on` (the corrected row's date, set by the
service), which places it where the wrong row was, exactly as a corrected ledger event keeps its economic date. `S` is the
knowledge version: a result pins `S`, so it is reproducible after later changes and after a reversal.

**Minimal alternative [PM]:** drop `selected_on` ordering and the correction pair, keep `SELECT`, `CLEAR`, `REVERSAL` and
resolve by `selection_seq` alone. Simpler, and sufficient for FR-017 and UAT-03. I recommend the fuller design only if the owner
wants a dated history of the choice shown to the user ("you chose X on 2026-03-01"); otherwise the minimal one. Both are append-only.

**Which view uses which selection [PM]:** by default every benchmark-dependent view uses the selection in force now, for any
as-of date (the choice is a lens on the portfolio, FR-018 "calculate benchmark-dependent analytics from the selected benchmark").
Using "the selection in force on that as-of date" for historical views is possible with `selected_on` and would be a one-line
change in the service; it is not the default because it makes two views of the same window disagree on the benchmark.

#### 17.5.2 Persistence, grants, errors

- `persistence/benchmark_selection_store.py`: `append_selection`, `append_reversal`, `append_correction`, `selection_rows(portfolio)`,
  all through the existing connection and transaction helpers and the CP1 `LedgerConcurrencyError`-style typed errors; trigger
  constraint names are load-bearing and mapped to typed errors (the `market_data_store` pattern).
- `domain/benchmark_selection.py`: the frozen `BenchmarkSelection` dataclass with a field-presence table like
  `FIELD_RULES`, and the pure `resolve_selection(rows, S)`. The CHECK constraints are hand-written; a **differential test** feeds
  every valid and invalid field combination from the presence table to the database and expects the domain and the database to
  agree (so the two cannot drift).
- **Migration 0015 hygiene:** unqualified names; every trigger function with `SET search_path = <schema>, pg_temp` and the inline
  schema-rename guard (the 0004, 0006 and 0011 block); `READ COMMITTED` required for appends; the migration checksum recorded;
  0001 to 0014 untouched.
- **Grants.** `finweb_app`: `SELECT, INSERT` on `benchmark_selection` and `USAGE` on its sequence, nothing else. `APP_GRANTS` and the
  privilege-enumeration test (`test_postgres_least_privilege`) are extended, so the grant spec and the check share one list; a test
  asserts the role has no `UPDATE`, `DELETE`, `TRUNCATE` or `CREATE` and cannot defeat the append-only rules with a TEMP shadow
  (the CP1B attacks are re-run against the new table). `NEVER_GRANT` is unchanged.

#### 17.5.3 How a result records the selection, and UAT-03

- The risk manifest (17.7.5) holds, for a benchmark-dependent group, `selection: {selection_id, selection_seq, record_type,
  benchmark_id, catalog_version, row_digest}` and the knowledge version `S` the resolver used. A portfolio with no selection, or
  a `CLEAR` in force, records `selection: NONE` and the relative metrics are `INSUFFICIENT_DATA` + `MISSING_BENCHMARK` with the
  detail `NO_BENCHMARK_SELECTED`.
- `reproduce_risk` takes the selection row **from the manifest** (by id, from the store or supplied), never "the current one", and
  reports `SELECTION_MISMATCH` if the supplied row differs and `SELECTION_SINCE_REVERSED` (informational) if a later reversal
  exists.
- **UAT-03 is met structurally and then proved:** (1) the benchmark-dependent group's manifest contains the selection, so
  changing the selection changes the question and therefore the manifest id and the result; (2) the benchmark-independent group
  does not contain it, so volatility, drawdown, Sharpe and Sortino keep **byte-identical manifests and results**; (3) because
  nothing is stored (17.8), no stale benchmark-dependent result can be read back from the engine; (4) for a consumer holding an
  earlier result, `risk_service.currency_of(result)` returns `CURRENT`, `SELECTION_SUPERSEDED`, `LEDGER_ADVANCED`, or
  `RELEASE_ADVANCED` by comparing the result's pinned `(S, ledger_version, release_id)` with the present ones. A UI or AI layer
  that caches must key on those four values; the plan states this as an interface rule for CP7 onward.
- Tests: select A, compute; select B, compute: the relative group differs and names B, the independent group is byte-identical;
  reverse B (now A in force): the group equals the first result exactly; `CLEAR`: relative metrics `MISSING_BENCHMARK`, independent
  unchanged; two portfolios do not affect each other; a pinned old `S` reproduces the old result after later changes; concurrent
  appends for one portfolio serialize (a second-connection lock test as CP4-11); the idempotent resubmission rule.

### 17.6 The methodology registry (CP4b)

#### 17.6.1 Shape

A `MethodologyEntry` per `(metric_id, version)`, frozen, validated at construction:

- **The PRD fields.** All fifteen PRD section 33 fields (`REQUIRED_FIELDS`: metric name, human definition, formula, annualization
  convention, data inputs, minimum observations, frequency, lookback, benchmark dependency, risk-free-rate dependency,
  missing-data handling, FX treatment, corporate-action treatment, known limitations, implementation version). PRD section 16.3's ten
  items (definition and formula, data requirements, minimum sample, window and frequency, annualization, benchmark, risk-free, FX,
  missing data, limitations) are a subset of these, so one entry satisfies both. `validate_entry` is reused as the schema gate: the
  entry's mapping form must pass it.
- **Engine-facing structured fields** (additive; not part of the fifteen): `convention_set_id` (`risk/1.0`), `ruling_refs`,
  `sufficiency` (`min_observations` by frequency, the short-window and gap policies as enums, the zero-capital eligibility flag),
  `benchmark_dependent: bool`, `risk_free_dependent: bool`, `frequencies_supported`, `default_window`, `states_table` (condition
  to the allowed `(state, reason, detail)`), `limitations` as an ordered list of fixed phrases. These are what make the registry
  the **single source of thresholds**: `risk.sufficiency` and the manifest partitioner read them; **no risk module contains a
  threshold literal**. A behavioural test mutates a registry entry's `min_observations` in a scratch registry and asserts the
  engine's state flips at exactly that count; an AST scan of `risk` flags integer literals compared with a count or length.
- `entry_key = "<metric_id>@<version>"`, `content_hash` over the canonical form. `ComputedMetric.method_id` is the entry key and
  `manifest.methodology` lists the keys used (until now empty; for CP3 metrics it stays empty, see 17.6.4).

#### 17.6.2 Consumers

The engine (thresholds, dependency partition), the evidence views and the HG3 pack (version, minimum-data rule, limitations,
formula text), and later the AI layer (P1: it reads `human_definition` and `known_limitations` from the registry and computed
values from `ComputedMetric`; it never composes a definition). The UI never invents a threshold (PRD 16.3). A function
`entry_for(metric_id, version)` is the only access; an unknown id or version raises, and `build_metric` for a risk id refuses
without an entry (the rule CP3 applied to `METRIC_IDS`, extended).

#### 17.6.3 The test that ties it to the `risk/1.0` text

Request to the Quant (P-15): `CP4_RISK_CONVENTIONS.md` carries a **Registry appendix**, one fenced machine-readable block per metric
(JSON; field names exactly as above), under a heading carrying the version. The engineer's test
`test_risk_registry_matches_methodology.py`:
1. parses the appendix and checks, **field for field and by canonical hash**, that the shipped entry equals the appendix entry
   (any difference fails; the entry is a transcription, never a paraphrase);
2. checks the entry's version equals the document's version header and every `ruling_refs` item exists as a heading in the document;
3. checks a metric appears in the appendix if and only if it has an entry and a row in the risk availability matrix, and that no
   registry id is unreachable from the engine;
4. pins the canonicalised appendix hash per version in the test (`{"risk/1.0": "<sha256>"}`): a text change under an unchanged
   version fails the test, which enforces the 2026-10-01 process rule (manifests cite ids, so text must not change under one id).
   Version bumps update the pin deliberately.
The test fails (it does not skip) if the methodology file is absent: a registry with no source text is not conformant.

#### 17.6.4 Relationship to the existing registries

- `performance.registry.METRIC_IDS` (24 ids) is an **emission whitelist**: `build_metric` refuses an unregistered id. It stays, and risk
  gets a sibling `risk.registry.RISK_METRIC_IDS`. A single read-only `metric_catalog` function unions them for the availability-matrix
  tooling. They answer "may this id be emitted?"; the methodology registry answers "what is this metric, by which rule, with what
  limits?". The two are tied: every `RISK_METRIC_IDS` member has a `MethodologyEntry`, and the matrix test fails otherwise.
- The **availability matrix** (`test_performance_availability_matrix.py`) is extended by a sibling `test_risk_availability_matrix.py`
  (same discipline: a row per id, a cell per condition, written from the Quant's fixtures, never from engine output). Its cells are
  also the `states_table` of the entry; a test asserts the two agree.
- **CP3's 24 metrics have no methodology entries** today (`manifest.methodology` is empty). PRD section 33 applies to every professional metric. **[PM]**
  Whether CP4 also transcribes `performance/1.x` into entries (a Quant appendix in `CP3_PERFORMANCE_CONVENTIONS.md`) or carries
  it as visible debt. Default in this plan: carry it as debt, with an explicit `NOT_YET_REGISTERED` allow-list in the registry test
  that can only shrink, so the gap is on the record and not silent.

#### 17.6.5 The AC-17 conflict **[PM], needs a decision before CP4b step 4**

`specs/FEATURE_PRD.md` AC-17 says the shipped registry contains **zero** metric entries (a non-empty registry "fails this
increment"), and `product_contract/methodology_registry.py` says it "must never ship a populated entry". Both were Increment 1
(PD-0004), before any metric existed. CP4's exit criterion needs populated entries, so the criterion cannot stand unamended.
Options: **(a)** a PD amends AC-17 and PD-0004's scope ("zero entries in Increment 1; from CP4, an entry exists only if it
transcribes a ratified methodology text and passes the tie test"); **(b)** leave `EMPTY_METHODOLOGY_REGISTRY` and its test untouched
(it still passes) and ship the populated registry in a different object. **(b) alone is not honest**, since it satisfies the test
and violates the intent; I recommend (a) with (b)'s mechanics (the constant remains as the Increment 1 artifact). Until decided,
the registry data structure and the tie test are built, but no entry is added under `src/`.

### 17.7 The risk computations (CP4c, CP4d)

#### 17.7.1 Module layout

```
src/risk/                          pure; same AST rules as performance (no clock, random, float, math, network, persistence)
  conventions.py                   RiskConventionSet: P-1..P-14 slots, placeholders, is_conformant, open_items, RISK_CONVENTION_SET_ID
  frequency.py                     Frequency, periods_per_year via the convention set (no literal in code)
  benchmark_leg.py                 benchmark period returns, currency translation, basis policy, price-of-date states
  risk_free_leg.py                 period risk-free accrual (exact, or certified Decimal-50)
  joint.py                         JointSeries: eligible-period intersection, per-leg effective dates, observation counts
  stats.py                         exact sums (pairwise), mean, variance, covariance, OLS; certified sqrt; ratio via one root
  single.py                        volatility, downside deviation, max drawdown, Sharpe, Sortino
  relative.py                      beta, alpha, R-squared, active return, tracking error, information ratio
  comparability.py                 PD-0014 disclosure (P-13)
  sufficiency.py                   observation counting, thresholds read from the registry entry, state mapping
  states.py                        the ONLY risk module that names a ReasonCode (cause -> (state, reason))
  registry.py                      RISK_METRIC_IDS; the MethodologyEntry data; entry_for
  manifest.py                      RiskManifest (finweb.risk_manifest/1), seal, reproduce_risk
  engine.py                        compute_risk(...): orchestration
src/risk_service/                  the I/O edge: loads events and the selection, reads the release, applies the CP3 gates, calls risk.engine
src/risk_tools/                    human and CI command line: cost measurement, the HG3 pack; never imported by product code
src/persistence/benchmark_selection_store.py     (17.5)
src/domain/benchmark_selection.py                (17.5)
```

**Import rules (AST tests in the style of `test_performance_boundaries.py`, new `test_risk_boundaries.py`).** `risk` may import
stdlib (with the `performance` bans), `domain.*`, `product_contract.*`, `performance.results`, `performance.numerics`,
`performance.series`, `performance.periods`, `performance.manifest`, `performance.states` (read use only), `performance.engine`
(for the portfolio leg only, through one function), and the analytics-facing `marketdata` modules `performance` may use. Not
`marketdata.adapters`, `ingest`, `files`, `store`, `profiles`, `verification`, `marketdata_tools`, `persistence`, `performance_service`,
`risk_service`, `risk_tools`. `performance` never imports `risk`, and nothing in `domain`, `marketdata`, `persistence` or
`product_contract` imports `risk`. No vendor word; no `AdjustedQuote`; no `ai*`, `advisory*`, `scenario*`, `execution*`, `order*`,
`broker*`. `portfolio_state = ACTUAL` on every metric (P8). `ENGINE_PINS`-style source hashes for `risk` (`RISK_ENGINE_ID`,
`RISK_ENGINE_PINS`) so a computation change cannot be silent.

**Why a new package, not more of `performance`.** The spine (a return series) is part of performance and goes in `performance`, so it
sits with its identities. The statistics have a different input (a series, not a ledger) and a different convention set
(`risk/1.0`), and keeping them out of the 5,000-line performance package keeps its pins stable. The dependency points one way.

#### 17.7.2 Exact intermediates, certified roots and regression

- Everything inside is `Fraction`. Presentation is one call to `performance.numerics.present`, with the risk rounding points of P-14.
- **Sums.** Mean, sum of squares, cross-products and downside sums are computed by pairwise (tree) summation of exact values
  (17.3.4). Variance and covariance use the raw-sum form `(n * Sxx - Sx^2) / (n * (n - 1))` (or the divisor of P-4), which is exact,
  so there is no cancellation problem and no centering error.
- **Square root, certified.** `numerics.certified_sqrt(x: Fraction, digits)` returns an exact result when `x` is a rational
  square (detected exactly, by integer square roots of numerator and denominator), otherwise a bracket `[lo, hi]` with
  `hi - lo <= 10**-digits` from an integer Newton method written in `numerics` (own implementation: `math` is banned in these
  packages; tests compare with `math.isqrt`). The value is the midpoint with `width = (hi - lo) / 2`, handed to `present(..., width)`,
  which already rounds decisively or flags a tie. A square root of a non-square rational is irrational and therefore **cannot
  be an exact tie**, so a bracket that straddles a rounding boundary is resolved by widening `digits` a bounded number of times
  and then flagged; the exact-tie case arises only for perfect squares, which are exact. Working precision defaults to the CP3
  value (`IRRATIONAL_WIDTH`, 50 digits) unless P-14 declares another.
- **One root per reported number.** Every ratio is arranged so only one square root is taken, of an exact rational. For example
  a Sharpe ratio `m / sigma` with `sigma = sqrt(v)` is `sign(m) * sqrt(m^2 / v)`; annualizing by `sqrt(ppy)` folds `ppy` into
  the radicand; the same holds for Sortino and the information ratio. Ratios of two rounded or irrational parts are **never**
  formed from presented values. (If P-3 or P-10 requires geometric annualization, `growth_root` and the Decimal-50 path of CP3 are
  reused, carrying `numeric_basis = DECIMAL_PREC50` and a width, exactly as `annualize` does.)
- **Regression is exact.** `beta = (n*Sxy - Sx*Sy) / (n*Sxx - Sx^2)`, `alpha_period = (Sy - beta*Sx) / n`, and `R^2 =
  (n*Sxy - Sx*Sy)^2 / ((n*Sxx - Sx^2) * (n*Syy - Sy^2))` are rational, so "certified regression" means exact, and the proof is by
  identity, not by tolerance: **RI-1** the centered and raw-sum forms agree exactly; **RI-2** the residuals sum to 0 and are
  orthogonal to the regressor, exactly; **RI-3** `R^2 = 1 - SSE/SST` exactly; **RI-4** `beta(y on x) * beta(x on y) = R^2`;
  **RI-5** scaling a series by a constant scales beta as expected; **RI-6** the window's beta equals the beta recomputed from the
  merged sums of two halves. All are exact and run in `verify_identities=True` mode; a failure is `CALCULATION_ERROR`. Every
  transcendental output (anything with a root or a power) carries a declared tolerance in the fixture and its width in the result.
- **Maximum drawdown** is exact: the cumulative wealth index is the exact product of `(1 + r_k)`, the running peak and the
  drawdown are exact ratios, and the convention (P-11) decides the base. Peak and trough dates are returned as details. A bit-length
  guard (`within_bounds`, `MAX_BITS`) protects the cumulative product; an overflow is `INSUFFICIENT_DATA` with
  `NOT_REPRESENTABLE`-style detail, not an exception (CP3-5 precedent).
- **Determinism hygiene** as in CP3: no clock, no `uuid4`, no iteration over a `set` or unordered `dict` that reaches output (every
  output tuple has a stated sort key), no global `decimal` context (a local context for every Decimal use).

#### 17.7.3 State propagation from the return series

`risk.sufficiency.assess(series, legs, entry)` produces, per metric, the observation set and the state:
1. **Dependencies first** (from the registry entry): a benchmark-dependent metric with no selection, an unknown id, a series not
   in `M`, or no readable benchmark is `INSUFFICIENT_DATA` + `MISSING_BENCHMARK` (detail names which); a risk-free-dependent
   metric with no series is `INSUFFICIENT_DATA` with `RISK_FREE_SERIES_MISSING` (no code, 17.2).
2. **Periods.** The eligible observation set is the periods the P-12 rule keeps; ineligible ones (insufficient, zero-capital,
   disclosed gaps) are listed, with their causes, in `lineage`/`details`. The observation count `n` is stated on every result.
3. **Sufficiency.** `n` below the entry's minimum for the frequency is `INSUFFICIENT_DATA` with the detail `TOO_FEW_OBSERVATIONS`
   (and the actual `n` and required `n` in lineage); the number is suppressed (P5), not softened.
4. **State.** Otherwise the worst state of the parts used (the CP3 aggregation, or P-12's stricter rule), the freshness vectors
   unioned across legs, and the series-level freshness summary carried. A statistic over a series that includes `LIMITED`
   periods is at most `LIMITED`, with `STALE_DATA` where it applies, and its stale share is stated, as `stale_weight` is in CP3.
5. **Degenerate inputs.** Zero variance gives volatility 0 (exact) and Sharpe, Sortino, beta's denominator and the information
   ratio `INSUFFICIENT_DATA` with details `ZERO_VOLATILITY`, `ZERO_DOWNSIDE_DEVIATION`, `ZERO_BENCHMARK_VARIANCE`,
   `ZERO_TRACKING_ERROR` (never infinity, never a guess). A cash-only portfolio therefore has an exact 0 volatility and an
   `INSUFFICIENT_DATA` Sharpe, subject to the Quant's ruling on whether volatility of an all-zero series is reported.
6. **Requested versus used window** (PRD 14): the result states the requested window and frequency and the ones actually used
   (clipped, gapped, or equal), the observation count, and, for a clipped window, the label that the history is shorter than asked.

#### 17.7.4 The PD-0014 comparability disclosure

A relative metric has two legs (portfolio and benchmark) whose effective timestamps can differ. Per boundary the engine already
has each leg's effective date: the portfolio leg's freshness vector (price dates used, in sessions) and the benchmark leg's
`date_used` and `missed_count`. `risk.comparability.assess(pairs)` returns `Comparability(level, max_gap_sessions, periods_affected,
share_affected, code)` using the thresholds and the session counting of P-13 (the sessions counted on the **benchmark's own
calendar** per the catalog; the portfolio leg's gap is its stalest holding's). A result is **never suppressed** for non-comparability
(PD-0014: stays computable). It carries the disclosure in a typed `RiskBasis.comparability` field and, if P-13 says so, a `LIMITED`
state with `STALE_DATA`-like semantics; the choice between disclosure-beside-`AVAILABLE` and `LIMITED` is the Quant's. Also in the
disclosure: a basis mismatch (price-only benchmark against a total-return portfolio), a currency treatment note, and whether
the benchmark is a proxy. P3 applies: a simplified UI string may drop precision, never this caveat.

#### 17.7.5 Manifests and `reproduce()`

`finweb.risk_manifest/1` **[J]** (CP3's `ComputationManifest` is untouched; its fields and canonical dict do not change, and a
test regenerates the HG2 synthetic pack and compares bytes). It embeds the portfolio-leg question (the existing
`ComputationManifest` for the series window, with its `manifest_id`), and adds:
`frequency`, `boundary_rule_id`, the boundary dates digest, `window_requested` and `window_used`, `risk_convention_set_id` and
its `placeholder` list and `conformant`, the registry entry keys and content hashes used, `data_set_refs` of kinds `BENCHMARK` and
`RISK_FREE` (consumed files, in both directions, as for quotes and FX), `benchmark_catalog_digest`, `risk_free_catalog_digest`,
the benchmark `selection` and `S` (17.5.3, relative group only), `numerics` (rounding rule id, sqrt digits), and `risk_engine_id`.
The `source_registry_digest` covers the new sources. **Dependency partition:** `compute_risk` emits up to three result groups, each
with its own manifest containing only what its metrics depend on (per the registry): the independent group (volatility, downside
deviation, maximum drawdown), the risk-free group (Sharpe, Sortino), and the benchmark group (beta, alpha, R-squared, active return,
tracking error, information ratio; it contains the selection and the risk-free reference where alpha uses it). A metric belongs to
exactly one group; grouping is a pure function of the entries.

`reproduce_risk(manifest, inputs, expected_digest)` re-runs the whole question and returns a typed status: the CP3 statuses plus
`SELECTION_MISMATCH`, `BENCHMARK_FILE_NOT_CITED`, `BENCHMARK_FILE_NOT_READ`, `RISK_FREE_FILE_NOT_CITED`,
`RISK_FREE_FILE_NOT_READ`, `REGISTRY_ENTRY_MISMATCH`, `CATALOG_MISMATCH`. No expected digest gives `RESULT_NOT_COMPARED`, never
`REPRODUCED` (CP3-6). **Both Current-mode and historical-as-of modes** carry through: in Current mode the benchmark and risk-free
files are read from `M_t`.

#### 17.7.6 Entry points

```
risk.engine.compute_risk(events, ledger_version, request: RiskRequest, reporting_currency, port, resolver, market_conventions,
                         performance_conventions, risk_conventions, *, suppressions, selection: Optional[SelectionRecord],
                         selection_version: int, portfolio_id=None, detection=..., verify_identities=False)
        -> RiskResult  (the groups; each a ComputationResult)
risk_service.compute_risk_for_portfolio(conn, portfolio_id, request, ...)   # all the CP3 gates; reads the selection; refuses synthetic M for a user portfolio
risk_service.currency_of(result)  # CURRENT | SELECTION_SUPERSEDED | LEDGER_ADVANCED | RELEASE_ADVANCED
```
`RiskRequest` carries the window spec, the frequency (default weekly), the reporting currency (default the portfolio's), the
valuation mode (historical as-of `E`, or Current through the CP3 `D_c(t)` machinery and `M_t`), and the metric subset. A Current-mode
refusal records the instant, `M`, `M_t` and `D_c` as CP4-2 and CP4-7 require. HG2 conditions 3 and 4 are enforced by the same
gates as CP3: a CN or HK holding is valued only with registered calendars and an admitted price source, otherwise the portfolio leg
is `INSUFFICIENT_DATA` and so is every metric derived from it.

#### 17.7.7 Provisional ids and detail names **[J]**

Metric ids (renaming is cheap now and a version bump later): `risk_volatility`, `risk_downside_deviation`, `risk_max_drawdown`,
`risk_sharpe`, `risk_sortino`, `risk_beta`, `risk_alpha`, `risk_r_squared`, `rel_active_return`, `rel_tracking_error`,
`rel_information_ratio`, and `benchmark_return` (the benchmark's own return over the window, for the comparison view).
Detail names: `TOO_FEW_OBSERVATIONS`, `ZERO_VOLATILITY`, `ZERO_DOWNSIDE_DEVIATION`, `ZERO_BENCHMARK_VARIANCE`, `ZERO_TRACKING_ERROR`,
`NO_BENCHMARK_SELECTED`, `BENCHMARK_ID_UNKNOWN`, `BENCHMARK_BASIS_REFUSED`, `BENCHMARK_CURRENCY_UNTRANSLATABLE`,
`RISK_FREE_SERIES_MISSING`, `WINDOW_SHORTER_THAN_REQUESTED`, `SCOPE_NOT_SUPPORTED`, `PERIOD_GAP`, `EMPTY_PERIODS_EXCLUDED`. The Quant
fixes the final vocabulary (P-17); detail names are part of the method (they appear in fixtures).

### 17.8 Storage: results are not persisted in CP4

**Answer: no.** CP3's rule holds. Reasons: a stored result is a second source of truth that can be stale; UAT-03 is satisfied
structurally if nothing is read back; reproducibility already comes from the manifest, the ledger at `L`, the release `M` and the
selection at `S`. What CP4 may add, only if the measured cost (17.3.4) requires it:

- A **bounded in-process memo** keyed by the full question digest (the risk manifest id, which already contains every input). A hit is
  by construction identical to a recompute; it is not part of the manifest, never persisted, never consulted without the complete key, and
  has a size bound. A test runs the whole exit matrix with the memo on and off and compares canonical bytes.
- If even that is not enough, a **rebuildable projection** like the market-data store (immutable rows keyed by manifest id, never
  authoritative, "current" never stored, only derived) would be a new design and goes back to the main session. **[PM]** Not planned.

### 17.9 Testing, the CP4 exit, and the HG3 evidence

**Fixtures.** The Quant's `cp4_golden` parts (hand-derived, calculator importing nothing from `src/`) are wired by a
`cp4_golden_kit.py` in `tests/product/`, in the style of the CP3 kits: pure path and PostgreSQL path (as `finweb_app`), assertion by
assertion. Mismatches are reported, never adjusted. Fixture `convention_sets` are minimum versions (performance/1.8 Ruling 11.6).
Transcendental outputs are compared within the fixture's declared tolerance; everything exact is compared exactly.

**Unit and property tests (engineer, independent of the fixtures):** the stats kernel against an independent oracle (Python's
`statistics` and `fractions` in the test only; certified roots against `math.isqrt`), property tests on random series for RI-1..RI-6
and I-10, permutation of input order (output sorted), scaling and shift invariances, and mutation checks on scratch copies
(`cp -R` to `$TMPDIR`, then edit there), recorded per item as in CP3.

**CP4e exit test (`test_cp4_exit.py`)**:
1. every risk metric x the full HG3 edge-case matrix below, on both paths, with the expected `(state, reason, detail)` taken from the
   Quant's fixtures, and an assertion that an `INSUFFICIENT_DATA` cell carries no number;
2. the golden fixtures (all parts) match, and determinism: the same inputs and as-of date give identical bytes across 5 hash seeds
   and with the memo on and off; `reproduce` is `REPRODUCED` for every manifest;
3. identities I-10, I-11 and RI-1..RI-6 on a large set of windows;
4. UAT-03 end to end (17.5.3) and the dependency partition: only the dependent group's manifest changes with the selection;
5. CP3 non-regression: the CP3 exit test, the HG2 synthetic pack and every CP3 manifest id are byte-identical;
6. migration checks: 0015 and 0016 checksums, existing release `projection_digest` unchanged, grants exact, TEMP-shadow attacks
   refused.

**HG3 edge-case matrix (PRD section 38.4).** Each row is a named test per metric; the expected cell comes from the fixtures **[Q]**.

| Case | Constructed as | Expected shape (Quant confirms the cells) |
|---|---|---|
| Insufficient history | window longer than inception, and fewer than the minimum observations | `INSUFFICIENT_DATA`, `TOO_FEW_OBSERVATIONS` or the CP3 window refusal, or a labelled clipped window, per P-12 |
| Missing FX | a holding in a currency with no fixing in a period, and a benchmark needing translation without a fixing | portfolio leg `MISSING_FX_HISTORY`; benchmark `BENCHMARK_CURRENCY_UNTRANSLATABLE` |
| Missing cost basis | an opening position without a cost basis | risk metrics are return-based and do not use cost basis: expected unchanged and `AVAILABLE`; the test asserts the **independence**, which is what the HG3 item proves **[Q]** |
| Cash-only | a portfolio with only cash | volatility exact 0 or suppressed per the Quant; Sharpe and Sortino `INSUFFICIENT_DATA` |
| Single security | one listing | all computable if observations suffice; no concentration claim made here (CP5) |
| Multi-currency | US, CN and HK listings with ECB FX | `AVAILABLE`/`LIMITED` with freshness from the three calendars; the series spans non-synchronous closes |
| Recently listed security | a holding first priced inside the window | the periods before listing: holding absent (not held) or `MISSING_PRICE_HISTORY`, then gap policy; observation count stated |
| Unavailable benchmark | no selection; selection with no series in `M`; a series not covering the window; stale benchmark; two conflicting sources; basis refused | `MISSING_BENCHMARK` with the right detail, or `SOURCE_CONFLICT`; independent metrics unaffected |
| Plus (engineer-added) | no risk-free series; zero variance; benchmark leg stale vs portfolio leg (PD-0014); a Current-mode request; account scope request | per the entries |

**Evidence pack toward HG3.** `risk_tools` extends the HG2 pack tool (`performance_tools`, unchanged) with a risk section that
produces, per metric and per condition, the 12 items of PRD section 38.4 as one `ProofRow` (a generic structure so CP5's metrics
append): **result** (from the engine), **method version** (the registry entry key and content hash), **benchmark** (the selection
row id and `benchmark_id`, basis, catalog version, or `NONE`), **lookback** (requested and used), **frequency**, **currency**,
**observation count**, **minimum-data rule** (from the entry), **fixture** (id and assertion id), **expected value** (read from the
Quant's fixture file, never recomputed), **tolerance** (from the fixture), **limitations** (from the entry), plus match and
state. Two packs as for HG2: a synthetic pack (committed, byte-reproducible, every manifest reproduced) and a real-slice pack
(git-ignored) that says `UNKNOWN` rather than fabricating where a benchmark, a risk-free series or three years of history is
absent. Tests: every number in the pack traces to a `ComputedMetric` or a fixture assertion; the pack builder imports no stats
module; a mismatch is shown, not hidden; the pack is byte-identical across hash seeds.

### 17.10 Increments

Each increment ends with the real test run, a main-session re-run, and mutation evidence on a scratch copy.

| Step | Content | Needs |
|---|---|---|
| **CP4b-1** (proposed first) | `performance/series.py` (the spine) with explicit-boundary input and an injected `BoundaryRule`; `WindowUsed` additive fields; identities I-10 and I-11; `compute_return_series`; hand-checkable tests (a flow-free case, a mid-period deposit, a zero-capital head, a holiday boundary, INSUFFICIENT periods); the measured cost tool and the gate (17.3.4); CP3 byte-identity test | CP3 only; no ruling |
| CP4b-2 | `RISK_FREE` kind: contract, `DataKind`, adapters (synthetic benchmark and risk-free), migration 0016, store, port reads for benchmark and risk-free (in memory and PostgreSQL), `DerivedReleaseView` for the new kinds, source-registry coverage, the terms-gate tests, precision profiles for synthetic sources | profile text from the Quant (can start with `DECLARED` synthetic profiles) |
| CP4b-3 | `benchmark_selection` (domain, migration 0015, store, differential test, grants, TEMP-shadow tests), `risk_service` selection read, `currency_of` | PM answers to Q3, Q4 (17.12) |
| CP4b-4 | `MethodologyEntry` structure, `risk.registry` skeleton, the tie test, the AC-17 resolution | `risk/1.0` with the registry appendix; PM decision on AC-17 |
| CP4c-1 | `risk.stats`: exact sums, certified sqrt, regression, identities RI-1..RI-6, property tests, cost gate result applied | P-4 only (divisor), none for the kernel |
| CP4c-2 | single-series metrics and `RiskConventionSet`, wired to `cp4_golden` part 1; sufficiency; maximum drawdown | `risk/1.0` (P-1 to P-8, P-11, P-12, P-14), fixture part 1 |
| CP4c-3 | `RiskManifest`, `reproduce_risk`, partitioned groups, `risk_service` for single-series, ENGINE pins; **midpoint independent review** | |
| CP4d-1 | benchmark and risk-free legs, joint series, currency translation, basis policy | P-9, P-16 |
| CP4d-2 | beta, alpha, R-squared, active return, tracking error, information ratio; fixture part 2 | P-8, P-10 |
| CP4d-3 | comparability disclosure, UAT-03 end-to-end, recompute-on-change and dependency-partition tests | P-13 |
| CP4e | exit test, matrix, evidence pack, all mutations; **final independent review**, then PM acceptance | fixtures complete |

**Why CP4b-1 first.** It depends on nothing the Quant is still deciding (the boundary rule is injected and the tests pass explicit
boundaries), it proves the whole return-definition claim by an exact identity against CP3, it measures the one risk that can change
the design (exact-rational cost), and it is the common ancestor of every later step.

### 17.11 Risks

1. **Exact-rational cost** (17.3.4). Could change the numeric design (enclosures) or require a CP1 additive change. Measured at the end of CP4b-1.
2. **AC-17 and the registry.** The exit criterion is unreachable under AC-17 as written (17.6.5).
3. **Cross-market weekly alignment** (P-1). Also the Quant's biggest revision-round risk. The injected rule contains it, but the spine's
   cost and the zero-capital and holiday behaviours depend on it.
4. **Port widening.** New `MarketDataPort` methods touch every implementation and test double, the Current-mode view, the release
   projection digest and the `ANALYTICS_PINS`. Handled as one reviewed step (CP4b-2) with a digest-unchanged proof.
5. **Manifest byte-identity.** Adding fields to `ComputationManifest` or `ComputedMetric` would change every CP3 id. The additive-when-present
   rule and the byte-identity test guard it; a new risk manifest avoids touching the old one.
6. **Selection semantics** (two axes or one; current or as-of; corrections) are partly product decisions. The minimal design is a valid
   fallback.
7. **Comparability under PD-0014** is a Quant measure; if it requires data the engine does not hold (a portfolio-leg effective date per
   boundary), the series builder must expose it. The plan keeps each leg's effective dates from the start so this does not need a rebuild.
8. **Real data is absent** (D1): HG3 can show method correctness and safe degradation, but not a real 3-year benchmarked analysis. Raise with the
   owner before HG3 (CP4_PLAN section 8). CN and HK real prices remain HG2 condition 3, and calendars condition 4.
9. **Registry transcription drift.** Mitigated by the tie test; costs one appendix per methodology version.
10. **Treasury format unknown.** The real adapter waits for a real file; nothing in CP4's exit depends on it.
11. **Decimal and Fraction edge cases** (huge bit lengths, tiny variances, `MAX_BITS`): each is an explicit state, never an exception, with
    tests for the extreme cases CP3's reviews found (CP3-5, CP3-16).

### 17.12 Open questions, decisions made, and what is needed

**For the main session [PM]:**
- **Q1.** AC-17 and PD-0004: amend (recommended) so a populated registry is allowed from CP4 (17.6.5). Blocks CP4b-4's content, not its structure.
- **Q2.** A second migration (0016) for the risk-free kind, besides PD-0039's 0015 (17.4.2). Alternative: carry the rate in a widened
  benchmark table (not recommended).
- **Q3.** Selection semantics: full (dated, ordered by `(selected_on, seq)`, with CP1-style corrections) or minimal (seq only); and
  whether a historical as-of view uses the current selection (default) or the one in force then (17.5.1).
- **Q4.** Where the catalogs live (`data/marketdata/BENCHMARKS.json`, `RISK_FREE.json`), who writes their content, and who decides which
  index is "recommended" for which portfolio (FR-017); the engine only reads the catalog.
- **Q5.** The cost budget and the permission to add `domain.replay.reconstruct_series` (an additive CP1 change) if the measurement needs it.
- **Q6.** Whether CP3's 24 metrics get registry entries in CP4 (a Quant appendix to `performance/1.x`) or are carried as debt with the allow-list.
- **Q7.** Scope of risk: portfolio only (planned) or account scope as well (CP3 supports it).
- **Q8.** A new reason code for a missing risk-free series, if the Quant asks (CP4_PLAN D4). Planned without one.
- **Q9.** `risk_service` as a separate package (planned) versus extending `performance_service`.

**Decisions made where the contracts did not cover (engineer choices for review):** (1) the spine lives in `performance`, the statistics in a
new `risk`; (2) a separate `RISK_FREE` kind and a typed synthetic adapter per new kind; (3) a separate `finweb.risk_manifest/1`, partitioned by
dependency, with CP3 manifests untouched; (4) no thresholds in code: the registry entry is the single source; (5) one square root per reported number,
with ratios folded under the root; (6) identities I-10, I-11 and RI-1..RI-6 as runtime checks; (7) a zero-capital period is flagged and never silently an
observation; (8) the registry is tied to the Quant's text by a transcription test and a hash pin; (9) no result storage, with an output-neutral memo only if
measured need; (10) provisional metric ids and detail names (17.7.7).

**What I need from the owner [H]:**
1. A real Treasury daily bill-rate file for one or more full years, registered by the owner (the human-only `register-file`), when the real risk-free
   adapter is wanted (not needed for CP4's exit).
2. A `SOURCES.json` entry for the Treasury source with the owner's attested `terms_check` (the engineer will not write the verdict).
3. A decision on real benchmark data before HG3 (PD-0039 D1): ETF proxies or a paid personal-use source, and its terms attestation.
4. Unchanged and still owed: HG2 condition 3 (a real CN or HK price source, or an explicit decision without one) and condition 4 (register `HKEX_SESSIONS`
   and `CN_A_SESSIONS`).

**What I need from the Quant:** `risk/1.0` with the slots P-1 to P-20; a **Registry appendix** in machine-readable form (P-15); the precision-profile
entries for the synthetic sources now and for the Treasury file later; the final detail vocabulary (P-17); `cp4_golden` parts with a stated tolerance
per assertion and convention minimums; and the answer to the open expectations in the matrix above (missing cost basis independence, cash-only volatility).

**Suggested next step:** dispatch **CP4b-1** (the spine, the identities, the byte-identity test and the cost measurement). It needs no ruling and ends with a
measured number that settles Q5 and the numeric design before the Quant's text arrives.

### 17.13 CP4b-1 as built: the return-series spine, the cost gate and the byte-identity proof (engineer; 2026-10-02; not yet reviewed)

**PM rulings applied (2026-10-02).** Q1 AC-17 is superseded for CP4 onward (when `risk/1.0` lands the AC-17 test asserts schema validity and equality with the Quant's appendix, not emptiness; no entry is added
until then); Q2 migration 0016 approved; Q3 the full selection design, a computation using the selection in force at the request's knowledge version (the Quant's ruling wins if different); Q4 the catalogs are the main
session's, and the "recommend" half of FR-017 is out of CP4; Q5 targets about 5 s for a 3-year weekly series over 20 listings and about 30 s for daily, mitigation ladder approved, enclosures need the Quant;
Q6 CP3 metrics carried as visible debt, entries owed before HG3; Q9 `risk_service` is a separate package. None of these changes CP4b-1's code; they bind CP4b-2 onward.

**Files.**
- `src/performance/series.py` (new, pure, pinned): `Frequency`; `BoundaryRule` (Protocol) and `ExplicitBoundaries` (dates the CALLER chose; not a convention; no default rule exists anywhere); `ShortWindowPolicy`
  (`REFUSE`, `CLIP_TO_INCEPTION`, no default); `resolve_series_window`; `PeriodReturn`, `SeriesAssessment`, `ReturnSeries` (the boundary valuations are the primitive); `build_series`; identities `link_identity` (I-10) and
  `coverage_identity` (I-11); `SeriesResult`, `SeriesRefusal`; `BoundaryRuleError`, `SeriesIdentityError`.
- `src/performance/engine.py`: `compute_return_series(...)` (one new entry; no existing function changed) and `series_digest_of`.
- `src/performance/results.py`: `WindowUsed` gains `requested_months` and `requested_start`, serialised only when set (so no CP3 window changes).
- `src/performance/manifest.py`: `ENGINE_ID` `performance/cp4-0.14`; `ENGINE_PINS` (adds `series`; `engine`, `manifest`, `results` re-hashed), `ENGINE_PIN_HISTORY` and `PUBLIC` updated in `test_performance_boundaries.py`.
- `src/risk_tools/__init__.py`, `src/risk_tools/cost.py` (new, a tool: it reads a clock, which is its purpose; never imported by product code, a test enforces it).
- Tests: `tests/product/test_performance_series.py` (28), `tests/product/test_performance_cp3_byte_identity.py` (4).

**Design as built, and where it differs from 17.3.** (1) Each period is `twr_segments` over its own slice of the window's flows (sliced by `bisect`, so the flows are valued once for the window and `group_flows` is not
repeated over the whole list per period). (2) The series manifest is the CP3 `ComputationManifest` of the window question with `series.frequency`, `series.boundary_rule`, `series.short_window_policy` and
`series.boundaries_digest` added to `numerics` (so all four are in `manifest_id`) and `identities_run` set; no manifest field was added, which is why the CP3 manifest key set is unchanged. The dedicated
`finweb.risk_manifest/1` of 17.7.5 is still CP4c-3. (3) A failed I-10 or I-11 RAISES `SeriesIdentityError` (an engine fault, never a number); a series has no metric to turn into `CALCULATION_ERROR`. (4) I-10 is checked
per maximal run of consecutive exact periods, so a series with an insufficient period still has its other runs checked, and the insufficient period is not hidden by the check. (5) A window refused under `REFUSE`
returns `series = None` with the CP3 cause and detail, a manifest carrying the declared window and the frequency, and a digest of the refusal (reproducible like a series). (6) `merged_from` and gap bridging were NOT
built (until P-12 is ruled): the boundary valuations are kept so they can be added without a valuation being repeated. (7) A boundary that is a flow day puts that flow in the period that ENDS there (the CP3
half-open window rule), tested by hand.

**What the tests prove (every expected value hand-derived in the test file).** A flow-free series is the ratio of end values per period and the linked product equals the window TWR (26/25 x 55/52 = 11/10); a daily
series is `close(D)/close(D-1) - 1` and links to 104/100; a deposit inside a period is neutralised (period 2 is 17/403, the whole window 168/155, 13/155 linked, and the same window as ONE period gives the same 13/155); a
boundary on a flow day; a missed session gives AVAILABLE + STALE_DATA and the series assessment counts it; an insufficient period has no number while the others do; a zero-capital period is a real 0 that is FLAGGED
(`ZERO_CAPITAL_RUN`), not counted silently; the window policies (refuse as CP3, clip with the requested window kept, a trailing-months request kept, a clip that leaves no positive window); the rule contract (five
violations raise); the rule id, frequency, policy and boundaries are part of the manifest id; I-10 and I-11 both fail on forged inputs and pass on real ones; only the required dates are valued (3 boundary reads for a
flow-free weekly series, 5 with one deposit); per-period flow-day counts; determinism (same bytes, different boundaries differ); and the cost tool's output-neutral mitigation.

**CP3 byte-identity (`test_performance_cp3_byte_identity`).** `ENGINE_ID` is part of every manifest, so manifest ids and result digests change with the bump BY DESIGN. The test shows nothing else changed: (1) the canonical
results of the 17 computations of the HG2 synthetic demonstration (every metric, state, reason, exact value, cause, freshness, lineage and manifest, with `engine_id` and the manifest ids masked) hash to the value recorded
BEFORE the change (`e059ec07...`, recorded from the tree before any CP4b-1 edit); (2) all 228 `exact` values of the committed gate record `reviews/gates/HG2_EVIDENCE/synthetic/*.json` equal the regenerated pack's (the
committed pack is NOT byte-identical to a regenerated one: part A's trailing-zero presentation and `conformant` already differ, 16.24, so exact values are what is compared); (3) the manifest, metric and window key sets
are the CP3 ones. A forged-result check shows the hash test can fail.

**Measured cost (the CP4b gate; Python 3.12.14 on the development machine, one process, synthetic data, `python -m risk_tools.cost`).** World: half US (USD) and half HK (HKD) listings, three accounts (USD, HKD, EUR cash),
FX from the USD and HKD fixings (HKD through the EUR cross), reporting USD, 40 external-flow days, window TRAILING_MONTHS 36 (2022-06-30 to 2025-06-30), every period AVAILABLE. Times are a cold run (every valuation built
once); `reconstruct` is timed separately over the same dates.

| Case | Frequency | Periods | Valuation dates read | `compute_return_series` | `reconstruct` alone | Exact sums, naive | Pairwise |
|---|---|---|---|---|---|---|---|
| 20 listings, 1,500 events | weekly | 158 | not printed | 2.2 s | 1.1 s | 3 ms | 2 ms |
| 20 listings, 1,500 events | daily | 782 | not printed | 7.8 s | 5.4 s | 57 ms | 15 ms |
| 30 listings, 2,000 events | weekly | 158 | 223 | 2.9 s | 1.5 s | 3 ms | 2 ms |
| 30 listings, 2,000 events | daily | 782 | 790 | 10.3 s | 7.1 s | 59 ms | 15 ms |

With the identities on (I-10, I-11) the times are unchanged within noise (2.9 s and 10.3 s at 30 listings). Bit lengths of the exact results at 30 listings: a weekly period return up to 165 bits, the sum 9,189 bits, the
sum of squares 18,375 bits, the variance numerator 18,377 bits; daily 66, 34,113, 68,243 and 68,231 bits. The pairwise sum equals the naive sum exactly in every case (checked). **Conclusions.** (a) Both working targets are
met with no mitigation (weekly 2.2 s at 20 listings against 5 s; daily 10.3 s at 30 listings against 30 s). (b) The exact-rational growth feared in 17.3.4 is not the bottleneck here: the exact sums over 782 daily returns take
under 0.1 s, because the denominators share structure (decimal prices and quantities, a few FX crosses). (c) The cost is the valuation: `reconstruct` is about half of the weekly and about 69 percent of the daily time, so
the additive CP1 `reconstruct_series` (ladder step 3) is the one mitigation that would matter. It is NOT built: it is within budget without it, and it is an additive CP1 change to propose only if a larger world or the real
service path (PostgreSQL reads) moves the numbers. (d) **Caveat:** synthetic prices have two decimals and the FX crosses are few; a portfolio with many currencies, more crosses or prices with many decimals would have larger
denominators, and a PostgreSQL-backed run adds I/O (not measured). The tool is parameterised (`--listings`, `--events`, `--flow-days`) so this can be re-run; the numbers are printed, not asserted. For CP4b-1, then: no
result storage, no `reconstruct_series`, no enclosures.

**Mutation evidence** (a scratch copy under `$TMPDIR`, never the repository; a shell harness applies one `sed` expression per mutant and runs the two new test modules). 25 mutants of `series.py`, `engine.py` and
`results.py`: boundary check not strict; endpoint check removed; flow slice left edge and right edge; `D - 1` not required; link product not `1 + r`; stale count removed; zero-capital flag removed; clip at the requested
start; coverage identity always PASS; all flows given to every period; flow-day count zeroed; link identity never FAIL; policy ignored; requested window dropped; insufficient count zeroed; frequency not set on the window;
frequency, rule id and boundaries digest removed from the manifest; identity failure not raised; `identities_run` emptied; `WindowUsed` always or never serialising the requested fields; the refusal digest emptied.
**First run: 21 killed, 4 survived** (slice left edge, all flows per period, `identities_run`, refusal-digest content). The first two are equal in value under `twr_segments`' own date filter and differ only in the flow-day
count and the required dates; the other two were untested content. Tests were added for each (per-period flow-day counts with two flows in two periods, the manifest's `identities_run`, the refusal digest's exact content).
**Second run: 25 of 25 killed.**

**Decisions the contracts did not cover.** (1) `compute_return_series` lives in `engine.py` (the public entry), the pure parts in `series.py`; `series` joined the public modules. (2) The boundary valuation is the primitive,
and the series stores each boundary's total as a `Valued`. (3) The refusal digest takes the declared window before the frequency is set (the frequency is in the manifest). (4) The cost tool lives in a new `risk_tools`
package, loading the test kits at run time as `performance_tools.synthetic` does; it is never imported by product code. (5) The byte-identity baseline is masked for `engine_id` and manifest ids because they must change
with `ENGINE_ID`; re-record the hash only in a commit that changes a CP3 result on purpose.

**Open.** (a) A real boundary rule needs `risk/1.0` P-1; until then every caller supplies explicit boundaries. (b) The series does not yet apply P-12 (gap bridging, zero-capital eligibility); it only flags. (c) No PostgreSQL
service path for the series yet (`risk_service` is CP4b-3/CP4c-3); the series was exercised through `InMemoryMarketData` only, and the PostgreSQL time was not measured. (d) The cost world is not a substitute for the
Quant's fixtures. **Next:** CP4b-2 (the `RISK_FREE` kind, migration 0016, port reads and `DerivedReleaseView`, the synthetic adapters) and CP4b-3 (migration 0015, the selection store), in parallel with the Quant's `risk/1.0`.

### 17.14 CP4b-3 as built: benchmark selection storage, migration 0015 (engineer; 2026-10-02; not yet reviewed)

**Rulings applied.** PD-0039 D5; PM Q3 (the full design: ordered by `(selected_on, seq)`, CP1-style corrections; a computation uses the selection in force at the REQUEST'S knowledge version, the current one, not the
one in force at the as-of date; the Quant's ruling wins if it differs). The benchmark id names a catalog entry, but no catalog exists (the main session creates `BENCHMARKS.json` when needed), so only the FORMAT is
validated; the catalog check is PENDING and `catalog_version` stays NULL until it exists.

**Files.**
- `src/persistence/migrations/0015_benchmark_selection.sql` (new) and its line in `CHECKSUMS` (0001 to 0014 untouched).
- `src/domain/benchmark_selection.py` (new, pure): `RecordType` (`SELECT`, `CLEAR`, `REVERSAL`), `Origin`, `BenchmarkSelection` (validated at construction), `FIELD_RULES`, `validate_correction_pair`,
  `resolve_selection`, `SelectionInForce`, `SelectionPin`, `pin_of`.
- `src/persistence/benchmark_selection_store.py` (new): `append_selection`, `append_correction`, `get_selection`, `current_selection_version`, `load_selections`, `require_committed_boundary`,
  `selection_in_force`, `selection_pin`, and the typed errors.
- Tests: `test_domain_benchmark_selection.py` (27, pure), `test_postgres_benchmark_selection.py` (6 pure and 37 opt-in database tests); `test_postgres_least_privilege.py` (`APP_GRANTS` and
  `EXPECTED_TABLE_PRIVILEGES` extended; the old-schema control skips the new grants), and the migration counts 14 to 15 in `test_persistence_ledger.py`, `test_postgres_ledger_integration.py` and the
  least-privilege test.

**The table.** One append-only table, `benchmark_selection`, shaped like `ledger_event`:
- Columns: `selection_seq` (primary key, drawn by the trigger, no default), `selection_id` (client-supplied; the idempotency key), `portfolio_id`, `record_type`, `benchmark_id`, `catalog_version`, `origin`,
  `selected_on`, `reverses_selection_id`, `corrects_selection_id`, `recorded_at` (audit only), `append_xid` (trigger-set).
- **Records.** SELECT (benchmark id and origin required), CLEAR (the user removes the benchmark: no id, nothing guessed), REVERSAL (withdraws a SELECT or CLEAR). A replacement carries `corrects_selection_id`.
- **Presence rules** per record type are three CHECKs, mirrored by `FIELD_RULES`.
- **Bounds.** `benchmark_id` and `catalog_version` are short ASCII identifiers by pattern (at most 64 characters, starting with a letter or digit; PostgreSQL's `$` refuses a trailing newline); `selected_on` lies
  between 0001-01-01 and 9999-12-31 (`infinity` and years beyond Python's range are refused, so every stored row can be read back). There is no numeric column.
- **Foreign keys.** A reversal and a replacement must name a row of the SAME portfolio (composite foreign keys on `(selection_id, portfolio_id)`); a row is reversed at most once and corrected at most once
  (partial unique indexes).

**The trigger (the 0003, 0008 and 0011 discipline).** One `BEFORE INSERT` function whose order is load-bearing: the schema-rename guard; READ COMMITTED required; stamp `recorded_at` and `append_xid`; the
per-portfolio advisory lock (the key includes the schema name); and only THEN `selection_seq := nextval(...)`, so within a portfolio the sequence order is commit order and a pinned version is stable. Then, under
the lock: an idempotent resubmission returns early (no new-row rule applies to a row that will not be written; tested after the state moved on, as CP1B-2); a REVERSAL cannot be reversed; a replacement needs a reversed
target AND the reversal must be this transaction's (exact `xid8` comparison). (AS FIRST WRITTEN a plain SELECT or CLEAR could not be dated before the latest live one,
`benchmark_selection_selected_on_monotonic`; that rule was REMOVED under `risk/1.1` Ruling 5.6, see the correction note at the end of this section.) A correction row carries its own `selected_on`, as a corrected ledger event keeps its own `event_date`. Every function has `SET search_path = <schema>, pg_temp` and starts with the inline rename guard; a second
trigger refuses UPDATE, DELETE and TRUNCATE for every role.

**Resolution (in `domain`, pure).** The selection in force at knowledge version `S` is, among the rows with `selection_seq <= S` that are SELECT or CLEAR and not reversed by a REVERSAL with `selection_seq <= S`, the one with
the greatest `selection_seq` ONLY (`risk/1.1` Ruling 5.6; first written as `(selected_on, selection_seq)`, superseded); none is `NONE`; a CLEAR in force is `CLEARED`. `selected_on` is data (shown, pinned), never an ordering key.
Consequence, tested: the latest record wins whatever its date, correcting the LATEST changes the current choice, and a replacement (a new, higher sequence) of an older choice becomes the latest. The version is
the portfolio's greatest committed `selection_seq`; a version above it is refused (it could not be reproduced), and a version INSIDE an atomic append (between a reversal and its replacement) is refused by the
C1C-2 rule on `append_xid` (adjacent rows below and above the version share an xid exactly when it cuts one transaction).

**The pin (the UAT-03 foundation).** `SelectionPin` is the data a benchmark-dependent manifest will record (the risk manifest is CP4c): portfolio, version, state, and the row in force (id, sequence, record type,
benchmark id, catalog version, origin, date and a digest of the whole row), with its own digest. Tested in memory and through PostgreSQL: every change of the selection (a select, a second select, a reversal back to
the first, a clear) gives a different pin; reversing back restores the SAME ROW (equal `row_digest`) but not the version (a different pin, so a different question); a pinned old version reproduces its own
pin after everything that followed; two portfolios do not affect each other; a NONE pin names its version. The digest uses `hashlib` and sorted-key JSON inside `domain` (domain must not import `marketdata`).

**Grants and attacks.** `finweb_app` holds exactly `SELECT, INSERT` on the table and `USAGE` on its sequence (`APP_GRANTS`, and the privilege-enumeration test compares the whole schema, so any extra privilege fails).
Tested as the role: UPDATE, DELETE and TRUNCATE are refused by privilege (42501) and, for the owner, by the trigger; DISABLE TRIGGER, DROP TRIGGER, DROP CONSTRAINT, DROP TABLE, ADD COLUMN and CREATE OR REPLACE
FUNCTION are denied; the sequence grant is load-bearing. TEMP-shadow attacks (the CP1B-1 probes) against the new table: a shadow `benchmark_selection` and sequence cannot hide the latest selection from the ordering
rule, cannot reverse a reversal or replace without its reversal, the sequence is the real one, and the lock is still taken. **Control:** in a scratch schema whose functions lost their pin, a reversal of a hidden
reversal is ACCEPTED (so the attack tests are sensitive). A renamed schema fails closed (`benchmark_selection_search_path_pin_stale`) for an append and for an UPDATE.

**Differential test.** For every record type and every presence mask of the five optional fields (96 combinations), the domain constructor and the database accept exactly the same rows (a target and, for a
correction, its reversal are built in the same transaction so every domain-valid combination is satisfiable). The domain also checks the same 96 against its own rule table.

**Concurrency.** A second connection with `lock_timeout` 300 ms fails with 55P03 while the first holds the portfolio's lock, is not blocked for another portfolio, and succeeds after commit; a threaded test shows the
second append waits and gets the higher sequence; the advisory key is in the schema namespace.

**Mutation evidence** (scratch copy under `$TMPDIR`; one `sed` expression per mutant, the migration's checksum line rewritten in the copy; the oracle is the three modules above plus the migration tests).
32 mutants. SQL (18): ordering rule removed or `<=`; same-transaction rule removed; reversed-target rule removed; reversal-of-reversal rule removed; lock key without the schema; function unpinned; rename guard removed;
READ COMMITTED check removed; idempotent early return removed; id regex length; date bounds removed; CLEAR forgets `catalog_version`; reversal foreign key without the portfolio; corrected-once and reversed-once
indexes made non-unique; truncate trigger removed; REVERSAL allowed a correction link. Python (14): resolve takes the minimum; reversals beyond the version counted; order by sequence only; boundary test inverted or
removed; pin without its version; correction pair without the portfolio check; `has_same_content` always true; version query MIN; `match` instead of `fullmatch`; future version allowed; duplicate check removed; origin dropped
from the pin; foreign portfolio ignored. **First run: 29 killed, 3 survived** (a REVERSAL carrying a correction link passes the trigger and was refused only by the CHECK, which the differential setup could not reach
because the trigger refused first; the pin's NONE branch; and one sed that did not apply, redone). Tests were added for each (a transaction in which the trigger's checks pass and only the field rule can refuse; a NONE pin at
version 2 differs from version 0). **Second run: 32 of 32 killed.** A mutant that broke the migration left its disposable schema behind (the schema was created before the class cleanup was registered); the test setup now
drops it on a failed open, and the leftover (mine) was dropped.

**Decisions the contracts did not cover.** (1) The table has its own sequence and per-portfolio lock namespace (`finweb.benchmark_selection.portfolio:<schema>:<portfolio>`), never the ledger's. (2) A `CLEAR`
record, so that "no benchmark" is an explicit act and not a missing row. (3) `origin` records whether a suggestion was accepted; the system never writes a row (a test scans for any other writer). (4) A
REVERSAL's `selected_on` is carried and not used. (5) `catalog_version` is NULL until a catalog exists. (6) `PortfolioNotFoundError` is reused from the ledger replay store for an unknown portfolio on a read; a write
to an unknown portfolio is the foreign-key rejection. (7) The pin lives in `domain` (the risk manifest will cite it; CP4c).

**Open.** (a) The catalog check of `benchmark_id` (the main session's `BENCHMARKS.json`): DONE in 17.16 (`admit_selection`, `append_selection(..., catalog=)`). (b) No service function yet that supplies `selected_on` and the explicit user act (`risk_service`, CP4c). (c) The risk manifest that records the pin is CP4c; this
increment builds the read and the pin data and the test that the pin changes with the selection. (d) A pin cannot say whether a LATER reversal exists (it is a point-in-time record by design); `reproduce_risk` will
report `SELECTION_SINCE_REVERSED` as information (17.5.3).

**Correction note (`risk/1.1` Ruling 5.6; engineer, 2026-10-02).** The ordering `(selected_on, selection_seq)` and the trigger rule `benchmark_selection_selected_on_monotonic` above (and the matching paragraph in 17.5.3) are
SUPERSEDED. A pinned version is a sequence number; the selection in force is the latest live record by `selection_seq` up to that version; no record at version 0 is `NONE`; the engine never substitutes a
benchmark. Changes: the monotonic rule is removed from the trigger in 0015 (the checksum line is the revised file's; 0015 was never released); `resolve_selection` is `max(live, key=selection_seq)`; `selected_on` is
data only; the mutants for the monotonic rule and for `(selected_on, seq)` are obsolete (the seq-only ordering has its own tests, including a record dated earlier than its predecessor winning, and a replacement
becoming the latest). The REVERSAL record and the C1C-2 atomic-append refusal remain as documented additions.

### 17.15 CP4b-2 as built: the boundary-rule grid, series conformance, the RISK_FREE kind, the exact sqrt and the registry loader (engineer; 2026-10-02; not yet reviewed)

**Rulings applied.** `risk/1.1` Rulings 2.x (grids, stubs, coverage, MAX_AVAILABLE, zero capital), 4.x (risk-free quote, conversion, staleness, Ruling 4.6 checklist), 7.1 (minimum observations), 9 (registry), 6.9 and 8.2/8.3
(read, not yet built). PM Q1 to Q9 (AC-17 superseded for CP4 onward; migration 0016 approved).

**Files.**
- `src/performance/grid.py` (new): `Frequency`, `grid_dates`, the `BoundaryRule` implementation `WeekdayFridayMonthEndGrid` (daily = weekdays, weekly = Fridays, monthly = last calendar day; stubs declared, never
  clipped or merged); `periods` per year constants `A_f` live in the registry, not here.
- `src/performance/series.py` (rewritten to conform to risk section 2): strictly increasing boundaries inside the window; the declared `requested_base` and stub lengths; no CLIP; zero-capital period (no flow day
  funded) = `INSUFFICIENT_DATA` with detail `ZERO_CAPITAL_PERIOD`; a part-funded period is an ordinary observation; `MAX_AVAILABLE` is a SEPARATE request starting after the last insufficient period and labelled
  (`AFTER_INSUFFICIENT_PERIOD` or `INCEPTION`), and refused with `NO_FULL_PERIOD` when nothing follows.
- `src/performance/engine.py` (`compute_return_series`: grid rule, `verify_identities=True` by default so I-10 and I-11 run in every product call), `manifest.py` (`ENGINE_ID` `performance/cp4-0.15`; pins re-recorded).
- Market data: `contracts.py` (`DataKind.RISK_FREE`, `RiskFreePoint`, `RiskFreeSeries`, `RiskFreeQuoteType` SIMPLE_YIELD / BANK_DISCOUNT, `RateUnit`; the Ruling 4.6 checklist is enforced in the constructor),
  `canonical.py`, `manifest.py`, `port.py` (`risk_free_series`, `risk_free_on`, counted publications), `store.py`, `ingest.py`, `adapters/base.py`, `adapters/calendar_file.py` (calendar kind `RATE_PUBLICATIONS`),
  `adapters/synthetic_risk_free.py` (new; synthetic sources are exempt from the terms gate, never from the profile or the registry record); `DerivedReleaseView` covers the risk-free series so `M_t` is re-derived by the build path.
- `src/persistence/migrations/0016_risk_free_kind.sql` (new; checksum in `CHECKSUMS`): `md_risk_free_series` and `md_risk_free_point`, append-only and sealed with their release, CHECKs that mirror the contract
  (ACT/360 for a discount quote, bounds on `rate`), kinds `RISK_FREE` and calendar kind `RATE_PUBLICATIONS` added, `finweb_app` SELECT only. `0001`..`0015` are untouched; releases WITHOUT a risk-free series keep the
  same projection digest (the `risk_free` key is present only when non-empty; a test migrates a scratch schema through 0015, writes, applies 0016, re-reads).
- `src/risk/` (new package): `risk_free.py` (period conversion), `sqrt.py` (exact integer square root), `registry.py` and `risk_registry.json` (the bundled copy), `__init__.py`.
- `src/product_contract/methodology_registry.py`: a docstring supersession note only (AC-17 is superseded for CP4 onward).
- Tests (new): `test_performance_grid.py`, `test_marketdata_risk_free.py`, `test_risk_free_leg.py`, `test_postgres_risk_free.py`, `test_risk_sqrt.py`, `test_risk_registry_matches_methodology.py`, `test_risk_boundaries.py`;
  updated: the migration counts (16), `MD_TABLES`, `APP_GRANTS`, `ENGINE_PINS`/`ANALYTICS_PINS`, the rich-release store test.

**Risk-free leg (`risk/risk_free.py`).** The quote at a period's START (last publication on or before the start; same day counts), simple interest over CALENDAR days: yield `y/B` per day (`B` 360 or 365 as declared;
percent units divided by 100 exactly), discount `y/(360 - y t)` per day with the bill's own term `t`; `(end - start).days` days. Staleness is counted in the series' own publication calendar: 0 missed =
`AVAILABLE`, 1 = `AVAILABLE`, 2 to 4 = `LIMITED` with `STALE_DATA`, 5 or more = `INSUFFICIENT_DATA` with `STALE_DATA` and no number; no series = `NO_RISK_FREE_SOURCE`; two admitted series for one currency =
`AMBIGUOUS_RISK_FREE_SERIES`; a series whose calendar does not govern it cannot be counted. Everything is `Fraction`; no float.

**Exact square root (`risk/sqrt.py`).** `sqrt_rounded(q, sign, digits=12)`: `N = q * 10^(2*digits)`, `k = isqrt(floor N)`, magnitude `k+1` if `4N >= (2k+1)^2` else `k` (half up; exact for rational squares whose root
is a half quantum, none for irrational roots). Reproduces every sqrt item of part 1. No `math`, no `Decimal` sqrt, no float.

**Registry loader (`risk/registry.py`).** Loads by `registry_id` from CONTENT (`risk/1.1`), resolves `common.*` pointers (whole-value pointers only; prose mentioning one is untouched), validates the twelve entries
against the PRD section 33 schema through `product_contract`, digest = SHA-256 of canonical JSON (whitespace and key order do not change it; any content change does). `minimum_observations(metric_id, frequency)` is
the only source of the thresholds (259/781, 51/155, 11/35; window facts 1/1). **Tie to the Quant's text** (replaces AC-17 for CP4): the shipped copy is BYTE-IDENTICAL to `methodology/registry/<file>.json`, which is
found by its content id, not its name; the id is the document's Convention set ID; every ruling an entry cites is a heading of the document; the thresholds are recomputed from the grid by brute force over every third
end date 2001 to 2029; no threshold literal exists in `src/risk`; the registry prose obeys its own forbidden-word list (P6).

**Measured (default suite).** 1916 tests, OK, 295 skipped (database tests opt in). Cost is as 17.13 (weekly 2.9 s and daily 10.3 s for 30 listings and 2000 events).

**Mutation evidence** (scratch copy under `$TMPDIR`; one `sed` expression per mutant, the migration's checksum line rewritten for SQL mutants; oracle = the eight modules of this increment plus the migration test).
48 mutants: grid (6: Friday offset, weekday bound, month-end, upper bound, stub end, one-period minimum); series (10: increasing check, window check, zero-capital by flow days, always-zero, the detail text,
MAX_AVAILABLE first/start/stub/label, the no-period refusal); engine (3: MAX_AVAILABLE spec, requested base, `verify_identities` default); risk-free (8: basis, discount sign, day count, lookup date, percent,
LIMITED edge, stale reason, no-source reason); store (6: limit edge, latest known, ambiguity, calendar mismatch, same-day, served risk-free in the registry pin); contract (4: discount ACT/360, decimals, term, order);
sqrt (3: tie, floor, sign); registry (2: threshold columns, digest); SQL (6: discount CHECK, point seal, no-update trigger, bounds, kind, calendar kind). **First run: 44 killed, 1 survived, 3 sed patterns that did
not apply.** Survivor: a BANK_DISCOUNT point without its term crashed with a `TypeError` that the adapter turned into the same issue code, so the test saw the right code for the wrong reason (test now asserts the
message). The three inapplicable patterns were redone against the actual lines; one of them (`verify_identities` default False) SURVIVED because every test passed the flag explicitly (a default-call test was added).
**Second run: all killed.**

**Decisions the contracts did not cover.** (1) The grid's `Frequency` lives in `performance` (the registry keys by its text value). (2) A series with an empty range returns `NO_OBSERVATION` with no series (the
contract forbids an empty series). (3) The risk-free read takes the series' own calendar from the port, and two series for a currency are an error, not a choice. (4) `verify_identities` defaults to True for
`compute_return_series`. (5) The bundled registry copy is byte-identical and tie-tested instead of loaded from `methodology/` at run time (the engine reads no file outside its own package). (6) The synthetic
risk-free adapter is exempt from the terms gate but not from the profile or the source registry record.

**Open.** (a) `BENCHMARKS.json` fields wanted: `benchmark_id`, `name`, `provider`, `currency`, `return_basis` (net / gross / price), `calendar_id`, `source_id`, `licensing`, `synthetic`, and whether the series is levels or
returns; and a `RISK_FREE.json` per currency (series id, quote type, unit, day-count basis, calendar id, decimals published, source). (b) The fixture loader for `cp4_golden` parts 1 and 2. (c) The benchmark leg, the
statistics, `RiskManifest`, `reproduce_risk`, comparability disclosure (Rulings 8.2/8.3), `risk_service`, the HG3 pack. (d) 17.5.3's ordering text is superseded (note above).

### 17.16 CP4c as built, to the MIDPOINT: the fixture loader, the catalogs, the benchmark leg, the single-series metrics, the Risk Manifest (engineer; 2026-10-02; not yet reviewed)

**Scope and stop.** Built: the loader for `cp4_golden` parts 1 to 3; the two catalogs and the selection's catalog check; the benchmark leg; volatility, downside deviation, maximum drawdown (with RD-1, RD-3), Sharpe, Sortino and
the benchmark's own return; the state combination of Ruling 7.3; `RiskManifest` and `reproduce_risk`. NOT built, by instruction: beta, R-squared, Jensen's alpha, active return, tracking error, information ratio, the
comparability disclosure (Ruling 8), and the default view (Ruling 7.7: the owner has now confirmed its trigger, PD-0040 addendum; it is built WITH the relative metrics, after the independent review of this midpoint).
Asking `compute_risk` for a metric not built is a `ValueError`, never a silent omission.

**Rulings applied.** `risk/1.2` (registry id `risk/1.2`; Ruling 9.2 (1.2): one registry file per version, the engine refuses an id it does not implement, a manifest records `registry_id` and `registry_digest`);
Rulings 1.1 to 1.5 (drawdown), 2.5 (states of the series), 3.1 to 3.4, 4.4, 5.1 to 5.4, 5.6, 6.2 to 6.6, 6.9, 6.12, 6.13, 7.1 to 7.4, 9.4. PM rulings of this round: the catalogs are the main session's (`entries` empty:
no real benchmark or risk-free source is admitted, PD-0039 D1, PD-0040), `catalog_version` = the catalog id, an id not in `entries` is refused, tests inject their own catalog; stop at the single-series metrics.

**Files.**
- Catalogs: `src/domain/catalogs.py` (pure: `BenchmarkCatalog`, `RiskFreeCatalog`, `parse_*_catalog`, `admit_selection`, `catalog_version_of`), `src/risk_service/` (`__init__`, `catalogs.py`: the only reader of
  `data/marketdata/BENCHMARKS.json` and `RISK_FREE.json`), `persistence/benchmark_selection_store.py` (`append_selection(..., catalog=)`, `append_correction(..., catalog=)`).
- Market data: `marketdata/calendars.py` (`CalendarSet.by_id`, `count_after_calendar`: the same counting rules for a calendar NAMED by id; `count_after` and the new method share `_count`).
- Performance (ENGINE_ID `performance/cp4-0.16`, pins re-recorded): `engine.compute_twr_between` (the TWR of `(start, end]` through `twr_segments`, for RD-1) and a fix found by part 3 (below).
- Risk: `states.py` (the only module naming a reason code; `combine`, the detail vocabulary of Ruling 7.4), `stats.py` (exact sums, the radicands, THE drawdown function), `results.py` (`RiskMetric`, `BenchmarkRef`,
  `DrawdownFacts`), `single.py` (`MetricBuilder`, the five metrics), `benchmark.py` (`BenchmarkLeg`, `open_benchmark`), `manifest.py` (`RiskManifest`, `reproduce_risk` statuses), `engine.py` (`compute_risk`,
  `reproduce_risk`; the only risk module that imports `performance.engine`), `risk_free.py` (`refuse_unadmitted`), `registry.py` (`IMPLEMENTED_REGISTRY_ID`), `risk_registry.json` (now the `risk/1.2` file, byte-identical).
  `RISK_ENGINE_ID` `risk/cp4c-0.1` with `RISK_ENGINE_PINS` in `test_risk_boundaries`.
- Tests: `cp4_golden_kit.py` (loader and checker), `test_cp4_golden.py`, `test_risk_stats.py`, `test_risk_single.py`, `test_risk_benchmark_leg.py`, `test_risk_engine.py`, `test_domain_catalogs.py`,
  `test_marketdata_calendar_by_id.py`; extended: `test_risk_boundaries.py`, `test_risk_registry_matches_methodology.py`, `test_postgres_benchmark_selection.py`, `test_performance_series.py`.

**The catalogs.** `entries` only are read; `candidates` are never parsed into anything (a test poisons them). A synthetic entry is refused in the committed form (Ruling 4.8), allowed only in a test catalog built with
`allow_synthetic`. `digest` = SHA-256 of the canonical JSON of the id and the entries only, so an edit to a candidate, a rule or a date changes no result and an edit to an entry does. `admit_selection` refuses a SELECT
that is not an entry, stamps `catalog_version`, and refuses a SELECT that already names another catalog (never re-stamped); a CLEAR and a REVERSAL name no benchmark and pass. **FINDING (for the main session):**
the committed ids contain a `/` (`benchmarks/1`), which migration 0015's `catalog_version` pattern (`[A-Za-z0-9][A-Za-z0-9._:+-]{0,63}`) does not allow, so the stored form replaces `/` by `:` (`benchmarks:1`;
`catalog_version_of`). Either name the catalogs without a `/` (the function becomes the identity) or widen the pattern in a later migration. Nothing else depends on the choice.

**The risk-free catalog gate.** A REAL series (a release with no synthetic file) that `RISK_FREE.json` does not admit for the reporting currency is no source: `NO_RISK_FREE_SOURCE` for every period, never another
currency's rate. A synthetic series is never catalogued (Ruling 4.8), every result from a release holding one is synthetic, and the gate does not apply to it. With the committed catalog (no entries) any real series fails closed.

**The benchmark leg (Rulings 5.1 to 5.4, 6.9).** `L(g)` is the latest calculation day on or before `g` on the calendar the CATALOG names (counted by `count_after_calendar`: coverage, completeness and the empty-interval rule
as for prices); the missed count gives the price thresholds (0 AVAILABLE; 1 AVAILABLE + `STALE_DATA`; 2 to 4 LIMITED + `STALE_DATA`; 5 or more INSUFFICIENT_DATA + `STALE_DATA`, detail `BENCHMARK_STALE`); no level on or before
`g` is `MISSING_BENCHMARK` + `BENCHMARK_NOT_COVERING_WINDOW`; a calendar that cannot count is INSUFFICIENT_DATA, no reason, `CALENDAR_COVERAGE_GAP`. The translation uses `port.fx_on(c_b, R, g)`: the fixing OF THE GRID
DATE (never the level's own date; a test makes the two differ), the same `marketdata.states.fx_input_state` mapping the valuation uses, the worse state wins, and the fixing's freshness is kept beside the level's (the
lag of Ruling 8.2 will need both). `b = L_R(g_k) / L_R(g_{k-1}) - 1`; RS-2 (the product of the periods is the ratio of the end values) holds exactly and is tested. `benchmark_return` reads `g_0` and `g_n` ONLY (Ruling 6.9: an
interior level is not an input; tested). The whole series is refused as a reference, with `MISSING_BENCHMARK`, when: no selection or a cleared one (`NO_BENCHMARK_SELECTED`, never substituted), the id is not in the catalog or not in
M or its currency or form disagree with the catalog entry (`BENCHMARK_SERIES_UNAVAILABLE`), the entry says `PRICE_RETURN` (`BENCHMARK_NOT_TOTAL_RETURN`; the file is still cited). The total-return check reads the CATALOG's
`return_basis`, because the market-data `BenchmarkSeries` contract carries no basis (no contract change and no migration were needed; Ruling 5.1's "the series carries it" is met by the catalog entry the series is bound to).
NOT built, said so and not defaulted: a series published as RETURNS (Ruling 5.1 compounding needs a base level the contract does not carry: refused as unavailable with its note), and two sources for one benchmark or an ETF proxy
(Rulings 5.7 and 5.5 (1.2): two sources raise `BenchmarkSourcesNotReconciled`; the loader does not load such ids and defers their items).

**The metrics.** One builder, `MetricBuilder.build`, makes every `RiskMetric`. A metric's parts, in the order of Ruling 7.3: the window (a refusal), the periods (Ruling 2.5: any INSUFFICIENT period suppresses with
`PERIOD_INSUFFICIENT` and the reason by `performance` Ruling 1.5 among those periods' causes, each listed; else any LIMITED period gives LIMITED + `STALE_DATA`, `STALE_PERIODS` and the count; else AVAILABLE + `STALE_DATA`),
the risk-free returns (Ruling 4.4), the observation count against the REGISTRY's thresholds (below N1 `INSUFFICIENT_OBSERVATIONS`, below N3 `OBSERVATIONS_BELOW_STANDARD`; no reason code on either; a test scans `src/risk` for a
threshold literal), and the degenerate cases (Ruling 6.12). `risk.states.combine` differs from `PerformanceAggregation` in one place on purpose: a LIMITED result takes its reason ONLY from LIMITED-level causes, so a result
limited by its count alone has no code (CP3's rule gives every LIMITED result `STALE_DATA`, which would invent a staleness). A suppressed metric still carries `stale_period_count` (fixture P7-F1). Everything is exact
(`Fraction`); a square-root metric is `sign * sqrt(Q)` with `Q` exact (`exact_square`, `sign`) and the value from the exact integer root; the Sharpe and the Sortino are one root of one exact quotient. The maximum drawdown is ONE
function (`stats.max_drawdown`; Ruling 1.3: a test fails if a second `def max_drawdown` appears); its dates and `peak_rule` ride with the value. RD-1 (`1 + MDD = 1 + TWR(peak, trough]` from the TWR engine through
`compute_twr_between`, over a window the series was not asked for), RD-3 and RQ-1 run on every call; a failure is INSUFFICIENT_DATA + `CALCULATION_ERROR` + `IDENTITY_FAILED`, never a number. RD-2 and RD-4 are tested
(brute force over every pair; the weekly path is a subsequence of the daily one).

**The Risk Manifest (Ruling 9.4).** `finweb.risk_manifest/1` EMBEDS the portfolio leg's `ComputationManifest` (ledger version and digest, release, the quote, FX and calendar files, conventions, suppressions, source registry
digest, the request and the grid) and adds: the engine id, `registry_id` and `registry_digest`, the metrics asked for, the request, the frequency and the grid rule, the risk-free block (currency, series id, the files read, the
catalog id and digest, a digest of every period's `(f_k, m_k, state)`), the benchmark block (the selection PIN: portfolio, version, state, the row in force; the catalog id and digest, the entry digest, the files read, the
currency treatment), the identities run, the numerics. No calculation timestamp is recorded. `reproduce_risk` re-asks the question and names the wrong input first (ledger, release, registry, suppressions, risk-free catalog,
benchmark catalog, selection pin, conventions, identity facts, source registry), then compares the files read in BOTH directions per kind (portfolio leg, risk-free, benchmark), the manifest id, and the result digest; no
expected digest is `RESULT_NOT_COMPARED`, never `REPRODUCED`. The default is every identity on; `verify_identities=False` leaves only RD-3 (arithmetic on the series) and says so in the manifest.

**The fixture loader (`cp4_golden_kit.py`).** It expands a part's compact definitions through the REAL adapters (calendar files including the new `RATE_PUBLICATIONS` kind, an ECB CSV with `N/A` cells for the declared gaps,
RAW price files in the three real layouts, the synthetic risk-free adapter, the mock adapter for benchmark levels, FEED and FILING corporate-action files) into one release per part, with a TEST benchmark catalog built from the
part's own definitions, and runs the engine per assertion (the F8-B dry run supplies the suppressions where a part has corporate actions). It is tolerant: an unknown block is not an input, an unknown item kind is DEFERRED
with a reason from a closed list, and the tests pin how many items each part has checked and deferred (so a part that grows fails loudly). **Result:** part 1 78 of 78 items checked, 0 mismatches; part 2 8 checked (volatility,
the BANK_DISCOUNT risk-free rates, the six benchmark returns), 53 deferred (relative metrics), 0 mismatches; part 3 17 checked (account scope, zero-capital periods, the snapshot, the split suppression, DAILY and MONTHLY series, the
MAX_AVAILABLE refusals), 50 deferred (37 relative, 6 Current mode, 4 default view, 3 two-source or proxy), 0 mismatches. Tolerance 0 everywhere, the exact radicand and the sign compared as well as the value.

**FINDINGS for the Quant (reported, nothing adjusted).** (1) Part 3 declares `market_data.retrieval_time_all_files` 2022-11-30T00:00:00Z, before every row of its data (to 2026-03-31). The market-data V0 check
(Ruling 2.2: a row dated after the latest session closed at the file's retrieval time contradicts the file) then marks every price series contradicted, and every valuation is INSUFFICIENT_DATA + `MISSING_PRICE_HISTORY`. The
kit retrieves the files after the last session (`honor_declared=False`), and a test records the behaviour under the declared time, so the finding is evidence. (2) Two listings with the same closes on the same dates
(SYN31, SYN32) give byte-identical Alpha Vantage files (the layout carries no ticker) and a file is its hash: the loader writes the repeat with its columns rotated (read by name; every value unchanged). Not a defect of
the fixture, a limit of the file layout; stated so the Quant knows the loader does it. (3) The shared test helper `eastmoney_csv` rounds closes to one decimal; the loader writes the fixture's closes exactly (its own function).

**A defect of mine found by the fixtures.** Part 3 (R8-K1, R11-X1) asserts `requested_base` for a `MAX_AVAILABLE` request refused for `NO_FULL_PERIOD`: the since-inception base `B`. My `compute_return_series` declared the
effective window's start `g_0` there. Fixed (`performance/cp4-0.16`; a test in `test_performance_series`).

**Mutation evidence** (scratch copies under `$TMPDIR`; one exact-string patch per mutant; oracle: the nine modules of this increment). 74 mutants (72 in the main run, plus M-DD1 and a faithful M-DD2 written as separate patches): statistics (9: mean, population variance, the raw-sum forms, the downside divisor, the
Sharpe and Sortino radicands, the sign, the shortfall rule), the Quant's named drawdown mutations (M-DD1 all-history peak, M-DD2 peak search from `g_1`, M-DD3 base moved to `g_1`, M-DD4 earliest peak, plus the trough and recovery
tie rules), single-series (18: the count edges, the stale rules, the stale count, the degenerate checks, RQ-1, RD-1, RD-3, rounding, signs, 252, the window reason, the rate parts, the Sortino `n`), states (3), the benchmark leg (13:
the freshness edges, the translation direction, the missing `- 1`, the level on the day, the price-return and currency and form checks, two sources, a non-positive level, the FX state, the fixing date, the calendar gap), the engine
(12: the selection version, the window ends, RD-1 on and off, the cited-file checks both ways, the registry and catalog and selection checks, the cleared selection, the refusal base), the risk-free gate (2), the registry id (1),
the catalogs (6), the calendar by id (2). **First run: 65 killed, 6 survived, 1 pattern that did not apply.** Survivors: five EQUIVALENT mutants (M-DD2b skips `k = 0`, whose drawdown is 0 by definition; the window part's
reason is also on its cause so dropping it from the part changes nothing; an AVAILABLE result's reason can only be `STALE_DATA` so the guard is redundant; the FX state check against `lookup.rate is not None` selects the same
cases; the benchmark's count part cannot fire because a window fact has threshold 1 and an empty window is refused earlier), and ONE real gap (the fixing at the level's date instead of the grid date): a test now makes them
differ (an HKD report of the US index at a date with a stale level). The mis-patched pattern was redone and killed. **Final: 69 of the 74 killed, 5 equivalent, 0 live survivors.** M-DD1 to M-DD4 give the Quant's counter-values: M-DD1 gives -0.175 for -0.1 on P2-D1 (WEEKLY and DAILY), M-DD4 moves
`peak_date` 2025-12-25 to 2025-12-19 on P2-D1 DAILY and nothing else, M-DD3 and M-DD2 fail P2-D2 (the engine's RD-1 catches the wrong drawdown first: CALCULATION_ERROR instead of the counter-value, which is the identity doing
its job). **The selection-store mutants (the loose end from CP4b-3) were re-run after the Ruling 5.6 change: 32 of 32 killed** (the two monotonic-rule mutants and the (selected_on, seq) ordering mutant are obsolete and replaced
by an ordering-by-date mutant). First re-run: 30 killed, S11 (the idempotent early return) SURVIVED because the monotonic rule had been the only new-row rule a resubmitted plain record could trip; a test now resubmits a REPLACEMENT in a
later transaction (the same-transaction rule would refuse it), which kills it; S9 had a bad sed pattern, redone, killed.

**Cost.** The risk layer adds about 0.03 s to a 784-period DAILY series on the part-1 world (five metrics and RD-1); the series build dominates (17.13).

**Decisions the contracts did not cover.** (1) The total-return check reads the catalog's basis (above). (2) `RiskMetric` is a type of its own, not a `ComputedMetric` (that type carries the CP3 id list, a freshness vector, a
stale weight and a breakdown that do not apply); `exact` is None for a square-root output and `exact_square` holds the radicand. (3) The catalog files are read by `risk_service`, not by the pure packages. (4) The stored
catalog version replaces `/` by `:`. (5) `compute_risk` raises for a metric not built and for a missing catalog or portfolio id a metric needs. (6) A RETURNS-form series and a two-source benchmark are refused or raise, never
defaulted. (7) A series is never read below the request's end: the leg reads `port.benchmark(id, date.min, g_n)`. (8) RD-3 always runs (it is arithmetic on the series); RD-1 and the series identities follow `verify_identities`.

**Open.** (a) The relative metrics, the comparability disclosure and the default view (after the review). (b) Rulings 5.5 and 5.7 (the ETF proxy, two sources with `source_priority`, `BENCHMARK_SOURCE_CONFLICT`) and 5.8
(Current mode): the loader defers their items; the engine has no Current-mode entry for the benchmark and the rate yet. (c) The `catalog_version` encoding of `/`. (d) The part-3 retrieval-time finding. (e) The PostgreSQL path of the
golden kit (the pure path only was asked) and a database round trip of a benchmark series needs no change (the series carries no new column). (f) `risk_service.compute_risk_for_portfolio` and `currency_of`, the HG3 pack.

### 17.17 CP4c fix round: the midpoint review (CP4M-1 to CP4M-6), `risk/1.4` and `cp4_golden/1.2-part3` (engineer; 2026-10-02; not yet reviewed)

**Targets.** `risk/1.4` (`RISK_1.4_REGISTRY.json`, byte-identical copy in `src/risk/risk_registry.json`, `IMPLEMENTED_REGISTRY_ID = "risk/1.4"`; the registry diff from 1.3 is the id, the change note, the status, the implementation version
and the two common keys `selection_rule` and `manifest_intermediates`: no formula, threshold or state moved), `cp4_golden/1.2-part3` (83 items, new portfolio R13). Parts 1 and 2 are unchanged. Engine id `risk/cp4c-0.2`;
`performance/cp4-0.16` and its pins are unchanged (verified); `ANALYTICS_PINS["store"]` re-recorded.

**CP4M-1.** The AVAILABLE + STALE_DATA branch of `MetricBuilder.build` builds a cause whose detail is `STALE_PERIODS`; the test that asserted the omission asserts the detail now.
**CP4M-2.** The risk-free catalog gate tests the SERIES' own lineage (`PeriodRate.series_synthetic`, from `lookup.series.lineage.is_synthetic`), never the release's flag: a real series the catalog does not admit is "no source" even in a
release that also holds a synthetic file; a series whose lineage is not stated is treated as real. **CP4M-3.** The benchmark ref's `source_id` and `synthetic` come from the series read, not from the entry; an entry that disagrees
with the series on source, synthetic flag or currency is refused with `bound=False`, and then NOTHING of the entry is named (a catalog that lies leaves `source_id`, `return_basis`, `currency` and `currency_treatment` None).
**CP4M-5.** The threshold-literal scan includes 11; M-C24 is killed through R2-L2 and by a unit test of its own. **CP4M-6 and Ruling 9.4 (1.4).** Each `RiskMetric` carries `intermediates`, a name-sorted tuple of exact `Fraction`s (validated:
sorted, exact, empty when the value is suppressed), in `to_canonical_dict` and so in the result digest `reproduce_risk` compares. Names: volatility `n, mean_return, sum_squared_deviations (S_rr), variance (s^2(r))`; downside `n, mean_excess,
mean_risk_free (rf-bar), shortfall_sum`; Sharpe and Sortino `n, mean_excess (d-bar), mean_return, mean_risk_free, shortfall_sum, variance`; drawdown `n, wealth_peak, wealth_trough` (the three dates are `DrawdownFacts`); benchmark
return `level_g0, level_gn` (the two translated levels). `Q` is `exact_square` and the sign is `sign` on the result, `n` also in the window; `mean_risk_free` is the rf-bar Ruling 6.8 shows with alpha: it is computed here and the
evidence view reads it. The beta, alpha, tracking-error, information-ratio and active-return rows of the table belong to the relative-metric increment. The intermediates are never in the presented result.

**CP4M-4 and Ruling 5.6 (1.4): the selection log with REVERSAL and correction pairs.** `domain.benchmark_selection.resolve_selection` is the only resolution (the store, the engine and the golden kit call it): over the records with
`seq <= v`, a REVERSAL voids the SELECT or CLEAR it names; a replacement (`corrects_selection_id`) takes the POSITION of the record it corrects, followed back along the chain; the record in force is the live SELECT or CLEAR with the
latest position (ties by seq): IN_FORCE or CLEARED, and NONE when none is live (a reversal of the only record gives NONE; a reversal of a later record gives back the earlier one, never NONE). A version that holds the REVERSAL half of a
pair without its replacement is REFUSED (`SelectionVersionNotPinnableError`; the engine lets it propagate: no state ever existed with that content, and the engine does not answer a question about one). The pin records `position` only
when it differs from the sequence (so every pre-1.4 pin is byte-identical). The store resolves over the rows up to the version through the same function; its append-time rules (pair atomicity by transaction id, a reversal of a reversal is
refused) are from CP4b-3 and unchanged (migration 0015 is frozen, no new migration). The kit's `selection_resolution` items are checked against the domain function (R13-V2, V3, V4, V5, V7 REFUSED, V8, V10), and the R13 replay also runs
through PostgreSQL (`test_postgres_benchmark_selection`). The old build's seq-only resolution gave the wrong record at R13-V8 (M-C29); that divergence no longer exists.

**Catalog ids.** `catalog_version_of` is the IDENTITY (the id is the version) and REFUSES an id that is not a well-formed identifier (letters, digits and `. _ : + -`, at most 64): an id containing `/` is REFUSED, not mapped (a mapping
would make two ids one version). The committed files must say `"benchmarks:1"` and `"risk_free:1"`: **the write guard denies the engineer those two data files, so the main session makes the one-line edit; until then the
four tests that load the committed catalogs fail** (a scratch copy with the edit passes all of them).

**Part 3's three file vintages versus market-data Ruling 0.1 (decision to ratify).** Part 3 (1.1 and later) cuts every series into three file vintages (V1, V2, V3). The store serves one series per currency (RISK_FREE) and the leg
one series per benchmark. A vintage is told apart by `adjustment_anchor` (the vintage label), and files of the SAME source whose points are disjoint and ascending and whose declared fields agree are SEGMENTS of one series (the store for
RISK_FREE, `_one_series` for a benchmark; empty files are ignored; a real/synthetic mix, different sources or overlap is refused). The ingest vintage key for RISK_FREE includes the anchor. The kit's earlier part-3 retrieval override
and finding test are removed: the kit cuts files as the part declares (`VintagePlan`).

**Checked and deferred.** Part 3: 30 checked, 53 deferred (relative metrics 39, benchmark sources or proxy 4, default view 4, Current mode 6); `PENDING_QUANT_RULING` no longer exists. `MINIMUM_MET` is True for all three parts.

**Mutation testing.** The round's first batch (21 CP4M mutants): 21 of 23 killed, F8 equivalent, F3 given a killing test. The 1.4 batch (domain ordering, voiding, pinnability, chain following, position in the pin, each intermediate,
the registry id, the engine's pair handling): 14 of 14 killed after one added assertion (the downside `n`).

**Open.** (a) The two data-file renames (main session). (b) Relative metrics, comparability, default view, Current mode; the 4 multi-source or proxy items (Rulings 5.5, 5.7, 5.8). (c) The Ruling 9.4 rows for beta, alpha,
tracking error, information ratio and active return.

### 17.18 CP4c round 2: segments in the release build (CP4M-7), the benchmark-return intermediates (CP4M-8), one pinnability check (CP4M-9); `market-data/1.12`, `cp4_golden/1.3-part3` (engineer; 2026-10-02; not yet reviewed)

**Targets.** `market-data/1.12` (Ruling 0.1 (1.12), section 11 item 10; the cited id is bumped in `manifest`, `profiles`, `reconciliation` and `market11`, and in every manifest and release id), `cp4_golden/1.3-part3` (83 items,
content hash unchanged: no item value moved; plus `release_cases` RB-1 to RB-5 and the mutation catalog M-R1 to M-R4). Engine id `risk/cp4c-0.3`; `performance/cp4-0.16` and its pins are unchanged. `ANALYTICS_PINS`: `manifest`,
`market11`, `profiles`, `reconciliation`, `store` re-recorded and `segments` added; `RISK_ENGINE_PINS` for `benchmark`, `engine`, `results`, `single`. The CP3 byte-identity baseline is re-recorded because the convention id and
the release id (a hash of the release content, which holds the id) are in every CP3 manifest: the canonical text of the 17 computations before and after, with `market-data/1.11` read as `1.12` and every 64-hex id masked, is
byte-identical (570394 characters each), so the id is the only change.

**CP4M-7: the rule, once, in the release build, for every kind.** New pure module `marketdata/segments.py` (pinned). Several files of one series are SEGMENTS of it only when (a) their declared COVERAGE intervals are
pairwise disjoint (start: the requested `start`/`read_start`, else the first date the file holds; end: the earlier of the requested `end`/`read_end` and the latest date of the governing calendar whose scheduled close or nominal
publication is at or before the file's retrieval time; with a bound on one side only, that bound is used, a superset, so a disjointness shown with it is sound), (b) they share one identity (source, series key, declared static
fields, synthetic flag, adjustment status and anchor), (c) the series is vintage-stable, (d) each passes its own checks (V0 and the after-retrieval test run per file, unchanged). Outcomes are the Quant's, checked in her order:
`REFUSED_IDENTITY`, `REFUSED_NOT_SEGMENTABLE`, `REFUSED_OVERLAP` (with the union span of the shared intervals), plus one of mine, `REFUSED_COVERAGE_UNDETERMINED` (a series in several files whose coverage cannot be stated cannot
be shown disjoint; a single file never needs one). All four are `TwoVintagesError`s (`SegmentError` subclasses). An overlap is refused even when every value agrees and even when one file holds no row on the shared dates.
- **Where.** `ingest._require_disjoint_segments` replaces `_require_one_vintage` and is called by `build_in_memory_market_data` after the calendars are built (prices: the exchange calendar governing the listing's MIC; FX: the ECB
  calendar; risk-free: the series' own `RATE_PUBLICATIONS` calendar; benchmarks: the calendar the file DECLARES in its request as `calendar`, which the catalog also names; corporate actions and vendor-adjusted quotes: never
  segmented). `MarketDataRelease.from_manifests` admits several files per key only when the manifests ALONE prove them disjoint: a segmentable kind, no vendor-adjusted status, equal identity fields, and EVERY file declaring
  its request `start` and `end`, the declared intervals disjoint. The cut is stricter than the build by design (manifests have no calendar and no rows); a release that was not cut is judged by the build alone.
- **Vintage-stable** means: RAW prices (an UNDECLARED quote series is not stable unless the adapter resolved it to RAW), ECB fixings, published index levels (not vendor-adjusted), and a risk-free series whose
  `revision_policy` is `NOT_REVISED` (a `REVISED` or `UNKNOWN` series makes each retrieval a vintage and is never segmented). Vendor-adjusted series (`SPLIT_`, `DIVIDEND_`, `TOTAL_RETURN_ADJUSTED`) never are.
- **No vintage label in any key field.** `adjustment_anchor` keeps its Ruling 2.3 meaning: `series_keys` (manifest) and the series key at the build carry the anchor ONLY for a vendor-adjusted series, so a label on a raw file cannot
  make a second series; it is a difference of IDENTITY (refused first). `adjustment_anchor` was removed from the kit's vintage handling: it writes none. The kit declares each file's coverage in its request (`start`, `end`) as the
  part's `segments` text states, and the benchmark's calendar.
- **The read side.** The release build hands the store the files of an admitted series; the port still returns one series per file, with every segment file cited in `consumed`. `store._rf_one_series` and `risk.benchmark._one_series`
  are NOT retired but reduced: they only ASSEMBLE what the build admitted and keep their old checks as a fail-closed assertion for a store built by hand (overlap, order, a declared field that differs: `NO_SELECTION` or
  `BenchmarkSourcesNotReconciled`). They no longer carry the rule, and nothing in the read path looks at an anchor.
- **Where it does not bite.** The synthetic-flag identity difference between files of one source cannot arise through the source gate (a real-scope file of a synthetic source is an `IngestError` first), so RB-5 is refused by the
  cut as `REFUSED_IDENTITY` and by the build as an `IngestError`; the identity rule itself is run on the exact RB-5 facts (pure test, and hand-built risk-free entries differing in usage scope).
- **Tests** (`test_market_data_segments`): RB-1 to RB-5 by the cut (coverage declared) and by the build of a release that was not cut (declared and undeclared), the overlap spans equal the Quant's, the admitted RB-1 is one series with
  every row once and three files cited; the reviewer's demonstrations (a backfill at a segment edge, and an anchor-labelled overlapping re-download of prices, agreeing, scaled by 1.5 and backfilling, with and without a label); the
  same for risk-free rates (edge backfill, agreeing and scaled re-download, a label, a REVISED or UNKNOWN series); touching versus adjacent declared intervals; the pure rule and the M-R1 to M-R4 counter-tests; and through
  PostgreSQL (`write_release` as the owner, `read_release` as `finweb_app`: the same projection digest, quotes and risk-free rows once each, every file cited). The store holds files and rows only: no segment table and no migration.

**CP4M-8.** `benchmark_return` records, besides `level_g0`, `level_gn` (the translated levels L_R), `index_level_g0`, `index_level_gn` (the index's own L), and when the index is translated `rate_g0`, `rate_gn` and
`fixing_date_g0`, `fixing_date_gn`. A fixing date is a `date` in the intermediates (`RiskMetric.intermediates` now admits a Fraction or a date; both are canonical-JSON leaves and in the digest). A benchmark already in the reporting
currency has no rate and no fixing, and none is recorded. Tests: Q2-T1 (HKD in USD) and Q1-B1 (USD).

**CP4M-9: one check, one error type.** `SequencedSelection.atomic_with_seq` is the boundary fact a loader states: the greatest `selection_seq` of the OTHER rows appended by the same transaction (None when appended alone). It is not in
`to_obj`, a row digest or a pin. `domain.benchmark_selection.check_pinnable` is the one check: a row at or below the version whose partner lies above it cuts a pair; and, for rows without the fact, a replacement above the version
whose target a known row reversed (the fallback for a hand-built full log). It is called by `resolve_selection`, so the engine, the kit and the store share it, and it raises `SelectionVersionNotPinnableError`.
`persistence.benchmark_selection_store`: `load_selections` reads the fact (`LOAD_SQL`, from `append_xid`), `require_committed_boundary` is now `check_pinnable` over the loaded rows (the BELOW/ABOVE queries are gone), and
`SelectionVersionNotABoundaryError` is an alias of the domain class. So the rows `load_selections(conn, p, 9)` returns, passed to `compute_risk` at version 9, are refused (they answered the ETF proxy), exactly as `selection_in_force`
refuses. **A caller who builds a log by hand without the fact and gives only the rows up to the version is outside the contract** (the domain cannot know what it was not told): the production source is the store, which always states it.

**Mutation testing.** 25 mutants of the round (the Quant's M-R1 to M-R4 as the engine's patches, identity at the cut and at the build, the three coverage bounds, the key anchor in the manifest and at the build, touching intervals, the
manifest proof, the build gate skipped, revisable risk-free series, the synthetic flag, the pair fact ignored, off by one and fallback removed, each CP4M-8 intermediate): **25 of 25 killed** after three additions (a RISK-FREE test
with a usage-scope difference, a request beyond what was available, touching declared intervals).

**Decisions the contracts did not cover.** (1) `from_manifests` requires a declared `start` and `end` on every file of a series in several files; the build derives the coverage when none is declared. (2) A series in several
files whose coverage cannot be stated is refused (`REFUSED_COVERAGE_UNDETERMINED`), not admitted. (3) A benchmark file in several segments declares its calendar in its request (`calendar`), because a `BenchmarkSeries` carries
none. (4) UNDECLARED prices are segmentable only after the adapter resolved them to RAW. (5) `segments` is pinned as an analytics module. (6) A fixing date is an intermediate of type date.

**Open.** (a) Ruling 0.1 (1.12) on `Current` mode: "a date covered only by a segment retrieved after t has no reading at t" follows from `M_t` (the files retrieved at or before t) and is exercised by the part-3 Current items, which stay
deferred (CURRENT_MODE_NOT_BUILT). (b) The relative metrics, comparability, default view. (c) A real benchmark adapter must DECLARE the calendar in its request when it delivers segments.

### 17.19 CP4c round 3: rows outside the declared coverage (CP4M-10), the catalog calendar, the boundary fact that cannot be forgotten; `market-data/1.13`, `cp4_golden/1.4-part3` (engineer; 2026-10-03; not yet reviewed)

**Targets.** `market-data/1.13` (Ruling 0.1 (1.13), items 1(b) and 1(c)), `cp4_golden/1.4-part3` (83 items, content hash unchanged; `release_cases` RB-1 to RB-9, mutations M-R1 to M-R7). The cited id is bumped in `manifest`, `profiles`,
`reconciliation` and `market11`. Risk modules are unchanged, so `risk/cp4c-0.3` and its pins stand; `performance` unchanged. `ANALYTICS_PINS` re-recorded (`manifest`, `market11`, `profiles`, `reconciliation`, `segments`; `store`
unchanged since round 2). The CP3 byte-identity baseline is re-recorded for the id alone, shown the same way as in 17.18 (the canonical text of the 17 computations before and after, 1.12 read as 1.13 and every 64-hex id masked,
is byte-identical, 570394 characters each).

**CP4M-10: the rule as the Quant wrote it.** In a series of SEVERAL files (a single-file series is unchanged and needs no coverage; its rows are Ruling 3.1's):
- the order of checks is IDENTITY, NOT_SEGMENTABLE, COVERAGE_UNDETERMINED, ROW_OUTSIDE_COVERAGE, OVERLAP, then ADMITTED. `REFUSED_ROW_OUTSIDE_COVERAGE` (renamed from my first `ROWS`) is `SegmentRowsOutsideCoverageError`.
- a file holding a row dated before its declared start or after its coverage end is refused, and with it the build. The coverage is NEVER widened to the hull (M-R5), a stray row is NEVER ignored (M-R6), and a coverage that
  cannot be stated is NEVER given the hull of the rows (M-R7). Coverage end is the earlier of the requested `end` and the latest date available by the retrieval time, so a row after a derived end is outside too.
- **"First row held" is a start for a FULL-HISTORY file only** (1.13). `segments.is_full_history`: the payload format is the ECB `eurofxref-hist` layout, or the request says `full_history` = `true`. Any other file of a series in
  several files with no requested start has no coverage: `REFUSED_COVERAGE_UNDETERMINED`. So a start-only request is a coverage (the end is what was available), a file with no request is not. This is a CHANGE from round 2, which
  inferred the start from the rows; the kit already declared both ends, and the tests that relied on the inference now declare a start.
- **Where.** The build: `FileSegment.rows_outside` is filled per file from the dates it holds and its coverage, and `admit_segments` judges it in the Quant's order. The cut cannot see rows, so it still proves only what the manifests
  show (declared intervals disjoint); **a cut release with a stray row is built and refused by the build**, which is the gate for every release however cut. The PostgreSQL projection (`write_release`) calls the calendar-free
  subset (`require_rows_inside_request`: for a file that shares a series key with another file, no row outside its declared `start` / `end`; `read_start` / `read_end` are a read window of a full-history file and never a request), so a
  file that says one thing and holds another is in no stored release, and a single-file series is not judged.
- **Tests** (`test_market_data_segments`): RB-1 to RB-9 by the cut (with the rows the cut cannot see noted) and by the build, with the declared coverage and without (undetermined); the reviewer's case (a July file with a June
  row) by the cut, the build and the projection; a row after the end; a derived end; FX segments (rows of the first file's range in the second, a row after the first file's end), risk-free segments, benchmark segments; the pure order and
  the M-R5/M-R6/M-R7 counter-tests; a single-file series unchanged, in the build and in the projection.

**Point 3: the catalog calendar.** `build_in_memory_market_data(..., catalog_calendars=...)` takes `{benchmark_id: calendar_id}` (the catalog entries'). A SEGMENTED benchmark file whose declared request `calendar` differs from its
entry's (or declares none) is refused, `REFUSED_CALENDAR_MISMATCH` (`SegmentCalendarMismatchError`, a `TwoVintagesError`); an id the catalog does not name, no catalog argument, and a single file are not compared. The kit passes the
part's own catalog. No production caller passes it yet (the committed catalog has no entries; the service that builds a release from the catalog is not built): **whoever builds a release for the engine must pass it.**

**Point 6: "not stated" is not "alone".** `SequencedSelection.atomic_with_seq` defaults to the sentinel `NOT_STATED` (a distinct singleton), and `None` means only "appended alone". `check_pinnable` refuses a REVERSAL at or below the
version whose fact is `NOT_STATED` (with the same `SelectionVersionNotPinnableError`), so a loader that forgets the fact fails closed. The store's `from_row` states NOT_STATED for a plain read (no boundary column) and the fact for
`load_selections`; the kit and the domain test helper state `None` for rows appended alone. A row that says "alone" while a replacement above it names its target is still refused (the consistency fallback).

**Mutation testing.** 15 mutants (M-R5 the hull, M-R6 rows ignored, in the build and in the pure rule; M-R7 the hull for an undetermined coverage; full-history never or always; the row check after the overlap and before the
undetermined check; the calendar comparison off, and applied to single files; NOT_STATED read as alone, and applied to non-reversals; the store's plain read stating "alone"; the projection check off, and applied to single files; a read
window taken for a request): **15 of 15 killed** after three additions (a single-file benchmark, a read window is not a request, the projection's single-file test). The DB-environment mutants were run with the database.

**Decisions the contracts did not cover.** (1) The full-history marker beyond the ECB format is the request pair `full_history` = `true`. (2) The projection's check is the declared-request subset because it has no calendar and no
resolver; the build is the complete gate. (3) The cut still requires a declared `start` and `end` on every file of a series in several files (stricter than the build, which accepts a start with the end left to the retrieval time).

**Open.** (a) The service that builds a release from the benchmark catalog must pass `catalog_calendars`. (b) Real adapters must declare `start` (and `end`) and, for benchmarks, `calendar` when they deliver segments.

### 17.20 CP4d increment 1: the benchmark-relative metrics and the comparability disclosure (engineer; 2026-10-03; not yet reviewed)

**Targets.** `risk/1.4` Rulings 6.7 to 6.11, 6.13, 7.3, 8 and 9.4 (1.4); `cp4_golden/1.4-part3` and `1.0-part2`. Engine id `risk/cp4d-0.1`. New modules `risk/relative.py` and `risk/comparability.py` (pinned in `RISK_ENGINE_PINS`),
and `results.py`, `single.py`, `engine.py` changed. No market-data, performance or registry change.

**What is built.**
- `risk_beta`, `risk_r_squared`, `risk_alpha_jensen`, `risk_tracking_error`, `risk_information_ratio`, `risk_active_return` (with `risk_volatility` etc. and `benchmark_return` as before). `compute_risk` accepts them; a metric that is not built
  is still a `ValueError`. Alpha reads the risk-free catalog; the other five read no rate (Ruling 6.7: beta is on TOTAL returns, so M-B3 and M-B17 have no counterpart in this design, and a test shows beta needs no rate).
- **Parts, in the order of Ruling 7.3:** the window and the series' periods (or, for the active return, the window return from the TWR engine itself: its state and causes are the portfolio leg's, Ruling 6.9 (1.1), so
  R11-X3 is `SOURCE_CONFLICT` with no `PERIOD_INSUFFICIENT` detail), the rates (alpha), the benchmark levels and translations at every grid date the metric reads (`g_0 ... g_n`; `g_0` and `g_n` only for the active return),
  the count, then the degenerate cases (`ZERO_BENCHMARK_VARIANCE`, `ZERO_PORTFOLIO_VARIANCE` for R-squared only, `ZERO_TRACKING_ERROR`). A refused benchmark is `INSUFFICIENT_DATA` + `MISSING_BENCHMARK` with the portfolio's own
  details still listed.
- **Values.** beta `S_rb / S_bb`; R-squared `S_rb^2 / (S_bb S_rr)`; alpha `A (d-bar - beta x-bar)`; tracking error and the information ratio as `sign * sqrt(Q)` with `Q` exact (`A s^2(a)`, `A a-bar^2 / s^2(a)`); active return
  `TWR - benchmark return`, arithmetic, with the decomposition view apportioned by `performance.numerics.apportion` (largest remainder). Everything exact; nothing computes from a presented value.
- **Identities, each a runtime check whose failure is `INSUFFICIENT_DATA` + `CALCULATION_ERROR`:** RS-2 (benchmark returns telescope to the level ratio), RB-1 (`0 <= R^2 <= 1`, `beta^2 S_bb = R^2 S_rr`), RA-1 (the series' window return equals the TWR engine's), RQ-1 on the information ratio.
- **Ruling 9.4 (1.4) intermediates**, in the digest: beta and R-squared `n, mean_return, mean_benchmark_return, sum_cross_deviations, sum_squared_deviations_benchmark, sum_squared_deviations_return` (+ `v_beta` for beta, exact,
  never presented, compared with the fixture's `v_beta`); alpha `n, mean_risk_free (rf-bar), mean_excess, mean_benchmark_excess, beta, sum_cross_deviations, sum_squared_deviations_benchmark`; tracking error and IR
  `n, mean_active, sum_squared_deviations, variance`; active return `n, portfolio_twr, benchmark_return`.
- **Comparability (Ruling 8, 8.2 (1.1), 8.3 (1.1)).** `RiskMetric.comparability` is a `Comparability` (`class`, `seam`, `lagged`), a DISCLOSURE: the state is whatever Ruling 7.3 gives, and an `INSUFFICIENT_DATA` result carries none (the
  constructor refuses it). The portfolio leg's inputs at each grid date are the freshness entries of the total at that point (`ReturnSeries.boundary_values`): exchange calendars and the ECB fixing; the benchmark leg's are its
  calculation calendar and the ECB fixing if translated. `lagged.points` lists the dates where the two lags differ; `seam.portfolio_calendars` and `seam.benchmark_calendars` are the two sorted instant sets (the ECB appears as the
  ECB calendar's id, e.g. `SYN4_ECB`); an empty portfolio set is no seam; `max_offset_minutes_at_last_grid_date` is the largest `|p - b|` of scheduled instants at `g_n`, whole minutes (770 for the HK holding against the NY
  index). `RiskMetric.decomposition` carries the view of Ruling 6.9 (1.1).

**Proof.** Part 2: 61 of 61 checked, 0 deferred (the deferral reason `RELATIVE_METRIC_NEXT_INCREMENT` is gone). Part 3: 58 checked, 25 deferred (15 two-source or proxy items, 6 Current-mode, 4 default-view; increment 2). Every
checked item matches on the pure path AND through PostgreSQL (`test_postgres_cp4_golden`: the release projected by the owner and read back as `finweb_app`, and the selection log appended with `append_selection` /
`append_correction` and handed to the engine as `load_selections` returns it, truncated at the pinned version; the ledger events are the kit's, in memory, until `risk_service` reads them from the ledger table in increment 2).
**No disagreement with a fixture was found in this increment.** Mutation testing (the Quant's M-B1 to M-B23 and M-C14 to M-C20 that apply, plus structural mutants of the new code): 25 of 25 killed against the engine.

**Decisions the contracts did not cover.** (1) The container names of the new intermediates (above). (2) The information ratio is also RQ-1-checked (Ruling 6.13 names RQ-1 for Sharpe and Sortino only; the same exact relation holds). (3) `window_twr`
(the TWR engine's `Valued` for `(g_0, g_n]`) is computed for every active return, whether or not `verify_identities` is on, because it is the portfolio leg's state, not only a check. (4) `risk_active_return` over a window with a
LIMITED stale period gets its state from the TWR engine's window return, not from the periods (no `STALE_PERIODS` detail on it).

**Open (increment 2).** Two sources and ETF proxies (Rulings 5.5, 5.7), Current mode (5.8), the default view (7.7), `risk_service`, the part-3 items they unlock, and the ledger-through-PostgreSQL leg of the golden test.

### 17.21 CP4d increment 2: two sources, ETF proxies, Current mode, the default view, `risk_service`, and the ledger-through-PostgreSQL leg (engineer; 2026-10-03; not yet reviewed)

**Targets.** `risk/1.4` Rulings 5.5 (1.2), 5.7 (1.2), 5.8 (1.3), 7.7 with the PD-0040 addendum, 8 and 9.4; `cp4_golden/1.4-part3`. Engine id `risk/cp4d-0.2`. `ANALYTICS_PINS["manifest"]` re-recorded (the optional `source_priority`
on `SourceRecord`; absent from `to_obj` when unset, so no registry digest moves). `RISK_ENGINE_PINS` re-recorded for benchmark, engine, manifest, relative, states and the new `levels`.

**What is built.**
- `risk/levels.py` (new): `LevelBook` (one level per calculation day with a status), `reconcile_sources` (Ruling 5.7: one source is SINGLE_SOURCE; agreeing sources are CORROBORATED when their independence groups differ, else
  SINGLE_SOURCE; the primary's level is carried; a disagreement withholds the day as `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, detail `BENCHMARK_SOURCE_CONFLICT`; published decimals, so levels agree iff equal) and `build_proxy`
  (Ruling 5.5: `TR_t = TR_prev * f_t * (P_t + d_t) / P_prev`, base the first print, prints with volume > 0 only, an ex-date that is not a print applied at the next print, a dividend DISAGREEMENT withholds every level from the first
  print on or after the ex-date, a price DISAGREEMENT poisons that print and every later one).
- `risk/benchmark.py`: the leg reads a `LevelBook`; `open_benchmark` handles a proxy entry, several sources (priority from the registry) or one; a withheld day, Current-mode "not yet due is not missed" and the FX adjustment.
- Current mode (Ruling 5.8 (1.3)): `compute_risk_current` and `reproduce_risk(market_at=...)`. `E = D_c(t)` by `performance.current.choose_current_date` from the portfolio's inputs only; everything is read over `M_t`; a benchmark day exists
  at `t` only if its close is at or before `t`; the manifest has a `CurrentBlock` (mode, instant, rule, date, causes, parent release, excluded files) and `BenchmarkBlock.level_date_gn` / `fixing_date_gn`, added to `to_obj` only in
  Current mode so historical ids are unchanged. A date that cannot be chosen: every metric `INSUFFICIENT_DATA` + `CALENDAR_COVERAGE_GAP`, no reason code, no series.
- `risk_service/default_view.py` (Ruling 7.7): 3Y trailing request falls back to MAX_AVAILABLE iff X is `INSUFFICIENT_DATA` with one of `WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`, `PERIOD_INSUFFICIENT`, `ZERO_CAPITAL_PERIOD`;
  Y is shown whatever its state, X carried as `refused`; evidence has both digests, both manifest ids and the `fallback` flag.
- `risk_service/service.py`: `compute_risk_for_portfolio`, `compute_risk_current_for_portfolio`, `currency_of`, pinned ledger and selection reads, the synthetic-data refusal (`SYNTHETIC_MARKET_DATA_REFUSED`; a labelled
  `allow_synthetic=True` opt-in for fixtures), the confirmation-policy gate and the read-only F8-B detection. `risk_service/groups.py` (UAT-03): the independent group and the benchmark group; a selection change recomputes the benchmark
  group only, a ledger change both; a view is `CURRENT` only if both pins are present (`STALE_SELECTION`, `STALE_LEDGER`, `STALE_LEDGER_AND_SELECTION` otherwise).
- `DerivedReleaseView(..., catalog_calendars=None)` passes the catalog calendars to the build.

**Proof.** Part 1: 78 checked. Part 2: 61 checked, 0 deferred. Part 3: 83 checked, 0 deferred, 0 mismatches (the deferral list is empty; `DEFERRED_REASONS` keeps only `KIND_UNKNOWN_TO_THIS_LOADER`). Parts 2 and 3 also pass through
PostgreSQL as `finweb_app`, via `risk_service`, with the ledger (atomic groups, internal-transfer pairs), the selection log (`append_correction` for pairs), market data and every `M_t` read from the database. **No disagreement with a fixture
was found.** Mutation testing on copies: 24 structural mutants of the engine/leg/levels (one, a gap ignored, first survived and is now killed by new assertions) and 9 of the service/groups (DB env): 33 of 33 killed.

**Decisions the contracts did not cover.**
1. `source_priority`: optional positive int on a `SourceRecord`; 1 is primary; unique among the sources of one benchmark id; required only for a source serving a benchmark another admitted source also serves (a multi-source benchmark with a
   missing or repeated priority is a `MISSING_BENCHMARK` refusal, `BENCHMARK_SERIES_UNAVAILABLE`). No committed admitted source needs it today.
2. Catalog field `proxy_listing_id` (optional UUID on a `BenchmarkEntry`): `BENCHMARKS.json` documents `proxy_of` (the underlying index) but names no listing. A catalog schema addition for the main session.
3. Resolution records (RESOLVED_BY_EVIDENCE) are not built. 4. RF quote publication at or before `t` is not separately enforced; `M_t` membership covers it. 5. `risk_service` imports `performance_service` private helpers (`_pin`, `_detect`,
   `_calendars_of`). 6. Notes show the published decimal, never a Fraction.

**Open.** (a) Main session: add `proxy_listing_id` to the catalog schema/data when a proxy benchmark is admitted; add `source_priority` to `SOURCES.json` for any benchmark served by two admitted sources. (b) A production release-building
service must pass `catalog_calendars`. (c) Next: the final independent CP4 review.

### 17.22 CP4e: the exit test, the risk availability matrix, one defect the matrix found (engineer; 2026-10-03; not yet reviewed)

**Targets.** CP4 exit criterion ("every metric includes definition/version/data requirements and fails safely when inputs are insufficient"; PRD 38.3), `risk/1.4` Rulings 7.1 to 7.5, tech plan 17 CP4e. Engine id `risk/cp4e-0.1`
(`relative.py` changed; `RISK_ENGINE_PINS` for `relative` and `engine` re-recorded). No market-data, performance or registry change. The HG3 evidence pack is NOT built here (after CP5, as instructed).

**`tests/product/test_cp4_exit.py` (32 tests; one needs the database).**
- **Scenarios.** 34 scenarios over 15 conditions (the eight PRD 38.4 edge cases, no risk-free source, and the plus rows: flat benchmark, Current mode, account scope, snapshot, zero-capital period, split suppression). Each
  runs ALL 12 metrics once and has a hand-written cell `(state, reason, exact set of risk detail names)` for every metric, derived from Rulings 7.1 to 7.5 (not from output). 31 of the 34 use a request the Quant's fixtures
  assert, and `CellsAgreeWithTheFixtureTests` compares each cell with the fixture's item wherever one exists on the same request (more than 60 items); the 3 constructed ones (a 60-month request on a 3-year portfolio, a
  7-observation window, R3 with five consecutive CNY fixings missing) are labelled `constructed`.
- **(a) Registry.** All 12 entries carry every PRD 16.3 requirement; every result's `method_key` is `risk/1.4#<metric>` and its manifest names the registry id and digest; the registry's own benchmark and risk-free dependency
  columns equal the engine's groups and the metrics that name `NO_RISK_FREE_SOURCE`.
- **(b) Fails safely.** A refused metric has no value, exact, radicand, sign, intermediates, comparability, decomposition or drawdown; an AVAILABLE or LIMITED one has its window, count and the registry's thresholds, and a number
  below N1 is never shown; reasons are coupled to states; `MISSING_COST_BASIS` never appears; the independent group is identical to the same request under a working benchmark when the benchmark is missing in any of its forms; a
  metamorphic test gives P6's in-kind holding a cost basis and every state, reason, detail and value is unchanged.
- **(c) Matrix.** metrics x conditions built from the data above: a row per registered metric, a cell per condition, every cell non-empty and holding; adding a metric or a condition without a row fails.
- **(d) Determinism.** Every scenario's canonical result is byte-identical in-process (a cold world against the warm one) and across processes at five `PYTHONHASHSEED` values (0, 1, 2, 3, random). **The engine holds no memo**
  (a source scan fails if one appears), so there is no memo-on/off comparison to make; the scan is what makes it mandatory the day one is added.
- **(e) Reproduction.** `reproduce_risk` gives REPRODUCED for every distinct golden result of parts 1 to 3 (historical, Current-mode and account-scope included), `RESULT_NOT_COMPARED` without a digest, `RESULT_DIFFERS` for a wrong
  one, and REPRODUCED for every scenario's result.
- **(f) UAT-03.** The engine-level partition on Q1's five selection versions (the independent group's result is the same bytes at every version and names no benchmark; the benchmark group differs at every version); and, with
  the database env, `test_uat_03_end_to_end_through_the_risk_service_and_the_database` runs the four UAT-03 tests of `test_postgres_risk_service` (selection moved: only the benchmark group recomputed and the independent result
  is the same object; ledger moved: both; no old view stays `CURRENT`).
- **(g) CP3.** The byte-identity test is run from the exit module and holds; the three golden parts are checked in full (78 + 61 + 83 = 222 items, 0 deferred, 0 mismatches).

**Mutation testing (copies only; the exit test alone).** 16 of 16 killed: chain assumed for the active return; reason chosen from any level (M-C24); count detail dropped; the Sharpe ratio placed in the benchmark group;
benchmark refusal part dropped; zero-volatility check removed; price-return benchmark accepted; RA-1 claimed PASS where not computable; the active return refused where the TWR engine has a value; reproduction ignoring the
digest; a wrong `method_key`; an empty registry FX field; the selection version ignored; a renamed detail; and two non-deterministic digests (hash seed, process id).

**A defect the matrix found (and the open finding it leaves).** `risk_active_return` over a window that contains a `ZERO_CAPITAL_PERIOD` (part 3, R9 over 12 months) raised an `AssertionError` in `relative._returns`: the
function chains the series' periods and a zero-capital period has no return. No fixture asked for it (R9-Z1 asserts only volatility and drawdown). Fixed in `relative.py`: the active return's value is the TWR engine's window
return (Ruling 6.9 (1.1): its state is that of `TWR(g_0, g_n]`), and RA-1, which compares the series' chain with the engine, is recorded `NOT_COMPUTABLE` in the lineage when the chain does not exist; every metric that reads
the periods is refused before this point, as Ruling 2.5 says. **This is a method question for the Quant**, listed in `OPEN_FINDINGS` of the exit test: Ruling 6.9 (1.1) (and R11-X3, where the active return does not take
`PERIOD_INSUFFICIENT`) support AVAILABLE; Ruling 2.4's "every statistic over a window containing it" supports INSUFFICIENT_DATA. The cell is asserted as the engine now behaves; `test_the_exit_criterion_has_no_open_finding` is an
EXPECTED FAILURE while the finding is listed, and becomes an unexpected success (a failing suite) the day the list is emptied, so the Quant's ruling cannot be forgotten.

**Decisions the contracts did not cover.** (1) A scenario's cell is the exact set of Ruling 7.4 detail names (as the fixtures compare), not a subset. (2) The DB UAT-03 tests are run from the exit module with the other suites'
env; without it they are SKIPPED, and said to be skipped. (3) The 5 hash seeds are 0, 1, 2, 3 and random.

**Open.** The Quant's ruling on the active return over a zero-capital window (above). The HG3 evidence pack after CP5. The final independent CP4 review.

### 17.23 CP4 final fix round: the review's findings CP4F-1 to CP4F-11, `risk/1.6`, `cp4_golden/1.6-part3` (engineer; 2026-10-03; not yet reviewed)

**Targets.** `reviews/TECH_REVIEW.md` §41 (HOLD: 1 HIGH, 3 MEDIUM, 7 LOW); `risk/1.6` (Rulings 5.5 (1.6), 6.9 (1.5), 7.3 (1.5), 7.7 (1.6); registry `RISK_1.6_REGISTRY.json`); `cp4_golden/1.6-part3` (95 items). Engine id `risk/cp4f-0.1`; `RISK_ENGINE_PINS`
re-recorded for benchmark, engine, levels, registry, relative, risk_free and single. The engine's registry copy is byte-identical to the 1.6 file and the engine implements `risk/1.6` only (1.0 to 1.5 are records). Not in this round, by instruction:
nothing. (CP4F-5 and CP4F-10 were first held for the Quant and came back ruled in 1.6; they are in.)

**What changed, by finding.**
- **CP4F-1 (HIGH), Ruling 6.9 (1.5).** `relative_metrics` adds a cause (no reason, detail `ZERO_CAPITAL_PERIOD`) to the active return whenever a period of the window is a zero-capital period; the benchmark return is untouched. The "no period chain" path
  (`_one`) is NOT refused wholesale: an interior valuation that is not a TWR input (five missing HKD fixings at one interior grid date, part 2 Q6) leaves the active return AVAILABLE with the TWR engine's value (6.9 (1.1)); that case is a
  constructed exit scenario. The lineage entry that recorded the chained window return against the TWR engine's is now `identity:RS-1` (it was labelled RA-1; Ruling 6.13's RA-1 holds by construction). The exit test's open finding is cleared
  (`OPEN_FINDINGS` empty, the expected-failure marker is a plain test).
- **CP4F-2 (MEDIUM), Ruling 7.3 (1.5).** A refused window (`WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`) still evaluates the window-independent causes: `_benchmark_context` calls `open_benchmark` at the request's `E` (series not in M, a binding the entry
  fails, a price-return series) and `risk_free.source_probe` asks for `NO_RISK_FREE_SOURCE`; a freshness, coverage or withheld-day cause needs a grid date and is not asked. Tested on the reviewer's cases (Q1 at selection versions 2, 3, 4 and P10, 60 months).
- **CP4F-3 (MEDIUM), Ruling 5.5 (1.2) item 4.** `levels._identify_actions` identifies a corporate action by its STATEMENT: one source's statements are deduplicated; a regular and a special dividend on one ex-date from one source are two actions, both applied;
  statements equal across sources are one corroborated action; two unequal statements about the same action (same ex-date, or for a dividend the same pay date, or for a split the same ratio) from disjoint sources are a DISAGREEMENT and neither is applied.
- **CP4F-4 (MEDIUM), Ruling 5.7 (1.2).** (a) A second source of a benchmark id is bound to the catalog: `BenchmarkEntry.additional_sources` (new optional field, absent from `to_obj` and so from every catalog digest when empty) lists each other source with
  its `return_basis`; a source serving the id that is not declared with the entry's basis refuses the whole benchmark (`BENCHMARK_SERIES_UNAVAILABLE`), so a price-index copy never fills a day the primary lacks. (b) Levels agree within the sum of their precision
  bounds (half a unit of the last published digit, as `market-data`'s `_agree`), not exactly. (c) A source that declares no upstream is independent of nothing: agreement with it is `SINGLE_SOURCE`.
- **CP4F-5 (ruled in 1.6), Ruling 5.5 (1.6).** A disputed ETF PRINT is withheld for that day only and the chain links around it (a dividend or split dated on it applies at the next print); a disputed dividend or split BREAKS the chain at its ex-date
  (`DayLevel.segment`, `BenchmarkLeg.span_part`: a ratio across the break is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, ratios inside one chain are what they would be without the dispute); a print with no usable reading is missing (staleness), not a conflict.
  The part-3 loader expands the new `second_source` of SYN33 (a second price upstream with declared disagreements).
- **CP4F-6 (LOW), Ruling 5.8 item 5.** The Current-mode FX lookup is made AT THE LATEST ECB FIXING DUE AT `t`, so the port counts only due fixings; before, the not-yet-due ones were subtracted from the port's count after the lookup, and the port withholds the rate at 5
  before any adjustment could apply. R7-C1 with the USD fixings of 01-05 to 01-08 missing is LIMITED + STALE_DATA with the number; five due ones are still withheld.
- **CP4F-7 (LOW).** `RiskView` pins the release id, the as-of and the reporting currency as well as the two versions; `compute_view`, `refresh` and `status` take the release and as-of the caller asks about (keyword, required) and read the currency from the database.
  A moved ledger, release, as-of or currency recomputes both groups; the selection alone recomputes only the benchmark group. Labels: `STALE_RELEASE`, `STALE_AS_OF`, `STALE_REPORTING_CURRENCY`, `STALE_MULTIPLE` besides the existing ones; the docstring now says what it
  does. A recomputation that is not over the release or as-of the caller says is refused (`ValueError`), never labelled current.
- **CP4F-8 (LOW).** `catalog_calendars` is REQUIRED (keyword-only) on `build_in_memory_market_data` and `DerivedReleaseView`, and `real_slice` passes an explicit empty mapping; 44 call sites in the tests say `catalog_calendars={}` where no benchmark catalog applies.
- **CP4F-9 (LOW).** `MetricBuilder.fault` no longer puts the unverified values in the cause note (it names the identity); the exit test scans causes and lineage of every refused metric for a fraction or a long decimal, and a lying TWR engine shows RD-1 and RS-1 faults carry none.
- **CP4F-10 (ruled in 1.6), Ruling 7.7 (1.6).** The default view falls back when the active return's portfolio leg `TWR(g_0, g_n]` is `INSUFFICIENT_DATA`, whatever its performance detail; the leg's state is recorded in the active return's lineage
  (`portfolio_leg_state`) and read from there. A leg that is not INSUFFICIENT never triggers it (benchmark-side and risk-free causes never do).
- **CP4F-11 (LOW).** Part 1 is in `test_postgres_cp4_golden` (78 of 78 through `risk_service` as `finweb_app`); part 3 is 95; the `selection_resolution` items now resolve the log the DATABASE stores (the runner's `selection_log`, with the stored sequence numbers mapped back).
- **Reviewer's notes.** `performance_service` publishes `pin_ledger_events`, `detect_suppressions`, `calendars_of_conventions` (the private names remain, so existing patches still work); `risk_service` uses only these.

**Proof.** Golden: part 1 78, part 2 61, part 3 95, 0 deferred, 0 mismatches, on the pure path and through PostgreSQL. Default suite 2290 tests OK (319 skipped, the DB tests); DB environment run twice, 2290 OK (2 skipped, E0); only `public` remains.
**Mutation testing** (copies only): 24 of 24 killed, among them M-C30 (zero capital not refused), M-C31 (refused window skips the benchmark causes and the risk-free probe), M-C32 (a disputed action withholds every later level), M-C34 (a disputed print treated as missing), M-C35 (the default view reads
details only), the not-yet-due fixing counted, the bound exact, an undeclared upstream independent, an undeclared second source admitted, the break ignored by the leg and by the statistics, a fault note carrying a number, `catalog_calendars` optional on either
path, and the status ignoring the release, the as-of or the currency.

**Decisions the contracts did not cover.**
1. How a dividend is identified ACROSS sources when neither the ex-date nor the pay date is shared: it is two single-source actions (both applied). A statement is "about the same action" by ex-date, pay date (a dividend) or ratio (a split); a different identity rule (record date, an issuer key) is the Quant's to give.
2. `additional_sources` as the way the catalog binds a second source (the series contract carries no return basis). BENCHMARKS.json's `entry_fields` should document it; no committed entry uses it.
3. For a disputed corporate action the chain breaks at EVERY ex-date the two statements name (so feed ex 01-08 against filing ex 01-09 breaks at both). A split's "same action" test includes an equal ratio on another date, which fails closed.
4. The restart of a broken chain is based at the first print on or after the break (`TR = P`); only ratios are ever used.
5. The refused-window probes use the request's `E` (the as-of) for the series and the risk-free lookup.

**Open.** Add `additional_sources` to `BENCHMARKS.json` `entry_fields` and the proxy-listing and priority rules before a second source or a proxy is admitted (main session). A resolution record (`RESOLVED_BY_EVIDENCE`) is still not built (the Quant's recommendation: with the first real-data increment that admits a
second price or corporate-action source). The HG3 evidence pack after CP5. A final re-check by the reviewer.

### 17.24 CP4 last round: the re-check's conditions, `risk/1.7` and `risk/1.8`, `cp4_golden/1.8-part3` (engineer; 2026-10-03; not yet reviewed)

**Targets.** `reviews/TECH_REVIEW.md` §42 (PASS_WITH_FINDINGS; three conditions); `risk/1.7` Ruling 5.5 (1.7) (the identity of a corporate action across sources) and `risk/1.8` Ruling 5.5 (1.8) (a foreign-currency dividend is converted), registry
`RISK_1.8_REGISTRY.json`, fixture `cp4_golden/1.8-part3` (101 items: R5-E7, R5-E8 and R5-E9 added). Engine id `risk/cp4h-0.1`; risk pins re-recorded (benchmark, engine, levels, registry); `ANALYTICS_PINS` re-recorded for `canonical` and `contracts`.
The target moved twice during the round (1.7, then 1.8, which supersedes the interim "refuse a foreign-currency dividend" order); the work is against 1.8.

**What changed.**
- **CP4F-3 residual, Ruling 5.5 (1.7).** `levels._same_action` / `_identify_actions`, in the ruled order: equal statements pair one-to-one (the record date is compared only when both state one); one side's own statements are deduplicated and never matched
  with each other; two unequal statements of different sides are ONE disputed action if they share a record date, an ex-date or (a dividend) a pay date, or if their ex-dates are at most 20 sessions apart (`LINKING_WINDOW_SESSIONS`; sessions of the
  entry's calendar, weekdays if it cannot count); further apart they are two single-source actions, both applied. An equal-ratio split on another date conflicts only inside the 20 sessions. R5-E7 (2 apart: SOURCE_CONFLICT) and R5-E8 (64 apart: both applied) pass.
- **CP4F-12, Ruling 5.5 (1.8).** `levels._convert_dividends`: declared in the price currency, as declared; the issuer's stated payment in the price currency, as stated; else declared x the ECB cross at the fixing of the EX-DATE (not the pay date).
  The fixing's freshness is the market-data Ruling 1.6 state (0: AVAILABLE; 1: AVAILABLE + STALE_DATA; 2 to 4: LIMITED + STALE_DATA; 5 or more: INSUFFICIENT_DATA + MISSING_FX_HISTORY, no rate used, the dividend not applied and the chain broken there) and attaches to
  EVERY ratio spanning the ex-date, through `Span` records on the `LevelBook` read by `BenchmarkLeg.parts_between` (no new detail name). The lineage of the print where a dividend lands records the declared amount and currency, the rate and fixing date
  or the issuer's statement, and the converted amount. The interim refusal and its `UNCONVERTIBLE` status are gone.
- **A market-data contract addition.** The issuer's stated payment needs a field: `CorporateActionObservation.paid_amount` (optional, positive, requires `paid_currency`, dividends only), read by the mock adapter, in the canonical form and the stored detail ONLY when stated
  (no digest recorded before moves). The contract had `paid_currency` and `issuer_fx_rate` but no amount, and an exact decimal cannot carry 0.46 / 3.30 as a rate; the Quant's ruling and fixture name `paid_amount`. It is a `market-data` contract change, flagged below.
- **CP4F-13.** The agreement bound is PER SOURCE (market-data Ruling 4.2): 0 when a source's declared precision (the most decimals it publishes) is at least the other's, half a unit of its last digit when it is the coarser. 100.12 against 100.13 and 187.44 against 187.43 are
  DISAGREEMENT; 4321.1234 against 4321.12 agree.
- **CP4F-14.** `groups._checked` checks a Current-mode result against the parent release `M` and the instant `t` the view declares (a type mismatch between a date and an instant is refused too).
- **The nit.** The same source listed twice in `additional_sources` (with two bases) is a `CatalogError`, in the parser and in the entry.

**Proof.** Golden 78 / 61 / 101, 0 deferred, 0 mismatches, pure path and through PostgreSQL (R5-E9 included: `paid_amount` survives the database round trip). Default suite 2302 OK (319 skipped); DB environment run twice, 2302 OK (2 skipped, E0); only `public` remains.
Two new exit scenarios (the fixture's R5-E9 request for all 12 metrics, and a constructed world with five CNY fixings missing at the ex-date). Mutation testing on copies: 13 of 13 killed, among them the dividend added unconverted (M-C38), the pay date's fixing (M-C39), the stated payment
ignored (M-C40), the staleness not attached (M-C41), the interim refusal (M-C42), the window of 0 and of infinity (M-C36, M-C37), the record date ignored, the bound always half a unit, one side matched with itself, and `_checked` ignoring the Current release or instant.
(An earlier set of 8 of 9 on the 1.7 work: the survivor, a duplicated source accepted by the catalog parser, is an equivalent mutant: the entry's constructor refuses it too.)

**Decisions the contracts did not cover.**
1. A source's DECLARED precision for the per-source bound is the most decimals it publishes on any level (a benchmark series carries no profile). A profile-declared precision would replace it.
2. `paid_amount` as a contract field (above); the Quant's text refers to it, `market-data` 7.1 does not define it.
3. Weekdays count the sessions of the 20-session window when the entry's calendar cannot (or none is named).
4. A dividend with no rate is NOT applied and breaks the chain; the break shares the segment mechanism of a dispute, and its cause is MISSING_FX_HISTORY, not SOURCE_CONFLICT.

**Open.** `market-data` Ruling 7.1 / `market-data/1.11` text for `paid_amount` (Quant); `BENCHMARKS.json` `entry_fields` for `additional_sources` (main session, from §17.23); a resolution record is still not built; the HG3 evidence pack after CP5; the reviewer's re-check.

### 17.25 CP4 conformance round: `risk/1.9`, `market-data/1.14`, `cp4_golden/1.9-part3` and `1.0-part4` (engineer; 2026-10-03; not yet reviewed)

**Targets.** `risk/1.9`, `market-data/1.14`, `cp4_golden/1.9-part3` (107 items), `cp4_golden/1.0-part4` (11 items, M-D1..M-D10), `RISK_1.9_REGISTRY.json`. `RISK_ENGINE_ID = risk/cp4i-0.1` with re-recorded source pins (engine, risk_free, benchmark, levels).

**What changed.**
1. Declared precision. The inference is removed. The catalog entry carries `official_decimals` (index level) and `precision_decimals` (the primary source); each `additional_sources[]` item carries its own `precision_decimals`. `BenchmarkEntry.source_precisions` holds the merged, sorted, serving-only map, validated as non-negative non-bool ints. Bound: delta = 0 if declared d >= official D, else half of 10^-d; levels agree iff |a-b| <= delta_A + delta_B. A multi-source series with an undeclared value raises `PrecisionUndeclared`, which `open_benchmark` maps to `BENCHMARK_SERIES_UNAVAILABLE`. A content check refuses a source whose levels show more decimals than declared. Priority is checked before precision.
2. `paid_amount` (market-data 1.14). Carried through contracts, canonical, ingest, mock adapter, reconciliation, manifest, market11, profiles and the PostgreSQL store. Paid currency must differ from the declared currency. Ruling 4.5 compares paid fields only when both sides state them.
3. CP4F-15. In `_identify_actions`, the payment that applies is decided by the stated payments across both sides (Ruling 4.5), not by statement order. FILING-only USD 0.43 is used (R5-E11); FEED 0.46 vs FILING 0.47 is a SOURCE_CONFLICT with BENCHMARK_SOURCE_CONFLICT (R5-E12). M-C46 is killed.
4. R10-S1: lineage `max_available_start: INCEPTION` present.
5. Kit loader: one mock adapter per source (a source shared by several benchmarks); JSON benchmark payloads for the distinct-payload rotation; part 4's per-file retrieval (list of dicts) alongside part 3's (list of strings).
6. Part 4, Current mode (Ruling 5.8): `risk_free_rates(..., instant=...)` looks up at the latest due publication; a not-yet-due publication is neither used nor missed; the benchmark side uses `_latest_due_fixing`; the default view falls back for beta (R41-V1) and the benchmark side refuses with no fallback (R42-V0). Checks compare lineage and detail names (M-D2, M-D3).
7. Registry: `risk_registry.json` byte-identical to `methodology/registry/RISK_1.9_REGISTRY.json`. The CP3 baseline was re-recorded only for the `market-data/1.14` id, verified by masked comparison.

**Proof.** Golden: part 3 107/107, part 4 11/11, on the pure path and through PostgreSQL as `finweb_app`. Default suite: Ran 2312, OK (skipped=320). DB-env suite, twice: Ran 2312, OK (skipped=2), both runs. Only `public` remains in `finweb_dev`. Mutations on `$TMPDIR` copies: M-C46 and the part-4 set killed (J1..J3 killed as extra engineer mutations).

**Decisions not covered by the contracts.** (a) Catalog fields for the declarations as above; (b) the priority error precedes the precision error; (c) the loader detects the part-4 format by `isinstance(files[0], dict)`; (d) engine id unchanged, pins carry the change.

**Open.** `BENCHMARKS.json` `entry_fields` must document `official_decimals`, `precision_decimals`, `additional_sources[].precision_decimals` (main session); the reviewer's re-check; HG3 pack after CP5.

## 18. CP5 diversification and drift implementation (2026-10-18)

**Status:** implemented for independent review, not accepted product truth. The full-NAV
capital universe is a **candidate**, pending owner decision OD-CP5-01. The earlier CP3
owner-reserved denominator question is not settled by an engineer, PM, fixture or test.
No commits, production dependencies, source admission, frontend or production endpoint
were added in this increment. Existing CP3/CP4 numerical paths are unchanged.

### 18.1 CP4 carry-in, CP4F-16

`test_cp4_golden.PartThreeTests` now asserts zero build exceptions, the exact declared
CNY `MISSING_VALUE` issue rows, all emitted/loaded file hashes, each source's file count,
and nonempty loaded observations. A regression restores the old CSV rotation on
duplicate JSON, observes `UNKNOWN_FORMAT`, and proves the new guard rejects it.
Engineer execution: 4 tests OK, 13.465 seconds. The root rerun and independent review
are recorded by their respective owners; this section is not that review.

### 18.2 Input and service architecture

`src/diversification/` separates immutable contracts, input assembly, exact core math,
certified radical presentation, registry, orchestration and drift. The service package
reads the portfolio reporting currency and a committed ledger pin through the existing
CP3/CP4 store boundary. It runs the existing F8-B policy/detection gate, refuses synthetic
market data by default, and accepts the existing explicit labelled test opt-in. No new
database schema or persistence format is necessary: metadata, coverage, owner choice,
accepted baselines and explicit user targets are immutable auditable arguments.

`compute_diversification_for_portfolio` obtains the ledger from the store and computes
concentration/exposure/correlation/cluster/covariance results. The corresponding Current
entry point uses CP3's date rule and an M_t derived release. `compute_analytics_for_portfolio`
composes the historical CP5 result and drift with CP4 beta, volatility, active return,
tracking error and maximum drawdown. Its CP4 call uses the exact ledger pin already used
by CP5, and pins the benchmark selection independently. Missing benchmark data affects
those dependent source metrics, not independent CP5 quantities. The aggregate result is
an `AnalyticsBundle` whose four immutable members retain their own manifests.

`MetadataSnapshot` supplies source/version/taxonomy/as-of and explicit country/sector
classification. Future-dated metadata is rejected. Asset class comes from explicit
instrument type; ETF sector stays UNKNOWN. No exchange, currency, name or ETF manager
business is treated as issuer geography/sector. Unknown classification is a LIMITED
partition, including its valued UNKNOWN category. Complete partitions are named in the
manifest so drift may use union categories with implicit zero only when justified.

`TotalReturnCoverage` supplies explicit dated, sourced evidence of complete security
action coverage. Absence of rows is never coverage evidence. Missing/unconfirmed
coverage or price-only coverage suppresses the affected historical leg. `history_for`
uses the unchanged CP4 RAW-close/dividend/split chain and cross-currency dividend rules;
cash/receivables use exact FX-only returns with zero native interest disclosed.

### 18.3 Candidate capital policy and state boundaries

`CapitalUniverseChoice` has choice, origin and evidence, all pinned in the manifest.
FULL_NAV is computable for an explicit USER_CONFIRMED record with evidence, or for an
explicit SYNTHETIC_CANDIDATE when the market observations/calendars, supplied metadata
and coverage records are demonstrably synthetic. The service creates neither record.
Missing or inapplicable choice suppresses concentration, exposure, weighted average
correlation, modeled volatility and contributions with CAPITAL_UNIVERSE_UNCONFIRMED;
the manifest exposes no candidate weights. Pairwise correlations and threshold graph
clusters are denominator-independent and remain available when their own inputs suffice.

CP3's complete exact portfolio value is the sole candidate denominator. Components
are grouped by listing or cash/receivable denomination across accounts. Zero-value
exclusions are recorded. A negative account component remains a refusal even when
netting within its bucket would hide it. Partial priced NAV is never a denominator.
Valuation state and same-severity reason priority propagate; policy, window, sample,
missing-input and degenerate-math refusals never carry a numerical alternative result.

### 18.4 Exact statistics and reproducibility

All amounts, weights, returns, covariances and contribution shares use Fraction.
Square-root outputs use the existing CP4 integer-certified root rounding. Weighted
average correlation retains exact signed-radical terms; rational interval sums certify
the final 12-place rounding, with PRESENTATION_TIE if the prescribed tie rule requires it.
Threshold edges compare exact squared cross moments, including equality; connected
components use canonical lexical order. Constant legs are allowed in covariance; an
undefined pair suppresses the complete average/cluster result rather than being dropped.
Negative risk contributions are retained. Zero model variance yields zero modeled
volatility but no fabricated contribution share/component allocation.

The bundled registry is byte-identical to the Quant's `DIVERSIFICATION_1.0_REGISTRY.json`;
the engine reads its observation thresholds. Historical legs use the CP4 weekday/Friday/
month-end grid. Fixed windows never trim or delete periods. An explicit MAX_AVAILABLE
records its common suffix selection and discarded boundary; a recent listing cannot
silently shorten a fixed request. Every manifest includes the CP3 valuation manifest,
ledger/release/identity digests, explicit metadata/coverage/policy inputs and hashes,
requested/effective window/grid, capital buckets, permitted weights, exact historical
observations and all consumed historical files. `reproduce_diversification` reruns the
question and compares every manifest field in both directions; a missing expected
result digest reports RESULT_NOT_COMPARED, never REPRODUCED.

Drift is implemented by a distinct delegated engineer in `diversification/drift.py`.
It derives compatibility from pinned CP5/CP4 source manifests, compares exact values
or exact radical representations, validates immutable accepted baseline evidence and
explicit user target provenance, and seals/reproduces its own source-bearing manifest.
No engine action accepts a baseline or invents a preference, materiality or warning.

### 18.5 Validation and remaining review boundaries

Engineer targeted command:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_diversification_golden tests.product.test_diversification_integration tests.product.test_diversification_drift tests.product.test_postgres_diversification
```

Observed before review freeze: **56 tests OK, 5 skipped, 9.504 seconds**. The five skips
are the explicit database opt-ins. The root had independently run the initial four
database methods as finweb_app against an isolated temporary PostgreSQL 17 cluster:
4 passed; the fifth complete-service composition method was then added for its rerun.
No database server was started or modified by the engineer.

The test inventory explicitly assigns all 34 Quant fixture ids in issue 1.1: six snapshots,
16 historical cases, nine drift/target cases, two capital-policy refusals and FX1.
All 12 threshold boundaries are exercised. Actual integration additionally covers
CP4's independently expected single-listing volatility, foreign cash FX volatility,
missing cost basis, missing FX/full-NAV refusal, recent listing/fixed-window refusal,
metadata lookahead/UNKNOWN, total-return coverage refusal, unpaid ledger receivable
counted once, source FX cross term with opposite native/reporting signs, Current M_t,
hash seeds, ambient Decimal context, input order, reproduction and missing file citations.

Open work belongs to the orchestration/review record: independent adversarial review,
root full regression and database reruns, the additive CP3 registry reader and actual
HG3 evidence exporter assigned to the other engineer, then the human HG3 decision.
Real sources, full-NAV owner confirmation and source-rights decisions remain open.

**Review-preparation follow-up:** `cp5_golden/1.1-part1` adds H16 without changing any
earlier case. H16 separates the correct exact-radical average 0.565685424949 from the
pre-rounded-pair mutation 0.565685424950; both paths were actually executed. The
bundle's default benchmark argument now loads the committed admitted catalog so
an absent selection produces CP4's MISSING_BENCHMARK result instead of a configuration
exception. Its database test asserts that refusal alongside available independent
volatility. Latest engineer targeted run: **57 tests OK, 5 database skips, 9.230 seconds**.

### 18.6 Independent §47 repair round (CP5I-1 through CP5I-6)

The independent implementation review returned HOLD. All six counterexamples were
encoded first in `test_diversification_review.py` and run against the reviewed code:
**6 tests, 5 assertion failures and 1 missing-attribute error, 0.597 seconds**. The
separate drift engineer also ran red positive/negative tie and policy-scope cases.
No Quant fixture or CP3/CP4 numerical engine was changed during this repair.

- **I-1:** capital choices now carry `decision_id`, `scope_kind`, `product_id`,
  `portfolio_id`, and `account_id`. `GLOBAL_PRODUCT` requires the explicit product
  identity; `PORTFOLIO` matches only the exact whole-portfolio request; `ACCOUNT`
  matches both portfolio and account. Missing scope/id/evidence or mismatched scope
  refuses the capital-dependent outputs. There is no implicit global scope or
  portfolio-to-account inheritance. Synthetic candidates retain their separate
  provenance and all-synthetic requirement. Drift validates and signs the same record.
- **I-2:** fixed/custom constituent-history windows retain the requested base even
  when the portfolio/acquisition is younger. The CP3 date-grid and positive-window
  validation are reused without its actual-TWR inception floor. SINCE_INCEPTION and
  MAX_AVAILABLE retain the known ledger/snapshot inception; the manifest pins this
  floor and, for an explicit common-suffix trim, the last refused boundary and causes.
- **I-3:** the result adds immutable `exposure_decompositions`. Each complete map has
  exact total 1, displayed total 1, category-sorted exact values, unchanged independent
  scalar presentations, and separately apportioned display values. The existing
  performance largest-remainder routine supplies category-key tie order. Three equal
  categories therefore display 0.333333333334, 0.333333333333, 0.333333333333. This
  field participates in the result digest. Drift continues to consume exact values.
- **I-4:** radical terms with rationally equivalent radicands are combined before
  bracketing. A proven exact tie or a certified width-below-1e-40 boundary carries the
  prescribed half-away value with original state and exact/radical witness. Lineage
  records PRESENTATION_TIE, boundary, bounds and exact/interval proof. It is no longer
  fabricated missing data. Positive and negative half-quantum cases and H16 run.
- **I-5:** cluster refusals combine pair inputs through the existing same-severity
  reason-priority function. A lower-severity stale pair cannot replace a missing-price
  refusal; the regression also renames/reorders the buckets.
- **I-6:** reproduction compares key presence and canonical typed values, including
  nested objects. Missing/added null fields, Boolean-versus-integer substitution and
  invalid structures return INPUT_MISMATCH. Unsupported numeric types are not coerced.

The CP5 implementation id is now **`diversification/cp5-0.2`**, distinguishing manifests
from the earlier unaccepted draft. Financial convention/registry ids remain unchanged
because the repairs implement their existing rules. CP3/CP4 manifests and frozen
numeric fixtures were not rewritten.

Latest targeted command adds `test_diversification_review` and `test_hg3_evidence` to
the prior CP5 group: **82 tests OK, 6 database skips, 10.150 seconds**. The sixth DB
method verifies policy applicability against actual database portfolio/account scope.
Full regression, serialized database execution, evidence regeneration and independent
re-review are root-owned next steps; this section does not claim those have passed.
