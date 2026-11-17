# CP7 F1 O-7 and O-6: where each claim-limit field comes from, and the claim block over a real NAV in each state (2026-11-10)

**Author:** quant-analyst. **Asked by:** the main session (PM), after the owner said "Start O-7". **Status:** a method and wording ruling,
written before any code exists.

**What it rules on:**
- the sources and text forms of the claim-limit fields, design 7.4 S1 to S5 and C1 to C7, filled for a `REAL_SOURCE` root;
- O-6: the block over a real NAV that is `LIMITED` or `INSUFFICIENT_DATA`.

**What I read and checked myself.** I treated the engineer's survey (`implementation/CP7_F1_O7_LINEAGE_EXTRACTION_PLAN.md`) as a map, not
as evidence. I verified every source below in the code, the stored files or the engine run in memory (no PostgreSQL, nothing written):
- `src/marketdata/claim_render.py` and `claim_limits.py`;
- `src/real_service/service.py` (`_write_root`, `_stage_real`), `worlds.py`, `src/persistence/real_proposal.py` (snapshot members and
  records), `src/web_api/real_scoped_contract.py` (`DECIMAL`);
- `src/performance/engine.py`, `results.py`, `valuation.py`, `manifest.py`, and an in-memory `compute` over `tests/product/performance_kit.py`;
- `src/marketdata/market11.py` (`UNBUILT_1_16`), `profiles.py`, `adapters/daily_csv.py`, `canonical.py`, `port.py`, `reconciliation.py`;
- migration `0009` (`md_file`);
- `data/marketdata/SOURCES.json`, and the manifests and payloads of `alphavantage.us/quote/2026-10-01/AAPL_compact.csv`,
  `openfigi/identity/2026-10-23/AAPL_UW.json` and `calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json`;
- `methodology/CP2_MARKET_DATA_CONVENTIONS.md`: Ruling 3.2 items 1 to 6, Ruling 5.2's `s(ℓ, D)`, and Ruling 6.5 items 1, 2, 5 and 6.

The engineer's table is accurate as a survey of where things are stored. **I correct one reading of it:** the V1 statement *can* be
supported from stored facts in the HG4 case. See §3.3.

## 0. The answers in short

1. **Fields.** §2 gives every field's source and exact text form. Five fields are new and two are renamed, because the single
   `session_date` cannot be true in both S1 and S3 (§4).
2. **Ruling 3.2 item 5 is not a precondition** for showing the real block at R8. The block must then say something narrower. Three statements
   change (C-1, C-2, C-6), plus the S4 text. Their exact text is in §5. **The block is shown only if the preconditions of §3.4 hold. Otherwise
   it refuses.** No caveat that changes the conclusion is softened.
3. **The shared `session_date` is split.** S1 carries the price session and the missed-session count. S3 carries the valuation date (§4).
4. **O-6** (§6):
   - **`LIMITED`** shows the normal block. With §4's split it is true as written.
   - **`INSUFFICIENT_DATA`** shows a **withheld variant**: the same twelve ids, and no sentence about a close, a holding value or a NAV value.
   - **An unknown state** refuses.
