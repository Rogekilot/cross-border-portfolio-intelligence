# PD-0043 — CP7-B authentication, isolation and PostgreSQL execution

**Status:** accepted execution authorization
**Date:** 2026-10-19 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM); recorded, not decided.

## Owner instruction, verbatim

> 继续按推荐顺序推进 CP7-B，完成登录与用户隔离、PostgreSQL 持久化，并进行测试和独立复核。保留既有条件，不恢复夜间自动任务，需要新增授权时再问我。

## Authorized work and retained boundaries

Complete the next ordered increment: ordinary self-hosted login/account sessions,
server-verified per-user resource isolation, PostgreSQL storage/save/reload and
actual tests plus separate independent review. Reuse the canonical User UUID,
portfolio ownership and append-only ledger; preserve CP7-A's explicit guest path.
Normal runtime connections must use a distinct least-privilege application role,
not the schema owner. Additive auth/session/storage migrations must preserve old
migrations and financial engines/method/fixture identities.

The previously authorized React/TypeScript/Vite and Python/PostgreSQL architecture
and dependency allowance remain. Engineers may use adequate existing standard-
library password hashing and opaque server-side sessions; details are implementation
choices to be checked, not new owner decisions. No external auth/email/cloud
service or additional production dependency is approved here; ask if one becomes
necessary. Do not store plaintext passwords or expose credentials/session tokens
in application logs, URLs or client persistent storage.

The local test/development PostgreSQL instance is isolated from the owner's
existing cluster, bound to a private Unix socket with TCP disabled and files under
an ignored local directory. It holds only acknowledged fictional portfolios/test
accounts in this increment. PostgreSQL durability must actually survive application
restart; a cached JSON answer alone does not demonstrate ledger persistence.

Saving fictional sandbox data after authentication does not admit synthetic quotes
for genuine user portfolios. Keep a distinct acknowledged persisted synthetic mode;
do not silently migrate guest data or price real holdings using fictional inputs.
Real-data/source/calendar/history admission, benchmark selection, personal-policy
meaning and all PD-0041/HG3 conditions remain. Full CP7 and HG4/HG5/later gates are
separate from this increment's technical acceptance.

No market-data download/admission, purchase, external service, Git commit/push,
deployment/publication or night automation is authorized. The cancelled overnight
task stays deleted. Actual work, evidence and remaining scope are tracked in
`STATUS.md`, `PROGRESS.md` and `reviews/CP7_PLAN.md`.

## PM evidence-path grant and routing correction

The engineer's bounded grant additionally covers exactly
`reviews/CP7_B_EVIDENCE/validation/web-engineer-playwright.log` and
`reviews/CP7_B_EVIDENCE/validation/web-engineer-freeze.json`, for its own sanitized
execution log and author freeze. The PM requested and received these two files
before updating the path registry; that routing oversight is recorded here rather
than described as a pre-existing grant. The PM inspected/adopted both artifacts
and now registers these exact paths in `.claude/role-write-paths.json`. They do
not carry independent review authority. All PM acceptance/environment/restart/
final-audit artifacts remain PM-owned; the distinct reviewer writes only its
technical review. No other evidence path, source permission, dependency or owner
decision is expanded by this correction.
