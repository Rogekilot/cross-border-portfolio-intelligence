# CP7-F3 local fictional API contract and backend implementation plan

2026-10-20 Asia/Shanghai. Contract candidate only: no product implementation,
imports, tests, PostgreSQL or process actions have been performed for F3.
The owner authorizes contract → fictional local API/UI → browser E2E → independent
review → personal fictional trial readiness. Existing provider/data/personal-file,
dependency, commit/deploy, human-gate and no-night conditions remain in force.
F2's sealed source/evidence and historical failures remain unchanged.

## Scope and injection

Keep the existing URLs and authentication client. Add optional `guarded_profile`
injection to `create_app` and `install_account_routes`; absent injection retains
the existing default legacy application and transport models exactly. The local
F3 launcher explicitly injects one immutable fictional server profile. After the
existing auth routes, guarded mode installs the complete replacement saved route
set below and returns before old saved/CSV/analytics/packet/real installers.
Register explicit unsupported responses rather than leaving accidental fallback.

The same profile's `SyntheticWorld` supplies capabilities, saved workspace and
F2 service inputs. Construct it with an explicit empty `BenchmarkCatalog` callable
for every F3 path; never call the default real catalog loader. Guarded mode is
saved-account only: capabilities remain available, but guest-session/guest-portfolio
actions return fixed503 `F3_GUARDED_SAVED_ONLY`. Legacy guest mode is unchanged.

Reuse HttpOnly session cookies, existing register/login/logout, owner identity,
Origin/CSRF checks, strict Pydantic models, no-store responses and loopback boundary.
No owner/user ID, database/profile configuration, authority, service selector,
generation override, callback or issuer capability is accepted from HTTP bodies.

## Server authority and minimal additive database metadata

Use the actual unchanged F2 `GuardedWorkspaceStore`. Fixed positive selector is
`CP5_DIVERSIFICATION`; performance and historical analytics positives are absent.
The server source uses existing typed `CapitalUniverseChoice(FULL_NAV,
SYNTHETIC_CANDIDATE, scope_kind=GLOBAL_PRODUCT, product_id=PRODUCT_ID)` with explicit
fictional F3 decision/evidence text. This is test fixture policy, not human real
approval. Its context is independent of portfolio IDs and is published once per
fresh database by the separate issuer during root provisioning. App configuration
contains executor DSN, schema and expected source-context SHA only, never issuer,
bootstrap or owner credentials. The actual server profile recomputes and compares
its source snapshot bytes to that pinned published context before use.

New `guarded_http_v1.sql` adds ONLY three metadata functions, under the existing
NOLOGIN owner with fixed `pg_catalog,<schema>,pg_temp` search_path, fully qualified
tables, PUBLIC EXECUTE revoked and executor-only grants. No F2 table/function,
RLS rule, old migration or CHECKSUMS changes:

- `gh_head(context_sha text) -> generation bigint`: current committed generation
  only; no rights/source/payload bytes or mutation. The later F2 head lock/check
  remains authoritative, so a racing generation change refuses; no auto retry.
- `gh_owned_roots(owner uuid,context_sha text) -> root_id uuid`: at most32 owned
  selected root IDs, deterministic UUID order, no names or economic fields. Null,
  malformed inputs and unsupported source context refuse. Foreign owners are
  never supplied by HTTP; authentication supplies the owner.
- `gh_operation(owner uuid,root uuid,context_sha text,operation uuid DEFAULT NULL,
  revision uuid DEFAULT NULL,report uuid DEFAULT NULL) -> operation_id,revision_id,
  report_id,kind`: at most one selector may be non-null. Resolve only owned root/
  context committed operation metadata; no JSON/hashes/financial payload. No selector
  means current revision by existing revision sequence (initial CREATE when none).
  Requested revision/report must match that root and its immutable operation.

Metadata discovery is not permission to read payload. Every selected root is then
admitted with the current generation on the SAME executor connection/outer
transaction before old source/snapshot/report work. Request-scoped core instances
avoid mutable shared generation. F2 current mode/head/expiry/purpose locks remain
held through actual commit/whole rollback. Current head metadata is read before
admission without a lock; F2's locked recheck rejects races. Public commit calls
receive an IDLE executor connection and own its outer transaction. No lower layer
commits; no direct writes are added by the HTTP adapter.

