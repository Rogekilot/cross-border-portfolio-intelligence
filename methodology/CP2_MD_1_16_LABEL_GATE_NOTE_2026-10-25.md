# market-data/1.16: the label gate, the registry re-issue, and six questions from F1 R4a (dated note, 2026-10-25)

**Author:** `quant-analyst` subagent, dispatched by the main session (PM), 2026-10-25.
**Governs nothing new.** This note is not a new market-data version and edits no ruling. It records:

- the registry ids that `market-data/1.16` §11 item 35 left to be fixed "when written";
- my check of the built code against the §11 gate;
- answers to six questions from the engineer's R4a records (`reviews/ENGINEERING_SELF_VALIDATION.md`,
  "F1 R4a (2026-10-25)" and "F1 R4a follow-up").

**Why a dated note and not an edit of the conventions file.** The text of `market-data/1.16` is
`methodology/CP2_MARKET_DATA_CONVENTIONS.md` at commit `ae6dfdc` (SHA-256
`91459f6b592c9949b5eaef7ca4bc1ea7150bde4129b5742673092352ec52d372`, unchanged in the working tree). One
id has one text (P9). Writing these answers into that file would change the text of an issued id, the
process error that the 1.9 → 1.10 note records. Where an answer would change method content, I say so
and name the version it needs (answer (d) only). None is issued here.

**How the facts were established.**

- I read `src/marketdata/` (working tree, uncommitted) against `git show HEAD:` and did not edit it.
- I ran these read-only probes, each a short script in `$TMPDIR` that calls `src/` functions and the
  existing test kits to establish **what the code does**. They are listed so a reviewer can rerun them:
  - a two-symbol `akshare.cn` synthetic file (finding F-1);
  - two Frankfurter-format synthetic files (finding F-2);
  - the item 22 test's world (answer (c));
  - the project's digest functions on the registry files.

  **No expected value below comes from running `src/`.** Each expected outcome is derived from the
  ruling it cites, and the hand arithmetic is shown in place.
- I ran these test modules with the documented `uv run …` command:
  - `test_marketdata_r4a_inputs`;
  - `test_marketdata_listing_market_gate`;
  - `test_marketdata_alphavantage_cn`;
  - `test_marketdata_cp2c1_adapters`;
  - `test_marketdata_akshare_cn`.

  Result: `Ran 172 tests`, `OK (skipped=4)`. I did not run the full suite.
- No network was used.

---

## 1. Task 1: the three registries re-issued for `market-data/1.16`

The ids expected in §11 item 35 are now fixed. Each new file was built by replacing only the fields
listed in its family's change note in the old file's text. I then compared every leaf value of old and
new: only those fields differ. Every file parses as JSON.

| New file (`methodology/registry/`) | New id | Built from (kept as the record) | File SHA-256 | Digest as the loader computes it |
|---|---|---|---|---|
| `RISK_1.11_REGISTRY.json` | `registry_id` `risk/1.11` | `RISK_1.10_REGISTRY.json` | `9760901707bd925fbd5f4693aa7b763f81cc2fa50ea1cccdccbfc7e90e899de3` | `registry_digest` (canonical JSON, `marketdata.canonical`) `5c630fdf9ff4eb6cf0569cda655794b1c0e1ec1f64c1e2ea7daf3df9348058ce` |
| `PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json` | `appendix_id` `performance-registry/1.2`; `registry_id` stays `performance/1.12` | `PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json` | `ef68208a2f6ca06cd5f6cade006a69dfa072fd661112b95874e05bc6e4df5840` | `PerformanceMethodologyRegistry.digest` `f2aefda7232da0a46be1d1592bb50856becf1d10a237e30cf64d060437891a71` |
| `DIVERSIFICATION_1.2_REGISTRY.json` | `registry_id` `diversification/1.2` | `DIVERSIFICATION_1.1_REGISTRY.json` | `0cd4fbe7d544d865448e734ccf61133fb406a0abda9bbb4876a1cda2513bedaa` | `diversification.contracts.digest` `4f27f1e957e36a6c0c749228153d5fb266e0a9ffd0b4f212fc95e8899e852297` |

The fields that changed are listed in each family's own document:

- `CP4_RISK_CONVENTIONS.md`, change note 1.10 → 1.11. The header moves to `risk/1.11`.
- `CP3_REGISTRY_APPENDIX_INVENTORY.md`, "Appendix re-issue `performance-registry/1.2`".
- `CP5_DIVERSIFICATION_CONVENTIONS.md`, change note 1.1 → 1.2. The header moves to
  `diversification/1.2`.

**Checks on the digests.** The old files' digests, recomputed today, equal the values recorded at
their issue:

- `risk/1.10`: `f6dc11f7…2b65`;
- `performance-registry/1.1`: `b2f8af49…ded69`;
- `diversification/1.1`: `d9ad11ba…73be`.

So the new digests are computed the same way.

**When they are in force.** Each new id is in force from the engineer's increment that moves the
code label to `market-data/1.16`. Until then the code runs, and its manifests cite:

- `risk/1.10`;
- `performance-registry/1.1`;
- `diversification/1.1`;
- `market-data/1.15`.

§11 item 35's last bullet holds both ways: no manifest may name `market-data/1.16` beside a 1.15-era
registry id, or the reverse. The byte copies in `src/` and the loaders' accepted ids follow in that
same increment (item 33).

