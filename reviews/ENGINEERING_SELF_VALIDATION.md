# Engineering self-validation — CP4F-16 and CP5 candidate

2026-10-18. Author: delegated native Codex engineer. This is implementation evidence,
not independent review, PM acceptance, an owner capital-policy decision, or HG3 approval.

CP4F-16 is fixed in the test kit only: complete part-3 source/build assertions plus an
executed legacy JSON-rotation regression. Targeted PartThreeTests: 4 tests passed in
13.465 seconds. Product numerical paths were untouched.

CP5 code is in `src/diversification/` and `src/diversification_service/`; tests are in
`tests/product/test_diversification_golden.py`, `test_diversification_integration.py`,
`test_postgres_diversification.py`, plus the separately delegated drift module/tests.
Architecture, choices and unresolved owner boundary: FEATURE_TECH_PLAN §18.

Executed command:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_diversification_golden tests.product.test_diversification_integration tests.product.test_diversification_drift tests.product.test_postgres_diversification
```

Observed: **56 tests OK, 5 skipped, 9.504 seconds**. The skipped tests require the
database opt-in. Root separately reported 4/4 earlier database methods passed; its
fifth composition test and full suites remain for root verification, not assumed here.

Failures encountered and corrected before that run: initial registry copy retained an
extra newline and then predated the Quant's capital-policy update; the byte tie test
caught both. A foreign-cash check initially requested 36 months against an independent
12-month fixture and properly refused; the test now asks the fixture's actual window.
The FX1 trial used an impossible 20% HKD/USD peg move and was refused by existing CP2
SOURCE_CONFLICT; the test now expresses the fixture's exact FX return using unpegged
USD/EUR. No safety or numeric guard was weakened. A test concatenated a list to a tuple;
that test setup was corrected before execution passed.

All 34 fixture ids of issue 1.1 are explicitly inventoried, and 12 sample-count boundaries run.
The math tests consume the Quant's expected values, never product output as expected.
The actual engine path reads pinned ledger, market-data release, calendars, actions and
FX, with explicit metadata and action-coverage records. Full-NAV weights are gated by
owner-evidenced policy or the explicit all-synthetic candidate path. No choice is
manufactured. No insufficient output exposes a value or alternative numeric witness.

No commits, production dependencies, network data downloads, source admissions, paid
generation, production endpoints or frontend scaffold were created. Existing dirty
checkout work was preserved. Full regression, independent review and human decisions
are separately recorded by their owners; they are not claimed by this self-validation.

Follow-up before review: Quant issue 1.1 adds H16; the exact implementation yields
0.565685424949 and the executed pre-rounded-pair mutation yields 0.565685424950.
Root's fifth DB bundle test found the service passed a null benchmark catalog into
CP4. The service now loads the existing committed admitted catalog when omitted;
the regression checks unavailable beta and available independent volatility. No
CP4 method changed. Latest execution of the same command: **57 tests OK, 5 skipped,
9.230 seconds**. Root's database rerun is recorded separately.

Root subsequently reported the repaired database suite **5/5 passed, 1.149 seconds**.
The owner-approved test-only FX1 extraction is now `compute_fx_case()` for reuse by the
HG3 evidence exporter. Its unchanged actual-pipeline assertion was rerun separately:
**1 test passed, 1.777 seconds**. The extraction changes no product or methodology file.

## Independent §47 repair round

The reviewer returned HOLD with CP5I-1 through CP5I-6. Before any product repair:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_diversification_review
```

Observed **6 tests, 5 FAIL and 1 ERROR, 0.597 seconds**. The failures reproduced the
unscoped approval, artificial portfolio-inception floor, missing exposure display
partition, refused half-quantum tie, wrong cluster reason and false reproduction
success for null-key tampering. After focused fixes, those same six tests passed.
Additional neighboring regressions cover explicit global/portfolio/account scope,
missing decision evidence, no account inheritance, custom versus since-inception/MAX
floors, display digest binding, equivalent-root cancellation at both signed ties,
bucket renaming and typed/null/invalid manifest tampering. The separately delegated
drift repair preserves exact-value comparisons and validates the new scoped policy.

Final engineer command for this round:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_diversification_review tests.product.test_diversification_golden tests.product.test_diversification_integration tests.product.test_diversification_drift tests.product.test_postgres_diversification tests.product.test_hg3_evidence
```

Observed **82 tests OK, 6 skipped, 10.150 seconds**. Skips are the database opt-ins;
their current six-method run belongs to the root's serialized validation slot.
The current CP5 engine id is `diversification/cp5-0.2`; method/registry and CP3/CP4
numeric paths and fixtures remain unchanged. Required full-suite/reviewer/export
results are not assumed. No acceptance or owner approval is claimed here.

## CP6 bounded candidate — 2026-10-19

Authority is the owner's PD-0041 approval with conditions. The implementation uses
the independently issued `insights/1.0` method, with four deterministic families:
metric snapshots, benchmark underperformance, historical direction, and explicit
user limits. New source paths are `src/insights/` and `src/insight_service/`;
the additive technical plan is `implementation/CP6_TECH_PLAN.md`.

The service replays actual CP4/CP5 inputs and compares their complete canonical
answers before accepting a metric. It retains exact witnesses, immutable source
manifests, scope, Current M_t, method and reference choices, unavailable states,
temporal seams, freshness uncertainty and synthetic flags. The narrowly matched
CP3 valuation auxiliary is separately reproduced and authenticates only capital
snapshot freshness, enabling a qualified Warning for a synthetic explicit user
limit. Unknown/limited freshness or comparability caps severity at Attention.
No threshold comes from the FULL_NAV product denominator or a generic heuristic.

Actual focused command:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_insight_golden tests.product.test_insight_sources tests.product.test_insight_integration tests.product.test_approved_analytics_policy
```

Observed **101 passed, 0 failures, 14.725 seconds**. Its 60 golden-module tests are
59 independently issued rule predicates plus one explicit eight-case integrity
inventory, not eight additional successful adapter probes. The 29 real adapter/
rule tests execute source and auxiliary tampering, actual four-family composition,
exact policy equality/conflict/scope, UNKNOWN refusal, immutable packet fields,
Current instant and M_t, history semantics and full reproduction. The separate
approved-policy module contributes 12 tests. No database tests were started here.

Independent counterexamples were run red before correction: four malformed-source
errors, one nested-history error, and one failing taxonomy plus one failing cluster
comparison. Their focused regressions now pass. Financial convention/reference
semantics are bound without changing earlier engines or fixture expectations.

The reproducible synthetic CLI is `python -m tests.product.insight_demo --output
/tmp/NEW_UNIQUE_DIRECTORY`; it exports complete packets, source evidence, readable
claims and byte hashes after a successful actual replay. Its synthetic constraints
are examples, never real owner investment preferences. The 66 HG3 supporting gaps
are not declared closed. Root full regression, independent review and PM acceptance
are separate next evidence; this self-validation is not their substitute.

## 2026-10-19 — CP7-B remaining ledger and explicit preferences

Authority PD-0044. Backend adds strict workspace command requests, immutable
migration0018, owner-scoped current/historical workspace reads, atomic ledger
preview/append/correction/reversal/account-container commands, UserLimit persistence
and explicit canonical benchmark selection. Existing financial methods, engines,
raw fixture bytes and old saved snapshots are unchanged. New API contracts and
resource bounds are in `implementation/CP7_B2_TECH_PLAN.md`.