5. **`file_hashes`** names **every file of M** (the snapshot's members), not only the files consumed (§7).
6. **Seven points** of the design, the docstring, the claim items and the plan are contradicted. They are listed in §8.
7. **Five questions** need an owner or design decision (§10). The block cannot be built until Q1 is answered.

## 1. Rules for every field

- **Three homes, and only three.** A field is read from one of these, and from nothing else:
  - **(I)** the issued document (`archive.issued`, parsed);
  - **(R)** the stored response (`archive.response`, parsed);
  - **(K)** a stored **claim record** written at create from the values the computation used. Its home, whether the response, the
    envelope or the engine, is Q1.

  No slot value is read from a code constant at read time, nor from a clock, the network or a default. The preconditions (§3.4) compare
  stored values with constants of the method (the claim list's convention set, the enum texts, the Test V4 marker). P-5 alone also reads the
  engine's present build state, by that marker, at create and at every read, because C-1 and C2 state in the present tense that no V4 record
  exists (corrected 2026-11-10; post-build note §5.2).
- **(K) is a copy, not a second computation.** It is written inside the create transaction, from:
  - the md rows and the snapshot the create lease already reads;
  - the profile table at create, whose set version the snapshot's `profile_digest` holds (it does not hash `call_adjustment`; corrected
    2026-11-10, see `CP7_F1_O7_POSTBUILD_WORDING_CHECK_2026-11-10.md` §2).

  It is immutable with the root. **Reproduce must rebuild (K) from the same inputs and compare it byte for byte with the stored one.** A
  difference is `RESULT_DIFFERS`, as for the issued bytes. Without that, the reproduce check would not cover these copied facts (P9).
- **Text forms.** The extractor copies stored text. The only forms it applies are those this note names:
  - **an integer** becomes base-10 digits, with no sign, separator or padding;
  - **a list** is handed to the renderer, which joins it with ", " in stored order. An empty list refuses;
  - **a file entry** is three stored strings joined with single spaces (§7);
  - **a stored decimal** is copied verbatim and never padded. Ruling 2.2 (1.12) item 7 makes "500" and "500.00" the same assertion. The
    stored and the key-figure form is "500".
- **Any field missing, malformed, or ambiguous refuses** with `ClaimRenderError`. "Ambiguous" means two candidate rows, or two values where one
  is required. Nothing is defaulted, and as-of is never used in place of a price date.

## 2. The fields: source and exact text form

Fields marked **new** or **renamed** follow from §4 and §5. "One row" means: exactly one `metric_id`/`view` row in `issued.metrics`. Zero
rows or two rows refuse.

| Slot | Field | Source | Exact text form | Cross-check (refuse on difference) |
|---|---|---|---|---|
| S1, S3 | `valuation_date` (**renamed** from `session_date`) | (R) `response.as_of` | ISO date as stored, `2026-09-30` | equals (I) `manifest.as_of` |
| S1, S5 | `price_session_date` (**new**) | (I) the one `holding_value`/`REPORTING` row, lineage pair `price_date_used` | ISO date as stored | the row's subject `listing` equals `response.opening_positions[0].listing_id`. **Absent:** see §6 |
| S1 | `missed_sessions` (**new**) | the same row, lineage pair `price_missed_sessions` | digits as stored, `0` | present whenever `price_date_used` is |
| S1, S3, C6 | `ledger_quantity` | (R) `response.opening_positions[0].quantity` | verbatim, `10` | exactly one opening position |
| S1 | `source_name` | (K) the snapshot `source_records[]` entry whose `source_id` equals the valuing reading's `source_id`: its `name` | verbatim, `Alpha Vantage free tier (US daily history)` | exactly one such record |
| S1 | `exchange_mic` | (I) the holding row's `freshness.entries[]` entry of kind `EXCHANGE_CALENDAR`: its `mics` | the **single** element, `XNAS` | exactly one entry and exactly one MIC. The engine lists "the MICs the calendar governs among the holdings" (`results.py:79`), and a one-holding root has one |
| S1 | `vendor_call` | (K) the valuing file's `md_file.manifest` `request` pair `function` | verbatim, `TIME_SERIES_DAILY` | exactly one `function` pair |
| S1 | `documentation_reference` (**new**, in place of `documentation_reading_date`, under Q2 option (a)) | (K) the profile's `call_adjustment[<vendor_call>].reference` for the file's `source_id`, copied when (K) is built at create from the profile table the computation used; from then on protected by the seal and by reproduce's byte comparison of (K). The snapshot's `profile_digest` does not hash it; it binds it only through `PROFILE_SET_VERSION`, whose counter moves with any `call_adjustment` change (corrected 2026-11-10, post-build note §2) | verbatim, `PD-0066 decision 3` | the profile's status for that call is `DECLARED`. See §3.4 P-2 |
| S1, S2, S5 | `adjustment_label_source` | (K) the valuing reading's `md_quote.lineage.adjustment_label_source` | **verbatim, the whole string:** `PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED` | it ends `:DECLARED` (P-2) |
| S3 | `reporting_currency` | (R) `response.reporting_currency` | `USD` | equals (I) `manifest.reporting_currency` |
| S3 | `opening_cash` | (R) `response.opening_cash.amount` | verbatim, `500`. **Not padded.** | `opening_cash.currency` equals `reporting_currency` |
| S3 | `metric_state` | (I) the one `portfolio_value`/`REPORTING` row: `state` | `AVAILABLE` / `LIMITED` / `INSUFFICIENT_DATA` | any other value refuses (§6) |
| S3 | `freshness` | the same row: `freshness.summary` | as stored, `CURRENT` | none |
| S3 | `delay_status` | the same row: `freshness.delays` | list, `END_OF_DAY` | non-empty |
| S3 | `reconciliation_status` | (K) the reconciliation status of the market-data lookup whose reading values the holding (`QuoteLookup.reconciliation.status`, `port.py:77`) | as stored, `SINGLE_SOURCE` | the lookup's selected reading has the same session date as `price_session_date`. Must equal `SINGLE_SOURCE` (P-3) |
| S3w | `nav_cause` (**new**, withheld variant only) | (I) the NAV row: `reason` if not null, else its `details` | the code, `MISSING_PRICE_HISTORY`; or the details list | not both empty (an `INSUFFICIENT_DATA` metric names its causes, `results.py`) |
| S4 | `file_hashes` | (K) every member of the snapshot, in stored order: `data_kind` from its `md_file` row, `source_id`, `payload_sha256` | list of `"<data_kind> <source_id> <payload_sha256>"` | every file in `manifest.data_set_refs[].consumed` is a member |
| S4 | `ledger_version` | (I) `manifest.ledger_version` (int) | base-10 digits, `2` | equals `archive.ledger_pin` and `response.ledger_version` |
| S4 | `convention_ids` (**renamed** from `convention_id`) | (I) `manifest.conventions`: pairs `market_data.convention_set`, then `performance.convention_set` | list, `market-data/1.16, performance/1.12` | each pair present once. The first equals `market-data/1.16` (P-6) |
| S5 | `adjustment_label_status` | (K) the valuing reading's `md_quote.lineage.label_status` | as stored, `UNVERIFIABLE` | must equal `UNVERIFIABLE` (P-1) |
| S5 | `retrieval_time` (**new**, replacing the composed `exposure_window`) | (K) the valuing file's `md_file.manifest` key `retrieval_time`: the **JSON string**, not the `timestamptz` column | verbatim, `2026-10-01T04:53:50Z` | equals the reading's `lineage.retrieved_at` |
| S5 | `v1_statement` | (K) under P-4 only: no member of M has `data_kind` `CORPORATE_ACTION` | the fixed text `no V1 event in M` | any other M refuses (§3.3) |

`exposure_window` is no longer a field. S5's template writes `E({price_session_date}, {retrieval_time})`, so the extractor composes nothing.
"The valuing reading" and "the valuing file" mean the reading of the listing at `price_session_date` that the lookup selected, and the file
it came from. (K) records which one it is. They are not inferred at read time.

## 3. The fields with no stored source, and Ruling 3.2 item 5

### 3.1 `documentation_reading_date`

It is stored nowhere as data. The date 2026-10-24 appears only in a code comment (`profiles.py:294`), in PD-0066 and in the design. What
**is** data is the reference `CallAdjustment.reference` = `PD-0066 decision 3` (`profiles.py:86, 304`), bound to the context only through the
profile set version in the snapshot's `profile_digest` (corrected 2026-11-10, post-build note §2).
- **The date may never be a template constant.** The claim would then state a fact no stored value supports (P9).
- **Option (a), method-sufficient for R8:** C-1 cites the record instead of the date: "as the owner read it (`PD-0066 decision 3`)". The
  decision record states the date, so the chain is auditable. Dropping the date from the sentence drops precision, not a caveat: the
  conclusion "a vendor's declaration, not a verification" is unchanged (P3).
- **Option (b):** store the date as profile data, for example a `read_on` field of `CallAdjustment`, and keep "on {date}". That changes the
  profile digest, which is cheap only before the real publish (R8 step 4), because the snapshot's content hash covers it.
- Which one is Q2.

### 3.2 `reconciliation_status`

It is computed by the market-data lookup (`reconciliation.py`, `SINGLE_SOURCE` at "the only upstream reporting") and is not written into
the issued document.
- **The method's own status must be copied.** It must not be derived from the registry or the member count, because that would be an
  interpretation (Ruling 4.6's safeguards can also turn two sources into one).
- So it goes in (K), from the lookup that valued the holding, cross-checked by session date (§2).
- Having the engine state it is the better long-term home (Q1 option C).
- With no value used there is no status (`reconciliation.py`: "no value and NO reconciliation status"). That is the withheld case (§6).

### 3.3 `v1_statement`: supported in the HG4 case, by M's composition

The engineer reads a constant "no V1 event in M" as asserting a check the system did not make. **That holds for Test V1, not for this
statement.**
- Ruling 3.2 item 5 case 3 is defined on **records**: "`M` holds no V1 event of ℓ with `X > d_p`".
- A V1 event is a `SPLIT` record in M from a filing-role source (item 1). Such a record can only be in a `CORPORATE_ACTION` file.
- So if no member of M has `data_kind` `CORPORATE_ACTION`, case 3 holds by definition. No test is run, and nothing is inferred from absence
  in the world. Item 5 itself says the statement is "about `M` after `d_p`, never about the world".
- M's members and their kinds are stored facts: the snapshot's members, and `md_file.data_kind` of each.
- **Rule:**
  - the statement is `no V1 event in M` **only** under P-4;
  - an M that holds any `CORPORATE_ACTION` file **refuses** the block, because cases 1 and 2 need item 5 built and Ruling 3.2 item 6's
    hand check made;
  - for the HG4 M (PD-0066 decision 2, option (a)) the item 6 check is vacuous, as item 6 says.

### 3.4 Preconditions of the fixed claim text (each checked when (K) is built; any failure refuses)

The C-items and parts of S1 are **fixed text**. Each is true only under a stored state. The block may be shown only when every one holds.

| # | Precondition | Source | Fixed text that depends on it |
|---|---|---|---|
| P-1 | the valuing reading's label status is `UNVERIFIABLE` | (K) | C1 ("It is UNVERIFIABLE", twice) |
| P-2 | the label source ends `:DECLARED`, and the profile's status for the call is `DECLARED` | (K) | C-1 ("That is the vendor's declaration … as the owner read it"). A `MEMORY` source would need different wording (my R7 ruling, O-2) |
| P-3 | the reconciliation status is `SINGLE_SOURCE` | (K) | C2 ("single-source"), C3 ("compared with any other source. There is none") |
| P-4 | no member of M is a `CORPORATE_ACTION` file | (K) | S5 V1 statement; C-1 ("no V1 event … exists") |
| P-5 (superseded below the table, 2026-11-10) | the manifest's `open_items` still holds the `UNBUILT_1_16` line for Ruling 3.3 / Test V4 | (I) `manifest.open_items` (each line is prefixed `market_data: `; I checked in memory that the line reaches the issued manifest) | C-1 ("no V4 record exists"), C2 ("unless a Test V4 record exists") |
| P-6 | `market_data.convention_set` = `market-data/1.16` | (I) | every item: the list is 1.16's |
| P-7 | `market_origin` = `REAL_SOURCE`, with one position and one cash balance | (R) | all real-source sentences (design 4.3) |
| P-8 | the NAV state is one of the three | (I) | §6 picks the variant |
| P-9 (added 2026-11-10, post-build note §5.1) | exactly one `holding_value`/`NATIVE` row, and its `currency` equals `reporting_currency`: no FX leg exists | (I), checked for **both** variants, before the variant is picked | S1 ("is {quantity} x p"), S3 ("is {quantity} x p + {cash}"), which state no FX conversion |
| P-10 (added 2026-11-10, post-build note §5.1) | withheld variant only: (K) `valuing` is empty, and no `holding_value` row carries a `price_date_used` lineage pair | (K) and (I) | withheld S1, S2, S5 ("no close values the holding", "no reading values the holding"), C2 ("That any close was used") |

**P-5 as corrected 2026-11-10 (post-build note §5.2), replacing the row above:** (i) the stored manifest's `open_items` holds exactly one line
that begins `market_data: ` and contains `Ruling 3.3, Test V4`; and (ii) the engine's `market11.UNBUILT_1_16` holds exactly one line containing
`Ruling 3.3, Test V4`. (i) is read from (I); (ii) is the engine's present build state, read deliberately at create and at every read.

### 3.5 Ruling 3.2 item 5: **not a precondition for R8. The block says something narrower.**

Item 5 asks the **valuation's lineage** to state three things for every RAW reading used. The engine says it does not
(`market11.py`, `UNBUILT_1_16`), and that line reaches the issued manifest's `open_items`, so the gap is disclosed (P9). For the
single-date check:
- **Label status and source:** item 5's own text says they are "held only in the reading's own ingest lineage". Copying them into (K) copies
  the stored statement. No new fact is made.
- **`E(d_p, R)` as a date list:** that is a calendar computation (`N(R)`), which belongs to the method code, not to an extractor. The narrower
  claim states the window by its two stored arguments, `E(d_p, R)`. The decision it serves, whether a V1 event lies in E, does not arise under
  P-4. The list is precision, not a caveat.
- **The V1 statement:** case 3 only, under P-4 (§3.3).

**What the narrower block must not do:** say that "the lineage" states these things, because the engine's lineage does not. C-6 is reworded
to name the stored record (§5).

**Item 5 stays an open item** of the engine and of the HG4 package. If Q1 chooses option C (the engine builds item 5 first), C-6 goes back to
"The lineage states", with E as a list.

## 4. The shared `session_date`: split it

- **The two dates mean different things.** The price session `d_p` (`price_date_used`) is the session whose close values the holding.
  `as_of` is the date of the valuation (Ruling 5.2: the last print at or before D).
- **They differ whenever a session is missed.** That includes `AVAILABLE` + `STALE_DATA` with one missed session, not only `LIMITED`. With one
  field, C-1 or C-2 is false.
- **S1:** "on {valuation_date}" for the value, and "for the {price_session_date} … session" for the close. It adds the missed-session count
  `s(ℓ, D)` (Ruling 5.2: sessions `d` with `last_print < d ≤ D`) as stored, so a stale close is visibly stale in the same sentence.
- **S3:** "on {valuation_date}".
- **S5:** `E({price_session_date}, {retrieval_time})`. Item 3 defines E on the reading's session `d_p`, not on D.
- **On a fresh price** both dates are equal and the count is `0`. The sentence stays true, if slightly redundant.

## 5. The new statements (exact EN text; `claim_limits.py` and `claim_render.py`)

These replace the statements of C-1, C-2 and C-6, and the S4 text of `claim_render._s_texts`, for a `REAL_SOURCE` root in states
`AVAILABLE` and `LIMITED`. `required_terms` are unchanged. All other items are unchanged.

- **C-1** (S1), under Q2 option (a):

  > The market value of the holding on {valuation_date} is {quantity} x p. Here p is the close {source} delivered for the {price_session_date} {exchange} session through {call}; {missed_sessions} sessions of that exchange lie after that close, up to {valuation_date} inclusive. p is read as as-traded (RAW) on the strength of the vendor's documentation of that call, as the owner read it ({documentation_reference}). The label source is {label_source}. That is the vendor's declaration, not a verification: no V1 event and no V4 record exists for this file.

  Under Q2 option (b), replace "as the owner read it ({documentation_reference})" with "as the owner read it on {documentation_reading_date}".
- **C-2** (S3):

  > The NAV in {reporting_currency} on {valuation_date} is {quantity} x p + {cash}.
- **S4** (`claim_render._s_texts`):

  > The inputs are named: the files of M with their hashes ({file_hashes}), L (the ledger version {ledger_version}) and the convention sets {convention_ids}. {SEAL_LIMIT}

  `SEAL_LIMIT` is unchanged. My PD-0079 O-1 recommendation on it still stands, separately.
- **C-6** (S5), under Q1 options A or B:

  > The stored record of this result states the label status ({label_status}) and the label source ({label_source}) of the reading used, the exposure window E({price_session_date}, {retrieval_time}), whose second argument is the file's retrieval time, and the statement of V1 events in M ({v1_statement}). The session list of that window is not stated: market-data/1.16 Ruling 3.2 item 5 is not built in the engine.

  Under option C, once item 5 is built: "The lineage states the label status ({label_status}), the label source ({label_source}), the exposure window {exposure_window}, and the statement of V1 events in M ({v1_statement})." Here `{exposure_window}` is the engine's stated date list.

`SLOT_FIELDS` becomes:

```
S1: valuation_date, price_session_date, missed_sessions, quantity, source, exchange, call, documentation_reference (or documentation_reading_date), label_source
S2: label_source
S3: reporting_currency, valuation_date, quantity, cash, state, freshness, delay, reconciliation
S4: file_hashes, ledger_version, convention_ids
S5: label_status, label_source, price_session_date, retrieval_time, v1_statement
```

## 6. O-6: the block in each state of the real NAV

| NAV state | Block | Why |
|---|---|---|
| `AVAILABLE` (with or without `STALE_DATA`) | the §5 block | true as written, with §4's split |
| `LIMITED` (2 to 4 missed sessions, Ruling 1.4 item 2) | the **same** §5 block | Every sentence is true. S3's state sentence (`LIMITED`, freshness `STALE`) sits in the same item as the NAV formula, and S1 states the stale session and its missed count. The stale weight is stated beside the number in the key figures (F-1). No sentence states a NAV number, so no further qualifier is needed here. |
| `INSUFFICIENT_DATA` | the **withheld variant** below | no close values the holding, and there is no `price_session_date`, label of a reading used, `E` or reconciliation status. C-1, C-2, C-4 and C-6 would each state something false. Only when (K) holds no valuing reading (P-10, added 2026-11-10); otherwise refuse. |
| anything else, or two NAV rows | refuse | P8, and the no-fallback rule |

**The withheld variant.** Same twelve ids, so the client's strict reader and the contract's item check keep their shape. Exact EN text.
Slots: `valuation_date`, `reporting_currency`, `state`, `nav_cause`, `freshness`, `delay`, the S4 slots, `quantity`. Preconditions
P-6 to P-8 only, plus P-9 and P-10 (added 2026-11-10, post-build note §5.1).

| Id | Text | Required terms |
|---|---|---|
| S1 | No holding value on {valuation_date} is stated: no close values the holding, and the NAV's state is {state}. | `No holding value` |
| S2 | No label source is stated: no reading values the holding. | `No label source` |
| S3 | No NAV in {reporting_currency} on {valuation_date} is stated. The state is {state}, cause {nav_cause}, freshness {freshness}, delay {delay}. | `No NAV`, `freshness`, `delay` |
| S4 | as §5 | as §5 |
| S5 | No label status, exposure window or V1 statement is stated: no reading values the holding. | `No label status` |
| C1 | That any price series is verified as-traded, or that any of its labels, split or dividend component, is verified. | `split`, `dividend component`, `verified` |
| C2 | That any close was used, or that any close is the exchange's official closing-cross price. | `closing-cross` |
| C3 | That any close was compared with any other source. There is none for this market. | `compared`, `other source` |
| C4, C5, C6, C7 | unchanged (N-6, N-7, N-8, N-9) | unchanged |

- **Why the C-items change and do not simply drop.** Each original C-item's second sentence asserts a property of p or of the reading used
  ("It is UNVERIFIABLE", "It is single-source and unchecked"). With no reading used, no stored value supports that.
- **The limits themselves stay.** Each variant still names what is not claimed.
- **No caveat that changes the conclusion is lost.** The conclusion is "no NAV is stated", and every remaining claim is a statement of
  absence. The partial figure stays in the key figures, under its own F-2 rules.
- **Quant ids for `check_block`:** `C-1X` (S1), `C-2X` (S3), `C-6X` (S5), `N-1X` (C1), `N-4X` (C2), `N-5X` (C3), plus N-6 to N-9 and C-5.
  S2's text is the renderer's own, as today. The coverage check of the variant is over this set.

## 7. `file_hashes`: every file of M

C-5 says "the files of M". That is the snapshot's members (= the release's files), not the subset the manifest lists as consumed:
- The V1 statement and P-4 are claims about **M**. A member that is not consumed, such as a corporate-action file, is exactly what a reader
  must see named.
- The kit run shows a `QUOTE` `consumed` list can be empty while M holds the price file.
- The consumed lists stay in the raw document. The cross-check of §2 ties them to M.

**Entry form:** `<data_kind> <source_id> <payload_sha256>`, in snapshot member order.

## 8. What this ruling contradicts (to be corrected)

1. **`claim_render.py` docstring**, "A SLOT IS FILLED FROM ITS LINEAGE FIELD and from nothing else". "Lineage" must be defined as the three
   homes of §1. Fields come from (I), (R) and (K), and the preconditions of §3.4 are checked before any text renders.
2. **`SLOT_FIELDS` and `lineage_from_slots`.** `session_date` filling S1 and S3 with one value is withdrawn (§4). The new map is in §5.
3. **`claim_limits.py`.** C-1, C-2 and C-6 statements and slots change (§5), the withheld variants are new (§6), and C-5's slot becomes a
   list of convention sets. **This also amends the wording of `market-data/1.16` Ruling 6.5 item 6 C-1, C-2 and C-6**, as they render on the F1
   path. The amendment goes into the next market-data change note. No value, state or method moves.
4. **Design 7.4:**
   - S1 "the 2026-09-30 XNAS session" is now the price session, and is separate from the valuation date;
   - S2 "It is `DECLARED`": the slot holds the whole stored label-source string, which ends `DECLARED`;
   - S3 "`10 x p + 500.00`": the stored and rendered text is `500`;
   - S4 "this convention id": both convention sets, and all files of M with kind and source;
   - S5 "the lineage states the exposure window `E(2026-09-30, R)` … and 'no V1 event in `M`'": the stored record states them, E is given by
     its arguments, and the V1 statement is conditional on P-4;
   - the design needs a paragraph for O-6's withheld variant, and for the preconditions.
5. **`market-data/1.16` Ruling 6.5 item 6 C-6** writes `E(2026-09-30, R)` = {2026-10-01, 2026-10-02} as a list. Until item 5 is built the
   rendered text gives the arguments only (§3.5). The list is still correct. It is derived by hand in §9.
6. **The engineer's plan** §3 and §8 item 5 read the V1 statement as unsupportable. It is supported under P-4 (§3.3). C-1's "no V4 record"
   is supported under P-5.
7. **My R7 client ruling** (`CP7_F1_R7_CLAIM_WORDING_CHECK_2026-11-07.md`): the client templates and the `PHRASES` table were written for the old
   slot set. S1, S3, S4 and S5 at all depths and in both locales need re-wording, and the withheld variant needs client text. **That needs a
   new wording check once Q1 and Q2 are answered and the server statements are built.** I have not written those strings here.

## 9. Hand-derived expected values

### 9.1 The HG4 case, from the stored files

Assumed inputs: the owner's create of quantity 10, cash 500 USD, as of 2026-09-30, over M = the three members of design 7.1 R4b:
`AAPL_compact.csv`, `AAPL_UW.json`, `NYSE_2025_2026.json`.

**Key-figure values.** The price file's row `2026-09-30` has close `c` (the vendor value is redacted in the public copy, PD-0083). So:
- p = c;
- holding = 10 × c;
- NAV = 10 × c + 500 USD.

The stored texts are the decimal texts of those two values (Ruling 2.2 (1.12) item 7). For R8's oracle, compare numerically.

**Missed sessions and freshness.** The NYSE calendar file lists 2026-09-30 as a session. I checked all 501 sessions of 2025 and 2026 against an
independent list (weekdays less the published holidays and the 2025-01-09 closure), with no difference. The last print is 2026-09-30 = D, so
`s(ℓ, D)` = **0**. The state is `AVAILABLE`, freshness `CURRENT`.

**Exposure window.**
- R = 2026-10-01T04:53:50Z, which is 2026-10-01 00:53:50 in New York (EDT, UTC−4), so the local date of R is r = 2026-10-01 (Thursday).
- `N(R)` = the first session after r = **2026-10-02** (Friday, a session). The calendar covers to 2026-12-31, so `N(R)` is determined.
- E(2026-09-30, R) = {sessions X : 2026-09-30 < X ≤ 2026-10-02} = **{2026-10-01, 2026-10-02}**. This agrees with Ruling 6.5 C-6.

**Field texts:**

| Field | Text |
|---|---|
| `valuation_date` | `2026-09-30` |
| `price_session_date` | `2026-09-30` |
| `missed_sessions` | `0` |
| `ledger_quantity` | `10` |
| `source_name` | `Alpha Vantage free tier (US daily history)` |
| `exchange_mic` | `XNAS` |
| `vendor_call` | `TIME_SERIES_DAILY` |
| `documentation_reference` | `PD-0066 decision 3` |
| `adjustment_label_source` | `PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED` |
| `reporting_currency` | `USD` |
| `opening_cash` | `500` |
| `metric_state` | `AVAILABLE` |
| `freshness` | `CURRENT` |
| `delay_status` | `END_OF_DAY` |
| `reconciliation_status` | `SINGLE_SOURCE` |
| `file_hashes` | `QUOTE alphavantage.us 066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb`, `IDENTITY openfigi b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc`, `CALENDAR calendar.manual 4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef`, in the snapshot's member order |
| `ledger_version` | the real pin, as digits |
| `convention_ids` | `market-data/1.16`, `performance/1.12` |
| `adjustment_label_status` | `UNVERIFIABLE` |
| `retrieval_time` | `2026-10-01T04:53:50Z` |
| `v1_statement` | `no V1 event in M` |

The hashes are the manifests' `file_sha256`, read from the store. The real pin exists only at R8.

### 9.2 The kit cases, for the extractor tests

**Superseded 2026-11-10 (post-build note §5.1):** under P-9 an H@XHKG root refuses, so the AVAILABLE and LIMITED cases move to AAPL@XNAS
(values in the post-build note §5.1), and H@XHKG becomes a P-9 refusal case. The original text follows, kept for the record.

These use `performance_kit.world_w`, listing H@XHKG, with USD 500 and 10 H. FX rates are not restated here: the tests compare dates, states and
lists, not FX-derived amounts.
- **`AVAILABLE`, as of 2025-03-28.** The last print is 2025-03-28, so `price_session_date` = `valuation_date` = `2025-03-28` and
  `missed_sessions` = `0`. Freshness `CURRENT`, delay `END_OF_DAY`, `exchange_mic` `XHKG`.
- **`LIMITED`, as of 2025-04-02, last close 2025-03-28.** The HKEX sessions after 03-28, up to 04-02, are 03-31, 04-01 and 04-02 (04-04 is
  Ching Ming), so `missed_sessions` = **3** (2 to 4 gives `LIMITED`, Ruling 5.2).
  - `price_session_date` = `2025-03-28`, which is not `valuation_date` `2025-04-02`. **This is the test that the split holds.**
  - Freshness `STALE`, state `LIMITED`, reason `STALE_DATA`.
- **`INSUFFICIENT_DATA`, as of a date before the listing's first close** (the plan's probe, 2025-01-29 on the midpoint kit). There is no
  `price_date_used`, and `nav_cause` is `MISSING_PRICE_HISTORY`. Freshness is `UNKNOWN`. The delay is the union over the legs (Ruling 1.6): `["UNKNOWN"]` only where there is no FX leg; on
  H@XHKG with a fixing on the as-of it is `["END_OF_DAY","UNKNOWN"]` (corrected 2026-11-10; the built test uses AAPL@XNAS as of 2025-03-27,
  accepted in the post-build note §3). The withheld variant renders. A test that
  feeds the §5 block instead must refuse.
