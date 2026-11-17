# PD-0066 — HG4 US single-date check: owner decisions, morning of 2026-10-24

**Status:** accepted (decisions 1–10, made one at a time on 2026-10-24)
**Date:** 2026-10-24 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0027 condition 2, PD-0032, PD-0062 item 4, PD-0064, PD-0065;
`reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md` (verdict item 4);
`methodology/CP2_MARKET_DATA_CONVENTIONS.md` (`market-data/1.15`, §10.1).

## Context

The night run (PD-0065) ended with a list of owner decisions (STATUS.md item 10). The owner
asked to go through them one at a time, starting with what the US single-date HG4 check needs:
one fictional account holding 10 AAPL plus USD 500, valued as of 2026-09-30 from real data.

## Decision 1: the stored AAPL file was the owner's own hand download

Question asked by the main session, verbatim:

> Did you download data/marketdata/files/alphavantage.us/quote/2026-10-01/AAPL_compact.csv yourself (Alpha Vantage TIME_SERIES_DAILY compact for AAPL, around 12:53 Beijing time on 2026-10-01)?

Owner's answer, verbatim: **"Yes, it was me"**

What this means:
- The file's manifest value `retrieved_by: human` is confirmed by the owner. The file is
  `TIME_SERIES_DAILY`, compact, AAPL, retrieved 2026-10-01T04:53:50Z, 5741 bytes, SHA-256
  `066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb`, covering 2026-05-08 to
  2026-09-30.
- It may serve as the price input of the 2026-09-30 single-date check. No new Alpha Vantage
  request is needed for the price. This closes the price half of HG4 data-check item 4
  (acquisition and human-acquirer recording) for this file only.

What this does not do:
- It does not declare the file's adjustment. The manifest stays `UNDECLARED`; whether
  `TIME_SERIES_DAILY` is as-traded is a separate confirmation (`market-data/1.15` OP-5).
- It does not settle identity (AAPL → XNAS), qualify a release, admit anything new, or
  approve HG4.
- It authorizes no other download.

## Decision 2: Ruling 6.5 accepted; no corporate-action file in the check's data (OP-2 a)

Question asked by the main session, verbatim:

> Do you accept Ruling 6.5 as the basis of the 2026-09-30 single-date check, with no corporate-action (split) file in its data (OP-2 option a)?

Owner's answer, verbatim: **"Accept, no split file (Recommended)"**

What this means:
- `market-data/1.15` Ruling 6.5 is the basis of the single-date check. A position that opens on
  2026-09-30 held no units at any earlier ex-date, so no split history can change the value.
- The check's data version `M` holds **no corporate-action file** (OP-2 option a). This closes
  HG4 data-check item 2 (split semantics) for this check.
- Results may show the holding value as AVAILABLE with the split label UNVERIFIABLE. They may not
  claim a verified as-traded series, a second-source or exchange check, a complete split history,
  or anything about another date. The open review finding that the dividend component is also
  UNVERIFIABLE (Ruling 6.5 item 6) applies to the claim limits as well.

What this does not do:
- It grants no meaning to Alpha Vantage `SPLITS` fields (Ruling 7.4). OP-3's downloads stay
  optional and unapproved.
- It does not settle the as-traded label (OP-5) or identity, and approves no download or gate.

## Decision 3: the owner's reading of the live Alpha Vantage documentation (OP-5)

The main session could not open the page: the project browser guard
(`.claude/hooks/guard_browser.py`) blocks outside sites. The owner opened
`https://www.alphavantage.co/documentation/#daily` in their own browser on 2026-10-24 and
reported, verbatim:

> 1. raw as traded
> 2. .SHH/.SHZ shown as supported

What this means:
- **`TIME_SERIES_DAILY` is raw (as-traded)**, by a human reading of the live documentation. This
  is the confirmation `market-data/1.15` OP-5 asks for. The label source for `alphavantage.us`
  `TIME_SERIES_DAILY` may move from `MEMORY` to `DECLARED` (§9B item 4 (d)). It is a declaration
  by the vendor, not a verification against the exchange (Test V4) or a filing (V1).
- **Shanghai (`.SHH`) and Shenzhen (`.SHZ`) symbols are documented as supported.** This is the
  human confirmation behind Ruling 7A.1's mapping, which review finding F-6 noted rested only on a
  summarizer read. The raw statement covers the same endpoint for those symbols.

What this does not do:
- It changes no file by itself. The quant-analyst records the label-source change in the
  methodology, and the engineer updates the source profiles; both are then reviewed.
