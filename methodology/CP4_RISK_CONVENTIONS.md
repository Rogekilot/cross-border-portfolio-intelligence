# CP4 risk conventions: return series, risk-free rate, benchmarks, risk and benchmark-relative statistics, sufficiency, registry

**Author:** `quant-analyst` subagent, dispatched by the main session (PM), 2026-10-02.
**Convention set ID:** `risk/1.11` (supersedes `risk/1.10` and earlier; 1.0 to 1.4 issued 2026-10-02,
1.5 to 1.9 issued 2026-10-03, 1.10 issued 2026-10-24, 1.11 issued 2026-10-25, each of 1.10 and 1.11 by a
`quant-analyst` subagent dispatched by the main session).

A Computation Manifest that computes any value defined here cites `risk/1.11` together with
**`performance/1.12`** (the return definition this document builds on), **`ledger-replay/1.5`**
(`FIFO/1` mode), **`market-data/1.16`**, `FIFO/1` and **`minor-units/1.1`**. A later change to any
RULING, or to any entry of the registry file of Ruling 9.3, creates a new ID, including a
clarification (one id, one text: P9).

**(1.11) When this id is in force.** `risk/1.11` is in force from the engineer's increment that moves
the code's market-data label to `market-data/1.16` (`market-data/1.16` §11 item 35). Until that
increment the code runs, and its manifests cite, `risk/1.10` with `market-data/1.15`; the text of
`risk/1.10` is this file at commit `ae6dfdc` (below). A manifest never cites `risk/1.11` beside
`market-data/1.15`, or `risk/1.10` beside `market-data/1.16` (Ruling 9.2 (1.10)).

(Header as issued for 1.0: "cites `risk/1.0`"; for 1.1: "cites `risk/1.1`"; for 1.2: "cites `risk/1.2`";
for 1.3: "cites `risk/1.3`"; for 1.4: "cites `risk/1.4`"; for 1.5: "cites `risk/1.5`"; for 1.6: "cites `risk/1.6`"; for 1.7: "cites `risk/1.7`"; for 1.8: "cites
`risk/1.8`"; for 1.9: "cites `risk/1.9` together with … **`market-data/1.11`** …". The 1.9 header kept
`market-data/1.11` although its registry already named `market-data/1.14`; 1.10 brings both to the
code's label. For 1.10: "cites `risk/1.10` together with … **`market-data/1.15`** …".)

**Change note, 1.10 → 1.11 (2026-10-25).** A label re-issue for the move of the code's market-data
label to `market-data/1.16` (`market-data/1.16` §11 item 35 and "When a manifest may cite 1.16",
point 1). It changes no method, no threshold, no state, no wording rule and no entry.

- **Why.** Ruling 9.2 (1.10): `implementation_version` names the labels the code runs, and a registry
  file is never edited after its id is issued. The engineer's next increment moves the code's
  market-data label to `market-data/1.16`. `RISK_1.10_REGISTRY.json` names `market-data/1.15`, so the
  registry is re-issued first, under a new `risk` id, and this header moves with it.
- **Registry (1.11):** `methodology/registry/RISK_1.11_REGISTRY.json`, `registry_id` `risk/1.11`. The
  fields that change, and nothing else:
  - `registry_id`: `risk/1.10` → `risk/1.11`;
  - `issued`: 2026-10-24 → 2026-10-25;
  - `change_note`: the 1.10 → 1.11 note;
  - `status`: "Part of the text of `risk/1.10`" → "… `risk/1.11`", the rest unchanged;
  - `common.implementation_version`: `["risk/1.10", "performance/1.12", "ledger-replay/1.5 (FIFO/1)",
    "market-data/1.15", "minor-units/1.1"]` → `["risk/1.11", "performance/1.12", "ledger-replay/1.5
    (FIFO/1)", "market-data/1.16", "minor-units/1.1"]`.

  No entry and no other `common` field changes. `RISK_1.0_REGISTRY.json` to `RISK_1.10_REGISTRY.json`
  stay unchanged as records. File SHA-256
  `9760901707bd925fbd5f4693aa7b763f81cc2fa50ea1cccdccbfc7e90e899de3`; `registry_digest` (SHA-256 of the
  canonical JSON, `marketdata.canonical`)
  `5c630fdf9ff4eb6cf0569cda655794b1c0e1ec1f64c1e2ea7daf3df9348058ce`. The 1.10 file keeps
  `registry_digest` `f6dc11f70362bd6c127368114c18c353980b0319706c7e777651100ee9c92b65` (recomputed today;
  equal to the value recorded in the 1.9 → 1.10 note). I computed both with the project's canonical
  serializer, read only; neither is an expected value of any metric. I built the new file by replacing
  exactly the five fields above in the 1.10 file's text and checked, field by field, that no other value
  differs.
- **The header** now names `risk/1.11` and `market-data/1.16`, with the in-force rule above.
- **No other ruling's content changes. No expected value changes.**
- **Fixtures (Ruling 11.4).** `cp4_golden/1.0-part1`, `1.0-part2`, `1.9-part3` and `1.0-part4` are
  **unaffected**, for the reason of the 1.9 → 1.10 note: their `convention_sets` are minimum versions,
  which `risk/1.11` and `market-data/1.16` meet, and no value, state, reason or detail they assert
  changes. Under `risk/1.11`, "the registry file of the risk version cited" (S2-1, S3-1) is
  `RISK_1.11_REGISTRY.json`. No fixture asserts a registry digest value. `market-data/1.16` itself
  leaves these fixtures unaffected (its 1.15 → 1.16 change note, "Fixtures").
- **For the engineer (in the increment that moves the market-data label; a byte copy, not a method
  change):**
  - `src/risk/risk_registry.json` becomes a byte copy of `RISK_1.11_REGISTRY.json`;
  - `risk.registry.IMPLEMENTED_REGISTRY_ID` = `risk/1.11`;
  - results cite `risk/1.11#<metric_id>`, and manifests record `registry_id` `risk/1.11` with the digest
    above;
  - tests that pin the document's id, the file name or the 1.10 digest move with the stated reason
    "risk/1.11 re-issue for market-data/1.16 (market-data/1.16 §11 item 35)";
  - ids compare numerically by component: `1.11` is later than `1.10`.
- **The CP4 freeze** (1.9 change note; §15.1) is unchanged: CP4 acceptance stays recorded at `risk/1.9`.
- **The text of `risk/1.10`** is this file at commit `ae6dfdc` (SHA-256
  `4325fd3c0b57ff9226954264a7257bd2fc29bdda453935d2b53c624b45bcfc8a`).

**Change note, 1.9 → 1.10.** This answers review finding M-2 of the code-label move
(`reviews/TECH_REVIEW.md`, "Code label to market-data/1.15 — review (2026-10-24)" and its re-review)
and finding R2-C7 of the `market-data/1.16` consistency re-review. It changes no method.

- **The defect.** PD-0067 decision 6 moved the code's market-data label to `market-data/1.15`.
  `RISK_1.9_REGISTRY.json` names `market-data/1.14` in `common.implementation_version`, which every
  entry points to. A composed response prints registry `risk/1.9` and its digest beside conventions
  that name `market-data/1.15`, so one audit chain names two versions of one dependency (P9, PRD §33).
  Ruling 9.2 (1.2) forbids editing an issued file, so the remedy is a new id.
- **Ruling 9.2 (1.10): what `implementation_version` names.** It names the convention ids the engine
  runs when it computes the entry: the `risk` id first, then each dependency at the label the code
  carries. **It is not a minimum.** The reasons and the rule are in Ruling 9.2 (1.10).
- **Registry (1.10):** `methodology/registry/RISK_1.10_REGISTRY.json`, `registry_id` `risk/1.10`. The
  fields that change, and nothing else:
  - `registry_id`: `risk/1.9` → `risk/1.10`;
  - `issued`: 2026-10-02 → 2026-10-24;
  - `change_note`: the 1.9 → 1.10 note;
  - `status`: "Part of the text of `risk/1.9`" → "… `risk/1.10`", the rest unchanged;
  - `common.implementation_version`: `["risk/1.9", "performance/1.12", "ledger-replay/1.5 (FIFO/1)",
    "market-data/1.14", "minor-units/1.1"]` → `["risk/1.10", "performance/1.12", "ledger-replay/1.5
    (FIFO/1)", "market-data/1.15", "minor-units/1.1"]`.

  No entry and no other `common` field changes. `RISK_1.0_REGISTRY.json` to `RISK_1.9_REGISTRY.json`
  stay unchanged as records. File SHA-256 `0f35c6b6f28100ca72a1680f14f6cb00000650c1daf0bdd01a88d3ed1b4ef334`;
  `registry_digest` (SHA-256 of the canonical JSON, `marketdata.canonical`)
  `f6dc11f70362bd6c127368114c18c353980b0319706c7e777651100ee9c92b65`. The 1.9 file keeps
  `registry_digest` `9418e11faa274403cbc96215bfa2fd9e83b46220ca61e7db2b77f05e89a7c54f`. I computed both with
  the project's canonical serializer, read only; neither is an expected value of any metric.
- **The header** now names `market-data/1.15` (it named `market-data/1.11` through 1.9).
- **No other ruling's content changes. No expected value changes.**
- **Fixtures (Ruling 11.4).** `cp4_golden/1.0-part1`, `1.0-part2`, `1.9-part3` and `1.0-part4` are
  **unaffected**. Their `convention_sets` are minimum versions (`risk/1.0` to `risk/1.9`,
  `market-data` up to 1.14), which `risk/1.10` and `market-data/1.15` meet, and no value, state, reason
  or detail they assert changes. Their structural assertions S2-1 and S3-1 name "the registry file of
  the risk version cited". Under `risk/1.10` that file is `RISK_1.10_REGISTRY.json`, so a checker takes
  its id and digest. No fixture asserts a registry digest value. No `cp5_golden` or `cp6_golden` item
  names a risk registry.
- **For the engineer (the label track; a byte copy, not a method change):**
  - `src/risk/risk_registry.json` becomes a byte copy of `RISK_1.10_REGISTRY.json`;
  - `risk.registry.IMPLEMENTED_REGISTRY_ID` = `risk/1.10`;
  - results cite `risk/1.10#<metric_id>`, and manifests record `registry_id` `risk/1.10` with the digest
    above;
  - tests that pin the document's id, the file name or the 1.9 digest move with the stated reason
    "risk/1.10 re-issue for market-data/1.15 (review M-2)";
  - any comparison of risk ids is numeric by component: `1.10` is later than `1.9`.
- **The CP4 freeze** (1.9 change note; §15.1). CP4 acceptance stays recorded at `risk/1.9`. This
  re-issue changes no ruling's content and no fixture, and it rules none of the §15.1 latent paths.
- **The text of `risk/1.9`** is this file at commit `4c62f3e` (SHA-256
  `a841bf0f2fd88f6eaae1488809afd91ff4307211b955300b58d7d11fa3098f0d`).

**Change note, 1.8 → 1.9.** This answers review finding CP4F-13 and the engineer's three contract
choices for 1.8.

- **Ruling 5.7 (1.9): a benchmark served by several sources declares its precision.**
  - The index's `official_decimals` is declared in the catalog entry, and each source's
    `precision_decimals` in its source declaration.
  - A source's bound is 0 when it publishes at least the official decimals, else `½ × 10^(−d)`.
  - **Inference from the levels is not accepted** (mutation M-C45). Undeclared means not usable:
    `BENCHMARK_SERIES_UNAVAILABLE` (M-C44).
- **`paid_amount` is defined in `market-data/1.14`** (Rulings 7.1 and 4.5). The engineer's field is
  ratified. A one-sided paid amount is used, not a disagreement (M-C43).
- **No text change for the engineer's third choice.** A dividend whose conversion has 5 or more
  fixings missed is not applied, and every ratio spanning its ex-date is `INSUFFICIENT_DATA` +
  `MISSING_FX_HISTORY`. That is Ruling 5.5 (1.8) item 4 as written: in effect a break at the ex-date
  with that reason, not `SOURCE_CONFLICT`.
- **Registry (1.9):** `RISK_1.9_REGISTRY.json`. `common.states_benchmark` gains the
  undeclared-precision row, and the implementation version cites `market-data/1.14`. No entry
  changes.
- **Fixtures:**
  - parts 1 and 2 are **unaffected**: their benchmarks have one source each, and they contain no
    paid fields;
  - `cp4_golden/1.8-part3` is **replaced by `1.9-part3`**:
    - the declarations are added to every multi-source series;
    - SYN4_BM_US_TR5 and SYN4_BM_US_TR4 are added;
    - R4-S4, R4-S6 and R5-E10 are added;
    - R5-E11 and R5-E12 are added (review finding CP4F-15): the FILING alone states the payment
      (used as stated), and the two sides state different payments (a `DISAGREEMENT`);
    - mutations M-C43 to M-C46 are added.
  - No earlier value, state, reason or detail changes. R5-E9 gains the bite M-C21.
  - R10-S1's `MAX_AVAILABLE` beta now carries `max_available_start` (`INCEPTION`), which Ruling 2.3
    always required. My derivation tool had dropped it for benchmark-relative kinds.
- **CP4 freeze.** At the main session's ruling, CP4 methodology is frozen for CP4 acceptance at
  `risk/1.9`, `market-data/1.14` and `cp4_golden/1.9-part3`. Refinements of paths that no admitted
  source exercises yet go to §15.1. They are ruled when the first real proxy or second source is put
  up for admission.

**Change note, 1.7 → 1.8.** This answers review finding CP4F-12 (§42).

- **Ruling 5.5 (1.8): a proxy dividend declared in a currency other than the ETF's price currency
  is converted, not refused.**
  - If the issuer states the amount paid in the price currency, that amount is used.
  - Otherwise the declared amount is converted at the ECB fixing of the ex-date, `u(ex-date)` (the
    EUR cross, `market-data` Rulings 1.3 and 1.6).
  - That fixing's freshness is the state of every ratio spanning the ex-date.
- **The interim refusal (the proxy unavailable from the ex-date) is superseded:**
  - mutation M-C42 is the interim refusal;
  - M-C38 is the defect found (added unconverted).
- **Registry (1.8):** `RISK_1.8_REGISTRY.json`. `common.corporate_action_treatment_benchmark` states
  the rule. No entry changes.
- **Fixtures:**
  - parts 1 and 2 are **unaffected**;
  - `cp4_golden/1.7-part3` is **replaced by `1.8-part3`**: R5-E9 (3 items) and mutations M-C38 to
    M-C42 are added. No earlier item changes.

**Change note, 1.6 → 1.7.** This answers the CP4 engineer's tech plan §17.23 decisions 1 and 3.

- **Ruling 5.5 (1.7): how an ETF proxy identifies one corporate action across the feed and the
  filing.**
  - Equal statements are one corroborated action.
  - A shared record date, ex-date or pay date makes one action. For a split: the record date, the
    ex-date, or an equal ratio within 20 sessions.
  - **Unpaired statements of the two sides whose ex-dates are at most 20 sessions apart are one
    disputed action. They are never two actions applied.** That covers decision 1's case, where the
    statements share neither date, and it is what changes from the build (mutation M-C36: applying
    both double-counts the dividend).
  - Further apart, they are two single-source actions, both applied.
- **Decision 3 is confirmed:**
  - a disputed action breaks the chain at every ex-date either statement names;
  - an equal-ratio split at another date conflicts **within the 20-session window** of `market-data`
    Ruling 6.4a. Outside it, it is a different split.
- **Registry (1.7):** `RISK_1.7_REGISTRY.json`. `common.corporate_action_treatment_benchmark` states
  the identity rule. No entry changes.
- **Fixtures:**
  - parts 1 and 2 are **unaffected** (no proxy);
  - `cp4_golden/1.6-part3` is **replaced by `1.7-part3`**: R5-E7 and R5-E8 are added, with mutations
    M-C36 and M-C37. No earlier item changes.

**Change note, 1.5 → 1.6.** This answers the final CP4 review (`reviews/TECH_REVIEW.md` §41),
findings CP4F-5 and CP4F-10.

- **Ruling 5.5 (1.6): disagreements in an ETF proxy.**
  - **A disputed ETF print** (its price sources disagree) is withheld for **that day only**. A grid
    date that needs it is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`. The total-return chain links
    around it, because no price of the withheld day is needed to link the prints on either side.
  - **A disputed dividend or split** breaks the chain at its ex-date. Only a ratio that spans the
    ex-date is unavailable.
  - 1.2's "from the ex-date on" is withdrawn. It suppressed every later window for ever.
  - The engineer's present proxy (every later print withheld) is mutation M-C33.
  - A resolution record is **not** required for CP4. Fail-closed per day or per span is the
    complete rule until one exists.
- **Ruling 7.7 (1.6): an active return refused by its portfolio leg is a history refusal.** This is
  decided by the owner's PD-0040 addendum ("any history refusal (too young, a gap, a zero-capital
  period) falls back … A missing benchmark is never a fallback trigger"). A `TWR(g_0, g_n]` that is
  `INSUFFICIENT_DATA` (for example `SPLIT_NOT_APPLIED`) triggers the fallback.
- **Registry (1.6):** `RISK_1.6_REGISTRY.json`. The `common` texts of the default view and of the
  ETF-proxy benchmark rows change; one row is added. No entry changes.
- **Fixtures (Ruling 11.4):**
  - `cp4_golden/1.0-part1` and `1.0-part2` are **unaffected**: they contain no proxy and no default
    view.
  - `cp4_golden/1.5-part3` is **replaced by `1.6-part3`**: R5-E4, R5-E5, R5-E6 and R11-V1 are added
    (7 items), with mutations M-C32 to M-C35.
  - No 1.5-part3 item changes. R5-E2 and R5-E3 hold under the break rule.

**Change note, 1.4 → 1.5.** This answers the CP4 exit test's open finding (the all-metrics matrix,
`tests/product/test_cp4_exit.py`) and confirms its ruling-derived cells.

- **Ruling 6.9 (1.5): the active return over a window containing a `ZERO_CAPITAL_PERIOD` is
  `INSUFFICIENT_DATA`**, detail `ZERO_CAPITAL_PERIOD`. The TWR's factor 1 over the empty weeks is an
  accounting convention, and an active return would turn it into a measured 0 % against the
  benchmark's real return.
  - The engine's current output (`AVAILABLE`, the TWR's value) is mutation M-C30.
  - `performance`'s own TWR is unchanged.
- **Ruling 7.3 (1.5): a refused window keeps its window-independent causes.** These are no
  selection, series not in `M`, price return and no risk-free source. So `MISSING_BENCHMARK`
  outranks the refusal's missing code. This states what the exit test's P7 and P8 cells already
  assume.
- **Registry (1.5):** `RISK_1.5_REGISTRY.json`. The `risk_active_return` entry changes (its
  missing-data handling, states, limitations and `defined_in`), and `common.reason_rule` gains the
  refused-window sentence.
- **Fixtures (Ruling 11.4):**
  - `cp4_golden/1.0-part1` and `1.0-part2` are **unaffected**: no active return in them spans a
    zero-capital period, and no refused window lacks a selection.
  - `cp4_golden/1.4-part3` is **replaced by `1.5-part3`**: R9-Z3 (3 items) and R6-W0 (2 items) are
    added, with mutations M-C30 and M-C31. No earlier item changes; 88 items.

**Change note, 1.3 → 1.4.** This answers the midpoint review's CP4M-4 and CP4M-6. **No value,
threshold, formula or state of an existing fixture item changes.**

- **Ruling 5.6 (1.4): the selection log with `REVERSAL` and corrections.** The `REVERSAL` record that
  migration 0015 stores is a valid user act. The ruling sets what it means and how the selection in
  force is resolved:
  - **A reversal voids the record it names.** The latest remaining live record is then in force; if
    none remains, NONE. This matches the engineer's build.
  - **A replacement takes the order position of the record it corrects.** This **differs** from the
    build, which orders a replacement by its own sequence number (fixture R13-V8, mutation M-C29).
  - **A reversal of a reversal is refused.** This matches the build.
  - **A version that cuts a correction pair is not pinnable.** This matches the build.
  - Results pinned before and after a reversal are stated.
- **Ruling 9.4 (1.4): the exact intermediates, per metric.** The list is now explicit. They live in
  the computation manifest, as exact rationals, inside the result digest, and are never presented.
  The code location is the engineer's.
- **Registry (1.4):** `RISK_1.4_REGISTRY.json`, with `registry_id` `risk/1.4`. It adds
  `common.selection_rule` and `common.manifest_intermediates`. No entry changes.

**Fixtures (Ruling 11.4).** `cp4_golden/1.0-part1` and `1.0-part2` are **unaffected**: their
selection logs hold SELECT and CLEAR records only, and every replacement position equals its own
sequence number. `cp4_golden/1.1-part3` is **replaced by `cp4_golden/1.2-part3`** (minimum
`risk/1.4`). Portfolio R13 is added, with a ten-record log and seven assertions (13 items), and
mutations M-C25 to M-C29 are added. No 1.1-part3 item changes.

**Change note, 1.2 → 1.3.** These are answers to three questions the CP4c engineer raised at the
midpoint. **No value, threshold, formula or state changes**; each point is a statement made exact,
marked "(1.3)".

- **Ruling 7.3 (1.3): which causes give the reason.**
  - Stated exactly: only causes at the result's own state level compete.
  - The observation-count rule is a cause **with no code** (`LIMITED` from N1 to N3,
    `INSUFFICIENT_DATA` below N1).
  - So a result limited by its count alone has **no** reason, even if a lower-level input is
    `AVAILABLE` + `STALE_DATA`.
  - This is `performance` Ruling 1.5 (1.1) unchanged. The engineer's `risk.states.combine` rule is
    right, and it is what 7.3 meant.
  - The separating fixture items are named in the ruling.
- **Ruling 5.8 (1.3): Current mode reads `M_t`.**
  - Every Current-mode input is read from `M_t` (`performance` Ruling 1.7). A benchmark level, fixing
    or rate that is due at `t` but not in `M_t` **is** missed.
  - A row that is not yet due is still not missed, as in 1.2.
  - 1.2 implied this through `performance` 1.7; it is now written.
- **Ruling 5.1 (1.3): a RETURNS-form benchmark source needs no base level.**
  - Compounded levels start at 1 on the calculation day before the series' first return. Every
    metric reads only ratios of levels, so the base cancels.
  - The contract and the catalog need no base-level field.
  - The engineer may refuse RETURNS-form series until one is put up for admission, provided the
    refusal is stated as such.
- **Registry (1.3):** `RISK_1.3_REGISTRY.json`, with `registry_id` `risk/1.3`. `common.current_mode`
  gains the `M_t` clause, and `common.reason_rule` is added. No entry changes.
- **Catalog ids.** The main session stores them as `benchmarks:1` and `risk_free:1`, because
  migration 0015's `catalog_version` pattern does not allow `/`. This document cites them in that form.

**Fixtures (Ruling 11.4).** `cp4_golden/1.0-part1` and `1.0-part2` are **unaffected**: they assert
no Current mode, and their reasons already follow 7.3 as now stated. `cp4_golden/1.0-part3` is
**replaced by `cp4_golden/1.1-part3`**, with minimum `risk/1.3`, for two reasons:

- **An input error is corrected.** 1.0's single retrieval time of 2022-11-30 contradicted every file
  under `market-data` Ruling 3.1. It is replaced by declared vintages (§11.2b).
- **One assertion is added:** R2-L2, the item that separates the two readings of 7.3.

No 1.0-part3 expected value changes.

**Change note, 1.1 → 1.2.** Written with `cp4_golden` part 3, and in answer to the main session's
question about the registry file name. Deriving part 3 by hand showed where the 1.1 text was silent
or too loose. Each point is settled below, marked "(1.2)". **No 1.1 value, threshold or formula
changes.**

- **Ruling 9.2 (1.2) and 9.3 (1.2): one registry file per version.**
  - Each file is named after its `registry_id`: `methodology/registry/RISK_1.0_REGISTRY.json`
    (restored to its 1.0 text), `RISK_1.1_REGISTRY.json`, `RISK_1.2_REGISTRY.json`.
  - The 1.1 clause "the file keeps its name" is withdrawn. It would have left the 1.0 record
    overwritten (P9: one id, one text).
  - The engine reads the id from the file's `registry_id`, never from its name.
  - **The registry in force under `risk/1.2` is `RISK_1.2_REGISTRY.json`.**
- **Ruling 0.1 (1.2) and 5.6 (1.2): account scope.** An internal transfer is a flow of the account,
  and a benchmark-dependent metric at account scope uses the portfolio's selection.
- **Ruling 5.5 (1.2): the ETF proxy, exactly.** The base level; dividends used if `CORROBORATED` or
  `SINGLE_SOURCE` (1.0 said "corroborated", which would have dropped a single-source dividend and
  biased the proxy toward a price return, the error Ruling 5.4 exists to prevent); splits; a
  `DISAGREEMENT` suppresses the proxy from its ex-date.
- **Ruling 5.7 (1.2): two sources, exactly.** Source order is data; a day one source lacks is
  `SINGLE_SOURCE` and used; the new detail `BENCHMARK_SOURCE_CONFLICT`.
- **Ruling 5.8 (1.2), new: Current mode.** A benchmark level, fixing or rate is used only if it
  existed at `t`; one not yet due is not "missed".
- **Ruling 7.7 (1.2), new: the default view** (PD-0040 OD-R1) as a service-level composition, with
  the exact trigger and how a fixture asserts it.
- **Ruling 7.4 (1.2):** the detail `BENCHMARK_SOURCE_CONFLICT`.
- **Registry (1.2):** `registry_id` `risk/1.2`. `common` gains `lookback.default_view`, `current_mode`
  and two `states_benchmark` rows; `corporate_action_treatment_benchmark` follows Ruling 5.5 (1.2).
  No entry-level text changes.
- **Errata in parts 1 and 2 (§11.5).** Their structural assertions S-1 and S2-1 name the registry
  file. They are read as "the registry file of the `risk` version the manifest cites". No asserted
  value, state, reason or detail changes, so neither fixture is reissued (Ruling 11.4).

**Fixtures (Ruling 11.4).** This change leaves **`cp4_golden/1.0-part1` and `1.0-part2`
unaffected**. Neither asserts an ETF proxy, a second benchmark source, Current mode, account scope
or a default view, and both re-check with 0 differences under the 1.2 calculators.
`cp4_golden/1.0-part3` is new and cites `risk/1.2` as its minimum.

**Engineer impact:**

- load `RISK_1.2_REGISTRY.json` (the engine's copy is today byte-identical to the 1.1 file);
- the new detail `BENCHMARK_SOURCE_CONFLICT`;
- Rulings 5.5, 5.7 and 5.8 for the benchmark leg;
- Ruling 7.7 in the service layer.

None changes a part-1 or part-2 behaviour.

**Change note, 1.0 → 1.1.** Written with `cp4_golden` part 2 (benchmark-relative metrics). Deriving
its expected values by hand showed five places where the 1.0 text admitted more than one reading.
Each is settled below, marked "(1.1)". **No 1.0 ruling's substance is reversed.**

- **Ruling 5.6 (1.1): the selection-log version.** A pinned version is a sequence number; the
  records in force are those with `seq ≤ version`, and the selection is the latest of them.
  Version 0 (or a portfolio with no record) has no selection.
- **Ruling 6.9 (1.1): what a window fact reads, and how it is presented.**
  - `benchmark_return` and `active_return` read the benchmark at **`g_0` and `g_n` only**, and the
    portfolio leg's state is that of `TWR(g_0, g_n]` (`performance` Ruling 5.5). This is the
    telescoping of `performance` Ruling 5.2 applied to the benchmark: an interior benchmark level
    is not an input of a window return, so its staleness cannot degrade one. The 1.0 registry text
    "at every grid date of the window" is withdrawn for these two entries; the statistics (beta, R²,
    alpha, TE, IR) still read every grid date.
  - Each metric's `value` is its own exact value quantized (`performance` Ruling 2.2). The
    apportioned triple of 1.0 is a separate **decomposition view**: total = the portfolio TWR over
    `(g_0, g_n]`, parts = (`benchmark_return`, `active_return`) in that order, by `performance`
    Ruling 2.4 item 3 (largest remainder; ties in that order). The two can differ by one quantum,
    and both are asserted (part 2, Q1-B1 and Q5-H1, where they do).
- **Ruling 8.2 (1.1): the two legs' inputs, and which grid dates are "used".** Defined exactly; a
  portfolio leg with no market input (cash in `R` only) has no instant and so no seam.
- **Ruling 8.3 (1.1): `max_offset_minutes_at_last_grid_date`** defined exactly, and the seam's
  1.0 fields (`portfolio_instants`, `benchmark_instants`, `fx_fixing`) replaced by two sorted lists of
  calendar ids. Nothing in the engine emits the object yet (CP4d), so no built output changes.
- **§13 (1.1): OD-R1 and OD-R2 are decided** (PD-0040), each as recommended: the labelled
  `MAX_AVAILABLE` fallback for a refused default view; sovereign 3-month bills for HKD and CNY, with
  none meanwhile. No ruling changes: OD-R1 is a service-layer request rule, and OD-R2's interim
  outcome is Ruling 4.6's.
- **Registry (1.1):** `registry_id` `risk/1.1`; the `benchmark_return` and `risk_active_return`
  entries' missing-data text follows Ruling 6.9 (1.1). The registry digest changes accordingly.

**Fixtures (Ruling 11.4).** This change leaves **`cp4_golden/1.0-part1` unaffected**: part 1 asserts
no benchmark-dependent metric, no comparability object and no selection. `cp4_golden/1.0-part2` is
new and cites `risk/1.1` as its minimum.

**Engineer impact:** the four 1.1 texts above are what part 2 tests. None changes a part-1 behaviour.

**Authority:**

- PD-0014 §3: CAPM and Jensen-alpha methodology, Sortino methodology and statistical sufficiency
  are reserved to `quant-analyst`;
- PD-0006, PD-0007, PD-0025, PD-0036: the state vocabulary is fixed, and every threshold is this
  role's;
- PD-0039: the owner's decisions D1 (synthetic benchmarks now), D2 (a per-currency risk-free
  *series*, no constant), D3 (the scope below) and D5 (the stored benchmark selection);
- CLAUDE.md invariants P1, P3–P7, P9, P12, NFR-001 and PRD §34 (conventions are part of the method).

**Scope (PD-0039 D3):** volatility, downside deviation, maximum drawdown, Sharpe, Sortino, beta,
Jensen's alpha, R², active return, tracking error, information ratio, the benchmark's own return
over the same window (needed for "benchmark comparisons"), the methodology registry and the
sufficiency rules. **Out of scope:** VaR, Expected Shortfall and rolling analytics (after HG3), and
everything in CP5 (concentration, exposure, correlation, risk contribution, drift).

**Inputs read:**

- PRD §3, §8, §11.1–11.4, §13, §14, §16, §17, §18.4, §20.2, §32–§34, §38.3 (CP4), §38.4 (HG3);
- PD-0006, PD-0007, PD-0014, PD-0025, PD-0036, PD-0039; `reviews/CP4_PLAN.md`;
- `reviews/gates/OPEN_METHODOLOGY_DEBT_MAX_DRAWDOWN_CONVENTION.md` (M1-F6);
- `methodology/CP3_PERFORMANCE_CONVENTIONS.md` (`performance/1.12`): header, §0–§2, §4, §5, §6.2,
  §7, §10, §11, §14–§19;
- `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (`market-data/1.11`): §0, Rulings 1.2, 1.6, 2.1–2.5,
  4.7, 4.8, 5.1–5.3, Appendix A.1;
- `methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md`;
- `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md` §0–§2, §5–§9;
  `methodology/HG1_ROUND4_VERIFICATION.md` §13.1–13.2;
  `methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md` Parts A, B and D;
- from `src/` only field and enum names: `product_contract/vocabulary.py` (states, reason codes,
  reference points), `product_contract/methodology_registry.py` (the fifteen §33 field names),
  `performance/registry.py` (the CP3 metric-id style). No `src/` code was run.

> **This document approves nothing.** It approves no gate, admits no source, selects no benchmark,
> changes no product scope and writes no UI wording. Where a question needs the product owner, it
> says so, gives options and a recommendation, and leaves it open (§13).

**Label key** (as in `performance/1.12`):

- **RULING**: binding within the Quant role's authority (methods, conventions, thresholds,
  sufficiency semantics).
