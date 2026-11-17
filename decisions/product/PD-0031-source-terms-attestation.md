# PD-0031 — Source terms-of-use checks: only ECB FX and OpenFIGI are admitted

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-01, adopting that session's reading of each source's published terms.
**Recorded by:** that session. **Recorded, not decided.**
**Implements:** the `terms_check` entries in `data/marketdata/SOURCES.json` (tech plan §15.3;
STATUS open item 16(e)).
**Bears on:** PD-0027 (free sources for development), PD-0028 (OQ-04 split).

---

## The decision

The owner asked what exactly to check before attesting each source. The session read each
source's published terms and gave a plain reading per entry, without legal advice. It also
asked the owner to judge honestly whether the project's use is commercial product development
or personal/academic. Its reading assumed product development.

Owner's answer, verbatim: **"Fill them in per your reading and record it"**

Each entry is recorded with `checked_by` naming the owner as **adopting the main session's
reading**, so the record does not claim the owner read the terms personally.

| Source | `permits_internal_development_use` | Basis (paraphrased) |
|---|---|---|
| `openfigi` | **true** | MIT open-source licence; no reuse or redistribution restrictions |
| `frankfurter.ecb` | **true** | ECB permits reproduction with acknowledgement; Frankfurter permits commercial use. Credit the ECB. |
| `akshare.cn`, `akshare.hk`, `akshare.us` | **false** | Eastmoney service agreement: written permission required; no copying or onward provision of market data. AKShare: academic research only. |
| `akshare_sina.cn`, `akshare_sina.hk`, `akshare_sina.us` | **false** | Sina Finance user agreement (covers the website, not only the app): no automated acquisition; no commercial use beyond written permission. AKShare: academic research only. |
| `alphavantage.us` | **false** | Free licence is personal and non-commercial; commercial use includes research and testing |
| `baostock.cn` | **left null** | No written terms located; unreachable from the owner's network |

Clause references and links are in each entry's `notes` and `terms_url`.

## Consequences

- **The loader admits only `frankfurter.ecb` and `openfigi`.** Every price file from the
  six AKShare routes, Alpha Vantage and BaoStock is refused with
  `SOURCE_TERMS_NOT_ATTESTED`. This was verified by loading the registry: those 8 are refused
  and 2 are admitted.
- **PD-0027's working premise is narrowed.** No free source of real security prices is
  admissible for development. PD-0027's other conditions stand (internal use, files,
  lineage, no AI-sourced numbers).
- **CP2 is not blocked.** PRD §38.3's CP2 exit needs test data from more than one adapter or
  mock. Synthetic fixtures, which are already the committed fixture policy, plus real ECB FX
  and OpenFIGI satisfy it. The adapters built from real file shapes keep their value as
  format parsers.
- The already-downloaded price files stay local, git-ignored and unused. Deleting them is not
  decided here.
- **Frankfurter caveat:** the tool calls the v1 endpoint, believed ECB-only. v2 blends
  providers unless `providers=ecb` is passed. The v1 provenance must be confirmed before CP2
  relies on these rates as ECB data. The ECB must be credited wherever the rates are shown.

## Open, for the owner (not decided here)

- **Real security prices for HG2** (PRD §38.4 requires a demonstration portfolio with price
  timestamps). The options presented:
  1. written permission from a source;
  2. a paid plan that expressly allows internal use, for example EODHD Internal Use at
     $399/month;
  3. HG2 on synthetic prices.
  This must be decided before CP3 or HG2 needs real prices.
- **Re-attestation if the project's character changes.** These checks assume commercial
  product development. If the owner regards the current work as personal or academic, the
  Eastmoney and AKShare verdicts could differ. The Sina ban on automated acquisition applies
  either way. Changing a verdict is a new PD.

## What this decision does not do

It is not a legal opinion, it selects no paid vendor, it does not close OQ-04b, and it
approves no gate.