- It admits nothing for CN: the `alphavantage.cn` profile stays TO_OBSERVE and A.5 CN stays empty.
- The terms PDF version and the rest of the documentation page were not re-checked.

## Decision 4: two OpenFIGI identity lookups for AAPL approved, run by the owner

Question asked by the main session, verbatim:

> Do you approve the two OpenFIGI identity lookups for AAPL (micCode XNGS, and exchCode UW), run by you from your own terminal?

Owner's answer, verbatim: **"Approve, I'll run both"**

What this means:
- Exactly two OpenFIGI v3 mapping requests are approved (PD-0027 condition 2), as recommended in
  `market-data` Ruling 7.3 item 8. They observe the US exchange-level entry for XNAS and test
  the segment-MIC reading:
  - `fetch --source openfigi --symbol AAPL --mic XNGS` (sends `micCode XNGS` only);
  - `fetch --source openfigi --symbol AAPL --exch-code UW` (sends `exchCode UW`).
- The owner runs them in their own terminal, so `retrieved_by: human` is true. The main session
  then verifies only those two files.

What this does not do:
- It approves no other request, and no change to the identity tables. Attaching a FIGI to the
  XNAS listing still follows Ruling 7.3 (only observed or confirmed exchange codes attach).
- It approves no gate.

**Result (observation, not a decision).** The owner ran both requests in their own terminal with
`FINWEB_HUMAN_DOWNLOAD=1`. The tool files them by UTC date, so they are under
`data/marketdata/files/openfigi/identity/2026-10-23/` (19:08 UTC = 03:08 on 10-24 in Shanghai).
The main session checked both manifests (`retrieved_by: human`, request as approved) and that each
payload's SHA-256 and size match its manifest. Both payloads are identical, 264 bytes:

| Request | Result |
|---|---|
| `micCode XNGS` (`AAPL_XNGS.json`, 19:08:13Z) | one record: `figi BBG000B9Y5X2`, `exchCode UW`, `compositeFIGI BBG000B9XRY4`, `shareClassFIGI BBG001S5N8V8`, Common Stock, Equity |
| `exchCode UW` (`AAPL_UW.json`, 19:08:18Z) | the same record |

- `figi ≠ compositeFIGI`, so this is an **exchange-level** record (Ruling 7.3). The composite
  matches the 2026-10-01 `exchCode US` observation (`BBG000B9XRY4`).
- The segment-MIC reading is **confirmed**: OpenFIGI's `micCode XNGS` returns the `UW` record,
  while `micCode XNAS` returned nothing on 2026-10-01.
- Follow-up for the quant-analyst: Appendix A.6 `UW` / `XNGS` (Nasdaq Global Select) can move from
  `MEMORY` to `OBSERVED`, so an exchange-level FIGI can attach to AAPL's XNAS listing. The engineer
  then applies it. Both are reviewed. Nothing is attached yet.

## Decision 5 (F1 design D3, expiry): the owner's reading of the live Alpha Vantage terms

This is the human reading that `implementation/CP7_F1_REAL_PATH_DESIGN.md` §3 requires before any
expiry option other than HOLD. The owner opened `https://www.alphavantage.co/terms_of_service/` on
2026-10-24, saved it as `/Users/<os-user>/Desktop/download.pdf` (156,583 bytes, 4 pages, not
copied into the project), and answered the four questions the main session asked. Verbatim:

> 1. None
>
> 2. one (1) year terms thereafter ("Renewal Term") until and unless either Party provides the
> other Party with thirty (30) days prior written notice to the end of the Annual License Term or
> the Renewal Term
>
> 3. Except as expressly required by law, if either party terminates this Agreement in accordance
> with any of the provisions of this Agreement, neither party will be liable to the other, because
> of such termination, for expenditures, commitments or damages caused in connection with this
> Agreement. Upon termination, User's access to the Alpha Vantage Platform shall be deactivated. No
> refunds shall be issued upon termination of Premium Membership plans unless otherwise authorized
> by the Alpha Vantage Platform. The following Section survive termination of this Agreement:
> Indemnity.
>
> 4. User shall retain all right, title and interest to the intellectual property rights to its
> data, and any other Content developed by User

The questions were: (1) date or version; (2) fixed term or renewal; (3) termination and notice;
(4) what happens to stored data afterwards.