- **RECOMMENDATION**: a change I believe is needed in someone else's area. They decide it.
- **OWNER DECISION**: put to the product owner, stated and left open.

**Worked examples and fixtures.** Every expected value was derived by hand from the inputs shown,
with the arithmetic beside it, and re-checked with exact `fractions.Fraction` in an independent
calculator that imports nothing from `src/`
(`methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py`). **No value comes from
running or reading the engine.** All prices, rates and levels are hypothetical.

---

## Answers at a glance (`reviews/CP4_PLAN.md` §5 and the dispatch)

| Question | Answer | Ruling |
|---|---|---|
| Max drawdown (M1-F6) | Peak-to-trough **within the window**, with the window's **base point included** in the peak search; the all-history running maximum is rejected. Closed by a fixture where the conventions disagree, and an exact reconciliation identity against the TWR. | §1 |
| Return series | The `performance/1.12` TWR over each grid period. One return definition. Simple returns. | 2.1, 2.6 |
| Grid | Daily = every weekday; weekly = every **Friday**; monthly = the **last calendar day** of each month. Holdings-independent. Each grid date is valued with the `performance` date-label bundle (each market's latest close ≤ the date, the ECB fixing of the date). | 2.2 |
| Holidays, non-synchronous closes | No special case: a closed market contributes its latest close (0 missed sessions). Zero-return periods are kept. No lead/lag adjustment. | 2.2 |
| Partial periods | Only full grid periods inside the requested window are observations; the stubs are excluded and declared. | 2.3 |
| Flows inside a period | Handled by the TWR; nothing new. | 2.4 |
| Annualization | Periods per year: daily 260, weekly 52, monthly 12. √A for dispersion, ×A for means. No geometric annualization here. | 3.1, 3.2 |
| Estimators | n − 1 around a sample mean; n around a fixed target (downside deviation). | 3.3 |
| √ and regression statistics | All statistics are exact rationals except a final square root, which is rounded **exactly** (certified with integer square roots). Fixture tolerance **0** on presented values. | 3.4 |
| Risk-free rate | A series in the reporting currency; the **13-week (3-month)** sovereign bill; the quote at each period's **start**, accrued as **simple interest over the period's calendar days**. Gaps by publication count, as FX. | §4 |
| Benchmark currency | Translated into R, **unhedged**, at the same ECB fixing the portfolio uses at each grid date. | 5.3 |
| Total or price return | **Total return required** for every benchmark-relative metric. A price-return series gives `INSUFFICIENT_DATA` + `MISSING_BENCHMARK`. | 5.4 |
| Downside threshold | The risk-free rate, for both the downside deviation and Sortino. | 6.3 |
| Beta and alpha | Market-model OLS on total returns gives β and R²; Jensen's alpha uses that same β with excess-return means, annualized arithmetically. | 6.7, 6.8 |
| Active return, TE, IR | Active return = arithmetic difference of the two window TWRs; TE = annualized sample sd of periodic active returns; IR = annualized mean periodic active return / TE. | 6.9–6.11 |
| Sufficiency | Floor = the count any full 1-year window yields; standard = the count any full 3-year window yields: weekly 51/155, daily 259/781, monthly 11/35. Frequency-invariant on full windows. Maximum drawdown, active return and benchmark return have no statistical minimum. | 7.1 |
| Shorter window than requested | Never silently shortened: refused with its detail. `MAX_AVAILABLE` is a separate, labelled request. | 7.2 |
| New reason codes | **None requested.** Details only (PD-0036 precedent). | 7.6 |
| Comparability | Disclose limited comparability for a two-leg metric when the legs' closes differ (the seam) or when, at any grid date, the legs are a different number of sessions behind (the lag). | §8 |
| Registry | A versioned record with the fifteen §33 fields plus seven structured fields. **(1.2)** One file per version, named after its `registry_id`. **(1.9)** The registry in force is `methodology/registry/RISK_1.9_REGISTRY.json`; the 1.0 to 1.8 files are kept as records. **(1.10)** The registry in force is `methodology/registry/RISK_1.10_REGISTRY.json`; the 1.0 to 1.9 files are kept as records. `implementation_version` names the labels the code runs, not minimums (Ruling 9.2 (1.10)). **(1.11)** The registry in force is `methodology/registry/RISK_1.11_REGISTRY.json`, from the market-data/1.16 label move; the 1.0 to 1.10 files are kept as records. | §9 |
| Selection log | **(1.4)** SELECT, CLEAR and REVERSAL. A reversal voids the record it names, and the latest remaining live record is in force. A replacement takes the corrected record's position. A pin that cuts a correction pair is refused. | 5.6 |
| HG1 reconciliation | Table of adopted, amended and superseded rulings. | §10 |
| Fixtures | `cp4_golden/1.0-part1` authored (series spine and single-series metrics, 11 portfolios, every HG3 edge case except the unavailable benchmark). **(1.1)** `cp4_golden/1.0-part2` authored (benchmark-relative metrics, comparability, the four unavailable-benchmark forms; 61 items, each with its biting mutations). **(1.2)** `cp4_golden/1.0-part3` authored (flat benchmark, lags, two sources, ETF proxies, daily and monthly, Current mode, account scope, snapshots, zero-capital periods, split suppression, the default view; 67 items). **(1.3)** Re-issued as `cp4_golden/1.1-part3` (retrieval vintages corrected; R2-L2 added; 70 items). | §11 |
| Default view (PD-0040) | **(1.2)** A service-level composition: the 3Y request, and `MAX_AVAILABLE` with its own window, count and state when the 3Y request is refused for history; the refusal stays in the evidence. | 7.7 |
| Current mode | **(1.2)** `E = D_c(t)`; a benchmark level, fixing or rate is used only if it existed at `t`. **(1.3)** It must also be in `M_t`. | 5.8 |
| Reason code | **(1.3)** Only causes at the result's own state level compete; the count rule has no code. | 7.3 |

---

## 0. Objects, scope and notation

### RULING 0.1: Scope

- **Scopes:** the portfolio (primary) and the account (`performance/1.12` Ruling 4.5, with its flow
  classes). Every formula applies unchanged to either.
- **Not defined here:** risk statistics of a single security, a sleeve or a currency. A holding's own
  return series (from adjusted prices) is CP5 work (`performance` OI-P4, `market-data` MD-OI-3).
- **Currency:** every statistic is computed in the portfolio's reporting currency `R` (PRD §14).
  Changing `R` recomputes everything; it is not a conversion of a statistic. No native-currency
  statistic is defined for a multi-currency scope, as `performance` Ruling 5.6 rules for the TWR.
- **(1.2) Account scope, exactly.** The account's ledger events only. An internal transfer is a flow
  of the account: a cash or in-kind inflow of the receiving account and an outflow of the sending
  one, valued as `performance` Ruling 4.5 says. At portfolio scope it is neutral. A
  benchmark-dependent metric at account scope uses the **portfolio's** selection (Ruling 5.6 (1.2)).
  An account that holds nothing for a whole period has a `ZERO_CAPITAL_PERIOD` (Ruling 2.4), as a
  portfolio does. Fixture R8 (part 3).
- **Modes:** both valuation modes of `performance` Ruling 1.7. In Current mode the window end `E`
  is `D_c(t)`. **(1.2)** The benchmark, its translation and the risk-free quote in Current mode:
  Ruling 5.8.
- **ETFs (PRD §18.4):** an ETF holding is a security. Nothing is looked through. Portfolio-level risk
  statistics are unaffected by that choice, because they use the portfolio's own value path; the
  look-through question matters for CP5's concentration and correlation, not here.

### RULING 0.2: The portfolio measured is the actual one, never a back-cast

The return series is the **actual** history of the portfolio: its own valuations and flows from
the ledger, through `performance/1.12`.

- It is **never** a back-cast of today's holdings at constant weights over past prices. That
  back-cast is a hypothetical portfolio. Presenting its statistics as the portfolio's would breach
  P8 (hypothetical and actual states stay separate) and PD-0014 §2.5 (one coherent analytical
  system: the HG1 prototype's risk figures described a 40/30/20/10 portfolio the user did not hold;
  HG1 round 4 §7.2).
- **Consequences:**
  - a security bought recently contributes only from its purchase date. No price before that date
    is needed (`performance/1.12` §16 item 1: quantity-zero positions are never priced). This is
    the HG3 "recently listed security" case for an established portfolio (fixture P11);
  - a portfolio whose own history is short has short statistics, whatever its holdings' history
    (fixture P8).
- **Known limitation, stated in the registry:** the statistics describe the portfolio as it was
  held over the window. They say nothing about the risk of the current holdings at today's weights.
  A current-weights view, if wanted, is a Scenario Lab object (P8), not a CP4 metric.

### RULING 0.3: Judgment class and wording

- Every metric here is a **Fact** (PRD §20.2): a deterministic computation on stated historical
  inputs. Beta, R² and alpha are **model-based facts**: the result of a stated regression on a stated
  window, labelled as such (PRD §17.2). None is an Interpretation or a Preference-dependent
  judgment. Words such as "high", "risky", "outperformed", "moved more than the market" belong to
  the insight layer (CP6) and need their own rule (PD-0014 §2.3).
- **P6.** Every statistic describes what happened in the window. The registry's wording field
  (Ruling 9.1) forbids predictive language for every entry: no "expected", "will", "should",
  "predicts", "risk you can expect". An annualized volatility is "the dispersion of the window's
  periodic returns, scaled to a year", not the volatility to expect next year.
- **P4.** Each metric names its reference point in the registry: the benchmark (beta, R², alpha,
  active return, TE, IR), the risk-free rate (Sharpe, Sortino, downside deviation), or the
  portfolio's own history (volatility, maximum drawdown). A sufficiency judgment (`LIMITED`) carries
  its own reference point: the threshold, in the same unit as the count (HG1 round 5 Ruling 1(b)).

### Notation

- `R`, `(D, L, M)`, `TV_R`, `X(c→R, D)`, `s(D)`, `u(D)`, `I₀`: as in `performance/1.12` §0.
- **Grid** `G_f`: the set of calendar dates on which a period of frequency `f` ends (Ruling 2.2).
- **Window:** the request gives `(B, E]` (Ruling 2.3). The grid points used are
  `g_0 < g_1 < … < g_n`, all in `[B, E]`. `g_0` is the **base**; the **observations** are the `n`
  periods `(g_{k−1}, g_k]`, `k = 1 … n`.
- `r_k`: the portfolio's return for period `k` (Ruling 2.1). `b_k`: the benchmark's (Ruling 5.3).
  `rf_k`: the risk-free return for period `k` (Ruling 4.3).
- `d_k = r_k − rf_k` (excess), `x_k = b_k − rf_k` (benchmark excess), `a_k = r_k − b_k` (active).
- `z̄ = (1/n) Σ z_k`; `s²(z) = Σ (z_k − z̄)² / (n − 1)`; `S_zw = Σ (z_k − z̄)(w_k − w̄)`.
- `A_f`: periods per year (Ruling 3.1).

---

## 1. Maximum drawdown: the M1-F6 debt, ruled and closed

The debt file (`reviews/gates/OPEN_METHODOLOGY_DEBT_MAX_DRAWDOWN_CONVENTION.md` §5) asks five
things. Rulings 1.1 to 1.5 answer them in order; Ruling 1.6 says how the debt closes.

### RULING 1.1: The canonical convention (debt item 1). Peak-to-trough within the window, from the base.

For a window with grid points `g_0 … g_n` and periodic returns `r_1 … r_n` (Rulings 2.1–2.3):

```
W_0 = 1                                   the base: the valuation at g_0
W_k = W_{k−1} (1 + r_k)                   k = 1 … n   (W_k = 1 + TWR(g_0, g_k], exact)
M_k = max_{0 ≤ j ≤ k} W_j                 the running peak, over the window INCLUDING the base
DD_k = W_k / M_k − 1                      the drawdown at g_k (≤ 0)
MDD = min_{0 ≤ k ≤ n} DD_k                the maximum drawdown, in [−1, 0]
```

- **The running peak never looks before `g_0`.** History before the window does not enter a
  statistic labelled with the window.
- **The base `g_0` is inside the peak search.** A fall in the first period is a drawdown from the
  base.
- **Reported with the value** (lineage, and asserted by the fixture):
  - `trough_date` = the **earliest** `g_k` with `DD_k = MDD`;
  - `peak_date` = the **latest** `g_j`, `j ≤ trough`, with `W_j = M_trough`: the last valuation at
    the high-water mark before the decline that reached the trough;
  - `recovery_date` = the earliest `g_k` after the trough with `W_k ≥ M_trough`, or none;
  - `peak_rule = WITHIN_WINDOW_FROM_BASE` (Ruling 1.3).
- If no `DD_k` is negative, `MDD = 0` and the three dates are none.
- **Exact.** `MDD` is a ratio of two products of rationals: a rational, presented to 10^−12
  (Ruling 3.4).

**Why this convention, and not the all-history running maximum:**

1. **A window label must mean what it says.** "Maximum drawdown (1Y)" is a statement about the
   year. Under the all-history rule, two portfolios with identical paths inside the year get
   different "1Y" figures because of what happened before it.
2. **Reproducibility from the window's inputs (§34, P12).** The all-history figure depends on data
   outside the declared window: on how much history exists. A since-inception figure would change
   when older history is imported, though nothing in the window changed.
3. **Every other statistic of the window uses exactly the window's observations** (HG1 M1 RULING
   1(a), consequence 1: one window, one observation set, one declaration). An all-history peak would
   give the drawdown a different window from the volatility printed beside it.
4. **It is the ordinary definition.** A drawdown statistic for a period is computed on that
   period's cumulative-return path, starting from the period's beginning value (GIPS-style period
   statistics; the maximum drawdown in standard performance texts, e.g. Bacon, *Practical Portfolio
   Performance Measurement and Attribution*: MEMORY, §14 item 6).
5. HG1 round 4 §7.9 already recommended this: "I would fix the peak at the window start, so that
   'Max Drawdown (1Y)' means what it says." Adopted.

**The other concept is a different metric, not a second convention for this one.** "How far below
its all-time high the portfolio stands at `E`" (an *underwater* or *current drawdown* figure) is a
legitimate quantity. It is **not** in CP4's scope. If wanted, it gets its own metric id, its own
registry entry and its own window rule ("since inception, as of `E`"). It may never be presented
under the label "maximum drawdown" for a trailing window.

### RULING 1.2: Agreement with the base rule of trailing-window returns (debt item 2)

**Yes, it must agree, and it does, by construction.**

- The base of a trailing-window return is "the last observation strictly before the window"
  (HG1 M1 RULING 1(a)); `performance/1.12` writes windows as `(B, E]` with the base valuation at the
  end of `B` (§0). The risk window's base is `g_0`, the valuation from which the first periodic
  return is measured (Ruling 2.3). `W_0 = 1` is that base.
- So the drawdown path and the window's return share one anchor. **`W_n − 1` is exactly the TWR
  over the effective window** `(g_0, g_n]`, and the drawdown path is the cumulative chart of HG1 M1
  RULING 1(b) (`n + 1` points), read as running-peak ratios.
- **Including the base in the peak search is what makes them agree.** A rule that starts the peak
  search at the first in-window observation `g_1` would measure the drawdown from a different
  anchor than the return: the M1 chart defect, mirrored onto drawdown. It is rejected.
- **HG1 M1 RULING 1(d) is amended, not reversed** (§10). Its rendering rule stands: a drawdown
  *chart* plots `DD_1 … DD_n`, a state series, and need not prepend an anchor, since `DD_0 = 0` by
  definition. What 1(d) did not say, and this ruling does, is that `M_k` includes `W_0`. A chart
  that drops the anchor point still plots values computed with it.

### RULING 1.3: The declaration in code (debt item 3)

The convention is named, never implied by a slice:

- The engine computes the drawdown **from the window's own periodic series** (Ruling 2.3's object,
  which carries `base_date`, `observation_count` and the grid). It never slices a drawdown series
  computed over a longer history.
- The result's lineage carries **`peak_rule: WITHIN_WINDOW_FROM_BASE`**, the `base_date`, the three
  dates of Ruling 1.1 and the window declaration of Ruling 2.3.
- One function owns the rule. A second implementation (for a chart, an insight or the AI layer)
  must call it, not re-derive it (HG1 M1 RULING 2(i), applied here).

### RULING 1.4: Reconciliation (debt item 4). Yes, against an independent engine fact.

Maximum drawdown is **not** without an engine fact to reconcile against. Two identities hold
exactly in tier E:

| ID | Identity | Where it must run |
|---|---|---|
| **RD-1** | `1 + MDD = 1 + TWR(peak_date, trough_date]`, where the right side is computed by the `performance/1.12` **TWR engine directly** over that sub-window (segment form), not from the risk series | every product call that presents a drawdown (one extra TWR: cheap); the fixtures; the HG3 pack |
| **RD-2** | for every pair `0 ≤ j < k ≤ n`: `TWR(g_j, g_k] ≥ MDD` (no deeper decline exists between grid points) | the test suite and the fixtures (it is O(n²)) |

Also:

- **RD-3:** `MDD ≤ min(0, min_k r_k)`: a single period's fall is a drawdown.
- **RD-4 (metamorphic, subsequence):** for the same base and last grid point, the weekly grid is a
  subset of the daily (weekday) grid, so `MDD_daily ≤ MDD_weekly`. A coarser grid never shows a
  deeper drawdown. Fixture P2-D1 asserts both (equal, −0.1, because P2 moves only on Fridays).

A failed RD-1 or RD-3 at runtime is an engine fault: `INSUFFICIENT_DATA` + `CALCULATION_ERROR`
(`performance` Ruling 11.1). The tolerance is **0** (HG1 M1 RULING 4: two quantities equal by
construction reconcile at identity).

**Why RD-1 is not a restatement.** The risk series is built period by period; RD-1's right side is
one TWR over a window the engine was not asked for, through the segment-form path of
`performance` Ruling 5.2. A defect in the series (a wrong base, a dropped period, a re-gridding)
breaks RD-1 even when the drawdown arithmetic itself is right.

### RULING 1.5: A fixture where the conventions disagree (debt item 5)

`cp4_golden/1.0-part1`, portfolio **P2** (USD, one US listing, weekly closes 100 → **120** (Fri
2025-12-05) → 100 → 110 → 99 → 105):

| Assertion | Window | Canonical (Ruling 1.1) | All-history running max | Base excluded from the peak search |
|---|---|---|---|---|
| **P2-D1** | base 2025-12-12 (level 100), to 2026-01-02 | **−0.1** = 99/110 − 1 (peak 12-19, trough 12-26) | −0.175 = 99/120 − 1 | −0.1 |
| **P2-D2** | base 2025-12-05 (level 120, the all-time high), to 2026-01-02 | **−0.175** = 99/120 − 1 (peak = the base, trough 12-26) | −0.175 | −0.1 |

- **P2-D1 bites the all-history convention**; **P2-D2 bites the base-excluded convention.** Neither
  fixture passes under a wrong reading. That is the debt's "partially blind control" concern (M1
  RULING 6(a)) answered.
- **Required mutations** (each must be shown to flip its assertion from pass to fail, on a scratch
  copy, as `performance` §11 does):
  - **M-DD1** running peak over all history → P2-D1 fails (−0.175 against −0.1);
  - **M-DD2** peak search starting at `g_1` → P2-D2 fails (−0.1 against −0.175);
  - **M-DD3** base moved to `g_1` (the M1 slice error) → P2-D2 fails, and P2-D1's `base_date` fails;
  - **M-DD4** peak date "earliest at the high-water mark" instead of "latest" → P2-D1's DAILY item
    fails (`peak_date` 2025-12-19 against 2025-12-25: the level is flat at 110 from Friday 12-19
    to Thursday 12-25, and the decline starts after 12-25).

### RULING 1.6: How this closes the debt

- **The convention is declared** (Rulings 1.1 and 1.3), it agrees with the return base rule (1.2), it
  has an independent reconciliation (1.4), and it has fixtures and mutations that bite (1.5). All
  five items of the debt's §5 are answered.
