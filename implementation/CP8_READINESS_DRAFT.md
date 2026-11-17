# CP8 Scenario Lab — engineering readiness draft

2026-10-19, engineer. **PREPARATION ONLY — NOT AN IMPLEMENTATION CONTRACT OR CP8 ACCEPTANCE.**
This file is the sole new project artifact of this assignment. No product, test,
method, dependency, migration, frozen D source or evidence file is changed.

## 1. Authority and status vocabulary

- **IMPLEMENTED** means an interface was found in current source. It does not mean
  it supports hypothetical inputs, and this read-only assignment did not execute it.
- **PROPOSED** means a reviewable future design, not a callable route or approved
  financial convention. **UNKNOWN** identifies a decision or capability not established.
- [Current status](../STATUS.md), [D PM acceptance](../reviews/CP7_D_PM_ACCEPTANCE.md)
  and the PM dispatch establish bounded local synthetic D technical acceptance:
  2618 tests run / 2616 passed / 2 stated E0 preflight skips / 0 failures. Those
  are the accepted D record's results, not new tests run for this document.
- [PD-0045](../decisions/product/PD-0045-bounded-overnight-cp7-continuation.md)
  authorizes CP8/9 preparation only after D, with the existing 14:30 Shanghai cutoff.
  CP8/9 formal implementation is **NOT AUTHORIZED** by that preparation permission.
- [PD-0013](../decisions/product/PD-0013-hg1-absorbs-hg4-ux-prototype-approval.md)
  makes HG4 real-data usability validation; HG1 already absorbed prototype UX.
  D's synthetic acceptance is not HG4 approval. HG5 follows CP6 + CP8 + CP9.
- [PD-0041](../decisions/product/PD-0041-hg3-approved-with-conditions-and-cp6-start.md)
  already chooses FULL_NAV/GLOBAL_PRODUCT, temporary US-only real validation and
  the labelled SPY/USD gross-total-return ETF-proxy route. Do not reopen those
  choices. It does not admit a source or select a benchmark for a portfolio.

The required product is PRD §24 / FR-029–030 / CP8 / UAT-06: a hypothetical copy,
explicit changes, Current-versus-Scenario risk/exposure comparison, and no change
to actual positions. The existing approved design also requires evidence on both
columns, permanent SCENARIO identity at every depth, and ACTUAL-only Overview and
Holdings. A proposed snapshot-only first increment would not alone complete CP8.

## 2. Current interface inventory

| State | Interface actually inspected | What exists / what it does not establish |
|---|---|---|
| IMPLEMENTED | `src/domain/portfolio.py` | Immutable User, Portfolio and Account identities. No ScenarioState, scenario ownership model or scenario store was found. ScenarioState in the old technical plan is a design declaration, not implemented code. |
| IMPLEMENTED | `src/domain/ledger.py`, `src/domain/replay.py` | Canonical actual events, correction/reversal rules, snapshot horizons and exact replay/FIFO. They are not a scenario editing language. |
| IMPLEMENTED | `src/persistence/web_workspace_store.py` | Owned immutable actual revisions, pinned ledger/benchmark/policies, native replay, append/correct/reverse/account commands, exact historical snapshot verification. Calling these commands changes actual state. |
| IMPLEMENTED | `src/web_api/analytics_context.py` | Read-only explicit owned portfolio/revision/account preflight before source decoding; current fixture-byte verification and calculation-span bound. No scenario selector/context exists. |
| IMPLEMENTED | `src/web_api/analytics_requests.py`, `analytics_composer.py`, `analytics_routes.py` | Account-only actual revision evaluate/evidence/reproduce for performance-window, gains, attribution and risk; family/group/window/manifest/digest binding. Not a scenario endpoint. |
| IMPLEMENTED | `src/performance/engine.py`, `results.py`, `manifest.py` | Actual valuation/window/gains/attribution/series and reproduction. ComputedMetric explicitly refuses non-ACTUAL portfolio state; manifest defaults to ACTUAL. There is no scenario parameter on the public computation entry. |
| IMPLEMENTED | `src/risk/engine.py`, `results.py`, `manifest.py` | Actual portfolio return-series risk, benchmark/risk-free legs and reproduction; RiskMetric explicitly enforces ACTUAL. This is not a hypothetical fixed-weight history entry. |
| IMPLEMENTED | `src/diversification/engine.py` | Actual capital snapshot and current-fixed-weight historical model; manifest explicitly writes ACTUAL. It composes actual CP3 valuation. Cannot relabel this entry as SCENARIO. |
| IMPLEMENTED | `src/diversification/core.py`, `contracts.py`, `inputs.py` | Exact capital buckets, capital/exposure/statistics primitives and explicit histories/coverage. Potential reuse below a new scenario entry needs a public-boundary and Quant review; no scenario service is inferred from these helpers. |
| IMPLEMENTED | `performance_service`, `risk_service`, `diversification_service` | Actual committed-ledger/service gates, pinned selection, read-only corporate-action detection and synthetic-source restrictions. The D fixture path separately discloses CALLER_SUPPLIED suppression semantics. Neither is a scenario-construction service. |
| IMPLEMENTED | `src/insight_service/sources.py`, `src/insights/engine.py` | CP6 verifies/reproduces sources and rejects non-ACTUAL sources; packets emit ACTUAL and scenario_id=null. Existing field names are not evidence of scenario support. |
| IMPLEMENTED | `web/src/App.tsx` | Scenario route is an honest CP8 not-implemented placeholder. No functioning scenario editor, comparison or scenario evidence reader exists. |
| UNKNOWN | Durable scenario storage / API / method registry | No implemented `src/scenario*` package or scenario migration/route was found in this scoped source inventory. Scenario creation/comparison is required; cross-session named saving is not explicitly required in the reviewed PRD/design. Storage lifetime, version retention and implementation remain unspecified. |

