# PD-0021 — CP1 entry: internal canonical identity, staged provisioning, and the E0 preconditions

**Status:** accepted
**Date:** 2026-09-22
**Decided by:** the designated **human product owner**, in a direct instruction to `pm-01`.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-e5`. **Recorded, not decided.**
**Planning basis:** `reviews/gates/PHASE_B0B_IMPLEMENTATION_PLAN.md` (Phase B0b)
**Builds on:** `PD-0020` @ `4c0fb347ad42abd6872ce4108c1426a57eb3be6c`
**Closes:** R1 (canonical identity fallback), R2 (development environment), R3 (E0 approval).
**Defers:** R4 (frontend framework), R6 (commercial/deployment intent).
**Reopens:** nothing. **Supersedes:** nothing. **`PD-0020` is not rewritten.**

> **Recorded, not decided.** The rulings in §1–§10 are the human product owner's. Where this
> record reasons or verifies, it is marked **[PM]** and carries no decision authority.

---

## 1. R1 — Canonical identity fallback: **OPTION A**

**Immutable internal database identities are the canonical persistence and join keys.**
FIGI, MIC, ticker and other market/vendor identifiers are **external identity and resolution
attributes**.

### 1.1 Required identity model

Distinct durable internal identities for **Issuer**, **Instrument**, and **Listing**.

Ledger events reference the internal **`listing_id`** — **never** ticker, FIGI, a FIGI+MIC
composite, or any vendor-specific identifier.

Internal IDs must remain stable when: FIGI is unavailable · FIGI arrives later · FIGI
changes · vendor mappings disagree · a ticker changes · an instrument or listing is
delisted · a provider is replaced.

### 1.2 FIGI + MIC remain authoritative resolution primitives

This ruling **does not weaken** PRD §10.1's *"use FIGI + MIC as canonical identity primitives
where available."* That requirement is interpreted as applying to **real-world
identification, matching, security resolution, normalization, and evidence/provenance** —
rather than requiring FIGI/MIC to be physical database primary keys.

```
internal immutable IDs            FIGI + MIC + other identifiers
        ↓                                     ↓
durable ledger / relational joins   external identity / resolution / evidence
```

**[PM] This reading is supported by the PRD's own text, not only by convenience.** §10.2
lists **`instrument ID` as a required field distinct from `FIGI where available`**, and
§10.1 forbids only the **ticker** as database primary key. An internal surrogate key with
FIGI/MIC as resolution attributes is consistent with both.

### 1.3 Option C is not adopted

**Do not** add a deterministic natural-key uniqueness scheme merely to make internal UUIDs
less opaque. It may later be useful as **additive hardening**. It is **not part of this
ruling** and must not be introduced silently.

### 1.4 The accepted invariant — the decisive reason

> A correction to external identity must be capable of becoming **an identity/resolution
> attribute update**, rather than **a migration of every historical ledger reference**.

---

## 2. R2 — Development environment: approved, with staged parallel provisioning

**A human-provisioned native development environment.** Approved production direction:
**Python 3.12** · **`uv`** · **PostgreSQL 16 or 17** · PostgreSQL-class persistence ·
**no Docker requirement for CP1** · frontend toolchain later.

Provisioning follows actual dependencies rather than document order.

### 2.1 PostgreSQL provisioning begins now, in parallel

Human PostgreSQL provisioning has **no dependency** on PD-0021 being committed, on
design-contract reconciliation, or on technical-plan reconciliation.

# BEGIN NATIVE POSTGRESQL PROVISIONING IN PARALLEL NOW.

```
                       ┌────────────► human provisions PostgreSQL
                       │
record PD-0021 ────────┤
                       │
                       └────────────► bounded planning reconciliation
                                          │
                       both complete ─────┘
                                          ↓
                                         E0  →  CP1