**Main session's notes on the reading** (not the owner's words; not legal advice). They come from a
local text extraction of the same PDF, which dropped a few words:
- (1) No date or version is shown. The reading is of what the site served on 2026-10-24.
- (2) Section 6, "License Term": an annual term that renews automatically for one-year terms
  unless either party gives 30 days' prior written notice before the end of a term. Nothing in
  section 6 limits it to paid plans.
- (3) Section 7: on termination, access is deactivated, and only the indemnity survives.
- (4) The quoted sentence is section 5b, the user's rights in the user's own data and content.
  Section 5a reserves Alpha Vantage's rights, including its "database and files". The terms do not
  say what happens to Alpha Vantage data already downloaded when the agreement ends.
- Under the design's rule (§3), a reading that shows a fixed term or termination on notice leads
  to X1 or HOLD, not X3 (FF1-C06: non-expiry is never inferred from silence).

The owner's choice of option follows below.

**Owner's choices, verbatim answers to the main session's three questions:**

> Given the one-year, auto-renewing licence that can be ended on 30 days' notice, which expiry option should the real-data path use?

**"X1 lease (Recommended)"**

> If the Alpha Vantage licence ends, what happens to the Alpha Vantage data already stored here?

**"All rights off (Recommended)"**

> When did you get your Alpha Vantage API key? That date starts the annual term, so its anniversary is when the current term ends.

**"On or near 2026-10-01"**

What this means:
- **D3 = X1, a lease checked at admission.** A published real-scope context carries an explicit
  `valid_until`. Admission is refused after it, and an operation admitted before it may complete.
  A renewal extends `valid_until` only when a human records it; without that record the context
  lapses and fails closed. If either party gives notice of non-renewal or termination, the owner
  withdraws the context.
- **Current term end.** The key existed by the first download (2026-10-01T04:53:50Z), so the term
  began on or before 2026-10-01 and ends on or before 2027-10-01. "Near" leaves the exact start
  open, so the main session proposes a conservative `valid_until` of **2027-09-01**. The owner can
  correct it from the signup date in their Alpha Vantage account.
- **On termination or lapse, all four rights go false** for Alpha Vantage data: create, read, export,
  reproduce (design §3, default withdrawal). Keeping past reports readable would need its own
  explicit decision.
- **The design changes:** X1 moves from "designed later" into the slice. R1 gains the X1 design and
  tests (`valid_until`, trusted clock, lease and cancellation), per the branch delta "terms reading
  shows a term or notice termination" (§7.2). This reading is the decision reference that would
  otherwise be needed for `NONE`; `NONE` stays unreachable for this source.
- **PD-0064 still applies only while the licence is in force.** Its storage, archive, export and
  reproduction reading ends with the licence.

What this does not do: it builds nothing, publishes nothing, and approves no gate. The remaining
F1 decisions (D1, D2, D4–D7) are separate.

## Decision 6 (F1 design D1): namespace, placement and real-root storage

Questions asked by the main session, with the owner's answers, verbatim:

> D1: where should real data live?

**"B, separate schema (Recommended)"**

> Placement: where does that real namespace go?

**"Separate database (Recommended)"**

> Storage for the real portfolio root:

**"S2, own tables (Recommended)"**

What this means (design §1, §7.2 branch deltas):
- **D1 = B (C02-B).** Real data lives in its own namespace, built from the same migration chain,
  with only a real-only gateway (a fork of the F2 design) installed. Legacy and fictional roles get
  no access there. The protected `guarded_workspace_*` files are **not** edited.
- **Placement: a separate database**, so connection rights are a barrier as well as grants. Each
  future migration is applied to both databases. No SQL goes into an existing non-disposable
  database without its own approval.
- **Storage S2.** Real roots and revisions live in their own add-on tables (`rw_root`,
  `rw_revision`), never in `web_saved_sandbox`/`web_portfolio_revision`, and need no migration. R3
  still audits every reader of the shared canonical tables, so that none stamps a real portfolio
  synthetic (P9).
- **Consequences for D4:** under B, the three PD-0059 edits to the F2 files are retired. Their
  obligation design (policy row, row guard, bundle guard) becomes the real seal's design.
- **Accepted cost** (stated to the owner before the choice): B has **no run evidence**. Every
  ordering the PD-0059 prototype proved under A (publication races, rollback, ACK loss, the
  ordinary-lease-without-link refusal) must be proven again for the real gateway. Inside the real
  executor role, isolation still rests on lease triggers, row guards and the seal, as under A.

## Decision 7 (F1 design D2): the sole authority, context identity, the E5 contract, the publisher

