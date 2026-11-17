# CP7-F3 frontend integration plan

2026-10-20 Asia/Shanghai. Frontend author: `/root/cp7e10_adapter_author`.
Status: SOURCE_ONLY_PROPOSAL; implementation and runtime remain held until the
shared HTTP contract and independent prereview are accepted. This plan is not
runtime approval, a personal trial result, real-data admission or HG4 approval.

## Existing seams and smallest change

The existing four-screen React application remains the product. Guest mode and
the legacy saved server remain the default. An explicitly configured guarded
server replaces the complete saved route set under the same `/api/v1/portfolios`
prefix; the browser must not choose a legacy financial route as a fallback.

Source observations:

- `web/src/App.tsx:62` owns the existing create form, which currently has no
  operation ID or opening-date field. `App.tsx:374` onwards owns session state,
  identity clearing, saved-list access and current revision navigation. Reuse it.
- `web/src/account.ts:29` centralizes same-origin HttpOnly-cookie requests,
  in-memory CSRF, AbortController and identity epochs. The post-JSON identity
  check at line66 is retained for every new response and download.
- `web/src/account.ts:111` creates saved portfolios; lines124-132 dispatch ledger
  and preference commands; lines149-175 dispatch CSV and exports. Those are the
  integration seam, rather than an independent auth client.
- `web/src/LedgerPanel.tsx:117` and `CsvPanel.tsx:45` already maintain uncommitted
  proposals, stable operation IDs for unchanged manual retries, explicit commit
  confirmation and historical read-only views. `PreferencesPanel.tsx:16` uses
  the same stable-command pattern. Keep these forms and their domain rules.
- `web/src/workspace.ts:118` and `csv.ts:118` reject wrong-scope payloads.
  Existing Snapshot/Workspace/Csv readers remain responsible for exact financial
  strings and preview/persisted distinctions after the new envelope is checked.
- `web/src/AnalyticsPanel.tsx:44` automatically requests PERFORMANCE_WINDOW/RISK
  summaries; `App.tsx` also opens old packet evidence/reproduction. Guarded mode
  explicitly renders localized unavailability for these unsupported paths.
  Actual CP5 snapshot facts/insights may remain visible behind current READ, but
  no old packet request or unsupported model computation is silently dispatched.

## Shared contract alignment

Backend author `/root/cp7e10_protocol_author` owns the exact wire table and route
lease enforcement. The agreed direction below is conditional on its final keys,
limits, status codes and tests; the client will not invent missing server facts.

1. Existing auth/session adds an optional strict `guarded_profile` capability.
   Absence keeps existing behavior. A recognized profile enables only its issued
   operations, fixed fictional source/as-of, opening-date constraints and archive
   controls. Malformed or unknown profile metadata disables guarded actions.
   Capability presentation is not a browser-supplied permission grant.
2. Guarded creation adds a canonical operation UUID and explicit `opening_date`
   to the familiar fictional inputs. Show opening facts separately from valuation
   as-of. Recommend Jan1 opening and Jan2 valuation for the shipped fictional
   source; use only server-issued date bounds, never relabel source dates or
   silently repair a refused input. Legacy create sends its original body.
3. Committed writes use `finweb.guarded_http/1`, disposition COMMITTED,
   portfolio/operation binding, `synthetic:true`, response/issued SHA and archive
   links. Normative `response_json` is the exact actual F2 stored UTF-8 response
   JSON string. Hash those bytes with WebCrypto, parse and bind them, then pass
   the result to the existing appropriate reader. Any convenience `response`
   object is not the rendered authority. No optimistic ledger, NAV or report is
   synthesized in JavaScript. A numeric value is always an issued exact string.
4. HTTP202 UNKNOWN has only the contract's root/operation metadata and no staged
   response, issued result, financial number or claimed zero-write outcome.
   REFUSED retains the typed server code and actual refusal evidence; it is not
   parsed as a successful Snapshot/Workspace/Csv result. Invalid envelopes fail
   closed and suppress new financial output.
5. Pure current reads retain their existing payload shape plus strict
   `guarded:{schema:'finweb.guarded_read/1',profile:'F3_FICTIONAL_CP5',portfolio_id,
   revision_id,operation_id,context_id,generation,issued_sha256,
   archived_response_sha256,archive_url}` provenance. Saved-list entries and
   workspace identify the archive operation for their selected revision. Bind
   current resource/revision metadata before existing readers. The server
   independently leases every read/export route; browser controls never replace
   that check. Metadata resolution must not read financial bodies before its lease.
   Current READ generation and original archived issuance generation are distinct:
   a current g2 lease may read a g1 artifact. Validate each binding in its own role
   without incorrectly requiring those generation numbers to be equal.
