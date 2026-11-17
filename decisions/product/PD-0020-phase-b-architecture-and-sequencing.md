# PD-0020 — Phase B architecture and sequencing: OQ-02 is closed, P0 opens, CP1 is first

**Status:** accepted
**Date:** 2026-09-22
**Decided by:** the designated **human product owner**, in a direct instruction to `pm-01`.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-e5`. **Recorded, not decided.**
**Decision package:** `reviews/gates/PHASE_B0A_DECISION_PACKAGE.md` (Phase B0a)
**Closes:** **OQ-02** (`specs/FEATURE_PRD.md` §9) — technology stack and persistence.
**Supersedes:** `PD-0011` §6 second bullet — *"It does not authorize any Priority A–E work"* —
**on authorization only**, to the extent necessary to authorize the Phase-B work stated below.
**Reopens:** nothing. **Amends:** nothing else.

> **Recorded, not decided.** Nothing in this document was decided by an agent. The decisions
> in §1–§10 are the human product owner's, given in their own instruction, and are
> transcribed here by a PM that did not make them. Where this record reasons, it is marked as
> the PM's reasoning and carries no authority.

> **This record does not authorize implementation beyond the sequence and preconditions
> stated in §12.** It is not a general licence to build.

---

## 1. OQ-02 is CLOSED

**OQ-02 — *"Technology stack and persistence — chosen by the engineer in T2/T13, or reserved
to the human?"*** — owner `human product owner`, needed by `HG1`, disposition *"Engineer
proposes; HG1 decides"* — is **resolved by the human product owner**.

This is the decision the Phase B0a audit found had never been made. PD-0017 approved HG1 and
satisfied the PRD §38.4 hard stop; it did not decide OQ-02, and no record between PD-0005 and
PD-0019 did either. **This record is that decision.**

`specs/FEATURE_PRD.md` §9's OQ-02 row may now be marked CLOSED, citing this record, in the
same manner as OQ-01 (PD-0006) and OQ-03 (PD-0005). **That edit is not made here** — it is a
`specs/` change and belongs to the bounded reconciliation in B0b, not to this decision record.

### 1.1 What was decided, per axis

| Axis | Decision |
|---|---|
| **Backend / runtime** | **Python-first** |
| **Frontend / application class** | **TypeScript SPA** — architectural class only |
| **Frontend framework** | **NOT DECIDED — reserved to the human** (§3) |
| **Persistence** | **PostgreSQL-class relational** |
| **Ledger** | **First-class append-only event domain model** |
| **Topology** | **Modular monolith** |
| **Development environment** | **(b) human-provisioned**, conditional on E0 (§5, §6) |

---

## 2. Backend, persistence, ledger and topology

### 2.1 Python-first backend

**Python is the authoritative backend / domain / financial-computation runtime.**

Grounds accepted by the owner: deterministic financial computation; native
`decimal.Decimal`; strong quantitative and data ecosystem; alignment with future
`quant_analyst` work; golden fixtures live in the same computational ecosystem as the engine;
and `src/product_contract/` **may potentially be reused rather than automatically ported**.

**This does not authorize a Python-rendered frontend.**

**[PM note]** "May potentially be reused" is the owner's wording and is deliberately not a
guarantee. Whether the existing 429 lines are reused as-is, refactored, or replaced is an
engineering judgment for B0b against the CP1 architecture — not a foregone conclusion of the
language choice.

### 2.2 TypeScript SPA — architectural class

The production frontend architectural class is a **TypeScript SPA**, suitable for: the
approved four-surface IA; bilingual EN / zh-CN behaviour; the Quick → Simple → Professional
depth ladder; evidence / Proof Packet interaction; Scenario Lab; and future interactive
portfolio workflows.

### 2.3 PostgreSQL-class relational persistence

**PostgreSQL-class relational persistence is the production direction.**

Grounds accepted by the owner: exact numeric support; constraints; auditability; mature
migration tooling; temporal / event-reconstruction needs; suitability for the approved
domain/ledger model.

> **This decision is independent of the prior Tech Plan's PostgreSQL proposal.** It is the
> owner's decision on the owner's stated grounds. `implementation/FEATURE_TECH_PLAN.md` T2
> remains what it always was — a proposal — and is not retroactively converted into the
> decision by agreeing with it.

### 2.4 First-class append-only ledger / event domain model

The CP1 ledger is a **first-class append-only event domain model**. Default architecture:

```
PostgreSQL
    ↓
