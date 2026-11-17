# PD-0063 — Brokers named; no paid personal plan now; Alpha Vantage A-share reading approved

**Status:** accepted
**Date:** 2026-10-23 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0027, PD-0028 (OQ-04b), PD-0031, PD-0032, PD-0038 condition 4, PD-0062 item 4.

## Context

The owner chose the real-data path first and asked how to source Mainland China and Hong Kong
data. The session reported:
- no admitted CN/HK price source (AKShare/Eastmoney and Sina refused under PD-0031/PD-0032;
  BaoStock unattested);
- Alpha Vantage's documentation shows Shanghai (`.SHH`) and Shenzhen (`.SHZ`) symbols under
  the same free licence already attested for US use;
- options for Hong Kong: the owner's own broker API, a paid personal vendor plan, or HKEX
  daily quotations with HKEX's written permission.

## Owner decision, verbatim

> a Mainland China broker has my holdings, and another of my holdings is at US Broker.
> Don't consider a personal plan right now
> approve the Alpha Vantage A-share reading

## What this means

1. **Brokers (a fact, not a data grant).** The owner's holdings are at a Mainland China broker
   (境内券商) and US Broker. This tells the plan which export formats and quote routes matter.
   It does not authorize reading any statement, export, account or credential. Real holdings
   enter the product only through a later, separately approved step.
2. **No paid personal data plan** (e.g. EODHD) is considered for now. Revisit only if the owner
   raises it.
3. **Alpha Vantage A-share reading approved.** The session's reading:
   - The Alpha Vantage free licence that PD-0032 attested for personal, non-commercial use is
     the same licence for Shanghai and Shenzhen symbols.
   - So a CN route (`.SHH`, `.SHZ` symbols) permits internal development use under the same
     conditions:
     - no redistribution or display to others;
     - the free key's limits (25 requests a day, shared with US; compact output covers the
       last 100 sessions);
     - re-attestation before any commercial use.

   This is the owner adopting that reading. It is not legal advice.

## Addendum, same day: Hong Kong dropped from personal use

The session asked whether the owner holds Hong Kong shares (e.g. via Stock Connect at CN broker).
Owner's answer, verbatim:

> No, I don't hold Hong Kong shares; my CN broker holdings are A-shares only. Drop Hong Kong prices from the personal-use plan for now.

- The personal-use real-data plan covers **US (US Broker) and Mainland China A-shares
  (CN broker)** only.
- Hong Kong price sourcing is **deferred**:
  - no HK source search, HKEX request or user-supplied price class is pursued for now;
  - HK listings stay supported by the product with made-up data. With real data they show
    the existing "no admitted source" refusal, not an estimate.
- This is a personal-use scope choice. **It does not change the V1 PRD scope (§5.2)**, which
  still lists Hong Kong, nor the requirement for an HK source before V1 can be complete or
  before HK real data is shown. OQ-04b is unchanged.

## What this does not do

- **No code change by itself.** A route needs registration in `data/marketdata/SOURCES.json`
  (with this terms entry), a source profile, adapter support for the CN market and symbol
  suffixes, and CN conventions from the quant-analyst. That is an engineer and quant
  increment, then independent review.
- **No download.** Every Alpha Vantage data request stays a human step and needs its own
  approval (PD-0027 condition 2, PD-0062 item 4).
- **HG2 condition 4 still binds.** Checked and registered SSE/SZSE calendars come before real
  A-share data.
- **The storage reading stays open.** The Alpha Vantage terms are silent on local storage,
  archive, own-report export and reproduction
  (`reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md`, verdict item 1). That owner decision is
  still open, for US and CN alike.
- **No Hong Kong source.** Hong Kong prices stay without an admitted source.
- **No display to others.** Nothing here permits showing data to anyone other than the owner
  and the project's agents (PD-0028).
