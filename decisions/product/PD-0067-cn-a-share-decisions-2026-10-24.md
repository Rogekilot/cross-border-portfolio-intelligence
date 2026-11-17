# PD-0067 — Mainland China A-share decisions and the remaining morning items, 2026-10-24

**Status:** accepted (decisions 1–6)
**Date:** 2026-10-24 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0034, PD-0038 and PD-0041 (HG2 condition 4), PD-0063, PD-0066 ("Still open"),
`reviews/CN_CALENDAR_CHECK_PACKET.md`, `methodology/CP2_MARKET_DATA_CONVENTIONS.md`
(`market-data/1.15` §7A, §10.1).

## Context

The owner continued the one-at-a-time walkthrough of the morning decisions (PD-0066) with the
Mainland China items.

## Decision 1: the CN A-share calendar is checked and registered (HG2 condition 4, CN)

Question asked by the main session, verbatim:

> Do you confirm the CN_A_SESSIONS draft (2025–2026 closures and session counts above, close 15:00, no half days) as checked by you, so it can be finalized and registered?

Owner's answer, verbatim: **"Confirm, register it"**

What the owner was shown: the comparison in `reviews/CN_CALENDAR_CHECK_PACKET.md` (the draft
against the 2025 and 2026 SSE and SZSE closure notices, no difference found; independent review
PASS). It covered:
- the weekday closures for each year;
- 243 sessions in 2025 and 242 in 2026;
- close 15:00 Asia/Shanghai, no half days;
- links to the four notices.

It also noted that SSE's 2026 after-hours fixed-price session (15:05–15:30) does not move the
close.

What was done:
1. **Finalized the draft** (`data/marketdata/calendars/drafts/CN_A_SESSIONS.json`). `version`
   changed from `draft-1 (unchecked)` to `2025-2026 v1`. `prepared_by` now records the owner's
   check on 2026-10-24 under PD-0034. No date, time or coverage changed. Main session, as for
   NYSE on 2026-10-02.
2. **Registered by the owner**, who ran `register-file` with `FINWEB_HUMAN_DOWNLOAD=1`. The copy is
   at `data/marketdata/files/calendar.manual/calendar/2026-10-23/CN_A_2025_2026.json`; the tool
   files by UTC date, and 19:57:53Z is 03:57 on 10-24 in Shanghai.
   - payload SHA-256 `f357b7d44b41297ae04153965963ac18426d453056f68291f825e4ad0380d772`, 8963 bytes;
   - manifest SHA-256 `7055862a64b3a0d1ee27bb3f51e336852c6426a2b213b06a2661a577bfac9b25`;
   - `retrieved_by: human`, `source_identifiers: [CN_A_SESSIONS]`.
3. **Checked by the main session:**
   - the registered copy is byte-identical to the finalized draft;
   - the manifest hash and size match;
   - the file holds 485 dates for XSHG and XSHE, `actual_through` 2026-09-30;
   - `download verify` re-hashed all 16 stored files: 0 failed;
   - the calendar-draft test (`test_performance_cp4_part_a2`) passes: 36 OK, 3 skipped.

What this means:
- **HG2 condition 4 is met for the Mainland China calendar** (XSHG, XSHE, 2025-01-01 to 2026-12-31).
  Extending coverage past 2026-12-31, or moving `actual_through`, is a new version needing a new check.
- The Hong Kong calendar (HKEX_SESSIONS) stays an unchecked draft. HK is dropped from personal use
  (PD-0063 addendum).

What this does not do:
- **It admits no A-share price.** The `alphavantage.cn` profile stays TO_OBSERVE and the A.5 CN
  order stays empty. Admission still needs the source order (OP-1), the real-file observations of
  Ruling 7A.3, and an owner decision.
- It approves no download and no gate.

## Decision 2: intended A.5 CN source order is Alpha Vantage alone (OP-1 b)

Question asked by the main session, verbatim:

> OP-1: which source order should A-share prices use?

Owner's answer, verbatim: **"(b) Alpha Vantage alone (Recommended)"**

What the owner was shown:
- options (a) keep CN empty, (b) Alpha Vantage alone once its preconditions hold, and (c) add a
  second upstream;
- the blocker for each second-upstream candidate:
  - CN broker statements: held listings and statement dates only; a file-reading approval and the
    broker's terms needed;
  - SSE/SZSE data: bulk terms unread;
  - Tushare Pro: account, token and terms; some tiers paid;
  - BaoStock: no written terms;
  - EODHD: paid;
  - AKShare/Eastmoney and Sina: refused.

What this means:
- **The intended order is `CN: [alphavantage]`** (`market-data/1.15` OP-1 b). Every CN price would
  be `SINGLE_SOURCE`, as US prices are. The only cross-check is the human Test V4 spot check
  against the exchange close. The product says plainly that there is no CN price-to-price
  reconciliation evidence (Ruling 4.7 item 4).