- **`ledger_version`:** the kit's `Ledger.version` for two events is `2`, so the text is `2`.

## 10. Questions for the owner or the design

**Q1: where the claim record (K) lives. Method requirements for any option:**
- it is written in the create transaction from the values used;
- it is immutable and sealed with the root;
- reproduce rebuilds and compares it;
- the read path needs no lease that reads md rows.

**Options:**
- **(A)** an object in the stored response. It needs no SQL. The response then carries copied md facts.
- **(B)** an object in the envelope. It needs SQL: the envelope key set is exact in `rw_check_real`, so the installer artifacts change before
  R8.
- **(C)** the engine states them first: Ruling 3.2 item 5 built, plus a reconciliation status in the holding lineage. This is a market-data and
  performance increment, with new digests. C-6 keeps "The lineage states", with E as a list.

**Recommendation:** (A) for R8, with (C) as the later home. PD-0073 chose "stored result + seal" over a manifest field for the same kind of
fact.

**Q2: the documentation-reading date.**
- **(a)** cite the record, `PD-0066 decision 3` (recommended: no digest change);
- **(b)** store the date as profile data before the real publish (the profile digest and its tests change);
- **(c)** keep a template constant. **Not acceptable (P9).** Listed only so the choice is complete.

**Q3: a real create whose claim record cannot be built** (a precondition fails, or a field is missing).
- **(a)** refuse it before the seal, with whole rollback, as FF1-C08 does for a service refusal (recommended);
- **(b)** commit it, and leave the root unreadable.