- **The debt closes on engine conformance**: when the CP4c engine passes P2-D1 and P2-D2 and the
  mutations M-DD1 to M-DD3 fail as stated. Until then it is **ruled, not closed**.
- **The HG1 prototype is not repaired.** `designs/hg1-prototype-v2/js/data.js:408` implements the
  all-history convention, which this ruling rejects. The prototype is a frozen HG1 artifact (HG1
  approved, PD-0017), it is not product truth, and no engine reads it. Its figure was right on its
  own fixture by coincidence (the debt file §2). It must not be cited as evidence for any drawdown
  figure.
- **RECOMMENDATION (main session):** annotate the debt file "RULED: `risk/1.0` §1 (2026-10-02);
  closes on CP4c conformance (P2-D1, P2-D2, M-DD1–M-DD3)". That file is outside my write paths.

---

## 2. The return series

### RULING 2.1: One return definition: the periodic TWR of `performance/1.12`

For grid points `g_0 < … < g_n` (Ruling 2.3):

```
r_k = TWR(g_{k−1}, g_k]        k = 1 … n,     performance/1.12 Rulings 5.1–5.3, in R, tier E
```

- **No second return definition** (PD-0014 §2.5). The periodic return is the TWR over the
  sub-window, computed by the same engine, with the same flow timing (Ruling 4.2), the same
  segment form (5.2), the same base rules (5.3) and the same states (5.5).
- **It is a total return in `R`**: price, FX, income and costs, exactly as the TWR. Corporate actions
  are value-continuous through the ledger (`market-data` Example 2-A). A split suppression
  (`SOURCE_CONFLICT`) reaches the periods that need a suppressed valuation, as it reaches any TWR.
- **Identity RS-1 (exact):** `Π_{k=1..n} (1 + r_k) = 1 + TWR(g_0, g_n]`, the second computed by the
  TWR engine directly over the whole effective window. It runs in every product call (it is one TWR)
  and fails as `CALCULATION_ERROR`.
- The valuations it needs are those of `performance` Ruling 5.2: the grid points and the two sides
  of each flow day. A valuation on any other day is not an input, so an interior gap that is not at
  a grid point or a flow day does not touch the series.

### RULING 2.2: The grids, and what ends a period across three markets

| Frequency | Grid `G_f`: a period ends at the end of… | `A_f` (Ruling 3.1) |
|---|---|---|
| `DAILY` | **every Monday to Friday** (calendar weekdays, whatever any exchange does) | 260 |
| `WEEKLY` | **every Friday** | 52 |
| `MONTHLY` | **the last calendar day of every month** | 12 |

**Which close ends a period.** A grid date `g` is valued exactly as any as-of date in
`performance/1.12` Ruling 1.7: each listing at the official close of `s(g)`, the latest session
of **its own** calendar on or before `g`; each currency at the ECB fixing `u(g)`. So a weekly period
ending Friday `g` ends:

- at Friday's 15:00 Shanghai close (07:00 UTC) for an A-share,
- at Friday's ~16:10 Hong Kong close (08:10 UTC) for an HK listing,
- at Friday's 14:10 Berlin ECB fixing (12:10 or 13:10 UTC) for every translation,
- at Friday's 16:00 New York close (20:00 or 21:00 UTC) for a US listing.

**Why a calendar grid, and why these days:**

- **One grid for every portfolio and every benchmark.** The grid depends on nothing a portfolio
  holds, so a portfolio and its benchmark are sampled on the same dates by construction, and a
  portfolio's grid does not change when it buys a Hong Kong stock. A grid built from "the sessions of
  the markets held" would move with the holdings and would differ between the two legs of every
  comparison.
- **A grid date is a valuation date, not a session.** No weekday is inferred to be a session
  (`market-data` Ruling 5.3 forbids that). The grid only says *when* the portfolio is valued; the
  valuation itself reads each market's real calendar.
- **Weekly (the PRD §14 default) ends on Friday**: the last weekday, and the close after which no
  market trades until Monday, so each week's period contains each market's full trading week. A
  Wednesday anchor (sometimes used to dodge holiday Fridays) would split every market's week in two
  and gains nothing here, because a holiday is already handled by `s(g)`.
- **Monthly ends on the calendar month-end**: the convention of every monthly return series
  (GIPS monthly valuation; MEMORY, §14 item 7). A month-end on a weekend takes Friday's closes.
- **Daily uses every weekday** so that the daily grid contains the weekly grid (Fridays are
  weekdays). That nesting is what makes Ruling 1.4's RD-4 and the frequency-invariance property of
  Ruling 7.1 hold. A trading-day grid of one exchange would be the wrong exchange for two of the
  three markets.

**Holidays.** No special case.

- A market closed on a grid date contributes its latest close. Its missed-session count is 0, so it
  is `CURRENT` (`market-data` Ruling 5.2: a holiday is not staleness).
- **A week in which a market was closed throughout** (fixture P10: a synthetic closed week) gives
  that market's holdings a local return of 0 for the week; the move appears in the next week's
  period. The period is **kept**. It is an observation of what the portfolio's value did over a week
  in which that market did not trade.
- **Zero-return periods are never dropped**, whether from a holiday, a weekend-only daily period, or
  a portfolio that did not move. Dropping them would make the grid holdings-dependent again, break
  the alignment with the benchmark, and change the period length of the neighbours.
- **Known limitation (registry):** on a weekday grid, holiday periods are zero for the markets that
  were closed and full-information for the others; the dispersion is understated by roughly the
  share of holiday periods, which `A_daily = 260` compensates for on average (Ruling 3.1). At weekly
  and monthly frequency the effect is negligible.

**Non-synchronous closes.** No adjustment.

- The two legs of every comparison, and the holdings within the portfolio, are valued at their own
  closes **for the same date label**. Between New York and the Asian markets that is a 12- to
  14-hour offset, the product's founding constraint (NFR-008; `market-data` Ruling 1.2). It is
  disclosed on every two-leg metric (§8).
- **No lead/lag correction** (Scholes–Williams, Dimson). Those are different estimators. Adding one
  would be a new convention with its own registry entry, not a silent improvement.
- **Weekly is the default because of this** (PRD §14): the offset is a fraction of a day in a
  seven-day period, against a fraction of a day in a one-day period. At daily frequency,
  cross-market covariances, betas and correlations are biased toward zero (the Epps effect; HG1
  round 4 §1.2 D1.3). The registry entries of every metric state it as a known limitation of the
  `DAILY` frequency.

### RULING 2.3: Windows, observations, stubs and the base

**Requests** (the caller supplies one, with a frequency and the end `E`):