Local rights remain F2's conservative CREATE+READ, READ alone, EXPORT+READ,
REPRODUCE+READ. Listing uses only UUID discovery followed by one serial current
READ lease per root; it never calls old `list_portfolios` on a new unleased
connection. Return no partial list/names if a selected root is held/refused.
Cross-root atomic listing is not claimed. Metadata functions do not authenticate
a hostile holder of executor credentials; the HTTP server/auth layer remains
trusted as in F2. The executor cannot issue/revoke rights or change roles/DDL.

## Capability and exact transport shapes

`/api/v1/auth/session` (and register/login/logout state) adds optional
`guarded_profile` only in guarded mode. `/api/v1/capabilities` includes the same
object alongside unchanged World capabilities:

```json
{"schema":"finweb.guarded_profile/1","profile":"F3_FICTIONAL_CP5","synthetic":true,"saved_only":true,"source_as_of":"2026-01-02","opening_date_required":true,"opening_date_max":"2026-01-02","opening_date_recommended":"2026-01-01","selector":"CP5_DIVERSIFICATION","operations":["CREATE","LEDGER","PREFERENCES","CSV_PARSE","CSV_PREVIEW","CSV_COMMIT","READ","EXPORT","ARCHIVE","REPRODUCE","RECONCILE"],"unsupported":["LEGACY_ANALYTICS","LEGACY_PACKETS","REAL_DATA","GUEST"]}
```

Capability facts guide presentation; the browser cannot submit them as authority.
Guarded create uses its own strict model: existing saved fields/mode plus REQUIRED
canonical `operation_id` UUID and REQUIRED canonical ISO `opening_date` no later
than source-as-of. The edge removes only operation_id from the inner F2 creation
body; all remaining explicit fields are retained in command identity/request
metadata. The existing F2 account edge validates opening date again. Jan1 opening
facts/Jan2 valuation enable same-source-date later events without weakening the
old snapshot-date rule. Equal Jan2 remains valid opening input, but Jan2 ordinary
subsequent events still refuse. Existing legacy HTTP models are not broadened.

Mutation success is HTTP200 and the following closed envelope. CREATE, LEDGER,
PREFERENCES and CSV use identical transport keys. `response` is convenience only;
the client hashes/parses normative exact UTF8 `response_json`, then applies the
existing Snapshot/WorkspaceResult/CsvCommit reader and root/revision binding.

```json
{"schema":"finweb.guarded_http/1","profile":"F3_FICTIONAL_CP5","disposition":"COMMITTED","synthetic":true,"portfolio_id":"uuid","operation_id":"uuid","revision_id":"uuid","response_json":"exact F2 archived UTF8 text","response":{},"response_sha256":"sha256","issued_sha256":"sha256","archive_url":"/api/v1/portfolios/uuid/operations/uuid","reconcile_url":"/api/v1/portfolios/uuid/operations/uuid/reconcile"}
```

Return only after F2 reports actual committed outcome. Retrieve revision binding
from immutable operation metadata. Exact retries preserve canonical request UUID/
body and return the original response/issued SHA; HTTP200 does not claim a new row.
Changed same-owner/op content remains409 conflict before head waiting. Never
compute a replacement response or repair/retry a refused command automatically.

F2's actual typed `RefusedWorkspaceResult` becomes HTTP422 with
`schema/profile/disposition=REFUSED/synthetic/portfolio_id/operation_id`, existing
`error:{code,detail,state:INSUFFICIENT_DATA}`, and exact `issued_json` plus
`issued_sha256` diagnostic only. It has no response/workspace/NAV and is emitted
only after the F2 result's whole-rollback check. Validation/rights/source/storage
errors use bounded existing error shapes, not this actual financial-refusal type.

F2 `UnknownWorkspaceResult` is HTTP202 with ONLY
`schema/profile/disposition=UNKNOWN/synthetic/portfolio_id/operation_id/reconcile_url`.
No response/issued bytes, numbers, persisted flag or rollback/zero-write assertion.
Operational/Interface errors around a write preserve ambiguity; generic database
errors are not relabeled as confirmed rollback. Network/malformed response is
likewise unresolved in UI. Retain exact op/body for deliberate manual same-body
retry or reconcile; never automatically retry a mutation.

Pure reads retain their old payload shape with one `guarded` object:
`schema=finweb.guarded_read/1,profile,portfolio_id,revision_id,operation_id,
context_id,generation,issued_sha256,archived_response_sha256,archive_url`.
These SHA fields reference the bound original archive, not the newly shaped read
payload. Portfolio-list entries each carry their latest committed operation link;
workspace carries current/requested revision's operation. Report reads link their
committed CSV operation. Preview/parse metadata links the already committed base
revision; it never claims the proposal's operation is committed. Existing preview
`preview:true/persisted:false` and report states remain intact.