Questions asked by the main session, with the owner's answers, verbatim:

> D2: where does the single authority for live real data live?

**"R-GW, in gateway (Recommended)"**

> How is a published real data set identified?

**"Content hash (Recommended)"**

> May the 'permanently closed' real-data web contract (E5) be replaced by a new, scoped contract version for this slice, after review?

**"Yes, new scoped version"**

> Who holds the credentials to publish or withdraw real data?

**"Only me (Recommended)"**

What this means (design §2):
- **R-GW.** The real gateway holds its own snapshot, history, head and mode rows. There is one
  authority and one lock order: mode shared, then head shared. Nothing falls back to the latest
  file, `FileStore` or `SOURCES.json` at runtime. The snapshot carries the source records it was
  published with.
- **Context = content hash.** Different content is a different context. Generation counts only
  rights or withdrawal changes. The HG4 root stays bound to its original context. A-shares later
  mean a new snapshot, context and root. Logical-name rebinding is out of the slice.
- **E5 contract.** The permanently closed real contract (`real_workspace_contract.py`, E5
  acceptance) may be superseded by a **new, scoped contract version** covering only this slice's
  real routes. It is not edited in place, and it is independently reviewed before use. The old
  contract stays as the historical record.
- **Publisher: the owner only.** Issuer/revoker credentials are provisioned only to the owner's own
  sessions, never to agent sessions. Every publish or withdraw records the issuer and a
  decision-record reference (PD id and sha), and a publish without one is refused. This is an
  operational control and a record, not proof of identity.

## Decision 8 (F1 design D4): parked patches, the pre-real test path, the test scope

Questions asked by the main session, with the owner's answers, verbatim:

> D4: do you confirm the engineer's view on the parked patches (N2a generalise, N2b generalise, N3 re-target after N2b, PD-0060 defer and reuse its pattern)?

**"Confirm all four"**

> How should the real-data code path be tested before your real data touches it?

**"(a) Made-up + test switch (Recommended)"**

> Where should the made-up test scope live?

**"One product module (Recommended)"**

What this means:
- **Patches** (design §4):
  - **N2a** is generalised to the real scope and re-targeted to the real gateway's objects;
  - **N2b** is generalised, with the world built from the locked snapshot;
  - **N3** is re-targeted after N2b, and its probe script stays as evidence only;
  - **PD-0060** is deferred, with its pattern reused for the all-writer matrix (T03);
  - **PD-0059**'s three F2 edits are retired (decision 6).
- **Pre-real test path: option (a).** This resolves the final-check MEDIUM in
  `reviews/TECH_REVIEW.md` ("Real-path F1 design — final check (2026-10-23)").
  - Invented data is never marked `synthetic = false`; this keeps FF1-C08 and E9-F01.
  - The real-scope branch runs before the real run through a **reviewed test-only switch**, in
    disposable databases only. The check "a real-scope source must not be synthetic", which the
    switch bypasses, gets its own separate test.
  - The design's `INVENTED_REAL_SHAPED_TEST` context, which set `synthetic = false` on invented
    bytes, is withdrawn. The first `synthetic = false` record stays reserved for the real run (R8).
- **Scope placement:** one parameterised product module holds every scope (`SYNTHETIC_TEST`, the
  test-switch scope and the real scope), so they share identical rules and cannot be mixed. The
  test switch is refused outside a test schema.

## Decision 9 (F1 design D5, D6): writer classes, acquisition recording, digest confirmation

Questions asked by the main session, with the owner's answers, verbatim:

> D5: do you confirm the writer classes (7 take part, 2 separate, 6 refused), with the legacy command-line exports kept outside the HG4 check and an owner procedure on withdrawal?

**"Confirm"**

> D6: record downloads with the fetch route, a sidecar record per file (role, not name), and your confirmation of the file hashes afterwards, using the files already on disk?

**"Yes, as described (Recommended)"**

> Do you confirm these hashes as the files you downloaded? AAPL prices 066c65e6e7ce61c0…b1b9d1fb (2026-10-01); OpenFIGI AAPL b2aaeb7b71166529…889c3ccc (both requests, today).

**"Yes, these are mine"**

What this means:
- **D5** (design §5): W01–W15 are classed as the design states:
  - participate (7): W03 (offline only), W04, W05, W06, W11, W13, W14;
  - proven separate (2): W02, W07;
  - refused (6): W01, W08, W09, W10, W12, W15. W15 becomes participating at R7.

  The legacy CLI and OS exports (W12) stay outside the HG4 runtime and are never the source of
  expected values. On withdrawal, the limit is disclosed and the owner follows a procedure: move the
  raw files aside and do not run the legacy tools.
