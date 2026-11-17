# CP7-E technical plan — E1 gate only

2026-10-19. **PROPOSED; root + independent freeze required before product edits.**
[PD-0046](../decisions/product/PD-0046-cp7e-real-source-web-integration-and-scoped-data-checks.md)
authorizes CP7-E. Root has selected this smaller first milestone: authenticated
metadata capabilities and strict no-write creation refusal. E1 is not E completion,
real UAT, source admission or HG4 acceptance. No PG/runtime action follows this draft.

## 1. Fixed boundary

Current independent metadata preflight has no verified/admitted real release,
AV adjustment UNDECLARED/coverage empty and no established F8-B role mapping.
The separate quote/calendar integrity report does not establish qualified financial
inputs, identity or a runnable real service. Neither report is runtime configuration.

E1 has **no qualified/eligible/ready success path**. Empty server configuration is
normally blocked; a valid descriptor is only CONFIGURED_NOT_VERIFIED/METADATA_ONLY.
It never reads payloads, builds a release, calls financial services, creates storage
or registers an operation. No0020, financial result, placeholder store/compute route,
real portfolio form, synthetic fallback or automatic task is installed.

## 2. Proposed paths and functions

- New `src/web_api/real_source_contexts.py`: immutable server-only descriptor,
  bounded metadata inspection and safe public capability object.
- New `src/web_api/real_requests.py`: strict E1 source/intent envelope parser.
- New `src/web_api/real_routes.py`: exactly the two endpoints below.
- New `tests/product/test_web_real_source_gate.py`; separate new actual-PG gate
  test module only after root grants its serialized slot.
- **Only old-source integration exception:** at the end of `account_routes`' existing
  installer, import/install the new router, injecting the existing `authenticated`
  and `database` callbacks. No old route/auth/body/response is changed. Record this
  exact source delta; do not claim old D53 source hashes all remain unchanged after it.

```text
ConfiguredSourceDescriptor(context_id, declared_release_id,
                           declared_source_ids, metadata_files)
MetadataFile(relative_path, expected_sha256, role)
validate_descriptor(value) -> immutable descriptor
inspect_configured_metadata(root, descriptor, allowed_metadata_files)
real_capabilities(provider) -> new E1 schema
parse_create_gate(raw_json_bytes) -> RealPortfolioGateRequest
refuse_create_gate(provider, request) -> always raises E1 refusal
install_real_source_routes(app, *, authenticated, database, provider=None)
```

Default provider has zero descriptors and performs zero filesystem reads. No
FileStore/read_release/adapter/builder, world, financial engine/service, store or
DB connection is injected. E1 reuses auth callbacks, not a copied authentication
implementation; only the existing session lookup may issue SQL. No auth counter,
session or financial row is mutated by either endpoint. Existing disabled account
mode remains disabled; there is no launcher/auth enablement change.

## 3. GET `/api/v1/real-source-contexts`

Authenticate first, then reject **any** query key (including duplicates) with422
INVALID_REQUEST. Next iterate `request.stream()` and reject the first nonempty
chunk with422 INVALID_REQUEST; never call unbounded `request.body()` or silently
ignore a GET body. Only an exhausted empty stream may reach the provider. No query
or body value is reflected in errors. New exact default success:

```json
{
  "schema_version":"finweb.cp7.real_source/1",
  "milestone":"E1_GATE_ONLY",
  "mode":"LOCAL_REAL_SOURCE_TEST_ACCOUNT",
  "state":"BLOCKED",
  "readiness_stage":"METADATA_ONLY",
  "provenance":{
    "ledger_origin":"PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED",
    "market_origin":"REAL_SOURCE_REQUESTED_NOT_QUALIFIED",
    "personal_holdings":false
  },
  "capabilities":{
    "source_metadata":true,"payload_verification":false,"source_qualification":false,
    "create":false,"saved":false,"workspace":false,"analytics":false,
    "imports":false,"exports":false,"evidence":false
  },
  "approved_context_count":0,
  "contexts":[],
  "blockers":["NO_APPROVED_REAL_SOURCE_CONTEXT",
              "REAL_PORTFOLIO_STORAGE_NOT_IMPLEMENTED","REAL_ANALYTICS_NOT_IMPLEMENTED"],
  "limits":{"http_bytes":32768,"output_bytes":65536},
  "scope":{"markets":["US"],"reporting_currencies":["USD"]},
  "support":{"data_action":"EXISTING_REGISTERED_PROJECT_METADATA_ONLY",
             "download_or_admission":false,"real_uat_verified":false,"hg4_approved":false}
}
```

A valid configured descriptor may add only this context shape:

```text
{context_id:lowercase64hex, configuration_digest:lowercase64hex,
 declared_release_id:lowercase64hex,
 declared_source_ids:1..6 unique sorted strings matching [a-z0-9][a-z0-9_.:-]{0,63},
 status:CONFIGURED_NOT_VERIFIED, readiness_stage:METADATA_ONLY,
 metadata_integrity:EXPECTED_METADATA_BYTES_MATCHED,
 payload_integrity:NOT_VERIFIED, financially_qualified:false}
```

