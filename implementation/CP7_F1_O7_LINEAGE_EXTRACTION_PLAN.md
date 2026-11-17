# CP7 F1 O-7: the lineage extraction for real roots (survey and plan)

> **CORRECTED AND SUPERSEDED, 2026-11-10 (after the Quant's ruling and PD-0082).** This survey went to the Quant, whose ruling
> (`methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md`) and the owner's answers (`decisions/product/PD-0082-o7-claim-record-and-suppressed-block.md`) decide what this plan left
> open. Where this file differs from them, they win. Corrections (the ruling's section 8 item 6):
>
> 1. **The V1 statement is supported.** Sections 3 and 8 (item 5) below read "no V1 event in M" as unsupportable from stored data. It is Ruling 3.2 item 5 **case 3**, defined on records: with
>    no `CORPORATE_ACTION` member in M it holds by definition (P-4), and the block refuses when M has one. C-1's "no V4 record exists" is supported by the manifest's open item (P-5).
> 2. **The shared `session_date` is split** (valuation date and price session, section 4's finding), and `documentation_reading_date` becomes `documentation_reference` (`PD-0066 decision 3`).
> 3. **Decided:** the claim record (K) lives in the stored response (option A, PD-0082 Q1); an unbuildable record refuses the create before the seal (Q3, code `RW_CLAIM_RECORD_REFUSED`);
>    over `INSUFFICIENT_DATA` the block is the withheld variant (Q4, O-6); `file_hashes` names every file of M; `exposure_window` is replaced by `retrieval_time` (the extractor composes nothing).
> 4. **Built** (same day): `src/marketdata/claim_record.py`, `claim_render.py`, `claim_limits.py`, `src/real_service/service.py`, `src/persistence/market_data_store.py`
>    (`read_release_files`), the client templates, and `tests/product/test_claim_record.py`. Design 7.4 is corrected in `CP7_F1_REAL_PATH_DESIGN.md`.
>
> The rest of this file is the survey as written, kept for the record of where each value was found.

Dated 2026-11-10. Author: the Engineer. **A survey and a written plan only: no change to `src/`, to tests or to any SQL.** Every statement
below was read in the code or run in memory (read-only probes in `$TMPDIR`, nothing stored). Where a choice is a method, wording or design
choice, it is marked **OPEN** and left to its owner (the Quant, the design or the owner). "Recommendation" is the Engineer's and decides nothing.

Sources read: `src/web_api/real_mode_routes.py`, `src/marketdata/claim_render.py`, `src/marketdata/claim_limits.py`, `src/real_service/service.py`,
`src/real_service/worlds.py`, `src/web_api/real_scoped_contract.py`, `src/web_api/real_launcher.py`, `src/persistence/real_fence_v1.sql`,
`real_workspace_v1.sql`, `real_proposal.py`, `src/performance/{engine,manifest,results}.py`, `src/marketdata/{manifest,contracts,canonical,market11,profiles}.py`,
`src/marketdata/adapters/daily_csv.py`, `data/marketdata/SOURCES.json`, a file manifest under `data/marketdata/files/alphavantage.us/`,
`implementation/CP7_F1_REAL_PATH_DESIGN.md` (7.1 R7/R8 rows, 7.4), `STATUS.md` (O-6, O-7).

## 0. Summary

1. `lineage_of(archive)` gets **only the stored bundle** (three byte strings, two digests, a revision id and a pin). It has no connection, no
   snapshot and no market-data row. At create time it is called after the COMMIT without a connection (`real_mode_routes.py:213`).
2. Of the 19 fields, **7 are already in the bundle** as text or as an ISO date, **3 more are in the bundle but are not text** (an int, two lists), **4 are in the context
   snapshot** (reachable only inside an admitted lease, not from the `Archive`), **4 are in `md_file`/`md_quote` rows** (readable only under an open
   `EXECUTE_CREATE`/`EXECUTE_REPRODUCE` lease) and **no row anywhere stores 3** (`documentation_reading_date`, `reconciliation_status`, `v1_statement`).
   Two more (`exposure_window`, `adjustment_label_status`) have their parts in the md rows and need a composition or a constant (see 2).
3. **The performance engine itself says it does not state several of them.** Its manifest open items (`marketdata/market11.py:116-133`,
   `UNBUILT_1_16`) say that "the lineage of a valuation does not state, for each RAW reading used, its label status and label source ... E(d_p, R) ... or the item 5
   statement of V1 events", and that the by-hand V1 check "is not recorded in this manifest". So five of the 19 fields have no source in the issued document **by the engine's own
   declaration**. `claim_render`'s docstring and design 7.4 assume the lineage carries them. That is a contradiction (section 8).
4. Whatever is not in the bundle must be **stored at create time** (the md-row facts exist only inside the create/reproduce lease) or the extraction
   cannot be built from `Archive` alone. Section 3 lists the options; the choice is not mine.
5. Over a **suppressed or LIMITED NAV** the extractor can hand over every S3 field, but `session_date` has no value when the price is withheld, and the renderer's S3/S1 text is
   unconditional. O-6 (the Quant) must rule before any real suppressed result is shown. Section 4.
6. A committed REAL create whose lineage cannot be filled becomes an **unreadable root that repeats UNKNOWN forever** (section 7). Recommendation: refuse it **before** the seal.

## 1. What `lineage_of` receives

The call site is one function, `block_for(origin, archive)` (`real_mode_routes.py:174-176`):
`lineage = lineage_of(archive) if origin.get("market_origin") == claim_render.REAL_SOURCE else None`, then `claim_render.render_claim_block(origin, lineage)`.
`origin` is `archive.origin`, the origin of the STORED response (`service.py:101-103`).

The object is `real_service.service.Archive` (`service.py:86-107`, frozen dataclass), built by `_archive_of(row)` (`service.py:110-113`) from the seven columns of the
SQL function `rw_archive` (`real_fence_v1.sql:538`), called by `RealWorkspaceService._archive` (`service.py:194-195`):

| field | type | content |
|---|---|---|
| `issued` | bytes | the performance service's canonical JSON (`ComputationResult.canonical_json()`, `service.py:323`): keys `manifest_id`, `manifest`, `result_digest`, `metrics[]` (the seal checks exactly these four, `real_fence_v1.sql:322`) |
| `response` | bytes | the persisted response (`service.py:253-256`): `portfolio_id`, `as_of`, `persisted`, `reporting_currency`, the synthetic flag, `origin`, `labels`, `name`, `operation_id`, `revision_id`, `ledger_version`, `opening_positions`, `opening_cash` |
| `envelope` | bytes | `real_envelope(...)` (`service.py:428-433`): `schema`, `scope`, flag, `owner_id`, `root_id`, `operation_id`, `revision_id`, `ledger_pin`, `context_id`, `generation`, `issued_sha256`, `response_sha256`, `manifest_id`, `result_digest`. The key set is exact in SQL (`real_fence_v1.sql:319`) |
| `issued_sha256`, `response_sha256` | str | digests of the stored bytes |
| `revision_id` | UUID | the revision |
| `ledger_pin` | int | the ledger version (`rw_revision.ledger_version`) |

Where it reaches the extractor:
- **Read**: `archive = unwrap(service.archive_read(...))` inside `run(work)` with an open executor connection (`real_mode_routes.py:240-243`), but `archive_read` returns only after its COMMIT, and `block_for` uses no connection.
- **Create / replay**: `outcome.archive` from `Created` (`service.py:116-122`, `_stage_create` returns `self._archive(...)` after staging or the replayed bundle, `:216`), then `committed(...)` runs **in a worker thread with no connection** (`real_mode_routes.py:213`).

Not in the object: the **context snapshot** (members, source records, registry digests; `rw_snapshot.snapshot`). It is read only by `store.admit` (returned as `lease.snapshot`,
`real_workspace_store.py:500-515`, used inside `_stage_create` and `_reproduce_*`), never by `archive_read` for the route. Not in it either: any `md_*` row.
The md rows are readable only through the thirteen lease-checked functions, and only when the lease purpose is `EXECUTE_CREATE` or `EXECUTE_REPRODUCE`
(`real_fence_v1.sql:572-590`: `PURPOSE` refusal otherwise). **`ARCHIVE_READ` cannot read them.** So the extractor cannot fetch anything at read time; everything it needs must already be in the bundle.

## 2. The 19 lineage fields (`SLOT_FIELDS`, `claim_render.py:51-60`)

The 19 distinct fields: `session_date`, `ledger_quantity`, `source_name`, `exchange_mic`, `vendor_call`, `documentation_reading_date`, `adjustment_label_source` (S1);
`reporting_currency`, `opening_cash`, `metric_state`, `freshness`, `delay_status`, `reconciliation_status` (S3); `file_hashes`, `ledger_version`, `convention_id` (S4);
`adjustment_label_status`, `exposure_window`, `v1_statement` (S5). `session_date`, `ledger_quantity` and `adjustment_label_source` fill more than one slot and must hold one value
(`lineage_from_slots`, `claim_render.py:128-145`). The renderer requires `type(value) is str` and non-blank; a non-empty list of non-empty strings is joined with ", " by the renderer itself (`_fill`, `claim_render.py:95-103`).

Column "form": **T** = already the text that must appear; **F** = needs formatting (named); **S** = a selection among stored values. "On the `_stage_real` path" = whether the REAL create
stores it anywhere today. Probes were run on `compute_for_portfolio` in memory over the `test_performance_midpoint` kit (never stored; `synthetic: false` over invented readings).

| # | field (slot) | where stored for a real root | form | on the `_stage_real` path |
|---|---|---|---|---|
| 1 | `session_date` (S1, S3) | `issued.metrics[]` row `holding_value`/`REPORTING`, `lineage` pair `price_date_used` (`engine.py:316-319`): ISO date text, **absent when the holding is withheld**. Alternatives: `response.as_of` (`service.py:253`), `manifest.as_of` | T (ISO text). **S**: which row (the listed holding) and which of two dates (price session or `as_of`) **OPEN** | yes, in `issued` |
| 2 | `ledger_quantity` (S1, S3) | `response.opening_positions[0].quantity` (`service.py:256`): canonical decimal text, e.g. `"10"` (contract `DECIMAL`, `real_scoped_contract.py:50,203`) | T | yes, in `response` |
| 3 | `source_name` (S1) | context snapshot: `source_records[].name` of the member's source (`alphavantage.us`: "Alpha Vantage free tier (US daily history)", `data/marketdata/SOURCES.json:92`); alternatives `upstream_provider` ("Alpha Vantage Inc.") or `md_quote.lineage.source` | T if one of those strings is accepted as the vendor name; which string is wording **OPEN** (Quant). **S**: the file-to-member-to-source chain | snapshot yes; **not in the bundle** |
| 4 | `exchange_mic` (S1) | `issued.metrics[]` `holding_value`/`REPORTING` `freshness.entries[]` of kind `EXCHANGE_CALENDAR`, key `mics` (a list; `results.py:113`; probe: `["XTST"]`) | **S** (the entry of kind `EXCHANGE_CALENDAR`) and a list; the join is done by the renderer | yes, in `issued` |
| 5 | `vendor_call` (S1) | the FILE manifest of the price file: `request` pair `function` = `TIME_SERIES_DAILY` (`data/marketdata/files/alphavantage.us/quote/2026-10-01/AAPL_compact.csv.manifest.json`), stored as `md_file.manifest` (`0009_market_data_files_and_releases.sql:26-36`). Also a code constant, `SourceProfile.function` (`profiles.py:297-298`) | T if read from `md_file.manifest`; **S**: pair lookup | md row only; **not in the bundle** |
| 6 | `documentation_reading_date` (S1) | **nowhere as data.** The reading of 2026-10-24 appears only in a code comment (`profiles.py:294`), in PD-0066 decision 3 and design 7.4. `CallAdjustment.reference` holds only the string `"PD-0066 decision 3"` (`profiles.py:86,304`). `SOURCES.json` `terms_check.checked_on` (`2026-10-01`) is the TERMS check, a different act | none | no |
| 7 | `adjustment_label_source` (S1, S2, S5) | `md_quote.lineage.adjustment_label_source` (`canonical.py:111`; value `PROFILE_CALL_ADJUSTMENT:<source>:<function>:<status>` built at `adapters/daily_csv.py:175-177`) | T | md row only. **The engine does not carry it** (`UNBUILT_1_16`, item 5) |
| 8 | `reporting_currency` (S3) | `response.reporting_currency` (`service.py:253`) and `manifest.reporting_currency`: `"USD"` | T | yes |
| 9 | `opening_cash` (S3) | `response.opening_cash.amount` (`service.py:256`): canonical decimal text, e.g. `"500"`. The contract refuses a fraction ending in `0`, so `"500.00"` cannot be stored (`DECIMAL`, `real_scoped_contract.py:50`) | T as stored. Design 7.4 writes `500.00`: a wording difference **OPEN** | yes, in `response` |
| 10 | `metric_state` (S3) | `issued.metrics[]` `portfolio_value`/`REPORTING` `state` (`AVAILABLE`, `LIMITED`, `INSUFFICIENT_DATA`) | T | yes |
| 11 | `freshness` (S3) | the same row, `freshness.summary` (`CURRENT`, `STALE`, `UNKNOWN`) | T | yes |
| 12 | `delay_status` (S3) | the same row, `freshness.delays` (a list, e.g. `["END_OF_DAY"]`; `["UNKNOWN"]` when suppressed; **empty for cash only**) | list; the renderer joins non-empty lists; an empty list is refused | yes |
| 13 | `reconciliation_status` (S3) | **not stored.** It is computed in the port lookup (`QuoteLookup.reconciliation`, `port.py:77`; `reconciliation.py:212-226`) and the performance engine does not write it into the issued document (no hit in `src/performance` for the status) | none | no |
| 14 | `file_hashes` (S4) | `issued.manifest.data_set_refs[kind=QUOTE].consumed[][0]` (the files CONSUMED, `manifest.py:490-545`) or the snapshot `members[].payload_sha256` (all files of M) | list of hash strings; the renderer joins. **OPEN**: S4 says "the files of M", the manifest holds the files consumed (probe: 2 QUOTE files), the snapshot holds every member. Also **S** (kind) | consumed: yes, in `issued`; members: snapshot only |
| 15 | `ledger_version` (S4) | `archive.ledger_pin` (int), `response.ledger_version` (int, `service.py:255`), `manifest.ledger_version` (int) | **F: an integer must be rendered as text.** The renderer refuses non-text | yes |
| 16 | `convention_id` (S4) | `issued.manifest.conventions` pair `market_data.convention_set` = `market-data/1.16` (probe), also `data_set_refs[].convention_set_id` | T. **S**: which pair | yes |
| 17 | `adjustment_label_status` (S5) | `md_quote.lineage.label_status` (`canonical.py:101`; set at ingestion, `UNVERIFIABLE` for these files, `daily_csv.py:170-173`) | T | md row only. **Not carried by the engine** (`UNBUILT_1_16`) |
| 18 | `exposure_window` (S5) | parts: `d_p` = field 1; `R` = `md_file.retrieval_time` / `md_quote.lineage.retrieved_at` (file manifest `retrieval_time` `2026-10-01T04:53:50Z`). The string `E(d_p, R)` is **composed** (design 7.4 writes `E(2026-09-30, R)`) | **F: composing a date and an instant into an interval string, and the instant's text form, are formatting.** **OPEN**, Quant | parts: field 1 in `issued`, `R` in an md row only. The engine does not state `E(d_p, R)` (`UNBUILT_1_16`) |
| 19 | `v1_statement` (S5) | **not stored, and not statable from stored data.** The engine says Test V1 is not built and that the by-hand check is not recorded in the manifest (`market11.py:117-121`); there is no corporate-action file in M | none | no |

So the counts: bundle and text (1 with a selection, 2, 8, 9, 10, 11, 16): 7. Bundle but not plain text (4 list, 12 list, 14 list, 15 int): 4. Snapshot only (3): 1. md rows only (5, 7, 17, plus `R` of 18): 3 (4 with `R`).
Nowhere (6, 13, 19): 3. Composed (18): 1.

## 3. Fields with no stored source, and what each would need (OPEN: not decided here)

For each: what is missing, and the kinds of answer. Whether the answer is a stored field, a constant, a different claim or a refusal belongs to the design, the Quant or the owner.

| field | what is missing | possible answers |
|---|---|---|
| `documentation_reading_date` | a stored date of the owner's reading of the vendor's live documentation (2026-10-24, PD-0066 decision 3) | (a) a new field on the profile's `CallAdjustment` (market-data code and its digests, Quant ruling on the label increment); (b) a field in a source record of the snapshot or in the publish record (changes the proposal format, the published snapshot and its content hash `context_id`); (c) a constant of the claim text (the claim then states a date no stored value supports: a P9 question); (d) leave the sentence out (a claim-limit change, Quant) |
| `reconciliation_status` | the lookup's status is not in the issued document | (a) the engine states it (a performance change, new digests); (b) it is derived from stored facts (one upstream in the used sources of the snapshot gives `SINGLE_SOURCE`): this is an interpretation, so a Quant ruling is needed first; (c) constant `SINGLE_SOURCE` (design 7.4 writes it as a fact of this slice): a P9 question |
| `v1_statement` | nothing records that Test V1 or the by-hand check of Ruling 3.2 item 6 was made, or what it found; the engine lists V1 as "not built" | the owner records the by-hand check in a stored record (publish record or a field of the context) and the extractor copies it; or the claim says "not checked" (a different statement, so a Quant ruling); a constant "no V1 event in M" would assert a check the system did not make, against the manifest's own open item |
| `adjustment_label_source`, `adjustment_label_status` | the engine does not carry them (`UNBUILT_1_16` item 5); they are in the md rows only | see the storage options below |
| `exposure_window` | `E(d_p, R)` is not stated; `R` is in md rows | storage options below, plus a Quant ruling on the text form |
| `vendor_call`, `source_name` | not in the bundle (md file manifest, snapshot) | storage options below |

**Storage options for everything that is not in the bundle** (3, 5, 7, 17, `R` of 18, the Quant-ruled items above). The md facts are readable only inside the create lease, and the create already holds the world in memory
(`_stage_real` builds `world` at `service.py:314` **before** `_write_root`, and `world.port.export()` holds the readings with their lineage).

| option | what changes | cost / limit |
|---|---|---|
| **A. A claim-lineage object in the `response`** written by `_write_root` / `_stage_real` from the world, sealed with the root (`rw_check_artifact` requires `response` = the stored `rw_root.snapshot_json` = `rw_revision.snapshot_json`, `real_fence_v1.sql:402-404`; it checks only specific keys of the response, not a closed key set) | `real_service/service.py` (build the object; `_write_root` writes the response before the compute, so the order of the two must be arranged), tests that pin the response shape | no SQL, no migration, no engine change. The root row then carries copied md facts (a stored value copy, not a computation). The response shape is a contract surface used by the PG tests: to verify before building |
| B. The same object in the `envelope` | SQL: the envelope key set is exact in `rw_check_real` (`real_fence_v1.sql:319`) | a change to the installer's SQL before R8 (no real install exists yet), a new `CHECKSUMS`/install fingerprint, and the R6 plan's pinned artifacts |
| C. The engine states them (Ruling 3.2 item 5) | `performance` (new rows or lineage pairs, new digests, a new method version), a Quant increment | the right home for label status and source, `E(d_p, R)` and the V1 statement, but it is a methodology and engine change, not O-7 |
| D. Read the snapshot in the read route | a new service call returning the snapshot with the archive (a second admission) | the snapshot lacks the md facts (it has members and source records only), so D does not cover 5, 7, 17 or `R` |

Recommendation: **A for the facts that already exist as stored values** (3, 5, 7, 17, `R`, 14's member list), **C for the facts that are statements the engine should make** (13, 19, `E(d_p, R)`), with the Quant ruling first.
Until then the extractor must refuse (section 6), which makes every REAL root unreadable: so O-7 cannot be closed by the Engineer alone.

## 4. The suppressed and LIMITED cases (for O-6)

Probed in memory (`compute_for_portfolio` over the midpoint kit, one position and cash, `ledger_pin` 2):

| case | `portfolio_value`/REPORTING | `holding_value` lineage | what an extractor would hand over for S3 |
|---|---|---|---|
| AVAILABLE, as of 2025-02-07 | `state` `AVAILABLE`, `value` `"875"`, `freshness.summary` `CURRENT`, `delays` `["END_OF_DAY"]` | `price_date_used` `2025-02-07`, `price_missed_sessions` `0` | `metric_state` AVAILABLE, `freshness` CURRENT, `delay_status` END_OF_DAY, session date 2025-02-07 |
| LIMITED (stale), as of 2025-02-12 | `LIMITED`, reason `STALE_DATA`, `"875"`, `STALE`, `["END_OF_DAY"]` | `price_date_used` **2025-02-07**, `price_missed_sessions` `3` | LIMITED, STALE, END_OF_DAY; the price session (02-07) is **not** `as_of` (02-12) |
| INSUFFICIENT_DATA, as of 2025-01-29 (before the first close) | `INSUFFICIENT_DATA`, reason `MISSING_PRICE_HISTORY`, `value` null, `UNKNOWN`, `["UNKNOWN"]`, lineage `identity:I-1 NOT_COMPUTABLE`; plus the partial row (500, `excluded_holdings` 1) | **no `price_date_used`** (withheld), no `last_print_date`, `price_missed_sessions` absent | INSUFFICIENT_DATA, UNKNOWN, UNKNOWN; **no session date** |

What `render_claim_block` would do (nothing is changed; this is by reading `claim_render.py:106-125` and `claim_limits.py:48-66`):
- **LIMITED**: it renders. S1 and S3 share one lineage field `session_date`, so C-1 ("the close ... delivered for the {session_date} session") and C-2 ("the NAV ... on {session_date} is {quantity} x p + {cash}") must name the **same** date. For a stale price that date is either the price session (then C-2 puts the NAV on a date it was not computed for) or `as_of` (then C-1 says the close was delivered for a session it was not). `lineage_from_slots` refuses two different values, so the slots cannot carry both. Not decidable by the Engineer.
- **INSUFFICIENT_DATA**: if the extractor takes `session_date` from `price_date_used` the field is missing and the renderer refuses (`CLAIM_LINEAGE_FIELD`), so the root's read answers `REAL_UNAVAILABLE` and **no suppressed real NAV can ever be shown**, the very case the key-figures view (F-2 partial block) was built for. If the extractor falls back to `as_of`, the block renders C-1 and C-2 as unconditional sentences ("The NAV ... is 10 x p + 500") beside `state INSUFFICIENT_DATA`, which states a number the document does not hold.
  C-2 has no state condition. Either way this is O-6.
- The extractor does not decide; it copies. Recommendation: until the Quant rules, a missing field **refuses** (no fallback to `as_of`), and the plan says plainly that a real suppressed NAV is then unreadable.

## 5. The proof before R8 (the PD-0080 pattern)

What can be proved before R8, in memory, with nothing stored and nothing marked real:
1. **The extractor as a pure function over parsed documents.** Input: the `issued` and `response` documents and, for the snapshot-held and md-held facts, the stored claim-lineage object (option A) or in-memory dicts of the snapshot's shape. Expected values are written by hand from the probe tables above, not from the extractor's output.
2. **A bundle built by the real staging code.** `compute_for_portfolio` runs in memory on the `test_performance_midpoint` kit (non-synthetic invented readings; `_pin` replaced) and `result.canonical_json().encode("utf-8")` is the `issued` bytes, exactly as `_stage_real` serializes (`service.py:323`); the `response` is built by the same code as `_write_root` (`service.py:253-256`). The response construction is inline in `_write_root`; to test it as the real code, a pure function `response_of(...)` would be extracted from it (a small `service.py` refactor with no behaviour change; recommendation).
3. **Per field**, a test that the extracted value equals the stored value byte for byte, and that mutants fail: another date, a dropped list entry, an int turned into a different text, a second NAV row, an absent holding row, a duplicate or non-text field. Each missing or malformed field makes the extractor raise `ClaimRenderError` (not return a hole).
4. **`render_claim_block` and the contract's re-render check** (`_claim_block`, `real_scoped_contract.py:262-285`) over the extractor's output, for AVAILABLE and LIMITED; for the suppressed case a test records the O-6 behaviour (refuses) so the ruling changes a test, not a surprise.
5. **Never**: a stored bundle; a checked-in fixture marked `synthetic: false` (PD-0066 decision 8). The checked-in fixtures, if any, come from the synthetic kit (`engine.compute`, `synthetic: true`), as the PD-0080 fixture does; the `real_quotes=True` outputs stay in memory.

First run at R8 (cannot be proved before): the real `md_file`/`md_quote` values (label source string, `retrieval_time`, label status), the real snapshot's source record, the real files' hashes and the real ledger pin; the claim text rendered from them (wording checked by the Quant on real values); a real archive read through the route on PostgreSQL; the real suppressed and stale outcomes; the create-then-repeat replay on a real root.

## 6. Wiring

- **Where the real extractor is passed**: `real_launcher.build()` (`real_launcher.py:195-200`) calls `create_real_mode_app(..., origins=origins)` with no `lineage_of`, so the default `unbuilt_lineage` applies (`real_mode_routes.py:66-69,92`). The wiring is one keyword: `lineage_of=<the extractor>`.
  The launcher still builds the service with `world_inputs=None` (`real_launcher.py:182-186`), so a REAL-scope create is refused by the service (`RW_SHAPE`, public `REAL_UNAVAILABLE`) until R8 wires the world: no REAL root can reach the extractor before then, except through a read of a root created some other way (none exists).
- **A TEST root never reads lineage**: `block_for` calls `lineage_of` only when `origin["market_origin"] == REAL_SOURCE` (`real_mode_routes.py:175`), and `render_claim_block` ignores the lineage for any other origin (`claim_render.py:117-119`). A test passes an extractor that raises for any call and reads and creates a TEST root.
- **A missing or malformed field refuses, never renders a hole**: the extractor raises `ClaimRenderError` (the existing codes `CLAIM_LINEAGE_FIELD`, `CLAIM_LINEAGE_SHAPE`, or new `CLAIM_LINEAGE_*` codes; the route logs only the code). On a read, `run` turns it into `REAL_UNAVAILABLE` (`real_mode_routes.py:144-146`), nothing of the bundle is sent. The renderer re-checks every field is a non-blank string.
- **Effect on the create response and on the repeat after TR7R-L-1**:
  - After the COMMIT, a failure to build the response answers the contract's UNKNOWN (`real_mode_routes.py:210-217`), and the identical command replays the stored root (`rw_precheck`, `service.py:202-203`). The replay goes through `committed(...)` and the same extractor, deterministic over the stored bundle: **if the extractor cannot fill a field once, it cannot on any repeat, and the read answers `REAL_UNAVAILABLE`**. The owner would hold a committed root whose answer is UNKNOWN for ever. That is the O-7 note in STATUS.
  - **Recommendation (design decision)**: run the extractor and `render_claim_block` inside `_stage_real` **before `_seal`**, in the create transaction. A root whose block cannot be rendered is then refused with whole rollback, as FF1-C08 already treats a service refusal (`service.py:324-327`), and is never committed. It needs a refusal code the contract's `ERRORS` and the client's `refusalZh` know (a new code, or the existing `RW_SEAL_REFUSED`), which is a contract-surface choice for the design.
  - When the extractor succeeds, the create response carries `claim_limits` rendered from the stored bundle, and the replay returns the same block byte for byte (the contract's equality check, `real_scoped_contract.py:275-282`, enforces that).

## 7. Test plan and file list

**New**
- `src/web_api/real_lineage.py` (or `src/marketdata/claim_lineage.py`): the pure extractor `lineage_of(archive)` plus a pure core over parsed documents. No connection, clock, environment or file. It selects and copies; it computes, rounds and interprets nothing. Where a field is a list it hands the list over (the renderer joins); where a field is an integer, **how it becomes text is OPEN** (formatting), and the Engineer proposes `str(int)` only after the Quant says so.
- `tests/product/test_real_lineage.py`: the tests of section 5.

**Changed**
- `src/web_api/real_launcher.py` (`build`): pass the extractor. `tests/product/test_real_preflight_static.py` pins `build` by digest (`FULL_PINS['web_api/real_launcher.py']`, line 952): that digest changes and is updated in the same change, and the launcher stays free of the password and environment helpers (the call-graph guard).
- `src/real_service/service.py`, only if option A or the pre-seal check is chosen: build the claim-lineage object, extract `response_of(...)`, call the extractor before `_seal`. Its tests (`test_real_service*`, the PG real-mode tests) change with it.
- `tests/product/test_real_mode_api.py`, `real_mode_kit.py`: the default `unbuilt_lineage` test and the injected-extractor tests keep working; add a test that the launcher's app uses the real extractor.
- `tests/product/test_postgres_real_mode.py`: a PG case over a TEST root (no lineage read) and, after R8's wiring, a real archive; run alone, never concurrently with another PG module.

**SQL and migrations**: none for option A and the pre-seal check (the response shape is not a closed key set in SQL). Option B changes `real_fence_v1.sql` and the installer's checked artifacts. Option C changes `performance`.

**Not done here**: the CSS or client; `claim_limits` text; the wording of any claim. The client needs no change (it renders the block the contract sends).

## 8. Contradictions found

1. `claim_render`'s docstring says a slot is filled "from its lineage field and from nothing else" and design 7.4 says the lineage records the label source, status, the exposure window and "no V1 event in M". **The engine's manifest says the opposite**: it does not state them (`market11.py:122-124`) and does not record the V1 check (`:117-121`). The extraction the design calls "first run at R8" has no source in the issued document for five fields.
2. Design 7.4 S3 writes the NAV as `10 x p + 500.00`. The contract stores cash as `"500"` (`real_scoped_contract.py:50`). Not a defect, but the rendered text will say `500`.
3. `SLOT_FIELDS` maps `session_date` to both S1 and S3 and `lineage_from_slots` refuses two different values, so a stale valuation (price date before `as_of`) cannot be stated truthfully in both places (section 4).
4. Design 7.1 names the claim-limit slots in the R5 and R7 rows and the "first check" at R8, but no row assigns the building of the extractor, and `real_mode_routes.py:26` and `:68` say "first built and checked at R8". The R8 row (owner steps) has no extraction step. Whoever owns it must be named.
5. The by-hand V1 check (Ruling 3.2 item 6) "is made before the run" and is not recorded. C-1's own text says "no V1 event and no V4 record exists for this file". Nothing in the stored bundle supports that sentence.

## 9. Recommendations (the Engineer's, for each open point)

| open point | recommendation |
|---|---|
| Where the md-held and snapshot-held facts live | option A (a claim-lineage object in the `response`, built from the world at create), no SQL |
| Statements the engine should make (reconciliation, V1, `E(d_p, R)`, label status/source) | the Quant rules whether they come from the engine (option C) or are stored facts; until then the extractor refuses |
| `documentation_reading_date` | a stored date is needed; the Quant or the owner chooses its home (profile data, snapshot source record or publish record) |
| Which date is `session_date` | the Quant rules; a stale valuation cannot use one field for two meanings |
| Integer to text (`ledger_version`) and the interval text of `E(d_p, R)` | Quant (formatting is a method question); the Engineer implements what is ruled |
| Which `source_name` text | Quant (wording) |
| `file_hashes`: consumed files or all files of M | the Quant says which S4 means |
| Missing field in the extractor | raise, never default or fall back |
| Unrenderable real root | refuse before the seal (whole rollback) rather than commit it |
| Suppressed real NAV (O-6) | refuse until ruled; accept that no real suppressed result is shown until then |
| `response_of(...)` refactor in `service.py` | yes, no behaviour change, to test the real response construction |