Archive read preserves exact raw strings and byte hashes:
`schema=finweb.guarded_archive/1,profile,synthetic,portfolio_id,operation_id,
revision_id,context_id,generation,issued_json,response_json,envelope_json,
issued_sha256,response_sha256,envelope_sha256`.
Hash strings are lowercase64hex. Client hashes raw UTF8 strings directly with
WebCrypto before parsing/binding, without copying Python's canonical serializer.
Complete HTTP response limit20,000,000 UTF8 bytes; overflow refuses the whole
response, never truncates an issued answer. Existing input32768, CSV16384bytes/
128rows/32columns/32accepted-events and F2 byte bounds remain unchanged.

## Complete guarded endpoint table

All paths below are under `/api/v1`. All require authenticated server-derived
owner; every POST additionally requires existing Origin+CSRF. UUIDs/query formats
are strict and bounded. New core/file callbacks are never accepted from clients.

| Method/path | Current purpose and exact work | Response |
|---|---|---|
| GET `/portfolios` | Metadata owned IDs then serial current READ; bounded per-root same-conn name/summary query | Existing list, each entry guarded/latest op link |
| POST `/portfolios` | CREATE+READ; F2.create with stable op/explicit opening date | COMMITTED/typed REFUSED/UNKNOWN |
| GET `/portfolios/{r}` | Resolve current/requested revision metadata; READ; validate archive then existing WorkspaceStore.read with same conn | Existing Snapshot+guarded |
| GET `/portfolios/{r}/workspace` | Same current READ and same-conn WorkspaceStore.workspace | Existing Workspace+guarded |
| POST `/portfolios/{r}/ledger-commands/preview` | CREATE+READ; actual old command preview with DB scope; unconditional whole outer rollback; output only after known IDLE | Existing preview+base guarded; ambiguity UNKNOWN |
| POST `/portfolios/{r}/ledger-commands` | CREATE+READ; F2.ledger_command | COMMITTED/typed REFUSED/UNKNOWN |
| POST `/portfolios/{r}/preferences` | CREATE+READ; F2.ledger_command(preferences=True) | Same disposition envelope |
| POST `/portfolios/{r}/imports/parse` | READ on committed base BEFORE parse_source; existing `_owned` on same conn, no old parse reconnection | Existing parsed rows+base guarded |
| POST `/portfolios/{r}/imports/preview` | CREATE+READ; actual F2.csv_preview with same conn/whole rollback | Existing preview receipt+base guarded; ambiguity UNKNOWN |
| POST `/portfolios/{r}/imports/commit` | CREATE+READ; F2.csv_commit; exact replay no reparse/compute | COMMITTED/typed REFUSED/UNKNOWN |
| GET `/portfolios/{r}/imports` | READ; existing CsvImportStore.list with same conn/cursor | Existing report page+base guarded; each row op link |
| GET `/portfolios/{r}/imports/{report}` | Owner/report metadata→READ; actual existing report validation same conn | Existing report+guarded CSV op link |
| GET `/portfolios/{r}/imports/{report}/export?format=json|csv` | EXPORT+READ; existing actual exporter same conn | Existing safe download headers/content + operation header |
| GET `/portfolios/{r}/exports/{holdings|transactions}?revision_id=...&format=json|csv` | EXPORT+READ on exact revision; existing exporter same conn | Existing protected CSV/lossless JSON + revision/op headers |
| GET `/portfolios/{r}/operations/{op}` | Current READ; F2.archive_read, strict native bindings | Raw archive object above |
| GET `/portfolios/{r}/operations/{op}/export` | EXPORT+READ; F2.archive_export | Complete archive JSON attachment; safe canonical UUID filename |
| POST `/portfolios/{r}/operations/{op}/reproduce` body`{}` | REPRODUCE+READ; actual F2.reproduce against original generation/issued bytes | `schema/profile/synthetic/root/op/status/detail/issued_sha256`; require REPRODUCED for UI success |
| GET `/portfolios/{r}/operations/{op}/reconcile` | Current READ; F2.reconcile; existing archive only, absence remains UNKNOWN | Same COMMITTED exact response envelope or202 UNKNOWN |
| Old packet GET/reproduce and analytics evaluate/evidence/reproduce | Authenticate, POST CSRF, then fixed503 `F3_GUARDED_UNSUPPORTED`; no old source/composer fallback | Typed unavailable state, no financial payload |
| Real source/workspace endpoints | Authenticate then fixed503 `F3_GUARDED_UNSUPPORTED`; never load/admit real data | Typed unavailable state |