**Key constraint:** an in-memory copy of events still becomes an ACTUAL computation
if handed to the existing actual-only entry points. Adding `state_type:SCENARIO`
only to the HTTP wrapper, changing canonical JSON after sealing, or setting an
unchecked manifest field would create contradictory evidence. None is proposed.
The old technical plan explicitly anticipates a separate CP8 entry and manifest
kind; current architecture tests also keep scenario capability out of pure
performance/risk packages. Do not weaken their guards to make the first UI work.

## 3. Financial semantics that must precede implementation

All items below are **UNKNOWN / QUANT CONTRACT REQUIRED**. This draft does not
choose a new financial convention or derive expected financial values.

1. **Hypothetical state model.** Define whether a scenario is an as-of capital
   snapshot, a rebalance at that as-of date, or a specified historical model.
   Actual portfolio TWR is not the historical performance of today's hypothetical
   weights. Keep that distinction in input, result and evidence identities.
2. **Action accounting.** Reducing/removing a position does not itself define
   proceeds, residual cash, funding, fees, tax, sale price or execution date.
   Adding cash may mean external capital or redistribution. Require an explicit
   supported model; never infer trades, a residual bucket or a funding currency.
3. **Target weights versus quantities.** Define accepted action variants, exact
   units, ordering/conflicts, the capital denominator, weight-sum checks and
   treatment of zero, shorts, leverage and fractional units. User confirmation
   of a decimal is not permission to round it into executable share quantities.
4. **Snapshot valuation and missing components.** Reuse the admitted price/FX and
   sufficiency rules, including unknown quantities, incomplete FULL_NAV and
   separately labelled partial figures. Partial value cannot become the weight
   denominator. No supplied scenario price may masquerade as an observed quote.
5. **Historical risk model.** Determine which same-registry methods are valid for
   a hypothetical state, how fixed weights/security histories and rebalance
   assumptions feed them, and what the result means. Do not synthesize actual
   transactions or historical portfolio NAV merely to obtain a risk series.
6. **Comparison and differences.** Specify comparability requirements, units,
   exact witnesses and whether a difference is meaningful for each metric.
   A backend calculation must issue any numeric delta as a metric; the browser,
   explanation layer and this draft must not subtract displayed values.
7. **Constraints.** A user-confirmed concentration bound is a preference, not a
   universal risk rule. Define simple validation separately from automatic
   optimization/weight allocation. An optimizer, personalized recommendation or
   inferred constraint is not an implied part of a form labelled "enforce".
8. **Evidence / methods.** Define a separate scenario entry/result/manifest with
   state_kind=SCENARIO, explicit scenario identity and compatible method registry
   references. Reuse existing formulas where valid; do not claim a new scenario
   wrapper alone establishes method equivalence or CP6 acceptance.

## 4. Proposed minimum decomposition

Every path and endpoint in this section is **PROPOSED / NOT CREATED**.

