# CP7-B account authentication, user isolation and PostgreSQL persistence

Authority: explicit owner request of 2026-10-19 to complete CP7-B; PD-0042 and
all PD-0041 conditions remain. No source admission, external identity service,
email, deployment, genuine-market simulation or night automation is added.

## Shared HTTP contract — finweb.cp7/1

The original guest routes remain unchanged. All account fetches use same-origin
credentials; the local Vite proxy forwards `/api` to the Python API. Account
requests do not use `X-Finweb-Session` or accept a client `user_id`.

1. `GET /api/v1/auth/session` returns
   `{schema_version,authenticated,user:{user_id,username}|null,csrf_token}`.
   An unauthenticated browser receives a random HttpOnly `finweb_csrf` bootstrap
   cookie; authenticated state reads the PostgreSQL session on every request.
2. `POST /api/v1/auth/register` and `/auth/login` accept exactly
   `{username,password}`. Register returns 201, login 200, with the session shape
   above. Username is normalized to lowercase ASCII: 3–32 characters, starts
   with a letter, remaining letters/digits/`_.-`. Password is unchanged, at least
   15 characters and at most 128 UTF-8 bytes. No composition rule or trimming.
3. `POST /api/v1/auth/logout` accepts `{}`, invalidates the server-side session,
   clears its cookie and returns unauthenticated state plus a bootstrap CSRF.
4. Every account mutation, including register/login/logout/reproduction, requires
   exactly one configured `Origin` and `X-Finweb-CSRF` from the session response.
   The header is strict lowercase ASCII hex64; missing, malformed, non-ASCII,
   stale or mismatched tokens are canonical `403 CSRF_REJECTED` before work.
5. `GET /api/v1/portfolios` returns
   `{schema_version,portfolios:[{portfolio_id,name,mode,synthetic:true,
   reporting_currency,as_of,created_at}]}`. Only the authenticated user's saved
   rows are selected; maximum 32 saved fictional sandboxes per account.
6. `POST /api/v1/portfolios` requires all CP7-A `PortfolioRequest` fields plus
   **`mode:"LOCAL_SYNTHETIC_ACCOUNT"`**. It creates a newly acknowledged fictional
   sandbox in PostgreSQL and returns the full CP7-A Snapshot shape, with
   `mode:"LOCAL_SYNTHETIC_ACCOUNT",synthetic:true,persisted:true`.
   There is no silent guest migration or genuine-user-input valuation using
   synthetic prices. CNY remains explicitly refused, `422 FX_PATH_UNAVAILABLE`.
7. `GET /api/v1/portfolios/{portfolio_id}` reconstructs the persisted snapshot
   using the actual canonical PostgreSQL ledger sequence IDs and stored source
   hashes; the entire canonical snapshot must equal the immutable saved artifact.
8. `GET /api/v1/portfolios/{portfolio_id}/packets/{insight_id}` and
   `POST .../reproduce` have the CP7-A proof/reproduction transport and exact
   expected digest request. Ownership is checked before any source, metric,
   packet access or reproduction. Unknown and foreign UUIDs are the same 404.

Canonical errors retain `{schema_version,error:{code,detail,state}}`:
`AUTHENTICATION_REQUIRED`401, `INVALID_CREDENTIALS`401 (same unknown-user/bad-
password detail), `USERNAME_UNAVAILABLE`409, `CSRF_REJECTED`403,
`AUTH_RATE_LIMITED`429, `AUTH_BUSY`429, generic `NOT_FOUND`404,
`ACCOUNT_MODE_DISABLED`503, `ACCOUNT_STORAGE_UNAVAILABLE`503,
`SAVED_SOURCE_DIFFERS`/`SAVED_RESULT_DIFFERS`503. Existing size/content-type,
schema, precision and strict local-origin/Host restrictions remain.

The durable-account caveat is exactly:
`SAVED_SYNTHETIC_SANDBOX: saved to this account; never an actual holding or real-market claim.`
It replaces only the guest expiry caveat; all data, currency, historical,
classification and synthetic limitations remain. No personal policy or benchmark
is invented. Optional policy/benchmark editing remains subsequent CP7 scope.