**`INSIGHTS_1.0_REGISTRY.json` is unaffected.** It names no market-data, `risk`, `diversification` or
`performance` version anywhere in its text; I checked the parsed file. Its keys are:

- `registry_id`, `issued`, `authored_by`;
- `authority`, `conventions`, `scope`;
- `shared`, `entries`.

`CP6_INSIGHT_CONVENTIONS.md` cites none of the moved ids either. Nothing in it names the label the
code runs, so no re-issue is owed (§11 item 35: "every registry that names a market-data version").

---

## 2. Answers

### (a) Does the §11 gate stand, and is it met by the built code?

**The gate stands as written. It is not yet met. Two built items do not run the 1.16 rule on every
route they govern:**

- **item 25** (V0 on a file that holds several symbols);
- **item 34** (V0-FX on the Frankfurter route).

Both are code findings. Neither changes the method, so neither needs a new market-data version. Items
32, 33 and 35 are completed by the label-move increment itself; item 35's methodology part is §1 above.

| Item | My reading of `src/` (working tree) | State |
|---|---|---|
| 23 label source from profile data | `profiles.CallAdjustment("RAW", DECLARED, "PD-0066 decision 3")` on both `TIME_SERIES_DAILY` entries; `daily_csv` builds `PROFILE_CALL_ADJUSTMENT:<source>:<function>:<status>` from the entry; the label status is still set to `UNVERIFIABLE` by ingest | built |
| 24 A.6 `UW`, item 9 attachment, item 10 checks | `exchange_codes`: `UW` `OBSERVED`, `TABLE_VERSION` `market-data/1.16#a6/2`; `resolver`: `SHARE_CLASS_CONFLICT` beside the existing `COMPOSITE_CONFLICT`; tests read the real `AAPL_UW.json` | built |
| 25 V0, duplicate session dates, every market | the opt-in flag is gone; `daily_csv` counts parsed dates per (symbol, file) on every route and names the contradicted series; ingest turns it into a `SeriesExclusion`, so the file stays in `M` | **built for single-symbol files; deviates on a multi-symbol file (F-1)** |
| 26 A.4 item 7, every route | `check_field_format` has no flag; it applies to every `TEXT_DECIMAL` or `FLOAT64` field with a `delivered_dp`; integral and `FLOAT32` fields are exempt; it counts the shown exponent, trailing zeros included. `daily_csv` is the only caller, and it serves every price route; no FX or other field declares a `delivered_dp` | built |
| 27 per-reading gate | `MIC_MARKET` and `EXCHANGE_ZONES` gain ARCX, BATS and XASE; `listing_market_refusal` refuses an unmapped MIC and a profile-less source; the gate is called from ingest (`bind`, which corporate-action records also pass through), the store constructor (`_require_readings_admitted`, also used by `read_release`) and `write_release` (`_require_admitted_to_store`: the profile-less check without an identity, the full check with `exchange_of`) | built; one LOW note below |
| 28 `NO_ADMITTED_SOURCE` exclusivity | `store.quote_on` adds the cause only when the listing has no exclusion and no quote | built |
| 34 V0-FX, a fixing date stated twice | `ecb_eurofxref`: counts parsed dates over all rows and names every currency series of the file as contradicted; the first-row-wins code is removed | **built for the ECB format; not on the Frankfurter route (F-2)** |
| 32 ids, 33 baselines, 35 registries | label step | the label-move increment |

**F-1 (item 25; Test V0 (1.16), "the unit is the series (listing, file)").**

- **What the code does.** `translate_daily_csv` returns early when any (symbol, date) repeats. The
  return carries the issues and the contradicted series, and **no reading of any symbol in the file**.
  For a single-symbol file, such as every Alpha Vantage file, that is the rule. For a multi-symbol file
  it is not.
- **The probe.** A synthetic `akshare.cn` file, in the test kit's format, with two symbols:
  - `600001`: three distinct dates;
  - `600002`: the same three dates, plus 2025-01-02 written a second time.
- **Expected under V0 (1.16), from the ruling.**
  - Series (600002, file): `CONTRADICTED`, with no reading. Lineage: V0, `DUPLICATE_SESSION_DATE`,
    2025-01-02.
  - Series (600001, file): not judged by this defect. Its three rows are read and are subject to every
    other check.
- **Observed.** 0 quotes. Only `600002` is named as contradicted. The control file without the extra
  row gives 6 quotes over both symbols. So `600001` silently supplies nothing, and nothing names a
  cause for it.
- **Consequence.** In a synthetic CN world, that listing would then resolve with no series at all. Under
  item 28 its lookup would read `NO_ADMITTED_SOURCE`, a cause that is not true (P9).
- **Scope.** The only multi-symbol route is the refused `akshare.cn` format (PD-0031/0032), so no real
  result is affected. But a manifest citing 1.16 on a synthetic `M` would run a V0 that is not the 1.16
  V0.
- **To clear.**
  - Exclude only the symbols that have a repeated date; read the other symbols' rows as before.
  - Test: the two-symbol file above, asserting `600001`'s readings and `600002`'s exclusion, each with
    its own lineage.