Actual pure command:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_web_api tests.product.test_web_auth tests.product.test_persistence_ledger tests.product.test_web_workspace -q
```

Observed **122 passed, zero skips/failures,3.284 seconds**. Initial runs exposed
the new migration's pin-block structural spelling and a new-test helper's duplicate
keyword; both were corrected without relaxing an existing assertion. A manifest
update/rerun overlap temporarily produced a checksum mismatch and was corrected
before the PostgreSQL suite.

Actual PostgreSQL command, on the root-provisioned private Unix socket with the
separate non-owner CP7 application role and disposable `finweb_it_*` schemas:

```
FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/finweb-cp7b-20261019/socket/.s.PGSQL.55419 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_CP7_APP_USER=finweb_cp7_app uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_postgres_web_workspace tests.product.test_postgres_web_auth -q
```

Observed **26 passed, zero skips/failures,26.445 seconds**:14 new workspace probes
and12 existing authentication/storage probes. The first23-test run found an old
typed-code regression for a tampered snapshot checksum; original
`SAVED_SOURCE_DIFFERS` behavior was restored and the full26-test rerun passed.
All disposable schemas were cleaned by the existing integration kit. No runtime
schema was migrated by this engineer and no process was restarted here.

Coverage includes actual global/gapped ledger pins; all15 manual input families
plus server-generated REVERSAL; zero basis and acquired_on; split on a different
date from trades; two-amount USD/HKD conversion without an invented rate;
atomic internal-transfer pairing; correction audit links; independent expected
native balances; stale/concurrent commands; idempotency conflict and retry after
a later head; rollback-only previews; immutable original proof reproduction;
historical empty-account visibility; full explicit policy semantic binding,
effective dates, clearing and policy-cited packet reproduction; empty real
catalog refusal and a positive labelled test-only catalog SELECT with origin/pin;
stored metadata corruption and owner-first404; least-privilege immutability and
new-store reload. Preview snapshots explicitly say persisted:false and
PREVIEW_NOT_SAVED, and cannot substitute for a committed artifact.

The original fictional market source/calendar remains one date,2026-01-02.
Later ledger native balances update, while unsupported market NAV is
INSUFFICIENT_DATA with no number. Production catalog entries remain empty; the
positive selection probe patches only a test catalog object, never data files.
Current actual CP5 portfolio targets are offered for personal policies; unsupported
CP4/account scopes are refused rather than silently rebound. No new dependency,
market-data admission, release, commit or night automation was introduced.

PM observed zero-basis preservation and the independent reviewer identified early
preview/history/pin/corrupt-metadata boundaries. Repairs are implemented and tested;
independent final validation and root regression remain separate evidence.

Final author follow-up: the saved-portfolio list now reports the latest revision's
as_of instead of permanently displaying its opening date; the new append probe
checks that metadata. Pure extreme-date probes exposed existing engine date-range
refusals; the API now translates ArithmeticError to422 (or503 for stored replay)
and rolls previews back. An actual PG regression covers0001-01-01 and9999-12-31.
Final actual PostgreSQL rerun, same command above: **27 passed, zero skips/failures,
29.759 seconds** (15 workspace+12 existing auth). Latest122-test pure rerun:
**122 passed,3.079 seconds**. The new pure test module also runs independently:
5 passed,0.001 seconds. Final `git diff --check` is clean. The four authorized old
test edits were compared to root's exact entry-byte backups: only migration18
count/version/table inventory and upgrade-list metadata plus comments changed.

Independent final-review integrity follow-up: persisted policy JSON must be an
array of objects; ACTIVE must agree with a nonempty decoded list; every stored
UserLimit field must be explicit, especially USER_CONFIRMED origin and nullable
scope/effectivity/subject fields. Constructor defaults may not manufacture absent
stored provenance. Owner snapshot/workspace GETs refuse malformed containers,
contradictory state/count and omitted fields with503 SAVED_RESULT_DIFFERS;
foreign-user requests still return404 before parsing. Snapshot serialization and
financial engines are unchanged.

Before the final exact-field strengthening, the complete author PostgreSQL suite
passed **28 tests,31.774 seconds**, zero failures/skips. After the strengthening,
the123-test pure suite passed **123 tests,3.284 seconds**, and the affected actual
PostgreSQL corruption test passed **1 test,1.647 seconds**, including missing
origin/account_id/effective_until/subject through both store reads and real ASGI
GETs. The targeted command was the same PG environment above plus
`python -m unittest tests.product.test_postgres_web_workspace.PostgresWorkspaceTests.test_policy_container_and_state_corruption_are_typed_after_ownership -q`.
All test schemas cleaned; the shared PG slot was released to root. Independent
full-suite verification of the final freeze remains distinct evidence.

Full-regression architecture repair: root's actual2561-test run found one real
dependency violation: persistence imported the risk-service catalog-file edge.
The existing boundary test was preserved unchanged. Catalog loading now belongs
to SyntheticWorld's web edge and is injected as a deferred provider; persistence
calls only after owner resolution and applies the domain's catalog rules. Missing
or malformed catalogs and non-catalog provider results are typed503
BENCHMARK_CATALOG_UNAVAILABLE, distinct from the committed valid empty catalog.
Saved proof replay continues to use its pinned selection without today's file.

Final targeted command includes `tests.product.test_risk_boundaries` before the
previous123 pure tests: **141 passed,3.776 seconds**, zero failures/skips. The
actual PostgreSQL command above passed **28 tests,35.986 seconds**, zero failures/
skips, with the expanded missing-catalog owner503/foreign404/proof-reload checks
and positive test-only selection via the injected provider. One intermediate
28-test run failed in new test wiring: its mock targeted a different synthetic
world from the ASGI app. The test now injects that same world at app construction;
its error/status assertions were preserved. All disposable schemas cleaned, PG
slot released, and `git diff --check` remains clean. Root full regression and
independent architecture verification remain separate next evidence.

## CP7-C author implementation and local validation — 2026-10-19

Authority is PD-0045 and the CP7-C validation contract. The C backend adds strict
original-byte CSV decoding, explicit indexed mapping/format/correction decisions,
rollback preview with a server-verifiable process receipt, atomic new-account
holdings or owned-account transactions, immutable full reports and successful
financial source identities. Unresolved intended economic rows produce zero
financial writes. Report-only operations do not claim source keys. Holdings
snapshot identities bind the complete economic record set before account creation.
Completed exact operations are recovered durably before receipt/capacity checks.

0019 adds only append-only reports/source-key tables, with SELECT and INSERT
application grants. The old eighteen SQL files and their checksum prefix remain
unchanged. Four old tests have only the authorized migration19 enumeration/table
inventory updates. Financial/domain methods, admitted catalogs, raw fixtures and
dependencies are unchanged. The existing architecture guard is included in the
pure checks. Backend and transport contracts are in CP7_C_TECH_PLAN.md.

Reports are bounded independently to1000 per portfolio and2,000,000 canonical
UTF-8 bytes. Exact retries precede capacity; report size is checked with conservative
final metadata at preview and exactly before insertion, in the same outer
transaction as financial writes. Report history has32-item owner-bound cursor
pages. JSON exports keep native unknowns, correction/reversal links, source
report/raw-row/file-SHA pointers, account names and only the historical benchmark
pin. The FIFO witness is direct public-engine output: the actual positive case
retains unit_cost1/6, while the fractional1:3 case keeps null/SPLIT_FRACTION. CSV
text protection is disclosed and does not claim universal spreadsheet safety or
decimal-import roundtripping.

Actual failures are preserved, not overwritten: phase2 combined42 actual PG
checks found one real equal-timestamp paging error (secondary ordering did not
match the cursor). Its original assertion remained; the targeted1000-report
recheck passed1 test in3.729s. Phase3 combined48 found one real complete-transfer
commit error after its rollback preview; the C boundary now restores deferred
batch insertion before B2 validates all constraints immediately. Phase4 combined50
had one new test instrumentation error: the actual immutable trigger returned
RestrictViolation/23001 rather than the assumed generic RaiseException. The test
now asserts the existing exact SQLSTATE. No financial or permission assertion was
weakened. Phase5 combined51 passed in87.387s before the final nonrecursive source
and report-only interpretation strengthening; final-candidate results follow.

Final author pure command: `uv run --no-cache --no-sync --frozen --offline python
-m unittest tests.product.test_csv_import tests.product.test_risk_boundaries
tests.product.test_web_api tests.product.test_web_auth
tests.product.test_persistence_ledger tests.product.test_web_workspace -q`:
**151 passed,4.016s**, zero skips/failures. Final actual PG command uses the
approved private55419 Unix socket/non-owner app role and disposable test schemas,
with modules `test_postgres_csv_import`, `test_postgres_web_workspace` and
`test_postgres_web_auth`: **52 passed,104.518s**, zero skips/failures. This includes
24 C tests and the unchanged28 B2 actual PG checks, including concurrent stale
head refusal, exact idempotency after process-key replacement, complete paired
transfers,1000-report pages/capacity, report growth/final-insert rollback,
original-source/report corruption and the existing FIFO positive/negative cases.

Sanitized raw logs remain in `/tmp/finweb-cp7c-20261019/` as
`backend-pure-final.log`, `backend-pg-final.log`, with every earlier red/green phase
kept separately. The approved bootstrap created only fresh
`finweb_cp7c_author`:19 migrations, SELECT/INSERT-only new-table grants,
non-owner application role and zero identities. Earlier schemas and API8000 were
not changed by the author. Independent review, actual HTTP/browser qualification,
controlled restart and PM full regression remain separate acceptance work.

### C final regression compatibility repair — original ledger TRUNCATE guard

PM's first full actual run was **2595 run,2592 passed,1 failed,2 E0 skips,
316.530s**. Its original raw log/JSON remain preserved as the first attempt.
The sole failure was the old ledger integration TRUNCATE assertion: the new0019
event source-key FK made PostgreSQL refuse ledger_event-only TRUNCATE with0A000
before its existing immutable trigger could run. This did not demonstrate a
weakened guard. The frozen0019/old SQL/FK/grants were not changed.

Under explicit PM authorization, only that test's TRUNCATE probe now names
`ledger_event, web_csv_source_key`, ledger first. SQLSTATE remains exactly23001;
new assertions require `diag.constraint_name=ledger_event_append_only` and the
original ledger-specific primary message, preventing the CSV table's generic
immutable23001 from satisfying the test. UPDATE/DELETE assertions are unchanged.
[PostgreSQL17's TRUNCATE documentation](https://www.postgresql.org/docs/17/sql-truncate.html)
specifies both the FK requirement and table-order trigger execution. Actual
PostgreSQL testing, rather than the documentation alone, confirms the guard.

The exact pre-repair file is retained at
`/tmp/finweb-cp7c-20261019/test_postgres_ledger_integration.py.before-truncate-repair`,
SHA-256 `56685066da7fe8f07ca87a4f272a341a28297e843452c36302d92a4c3543bfc4`.
The authorized focused old test plus all24 C PostgreSQL tests actually passed:
**25 tests,50.945s**, zero skips/failures. Command uses the same approved55419
Unix socket/non-owner app configuration and disposable schemas, modules
`tests.product.test_postgres_ledger_integration.LedgerDatabaseTests.test_update_delete_truncate_are_rejected`
and `tests.product.test_postgres_csv_import`. Raw output:
`/tmp/finweb-cp7c-20261019/backend-truncate-focused-c24.log`.
No B2/product source or API/runtime changed; a redundant28-B2 rerun was not
performed for this test-only compatibility change. Independent targeted review
and PM's complete final rerun remain distinct pending evidence.

## CP7-D backend author candidate — 2026-10-19

PD-0045 authorizes D after accepted/sealed C. Four additive web-edge modules
provide strict account-only explicit-revision evaluate/evidence/reproduce POSTs;
account_routes receives only installation wiring. No old snapshot, report, Proof
Packet, financial/domain/method, persistence, catalog, dependency, SQL or old-test
change is made. New analytics are read-only on-demand results, not newly saved
historical artifacts. The existing synthetic service gates remain unchanged.
The pure engines receive honest CALLER_SUPPLIED suppressions; no fictitious F8-B
feed/filing policy, external data, return history or new Warning is introduced.

Each request resolves portfolio, revision and historically visible owned scope
before raw fixture/catalog access or financial replay. It verifies current raw
quote/calendar bytes against the cached world's pinned source identity and
preserves existing complete saved-snapshot comparison. Required catalogs load
lazily; performance never reads unused benchmark/risk-free catalogs. Risk's
independent and benchmark groups keep distinct manifests, including approved
36-month X and MAX_AVAILABLE Y when fallback is actually issued. Current Jan2
nonpositive-window refusal/count-null remains engine-authored, not an invented
zero/observation count. Exact0/1, missing basis, original partial/excluded fields
and issued excluded weight are copied without new financial calculation.

Evidence binds family/group, normalized question, owner-scoped revision, ledger,
selection where consumed, source/calendar/release, registry/conventions and the
specific manifest. Reproduce calls the original family's engine with that trusted
typed manifest and pinned inputs. Valid identity plus a deliberately wrong expected
digest reaches RESULT_DIFFERS. No caller financial result or manifest is trusted.
No standalone curve or unsupported performance insight source is added.

Resource limits are explicit local transport bounds:3660 inclusive natural dates
across pinned source/request/acquisition work,32KiB request and2,000,000 UTF-8
complete output bytes. Span checks precede old snapshot replay/new engine loops;
whole-request resource errors carry a transport kind without a fabricated metric
state. No clamping, silent evidence truncation or source substitution.

Observed author results, with original logs retained under
`/tmp/finweb-cp7d-20261019/`:

- First pure+architecture run: **26 passed,0.425s**. The additive scope-order
  source check was then strengthened after independent finding R2: a foreign or
  later account scope must404 before poisoned fixture/replay work. New actual
  PG/in-process ASGI tests prove foreign/later404 and valid owned-scope503.
- First PG command stopped during test-module import: loader1 ERROR,
  ModuleNotFoundError(domain), no test body/PG product branch executed. The new
  standalone test now uses the existing src-path bootstrap convention.
- Second new actual run: **14 run,10 passed,1 failed,3 errors,18.144s**. Three
  errors were the author's incorrect sequence-table spelling in a no-write test
  helper. The failure compared a store datetime-bearing report object directly
  with its JSON-decoded GET form; it now compares exact canonical bytes. The
  original gain0/weight1/3/null financial expectations were preserved and already
  passed. These are test scaffold/comparison repairs, not engine changes.
- Final author pure run: **159 passed,3.499s**, zero failures/skips, including
  the retained architecture guard and all prior151 pure C/B2 checks.
- Final actual PostgreSQL plus in-process ASGI: **66 passed,101.627s**, zero
  failures/skips:14 new D,24 C and28 B2. This is not a real-HTTP/browser claim.
  It covers all four families and their own evidence/reproducers, wrong digests,
  old revision and account isolation, source/catalog corruption, null counts,
  independent selection behavior, resource refusals and no ledger/revision/
  report/source-key/selection or sequence changes from analytics requests.

The author's independently chosen positive example imports one SYN-A unit with
basis100 and one SYN-B unit with unknown basis into a separate account; shipped
prices100/50 give known gain0 and excluded weight50/150=1/3. The actual public
engine emits LIMITED value0/exact0/1/weight1/3 while preserving partial=false and
excluded=[]; the adapter does not manufacture a count or rewrite those fields.
Separate known basis0 versus absent-basis checks preserve100 versus no gain value.

Raw logs: backend-pure-phase1.log, backend-pg-phase1.log (loader failure),
backend-pg-phase2.log (scaffold/comparison failures), backend-pure-phase2.log and
backend-pg-phase3.log (final green). Canonical author examples are separate
backend-wire-*.json files, not independent expected-value fixtures. Web author
confirmed no concurrent self-validation edits before this additive append.
PG slot was explicitly released to PM after66 completion; author did not
provision/control runtime schemas, shared API, browser or restart processes.
Independent technical/design/browser proof and PM final regression/acceptance
remain separate work. All66 old HG3 supporting-evidence gaps remain disclosed.

### D independent R2 extension — revision before stored-source decoding

The independent pure counterexample demonstrated that an owned portfolio with
corrupt request_json and a foreign/random explicit revision reached the preserved
WorkspaceStore._record's source decoder before its revision lookup, returning503
instead of generic404. Its original two-case red script/log remain unchanged.
This is a real ordering finding in the new D boundary, not a financial result bug.

Only new analytics_context production code was repaired: an identity-only owned
portfolio query (no request_json fetch) and explicit revision existence check now
precede _record. ACCOUNT visibility also uses that raw pinned ledger/revision
sequence before source decoding. The sealed persistence helper remains unchanged.
The added actual PG/in-process ASGI regression corrupts the saved request JSON:
foreign/random revisions and foreign/later account scopes return404, while valid
owned initial/later revisions/scopes retain503 SAVED_SOURCE_DIFFERS. Disk source
work is poisoned in the same test to prove it is not reached prematurely.

An intermediate affected15-D actual run passed in20.896s. The final identity-only
query candidate then passed **159 pure tests,3.524s**, and **15 actual PG plus
in-process ASGI tests,21.149s**, zero failures/skips. Logs are
`backend-pure-revision-order-final.log` and `backend-pg-revision-order-final.log`
in the D temporary directory. Existing C/B2 suites were not redundantly rerun for
this bounded order change; independent combined/full regression follows. Earlier
159/66 and the original R2 red/freeze remain separate historical evidence.

The sole production path changed after the first author freeze is
analytics_context.py. PM was notified before edits; the already-running shared
API does not autoreload, so these disk/in-process checks are not proof of a
restarted process. Author has not touched shared API/browser/process controls.
PG is released for PM's restart and independent validation against the new freeze.

## F1 R1 (2026-10-25)

Increment R1 of `implementation/CP7_F1_REAL_PATH_DESIGN.md` (section 7.1, R1 row): the real
authority core, the scope core, the X1 design and the publisher tool. Author: the Engineer.
This is the author's own record. It is not a review, and nothing in it is declared reviewed.

### Result, stated first

**The R1 SQL has been executed, on PostgreSQL 17.11 (Homebrew), and the R1 tests pass after
the review-fix round (stage 3): 221 tests (119 pure, 102 PostgreSQL), no failures, no errors, and
no skips with the PG command.** The record has three stages. Numbers inside stages 1 and 2 are
those of their time; the current numbers are in "Test results" and in the stage 3 subsection.

1. **Stage 1 (written first).** No PG-capable role had been supplied (`finweb_dev` is not a
   superuser; `initdb` of a private cluster fails in the sandbox with a `shmget` "Operation
   not permitted"), so the 74 PG tests were written and skipped, with this exact reason:
   `cannot provision a disposable database as 'finweb_dev': REFUSED: admin role must be a superuser that can CREATE ROLE and CREATE DATABASE. Set FINWEB_PG_ADMIN_USER to a superuser role of the development cluster (the supplied FINWEB_PG_USER is used when it is not set)`
2. **Stage 2 (PD-0071).** The owner lent the dev superuser `<os-user>` to the test kits
   (`FINWEB_PG_ADMIN_USER=<os-user>`, `/tmp/.s.PGSQL.5432`, inside the sandbox), only for the
   kits' own `finweb_it_rw_<hex8>` throwaway databases and roles. The kit used it for nothing
   else, and no interactive SQL was run as that role. The main session's first run of the 74
   PG tests gave `Ran 74 tests in 47.145s` / `FAILED (failures=1, errors=1)`. Both were
   defects in the tests, not in the SQL (below). After the repairs and two additions the three
   PG modules gave 76 tests, all passing.
3. **Stage 3 (review-fix round, 2026-10-25).** The independent technical review of R1 returned
   PASS_WITH_FINDINGS (4 MEDIUM, 10 LOW, no HIGH; `reviews/TECH_REVIEW.md`, "F1 R1 build -
   independent technical review (2026-10-25)"). Every finding is addressed or answered below
   in "Stage 3: the review's findings, one by one". The design was not edited.

The two first-run defects, and what PostgreSQL showed:

- **ERROR** `test_the_loader_holds_nothing_in_r1_and_cannot_publish`. The probe
  `INSERT INTO t SELECT * FROM t` as the loader raised `GeneratedAlways` (SQLSTATE 428C9, a
  `GENERATED ALWAYS` identity column) instead of a privilege refusal. PostgreSQL raises that
  while it rewrites the statement, before the privilege check at executor start, so the probe
  showed nothing about privilege. It is now `INSERT ... DEFAULT VALUES`, `DELETE` and
  `TRUNCATE` for every table, and each is refused with 42501.
- **FAIL** `test_naming_the_guard_fires_it_at_once_and_a_non_deferrable_key_cannot_be_named`
  ("Error not raised"). The first half held: naming the deadline guard fires it at the `SET
  CONSTRAINTS` statement (`RW_DEADLINE`). The second half was my assumption and is false:
  **PostgreSQL 17.11 accepts `SET CONSTRAINTS "<schema>"."<not deferrable key>" IMMEDIATE`
  silently (nothing to fire); it refuses only `... DEFERRED` (42809, "is not deferrable"). A name
  that does not exist is refused in both forms (42704).** The test is split into
  `test_naming_the_guard_fires_it_at_once` and a recorded-behaviour test that asserts exactly
  this. The design never claimed the refusal I had expected; it cites the manual's "must all be
  deferrable" as the reason not to name the lease-to-root-link key (3.2), and that choice
  stands (no product path names it). See the observations below.

Mutation checks (SQL edited by hand, tests run, SQL restored; each restored by a second edit
and re-read): (1) the deadline guard's `RAISE` disabled: 4 tests fail (the COMMIT refusal, naming
the guard, the root-link named form, and the observed-behaviour test); (2) the `LEAST` cap
removed: 3 tests error; (3) the pending-mark refusal removed from admit: 2 withdrawal tests
error, **but `test_overlapping_admissions_stop_while_a_withdrawal_runs` still passes**, so it is
a soak check and not a proof that the mark stops admissions (the first withdrawal test is);
(4) the in-flight marker truncated to milliseconds: the in-flight test fails on its
1-microsecond assertion (`timedelta(microseconds=474)`).

### Stage 3: the review's findings, one by one

Each fix was verified against the reviewer's own evidence (the same scenarios, rebuilt as tests)
and then by a mutation of the code, run on the final SQL and Python (hand edit, run, restore,
re-read). "Where" gives files; line numbers of tests are in the tables below.

| Finding | What was wrong | What changed, and where | Test that now fails the defect |
|---|---|---|---|
| **M-1** (second door to `TEST_SWITCH`) | `build_snapshot` and `write_proposal` accepted `SCOPES["TEST_SWITCH"]` with no switch. | `real_scope.py`: `SCOPES` is a read-only `MappingProxyType`; `resolve_scope` is the only function that makes a `ResolvedScope` (private `_MINT`); `require_resolved` refuses anything else with `RW_SCOPE_UNRESOLVED`. `real_proposal.py`: `build_snapshot` and `write_proposal` take only a `ResolvedScope`; the old body is the private `_build_snapshot`; `verify_proposal` reads the scope from the bytes (data) and cannot hand it back to a builder. Docstring of the old claim corrected. | `test_real_scope.py` `SecondDoorTests` (5 tests: scopes are looked up in two functions only; only the switch mints; every build call site; every public function that takes a scope is one the test knows; every building function refuses every bare form of `TEST_SWITCH`), `test_real_proposal.py` `test_the_builder_and_the_writer_are_not_a_second_door_to_test_switch`. Mutant (builder takes a bare `ScopeDef`): 3 tests fail. |
| **M-2** (REAL-labelled invented content) | A test built invented content in the REAL scope with `synthetic: false` and `REAL_SOURCE`. | Every R1 test was searched (`REAL_SOURCE`, `synthetic`, `"REAL"`, `SCOPES["REAL"]`). No test now writes or verifies invented content under the REAL scope's labels: the only REAL-scope documents are the test scopes' bytes with the scope field alone changed to REAL (synthetic sources and labels, no `REAL_SOURCE`, asserted), which must be refused (`RW_ORIGIN_MISMATCH`). The one `REAL_SOURCE` string left is an input that must be refused at build (`RW_ORIGIN_MIXED`, `test_real_proposal.py:131`), never written. No test needs a `synthetic: false` invented record, so none exists. **The REAL branch of the writer and verifier is therefore not exercised in R1, by design (R4b, on real inputs).** | `test_real_proposal.py` `test_writer_output_verifies_for_every_scope`, `test_origin_labels_must_match_the_scope`; `test_real_scope.py` `test_invented_data_is_never_marked_synthetic_false`. |
| **M-3** (withdrawal said "nothing was recorded" after the mark committed) | When step 2 ended by statement timeout, cancel or deadlock, the output said nothing was recorded although the drain mark was committed. | `real_workspace_store.py` `withdraw`: from the moment the mark is committed every outcome of step 2 says so. A wait that ends by lock timeout, statement timeout, cancel or deadlock is `NOT_YET_EFFECTIVE` (exit 3) with the mark, the pending refusal, the in-flight lease lines; a gateway refusal of step 2 says the mark stays recorded; an UNKNOWN names the recorded mark. The first step's output no longer claims a record it did not make. | PG `withdrawal.py:205` is the reviewer's run (publisher connection `statement_timeout` 1 s, tool `lock_timeout` 4 s): asserts the tool output (exit 3, no "nothing was recorded", the mark line, "(QueryCanceled)", the blocking lease), the mark row in the database, no new generation, new admissions refused with the pending code, the status view, and the rerun continuing from the same mark. `:239`: cancel is exit 3, a terminated backend is exit 4 naming the mark. Pure `test_real_publisher_tool.py:496`, `:513`, `:521`, `:535`, `:546`. Mutant (revert): 2 PG and 2 pure tests fail. |
| **M-4** (no PG test on a `TEST_SWITCH` context) | No PG test admitted, bounded or refused a lease on a `TEST_SWITCH` context. | `test_postgres_real_gateway_x1.py`: `X1Case.SCOPE` and `live()` (the stored bytes are asserted to be of the scope under test, synthetic labels, no `REAL_SOURCE`); `TestSwitchAdmissionAndLapseTests` (6 tests) and `TestSwitchCappedDeadlineTests` (4 tests) repeat every admission, lapse, cap, table-check and COMMIT-guard test on `TEST_SWITCH`. | Mutant S19 (admit refuses every `TEST_SWITCH` context in a TEST install): 9 tests fail, all in the two new classes. Mutant S20 (the guard exempts `TEST_SWITCH` leases): 1 test fails (`TestSwitchCappedDeadlineTests.test_a_read_held_past_its_deadline...`). |
| **Commit outcome** (PM decision on the reviewer's item 3) | `_transact` treated some errors at COMMIT as a definite rollback. | `_transact` and `_classify`: the stricter E4 rule. At or after the commit point only a gateway `RW_*` code on a connection back at IDLE is a definite refusal; every other error at COMMIT (a lock timeout included) and every missing answer is UNKNOWN, which says to check the status view, retries nothing and never prints "recorded nothing". Before the commit point a refusal on a usable IDLE connection stays a definite rollback. Docstring cites F2 at `guarded_workspace_store.py:271-272` (it maps `OperationalError`/`InterfaceError` to UNKNOWN and lets other database errors propagate) and states where R1 is finer and where it is stricter. **Design not edited**: this follows design 3.1 (E4) and is stricter than design 4.4 item 4 ("an error reply to COMMIT means the transaction rolled back"); the PM chose the stricter rule and will note the two passages. | Pure `test_real_publisher_tool.py:222`-`:325` (`CommitOutcomeTests`): `:278` every non-gateway error at the commit is UNKNOWN (a lock timeout, a deadlock, a cancel, a constraint error without a code, a driver error), `:288` the one definite refusal, `:306` the same errors before the commit point. Mutants: lock timeout at COMMIT reported as `LOCK_TIMEOUT`: 2 tests fail; a non-gateway error at the commit reported as a refusal: 5 tests fail. |
| **L-1** (the marker namespace is open to every connected session) | Any session with CONNECT can forge a marker, deny an admission by holding an exclusive lock on a marker key (the reviewer's run: `LockNotAvailable`, or a wait with no lock timeout), omit one, or be listed twice. | `real_workspace_v1.sql`: markers use `pg_try_advisory_xact_lock_shared` (a session holding a conflicting exclusive lock can no longer delay or deny an admission, it can only leave the lease unnamed); the exclusive root and publish locks are masked below 2^62; a comment at the top of the file reserves the key ranges, says the markers are advisory not authoritative, and lists the limits that remain (a session can forge a marker, withhold one, or be listed twice) and what R3 and later increments must respect. **Left, and why:** forging, omission and double listing remain documented limits: advisory locks need no privilege, and nothing short of restricting who may connect narrows them; safety does not read the markers. | PG `x1.py:671` (a loader's exclusive lock on the marker key does not delay the admission, which is unnamed), `:693` (characterisation: a forged marker is listed), `:710` (an admission's locks in `pg_locks`: one exclusive below the marker range, two shared markers, the key encodes `complete_by`); static `test_exclusive_advisory_locks_stay_out_of_the_marker_key_range`. Mutant (blocking lock again): the first test errors on its 5 s `lock_timeout`. |
| **L-2** (an admission queued on the root lock completes after the drain mark, and the withdrawal does not name it) | Admit checked the pending mark and sampled the clock before it took the root lock, so an admission that queued behind a stalled lease was ADMITTED after a mark was committed. | `rw_admit` checks the pending mark again after it takes the root lock (a new statement, so under READ COMMITTED it sees marks committed during the wait), so that admission is refused with `RW_WITHDRAWAL_PENDING` and writes no lease. **Left:** the withdrawal's blocker list still does not name an admission that is queued on the root lock (it holds only the head share; its marker is taken after the lock). Safety was never affected: the head share blocks the withdrawal either way. | PG `withdrawal.py:268`. Mutant (second check removed): that test fails. Static `test_admit_checks_the_drain_mark_again_after_it_holds_the_root_lock`. |
| **L-3** (`_transact` re-raised every database error with no gateway code, and its docstring stated a rule the code did not follow) | At the CLI that became a traceback and exit 1, which is none of the tool's five statuses; the docstring cited F2's rule but R1 departed from it in three branches. | Same rule as the commit outcome above: at or after the commit point such an error is UNKNOWN; before it, on a usable IDLE connection, a definite rollback reported as `RW_STATEMENT_FAILED` (exit 2). Nothing is re-raised. The docstring now states the rule the code follows and each departure from F2. | Pure `test_real_publisher_tool.py:278`, `:260`. |
| **L-4** (two concurrent drain marks both said "recorded") | The second withdrawal printed that it had recorded a mark that the first had made. | `rw_withdraw_mark` returns seven columns (issuer and PD id added) and falls back to reading the winner when `INSERT ... ON CONFLICT DO NOTHING` created nothing; the tool prints "already recorded" and names the other issuer and reference, and the generation carries the first mark's issuer. | PG `withdrawal.py:300` (the first mark held open in a transaction, the second waits on it). Pure `test_real_publisher_tool.py:546`. Mutant (the fallback says created): that test fails. |
| **L-5** (no code of its own for a completed withdrawal) | A withdrawn context and a right never granted were both `RW_RIGHT_REFUSED`. | `rw_admit` raises `RW_WITHDRAWN` when the current generation names a drain mark and all four rights are false; `RW_RIGHT_REFUSED` remains for a right never granted and for all four rights turned off by a renewal that names no mark. | PG `x1.py:118`, `withdrawal.py:139`. Mutant (code replaced): 2 tests fail. |
| **L-6** (renew output not under the "never within" test) | `renew` was not tested for "within" or "margin". | `test_real_publisher_tool.py:345` covers every renew output. | Mutant P5a (renew says "within"): that test fails. |
| **L-7** (docstring cites the soak test as proof) | The characterisation test's docstring named the overlap soak as the proof that the mark stops admissions. | Docstring at `withdrawal.py:424` now cites `test_withdrawal_during_an_in_flight_read_marks_first_waits_then_applies` and says the soak also passes without the mark. | (docstring) |
| **L-8** (the CLI exited 1 with a traceback on malformed input) | `--rights-json '{bad'`, a missing proposal file or a malformed evidence file each gave a traceback and exit 1, none of the tool's statuses. | `real_workspace_store.py` `_read_input`, `_json_input`, `_read_evidence`, `main`: typed refusals `RW_INPUT_UNREADABLE` and `RW_SHAPE`, and (my addition) `RW_CONNECT_FAILED` when the connection cannot be made, each with exit status 2 and no traceback; nothing is written, as before. | Pure `test_real_publisher_tool.py:684`. |
| **L-9** (the self-validation was stale or inexact in two places) | (1) "Open: a stray test process" said the process was still alive; PD-0071's addendum records that the main session ended it and dropped its database. (2) The `_transact` claim repeated the inexact F2 citation. | (1) The note now records the cleanup, and the read-only catalog query of this round found no `finweb_it%` database or role. (2) The decision text and the docstring are corrected (see the commit-outcome row). Also refreshed: the counts, the function count (21), the line numbers of every table, the markers item and the REAL-branch statement. | (this file) |
| **L-10** (S1, S16, S18 survived the PG tests) | The three strict comparisons were pinned by static text only. | One predicate, `rw_reached(now, limit)` = `now >= limit` (the first refused instant is the limit itself); the guard, the lapse, the publish and renewal floors and the regression test all call it, and the static test pins that nothing else compares an instant with the clock. **Behavioural, two parts.** `StrictComparisonTests` (`x1.py:562`) calls the predicate as the owner with equal instants and one microsecond either side. `PredicateWiringTests` (`x1.py:586`) shows that each call site CALLS the predicate, clock first and limit second: in an install of its own the owner role replaces `rw_reached` with one that is true 30 s early (or 30 s late for the regression test), and each site must change its answer; a site rewritten inline cannot. **What this cannot do:** the real clock never produces an instant equal to a stored one at a call site and no hook may supply a time, so the equality edge is shown on the predicate, and the wiring is shown by the replacement; an inline rewrite that keeps the behaviour (for example `p_valid_until <= v_now`) is also refused by these tests and by the static test, by design. | See the mutation table below: S1, S16, S18 each fail one PG test. |

Mutation results of this round (S-numbers are the reviewer's). Everything was restored and
re-read; the final suites above ran on the restored files.

| Mutant | Result |
|---|---|
| S1: the deadline guard written inline as `clock_timestamp() > NEW.complete_by` | killed: `PredicateWiringTests.test_the_deadline_guard_at_commit_calls_the_predicate...` fails (1 of 102 PG tests) |
| S1 at the predicate: `>=` changed to `>` in `rw_reached` | killed: `StrictComparisonTests.test_the_first_refused_instant_is_the_limit_itself` fails (1 of 102) |
| S16: the lapse written inline as `v_now > v_hist.valid_until` | killed: `PredicateWiringTests.test_the_lapse_of_a_lease_calls_the_predicate...` fails (1 of 102) |
| S18: the renewal floor written inline as `p_valid_until < v_now` | killed: `PredicateWiringTests.test_the_floor_of_a_renewal_calls_the_predicate` fails (1 of 102; the first run of this mutant raised a `KeyError` in the test instead of failing, which I corrected so it fails cleanly) |
| S18 on the publish floor, same form | killed: `test_the_floor_of_a_publish_calls_the_predicate` fails |
| S19: admit refuses every `TEST_SWITCH` context in a TEST install | killed: 9 tests (3 failures, 6 errors), all in `TestSwitchAdmissionAndLapseTests` and `TestSwitchCappedDeadlineTests` |
| S20: the deadline guard exempts `TEST_SWITCH` leases | killed: 1 failure, `TestSwitchCappedDeadlineTests.test_a_read_held_past_its_deadline_is_refused_at_commit...` |
| P5a: renew says "within the term" | killed: `RenewTests.test_no_renew_output_ever_says_within_or_margin` fails |
| M-1: `build_snapshot` accepts a bare `ScopeDef` | killed: 3 tests fail |
| M-3: step 2 ended by statement timeout or cancel reverted to "nothing was recorded" | killed: 2 PG and 2 pure tests fail |
| L-2: the second mark check after the root lock removed | killed: `withdrawal.py:268` fails |
| L-4: the fallback reports `created = true` | killed: `withdrawal.py:300` fails |
| L-5: `RW_WITHDRAWN` replaced by `RW_RIGHT_REFUSED` | killed: 2 tests fail |
| L-1: the marker taken with a blocking lock again | killed: `MarkerTests` first test errors |
| Commit outcome (a): lock timeout at COMMIT reported as `LOCK_TIMEOUT` | killed: 2 pure tests fail |
| Commit outcome (b): a non-gateway error at/after the commit reported as a refusal | killed: 5 pure tests fail |

The four mutations of stage 2 (the deadline guard's `RAISE` disabled, the `LEAST` cap removed, the
pending-mark refusal removed from admit, the marker truncated to milliseconds) were run on the
earlier SQL and were NOT re-run in stage 3.

### Test results (actual, this session)

Stage 3 (final, after the review-fix round); the PG command is
`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`
in front of the same `uv run ... unittest` command.

| Run | Summary lines |
|---|---|
| The 7 R1 modules only, no PG variables | `Ran 221 tests in 4.240s` / `OK (skipped=102)` |
| The 7 R1 modules only, PG command | `Ran 221 tests in 66.341s` / `OK` (no skips) |
| Default suite: `uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .` | `Ran 3155 tests in 162.187s` / `OK (skipped=543)` |
| Full suite, PG command | `Ran 3155 tests in 291.654s` / `OK (skipped=113)` |

R1 modules, one by one (the PG modules run with the PG command; without it every test of the
three PG modules skips): `test_real_scope` 25, `test_real_proposal` 17, `test_real_publisher_tool` 52,
`test_real_gateway_static` 25 (pure, 119 in all); `test_postgres_real_gateway_core` 40 (1.640 s),
`test_postgres_real_gateway_x1` 45 (49.166 s), `test_postgres_real_gateway_withdrawal` 17 (11.614 s)
(PostgreSQL, 102 in all). 119 + 102 = 221.

Baseline before R1 was 2934 tests (default skipped 441; with PG variables skipped 113). R1 adds
221 tests: 119 pure and 102 PG (3155 = 2934 + 221). In the default suite the 102 PG tests skip
(441 + 102 = 543). With the PG command they all run and pass, and the skip count is the baseline
113, which comes from other modules' own conditions and is unchanged by R1.

History, kept for the record. After stage 2: R1 modules 176 tests (100 pure, 76 PG), default `Ran 3110
tests in 154.063s` / `OK (skipped=517)`, full suite with the PG command `Ran 3110 tests in 269.662s` /
`OK (skipped=113)`. Stage 1: default `Ran 3108 tests` / `OK (skipped=515)`; with PG variables and no
admin role `Ran 3108 tests` / `OK (skipped=187)` (the 74 PG tests skipped); the main session's first
stage-2 run of the 74 PG tests `Ran 74 tests in 47.145s` / `FAILED (failures=1, errors=1)`.

### Product path or E11 crafted fixture

Marked per design 4.4 and 3.2. "Product path" means the test calls the product publisher
tool, the product admit wrapper or the product factory. "E11 crafted" means the disposable
database's owner role writes a row that no product command can write. No R1 test is product
evidence for the REAL install kind: product code writes the install kind `TEST` only
(`install_test_gateway`, `real_workspace_store.py`; static test
`test_only_a_test_install_is_ever_written_by_product_code`), and the one `REAL` row exists
only in `GatewayKit.install(kind="REAL")`, written by the owner of a disposable database whose
name carries `finweb_it_rw_` (the `finweb_real` prefix is refused). Test-scope snapshots come
from `real_scope.make_snapshot` (the factory), never a test helper.

All paths below are under `tests/product/`. Line numbers are those of the files at the end of
stage 3 (the `def` line of the test). "PG" means PostgreSQL 17.11 on the shared dev cluster, in a
throwaway database. Abbreviations: `core` = `test_postgres_real_gateway_core.py`, `x1` =
`test_postgres_real_gateway_x1.py`, `wd` = `test_postgres_real_gateway_withdrawal.py`, `static` =
`test_real_gateway_static.py`, `tool` = `test_real_publisher_tool.py`, `scope` = `test_real_scope.py`,
`proposal` = `test_real_proposal.py`.

| Exit item or test | Where it is shown (file:line) | Path | Executed |
|---|---|---|---|
| Snapshot, history with one expiry-basis entry per member source, head, drain mark, mode, install kind with `W` | `core:62` (install row), `:249`, `:258`, `:269`, `:279`, `:291` (immutability, chain, mark order); `static:210`, `:216` (triggers, mark columns) | product install; crafted rows only to attempt forbidden writes | yes (static and PG) |
| Four roles; loader holds no table privilege | `core:91`, `:103`, `:125`, `:140`, `:158`, `:177`, `:194`; `static:173`, `:192`, `:202` | product install | yes |
| Lease and root-link tables; `rw_admit` | `x1:62`, `:89`, `:135`; `static:92`, `:105` | crafted root fixture (design 3.2); admit is the product function | yes |
| `complete_by = LEAST(admitted_at + W, valid_until)` and its table CHECK | `x1:174` (both orders of LEAST), `:189` (CHECK); `static:142` | crafted root fixture; the crafted lease row is an E11 probe | yes |
| Deferred root-link-to-portfolio FK | `core:708`, `:726`; `static:164` | E11 crafted (a root-link row written directly) | yes |
| `rw_list_roots` | `core:687` | crafted roots | yes |
| Deadline guard as a constraint trigger of its own, unique name | `x1:292`; `static:148` | product install | yes |
| Proposal format, pure writer and verifier | `proposal:41`, `:49`, `:57`, `:70`, `:77`, `:81`, `:97`, `:131`, `:146`-`:258` | product path (pure) | yes |
| Publisher commands publish, renew, withdraw; mandatory decision reference; exit statuses | `tool:130`-`:560` (pure, scripted connection), `:644`-`:730` (command line); `core:299`, `:412`; `x1:436`; `wd:542`; `static:224`, `:272`, `:297` | product path | yes |
| Expiry evidence (derived kind, upper-bound wording, no lower bound) | `core:452`, `:475`, `:489`, `:499`, `:510`; `tool:136`, `:345`, `:561`; `static:289` | product path | yes |
| Renewal with an earlier `valid_until` (E25) | `x1:451`, `:471`, `:483`, `:505`, `:514`, `:534` | product path on a crafted root | yes |
| Scope core: definitions, factory, reviewed switch (one door: `ResolvedScope`), install-kind guard (4.2) | `scope:50`-`:316` (`TestSwitchTests` `:88`, `SecondDoorTests` `:196`, `InstallKindGuardTests` `:251`); `proposal:97`; PG side `core:599`, `:611`, `:617`, `:653`, `:660`, `:668` | factory is product path; REAL-kind install is E11 crafted | yes |
| X1: `valid_until`, trusted clock, admission under lock, capped deadline, cancellation, on both test scopes | `x1:62`-`:741` (`TestSwitchAdmissionAndLapseTests` `:735`, `TestSwitchCappedDeadlineTests` `:741` repeat the admission, lapse, cap and guard tests on `TEST_SWITCH`); `wd:484` | see T07 below | yes |
| The strict comparisons of time | `x1:562` (`StrictComparisonTests`: the predicate at equal instants), `:586` (`PredicateWiringTests`: each site calls the predicate); `static:113` | predicate: E11 crafted call by the owner; wiring: E11 crafted replacement in an install of its own | yes |

Listed tests:

| Test | Where | Path | Executed |
|---|---|---|---|
| T01 (edit a proposal, nothing live changes) | PG: `core:318`; pure: `proposal:41`, `:232`; no env, FileStore or guarded import: `static:238` | product path | yes |
| T02 (two connections, blocking-pid causality) | `wd:71` (a renewal waits for a reader; `pg_blocking_pids` names the reader), `:89`, `:124`, `:139` (withdrawal during an in-flight read: mark first, then wait, then apply), `:171`, `:205`, `:239`, `:268` (a queued admission is refused by a mark committed while it waited), `:300` (two concurrent marks), `:377` | product path on a crafted root | yes |
| T04 (roles and privileges) | `core:78`, `:91`, `:103`, `:125`, `:140`, `:158`, `:177`, `:194`, `:204`, `:222` | product install | yes |
| T07 R1: admit before `valid_until`, refused at or after, four purposes (and `RW_WITHDRAWN` after a completed withdrawal) | `x1:62`, `:89`, `:105`, `:118`; the same four on `TEST_SWITCH` through `x1:735` | product path on a crafted root | yes |
| T07 R1: the lease records instant, `valid_until`, `complete_by`; crafted later `complete_by` refused | `x1:62`, `:189` | crafted lease row is E11 | yes |
| T07 R1: clock regression refused | `x1:274` (own install named `regress`, a stored instant moved ahead by the owner: E11 crafted); the call site's wiring `x1:645` | E11 crafted | yes |
| T07 R1: overlapping admissions never refuse each other | `x1:243`; order in SQL: `static:92` | product path | yes (a race: it did not fail, and it cannot prove the absence of a race) |
| T07 R1: forward jump has no hook | `static:81` (clock is `clock_timestamp()` only, no override); policy by `x1:89` | static | yes |
| T07 R1: renewal needs a reference, not by executor or loader; valid renewal restores admission and a bound root resolves; equal date restores rights after a withdrawal | `x1:436`, `:451`, `:471` | product path | yes |
| T07 R1: date correction, pin scenario, term already renewed, refused renewals append nothing, correction waits for an in-flight read and times out | `x1:483`, `:505`, `:514`, `:534` | product path | yes |
| T07 R1: both orders of the cap; positive control; refused at COMMIT with all session timeouts 0 | `x1:174`, `:208`, `:235`; the same on `TEST_SWITCH` through `x1:741` | product path; read-phase lease only | yes |
| T07 R1: withdrawal and the drain mark | `wd:139`, `:171`, `:205`, `:239`, `:268`, `:300`, `:329`, `:348`, `:464`, `:542` | product path | yes |
| T07 R1: no-expiry only with evidence, omission cases | `core:452`, `:475`, `:489` | product path | yes |
| FF1-C03 (a separate proposal edit cannot move the live snapshot; full versus used digest; swapped or stale refused) | `proposal:57`, `:70`, `:221`, `:232`, `:238`; `core:318`, `:400` | product path | yes |
| FF1-C04 (actual role closure; loader cannot advance head, mode or rights; issuer and reference recorded) | `core:125`, `:177`, `:194`; `wd:329`, `:542` | product install | yes |
| FF1-C06 (expiry kind derived, never defaulted; unknown never maps to NONE; lease is validity at admission; clock) | `core:452`-`:510`; `x1:89`, `:208`, `:243`, `:274` | product path | yes |
| Reduced FF1-C12 (idempotent re-run of an interrupted publish; acknowledgement loss is UNKNOWN until reconciled) | `core:343`, `:363`, `:380`; `wd:521`; pure `tool:222`-`:325` (`CommitOutcomeTests`) | product path | yes |
| 4.2 scope tests (switch refused outside its door and by every second door; install-kind guard in both directions; asserts the install-kind code only) | pure `scope:88`-`:316`, `proposal:97`; PG `core:599`, `:611`, `:617`, `:653`, `:660`, `:668` | factory product path; REAL-kind install E11 crafted | yes |
| Fact 17, showing 1: the named `SET CONSTRAINTS "<schema>"."rw_root_link_portfolio_fkey" IMMEDIATE` fires that key only and leaves the guard pending | `x1:320` (three parts: the key fires at the SET statement; with the portfolio row present the SET passes and the guard still refuses at COMMIT with the whole transaction rolled back; the control commits), `:364` (naming the guard fires it at once) | E11 crafted (second root written by the owner in one transaction) | yes |
| Fact 17, showing 2: the deadline guard's COMMIT-time refusal (`RW_DEADLINE`, connection IDLE, no lease row remains) | `x1:208` | product path | yes |

### What PostgreSQL did, item by item (the eleven "not shown" items of stage 1)

Server: PostgreSQL 17.11 (Homebrew), as the kit logs at each provisioning
(`real-gateway kit: PostgreSQL 17.11 (Homebrew), disposable database finweb_it_rw_<hex8>`).
"Observed" means a passing test asserts it; where the test is a recorded-behaviour test it says
so. Nothing here is a claim about another server version.

1. **Install: observed.** The product installer sent the whole `real_workspace_v1.sql` body
   through psycopg 3.3.6 in one `execute`, and every install (core, x1, wd, regress, wiring and
   the crafted-REAL install) completed. The catalog test (`core:78`) counts 21 functions
   (`rw_reached` was added in stage 3).
2. **Advisory-lock markers: observed, and mutation-checked.** An uncommitted lease is named from
   public `pg_locks` by `rw_in_flight` (`x1:534` and `wd:171`, `:338` print "blocking lease:
   backend N, complete_by ..."). The marker round-trips `complete_by` to within 1 microsecond
   (stage 2: the assertion is `<= 1 us`; truncating the key to milliseconds failed it with a 474 us
   difference); stage 3 `x1:710` reads the marker's key back from `pg_locks` and compares it with
   the lease's `complete_by` in microseconds. Stage 3 also shows what stage 1 could not: the
   gateway's exclusive root lock lies below 2^62 and the shared deadline marker in
   [2^62, 2^62 + 2^53) (`x1:710`, and the mask in the SQL), a loader's exclusive lock on a marker
   key no longer delays an admission (`x1:671`, markers are try-locks), and a forged marker is
   listed as a blocker (`x1:693`, a documented limit: the list is advisory, safety never reads it).
3. **`SET CONSTRAINTS`: observed, with one wrong expectation of mine.**
   - A named `SET CONSTRAINTS "<schema>"."rw_root_link_portfolio_fkey" IMMEDIATE` fires that key
     only (`x1:320`): with no portfolio row the SET statement fails with a foreign-key
     violation naming that key; with the row present the SET passes and the deadline guard,
     still pending, refuses the COMMIT with `RW_DEADLINE` and the whole transaction (second root
     included) is rolled back; the control commits. Fact 17's "named form" claim is shown.
   - Naming the guard fires it at once (`x1:364`).
   - **Naming a NOT DEFERRABLE key `IMMEDIATE` is accepted and does nothing; `DEFERRED` is
     refused with 42809 "is not deferrable"; a missing name is refused with 42704 in both forms**
     (`x1:378`, recorded behaviour). The expectation I first wrote (a refusal in every form)
     was mine, not the design's.
4. **COMMIT-time refusal: observed from the client side.** The `COMMIT` statement returns the
   error `RW_DEADLINE`, the connection is `IDLE` afterwards, and no lease row remains
   (`x1:208`, both orders of the cap, all four session timeouts 0; and on a `TEST_SWITCH`
   context through `x1:741`). Still not shown: the order
   of steps inside PostgreSQL's commit (only the client-visible effect is), and the
   commit-processing gap (a stall between the guard's check and the commit record), which no
   client can probe.
5. **Share-overtakes-exclusive: observed, and it is true.** Recorded-behaviour test
   `wd:424`: A holds `FOR SHARE` on the head row; B's `FOR UPDATE` queues, and
   `pg_blocking_pids(B)` is `[A]`; C's `FOR SHARE` is then granted at once, B stays queued after A
   leaves, `pg_blocking_pids(B)` is then `[C]` (the server names the member it is waiting on, not
   both), and B is granted when C ends. So the starvation reading of design section 9 is real server
   behaviour, and the drain mark is what the design uses against it: the first withdrawal test
   (`wd:139`) shows the mark alone refusing a new admission while a reader holds a share
   lock. The overlap soak (`wd:377`) ended WITHDRAWN in all of five runs, with about 1,000
   admissions per loop in the second, and a loop saw the pending code in each run. It passes
   without the mark refusal (stage 2 mutation 3), so it is a soak check and not the proof; the
   characterisation test's docstring no longer cites it as the proof (L-7).
6. **`TRUNCATE` ordering: observed.** For the four tables another table references (snapshot,
   history, drain mark, root link) PostgreSQL's own foreign-key refusal (`FeatureNotSupported`) comes
   first and the immutability trigger is not reached; for the unreferenced `rw_install`, `rw_head`,
   `rw_lease` and `rw_mode` the trigger refuses with `RW_IMMUTABLE`
   (`assertTruncateRefused` in the kit; `core:249`-`:291`).
7. **`proconfig`: observed.** Each function carries one element,
   `search_path=pg_catalog, <schema>, pg_temp`; the test splits at `=` and strips spaces
   (`core:78`).
8. **Guard-bypassing session: observed** (`x1:415`, a characterisation, not a requirement). A
   session that fires the guard early, by `SET CONSTRAINTS ALL IMMEDIATE` or by name, and then
   stalls past `complete_by` commits unchecked: the lease row is committed after its own deadline,
   in both variants. This is the disclosed limit of design 3.1 / section 9.
9. **Value not delivered after a refused COMMIT: not shown.** It belongs to R5's read tail.
10. **REAL install kind and REAL scope: observed on the crafted fixture only.** Publish refuses
    every REAL-scope snapshot with `RW_REAL_SCOPE_UNWIRED` until R2 wires the validators
    (`core:599`); a crafted install that reports REAL refuses both test scopes at publish and at
    admit (`core:653`, `:660`, `:668`). No REAL context was ever published or admitted by any
    code. The REAL branch of the proposal writer and verifier is likewise not exercised in R1 (M-2):
    R4b does it, on real inputs.
11. **R2 to R8: not built and not shown** (no write fence, row policy, journal, seal, bundle guard,
    archive, `md_*` read functions, guarded load, O1-O3 validators, loader grants, installer or
    preflight, launcher or probe).

### Closed: a stray test process (was open in stage 2)

During stage 2 I ran, in the foreground with a 200-second tool timeout, a first version of the
share-overtake test (now `wd:424`). It had a cleanup-order bug (it rolled back the waiting
connection before the lock holder that was keeping it waiting, and psycopg serialises a connection
behind its running statement), so the test never returned, and the sandbox refused `kill` on the
process. **This is closed.** The main session stopped the task (`bhg3rjuy9`) and, with the owner's
approval, dropped that run's database `finweb_it_rw_0fbb0a46` and its roles; PD-0071's addendum
records it. The test is fixed (holders released first, `Connection.cancel()` for the waiter, a 30 s
`lock_timeout` backstop on the waiter). At the end of stage 3 a read-only catalog query as
`finweb_dev` found no database, role or schema whose name begins `finweb_it` or `rw_`, and every
run of stage 3 was in the foreground (no background process was started).

### Decisions the contracts did not cover (author's choices)

- Lease naming: advisory-lock markers, so an in-flight lease can be named from public
  `pg_locks` without a table write (item 2 above).
- Derivation of the expiry kind is in SQL (admit re-derives from the stored snapshot and
  entries); the Python tool derives it too, for the operator's preview, and the database is
  the authority.
- `W` is per install (one row), whole seconds from 1 to 86400. No default.
- No replay branch in R1's admit.
- The install kind is readable through a definer function (`rw_install_info`), not by table
  privilege.
- Commit-outcome classification (`_transact`, stage 3, the PM's decision on the reviewer's item 3):
  the stricter fail-closed E4 rule. At or after the commit point only a gateway `RW_*` code on a
  connection back at IDLE is a definite refusal; every other error at COMMIT (a lock timeout
  included) and every missing answer is UNKNOWN (exit 4: the tool says so, tells the operator to
  check the status view, retries nothing, never prints "recorded nothing"). Before the commit point
  a refusal on a usable IDLE connection stays a definite rollback: a gateway code is its own
  refusal, any other database error (a statement timeout, a cancel, a deadlock, an error with no
  gateway code) is reported as `RW_STATEMENT_FAILED` with the exception's class name (exit 2), and
  a closed or non-IDLE connection is UNKNOWN. Nothing is re-raised. This replaces the stage 2 text,
  which said that a database error with no gateway code was re-raised. **Relative to F2**
  (`guarded_workspace_store.py:271-272`, `OperationalError`/`InterfaceError` -> UNKNOWN, other
  database errors propagate), R1 is finer before the commit point and stricter at it. **Relative to
  the design**, this follows 3.1 (E4) and is stricter than 4.4 item 4 ("an error reply to COMMIT
  means the transaction rolled back"); the design was not edited, and the PM will note the two
  passages.
- A wait of the withdrawal's step 2 that ends by statement timeout, cancel or deadlock is reported as
  NOT_YET_EFFECTIVE (exit 3), the same state as a lock timeout, because the mark is pending either
  way. A terminated backend (closed connection) is UNKNOWN naming the recorded mark.
- One predicate for every comparison of a stored instant with the clock, `rw_reached(now, limit)`
  = `now >= limit`, which takes both instants as arguments and which no runtime role can call. It
  is what lets a test pin the equality edge; it is not a hook for time (nothing outside the owner's
  tests supplies an instant, and the clock is still `clock_timestamp()` alone).
- A completed withdrawal has the code `RW_WITHDRAWN` (a generation that names a drain mark and has
  all four rights false). The design names no spelling; I chose this one. `RW_RIGHT_REFUSED` stays
  for a right never granted and for a renewal that turns all four rights off without naming a mark.
- `rw_withdraw_mark` returns seven columns (issuer and PD id added), and its second call on the same
  generation reports `created = false` even when the insert lost a race.
- The markers are try-locks and the exclusive locks are masked below 2^62. A queued admission is
  still not named by the withdrawal (L-2, left).
- `ResolvedScope` (M-1) is a token class with a private mint; `SCOPES` is read-only. No design text
  names this mechanism; it is the smallest one that makes the switch the only way and lets a static
  test list every path that yields a `TEST_SWITCH` scope.
- `RW_CONNECT_FAILED`, `RW_INPUT_UNREADABLE` and `RW_SHAPE` for the command line (L-8), all exit 2.
- The kit reads `FINWEB_PG_ADMIN_USER` (falling back to `FINWEB_PG_USER`) for the provisioning
  superuser, because the supplied role is not one. PD-0071 now names `<os-user>` for it. The
  kit also writes one stderr line per provisioning with the server version.
- The `SET CONSTRAINTS` test on a non-deferrable key now records what the server does
  (accepted for `IMMEDIATE`, 42809 for `DEFERRED`) instead of the refusal I first assumed. No
  design text changed and no product code depends on it.
- The characterisation tests (`x1:415`, `x1:693` and `wd:424`) are marked as not product
  evidence in their docstrings; the last is raw SQL by the owner role on the head row.
- `PredicateWiringTests` (`x1:586`) replaces `rw_reached` as the owner role in an install of its own,
  and restores it after each test. That is an E11 crafted act in a disposable database, not product
  evidence, and no product path replaces a function.

### Files

New (all untracked): `src/persistence/real_scope.py`, `real_proposal.py`,
`real_workspace_context.py`, `real_workspace_store.py`, `real_workspace_v1.sql`;
`tests/product/real_gateway_fixtures.py`, `real_gateway_kit.py`, `test_real_scope.py`,
`test_real_proposal.py`, `test_real_gateway_static.py`, `test_real_publisher_tool.py`,
`test_postgres_real_gateway_core.py`, `test_postgres_real_gateway_x1.py`,
`test_postgres_real_gateway_withdrawal.py`. Stage 3 changed, among those (all under `src/persistence/`
and `tests/product/` except this file): `real_scope.py`, `real_proposal.py`,
`real_workspace_store.py`, `real_workspace_v1.sql`, `test_real_scope.py`, `test_real_proposal.py`,
`test_real_publisher_tool.py`, `test_real_gateway_static.py`, `test_postgres_real_gateway_core.py`,
`test_postgres_real_gateway_x1.py`, `test_postgres_real_gateway_withdrawal.py`. No `guarded_workspace_*`
file, no design file and nothing under `.claude/` was edited by this work.

## F1 R4a (2026-10-25)

Increment R4a of `implementation/CP7_F1_REAL_PATH_DESIGN.md` (section 7.1 row R4a; section 7.1a), code part. Author: the
Engineer. This is the author's own record. It is not a review, and nothing in it is declared reviewed. Another engineer
built R2 in the same working tree at the same time; I edited no R2 path (`src/persistence/`, the provenance module, the
`*real*` and provenance tests).

### Result, stated first

**Items 1 to 4 of the brief are built and tested. Item 5 (the code label to `market-data/1.16`) and item 6 (the registry
sync) are NOT done, on purpose: I stopped before the label switch because the Quant's own gate for citing 1.16 is not met
and cannot be met inside this increment.** The reason is in "The gate", below. Nothing was chosen around it.

Tests, both full suites run at the end on the shared tree (with R2's files in it at that moment):

| Run | Summary lines |
|---|---|
| Default (`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`) | `Ran 3240 tests in 159.645s` / `OK (skipped=543)` |
| With PostgreSQL (`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>` in front) | `Ran 3240 tests in 286.178s` / `OK (skipped=113)` |

Baseline at HEAD `11c804a` was 3155 OK. The difference, 85, is my 34 new tests and R2's tests that were in the tree. Two
earlier default runs during the work failed in R2's files only (`test_real_scope` `SecondDoorTests` and
`test_real_gateway_static`, which scan `src/persistence/` and saw R2's new `real_provenance.py` before R2 had updated the
tests); both passed in the later runs. I did not touch them.

### The gate (why item 5 and item 6 are not done)

`methodology/CP2_MARKET_DATA_CONVENTIONS.md` section 11, "When a manifest may cite 1.16" point 1: *a manifest cites
`market-data/1.16` only once items 23-28 and 32-35 are all built*, and the closing paragraph calls a manifest that cites 1.16
earlier "a defect: the id would name a method the code does not run (P12)". The brief and the design (7.1a item 6; E12) list
only the label source (item 23) and A.6 (item 24) before the label. Items 25, 26, 27, 28 and 34 are not built; I checked each
in `src/`:

| Item | What 1.16 requires | State in `src/` today |
|---|---|---|
| 25 | Test V0 for duplicate session dates in every market | `refuse_duplicate_dates` is set only on the CN route (`adapters/alphavantage.py:139`); the US route does not |
| 26 | A.4 item 7 (delivered decimals) on every route | `enforce_delivered_dp` is set only on the CN route |
| 27 | The per-reading gate in ingest, the store constructor, `write_release` and `read_release`: MIC table gains ARCX, BATS, XASE; an unmapped MIC refused; a source with no profile never supplies a real reading; corporate-action admission | `profiles.MIC_MARKET` has five MICs; an unmapped MIC returns no refusal (`listing_market_refusal`); the persistence half is in `src/persistence/market_data_store.py`, which R2 owns |
| 28 | `NO_ADMITTED_SOURCE` only when the listing has no series at all | `store.py:374` adds it whenever the market has no admitted source, exclusions or not |
| 34 | Test V0-FX: a fixing date stated twice excludes every currency series of the file | `ecb_eurofxref.py:116` still lets the first row win |

The label step also needs more than the eight constants: `market11.UNBUILT_1_15` carries the "not built" lines under a 1.15
label, and point 2 requires the 1.16 form of them (and one for item 22 unless it is built with its test; see below), which
changes every manifest and so the CP3 byte-identity baseline. And the three registries must be re-issued first (item 35).

What I did instead of switching: items 1 to 4 below, and a **scratch trial of the switch** in a copy under `$TMPDIR`
(`r4a_trial`; `rm` was denied to me, so the copy is still there): the eight constants to 1.16 and `PROFILE_SET_VERSION` to
`market-data/1.16#profiles/5`. The default suite on the trial had 22 failures that belong to the switch (listed in the
report), and one more (`test_real_scope`) that was R2 work in progress. Nothing from the trial is in the working tree.

### What changed

Source (`src/marketdata/`):