## Authentication and data protection

Passwords use stdlib/OpenSSL scrypt N=131072,r=8,p=1, salt16 random bytes,
dklen32, maxmem256MiB; encoded parameters are fixed and validated, constant-time
derived-hash comparison, same KDF for unknown usernames. At most two KDF operations
run concurrently; there is no unbounded hash work queue. Durable per-peer and
per-name attempt buckets cap login at20/register at10 per fifteen minutes.
Sessions are random256-bit opaque cookies; only SHA256 digests are stored in
PostgreSQL. Eight-hour absolute expiry, logout invalidation, rotation on login,
maximum eight active sessions per user. `HttpOnly;SameSite=Strict;Path=/api/v1`;
Secure and HTTPS are production defaults. Insecure cookies require the explicit
named local-development configuration. No bearer token enters a URL/localStorage.
All responses are no-store; neither request bodies, passwords nor tokens are
logged. The dev server must run with `--no-access-log`.

## PostgreSQL and migration boundary

Additive migration0017 creates `web_identity`, `web_session`, `web_auth_rate` and
`web_saved_sandbox`; old migration bytes/checksums are unchanged. Existing
`app_user`, `portfolio`, `account`, identities and append-only `ledger_event`
remain authoritative. Sandbox creation writes the user-owned portfolio, account,
opening ledger rows and pinned snapshot in one transaction; failures roll back.
Idempotency keys are distinct per opening row. Actual global/gapped ledger_seq
values, not event counts, become the source pin. Stored requests are a transport
record, never a substitute for loading the persisted ledger.

Each store operation opens a fresh connection, validates schema and role, pins
search_path and statement_timeout. Superuser/schema-owner runtime is refused.
Separate `web_account_store.APP_GRANTS` gives only required CP7 table/sequence
privileges, with no ledger/snapshot/identity UPDATE/DELETE and no DDL. Historical
ledger-only `APP_GRANTS` remains untouched. Schema setup/migrations/grants occur
outside HTTP requests. This is application-level owner isolation with scoped
joins, not a claim of PostgreSQL RLS or production deployment completion.

## Explicit local review launcher

`web_api.account_dev:app` requires all four variables:
`FINWEB_CP7_PG_SOCKET`, `FINWEB_CP7_PG_DATABASE`, `FINWEB_CP7_PG_USER`,
`FINWEB_CP7_PG_SCHEMA`. No `.env` or secret files, default owner identity,
automatic migration or database fallback. Root provisions the private scratch
cluster/schema/application role separately, then runs Uvicorn on loopback with
no access log. Original `web_api.dev` remains the independent guest-only entry.

## Validation status

Initial actual unit boundary and unchanged guest suite: **24 tests passed,
3.574s**. The first PostgreSQL run was blocked by the filesystem sandbox's socket
policy; authorized elevated socket access then reached the actual server. That
run exposed session `SELECT FOR UPDATE` requesting forbidden identity UPDATE
privilege; the store now uses per-user advisory transaction locks and keeps the
immutable grants. Subsequent PG run passed10/11; the remaining test had identical
injected timestamps and incorrectly assumed a tie's first-created random token
would be oldest. The test now advances its clock by1microsecond per session.
Final targeted actual PostgreSQL run: **12 tests passed, 7.120s, no skips**,
on root-provisioned PostgreSQL17.11 through the `finweb_cp7_app` non-owner role
inside a uniquely named disposable schema, verified dropped afterwards. Tests
cover real credential/session storage, cookie/CSRF checks, generic login failures,
logout/absolute expiry/session bounds, durable throttling, two-user isolation
before a poisoned financial source, byte-identical new-store/new-app financial
and proof reconstruction, actual global/gapped sequence pins across two saved
portfolios, invalid atomic pin refusal, transaction rollback, least-privilege
denials and source/artifact tampering. This author's targeted suite reconstructs
new store/application instances; physical database/server restart evidence comes
from the separate main-session execution below.

