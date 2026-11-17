# CP7 F1 on the real-data path: design options for the owner

2026-10-23, engineer, under PD-0065 (night run: design only, no code, no database, no network).
Revised 2026-10-23 after the independent review (`reviews/TECH_REVIEW.md`, "Real-path F1 design
(2026-10-23)", FAIL, findings 1 to 11). See "Changes after review" at the end.

Status: **PROPOSAL. Nothing in this file is decided.** Every "recommendation" or "lean" is the
engineer's view for the owner to accept, change or reject. Nothing here approves a gate, a data
download, a source admission or a change to a protected file.

What this is: the design for closing F1 ("every writer under one database authority, with
revocation, expiry and commit/rollback") for a **real-data** path, scoped to the smallest target
HG4 needs (`reviews/CP7_E9_REAL_SOURCE_AND_UAT_PACKET.md`): one project-constructed, non-personal
US account, 10 AAPL plus USD 500 on 2026-09-30, from Alpha Vantage files the owner downloads by
hand (PD-0063, PD-0064).

How this was checked: I read the documents and source named in the brief and the source files
quoted below. I ran no test, opened no database and read no raw data file (I listed file names
under `data/marketdata/files/` only). "Verified" means read in source. Everything else is taken
from the cited records and is as reliable as they are.

## 0. Decision table

| # | Decision | Options | Engineer's view | Owner must say |
|---|---|---|---|---|
| D1 | Namespace for real data | **A** shared canonical tables + mandatory provenance link (C02-A) / **B** separate real schema, real-only gateway (C02-B) | **Genuinely the owner's choice.** A has executed evidence for the fictional prototype but needs protected-file edits; B needs none but has no run evidence. Weak lean stated in section 1. | A or B; placement |
| D2 | Sole-authority object | **R-GW** snapshot/history/head/mode inside the real gateway / **R-SPLIT** separate addon / **R-MD** reuse `md_release` (rejected) | R-GW. Context identity is the snapshot content hash (section 2). | Confirm; allow replacing the E5 "permanent" refusal contract for this slice |
| D3 | Expiry | X1 lease at admission / X2 strict physical expiry / X3 explicitly non-expiring | **Expiry is UNKNOWN. HOLD is the default.** X3 only after a human verifies the current live terms and records what they say. | Whether and when the terms get read; until then HOLD |
| D4 | Five parked patches | adopt / generalise / retire, each | N2a, N2b: generalise. N3: re-target after N2b. PD-0059: depends on D1. PD-0060: defer as test pattern. | Confirm; keep a synthetic scope in product code or not |
| D5 | Writers W01 to W15 | participates / proven separate / refused | Section 5 (7 P, 2 S, 6 R) | Confirm legacy CLI exports stay outside HG4 |
| D6 | Acquirer recording | v1 human unchanged / + sidecar record / extend v1 / human v2 | v1 `human` unchanged + sidecar record + the owner's digest confirmation. Agent files via `manifest_v2`, not in the slice. | Naming; per-download approval record; fetch vs browser |
| D7 | Minimal HG4 slice | ordered increments R0 to R8, with branch deltas | Section 7 | Order and gating |

Dependencies: D1 first (it shapes D2, D4, D5). D3 and D6 are owner statements and do not depend on
code. D7 follows from the others and has a delta for each owner branch (section 7.2).

## 0.1 Facts this design stands on (verified in source unless noted)

1. **The F2 gateway is fictional by construction.** `src/persistence/guarded_workspace_v1.sql`:
   - `:21` `gw_mode` allows only `FICTIONAL_ONLY` or `CLOSED`; `:141-142` `gw_admit` refuses any
     other mode; `:145` refuses any expiry other than `NONE`; `:12` is the expiry enum.
   - `:289-335` `gw_check_artifact` requires `synthetic = true`, envelope schema
     `finweb.f2.fictional-issued-envelope/1`, snapshot scope `LOCAL_FICTIONAL_ONLY`, source
     records `synthetic = true` with `terms_check = null`, capital policy origin
     `SYNTHETIC_CANDIDATE`, and the fixed CP5_DIVERSIFICATION question/binding and fixture hashes.
     `:398` repeats `synthetic` in `gw_seal`.
   So a real gateway needs these predicates replaced under either D1 option.
2. **Writers choose their schema by `search_path`.** `ledger_store.py:72-79`, `web_account_store.py:73`
   and `migrator.py` ("Migration SQL must use unqualified names"). Any store runs unchanged on any
   connection that holds the grants.
3. **Real root storage is blocked by synthetic labels** (finding 3):
   - `migrations/0017_web_accounts_and_saved_sandboxes.sql:23`:
     `mode CHECK (mode = 'LOCAL_SYNTHETIC_ACCOUNT')` on `web_saved_sandbox`;
     `0018_web_portfolio_revisions.sql:6` has `web_portfolio_revision` reference
     `web_saved_sandbox`.
   - `web_account_store.py:23` `MODE = "LOCAL_SYNTHETIC_ACCOUNT"`; `:192` account name
     "Explicit fictional sandbox"; `:197` source reference "CP7 saved synthetic opening".
   - The migrator forbids editing applied files ("a change is a new file"), and F2 and the 19
     migrations are protected.
4. **F2's optional provenance is optional.** An ordinary valid F2 lease can still commit with no
   provenance link (case B06; `C02_C03_DECISION_DESIGN_V2.md` section 1; matrix FF1-C02).
5. **Protected-file coupling.** `validate_domain_constraints` accepts a fixed list of deferrable
   constraints, and F2 `_stage` runs `SET CONSTRAINTS ALL IMMEDIATE` before N2b attaches its link
   (matrix FF1-C02 `protected_item_conflict`).
6. **Manifest acquirers.** `manifest.py:123-124` accepts `human` or `synthetic` only.
   `manifest_v2.py` accepts only `agent`, only `INTERNAL_DEVELOPMENT_ONLY`, and needs script
   fields and an envelope digest. E1's gate (`real_source_contexts.py:210`) accepts only `human`
   and must stay limited (`TRUTHFUL_ACQUISITION_COMPATIBILITY_V1.md:11`). No code loads a v2
   manifest into ingest.
7. **Mutable authority today.** `files.py:55-58` reads `SOURCES.json` on demand; `ingest.py:264-270`
   and `:844` enforce the terms gate on whatever `SourceRecord` they get.
8. **A legacy real path exists outside the database.** `src/performance_tools/real_slice.py`
   reads `FileStore` and the registry directly (`:59-65`).
9. **Local real files exist** (gitignored, v1 manifests; names only, not read): Alpha Vantage
   `AAPL_compact.csv` (2026-10-01), NYSE and ECB calendars (2026-10-02), Frankfurter FX
   (2026-05-08 to 2026-09-30), OpenFIGI AAPL identity. **No split-event file is present.**
   Whether they suffice is a qualification question. Not verified: whether the owner's own
   database has the F2 addon, and what `SOURCES.json` currently records for `alphavantage.us`.
10. **Two axes, not one (P8).** In this code `state_kind` is the actual-versus-scenario axis:
    `financial_service_integration.py:327` requires `ACTUAL`, and `insights/engine.py:126` treats
    a non-`ACTUAL` state or a `scenario_id` as `SCENARIO_UNSUPPORTED`. Fictional versus real
    *market data* is a different axis. F2's fictional portfolios are already `ACTUAL`
    (`gw_check_artifact`, v1.sql:318). The "constructed, not the owner's holding" fact is carried
    by origin fields: E1 already names the HG4 ledger
    `PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED` with `personal_holdings=False`
    (`real_source_contexts.py:322-323`) and a mode string
    `LOCAL_REAL_SOURCE_TEST_ACCOUNT` (`:17`).
11. **Hard-coded synthetic readers and labels** (grep of `src` for `LOCAL_SYNTHETIC_ACCOUNT`,
    `synthetic=True`, `"synthetic": True`, `allow_synthetic=True`, `SYNTHETIC_ONLY`; 18 files):
    `persistence/web_account_store.py` (`list_portfolios` `:136-144` returns `MODE` and
    `synthetic: True` without reading the stored mode; capacity count `:186`; create `:192, :197`),
    `web_workspace_store.py` (`_initial` `:59-65` reads `web_saved_sandbox`; `:135`
    `allow_synthetic=True`; `:216`), `web_csv_store.py` (`:323, :509, :544`),
    `guarded_http_store.py` (`:150, :326-461`, listing `:374`), `guarded_csv_report_store.py`,
    `guarded_workspace_store.py`, `web_api/account_routes.py` (`:42` mode literal, `:204, :214`),
    `guarded_routes.py` (`:22`), `analytics_composer.py` (`:17` limitation text), `app.py`,
    `synthetic.py`, `account_dev.py`, `guarded_dev.py`, and the service layer
    (`financial_service_integration.py`, `performance_service/service.py`,
    `risk_service/service.py`, `performance/engine.py`). I did not read every one in full; R3
    must audit each.

## 1. D1. Target namespace for real data

**Question.** Where do real portfolios, accounts, ledger events, revisions and archives live, and
what stops every other writer from touching them?

### What switching schema alone does not do

- Fact 2: the same writers run against any schema that grants them access.
- Fact 4 and V2 section 1: copying F2 into a schema keeps the "ordinary lease, no link" commit if
  the original `gw_admit`/`gw_seal` are executable there.
- Fact 1: a copied gateway still refuses real contexts.
- Fact 3: the stored root would carry the synthetic labels and constraints.

So isolation comes from (i) who holds any privilege, (ii) a seal that cannot complete without the
real provenance link, (iii) a real-only mode, and (iv) real origin labels. D1 is how to get them.

### Options, side by side

| | **A. Shared tables + mandatory link (C02-A)** | **B. Separate real schema + real-only gateway (C02-B)** |
|---|---|---|
| Approach | Keep the canonical tables. Register each real root first; row triggers on 8 canonical tables refuse a write to a registered root without a real lease; the bundle guard requires the link at commit. | Fresh schema built with the migration chain; only a real-flavour gateway installed; legacy and fictional roles get no `USAGE`. The seal requires the link by design. |
| Evidence base | **The owner approved A for the fictional prototype (PD-0059). It was built and passed its tests.** `STATUS.md` (PD-0059 entries, 2026-10-20 log) and `reviews/FULL_F1_REQUIRED_2026-10-20/PM_ACCEPTANCE_V1.md` record: 6 offline, 8 native and 1 fresh-process method PASS, 0 failure/error/skip; ordered publication races, current rights, rollback, ACK loss and optional compatibility passed; 10 native write fences. **It was accepted with limits:** the workspace and `csv_apply` refusals were "NOT_FOUND early refusals only / PARTIAL", with "no all-writer closure"; PD-0060 later closed two wrapper gaps within a fixed scope; FullF1 stayed NOT_CLOSED. Those orderings were exercised, for the fictional scope only. | **No run evidence.** Built from F2's proven design, but every ordering must be proven again. |
| Protected files | The three PD-0059 edits **plus** real predicates in `gw_admit`, `gw_check_artifact`, `gw_seal`, the `gw_mode` check (fact 1). Needs owner approval. A change to those functions means part of the prototype evidence must be re-run. | None edited. New gateway file derived from the F2 design (fork). |
| Real root storage (fact 3) | **Same two sub-options as B** (below): S1 needs a new migration `0020` that reaches every schema incl. the fictional one; S2 uses add-on tables installed beside the gateway (as PD-0059's `required_synthetic_provenance_v1.sql` was an add-on, not a migration) and needs no migration. New real create code either way. | Same constraint problem: a fresh schema from the 19 migrations still has `0017:23`. S1 or S2 (below). |
| Isolation inside the executor role | Row guards + seal carry it. | **Same.** The real executor needs DML on `portfolio`, `account`, `ledger_event` and the web tables, because the stores issue canonical SQL on its connection. `WorkspaceStore.command` or `append_event` on that connection are stopped by the lease requirement, row guards and the seal's shape check, **not** by missing grants. |
| What is simpler | One login, one ledger, one migration chain. | Legacy and fictional roles are excluded by grants (a catalog check); no root-ID collision problem, because the whole schema is real. |
| What is costlier | Insert-first/register-later and root-collision ordering; an extra trigger and lock on every fictional write; regression proof for the accepted fictional flow. | A second schema built from the **same** migration chain (the `CHECKSUMS` chain is shared; each future migration is applied to both schemas); a **fork of the gateway file**; a real-mode launcher with its own account; Scenario Lab (CP8) needs a designed read path later. |

### V2 section 1's objection to B, answered directly

V2: the Python stores that issue canonical SQL cannot become the B capability model just by
switching the connection. **That is correct and B does not claim otherwise.** Under B the real
executor keeps direct DML gated by lease triggers (the F2 pattern), so the in-role ordering proof
(the B06 case: ordinary lease without link must not complete) is required for the new real gateway
exactly as for A. What B changes is only who else has grants and whether fictional flow can be
disturbed. V2's remaining point, that B means more new interface than A, still holds.

### Real root storage (finding 3, needed under both options)

A real HG4 portfolio must never be stored as `LOCAL_SYNTHETIC_ACCOUNT`, "Explicit fictional
sandbox" or "synthetic opening" (P9). New real create code is required (not
`WebAccountStore.create_portfolio`, whose labels are fixed). Its labels come from the root origin
(section 1.1).

| Sub-option | What it is | Files |
|---|---|---|
| **S1** relax the check | New migration `0020`: allow a second mode value (suggest the E1 string `LOCAL_REAL_SOURCE_TEST_ACCOUNT`) on `web_saved_sandbox`; real create writes through the existing sandbox/revision tables | New `migrations/0020_*.sql` + `CHECKSUMS` entry; new `real_account_store.py`; **and every legacy reader and label in fact 11 that would then see a real row**: at least `list_portfolios` (`web_account_store.py:136-144`, would report a real root as `LOCAL_SYNTHETIC_ACCOUNT`, `synthetic: true`), the capacity count (`:186`), `WorkspaceStore._initial` (`web_workspace_store.py:59-65`) and its `allow_synthetic=True` / "acknowledged fictional listings" checks (`:135, :216`), `web_csv_store.py` (`:323, :509, :544`), `guarded_http_store.py` (`:150, :326-461`, listing `:374`), `account_routes.py` (`:42, :204, :214`), `guarded_routes.py` (`:22`), `analytics_composer.py` (`:17`), plus the service-layer synthetic defaults. Applies to the shared schema under A, and to every schema built from the chain under B |
| **S2** real root has its own tables | The real root does **not** use `web_saved_sandbox`/`web_portfolio_revision`; add-on tables `rw_root` and `rw_revision` (installed beside the gateway, not a migration) hold the real root and revisions, and the gateway archive holds the response; `portfolio`/`account`/`ledger_event` stay canonical. **Available under A and under B.** Checked: nothing in the 19 migrations requires the real root to have a `web_saved_sandbox` row, and legacy readers that start from that table never enumerate it | `real_workspace_v1.sql` (B) or an add-on SQL file installed in the shared schema (A, as PD-0059 did); `real_workspace_store.py`; a real-mode read path in the web layer. It avoids the fact-11 reader list only for readers that start from `web_saved_sandbox`; readers of the shared canonical tables (ledger reads, analytics, service defaults) must still be audited so none stamps a real portfolio synthetic |

S1 touches the migration chain (new file only, old 19 unchanged, T10 holds) and so the fictional
schema too. S2 avoids that, and duplicates revision logic. The choice is independent of A or B.

### 1.1 Origin of a real-mode root (finding 4)

The root records, immutably, in its policy row and in every output: `market_origin = REAL_SOURCE`,
`ledger_origin = PROJECT_CONSTRUCTED_NONPERSONAL_UAT`, `personal_holdings = false`, and the
account/opening labels above. The UI must show the portfolio as a project-constructed test
account, never as the owner's holding.

`state_kind` is not the place for this. It is the actual-versus-scenario axis (fact 10): the
financial service requires `ACTUAL`, and a non-`ACTUAL` value or a `scenario_id` makes insights
return `SCENARIO_UNSUPPORTED`. A user-entered constructed ledger is not a scenario. So `state_kind`
stays `ACTUAL`, and "not the owner's holding" is carried by `ledger_origin` and
`personal_holdings`. HG2's older "hypothetical" label for a demonstration ledger was an origin
label (`pack.py`, "not a user's holdings"), the same fact. Remaining ask of the Quant: confirm that
`state_kind = ACTUAL` plus the origin fields is the intended encoding. I do not treat it as open
beyond that confirmation.

### Engineer's view on D1

Genuinely the owner's choice. A weak lean toward B, for one reason only: it avoids editing
protected F2 files and the shared canonical tables' triggers, which keeps the accepted fictional
flow and its evidence untouched. Against that stands A's executed evidence. If the owner values the
run evidence and one chain more than avoiding protected edits, A is equally defensible. What flips
it to A: one login/one ledger wanted, or the owner prefers not to maintain a second schema and a
forked gateway.

**Placement (sub-question).** Own schema in the dev database, or own database. Lean: dedicated
database, so `CONNECT` is also a barrier. PD-0065 forbids installing SQL into an existing
non-disposable database tonight.

**Files affected.** B: new `real_workspace_v1.sql`, `real_workspace_store.py`, real-mode launcher
under `src/web_api/`, S1 or S2 files, tests; unchanged `guarded_workspace_*`, old migrations.
A: the three `guarded_workspace_*` files and `gw_*` functions, an add-on SQL file for S2 or the
`0020` migration for S1, real create code, launcher, tests. S1 adds the legacy readers of fact 11.

## 2. D2. The sole-authority object

**Question.** How is a real release or context published, generated, locked and withdrawn, with no
fallback to the latest file, `FileStore`, or a mutable `SOURCES.json` (C03)?

### Required properties (E10 sections 2 and 4, matrix FF1-C03)

- An immutable **snapshot** per context: ordered members
  `(payload_sha256, manifest_sha256, acquisition reference or explicit legacy-null, adapter id and
  version)`, release id and digest, projection digest, **both** the full-registry digest and the
  used-source digest, identity, calendar, convention, profile and **F8B confirmation-policy**
  digests (finding 6c), the decision/rights evidence reference, and the origin fields of 1.1.
  Digests and metadata, not raw payload bytes.
- A stable, never-deleted **head row** per context; an immutable **history** row per generation;
  one **mode** row (`CLOSED`, `REAL_SNAPSHOT_V1`, `MAINTENANCE_HOLD`).
- Consumers take mode shared, then head shared, in the caller's outer transaction and read only
  the locked tuple. Issuer/revoker take the same rows exclusive in the same order. A revocation
  waits for in-flight work and is effective after its own commit (E10 section 4).

### Options

| | **R-GW** inside the real gateway (engineer's view) | **R-SPLIT** separate `real_authority_*` addon | **R-MD** reuse `md_release` |
|---|---|---|---|
| Shape | The gateway's own snapshot/history/head/mode, mirroring `gw_*` | Second set of tables + lock function the gateway calls | Mark an `md_*` release "published" |
| Pros | One authority, one lock order; matches the C03 "no shadow head" rule | Reusable by non-gateway consumers | Nothing new |
| Cons | Tied to the gateway's schedule | Two objects to keep consistent | `md_*` are append-only (migration 0011); mixes candidate data with authority (W04) |
| Verdict | Recommended | Acceptable if several gateways need it | Rejected |

### Context identity (finding 10)

In F2, `context_id = sha256(snapshot)` and a root is bound to one context. R-GW inherits this:
**a context is a content hash.** Consequences, stated plainly:
- Different content is a different context, never "a new generation of the same context".
- **Generation** counts only rights/withdrawal changes of one context.
- Adding A-shares later is a new snapshot and a new context. The HG4 root stays bound to its
  original context (reproduction keeps working); a root for the new context is a new root.
- Option for later: a logical context name with rebinding of roots across snapshots. That needs a
  designed, reviewed rebinding rule and is not in the slice.
Owner confirmation should say: content hash (recommended for the slice) or logical id.

### Lifecycle

1. **Generate.** A qualification run (increment R4b) produces proposal files and loads candidates
   through the candidate-loader role (W04). Files and candidates are inputs only.
2. **Publish.** One issuer command, one transaction: verifies exact bytes and digests against the
   proposal, appends history generation 1, inserts the head, sets mode `REAL_SNAPSHOT_V1`.
   Re-running with identical input returns the original; different content is a different context.
3. **Lock.** Mode shared, then head shared; no lower layer releases a lock; the lock function
   returns no bearer token.
4. **Withdraw.** A new generation with all four rights false, or mode `CLOSED`, in one
   transaction, waiting for in-flight work.
5. **Edit a proposal file.** Changes nothing live. An edited export is a new candidate.
6. **Never** a latest-file lookup, `FileStore` in the runtime, `SOURCES.json` in the runtime path,
   or a default registry. The snapshot carries the source records (with the human terms check) it
   was published with; `registry.require_attested` runs on that copy.

### Who may publish (finding 11)

Publishing and withdrawing are human acts. The issuer/revoker credentials are provisioned only to
the owner's own sessions, not to agent sessions, and every publish or withdraw records the issuer
actor and a decision-record reference (PD id and sha) in the history row (E10 section 2). That is
an operational control and a record, not proof of identity. A publication without a decision
reference is refused. The decision reference for the first real snapshot is the R0 record plus the
qualification decision; which PD covers which publish is for the owner to confirm.

**Open point (owner):** `real_workspace_contract.py` and the E5 acceptance describe a *permanently*
closed real contract. A scoped real route needs a new contract version and review, not an edit.

**Files affected.** `real_workspace_v1.sql`, issuer/revoker tooling in `real_workspace_store.py`
(A: the `gw_*` equivalents), tests T01, T02, T04, T05.

## 3. D3. Expiry

**What is established.** Nothing in the project verifies what Alpha Vantage's terms say about a
term, expiry or termination. `reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md` covers licence scope,
RAW close, history, splits and identity. It was read through a page summarizer, only about the first
half of the documentation was read, whether the terms PDF is current is listed as "Not verified",
and it says to re-check against the live pages before any decision relies on exact wording. It
records the licence as revocable. **So expiry is UNKNOWN (unverified live terms).** E10 section 5:
an unknown validity is not perpetual permission; FF1-C06: X3 is never inferred from a missing date.

| Option | Meaning | Needs | Status |
|---|---|---|---|
| **X1 lease at admission** | Finite validity checked at admission under the lock; an admitted operation may finish later | Terms that allow in-flight completion; `valid_until`, trusted clock, lease and cancellation tests | Designed later; not built if the terms show no finite term |
| **X2 strict physical expiry** | Valid at the physical commit instant | An external reservation/commit protocol that does not exist | Unsupported |
| **X3 explicitly non-expiring** | A human has verified that no finite expiry applies to this purpose; the local head still controls state | A human-verified, recorded reading of the **current live terms** | Possible only after that record exists |

### Default: HOLD

HOLD means: no head is published for the owner's real data, so the real run (R8) does not happen.
All other increments are still built and tested, so the real-scope code path is exercised before
R8 and not first on the owner's data:

- **Scope `SYNTHETIC_TEST`** (invented, `synthetic = true`) tests the fictional-scope regression.
- **A made-up real-shaped test context** (`INVENTED_REAL_SHAPED_TEST`) tests the *real-scope*
  branch: `synthetic = false` sources, a permitting terms check, v1-human members with invented
  bytes, `NONE` expiry with a test-only decision reference, the real admit/seal, origin labels. It
  runs the same code as a real context; only the content is made up.
- **Where it may exist:** disposable test databases only. Install-time marker: a `test_only` flag in
  the mode row and in the snapshot origin fields; the issuer and the real launcher refuse a
  `test_only` snapshot in a non-test schema and a real snapshot in a `test_only` schema.
- **What it must never be used for:** the owner's database; any UAT or HG4 evidence; expected values
  of the real run; any statement about a real source, price or licence; display in the product as
  data. Its outputs carry the origin label `INVENTED_REAL_SHAPED_TEST`. This is a convention plus a
  refuse-on-mismatch marker, not proof against a person with database ownership.
- It makes "R8 publishes the first real head" the first use of *real content*, not of the real
  branch.

### What X3 would require (not drafted for the owner to sign)

A human reads the live terms and records: the date and version/URL read; whether they contain a
fixed term, renewal, or termination or revocation on notice; what the terms say happens to stored
data afterwards; and, from that, which of X1/X2/X3 applies. If the reading shows a fixed term or
notice-based termination needing in-flight handling, the answer is X1 or HOLD, not X3. I do not
write the conclusion. The record is stored in the history row as the decision reference. `NONE` is
unreachable for a real-scope context without it (today `NONE` means "explicit fictional fixture").
`FINITE` and `UNKNOWN` remain HOLD. No re-read cadence is proposed; a reminder must not become an
automatic expiry.

**Audience.** The owner and the project's agents (PD-0028, PD-0064); nothing displayed or exported
to anyone else. This reading is the owner's, not legal advice or provider confirmation.

**Withdrawal granularity (owner question).** Rights are four independent booleans (create, read,
export, reproduce). Lean: default withdrawal sets all four false; keeping historical reports
readable is an explicit second step. **Scope of withdrawal (finding 11):** it stops the *database
runtime*. The raw files, the download tool, and the legacy CLI (W01/W02/W12, including
`real_slice.py` reading `FileStore`) are not covered; after a withdrawal they can still read and
export. Options: disclose the limit (the CLI is local and owner-run); add an owner procedure
(move the files, do not run the CLI); or later make the CLI consult the head. Lean: disclose plus
procedure now.

**Files affected.** `real_workspace_v1.sql` (history evidence reference; real `admit` accepts
`NONE` only with evidence), tests T07.

## 4. D4. The five parked patches

Locations: `reviews/CP7_EXIT_INVENTORY.md` section 3. N2a hard-codes the fictional scope
(`synthetic_provenance_v1.sql:86, :93, :135, :185`), so none can be merged and used for real
unchanged. CSV R1 is already merged (commit `df5b43b`, PD-0062) and is not part of this table.

**Coupling to `gw_*` (finding 7).** N2a's guarded load `np_guard` reads `gw_mode`, `gw_lease`,
`gw_head`, `gw_root`, `gw_rights_valid` (`:178-195`); N2b subclasses `GuardedWorkspaceStore`
(`synthetic_provenance_link_store.py:130`). "Generalise" therefore includes re-targeting this
coupling to the real gateway's objects (or, under A, to the generalised `gw_*`). It cannot be done
before those objects exist.

| Patch | Options | Engineer's view | Files affected |
|---|---|---|---|
| **N2a** candidate registry (5 files) | adopt / generalise / retire | **Generalise** scope and gateway coupling. Real scope requires `synthetic = false`, a permitting terms check, `INTERNAL_DEVELOPMENT_ONLY`, v1-human members (v2 refused in the slice), and no mixing with `SYNTHETIC_TEST` (P8 data-origin separation). | New provenance module/store/SQL derived from N2a; N2a tests become the synthetic-scope regression |
| **N2b** link to the financial service | adopt / generalise / retire | **Generalise.** The world builder builds registry, resolver, port, calendars and conventions from the locked snapshot and calls the real F8B service. Subclass target is the real store. | New real world builder; link tables; N2b tests re-targeted |
| **N3** concurrency/restart tests | adopt / re-target / retire | **Re-target after N2b.** Probe script under `reviews/` is evidence: retire. | New real tests derived from `test_postgres_synthetic_provenance_link_n3.py` |
| **PD-0059** required provenance (3 F2 edits + 4 new files) | adopt / generalise / retire | **Depends on D1.** B: retire the three F2 edits, keep the obligation design (policy row, row guard, bundle guard) as the real seal. A: adopt the edits, then generalise (the policy fixes `SYNTHETIC_TEST`). Preimages are byte-identical to HEAD (`cmp`), so regenerate by diffing `source/` against HEAD; the malformed headers in `FULL_PATCH.diff` do not matter. | B: none of `guarded_workspace_*`. A: `guarded_workspace_context.py`, `_store.py`, `_v1.sql` |
| **PD-0060** write-refusal test | adopt / generalise / retire | **Defer; reuse the pattern** for the all-writer matrix (T03). Depends on PD-0059. | New real-schema refusal test |

**Owner question:** keep a `SYNTHETIC_TEST` scope and the `INVENTED_REAL_SHAPED_TEST` origin in
product code (needed to exercise the real branch before R8) or only in test code. Lean: one
parameterised module so all scopes use identical rules and cannot be mixed.

## 5. D5. Writer boundaries W01 to W15 on the real path

Numbering: E10/N1 (`F1_AUTHORITY_EXPIRY_COMMIT_PROTOCOL_V1.md` section 1; matrix
`writer_boundaries`). Classes: **P** participates; **S** proven separate (shown by a test);
**R** refused (not wired, or denied). Scope: the HG4 slice (CREATE, read, reproduce on one
context). Under either D1 option unless noted.

| ID | Writer / reader | Class | How, and the proof needed |
|---|---|---|---|
| W01 | `FileStore.load_registry` / `SOURCES.json` (`files.py:55`) | **R as authority**; stays for historical and fictional tools | No positive real service loads it. Its content enters only as a proposal the issuer imports. T01: edit the file, nothing live changes. |
| W02 | Download tool (`download.py`: `fetch`, `register-file`, `probe`) | **S** | Writes only files and manifests; cannot publish or reach the database. `require_human` is not a security control (`:153`). A file is not live until published. |
| W03 | Manifest/ingest (`ingest_file`, `build_in_memory_market_data`) | **P (offline only)** | Runs at qualification before publication, with the terms gate. **R at runtime**: no ingest from `FileStore`. |
| W04 | `md_*` storage (`market_data_store.py:272-285`) | **P** | Candidate-loader writes immutable unreferenced rows; publication makes them reachable. One manifest per payload sha (matters for D6). |
| W05 | Readers (`read_release`, `:665`) | **P** | Called on the same outer connection under the held locks against the snapshot registry; internal transaction is a savepoint. |
| W06 | Resolver/derived | **P by freezing**; mutators **R** | Identity, calendar, conventions, profile from the locked snapshot; `add_vendor_id`, `change_ticker`, `apply_identity_assertions` and the live derived view unreachable. |
| W07 | Root create (`WebAccountStore.create_portfolio`) | **S** | Under B: legacy role has no grants in the real schema. Under A: row guard on registered roots. Real create is the new code of section 1. T03. |
| W08 | Workspace/ledger (`WorkspaceStore.command`) | **R** | Legacy roles: no grants (B) or row guard (A). **On the executor role** (finding 2b): refused by the lease requirement and the seal's shape check (single CREATE bundle), not by missing grants. T03 includes executor-role attempts. |
| W09 | CSV (`CsvImportStore`) | **R** | Not in the slice. The merged R1 report-only protocol creates no financial provenance (FF1-C11). Real CSV commit deferred. |
| W10 | Generic ledger, system events, selection, direct SQL | **R** | Same as W08. Ordinary lease without link cannot complete the seal. T03 covers every FF1-C02 entry class. |
| W11 | Financial service (`compute_for_portfolio`) | **P** | Same connection, staged ledger pin, explicit F8B policy digest from the snapshot; result must be `synthetic=false`, F8B dry run, accepted NAV, else whole rollback. |
| W12 | Legacy CLI and OS exports (`pack.py`, `evidence_pack.py`, `real_slice.py`) | **R for the HG4 runtime** | Read files, not the database authority; not claimed to follow purpose locks and unaffected by withdrawal (section 3). Not part of the UAT; at most a human cross-check, never the source of expected values. |
| W13 | Installer/migrator | **P** under maintenance | NOLOGIN owner distinct from runtime, issuer, loader; mode `MAINTENANCE_HOLD` first. Superuser/OS change is a declared trusted boundary. |
| W14 | Launchers/roles | **P** | Separate real-mode launcher and credentials, no owner fallback, startup refusal on mismatched schema/role/object pins. Environment inventory is a separate read-only step (FF1-C09). |
| W15 | Real routes (`real_workspace_routes.py`, `real_source_contexts.py`) | **R until R7**, then **P** for create/read/reproduce | E1 and its `MetadataProvider` (which reads a `SOURCE_REGISTRY` file from disk, `:142-164, :218-245`) stay limited and closed; real mode uses a new snapshot-based provider, not E1. |

Count: P 7 (W03 offline, W04, W05, W06, W11, W13, W14); S 2 (W02, W07); R 6 (W01, W08, W09, W10,
W12, W15; W15 becomes P at R7). A summary of intent, not proof of completeness: unknown reachable
actors stay HOLD (matrix closure predicate 2).

## 6. D6. Acquirer recording

### 6.1 The owner's hand download (v1, `retrieved_by: "human"`)

`FileManifest` stays as is. No change is needed to record a human acquirer.

| Route | Manifest records | Weakness |
|---|---|---|
| **a. Owner runs `fetch`** in their terminal (`download.py:476`) | function, symbol, `outputsize`, tool name and sha, retrieval time of the call | Needs the free key in the owner's environment; only `TIME_SERIES_DAILY` implemented |
| **b. Browser download, then `register-file`** (`:761`) | `request = (("origin","hand-made file"),)`, retrieval time = time of registration (`_now()`), adjustment from a flag | No request parameters; the RAW inference is keyed on `request.function`, so the owner's `--adjustment` flag carries it; a delay misstates retrieval time used by freshness |

Lean: route (a) for prices. Splits: see R4 (section 7); choice is the owner's.

### 6.2 Naming the human and the decision record

| Option | Verdict |
|---|---|
| a. Nothing more | Insufficient: no link to the per-request approval (PD-0027 cond. 2, PD-0062 item 4) |
| **b. Sidecar acquisition record** | Canonical-JSON record: payload sha, manifest sha, decision record id and sha, role "designated human product owner", request description, the owner's stated download time, tool or "browser", terms-check reference; carried in the snapshot member tuple as the E10 explicit-legacy provenance slot. Engineer's view |
| c. Name field in v1 | Rejected: exact key sets in `manifest_v2`/E1; every manifest digest would change |
| d. Human manifest v2 | Rejected for now: reopens the accepted E11 contract |

Naming: bind to the decision record (mandatory); record the **role**, not the personal name, since
the person is already named in the PD and `SOURCES.json`, and extra names in metadata that a model
may see add exposure without proof. The owner may name themselves. Per download: a PD (or
addendum) approves the request beforehand; afterwards the **owner confirms the file digests** in an
addendum. The sidecar cites both. Records are made by the main session.

### 6.3 Never downgrade agent to human: what is actually enforceable in the slice

A human can run `register-file` on agent-fetched bytes with the human-only switch set, and the
tool will write `human`. Per `TRUTHFUL_ACQUISITION_COMPATIBILITY_V1.md:66-68` that does not make the
acquisition human. The controls that can fire now:

1. **The owner's own confirmation of file digests after their own download** (6.2). This is the
   binding control. It is an attestation; it does not authenticate who fetched the bytes.
2. **Agent manifests are refused in the real scope** in the slice (R2 refuses v2/envelope
   members). This catches files that *declare* an agent, not relabelled ones.

Not claimed: a "seen under both" collision check and a `register-file` refusal for known agent
payloads cannot fire today, because v2 is refused in the scope, `md_file` holds one manifest per
payload, agent bytes (E7/E8) live outside the real schema, and there is no index of agent-acquired
payload hashes. If one is defined later (a list of E7/E8 digests), both checks become best-effort
detection, still not proof.

### 6.4 Agent-acquired files (such as the E8 sample): later, not in the slice

Use `manifest_v2` (`retrieved_by: "agent"` plus envelope). Wiring when wanted: (1) a v2-aware
candidate path with `read_manifest_metadata`, `verify_acquisition_binding` and an operator-supplied
`TrustedAcquisitionWitness`, giving `INTEGRITY_BOUND_NOT_ADMITTED`, then a separate human terms
check and rights step; (2) ingest via a typed manifest view without the acquirer (adapters do not
read `retrieved_by`; one synthetic-only exception), never converting v2 to v1; (3) storage of
envelope and witness in candidate tables plus a rule for a payload under two acquisitions
(`md_file` keeps one manifest per payload); (4) **not** the E1 gate: E1 must stay limited, so v2
loads through the new path only. Files affected: the provenance module, the member tuple; no change
to `manifest.py`.

## 7. D7. Minimal slice for HG4

Scope claim: F1 **closed for this named target only** (one context, CREATE plus read plus
reproduce, one real namespace). It does not close full F1, D3, real UAT or HG4. Each increment:
engineer builds and tests, independent technical review, main session records. Tests: T01 to T10
are E10 section 7; FF1-Cnn are matrix cases; all are proposals, none run. Provisioning uses the
in-repo helpers (`tests/product/guarded_pg_provision.py`, `dev_env.py`) on a disposable schema or
cluster.

### 7.1 Increments (order fixed by dependency)

| # | Increment | Needs | Tests it carries | Exit |
|---|---|---|---|---|
| **R0** | Owner decisions recorded as a PD. **Every** owner decision: D1 (A/B, placement, S1/S2), D2 (R-GW/other, context identity, E5 replacement), D3 (HOLD or the live-terms reading), D4 (fate of N2a, N2b, N3, PD-0059, PD-0060; synthetic scope in code), D5 (class assigned to each of W01 to W15), D6 (naming, per-download record, fetch vs browser, existing files vs new), D7 (this order), Quant confirmation that `state_kind` stays `ACTUAL` with origin fields | Owner | none | PD exists |
| **R1** | Real authority core: snapshot/history/head/mode, issuer/revoker, roles, expiry representation, **and the lease and root tables with the admit function** (N2a's guarded load needs the lease row and root row as well as mode and head, `synthetic_provenance_v1.sql:180-194`) | R0 | T01, T02 (two connections, blocking-pid causality), T04, T07 (`NONE` only with evidence; `FINITE`/`UNKNOWN` refuse), admit/lease tests, FF1-C03, FF1-C04, reduced FF1-C12 (idempotent re-run of an interrupted publish). Run for `SYNTHETIC_TEST` **and** the `INVENTED_REAL_SHAPED_TEST` context | Publish, withdraw, re-publish; a lease minted and refused on invented data of both kinds |
| **R2** | Real-scope provenance candidates (generalised N2a); guarded load bound to R1's mode, head, lease and root | R1 | Contract tests: reject synthetic source in real scope, missing/negative terms check, agent/v2 member, mixed scopes, `test_only` snapshot in a non-test schema; PG: N2a regression under `SYNTHETIC_TEST`; real-scope guarded load with a real lease; loader cannot publish | Candidates immutable and unreferenced; guarded load exercised in both scopes |
| **R3** | Real root storage (S1 or S2, including the fact-11 reader audit) and the gateway seal: journal/seal/archive with the mandatory link (generalised N2b), CREATE, archive read, reproduce, origin labels | R1, R2 | T03 all-writer matrix incl. executor-role attempts (every FF1-C02 class; ordinary lease without link refused); fictional flow unchanged (T10 control); T06; T08; T09 (rollback, ACK loss, UNKNOWN, no auto retry); FF1-C01, C02; a stored real root never carries a synthetic label and legacy readers never list it as synthetic | Catalog and behaviour assertions |
| **R4a** | Split input and policy: per `market-data/1.15` Ruling 6.5 (`methodology/CP2_MARKET_DATA_CONVENTIONS.md`, written tonight and still under review, so cited as pending): item 2 says no corporate-action file is required in `M`; item 8 recommends keeping any Alpha Vantage `SPLITS` file out of the UAT's `M` (the owner's choice, OP-2). **Default path: no split file in `M`.** An Alpha Vantage split adapter/fetch is built only if the owner chooses otherwise (then Ruling 6.4d policy rules apply in full). Also the F8B policy digest, identity and calendar snapshot, and the deferred `alphavantage.us` `terms_check` update (PD-0064) | R0, Quant ruling | Adapter tests on invented bytes if built; policy digest recorded | Inputs defined |
| **R4b** | The qualification run that writes the proposal files, and the issuer import of the registry into the snapshot | R1, R2, R4a | Qualification run reproducible; digests in the proposal match; proposal edit changes nothing live | Proposal files exist for the invented real-shaped release |
| **R5** | Real consumption: load a qualified release, read under the held lock, real F8B service call. Output carries the Ruling 6.5 claim limits (below) | R2, R3, R4b | FF1-C05; FF1-C08 (unaccepted result or error rolls back everything; ambiguous commit is UNKNOWN); **independent NAV oracle `10 x p + 500` derived by the quant-analyst, not from the engine or the same adapter**, first on the invented real-shaped release (E9 G13) | Preflight passes on invented data |
| **R6** | Deployment audit and one restart delta (read-only inventory of the owner's environment needs the owner's go-ahead) | R1, R3 | FF1-C09; FF1-C10 | Inventory written; unknown actors listed HOLD |
| **R7** | Web real mode: launcher, create/read/reproduce routes, UI with origin labels (1.1) and the Ruling 6.5 claim limits (below), EN/zh, three depths; closed refusal elsewhere; two-user isolation | **R3, R5, R6**; owner approval to replace the E5 contract | API contract tests; Playwright; foreign root returns generic 404 before decode; FF1-C11 sentinels (raw not in model-visible fields); closed routes still closed; UI test that the claim limits are shown | UI runs on invented data |
| **R8** | The real run on the owner's files, UAT, then the HG4 package | R5 to R7, D3 not HOLD, owner data approvals | UAT per E9 | Not an F1 deliverable; listed for sequence |

Dependency order, re-checked: R0; then R1 and R4a (R4a needs only R0 and the Quant ruling); then R2
(needs R1); then R3 (needs R1, R2) and R4b (needs R1, R2, R4a); then R5 (needs R2, R3, R4b) and R6
(needs R1, R3); then R7 (needs R3, R5, R6); then R8.

**Claim limits carried into R5 output and R7 UI (Ruling 6.5 items 5 and 6, pending review).** The
result may say: the holding value is `10 x p` where `p` is the close Alpha Vantage
`TIME_SERIES_DAILY` delivered for the 2026-09-30 XNAS session, read as as-traded (`RAW`, label
source `MEMORY`, split label `UNVERIFIABLE`); NAV is `10 x p + 500.00` USD; state `AVAILABLE`,
freshness `CURRENT`, delay `END_OF_DAY`; reconciliation `SINGLE_SOURCE`; the inputs by hash. It must
not claim: Nasdaq's official closing-cross price; a comparison with any other source; that the
listing had no split or that split history is complete or verified; that the quantity 10 is
verified (it is the ledger fact); anything about another date, a return, performance or risk. Dropping
these caveats changes the conclusion (P3). If the ruling changes in review, this list changes with it.

### 7.2 Branch deltas (owner choices)

| Choice | Effect on the slice |
|---|---|
| **B** (separate schema) | R1/R3 build the real gateway file and the new schema; S1 or S2 for storage; PD-0059 F2 edits retired; no protected edits |
| **A** (shared tables) | R1 generalises `gw_*` (protected-file edits, owner approval, prototype evidence partly re-run); R3 adds row guards on 8 tables and root registration before create; storage by S2 add-on SQL (no migration) or S1 `0020` plus the fact-11 readers; PD-0059 edits adopted then generalised |
| **S1 / S2** (either option) | S1: `0020` plus the fact-11 reader list in R3. S2: add-on tables and a real-mode read path in R3; the audit shrinks to readers of shared canonical tables |
| **HOLD** (default) | R1 to R7 are built and tested with both a `SYNTHETIC_TEST` context and a made-up real-shaped (`INVENTED_REAL_SHAPED_TEST`) context in disposable databases, so the real-scope branch runs before R8; no head is published for real data; R8 does not happen; HG4 on real data stays unrequestable |
| **X3 after a live-terms reading** | As HOLD until the record exists; then R8 can publish a real-scope head with `NONE` plus the reading as decision reference |
| **Terms reading shows a term or notice termination** | X1 design and tests added to R1; or HOLD |
| D6 other options | b is assumed in R2/R3; option a drops the sidecar and weakens the per-request link; c/d reopen frozen contracts and are not planned |

### 7.3 What can follow later

- **A-shares** (PD-0063): checked SSE/SZSE calendars (HG2 condition 4), `.SHH`/`.SHZ` adapter, CN
  conventions from the Quant, a new snapshot and a new context. `PRIMARY_ORDER["CN"]` is empty
  (`profiles.py:242`): no CN source admitted. The Alpha Vantage A-share route is being prepared
  separately tonight and is not admitted.
- Real CSV import (W09); ledger append/correction on real roots (W08, W10).
- More than one context or head (FF1-C07).
- X1 lease where terms need it; agent-acquired v2 wiring (6.4); real export purpose and the legacy
  CLI (W12); restore/maintenance drills; full publication fault injection.
- Hong Kong: dropped from the personal-use plan (PD-0063 addendum); still a V1 obligation.

## 8. Open questions for the owner

1. **D1:** A or B? Placement: own schema, or own database? Storage S1 or S2 (section 1)?
2. **D1.1:** `state_kind` stays `ACTUAL` and the constructed AAPL ledger is marked by its origin
   fields (section 1.1). The Quant is asked to confirm; the owner need only note it.
3. **D2:** content-hash context (recommended) or logical id? May the E5 permanent contract be
   replaced by a scoped version for this slice?
4. **D3:** do you, or a person you designate, want to read the live Alpha Vantage terms and record
   the result? Until then HOLD. On withdrawal, all four rights false by default? Disclose-plus-
   procedure for the legacy CLI and raw files?
5. **D4:** keep a `SYNTHETIC_TEST` scope and the made-up real-shaped test context in product code
   (disposable databases only), or in test code only?
5a. **Split file (Ruling 6.5 item 8, OP-2):** keep any Alpha Vantage `SPLITS` file out of the UAT's
   `M` (the Quant's recommendation and the default here)?
6. **D6:** bind each download to a decision record? Role or personal name? `fetch` or browser plus
   `register-file`? Use the files already present (2026-10-01/02) or download again? No split file
   is present either way.
7. Who holds the issuer credentials, and which PD is the decision reference for the first publish?
8. Does your own database already have the F2 addon installed? (Not checked.)
9. Should the Quant and the reviewer see this before R0?

## 9. Risks and what I did not verify

- No code was run. Every SQL claim (lock order, trigger timing, savepoint behaviour, the real
  seal) is a design claim until R1/R3 tests and review.
- Under B the real gateway is a fork of F2's design; drift is a maintenance cost. Under A the
  protected-file edits invalidate part of the prototype evidence.
- "Legacy roles have no privilege" must hold for default privileges, role membership and definer
  functions elsewhere (catalog audit, T03/R6).
- Database locks serialise recorded state only. A provider changing terms is outside them
  (E10 section 5). A trusted-operator boundary (superuser, OS) remains.
- Scenario Lab (CP8) needs a read path from a separate real namespace; not designed here.
- I did not read any data file, `SOURCES.json`, or the live terms; whether `AAPL_compact.csv`
  covers 2026-09-30 is unchecked.

## Changes after review (2026-10-23)

| Finding | Fix |
|---|---|
| 1 (HIGH, D3) | Removed "terms set no expiry" as a fact; expiry stated UNKNOWN with the data check's own caveats; HOLD default; no statement drafted; X3 only after a human reads the live terms and records version/date and clauses; audience corrected to owner and project agents (section 3) |
| 2 (HIGH, D1) | A and B shown side by side; A's PD-0059 approval and passed prototype stated; B's lack of run evidence stated; "catalog fact" claim corrected (executor needs DML; row guards and seal carry it); V2 section 1 objection answered; recommendation replaced by "genuinely the owner's choice" with a weak lean disclosed (section 1; D5 W08/W10 corrected) |
| 3 (P9) | Real root storage designed: facts on 0017/0018 and `web_account_store.py`; S1 (migration 0020) and S2 (own tables) with file lists per option; new real create code (section 1) |
| 4 (P8) | Fictional-vs-real separated from hypothetical-vs-actual; B's false P8 reason removed; origin fields recorded in the root and outputs; `state_kind` label left as an open Quant/owner question (fact 10, 1.1) |
| 5 | Non-downgrade restated: the owner's digest confirmation is the binding control; agent manifests refused in the real scope; uncheckable mechanisms removed and named as not claimed (6.3) |
| 6 | Added R4 (split input or "no split file" path referencing the pending quant ruling; qualification run and issuer import; F8B policy digest in the snapshot; `alphavantage.us` terms-check update) and assigned the NAV oracle to the quant-analyst (R5) |
| 7 | N2a/N2b `gw_*` coupling stated; authority core moved before provenance (R1 before R2); R7 depends on R3, R5, R6 |
| 8 | Branch deltas for A/B, HOLD/X3, terms outcomes and D6 (7.2); R0 lists every owner decision D1 to D7 including patch fates and writer classes |
| 9 | CSV R1 noted as merged (`df5b43b`); CN line is `profiles.py:242`; E1 v2 branch removed; W15 and the E1 file-reading provider addressed; audience corrected |
| 10 | Context identity defined as content hash; generation vs new context; HG4 root stays on its context; logical-id rebinding listed as later option (section 2) |
| 11 | Withdrawal scope stated (database runtime only; W01/W02/W12 unaffected) with options; publisher is a human issuer with a decision reference and an operational credential rule (sections 2, 3) |

### Second round (re-review PASS_WITH_FINDINGS, R1 to R8)

| Finding | Fix |
|---|---|
| R1 (MEDIUM) | Added a made-up real-shaped test context (`INVENTED_REAL_SHAPED_TEST`): real-scope code path, invented content, disposable test databases only, `test_only` marker refused in non-test schemas and vice versa; exercised in R1 to R5 and R7 so the real branch runs before R8; the list of what it must never be used for is in section 3 ("Default: HOLD"); HOLD delta updated |
| R2 (MEDIUM) | Fact 11 greps `src` for hard-coded synthetic readers and labels (18 files); S1's file list now names `list_portfolios`, the capacity count, `WorkspaceStore._initial` and its synthetic checks, CSV store, guarded HTTP store, routes, composer limitation text and service defaults; S2's residual audit stated |
| R3 (MEDIUM) | S2 offered under A as well as B (add-on tables, as PD-0059 did), with a stated check that nothing requires a `web_saved_sandbox` row; A-vs-B table row, files list and branch deltas updated; S1/S2 independent of A/B |
| R4 (MEDIUM) | Lease and root tables with admit moved into R1; R4 split into R4a (needs R0 and the Quant ruling) and R4b (needs R1, R2, R4a); "R1 with R4" replaced by an explicit, re-checked dependency order; R5 now also needs R2; R6 needs R1 |
| R5 (LOW) | `state_kind` reframed as the actual-versus-scenario axis (cited); it stays `ACTUAL`; the constructed ledger is marked by origin fields; only a Quant confirmation remains |
| R6 (LOW) | Ruling 6.5 (`market-data/1.15`) cited as pending review; default path "no split file in `M`" with the owner's OP-2 choice; claim limits (UNVERIFIABLE label, SINGLE_SOURCE, no other-date claim, etc.) carried into R5 output and R7 UI with a UI test |
| R7 (LOW) | PD-0059 evidence cited from `STATUS.md` and `PM_ACCEPTANCE_V1.md`, with "accepted with limits", the partial workspace/`csv_apply` refusals, no all-writer closure, and PD-0060's later narrow closure |
| R8 (LOW) | B's cost corrected: same migration chain, forked gateway file |