**Method requirement either way:** no real result is ever shown without its block (P3). Option (b) gives the "UNKNOWN for ever" root of the
plan's §6. A new refusal code would be a contract-surface choice.

**Q4: the claim block over a suppressed real NAV.**
- **(a)** the withheld variant of §6, keeping the twelve ids (recommended);
- **(b)** no block, and the root is unreadable. The partial figure PD-0035 §2 requires would then never be shown on a real root.
- **(c)** a block with a different item set. This changes the client reader and the contract's item check.

**Q5: the slot renames** (`valuation_date`, `price_session_date`, `convention_ids`, and the S5 arguments) change the server's `SLOT_FIELDS`,
the client's mirror and its test pin.
- Confirm they land in one change with the client's re-worded strings, followed by a new client wording check (§8 item 7).
- The alternative is to keep the old names with new meanings. **That is not recommended:** `session_date` would keep meaning two dates.

## 11. Not done here

- No code, no tests and no change to `src/`, `implementation/` or the design. Those owners apply §5 and §8 after Q1 to Q5.
- No client strings for the new S1, S3, S4 and S5 or for the withheld variant. They follow once the server statements are fixed (§8 item 7).
- Ruling 3.2 item 5 stays unbuilt and stays listed in the manifest. The HG4 package should state it as an open item, with this note's
  narrower wording as the disclosure.