| Order | Bounded deliverable | Prerequisite and limits |
|---|---|---|
| CP8-A | Quant state/action/comparison contract; independent hand-derived golden cases; engineer final typed API and dependency plan; designer Current/Scenario/evidence flow | Formal CP8 authorization and Quant definition. This draft is preparation for that work, not completion of it. |
| CP8-B | Isolated scenario definition/validation and deterministic snapshot capital comparison at one fixed actual revision | Only defined actions; existing fictional Jan2 instruments/prices; no actual writes, no AI, no history creation. A disclosed snapshot milestone, not full CP8 exit. |
| CP8-C | Valid hypothetical risk/exposure model, paired comparison, separate evidence/reproduce and three-depth EN/zh UI | Same declared source/window/units; explicit insufficient branches; positive statistics need independently sufficient test data and separate data authorization where applicable. |
| CP8-D | Isolation/integrity/adversarial tests, independent technical and designer checks, PM checkpoint package | All PRD §24.3 outputs accounted for, supported or honestly refused; actual-state nonmutation proven. HG4/5 owner decisions stay separate. |

Suggested new modules, after approval:

- `src/scenario/contracts.py`, `validation.py`, `engine.py`, `manifest.py`:
  immutable definitions, state-aware orchestration and reproduction. No database,
  web, source loader or actual write imports in this pure boundary.
- `src/scenario_service/context.py`, `service.py`: owner-scoped base revision
  acquisition and source/provider injection. No call to actual ledger commands,
  CSV import, benchmark selection writes or actual portfolio creation.
- `src/web_api/scenario_requests.py`, `scenario_routes.py`: strict wire conversion
  at the web edge. Minimum route installation only; old D responses stay exact.
- New `tests/product/test_scenario_*.py` and a separately approved actual-PG suite;
  independent Quant fixtures belong in `methodology/`, not author output copies.
- Frontend module/reader paths remain the web author's proposal; require separate
  SCENARIO types rather than widening accepted actual Snapshot/Workspace unions.

**Reuse choice:** prefer an additive scenario orchestrator over suitable public
exact primitives, with separately reviewed public seams if required. Do not copy
the financial engine wholesale or reach through private helpers as a permanent
API. Do not make old ACTUAL result classes accept SCENARIO without an explicit
reviewed contract and preservation tests. The exact reuse seam remains UNKNOWN
until Quant establishes the supported state model and implementation is authorized.

**Required product versus storage design:** hypothetical state creation and
comparison are already required by PRD §24 / FR-029 / CP8, and are not a new owner
question. Those clauses and approved design §D1.7 do not explicitly require named
scenario saving across logout/restart; the prototype's named presets are disclosed
fixed enumerations, not evidence of durable user-created scenarios. Its phrase
"persistent separation" requires permanent visual identity, not database storage.
The technical lifetime, storage/versioning, retention/export/deletion contract
remain UNKNOWN. Recommend retaining the complete immutable definition throughout
an active, recomputable comparison first, without claiming cross-session saving.
If the final CP8 scope includes a durable Save action, specify and verify that
behavior before presenting it. A separate immutable scenario namespace/table and
minimal grants are only a proposal, not authority to add a migration now. No
scenario goes in actual revision JSON.

## 5. Input and recomputation contract sketch

The following names are discussion shapes, **not final wire fields or live routes**.
Each route would authenticate and check CSRF. No caller-supplied owner, source
hash, actual ledger version, registry version or financial output is trusted.

```text
POST /api/v1/portfolios/{portfolio_id}/scenarios/validate
POST /api/v1/portfolios/{portfolio_id}/scenarios/evaluate
  base_revision_id, as_of, scope:{kind,account_id},
  scenario:{scenario_id?, definition_version?, name,
            model_id, actions:[Quant-defined tagged action variants]},
  question:{family,window,frequency}, synthetic_acknowledged

POST /api/v1/portfolios/{portfolio_id}/scenarios/evidence
POST /api/v1/portfolios/{portfolio_id}/scenarios/reproduce
  full_canonical_definition_or_owned_saved_version,
  explicit_base_revision_id, explicit_question,
  scenario_result_id, expected_binding_digest,
  expected_manifest_id, expected_result_digest
```

Required sequence, **PROPOSED**:

1. Prove portfolio ownership, exact base revision and revision-visible account
   scope before JSON/source/catalog work; foreign/missing identities share 404.
2. Verify the immutable actual base source/result and read its native state.
   The baseline stays pinned even if the actual head later advances. Present
   that base date/revision; an explicit "rebase" is a new scenario definition,
   not automatic retargeting to current holdings.
3. Strictly validate action enums and exact string inputs. Resolve listings by
   existing owned/admitted identity, never ticker guessing; unsupported entries
   remain explicit. No new SPY/default benchmark, instrument or classification.
4. Build a separate immutable hypothetical state. Record every user modification
   and every inherited input, along with the defined funding/weight semantics.
   Validation errors prevent the complete scenario computation; no silent clipping,
   auto-normalization, missing-row omission or partial action application.
