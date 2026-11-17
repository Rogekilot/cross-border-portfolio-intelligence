# CP2 market-data conventions: FX fixing, prices, adjustment, reconciliation, freshness, corporate actions

**Author:** `quant-analyst` subagent, dispatched by the main session (PM), 2026-10-01.
**Convention set ID:** `market-data/1.16` (supersedes `market-data/1.15` and earlier; 1.16 issued
2026-10-24, by a `quant-analyst` subagent dispatched by the main session).

(Header as issued for 1.11: "`market-data/1.11` (supersedes `market-data/1.10` and earlier; 1.11
issued 2026-10-02)"; for 1.12: "`market-data/1.12` (supersedes `market-data/1.11` and earlier;
1.12 issued 2026-10-02)"; for 1.13: "`market-data/1.13` (supersedes `market-data/1.12` and
earlier; 1.13 issued 2026-10-03)"; for 1.14: "`market-data/1.14` (supersedes `market-data/1.13`
and earlier; 1.13 and 1.14 issued 2026-10-03)"; for 1.15: "`market-data/1.15` (supersedes
`market-data/1.14` and earlier; 1.15 issued 2026-10-23, by a `quant-analyst` subagent dispatched by
the main session during the unattended night run of PD-0065)".)

**Change note, 1.15 → 1.16.** This version records the owner's readings and observations of
2026-10-24 (PD-0066 decisions 2–4 and 10; PD-0067 decisions 1–6). It also answers the open LOW
findings of the 1.15 review (`reviews/TECH_REVIEW.md`, "market-data 1.15 and CN calendar packet
(2026-10-23)", F-1 to F-7) and rules on the questions the engineer raised in the A-share route rounds
(same file, "A-share route fix round", and `STATUS.md` item 9 "Found in passing"). Finally, it
confirms the `state_kind` encoding of `implementation/CP7_F1_REAL_PATH_DESIGN.md` §1.1.

It approves nothing, admits nothing and decides nothing for the owner. The text of 1.15 is this file
at commit `44a40e8` (SHA-256 `<private pin, PD-0083>`).
No network was used. The payloads I read are:
- the two 264-byte OpenFIGI files of 2026-10-23 (`AAPL_UW.json` and `AAPL_XNGS.json`);
- the 2026-10-01 OpenFIGI files `AAPL_US.json` and `AAPL_XNAS.json`, on which Ruling 7.3 items 8 and 9
  rest (the composite and share-class equality, and the observed negative). The draft's list left these
  out (fix round 2, review R2-C8 (b));
- the AAPL CSV.

I re-hashed each, read the OpenFIGI records, and counted the CSV's decimals and dates. I also read the
registered NYSE and CN calendar files. **No expected value in 1.16 comes from running `src/`.** In the
fix rounds I called `src/` functions read only, to establish facts about the code, never an expected
value:
- `FileStore.index()` on the data root: in round 1 it refused (two manifests of one payload); in round
  2, after the owner-approved move of `AAPL_XNGS.json`, it built, with 15 entries (Ruling 7.3 item 9);
- in round 2, the project's digest functions on the re-issued registry files (§11 item 35), so the
  engineer can check the copies.

- **The label source of Alpha Vantage `TIME_SERIES_DAILY` moves from `MEMORY` to `DECLARED`** (PD-0066
  decision 3; §9B item 4 (d); OP-5). On 2026-10-24 the owner read the live documentation and reported
  that the call is "raw as traded".
  - **This is a declaration by the vendor, not a verification.** No Test V1 event and no Test V4
    record exists for any Alpha Vantage file. So the series' label status stays `UNVERIFIABLE`, and
    V0–V3 (and V4 once built) still run on every file (§9B item 4 (a)–(c), unchanged).
  - It applies to `alphavantage.us`, and to `alphavantage.cn`, whose documentation shows `.SHH`/`.SHZ`
    as supported on the same call. For `alphavantage.cn` it relaxes nothing: admission still needs
    Ruling 7A.3 (c) 5, which is V4 for both components.
  - A stored result whose manifest cites 1.15 or earlier keeps the `MEMORY` it recorded, and its
    wording may not say `DECLARED`. The reading reaches a result only through a manifest that cites
    1.16. That is a statement about stored records, not a test that a 1.15 manifest reproduces under
    1.16 code (fix round, review C-3).
- **Ruling 7A.1's suffix → MIC mapping is `DECLARED` on the owner's reading** (PD-0066 decision 3).
  1.15 called it `DECLARED` on a summarizer read, which was mislabelled (review F-6 (a)). The status
  is unchanged; its basis is now a human reading.
- **Appendix A.6: `UW` / XNGS (XNAS) moves from `MEMORY` to `OBSERVED`** (PD-0066 decision 4), on the
  owner's two OpenFIGI files of 2026-10-23 (payload SHA-256 `b2aaeb7b…889c3ccc`). Since the owner's
  move of 2026-10-24, `AAPL_UW.json` is the one in the indexed store and `AAPL_XNGS.json` is kept,
  unchanged, under `data/marketdata/observations/` (Ruling 7.3 item 9).
  - Ruling 7.3 items 6 and 8 are updated.
  - New item 9 states what now attaches to AAPL's XNAS listing:
    - `figi` `BBG000B9Y5X2`;
    - `composite_figi` `BBG000B9XRY4`;
    - share class `BBG001S5N8V8`.
  - New item 10 is a fail-closed consistency test between FIGI levels.
- **Ruling 6.5:**
  - item 2 is reworded: it holds for the **units**; the price basis rests on the label (review F-5);
  - item 5 gains the calendar condition on `E(D, R)` (review F-4);
  - item 6's claim limits are a numbered list, with **"the dividend component is `UNVERIFIABLE`"**
    as its own item (PD-0066 decision 2; review F-2 of the F1 final check), and with the label
    source `DECLARED`;
  - item 8 is marked decided (OP-2 (a), PD-0066 decision 2);
  - new item 9 **confirms `state_kind = ACTUAL`** for the project-constructed AAPL ledger, with
    conditions;
  - new item 10 recommends a human look at EDGAR over `E(D, R)` before the run (review F-5). A hit
    stops the run and returns the decision to the owner, whatever SEC EDGAR's registration state
    (fix round).
- **Ruling 3.2:**
  - **Item 1 (review F-1).** In the synthetic world, a synthetic filing-role record is a V1 event for
    a synthetic series, as Ruling 4.8 item 4(a) allows for corroboration. Read literally, 1.15 left
    no synthetic V1 event.
  - **Item 3 (review F-4).** The calendar must cover `E` only as far as needed to place a V1 event.
    The coverage-gap rule applies only to a V1 event dated after the calendar's coverage `T`, **and
    then only when `N(R)` is also undetermined** (fix round). Example 3-G.
  - **Item 4 (fix round).** Test V4 clears an exposure only where Ruling 3.3 establishes `RAW` for
    `X`. An equality alone does not. Example 3-F (e).
- **Ruling 3.3 (review F-3).** The V4 table is keyed on ex-dates in `(d, N(R)]`, the exposure window
  of `d`, in session dates. 1.15 wrote `(d, R]`. A new soundness condition: when a consolidation
  shares that window with another event, an equality establishes nothing. The condition reasons over
  the events recorded in `M`, and the residual of unrecorded events is stated (fix round). Example
  3-F.
- **Test V0 (1.16): two rows for one session date make the series `CONTRADICTED`, in every market**
  (the engineer's question; the "pinned known gap"). The rows are keyed on the parsed date. Example
  3-E.
- **Appendix A.4 item 7 applies on every route, US included** (the engineer's question; review F-7).
  It is a refusal on the decimals the text **shows**, trailing zeros included. That count is not the
  value's decimals, which the grid check uses. Example 3-E.
- **Ruling 4.7, new item 6: the per-reading form of A.5** (reviews M-1, R-1 and R-2 of the A-share
  route):
  - the MIC → market table gains ARCX, BATS and XASE (US);
  - an unmapped MIC (BJSE, for example) refuses the reading;
  - a source with no profile never supplies a real price reading;
  - a profiled source's corporate-action records pass the same admission conditions as its prices
    (fix round);
  - a filing source declares its markets in an Appendix A.3 **filing profile**, and a source with no
    profile of either kind supplies no real corporate-action record (fix round 2, review R2-C5);
  - the five gate labels are **admission refusals, not reason codes**.
- **Test V0-FX (1.16): a fixing date stated twice in an FX file excludes every currency series read
  from that file**, whole (fix round 2, review L-4). One rule for one defect, as for prices.

  Ruling 2.2 item 1 gains the three US zones.
- **Ruling 4.7 item 1: `NO_ADMITTED_SOURCE` is the cause only when `M` holds no series of the listing
  at all.** Example 7A-G2 (c) therefore names V0 alone.
- **Ruling 2.1: the official close is the close the exchange publishes under the rules in force on the
  session's date.** This answers the reviewer's point on SSE funds, which gained a closing call auction
  only with the 2026 revision (a search summary). The after-hours fixed-price session does not move
  the close or the 15:00 scheduled close. New MD-OI-19 covers volume.
- **Ruling 7A.1 item 4:** the vendor id is kept in the reading's lineage and is never handed to the
  resolver. This conforms to the item (the engineer's question).
- **Ruling 7A.2 and A.1 (review F-6 (c)):** "refusal-only" holds only if the MEMORY grid is not looser
  than the true one.
- **Ruling 7A.3:**
  - item 3 statuses: (a) is recorded in `SOURCES.json` (review F-2, resolved); (b) is **met**, by the
    registered CN calendar (PD-0067 decision 1, SHA-256 `f357b7d4…`); (c) has its plan approved
    (PD-0067 decision 3) but no file; (e) has an intended order (PD-0067 decision 2), and admission
    still needs a new owner decision;
  - item 5's two memory statements are tagged (review F-6 (b)).
- **§9D (new):** rulings on the engineer's seven questions.
- **§10.1** records what PD-0066 and PD-0067 decided on OP-1 to OP-6. **§12** gains items 23–26
  (MEMORY, a search summary, or observed for AAPL only, as marked). Item 23's first point is used
  permissively, for `Listing.figi` only (fix round). **§13:**
  - MD-OI-18 is closed;
  - MD-OI-14, MD-OI-15 and MD-OI-16 are updated;
  - MD-OI-19, MD-OI-20 and MD-OI-21 (fix round: the hfq residual) are new.
- **Ids for the engineer (§11 item 32):**
  - convention set `market-data/1.16`, in all eight label constants together, the five per-rule ids
    included (fix round 2, review R2-C2);
  - profile set `market-data/1.16#profiles/5`. This confirms the 1.15 track's
    `market-data/1.15#profiles/4` and states a rule: the counter moves with the content, and only
    then. Round 2 fixes the rule's scope: every value the profiles module transcribes (review R2-C4);
  - A.6 table `market-data/1.16#a6/2`. Round 2 rules that the A.6 id names the version that introduced
    its content, so the 1.15 code's `market-data/1.5#a6/1` conforms (reviews L-3, R2-C4).
- **Engine behaviour changes** (§11 items 23–35, a later increment after the 1.15 label move):
  - the label source read from profile data;
  - A.6 `UW`, the FIGI attachment and the level-consistency test;
  - V0 duplicate dates in every market;
  - A.4 item 7 on every route;
  - the per-reading gate with the MIC table, the profile-less refusal and the gate labels;
  - the `NO_ADMITTED_SOURCE` exclusivity;
  - the V4 window and the consolidation condition (when V4 is built);
  - the synthetic V1 events, the coverage clause of `E`, and item 4's V4 clearing through Ruling 3.3
    (when V1 and Ruling 3.2 item 4 are built);
  - the corporate-action admission conditions and the share-class consistency test (fix round);
  - the filing-profile refusal for corporate-action records (fix round 2);
  - V0-FX for a duplicated fixing date (fix round 2);
  - the origin fields' conditions (F1 build);
  - the separate dividend claim limit (F1 R5/R7);
  - the ids, and the registries re-issued with each label move (§11 item 35).
- **The 1.15 review's findings, each with its resolution:**

  | Finding | Resolution in 1.16 |
  |---|---|
  | F-1: Ruling 3.2 item 1 shut synthetic filing records out of V1 | **Fixed.** A synthetic-world exception, on the Ruling 4.8 item 4(a) model (Ruling 3.2 item 1). |
  | F-2: "recorded in `SOURCES.json`" was not yet true | **Resolved by the record.** The `alphavantage.cn` entry exists (commit `f42efa0`). Ruling 7A.3 (a) now says so. |
  | F-3: Ruling 3.3 keyed on `(d, R]` against Ruling 3.2 item 4 | **Fixed.** Keyed on `(d, N(R)]`, with the consolidation condition. In the fix round, Ruling 3.2 item 4 was brought in line: it clears only where Ruling 3.3 establishes `RAW` (reviews M-1, C-1). Example 3-F (a)–(e). |
  | F-4: whether `E` must be covered with no V1 event | **Ruled.** Only to place a V1 event dated after the coverage, and then only when `N(R)` is also undetermined (fix round, reviews C-2, L-1). Ruling 3.2 item 3; Ruling 6.5 item 5 and the interim rule follow it. Example 3-G (a)–(d). |
  | F-5: the exposure rule cannot fire for HG4, and item 2 overstated | **Fixed and mitigated.** Item 2 now speaks of the units. The residual is listed in claims C-1, N-1 and N-3. Item 10 recommends the EDGAR look. Whether to require it is the owner's call. A hit stops the run (fix round). |
  | F-6 (a): the suffix map labelled `DECLARED` on a summarizer read | **Resolved by PD-0066 decision 3.** It is `DECLARED` on a human reading. |
  | F-6 (b): two untagged memory statements | **Fixed.** Tagged MEMORY (Ruling 7A.3 item 5). |
  | F-6 (c): the "refusal-only" claim | **Fixed.** Now with the proviso "not looser than the true grid" (Ruling 7A.2; A.1). |
  | F-7: G3-d expected a check `src/` lacked | **Engine side closed by B2** for CN. **Method side:** A.4 item 7 is named as a behaviour to build on every route (§11 item 26). |

- **The fix round of 1.16** (the independent review of this draft, 2026-10-24). Each finding, with its
  resolution:

  | Finding | Resolution |
  |---|---|
  | M-1, C-1 (MEDIUM): Ruling 3.2 item 4 still cleared on any V4 equality, against Ruling 3.3's consolidation condition | **Fixed.** Item 4's condition and "How it clears" now require that Ruling 3.3 *establishes* `RAW` for `X`. The F-3 note in Ruling 3.3 says so. New Example 3-F (e) is C-1's scenario. §11 item 30 tests it through item 4. |
  | C-2 (MEDIUM), L-1: the `X > T` clause applied even when `N(R)` is known | **Fixed.** The gap applies only when `X > T` and `N(R)` is undetermined, with the case analysis written out (Ruling 3.2 item 3). The interim rule and Ruling 6.5 item 5 follow. New Example 3-G (d). "After `T`" replaces "beyond the coverage". |
  | C-3 (MEDIUM): §11 item 23's 1.15-reproduction test | **Withdrawn.** It is replaced by a statement about stored records (Ruling 6.5 item 6) and a "Must not decide" against multi-version profiles. |
  | C-4 (MEDIUM): two manifests of one payload | **Corrected and routed.** Ruling 7.3 item 9 states the `src/` refusal, which I confirmed read-only, and its consequence: every real build from `data/marketdata` is refused today. The remedy is routed to the owner or the PM before R4a or R8 (§11). Item 24's test is replaced. |
  | L-2: two residual statements too narrow | **Fixed.** (a) Ruling 3.3 reasons over the events recorded in `M`, and the unrecorded-event residual is stated with an example. (b) N-2 is qualified by anchor. The hfq residual is stated in Ruling 3.2 item 3 and as MD-OI-21. |
  | L-3, C-8: an EDGAR hit before registration | **Fixed.** A hit stops the run and reopens OP-2 (a), whatever the registration state. V4 alone does not lift the interim refusal (Ruling 6.5 item 10). |
  | L-4: memory labels | **Fixed.** The §12 1.16 header names item 23's permissive use. A.3's `declared_by_source` comments no longer say MEMORY beside `DECLARED`. |
  | L-5, C-10 (second half): the CP6 key "includes the portfolio" | **Fixed.** Condition 3 cites CP6's scope requirement and `history_problem`'s `SCOPE_MISMATCH` check, not the semantic key. |
  | L-6, C-5: the gate on citing 1.16 | **Fixed.** Items 23–28, 32 and 33 gate the citation. Items 29–30 keep "not built" standing under 1.16, as the 1.15 move does. Item 31 binds the F1 path (§11). *Superseded in fix round 2 (reviews L-2, R2-C3): items 23–28 and 32–35 gate it, and every unbuilt behaviour of items 17–22, 29 and 30 keeps its own line.* |
  | C-6: corporate-action gate without admission | **Fixed.** A profiled source's records pass conditions 1–3, as `src/` already does. §11 item 27 adds the test. |
  | C-7: the fixture-impact reason | **Corrected.** The cp3 and cp4 golden US files do carry the label source in lineage. It moves to `:DECLARED`, and no number, state or pin moves (below). |
  | C-9: the share-class half untested | **Fixed.** §11 item 24 gains the share-class test. Ruling 7.3 item 10 notes that this half is new behaviour. |
  | C-10 (first half): where questions 6 and 7 are recorded | **Corrected** in §9D. |

- **Fix round 2 of 1.16** (the re-reviews of 2026-10-24: "market-data 1.16 — method review — re-review"
  and "… consistency with code and records — re-review"). Each finding, with its resolution:

  | Finding | Resolution |
  |---|---|
  | M-1 (method), R2-C1 (MEDIUM): Example 3-F (e) gave 640.00 for the one-event series | **Corrected, re-derived by hand.** At `d` = 09-30, the consolidation `SPLIT (2, 3)` alone maps `× 3/2`: 320.00 × 3/2 = **480.00**. The split `SPLIT (3, 2)` alone maps `× 2/3`: 320.00 × 2/3 = 640/3 = 213.33…. Both: 320.00 × 3/2 × 2/3 = 320.00. The draft's 640.00 was case (b)'s `SPLIT (1, 2)` value. No outcome changes. |
  | R2-C2 (MEDIUM): §11 item 32 left out the per-rule ids | **Fixed.** Item 32 names all eight label constants, the five per-rule ids included. They move together. |
  | L-1 (method): Ruling 7.3 item 9's "iff" left out item 10 | **Fixed.** Item 9 attaches iff item 3's checks and item 10's level-consistency checks all pass. |
  | L-2 (method), R2-C3: the 1.16 gate carried "not built" for V1, V4 and item 4 only, and leaned on uncommitted code text | **Fixed.** The gate is self-contained in §11. Every engine behaviour of §11 items 17–22, 29 and 30 that is not built when a manifest cites 1.16 keeps its own "not built" line. The 1.15 note's sentence on citing 1.15 is reconciled: PD-0067 decision 6 overrode it for 1.15, and §11's rule governs from 1.16 on. |
  | L-3 (method), R2-C4, R2-C8 (a): the A.6 id, the counter's scope, the A.6 comment | **Ruled.** The A.6 id names the version that introduced its content (`market-data/1.5#a6/1` conforms under 1.15; `market-data/1.16#a6/2` under 1.16). The profile counter counts every value the profiles module transcribes (A.1–A.5, the Ruling 2.2 item 1 zones and the Ruling 4.7 item 6 MIC table), never a comment. The A.6 comment now says the table content changed. |
  | L-4 (method): duplicate FX dates (pre-existing) | **Ruled.** Test V0-FX (1.16): a fixing date stated twice excludes, whole, every currency series read from that file (`V0_FX_DUPLICATE_DATE`). Serving the first row chose between two statements, which §11 "Must not decide" forbids. New §11 item 34. |
  | L-5 (method): the fixture note counted JSON decimals | **Corrected.** The note now counts the payload text the kits write: US 4, CN 1, HK float32 (exempt). |
  | R2-C5: a filing source's markets had no field to read | **Ruled.** A filing source declares its markets in an Appendix A.3 **filing profile**, not in `SOURCES.json`. No registry field is added and no registry digest moves. A source with no profile of either kind supplies no real corporate-action record (Ruling 4.7 item 6). |
  | R2-C6: Ruling 3.2 item 5's lineage against Example 3-G (d) | **Fixed.** Item 5 has three exclusive cases: the V1 events in `E`; "no V1 event in `E`", with the later events listed as outside `E`; or "no V1 event in `M`", only when `M` holds no V1 event of ℓ dated after `d_p`. |
  | R2-C7: the registries' version move was asserted but not routed | **Routed, and done for 1.15.** The three registries are re-issued today, citing `market-data/1.15`: `risk/1.10`, `performance-registry/1.1` and `diversification/1.1`. New §11 item 35 makes the re-issue part of every label move. For 1.16 it gates the citation. |
  | R2-C8 (b): the read list left out `AAPL_US.json` | **Fixed** in the preamble above. |
  | (new fact, 2026-10-24) the duplicate OpenFIGI manifest was moved | **Recorded.** The owner approved moving `AAPL_XNGS.json` and its manifest, unchanged, to `data/marketdata/observations/openfigi/identity/2026-10-23/`. I re-hashed both: payload `b2aaeb7b…889c3ccc`, manifest `cb4d862d…63c8d`, as before. `FileStore.index()` builds again (15 entries, read only). Ruling 7.3 items 6, 8 and 9, A.6, §11 item 24 and the PM routes are updated. |

- **No expected value in any earlier example changes.** Example 7A-G2 (c) already named only V0 and
  2026-09-25. Examples 3-E, 3-F and 3-G are new, and their values are derived by hand in place. That
  includes the fix round's 3-F (e) and 3-G (d). **Fix round 2** corrects one hand-derived value in
  3-F (e), the consolidation-only series at 09-30: 480.00, not 640.00 (derivation above and in place).
  No outcome in any example changes.
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves these **unaffected**:
  - `cp1_golden/1.1`;
  - the four `cp3_golden` parts;
  - `cp4_golden` parts 1–4;
  - `cp5_golden`;
  - `cp6_golden`.

  The reasons:
  - Their price files are expanded one row per session, so no date repeats.
  - **A.4 item 7 counts the decimals the payload text shows**, so the count is of what the fixture
    loaders write, not of the fixture JSON (fix round 2, review L-5; the draft counted the JSON, where
    every close has 2). The loaders (`tests/product/marketdata_exit_kit.py`, used by the cp3 and cp4
    kits) write:
    - US files (Alpha Vantage layout): every price with **4** decimals (`:.4f`), against
      `alphavantage.us` `delivered_dp` 4;
    - CN files (Eastmoney layout): every price with **1** decimal (`:.1f`), against `delivered_dp` 2. No
      CN fixture close has a nonzero second decimal (I checked every CN step value), so the 1-decimal
      text is the exact close;
    - HK files (Sina layout): float32 renderings, which A.4 item 7 exempts (it applies to `TEXT_DECIMAL`
      and `FLOAT64` fields with a declared `delivered_dp`).

    So no fixture file is refused. A kit change that writes more decimals than a profile's
    `delivered_dp` would refuse every such synthetic file. That would be a finding, not a fixture change.
  - **FX files are written one row per fixing date** (each FX block's `rows_rule`), so V0-FX's
    duplicate-date rule (fix round 2) excludes nothing.
  - **The fixtures' corporate-action records are synthetic** (upstream `synthetic`), so the
    filing-profile refusal of Ruling 4.7 item 6 (fix round 2) does not apply to them (Ruling 4.8).
  - No fixture listing uses ARCX, BATS, XASE or an unmapped MIC.
  - No fixture asserts `NO_ADMITTED_SOURCE` beside an excluded series.
  - Ruling 3.2 item 1's synthetic clause is what lets the SYNS, SYNT and SYN43 splits verify, as
    the 1.15 change note expected.
  - **Lineage does change, by design.** The draft said the fixtures declare `RAW`, so no label source
    enters their lineage. That was wrong (fix round, review C-7).
    - The `cp3_golden` and `cp4_golden` loaders write their US files with adjustment `UNDECLARED`
      and request function `TIME_SERIES_DAILY` (`tests/product/cp3_golden_kit.py`, `cp4_golden_kit.py`).
    - So their US readings carry the label source
      `PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:MEMORY` today, and `:DECLARED` once
      §11 item 23 is built.
    - That moves lineage strings, and any digest or baseline taken over canonical lineage
      (`marketdata/canonical.py` serializes `adjustment_label_source`).
    - It moves no number, state, reason code or fixture expected value.
    - It moves no `FIXTURE_PINS` entry. Those hash the fixture JSON, and no fixture JSON names a label
      source.
    - The pins on the string itself (`test_marketdata_cp2c2_conventions13.py`,
      `test_marketdata_alphavantage_cn.py`) are re-recorded under §11 item 33, with this reason.

  If a number, state, reason code or fixture expected value moves, that is a finding, not a fixture
  change.
- **Companion citation.** A manifest cites `market-data/1.16` once §11 items 23–28 and 32–35 are all
  built. Items 29–31 do not gate it, and every unbuilt behaviour keeps its "not built" line (§11, "When
  a manifest may cite 1.16"). 1.16 changes no `performance`, `risk`, `diversification` or `insight`
  ruling.
- **The registries move with the code label, by re-issue** (fix round 2, review R2-C7; `risk` Ruling
  9.2 (1.10)). The draft said only that they "move only when the code moves". The code label moved to
  `market-data/1.15` today (PD-0067 decision 6), so the three PRD §33 registries that name a
  market-data version are re-issued today under new ids, each citing **`market-data/1.15`** (not 1.16,
  which is not in code). The old files stay unchanged as records:

  | Family | Old file (record) | New file | New id |
  |---|---|---|---|
  | risk | `RISK_1.9_REGISTRY.json` (`risk/1.9`) | `RISK_1.10_REGISTRY.json` | `registry_id` `risk/1.10` (a new `risk` convention id; `CP4_RISK_CONVENTIONS.md` change note 1.9 → 1.10) |
  | performance | `PERFORMANCE_1.12_REGISTRY.json` (`performance-registry/1.0`) | `PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json` | `appendix_id` `performance-registry/1.1`; `registry_id` stays `performance/1.12` (`CP3_REGISTRY_APPENDIX_INVENTORY.md`) |
  | diversification | `DIVERSIFICATION_1.0_REGISTRY.json` (`diversification/1.0`) | `DIVERSIFICATION_1.1_REGISTRY.json` | `registry_id` `diversification/1.1` (a new `diversification` id; `CP5_DIVERSIFICATION_CONVENTIONS.md` change note 1.0 → 1.1) |

  Each conventions document lists every field that changed. The engineer syncs the byte copies in
  `src/` (§11 item 35). When the label moves to 1.16, the three are re-issued again first.

**Change note, 1.14 → 1.15.** This version answers item 2 of the verdict in
`reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md` (split semantics) for the HG4 US single-date check of
`reviews/CP7_E9_REAL_SOURCE_AND_UAT_PACKET.md`, and writes the conventions of the Alpha Vantage
A-share route approved for reading in PD-0063, **without admitting it**. It was written without
network access and without reading any downloaded payload beyond what Example A-1 already quotes. It
approves nothing and decides nothing for the owner: §10 (1.15) lists the owner proposals.

- **Ruling 6.5 (new): a valuation on the date a position opens.** The HG4 check (10 units opened on
  2026-09-30, valued on 2026-09-30, plus USD 500) needs **no corporate-action file**. No split, recorded
  or not, can change the units of that valuation. So nothing is inferred from the lack of records, and
  Ruling 6.4 item 4, Ruling 6.4d case (d) and the E9 rule "an empty response is never proof of complete
  history" all hold. The ruling states what the result may and may not claim. A holding value **may**
  be `AVAILABLE` while the series' split label is `UNVERIFIABLE`. The ruling also clarifies (no change)
  that the Ruling 6.4a windows have effects only for accounts that hold units at the ex-date.
- **Ruling 3.2 (new): V1's reference events, the compact-window label, and split-label exposure.**
  - A V1 reference event must come from a filing-role record. A feed-only record never is one.
  - The label of a 100-session window is `UNVERIFIABLE` unless a decisive filing-attested split
    lies inside it. Absence never makes the label `VERIFIED` or "moot". The A.3 phrase
    `split_component_moot_if` is withdrawn.
  - **New suppression:** a reading at session `d_p` supplies no price for any `D` if both of these
    hold:
    - a filing-attested split has its ex-date in the reading's **exposure window**
      `(d_p, N(R)]`;
    - the file's RAW reading has not been established for that split.

    The result is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, with lineage cause
    `SPLIT_LABEL_EXPOSED`.
- **Ruling 3.3 (new): Test V4, the exchange reference check.** A human-recorded, exchange-published
  official close must equal the series' close. It verifies the RAW label for an event that lies
  between that date and the vintage. It is the only label test available for CN, and it is an
  admission precondition there (Ruling 7A.3).
- **Ruling 4.5 (1.15): a ratio delivered as a decimal factor.** It agrees with the filing's exact
  ratio within its rendering bound `½ × 10^(−d)`. A corroborated event carries the filing's ratio.
- **Ruling 7.4 (new): a corporate-action type is granted to undocumented feed fields only from
  observation.**
  - Alpha Vantage `SPLITS` today: **no grant**. Every record is `UNMAPPED_ACTION`, and the adapter
    outputs no `SPLIT`.
  - These must be observed first:
    - O-1: the shape of the response;
    - O-2: a forward split whose record, payable and ex-dates differ (AAPL 2020);
    - O-3: a reverse split, which rules out a magnitude-only ratio.
  - A record of a ledger listing that stays unmapped gets a lineage flag only.
- **Ruling 7.5 (new): empty and non-data responses.**
  - An empty response is stored. It means "zero records at `R`", and its coverage is
    `NOT_ESTABLISHED`. It has no effect on any computation and is never "complete".
  - A notice, error or rate-limit body is an acquisition failure, never an empty response.
- **Ruling 7.6 (new): feed/filing pairs.**
  - US: Alpha Vantage `SPLITS` plus SEC EDGAR filings.
  - CN: no admitted feed yet, plus cninfo announcements.
  - Also: what applies when only one side exists, and how a filing record is prepared.
- **§7A (new): the Alpha Vantage A-share route, pending observation and not admitted.**
  - Ruling 7A.1: `.SHH` → XSHG, `.SHZ` → XSHE, and nothing else is inferred. Resolution is by
    (MIC, code), and B-shares are out of the route.
  - Ruling 7A.2: the A.1 CN decimals apply unchanged. §12 items 10–11 are still MEMORY.
  - Ruling 7A.3: the observations required before admission. Until then CN listings keep
    `NO_ADMITTED_SOURCE`.
  - Synthetic golden examples 7A-G1 to 7A-G4.
- **Appendix A.3:**
  - an `alphavantage.cn` profile (`TO_OBSERVE`, provisional fields for synthetic tests only);
  - an `alphavantage.us.splits` entry with no grant;
  - the `alphavantage.us` moot line is replaced by a pointer to Ruling 3.2.

  **A.5 is unchanged**: CN stays `[]`. The CN order is an owner proposal (OP-1).
- **Engine behaviour changes:**
  - Ruling 3.2 item 4, which must be **built together with Test V1**. V1 is not built
    (`src/marketdata/market11.py` lists it as "not built"). Until both exist, the interim pre-run
    check of Ruling 3.2 item 6 applies.
  - Test V4 as a new human-authored input.
  - The Ruling 4.5 decimal comparison.
  - The Alpha Vantage `SPLITS` adapter emits only `UNMAPPED_ACTION`, plus the lineage flag.
  - Classification of empty and non-data responses.
  - The `alphavantage.cn` route: vendor-id grammar, resolution and the not-admitted gate.
- **No expected value in any earlier example changes.**
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves these **unaffected**:
  - `cp1_golden/1.1`, which has no market data;
  - the four `cp3_golden` parts;
  - `cp4_golden` parts 1–3;
  - `cp5_golden` and `cp6_golden`, which hold no `SPLIT`.

  Ruling 3.2 item 4 could bite only where a fixture holds a filing-side split after a valued date,
  and three do. Each split is decisive and V1-consistent, so once V1 is built their labels are
  `VERIFIED` and nothing is suppressed:
  - `cp3_golden` part 2 (SYNS, 4:1 on 2025-03-03: 80.00 → 20.00, `R/h = (1/4)/(1/4) = 1`);
  - `cp3_golden` part 3 (SYNT, the same prices);
  - `cp4_golden` part 3 (SYN43, 2:1 on 2025-09-08: 98.00 → 49.00, `R/h = (1/2)/(1/2) = 1`).
    98.00 is the fourth value of the weekly cycle on 2025-09-05. Read as the step value 100.00, it
    gives `R/h = 0.98`, with the same outcome.

  If V1, once built, returns anything else on these, that is an engine finding, not a fixture
  change.
- **Companion citation.** A manifest cites `market-data/1.15` once its behaviour changes are
  built. No `performance`, `risk`, `diversification` or `insight` ruling changes.

**Change note, 1.13 → 1.14.** This defines the field the CP4 engineer added to carry an issuer's
stated payment in another currency (`risk` Ruling 5.5 (1.8)). It ratifies the engineer's contract
choice and states it.

- **Ruling 7.1 (1.14): `paid_amount`.** It is the per-unit amount the issuer states it pays in
  `paid_currency`, as a `Money` exact decimal. Its constraints are as the engineer built them:
  - positive;
  - present only with `paid_currency`;
  - `CASH_DIVIDEND` only;
  - `paid_currency` differs from the declared currency;
  - in canonical form only when stated.

  `paid_amount` governs over `issuer_fx_rate`. It is never derived from our FX.
- **Ruling 4.5 (1.14): corroboration with paid fields.** The declared fields are compared as
  before. The paid fields are compared only when both sides state them. One side's statement adds a
  single-source paid amount to a corroborated dividend; it does not create a disagreement.
- **Engine behaviour changes:** the validation of the new field (as built), and the 4.5 comparison.
- **No expected value in any example changes.**
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves **unaffected**:
  - `cp1_golden/1.1`;
  - the four `cp3_golden` parts;
  - `cp4_golden/1.0-part1` and `1.0-part2`.

  None of these states a paid currency. `cp4_golden` part 3 already uses `paid_currency` /
  `paid_amount` with these meanings (R5-E9, both sides stating 0.46), and it is re-issued as
  `1.9-part3` for another reason (`risk/1.9`). Its minimum becomes `market-data/1.14`. Its items
  R5-E10 (the FEED alone states the payment), R5-E11 (the FILING alone states it) and R5-E12 (both
  state different payments: `DISAGREEMENT`) pin the 4.5 comparison from both sides (review finding
  CP4F-15).

**Change note, 1.12 → 1.13.** This answers review finding CP4M-10 (`reviews/TECH_REVIEW.md` §39.5)
and the main session's fail-closed ruling on it, which I confirm. Ruling 0.1 (1.13) states two
refusals that 1.12 left implicit.

- **Item 1(b): a coverage that cannot be stated.** In a series of several files, a file whose
  coverage cannot be stated is refused: `REFUSED_COVERAGE_UNDETERMINED`. This confirms the engineer's
  fourth outcome, and the name is accepted. Without a coverage, disjointness cannot be shown, and
  inferring one from the rows lets the content define its own claim.
- **Item 1(c): rows outside the declared coverage.** In a series of several files, a file holding a
  row outside its declared coverage is refused: `REFUSED_ROW_OUTSIDE_COVERAGE`. The coverage is
  **never widened** to the hull of the interval and the rows.
- **"First row held"** in item 1's `start` applies **only** to a full-history file, which has no
  requested start. A file with a requested start has that start, whatever rows it holds.
- **Order of the checks:**
  1. identity;
  2. segmentability;
  3. coverage undetermined;
  4. row outside coverage;
  5. overlap.
- **Single-file series:** unchanged. They need no coverage under Ruling 0.1, and their rows are
  judged by Ruling 3.1 (V0 and the after-retrieval test) as before.
- **Engine behaviour changes:** the release build refuses the two new cases. The undetermined case
  is already built.
- **No expected value in any example changes.**
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves **unaffected**:
  - `cp1_golden/1.1`;
  - the four `cp3_golden` parts;
  - `cp4_golden/1.0-part1` and `1.0-part2`.

  They declare one file per series. `cp4_golden/1.3-part3` is **replaced by `cp4_golden/1.4-part3`**
  (minimum `market-data/1.13`), which adds release cases RB-6 to RB-9 and mutations M-R5 to M-R7. No
  item changes.

**Change note, 1.11 → 1.12.** This answers the CP4c engineer's question, routed by the main
session, about reading `cp4_golden/1.1-part3`'s file vintages. The question arose because I wrote,
in that fixture, several files per series, which Ruling 0.1 as written forbade.

- **Ruling 0.1 (1.12): a series may be delivered in segments.** One series may come in several
  files when the files' declared **coverage intervals** are pairwise disjoint, all conditions of
  item 2 hold, and the series is one whose published values do not depend on the retrieval (raw
  prices, ECB fixings, published benchmark levels, risk-free quotes). Vendor-adjusted series are
  never segmented.
  - Two files that cover a common date remain two vintages: building `M` fails closed, as before,
    **even if their values agree**.
  - Disjoint **points** are not enough. A later file that adds a row on a date an earlier file
    covers without a row is a revision of that date ("no print" became "a print"), and is refused.
- **The vintage is the file's retrieval time** (Ruling 2.3's definition, unchanged). **No vintage
  label goes into any identity field.** In particular, `adjustment_anchor` keeps its Ruling 2.3
  meaning (null for a raw series). A series key that carries a vintage label in the anchor makes
  each segment a separate series and bypasses this ruling's check.
- **Where the rule lives:** in the release build, once for every kind, prices included. The read
  path receives one series per key.
- **Engine behaviour changes:**
  - `from_manifests` and `_require_one_vintage`: per series key, admit disjoint coverage
    segments; refuse overlap;
  - the two merges on the risk read path (`_one_series`, `_rf_one_series`) become redundant;
  - the kit stops writing vintage labels into `adjustment_anchor`;
  - the cited id.
- **No expected value in any example changes.**
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves **unaffected**:
  - `cp1_golden/1.1` (no market data);
  - `cp3_golden/1.4-part1`, `1.2-part2`, `1.2-part3`, `1.2-part4`;
  - `cp4_golden/1.0-part1` and `1.0-part2`.

  They declare one file per series, which 1.12 admits exactly as 1.11 did. `cp4_golden/1.2-part3`
  is **replaced by `cp4_golden/1.3-part3`** (minimum `market-data/1.12`). It states the coverage of
  each vintage and adds five release-build cases (`release_cases`, RB-1 to RB-5) that bite the
  points-only reading.

**Change note, 1.10 → 1.11.** This answers review CP3-15 (`reviews/TECH_REVIEW.md` §31.1 item 4
and §32.1 item 2) and HG2 condition 1 (PD-0038).

- **New Ruling 6.4d: the confirmation-policy test, per (listing, ex-date).** Before 1.11, the
  policy gate (`DETECTION_POLICY_UNMATCHED`) was an engineer's choice (tech plan, CP3-11/CP3-15)
  with no ruling text. The rulings it serves already worked per (listing, ex-date): Ruling 4.5
  corroborates on equal ex-dates, and Ruling 6.4 item 2 detects per corroborated split. 6.4d
  makes the test normative:
  - **A policy is valid** only with a non-empty feed role and a non-empty filing role, and with
    no source in both. An invalid policy is refused when it is configured.
  - **A key (ℓ, X)** is any listing of the ledger at `L` and any ex-date `X` on which `M` (`M_t`
    in Current mode) holds a `SPLIT` record of ℓ. It is matched on **exact** ex-date equality.
    No window applies: the ±20-session window of Ruling 6.4a is not used, and an old record of ℓ
    on another date counts only for its own key.
  - **A key is unmatched if any source with a record for it is named in neither role.** This
    covers:
    - the reviewer's case, where a role has no source on the key while an unclassified source
      has one;
    - the case where only unclassified sources have records;
    - **also the case where both roles are matched but an unclassified source holds a record**
      (case (c)). That record could turn `CORROBORATED` into `DISAGREEMENT`.
  - **Not unmatched:**
    - no record at all;
    - `FEED_ONLY` or `FILING_ONLY` with every source classified. That is `SINGLE_SOURCE`, and
      silence is correct.
  - **Any unmatched key refuses the whole computation.** The state is `INSUFFICIENT_DATA` with a
    **null reason code**, and the lineage cause is `DETECTION_POLICY_UNMATCHED`. This follows the
    coverage-gap precedent for configuration defects. It is not `SOURCE_CONFLICT`, and no code is
    new (PD-0036 §2).
  - **The refusal names every unmatched key**, with listing, ex-date, unclassified sources and
    unmatched roles.
- **Beyond the review's remedy direction:** case (c) is added. A refusal limited to an
  unmatched role would let an unclassified record that disagrees go unseen. The CP3-15 fix in
  progress needs that one extra condition (§11 item 13, 1.11).
- **Engine behaviour changes:**
  - the policy gate (case (c) refuses; the refusal names unmatched keys as Ruling 6.4d item 6
    says);
  - the cited id.

  No other ruling changes.
- **No expected value in any example changes.** Examples 6-A to 6-C have no confirmation-policy
  question. Example 6-D is new.
- **Fixtures (`performance` Ruling 11.6 item 3).** This change leaves **all** of these
  unaffected:
  - `cp1_golden/1.1`: it has no market data;
  - `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2`, `cp3_golden/1.2-part3` and
    `cp3_golden/1.2-part4`.

  **Why the CP3 parts are unaffected:**
  - their `market_data` minimum is `market-data/1.10`, which 1.11 meets (item 1);
  - their only corporate-action evidence is the P13 synthetic pair (parts 2 and 3; part 4 reuses
    P13). It has one record on the side `FEED` and one on the side `FILING`, on one key. Every
    source on that key is classified, so the key is matched and detection is as before;
  - no fixture asserts `DETECTION_POLICY_UNMATCHED`, a policy refusal or a policy digest.

  No fixture version is issued, and no independent calculator changes.
- **Companion citation.** `performance/1.11` names `market-data/1.10` as its companion
  (header, §14, §16). A manifest cites **`market-data/1.11`** in its place. No `performance`
  ruling changes, so `performance` is not re-issued for this.

**Change note, 1.9 → 1.10.** This clarification was first written in place under 1.9, which was a
process error: one ID must have one text (P9). It is re-issued here under its own ID.

- **Ruling 6.4c rule 4 (clarification):** under the conservative rule, a receiver that sells part
  of the carried units stays suppressed until its first zero day. Under `FIFO/1` lot identity, the
  suppression ends on the day the last tainted unit is relieved.

**No expected value changed. No engine behaviour changed**: the engine already implements the
conservative rule, and lot identity does not exist yet.

**Change note, 1.8 → 1.9.** This version answers the CP3 midpoint review (`reviews/TECH_REVIEW.md`
§28), findings CP3-2 and CP3-3. Both concern when an F8 split suppression applies. No expected value
in any example changed.

- **Ruling 6.4c (new; CP3-2): a suppression follows the units.** Units carried out of a suppressed
  position by an internal transfer carry the suppression to the receiving position. It is decided
  by lot identity, at every scope.
- **Ruling 4.8 item 4 (new; CP3-3): synthetic corporate-action evidence.** It never causes an
  append. It **does** drive detection and suppression, because suppression creates no fact and
  only withholds a number. Corroboration happens within one world: all real, or all synthetic. A
  mixed pair never corroborates. The append bar depends on the evidence, not on whether `M` holds
  some other synthetic file.

**Change note, 1.7 → 1.8.** Written with `performance/1.0`
(`methodology/CP3_PERFORMANCE_CONVENTIONS.md` §13). Four changes; no expected value in any
example changed.

- **ECB fixing instant (Ruling 1.1, §11 item 1, §12 item 1):** the nominal concertation instant
  becomes **14:10 Europe/Berlin**, because the ECB's own page describes the concertation as
  "around 14:10 CET" (read by the main session for the calendar drafts, PD-0034). §12 item 1
  already said that a different publisher minute changes the constant in a new version. The
  publication time (16:00) is unchanged. No ordering in Ruling 1.2 changes; its hour figures are
  restated.
- **Scheduled close (Ruling 5.3 item 6, Ruling 2.2 item 3):** a calendar's scheduled close is the
  latest instant at which the session's official closing price can be determined. For HKEX that
  is **16:10**, and **12:10** on half days (the end of the closing auction session's random-close
  window). This confirms the provisional value in the HKEX draft.
- **CNH in aggregates (Ruling 1.4):** an aggregate that includes a CNH amount is
  `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`, not `LIMITED`. The excluded weight cannot be stated
  in reporting-currency terms without the missing rate, so HG1 round 4 §6 R1 cannot be met.
- **Ruling 4.7 item 3** (a total with an unpriced holding) is adopted by `performance/1.0` Ruling
  1.4, and extended there to every cause of an unvalued component.

**Change note, 1.6 → 1.7.** This version answers review finding C2-16.

- **Test V0-FX (§3, new):** an FX series with any row on a non-fixing day inside `C_ECB`
  coverage is excluded whole (`V0_FX_OFF_CALENDAR`). Rows outside coverage are not judged.
- **For both prices and FX:** a row dated after its file's retrieval could have contained it
  contradicts the series.
- No expected value changed.

**Change note, 1.5 → 1.6.** Two changes; no expected value changed.

- **Ruling 6.4a item 5 is tightened** to the rule the engineer implemented. Overlapping windows
  of two corroborated splits make both `CONFLICT_RATIO`, append nothing and suppress valuation
  from the earlier ex-date, whatever the ledger holds. The test is decided over the whole `M`.
  The wording also adds the coverage-gap case and the way a human resolution clears it (windows
  cut at the midpoint).
- **Ruling 7.3 item 4:** resolution of composite-only observations may wait until such a source
  is admitted. Until then, those observations are unresolved.
A Computation Manifest (Tech Plan §6.2) that uses any price, FX rate or corporate-action
observation cites this ID next to `ledger-replay/1.3`. A later change to any RULING creates a new
ID.

**Change note, 1.4 → 1.5.** This version answers the two methodology gaps of the CP2 fix round
(tech plan §15.18).

- **Ruling 7.3 (new) and Appendix A.6:** FIGI levels and the MIC ↔ OpenFIGI exchange-code
  table.
  - A FIGI is attached to a listing's exchange-level `figi` only from an **exchange-level**
    record (`figi ≠ compositeFIGI`) whose exchange code belongs to the listing's MIC.
  - A **composite** record (`figi = compositeFIGI`, e.g. AAPL `exchCode US`) never fills the
    listing's `figi`. It may fill `composite_figi` under the rule in 7.3.
  - This turns OpenFIGI resolution back on without inventing a venue.
- **Appendix A.3/A.4:** `delivered_dp` is declared for the refused Eastmoney and Sina-US
  open/high/low and for Eastmoney's qfq values, from the probe files. A.4 gains item 7: an
  undocumented `delivered_dp` is the maximum decimal count observed, which is conservative.
  Example 3-C is reproducible from the profile again, with the same result.

No expected value in any example changed.

**Change note, 1.3 → 1.4.** This version answers the CP2c-2 engineer's open choices on the 1.3
implementation (commit `39733e9`; tech plan §15.17). It is a version bump because these rulings
change or fix behaviour:

- **Ruling 6.4a (new):** a ±20-session linking window decides which ledger splits are compared
  with a corroborated split. This replaces the unbounded reading and the engineer's
  "explained by a corroborated split" rule.
- **Ruling 6.4b (new):** a user's reversal of a system-appended split is final within its
  window.
- **V2 (a′):** a missing `delivered_dp` stops V2 (`PROFILE_INCOMPLETE`). It is not replaced by
  `½ ulp` of binary64.
- **A.1:** the CN security class is derived from (MIC, `SecurityType`, `trading_currency`).

Clarifications that change nothing:

- a refuted re-server file takes part in the date-set check (Ruling 1.1a item 6);
- how a precision bound is stored (§9C item 6).

No expected value in any example changed. The rulings are in §9C.

**Change note, 1.2 → 1.3.** This version answers the CP2c-1 engineer's six questions on the 1.2
implementation (§9B). It is a version bump because three answers fix behaviour that 1.2 left
open, so a 1.2 manifest and a 1.3 manifest could compute different results:

- **V2 (a′):** the reference bound `δ_r` is defined per field. The close's bound of 0 does not
  carry over to open, high and low.
- **Ruling 1.1a:** a file's "coverage" for the date check is defined, and so is what a
  `REFUTED` re-server file does.
- **Ruling 1.5a (new):** the content of a central-parity series.

Clarifications that change nothing, written in place:

- Ruling 2.4 item 4a: unrecovered readings that agree are still no value and carry no status.
- §3 consequences: a dropped series stays in `M`.
- The lookup outcomes (§9B).

No expected value in any example changed.

**Change note, 1.1 → 1.2.** This version follows PD-0031 and PD-0032. Only `alphavantage.us`,
`frankfurter.ecb` and `openfigi` are admitted; no CN or HK price source is (STATUS item 17). It
also answers the CP2b and CP2c-1 engineers' questions.

- **Appendix A.**
  - The `alphavantage.us` profile is `OBSERVED` from its first real file (§A.3, Example A-1).
  - The six AKShare routes are marked `REFUSED (PD-0031/0032)`. Their observed formats stay on
    record for the parsers. A.5 primary order is reduced to the admitted upstreams.
- **Ruling 1.1a (new):** FX source preference and provenance. An ECB-direct file is preferred.
  Frankfurter v1 stays usable for development only until its provenance is confirmed by an exact
  comparison with the ECB file.
- **Ruling 2.4 item 5:** the float32 signature test applies to non-integral fields only.
  Integral fields use the spacing test (A.4 item 2).
- **Ruling 2.4 item 4a (new):** an unrecovered reading is not an admissible print.
- **Test V2:** the precision bound comes from the series' profiles, not from the caller, and the
  formulas are stated. **Example 3-C's classification is unchanged.**
- **Ruling 4.3:** two renditions from one upstream that differ give `DISAGREEMENT`, while their
  agreement is still only `SINGLE_SOURCE`.
- **Ruling 4.1a (new):** which readings are comparable. A currency mismatch is refused at
  ingest. A non-RAW reading enters reconciliation only after un-adjustment.
- **Ruling 4.7 (new):** a market with no admitted source. Ruling 4.8 (new): synthetic data.
- **Ruling 5.3 (new):** the content of a calendar file, and how a coverage gap is represented.
- **§9A (new):** the rulings on the CP2b engineer's six judgment calls.
- **No expected value in any earlier example changed.**

**Change note, 1.0 → 1.1.** This version answers the first real downloads (owner probe runs,
2026-10-01, files under `data/marketdata/files/`, read only) and records PD-0030.

- **Adjustment method becomes a formal label field (Ruling 2.3), and Test V2 is replaced by an
  affine test (§3).** Version 1.0's V2 assumed a proportional method. The Eastmoney 前复权 file
  for 600519 is **subtractive**: every price field is exactly 79.58 below raw. That is outside
  1.0's V2. New: Ruling 2.5 (vendor-adjusted series are not return inputs unless proportional;
  vendor-computed derived columns are never inputs) and Example 3-C (the real file).
- **Ruling 2.4 is rewritten around precision profiles kept as data** (Appendix A).
  - Float-rendered numbers are normalized to the shortest decimal that round-trips the field's
    declared binary format, then validated against the market's maximum decimals.
  - The §4.2 bound becomes 0 for values recovered exactly.
  - Sina HK closes are float32 renderings (`474.20001` → 474.2).
- **New Ruling 2.6, volume units.** No 1.1 rule uses volume magnitude. Any later rule that does
  must convert to shares through the profile: Eastmoney CN reports lots of 100, Sina HK reports
  shares.
- **Rulings 4.1 and 4.3: independence is by upstream, not by library.** Primary order is set
  per market by upstream. A shared wrapper library is a common-mode component, and new
  safeguards (Ruling 4.6) address it.
- **PD-0030 recorded.**
  - OD-1: `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` now exist (Ruling 4.4, §4.4 table,
    Ruling 6.4).
  - OD-2: F8-B is decided; it applies once implemented, and F8-A applies until then (§6.3).
  - OD-3: CNH stays strict (Ruling 1.4).
- **No expected value in any 1.0 example changed.** Example 3-B (proportional) still stands as
  a proportional case under the new V2.
**Authority:** PD-0021 §9 (conventions are the Quant's; the engineer must not decide them
silently); CLAUDE.md invariants P5, P6, P9, P12, NFR-001, NFR-008, NFR-009, §34 ("conventions —
day-count, annualization, compounding, FX fixing — are part of the method and are written down
in `methodology/`"); PD-0006 and PD-0028 (staleness threshold and FX fixing assigned to this role).
**Answers:** STATUS.md open items 12 (F8) and 16 (a), (c), (d); HG1 round 4 §9 items 2 and 3 for
the development tier.
**Inputs read:** PRD §8, §9.1, §9.7, §10.3, §11.1–§11.4, §12, §32–§34, NFR-001/-008/-009/-010;
PD-0006, PD-0014 Part 1, PD-0015 Part 1, PD-0021 §1, PD-0025, PD-0027, PD-0028;
`methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (`ledger-replay/1.3`: Rulings 0.3, 1.2, 3.1, 3.2,
3.4, 5A.7, §7, F8, F12, OI-1, OI-2, OI-6, OI-8);
`methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md` §4.3, §4.6, §5.4, §6, §7.3, §7.6, §9;
`designs/FEATURE_DESIGN.md` §D5; `implementation/FEATURE_TECH_PLAN.md` §13.E, §13.H;
`src/marketdata/contracts.py`, `src/product_contract/vocabulary.py`, `src/domain/currency.py`,
`src/domain/instrument.py` (read only).
**(1.15) Also read**, read only:

- decisions PD-0063, PD-0064 and PD-0065;
- reviews:
  - `reviews/HG4_DATA_SOURCE_CHECK_ALPHA_VANTAGE.md`;
  - `reviews/CP7_E9_REAL_SOURCE_AND_UAT_PACKET.md`;
  - `reviews/CP7_E9_EVIDENCE/gap-author/REMAINING_EVIDENCE_MATRIX.md` (R08);
  - `reviews/CP7_E8_EXECUTION_RESULT.md`;
  - `reviews/CP7_E2_SEC_RESULT.md`;
- `ledger-replay/1.5` Rulings 3.2 and 3.4 and §0.5.7;
- source code:
  - `src/marketdata/adapters/alphavantage.py` and `daily_csv.py`;
  - `src/marketdata/precision.py` (`resolve_close`);
  - `src/marketdata/ingest.py` (`_enrich`, `_classify_close`);
  - `src/marketdata/profiles.py`;
  - `src/marketdata/adapters/eodhd_split_candidate.py`;
- the calendar drafts under `data/marketdata/calendars/drafts/` (unregistered);
- the split entries of the `cp3_golden` and `cp4_golden` fixtures, for the fixture-impact statement.

No payload was read beyond the Example A-1 row already quoted. No network was used. **No expected
value in 1.15 comes from running `src/`.** I used a scratch `fractions.Fraction` only to check long
division.

**(1.16) Also read**, read only:

- decisions PD-0066 and PD-0067, and `STATUS.md` items 9–11;
- reviews:
  - `reviews/TECH_REVIEW.md`, these sections:
    - "Real-path F1 design — final check (2026-10-23)";
    - "market-data 1.15 and CN calendar packet (2026-10-23)";
    - "Alpha Vantage A-share route, pending (B2) …";
    - "A-share route fix round …";
  - `reviews/CN_CALENDAR_CHECK_PACKET.md`;
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` §0.1 and §1.1, the engineer's track today, read only;
- `methodology/CP6_INSIGHT_CONVENTIONS.md` §2 and §3, on ACTUAL versus model semantics;
- source code:
  - `src/marketdata/profiles.py`, `exchange_codes.py` and `store.py` (`quote_on`);
  - `src/marketdata/adapters/alphavantage.py` and `daily_csv.py`;
  - `src/marketdata/precision.py` (`check_field_format`);
  - the `state_kind` uses in `financial_service_integration.py`, `insights/engine.py` and
    `web_api/real_source_contexts.py`;
- data files, read and re-hashed only:
  - the two OpenFIGI files of 2026-10-23 and the 2026-10-01 `AAPL_US.json`/`AAPL_XNAS.json`;
  - `AAPL_compact.csv`: decimals and dates only;
  - the registered `NYSE_2025_2026.json` and `CN_A_2025_2026.json` calendars: metadata and date
    counts;
  - the `alphavantage.cn` entry of `data/marketdata/SOURCES.json`;
- the fixture market-data blocks, for decimal counts and MICs.

The session dates and counts in Example 3-G and Ruling 6.5 item 5 come from the registered NYSE
file's date list. I counted them in a scratch shell, not through `src/`, and checked them by hand
from weekdays and holidays.

> **This document approves nothing.** It approves no gate, selects no vendor, licenses nothing
> and changes no product scope. Where a question needs the product owner, it says so and leaves
> it open (§10).

**Label key** (as in `ledger-replay/1.3`).

- **RULING**: binding within the Quant role's authority (methods, conventions, thresholds,
  sufficiency semantics).
- **RECOMMENDATION**: an engineering or data-handling change I believe is needed. Someone else
  decides it.
- **OWNER DECISION**: a product question. It is stated and left open.

**Out of scope, by instruction:** return and denominator conventions (CP3), lot depletion, the
money-rounding convention (OI-8; §8 says where CP2 meets it), benchmark licensing.

**Worked examples.** Every expected value below was derived by hand from the inputs shown. The
derivation sits next to the value. No value comes from running `src/`. I used a calculator
(exact `fractions.Fraction` in a scratch shell) only to check long division. **All market numbers
in the examples are hypothetical**, chosen to exercise a rule. They are not claims about any
real security or fixing.

**External facts.** I have no network access here. Exchange hours, the ECB fixing procedure,
the TARGET calendar, the PBOC band and the HKD peg are stated from my knowledge and listed in
§12 for the human to confirm against the publisher at download time. No computation in this
document depends on the exact minute of any of them. Each ordering it relies on is separated by
hours.

---

## 0. Objects and notation

- **Listing `ℓ`**: the internal `listing_id` (PD-0021 §1). Each listing has one exchange `m(ℓ)`
  (by MIC) and one trading currency.
- **Session calendar `C_m`**: the set of local dates on which exchange `m` held a trading
  session. It is **reference data**: a versioned, content-hashed file, listing **actual**
  sessions, not planned ones (§2.2).
- **Fixing calendar `C_ECB`**: the set of dates on which the ECB publishes euro reference rates
  (TARGET business days). Also a versioned file.
- **Market-data version `M`**: the exact set of immutable, content-hashed files a computation
  reads. This covers price, FX and corporate-action files, both calendars, and any
  human-authored resolution records (§4.4). `M` and this convention ID together make the market
  side of §34 reproducible, as `L` does for the ledger.
- **Resolved inputs.** For a date `D` (or a Current-mode instant `t`), CP2 produces:
  - `P(ℓ, D | M)`, the price of a listing;
  - `X(b→q, D | M)`, the rate in units of `q` per one unit of `b`;
  - the corporate-action set for `ℓ`.

  Each comes with the date it actually comes from, its freshness and reconciliation status, a
  `(sufficiency_state, reason_code)` pair, and lineage.

### RULING 0.1: One vintage per series in `M`

A **series** is identified by (source, listing or currency pair, adjustment status, anchor).
`M` may contain **at most one vintage** (one retrieval) per series. If a file set holds two
vintages of one series, building `M` must **fail closed**. It must not pick "the latest file".
Picking one vintage silently would be a silent win between two versions of the same facts.

Two vintages of one **raw** series that disagree on a past date are a *revision* and are flagged
(§4.3). Two vintages of an **adjusted** series are expected to differ (§2.3), and that is why
only one may be in `M`.

**(1.12) Segments: one series in several files, each date in exactly one.** "At most one vintage
per series" is read **per date**: for each series and each date, at most one file in `M` speaks
about that date. Several files of one series are admitted to `M` as **segments of one series** when
all of the following hold. Otherwise building `M` fails closed, and nothing is picked.

1. **Disjoint coverage.**
   - Each file has a declared coverage interval `[start, end]`. For FX this is Ruling 1.1a item 5.
     For every other kind it is defined the same way:
     - **`start`:** the manifest's requested start date, or for a full-history file the first date
       it holds;
     - **`end`:** the earlier of the requested end date and the latest date whose scheduled close or
       publication is at or before the manifest's `retrieval_time`.
   - **The coverage intervals of the segments of one series are pairwise disjoint.**
   - Inside its coverage, a file's missing row is a statement: that date had no print. Outside it,
     the file says nothing.
   - **So disjoint points are not enough.** File B, covering a date that file A also covers, is a
     second vintage of that date even when A holds no row there. A "no print" that becomes a print
     is a revision. Two files that overlap are refused **even if every overlapping value agrees**:
     Ruling 0.1 never chooses between vintages, and agreement today is no rule.
2. **One identity.** Same source (and upstream), same series key (subject, adjustment status,
   method, anchor), same declared static fields (currency, unit, calendar, quote type, return basis
   and so on), and the same `synthetic` flag (Ruling 4.8).
3. **A vintage-stable series.** The published value of a date does not depend on when it was
   retrieved:
   - `RAW` prices;
   - ECB fixings;
   - published index levels (a `BenchmarkSeries`, `risk` Ruling 5.1);
   - risk-free quotes (`risk` Ruling 4.6).

   **Vendor-adjusted series (`SPLIT_ADJUSTED`, `DIVIDEND_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`) are
   never segmented.** With anchor `LATEST`, each retrieval re-bases the whole history (Ruling 2.3), so
   two segments sit on two bases and their join is a false jump. They are not valuation inputs
   anyway (Ruling 2.3).
4. **Each segment passes its own file checks.** Ruling 3.1 (V0, and the after-retrieval test on its
   own `retrieval_time`) and Ruling 4.6 run per file.

**(1.13) Two more refusals, and the order of the checks.** These apply to every file of a series in
several files.

- **1(b) Coverage that cannot be stated: `REFUSED_COVERAGE_UNDETERMINED`.**
  - **When:** the file has no requested range and is not a full-history file, or the governing
    calendar does not cover the date its `end` needs (Ruling 5.3).
  - **Why refuse:** disjointness cannot be shown without coverage.
  - **Why not take the hull of the rows:** that would make the file's content define its own claim.
    A file that holds no row on its last covered day would then appear to cover less than it did,
    and a missing edge print would become invisible. Ruling 1.1a item 5 rejected exactly that
    "held dates" reading.
- **1(c) A row outside the declared coverage: `REFUSED_ROW_OUTSIDE_COVERAGE`.**
  - **What:** a file holding a row dated before its declared `start` or after its declared `end`
    is refused, and with it the build.
  - **The coverage is never widened to the hull** of the declared interval and the rows.
  - **"First row held"** in item 1 defines `start` only for a **full-history** file, which has no
    requested start. A file with a requested start keeps it, whatever rows it holds.
  - **Why refuse:**
    - Such a row contradicts the file's own manifest. Either the request or the dating is wrong. As
      with Test V0 and the after-retrieval test (Ruling 3.1), one row that the file's own record says
      it cannot hold means none of its dates can be trusted.
    - The row is also a second reading of a date another segment may cover. That is the CP4M-10
      route back to the RB-2 revision.
  - **Why not the hull:** the hull trusts the stray row, and extends the file's claim of "no print"
    over every date between that row and the declared range, dates the file was never asked for.
    - Where the row lands in a date another segment covers, the hull is refused anyway, but for a
      fabricated overlap span (RB-6: 2025-06-13..2026-01-08).
    - Where it lands in a hole that no segment covers, the hull **admits** it, and the row values
      that date (RB-9).
    - Refusing names the actual defect in both cases.
- **The order of the checks**, with the first failing check giving the outcome:
  1. `REFUSED_IDENTITY`;
  2. `REFUSED_NOT_SEGMENTABLE`;
  3. `REFUSED_COVERAGE_UNDETERMINED`;
  4. `REFUSED_ROW_OUTSIDE_COVERAGE`;
  5. `REFUSED_OVERLAP`;
  6. otherwise `ADMITTED`.
- **Each refusal fails the build closed** (the Ruling 0.1 error). Nothing is dropped and nothing is
  picked.
- **A series in one file** needs no coverage and is not checked under 1(b) or 1(c). Its rows are
  judged by Ruling 3.1 as before.
- **Fixture:** `cp4_golden/1.4-part3` `release_cases` RB-6 to RB-9.

**The vintage is the file's `retrieval_time`** (Ruling 2.3). Segments are told apart by their
coverage and retrieval time, which every manifest already records. **No field of the series key
carries a vintage label.** `adjustment_anchor` means only what Ruling 2.3 says: `LATEST` or
`EARLIEST`, or null for a raw series.

**Where.** The check and the joining happen in the release build, once, for every kind. Each
admitted series reaches the read path as one series, with lineage listing its segment files and
their coverage. A Current-mode read uses only the segments in `M_t` (`performance` Ruling 1.7).
A date covered only by a segment retrieved after `t` has no reading at `t`.

**What a segment boundary does not do.** It does not break staleness counts or windows. A date
inside no segment's coverage (a hole between segments) has no reading, and Ruling 5.2 counts it as a
missed session, exactly as a missing row.

**Rejected:**

- **disjoint points as the test.** It admits a backfilled print on a date an earlier file showed as
  missing (`cp4_golden/1.3-part3` case RB-2).
- **a declared vintage label in the anchor or another identity field.** It makes each segment its
  own series, so this check never sees two files of one series, and an overlap would surface only
  later as two "sources".
- **taking the latest file on overlap.** That is Ruling 0.1's original prohibition.

---

## 1. FX

### RULING 1.1: The fixing. "The rate for date D" is the ECB euro reference rate dated D.

**Convention.**

- The only FX observations in this convention set are the **ECB euro foreign-exchange reference
  rates**. Each is a quote of **units of currency `c` per 1 EUR**, for `c` ∈ {USD, HKD, CNY, …},
  with reference date `f`.
- The rate is fixed at the ECB's daily concertation, **nominally 14:10 Europe/Berlin local
  time** (1.8; the ECB says "around 14:10 CET"; 1.0–1.7 used 14:15 from memory). CET in winter,
  CEST in summer; use the IANA zone, never a fixed offset. The ECB publishes it at about 16:00
  the same day.
- In the seam type, `FXObservation(base=EUR, quote=c, rate=x_c(f))`. Both `observed_at` and
  `Freshness.source_time` are `f` at 14:10 Europe/Berlin (1.8). The instant is a nominal label:
  no rule in this document depends on its minute.
- The value is stored **exactly as the published decimal text**: no float, no re-rounding, and
  trailing zeros are irrelevant to the value.

**"The rate for date `D`"** means the fixing with reference date `D`, if it exists. Otherwise it
means the latest fixing before `D` under Ruling 1.6. **It is never a fixing dated after `D`,
never an interpolation, and never "today's" rate applied to a past `D`** (PRD §8.3, NFR-009).

**Why.**

1. It is the only daily reference fixing among the PD-0027 sources that covers USD, HKD and CNY
   from one publisher at one instant. One instant for every pair is what makes cross rates
   consistent (Ruling 1.3).
2. HG1 round 4 §4.6 requires **one fixing time for all three markets**, the same for the
   portfolio leg and the benchmark leg. Under PD-0027 the ECB fixing is the only candidate.
3. It is free to use for this purpose, published daily with a long history, and its time is
   stated by the publisher.

**Rejected alternatives.**

- **WM/Reuters 16:00 London.** This is the market standard, and HG1 round 4 §9.2 named it. It
  is a licensed product and is not among the PD-0027 sources. If the OQ-04b launch vendor offers
  it, the choice of fixing returns with OQ-04b, and a change is a new convention ID.
- **A fixing timed to each market's close** (HKD at the HK close, USD at the NY close). One
  portfolio would then translate one currency at different instants. Cross rates would stop
  being consistent, and no free source publishes such fixings.
- **The next ECB fixing after the US close** (`D+1`'s ECB fixing for a US close on `D`). This
  is look-ahead relative to the date label. In Current mode `D+1` does not exist yet. It also
  moves the Asian closes even further from their rate.
- **The CFETS central parity for CNY.** Different instant, different publisher, and an
  administrative reference rather than a market rate. See Ruling 1.5.

### RULING 1.1a (1.2): Which file carries the ECB fixing, and Frankfurter's provenance

1. **Preferred source: the ECB's own reference-rate history file** (`eurofxref-hist`, CSV),
   downloaded by the human. It is the publisher's own record of the quantity Ruling 1.1
   defines, so its provenance needs no argument. It must be admitted through the same terms
   attestation as any source (a new `SOURCES.json` entry, `upstream: ecb`). The ECB terms
   reading in PD-0031 (reproduction permitted with acknowledgement) is the one that applies;
   the attestation itself is the owner's.
2. **Frankfurter v1** (`frankfurter.ecb`, admitted) carries the `ecb` upstream as a
   **declaration**, not a confirmed fact (PD-0031 caveat: v2 blends providers unless asked not
   to).
   - Until confirmed, its rates may be used for development, parser tests and synthetic-fixture
     work.
   - **They may not be the evidence for any CP2-exit or HG2 claim that a value is "the ECB
     reference rate for `D`"**, and every resolved rate from it carries
     `provenance: UNCONFIRMED` in lineage.
   - Sufficiency is not changed by this, because no second FX source exists either way. The
     condition is about what may be claimed, which is a P9 matter.
3. **Confirmation is one deterministic check.** For every (date, currency) in the overlap of a
   Frankfurter v1 file and an ECB-direct file, the two values must be **equal as decimals**
   (trailing zeros ignored). The dates present must also be the same set within the overlap.
   - If both hold on an overlap that includes the dates Frankfurter supplied, those dates are
     `provenance: CONFIRMED` for that Frankfurter file. Any difference refutes the declaration
     for that file.
   - I recommend running this once over the probe window, 2025-01-02 to 2025-01-08, and then
     relying on the ECB file.
4. **If both are admitted, they reconcile only by the transport check** (Ruling 4.1). They share
   one upstream, so their agreement is `SINGLE_SOURCE`, never `CORROBORATED`.
   - A value difference on a (date, currency) gives `DISAGREEMENT`: `INSUFFICIENT_DATA` +
     `SOURCE_CONFLICT` for that rate, until a resolution record cites the ECB publication.
   - A date present in one and absent in the other, within both files' coverage, is also
     `DISAGREEMENT` for that date.
   - Primary order: the ECB file, then Frankfurter (A.5).
5. **(1.3) The coverage of a file, for currency pair `c`.** It is **not** simply the first and
   last date the file holds; that would hide a missing edge date. It is the closed interval
   `[start, end]`:
   - **`start`:**
     - for a request-bounded file (a Frankfurter time series), the manifest's requested start
       date;
     - for a full-history file (`eurofxref-hist`), the first date the file holds a value for
       `c`, because a currency's series has its own start.
   - **`end`:** the earlier of the requested end date (full-history files have none) and
     `D_ret`. `D_ret` is the latest fixing date `f` in `C_ECB` with `f` at 16:00 Europe/Berlin
     ≤ the manifest's `retrieval_time`, which is the nominal publication of Ruling 1.6. A fixing
     that could not yet have been published when the file was fetched is never counted as
     missing from it.
   - If `C_ECB` does not cover the overlap, the date-set part of the check is `UNVERIFIABLE`
     for the uncovered dates (Ruling 5.3). The value part still runs on dates both files hold.
   - Example: a Frankfurter file requested for 2025-01-01..2025-01-08 has start 2025-01-01.
     2025-01-01 is a TARGET closing day, so its absence is not a gap. If the file lacks
     2025-01-08 while the ECB file has it, that is a `DISAGREEMENT` for 2025-01-08. Under the
     held-dates reading, the file's coverage would have ended on 2025-01-07 and the gap would
     have been invisible.
6. **(1.3) What a `REFUTED` Frankfurter file does.**
   - **It stays in `M`**, flagged `provenance: REFUTED` with the differing (date, currency)
     list. The evidence must be reproducible, and Ruling 0.1 needs `M` to be the exact file set
     read.
   - **It supplies no rate on any date.** Its provenance is refuted for the whole file, so on a
     date the ECB file lacks, its value is not an ECB fixing either.
   - On each (date, currency) where the two files' values **differ**, the ECB file's value is
     `DISAGREEMENT` (`INSUFFICIENT_DATA` + `SOURCE_CONFLICT`) until a resolution record cites
     the ECB publication. The mismatch may be a transport error on either side, so the ECB
     file does not win silently.
   - On dates where they agree, the ECB value is used (`SINGLE_SOURCE`).
   - **(1.4 clarification) The refuted file still takes part in the date-set check of item 4.**
     The reason is the same as for values: a mismatch may be a transport fault in the ECB file.
     - A date the ECB file holds and the refuted file lacks makes that ECB value
       `DISAGREEMENT`.
     - A date the refuted file holds and the ECB file lacks is `DISAGREEMENT` for that date.
       That date has **no rate** (`SOURCE_CONFLICT`) and is not carried forward over.
     - Both clear through a resolution record. Refutation is an anomaly that needs human review
       anyway, so suppressing the affected dates costs little.

### RULING 1.2: How the fixing relates to the three markets' closes on the same date

For a calendar date `D`, in UTC:

| Event on `D` | Local time | UTC, northern winter | UTC, northern summer |
|---|---|---|---|
| SSE/SZSE close (closing call auction ends) | 15:00 Asia/Shanghai | 07:00 | 07:00 |
| HKEX close (closing auction ends about 16:08–16:10) | about 16:10 Asia/Hong_Kong | about 08:10 | about 08:10 |
| **ECB concertation** (1.8: nominal 14:10) | **14:10 Europe/Berlin** | **13:10** | **12:10** |
| NYSE/Nasdaq close | 16:00 America/New_York | 21:00 | 20:00 |

(China and Hong Kong have no DST. In the weeks when the US is on summer time and Europe is not,
in March and late October to early November, the ECB fixing is 13:10 UTC and the US close
20:00 UTC.)

**Consequence, stated as a rule.** A date-`D` bundle consists of each listing's official close
on `D` (in its own local calendar) and the ECB fixing of `D`.

- The fixing comes **about 4 to 6⅙ hours after** the Mainland and Hong Kong closes of `D`.
  The range runs from about 4 h after the HK close in summer (12:10 − 08:10 UTC) to 6 h 10 min
  after the Mainland close in winter (13:10 − 07:00 UTC).
- It comes **about 6 h 50 min to 7 h 50 min before** the US close of `D` (7 h 50 min when both
  sides are on the same time regime; 6 h 50 min in the mismatch weeks).

No single instant makes the three markets simultaneous; that is the product's founding
constraint (NFR-008). The seam is not an error. It is a **temporal-comparability disclosure**
(PD-0014 Part 1, HG1 round 4 §5.2), attached to any two-leg comparison and to any statement
that a translated US position and a translated Asian position are "as of the same time".

A ledger event's local `event_date` (Ruling 1.2 of `ledger-replay/1.3`) is translated at the
fixing for that date label. That is how HG1 round 4 §7.3 and OI-1 ("basis at the transaction-date
FX rate") are met.

### RULING 1.3: Cross rates through EUR are exact ratios of two same-date published rates

**Formula.** With `x_c(f)` = units of `c` per 1 EUR on fixing date `f`:

```
X(b→q, f) = x_q(f) / x_b(f)          units of q per one unit of b
```

For example:

- HKD per USD = `x_HKD / x_USD`;
- CNY per USD = `x_CNY / x_USD`;
- CNY per HKD = `x_CNY / x_HKD`.

The inverse quote is `x_b / x_q`. It is a separate, labelled value, never a silent flip.

**Precision. Yes, a cross is carried as an exact ratio.**

- A cross rate is the **rational number** `x_q / x_b`, held as the ordered pair of its two
  published observations (both lineage records kept).
- It is **never** materialized as a rounded `Decimal`.
- A conversion `A × X(b→q)` is computed exactly as `A × x_q / x_b`.
- Rounding happens at most once, at the very end, under the money-rounding convention (OI-8),
  which does not exist yet (§8).

**Same-date rule.** Both legs come from **one** fixing date `f`. When the latest observations
of the two legs carry different dates, the cross uses the **latest date on which both exist**,
and Ruling 1.6 counts missed fixings from that common date. Legs from two dates are never
combined.

**Never use a rebased rate from a re-server.** For example, Frankfurter's `from=USD` returns a
USD-based quote that it has computed and rounded itself. That number is not published by the
ECB, and its rounding convention is not ours. Download the **EUR-based** quotes only, and derive
crosses here.

**Why.**

1. An exact ratio is deterministic, auditable to two published facts (P9), and needs no
   rounding convention.
2. Rounded crosses are **not mutually consistent**. Example 1-A shows a 4-decimal triangle
   failing to close.
3. A Mainland account converting USD to CNY and an HK account converting USD to HKD must
   agree with the HKD-to-CNY rate. Only exact ratios guarantee that.

**Rejected alternative:** storing each cross as a `Decimal` rounded to some number of places.
That decides OI-8 by accident, inside the data layer (compare HG1 round 4 §7.9 on rounding inside
`data.js`).

#### Example 1-A: cross rates and a conversion (hypothetical fixing)

Published on fixing date `f`: `x_USD = 1.0823`, `x_HKD = 8.4512`, `x_CNY = 7.8243`.

| Cross | Exact value | Reduced fraction | Decimal expansion (checked by long division) |
|---|---|---|---|
| HKD per USD | 8.4512 / 1.0823 | 84512 / 10823 | 7.8085558532… (does not terminate: 10823 = 79 × 137) |
| CNY per USD | 7.8243 / 1.0823 | 78243 / 10823 | 7.2293264344… (does not terminate) |
| CNY per HKD | 7.8243 / 8.4512 | 78243 / 84512 | 0.9258211851… (does not terminate: 84512 = 2⁵ × 19 × 139) |

Long division for the first row: 84512 / 10823 = 7 rem 8751; 87510 / 10823 = 8 rem 926;
9260 → 0; 92600 / 10823 = 8 rem 6016; 60160 → 5 rem 6045; 60450 → 5 rem 6335; 63350 → 5 rem
9235; giving 7.808555…

**Exact triangle.** (84512/10823) × (78243/84512) = 78243/10823, which is CNY per USD
**exactly**.

**Rounded triangle fails.** Rounded to 4 places, the rates are 7.8086, 0.9258 and 7.2293.
7.8086 × 0.9258 = **7.22920188**, which rounds to 7.2292, not 7.2293. Two surfaces converting
the same USD to CNY by two paths would differ.

**Conversion.** 10,000 HKD → USD = 10,000 × 1.0823 / 8.4512 = 108,230,000 / 84,512. Dividing
both by 16 gives **6,764,375 / 5,282** USD ≈ 1,280.6465354…, which does not terminate
(5,282 = 2 × 19 × 139). The exact rational is the CP2/CP3 intermediate. Turning it into a
reportable `Decimal` needs OI-8 (§8).

### RULING 1.4: Onshore CNY and offshore CNH are different quotes. V1 has a rate for CNY only.

**Convention.**

- **CNY** is the onshore renminbi, traded in the China interbank market. It is the currency of:
  - Mainland-listed A-shares (XSHG, XSHE);
  - cash in Mainland bank or broker accounts;
  - Southbound Stock Connect consideration debited from a Mainland account (Ruling 0.3 of
    `ledger-replay/1.3`: the event currency is the cash actually moved, CNY).
- **CNH** is renminbi held and settled outside the Mainland. It is the currency of:
  - RMB cash at a Hong Kong or other offshore broker;
  - Northbound Stock Connect consideration paid by an offshore investor;
  - the trading currency of HKEX RMB-counter securities.

  `CNH` is not an ISO 4217 code. It is the market convention, and `CurrencyCode` admits it
  syntactically.
- The **amount's own currency decides the rate**. CNY amounts use `x_CNY` from the ECB. CNH
  amounts need a CNH rate. **No PD-0027 source publishes one.**
- **RULING (strict default):** a CNH amount's reporting-currency translation is
  `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`. Its native-currency value is unaffected (Tech Plan
  §13.E). **(1.8)** A reporting-currency aggregate that includes it is also `INSUFFICIENT_DATA` +
  `MISSING_FX_HISTORY` (`performance/1.0` Ruling 1.4). Versions 1.0–1.7 said `LIMITED` with the
  excluded weight stated, but that weight cannot be measured in reporting-currency terms without
  the rate that is missing, so HG1 round 4 §6 R1 cannot be met.
- **The engineer must never substitute the CNY rate for CNH silently.**
- The ECB labels its series CNY. I treat it as the onshore rate. I could not verify from here
  which market segment the concertation samples. Ruling 1.5's band check is a deterministic
  plausibility test of that, not proof.

**Why.** The two quotes are one currency unit in two markets with separate prices. The
CNY–CNH basis is usually small but has widened sharply at times of stress. A proxy is a
different market's price presented as this one's.

**Rejected alternative:** translate CNH at the CNY rate with a `LIMITED` state and a
"translated at the onshore rate" caveat. This was offered to the owner as OD-3. **Decided
(PD-0030 §3):** CNH stays strict, and a CNH source is added to OQ-04b's scope.

### RULING 1.5: The CFETS central parity is a plausibility bound, never a valuation rate. The HKD peg band likewise.

**Convention.**

1. The CFETS USD/CNY central parity (中间价), published about 09:15 Asia/Shanghai on Mainland
   interbank trading days, is stored as its own series with its own lineage, if downloaded.
   It is **never** used to translate, value or fill a missing ECB rate.
2. **Band check.** For each date `f` with both values, compute
   `|X_ECB(USD→CNY, f) / parity(f) − 1|`.
   - Onshore spot may trade at most **±2 %** from that day's central parity (the PBOC band).
   - If the ECB-derived rate lies **outside** ±2 %, the date's CNY observation is `IMPLAUSIBLE`
     (§4.3).
   - The comparison is exact rational arithmetic: `|x_CNY/x_USD − p| > 0.02 × p`.
3. **HKD peg check.** If `X_ECB(USD→HKD, f)` lies outside the **7.75–7.85** HKD-per-USD band of
   the Linked Exchange Rate System, the date's HKD observation is `IMPLAUSIBLE`.

**Why.**

- The parity is fixed about 12 hours before the ECB concertation (in winter; 11 in summer).
  It is an administrative reference. Onshore spot routinely trades away from it within the band.
  Using it as a second source with a tight tolerance would report noise as disagreement.
- It is **independent** of the ECB, and the band is a published, hard bound on onshore spot.
  So it is the strongest deterministic check available on a single-source FX series (PD-0027
  condition 4: "where available").
- The peg band plays the same role for HKD.

**Rejected alternatives:**

- using the parity as the CNY valuation rate (Ruling 1.1);
- reconciling the ECB rate against the parity with a tight tolerance (a different quantity).

### RULING 1.5a (1.3): Content of a central-parity series, once one is admitted

No central-parity source is admitted today. Tests inject a mapping, which is acceptable for
tests only. An admitted series must carry the following. The serialization is the engineer's.

1. **Admission.** A `SOURCES.json` entry with `upstream: cfets` and the owner's terms
   attestation, like any source (PD-0031). Until then the band check of Ruling 1.5 **does not
   run in product paths**. That is recorded in lineage as `PARITY_CHECK_NOT_RUN`, with no state
   effect. A test-injected mapping must never reach a product path.
2. **Per observation:**
   - the **ordered pair**, explicit: `base = USD`, `quote = CNY`;
   - the **quote unit**: units of quote per `quote_unit` units of base, stated explicitly (1
     for USD/CNY). This is **MEMORY**: CFETS quotes some currencies per 100 units, so the unit
     is never assumed;
   - the **parity date** `p`, a local date in Asia/Shanghai;
   - the **publication instant**: about 09:15 Asia/Shanghai (**MEMORY**), recorded as published
     where the file states it;
   - the **value** as decimal text, exactly as published, with no re-rounding;
   - lineage: retrieval time and file hash, as for every file in `M`.
3. **Calendar.**
   - Parity dates follow the **China interbank market's** working days. They are not the
     SSE/SZSE session calendar: the interbank market can open on adjusted weekend working days
     when the stock exchanges are closed (**MEMORY**).
   - The parity series needs **no** calendar of its own for the band check. The check runs only
     for a date `f` that is both an ECB fixing date and a parity date `p = f`.
   - A date with no parity (a Mainland holiday) is simply **not checked**. That is not a gap,
     not a missing-data state, and not a freshness count. The parity is never carried forward to
     check another date's fixing.
4. **The check itself is unchanged** (Ruling 1.5):
   - flag `IMPLAUSIBLE` iff `|x_CNY / x_USD − p_value / quote_unit| > 0.02 × p_value / quote_unit`;
   - exact rational arithmetic, on the same date;
   - only the USD/CNY pair has a band in this convention set.

   A parity for any other pair is stored, if admitted, and not used.
5. The parity is **never** a valuation or translation rate (Ruling 1.5 item 1), and never fills
   a missing ECB fixing.

### RULING 1.6: Weekends, holidays and missing fixings

Let `D` be the date (historical mode). Then:

- `e(D)` = the latest date in `C_ECB` that is ≤ `D` (the fixing that *should* apply);
- `u(D)` = the latest date ≤ `D` for which `M` holds the observation. For a cross, both legs
  must be present (Ruling 1.3). An ECB "N/A" is not an observation.
- `m(D)` = the number of dates `f` ∈ `C_ECB` with `u(D) < f ≤ D`: **missed fixings**.

| Condition | Rate returned | Freshness | Sufficiency | Reason code |
|---|---|---|---|---|
| `m = 0` | `X(u(D))` | `CURRENT` | `AVAILABLE` | none |
| `m = 1` | `X(u(D))` | `STALE` | `AVAILABLE` | `STALE_DATA` |
| `m = 2` to `4` | `X(u(D))` | `STALE` | `LIMITED` | `STALE_DATA` |
| `m ≥ 5`, or no observation ≤ `D` at all | **none** | `STALE` (or `UNKNOWN` if none) | `INSUFFICIENT_DATA` | `MISSING_FX_HISTORY` |
| pair needs CNH (Ruling 1.4) | **none** | n/a | `INSUFFICIENT_DATA` | `MISSING_FX_HISTORY` |
| observation `IMPLAUSIBLE` or in `DISAGREEMENT` (§4) | **none** | n/a | `INSUFFICIENT_DATA` | see §4.5 |
| `C_ECB` does not cover `(u(D), D]` | **none** | `UNKNOWN` | `INSUFFICIENT_DATA` | none |

**Carry-forward is allowed only as "the latest fixing at or before `D`"**, and how it is
marked depends on why the fixing is old:

- **Over non-fixing days** (weekends and TARGET closing days), `m = 0`. The rate is current,
  because no newer fixing exists. This is the same session principle as HG1 round 4 §5.4: a
  market on holiday is not stale. **Marking:** the result always carries its **fixing date
  `u(D)`**, which can differ from `D`. The manifest records it.
- **Over a missing fixing on a fixing day** (a data gap), the rate is stale. It is marked
  `STALE`/`STALE_DATA` and degraded as the table says. The maximum carry is **4 missed
  fixings**.

**Why `MISSING_FX_HISTORY` at `m ≥ 5` and not `STALE_DATA`** (unlike prices, §5.2). Five missed
fixings is a week of absent history for the date being translated. PRD §32 names that
condition specifically, and its remedy is to obtain the missing fixings. HG1 round 4 §6 already
allows `MISSING_FX_HISTORY` with `LIMITED` on aggregates (with stated weight) and with
`INSUFFICIENT_DATA` at the level of the missing rate.

**Current mode.** At instant `t`, a fixing date `f` counts as expected only if `f` at 16:00
Europe/Berlin ≤ `t`. That is the nominal publication time. Before 16:00 on `f`, the latest
expected fixing is the previous one. An observation counts only if its file's recorded
retrieval time is ≤ `t`. A late publication can therefore show `m = 1` (`STALE`, still
`AVAILABLE`) for a short while. That is honest and deterministic given `t` and `M`.

**Rejected alternatives:**

- unlimited carry-forward (fabricates history, P5);
- interpolation between fixings (a forecast-shaped fill, P6);
- the next fixing (look-ahead);
- a calendar-day age limit (it fires on Easter and Christmas, when nothing is missing).

#### Example 1-B: Easter 2025 and a data gap (the calendar is assumed for the example)

Assumed `C_ECB` around Easter 2025: Fri 18 Apr (Good Friday) and Mon 21 Apr (Easter Monday) are
TARGET closing days. The fixing dates are 14–17, 22–25, 28–30 Apr.

| Case | `M` holds | `D` | `u(D)` | Fixing dates in `(u, D]` | `m` | Result |
|---|---|---|---|---|---|---|
| (i) | every fixing | Sat 19 Apr | 17 Apr | none | 0 | 17 Apr rate, `CURRENT`, `AVAILABLE`, fixing date 2025-04-17 |
| (ii) | every fixing | Mon 21 Apr | 17 Apr | none (21 Apr is closed) | 0 | same. A US close on 21 Apr is translated at the 17 Apr fixing, 4 calendar days old, and not stale. |
| (iii) | 22 Apr missing | Tue 22 Apr | 17 Apr | {22} | 1 | 17 Apr rate, `STALE`, `AVAILABLE` + `STALE_DATA` |
| (iv) | 22 and 23 Apr missing | Wed 23 Apr | 17 Apr | {22, 23} | 2 | 17 Apr rate, `LIMITED` + `STALE_DATA` |
| (v) | 22–28 Apr missing | Mon 28 Apr | 17 Apr | {22, 23, 24, 25, 28} | 5 | **no rate**, `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` |

---

## 2. Prices

### RULING 2.1: "The price for date D" is the exchange's official close of the session dated D

**Convention.**

- `P(ℓ, D | M)` is the **official closing price** of listing `ℓ` for the session with local
  date `s(D)` = the latest date in `C_m(ℓ)` that is ≤ `D`. "Official" means the exchange's own
  definition:
  - closing auction for NYSE and Nasdaq;
  - the closing auction session where applicable on HKEX;
  - the 14:57–15:00 closing call auction on SSE and SZSE.
- **(1.16) Which definition: the one in force on the session's date.** The official close is the
  closing price (收盘价) the exchange itself publishes for that session, under its trading rules in
  force on that session's date. The mechanisms listed above are **descriptions, not the definition**.
  Each is as I recall it (MEMORY, §12 items 3 and 24), apart from what the CN packet's search summary
  says:
  - **SSE and SZSE shares:** the 14:57–15:00 closing call auction. The packet links SSE's 2018
    closing-mechanism change for shares.
  - **SSE funds, ETFs included:** a closing call auction **only from** SSE's 2026 trading-rules
    revision. A search summary says it took effect on 2026-07-06 (`reviews/CN_CALENDAR_CHECK_PACKET.md`;
    the rule text is unread). Before that, an SSE fund's close was formed by the rule then in force,
    which I recall as the volume-weighted average price of the last minute of trading (MEMORY).
    So "the closing call auction on SSE" does not describe SSE ETF closes before the revision.
  - **NYSE Arca, Cboe BZX and NYSE American** (ARCX, BATS, XASE; Ruling 4.7 item 6): each runs a
    closing auction for its own listings (MEMORY, §12 item 25).

  Nothing in this method computes or checks a close from its mechanism. The value used is the
  exchange-published close, and Test V4 (Ruling 3.3) compares a series against exactly that figure
  for its date. A mechanism change inside a series, such as an SSE ETF across 2026-07-06, therefore
  changes no rule, no V4 outcome and no grid check. The ETF grid (3 decimals, A.1) is a bound on the
  published close whatever formed it. A published close that broke it would fail closed (Ruling 2.4
  item 4).
- **(1.16) SSE after-hours fixed-price trading**, 15:05–15:30, extended by the same revision from STAR
  shares to all A-shares and ETFs (search summary). It trades **at** the official close. It changes
  neither the close nor the 15:00 scheduled close (Ruling 5.3 item 6). Whether a vendor's daily volume
  includes it is unknown (MD-OI-19). The print rule needs only volume > 0.
- It is **not** a last trade that differs from it, a VWAP, an intraday quote, or a vendor
  composite. (1.16) A VWAP is excluded **as a source's substitute**. Where the exchange's own rule
  formed its published close from a VWAP, as recalled for SSE funds before the 2026 revision, that
  published figure is the official close.
- It is **raw** (Ruling 2.3), in the listing's trading currency.
- **Print rule.** A row counts as a print for session `d` only if the source reports
  **volume > 0** for `d`. A zero-volume row, or a source-filled row repeating the previous
  close, is not a print. This covers suspended A-shares (停牌) and untraded illiquid HK names.
  The price is then the last print, aged by Ruling 5.2. A source that reports no volume cannot
  support the freshness rule and is **not admissible** as a valuation source; it may
  corroborate only.
- **Only the listing held.** A position is valued at **its own listing's** price, and only
  that. A missing price is never filled from a sibling listing of the same issuer (the BABA
  NYSE ADS and 9988 HKEX case, PRD §10.3), converted by an ADS ratio and FX. This answers HG1
  round 4 §9 item 3 for valuation. Issuer-level aggregation is a CP5 exposure concern.

**Why.** The official close is the one number the exchange publishes per session. Two faithful
sources can reproduce it exactly (§4.2), and it is what the ledger's trade-date units are
quoted against. Sibling substitution mixes calendars, currencies, the ADS ratio and FX timing
into one number: the "never conflate" failure NFR-008 forbids.

**Rejected alternatives:**

- the last trade of a consolidated tape (it can differ from the official close by ticks);
- a mid or VWAP (not published per session by the exchange);
- valuation from a sibling listing.

### RULING 2.2: Time zones, session dates and the as-of date

1. **Each exchange has one IANA zone:**
   - XNYS, XNAS: `America/New_York`;
   - XHKG: `Asia/Hong_Kong`;
   - XSHG, XSHE: `Asia/Shanghai`;
   - ECB: `Europe/Berlin`.
   - **(1.16)** ARCX (NYSE Arca), BATS (Cboe BZX) and XASE (NYSE American): `America/New_York`.
     These are the US venues of Ruling 4.7 item 6. A zone lets a calendar file name them. **No
     registered calendar governs them yet:** `NYSE_SESSIONS 2025-2026 v1` applies to [XNYS, XNAS]. So
     a listing on them stays `FRESHNESS_UNKNOWN` until a calendar version that names them is checked
     and registered by the owner (Ruling 5.3 item 8; MD-OI-20).
   - No other MIC has a zone. A MIC that is not listed has no V1 market (Ruling 4.7 item 6).

   Fixed UTC offsets are never used.
2. **The session date is the source's local date label**, read in the exchange's zone. It is
   **never** derived by converting a timestamp to UTC and taking its date. For example, a
   source's "00:00 local" stamp for an HK bar is 16:00 UTC on the previous day.
3. `QuoteObservation.observed_at` = the session's **scheduled close instant** on that local
   date, from `C_m`. Half-day sessions use their early close: HKEX half days 12:10 (1.8, Ruling
   5.3 item 6); US early closes are 13:00 ET.
4. `C_m` lists **actual** sessions. A session cancelled after the fact (for example an HKEX
   weather closure before the 2024 severe-weather-trading arrangements) is not a session.
5. **As-of date `D` (historical mode).** The bundle for `D` is: every listing's close for
   `s(D)` in its own calendar, and the ECB fixing `u(D)` (Ruling 1.6). The latest instant in
   that bundle is the US close of `D` when a US listing trades on `D`.
   - The CP3 valuation cutoff instant (HG1 round 4 §7.6; `ledger-replay/1.3` OI-2) must be
     compatible with this date-label rule. **CP3 dependency, named here, not decided.**
   - No input dated after `D` enters (PD-0015 Part 1).
6. **Current mode at instant `t`.** A session counts as available only if its scheduled close
   is ≤ `t` and its file's retrieval time is ≤ `t`. With PD-0027 end-of-day files,
   `DataDelayStatus` is `END_OF_DAY` for every price and every fixing. `LIVE` and `DELAYED` are
   unreachable in the development tier (PD-0028 gaps).

### RULING 2.3: Raw, split-adjusted, dividend-adjusted and total-return series are four different series and are never mixed

**Definitions** (PRD §11.3; the `AdjustmentStatus` labels):

| Label | What it is | Stable across retrievals? |
|---|---|---|
| `RAW` | The official close as printed on that date, in the units that traded that day | **yes**. A change is a revision (Ruling 0.1). |
| `SPLIT_ADJUSTED` | Each close before a split ex-date multiplied by `o/n` for every split `(n, o)` with ex-date after it, up to the **retrieval date** | **no**. Changes whenever a later split occurs. |
| `DIVIDEND_ADJUSTED` | As above, also back-adjusted for cash dividends by a **stated method**: proportional factor `1 − d/P_prev` per ex-date (the "adjusted close" convention), or subtractive. Plus an **anchor**: latest price kept raw (前复权 qfq) or earliest kept raw (后复权 hfq). | **no** (qfq). hfq is stable unless history is revised. |
| `TOTAL_RETURN_ADJUSTED` | An index whose ratio across an ex-date equals the total return under a **stated reinvestment convention**, e.g. `(P_ex + d)/P_prev` | depends on its anchor |

`DIVIDEND_ADJUSTED` (proportional) and `TOTAL_RETURN_ADJUSTED` are **not** the same series.
Across an ex-date, the first gives `P_ex / (P_prev − d)` and the second `(P_ex + d) / P_prev`.
The two differ by `d (P_prev − P_ex − d) / (P_prev (P_prev − d))`. So the method and anchor
are part of the label. A series without them is unlabelled.

**Label fields (1.1).** An adjusted series' label is the tuple
(`adjustment_status`, `method`, `anchor`, `vintage`). These are the definitions:

- **Event map.** Each corporate action `j` with ex-date `X_j`, cash `d_j` per pre-event share and
  share ratio `(n_j, o_j)` (`(1, 1)` when there is no share distribution) defines a map applied
  to prices dated before `X_j`.
- **`method`** is one of:
  - **`PROPORTIONAL`:** `p ↦ p × (1 − d_j / P_prev,j) × o_j / n_j`. The map is a pure scale
    factor, so between events the adjusted series is `adj_t = a × raw_t`.
  - **`SUBTRACTIVE`** (the ex-rights reference-price form, 除权除息参考价):
    `p ↦ (p − d_j) × o_j / n_j`. Cash is subtracted first, then the share ratio divides. The
    composition of such maps is affine, so between events `adj_t = a × raw_t − b`, with
    `a = Π o_j/n_j` and `b > 0` whenever any cash event is in the adjustment span. With cash
    events only, `a = 1` and `b = Σ d_j`: a constant cash offset.
  - **`UNKNOWN`:** not yet established by Test V2. A series may not be used for anything that
    depends on its dividend treatment.
- **`anchor`** is `LATEST` (前复权 qfq: rows after the last event up to the vintage equal raw)
  or `EARLIEST` (后复权 hfq: rows before the first event equal raw).
- **`vintage`** is the file's retrieval time. With anchor `LATEST`, `a` and `b` for a given date
  change whenever a later event occurs, so two vintages of one qfq series differ, legitimately
  (Ruling 0.1).

The method is established from the data by Test V2 (§3), not from the source's documentation.
A file manifest that says `UNDECLARED` (as the Eastmoney qfq probe does) is labelled only after
V2 has run.

**Which use needs which:**

- **Valuation** (market value at `D` = replayed quantity `S(D, L)` × price): **`RAW` only.** The
  ledger's quantity at `D` is in the units held at `D` (Ruling 3.2 of `ledger-replay/1.3`
  applies a split at the start of its ex-date), and only the raw close of `D` is quoted in
  those units. Any adjusted series multiplied by a ledger quantity applies a later split twice,
  or a dividend once too often (Example 2-A).
- **Security-level return series** (volatility, beta, correlation; CP3/CP4): a price-return
  series needs `SPLIT_ADJUSTED`; a total-return series needs dividends under a stated
  convention. Which one each metric uses is CP3/CP4's to rule.
  - **RECOMMENDATION:** derive both **inside the engine** from `RAW` plus corroborated
    corporate actions (§4.6, §7). The method is then ours, written down, and stable across
    retrievals.
  - Vendor-adjusted series are kept as **verification inputs** (§3), with full lineage. They
    are not used as analytic inputs unless a later convention admits a specific one.
- **Portfolio return** (CP3) is built from valuations plus ledger flows. It needs no adjusted
  series.

**Never mixed.** A series carries one label for all its points. A computation may not splice
two series with different labels, anchors or vintages. Comparing two series of different labels
is allowed only through the exact factor relationship of §3.

**Rejected alternative:** a single "close" column whose meaning depends on the source. That is
exactly the failure STATUS item 16c names: yfinance's `Close` is split-adjusted, while
Alpha Vantage's free daily series is documented as as-traded.

#### Example 2-A: why valuation needs RAW (hypothetical prices; the listing and dates of `ledger-replay/1.3` Example 3-A)

A1 holds 50 U from 2025-01-06. A `SPLIT (4, 1)` has ex-date 2025-02-03.

- Raw closes: 2025-01-31 **150.00**; 2025-02-03 **38.00**.
- A split-adjusted vintage retrieved after 2025-02-03: 2025-01-31 = 150.00 × 1/4 = **37.50**;
  2025-02-03 = **38.00**.

| Use | `RAW` | `SPLIT_ADJUSTED` |
|---|---|---|
| Value on 2025-01-31, quantity 50 (pre-split units) | 50 × 150.00 = **7,500.00**, correct | 50 × 37.50 = 1,875.00, **wrong by a factor of 4** |
| Value on 2025-02-03, quantity 200 | 200 × 38.00 = **7,600.00** | 200 × 38.00 = 7,600.00 (equal on and after the last split) |
| Price return across the ex-date | 38/150 − 1 = −56/75 ≈ −74.67 %, **wrong** (the split appears as a loss) | 38/37.5 − 1 = **1/75** ≈ +1.333 %, correct |

Valuation therefore needs `RAW`, and a return series needs an adjusted series.

Vintage effect: if U later split `(2, 1)` with ex-date 2026-01-05, a vintage retrieved after
that would show 2025-01-31 = 18.75. That is a different vintage of the same source, not a
disagreement. Ruling 0.1 keeps one vintage in `M`.

### RULING 2.4 (1.1, rewritten): Parsing source numbers through precision profiles

Version 1.0 said "round half-even to `q_m` decimals". That rule is replaced. Rounding a float32
rendering half-even at a fixed decimal count works only by accident.

1. **Never construct a `Decimal` from a binary float.** Read the file's text. Keep the text
   verbatim in lineage.
2. **Every numeric field of every source and market has a precision profile**, held as data
   (Appendix A). The profile gives:
   - the field's **binary format**: `TEXT_DECIMAL`, `FLOAT64` or `FLOAT32`, meaning the type in
     which the upstream or the wrapper last held the number before printing it;
   - the market's **maximum decimals** for a price (`max_dp`, which may depend on price level);
   - for volume, the **unit** (Ruling 2.6).
3. **Normalization.** The normalized value is the **shortest decimal string that converts back
   to the same binary value in the declared format** (the shortest-round-trip rule; Python's
   `repr` does this for float64, and the float32 analogue is the shortest `%.{p}g` that
   round-trips through IEEE-754 binary32).
   - `TEXT_DECIMAL`: the text is the value.
   - `FLOAT64` as printed by pandas: the text is already the shortest round-trip form, so
     normalization is the identity. `1288.0` is 1288.0.
   - `FLOAT32`: normalization recovers the decimal, e.g. `474.20001` → **474.2** and
     `469.39999` → **469.4** (Sina HK closes, observed).
4. **Validation (fail closed).** After normalization, a price must have at most `max_dp`
   decimals for its market and price level. This holds only if:
   - the format can resolve that grid at that price: `ulp(v) < 10^(−max_dp)`, where for float32
     `ulp(v) = 2^(⌊log2 v⌋ − 23)`; and
   - the source really carried a grid price.

   If either fails, the value is **not recovered**. It is kept, but marked imprecise. Its
   §4.2 bound is `½ ulp(v)` in the declared format, and it may **corroborate only**: it is never
   the value used. If the profile is FLOAT32 at too high a price, the remedy is another source,
   not a looser grid.

   **4a (1.2). An unrecovered reading is not an admissible print.**
   - It may confirm another source's recovered value under §4.2 with its `½ ulp` bound.
   - On its own it supplies no price. The session counts as a session without an admissible
     print for Ruling 5.2's count, so the resolved price for `D` is the last admissible print,
     aged accordingly.
   - If no admissible print exists on or before `D`, the result is `INSUFFICIENT_DATA` +
     `MISSING_PRICE_HISTORY` (Ruling 4.4).
   - It carries **no** reconciliation status of its own. `SINGLE_SOURCE` means a value is used,
     and none is.
   - **(1.3 clarification.)** The same holds when **two or more** unrecovered readings agree
     within their `½ ulp` bounds. Agreement does not make any of them a grid decimal, so there
     is still no admissible print. `CORROBORATED` is wrong here: Ruling 4.3 defines it as "the
     primary source's value is used", and no value is used. The datum has no reconciliation
     status. Its agreement may be recorded in lineage as `UNRECOVERED_READINGS_AGREE`, which is
     informational and has no state effect.
5. **Profile check against the data (fail closed).** The signature tests below apply to
   **non-integral fields only**: prices, rates and turnover amounts. A field declared integral
   (volume) is tested by float32 integer spacing instead (A.4 item 2). A field is integral by
   its profile, not because a given value happens to be a whole number. A close of `476.0` is
   still a non-integral field.
   - A field declared `TEXT_DECIMAL` or `FLOAT64` that shows the float32 signature fails the
     check. The signature is that the text equals the 8-significant-digit rendering (`%.8g`) of
     its own float32 value and is longer than its float32 shortest-round-trip form, as
     `474.20001` is (float32 shortest form `474.2`).
   - So does a field declared `FLOAT32` whose text is not the float32 rendering of its own
     float32 value, at 8 significant digits or shortest.

   A failed check means the profile is wrong, so the file is not admitted until the profile is
   corrected. Profiles are versioned data. A change is not a methodology change, but the
   manifest records the profile version.
6. **Volumes** must normalize to an integer in their unit (Ruling 2.6). A non-integral volume
   fails the profile check.
7. **Adjusted values** are not on any grid. They are normalized by rule 3 and never rounded.
   Their imprecision enters §4.2 through the profile.
8. This is parsing normalization. It is not the OI-8 money-rounding convention.

**Why shortest round-trip, not rounding to the grid.** The shortest round-trip form is a
property of the binary value alone. It needs no tick table, so it is not exposed to facts I
state from memory. It is exactly the decimal the upstream wrote, whenever that decimal had at
most 6 significant digits (float32) or 15 (float64). The grid check then verifies the result,
and does not manufacture it. Rounding to `q_m` would silently "repair" a value that was never
on the grid, and that is a silent correction.

**Observed in the probe files** (format evidence, quoted minimally):

- Sina HK `close` shows the float32 signature (`474.20001`, `469.39999`). Sina HK
  `open`/`high`/`low` do not (`473.6`, whose float32 rendering would be `473.60001`).
- Sina US `close` is not float32: `233.85` would render as `233.85001`.
- The volumes are not float32 either. 142,920,468 lies in [2²⁷, 2²⁸), where float32 integers
  are multiples of 16, and 142,920,468 mod 16 = 4. 55,740,727 is odd in [2²⁵, 2²⁶), where they
  are multiples of 4.
- The profile is therefore **per field**, not per file.

### RULING 2.5 (1.1): Which vendor-adjusted series may serve return work, and vendor-derived columns

1. **A `SUBTRACTIVE` series** (or any adjusted series whose V2 method is not `PROPORTIONAL`) is
   **never a return input**, not even with a caveat. It is also not a check on one.
   - Between two dates with no event between them, its return is
     `(raw_t1 − raw_t0) / (raw_t0 − b)` when `a = 1`. The raw return is
     `(raw_t1 − raw_t0) / raw_t0`.
   - Every percentage move is therefore scaled by `raw_t0 / (raw_t0 − b)`. The factor grows
     with `b`, so it grows with the vintage, as dividends accumulate after the window.
   - Once `b` reaches `raw_t0`, the adjusted price is zero or negative and the return is
     undefined. That is a known property of long-dated 前复权 series for high-payout stocks.
   - Volatility, beta and drawdown computed from it describe no investable position.

   (Across the ex-date of the last event in the adjustment span, both methods give
   `P_ex / (P_prev − d)`. Across an earlier ex-date, the subtractive ratio is shifted by the
   later events' offset as well. Either way, the distortion lives *between* events, which is
   most of the series.)
2. **A `PROPORTIONAL` series** is admissible as a **cross-check** of an engine-derived series,
   per the Ruling 2.3 recommendation. Between events its returns equal raw returns exactly.
3. **Consequence for later return work (CP3/CP4).**
   - The engine derives its own split- and dividend-adjusted, or total-return, series from
     `RAW` plus corroborated corporate actions, by a method the CP3 registry entry states.
   - A vendor 前复权/后复权 series from Eastmoney (subtractive, Example 3-C) can serve only as a
     check on the **event maps**: `b` must equal the sum of corroborated cash per share over the
     adjustment span (Test V2, part (c)). It never checks returns.
   - Valuation is unaffected, because it uses `RAW` only (Ruling 2.3).
4. **Vendor-computed derived columns are never inputs.** Eastmoney's 涨跌幅, 涨跌额, 振幅 and
   换手率, a source's "change %" and similar are the vendor's arithmetic on its own (possibly
   adjusted) levels. The qfq file's 涨跌幅 differs from the raw file's on the same day (−2.49
   against −2.36) because the base is shifted by `b`. The engine computes what it needs (P1).
   These columns may be kept in the file but are not parsed into observations, apart from the
   consistency check of Ruling 4.6.

### RULING 2.6 (1.1): Volume units

1. **No rule in `market-data/1.1` uses the magnitude of volume.** The print rule (Ruling 2.1)
   needs only `volume > 0`, which holds in any unit. The profile check (Ruling 2.4 item 6) needs
   only integrality.
2. **Each source and market profile declares the volume unit** (Appendix A):
   - Eastmoney CN reports **lots of 100 shares** (手);
   - Sina HK reports **shares**;
   - Sina US is declared shares but **not yet verified**, because its file carries no turnover
     column.

   Evidence for CN: turnover ÷ (close × volume) is 100.6, 100.5, 100.3, 100.2 and 99.7 across
   the five 600519 rows. The ratio is about 100, and it is not exactly 100 because turnover is
   at traded prices, not at the close. For HK (00700), the same ratio is between 1.0008 and
   1.0094 on the five rows, with a median of 1.0045.
3. **Any later rule that uses volume magnitude** must convert to shares through the profile
   before using it. That covers liquidity, turnover, volume-weighted checks and any
   cross-source volume comparison. **Volume is never compared across sources without that
   conversion.**

   The unit check uses the turnover ratio above. Its **median** over a file's rows that have
   turnover must lie within [0.9, 1.1] × the declared shares-per-unit. The check uses the
   median because the ratio on a single row is VWAP ÷ close, and that can move by up to the
   daily limit on an extreme day. The band only has to separate units that differ by a factor
   of 100 or more.
4. Volume is **not reconciled** across sources in 1.1. Consolidated against primary-venue
   volume legitimately differs, so a volume difference says nothing about the official close.

---

## 3. Adjustment-label verification (STATUS 16c)

### RULING 3.1: A series' adjustment label is verified from its own data before use, and the result is recorded

Every series ingested receives a **label status**: `VERIFIED`, `CONTRADICTED` or
`UNVERIFIABLE`. The tests below are deterministic. Their reference facts (split events) come
from issuer filings recorded as corporate-action observations (PD-0027: HKEXnews, cninfo, SEC
EDGAR). They never come from the series under test.

**Test V0: calendar alignment** (catches a one-day date shift).

- Every session date in the series must be in `C_m(ℓ)`.
- If more than zero dates fall on non-session days, the series is `CONTRADICTED`. For example,
  every row landing on a Sunday is the signature of a UTC conversion (Ruling 2.2).
- **(1.16) Two rows for one session date also make the series `CONTRADICTED`, in every market.**
  - **The unit** is the series (listing, file), as for the rest of V0. In a single-listing file, such
    as every Alpha Vantage file, that is the whole file.
  - **The key is the parsed date, not its spelling.** `2026-09-29` and `20260929` are one date. A
    label that does not parse as a date is its own key, and the row is refused as unparseable anyway.
  - **Identical duplicate rows count too.** One file stating one session twice shows that its dating
    cannot be trusted, by the same reasoning as one misdated row in Test V0-FX. Agreement between the
    two rows is not evidence: they come from one upstream (Ruling 4.3).
  - **Effect** (§3 consequences):
    - the series supplies no reading, and its file stays in `M`;
    - lineage names the test (`V0`), `DUPLICATE_SESSION_DATE` and the dates;
    - that lineage reaches the listing's lookup as its `SERIES_CONTRADICTED` cause.
  - **Why every market.** 1.15 required it only for the CN route's admission (Ruling 7A.3 (c) 3).
    The US path kept both rows: two equal rows gave `SINGLE_SOURCE`, and two different ones gave
    `DISAGREEMENT` for that date only, while the file's other dates were read. That is the "known
    gap" the engineer pinned. One rule for one defect is required by P12, and V0 has no market
    exception. Example 3-E.

**Test V0-FX (1.7): the same test for FX series** (review finding C2-16).

- The unit tested is one currency series from one FX file: (file, currency).
- **Rule.** The series fails, and is excluded **whole**, with lineage cause
  `V0_FX_OFF_CALENDAR`, if **any** row inside the governing `C_ECB` coverage is dated on a day
  that is **not** a fixing day.
  - Excluding only the off-calendar rows is not enough. If every row is labelled one day
    early, only the weekend row would go. As of Monday, the series would then serve Tuesday's
    rate as `CURRENT`. That is look-ahead against Ruling 1.1 ("never a fixing dated after
    `D`").
  - One misdated row is evidence that the series' dating is wrong, so none of its dates can be
    trusted.
- **(1.16 fix round 2, review L-4) A fixing date stated twice also fails the series.** The same
  argument as Test V0 (1.16) for prices, and one rule for one defect (P12).
  - **The key is the parsed date.** If a date appears in more than one row of an FX file, every
    currency series (file, c) read from that file fails, whole, with lineage cause
    `V0_FX_DUPLICATE_DATE` and the dates. A date row carries every currency column, so the defect is
    the file's dating, whatever the values: equal values count too, and so does a row where `c` is
    `N/A` (Ruling 1.6).
  - **It applies inside and outside `C_ECB` coverage.** A duplicate is not a calendar question, so the
    "not judged" clause below does not exempt it.
  - **Why not keep the first row.** Two rows for one date are two statements of one fixing. Serving
    either one is choosing which value wins, which only a resolution record may do (§11 "Must not
    decide"). `src/marketdata/adapters/ecb_eurofxref.py` keeps the first row today and reports the
    second as unparseable. That is the behaviour §11 item 34 replaces.
  - **Example (synthetic).** An ECB file lists 2025-01-02 twice, USD 1.08 and then 9.99. The USD series
    of the file supplies no rate for any date, so `D` = 2025-01-02 never gets 1.08 or 9.99 from it, and
    every other currency series of the same file is excluded with it. Their dates are missed fixings
    for Ruling 1.6. The result is the same when both rows say 1.08.
- **Rows outside `C_ECB` coverage are not judged** (Ruling 5.3). They are `UNVERIFIABLE`, and
  any `D` there resolves to `UNKNOWN` anyway.
- **Added for both prices and FX: a row dated after its file could have contained it also
  contradicts the whole series.** This catches a shift that lands only on valid days.
  - For FX, that means after `D_ret` (Ruling 1.1a item 5).
  - For prices, that means after the latest session whose scheduled close is ≤ the
    manifest's `retrieval_time`.
- **Effect.** An excluded series supplies no readings, but its file stays in `M` (as in the
  §3 consequences). Its dates are then missed fixings for Ruling 1.6: stale, or
  `MISSING_FX_HISTORY` from 5 missed on. A cross whose leg is excluded uses the latest common
  date of the remaining admitted legs.
- **Known limit.** A constant shift by a whole number of weeks, or a file too short to touch a
  non-fixing day, can still pass. The 1.1a comparison of the date set and values with the ECB
  file is the check that catches those, and it is one more reason to obtain the ECB-direct file.

**Test V1: split-day jump** (separates `RAW` from any split-adjusted label).

- Take a **decisive** split event `(n, o)` on `ℓ`, with ex-date `X` inside the series and
  `n/o ≥ 2` or `n/o ≤ 1/2`. Let `p₋` = the series' close for the last session before `X`, and
  `p₊` = its close for `X`. Let `R = p₊ / p₋`.
- Hypotheses:
  - `RAW` predicts `ln R ≈ ln(o/n)`;
  - any split-adjusted label predicts `ln R ≈ 0`;
  - the gap between them is the ex-date's own market move.
- **Rule.** Hypothesis `h` is *consistent* iff `|ln R − ln h| ≤ ln 1.3`.
  - For a decisive event, `|ln(n/o)| ≥ ln 2 = 0.6931 > 2 × ln 1.3 = 0.5247`, so the two windows
    are disjoint, and at most one hypothesis is consistent.
  - The comparison is decidable without floating point: `R` and `h` are exact rationals, and
    `|ln R − ln h| ≤ ln 1.3` ⇔ `1/1.3 ≤ R/h ≤ 1.3`.
- **Why 30 %.** It is a one-session move beyond the split that main-board A-shares cannot make
  (±10 % limit; ±20 % on ChiNext and STAR), and that US and HK large caps essentially never
  make. If the actual move exceeds it, the test returns "neither" and is **inconclusive**. It
  never returns a wrong answer, because the windows do not overlap.
- **Outcome:**
  - every decisive event in the series' window `[first date, retrieval date]` is consistent
    with the claimed label → `VERIFIED` for the split component;
  - any event consistent with the other hypothesis → `CONTRADICTED`;
  - no decisive event, or only inconclusive events → `UNVERIFIABLE`.

**Test V2 (1.1, replaces 1.0's V2): affine fit, which establishes the method.** It applies to
two series of one listing from **one upstream**: a reference series (`RAW`, or split-only
`Close`) and an adjusted series.

- **(a) Fit per interval.** Split the overlap at every known ex-date (corroborated splits and
  dividends) and at every date where the two series' relation changes. In each interval with at
  least two distinct reference values:
  - take the two rows with the smallest and largest reference value, and solve exactly, in
    rationals, for `adj_t = a × ref_t − b`;
  - every other row and every price field (open, high, low, close) must satisfy the fit within
    the propagated precision bound of Ruling 4.2.

  If any row breaks the fit, the relation is not affine in that interval. The method is then
  `UNKNOWN`, and the series is `CONTRADICTED` as any adjusted label.

- **(a′) The bound (1.2).** The bound is **derived from the two series' precision profiles**.
  It is not a caller input, and it is not a function of the market's `max_dp`. Write:
  - `δ_r`, `δ_j` for the §4.2 bounds of the reference and adjusted value on row `i`
    (`δ_r = 0` for a recovered raw close);
  - `e_i = δ_j + |a| × δ_r`;
  - `lo`, `hi` for the two anchor rows;
  - `Δ = ref_hi − ref_lo`.

  Then:
  - **Residual test:** `|adj_i − (a × ref_i − b)| ≤ e_i + max(e_lo, e_hi)` for every row. Every
    row lies between the anchors, so the anchors' error interpolates and is not amplified.
  - **`a ≠ 1`** only if `|a − 1| > u_a = (e_lo + e_hi) / Δ`.
  - **`b ≠ 0`** only if `|b| > u_b = e_lo + |ref_lo| × u_a`.
  - **`δ_r` per field (1.3).** `δ_r` is the bound of **that field's** value on that row. It
    is taken from that field's profile, not copied from the close:
    - **close** that passed the grid validation (recovered): `δ_r = 0`;
    - **open, high, low** (never grid-validated, A.1):
      - `TEXT_DECIMAL` or `FLOAT64`: `δ_r = ½ × 10^(−delivered_dp)`, the source's own
        rounding, which cannot be ruled out without a grid;
      - `FLOAT32`: `δ_r = ½ ulp(v)`;
    - **any field whose value was not recovered**: `½ ulp(v)` in its format, or
      `½ × 10^(−delivered_dp)`, whichever its profile gives.

    Using the close's 0 for open, high and low understates the bound, so a valid series can
    fail V2. The bound must never be smaller than what the source's format guarantees.
  - **(1.4) `delivered_dp` must be declared for every field V2 reads.** If a `TEXT_DECIMAL` or
    `FLOAT64` field V2 needs has no declared `delivered_dp`, **V2 does not run** on that series.
    The `method` is `UNKNOWN`, the label is `UNVERIFIABLE`, and lineage records cause
    `PROFILE_INCOMPLETE`. `½ ulp` of binary64 is **not** a substitute.
    - `½ ulp` of binary64 bounds only the float rendering. It does not bound any decimal
      rounding the source applied first, for example a high or low rounded to 2 dp.
    - So it understates the bound by up to `½ × 10^(−dp)`, and V2 could classify on noise.
    - A float32 field keeps `½ ulp` of binary32, because there the format is the binding limit.
  - An adjusted series' `δ_j` is half a unit of the decimals the source **delivers for adjusted
    values** (profile field `adjusted_dp`). That equals half a unit of `max_dp` only when the
    source happens to deliver `max_dp` decimals and the reference is recovered.
  - **Example 3-C under this bound:**
    - `δ_r = 0` and `δ_j = 0.005`, so `e = 0.005`, `Δ = 48`, `u_a = 0.01/48 ≈ 0.000208`, and
      `u_b = 0.005 + 1240 × 0.000208 ≈ 0.263`.
    - `a = 1` (within `u_a`) and `b = 79.58 ≫ 0.263`, so the method is **`SUBTRACTIVE`**,
      unchanged.
    - Residual bound `0.01`, observed residual 0.
    - **(1.5) Reproduced from the A.3 profile.** The open, high and low fields have declared
      `delivered_dp 2`, so their `δ_r = 0.005`, `e_i = 0.005 + 1 × 0.005 = 0.01`, and the
      residual bound is `0.01 + 0.005 = 0.015`. Their observed residual is 0 (every field is
      exactly 79.58 below raw).
    - The anchors are closes, so `u_a` and `u_b` are unchanged, and so is the classification
      (`SUBTRACTIVE`).
- **(b) Classify the method,** from all intervals together:

  | Fit | Method |
  |---|---|
  | `b = 0` within the bound, `a ≠ 1` | `PROPORTIONAL` |
  | `b ≠ 0` | `SUBTRACTIVE` (affine). With `a = 1` it is a pure cash offset. |
  | `a = 1` and `b = 0` in every interval | `IDENTITY`: no adjustment in this window. The method is `UNKNOWN` (unverifiable here), and the series equals the reference in this window. |
  | proportional in some intervals, subtractive in others | `CONTRADICTED` |

  `b ≠ 0` with `a = 1` cannot come from a proportional method, because a proportional map has
  no additive term. A non-constant ratio `adj/ref` beyond the bound rules out
  `PROPORTIONAL`.
- **(c) Event check, where corporate actions are available.**
  - Across each corroborated event `j`, the change in `(a, b)` must equal the event map of
    Ruling 2.3 under the classified method, within the bound:
    - **proportional:** the ratio of successive `a` values is `(1 − d_j/P_prev,j) × o_j/n_j`;
    - **subtractive:** `a` scales by `o_j/n_j`, and `b` changes as `(p − d_j) × o_j/n_j`
      composes.
  - **Anchor `LATEST`:** for the interval after the last event before the vintage, `(a, b)`
    must be `(1, 0)`. For an interval wholly before it, `b` must equal the composition of all
    later events. With cash events only, that is `b = Σ d_j` over events in (interval end,
    vintage].
  - An event with no matching change, or a change with no known event, makes the series
    `CONTRADICTED`.
- **(d)** Version 1.0's Example 3-B is the proportional case of this test: `a` steps by
  0.99 = 1 − 0.50/50.00, and `b = 0`.

**Test V3: cross-source factor** (ties a source's label to another source's).

- Source A is labelled `RAW`. Source B is labelled `SPLIT_ADJUSTED` with vintage `v`.
- For every common date `t`, `A_t / B_t` must equal `Π (n/o)` over corroborated splits with
  ex-date in `(t, v]`, within the §4.2 bound.
- A ratio of 1 before a split means A is not raw, or B is not adjusted. The test cannot say
  which, so both series are `CONTRADICTED` pending human review.

**Consequences.**

- A `CONTRADICTED` series is **not admitted** to `M` under its label. For each date it covers,
  it is treated as absent.
  - **(1.3 clarification)** "Not admitted" means it supplies **no readings**. The file itself
    stays in `M`, so the result is reproducible, with the failing test and dates in lineage.
  - The unit dropped is the series: (listing, file), or (listing, file, adjustment) where a file
    holds several. A V0 failure drops that listing's series from that file only. It never drops
    other listings in the same file, and never the same listing's series from other files.
- An `UNVERIFIABLE` series is admitted, with that status in lineage:
  - for `RAW` and `SPLIT_ADJUSTED`, the label is moot inside a window that contains no split up
    to the retrieval date, because the two series are then identical;
    - **(1.15)** "Contains no split" is a fact about the world that the admitted sources cannot
      establish. It is never asserted from an absent record, an empty response or a search with no
      hit. The operative rule is Ruling 3.2 item 4: a **known** (filing-attested) split in a
      reading's exposure window, with the label not established for it, withholds the reading.
  - for dividend labels, the status is carried to any CP3 use.

**Candidate decisive events** (to be confirmed by the human from the issuer filing; this
document asserts none of them as fact):

- AAPL 4-for-1 (2020);
- NVDA 10-for-1 (2024);
- Tencent 0700.HK 5-for-1 subdivision (2014);
- any A-share 10转10 (ratio 2) found on cninfo.

#### Example 3-A: Test V1 on a hypothetical 4-for-1 split

Split `(4, 1)`, so `h_RAW = o/n = 1/4`. The market moved +4 % on the ex-date.

| Series claims | `p₋` | `p₊` | `R` | `R / h_RAW` | `R / 1` | Consistent with | Result |
|---|---|---|---|---|---|---|---|
| `RAW` | 400.00 | 104.00 | 13/50 = 0.26 | 0.26 × 4 = **1.04** ∈ [0.769, 1.3] | 0.26, ∉ | `RAW` only | `VERIFIED` |
| `SPLIT_ADJUSTED` | 100.00 | 104.00 | 26/25 = 1.04 | 4.16, ∉ | **1.04** ∈ | adjusted only | `VERIFIED` |
| `RAW` (actually adjusted) | 100.00 | 104.00 | 1.04 | 4.16, ∉ | 1.04 ∈ | adjusted | **`CONTRADICTED`** |
| `RAW` | 400.00 | 200.00 | 1/2 | 2, ∉ | 0.5, ∉ | neither | inconclusive |

(1/1.3 = 0.769…; ln 1.04 = 0.0392.)

#### Example 3-B: Test V2 on a hypothetical dividend

A source gives `Close` (claimed split-only) and `Adj Close` (claimed proportional,
dividend-adjusted). There is one dividend `d = 0.50` with ex-date `E`, `P_prev = 50.00`, and no
later event.

- `Close_{E−1}` = 50.00, `Adj_{E−1}` = 49.50, so `k_{E−1}` = 0.99.
- On `E`: `Close` = `Adj`, so `k_E` = 1.
- Step = 0.99 = 1 − 0.50/50.00 = 99/100. **Consistent.**

If `Close` had also been dividend-adjusted, `k` would be 1 on both sides, with no step at a
decisive dividend: **`CONTRADICTED`**.

#### Example 3-C (1.1): the real Eastmoney qfq file for 600519 is subtractive

The files are `akshare.cn/quote/2026-10-01/600519_2025-01-02_2025-01-08_{raw,qfq}.csv`, both
from upstream Eastmoney (`stock_zh_a_hist`). The qfq manifest declares `UNDECLARED`. Its
vintage is 2026-10-01T03:49:52Z. There is no known event in the window (2025-01-02 to
2025-01-08), so the window is one interval.

- **(a) Fit.**
  - Reference row with the largest close: 2025-01-02, raw 1288.0, qfq 1208.42.
  - Reference row with the smallest close: 2025-01-06, raw 1240.0, qfq 1160.42.
  - `a = (1208.42 − 1160.42) / (1288.0 − 1240.0) = 48 / 48 = 1`.
  - `b = 1288.0 − 1208.42 = 79.58`.
  - Every other close, and every open, high and low on all five rows, satisfies
    `qfq = raw − 79.58` **exactly**. The difference is 3979/50 on all 20 price fields, so the
    residual is 0.
- **(b) Proportional ruled out.**
  - `adj/raw` is 1208.42/1288.0 = 0.938214 on 2025-01-02 and 1162.92/1242.5 = 0.935952 on
    2025-01-08. The difference is 0.002263.
  - The propagated relative bound is the sum of four half-cent terms over prices near 1,200,
    about 1.6 × 10⁻⁵. The difference is about 140 times the bound.
  - **Method: `SUBTRACTIVE`, `a = 1` (a cash offset).**
- **(c) Anchor.** Even the last row is 79.58 below raw. That is consistent with anchor `LATEST`
  at the vintage, because the events after the window are subtracted. It does not verify it.
  Verifying it needs a window that reaches past the last event before 2026-10-01, or the
  event check:
  - the corroborated cash dividends per share of 600519 with ex-dates in
    (2025-01-08, 2026-10-01] must sum to **79.58**;
  - I have not derived that sum. It needs the corporate-action files, and I state no dividend
    figure from memory.

  **Label:** (`DIVIDEND_ADJUSTED`, `SUBTRACTIVE`, `LATEST` unverified, vintage
  2026-10-01T03:49:52Z).
- **Why it matters for returns (Ruling 2.5).**
  - Raw close return from 2025-01-02 to 2025-01-08: 1242.5/1288.0 − 1 = −45.5/1288 =
    **−13/368 ≈ −3.5326 %**.
  - The same span on qfq: 1162.92/1208.42 − 1 = −45.5/1208.42 = **−2275/60421 ≈ −3.7652 %**.
  - The two differ by about 23 bp over four sessions, with no corporate action in between. The
    ratio of magnitudes is 1288/1208.42 ≈ 1.0659 = `raw / (raw − b)`.
  - A volatility computed on this qfq window would be about 6.6 % too high, and the excess
    grows with each later vintage.

### RULING 3.2 (1.15): V1's reference events, the compact-window label, and the split-label exposure of a valuation date

**Problem.** Ruling 3.1 says V1 takes a decisive split "on ℓ" from issuer filings, but not which
records in `M` qualify. Ruling 4.7 item 4 expects most US labels to stay `UNVERIFIABLE`, and Ruling
3.1 admits such a series. It calls the label "moot" where no split lies up to the retrieval date. Yet
nothing says what happens when a split **is known** to lie after a valued date and the label cannot
be tested. There a series mislabelled `RAW` is wrong by the split factor, and P5 forbids showing that
number.

**Rule.**

1. **V1 reference events.**
   - A V1 event for listing ℓ is a `SPLIT` of ℓ for which `M` (or `M_t`) holds a record from a
     source in the confirmation policy's **filing role**. Its status does not matter:
     `CORROBORATED`, `FILING_ONLY` or `DISAGREEMENT`. V1 uses the **filing's** ratio `(n, o)` and
     ex-date.
   - **Never a V1 event:**
     - a feed-only record;
     - a record from the same upstream as the series under test. Ruling 3.1 says reference facts
       never come from the series under test, and Ruling 4.1 makes independence a matter of
       upstream.
       - **(1.16, review F-1) The synthetic world is the exception.** Every synthetic series and
         record has upstream `synthetic` (Ruling 4.8 item 1), so this bullet read literally would
         leave no synthetic V1 event at all. Then the SYNS, SYNT and SYN43 splits could not verify
         (§11 item 17), and Examples 3-D (b)–(d) and 6-E (vi) could not be built.
       - In the synthetic world, therefore, a synthetic record whose source is in the confirmation
         policy's **filing role** is a V1 event for a synthetic series. This is the waiver Ruling 4.8
         item 4(a) already grants corroboration: the fixture author declares the roles, and
         independence is not tested there. Nothing in a synthetic result is a real market fact
         (Ruling 4.8 item 2).
       - A synthetic **feed** record is still never a V1 event (the first bullet).
     - a record from the other world (Ruling 4.8 item 1). Synthetic filing records test synthetic
       series only.
   - V1 needs **admissible prints** (Ruling 2.1 print rule; Ruling 2.4 item 4a) at both `p₋` (the
     last session before `X`) and `p₊` (`X`), in the same file. If either is missing, the event is
     inconclusive.
2. **The label of a compact window** (Alpha Vantage `outputsize=compact`: the latest 100 sessions;
   Ruling 4.7 item 4). The window is `[first row, retrieval]`, as in Ruling 3.1. The decisive
   events that count are the V1 events with `n/o ≥ 2` or `n/o ≤ 1/2` and `X` in
   `(first row, last row]`.
   - **`VERIFIED`:** at least one counted event, and every counted event is consistent with `RAW`.
   - **`CONTRADICTED`:** any counted event is consistent with the adjusted hypothesis.
   - **`UNVERIFIABLE`:** otherwise. This is the usual case, and the series is admitted (Ruling 3.1
     consequences).
   - **Events that do not count:**
     - a non-decisive split (for example 3:2), even if its jump happens to fall in only one window.
       Decisiveness is a property of the event, not of the observed move (Example 3-D (c));
     - an event dated on the first row, or after the last row.
   - **Nothing based on absence changes the label:** no corporate-action file, an empty response
     (Ruling 7.5), or a filing search with no hit. None of them makes the label `VERIFIED` or
     "moot".
3. **The exposure window of a reading.** Take a `RAW`-labelled close for session `d_p`, from a file
   retrieved at `R`.
   - **`N(R)`** = the first session of `C_m(ℓ)` whose local date (exchange zone, Ruling 2.2) is
     **strictly after** the local date of `R`.
   - **`E(d_p, R)`** = { `X` ∈ `C_m(ℓ)` : `d_p < X ≤ N(R)` }.
   - **Why this window.** Under Ruling 2.3, a split-adjusted vintage `R` gives
     `adj(d_p) = raw(d_p) × Π o_j/n_j` over the splits the vendor has applied with ex-date after
     `d_p`. A mislabelled series is therefore wrong at `d_p` only through an ex-date after `d_p`
     that the vendor applied by `R`.
     - An ex-date is a session date.
     - A vendor's overnight batch may apply an ex-date of the coming session before that session
       opens (MEMORY, §12 item 19). So `N(R)` includes the session after `R`'s local date. That is
       conservative by at most one session.
     - **(1.16 fix round, review L-2) Anchor.** This is the backward adjustment that Ruling 2.3
       defines for `SPLIT_ADJUSTED`, and for `DIVIDEND_ADJUSTED` with anchor `LATEST` (qfq). A series
       adjusted with anchor `EARLIEST` (hfq) keeps its earliest rows raw and moves every row on or
       after an event. Mislabelled `RAW`, it would differ at `d_p` through events dated **on or
       before** `d_p`, and no exposure window holds those. `E` does not narrow that residual.
       - V1 on a decisive split inside the file window would show it, since such a series has no jump
         at the split.
       - So would Test V4 on any date on or after one of those events (`v ≠ c*`).
       - Without either, it is part of the `UNVERIFIABLE` label (Ruling 6.5 N-1 to N-3; MD-OI-21).
   - **(1.15) A calendar that does not cover `E`:** Ruling 5.3's coverage-gap rule applies: `UNKNOWN`,
     `INSUFFICIENT_DATA`, no reason code, cause `CALENDAR_COVERAGE_GAP`. **(1.16)** This holds only in
     the one case the next bullet names.
   - **(1.16, review F-4) Only as far as a V1 event must be placed.** `E` is used for one decision:
     whether a V1 event (item 1) of ℓ lies in it (item 4). Take a V1 event of ℓ in `M` with
     ex-date `X > d_p`.
     - Let `T` be the last date of the governing calendar's coverage, and `r` the local date of `R`.
     - **`N(R)` is determined** iff `C_m` holds a session in `(r, T]`. Then `N(R) ≤ T`.
     - Otherwise `N(R)` lies after `T` and is **undetermined**: when `r ≥ T`, or when no covered
       session follows `r`.
     - **`X ≤ T`.** The calendar decides whether `X ∈ E`. `X` is in `C_m` or not.
       - If `X ≤ r`, then `X < N(R)`, so `X ∈ E` whenever it is a session, without knowing `N(R)`.
       - If `X > r` and `X` is not a session, `X ∉ E`.
       - If `X > r` and `X` is a session, `C_m` holds a session in `(r, X]`, which lies inside
         `(r, T]`. So `N(R)` is determined, `N(R) ≤ X`, and `X ∈ E` iff `X = N(R)`.
     - **`X > T`, and `N(R)` determined.** Then `X > T ≥ N(R)`, so `X ∉ E`, whatever the calendar
       would say about `X`. There is no coverage gap (1.16 fix round, reviews C-2 and L-1).
     - **`X > T`, and `N(R)` undetermined.** The calendar cannot say whether `X` is a session, or
       whether `X ≤ N(R)`. **Only here** does Ruling 5.3's coverage-gap rule apply to `E`. This
       includes an `X` with `T < X ≤ r`: `X` precedes `N(R)`, but whether it is a session is unknown.
     - **"After `T`" is meant, not "outside the coverage".** A record dated before the coverage
       starts has `X ≤ d_p` for every reading whose freshness can be counted (Ruling 5.3), so it is
       never in `E`. Example 6-E (iv) holds such a record.
     - **No V1 event of ℓ with `X > d_p` in `M`.** `E`'s coverage is **no condition**. No event can
       be placed, and nothing is inferred from the calendar's silence about later dates. This is not
       absence used as evidence: the rule acts only on records in `M` (item 4), and the calendar
       cannot add one.
     - **Lineage (item 5)** lists `E` as far as the calendar covers it. When `N(R)` lies beyond `T`,
       it adds "coverage ends at `T`; `N(R)` undetermined".
     - Example 3-G.
     - This is the reading 1.15's Example 6-E took. Its calendar line ("covers `D` and `E(D, R)`")
       was a sufficient condition, not a necessary one.
4. **The exposure rule (new behaviour).**
   - **When it applies.** Both of these hold:
     - `M` holds a V1 event (item 1) of ℓ with `X ∈ E(d_p, R)`;
     - the file's `RAW` reading is **not established for `X`**: neither V1 on `X` was consistent
       with `RAW` (a decisive event only, as Example 3-D (c) applies), nor Test V4 on some date
       `d < X` of the same file **established `RAW` for `X` under Ruling 3.3**. That includes 1.16's
       window `(d, N(R)]` and its consolidation condition.
     - **(1.16 fix round, reviews M-1 and C-1) An equality alone does not clear.** Where Ruling 3.3
       finds `v = c*` but establishes nothing, this item applies. Examples 3-F (b) and (e) show it. The
       draft of 1.16 kept 1.15's words "found equality" here, which gave a second state.
   - **Then:**
     - the close at `d_p` supplies **no price** for any `D`;
     - every other close of that file dated before `X` is exposed in the same way, so falling back to
       an earlier print of the file does not help;
     - if no other admitted reading exists, the result is `INSUFFICIENT_DATA` +
       **`MISSING_PRICE_HISTORY`** ("no usable price for the requested date", PD-0030 §1), with
       lineage cause **`SPLIT_LABEL_EXPOSED`** (listing, `X`, file, `E`).
   - **Not these codes:**
     - not `SOURCE_CONFLICT`: no two inputs disagree;
     - not `STALE_DATA`: the older prints are exposed too.
   - **Why withhold rather than caveat.** The two readings differ by the factor `o/n`, not by a
     rounding. Showing either one is choosing a hypothesis the data cannot settle (P5: insufficient
     data suppresses the number).
   - **Scope: splits only.** A filing-role `CASH_DIVIDEND` with ex-date in `E` is recorded in
     lineage as `DIVIDEND_LABEL_EXPOSED`, with no state effect. It is the residual the A.3 profiles
     have disclosed since 1.2: the error is about one dividend's yield, not a factor (anchor
     `LATEST`; for `EARLIEST`, see item 3, "Anchor"). It is a known
     limit (MD-OI-17), and the A-share route checks it before admission (Ruling 7A.3).
   - **How it clears:**
     - V1 on a later vintage that holds `X` (decisive events only);
     - Test V4 on a date `d < X` of the same file, **when Ruling 3.3 establishes `RAW` for `X`**, the
       consolidation condition included (1.16 fix round);
     - an earlier vintage whose `N(R′) < X`, since raw series may be segmented (Ruling 0.1 (1.12)).
       For `X = N` of the valued date's own session, no such vintage can hold `d_p` (Example 3-D
       (d)).
5. **Lineage of every `RAW` reading used in a valuation:**
   - its label status, and the label's source (`PROFILE_CALL_ADJUSTMENT…:MEMORY` or `DECLARED`,
     §9B item 4). **(1.16)** For Alpha Vantage `TIME_SERIES_DAILY` it is `DECLARED`, citing PD-0066
     decision 3. The status is read from the profile data, never fixed in code;
   - `E(d_p, R)` as an explicit date list;
   - **(1.16 fix round 2, review R2-C6) the V1 events, in exactly one of three cases:**
     1. `M` holds V1 events of ℓ with `X` in `E`: each of them (listing, `X`, ratio, source, record).
        Any V1 event of ℓ with `X > d_p` outside `E` is listed too, marked "outside `E`";
     2. `M` holds V1 events of ℓ with `X > d_p`, none of them in `E`: "no V1 event in `E`", with each of
        them listed and marked "outside `E`" (Example 3-G (d));
     3. `M` holds no V1 event of ℓ with `X > d_p`: "no V1 event in `M`" (Examples 3-D (a), 3-G (a); the
        HG4 rows of Ruling 6.5).

     An event with `X ≤ d_p` is not listed: it cannot lie in `E`. The draft's wording ("the V1 events
     found in `E`, or 'none in `M`'") would have written "none in `M`" in case 2, where `M` holds one.

   "No V1 event in `M`" is a statement about `M` after `d_p`, never about the world.
6. **Build order, and the interim rule.**
   - Item 4 is built **together with V1**, never before it. Otherwise the decisive synthetic splits
     of the golden fixtures, which V1 would verify, would be suppressed (see the 1.15 change note).
   - **Until both are built:** a real-data computation is **not run** if its `M` holds a
     filing-role `SPLIT` record with `X` in `E(d_p, R)` of any reading it uses. The PM or the
     engineer checks this on the file list of `M` before the run. It is a refusal, not a silent
     pass.
   - **(1.16) Placing a record.** A record is placed as item 3 places it.
     - A record with `X` after `T` counts as in `E`, so the run is refused, **only when `N(R)` is
       undetermined**.
     - When `N(R)` is determined, `X > T ≥ N(R)` puts the record outside `E`, and the check passes
       (1.16 fix round, reviews C-2 and L-1; Example 3-G (d)).
     - V4 does not lift this refusal. It lifts only when V1 and item 4 are built.
   - For the HG4 single-date `M` of Ruling 6.5, the check is vacuous unless such a record is added.

**Rejected:**

- **Treating "no record in `M`" as no split.** That is absence taken as evidence (Ruling 6.4 item 4;
  E9).
- **Requiring confirmed absence before any US value is `AVAILABLE`.** No admitted source can confirm
  absence, so every US value would be `INSUFFICIENT_DATA` for good. Ruling 4.7 item 4 already chose
  disclosure for that residual.
- **Applying item 4 to feed-only records.** A single free feed would then withhold prices on its own
  word, and its date semantics are not granted (Ruling 7.4). It also reverses Ruling 3.1's choice of
  filings as the reference.

### RULING 3.3 (1.15): Test V4, the exchange reference check

**Input.** A **human-authored reference record**, part of `M` like a resolution record. It states:

- the listing (MIC, local code);
- a session date `d`;
- the **exchange-published official close** `c*` as decimal text;
- the publication: the exchange page or daily report, and the date it was read;
- who recorded it.

An agent may draft the record. A human confirms it against the page before it enters `M`, as for
calendars (Ruling 5.3 item 8). It is never an AI extraction (PD-0027 condition 5). Whether the
exchange site's terms allow noting a single figure for this purpose is part of the human's step
(§12 item 22).

**Test.**

- **When it runs.** The series' close `v` at `d` must be recovered (Ruling 2.4). Then `v` and `c*`
  are two recovered renditions of one official close, so they must be **equal** (Ruling 4.2,
  bound 0). An unrecovered `v` does not run V4.
- **Outcomes for the `RAW` label of the file:**

  | Result | Event with ex-date `X`, `d < X ≤ N(R)` (1.16; a V1 event, or a filing-role `CASH_DIVIDEND`) | Outcome |
  |---|---|---|
  | `v ≠ c*` | any | **`CONTRADICTED`**, whatever the cause: an adjustment, a consolidated last price instead of the official close, or a wrong date. Ruling 3.1's consequences apply. |
  | `v = c*` | yes | The `RAW` reading is **established for that event**, for its component (split or dividend). An adjusted series would differ at `d` by the event's map (Ruling 2.3), which is never the identity for `n ≠ o` or `d_j > 0`. **(1.16)** With several events in the window, this holds for all of them unless one is a consolidation (below). |
  | `v = c*` | none | No label effect. It is recorded as a single-date agreement with the exchange: evidence for Ruling 4.6 item 5. It is not corroboration, because the exchange record is not a price reading in `M`. |

- **(1.16, review F-3) The window is `(d, N(R)]`**, the exposure window `E(d, R)` of the tested date
  (Ruling 3.2 item 3), in session dates. 1.15 wrote `(d, R]`. That compared a date with an instant, and
  it left out `X = N(R)`, which Ruling 3.2 item 4 (1.15) cleared by any V4 equality at `d < X`. One
  input set then gave two states. **(1.16 fix round)** Ruling 3.2 item 4 now clears only where this
  ruling establishes `RAW` for `X`, so the two rulings give one state.
  - The reasoning is the same for every `X > d` the vendor could have applied by `R`: a series
    adjusted for `X` differs from raw at `d`. That holds under backward adjustment (Ruling 3.2 item 3,
    "Anchor"; MD-OI-21).
  - An `X > N(R)` is in no exposure window of this file, so it needs no clearing.
- **(1.16) Several events in the window: the consolidation condition.**
  - Let `W` be the events **recorded in `M`** with ex-date in the window. Under Ruling 2.3, a vendor
    that applied a set `J ⊆ W` shows, at `d`, the composite of their maps applied to `raw(d)`. Equality
    `v = c*` says that composite is the identity at `raw(d)`.
  - Every map except a consolidation **lowers** a positive price:
    - a forward split or 送转, `× o/n` with `o/n < 1`;
    - a proportional cash event, `× (1 − d_j/P_prev)`;
    - a subtractive cash event, `− d_j`, then `× o/n`.

    So a composite of any non-empty set of them is below `raw(d)`. Equality then shows that `J` is
    empty, so `RAW` is established for **every** event in `W`.
  - A **consolidation** (`n < o`, `× o/n` with `o/n > 1`) raises the price. Together with another
    event it can compose to the identity: `(1, 2)` and then `(2, 1)` gives `× 2 × 1/2 = 1`.
  - **Rule.** If `W` holds a consolidation and at least one other event, the equality
    establishes **none** of them (the "none" row's outcome: no label effect). A single consolidation
    alone is established as usual, because its map is not the identity.
  - The rule is conservative: it may refuse where an exact subset test would clear. **Among the events
    recorded in `M`**, it never clears a composite it cannot rule out. Example 3-F.
  - **(1.16 fix round, review L-2) The residual: unrecorded events.** The argument covers `W` only. An
    event with no record in `M` can cancel a recorded one.
    - Take file F1 of Example 3-D (`N(R)` = 10-02) and a V4 record at `d` = 2026-09-01.
    - `M` holds a filing-role `SPLIT (2, 1)` with `X` = 10-01. The issuer also had a 1-for-2
      consolidation on 09-15, and `M` holds no record of it.
    - A vendor that applied both shows `raw(09-01) × 2 × 1/2 = raw(09-01)` at 09-01. So `v = c*`, `W`
      holds the split alone, and `RAW` is "established" for 10-01.
    - Yet the vendor's 09-30 value is `raw(09-30) × 1/2`, because only the split lies after 09-30.
    - This is the closed-world premise on `M` that 1.15's single-event row already carried. The rule
      does not remove it. It is narrower than it looks: an unrecorded event matters only if its ex-date
      lies in `(d, N(R)]`, so a V4 date nearer `X` leaves less room.

- **Unit.** The result belongs to the file's series (listing, file). Each file is tested on its own.
  A route-level observation (Ruling 7A.3) shows how a source behaves. It does not verify a later
  file.

**What V4 never does.**

- `c*` is never a price used, and it changes no reconciliation status (Ruling 4.3).
- Settling a disagreement is the job of a **resolution record**, which is a different object.

**Why.** The exchange's own publication is the definition of the official close (Ruling 2.1). Where
no second admitted source exists (CN and US today, Ruling 4.7 item 4), it is the only reference that
does not come from the series under test.

#### Example 3-D (1.15; hypothetical US listing U; the dates are 2026 NYSE sessions as in the unregistered draft)

File F1 holds the latest 100 sessions, 2026-05-08 to 2026-09-30, and was retrieved at
`R` = 2026-10-01T04:53:50Z, which is 2026-10-01 00:53:50 in New York.

- `N(R)` = the first session after 2026-10-01, which is **2026-10-02**.
- `E(2026-09-30, R)` = {2026-10-01, 2026-10-02}.
- The V1 windows: `RAW` is consistent iff `R/h_RAW ∈ [10/13, 13/10]` ≈ [0.7692, 1.3], with
  `h_RAW = o/n`. The adjusted hypothesis is consistent iff `R ∈ [10/13, 13/10]`.

| Case | Filing-role `SPLIT` records in `M` | V1 | Label of F1 | Valuation from F1 |
|---|---|---|---|---|
| (a) | none | no event | `UNVERIFIABLE` | Close at 09-30 **usable**. Lineage: `E` = {10-01, 10-02}, "no V1 event in `M`". |
| (b) | (2, 1), `X` = 2026-07-15 | `p₋` (07-14) = 300.00, `p₊` (07-15) = 153.00. `R = 153/300 = 51/100`, `h_RAW = 1/2`, `R/h = 51/50 = 1.02` ∈ the `RAW` window. `R = 0.51` ∉ the adjusted window. | **`VERIFIED`** | every date usable |
| (c) | (3, 2), `X` = 2026-07-15 | Not decisive: `n/o = 3/2 < 2`. With `p₋` = 300.00 and `p₊` = 204.00, `R = 17/25 = 0.68` and `R/h = (17/25)/(2/3) = 51/50` happen to be consistent with `RAW` only. But the windows overlap: the `RAW` window for `R` is `[2/3 × 10/13, 2/3 × 13/10] = [20/39, 13/15]` ≈ [0.513, 0.867], against [0.769, 1.3] for adjusted. A move of +16 % (`p₊` = 232.00, `R` = 0.7733) would sit in both. So the event does not count. | `UNVERIFIABLE` | At 09-30, `X` ∉ `E(09-30, R)`, so the close is **usable**. At **07-14**, `E(07-14, R)` = (07-14, 10-02] ∋ 07-15, so the close is **exposed**: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, `SPLIT_LABEL_EXPOSED`. If F1 were split-adjusted, its 07-14 row would read 300.00 × 2/3 = 200.00 for a true raw 300.00, and F1 cannot say which. |
| (d) | (4, 1), `X` = 2026-10-01 | `p₊` is not in F1, whose last row is 09-30, so V1 cannot run. | `UNVERIFIABLE` | `X` ∈ `E(09-30, R)`, so the close at 09-30 is **exposed**: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`. **Remedy:** F2, retrieved after the close of 10-01, holds 09-30 = 320.00 and 10-01 = 81.60. `R = 81.6/320 = 51/200` and `R/h = (51/200)/(1/4) = 51/50 = 1.02`, so `RAW` is consistent and F2 is `VERIFIED`. The 09-30 close from F2 is usable. An earlier vintage does not help: any `R′` whose local date is 09-30 has `N(R′)` = 10-01 = `X`, and before 09-30 no file holds the 09-30 row. |

All the numbers in this example are hypothetical. They say nothing about any real listing.

#### Example 3-E (1.16): duplicate session dates, and delivered decimals, on the US route (synthetic)

**Set-up.**

- **Listing.** Synthetic listing U2 on XNAS, 100 units.
- **Source.** A synthetic source with upstream `synthetic`, read through the `alphavantage.us` profile:
  - `TEXT_DECIMAL`, `delivered_dp 4`;
  - the close grid-checked against the US `price_max_dp`, which is 2 decimals at or above 1.00.
- **Manifest.** Declared `RAW` and USD.
- **Calendar.** The registered `NYSE_SESSIONS 2025-2026 v1`: 2026-09-28 (Monday), 09-29 and 09-30 are
  sessions.
- **Retrieval.** `R` = 2026-10-01T01:00:00Z, which is 21:00 on 09-30 in New York, after that day's
  16:00 close. The latest session closed at `R` is 09-30.
- **Valuation date.** `D` = 2026-09-30.

**File (a): one session written twice, in two spellings, with identical values.**

```
timestamp,open,high,low,close,volume
2026-09-30,50.1000,50.9000,49.8000,50.5000,120000
2026-09-29,49.6000,50.2000,49.5000,50.0000,110000
20260929,49.6000,50.2000,49.5000,50.0000,110000
2026-09-28,49.0000,49.8000,48.9000,49.7000,100000
```

- **Profile check: passes.** Every price shows 4 decimals, and 4 ≤ 4. Every volume is an integer.
- **Row checks** (`low ≤ min(open, close) ≤ max(open, close) ≤ high`): all pass.
  - 09-30: 49.80 ≤ 50.10 ≤ 50.50 ≤ 50.90;
  - 09-29, both rows: 49.50 ≤ 49.60 ≤ 50.00 ≤ 50.20;
  - 09-28: 48.90 ≤ 49.00 ≤ 49.70 ≤ 49.80.
- **V0 (1.16): fails.** The parsed dates are {09-28, 09-29, 09-29, 09-30}. Each is a session, but
  2026-09-29 occurs twice. The series is `CONTRADICTED`: it supplies no reading, and the file stays in
  `M`.
- **`D` = 09-30:** `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, with no value. The lineage cause is
  `SERIES_CONTRADICTED`, naming V0, `DUPLICATE_SESSION_DATE` and 2026-09-29.
- **Before 1.16, on the US path** (as the engineer's pinned test describes it; I did not run it). 09-30
  gave 50.50, `CURRENT`, `AVAILABLE`, worth
  100 × 50.50 = 5,050.00. 09-29 gave two equal readings from one upstream, so `SINGLE_SOURCE`
  (Ruling 4.3). That difference is what 1.16 changes.
- **Variant (a′): the duplicate row has a different close.** Write the second 09-29 row as
  `20260929,49.6000,50.2500,49.5000,50.2500,110000`.
  - The row check passes: 49.50 ≤ 49.60 ≤ 50.25 ≤ 50.25.
  - Before 1.16: |50.25 − 50.00| = 0.25 > 0, so 09-29 gave `DISAGREEMENT` and `SOURCE_CONFLICT` for
    that date only, while 09-30 stayed `AVAILABLE`.
  - Under 1.16: the same result as (a).

**File (b): (a) without the `20260929` row, and the 09-30 close written `50.50000`.**

- **Profile check (A.4 item 7): fails.** `50.50000` **shows** 5 decimals, and 5 > `delivered_dp` 4.
  - The file is not admitted: no reading, and one `PROFILE_CHECK_FAILED` issue on the close.
  - The value 50.5 has 1 decimal and lies on the cent grid, but that is the grid check (Ruling 2.4
    item 4), which counts the **value's** decimals. The profile check counts the decimals the **text**
    shows, trailing zeros included, because a `TEXT_DECIMAL` source is profiled by its fixed decimal
    count (A.4 item 1).
  - The text is not repaired to `50.5000` (Example 7A-G3 (d)).
- **`D` = 09-30:** `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`.

**File (c): (b) with `50.5000`.**

- **Every check passes:**
  - the profile check (4 shown decimals);
  - V0 (three distinct sessions);
  - the after-retrieval test (no row after 09-30).
- **`D` = 09-30:** the print is admissible (volume 120000 > 0, and 50.5 is recovered with 1 ≤ 2
  decimals). `s` = 0, so the result is `CURRENT`, `AVAILABLE`, with value 100 × 50.50 = **5,050.00**.
- **A close written `50.5`** also passes the profile check. Showing fewer decimals than delivered is
  not a failure, and the recovered close's bound is 0 either way.

**The real file.** The stored `alphavantage.us/quote/2026-10-01/AAPL_compact.csv` (SHA-256
`066c65e6…b1b9d1fb`) has 100 rows with 100 distinct dates. All 400 price texts show exactly 4
decimals. I counted these from the file, not through `src/`. So neither change refuses it.

#### Example 3-F (1.16): the V4 window and the consolidation condition (hypothetical; file F1 of Example 3-D)

**Set-up.**

- **File F1.** As in Example 3-D, retrieved at `R` = 2026-10-01T04:53:50Z, which is 00:53:50 on
  2026-10-01 in New York. So `N(R)` = 2026-10-02 and `E(2026-09-30, R)` = {10-01, 10-02}. F1's 09-30
  close is `v` = 320.00, recovered.
- **V4 record.** Listing U on XNAS, `d` = 2026-09-30, with the exchange-published `c*` = 320.00
  (hypothetical). So `v = c*`.
- **The window tested** is `(d, N(R)]` = (09-30, 10-02].

| Case | Filing-role events in the window | What an adjusted F1 would show at 09-30, for each non-empty set `J` the vendor could have applied | Outcome | 09-30 close |
|---|---|---|---|---|
| (a) | `SPLIT (4, 1)`, `X` = 10-02 = `N(R)` | {split}: 320.00 × 1/4 = 80.00 ≠ 320.00 | `RAW` **established** for `X` | **usable**. Under 1.15's key `(d, R]`, 10-02 lay after `R`'s local date 10-01, so the table said "no label effect" and the close stayed exposed. That is review F-3's second reading. |
| (b) | `SPLIT (1, 2)` (a consolidation), `X` = 10-01; and `SPLIT (2, 1)`, `X` = 10-02. Chosen only to show the cancellation. | {cons}: 320.00 × 2 = 640.00; {split}: 320.00 × 1/2 = 160.00; {both}: 320.00 × 2 × 1/2 = **320.00** = `c*` | a consolidation plus another event: **nothing established** | **exposed**: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, `SPLIT_LABEL_EXPOSED` (U; 10-01 and 10-02; F1; `E` = {10-01, 10-02}) |
| (c) | the `SPLIT (1, 2)` of (b) alone, `X` = 10-01 | {cons}: 640.00 ≠ 320.00 | established | **usable** |
| (d) | `CASH_DIVIDEND` 0.26 per share, ex-date 10-01 (`P_prev` = the 09-30 close, 320.00); and `SPLIT (4, 1)`, `X` = 10-02 | {div}: proportional 320.00 × (1 − 0.26/320.00) = 319.74, subtractive 320.00 − 0.26 = 319.74; {split}: 80.00; {both}: 319.74 × 1/4 = 79.935 (equally (320.00/4) − 0.26/4 = 80.00 − 0.065) | no consolidation, and no set gives 320.00: **both components established** | **usable**, with no `DIVIDEND_LABEL_EXPOSED` |

All numbers are hypothetical. In (d) the proportional and subtractive dividend maps agree at `d`
because `d` is the session just before the ex-date: `P_prev × (1 − d_j/P_prev) = P_prev − d_j`.

**Case (e) (1.16 fix round, reviews M-1 and C-1): Ruling 3.2 item 4 goes through Ruling 3.3.**

- **File F4** of listing U holds the rows 2026-09-30 and 2026-10-01 (hypothetical). It was retrieved
  at `R` = 2026-10-01T22:00:00Z, which is 18:00 on 10-01 in New York (EDT), after that day's 16:00
  close.
  - `r` = 10-01, so `N(R)` = 2026-10-02, a session of the registered calendar.
  - `E(10-01, R)` = {10-02}.
  - `E(09-30, R)` = {10-01, 10-02}.
- **Filing-role records in `M`**, chosen only to show the cancellation:
  - `SPLIT (2, 3)`, a consolidation, `X` = 10-01. `n/o = 2/3` lies between 1/2 and 2, so it is not
    decisive and V1 does not count it.
  - `SPLIT (3, 2)`, `X` = 10-02. It is after F4's last row, so V1 cannot run on it.
- **As-traded closes**, with no price move: 09-30 = 320.00, and 10-01 = 320.00 × 3/2 = 480.00.
- **A vendor that applied both events** shows:
  - at 10-01, 480.00 × 2/3 = 320.00;
  - at 09-30, 320.00 × 3/2 × 2/3 = 320.00.
- **V4 record.** `d` = 09-30, `c*` = 320.00. Whether F4 is raw or adjusted for both events, it shows
  `v` = 320.00 = `c*`. Adjusted for one event only, it would show a different value, and V4 would
  contradict it:
  - the consolidation alone (`SPLIT (2, 3)`, `× o/n = × 3/2`): 320.00 × 3/2 = **480.00**;
  - the split alone (`SPLIT (3, 2)`, `× 2/3`): 320.00 × 2/3 = 640/3 = **213.33…** (a vendor would print a
    rounding of it, still ≠ 320.00).

  (Fix round 2, reviews M-1 and R2-C1. The draft said 640.00 for the consolidation alone. That is case
  (b)'s `SPLIT (1, 2)` value, `× 2`, not this example's `× 3/2`.)
- **Ruling 3.3.** The window `(09-30, 10-02]` holds the consolidation and the split, so nothing is
  established.
- **Ruling 3.2 item 4 at `D` = 10-01.** `X` = 10-02 lies in `E(10-01, R)`. V1 cannot run on it, and V4
  establishes nothing, so `RAW` is not established for `X`.
  - The 10-01 close is **exposed**: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`,
    `SPLIT_LABEL_EXPOSED` (U; 10-02; F4; `E` = {10-02}).
  - The 09-30 close is exposed too, since both events lie in its window.
- **Why it matters.** The draft read "any equality clears". Under that reading, the 09-30 equality
  would clear 10-02 and show 320.00 as `AVAILABLE` for 10-01. If F4 is adjusted, the as-traded close is
  480.00, and 480.00 / 320.00 = 3/2: the number is wrong by a split factor.
- **Remedy for 10-01.** A V4 record at `d` = 10-01 with `c*` = 480.00.
  - If F4 shows 480.00, the window `(10-01, 10-02]` holds the split alone, so `RAW` is established for
    10-02, and the 10-01 close is usable.
  - If F4 shows 320.00, `v ≠ c*`, and F4 is `CONTRADICTED`.
- **The 09-30 close stays exposed under the rule.** No V4 date before 10-01 has a window without the
  split. Both records together would exclude every non-empty `J`, but the rule tests one record at a
  time. It is conservative, as stated above.

#### Example 3-G (1.16): an exposure window that runs past the calendar (hypothetical file; the registered NYSE calendar)

**Set-up.**

- **File F3.** Listing U on XNAS, compact, holding the 2026-09-30 row. It was retrieved at
  `R` = 2027-01-04T22:00:00Z, which is 17:00 EST on Monday 2027-01-04. This is review F-4's scenario.
- **Calendar.** `NYSE_SESSIONS 2025-2026 v1`, coverage to `T` = 2026-12-31.
- **Dates.** `d_p` = `D` = 2026-09-30.
- **`N(R)`** = the first session strictly after 2027-01-04. It is beyond `T`, so it is **undetermined**.
- **The covered part of `E(2026-09-30, R)`** is (2026-09-30, 2026-12-31], which holds **64** sessions:
  - weekdays: 22 in October 2026 (1–2, 5–9, 12–16, 19–23, 26–30), 21 in November (2–6, 9–13, 16–20,
    23–27, 30) and 23 in December (1–4, 7–11, 14–18, 21–25, 28–31), so 66 in all;
  - minus 2026-11-26 and 2026-12-25, which the registered file closes;
  - the result equals the file's date count.

| Case | V1 events of U in `M` with `X > d_p` | Can `X` be placed? | 09-30 close |
|---|---|---|---|
| (a) | none | nothing to place | **usable**. Lineage: `E` = the 64 listed sessions, then "coverage ends at 2026-12-31; `N(R)` undetermined", and "no V1 event in `M`". |
| (b) | filing-role `SPLIT (3, 2)`, `X` = 2026-11-02 (a Monday and a session). No V4 record. | yes: `X ≤ T`, and `X` is before `R`'s local date, so `X < N(R)` and `X ∈ E` | **exposed**: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, `SPLIT_LABEL_EXPOSED`. (3, 2) is not decisive, so V1 does not count it. |
| (c) | filing-role `SPLIT (2, 1)`, `X` = 2027-01-05 | no: `X > T`, and `N(R)` is undetermined, because `r` = 2027-01-04 is after `T` | coverage gap: freshness `UNKNOWN`, `INSUFFICIENT_DATA`, no reason code, cause `CALENDAR_COVERAGE_GAP` (`NYSE_SESSIONS`, uncovered from 2027-01-01). Until V1 is built, the interim rule refuses the run (Ruling 3.2 item 6). |
| (d) | **File F1 of Example 3-D instead of F3** (`R` = 2026-10-01T04:53:50Z, `r` = 2026-10-01): filing-role `SPLIT (2, 1)`, `X` = 2027-01-15 | yes: `X > T`, but `N(R)` = 2026-10-02 is determined (a session in `(r, T]`). So `X > T ≥ N(R)`, and `X ∉ E` = {10-01, 10-02}. | **usable**. No coverage gap, and the interim rule does not refuse. Lineage: `E` = {10-01, 10-02}, and "no V1 event in `E`", with the 2027-01-15 record listed as outside `E`. |

Under 1.15, case (a) had two readings: `CALENDAR_COVERAGE_GAP`, and usable. 1.16 keeps the second.
Case (d) comes from the 1.16 fix round (reviews C-2 and L-1). The draft applied the gap whenever
`X > T`, and so gave case (d) a coverage gap with a refused run.

---

## 4. Two-source reconciliation (PD-0027 condition 4)

### RULING 4.1: What is compared

The comparison is like with like:

- **Prices:** two `RAW` official closes for the same `(ℓ, session date)`. A second source that
  only offers a split-adjusted series (yfinance) may be compared after exact un-adjustment by
  corroborated split factors (Test V3's factor). The derived value carries the propagated
  precision bound.
- **FX:** the same ECB quote from two retrieval paths (the ECB's own history file and a
  re-server such as Frankfurter). This is a **transport** check, not independent corroboration:
  both come from one publisher. FX is therefore single-source in the development tier. The
  independent checks are the bands of Ruling 1.5.
- **Corporate actions:** a feed record against the issuer filing, field by field (§4.6).

**Independence (1.1, sharpened).** The independence group is the **upstream**: the
organization whose pipeline produced the numbers. It is not the library that fetched them.

- Every source has an `upstream` attribute (Appendix A). In the current landscape:
  - `akshare.cn` via `stock_zh_a_hist` is upstream **eastmoney**;
  - `akshare_sina.*` is upstream **sina**;
  - Alpha Vantage is upstream **alphavantage**;
  - Frankfurter and the ECB file are upstream **ecb**.
- Two sources corroborate only if their upstreams differ. Two functions of one library that
  reach two upstreams (Eastmoney and Sina through AKShare) **are** independent in this sense.
- Two functions that reach one upstream are not. For example, two Eastmoney endpoints, or a
  re-server of the same feed, do not corroborate, and agreement between them counts as
  `SINGLE_SOURCE`.
- All upstreams ultimately report the same exchange's official close. Independence here means
  separate collection, storage and adjustment pipelines, so that a processing error in one is
  not replicated in the other. It does not mean separate primary data. That is the right
  notion: the official close is the quantity both should reproduce.
- **The shared wrapper is a common-mode component.** A parsing or column-mapping defect in the
  library could make both upstreams agree on a wrong number. Ruling 4.6 adds the safeguards.
  Corroboration through one library is valid, provided those safeguards pass.

### RULING 4.1a (1.2): Which readings enter a price reconciliation

The **reading set** for `(ℓ, session date)` contains only readings that are:

- admitted (terms attested, label not `CONTRADICTED`);
- in `ℓ`'s trading currency;
- either `RAW`, or un-adjusted to raw by the exact factor of Test V3 from **corroborated**
  corporate actions.

That gives three cases:

1. **A reading in a currency other than the listing's trading currency is refused at ingest.**
   A listing has one trading currency (PRD §8.2). A different currency means either a wrong
   currency label or a different listing (an HKEX RMB counter is its own `listing_id`). Neither
   is a comparable reading of this listing's close. The refusal is a data error, flagged with
   the file. It is not a comparison outcome.
2. **An adjusted reading that cannot be un-adjusted exactly** is left out of the reading set,
   with a lineage note that it is not comparable. A missing corroborated factor and a
   `SUBTRACTIVE` method with an unknown `b` are two ways this happens. Such a reading has no
   status and no effect on the resolved value.
3. The status of the resolved value (Ruling 4.3) is computed over the reading set only.

### RULING 4.2: The tolerance is a precision bound, not a judgment

Two values `a` (source A) and `b` (source B) of the same official close **agree** iff

```
|a − b| ≤ δ_A(a) + δ_B(b)
```

Here `δ_X` is the **precision bound of the value as source X delivers it**, from its profile
(Ruling 2.4, Appendix A):

- **`0`** for a raw price that was **recovered**: it passed Ruling 2.4's validation, so it is
  exactly a grid decimal. Two recovered values of one official close must therefore be
  **equal**.
- `½ × 10^(−d_X)` for a text source that rounds coarser than the market grid, with `d_X`
  decimals declared in its profile. Such a value corroborates only.
- `½ ulp(v)` in the declared binary format, for a value that was **not** recovered.
- `F × δ` of the input, for a value derived by an exact multiplication by a factor `F`
  (un-adjustment).
- for an adjusted value, the format bound of rule 3 in Ruling 2.4, propagated through the fit.

Profiles are data (Appendix A), checked against each file's own content (Ruling 2.4 item 5).
Examples 4-A (a) to (c) keep their status under 1.1:

- (a): 12.34 and 12.3400 are both recovered and equal, so the bound is 0 and the difference
  is 0;
- (b): 187.44 and 187.43 are both recovered and unequal;
- (c): the derived value uses `F × δ`.

**Why this tolerance, and why it is neither a forecast nor an opinion.** An official close is
one number published by the exchange. Two faithful renditions can differ only by how each was
written down. The bound is exactly that difference.

- It contains no statistic, no expectation of any price, no materiality judgment and no view
  of which source is better.
- A difference larger than the bound means the two sources report **different numbers**: a
  consolidated last versus the official close, a wrong date, an adjustment, a typo. We then do
  not know which is the official close.
- A looser materiality tolerance would be an opinion about which errors matter, applied before
  anyone has looked.
- If US sources routinely differ by a tick (a consolidated-tape close), the remedy is to choose
  a source that publishes the official close. It is not to widen the bound.

### RULING 4.3: Reconciliation status, and which value is used

Each resolved datum carries exactly one status:

| Status | Meaning | Value used |
|---|---|---|
| `CORROBORATED` | two independent sources agree within §4.2 | the **primary** source's value |
| `SINGLE_SOURCE` | only one source has the datum, or the sources share an upstream, or (FX) no independent second source exists | that source's value |
| `DISAGREEMENT` | two sources differ beyond §4.2, or two vintages of one raw series differ (a revision) | **none** |
| `IMPLAUSIBLE` | (FX) the value breaches a published bound (Ruling 1.5) | **none** |
| `DISAGREEMENT` (1.2, same upstream) | two renditions from **one** upstream differ beyond §4.2: two functions or endpoints of one upstream, two vintages of a raw series, or the ECB file against Frankfurter | **none** |
| `RESOLVED_BY_EVIDENCE` | a former `DISAGREEMENT` or `IMPLAUSIBLE`, settled by a human-authored resolution record in `M` | the value the record names |

**Why agreement and disagreement are asymmetric within one upstream (1.2).**

- Agreement between two renditions of one pipeline is not independent evidence, so it stays
  `SINGLE_SOURCE`.
- Disagreement is evidence that the pipeline reported two numbers for one official close, and
  then we do not know which is right. That is `DISAGREEMENT`, by the same reasoning as a
  revision (Ruling 0.1).

**Primary order (1.1: by upstream, held as data in Appendix A).**

| Market | Order (1.2, admitted upstreams only; PD-0031/0032) |
|---|---|
| CN | **none admitted** (Ruling 4.7) |
| HK | **none admitted** (Ruling 4.7) |
| US | alphavantage |
| FX | ecb: the ECB's own file if admitted (Ruling 1.1a), then Frankfurter v1. One upstream, so this is a transport check only. |

Refused upstreams (eastmoney, sina) are removed from the order. They do not sit at its end.
If a future PD admits them, the order is re-set in a new version. 1.1 named "AKShare primary"
(PD-0027); that no longer applies, because no AKShare route is admitted. Because recovered values that agree are **equal** (δ = 0), the order can only
matter when a value is unrecovered. It never matters to a number that is used.

The order decides only which of two **agreeing** values is carried. Within the bound they are
the same official close, so nothing is decided by it. When the primary lacks the datum, the
second source's value is used as `SINGLE_SOURCE`, and the status says so.

**No source silently wins.**

- A `DISAGREEMENT` is never settled by primary order, recency, a majority of vendors or an
  average.
- It is settled only by a **resolution record**: a human-authored file in `M` that names the
  value and cites the authority. Examples of authorities are the exchange's daily quotation
  report and the issuer's filing. **Never an AI model** (PD-0027 condition 5).
- The record is versioned like any other input, so the resolved value is auditable (P9).
  Both original values stay in lineage.

`SINGLE_SOURCE` does not degrade sufficiency. FX is always single-source in the development
tier, and degrading every translated value would make the state meaningless (the PD-0006
argument). It is disclosed in lineage, and HG2's reconciliation evidence counts it.

That holds equally when one upstream is temporarily unreachable (Eastmoney throttling) or
permanently absent (BaoStock, unreachable from the owner's network). Nothing in this document
requires two upstreams for a value to be used. Two are required only for `CORROBORATED`,
which HG2 reports as a share of all values.

### RULING 4.4: State consequences, in the existing vocabulary where it fits

| CP2 outcome for one input | Sufficiency of that input | Reason code (1.1, PD-0030 §1) |
|---|---|---|
| price `DISAGREEMENT` | `INSUFFICIENT_DATA` | `SOURCE_CONFLICT` |
| FX `DISAGREEMENT` or `IMPLAUSIBLE` | `INSUFFICIENT_DATA` | `SOURCE_CONFLICT` |
| a ledger split in conflict with a corroborated corporate action, or not recorded (Ruling 6.4) | valuation `INSUFFICIENT_DATA` for the affected dates | `SOURCE_CONFLICT` |
| no price print ≤ `D` at all | `INSUFFICIENT_DATA` | `MISSING_PRICE_HISTORY` |
| FX missing (Ruling 1.6) | `INSUFFICIENT_DATA` | `MISSING_FX_HISTORY` |
| stale price or FX (Rulings 1.6, 5.2) | per the tables | `STALE_DATA` |
| freshness `UNKNOWN` (no calendar coverage) | `INSUFFICIENT_DATA` | none: it is a configuration gap, not a data condition |

Coupling, per PD-0030: `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` both require a
non-`AVAILABLE` state. Under HG1 round 4 §6, they pair with `INSUFFICIENT_DATA` at the level of
the affected input, and with `LIMITED` on an aggregate only when the excluded weight is stated
(R1). Neither may pair with `AVAILABLE`.

A price with ≥ 5 missed sessions stays `STALE_DATA`, not `MISSING_PRICE_HISTORY`, because a
print exists (HG1 round 4 §5.4). `MISSING_PRICE_HISTORY` means no print on or before `D`, or a
listing with no admitted series at all, for example when every series for it is
`CONTRADICTED`.

Codes that **must not** be used for these outcomes:

- `CALCULATION_ERROR` is an engine fault (HG1 round 4 §6 R2).
- `LEDGER_INCONSISTENT` means the ledger contradicts *itself* (PD-0025 §1). A ledger that
  disagrees with a corporate-action record is a conflict between two inputs.
- `UNSUPPORTED_ASSET` concerns a method's domain, not data coverage.
- `STALE_DATA` may not stand in for a conflict.

Propagation to metrics is CP3's. The rule already fixed applies: aggregates may be `LIMITED`
only with the excluded weight stated (HG1 round 4 §6 R1).

### RULING 4.5: Corporate-action and FX reconciliation specifics

- **Split:**
  - the ratio is compared as an **exact rational** (`(15, 10)` = `(3, 2)`);
  - the ex-date must be **equal**.
  - **(1.15) A ratio delivered as a decimal factor.** This applies to a feed whose ratio field is a
    decimal with `d` delivered decimals, and only once its direction is granted (Ruling 7.4).
    - The feed agrees with the filing's exact ratio `n/o` iff `|v − n/o| ≤ ½ × 10^(−d)`. This is
      Ruling 4.2's precision bound applied to a ratio: a decimal rendering of 1/3 can never equal
      1/3 exactly. When `v` happens to be exact (`4.0000`), the difference is 0, so the exact
      comparison above is the special case.
    - **A corroborated event carries the filing's `(n, o)`.** The feed's text and bound stay in
      lineage.
    - **The filing side must state an exact ratio.** Issuer filings do: "four-for-one",
      "每10股转增4股". A filing record without one cannot be normalized under Ruling 7.1, and
      cannot be a filing record of a `SPLIT`.
    - **A feed-only decimal record** keeps its text, its exact decimal value (`0.3333` is
      3333/10000) and its bound. No computation uses its ratio: it is `SINGLE_SOURCE`, so there is
      no detection, no append and no V1 event (Ruling 3.2 item 1). No "nearest simple fraction" is
      derived from it.
- **Cash dividend:**
  - per-unit amount, declared currency, ex-date and pay date must be **equal**;
  - a per-10-share quote ("10派2.5元") is normalized exactly to 0.25 per share before
    comparing.
  - **(1.14) Paid fields** (`paid_currency`, `paid_amount`, `issuer_fx_rate`, Ruling 7.1).
    - **Both sides state them:** they must be equal too (`paid_amount` exactly, as a decimal).
      Otherwise the dividend is in `DISAGREEMENT`.
    - **One side states them:** the declared fields decide the status as above. The paid fields
      are then a `SINGLE_SOURCE` addition, used as stated (Ruling 4.3: single-source values are
      used). A feed often omits what the filing states, and the omission is not a contradiction.
- **Corroboration** means a feed record and an issuer filing agree. A feed-only or filing-only
  record is `SINGLE_SOURCE`.
- **FX transport check:** the two retrievals of one ECB quote must be equal as decimals
  (trailing zeros ignored). Any difference is `DISAGREEMENT`.

### RULING 4.6 (1.1): Safeguards when two upstreams share one wrapper library

When both sides of a corroboration were fetched through the same library (AKShare today), all of
the following must hold. Otherwise the pair's status is `SINGLE_SOURCE`, not `CORROBORATED`, and
the failing check is flagged.

1. **Different code paths.** The two sides came from **different library functions, each
   specific to its upstream**: `stock_zh_a_hist` (eastmoney) and the Sina daily function. They
   were not produced by one function with an upstream switch that shares the parsing code.
   The manifest's `request.function` records this, and the engineer checks it.
2. **Row-internal consistency on both sides.** On every row,
   `low ≤ min(open, close) ≤ max(open, close) ≤ high`, after normalization. A column-mapping
   defect (open and close swapped, say) usually breaks this on some row of any multi-day file.
   A failing row is not admitted from that file.
3. **Within-source arithmetic** where the upstream supplies it. For Eastmoney, 涨跌额 must equal
   `close_t − close_{t−1}` exactly on consecutive rows of the same file (raw file:
   1275.0 − 1288.0 = −13.0 ✓). This is used only as a check, never as an input (Ruling 2.5
   item 4).
4. **Library version in lineage.** A different library version is a different vintage (Ruling
   0.1). Two sides fetched with different versions are still comparable. One version on both
   sides is the common-mode case these checks address.
5. **RECOMMENDATION (HG2 evidence).** Spot-check, against at least one value per market from a
   path that does **not** go through the shared library: Alpha Vantage once a key exists, or the
   exchange's own published daily quotation for a date. This bounds the common-mode risk with
   evidence rather than argument.

**Why this does not reject one-library corroboration outright.** Corroboration exists to catch
an upstream's own errors: a wrong date, an adjustment applied to a "raw" series, a
consolidated-tape close. Those originate upstream, and two upstreams catch them whatever
fetched them. What a shared wrapper adds is one extra common failure point. That point is a
parser, so it is the kind of failure checks 1 to 3 detect.

### RULING 4.7 (1.2): A market with no admitted source

Under PD-0031 and PD-0032, CN and HK have no admitted price source. US has one upstream
(alphavantage), and FX has one (ecb).

1. **Each listing on a market with no admitted source** resolves, for every `D`, to
   `P(ℓ, D) = none`, `INSUFFICIENT_DATA` + **`MISSING_PRICE_HISTORY`** (Ruling 4.4: "a listing
   with no admitted series at all").
   - The cause is recorded in lineage as `NO_ADMITTED_SOURCE` with the market. A UI or AI
     explanation can then say "no licensed price source for this market", not "the data is
     missing".
   - Its freshness is `UNKNOWN`. It is **not** `STALE_DATA`, because nothing was ever printed.
   - Refused files that sit on disk are not readings. They are never consulted, not even as
     corroboration.
   - **(1.16) `NO_ADMITTED_SOURCE` is the cause only when `M` holds no series of ℓ at all.**
     - If `M` holds a series of ℓ that was excluded (`CONTRADICTED`, Ruling 3.1), that exclusion is
       the cause (`SERIES_CONTRADICTED`, with its test and dates), and `NO_ADMITTED_SOURCE` is **not**
       added. Lineage names causes, not every true statement about the market (§9B item 3: each
       cause keeps its own lineage entry, so a UI or AI explanation can say why).
     - **In a real `M` the two cannot meet.** No real reading of a market whose A.5 list is empty
       enters `M` (item 6), so no such series can be excluded there.
     - **In a synthetic `M` they can.** The synthetic upstream is that world's source (Ruling 4.8), so
       a synthetic series of a CN listing exists and can fail. Its own failure is then the true cause.
       Example 7A-G2 (c) expects V0 and 2026-09-25 only.
     - A synthetic `M` that holds **no** series of a CN or HK listing still records
       `NO_ADMITTED_SOURCE`, as before. Nothing else would explain the missing price, and the result
       is marked synthetic anyway (Ruling 4.8 item 2).
2. **The ledger facts stay available**: quantity, native-currency cost basis, and cash in CNY or
   HKD (Tech Plan §13.E). Only what combines a quantity with a price is suppressed: market
   value, weights, unrealized gain, and any return.
3. **Aggregates (CP3, sharpening MD-OI-4).**
   - Under HG1 round 4 §6 R1, an aggregate may be `LIMITED` only if the excluded weight is
     stated as a number.
   - A holding with no price has **no measurable value**. So its weight in a market-value
     aggregate cannot be stated in value terms, and that aggregate cannot meet R1.
   - **My ruling, for CP3 to adopt or replace:** a market-value aggregate that includes any
     holding with no price is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`. It is not a
     partial total presented as the total. **(1.8) Adopted** by `performance/1.0` Ruling 1.4,
     which extends it to every cause of an unvalued component.
   - A separately labelled "value of priced holdings" with an explicit count of unpriced
     holdings is a different metric. Whether to have it is a CP3/design question.
   - Weighting the excluded part by cost basis is **rejected**. It would mix a historical
     amount with current values.
4. **`SINGLE_SOURCE` everywhere it applies** (all US prices, all FX) does not downgrade
   sufficiency (Ruling 4.3). The consequences for verification are recorded:
   - Test V3 (cross-source) cannot run for US.
   - Test V1 needs a decisive split inside Alpha Vantage's 100-session window, which is rare.
   - So most US series' split labels will be `UNVERIFIABLE`. They are admitted with that status
     (§3).
   - **(1.15)** The label of a compact window, and what happens when a known split falls after a
     valued date, are ruled in Ruling 3.2 items 2–4. What a single-date value may claim is ruled
     in Ruling 6.5.
   - For now, HG2 has **no price-to-price reconciliation evidence** for US.
   - The only cross-checks available are against issuer filings (SEC EDGAR), for corporate
     actions, once such files exist.
   - That should be said plainly at HG2. It is not a defect of the method; it follows from
     which sources are admitted.
5. **The market states are data, not code.** A.5 lists admitted upstreams per market. A market
   whose list is empty is in this ruling's case. Admitting a source (a new PD) changes the data
   and nothing else.
6. **(1.16) The per-reading form of A.5: admission is judged by the listing's market, not by the
   file's source id.** This is the method behind the engineer's listing-market gate. It answers
   review findings M-1, R-1 and R-2 of the A-share route rounds.
   - **A real price reading** (a raw or adjusted quote) bound to listing ℓ is admitted only if **all**
     of these hold:
     1. ℓ's MIC maps to a V1 market in the table below;
     2. the reading's source has a profile, and the profile is admitted (A.3: not `TO_OBSERVE`,
        `MEMORY` or refused) and covers that market;
     3. the profile's upstream is in A.5 for that market.

     Otherwise the reading is refused.
   - **A source with no profile never supplies a real price reading**, whatever its registry entry or
     terms check says (Appendix A: "a missing profile fails closed"; §11 "Must not decide"). OpenFIGI
     and the calendar files are identity and reference sources. They are not price sources, so a
     quote attributed to them is refused (review R-2). **(1.16 fix round 2)** The refusal's label is
     `SOURCE_NOT_ADMITTED`, for a price reading and for a corporate-action record alike.
   - **A real corporate-action record bound to ℓ:**
     - condition 1 holds;
     - **a source with a profile** supplies such records only under conditions 2 and 3, as for its
       price readings. Its profile must be admitted and must cover the market, and its upstream must be
       in A.5 for that market (1.16 fix round, review C-6).
       - A source that is pending observation, or refused, for a market's prices supplies no
         corporate-action record of that market's listings either. This is defence in depth for a
         store built by hand (the R-2 class).
       - `src/` does this today. `store.py` `_require_readings_admitted` sends a
         `CorporateActionObservation` through `require_listing_market`, which applies the profile's
         `not_admitted_reason`. The draft of 1.16 named only market coverage here; read literally, it
         would have let a `TO_OBSERVE` or refused source's records through;
     - **a filing-role source with no price profile** declares the markets it covers in its own
       Appendix A.3 entry, a **filing profile**, added in the version that records its registration
       (OP-6; for example SEC EDGAR US, cninfo CN). A record bound to a listing outside them is refused
       (`SOURCE_MARKET_NOT_COVERED`). A.5 does not apply to such a source: A.5 orders price sources only,
       so an empty A.5 list does not refuse a cninfo record of a CN listing.
       - **(1.16 fix round 2, review R2-C5) Why A.3, not `SOURCES.json`.** The draft said "its registry
         entry", but `SourceRecord` has no markets field, and adding one would move every source-registry
         digest (`source_registry_digest`, `performance` Ruling 1.7 (1.12) item 4) for no change of
         terms. Market coverage is convention data, like a price profile's markets, so it belongs in the
         profile set. Adding a filing profile is a content change, so the profile counter moves
         (§11 item 32).
       - **A filing profile states:** the source id; role `FILING`; the markets it covers; the record
         types it attests (for example `SPLIT`, `CASH_DIVIDEND`); and the terms reference recorded at
         registration. It has no price fields, so it never supplies a price reading (the bullet above).
       - **A source with no profile of either kind supplies no real corporate-action record**, as for
         prices, with the same label `SOURCE_NOT_ADMITTED`. `src/` lets such a record through today
         (`listing_market_refusal` returns no refusal for a source with no profile, and ingest checks a
         non-price file only against a profile that exists). Today no filing source is registered
         (PD-0067 decision 4), the HG4 `M` holds no corporate-action file (PD-0066 decision 2), and the
         data root holds none (I listed it on 2026-10-24), so this refuses nothing that any current
         result uses. Synthetic records are exempt (below).

     Its **use** is governed by Rulings 6.4d, 7.4 and 7.6.
   - **MIC → market** (convention data, read with Ruling 2.2 item 1):

     | MIC | Market |
     |---|---|
     | XNYS, XNAS, ARCX (NYSE Arca), BATS (Cboe BZX), XASE (NYSE American) | US |
     | XHKG | HK |
     | XSHG, XSHE | CN |
     | any other, for example BJSE (the Beijing Stock Exchange, not a V1 market: Ruling 7A.1 item 3), or a Stock Connect or segment MIC | **none**: not a V1 market |

     - ARCX, BATS and XASE are added because V1 ETFs often have their primary listing there (MEMORY,
       §12 item 25). Mapping them lets the gate judge their readings. It does not make their prices
       usable: until a checked calendar names them, they stay `FRESHNESS_UNKNOWN` (Ruling 2.2 item 1;
       MD-OI-20).
     - **An unmapped MIC refuses the reading.** It never passes unjudged (review R-1).
     - **RECOMMENDATION (engineer):** also refuse a MIC outside this table when an identity is
       registered, so that a Beijing or segment-MIC listing never enters the identity table.
   - **The refusal labels.** These are labels of an **admission refusal**:
     - `SOURCE_NOT_ADMITTED`;
     - `SOURCE_PENDING_OBSERVATION`;
     - `SOURCE_NOT_IN_PRIMARY_ORDER`;
     - `SOURCE_MARKET_NOT_COVERED`: the listing's market is known, and the source's profile (or a
       filing source's filing profile, fix round 2) does not cover it;
     - `LISTING_EXCHANGE_UNKNOWN`: the listing's market cannot be established, because its MIC is
       unknown to the identity supplied or maps to no V1 market. (1.16) The unmapped case is folded
       into this label, and the detail names the MIC.

     **The labels are not reason codes** (Ruling 4.4; PD-0030; §11 "Must not decide": no new reason
     codes).
     - They never appear as a `MetricResult`'s reason, as a metric's lineage cause, or as a data
       condition in UI or AI wording.
     - They are recorded where the refusal happens: the ingest issue, or the store or release-build
       refusal, with source, listing and MIC. They are like Ruling 0.1's `REFUSED_*` labels.
   - **What a metric shows.** There are two fail-closed paths, and neither admits the reading.
     - **The refused reading is left out of `M`.** This is a release builder's choice, as
       `real_slice` makes it. The exclusion must be recorded in the release's record, with its label
       (P9). The listing then resolves as if the reading had never existed. Where A.5 is empty, that
       is item 1 (`NO_ADMITTED_SOURCE`).
     - **The build is refused whole.** No computation runs.
   - **Synthetic readings** are exempt, as from every other admission gate. They never meet real data
     (Ruling 4.8).

### RULING 4.8 (1.2): Synthetic data is its own upstream and never meets real data

PD-0031 makes synthetic fixtures the CP2 test basis, and HG2 on synthetic prices for CN and HK
is one of the owner's open options (STATUS 17).

1. A synthetic series has `upstream: synthetic` and lineage `synthetic: true`. It is never in
   the same reconciliation as a real reading, in either direction: it neither corroborates nor
   is corroborated, and it never resolves a disagreement.
2. An `M` that contains a synthetic file marks **every** result computed from it as synthetic.
   This is a lineage flag on the manifest, like the separation of hypothetical and actual
   states (P8). No result from a synthetic `M` may be presented as a real market fact.
3. Expected values for synthetic fixtures are derived by hand from the synthetic inputs, as for
   any golden fixture. They are never recorded from the implementation's output.
4. **(1.9; review CP3-3) Synthetic corporate-action evidence.** This item answers how item 1
   combines with Ruling 6.4 item 2.
   - **(a) Corroboration happens within one world.**
     - A split is corroborated only by a feed record and an issuer-filing record that agree
       (Ruling 4.5) and are **both real** (subject to Rulings 4.1 and 4.6), or **both synthetic**.
     - A synthetic record and a real record never corroborate each other, in either direction
       (item 1).
     - For two synthetic records, the independence test of Ruling 4.1 does not apply. Both have
       upstream `synthetic`, and the fixture author declares them as the two sides of Ruling 4.5,
       the feed and the filing.
   - **(b) Synthetic evidence never causes an append** (F8-B, PD-0030 §2; review C2-2), to any
     ledger, in a dry run or not. The outcome that would have been `NOT_RECORDED` + append is
     **`NOT_RECORDED`, append barred (synthetic evidence)**. The CP2 dry run reports it in place of
     `WOULD_APPEND`.
   - **(c) Synthetic evidence does drive detection and suppression,** exactly as real evidence
     does: Rulings 6.4 item 2, 6.4a and 6.4c, with the same outcomes and the same
     `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from the same dates.
     - Suppression creates no ledger fact. It only withholds a valuation that would mix pre-split
       quantities with post-split prices. Turning it off for synthetic evidence trades a withheld
       number for a fabricated one, which is the outcome review CP3-3 measured (1,875 against a
       true 7,500).
     - That is the reverse of the order item 1 protects.
   - **(d) The append bar depends on the evidence, not on `M`.** A split corroborated by **real**
     feed and filing records may be appended under F8-B even when the same `M` also holds
     synthetic price files. The CP2 rewrite of every finding to `SYNTHETIC_EVIDENCE` merely
     because `M` contains a synthetic file is corrected to this.
   - **(e) There is no "real ledger" test.**
     - The ledger carries no real or synthetic flag. The protection for real results is item 2:
       every result computed against an `M` that holds any synthetic file is marked synthetic,
       and may never be presented as a real market fact.
     - So synthetic evidence can suppress a valuation only inside a result that is already
       synthetic. It cannot alter a presentable real figure.
     - **RECOMMENDATION (PM):** product presentation paths should refuse a user portfolio's
       presented figures against an `M` holding synthetic files. That is the P8-style separation
       of the HG2 demonstration from real use. It is a product boundary, not a method.
   - **Consequence for `cp3_golden`.** A "corroborated split missing from the ledger" case is
     producible on synthetic data. It supplies a synthetic feed record and a synthetic filing
     record that agree, and gives `NOT_RECORDED` (append barred) and `INSUFFICIENT_DATA` +
     `SOURCE_CONFLICT` from the ex-date.

#### Example 4-A: price reconciliation (hypothetical values)

| Case | Source A (primary) | Source B | Bound `δ_A + δ_B` | `|a − b|` | Status | Value used |
|---|---|---|---|---|---|---|
| (a) A-share, A 2 dp, B 4 dp | 12.34 | 12.3400 | 0.005 + 0.00005 = 0.00505 | 0 | `CORROBORATED` | 12.34 |
| (b) US, A 2 dp, B 4 dp | 187.44 | 187.4300 | 0.00505 | 0.01 | **`DISAGREEMENT`** | none, `INSUFFICIENT_DATA` |
| (c) US pre-split, B = split-adjusted 6 dp × corroborated factor 4 | 499.23 | 124.807503 × 4 = 499.230012 | 0.005 + 4 × 0.0000005 = 0.005002 | 0.000012 | `CORROBORATED` | 499.23 |
| (d) HK, B lacks the date | 3.450 | none | n/a | n/a | `SINGLE_SOURCE` | 3.450 |

#### Example 4-B (1.15): a decimal split factor against a filing ratio (hypothetical records; the feed is read as new/old)

| Feed text (`d`) | Bound `½ × 10^(−d)` | Filing ratio | `\|v − n/o\|` | Status | Event ratio |
|---|---|---|---|---|---|
| `4.0000` (4) | 1/20000 = 0.00005 | (4, 1) | 0 | `CORROBORATED` | (4, 1) |
| `1.5000` (4) | 0.00005 | (3, 2) | 0 | `CORROBORATED` | (3, 2) |
| `0.3333` (4) | 0.00005 | (1, 3) | \|3333/10000 − 1/3\| = \|9999 − 10000\|/30000 = **1/30000** ≈ 0.0000333 | `CORROBORATED` | (1, 3) |
| `0.6667` (4) | 0.00005 | (2, 3) | \|20001 − 20000\|/30000 = 1/30000 | `CORROBORATED` | (2, 3) |
| `0.3333` (4) | 0.00005 | (1, 4) | 3333/10000 − 2500/10000 = 833/10000 = 0.0833 | `DISAGREEMENT` | none |
| `0.2500` (4) | 0.00005 | (4, 1) | \|1/4 − 4\| = 15/4 | `DISAGREEMENT` (a direction error is caught) | none |
| `0.33` (2) | 0.005 | (1, 3) | \|33/100 − 1/3\| = 1/300 ≈ 0.00333 | `CORROBORATED` | (1, 3) |
| `0.333333` (6) | 0.0000005 | (1, 3) | 1/3000000 ≈ 0.00000033 | `CORROBORATED` | (1, 3) |

The ex-dates are equal in every row. If they were not, the status would be `DISAGREEMENT` whatever
the ratio.

---

## 5. Freshness (PRD §11.2; threshold per PD-0006 and HG1 round 4 §5.4)

### RULING 5.1: Freshness belongs to (observation, as-of), not to the observation

The same close is current as of one date and stale as of a later one. Freshness is therefore
**computed when an input is resolved for `D` or `t`**, from the calendar and `M`. It is
**not** fixed at ingest.

The observation stores only:

- its source time;
- its session or fixing date;
- `DataDelayStatus` (`END_OF_DAY` for all PD-0027 files).

### RULING 5.2: The deterministic rule (end-of-day data)

**Prices.**

- `s(ℓ, D)` = the number of sessions `d ∈ C_m(ℓ)` with `last_print(ℓ) < d ≤ D`.
- In Current mode, count only sessions whose scheduled close is ≤ `t`.
- `last_print` follows the print rule of Ruling 2.1.

**FX.** `m(D)` per Ruling 1.6.

| Count since the last print or fixing | `FreshnessState` | Sufficiency effect, price | Sufficiency effect, FX |
|---|---|---|---|
| 0 | `CURRENT` | none: `AVAILABLE` | none: `AVAILABLE` |
| 1 | `STALE` | `AVAILABLE` + `STALE_DATA` | `AVAILABLE` + `STALE_DATA` |
| 2–4 | `STALE` | `LIMITED` + `STALE_DATA` | `LIMITED` + `STALE_DATA` |
| ≥ 5 | `STALE` | `INSUFFICIENT_DATA` + `STALE_DATA` | `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` (Ruling 1.6) |
| cannot be counted: the calendar does not cover the interval, or the observation has no session date | `UNKNOWN` | `INSUFFICIENT_DATA`, no code | `INSUFFICIENT_DATA`, no code |

- The price thresholds are those of HG1 round 4 §5.4, restated, not changed. `CURRENT` here is
  that section's `CURRENT_CLOSE`. `CURRENT` is the name in `contracts.py`, and it means
  "latest available close (or fixing); none has been missed".
- During a US session with end-of-day data, the latest close is `CURRENT` (no close has been
  missed), and its delay status `END_OF_DAY` says it is not live. Both are shown on the D5 axis.
- `UNKNOWN` fails closed. Calendars are reference data this project controls, and a missing
  calendar is a gap to fix, not a reason to guess.
- Freshness says nothing about **temporal comparability** (PD-0014 Part 1). Two `CURRENT`
  inputs from different markets are still measured at different instants (Ruling 1.2).

#### Example 5-A: an A-share across a holiday (calendar assumed for the example)

Assumed `C_XSHG`: sessions 28, 29, 30 Apr; closed 1–5 May; sessions 6, 7, 8, 9, 12 May. Last
print 30 Apr.

| `D` | Sessions in (30 Apr, `D`] | `s` | Result |
|---|---|---|---|
| 5 May | none | 0 | `CURRENT`, `AVAILABLE` (a holiday is not staleness) |
| 6 May (no 6 May print in `M`) | {6} | 1 | `STALE`, `AVAILABLE` + `STALE_DATA` |
| 9 May | {6, 7, 8, 9} | 4 | `LIMITED` + `STALE_DATA` |
| 12 May | {6, 7, 8, 9, 12} | 5 | `INSUFFICIENT_DATA` + `STALE_DATA`, no value |

A suspended stock follows the same rows. Under the print rule, a suspension and a data gap
look the same, and both give the honest result: the current value is unknown. Reconciliation
separates them, because a gap is a date the second source has.

### RULING 5.3 (1.2): What a calendar file must contain, and how a coverage gap is represented

Rulings 1.6, 2.1, 2.2 and 5.2 count sessions and fixings. They need exactly the following from
a calendar file. The format, meaning the serialization and field names, is the engineer's.
**The content is not.**

**Required content (both kinds of calendar):**

1. **`calendar_id`** and **kind**: `EXCHANGE_SESSIONS` or `ECB_FIXINGS`.
2. **`applies_to`**:
   - for exchange calendars, the MICs it governs (e.g. `[XNYS, XNAS]`; `[XSHG, XSHE]`;
     `[XHKG]`);
   - for the ECB calendar, `[ECB]`.

   Every listing's MIC must be governed by **exactly one** calendar in `M`. Zero or more than
   one makes that listing's freshness `UNKNOWN`.
3. **`timezone`**: an IANA name (Ruling 2.2).
4. **`coverage`**: one **contiguous, closed** date interval `[from, to]`.
   - Inside it, the file is complete: a date is a session (or fixing day) **if and only if**
     it is listed.
   - Outside it, nothing is known.
   - One calendar may not have several disjoint intervals. Extending coverage makes a new
     version of the file.
5. **`dates`**: the **explicit list** of session dates (exchange) or fixing dates (ECB) inside
   coverage.
   - It is an explicit list, not "weekdays minus holidays". A-share make-up working weekends,
     for instance, are not trading days, and an explicit list carries no such rule.
   - It lists **actual** sessions: a session cancelled after the fact (an unscheduled closure)
     is removed in a new version (Ruling 2.2 item 4).
6. **Close time per session** (exchange calendars): a default scheduled close, plus explicit
   overrides for half or early sessions. This sets `observed_at` (Ruling 2.2 item 3) and the
   Current-mode rule "sessions whose scheduled close ≤ `t`" (Ruling 5.2).
   - **(1.8) Which instant.** The scheduled close is the **latest instant at which the session's
     official closing price can be determined** under the exchange's rules. It is never an
     earlier instant, because Current mode would then treat a close as available before it
     exists.
     - **HKEX: 16:10, and 12:10 on half days.** The closing auction session runs from 16:00 and
       ends at a random moment in roughly its last two minutes (about 16:08–16:10), and the
       official close of an auction-eligible security is the auction price (MEMORY, §12 item 3).
       16:00 is rejected: for auction-eligible securities the close does not exist yet then.
       Per-security close times (auction-eligible or not) are rejected: they need an
       eligibility list this project does not hold, and gain at most ten minutes.
     - SSE/SZSE 15:00 (end of the closing call auction); NYSE/Nasdaq 16:00, early closes 13:00
       (unchanged).
     - **(1.16)** 15:00 holds for SSE funds before the 2026 revision too: a close formed from the
       last minute of trading (MEMORY, Ruling 2.1) exists at the end of trading, 15:00. The 15:05–15:30
       after-hours session comes after the close and does not move it.
     - **(1.16)** ARCX, BATS and XASE: 16:00 ET, early closes 13:00 (MEMORY, §12 item 25). These are
       stated in the calendar file that names them, once one is checked.
   - For `ECB_FIXINGS`: the fixing time (**14:10**, 1.8) and the nominal publication time
     (16:00, Ruling 1.6 Current mode).
7. **`actual_through`**: the last date up to which the list has been checked as actual rather
   than scheduled. Dates after it, still inside coverage, are scheduled.
   - Counting uses the list as given either way.
   - A resolved value records in lineage whether its counted interval went past
     `actual_through`.
   - This has no state effect. A later correction is a new calendar version, and results
     reproduce per version.
8. **Evidence**: the publisher reference for the holiday or closure list (exchange notice or
   circular; for the ECB, the TARGET closing days), who prepared the file, and when.
9. A version label. The **content hash** is computed by the loader, as for every file in `M`
   (Ruling 0.1: one version per `calendar_id` in `M`).

**A calendar is never derived from a price or rate file.** That would be circular: Test V0
compares the two, and the freshness count would then always say "no session missed". It is
hand-made from the publisher's notices. A price file's dates may be used only as a
**cross-check** that the human reviews. Example A-1 shows one.

**Coverage gaps: one rule, everywhere.** Any count over an interval that is not wholly inside
`coverage` cannot be made. The intervals are `(last_print, D]` (Ruling 5.2), `(u(D), D]`
(Ruling 1.6), the search for `s(D)` or `e(D)`, and a series window for Test V0. The result:

| Count needed | Result |
|---|---|
| price freshness (Ruling 5.2) | freshness `UNKNOWN`, `INSUFFICIENT_DATA`, **no reason code** (as 1.1) |
| FX missed fixings (Ruling 1.6) | freshness `UNKNOWN`, `INSUFFICIENT_DATA`, no reason code (Ruling 1.6 table, last row) |
| `s(D)` or `e(D)` lookup itself | the same. There is no fallback to "the latest weekday". |
| Test V0 on a series window | `UNVERIFIABLE` for the uncovered part. The series is still admitted, but any `D` in that part resolves to `UNKNOWN` anyway. |

- Weekdays are **never** inferred as sessions, and a missing year is never filled.
- The reason code stays null deliberately. A coverage gap is a configuration defect in
  reference data this project controls, not a property of the market data. It must be visible
  in lineage (`CALENDAR_COVERAGE_GAP`, with the calendar and the uncovered dates) so that it
  gets fixed, not explained to a user as a data condition.

---

## 6. F8: who applies a split to positions

### 6.1 The problem

`ledger-replay/1.3` applies `SPLIT` events from the ledger (Rulings 0.2, 3.2, 3.4, §7). PRD
§12.2 calls for *automatic* split support, which points at the CP2 corporate-action feed. If
both apply a split, it is applied twice. If neither does, the ledger quantity and the raw
price are in different units from the ex-date on. In both cases the valuation is wrong by the
split factor (Example 6-A).

### 6.2 Options

| | Who applies | Double application | Determinism | User-visible behaviour |
|---|---|---|---|---|
| **F8-A** | Ledger only, entered by the user or by import. The feed **detects** and flags, and never applies. | impossible: replay reads only the ledger | `S(D, L)` unchanged | An unrecorded split suppresses valuation from the ex-date until the user records it. Not "automatic". |
| **F8-B** | Ledger only, but the **system appends** the `SPLIT` event when a split is **corroborated** (feed and filing agree, §4.5). The event is provenance-linked to the observations and reversible by `REVERSAL`. | impossible: replay reads only the ledger; the append is idempotent per `(account, listing, ex-date)`; F12/0007 refuses a second live split | each append is a new `L`, so reproducibility holds | Automatic, as PRD §12.2 asks. The system writes into the user's ledger. |
| F8-C | The feed applies the split inside replay, with no ledger event. | likely if the user also records it | positions then depend on `M` as well as `L` | automatic, opaque |
| F8-D | Both, de-duplicated by matching | possible when the dates or ratio forms differ (`(15, 10)` against two events; record date against ex-date) | fragile | automatic |

**Rejected by me (methodology): F8-C and F8-D.**

- **F8-C** breaks PRD §9.1 (transactions are canonical and positions are derived) and §12.1
  (corporate actions are ledger-affecting events). It makes a position depend on a free feed
  whose ticker and delisting coverage is weak (STATUS 16d). It also lets a feed correction
  change a historical position without a new ledger version.
- **F8-D** reintroduces exactly the ambiguity Ruling 3.4 removed (duplicate, component or
  successive split).

### 6.3 F8-B: DECIDED by the owner (PD-0030 §2). F8-A applies until F8-B is implemented.

PD-0030 §2 adds the following conditions:

- the appended event is **attributable**: its source reference names the feed record, the
  filing and the market-data version `M`;
- it goes through the normal store path (idempotent, migration 0007, reversible by
  `REVERSAL`);
- a `SINGLE_SOURCE` or disputed split is never appended.

Ruling 6.4 below is unchanged by the decision. It already specified exactly this.

The reasons I gave when recommending it:

- it meets PRD §12.2 "automatic";
- it keeps one point of application (the ledger), so double application is structurally
  impossible;
- it requires corroboration, so a single free source can never move a user's quantities.

**Until F8-B is implemented, F8-A applies.** It changes no user quantity.

### RULING 6.4: Invariants under either F8-A or F8-B

1. **Replay reads only ledger `SPLIT` events.** No feed record enters `S(D, L)`.
2. **Detection.** For each corroborated split `(n, o)` on `ℓ` with ex-date `X`, find every
   account whose position in `ℓ` is non-zero at the start of `X` (at the current `L`; the Ruling
   3.4 condition). For each such account, the ledger must hold exactly one live `SPLIT` with
   date `X` and an equal ratio as a rational. Otherwise:
   - **No ledger split.** Valuation of that position (quantity × `RAW` price) is
     `INSUFFICIENT_DATA` for every `D ≥ X`, flagged "corporate action not recorded".
   - **Ledger split with the same ratio but a different date `Y`** (for example a record date
     or pay date). Valuation is `INSUFFICIENT_DATA` for every `D` in `[min(X, Y), max(X, Y))`,
     because quantity and price are in different units there. Flag "split dated off its
     ex-date".
   - **Ledger split with a different ratio.** `INSUFFICIENT_DATA` from `min(X, Y)`, flagged
     conflict.

   The replayed **quantity itself is still reported** as the ledger fact it is. Only the
   valuation that combines it with a price is suppressed, with reason code `SOURCE_CONFLICT`
   (1.1, PD-0030 §1).
3. **Under F8-B (decided, PD-0030; applies once implemented):**
   - the system appends one `SPLIT (n, o)` dated `X` per affected account;
   - if an equal live split already exists, nothing is appended (idempotent no-op);
   - if a split with a different ratio or date exists, the system appends nothing and the
     conflict of item 2 stands for the user to correct;
   - `SINGLE_SOURCE` corporate actions are never auto-appended.

   A non-integral result still follows §7 of `ledger-replay/1.3` (unresolved-convention), which
   is unchanged.
4. **A ledger split with no corroborating record** is flagged in lineage and does **not**
   change sufficiency. The ledger is canonical, and absence from a weak free feed is not
   evidence of absence (STATUS 16d).
5. **A raw-price discontinuity** (a session-to-session ratio ≥ 1.9 or ≤ 1/1.9) with no recorded
   corporate action is a **review flag only**, with no state effect. It points the human at a
   possibly missing corporate action. It is not evidence of one.

### RULING 6.4a (1.4): Linking ledger splits to corroborated splits: a window of ±20 sessions

Items 2 and 3 above compare "the" ledger split with a corroborated split, but 1.0–1.3 never said
which ledger splits are compared. Read literally, item 3 lets any other split on the position, at
any date, block every later append for ever. That was not intended. The linking rule is this.

1. **Window.** For a corroborated split `K = (n, o)` on listing `ℓ` with ex-date `X`, the
   linking window `W(K)` is the closed interval from the **20th session before `X`** to the
   **20th session after `X`**, counted in `C_m(ℓ)` (Ruling 5.3).
   - If the calendar does not cover `W(K)`, linking cannot be evaluated. The position's
     valuation is `INSUFFICIENT_DATA` from `X` with no reason code and lineage cause
     `CALENDAR_COVERAGE_GAP` (Ruling 5.3), and nothing is appended.
2. **Candidates.** For each account with non-zero units at the start of `X`, the candidates are
   the live ledger `SPLIT`s on `(account, ℓ)` dated inside `W(K)`. Splits outside the window are
   not candidates for `K`.
3. **Outcomes, for that account and `K`:**

   | Candidates in `W(K)` | Outcome | Valuation | F8-B |
   |---|---|---|---|
   | none | `NOT_RECORDED` | `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from `X` | append `SPLIT (n, o)` dated `X` (subject to Ruling 6.4b) |
   | exactly one, dated `X`, ratio equal as a rational | `MATCHED` | no effect | no-op |
   | exactly one, ratio equal, dated `Y ≠ X` | `CONFLICT_DATE` | `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` on `[min(X, Y), max(X, Y))` | no append |
   | any candidate with a different ratio, or two or more candidates | `CONFLICT_RATIO` | `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from `min(X, earliest candidate date)` | no append |

4. **Ledger splits that no window contains** fall under item 4: they are flagged in lineage
   (`UNCORROBORATED_LEDGER_SPLIT`) and change no state, **whatever their ratio**. A ledger split
   with an equal ratio but outside every window is therefore **not** `CONFLICT_DATE`. It is a
   different split, or one the free feed does not know about.
5. **Overlapping windows (1.6, tightened).**
   - **When it applies.** Two corroborated splits `K₁` (ex-date `X₁`) and `K₂` (ex-date
     `X₂ > X₁`) of the same listing `ℓ` in `M` have overlapping windows: `W(K₁) ∩ W(K₂) ≠ ∅`.
   - **Then, for every account** with non-zero units in `ℓ` at the start of `X₁` or of `X₂`:
     - **both** outcomes are `CONFLICT_RATIO`, **whatever the ledger contains** (no candidate,
       one, or several, matching or not);
     - **nothing is appended** for either split;
     - valuation is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from `X₁`, with lineage cause
       `OVERLAPPING_SPLIT_WINDOWS`.
   - **Decided from the whole of `M`.** The test runs over every corroborated split of `ℓ` in
     the market-data version, not over a caller's date range. It never depends on the order in
     which splits were appended or evaluated.
   - **Why the ledger is not consulted.**
     - Under F8-B, appending the split for `K₁` would put a ledger split inside `W(K₂)`. That
       would change `K₂`'s outcome, and then `K₁`'s, so the result would depend on evaluation
       order.
     - Two corroborated records close together can also be one event recorded twice, for
       example an ex-date revised between vintages.
     - Failing closed for the pair removes both risks.
   - **If the overlap cannot be decided,** because the calendar does not cover both windows,
     both splits take the coverage-gap outcome of item 1, from `X₁`, and nothing is appended.
   - **How it clears.** A human-authored resolution record in `M` cites the issuer filings and
     states that `K₁` and `K₂` are two distinct events, or that one of them is not real.
     - **Distinct:** each window is cut at the midpoint. `W′(K₁)` keeps the sessions of `W(K₁)`
       strictly closer to `X₁` than to `X₂`, and `W′(K₂)` likewise. A ledger split exactly
       equidistant stays `CONFLICT_RATIO`. Then the item-3 table applies to each split
       separately, and F8-B may append.
     - **One not real:** the other is evaluated alone.
   - A listing that splits twice within 40 sessions is rare enough that failing closed costs
     little. The fail-closed part matches the engineer's CP2 fix-round implementation, as the
     coordinator reported it; I have not read that code. The coverage-gap case and the
     resolution-record clearing path are written here in 1.6 and may not be built yet.
6. **Why ±20 sessions.**
   - A user who records a split off its ex-date records one of its own dates: record date,
     payable or distribution date, or the date the shares were credited. These sit close to
     the ex-date:
     - US large splits: payable date one session before ex-date, record date about one to two
       weeks before;
     - A-shares: record date (股权登记日) one session before ex-date (除权除息日);
     - Hong Kong bonus issues: certificates dispatched some weeks after the record date.

     These offsets are **MEMORY**, to be confirmed with §12. Twenty sessions, about four
     calendar weeks, covers all of them.
   - The window is short enough that two genuine splits of one listing essentially never share
     it.
   - A shorter window would turn a pay-date entry into a spurious second split, which Ruling 6.4
     item 4 would silently accept. A longer one would link unrelated splits.
   - This is a convention; the number is a written choice, as the freshness thresholds are.
7. **The engineer's 1.3 rule is corrected** (§9C item 1):
   - "equal ratio, explained by no corroborated split" is `CONFLICT_DATE` **only inside a
     window**;
   - "different ratio on a different date" is a conflict **inside** a window and merely
     uncorroborated **outside** it.

### RULING 6.4b (1.4): A user's reversal of a system-appended split is final for that window

1. When the user reverses a `SPLIT` that the system appended under F8-B, that reversal is
   **final**. The system never appends a split again for the same `(account, ℓ)` with a date
   inside the reversed event's linking window `W(K)`. This holds under every later `L`, every
   later market-data version, every release, and a re-observed or corrected corporate action
   whose window contains the reversed event's date.
   - The user's act is the most specific evidence the system has about that account, and a
     system that re-appends what the user removed is overriding the user (PD-0030: "reversible
     by the user").
2. **Detection still runs** (F8-A behaviour). With no live split in the window, the outcome is
   `NOT_RECORDED`:
   - valuation from `X` is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`;
   - lineage cause `SYSTEM_SPLIT_REVERSED_BY_USER`.

   The units of the ledger and of the raw price still disagree, so a value cannot be shown.
3. **The user clears it** by either:
   - recording the split themselves, in which case the outcome is `MATCHED` or `CONFLICT_DATE`
     by the table; or
   - correcting the history so the position holds no units at the start of `X`, in which case
     detection no longer applies.
4. **A corroborated split whose window does not contain the reversed event's date** is a
   different event and follows the normal F8-B rule.
5. The engineer's FINAL treatment is **confirmed**, with this scope (§9C item 2).

### RULING 6.4c (1.9; review CP3-2): A suppression follows the units, including units carried by an internal transfer

**Problem.** Ruling 6.4 item 2 suppresses the positions that hold units **at the start of `X`**.
Units moved after that by an internal transfer arrive in an account that did not hold the listing
at `X`. Read literally, they arrive unsuppressed. Yet they are the same pre-split units, valued at
the post-split raw price. The review's probe valued them at 4,375 against a truth of 10,000 or no
value. Ruling 6.4's purpose is that a quantity and a price in different units are never
multiplied. That purpose attaches to the **units**, not to the account that held them on `X`.

**Rule.**

1. **Tainted lots.** For a corroborated split `K` (ex-date `X`) and a source position `(a, ℓ)` that
   Ruling 6.4/6.4a suppresses over an interval `[F, E)`:
   - `F = X`, or `min(X, Y)`;
   - `E` is open-ended, or `max(X, Y)` for `CONFLICT_DATE`;
   - the lots that `(a, ℓ)` holds on a day `T` in `[F, E)` are **tainted for `K`** on `T`.
2. **The taint travels with carried lots.** An internal security transfer out of `(a, ℓ)`
   dated `T` in `[F, E)` carries lots to the receiving position `(a′, ℓ)` (`ledger-replay`
   0.4.5; the lot fold). Every carried lot that is tainted on `T` arrives tainted.
   - Carried again, by a further internal transfer, it stays tainted.
   - Several hops are followed.
3. **How long a carried taint lasts.** It lasts from the in-leg date `T` until the earliest of:
   - **(a)** the carried units have left the receiving position (Rule 4);
   - **(b) `X` itself**, **only** when the source's suppression was `CONFLICT_DATE` with `Y < X`.
     There the ledger had split the units early, and the market catches up at `X`;
   - **(c)** a ledger version `L′` at which the source position is no longer suppressed on `T`.
     For example, F8-B or the user appended the split dated `X` in the source account. Taint is
     evaluated per `L`, so at `L′` the carried lots were never tainted.

   In every other case (`NOT_RECORDED`; `CONFLICT_DATE` with `Y > X`; `CONFLICT_RATIO`;
   `OVERLAPPING_SPLIT_WINDOWS`; a coverage gap) the carried taint is **open-ended**.
   - A later `SPLIT` in the **source** account does not reach units that already left it.
   - A `SPLIT` dated `X` in the **receiving** account scales nothing those units carry, because
     they were not there at the start of `X` (Ruling 3.2 of `ledger-replay`).
4. **What is suppressed.**
   - A receiving position is `INSUFFICIENT_DATA` + **`SOURCE_CONFLICT`** on every day `D ≥ T` on
     which it holds **any** unit of a tainted carried lot. The lineage cause is
     `SPLIT_SUPPRESSION_CARRIED`, with the source position, `K` and the source's own cause.
   - "Holds" is decided by **lot identity** under the lot-relief method in force (`FIFO/1`:
     carried lots keep their acquisition dates, so they are relieved in that order).
   - **Until the FIFO lot fold (`ledger-replay/1.4`) exists, the conservative rule applies:**
     the receiving position stays suppressed until the end of the first day on which it ends at
     0 units. A conservative rule suppresses at least as much as the lot-identity rule.
   - **(1.10 clarification, confirmed for the engineer.)**
     - A receiver that sells **part** of the carried units stays suppressed under the
       conservative rule until its first zero day. That is the intended cost: without lot
       identity, no rule can say whether the remaining units are the tainted ones.
     - Once `FIFO/1` lot identity exists, FIFO relieves the carried lots (earliest acquisition
       dates) first, and the suppression ends on the day the last tainted unit is relieved.
5. **Scope.** The suppression is on the **position's valuation**, so it applies identically at
   every scope:
   - the receiving account's own metrics;
   - every portfolio total that includes the position (Ruling 1.4 of `performance`).
6. **Flows.** An internal or external in-kind flow is valued `q × P(ℓ, d) × X` (Ruling 4.3 of
   `performance`). It is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` when its units are suppressed on
   `d`: units from a position suppressed on `d`, or units of a tainted lot. This is the remedy for
   review CP3-1. An internal transfer is a flow only at account scope; at portfolio scope it is
   neutral and is not valued.
7. **F8-B is unchanged.**
   - The system appends only to accounts that held units at the start of `X` (Ruling 6.4 item
     3), never to a receiver. A `SPLIT` dated `X` in a receiver that held nothing at `X` would
     scale nothing.
   - The remedy for carried units is the source's split, which clears the taint at the new `L`
     (rule 3 (c)).
   - The transfer's recorded quantity is then read in post-split units. Whether that is what the
     user meant is a question of the user's own record. It is flagged in lineage as
     `TRANSFER_AFTER_UNRECORDED_SPLIT` for review, with no state effect.

**Example 6-C (CP3-2's probe).**

- **Set-up.** A1 holds 50 U, bought before `X` for 7,500 USD. Cash is 2,500. The corroborated split
  (4:1, `X` = 2025-02-03) is missing from the ledger. Raw closes are 150.00, then 37.50.
- **2025-02-05:** an internal transfer moves the 50 units to A2.
- **Results:**
  - A1 is suppressed from 02-03 (`NOT_RECORDED`). The 50 units carried on 02-05 are tainted.
  - A2 holds them from 02-05, so A2's position is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`
    (`SPLIT_SUPPRESSION_CARRIED`), open-ended.
  - **Portfolio total on 02-06: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`**, not 4,375.
  - At a later `L′` where the split dated 02-03 is in A1's ledger:
    - A1 holds 200 from 02-03, and the transfer moves 50 of them;
    - A1 = 150, A2 = 50, at 37.50;
    - the total on 02-06 is 2,500 + 7,500 = **10,000**, with no taint;
    - lineage notes `TRANSFER_AFTER_UNRECORDED_SPLIT`, because the user's "50" was recorded
      before the split was.

### RULING 6.4d (1.11; review CP3-15): The confirmation policy must classify every split record it could corroborate with, per (listing, ex-date)

**Problem.** Detection (Ruling 6.4 item 2) acts only on a **corroborated** split. Corroboration
(Ruling 4.5) needs a feed record and an issuer-filing record that agree, with **equal** ex-dates.
Which source is a feed and which is a filing is configuration: the **confirmation policy**, two
sets of source ids called the **feed role** and the **filing role**. Records from a source the
policy names in neither role are not read.

A policy that leaves out the source of one side of a split can never corroborate that split. If
the ledger also lacks the split, detection finds nothing, and the position is valued in mixed
units with no flag. That is a silent breach of Ruling 6.4's purpose and of P5. The check must
therefore run at the unit corroboration works on: one listing and one ex-date.

- A check over all listings together (CP3-11) is defeated by a record of another listing.
- A check per listing (the CP3-15 first fix) is defeated by an old record of the **same** listing
  on another date. In review §32.1 item 2, a 2023 filing record of ℓ satisfied the filing role,
  while the 2025 split's filer was named in no role.

**Rule.**

1. **A valid policy.** Each role names **at least one** source, and no source is in both roles.
   - A policy with an empty role, or with a source in both roles, is invalid. It is refused when
     it is configured, before any computation and whatever `M` holds.
   - With an empty role, Ruling 4.5 could never corroborate anything, so F8 detection would be
     switched off. An invalid policy therefore never reaches detection, and never yields a
     number.
2. **The keys.**
   - **ℓ ranges over** the listings named by any event of the ledger at the computation's version
     `L`, live or reversed.
   - **`X` ranges over** the ex-dates (Ruling 7.1, `SPLIT` row) of the `SPLIT` observations of ℓ
     in the market-data version `M`. In Current mode, that is `M_t` (`performance` Ruling 1.7
     (1.2)).
   - **Every key (ℓ, X)** with at least one such record is tested. That includes ex-dates before
     any holding and after the as-of date. The test is on the policy, not on a valuation date,
     and it is decided from the whole of `M`, as Ruling 6.4a item 5 is.
   - **What counts as a record for (ℓ, X):** a `SPLIT` observation of ℓ whose ex-date **equals**
     `X`, real or synthetic.
     - No window applies. The ±20-session window of Ruling 6.4a links a **ledger** split to a
       corroborated split. It plays no part in corroboration, which Ruling 4.5 makes exact on the
       ex-date.
     - A record on any other date, however close, belongs to its own key.
     - The 2023 record of the review's probe is the key (ℓ, 2023-06-01) only. It says nothing
       about (ℓ, 2025-02-03).
   - Human resolution records (Ruling 6.4a item 5) are not observations, and are not part of this
     test.
3. **The test.** For each key, let:
   - `S(ℓ, X)` = the sources with at least one record for (ℓ, X);
   - `U(ℓ, X)` = the sources in `S(ℓ, X)` that are named in **neither** role (the
     *unclassified* sources).

   **The key is UNMATCHED if and only if `U(ℓ, X)` is not empty.**
4. **The cases, stated explicitly.**

   | Records at (ℓ, X) | Unmatched? | Why |
   |---|---|---|
   | (a) a role has no source at the key, and an unclassified source has a record (CP3-15) | **yes**, refused | The unclassified record may be exactly the missing side. Corroboration is made impossible by configuration, not by the evidence. |
   | (b) only unclassified sources have records; no source of either role does | **yes**, refused | The same, for both roles. This includes a lone unclassified source. The test does not guess which role it would take. |
   | (c) both roles have a source at the key, **and** an unclassified source has one too | **yes**, refused | The unclassified record could be in the same role with another ratio, and Ruling 4.5 would then make the split `DISAGREEMENT`, which is never appended (PD-0030 §2). Ignoring it can hide a dispute and let F8-B append a split the full evidence disputes. |
   | (d) no record at all for ℓ | no key | Nothing exists to detect, so silence is correct. |
   | (e) every source at the key is classified, and one role has none (`FEED_ONLY` or `FILING_ONLY`) | **no** | This is `SINGLE_SOURCE` under Ruling 4.5, so no suppression and no append (Ruling 6.4 items 3–4). No policy could corroborate it from what `M` holds, so silence is correct. |
   | (f) a role names a source that has no record anywhere in `M` (a typo, an unused source) | not by itself | It matters only if some key has an unclassified source, and then (a)–(c) apply. Otherwise nothing in `M` is lost. |

   **Why classification can be required of every source.** Ruling 4.5 defines corroboration by
   two kinds of record: a feed record and an issuer filing. Every corporate-action source is one
   or the other, so an unclassified source is always a missing or misspelt registration, never a
   third kind.
   - A source deliberately not trusted for corporate actions is kept out of `M`. `M` is an
     explicit file set (Ruling 0.1).
   - It is not left out of the policy. Leaving it out of the policy hides it, while excluding it
     from `M` is recorded.
5. **The effect.** If **any** key is unmatched:
   - the **whole computation is refused**, and no number is shown for any metric it was asked
     for. Under F8-B, the append run is refused too, and nothing is appended;
   - **state `INSUFFICIENT_DATA`, reason code null** (no reason code). The lineage cause is
     **`DETECTION_POLICY_UNMATCHED`**;
   - this follows the coverage-gap precedent (§5, "Coverage gaps"). A policy that does not
     classify the evidence is a configuration defect this project controls, not a property of the
     market data. It is shown so that it gets fixed, not explained to a user as a data condition;
   - **not `SOURCE_CONFLICT`.** No conflict between sources has been established, and a
     corroboration has not even been attempted;
   - **not `UNRESOLVED_CONVENTION`.** The convention is resolved (this ruling); the configuration
     does not meet it;
   - no new code (PD-0036 §2; §11 "Must not decide").
6. **What the refusal names.** It names **every** unmatched key, not only the first, in the order
   (listing id as text, then `X`). For each key:
   - `listing`: the listing id;
   - `ex_date`: `X`;
   - `unclassified_sources`: `U(ℓ, X)`, sorted;
   - `unmatched_roles`: the roles with no source in `S(ℓ, X)`, from `feed` and `filing`, in that
     order. This list is **empty** in case (c), where both roles are matched and the unclassified
     source is the whole problem.

   The manifest also cites the policy: its digest and both roles' source ids.
7. **Order with other refusals.** Where a user-portfolio entry refuses a market-data version
   holding synthetic files (`SYNTHETIC_MARKET_DATA_REFUSED`), that refusal comes first, as it is
   built. Then this test runs. Detection runs only if no key is unmatched.
8. **When nothing is unmatched**, detection proceeds exactly as in Rulings 6.4–6.4c. It reads the
   classified records only, and every key's records are then all classified.

**Example 6-D (review §31 and §32.1 probes; hand-derived).**

`M` holds three `SPLIT` records of the ledger's listings:

- ℓ₁ (4:1), ex-date 2025-02-03, from `test.feed` and from `test.filing`, agreeing;
- ℓ₁ (3:2), ex-date 2023-06-01, from `other.filing`, before any holding;
- ℓ₂, one old record from `other.filing` on its own ex-date `d₂`.

The ledger holds ℓ₁ across 2025-02-03 with no split, and ℓ₂.

The keys are (ℓ₁, 2025-02-03) with `S` = {`test.feed`, `test.filing`}, (ℓ₁, 2023-06-01) with
`S` = {`other.filing`}, and (ℓ₂, `d₂`) with `S` = {`other.filing`}.

| Policy (feed; filing) | Unmatched keys: `unclassified_sources` / `unmatched_roles` | Outcome |
|---|---|---|
| Q1 {`test.feed`}; {`test.filing`, `other.filing`} | none | Detection runs. (ℓ₁, 2025-02-03) is `CORROBORATED` and `NOT_RECORDED`, so ℓ₁ is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from 2025-02-03. The other two keys are `FILING_ONLY` (case (e)). |
| Q2 {`test.feed`}; {`other.filing`} | (ℓ₁, 2025-02-03): [`test.filing`] / [`filing`] | **refused**. A per-listing check passes here, because `other.filing` holds a record of ℓ₁ on 2023-06-01: the §32.1 defeat. |
| Q3 {`test.feed`}; {`test.filling`, `other.filing`} | (ℓ₁, 2025-02-03): [`test.filing`] / [`filing`] | **refused**. The typo `test.filling` matters only through the unclassified `test.filing` (case (f)). |
| Q4 {`test.feed`}; {`typo.filing`} | (ℓ₁, 2023-06-01): [`other.filing`] / [`feed`, `filing`]; (ℓ₁, 2025-02-03): [`test.filing`] / [`filing`]; (ℓ₂, `d₂`): [`other.filing`] / [`feed`, `filing`] (ℓ₁ before ℓ₂ if its id sorts first) | **refused**, naming all three keys |
| Q1, with `M` also holding a (2:1) record of ℓ₁ dated 2025-02-03 from `third.feed` | (ℓ₁, 2025-02-03): [`third.feed`] / [] | **refused**, case (c). If `third.feed` were classified as a feed, the feed role would hold (4:1) and (2:1), so `DISAGREEMENT`. Ignoring it would report `CORROBORATED`. |
| Q1, with `M` lacking the `test.filing` record | none | Not refused. (ℓ₁, 2025-02-03) is `FEED_ONLY`, so `SINGLE_SOURCE`, with no suppression (case (e)). That is Ruling 4.5's known limit of a single source, not a policy defect. |

**Rejected:**

- **A check over all listings together, or per listing:** both are defeated as shown above.
- **Refusing only when a role is unmatched**, the narrower form that leaves out case (c). It
  lets an unclassified record silently decide between `CORROBORATED` and `DISAGREEMENT`.
- **Using the ±20-session window to decide which records count for a key:** corroboration is
  exact on the ex-date, and a widened key would let a record on another date satisfy a role, which
  is the §32.1 defeat in a smaller form.
- **Suppressing only ℓ instead of refusing:** the defect is in the policy, which governs every
  listing. Every total that holds ℓ would be `INSUFFICIENT_DATA` anyway, and a partial answer would
  invite reading the remaining numbers as checked.

#### Example 6-A (hypothetical; the listing and dates of Example 2-A)

A1 holds 50 U. The corroborated `SPLIT (4, 1)` has ex-date 2025-02-03. Raw closes are 150.00
(2025-01-31) and 38.00 (2025-02-03).

| Ledger | Application rule | Quantity on 2025-02-03 | Value on 2025-02-03 | Correct? |
|---|---|---|---|---|
| no `SPLIT` | F8-A detection | 50 | `INSUFFICIENT_DATA` (would be 50 × 38 = 1,900) | value suppressed, as it should be |
| `SPLIT (4, 1)` dated 2025-02-03 | either | 50 × 4 = 200 | 200 × 38.00 = **7,600.00** | yes |
| `SPLIT (4, 1)` dated 2025-02-03, plus the feed applied as well (F8-C/D failure) | rejected | 50 × 4 × 4 = 800 | 30,400.00 | **no**, ×4 |
| `SPLIT (4, 1)` dated 2025-01-29 (record date) | either | 200 from 2025-01-29 | `INSUFFICIENT_DATA` on 2025-01-29, -30 and -31 (it would be 200 × 150 = 30,000 on 01-31); 7,600.00 from 2025-02-03 | suppressed where wrong |
| none, then F8-B appends `SPLIT (4, 1)` dated 2025-02-03 at new `L′` | F8-B | 200 at `L′` (50 at the old `L`) | 7,600.00 at `L′` | yes, and `L` is reproducible |

### RULING 6.5 (1.15): A valuation on the date a position opens (the HG4 US single-date check)

**Scope.**

- The as-of date is `D`.
- Every security position that is valued has its **first** ledger event dated `D`
  (`OPENING_POSITION`, an external `TRANSFER_IN`, or a purchase), so it holds 0 units at the start of
  `D`.
- The computation reads values **at `D` only**: market value and NAV at `D`.

This is the HG4 check of `CP7_E9_REAL_SOURCE_AND_UAT_PACKET.md`: one account, `OPENING_POSITION` of
10 units of one US listing and `OPENING_CASH` USD 500, both dated 2026-09-30, valued on 2026-09-30 in
USD.

1. **No split, recorded or not, can change the units of this valuation.**
   - **The quantity.** `ledger-replay/1.5` Ruling 3.2 applies a `SPLIT` at the start of its ex-date.
     It applies a split dated on an opening date before the opening quantity is added, and the
     snapshot is already post-split. Ruling 3.4 (last paragraph) says a split scales nothing in a
     position holding 0 units at the start of its date. The replayed quantity `S(D, L)` is
     therefore the recorded 10, whatever the split history.
   - **Detection.** Ruling 6.4 item 2 concerns accounts with non-zero units **at the start of `X`**.
     - For every `X ≤ D` the position holds 0 then.
     - For `X > D`, detection affects only valuation dates `≥ X > D`.

     So for every possible split, the set detected for the valuation at `D` is empty. Ruling 6.4c
     needs a transfer out of a suppressed position, and there is none.
   - **The price.** What remains is the unit basis of the price at `D`. That is Ruling 3.2 items
     3–4, a question about the price file's label, not about the ledger.
2. **So no corporate-action file is required in `M`.** An `M` with no split record is acceptable for
   this valuation. This does **not** treat absence as evidence: the result is the same under every
   split history, so nothing is inferred from the missing records.
   - **(1.16, review F-5) "The same under every split history" holds for the units.** The replayed
     quantity is 10 whatever splits occurred (item 1).
   - **The price basis does not get that guarantee.** `P(ℓ, D)` is right only if the file's `RAW`
     label is right for every split with ex-date in `E(D, R)` (Ruling 3.2 item 3), and that label is
     declared, not verified (item 6).
   - A split-adjusted series wrongly labelled `RAW` would be wrong at `D` by the split's factor, and
     with no filing record in `M` the exposure rule (Ruling 3.2 item 4) has nothing to act on.
   - That residual is disclosed (item 6, claims C-1, N-1 and N-3), not removed. Item 10 recommends a
     cheap human look that narrows it.

   It is consistent with each of these:
   - **Ruling 6.4 item 4** (absence from a weak free feed is not evidence of absence). No absence is
     used.
   - **Ruling 6.4d case (d)** (no key, so silence is correct). Case (d) says only that the policy
     test has nothing to check. It does not say that no split occurred, and this ruling does not
     read it so.
   - **The E9 rule** (an empty response, or no key, is never proof of complete history). No claim
     of complete history is made, and none is needed.
3. **If `M` does include a corporate-action file, Ruling 6.4d applies in full.** Every source with a
   `SPLIT` record in `M` must be named in a role, or the whole computation is refused
   (`INSUFFICIENT_DATA`, no reason code, `DETECTION_POLICY_UNMATCHED`). That holds even though no
   outcome could change the value. The policy itself must be valid when configured (6.4d item 1),
   whatever `M` holds. Records that are `UNMAPPED_ACTION` (Ruling 7.4) are not `SPLIT` records and
   create no key.
4. **Linking windows of splits before any holding (clarification, no change).**
   - What 6.4a items 1, 2 and 5 say:
     - the ±20-session window;
     - the overlap test;
     - their coverage-gap outcome, `CALENDAR_COVERAGE_GAP`.

     Each has consequences only for an account with non-zero units at the start of the ex-date.
   - Take a corroborated split of ℓ dated before any holding, for example a 2020 split when the
     ledger starts in 2026. It evaluates no window, and the calendar need not cover its year (the
     drafts cover 2025–2026).
   - The valuation at `D` is unaffected. An engine that refuses or suppresses here is wrong
     (Example 6-E, row (iv)).
5. **State.** The holding value `10 × P(ℓ, D)` and the NAV `10 × P(ℓ, D) + 500` are **`AVAILABLE`**
   iff all of these hold:
   - `P(ℓ, D)` is an admissible print **on `D`**:
     - volume > 0 (Ruling 2.1);
     - a recovered close (Ruling 2.4);
     - from an admitted source;
     - from a series not `CONTRADICTED`.
   - The calendar governing XNAS covers `D` (Ruling 5.3), so the count is 0 and the price is
     `CURRENT` (Ruling 5.2). E9's smoke target requires the print on `D` itself, `missed_count = 0`.
     A print one session earlier would be `AVAILABLE` + `STALE_DATA` under Ruling 5.2. E9 chose the
     narrower target as a test choice, and that changes no method.
   - No Ruling 3.2 item 4 exposure.
   - **(1.16, review F-4)** If `M` holds a V1 event of ℓ dated after `D`, the calendar can place it
     inside or outside `E(D, R)` (Ruling 3.2 item 3). That holds when its ex-date is not after `T`, or
     when `N(R)` is determined. Only an event after `T` with `N(R)` undetermined gives the coverage gap
     (1.16 fix round, reviews C-2 and L-1). With no corporate-action file in `M` (OP-2 (a), decided),
     there is no such event, so this condition is met trivially.
     - The lineage still lists `E`.
     - For the HG4 file (`R` = 2026-10-01T04:53:50Z, 00:53:50 on 10-01 in New York), `N(R)` =
       2026-10-02, and `E(2026-09-30, R)` = {2026-10-01, 2026-10-02}.
     - Both dates are sessions of the registered NYSE calendar, whose coverage runs to 2026-12-31. So
       `N(R)` is determined, and any V1 event added to `M` could be placed (Example 3-G (d)).
   - No policy refusal (item 3).
   - ℓ resolves uniquely (Ruling 7.3).
   - The cash is in the reporting currency, so no FX is involved.

   **Yes: a holding value may be `AVAILABLE` while the series' split label is `UNVERIFIABLE`.**
   - Ruling 3.1's consequences admit such a series, and Ruling 4.7 item 4 foresaw this for every US
     price.
   - No row of the Ruling 4.4 state table is triggered.
   - The label status is carried in lineage (Ruling 3.2 item 5), and the claims below are limited
     accordingly.
   - "Split **history**" is not a status this method assigns at all. The method never asserts it,
     either way.
6. **What the result may claim, and what it may not.**

   (1.15's table, kept as issued.)

   | May claim | May not claim |
   |---|---|
   | The market value of the holding on 2026-09-30 is `10 × p`. Here `p` is the close Alpha Vantage `TIME_SERIES_DAILY` delivered for the 2026-09-30 XNAS session. `p` is read as as-traded (`RAW`) on the strength of the call's documentation, with label source `MEMORY` until the human confirms that documentation (§9B item 4 (d); OP-5). | That the series is **verified** as-traded. Its split label is `UNVERIFIABLE` and its dividend component is `UNVERIFIABLE` (A.3). |
   | The NAV in USD on 2026-09-30 is `10 × p + 500.00`. | That `p` is Nasdaq's official closing-cross price as checked. It is single-source and unchecked, unless a Test V4 record exists. |
   | The state is `AVAILABLE`, freshness `CURRENT`, delay `END_OF_DAY`. | That the close was compared with any other source. There is none for US (Ruling 4.7 item 4). |
   | Reconciliation status is `SINGLE_SOURCE`. | That the listing had no split, or that its split history is complete or verified, in any period. |
   | The inputs are named: the files of `M` with their hashes, `L`, and this convention ID. | That an empty `SPLITS` response, if one exists, shows anything beyond "zero records at `R`" (Ruling 7.5). |
   | The lineage states the exposure window `E(2026-09-30, R)` and "no V1 event in `M`". | That the quantity 10 is verified. It is the user's ledger fact (Ruling 6.4 item 4: the ledger is canonical). |
   | | Anything about another date, a return, or any performance or risk figure. |

   **(1.16) The claim limits, as one numbered list.** This list governs; the table above is the 1.15
   record. Each item is a separate limit, so a shortened list (an R5 output, an R7 screen, an AI
   explanation) can be checked item by item (P3: plainer wording may drop precision, never a caveat
   that changes the conclusion). PD-0066 decision 2 and the F1 final check (finding F-2) asked for the
   dividend component as its own item.

   **May claim:**
   - **C-1.** The market value of the holding on 2026-09-30 is `10 × p`.
     - Here `p` is the close Alpha Vantage `TIME_SERIES_DAILY` delivered for the 2026-09-30 XNAS
       session.
     - `p` is read as as-traded (`RAW`) on the strength of the vendor's documentation of that call, as
       the owner read it on 2026-10-24. The label source is `DECLARED` (PD-0066 decision 3; §9B item
       4 (d)).
     - **That is the vendor's declaration, not a verification.** No V1 event and no V4 record exists
       for this file.
   - **C-2.** The NAV in USD on 2026-09-30 is `10 × p + 500.00`.
   - **C-3.** The state is `AVAILABLE`, freshness `CURRENT`, delay `END_OF_DAY`.
   - **C-4.** The reconciliation status is `SINGLE_SOURCE`.
   - **C-5.** The inputs are named: the files of `M` with their hashes, `L`, and the convention ID the
     manifest cites.
   - **C-6.** The lineage states the label status (`UNVERIFIABLE`), the label source (`DECLARED`), the
     exposure window `E(2026-09-30, R)` = {2026-10-01, 2026-10-02}, and "no V1 event in `M`".

   **May not claim:**
   - **N-1.** That the series' **split** label is verified. It is `UNVERIFIABLE`.
   - **N-2.** That **the dividend component is verified. It is `UNVERIFIABLE`** (A.3; MD-OI-17).
     - How a dividend-adjusted series would differ from raw at 2026-09-30 depends on its anchor
       (Ruling 2.3), which is not verified either (1.16 fix round, review L-2).
       - With anchor `LATEST` (qfq, the "adjusted close" convention), it differs through any cash
         dividend with ex-date in `E(2026-09-30, R)` that the vendor had applied by `R`, by about
         that dividend's yield.
       - With anchor `EARLIEST` (hfq), it differs through every event from the series' first event up
         to 2026-09-30, compounded (Ruling 3.2 item 3, "Anchor"; MD-OI-21).
     - `M` holds no corporate-action record either way (OP-2 (a)), so nothing is known about such a
       dividend, and nothing is claimed about it.
   - **N-3.** That the series is **verified** as-traded, or that the vendor's declaration has been
     checked against the exchange or a filing.
   - **N-4.** That `p` is Nasdaq's official closing-cross price as checked. It is single-source and
     unchecked, unless a Test V4 record exists.
   - **N-5.** That the close was compared with any other source. There is none for US (Ruling 4.7
     item 4).
   - **N-6.** That the listing had no split, or that its split history is complete or verified, in
     any period.
   - **N-7.** That an empty `SPLITS` response, if one exists, shows anything beyond "zero records at
     `R`" (Ruling 7.5).
   - **N-8.** That the quantity 10 is verified, or that it is the owner's holding. It is the ledger fact
     the project entered (Ruling 6.4 item 4: the ledger is canonical; item 9: `personal_holdings =
     false`).
   - **N-9.** Anything about another date, a return, or any performance or risk figure.

   **A stored result whose manifest cites `market-data/1.15` or earlier carries label source
   `MEMORY`.** That is what it recorded, and it is never re-labelled. Its C-1 and C-6 say `MEMORY`, not
   `DECLARED`. The owner's reading reaches a result only through a manifest citing 1.16 (P9, P12). The
   value `10 × p + 500.00` is the same under either.
   - **(1.16 fix round, review C-3)** This is a statement about stored records. It is not a
     reproduction requirement.
   - Code at 1.16 runs one method. Reproducing a 1.15 manifest with it is refused
     (`CONVENTION_MISMATCH`, `performance/engine.py` `reproduce`), and that is correct.
   - A 1.15 manifest reproduces with the code that ran it.
   - No multi-version profile set is specified, and none may be built so that an earlier manifest
     reproduces under later code (§11, "Must not decide").

7. **What this ruling does not extend to.** It does not cover:
   - a valuation at `D′ > D`;
   - a return over `[D, D′]`;
   - any position held across a session after it opens.

   There, Ruling 6.4 detection, the 6.4a windows and corporate-action evidence matter again, and so
   do the free-feed limits (Ruling 4.7 item 4; STATUS 16d). Each later scope is judged under the
   general rules. Nothing is carried over from this ruling.
8. **RECOMMENDATION (PM), for the HG4 UAT.** Keep any Alpha Vantage `SPLITS` file **out of the UAT's
   `M`**.
   - The file may be stored (Ruling 7.5) and used to observe the format (Ruling 7.4 O-1).
   - The value is the same either way. Leaving it out removes the policy-refusal path of item 3,
     and shortens what the reviewer must check.
   - The choice is the owner's (OP-2).
   - **(1.16) Decided: option (a)**, no corporate-action file (PD-0066 decision 2).
9. **(1.16) The origin of the HG4 account: `state_kind` stays `ACTUAL`, and the origin is a separate
   axis.** This confirms the encoding in `implementation/CP7_F1_REAL_PATH_DESIGN.md` §1.1, the one
   item PD-0066 decision 10 left to me:
   - `state_kind = ACTUAL`;
   - `ledger_origin = PROJECT_CONSTRUCTED_NONPERSONAL_UAT`;
   - `personal_holdings = false`;
   - `market_origin = REAL_SOURCE`.

   **Confirmed, on the conditions below.**
   - **Why `ACTUAL`.**
     - `state_kind` answers one question: is this the ledger's recorded state, or a hypothetical
       transformation of one? A scenario or a model is a transformation (P8; `CP6_INSIGHT_CONVENTIONS.md`
       §2, "ACTUAL versus model semantics"). The HG4 ledger has two recorded events, replayed as
       recorded. No scenario transforms them.
     - The rulings that compute the value do not depend on who entered the ledger: `ledger-replay`
       Rulings 3.2 and 3.4, and items 1–5 of this ruling. So `ACTUAL` is a true statement of the
       state's kind.
     - "Not the owner's holding" is a different fact, about **who** the ledger belongs to. It belongs
       on its own axis.
   - **Rejected: `HYPOTHETICAL`.** A hypothetical state is a change to some actual ledger. Labelling a
     constructed ledger so would invent an actual portfolio it derives from. It would also send the
     check down the scenario path, which the services refuse (`SCENARIO_UNSUPPORTED`). So the HG4
     check could not run, and P8's separation would carry a meaning it does not have.
   - **Rejected: a third `state_kind` value**, such as `CONSTRUCTED`. It would merge two axes, and
     every consumer of the actual/scenario axis would have to learn a value that says nothing about
     that axis.
   - **Rejected: the HG2 "hypothetical" label** (`pack.py`, "not a user's holdings"). That label was
     an origin label all along, as the design notes.
   - **Conditions.**
     1. **Mandatory and immutable.** The origin fields are written once on the root, and carried into
        every manifest and result that reads it (P9). `personal_holdings` is stated explicitly, `true`
        or `false`. If it is missing, the computation is refused; it is **never defaulted** either way.
     2. **Independent of `synthetic`.** `market_origin` describes the market data. It is
        `REAL_SOURCE` only if `M` holds no synthetic file (Ruling 4.8 item 2). The ledger carries no
        real/synthetic flag (Ruling 4.8 item 4(e)), and a constructed ledger does not make a result
        synthetic.
     3. **No crossing of baselines.** A constructed root's results never serve as a historical
        baseline or comparison for a personal root, and a personal root's never serve for a
        constructed one (P4, the portfolio's own history).
        - **This already holds today, through CP6's scope requirement, not through the semantic key**
          (1.16 fix round, reviews L-5 and C-10).
        - `CP6_INSIGHT_CONVENTIONS.md` §3 says history requires matching "scope". In `src/`, the
          semantic key (`insights/evidence.py` `semantic_fields`) holds no portfolio or account.
        - The separation comes from the separate check in `history_problem`. It refuses a baseline
          whose portfolio, account, state or scenario differs (`SCOPE_MISMATCH`). The two roots are
          different portfolios, so that check applies. No CP6 ruling changes.
        - Any later convention or component that looks up or compares history across roots, or by
          semantic key alone, must either keep that scope check, or carry the portfolio and account
          **and** `ledger_origin` and `personal_holdings` in its key.
     4. **The axes are orthogonal.** A scenario run on the constructed ledger later is
        `HYPOTHETICAL`, with the same origin fields.
     5. **Claims.** Claim N-8 of item 6 applies: the quantity is the project's ledger fact, never "your
        holding". How that is worded on screen is the designer's; that it may not be dropped is P3.
10. **(1.16) RECOMMENDATION (PM/owner), review F-5: a human look at EDGAR over `E` before the run.**
    `E(2026-09-30, R)` for the HG4 file is two sessions, 2026-10-01 and 2026-10-02.
    - **The look.** Before the run, the owner checks AAPL's filings on SEC EDGAR for a stock split with
      ex-date on either day, for example an 8-K that announces one.
    - **A hit stops the run, whatever SEC EDGAR's registration state** (1.16 fix round, reviews L-3
      and C-8). The run does not go ahead, and the decision goes back to the owner:
      - **It reopens OP-2 (a).** A hit changes the `M` the owner decided under OP-2 (a) (PD-0066
        decision 2).
      - **While SEC EDGAR is unregistered** (PD-0067 decision 4: no entry until the owner's terms
        reading), the hit cannot become a filing record. `M` then holds no record, and the interim rule
        is vacuous. Going ahead would show an `AVAILABLE` NAV with "no V1 event in `M`" while a human
        knows of an exposure. That is the failure review F-5 describes, and P5 forbids it.
      - **Once SEC EDGAR is registered**, the hit can become a filing record (Ruling 7.6 item 2).
        - The interim rule of Ruling 3.2 item 6 then refuses the run **until V1 and item 4 are
          built**. V4 alone does not lift that refusal.
        - After that, item 4 withholds the close unless V1, or V4 under Ruling 3.3, establishes `RAW`
          for `X`.
    - **No hit** claims nothing. It is not a V1 event and not evidence of absence (Ruling 6.4 item 4),
      and it changes no state or label. The run's record may note that the look was made, by whom
      and when.
    - **Why it is worth it.** It is the cheap positive check that closes the case review F-5
      describes: a split announced in `E`, with a series that is in fact adjusted. The existing file's
      `E` is already as short as a file holding the 2026-09-30 row can have, give or take one session.
      A file retrieved on 09-30's own evening would have `E` = {10-01}.
    - The look is a procedure, not a method change, and whether it is required for HG4 is the owner's
      call. What a hit does is method: the stop above applies P5 to an exposure a human knows of.

#### Example 6-E (1.15): the single-date check under six market-data versions (hypothetical close)

- **Ledger.** Account A, with `OPENING_POSITION` 10 units of ℓ (the HG4 US listing) dated 2026-09-30
  and `OPENING_CASH` USD 500.00 dated 2026-09-30. `D` = 2026-09-30, reporting currency USD.
- **Price.** `M` holds one admitted `RAW` file with an admissible print on 2026-09-30 and retrieval
  `R`.
- **Calendar.** The calendar covers `D` and `E(D, R)`.
- **Policy.** Where one is configured: feed `{av.splits}`, filing `{sec.filing}`. These ids are
  illustrative; the engineer and PM name the real ones.
- **The close.** `p` is the UAT's unknown. For the arithmetic only, take a **hypothetical**
  `p` = 250.00, which is not a claim about any real close. Then:
  - value = 10 × 250.00 = **2,500.00**;
  - NAV = 2,500.00 + 500.00 = **3,000.00** USD.

  The UAT's expected value stays the formula `10 × p + 500`.

| `M` also holds | 6.4d keys | Detection at `D` | `P(ℓ, D)` | NAV | State |
|---|---|---|---|---|---|
| (i) no corporate-action file | none (case (d)) | nothing to detect | `p`, `CURRENT` | `10p + 500` (3,000.00) | `AVAILABLE` |
| (ii) an Alpha Vantage `SPLITS` file that is a recognised empty response (Ruling 7.5) | none | nothing | `p` | the same | `AVAILABLE`. Lineage adds `EMPTY_RESPONSE`, coverage `NOT_ESTABLISHED`. |
| (iii) an Alpha Vantage `SPLITS` file with one record dated 2020-08-31, field meaning **not granted** | none: the record is `UNMAPPED_ACTION`, not a `SPLIT` (Ruling 7.4) | nothing | `p` | the same | `AVAILABLE`. Lineage adds `UNMAPPED_ACTION_RECORD` (ℓ, "2020-08-31"), with no state effect. |
| (iv) a granted `av.splits` record and a `sec.filing` record, both `(4, 1)` on 2020-08-31 | (ℓ, 2020-08-31), `S` = {av.splits, sec.filing}, `U` = ∅ | `CORROBORATED`. Units at the start of 2020-08-31: none, since the ledger starts on 2026-09-30, so no account is detected, no window is evaluated and the 2020 calendar is not needed. | `p` | the same | `AVAILABLE` |
| (v) as (iv), but the policy names `{av.splits}` and `{sec.filng}` (a typo) | (ℓ, 2020-08-31) **unmatched**: `unclassified_sources` [sec.filing], `unmatched_roles` [filing] | not reached | — | none | **refused**: `INSUFFICIENT_DATA`, no reason code, `DETECTION_POLICY_UNMATCHED` (item 3) |
| (vi) as (i), plus a `sec.filing` record `(2, 1)` with `X` ∈ `E(D, R)` (hypothetical), and the file's `RAW` reading not established for `X` | (ℓ, `X`), filing only | at `D`: none (`X > D`) | **none**: the reading is exposed (Ruling 3.2 item 4) | none | `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, `SPLIT_LABEL_EXPOSED` |

In (vi), if the same file holds `X` and V1 finds the jump consistent with `RAW`, or a Test V4 record
before `X` agrees, the state returns to `AVAILABLE` with NAV `10p + 500`. Under F8-A the account
would be detected for dates `≥ X` only if the split were corroborated. Here it is filing-only, so it
is `SINGLE_SOURCE` and nothing is detected.

---

## 7. Corporate-action observations for V1

### RULING 7.1: Types CP2 normalizes (PRD §12.2)

| Type | Required fields | Field meaning |
|---|---|---|
| `SPLIT` (forward or reverse; also A-share 送股 and 转增) | `listing_id`, `ex_date`, ratio `(n, o)` | `ex_date` is the first session trading on the post-split basis, as in Ruling 1.2 of `ledger-replay/1.3`. **One** observation per listing per ex-date, carrying the **combined** ratio: "10送3转增2" is `(15, 10)`. |
| `CASH_DIVIDEND` | `listing_id`, `ex_date`, `pay_date`, `record_date` where available, `amount_per_unit` as `Money` in the **declared** currency | `amount_per_unit` is per unit held at the record date. When a share distribution has the same ex-date ("10送3派2元"), it is per **pre-distribution** share (0.20 here). If the issuer pays in a different currency from the declared one (common for H-shares and some HK issuers), the paid currency and the issuer's conversion rate are recorded as stated by the issuer. They are never derived from our FX (compare Ruling 5A.7 of `ledger-replay/1.3`). |
| `SYMBOL_CHANGE` | `listing_id`, `effective_date`, old ticker, new ticker | an identifier update, not a position event (Ruling 7.2) |

**(1.14) The paid fields of a `CASH_DIVIDEND`**, stated by the issuer when it pays in a currency
other than the declared one:

| Field | Meaning | Constraints |
|---|---|---|
| `paid_currency` | the currency the issuer pays in | ISO 4217; differs from the declared currency |
| `paid_amount` | the amount per unit (held at the record date) the issuer states it pays in `paid_currency` | a `Money` exact decimal as stated; positive; only with `paid_currency`; `CASH_DIVIDEND` only |
| `issuer_fx_rate` | the conversion rate the issuer states, declared → paid | an exact decimal as stated; only with `paid_currency` |

- **Which one governs.** `paid_amount` is the cash fact a holder receives per unit, so it governs.
  The issuer's rate is often rounded, and the stated amount need not equal `amount × rate`.
- **Only a rate is stated.** The paid amount is `amount_per_unit × issuer_fx_rate`, exact and not
  rounded. Lineage says it was derived from the issuer's rate.
- **Both are stated and differ** beyond `½ × 10^(−d)`, with `d` the decimals of the stated
  `paid_amount`: a review flag in lineage. There is no state effect; the stated amount governs.
- **Never derived from our FX** (as above), and **appears in canonical form only when stated**, so a
  dividend without paid fields keeps its digest.
- **Users:** the ledger's income check (as before) and the ETF proxy of `risk` Ruling 5.5 (1.8),
  item 2.

`effective_date` in the current seam type means **`ex_date`** for `SPLIT` and
`CASH_DIVIDEND`. A dividend also needs `pay_date`: ledger `DIVIDEND` events are dated on the
pay date (Ruling 4.1 of `ledger-replay/1.3`), so the CP3 check of recorded against expected
income joins on it.

**Feed dividends never create ledger cash.** Whether dividends should also be system-appended,
as in F8-B, is a separate owner question. It is not proposed here.

**Other types** (rights issues 配股, spin-offs, mergers, tender offers, scrip and special
distributions; PRD §12.3) are stored as observations with type **unsupported** and their dates.
They change no position and no price. A listing with an unsupported action dated in a window
is flagged for any CP3 return spanning that date. That treatment is CP3's to rule.

### RULING 7.2: A symbol change is an attribute update on the existing listing

1. **Never a new `listing_id`** (PD-0021 §1.1, §1.4). The `Listing`'s `ticker` changes. Its
   identity, its ledger references, its price series and its positions do not.
2. **Effective-dated.** The ticker is held as a history, `(ticker, valid_from, valid_to)`, so an
   observation under the old ticker dated before `effective_date` resolves to the same
   `listing_id`. Resolution keys on (identifier, MIC, observation date). It never keys on the
   ticker alone.
3. **Deterministic test that it is a symbol change.** The old and new tickers must resolve, via
   OpenFIGI, to the **same FIGI** on the same MIC.
   - **Different FIGIs** mean a different instrument or listing (a merger, a new share class, a
     venue transfer). That is **not** a symbol change and is never auto-merged. It goes to a
     human.
   - **If the old ticker no longer resolves** (common), the change needs a corroborating issuer
     filing or exchange notice. Otherwise it stays unconfirmed, and observations under the new
     ticker stay unresolved. They are **not guessed** (`InstrumentResolution.listing_id is None`).
4. **Price-history continuity.** A source that splits one listing's history across two tickers
   is concatenated under the one `listing_id`. Overlapping dates must reconcile under §4.2, as
   two vintages of one raw series.
5. **Not a symbol change:**
   - an A-share short-name change, such as an ST or *ST prefix (the code is unchanged; it is a
     name attribute);
   - a move to another venue (a new MIC; out of V1 scope, flagged to a human).

**Example 7-A (structure only).** A US listing changes ticker `OLD` → `NEW`, effective `E`.
Same listing, same FIGI.

- A price row from source B labelled `OLD`, dated `E − 1`, resolves to listing `ℓ`.
- A row labelled `NEW`, dated `E`, resolves to `ℓ`.
- A row labelled `NEW`, dated `E − 1`, does not resolve: `NEW` was not valid then. It is
  flagged, not guessed.
- The ledger references `ℓ` throughout and is unchanged.

### RULING 7.3 (1.5): FIGI levels, and which OpenFIGI records may attach to a listing

1. **Three FIGI levels, three attributes, never mixed.** An OpenFIGI record carries `figi`,
   `compositeFIGI` and `shareClassFIGI`.
   - **Exchange level:** the security on one venue. It is the only level that matches a V1
     `Listing` (an instrument on a MIC, PRD §10.1 "FIGI + MIC"). It fills `Listing.figi`.
   - **Composite level:** the security across all venues of one country. It fills a separate
     attribute, `composite_figi`.
   - **Share-class level:** global, across countries. It belongs to the `Instrument`, not the
     `Listing`.

   One field holding values of different levels would make equality joins silently wrong: an
   exchange-level FIGI from one source would never equal a composite FIGI stored by another.
2. **The level of a record is decided from the record itself, not from a code table.**
   - `figi = compositeFIGI` → **composite-level**.
   - `figi ≠ compositeFIGI` → **exchange-level**.
   - Observed:
     - AAPL `exchCode US` gives `figi = compositeFIGI = BBG000B9XRY4`, so it is composite;
     - 700 `exchCode HK` gives `figi BBG000BJ35N5 ≠ compositeFIGI BBG000BJ35F4`, so it is
       exchange-level.
3. **Exchange-level attachment.** An exchange-level record's `figi` attaches to listing `ℓ`'s
   `Listing.figi` iff **all** of these hold:
   - its `exchCode` is in the A.6 code set of `ℓ`'s MIC, with an entry whose status is
     `OBSERVED` or `CONFIRMED`. `MEMORY` and `TO_CONFIRM` entries do **not** attach (see item 6);
   - its `ticker` equals `ℓ`'s ticker valid on the assertion's date (Ruling 7.2 item 2);
   - its `securityType2` is consistent with the instrument's `SecurityType`: "Common Stock"
     with `COMMON_STOCK`, an ETP type with `ETF`.

   If any of these fails, nothing is attached, and the record is kept as unmatched evidence.
4. **The composite code "US": it may not resolve to a specific MIC listing by itself.**
   - A composite record says "this security, in the US". It does not say which venue. Writing
     it into `Listing.figi` would assert a venue the record does not contain.
   - It **may fill `composite_figi`** on exactly one listing. That requires all of:
     - the record is composite-level (item 2);
     - its composite code's country (A.6 `composite_codes`) is the country of `ℓ`'s MIC;
     - its ticker equals `ℓ`'s ticker valid on the assertion date;
     - **exactly one** active V1 listing in that country carries that ticker on that date.
       Zero or several matches attach nothing.
   - A later observation that carries only a composite FIGI resolves to `ℓ` through
     `composite_figi` under that same uniqueness test, evaluated at the observation's date.
     Otherwise it does not resolve.
   - **(1.6) This path may wait.** No admitted source produces composite-only observations:
     Alpha Vantage observations carry a ticker, and OpenFIGI files are identity assertions, not
     observations. So CP2 can close without it, on two conditions:
     - until it is built, a composite-only observation is **unresolved**
       (`InstrumentResolution.listing_id = None`), never resolved some other way, and a test
       pins that;
     - it must be built before any source whose observations carry only a composite FIGI is
       admitted. It is an admission precondition, recorded in that source's A.3 profile.
   - **Why this is not a venue guess.** A US equity has one primary listing, and V1 values it
     at that listing's official close (Ruling 2.1). The uniqueness test makes the
     composite-to-listing link a fact about our own listing table, not about the record.
5. **Symbol-change test (refines Ruling 7.2 item 3).**
   - "Same FIGI on the same MIC" means **exchange-level** FIGIs.
   - Equal composite FIGIs alone are **not** sufficient. A move to another US venue keeps the
     composite and changes the exchange-level FIGI, and Ruling 7.2 item 5 excludes venue moves.
   - With composite equality only, the change is unconfirmed and goes to a human.
6. **Status of A.6 entries.**
   - `OBSERVED`: seen in an admitted file with the record's level established by item 2.
   - `CONFIRMED`: a human has checked it against OpenFIGI's published exchange-code list and
     recorded the reference.
   - `MEMORY`: stated by me from recollection.
   - `TO_CONFIRM`: a guess that needs a lookup.

   Only `OBSERVED` and `CONFIRMED` entries attach FIGIs. That keeps the C2-4 fix (no FIGI
   attached on an unproven code) and turns resolution back on wherever evidence exists. Today
   that means:
   - **exchange level:** XHKG via `HK` (observed, 700);
   - **composite level:** the US via `US` (observed, AAPL).

   **No US exchange-level code is observed yet.** So no US `Listing.figi` attaches until one is.
   US listings resolve through `composite_figi` (item 4).

   **(1.16) Today that means:**
   - **exchange level:**
     - XHKG via `HK` (observed, 700);
     - **XNAS via `UW`**, segment XNGS (observed, AAPL: `AAPL_XNGS.json` and `AAPL_UW.json`,
       2026-10-23, payload SHA-256 `b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc`;
       PD-0066 decision 4; A.6). **(1.16 fix round 2)** Where the two files are kept since the
       owner-approved move of 2026-10-24 (item 9): `AAPL_UW.json` and its manifest in the indexed store,
       `data/marketdata/files/openfigi/identity/2026-10-23/`; `AAPL_XNGS.json` and its manifest,
       unchanged, in `data/marketdata/observations/openfigi/identity/2026-10-23/`, outside the indexed
       root. I re-hashed all four files on 2026-10-24 after the move: payload `b2aaeb7b…889c3ccc` in both
       places, manifests `7952829b…a738` (`UW`) and `cb4d862d…63c8d` (`XNGS`), as before the move;
   - **composite level:** the US via `US` (observed, AAPL).

   **The other US exchange-level codes stay `MEMORY`:**
   - `UQ` and `UR` (XNAS);
   - `UN` (XNYS);
   - `UP` (ARCX), `UF` (BATS) and `UA` (XASE).

   A US listing whose record carries one of them gets no `Listing.figi`, and resolves through
   `composite_figi` (item 4) as before.
7. **What an attached exchange-level record carries with it.** When an exchange-level record
   attaches under item 3, its `compositeFIGI` also fills `ℓ`'s `composite_figi`, and its
   `shareClassFIGI` fills the instrument's share-class attribute. No composite-code lookup is
   needed, because the record links the levels itself. For 700 on XHKG: `figi BBG000BJ35N5`,
   `composite_figi BBG000BJ35F4` and share class `BBG001S8C4T6`, all observed.
8. **Observed negative.** `idType TICKER, idValue AAPL, micCode XNAS` returned "No identifier
   found". OpenFIGI's `micCode` filter did not accept the Nasdaq operating MIC for AAPL.
   - My **MEMORY** reading is that it expects the segment MIC, here XNGS (Nasdaq Global
     Select).
   - **RECOMMENDATION:** the human downloads AAPL with `micCode XNGS` and with `exchCode UW`.
     That observes the US exchange-level entry for XNAS and confirms or refutes the segment
     reading in one step.
   - **(1.16) Done, and the segment reading holds for AAPL.** The owner ran both requests on
     2026-10-23 at 19:08 UTC (PD-0066 decision 4; `retrieved_by: human`; the owner confirmed the
     digests, decision 9).
     - **`micCode XNGS`** (`AAPL_XNGS.json`, manifest SHA-256 `cb4d862d…63c8d`) and **`exchCode UW`**
       (`AAPL_UW.json`, manifest SHA-256 `7952829b…a738`) returned **byte-identical** payloads.
     - The payload is 264 bytes, SHA-256 `b2aaeb7b…889c3ccc`. It holds one record: `figi`
       `BBG000B9Y5X2`, `ticker` `AAPL`, `exchCode` `UW`, `compositeFIGI` `BBG000B9XRY4`,
       `shareClassFIGI` `BBG001S5N8V8`, `securityType2` "Common Stock", `marketSector` "Equity".
       I re-hashed both files and read the record. **(1.16 fix round 2)** The evidence is unchanged by
       the move of 2026-10-24: `AAPL_XNGS.json` and its manifest now lie in
       `data/marketdata/observations/openfigi/identity/2026-10-23/`, `AAPL_UW.json` and its manifest
       stay in `data/marketdata/files/openfigi/identity/2026-10-23/`, and all four hashes are the ones
       above (re-hashed after the move).
     - `figi ≠ compositeFIGI`, so the record is **exchange-level** (item 2).
     - With the 2026-10-01 negative for `micCode XNAS`, this shows that OpenFIGI's `micCode` filter
       takes the **segment** MIC, at least for AAPL. A query for an XNAS listing uses `exchCode` or
       the segment MIC, never the operating MIC.
     - **What is MEMORY here.** That XNGS is a segment of the operating MIC XNAS is ISO 10383 as I
       recall it (§12 item 23). The A.6 entry rests on it, as every segment row of A.6 has since 1.5.
       The consequence if it were wrong is confined to the identity attribute `Listing.figi`
       (item 9).
9. **(1.16) What can now attach to AAPL's XNAS listing.** With A.6 `UW` `OBSERVED`, the record above
   attaches to the XNAS listing ℓ of AAPL **iff all of these hold** (1.16 fix round 2, review L-1):
   - item 3's three conditions. The first (the record's `exchCode` `UW` is in ℓ's A.6 code set with
     status `OBSERVED` or `CONFIRMED`) holds by the A.6 entry. The other two are conditions on the
     hand-entered identity record of ℓ:
     - it carries ticker `AAPL` valid on the assertion's date (the retrieval, 2026-10-23; Ruling 7.2
       item 2);
     - it has `SecurityType` `COMMON_STOCK`, consistent with "Common Stock";
   - item 10's two level-consistency checks: the record's `compositeFIGI` equals any `composite_figi`
     already on ℓ, and its `shareClassFIGI` equals any share-class FIGI already on the instrument.

   If any one fails, nothing attaches (item 10 says what "nothing" means). On the files, the A.6
   condition holds, and the record's composite and share-class values equal those of `AAPL_US.json`.
   The other four conditions are judged against what ℓ and its instrument carry: the two
   identity-record conditions hold only if the hand-entered record says so, and the item 10 checks hold
   only if any `composite_figi` or share-class FIGI already stored equals the record's (a mistyped
   stored value attaches nothing).

   Then, by item 7:
   - **`Listing.figi` = `BBG000B9Y5X2`** (exchange level);
   - **`Listing.composite_figi` = `BBG000B9XRY4`**. It equals the composite record of `AAPL_US.json`
     (2026-10-01, `figi = compositeFIGI = BBG000B9XRY4`), so the two observations agree;
   - **the instrument's share-class FIGI = `BBG001S5N8V8`**, also equal in both files.

   **Nothing else attaches:** no other listing, and no other US venue code.

   **The two manifests of one payload.**
   - **One payload, one manifest** (1.16 fix round, review C-4). A release binds each payload hash to
     exactly one manifest. Nothing may choose between two manifests of one payload silently.
   - **`src/` goes further, and fails closed.**
     - `FileStore.index()` (`marketdata/files.py`) refuses a data root in which two manifests claim one
       payload ("two manifests claim file …").
     - Every real build calls it: `ingest.py` `build_in_memory_market_data`, and
       `performance_tools/real_slice.py`.
     - PostgreSQL `md_file` refuses a second, different manifest for a registered payload
       (`FileRegistrationConflictError`).
   - **What happened, as a record (1.16 fix round 1).** `AAPL_UW.json` and `AAPL_XNGS.json` both lay
     under `data/marketdata/files/`, so every real build over that root was refused before it read a
     file, the HG4 price file `AAPL_compact.csv` included. I confirmed it on 2026-10-24 by calling
     `FileStore.index()` read-only on the data root, with the working-tree `files.py`, which matches
     `HEAD`: it raised "two manifests claim file b2aaeb7b…889c3ccc". No wrong number could result. The
     draft of 1.16 said one manifest "enters a release", which the file layer never reaches.
   - **The remedy was the owner's or the PM's, not mine or the engineer's.** There were two routes:
     - one manifest and its payload are moved out of the indexed root, as a data action the owner
       approves, and kept as an acquisition record (PD-0066 decision 9 prefers that `AAPL_UW.json`
       stays);
     - or the PM schedules a design change in which a release names its manifest by hash.
   - **(1.16 fix round 2) The first route was taken.** On 2026-10-24, with the owner's approval,
     `AAPL_XNGS.json` and its manifest were moved, unchanged, to
     `data/marketdata/observations/openfigi/identity/2026-10-23/`, outside the indexed root.
     `AAPL_UW.json` and its manifest stay in `data/marketdata/files/openfigi/identity/2026-10-23/`, as
     PD-0066 decision 9 prefers. Evidence, all read only, 2026-10-24:
     - all four files re-hashed after the move are the hashes of item 8;
     - `FileStore.index()` on `data/marketdata`, with the working-tree `files.py`, now builds, with
       **15 entries**; payload `b2aaeb7b…889c3ccc` maps to
       `files/openfigi/identity/2026-10-23/AAPL_UW.json.manifest.json`, and no entry points under
       `observations/`.

     The design-change route is not needed for this case. The rule "one payload, one manifest" stays,
     and so does `src/`'s refusal, which is the guard for the next such pair. The move is a data action
     the PM records (§11, "What this version leaves to the owner and the PM"); this document is not that
     record.
   - **The A.6 entry cites both manifests by hash**, wherever they are kept, because only the `XNGS`
     request shows the segment-MIC reading. A.6 is convention data, not a release input, so it needs
     neither file in `M`.

   **No valuation role.**
   - The FIGI is an identity attribute (PRD §10.1). This ruling gives it no role in a valuation, and
     the HG4 value `10 × p + 500.00` does not depend on it.
10. **(1.16) Consistency between the levels (fail closed).** An exchange-level record attaches only if
    both of these hold:
    - its `compositeFIGI` equals any `composite_figi` already on ℓ;
    - its `shareClassFIGI` equals any share-class FIGI already on the instrument.

    A difference attaches **nothing**, and both records are kept as unmatched evidence for a human.
    One listing cannot carry FIGIs of two different securities. For AAPL the values are equal, so it
    attaches.
    - "Nothing" means no `Listing.figi`, no `composite_figi`, and no identifier row of any level.
    - **(1.16 fix round, review C-9) The share-class half is new behaviour.** `src/` today refuses a
      composite mismatch (`COMPOSITE_CONFLICT`, `resolver.py`). On a share-class mismatch it still
      attaches the FIGI and adds a second `SHARE_CLASS_FIGI` row, while keeping the instrument's old
      value. §11 item 24 therefore tests the share-class half on its own.

### RULING 7.4 (1.15): A corporate-action type is granted to a feed's undocumented fields only from observation

**Problem.** Alpha Vantage's `SPLITS` endpoint is free, but its fields are not described in prose
(HG4 data-source check). Ruling 7.1 needs, for a `SPLIT`:

- an `ex_date`, meaning the first session on the post-split basis;
- a ratio `(n, o)`, meaning new units over old.

A wrong reading of either is a quantity error: a reverse split read as a forward split is wrong by
`n²/o²`, which is ×16 for 1:4 against 4:1. A wrong date mislinks the ledger (Rulings 6.4, 6.4a).

**Rule.**

1. **Unit of grant.** A grant covers one (source, endpoint, response shape). The shape is the set of
   field names and the lexical form of each field as observed. A response of another shape voids
   the grant for that file until the new shape is observed.
2. **Before a grant, nothing is typed.**
   - Each record yields **no observation of any type**: not `SPLIT`, and not `UNSUPPORTED`.
   - Each record yields an adapter issue `UNMAPPED_ACTION`, and its text is kept in lineage
     (quarantined).
   - If the file is in `M`, it stays there, as a `CONTRADICTED` series' file does (Ruling 3.1).
   - **Lineage flag `UNMAPPED_ACTION_RECORD`**, with no state effect. It is raised for every
     quarantined record whose vendor id resolves to a listing named in the ledger at `L`, and gives
     the listing, the record's date text and the source.
     - Like Ruling 6.4 item 5, it points a human at a possible event. It is not evidence of one.
   - A quarantined record is not an "unclassified source" under Ruling 6.4d. It is not a `SPLIT`
     record, so it creates no key. Its effect equals leaving those records out of `M`, except that
     it is **recorded**, which Ruling 6.4d prefers to hiding.
   - **Never a basis for a grant (E9):**
     - the endpoint's name (`SPLITS`);
     - a field's name (`split_factor`, `effective_date`);
     - a positive ratio;
     - a match to one known event's ratio;
     - a flag or type that a caller supplies.
3. **What must be observed.** Each observation is checked against an **issuer-filing record**
   prepared under Ruling 7.6 item 2, never against another feed, and recorded with the response's
   file hash.
   - **O-1, the shape.** A successful, non-empty response, recording:
     - the field names;
     - the date's lexical form;
     - the ratio's lexical form: a decimal with `d` decimals, or "n:o" or "n/o" text;
     - the body for a symbol that has no records (Ruling 7.5 item 5).
   - **O-2, a forward split of a share distribution of 25 % or more,** whose filing gives three
     **different** dates: record date, payable or distribution date, and ex-date (the first session
     on the split-adjusted basis).
     - The candidate is AAPL's 4-for-1 of 2020. From MEMORY, §12 item 15: record date 2020-08-24,
       distribution 2020-08-28, split-adjusted trading from 2020-08-31. These dates are confirmed
       from the filing before use.
     - The record's date must equal exactly one of the three dates.
     - The ratio's value fixes the direction (new/old against old/new).
   - **O-3, a reverse split** (a consolidation) of a US listing, with its filing. The human chooses
     the listing.
     - It shows how a consolidation is written. That rules out a magnitude-only convention, under
       which 1-for-4 and 4-for-1 would look alike.
     - It also shows the date the record carries.
   - **O-4, a stock distribution under 25 %.** Needed only to map that class. Under US practice its
     ex-date comes before the record date (MEMORY, §12 item 19), so O-2's date semantics do not
     carry over to it.
4. **What may be granted**, and only in a new market-data version that cites the observation files
   and the filing records:
   - **Date.**
     - The record's date maps to Ruling 7.1's `ex_date` **only if** it equalled the ex-date in both
       O-2 and O-3.
     - If it equalled the record date or the payable date, it maps to nothing. **No ex-date is
       derived by an offset rule**, because the offset differs by class and market (§12 item 19).
       The records stay `UNMAPPED_ACTION`.
   - **Ratio direction.**
     - O-2 written as 4 (or "4:1") and O-3 written as a value below 1 for the consolidation (for
       example `0.2500` for 1-for-4) mean **new/old**.
     - The mirror image means old/new, which is inverted on reading.
     - Any other combination gives no grant.
     - Decimal ratios are compared with filings under Ruling 4.5 (1.15).
   - **Classes.** `SPLIT` is granted only for the classes observed:
     - forward with factor `≥ 5/4` (O-2's class);
     - consolidations (O-3's class).

     A factor in `(1, 5/4)` stays `UNMAPPED_ACTION` until O-4. A factor of exactly 1, a factor
     `≤ 0`, or an unparseable factor stays `UNMAPPED_ACTION`.
   - **Never granted from a splits endpoint:** cash dividends, spin-offs, symbol changes, or any
     type Ruling 7.1 lists as unsupported.
5. **Who grants.** The quant records the grant in a new version, with profile status `OBSERVED` and
   the file hashes, as in A.4. The engineer implements a mapping only from that version, never from
   a reading of a sample.
6. **Alpha Vantage `SPLITS` today.** Nothing has been observed, so there is **no grant**, and every
   record is `UNMAPPED_ACTION`.
   - My recollection of its field names (`effective_date`, `split_factor`; MEMORY, §12 item 14)
     grants nothing.
   - A field called `effective_date` is exactly the ambiguity O-2 settles. "Effective" may mean the
     payable date, the ex-date, or the date the vendor recorded the event.
7. **The same rule binds any later feed.** For an A-share 送转 feed, the O-2 analogue is an event
   whose 股权登记日 and 除权除息日 differ: the record date is the session before the ex-date (MEMORY,
   §12 item 21). O-3 has no A-share analogue (A-share consolidations are rare). The class it would
   cover then stays unmapped.

### RULING 7.5 (1.15): Empty and non-data corporate-action responses

1. **An empty response is stored.** A successful response with zero records is kept like any
   acquired file: its bytes, its hash, and a manifest with the request and the retrieval time `R`.
   PD-0064 accepts local storage and archive for Alpha Vantage data.
2. **Its meaning, exactly:** "at `R`, source S returned no record for vendor id V on endpoint E".
   - Its lineage term is **`EMPTY_RESPONSE`**.
   - Its coverage is **`NOT_ESTABLISHED`**. The endpoint's history depth and forward horizon are
     undocumented, so the manifest declares **no** coverage interval. An interval would be a claim
     nobody can support.
3. **Its effect on any computation: none.**
   - It creates no Ruling 6.4d key and fills no role.
   - It is not a filing.
   - It does not make a label `VERIFIED` or "moot" (Ruling 3.2 item 2).
   - It does not shorten an exposure window.
   - It is not "verified complete" and not "no events". Lineage, UI and AI wording must not
     describe it as "no splits", "complete" or "verified".
4. **A known event that is missing.** Suppose `M` holds a filing record of an event for the listing
   that V resolves to, and the response is empty. The source's profile then records
   **`KNOWN_EVENT_ABSENT`**, with the file hash.
   - This is evidence that the endpoint's history is incomplete for that id.
   - It has no state effect.
   - The file cannot serve as O-1 to O-4 evidence (Ruling 7.4).

   For AAPL, an empty response would be such a case once the 2020 filing record exists.
5. **Non-data bodies are acquisition failures, never empty responses.**
   - **What counts:** any body that is not the observed successful shape. For example, a JSON
     object that carries only a notice, a rate-limit message, an error message or a premium-only
     message. From MEMORY (§12 item 16), Alpha Vantage uses the keys `Note`, `Information` and
     `Error Message`, and returns `{}` for some invalid calls.
   - **Never in `M`.** Such a body is never a corporate-action file. It is kept, if at all, as
     acquisition evidence.
   - **Before O-1, no body can be classified `EMPTY_RESPONSE`.** Until the empty successful shape
     has been observed, an empty-looking body (`{}`, `[]`, an object with an empty list) is also an
     acquisition failure.
6. **Vintages.** Corporate-action series are not segmentable (Ruling 0.1 item 3). `M` holds at most
   one file per (source, vendor id, endpoint). A later response is a new vintage, used in a new
   `M`. It is never merged with the empty one.

### RULING 7.6 (1.15): The feed/filing pair for splits, by market

1. **The roles.**

   | Market | Feed role (Ruling 4.5 "feed") | Filing role (Ruling 4.5 "issuer filing") |
   |---|---|---|
   | US | Alpha Vantage `SPLITS`, **once granted** (Ruling 7.4). Until then its records are unmapped. | **SEC EDGAR** issuer filings. Typically the 8-K, or the press release filed as its exhibit, that states the ratio and the record, distribution and ex-dates. Later 10-Q or 10-K notes may restate them. |
   | CN | **none admitted.** No Alpha Vantage A-share corporate-action endpoint is known to me. | **cninfo (巨潮资讯)** issuer announcements, chiefly the 权益分派实施公告 (每10股送/转增 x股; 股权登记日; 除权除息日). The SSE and SZSE disclosure pages carry the same documents (PD-0027). |

   Alpha Vantage and the issuer through EDGAR are separate pipelines, so they are independent in the
   sense of Ruling 4.1.
2. **How a filing record is prepared.** It is a corporate-action file that a **human** confirms
   against the filing before it enters `M`. It contains:
   - the listing: MIC and code;
   - the type;
   - the ratio as stated, in integers;
   - the ex-date as stated, plus the record and payable dates;
   - the filing cited: the EDGAR accession number, or the cninfo announcement id and URL;
   - the quoted sentence or sentences relied on.

   An agent may draft it, as for calendars (Ruling 5.3 item 8). It is never an AI extraction taken
   as fact (PD-0027 condition 5). The filing-role source needs its own `SOURCES.json` entry with a
   terms check (OP-6).
3. **Both sides present and agreeing** (Ruling 4.5 (1.15)): `CORROBORATED`. This drives Ruling 6.4
   detection, and the F8-B append once it is implemented.
4. **Feed only:** `FEED_ONLY`, so `SINGLE_SOURCE`.
   - No detection, no append and no suppression (Ruling 6.4 items 3–4; Ruling 6.4d case (e)).
   - Not a V1 event (Ruling 3.2 item 1).
5. **Filing only:** `FILING_ONLY`, so `SINGLE_SOURCE` for F8: no detection and no append.
   - It **is** a V1 event, and it counts for the exposure rule of Ruling 3.2 item 4. The filing is
     the reference Ruling 3.1 names.
6. **Neither:** there is no key (Ruling 6.4d case (d)). Nothing is claimed either way.
7. **The HG4 single-date check needs neither side** (Ruling 6.5).

---

## 7A (1.15). The Alpha Vantage A-share route: pending observation, not admitted

PD-0063 approved reading Alpha Vantage's free licence as covering Shanghai (`.SHH`) and Shenzhen
(`.SHZ`) symbols. PD-0064 extended the storage reading to them. **That is a terms reading only.**
This section states the route's conventions so that the engineer can build it as **not admitted**.
No CN price profile is admitted here (PD-0065).

### RULING 7A.1: Vendor id → MIC, and how a listing is resolved

1. **Grammar.** A vendor id of this route is exactly six ASCII digits, a full stop, and `SHH` or
   `SHZ` in upper case. Anything else is not a vendor id of this route.
2. **Mapping.** This mapping is `DECLARED` in 1.15 from Alpha Vantage's documentation as the session
   read it for PD-0063 (§12 item 18):
   - **`SHH` → XSHG**;
   - **`SHZ` → XSHE**.

   **(1.16) The status is now `DECLARED` on a human reading** (PD-0066 decision 3).
   - On 2026-10-24 the owner read the live documentation (`#daily`) and reported ".SHH/.SHZ shown as
     supported".
   - 1.15 used the same label on a summarizer read. That was mislabelled, because by §9B item 4 (d)
     such a read is `MEMORY` (review F-6 (a)). The status is unchanged; its basis is now a human
     reading.
   - It is the vendor's declaration of the suffixes. It is not an observation. The Ruling 7A.3 (c)
     observations test it for each profiled listing: a Test V4 equality against the SSE (or SZSE)
     published close of a listing resolved through `.SHH` (or `.SHZ`) observes that the suffix
     reached that exchange's close.

   **The MIC is the only thing inferred from the vendor id.** The security type, the class (A.1),
   the trading currency, the board and the listing's existence are not.
3. **Not mapped:**
   - any other suffix (`.SS`, `.SZ`, `.SH`, `.BJ` and so on);
   - no suffix;
   - a code that is not six digits;
   - a lower-case suffix.

   Each is **unresolved** (`InstrumentResolution.listing_id = None`), flagged, and never guessed.
   The Beijing exchange is not a V1 market.
4. **Resolution** is by **(MIC, six-digit local code)** against the identity table at the
   observation date (Ruling 7.2 item 2).
   - Exactly one active V1 listing resolves it. Zero or several leave it unresolved.
   - The vendor id is stored scoped to its source (`ExternalIdentifiers(vendor_id, source_id)`) and
     is never a key of another source.
   - **(1.16) Restated, the engineer's question.** The vendor id is **kept verbatim in the reading's
     lineage** (the row reference `<vendor id>@<date>`), scoped by the file's source id, and in every
     issue. It is **never handed to the resolver**, and so is never a key, not even for its own
     source.
     - The 1.15 wording "`ExternalIdentifiers(vendor_id, source_id)`" named a form that the resolver
       treats as a lookup step. A stored vendor-id row could then stand in for (MIC, code), which is
       review M-2's failure.
     - So the build after M-2 conforms to this item: the resolver receives (MIC, code) only, and the
       vendor id lives in lineage.
     - A vendor-id row of this route in the identity table is never consulted. Holding one is not an
       error, and it resolves nothing.
   - **Why the code alone never resolves.** One six-digit code can mean different instruments on
     the two exchanges, and some SSE codes are index codes. From MEMORY (§12 item 20), `000001` is a
     Shenzhen share and also the SSE Composite index. So `000001.SHH` resolves to nothing unless an
     XSHG listing with code 000001 exists. None can, because indices are not V1 listings.
5. **Code-range check: `FLAG_ONLY`** (MEMORY, §12 item 17).
   - Expected first digits: `.SHH` codes begin with 5, 6 or 9; `.SHZ` codes begin with 0, 1, 2 or 3.
   - A mismatch is flagged `VENDOR_CODE_RANGE_UNEXPECTED`.
   - The check never resolves or refuses anything by itself. Resolution is by the identity table.
6. **Identity fields and OpenFIGI.**
   - The listing's `SecurityType` and `trading_currency` come from the identity source of record:
     a hand-entered identity record, or the owner's holdings import once that is separately
     approved (PD-0063 item 1). Alpha Vantage's CSV carries neither.
   - **OpenFIGI's role** is an identity-assertion source under Ruling 7.3.
     - An exchange-level FIGI attaches to a CN listing only through an A.6 code with status
       `OBSERVED` or `CONFIRMED`.
     - `CG` (XSHG), `CS` (XSHE) and the composite `CH` are **MEMORY** today, so **no CN FIGI
       attaches** until the A.6 downloads are made.
     - An OpenFIGI query uses the local code (`TICKER` `600519`) with the exchange code. It never
       uses the Alpha Vantage vendor id.
     - OpenFIGI's `securityType2` is a consistency check against the identity record's
       `SecurityType` (Ruling 7.3 item 3). It is not its source.
   - Neither source stands in for the other:
     - the suffix does not give a FIGI;
     - an unattached OpenFIGI record gives no MIC.
7. **Route scope: A-shares and ETFs in CNY.**
   - **In scope:** listings of class `A_SHARE` (`COMMON_STOCK`, CNY) and `FUND_ETF_LOF_BOND`
     (`ETF`, CNY).
   - **Out of scope: B-shares** (USD on XSHG, HKD on XSHE).
     - The CSV carries no currency, and no file shows which currency Alpha Vantage quotes them in.
     - Their files are refused at ingest by the currency mismatch of Ruling 4.1a, because this
       route's manifests declare CNY.
     - A manifest of this route may not declare USD or HKD.
8. **Currency.** The acquirer declares **CNY** in the manifest. It is never inferred from the file.

### RULING 7A.2: Decimals

- **The Appendix A.1 CN `price_max_dp` by security class applies to this source unchanged.** It is
  a fact about the market's price grid (Ruling 2.4 item 4), not about a source:
  - `A_SHARE` 2;
  - `FUND_ETF_LOF_BOND` 3.
- **The class** comes from the identity record (the A.1 table).
  - If unknown, the strict 2 applies, flagged `SECURITY_CLASS_UNRESOLVED` (§9A item 2).
  - The class is re-applied at ingest once it is known, as built.
- **Normalization.**
  - Trailing zeros carry no decimals: `10.1000` is 10.1 and lies on the 2-decimal grid (as
    Example 4-A (a), 12.3400).
  - A text field showing more decimals than its profile's `delivered_dp` fails the profile check,
    and the file is not admitted (A.4 item 7; Ruling 2.4 item 5).
- **Still MEMORY**, and confirmed only from the exchanges' trading rules (上海/深圳证券交易所交易规则)
  by the human:
  - §12 item 10, the ticks: A-shares CNY 0.01; funds and ETFs CNY 0.001;
  - §12 item 11, the board lot of 100 shares, and so what a volume unit of 手 would mean.
- **Why a MEMORY grid is safe here.** It is a refusal-only check. A wrong value could refuse a
  valid price, but never admit an off-grid one.
  - **(1.16, review F-6 (c)) That holds only if the MEMORY value is not looser than the true
    grid.**
    - A value that is too strict, say 2 decimals for a fund whose tick were 0.001, can only refuse
      valid closes. Those cost freshness, as in Example 7A-G3 (b).
    - A value that is too loose would admit off-grid closes, say 3 decimals for shares whose true
      tick is 0.01.
    - So the claim is "refusal-only, provided §12 item 10 is not looser than the exchanges' rules".
      The human's confirmation of §12 item 10 removes the proviso. Until then it is a stated
      residual, and it is one of the facts admission (Ruling 7A.3) relies on.
- **Delivered decimals are this source's own** and are observed (Ruling 7A.3). The US profile's
  `delivered_dp 4` does not carry over.

### RULING 7A.3: Admission is by observation; until then CN keeps `NO_ADMITTED_SOURCE`

1. **Status now.**
   - The `alphavantage.cn` profile is **`TO_OBSERVE`**: pending observation, not admitted.
   - A.5 CN stays `[]`.
   - Every CN listing resolves, for every `D`, to `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`,
     with lineage cause `NO_ADMITTED_SOURCE`, freshness `UNKNOWN` and its ledger facts kept
     (Ruling 4.7).
   - A real `alphavantage.cn` file supplies **no reading**, not even as corroboration, even though
     its terms are attested. Terms attestation is necessary for admission, not sufficient. The
     engineer gates on the profile status and on A.5, not on `terms_check` alone.
2. **Provisional fields for synthetic tests.**
   - The pending profile may carry field declarations that mirror `alphavantage.us`:
     - `TEXT_DECIMAL`, `delivered_dp 4`;
     - the close grid-checked by class;
     - volume integral, `SHARE`, `DECLARED_UNVERIFIED`.
   - They are marked `PROVISIONAL_UNOBSERVED`.
   - They exist **only** so the parser can be tested on synthetic files (Examples 7A-G1 to G3).
   - They admit nothing, and the A.4 results replace them.
3. **Admission requires all of these**, and then an owner PD:
   - **(a) Terms.** Done: the PD-0063 and PD-0064 readings, recorded in `SOURCES.json` by the main
     session.
     - **(1.16) Recorded.** `data/marketdata/SOURCES.json` holds the `alphavantage.cn` entry
       (`checked_on` 2026-10-23, citing PD-0063 and PD-0064, stating that it admits nothing). It came
       with the A-share route commit `f42efa0`. Review F-2 of 1.15 is resolved.
     - PD-0066 decision 5 adds that the licence is a one-year term, renewing unless ended on notice.
       The F1 design handles that as a lease (X1). It changes no market-data rule. A file's usability
       after the licence ends is a rights question of the F1 path, not of this document.
   - **(b) Calendar.** The CN calendar is checked and registered (HG2 condition 4, PD-0038).
     - **(1.16) Met** (PD-0067 decision 1). `CN_A_SESSIONS` `2025-2026 v1` is at
       `calendar.manual/calendar/2026-10-23/CN_A_2025_2026.json`:
       - payload SHA-256 `f357b7d44b41297ae04153965963ac18426d453056f68291f825e4ad0380d772`, which I
         re-hashed;
       - applies to [XSHG, XSHE], zone `Asia/Shanghai`, close 15:00, no overrides;
       - coverage 2025-01-01 to 2026-12-31, `actual_through` 2026-09-30.
     - **Consequences for the observation files.** Dates after 2026-09-30 are scheduled sessions, not
       checked actual ones. Ruling 5.3 item 7 records that in lineage with no state effect.
       - A file for (c) 4 can span a closure inside the checked part, for example 2026-09-25 or
         2026-06-19, both weekday closures of the registered file.
       - A row after 2026-12-31 is outside coverage, and V0 cannot judge it (Ruling 5.3).
       - So an observation file retrieved in 2027 needs a new calendar version first.
   - **(c) Profile observation from real files.** Each result is recorded `OBSERVED` with its file
     hash.
     1. **Format and `delivered_dp`** per field (A.4 items 1 and 7).
     2. **Grid** (A.4 item 4), with the class taken from the identity record. Every close of an
        `A_SHARE` listing lies on the 2-decimal grid. If an ETF is profiled, every ETF close lies
        on the 3-decimal grid.
     3. **Row order, and unique dates.** A file with two rows for one date is refused.
     4. **Session dates.**
        - V0 runs against the registered calendar.
        - At least one profiled file spans a CN holiday closure and has no row on any closed day.
        - No row may fall on a session not closed at `R` (Ruling 3.1's after-retrieval test). So
          the acquirer retrieves after 15:00 Asia/Shanghai on the last session wanted.
     5. **Raw against adjusted, both components** (Rulings 3.2 and 3.3).
        - **Dividend component.** Test V4 on a date `d < X`, for a listing whose cninfo-attested
          cash-dividend ex-date `X` lies in the window, at least 20 sessions before `R`. A vendor
          that applies adjustments late would otherwise look raw. Equality is required.
        - **Split component (送股/转增, Ruling 7.1).** Test V4 on `d < X` for a listing whose
          cninfo-attested 送转 lies in the window. Any ratio will do. V1 is an alternative if the
          event is decisive (`n/o ≥ 2`, as with 10转10).
        - A combined event (10送3派2) tests both components at once.
        - **Any `CONTRADICTED` result**, or a V4 inequality, means the route is not admitted as
          `RAW`.
     6. **Suspension (停牌).** Take a listing whose full-day suspension inside the window is
        attested by an exchange or cninfo notice, and observe how that day is written.
        - **An absent row** is acceptable (Ruling 2.1).
        - **A zero-volume row** is acceptable (Ruling 2.1). Example 7A-G2 shows both resolve
          identically.
        - **A row with volume > 0** on a suspended day is a profile failure, and the route is not
          admitted. The print rule could no longer age the price.
     7. **Volume.** It must be integral (A.4 item 2). Its unit (股 or 手) stays
        `DECLARED_UNVERIFIED` unless a Test V4 record also states the exchange's volume, with its
        unit, for the same date. No magnitude rule may use it meanwhile (Ruling 2.6).
        - **(1.16)** Where a V4 record states the exchange's volume for an SSE listing on or after
          the 2026 revision, it also records whether that figure includes the after-hours
          fixed-price session (Ruling 2.1; MD-OI-19). Otherwise a unit test could be confounded by
          the after-hours trades.
     8. **The official close.** At least one V4 equality, which item 5 already implies.
        - **(1.16)** V4 compares with the close the exchange published for that date, whatever
          mechanism formed it (Ruling 2.1). For an SSE ETF, a date before or after 2026-07-06 serves
          equally.
   - **(d) Identity.** Identity records with `SecurityType` and CNY exist for the owner's CN
     listings. The A.6 `CG`/`CS` observations are needed only if FIGIs are wanted, not for prices.
   - **(e) An owner PD** admits `alphavantage.cn` and sets A.5 CN.
   - **(1.16) Status after PD-0066 and PD-0067:**
     - **(a)** done and recorded;
     - **(b)** met;
     - **(c)** the plan and budget are approved (PD-0067 decision 3, OP-4). The owner names the
       listings later. **No request is approved, no file exists, and nothing is observed.**
       - Each download needs its own approval and an A-share `fetch` route in the download tool,
         which is an engineer increment.
       - **RECOMMENDATION (owner):** retrieve after **15:30** Asia/Shanghai on the last session wanted,
         not only after 15:00. The after-hours session has then ended, so the day's volume is final
         whichever way the vendor counts it.
       - The vendor's update time is undocumented (MEMORY), so later still is safer.
       - This is stricter than, and compatible with, PD-0067's "after 15:00".
     - **(d)** not yet;
     - **(e)** the **intended** order is `CN: [alphavantage]` (PD-0067 decision 2, OP-1 (b)). It is
       **not admitted**: `PRIMARY_ORDER["CN"]` stays `()`, and the profile stays `TO_OBSERVE`. A
       final admission decision by the owner, after the (c) observations are reviewed, is still
       required, in a reviewed increment that changes A.5 and the profile together.
     - **The owner's reading of the documentation (PD-0066 decision 3) relaxes none of (c).** A
       vendor's declaration that the call is raw is exactly what (c) 5 tests, because a mislabelled
       CN series would be wrong at most valuation dates (item 5).
4. **Budget.** Item (c) needs about 3–4 Alpha Vantage requests, since one listing can serve several
   items. That fits within the shared 25-a-day key. It also needs the human's V4 look-ups and the
   cninfo announcements. Each request is a separate owner approval (PD-0027 condition 2; PD-0062
   item 4).
5. **Why this is stricter than the US admission.** Example A-1 admitted the US route on format and
   grid alone, with the label `UNVERIFIABLE`. Three things differ here:
   - A-share cash dividends are near-universal and annual (MEMORY; tagged in 1.16, review F-6 (b)).
     Many CN data vendors serve forward-adjusted (前复权) series by default (MEMORY). A mislabelled
     series would be wrong at every date before the latest ex-date in its vintage, which is exactly
     where valuations fall.
   - Suspensions are common (MEMORY; tagged in 1.16), and the print rule depends on how they are
     written.
   - Neither MEMORY statement is used as a fact by any rule. Each only justifies a stricter admission.
   - No second CN source exists to catch either.

#### Synthetic golden examples for the adapter (7A-G1 to 7A-G4)

**All of these are SYNTHETIC.**

- **No real file.** None was derived from a real file or from running `src/`.
- **Synthetic codes.** The codes (609999, 609998, 569999, 569998, 009999, 009997, 909999) were
  chosen from ranges I believe unassigned (MEMORY). If any is assigned, the fixtures stay synthetic
  by their source id.
- **Expected values** were derived by hand from the inputs shown.

**Shared set-up.**

- **Source.** `synthetic.alphavantage.cn`, with upstream `synthetic` (Ruling 4.8) and payload format
  `alphavantage_csv_daily/1`.
- **Manifest.**
  - `request.function` `TIME_SERIES_DAILY`;
  - declared adjustment `UNDECLARED`, read as `RAW` through the profile's provisional call mapping.
    The label status is `UNVERIFIABLE`, and the label source is the profile, not the file (§9B
    item 4);
  - declared currency CNY;
  - one `source_identifiers` entry, the vendor id.
- **Profile.** The provisional fields of Ruling 7A.3 item 2:
  - open, high, low and close `TEXT_DECIMAL`, `delivered_dp 4`;
  - volume integral, `shares_per_unit 1`, `DECLARED_UNVERIFIED`.
- **Calendar `SYN_CN`** (assumed for the examples; the same closures as the unregistered draft, not
  asserted as fact):
  - XSHG and XSHE, `Asia/Shanghai`, close 15:00;
  - coverage 2026-09-01 to 2026-10-31;
  - sessions are every weekday in coverage **except** 2026-09-25, 2026-10-01, 2026-10-02 and
    2026-10-05 to 2026-10-07;
  - so the sessions near the holiday are 09-24, 09-28, 09-29, 09-30, 10-08 and 10-09.
- **Synthetic identity table:**

  | Listing | MIC | Code | `SecurityType` | Currency | Class (A.1) |
  |---|---|---|---|---|---|
  | L1 | XSHG | 609999 | `COMMON_STOCK` | CNY | `A_SHARE` (2 dp) |
  | L2 | XSHE | 009999 | `COMMON_STOCK` | CNY | `A_SHARE` |
  | L3 | XSHG | 569999 | `ETF` | CNY | `FUND_ETF_LOF_BOND` (3 dp) |
  | L4 | XSHG | 569998 | null | CNY | none: strict 2, `SECURITY_CLASS_UNRESOLVED` |
  | L5 | XSHE | 009997 | `COMMON_STOCK` | CNY | `A_SHARE` |
  | L6 | XSHG | 909999 | `COMMON_STOCK` | USD | `B_SHARE_SSE` (out of route scope) |

- **Resolution.** The resolution results below are in the **synthetic world**, where the synthetic
  source is CN's only source. Each example also states the **real-world** result for the same
  bytes under the pending `alphavantage.cn`.

**7A-G1: an `.SHH` A-share, newest first, across two holidays.**

L1, vendor id `609999.SHH`, retrieved `R` = 2026-10-08T08:00:00Z (16:00 in Shanghai, after the
10-08 close at 07:00Z).

```
timestamp,open,high,low,close,volume
2026-10-08,10.3500,10.6000,10.2800,10.5500,2034500
2026-09-30,10.2000,10.3500,10.1100,10.3000,1523400
2026-09-29,10.0500,10.2200,10.0000,10.2000,1310000
2026-09-28,10.1000,10.1500,9.9800,10.0500,987600
2026-09-24,10.0000,10.1800,9.9500,10.1200,1100300
```

- **Row check** (Ruling 4.6 item 2), `low ≤ min(open, close) ≤ max(open, close) ≤ high`:
  - 10-08: 10.28 ≤ 10.35 ≤ 10.55 ≤ 10.60;
  - 09-30: 10.11 ≤ 10.20 ≤ 10.30 ≤ 10.35;
  - 09-29: 10.00 ≤ 10.05 ≤ 10.20 ≤ 10.22;
  - 09-28: 9.98 ≤ 10.05 ≤ 10.10 ≤ 10.15;
  - 09-24: 9.95 ≤ 10.00 ≤ 10.12 ≤ 10.18.

  All pass.
- **V0.** All five dates are `SYN_CN` sessions.
- **After-retrieval test.** The latest session whose close is at or before `R` is 10-08. No row
  comes later. Pass.
- **Expected adapter output.** No issues, and five quotes **in ascending date order**. The input
  order is not assumed. Each quote has:
  - currency CNY;
  - the vendor id `609999.SHH`, scoped to the source;
  - the verbatim close text in lineage.

| `value_date` | close (numeric) | recovered | bound | volume |
|---|---|---|---|---|
| 2026-09-24 | 10.12 | yes (2 dp) | 0 | 1100300 |
| 2026-09-28 | 10.05 | yes | 0 | 987600 |
| 2026-09-29 | 10.2 | yes (`10.2000` → 1 dp) | 0 | 1310000 |
| 2026-09-30 | 10.3 | yes | 0 | 1523400 |
| 2026-10-08 | 10.55 | yes | 0 | 2034500 |

The open, high and low are not grid-checked. Each has bound `½ × 10⁻⁴`, its V2 `δ_r`.

- **Identity.** `.SHH` gives XSHG, and (XSHG, 609999) is L1. L1's class is `A_SHARE`, and re-applying
  the grid at ingest changes nothing.
- **Resolution (synthetic world):**
  - `D` = 2026-10-08: 10.55, 0 missed, `CURRENT`, `AVAILABLE`.
  - `D` = 2026-10-05, a holiday: `s(D)` = 09-30. There are no sessions in (09-30, 10-05], so the
    price is 10.30, `CURRENT`, `AVAILABLE`, dated 09-30. A holiday is not staleness (Example 5-A).
    300 units are worth 300 × 10.30 = **3,090.00** CNY.
  - `D` = 2026-09-25, a holiday: 10.12 dated 09-24, `CURRENT`.
- **The same bytes as a real `alphavantage.cn` file (pending):**
  - no reading;
  - L1 at any `D` is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, with cause
    `NO_ADMITTED_SOURCE` and freshness `UNKNOWN`;
  - the 300 units and their cost basis are still reported (Ruling 4.7 item 2).

  The engineer tests this through the admission gate. A synthetic payload is never relabelled as a
  real source.

**7A-G2: an `.SHZ` A-share with a suspension, written two ways, plus two refusals.**

L2, vendor id `009999.SHZ`. 09-29 is a suspended day.

G2-a: the suspended day as a zero-volume row. `R` = 2026-09-30T08:00:00Z.

```
timestamp,open,high,low,close,volume
2026-09-30,8.1500,8.2400,8.0800,8.2000,845000
2026-09-29,8.1200,8.1200,8.1200,8.1200,0
2026-09-28,8.0500,8.1500,8.0100,8.1200,912000
```

- **Row checks:**
  - 09-30: 8.08 ≤ 8.15 ≤ 8.20 ≤ 8.24;
  - 09-29: four equal values;
  - 09-28: 8.01 ≤ 8.05 ≤ 8.12 ≤ 8.15.

  All pass.
- **Adapter output.** Three quotes: 8.12 (09-28), 8.12 (09-29, **volume 0**) and 8.2 (09-30), all
  recovered. The 09-29 quote is an observation, **not a print** (Ruling 2.1).
- **Resolution:**
  - `D` = 09-29: the last print is 09-28, and the sessions in (09-28, 09-29] are {09-29}, so
    `s = 1`. The result is `STALE`, `AVAILABLE` + `STALE_DATA`, 8.12 dated 09-28.
  - `D` = 09-30: 8.20, `CURRENT`.

**G2-b: the same file without the 09-29 row.** The adapter gives two quotes. The resolution is
**identical** to G2-a at both dates. That is the point: Ruling 7A.3 (c) 6 accepts either way of
writing a suspension.

**G2-c: a holiday-filled row.** G2-a plus the row `2026-09-25,8.0500,8.0500,8.0500,8.0500,0`.

- 09-25 is not a `SYN_CN` session, so **V0 fails**.
- The whole series from this file is `CONTRADICTED` (Ruling 3.1) and supplies no reading. The file
  stays in `M`.
- `D` = 09-30 is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY` (every series `CONTRADICTED`), with
  lineage naming V0 and 2026-09-25.
- Volume 0 does not rescue the row. V0 judges dates, not prints.

**G2-d: retrieved during the session.** G2-a's rows, retrieved at `R` = 2026-09-30T05:00:00Z (13:00
in Shanghai).

- The latest session whose close is at or before `R` is 09-29 (its close is 2026-09-29T07:00Z). The
  09-30 row lies after it.
- The after-retrieval test **contradicts the whole series** (Ruling 3.1, 1.7). The partial 09-30
  row, and every row with it, supplies nothing.
- `D` = 09-29 is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`. It does **not** fall back to the
  09-28 print.

**7A-G3: the decimal grid by class.**

G3-a: L3 (ETF), vendor id `569999.SHH`, `R` = 2026-09-30T08:00:00Z.

```
timestamp,open,high,low,close,volume
2026-09-30,1.2310,1.2400,1.2290,1.2340,50123400
2026-09-29,1.2280,1.2350,1.2250,1.2345,48000000
2026-09-28,1.2300,1.2330,1.2260,1.2300,45500000
```

Row checks:

- 09-30: 1.229 ≤ 1.231 ≤ 1.234 ≤ 1.240;
- 09-29: 1.225 ≤ 1.228 ≤ 1.2345 ≤ 1.235;
- 09-28: 1.226 ≤ 1.230 ≤ 1.230 ≤ 1.233.

All pass.

| Close | Decimals | Adapter (class unknown: strict 2) | Ingest, class `FUND_ETF_LOF_BOND` (3) |
|---|---|---|---|
| 09-28 `1.2300` | 2 | recovered, bound 0 | recovered, bound 0 |
| 09-29 `1.2345` | 4 | **not recovered**, bound `½ × 10⁻⁴` = 0.00005, flagged `SECURITY_CLASS_UNRESOLVED` | **still not recovered** (4 > 3). Not an admissible print (Ruling 2.4 item 4a). |
| 09-30 `1.2340` | 3 | **not recovered**, bound 0.00005, flagged `SECURITY_CLASS_UNRESOLVED` | **recovered**, bound 0 |

- **Resolution:**
  - `D` = 09-29: the last admissible print is 09-28, so `s = 1`. The result is `AVAILABLE` +
    `STALE_DATA`, 1.23.
  - `D` = 09-30: 1.234, `CURRENT`. 10,000 units are worth 10,000 × 1.234 = **12,340.00** CNY.

**G3-b: the same rows with the class unknown.** L4, vendor id `569998.SHH`, the same rows.

- The class is unknown, so strict 2 decimals stays in force at ingest, and the 09-30 close `1.234`
  **stays unrecovered**.
- `D` = 09-30: the last admissible print is 09-28, and the sessions in (09-28, 09-30] are
  {09-29, 09-30}, so `s = 2`. The result is **`LIMITED` + `STALE_DATA`**, 1.23.
- An unknown class costs freshness. It never admits an off-grid price.

**G3-c: an off-grid A-share close.** L1, vendor id `609999.SHH`, `R` = 2026-09-30T08:00:00Z.

```
timestamp,open,high,low,close,volume
2026-09-30,10.1000,10.1500,10.0500,10.1250,700000
2026-09-29,10.0000,10.1200,9.9900,10.1000,650000
```

- **Row checks:** 09-30: 10.05 ≤ 10.10 ≤ 10.125 ≤ 10.15; 09-29: 9.99 ≤ 10.00 ≤ 10.10 ≤ 10.12.
- **Closes:**
  - 09-29 `10.1000` is 10.1, recovered. Trailing zeros carry no decimals.
  - 09-30 `10.1250` is 10.125, which has 3 decimals. It is **not recovered**, at the adapter (strict
    2) and at ingest (`A_SHARE`, 2). Its bound is 0.00005.
- `D` = 09-30: the last admissible print is 09-29, so `s = 1`. The result is `AVAILABLE` +
  `STALE_DATA`, 10.10.

**G3-d: a float rendering in a text field.** 7A-G1's file, with the 09-30 close written
`10.300000000000001` (15 decimals).

- The field shows more decimals than its declared `delivered_dp 4`, so **the profile check fails**
  (A.4 item 7; Ruling 2.4 item 5).
- **The whole file is not admitted.** The adapter outputs no quote and one profile issue.
- The value is **not** normalized to 10.3. Normalizing it would be a silent repair, and the remedy
  is to correct the profile (to `FLOAT64`) after observation.

**7A-G4: resolving vendor ids (no CSV).**

| Vendor id | Parse | MIC | Lookup (MIC, code) | Result |
|---|---|---|---|---|
| `609999.SHH` | valid | XSHG | L1 | resolved: L1 |
| `009999.SHZ` | valid | XSHE | L2 | resolved: L2 |
| `569999.SHH` | valid | XSHG | L3 | resolved: L3 |
| `009997.SHH` | valid | XSHG | none (L5 is on XSHE) | **unresolved**, and flagged `VENDOR_CODE_RANGE_UNEXPECTED` (a `.SHH` code starting with 0). The same code means another instrument on the other exchange (the `000001` hazard). |
| `009997.SHZ` | valid | XSHE | L5 | resolved: L5 |
| `609999.SHZ` | valid | XSHE | none | **unresolved**, flagged (a `.SHZ` code starting with 6) |
| `609999.SS` | suffix not in this route | — | — | **unresolved** |
| `609999` | no suffix | — | — | **unresolved** |
| `60999.SHH` | 5 digits | — | — | **unresolved** |
| `609999.shh` | lower case | — | — | **unresolved** |
| `909999.SHH` | valid | XSHG | L6 (USD B-share) | resolved, but **out of route scope**. A file declared CNY is refused at ingest by currency mismatch (Ruling 4.1a), and a USD declaration is not allowed on this route (Ruling 7A.1 item 7). |

---

## 8. Where CP2 meets OI-8 (money rounding), and where it does not

| Place | Needs OI-8? | Treatment in this convention set |
|---|---|---|
| Storing ECB quotes | no | stored exactly as published |
| Cross rates | no | exact rationals (Ruling 1.3) |
| Un-adjusting a split-adjusted value | no | exact multiplication; precision carried in the bound (§4.2) |
| Parsing float-rendered raw closes | no | normalization to the tick grid (Ruling 2.4) is parsing, not money rounding |
| Dividend per share from "10派X" | no | X/10 is exact |
| **Converting an amount to the reporting currency** (CP3) | **yes** | The exact result (Example 1-A: 6,764,375 / 5,282 USD) almost never terminates, because every USD/HKD/CNY conversion is a ratio of two ECB quotes. Under Ruling 0.4.6 of `ledger-replay/1.3`, a non-terminating value is `INSUFFICIENT_DATA` / `UNRESOLVED_CONVENTION`. **So OI-8 must be ruled before CP3 presents any reporting-currency value.** CP2 does not need it. |
| Displaying a rate | yes, as a registry display-precision field (as in Ruling 5A.7) | CP3 or CP7. Not CP2. |

---

## 9. Findings on `src/marketdata/contracts.py` (read only; for the engineer and PM to route)

| ID | Finding | Blocks CP2? |
|---|---|---|
| MD1 | `Freshness.state` sits on the observation. Freshness depends on the as-of (Ruling 5.1), so an ingest-time state would be wrong as soon as `D` moves. The state belongs on the resolved input for `(D or t, M)`. The observation keeps `source_time` and `delay_status`. | yes |
| MD2 | `FXObservation.rate` is a `Decimal`. That fits a published ECB leg (base `EUR`). A derived cross must not be an `FXObservation` with a rounded rate (Ruling 1.3). It needs a representation that holds the two leg observations and the exact ratio. | yes |
| MD3 | `Lineage` has only `source` and `adjustment_status`. PD-0027 condition 3 and this document need more: retrieval time, file content hash, known upstream, adjustment method and anchor (Ruling 2.3), label status (§3), reconciliation status (§4.3), the precision profile used, and the fixing or session date actually used. | yes |
| MD4 | `QuoteObservation` has no **session date** (a local date, Ruling 2.2), no **volume** (the print rule, Ruling 2.1) and no price kind (official close). | yes |
| MD5 | `CorporateActionObservation.effective_date` is undefined. It must mean the ex-date (Ruling 7.1). Dividends lack `pay_date`, `record_date`, the per-unit basis and the declared/paid currency. There is no type for unsupported actions, and none for a symbol change (by design: Ruling 7.2 makes it an identifier-history record). | yes, for §6 detection and §7 |
| MD6 | `Listing.ticker` is a single value (`src/domain/instrument.py`). Ruling 7.2 needs an effective-dated ticker history for resolution. That is an identity-model addition, not a change of key. | yes, for symbol changes |
| MD7 | `FreshnessState` has `CURRENT`, `STALE` and `UNKNOWN`, which match Ruling 5.2. No change is needed. The docstring's "no threshold is defined" is now answered by this document. | no |
| MD8 | `DataDelayStatus` is `END_OF_DAY` for every PD-0027 datum. `LIVE` and `DELAYED` stay unreachable until OQ-04b. | no |

## 9A (1.2). Rulings on the CP2b engineer's six judgment calls

| # | Engineer's call | Ruling | Where |
|---|---|---|---|
| 1 | V2's per-row precision bound is a caller input: half a unit of the market's `max_dp` | **Corrected.** The bound comes from the two series' profiles: `e_i = δ_j + \|a\|δ_r`, residual ≤ `e_i + max(e_lo, e_hi)`, plus `u_a` and `u_b` for classification. It is not a caller input. It equals half a unit of `max_dp` only by coincidence. | §3 V2 (a′) |
| 2 | CN `max_dp` defaults to `A_SHARE` = 2 unless the request carries `security_class` | **Confirmed, with two changes.** The class comes from the listing's identity record (`Instrument.security_type`), not from a request parameter. If it is unknown, the strict value 2 applies (fail closed: a 3-dp fund price is refused, never an off-grid share price accepted), and the refusal is flagged "security class unknown", not dropped silently. Currently moot, because no CN source is admitted. | Ruling 2.4 item 4; A.1 |
| 3 | An unrecovered single reading gives `SINGLE_SOURCE` with no value used | **Corrected.** An unrecovered reading is not an admissible print and carries no reconciliation status. `SINGLE_SOURCE` means a value is used. The session counts as missed in Ruling 5.2 (the last admissible print is used, aged), or the result is `MISSING_PRICE_HISTORY` if none exists. | Ruling 2.4 item 4a |
| 4 | Two functions of ONE upstream that differ beyond the bound are `DISAGREEMENT` | **Confirmed, and now written into the ruling.** Within one upstream, agreement is `SINGLE_SOURCE`, while disagreement is `DISAGREEMENT`. | Ruling 4.3 (1.2 row and paragraph) |
| 5 | A `NOT_COMPARABLE` flag when readings differ in currency or are not all `RAW`, with no status | **Corrected for currency, confirmed for adjustment.** A reading in a currency other than the listing's trading currency is **refused at ingest** as a data error. It is not a comparison outcome. An adjusted reading that cannot be un-adjusted exactly is left out of the reading set with a not-comparable lineage note and no status. The resolved value's status is computed over the reading set only. | Ruling 4.1a |
| 6 | Raw OHLC is not stored on `QuoteObservation`, so V2 at ingest needs the raw rows supplied | **Confirmed.** V0–V3 and the Ruling 4.6 row checks are **file-level ingest checks**, run over full rows from the files in `M`, so they are re-runnable and deterministic. Their results (label status, `method`, `anchor`) are stored as series lineage. Note MD4 still stands: the print rule needs **volume** (or a stored print flag) and the **session date** on each observation. | §3; MD4 |
| — | The float32 signature should apply to non-integral fields only | **Confirmed.** Integral fields use the spacing test of A.4 item 2. Integrality is a property of the field's profile, not of a value. | Ruling 2.4 item 5 |

## 9B (1.3). Rulings on the CP2c-1 engineer's questions (the 1.2 implementation)

| # | Question | Ruling | Where |
|---|---|---|---|
| 1 | Two unrecovered readings that agree: the engineer kept `CORROBORATED` with no value used | **Wrong.** Agreement does not make an unrecovered reading admissible. There is no print, no value and **no reconciliation status**. The session counts as missed for Ruling 5.2. Agreement may be noted in lineage (`UNRECOVERED_READINGS_AGREE`) with no state effect. `CORROBORATED` means a value is used. | Ruling 2.4 item 4a |
| 2 | V2's reference bound for raw open/high/low: the close's bound applied to all four | **Corrected.** `δ_r` is per field, from that field's profile. A recovered close is 0. Open, high and low are not grid-validated: `½ × 10^(−delivered_dp)` for text or float64 fields, `½ ulp` for float32. Applying the close's 0 understates the bound and can fail a valid series. | §3 V2 (a′) |
| 3 | 1.1a date check: "coverage" read as the first and last date the file holds | **Not what I meant; now defined.** `[start, end]`: start is the requested start (or, for a full-history file, the first date held for that currency); end is the earlier of the requested end and the last fixing published by the retrieval time (16:00 Berlin rule). The held-dates reading hides a missing edge date. | Ruling 1.1a item 5 |
| 4 | Profile `call_adjustment` (status MEMORY) maps an UNDECLARED `TIME_SERIES_DAILY` manifest to `RAW` | **Acceptable, on four conditions.** (a) The label stays `UNVERIFIABLE`, and lineage records that the RAW label came from the profile with status MEMORY, not from the file. (b) V0, V1 and V2/V3 still run on every file, so a decisive split in a later file verifies or contradicts the label. (c) If the issuer-filing record shows a split inside a file's window and the series shows no jump, the series is `CONTRADICTED`. (d) MEMORY becomes DECLARED only after the human confirms Alpha Vantage's documentation (§12 item 6). **(1.16) (d) is met:** the owner read the live page on 2026-10-24, "raw as traded" (PD-0066 decision 3). The status is `DECLARED` for `alphavantage.us` and `alphavantage.cn`. Conditions (a)–(c) stand unchanged, with `DECLARED` in place of MEMORY in (a). It is a dated reading: it applies to files of the call from the source's admission on, on the stated assumption that the documentation did not change between 2026-10-01 and 2026-10-24. A later reading that differs makes a new market-data version. | §3; A.3 |
| 5 | A V0-`CONTRADICTED` series is dropped per (listing, file); a `REFUTED` Frankfurter file stays in `M`, flagged | **Both confirmed, with the effects stated.** (a) The dropped series supplies no readings, but its file stays in `M` with the failure in lineage. (b) The refuted file supplies **no rate on any date**. Where it differs from the ECB file, that ECB value is `DISAGREEMENT` (`SOURCE_CONFLICT`) until a resolution record. Where it agrees, the ECB value is used (`SINGLE_SOURCE`). | §3 consequences; Ruling 1.1a item 6 |
| 6 | Format of a central-parity series; the CNY check takes an injected mapping (tests only) | **Specified.** It needs: an admitted `cfets` upstream; an explicit ordered pair and quote unit; the parity date (Asia/Shanghai) and the publication instant; the published decimal text; file lineage. It is checked only on dates that are both ECB fixing and parity dates, and never carried forward. Until it is admitted, the check does not run in product paths (`PARITY_CHECK_NOT_RUN` in lineage), and an injected mapping must never reach one. | Ruling 1.5a |

**The typed lookup outcomes `NO_HISTORY`, `STALE_BEYOND_LIMIT` and `FRESHNESS_UNKNOWN`: no
conflict**, on these conditions.

1. **They are internal outcomes, not a second vocabulary.** Every outcome maps to exactly one
   `(sufficiency_state, reason_code)` pair in the PD-0006/PD-0030 vocabulary, and that pair is
   what reaches a `MetricResult`, the UI or the AI layer:

   | Outcome | Price | FX |
   |---|---|---|
   | `NO_HISTORY` | `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY` | `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` |
   | `STALE_BEYOND_LIMIT` (≥ 5 missed) | `INSUFFICIENT_DATA` + **`STALE_DATA`** (Ruling 5.2) | `INSUFFICIENT_DATA` + **`MISSING_FX_HISTORY`** (Ruling 1.6) |
   | `FRESHNESS_UNKNOWN` | `INSUFFICIENT_DATA`, **no** reason code, lineage cause `CALENDAR_COVERAGE_GAP` (or no / several calendars) | same |

   The price and FX rows of `STALE_BEYOND_LIMIT` differ deliberately. A single mapping for both
   would be a defect.

## 9C (1.4). Rulings on the CP2c-2 engineer's open choices (commit `39733e9`)

| # | Choice | Ruling | Where |
|---|---|---|---|
| 1 | Off-date linking: an equal ratio that no corroborated split explains is `CONFLICT_DATE`; a different ratio on another date is unlinkable; the literal reading of 6.4 item 3 blocks for ever | **Corrected: a linking window is needed, and now exists.** ±20 sessions of the listing's calendar around the ex-date. Inside it: one equal split on `X` is `MATCHED`; one equal split on `Y ≠ X` is `CONFLICT_DATE`; any different ratio, or two or more candidates, is `CONFLICT_RATIO`; none is `NOT_RECORDED` (append under F8-B). Outside every window, a ledger split of any ratio is only `UNCORROBORATED_LEDGER_SPLIT` (lineage, no state). Overlapping windows fail closed. An uncovered calendar gives `CALENDAR_COVERAGE_GAP`. | Ruling 6.4a |
| 2 | A user's reversal of a system split is FINAL: never re-appended, valuation suppressed until the user records it | **Agreed, with a scope.** No re-append for the same `(account, ℓ)` with a date inside the reversed event's window, under any later `L`, market-data version or release. Detection still gives `NOT_RECORDED` → `SOURCE_CONFLICT` with cause `SYSTEM_SPLIT_REVERSED_BY_USER`. A corroborated split outside that window follows the normal rule. | Ruling 6.4b |
| 3 | A `REFUTED` Frankfurter file still takes part in the 1.1a date-set check | **Agreed** (made explicit). A date mismatch is `DISAGREEMENT` for that date, for the same reason as a value mismatch: the ECB file's own transport may be at fault. | Ruling 1.1a item 6 |
| 4 | A float64 field with no declared `delivered_dp` gets `½ ulp` (binary64) as its V2 reference bound | **Not agreed.** That bounds only the float rendering, not the source's decimal rounding, so it understates. A missing `delivered_dp` on a field V2 reads stops V2: method `UNKNOWN`, label `UNVERIFIABLE`, cause `PROFILE_INCOMPLETE`. Float32 keeps `½ ulp` of binary32. | §3 V2 (a′) |
| 5 | CN class: `COMMON_STOCK` on a mainland exchange read as an A-share; B-shares and LOF/bond funds not distinguishable | **Strict default confirmed as safe:** it only ever refuses. The class is now derived from (MIC, `SecurityType`, `trading_currency`): B-shares are identified by USD (XSHG) or HKD (XSHE), so no blanket refusal is needed. LOF and bond funds are not V1 instruments. Anything unmatched is strict 2 dp with `SECURITY_CLASS_UNRESOLVED`. | A.1 |
| 6 | `precision_bound` (e.g. `2^-53`) stored with scale up to 100, not PD-0026's 24 | **Methodologically fine, on two conditions.** (a) The bound is stored **exactly**, or rounded **toward +∞** (a larger bound is conservative), never truncated or rounded down. Exact decimal expansions of `2^-k` have `k` decimals, so scale 100 holds every bound down to `2^-100` exactly. Below that, round up. (b) It is metadata about a reading's precision. It is never a money amount, quantity or ledger value, and it never enters a reported number, only comparisons. PD-0026 is titled and written for ledger values (`ledger_event`, migration 0008). Whether its scope also reaches market-data metadata is for the PM to confirm against the PD. Nothing in the method requires the 24-decimal limit there. | Ruling 2.4; §4.2 |
2. **Withholding applies only at `INSUFFICIENT_DATA`.**
   - With 2–4 missed sessions or fixings, the state is `LIMITED`, and the number **is returned**
     with its state (PD-0007: `LIMITED` carries a value).
   - With 1 missed, the number is returned as `AVAILABLE` + `STALE_DATA`.
   - An outcome that withheld a `LIMITED` value would conflict with PD-0007.
3. **The causes that share an outcome stay distinguishable in lineage.** `NO_HISTORY` covers:
   - no print or fixing on or before `D`;
   - `NO_ADMITTED_SOURCE` (Ruling 4.7);
   - every series `CONTRADICTED`;
   - only unrecovered readings.

   Each keeps its own lineage cause. The `SOURCE_CONFLICT` cases (`DISAGREEMENT`, `IMPLAUSIBLE`)
   and CNH (`MISSING_FX_HISTORY`, Ruling 1.4) need their own outcomes or causes. They must not
   be folded into `NO_HISTORY`, because their reason codes differ.

## 9D (1.16). Rulings on the engineer's questions from the A-share route rounds (B2 and the fix round)

**Where the questions are recorded** (1.16 fix round, review C-10):

- Questions 1–5 are in `STATUS.md` item 9 ("Found in passing").
- `reviews/TECH_REVIEW.md` ("Alpha Vantage A-share route, pending (B2) …" and "A-share route fix
  round …") adds context on 2 (`enforce_delivered_dp` is CN-only) and 3 (the Quant is asked for the
  US venues).
- Questions 6 and 7 are in neither file. They come from the task that routed them to me on
  2026-10-24, and they match the engineer's comments at `HEAD` in
  `tests/product/test_marketdata_alphavantage_cn.py`: the G2-c test (about line 481) and the G1 label
  test (about line 289).

Each ruling is a method statement. How it is built is the engineer's (§11 items 23–35; items 34 and
35 were added in fix round 2).

| # | Question | Ruling | Where |
|---|---|---|---|
| 1 | The US path keeps duplicate session dates (pinned as a known gap). Should US refuse them? | **Yes, in every market.** Two rows for one parsed session date make the series (listing, file) `CONTRADICTED`, even when the rows are identical. There is no reading, the file stays in `M`, and lineage names `DUPLICATE_SESSION_DATE` and the dates. CN already refuses, so the US gap was a market exception V0 does not have. | §3 V0 (1.16); Example 3-E |
| 2 | US `delivered_dp` is not enforced. | **Enforce it on every route.** A.4 item 7 has said since 1.5 that "more decimals than declared fails the profile check". The opt-in limited to CN is not in the method. The count is of the decimals the **text shows**, trailing zeros included (`50.50000` shows 5). The grid check counts the **value's** decimals (50.5 has 1). Showing fewer decimals than delivered is not a failure. The stored AAPL file passes: all 400 price texts show 4. | A.4 item 7; Ruling 2.4 item 5; Example 3-E |
| 3 | `MIC_MARKET` lacks ARCX, BATS, XASE and BJSE. | **ARCX, BATS and XASE map to US**, with zone `America/New_York`. They stay `FRESHNESS_UNKNOWN` until a checked calendar names them. **BJSE**, and any other MIC outside the table, maps to **no V1 market**: a real reading bound to such a listing is refused (`LISTING_EXCHANGE_UNKNOWN`), never passed unjudged. RECOMMENDATION: refuse such a MIC at identity registration too. | Ruling 2.2 item 1; Ruling 4.7 item 6; A.1 |
| 4 | Are the two new gate labels, `SOURCE_MARKET_NOT_COVERED` and `LISTING_EXCHANGE_UNKNOWN`, admission refusals rather than metric reasons? | **Confirmed**, with the meanings in Ruling 4.7 item 6. All five gate labels are admission refusals. They are not reason codes, never a metric's lineage cause, and never a UI or AI data condition. A metric sees either the Ruling 4.7 item 1 outcome (the reading left out of `M`) or no computation (the build refused). `LISTING_EXCHANGE_UNKNOWN` also covers an unmapped MIC. | Ruling 4.7 item 6 |
| 5 | The CN vendor id is now carried only in the row reference. Does that meet Ruling 7A.1 item 4? | **Yes.** Item 4 is restated: the vendor id lives verbatim in lineage, scoped by the file's source id, and is never handed to the resolver. 1.15's `ExternalIdentifiers(vendor_id, source_id)` wording named a lookup key, which review M-2 showed could stand in for (MIC, code). | Ruling 7A.1 item 4 |
| 6 | The G2-c lineage lists both `NO_ADMITTED_SOURCE` and `SERIES_CONTRADICTED`. | **Only `SERIES_CONTRADICTED`** (V0, 2026-09-25), as the example states. `NO_ADMITTED_SOURCE` is the cause only when `M` holds no series of the listing at all. In a real `M` the two can never meet. | Ruling 4.7 item 1 (1.16); Example 7A-G2 (c) |
| 7 | `PROVISIONAL_UNOBSERVED` maps to `volume_unit_status` `DECLARED_UNVERIFIED`. | **Confirmed.** `PROVISIONAL_UNOBSERVED` is a profile status (admission). `volume_unit_status` is the lineage's two-valued unit status (`VERIFIED`, `DECLARED_UNVERIFIED`). A provisional field is reported `DECLARED_UNVERIFIED` whatever the file holds, because only A.4 observation on a real file can verify it. The lineage's `precision_profile_id` still names the pending profile, so the provenance is not lost. This is what Ruling 7A.3 item 2 and the 7A-G set-up already state. | Ruling 7A.3 item 2; Ruling 2.6 |

---

## 10. Owner decisions (all three decided 2026-10-01, PD-0030)

**Status in 1.1.**

- **OD-1: decided (b).** `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` are added, both
  requiring a non-`AVAILABLE` state.
- **OD-2: decided F8-B.** It applies once implemented, with F8-A until then.
- **OD-3: decided (a).** CNH stays strict, and a CNH source is added to OQ-04b.

The text below is kept as the record of what was put to the owner. Its "until decided" clauses
are superseded.

**OD-1: Reason codes for two CP2 outcomes** (amends PD-0006 and PD-0025, as PD-0025 did).

- Today, a source conflict and a listing with no price at all can only be `INSUFFICIENT_DATA`
  with a **null** reason code. That is valid under PD-0006, but the UI and the AI layer cannot
  then say why.
- Options:
  - **(a)** Add `SOURCE_CONFLICT`: two inputs that must agree do not, unresolved. This covers
    two price sources, a value outside a published bound, and a ledger split against a
    corroborated corporate action. It requires a non-`AVAILABLE` state.
  - **(b)** Option (a), plus `MISSING_PRICE_HISTORY`, the counterpart of `MISSING_FX_HISTORY`.
    It requires a non-`AVAILABLE` state.
  - **(c)** Add nothing, and carry the cause in lineage detail with a null code.
- **Recommendation: (b).** Both outcomes are common with free sources (STATUS 16d), and both
  need a user-facing explanation.
- **Until decided, (c) applies.** No engineer may reuse `CALCULATION_ERROR`,
  `LEDGER_INCONSISTENT`, `STALE_DATA` or `UNSUPPORTED_ASSET` for them.

**OD-2: F8, the source of split application** (§6).

- Options:
  - **F8-A**, ledger only, with feed detection;
  - **F8-B**, ledger only, with system-appended corroborated splits.

  F8-C and F8-D are rejected on methodology grounds.
- **Recommendation: F8-B.** It changes user-visible behaviour, because the system writes ledger
  events, so it is the owner's.
- **Until decided, F8-A applies.**

**OD-3 (optional; not blocking): CNH translation** (Ruling 1.4).

- In force now: strict, `MISSING_FX_HISTORY` for CNH amounts.
- Options:
  - **(a)** keep strict until OQ-04b supplies a CNH fixing;
  - **(b)** translate CNH at the onshore CNY rate as `LIMITED`, with the caveat stated;
  - **(c)** add a CNH fixing source now, which is a PD-0027 source change.
- **Recommendation: (a)**, with a CNH source added to the OQ-04b scope.

**Not an owner decision, recorded for completeness.** HG1 round 4 §9 item 2 handed the
FX-fixing time back as a product decision. PD-0027's choice of the ECB as the only FX source,
and PD-0028's routing of the convention to this role, settle it for the development tier
(Ruling 1.1). It returns with OQ-04b if the licensed vendor offers another fixing.

### 10.1 (1.15) Owner proposals, open. Nothing here is decided.

**(1.16) Status after PD-0066 and PD-0067.** Decided by the owner, recorded here, and decided by no
one else. The 1.15 text below is kept as the record of what was put to the owner.

| Proposal | Status | Record |
|---|---|---|
| OP-1, the A.5 CN order | **(b) chosen as the intended order, not admitted.** A.5 CN stays `[]` until the Ruling 7A.3 (c) observations pass and the owner decides admission again. | PD-0067 decision 2 |
| OP-2, the HG4 UAT's `M` | **(a): no corporate-action file.** | PD-0066 decision 2 |
| OP-3, the `SPLITS` acquisitions | **Deferred.** Ruling 7.4 stands, and every record is `UNMAPPED_ACTION`. | PD-0067 decision 5 |
| OP-4, the CN profile acquisitions | **The plan and budget are approved.** The listings are named later, and each request is approved separately. No request is approved yet. | PD-0067 decision 3 |
| OP-5, the documentation statements | **Done.** "Raw as traded" and ".SHH/.SHZ shown as supported" (the owner's reading of 2026-10-24). The label source and the 7A.1 mapping are `DECLARED`. | PD-0066 decision 3 |
| OP-6, the filing-role sources | **Decided: register SEC EDGAR and cninfo; an agent drafts filing records from text the owner supplies, and the owner confirms each.** Not done: no `SOURCES.json` entry is added until the owner's own terms reading of each site is recorded. Until then no filing record can enter `M`. | PD-0067 decision 4 |

**OP-1: the A.5 CN source order** (Ruling 7A.3 item 3 (e)). Options:

- **(a) Status quo.** CN has no admitted source, and CN holdings show ledger facts only (Ruling
  4.7).
- **(b) `CN: [alphavantage]` alone**, once Ruling 7A.3 (b)–(d) are met.
  - Every CN price is then `SINGLE_SOURCE`, as every US price is.
  - The only cross-check is human Test V4 spot checks against the exchange.
  - HG2 has no CN price-to-price reconciliation evidence, which should be said plainly, as Ruling
    4.7 item 4 says it for US.
- **(c) Option (b) plus a second upstream for corroboration.** Each candidate is listed with what
  blocks it:

  | Candidate | What it would add | What blocks it |
  |---|---|---|
  | The owner's broker (CN broker) statements or exports | an independent upstream for the closes of **held** listings on statement dates | A separately approved reading of the owner's files (PD-0063 item 1), a profile, and the broker's terms. It covers held listings and statement dates only. |
  | SSE/SZSE published daily data | the official close itself | Its terms for anything beyond a human-recorded V4 figure are unread. As a bulk feed, its admission needs a terms check. |
  | Tushare Pro | broad history | It needs an account and a token, which no one may create tonight. Its terms are unread, and some tiers are paid (PD-0063 item 2: no paid personal plan). From MEMORY. |
  | BaoStock | broad history | No written terms were found (2026-10-01). It is unattested and stays refused. |
  | EODHD | broad history | It is paid, which PD-0063 item 2 excludes for now. |
  | AKShare/Eastmoney, Sina | — | **Not options.** They are refused by PD-0031 and PD-0032. |

- **Recommendation: (b)** once its preconditions hold, keeping the broker option of (c) for later. A
  second upstream's place in the order is set in the version that admits it. Within the §4.2 bound,
  order matters only for an unrecovered value (Ruling 4.3).

**OP-2: what the HG4 UAT's `M` holds** (Ruling 6.5 item 8).

- **(a) No corporate-action file.** Recommended.
- **(b) Include the Alpha Vantage `SPLITS` file.** The value is the same, but the configured policy
  must classify its source, which adds a refusal route.

**OP-3: acquisitions for the Alpha Vantage `SPLITS` grant** (Ruling 7.4). Optional for HG4.

- One Alpha Vantage request for AAPL (O-1, O-2).
- One request for a US listing with a reverse split, chosen by the human with its 8-K (O-3).
- The human-confirmed SEC filing records for both (Ruling 7.6 item 2).

Each request is a separate approval (PD-0027 condition 2).

**OP-4: acquisitions for the CN profile** (Ruling 7A.3 (c)).

- About 3–4 Alpha Vantage requests.
- The human's V4 look-ups on the SSE/SZSE pages.
- The cninfo announcements for the dividend, 送转 and suspension listings.

These come after the CN calendar is registered.

**OP-5: confirm two documentation statements**, as a human reading of the live Alpha Vantage pages:

- `TIME_SERIES_DAILY` is raw (as-traded). This moves the label source from `MEMORY` to `DECLARED`,
  §9B item 4 (d). The HG4 data-source check was a research agent reading through a summarizer, so it
  does not count as the human's confirmation.
- `.SHH` and `.SHZ` symbols are supported, and the raw statement covers them.

**OP-6: register the filing-role sources** `sec.edgar` and `cninfo` (ids illustrative), with terms
checks, and decide who prepares filing records. The options are the human alone, or an agent draft
that the human confirms (Ruling 7.6 item 2).

---

## 11. What the engineer must implement, and must not decide

**Must implement** (CP2 tech plan; Write/Edit only):

1. ECB EUR-based quotes as published decimal text. `observed_at` and `source_time` are
   `f` at 14:10 Europe/Berlin (1.8; it was 14:15 through 1.7). The ECB calendar file's
   `fixing.time` must say 14:10 as well, since the calendar adapter checks it against the
   convention. Prefer the ECB's own history file; use a re-server only for
   the transport check (§4.1). Never use a rebased quote.
2. Crosses as exact rationals of same-date legs (Ruling 1.3), carrying both lineage records.
3. `C_ECB` and the exchange session calendars `C_m` as versioned, hashed reference files of
   actual sessions, part of `M`.
4. Resolution of `P(ℓ, D | M)` and `X(b→q, D | M)` returning:
   - the value, or none;
   - the date actually used;
   - the missed-session or missed-fixing count;
   - `FreshnessState`, `(sufficiency, reason)` and lineage.

   This is computed at resolution, per Rulings 1.6 and 5.2, in both modes.
5. Raw official closes as the only valuation price. The print rule (volume > 0). No sibling
   substitution.
6. Adjusted series stored with method, anchor and vintage, and not used in valuation
   (Ruling 2.3).
7. Label tests V0–V3 at ingest, and the label status (§3). V2 is the 1.1 affine fit, and its
   result sets `method` (Ruling 2.3).
8. Reconciliation with the precision profiles of Appendix A, the statuses of Ruling 4.3, primary
   order by upstream (Appendix A), both values kept in lineage, and resolution records as inputs
   in `M`.
8a. (1.1) Number parsing per Ruling 2.4:
    - the shortest round-trip in the field's declared binary format;
    - the `max_dp` validation;
    - the profile-versus-data check;
    - an unrecovered value marked and limited to corroboration.

    Profiles are a versioned data file, built from Appendix A, with the profile version
    recorded in the manifest.
8b. (1.1) The shared-library safeguards of Ruling 4.6, and the volume-unit check of
    Ruling 2.6.
8c. (1.1) Vendor-derived columns (涨跌幅, 涨跌额, 振幅, 换手率 and similar) are not parsed into
    observations. 涨跌额 is used only as the Ruling 4.6 check.
9. Plausibility bands: CFETS ±2 % and the HKD 7.75–7.85 band (Ruling 1.5).
10. `M` as an explicit file set with one vintage per series (Ruling 0.1). Refuse to build an
    `M` that has two. **(1.12)** "One vintage" is per date: admit disjoint-coverage segments of a
    vintage-stable series and join them in the release build; refuse overlapping coverage, segmented
    adjusted series, and segments whose identities differ. **(1.13)** Also refuse a segment whose
    coverage cannot be stated, or which holds a row outside its declared coverage (never widen it).
11. Corporate-action normalization per Ruling 7.1. The symbol-change identifier history and the
    FIGI-equality test per Ruling 7.2.
12. F8-A detection (Ruling 6.4) now. F8-B (decided, PD-0030 §2) in a later CP2 increment,
    with the attribution PD-0030 requires.
13. `market-data/1.11` recorded in every manifest that reads market data.
    - 1.11: Ruling 6.4d, the confirmation-policy test per (listing, ex-date):
      - **Policy validity.** Both roles must be non-empty and disjoint. This is checked when the
        policy is configured.
      - **For every listing ℓ** named by an event of the ledger at `L`, and every ex-date `X` of
        a `SPLIT` record of ℓ in `M` (or `M_t`), with **exact** date equality: if any source
        with a record for (ℓ, X) is in neither role, the key is unmatched.
        - This is `if foreign:`, not `if unmatched and foreign:`. Case (c) also refuses.
        - The ±20-session window is not used.
      - **Any unmatched key:** refuse the whole computation, and, under F8-B, the append run:
        - state `INSUFFICIENT_DATA`, reason code null, lineage cause
          `DETECTION_POLICY_UNMATCHED`;
        - list every unmatched key in (listing id text, `X`) order, each with `listing`,
          `ex_date`, `unclassified_sources` (sorted) and `unmatched_roles` (a subset of `feed`,
          `filing`, in that order, possibly empty);
        - cite the policy (digest, feed ids, filing ids) in the manifest.
      - **The synthetic-data refusal stays first.**
      - **Tests should cover:** every row of Example 6-D (Q1–Q4, case (c) with `third.feed`,
        case (e)), through the service, pure and through PostgreSQL. The reviewer checks against
        Ruling 6.4d.
    - 1.10: clarification only (Ruling 6.4c rule 4, a partial sale by a receiver); no behaviour
      change.
    - 1.9: Ruling 6.4c (the suppression follows carried units: taint by lot identity,
      conservatively until the receiver ends a day at 0 before the FIFO fold exists; in-kind
      flows of suppressed units are suppressed). Ruling 4.8 item 4 (synthetic evidence: no append;
      detection and suppression on; corroboration within one world; the append bar depends on the
      evidence, not on `M`).
    - 1.8: the ECB nominal fixing instant 14:10 (code constant and the ECB calendar's
      `fixing.time` together); the scheduled-close rule of Ruling 5.3 item 6 (HKEX 16:10/12:10,
      calendar data only); CNH aggregates `INSUFFICIENT_DATA` (Ruling 1.4).
    - 1.7: Test V0-FX (whole-series exclusion, `V0_FX_OFF_CALENDAR`), and the after-retrieval
      row check for prices and FX.
    - 1.6: Ruling 6.4a item 5, tightened, with the coverage-gap case and the
      resolution-record clearing path; Ruling 7.3 item 4, composite-only resolution deferred,
      with "unresolved" pinned by a test.
    - The 1.5 changes are
    Ruling 7.3 with the A.6 table (FIGI levels, attachment, and the composite rule) and the
    declared `delivered_dp` values with A.4 item 7.
    - The 1.3 behaviour changes are §9B items 1, 2, 3 and 5(b), and Ruling 1.5a.
    - The 1.4 changes are §9C items 1, 2, 4 and 5: Rulings 6.4a and 6.4b, V2 (a′)
      `PROFILE_INCOMPLETE`, and the A.1 CN class table.
14. (1.1) `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY` used exactly as in the Ruling 4.4
    table.
15. (1.2) Calendar files with the content of Ruling 5.3, hand-made by the human. A coverage gap
    gives `UNKNOWN` with the `CALENDAR_COVERAGE_GAP` lineage cause, never an inferred weekday.
16. (1.2) The no-admitted-source representation of Ruling 4.7, the synthetic-data separation of
    Ruling 4.8, and `provenance: UNCONFIRMED` on Frankfurter-derived rates until Ruling 1.1a's
    check passes.
17. (1.15) **Test V1 and Ruling 3.2, built together.**
    - **V1:**
      - its events are filing-role `SPLIT` records only, using the filing's ratio;
      - it needs admissible prints at `p₋` and `p₊` in one file;
      - it uses the decisive-event rule.
    - **The exposure window** `E(d_p, R)`, with `N(R)` the first session strictly after `R`'s
      local date.
    - **Item 4's suppression:** `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY` with cause
      `SPLIT_LABEL_EXPOSED`. It applies to every close of the file dated before `X`.
    - **Item 5's lineage**, and `DIVIDEND_LABEL_EXPOSED` (informational).
    - **Until both are built**, apply the interim pre-run refusal of item 6.
    - **Tests:** Example 3-D (a)–(d); the three fixture splits named in the 1.15 change note give
      `VERIFIED`.
18. (1.15) **Test V4** (Ruling 3.3).
    - A human-authored reference record as an input kind in `M`.
    - Exact equality with a recovered close.
    - The three outcomes.
    - The record is never a price reading and never a resolution record.
19. (1.15) **The decimal-ratio comparison** of Ruling 4.5 (1.15). Tests: every row of Example 4-B.
20. (1.15) **Alpha Vantage `SPLITS`** (Rulings 7.4 and 7.5).
    - The adapter emits `UNMAPPED_ACTION` for every record and **no `SPLIT`**, whatever the record
      contains.
    - The lineage flag `UNMAPPED_ACTION_RECORD` for records of ledger listings.
    - `EMPTY_RESPONSE` only after O-1 is granted. Before that, an empty-looking body and any
      notice, error or rate-limit body is an acquisition failure, kept out of `M`.
    - No coverage interval for an empty response.
    - `KNOWN_EVENT_ABSENT` in the profile.
    - **Tests:**
      - negative oracles: a ratio of exactly 4, a field named `split_factor`, a caller-supplied
        type, the endpoint name;
      - Example 6-E rows (ii) and (iii).
21. (1.15) **The `alphavantage.cn` route** (§7A).
    - **Parameterize the Alpha Vantage adapter by source and market.** US behaviour stays
      byte-for-byte unchanged.
    - **Profile:** `TO_OBSERVE`, with `PROVISIONAL_UNOBSERVED` fields.
    - **Vendor ids:** the grammar and the suffix → MIC map of Ruling 7A.1, resolution by
      (MIC, code), and the `FLAG_ONLY` code-range check.
    - **Scope:** refuse B-shares; manifests declare CNY.
    - **The admission gate.** A real `alphavantage.cn` file supplies no reading while the profile
      is `TO_OBSERVE` or A.5 CN is empty, even with a permitting `terms_check`.
    - **Tests:** Examples 7A-G1 to 7A-G4, plus a test that CN still resolves to
      `NO_ADMITTED_SOURCE`.
22. (1.15) **Ruling 6.5 item 4.** Test: a corroborated split dated before any holding, outside the
    calendar's coverage, changes nothing (Example 6-E row (iv)).

**(1.16) Must implement**, in an increment **after** today's move of the code label to
`market-data/1.15` (PD-0067 decision 6).

**When a manifest may cite 1.16** (1.16 fix round, reviews L-6 and C-5; rewritten in fix round 2,
reviews L-2 and R2-C3, so that it stands on this section alone).

1. **The gate.** A manifest cites `market-data/1.16` only once items **23–28 and 32–35** are all built.
   These items are unconditional, and they can be built now. Item 35 includes re-issuing the three
   registries for 1.16 before the label moves.
2. **What does not gate the label, and how it is disclosed.** The engine behaviours of items 17–22, 29
   and 30 depend on Test V1 or Test V4, or are separate builds. They do not gate the label. Instead,
   **every one of them that is not built when a manifest cites 1.16 is listed in that manifest, one
   "not built" line each**, naming the 1.16 ruling and stating what the code does not do. The line is
   part of the manifest, so the gap is auditable from the manifest alone (P9). The lines are, at
   least:
   1. **Ruling 3.2 item 4 with Test V1** (items 17 and 30): no close is withheld for split-label
      exposure, in the 1.16 form (the synthetic-world V1 events of item 1, the coverage clause of
      item 3, and clearing by V4 only where Ruling 3.3 establishes `RAW`). The line also says that the
      interim pre-run check of Ruling 3.2 item 6 applies, that it is made by hand, and that the manifest
      does not record that it was made or what it found;
   2. **Ruling 3.2 item 5** (items 17 and 30): the valuation lineage does not carry the label status
      and source of each `RAW` reading used, `E` as a date list, or the item 5 statement of V1 events
      in its three cases; `DIVIDEND_LABEL_EXPOSED` is not raised;
   3. **Ruling 3.3, Test V4, in its 1.16 form** (items 18 and 29): no human-recorded exchange close is
      an input of `M`, so no `RAW` label is established by it; the window `(d, N(R)]` and the
      consolidation condition are not applied;
   4. **Ruling 4.5 (1.15)** (item 19): a ratio delivered as a decimal factor is not compared with the
      filing's exact ratio;
   5. **Rulings 7.4 and 7.5** (item 20): no adapter emits `UNMAPPED_ACTION` for a feed with no granted
      meaning, no `UNMAPPED_ACTION_RECORD` flag is raised, and empty or non-data responses are not
      classified (`EMPTY_RESPONSE`);
   6. **items 21 and 22** (the `alphavantage.cn` route of §7A, and Ruling 6.5 item 4), each only if it
      is not built when the label moves. The engineer states which are built, with the test that
      shows it.

   A line is removed only by the increment that builds the behaviour with its tests. The interim
   pre-run rule of Ruling 3.2 item 6 stands until item 1's line is removed. Each conditional item is
   built together with the test it extends.
3. **Item 31** binds the F1 path whenever it presents a Ruling 6.5 result, whatever label the manifest
   cites. It is not a market-data engine item.
4. **Which rule governs which label.** The 1.15 change note above says a manifest cites
   `market-data/1.15` "once its behaviour changes are built". That sentence is part of the 1.15 text
   and is not edited. For 1.15 it was overridden by the owner: PD-0067 decision 6 moved the code to the
   1.15 label before items 17–20 were built, so that the release id names the method the code runs. A
   product decision ranks above this document. PD-0067 does not say how the unbuilt behaviours are
   disclosed. The 1.15 code lists them in each manifest's open items, which is what point 2 requires
   for 1.16, but that code is not the authority for this rule. **From 1.16 on, points 1–3 govern.**

A manifest that cites 1.16 before items 23–28 and 32–35 are all built, or that omits a "not built" line
point 2 requires, is a defect: the id would name a method the code does not run (P12), or hide that it
does not (P9).

23. **The label source from profile data** (§9B item 4 (d); Ruling 3.2 item 5).
    - `alphavantage.us` and `alphavantage.cn` `TIME_SERIES_DAILY`: the `call_adjustment` entry carries
      status `DECLARED` and the reference PD-0066 decision 3.
    - The lineage label source reads `PROFILE_CALL_ADJUSTMENT:<source>:TIME_SERIES_DAILY:DECLARED`.
      The status comes **from the profile data**; `daily_csv.py` today hard-codes `:MEMORY`.
    - The label **status** stays `UNVERIFIABLE`.
    - Test: a file of an undeclared manifest carries `DECLARED` in lineage and `UNVERIFIABLE` as its
      status.
    - **No test reproduces a 1.15 manifest under 1.16 code** (1.16 fix round, review C-3). That is
      refused with `CONVENTION_MISMATCH`, which is correct. Stored 1.15 results keep the `MEMORY` they
      recorded (Ruling 6.5 item 6).
24. **A.6 and Ruling 7.3 items 8–10.**
    - `XNAS` `UW` (segment XNGS) becomes `OBSERVED`, citing the payload SHA-256 `b2aaeb7b…889c3ccc`
      and both manifests (`7952829b…a738` in the store, `cb4d862d…63c8d` under `observations/`).
      Table version `market-data/1.16#a6/2`.
    - The attachment of item 9: iff item 3's conditions against the hand-entered AAPL identity record
      and item 10's two level-consistency checks all hold (fix round 2, review L-1).
    - The level-consistency refusal of item 10.
    - Tests:
      - the AAPL record attaches `BBG000B9Y5X2`, `BBG000B9XRY4` and `BBG001S5N8V8`. **(fix round 2)**
        The owner's move of 2026-10-24 is done (Ruling 7.3 item 9), so this can run read only on the
        real data root, from `files/openfigi/identity/2026-10-23/AAPL_UW.json`. It also runs on a test
        root holding one manifest;
      - the same record with a hand-entered `composite_figi` that differs from `BBG000B9XRY4`
        attaches nothing (item 9's "iff", through item 10);
      - a record with `exchCode` `UQ`, `UN` or `UP` still attaches nothing;
      - a record whose `compositeFIGI` differs from a stored `composite_figi` attaches nothing (already
        true in `src/`, kept);
      - **(1.16 fix round, review C-9)** a record whose `compositeFIGI` matches, but whose
        `shareClassFIGI` differs from the instrument's, attaches nothing: no `Listing.figi`, and no
        new identifier row of any level. It is kept as unmatched evidence. This is new behaviour;
      - **(review C-4)** a data root holding two manifests of one payload is still refused before any
        file is read. This is the `FileStore.index()` behaviour, kept. Since the move it is tested on a
        test root, not on the real one;
      - **(fix round 2)** `FileStore.index()` on the real data root builds, and maps payload
        `b2aaeb7b…889c3ccc` to the `AAPL_UW.json` manifest. Nothing under `data/marketdata/observations/`
        is indexed.
25. **Test V0 for duplicate session dates, in every market** (§3 V0 (1.16)). The key is the parsed
    date, and the unit is the series. Tests: Example 3-E (a) and (a′), plus one CN case. The CN
    route's behaviour (no reading) is kept, and its cause now reaches the lookup lineage.
26. **A.4 item 7 on every route** (US included). Count the decimals the text shows, trailing zeros
    included, for every `TEXT_DECIMAL` or `FLOAT64` field with a declared `delivered_dp`; integral
    fields are exempt. Tests: Example 3-E (b) and (c). The stored AAPL file still passes, since every
    price text shows 4 decimals.
27. **The per-reading gate of Ruling 4.7 item 6**, at ingest, in the store constructor, in
    `write_release` and in `read_release`.
    - The MIC → market table gains ARCX, BATS and XASE (US), and Ruling 2.2 item 1 gains their zone.
    - An unmapped MIC is refused (`LISTING_EXCHANGE_UNKNOWN`).
    - A source with no profile never supplies a real price reading (review R-2), with the label
      `SOURCE_NOT_ADMITTED`.
    - **Corporate-action records** (1.16 fix round, review C-6; fix round 2, review R2-C5):
      - a profiled source's records pass conditions 1–3, as its price readings do. That is kept from
        `src/`;
      - a filing source's records are checked against the markets of its Appendix A.3 **filing
        profile** (Ruling 4.7 item 6), not against a `SOURCES.json` field. No registry field is added,
        so no registry digest moves. A filing profile is added only when a filing source is registered,
        and the profile-set counter moves then (item 32);
      - a real corporate-action record of a source with **no profile of either kind** is refused
        (`SOURCE_NOT_ADMITTED`). This is new behaviour: today `listing_market_refusal` returns no
        refusal for a source with no profile, and the corporate-action path has no other profile
        check.
    - The five labels stay admission refusals and never reach a `ReasonCode`.
    - Tests:
      - BJSE and XSSC listings are refused;
      - in a hand-built store, a real `alphavantage.cn` `SPLIT` bound to an XSHG listing is refused
        (`SOURCE_PENDING_OBSERVATION`), and so is a record of a source whose profile is refused;
      - an ARCX listing passes the gate for `alphavantage.us` and is still `FRESHNESS_UNKNOWN` under
        the registered NYSE calendar;
      - an `openfigi` quote is refused;
      - the TS-1 arms (adjusted rows and corporate actions) are covered.
28. **`NO_ADMITTED_SOURCE` exclusivity** (Ruling 4.7 item 1 (1.16)). Add the cause only when the
    listing has no series in `M`, so neither readings nor exclusions. Test: Example 7A-G2 (c) lineage
    names V0 and 2026-09-25, and not `NO_ADMITTED_SOURCE`. A listing with no series keeps
    `NO_ADMITTED_SOURCE`.
29. **When Test V4 is built (item 18): the window `(d, N(R)]` and the consolidation condition** of
    Ruling 3.3 (1.16). Tests: rows (a)–(d) of Example 3-F.
30. **When V1 and Ruling 3.2 item 4 are built (item 17):**
    - the synthetic-world V1 events of Ruling 3.2 item 1 (1.16), so SYNS, SYNT and SYN43 give
      `VERIFIED`;
    - the coverage clause of Ruling 3.2 item 3 (1.16, fix round). The coverage-gap rule bites only for
      a V1 event after `T` **when `N(R)` is undetermined**;
    - lineage of `E` beyond coverage;
    - **(fix round 2, review R2-C6)** Ruling 3.2 item 5's statement of V1 events, in exactly one of
      its three cases: the V1 events found in `E` (any later ones listed as outside `E`); "no V1 event
      in `E`", with the V1 events of ℓ dated after `E` listed as outside `E`; or "no V1 event in `M`",
      only when `M` holds no V1 event of ℓ with `X > d_p`;
    - **(1.16 fix round, reviews M-1 and C-1)** item 4 clears by V4 only where Ruling 3.3
      establishes `RAW` for `X`. A V4 equality that establishes nothing never clears. This part waits
      for item 29 as well.

    Tests:
    - every row of Example 3-G, (d) included. Row (d)'s lineage reads "no V1 event in `E`" and lists the
      2027-01-15 record as outside `E`; it never reads "no V1 event in `M`";
    - Example 3-F (b) and (e) through item 4, once item 29 is built.

    Meanwhile, the interim pre-run rule of item 6 places records the same way. It refuses for a record
    after `T` only when `N(R)` is undetermined.
31. **Ruling 6.5 items 6 and 9, on the F1 path** (`implementation/CP7_F1_REAL_PATH_DESIGN.md` R1, R5
    and R7).
    - The claim-limit list C-1 to C-6 and N-1 to N-9 is carried item by item into the R5 output and
      the R7 screen, with **N-2 (dividend component `UNVERIFIABLE`) as its own item**.
    - The origin fields are mandatory, immutable and never defaulted. A missing `personal_holdings`
      refuses the computation.
    - `market_origin = REAL_SOURCE` only for an `M` with no synthetic file.
    - `state_kind = ACTUAL`.
32. **Ids.** (Fix round 2, reviews R2-C2, R2-C4 and L-3.)
    - **The eight label constants move together, all to 1.16** (review R2-C2). Each reaches a record:
      `conventions.ids()` returns the convention set and the four per-rule policy ids, and the
      performance engine writes them into every manifest as `market_data.<k>`; `TOLERANCE_REF` is
      written into each reconciliation result; `PROFILE_SET_VERSION` prefixes every
      `precision_profile_id` in lineage; `CONVENTION_SET_ID` is stamped on file records and releases. A
      manifest that cites `market-data/1.16` beside a per-rule id of 1.15 names a 1.15 text for a rule
      the code runs in its 1.16 form (1.16 changes Ruling 2.1 and Ruling 4.7, for example), which P12 and
      P9 forbid.

      | Constant (module as of the 1.15 working tree) | Value under 1.15 code | Value under 1.16 |
      |---|---|---|
      | `CONVENTION_SET` (`profiles.py`) | `market-data/1.15` | `market-data/1.16` |
      | `CONVENTION_SET_ID` (`manifest.py`) | `market-data/1.15` | `market-data/1.16` |
      | `PROFILE_SET_VERSION` (`profiles.py`) | `market-data/1.15#profiles/4` | **`market-data/1.16#profiles/5`** |
      | `FRESHNESS_ID` (`market11.py`) | `market-data/1.15#5.2` | `market-data/1.16#5.2` |
      | `PRICE_OF_DATE_ID` (`market11.py`) | `market-data/1.15#2.1-2.4a` | `market-data/1.16#2.1-2.4a` |
      | `FX_ID` (`market11.py`) | `market-data/1.15#1.1-1.6` | `market-data/1.16#1.1-1.6` |
      | `RULE_ID` (`reconciliation.py`) | `market-data/1.15#4.1-4.8` | `market-data/1.16#4.1-4.8` |
      | `TOLERANCE_REF` (`reconciliation.py`) | `market-data/1.15#4.2` | `market-data/1.16#4.2` |

      A per-rule id names the convention set whose text the code runs. It moves with the set even if
      that ruling's text did not change, because "the text of 1.16" is one text (P9). The ruling ranges
      after `#` do not change. Any new constant of this kind is added to this table by a market-data
      version before it is written into a manifest.
    - **A.6 `TABLE_VERSION`** = `market-data/1.16#a6/2` (its own rule, below). It is not one of the
      eight and does not move with them.
    - Every release id changes.
    - **Rule for the profile-set counter (1.16; scope fixed in fix round 2, review R2-C4).** The
      profile-set id is `<governing convention set>#profiles/<k>`.
      - **What is counted.** `k` counts the content of every convention value the profiles module
        (`src/marketdata/profiles.py`) transcribes, wherever in this document the value is ruled:
        Appendix A.1–A.5 (the market profiles, the CN class table, the source and filing profiles with
        every field, status and reference, and the primary order), the Ruling 2.2 item 1 exchange zones,
        the Ruling 4.7 item 6 MIC → market table, and the Ruling 1.8 ECB fixing and publication times.
        Comments, docstrings, the refusal-label names and the id constants themselves are not content.
      - **When it moves.** `k` increases by one whenever that content changes, and only then.
        **Different content never shares an id**, and the same content under a new governing set keeps
        its `k`. A version that changes only the MIC table, or only a zone, moves `k`.
      - The engineer's track moving the code to 1.15 today asked me to confirm its reading
        (`src/marketdata/profiles.py`, working tree). **Confirmed: `market-data/1.15#profiles/4`.**
      - The `alphavantage.cn` profile entered the code (commit `f42efa0`) under
        `market-data/1.14#profiles/3`, the id that before denoted a set without it. That was the
        defect: content changed with no version change. Counter 4 is that content's own id.
      - **Why 1.16 takes 5.** Its content changes are:
        - the `call_adjustment` entry of `alphavantage.us` and `alphavantage.cn` for `TIME_SERIES_DAILY`
          gains its status `DECLARED` and the reference PD-0066 decision 3 as data (item 23). Today the
          status is not profile data: `daily_csv.py` hard-codes `:MEMORY`;
        - the MIC → market table gains ARCX, BATS and XASE as US (item 27); A.1 lists them only in a
          comment, so the table is the content;
        - the exchange-zone table gains their zone (Ruling 2.2 item 1).

        The `alphavantage.cn` mapping basis (now the owner's reading, PD-0066 decision 3) changes only a
        comment; its status `DECLARED` is unchanged. It does not by itself move `k`.
      - A filing profile (Ruling 4.7 item 6) is profile content: the version that adds the first one
        moves `k`.
    - **Rule for the A.6 table id (fix round 2, reviews L-3 and R2-C4).** The A.6 id is
      `market-data/<version that introduced its content>#a6/<k>`, where `k` counts A.6 content changes
      (codes, statuses, references and the composite-code table; comments are not content).
      - It names the introducing version, not the governing set, because the id is stamped into
        identifier provenance (`…;market-data/1.5#a6/1`), which persists on identity rows across code
        versions. An identity row asserted under unchanged A.6 content must keep the id it was asserted
        with. The profile-set id appears only in manifests of the running set, so it carries the
        governing set.
      - Under 1.15 code, `market-data/1.5#a6/1` (`exchange_codes.py`) **conforms**: the A.6 content has
        not changed since 1.5.
      - Under 1.16, the `UW` status moves `MEMORY` → `OBSERVED`, so the content changes and the id is
        **`market-data/1.16#a6/2`**.
      - The draft said A.6 follows "the same rule" as the profile set. That was wrong for this table;
        this bullet replaces it.
33. **Baselines.** Re-record every test pin and baseline the changes move, each with its stated
    reason. These include:
    - the V0 duplicate-date pin;
    - the CN-only `enforce_delivered_dp` and `refuse_duplicate_dates` defaults;
    - the G2-c lineage;
    - `listing_market_refusal("alphavantage.us", "ARCX")`, which stays `None` because ARCX is now US
      and the source is admitted for US;
    - the byte-identity baseline;
    - **(1.16 fix round, review C-7)** the label-source string pins
      (`test_marketdata_cp2c2_conventions13.py`, and `test_marketdata_alphavantage_cn.py` for both
      routes), and any digest taken over the canonical lineage of the cp3 and cp4 golden runs. They
      move from `:MEMORY` to `:DECLARED`. No number, state, reason code or `FIXTURE_PINS` entry moves;
    - **(fix round 2, review L-4)** the ECB adapter pin
      `test_marketdata_cp2c1_adapters.py` "a duplicate date is reported and the first row wins" (around
      line 182). Under item 34 no row wins: the file's currency series are excluded whole. The reason
      to record is Test V0-FX (1.16);
    - **(fix round 2, review R2-C7)** the registry copies and their pins under item 35: the byte
      copies in `src/` (`risk/risk_registry.json`, `diversification/diversification_registry.json`,
      `product_contract/performance_methodology_registry.json`), the ids the loaders accept, and the
      tests that compare them with `methodology/registry/` (for example
      `test_risk_registry_matches_methodology.py`, `test_performance_methodology_registry.py`,
      `test_diversification_golden.py`, `test_marketdata_version_label.py`). The reason to record is
      the re-issue, not a method change.

    Before the change, re-check that no stored real release is affected (as for PD-0067
    decision 6).
34. **(fix round 2, review L-4) Test V0-FX for a fixing date stated twice** (§3, Test V0-FX (1.16)).
    - Key: the parsed fixing date, within one FX file. Unit: every currency series read from that file.
    - Two or more rows with one fixing date exclude **every** currency series of the file, whole,
      with lineage cause `V0_FX_DUPLICATE_DATE` naming the date. Inside and outside calendar coverage
      alike. No row is kept, whether or not the rows agree.
    - The ECB adapter's "row not read" (`ecb_eurofxref.py`, first row wins) is replaced.
    - Tests (synthetic ECB files):
      - 2025-01-02 listed twice, USD 1.08 then 9.99: no USD rate, and no rate of any other currency
        of the file, for any date; lineage names `V0_FX_DUPLICATE_DATE` and 2025-01-02;
      - the same with both rows equal (1.08 and 1.08): the same exclusion, since the rule judges the
        file, not the values;
      - a file with one row per date is unaffected.
    - No fixture moves: every fixture FX file is written one row per fixing date.
35. **(fix round 2, review R2-C7) The registries are re-issued with every label move.**
    - **Rule.** A PRD §33 registry's `implementation_version` names the labels the code runs, not
      minimums (`risk` Ruling 9.2 (1.10)). A registry file is never edited after its id is issued. So
      every move of the market-data label is preceded by a re-issue, under new ids, of every registry
      that names a market-data version, and the code's byte copies follow in the same increment as the
      label.
    - **Done for 1.15, today (2026-10-24):**

      | New file (`methodology/registry/`) | New id | Cites |
      |---|---|---|
      | `RISK_1.10_REGISTRY.json` | `risk/1.10` | `market-data/1.15` |
      | `PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json` | `appendix_id` `performance-registry/1.1` (`registry_id` stays `performance/1.12`) | `market-data/1.15` |
      | `DIVERSIFICATION_1.1_REGISTRY.json` | `diversification/1.1` | `market-data/1.15` (and `risk/1.10`) |

      The changed fields are listed in `CP4_RISK_CONVENTIONS.md` (change note 1.9 → 1.10),
      `CP3_REGISTRY_APPENDIX_INVENTORY.md` (appendix re-issue 1.1) and
      `CP5_DIVERSIFICATION_CONVENTIONS.md` (change note 1.0 → 1.1). The engineer's part: the byte
      copies, the ids the loaders accept, and the pins of item 33.
    - **For 1.16**, before a manifest cites it: the same three are re-issued again, citing
      `market-data/1.16`. The ids I expect are `risk/1.11`, `performance-registry/1.2` and
      `diversification/1.2`, but they are fixed only when written. `INSIGHTS_1.0` names no market-data
      version and is not affected.
    - A registry id never names market-data 1.16 while the code runs 1.15, and the reverse.

**Must not decide:**

- any rounding of a converted amount or of a rate (OI-8; CP3);
- any display precision;
- any tolerance, band, threshold or fixing other than those stated here;
- which value wins a disagreement (only a resolution record does);
- a CNH proxy;
- interpolation, look-ahead or next-day fixings;
- carry-forward beyond Ruling 1.6;
- sibling-listing price substitution;
- any F8-B behaviour beyond PD-0030 §2 and Ruling 6.4;
- further reason codes, or reusing a code for an outcome the Ruling 4.4 table assigns
  elsewhere;
- which adjusted series a return metric uses (CP3/CP4); and never a `SUBTRACTIVE` vendor series
  as a return input (Ruling 2.5);
- dividend automation;
- (1.1) a tick or decimal rule, a volume unit, or an upstream grouping that is not in Appendix
  A. A missing profile **fails closed**: the file is not admitted until the profile exists;
- (1.1) rounding a float rendering to a fixed number of decimals in place of Ruling 2.4's
  shortest round-trip;
- (1.15) a meaning for any undocumented corporate-action field, or a `SPLIT` type for any record,
  without a grant in a market-data version (Ruling 7.4);
- (1.15) an ex-date derived from a record or payable date by an offset;
- (1.15) a coverage interval for an empty response;
- (1.15) admitting `alphavantage.cn`, or any CN source, or adding to A.5. That needs an owner PD.
- (1.16) treating `DECLARED` as `VERIFIED`, or raising any label status from the owner's
  documentation reading;
- (1.16) moving any other A.6 entry to `OBSERVED` or `CONFIRMED` without a file or a recorded human
  check (`UQ`, `UR`, `UN`, `UP`, `UF`, `UA`, `CG`, `CS`, `CH`);
- (1.16) a calendar for ARCX, BATS or XASE, or adding them to the registered NYSE calendar's
  `applies_to`, or extending any calendar past 2026-12-31. Each is a new calendar version that the
  owner checks (Ruling 5.3 item 8);
- (1.16) a reason code for an admission refusal, or showing a gate label as a data condition;
- (1.16) any use of volume magnitude, or a correction for after-hours volume (MD-OI-19);
- (1.16) a market for a MIC outside the Ruling 4.7 item 6 table;
- (1.16) a default for `personal_holdings` or `ledger_origin`, or a `state_kind` other than `ACTUAL`
  for a recorded ledger;
- (1.16 fix round, review C-4) a rule that picks one of two manifests of one payload by name, order
  or time, or a change to the `FileStore.index()` refusal, unless the PM has scheduled the design
  change of Ruling 7.3 item 9. **(Fix round 2)** The move route was taken, so this refusal stays as the
  guard for any later pair;
- (fix round 2, review L-4) keeping one of two FX rows for one fixing date, by order or by value
  (Test V0-FX (1.16));
- (fix round 2, review R2-C5) a markets field in `SOURCES.json` for a filing source. Its markets go in
  its Appendix A.3 filing profile (Ruling 4.7 item 6);
- (fix round 2, review R2-C7) editing a registry file after its id is issued, or a registry that
  names a market-data version other than the one the code runs (§11 item 35);
- (1.16 fix round, review C-3) a multi-version profile set, or any other device, that lets a manifest
  citing an earlier convention set reproduce under later code; and running 1.16 behaviour under a
  1.15 label.

**(1.16) What this version leaves to the owner and the PM.** The Quant does not decide any of these:

- **The owner:**
  - admitting `alphavantage.cn` and setting A.5 CN (OP-1, after the Ruling 7A.3 (c) observations);
  - naming the A-share listings and approving each download (OP-4);
  - the terms readings for SEC EDGAR and cninfo, and confirming each filing record (OP-6);
  - whether the EDGAR look of Ruling 6.5 item 10 is required for HG4;
  - checking any new calendar version;
  - the HG4 gate itself;
  - correcting the X1 `valid_until` (PD-0066 decision 5; not a market-data matter);
  - ~~**(1.16 fix round)** which OpenFIGI manifest stays in the indexed data root, if the move route is
    taken.~~ **Done, 2026-10-24 (fix round 2).** The owner approved the move: `AAPL_UW.json` stays in
    the indexed store, as PD-0066 decision 9 preferred, and `AAPL_XNGS.json` and its manifest are kept,
    unchanged, under `data/marketdata/observations/openfigi/identity/2026-10-23/` (Ruling 7.3 item 9);
  - **(1.16 fix round)** whether to confirm §12 item 23 (XNGS is a segment of XNAS) from the ISO 10383
    list. The A.6 `UW` attachment rests on it;
  - **(1.16 fix round)** a new decision on `M` if the EDGAR look finds a hit (Ruling 6.5 item 10).
- **The designer:** the on-screen wording of the claim limits and of "not the owner's holding". The
  method requires only that none of them is dropped (P3).
- **The PM:**
  - the order of the 1.16 code increment relative to the F1 build R1 → R8. A result shown at HG4
    cites the version its manifest carries;
  - ~~**(1.16 fix round, review C-4)** before R4a or R8, routing the two OpenFIGI manifests of one
    payload.~~ **Done, 2026-10-24 (fix round 2):** routed to the owner's move, which was carried out.
    `FileStore.index()` on `data/marketdata` builds again (15 entries; Ruling 7.3 item 9). No design
    change is needed for this case;
  - **(fix round 2)** recording the move as a data action, in a PD or in `STATUS.md`: the date, the
    owner's approval, the two paths, and the unchanged hashes (payload `b2aaeb7b…889c3ccc`, manifest
    `cb4d862d…63c8d`). Ruling 7.3 item 9 cites the move; once recorded, the record is its authority,
    not this document;
  - **(fix round 2)** the stray `.claude/` directories under the data root (noted by the method
    re-review for `files/openfigi/identity/2026-10-23/.claude/.cc-writes`; on 2026-10-24 I also saw
    `data/marketdata/.claude`, `data/marketdata/files/.claude` and
    `data/marketdata/calendars/drafts/.claude`, all read only, holding no files). `FileStore` searches
    the `files/` tree for manifests. They hold none, so the index is unaffected, but a data root should
    hold only data. They are harness artefacts, not mine to remove;
  - **(fix round 2, §11 item 35)** sequencing the registry byte copies with the label track, and the
    1.16 re-issue before the 1.16 label move.

---

## 12. External facts used here, to be confirmed by the human at download

None of these is asserted as verified. Each was stated from knowledge without network access.

1. **ECB.** Concertation "around 14:10 CET" (1.8: as the ECB's page states, read by the main
   session on 2026-10-01 for PD-0034; 1.0–1.7 said 14:15 from memory), publication at about
   16:00 CET, quotes in units per 1 EUR, no publication on TARGET closing days.
   - Applied in 1.8: the `observed_at` constant is 14:10. No ordering in Ruling 1.2 changed.
     The owner confirms the wording when checking the ECB calendar draft.
2. **TARGET closing days.** 1 January, Good Friday, Easter Monday, 1 May, 25 and 26 December,
   and weekends.
3. **Exchange closes.** SSE and SZSE 15:00 with a 14:57–15:00 closing call auction; HKEX 16:00
   continuous trading, then the closing auction session to a random close at about 16:08–16:10
   (auction-eligible securities close at the auction price; others at a price taken from the
   last minute of continuous trading); NYSE and Nasdaq 16:00 ET. (1.8: the HKEX calendar's
   scheduled close is 16:10, Ruling 5.3 item 6.)
   - Half days: HKEX on some eves; US early closes at 13:00 ET.
   - HKEX severe-weather trading from late 2024.
   - **(1.16)** The SSE closing call auction applies to **shares**. For SSE **funds**, see item 24.
     Ruling 2.1 now defines the close by the exchange's publication under the rules in force, so no
     rule depends on the mechanism.
4. **PBOC band.** Onshore USD/CNY spot within ±2 % of the day's central parity. CFETS parity
   published at about 09:15 Beijing time.
5. **HKD peg.** Linked Exchange Rate System, convertibility band 7.75–7.85 HKD per USD.
6. **Free sources.**
   - yfinance `Close` is split-adjusted, and `Adj Close` is split- and dividend-adjusted
     (proportional).
   - Alpha Vantage's free `TIME_SERIES_DAILY` is documented as as-traded (raw). **(1.16) Confirmed by
     the owner's reading of the live page on 2026-10-24 (PD-0066 decision 3).** It is now a vendor
     declaration with status `DECLARED`, not a verification.
   - AKShare offers unadjusted, qfq and hfq series.
   - Frankfurter returns the previous fixing, under that fixing's own date, when asked for a
     non-fixing date. **Use the payload date, never the requested date.**
7. **Daily price limits** on A-shares: ±10 % on the main board, ±20 % on ChiNext and STAR.

**Added in 1.1.** These are all **from memory**; the human should confirm them from the cited
publisher. None is load-bearing for normalization, which uses shortest round-trip. They bound
the `max_dp` validation and the optional tick-grid check.

8. **US minimum price increment** (SEC Regulation NMS Rule 612, the "sub-penny rule"): quotes
   ≥ $1.00 in $0.01, and below $1.00 in $0.0001. Official closing prices of NYSE and Nasdaq
   listings are on that grid. Confirm whether any 2024–2026 amendment changed the tick for any
   tier. I recall a 2024 SEC proposal or adoption of a half-penny tick for some stocks, but I
   cannot confirm its status or effective date.
9. **HKEX spread table** (Part A, equities), as I recall the long-standing version:

   | Price band (HK$) | Tick (HK$) |
   |---|---|
   | 0.01–0.25 | 0.001 |
   | 0.25–0.50 | 0.005 |
   | 0.50–10 | 0.01 |
   | 10–20 | 0.02 |
   | 20–100 | 0.05 |
   | 100–200 | 0.1 |
   | 200–500 | 0.2 |
   | 500–1,000 | 0.5 |
   | 1,000–2,000 | 1 |
   | 2,000–5,000 | 2 |
   | 5,000–9,995 | 5 |

   HKEX has since reduced the spreads in some bands, in phases around 2024–2025. I do not
   reliably remember which bands or dates. **Confirm the table and its effective dates from
   HKEX.** Part B, for ETFs and debt securities, has smaller ticks. The probe's 00700 closes
   (469.4, 474.2, 439.6, 429.2, 476.0) are all multiples of 0.2, which is consistent with the
   200–500 band.
10. **SSE/SZSE ticks:** A-shares CNY 0.01; funds (ETFs, LOFs) and bonds CNY 0.001; SSE B-shares
    USD 0.001; SZSE B-shares HKD 0.01. Confirm from the exchanges' trading rules.
11. **A-share trading unit:** buy orders in lots of 100 shares (1 手), which is the unit
    Eastmoney's volume uses (observed, Ruling 2.6). STAR Market buy orders have a 200-share
    minimum. That does not change the volume unit, but confirm it.
12. **The ex-rights reference price formula** of SSE/SZSE:
    `(prev close − cash per share + rights price × rights ratio) / (1 + share ratio)`. This is
    the form behind Eastmoney's subtractive 前复权, which the probe confirms in one window only
    (Example 3-C).
13. **Upstreams of the AKShare functions in use.** I take these from the function and source
    names in the manifests, not from AKShare's code, which I have not read:
    - `stock_zh_a_hist`, `stock_hk_hist` and `stock_us_hist` reach Eastmoney;
    - `stock_zh_a_daily`, `stock_hk_daily` and `stock_us_daily` reach Sina.

    The engineer should confirm each function's upstream from the AKShare source at the pinned
    version and record it in the profile.

**Added in 1.15.** These are all MEMORY unless marked otherwise. None of them is used as a fact by
any rule here: each one either grants nothing or is a refusal-only or flag-only input.

14. **Alpha Vantage `SPLITS` field names.** My recollection is `effective_date` and `split_factor`,
    in a JSON object with `symbol` and a `data` list. **They grant nothing** (Ruling 7.4 item 6).
15. **AAPL's 2020 split**, from the 8-K of about 2020-07-30:
    - four-for-one;
    - holders of record at the close on 2020-08-24;
    - shares distributed after the close on 2020-08-28;
    - split-adjusted trading from 2020-08-31.

    Confirm from the filing before O-2 relies on it. The CP7 E8 sample (EODHD) matched a 4:1 event
    on 2020-08-31. That is another vendor, so it confirms no Alpha Vantage field.
16. **Alpha Vantage non-data bodies:**
    - JSON with a `Note` key (rate limit), an `Information` key (limits or premium-only), or an
      `Error Message` key (invalid call);
    - `{}` for some invalid calls.

    Ruling 7.5 item 5 does not depend on these exact keys.
17. **A-share code ranges:**
    - SSE: A-shares 600, 601, 603 and 605; STAR 688 and 689; funds and ETFs 5xxxxx; B-shares 900.
    - SZSE: main board 000–003; ChiNext 300 and 301; funds and ETFs 15xxxx and 16xxxx; B-shares
      200.

    Used `FLAG_ONLY` (Ruling 7A.1 item 5).
18. **Alpha Vantage's documentation shows `.SHH` and `.SHZ` symbols.** The session read this for
    PD-0063, through a page summarizer, not as a human confirmation. Confirm the page, and whether
    its "raw (as-traded)" statement for `TIME_SERIES_DAILY` covers these symbols (OP-5).
    **(1.16) Confirmed by the owner on 2026-10-24** (".SHH/.SHZ shown as supported"; PD-0066 decision 3).
    The raw statement is the call's, and the call documents these symbols. The terms PDF version
    and the rest of the page were not re-checked (PD-0066).
19. **US ex-date practice for stock distributions:**
    - 25 % or more: ex-date is the first business day after the payable date (due bills);
    - under 25 %: ex-date is before the record date (regular way).

    Data vendors' overnight batches may apply the next session's ex-date before it opens. That is
    why `N(R)` in Ruling 3.2 item 3 includes it.
20. **SSE index codes in the 000xxx range** (for example the SSE Composite, `000001`) overlap SZSE
    share codes.
21. **A-share 权益分派.** The 股权登记日 is the session before the 除权除息日, and 转增 shares are
    listed from the ex-date. Many CN data vendors serve 前复权 series by default.
22. **Exchange sites' terms** (SSE, SZSE, Nasdaq) for a human noting a single published close as a
    Test V4 reference: not read.

**Added in 1.16.** These are MEMORY or a search summary, as marked. The draft said none is used as a
fact by any rule. That was wrong for one item (1.16 fix round, review L-4):

- **Item 23's first point is used permissively.** "XNGS is a segment of XNAS" is the link on which
  the A.6 `UW` → XNAS entry rests. So the attachment of `BBG000B9Y5X2` to AAPL's XNAS listing rests on
  it too (Ruling 7.3 items 8 and 9).
  - Its consequence is confined to the identity attribute `Listing.figi`, which has no role in a
    valuation.
  - The owner may confirm it from the ISO 10383 list (§11, "What this version leaves").
- **Item 23's second point and item 25 map ARCX, BATS and XASE to US** at the gate (Ruling 4.7 item 6).
  A reading there can then pass the gate. No value can be `AVAILABLE` until a checked calendar names
  those MICs (MD-OI-20), so no number rests on them.
- **The others** are descriptive, flag-only or refusal-only inputs.

23. **ISO 10383 MICs (MEMORY).**
    - XNGS (Nasdaq Global Select), XNMS (Nasdaq Global Market) and XNCM (Nasdaq Capital Market) are
      segment MICs of the operating MIC XNAS.
    - ARCX is NYSE Arca, BATS is Cboe BZX, XASE is NYSE American, and BJSE is the Beijing Stock
      Exchange.
    - XSSC and XSEC are the Stock Connect segment MICs of Shanghai and Shenzhen.

    The A.6 `UW` entry rests on the first point (Ruling 7.3 item 8). Confirm it from the ISO 10383
    list.
24. **SSE 2026 trading-rules revision (search summary only; `reviews/CN_CALENDAR_CHECK_PACKET.md`).**
    - It was announced 2026-04-24, and is said to be effective 2026-07-06.
    - It extends after-hours fixed-price trading (15:05–15:30) from STAR shares to all A-shares and
      ETFs.
    - It moves SSE funds to a closing call auction.

    **From MEMORY:**
    - before the revision, an SSE fund's close was the volume-weighted average price of the last
      minute of trading, including the last trade;
    - SSE shares have had the 14:57–15:00 closing call auction since August 2018;
    - a stock with no trade in a session closes at its previous close.

    Confirm from the rule text. Ruling 2.1 does not depend on any of it.
25. **US venues (MEMORY).**
    - NYSE Arca, Cboe BZX and NYSE American follow the NYSE holiday and early-close schedule, close
      at 16:00 ET, and run closing auctions for their own listings.
    - Many US ETFs have their primary listing on NYSE Arca.

    A calendar version naming them needs the owner's check.
26. **OpenFIGI `micCode` semantics (OBSERVED for AAPL only).**
    - The filter accepts the segment MIC XNGS and returned nothing for the operating MIC XNAS
      (Ruling 7.3 item 8).
    - Whether this holds for every Nasdaq tier, or for NYSE (`XNYS` has no segment split in my
      recollection; MEMORY), is unobserved.

## 13. Open issues

- **MD-OI-1 (CP3; closed in 1.8).** The valuation cutoff instant must be compatible with the
  date-label bundle of Ruling 2.2 (5), together with `ledger-replay/1.3` OI-2. Ruled in
  `performance/1.0` Ruling 1.7.
- **MD-OI-2 (CP3; closed in 1.8).** OI-8 is a blocker for any reporting-currency value (§8).
  Ruled in `performance/1.0` §2.
- **MD-OI-3 (CP3/CP4).** Which adjusted series, or which engine-derived adjustment, each return
  metric uses. The recommendation of Ruling 2.3 stands until then.
- **MD-OI-4 (CP3; closed in 1.8).** How the excluded weight of an aggregate (HG1 round 4 §6 R1) is measured
  when the excluded input is a position whose price is in `DISAGREEMENT`. Ruled in
  `performance/1.0` Ruling 1.4: it cannot be measured, so the aggregate is `INSUFFICIENT_DATA` +
  `SOURCE_CONFLICT`.
- **MD-OI-5 (OQ-04b).** The launch fixing (WM/R or another), a CNH source, and live FX. Each
  is a new convention version.
- **MD-OI-6 (CP4).** The benchmark leg must use this same ECB fixing, or the comparability
  problem of HG1 round 4 §5.2 becomes permanent.
- **MD-OI-7 (fixtures).** A CP2 golden fixture with hand-derived values can be written from
  Examples 1-A, 1-B, 2-A, 3-A, 3-B, 4-A, 5-A and 6-A once the engineer's file formats exist. I
  have not written one here, because it needs those formats. **(1.1)** The formats now exist
  (`finweb.marketdata.file_manifest/1`). Example 3-C is a real-file case ready for it.
- **MD-OI-8 (1.1; closed in 1.2).** `alphavantage.us` is profiled (Example A-1). The AKShare
  routes are refused (PD-0031/0032), so they will not be profiled. Any newly admitted source is
  profiled by A.4 before use. The 1.1 text read: the Sina-backed CN function, the Eastmoney
  HK/US functions and Alpha Vantage have no observed profile yet.
- **MD-OI-10 (1.2; owner, STATUS 17).** Real CN and HK prices. Until a source is admitted, every
  CN and HK valuation is `MISSING_PRICE_HISTORY` (Ruling 4.7). This changes no method.
- **MD-OI-11 (1.2; CP3).** Whether a "value of priced holdings" metric, with an unpriced-holding
  count, exists beside the total (Ruling 4.7 item 3). **(1.8)** Put to the owner as OD-P2 in
  `performance/1.0` §15.
- **MD-OI-12 (1.2).** Ruling 1.1a's provenance check needs an ECB-direct file, and so a terms
  attestation by the owner for `ecb.eurofxref`. Each gets one from its first real file, by the rule of
  Appendix A §A.4, before it is admitted.
- **MD-OI-9 (1.1).** The 600519 event check of Example 3-C: the sum of corroborated cash per
  share with ex-dates in (2025-01-08, 2026-10-01] must equal 79.58. It needs the
  corporate-action files.
- **MD-OI-13 (1.15; engineer).** Test V1 and Test V3 are not built (`src/marketdata/market11.py`).
  Ruling 3.2 item 4 waits on V1, and the interim pre-run refusal of item 6 applies until then.
- **MD-OI-14 (1.15; owner OP-1, OP-4).** `alphavantage.cn` is pending observation (Ruling 7A.3).
  Until it is admitted, CN stays `NO_ADMITTED_SOURCE`.
  - **(1.16)** 7A.3 (a) and (b) are met. The intended order is `[alphavantage]`, and the observation
    plan is approved. Still open: the listings, each download, the A-share `fetch` route, the (c)
    observations, (d), and the owner's admission decision.
- **MD-OI-15 (1.15; owner OP-3).** The Alpha Vantage `SPLITS` grant needs O-1 to O-3 (Ruling 7.4).
  Until then, no US feed role holds a usable record, and nothing can be `CORROBORATED` for real US
  data.
  - **(1.16) Deferred** by the owner (PD-0067 decision 5).
- **MD-OI-16 (1.15; owner OP-6).** The filing-role sources (SEC EDGAR, cninfo) need registration and
  terms checks. Filing records need a human preparer or confirmer (Ruling 7.6 item 2).
  - **(1.16) Decided** (PD-0067 decision 4): an agent drafts each record from owner-supplied text, and
    the owner confirms it.
  - **Open:** the owner's terms readings, and the entries. Each entry declares the markets it covers
    (Ruling 4.7 item 6).
- **MD-OI-17 (1.15).** Dividend-component exposure stays a disclosed residual with no state effect
  (Ruling 3.2 item 4), for US and for an admitted CN route. Revisit when a dividend-verifying
  reference is routinely available: V4 records, or an adjusted series from the same upstream for
  V2.
- **MD-OI-18 (1.15; owner OP-5).** The `RAW` documentation of `TIME_SERIES_DAILY` has not been
  confirmed by a human, so the label source stays `MEMORY` (§9B item 4 (d)).
  - **(1.16) Closed.** The owner's reading (PD-0066 decision 3) makes the source `DECLARED`. The label
    status remains `UNVERIFIABLE`. That part is not an open issue but the stated residual of Rulings
    3.2 and 6.5.
- **MD-OI-19 (1.16).** Whether a vendor's daily volume for an SSE listing includes the after-hours
  fixed-price session (Ruling 2.1).
  - The print rule needs only volume > 0, so the effect is confined to one edge case. A share or ETF
    with no trade in the regular session, but with after-hours trades, would count as a print at a
    close carried from the previous session (MEMORY, §12 item 24). That would understate staleness
    by one session.
  - Observe it when a V4 record states the exchange's volume (Ruling 7A.3 (c) 7). No rule changes
    until then.
- **MD-OI-20 (1.16).** No registered calendar governs ARCX, BATS or XASE. A V1 listing there (most
  plausibly a US ETF on NYSE Arca) stays `FRESHNESS_UNKNOWN` until a calendar version naming those
  MICs is checked and registered by the owner (Ruling 2.2 item 1; §12 item 25).
- **MD-OI-21 (1.16 fix round, review L-2).** Rulings 3.2 item 3 and 3.3 reason under backward
  adjustment: `SPLIT_ADJUSTED`, and anchor `LATEST`.
  - A series adjusted with anchor `EARLIEST` (hfq) and mislabelled `RAW` differs at `d_p` through
    events on or before `d_p`. Those lie outside every exposure window.
  - V1 on a decisive split in the file window would show it, as would V4 on a date after such an
    event. Otherwise it is a residual of the `UNVERIFIABLE` label (Ruling 6.5 N-1 to N-3).
  - No rule changes. Revisit when V4 is built.

---

## Appendix A (1.1, updated in 1.2): Precision, unit and upstream profiles, as data

**Status key:**

- `OBSERVED`: established from the probe files of 2026-10-01 by the tests stated;
- `DECLARED`: a convention set here;
- `MEMORY`: stated from my knowledge, and to be confirmed by the human (§12);
- `TO_OBSERVE`: no file yet. The source is not admitted until its profile is filled by §A.4.

The engineer transcribes this into a versioned profile file. The transcription carries this
document's convention ID and its own profile version.

### A.1 Markets

```yaml
markets:
  CN:   # XSHG, XSHE
    price_max_dp:                       # validation bound of Ruling 2.4 item 4
      A_SHARE: 2                        # MEMORY (§12 item 10); OBSERVED-consistent: 1324.49, 1267.01
      FUND_ETF_LOF_BOND: 3              # MEMORY (§12 item 10)
      B_SHARE_SSE: 3                    # MEMORY
      B_SHARE_SZSE: 2                   # MEMORY
    tick_table: { status: MEMORY, use: FLAG_ONLY }      # §12 item 10; never used to normalize
    volume_unit_note: "board lot 100 shares (MEMORY, §12 item 11)"
  HK:   # XHKG
    price_max_dp: 3                     # grid-free bound covering every band of the spread table
                                        # (smallest tick 0.001); MEMORY-derived, conservative
    tick_table: { status: MEMORY, effective_dates: TO_CONFIRM, use: FLAG_ONLY }   # §12 item 9
  US:   # XNYS, XNAS; (1.16) also ARCX, BATS, XASE (Ruling 4.7 item 6), with no calendar governing them yet
    price_max_dp:
      - { price_at_least: "1.00", max_dp: 2 }    # MEMORY (§12 item 8, Rule 612)
      - { price_below:    "1.00", max_dp: 4 }    # MEMORY
    tick_table: { status: MEMORY, use: FLAG_ONLY }
```

**CN security class (1.4).** The class is derived deterministically from the identity record:
MIC, `SecurityType` (V1 has only `COMMON_STOCK` and `ETF`) and the listing's
`trading_currency`. It never comes from a request.

| MIC | `SecurityType` | `trading_currency` | Class | `max_dp` |
|---|---|---|---|---|
| XSHG or XSHE | `COMMON_STOCK` | CNY | `A_SHARE` | 2 |
| XSHG or XSHE | `ETF` | CNY | `FUND_ETF_LOF_BOND` | 3 |
| XSHG | `COMMON_STOCK` | USD | `B_SHARE_SSE` | 3 |
| XSHE | `COMMON_STOCK` | HKD | `B_SHARE_SZSE` | 2 |
| any other combination | | | none | strict 2, flagged `SECURITY_CLASS_UNRESOLVED` |

- B-shares need no blanket refusal. Their trading currency identifies them.
- A B-share price in CNY is already refused at ingest by currency mismatch (Ruling 4.1a).
- LOFs and bond funds are not V1 instruments (`SecurityType` excludes mutual funds, PRD §5.3).
  An `ETF` row covers listed ETFs only.
- The strict default is safe because it can only **refuse** a valid 3-dp price; it can never
  accept an off-grid one.
  - **(1.16, review F-6 (c))** That is true **relative to the class table**: an unknown class gets
    the stricter of the two values.
  - The MEMORY tick values themselves are refusal-only only if they are not looser than the
    exchanges' true grids (Ruling 7A.2, 1.16).
- The tick values are **MEMORY** (§12 item 10).
- No CN source is admitted today, so this is not exercised yet.

`price_max_dp` applies to the **close** (the only valuation field). Open, high and low are used
only in the Ruling 4.6 row check and are not validated against it: US highs and lows can carry
sub-penny prints, e.g. `231.8201` in the probe.

### A.2 Float32 recoverability thresholds (exact arithmetic, not memory)

For a float32 field with `ulp(v) = 2^(⌊log2 v⌋ − 23)`, a grid of `10^(−dp)` is recoverable iff
`ulp(v) < 10^(−dp)`.

```yaml
float32_recoverable_below:
  dp_2: "131072"   # ulp on [65536,131072) = 2^-7 = 0.0078125 < 0.01; on [131072,262144) = 0.015625
  dp_3: "16384"    # ulp on [8192,16384)   = 2^-10 ≈ 0.000977 < 0.001
  dp_4: "1024"     # ulp on [512,1024)     = 2^-14 ≈ 0.000061 < 0.0001
```

Above a threshold, the value is unrecovered. Its bound is `½ ulp(v)`, and it corroborates only.

### A.3 Sources

**Admission (1.2, PD-0031/0032).** Only `alphavantage.us`, `frankfurter.ecb` and `openfigi`
are admitted. Every `akshare.*` and `akshare_sina.*` entry below is **`REFUSED`**: its observed
format is kept as a parser record, but no file from it is ever a reading (Ruling 4.7, item 1).
`baostock.cn` is unattested and refused.

```yaml
sources:
  - source_id: akshare.cn                    # REFUSED (PD-0031/0032): Eastmoney terms
    upstream: eastmoney                      # DECLARED from function name (§12 item 13)
    library: akshare (version from manifest)
    function: stock_zh_a_hist
    markets: [CN]
    payload_format: akshare_csv_cn_daily/1
    fields:
      开盘|收盘|最高|最低: { format: FLOAT64, delivered_dp: 2, status: OBSERVED }
                         # "1288.0", "1324.49"; no float32 signature; delivered_dp 2 = max observed (A.4 item 7, 1.5)
      成交量: { format: FLOAT64, integral: true, unit: LOT_100, shares_per_unit: 100,
               status: OBSERVED }   # median turnover/(close*vol) = 100.3 over 5 rows
      成交额: { format: FLOAT64, currency: CNY, use: UNIT_CHECK_ONLY, status: OBSERVED }
      涨跌额: { use: CHECK_ONLY_RULE_4_6 }
      涨跌幅|振幅|换手率: { use: NOT_INGESTED }
    adjust_param:
      "": RAW
      qfq: { adjustment_status: DIVIDEND_ADJUSTED, method: SUBTRACTIVE, anchor: LATEST,
             adjusted_dp: 2, status: OBSERVED_ONE_WINDOW }   # Example 3-C; re-run V2 on every file;
                                                             # adjusted_dp 2 = max observed ("1244.91")
      hfq: { status: TO_OBSERVE }           # expected SUBTRACTIVE/EARLIEST; verify by V2, never assume

  - source_id: akshare_sina.hk               # REFUSED (PD-0031/0032): Sina terms
    upstream: sina
    function: stock_hk_daily
    markets: [HK]
    payload_format: akshare_sina_csv_hk_daily/1
    fields:
      close: { format: FLOAT32, status: OBSERVED }      # "474.20001" -> 474.2, "469.39999" -> 469.4
      open|high|low: { format: FLOAT32, status: DECLARED }
                     # data consistent with either format ("473.6" is its own float32 shortest form);
                     # FLOAT32 is the safe declaration for grid prices of <= 6 significant digits
      volume: { format: FLOAT64, integral: true, unit: SHARE, shares_per_unit: 1, status: OBSERVED }
              # 150000004 mod 16 = 4 on [2^27, 2^28): not float32; median turnover ratio 1.0045 over 5 rows
      amount: { format: FLOAT64, currency: HKD, use: UNIT_CHECK_ONLY, status: OBSERVED }
    adjust_param: { raw: RAW }

  - source_id: akshare_sina.us               # REFUSED (PD-0031/0032): Sina terms
    upstream: sina
    function: stock_us_daily
    markets: [US]
    payload_format: akshare_sina_csv_us_daily/1
    fields:
      open|high|low|close: { format: FLOAT64, delivered_dp: 4, status: OBSERVED }
                           # "233.85" (float32 would print 233.85001); delivered_dp 4 = max observed ("231.8201", 1.5)
      volume: { format: FLOAT64, integral: true, unit: SHARE, shares_per_unit: 1,
                status: DECLARED_UNVERIFIED }   # no turnover column, so the Ruling 2.6 check cannot run
    adjust_param: { raw: RAW }

  - source_id: akshare_sina.cn            # REFUSED (PD-0031/0032); never profiled
    upstream: sina

  - source_id: akshare.hk / akshare.us   # REFUSED (PD-0031/0032); never profiled
    upstream: eastmoney

  - source_id: alphavantage.us            # ADMITTED (PD-0032); profile OBSERVED 1.2 (Example A-1)
    upstream: alphavantage                # direct API, no wrapper library (manifest "libraries": [])
    independence_group: alphavantage      # its own upstream suppliers are not disclosed to us;
                                          # the only admitted US upstream, so independence is moot today
    function: TIME_SERIES_DAILY           # free tier; outputsize=compact gives the last 100 sessions
    markets: [US]
    payload_format: alphavantage_csv_daily/1
    row_order: DESCENDING_BY_DATE         # OBSERVED; the parser sorts and never assumes an order
    fields:
      timestamp: { meaning: SESSION_DATE_LOCAL_LABEL, status: OBSERVED }   # a date, not an instant (Ruling 2.2)
      close: { format: TEXT_DECIMAL, delivered_dp: 4, grid_check: US price_max_dp,
               status: OBSERVED }   # 100/100 closes on the cent grid ("<redacted vendor value>"), so recovered, δ = 0
      open|high|low: { format: TEXT_DECIMAL, delivered_dp: 4, grid_check: NONE,
                       status: OBSERVED }   # 47 of 300 values off the cent grid (sub-penny, e.g. "100.1401");
                                            # used only in the Ruling 4.6 row check
      volume: { format: TEXT_DECIMAL, integral: true, unit: SHARE, shares_per_unit: 1,
                status: DECLARED_UNVERIFIED }   # integer text; no turnover column, so Ruling 2.6 cannot run
    adjustment:
      declared_by_source: RAW             # AV documents TIME_SERIES_DAILY as "raw (as-traded)"; basis MEMORY through 1.15,
                                          # DECLARED from 1.16 (label_source_status below; 1.16 fix round, review L-4)
      # (1.16) DECLARED: the owner's reading of the live documentation, 2026-10-24, "raw as traded" (PD-0066
      # decision 3; section 9B item 4 (d)). A vendor declaration, NOT a verification: no V1 event, no V4 record.
      label_source_status: DECLARED       # lineage: PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED
      manifest_declared: UNDECLARED
      label_status: UNVERIFIABLE          # V1: no decisive split in the window; V2/V3: no admitted reference
      # (1.15) the 1.2 line `split_component_moot_if` is WITHDRAWN: absence of a split cannot be shown with the
      # admitted sources (Ruling 3.1 consequences, 1.15 note). In its place:
      split_exposure: "Ruling 3.2 item 4: a filing-role SPLIT with ex-date in E(d_p, R) withholds the reading unless V1/V4 established RAW for it"
      dividend_component: UNVERIFIABLE    # residual risk recorded: a dividend-adjusted series would
                                          # differ from raw by about one quarterly yield before each ex-date
                                          # (1.15: DIVIDEND_LABEL_EXPOSED in lineage, no state effect; MD-OI-17)

  - source_id: alphavantage.us.splits     # (1.15) id illustrative. Corporate-action FEED candidate. NO GRANT (Ruling 7.4)
    upstream: alphavantage
    kind: CORPORATE_ACTION
    function: SPLITS                      # free tier; fields undocumented in prose (HG4 data-source check)
    fields: { status: TO_OBSERVE }        # MEMORY names effective_date / split_factor (§12 item 14) grant nothing
    records_output: UNMAPPED_ACTION       # every record, until O-1..O-3 are observed and granted in a new version
    empty_response: NOT_CLASSIFIABLE_UNTIL_O1   # Ruling 7.5 item 5; then EMPTY_RESPONSE, coverage NOT_ESTABLISHED
    role: FEED                            # in the confirmation policy only once granted; filing role: SEC EDGAR (Ruling 7.6)

  - source_id: alphavantage.cn            # (1.15) PENDING OBSERVATION, NOT ADMITTED (Ruling 7A.3). Terms: PD-0063/PD-0064 reading
    upstream: alphavantage
    independence_group: alphavantage      # the same upstream as alphavantage.us
    function: TIME_SERIES_DAILY           # compact = last 100 sessions; 25 requests/day shared with US
    markets: [CN]
    payload_format: alphavantage_csv_daily/1   # ASSUMED from the US route; confirmed or replaced by A.4 item 1
    vendor_id:
      grammar: "six ASCII digits, '.', then SHH or SHZ (upper case)"     # Ruling 7A.1 item 1
      suffix_to_mic: { SHH: XSHG, SHZ: XSHE }   # DECLARED from AV documentation as read for PD-0063 (§12 item 18)
                                                # (1.16) basis: the owner's reading, 2026-10-24 (PD-0066 decision 3);
                                                # 1.15's basis was a summarizer read (review F-6 (a))
      code_range_check: FLAG_ONLY               # MEMORY, §12 item 17
      scope: [A_SHARE, FUND_ETF_LOF_BOND]       # CNY only; B-shares out of route (Ruling 7A.1 item 7)
    status: TO_OBSERVE
    fields:                               # PROVISIONAL_UNOBSERVED: synthetic tests only (Ruling 7A.3 item 2); replaced by A.4
      open|high|low: { format: TEXT_DECIMAL, delivered_dp: 4, grid_check: NONE, status: PROVISIONAL_UNOBSERVED }
      close: { format: TEXT_DECIMAL, delivered_dp: 4, grid_check: "CN price_max_dp by class (A.1)",
               status: PROVISIONAL_UNOBSERVED }
      volume: { format: TEXT_DECIMAL, integral: true, unit: SHARE, shares_per_unit: 1,
                status: PROVISIONAL_UNOBSERVED }   # unit 股 vs 手 unknown; no magnitude rule uses it (Ruling 2.6)
    adjustment:
      declared_by_source: RAW             # the TIME_SERIES_DAILY documentation; basis DECLARED from 1.16 (below; OP-5 done)
      label_source_status: DECLARED       # (1.16) the same reading (PD-0066 decision 3): the call's raw statement, with .SHH/.SHZ
                                          # documented on that call. Relaxes nothing below.
      admission_requires: "Ruling 7A.3 (c) 5: V4 (or V1) establishes RAW for a cash and a share event"
    admission: NOT_ADMITTED               # A.5 CN stays []; Ruling 4.7 applies to every CN listing
                                          # (1.16) intended order [alphavantage] (PD-0067 decision 2), not admitted;
                                          # 7A.3 (a) recorded, (b) met (CN_A_SESSIONS 2025-2026 v1, sha f357b7d4...)

  - source_id: frankfurter.ecb            # ADMITTED; upstream DECLARED, provenance UNCONFIRMED (Ruling 1.1a)
    upstream: ecb
    payload_format: frankfurter_json_timeseries/1
    fields:
      rates.<date>.<ccy>: { format: TEXT_DECIMAL, parse: JSON_NUMBER_LEXEME_AS_DECIMAL,
                            status: OBSERVED }   # "1.0321", "8.0261", "7.5338": 4 dp in the probe
      date_key: { rule: USE_PAYLOAD_DATE }       # never the requested date (§12 item 6)
    role: TRANSPORT_CHECK_FOR_ECB                # same upstream as the ECB file: never corroboration

  - source_id: ecb.eurofxref               # PREFERRED FX source (Ruling 1.1a); needs a SOURCES.json
    upstream: ecb                          # entry and the owner's terms attestation before admission
    fields: { rates: { format: TEXT_DECIMAL, missing_token: "N/A", status: MEMORY } }
```

#### Example A-1 (1.2): profiling `alphavantage.us` from its first file (A.4 procedure)

The file is `alphavantage.us/quote/2026-10-01/AAPL_compact.csv`. Its manifest records
`TIME_SERIES_DAILY`, compact output, retrieval at 2026-10-01T04:53:50Z, and no wrapper
library. It has 100 rows covering 2026-05-08 to 2026-09-30 in descending date order, with
unique dates. I quote one row only: `2026-09-30, <open>, <high>, <low>, <close>` (vendor values redacted in the public copy, PD-0083).

| A.4 step | Check | Result |
|---|---|---|
| 1 Format | Every price has exactly 4 decimals, with trailing zeros kept (`100.0000`). A float rendering would not keep them, and none shows the float32 signature (the example value is redacted in the public copy, PD-0083). | `TEXT_DECIMAL`, `delivered_dp` 4 |
| 2 Integer | Every volume is digit-only text, (the minimum is redacted in the public copy, PD-0083). Text is not float, so the spacing test is not needed. | integral |
| 3 Unit | No turnover column | `SHARE`, `DECLARED_UNVERIFIED` |
| 4 Grid | 100/100 closes lie on the US cent grid for prices ≥ $1 (the range is redacted in the public copy, PD-0083). 47/300 open, high and low values are sub-penny, which is allowed because they are not validated (A.1). | closes recovered, δ = 0 |
| 5 Upstream | A direct API, no library | `alphavantage` |
| row check (Ruling 4.6 item 2) | `low ≤ min(open, close) ≤ max(open, close) ≤ high` | 100/100 pass |
| V0 cross-check (Ruling 5.3; the human confirms against the NYSE calendar) | The weekdays absent between the first and last date are exactly 2026-05-25, 2026-06-19, 2026-07-03 and 2026-09-07. There are no weekend dates. | Consistent with the 2026 NYSE holidays as I recall them (Memorial Day; Juneteenth; Independence Day observed on Friday 3 July; Labor Day). **MEMORY**: the NYSE calendar file is the authority, not this file. |
| V1 | The largest one-session close move is −7.35 % (2026-07-31). No ratio is near 1/2 or 2, so there is no decisive split. | `UNVERIFIABLE` |

### A.4 Rule to obtain a `TO_OBSERVE` profile (deterministic)

From the first real file of a new source and market, run each check below. Record each result
in the profile with status `OBSERVED` and the file hash it came from.

1. **Format**, per numeric field:
   - `FLOAT32` if any value of a non-integral field shows the float32 signature (Ruling 2.4
     item 5);
   - otherwise `TEXT_DECIMAL` if the values carry a fixed decimal count with trailing zeros kept
     (as `100.0000`), or are JSON strings or number lexemes;
   - otherwise `FLOAT64` (shortest-repr renderings, `.0` on whole numbers).

   `TEXT_DECIMAL` and `FLOAT64` normalize identically (the text is the value). They differ only
   in what `delivered_dp` means for the §4.2 bound.

   A field with no signature in a small file may be declared `FLOAT32` conservatively, but only
   when all its values have at most 6 significant digits.
2. **Integer fields** (volume): integral after normalization. For values ≥ 2²⁴, test float32
   spacing: on `[2^k, 2^(k+1))`, float32 integers are multiples of `2^(k−23)`.
3. **Volume unit:** the median of turnover ÷ (close × volume) within [0.9, 1.1] × a candidate
   unit from {1, 100, 1000}. If there is no turnover column, the unit stays
   `DECLARED_UNVERIFIED`, and no magnitude-using rule may use the volume.
4. **Grid:** every close satisfies the market's `price_max_dp` after normalization. A failure
   means the profile is wrong or the source is not reporting official closes. Either way the
   source is not admitted.
5. **Upstream:** confirmed from the library's source at the pinned version (§12 item 13). It is
   never inferred from agreement with another source.
6. **Adjusted series:** `method` and `anchor` only from Test V2. They are never declared.
7. **(1.5) `delivered_dp` when the source does not document it** is the **maximum number of
   decimals** observed in that field across the profiling file (status `OBSERVED`, file hash
   recorded).
   - This is conservative. The source delivers at least that many decimals, so its true
     rounding error is at most `½ × 10^(−observed max)`, which is the bound used.
   - Later files are checked against it: more decimals than declared fails the profile check
     (Ruling 2.4 item 5), and the profile is redone.
   - Float32 fields need no `delivered_dp`, because `½ ulp` of binary32 binds.
   - **(1.16) On every route, for every declared `delivered_dp`**, whether the value was observed or
     documented. That includes `alphavantage.us`, which until now has been checked only on the CN
     route.
     - The count is the decimals the **text shows, trailing zeros included**. That is how item 1
       recognizes `TEXT_DECIMAL`, by a fixed decimal count. `50.50000` shows 5.
     - It is **not** the value's decimal count, which the grid check uses (Ruling 2.4 item 4;
       `10.1000` is 10.1 there).
     - Showing fewer decimals than declared is not a failure.
     - Integral fields are exempt (item 2).
     - Example 3-E.

### A.5 Primary order by upstream (Ruling 4.3)

```yaml
primary_order:          # 1.2: admitted upstreams only (PD-0031/0032)
  CN: []                # no admitted source: Ruling 4.7 (MISSING_PRICE_HISTORY, NO_ADMITTED_SOURCE)
  HK: []                # no admitted source: Ruling 4.7
  US: [alphavantage]    # SINGLE_SOURCE for every US price
  FX: [ecb]             # ecb.eurofxref (if admitted) first, then frankfurter.ecb: transport check only
```

The 1.1 order (CN eastmoney, sina; HK and US sina, eastmoney, alphavantage) is withdrawn with the
admissions it assumed.

**(1.15)** The table is unchanged: CN stays `[]` while `alphavantage.cn` is pending (Ruling 7A.3).
The proposed CN order is the owner's decision (OP-1, §10.1), and so is HK, which is dropped from
personal use under PD-0063 and stays `[]`.

**(1.16)** The table is still unchanged.
- The owner chose `CN: [alphavantage]` as the **intended** order (PD-0067 decision 2, OP-1 (b)).
- It enters this table only in the reviewed increment that follows the owner's admission decision,
  after the Ruling 7A.3 (c) observations.
- A.5 is read per reading, by the listing's market (Ruling 4.7 item 6).

### A.6 (1.5) MIC ↔ OpenFIGI exchange codes (Ruling 7.3)

**Status key:**

- `OBSERVED`: in an admitted OpenFIGI file, with the level shown by `figi` vs `compositeFIGI`;
- `CONFIRMED`: checked by a human against OpenFIGI's published exchange-code list, with the
  reference recorded;
- `MEMORY`: my recollection of Bloomberg/OpenFIGI codes, which does not attach;
- `TO_CONFIRM`: unknown, which does not attach.

Only `OBSERVED` and `CONFIRMED` entries attach (Ruling 7.3 items 3 and 6).

```yaml
exchange_codes:            # MIC (as used on Listing) -> exchange-level exchCode(s)
  XNAS:                    # Nasdaq operating MIC; V1 listings carry the operating MIC
    - { code: UW, segment_mic: XNGS, segment: "Nasdaq Global Select", status: OBSERVED }
      # (1.16; was MEMORY) AAPL_XNGS.json (request micCode XNGS) and AAPL_UW.json (request exchCode UW),
      # retrieved 2026-10-23 19:08:13Z and 19:08:18Z by the owner (PD-0066 decision 4);
      # byte-identical payloads, SHA-256 b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc;
      # manifests cb4d862d37e628b31c7a009f53d461188583e2090934de2bb080c08e21963c8d (XNGS),
      #           7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738 (UW);
      # kept at (since the owner-approved move of 2026-10-24, hashes unchanged):
      #   UW:   data/marketdata/files/openfigi/identity/2026-10-23/         (the indexed store)
      #   XNGS: data/marketdata/observations/openfigi/identity/2026-10-23/  (outside the indexed root)
      # record: figi BBG000B9Y5X2 != compositeFIGI BBG000B9XRY4 (exchange level), shareClassFIGI BBG001S5N8V8.
      # XNGS as a segment of XNAS: ISO 10383, MEMORY (section 12 item 23).
      # Both manifests are cited here by hash; only one may sit in an indexed data root (Ruling 7.3 item 9,
      # 1.16 fix round, review C-4).
      # (fix round 2, reviews L-3 and R2-C8 (a)) This entry's status value changed, MEMORY -> OBSERVED, so
      # the TABLE CONTENT CHANGED in 1.16. Table version market-data/1.16#a6/2 (was market-data/1.5#a6/1;
      # rule: section 11 item 32). The other lines of this comment are not content.
    - { code: UQ, segment_mic: XNMS, segment: "Nasdaq Global Market", status: MEMORY }
    - { code: UR, segment_mic: XNCM, segment: "Nasdaq Capital Market", status: MEMORY }
    # OBSERVED negative: micCode XNAS for AAPL -> "No identifier found" (AAPL_XNAS.json)
  XNYS: [ { code: UN, status: MEMORY } ]
  ARCX: [ { code: UP, status: MEMORY } ]     # NYSE Arca; only if a V1 listing's primary venue is Arca (ETFs)
  BATS: [ { code: UF, status: MEMORY } ]     # Cboe BZX; only if a V1 ETF's primary listing is there
  XASE: [ { code: UA, status: MEMORY } ]     # NYSE American; not in the 1.4 MIC list, listed for completeness
  XHKG: [ { code: HK, status: OBSERVED } ]   # 700_HK.json: figi BBG000BJ35N5 != compositeFIGI BBG000BJ35F4
  XSHG: [ { code: CG, status: MEMORY } ]
  XSHE: [ { code: CS, status: MEMORY } ]

composite_codes:           # composite-level exchCode -> country of the MICs it spans
  US: { mics: [XNYS, XNAS, ARCX, BATS, XASE], status: OBSERVED }  # AAPL_US.json: figi = compositeFIGI
  CH: { mics: [XSHG, XSHE], status: MEMORY }
  HK: { status: TO_CONFIRM }   # the HK exchange-level code is "HK" (observed); whether the HK
                               # composite record also uses "HK" is unknown, so it is not used to
                               # read a level: Ruling 7.3 item 2 decides the level from the record
```

**What the human should download next** to move entries to `OBSERVED`. Each is one OpenFIGI
`TICKER` query:

- ~~AAPL with `exchCode UW` and with `micCode XNGS` (XNAS);~~ done 2026-10-23 (1.16: `UW` is
  `OBSERVED`);
- an NYSE common stock with `exchCode UN` (XNYS);
- 600519 with `exchCode CG` (XSHG) and with `CH` (the composite);
- a Shenzhen A-share with `exchCode CS` (XSHE).

The engineer moves an entry to `OBSERVED` only from such a file, with the level test of Ruling
7.3 item 2 passing. Exchange-level means `figi ≠ compositeFIGI`.
