# PD-0027 — Free market-data sources for development (P0 / OQ-04, development tier)

**Status:** accepted. Its "does not close OQ-04" clause is **amended by PD-0028**: OQ-04
was split, and this PD closes the development tier (OQ-04a).
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-01, after a vendor comparison and a zero-cost option were presented by that session.
**Recorded by:** that session. **Recorded, not decided.**
**Bears on:** P0 / OQ-04 (PD-0020 §9), H5 deployment intent (PD-0020 §10.2, PD-0021 §8),
H6 live-data execution model (PD-0020 §10.3), PRD §4.3, §11.2–§11.4, §41.1.

---

## The decision

The owner asked whether the platform could be built without paying for market data ("API
provided AI service is fine"). The session presented a free setup for development and
internal use, with its limits, and suggested settling OQ-04 in two steps: free sources now,
a commercial vendor before private beta.

Owner's answer, verbatim: **"Go with the free sources for development, record it"**

The setup as presented:

| Need | Source as presented |
|---|---|
| All three markets (US, HK, Mainland China), raw and split/dividend-adjusted daily prices | **AKShare** (open-source library; no key), primary |
| Second source, Mainland China | **BaoStock**, or the **Tushare** free tier (unadjusted daily only) |
| Second source, US and HK | **Alpha Vantage** free tier (25 calls/day), or **yfinance** |
| FX: USD / HKD / CNY | **ECB** daily reference rates (e.g. via the Frankfurter API); CFETS CNY central parity as published |
| Identifier resolution | **OpenFIGI** |
| Corporate-action cross-check | Issuer filings: **HKEXnews**, **cninfo (巨潮)**, **SEC EDGAR** |

Conditions presented with it, and adopted with it:

1. **Development and internal use only.** Data from these sources is not shown to anyone
   other than the owner and the project's own agents. The owner's own review, including
   HG2, counts as internal. Private beta or any external display needs a commercial,
   licensed source first (PRD §4.3: data being reachable does not make it redistributable).
2. **Files, not live calls from agents.** A human runs the download outside the agent
   sandbox and saves the results as files. The platform and its agents read only those
   files. The harness network policy does not change, and no credentials enter model
   context (PD-0020 §10.3).
3. **Lineage on every file:** source, retrieval time, and whether the series is raw,
   split-adjusted, dividend-adjusted or total-return adjusted (PRD §11.2, §11.3).
4. **Two independent sources per market where available.** Disagreements are flagged rather
   than resolved silently. This also gives HG2 its reconciliation evidence.
5. **An AI model is never a price, FX or corporate-action source** (P1, PRD §22.3). The
   owner's acceptance of AI API costs applies to the explanation layer only.
6. **No purchase and no binding** of any vendor (PD-0020 §9).

## Consequences

- CP2 adapters target these sources through the normalized contracts (tech plan §5, P11).
  Swapping in a commercial vendor later is a new adapter, not a change to analytics.
- Choosing between the listed alternatives (BaoStock or Tushare; Alpha Vantage or yfinance),
  the file layout, and the download script belong to the CP2 technical plan. The download
  itself remains a human step.
- Before any source is used, its terms of use are checked for internal development use.
  Yahoo's terms restrict yfinance-style access to personal use, so yfinance is the fallback,
  not the default.
- Free sources come with no support or uptime promise. Saved files keep CP2 reproducible
  when a source changes or goes offline.

## What this decision does not do

- **It does not close OQ-04.** The commercial vendor for private beta and later is still
  open. Whether this development-tier ruling is enough for OQ-04 at CP2 exit (PD-0020 §9) is
  still the owner's call.
- It does not rule on H5 (deployment intent). It settles H6 for development only.
- It licenses no benchmark index (PRD §11.4) for external display.
- It approves no gate.