5. Invoke the approved scenario entry; compute actual baseline and scenario with
   explicitly comparable question/source assumptions. Baseline ACTUAL risk and
   scenario fixed-weight historical risk may be different models: mark them
   non-comparable rather than subtracting unlike outputs.
6. Issue separate baseline and scenario references and any supported comparison
   metrics. Preserve value=0 versus null, all causes, exact rational/radical
   witnesses, exclusions/partial state, dates, observations and freshness.
7. Evidence/reproduction binds the exact scenario definition/version and base,
   checks source bytes and method versions, reruns that entry, and compares the
   complete canonical result. A valid reference with wrong expected answer must
   reach result comparison, not become a fabricated missing identity.

Initial resource proposal: retain D's 32KiB HTTP / 2MB UTF-8 response and
3660-natural-date calculation bounds, and add an explicitly published finite
action/constituent/definition capacity after complexity review. These limits are
not yet an implementation contract. Reject whole oversized work before loops;
do not shorten financial windows, drop constituent histories or truncate evidence.

## 6. Identity and evidence isolation

All additions below are **PROPOSED**. Existing ACTUAL objects remain byte-exact.

- Common binding: owner-resolved portfolio, explicit base revision/ledger/selection
  pins, account scope, as-of, reporting currency, fixture/release/calendar hashes,
  registry/method versions and complete question. Owner identity is derived from
  session context, not accepted from the body or written as an authentication secret.
- Scenario binding: `state_type:SCENARIO`, distinct scenario id and immutable
  definition/version digest, model semantics, exact action inputs/provenance,
  inherited-input references, assumptions and hypothetical-state digest.
- Actual binding: `state_type:ACTUAL`, scenario_id=null and the original actual
  result reference. A no-op scenario still has a different state identity.
- Comparison binding: two explicit typed references, comparator method/version,
  same/different source/window/model disclosures and a metric-level comparability
  state. It is neither a replacement Actual claim nor a bare JavaScript delta.
- Scenario evidence, exported JSON, downloaded reports, print/deep links and all
  depths retain the SCENARIO marker and modified-versus-inherited provenance.
  Overview/Holdings reject scenario objects structurally. Old CP5/6 proof loaders
  and CP6 source verification continue to reject unsupported scenario sources.
- Baseline changes, definition changes, user changes, logout and rebase invalidate
  affected scenario UI results/receipts. An async old result must never populate
  a new identity or restore private data after logout.
- Do not register scenario actions as actual LedgerEvents, claim financial source
  keys, modify UserLimit provenance or change benchmark selection. Explicit actual
  portfolio editing remains an independent future user action through its existing
  confirmation flow; no "apply scenario" endpoint is proposed for this increment.

## 7. Proposed independent verification matrix — all NOT RUN

| Boundary / case | Required evidence after implementation authorization |
|---|---|
| Actual nonmutation | Before/after all actual ledger rows, revisions, accounts, selection/policy pins, CSV source keys/reports and complete saved bytes unchanged on successful, invalid, oversized, cancelled, repeated and concurrent scenario work. Also preserve the next actual write behavior. |
| Least privilege | Scenario compute adapter cannot call actual command/import/write paths; if scenario persistence is approved, its own namespace/grants only. No RLS claim without actual policy tests. |
| State types | ACTUAL and SCENARIO ids/manifests differ even for a no-op. Actual snapshot/evidence/CP6 readers refuse scenario payload injection; no wrapper-only retagging. |
| Ownership order | Foreign portfolio/revision/account/scenario plus damaged stored source or catalog still returns generic 404 before source parsing/provider calls. Owned corruption returns typed refusal. |
| Action semantics | Quant-derived examples for reduce/remove/add/increase-cash/alternative weights; explicit funding, dates and precision. Conflicting actions, overspend, shorts or leverage outside defined scope refuse, never silently normalize. |
| FULL_NAV | Securities/cash/receivables retained; incomplete base denies unsupported weights; no denominator from a partial valuation. Already-approved global policy identity stays intact. |
| Numerical witnesses | Independent handwritten exact expectations; zero versus null, nonterminating fractions, display ties and rounding. No expected fixtures copied from author outputs. |
| Source insufficiency | Missing listing/price/FX/calendar/classification/coverage, unresolved split and one-day source; preserve exact issued causes and null counts. No default rate, price, return or warning. |
| Statistical model | Independently sufficient labelled test-only histories under the approved model; distinguish actual TWR from fixed-weight historical association; no forecast or execution promise. Current one-day runtime cannot certify positive historical risk. |
| Benchmark/risk-free | Empty, missing and malformed catalog distinct; UI NOT_STATED/NONE/SELECTED and their canonical NONE/CLEARED/IN_FORCE pins remain distinct. Independent outputs survive irrelevant missing dependencies; no automatic SPY choice. |
| Window/group identity | Same requested window/frequency/scope; no silent clipping. If default X/Y composition is supported, both refusals/results and independent/benchmark identities remain traceable. |
| Comparisons | Same output with no-op where mathematically valid, but distinct identity; unsupported comparison suppresses its delta. Partial/LIMITED exclusion semantics remain metric-specific. |
| Reproduce/tamper | Correct answer REPRODUCED; wrong expected digest RESULT_DIFFERS; changed definition/base/pin/source/method refuses. Missing provenance keys do not reconstruct default confirmation. |
| Stale/rebase/concurrent | Actual head advance does not mutate old scenario; explicit new definition on rebase; operation/version conflicts do not overwrite another scenario or change actual state. |
| Resources/durability | All nested work bounded before expensive loops; full output size checked. If saving is approved: exact retry, immutable history, restart, capacity and corruption tests in separate scenario storage. |
| Browser/evidence | EN/zh, Quick/Simple/Professional, narrow layout, keyboard/focus, both comparison columns and nested proof views retain hypothetical status; raw machine labels do not masquerade as explanation. |
| Identity races | Out-of-order results, navigation, account change, logout and new login cannot mix actual/scenario contexts or expose another user's definitions. |
| Preservation | Frozen D53 and protected engines/methods/SQL/fixtures/catalogs/old evidence exact unless a later specific change is approved. Existing architecture guards run early, then affected and complete actual regressions with truthful executor attribution. |