No unmatched `/portfolios/...` route may dispatch into the legacy installer in
guarded mode. Foreign/mismatched archive/read IDs receive indistinguishable404
without payload; reconcile absence retains F2 UNKNOWN without revealing another
owner's existence. Head changes/finite/unknown expiry cause bounded HOLD/refusal,
not stale success. Map known F2 errors by exact diagnostic only: NOT_FOUND404,
IDEMPOTENCY/STALE409, RIGHT403, GENERATION/MODE/EXPIRY423; malformed input422 and
other storage503. No SQL text, connection configuration, request credentials or
raw exception internals are reflected. Current-head withdrawal tests use issuer
outside the app; app owns no issuer capability or HTTP administrative route.

## Exact proposed backend edit boundary

Two existing files only:

1. `src/web_api/app.py`: optional guarded profile/world/capability injection and
   guarded-saved-only guest refusal, keeping absent-profile behavior.
2. `src/web_api/account_routes.py`: optional profile state and complete guarded
   installer branch after auth routes; ordinary saved handlers/models unchanged.

Four new source files:

3. `src/web_api/guarded_routes.py`: strict F3 create/archive models, full route table,
   bounded disposition/raw-byte serialization, safe download and exact error mapping.
4. `src/persistence/guarded_http_store.py`: immutable server profile and explicit
   request-scoped F2 facade, same-conn read/preview/export helpers, metadata addon
   installer. Public helpers are fixed methods, not arbitrary read callbacks.
5. `src/persistence/guarded_http_v1.sql`: exactly the three metadata functions,
   no table/old SQL/F2 behavior changes.
6. `src/web_api/guarded_dev.py`: explicit owned configuration JSON/CLI local app
   factory, no `.env`, default credentials, migration or issuer connection.

New tests `tests/product/test_guarded_http_contract.py` and
`tests/product/test_postgres_guarded_http.py`; this plan is the ninth backend path.
Do not edit F2's12 sealed product paths or existing tests/fixtures/migrations,
financial methods, dependencies or public real-data gates. Parent reviews/releases
this boundary before product implementation. Source/SQL/route/runtime review then
meaningful API tests precede actual browser E2E and personal-trial documentation.

## Bounded real runtime and validation sequence

Root owns `/private/tmp/finweb-cp7f3-20261020/runtime-a1`, PG17.11 Unix55433/TCP
disabled, API127.0.0.1:8003 and UI127.0.0.1:5174; only these newly owned loopback
origins are allowed. Existing servers/clusters/F2 leaves remain untouched.
Use installed uv/Python3.12, Node26.8.2 and installed Chrome; no installation,
browser download, external navigation or package fetch. Root-only new helper
`/private/tmp/finweb-cp7f3-20261020/backend/prepare_f3_runtime.py` will provision via
ACTUAL load_migrations/apply_migrations(old19), F2 installer and new metadata addon,
then publish fixed GLOBAL_PRODUCT fictional context/rights through issuer once.
It writes separate owned0700/0600 app config with executor only and records actual
PG identity, schema/roles/source context, migration history and later waited stop.
Future prospective command after review: offline Python helper `prepare --runtime
.../runtime-a1 --port 55433`; then app factory via uvicorn on127.0.0.1:8003 and the
new additive ViteF3 config on5174. Commands are proposals, not yet executable.

Avoid elaborate repeated GO rounds: one exact reviewed config/source/input
inventory and root runtime release; preserve failures and stop the affected branch.
Root supplies independent test schema or distinct owner namespaces and controls
all issuer mutation/process/browser actions serially. No blind retries. Bound
provision cooperative target90s, API test target120s, browser target180s and overall active run20min,
with at most10s stop/reap-only cleanup. API query/lock timeouts and root owned
PID/start/data-dir checks remain; limitations are cooperative, not native/OS isolation.
The unchanged account-store connection enforces an actual15,000ms application
statement timeout (lock3,000ms/connect2s); the F3 DSN declares that same value.
Preparation checks its90s target at child starts and completion; SQL phases are
subject to native per-statement caps and root supervision, not a hard90s deadline.
Fix prior provision receipt discriminator in THIS new helper using distinct
`schema` type and `product_schema`, preserving F2 original receipts unchanged.

### F3D02 actual compatibility correction