6. Guarded archive read/export/reproduce and operation reconciliation are distinct
   fixed methods. Reading an archive must not call compute/reproduce implicitly.
   Reproduce success requires the explicit REPRODUCED state and exact expected
   artifact/hash bindings. REFUSED, INPUT_MISMATCH and RESULT_DIFFERS stay visible.
   Fixed routes are GET `/portfolios/{root}/operations/{op}`, GET its `/export`,
   POST its `/reproduce` with `{}`, and GET its `/reconcile`. Archives preserve
   exact `issued_json`, `response_json` and `envelope_json` strings plus their
   digests. Browser SHA-256 checks the exact UTF-8 strings before parsing; no
   Python canonical serializer is reimplemented in JavaScript. COMMITTED supplies
   normative `response_json`; `issued_json` need only be fetched on archive read,
   avoiding duplicated full artifacts on ordinary mutations. Reconciliation
   returns the same committed envelope or202 UNKNOWN. Unsupported historical
   analytics/packets receive fixed503 `F3_GUARDED_UNSUPPORTED` without old fallback.
   The backend's proposed complete HTTP output cap is20MB; freeze its exact byte
   definition with the contract. Enforce the cap before JSON parsing where the
   fetch stream permits, and refuse the whole oversized output without financial
   truncation. Existing narrower input/file/report caps remain applicable.

Before product edits, align the exact profile schema, read provenance, archive
list/link shapes, reconciliation response, HTTP refusal envelope, request/output
caps and identity-bound export headers with the backend contract. Required UI
knowledge is semantic metadata only; no context object, connection, selector,
permission snapshot or arbitrary callback is sent to the server.

## Operation lifetime and usable recovery

Create obtains its UUID once for an exact submitted body. Ledger, CSV and
preferences retain their existing operation UUID and expected revision during
unchanged preview/confirmation/manual retry. No automatic mutation retry is
introduced. A proposal edit invalidates its preview and requires a new explicit
proposal; an unresolved UNKNOWN operation remains separately identifiable.

Show COMMITTED only after the server-issued committed envelope validates. On a
transport failure after submission, explain that the outcome is uncertain and
retain the same operation/body in memory. Expose explicit same-operation retry
and reconcile actions; do not substitute a fresh UUID or claim rollback. UNKNOWN
reconciliation remains UNKNOWN until the server confirms an archived committed
bundle; absence is not proof of no write. Recovered create/ledger/CSV results
follow the same normal typed result handler and refresh the owned list/head.

Keep one clear operation-status area with root/operation references and a small
current archive panel in Portfolio. Archive read, JSON export and reproduction
are separately labelled controls. Export uses the authenticated current endpoint,
validated resource/hash/content headers and existing safe local download pattern.
Technical hashes and provenance are expandable evidence, not a replacement for
plain outcome text. A reload loses in-memory drafts; disclose that limit rather
than storing credentials, private portfolios, raw CSV or pending financial bodies
in local/session storage. Saved owned operation/archive discovery must come from
the server's final contract, not inferred names or identities.

Identity/session/CSRF loss clears guarded capability, displayed artifacts,
pending operations, confirmations and file state along with the existing saved
workspace. Late decoded responses and downloads are ignored after identity,
selected-root/revision or view epochs change. Same-origin tab invalidation remains.
Recheck those epochs after every asynchronous WebCrypto digest as well as fetch,
body decoding and download preparation; a successful hash cannot publish stale
private data into a later identity or selected view.

## Proposed exact frontend paths

Only the following product paths are proposed, pending final contract release:

| Path | Change |
| --- | --- |
| `web/src/guarded.ts` (new) | Strict capability/envelope/archive/reconcile readers, immutable operation transport types and binding checks; no finance computation. |
| `web/src/guarded-i18n.ts` (new) | English/Chinese outcome, date, permission, archive and uncertainty text. |
| `web/src/GuardedArchivePanel.tsx` (new) | Current owned operation/archive read/export/reproduce and manual reconcile controls; native semantic elements. |
| `web/src/guarded.test.ts` (new) | Parser, binding, disposition, operation-lifetime and identity-cancellation cases using invented transport fixtures. |
| `web/e2e/guarded-flow.spec.ts` (new) | Actual new loopback API/browser flow and transport-only loss/delay injection. |
| `web/vite.f3.config.ts` (new) | Fixed isolated loopback5174, strict port, proxy only `/api` to8003, `envDir:false`; preserve the legacy Vite config. |
| `web/src/account.ts` | Reuse existing authenticated request boundary; opt-in profile and fixed guarded methods; unwrap only validated commits. |
| `web/src/App.tsx` | Existing create form opening date/stable ID, capability lifetime, outcome/recovery and archive surface; explicitly unavailable old analytics/packets in guarded mode. |
| `web/src/LedgerPanel.tsx` | Existing preview/commit form obtains typed guarded recovery metadata without changing domain input semantics. |
| `web/src/CsvPanel.tsx` | Preserve parse/map/preview/report workflow and exact proposal on uncertain commit; integrate recovered report/head. |
| `web/src/PreferencesPanel.tsx` | Preserve exact preferences command and explicit manual outcome handling. |
| `web/src/i18n.ts` | Merge additive guarded translations into both languages. |
| `web/src/styles.css` | Small responsive/long-hash/status-control additions only if existing rules are insufficient. |
| `web/README.md` | Document opt-in local profile, actual commands supplied by root, fictional trial flow and known limits. |