## 8. Required decisions and suggested order

| State / owner | Item | Engineering recommendation |
|---|---|---|
| UNKNOWN / Quant before numerical CP8 work | Eight semantics in §3; state-aware public reuse seam and independent golden expectations | Define snapshot actions and capital accounting first, then valid historical risk/comparison semantics. Keep current engine method formulas wherever applicable; no label-only bridge. |
| NOT AUTHORIZED / human owner | Formal CP8 implementation scope and any explicitly necessary method/source edits | Present the reconciled Quant + engineering + design package before implementation. A possible first local synthetic snapshot milestone must be named as partial, not full CP8 completion. |
| UNKNOWN / engineer + PM contract | Scenario storage lifetime/versioning/retention; any proposed durable Save control | Creation/comparison is already required, not pending owner reconfirmation. The reviewed PRD/design does not explicitly require cross-session named saving. Specify the chosen technical lifetime and any actual Save promise; do not assume an implied DB migration. Automatic optimization remains outside the proposed first increment and needs its own defined contract. |
| ALREADY DECIDED / do not re-ask | FULL_NAV/GLOBAL_PRODUCT; temporary US-only real validation; SPY ETF-proxy route | Carry PD-0041 provenance unchanged. Per-portfolio dated benchmark choice and admissible data remain separate facts. |
| RESERVED / human gate and source authorization | Real holdings/data reading, downloads/admission, new dependencies/services, HG4 real-data validation, later HG5 | None performed or implied. Existing synthetic scope is not evidence of real-data readiness; HG3's 66 supporting gaps stay open. |
| DEFERRED / CP9 | AI-created scenarios / natural-language orchestration | Not required to implement the deterministic CP8 core; no model call, conversational recommendations or execution path in this preparation. |

Recommended next action after this read-only draft: PM obtains the Quant contract
and reconciles it with designer/evidence requirements, then presents a concrete
CP8 implementation scope for the owner's decision. Preparation may continue under
PD-0045; implementation does not begin on silence or technical enthusiasm.

## 9. Inspection and preservation record

- Read current STATUS/PROGRESS, PD-0013/0041/0045, D PM acceptance and synthetic
  exit, PRD §§24/38/CP8/UAT-06, approved design Scenario/P8 sections, original tech
  model/boundaries, and the source/test interfaces inventoried above.
- Searched code/path names for scenario entry/types/routes/migrations; found the
  proposed old model, ACTUAL guards and web placeholder, not an existing scenario
  service. This is a scoped source inventory, not proof of runtime behavior.
- No financial engine, tests, PostgreSQL, HTTP, browser, process control, download,
  install, external AI/service, real market row or personal holdings file was used.
- No new test pass, source admission, gate decision, durable scenario feature or
  full CP8 completion is asserted. The old dirty checkout is preserved. Draft
  link/path inspection and D53 hash preservation are the only intended checks.
