# PD-0039 — CP4: benchmark data, risk-free rate, scope, benchmark selection storage

**Status:** accepted
**Date:** 2026-10-02
**Decided by:** the designated **human product owner**, answering four questions put by the main
session in a Claude Code session on 2026-10-02.
**Recorded by:** the main session (PM). **Recorded, not decided.**
**Plan:** `reviews/CP4_PLAN.md` §4 (D1–D5). D4 (new reason codes) was deliberately not asked: it is
decided if and when `quant-analyst` requests a code.

---

## The decisions

| # | Question put | Owner's answer, verbatim | Option text the owner selected |
|---|---|---|---|
| D1 | "Where should CP4's benchmark data (beta, alpha, tracking error) come from?" | **"Synthetic now (Recommended)"** | Build and prove CP4 on synthetic benchmarks behind a source-independent contract. Decide on real data (ETF proxies or a paid source) before HG3. |
| D2 | "What risk-free rate should Sharpe, Sortino and alpha use?" | **"Public series (Recommended)"** | A per-currency rate series from an admitted public source, e.g. US Treasury daily bill rates. You check and attest the terms; synthetic series in fixtures meanwhile. |
| D3 | "What should CP4's scope be?" | **"PRD list + TE/IR (Recommended)"** | Volatility, downside deviation, drawdown, Sharpe, Sortino, beta, Jensen's alpha, plus active return, tracking error and information ratio. VaR, Expected Shortfall and rolling analytics after HG3. |
| D5 | "Store each portfolio's chosen primary benchmark as user data (dated, append-only; new migration 0015)?" | **"Yes (Recommended)"** | Required by PRD FR-017: the user explicitly selects the primary benchmark; the engine records which one each result used. |

## Consequences

**D1 (benchmark data):**
- CP4 is built and proved on synthetic benchmark series, behind a `BenchmarkSeries` contract that does
  not depend on the source (PRD §11.4).
- **Owed before HG3:** a decision on real benchmark data, either ETF proxies or a paid personal-use
  source.

**D2 (risk-free rate):**
- The risk-free rate is a per-currency **series** from an admitted public source. A declared constant
  is not used.
- The candidate for USD is US Treasury daily bill rates. **Owner action:** check and attest that
  source's terms (as at PD-0031) before any real risk-free data is used.
- Until then, fixtures use synthetic series.
- `quant-analyst` sets the convention: the rate tenor, compounding, de-annualization, and the currency
  (the reporting currency).

**D3 (scope):**
- CP4 delivers:
  - volatility, downside deviation, maximum drawdown, Sharpe and Sortino;
  - beta and Jensen's alpha (with R²);
  - active return, tracking error and information ratio;
  - the methodology registry and the sufficiency checks.
- VaR, Expected Shortfall and rolling analytics wait until after HG3. They stay Advanced V1 scope (PRD
  §16.2).

**D5 (benchmark selection storage):**
- The user's primary-benchmark selection is stored per portfolio, dated and append-only, in a new
  migration, 0015.
- Every benchmark-dependent result records which selection it used.

**Unchanged:**
- HG2 conditions 3 and 4;
- OQ-04b;
- PD-0032 (personal/academic use; internal-only data).

## What this decision does not do

It does not admit any source; the Treasury attestation is the owner's. It does not choose real
benchmark data, approve HG3, or rule on methodology, which is reserved to `quant-analyst` under
PD-0014 §3.
