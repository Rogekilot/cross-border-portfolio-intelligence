# Phase B / CP1 — Implementation authority (Engineer-readable synchronization)

**Synchronized by:** `product_manager`, worker `pm-01`, session `fin-web-e5`, 2026-09-22
**Sources:** `decisions/product/PD-0020-phase-b-architecture-and-sequencing.md` @
`4c0fb347ad42abd6872ce4108c1426a57eb3be6c` · `decisions/product/PD-0021-cp1-identity-and-entry-preconditions.md`
@ `ddc5d0042a5330706926bb8c95ee2e9665735c25`
**Reached from:** `specs/FEATURE_PRD.md` §9.1 — a declared read of the `implement` task.

---

## 0. What this file is

# THIS FILE IS NOT NEW PRODUCT LAW.

It **synchronizes already-approved human decisions into an Engineer-readable specification
surface**. Every statement below was decided by the human product owner and recorded in
`PD-0020` or `PD-0021`.

> **If this file differs from `PD-0020` or `PD-0021`, the accepted PD controls and the
> discrepancy is a defect in this synchronization artifact.**

**Why it exists.** `decisions/product/` is outside the `engineer` role's `read_paths`, so an
Engineer cannot lawfully read the PDs. This file is inside `specs/`, which the `engineer`
role can read, and it is reachable by an explicit pointer from `specs/FEATURE_PRD.md` §9.1,
which the `implement` task declares as an input.

**What it is not.** It is an **authority index and synchronization layer**. It is **not the
primary technical implementation contract**. That remains:

# `implementation/FEATURE_TECH_PLAN.md`

No additional architecture decision is introduced here. Where this file summarizes, the Tech
Plan elaborates.

---

## 1. From PD-0020 — architecture and sequencing

| Item | Decided |
|---|---|
| **OQ-02** | **CLOSED.** The stack/persistence question reserved to the human is resolved. |
| **Backend / runtime** | **Python-first.** Python is the authoritative backend, domain and financial-computation runtime. Grounds: deterministic financial computation, native `decimal.Decimal`, quantitative ecosystem, alignment with future Quant work, golden fixtures in the same ecosystem, and possible reuse of `src/product_contract/` rather than automatic porting. **This does not authorize a Python-rendered frontend.** |
| **Frontend class** | **TypeScript SPA** — architectural class only. |
| **Frontend framework** | **NOT DECIDED — reserved to the human.** React, Vue and Svelte were compared; none was selected. **Do not select or scaffold one.** |
| **Persistence** | **PostgreSQL-class relational.** Grounds: exact numeric support, constraints, auditability, mature migration tooling, temporal/event-reconstruction needs. Decided independently of the prior Tech Plan's proposal. |
| **Ledger** | **First-class append-only event domain model.** `PostgreSQL → append-only ledger/event tables → deterministic point-in-time reconstruction`. **Mutable current-position rows must not become the sole system of record.** Does **not** authorize Kafka, a dedicated event-store product, distributed event sourcing, or service-per-domain. |
| **Topology** | **Modular monolith.** No microservices, sharding, distributed transactions, dedicated queues or time-series database **without evidence**. Maintain clean internal module boundaries. Keep AI orchestration behind a hard boundary so later isolation stays inexpensive at CP9. |
| **Dev environment** | **Human-provisioned**, harness retained for governance/review. Conditional on E0. |
| **P0** | **Authorized** as a human-owned parallel market-data provisioning / commercial workstream. |
| **Sequencing** | **CP1-first, P0 in parallel.** CP1 does not wait for OQ-04. CP2 follows the PRD spine. |
| **PD-0011 §6** | Superseded **on authorization only**, to the extent needed to authorize Priority-A work through P0, B0b planning, the bounded E0 increment, and CP1-first engineering. **All substantive PD-0011 requirements remain in force.** |

---

## 2. From PD-0021 — CP1 identity and entry preconditions

### 2.1 Canonical identity — Option A

**Immutable internal database identities are the canonical persistence and join keys.**

- Distinct durable internal identities for **Issuer**, **Instrument**, **Listing**.
- **Ledger events reference the internal `listing_id`** — never ticker, never FIGI, never a
  FIGI+MIC composite, never a vendor identifier.
- Internal IDs stay stable when FIGI is unavailable, arrives later, or changes; when vendor
  mappings disagree; when a ticker changes; when something is delisted; when a provider is
  replaced.

**FIGI + MIC remain authoritative resolution primitives.** PRD §10.1's *"use FIGI + MIC as
canonical identity primitives where available"* applies to **real-world identification,
matching, security resolution, normalization, and evidence/provenance** — not to physical
database primary keys.

```
internal immutable IDs            FIGI + MIC + other identifiers
        ↓                                     ↓
durable ledger / relational joins   external identity / resolution / evidence
```

**Option C is not adopted.** Do not add a deterministic natural-key uniqueness scheme to make
internal IDs less opaque. It may be additive hardening later; it is not part of the ruling.

