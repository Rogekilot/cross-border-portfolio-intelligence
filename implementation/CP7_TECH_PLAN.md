# CP7 technical plan — local synthetic guest slice

Authority: PD-0042 (2026-10-19), retained PD-0041 conditions, PRD §7.1,
§21 and CP7. This increment starts CP7; it does not complete CP7.

## Shared HTTP contract, `finweb.cp7/1`

All routes are under `/api/v1`. Requests/responses are JSON. Financial numbers
are exact decimal or rational **strings**, never JSON floating-point values.
Only the explicit `LOCAL_SYNTHETIC_GUEST` route exists in this increment.
As-of is fixed to `2026-01-02`; admitted demo symbols are `SYN-A` (USD 100) and
`SYN-B` (USD 50). These are fictional securities, not aliases of real tickers.
Their raw inputs are versioned under `src/web_api/fixtures/`.

`GET /capabilities` returns `{schema_version,mode,synthetic,as_of,
reporting_currencies:[{code,available,reason}],listings:[{symbol,listing_id,name,
currency}],defaults:{name,reporting_currency,positions,cash,
synthetic_acknowledged},limitations}`. USD is available; CNY is disabled with
`FX_PATH_UNAVAILABLE`. The form reads these authoritative supported inputs and
defaults. A CNY POST is also explicitly refused with that code (HTTP 422).

1. `POST /guest-sessions` body `{"mode":"LOCAL_SYNTHETIC_GUEST"}` returns
   `{schema_version, session_token, mode, limitations}`. The random capability
   is returned once and is supplied as `X-Finweb-Session` thereafter; keep it
   in memory, never a URL. Guest state expires after one hour or process exit.
2. `POST /guest-portfolios` accepts
   `{"name":"My synthetic demo","reporting_currency":"USD","positions":[{"symbol":"SYN-A","quantity":"10"}],"cash":"500","synthetic_acknowledged":true}`.
   Name is 1–80 characters, at most two distinct demo symbols, quantity in
   `(0,1000000]`, cash in `[0,1000000000]`, at most six decimal places, no exponent
   notation. Empty positions are permitted only with positive cash. Unknown
   fields, real symbols, unacknowledged synthetic mode, other currencies and
   JSON numeric inputs are rejected. Creates an ephemeral guest portfolio and
   returns the full Snapshot below (HTTP 201).
3. `GET /guest-portfolios/{portfolio_id}` returns the same immutable Snapshot.
4. `GET /guest-portfolios/{portfolio_id}/packets/{insight_id}` returns
   `{schema_version,portfolio_id,synthetic:true,packet,result_digest}`; `packet`
   is the complete CP6 `ProofPacket.to_obj()` without dropping caveats.
5. `POST /guest-portfolios/{portfolio_id}/packets/{insight_id}/reproduce` body
   `{"expected_result_digest":"<64 lowercase hex>"}` reruns CP3/CP5/CP6
   through their existing reproduction path, returning
   `{schema_version,portfolio_id,insight_id,status,detail,expected_result_digest,
   actual_result_digest,synthetic:true}`. A digest mismatch is `RESULT_DIFFERS`,
   never a successful reproduction.

Snapshot fields (all are present):

```
{
  schema_version: "finweb.cp7/1",
  portfolio_id: UUID, name: string,
  mode: "LOCAL_SYNTHETIC_GUEST", synthetic: true, persisted: false,
  reporting_currency: "USD", as_of: "2026-01-02",
  limitations: string[],
  inputs: {positions: [{symbol,quantity}],cash:string},
  valuation: {manifest_id,result_digest,metrics: CP3Metric[]},
  diversification: {manifest_id,result_digest,metrics: CP5Metric[]},
  insights: {manifest_id,result_digest,packets: FullCP6ProofPacket[],diagnostics: object[]},
  provenance: {source_id,input_sha256,calendar_sha256,release_id,synthetic:true}
}
```

