# CP7-D — additive owned analytics transport

2026-10-19. IN_PROGRESS under PD-0045 after CP7-C acceptance/sealing. D validation
contract: reviews/CP7_D_VALIDATION_PLAN.md. The441-source/745-prior-evidence entry
inventory is immutable. No migration/dependency/method/source/catalog change.

## Preserved boundary and source identity

Do not change SyntheticWorld.create or old snapshot/report/packet serialization.
New account-only analytics are computed read-only on demand from an explicitly
owned revision. Guest analytics are not added. Old ledger/selection/as_of and
historically visible accounts are loaded before engine work. The cached world
must also match the two current on-disk raw fixture hashes on each request.
Required catalog providers load lazily after ownership, never default to empty on
damage; unrelated performance families never read risk catalogs. No head fallback.

The explicitly fictional seam invokes existing pure engines with suppressions=()
and detection=CALLER_SUPPLIED. No fabricated F8-B feed/filing policy, synthetic
USER-service override, real-data route, new insight/Warning or personal policy.
Resource refusal is a transport error, never a fabricated financial metric.

## Final wire contract v1

Three authenticated POST routes under `/api/v1/portfolios/{portfolio_id}/analytics/`:
`evaluate`, `evidence`, `reproduce`. Existing Origin/CSRF is mandatory. JSON is
canonical, no-store/nosniff;32KiB request cap remains. No external HTTP/provider.

Evaluate body has exactly:

```
{
 "revision_id":"UUID", "as_of":"YYYY-MM-DD",
 "family":"PERFORMANCE_WINDOW|GAINS|ATTRIBUTION|RISK",
 "window":{"rule":"TRAILING_MONTHS|YTD|SINCE_INCEPTION|CUSTOM|MAX_AVAILABLE",
           "months":null,"base":null},
 "frequency":null,
 "scope":{"kind":"PORTFOLIO|ACCOUNT","account_id":null},
 "view":"REQUESTED|DEFAULT", "synthetic_acknowledged":true
}
```

UUIDs and ISO dates are canonical strings. All fields above, including nullable
ones, are required. TRAILING_MONTHS uses1/3/6/12/36/60 and base=null; CUSTOM uses
base and months=null; other rules require both null. MAX_AVAILABLE and DEFAULT
are RISK-only. RISK frequency is DAILY/WEEKLY/MONTHLY, other families require null.
DEFAULT requires TRAILING_MONTHS36. PORTFOLIO requires null account; ACCOUNT needs
an owned account visible at that revision. as_of must equal the revision's date.

Evaluate response has exactly:

```
{
 "schema_version":"finweb.cp7.analytics/1",
 "portfolio_id":"UUID","revision_id":"UUID","persisted":false,"synthetic":true,
 "question":<normalized body>,
 "revision":{"as_of":"ISO","ledger_version":123,"selection_version":0,
              "reporting_currency":"USD"},
 "results":[{"result_id":"FAMILY:GROUP:manifest_id:result_digest",
   "family":"...","group":"PERFORMANCE|INDEPENDENT|BENCHMARK",
   "binding":<below>,"binding_digest":"SHA",
   "engine_result":<unchanged canonical engine result>,"definitions":[<registry entries>]}],
 "views":[{"metric_id":"...","metric_index":0,"fallback":false,
   "shown_result_id":"...","refused_result_id":null,"refused_metric_index":null,
   "composition":null}],
 "limits":{"calculation_days":3660,"output_bytes":2000000,"http_bytes":32768},
 "limitations":[<explicit fictional/source/method limitations>]
}
```

Binding exact keys: portfolio_id,revision_id,ledger_version,as_of,scope,
reporting_currency,family,group,question_digest,release_id,input_sha256,
calendar_sha256,fixture_as_of,engine_id,selection_pin,benchmark_catalog,
risk_free_catalog,registry,conventions. Catalog fields are null or
`{id,digest}`; registry likewise. Nullable dependency fields mean not consumed.
Populate these from the actual manifest; common revision.selection_version does
not mean every group consumed selection. definitions are existing resolved
methodology entries (performance/risk), not new thresholds or financial values.