All financial caps remain false and approved_context_count=0 even then. No assumed
release existence, quote coverage/freshness, local paths, owner checked_by, private
configuration, raw terms/rows/exceptions or authentication material is exposed.
No old `/capabilities`, Snapshot, Workspace or D analytics schema is widened.
Contexts are unique and sorted by context_id; an empty contexts list is valid.

## 4. POST `/api/v1/real-portfolios`

This is a strict **intent gate**, not an implemented financial constructor. Exact
required fields; no defaults/coercion/extra keys:

```text
operation_id: canonical UUID string
mode: literal LOCAL_REAL_SOURCE_TEST_ACCOUNT
source_context_id: lowercase64hex
expected_configuration_digest: lowercase64hex
release_id: lowercase64hex
as_of: exact YYYY-MM-DD
constructed_ledger_acknowledged: strict Boolean true
```

Reject name/positions/cash/events/payload/path/url/owner_id/registry/quote/timestamp/
permission/approved/contains_synthetic and every other undeclared field. This E1
envelope cannot describe a financial portfolio; E2 must freeze actual inputs later.
Reject missing fields, duplicate JSON keys, non-finite constants and invalid dates,
UUIDs/hashes/bools with422 INVALID_REQUEST and sanitized field-only details.

Use `authenticated(request, mutation=True)` **before** JSON/model/source inspection
for requests within existing transport bounds. A Request-only async route can call
the synchronous callback through the existing Starlette threadpool helper, then
strictly parse raw JSON; no auth reimplementation/dependency install. Existing
middleware Host/Origin/content-type/body-size refusals still precede route auth.

| Condition after auth + strict parsing | E1 refusal |
|---|---|
| No matching configured context, including empty default |409 REAL_SOURCE_NOT_CONFIGURED; no unrelated descriptor I/O|
| Matching descriptor is invalid or its metadata missing/corrupt/disallowed |503 REAL_SOURCE_CONFIGURATION_UNAVAILABLE|
| Metadata valid but expected configuration digest or declared release differs |409 REAL_SOURCE_CONFIGURATION_DIFFERS; never combine contextA with digest/releaseB|
| Matching declaration/metadata |409 REAL_PORTFOLIO_CREATION_DISABLED; still not qualified, storage/compute absent|

No201, portfolio/account/id/artifact response, operation reservation, retry cache,
capacity consumption or financial write. Same or changed retries are still refusals.
E1 errors: `{schema_version:"finweb.cp7.real_source/1",error:{code,detail,kind}}`,
kind REQUEST/CONFIGURATION/CAPABILITY. No forged MetricResult/state for capability
errors. Existing auth/transport401/403/503 envelopes stay unchanged. All responses
retain no-store/nosniff; no raw caller values or private errors are reflected.

## 5. Metadata guard and limits

Descriptors are injected only by trusted server configuration/tests, never browser
content. Exact descriptor fields exclude an approval/permission switch. Separate
server allowlist binds project-relative metadata path, expected byte SHA and fixed
role (registry/release declaration/payload-manifest metadata). Check allowlist and
resolved project containment before stat/read; reject absolute/traversal/symlink
escape. No glob, recursive discovery, environment root override, URL or following
a manifest's adjacent payload. No payload hash read, parsing or service call in E1.

Exact role enum: **SOURCE_REGISTRY / RELEASE_DECLARATION / FILE_MANIFEST**. A
configured descriptor has1 SOURCE_REGISTRY,1 RELEASE_DECLARATION and1..6 FILE_MANIFEST
entries (3..8 total), distinct metadata paths, and1..6 declared_source_ids using the
public pattern/order above. Empty descriptor configuration is normal; a configured
descriptor with empty sources/files is503. `{}` can never match a metadata role.
All JSON objects below reject extra keys and duplicate keys at every depth before
using any existing pure parser; strict types reject booleans as integers and reject
coercion/non-finite numbers. Required means present even where null/empty is allowed:

