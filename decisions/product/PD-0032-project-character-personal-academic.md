# PD-0032 — The project is personal or academic for now; source terms re-checked

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-01.
**Recorded by:** that session. **Recorded, not decided.**
**Amends:** PD-0031 (the `alphavantage.us` verdict only). **Bears on:** H5 deployment intent
(PD-0020 §10.2, PD-0021 §8), PD-0027, PD-0028 (OQ-04b).

---

## The decision

PD-0031's verdicts assumed commercial product development. They noted that the Eastmoney and
AKShare verdicts could differ if the owner regarded the work as personal or academic, and
that the Sina ban on automated acquisition applies either way.

Owner's statement, verbatim: **"see this project as personal or academic rather than a
product"**

So for the present phase, use of market data in this project is **personal or academic and
non-commercial**.

## Terms re-checked under that premise (the session's reading; not legal advice)

| Source | Before (PD-0031) | Now | Why |
|---|---|---|---|
| `alphavantage.us` | false | **true** | The free licence covers personal, non-commercial use, which this now is |
| `akshare.cn/hk/us` (Eastmoney) | false | **false** | Eastmoney forbids copying its market data without written permission, whatever the purpose. Stored files are copies. |
| `akshare_sina.cn/hk/us` (Sina) | false | **false** | Sina forbids automated acquisition whatever the purpose |
| `frankfurter.ecb`, `openfigi` | true | true | Unchanged |
| `baostock.cn` | null | null | No written terms located; unreachable |

AKShare's own academic-research-only disclaimer is now met, but a library cannot grant rights
its upstream website withholds. The upstream terms decide.

## Consequences

- The loader admits `alphavantage.us`, `frankfurter.ecb` and `openfigi`. This was verified by
  loading the registry: 3 admitted, 7 refused.
- **Real US prices** are available for development within the free key's limits: 25 requests
  a day, and compact output covering the last 100 sessions only (Probe 4). **There is still no
  admissible real price source for Mainland China or Hong Kong.** STATUS open item 17 narrows
  to those two markets.
- The Alpha Vantage key pasted into chat earlier is treated as exposed (STATUS, Probe 4).
  Request a new key and keep it terminal-only.
- **H5 for the present phase:** personal or academic, non-commercial. Private beta, external
  display and commercial use remain gated by OQ-04b (PD-0028) and HG7.
- **Change of character.** If the project moves toward a product, beta or any commercial use:
  - every `terms_check` must be re-done under the new premise;
  - data fetched under personal or non-commercial terms is not carried into that use;
  - that move is a new PD.
- The PRD's product scope, its commercial assumption (§4.3) and the gates are unchanged.
  This PD describes how the project is used now, not what the product is.

## What this decision does not do

It is not a legal opinion. It does not admit any Eastmoney or Sina data, select a paid
vendor, close OQ-04b, or approve any gate.