`AccountPanel`, old clients/readers/tests, existing E2E assertions and package
tooling stay intact unless the final concrete contract demonstrates a necessary
small change. Any such addition is proposed explicitly before editing. The
implementation plan itself is this newly authorized Markdown path. Scratch is
restricted to `/private/tmp/finweb-cp7f3-20261020/frontend/`.

## Focused validation

Author unit coverage after code release:

- Legacy capability absence and request bytes unchanged; unknown profiles closed.
- Strict COMMITTED root/operation/response/hash/synthetic/persisted bindings and
  existing exact-string readers; foreign/reordered/absent metadata refuses.
- UNKNOWN/REFUSED cannot carry/display successful financial payloads; malformed
  2xx and non-JSON errors never become committed state.
- Unchanged explicit retry preserves UUID/body/head; no hidden retry on network,
  202,409,422 or quota refusal. An edited proposal cannot reuse stale confirmation.
- Required opening date, server bounds and separately labelled source-asof;
  legacy creation remains unchanged. Server remains authoritative for chronology.
- Archive read does not reproduce; export headers and artifact identities match;
  reproduction requires explicit state plus exact hashes, never object truthiness.
- Logout/session/CSRF/root/revision changes suppress late JSON, reconciliation
  and downloads and clear pending artifacts. EN/Chinese keys remain complete.

One bounded new actual Playwright flow should cover create with explicit opening
date -> ledger rollback preview/commit -> explicit CSV header/map/preview/commit
-> exact operation replay -> archive read/export/reproduce -> reload and owned
reopen. Use genuine API response strings for UI comparisons. Retain independent
numerical expectations from the existing service/core contracts separately.
Inject only network loss/delay around actual responses for UNKNOWN recovery;
do not mock financial output. Include a second disposable identity for canonical
foreign-ID refusal and session clearing, bilingual 390px rendering, keyboard-only
reachability/activation, focus recovery and no private web storage. Existing guest
and saved-flow regression selection is based on actual touched seams and must
exercise the legacy-default server separately from the new guarded profile.

Typecheck, focused Vitest, build and actual browser/API checks run only after the
root releases reviewed sources/runtime. Root coordinates DB/API/frontend/browser
serially. Browser output stores screenshots/download bytes and scrubbed result
metadata, never cookie/CSRF/password traces. Independent review uses separate
oracles and execution; author source/unit success is not independent acceptance.

## Installed tooling observed without execution

- `web/package.json` requires Node>=26 and pins React19.3.1, TypeScript7.0.2,
  Vite8.3.4, Vitest5.0.5 and Playwright1.64.1. Existing scripts are typecheck,
  test, build and test:e2e. No install or package/lock/config change is proposed.
- `/opt/homebrew/bin/node` currently resolves to
  `/opt/homebrew/Cellar/node/26.8.2/bin/node`; npm/npx resolve to the installed
  Homebrew npm CLI. These are path observations, not a newly executed version test.
- `web/node_modules/.bin/{playwright,vite,vitest,tsc}` and
  `@playwright/test/package.json` exist. The installed package declares1.64.1.
- Existing `web/playwright.config.ts` uses the loopback5173 default, serial
  execution and `FINWEB_CHROMIUM_EXECUTABLE_PATH`; no server or download setup.
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` exists and was
  used by historical E3 focus harnesses. The default Playwright cache currently
  contains only `.links`, so do not assume a cached Playwright browser exists.
- Legacy Vite remains loopback5173 with proxy8000. Root selected the new F3 API
  `127.0.0.1:8003`, UI `127.0.0.1:5174` and private PG Unix port55433/TCPoff.
  New `vite.f3.config.ts` uses `envDir:false` (the installed Vite type explicitly
  accepts `string|false`), fixedhost/strictport and fixedproxy; no `.env` load.
  Root owns starts/stops, preserves old servers and serializes the browser.
  Existing Playwright configuration can receive the explicit new baseURL and
  installed executable from root; a second Playwright config is unnecessary.
  Use a temporary browser context/profile and restrict test requests to the new
  owned loopback origins. Never attach an existing personal browser profile.
  No executable, app, browser or server was started during this source inventory.

## Personal fictional trial readiness

After actual API/UI/E2E and independent review, provide a short local startup
guide, the shipped fictional examples, recommended opening/valuation dates,
manual retry/reconcile exercise, archive/export/reproduce checklist, logout/data
isolation steps and known unsupported analytics. Report actual tested browsers,
ports and resource limits rather than promises. User trial feedback and owner
acceptance remain separate. Real data/personal file access, external services,
installs, commits, deployment, source qualification, HG4 and night automation
retain their existing restrictions.