| Role | Exact JSON field set / types and minimum cross-references |
|---|---|
| SOURCE_REGISTRY | Top-level exactly `{sources:[record...]}`, nonempty, unique source_id. Each record requires source_id/name/upstream_provider/independence_group (nonblank strings), terms_url (string or null), synthetic (bool), terms_check (null or exact `{checked_by:nonblank string,checked_on:ISO date,permits_internal_development_use:bool,notes:string}`); only additional allowed field is source_priority (positive strict int). Use SourceRegistry.from_json only after this strict envelope check. Every descriptor-declared source must exist, have synthetic=false and an explicit nonnull terms_check with permits_internal_development_use=true. This is metadata attestation, not new rights verification or financial qualification. |
| RELEASE_DECLARATION | Exactly the8 fields emitted by MarketDataRelease.to_json: schema/name/files/source_precedence/conventions/created_for/convention_set_id/release_id. schema literal finweb.marketdata.release/1; nonblank name/convention_set_id; created_for string; files nonempty sorted unique64hex array; source_precedence nonempty unique source-id array; conventions sorted unique string-pair arrays; release_id64hex. Existing pure from_json verifies content digest (never from_manifests/build). release_id must equal descriptor.declared_release_id; source_precedence's set must equal descriptor.declared_source_ids. |
| FILE_MANIFEST | Exactly FileManifest.to_obj's20 required fields: schema,file_sha256,size_bytes,payload_filename,payload_format,source_id,data_kind,market,retrieval_time,retrieved_by,request,declared_adjustment,adjustment_anchor,declared_currency,declared_delay,source_identifiers,script,libraries,usage_scope,coverage. schema literal finweb.marketdata.file_manifest/1; hashes64hex; size strict nonnegative int; strings/enums/date/null/string-pair arrays checked against existing FileManifest contract before pure from_json. script exactly `{name:string|null,version:string|null,script_sha256:64hex|null}`. No default fields are reconstructed. E1 permits only QUOTE/CALENDAR metadata, retrieved_by=human, INTERNAL_DEVELOPMENT_ONLY, declared source attested above; QUOTE market=US/currency=USD, CALENDAR market null/US and currency null/USD. UNDECLARED adjustment/empty coverage stay declarations, never become RAW/verified coverage. Require safe basename payload_filename but never open it. |

Across the complete descriptor, FILE_MANIFEST payload hashes must be distinct and
their set exactly equal release.files; manifest source-id set must equal declared
source ids. Reject missing/extra release members or source references. Thus only
expected metadata bytes **and** complete schema/cross-reference success can produce
EXPECTED_METADATA_BYTES_MATCHED; it still does not qualify payloads or services.

Bound bytes, verify SHA against trusted expected bytes, parse strict UTF-8/JSON and
applicable metadata schemas; validate source identity/attestation/references without
turning that into financial qualification. Never trust JSON approved=true,
contains_synthetic=false, a self-consistent checksum, stat size or filename as
qualification. Reverify the requested metadata on every call; no cached ready/digest
survives changed SOURCES rights or manifest bytes. mtime/check/retrieval time is not
market-data freshness. One configured broken descriptor makes GET503, not an empty
normal list. No descriptor means normal blocked GET200 and POST409, not503.

Bounds:16 descriptors;8 metadata files/descriptor;65536 bytes/file;1048576 aggregate
metadata bytes/request;65536 UTF-8 response bytes; existing32768 HTTP bytes. Reject
whole oversized work before unbounded loops; do not truncate metadata/output.

## 6. Verification contract — all NOT RUN at plan drafting

| Layer | Required evidence after implementation GO |
|---|---|
| Strict request | Exact field set/types/date/hash/UUID; duplicate keys/non-finite values and body injection rejected; no raw error reflection. |
| Provider | Default zero I/O; configured valid remains METADATA_ONLY/zero approved/all financial capsfalse; no JSON flag enables finance. |
| Guards/spies | FileStore/read_release/adapter/builder/payload/financial service never called. Generated temp metadata verifies role/cardinality/exact nested fields/crossrefs, `{}`/self-approval refusal, allowlist/root/SHA/bounds, missing/corrupt distinctions, changed rights/manifest/cache, no payload open. |
| Auth/CSRF | Existing session dependency; guest401, invalid/missing/duplicate Origin/CSRF403; configured poison not read first; account disabled/storage503 retained. |
| Routes | GET auth precedes query and first-nonempty streamed-body422; no unbounded body read/provider call on refusal. Exact blocked GET, configured-error503 and four POST refusals; contextA+digest/releaseB409; repeats no registration/write. Public paths/private checked_by/config/errors absent. |
| Actual PG + in-process ASGI | Fresh authorized19-migration schema, no0020. Setup writes separately attributed; trace/count entities/financial/ledger/revisions/selection/CSV before/after E1 calls/failures; only auth sessionSELECT expected. No actual runtime claim until slot granted. |
| Compatibility | Existing synthetic save/reload/preview/correction/oldproof reproduction still work; existing route bytes unchanged. Early architecture tests plus appropriate affected/full actual checks after grant. |
| Independent runtime/design | Root serializes PG/API/browser/processes. Own blocked EN/zh Quick/Simple/Professional, disabled/no financial requests, error recovery/logout/identity clearing; not positive real UAT. |
| Preservation | E entry458 source/1145 old evidence; new files + exact account_routes hook recorded. Old53 source has this approved exception, not a false all-identical claim. SealedD347, all old19SQL/CHECKSUMS, financial/domain/method/fixture/catalog/dependencies untouched. |

E2 separately reviews immutable real root/revisions/artifacts, true create/manual/
CSV inputs and gated compute/reproduce after genuinely qualified material. E1
does not install those endpoints, empty placeholder services, schema20 or a real
renderer. Frontend uses a new strict readiness reader, refuses permissive/eligible
payloads and leaves every financial control disabled with zero requests. Existing
FULL_NAV/US-only/SPY-route/stack/depth decisions stand; no OCR/CP8/9, data admission,
download, model/dependency, automation restart, deployment or owner gate follows.