- `profiles.py`: new `CallAdjustment(adjustment, status, reference)`, `CALL_ADJUSTMENT_STATUSES = (DECLARED, MEMORY)` and
  `PD_0066_DECISION_3`. `SourceProfile.call_adjustment` now maps a function to a `CallAdjustment`. The `TIME_SERIES_DAILY`
  entries of `alphavantage.us` and `alphavantage.cn` are `CallAdjustment("RAW", DECLARED, "PD-0066 decision 3")` (item 23 names
  both). The comment at the old `:260` says DECLARED. `CONVENTION_SET` and `PROFILE_SET_VERSION` are unchanged (see "Known
  inconsistency").
- `adapters/daily_csv.py`: the label source is `PROFILE_CALL_ADJUSTMENT:<source>:<function>:<status>` with the status read from
  the profile entry; an override with no profile entry falls back to MEMORY (the old constant). `adapters/alphavantage.py` reads
  `documented.adjustment`. The label STATUS is untouched: ingestion still sets UNVERIFIABLE.
- `exchange_codes.py`: `UW` (XNAS, segment XNGS) is OBSERVED; `TABLE_VERSION` is `market-data/1.16#a6/2`, because the A.6 id
  names the version that introduced the content (item 32, rule for the A.6 table id), not the governing set.
- `resolver.py`: Ruling 7.3 item 10, the share-class half (new behaviour, section 11 item 24, review C-9). An exchange-level
  record whose `shareClassFIGI` differs from the instrument's stored one attaches nothing and adds no row; it is quarantined as
  `SHARE_CLASS_CONFLICT`. Before this, the FIGI attached and a second `SHARE_CLASS_FIGI` row was added beside the old value.
  The composite half (`COMPOSITE_CONFLICT`) already existed.
- `claim_limits.py` (new): Ruling 6.5 item 6 (1.16) as data: C-1 to C-6 and N-1 to N-9, N-2 ("the dividend component is
  UNVERIFIABLE") an item of its own. Slots, no vendor name, no hard-coded label source. `contracts.py`: a comment only.

Tests: new `tests/product/test_marketdata_r4a_inputs.py` (34 tests); re-recorded pins below.

### Item 4: the confirmation policy with no corporate-action file

The policy was already validated at construction (`ConfirmationPolicy.__post_init__`: an empty role or a source in both roles
raises) and already cited in every manifest as `detection_policy` (`digest`, `feed`, `filing`). R4a adds tests that this holds
when `M` holds no corporate-action record, and the digest as a hand-computed literal. No `src/` constant names the real ids,
because the PM decides them.

**Proposal (for the PM, not a decision).**

| | Feed role | Filing role | Digest (sha256 of `{"feed":[..],"filing":[..]}`, sorted keys, no spaces) |
|---|---|---|---|
| A (recommended) | `alphavantage.us` | `sec.edgar` | `6f1031f0239eefc7d5e77193276c49051a9c304a1498da1ed22f7d3e313001f3` |
| B (fallback) | `none.admitted.feed` | `none.admitted.filing` | `f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1` |

A: the feed id is a registered source (its `SPLITS` endpoint is the OP-3 candidate), so a split file added later needs no policy
change on that side. The filing id is a name reserved for SEC EDGAR, which is NOT registered (PD-0067 decision 4: no entry until
the owner's terms reading), so a reader of the manifest could take EDGAR to be in play. B is the id pair `real_slice.py` already uses
for "no corporate-action source is admitted"; it says exactly that and claims nothing. Under either, `M` holds no record, so the
Ruling 6.4d test has no key and the roles classify nothing. Either way, naming a different source later changes the digest and
so is a new context. I recommend A; the PM chooses.

### Pins and tests re-recorded, each with its reason

| File and test | Before | After | Why, and what shows it |
|---|---|---|---|
| `test_marketdata_alphavantage_cn.py` `test_g1_label_is_read_as_raw_from_the_profile_and_stays_unverifiable` | label source `...alphavantage.cn:TIME_SERIES_DAILY:MEMORY` | `...:DECLARED` | the status is profile data and is DECLARED (item 23; PD-0066 decision 3). Only the last word moved: mutation of `daily_csv` back to the constant MEMORY fails `LabelSourceTests` 3, 5 and 6 (new); I did not run it against the old pins separately |
| `test_marketdata_alphavantage_cn.py` `test_the_us_output_is_pinned_field_by_field` | `...alphavantage.us:TIME_SERIES_DAILY:MEMORY` | `...:DECLARED` | same; every price, volume, bound and profile id in the same assertion is unchanged |
| `test_marketdata_cp2c2_conventions13.py` `test_a_raw_label_read_from_the_profile_says_so_and_a_declared_one_does_not` | `...:MEMORY` | `...:DECLARED` | same |
| `test_marketdata_cp2c2_exit.py` `ANALYTICS_PINS["profiles"]` | `<private pin, PD-0083>...` | `2d16366e...` | `profiles.py` changed: AST diff against `git show HEAD:` (`ast.dump` per top-level definition) adds `CALL_ADJUSTMENT_STATUSES`, `CallAdjustment`, `PD_0066_DECISION_3` and changes `SOURCES` and `SourceProfile` only. `CONVENTION_SET`, `PROFILE_SET_VERSION` and every other definition are equal |
| `test_marketdata_cp2c2_exit.py` `ANALYTICS_PINS["contracts"]` | `ac990c22...` | `7cb65035...` | a comment only; the AST of the whole module equals HEAD's (`ast.dump` equal) |
| `test_cp2_final_round.py` `test_a6_is_versioned_data_with_the_statuses_of_the_appendix` | A.6 id `market-data/1.5#a6/1`; `UW` MEMORY | `market-data/1.16#a6/2`; `UW` OBSERVED | A.6 content changed (item 24, PD-0066 decision 4); every other entry and the composite table are as before (the same assertion lists them) |
| `test_cp2_final_round.py` `test_an_exchange_level_hk_record_fills_all_three_levels...` | provenance string holds `market-data/1.5#a6/1` | `market-data/1.16#a6/2` | the table id stamped into identifier provenance; the three levels attached are unchanged |
| `test_cp2_final_round.py` `test_memory_and_to_confirm_codes_never_attach_an_exchange_level_figi` | attaching entries `{XHKG/HK}`; example MEMORY code `UW` | attaching entries `{XHKG/HK, XNAS/UW}`; example code `UQ` | `UW` attaches now; the test's point (a MEMORY code attaches nothing) is kept on `UQ`, which is still MEMORY |
| `test_cp2_final_round.py` `test_a_confirmed_code_attaches_exactly_like_an_observed_one` | CONFIRMED `UW` | CONFIRMED `UQ` | with `UW` OBSERVED the test no longer showed the CONFIRMED status at work |
| `test_cp2_fix_round_marketdata.py` `test_without_a_mic_to_exchange_code_mapping_nothing_is_attached...` | code `UW` | code `UQ` | same reason; its assertions (CONFLICT, EXCHANGE_UNVERIFIABLE, "status MEMORY", UNCONFIRMED) are unchanged |

No byte-identity baseline, `FIXTURE_PINS` entry, golden file or number moved: the cp3/cp4 golden runs use synthetic routes and
do not carry the label source.

### Mutation checks (hand edit, run, restore, re-read; the final suites ran on the restored files)

1. The share-class check disabled (`False and ...`): `A6AndRuling73Tests.test_6...` fails with `(('SHARE_CLASS_FIGI',), RESOLVED) != ((), CONFLICT)`, which is the pre-change defect.
2. `UW` set back to MEMORY: 5 tests of `A6AndRuling73Tests` fail (1, 3, 4, 5, 7) and test 6 errors.
3. `daily_csv` writing the constant MEMORY again: `LabelSourceTests` 3, 5 and 6 fail.

### Known inconsistency in this tree (stated, not hidden)

The profile content changed (the `call_adjustment` entries carry DECLARED, which item 32 counts as profile content) while
`PROFILE_SET_VERSION` is still `market-data/1.15#profiles/4`. The Quant's rule is that different content never shares an id, and
1.16 names `market-data/1.16#profiles/5`. The id moves with the label, so **this tree must not be committed as a state that
builds a release**. `ReleaseLabelIsNotMovedYetTests` states the position, so a later increment must change it on purpose. The
manifest also still cites 1.15 beside a label source that reads DECLARED. No real release exists to be affected (no
`data/marketdata/releases/` directory; the PostgreSQL side needs SQL against `finweb_dev`, which I did not run, so "no `md_*`
tables" is not re-checked by me).

### Ruling 6.5 item 4 (section 11 item 22)

`ConfirmationPolicyWithNoCorporateActionFileTests.test_7` is the Quant's test for item 22 (Example 6-E row (iv)): a corroborated
(4, 1) split dated 2020-08-31, before any holding and outside the test calendar's 2024-06-03 to 2026-06-30 coverage, changes no
metric of the valuation. It passes on the unchanged engine. If the Quant accepts it as the test, item 22's "not built" line is
not needed at the label step.

### Deviations from the brief, and open items

- **Item 5 and item 6 not done** (the gate above). This is the stop the brief allowed, not a silent choice.
- **Item 3 has no earlier home in code.** The code carried no claim-limit list at all (R5 builds the block, 7.4). I added the data
  module so that N-2 is an item of its own and a test fails when it is dropped. R5 and R7 may extend or replace it. The design's
  C1 to C7 and the Quant's N-1 to N-9 differ: the design's C1 joins N-1, N-2 and N-3, and its R7 test names "C1's dividend
  component". The Quant's list says N-2 is its own item. R5 and R7 should follow the Quant's numbering; I did not edit the design.
- **`securityType` against `securityType2`.** Ruling 7.3 item 3 speaks of `securityType2`; the OpenFIGI adapter reads `securityType`
  into `IdentityAssertion.security_type`. They are both "Common Stock" in the owner's file, so nothing differs today. For the Quant.
- The scratch trial copy is at `$TMPDIR/r4a_trial` and `$TMPDIR/r4a_scripts`; `rm` was denied.
- No commit, no network, no install, no SQL against `finweb_dev` beyond what the test kits run themselves. No background process.

### Files

Changed: `src/marketdata/profiles.py`, `exchange_codes.py`, `resolver.py`, `contracts.py` (comment), `adapters/daily_csv.py`,
`adapters/alphavantage.py`; `tests/product/test_cp2_final_round.py`, `test_cp2_fix_round_marketdata.py`,
`test_marketdata_alphavantage_cn.py`, `test_marketdata_cp2c2_conventions13.py`, `test_marketdata_cp2c2_exit.py`; this file.
New: `src/marketdata/claim_limits.py`, `tests/product/test_marketdata_r4a_inputs.py`.

## F1 R2 (2026-10-25)

Increment R2 of `implementation/CP7_F1_REAL_PATH_DESIGN.md` (section 7.1, R2 row). Author: the Engineer. This is the author's own
record, not a review; nothing here is declared reviewed. The design was not edited. R4a's files were not edited (the files R4a
changed in the same tree are listed in `git status`; none is in the list below except `market_data_store.py`, see "Files").

### Result, stated first

The R2 tests all run (no skip) and pass: `tests.product.test_postgres_real_provenance`, `test_postgres_real_loader` and
`test_postgres_real_gateway_core` together: `Ran 144 tests in 15.559s` / `OK` (PG command). The pure modules
`test_real_provenance` (63 tests) and `test_real_provenance_static` (20) pass without the database.

The two full suites do NOT pass, and none of the failures is in an R2 module or an R2 product path. Both runs fail only in
market-data tests that concern R4a's work in the same tree (profile admission, exchange codes, the analytics pins of
`profiles` and `store`, Ruling 4.7 item 6). Baseline at 11c804a was 3155 OK.

- Default: `Ran 3376 tests in 165.241s` / `FAILED (failures=10, errors=9, skipped=647)`.
- PG command: `Ran 3368 tests in 304.361s` / `FAILED (failures=10, errors=9, skipped=113)`; the one extra PG failure is
  `test_marketdata_cp2c2_exit.ExitCriterionPostgreSQLTests` (the same `profiles`/`store` pin) and one extra error is
  `test_postgres_corporate_actions_service.SplitConfirmationDbTests.setUpClass` (`SOURCE_NOT_ADMITTED: source 'mock.feed' has no profile`).
  The counts moved between my runs (a first default run had 146 errors) because R4a was editing while I ran. They are R4a's to
  close; I did not touch them. Failing modules: `test_performance_cp4_part_a2`, `_a4`, `test_marketdata_cp2c2_identity_and_class`,
  `_cp2c2_exit`, `test_marketdata_akshare_cn`, `test_cp2_fix_round_marketdata`, `test_marketdata_listing_market_gate`,
  `test_marketdata_cp2c1_adapters`, `test_marketdata_alphavantage_cn`.

### Exit statements

(a) **The loader registers a context-bound bundle AFTER the publish.** A registration is unbound or bound. A bound one carries the
snapshot's `context_id` (FK to `rw_snapshot`); it is refused with `RW_PROV_INPUT_MISSING` before the publish and accepted after it,
and a lease loads only a registration bound to its own context (`RW_PROV_CONTEXT_DIFFERS` otherwise). So the loader's last R8 use is
step (4a). Tests: `test_postgres_real_provenance.py:238` (before/after), `:272`, `:289` (the function called directly), `:398`, `:411`
(the database alone, with no Python wrapper). Product path: `real_provenance_v1.sql` `rwp_put_context` (345) and `rwp_load_context` (425).
Alternative, not taken because the design fixes the bound-after-publish order: resolving by the snapshot's digests would shorten
the window; I record it, no more.

(b) **The install does not require the loader to have LOGIN; the per-call check does.** `_install_gateway_body` accepts a loader with
or without LOGIN (executor and publisher must have LOGIN; the owner must not); `verify_registry_install` never reads
`rolcanlogin`. `rwp_caller` (SQL 138-144) requires LOGIN on every call, so a loader set NOLOGIN is refused with
`RW_PROV_ROLE_REFUSED` even from a session opened earlier; that session's `md_*` INSERTs are unaffected (privileges, not the
registry). Tests: `test_postgres_real_provenance.py:1079` (`LoaderWithoutLoginTests`: install with NOLOGIN passes, cannot connect,
registers once LOGIN is on, is refused again when it is off, and the executor's load does not depend on it); the installer half with no
database at `test_real_provenance.py:593` (`InstallerRoleCheckTests`). A loader that cannot log in cannot register, so a deployment
that wants the registry to work must keep LOGIN on while it registers.

### Mapping of the brief's items

| Item | Test (file:line) | Product path |
|---|---|---|
| N2a generalised to `rwp_` | `test_postgres_real_provenance.py:45` (p01 to p06, run on SYNTHETIC_TEST `:226` and on TEST_SWITCH `:230`); pure `test_real_provenance.py:52` | `real_provenance_v1.sql`, `real_provenance_store.py:141` |
| O1, O2, O3 each with controls | `test_real_provenance.py:256` (pure); SQL `test_postgres_real_provenance.py:845, :852, :863`; Python/SQL grid `:883` | `real_provenance.py` `o1_fails/o2_fails/o3_fails`; SQL `rwp_origin` (116), `rwp_permits` (95) |
| Publish reports every failed predicate | `test_postgres_real_provenance.py:708` (order kind, O1, O2, O3, candidate), `:771` in a REAL install | `real_workspace_v1.sql:438` `rw_publish` calls `rwp_origin_failures` (SQL 445) |
| Validators take attestations by value, write nothing | `test_real_provenance.py:406`; `test_postgres_real_provenance.py:903` | `real_provenance.py` (no I/O), `rwp_origin` is STABLE with no write |
| REAL branch enabled behind the validators | `:793` (stub of `rwp_origin_failures` shows the wiring), `:760` | `real_workspace_v1.sql:434-438` |
| Guarded load bound to mode, head, lease, root | `:310` (both test scopes), `:572` (crafted generation, rights, phase), `:644`, `:653` | `rwp_guard` (311), `rwp_load_context` (425), `load_guarded` (`real_provenance_store.py:239`) |
| Refuses at or past `complete_by`; pause-before-the-guarded-load | `:518`, `:522` (earlier of W and valid_until), `:558` (checked before the candidate is read), `:674` (calls `rw_reached`, not an inline `>`) | `rwp_guard` calls `rw_reached(clock_timestamp(), l.complete_by)` |
| TEST_SWITCH guarded load with a real-branch lease | `:506` (`GuardedLoadOnTestSwitch`) | `rwp_guard` `rw_scope_allowed` |
| Loader cannot publish | `test_postgres_real_loader.py:158` (`:171`) | `real_roles.py` list (nothing on `rw_*`) |
| Loader's exact privileges as a catalog assertion | `test_postgres_real_loader.py:57` (hand-written EXPECTED table; `:95` explicit grants; `:125` audit with one extra grant) | `real_roles.py:50, :71, :79, :137` |
| `write_release(..., count_rows=False)` | `test_postgres_real_loader.py:238` (`:256` default needs a SELECT the loader lacks, `:268` same projection as the owner, `:286` outside the list); pure `test_real_provenance.py:673` | `market_data_store.py:448-488` |
| Loader's SELECT of `md_quote` refused 42501 | `test_postgres_real_loader.py:159` | no SELECT on `md_quote` |
| Registry get returns the payload bytes | `test_postgres_real_loader.py:196` | `rwp_get_context` (418) |
| Registry binding; install with a loader that cannot log in | `:237`, `:1079` | above |
| Install-kind test gains O1's code | `test_postgres_real_gateway_core.py` (the install-kind test now lists `RW_INSTALL_KIND`, O1, O2, O3, `RW_PROV_CANDIDATE_MISSING` and asserts `RW_REAL_SCOPE_UNWIRED` is absent) | `rw_publish` |
| N2a regression under SYNTHETIC_TEST | `:226` | |

Error classification (3.1 E4, fail-closed): `OneTransaction._transact` and `_classify` in `real_workspace_context.py:82-147`, moved out of
`RealPublisher` so the loader's registration uses the same code. Tests: `:127` (p04b, after the commit point only a gateway code on an
IDLE connection is a refusal), `:150` (killed connection is UNKNOWN), `:170` (lock timeout), and R1's `test_real_publisher_tool.py`
`CommitOutcomeTests`.

### Mutation checks (SQL or Python edited by hand, the tests run, the file restored and diffed against a backup)

Killed (each by the tests named in the brief's list): SQL O1 as `= 'true'`; SQL O2 exempting synthetic sources (12 failures); SQL O3
accepting v2 or dropping the usage-scope condition; Python O1 as `is True` (6); Python permit as `is not False` (2); Python O2
exemption (23); Python O3 without the schema (1); `origin_report` truncated to the first failure (33); the deadline check removed from
`rwp_guard` (4 failures, 1 error); the deadline written inline as `clock_timestamp() > complete_by` (the wiring test and 2 static tests);
the bound check disabled (3); the LOGIN check removed from `rwp_caller` (2); the generation and rights re-checks removed (the crafted-state
tests); `rw_publish` no longer calling `rwp_origin_failures` (9); the loader list with SELECT `md_quote` added (7), SELECT `md_release`
removed (5 failures, 5 errors), `rwp_load_context` added to the loader (6 failures, 3 errors); the E4 rule (gateway code after the commit
made UNKNOWN) killed by p04b on both scopes and by `CommitOutcomeTests`; `count_rows` ignored (4 errors).

One mutation was NOT killed at first: removing `f IS NULL OR f IS DISTINCT FROM l.context_id` from `rwp_load_context`, because
`load_guarded` repeats the check in Python. I added `test_the_database_alone_refuses_another_contexts_or_an_unbound_candidate` (`:411`),
which calls the SQL directly; the same mutation then fails 2 tests. All mutated files were restored (diffs clean). `market_data_store.py`
was restored by hand-edit without a backup; its `git diff` against the pre-R2 state is only the `count_rows` change.

### Not shown

- The guard's mode-hold, expiry re-derive and root-link refusals are not each shown by their own test beyond `provfresh` (nothing
  published) and the crafted generation, rights and phase cases. The root-link check is also enforced by a foreign key.
- The registry's capacity limits (`RW_PROV_CAPACITY`) have no test.
- The Python/SQL parity grid covers the structured cases; byte-level cases (a changed envelope digest, stored witnesses) are checked
  separately, not in the grid.
- Concurrency: the p06 test shows two concurrent identical and conflicting registrations; it does not show lock fairness.
- The loader's catalog test does not yet assert "no other function": PUBLIC's default EXECUTE on the migration functions is R3's revoke.
- The loader's `LOGIN` requirement is shown against PostgreSQL 17.11 only.
- No SQL ran against `finweb_dev` or any existing database; the kit's disposable databases only. A read-only catalog query as
  `finweb_dev` after the runs found no `finweb_it%` database and no such role.

### Decisions the contracts did not cover

1. Namespace `rwp_*` and codes `RW_PROV_*`, `RW_O1_SYNTHETIC_SOURCE`, `RW_O2_TERMS_CHECK`, `RW_O3_ACQUISITION`, `RW_ORIGIN_MIXED`.
2. The guarded load is limited to the create and reproduce purposes; read and export leases never reach a candidate.
3. R1's installer was relaxed: the loader may be LOGIN or NOLOGIN (R1 required one of them). Executor and publisher keep LOGIN, owner NOLOGIN.
4. `OneTransaction` extracted from `RealPublisher` (one runner, not two copies).
5. The O predicates exist in Python and in SQL, with a parity test (a grid and the candidate table), because the publish must run in the
   database and the tool must be able to say the same thing before the database.
6. In a test scope the O failures are informational (publish does not refuse for them); a test scope holds only synthetic sources, no terms
   check, no terms URL, no human v1 manifest (`RW_PROV_SCOPE_REFUSED`).
7. The install-kind refusal is ordered before the origin refusal in `rwp_put_context`.
8. The census tests in `test_real_scope.py` were updated for the new `scope_by_snapshot_field` and `require_resolved` call sites (each with a
   comment). `validate_loaded_bundle` takes a `ScopeDef` from `scope_by_snapshot_field`, so reading back never grants the switch.
9. The executor's `GRANT EXECUTE ON rwp_load_context` is in the registry SQL; R3 should fold it into the executor's list.
10. `rwp_caller` does not check `rolinherit` (the kit's roles are NOINHERIT but the check that matters is no membership and `role = none`).
11. E11 fixtures: a kit REAL install, a stub of `rwp_origin_failures` to show the wiring, crafted leases and head rows, and
    `ALTER ROLE ... LOGIN/NOLOGIN` by the kit's admin. REAL-scope test bytes are invented; bytes with `synthetic=false` are only passed to a
    validator or to a publish that is refused, and none is stored (design 4.2). Product code never writes install kind REAL.

### Files

Changed: `src/persistence/real_workspace_v1.sql` (the `rw_publish` REAL branch), `real_workspace_context.py` (`OneTransaction`),
`real_workspace_store.py` (installer: two SQL files, loader grants, registry check), `market_data_store.py` (`count_rows`, keyword-only);
tests `real_gateway_kit.py`, `test_postgres_real_gateway_core.py`, `test_real_gateway_static.py`, `test_real_publisher_tool.py`,
`test_real_scope.py`; this file. `market_data_store.py` already had uncommitted changes in the tree before R2; mine is the `count_rows` part only.
New: `src/persistence/real_provenance_v1.sql`, `real_provenance.py`, `real_provenance_store.py`, `real_roles.py`; tests
`real_provenance_case.py`, `real_provenance_fixtures.py`, `test_real_provenance.py`, `test_real_provenance_static.py`,
`test_postgres_real_provenance.py`, `test_postgres_real_loader.py`.

No commit, no network, no install, no background process.

### R2 review follow-up: L-1 and L-4 closed with tests (2026-10-25)

The independent review passed R2 with five LOWs. L-1 and L-4 are closed here; L-2 (R3's audit), L-3 (HG4 package, R6) and L-5 stay open as the coordinator directed. No product code changed.

- **L-1, the passing side of O2 at publish.** `PublishOriginPassingSideTests` in `test_postgres_real_provenance.py` (class before `PublishInARealInstallTests`). Bytes are the relabelled REAL snapshot with a permitting `terms_check` set in each source record (two or more sources, all of them member sources). Through `rwp_origin_failures` called by value and through a refused `rw_publish`, O2 drops from the list while O1 and O3 (and the missing candidate) stay listed; the control with null checks lists O2. Further cases: only the first, only the last, or one negative check keeps O2 listed. The permitting check is an invented attestation passed to a validator and to a refused publish; nothing is stored and nothing is `synthetic=false`. **Mutation A** (the snapshot's `terms_check` replaced by null in `rwp_origin_failures`, `real_provenance_v1.sql:475`) now fails 2 tests; restored, diff clean.
- **L-4, the membership refusal in `rwp_caller`.** `RegistryMembershipTests` (install `provmember`; new kit helper `Install.set_membership`, an E11 crafted fixture run by the disposable database's admin and reverted in `finally`). A role that is a member of the loader makes the loader's put and get fail with `RW_PROV_ROLE_REFUSED` and write nothing; the member itself (after `SET ROLE` to the loader) is also refused; the loader as a member of another role is refused; an executor that is a member of another role is refused in `load_guarded`; after the revoke each control registers or loads again. **Mutation W** (the `pg_auth_members` EXISTS removed, `real_provenance_v1.sql:145`) now fails 3 tests. Not shown by this mutation: the member-calling-via-`SET ROLE` case alone, which the earlier `session_user` check already refuses; the loader-side cases are what pin the membership check.

## F1 R4a follow-up: market-data/1.16 gate items 25, 26, 27, 28, 34 (2026-10-25)

Engineer's self-validation; not a review. The label switch (item 23's constants, 32, 33, 35) is still NOT done: the eight constants name 1.15,
`PROFILE_SET_VERSION` is `market-data/1.15#profiles/4`, the three registries are not re-issued. The 1.16 form of the `not built` lines (`market11.UNBUILT_1_15`) is not built either.

Result: default `3409 tests OK (skipped=647)`; PostgreSQL (`FINWEB_PG_INTEGRATION=1` ...) `3409 tests OK (skipped=113)`.

| Item | Built | Tests (a mutation fails them) |
|---|---|---|
| 25 V0, duplicate session dates, every market | `AdapterOutput.contradicted` (`ContradictedSeries`); `daily_csv` counts parsed dates per (symbol, file) always; `ingest_file` turns it into a `SeriesExclusion` (file stays in M), `build_in_memory_market_data` adds the `LabelResult` | `r4a_inputs.DuplicateSessionDateTests` (Example 3-E (a), (a'), same spelling, outside calendar, several dates), `alphavantage_cn.World.test_g2_dup_...` (CN). Mutations A (key by text), B (`n > 2`), C (exclusions dropped) fail 3/9/12 tests |
| 26 A.4 item 7 on every route | `precision.check_field_format` has no flag; TEXT_DECIMAL and FLOAT64 with `delivered_dp`; FLOAT32 and integral fields exempt | `DeliveredDecimalsTests` (3-E (b), (c), the stored AAPL file: 100 rows, 400 texts of 4 decimals, counted from the bytes). Mutations F (value's decimals), G (no FLOAT32 exemption) fail |
| 27 gate, non-persistence and persistence halves | `MIC_MARKET`/`EXCHANGE_ZONES` gain ARCX, BATS, XASE; `listing_market_refusal` in the Ruling's order (unmapped MIC, no profile, coverage, admission); `market_data_store._require_admitted_to_store` refuses a profile-less real reading even without `exchange_of`; `read_release` inherits the constructor's gate | `listing_market_gate.Item27PerReadingGateTests`, `WriteGate.test_1_16_*`. Mutations I, J, K, L fail |
| 28 NO_ADMITTED_SOURCE exclusivity | `store.quote_on` adds the cause only when the listing has no exclusion; freshness stays UNKNOWN | `NoAdmittedSourceExclusivityTests`, `alphavantage_cn` G2-c. Mutations H, H2 fail |
| 34 V0-FX duplicate dates | ECB adapter returns no rate and one `ContradictedSeries` per currency when a parsed date repeats (all rows, inside or outside the read window); the first-row-wins rule is gone | `FixingDateStatedTwiceTests` (USD 1.08 then 9.99, equal rows, N/A row, with and without calendar, outside coverage, outside read window, other files untouched). Mutations D, E fail |

Policy ids (PM option B): `none.admitted.feed` / `none.admitted.filing`, digest `f5942dc5...69bc1` (pinned by `PROPOSAL_B`). No `src/` constant: `performance_tools/real_slice.py:323` already builds exactly that pair, and the R4b world builder takes it from the same two literals.

Re-recorded (each with its reason in the test): the US known-gap test (now refuses); the ECB first-row-wins test (now excludes); G2-c (no NO_ADMITTED_SOURCE beside V0); `test_what_the_rule_does_not_judge_is_stated` (the rule now judges all three); the made-up-source store test (now SOURCE_NOT_ADMITTED); eight tests of akshare.cn (3-decimal ETF/B-share closes, a grid-violation text, 474.20001, 8-decimal adjusted values) run against `gate_kit.delivered_dp("akshare.cn", 8)` because the recorded Eastmoney profile (`delivered_dp 2`) now refuses them at the profile check; the hand-built REAL stores of invented sources on XTST (midpoint, corporate-actions service, cp4 a2/a4, recheck, precision_1_1, the F8-B PostgreSQL test) are built inside `gate_kit.admitted_real_world` / `admitted_sources`, which adds a profile and a US market for the invented ids for the duration of the construction only. `ANALYTICS_PINS["profiles"]` = `38befe69...` and `["store"]` = `ed4acf27...`, reasons in the pin comments.

Findings for the Quant (not adjusted): (1) item 26 on every route makes the recorded Eastmoney `delivered_dp 2` refuse every FUND_ETF_LOF_BOND close (3 decimals) and every B-share close, and qfq values, before the class grid sees them; the source is refused and synthetic-only, but the A.1 class grid is unreachable on that route as recorded. (2) A real filing source cannot exist yet: no filing-profile mechanism is in `profiles.py` (the method adds one with the first registered filing source), so every real corporate-action record is refused. (3) `UNBUILT_1_15` replacement and the counter `1.16#profiles/5` wait for the label step.

## F1 R4a: Quant fixes F-1, F-2, (c) and the label switch to market-data/1.16 (2026-10-25)

Engineer's self-validation; not a review. Source: the Quant's note `methodology/CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25.md`. Nothing committed.

Result: default `Ran 3425 tests in 159.085s` / `OK (skipped=654)`; PostgreSQL (`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`) `Ran 3425 tests in 306.455s` / `OK (skipped=113)`.

| Item | Built | Tests (a mutation fails them) |
|---|---|---|
| F-1 (item 25): the rule excludes the series, not the file | `daily_csv` drops the rows of each contradicted symbol (`rows = [r for r in rows if symbol not in excluded]`) and goes on translating the rest; `contradicted` carries one `ContradictedSeries` per symbol | `cp2c2_identity_and_class.MultiSymbolFileV0Tests`: control (no repeat, both served); the repeating symbol is excluded and the clean symbol's readings are present and its lookup is not NO_ADMITTED_SOURCE. Mutation M (the whole file excluded) fails them; restored |
| F-2 (item 34) on the Frankfurter route | `frankfurter.py` reads the JSON with `object_pairs_hook`, counts parsed dates over the `rates` names; a repeated key or two spellings of one date return no rate and one `ContradictedSeries("V0_FX_DUPLICATE_DATE")` per currency of the file | `r4a_inputs` tests 7a to 7e (repeated key, two spellings, every currency excluded, a clean control, the two stored Frankfurter files exclude nothing). Mutation N (the check removed) fails them; restored |
| (c) non-vacuity of `ConfirmationPolicyWithNoCorporateActionFileTests.test_7` | the 2020 key is CORROBORATED under the policy with the filing source and unmatched under a policy without it | `test_7` asserts both; item 22's "not built" line is gone |
| 35 label switch | the eight constants (`manifest.CONVENTION_SET_ID`, `profiles.CONVENTION_SET`, `profiles.PROFILE_SET_VERSION`, `reconciliation.RULE_ID`, `reconciliation.TOLERANCE_REF`, `market11.FRESHNESS_ID`, `PRICE_OF_DATE_ID`, `FX_ID`) read `market-data/1.16`; `PROFILE_SET_VERSION` = `market-data/1.16#profiles/5` | `version_label.VersionLabelTests`, `r4a_inputs.ReleaseLabelIsMovedTests` (replaces `ReleaseLabelIsNotMovedYetTests`: the eight constants, the A.6 id, and the content of profiles/5 = the three changes of answer (b): DECLARED call_adjustment on both Alpha Vantage calls, ARCX/BATS/XASE with zones, the Ruling 4.7 item 6 order) |
| "not built" lines | `UNBUILT_1_15` is `UNBUILT_1_16`, six lines (V1, lineage item 5, V4, Ruling 4.5, Rulings 7.4/7.5, and the new line for answer (d): the text names `securityType2`, the rule means `securityType`, ETF values need a human's confirmation). No line for items 21 and 22 (built). No code change for (d). The new line says "the identity feed's securityType2" and not the vendor: `market11` must stay vendor-free (`cp2c2_exit` check 2 caught my first wording) | `version_label.UnbuiltBehavioursAreDisclosedTests` (6 lines, one per behaviour, the by-hand wording of line 0, the three item 5 statements, the (d) line, the tripwires) |
| three registries | `risk_registry.json`, `performance_methodology_registry.json`, `diversification_registry.json` are byte copies of `RISK_1.11_REGISTRY.json`, `PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json`, `DIVERSIFICATION_1.2_REGISTRY.json`; `IMPLEMENTED_REGISTRY_ID = "risk/1.11"`, `RISK_ENGINE_ID = "risk/cp4i-0.3"` (pins moved), `METHOD_KEY_PREFIX = "diversification/1.2#"`, appendix check `performance-registry/1.2` | `version_label.RegistryVersionTests` with `REGISTRY_REISSUES` re-recorded: file SHA-256 risk `9760901707bd...`, performance `ef68208a2f6c...`, diversification `0cd4fbe7d544...`; loader digests risk `5c630fdf9ff4...8058ce`, performance `f2aefda7232d...891a71`, diversification `4f27f1e957e3...852297`, all equal to the Quant's values; `differs_at` computed from the files and read against each change note |

Pins and baselines re-recorded (reason in each comment): `ANALYTICS_PINS` `market11` = `81730a26...` (labels, `UNBUILT_1_16`), `reconciliation` = `48f6969a...` (labels), `manifest` = `fe4e5201...` (label), `profiles` = `eae4650f...` (labels and counter); `store` = `ed4acf27...` and `contracts` = `7cb65035...` unchanged since the earlier step. `ast.dump` against HEAD, old labels read as 1.16 and the tuple assignment dropped with its name unified: `manifest`, `reconciliation`, `market11` equal. `test_risk_boundaries` engine/registry pins (`8766b2e4...`, `8844f2c4...`, comment cp4i-0.3). `BASELINE_SHA256` of `test_performance_cp3_byte_identity` = `952f790512f5d70b...e39b4` (was `971cd925...`).

Revert demonstration of the CP3 byte-identity baseline (scratch copy of the tree, run of that test's hash): new tree `952f7905...`; `UNBUILT_1_16` emptied `34773977...`; all eight constants reverted to 1.15 (`PROFILE_SET_VERSION` to `1.15#profiles/4`) and lines emptied `e0d38c11...` (the 2026-10-24 label-alone value); eight constants reverted with `market11.py` as at HEAD (the five `UNBUILT_1_15` lines) `971cd925...` = the previous baseline, exactly; seven of eight reverted (FX_ID left at 1.16) `c4bb1282...`, which is neither, so all eight must be reverted. In that reverted scratch tree `version_label`, `r4a_inputs` (`ReleaseLabelIsMovedTests`) and `cp2c2_exit` fail. My first wording of line 5 named the vendor and gave `58790111...`; the vendor-free wording is the one recorded.

Stored real releases: none affected. `data/marketdata` holds files and registries but no release record or manifest (no `release_id` or `convention_set` in any stored file; the only `market-data/1.15` text under `data/` is a historic note in `SOURCES.json`). I ran no SQL against `finweb_dev` (PD-0071); the PG suite's own kits ran in disposable schemas.

Open: (d) is an open item only (a human confirms ETF `securityType` / `securityType2` values; the text defect goes to the next market-data version). Findings (1) and (2) of the previous section stay with the Quant. Scratch copies left in `$TMPDIR` (`/tmp/claude-503`): `r4a_trial`, `r4a_label`, `r4a_label2`, `r4a_scripts`, and stray `ed1.sed`, `dummy`, `*.new`, `full_default.txt`, `full_pg.txt` (rm is denied to me).

## F1 R4a fix round: review HIGH-1, MEDIUM-2/3, LOW-4/5/6/7 and the repeated header column (2026-10-25)

Engineer's self-validation; not a review. Source: `reviews/TECH_REVIEW.md` "F1 R4a build - independent technical review (2026-10-25)" (HOLD) and Addendum A of `methodology/CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25.md`, which I treated as the contract. The label stays `market-data/1.16`. Nothing committed.

Result: default `Ran 3462 tests in 176.907s` / `OK (skipped=654)`; PostgreSQL (the brief's prefix) `Ran 3462 tests in 320.051s` / `OK (skipped=113)`. 37 tests are new. The CP3 byte-identity baseline (`952f7905...`) and the golden-world tests did not move: no golden world, and none of the stored real files (checked through their adapters: AAPL, the two Frankfurter files, the akshare files), states a date twice.

**Structure (my call; the Quant left it to me).** The price duplicate test is now in ONE place, `ingest_file`, after identity resolution, so every route is covered by construction and the unit is the resolved listing (LOW-5). An adapter LISTS what each row states (`AdapterOutput.dated_statements`: one `DatedStatement` per row whose date parses and which names a symbol, refused rows included); ingestion resolves them, counts (listing, file, parsed date), and for a listing with two it adds the `SeriesExclusion`, the `DUPLICATE_SESSION_DATE` issue, the market gate (`bind`), and drops that listing's quotes, adjusted rows and reference rows of the file. An adapter that lists nothing is judged on the quotes and adjusted rows it emitted. `ContradictedSeries` is now FX-only (`currency` required, optional `names`); the price form, the daily_csv per-symbol drop and its pre-check are gone (they were the source of MEDIUM-2: a series dropped with no exclusion). FX keeps its adapter-level detection (a layout question) and `ingest_file` has a net: a (pair, date) emitted twice by an adapter that named nothing excludes every currency series of the file.

| Finding | Built | Tests | Mutation and fail count |
|---|---|---|---|
| HIGH-1 mock quotes (item 25) | mock lists `dated_statements` | `MockRouteDuplicateDatesTests` 1-8 (control; the reviewer's 7th twice 101/150; equal rows; two spellings; a repeated row that fails its own check; only the repeating series; unreadable dates; an adapter that lists nothing) | A: mock lists none: 5 fail |
| HIGH-1 mock FX (item 34) | key (base, quote, date), unit every quote currency of the file; detail names the pair | tests 9-12 (two-currency control is NOT excluded; the reviewer's case excludes USD and HKD; equal rows and two spellings; a route that names nothing) | B: mock check off: 1 fails (the ingestion net catches the other cases); date-only key: 5 fail (2 here, 3 in `test_marketdata_pipeline`); M (net off): 1 fails (test 12) |
| central V0 | ingestion counts per resolved listing | all of the above, `DuplicateSessionDateTests`, `MultiSymbolFileV0Tests` | C: count disabled: 22 fail (18 `r4a_inputs`, 3 `identity_and_class`, 1 `alphavantage_cn`); D: the fallback for an adapter that lists nothing: 1 fails |
| MEDIUM-2 blank or unparseable date (A.2) | `daily_csv` lists no statement for an unreadable date; the row is refused alone (`UNPARSEABLE_ROW`) | `UnreadableDateRowTests` 1-6: one blank row; two blank; two with one bad label; two with different labels; `2025-01-07x` never joins 2025-01-07; (iv) a parsable date with a bad field counts (ROW_INCONSISTENT and contradicted). The hand check of Example 3-E (c) with two empty-timestamp rows: 100 x 50.50 = 5,050.00, `CURRENT`, `AVAILABLE`, 3 readings, no exclusion | E: an unreadable label counted as a date: 3 error |
| MEDIUM-3 Frankfurter repeated top-level members | all `rates` members counted together (a date in two members is a date stated twice: V0-FX); a repeated `rates`, `base` or `amount` that states no date twice REFUSES the file (UNKNOWN_FORMAT) | `CurrencyStatedTwiceTests` 4-6 | H: only the last member counted: 1 fails; I: the refusal off: 2 fail |
| LOW-4 a currency stated twice (A.3) | Frankfurter: a currency twice in one date object (`usd` = `USD`); ECB: a header naming a read currency twice; every currency series of the file excluded, lineage names the dates and the currency | `CurrencyStatedTwiceTests` 1-3, 7-8 (a repeated column nobody reads changes nothing) | J: 1 fails; K: 1 fails |
| LOW-5 aliases of one listing (A.4) | the key is the listing (above) | `MultiSymbolFileV0Tests` 3-4 (the review's case: `600519` and `600519X` on 2025-01-03: NO_HISTORY, INSUFFICIENT_DATA + MISSING_PRICE_HISTORY, SERIES_CONTRADICTED, not FOUND 10.50; aliases on different dates are served) | G: keyed by symbol again: 1 fails |
| repeated header column (A.3 observation) | `daily_csv` lists each row twice when the header names a column it reads twice (any of date, open, high, low, close, volume, turnover, change, symbol); every series of the file is contradicted | `HeaderNamesAColumnTwiceTests` (each of the six US columns), `MultiSymbolFileV0Tests` 5-6 (the Eastmoney layout; an unread repeated column changes nothing) | L: listed once: 7 fail (6 subtests + 1) |
| LOW-6 M4 | - | `listing_market_gate.WriteGate.test_1_16_a_real_adjusted_row_of_a_source_with_no_profile_...` (with and without `exchange_of`; a profiled source's adjusted row reaches the database) | M4: the adjusted profile-less check off: 1 fails |
| LOW-6 M6 | - | `ReviewersScenario.test_a_real_file_that_repeats_a_date_is_refused_by_the_market_gate_just_the_same` (XSHG, XSHE, HK listings; the US control is excluded and not refused) | M6: `bind` off on the duplicate path: 1 fails |
| LOW-7 `write_release` without `exchange_of` | NOT FIXED (see below) | - | - |

Re-recorded: `test_marketdata_pipeline.test_bad_rows_are_reported_never_dropped_silently` (its bad rows shared one date, which since 1.16 contradicts the series; they now have dates of their own), three adapter-level tests in `test_marketdata_alphavantage_cn` and `test_marketdata_cp2c1_adapters` (the adapter now lists two statements and ingestion refuses the series; the refusal is tested through the real path).

**Adapter sweep (HIGH-1), pinned by `AdapterSweepTests`** (a new adapter class not in the table fails it):
- `AlphaVantageQuoteAdapter`, `AkshareCnQuoteAdapter`, `AkshareSinaQuoteAdapter`: item 25 runs (via `translate_daily_csv`, judged by ingestion). Item 34 n/a.
- `MockSyntheticAdapter`: item 25 runs for QUOTE, item 34 for FX (new this round); its CORPORATE_ACTION and BENCHMARK kinds are outside both items.
- `EcbEurofxrefFxAdapter`, `FrankfurterFxAdapter`: item 34 runs, with a date or a currency stated twice (Frankfurter at the top level, the `rates` level and the date level).
- `CalendarFileAdapter`, `OpenFigiIdentityAdapter`, `EodhdSplitCandidateAdapter`: not price or FX series; outside the items. `SyntheticRiskFreeAdapter`: outside; the contract requires strictly increasing dates, so a repeated date is refused (as for a benchmark series).
- No adapter in `src/marketdata/adapters/` lacks the check; a future route is still judged by ingestion on what it emits.

**LOW-7 assessment.** `write_release` cannot apply the listing-market check without `exchange_of`. The release contents (`StoreContents`) carry only `listing_id`; the listing's exchange MIC is in the identity registry (`exchange_of`) or the `listing` table, and the real loader holds SELECT on `md_file`/`md_release` only. The one market string a reading carries, `Lineage.market`, is the MANIFEST's claim, which is exactly what the listing-level gate exists not to trust. I made no change and did not edit `test_postgres_real_loader.py`. For R3: either the loader passes the identity's `exchange_mic` (a caller-supplied mapping, no table read), or `write_release` refuses a non-synthetic reading when `exchange_of` is None (fail closed; it would change the loader's call), or a database check on the append-only insert. The read side already fails closed, so no number is served.

**Choices the contract did not cover:** (1) the repeated top-level `base`, `amount` or a second `rates` member with other dates REFUSES the Frankfurter file whole (fail closed); a date in two `rates` members is treated as V0-FX. (2) For a mock FX long-layout file, a duplicate (pair, date) excludes every quote currency in the file (the Quant read this and approved it). (3) A repeated header column makes each row two statements; I used the same mechanism for any read column, volume included. (4) The ECB duplicate-column check counts only the currency columns the manifest asks for. (5) A repeated unparseable Frankfurter date name yields one `bad date key` issue, not one per copy (the JSON object collapses the names); nothing is served either way.

Scratch left in `/tmp/claude-503` (rm denied): `r4a_label`, `r4a_label2`, `runmods.sh`, `full_default2..4.txt`, `full_pg2.txt`, `*.new`, `base_patch.txt`.

## F1 R3 (2026-10-26)

Engineer's self-validation; not a review. Scope: `implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.1 R3 row, 2.6, 4.2 (build table, install kind, O4), 4.4 Step 2 item 2, 1.2 rule 5.3 (e), section 1 items 1 and 6, fact 11. R1 (11c804a) and R2 (a6bee4c) are the base. Binding: PD-0069, PD-0070 decision 2 / E28, PD-0059, PD-0060, PD-0071. Nothing committed.

**Result.** Default suite: `Ran 3593 tests in 162.216s` / `OK (skipped=747)`. PostgreSQL suite (the brief's prefix: `FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`): `Ran 3593 tests in 356.200s` / `OK (skipped=113)`. R3 modules alone, same prefix: role lists 14, labels 18, loader entry 6, gateway core 40, fence 16, seal 31, md read 14, catalog audit 27, reader audit 2, loader (PG) 18, x1 45, gateway static 25, provenance 63 + 20 static + 96 PG: all OK. After the runs: no `finweb_it%` database and no `finweb_it%` or `rw_%` role (read-only query as `finweb_dev`); no background process was started.

**Built (SQL-level facts only).**
- S2 storage `rw_root`, `rw_revision`, the bundle tables `rw_artifact`, `rw_operation` (mandatory link column, no FK), `rw_journal`; immutability triggers; `src/persistence/real_fence_v1.sql` is the CORE file, `real_workspace_fictional_v1.sql` the TEST-only part (functions only).
- The three barriers on `portfolio`, `account`, `ledger_event`, `benchmark_selection`, `rw_root`, `rw_revision`: BEFORE row trigger `zz_rw_write` (and `zz_rw_truncate`), restrictive RLS policy `rw_row_guard` (+ permissive `rw_baseline`) TO the executor, AFTER trigger `zz_rw_journal`. Deadlines are checked at statement time, reads of the rooted tables and the archive included.
- `rw_seal`, `rw_validate`, `rw_bundle_guard` with the deferred constraint trigger `rw_bundle_complete`, `rw_archive`, `rw_precheck`, `rw_link_verify`, `rw_check_artifact` (structural checks + the origin-label row guard), `rw_check_real` (O4a, O4b), `rw_check_fictional` (TEST-only).
- Thirteen lease-checked `rw_md_<table>(release text)` functions and `rw_md_guard` (code `RW_MD_READ_REFUSED`, DETAIL NO_LEASE / PURPOSE / DEADLINE / RELEASE); the executor holds EXECUTE on them and no privilege on any `md_*` table.
- `real_roles`: one list per runtime role, the same table and sequence lists for TEST and REAL, `sql_files(kind)` (REAL omits the TEST-only file), the schema-wide `REVOKE EXECUTE ON ALL ROUTINES ... FROM PUBLIC` as the first statement after the last file. `real_catalog_audit` (product code, run by both installers and by tests). `real_workspace_store._install_gateway_body(..., kind)`; `install_test_gateway` is unchanged (TEST only). New product modules: `real_labels.py` (pure row-to-label mapping), `real_loader.py` (LOW-7).

**Exit claims (what R3 does and does not claim).** SQL-level facts about commits only (a crafted commit is durable after the connection drops; a refused COMMIT leaves no row). No outcome code, no "UNKNOWN, no retry", no service call, no create / read / reproduce application code (R5). It does NOT claim that a REAL database holds no fictional-branch function, that REAL's grants are right, or anything about the loader's reads: it shows the file split, the lists and that the audit can see. Every seal / bundle / replay / archive test is an "E11 crafted probe, not product evidence" (`real_bundle_probe.py` writes the bundle through the executor connection in the format the SQL checks). The real branch's ACCEPTED side (O4 with `synthetic = false`) is not exercised: invented data is never marked `synthetic = false`; its refusals are.

**Tests by item of the brief.**
| Item | Where | Notes |
|---|---|---|
| T03 all-writer matrix incl. executor attempts, FF1-C02 classes, `WebAccountStore.create_portfolio` on the executor connection, lease-less insert into a registered-nowhere root each barrier alone, ordinary lease without link refused, PD-0060 pattern | `test_postgres_real_gateway_fence.py` (16), `..._seal.py` (`MandatoryLinkTests`) | the fence-alone / policy-alone / journal-alone switches are done by the owner of the disposable DB (E11 crafted), switched back in `finally` |
| fictional flow unchanged (T10), FF1-C01 / C02 | the existing F2 and R1 modules, unchanged and green in both suites | R3 changed none of `guarded_workspace_*` |
| O4, seal acceptance, atomic commit, crafted T06-T09 parts | `test_postgres_real_gateway_seal.py` (31) | each marked "E11 crafted probe, not product evidence" |
| create-phase items, read bound, md_* read functions | seal (`CreatePhaseDeadlineTests`), fence (`ReadBoundTests`, `RowPolicyReadTests`), `test_postgres_real_gateway_mdread.py` (14) | refused after `complete_by`, after a lapse, during a pending drain mark, after a withdrawal; no direct SELECT |
| install-kind test gains the origin-label code | `test_postgres_real_gateway_core.py` (40) | |
| R1's crafted root fixture extended for the fence | `real_gateway_kit.craft_root`, `bundle_guard_off` | |
| one list per role, TEST and REAL, schema-wide revoke, re-run of the loader write with it in place | `test_real_role_lists.py` (14, pure), `test_postgres_real_loader.py` (18) | the loader's EXECUTE is the two registry functions over EVERY function of the schema; PUBLIC has none and no NULL ACL; the two insert-trigger functions on `md_*` tables are pinned as exactly `md_release_stamp` and `md_require_open_release` |
| catalog audit shown on TEST (pass as TEST; TEST-only functions reported as REAL) and each crafted drift | `test_postgres_real_catalog_audit.py` (27) | drifts: executor granted a publisher function; executor owning a table and a function; loader granted a write on `rw_head`; loader `SELECT` on `app_user` (R2 L-2 probe); executor `SELECT` on `md_quote`; column-level grants; `MAINTAIN` on the drain-mark table for loader, executor, publisher, and on the three `rwp_` tables for executor and publisher; PUBLIC `EXECUTE`; sequence / schema grants; grant option; barrier / policy removed or made permissive; unknown deferrable constraint; guard-name collision; a function the files do not create or without a pinned search path; an `md_*` table without a read function; the install row of the other kind |
| label tests | `test_real_labels.py` (18, pure), `test_postgres_real_reader_audit.py` (2) | below |
| LOW-7 | `test_real_loader.py` (6, pure), `test_postgres_real_loader.py` (`LoaderEntryTests`) | below |

**Mutation checks (a guard changed in the working tree, targeted modules run, change reverted; fail counts are failures + errors as the runner reports them, subtests counted separately).**
| # | Mutation | Result |
|---|---|---|
| M1 | fence without its `phase = 'OPEN'` test | SURVIVED the first test set (fence module 15 tests OK). Added `WriteAfterTheSealTests` (a write after the seal, each barrier alone): now 2 subtests fail. This is the one gap the mutations found in the first set |
| M2 | fence without its deadline test | 2 errors (`CreatePhaseDeadlineTests`, both subtests) |
| M3 | `rw_row_guard` made PERMISSIVE | the installer's own audit refuses the install: 15 of 15 fence tests error (`RW_AUDIT_CONTROL_MISSING` on five tables) |
| M3b | `rw_row_allowed` returns true (policy hollow, audit cannot see it) | 11 fail (matrix "each barrier alone" 7, read bound 2, policy read 1, after-seal 1) |
| M4 | journal without its root / purpose / phase / deadline tests | first set: 1 fail (after-seal `[journal]`). Added `test_each_barrier_alone_refuses_a_write_under_the_wrong_lease`: now 3 fail |
| M5 | policy without its read deadline | 2 fail (`ReadBoundTests`) |
| M6 | `rw_validate` without `rw_check_artifact` | 16 fail (seal module) |
| M7 | origin guard without the result-flag equality | 2 fail |
| M8 | `rw_seal` without the link check | 2 errors (the bundle guard's own link check still refuses at COMMIT; the seal-time test is what notices) |
| M9 | `rw_archive` without its deadline test | 2 fail |
| M10 / M11 / M12 | `rw_md_guard` without DEADLINE / RELEASE / PURPOSE | 5 / 40 / 2 fail |
| MP1 | executor granted `SELECT` on `md_quote` in `real_roles` | 3 fail (2 pure role-list tests, 1 PG md read test; the install's own audit reads the same list, so only the hand-written constants catch it) |
| MP2 | PUBLIC revoke replaced by `SELECT 1` | 1 fail + 18 errors (the install audit refuses; the statement-list test fails) |
| MP3 / MP3b | loader entry without the None check / passing `exchange_of=None` on | 4 / 2 fail |
| MP4 | label mapping ignoring the row's ledger origin | 1 fail |
| MP5 | catalog audit looking at `rw*` / `md_*` relations only (the old loader catalog's blind spot) | 4 fail, among them the loader-`SELECT`-on-`app_user` probe |
| MP6 / MP7 | `"synthetic":true` literal outside the scope twin in the fence file / display wording in an object-name file | 1 / 1 fail |
| MP8 | `rw_bundle_complete` dropped from the expected deferrable inventory | the installer's audit refuses the install: the audit module errors throughout |

**Deferrable-constraint inventory of each branch (4.4 Step 2, item 2).** Keyed (constraint, table, kind): `ledger_event_transfer_pairing` (`ledger_event`, trigger), `rw_root_link_portfolio_fkey` (`rw_root_link`, FK), `rw_bundle_complete` (`rw_lease`, trigger), `rw_lease_deadline_guard` (`rw_lease`, trigger), `web_csv_source_key_report_id_fkey` (`web_csv_source_key`, FK). Real branch (the core alone, the crafted REAL file list) and fictional branch (TEST catalog) have the SAME five; the TEST-only part creates no constraint. Shown by `test_the_deferrable_inventory_is_the_same_with_and_without_the_test_only_part` (symmetric difference empty), by the hand-written set in the audit test, and by the audit itself, which reports any other deferrable constraint (`RW_AUDIT_DEFERRABLE_INVENTORY`) and a second constraint with a guard's name (`RW_AUDIT_GUARD_NAME`). The last item belongs to a table no real path writes (the executor has no privilege on it).

**LOW-7 (R4a): the choice.** `write_release` without `exchange_of` can store a real reading on an unmapped or unadmitted market. I chose (a) made structural: `persistence/real_loader.load_release(conn, release, manifests, contents, calendars, *, exchange_of)` refuses `exchange_of` that is None or not callable (`RW_LOADER_NO_IDENTITY`) before any statement, then calls `write_release(..., exchange_of=exchange_of, count_rows=False)`. The REAL path's loader calls this function. Reasons: (b) would change `write_release`'s documented owner-side default, which R4a pinned in `test_marketdata_listing_market_gate` (`exchange_of=None` is how those tests call it) and which the 1.16 label describes; (c) a database check needs the listing's market inside the database and the loader role is deliberately given no read of the identity tables. `src/marketdata/` and R4a's test files are untouched; the 1.16 wording stays true. Residual: a caller that bypasses `load_release` and calls `write_release` itself with `exchange_of=None` is not stopped by this wrapper (the owner-side tests do exactly that); the read side still fails closed. The check is a convention enforced by the one entry the loader code is to use, not by the database; a static check that the R4b / R5 loader code imports `load_release` and not `write_release` is for the increment that writes that code.

**Reader audit (fact 11, section 1 item 6).** (1) The files of `src/` and `web/src` that refer to an S2 object are pinned (five, all gateway SQL or object-name lists): a new reader is a visible change. (2) Outside identifiers, none carries `fictional`, `sandbox`, `synthetic` or `invented`, a fact-11 label or a mode string. (3) The S2-reading SQL names `synthetic = true` only in `rw_origin_expected` (the scope twin) and the root table's check. (4) The 18 fact-11 files of `src/` (narrow terms, the fact's own: 17 Python files plus migration 0017) and 7 non-test `web/src` files each have a written disposition in `test_real_labels.py`, and none refers to an S2 object. The widened terms hit many more files (`src/` has about 90 files with `synthetic`, `invented` or the like, mostly as data flags in the engines and the market-data modules; `web/src` has 19 non-test files); the design says the audit uses the terms, not the count, and asks for the hits "that can reach a real root's output", so I did not list the flag-carrying engine and market-data modules one by one: they take the flag from their input and none reads an S2 object (shown for every file by the first check). That grouping is mine; the owner or the reviewer may want the long list. (5) Behavioural: on a crafted root (a canonical `portfolio` row + root link, no `web_saved_sandbox` row) `WebAccountStore.list_portfolios` returns nothing and `WorkspaceStore._initial` raises 404 `NOT_FOUND`; with a `web_saved_sandbox` row added (control) both find it. Dispositions of the F2 guarded files rest on my reading of their hits, not on a test of each.

**Label tests.** `real_labels.root_labels(row)` is a pure function of the four stored origin fields: it refuses a missing field, a non-bool, a combination no scope produces, and `personal_holdings = true`; it takes no scope, mode or install kind. Tested on in-memory rows of both origin values (built from `real_scope.SCOPES`, never stored or served); TEST_SWITCH and SYNTHETIC_TEST rows, their labels and a built TEST_SWITCH snapshot contain no `REAL_SOURCE` and no `PROJECT_CONSTRUCTED`; the render test on the in-memory `REAL_SOURCE` row shows none of the four display words in any of its server-built strings, with a control that the check can see them in the invented-origin strings. The claim-limit sentences C1-C7 / S1-S5 of 7.4 are R5's and R7's.

**Decisions the contracts did not cover.**
1. The real branch's envelope, question, binding, issued-result and manifest shapes (`finweb.real.issued_envelope/1`, `service_question/1`, `service_binding/1`; key sets in `rw_check_artifact`). They are my reading of 4.2 / 4.4 and R5 must build to them or the Quant / owner change them with R5 in view, since after R3 no increment adds gateway SQL.
2. The fictional branch's `rw_check_fictional` keeps the four validated identifiers of F2's check and does not carry F2's CP5-specific checks.
3. Executor grants beyond the design text: `SELECT, INSERT` on `issuer`, `instrument`, `listing` (the create books a listing; they have no root and are not fenced) and `SELECT` on `app_user` (admit checks the owner in a definer function).
4. `rw_operation.kind` admits `CREATE` only. The mandatory link is the column `provenance_context_sha256` (a hex digest, checked by `rw_link_verify` against the registry), deliberately without a foreign key to the registry.
5. `RW_ORIGIN_MISMATCH` is reported together with the branch's other predicate codes inside `RW_SEAL_REFUSED` (DETAIL); a structural failure raises its own code at once. The result's `synthetic` flag, wherever it appears (envelope, manifest, valuation manifest, response), must equal the scope's axis: a TEST_SWITCH result that says false is a mismatch.
6. `rw_precheck` kept (F2's `gw_precheck`), identifiers only. The TEST-only function is granted to no role (the core calls it as the owner at run time).
7. `_install_gateway_body` takes `kind`; `install_test_gateway` still records TEST only, and product code never writes install kind REAL.
8. The migration trigger `ledger_event_before_insert` is not SECURITY DEFINER and reads `account` with the executor's privileges; the row policy hides the account without a lease, so a lease-less `ledger_event` insert fails first on that table's CHECK (`ledger_event_append_identity_present`) or on the fence. Tests that switch barriers off for `ledger_event` switch `account`'s policy off too. `benchmark_selection_before_insert` needs the session `search_path` to start with the schema.
9. The audit compares every relation, sequence and function of the schema, including migration objects, for four principals. A function created later carries PostgreSQL's default PUBLIC `EXECUTE`, so the audit reports `RW_AUDIT_PRIVILEGE_DIFFERS` as well as the function-set finding; after an owner change PostgreSQL moves the ACL entries, so the ownership drifts have installs of their own and are not reverted.
10. The executor-fired migration triggers (`ledger_event` insert triggers, `benchmark_selection_before_insert`) DID fire under the revoke in R3's crafted probes: the executor's own connection inserts `ledger_event` rows in the seal probes (`real_bundle_probe.write_account_and_event`) and in the fence module's all-barriers-off control, on installs that have the revoke, and the inserts succeed. That is E11 crafted evidence on a disposable database, not the product path; per the design the first PRODUCT firing is R5's `SYNTHETIC_TEST` create (2.6 / 1.2 rule 5.3 (e); TR6-L2) and its exit states it. The loader-fired ones (`md_release_stamp`, `md_require_open_release`) are shown under the revoke by the loader write.

**Advisory-lock key (RR-L2 / R2 L-5): position, a carried limit.** Not closed. Any connected runtime role can hold `pg_advisory_lock` on the root, publish or registry key and make the admit, publish or register of another role fail after its `lock_timeout` (fail closed with a coded error, nothing recorded, the same command can be re-run; no wrong value is produced). I found no cheap closure that stays inside R3: (i) a row lock instead of an advisory lock needs a table privilege the loader lacks, but a create has no `rw_root_link` row to lock before admission registers it, and publish and register have no row at all, so they would lock a singleton (`rw_mode`), serialising every publish; (ii) a salted key hides the key only until a session reads `pg_locks`, which any role may do and which shows the held keys; (iii) either is a change to R1 / R2 SQL after their independent reviews and their concurrency evidence, in the last increment allowed to add gateway SQL. **Correction (technical review of R3, L-2): this sentence said R3 adds no advisory lock, and that is wrong.** The fence file has none, but R3 edited `rw_admit` (`real_workspace_v1.sql:380`) to take a SECOND exclusive transaction advisory lock, the operation lock `rw.op:<schema>:<owner>:<operation>` (key masked below 2^62 like the root and publish locks), so that two admissions of one operation id serialise. Any session that can call `pg_advisory_lock` with that key can hold it and make the admission of that operation fail after its `lock_timeout` (fail closed, nothing recorded). It is the same exposure as the root key, falls under the same carried RR-L2 limit, and is not narrowed by anything R3 added. R1's marker test was edited to accept the extra lock (`x1.py` `MarkerTests`). The exposure is narrowed, not removed, by PD-0070 (the roles that can connect). If the owner wants it closed, it is a reviewed change to three call sites with a new concurrency test, best made before R5 builds on `rw_admit`; I recommend stating it in the exit and in design 8.

**Design note for the next design revision (not code).** R2's guarded-load narrowing (create / reproduce only) extends E28 to the registry: the loader's registry get function reads the bundle with payload bytes, and the reviewer already noted that this goes to design 8.2.

**Open items.** (a) Dispositions of the F2 guarded files and the widened-term grouping above rest on reading; a reviewer may want the long list. (b) LOW-7 is enforced by the entry function, not the database. (c) The real branch's accepted side and the REAL catalog are first read at R8. (d) The first PRODUCT firing of the executor's migration triggers without PUBLIC `EXECUTE` is R5's (crafted firings are in R3's probes, decision 10). (e) The advisory-lock limit above. Scratch: `$TMPDIR/pg_full.log` (the PostgreSQL run's log).

## F1 R3 fix round (2026-10-26)

Engineer's self-validation; not a review. Answers the independent review of the R3 build (`reviews/TECH_REVIEW.md`, "F1 R3 build", FAIL / HOLD: one HIGH, two MEDIUM, seven LOW). Nothing committed. The review's reading of H-1 is right and is the main change: the first R3 seal checked documents the tests had written by hand, in a shape no service issues.

**Result.** Default suite: `Ran 3613 tests in 169.772s` / `OK (skipped=767)`. PostgreSQL suite (the brief's prefix, as in the R3 section): `Ran 3613 tests in 380.172s` / `OK (skipped=113)`. The seal module now has 45 tests (31 before), the catalog audit module 32. After both runs: no `finweb_it%` database and no `finweb_it%` or `rw_%` role (read-only query as `finweb_dev`); no background process.

**H-1. The seal accepts what the services issue.**
- *Real branch* = the performance service's `ComputationResult.to_canonical_dict()`: keys `manifest_id, manifest, result_digest, metrics`, a FLAT manifest (`finweb.computation_manifest/1`), `result_digest = sha256(canonical metrics list)`. `rw_check_real(env, issued, response, ctx)` reads exactly those fields: O4a is `manifest.synthetic` and every `metrics[].synthetic` false; O4b is `manifest.split_detection = F8B_DRY_RUN`; `RW_REAL_RELEASE_DIFFERS` is `parent_release_id` (else `release_id`) against the snapshot's `release.release_id`; `RW_REAL_POLICY_DIFFERS` is `detection_policy[0] = ["digest", snapshot.f8b_policy_digest]`.
- *Fictional branch* = the existing integration's CP5 Result `{manifest, manifest_id, result_digest, metrics, clusters, exposure_decompositions}` with its own `finweb.local_fictional.service_question/1` and `service_binding/1`. `rw_check_fictional` is a fork of F2's `gw_check_artifact` that accepts those bytes: envelope shape, question equal to the one the gateway's fields imply, binding equal to the one the issued fields imply, native digests, CP5 manifest and valuation-manifest fields, capital-policy origin, the identity-facts digest, the synthetic flags, the F8B dry run, no terms check, and the release and F8B policy re-keyed to the S2 snapshot.
- *Common*: `rw_check_artifact` checks bytes, canonical forms, the envelope's identifiers, the response equals the stored root and revision, the manifest id is recomputed, the origin-label guard reads the `synthetic` flag wherever the issued bytes state it (manifest, nested valuation manifest, each metric), then dispatches with one `ctx` object (snapshot plus the gateway's own identifiers).
- *Tests call the services.* `tests/product/real_service_producers.py` calls `financial_service_integration.issue_local_service` (selector CP5_DIVERSIFICATION, and PERFORMANCE_SYNTHETIC_REFUSAL for the performance service) on the integration's own inline world, re-addressed to the disposable database's ids (the capital policy is scoped to the new root and the context fingerprint recomputed by the integration's own function; a stub connection supplies the database's pin). `AcceptedCreateTests.test_h1_the_seal_accepts_exactly_the_bytes_the_existing_fictional_integration_issues` seals those bytes unedited, commits, and compares the archive with a second call of the service (byte equal, question and binding byte equal). `test_h1_the_real_branch_is_shown_the_performance_services_own_output_and_refuses_it` seals the performance service's bytes on TEST_SWITCH and gets exactly `RW_O4A_SYNTHETIC_RESULT, RW_REAL_RELEASE_DIFFERS, RW_REAL_POLICY_DIFFERS`. **An accepted real-branch commit is impossible before R8** (the service refuses invented data, so its only output states `synthetic = true`; a `synthetic = false` result of invented data is forbidden). A further test sets the release and the policy to the snapshot's and shows those two codes disappear (only O4a remains), and seven cases (release without policy, policy without release, another release, another policy digest, a policy not in the digest form, parent versus release_id precedence both ways) show each binding compares the value, not only the shape.
- *Stop-and-report list (predicates the old design text named that a service output cannot carry, so they are NOT checked; none was replaced by an invented wrapper).* (1) `projection_digest`: the performance manifest has no projection digest; the snapshot has one. (2) The snapshot's `identity_digest` against the manifest's `identity_digest`: the manifest's digests the identity FACTS this computation asked for, a different quantity. (3) The snapshot's registry digests against `source_registry_digest`: the manifest's hashes the full `SourceRecord` objects, the snapshot's hashes its own record dicts. (4) The manifest `origin`: neither service issues an origin object (the old probe invented one); the origin is bound by the root row, the envelope and the flags the services do issue. (5) The fictional question's and binding's `context_id` against the lease's context: the integration's context id is the SHA-256 of its own fingerprint snapshot, not the S2 snapshot's id, and no issued field relates the two. (6) F2's fixed-fixture hashes, the capital policy against the snapshot's, and the identity facts against the snapshot's lookup answers: the S2 snapshot has no field to check them against. (7) A question for the Quant: I read `f8b_policy_digest` as the `digest` member of `performance_service.policy_reference(policy)` (`detection_policy[0] == ["digest", X]`); the service constants in the tests are taken that way, and the snapshot field is not defined anywhere else I could find. (8) The real branch's accepted commit (above).

**M-1 / L-6. Executor grants.** `real_roles.EXECUTOR_TABLES` no longer grants `app_user`, `issuer`, `instrument` or `listing` (SELECT or INSERT): admit reads `app_user` in a definer function, and nothing in R3 needs the others. Every suite passed without them. `test_a_lease_less_executor_write_to_the_identity_tables_is_refused_and_so_is_every_read` shows a refusal with and without a create lease for each of the four, and `has_table_privilege` false for 7 privileges on each. **R5 design question:** if the shared create tail's world builder must read or write an identity row (the instrument and listing a position names), that is a lease-checked read or write FUNCTION (gateway SQL), not a grant; I recommend the main session decide it before R5 and that R5 not re-add the grant.

**M-2. Create-phase withdrawal and cancellation (3.2, marked R3).** `CreatePhaseWithdrawalTests` (seal module, W = 3): (a) a stalled create (admitted with the root and operation advisory locks in place, five rows written, stalled past `complete_by`, every session timeout 0): the withdrawal records its mark, reports `NOT_YET_EFFECTIVE` and names the blocking lease by backend; the publisher can neither terminate nor cancel it; the owner terminates it; the withdrawal then finishes; no economic row, journal row, lease row, artifact or advisory lock remains. (b) the create over its statement timeout (QueryCanceled) and the create cancelled by `pg_cancel_backend`: each rolls back wholly, the locks are released with the connection still open, and the withdrawal then finishes in under 4 s.

**L-1. Catalog audit.** `real_catalog_audit`: the privilege comparison covers every routine kind, procedures included (the prokind filter is gone); the row policies are compared by DEFINITION (exactly two, kinds, command, role list, USING and WITH CHECK, normalized for quoting and schema qualification) with the new code `RW_AUDIT_CONTROL_DIFFERS`; the fence, journal, truncate, immutability and lease-guard triggers by `tgtype`, the function they run (`tgfoid`, by name and schema) and, for the guards, DEFERRABLE INITIALLY DEFERRED; memberships (`RW_AUDIT_MEMBERSHIP`): a runtime role or the owner as the member of any role whatever its options (SET TRUE lets it `SET ROLE`, which `has_*_privilege` does not report for a NOINHERIT role), and any role that may SET or INHERIT one; a membership with ADMIN OPTION alone is tolerated (design 5.3 (a), (b) is the preflight's). Tests: a procedure with PUBLIC EXECUTE (and the control with it revoked), eight policy definition drifts, eight trigger definition drifts, four memberships from runtime roles with SET TRUE or FALSE, a role outside the install with SET, INHERIT and ADMIN-only.

**L-2. Corrected** in the R3 section above (the operation lock is an advisory lock and falls under the carried RR-L2 limit).

**L-3. Relabelled.** Every md_* read-function test now says "E11 crafted probe, not product evidence" (module and test docstrings).

**L-4. Surviving mutants, killed.** Method as before: edit the working tree, run, revert (git shows no mutant left). Failures counted on the module named:

| Mutant (reviewer's name) | Test that kills it | Failing tests with the mutant |
|---|---|---|
| MF `rw_link_verify` member comparison removed | seal `MandatoryLinkTests.test_the_link_compares_the_candidates_members_with_the_snapshots` (registered, same-context, same-scope candidates differing only in members; control: extra key, same members, commits) | 4 sub-cases (seal module) |
| MG `rw_md_file` release `WHERE` removed | mdread: a stray `md_file` row no release lists, now present in every md test | 8 (mdread module) |
| MH fence `RW_MULTI_ROOT_REFUSED` removed | seal `FenceMultiRootTests` (transfer to another root's account refused; control inside the root) | 1 (fence module alone: 0) |
| MO `rw_publish` test-scope origin check removed | seal `O4AndLabelTests.test_publish_refuses_a_test_scope_snapshot_...` (direct call by the publisher with crafted bytes; control publishes) | 3 sub-cases |
| MU `rw_check_fictional` no-terms-check predicate removed | seal: the function called as owner with the real bundle's documents and a crafted context | 1 |
| MC envelope `scope` check removed | seal struct case "envelope names another scope" | 1 |

New mutants of the H-1 code, each run (first-version survivors are named, and killed by the test added): O4a manifest clause 1, O4a metrics clause 1 (the first mutant only removed one disjunct and survived until the manifest-only and metrics-only cases were added); real release predicate 3; real policy digest VALUE comparison survived (0) until the value cases were added, then 1; real `result_digest` recomputation 2; fictional question equality 1; fictional binding equality 1; fictional result-digest recomputation survived (0) until the late-edit digest cases were added, then 2; fictional identity digest 1; fictional release predicate survived (0) until the fictional release and policy cases were added, then 1; fictional policy digest value 1; capital-policy origin 1; origin-label `flags_bad` 7; manifest-id recomputation 2.

**The reviewer's three equivalent mutants, and why they are equivalent** (each was also run: MD against the seal and x1 modules, ME and MX against the seal and fence modules; 0 failures each, as predicted):
- *MD* (the archive's `l.owner_id IS DISTINCT FROM o`): the artifact is read by `(owner = o, operation)`, so `a.owner_id = o`. The function also requires `l.root_id = a.root_id` and `l.context_id = a.context_id`, and a lease can exist only on a root-link row `(root, owner, context)` whose `root_id` is its primary key, so a root has one owner. Hence `l.owner_id = o` follows from the root and link tests.
- *ME* (`j.action <> 'INSERT'` in `rw_validate`): the journal row of an UPDATE or DELETE is produced only by an UPDATE or DELETE of a fenced table by the executor; the executor holds SELECT and INSERT on those tables and nothing else, so no such row can exist, and the test is a guard for a grant that is not there. (Reviving it would need a grant the audit refuses.)
- *MX* (`n <> op.journal_count` in `rw_validate`): the executor can only INSERT, each insert adds a row of the root and a journal row, and `rw_state(root)` (compared with the sealed digest in the next conjunct) changes with every inserted row; so a changed count implies a changed state digest. The count remains as a cheaper, earlier check.

**L-5. Both orderings of the cap** (`valid_in` 120 s: W decides; 2 s: `complete_by = valid_until`) now run in the seal-deadline test and in the seal-to-COMMIT pause test, with the lease's own `complete_by` compared with `valid_until` in each.

**L-7 / RR-L2.** Carried limits, unchanged (the correction above is part of RR-L2). The prepared-transactions observation is left for the R6 preflight; nothing built.

**Decisions the contracts did not cover.** (1) The signature of the branch checks is `(env, issued, response, ctx)` with `ctx` built by the core. (2) O4a reads the manifest flag AND every metric flag. (3) The test world is the integration's own inline world dated 2026-01-05; the probe's ledger event is dated 2026-01-02. (4) `RW_AUDIT_CONTROL_DIFFERS` and `RW_AUDIT_MEMBERSHIP` are new finding codes; ADMIN-only memberships are tolerated. (5) The fictional binding's `synthetic` stays the service's `true`, so a fictional result stating `false` is refused by the predicate codes (and the label guard), not by a binding mismatch. (6) A stray `md_file` row is part of the md fixture. (7) The seal tests mark every bundle "E11 crafted probe": the write path is crafted; the issued bytes are the services'.

**Open items.** (a) The stop-and-report list above (eight points, two are questions for the Quant: the meaning of `f8b_policy_digest`, and whether R8 will add the manifest fields (1) to (4) or the design drops those predicates). (b) The real branch's accepted commit and the REAL catalog are first read at R8. (c) The R5 identity-row question. (d) The advisory-lock limit (RR-L2), including the operation lock. (e) Prepared transactions, for the R6 preflight. Scratch: `$TMPDIR/default_full.log`, `$TMPDIR/pg_full.log`.

## F1 R3 follow-up: the stop-list dispositions, PD-0073 and the identity-table question (2026-10-26)

Engineer's self-validation; not a review. Answers the PM's decisions on `implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md`, PD-0073 (origin carried by the stored result and the seal) and the Quant's four conditions (`methodology/CP2_ORIGIN_CARRIAGE_NOTE_2026-10-26.md`). Nothing committed. The disposition note was updated (status table, "Decided and built", "Obligations carried to later increments").

**Result.** Default suite: `Ran 3620 tests in 914.209s` / `OK (skipped=774)` (the run was slow because the machine was loaded; the previous run took 169.772s for 3613 tests). PostgreSQL suite (`FINWEB_PG_INTEGRATION=1` with the brief's socket, database and users, `discover -s tests/product -t .`): `Ran 3620 tests in 413.981s` / `OK (skipped=113)`. After both runs: no `finweb_it%` database or role and no `rw_%` role (read-only query as `finweb_dev`, empty result). The suites were run one after the other, not concurrently. The seal module has 52 tests (47 before this round: 45 after the fix round and 2 `IdentityRowsTests`).

**What was built (all in `src/persistence/real_fence_v1.sql`; no other source file changed).**
1. `RW_REAL_PROJECTION_DIFFERS` (5.1), `rw_check_real`: `md_release.projection_digest` of `snapshot.release.release_id`, read in the database, `IS DISTINCT FROM snapshot.projection_digest`. A missing row is NULL, hence distinct, hence a refusal. Fictional branch untouched (T10).
2. `RW_REAL_REGISTRY_DIFFERS` (5.3, my variant), `rw_check_real`: `manifest.source_registry_digest IS DISTINCT FROM snapshot.registry.used_source_digest`. Until R4b re-encodes the snapshot side with the engine's own `source_registry_digest(...)` the code appears on every real-branch refusal; the refusal-list tests pin it (`test_h1_the_real_branch_is_shown_...` and the O4 list tests), so the state is visible and R4b must change those lines. The test that shows the predicate does not fire when the digests agree sets the manifest field to the snapshot's.
3. Response-origin conjunct (PD-0073), `rw_check_artifact`, in the origin-label row guard (both branches): `response_obj->'origin' IS DISTINCT FROM {market_origin, ledger_origin, personal_holdings, synthetic}` built from the immutable root row.
4. Root binding (condition 1), `rw_check_artifact`, generic over both branches: `manifest.portfolio_id` and `portfolio_id` of every object in the issued document whose `schema` matches `^finweb\.[a-z_.]*manifest/` must equal the root's id; NULL, an absent key and another portfolio are `RW_MANIFEST_DIFFERS`.

**Tests added (seal module).**
- `O4AndLabelTests.test_the_real_branch_binds_the_snapshots_projection_digest_to_the_database` (projection differs; release not loaded; control).
- `O4AndLabelTests.test_the_real_branch_binds_the_registry_digest_the_service_issued_to_the_snapshots`.
- `O4AndLabelTests.test_the_stored_result_must_carry_the_roots_origin_labels` (condition 2: origin absent, null, and for each of the four origin fields changed and absent; both branches).
- `StructuralRefusalTests.test_every_manifest_the_seal_sees_names_the_root_and_a_null_portfolio_is_refused` (condition 1: top-level null, another portfolio and absent; injected null, another portfolio and without the key; on the fictional branch the nested valuation manifest null and another portfolio; controls: a nested manifest naming the root commits on the fictional branch and is not refused with `RW_MANIFEST_DIFFERS` on the real branch).
- `ReplayAndArchiveTests.test_the_archive_read_returns_the_four_origin_fields_and_refuses_a_result_that_lacks_them` (condition 3, R3's SQL surface: `rw_archive` returns the stored response with the four fields and the root's columns; a crafted stored response without them, written by the owner with the immutability trigger disabled for the test only, is refused at read).
- `real_bundle_probe.py`: `response_of` carries `origin`; the crafted `md_release` row for the projection predicate; `edit_issued` hook.

**Condition 4 (`SCOPE_MISMATCH` by portfolio).** `grep -rn "SCOPE_MISMATCH\|history_problem\|baseline" src/persistence/real_*.py src/persistence/real_*.sql` finds nothing, so R3 has no such check to bypass and adds no mechanism for it. The root binding is an additional refusal inside the seal, not a replacement.

**Mutation table (edit the working tree, run the seal module, revert; `git diff` shows no mutant left).**

| Mutant | Killed by | Failing with the mutant |
|---|---|---|
| projection predicate disabled (`false AND`) | projection test | 2 sub-cases (module: 1 failing test) |
| projection compared with `<>` (NULL-lenient, a missing release passes) | projection test, release-not-loaded case | 1 |
| registry predicate disabled (`false AND`) | AcceptedCreate H-1 test and the O4 list tests that pin the code | at least 3 tests |
| origin conjunct removed | `test_the_stored_result_must_carry_the_roots_origin_labels` | all sub-cases for absent and changed origin |
| origin compared without `market_origin` / `ledger_origin` / `personal_holdings` / `synthetic` (four mutants) | the same test | 4 failures + 2 errors each, the named field's "changed" and "absent" cases on both branches, plus the null case |
| both root-binding terms disabled | `StructuralRefusalTests` root-binding test | failing on both branches |
| nested scan made NULL-lenient (`<>`) | the same test | 5 sub-cases (injected null, injected without key, valuation manifest null, ...) |
| origin conjunct removed (archive test only) | `ReplayAndArchiveTests` archive test | 1 |

Reverted state checked: `real_fence_v1.sql` has one `response_obj->'origin' IS DISTINCT FROM origin_row` conjunct, no `false AND`, no `<> a.root_id`. (The per-field mutant first failed with an operator error on `jsonb - unknown`; the `::text` cast fixed it, and the fourth run above is the accepted one. One earlier weak registry run killed 3 tests, the later runs more.)

**B (identity tables).** Unchanged from the follow-up: no executor privilege and no identity writer function; `IdentityRowsTests` (2 tests) shows a create that names a seeded listing commits, a missing listing is a foreign-key violation, and the executor's SELECT and INSERT on the three tables are refused. Open item for R6/R8: the owner-run, idempotent real identity seed.

**Decisions the contracts did not cover.** (1) The root binding is a generic scan over every manifest-shaped object (`schema` matching `^finweb\.[a-z_.]*manifest/`), not a list of known paths, so a future service's nested manifest or an injected one is covered without a code change. (2) A missing, null or non-string `portfolio_id` in a manifest-shaped object is a refusal. (3) The response-origin conjunct is placed in the row guard so it fires before either branch; a mismatch is listed as the guard's existing code `RW_ORIGIN_MISMATCH` (no new code). (4) The registry predicate is built before R4b with the visible side effect described above, as the PM asked.

**Limits kept (PD-0073).** The origin fields do not by themselves prove the data is real; `synthetic=false` iff `REAL_SOURCE` is a rule on labels and flags, and real provenance rests on the loader, the registry and O1/O2/O4, which have no control before R8. 5.2, 5.5 and 5.6 are dropped provisionally with narrowed claims; the re-review checks that no HG4 or P9 claim depends on them.

**Open items.** (a) R4b: compute `registry.used_source_digest` with the engine's `source_registry_digest(...)`; check member sources equal sources with a file in the release; update the pinned refusal lists. (b) R5: the four origin fields in every result and on reproduce, read, export and the read tail, from the stored response or the root via `rw_archive`; labels read the stored fields. (c) Real identity seed (R6/R8). (d) An accepted real-branch commit is impossible before R8. (e) RR-L2 advisory-lock limit. Scratch: `$TMPDIR/default_full.log`, `$TMPDIR/pg_full.log`.

## F1 R3 re-review findings RR-L1 to RR-L4 (2026-10-26)

Engineer's self-validation; not a review. Answers the independent re-review of R3 (`reviews/TECH_REVIEW.md`, "F1 R3 build, re-review", PASS_WITH_FINDINGS, LOW only). Nothing committed. RR-L5 (design 1.1 wording) is the main session's design revision; nothing was done for it.

**Result.** Default suite (`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`): `Ran 3627 tests in 160.930s` / `OK (skipped=781)`. PostgreSQL suite (the brief's prefix, `discover -s tests/product -t .`): `Ran 3627 tests in 378.289s` / `OK (skipped=113)`. Run one after the other. Leftover check (read-only, as `finweb_dev`): no `finweb_it%` database or role, no `rw_%` role. The seal module has 53 tests (52 before), the catalog audit module 38 (32 before).

**RR-L1. Root binding by explicit list.** `rw_check_artifact` no longer decides what to scan by a naming pattern. Three rules over every object anywhere in the issued bytes: (1) an object with a `portfolio_id` key names the root, whatever its schema or none; (2) an object whose schema is on the list read from `src/` (`finweb.computation_manifest/1`, `diversification_manifest/1`, `drift_manifest/1`, `insight_manifest/1`, `risk_manifest/1`) must carry `portfolio_id` = the root; (3) an object whose `schema` contains "manifest" in any case and is on neither list is refused. The market-data file manifests (`finweb.marketdata.file_manifest/1` and `/2`) are listed apart, so they neither need the key nor fail closed (if one carries the key, rule 1 applies). The test `StructuralRefusalTests.test_every_manifest_the_seal_sees_names_the_root_and_a_null_portfolio_is_refused` now has, on both branches, the reviewer's four escapes (digit, upper case, hyphen, no schema key), a numeric `portfolio_id`, an unlisted manifest schema that names the root, one in capitals with no portfolio, a listed schema with the key absent, and a file manifest carrying another portfolio; and four controls that must not be refused with `RW_MANIFEST_DIFFERS` (a nested manifest naming the root, file manifest v1 and v2 without the key, an object naming the root with no schema). The integration's CP5 bytes still commit unedited.

| Mutant | Failing sub-cases |
|---|---|
| rule 1 disabled | 6 (no schema key, numeric id, file manifest with another portfolio; both branches) |
| rule 2 disabled | 4 (injected without the key; listed schema with the key absent; both branches) |
| rule 3 disabled | 4 (unlisted schema naming the root, unlisted in capitals; both branches) |
| file-manifest exemption removed | 4 (v1 and v2 controls, both branches; 2 failures, 2 errors) |

The reviewer's four spellings are each refused by rule 3, and by rule 1 where they carry another root's id; the table shows each rule has cases only it kills.

**RR-L3. N7, N8, N9 on the real branch.** `test_each_part_of_the_real_branchs_service_output_that_does_not_match_is_refused_with_its_own_code` gains seven cases: a risk-manifest schema naming the root (it passes the generic scan, so only the real check refuses it) and a non-manifest schema (N7); an account-scoped NAV `ACCOUNT:<uuid>` and an absent scope (N8); another `as_of` and an absent `as_of` (N9); and another reporting currency. Mutants on `rw_check_real`'s structural conjunct, each run on the seal module: N7 (schema term removed) 2 failing; N8 (scope term removed) 2 failing; N9 (`as_of` term removed) 2 failing. All reverted.

**RR-L4. Member sources against the release's files: they can differ, so the predicate is built (`RW_REAL_MEMBERS_DIFFER`).** The manifest's `source_registry_digest` covers the sources of every file of the release (`read_release` takes `source_ids` from `md_release_file` joined to `md_file`); the snapshot's `used_source_digest` covers its members' sources; nothing compared the snapshot's members with the release the database holds. By design they agree for HG4 (three members, a release built from exactly those), but that is intention, not enforcement. The seal now compares the sorted `(file_sha256, source_id)` pairs of the snapshot's release in the database with the sorted `(payload_sha256, source_id)` pairs of `snapshot.members`; a release the database does not hold gives the empty list and differs. This is stronger and simpler than the `release_source_digest` the PM suggested: the SQL reads both sides, so no new snapshot field, no SQL-side canonical digest, and published snapshots keep their bytes. R4b therefore adds no gateway SQL; its builder takes the members from the release's own rows (first R4b line of the disposition note). The "R3-class change" escape is removed from the note.
- Test: `O4AndLabelTests.test_the_real_branch_binds_the_snapshots_members_to_the_releases_files` (control; a further file of a source no member names; a further file of a member's source; the member missing; the member's hash under another source; another file of the member's source; a release the database does not hold).
- Probe support (`real_bundle_probe.py`, E11 crafted): the service world's release is one row shared by the class, but each setup's members differ, so `align_release` makes the release's `md_file` and `md_release_file` rows those of the setup before each bundle is made (table triggers disabled for the crafted edit only, re-enabled in `finally`).
- Mutants: predicate disabled: 6 failing sub-cases (every failing case); compare source sets only instead of pairs: 2 failing (the two cases that keep the source set and change the files), so the pair comparison is needed.

**RR-L2. The catalog audit sees function bodies and the full trigger set** (`real_catalog_audit.py`; Python, not gateway SQL, but Phase 2's `--check` relies on it).
- *Function definitions* (`RW_AUDIT_FUNCTION_DEFINITION`): each `rw_`/`rwp_` function is compared with the definition the installer's own SQL files give it, parsed from the files with the installer's marker substitution: body exactly as stored (`prosrc`), language, SECURITY DEFINER, volatility, STRICT, LEAKPROOF, PARALLEL and settings (whitespace, quotes and case normalised). The owner stays with the existing ownership check. The report carries a SHA-256 per function (`inspected["function_digests"]`), one per gateway function (more than 60). A clean TEST install and the REAL fixture both pass, which shows the parse matches every function.
- *Full trigger set* (`EXPECTED_TRIGGERS`, hand-written from the SQL files and the migrations and checked against a clean install by `test_the_expected_trigger_sets_are_the_catalog_of_a_clean_install`): on the six fenced tables, every `rw_`/`rwp_` table and every `md_` table, every non-internal trigger must be one the table expects (name, function in this schema, `tgtype`, constraint kind) and enabled for every session ('O', so a replica-only enable is a finding). A trigger the table does not expect is `RW_AUDIT_CONTROL_DIFFERS` whatever function it runs. This also brings the gateway's own triggers on `rw_install`, `rw_snapshot`, `rw_history`, `rw_drain_mark`, `rw_root_link`, `rw_head`, `rw_mode` and `rwp_*`, and the migration and `md_*` triggers, under the audit; the old comparison did not cover them.
- *Tests* (`DefinitionDriftTests`, 6 tests; E11 crafted drifts with a clean control before and after each): the reviewer's `rw_row_allowed` -> `SELECT true` and pass-through `rw_write_fence`, plus `rw_check_real`, `rw_journal_after` and a comment-only change; seven property drifts (SECURITY INVOKER, a `public` search_path ahead of `pg_temp`, an extra setting, VOLATILE, STRICT, LEAKPROOF, PARALLEL SAFE); the `zzz_probe` BEFORE trigger on `portfolio` and on seven further tables (with an AFTER trigger on `account`), and a disabled extra trigger; fourteen disabled expected triggers (migration, md, and the gateway's on tables not read before), one enabled for replica sessions only, a migration trigger re-pointed to another function, an md trigger of another type.
- *Mutants on the audit* (each run on `DefinitionDriftTests`): definition check not called: 12 failures and 1 error; `prosrc` ignored: 5; settings ignored: 2; unexpected-trigger finding removed: 9; "enabled" test weakened to "not disabled": 1; trigger function not compared: 1. All reverted; the audit module passes (38 tests).
- *Limits (stated in the module docstring).* The bodies of the migration functions (the ledger and benchmark triggers, `account_guard_identity`, the `md_*` guard functions) are not compared with the migration files, only the triggers that run them; triggers on tables outside the three groups (`web_*`, `app_user`, identity tables) are not read. A new migration trigger on a table the audit reads is a reviewed change to `EXPECTED_TRIGGERS`; until it is made the install audit refuses.

**Decisions the contracts did not cover.** (1) `RW_REAL_MEMBERS_DIFFER` compares pairs read from the database instead of adding a `release_source_digest` field. (2) Rule 3 of the root binding refuses an unlisted schema containing "manifest" even if it names the root: a new manifest schema is added by a reviewed change. (3) The audit's expected trigger table covers the fenced, `rw_`/`rwp_` and `md_` tables only. (4) The comparison of `prosrc` is byte exact, so a comment edit is a finding.

**Open items.** (a) Supersedes the earlier R4b line: R4b adds no gateway SQL for the member sources; it builds the members from the release's rows, computes `used_source_digest` with the engine's function and updates the pinned refusal lists. (b) The migration functions' bodies and the `web_*`/identity triggers are outside the audit (limit above). (c) RR-L5 is the main session's. Scratch: `$TMPDIR/default_full.log`, `$TMPDIR/pg_full.log`.

## F1 R4b (2026-10-31)

Engineer's self-validation; not a review. Built from `implementation/CP7_F1_REAL_PATH_DESIGN.md` (R4b row of 7.1; 6.1, 6.3, 6.4 [E9], 4.2, 3.3) and the three binding obligations of `implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md`. **No gateway SQL was changed** (`src/persistence/real_*_v1.sql` untouched). Nothing committed.

**Result.** Default suite (`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`): `Ran 3707 tests in 177.411s` / `OK (skipped=785)`. PostgreSQL suite (`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`, same command): `Ran 3707 tests in 394.229s` / `OK (skipped=113)`. Before R4b: 3462 tests. The shared development cluster was NOT running when this increment started (stale `postmaster.pid` after the reboot; the sandbox cannot remove it); it was started once with the documented command and the sandbox exception (the permission gate allowed it), used for the PG runs, and stopped again. No `finweb_it%` database or role remains (checked); no background process.

**Built.**
- `src/persistence/real_sidecar.py` (pure): the sidecar schema `finweb.acquisition_sidecar/1`, `encode_sidecar` (bytes out, writes nothing), `read_sidecar` (bytes in), `sidecar_failures`, `o5_failures`/`require_o5` (O5; every failed predicate of every member), `candidate_failures` (O1 to O3 and O5 together, independently), `sidecar_for`. Codes: `RW_O5_LEGACY_NULL`, `RW_O5_SIDECAR_MISSING`, `RW_O5_SIDECAR_SCHEMA`, `RW_O5_PAYLOAD_DIGEST`, `RW_O5_MANIFEST_DIGEST`, `RW_O5_SLOT_DIGEST`, `RW_O5_APPROVER_ROLE`, `RW_O5_DECISION_TRIPLE`, `RW_O5_FAILED`. O5 is bypassed in `SYNTHETIC_TEST` and `TEST_SWITCH` (empty report, `bypassed=True`).
- `src/persistence/real_registry_map.py` (pure): the one mapping from a proposal record to the engine's `SourceRecord`, and the registry digests built on it. `real_proposal.py` uses it: **obligation 1** (`used_source_digest` and `full_registry_digest` are the engine's `source_registry_digest`), `terms_url` may be null, the REAL scope's `terms_check` is exactly the engine's four fields, the REAL scope refuses the legacy null in the writer and the verifier (`RW_O5_LEGACY_NULL`).
- `src/real_tools/qualification.py` (outside `persistence`, which may not import ingest or adapters): `qualify` (reads a `FileStore` directly, E9 proposal (a); builds the release through the engine's ingest; **obligation 2**: one member per file of the release's own manifests, payload hash and manifest source; the digests below; writes the proposal with R1's writer and refuses unless R1's verifier passes it), `classify`/`HG4_CONFIRMATION_TABLE` (every member against the 6.3 table), `save_proposal` (exclusive create, the module's only write), `load_qualified` (**obligation 3 / LOW-7**: through `real_loader.load_release` with `exchange_of`, never `write_release`).
- `src/real_tools/candidates.py`: `build_candidate` (unbound, or bound to the published context) and `register_candidate` through `RealProvenanceStore` on the loader's connection; the operation id is a function of the context bytes, so a re-run reconciles.
- `real_workspace_store.py`: `RealPublisher.publish(..., sidecars=())` evaluates O5 in Python before any statement (a REAL proposal without a valid sidecar per member is `RW_O5_FAILED`, nothing recorded); CLI `--sidecar PATH` (repeatable, read-only).

**Tests.** `test_real_sidecar.py` (37 pure), `test_real_qualification.py` (39 pure, invented `TEST_SWITCH` store from `marketdata_exit_kit.build_world`), `test_postgres_real_qualification.py` (4 PG: the chain on a disposable TEST install). The PG tests read expected values from the database: `md_release.projection_digest`, `release_content`, `md_release_file` joined to `md_file`, the engine's `registry_digest_of` the port `read_release` builds from the rows, and the seal's own members comparison on the PUBLISHED snapshot row.
- O5 failing cases (REAL, in memory): legacy null; no sidecar; payload digest differs; manifest digest differs; approver role not the owner's (six spellings); decision triple missing or malformed (twelve forms); not-a-sidecar bytes; the slot not the digest of the bytes; all failures of all members listed. Control: a sidecar valid in every respect, with synthetic sources, lists O1 and O2 and no O5 code, and each O5 failure adds only its own code. Bypass under both test scopes.
- Exit items: reproducible run (same store, and two stores built alike: same bytes); digests independently derived; output passes `verify_proposal`; an edited proposal is refused and sends no statement and changes nothing in the database or the store; the run writes no file and changes nothing in the store; proposal files are written by `save_proposal` (new file only); the sidecar reader parses bytes and writes nothing (every file door closed during the calls, and a source scan). No sidecar file is written for an invented payload; the REAL scope is reached only to show REFUSALS (it needs a sidecar per member and the invented sources are synthetic, so `RW_ORIGIN_MIXED`).
- Pins changed (**obligation 3**), each with its reason in the test: `test_postgres_real_gateway_seal.py` three real-branch refusal lists lose `RW_REAL_REGISTRY_DIFFERS`, and the registry test's case "the service's own digest" now expects the code ABSENT, with the pre-R4b encoding added as a failing case. Reason: the probe's snapshot now carries the service world's own source record (`real_bundle_probe.service_content`, candidate source id = `unit.SOURCE`), so the engine digest the builder computes equals the one the service issues; before R4b the snapshot's digest was over the proposal's own dicts. `test_real_scope.py` (the `require_resolved` callers gain `qualify` and `build_candidate`, both refusing a bare scope) and `test_real_gateway_static.py` (`publish` gains the keyword-only `sidecars`, which names no source).
- Static: no R4b module calls `write_release` (only `real_loader` does, once); the run reaches the projection only through `load_release`; the module's only `open` is `"xb"`; nothing in the product imports `real_tools`; the sidecar module has no file, clock, environment, connection or random door.

**Mutants** (targeted modules `test_real_sidecar`, `test_real_qualification`, `test_real_proposal`, `test_real_scope`, `test_real_publisher_tool`; baseline 169 then 170 OK; every mutant killed, failing tests in brackets). Validator: bypass removed [48]; legacy null skipped [8]; payload check dropped [4]; manifest check dropped [4]; role check dropped [8]; triple check dropped [15]; slot check dropped [1]; first failure only [2]; first member only [4]; non-canonical bytes accepted [1]; `candidate_failures` drops O5 [1]; extra keys accepted [2]. Builder: registry digest in the pre-R4b encoding [5]; used set = every record [5]; `terms_url or None` [3]; synthetic forced true [1]; REAL legacy-null refusal removed [2]; refusal applied to every scope [71]; terms-shape check removed [2]; a member dropped [7]; member source = adapter id [27 errors]; `require_o5` skipped [4, after adding the "valid digests, invalid role/triple" test: before it only 2]; sidecars accepted in a test scope [1]; manifest digest = payload digest [10]; policy digest constant [2]; `save_proposal` overwrites [2]; classification always CONFIRMED [1]; `write_release` instead of `load_release` [3]; `needs_review` always false [1]; identity rows ignored [1]; candidate ignores the financial context [2]; candidate drops a member [3]; publisher skips O5 [2].

**Decisions the contracts did not cover.**
1. *Where O5 is enforced.* Not in SQL (the database cannot see sidecar bytes; a gateway change would reopen R3). It is enforced in Python at three points: the proposal writer/verifier (the legacy null in REAL), the qualification run (`require_o5`, before anything is written), and `RealPublisher.publish(sidecars=...)` (before any statement). The SQL publish itself evaluates O1 to O3 and the registry consultation only. Risk: a different publish tool, or SQL run by the owner, bypasses O5; the owner's publisher is the product tool and the REAL install has no other publisher path (R6/R8 procedure).
2. *Sidecar content* (design 6.1 names the fields, not their types): `payload_sha256`, `manifest_sha256`, `approver_role` (exactly "designated human product owner"), `decision` {`pd_id` `PD-NNNN`, `git_commit` 40 hex, `doc_sha256` 64 hex}, `request`, `tool`, `terms_check_reference` (non-empty texts). Canonical JSON only. The member's slot is the SHA-256 of the sidecar's bytes. The main session writes the three real sidecars with `encode_sidecar`.
3. *A test scope takes no sidecar at all* (`RW_O5_SIDECAR_IN_TEST_SCOPE`) and stores `null` in every slot: an invented sidecar's digest in a snapshot would store an invented human attestation.
4. *The digests the design does not define*, each over plain data, recomputable: `identity_digest` (issuers, instruments, listings and identifier rows of the registry, by id), `calendar_digest` (the `calendars` part of the projection document), `convention_digest` (`ConventionSet.ids()`, `PerformanceConventionSet.ids()`, the release's convention pairs), `profile_digest` (profile set version, and per member source its status, role, markets and admission), `release_digest` (the release document as `md_release.release_content` stores it), `projection_digest` (the digest `write_release` stores, passed through `stored_contents`), `f8b_policy_digest` (`performance_service.policy_reference`). The Quant owns no definition of these; R5's world builder must recompute the same values from the locked snapshot. If the Quant wants a different encoding of any of them, it is a one-function change here.
5. *Provenance candidates are built here* (R8 step 2 says the run loads "the `md_*` rows and the unbound candidates"; the R4b row does not list it). `build_candidate`/`register_candidate`: v1 manifests only (a `FileStore` cannot hold a v2 manifest), unbound before the publish and bound to the published context after it. In a test scope the publish does not refuse a missing candidate (the registry consultation is informational there; `RW_PROV_CANDIDATE_MISSING` is a refusal in REAL only), so the missing-candidate refusal is not shown here.
6. *The qualification result flags, and decides nothing about admissibility.* Adapter issues, resolution exceptions, series a label test did not admit, and members the 6.3 table does not cover set `needs_review`; the proposal is still written (the owner reviews it). The run does not decide whether the 2026-09-30 row of `AAPL_compact.csv` is an admissible print: that is the method's (the engine's V0 and the profile), reported, not re-decided.
7. *The 6.3 table is two constants* (the two rows, recomputed from the files read-only; a test recomputes them again when the files are on the machine). The NYSE calendar has no table row; its registered check is passed by the caller (`registered_checks`), and the main session names the record that registered it (design 6.1).
8. *The source registry of a REAL proposal is the whole `SOURCES.json`* (design 2.1: the full registry the snapshot was published with). A synthetic source anywhere in it makes the run `RW_ORIGIN_MIXED`; the real file has none.

**Open items.** (a) **Identity seed.** Nothing writes `issuer`, `instrument` and `listing` in the real database before the load; the tests seed them as the owner (E11). The step is owner-run (R6 install plan / R8), checked against `identity_digest`. (b) **Registration sequence.** `register_candidate` is the tool the R3 note asked R4b's or R6's plan to name; R6's plan still states the loader's `LOGIN` windows around it. (c) **No real run.** The three real sidecars, the real identity registry and the real configuration of the run (the adapters for the Alpha Vantage, OpenFIGI and calendar files, the F8B policy, the conventions) are R8's; the run needs a small launcher with that configuration, which the main session or R6 writes (no real file was copied or written; the only read of `data/marketdata` is the table check). (d) The invented release in the PG tests is the `mock` flavour; the REAL control of O5 with valid sidecars cannot pass the run until R8 (invented sources are synthetic). (e) Scratch under `/tmp/claude-503` (`r4a_*`, `runmods.sh`, `full_*.txt`, `*.new`, `try_q.py`, `mut.sh`, `pg_try.log`, `full_default_r4b.txt`, `full_pg_r4b.txt`) remains, because `rm` is denied.

## F1 R4b fix round (2026-10-31)

Scope: the two MEDIUM findings of the R4b independent review (`reviews/TECH_REVIEW.md`, "F1 R4b build"). No gateway SQL changed. TR4B-L1 (O5 enforced only in Python, so hand SQL as the publisher role can bypass it) is left alone: it is with the owner (PD-0074).

**Result.** Default suite (`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`): `Ran 3720 tests in 176.567s` / `OK (skipped=785)`. PostgreSQL suite (`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`, same command, run after the default one): `Ran 3720 tests in 394.895s` / `OK (skipped=113)`. Before the round: 3707 tests (+7 sidecar, +6 qualification). The development cluster was already running and was left running. No `finweb_it%` database remains (catalog count 0 over the socket); no background process.

**TR4B-M1: a test-scope proposal stored an invented sidecar's digest.** The R4b writer and verifier refused only the REAL null slot, so a TEST_SWITCH or SYNTHETIC_TEST proposal whose slot was `sidecar_digest(<invented bytes>)` verified and `RealPublisher.publish` returned PUBLISHED. That stores an invented human attestation in a snapshot, which design 4.2 L-4 forbids in any scope. Fixed in three places, none in SQL:
- `real_proposal._member_dict` (used by the writer and, through `_build_snapshot`, by the verifier): in a scope whose origin axis is not REAL a non-null `acquisition_record_sha256` is `ProposalError("RW_O5_SLOT_IN_TEST_SCOPE")`.
- `real_sidecar.require_null_slots_in_test_scope(scope, members)` (new, constant `O5_SLOT_IN_TEST_SCOPE`): a no-op in REAL; in a test scope it raises `SidecarError` listing every member that holds a slot.
- `RealPublisher.publish` calls it after `verify_proposal` and before `require_o5`, so the refusal does not depend on the verifier alone; the existing `except` maps it to a refusal with "nothing was recorded", before any statement.

Tests (`TestScopeStoresNoSidecarDigestTests`, 7): the writer refuses a slot on the first and on the last member in both test scopes; the verifier refuses valid bytes edited to carry a slot with `context_id` recomputed, in both scopes (control: the unedited bytes verify); the publisher refuses the same edited bytes in both scopes, sends no statement, and `rw_publish` is not called; the publisher's own check, shown independent of the verifier by stubbing `verify_proposal` to accept; the unit check (REAL no-op, test scopes list exactly the filled members, an all-null list passes, dict members accepted); controls (a REAL proposal still verifies with all slots filled, a test proposal still carries nulls).

**TR4B-M2: `identity_digest` depended on insertion order.** It digested `resolver.identifier_rows()` in registration order though its docstring said "ordered by id"; two registries holding the same rows, registered in another `vendor_ids` order, gave different digests, which breaks P12 and P9. Fixed in `src/real_tools/qualification.py`: each of the four row lists (issuers, instruments, listings, identifiers) is sorted by a TOTAL key, the canonical JSON text of the row (every field takes part, `null` for an absent one), so the digest is a function of the SET of rows. The key is stated in the docstring. The value the digest takes on the kit's identity is unchanged (that registry's rows were already in that order).

Tests: the self-comparing assertion (`identity_digest(ident) == identity_digest(x.identity())`) is replaced by an expected digest written from the 3 issuers, 3 instruments, 3 listings and 7 identifier rows as plain data (the previously unused hand-built listings list became the full hand-written structure), compared with the function and with the digest the qualification run put in the proposal. New `DigestOrderIndependenceTests` (6): the reviewer's case (two registries, the same ids registered in the other order; control that their row order really differs and the row sets are equal); four permutations of the rows (reversed, two rotations, a hash-ordered shuffle) through a stub that hands the rows out in that order (control: the permutation really moved them); sensitivity (an added row, and a different value of an added row, each change the digest, also under permutation); calendar digest from a `CalendarSet` built in four other orders (and sensitive to dropping a calendar); profile digest for permuted and repeated source ids (and sensitive to dropping one); convention digest built twice, equal to its hand-written structure.

The other digests, checked for the same defect: `calendar_digest` (`CalendarSet.calendars()` is sorted by id), `convention_digest` (the id lists come from the convention sets in a defined order; the release's pairs are validated sorted), `profile_digest` (`sorted(set(...))`, markets sorted), `release_digest` (files validated sorted; `source_precedence` is order-significant by design), the F8B policy digest (sorted), `projection_digest` (a defined projection order) are not insertion-ordered; only `identity_digest` was.

**Mutants** (targeted modules, baseline 183 OK; every mutant killed, failing tests in brackets). M1: `_member_dict` check removed [6 failures]; the same check applied to REAL as well [6 errors]; the publisher's `require_null_slots_in_test_scope` call removed [1 error, the stub test; the verifier alone catches the real bytes, which is why the stub test exists]; the REAL no-op removed from `require_null_slots_in_test_scope` [3 failures, 1 error]. M2: sort removed from the identity digest [2 failures]; sort by listing id only (the partial key; the reviewer's case keeps insertion order inside one listing) [2 failures]. All restored; the targeted modules are back to 183 OK.

**Decisions the contracts did not cover.**
1. New refusal code `RW_O5_SLOT_IN_TEST_SCOPE`. It is distinct from `RW_O5_LEGACY_NULL` (the REAL null) and says the opposite thing: a test scope must hold null.
2. The canonical order of `identity_digest` is the canonical-JSON text of each row. The digest value for the kit's registry did not change, but the key is now a stated part of the method of this digest; R5's world builder must recompute with the same key (a set, sorted by that text).
3. The publisher's check is redundant with the verifier's by design (defence in depth, tested independently).
4. The earlier "Decisions" item 3 of the R4b section named `RW_O5_SIDECAR_IN_TEST_SCOPE` and said a test scope "takes no sidecar at all". The R4b code refused only the REAL null; this round makes the stored-slot half true, under the code named above. The `sidecars` argument of `publish` is still ignored in a test scope (O5 is bypassed), as before.

**Open items.** TR4B-L1 stays with the owner (PD-0074). The R4b open items (a) to (e) stand. Scratch under `/tmp/claude-503` (`mut.sh`, the review probes, the suite logs) remains because `rm` is denied.

## F1 R5 (2026-10-31)

Scope: the R5 row of design 7.1 (line 2772). Real consumption: the scoped contract (2.4, not installed anywhere), `read_release(..., lease_checked=True)`, the shared create tail and the shared read tail (E23), the real create up to the service's refusal, the `SYNTHETIC_TEST` create (the fictional branch), the world builder, the claim limits (7.4), tests T-a to T-g and T-m. **No gateway SQL changed** (a test pins the SHA-256 of `real_fence_v1.sql`, `real_workspace_v1.sql`, `real_provenance_v1.sql` and `real_workspace_fictional_v1.sql`). Nothing is committed. No stop-and-report item arose from the gateway; the placement and audit findings below were resolved inside the engineer's paths and are listed for the reviewer.

**Result.** Default suite (`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`): `Ran 3832 tests in 183.095s` / `OK (skipped=833)`. PostgreSQL suite (`FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`, same command, run after the default one): `Ran 3832 tests in 417.267s` / `OK (skipped=113)`. Before R5: 3720 tests (default `OK (skipped=785)`, PG `OK (skipped=113)`); R5 adds 112 tests, of which 48 are PG tests that skip in the default run. Both suites were run on the final tree, after the last source change and after the mutation checks; earlier pairs on slightly earlier trees also passed (`Ran 3831 tests` / `OK (skipped=833)` and `OK (skipped=113)`, before the seal sentence below was added). The development cluster was left running. Leftover check, read-only as `finweb_dev`: 0 `finweb_it%` databases, 0 `finweb_it%` or `rw_%` roles.

**What was built.**
- `src/web_api/real_scoped_contract.py` (pure leaf; installed nowhere; imports only `marketdata.claim_render` and `persistence.real_labels`, both pure): schemas, `ROUTES` (create, owner-scoped list, read, reproduce; no export), the `ERRORS` vocabulary, `parse_intent` (no `mode` field), and the committed, read, reproduce, list, refusal and unknown payloads.
- `src/persistence/market_data_store.py`: `read_release(conn, release_id, exchange_of=None, *, registry, lease_checked=False)`. With `lease_checked=True` every read goes through the table's `rw_<table>(release_id)` function (one helper, `_lease_function`, writes the name rule); the WHERE and ORDER BY are the same; the file-list check, the projection recompute and the registry checks are unchanged (FR-L1 (a)). No SQL added.
- `src/persistence/real_tails.py`: `CreateTail`, `ReadTail`, `fire_by_name` (inventory check against `real_catalog_audit.EXPECTED_DEFERRABLE`, then `SET CONSTRAINTS <schema>.<name> IMMEDIATE` for each name but the deadline guard; `SET CONSTRAINTS ALL` appears nowhere), `reconcile` (a new connection, an `ARCHIVE_READ` admission at the current generation, `rw_precheck` then `rw_archive`; it returns COMMITTED or UNKNOWN and nothing else), and the results `Done`, `Refused`, `Unknown`, `Reconciled`. The COMMIT-time classification is `OneTransaction._classify` (design 3.1, E4), unchanged.
- `src/real_service/service.py` (`RealWorkspaceService`: create, reconcile, archive read, reproduce, list) and `src/real_service/worlds.py` (the world builders and the verifier). The service holds no COMMIT, no SET CONSTRAINTS and no classification; a static audit checks that.
- `src/marketdata/claim_render.py` (pure render of the claim limits over the Quant's `claim_limits.py`, which is unchanged), `src/persistence/real_digests.py` (see decision 1), `src/persistence/real_labels.py` (`ORIGIN_FIELDS`, `FLAG_FIELD`).
- Tests: `test_real_r5_pure.py` (64, no database), `test_postgres_real_r5_tails.py` (36), `test_postgres_real_r5_real.py` (9), `test_postgres_real_r5_smoke.py` (3; the file name is a leftover, the content is the contract-wiring tests, see open item 6), base case `real_r5_case.py`.

**Labels.** Every PG test carries one of "product path, shared tail on SYNTHETIC_TEST", "E11 crafted probe, not product evidence", "first run at R8" or "product path, real branch to the service's refusal"; a static test checks every PG test of the two files has one. No test claims an acknowledgement-loss re-proof for the real branch (PD-0068 answer 2); a static test checks the real-branch file has no `_after_commit` and no `reconcile`.
- Tails on the `SYNTHETIC_TEST` create (product path): accepted create, replay, idempotency conflict, T-a (statement recorder: `SET CONSTRAINTS <schema>.<name>` per name, none `ALL`, the deadline guard never named, inventory refusal for an unknown or missing deferrable constraint), T-b, T-c, T-d, T-e, T-f, T-g (the stalled create, read, reproduce and list entry refused at COMMIT with no value delivered; a killed connection is UNKNOWN; reconciliation makes its own committed state), concurrency and restart, FF1-C05 world binding (each changed digest refused with `RW_WORLD_DIFFERS` naming the field before any INSERT; nothing left), the migration-trigger test below.
- Real branch on a `TEST_SWITCH` chain (invented data, `QualifiedChainCase`): FF1-C08 (the actual service refuses, whole rollback, nothing addressable, no seal, no firing, no COMMIT), FF1-C05 inputs, reads of a missing real root find nothing, T-m, and two E11 crafted FR-L1 probes (projection recompute, file-list check).
- T-m: digest parity with a direct read by the owner; no `FROM md_*` table statement on the executor's connection (the matcher strips the schema qualifier and the quotes, so it is not vacuous: the owner with the default keyword shows `md_*` reads, and the executor's default-keyword read gives `InsufficientPrivilege` 42501); the read after `complete_by` is refused by the function (`Refused`, `RW_MD_READ_REFUSED`, detail `DEADLINE`).
- Accepted side of the real branch (seal, commit, archive, reproduce, list of a real root): **first run at R8**, not exercised here.

**Claim limits (7.4).** `render_claim_block(origin, lineage)` fills S1 to S5 from named lineage fields (`SLOT_FIELDS`) and states C1 to C7 as the may-not items. A lineage with a missing, empty or non-text field is refused (`ClaimRenderError`), not rendered with a hole. A non-`REAL_SOURCE` stored origin renders the invented-data mark in every slot and no item, and the lineage is not read. S4, next to the ledger version it names, carries `SEAL_LIMIT` (PD-0073 binding obligation). Its first version disclaimed the account's identity and the context; TR5-L2 showed those were the wrong subjects, and the Fix round below gives the current sentence. The block never says the seal verifies identity, context or manifest origin; a pure test checks the required phrases and that every sentence about the seal and those subjects is a negation (mutants C6a to C6c). I found this sentence missing on a late re-read of the obligation and added it then; the first full-suite runs were before it. `check_block` requires each item's required terms (P3) and covers the Quant's list item by item. Fixtures: an in-memory `REAL_SOURCE` lineage with placeholder slot values, never stored or served, and a `SYNTHETIC_TEST` origin.
Mapping of the design numbering to the Quant's items (`S_ITEMS`, `C_ITEMS`): S1 C-1; S2 C-1 (its last sentences, the label source); S3 C-2, C-3, C-4; S4 C-5; S5 C-6; C1 N-1, N-2, N-3; C2 N-4; C3 N-5; C4 N-6; C5 N-7; C6 N-8; C7 N-9.

**Ruling 6.5 items 5 and 6, market-data/1.15 against 1.16.** `claim_limits.py` already encodes 1.16, and the render follows it: the label source is read from the lineage field `adjustment_label_source` (DECLARED for a result that cites 1.16; a stored result that cites 1.15 or earlier says MEMORY and the render does not hard-code the word); N-2 (the dividend component is unverifiable) is its own item inside C1; N-8 (the quantity is not verified and is not the owner's holding) is C6. A pure test mutates the lineage's label source and checks the S2 text follows it. I did not compare against a separate 1.15 text of the design; where the design's section 7.4 and the Quant's file differ in numbering I used the mapping above and did not change the Quant's items.

**Mutation checks** (all restored; baseline for the first block is the 111 R5 tests, which passed in 32 s before the seal sentence and are 112 after; fail counts are failures plus errors of that run).

| id | mutation | fail count |
|---|---|---|
| T1 | the tail issues `SET CONSTRAINTS ALL IMMEDIATE` instead of naming each | 6 (5 failures, 1 error) |
| T2 | the tail also fires the deadline guard (the `continue` removed) | 5 (4 failures, 1 error) |
| T3 | the create tail never calls `fire_by_name` | 4 (2 failures, 2 errors) |
| T4 | the read tail also fires the constraints | 2 |
| T5 | `reconcile` reports `ROLLED_BACK` for an absent operation | 4 |
| T6 | `reconcile` reports a refused reconciliation as `REFUSED` instead of UNKNOWN | 3 |
| T7 | `_finish` returns a value (`Done`) for an UNKNOWN commit | 18 (5 failures, 13 errors) |
| T8 | `_classify`: a non-gateway error at or after the commit point becomes a refusal | 10 (3 failures, 7 errors) |
| R1 | the statement recorder records nothing | 5 (4 failures, 1 error) |
| R2 | the table matcher keeps the schema name instead of the table name | 4 |
| R3 | `_select` ignores `lease_checked` and reads the table | 10 |
| C1 | drop N-2 from claim item C1 | 3 (run on the pure and wiring modules, 63 tests) |
| C2 | the S3 text drops C-4 | 3 (pure module) |
| C3 | a non-`REAL_SOURCE` origin renders the real block | 2 (1 failure, 1 error; pure module) |
| C4 | hard-code `DECLARED` in S2 | 2 (pure module) |
| C5 | `missing_items` always returns the empty set | 18 (pure module) |
| C6a | the S4 seal sentence replaced by "The seal that stores the result verifies the ledger." | 1 (pure module) |
| C6b | the S4 seal sentence kept but followed by "The seal verifies the identity of the account and the context." | 1 (pure module) |

T8 mutates `real_workspace_context.py` (R1 code) and was restored; `git diff` shows that file unchanged. C1 to C5 were run before the three tests added in the placement round below, so their module had 60 tests; each was restored and the module is green again.

**Exit statement: executor-fired migration triggers of the `SYNTHETIC_TEST` create, with PUBLIC's `EXECUTE` revoked** (1.2 rule 5.3 (e); technical TR6-L2). The create runs as the executor role on an install that has the installer's schema-wide revoke of PUBLIC `EXECUTE` in place; a test asserts that PUBLIC holds no `EXECUTE` on the trigger functions and that the create then commits. The create writes `ledger_event` rows (the two opening events, through `ledger_store.append_batch`) and fires:
- `ledger_event_before_insert` (BEFORE INSERT, not deferrable): fired by each insert.
- `ledger_event_transfer_pairing` (AFTER INSERT, deferrable constraint trigger): fired by name by the tail's `fire_by_name` before the COMMIT.
- `benchmark_selection_before_insert` is **not** fired: the create writes no `benchmark_selection` row.
- `rw_lease_deadline_guard` is deferrable and is deliberately left pending; the COMMIT fires it.
So these are the first firings of migration triggers by the executor with PUBLIC's `EXECUTE` revoked, and they work. The evidence is the committed create in the test, not a reading of the manual: PostgreSQL documents the `EXECUTE` check on a trigger function at `CREATE TRIGGER` time, and I did not rely on that. The same statement for the real branch is not made: its accepted side is first run at R8.

**Decisions the contracts did not cover.**
1. **The six digest functions moved out of `real_tools`.** R4b put `identity_digest`, `calendar_digest`, `convention_digest`, `profile_digest`, `release_digest` and `projection_digest` in `real_tools.qualification`, and the standing rule (`test_real_qualification`, the `real_tools` docstring) is that product code never imports `real_tools`. The world builder must recompute exactly those digests (binding obligation: R4b's functions, nothing re-implemented). I moved the bodies unchanged to `persistence/real_digests.py`; `qualification.py` imports the names from there, a test asserts they are the same objects, and the R4b tests pass unchanged. This edits committed R4b code (only the move). If the Quant or the reviewer would rather have the digests defined elsewhere, only the import line of `real_worlds` and `qualification.py` changes.
2. **The service layer lives in `src/real_service/`, not in `persistence`.** `test_performance_boundaries` says nothing in `persistence` imports the performance engine; the service and the fictional world builder call it. Placed above `persistence` (and below `web_api`). I first wrote them under `persistence`; those two paths remain as docstring-only stubs (`src/persistence/real_worlds.py`, `src/persistence/real_workspace_service.py`) because the engineer cannot delete files. **The main session should delete both.** Nothing imports them.
3. **Source-audit pins changed, for the reviewer's attention.** (a) `test_real_labels.S2_REFERENCING` gains `real_tails.py`, `real_service/service.py`, `real_scoped_contract.py`; `FACT_11` gains `real_service/worlds.py`. (b) The wording audit finds `synthetic` or `invented` in a file that names an S2 object. The new readers now take the column names from `real_labels.ORIGIN_FIELDS` and the flag name from `real_labels.FLAG_FIELD`, take the service's refusal code through `worlds.REFUSAL_CODE`, and say "made-up test data" in prose. `IDENTIFIER` was first widened by a pattern (names with `synthetic` or `invented` and an underscore); the review (TR5-L1) showed that blinded the audit to hard-coded origin values, and the Fix round below replaces the pattern with an explicit one-name allowlist. (c) `market_data_store.py` is not in the S2 pin because it spells no S2 object (one helper derives `rw_<table>`), so the audit does not see this new reader; the recorder tests and the `read_release` call-site audit cover it instead. A reviewer may prefer it listed by name. (d) `test_real_scope` lists the scope-lookup callers: `_stage_create` and the reproduce `body` are added, each reading the scope from the locked snapshot's field.
4. **No `mode` field in the create request**; the origin is a property of the context's locked snapshot, read through `real_scope.scope_by_snapshot_field`.
5. **The invented fictional world is data in `worlds.py`** (source id `r5.inline.invented.quotes`, day 2026-01-05, deterministic ids 200 to 209). The fictional integration's own `context_id` differs from the S2 snapshot's `context_id`; the envelope carries the S2 one and the question carries the integration's.
6. **`RW_RELEASE_REFUSED`** is a new public code for a `read_release` integrity failure (`MarketDataStoreError`, `LookupError`, `PermissionError`, `ValueError`), raised with whole rollback; a `psycopg` error (including the function's own deadline refusal) is not caught there and reaches the tail's classifier.
7. **`SET LOCAL search_path TO <schema>, pg_temp`** is issued by the tails at the start of each transaction: the executor's search path is not the schema, and the services this path calls write unqualified table names.
8. **Replay.** An `EXECUTE_CREATE` of an operation that is already sealed is made read-only (phase REPLAY) by the gateway; the service finds it with a post-admit `rw_precheck`, reads the archive, calls no service and writes nothing.
9. **Executor-side input shapes**: `WorldInputs(resolver, market_conventions, perf_conventions, policy)` and `ProvenanceLink(context_sha256, members, witnesses)`, because the executor holds no identity grant and the link comes from the registered candidate. R7 and R8 must supply them.
10. **Lineage field names** (`SLOT_FIELDS`) are the render's input contract; R7 and R8 must map the real lineage to them.
11. **The gateway SQL pin test** (`test_no_gateway_sql_was_added_after_R3`): a later reviewed SQL change must update the four digests on purpose.

**Open items.**
1. The accepted side of the real branch (seal, commit, archive, reproduce, list of a real root) and the NAV oracle `10 x p + 500` are first run at R8. Nothing in R5 shows an accepted real number.
2. The scoped contract needs the independent review that the R5 exit names, before R7 installs it.
3. The residual of 4.4 (8.1 item 11) stands, as stated in the exit of the design: no end-to-end acknowledgement-loss re-proof for the real branch.
4. Decisions 1 to 3 touch committed R4b code, a standing boundary test and three source-audit pins; the technical reviewer should look at them as items of this increment.
5. ~~The two docstring-only stubs in `src/persistence/` (decision 2) should be deleted by the main session.~~ Done: the main session deleted `src/persistence/real_worlds.py` and `src/persistence/real_workspace_service.py`; neither exists in the tree.
6. `tests/product/test_postgres_real_r5_smoke.py` has a leftover name from a first plan; its content is the contract-wiring tests. The main session may rename it to `test_postgres_real_r5_contract.py` (I could not delete or move a file).
7. Scratch under `/tmp/claude-503` (`pg5.sh`, `def5.sh`, `mut.sh`, `closure.py`) remains because `rm` is denied.

### Fix round (2026-10-31): the six findings of the R5 independent review

Scope: `reviews/TECH_REVIEW.md`, "F1 R5 build — independent technical review", PASS_WITH_FINDINGS (2 MEDIUM, 4 LOW), plus the optional layering note. No gateway SQL changed (the pin test still holds). Nothing committed.

**Result.** Default suite: `Ran 3843 tests in 167.810s` / `OK (skipped=834)`. PostgreSQL suite (same prefix as above, run after the default one): `Ran 3843 tests in 431.316s` / `OK (skipped=113)`. Before the round: 3832 (`OK (skipped=833)` / `OK (skipped=113)`); the round adds 11 tests, one of them PG-only. Targeted before the full runs: the four R5 modules `Ran 122 tests in 32.099s` / `OK`; `test_real_labels`, `test_real_scope`, `test_real_qualification`, `test_performance_boundaries` `Ran 103 tests in 5.589s` / `OK`. The development cluster was left running; leftover check as `finweb_dev`: 0 `finweb_it%` databases, 0 `finweb_it%` or `rw_%` roles, 4 databases in all.

**TR5-M1 (contract did not tie labels and block to the origin).** `real_scoped_contract`: `label_object(labels, origin)` now requires the labels to equal `real_labels.root_labels(origin)` (a contradictory origin is refused too); `_claim_block(block, origin)` requires `claim_render.check_block(block, origin) == []` (a malformed item is a refusal, not a crash); `digest_field` requires 64 lowercase hex for `response_sha256` and `issued_sha256` (the reproduce digest may be `None`, as for a source refusal). `read_payload` also checks `result` and `ledger_pin` types as `committed_payload` does. Tests (`ContractBindsLabelsAndBlockToOriginTests`, 6): controls (matching origin, labels and block accepted for both origins); the reviewer's four probes, each now `REAL_UNAVAILABLE`: a test origin with the real labels and the real block (also each half alone, and through `reproduce_payload`), a real origin with the invented-data block (and with the test labels), a real block missing C1 (generalised: every one of the 12 S-slots and C-items removed in turn, and a required term removed), `response_sha256="x"` (generalised: empty, uppercase, 63 and 65 characters, `None`, an int, for both digests and both payloads); an origin whose fields contradict each other. The REAL_SOURCE origin and lineage are in-memory fixtures, never stored. Existing contract tests that used placeholder labels and an empty block now use the derived labels and a rendered block. Mutants (failures counted with subtests): label comparison removed 6; `check_block` call removed 18; digest check removed 16. All restored.

**TR5-M2 (reproduce dropped the stored origin).** `Reproduction` now has `origin` (the `archive.origin` of the archive read in the reproduce's own transaction and admission) and a `labels` property; all five construction sites pass it, including the refusal and the result-differs outcomes. The wiring test no longer takes origin or labels from the create: it builds `reproduce_payload` from `again.value.origin` and `again.value.labels`, and asserts the payload's origin equals it. Mutant: the fictional reproduce drops the origin: 1 failure (the wiring test). The real-branch reproduce has the same construction but no committed real root exists before R8, so its origin is first checked at R8.

**TR5-L1 (widened `IDENTIFIER`).** Reverted to HEAD's pattern (`fictional`/`sandbox` names). The R5 files needed one more exemption, so there is now an explicit tuple `ALLOWED_NAMES = ("SYNTHETIC_MARKET_DATA_REFUSED",)` and a helper `without_identifiers`. The other hits were prose, which I reworded (`real_tails.py`, the contract). A new test checks the allowlist is exactly that tuple, that the origin enum values and `contains_synthetic` are NOT exempt, and that the reviewer's mutant text appended to `real_roles.py` is found. The mutant itself, applied to the real file (a line `... "SYNTHETIC_TEST" ... "INVENTED_TEST_LEDGER"` in `real_roles.py`): 2 failures (the S2 wording audit on `real_roles.py`, and the new test), and it flags no R5 file. Restored; `git diff` of `real_roles.py` is empty.

**TR5-L2 (seal sentence, wrong subjects).** `SEAL_LIMIT` now reads: "The seal that stores the result checks the ledger by its pin (the ledger version), not by its content; the staging and the reproduce of the result are what catch a different ledger. The seal does not verify the instrument identity facts the computation used (trading currency, exchange and security type), and it does not verify the origin recorded in the engine's manifest." The account-identity and "context the result ran under" phrases are gone (for real-source output `rw_check_real` does bind the result to its context's snapshot; the fictional context's unverified `context_id`, disposition 5.5, is a test-only limit that never renders here, and the comment in the source says so). The test requires the exact phrases and forbids the old ones. Mutants: C6a ("verifies the ledger") 1 failure; C6b ("The seal verifies the instrument identity facts...") 1; C6c (the old context phrase restored) 1. Restored.

**TR5-L3 (two guards had no killing test; wrong comment).** `DefenceInDepthGuardTests` (2, E11 crafted probes, labelled so): the create is run with `store.admit` stubbed to admit a test-scope context on an install that reports kind REAL, and must refuse `RW_INSTALL_KIND` before the link (control: kind TEST gets past the guard and stops at the release binding); `verify_world` is run with every digest matching and only the port's `contains_synthetic` flipped, and must refuse `RW_WORLD_DIFFERS` naming `contains_synthetic` (control: the unflipped world passes). Mutants: `check_install_kind` removed from `_stage_create` 1 failure; the I2 row removed from `verify_world` 1 failure. The `test_real_scope` comment is corrected: only the CREATE runs `check_install_kind`; the reproduce does not and relies on the SQL admission's install-kind guard. I did not add the check to reproduce: design 4.2 names the Python check a second barrier where the executor writes, and reproduce writes no economic row. If the reviewer reads the design as requiring it on reproduce, it is one line.

**TR5-L4 (two tests claimed more than they showed).** (1) The post-commit test is renamed `test_T_c_an_error_with_no_gateway_code_in_the_post_commit_check_...` with a docstring saying it shows the post-commit path only, and it now asserts the bundle IS durable. A new test injects a real error AT the COMMIT: the owner role, in the disposable database, replaces the body of the deferred deadline guard's trigger function (`rw_deadline_check`) with one that raises a CHECK violation with no `RW_` code, restored in `finally` and compared with the saved definition; the create is run through the product path. Result: `Unknown`, the connection back at IDLE, exactly one admission (no retry), the firing step reached, nothing left (the server rolled the transaction back, so UNKNOWN is the conservative answer, as the E4 rule says), and reconciliation reports UNKNOWN/ABSENT. It is labelled "E11 crafted probe" because the guard body is crafted. Mutant: `_classify` treats a non-gateway error at or after the commit point as a refusal: 3 failures, including both T-c tests. (2) The hand-written set is replaced by `RefusalVocabularyTests` (pure): `reachable_refusal_codes()` derives the set from the whole-string `RW_`, `REAL_`, `LOCAL_` and refusal-code constants in the service, tails, scope, provenance, store, context and integration modules, plus every `RAISE EXCEPTION 'RW_...'` of the four gateway SQL files, plus `worlds.REFUSAL_CODE`. The test has a non-vacuity floor (it names `LOCAL_SERVICE_RESULT_REFUSED`, `RW_UNKNOWN_DEFERRABLE`, `RW_DEFERRABLE_INVENTORY_DIFFERS`, `RW_LINK_MISSING`, `RW_SHAPE` as reachable and not public, and `RW_NOT_FOUND`, `RW_DEADLINE`, `RW_MD_READ_REFUSED` and others as public), states the mapping (a code in `ERRORS` keeps its status and kind; every other reachable code is the 503 `REAL_UNAVAILABLE`, kind CONFIGURATION, and is not reflected; fails closed, not a typed 409), and checks no `ERRORS` entry is dead. The PG wiring test of the same name is replaced by one that takes two codes the service returned in that run (`RW_LINK_MISSING`, `RW_NOT_FOUND`) through the payload.

**Optional layering note.** The smaller fix was the docstring: `real_service` really does import the pure contract leaf (the intent validator, the label field names, the list entry), so moving the dependency would have meant duplicating or relocating the validator. `src/real_service/__init__.py` now says it imports exactly that one `web_api` module, and no route, app or launcher.

**Decisions.** (a) Labels are verified against `root_labels(origin)` rather than derived inside the contract, so a caller that passes wrong labels is refused and not silently corrected (design 2.4: no repair). (b) The reproduce digest may be `None` (a source refusal has none). (c) The allowlist is a reviewed tuple in `test_real_labels.py`; adding a name is a reviewed change.

**Open items after the round.** The R5 open items above stand except item 5 (done by the main session). Lineage extraction (stored real result to `SLOT_FIELDS`) is still unbuilt and now has the contract guard in front of it. The reviewer's other observations (the real-branch `listing_ok`, the 64-root list bound, an untyped `ScopeError` in the reproduce body, the 1.15-versus-1.16 comparison) are unchanged.

## Cloud vendor-file flag (2026-11-01)

**Why.** A clean clone (commit `26d82ec`) has no `data/marketdata/files/` (gitignored; PD-0027/PD-0028, internal use only), so tests that read the human-downloaded payloads error there. The owner decided the payloads never go to the cloud; a cloud run states that with `FINWEB_NO_VENDOR_FILES=1` and skips exactly those tests.

**What.** `tests/product/vendor_files.py` holds the one switch: `needs_vendor_files = unittest.skipIf(<flag is exactly "1">, "vendor payloads absent by design (FINWEB_NO_VENDOR_FILES=1; PD-0027/PD-0028)")`. With the flag unset nothing changes: a missing payload is still an error. There is no skip-if-missing logic, and a test pins that the helper does not touch the file system. 16 tests carry the decorator, 15 from the first round and one added later (per method, no module or class skips):
- `test_marketdata_r4a_inputs`: `A6AndRuling73Tests` test_2 to test_11 (10 tests; test_1 reads no payload and still runs), `DeliveredDecimalsTests.test_5_the_stored_aapl_file_passes_every_price_text_shows_exactly_four_decimals`, `FixingDateStatedTwiceTests.test_7e_the_two_stored_frankfurter_files_state_no_date_twice_so_nothing_on_disk_is_excluded`;
- `test_performance_evidence_pack`: `RealSliceTests` `test_only_terms_attested_files_are_admitted_and_the_drafts_are_never_read`, `test_the_real_slice_builds_from_the_admitted_files_and_is_labelled_real_and_states_what_is_missing`, `test_an_unattested_source_is_refused_before_its_payload_is_used`;
- `test_real_qualification` (added on the coordinator's instruction): `ConfirmationTableTests.test_the_table_equals_the_real_files` (renamed from `..._when_they_are_on_disk`; its own `skipTest` on missing files is removed, so it now errors if a file is missing and the flag is unset).

That makes 16 gated tests. The gated set is pinned by `tests/product/test_vendor_files_flag.py` (a static scan of every test file for the decorator, compared to `EXPECTED_GATED`; a decorated class or module-level function can never match). Adding a test to the gate is a reviewed change to that list.

**How the set was found.** A clean copy of the tree (tracked and untracked-unignored files only, so no `data/marketdata/files/`) was made under `$TMPDIR` and the two modules were run there before any change: 114 tests, 2 failures and 16 errors = 18 records. They are 15 tests, because `A6AndRuling73Tests.test_8` is a subTest loop that reports 4 error records. The real `data/marketdata/files/` was not read, moved or written for this.

**Other skip-if-missing logic (audit of `tests/product/`).** Searched `skipTest`/`skipIf`/`skipUnless`/`SkipTest`, `exists()`/`is_file()`/`is_dir()`, `FileNotFoundError`, and every use of `data/marketdata`. The only one that read vendor payloads was `test_real_qualification.py` (`is_file()` then `skipTest`), now on the flag. The rest do not read payloads:
- every other `skipIf`/`skipUnless`/`skipTest` is for PostgreSQL provisioning (`pk.skip_reason()`, `FINWEB_PG_*`, F2/F3 CONFIG, MAINTAIN on PG 17), psycopg, or the sandbox's refusal to bind a Unix socket (`test_guarded_dev_startup.py:232`);
- `test_marketdata_tools.py:81` and `test_marketdata_tools_probe.py:55` test a temp dir the test itself wrote;
- `test_performance_cp4_part_a2.py` `CalendarCheckTests` scans `data/marketdata/**/*.json` for calendar documents. It needs only the four tracked drafts (it passes in the clean copy), and the manual calendar files are not vendor payloads, so it is not gated;
- `test_performance_real_fx.py` and `test_marketdata_cp2c2_exit.py` read only the tracked `SOURCES.json`.

**Results.** Counts are by test, so the "18" error records are 15 tests, plus the one above = 16 skips.
- Default, flag unset, real tree: Ran 3848 (3843 + 5 new), OK (skipped=834).
- PostgreSQL, flag unset, real tree: Ran 3848, OK (skipped=113).
- Flag set, real tree: Ran 3848, OK (skipped=850 = 834 + 16).
- Clean copy, flag set, full default suite: Ran 3848, OK (skipped=850), matching the real tree.
- Clean copy, flag unset, the three modules and the pin: Ran 164, FAILED (failures=2, errors=17), which is the earlier 18 records plus the former skip now erroring, so the flag is the only thing that changes behaviour.

### Review fixes TVF-M1, TVF-L2, TVF-L3 (2026-11-01)

Review: `reviews/TECH_REVIEW.md`, "Cloud vendor-file flag — independent review", PASS_WITH_FINDINGS. All changes are in `tests/product/`.

**TVF-M1 (MEDIUM): the pin saw one spelling of the gate.** `test_vendor_files_flag.py` now holds the gate with four checks:
1. `gated_ids`, as before (the decorator on test methods, compared with `EXPECTED_GATED`).
2. `flag_problems`, static, on every file under `tests/product/` except `vendor_files.py` and the pin. It fails on:
   - the text `NO_VENDOR_FILES` anywhere;
   - any import of the helper module other than exactly `from vendor_files import needs_vendor_files` (no alias, no `import vendor_files`, no `from tests.product import vendor_files`, no other names, no dynamic import by string);
   - any reference to `needs_vendor_files` that is not a bare-name decorator on a `test*` method of a top-level class. That rules out aliasing, rebinding, assignment-applied decorators, a decorated class, a call form, a module-level function, a non-test method and a class nested in an `if`.
   I reworded three import comments and one docstring in the gated modules so that none of them spells the flag.
3. `payload_skip_problems` (TVF-L2, below).
4. A load-time comparison. In a subprocess (`sys.executable`, cwd at the repo root, every `FINWEB_*` variable removed, so no database is reached) the whole suite is LOADED, never run, once with the flag set and once without. The test ids carrying `__unittest_skip__` (method or class) must differ by exactly `EXPECTED_GATED`; nothing may be UNskipped by the flag; no test module may fail to load; and the two loads must hold the same number of tests (it also checks more than 1000 were loaded). Cost: about 3.5 s for the pin module in all.

The reviewer's bypass spellings are kept as source text in the pin (`BYPASSES`, `SKIP_ON_PAYLOAD`, `CLEAN`), and `CheckersRefuseTheBypassesTests` asserts that the static checks refuse each one and accept the plain forms.

**What remains uncaught, and why.** A runtime `SkipTest` raised from a body, `setUpClass` or `setUpModule` that learns the flag by a means that avoids both the text `NO_VENDOR_FILES` and the helper, for example `os.environ.get('FINWEB_NO_' + 'VENDOR' + '_FILES')`, or a scan of the whole environment. The load-time comparison cannot see such a skip, because it exists only at run time. Check 2 covers the natural spellings of a runtime skip (all of mutants 10 to 12 below, which the load-time check cannot see), and the obfuscated form is caught only by review. Mutant 17 below does exactly this and is NOT caught. A helper change in `vendor_files.py` is the one reviewed file the checks exempt; a load-time gate added there is caught by check 4, and a runtime one is not.

**Mutants.** I recreated the reviewer's spellings (their files were no longer in `$TMPDIR/tvf_mut`) in a fresh copy of the tree, `$TMPDIR/mut1`, as `tests/product/test_zz_mut.py`, and ran only `tests.product.test_vendor_files_flag` for each. "Skips" is whether the mutant skipped under the flag (run alone); in every row but the control it did, so each is a real bypass. The control is the same file with no gate.

| # | Mutant | Pin result | Caught by |
|---|---|---|---|
| 01 | control, no gate | OK | (none, as it should be) |
| 02 | `@needs_vendor_files` on a method | FAILED | 1, 4 |
| 03 | on a class | FAILED | 1, 2, 4 |
| 04 | on a mixin method | FAILED | 1, 4 |
| 05 | `import vendor_files as vfx`, `@vfx.needs_vendor_files` | FAILED | 1, 2, 4 |
| 06 | alias `nvf` | FAILED | 2, 4 |
| 07 | `gate = needs_vendor_files` | FAILED | 2, 4 |
| 08 | inline `skipIf` on the env var | FAILED | 2, 4 |
| 09 | inline `skipIf` on the helper | FAILED | 2, 4 |
| 10 | `SkipTest` in `setUpModule` | FAILED | 2 only (run-time skip) |
| 11 | `SkipTest` in `setUpClass` | FAILED | 2 only |
| 12 | `self.skipTest` in the body | FAILED | 2 only |
| 13 | `test_a = needs_vendor_files(test_a)` | FAILED | 2, 4 |
| 14 | `C = needs_vendor_files(C)` | FAILED | 2, 4 |
| 15 | decorated class nested in an `if` | FAILED | 2, 4 |
| 16 | `is_file()` then `skipTest` on a payload (TVF-L2) | FAILED | 3 |
| 17 | runtime `SkipTest` on an env name built from pieces | OK, NOT caught | (review only) |

So 15 of the 16 bypass spellings are caught and the control stays green. Mutant 17 is the one uncaught case described above.

**TVF-L2 (LOW): skip-if-missing on payloads.** `payload_skip_problems` fails when a top-level class or function (decorators included), or a module-level statement, uses `skipTest`/`SkipTest`/`skipIf`/`skipUnless`/`skip` and also refers to the real data root: the string `marketdata` or `data/marketdata`, `DEFAULT_ROOT`/`REAL_ROOT`, or a module-level name whose value is built from the root (`DATA`, `UW_PATH`). It runs over all of `tests/product/` and gives no finding on today's tree. Its limit is scope: a skip in one class cannot see a path constant that is built in another module.

**TVF-L3 (LOW): `CalendarCheckTests` is not gated.** It scans `data/marketdata/**` (the `files/` folder included) for calendar documents, but its assertions need only the four tracked drafts (at least four documents; the NYSE, ECB, HKEX and CN-A draft names). It therefore passes without the payloads and without the registered calendar files. A cloud run checks a narrower set for that test than the owner's Mac does, and the Mac does not error if the registered calendar files under `files/calendar.manual/` are moved. The manual calendar files are not vendor payloads. The same note is in the docstring of `tests/product/vendor_files.py`.

**Runs for this round** (targeted only; no full suite was run):
- `tests.product.test_vendor_files_flag`, `test_marketdata_r4a_inputs`, `test_performance_evidence_pack`, `test_real_qualification`, flag unset, real tree: `Ran 170 tests in 7.268s` / `OK`.
- The same four modules, `FINWEB_NO_VENDOR_FILES=1`, real tree: `Ran 170 tests in 7.076s` / `OK (skipped=16)`.
- The same four modules in a fresh clean copy (`$TMPDIR/clone4`, no `data/marketdata/files/`), flag set: `Ran 170 tests in 7.738s` / `OK (skipped=16)`. Flag unset: `Ran 170 tests in 7.681s` / `FAILED (failures=2, errors=17)`, the same 19 records as before (the payload tests error when the flag is unset).

## F1 R6 (2026-11-01)

This is the Engineer's own check, not a review. The R6 review is the independent reviewer's; the gate is a separate item in it (design 7.1).

**Built.** The preflight (`src/persistence/real_preflight.py`), the REAL installer (`src/persistence/real_install.py`), the gate in the publisher tool (`real_workspace_store.main`), the guard-function comparison in the catalog audit (`real_catalog_audit`, FR-L1 (b)), the rule-6 tripwires (`connection.py`, `guarded_pg_provision.py`), the identity seed (`src/real_tools/identity_seed.py`), the install plan (`implementation/CP7_F1_R6_INSTALL_PLAN.md`). No gateway SQL changed (nothing in `src/persistence/*.sql` or `migrations/`).

**Tests.** `test_real_preflight` (92: decision table, by-command rule, every listed case on fake facts, classifier, Pass S under temporary `HOME`, hba prediction, both new codes), `test_real_preflight_static` (16: no flag, environment key or credential option; the installer names no TEST-only file and takes its lists only from `real_roles`; the gate is keyed to the command; the probe child sends no statement), `test_real_identity_seed` (14; 6 need PostgreSQL), `test_postgres_real_preflight` (33, PostgreSQL), `test_preflight_calibration` (8, opt-in, skipped by default). Also changed because the tool now reads the install kind first: `test_real_publisher_tool`, `test_real_sidecar` (fake connections scripted with `rw_install_info`; the O5 "no write" assertion now reads "no statement but the kind read"), `test_real_gateway_static` (the reserved-prefix literal is defined once, in `connection.py`), `test_real_scope` (design 4.2 comment corrected).

**What the PostgreSQL tests show and do not show.** On the development cluster (PostgreSQL 17.11): the five guard functions are each compared (hollowed body, restored pin, dropped pin, dropped function; reverted in a rolled-back transaction); a non-superuser (the publisher role) can read every catalog and setting the runtime gate reads, including `has_parameter_privilege` for `public`; the cluster is refused (`PF_CONNECTED`) because it trusts its roles; the never-created role gives `OTHER`; `install_in_database` on a disposable database runs the REAL file list and REAL lists, writes `REAL` last, and the audit as REAL is clean; Phase 0 against the cluster is refused and creates nothing (counts of `pg_database` and `pg_roles` unchanged, no `finweb_real*` name); a granted membership is an escalation path (FF1-C09); a later migration's routine is refused until the revoke is re-run (FF1-C10); `publish` and `renew` stop on a failing gate and write nothing; `withdraw` proceeds, prints the result after, and keeps its own status. **These show the refusal side only.** No attempt was `CHALLENGED` or `REJECTED`: the classifier patterns for those two are uncalibrated until the opt-in test has been run in the cloud (not run here), or R8 step 1. The accepting side of the installer and the first read of a REAL catalog are first exercised at R8 step 1. In the tool tests a REAL target is simulated by replacing `_read_kind_rows` and `_run_gate` (the writes are real, on a TEST install); no REAL target exists.

**Not run, by instruction.** `test_preflight_calibration` (opt-in; the owner's cloud environment; no cluster started here). No database or role in the reserved namespace was created.

**Suites** (run one after the other, real lines):
- Default: `uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .` gave `Ran 4017 tests in 284.067s` / `OK (skipped=881)`.
- PostgreSQL: the same, prefixed `FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app FINWEB_PG_ADMIN_USER=<os-user>`, gave `Ran 4017 tests in 673.539s` / `OK (skipped=121)`.
- Baseline was 3854 tests, `OK (skipped=834)` and `OK (skipped=113)`. The difference is +163 tests. Default skips +47: the 33 PostgreSQL tests of `test_postgres_real_preflight`, the 6 PostgreSQL tests of `test_real_identity_seed`, and the 8 opt-in calibration tests. PostgreSQL-run skips +8: the calibration tests only.
- An earlier default run in this round failed once, `test_real_sidecar` (fake connection had no `rw_install_info`); fixed as above and re-run.

**Vendor files.** No new test reads `data/marketdata/files/`; the pinned list in `test_vendor_files_flag.py` is unchanged and passes.

**Decisions the contracts did not cover.** Listed in the plan, section 13. The main ones: `withdraw` with no readable kind row refuses and writes nothing; a field that cannot be read is a refusal, not a pass; the outcome patterns are libpq/server wording and fail closed when unrecognised; the identity seed lives in `real_tools` and verifies the stored columns separately from the digest.

**Not done.** Mutation checks of the new static test were not run in the first round (done in "R6 review fixes" below). The gate for the launcher and admission probe is R7's.

### R6 review fixes (2026-11-01)

Findings of "F1 R6 build — independent technical review" in `reviews/TECH_REVIEW.md`: TR6B-M-1, M-2, L-1 to L-4, and observations O-2 and O-3. No gateway SQL changed.

**TR6B-M-1 (Pass S covers the libpq the tools actually use).** `scan_stored_credentials` now scans the union of `PGSERVICEFILE`, `~/.pg_service.conf`, `PGSYSCONFDIR`, `pg_config --sysconfdir` and `LIBPQ_COMPILED_SYSCONFDIRS = ("/etc/postgresql-common",)` (psycopg-binary's bundled libpq 18). If `pg_config` is missing or fails (`sysconfdir=None`) the scan returns a NOT INSPECTED entry, which refuses (`PF_NOT_INSPECTED`); it is no longer a note. A service file that exists and cannot be read in any of those directories is likewise not inspected. `real_install.run_checks` now fills `sysconfdir` from `pf.installation_sysconfdir()` when none is given (the runtime gate already did). Tests (fake files under a temporary HOME or root; the helper is hermetic, with a known empty etc directory and no compiled default): `pg_config` unknown refuses and with a directory passes; `installation_sysconfdir` returns None for a missing and a failing `pg_config`; the compiled default is scanned; each of the five locations alone refuses; an unreadable file in a scanned directory is not inspected.

**TR6B-L-4.** A passfile or service-file host that is a directory is compared with the socket directory by real path (`_same_directory`; a path that cannot be resolved counts as a match). Test: the real spelling, a trailing slash, `//`, `/.`, a symlink and a symlink with a slash all match; `<dir>_other` does not; the service file with a trailing slash matches.

**TR6B-L-3.** `predict_hba` returns "unpredictable" for a `local` row with a database or user token that starts with `/` (regular expression) and for `samerole` and `samegroup`, besides `@` and `+`; the installer then refuses it as `PF_HBA_FILE_LOADED_DIFFER`. Tests: each token, a plain control, and the decision.

**TR6B-L-2.** `main` prints the withdrawal's own result and fixes its status first, then calls `_print_post_withdrawal_preflight`, which catches `BaseException` (Ctrl-C and `SystemExit` included) and prints "preflight could not run: <type>". Test, for a completed and a pending withdrawal and for `KeyboardInterrupt`, `SystemExit`, `TimeoutError`, `RuntimeError` and `MemoryError`: the withdrawal's first line is already printed when the gate starts, the status is the withdrawal's own, the line is printed once.

**TR6B-L-1 (five survivors pinned).** B6b: a missing escalation answer refuses (`PF_NOT_INSPECTED`, naming the pair). B23: a missing parameter-privilege answer refuses, for every key. B25: `could not load pg_hba.conf`, `pg_hba.conf is invalid` and `could not open file "pg_hba.conf"` classify `OTHER`. B26: Phase 0 with the real roles but no real database refuses with a subject for each of the four roles. B27: a LOGIN superuser with an md5, null or absent verifier refuses in Phase 2 and in `check`, with that role as the subject. The design agrees with the last one (5.3 (e): every LOGIN role); the code was already right, only unpinned.

**TR6B-M-2 (static no-bypass test).** New checks: (1) no tool imports `os`, `posix`, `nt` or `importlib` in any form, none names `environ` in an import, none uses `__import__`, `expanduser`, `environb`, `getenvb` or `putenv`; (2) no file read (`open`, `read_text`, `read_bytes`, `.open`, `.read`, `json.load` and the like) except the allow-list by tool and function: the installer none, the publisher `_read_input` and `_install_gateway_body` (R3's gateway file), the seed `main`; the call sites of the allowed reads are pinned to the command-line inputs (`args.proposal`, `args.evidence_file`, the `--sidecar` list, `args.seed_file`); (3) every `execute` argument in `real_install.py` is a string literal, a literal with `%` values, or the loop variable of a `for` over `role_statements`, `database_statements` and `schema_statements`, directly or through an assigned name; (4) the installer reads no file and imports no `subprocess`, `urllib`, `pickle` and the like. A fourth test checks the checker itself on the reviewer's spellings.

The reviewer's mutants, applied in a copy of `src/` and `tests/product/` (`/tmp/claude-503/r6fixtree`, restored after each), run against `test_real_preflight`, `test_real_preflight_static`, `test_real_publisher_tool` and `test_real_identity_seed`. The control gave `Ran 194 tests` / `OK (skipped=6)`.

| Mutant | Result | Failing test (first) |
|---|---|---|
| S3i `from os import environ as _E` in the installer | FAILED | `test_no_tool_imports_os_or_anything_that_reaches_the_environment_under_any_spelling` |
| S3s the same in the seed | FAILED | same |
| S3 the same in the publisher | FAILED | same |
| S4 publisher password from `Path("~/.finweb_publisher").expanduser().read_text()` | FAILED (failures=2, errors=2) | `test_no_tool_reads_a_file_except_its_named_inputs`, the import test |
| S6 installer executes statements from `installer_extra.txt` | FAILED (failures=3) | `test_no_tool_reads_a_file_except_its_named_inputs`, `test_every_statement_the_installer_executes_...`, `test_the_installer_reads_no_file_...` |
| S6b installer executes statements from `json.load(open("grants.json"))` | FAILED (failures=3) | same three |
| B6b missing escalation pair passes | FAILED | `test_a_missing_escalation_answer_for_any_pair_refuses_as_not_inspected` |
| B23 missing parameter-privilege answer passes | FAILED | `test_a_missing_parameter_privilege_answer_refuses_as_not_inspected` |
| B25 `_REJECT` loosened to any `pg_hba` | FAILED | `ClassifierTests.test_classes` |
| B26 Phase 0 accepts existing real roles | FAILED | `test_phase_zero_refuses_an_existing_real_role_with_no_real_database` |
| B27 verifier check limited to the four real roles | FAILED | `test_every_login_role_needs_a_scram_verifier_the_cluster_superuser_included` |
| L2 post-withdrawal preflight catches `Exception` only | FAILED | `test_the_withdrawals_own_result_is_printed_and_its_status_fixed_before_...` |
| M1a compiled default directory removed | FAILED | `test_the_bundled_libpqs_compiled_default_directory_is_scanned` |
| M1b unknown `pg_config` directory is a note again | FAILED | `test_an_installation_etc_directory_that_cannot_be_determined_...` |
| L4 exact string host compare | FAILED | `test_a_passfile_host_spelled_with_a_trailing_slash_or_through_a_symlink_still_matches` |
| L3a regex / `samerole` tokens not flagged (databases) | FAILED | `test_regular_expression_and_group_tokens_cannot_be_predicted` |
| L3b regex token not flagged (users) | FAILED (failures=2) | the same, and `test_a_regular_expression_row_in_the_file_...` |

**Observation O-2 (seed).** The seed now reads back every row after the writes, inside the transaction, and compares it with the seed on the stored columns (`RW_SEED_CONFLICT` on a difference, which rolls back). The docstring and plan 13.4 say precisely that: share-class and composite FIGI and the identifier rows are not stored, so they cannot be read back and are held to the proposal's digest only through the seed file. Tests: a fake connection checks that each of the three tables is read back after the inserts, and that a changed value in any one table refuses; the PostgreSQL seed tests run the read-back on a TEST install.

**Observation O-3 (plan).** Plan section 7 now says "no REAL install in the reserved namespace" and names the kit's crafted `REAL`-kind installs (R3's fixture and R6's `InstallerOnTestInstallTests`); their names are outside the reserved namespace, so the tools refuse them (5.2).

**Not changed.** O-1 (decide the name from `SELECT current_database()`): a design question for R7's launcher as well; left as built. O-4 (`initdb --pwfile` in the cloud calibration): accepted by the reviewer. O-5 is not R6's.

**Suites** (one after the other):
- Default: `Ran 4037 tests in 269.932s` / `OK (skipped=881)` (final run, after the last test edit; an earlier run of the same code gave `Ran 4037 tests in 309.314s` / `OK (skipped=881)`). That is +20 tests over the previous round (4017) and the same skips.
- PostgreSQL (the same command with the `FINWEB_PG_*` prefix): `Ran 4037 tests in 567.457s` / `OK (skipped=121)`. The same +20 tests and the same skips as before (the 8 opt-in calibration tests).
- A first PostgreSQL run of this round gave `Ran 4037 tests in 675.914s` / `FAILED (failures=1, skipped=121)`: `test_postgres_real_preflight.RoleClosureTests.test_the_four_roles_of_an_install_hold_no_membership_anywhere_and_the_preflight_sees_none` called `gather_facts` without a `sysconfdir`, which the TR6B-M-1 change now reports as not inspected. The two `gather_facts` calls in `RoleClosureTests` now pass `sysconfdir=pf.installation_sysconfdir()` (test change only, no product change); the module and the seed tests then gave `Ran 49 tests` / `OK`, and the full run above followed. One further PostgreSQL run was killed by an interruption of the session before it finished and is not counted.
- Tree check before the final runs: `/tmp/claude-503/r6fixtree` (where the mutants were applied and restored after each) differs from `src/` and `tests/` only in `test_postgres_real_preflight.py`, which I edited after taking the copy (the `sysconfdir` fix above); no mutant is applied in the real tree, and the static test passes in both suites.

### PD-0076 follow-up (2026-11-01)

The owner decided choices A to E (`decisions/product/PD-0076-r6-install-plan-choices-a-to-e.md`). R6 was committed at `4d7a6d1`; the cloud calibration of the first eight tests passed (STATUS.md). This follow-up changes one constant, adds tests, and rewrites the plan's choices. No gateway SQL changed; no `finweb_real*` database was created; the dev PostgreSQL was not touched; the opt-in tests were not run.

**Choice E, code.** `real_preflight.WITHDRAW_REQUIRE_AUTH` is `"!password"` (was `None`). `store._default_connect` already passes it as `require_auth` for `withdraw` to a reserved-namespace database, and `connect_with_prompt` adds the parameter when it is truthy, so the connection string carries `require_auth='!password'`. `withdraw` is still never gated by the preflight (`command_plan` unchanged). Tests: `test_withdraw_connects_under_its_own_constant` no longer pins `None` (it pins `"!password"`, and still shows the constant is the only thing that moves withdraw's demand, for `scram-sha-256`, `!password` and `None`); new `test_the_connection_parameters_of_each_command_carry_the_require_auth_of_pd_0076` runs the real `connect_with_prompt` through `_default_connect` with only `psycopg.connect` faked and asserts the connection string has `require_auth='!password'` for withdraw and `require_auth='scram-sha-256'` for publish, renew and status, `passfile='/dev/null'`, exactly one `require_auth`, and none for a TEST-named database; new `test_withdraw_stays_ungated_whatever_its_connection_demands`. No static check pinned the old value (the static test's signature and option checks are unchanged and pass).

**Choice E, server behaviour (opt-in, not run).** Five tests added to `tests/product/test_preflight_calibration.py` (same variable `FINWEB_PREFLIGHT_CALIBRATION=1`, same throwaway-cluster machinery, invented roles and passwords only; one more invented role, `cal_md5`, created and dropped by the test). They are: `test_withdraw_demand_is_the_negated_cleartext_password_method`; `test_withdraw_refuses_a_cleartext_password_server_and_the_password_is_not_sent` (hba `password`: libpq refuses with `PF_REQUIRE_AUTH`, the password is not in the error, the control with no demand connects, so the server really asked); `test_the_withdraw_connection_sends_no_password_message_to_a_server_that_asks_for_cleartext` (a stand-in server on a Unix socket answers the startup packet with AuthenticationCleartextPassword and records what follows: with `!password` no PasswordMessage, at most a Terminate; the control with no demand sends one containing the invented password); `test_withdraw_connects_to_a_scram_server_with_the_right_password` (a wrong password is refused by the server, `CHALLENGED`, not by the demand); `test_contrast_md5_and_trust_what_the_negated_demand_allows_and_what_the_scram_demand_would_stop` (RECORDED AND ASSERTED: `!password` allows an md5 server with an MD5 verifier and a trust server; `scram-sha-256` refuses both). Skipped without the variable (13 tests in the module now, all skipped here). **I could not run them, so their assertions about libpq's behaviour are unverified**; in particular the stand-in server's byte handling and whether libpq sends a Terminate on the refusal are my reading of the protocol, and the assertion allows an empty tail or a lone Terminate. The plan section 8 gives the command, including one that runs only these five.

**The install plan** (`implementation/CP7_F1_R6_INSTALL_PLAN.md`). Section 3 A to E are DECIDED with PD-0076's answers quoted and the consequences carried: A the dedicated macOS user (new section 4 item 0, section 5 steps, the remaining limit and the owner's recorded check of directory owners and modes); B the owner holds the executor, a named agent session may hold the loader password for one window at a time (the limit, the readable payload bytes, the HG4 package naming the session per window, the loader credential never goes to the cloud); C and D the two-window sequence with `phase1 --loader-login nologin` (section 6 rewritten: LOGIN, `\password`, `check`, the load or registration, NOLOGIN, then end any open loader session before treating the window as closed, R2 L-3); E the constant and its server tests (section 8). R6R-L1 and TR6R-L1 stay open (section 11). Header, contents, the exit checklist and section 9 updated to match.

**One point I could not settle and left open, not resolved** (plan section 3 B and section 11). PD-0076 B says the loader password reaches the agent session "by a prompt, never by a file or the environment". The tools take a password from a terminal prompt; an agent session's shell has no controlling terminal for the owner to type into, and typing the password into the chat leaves it in the session transcript. No loader command-line tool exists (R6R-L1). I do not read this as contradicting design 1.2 rule 4 or 3.3, which name the holder in R6's plan and allow a route that avoids the environment, a project file, a passfile and a service file, but the route is undefined. It is flagged for R8's plan and the owner.

**Plan wording after the follow-up review (TR6C-1, TR6C-2, O-6, O-7; PD-0077).** Plan only, no code or test change, so the suites below were not re-run. Section 3 B keeps PD-0076's quoted answer and adds PD-0077's ("I type it myself"): the owner types the loader password at the tool's prompt in the owner's own terminal for each window, no agent session holds it, and the HG4 package states that the owner held both credentials. The earlier "does not contradict rule 4" sentence is replaced by the reviewer's assessment (chat is the only channel into an agent session; it would contradict PD-0076 B and rule 4; PD-0077 removes it); section 6 (each window) and section 11 use the owner's terminal prompt as the loader's route, and any tool for step (4a) (R6R-L1, still open) or the step (2) load must take its password from that prompt. Section 3 B also lists the window's loader writes (`md_*` inserts, the registry put). Section 5 has the R8 precondition and section 12 a checklist row: the five `!password` server tests must have passed in the Fin-Web cloud before R8 step 1. `implementation/CP7_F1_REAL_PATH_DESIGN.md` 5.1 gets one note line saying PD-0076 E sets `require_auth=!password` for withdraw.

**Suites** (one after the other, final tree, before this plan-only edit):
- Default: `Ran 4044 tests in 180.014s` / `OK (skipped=886)`.
- PostgreSQL (with the `FINWEB_PG_*` prefix): `Ran 4044 tests in 588.870s` / `OK (skipped=126)`.
- Baseline was 4037 tests, `OK (skipped=881)` and `OK (skipped=121)`. The change is +7 tests: 2 new unit tests (connection parameters per command; withdraw stays ungated; they run in both suites) and 5 new opt-in tests (skipped in both suites). So skips are +5 in each suite.

### F1 increment R7: web real mode (2026-11-07)

Written by the Engineer, not reviewed by anyone. The technical reviewer has not seen it.

**What was built.**
- `src/web_api/real_mode_routes.py`: the real-mode app. It installs R5's scoped contract (create, list, read, reproduce under `/api/real/v1/roots`) and the session routes only; every other `/api/*` path is a closed 503 `REAL_MODE_ROUTE_CLOSED`. A foreign, unknown or malformed root is one 404 before the body is decoded.
- `src/web_api/real_launcher.py` and `src/persistence/real_tool_gate.py`: the launcher. Its target comes from the database name and the install-kind rows, never from an argument. A `REAL` target runs R6's preflight; a `TEST` target runs none. It has no path to the switch.
- `src/real_tools/admission_probe.py`: E27. One transaction on the executor connection, `admit` for `ARCHIVE_READ`, `ARCHIVE_EXPORT` or `EXECUTE_REPRODUCE`, the outcome or the refusal code printed, rolled back. There is no `EXECUTE_CREATE` choice.
- `web/src` (`real-mode.ts`, `real-mode-claims.ts`, `real-mode-i18n.ts`, `RealModeApp.tsx`, `real-main.tsx`), `web/real.html`, `web/vite.real.config.ts`, `web/e2e/real-mode-flow.spec.ts`: the screen, with its own list type and strings.
- Fix-first items: TR5-L5 (`claim_render.lineage_from_slots`; `real_scoped_contract._claim_block` re-renders and requires byte equality; `reproduce_payload` requires a digest unless `INPUT_MISMATCH` or `SOURCE_REFUSED`), TR6B-R-1 (the spelling checker of the static test), TR6C-3 (tool discovery), TR6B-R-2 (the `sysconfdir` fallback test).

**Tests added.** `test_real_mode_api.py` (32), `test_real_tools_start.py` (21), additions to `test_real_r5_pure.py`, `test_real_preflight.py` and `test_real_preflight_static.py`, `web/src/real-mode.test.ts` (57), and `test_postgres_real_mode.py` (15, PostgreSQL).

**What was not run.** `test_postgres_real_mode.py` was written and imported, but it has never executed: no PostgreSQL server was listening. `/tmp/.s.PGSQL.5432` does not exist, so the kit skipped all 15 tests with "No such file or directory". I did not start a cluster. The same holds for `tests/product/real_dev_env.py` (it refuses cleanly with "not provisioned") and for `web/e2e/real-mode-flow.spec.ts` (no server or browser may be started here). The D-3 PostgreSQL evidence is therefore the source reading below plus tests that have not executed.

**D-3 (put to the owner through the PM; not decided here).** Can the real-mode app hold a second user without an economic write? A registration writes `app_user`, `web_identity` and `web_session` rows and no portfolio, account or ledger row, so none of it is fenced. But the real install has no role that may write those rows: `real_roles.EXECUTOR_TABLES` gives the executor `portfolio`, `account`, `ledger_event`, `benchmark_selection`, `rw_root`, `rw_revision` and nothing else, and the installer creates four roles (owner, executor, loader, publisher). So as installed the app cannot register even one user. It needs a fifth role holding the four identity tables, and the install plan, the catalog audit's role lists and the preflight do not contain it. That is an install-plan decision, not mine.

**Suites.**
- Default: `Ran 4135 tests in 192.753s` / `OK (skipped=901)`. Baseline was 4044 / `OK (skipped=886)`: +91 tests, of which 15 are the new PostgreSQL module (skipped here) and the rest ran.
- `npx tsc --noEmit -p .` clean. `npx vitest run`: `Test Files 12 passed (12)`, `Tests 218 passed (218)`.
- PostgreSQL: not run (no server). Nothing in this increment ran against a database.

*(The first-round paragraphs "What was not run" and "D-3" above, and this PostgreSQL line, are superseded by the fix round below.)*

#### R7 fix round (2026-11-07, after PD-0078 and the Quant's wording ruling)

Written by the Engineer, not reviewed by anyone.

**PostgreSQL module now run.** After the PM restarted the development cluster, `test_postgres_real_mode` was run. Its first errors were two bugs in the test module: the account role's grants ran in the maintenance database, not the disposable one, and a test assumed an empty `rw_root`. Both are fixed. The module has since passed on every run (see the results in the fix-round report).

**D-3, as it now stands.** D-3 is NOT declared. PD-0078 (the owner's answer "Fifth account role (Recommended)") gives the real database a fifth role, `account`, holding `SELECT`/`INSERT` on `app_user` and `web_identity`, `SELECT`/`INSERT`/`UPDATE`/`DELETE` on `web_session` and `web_auth_rate`, `USAGE` on the schema, and nothing else. Built:
- `real_roles.ACCOUNT_TABLES`, the `account` entry of `role_lists`, and the optional `account_role` of `grant_statements`, `apply_role_grants`, `_check_install_inputs`, `_install_gateway_body`, `install_test_gateway` and `real_catalog_audit.audit`.
- The real installer: `InstallNames.account`, `role_statements` (the fifth `CREATE ROLE ... LOGIN`, no password), `GRANT CONNECT`, the audit call, the Phase 1 password list; `real_preflight.REAL_ROLES["account"] = "finweb_real_account"`, so Phase 0, Phase 2 and the runtime gate judge it like the other four.
- Tests: the grant list pinned (`test_real_role_lists`), the preflight cases (`test_real_preflight`), and on PostgreSQL an installer test (exact grants from the catalog), audit refusals (extra grant, UPDATE on `app_user`, economic, rooted-table and market-data grants, a gateway function, a sequence, a grant option, a membership, a revoked grant, a missing role) and installer-check refusals (`test_postgres_real_mode.AccountRoleInstallerTests`, `test_postgres_real_preflight.AccountRoleChecksOfTheInstallerTests`). The two-user isolation tests now run over an install whose account role was granted and audited by the product installer, not by a hand-made role.
- Engineer's choice: the `account_role` argument of the audit, the body and the TEST installer is optional, so the many earlier four-role fixtures stay valid. The real installer, Phase 2 and the preflight always require it. A reviewer may prefer it mandatory for `kind="REAL"` in the body itself.

**The Quant's wording ruling** (`methodology/CP7_F1_R7_CLAIM_WORDING_CHECK_2026-11-07.md`, R-1 to R-12): blocks R7-EN, R7-ZH, R7-PHRASES and R7-TEST-FORM applied as written to `real-mode-claims.ts` and `real-mode.test.ts`; R-12 is a Python test (`test_real_mode_api.ClientTextAgreesWithTheServerTests`) that fills the client's English professional templates from the server's slots and compares them item by item with `claim_render`'s text, with a control that finds a difference in either. `npx tsc --noEmit -p .` clean; `npx vitest run`: 224 passed.

**The intermittent PostgreSQL failure.** The failing test's name was lost, so this is from reading my tests. Found and fixed: the lapse test used a 2 s `valid_until` counted from before the publish call, and its positive control opened a new connection and ran the start gate, so on a loaded machine the control could meet `RW_LAPSED` (now 10 s). R7Case's install used the 4 s operation window, short for a create through the HTTP app under load (now 30 s). Checked and not a cause: the sign-up limit (`web_auth_rate` is per peer and per schema; each test uses its own peer and username), shared names and advisory-lock keys (every operation id and snapshot is unique per call), and test order (counts are compared as deltas; crafted grants are reverted in `finally`). I cannot show that these were the cause of that run's failure.

**Playwright fix (after the PM's first run).** `real-mode-flow.spec.ts` line 53 failed on the bare token `UNVERIFIABLE`, which occurs in the stored engine JSON (an `open_items` note about the CNY band check), not in any 7.4 sentence. The spec now checks the real origin labels and distinctive phrases of the 7.4 claim text in English and Chinese (no bare status tokens). The structural checks (`.real-origin`, `[data-claim-id]` count 0) cover the whole app. The text check is split: the app text with only the `.issued-result` block removed (at the start and in every language and depth), and the `.issued-result` text on its own for the same phrases. Nothing else is excluded. No other bare-token check exists in the spec. `real_dev_env.py` now line-buffers stdout; the README recipe says it exits on end of stdin.

**Playwright fix 2 (after the PM's second run).** Line 74 failed on "constructed by the project for testing", which is in the create form's acknowledgement checkbox on every screen (a permanent non-claim string). It is dropped from the list. The list now lives in `web/e2e/real-mode-phrases.ts` (real origin labels and wording unique to the 7.4 templates only), imported by the spec and by a vitest ("the phrases the browser spec forbids over TEST data") that fails if any phrase occurs in a non-claim client string (common, test-origin, refusal and TEST label strings, EN and zh, and the `RealModeApp.tsx` source) or if a phrase occurs in no claim template or real label. Scope of the text checks is unchanged: whole app minus `.issued-result`, plus `.issued-result` on its own; structural checks cover the whole app. Ready line: the print was already flushed, and I could not reproduce the missing line because I may not run `real_dev_env.py`; the same JSON is now also written to `<contexts-file>.ready.json` (0600, removed on exit), and the README records the unexplained pipe behaviour as LOW.

**Replay (PM's third run, line 97).** Not a product defect: the client mints a new operation id on every Create (`RealModeApp.submit`), and only the "repeat" button after an unknown outcome resends the stored body. The spec now expects a second command (201, `replayed: false`, new ids); vitest R7-REPLAY pins the id behaviour; the server's replay is `test_a_replayed_create_is_a_200` and the PostgreSQL module.

**Review round, F1 R7 independent review (TR7-M-1, TR7-L-1 to L-6).**
- **TR7-M-1.** The permanent title is now "Stored results" / "已存结果" (`common.*.title`, and `web/real.html` "Meridian — Stored results"). New vitest "no permanent client string states a real origin": the real origin labels and the wording real-source / real origin / from a real / 真实来源 may not occur in `common` EN/zh, `real.html` or the `RealModeApp.tsx` source (comments stripped, apart from the one entry tag rendered only for a real stored origin). It fails on the old title (three failures when the old EN title was put back; the test also carries the control). Excluded on purpose: the test origin's own mark and statements (they negate a real source) and `refusalZh` (some refusals name the real source in the negative). The drift guard is unchanged. The spec also asserts the h1 and the document title.
- **TR7-L-5.** `RealModeApi.create` turns no answer, a non-JSON answer, a 5xx that is not a contract refusal and a 200/201 that fails the strict reader into `UnknownOutcome` (id and body kept, repeat offered). A contract refusal (an error object with a code) stays a plain refusal. Vitest added.
- **TR7-L-6.** `install_account_routes` takes `session_cookie` and `bootstrap_cookie` (defaults unchanged); the real-mode app passes `finweb_real_session` and `finweb_real_csrf`. `CookieNameTests` in `test_real_mode_api.py`.
- **TR7-L-4.** The probe refuses (exit 2, `REFUSED PROBE_ROLE`, nothing sent) unless it is the named role, no superuser and not the schema owner; a `psycopg.Error` from the admission is `DATABASE_ERROR <class>` with its own exit status 3 and the text that it is not a gateway refusal. Tests in `test_real_tools_start.ProbeTests`.
- **TR7-L-2.** `test_the_shared_gates_function_bodies_are_pinned_exactly` pins the three functions of `real_tool_gate` as normalized source; `test_the_pin_sees_the_two_mutants_the_reviewer_found` applies G1 and G3 to the source text in memory and shows each changes exactly one pinned function. Nothing was written to the repo.
- **TR7-L-1.** `discover` now walks all of `src` (`rglob`) and takes a module that is a program (`is_program`) or a launcher (module-level `app`, or an import of uvicorn) and is real-related (a path part or file name with real / loader / launcher / window, or an import of one of the gateway modules). The temp-tree test includes G4, G5 and G6 and negative cases (a fictional dev server, a plain tool). Limit: a program with none of those names and no gateway import is not found.
- **TR7-L-3.** `subprocess`, `operator`, `pty`, `shlex`, `pexpect`, `commands`, `popen2`, `pipes`, `getpass`, `keyring` are banned modules for the checked modules; `methodcaller` and `attrgetter` are banned calls (bare and attribute) and names. The spelling mutants include G6 and R1. The `persistence/real_*.py` modules a checked module imports are held to the same spelling rules, except `real_preflight`, `real_provenance` and `real_sidecar` (documented, stale-checked).
- Not touched: the raw-JSON display, the claim text, O-1 to O-5.

**Re-review LOWs, 2026-11-07 (TR7R-L-1, TR7R-L-3; owner: "Fix them now").**
- **TR7R-L-1.** In `real_mode_routes.create`, once the service returns `Created` (committed), any failure to build the response (unbuilt lineage, render error, read error, any exception) answers the contract's `unknown_payload` (503, schema `finweb.cp7.real_scoped_unknown/1`), logged by class only; no new code. A refusal before the commit stays a refusal. Tests: the cited route test now expects UNKNOWN; a new route test (three failure kinds) shows the identical body then replays (200, `replayed: true`, same root) with the same operation id and no other id minted; a refusal-before-commit test. PostgreSQL (`AppOverTheRealServiceTests`, TEST install): a TEST create cannot fail to build by itself, so the claim render is patched to raise on its first call only; the first answer is UNKNOWN with the root committed (`rw_root` count 1), the repeat is a replay and the count stays 1. Client unchanged (it already treats the unknown schema as `UnknownOutcome`). In R7 the unbuilt lineage still means a REAL create replays to UNKNOWN until R8 builds it.
- **TR7R-L-3.** `real_preflight` is no longer excluded: `preflight_violations` applies the spelling rules to it and allows by name and function only the `os` and `subprocess` imports (module level), `getpass` in `terminal_prompt`, and one constant-tuple `getattr` in `RoleFact`; uses of `os`, `subprocess`, `getpass` and `sys` attributes are confined to the functions that need them (`os.environ` to `process_environment`, `subprocess.run` to the two child runs, `sys.executable` to `_spawn_child`). `connect_with_prompt` is in no list. In-memory mutants of the source text (nothing written): the reviewer's `subprocess.run(["printenv", ...])` (P1), `os.environ`, `os.popen`, `os.system`, a `subprocess` import and a `from subprocess import` inside `connect_with_prompt`, `operator.methodcaller`, `getpass` outside the prompt, and a `subprocess` import or use in a new function: all fail. The stale-exclusion check stays (two exclusions left).
- **Small.** The probe's role refusal says "Nothing was written."; the launcher and `real_dev_env` docstrings now say the account role is created by the installer (PD-0078).

**Second re-review LOWs, 2026-11-07 (TR7R2-L-1, TR7R2-L-2).**
- **TR7R2-L-1.** `PASSWORD_PATH` in `test_real_preflight_static.py` pins as normalized source `terminal_prompt` and `connect_with_prompt` (`real_preflight`), the two wrappers that remember a prompt answer (`real_launcher.remembered`, `real_install._remembered`) and the string builder the password passes through (`connection.conninfo_with`); `build_conninfo` takes no password and is not pinned. `PasswordPathTests` also forbids any tool or the shared gate to name `process_environment`, `process_home`, `_spawn_child`, `_read`, `scan_stored_credentials` or `Prober` (`installation_sysconfdir` is allowed: the installer passes it on as a directory name). In-memory mutants applied IN ADDITION to the prompt line, which stays: `process_environment().get(...) or password`, `_read(Path(process_home()) / ...) or password`, `_spawn_child(...) or password`, an environment read before the prompt, a changed `params`; and in `terminal_prompt` an environment read and a `subprocess` import: every one changes the pinned text, so the pin fails.
- **TR7R2-L-2.** The PostgreSQL test compares `rw_root` against a count taken before its first post (`roots_before + 1`), not an absolute 1. Run in the order create-read-reproduce-list-replay first, then this test: `Ran 2 tests` / `OK`.

**Third re-review LOW, 2026-11-07 (TR7R3-L-1; owner: "Pin them, then commit").** In `test_real_preflight_static.py`: (1) `PROMPT_STATEMENTS` pins, per tool (launcher, probe, installer, identity seed, publisher tool), every statement, signature and `if`/`while` test that names `prompt`, `ask`, `remembered`, `_remembered`, `terminal_prompt` or `connect_with_prompt`, per top-level function, as normalized source; a tool in `TOOLS` that names a prompt and is not in the table fails, so a newly discovered tool is pinned the day it is listed. No file reader, environment read or other source can stand in for `pf.terminal_prompt` in a pinned selection expression without changing a pinned statement. (2) `PASSWORD_PATH` now also pins `connection._quote`, `build_conninfo` and `is_reserved_real_name`, and `CONNECTION_CONSTANTS` pins `RESERVED_REAL_PREFIX` and `_SOCKET_NAME`; `build_conninfo`'s only callees are `_quote`, `os.path.split` and `_SOCKET_NAME.match`, all covered. In-memory mutants, all changing a pin: the reviewer's file reader in `real_launcher.main`, a value-logging `_quote`, a socket directory taken from the environment in `build_conninfo`; and one per new link (the selection in the probe, the installer, the identity seed and the publisher tool; a file read after the prompt answer in `remembered`; an extra wrapper statement in `main`; `is_reserved_real_name`; the reserved prefix).

**Fourth re-review LOW, 2026-11-07 (TR7R4-L-1; owner: "Fix it now").**
- **Runtime identity check.** New `src/persistence/prompt_route.py` (`require_genuine(module)`): the module IS `persistence.real_preflight`, and its `terminal_prompt` and `connect_with_prompt` ARE the objects the check saw at its own import. Each of the five tools (launcher, probe, installer, identity seed, publisher tool) calls it right after parsing its arguments, before any prompt is built or used; on failure it prints `REFUSED <TOOL>_PROMPT_ROUTE` with the reason, exits with its refusal status and writes and opens nothing. `tests/product/test_real_preflight_prompt_route.py` (not in `test_real_tools_start`, because the static test keeps the real installer out of the other test modules) substitutes a look-alike module and replaces each function, for all five tools: refused, no prompt asked, no connection opened. A static test shows the call is the first prompt-related statement of each `main`.
- **Pins in full.** `FULL_PINS` (SHA-256, first 20 hex digits, of normalized source): each tool's `main`, the connect defaults and prompt builders on the path (`default_connect`, `_default_connect`, `remembered`, `_remembered`, `make_account_store`, `build`), each tool's import statements, and the imports of `real_preflight`, `connection`, `real_tool_gate` and `prompt_route` (whose `require_genuine` is pinned too). The comment states that a legitimate later change to a pinned function means a deliberate pin update, with the reviewer told. A hash is used because five full `main`s as literals would be unreadable; `FullPinTests.digests` regenerates them.
- **Spelling-checked set widened.** Every module of `persistence/` that a checked module imports, and what those import in turn (the closure), not only `real_*.py`. `connection` (`os.path.split` in `build_conninfo`) and `migrator` (`os.listdir` in `load_migrations`) get exactly their `os` use, by name and function; `real_scope` joins the documented exclusions (a `__getattr__` proxy). Because the spelling rules do not see a plain `open()`, the same set is also held to a file-read allow-list per function (`PERSISTENCE_FILE_READS`).
- **Mutants (source text in memory, nothing written).** Y1 (the launcher imports a look-alike `prompting` module as `pf`; every prompt statement unchanged, so the earlier pin alone did not see it) changes the import pin. Y2 (`connect = connect or default_connect` replaced by a wrapper that hands `default_connect` a file-reading prompt) changes the `main` pin. One more per added defence: a wrapped `connect` or `prompt` in the main of the probe, installer, identity seed and publisher tool; a file-reading prompt in `default_connect`, the probe's and the publisher's `_default_connect`; a look-alike import in `real_preflight`, `real_tool_gate`, `prompt_route` and `connection`; a disabled `require_genuine`; the check call or its import removed from the launcher; and a look-alike prompt module that opens a dotfile is found by the file-read check. At run time the substituted module and the replaced functions are refused by all five tools.

**PD-0079 build, 2026-11-09 (key figures and the labelled raw document).**
- **Component.** `AnalyticalMetric.tsx` does not fit: it takes the fictional app's `AnalyticsResult`/question/binding, reads `react-i18next`, and interprets (`gainDirection`, `metricLabel`, `reasonLabel`, `subjectLabel`, partial-value context). I wrote the smallest component instead: `KeyFigures` in `RealModeApp.tsx` over `keyFigures()` in `real-mode.ts`. The server's response shape is unchanged (the stored result already holds `metrics[]` with `metric_id`, `view`, `subject`, `value`, `state`, `reason`, `currency`).
- **Figures.** A fixed list by (metric id, view), in this order: `portfolio_value`/REPORTING (the NAV), `holding_value`/REPORTING, `cash_value`/REPORTING, `receivable_value`/REPORTING. These are the single-date valuation's reporting-view figures (`performance/engine.py compute`). Native views are left to the raw document (one per currency or holding, and not needed for the HG4 NAV check). `portfolio_value_priced_holdings` is NOT listed: it is the partial figure that exists only when the total is suppressed, and beside a NAV row it could read as the NAV. Within a figure the stored order is kept; nothing is sorted. A listed figure the result lacks shows as absent.
- **Display.** Label, subject (as stored, `k=v`), value and currency string as stored, state as stored, reason as stored. The value is copied only for AVAILABLE and LIMITED; INSUFFICIENT_DATA, an unknown state and a missing state show no number (fail closed). LIMITED shows its state, reason and a marker beside the value. Over a non-real origin the existing invented-data mark heads the list (class `figures-mark`, not `invented-data-mark`, so the existing single-element check on the claim block is unaffected). The raw document stays collapsed and unchanged, below the figures, with an always-visible `raw-note` label above its `<details>`.
- **New strings** are in `common` (EN and zh), so the drift guard, the widened-wording test and the "no permanent client string states a real origin" test cover them. The claim templates are untouched. No depth variants.
- **Tests.** vitest: byte-for-byte values (19 integer digits plus 18 decimals, a negative with trailing zeros, `0.10` and `9.90`, stored order, fixed list order), INSUFFICIENT_DATA with a value present, unknown and missing state, LIMITED, absent figures, the TEST marking in both languages, the order claim limits / figures / note / raw document, the raw document byte-identical and collapsed, a pure in-memory REAL_SOURCE render, and a source scan that forbids number conversion, formatting, arithmetic, sorting and reduction in the figure code (nine mutants of the code are each found by it). Removing the INSUFFICIENT_DATA suppression fails 2 tests; removing the LIMITED marker fails 1. Playwright spec extended (NAV compared with the API's value, the marking, the raw label); not run.
- No pinned function of the gated tools changed; `FULL_PINS` is untouched.

**PD-0079 shape finding and the Quant's ruling, 2026-11-09.**
- **Finding (defect in my build).** `keyFigures()` was written against the performance engine's `ComputedMetric` dictionary. The result a TEST (fictional-scope) create STORES is the CP5 DIVERSIFICATION result (`service._stage_fictional`, selector `CP5_DIVERSIFICATION`): top-level keys `clusters, exposure_decompositions, manifest, manifest_id, metrics, result_digest`; `metrics[]` rows keyed `metric_id` + `method_key` (`diversification/1.2#...`), with `subject` a list of strings and no `view`, `currency`, `unit`, `stale_weight_presented`, `breakdown` or `partial`. There is no `portfolio_value` metric anywhere in it (the only money figures are `manifest.buckets[].value`, exact rationals per `CASH:<ccy>` and `SECURITY:<id>`; a total would be their sum). The performance document (`portfolio_value`/REPORTING etc.) is what the REAL branch (`_stage_real`, `compute_for_portfolio`) will issue, which is not wired until R8, so no stored instance of it exists. My vitest fixtures were hand-built to the performance shape and so did not catch this.
- **Not built, stopped on (by the PM's rule): F-1, F-2, F-3, and the NAV row over TEST data.** Each names a field the genuine stored TEST document does not hold (`stale_weight_presented`, the `portfolio_value_priced_holdings` row, `breakdown`, `portfolio_value`). Reported to the PM; nothing substituted or derived.
- **Applied:** blocks PD79-EN, PD79-ZH and PD79-TEST verbatim (all keys, including the ones F-1 and F-2 will use); F-6 (per-origin notes, test updated, plus "no `claim limits` / `声明限制` over TEST"); F-9 (`details` shown, uninterpreted); F-10 (only a string value is ever shown; AVAILABLE or LIMITED with a null, numeric or missing value shows `figureUnreadable`; only INSUFFICIENT_DATA shows `figureNoValue`); the strings F-4, F-5, F-7, F-8, F-11; the zh term guard.
- **Fixture and the hole.** `web/src/real-mode-stored-result.fixture.json` is a record of the stored document of a TEST create (its `metrics` without the per-run `manifest_id`, `manifest.buckets`, `clusters`, top-level keys, valuation manifest keys), made by a throwaway print from a PostgreSQL test on a TEST install, invented data. `tests/product/test_postgres_real_mode_figures.py` pins the shape (no NAV, no `view`, string subjects, the metric key set) and asserts the fixture equals the live document, so it fails when the shape or values move; the vitest tests read the same file and show every listed figure absent over it. Crafted variants of recorded rows cover F-9 and F-10.
- **Playwright spec** now pins what is true over a TEST create (the API has no NAV metric; the four listed figures show as absent; the marking and raw label show); it no longer compares a NAV value.

**Engineer's choice for the reviewer to judge.** The issued result is shown as stored JSON, so engine notes (such as the `open_items` entry above) reach the screen with no context or translation. I chose that over formatting the document, which would mean the client interpreting engine fields; the cost is unexplained engine text on the screen.

**Launcher.** `--account-user` takes its password only from the prompt; `test_real_tools_start.AccountRolePasswordTests` shows the prompt is asked for the account role over a REAL target and that no option or connection-string password route exists.

**PD-0080 build, 2026-11-09 (the figures read the document a REAL create stores; F-1, F-2, F-3).**
- **Engine-made fixture.** `tests/product/real_figures_engine_fixture.py` (not a test module) runs the real `performance.engine.compute` on invented in-memory worlds from `performance_kit` and serializes with `ComputationResult.canonical_json()` parsed as the route parses it. Four cases: AVAILABLE (Example W), LIMITED (V-2(a), stale weight 0.555632726768), SUPPRESSED (V-2(c), CNH cash with no FX: NAV no number, partial figure with counts) and SUBCENT (AAPL 1.004: total 2.01, breakdown 1.01 and 1, the holding row alone 1). All four are engine output; no row is crafted. The checked-in `web/src/real-mode-engine-result.fixture.json` keeps the listed rows and the partial row verbatim and, for every other row, only id, view, subject, state, reason. `real-mode-stored-result.fixture.json` (the TEST document) is unchanged.
- **What is and is not shown.** `test_real_figures_engine_fixture` regenerates and fails on any difference, and shows by AST that `_stage_real` stores `result.canonical_json().encode("utf-8")` of `performance_service.compute_for_portfolio(...)`, that `compute_for_portfolio` calls `engine.compute` once and `_finish`, and that `compute_for_portfolio` REFUSES the invented worlds (CP3-10), which is why the generator calls `engine.compute` directly. First-run at R8: the document of a real `_stage_real` over REAL_SOURCE data read back through the route; the fixture's manifest lacks the `detection`/policy citation `compute_for_portfolio` adds (no figure reads it).
- **F-1.** The row carries `stale_weight_presented`; shown beside the LIMITED marker as stored; a LIMITED `portfolio_value` with none shows `figureStaleNotStated`. **F-2.** The partial block shows only when the NAV row has no number and the partial row is stored, after the four groups, with `figurePartialNotNav` and both lineage counts. **F-3.** When the NAV has a number and a non-empty `breakdown`, each part shows the `shown` entry of its breakdown line (ref built from the part's subject); no line: no number and `figureUnreadable`; no breakdown: the row's own value. A lookup only; the no-arithmetic scan is green.
- **TEST and no-NAV.** Over a non-real origin whose document holds none of the listed figures, one statement (`testOrigin.figuresNone`, with the invented-data mark) REPLACES the four absent lines; nothing is read from `manifest.buckets`. Over a REAL source with no NAV row at all a bold notice (`figureNoNav`) replaces the NAV group's absent line; a suppressed NAV row (a row, no number) keeps its row and gets no notice. No server change.
- **Quant follow-up G-1 to G-6, 2026-11-09.** Applied verbatim: `figuresNone` (en, zh), `figureNoNav` (en, zh), `figureExcludedComponents` (en), the `FIGURE_LIST` comment. The no-NAV notice now sits inside the NAV group (the `noNav` variable and the `navStatus` import in the component are gone; `navStatus` stays exported and used by `partialBlock`). A fifth engine-made case RECEIVABLE (accrued dividend: total 11228.21, parts 5128.21, 6000, 100) is in the generator and the fixture; the Python test checks the hand values and the ref `receivable:{account}/{event}` from the row's subject; vitest covers the lookup and two mutants.
- **TR7F-L-1 to L-5 and the Quant's H-1, H-2, 2026-11-09.** Client: a value, a breakdown `shown` and a stale weight must be decimal text (a shape check, `1e3` allowed as the engine's text form; nothing is parsed or rewritten) and a count must be digits; more than one `portfolio_value`/REPORTING row shows every NAV row as not readable, apportions nothing and hides the partial block; a breakdown with a malformed line or a duplicate ref gives no part a number (not the first line, not the next good one); the stale weight shows only on a LIMITED row with a number (H-1), and a present-but-unreadable weight shows `figureUnreadable`; the two partial counts show only beside a number (H-2). Fixture: it now keeps the NATIVE rows of the listed figures (they come first), a sixth engine-made case SPLIT_UNRESOLVED (3 shares, 1-for-2 split) and the generator docstring is corrected (`compute_for_portfolio` runs in memory on the `test_performance_midpoint` kit). Python: a pure test runs `compute_for_portfolio` (only `_pin` replaced) against `engine.compute` on an `OPENING_*` ledger, a BUY ledger and a suppressed one (rows equal except `manifest_id`; manifest differs only in `detection_policy`, `split_detection`; partial row kept); `result` is assigned once in `_stage_real`. Guard: `REAL_WORDING` now covers the `testOrigin` table (only the two `mark` negations allowed, by exact string) and `real market`, `真实数据`. Mutants run in the real source, then reverted: `String(JSON.parse(..))` on the part, weight and count paths, `[x].map(Number).map(String)[0]`, `x*100/100` and removing the view check each fail vitest; dropping rows in `_stage_real` and dropping the partial row in `_finish` each fail the new Python test; `git diff -- src` is clean afterwards.
- **Re-review fixes TR7F2-L-1, L-2 and the exponent correction, 2026-11-09.** Mutants this round were run only on a copy of `web/` under `$TMPDIR` (the repo files were not touched; the earlier round's in-place mutants broke that rule and were reverted). `DECIMAL_TEXT` is now plain digits only (an exponent is unreadable on the value, breakdown, weight, count and partial paths; the comment is corrected); two `portfolio_value_priced_holdings` rows show the block as not readable with no count; a present, non-array `breakdown` gives no part a number (an absent key or an empty array still means no breakdown); the behavioural byte-for-byte test uses plain decimals only. The Python comparison has a fourth ledger (a stale holding as of 2025-02-12: LIMITED NAV with a stale weight) and a test whose in-memory `_finish` mutants (drop the weight, drop the partial row, drop a row) must each fail the comparison. Copy-run mutants, each failing the named vitest test (the one slot-table test that reads a server file also fails in the copy, as in the baseline of that copy): JSON.parse on part, weight and count, `map(Number).map(String)`, `*100/100` (all TR7F-L-2), removing the view check, allowing exponent, non-array fallback, two partials accepted.
- **Mutants** are on the data (a vitest cannot run a mutated component): the weight dropped, a partial row added beside a NAV number, a NAV number given to the suppressed document, a changed breakdown value, the breakdown emptied, a breakdown line removed. Each changes the screen as the rule says.

## F1 R8 guided runner (2026-11-15)

Not reviewed by anyone else; written by the engineer (a first draft was cut off before any test ran; the second engineer reviewed it line by line and fixed it).
Design: `implementation/CP7_F1_R8_GUIDED_RUNNER.md`.

- **Files.** `src/real_tools/r8_guide.py` (new), `tests/product/test_r8_guide.py` (new, 73 tests, mocks only), `tests/product/test_real_preflight_static.py`
  (`ORCHESTRATORS`, `OrchestratorTests`, pin `3bb6a4525230b7190ff4`), the design note.
- **Hard constraints, and what shows each.**
  - No password through the runner: no `getpass`, `terminal_prompt`, `connect_with_prompt` or driver name in the source (AST test); no `PG*` string; the psql
    scripts are constants with no secret; every child's env has no `PG*` variable and `PYTHONPATH=src`; no argv holds a password-like value.
  - Prompts and capture: the tools' prompt is `getpass.getpass` (`/dev/tty`); psql, initdb and sudo also use `/dev/tty`. `_real_run` pipes stdout and stderr only and
    leaves stdin to the terminal (a test fakes Popen and checks `stdin=None`). Vite alone gets `/dev/null` stdin (a keystroke reader). `sysadminctl -password -`
    reading `/dev/tty` is NOT verified.
  - Command lines equal the runbook's, argument for argument, for every tool (a test types each out) and every one parses with that tool's own parser.
  - Latch: written before exit for rule 0.3 and 0.4 stops; a plain re-run exits 3; reset needs a committed record, a newer clean HEAD and a typed phrase.
- **Changes to the draft.** (1) Vite is spawned with stdin `/dev/null` (the draft let it read the terminal and race the prompts). (2) `cluster_user` and
  `cluster_initdb` now re-check the clean tree (they take a password). (3) A create whose outcome was not recorded (quit or interrupt) is asked about on the next
  run (`create_pending`). (4) A recorded stop outcome with no latch re-latches on the next run; a reset marks it `lifted`. (5) Five tests added; the static pin
  recomputed (the draft's own pin was right for the draft). Nothing in the tools was changed.
- **Results (real).** `test_r8_guide`: 73 run, OK. `test_real_preflight_static`: 63 run, OK. Default suite as in `CLAUDE.md`: 4377 run, OK, 920 skipped, 193 s.
  No PostgreSQL or web suite run. No mutants run beyond those inside `OrchestratorTests` (in memory).
- **Mistyped-password exception (PM, 2026-11-15).** `exec_pw`: sudo (exit 1, "incorrect password attempt"), psql login (exit 2, "password authentication failed") and
  psql `\password` mismatch (exit 3, "Passwords didn't match") may be retried by the owner's choice, at most 3 times per step; the next failure latches; each
  failed attempt is recorded with its time, nothing typed. The reviewed tools are NOT included: none prints the server's text, so a refused password cannot be
  told from a server that is down. Seven tests added (`MistypedPasswordTests`); pin now `8bfbf1b9663f66420a1d`. Re-run: both files 143 run OK; default suite
  4384 run, OK, 920 skipped, 196 s (these supersede the counts above). The psql and sudo texts and exit codes are from source and docs, not from a run.
- **Tool connect-failure retry (PM, same day; tools unchanged).** `own_connection_failure`: exit 2 plus the tool's own whole-line connect failure with "nothing was
  sent" wording, for loader, probe, launcher (executor connect), publisher commands, and `real_install` phase0, phase2 and check; same 3-retry machinery, count in
  the state. Not eligible: phase1, `identity_seed` (its line covers statement errors too), the launcher's account-role failure. Tests: 6 more; pin
  `727a6da37a02ab874f23`. Both files 149 run OK.
- **Review fixes TR8G-H-1 to L-3 (2026-11-15).** Latch saved first in `handle_stop` (H-1); window open flag, notice with the exact close command, close on exhausted
  retries at a window step, and a step that needs the loader LOGIN goes back to `w*_open` when the window is closed (M-1, M-2; the test world now models LOGIN/NOLOGIN);
  only `PF_CONNECT_FAILED` retries (M-3); decision records must be files added after P8 / after the stop (M-4); `identity_seed` and `LAUNCH_ACCOUNT_ROLE` +
  `OperationalError` retry (L-1, read in the source); 4xx + `RW_WITHDRAWN` only under the withdrawal, a "no" latches, append-only `events.log` with the record built from
  it and a state/log disagreement refused, Vite from `web/node_modules/.bin/vite` (L-2); tests for the three surviving mutants, `PYTHONDONTWRITEBYTECODE=1`, note corrected
  (L-3). 16 tests added (`ReviewFindingsTests` and changes in `MistypedPasswordTests`). Pin `8fdf59a46bacc8f64e5d`; `ORCHESTRATOR_PLACES["os.open"]` gained `event`.
  **Re-review LOW fixes (TR8G2-L-1 to L-3):** a lifted latch's record is in `used`; a log without a state file refuses a first run (`STATE_MISSING`); `--status` reports a
  missing log or state plainly; tests for each, and one that kills "current P8 instead of the first". Pin `<private pin, PD-0083>`.
  **Final results:** `test_r8_guide` 105 run OK; with `test_real_preflight_static` 168 run OK; default suite 4409 run, OK, 920 skipped, 196 s.
- **Not done / open.** Never run against a real cluster, sudo, initdb or psql. The tool output regexes are copied from source and unexercised against real output.
  Phase 0 is not latched (runbook 3.2 says resolve and re-run), the one place rule 0.4's wording and the runbook's step differ.

## HG4 revision item 3 (PD-0087): DR-R8-1, DR-R8-3, DR-R8-4 on the real-mode screen (2026-11-16)

Engineer's self-validation; not a review.

- **DR-R8-1 (Open).** The list entry now carries `operation_id`, the root's one stored create operation. `RealWorkspaceService._entry_body` reads it with
  `SELECT operation_id FROM rw_revision WHERE portfolio_id=%s ORDER BY revision_seq LIMIT 1` inside the SAME `ARCHIVE_READ` admission that already reads `rw_root`
  (Python only; no installed SQL changed; the executor already holds SELECT on `rw_revision`, `real_roles.EXECUTOR_TABLES`, the same list for TEST and REAL; the row policy
  filters it like `rw_root`). A root has exactly one revision (operation CREATE; the root id is `uuid5(owner, operation)`), so no "latest" is chosen. `contract.list_entry` takes
  `operation_id` (required for a readable entry, refused on a refused entry); the client reader requires it (strict); Open calls `openEntry` = `api.read(root, operation)`
  and fills the Read form. **This changes the list wire shape that R5 reviewed (design 2.4: "R7 may not change its wire shapes without a new review"); the new review is PD-0087's.**
- **DR-R8-3.** Hint under the password field (EN, zh: at least 15 characters, at most 128 UTF-8 bytes; test reads `auth.py` for 15 and 128). `credentialsRefusalText` maps
  `INVALID_REQUEST` on sign-in/sign-up to a fixed readable text, code kept first; nothing of the input is in it and the server is unchanged. The password field is cleared on a refusal.
- **DR-R8-4.** `clearTyped` (Read ids, Create form, acknowledgement, kept unknown-outcome command) on session loss, sign-out and a successful sign-in/up (after the credentials are
  accepted, not on the refusal path).
- **Review round TR8F (PASS_WITH_FINDINGS; all fixed).** (M-1) The commands moved out of the component into `web/src/real-mode-session.ts` (plain functions over state
  sinks: `openStored`, `readTyped`, `refreshList`, `createRoot`, `reproduceRoot`, `enterSession`, `leaveSession`, `sessionLost`); the tests now check their EFFECTS (the root is
  set, busy while running, a refusal becomes the problem text) and that the component sends no request itself. `busy` is a required prop of `RootEntries` and every sink is
  required, so dropping `busy` or a sink is a `tsc` error. (L-1) A `SessionEpoch` is bumped on sign-out (first), session loss and sign-in; a result that arrives under an older
  epoch is dropped (read, list, create, reproduce), except that a 401 still shows its own message; `enter` clears `entries`, `root` and the typed values before the new list
  arrives; the stored result renders only while signed in. Tests: Open-then-sign-out, Refresh-then-sign-out-then-sign-in, read/create then session loss, reproduce then sign-out.
  (L-2) `INVALID_REQUEST` text and a new hint under the username field state both rules (username: 3 to 32 ASCII characters, letters, digits, dot, underscore or hyphen,
  starting with a letter; test pins the regex in `auth.py`), EN and zh. **List schema bumped to `finweb.cp7.real_scoped_list/2`** (both sides and the tests): the strict shape
  changed, and a captured `/1` list must not be read as the same shape; cost is four lines and nothing else references the string. Count corrected: the first version of the
  new test file had 12 tests, not 13; it now has 22.
  Known gap: a late 401 from user A's request, arriving after user B signed in, runs `sessionLost` on the shared client and clears B's screen (B signs in again); not fixed.
- **Tests added/changed.** `web/src/real-mode-revision.test.ts` (new; 22 tests after TR8F), `real-mode.test.ts` list reader (operation id required/refused), `test_real_r5_pure`,
  `test_real_mode_api` (x2), `test_postgres_real_r5_tails` (operation id equals `created.operation_id`).
- **Results (real).** `npx tsc --noEmit` clean. `npx vitest run`: 13 files, 299 tests passed. Default suite as in `CLAUDE.md`: 4409 run, OK, 920 skipped, 184 s.
  `test_real_preflight_static` + `test_real_mode_api` + `test_real_r5_pure`: 187 run OK (the static pins did not change).
- **Results after TR8F (real).** `tsc` clean; `vitest` 13 files, 309 tests passed. `FINWEB_PG_INTEGRATION=1 … test_postgres_real_r5_tails` (dev socket `/tmp/.s.PGSQL.5432`): 37 run, OK
  (so the `rw_revision` read and the operation id are now exercised on the TEST install; the REAL install was not touched). Default suite: 4483 run, **1 failure**, 920 skipped:
  `test_real_r5_pure ... test_it_is_installed_in_the_real_mode_app_and_nowhere_else`, because another engineer's new `src/real_tools/r8_http_check.py` imports the scoped contract
  (the test pins the importers as `service.py` and `real_mode_routes.py`); not caused by this change, to be settled with that engineer. Mutants could not be run (the shell command
  that builds `$TMPDIR` copies was denied by permission); the three reviewer mutants M2, M3, M19 are killed by reasoning only: M2 by "sets the root", M3 by `tsc` (required prop),
  M19 by the refusal test (an unwrapped command rejects).
- **Review round TR8F2 (PASS_WITH_FINDINGS; L-1 and L-2 fixed, L-3 accepted as it stands).** (L-1) Sign out is disabled while a command runs (`SignedInBar`, required
  `busy`). `busy` now belongs to the epoch: `SessionEpoch.track()` counts the running commands of the current epoch, a stale command's end changes nothing, and a change
  of session sets busy false. **The bump before the logout call is removed**, not kept: with Sign out disabled while busy nothing of the session is in flight when it starts,
  the second bump (when the logout is answered) already drops later results, and the first bump dropped the still-signed-in user's own results, including an unknown create
  outcome, when the logout failed. (L-2) Tests added for every surviving mutant: unknown outcome and follow-up list after a session change (E6, E7); credentials prefilled
  before sign-in (B11); a seeded reproduction cleared by Open, Read and Create (B6 to B8); `read` and `reproduce` arguments asserted (B5, B12); the list after a create (B4);
  a seeded problem cleared (B9); `shownRoot` (E17, plus a pin on its use). Tests in the file: 31. **Mutants run in a `$TMPDIR` copy (`$TMPDIR/m2/web`), vitest only, each applied
  to the copy and restored: E6, E7, B11, B6, B7, B8, B12, B5, B4, B9, E17 each fail 1 test (killed); also the pre-logout bump back (1 failed), Sign out enabled (1), busy cleared by a
  stale command (2), `moveEpoch` without busy reset (2), `shownRoot` unguarded (1).** `tsc` was not run on the copies (types resolve differently through the symlinked
  `node_modules`); the type-level mutants (required props) were not re-run this round.
- **Not verified.** (Before TR8F: ) The new `rw_revision` SELECT in `_entry_body` runs only in the PostgreSQL tests, which were SKIPPED here (no database): it is unexercised against a database,
  including the REAL install. Playwright e2e not run. No DOM in the web tests (no jsdom): the component's wiring is pinned on its source text and the behaviour is in exported
  pure functions. No mutants were run.

## HG4 revision item 1 and 2 (PD-0087, PD-0088): the supplementary-run tool and runner, and check 10.1 (2026-11-16)

Engineer's self-validation; not a review. Built to `implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md` revision 2 (TR8S H-1, M-1 to M-4, L-1 to L-5). Nothing was run against the cluster,
sudo, `pg_ctl`, the launcher or either runner; no network.

- **Built.** `src/real_tools/r8_http_check.py` (loopback tool), `src/real_tools/r8_supplement.py` (runner, a `Guide` subclass, own folder `~/finweb-r8-supplement/`),
  `r8_guide.py` (two behaviour-neutral class attributes `DIR_NAME`, `SCHEMA`; check 10.1 without the close: `QUANT_NUMBERS`, `compare_nav(holding, nav, missed, state)`, `s_check_nav`).
  Tests: `test_r8_http_check.py` (37), `test_r8_supplement.py` (27), `test_r8_guide.py` (updated for 10.1; 106), `test_real_preflight_static.py` (new `HttpToolTests`, the supplement
  in `ORCHESTRATORS`, two relaxed rules, pins). Section 7 added to `implementation/CP7_F1_R8_GUIDED_RUNNER.md`.
- **TR8S, how each is met.** H-1: `http.client.HTTPConnection(HOST, PORT, timeout)` with the constants `127.0.0.1`, `8004`; the static class bans urllib, requests, httpx, proxy
  APIs, `set_tunnel`, cookiejar, sockets, `os`, `input`, `open`, loggers; cookies parsed by hand. M-1: expected bytes `canonical_json(refusal_payload(ContractRefusal(code)))`, a test
  asserts each body's `error.code` and that the string-argument call gives `REAL_UNAVAILABLE`. M-2: B is `--phase b`, run before any create; `--resume` expects the 200; the count rule is
  2, or 3 with Y present. M-3: count != expected is exit 5 before the create; coded list/read/reproduce refusals are findings (5 before a create, 2 after), never a retry; every reproduce
  status but REPRODUCED stops; the runner latches on any exit but 0, 3, 5, 7. M-4: AST guard on the password (one prompt, one load inside one `json.dumps`), on emit arguments (no secret
  names, only safe keys, `.raw` only inside a hash or length), one `print`, header readers only in `default_send`; the tool never calls `input()` (the runner reads the acknowledgement,
  B's username and the name and passes options); the runner starts the tool only as a child and a test forbids any import of it; the two relaxed guards are stated in the test file with
  the reason; logout is in a `finally`. L-1: 401/422 are counted typos, 429 waits uncounted. L-2: the prompt label is `web account <name> (screen sign-in, not a database role)`.
  L-3: step `reeval_101` uses `attempts[-1]`, is labelled, writes only to the supplement's log. L-4: acknowledgement per phase with the requests listed. L-5: four B bodies.
- **Decisions the plan did not fix.** (1) Exit 7 for an unusable command line or a failed prompt-route check (nothing sent): argparse's own exit 2 would collide with "unexpected after a
  create", so the parser raises instead; the runner stops without a latch. (2) `pg_ctl stop -m fast --wait`: the long option, because the runner guard bans the string `-w` (psql's
  no-password flag). (3) A connection refused AFTER a create-route request was sent is exit 2 (a latch), not a retry. (4) Y's name is `R8 supplement`, the conflict's `R8 supplement
  conflict` with quantity 11, the 422 request uses quantity 0 and an id derived with `uuid5` from Y's id (no randomness in the tool). (5) `read_first` digests are reported by the
  tool and kept by the runner; the owner is not asked to type them. (6) Output of an unexpected body is its SHA-256 and length only; a matching contract refusal body is printed in full.
- **Results (real).** `test_r8_http_check` 37 OK; `test_r8_supplement` 27 OK; `test_r8_guide` 106 OK; `test_real_preflight_static` OK; the four together 242 OK. Nine behavioural mutants of the
  tool in a `$TMPDIR` copy (bare-string refusal body, Y-present tolerated, count check removed, logout not in `finally`, after-create finding as exit 5, replay accepted as 201, no CSRF
  header, a printed cookie, the sent flag not set) were each killed by `test_r8_http_check`. The static class's 26 source mutants (in memory) and the supplement's 14 are each caught by
  the checker and change the pin. Default suite: see the report.
- **Not verified.** The tool's `http.client` and hand-parsed cookie handshake against the real launcher (the fake launcher mirrors the cookie and CSRF rules read from `account_routes.py`;
  the sandbox cannot open sockets); the real `pg_ctl status` output format (`PID: n`, as the R8 runner's `pg_ctl status` use implies); the S8 line parsing against a real terminal; no
  PostgreSQL leg was run.

### Fix round after TR8S2 (FAIL: H-1, M-1, M-2, L-1 to L-7), 2026-11-16

Engineer's self-validation; not a review. Nothing was run against the cluster, sudo, `pg_ctl`, the launcher or either runner; no network.

- **H-1** every signing-in step has `services="C2.json"`; a rerun at `http_b` starts the launcher before the tool (tests: typo then "n", quit at the retry question, Ctrl-C; and `http_pre`
  after `--resolve retry`, `http_post` after a declined acknowledgement). **M-1** `pg_stop` is resumable (socket not required once `pid_before` is recorded; `pg_ctl status` decides);
  the message says the state is UNKNOWN. **M-2/L-6** taint tracking and the hard password rule; the reviewer's 10 leak mutants and 5 runner mutants are tests and each fails the rules.
  The runner may use the `r8_guide` module only as `base.<Guide name>` and a few listed attributes; `__import__` and `importlib` are banned. **L-1** B's username is re-asked on a retry.
  **L-2** the fake has separate bootstrap and session tokens, bootstrap-cookie deletion, 403, 429; `test_r8_http_check_kit` runs the unmodified tool through the real auth routes in process.
  **L-4** `--resolve http_pre done` refused; `http_post` without digests stops cleanly. **L-5** phase b: any root in B's list is a finding; `pg_stop` refuses while 8004 or 5175 is open.
  **L-7** the record's Run section is filled; `pg_start`'s commands sit under `pg_start`.
- **Surviving mutants, now killed (in a `$TMPDIR` copy).** Session CSRF token not used (34 failures), post-restart Y digest comparison dropped, reproduce `issued_sha256` comparison
  dropped, a refused connection after a create treated as a retry, the start-of-post count check dropped (each by `test_the_post_restart_comparisons_each_stop_the_run`, and the refused
  connection by its own test). Runner mutants each killed: `services` removed from `http_b`, `pg_stop` resume unreachable, port check dropped, `--resolve http_pre done` allowed, username
  not re-asked, `NO_CONNECT` counted, the declined acknowledgement leaving the step started.
- **Results (real).** `test_r8_supplement` 39 OK; `test_r8_http_check` 42 OK; `test_r8_http_check_kit` 2 OK; six focused modules together 344 OK; default suite 4503 tests, OK (skipped=920).
  Pins: `r8_guide.py` unchanged `<private pin, PD-0083>`, `r8_supplement.py` `da802c4b2462721ff8ce`, `HttpToolTests.PIN` `677d20c8fda752f7fa89` (Python 3.12 `ast.unparse`; the system
  python3.9 gives different digests).
- **Not verified.** As above: no real launcher, socket, `pg_ctl` or PostgreSQL leg.

### Fix round after TR8S3 (PASS WITH FINDINGS: N-L2, N-L3), 2026-11-16

Engineer's self-validation; not a review. Nothing was run against the cluster, sudo, the launcher or either runner; no network. The sources `r8_http_check.py` and `r8_supplement.py`
are unchanged, so no pin moved.

- **What changed.** `tests/product/test_r8_supplement.py` (one new test), `tests/product/test_real_preflight_static.py` (rules and mutant tests), section 7 of
  `implementation/CP7_F1_R8_GUIDED_RUNNER.md` (reworded to claim only what the rules enforce).
- **N-L3, the new test.** `test_a_declined_retry_at_a_create_step_and_exit_7_there_rerun_without_resolve_and_without_step_interrupted`: at `http_pre`, a declined retry at A's login and
  tool exit 7 each leave `started` cleared, no latch, and a plain rerun finishes with no `STEP_INTERRUPTED`. In a `$TMPDIR` copy each of the reviewer's two mutants (removing
  `no_effect` from either branch) fails this test alone.
- **N-L2, rules extended.** Tool taint: every `except ... as name` is a source (any class, tuples, `BaseException`), except the tool's own `Retry`, `Finding`, `Unknown`; a secret stored
  in an attribute that is not itself a source, or put into a non-local container, is a problem; a local container becomes tainted. Runner: `real_seams` may be named only in `main` and
  never as the object of an attribute or subscript; no dunder attribute except `__init__` and `__name__`. The reviewer's N1 to N5 and four runner bypasses, plus extra variants
  (tuple except, local container, module-level dict, `__class__`), are tests that fail the rules themselves and change the pin.
- **Left to the pin.** A value returned and emitted by its caller, `global` or `nonlocal` rebinding, an object method that stores its argument, a class-body assignment of a secret.
  Section 7 says so and names the whole-source pin as the backstop.
- **Results (real).** Default suite: 4504 tests, OK (skipped=920). Six focused modules (`test_real_preflight_static`, `test_r8_guide`, `test_r8_http_check`, `test_r8_http_check_kit`,
  `test_r8_supplement`, `test_real_r5_pure`): 345 tests, OK. Pins (Python 3.12): `r8_guide.py` `<private pin, PD-0083>`, `r8_supplement.py` `da802c4b2462721ff8ce`,
  `HttpToolTests.PIN` `677d20c8fda752f7fa89`.

## HG4 condition 2: the root's generation on the real screen (2026-11-17, engineer)

- **What changed.** Read contract `real_scoped_read/2` with required `created_under_generation` (from the stored envelope); web parser, `RootDetail`, list relabel and the
  one note (both locales); `r8_http_check.view` drops the new field (pin `677d20c8fda752f7fa89` -> `75a9b40922300de3b3dd`). No SQL, grant, migration, list schema or create result.
  Note: `implementation/HG4_CONDITION2_ROOT_GENERATION_NOTE.md`. The read path's role (executor) already has EXECUTE on `rw_archive` (`real_roles.py` EXECUTOR_FUNCTIONS).
- **Tests added.** `test_real_mode_api` (created-under 1 vs head 3, envelope-sourced, malformed envelope refused, list docstring and no extra list read, key set),
  `test_real_r5_pure` (required/validated field), web `real-mode.test.ts` (relabel, note once, empty state, refused entry, opened row, parser rejections).
- **Results (real).** Default suite: 4507 tests, OK (skipped=920). With PostgreSQL (dev cluster): 4507 tests, OK (skipped=126), 754 s. Web: `tsc --noEmit` clean, `vitest run` 13 files, 324 tests pass.
  Independent review is the technical reviewer's.

- **TR-G2 L-1 follow-up (HG4 condition 2).** Added `test_postgres_real_mode.AppOverTheRealServiceTests.test_the_list_generation_is_the_contexts_current_one_and_the_read_names_the_creation_generation_HG4_condition_2`: create at generation 1, renew twice (head 3), then through the HTTP app, the real service and the installed SQL the list entry says 3 and the read says `created_under_generation` 1 (also checked against the stored envelope). Mutants (in memory, from `$TMPDIR`, nothing in the tree): list entry reporting the artifact's generation, and read reporting the head; both make the test FAIL. No product code changed. Independent review is the technical reviewer's.