Adding migration0017 exposed three old default-suite metadata expectations for
the migration count/versions/table inventory. PM explicitly authorized only
their exact metadata updates; other assertions and inherited changes remain.
No old migration or financial engine was changed to address these expectations.
Final corresponding auth/guest/migration-guard run: **117 tests passed, 3.344s,
no skips** (including24 auth/guest tests). `git diff --check` passes.

Independent reviewer results are recorded in [technical review §53](../reviews/TECH_REVIEW.md):
**117 tests passed, 3.257s**, **12 actual PostgreSQL tests passed, 6.886s**,
**39 actual HTTP requests passed** and **5/5 real browser flows passed, 8.5s**,
plus the reviewer's own in-app-browser account/Chinese/keyboard checks. These
are independent executions, not the author's runs above. The final bounded
saved-context wording repair was separately checked: TypeScript,25 Vitest tests
and production build passed; the reviewer explicitly does not relabel the earlier
HTTP/browser runs as rerun after that copy-only correction. Final §53.6 verdict:
**PASS_WITH_FINDINGS**, solely the carried nonblocking CP7A-R8 repeated-Quick-
caveat readability debt. CP7B-R1 through R4 are closed. All38 final candidate
code/test identities matched that review-stage inventory; the two authorized
metadata follow-ups below expand the final inventory to40 files.

The main session additionally performed controlled **physical PostgreSQL stop/
start and API process restart**, recorded in
[actual restart durability evidence](../reviews/CP7_B_EVIDENCE/validation/actual-restart-durability.json).
Its independently entered fictional holdings give NAV450 and HHI29/81. The
database-down request canonically refused with503 ACCOUNT_STORAGE_UNAVAILABLE;
after both restarts, the same session, full snapshot and full packet remained
identical, actual source reproduction returned REPRODUCED, and logout revoked
access with401. This physical restart proof is attributed to the main session,
not this author's targeted PostgreSQL suite or the independent reviewer.

The main session's first full actual-PostgreSQL regression ran2539 tests in
243.615s:2535 passed,2 failed and2 E0 preflight checks skipped. Its
[initial raw log](../reviews/CP7_B_EVIDENCE/validation/pm-full-postgres-initial.log)
is retained as a failed run. Both failures were older test migration metadata:
`test_postgres_least_privilege.py` expected16 schema-migration rows, and
`test_postgres_risk_free.py` expected only0016 when upgrading from0015.
PM authorized only count16→17 and its comment in the former; the latter now
asserts the exact ordered0016+0017 migration filenames and names both in its
description. Permission denials/grants, full before/after projection digest,
actual reload, empty risk-free export and zero risk-free rows are unchanged.
The author reran those two actual PostgreSQL methods:2 passed,0.487s. The
independent reviewer then verified the exact backup-file deltas and reran both
complete affected modules: **33 passed,1.736s,no skips** (§53.7). No production
code, earlier migration, financial engine, method or expected fixture changed.

The main session's final full Python regression with actual PostgreSQL opt-ins
then passed: **2539 run,2537 passed,2 E0 preflight skips,0 failures,231.391s**.
The [final raw log](../reviews/CP7_B_EVIDENCE/validation/pm-full-postgres.log)
records this result; it supersedes the initial failed run without erasing it.
The separate [environment inspection](../reviews/CP7_B_EVIDENCE/validation/environment.json)
confirms PostgreSQL17.11, TCP disabled,0700 private socket directory and socket,
17 applied migration versions, zero leftover test schemas, non-owner application
role flags all false, no runtime schema CREATE, and no UPDATE/DELETE on ledger,
credentials or saved-snapshot tables. It read no private credential rows.

All40 final candidate code/test identities match the expanded reviewed freeze;
only this technical document changes in this finalization. These results support
bounded CP7-B acceptance; **full CP7 remains incomplete**. PM acceptance, current
project status and checkpoint-wide completion remain main-session responsibilities.
All existing data/gate conditions remain and no night automation is restored.