append-only ledger/event tables
    ↓
deterministic point-in-time reconstruction
```

**Mutable current-position rows must not become the sole system of record.**

**This does not authorize:** Kafka; a dedicated event-store product; distributed event
sourcing; service-per-domain architecture.

**[PM note]** This is the decision that most directly serves CP1's exit criterion —
*"historical positions can be deterministically reconstructed"* — by making reconstruction a
fold over recorded events rather than an inference from mutable state.

### 2.5 Modular monolith

Use a **modular monolith** initially. Maintain clean internal module boundaries. Keep **AI
orchestration behind a hard boundary** so later isolation remains inexpensive when CP9 makes
it useful.

**Do not introduce** microservices, sharding, distributed transactions, dedicated queues, or
a time-series database **without evidence**. At the ~500-holding V1 target (NFR-007), scale
does not justify those costs.

---

## 3. The frontend framework is NOT decided

# THE SPECIFIC FRONTEND FRAMEWORK IS NOT DECIDED.

- B0b **must** compare a bounded set of mature choices and return a decision package.
- **The PM may not silently treat the framework as an implementation detail.**
- **Before production frontend scaffolding, the human product owner must explicitly approve
  the framework or explicitly delegate that choice.**
- The PM has **no authority to close this silently**.

Any B0b section addressing it ends exactly with
`FRONTEND FRAMEWORK — AWAITING HUMAN DECISION`.

---

## 4. Development environment — H1b

**Decision: (b) human-provisioned development environment, harness retained for governance
and review.**

> The current sandbox **must not** choose the production persistence architecture merely
> because PostgreSQL or Docker is absent today.

**This option is CONDITIONAL on E0.** The repository does not yet prove that the governed
Engineer runtime can connect to a human-provisioned PostgreSQL instance. **Do not assume it
can.**

---

## 5. E0 — Engineer → PostgreSQL connectivity preflight

Before persistence-backed CP1 product implementation begins, **E0 must run**. The question is
specifically:

> Can the **actual governed Engineer runtime used for CP1** reach the human-provisioned
> PostgreSQL instance?

# E0 PASS IS A HARD PRECONDITION FOR PERSISTENCE-BACKED CP1 ENGINEERING.

### 5.1 What E0 tests

Both routes: **(1) PostgreSQL Unix-domain socket; (2) loopback TCP.**

E0 must **distinguish**, not conflate: successful connection · connection permitted but no
listener/server · socket/path absent · policy/sandbox denial · required tool unavailable ·
other failure.

**E0's result must not be inferred** from the PM environment, the host OS, another sandbox,
another agent, or generic capability metadata. Only the governed Engineer runtime's own
observation counts.

### 5.2 Command form — the inline probe is not lawful

`guard_bash` denies inline interpreter forms (`python3 -c`, `node -e`, and equivalents).

# DO NOT USE AN INLINE INTERPRETER FOR E0.

The probe **must be authored as a file**. Default lawful form: a bounded Python unit-test
file under `tests/product/`, executed via the allowlisted `python3 -m unittest` route —
conceptually:

```
python3 -m unittest discover -s tests/product -p 'test_postgres_connectivity_preflight.py'
```

**B0b must verify the exact lawful command against the live allowlist before execution.**

> **Do not route around a denial by changing shells or interpreters.** A denial is a
> boundary, not an obstacle (`CLAUDE.md` Security).

### 5.3 E0 should not require PostgreSQL client tooling

E0's purpose is **transport reachability from the governed Engineer environment**, not
database-schema validation. It should distinguish outcomes using standard runtime facilities
where possible, rather than requiring `psql`, a PostgreSQL Python driver, or product
dependency installation **solely to establish whether the sandbox permits the connection**.

For both routes, capture the concrete OS/runtime outcome well enough to distinguish
permitted connection · refused / no listener · missing socket · denied operation.
**B0b will define the exact test. Do not expose credentials during E0.**

### 5.4 E0 write scope

The E0 Engineer may write **only** what the bounded connectivity test and its normal lawful
task evidence require. Expected product-test locus: **`tests/product/`**.

**E0 may NOT create:** domain models · database schema · migrations · application code ·
production dependencies · frontend files.

**Retention is an open question, to be answered deliberately.** B0b must recommend whether
the preflight remains a durable diagnostic test. If retained, it must be designed so
**ordinary offline test runs do not fail merely because a developer has not explicitly
requested or provisioned the PostgreSQL preflight**. *Do not decide that by accident during
E0.*

### 5.5 E0 outcomes

| Outcome | Consequence |
|---|---|
| **Either lawful route succeeds** | Option (b) is operationally feasible. Proceed under the approved PostgreSQL architecture. |
| **Route permitted, but no server/listener** | A **provisioning** result, **not** proof of a harness block. Correct provisioning; rerun the bounded probe lawfully. |
| **Both legitimate routes denied by harness policy** | **STOP and return to the human.** |

If both routes are denied, **do not**: silently substitute SQLite · weaken the production
persistence decision · run PostgreSQL outside the governed workflow while claiming Engineer
validation · bypass the sandbox.

The required path then becomes **option (c) — explicit provisioning / policy change**, and
only at that point does the environment/policy problem become a genuine Harness Architect
matter. **No Architect work is authorized merely because E0 has not yet run** (§11).

---

## 6. E0's task representation — and the state rule that governs it

E0 uses **a bounded first `implement` increment**, **not** an advisory Engineer engagement.

**Reason (owner's):** the Engineer must author a probe file under `tests/product/`; the file
is a repository artifact; full task-keyed provenance is wanted; and advisory execution would
leave the write without normal shard / execution-record / handoff provenance.

**[PM note]** This is consistent with ADR-0030 as recorded in `CLAUDE.md`: an advisory worker
gets **no shard, no execution record, no handoff**, because all three are task-keyed. A
write that must be attributable therefore cannot be advisory.

### 6.1 Sequence (after B0b approval)

1. dispatch a fresh lawful Engineer bound to `implement`;
2. transition `implement` into its lawful active / in-progress state for the first bounded
   increment;
3. permit writes only to the approved E0 test/evidence scope (§5.4);
4. run the allowlisted unit-test probe **from that Engineer runtime**;
5. record the E0 execution **truthfully**;
6. stop the E0 worker after its bounded probe is complete;
7. continue CP1 through later bounded Engineer increments under the same **still-active**
   `implement` task.

### 6.2 CRITICAL STATE RULE

# The E0 increment must NOT transition `implement` to `complete`.

`implement` remains **`in_progress`** through E0 and throughout subsequent CP1
implementation, until the actual implementation checkpoint is genuinely complete.

**Why:**

```
implement complete
        ↓
