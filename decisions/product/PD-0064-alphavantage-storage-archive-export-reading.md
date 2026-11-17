# PD-0064 — Alpha Vantage personal licence covers local storage, archive, own export and reproduction

**Status:** accepted
**Date:** 2026-10-23 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Closes:** item 1 of the verdict in `reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md` (terms reading).
**Bears on:** PD-0027, PD-0028, PD-0032, PD-0062 item 4, PD-0063.

## Context

The Alpha Vantage terms license personal, non-commercial use. They are silent on whether
that use includes keeping the data locally, archiving it, exporting the owner's own reports,
and reproducing results from the stored data. The HG4 data check left that reading to the
owner. The real-data path needs it for every stored price file and every reproduction.

## Owner decision, verbatim

> I accept the reading that Alpha Vantage's personal, non-commercial licence covers local storage, archive, my own report export and reproduction, for US and A-shares. Record it.

## What this means

For `alphavantage.us` and the planned A-share route (`.SHH`/`.SHZ`, PD-0063), the owner accepts
that personal, non-commercial use includes:
- **local storage** of downloaded files and of the normalized data derived from them;
- **archive**, meaning keeping those files and records for later replay;
- **own report export**: the owner exporting reports and data for the owner's own use;
- **reproduction**: re-running calculations from the stored inputs.

This is the owner adopting a reading of the published terms. It is not legal advice and not
written confirmation from Alpha Vantage.

## Conditions that still apply

- **Personal use only.** Nothing is displayed, exported or shared to anyone other than the
  owner and the project's agents (PD-0028). An export the owner gives to someone else is
  outside this reading.
- **Free-key limits:** 25 requests a day across US and A-shares, and compact output covering
  the last 100 sessions.
- **Re-attestation before any commercial use.** Data fetched under these terms is not carried
  into commercial use (PD-0032).

## What this does not do

- It authorizes **no download**. Each Alpha Vantage request is a human step that needs its own
  owner approval (PD-0027 condition 2, PD-0062 item 4).
- It changes **no code or registry entry by itself**. The `terms_check` notes in
  `data/marketdata/SOURCES.json` are updated with the next market-data increment.
- The HG4 data check's **other items stay open**:
  - item 2, the quant ruling on split semantics;
  - item 3, identity via OpenFIGI;
  - item 4, acquisition approval and the human-acquirer recording.
- It approves **no gate**. HG4 is still not ready to request.