- **It is not admitted by this decision.** `PRIMARY_ORDER["CN"]` stays `()` and the
  `alphavantage.cn` profile stays TO_OBSERVE until all of the following hold:
  1. the registered CN calendar (done, decision 1);
  2. the real-file observations of Ruling 7A.3 (c): delivered decimals and grid; unique dates and
     row order; no rows on closed days or after retrieval; as-traded confirmed for a cash dividend
     and a 送股/转增 event; how a suspended day is written; the volume unit. These need the OP-4
     downloads, each approved separately;
  3. a **final admission decision by the owner**, made after those observations are reviewed. That
     decision changes the A.5 order and the profile status in a reviewed increment.
- The CN broker-statements option of (c) stays open for later and needs its own approvals
  (PD-0063 item 1).

## Decision 3: the A-share observation plan is approved; listings and requests come later (OP-4)

Question asked by the main session, verbatim:

> OP-4: approve the A-share observation plan (about 3–4 Alpha Vantage requests plus your exchange-close look-ups and cninfo announcements), with each request approved once you name its listings?

Owner's answer, verbatim: **"Approve the plan, pick later"**

What this means:
- **The plan and budget are approved**, for the Ruling 7A.3 (c) observations: about 3–4 Alpha
  Vantage `TIME_SERIES_DAILY` requests for `.SHH`/`.SHZ` listings, the owner's Test V4 look-ups of
  official closes on the SSE/SZSE sites, and the cninfo announcements attesting each event.
- **The owner picks the listings later.** Within the file's 100-session window they must cover:
  - a cash dividend with ex-date at least 20 sessions before retrieval;
  - a 送股/转增 event (a combined event such as 10送3派2 covers both components);
  - a full-day 停牌 attested by an exchange or cninfo notice;
  - at least one CN holiday closure.

  Downloads run after 15:00 Asia/Shanghai on the last session wanted. Agents do not choose
  listings from memory.
- **No request is approved yet.** Each Alpha Vantage request is approved separately once its
  listing is named (PD-0027 condition 2, PD-0062 item 4). It is run by the owner with the download
  tool, which today implements only the US route: an A-share `fetch` route is a separate engineer
  increment, and the US-symbol guard refuses `.SHH`/`.SHZ` under `alphavantage.us`.
- **Naming a listing is the owner's choice.** Nothing reads the owner's broker statements
  (PD-0063 item 1).

## Decisions 4–6: filing sources (OP-6), split downloads (OP-3), the version label (L-2)

Questions asked by the main session, with the owner's answers, verbatim:

> OP-6: how should filing sources (cninfo, SEC EDGAR) be set up?

**"Register; agent drafts, I confirm"**

> OP-3: the Alpha Vantage split downloads (AAPL plus one reverse split, with SEC filings)?

**"Defer (Recommended)"**

> L-2: the market-data version label in the code?

**"Raise to 1.15 (Recommended)"**

What this means:
- **OP-6, decision 4.** cninfo and SEC EDGAR are to be registered as filing-role sources
  (`market-data/1.15` Ruling 7.6). Registration needs, for each:
  1. **A terms check**, as the owner's own reading of the site's live terms, recorded verbatim by
     the main session in `data/marketdata/SOURCES.json`. It has not been done yet; no entry is
     added until it is.
  2. **Filing records** (Ruling 7.6 item 2). An agent drafts each record only from text the owner
     supplies, because agents cannot open either site from here. The owner confirms each record
     against the filing before it counts. An unconfirmed draft attests nothing.
- **OP-3, decision 5: deferred.** No Alpha Vantage `SPLITS` acquisition is planned. Ruling 7.4
  stands: `SPLITS` fields have no granted meaning, every record is `UNMAPPED_ACTION`, and nothing in
  the HG4 single-date check needs them (PD-0066 decision 2).
- **L-2/N-1, decision 6: raise the version label to `market-data/1.15`.**
  - `CONVENTION_SET` and `PROFILE_SET_VERSION` move from `market-data/1.14` to `market-data/1.15`,
    so the release id names the method the code now runs (P12, NFR-001). Every release id changes.
  - Test baselines and pins are re-recorded, each with a stated reason.
  - No stored real release is affected: `finweb_dev` has no `md_*` tables, per the 2026-10-24
    review. The engineer re-checks this before the change.
  - An engineer increment, then independent review.

## Still open after this record

- The owner's terms readings for cninfo and SEC EDGAR (decision 4).
- Listings for the A-share observations, and each download approval (decision 3).
- An A-share `fetch` route in the download tool (an engineer increment) before the first A-share
  download.