Author PG attempt1 ran one case and failed CREATE with F2_POLICY_DIFFERS; seven
cases were not run. The original F2 artifact validator allows only a portfolio
capital policy, while the approved fixed F3 context deliberately uses the exact
fictional GLOBAL_PRODUCT policy. This supersedes the original metadata-only
description of the F3 addon. The new F3 SQL extends only that predicate: original
native/context equality, synthetic origin and portfolio/root branch remain; the
additional branch accepts only the entire fixed F3 policy object (FULL_NAV,
SYNTHETIC_CANDIDATE, evidence `F3 fictional local trial only`, decision
`f3-fictional:1`, known PRODUCT_ID, null portfolio/account).

Installation verifies the full frozen F2 SQL SHA, derives its original prosrc,
then checks the actual DB function signature, NOLOGIN owner, SECURITY DEFINER,
language, search_path, exact prosrc hash and one predicate occurrence. It replaces
only that predicate; no role/table/grant/financial-method change. The current
failed-attempt runtime can receive the one-time owner-only
`upgrade_guarded_http_policy(conn, schema=...)` after independent review. It saves
original/revised DDL and hashes plus unchanged ACL/owner/config in its returned
receipt; repeat application refuses. Context/source bytes remain unchanged.
This is a correction to the new fictional local profile, not real admission or
full F1 closure. Original sources and failed attempt are preserved under
`backend/author-a1-preserved`; all F2 source/migration bytes remain unchanged.

Contract/ASGI tests cover default app compatibility, full route replacement,
strict opening/op/body, unauthenticated/CSRF/Origin/IDOR, actual CREATE/ledger/CSV,
same-body retry/conflict, READ/report/export gates, raw archive SHA and actual
REPRODUCED, current withdrawal/finite expiry, actual typed refusal whole rollback,
and UNKNOWN/no fake success or generic-error rollback claims. Use actual fresh PG
and actual financial service, not mock commit success. Unit tests may target exact
transport encoding/error classification; they do not substitute for actual PG.
Existing F2 green42 is not repeated without a relevant changed failure concern.
Independent20 semantic oracles were frozen before implementation; reviewer writes
and executes independent cases. Browser E2E uses only newly invented synthetic
inputs/files and cold temporary browser state; test login isolation, create→ledger
→CSV→replay→archive/reproduce, UNKNOWN/reconcile UI, zh/en, narrow width, keyboard
and typed unavailable states. Frontend computes no financial substitute.

Personal trial package contains exact local launch/stop instructions, fictional
sample/date labels, verification checklist and known unsupported features. It is
readiness for user fictional experience, not completed personal acceptance, real
UAT, data/provider permission, fullF1/deployed-writer closure, D3 or HG4 approval.

## 2026-10-22 addendum: CSV R1 install step and the in-repo PostgreSQL runner

- **Mandatory install step.** After the CSV R1 merge (PD-0062 item 1),
  `persistence.guarded_csv_report_store.install_guarded_csv_report(conn, schema=..., executor_role=...)`
  is a required step after `install_guarded_http` for every F3 schema (F2 -> F3 HTTP add-on -> R1). It is run by the
  non-login schema owner, is not a numbered migration and changes no F2 function. `ReportAwareWorkspaceStore` calls
  `gh_csv_report_precheck` on every guarded write, so a schema without R1 fails closed: every guarded write returns
  503 `F3_STORAGE_UNAVAILABLE` (in the HTTP integration module, the first write fails, then a KeyError on the missing
  disposition). This coupling is the reviewed design. An existing, non-disposable F3 database therefore needs the
  installer before the merged code can write to it, but installing it there requires a separate owner decision
  (PD-0062 item 1). Only new or disposable test databases (e.g. the runner below) install it without one. (Wording
  corrected by the main session after review finding M-2, 2026-10-22.)
- **In-repo runner** `tests/product/guarded_pg_runner.py` (not discovered by unittest). Command:
  `uv run --no-cache --no-sync --frozen --offline python tests/product/guarded_pg_runner.py --socket <dir>/.s.PGSQL.<port> --database <db> --admin-user <superuser>`
  (optional `--modules workspace,http,report`; optional env `FINWEB_IT_ADMIN_PASSWORD`).
  It creates one disposable database `finweb_it_guarded_<hex8>` with per-module schemas and non-superuser roles, applies
  the real migrations and installers (workspace: F2; http and report: F2 + HTTP add-on + R1), builds each module's
  CONFIG, runs `test_postgres_guarded_workspace` (24), `test_postgres_guarded_http` (8) and
  `test_postgres_guarded_csv_report` (6), then drops everything it created and verifies nothing with its prefix
  remains. Any skip, failure or cleanup error exits non-zero. The admin role must be a superuser (CREATE ROLE,
  CREATE DATABASE). No restart-dependent test is covered or skipped.