design_review becomes ready
technical_review becomes ready
        ↓
project appears reviewable
```

That would falsely signal that implementation is finished **even though CP1 has not begun**.

Therefore: E0 is a bounded execution increment *inside* `implement`; it is **not** `implement`
completion; **it earns no CP1 completion credit**; and **it must not trigger downstream review
readiness**.

Use the execution-record lifecycle that truthfully represents an unfinished task. Where
supported, record the bounded E0 execution with execution status **`started`** rather than
falsely recording the whole task as complete.

> **Do not fabricate a completed task merely because the individual Engineer finished its E0
> assignment.**

### 6.3 Worker stop behaviour

If the E0 Engineer stops while the `implement` shard remains `in_progress`, **preserve the
normal governed behaviour**. The stop may be recorded as the known unresolved /
unconcluded-task gap under the existing **ADR-0033 P2** lifecycle.

**[PM note — verified against ADR-0033 P2.]** That ADR exists for exactly this ordering:
*"reopen task → bind a worker with `--assigned-task-id` → shard `in_progress` → worker does
the work → worker stops"*. The stop is **allowed** and `record_unconcluded_task_stop()` writes
a durable gap naming the exact worker, its task, the shard status and revision at stop, and
its parent. `validate_runtime --mode conformance` reports it **until the parent concludes the
shard**, and reconciliation is **derived from the shard, never from the ledger's own status**
— so the gap cannot be closed by editing the file that records it.

# Do not "fix" that gap by completing `implement`.

It reconciles only when the implementation task genuinely reaches completion later.

**B0b must describe the exact lawful recording sequence** so E0 evidence remains attributable
without producing a false DAG transition.

---

## 7. Bounded supersession of PD-0011 §6

`PD-0011` §6 states, as its second bullet:

> *"It does not authorize any Priority A–E work."*

Nothing in `PD-0017` or `PD-0019` lifted that withholding. **This decision now does so, in a
bounded manner:**

# PD-0020 supersedes PD-0011 §6 on authorization only, to the extent necessary to authorize the Phase-B work stated in PD-0020.

**This decision authorizes exactly four things:**

1. **Priority A work through P0**;
2. **Phase B0b planning**;
3. **the bounded E0 precondition increment, after B0b approval**;
4. **CP1-first production engineering, after B0b approval and applicable preconditions**.

**This is not blanket authorization to execute Priorities B–E immediately.** Those remain
subject to checkpoint dependencies, human decisions, and later authorization.

### 7.1 PD-0011's substantive requirements remain in force

The supersession is **on authorization only**. Everything else in `PD-0011` stands
unamended — in particular:

- the **C+B accepted design direction** and the **four-surface IA**;
- the **dependency order**: market/reference data + security resolution ↓ cross-border
  deterministic calculation spine ↓ Proof Packets / evidence ↓ real AI integration;
- *"Do not interpret Priorities A–E as five unrelated parallel feature projects."*;
- **Priority A's provider-reality standard**: *"Do not merely demonstrate that an API
  responds"* — provider response → normalized internal object → provenance/source →
  timestamp/freshness → deterministic downstream consumption, with provider limitations
  **evaluated explicitly rather than hidden behind adapters**, and a real primary/fallback
  provider decision emerging;
- **Priority C's** required source-image retention / redaction-access / deletion policy;
- **Priority D's** fixed historical valuation date/window, the **golden cross-border portfolio
  fixture** as a permanent regression asset, and *"Do not certify the calculation engine
  merely because its own implementation tests pass"*;
- **Priority E's** adversarial *"Which stock should I sell?"* advisory-boundary test;
- the **review-budget** direction (data-source correctness, instrument identity, cross-border
  FX and corporate actions, calculation reproducibility, OCR uncertainty, AI
  deterministic-boundary enforcement);
- **ETFs are V1; mutual funds require a separate product decision** and must not be silently
  added.

**`PD-0011`, `PD-0017` and `PD-0019` are not rewritten.** This record changes one clause of
one section of `PD-0011`, on authorization, and nothing else.

---

## 8. Sequencing — CP1-first does not discard PD-0011's dependency logic

**Decision: HYBRID / PARALLEL.**

```
                   ┌── P0 / Priority A vendor + commercial work
                   │