```

**Do not serialize PostgreSQL installation behind a documentation round.** It mutates no
repository authority.

### 2.2 Required before E0 — and only this

Native PostgreSQL 16 or 17 · the service running · a **known Unix-domain socket path** · a
**known loopback TCP host/port**.

**Not required merely for E0:** Docker · Node · a frontend framework · SQLAlchemy · Alembic ·
a PostgreSQL Python driver · any production dependency installation.

**E0 is a standard-library transport probe.**

### 2.3 Required before CP1 product code

Python 3.12 · `uv` · the approved dependency/lockfile setup · PostgreSQL · the approved
backend test/dependency tooling.

> **Do not allow the host's current Python 3.9.6 to become the product runtime by accident.**

### 2.4 Node and frontend tooling are **not** a CP1 blocker

# DEFER NODE / FRONTEND PROVISIONING.

They do not block E0, CP1-A, CP1-B, CP1-C or CP1-D. Provision them before production
frontend/application work. **Node absence must not appear in the CP1 critical path.**

---

## 3. R3 — E0 connectivity preflight: **APPROVED**

E0 is approved exactly as a **bounded first `implement` increment**. Its sole purpose:

> determine whether the actual governed Engineer runtime can reach the human-provisioned
> PostgreSQL endpoint.

### 3.1 Command form

A file-based test, e.g. `tests/product/test_postgres_connectivity_preflight.py`, invoked
through the lawful `python3 -m unittest` route.

**Do not use** `python3 -c`, `node -e`, or any shell/interpreter workaround.

**[PM] Verified against the live policy:** `.claude/settings.json` `permissions.allow`
contains `Bash(python3 -m unittest:*)`, and the `discover` form already runs in this
repository (`Ran 50 tests … OK`). `guard_bash` denies inline interpreters, redirection and
`rm`/`mv`/`cp`/`mkdir`; the approved command contains none.

### 3.2 Transport checks

Test **independently**: (1) Unix-domain socket; (2) loopback TCP. Record enough **raw**
evidence to classify each as `TRANSPORT_REACHABLE` · `PERMITTED_NO_LISTENER` ·
`SOCKET_MISSING` · `POLICY_DENIED` · `RUNTIME_ERROR` · timeout/other.

**Do not send** credentials, PostgreSQL startup packets, or application queries.

### 3.3 The E0 Engineer registration must be **complete**

E0 is the first new production-phase worker registration. **Do not repeat the unrecoverable
provenance omission seen on `designer-35`.**

Expected identity: **`engineer-06`**, if still free at dispatch. Otherwise the next lawful
unused Engineer identity.

**Required registration fields:**

| Field | Value |
|---|---|
| `role_id` | `engineer` |
| runtime type | `delegated_subagent` |
| `parent_worker_id` | `pm-01` |
| `agent_id` | the **witnessed** id from the actual `SubagentStart` observation |
| `assigned_task_id` | `implement` |
| engagement capability | `filesystem` |
| engagement capability | `shell` |
| `agent_definition` | **`.claude/agents/engineer.md`** |
| `note` | substantive description of the bounded E0 assignment |

plus the normal lawful worker/role/runtime/parent fields the live helper requires.

> **Do not invent the `agent_id`.** Witness it from the actual spawned worker first.

# `--agent-definition` IS LOAD-BEARING PROVENANCE

**Do not omit `--agent-definition .claude/agents/engineer.md`.**

The `designer-35` record demonstrates why: an omitted `agent_definition` becomes `null`;
`rebind` cannot later populate that field; registration refuses rebinding the worker's
witnessed `agent_id`; therefore the omission **cannot lawfully be back-filled**; and it
leaves a permanent provenance disclosure and validator warning.

**[PM] Verified.** `validate_runtime --mode readiness` currently emits
*"WARN: delegated subagent `designer-35` has no `agent_definition` recorded."*
`register_worker.py rebind` accepts only `--runtime-identity`, `--hook-session-id` and
`--hook-boundary` — **there is no `--agent-definition` on rebind**, and no route to add
`agent_id`, `assigned_task_id` or an engagement after the fact. Registration is one-shot and
its only window is **while the worker runs**.

The first Phase-B Engineer registration establishes the correct pattern for every later CP1
increment.

**Before allowing the worker to write**, verify its registry record carries: correct worker
id · `role_id = engineer` · correct parent · witnessed agent id · `assigned_task_id =
implement` · both engagement capabilities · `.claude/agents/engineer.md`.

**If registration is incomplete, or the registration window is missed:** do not backfill · do
not improvise · **stop the attempted round truthfully** · record any required unresolved gap ·
**redispatch a fresh Engineer lawfully**.

### 3.4 E0 proves transport only

# E0 PASS = TRANSPORT REACHABILITY.

It does **not** establish PostgreSQL protocol success · authentication · server
identity/version · role permissions · schema access · transaction behaviour · migrations ·
`Decimal`/`NUMERIC` correctness.

> **Do not write "PostgreSQL works" merely because E0 passes.**

### 3.5 E0b is separately approved in concept

Later, **inside CP1-B**, after the necessary application dependency exists:

# E0b — POSTGRESQL PROTOCOL / DRIVER SMOKE TEST

verifying driver-level connection · actual PostgreSQL server and version · application-role
access · rollback behaviour · **exact `Decimal ↔ NUMERIC` round trip**.

**E0b is not part of E0.**

---

## 4. E0 task state

E0 is the bounded first increment of the existing **`implement`** workflow task.

```
implement:  ready → in_progress        …and after E0:  in_progress
```

# DO NOT COMPLETE `implement` AFTER E0.

E0 earns **no** CP1 completion credit · does **not** make the project review-ready · must
**not** promote `design_review` · must **not** promote `technical_review`.

The Engineer stopping after its bounded assignment while the task remains `in_progress` is
represented through the existing truthful lifecycle (ADR-0033 P2 unconcluded-task stop).

> **Do not clear an unresolved-stop gap by falsely completing the task.**

---

## 5. R4 — Frontend framework: **DEFER**

The production architectural class remains **TypeScript SPA**. **Do not select React, Vue or
Svelte now.** The B0b recommendation for React remains useful evidence.

Return for a human framework decision **before** production frontend scaffolding, CP7
implementation, or framework-specific design becoming load-bearing.

**This deferred decision must not block backend/domain engineering.**

---

## 6. R5 — Design-contract reconciliation: substantive supersessions approved; mechanism to be optimized

The substantive supersessions already decided by prior PDs are **accepted** and are **not new
product decisions**: four-level explanation wording → three rungs · eleven-surface framing →
approved four-surface IA · PD-0014's §D3.2 supersession · PD-0014/PD-0015 freshness and
valuation-time changes · stale OQ-01 remnants · `FEATURE_PRD.md` OQ-02 → **CLOSED** citing
PD-0020.

### 6.1 CRITICAL LIFECYCLE RULE

# DO NOT REOPEN `prd`.

`specs/FEATURE_PRD.md` is the declared artifact of the completed `prd` task. Reopening it
would demote completed downstream planning tasks — **`ux_planning` and `tech_planning`** —
and because those tasks have **no lawful revalidation block**, a dependency withdrawal would
write completion-withdrawal witnesses that are **not restorable** through the normal
revalidation mechanism. That would risk invalidating completed design and technical-planning
history, including the work culminating in Checkpoint A.

# OQ-02 SPEC RECONCILIATION MUST NOT BE IMPLEMENTED THROUGH A `prd` TASK REVISION.

**Do not** attempt to make the lifecycle "cleaner" by reopening the upstream PRD task.

**[PM] Verified, and the exposure is worse than a risk — it is a certainty.**
`workflows/feature-development.json` declares exactly **one** `revalidation` block in the
entire workflow, and it belongs to **`implement`**. `prd`, `ux_planning`, `tech_planning`,
`design_review`, `technical_review` and `pm_acceptance` have **none**. Per ADR-0030, a task
with no `revalidation` block is **not restorable at all**. The graph is
`prd → {ux_planning, tech_planning} → implement → {design_review, technical_review} →
pm_acceptance`, so reopening `prd` demotes `ux_planning` (complete rev 31) and
`tech_planning` (complete rev 8) into a state from which only **genuinely redoing them**
restores completion.

### 6.2 Safe routes for closing OQ-02 in the specification

**Route S1 — direct PM-owned spec edit without reopening `prd`.** Because `specs/` is within
the PM's write boundary, the human decision already exists in PD-0020, and the edit only
synchronizes an open-question status with an already-authoritative decision, the PM may
directly update `specs/FEATURE_PRD.md` to mark **OQ-02 = CLOSED** citing PD-0020,
**WITHOUT REOPENING `prd`.**

If selected: state explicitly that the edit synchronizes an already-decided human ruling ·
attribute it to PD-0020/PD-0021 · do not pretend it came from a new PRD task round · record
why no task revision was used · **make no other substantive PRD/spec scope change in the same
edit**.

**This is the preferred route unless repository doctrine explicitly forbids such PM-owned
synchronization.**

**Route S2 — PM-owned supersession note only.** If direct synchronization is judged
inappropriate, maintain a durable PM-owned note stating that OQ-02 was closed by PD-0020,
that any stale OPEN marker is superseded, and that downstream implementation must treat
PD-0020 as authority. If used, downstream Engineer briefs must cite the note and PD-0020
explicitly, and **stale source wording must not silently regain authority**.

### 6.3 Design and technical artifacts — task-bound revision remains available

Reopening **`ux_planning`** is safe relative to completed-task withdrawal because its
dependent `implement` is **not complete**. The same holds for **`tech_planning`**.

# BOTH MUST OCCUR BEFORE E0 MAKES `implement` ACTIVE, if they are required.

Once `implement` is `in_progress`, reopening either dependency can demote it.

### 6.4 Optimize the mechanism

**Do not automatically reopen `ux_planning`.** Weigh in-place Designer revision (canonical
artifact updated directly; but full task lifecycle and revision churn, for content that is
largely **CP7-facing rather than CP1-load-bearing**) against the supersession-note route
(preserves authority without design-task churn; but downstream implementation must reliably
discover the note).

**Stated preference:** keep CP7-facing mechanical design cleanup **off the CP1 critical
path**, if authority and traceability remain intact. **Do not choose it only for speed if the
Engineer would not lawfully discover the supersession.**

---

## 7. Reporting currency — CP1 model versus CP7 presentation

### 7.1 CP1-A **must** include the reporting / native currency domain model

At minimum: Portfolio reporting currency · Listing trading/native currency · LedgerEvent
currency · Account/cash currency representation · the invariant that **historical ledger
facts are not rewritten into reporting currency** · the boundary where later FX conversion
enters · behaviour when an FX observation is **unavailable**.

The model must hold holdings and cash across **USD, HKD, CNY** and other supported currencies
**without premature conversion**.

### 7.2 Deferred work is presentation only

UI controls · labels · explanatory copy · native-vs-reporting display · switching behaviour.

> **Deferred presentation work is not permission to omit the underlying CP1 currency model.**

---

## 8. R6 — Commercial / deployment intent: **DEFER**

P0 may begin provider research now. For vendor and licensing comparison, model at least
**internal/development**, **private beta**, and **public/commercial display**.

**Do not finalize production licensing before intended deployment is sufficiently explicit.**

---

## 9. Quant Analyst boundary — approved

**Quant is not required for:** E0 · ordinary schema design · event ordering · identity-model
implementation · database connectivity.

**Quant is required** where implementation depends on financial methodology or conventions,
and **before CP1 closure, to independently ratify the golden fixture**.

**The Engineer must not silently decide:** lot depletion method · split fractional-share
treatment · return denominator conventions · later methodology-registry content.

The proposed CP1 fixture deliberately avoids unresolved Quant conventions and **must remain
bounded that way**.

---

## 10. CP1 implementation order

After PD-0021 is committed, PostgreSQL is provisioned, pre-E0 planning authority is resolved,
and **E0 passes**:

| Package | Contents | Notes |
|---|---|---|
| **CP1-A** | User · Portfolio · Account · Issuer · Instrument · Listing · canonical internal IDs · FIGI/MIC attributes · **reporting/native currency model** | **No reporting-currency UI.** |
| **CP1-B** | append-only ledger events · PostgreSQL schema/migrations · **E0b** · `Decimal`/`NUMERIC` correctness · reversal/correction · idempotency | **Requires E0 PASS.** |
| **CP1-C** | positions · cash · multi-currency state · as-of replay | |
| **CP1-D** | mandatory CP1 scenarios · reproducibility · **Quant independent ratification before closure** | |

All remain **bounded increments under `implement = in_progress`**. Complete `implement` only
when actual CP1 implementation is ready for downstream review.

---

## 11. P0 remains parallel

P0 stays human-owned and parallel to CP1. It does **not** block CP1. It **must close OQ-04
before CP2 exits**. Provider research may proceed while PD-0021 is recorded, PostgreSQL is
provisioned, CP1 planning authority is reconciled, and E0/CP1 proceed. **Do not serialize P0
unnecessarily.**

---

## 12. What this decision does NOT do

- It does **not** rewrite, amend or reopen `PD-0020`, `PD-0019`, `PD-0017` or `PD-0011`.
- It does **not** authorize CP1 product implementation to begin — E0 and its prerequisites
  come first.
- It does **not** authorize running E0 in the turn that records this decision.
- It does **not** select a frontend framework (§5) or finalize deployment intent (§8).
- It does **not** adopt Option C (§1.3).
- It does **not** reopen `prd` under any circumstances (§6.1).
- It does **not** close OQ-04.
- It does **not** itself edit `specs/FEATURE_PRD.md`, `designs/FEATURE_DESIGN.md` or
  `implementation/FEATURE_TECH_PLAN.md`; §6 rules on the **mechanism**, and the edit is a
  separate, bounded, attributable act.
- It does **not** mutate any task shard. `implement` remains `ready` until the lawful E0
  increment begins.

## 13. What is not evidence for this decision

Per PRD §38.1: none of the following was treated as approval — the B0b plan's PM
recommendations, the passing validation suite, the verified permission allowlist, or the
absence of objection. Those are inputs the owner weighed. **The rulings in §1–§10 are the
owner's**, recorded here by an agent that did not make them.