Performance engine_result is ComputationResult.to_canonical_dict; RISK is
RiskResult.to_canonical_dict. They keep distinct manifests and metric shapes,
all exact/radical/zero/null/rounding/partial/excluded/freshness/count/reason fields.
views selects a metric by result_id plus metric_index: CP3 metric_id alone is not
unique across subjects/views. Requested view maps every metric; DEFAULT maps
approved DefaultView shown/refused X/Y with original composition.evidence.

Evidence/reproduce body has exactly:

```
{"question":<same full evaluate body>,"result_id":"...",
 "expected_binding_digest":"SHA","expected_manifest_id":"SHA",
 "expected_result_digest":"SHA"}
```

Evidence response: schema_version,portfolio_id,revision_id,question,result (one
exact result wrapper),ledger_reference,limits. ledger_reference is
`{portfolio_id,revision_id,ledger_version,workspace_path}` pointing to the existing
owned pinned workspace with canonical events/correction/source links. Full engine
manifest carries consumed-file/source evidence; no CP5 packet substitution.

Reproduce response: schema_version,portfolio_id,revision_id,family,group,result_id,
binding_digest,expected_manifest_id,expected_result_digest,status,detail,
rerun_manifest_id,rerun_result_digest,limits. Route resolves result identity and
binding, then invokes the existing family's typed reproducer with its trusted
manifest and pinned inputs. A valid result identity with a wrong expected digest
must yield engine RESULT_DIFFERS. Wrong binding/manifest/family/result identity
refuses409 ANALYTICS_BINDING_DIFFERS. No caller metric or manifest is trusted.

New analytics transport errors contain `{schema_version,error:{code,detail,kind}}`
without an invented financial state. kind is REQUEST/BINDING/SOURCE/ENGINE/RESOURCE.
Codes: ANALYTICS_SPAN_LIMIT422, ANALYTICS_OUTPUT_LIMIT422,
ANALYTICS_AS_OF_DIFFERS409, ANALYTICS_BINDING_DIFFERS409,
ANALYTICS_CATALOG_UNAVAILABLE503, ANALYTICS_SOURCE_DIFFERS503,
ANALYTICS_ENGINE_ERROR503, ANALYTICS_REQUEST_REFUSED422. Existing auth/owner/storage
errors retain their existing codes. Strict wire model errors retain normal422.

## Resource/semantic checks

Before old snapshot verification or any new engine loop, guard the inclusive
natural-date span of pinned event/acquisition/settlement/ex dates and requested
base/end, including SINCE_INCEPTION/MAX_AVAILABLE and DEFAULT's X/Y work. At most
3660 natural dates are admitted; do not clamp dates or convert resource refusal
to financial insufficiency. Check complete final canonical UTF-8 output<=2MB.

Risk independent/benchmark results are ordinary separate engine calls. DEFAULT
memoizes identical X/Y group requests only within one evaluation; every shown
claim links to its own result. Empty catalog, absent/clear selection and history
causes may coexist; preserve actual reason priority. On Jan2 I0=E, use actual
WINDOW_NOT_POSITIVE/null count emissions; never manufacture0/NO_FULL_PERIOD.
Known zero basis/value remains0, unknown basis remainsnull; no-sales is not a
zero realized total when its window is refused. No standalone series/chart
endpoint or performance insight adapter. All66 old HG3 gaps remain disclosed.

## Files and verification

New web edge: analytics_requests.py,analytics_context.py,analytics_composer.py,
analytics_routes.py. Only account_routes.py gets minimal installation. New tests:
test_web_analytics.py and test_postgres_web_analytics.py (optional input-only kit).
No persistence/old tests/financial methods/raw fixtures/catalog/dependency edits.
Author actualPG and in-process ASGI tests are authorized in disposable schemas;
shared loopback API/browser/restart access waits for PM. Independent review and
full PM regression remain separate. Append self-validation only after web author
coordinates its shared document use. Hard stop14:30Shanghai.

Independent R2 identity-order extension: before invoking the preserved _record
helper (which decodes initial request JSON), the new context first queries only
owned portfolio metadata and proves the explicit revision exists in that portfolio.
ACCOUNT scope is also proven visible from that raw revision pin/sequence before
source JSON decoding. Missing/foreign revision or scope stays404 even when this
owner's stored request JSON is damaged; a valid owned target still exposes its
typed503 source-integrity failure. No sealed helper or valid-response wire changed.
