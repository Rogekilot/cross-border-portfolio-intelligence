# PD-0044 — CP7-B ledger, personal policy and benchmark workflows

**Status:** accepted execution authorization
**Date:** 2026-10-19 (Asia/Shanghai)
**Decided by:** designated human product owner in this chat.
**Recorded by:** main session (PM); recorded, not decided.

## Owner instruction, verbatim

> 继续按推荐顺序推进 CP7-B 剩余工作，先完成流水增改交互，再推进个人策略与基准选择，并进行测试和独立复核。保留既有条件，不恢复夜间自动任务，需要新增授权时再问我。

## Ordered authorized work

1. Account-owned ledger history and manual append/reversal/atomic correction
   interactions, with explicit validation/preview/confirmation and retry/concurrency
   controls. Reuse canonical event types and append-only stores. Old ledger rows,
   saved snapshots, source pins and packets must remain reproducible after a new
   revision; no financial engine or methodology change is implied.
2. Optional explicitly user-confirmed personal limits, preserving existing
   `UserLimit` provenance/scope/effectivity/subject/semantic identity and strict
   breach rules; blank is absence. Version/save/remove operations are durable and
   isolated. Never seed a risk tolerance, threshold, horizon or account inheritance.
3. Explicit per-portfolio benchmark choice using the existing catalog and
   append-only selection log/pin. Distinguish never stated, explicitly no benchmark
   and an admitted selection. Catalogs remain empty: implement honest empty/unavailable
   behavior and reject unadmitted IDs. Tests may use their own clearly fictional
   catalog fixtures; that does not admit production entries or enable genuine
   benchmark analytics. SPY is not silently selected.
4. Appropriate real PostgreSQL/API/browser tests, immutable revision/proof checks,
   bilingual UI checks and distinct independent adversarial review before PM
   technical acceptance. Full CP7, CSV, real-data validation and later human gates
   retain their separate requirements.

## Implementation and preservation boundaries

The PM captured376 current source/test/method/config files and561 prior evidence
files under `/tmp/finweb-cp7b2-20261019/` before author edits. Preserve inherited
uncommitted work and the accepted A/B evidence packages. Use a new
`reviews/CP7_B2_EVIDENCE/` package for this increment, PM-owned; author tools/logs
go only to their existing paths or temporary directories and are adopted by the
PM after inspection. Engineer owns source/tests/implementation/web; the independent
reviewer writes only `reviews/TECH_REVIEW.md`. No new evidence-path grant is needed.

Additive numbered migrations, exact minimal application grants and bounded API/
web integration are routine implementation choices within this request. Frozen
migration bytes and earlier financial methods/fixtures may not be edited. Existing
test metadata that necessarily enumerates migrations must be inspected and separately
recorded before a narrow update; permission/digest/financial assertions stay intact.

The local workflow remains explicitly fictional SYN/USD. If supporting a later
as-of transaction requires additional fictional raw dates, add a new versioned raw
demo input/calendar rather than modifying accepted v1 files; pin the version on
each immutable revision and retain the old reproducer. This is a local synthetic
implementation choice, not real-market data admission or an authorization to
invent historical coverage. Unsupported date/currency/source states remain typed
refusals or unavailable metrics; do not change the accepted ledger replay cutoff.

Reuse the approved installed dependencies and private local PostgreSQL instance;
serialize DB suites and use separate fresh runtime/disposable schemas. No external
auth/cloud service, extra production dependency, download/admission/purchase,
Git commit/push, deployment/publication or scheduler action is authorized. Ask
only if a genuinely new authorization becomes necessary. PD-0041/HG3 and all
existing conditions remain; cancelled night automation stays deleted.