**The decisive invariant:** a correction to external identity must be capable of becoming
**an identity/resolution attribute update**, not **a migration of every historical ledger
reference**.

### 2.2 Reporting / native currency — CP1 scope, not deferred

**CP1-A must include the reporting/native currency domain model**, at minimum: Portfolio
reporting currency · Listing trading/native currency · LedgerEvent currency · Account/cash
currency representation · the invariant that **historical ledger facts are not rewritten into
reporting currency** · the boundary where later FX conversion enters · behaviour when an FX
observation is **unavailable**. Holdings and cash across **USD, HKD, CNY** and other
supported currencies must be representable **without premature conversion**.

**Deferred is presentation only** — UI controls, labels, copy, native-vs-reporting display,
switching behaviour. **That deferral is not permission to omit the CP1 currency model.**

### 2.3 E0 — the connectivity precondition

E0 is a **bounded first `implement` increment** whose sole purpose is to determine whether
the actual governed Engineer runtime can reach the human-provisioned PostgreSQL endpoint.

- File-based test under `tests/product/`, invoked via the lawful `python3 -m unittest` route.
  **No `python3 -c`, no `node -e`, no shell/interpreter workaround.**
- Two transports tested independently: **Unix-domain socket** and **loopback TCP**.
- Classify each: `TRANSPORT_REACHABLE` · `PERMITTED_NO_LISTENER` · `SOCKET_MISSING` ·
  `POLICY_DENIED` · `RUNTIME_ERROR` · timeout/other. Record raw evidence.
- **Send no credentials, no PostgreSQL startup packet, no application query.**

# E0 PASS = TRANSPORT REACHABILITY.

E0 does **not** establish PostgreSQL protocol success, authentication, server
identity/version, role permissions, schema access, transaction behaviour, migrations, or
`Decimal`/`NUMERIC` correctness. **Do not write "PostgreSQL works" because E0 passed.**

### 2.4 E0b — separate, inside CP1-B

After the necessary application dependency exists: driver-level connection · actual
PostgreSQL server and version · application-role access · rollback behaviour · **exact
`Decimal ↔ NUMERIC` round trip**. **E0b is not part of E0.**

### 2.5 `implement` stays `in_progress`

```
implement:  ready → in_progress   …and after E0:  in_progress
```

# DO NOT COMPLETE `implement` AFTER E0.

E0 earns no CP1 completion credit, does not make the project review-ready, and must not
promote `design_review` or `technical_review`. An Engineer stopping after its bounded
assignment while the task remains `in_progress` is represented through the existing truthful
ADR-0033 P2 unconcluded-task-stop lifecycle. **Do not clear that gap by falsely completing
the task.**

### 2.6 Frontend framework — still human-undecided

Return for a human decision before production frontend scaffolding, CP7 implementation, or
framework-specific design becoming load-bearing. **This must not block backend/domain work.**

### 2.7 Quant boundary

**Quant is not required for** E0 · ordinary schema design · event ordering · identity-model
implementation · database connectivity.

**Quant is required** where implementation depends on financial methodology or conventions,
and **before CP1 closure to independently ratify the golden fixture**.

# The Engineer must not silently decide:

lot depletion method (FIFO / average / specific-lot) · split fractional-share treatment ·
return denominator conventions · later methodology-registry content.

If implementation appears to require one of these, **stop and report it** rather than
choosing.

---

## 3. Standing constraints carried from earlier accepted decisions

These are not new. They remain in force and bear directly on CP1.

- **PRD §9.1** — *"transactions/ledger events are canonical and positions are derived state.
  Do not maintain an independent mutable 'current shares' value that can silently diverge
  from the ledger."*
- **PRD §9.3** — missing cost basis is allowed and **must never be fabricated**.
- **PRD §9.6** — deposits/withdrawals are external cash flows, not investment gains;
  transfers inside one portfolio are internal movements and must not be counted as return.
- **PRD §10.1** — **ticker is never the database primary key**.
- **PRD §12.4** — corporate actions must preserve economic continuity.
- **P12 / NFR-001 / §34** — determinism: same inputs and as-of date, same output.
- **PD-0011** — ETFs are V1; **mutual funds require a separate product decision** and must
  not be silently added.

---

## 4. Not authorized

Selecting a frontend framework · selecting a market-data vendor · writing market-data
adapters · deciding Quant methodology · implementing OCR · implementing AI orchestration ·
creating AI provider integrations · completing `implement` at E0 · reopening `prd` or
`ux_planning`.

---

## 5. Where to go next

| Need | Read |
|---|---|
| **Primary technical implementation contract** | **`implementation/FEATURE_TECH_PLAN.md`** |
| Product requirements and acceptance criteria | `specs/FEATURE_PRD.md` |
| Design / interaction contract | `designs/FEATURE_DESIGN.md` |
| Methodology and conventions | `methodology/` |
