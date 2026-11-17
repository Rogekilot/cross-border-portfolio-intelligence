# PD-0033 — ECB-direct and calendar sources admitted; PD-0026 scope clarified; OpenFIGI lookups

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-01, adopting that session's suggestions.
**Recorded by:** that session. **Recorded, not decided.**
**Answers:** the owner items in `reviews/CP2_PM_ACCEPTANCE.md` §5 and STATUS (CP2):
- the `ecb.eurofxref` and `calendar.manual` attestations;
- the main-session reading of PD-0026, left open for the owner;
- the OpenFIGI lookups of `market-data/1.5` Appendix A.6.

---

## The decision

The session gave its reading on each item and suggested:

1. approve `ecb.eurofxref` and `calendar.manual`;
2. confirm the PD-0026 reading;
3. run the five OpenFIGI lookups the tool can make as it is;
4. decide who makes the calendar files.

Owner's answer, verbatim: **"Go with your suggestions, record them"**

Item 4 was a question put to the owner, not a recommendation. It stays open (below).

### 1. Source attestations (in `data/marketdata/SOURCES.json`)

| Source | Verdict | Basis |
|---|---|---|
| `ecb.eurofxref` | **true** | ECB disclaimer: free use if the ECB is cited and the data appear accurately. Modifications must be stated explicitly, so EUR-derived crosses are labelled derived. The ECB accepts no liability. Same upstream as `frankfurter.ecb`, so it is a provenance check (Ruling 1.1a), not an independent second source. |
| `calendar.manual` | **true** | No third-party terms apply; session and holiday dates are public facts. This attests the **method** for every calendar file: made from the publisher's notice and named in `evidence`; never derived from a price or rate file (Ruling 5.3); `prepared_by` says who prepared and who checked it. |

Loading the registry confirms 5 admitted (`alphavantage.us`, `frankfurter.ecb`,
`ecb.eurofxref`, `calendar.manual`, `openfigi`) and 7 refused.

### 2. PD-0026 scope (clarification; no new limit)

PD-0026's bounds apply to the ledger's stored values, the `ledger_event` columns it names.
Market-data values carry the same bounds by migration 0010: prices, rates, volumes, split
ratios, dividend amounts and benchmark values are all below 10^30 with at most 24 decimals.
**`precision_bound` is outside PD-0026.** It is an exact derived error margin, never a
ledger value or a displayed figure. It keeps the value limit below 10^30, with a scale limit
of 100, so it is stored exactly. The main-session reading recorded in STATUS and in
`reviews/CP2_PM_ACCEPTANCE.md` §5 is confirmed, and that open item is closed.

### 3. OpenFIGI lookups (owner action; OpenFIGI is admitted)

Run by the owner with the download tool, outside the agent sandbox, under PD-0027 (files,
not agent network calls). Each one is `fetch --source openfigi --symbol <S> --exch-code <C>`:

| Symbol | `--exch-code` | Moves to OBSERVED if the level test passes |
|---|---|---|
| AAPL | UW | XNAS (Nasdaq Global Select) |
| IBM (or another NYSE common stock) | UN | XNYS |
| 600519 | CG | XSHG |
| 600519 | CH | the CN composite code |
| 000001 (or another Shenzhen A-share) | CS | XSHE |

The sixth A.6 query, AAPL with `micCode XNGS`, **waits for a tool fix.** The tool always
sends an `exchCode` (default `US`) even when `--mic` is given, so that query would likely
return nothing. An engineer change is queued. The engineer moves an A.6 entry to `OBSERVED`
only from a saved file that passes Ruling 7.3 item 2.

## Open (not decided here)

- **Who makes the calendar files** (US: XNYS+XNAS; CN: XSHG+XSHE; HK: XHKG; ECB). There are
  two options:
  - the owner makes them;
  - the session drafts them from the official notices, with `prepared_by` naming it, and the
    owner checks them before registering.

  Until they exist, every freshness check is UNKNOWN, which fails closed.
- **The HKEX default close** (16:00 continuous trading versus about 16:10 after the closing
  auction) goes to the `quant-analyst` before the HK file's `close.default` is set.

## What this decision does not do

It is not a legal opinion, it admits no Eastmoney, Sina or BaoStock data, it does not change
PD-0026's ledger bounds, and it approves no gate.