PD-0020 ───────────┤
                   │
                   └── B0b → E0 → CP1
                                      ↓
                                     CP2
                                      ↓
                         analytics → evidence → AI
```

**This reconciles the two authorities rather than rewriting either historical source.**

**CP1 builds the identity/domain substrate.** CP1's **Instrument / Issuer / Listing** model
provides the domain substrate that later security resolution requires: security resolution
must resolve *into* a stable identity model. CP1-first engineering is therefore **compatible**
with PD-0011's requirement that market/reference data and security resolution precede
downstream deterministic analytics.

**Priority A begins now**, in parallel, through P0 and later CP2 work. **Nothing in Priority
A is dropped.**

**CP1 is the first production engineering checkpoint**, beginning after: this record is
durably committed; B0b is approved; E0 passes where required; and CP1-critical identity
decisions are resolved (§10). It does **not** wait for OQ-04. The HG1 gate is already cleared
(PD-0017 §3) and OQ-02 is now resolved (§1).

**CP2 follows the PRD spine** as the market-data normalization checkpoint. Its mock/replay
substitutability requirement is implemented according to **the PRD's own exit criterion** —
*"same internal analytics contract can consume test data from more than one adapter/mock
without business-logic change."* Live-provider work remains gated by P0 / OQ-04 where
applicable.

---

## 9. P0 is authorized — OQ-04 remains OPEN

# P0 — MARKET-DATA PROVISIONING / COMMERCIAL GATE is authorized to begin immediately as a human-owned parallel workstream.

**OQ-04 remains OPEN.** It must close before CP2 exits. **It does not block CP1.**

P0 evaluates: realistic providers · U.S. coverage · Hong Kong coverage · Mainland-China
coverage · security-resolution / FIGI-MIC support · prices · FX · historical data · corporate
actions · rate limits · commercial cost · licensing · redistribution / display rights ·
trial / account availability · secret provisioning · lawful live-execution mechanism.

> **Do not purchase or bind a production vendor merely from this authorization.**

---

## 10. Deferred rulings and one unresolved CP1-critical item

### 10.1 H4 — initial live market scope: **DEFER**

Do not prematurely narrow CP1 or the normalized CP2 contracts to one market. P0 evaluates
U.S., Hong Kong and Mainland China. A recommendation for initial live CP2 binding returns
later.

### 10.2 H5 — commercial / deployment intent: **DEFER final ruling**

P0 must nevertheless model **development/internal**, **private beta**, and
**public/commercial display**, because licensing and display rights may differ. **Do not
finalize a vendor or licence until deployment intent is sufficiently explicit.**

### 10.3 H6 — live-data execution model: **DEFER to P0 / CP2**

**Do not change harness network policy now.** CP2's replay/mock path remains
provider-independent. A lawful live-data execution recommendation returns later, and must not
expose credentials to model context, bypass external-action policy, or use browser access as
arbitrary vendor egress.

### 10.4 FIGI / canonical identity fallback — **UNRESOLVED and CP1-CRITICAL**

The canonical identity fallback where FIGI is unavailable **remains unresolved** and is
**CP1-critical**. **Do not silently choose it inside a schema.**

B0b must determine: existing product law · where FIGI is unavailable or unsuitable · what
durable internal identity exists independently of vendor coverage · how MIC/listing identity
participates · whether this is an implementation detail or requires a human ruling ·
migration consequences if chosen incorrectly.

If no approved source resolves it, B0b returns bounded alternatives, a PM recommendation, and
`AWAITING HUMAN DECISION`.

# No irreversible CP1 identity schema work may begin while this remains ambiguous.

---

## 11. Harness Architect boundary

**No Harness Architect work is authorized merely because E0 remains untested.**

If E0 later proves that **both** legitimate PostgreSQL routes are denied by harness policy:
(1) stop; (2) preserve evidence; (3) return for human authorization; (4) identify the
required policy/provisioning change; (5) engage the Harness Architect **only if authorized**.

# Do not work around the harness.

---

## 12. What this decision does NOT do

- It does **not** authorize implementation beyond the sequence and preconditions in §7 —
  specifically, no product implementation may begin during B0b.
- It does **not** authorize Priorities B–E for immediate execution.
- It does **not** decide the frontend framework (§3).
- It does **not** close OQ-04 (§9), H4, H5 or H6 (§10.1–§10.3).
- It does **not** resolve the FIGI / canonical-identity fallback (§10.4).
- It does **not** rewrite, amend or reopen `PD-0011` beyond §6's authorization clause, nor
  `PD-0017` or `PD-0019` at all.
- It does **not** reopen HG1, Post-HG1 Checkpoint A, or any product contract — not the
  metric-state rules, the deterministic boundary, the Proof Packet architecture, scenario
  isolation, freshness, or AI grounding.
- It does **not** add mutual funds to V1.
- It does **not** change harness network policy, the sandbox, or any security policy.
- It does **not** convert `implementation/FEATURE_TECH_PLAN.md` into approved architecture.
  That document remains a proposal; **this record is the decision**, on the owner's own
  stated grounds.
- It does **not** complete, advance, or otherwise mutate any task shard. `implement` remains
  `ready` rev 32 until the lawful E0 increment begins after B0b approval.

## 13. What is not evidence for this decision

Recorded because PRD §38.1 requires it: none of the following was treated as approval and
none of it approved anything — the Phase B0a package's PM recommendation, the passing
validation suite, the prior tech plan's T2 proposals, the absence of objection, or elapsed
time. Those are inputs the owner weighed. **The decisions in §1–§10 are the owner's**, and are
recorded here by an agent that did not make them.
