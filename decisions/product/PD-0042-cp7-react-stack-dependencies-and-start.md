# PD-0042 — CP7 React stack, bounded dependencies and start

**Status:** accepted
**Date:** 2026-10-19 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Decision material:** `reviews/CP7_ENTRY_DECISION_PACKET.md`, D-CP7-01/02 and
the immediately preceding recommendation in this chat.

## Owner decision, verbatim

> 同意上述两项推荐：采用 React＋TypeScript＋Vite，批准决策包列明的基础依赖及开发测试工具安装。记录决定并按推荐顺序开始 CP7，保留既有条件，不恢复夜间自动任务。

## Adopted choices and authorization

1. **D-CP7-01:** React + TypeScript + Vite production SPA. This resolves the
   reserved framework choice in PD-0020 §3 and PD-0021 §5; Python remains the
   authoritative backend, with PostgreSQL and the existing modular monolith.
2. **D-CP7-02:** install the bounded initial dependency allowance from the packet:
   runtime `react`, `react-dom`, `react-router`, `i18next`, `react-i18next`,
   Python `fastapi` and `uvicorn`, plus their required locked dependencies;
   development/test TypeScript, Vite + React plugin, React type declarations,
   Vitest, React Testing Library and Playwright, with compatible locked versions.
   Inspect environment, versions/licenses and lockfile changes. Further production
   dependencies require separate approval. No ORM rewrite is authorized.
3. Start CP7 in the recommended order: reconcile already-approved design contracts;
   thin exact-data query/command API; first local portfolio-to-evidence flow;
   persistence/authentication/import/export; full core views and bilingual depths;
   DB/API/browser and independent reviews. The first flow is an increment, not
   acceptance of all CP7.

## Conditions retained

- PD-0041/HG3 conditions remain: FULL_NAV/GLOBAL_PRODUCT, separate largest-security
  weight, labelled SPY ETF-proxy route without automatic portfolio selection,
  temporary US-only real validation, and source/calendar/history prerequisites.
- Use labelled synthetic development data or admitted adequate real data. Preserve
  missing/limited/unknown states and caveats. No browser financial recalculation,
  invented user limits, inflated freshness or unsupported severity.
- Existing four-surface IA and three Quick/Simple/Professional depths remain the
  design authority. HG4 retains later real-data usability validation; HG5 and later
  gates remain separate. A guest/local development flow is not a permanent waiver
  of normal authentication, saved-portfolio isolation, persistence or CSV scope.
- The 66-entry historical HG3 gap inventory and immutable evidence remain intact;
  new claims require their own supporting proof.
- No market-data purchase/download/admission, external auth/cloud service, Git
  commit/push, deployment or publication is authorized by this stack decision.
- The cancelled overnight automation stays deleted. No scheduler is recreated.

## Specialist path grant and execution evidence

The PM adds `web/` to the engineer write paths in `.claude/role-write-paths.json`
for the approved SPA source, package/lock/config files and tests. Existing source,
fixture and dirty work are preserved. This is a path grant for the adopted stack,
not a change to financial method ownership or independent-review separation.

Current execution, actual provisioning/test results and open work are recorded in
`STATUS.md`, `PROGRESS.md` and `reviews/CP7_PLAN.md`. No implementation success or
CP7 completion is implied by this decision record.
