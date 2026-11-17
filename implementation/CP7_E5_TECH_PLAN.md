# CP7-E5 — closed real-workspace contract/refusal implementation

2026-10-19. Author `/root/cp7e_context_contract`. Only v1.1 sections1–6.
User authorization continues existing N1 for local implementation, tests and
independent review. All source/personal/dependency/release/gate conditions remain;
no overnight automation is resumed.

## Frozen authority and actual state

- Sealed contract `reviews/CP7_E4_EVIDENCE/contract-v1.1/REAL_INTERFACE_CONTRACT_V1.md`:
  SHA256 `c769a12d581fbfed6e53c97506daaa9c0232c8ebfc5eb668b8ba6c13e22e32ba`.
- Sealed field schema `REAL_INTERFACE_FIELDS_V1.schema.json` in that directory:
  SHA256 `b973dbdad774ee76b0eba6620ae24285b27820b658ddf9944e53d2190c979eb9`.
  Reference only: neither schema nor evidence files are runtime configuration.
- D3 NOT_QUALIFIED, exact raw source allowlist empty, future qualification/rights/
  expiry/commit protocol NOT_CLOSED. No future positive route/type/store/migration
  is installed from sections7–10. No financial method is changed.

## Exact paths

1. New `src/web_api/real_workspace_contract.py`: fixed typed refusal, bounded
   strict preparse, CreateRequest semantics, frozen RAM catalogue, exact public
   blocked/error envelopes. Imports only stdlib and existing canonical encoder.
2. New `src/web_api/real_workspace_routes.py`: Request-only GET
   `/api/v1/real-workspace-contract` and POST `/api/v1/real-workspace-intents`.
   Auth injected from existing account closure. No database/source/service/store
   dependency is injected into the new decision path.
3. Only old product delta: two-line import/install hook at the end of
   `src/web_api/account_routes.py`, after E1 installation. Full preimage saved at
   `/tmp/finweb-cp7e5-20261019/author/account_routes.before.py`, SHA256
   `b213a2531a10375bf093d74c17bb32a13797c448f71b648dcc54085d59474f0c`, matching
   the explicit451 E1/E3/E4 source baseline. Root EntryGO preceded this edit.
4. New `tests/product/test_web_real_workspace_contract.py`: isolated fixed module,
   generated request/RAM data, existing synthetic compatibility. Existing tests
   are untouched. No discover/full-suite permission follows.
5. This plan. No other source, front end, financial/method/fixture/SQL/dependency
   or sealed evidence change is intended.

## Semantics

Existing LocalBoundary retains Host/Origin/site and mutation content-type/actual
32768-byte precedence. Existing account authentication then checks configured/
HTTPS/session and POST CSRF; its current session SELECT is the explicit exception
to no new I/O. No claim that all login/logout/rate operations are side-effect-free.
New handlers call authentication before query/body semantics or RAM validation.

GET rejects any query and first nonempty stream chunk; empty streams are exhausted.
POST accumulates no more than32768 bytes even independently of middleware, then
scans container depth≤8 and each decoded token≤4096 UTF-8 bytes before constructing
a container tree. String-token decoding is bounded by the already bounded body.
Duplicate JSON keys, BOM, invalid UTF-8/scalars, constants/numeric tokens and extra
values are rejected. This request has no numeric JSON fields: decimals are exact
strings, acknowledged is strict true, unknown basis/date are required null.

Semantic validation uses canonical UUID/date/hash, concrete non-whitespace scalar
name rules, exact decimal lexical form and slice ranges, exactly one position and
one USD cash object. No trim/normalization/rounding/source identity inference.
The immutable RAM catalogue is default-empty, ≤16 exact closed records, sorted
strictly and unique. Whole-catalogue validation follows strict request and precedes
matching; QUALIFIED/READY/extra-field records are configuration errors. Constructors
do not inspect configuration or perform I/O before authentication.

Every intent refuses: unknown context, release mismatch, withdrawn, unqualified.
No success constructor, operation reservation, root/account/event/revision/artifact,
price lookup or financial result exists. Same/changed retries re-evaluate refusal,
without inventing an idempotency record. Output uses existing canonical JSON and
no-store/nosniff headers, no Set-Cookie. Closed output≤65536/error≤4096, whole refusal
on overflow. Old E1 exception/schema/routes remain isolated and exact.

## Validation plan and execution boundary

**At initial candidate freeze: product imports/tests/ASGI/PG/HTTP/browser NOT RUN.**
Only stdlib AST/syntax, exact diff/hash and source/document checks may run before
root supplies the independently reviewed closed-I/O runner and explicit GO.

The new fixed module covers meaningful boundaries:

- Exact decimals/ranges, required nulls/keys, array shape, scalar/date/UUID/hash,
  duplicate keys/invalid bytes/BOM, pre-tree depth/token bounds, exact body bound.
- RAM capacity/order/uniqueness/closed status, poison precedence, no filesystem,
  no positive path, repeated/changed intent zero reservation and fixed error text.
- In-process ASGI using SessionOnlyStore: old transport/auth/CSRF precedence,
  bounded streamed GET, bad configuration, database/disabled typed refusals,
  canonical complete bytes/headers, no private-value reflection or economic call.
- Old E1 full default/refusal bytes, then existing fictional complete snapshot
  comparison with the new hook disabled versus enabled, and reload after intents.
  Known independent arithmetic assertion stays10×100+10×50+500=2000.

Legacy compatibility app construction uses ONLY shipped
`src/web_api/fixtures/quotes-v1.json`, `calendar-v1.json`, and necessary existing
product-contract policy/registry JSON. Root has separately allowed the four exact
src JSON paths (including performance_methodology_registry); legacy catalog
metadata, if invoked, is limited to its existing explicit metadata allowlist.
No `data/marketdata` raw payload may be opened; no secret/personal/home cache read.
The guard, not this module, owns actual I/O permission. Spies are additional
behavior assertions, not an OS sandbox. No independently unreviewed runner edits.

Future real NAV, persistence, physical restart, source qualification, personal
pilot and HG4 are not acceptance criteria of this refusal-only increment and
cannot be claimed from its tests. Root records actual execution and PM acceptance
after author checks and independent technical review, preserving any failures.