| Rule | Requested base `B` |
|---|---|
| `TRAILING_MONTHS` (12, 36, 60; PRD §14's 1Y, 3Y, 5Y) | `sub_months(E, n)` (`performance` Ruling 5.4, end-of-month rule) |
| `SINCE_INCEPTION` | `I₀` (`performance` Ruling 4.4) |
| `CUSTOM` | the caller's `B` |
| **`MAX_AVAILABLE`** (PRD §14's "maximum available"; new here) | see below |

**Validity** is `performance` Ruling 5.4's: `B ≥ I₀` and `B < E ≤` the as-of date. A window before
inception is `INSUFFICIENT_DATA`, no reason, detail `WINDOW_BEFORE_INCEPTION`; before a snapshot,
`INSUFFICIENT_DATA` + `NOT_RECONSTRUCTABLE` (detail `WINDOW_BEFORE_SNAPSHOT`).

**Grid points and observations:**

```
g_0 = the first grid date ≥ B                 the base (it may equal B)
g_n = the last grid date ≤ E
n   = (number of grid dates in [B, E]) − 1    the observation count
```

- `n < 1` → `INSUFFICIENT_DATA`, no reason, detail `NO_FULL_PERIOD`.
- **Stubs.** `(B, g_0]` and `(g_n, E]` are **not observations**. A partial period would have a
  different length from the others and would distort the dispersion. They are declared:
  `stub_start_days = g_0 − B`, `stub_end_days = E − g_n`.
- **The base rule is HG1 M1 RULING 1(a)**: `g_0` is the valuation strictly before the first
  observation's period; it is not an observation.

**Every result declares:** the frequency and grid rule; the requested rule, `B` and `E`; the
**effective window** `base_date = g_0`, `last_period_end = g_n`, `observation_count = n`; the two
stub lengths; and for `MAX_AVAILABLE`, why it starts where it does. This is PRD §14's "state the
actual window/frequency used", and §13.3's observation count.

**`MAX_AVAILABLE`.** Start from the `SINCE_INCEPTION` grid points. If any period is
`INSUFFICIENT_DATA` (Ruling 2.5), let `j` be the **last** such period; the base becomes `g_j`, and
the observations are the periods after it. Lineage: `max_available_start` = `INCEPTION` or
`AFTER_INSUFFICIENT_PERIOD` (with the period's end date and cause).

- It is "the longest window ending at `g_n` in which every period is computable". It is a different
  request from `SINCE_INCEPTION`, which is refused by an early gap.
- It is labelled with its actual window, always. It never answers a `TRAILING_MONTHS` request
  (Ruling 7.2).

**Examples** (fixtures):

- P3-A1: 3Y to Friday 2026-01-02: `B` = Mon 2023-01-02, `g_0` = Fri 2023-01-06, `n` = **156**,
  stubs 4 and 0 days.
- P3-A7: 1Y to Wednesday 2025-12-31: `B` = 2024-12-31, `g_0` = 2025-01-03, `g_n` = 2025-12-26,
  `n` = **51**, stubs 3 and 5 days.
- P1-S1: monthly 1Y to 2025-12-31 (a month-end): `g_0` = `B` = 2024-12-31, `n` = **12**; P1-S2, the
  same request at 2025-12-30: `g_n` = 2025-11-30, `n` = **11**, stubs 1 and 30 days.

### RULING 2.4: External flows inside a period, and periods without capital

- **A period that contains an external flow** has the TWR over that period as its return. The flow
  is neutralised by `performance` Rulings 4.2 and 5.1–5.2, valued at the flow date's close and
  fixing. Nothing new is needed and nothing may be added: in particular **no Modified Dietz, and no
  re-gridding around flow dates** (`performance` §5, rejected alternatives). Fixture P9: a Wednesday
  deposit, invested the same day, leaves every periodic return equal to P3's.
- **A period with no capital at any time** (every day of it is a `ZERO_CAPITAL_RUN` of
  `performance` Ruling 5.3: the portfolio was empty throughout) is **not an observation of a
  return**. Its TWR factor of 1 is an accounting convention, not a measured 0 % return. It makes the
  period `INSUFFICIENT_DATA`, no reason, detail `ZERO_CAPITAL_PERIOD`, and so every statistic over a
  window containing it (Ruling 2.5). `MAX_AVAILABLE` then starts after it.
  - A period that **starts** at value 0 but receives capital at the start of its first day (a new
    portfolio whose base `g_0 = I₀`) is fully invested over the period, by `performance` Ruling 4.2
    (cash inflows at the start of the day). It is a normal observation.
  - A period with capital for part of its days only (emptied and refunded inside it) is a normal
    observation of a partial-exposure period. **Known limitation**, stated in the registry.

### RULING 2.5: States of the series. Nothing is dropped, filled or re-gridded.

Each `r_k` carries the state of its TWR (`performance` Ruling 5.5). For a statistic over the
window:

1. **Any period `INSUFFICIENT_DATA`** → every statistic over the window is `INSUFFICIENT_DATA`, with
   the reason chosen by `performance` Ruling 1.5 among those periods' causes; lineage lists every
   such period with its own cause; detail `PERIOD_INSUFFICIENT`.
2. **Otherwise, any period `LIMITED`** → `LIMITED` + `STALE_DATA`, with the count of `LIMITED`
   periods out of `n` stated beside the value (`stale_period_count`; HG1 round 4 §6 R1: an aggregate
   is `LIMITED` only with the affected share stated as a number); detail `STALE_PERIODS`.
3. **Otherwise, any period `AVAILABLE` + `STALE_DATA`** → `AVAILABLE` + `STALE_DATA`.

**Rejected:**

- **dropping** an insufficient period and computing on the rest: it changes the spacing of the
  observations, joins two non-adjacent periods into a fictitious one for the drawdown path, and
  presents a statistic of a series the portfolio did not have;
- **filling** it (interpolation, a zero return, the benchmark's return): a fabricated observation
  (P5, §32);
- **re-gridding** around it (merging it with a neighbour into a longer period): the merged period's
  variance belongs to a different frequency.

The honest alternatives are a later `B` or `MAX_AVAILABLE`, both labelled.

### RULING 2.6: Simple returns, not logarithmic

`r_k` is the simple return `W(g_k)/W(g_{k−1}) − 1`. Every statistic uses it.

- It is what the TWR is: simple returns compound to the window's return (RS-1).
- A portfolio's simple return is the value-weighted sum of its parts' simple returns; a log return
  is not. CAPM and Jensen's alpha are stated in simple excess returns.
- It is exact (a rational). A logarithm would make every statistic transcendental and every identity
  approximate (`performance` Ruling 2.1).
- **Rejected:** log returns. Their convenience (additivity over time) is not needed: no statistic
  here sums returns across time except the arithmetic means, which are defined on simple returns.

### RULING 2.7: Which listing, which fixing (cross-border specifics)

Stated once, because they are not new:

- **Listing.** A holding is valued at its own listing's close only, never a sibling listing's
  (`market-data` Ruling 2.1; PRD §10.3).
- **FX.** Every translation at grid date `g` uses the ECB fixing `u(g)`, for the portfolio and for
  the benchmark alike (Ruling 5.3). One fixing for both legs is what keeps the comparison from
  carrying an FX-timing difference of its own (HG1 round 4 §9 item 2).
- **Security and FX effects** are not separated in any risk statistic here. The statistics are of
  the total return in `R`. The decomposition of a return into price, FX and interaction is
  `performance` §9 (attribution); a decomposition of *risk* into price and FX is CP5 work.

---

## 3. Annualization and numerics

### RULING 3.1: Periods per year

| Frequency | `A_f` | Why |
|---|---|---|
| `DAILY` | **260** | the weekday grid has exactly 5 periods per week, so `A_daily = 5 × A_weekly`; a weekday grid averages 260.9 dates a year |
| `WEEKLY` | **52** | the universal convention |
| `MONTHLY` | **12** | exact |

- **252 is rejected** for this grid. 252 is the session count of one exchange (roughly NYSE); HKEX
  and SSE/SZSE hold fewer, and the grid is not any exchange's sessions (Ruling 2.2). On a weekday grid
  that includes holidays, scaling by 260 is the consistent choice: if `σ_t²` is the per-session
  variance, the weekday-grid sample variance is about `(sessions/260) σ_t²`, and × 260 gives back
  about `sessions × σ_t²`.
- The HG1 prototype's `/252` and `×252` (round 4 §7.9) are superseded (§10).

### RULING 3.2: How each quantity is annualized

| Quantity | Annualized as | Note |
|---|---|---|
| a dispersion (volatility, downside deviation, tracking error) | × `√A_f` (square-root-of-time) | assumes serially uncorrelated periodic returns (registry limitation; Lo 2002, MEMORY §14 item 5) |
| a mean (the Sharpe, Sortino and IR numerators; Jensen's alpha) | × `A_f` (arithmetic) | an **arithmetic** annualization; it is not the annualized TWR |
| a ratio (Sharpe, Sortino, IR) | (`A_f` × mean) / (`√A_f` × dispersion) = `√A_f` × mean / dispersion | |
| beta, R² | not annualized (dimensionless) | |
| maximum drawdown, active return, benchmark return | **never annualized** | window facts, like the TWR (`performance` Ruling 7.2) |

- **The arithmetic/geometric distinction is declared on every metric** (HG1 round 4 §1.2 D1.2). An
  arithmetic-annualized mean excess return (the Sharpe numerator, Jensen's alpha) is **not** the
  annualized TWR minus the risk-free rate and may never be presented as if it were. The registry
  says which basis each figure uses.
- **No geometric annualization** is defined here. The annualized TWR is `performance` Ruling 7.2's
  metric, with its one-year floor.
- **The one-year floor applies here too, through the sufficiency floor** (Ruling 7.1): no
  annualized statistic is presented from fewer observations than a full year yields. Scaling a mean
  of a few weeks by 52 would state a year that did not happen (the reasoning of `performance`
  Ruling 7.2 and GIPS's rule against annualizing short periods; MEMORY, `performance` §18 item 7).

### RULING 3.3: Estimators

- **Around a sample mean: `n − 1`.** Volatility, the Sharpe denominator, tracking error and the
  regression's sums use the sample (unbiased) variance `s²`. The window is a sample of the
  portfolio's periodic returns, and the mean is estimated from it. (Beta and R² are ratios of sums,
  so the divisor cancels.)
- **Around a fixed target: `n`.** The downside deviation is a root-mean-square shortfall below a
  target that is not estimated from the sample (Ruling 6.3), so no degree of freedom is used: divide
  by the **full** `n`, with periods above the target contributing 0 (Sortino and Price 1994;
  HG1 round 4 §7.5: dividing by the count of downside periods instead inflated the prototype's
  figure by 39 %).
- The HG1 prototype's population moments (÷n) for volatility are superseded (§10).

### RULING 3.4: Exactness, square roots, presentation and tolerance

1. **Tier E (exact).** Every periodic return, risk-free return, benchmark return, mean, sum of
   squares, covariance sum, beta, R², alpha, active return, benchmark return and maximum drawdown is
   an **exact rational** (`Fraction`). Nothing here needs a logarithm or an exponential.
2. **The only irrational step is one final square root.** Each square-root metric is
   `sign × √Q` with `Q` an exact non-negative rational:

   | Metric | `sign` | `Q` |
   |---|---|---|
   | volatility | + | `A s²(r)` |
   | downside deviation | + | `A Σ min(0, d_k)² / n` |
   | tracking error | + | `A s²(a)` |
   | Sharpe | sign of `d̄` | `A d̄² / s²(r)` |
   | Sortino | sign of `d̄` | `A d̄² n / Σ min(0, d_k)²` |
   | information ratio | sign of `ā` | `A ā² / s²(a)` |

   A ratio is never computed as a quotient of two separately rounded roots.
3. **Presented value** (`MetricResult.value`): the `ROUND_HALF_UP` rounding of the exact value to
   **10^−12** (`performance` Ruling 2.2's quantum for returns, weights and shares, extended here to
   every risk statistic, which are all dimensionless or decimal fractions).
4. **The square root is rounded exactly, with integers only** (`performance` Ruling 2.1 method (a),
   which needs no transcendental function here):
   - `N = Q × 10^24` (a rational), `k = isqrt(⌊N⌋)` = `⌊√N⌋`;
   - the magnitude rounds to `k + 1` quanta if `4N ≥ (2k + 1)²`, else to `k`. That is the exact test
     `√N ≥ k + ½`, decided in integers;
   - the sign is applied after, so ties round away from zero, as `ROUND_HALF_UP` does.

   This is exact: no tie rule is needed, and `PRESENTATION_TIE` cannot occur. `performance`'s method
   (b) (`Decimal`, `prec` 50) remains conformant, with its tie rule, but (a) is the product path.
5. **Tolerances.**

   | Comparison | Tolerance |
   |---|---|
   | tier-E identities (RS-1, RD-1, RD-3, Ruling 6.13) | **0** |
   | fixture against engine, rational outputs | **0** on the presented value, and the exact rational |
   | fixture against engine, square-root outputs | **0** on the presented value, and `Q` exactly (`exact_square`) |
   | presented against exact | ≤ 0.5 × 10^−12 |

   **Why 0 is fair to an implementation using method (b):** the part-1 calculator certifies that
   every square-root value in the fixture is at least **10^−18 quanta** (10^−30 absolute) away from a
   rounding boundary (`--check` prints the smallest distance). A correct `Decimal` route at `prec`
   50 cannot round differently there. A future fixture value that fails this certificate is
   re-chosen, never given a tolerance.
6. **Nothing computes from a presented value** (`performance` Ruling 2.1). A Sharpe ratio is computed
   from the exact `d̄` and `s²`, never from the presented volatility.

---

## 4. The risk-free rate (PD-0039 D2)

### RULING 4.1: A series, in the reporting currency, and nothing else

- `rf_k` comes from **one admitted risk-free series per currency**, in **`R`**.
- **The reporting currency, not the holdings' currencies.** The portfolio's returns are in `R`; the
  riskless alternative for an investor measuring in `R` is an `R` instrument. A USD rate against a
  CNY-measured return mixes two currencies' interest levels into the "excess" return (covered
  interest parity). HG1 round 4 §7.9 required the rate to be stated as the reporting currency's;
  this ruling makes it a requirement.
- **No constant** (PD-0039 D2: "a constant hides the window dependence"). **No substitute currency**:
  without an admitted `R` series, the rf-dependent metrics are `INSUFFICIENT_DATA` (Ruling 4.6).
- **No interpolation, no look-ahead** (`market-data` Ruling 1.6's rejected alternatives apply
  unchanged).

### RULING 4.2: The tenor: the 13-week (3-month) sovereign bill

- **USD: the 13-week US Treasury bill.** Other currencies: the closest equivalent sovereign
  instrument of about three months (Ruling 4.6).
- **Why 13 weeks:**
  - it is the conventional money-market reference for performance statistics, with the longest and
    most liquid history;
  - the shortest bills (4-week) carry the largest distortions around US debt-ceiling dates, which
    are not a risk-free return;
  - the term mismatch with a weekly or monthly period is small (a short-end term premium), and is a
    stated limitation, not an error.
- **Rejected:** overnight rates (SOFR, HIBOR overnight, the 7-day repo), which describe a different
  instrument and carry funding-market spikes; a tenor matched to each frequency, which would make
  the Sharpe ratio of one window depend on the frequency through the rate as well as the returns.

### RULING 4.3: From a quoted rate to a per-period return

**The quote at the period's start, accrued as simple interest over the period's calendar days:**

```
f_k   = the latest publication date ≤ g_{k−1}              (the quote known when the period starts)
ρ_k   = the simple rate per calendar day of the quote at f_k
rf_k  = ρ_k × (g_k − g_{k−1})                              exact rational
```

**`ρ` by quote type** (`y` = the quoted rate as a decimal fraction):

| Quote type | `ρ` (per calendar day) | Basis |
|---|---|---|
| `SIMPLE_YIELD` (money-market or investment yield) on an ACT/`B` basis | `y / B` (`B` = 360 or 365, from the source profile) | the yield is simple interest by definition |
| `BANK_DISCOUNT` (US bill discount rate, ACT/360) with term `t` days | `y / (360 − y t)` | the bill's holding-period return `1/(1 − y t/360) − 1`, divided by its `t` days |

**Why each choice:**

- **The start of the period, not the end:** a riskless investment over `(g_{k−1}, g_k]` is made at
  `g_{k−1}` at the rate then quoted. Using the end-of-period quote would put information from after
  the period's start into the benchmark the period is measured against. Fixture P1-S1's July period
  bites this: it uses the 3.65 % quoted on 06-30, not the 7.30 % in force from 07-01.
- **Calendar days, not periods:** interest accrues over weekends and holidays. A daily period from
  Friday to Monday earns three days. Dividing an annual rate by 252, 260 or 52 would ignore that
  (the HG1 prototype's `0.045/252` is superseded, §10).
- **Simple, not compounded, within a period:** the quote is a simple-interest rate, and a bill held
  over less than its term earns pro rata. Compounding a simple rate within a period would invent
  interest on interest the instrument does not pay. Across periods, `rf_k` enters only arithmetic
  means (Ruling 6), never a product.
- **Exact:** every `ρ` and `rf_k` is a rational. Example: 3.65 % on ACT/365 is `0.0365/365 =
  1/10,000` a day; a 31-day month earns `31/10,000`.

**The source profile declares** the quote type, the basis, the term `t` (for a discount rate) and the
unit (percent). These are data, not code, so a confirmed source attestation can set them without a
convention change.

### RULING 4.4: Staleness, gaps and coverage

With `m_k` = the number of publication dates in `(f_k, g_{k−1}]` (Ruling 4.5's calendar):

| Condition | `rf_k` | State of `rf_k` | Reason | Detail |
|---|---|---|---|---|
| `m_k = 0` | the quote at `f_k` | `AVAILABLE` | none | |
| `m_k = 1` | the quote at `f_k` | `AVAILABLE` | `STALE_DATA` | `RISK_FREE_STALE` |
| `m_k = 2` to `4` | the quote at `f_k` | `LIMITED` | `STALE_DATA` | `RISK_FREE_STALE` |
| `m_k ≥ 5` | none | `INSUFFICIENT_DATA` | `STALE_DATA` | `RISK_FREE_STALE` |
| no quote on or before `g_{k−1}` (the series starts after it) | none | `INSUFFICIENT_DATA` | none | `RISK_FREE_UNAVAILABLE` |
| no admitted series for `R` in `M` | none | `INSUFFICIENT_DATA` | none | `NO_RISK_FREE_SOURCE` (with `R`) |
| the publication calendar does not cover the interval | none | `INSUFFICIENT_DATA` | none | `CALENDAR_COVERAGE_GAP` |

- The thresholds are the price and FX thresholds (`market-data` Ruling 5.2), so one staleness scale
  runs through the product.
- `≥ 5` takes `STALE_DATA`, as prices do. `MISSING_FX_HISTORY` stays FX-specific: PRD §32 names that
  condition, and it names nothing for a rate.
- The states of the `rf_k` combine into an rf-dependent statistic like period states (Ruling 2.5).
- A publication on a non-publication day is not expected, so a holiday is not staleness.
- Carry-forward is bounded at 4 missed publications, as for FX.

### RULING 4.5: The publication calendar

A risk-free series is counted on its own **publication calendar**, a new calendar kind
`RATE_PUBLICATIONS`, with the content of `market-data` Ruling 5.3 items 1–9:

- `applies_to`: the series id(s);
- the timezone, the coverage interval, the explicit list of publication dates, `actual_through`,
  evidence (the publisher's holiday notice) and version;
- a nominal publication time (Current mode: a date counts as published only from that time).

It is hand-made from the publisher's notices, never derived from the rate file (circularity,
`market-data` Ruling 5.3). Without it, staleness cannot be counted, and the series fails closed
(`CALENDAR_COVERAGE_GAP`). **Owner action** (as PD-0034 for exchange calendars): the session drafts
it from the publisher's schedule; the owner checks and registers it.

### RULING 4.6: What a source must provide, and what happens without one

**For any currency, a risk-free source is usable only if it provides all of the following**, which
the owner's attestation (PD-0031 method) can check item by item:

1. **Currency and instrument:** a sovereign (or, failing that, a stated interbank) rate in the
   currency, at a tenor of about three months (Ruling 4.2), named exactly (series id).
2. **Quote convention:** quote type (simple yield or bank discount), day-count basis (360/365, or
   actual/actual stated), and for a discount rate the term in days of the quoted bill, per quote if
   it varies.
3. **Unit and precision:** percent or decimal, and the decimals published.
4. **Date semantics:** which date a value is "for", the time of day it represents (for example a
   closing bid), and its time zone.
5. **A publication schedule** from which Ruling 4.5's calendar can be built (holidays and non-
   publication days).
6. **History** reaching at least one period before the earliest window base it must serve (3Y + one
   week for the default; 5Y + one month for the longest PRD window), machine-readable.
7. **Revision policy:** whether published values are revised; each retrieval is a vintage
   (`market-data` Ruling 0.1: one vintage per series in `M`).
8. **Terms** permitting the use (PD-0031/PD-0032: personal/academic, internal; re-attest before any
   commercial use).

**USD (PD-0039 D2's candidate).** The US Treasury's "Daily Treasury Bill Rates" (MEMORY, §14 item 1:
to be confirmed at attestation):

- it publishes, for each business day, the 13-week bill's **bank discount** rate and its **coupon
  equivalent**;
- **use the coupon equivalent as `SIMPLE_YIELD`**, with the basis the Treasury states for it
  (believed ACT/365 for bills of 182 days or less; the attestation confirms it). That avoids needing
  each quote's days to maturity;
- the bank-discount column is a corroboration check only (the two must agree within their rounding);
- the publication calendar is the Treasury's business-day schedule, which follows the US government
  securities market's holidays, **not** the NYSE calendar (Columbus Day and Veterans Day differ);
- **Owner action:** attest the terms and confirm items 2, 4 and 5 against the publisher's
  documentation. Nothing real is used before that.

**CNY and HKD reporting.** No source is admitted, and none is proposed as decided. What is needed is
a source meeting items 1–8. Candidates to examine (MEMORY, §14 item 2; terms unknown):

- **HKD:** the HKMA's Exchange Fund Bills 91-day yield (sovereign, preferred), or HKAB's 3-month
  HIBOR (interbank; it carries a small credit premium, to be stated if used);
- **CNY:** the ChinaBond 3-month government-bond yield (sovereign, preferred), or 3-month SHIBOR
  (interbank).

**Without an admitted `R` series** (every CNY- or HKD-reporting portfolio today):

- **Sharpe, Sortino, downside deviation and Jensen's alpha** are `INSUFFICIENT_DATA`, no reason,
  detail `NO_RISK_FREE_SOURCE` (with `R`). Never a USD rate, never a constant, never 0.
- **Volatility, maximum drawdown, beta, R², active return, tracking error, information ratio and
  benchmark return** do not use the rate (Ruling 6) and are unaffected. That is one reason beta is
  estimated on total returns (Ruling 6.7).
- Fixture P10 (CNY reporting) asserts it.

This is the outcome PD-0039 D2 chose ("(c) none for now" for currencies without a source), and it is
P5's: a number from the wrong currency's rate is not a weaker number, it is a different metric.

---

## 5. Benchmarks (PD-0039 D1, D5)

### RULING 5.1: The `BenchmarkSeries` contract

A benchmark is usable only through a series that carries all of the following (PRD §11.1, §11.4,
§13.3). The analytics read nothing else, so the source can change without the method changing.

| Field | Content |
|---|---|
| `benchmark_id` | stable id, independent of the source |
| `name`, `provider` | the index and its provider, or "proxy: `<listing>`" (Ruling 5.5) |
| `source_id` | an entry of the source registry, with its terms check; included in `source_registry_digest` (`performance` Ruling 1.7 (1.12) item 4) |
| `licensing` | the licence reference and the permitted use (PRD §11.4: licensing metadata travels with the data) |
| `currency` `c_b` | the currency the levels are in |
| `return_basis` | `TOTAL_RETURN_NET`, `TOTAL_RETURN_GROSS` or `PRICE_RETURN`, with the provider's statement of the dividend treatment (for net: the withholding basis the provider applies) |
| `calendar_id` | the index calculation calendar (an `EXCHANGE_SESSIONS` calendar; Ruling 5.2) |
| levels | `(date label, level)` pairs, decimal strings, one per calculation day; `observed_at` = the calculation's scheduled close |
| `vintage` | retrieval time; one vintage per series in `M` (`market-data` Ruling 0.1) |
| `synthetic` | true for fixture series (`market-data` Ruling 4.8: every result computed from them is synthetic) |

A series without a `return_basis` is unlabelled and is refused (PRD §11.3: never mix blindly).

**A source that publishes returns instead of levels** is usable only by exact compounding into
levels: `L(d) = Π (1 + ret_j)` over **every** calculation day `j ≤ d` from a stated base level, with
the same `return_basis` rule. A missing day breaks the chain from that day on (no level exists for
it: `BENCHMARK_NOT_COVERING_WINDOW` for later grid dates until a new base). Returns are never
interpolated, and a vendor's own period returns (weekly, monthly) are never used in place of the
grid's (`market-data` Ruling 2.5 item 4: vendor-derived columns are not inputs).

**(1.3) The base level of a RETURNS-form series.** "A stated base level" above is fixed here, and it
needs no field in the contract or the catalog.

- `L(d₀) = 1`, where `d₀` is the calculation day immediately before the first return in the series
  (the start of that return's day).
- After a break in the chain, the chain restarts at 1 on the calculation day before the first return
  after the break.
- **Why no field is needed.** Every quantity in this document reads a benchmark only through ratios
  `L(g)/L(g′)` of one unbroken chain: `b_k`, `benchmark_return`, and through them every statistic. Any
  base cancels exactly, so the choice cannot change a result. No CP4 surface presents a benchmark
  level.
- **The convention is still recorded**, so that a level is reproducible: lineage carries
  `level_base: UNIT`, `d₀`, and each restart.
- A window whose grid dates span a break has no ratio across it: `INSUFFICIENT_DATA` +
  `MISSING_BENCHMARK`, detail `BENCHMARK_NOT_COVERING_WINDOW`, as above.
- **Interim.** No RETURNS-form source is admitted or proposed (PD-0039 D1: synthetic level series
  only), and no fixture item exercises one. The engineer may therefore leave RETURNS-form ingestion
  unbuilt until a source is put up for admission. Then this rule applies, and a fixture item is added
  first.
  - Until then, a RETURNS-form series is refused **at ingest**, with a lineage cause naming the form,
    so it never becomes a `BenchmarkSeries` in `M`.
  - The analytics then truthfully report `BENCHMARK_SERIES_UNAVAILABLE` for a selection that names
    it.
  - What is not acceptable is to admit the series and then report it as absent.

### RULING 5.2: The benchmark's level at a grid date

`L(g)` = the level of the latest calculation day `≤ g` on the series' calendar, with a missed count
`m_b(g)` = calculation days in `(that day, g]`, and the **price** freshness thresholds of
`market-data` Ruling 5.2:

| `m_b(g)` | State | Reason | Detail |
|---|---|---|---|
| 0 | `AVAILABLE` | none | |
| 1 | `AVAILABLE` | `STALE_DATA` | `BENCHMARK_STALE` |
| 2–4 | `LIMITED` | `STALE_DATA` | `BENCHMARK_STALE` |
| ≥ 5 | `INSUFFICIENT_DATA` | `STALE_DATA` | `BENCHMARK_STALE` |
| no level on or before `g` | `INSUFFICIENT_DATA` | `MISSING_BENCHMARK` | `BENCHMARK_NOT_COVERING_WINDOW` |
| calendar does not cover | `INSUFFICIENT_DATA` | none | `CALENDAR_COVERAGE_GAP` |

### RULING 5.3: Currency treatment: translated into `R`, unhedged, at the portfolio's fixing

```
L_R(g) = L(g) × X(c_b → R, g)            at the ECB fixing u(g), the same rate the portfolio uses at g
b_k    = L_R(g_k) / L_R(g_{k−1}) − 1     exact
```

- **Translated, because the comparison is in `R`.** The portfolio's return in `R` includes its
  currency exposure. A benchmark left in its own currency would put the FX return of the portfolio
  into "active return" and "alpha" as if it were skill or selection. PRD §14 sets the analysis in
  the reporting currency, and §13.3 requires the treatment to be exposed: every result states
  `currency_treatment: TRANSLATED_UNHEDGED (ECB fixing u(g))`.
- **Unhedged**, because V1 holds no FX hedge and a hedged benchmark needs forward points that no
  admitted source provides. A currency-hedged benchmark would be a different `benchmark_id`.
- **The same fixing as the portfolio**, so that neither leg carries a fixing-time difference (HG1
  round 4 §9 item 2). The translation's state combines with the level's (the worse wins), and its
  missed fixings count toward the benchmark leg's lag (§8).
- **Native (untranslated) benchmark returns** are not used by any metric here.

### RULING 5.4: Total return is required

- **Every benchmark-relative metric** (beta, R², alpha, active return, TE, IR) and the benchmark
  return itself **require a `TOTAL_RETURN_NET` or `TOTAL_RETURN_GROSS` series.**
- **Why:** the portfolio series is a total return: income is in the TWR (Ruling 2.1). Against a
  price-return benchmark, active return and alpha are biased upward by the benchmark's dividend
  yield, and the ex-dividend jumps of the benchmark add noise to TE and beta that the portfolio does
  not have. That is the "blind mix" PRD §11.3 forbids.
- **A `PRICE_RETURN` series** gives `INSUFFICIENT_DATA` + `MISSING_BENCHMARK`, detail
  `BENCHMARK_NOT_TOTAL_RETURN`. The benchmark is missing *as a usable reference point*: more data of
  the same kind does not fix it; a total-return series or another selection does.
- **Net or gross** is part of the benchmark's identity, chosen with the benchmark, and stated on
  every result. Net is closer to what a portfolio that records withholding as `TAX` events earns;
  that is advice for the selection, not a method rule.

### RULING 5.5: ETF proxies (only if the owner chooses D1 option (b))

If a listed ETF stands in for an index:

- the series is built **inside the engine** from the ETF's `RAW` closes and its **corroborated** cash
  dividends (`market-data` Rulings 2.3 and 4.5), as a `TOTAL_RETURN_GROSS` series reinvested at the
  ex-date close: `TR_t = TR_{t−1} × (P_t + d_t) / P_{t−1}`, with `d_t` the cash per share whose
  ex-date is `t` (`market-data` Ruling 2.3's `TOTAL_RETURN_ADJUSTED` form);
- a vendor-adjusted series is never the input (`market-data` Ruling 2.5);
- `name` says "proxy", with the ETF and its own fees: an ETF's return is the index's net of the fund's
  expense ratio and tracking difference, a stated limitation;
- the ETF's calendar is its listing's exchange calendar.

**(1.2) Exactly.** This text replaces the word "corroborated" above.

1. **Base.** `TR` at the ETF's first `RAW` close in `M` is that close. The ratios, not the base
   level, enter every metric.
2. **Each later print `t`** (the previous print `t⁻`):
   `TR_t = TR_{t⁻} × f_t × (P_t + d_t) / P_{t⁻}`.
   - `d_t` is the cash dividend per share (per new share on a split date) with ex-date `t`, and 0 if
     there is none.
   - `f_t` is the split ratio `new_units/old_units` with ex-date `t`, and 1 if there is none.
   - An ex-date that is not a print date of the ETF applies at the next print.
3. **Which corporate actions are used.** Those whose status (`market-data` Rulings 4.3 and 4.5) is
   `CORROBORATED`, `SINGLE_SOURCE` or `RESOLVED_BY_EVIDENCE`, at the value used by Ruling 4.3.
   - `SINGLE_SOURCE` does not degrade (`market-data` Ruling 4.3). Dropping a single-source dividend
     would turn the proxy into a partial price return, which is the bias Ruling 5.4 exists to
     prevent.
   - This is an engine-built series. It is not the ledger, so `market-data` Ruling 6.4's
     no-auto-append rule for the user's ledger does not apply to it.
4. **A `DISAGREEMENT`** (feed and filing differ on the amount, ratio or date) means the proxy has no
   usable level from that ex-date on, until a resolution record exists: `INSUFFICIENT_DATA` +
   `SOURCE_CONFLICT`, detail `BENCHMARK_SOURCE_CONFLICT`. Levels before the ex-date are unaffected,
   so a window ending before it is computed (part 3, R5-E3).
5. **Staleness** of the ETF's closes is Ruling 5.2's, on the listing's calendar.
6. **Known limitation:** a corporate action absent from every source cannot be detected here. A
   price discontinuity with no record is the plausibility check of `market-data`, not of this ruling.

Fixtures: part 3, R5-E1 (`CORROBORATED` and `SINGLE_SOURCE` dividends), R5-E2 and R5-E3 (a
`DISAGREEMENT`).

**(1.6) Disagreements in a proxy, stated exactly** (review finding CP4F-5). Item 4 above, "from that
ex-date on", is **replaced** by items 4a and 4b. The chain of item 2 is a product of
consecutive-print ratios, so what a dispute removes is exactly the ratios that need the disputed
input. Nothing else is removed.

- **4a. A disputed print.**
  - **When:** the ETF's price sources disagree on its close for day `u` (`market-data` Rulings
    4.2–4.3).
  - **That day:** the print is **withheld for that day only**. `u` has no level; it is in conflict.
    A grid date whose latest print is `u` (Ruling 5.2's `L(g)` would use `u`) is `INSUFFICIENT_DATA`
    + `SOURCE_CONFLICT`, detail `BENCHMARK_SOURCE_CONFLICT`, as a disputed benchmark level is under
    Ruling 5.7.
  - **The chain links around it:** `TR_{u⁺} = TR_{u⁻} × f × (P_{u⁺} + Σd)/P_{u⁻}`, between the usable
    prints `u⁻` before and `u⁺` after.
    - A dividend or split with ex-date `u` applies at `u⁺`, as item 2 already rules for an ex-date
      on a non-print day. The dividend is then held as cash from `u` to `u⁺` and reinvested at
      `P_{u⁺}`: a one-print difference in reinvestment timing, stated as a limitation.
    - Every ratio not ending on `u` is the same as if the dispute did not exist.
  - **Why not "missing, therefore stale":** the print exists and two sources contradict each other
    about it. That is `SOURCE_CONFLICT`, as for any disputed datum (`market-data` Ruling 4.3).
    Carrying `u⁻`'s level forward as if `u` had no session would present a number for a date on
    which the data is in conflict (mutation M-C34).
  - **Why not "break the chain":** linking around `u` needs no value of `u`. A break, and a restart
    at 1 under Ruling 5.1 (1.3), is for a chain that cannot be linked. That covers a returns-form
    series missing a return, and item 4b.
- **4b. A disputed dividend or split.**
  - **When:** feed and filing disagree on its amount, ratio or date.
  - **The chain breaks at its ex-date `x`.** No factor exists for the link across `x`.
  - **A ratio `L(b)/L(a)` with `a < x ≤ b` is unavailable:** `INSUFFICIENT_DATA` +
    `SOURCE_CONFLICT`, detail `BENCHMARK_SOURCE_CONFLICT`. That covers a statistic with any period
    spanning `x`, and a window fact with `g_0 < x ≤ g_n`.
  - **Ratios entirely before `x`, or entirely from `x` on, are available.** They need no factor
    across the break. This is the Ruling 5.1 (1.3) restart, applied to a proxy.
  - So a window that starts after the ex-date is computed (R5-E4). 1.2's "every level from the
    ex-date on" suppressed it for ever (mutation M-C32).
- **Until a resolution record exists**, 4a and 4b are the complete rule. They fail closed on exactly
  the dates and spans that need the disputed datum, never more. A resolution record
  (`RESOLVED_BY_EVIDENCE`, `market-data` Ruling 4.4), when built, supplies the value, and the day or
  span becomes available.
  - **CP4 does not need it.** Its absence removes only the dates and spans that genuinely need the
    disputed datum.
  - **RECOMMENDATION:** build it with the first real-data increment that admits a second price or
    corporate-action source.
- **Fixtures:**
  - R5-E5: a disputed interior non-grid print, linked around, so the 1Y beta and window facts are
    unchanged;
  - R5-E6: a disputed print at `g_n`, so `SOURCE_CONFLICT`;
  - R5-E4: a window after a disputed dividend's ex-date, `AVAILABLE`.
  - Mutations M-C32, M-C33 and M-C34.

**(1.7) Which statements are one corporate action** (the CP4 engineer's tech plan §17.23 decisions 1
and 3). Items 3, 4 and 4b need to know when a feed statement and a filing statement are about the same
action. For one listing and one action type, the statements of the two independent sides (`FEED`,
`FILING`; `market-data` Rulings 4.5 and 4.6) are matched in this order:

1. **Equal statements pair one-to-one** (type, ex-date, pay date, record date when stated, amount or
   ratio): one `CORROBORATED` action. Two equal pairs on one ex-date (a regular and a special dividend,
   both sides stating both) are two actions.
2. **A shared identity date makes one action.**
   - **Dividend:** the record date (when both state one), the ex-date or the pay date.
   - **Split:** the record date, the ex-date, or an equal ratio within the linking window of item 3.
   - Each connected group of such statements is **one action in `DISAGREEMENT`**, because its
     statements are not equal.
   - The record date comes first because it is the issuer's legal identity of the entitlement (who
     holds on the record date is paid). The ex-date and pay date follow from it under the market's
     settlement rule.
3. **Unpaired statements whose ex-dates are at most 20 sessions apart** (the listing's calendar,
   `market-data` Ruling 6.4a's linking window) are **one action in `DISAGREEMENT`**.
   - Two such statements most likely describe one dividend whose dates one side has wrong, the risk
     `market-data` Ruling 6.4a item 5 names for splits ("one event recorded twice").
   - Applying both would double-count the income in the proxy's total return. That is a fabricated
     return, and P5 forbids it.
   - Failing closed costs only the windows that span the ex-dates (item 4b), and a resolution record
     clears it.
4. **What is left is `SINGLE_SOURCE`**, each applied (item 3).
   - Two statements of the two sides more than 20 sessions apart are two dividends. A fund paying
     monthly is at about 21 sessions, at the window's edge.
   - **Known limitation:** an ETF with a distribution interval of 20 sessions or less, where one side
     misses a payment, gives a needless `DISAGREEMENT`. The failure is closed, never a double count.

**A disputed action's break** (item 4b) is at **every** ex-date its statements name. The true
ex-date is unknown, so the chain cannot be linked across any of them. This confirms the engineer's
decision 3. Its "a split with an equal ratio on another date also conflicts" holds **within the
20-session window** only. Outside it, the two are different splits. Two equal-ratio splits a year
apart are not a dispute.

Statements from one side alone are never matched with each other. Equal ones are one statement
(deduplicated); unequal ones on one ex-date are that side's two actions, as built.

`market-data`'s own corporate-action keys are unchanged: Ruling 6.4d keys F8 split detection by
exact ex-date. This rule governs the proxy's use of dividends and splits only.

**RECOMMENDATION (main session):** when `market-data` builds dividend corroboration for the ledger, it
should adopt the same identity rule, so that one dividend has one identity across the product.

**Fixture:** part 3 (1.7), SYN34 (one-sided statements).

- **R5-E7:** feed 0.50 ex 2025-03-03 against filing 0.50 ex 03-05, 2 sessions apart with no shared
  date. This is one disputed dividend, so a window spanning it is `SOURCE_CONFLICT`. M-C36 (the
  build's "two actions, both applied") gives a number.
- **R5-E8:** feed 0.40 ex 2025-09-02 and filing 0.40 ex 12-01, about 64 sessions apart. These are two
  dividends, both applied. M-C37 (any unpaired pair is disputed) refuses it.

**(1.8) A dividend declared in another currency** (review finding CP4F-12). The proxy is a total
return in the ETF's **price currency** `p` (item 2). A cash dividend whose declared currency `c` ≠ `p`
must enter `d_t` **in `p`**. Adding it unconverted mixes units: CNY 3.60 on a USD 50 print is not a
return. The rule, for each dividend applied under items 3 and 4:

1. **`c = p`:** the declared amount, as before.
2. **The issuer states a payment in `p`** (`paid_currency = p` with `paid_amount`; `market-data`
   Ruling 7.1, where the issuer's own conversion is recorded as stated, never derived): that amount
   is used.
   - It is the issuer's fact about what a holder received, as the ledger uses it.
   - Our FX is not substituted for it.
3. **Otherwise:** `d_t = amount × X(c → p, ex-date)`, the ECB cross at `u(ex-date)`.
   - `u(ex-date)` is the fixing of the ex-date's date label, or the latest earlier one (`market-data`
     Ruling 1.6), with its missed count.
   - **Why the ex-date:** the ex-date is when the dividend leaves the price. The chain reinvests it at
     the ex-date print (item 2), so the value is measured on that day. Index providers convert a
     foreign-currency dividend at the ex-date rate for the same reason.
   - **Why not the pay date:** the pay date would use a rate from days later, for a value that left
     the price on the ex-date (mutation M-C39).
   - **One fixing, the ECB's** (Rulings 2.7 and 5.3): the same source the portfolio and the
     benchmark's own translation use.
4. **Freshness, by `market-data` Ruling 1.6's FX thresholds on that fixing.** The state applies to
   every ratio of proxy levels that spans the ex-date, as item 4b does for a disputed action:
   - a statistic with a period across it;
   - a window fact with `g_0 < ex ≤ g_n`.

   | Missed fixings | State | Reason |
   |---|---|---|
   | 0 | `AVAILABLE` | — |
   | 1 | `AVAILABLE` | `STALE_DATA` |
   | 2–4 | `LIMITED` | `STALE_DATA` |
   | ≥ 5 | `INSUFFICIENT_DATA` | `MISSING_FX_HISTORY` |

   - With 5 or more missed, the ratio is unavailable and no rate is used.
   - The `market-data` lineage carries the rate, the fixing date and the missed count. No risk
     detail is added: this is translation staleness, as in Ruling 5.2's translation row.
   - Ratios not spanning the ex-date are unaffected.
5. **Disclosure.** Lineage records, for each converted dividend:
   - the declared amount and currency;
   - the rate and the fixing date used, or the issuer's stated payment;
   - the converted amount.

   A surface that shows the proxy's composition shows "dividend converted from CNY at the ECB fixing
   of 2025-03-03".
6. **Not refused.** The 1.7 text's silence led to the interim refusal (proxy unavailable from the
   ex-date, M-C42). That interim refusal is superseded: the conversion is determinate and its
   freshness is stated, so refusing would suppress a computable fact.

**Fixture:** part 3 (1.8), SYN35, a USD-traded ETF that declares in CNY. R5-E9 (beta, benchmark
return, active return) covers three dividends:

- CNY 3.60 ex 2025-03-03 at the fresh fixing: `3.60 × 1.08/7.80 = 162/325` USD;
- CNY 2.00 ex 2025-03-14, inside the fixture's CNY gap: converted at 03-12's rate (`1.08/7.839`), 2
  fixings missed, so `LIMITED` + `STALE_DATA` for every ratio spanning it;
- CNY 3.30 ex 2025-09-02 with the issuer's stated USD 0.46, used as stated.

Mutations M-C38 to M-C42 each change all three items.

**(1.9) Which statement's paid fields** (review finding CP4F-15). Which side states the paid fields
is decided by `market-data` Ruling 4.5 (1.14), not by the order of the statements. When both sides
state them, they are compared, and a difference makes the dividend a `DISAGREEMENT` (item 4b). When
one side states them, that side's payment is used under item 2, **whichever side it is**. Fixtures:
part 3 (1.9), SYN35: R5-E10 (the FEED alone states USD 0.44), R5-E11 (the FILING alone states USD
0.43) and R5-E12 (FEED 0.46 against FILING 0.47: `SOURCE_CONFLICT`). M-C46 keeps only the first
statement's paid fields. It ignores R5-E11's payment and computes R5-E12 silently.

### RULING 5.6: The user's primary-benchmark selection (D5) and how a result names it

- **The selection is user data** (PRD §13.1, FR-017), stored per portfolio, append-only (migration
  0015). A record carries: `selection_id`, `portfolio_id`, `benchmark_id` (or **none**, to clear),
  `recorded_at` (instant), and a sequence number. The engine never chooses or defaults a benchmark;
  the system may *recommend* one, outside the engine (PRD §13.1).
- **Which selection applies.** The caller pins a version of the selection log, as it pins `L`. The
  selection in force is the **latest record in that version**, whatever the window: a benchmark is a
  lens the user chooses now, not a historical fact of the window. It is recorded in the manifest, so
  a result reproduces with the selection it used.
  - **(1.1)** A version is a sequence number: the records in force are those with `seq ≤ version`,
    and the selection is the one with the highest `seq` among them. Version 0, or a portfolio with no
    record, has no selection (`NO_BENCHMARK_SELECTED`). A record whose `benchmark_id` is none clears
    the selection.
  - **(1.1)** The engine never substitutes a benchmark when none is in force: not the first in `M`,
    not a recommendation, not the previous selection (part 2, mutations M-B10 and M-B22).
- **Every benchmark-dependent result names** (PRD §13.3): `benchmark_id`, name, provider,
  `return_basis`, `c_b`, `currency_treatment`, the series' `source_id` and content hash,
  `selection_id`, `recorded_at`, the selection-log version, and the window, frequency, observation
  count, calculation timestamp and method version of §2–§3. (The calculation timestamp is manifest
  metadata. It is not part of any digest, so it does not affect reproduction.)
- **No selection, or a cleared one:** `INSUFFICIENT_DATA` + `MISSING_BENCHMARK`, detail
  `NO_BENCHMARK_SELECTED`. A selection whose series is not in `M`: detail
  `BENCHMARK_SERIES_UNAVAILABLE`.
- **When the selection changes,** results computed under the earlier `selection_id` are superseded.
  A surface may not label them current (UAT-03). Because CP4 stores no results, this is a property
  of the manifest: a reader compares its `selection_id` with the latest one.
- **Additional benchmarks** (PRD §13.1, "comparative references") use the same metrics with their own
  `benchmark_id`, and are never labelled primary.
- **(1.2) Account scope.** The selection is per portfolio, and an account has none of its own. A
  benchmark-dependent metric at account scope uses the portfolio's selection in force at the pinned
  version, and names it as above (part 3, R8-K1).

**(1.4) Reversals and corrections (review finding CP4M-4).** Migration 0015 stores three record types:
`SELECT`, `CLEAR` and `REVERSAL`. A SELECT or CLEAR may also be the **replacement** in a correction
pair: it carries `corrects_selection_id`, and is appended in the same transaction as the REVERSAL of
the record it corrects. This text rules what they mean. It replaces the 1.1 sentence "the selection is
the one with the highest `seq` among them" wherever the two differ.

1. **Is a REVERSAL a valid user act? Yes.**
   - It is the user's (or an operator's, on the user's instruction) statement that a recorded SELECT
     or CLEAR **should never have been recorded**: a wrong click, a wrong portfolio, a mis-entry.
   - It is the CP1 shape the ledger already uses: a correction is a reversal plus an optional
     replacement, never an edit. One correction shape across all user data keeps the audit trail
     uniform (P9).
   - It is not a second way of changing one's mind. **A change of mind is a new SELECT or a CLEAR.**
   - The engine never creates a REVERSAL. The system never creates one on its own (FR-017).
2. **Meaning: a reversal voids the record it names, as if it had not been recorded.** A voided record
   is not "no selection", and it is not a CLEAR.
3. **Resolution at a pinned version `v`:**
   1. The known records are those with `seq ≤ v`.
   2. **If a known REVERSAL belongs to a correction pair whose replacement has `seq > v`, the version
      is not pinnable**, and the request is refused. No committed state ever held the reversal
      without its replacement (they are one append), so such a version names a state that never
      existed.
   3. A record is **live** if it is a SELECT or CLEAR and no known REVERSAL names it.
   4. **Position.** A live record's position is its own `seq`, except that a replacement takes the
      position of the record it corrects, followed back to the original record of the chain.
      - A correction says what the original record should have been. It is not a new instruction
        issued now.
      - So **correcting a superseded record does not override a later choice** (R13-V8): the user
        corrects an old entry, and their current choice stays in force.
      - **Correcting the latest record** puts the replacement in force (R13-V10). This is the
        ordinary case, and there the two orderings agree.
   5. **In force:** the live record with the **latest position**. A SELECT gives `IN_FORCE`, a CLEAR
      gives `CLEARED`. No live record gives `NONE`.
   6. The engine never substitutes a benchmark for `NONE` or `CLEARED` (1.1 unchanged).
4. **After a reversal, the prior live record is in force, not NONE.**
   - The earlier record was the user's explicit choice and was never withdrawn. Voiding a later
     record cannot withdraw it.
   - NONE would turn every reversal into a CLEAR, which the user did not ask for and which CLEAR
     already expresses.
   - If no live record remains, the state is NONE (not CLEARED: nothing was cleared).
5. **A reversal of a reversal is refused at append.**
   - To reinstate a voided choice, the user records a new SELECT. It carries its own id and date,
     and the audit trail says plainly what happened.
   - Allowing "un-voiding" would make a record's status depend on a chain of reversals.
   - These are also refused: a second reversal of one record; a reversal or replacement naming
     another portfolio's record; a replacement not appended with its reversal.
6. **Results pinned before and after.**
   - A result computed at version 2 (seq 2 in force, the CN index in R13) names seq 2. It reproduces
     at version 2 **for ever**: a later reversal does not change what version 2 was.
   - At version 3, after seq 3 reverses seq 2, the selection in force is seq 1 (the US index). The
     version-2 result is then **superseded**: its `selection_id` is no longer the one in force, and
     no surface may label it current (UAT-03; the superseded rule above).
   - **RECOMMENDATION (engineer, design):** the evidence states *why* it is superseded:
     - "the record it used was reversed (seq 3)", when a REVERSAL names the result's selection;
     - otherwise "the selection changed" (a later record).

     Both causes are derivable from the log. Neither is a state.
7. **The pin** records the version `v` and the record in force (id, seq, type, benchmark, row digest),
   as built. **(1.4)** It also records the record's position whenever the position differs from its
   seq, that is, for a replacement.

**Fixture:** `cp4_golden/1.2-part3`, portfolio R13. The ten-record log is:

| Seq | Record |
|---|---|
| 1 | SELECT US |
| 2 | SELECT CN |
| 3 | REVERSAL of 2 |
| 4 | CLEAR |
| 5 | REVERSAL of 4 |
| 6 | SELECT CN |
| 7 + 8 | REVERSAL of 1, replaced by the ETF proxy |
| 9 + 10 | REVERSAL of 6, replaced by the two-source US index |

The `selection_resolution` and `benchmark_return` items at versions 2, 3, 4, 5, 7, 8 and 10 give:

| Version | Resolution |
|---|---|
| 2 | CN |
| 3 | US |
| 4 | CLEARED |
| 5 | US |
| 7 | REFUSED |
| 8 | CN (seq 6, not the replacement seq 8) |
| 10 | US two-source |

**The engineer's build differs at version 8.** It orders by sequence alone, so it resolves the ETF
proxy (seq 8). That is mutation M-C29.

### RULING 5.7: Two sources for one benchmark

- A `benchmark_id` may be served by more than one admitted source (for example an index file and a
  second vendor's copy). Their levels for the same calculation day are reconciled exactly as two
  price sources are (`market-data` Rulings 4.1–4.3): the tolerance is the **precision bound** of the
  two published levels (Ruling 4.2), never a judgment.
- **Agreement** within the bound: the primary source's level is used (`market-data` Ruling 4.3's
  order), status `CORROBORATED`.
- **Disagreement** beyond the bound: that day's level is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`
  until a resolution record exists (`market-data` Ruling 4.4). Every grid date that needs it is
  then `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, and so is every benchmark-relative metric over a
  window containing it.
- Two sources with **different `return_basis`** (net against gross, or total against price) are
  two different benchmarks and are never reconciled against each other.
- A synthetic and a real series never meet (`market-data` Ruling 4.8).

**(1.2) Exactly, per calculation day `d`:**

| Sources with a level for `d` | Status | Level used |
|---|---|---|
| two or more, all agreeing within the precision bound | `CORROBORATED` (if their upstreams are independent; else `SINGLE_SOURCE`, `market-data` Ruling 4.3) | the highest-priority source's |
| one only (the others lack `d`) | `SINGLE_SOURCE` | that source's. It is used and does not degrade (`market-data` Ruling 4.3). |
| two or more, differing beyond the bound | `DISAGREEMENT` | none: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, detail `BENCHMARK_SOURCE_CONFLICT`, until a resolution record (`RESOLVED_BY_EVIDENCE`, the recorded value) |
| none | (no level) | Ruling 5.2 falls back to the latest earlier day and counts `d` as missed |

- **Priority** is data: each source of a `benchmark_id` carries a `source_priority` (1 = primary),
  fixed in the source registry, as `market-data` Appendix A fixes the price order. It decides only
  which of two agreeing levels is carried.
- **"Needs it"** means: `L(g)` uses `d` (Ruling 5.2: `d` is the latest calculation day ≤ `g` with a
  level from any source). A disagreement on a day no grid date uses does not affect the result.
  - A statistic reads every grid date of its window.
  - A window fact reads `g_0` and `g_n` only (Ruling 6.9 (1.1)). So a window fact whose ends avoid
    the disputed day is computed (part 3, R4-S1 and R4-S2).
- The resolved level, the status and both sources' levels go to lineage.

Fixtures: part 3, R4-S1 to R4-S3.

**(1.9) The precision bound of a benchmark source is declared, never inferred** (review finding
CP4F-13). `market-data` Ruling 4.2 takes each source's bound from its **profile**, which is data,
and checks it against each file's content. Benchmark sources follow the same rule:

1. **Declarations.**
   - The catalog entry declares the index's **`official_decimals` `D`**: the precision the index
     provider publishes.
   - Each source of the benchmark (the entry's own and each additional one) declares
     **`precision_decimals` `d_X`**: the decimals that source writes.
2. **Bound.** `δ_X = 0` when `d_X ≥ D`, because the source renders the official level exactly, so
   two such renditions must be equal. Otherwise `δ_X = ½ × 10^(−d_X)`: a coarser rendition, which
   only corroborates. Two levels agree iff `|a − b| ≤ δ_A + δ_B` (Ruling 4.2).
3. **Content check.** A level whose text shows more decimals than its source declares contradicts
   the profile, as in `market-data` Ruling 2.4 item 5. That source's file is refused for the series.
4. **Undeclared.** A benchmark served by more than one source without `D` or a source's `d_X` cannot
   be reconciled. It is not a usable series: `INSUFFICIENT_DATA` + `MISSING_BENCHMARK`, detail
   `BENCHMARK_SERIES_UNAVAILABLE`, as for an undeclared second source (the engineer's CP4F-4 rule).
   A single-source benchmark needs no declaration, because nothing is reconciled.

**Why not infer the bound from the most decimals a source shows.**
- It lets the data set its own tolerance, the same circularity the coverage rule refuses
  (`market-data` Ruling 0.1 (1.13)).
- It changes retroactively when a new file shows one more decimal.
- It fails open when a coarse source's texts drop trailing zeros. Its levels "990", "1000" would
  read as 0 decimals, so the bound would be 0.5, not the 0.05 its 1-decimal rounding allows.
  Fixture R4-S4: 990.30 against 990 agrees under inference (M-C45) and disagrees under the declared
  bound.

**Fixtures:**
- part 3 (1.9), SYN4_BM_US_TR5: `D` = 2, a primary with `d` = 2 and a coarser source with `d` = 1,
  disputed on 2025-08-08 (R4-S4);
- SYN4_BM_US_TR4: two sources, nothing declared, so unusable (R4-S6);
- the two sources of SYN4_BM_US_TR2 now declare `D` = `d` = 2. R4-S1 to R4-S3 are unchanged.

### RULING 5.8 (1.2): Current mode, for the benchmark leg and the risk-free rate

In Current mode at instant `t` (`performance` Ruling 1.7 (1.12)):

1. **The window end** is `E = D_c(t)`, resolved from the **portfolio's** inputs only, exactly as
   `performance` rules. The benchmark never moves `E`: the benchmark is a reference for the
   portfolio's window, not a co-owner of it.
2. **A benchmark calculation day `d` exists at `t`** only if its scheduled close (the index's
   calculation calendar, `market-data` Rulings 2.2 and 5.3) is at or before `t`. `L(g)` is the
   latest calculation day ≤ `g` that exists at `t`.
3. **An ECB fixing of date `u` exists at `t`** only if its **publication** time is at or before `t`.
   The rate is unknown before it is published, even though it is fixed at 14:10. Both legs'
   translations obey this. The portfolio's translations already do, through `D_c(t)`.
4. **A risk-free quote** is used for a period only if its publication time is at or before `t`, in
   addition to Ruling 4.3's "latest quote on or before the period's start".
5. **Not yet due is not missed.** A calculation day, fixing or publication that does not exist at `t`
   is neither used nor counted in `m_b(g)`, the FX missed count or the session lag `Λ_B(g)`. The
   market has not failed to publish: the time has not come.
   - So, for an HK portfolio before the US close, the benchmark at `g_n` is Thursday's level,
     `AVAILABLE`, with no `LAGGED` point.
   - The time difference is disclosed where it belongs: in the `SEAM` offset, measured from the
     instants actually used (Ruling 8.3 (1.1)). In part 3, R7-C1 this is 1140 minutes, against 770
     in the historical twin R7-H1.
6. **Lineage** records `valuation_mode`, `t`, `D_c(t)`, and for `g_n` the benchmark day and fixing
   date actually used.
7. **(1.3) `M_t`.** Every Current-mode input is read from `M_t`, the files of `M` retrieved at or
   before `t` (`performance` Ruling 1.7; `market-data` Ruling 2.2 item 6). This applies to the
   benchmark's levels, its translation and the risk-free quotes, as it does to the portfolio's
   prices.
   - So a calculation day, fixing or publication **exists at `t`** if its scheduled close or
     publication is ≤ `t` **and** its file is in `M_t`.
   - Item 5 distinguishes two cases:
     - **not yet due** (close or publication after `t`): not used and not missed;
     - **due but not in `M_t`** (published, not yet retrieved): missed, with the ordinary
       consequences (Ruling 5.2's counts, `STALE_DATA` for a late file). This is `market-data`
       Ruling 1.6's "a late publication can show `m = 1`", applied to the benchmark leg.
   - In `cp4_golden/1.1-part3` the declared file vintages make `M_t` equal to the rows due at `t` at
     both Current-mode instants. So the two cases do not arise there, and the values are those of the
     instant rule alone. The calculator's `--retrieval` verifies this.

**Why.**

- A Current-mode result may not contain a number that did not exist at `t`: no look-ahead (P12,
  §34).
- Calling a future session "stale" would put a `STALE_DATA` reason on every cross-market current
  view for a reason that is not a data fault.

**Rejected:**

- **moving `E` back** until the benchmark's market has closed too. That would hide the portfolio's
  own latest close for a reference series.
- **using the historical (date-labelled) benchmark level** at `D_c(t)`. That is a look-ahead whenever
  the index closes after `t` (mutation M-C1).

Fixtures: part 3, R7-C1, R7-H1 and R7-C2.

---

## 6. The metrics

### RULING 6.1: Common inputs

Every metric of a window uses the same `n` periods (Ruling 2.3). Benchmark-relative metrics use
`b_k` on the same periods; rf-dependent ones use `rf_k` on the same periods. States combine by
Ruling 7.3. Formulas use the notation of §0; `A = A_f`.

### RULING 6.2: Volatility (`risk_volatility`)

```
σ = √( A × s²(r) )          s²(r) = Σ (r_k − r̄)² / (n − 1)
```

The annualized sample standard deviation of the periodic returns. `σ = 0` is a fact (a cash-only
portfolio in `R`). No risk-free or benchmark dependency.

### RULING 6.3: Downside deviation (`risk_downside_deviation`), target = the risk-free rate

```
DD = √( A × (1/n) Σ min(0, d_k)² )          d_k = r_k − rf_k
```

- **The target is the risk-free rate** `rf_k`, period by period.
  - **Why not 0:** a target of 0 measures losses only, and makes the Sortino ratio's numerator
    (excess over the risk-free rate) and denominator (shortfall below 0) refer to different
    thresholds. Sortino and Price's framework requires one target for both (MEMORY, §14 item 4).
  - **Why not a user value:** a minimum acceptable return is a personal constraint, and P7 forbids
    inventing one. A user-supplied target, if the product adds one (Portfolio Policy), would be a
    separate, Preference-dependent metric.
  - **Why the risk-free rate:** it is the non-personal reference point the Sharpe ratio already uses
    (P4), so Sharpe and Sortino differ only in their measure of dispersion. The HG1 prototype used
    the same target (130 of 252 days "below the daily risk-free rate", round 4 §7.5); its
    denominator, not its target, was wrong.
- **Divide by `n`** (Ruling 3.3), periods above the target contributing 0.
- **What it means, stated in the registry (P3):** the dispersion of the shortfalls **below the
  risk-free rate**. It is not a measure of losses. A portfolio of uninvested cash in `R` that earns
  nothing has a positive downside deviation, about the annual risk-free rate divided by `√A` (with a
  constant rate, exactly `√A` times the per-period rate), because every period fell short of the
  riskless alternative.
  That is true, and the explanation must say so (fixture P4-C1: 0.006338769597 over 3Y weekly, at a
  rate of 3.65 % and then 7.30 %).
- **Depends on the risk-free series** (Ruling 4.6 applies without one).

### RULING 6.4: Maximum drawdown (`risk_max_drawdown`)

As Ruling 1.1. No risk-free or benchmark dependency. No statistical minimum (Ruling 7.1).

### RULING 6.5: Sharpe ratio (`risk_sharpe`)

```
Sharpe = (A × d̄) / (√A × s(r)) = sign(d̄) √( A d̄² / s²(r) )          d̄ = (1/n) Σ (r_k − rf_k)
```

- **Numerator:** the arithmetic mean periodic excess return, annualized × A (Ruling 3.2).
- **Denominator: the volatility of the portfolio's returns** (Ruling 6.2), not the standard
  deviation of the excess returns.
  - Sharpe (1994) defines the ex-post ratio with the standard deviation of the *differential*
    return `d_k` (MEMORY, §14 item 3). The two coincide when the rate is constant.
  - **Rejected, for two reasons.** First, it makes the ratio's denominator differ from the volatility
    shown beside it, a parallel truth (PD-0014 §2.5): with this ruling, "Sharpe = annualized mean
    excess return ÷ volatility" holds exactly on the screen. Second, for a riskless path (cash
    only) it divides by the variation of the rate itself and returns a large, finite and meaningless
    number. With the portfolio's volatility, that case is correctly undefined.
- **Undefined when `s²(r) = 0`:** `INSUFFICIENT_DATA`, no reason, detail `ZERO_VOLATILITY` (a
  ratio of excess return to risk is not defined where no risk was taken).

### RULING 6.6: Sortino ratio (`risk_sortino`)

```
Sortino = (A × d̄) / DD = sign(d̄) √( A d̄² n / Σ min(0, d_k)² )
```

- Same numerator as Sharpe; denominator the downside deviation of Ruling 6.3.
- **Undefined:**
  - when `s²(r) = 0` (`ZERO_VOLATILITY`, as Sharpe). Without this, a cash-only portfolio below the
    risk-free rate would show `Sortino = −√A` (−7.21 weekly) whatever the rate: a constant of the
    frequency, not a property of the portfolio (P5, §32: a value that can be mistaken for real
    analytics);
  - when no period falls below the target (`DD = 0`): detail `NO_DOWNSIDE_OBSERVATIONS`.

  Both are `INSUFFICIENT_DATA` with no reason (PD-0036).

### RULING 6.7: Beta and R² (`risk_beta`, `risk_r_squared`): the market model, on total returns

```
β  = S_rb / S_bb                      S_rb = Σ (r_k − r̄)(b_k − b̄),  S_bb = Σ (b_k − b̄)²
R² = S_rb² / (S_bb × S_rr)
```

- The OLS slope and coefficient of determination of `r_k = α_m + β b_k + ε_k` (the single-index
  market model; MEMORY, §14 item 3), on the total returns in `R` of Rulings 2.1 and 5.3.
- **On total returns, not excess returns.** With a time-varying rate, the excess-return slope differs
  from this one by a term in the covariance of the rate with the returns. At these frequencies it is
  negligible, but it is not zero, and choosing it would make beta depend on the risk-free source.
  Total-return beta needs no rate, so beta, R², TE and IR stay available for currencies without an
  admitted risk-free series (Ruling 4.6). With a constant rate the two slopes are identical (HG1
  round 4 §2.5).
- **One beta everywhere.** The β of this ruling is the β inside Jensen's alpha (6.8) and the β shown
  with it (PRD §17.2). No second beta exists.
- **Lineage:** `S_rb`, `S_bb`, `S_rr`, `n`, and the sampling variance of β under the OLS assumptions,
  `v_β = (S_rr − β S_rb) / ((n − 2) S_bb)` (exact). `v_β` is not presented. It is for the insight
  layer (RECOMMENDATION, CP6: a sentence comparing β with 1 should be permitted only when
  `|β − 1| ≥ 1.96 √v_β`, HG1 round 4 verification §13.1–13.2's standard).
- **Undefined:**
  - `S_bb = 0` (the benchmark did not move): β and R² `INSUFFICIENT_DATA`, detail
    `ZERO_BENCHMARK_VARIANCE`;
  - `S_rr = 0` (the portfolio did not move): β = 0 is defined; R² is `0/0`, `INSUFFICIENT_DATA`,
    detail `ZERO_PORTFOLIO_VARIANCE`.

### RULING 6.8: Jensen's alpha (`risk_alpha_jensen`): historical, model-based

```
α_J = A × ( d̄ − β x̄ )          d̄ = mean(r_k − rf_k),  x̄ = mean(b_k − rf_k),  β from Ruling 6.7
```

- Jensen's measure: the window's mean excess return minus β times the benchmark's mean excess
  return (Jensen 1968; MEMORY, §14 item 3), annualized **arithmetically** (× A, Ruling 3.2).
- With a constant rate it equals the intercept of the excess-return regression exactly (fixture
  check, part 2). With a varying rate it differs from that intercept only through the slope
  (Ruling 6.7).
- **It is not the vertical distance on an ex-post market line of geometric window returns** (HG1
  round 4 §2.2, concept 3 against concept 4). It may never annotate that distance.
- **Presented only with** (PRD §17.2): the benchmark (Ruling 5.6), the risk-free series id and its
  mean over the window, β, R², the window, the frequency and `n`. The registry labels it "historical,
  model-based; not a measure of skill", and its wording field forbids "bad", "sell", "underperformed
  the market's expectation" or any predictive phrasing for any sign.
- Depends on the benchmark **and** the risk-free series. `S_bb = 0` → detail
  `ZERO_BENCHMARK_VARIANCE`.

### RULING 6.9: Active return (`risk_active_return`) and benchmark return (`benchmark_return`)

```
benchmark_return = L_R(g_n) / L_R(g_0) − 1  ( = Π (1 + b_k) − 1 )
active_return    = TWR(g_0, g_n] − benchmark_return            arithmetic, not annualized
```

- Both over the **effective window** `(g_0, g_n]`, so the portfolio leg is exactly RS-1's TWR.
- **Arithmetic difference** of the two window returns. **Why, against the geometric
  `(1 + R_p)/(1 + R_b) − 1`:** the displayed difference must be the difference of the two displayed
  returns. A reader who sees "portfolio +5.0 %, benchmark +3.0 %" must be able to reconcile "+2.0 %"
  without a formula (PD-0014 §2.2 and §2.4: the evidence must not be able to refute the sentence). The
  geometric form has merits (it compounds and converts across currencies) and is rejected for that
  reason only. The three figures form a decomposition object (`performance` Ruling 2.4 item 3):
  presented values are apportioned so that the displayed difference equals the difference of the
  displayed legs.
- **Not annualized**, ever (Ruling 3.2).
- `benchmark_return` is single-leg; `active_return` is two-leg (§8). No statistical minimum (7.1).
- **(1.1) Inputs.** Both read the benchmark at **`g_0` and `g_n` only** (Rulings 5.2 and 5.3 apply at
  those two dates), and the portfolio leg's state is that of `TWR(g_0, g_n]` (`performance` Ruling
  5.5). An interior benchmark level is not an input of a window return, as an interior valuation is
  not an input of the TWR (`performance` Ruling 5.2). For the same reason the comparability of an
  active return is measured at `g_0` and `g_n` (Ruling 8.2 (1.1)).
- **(1.1) Presentation.** Each metric's `value` is its own exact value quantized (`performance`
  Ruling 2.2). The **decomposition view** is separate: total = `TWR(g_0, g_n]`, parts =
  (`benchmark_return`, `active_return`), apportioned by `performance` Ruling 2.4 item 3 (largest
  remainder, ties in that order). A surface that shows the three together shows the view; a surface
  that shows one alone shows its value. They can differ by one quantum (part 2, Q1-B1).
- **(1.5) A window that contains a `ZERO_CAPITAL_PERIOD`.** If any grid period of `(g_0, g_n]` held
  no capital at any time (Ruling 2.4), the **active return** is `INSUFFICIENT_DATA`, no reason, detail
  `ZERO_CAPITAL_PERIOD`. It combines with the other causes by Ruling 7.3. The **benchmark return** is
  unaffected: it has no portfolio leg.
  - **What `TWR(g_0, g_n]` means across such a period under `performance/1.12`.** Ruling 5.3 gives a
    run with no capital a factor of **1** (`0/0 = 1`, lineage `ZERO_CAPITAL_RUN`), and the window
    stays as it is. The TWR is then the compounded return of the capital **while invested**, chained
    across the gap. Time out of the market adds nothing to it. As a statement about the user's money
    it is well defined, and `performance` keeps it: this ruling changes nothing in `performance`.
  - **Why it cannot be an active return.** The active return subtracts the benchmark's return over
    the **whole** window, including the weeks the portfolio was empty. Set against the benchmark's
    real movement over those weeks, the factor 1 becomes a **measured 0 %**, and the difference
    reports a performance gap that consists entirely of the benchmark's return over a span the
    portfolio did not exist in.
    - This is the reason Ruling 2.4 gives for statistics: the factor 1 is "an accounting convention,
      not a measured 0 % return".
    - It applies here as soon as the convention is compared with a real return.
    - Ruling 6.9 (1.1) (the state of the portfolio leg is that of the TWR) governs the **data**
      state. This item adds a **definitional** refusal, as Ruling 6.12 does for a degenerate case.
      The two rulings do not conflict: 1.1 never said the TWR's state is the only cause.
  - **Partial capital.** A period with capital for part of its days stays an observation, as in
    Ruling 2.4: the same stated limitation, now also in the active return's registry entry.
  - **Remedy for the user.** A window that starts after the gap (a later `B`, or `MAX_AVAILABLE`,
    whose base Ruling 2.3 moves past the gap).
  - **Fixture:** part 3 (1.5), R9-Z3:
    - 1Y: `INSUFFICIENT_DATA`, `ZERO_CAPITAL_PERIOD` (mutation M-C30 gives `AVAILABLE` 0);
    - the 1Y benchmark return: `AVAILABLE` 0;
    - base 2025-04-01: `AVAILABLE` −25/2678.

### RULING 6.10: Tracking error (`risk_tracking_error`)

```
TE = √( A × s²(a) )          a_k = r_k − b_k
```

The annualized sample standard deviation of the periodic active returns (n − 1, Ruling 3.3). The
"ex-post" tracking error; no risk-free dependency. `TE = 0` is a fact (the portfolio replicated the
benchmark).

### RULING 6.11: Information ratio (`risk_information_ratio`)

```
IR = (A × ā) / TE = sign(ā) √( A ā² / s²(a) )
```

- The annualized mean periodic active return over the tracking error: the Sharpe ratio of the
  active return, with the benchmark in the place of the riskless asset (Sharpe 1994 states the
  information ratio as this generalisation; MEMORY, §14 item 3).
- **Its numerator is not `active_return`.** `A × ā` is an arithmetic annualized mean; `active_return`
  is a window difference of compounded returns. The registry names the numerator "annualized mean
  periodic active return", and no surface may show it under the label "active return".
- **Undefined when `TE = 0`:** detail `ZERO_TRACKING_ERROR`.

### RULING 6.12: Degenerate cases (all `INSUFFICIENT_DATA`, no reason code)

| Metric | Condition | Detail |
|---|---|---|
| Sharpe, Sortino | `s²(r) = 0` | `ZERO_VOLATILITY` |
| Sortino | no `d_k < 0` | `NO_DOWNSIDE_OBSERVATIONS` |
| beta, R², alpha | `S_bb = 0` | `ZERO_BENCHMARK_VARIANCE` |
| R² | `S_rr = 0` | `ZERO_PORTFOLIO_VARIANCE` |
| information ratio | `s²(a) = 0` | `ZERO_TRACKING_ERROR` |

A zero volatility, downside deviation, tracking error or drawdown is a value, never one of these.
None of them is `CALCULATION_ERROR` (PD-0036 §2; HG1 R2).

### RULING 6.13: Identities and metamorphic checks

Exact (tier E, tolerance 0; a failure at runtime is `CALCULATION_ERROR`):

| ID | Identity |
|---|---|
| RS-1 | `Π (1 + r_k) = 1 + TWR(g_0, g_n]` (Ruling 2.1) |
| RS-2 | `Π (1 + b_k) = L_R(g_n) / L_R(g_0)` |
| RD-1, RD-3 | Ruling 1.4 |
| RA-1 | `active_return = TWR(g_0, g_n] − benchmark_return` |
| RQ-1 | `Sharpe² × s²(r) = A d̄²` and `Sortino² × Σ min(0, d)² = A d̄² n` on the exact `Q`s (no rounding) |
| RB-1 | `0 ≤ R² ≤ 1`; `β² S_bb = R² S_rr` |

Metamorphic (property tests; fixtures where named):

1. **Flow neutrality:** an external deposit invested the same day at that day's close changes no
   periodic return and no statistic (P9 equals P3).
2. **Cost basis:** removing every cost basis changes no statistic (P6 equals P3).
3. **Frequency invariance of the state** on full windows (Ruling 7.1; P3-A1/A2, P3-A3).
4. **Subsequence:** `MDD_daily ≤ MDD_weekly` for the same base and end (RD-4; P2-D1).
5. **Scale:** multiplying every holding and flow by a constant changes nothing.
6. **Benchmark identity** (part 2): with the benchmark equal to the portfolio's own series, β = 1,
   R² = 1, TE = 0, active return = 0, IR undefined (`ZERO_TRACKING_ERROR`), alpha = 0.
7. **Constant rate** (part 2): α_J equals the intercept of the excess-return regression.
8. **Determinism:** byte-identical results across runs and `PYTHONHASHSEED` (`performance` 11.3 #7).

---

## 7. Sufficiency

### RULING 7.1: Minimum observations, by metric and frequency

**The thresholds are counts that a full window of the stated length always yields** on the grid of
Ruling 2.2, whatever its end date:

| Frequency | Observations in a full 1-year window | in a full 3-year window | in a full 5-year window |
|---|---|---|---|
| `DAILY` | 259–262 | 781–784 | 1,304–1,305 |
| `WEEKLY` | 51–52 | 155–156 | 260–261 |
| `MONTHLY` | 11–12 | 35–36 | 59–60 |

(Counted exactly over every end date from 2001-01-01 to 2029-12-31, a full 28-year cycle of
weekday and leap-year combinations, with `B = sub_months(E, n)`. The calculator's companion check
in the derivation document repeats the count.)

| Metrics | `INSUFFICIENT_DATA` if `n <` | `LIMITED` if `n <` | `AVAILABLE` from |
|---|---|---|---|
| volatility, downside deviation, Sharpe, Sortino, beta, R², Jensen's alpha, tracking error, information ratio | **N1**: daily **259**, weekly **51**, monthly **11** | **N3**: daily **781**, weekly **155**, monthly **35** | N3 |
| maximum drawdown, active return, benchmark return | **1** (one full period) | — | 1 |

- **N1 = one full year; N3 = three full years** (PRD §14's default lookback).
- **Below N1: no number** (`INSUFFICIENT_DATA`, no reason, detail `INSUFFICIENT_OBSERVATIONS`). Each
  of these statistics is annualized (Ruling 3.2), and annualizing a mean from less than a year states
  a year that did not happen; the same floor applies to the dispersions so that one window has one
  sufficiency floor.
- **N1 to N3: `LIMITED`** with the value (PD-0007), no reason, detail `OBSERVATIONS_BELOW_STANDARD`.
  The caveat changes the conclusion: at one year of weekly data, the standard error of an annualized
  Sharpe ratio is about 1, so its sign is often not established; volatility is known to about ±10 %
  of itself. That is PD-0006's definition of `LIMITED`.
- **Maximum drawdown, active return and benchmark return are window facts**, like the TWR
  (`performance` Ruling 5.5: no minimum length). They are exact path quantities, not estimates, and
  are not annualized. Their registry entries state the limitation that a short window shows only
  what happened in it.
- **Every result carries the count and both thresholds in the same unit** (HG1 round 4 §1.3: "a count
  and a threshold expressed in different units is not a disclosure"; HG1 round 5 Ruling 1(b): the
  `LIMITED` qualifier names the sample and the standard it was judged against).

**Why counts derived from full windows, and not round numbers.** HG1 round 4 §1.4 set "≥ 156 weekly
for AVAILABLE, 52–155 for LIMITED". On the Friday grid, a full 3-year window has 155 observations on
about half of all end dates, and a full year has 51 on some. Those thresholds would have refused a
full window: the "unmeetable by construction" defect HG1 round 4 §1.4 itself diagnosed, and the
frequency disagreement of HG1 round 5 F1. **Consequence, and the property this ruling is built for:
on any full 1-, 3- or 5-year window, the state is the same at every frequency** (HG1 round 5 Ruling
1(c)'s frequency-invariance condition holds by construction). Fixtures P3-A1/A2 (3Y: `AVAILABLE` at
784 daily, 156 weekly, 35 monthly) and P3-A3/A7 (1Y: `LIMITED` at 261 daily, 52 or 51 weekly, 11
monthly) assert it. On a partial window (`CUSTOM`, `MAX_AVAILABLE`) the state can differ by frequency;
it is computed, never assumed.

### RULING 7.2: When the window is shorter than requested

- **A request is answered over the requested window or refused.** Never silently over a shorter one.
  - `TRAILING_MONTHS` with `B < I₀`: `INSUFFICIENT_DATA`, detail `WINDOW_BEFORE_INCEPTION`
    (`NOT_RECONSTRUCTABLE` before a snapshot). Fixtures P3-A5 (5Y on a 3-year portfolio), P8-L1.
  - A window whose series has an `INSUFFICIENT_DATA` period: refused with that period's reason
    (Ruling 2.5). Fixture P7-F1.
- **"Maximum available" is a separate request** (`MAX_AVAILABLE`, Ruling 2.3), answered over its
  actual window with that window declared. Its sufficiency is judged by the same thresholds.
  Fixtures P3-A6, P7-F2, P8-L2.
- **Why:** a "3Y" label on two years of data asserts a year that is not there (`performance` Ruling
  5.4's reasoning for returns). PRD §14's "state the actual window" is met by declaring the effective
  window on every result, and by `MAX_AVAILABLE` when the user wants whatever exists.
- **Which request a default view sends** when the 3Y request is refused is a product choice: OWNER
  DECISION OD-R1 (§13). **(1.2)** Decided (PD-0040); the composition is Ruling 7.7.

### RULING 7.3: How the states combine, and the single reason

A metric's state is the worst of:

1. the window (Ruling 2.3: refusal);
2. the series (Ruling 2.5);
3. the risk-free returns, for rf-dependent metrics (Ruling 4.4);
4. the benchmark levels and translations, for benchmark-dependent metrics (Rulings 5.2–5.4, 5.6);
5. the observation count (Ruling 7.1);
6. the degenerate cases (Ruling 6.12).

The single `reason_code` is chosen by `performance` Ruling 1.5, **unchanged**, including its (1.1)
clause: only causes **at the result's own level** compete. So:

- `MISSING_BENCHMARK` (7th) outranks every missing-data code, as placed in `performance/1.2`;
- an `INSUFFICIENT_DATA` result made so by the count (no code) has **no reason**, even if a `LIMITED`
  stale input carries `STALE_DATA` (fixtures P7-F2 volatility, P4-C2 Sharpe);
- `UNSUPPORTED_ASSET` does not arise: the portfolio series has no asset-domain restriction, and an
  unpriceable holding reaches the series through its valuation state.

Lineage lists **every** cause with its detail, including those that did not set the reason.

**(1.3) Stated exactly.** The text above already meant this; it is written out because a CP3-style
"first code present" reading was possible.

1. **Causes.** Each item of 1–6 above contributes zero or more causes. A cause is a triple
   (state level, reason code or none, detail).
   - The count rule (Ruling 7.1) is the cause (`LIMITED`, **none**, `OBSERVATIONS_BELOW_STANDARD`)
     for N1 ≤ n < N3, or (`INSUFFICIENT_DATA`, **none**, `INSUFFICIENT_OBSERVATIONS`) for n < N1.
   - The degenerate cases of Ruling 6.12, `ZERO_CAPITAL_PERIOD`, `NO_FULL_PERIOD` and
     `WINDOW_BEFORE_INCEPTION` are likewise causes with no code.
2. **State** = the most severe cause level (`AVAILABLE` < `LIMITED` < `INSUFFICIENT_DATA`).
3. **Reason** = the first code, in `performance` Ruling 1.5's order, among the causes **whose level
   equals the state**. An `AVAILABLE` result can carry only `STALE_DATA`. If no cause at the state's
   level has a code, the reason is **none**.
4. **A coded cause at a lower level never supplies the reason.** It stays in the details (for
   example `STALE_PERIODS`) and in lineage.

**Consequences:**

- A result limited by its count alone has no reason, even if a period or input is `AVAILABLE` +
  `STALE_DATA`.
- A result limited by its count **and** by a `LIMITED` + `STALE_DATA` input has `STALE_DATA`,
  because both causes are at the `LIMITED` level.
- `INSUFFICIENT_DATA` is handled the same way.

**The fixture items that separate this from the "first code present at any level" reading**
(mutation M-C24 in part 3):

| Item | State, and the cause that sets it | Lower-level coded cause | Reason under this ruling | Under the other reading |
|---|---|---|---|---|
| **part 3 (1.1), R2-L2**: beta, tracking error and volatility, 1Y weekly | `LIMITED` (n = 52) | the 2025-06-13 period, `AVAILABLE` + `STALE_DATA` | **none** | `STALE_DATA` |
| part 1, P7-F2 volatility (`MAX_AVAILABLE`) | `INSUFFICIENT_DATA` (n = 28) | `LIMITED` + `STALE_DATA` periods | **none** | `STALE_DATA` |
| part 1, P4-C2 Sharpe | `INSUFFICIENT_DATA` (`ZERO_VOLATILITY`) | `LIMITED` + `STALE_DATA` risk-free | **none** | `STALE_DATA` |

R2-L2's volatility is a single-series item, so CP4c can already run it. The **control** is part 3's
R3-X1 beta and TE: `LIMITED` by count **and** by a 2-fixing-stale benchmark translation, so the
reason is `STALE_DATA` under both readings.

**(1.5) A refused window, and which causes still count.** When the window itself is refused
(`WINDOW_BEFORE_INCEPTION`, or `NOT_RECONSTRUCTABLE` with `WINDOW_BEFORE_SNAPSHOT`, Ruling 2.3), there
are no grid dates.

- **Window-dependent causes are not evaluated:** periods, levels, coverage, staleness, the count,
  degenerate cases and comparability.
- **Window-independent causes are:**
  - no selection, or a cleared one (`NO_BENCHMARK_SELECTED`);
  - a selected series absent from `M` (`BENCHMARK_SERIES_UNAVAILABLE`);
  - a price-return series (`BENCHMARK_NOT_TOTAL_RETURN`);
  - no risk-free source for `R` (`NO_RISK_FREE_SOURCE`).
- They combine with the refusal by item 3, so a refused window with no benchmark selected has reason
  `MISSING_BENCHMARK`. The window detail stays in the details.
- With a selected, admitted, total-return benchmark, a refused window gives only the refusal.

Fixture: part 3 (1.5), R6-W0 (60 months, no selection: beta and benchmark return
`MISSING_BENCHMARK` with `NO_BENCHMARK_SELECTED` and `WINDOW_BEFORE_INCEPTION`; mutation M-C31). This
is the CP4 exit test's P7 and P8 "MISSING_BENCHMARK outranks" reading, now pinned.

### RULING 7.4: Detail names (fixed by `risk/1.0`; a rename is a convention change)

| Detail | Meaning | Ruling |
|---|---|---|
| `INSUFFICIENT_OBSERVATIONS` | `n` below N1 | 7.1 |
| `OBSERVATIONS_BELOW_STANDARD` | `n` from N1 to below N3 (`LIMITED`) | 7.1 |
| `NO_FULL_PERIOD` | no complete grid period in the window | 2.3 |
| `WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT` | as `performance` 5.4 | 2.3 |
| `PERIOD_INSUFFICIENT` | a period return is `INSUFFICIENT_DATA` | 2.5 |
| `STALE_PERIODS` | some period returns are `LIMITED` or stale | 2.5 |
| `ZERO_CAPITAL_PERIOD` | a period with no capital throughout | 2.4 |
| `RISK_FREE_STALE`, `RISK_FREE_UNAVAILABLE`, `NO_RISK_FREE_SOURCE` | Ruling 4.4 | 4.4 |
| `NO_BENCHMARK_SELECTED`, `BENCHMARK_SERIES_UNAVAILABLE`, `BENCHMARK_NOT_TOTAL_RETURN`, `BENCHMARK_NOT_COVERING_WINDOW`, `BENCHMARK_STALE` | Rulings 5.2, 5.4, 5.6 | 5 |
| **(1.2)** `BENCHMARK_SOURCE_CONFLICT` | the benchmark level used at a grid date is in `DISAGREEMENT` between two sources, or an ETF proxy's corporate action is (reason `SOURCE_CONFLICT`) | 5.5, 5.7 |
| `ZERO_VOLATILITY`, `NO_DOWNSIDE_OBSERVATIONS`, `ZERO_BENCHMARK_VARIANCE`, `ZERO_PORTFOLIO_VARIANCE`, `ZERO_TRACKING_ERROR` | Ruling 6.12 | 6.12 |
| `CALENDAR_COVERAGE_GAP` | as `market-data` 5.3 | 4.4, 5.2 |

Lineage also carries `peak_rule`, `max_available_start`, `stale_period_count` and the comparability
object (§8).

### RULING 7.5: The HG3 edge cases

| HG3 edge case | What every metric reports | Fixture |
|---|---|---|
| **Insufficient history** | A trailing request before inception: `INSUFFICIENT_DATA`, `WINDOW_BEFORE_INCEPTION`. A window with `n` < N1: dispersion and ratio metrics `INSUFFICIENT_DATA`, `INSUFFICIENT_OBSERVATIONS`; drawdown, active and benchmark return `AVAILABLE`. `n` from N1 to N3: `LIMITED` with the value. | P3-A4, P3-A5, P1-S1, P3-A3 |
| **Missing FX** | A grid or flow-day valuation needing a rate missed for ≥ 5 fixings: that period `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`, and every metric over a window containing it. 2–4 missed: `LIMITED` + `STALE_DATA` with the stale-period count. `MAX_AVAILABLE` starts after the last insufficient period. | P7-F1, P7-F2 |
| **Missing cost basis** | **No effect.** No risk statistic reads cost basis: the series is valuation-based (`performance` Ruling 5.1). `MISSING_COST_BASIS` never appears on a risk metric. A snapshot portfolio's history starts at `S` (Ruling 2.3). | P6-B1 |
| **Cash-only** | In `R` with no interest: volatility **0** (`AVAILABLE`), maximum drawdown **0**, downside deviation **positive** (the shortfall below the risk-free rate, Ruling 6.3), Sharpe and Sortino `INSUFFICIENT_DATA` `ZERO_VOLATILITY`. Part 2: β = 0, R² `ZERO_PORTFOLIO_VARIANCE`, TE = the benchmark's volatility. Cash in a foreign currency: an ordinary FX-return series (next row). | P4-C1 to C3 |
| **Single security** | No special case: the series is the security's total return in `R` while fully invested. | P1, P3 |
| **Multi-currency** | Translation at each grid date's ECB fixing; the statistics are of the return in `R`, never a native return. | P5-M1 (part 2 adds a benchmark in another currency) |
| **Recently listed security** | In an established portfolio: no effect, and no price before purchase is needed (Ruling 0.2). As the whole portfolio: short history, as the first row. | P11-R1, P8-L1/L2 |
| **Unavailable benchmark** | Benchmark-dependent metrics `INSUFFICIENT_DATA` + `MISSING_BENCHMARK` (no selection, series missing, price-return only, not covering the window); benchmark-independent metrics unaffected. | part 2 |

### RULING 7.6: Reason codes (PD-0039 D4): none requested

Every outcome above is expressed with the existing codes (`MISSING_BENCHMARK`, `STALE_DATA`,
`MISSING_FX_HISTORY`, `NOT_RECONSTRUCTABLE`, `SOURCE_CONFLICT`, `CALCULATION_ERROR`) or with no code
and a specific detail, as PD-0036 decided for CP3.

- **Considered and not requested: a code for "no risk-free rate".** It would name a data condition
  that crosses four metrics, the shape of codes the owner has added before (PD-0025, PD-0030). But
  the detail `NO_RISK_FREE_SOURCE` carries the cause and its remedy fully, the state already
  suppresses the number (P5), and PD-0036 chose details for history-shaped conditions. **If** the CP7
  design finds it cannot explain the case from the detail, that is the time to ask: the fallback is
  one code, `MISSING_RISK_FREE_RATE`, requiring a non-`AVAILABLE` state.

### RULING 7.7 (1.2): The default view (PD-0040, OD-R1): a service-level composition

PD-0040 decided OD-R1 as recommended: when the default 3Y request is refused, the default view
shows `MAX_AVAILABLE` with its true window, count and state, and the 3Y refusal stays in the
evidence. This ruling states the composition exactly. It is a **request rule in the service layer**:
it creates no metric, changes no result and relabels nothing (Ruling 7.2 unchanged).

**Inputs:** the metric, the frequency (default `WEEKLY`), the scope, `E` (or `t` in Current mode),
the selection-log version, and the default request (`TRAILING_MONTHS 36`, the registry's
`lookback.default`).

**Composition:**

1. Compute `X` = the metric over the default request. This is an ordinary result.
2. **Fall back** if and only if `X.state = INSUFFICIENT_DATA` **and** `X`'s details include one of:
   - `WINDOW_BEFORE_INCEPTION`;
   - `WINDOW_BEFORE_SNAPSHOT`;
   - `PERIOD_INSUFFICIENT`;
   - `ZERO_CAPITAL_PERIOD`.

   These are the refusals **for the portfolio's history**: too young, or with a gap (OD-R1 as put:
   "younger than three years (or with a gap)"). They are exactly the conditions `MAX_AVAILABLE` is
   built to get past (Ruling 2.3).
3. If it falls back, compute `Y` = the same metric over `MAX_AVAILABLE`, with the same frequency,
   scope, `E` and selection. This is an ordinary result. The view shows `Y` with its own effective
   window, observation count, state and value, **whatever that state is**.
   - `Y` may itself be `INSUFFICIENT_DATA` (part 3, R9-Z1: 40 weekly observations).
   - PD-0040's "LIMITED state" describes the typical case. It is not a promise of a number (P5).
4. The view carries `X` as its **refused** result: the 3Y refusal stays in the evidence.
5. **No fall-back** for any other refusal: a missing, price-return, stale or conflicting benchmark;
   a missing risk-free series; a degenerate case. Then the view shows `X`.
   - `MAX_AVAILABLE` would be refused for the same cause, and showing it would only replace a clear
     reason with a shorter window (part 3, R6-V0).
   - A benchmark-side gap does not move `MAX_AVAILABLE`'s base: Ruling 2.3 moves it past the
     **portfolio's** insufficient periods only.

**Evidence and reproduction.** `X` and `Y` each have their own manifest and reproduce on their own.
**RECOMMENDATION (engineer):** the view's evidence record carries both result digests and the
`fallback` flag, so that an auditor can see the refusal and the substitute side by side (P9).

**How a fixture asserts it.** A `default_view` item (part 3 `format.default_view`) checks the
composition only: `fallback`, a summary of `X` as `refused` (or null), and a summary of what is
`shown`. The same `X` and `Y` also appear as ordinary items, so that the method and the composition
are tested separately. Mutations M-C12 (always fall back) and M-C13 (never fall back) each fail it.
Fixtures: part 3, R6-V1, R6-V0, R9-Z1 and R10-S1.

**(1.6) A history refusal reported by the portfolio leg** (review finding CP4F-10). The owner's
PD-0040 addendum decided the scope: "any history refusal (too young, a gap, a zero-capital period)
falls back to the longest clean window ending today … A missing benchmark is never a fallback
trigger". Item 2 is therefore read **by cause, not by detail name**. The default request's
`INSUFFICIENT_DATA` result triggers the fallback when **any** of its `INSUFFICIENT_DATA`-level causes
comes from the **portfolio's own history**:

- the window before inception or snapshot;
- a period of the series `INSUFFICIENT_DATA`, including `ZERO_CAPITAL_PERIOD`;
- **(1.6)** for a window fact with a portfolio leg (the active return), the leg `TWR(g_0, g_n]`
  being `INSUFFICIENT_DATA`, whatever `performance` detail it carries.
  - Examples: `SPLIT_NOT_APPLIED` from a split suppression, a valuation 5 or more fixings or
    sessions stale, `NON_POSITIVE_BASE`.
  - Each is a gap in the portfolio's history.
  - The statistics beside it, over the same window, report the same gap as `PERIOD_INSUFFICIENT`
    and already fall back.

**Never a trigger:** any benchmark-side cause (selection, series, basis, coverage, staleness, source
conflict) and any risk-free cause. `MAX_AVAILABLE` moves its base past the portfolio's insufficient
periods only (Ruling 2.3), so for those causes it would be refused for the same reason. The owner
excluded the missing benchmark explicitly.

The service needs the portfolio leg's state. Ruling 6.9 (1.1) puts it in the active return's
lineage, so the service reads it there. The detail names are not extended.

Fixture: part 3 (1.6), R11-V1. The 3Y active return is refused by the leg (`SOURCE_CONFLICT`, the
uncovered split), so `fallback: true`. `MAX_AVAILABLE` has no full period after the gap and shows
`NO_FULL_PERIOD`. Mutation M-C35 is the present build, which does not fall back.

**This was not left open.** The addendum's words cover it: a gap is a history refusal whichever
result reports it. I set out no options.

**(For the main session.)** Item 2's trigger set is my reading of PD-0040 together with OD-R1 as put
to the owner. It includes a gap, not only youth. If the owner meant youth only, the set shrinks to
the first two details, and part 3 still holds: its two fallbacks are R9-Z1
(`WINDOW_BEFORE_INCEPTION`) and R10-S1 (`WINDOW_BEFORE_SNAPSHOT`).

---

## 8. Comparability (PD-0014 Part 1)

### RULING 8.1: Which metrics are two-leg

**Two-leg** (portfolio against benchmark): beta, R², Jensen's alpha, active return, tracking error,
information ratio. **Single-leg:** volatility, downside deviation, maximum drawdown, Sharpe, Sortino,
benchmark return.

The risk-free rate is **not a comparison leg**: `rf_k` is the rate known at the period's start, a
rate for the whole period, not a market level at an instant. Sharpe and Sortino are single-leg.

### RULING 8.2: The rule, in sessions

For each grid date `g` used (`g_0 … g_n`):

- each input `i` of a leg has a **session lag** `λ_i(g)`: its missed count at `g` on its own calendar
  (sessions for a price or benchmark level, fixings for an FX rate; `market-data` Rulings 1.6 and
  5.2; Ruling 5.2 here);
- a leg's lag is the largest of its inputs': `Λ_P(g)` over the portfolio's priced holdings and rates
  at `g`; `Λ_B(g)` over the benchmark level and its translation at `g`.

A two-leg result **must disclose limited temporal comparability** when either holds:

1. **`LAGGED`:** at **any** grid date used, `Λ_P(g) ≠ Λ_B(g)`. The legs are then measured a
   different number of sessions behind the date. One session is enough: it is a whole trading day
   of the other leg's market.
2. **`SEAM`:** the two legs' inputs at a grid date have **different scheduled instants**: their
   exchange calendars differ, or one leg is translated at the ECB fixing and the other is not. This is
   the same-date seam of `market-data` Ruling 1.2. Between New York and Hong Kong or Shanghai it is
   always present (HG1 round 4 §5.4). It is a structural property, disclosed with its size.

Otherwise (`FULL`): the same calendars, the same fixing use, and no lag difference at any grid date.
Example: a US-only portfolio in USD against a USD index on the NYSE calendar.

**(1.1) Exactly which inputs and dates.**

- **Grid dates used:** every `g_0 … g_n` for a statistic (beta, R², alpha, TE, IR); `g_0` and `g_n`
  only for `active_return` (Ruling 6.9 (1.1)).
- **Portfolio leg at `g`:** each listing with non-zero quantity at the end of `g` (its calendar, and
  its missed sessions at `g`), and each currency other than `R` that is held at `g` as cash or as a
  listing's currency (the ECB fixing, and its missed fixings at `g`).
- **Benchmark leg at `g`:** the benchmark's calculation calendar (and its missed calculation days at
  `g`), and the ECB fixing if `c_b ≠ R` (and its missed fixings).
- **Instant sets:** the portfolio's is the union over the dates used of its calendar ids, plus the
  ECB if any translation is used; the benchmark's likewise. **`SEAM` holds when the portfolio's set
  is non-empty and differs from the benchmark's.** A portfolio leg with no market input (cash in `R`
  only) has an empty set: it is measured at no market instant, so there is no seam (part 2, Q4-C1).
- **Lag:** `Λ(g)` is the largest missed count among a leg's inputs at `g` (0 if it has none).
- **This is a disclosure, never a state** (PD-0014 §1.3). The value stays `AVAILABLE` (or whatever
  Ruling 7.3 gives) and is shown; "not degraded" is never claimed for a two-leg metric with a
  `LAGGED` or `SEAM` disclosure.
- **Why sessions:** PD-0014 §1.2 item 3 and HG1 round 4 §5.4. A holiday in one market is not a lag
  (its count is 0), so the rule does not fire on every Chinese holiday; a missed print is a lag,
  whatever the wall-clock time.

### RULING 8.3: The disclosure object (lineage, and read by the evidence views)

```
comparability: {
  class: FULL | LIMITED,
  seam: null | { portfolio_instants: [(calendar_id, local close)], benchmark_instants: [...],
                 fx_fixing: "ECB 14:10 Europe/Berlin" | null, max_offset_minutes_at_last_grid_date },
  lagged: { count: k, of: n + 1, points: [ { date: g, portfolio_lag: Λ_P(g), benchmark_lag: Λ_B(g) } ] }
}
```

`class` is `LIMITED` if `seam` is not null or `lagged.count > 0`. The counts are stated as numbers,
as HG1 round 4 §6 R1 requires for a stated share.

**(1.1) The fields, exactly.**

- `seam.portfolio_calendars` and `seam.benchmark_calendars` are the two instant sets of Ruling 8.2
  (1.1), as sorted calendar ids (the ECB fixing appears as the ECB calendar's id). The 1.0 field names
  `portfolio_instants`, `benchmark_instants` and `fx_fixing` are replaced by these two lists.
- `seam.max_offset_minutes_at_last_grid_date`: at `g_n`, each input's instant is the scheduled close
  of the session (or calculation day) actually used, in its calendar's time zone (`market-data` Rulings
  2.2 and 5.3), or 14:10 Europe/Berlin on the fixing date `u` actually used; the field is the largest
  `|p − b|` over a portfolio instant `p` and a benchmark instant `b`, in whole minutes. Example: an HK
  holding in a USD portfolio against a US index on Friday 2026-01-02 has 08:10 UTC (HKEX) and 13:10
  UTC (ECB) against 21:00 UTC (NYSE): 770 minutes.
- `lagged.of` is the number of grid dates used; `lagged.points` lists only the dates where the lags
  differ.
- A result that is `INSUFFICIENT_DATA` carries no comparability object (there is no value to qualify).

---

## 9. The methodology registry

### RULING 9.1: The record shape

Each entry holds the **fifteen PRD §33 fields** (the names of `src/product_contract/
methodology_registry.py`, which also cover PRD §16.3's list), **plus seven structured fields** this
ruling adds, because PRD §16.3, P4, P6, §20.2 and PD-0014 require them and a prose field cannot be
tested:

| Field | Content |
|---|---|
| `metric_name` | the human name |
| `human_definition` | one sentence, historical and descriptive (P6) |
| `formula` | the exact formula, in the notation of §0 |
| `annualization_convention` | Ruling 3.2's row, saying arithmetic or square-root-of-time, or "never" |
| `data_inputs` | the inputs (series, rate, benchmark), with the rulings that define them |
| `minimum_observations` | the N1/N3 table of Ruling 7.1, per frequency, in observations |
| `frequency` | the allowed frequencies, the grid rule of each, and the default (`WEEKLY`) |
| `lookback` | the allowed requests and the default (`TRAILING_MONTHS` 36) |
| `benchmark_dependency` | none, or "the user's primary benchmark, total return, translated unhedged" |
| `risk_free_rate_dependency` | none, or "the 13-week sovereign series in `R`, Ruling 4.3" |
| `missing_data_handling` | Rulings 2.5, 4.4, 5.2, 7.3, in one sentence each that applies |
| `fx_treatment` | "in `R`; each grid date at the ECB fixing `u(g)`; benchmark the same" |
| `corporate_action_treatment` | "through the ledger valuations (`performance` 2.1); benchmark: total return as published or Ruling 5.5" |
| `known_limitations` | a list |
| `implementation_version` | the cited convention ids, `risk/1.0` first |
| **`metric_id`** | the engine id (`risk_volatility`, …) |
| **`judgment_class`** | `FACT` (with `MODEL_BASED` for beta, R², alpha) |
| **`reference_point`** | `BENCHMARK`, `PORTFOLIO_HISTORY`, or `RISK_FREE_RATE` (`vocabulary.ReferencePoint` has the first two; the third is a RECOMMENDATION to the engineer: add it, or record the rate as the reference point in a separate field) |
| **`comparability_class`** | `SINGLE_LEG` or `TWO_LEG` (§8) |
| **`presentation`** | unit, quantum (10^−12), rounding (`ROUND_HALF_UP`), numerics (`EXACT` or `CERTIFIED_SQRT`) |
| **`states`** | the list of (condition, state, reason, detail) the metric can produce |
| **`wording`** | the P6/P3 constraints: words forbidden, and the caveat that may never be dropped |

`defined_in` (the ruling numbers) is carried for audit.

### RULING 9.2: Versioning

- **An entry is identified by its `metric_id`**; its text is identified by the convention id in
  force. A result cites `risk/1.0#risk_volatility` (under 1.1: `risk/1.1#risk_volatility`).
- **Any change to an entry's text is a convention change**, issued as a new id (`risk/1.1`), with a
  change note that names the entries changed and, under Ruling 11.4, the fixtures it leaves
  unaffected.
- **The registry file is versioned with the convention.** Its SHA-256 (of the canonical JSON) is the
  `registry_digest`, recorded in every manifest that presents a CP4 value, and compared by
  `reproduce()` as it compares `identity_digest`.
- `implementation_version` lists every convention id the entry depends on, `risk/1.0` first.
- **(1.2) One file per registry version.**
  - Each version's registry is its own file, named after its `registry_id`:
    `methodology/registry/RISK_<version>_REGISTRY.json`.
  - A file is never edited after its version is issued. A new version is a new file, and the old
    one stays as the record of the old text (P9: one id, one text; a manifest citing `risk/1.0` must
    be able to find the 1.0 registry and recompute its digest).
  - **The engine reads the id from the file's `registry_id` field, never from the file name**, and
    refuses a file whose `registry_id` is not the `risk` id it implements.
  - A manifest records both `registry_id` and `registry_digest` (Ruling 9.4).
- **(1.10) What `implementation_version` names, and when a registry is re-issued.**
  - It names the convention ids the engine **runs** when it computes the entry: the `risk` id first,
    then every dependency at the label the code carries for it. It is **not a minimum version**.
  - **When a dependency's code label moves** (for example `market-data/1.14` → `1.15`), the registry is
    re-issued under a new `risk` id in the same increment, and this document's header moves with it.
    Until the re-issue is synced into the engine, the label move is not complete.
  - **Why not a minimum.**
    - PRD §33 asks each metric to store its *implementation* version.
    - A manifest already records the convention ids that ran. A registry whose field were a minimum
      would sit beside that manifest naming another version of the same dependency, and an auditor
      could not tell a stale registry from a compatible one (P9).
    - The field has moved with the code before: `risk/1.9` moved it to `market-data/1.14` (1.9 change
      note).
  - **Fixtures are different.** A fixture's `convention_sets` stay minimum versions (Ruling 11.4,
    `performance` Ruling 11.6). A fixture asserts values, and a later version that changes nothing it
    asserts leaves them true. A registry states what a result was computed by.
  - Citations of where a rule is defined (for example "`risk/1.9` section 2" in another family's
    registry) are not version fields. They stay valid while the cited text is unchanged.

### RULING 9.3: The entries

The entries are **`methodology/registry/RISK_1.0_REGISTRY.json`**, which is part of the text of
`risk/1.0`. It holds the twelve entries: `risk_volatility`, `risk_downside_deviation`,
`risk_max_drawdown`, `risk_sharpe`, `risk_sortino`, `risk_beta`, `risk_r_squared`,
`risk_alpha_jensen`, `risk_active_return`, `risk_tracking_error`, `risk_information_ratio`,
`benchmark_return`. The engine's registry is data loaded from it, or a copy tested equal to it
(CP4b). The UI never invents a threshold (PRD §16.3): every number a surface shows about sufficiency
comes from `minimum_observations`.

**(1.1)** The file now carries `registry_id` `risk/1.1` and the 1.1 entries (Ruling 6.9 (1.1)). It
keeps its file name; the version is the `registry_id` and the digest, not the name.

**(1.2)** The 1.1 paragraph above is **withdrawn** (Ruling 9.2 (1.2)). The files are:

| File | `registry_id` | Status |
|---|---|---|
| `methodology/registry/RISK_1.0_REGISTRY.json` | `risk/1.0` | the 1.0 text, restored unchanged; a record |
| `methodology/registry/RISK_1.1_REGISTRY.json` | `risk/1.1` | the 1.1 text; a record |
| `methodology/registry/RISK_1.2_REGISTRY.json` | `risk/1.2` | the 1.2 text; a record (was in force under 1.2) |
| `methodology/registry/RISK_1.3_REGISTRY.json` | `risk/1.3` | the 1.3 text; a record |
| `methodology/registry/RISK_1.4_REGISTRY.json` | `risk/1.4` | the 1.4 text; a record |
| `methodology/registry/RISK_1.5_REGISTRY.json` | `risk/1.5` | the 1.5 text; a record |
| `methodology/registry/RISK_1.6_REGISTRY.json` | `risk/1.6` | the 1.6 text; a record |
| `methodology/registry/RISK_1.7_REGISTRY.json` | `risk/1.7` | the 1.7 text; a record |
| `methodology/registry/RISK_1.8_REGISTRY.json` | `risk/1.8` | the 1.8 text; a record |
| `methodology/registry/RISK_1.9_REGISTRY.json` | `risk/1.9` | the 1.9 text; a record (was in force under 1.9) |
| `methodology/registry/RISK_1.10_REGISTRY.json` | `risk/1.10` | the 1.10 text; a record (in force under 1.10, until the market-data/1.16 label move) |
| **`methodology/registry/RISK_1.11_REGISTRY.json`** | **`risk/1.11`** | **(1.11) in force under `risk/1.11`**, part of its text |

The twelve entries are unchanged in 1.2, 1.3 and 1.4. Only `common` changes, as the change notes
list. The engine's registry is loaded from the file in force, or is a copy tested equal to it. It must
be updated to the **1.4** file.

### RULING 9.4: What a CP4 manifest records (PRD §34)

In addition to `performance/1.12`'s manifest (ledger version, `M`, `identity_digest`,
`source_registry_digest`, convention ids):

- the request (rule, `B`, `E`, frequency) and the effective window (Ruling 2.3);
- the risk-free series id and content hash, and for each period `f_k` and `m_k` (or their summary);
- the benchmark block of Ruling 5.6 (series id and hash, selection id, selection-log version);
- the `registry_digest` (Ruling 9.2), and **(1.2)** the `registry_id` read from the file;
- **(1.2)** in Current mode: `valuation_mode`, `t`, `D_c(t)`, and the benchmark day and fixing date
  used at `g_n` (Ruling 5.8);
- **(1.2)** for a default view: both result digests and the `fallback` flag (Ruling 7.7,
  recommendation);
- the comparability object (§8) for two-leg metrics;
- the exact intermediate values: `n`, the sums and means, `Q` for square-root metrics, and for the
  drawdown the three dates. **(1.4) Exactly, per metric** (each an exact rational; `S_zw` and `s²` as in
  §0; `rf̄ = (1/n) Σ rf_k`; `Q` is the radicand of Ruling 3.4):

  | Metric | Intermediates |
  |---|---|
  | volatility | `n`, `r̄`, `S_rr`, `s²(r)`, `Q` |
  | downside deviation | `n`, `rf̄`, `Σ min(0, d_k)²`, `Q` |
  | Sharpe | `n`, `rf̄`, `d̄`, `s²(r)`, `Q`, sign |
  | Sortino | `n`, `rf̄`, `d̄`, `Σ min(0, d_k)²`, `Q`, sign |
  | maximum drawdown | `n`; peak, trough and recovery dates; `W` at the peak and at the trough |
  | beta, R² | `n`, `r̄`, `b̄`, `S_rb`, `S_bb`, `S_rr`, `v_β` (beta) |
  | Jensen's alpha | `n`, `rf̄`, `d̄`, `x̄`, `β` (with its own `S_rb`, `S_bb`) |
  | tracking error | `n`, `ā`, `S_aa`, `s²(a)`, `Q` |
  | information ratio | `n`, `ā`, `s²(a)`, `Q`, sign |
  | benchmark return | `L(g_0)`, `L(g_n)`, the two translation rates and their fixing dates, `L_R(g_0)`, `L_R(g_n)` |
  | active return | `TWR(g_0, g_n]`, the benchmark return, both exact |

  **Where they live:**
  - in the Computation Manifest of the result (the audit record), never in the presented result;
  - included in the result digest that `reproduce()` compares, so that a change in any intermediate
    is a reproduction failure that names the input;
  - `rf̄` is the "risk-free series … and its window mean" that Ruling 6.8 requires alpha to be shown
    with. It is computed here and read by the evidence view; it is never recomputed there.

  The container (field and module names) is the engineer's choice. The content above is not.
- the calculation timestamp (metadata, excluded from every digest).

`reproduce()` recomputes from these and compares the result digest, as `performance` Ruling 11.1
(1.4) requires.

---

## 10. HG1 reconciliation

Rulings from `methodology/HG1_ROUND4_*`, `HG1_ROUND5_*` and `HG1_M1_*` that touch CP4, and what
`risk/1.0` does with each. "Adopts" means the HG1 ruling is now a CP4 rule; "amends" means it stands
with the stated change; "supersedes" means it no longer applies to the engine.

| HG1 ruling | `risk/1.0` | Where |
|---|---|---|
| M1 RULING 1(a): the base is the last observation strictly before the window | **Adopts** for every risk window (`g_0`) | 2.3 |
| M1 RULING 1(b): a cumulative chart has n + 1 points | **Adopts**; the drawdown path is that chart | 1.2 |
| M1 RULING 1(c): the window label names the observations, not the anchor | **Adopts** (`effective_window`) | 2.3 |
| M1 RULING 1(d): drawdown and rolling series are state series; no anchor prepended | **Amends**: the rendering rule stands, and the running peak *includes* the base | 1.2 |
| M1 RULING 2: one function owns the window convention, and declares its rule | **Adopts**, extended to the peak rule | 1.3 |
| M1 RULING 3: "ALL" = first available close, declared | **Adopts** as `SINCE_INCEPTION` (base `I₀`) and adds `MAX_AVAILABLE` | 2.3 |
| M1 RULING 4: identity reconciliation at identity, never widened | **Adopts**, at tolerance 0 | 1.4, 3.4 |
| M1-F6: the max-drawdown convention | **Ruled** | §1 |
| M1-F9 / round 5 F2: "trailing 1Y" of 351–352 days | **Closed for the engine**: `sub_months` (`performance` 5.4) and the declared effective window | 2.3 |
| Round 4 §1.2 D1.1: one observation count, in the frequency used | **Adopts** | 2.3, 7.1 |
| Round 4 §1.2 D1.2: arithmetic and geometric bases presented as one | **Adopts**: every metric declares its basis | 3.2, 6.9, 6.11 |
| Round 4 §1.2 D1.3: weekly is the cross-market default; daily needs a stated limitation | **Adopts** | 2.2 |
| Round 4 §1.3: seven disclosures for benchmark-dependent figures | **Adopts** | 5.6 |
| Round 4 §1.4: thresholds 156/52 weekly, 750/250 daily | **Supersedes** with 155/51 weekly, 781/259 daily, 35/11 monthly: the old ones refused some full windows | 7.1 |
| Round 4 §2.2–2.4: regression alpha is not the ex-post market-line distance; no "predict"/"should" | **Adopts** (no SML metric in CP4) | 6.8 |
| Round 4 §2.5: beta on raw returns is right when the rate is constant | **Amends**: beta is always the total-return market-model slope | 6.7 |
| Round 4 §3: VaR sign convention | **Not addressed**: VaR is out of CP4 scope (PD-0039 D3). It stays an HG1 record | — |
| Round 4 §5.2–5.4: comparability is a disclosure for two-leg metrics; staleness is counted in sessions | **Adopts**, with the session rule made exact | §8 |
| Round 4 §6 and R1/R2: reason-state pairing; stated share for aggregate `LIMITED`; `CALCULATION_ERROR` is an engine fault | **Adopts** | 2.5, 6.12, 7.3 |
| Round 4 §7.2: risk statistics described a different portfolio | **Adopts the principle**: actual history only | 0.2 |
| Round 4 §7.5: downside deviation divides by `N` | **Adopts** | 3.3, 6.3 |
| Round 4 §7.9: rf de-annualized by `/252` | **Supersedes**: calendar-day simple accrual of a quoted series | 4.3 |
| Round 4 §7.9: one USD rate for all portfolios | **Supersedes**: one series per reporting currency | 4.1 |
| Round 4 §7.9: population moments | **Supersedes**: `n − 1` around a sample mean | 3.3 |
| Round 4 §7.9: Sharpe arithmetic-annualized | **Adopts**, declared | 3.2, 6.5 |
| Round 4 §7.9: max-drawdown peak from all history; "fix the peak at the window start" | **Adopts the recommendation** | §1 |
| Round 4 §7.9: rounding inside the data layer | **Adopts the principle** (no rounding before presentation) | 3.4 |
| Round 4 §9 item 1 (frequency) | **Answered**: weekly default, as PRD §14 | 2.2 |
| Round 4 §9 item 2 (one FX fixing for both legs) | **Answered** with `market-data` 1.1: the ECB fixing, the same for both | 5.3 |
| Round 4 §9 item 6 (ETF look-through) | **Answered for CP4**: none; matters for CP5 | 0.1 |
| Round 4 verification §13.1–13.2: 1.96 standard errors before a band or direction claim | **Carried to CP6** as a recommendation, with `v_β` supplied | 6.7 |
| Round 5 Ruling 1(a)–(b): a `LIMITED` qualifier carries the state, the sample, the frequency and the standard | **Adopts**: the result carries all four | 7.1 |
| Round 5 Ruling 1(c): the frequency-invariance condition | **Met by construction** on full windows | 7.1 |
| Round 5 Ruling 2 (SML x-domain), F4–F9 | **Not CP4** (design and claim traceability) | — |
| Round 5 F3: two calendars in one fixture | **Closed for the engine**: registered calendars value every grid date | 2.2 |

---

## 11. Fixtures

### 11.1: The `cp4_golden` plan

| Part | Content | Status |
|---|---|---|
| **1** | The series spine (grids, windows, stubs, `MAX_AVAILABLE`, flows, holidays, states), the risk-free conversion, volatility, downside deviation, maximum drawdown (the M1-F6 disagreement), Sharpe, Sortino, thresholds and frequency invariance; HG3 edge cases: insufficient history, missing FX, missing cost basis, cash-only, single security, multi-currency (FX-return series), recently listed (both forms) | **Authored**: `cp4_golden/1.0-part1` |
| **2** | Beta, R², Jensen's alpha, active return, benchmark return, tracking error, information ratio; a synthetic total-return benchmark (USD, NYSE calendar) and a second in HKD on an HK calendar; a synthetic price-return series; the selection log; comparability (`FULL`, `SEAM`, `LAGGED`); a `BANK_DISCOUNT` risk-free series (HKD); the unavailable-benchmark edge case in all four forms; cash-only against a benchmark; metamorphic #6 and #7 | **(1.1) Authored**: `cp4_golden/1.0-part2` (§11.2a) |
| **3** | Account scope; a snapshot portfolio (`NOT_RECONSTRUCTABLE`, history from `S`); a `ZERO_CAPITAL_PERIOD`; a split suppression reaching the series (`SOURCE_CONFLICT`); Current mode (`E = D_c(t)`, a benchmark level not yet available at `t`). **(1.2)** Also: a flat benchmark; a `LAGGED` date inside a statistic's window; stale FX on the benchmark leg only; two benchmark sources; ETF proxies; `DAILY` and `MONTHLY` benchmark statistics; the default view | **(1.2) Authored**: `cp4_golden/1.0-part3` (§11.2b) |

### 11.2: Part 1, as authored

- `methodology/fixtures/cp4_golden/cp4_golden_part1.json` (`cp4_golden/1.0-part1`): synthetic market
  data (calendars including the new `RATE_PUBLICATIONS` kind, ECB-layout FX with a cyclic HKD rate
  and CNY gaps, five price series, one risk-free series), five listings, eleven portfolios, 24
  assertions, 78 expected items.
- `methodology/fixtures/cp4_golden/CP4_GOLDEN_PART1_DERIVATION.md`: the hand derivation (closed forms
  for the long cyclic series; P1 period by period; every state case).
- `methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py`: the independent calculator.
  `--check` re-derives every expected item from the fixture's inputs and compares; `--closed` re-does
  P3 and P5 from the closed forms. Both pass (§12 of the derivation records the run).

### 11.2a (1.1): Part 2, as authored

- `methodology/fixtures/cp4_golden/cp4_golden_part2.json` (`cp4_golden/1.0-part2`, minimum `risk/1.1`):
  four synthetic benchmarks (US gross total return with gaps, the same levels as price return, a
  total-return series first published 2025-07-04, an HK net total-return index in HKD), a
  `BANK_DISCOUNT` HKD risk-free series, a selection log per portfolio, five portfolios, 16 assertions,
  61 expected items.
- **Every expected item names the mutations that must fail it** (`bites`), from a catalog of 22
  mutations, each a single departure from this text. `--mutations` runs each one and requires that it
  changes **exactly** the items that name it, and that every item names at least one.
- `methodology/fixtures/cp4_golden/CP4_GOLDEN_PART2_DERIVATION.md` and
  `methodology/fixtures/cp4_golden/derivation/cp4_part2_calculator.py` (which reuses the part-1
  calculator for valuation).
- Format additions: a `benchmarks` block (Ruling 5.1 fields; `cycle` with `levels`); per portfolio a
  `benchmark_selections` list (Ruling 5.6 (1.1)); per assertion a `selection_log_version`; per item
  `benchmark`, `comparability`, `v_beta`, `decomposition_view` and `bites`.

### 11.2b (1.2): Part 3, as authored

- `methodology/fixtures/cp4_golden/cp4_golden_part3.json` (`cp4_golden/1.0-part3`, minimum `risk/1.2`).
  - **Inputs:** six listings (one with a missing print, one with a 2:1 split, two ETFs); FX with CNY
    gaps; a flat, a CN (CNY, SSE calendar) and a two-source US benchmark; two ETF proxies; corporate
    actions (a corroborated split, corroborated, single-source and disputed dividends).
  - **Size:** twelve portfolios, 24 assertions, 67 expected items, every item with its biting
    mutations (23 in the catalog, M-C1 to M-C23).
- **Format additions:**
  - `valuation_mode` / `instant` per assertion, and `as_of_resolved` per item;
  - `scope` per item;
  - several benchmark entries with one id (`source_priority`, `level_overrides`);
  - `construction: ETF_PROXY`;
  - `corporate_actions` with per-side amounts;
  - `cycle` as a list;
  - the item kind `default_view` (Ruling 7.7).
- `methodology/fixtures/cp4_golden/CP4_GOLDEN_PART3_DERIVATION.md` and two independent derivations:
  - `derivation/cp4_part3_calculator.py`, a day-by-day replay that reuses the part-2 and part-1
    calculators. `--check`, `--closed` and `--mutations` all pass.
  - `derivation/cp4_part3_closed_forms.py`, which writes the periodic returns from the cycles
    directly, shares no code with the calculator, and re-derives 22 long-series values. All agree.

**(1.3) Re-issued as `cp4_golden/1.1-part3`** (same file; minimum `risk/1.3`). It now has 25
assertions and 70 expected items; the catalog has 24 mutations (M-C1 to M-C24); the closed forms
re-derive 25 values.

1. **Retrieval (an input error in 1.0, corrected).**
   - **What was wrong.** 1.0 declared every file retrieved at 2022-11-30, before all its rows. Under
     `market-data` Ruling 3.1's after-retrieval test, every series is then contradicted.
   - **The correction.** `market_data.retrieval` now declares three vintages per series:
     - V1: the rows to 2026-01-08, retrieved 2026-01-09T00:00Z;
     - V2: the rows of 2026-01-09, each retrieved at its own calendar's close or publication instant;
     - V3: the rest, retrieved 2026-04-01T00:00Z.
   - **What this guarantees.** Every file is retrieved after its rows exist. At both Current-mode
     instants (R7), `M_t` holds exactly the rows due.
   - **For the loader.** It must reproduce these vintages. One file per series retrieved after its
     last session leaves `M_t` empty on 2026-01-09, and R7-C1 and R7-C2 fail.
   - **Verified.** `cp4_part3_calculator.py --retrieval` checks both properties and rejects both
     wrong declarations.
2. **R2-L2** (new): the 1Y beta, tracking error and volatility of R2. They are `LIMITED` by count with
   an `AVAILABLE` + `STALE_DATA` period, so the reason is none (Ruling 7.3 (1.3)). Mutation M-C24
   fails exactly these three items.

**(1.4) Re-issued as `cp4_golden/1.2-part3`** (same file; minimum `risk/1.4`). It adds portfolio R13
(Ruling 5.6 (1.4)): a ten-record selection log, seven assertions and 13 items. The new item kind
`selection_resolution` asserts the resolution alone (`NONE`, `CLEARED`, `IN_FORCE` or `REFUSED`, with
the record in force). New record fields are `record_type`, `reverses_selection_id`,
`corrects_selection_id` and `atomic_with_seq`. Mutations M-C25 to M-C29 are added. In total: 13
portfolios, 32 assertions, 83 items, 29 mutations. No 1.1-part3 item changes.

**(Fixture note, not a ruling change.) Re-issued as `cp4_golden/1.3-part3`** with minimum
`market-data/1.12`. This follows `market-data` Ruling 0.1 (1.12): a series may come in several files
when each covers its own dates, but a date may never come from two files.

- The V1/V2/V3 vintages are declared as **coverage segments of one series**, with no vintage label in
  any identity field.
- Release-build cases RB-1 to RB-5 are added, with mutations M-R1 to M-R4.
- No item changes.

**(Fixture note.) Re-issued as `cp4_golden/1.4-part3`** with minimum `market-data/1.13` (Ruling
0.1 (1.13)): release cases RB-6 to RB-9 and mutations M-R5 to M-R7 are added. No item changes.

**(1.5) Re-issued as `cp4_golden/1.5-part3`** (minimum `risk/1.5`):

- R9-Z3: an active return over a window with a zero-capital period, plus two controls;
- R6-W0: a refused window with no selection;
- mutations M-C30 and M-C31;
- in total 13 portfolios, 34 assertions, 88 items, 31 mutations.

**(1.6) Re-issued as `cp4_golden/1.6-part3`** (minimum `risk/1.6`):

- new ETF SYN33, with a second price source that disagrees on 2025-08-06 and 2026-01-09;
- new proxy benchmark SYN4_BM_ETF_PROXY_PX, and R5 selection seq 3;
- R5-E4, R5-E5 and R5-E6 (Ruling 5.5 (1.6));
- R11-V1 (Ruling 7.7 (1.6));
- mutations M-C32 to M-C35;
- in total 38 assertions, 95 items, 35 mutations.

**(1.7) Re-issued as `cp4_golden/1.7-part3`** (minimum `risk/1.7`):

- ETF SYN34 with four one-sided dividend statements;
- proxy SYN4_BM_ETF_PROXY_ID, and R5 selection seq 4;
- R5-E7 and R5-E8 (Ruling 5.5 (1.7));
- mutations M-C36 and M-C37;
- in total 40 assertions, 98 items, 37 mutations.

**(1.8) Re-issued as `cp4_golden/1.8-part3`** (minimum `risk/1.8`):

- ETF SYN35 (USD) with three CNY-declared dividends;
- proxy SYN4_BM_ETF_PROXY_FX, and R5 selection seq 5;
- R5-E9 (Ruling 5.5 (1.8));
- mutations M-C38 to M-C42;
- in total 41 assertions, 101 items, 42 mutations.

**(1.9) Re-issued as `cp4_golden/1.9-part3`** (minimums `risk/1.9`, `market-data/1.14`):

- precision declarations on every multi-source series;
- benchmarks SYN4_BM_US_TR5 and SYN4_BM_US_TR4, and R4 selection seqs 2 and 3;
- R4-S4, R4-S6 and R5-E10 (a one-sided issuer payment);
- R5-E11 (a FILING-only issuer payment) and R5-E12 (two different issuer payments: a
  `DISAGREEMENT`), for review finding CP4F-15;
- R10-S1's `MAX_AVAILABLE` beta gains its `max_available_start` lineage;
- mutations M-C43 to M-C46;
- in total 46 assertions, 107 items, 46 mutations.

### 11.3: Format points to agree with the engineer

1. The `cycle` construct for price and FX steps (a mechanical expansion; it introduces no number not
   in the block), and `gaps_by_currency` for FX.
2. The `RATE_PUBLICATIONS` calendar kind and the `risk_free` block (Ruling 4.5, 4.3's profile fields).
3. Request encodings (`TRAILING_MONTHS`, `CUSTOM`, `SINCE_INCEPTION`, `MAX_AVAILABLE`) and the
   `effective_window` object.
4. `exact_square` and `sign` for square-root metrics.
5. `details_include`: the fixture asserts exactly the `risk/1.0` detail names present (Ruling 7.4),
   and nothing about CP2 or CP3 lineage names.
6. `FIXTURE_PINS` (item counts and a content hash), as for CP1 and CP3.

### RULING 11.4: Fixture convention policy

`performance` Ruling 11.6 applies unchanged to `cp4_golden`: `convention_sets` are minimum versions;
a convention change that alters an asserted value, state, reason or detail requires a new fixture
version; every `risk` change note names the fixtures it leaves unaffected.

### 11.5 (1.2): Errata in parts 1 and 2 (no reissue)

These errata affect prose only. No asserted value, state, reason or detail changes, so under Ruling
11.4 neither fixture is reissued and their files are left as issued.

- **Part 1, structural assertion S-1:** "the registry digest of
  methodology/registry/RISK_1.0_REGISTRY.json (Ruling 9.2)" reads as "the `registry_id` and
  `registry_digest` of the registry file of the `risk` version the manifest cites (Ruling 9.2 (1.2));
  under `risk/1.2`, `RISK_1.2_REGISTRY.json`".
- **Part 2, structural assertion S2-1:** "the registry digest of
  methodology/registry/RISK_1.0_REGISTRY.json (registry_id risk/1.1)" reads the same way. The 1.1
  registry is `RISK_1.1_REGISTRY.json`. `RISK_1.0_REGISTRY.json` again carries `registry_id`
  `risk/1.0`.

---

## 12. What the engineer needs first, must build, and must not decide

**The tech plan's slots** (`implementation/FEATURE_TECH_PLAN.md` §17, rows P-1 to P-20, read for this
mapping only):

| Slot | Ruled by | Note |
|---|---|---|
| P-1 `boundary_rule` | 2.2, 2.3 | weekdays / Fridays / month-ends; `g_0` = first grid date ≥ `B`, `g_n` = last ≤ `E` |
| P-2 `return_form` | 2.6 | simple |
| P-3 `annualization` | 3.1, 3.2 | 260/52/12; √A for dispersion, ×A for means, nothing geometric |
| P-4 `estimators` | 3.3 | n − 1 around a sample mean; n for the downside deviation |
| P-5 `downside` | 6.3, 2.2 | target `rf_k`; divide by n; zero-return periods kept |
| P-6 `risk_free` | 4.1–4.6 | 13-week, quote at the start, simple calendar-day accrual; `RATE_PUBLICATIONS` calendar; no series → `NO_RISK_FREE_SOURCE` |
| P-7 `excess_return` | 6.5, 6.6, 6.8 | per period, arithmetic mean × A |
| P-8 `regression` | 6.7, 6.8 | **the market model on total returns** (not an excess-return regression); Jensen's alpha with that β |
| P-9 `benchmark_treatment` | 5.1–5.5 | translated unhedged at `u(g)`; total return only; price freshness thresholds; a returns-kind source by exact compounding (5.1) |
| P-10 `relative` | 6.9–6.11 | active return arithmetic; TE and IR as written |
| P-11 `drawdown` | 1.1–1.5 | within the window, from the base; latest peak, earliest trough |
| P-12 `sufficiency` | 2.3, 2.4, 2.5, 7.1, 7.2 | thresholds N1/N3; **refuse**, never clip a requested window (`MAX_AVAILABLE` is its own rule); gaps **suppress** (no drop, no merge); zero-capital only for a period with no capital at any time; no stale-share threshold: any `LIMITED` period makes the metric `LIMITED`, with the count |
| P-13 `comparability` | §8 | a disclosure beside the state, never a state change |
| P-14 `risk_rounding` | 3.4 | 10^−12 half-up; exact integer square root; no enclosure width; tolerance 0 |
| P-15 `registry_appendix` | 9.3 | the JSON file, not fenced blocks in this document: one file, one digest. **(1.2)** one file per version; the id from `registry_id`. **(1.9)** load `RISK_1.9_REGISTRY.json`. **(1.10)** load `RISK_1.10_REGISTRY.json`. **(1.11)** load `RISK_1.11_REGISTRY.json` |
| P-16 `source_disagreement` | 5.7 | precision-bound reconciliation; `SOURCE_CONFLICT` on disagreement. **(1.2)** per calculation day, `source_priority` as data, `SINGLE_SOURCE` used, detail `BENCHMARK_SOURCE_CONFLICT`; ETF proxy corporate actions (5.5 (1.2)) |
| P-17 `details_vocabulary` | 7.4 | `INSUFFICIENT_OBSERVATIONS` (not `TOO_FEW_OBSERVATIONS`) and the rest of the table |
| P-18 `scope` | 0.1 | portfolio **and** account scope |
| P-19 `fixture_format` | 11.3 | |
| P-20 `hg1_reconciliation` | §10 | |

**Four places where the CP4b spine (`src/performance/series.py`, as it stands uncommitted on
2026-10-02, read only for this list and after the fixture was final) must change to meet `risk/1.0`:**

1. `validate_boundaries` requires the boundaries to start at the window's `B` and end at `E`. Under
   Ruling 2.3 they start at `g_0 ≥ B` and end at `g_n ≤ E`, and the stubs are declared. The series'
   window becomes the effective window, with the requested one kept beside it.
2. `ShortWindowPolicy.CLIP_TO_INCEPTION` is not a `risk/1.0` behaviour (Ruling 7.2). A requested window
   is refused; `MAX_AVAILABLE` is a separate request whose base also moves past the last insufficient
   period (Ruling 2.3), which clipping to `I₀` does not do. Whether a default view falls back to it is
   OD-R1.
3. The "later gap policy can merge periods" option is ruled out (Ruling 2.5: no re-gridding).
4. `zero_capital` is flagged when *some* run of a period is `0/0`. `ZERO_CAPITAL_PERIOD` applies only
   when **every** day of the period has no capital (Ruling 2.4). A partially funded period is an
   observation.

**First (CP4b, the spine), in this order:**

1. **The window and grid function** (Rulings 2.2, 2.3): from a request, a frequency and `E`, return
   `B`, `g_0 … g_n`, `n`, the stubs, the rule, and the refusals. Pure; no market data. Test it alone
   against every `effective_window` in part 1.
2. **The periodic series** (Rulings 2.1, 2.4, 2.5): each `r_k` as a `performance/1.12` TWR over its
   period, with its state; RS-1 at runtime; `MAX_AVAILABLE`; `ZERO_CAPITAL_PERIOD`. Part 1's
   `return_series` items test it.
3. **The certified square root and the presentation** (Ruling 3.4).
4. **The risk-free series**: the `RATE_PUBLICATIONS` calendar kind, the source profile fields, the
   per-period rate (Ruling 4.3) and its states (4.4). Part 1's `risk_free_rates` item tests it.
5. **The registry as data** from the file in force (Ruling 9.3; **(1.9)** `RISK_1.9_REGISTRY.json`;
   **(1.10)** `RISK_1.10_REGISTRY.json`; **(1.11)** `RISK_1.11_REGISTRY.json`, with the id read from `registry_id`), its id and digest in manifests, and a test that the engine's
   registry equals the file.
6. **`BenchmarkSeries`** as a market-data kind (Ruling 5.1), with the synthetic adapter and the terms
   gate; and **migration 0015** for the selection log (Ruling 5.6). Values arrive with part 2.
7. **The fixture loader** for part 1 (format points of §11.3) and its `FIXTURE_PINS`.

**Then CP4c:** the single-series metrics (6.2–6.6), RD-1/RD-3 at runtime, and the M-DD mutations.
**CP4d:** 6.7–6.11, §8, after part 2.
**(1.2) With part 3:**

- the account scope (0.1 (1.2), 5.6 (1.2));
- snapshots and `ZERO_CAPITAL_PERIOD` through the series (2.3, 2.4);
- split suppression reaching the series;
- the benchmark leg's two-source reconciliation and ETF proxy (5.5 (1.2), 5.7 (1.2));
- Current mode for the benchmark leg (5.8);
- the default-view composition in the service layer (7.7), not in the metric engine.

**Must not decide:** any grid, anchor day, period count per year, estimator divisor, target, tenor,
quote conversion, accrual rule, threshold, detail name, peak rule, request rule, state combination,
reason priority, rounding mode, quantum or tolerance; whether a benchmark is total return; which
benchmark applies.

**Must never:** use a float; drop, fill or re-grid a period; shorten a requested window silently;
use a constant or another currency's rate; use a price-return benchmark for a relative metric;
compute a ratio from presented values; present `LIMITED` without the count and thresholds; present a
risk statistic of a back-cast portfolio as the portfolio's.

---

## 13. Owner decisions

> **(1.1) OD-R1 and OD-R2 are decided** (PD-0040, 2026-10-02), each as recommended:
>
> - **OD-R1: option (b), the labelled fallback.** When the default 3Y request is refused, the
>   default view sends `MAX_AVAILABLE` and shows its actual window, count and state. The 3Y refusal
>   stays in the evidence. This is a request rule in the service layer; Ruling 7.2 is unchanged (no
>   result is labelled with a window it did not use).
> - **OD-R2: sovereign bills, none meanwhile.** USD: the Treasury's 13-week coupon equivalent, after
>   attestation and calendar registration (owner actions). HKD and CNY: HKMA Exchange Fund Bills
>   91-day and ChinaBond 3M are sought. Until then, HKD- and CNY-reporting portfolios get
>   `NO_RISK_FREE_SOURCE` for Sharpe, Sortino, downside deviation and alpha (Ruling 4.6). HIBOR and
>   SHIBOR are not adopted.
>
> The text below is the 1.0 record.

### OD-R1 (open): which request a default view sends when the 3-year request is refused

PRD §14's default is 3Y weekly. For a portfolio younger than three years (or with a gap), the
`TRAILING_MONTHS 36` request is refused (Ruling 7.2).

- **(a) Strict:** the default view shows the refusal ("3Y — not available: the portfolio's history
  starts …"), and the user may choose "maximum available".
- **(b) Fallback, labelled:** the default view sends `MAX_AVAILABLE` when the 3Y request is refused,
  and shows the result with its actual window in the same visual unit ("since 2025-03-07, 41 weekly
  observations — limited"). The 3Y refusal stays visible in the evidence.
- **(c) Both side by side.**

**Recommendation: (b).** The method is the same either way (both requests exist; neither is ever
mislabelled). (b) gives a new user a figure with its true window and its `LIMITED` state, rather
than an empty default that teaches them the analytics do not apply to them. It needs the label to
carry the actual window, which Ruling 2.3 already requires. **Until decided:** (a), which fails
closed.

### OD-R2 (open): risk-free sources

- **USD:** attest the US Treasury "Daily Treasury Bill Rates" for the 13-week coupon equivalent
  (Ruling 4.6), and register its publication calendar (Ruling 4.5). PD-0039 D2 already chose a public
  series; this is the attestation it calls for.
- **HKD and CNY:** options:
  - **(a)** look for sovereign 3-month series (HKMA EF Bills 91-day; ChinaBond 3M) and attest them;
  - **(b)** accept interbank 3-month rates (HIBOR, SHIBOR) as a stated, slightly-credit-bearing
    substitute;
  - **(c)** none for now: CNY- and HKD-reporting portfolios show no Sharpe, Sortino, downside
    deviation or alpha.

  **Recommendation: (a), with (c) until a source is attested.** Mainland and Hong Kong investors
  reporting in CNY or HKD are the product's core users, so (c) leaves four of the CP4 metrics
  permanently unavailable for them at HG3. (b) is acceptable if (a) fails, provided the registry
  states the credit premium.

### Already owed, not new (PD-0039 D1)

A decision on real benchmark data before HG3. Note for that decision: whatever is chosen must
provide a **total-return** series (Ruling 5.4). A price-only index source cannot serve any
benchmark-relative metric; an ETF proxy can, through Ruling 5.5, if corroborated dividends exist for
it.

---

## 14. External facts from memory (to be confirmed by the human)

None of these is asserted as verified. I have no network access here.

1. **US Treasury "Daily Treasury Bill Rates":** published each business day for 4-, 6-, 8-, 13-, 17-,
   26- and 52-week bills, with a bank-discount column and a coupon-equivalent column; the coupon
   equivalent of a bill of 182 days or less is a simple-interest yield, believed on a 365-day basis
   (366 in some leap-year cases); values are closing bid quotations on the most recently auctioned
   bills. **Confirm the basis, the date semantics and the holiday schedule at attestation.**
2. **HKD and CNY candidates:** HKMA Exchange Fund Bills (91-day) yields; HKAB HIBOR fixings;
   ChinaBond government-bond yield curve (3-month point); SHIBOR (shibor.org). Their terms and
   formats are unknown to me.
3. **Sharpe (1994)**, "The Sharpe Ratio", *Journal of Portfolio Management* 21(1): ex-post ratio of
   mean differential return to its standard deviation; the information ratio as its generalisation.
   **Jensen (1968)**, "The Performance of Mutual Funds in the Period 1945–1964", *Journal of Finance*:
   the alpha. **Sharpe (1963)**: the single-index (market) model.
4. **Sortino and Price (1994)**, "Performance Measurement in a Downside Risk Framework", *Journal of
   Investing*: downside deviation below a minimum acceptable return, root-mean-square over all
   periods.
5. **Lo (2002)**, "The Statistics of Sharpe Ratios", *Financial Analysts Journal*: √T scaling assumes
   serially uncorrelated returns; the standard error of an estimated Sharpe ratio is about
   `√((1 + SR²/2)/n)` per period under i.i.d. normal returns.
6. **Bacon**, *Practical Portfolio Performance Measurement and Attribution*: maximum drawdown over a
   period from its own cumulative path; arithmetic and geometric excess returns.
7. **GIPS 2020:** monthly valuation and calendar-month returns for composites; no annualization of
   periods under one year (as `performance` §18 item 7).
8. **The Epps effect** (Epps 1979): sampled covariances of asynchronously traded assets shrink toward
   zero as the sampling interval shortens.

None of the rulings depends on a citation for its correctness: each is argued in place. The citations
say that the chosen method is the standard one, which a reviewer can check.

---

## 15. Open issues

- **OI-R1.** Part 3 of `cp4_golden` (§11.1). (1.1: part 2 is authored. **1.2: part 3 is authored;
  closed.**)
- **OI-R2.** OD-R1 and OD-R2 (§13). (1.1: decided, PD-0040.)
- **OI-R3.** `ReferencePoint` has no `RISK_FREE_RATE` member (Ruling 9.1). The engineer adds one or
  records the rate separately; if a vocabulary change needs the owner, the main session routes it.
- **OI-R4.** The publication calendar for the Treasury series (Ruling 4.5): drafted by the session,
  registered by the owner, as PD-0034.
- **OI-R5.** `market-data/1.11` is unchanged by this document. The `RATE_PUBLICATIONS` calendar kind
  and the `BenchmarkSeries` and risk-free contracts are defined here; a later `market-data` issue may
  absorb them without changing their content.
- **OI-R6.** HG2 conditions 3 and 4 still bound what a real CP4 demonstration can show: no CN/HK
  prices, and no registered HK/CN calendars, so no real CN/HK series. A real 3-year weekly series does
  not exist for any market today (`reviews/CP4_PLAN.md` §3), so every real 3Y statistic is
  `INSUFFICIENT_DATA` until history accrues or a source is admitted. That is P5 working, and HG3
  should be told so.
- **OI-R7.** The underwater (current-drawdown) metric of Ruling 1.1's last paragraph, if the product
  wants it: product scope, then a registry entry.
- **OI-R8 (1.2).** Ruling 7.7's trigger set includes a gap (`PERIOD_INSUFFICIENT`,
  `ZERO_CAPITAL_PERIOD`) as well as youth. That is my reading of PD-0040 with OD-R1 as put. The main
  session may confirm it with the owner; the narrower reading changes no part-3 item.
- **OI-R9 (1.2).** Not covered by any fixture yet:
  - `M_t` retrieval filtering in Current mode;
  - the risk-free quote at `t`;
  - an ETF proxy split, a proxy ex-date on a non-print day, and a resolution record;
  - two sources agreeing within the bound but unequal;
  - a fallback default view for a benchmark-relative metric.

  These are a later part, if wanted (`CP4_GOLDEN_PART3_DERIVATION.md` §16).

  **Note (2026-10-03; fixture coverage only, no ruling or id change).**
  - Two of these paths are now pinned by `cp4_golden/1.0-part4`:
    - the risk-free quote at `t` (Ruling 5.8 items 4, 5 and 7): R41-C1, R41-C2 and R41-C3;
    - the fallback default view for a benchmark-relative metric (Ruling 7.7 (1.6)): R41-V1 falls
      back, R42-V0 does not.
  - R41-C2 is also the first item in which `M_t` filtering changes a result: a risk-free file
    published but not yet retrieved.
  - **Stated limitation of this coverage.** The "not yet due" case (R41-C3) can be exercised only on
    a synthetic publication time: 20:00 New York, after 00:00 UTC of the next day.
    - With a same-day publication before that hour, the quote of a period's start is always
      published by `t`. That covers parts 1 to 3's calendars and the Treasury bill rates as
      described in Ruling 4.6.
    - On those calendars, Ruling 5.8 items 4 and 5 never decide a risk-free result. Only item 7 (a
      late file) can.
    - See `CP4_GOLDEN_PART4_DERIVATION.md` §1.1.
- **OI-R11 (1.3).** RETURNS-form benchmark ingestion is unbuilt by choice (Ruling 5.1 (1.3)
  interim). When a RETURNS-form source is proposed for admission, a fixture item comes first: a chain,
  a break and a window across it.
- **OI-R10 (1.2).** `source_priority` for a benchmark's sources is a new source-registry field
  (Ruling 5.7 (1.2)). `market-data` holds the price order as data in its Appendix A; a later
  `market-data` issue may absorb this field, as OI-R5 says for the other contracts.

### 15.1 (1.9): Latent paths, to be ruled at first admission

CP4 methodology is frozen for CP4 acceptance at `risk/1.9`, `market-data/1.14` and
`cp4_golden/1.9-part3` (main-session ruling). No admitted source today exercises the paths below:
no real ETF proxy, and no real second source for a benchmark or a price. Each item is ruled, with a
fixture item first, **when the first real proxy or second source is put up for admission**, and not
as a new version before then. Until it is ruled, the current text governs, and where the text is
silent the engine refuses, as P5 requires.

Exceptions to the freeze: a defect on a path that is not latent, a defect in a golden value, or a
contradiction in the text.

- **OI-L1. ETF proxy split.** The method is stated: the chain's `f_t` (Ruling 5.5 item 2), its
  identity across sources (Ruling 5.5 (1.7)), and a disputed split under item 4b. No fixture item
  exercises any of it (OI-R9). At admission, a fixture item comes first (a corroborated split, then
  a disputed one), and any defect it exposes is ruled then.
- **OI-L2. Proxy ex-date on a non-print day.** The method is stated: Ruling 5.5 item 2 applies the
  dividend at the next print. No fixture item covers it (OI-R9). One point is open: for a dividend in
  another currency, Ruling 5.5 (1.8) item 3 converts at the ex-date's fixing, not the fixing of the
  print that applies it. My reading is that the ex-date governs, since the ex-date is the date the
  value leaves the price. It is confirmed with a fixture item at admission.
- **OI-L3. Resolution records.** The form and evidence of a record that resolves a disputed dividend,
  print or benchmark level (`RESOLVED_BY_EVIDENCE`), and what lifts `SOURCE_CONFLICT`. No fixture
  item covers it (OI-R9).
- **OI-L4. Agreement within the bound but unequal.** Ruling 5.7 (1.2) uses the primary's level.
  It is not fixture-pinned (OI-R9). With declared precision (1.9) it arises only for a coarser source
  (for example 990.32 against 990.3).
- **OI-L5. Dividend identity for frequent distributors.** Ruling 5.5 (1.7) item 3 links unpaired
  statements up to 20 sessions apart. Its known limitation is a needless `DISAGREEMENT` for a payer
  every 20 sessions or less when one side misses a payment: fail-closed, never a double count. The
  open question is whether the window should depend on the fund's declared distribution frequency.
  That depends on the first real proxy's payment pattern.
- **OI-L6. Paid fields beyond `paid_amount`.** These are stated in `market-data` Ruling 7.1 (1.14)
  but not fixture-pinned:
  - a stated `issuer_fx_rate` alone (paid amount = amount × rate, exact);
  - both a paid amount and a rate stated, with their mismatch flagged;
  - one side stating the amount and the other only the rate. Is that a comparison of the derived
    amount, or two different fields?
  The validation that `paid_currency` differs from the declared currency is not enforced (review
  §43). That is engineering against existing text, not an open method question.
- **OI-L7. A payment in a third currency.** Ruling 5.5 (1.8) item 2 uses the issuer's payment only
  when it is stated in the ETF's price currency `p`. Otherwise the declared amount is converted. The
  open question is whether a payment stated in a third currency (CNY declared, HKD paid, a USD-traded
  ETF) should be converted from the paid amount instead.
- **OI-L8. Precision declarations over time and for proxy prices.** `official_decimals` and
  `precision_decimals` are undated declarations. The open questions are a provider that changes its
  published precision, and the content-check refusal (Ruling 5.7 (1.9) item 3) on a real file. No
  fixture item covers the refusal.
- **OI-L9. A vintage-unstable second source.** `market-data` Ruling 0.1 (1.12) admits segmented
  series only for vintage-stable kinds. The open question is an adjusted-price or revised-level source
  offered as a second source.
- **OI-L10. RETURNS-form benchmark sources** (OI-R11) and **`source_priority` as a source-registry
  field** (OI-R10), as already recorded.

Not latent, and so outside this list: the risk-free quote at `t` in Current mode, and the fallback
default view of a benchmark-relative metric (both OI-R9). These run on admitted sources today, and
no fixture item pins them. They are open fixture coverage, not deferred method.

**Note (2026-10-03; fixture coverage only, no ruling or id change).** Both are now pinned by
`cp4_golden/1.0-part4`:
- R41-C1, R41-C2, R41-C3: the quote published and retrieved, due but late, and not yet due;
- R41-V1 and R42-V0: the history fallback, and the benchmark-coverage refusal that does not fall
  back.

The "not yet due" case is exercised only on a synthetic publication time. On every registered or
proposed risk-free calendar it cannot arise (OI-R9's note).