**F-2 (item 34; Test V0-FX (1.16), "a fixing date stated twice in an FX file … every currency series
read from that file").**

- **The rule's scope.** Item 34's key and unit ("the parsed fixing date, within one FX file"; "every
  currency series read from that file") are not limited to the ECB format. The bullet "the ECB adapter's
  'row not read' is replaced" names one part of the change. Its test list names ECB files only, which
  was too narrow on my part. `frankfurter.ecb` is an admitted FX source (A.3, role
  `TRANSPORT_CHECK_FOR_ECB`).
- **What the code does.** `frankfurter.py` reads the payload with `json.loads`. For an object with a
  repeated name, that keeps the **last** value. It then reads every date key separately.
- **Probe (i): one key twice.** `"rates": {"2025-01-02": {"USD": 1.0800}, "2025-01-02": {"USD":
  9.9900}, "2025-01-03": {"USD": 1.0810}}`, with the kit's ECB calendar.
  - Expected under V0-FX (1.16): the file's USD series is excluded whole. No rate from this file on any
    date, and lineage `V0_FX_DUPLICATE_DATE` 2025-01-02.
  - Observed: `fx_on(EUR→USD, 2025-01-02)` is `FOUND` at 999/100 (9.99), `SINGLE_SOURCE`, with no
    exclusion. One of two statements was chosen by the parser's order, which §11 "Must not decide"
    forbids.
- **Probe (ii): two spellings of one date.** The same file with keys `"2025-01-02"` and `"20250102"`
  (both parse to one date under the product's Python 3.12 `date.fromisoformat`).
  - Expected: the same exclusion.
  - Observed: three readings, and `DISAGREEMENT` (no selection) on 2025-01-02 only, with the file's other
    date served. That is the pre-1.16 US pattern Example 3-E describes.
- **This is the existing rule, not a new one.** A JSON object keyed by date states a date once per name.
  A repeated name, or two names that parse to one date, states it twice. No market-data version is
  needed.
- **To clear.**
  - Detect repeated names, for example with `object_pairs_hook`, and repeated parsed dates in `rates`.
    The means are the engineer's.
  - Exclude every currency series of the file with `V0_FX_DUPLICATE_DATE` and the dates.
  - Tests: probes (i) and (ii), both with equal values as well.
- **Effect on stored data.** I parsed both stored Frankfurter files with every name kept:
  - `EUR_2025-01-02_2025-01-08.json`: 5 date names, 5 distinct dates;
  - `EUR_2026-05-08_2026-09-30.json`: 104 date names, 104 distinct dates.

  So the fix excludes nothing that is on disk.

**LOW, not blocking (item 27).**

- `SourceProfile.gate_refusal` checks A.5 for **every** market a profile covers. Ruling 4.7 item 6
  condition 3 judges the market of the reading's listing.
- That is stricter, never looser. It differs only for a profile that covers several markets, and no
  profile does today: every entry of `SOURCES` lists at most one market.
- RECOMMENDATION: judge the listing's market when the first multi-market profile is added.

**Item 28, a note, not a finding.** "No series" means neither readings nor exclusions (item 28's own
words), so a listing with only verification-only adjusted rows still records `NO_ADMITTED_SOURCE`. That
is what item 28 says.

### (b) What `market-data/1.16#profiles/5` names

It names **the profile-set content of `market-data/1.15#profiles/4` plus exactly three changes**
(§11 item 32, "Why 1.16 takes 5"):

1. the `TIME_SERIES_DAILY` `call_adjustment` entry of `alphavantage.us` and of `alphavantage.cn`
   carries its status `DECLARED` and the reference "PD-0066 decision 3" as data. The adjustment `RAW`
   is unchanged;
2. the Ruling 4.7 item 6 MIC → market table gains ARCX, BATS and XASE, each → US;
3. the Ruling 2.2 item 1 zone table gains ARCX, BATS and XASE, each → `America/New_York`.

**Confirmed against `src/marketdata/profiles.py`.** I diffed the working tree against `HEAD`. There
is no other content change:

- the A.1 markets and CN class table;
- every other source profile, field, status and `delivered_dp`;
- the A.5 primary order;
- the ECB fixing and publication times.

The new `CALL_ADJUSTMENT_STATUSES` tuple and the `PD_0066_DECISION_3` constant are the vocabulary and
the reference of change 1. The docstrings and comments are not content.

**`listing_market_refusal`'s order is not profile content.** It is the logic of Ruling 4.7 item 6,
named by the convention set id, and it does not move `k`. It conforms:

1. a MIC that maps to no V1 market, `None` included → `LISTING_EXCHANGE_UNKNOWN`, with the MIC named;
2. no profile → `SOURCE_NOT_ADMITTED`;
3. the profile does not cover the market → `SOURCE_MARKET_NOT_COVERED`;
4. not admitted, or the upstream not in A.5 → `not_admitted_code`.

The ruling fixes the conditions and the labels. It does not fix which label wins when two parts of its
condition 2 fail together: for example, `alphavantage.cn` on an XNAS listing is both uncovered and
pending. The code reports coverage first. Every failing case is refused, and the labels are not reason
codes, so either precedence conforms.

**Only at the label step.** The working tree already holds profiles/5 content under the id
`market-data/1.15#profiles/4`. The engineer states this. That tree must not build a release; the id
moves to `market-data/1.16#profiles/5` together with the eight constants. No filing profile exists, so
nothing else is counted (answer (f)).

### (c) Is `test_7` an acceptable item 22 test?

**Yes, as the item 22 test, once one assertion is added.** Then item 22's "not built" line (gate
point 2.6) can be left out at the label step.

- **What it shows.** It values the midpoint kit's ledger with and without a corroborated (4, 1) split
  dated 2020-08-31, from a feed and a filing source:
  - the ledger begins 2024-12-20;
  - the kit calendar covers 2024-06-03 to 2026-06-30, so the split lies before any holding and outside
    the calendar.

  Every metric's (state, reason, value) is equal, all `AVAILABLE`. That is Ruling 6.5 item 4 in
  general form. Example 6-E row (iv) is one instance of it; it is not required literally.
- **The pinned value, by hand.**
  - 50 units × 37.50, the kit's close on 2025-02-03, = 1,875.00;
  - cash 10,000.00 − 7,500.00 = 2,500.00;
  - total 1,875.00 + 2,500.00 = **4,375.00**, the value the test pins.
- **The assertion to add (non-vacuity).** "With equals without" also passes if the 2020 records never
  reach detection. The test should assert that they do:
  - the key (ℓ, 2020-08-31) is `CORROBORATED` under the test's policy;
  - under a policy that omits the filing source, the same key is unmatched.

  My probe shows both hold today: `corroborate` gives `CORROBORATED`, and `policy_unmatched_keys` gives
  that key with `test.filing` unclassified. The test does not yet defend it.
- **RECOMMENDATION (not a condition).** Read the calendar's coverage start from the calendar object, not
  from the literal `D(2024, 6, 3)`. The test's class name ("…NoCorporateActionFile…") does not describe
  this test.

### (d) `securityType2` or `securityType`?

**The rule means OpenFIGI's `securityType`, and the code, which reads `securityType`, need not change.
The text's field name is a defect, inherited from 1.5, to be corrected in the next market-data
version. It does not block the 1.16 label.**

- **Why `securityType`.** Ruling 7.3 item 3 matches "Common Stock" with `COMMON_STOCK` and "an ETP
  type" with `ETF`. As I recall OpenFIGI's vocabulary (MEMORY, to be confirmed by a human):
  - `securityType` carries "Common Stock" and "ETP";
  - `securityType2` carries "Common Stock" and, for ETFs, "Mutual Fund".

  The values the rule names belong to `securityType`. Read literally against `securityType2`, the ETF
  clause could never be met.
- **Why it does not block.**
  - Every OpenFIGI record held has `securityType` = `securityType2` = "Common Stock": `AAPL_UW.json`,
    `AAPL_US.json` and `700_HK.json`. I read them.
  - So for every input that exists, the code's outcome and the literal text's outcome are the same.
  - The only test that uses "ETP" is synthetic and passes it as `securityType` (`test_cp2_final_round`).
- **Text to correct, in the next market-data version (not issued here; it changes rule text).** Two
  places:
  - Ruling 7.3 item 3;
  - Ruling 7A.1's "OpenFIGI's `securityType2` is a consistency check".
- **Owed before any ETF OpenFIGI record is used.**
  - A human confirms both fields' values for an ETF, from OpenFIGI's documentation or the record itself
    (a new §12 item).
  - If "ETP" in fact appears in `securityType2`, the code changes then, not now.
- **RECOMMENDATION.** Until that version, the label-move increment lists this in the manifest's open
  items as one line, alongside gate point 2's lines (which are "at least" those listed). The line says
  the type check reads `securityType` where the 1.16 text names `securityType2`, and that the two are
  equal on every record held.

### (e) Engineer's finding 1: Eastmoney `delivered_dp 2` and the class grid

**The refusal is intended.** A per-class `delivered_dp` is not introduced.

- **Why.** A.4 item 7 sets an undocumented `delivered_dp` to the maximum decimals observed in the
  profiling file. It also says a later file showing more "fails the profile check …, and the profile is
  redone".
  - The `akshare.cn` profile was observed from A-share files only: maximum 2, "1324.49"; qfq
    `adjusted_dp` 2, "1244.91".
  - A 3-decimal ETF or SSE B-share close is exactly the case of a file the profile was not observed on.
  - The rule's answer is to re-profile with such a file, which would give `delivered_dp` 3 if that is
    what it shows. Accepting the text under the old profile is not the answer.
- **The two checks do different jobs.** `delivered_dp` is the source's rendering bound (§4.2), a
  property of the source, not of the class. The class-dependent validity bound is the A.1 grid, which
  runs after it. So a per-class `delivered_dp` would duplicate the grid, and it would be a value no file
  has shown.
- **Stated as a limit (no method change).** On the `akshare.cn` route as recorded:
  - the A.1 class grid is reachable only for closes whose text shows at most 2 decimals;
  - a `FUND_ETF_LOF_BOND` or `B_SHARE_SSE` close with a third decimal, and any qfq text with more than 2
    decimals, is refused at the profile check (`PROFILE_CHECK_FAILED`) before the grid sees it;
  - the 3-decimal class values are therefore exercised only by tests that substitute a profile (the
    engineer's `gate_kit.delivered_dp("akshare.cn", 8)`). Those are tests of the grid, not of the
    recorded profile, and should say so.

  The source is refused (PD-0031/0032), so no real result is affected.
- **For a future CN source.** Its A.4 profiling must include a file of every class it is to serve. A
  provisional profile like `alphavantage.cn`'s (`delivered_dp` 4) does not have this limit for 3-decimal
  closes.

### (f) Engineer's finding 2: no filing profile, so every real corporate-action record is refused

**Confirmed: this is the intended state under 1.16.**

- **Why it is intended.** Ruling 4.7 item 6 says a filing profile is "added in the version that
  records its registration". No filing source is registered (PD-0067 decision 4). So no profile of
  either kind exists for one, and its records are refused as `SOURCE_NOT_ADMITTED`.
- **Nothing current is lost.**
  - The HG4 `M` holds no corporate-action file (PD-0066 decision 2).
  - The data root holds none. I listed it today: `files/` holds quote, FX, calendar and identity
    directories only.
  - `SOURCES.json` registers no filing-role source.
  - Synthetic records are exempt (Ruling 4.8), so the fixtures are unaffected.

**Before a real filing source can supply a record, all of these must exist, in this order:**

1. **The owner's terms reading.** The site's live terms (SEC EDGAR, cninfo), recorded verbatim by the
   main session in `data/marketdata/SOURCES.json`, which registers the source (PD-0067 decision 4
   item 1; OP-6). This is the owner's step.
2. **A market-data version that adds the source's Appendix A.3 filing profile.** It states:
   - the source id;
   - role `FILING`;
   - the markets it covers;
   - the record types it attests;
   - the terms reference recorded at registration.

   It is profile content, so the counter moves (`#profiles/6` under that version). Being a new
   convention set, it also re-issues the registries again (§11 item 35). This is my step, after step 1.
3. **The engineer's build.**
   - The filing-profile data type in `profiles.py`.
   - Its branch of the gate:
     - a record of a listing in the profile's markets passes condition 1 and the market check;
     - a record outside them gets `SOURCE_MARKET_NOT_COVERED`;
     - A.5 is not applied;
     - the source never supplies a price reading.
   - Tests for each.
4. **Each record.** Prepared per Ruling 7.6 item 2 from text the owner supplies, and confirmed by the
   owner against the filing. An unconfirmed draft attests nothing (PD-0067 decision 4 item 2).
5. **To use a record in a computation.** The F8-B confirmation policy names the source in its filing
   role (Ruling 6.4d).
   - The policy the engineer recorded (option B, `none.admitted.filing`) would leave such a record
     unclassified, and the whole computation would be refused (`DETECTION_POLICY_UNMATCHED`), which is
     correct.
   - Changing the policy changes its digest, so it is a new context. Which ids to use is the PM's
     choice.
6. **For the HG4 check only.** Adding any corporate-action file to its `M` needs a new owner decision,
   because PD-0066 decision 2 fixed "no corporate-action file".

---

## 3. What blocks the label switch

1. **F-1:** item 25 on a multi-symbol file. Fix in `daily_csv`, with its test.
2. **F-2:** item 34 on the Frankfurter route. Fix in `frankfurter.py`, with its tests.
3. **The label-move increment's own parts**, as §11 lists them:
   - the eight constants, `PROFILE_SET_VERSION` = `market-data/1.16#profiles/5`, and `UNBUILT_1_15`
     in its 1.16 form, one line per unbuilt behaviour of gate point 2;
   - item 22's line may be left out once the assertion in (c) is added;
   - the byte copies of the three registries above and the ids their loaders accept;
   - the re-recorded pins (item 33);
   - the check that no stored real release is affected.

Not blocking:

- the item 27 LOW note;
- answer (d), with the recommended open-item line;
- the limit in (e);
- the state in (f).

## 4. What this note does not do

- It edits no ruling of `market-data/1.16`. It decides nothing for the owner or the PM: the policy ids,
  the order of increments and the HG4 data are theirs.
- It issues no market-data version. The text correction of (d) waits for the next version, whose
  timing the PM sets.

---

## Addendum A (2026-10-25, after the R4a review): three rulings on Tests V0 and V0-FX

Sections 1 to 4 above are unchanged; before this addendum the file's SHA-256 was
`188415c4124df6d44bfe9638c67cb86312a9078e00f414062063e96baf79bea9`. These rulings answer the PM's routing of
`reviews/TECH_REVIEW.md`, "F1 R4a build — independent technical review (2026-10-25)", findings MEDIUM-2,
LOW-4 and LOW-5. Like the rest of this note, they edit no 1.16 ruling and issue no version. No
expected value comes from running `src/`.

### A.0 A correction to section 2 (a)

My gate table said, for item 26, that `daily_csv` "serves every price route". The mock synthetic
route (`adapters/mock.py`) is a price and FX route that does not go through `daily_csv` or the ECB and
Frankfurter adapters. So my item 25 and item 34 checks missed it; the review's HIGH-1 is right.

For item 26 the error has no effect. A.4 item 7 applies only to fields with a declared
`delivered_dp`, and the mock source has no precision profile.

### A.1 The principle the three rulings share

Tests V0 (1.16) and V0-FX (1.16) judge **what a file states**, not how it lays the statement out.

- **A price file states a close per (listing, session date).** V0's unit is "the series (listing,
  file)" (section 3 V0 (1.16); section 3 "Consequences": "the unit dropped is the series: (listing,
  file)").
- **An FX file states a fixing per (fixing date, currency).** In the ECB wide layout, one date row
  carries every currency, which is why V0-FX (1.16) speaks of "a date row".
- The same facts can come in different layouts:
  - a wide CSV row;
  - a JSON object keyed by date;
  - a long list with one row per (date, currency) or per (ticker, date);
  - a vendor symbol or an alias.

  The method must give the same outcome for the same facts whatever the layout (P12).
- **Two statements of one fact in one file** trigger the duplicate clause, with the 1.16 unit and
  cause:
  - for prices, the series (listing, file) is `CONTRADICTED`, with `V0`, `DUPLICATE_SESSION_DATE` and the
    dates;
  - for FX, every currency series of the file is excluded whole, with `V0_FX_DUPLICATE_DATE` and the
    dates.
- **A row whose date cannot be read states no fact.** It is refused at row level and takes no part in
  the count.
- Nothing is ever chosen by order or by value (section 11 "Must not decide": "which value wins a
  disagreement"; "keeping one of two FX rows for one fixing date, by order or by value").
- **Every adapter must agree:** `daily_csv` (all its routes), `ecb_eurofxref`, `frankfurter` and `mock`,
  and any later one. Where the check lives is the engineer's choice. The review's suggestion (where the
  rest of V0 runs, over parsed dates per (listing, file) after resolution, and per FX file) gives that
  agreement by construction.

### A.2 Ruling 1 (MEDIUM-2): a blank or unparseable date label

**Settled by the 1.16 text.** The next market-data version restates one phrase, with no behaviour
change. Code labelled 1.16 must already behave as follows.

The 1.16 sentence is: "A label that does not parse as a date is its own key, and the row is refused
as unparseable anyway."

- **What the sentence means.**
  - "Its own key" means only that such a label **never joins the key of a real date**. For example,
    `2026-09-29x` is not `2026-09-29`.
  - It does not make the label a key of the duplicate count.
  - What governs is the second half: the row is refused as unparseable.
- **Why this reading is the right one.**
  - V0 tests "every session date in the series". A row that names no date names no session, so it is
    not in the series V0 judges.
  - The duplicate clause is keyed on "the parsed date". An unparsed label has none.
  - The Effect bullet requires lineage to name "the dates". An unparseable label has no date to name,
    which shows the clause was not written for it.
  - Before 1.16 the US route refused such a row alone (`UNPARSEABLE_ROW`) and read the rest. No ruling
    asked for more.
- **Outcomes, for every adapter:**

  | Case | Outcome | Kind |
  |---|---|---|
  | (i) one blank or unparseable date label | that row is refused, with an `UNPARSEABLE_ROW` issue in the ingest record; the series' other rows are judged by V0 and every other test as if the row were absent | **row-level issue** |
  | (ii) two or more rows with the same blank or unparseable label | each such row is refused, as in (i); they are **not** two statements of a session, so V0 is not failed by them | row-level issues |
  | (iii) two or more rows with different unparseable labels | the same as (ii) | row-level issues |
  | (iv) a row whose date **parses**, while another of its fields does not | it **does** state that session, so it counts in the duplicate test, as V0-FX (1.16) counts an `N/A` cell and as V0 counts identical rows. The row is also refused for its bad field | counts for V0; row-level issue |

  None of (i) to (iii) is a whole-series exclusion or a refused file.
- **What is wrong today.**
  - The behaviour the review found is not allowed under any reading: a series removed with no
    exclusion and no cause.
  - A file is refused whole only by the rules that already do so. These include:
    - the profile check (Ruling 2.4 item 5; for example, an empty **price** text fails it);
    - a missing required column;
    - the admission gates.
- **ECB, Frankfurter and mock must agree.**
  - ECB: an unparseable date row is refused and skipped in the count. That conforms.
  - Frankfurter: an unparseable date name is refused (`bad date key`) and is not a fixing date. If the
    same unparseable name is repeated, every copy is refused, and nothing is chosen.
  - Mock: an unparseable `date` is refused by its row reader and counts nowhere.
- **Hand check of the review's example**, on Example 3-E (c). The file holds the three clean rows of
  09-28, 09-29 and 09-30 (close `50.5000` on 09-30), plus two rows with an empty `timestamp` and price
  texts present.
  - The profile check passes: every price text shows 4 decimals, and no text is empty.
  - The two undated rows are refused, with two `UNPARSEABLE_ROW` issues.
  - V0 judges the parsed dates {09-28, 09-29, 09-30}. They are distinct sessions, so V0 passes.
  - At `D` = 09-30 the result is `CURRENT`, `AVAILABLE`, with value 100 × 50.50 = **5,050.00**, as in
    Example 3-E (c).
- **Known limits (stated, not changed).**
  - A refused row's true date is unknown, so V0 cannot see whether it repeated a valid row. If it was
    the latest session, its absence shows as a missed session under Ruling 5.2. The cause is recorded
    in the ingest record, not in the lookup's lineage, as for every row-level refusal today
    (`ROW_INCONSISTENT` and the others).
  - If **every** row of a listing in a file is refused, `M` holds no series of that listing. Item 28's
    definition (neither readings nor exclusions) then applies as written. In a synthetic CN world that
    records `NO_ADMITTED_SOURCE`, and the result is marked synthetic (Ruling 4.8 item 2).

### A.3 Ruling 2 (LOW-4): one currency stated twice for one fixing date

**This is the V0-FX duplicate rule, and the outcome is V0-FX (1.16)'s: every currency series of the
file is excluded whole, the file stays in `M`, and lineage carries `V0_FX_DUPLICATE_DATE` with the
dates. The detail also names the currency stated twice.**

- **Why it is this rule.**
  - V0-FX (1.16) gives its reason itself: "Two rows for one date are two statements of one fixing.
    Serving either one is choosing which value wins, which only a resolution record may do."
  - A currency stated twice for one date is two statements of one fixing (date, currency) in one file:
    - in the Frankfurter layout, `{"USD":1.08,"USD":9.99}`;
    - in the ECB layout, a header `Date,USD,USD` states USD twice on every date.
  - The same two statements in a long layout are two rows for one (date, currency). The mock FX format
    is such a layout, and there the duplicate clause plainly applies. By A.1, the outcome cannot depend
    on the layout.
- **The long-format key, which HIGH-1's mock fix needs.**
  - In a file with one row per (pair, date), as mock FX files are, the key is the fixing (pair, date),
    not the date alone.
  - The literal phrase "a date appears in more than one row" would fail every mock FX file that holds
    two currencies, because each date appears once per currency. That is not what the rule says: its
    stated premise, "a date row carries every currency column", describes the wide layout only.
  - The unit stays "every currency series read from that file".
  - The engineer's `MockSyntheticAdapter._duplicated_fixings` in the working tree, keyed on
    (base, quote, date) and excluding every quote currency of the file, conforms. I read it; I did not
    run it.
  - The review's HIGH-1 expected text, "the file's USD series is excluded whole", should read **every
    currency series of the file**.
- **Hand outcomes.**
  - Frankfurter file: `"2025-01-02": {"USD": 1.0800, "USD": 9.9900}`, `"2025-01-03": {"USD":
    1.0810}`. Expected: no rate from this file on any date, for USD or for any other currency it holds.
    Lineage: `V0_FX_DUPLICATE_DATE`, 2025-01-02, USD.
  - ECB file with the header `Date,USD,USD,`: every date states USD twice, so every currency series of
    the file is excluded. Lineage names every date of the file and USD.
- **Is it settled by the 1.16 text?**
  - **The outcome is.** §11 "Must not decide" forbids serving either value. Among the outcomes that
    serve neither, V0-FX (1.16) is the one the text prescribes for the same defect in the wide and long
    layouts.
  - **The letter of the operative sentence is not.** It is keyed on a date "in more than one row", and
    does not reach a repeated name or column.
  - So the next market-data version restates the key as "a fixing (date, currency or pair) stated
    more than once in one FX file, in any layout", with the 1.16 unit and cause. That restatement
    changes no behaviour from this ruling.
- **May code labelled 1.16 carry it now?** Yes, and it should.
  - This is not later-version behaviour under an earlier label. It is the only family of outcomes 1.16
    permits (no value chosen), in the form 1.16 already gives the same defect.
  - When the next version is issued, no result computed under this ruling changes.
  - Serving 9.99, or either value, does not conform to 1.16 today. Neither does `NO_SELECTION` on one
    date while the file's other dates are served.

**Observation for routing (not asked; LOW).** By the same principle, a price file whose header repeats
a field column is affected.

- For example, `timestamp,open,high,low,close,close,volume` states each session's close twice.
- Python's `csv.DictReader`, which `daily_csv` uses, keeps the **last** of two same-named columns. I
  checked this in a scratch shell; I did not probe the adapter.
- By A.1 this is two statements of one (listing, session) close. Every series in the file is then
  `CONTRADICTED` under V0's duplicate clause, and nothing is read by order.
- I list it so the engineer can check `daily_csv` and the PM can schedule it. Its letter waits for the
  same restatement in the next version. It is not one of the review's findings.

### A.4 Ruling 3 (LOW-5): two aliases of one listing on one date

**Settled by the 1.16 text: the key is the listing, not the vendor symbol.** The duplicate test counts
(listing, file, parsed session date) **after identity resolution**.

- **The rule.** V0 (1.16) says "the unit is the series (listing, file), as for the rest of V0". Section 3
  "Consequences" defines the series as (listing, file).
- **The aliases case.** Two vendor ids, ticker/MIC pairs or other aliases that resolve to one listing
  on one date state that listing's session twice. The series (listing, file) is then `CONTRADICTED`
  whole: no reading on any date, with lineage `V0`, `DUPLICATE_SESSION_DATE` and the date.
- **Hand outcome for the review's case.** One XSHG listing has vendor ids `600519` and `600519X`; both
  state 2025-01-03 in one file.
  - Expected: the series is `CONTRADICTED` and supplies no reading.
  - The lookup is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`, with cause `SERIES_CONTRADICTED`
    (V0, 2025-01-03).
  - It is not `FOUND 10.50`.
- **Rows that do not resolve** belong to no series. They supply nothing and stay pending, as today. A
  per-symbol pre-check before resolution may remain, but it must never remove a series without its
  exclusion and cause, which is MEDIUM-2's defect.
- **The same holds on the mock route.** Mock rows keyed by (MIC, ticker) are aliases in the same sense.
  The working-tree `_duplicated_sessions` keys on (MIC, ticker), so it has this gap too.
- **Next version and the gate.**
  - No new version is needed. A restatement in the next version (the key named as the listing after
    resolution) would change nothing.
  - Under the gate's standard, which I applied to F-1, this is a deviation of item 25 on the routes that
    carry aliases. So it is fixed before the label, not disclosed: gate point 2 offers no "not built"
    line for items 23–28.
  - Its reach is small: the refused multi-symbol Eastmoney layout, and mock files that alias one
    listing. A duplicate check run after resolution clears it on every route at once.

### A.5 Summary for the engineer and the PM

| Question | Settled by 1.16? | Outcome | Next version | Interim under the 1.16 label |
|---|---|---|---|---|
| MEDIUM-2: blank or unparseable date | yes | row-level refusal (`UNPARSEABLE_ROW`); no part in the duplicate count; never a silent series removal | restate "its own key" (clarification) | none needed: the 1.16 behaviour is the outcome |
| LOW-4: one (date, currency) stated twice | outcome yes (via §11 and V0-FX's stated reason); letter no | V0-FX (1.16): every currency series of the file excluded, file in `M`, `V0_FX_DUPLICATE_DATE` + dates + currency; long-format key is (pair, date) | restate the key as the fixing, in any layout | yes: exactly this outcome, which the next version keeps |
| LOW-5: aliases of one listing | yes | key (listing, file, parsed date) after resolution; series `CONTRADICTED` | optional restatement, no change | none needed |

None of these changes `market-data/1.16#profiles/5`, the A.6 id, any registry or any fixture. The
fixtures' price and FX files have one row per (listing or pair, date), with no blank dates and no
aliases. That follows from the 1.15 → 1.16 change note, "Fixtures", and the review's count: 1142
quote keys and 828 FX keys in the cp3 golden world, none repeated.

---

## Addendum B (2026-10-25, after the R4a fix round): four engineer choices, ruled

Sections 1 to 4 and Addendum A are unchanged. Before this addendum the file's SHA-256 was
`5e32bfaa41e0a808527f6dd743b6906724df5c769f28bec0e283add3be879a7d`.

These rulings answer the PM's routing of the engineer's "Choices the contract did not cover"
(`reviews/ENGINEERING_SELF_VALIDATION.md`, "F1 R4a fix round …", choices 1, 3, 4 and 5; choice 2 was
ruled in A.3). I read the cited code in `src/marketdata/adapters/` (`frankfurter.py`, `ecb_eurofxref.py`,
`mock.py`) and did not run it. No expected value comes from running `src/`. None of the four changes
`market-data/1.16#profiles/5`, the A.6 id, a registry or a fixture.

| # | Engineer's choice | Ruling | Settled by 1.16, or the next version |
|---|---|---|---|
| B.1 | Frankfurter: a repeated top-level `base`, `amount` or `rates` member. If it restates a date, V0-FX applies (every currency series excluded, file kept in `M`). If it states no date twice, the whole file is refused (`UNKNOWN_FORMAT`). | **Confirmed.** A date in two `rates` members is a fixing stated twice, so V0-FX (A.3) applies. Otherwise a repeated envelope member leaves the file's basis or content to the parser's order: the adapter cannot establish "EUR-based, amount 1" (§11 item 1, "never use a rebased quote"; Ruling 1.1a) or which `rates` holds the file's dates. The file is refused even when the repeats agree. Both outcomes serve nothing from the file, and neither chooses a statement. | The **outcome** is settled by 1.16: §11 item 1, and §11 "Must not decide" (no statement chosen by order). The **next version** states the envelope rule explicitly ("a Frankfurter payload with a repeated top-level member is not in its declared format"), with no change in behaviour. Until then this is a conforming interim under the 1.16 label. |
| B.2 | A repeated CSV header column covers **any** column the adapter reads, volume included, and every series of the file is `CONTRADICTED`. The ECB duplicate-column check counts only the currencies the manifest asks for. | **Confirmed, both halves.** Every read column feeds a reading or its admission: the date, symbol and close; the print rule's volume (Ruling 2.1); the row check's open, high and low (Ruling 4.6); turnover (Ruling 2.6); and the within-source change check (Ruling 4.6). So two of any of them is two statements read by order, and by A.1 every series of the file states each of its rows twice. A column the adapter does not read states nothing the method uses, so its repeat changes nothing. That is why ECB counts only the currencies it reads: V0-FX's unit is "every currency series **read** from that file". When the manifest names no currency, every column is read and every column counts. | **Next version** (the letter of V0 and V0-FX is keyed on dates). The A.3 observation already routed this case. It is a conforming interim under the 1.16 label: it is the only no-choice outcome, and the next version keeps it. |
| B.3 | A repeated unparseable Frankfurter date name gives **one** `bad date key` issue, not one per copy. | **Confirmed.** A.2 requires that every copy is refused and that none is served or counted, and the code does that. How many issues the ingest record lists for one refused name is record-keeping, not method. **RECOMMENDATION** (not a condition): the parser already keeps repeated names, so the issue's detail may state how many copies there were (P9). | **Settled by 1.16** (A.2). Nothing for the next version. |
| B.4 | Mock rows: a blank date gets `MISSING_FIELD`, a non-date gets `UNPARSEABLE_ROW`, and each row is refused alone. | **Confirmed.** A.2 fixes the outcome: refused at row level, no part in the duplicate count, never a series removal. The issue code is adapter vocabulary (`IssueCode` is not a `ReasonCode`). `MISSING_FIELD` for a blank date is accurate, and A.2's naming of `UNPARSEABLE_ROW` meant the kind of outcome, not a required code. **RECOMMENDATION** (LOW, cosmetic): align the code across adapters later. `daily_csv` gives `UNPARSEABLE_ROW` for a blank timestamp, and readers of ingest records across routes would see one code for one defect. | **Settled by 1.16** (A.2). Nothing for the next version. |

**Owed to the next market-data version** (a restatement only; it changes no behaviour these rulings
fix):

- the "its own key" clarification (A.2);
- the key of the duplicate clauses as the statement, in any layout:
  - (listing, session date) for prices, after resolution (A.3, A.4);
  - (date, currency or pair) for FX (A.3, A.4);
  - a repeated read column (B.2);
- the Frankfurter envelope rule (B.1);
- the `securityType` field name (answer (d)).

The PM sets the timing of that version. Any version re-issues the registries before its label move
(§11 item 35).