- **D6** (design §6):
  - **Route:** the download tool's `fetch` for prices.
  - **Records:** a canonical sidecar acquisition record per file. It holds the payload and manifest
    SHA-256, the approving decision record (PD id and sha), the role "designated human product
    owner" (not the personal name), the request, the tool and the terms-check reference.
  - **Agent files:** agent manifests (v2) are refused in the real scope.
  - **Files:** the files already on disk are used, with no new download.
- **The owner's digest confirmation** (the binding control under design §6.3; an attestation, not
  authentication):

  | File | Payload SHA-256 | Manifest SHA-256 |
  |---|---|---|
  | `alphavantage.us/quote/2026-10-01/AAPL_compact.csv` | `066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb` | `268535ddc8b6284a144cbe810668a3586a9e574f257b438794bbe08c1f0efb82` |
  | `openfigi/identity/2026-10-23/AAPL_XNGS.json` | `b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc` | `cb4d862d37e628b31c7a009f53d461188583e2090934de2bb080c08e21963c8d` |
  | `openfigi/identity/2026-10-23/AAPL_UW.json` | `b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc` (identical bytes) | `7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738` |

  (Paths are relative to `data/marketdata/files/`.)
- **Note for the engineer:** the two OpenFIGI payloads are byte-identical, and `md_file` keeps one
  manifest per payload SHA (W04). Only one of the two manifests can enter a release. Prefer
  `AAPL_UW.json`, whose request names the exchange code directly.
- The NYSE calendar file (`calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json`) is the
  owner-checked calendar already registered under HG2 condition 4. It needs no new confirmation
  here.

## Decision 10 (F1 design D7): build order

Question asked by the main session, verbatim:

> D7: do you confirm the build order R0–R8 as adjusted, with the design revised to match PD-0066 and re-reviewed before R1 starts?

Owner's answer, verbatim: **"Confirm (Recommended)"**

What this means:
- **R0 is this record.** Decisions 5–10 settle D1–D7. The one remaining item is the quant-analyst
  confirming that the constructed AAPL ledger keeps `state_kind = ACTUAL`, marked by its origin
  fields (design §1.1). That is a confirmation, not an owner decision.
- **Before R1:**
  1. The engineer revises `implementation/CP7_F1_REAL_PATH_DESIGN.md` into a decided version
     matching this record:
     - B, a separate database, S2;
     - R-GW, content hash, the new scoped contract, the owner as sole publisher;
     - X1 with `valid_until` 2027-09-01 and human-recorded renewal, all rights off on end;
     - the confirmed patch fates;
     - the test-switch scope in one product module, with `INVENTED_REAL_SHAPED_TEST` removed;
     - the D5 classes, and D6 with the existing files.
  2. The technical-reviewer checks the revision.
  3. It is committed when the owner asks.
- **Alongside, the quant-analyst's follow-ups** in `methodology/CP2_MARKET_DATA_CONVENTIONS.md`, each
  reviewed:
  - the `TIME_SERIES_DAILY` label source moves `MEMORY` → `DECLARED` (decision 3);
  - A.6 `UW`/`XNGS` moves `MEMORY` → `OBSERVED` (decision 4);
  - the Ruling 6.5 claim limits gain "dividend component UNVERIFIABLE";
  - the `state_kind` confirmation.
- **Then R1 → R8 in the design's dependency order:**
  1. R1 and R4a;
  2. R2;
  3. R3 and R4b;
  4. R5 and R6;
  5. R7;
  6. R8.

  Each step is built, independently reviewed and committed. R1 includes the X1 lease. R6's
  inventory of the owner's environment needs the owner's go-ahead. R7 uses the new scoped contract
  after its review. R8 is the owner's publish, the real run, the UAT and the HG4 package.

This record approves no gate, publishes nothing, and installs nothing into an existing database.

## Still open after this record (not decided here)

- Confirming the CN calendar packet (`reviews/CN_CALENDAR_CHECK_PACKET.md`) and registering
  CN_A_SESSIONS (HG2 condition 4 for CN).
- `market-data/1.15` OP-1 (A.5 CN source order), OP-3, OP-4 and OP-6.
- L-2/N-1: bump `CONVENTION_SET`/`PROFILE_SET_VERSION` to `market-data/1.15`, or confine the V0 date
  list to the CN route.