CP3Metric is the existing `ComputedMetric.to_canonical_dict()` transport;
CP5Metric is existing `Metric.to_obj()` transport. Decimal/Fraction/date/enum
serialization uses the project's canonical JSON encoder; `null` stays `null`.
Metrics retain state, reason, exact witnesses, source/manifest identities,
freshness, method, exclusions and limitations. The frontend renders these
values and never computes a financial metric or fills an unavailable value.

Refusals use `{schema_version,error:{code,detail,state:"INSUFFICIENT_DATA"}}`.
Expected HTTP statuses: 400 invalid/empty input, 401 absent/expired session,
403 forbidden origin/host, 404 unknown or other-session portfolio/packet,
413 oversized body, 422 schema validation, 429 bounded session capacity,
503 local synthetic route disabled or deterministic source refused.
No existence distinction is exposed across session capabilities.

## Security and local execution boundary

The application factory defaults to synthetic guest mode disabled. Development
launch explicitly enables it. Loopback hosts only, strict configured same-origin
requests (Vite's local development origin is explicitly allowlisted), no CORS
wildcard and no cookie authentication. Mutation requests require JSON and
same-origin browser metadata where present. The capability header protects
session resources; the guest mode is not an account or persistence substitute.
Bodies, sessions and portfolios per session are bounded. Responses are
`Cache-Control: no-store`, and no financial input or capability is logged.

## Implementation boundary

`src/web_api/` provides raw synthetic-input adapter, ephemeral guest repository,
canonical HTTP transport and thin FastAPI routes. Existing CP1 ledger event and
replay, CP3 valuation, approved CP5 capital policy and CP6 source verification
remain the authorities. There are no imports from `tests/`, no expected-output
fixtures loaded, no financial method changes and no genuine-user market path.
Country/sector metadata and total-return coverage are absent; historical risk
statistics involving a security remain explicitly insufficient. Cash-only
`modeled_volatility` may be AVAILABLE with zero under the existing CP5 zero-native-
interest cash convention; its credit/liquidity/default-risk caveat remains visible.
This adapter does not override or upgrade any engine state. No personal policy/benchmark is
invented. Freshness is historical synthetic freshness at the labelled as-of.

## Remaining CP7 increments

Normal accounts/authentication and user isolation, PostgreSQL persistence,
CSV mapping/preview/correction/quarantine/import/export, broader real-source
selection and complete core views remain later increments. First-slice tests and
independent review do not waive HG4 real-data usability or any later gate.

## Actual engineering validation — first candidate

Executed with the approved FastAPI/Uvicorn installation present:

```
PYTHONDONTWRITEBYTECODE=1 uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_web_api -q
```

Observed **13 tests passed, 1.979 seconds**. The tests exercise the actual ASGI
application using only stdlib HTTP message driving, actual CP1 opening ledger
events and CP3/CP5/CP6 services. They cover raw-input NAV/concentration arithmetic,
exact fractional transport, genuinely insufficient security history and LIMITED
unknown classification, cash-only behavior, full packet opening/reproduction and
wrong/missing expected digests, cross-session resource/packet isolation,
expiry/capacity, schema/precision bounds, explicit synthetic acknowledgment,
unsupported currencies, disabled guest mode, origin/JSON/body limits and canonical
host refusals. They do not simulate green answers from a mock financial engine.

Independent preflight reported malformed Host authority handling. Its concrete
counterexamples were first reproduced red: `[broken` raised ValueError and seven
other malformed authorities were accepted. Whole-authority/port/duplicate-Host
validation now rejects them with canonical 403 before source access. The focused
suite then passed. An initial test used title-case `Observation`; the issued CP6
enum is `OBSERVATION`, so that test expectation was corrected without changing
engine output or severity logic.

No database, account authentication, persistence, import/export or real-source
claim was tested or delivered by this candidate. Browser verification and
independent implementation review are root-owned follow-ups; this is the
engineer's actual test evidence, not an independent acceptance verdict.
