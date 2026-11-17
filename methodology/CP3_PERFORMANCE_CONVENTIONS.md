# CP3 performance conventions: valuation, rounding, lots, flows, TWR, MWR, annualization, income, attribution, reconciliation

**Author:** `quant-analyst` subagent, dispatched by the main session (PM), 2026-10-01.
**Convention set ID:** `performance/1.12` (supersedes `performance/1.11` and earlier; 1.11 and
1.12 issued 2026-10-02).

A Computation Manifest (Tech Plan §6.2) that computes any value defined here cites
`performance/1.12` together with **`ledger-replay/1.5`** (the `FIFO/1` mode of the lot fold),
**`market-data/1.11`**, the lot-relief method in force (§3.2: `FIFO/1`) and the minor-unit table
**`minor-units/1.1`** (Ruling 2.3). A later change to any RULING creates a new ID, including a
clarification.

(Header as issued for 1.11: "cites `performance/1.11` together with `ledger-replay/1.5`,
`market-data/1.10`, `FIFO/1` and `minor-units/1.1`". `market-data/1.11` was issued after it, the
same day, and 1.12 names it.)

**Change note, 1.11 → 1.12.** This answers the CP4 part A question on `market11.UNBUILT`'s
item "not built: Current mode (instant t) … historical mode only" (`market-data` Rulings 1.6,
2.2 item 6 and 5.2).

- **Ruling 1.7 (1.12): the market-data instant clauses are met by the composition.** That
  composition is three steps: choose `D_c(t)`, restrict `M` to `M_t`, then apply the
  historical-mode rules at `D_c(t)`. The market-data policies do **not** need to take `t`. The
  proof is written in Ruling 1.7 (1.12) item 1. The instant clauses are availability conditions
  on single inputs, and the composition can break one in exactly one way: when `D_c(t)` is chosen
  without testing an input the bundle reads.
- **Ruling 1.7 (1.12) item 2 closes that gap. `D_c(t)` now also tests the events dated `D`.**
  - **The gap.** Up to 1.11, `D_c(t)` tested only the exchanges of positions held at the **end**
    of `D`, and the ECB only when an amount other than `R` is held at the end of `D` or as a
    receivable.
  - **What it missed.** Some events dated `D` need `D`'s close or fixing, while nothing they touch
    remains held: an in-kind transfer out of a listing's last units, or a foreign-currency
    withdrawal, income, cost or conversion that leaves nothing in that currency. For these,
    1.11 could choose `D_c = D` before `D`'s close or fixing exists.
  - **The effect.** The event was then translated or valued with `D − 1`'s input, labelled
    `STALE`. An instant-aware market-data policy would have labelled the same wrong-date input
    `CURRENT`, which is worse.
  - Example 1.7-C shows the case.
  - **The fix.** The exchange set and the ECB test now include every live ledger event dated `D`.
- **Folded into 1.12 before implementation, at the PM's instruction** (review §33). No manifest
  cites 1.12 yet, so no result was computed under the shorter text:
  - **Ruling 2.2 (1.12): the exponent of a presented value** (CP4-3). Derived money has exactly
    the minor unit's decimals. A money fact is padded to the minor unit and **never rounded**: it
    has `max(minor_unit, its own shortest decimals)` decimals, so `2248` → `2248.00` and `0.125`
    USD stays `0.125`. The recorded scale is not used. A fact in a currency outside the table is
    shown unpadded, with `CURRENCY_NO_MINOR_UNIT`. The `NATIVE` view of a recorded amount is a
    fact, and every `REPORTING` value is derived.
  - **Ruling 1.7 (1.12) item 4: `M_t` scopes the files of `M` only.** The source registry and the
    identity registry are read at computation time and pinned by digest. The new manifest field
    is `source_registry_digest`.
  - **Ruling 1.7 (1.12) item 5: a Current-mode refusal records `t`, `M` and `M_t`** (CP4-2).
- **No expected value changes.**
  - No fixture asserts a Current-mode result (`current_mode_as_of` is planned in §11.5, and no
    part asserts it), and no example computes one.
  - The exponent rule changes no value. Fixtures compare values numerically.
  - No fixture asserts a native money fact with more decimals than its minor unit, or one in a
    currency outside the table.
  - I scanned every fixture item whose presented value differs from its exact value. The only
    one in a fact-like row is P6-V2's USD cash in the `REPORTING` view of an HKD portfolio, which
    is derived, as before.
- **Fixtures (Ruling 11.6 item 3).** This change leaves **all** of these unaffected:
  - `cp1_golden/1.1`;
  - `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2`, `cp3_golden/1.2-part3` and
    `cp3_golden/1.2-part4`.

  They are all historical mode. Their native facts (for example P1's `"20000"` HKD) are the same
  values once padded. No fixture version is issued. When a fixture is next re-issued for another
  reason, its native money texts may be written padded, as a wording-only change (Ruling 11.6
  item 4).
- **The open item.** `market-data` needs **no** text change and **no** new id: no market-data
  ruling changes, and 1.12 shows that its clauses hold under the composition. The item lives in
  `src/marketdata/market11.py` (`UNBUILT`), so it is the engineer's to change. The ruling on it is
  in §16 (1.12).

(Header as issued for 1.4: "cites `performance/1.4` together with `ledger-replay/1.3` and
`market-data/1.10`". As issued for 1.5: "cites `performance/1.5` together with `ledger-replay/1.4`".
As issued for 1.6: "cites `performance/1.6` together with `ledger-replay/1.5`". As issued for 1.7,
1.8, 1.9 and 1.10: "cites `performance/1.7`", "`performance/1.8`", "`performance/1.9`" or
"`performance/1.10`" "together with `ledger-replay/1.5`", with the minor-unit table cited as "the
minor-unit table version", which was `minor-units/1`.)

**Change note, 1.10 → 1.11.** This applies PD-0037 (the owner's confirmation of the minor-unit
table) and HG2 condition 2 (PD-0038). It changes the **status** of table rows, and no value.

- **Ruling 2.3 (1.11): the ten ISO rows are CONFIRMED.**
  - USD, HKD, CNY, EUR, GBP, CHF, SGD, AUD and CAD (2 minor units) and JPY (0) change status from
    `MEMORY` to **`CONFIRMED`**: by the owner, 2026-10-02, against SIX's ISO 4217 List One
    (`list-one.xml`) published 2026-09-17, per PD-0037. PD-0037 records that all ten
    `CcyMnrUnts` values match.
  - **No minor unit changes.** Every (currency, decimals) pair is the same as in `minor-units/1`.
  - **CNH stays `DECLARED`.** It is not an ISO 4217 code, so List One cannot confirm it, and
    PD-0037 does not cover it. A `DECLARED` row is a Quant convention, not a fact awaiting
    confirmation, so it is not an open item (Ruling 2.3, 1.11).
- **The table id becomes `minor-units/1.1`.** The rule (Ruling 2.3, 1.11):
  - one id, one text (P9; the precedent is the 1.3 → 1.4 note below). A row's status is part of
    the table's recorded text, and a manifest citing `minor-units/1` must keep resolving to the
    table as it then stood, with its rows from memory;
  - **minor** version (`1` → `1.1`): only status or provenance changes, and every
    (currency, decimals) pair is identical, so the two are **value-equivalent**;
  - **major** version (`minor-units/2`): a currency is added or removed, or a minor unit changes.
    That can change a computed value or a state (a currency moving out of
    `CURRENCY_NO_MINOR_UNIT`), and it needs its own confirmation (PD-0037).
  - `minor-units/1` is read as `minor-units/1.0`.
- **§18 item 1 is closed** (confirmed by PD-0037). The item number stays, so the references to
  §18 items 4 and 5 still hold.
- **§16 (1.11): the engine's HG2 open item closes.** It names no unbuilt rule. The pack is built,
  the gate is decided (PD-0038), and I-7 runs where Ruling 11.1 (1.2) puts it.
- **No computed value changes.** No value, state, reason, detail, quantum, rounding mode or
  apportionment changes, in any example or fixture. The only output that changes is
  conformance metadata: the manifest's `conformant` flag and its open-items list, plus the cited
  ids.
- **Fixtures (Ruling 11.6 item 3).** This change leaves **all** of these unaffected:
  - `cp1_golden/1.1`;
  - `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2`, `cp3_golden/1.2-part3` and
    `cp3_golden/1.2-part4`.

  **Why:**
  - none of them asserts a minor-unit table id, a row status, `is_conformant` or an open item;
  - their `convention_sets` name no minor-unit table;
  - the presented money values they assert are quantized with the same minor units, so every
    one is unchanged;
  - their `performance` minimums (1.6, or 1.9 for part 4) are met by 1.11 under Ruling 11.6
    item 1.

  No fixture version is issued, no fixture is relabelled, and no independent calculator under
  `methodology/fixtures/cp3_golden/derivation/` changes. None of them reads a row status.
- **Engineer tests outside `methodology/`** that pin `minor-units/1`, `performance/1.10`, a
  `performance/1.10#…` slot id or `is_conformant` False need updating. Those tests are not
  fixtures, and the expected values do not change (§16, 1.11).

**Change note, 1.9 → 1.10.** This answers the CP3f build's question on breakdown grouping keys,
with a re-derivation.

- **Ruling 9.6 (1.10): one key per contribution per grouping.**
  - **A receivable's FX goes to the listing (and market) its `DIVIDEND` names**, not `none`.
    Accrued income is part of the security's return until it is paid (Ruling 8.1). The 1.9 example
    putting it in `none` was wrong, and is withdrawn.
  - **Income, fee, tax and financing events** go to:
    - the listing they name, else `none` (Ruling 8.4);
    - their **event currency** in the currency grouping;
    - a new component kind, **`event`** (by `event_id`).
  - **A conversion result** is `none` by listing, market and currency, and `event` by component.
  - **`market`** is the listing's MIC.
  - The order is extended to cover the new keys.
- **On the CP3f engineer's three readings:**
  - **(a) is changed:** receivables go to the dividend's listing.
  - **(b) is changed** for the currency and component groupings. Its listing rule was right.
  - **(c) follows (a) and (b).**
  - **The engine must change.** The CP3f build followed the 1.9 example.
- **Ruling 1.1b is unchanged.** The CP3f wording of `last_print_date` matches it.
- **Fixtures (Ruling 11.6 item 3).** This change leaves **all** of these unaffected:
  - `cp1_golden/1.1`;
  - `cp3_golden/1.4-part1`, `1.2-part2` and `1.2-part3`;
  - `cp3_golden/1.2-part4`. Its breakdowns are P3 `attr.price` by listing (positions and trade
    results only), and P6 and P21 `attr.fx` by component (positions, cash and receivables, whose keys
    are unchanged in that grouping). None of them groups a receivable by listing or market, or groups
    an event line.

  No fixture version is issued.

**Change note, 1.8 → 1.9.** This version answers three questions from the CP3e build (attribution).
Each answer was re-derived from the rulings; neither side was simply accepted.

- **New Ruling 1.1b: the last print date of a withheld holding (CP3e finding P22-V1).**
  - **Re-derivation.** The fixture field `price_date_used` is defined (part 1 `format`) as "the
    session whose close was used". When `market-data` 5.2 withholds a holding's value (5 or more
    missed sessions), no close is used. So the engine is right not to report one, and
    `cp3_golden/1.1-part4` was wrong to put 2025-03-07 in that field.
  - **The date itself is still a fact the audit needs** (P9: "last priced 2025-03-07"). It is also
    an input the missed-session count already depends on. Ruling 1.1b therefore adds a separate
    lineage field, `last_print_date`, which is reported whenever a print exists at or before `D`,
    including when the value is withheld. `price_date_used` is reported only when a close values the
    holding.
  - **Engine impact:** additive (one lineage field).
- **Ruling 9.5 (1.9): the scope of the base and value conditions.**
  - `NON_POSITIVE_BASE`, `NEGATIVE_VALUE` and `TOTAL_LOSS` suppress only the **percentage**
    attribution (Cariño, `attr.*` `C_k`).
  - The **money** lines need no base: they sum to `g_D` exactly, and `G` stays `AVAILABLE` in those
    cases (part 1 P4-R1). Their state comes only from missing or limited inputs.
  - This **confirms** the CP3e engineer's reading. The 1.0 text could be read either way.
- **Ruling 9.6 (1.9): a published breakdown is a decomposition object.**
  - **Re-derivation.** Ruling 2.4 items 3 and 4 require a total with its parts to be shown with
    apportioned values that sum to the displayed total. A breakdown is that object.
  - **Its total is the line's apportioned display value** in the attribution of the same window,
    so a drill-down sums to the bar it opens.
  - The rule also fixes:
    - the part order and tie order;
    - that a part exactly 0 is omitted (its component stays in lineage);
    - that components without the grouping key form one part keyed `none`, so each grouping sums to
      the line.
  - This **corrects** `cp3_golden/1.1-part4`, whose breakdown parts were presented independently
    (P6's parts summed to 6.76 against a 6.75 line). The CP3e engine follows the fixture, so it
    changes too.
- **Fixtures (Ruling 11.6 item 3).**
  - **Unaffected:** `cp1_golden/1.1`, `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2` and
    `cp3_golden/1.2-part3`. None asserts `price_date_used` on a withheld holding, a breakdown, or a
    percentage attribution with a non-positive base.
  - **Affected:** `cp3_golden/1.1-part4`, at P22-V1 and its three breakdowns. It is re-issued as
    `cp3_golden/1.2-part4`. No money line, Cariño component, total, state or reason changes.

**Change note, 1.7 → 1.8.** The PM ruled on OI-P11 to stop relabel churn. The ruling is recorded as
**Ruling 11.6, the fixture convention policy**:

- a fixture's `convention_sets` are the **minimum** versions it was derived and ratified under;
- a checker accepts the same family at that version or later;
- a convention change that alters any asserted value, state, reason or detail **requires** a new
  fixture version;
- every convention change note states which fixtures it leaves unaffected.

Nothing else changed.

- **Fixtures this change leaves unaffected (Ruling 11.6 item 3):** `cp1_golden/1.1`,
  `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2`, `cp3_golden/1.2-part3` and
  `cp3_golden/1.1-part4`. 1.8 changes no computation.
- **Attestation for 1.7, under item 3.** `performance/1.7` added only line identifiers and a note,
  and it changed no value, state, reason or detail. It leaves unaffected `cp1_golden/1.1`,
  `cp3_golden/1.4-part1`, `cp3_golden/1.2-part2` and `cp3_golden/1.2-part3`. `cp3_golden/1.0-part4`
  is unaffected in values, and was re-issued as `1.1-part4` only to carry the identifiers. The 1.7
  change note below said this in substance. This line makes the attestation explicit, and leaves the
  1.7 text as issued.
- **OI-P11 is closed** by Ruling 11.6. No relabel of parts 1–3 is needed: they cite `performance/1.6`
  as their minimum, and remain valid under 1.7 and 1.8.

**Change note, 1.6 → 1.7.** The PM ruled that the attribution lines get fixed identifiers. A
position alone is too fragile for the API, manifests, the HG2 evidence pack and the UI.

- **Ruling 9.2 (1.7 addition):** the eight lines have fixed identifiers, in the registry order:
  - `attr.price`
  - `attr.fx`
  - `attr.price_fx_interaction`
  - `attr.income`
  - `attr.fees`
  - `attr.taxes`
  - `attr.financing`
  - `attr.conversion`

  The registry order and every line's content are unchanged.
- **The since-acquisition lines (Ruling 9.7)** have been fixed since 1.5: `LOCAL_AT_ACQUISITION_FX`,
  `FX_ON_COST` and `INTERACTION`. They are restated in Ruling 9.2 (1.7), not renamed, because
  `cp3_golden` part 3 asserts them.
- **§11.5:** the note that part 4 is authored.
- **Nothing else changed:** no other ruling, and no expected value in any example or in `cp3_golden`
  parts 1–4.
  - Part 4 becomes `cp3_golden/1.1-part4`, which identifies lines by these ids.
  - Parts 1–3 assert no attribution line, but their `convention_sets` still cite `performance/1.6`
    (structural assertions S-1, S2-1, S3-1). See OI-P11.

**Change note, 1.5 → 1.6.** Two owner decisions in PD-0036.

- **PF-1 decided (PD-0036 §1).** New **Ruling 3.7a**: a lot of kind `RECORDED`, one carrying
  `acquired_on` (`ledger-replay/1.5` Ruling 0.6), takes its reporting-currency unit cost at the
  `acquired_on` fixing. That resolves `ACQUISITION_DATE_UNKNOWN` for such lots.
  - A date before the market data's FX coverage gives `MISSING_FX_HISTORY`.
  - A basis already in `R` needs no rate.
  - Ruling 9.7 (1.6) applies the same rate to the since-acquisition view.
  - Returns, flows and the inception base are untouched.
- **OD-P5 decided (PD-0036 §2): no new reason codes.** Option (a), in force since 1.1, is now the
  owner's decision. §15 is updated to say so. Nothing changes in behaviour.
- **No expected value changed.** No event in `cp3_golden` parts 1–3 up to `1.0-part3` carries
  `acquired_on`. Part 3 becomes `cp3_golden/1.1-part3`: its convention sets are relabelled, and
  portfolio P20 is added for Ruling 3.7a. Every earlier part-3 value is unchanged.

**Change note, 1.4 → 1.5.** Written with `ledger-replay/1.4` (the `FIFO/1` mode of the one lot
fold) and `cp3_golden` part 3. Every 1.5 text is new and marked "(1.5)". **No 1.4 ruling text is
changed.**

- **New Ruling 3.3a:** `FIFO/1` is defined normatively by `ledger-replay/1.4` Ruling 0.5. Relief is
  per position; "portfolio-wide" in §3.2 means the method. Lots carry identity, carry history and a
  date kind (`TRADE`/`ENTRY`), which Ruling 3.7 reads.
- **New Ruling 1.1a:** under `FIFO/1`, a carried split taint is decided by the end-of-day lot book.
  This replaces the conservative rule, as `market-data` Ruling 6.4c rule 4 provides.
- **Ruling 3.8, states completed (1.5):**
  - a sale that relieves units suppressed on its date has its realized gain `INSUFFICIENT_DATA` +
    `SOURCE_CONFLICT`;
  - a relief record that replay withholds passes its cause on;
  - the mixed-currency test ignores unknown portions;
  - the detail names are fixed.
- **New Ruling 3.9a:** the remaining-basis metric, its views and states, including suppression.
- **Ruling 3.10, aggregates completed (1.5):** which excluded sales give `LIMITED` and which give
  `INSUFFICIENT_DATA`, and what happens when an excluded weight cannot be measured.
- **Ruling 9.7 (1.5):** the line names and their order, and the states.
- **§11.5 erratum (1.5):** the plan's P1 value "E7: 2,250 − 50 × 150 = 750" is wrong. E7 sells 50
  units after the 4:1 split, at a unit cost of 37.50. The realized gain is 2,250 − 1,875 =
  **375**. X12 (500) and the X13 carried lot (4,125) stand.

**Expected values.** No value in any example, nor in `cp3_golden` parts 1 and 2, changed. Those
parts exercise no lot relief and no gain.

**Engine behaviour.**

- The carried taint now ends by lot identity. This never suppresses more than the conservative
  rule, and it suppresses less when a receiver relieves the tainted lot without reaching 0.
- The gain and remaining-basis rules are for CP3d, which is not yet built.
- Parts 1 and 2 cite `performance/1.4` and `ledger-replay/1.3` in `convention_sets`. When the engine
  cites 1.5 and `ledger-replay/1.4`, they need a wording-only relabel (structural assertion S-1).
  That is for the PM to schedule; part 3 does not change them.

**Change note, 1.3 → 1.4.** These clarifications were first written in place under 1.3, which was
a process error: two texts must never share one ID (P9). They are re-issued here under their own
ID. The texts are those marked "(1.4 clarification)" below.

- **Ruling 1.7:** "every CP2 step runs over `M_t`" includes F8 split detection and its
  suppressions.
- **Ruling 8.6:**
  - amounts carry their line's sign (fees, taxes and financing negative);
  - a window with no such event has amount 0, `AVAILABLE`;
  - the conversion-result amount is Ruling 8.5 summed over the window (= attribution line 8);
  - an untranslatable income or cost event makes only its own line's amount
    `INSUFFICIENT_DATA`.
- **§11 (reproduction):** a reproduction without an expected digest is `RESULT_NOT_COMPARED`, never
  `REPRODUCED`. HG2 evidence cites the manifest ID and the expected digest for each reproduced
  result.

**No expected value changed**, in any example or in `cp3_golden` parts 1 and 2. **No built engine
behaviour changes:**

- `RESULT_NOT_COMPARED` is already the engine's outcome;
- Current mode is not yet wired to detection;
- the Ruling 8.6 statements define the income and cost metrics of CP3c, which are not yet built.
  `cp3_golden` part 2 asserts them.

**Change note, 1.2 → 1.3.** This version answers the CP3 midpoint review (`reviews/TECH_REVIEW.md`
§28), with the rulings in `market-data/1.9`. No expected value changed, and `cp3_golden` part 1 has
no split, transfer-after-split or synthetic corporate-action case.

- **Ruling 1.1:** a position's state includes a suppression carried with tainted lots
  (`market-data` Ruling 6.4c; review CP3-2).
- **Ruling 4.3:** an in-kind flow of suppressed units is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`,
  and so are the TWR and `G` over its window (review CP3-1).
- **Synthetic corporate-action evidence** (`market-data` Ruling 4.8 item 4; review CP3-3) drives
  detection and suppression, but never an append.
- **For `ledger-replay/1.4` (the FIFO lot fold, still to be written):** the fold must expose, per
  lot, its carry history (the source position and in-leg date of each internal carry) so that
  Ruling 6.4c's taint can be decided by lot identity. Until then, 6.4c's conservative rule
  applies: the receiver stays suppressed until it ends a day at 0.

**Change note, 1.1 → 1.2.** This version answers the CP3b engineer's ten questions (tech plan
§16.15). **No expected value in any example or in `cp3_golden` part 1 changed.** The engine's CP3b
behaviour already matches every answer except Q1 (key the freshness vector by calendar), Q2 (the
`MISSING_BENCHMARK` position) and Q6 (restricting `M` in Current mode).

| Q | Ruling | Answer |
|---|---|---|
| 1 | 1.6 | The freshness vector is keyed by **calendar ID**, with the MICs it governs listed in the entry |
| 2 | 1.5 | `MISSING_BENCHMARK` is **7th**, after `UNSUPPORTED_ASSET` and before `MISSING_COST_BASIS` |
| 3 | 1.4 item 2 | Gross value 0: the stale share is **not stated**, and lineage carries `STALE_SHARE_UNDEFINED`. The total stays `LIMITED` + `STALE_DATA`. |
| 4 | 5.2 | An empty run is a factor of 1 by definition. It records **no** factor and **no** `ZERO_CAPITAL_RUN`. Confirmed. |
| 5 | 11.1 | I-2 and I-3 are **not** required in every product call. They are required in tests, the fixture, the HG2 evidence pack, and every call that computes the attribution (which values every day anyway). |
| 6 | 1.7 | Current mode computes over **`M_t`**: the files of `M` retrieved at or before `t`. Every CP2 step runs over `M_t`. |
| 7 | 7.2 | `NEGATIVE_GROWTH_FACTOR` is **kept** as a defensive refusal. Reaching it is an engine fault: `CALCULATION_ERROR`. |
| 8 | 1.7 | With nothing held but cash in `R`, `D_c(t)` = `UTC-date(t)`. Confirmed. |
| 9 | 1.4a | Any account before its snapshot means the partial metric is not emitted, in the mixed case too. Confirmed. |
| 10 | 2.1 | Methods (a) and (b) are **equally** conformant. **(b), `Decimal` at `prec` 50 plus the tie rule, is the product path for annualization.** "Preferred" is withdrawn. |

`cp3_golden` part 1 becomes `cp3_golden/1.1-part1`: structural assertion S-5 is reworded to the
portfolio level, and S-4's evidence is stated. No expected value changed; the content hash must be
re-pinned.

**Change note, 1.0 → 1.1.** This version records the owner's decisions (PD-0035) and answers the
CP3a engineer's open points (tech plan §16.12–§16.14). No expected value in any 1.0 example changed.

- **OD-P1 decided: FIFO** (Ruling 3.3) is the method, `FIFO/1`. Average cost (Ruling 3.4) stays
  specified but is not used. Every realized and unrealized figure carries the broker-difference
  caveat (§3.2).
- **OD-P2 decided:** new **Ruling 1.4a** specifies the metric "value of priced holdings": its
  name, definition, label, excluded count and list. It **never** feeds the total, a return, a
  gain, or a weight.
- **OD-P3 decided:** HG2 runs on synthetic US/CN/HK data plus a real US/ECB slice (§12).
- **OD-P4 decided:** the daily Cariño-linked attribution supersedes HG1 round 4 §4.3 (Ruling 9.8).
- **Ruling 1.4, new item 4:** the total before the first event is 0, and an empty ledger is not.
- **Ruling 1.7:** Current mode is deferred by the PM's CP3a ruling. Ruling 1.7 stands for when it
  is built.
- **Ruling 2.1 and Ruling 6.2 (numerics), rewritten:** the binding requirement is now the
  **presented value**, the half-up rounding of the exact mathematical result. **Certified exact
  bracketing** (the engineer's plan, tech plan §16.6) is conformant, and is preferred for
  annualization and the IRR, whose exponents are rational. A tie that cannot be decided has a
  stated rule. `Decimal` at `prec` 50 stays allowed where no exact form exists (Cariño
  logarithms).
- **Ruling 6.4a-perf (new, in Example V-2a):** an unapplied corroborated split (the CP2 dry run's
  `WOULD_APPEND`) is `SOURCE_CONFLICT`. This confirms engineer choice 2.
- **§15, new OD-P5:** reason codes for "zero denominator", "no sign change" and "history too
  short". My recommendation is no new codes. Put to the owner.
- **Ruling 1.5 (clarified):** the single reason comes only from causes at the result's own state
  level. A suppressed result never borrows `STALE_DATA` from an `AVAILABLE` input.
- **Ruling 5.3 (extended):** a negative TWR factor (the value fell below zero) gives
  `INSUFFICIENT_DATA`, detail `NEGATIVE_VALUE`. A factor of 0 is a real −100 %.
- **Detail names added:** `NEGATIVE_VALUE`, `WINDOW_NOT_POSITIVE` (B ≥ E),
  `WINDOW_BEFORE_SNAPSHOT` (with `NOT_RECONSTRUCTABLE`), `NO_VALUED_COMPONENT`.
- **The CP3 golden fixture, part 1** (valuation, TWR, annualization) is authored:
  `methodology/fixtures/cp3_golden/` (`cp3_golden/1.0-part1`).

**Authority:**

- PD-0021 §9: lot depletion, split fractions and return denominators are Quant decisions, and the
  engineer must not decide them silently;
- PD-0006, PD-0007, PD-0025, PD-0030: the state vocabulary, with every threshold left to this role;
- CLAUDE.md invariants P1, P3–P6, P9, P12, NFR-001 and §34 (conventions are part of the method).

**Answers:**

- OI-8 (money rounding), §2;
- OI-2 and MD-OI-1 (valuation cutoff), Ruling 1.7;
- MD-OI-2 and MD-OI-4, §2 and Ruling 1.4;
- OI-1 and OI-6 (basis in reporting currency at transaction-date FX), Ruling 3.7;
- the CP3 parts of OI-4: fee capitalization (3.6), income timing and buckets (§8), the state of a
  partly known basis (3.10);
- `ledger-replay/1.3` Ruling 5.3 (the bucket for `INTEREST_CHARGED`) and 5A.5 (attributing a
  conversion), §8;
- HG1 round 4 §4.3, §4.6, §7.3, §7.4, §7.6, §7.9, where CP3 owns them;
- PD-0033 and PD-0034 items: the HKEX default close and the ECB minute (§13; written into
  `market-data/1.8`).

**Owner decisions:** OD-P1 to OD-P4 were put to the owner in 1.0 and **decided in PD-0035**, each
as recommended (§15). OD-P5 (reason codes) is new in 1.1 and open.

**Inputs read:**

- PRD §3, §4, §8, §9, §11.2, §11.3, §14, §15, §18.4, §32–§34, §38.3 CP3, §38.4 HG2, UAT-02 and
  UAT-04;
- PD-0006, PD-0007, PD-0021, PD-0024, PD-0025, PD-0026, PD-0030 to PD-0034;
- `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` (`ledger-replay/1.3`) in full;
- `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (`market-data/1.7`, amended here to 1.8);
- `methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md`;
- `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md` §4–§9 and `HG1_ROUND4_VERIFICATION.md` §4, §7
  and §13.5;
- `reviews/gates/OPEN_METHODOLOGY_DEBT_MAX_DRAWDOWN_CONVENTION.md`;
- `methodology/fixtures/cp1_golden/` (event list);
- the calendar drafts' metadata.

From `src/` I read only field and enum names (`domain/ledger.py`: DIVIDEND `ex_date` exists and
must not be after the pay date; `product_contract/vocabulary.py`; `methodology_registry.py`'s
fifteen §33 fields) and the places that hold the 14:15 constant. No `src/` code was run.

> **This document approves nothing.** It approves no gate, selects no vendor, changes no product
> scope and writes no UI wording. Where a question needs the product owner, it says so, gives
> options and a recommendation, and leaves it open (§15).

**Label key** (as in `ledger-replay/1.3` and `market-data/1.8`):

- **RULING**: binding within the Quant role's authority (methods, conventions, thresholds,
  sufficiency semantics).
- **RECOMMENDATION**: a change I believe is needed in someone else's area. They decide it.
- **OWNER DECISION**: put to the product owner. It is stated and left open.

**Worked examples.** Every expected value was derived by hand from the inputs shown, and the
derivation sits next to it. I checked the long divisions, the logarithms of the Cariño factors and
the IRR bisections with exact `fractions.Fraction` and Python `decimal` in a scratch shell, used as
a calculator. **No value comes from running or reading the engine.** All prices and FX rates are
hypothetical, chosen to exercise a rule. HKD rates are kept inside the 7.75–7.85 peg band, so that
`market-data` Ruling 1.5 would not flag them.

---

## 0. Objects, scope and notation

- **`R`**: the portfolio's reporting currency (PRD §8.1).
- **`(D, L, M)`**: the as-of date (end of day `D`), the ledger version and the market-data version.
  Every value in this document is a function of `(D, L, M)`, or of a window and `(L, M)`, plus the
  convention IDs. Nothing reads a clock, except Current mode's choice of `D` (Ruling 1.7), which
  is itself recorded.
- **`S(D, L)`**: the replayed state of `ledger-replay/1.3`, including its lot model (Ruling
  0.4.1). CP3 reads the exact lot model, not the replay's emitted basis values (Ruling 2.5).
- **`P(ℓ, D)`**: the resolved raw official close for listing `ℓ` (`market-data` Ruling 2.1), with
  its state, freshness and lineage. **`c(ℓ)`** is its trading currency.
- **`X(c→R, D)`**: the resolved rate in units of `R` per unit of `c` (`market-data` Rulings 1.3 and
  1.6). It is an exact ratio of two ECB quotes. **`X(R→R, D) := 1`**, with no lookup and no
  freshness.
- **Scopes:**
  - **portfolio**: the primary scope. Internal transfers are not flows (`ledger-replay` 6.1);
  - **account**: internal transfers are flows of the account (`ledger-replay` 6.1). Every formula
    below applies unchanged with the account's flow set;
  - **position**: `(account, listing)`;
  - **listing at portfolio level**: the sum over accounts.
- **Two tiers of number** (Ruling 2.1): tier **E** (engine, exact) and tier **P** (presented,
  quantized once).
- **Windows** are half-open, **`(B, E]`**: the base valuation is at the end of `B`, the last at the
  end of `E`, and the window contains the days `B+1 … E`. This is `HG1 M1` RULING 1(a): the base is
  the valuation strictly before the first in-window day.
- **Judgment class (§20.2):** every metric in this document is a **Fact**. Each is a deterministic
  historical computation. CP3 emits no word such as "high", "poor" or "good" (P4), and nothing
  predictive (P6). An annualized return is a historical average compound growth rate, not an
  expected return (§7).

---

## 1. Valuation

### RULING 1.1: The value of a position in its trading currency

```
MV_c(a, ℓ, D) = q(a, ℓ, D | L) × P(ℓ, D | M)          in c(ℓ), exact
```

- `q` is the replayed end-of-day quantity. `P` is the raw official close of `s(D)`, the latest
  session of `ℓ`'s calendar on or before `D`. Both are terminating decimals, so the product is
  exact.
- **`q = 0` means no position.** No price is looked up and no value is emitted. Unpriced
  zero-quantity listings never affect any total.
- **State.** Take the worst of these, with the reason chosen by Ruling 1.5:
  - the quantity's state from replay: `AVAILABLE`, or `INSUFFICIENT_DATA` with
    `LEDGER_INCONSISTENT`, `UNRESOLVED_CONVENTION` (split fraction) or `NOT_RECONSTRUCTABLE`;
  - (1.3) a suppression carried with tainted lots by an internal transfer (`market-data` Ruling
    6.4c, `SOURCE_CONFLICT`, cause `SPLIT_SUPPRESSION_CARRIED`). This applies to a receiving
    position that did not hold the listing at the ex-date, at account and portfolio scope alike;
  - the corporate-action check of `market-data` Rulings 6.4 and 6.4a (`SOURCE_CONFLICT`, or a
    calendar coverage gap with no code);
  - the price's state from `market-data` Rulings 4.4, 4.7 and 5.2.
- **Only `RAW` closes value a position** (`market-data` Ruling 2.3). No adjusted series and no
  sibling listing is ever used.

### RULING 1.1b (1.9): The last print date of a holding, valued or withheld

- **`price_date_used`** is the session date of the close that **values** the holding. It is
  reported only when the holding has a value (`AVAILABLE` or `LIMITED`).
- **`last_print_date`** is the session date of the last admissible print of the listing at or before
  `D` in `M`, or in `M_t` in Current mode. This is `market-data` Ruling 5.2's `last_print(ℓ)`, the
  print the missed-session count `s(ℓ, D)` is counted from.
  - It is lineage. It is reported **whenever such a print exists**, including when the value is
    withheld:
    - 5 or more missed sessions;
    - a split suppression (`market-data` 6.4–6.4c);
    - an unresolved quantity.
  - When the holding is valued, it equals `price_date_used`.
  - When no print exists at or before `D` (`MISSING_PRICE_HISTORY`), it is absent.
- **Never a value.** No price, and no value computed from the withheld print, is reported beside it.
  "Last priced on 2025-03-07" explains the withholding (P9). It does not soften it (P5).

### RULING 1.1a (1.5): A carried split taint under `FIFO/1` is decided by the end-of-day lot book

`market-data` Ruling 6.4c rule 4 decides "holds a unit of a tainted carried lot" by lot identity
under the lot method in force, with a conservative stand-in until the FIFO fold exists. That fold
is `ledger-replay/1.4` Ruling 0.5, and from 1.5 the stand-in is replaced as follows.

1. **The holding.** A receiving position's valuation on `D` (Ruling 1.1) carries the suppression
   (`SOURCE_CONFLICT`, cause `SPLIT_SUPPRESSION_CARRIED`) **iff its end-of-day lot book on `D`
   holds a lot tainted for `K`**. A lot is tainted when its carry history has a hop out of a
   position suppressed for `K` on the hop's date, within the duration of 6.4c rule 3.
2. **So the holding's suppression ends on the day the last tainted unit is relieved.** At the end
   of that day the position holds no tainted unit, and it is valued.
3. **The events of that day stay suppressed.** Every `SELL` or `TRANSFER_OUT` dated `D` whose relief
   record holds a tainted portion is suppressed:
   - a sale's realized gain (Ruling 3.8 (1.5));
   - an in-kind flow (Ruling 4.3; 6.4c rule 6);
   - the sale's trade result in the attribution (part 4).
4. **Never more suppression than the conservative rule.** On the first day a receiver ends at 0, its
   lot book is empty. So the lot-book rule ends the suppression no later.

**Why the end-of-day book.** A holding is valued as its end-of-day quantity times the close. Once
no tainted unit is held, quantity and price are in one unit system. The units that were in
different units have left through events of that day, and those events are suppressed (item 3).

**Example** (`cp3_golden` part 3, P17; `ledger-replay` Example F-I):

- V2 receives 40 tainted units on 03-05 and holds its own 100, bought on 03-04 after the ex-date.
- Its valuation is suppressed on 03-05 to 03-09.
- On 03-10 its `SELL` of 40 relieves the tainted lot whole, because its date 02-03 is older than
  03-04. The sale's realized gain is suppressed.
- V2's holding on 03-10 is 100 × 20.00 = **2,000.00**, `AVAILABLE`.
- The conservative rule would have suppressed V2 indefinitely, because it never ends a day at 0.

### RULING 1.2: The value in the reporting currency

```
MV_R(a, ℓ, D) = MV_c(a, ℓ, D) × X(c(ℓ)→R, D)           exact rational
```

- The rate is the ECB fixing `u(D)` of `market-data` Ruling 1.6, as an exact cross. Its state
  joins the position's state.
- **CNH** (`c(ℓ)` = CNH) gives `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` (`market-data` Ruling
  1.4). The native value stays `AVAILABLE`.
- **Why the same-date fixing.** PRD §8.3 says historical values use the FX of the valuation date.
  `market-data` Ruling 1.2 makes the date-`D` bundle (each market's close of `D` plus the ECB fixing
  of `D`) the definition of "as of `D`".

### RULING 1.3: Cash and dividend receivables

```
Cash_R(a, k, D) = balance(a, k, D | L) × X(k→R, D)
Recv_R(e, D)    = amount(e) × X(currency(e)→R, D)      (Ruling 8.1: an accrued DIVIDEND e)
```

- A zero balance needs no rate.
- A negative balance is valued signed (`ledger-replay` Ruling 1.3).
- A CNH balance is `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` in `R`. In CNH it is a fact.

### RULING 1.4: Totals, and a total with any unvalued component

```
TV_R(D) = Σ_positions MV_R + Σ_cash Cash_R + Σ_receivables Recv_R       exact
```

The same holds at account scope. The state of `TV_R` follows these rules:

1. **Any component `INSUFFICIENT_DATA` makes the total `INSUFFICIENT_DATA`**, with no value. A
   component is one of: an unpriced position (no admitted source, no print, `SOURCE_CONFLICT`,
   stale for 5 or more sessions); an un-FX-able amount (CNH, a missing rate); an unresolved or
   inconsistent quantity; or a coverage gap. The reason is chosen by Ruling 1.5. Lineage lists
   **every** unvalued component with its own cause, its native quantity or amount, and its
   listing or currency.
2. **Otherwise, any component `LIMITED` makes the total `LIMITED` + `STALE_DATA`.** Within
   valuation only staleness of 2 to 4 sessions or fixings produces `LIMITED`. The value is
   presented (PD-0007), and the **stale weight** is stated beside it as a number (HG1 round 4 §6
   R1):
   ```
   stale weight = Σ_{LIMITED components} |v| / Σ_{all components} |v|        (gross weights)
   ```
   Gross weights are used because cash may be negative. A signed denominator could be zero or
   change sign.

   **(1.2) Gross value 0.** If Σ |v| over all components is 0 (every component, including the
   `LIMITED` one, is worth exactly 0), the share is 0/0 and is **not stated**. The total stays
   `LIMITED` + `STALE_DATA` with its value (0), and lineage carries `STALE_SHARE_UNDEFINED`.
   - A stated share would mean nothing here: no value depends on the stale input.
   - Suppressing the total would hide a fact.
3. **Otherwise the total is `AVAILABLE`.** If any component carries `STALE_DATA` (one missed
   session or fixing), the total carries `AVAILABLE` + `STALE_DATA`.

This **adopts `market-data` Ruling 4.7 item 3 and extends it** from "no price" to every cause of an
unvalued component. It also **amends `market-data` Ruling 1.4**: a CNH component no longer makes
the aggregate `LIMITED` (now in `market-data/1.8`). And it **closes MD-OI-4**: a position whose
price is in `DISAGREEMENT` has no measurable weight either.

**Why.**

- HG1 round 4 §6 R1 allows a `LIMITED` aggregate only when the excluded weight is stated as a
  number.
- An unvalued component has no reporting-currency value, so its weight cannot be measured. A
  number that leaves it out would be a partial total presented as the total. That is exactly
  what §32 forbids: "values that can be mistaken for real analytics".
- **Rejected:**
  - weighting the excluded part by its cost basis, which mixes a historical amount with current
    values (`market-data` 4.7);
  - weighting it by the last stale price, which is the very number the freshness rule declined
    to stand behind;
  - for CNH, the CNY rate, which is a different market's price (PD-0030 §3).

**What stays available.** Native per-currency subtotals and per-position native values are
separate metrics and remain facts. Examples: "HKD 3,000 cash"; "0700: 500 shares, HKD 175,000.00".

- A **native per-currency subtotal** for currency `c` is the sum of the native values of every
  component denominated in `c`: cash in `c`, receivables in `c`, and positions whose listing
  currency is `c`.
- It is `INSUFFICIENT_DATA` if any such component lacks a native value. For example, an unpriced
  HKD listing makes the HKD subtotal `INSUFFICIENT_DATA`.

The separately labelled "value of priced holdings" is a **different metric**, decided in PD-0035
§2 and specified in Ruling 1.4a.

4. **(1.1) Before the first event, and with no events at all.**
   - A portfolio with no snapshot account, valued at a `D` before its first event, holds nothing.
     The replayed state is empty, and that is a claim about the data (`ledger-replay` Ruling 8.1).
     So **`TV_R(D)` = 0, `AVAILABLE`**, with no lookup.
   - A ledger with **no live event at all** has no portfolio to value. The total is
     `INSUFFICIENT_DATA`, with no reason and detail `NO_LIVE_LEDGER_EVENTS`. That confirms the CP3a
     engineer's choice. It is never presented as 0.

### RULING 1.4a (1.1; PD-0035 §2): "Value of priced holdings", a separate, partial metric

- **Suggested metric ID:** `value.priced_holdings` (the CP3a engine's naming: `priced_holdings_value`).
- **Definition.** The sum, in `R`, of the reporting-currency values of every component of
  `TV_R(D)` (Ruling 1.4) whose own value is `AVAILABLE` or `LIMITED`. It always comes with:
  - the **excluded count**: the number of non-zero components with no reporting-currency value;
  - the **excluded list**: each excluded component (position `(account, listing)`, cash
    `(account, currency)`, or receivable), with its native quantity or amount and its own reason.
- **Label** (the meaning; the design writes the words before CP7): "Value of priced holdings:
  partial; excludes N holdings that cannot be valued". The count is in the same visual unit as
  the value (HG1 round 4 §6 R1 spirit). It carries the same freshness vector as a total
  (Ruling 1.6).
- **When it exists.** It is emitted **only when `TV_R(D)` is `INSUFFICIENT_DATA` because one or
  more components are unvalued** (Ruling 1.4 item 1), and at least one component is valued.
- **When it does not exist:**
  - when the total is `AVAILABLE` or `LIMITED`, it is not emitted, because the total is the
    figure and a second number with the same content would compete with it;
  - when the total is suppressed but **no** component is valued, it is emitted as
    `INSUFFICIENT_DATA`, no reason, detail `NO_VALUED_COMPONENT`, and never as 0;
  - when an account is before its snapshot, it is not emitted (the total is `NOT_RECONSTRUCTABLE`).
    **(1.2, Q9)** This holds when **any one** account is before its snapshot, even if the others are
    reconstructable. That account's holdings are unknown, so no count of what is left out could be
    stated. Confirmed.
  - if the **set** of holdings itself is unknown, it is `INSUFFICIENT_DATA` with that reason and
    no value. That covers any component whose quantity is `LEDGER_INCONSISTENT` or
    split-unresolved: a partial sum over an unknown set cannot state what it leaves out. (An
    account before its snapshot is the not-emitted case below.)
- **State:** the worst state of the included components (`AVAILABLE` or `LIMITED`), with
  `STALE_DATA` propagated as for a total. A stale share is stated if `LIMITED` (Ruling 1.4
  item 2), computed over the included components.
- **Never:**
  - shown in the total's place or labelled as the total;
  - summed into, or substituted for, `TV_R` anywhere;
  - used as a base value, end value or flow value of any return or gain (§5–§9);
  - used as a denominator for any weight or share, including stale or excluded weights;
  - used to make an aggregate `LIMITED`.

  A return over a window whose end total is `INSUFFICIENT_DATA` stays `INSUFFICIENT_DATA`.
- **Why these limits.** The owner chose to show what can be valued rather than nothing (PD-0035
  §2). The limits keep that figure from becoming the partial total presented as the total that
  Ruling 1.4 forbids. A return or a weight built on it would silently change the portfolio being
  measured on the days a holding is unvalued.
- **Rounding:** as any derived money value (Ruling 2.2).
- **Example V-2 (b), continued.** The total is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`. The
  value of priced holdings is 359,950/39 → **9,229.49 USD**, `AVAILABLE`, with excluded count
  **1**: the XSHG listing, 100 shares, `MISSING_PRICE_HISTORY`.

### RULING 1.5: One reason code for a combined state, by priority

When several non-`AVAILABLE` causes combine (in a total, a return, an attribution), the single
`reason_code` (PD-0006: zero or one) is the first present in this order:

1. `CALCULATION_ERROR`: an engine fault (HG1 R2), including a failed runtime identity (§11);
2. `LEDGER_INCONSISTENT`;
3. `NOT_RECONSTRUCTABLE`;
4. `SOURCE_CONFLICT`;
5. `UNRESOLVED_CONVENTION`;
6. `UNSUPPORTED_ASSET`;
7. `MISSING_BENCHMARK` (1.2; a CP4 code, placed now);
8. `MISSING_COST_BASIS`;
9. `MISSING_PRICE_HISTORY`;
10. `MISSING_FX_HISTORY`;
11. `STALE_DATA`;
12. none (for example a calendar coverage gap only, or a cause with no code).

**(1.2) Why `MISSING_BENCHMARK` goes there.** Like `UNSUPPORTED_ASSET`, it says the metric is
**undefined**: no reference point (P4), whatever data exists. More data does not resolve it; the
user's choice of benchmark does. So it ranks with the method-domain codes, above every
missing-data code. The CP3b engineer placed it after `MISSING_FX_HISTORY`, which ranks a missing
FX rate as more fundamental than the absence of anything to compare with. That changes nothing in
CP3, where no metric emits it.

**(1.1) Which causes compete.** The reason is chosen only from the causes **at the result's own
state level**:

- an `INSUFFICIENT_DATA` result takes its code from the `INSUFFICIENT_DATA` causes;
- a `LIMITED` result takes it from the `LIMITED` causes;
- an `AVAILABLE` result carries `STALE_DATA` or nothing.

If no cause at that level has a code, the reason is none, **even if a lower-severity cause has one**.

Example: a TWR that is `INSUFFICIENT_DATA` because of `NON_POSITIVE_BASE` (no code) has reason
**none**. It does not take `STALE_DATA` from an `AVAILABLE` + `STALE_DATA` valuation in the same
window, because staleness is not why it is suppressed. The 1.0 wording ("the first present") was
ambiguous here.

Every cause stays in lineage, with its detail. The order answers "what should be fixed first":

- the ledger contradicting itself makes everything downstream moot;
- a conflict needs a human resolution record;
- a convention gap needs a methodology ruling;
- missing data needs a source;
- staleness resolves with time.

It matches the replay's existing choice (inconsistency outranks convention; review §20.2).

### RULING 1.6: Freshness of a total

A total (and every return built from totals) carries a **freshness vector**, not one state:

- for each exchange calendar governing a non-zero position: the oldest session used and the
  largest missed-session count. **(1.2) The entry is keyed by the calendar's `calendar_id`** and
  lists the MICs it governs. For example, one entry for XNYS and XNAS together under the NYSE
  calendar. Staleness is counted in a calendar's sessions (`market-data` Ruling 5.2), so a
  per-MIC key would repeat one fact. The per-listing session used and missed count stay on each
  holding;
- for each currency translated: the fixing date used and the missed-fixing count;
- `DataDelayStatus` (`END_OF_DAY` for every PD-0027 datum).

**Summary freshness:** `UNKNOWN` if any component is `UNKNOWN` (the total is then
`INSUFFICIENT_DATA` already); `STALE` if any component is `STALE`; otherwise `CURRENT`.

A total is a **single-leg level** in HG1 round 4 §5.2's table. It is computable and not degraded by
non-simultaneous closes, but its instants are disclosed. The temporal-comparability disclosure
applies to **comparisons** (two-leg metrics). CP3 defines no two-leg comparison; benchmark
comparisons are CP4.

### RULING 1.7: The as-of date in both modes (closes OI-2 and MD-OI-1)

**Historical mode.** The caller gives `D`. Then:

- ledger events are included by **local `event_date` ≤ `D`** (`ledger-replay` Ruling 1.2, OI-2),
  never by instant;
- prices are the closes of `s(D)` in each listing's own calendar;
- FX is the fixing `u(D)`.

This is the date-label bundle of `market-data` Ruling 2.2 (5). An HKEX trade dated `D` is in
`S(D)` and is valued with the HKEX close of `D`, whoever computes it.

**Current mode at instant `t`.** The engine chooses

```
D_c(t) = the latest date D ≤ UTC-date(t) such that
         for every exchange m governing a listing with non-zero quantity in S(D, L):
             D ∉ C_m   or   scheduled_close_m(D) ≤ t
         and, if any amount in a currency other than R is held:
             D ∉ C_ECB or   16:00 Europe/Berlin on D ≤ t
```

It then computes exactly as in historical mode at `D_c(t)`, with the additional Current-mode
constraint that only files retrieved at or before `t` are read (`market-data` Rulings 2.2 (6) and
1.6). `D_c(t)` and `t` are both recorded in the manifest.

**(1.2) How "only files retrieved at or before `t`" restricts `M` (Q6).**

- A Current-mode computation at `t` runs over **`M_t`**: the subset of the release `M` whose
  files' recorded `retrieval_time` is ≤ `t`. Calendar files are included, by their own
  registration time.
- **Every** CP2 step runs over `M_t`, not over `M`:
  - selection of a reading;
  - two-source reconciliation (Ruling 4.3);
  - the one-vintage rule (0.1);
  - the date-set and provenance checks (1.1a);
  - label tests V0–V3;
  - freshness counts.
- A file retrieved after `t` therefore cannot corroborate, contradict, revise or date-check
  anything at `t`. Refusing only a selected late reading (the CP3b behaviour) is not enough: a later
  file could still turn a `SINGLE_SOURCE` value into `DISAGREEMENT`, or the reverse.
- `M_t` is a deterministic function of `(M, t)`. The manifest records `t`, `M`, and the hashes
  of the files excluded from `M`, so the computation is reproducible.
- If `M_t` leaves a needed input without a reading, the outcome is the ordinary CP2 one (no
  history, or stale). It is not a special state.
- **(1.4 clarification, confirmed for the engineer.)** "Every CP2 step" includes **F8 split
  detection and its suppressions** (`market-data` Rulings 6.4–6.4c). A corporate-action feed or
  filing file retrieved after `t` neither creates nor clears a suppression at `t`. Detection in
  Current mode runs over the same `M_t` as the valuation.

**(1.2) Nothing held (Q8).** If `S(D, L)` holds no non-zero position and no amount in a currency
other than `R`, both conditions are vacuous, so `D_c(t)` = `UTC-date(t)`. Confirmed. Ledger events
dated after that date are not in the state, which is correct under Ruling 1.2 of `ledger-replay`.

**(1.1)** The PM's CP3a ruling builds only historical mode in CP3 and refuses a Current request with
a typed refusal (tech plan §16.14). That is a scheduling choice, consistent with this ruling.
When Current mode is built, it chooses `D_c(t)` as above.

- If a governing calendar does not cover a candidate date, the choice of `D_c` cannot be made.
  Every Current-mode metric is then `INSUFFICIENT_DATA`, with no code and lineage cause
  `CALENDAR_COVERAGE_GAP`. This fails closed and is never resolved by guessing a weekday.
- **Why.** This is HG1 round 4 §7.6's rule, "the as-of date is the latest instant at or before
  which every required input has a print", written in date labels. A dated snapshot then always
  bounds its inputs (P12, §34), and two people computing at the same `t` get the same `D`.
- **Rejected:**
  - an instant-based cutoff that orders events across time zones (rejected in `ledger-replay`
    Ruling 1.2);
  - per-market as-of dates with no portfolio date, which give no single state to reproduce;
  - "today" in some time zone, which bounds no input.

**(1.12) Ruling 1.7 amended: the date test covers every event dated `D`, and the market-data
instant clauses are met by the composition.**

1. **The composition satisfies `market-data` Rulings 1.6, 2.2 item 6 and 5.2.**
   - **What Current mode is.** It is the composition of three steps:
     - (i) choose `D_c(t)` by this ruling;
     - (ii) restrict `M` to `M_t`;
     - (iii) apply the **historical-mode** market-data rules at `D_c(t)`.

     The market-data policies (price selection, FX resolution, freshness) take a **date**. They
     do not need to take `t`.
   - **What those rulings' Current-mode clauses require.** Each puts conditions on single inputs:
     - **(R) retrieval:** an observation counts only if its file's retrieval time is ≤ `t`
       (1.6, 2.2 item 6);
     - **(C) close:** a session `d` counts as available or expected only if its scheduled close is
       ≤ `t` (2.2 item 6, 5.2);
     - **(P) publication:** a fixing date `f` counts as expected only if 16:00 Europe/Berlin on
       `f` is ≤ `t` (1.6).
   - **(R) is `M_t` exactly.**
   - **(C) and (P) are vacuous on every input of the bundle at `D = D_c(t)`.** The bundle reads
     sessions `s ≤ D` and fixing dates `f ≤ D` only (`market-data` Ruling 2.2 item 5).
     - **For `s = D` or `f = D`:** the exchange or the ECB is in the test of item 2 below, so
       `D_c(t)` was chosen only if the close or the publication is ≤ `t`.
     - **For `s < D` or `f < D`:** `s` and `f` are at most `UTC-date(t) − 1`. Every calendar in
       use has its scheduled close or publication on the **same UTC date** as its local date:
       - XNYS and XNAS 16:00 New York = 20:00 or 21:00 UTC;
       - XHKG 16:10 = 08:10 UTC;
       - XSHG and XSHE 15:00 = 07:00 UTC;
       - the ECB 16:00 Berlin = 14:00 or 15:00 UTC.

       So the close or publication is before 00:00 UTC of `UTC-date(t)`, which is ≤ `t`.
     - **A calendar for which that same-UTC-date property fails** must be checked again before
       this argument covers it. The engineer's calendar check should assert the property for
       every calendar registered.
     - **Sessions on local dates after `D`.** An HKEX or SSE session dated `UTC-date(t) + 1`
       closes at 08:10 or 07:00 UTC of that date, which is after `t`, so it is never available.
   - **So a date-plus-`M_t` result and an instant-aware result agree on every input the bundle
     reads.**
   - **Where an instant-aware policy would differ: inputs outside the bundle.** Example: at
     10:00 UTC, an HKEX close of the same day exists while the US close and the ECB fixing do
     not. Per-input instant selection would value the HKEX holding at today's close and
     translate at yesterday's fixing. That is the per-market as-of date rejected above. The
     `market-data` instant clauses are **availability conditions**: they say what may be used at
     `t`. They are **not** a definition of the bundle. The bundle is this ruling's, as
     `market-data` Ruling 2.2 item 5 left it to CP3 (MD-OI-1, closed in `market-data/1.8`).
2. **The test of `D` is extended.** In the definition of `D_c(t)` above:
   - **"every exchange `m` governing a listing with non-zero quantity in `S(D, L)`"** becomes:
     every exchange `m` governing a listing that has non-zero quantity in `S(D, L)`, **or that is
     named by a live ledger event dated `D`**;
   - **"if any amount in a currency other than `R` is held"** becomes: if any amount in a currency
     other than `R` is held at the end of `D` (a balance, a position's listing currency, or an
     accrued receivable), **or if a live ledger event dated `D` carries an amount, or names a
     listing, whose currency is not `R`**.
   - **Why.** Events dated `D` are in the state at `D` and are inputs of window, gain, income and
     attribution metrics ending at `D`. Some need `D`'s close or fixing while nothing they touch
     remains held at the end of `D`:
     - an in-kind flow (Ruling 4.3);
     - a foreign-currency cash flow, income, cost or conversion (Rulings 4.3, 8.1–8.5);
     - realized proceeds (Ruling 3.8).

     HG1 round 4 §7.6's rule, "every required input has a print", requires them.
   - **One test for every metric.** The test is deliberately wider than any one metric needs:
     a `BUY`, or a same-day `SELL` of a listing still held, adds an exchange whose `D` close the
     metric may not read. That costs at most the time until that close. **`D_c(t)` stays a
     function of `(t, L, M_t)` only, never of the metric requested**, so every metric computed at
     `t` shares one date (P12).
   - **Q8 (nothing held) is refined.** Both conditions are vacuous only when there is also no
     live event dated `D`.
3. **The ordinary outcome is unchanged.** If an input of the bundle at `D_c(t)` still has no
   reading in `M_t`, for example a fixing published but not yet retrieved, the outcome is the
   ordinary CP2 one: `STALE`, or no history (item "If `M_t` leaves a needed input…" above).
   `market-data` Ruling 1.6's "a late publication can show `m = 1` for a short while" is that
   case.
4. **What `M_t` scopes, and what it does not (review §33.6).** "Every CP2 step runs over `M_t`"
   (Ruling 1.7 (1.2)) scopes the **files of `M`**, of every kind: prices, FX, corporate actions
   and calendars (calendars by their registration time). Their observations carry market
   information dated in time, so a file retrieved after `t` could look ahead.
   - **Reference data held outside `M` is not scoped to `t`.** That is the source registry
     (`SOURCES.json`: terms attestation, `upstream_provider`, `independence_group`, `synthetic`)
     and the identity registry the resolver reads. Each is read **at the version in force when the
     computation runs**, and it is **pinned in the manifest by digest**. It is an input like the
     ledger version `L`, which the caller also pins independently of `t`.
   - **Why the attestation is not scoped.** An attestation is a permission to use data, and it
     applies when the data is used. Reading the registry as of `t` would revive a withdrawn
     permission for a computation run after the withdrawal. A withdrawal therefore makes the build
     fail closed, in either mode. Adding an attestation cannot bring a file into `M`, because `M`
     is an explicit file set (`market-data` Ruling 0.1).
   - **Why identities and upstream groups are not scoped.**
     - They describe what a source is, or which listing a row belongs to. They carry no
       observation of the market after `t`.
     - A later version is a **correction**. It applies by version, as a ledger correction applies
       by `L` (`ledger-replay` Ruling 1.2), and the manifest records which version was used.
     - Effective-dated content inside a registry (for example a symbol change, `market-data`
       Ruling 7.2) is applied by date label, as now.
   - **What must be recorded.** Today the manifest records `identity_digest`, and `reproduce()`
     compares it. It records **no** source-registry digest, so a change to `independence_group` or
     `synthetic` could change a reconciliation status or the world of a corroboration with no
     trace. In both modes the manifest records **`source_registry_digest`**:
     - the SHA-256 of the canonical JSON of the full source records, every field including
       `terms_check`;
     - for every source with at least one file in the `M` the computation read (`M_t` in Current
       mode);
     - sorted by `source_id`.

     `reproduce()` compares it as it compares `identity_digest`. A difference is reported, and
     never passes silently.
5. **A Current-mode refusal is a Current-mode result (review CP4-2).** Ruling 1.7 (1.2)'s
   manifest record (`t`, `M`, and the hashes of the files `M_t` leaves out) applies to **every**
   result of a Current-mode request, including a refusal: the synthetic refusal,
   `DETECTION_POLICY_UNMATCHED`, `NO_ELIGIBLE_DATE` and a coverage gap. Such a refusal records:
   - `valuation_mode` Current;
   - `as_of_rule` `D_c(t)`;
   - the instant `t`;
   - the parent release `M`, and the hashes `M_t` excludes;
   - the `D_c(t)` if one was chosen, else none;
   - the digests of item 4.

   Its keys or causes can then be traced back to the `M_t` they came from (P9).

#### Example 1.7-C (1.12): an event dated `D` that needs `D`'s fixing, with nothing foreign left

- **Calendars, assumed for the example.** 2026-10-01 (Thursday) and 2026-10-02 (Friday) are
  fixing days in `C_ECB`. Publication is 16:00 Berlin = **14:00 UTC** (CEST).
- **Ledger.** `R` = USD. A1 holds USD cash and 7,800 HKD. On 2026-10-02 it **withdraws all 7,800
  HKD**. Nothing else is held.
- **`t` = 2026-10-02 12:00 UTC.** `M_t` holds fixings up to 2026-10-01.

| Rule | `D_c(t)` | Withdrawal translated at | State of that input |
|---|---|---|---|
| 1.11 (end-of-`D` test only) | **2026-10-02**. At the end of 10-02 only USD is held, so both conditions are vacuous. | the 10-01 fixing (`u(D)` = 10-01, `m` = 1) | `STALE`, `AVAILABLE` + `STALE_DATA`: a 10-02 flow at a 10-01 rate |
| instant-aware `market-data` policy at 10-02 | 2026-10-02 | the 10-01 fixing (10-02 is not yet expected, so `m` = 0) | `CURRENT`. The same wrong-date rate, now unflagged. |
| **1.12** | **2026-10-01**. The event dated 10-02 is in HKD, so the ECB test applies, and 14:00 UTC > `t`. For 10-01: HKD is held, and the 10-01 publication (14:00 UTC on 10-01) is ≤ `t`. | not in the state: its `event_date` 10-02 is after `D_c` | every input `CURRENT` |

The in-kind version is the same. A1 transfers out its last 100 units of an XNYS listing on
2026-10-02, and holds only USD cash afterwards. Under 1.11, `D_c` = 10-02 and the out-flow is
valued at 10-01's close, `STALE`. Under 1.12, the event names an XNYS listing whose 10-02 close
(20:00 UTC) is after `t`, so `D_c` = 10-01.

### RULING 1.8: A position is valued in its listing's currency, never in its event currency

For Southbound holdings (an HKEX listing bought with CNY), the position's native value is in HKD
(`c(ℓ)`), whatever currency the purchase was paid in. The event currency matters only for cash
(`ledger-replay` 0.3) and for the lot's basis currency (Ruling 3.7).

#### Example V-1: valuation and presentation (USD reporting; the end of day 2 of Example W, §5)

ECB on 2025-04-02 (hypothetical): `x_USD` = 1.0800 and `x_HKD` = 8.4240. So
`X(HKD→USD)` = 1.0800 / 8.4240 = 10800 / 84240 = **5/39** (7.8 HKD per USD, inside the band).

| Component | Native | Exact in USD | Presented (Ruling 2.2) |
|---|---|---|---|
| H@XHKG, 100 × 400.00 | HKD 40,000.00 | 40,000 × 5/39 = 200,000/39 | 5,128.21 |
| Cash HKD | 790 | 790 × 5/39 = 3,950/39 | 101.28 |
| Cash USD | 4,000 | 4,000 | 4,000.00 |
| **Total** | | 156,000/39 + 203,950/39 = **359,950/39** = 9,229.4871794… | **9,229.49** |

The presented parts happen to sum to the presented total here. Ruling 2.4 governs when they do not.

#### Example V-2: stale and unvalued components

Take V-1 with two changes.

- **(a) H's last print is 3 sessions old.**
  - H is `LIMITED` + `STALE_DATA`.
  - The total is **9,229.49, `LIMITED` + `STALE_DATA`**.
  - Stale weight = (200,000/39) / (359,950/39) = 200,000 / 359,950 = 4,000/7,199 = 0.555632…,
    stated as **55.56 %**.
- **(b) The portfolio also holds 100 shares of an XSHG A-share.** No CN source is admitted
  (`market-data` 4.7).
  - The total is **`INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`**, with no value. Lineage gives
    "XSHG listing, 100 shares, `NO_ADMITTED_SOURCE`".
  - Still available: the A-share's quantity (100), its CNY basis, every cash balance in its own
    currency, and H's native value (HKD 40,000.00).
- **(c) Instead of (b), the account holds CNH 1,000.** The total is **`INSUFFICIENT_DATA` +
  `MISSING_FX_HISTORY`** (Rulings 1.4 and 1.5). Before `market-data/1.8` this would have been
  `LIMITED` with an unmeasurable weight.
- **(d) Both (a) and (b).** The total is `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`. In the
  priority order, `MISSING_PRICE_HISTORY` (8) outranks `STALE_DATA` (10), and lineage lists both.

#### Example V-2a (1.1): a split not yet applied in the ledger

The CP2 service's dry run reports `WOULD_APPEND` for a corroborated split missing from the ledger.
The valuation of the affected position is `INSUFFICIENT_DATA` + **`SOURCE_CONFLICT`** from the
ex-date (cause `SPLIT_NOT_APPLIED`). This is the `NOT_RECORDED` outcome of `market-data` Ruling
6.4a, so it takes the same code (**RULING 6.4a-perf**, confirming CP3a engineer choice 2).

- The quantity, which is pre-split, and the raw price, which is post-split, are in different units.
- No other code fits. `LEDGER_INCONSISTENT` is wrong: the ledger does not contradict itself.

#### Example V-3: Current mode

The portfolio holds H@XHKG, USD cash and HKD cash, with `R` = USD. Take `t` = 2025-04-02 14:30 UTC.

- Is `D` = 2025-04-02 eligible?
  - It is an HKEX session. The scheduled close, 16:10 Asia/Hong_Kong (`market-data/1.8`), is 08:10
    UTC, which is ≤ `t`.
  - It is an ECB fixing day. 16:00 Europe/Berlin is CEST in April, so 14:00 UTC ≤ `t`.
  - So **`D_c` = 2025-04-02**.
- Add a NYSE listing. Its close of 2025-04-02 is 16:00 EDT = 20:00 UTC > `t`, so 04-02 is not
  eligible, and **`D_c` = 2025-04-01**, with every input taken as of 04-01.

The "current" snapshot is therefore never priced from a US intraday quote, which was HG1 round 4
§7.6's defect.

---

## 2. Money and number representation (OI-8)

### RULING 2.1: Two tiers. Exact inside, rounded once at the edge.

- **Tier E (engine).** Every money amount, quantity, rate and return is an **exact rational**
  (`Fraction`), built from the ledger's decimals, the published price decimals and the ECB
  decimals.
  - Crosses are ratios (`market-data` 1.3).
  - Unit costs are ratios (`ledger-replay` 0.4.1).
  - There is **no intermediate rounding anywhere**, and **never a binary float**.
  - Every identity of §11 holds **exactly** in tier E.
- **Irrational results (1.1, rewritten).** These are annualization roots, the IRR, and Cariño's
  logarithms.
  - **The binding requirement is the presented value.** It is the `ROUND_HALF_UP` rounding, to
    Ruling 2.2's quantum, of the **exact mathematical result**.
  - **The method is conformant if it guarantees that value:**
    - **(a) Certified exact bracketing.** Integer or `Fraction` bisection gives a
      rational bracket `[lo, hi]` containing the exact result. It is narrowed until it contains
      no rounding boundary of the quantum.
      - This is always available for **annualization**: `Y` is rational (Ruling 7.1), so
        `(1+R)^(1/Y)` with `Y = p/q` is the `p`-th root of the exact `(1+R)^q`.
      - It is always available for the **IRR**: every `τ` is a ratio of day counts over `n`
        (Ruling 6.1), so with `y = g^(1/n)` the IRR function is a sum of integer powers of `y`.
      - This is the CP3a engineer's plan (tech plan §16.6). It needs no transcendental function.
    - **(b) `Decimal`**, context `prec = 50`, `ROUND_HALF_EVEN`, using `ln` and `exp`. These are
      correctly rounded under the General Decimal Arithmetic specification (MEMORY, §18 item 4).
      Power is computed as `exp(y × ln x)`, never `Decimal.power`. This is the method for Cariño's
      `κ` factors, which have no exact rational form. It is allowed elsewhere.
  - **An undecidable tie.** If after narrowing to a width of 10^−40 the bracket still contains a
    rounding boundary `b` (the exact result is `b`, or within 10^−40 of it), the presented value
    is `b` rounded half-up. Lineage records `PRESENTATION_TIE`. That is deterministic, and differs
    from the truth by at most 10^−40.
  - Method (a) and method (b) give the same presented value except in that case.
  - **(1.2) The two are equally conformant, and (b) is the product path for annualization (Q10).**
    - For a multi-year window, `Y = p/q` has `p` in the tens of thousands (for example 79/73,
      or 1,096-day windows). The exact `p`-th root bracket of `(1+R)^q` then needs integers of
      millions of bits. That is correct but costly, for no change in the presented value.
    - Method (b) with the tie rule meets the binding requirement. The tie test is whether
      `[v − 10^−40, v + 10^−40]` contains a rounding boundary.
    - "Preferred" in 1.1 is withdrawn.
    - Method (a) stays available, and is the natural fit where exponents stay small. A fixture
      tolerance (10^−10, Ruling 11.2) covers either.
    - **`Y = 1` is exact under either method**: the annualized value is the period value, with no
      transcendental step (Ruling 7.1).
- **Nothing computes from a tier-P value.** A presented value is an output, never an input. A
  later computation always starts again from tier E.

**Why.** Every reporting-currency amount is a ratio of ECB quotes, and almost never terminates
(`market-data` Example 1-A). Rounding inside would make each identity hold only approximately,
would make results depend on evaluation order, and would hide defects inside a rounding tolerance
(HG1 M1 RULING 4(ii)). Exact rationals make every identity checkable at zero tolerance.

**Rejected:**

- a fixed-precision `Decimal` for money (for example 28 digits). It would be deterministic, but it
  makes identities approximate and invites "fixing" a test by widening a tolerance;
- binary floats (PD-0025).

### RULING 2.2: Presented values (`MetricResult.value`), quantized once

| Quantity | Quantum | Mode |
|---|---|---|
| A derived money amount in currency `k` (any value involving a price, an FX rate, a division or an allocation) | 10^(−minor_unit(k)) | `ROUND_HALF_UP` (half away from zero) |
| A return, a return component, a weight, a share | 10^(−12), as a decimal fraction (0.0123 = 1.23 %) | `ROUND_HALF_UP` |
| A displayed rate (a cross, or the implied rate of `ledger-replay` 5A.7) | 10^(−6) | `ROUND_HALF_UP` |
| A recorded ledger fact or a sum of facts (a quantity, a recorded amount, a native cash balance, replay's terminating basis of whole lots) | **none**: it is presented exactly as the ledger implies | none |

- **Half away from zero, not half-even.** Values are never summed after rounding (Ruling 2.1), so
  half-even's one advantage, unbiased sums of rounded values, does not apply here. Half away from
  zero is what a person checking by hand expects (四舍五入), and what the euro-conversion rules
  prescribe for exact halves (MEMORY, §18 item 5). Ties occur only for terminating values. A
  non-terminating rational cannot sit exactly on a half.
- **A display precision coarser than the quantum** (for example 0.01 % on screen) is applied by
  the presentation layer to the tier-P value. Double rounding differs from a single rounding of the
  exact value only if the exact value lies within 0.5 × 10^(−12) of a display tie. That is a known
  and negligible limitation. **Decomposition views do not use the presentation layer's rounding**
  (Ruling 2.4).
- **Rejected:** quantizing returns to a display precision inside the engine (the HG1 round 4 §7.9
  defect of rounding inside the data layer), and per-surface choices.

**(1.12) The exponent of a presented value (review CP4-3).** The quantum of the table above is
also the presented **exponent**. Facts get the rule below.

1. **Derived money** in currency `k` is presented with exactly `minor_unit(k)` decimals:
   `2248.00`, `0.00`, `-3.50`, and JPY `5000`. That is Ruling 2.2 as built.
2. **A money fact is padded, never rounded.** A recorded amount, or a sum of recorded amounts, in
   currency `k` has an exact value `v`, which is a terminating decimal. Let `d(v)` be the number of
   decimals of its shortest exact form: the least `n ≥ 0` with `v × 10^n` an integer. It is
   presented with exactly **`max(minor_unit(k), d(v))`** decimals:
   - `2248` USD → `2248.00`; `1000` HKD → `1000.00`; `0` → `0.00`; `-3.5` → `-3.50`;
   - a recorded **`0.125` USD fee stays `0.125`**, because a fact is never rounded (Ruling 2.1).
     A fact with more decimals than the minor unit is shown with its own decimals. Ledger amounts
     may carry up to 24 (PD-0026);
   - JPY `5000` → `5000`. A recorded JPY `12.5` stays `12.5`.
3. **The recorded scale is not used.** `2248`, `2248.0` and `2248.0000` as recorded give the same
   presentation. A sum of facts has no single recorded scale, and a presentation that depended on
   how an input was typed would break P12. The presentation is a function of the exact value and
   the table only.
4. **A money fact in a currency missing from the table** is still a fact. It is presented in its
   shortest exact form with no padding. Its state is unchanged, and lineage carries the detail
   `CURRENCY_NO_MINOR_UNIT`.
   - Suppressing a known ledger fact would be wrong.
   - Only **derived** money in such a currency is `INSUFFICIENT_DATA` (Ruling 2.3).
5. **Which values are facts is decided by the view:**
   - **`NATIVE` view:** a recorded amount, or a sum of recorded amounts, is a fact (cash balances,
     receivable amounts, and replay's terminating basis of whole lots);
   - **`REPORTING` view:** every value is **derived**, including an amount already in `R`, which
     Rulings 1.2 and 1.3 translate at `X(R→R) = 1`. It is quantized by item 1.
   - So the two views agree whenever the fact has at most the minor unit's decimals, which is
     almost every cash balance. For a `0.125` USD fee in a USD portfolio, the native view shows
     the record, `0.125`, and the reporting view shows the presented `0.13`. That difference is the
     fact/derived distinction made visible, not an inconsistency. The exact value stays in the Proof
     Packet.
6. **Quantities and other non-money facts** keep their shortest exact form, with no padding.
7. **The exponent is presentation only.** It changes no value, state, reason, comparison or
   digest: `canonical_decimal` normalizes the exponent (review §33.2). A fixture compares values
   numerically, so `"20000"` and `"20000.00"` are the same assertion.

### RULING 2.3: The minor-unit table (reference data, versioned)

**(1.11) Table `minor-units/1.1`.** It is in force from `performance/1.11`.

| Currency | Minor unit (decimals) | Status |
|---|---|---|
| USD | 2 | CONFIRMED (ISO 4217) |
| HKD | 2 | CONFIRMED (ISO 4217) |
| CNY | 2 | CONFIRMED (ISO 4217) |
| EUR | 2 | CONFIRMED (ISO 4217) |
| CNH | 2 | DECLARED (not an ISO code; market convention follows CNY) |
| JPY | 0 | CONFIRMED (ISO 4217), listed only because the ECB publishes it |
| GBP, CHF, SGD, AUD, CAD | 2 | CONFIRMED (ISO 4217) |

**The confirmation record of every CONFIRMED row:**

- confirmed by the human product owner, 2026-10-02;
- against SIX's ISO 4217 List One (`list-one.xml`), published 2026-09-17, field `CcyMnrUnts`;
- recorded in PD-0037.

**Statuses:**

- **`CONFIRMED`**: checked against the publisher by the owner, with the record above.
- **`MEMORY`**: written from the Quant's memory, and not yet confirmed. Any `MEMORY` row is an
  open item of the convention.
- **`DECLARED`**: a Quant convention with no external publisher to confirm it against (CNH). It
  is not an open item. CNH aggregates are `INSUFFICIENT_DATA` in any case (`market-data/1.8`), and
  CNH is part of OQ-04b.

**The 1.0–1.10 record (`minor-units/1`).** The same currencies and minor units, with every ISO row
`MEMORY` and CNH `DECLARED`.

- The table is a versioned data file. Its version is recorded in every manifest that presents
  money.
- ~~The owner confirms the MEMORY rows against the ISO 4217 list maintained by SIX (§18 item
  1).~~ **(1.11) Done:** PD-0037. No `MEMORY` row remains.
- **(1.11) Table ids.**
  - A table id is `minor-units/<major>.<minor>`, and `minor-units/1` is read as
    `minor-units/1.0`.
  - **A new minor version** changes only status or provenance, and keeps every
    (currency, decimals) pair. It is value-equivalent to every other minor version of the same
    major.
  - **A new major version** adds or removes a currency, or changes a minor unit. A currency added
    later starts as `MEMORY` until the owner confirms it (PD-0037).
  - A fixture check that compares table ids accepts a **later minor version of the same major**,
    as Ruling 11.6 item 1 does for convention sets. It refuses a different major. (No fixture cites
    a table id today.)
- **A currency missing from the table fails closed.** Its derived money values are
  `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION` (detail `CURRENCY_NO_MINOR_UNIT`). The engine never
  defaults to 2.

### RULING 2.4: Decompositions. Removed + remaining = original, and displayed parts sum to the displayed whole.

1. **In tier E, every decomposition is exact:**
   - removed basis + remaining basis = original basis;
   - realized + remaining = proceeds and basis identities;
   - attribution lines sum to the gain (§9).

   No allocation rule is needed there, because nothing is rounded.
2. **Independently presented values** (each `MetricResult` on its own) are each quantized by
   Ruling 2.2. They reconcile within a stated tolerance, not exactly:
   ```
   | Σ_{i=1..k} p̂_i − T̂ |  ≤  (k + 1) / 2  quanta
   ```
   This bound follows from each `|p̂ − p| ≤ ½` quantum and `|T̂ − T| ≤ ½` quantum.
3. **A published decomposition object** is a total with its parts, such as a gain attribution, a
   basis split or a realized-gain line. The engine emits it with **apportioned display values**,
   computed by the largest-remainder method:
   - `T̂` = the total quantized by Ruling 2.2;
   - each part is first rounded **down** (toward −∞) to the quantum;
   - the shortfall `T̂ − Σ floor` (an integer number of quanta, between 0 and `k`) is given one
     quantum at a time to the parts with the largest remainders `p − floor(p)`;
   - ties go in the fixed line order of the decomposition's registry entry.

   **Properties:** the displayed parts sum to the displayed total **exactly**, as HG1 round 4 §4.4
   requires; each displayed part is within one quantum of its exact value; and the method is
   deterministic.
4. A surface that shows a decomposition shows the apportioned values for **every** line of it.
   The exact values sit in the Proof Packet. Apportionment is an engine output, so the rendered
   number is one the engine produced (HG1 M1 RC).
5. **Rejected:**
   - a "rounding difference" line, which is not an economic quantity;
   - a footnote "may not sum", which HG1 round 4 §4.4 rules out;
   - computing the total as the sum of rounded parts, which makes the total depend on how many
     lines a view shows.

### RULING 2.5: Relation to `ledger-replay` Ruling 0.4.6, and closure of OI-8

- **Replay's own emitted basis values are unchanged:** exact when terminating, otherwise
  `INSUFFICIENT_DATA` with `BASIS_NOT_EXACT`. They remain the ledger-state audit output, and the
  CP1 golden fixture stays valid.
- **CP3's metrics read replay's exact lot model, not its emitted values.** So a proportional basis
  of 200/3 USD is a presentable CP3 value (66.67, Ruling 2.2), not an insufficiency.
- Surfaces and the AI layer present CP3's cost-basis and gain metrics, not replay's raw basis
  output.
- **OI-8 is closed** by §2. Its two prerequisites now exist: the minor-unit table (2.3) and the
  allocation rule (2.4).

#### Example R-1: removed + remaining (USD)

One lot of 3 units for 100.00 USD. Sell 1 for 40.00.

- Tier E:
  - removed = 100/3;
  - remaining = 200/3;
  - realized = 40 − 100/3 = 20/3;
  - check: 100/3 + 200/3 = 100, exactly.
- Independently presented: removed **33.33**, remaining **66.67**, realized **6.67**.
- Basis decomposition object (total 100.00):
  - floors 33.33 + 66.66 = 99.99, so the shortfall is 1 quantum;
  - remainders: 0.00333… for removed and 0.00666… for remaining, so remaining gets the quantum;
  - result **33.33 + 66.67 = 100.00**.
- Proceeds object (total 40.00, a recorded fact):
  - floors 33.33 + 6.66 = 39.99, so the shortfall is 1;
  - realized has the larger remainder (0.00666… against 0.00333…), so it gets the quantum;
  - result **33.33 + 6.67 = 40.00**.

#### Example R-2: an attribution whose independently rounded lines do not sum

Example W's money attribution (§9) has these exact lines in USD: 1,800/7, −3,979/273, −100/273,
1,000/39, −9/7, −100/39, 0 and −80/7. The total is G = 9,850/39 = 252.5641…, so `T̂` = **252.56**.

- **Independently rounded:** 257.14, −14.58, −0.37, 25.64, −1.29, −2.56, 0.00, −11.43. These sum
  to **252.55**, which is within the (8 + 1)/2 bound but not equal.
- **Apportioned:**
  - floors are 257.14, −14.58, −0.37, 25.64, −1.29, −2.57, 0.00, −11.43, summing to 252.54;
  - the shortfall is 2 quanta;
  - the largest remainders are taxes (−2.5641 − (−2.57) = 0.005897) and FX (0.004908);
  - result: **257.14, −14.57, −0.37, 25.64, −1.29, −2.56, 0.00, −11.43**, summing to
    **252.56**.

The FX line shows −14.57 against an independent −14.58. Both are within one cent of the exact
−14.5751.

---

## 3. Cost basis, lot relief, realized and unrealized gain

### RULING 3.1: What the lot-relief method does and does not change

**Unaffected by the method, and computed now:**

- every value, every flow, the absolute gain `G` (§5), the TWR, the MWR and the whole attribution
  (§9). None of them reads a cost basis; they use values and flows only;
- the **total** realized plus unrealized gain of a position over its life, when all bases are
  known and nothing was transferred out. That is proceeds plus end value minus acquisition
  costs, whatever lots a sale is said to have used (Example L-1);
- every case `ledger-replay` Ruling 0.4 already finds determinate: one candidate lot, or whole
  moves.

**Changed by the method, and pending OD-P1:**

- the **split** of that total between realized and unrealized;
- the remaining basis of a position after a depletion from two or more lots;
- the basis that an internal partial transfer from two or more lots carries.

### 3.2: OWNER DECISION OD-P1. The lot-relief method. **DECIDED (PD-0035 §1): FIFO.**

> **(1.1) Decided.** The owner chose **A, FIFO** ("FIFO (Recommended)", PD-0035 §1).
>
> - **Ruling 3.3 is the method, ID `FIFO/1`**, recorded in every manifest that presents a realized
>   gain, unrealized gain or remaining basis.
> - Ruling 3.4 (average cost) stays specified, so a future change has a defined alternative. **It
>   is not used.**
> - **Caveat on every realized or unrealized figure** (P3): its meaning is "lots are relieved first
>   in, first out; this may differ from your broker's own lot records". The words are the design's.
> - **Where the method runs.** The PM ruled a single lot engine in `domain` (tech plan §16.14). So
>   FIFO is a mode of the one lot fold (recommendation PF-3). Its "none" mode stays exactly
>   `ledger-replay/1.3`, which is what the CP1 golden fixture asserts. Specifying the FIFO mode's
>   replay output (as `ledger-replay/1.4`) and its fixture values belongs to `cp3_golden` part 3
>   (lots), and is not done in 1.1.
> - The "until the owner decides" paragraph below is history.
>
> The text below is the 1.0 record of what was put to the owner.

PD-0021 §9 reserves this to the Quant. I am putting it to the owner because it changes
user-visible realized and unrealized figures and their match with the user's broker statements.
The launch users (Mainland China-based, PRD §4.3) mostly see average cost on Mainland and Hong
Kong statements, but per-lot FIFO on US statements (MEMORY, §18 item 6). Both methods below are
fully specified (Rulings 3.3 and 3.4), so whichever is chosen can be built and tested without
another ruling.

| Option | What it is | For | Against |
|---|---|---|---|
| **A. FIFO, portfolio-wide** (**recommended**) | Lots are relieved oldest acquisition date first. Lots acquired on the same date are relieved pro rata. | Keeps each lot's own acquisition-date FX in the reporting-currency basis (HG1 §7.3) with no pooling. Handles lots in different basis currencies (Southbound CNY lots beside HKD lots) without averaging across currencies. **Preserves information:** an unknown-basis lot taints only the sales that use it (Example L-3). Order-independent within a day. Matches US broker defaults. | Differs from average-cost statements for Mainland and HK holdings. |
| **B. Daily average cost, portfolio-wide** | Each position is one pool. A day's depletions relieve the pool's average, in every basis currency and in `R`. | Matches the average cost Mainland and HK brokers display. Simple to explain. | **One unknown-basis lot makes the whole pool unknown** until the position is closed (L-3). A native average across currencies is undefined, so mixed CNY/HKD positions get no native gain. Differs from US statements. |
| **C. Per-account method chosen by the user** (default A) | The user names the method each account's broker uses. | Matches each broker statement. | A new user setting (product scope; P7 does not apply, but it is still a setting). Portfolio totals mix methods. More to test. A candidate for V1.5. |

**Recommendation: A**, labelled "first in, first out; may differ from your broker's statement"
wherever a realized or unrealized figure appears (P3). V1 is not tax guidance (PRD §5.3, §15.3), so
no method is "correct for tax". The deciding arguments are information preservation and exact
per-lot FX.

**Until the owner decides:**

- every method-dependent value for a depletion from two or more lots stays as `ledger-replay/1.3`
  gives it: `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION`, detail `LOT_DEPLETION`;
- everything in Ruling 3.1's first list is computed;
- the manifest records `lot_relief: UNDECIDED`.

Once the owner decides, the chosen method's ID (`FIFO/1` or `AVCO/1`) is recorded in
`performance/1.1` and in every manifest. The CP3 fixture's method-keyed cases (L-1) then have one
expected value each. The CP1 fixture's V3 is a replay output (`ledger-replay/1.3`, method-free)
and is unchanged (Ruling 2.5).

### RULING 3.3: FIFO specification (applies if OD-P1 = A or C)

The lot model is `ledger-replay` 0.4.1, extended by Ruling 3.7. Each lot λ has:

- units `u_λ`;
- a unit cost `c_λ` (exact rational) in basis currency `k_λ`, or unknown;
- an **acquisition date `a_λ`**;
- a reporting-currency unit cost `c_R,λ` (Ruling 3.7), or a state.

For a position `(acct, ℓ)` and a day `d` with depleting quantity `q_dep > 0`:

1. **The candidate set** is that of `ledger-replay` 0.4.2: the lots at the end of `d − 1`,
   rescaled by a `SPLIT` dated `d`, plus every lot acquired on `d`, including carried lots arriving
   by an internal in-leg dated `d`.
2. **Order:** by `a_λ` ascending. Lots with **equal** `a_λ` form one group. A group is relieved
   **pro rata** to its lots' units, never in `ledger_seq` order.
3. **Walk the groups.** Relieve whole groups while the remaining need is at least the group's
   units. The first group that is not wholly needed gives each of its lots
   `need × u_λ / U_group` units. Each relieved portion carries `c_λ`, `k_λ`, `a_λ` and its
   `c_R,λ` state.
4. **Allocation to events.** Each depleting event `e` on `d` (`SELL`, external or internal
   `TRANSFER_OUT`) receives the fraction `q_e / q_dep` of **every** relieved portion.
   - A sale's relieved basis is its share.
   - An internal out-leg carries its share as lots, keeping `a_λ` and `c_R,λ`.
5. **Fractional lot units** may arise from pro rata relief. They are exact rationals and harmless.
   Only the position quantity's integrality matters, under `ledger-replay` §7.
6. **Preconditions** are those of `ledger-replay` 0.4.5. A flagged source (negative quantity,
   `LEDGER_INCONSISTENT`, split-unresolved) relieves nothing, and its out-legs inherit its cause.
   A same-day transfer cycle stays unresolved, as replay already does.

**Why "pro rata within a date".** The ledger has dates, not execution times (`ledger-replay`
0.4.2). Any fixed order among same-date lots would be an invented one, and `ledger_seq` is entry
order. Pro rata is symmetric, so entry order cannot change a basis.

**Why it is order-independent across the day.** Start-of-day lots all have `a_λ < d`, so they
are relieved before any same-day acquisition. That is what every plausible execution order gives
under FIFO (`ledger-replay` Example 0.4-D: 600 in every reading).

### RULING 3.3a (1.5): `FIFO/1` is the FIFO mode of the one lot fold (`ledger-replay/1.4` Ruling 0.5)

- **The normative definition** of `FIFO/1` is `ledger-replay/1.4` Ruling 0.5. Ruling 3.3 above is
  its summary; where the wording differs, Ruling 0.5 governs. The two agree on the candidate set,
  the order by acquisition date, pro rata within a date, the allocation to a day's events, and the
  preconditions.
- **Relief is per position `(account, listing)`** (0.5.2). "FIFO, portfolio-wide" in §3.2 means the
  same method in every account, not one pool across accounts.
- **What CP3 reads** (Ruling 2.5): the exact lot book and relief records of 0.5.14. Each lot has:
  - an identity and a carry history;
  - an acquisition date `a_λ`;
  - a **date kind**: `TRADE` for a `BUY`, `ENTRY` for an `OPENING_POSITION` or an external
    `TRANSFER_IN`. A carried lot keeps its origin's kind;
  - a basis currency and a unit cost, or unknown.
- **Ruling 3.7's table in these terms:**
  - `TRADE`: `c_R,λ = c_λ × X(k_λ→R, a_λ)`;
  - `ENTRY` with `k_λ = R`: `c_R,λ = c_λ`;
  - `ENTRY` with `k_λ ≠ R`: `INSUFFICIENT_DATA` + `MISSING_COST_BASIS`, detail
    `ACQUISITION_DATE_UNKNOWN`;
  - unknown: `MISSING_COST_BASIS`, detail `UNKNOWN_BASIS`.

  A carried lot's `c_R,λ` is its origin's, because `a_λ`, the date kind and `k_λ` are unchanged.
- **What stays unresolved** under `FIFO/1` (0.5.9): a non-integral split, a same-day transfer
  cycle, and what inherits them. A value from such a relief record takes the record's reason
  (Ruling 3.8 (1.5)).

### RULING 3.4: Daily average-cost specification (applies if OD-P1 = B or C)

1. Each position has one **pool**:
   - units `U`;
   - per basis currency `k`, a native basis `B_k`;
   - a reporting-currency basis `B_R` (Ruling 3.7), or its state;
   - a flag for any unknown-basis units.
2. **On day `d`:**
   - the pool′ is the start pool (units rescaled by a split; bases unchanged) plus every
     acquisition dated `d` (including carried-in pool shares);
   - if `q_dep > 0`, let `φ = q_dep / U′`;
   - each depleting event `e` removes `φ × (q_e / q_dep)` of **every** component (`U`, each
     `B_k`, `B_R`);
   - an internal out-leg carries its removed components to the receiver's pool.
3. **Unknown basis.** If pool′ holds any unknown-basis units, every removed basis and the
   remaining basis are **unknown** (`MISSING_COST_BASIS`). The flag clears only when the position
   ends a day at 0.
4. The average is over the whole day's candidate set, so it does not depend on intra-day order.
   A broker's true moving average would, which is a known difference.

### RULING 3.5: Rules common to every method

- **Splits** rescale lots (FIFO) or pool units (AVCO). Total native basis, every `c_R,λ × u_λ`, and
  every acquisition date are unchanged (`ledger-replay` 0.4.1).
- **Unknown-basis units** are relieved like any other units.
- **A non-terminating value is not a problem** (§2).
- **The determinate cases of `ledger-replay` 0.4** give the same value under every method, by
  construction. That is checked in the fixture.

### RULING 3.6: Transaction costs are not capitalized into basis

- A lot's basis is the acquiring event's recorded amount (`BUY.amount`) or its `cost_basis`, as
  recorded. A sale's proceeds are `SELL.amount` as recorded.
- A separately recorded `FEE` or `TAX`, including one carrying a `listing_id` (commission, stamp
  duty, levies), is **never** added to a basis or deducted from proceeds. It is reported in the
  fees or taxes line (§8) and in the position's attributed costs (§9).
- If the source's consideration already includes the commission and it is recorded that way, the
  commission is in the basis because the recorded amount says so. Recording it again as a `FEE`
  would double-count, the same pattern as `ledger-replay` Rulings 4.3 and 5A.5.

**Why.** Nothing links a `FEE` or `TAX` to the trade it belongs to (finding F9). Capitalizing
would need that link, and inferring it would be a guess: several trades can share a listing and a
date. The choice moves no value except the realized/unrealized split, and the fees line makes the
cost visible. The identity "unrealized gain + fees and taxes lines = `G`" still holds (Example
L-4).

**Rejected:**

- capitalization by a heuristic link on (account, listing, date). It is ambiguous, and it would
  fabricate basis (PRD §9.3);
- capitalizing account-level fees by allocation. Same reason.

Capitalization becomes possible once a link exists (recommendation PF-2, §17). Adopting it then
would change user-visible gains, so it would come back to the owner.

### RULING 3.7: The reporting-currency basis is translated at the acquisition date's FX (OI-1, OI-6, HG1 §7.3)

`c_R,λ = c_λ × X(k_λ→R, a_λ)`, fixed when the lot is created and never re-translated. The
acquisition date `a_λ` depends on how the lot arose:

| Acquiring event | `a_λ` | `c_R,λ` |
|---|---|---|
| `BUY` | `event_date` | `amount / q` × `X(event.currency→R, event_date)`. The event currency is the cash actually paid, so CNY for Southbound. **Never** the rate implied by the user's own `CURRENCY_CONVERSION` (OI-6, `ledger-replay` 5A.7). |
| internal `TRANSFER_IN` (a carried lot) | the **source lot's** `a_λ` | the source lot's `c_R,λ`, unchanged |
| external `TRANSFER_IN` with `cost_basis`, or `OPENING_POSITION` with `cost_basis` | `event_date`, used for FIFO order only | if `k_λ = R`: known, with no FX needed. Otherwise **`INSUFFICIENT_DATA` + `MISSING_COST_BASIS`**, detail `ACQUISITION_DATE_UNKNOWN`. The native basis stays known. |
| either, without `cost_basis` | `event_date`, used for FIFO order only | unknown (`MISSING_COST_BASIS`), as is the native basis |

- **The rate's state is the lot's state for ever.** A lot bought on a date whose fixing is 2–4
  fixings stale has a `LIMITED` + `STALE_DATA` reporting-currency basis. A CNH-paid lot (offshore
  Northbound) has an `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` reporting-currency basis.

**Why the transfer and snapshot rule is strict.** The `cost_basis` on those events is the user's
historical cost. Its date is not recorded. The event date is when the lot entered **this**
portfolio, not when it was bought. Translating at the event-date rate would give the lot a
reporting-currency basis whose FX component is invented, which PRD §9.3 forbids ("never fabricate
cost basis"). This is the case PRD §9.3 anticipates: without transaction history, investor-specific
unrealized gain is unavailable or limited. The native gain stays available.

- **Rejected:** translation at the transfer or snapshot date with a `LIMITED` caveat. The caveat
  would change the conclusion, and the remedy is a recorded date (recommendation PF-1, §17).

### RULING 3.7a (1.6; PD-0036 §1): A recorded acquisition date (`acquired_on`)

A lot of kind **`RECORDED`** (`ledger-replay/1.5` Ruling 0.6) is an opening or external transfer-in
lot whose event carries `acquired_on`. It has `a_λ = acquired_on`.

1. **Its reporting-currency unit cost:** `c_R,λ = c_λ × X(k_λ→R, a_λ)`. This is the `BUY` row's rule
   at the recorded date, so **`ACQUISITION_DATE_UNKNOWN` does not arise** for it.
2. **The rate at `a_λ`** follows `market-data` Ruling 1.6 exactly, as for any date:
   - the fixing `u(a_λ)`, carried over weekends and TARGET closing days with `m = 0`;
   - `STALE` / `LIMITED` for 1 to 4 missed fixings;
   - CNH (Ruling 1.4) has no rate.

   As Ruling 3.7 says, that state is the lot's state for ever.
3. **A date before the FX coverage of `M`.** When `M` holds no observation of the pair at or before
   `a_λ`, the reporting-currency basis is `INSUFFICIENT_DATA` + **`MISSING_FX_HISTORY`**. The remedy
   is to obtain the earlier fixings. The ECB publishes from 1999, so this is a gap in `M`, not in
   the world.
   - If the ECB calendar `C_ECB` also does not cover the date, lineage carries
     `CALENDAR_COVERAGE_GAP` as well. The reason is still `MISSING_FX_HISTORY`, because Ruling 1.5
     takes the first cause at that level that has a code.
   - When observations exist but the calendar does not cover `(u(a_λ), a_λ]`, `market-data` 1.6's
     last row applies: `INSUFFICIENT_DATA` with no code, cause `CALENDAR_COVERAGE_GAP`.
4. **`k_λ = R`:** no rate is needed, so the basis is known **whatever the date**, including one before
   any coverage.
5. **No basis (`cost_basis` absent):** unknown (`MISSING_COST_BASIS`, `UNKNOWN_BASIS`), as before.
   The date still orders FIFO.
6. **Nothing else reads `acquired_on`:**
   - it is not a flow date: an external transfer-in is still an in-kind flow at its `event_date`
     close (Ruling 4.1);
   - it does not change the inception base or any window (Ruling 4.4);
   - it moves no value into or out of any return.

   It only sets the FIFO order and the acquisition-date FX of the lot's cost.
7. **Label (meaning; the design writes the words):** a gain built on a `RECORDED` lot carries "cost
   and acquisition date as recorded by you". That is part of the existing broker-difference caveat
   (P3, P9).

**Why.** PRD §8.3 and HG1 round 4 §7.3 translate cost at the transaction date. The recorded date is
the transaction date, as the user states it. Ruling 3.7's strict refusal existed only because that
date was missing, so recording it removes the reason for the refusal. A rate the market data does
not hold is missing data, not an unknown date, so it takes the missing-data code.

**Rejected:**

- the earliest fixing in `M` for a date before coverage (look-ahead, `market-data` 1.6);
- `ACQUISITION_DATE_UNKNOWN` for a date before coverage. The date is known, and that code would point
  the user at the wrong remedy (Ruling 1.5's rationale).

### RULING 3.8: Realized gain

For each `SELL` `e` dated `d`, with proceeds `A_e` in currency `c_e` and its relieved portions:

```
RG_native(e) = A_e − Σ relieved native basis          only if every portion's k_λ = c_e
RG_R(e)      = A_e × X(c_e→R, d) − Σ relieved (units × c_R,λ)
```

- **Native gain for mixed currencies.** When portions are in more than one basis currency, or in
  one that differs from `c_e`, the native gain is not a defined quantity. It is
  `INSUFFICIENT_DATA` + `UNSUPPORTED_ASSET`, detail `MIXED_CURRENCY_BASIS`: the position is outside
  the domain of a native-currency gain (HG1 round 4 §6). `RG_R` is unaffected.
- **States.** Any relieved portion that is unknown gives `MISSING_COST_BASIS`. Any multi-lot relief
  while OD-P1 is open gives `UNRESOLVED_CONVENTION`. Any portion whose `c_R,λ` is insufficient
  gives that portion's reason (in `R` only). The proceeds rate's state joins.
- **An external `TRANSFER_OUT` relieves lots but realizes nothing.** The units leave the
  portfolio at market value as an outflow (§4). They are not sold.
- **An internal `TRANSFER_OUT`** carries its share (Rulings 3.3 and 3.4).
- **Window aggregation:** `RG_R(B, E]` = Σ over sales dated in `(B, E]` (Ruling 3.10).

**(1.5) States, completed.** The relieved portions are the sale's relief record (`ledger-replay/1.4`
0.5.5).

1. **Suppressed units.** Take a `SELL` dated `d` whose relief record holds units suppressed on `d`.
   Either the sale's own position is suppressed on `d` (`market-data` Rulings 6.4 and 6.4a), or a
   portion belongs to a lot tainted on `d` (6.4c; Ruling 1.1a). Then `RG_native` and `RG_R` are
   `INSUFFICIENT_DATA` + **`SOURCE_CONFLICT`**, with the suppression's cause in lineage
   (`SPLIT_SUPPRESSION_CARRIED` for a tainted portion).
   - **Why.** The ledger's quantity and the market's units disagree there. The relief proportion,
     and so the relieved basis, may be apportioned in the wrong unit system. For example, 40 units
     moved after an unrecorded 4:1 split are either 40 pre-split units (basis 3,200) or 40
     post-split units (basis 800). Before 1.5 this gain would have been presented `AVAILABLE`.
2. **A withheld relief record.** If replay gives the relief record a state (flagged position,
   opaque lot, same-day cycle; `ledger-replay/1.4` 0.5.9), the realized gain takes that reason and
   those details.
3. **The mixed-currency test is over known-basis portions only.** An unknown portion contributes
   `MISSING_COST_BASIS` instead. When both occur, both causes are in lineage, and the reason follows
   Ruling 1.5: `UNSUPPORTED_ASSET` before `MISSING_COST_BASIS`.
4. **Detail names, fixed:** `UNKNOWN_BASIS` (an unknown portion); `ACQUISITION_DATE_UNKNOWN` (an
   `ENTRY` portion whose `k_λ ≠ R`, in `R` only); `MIXED_CURRENCY_BASIS` (native only).

### RULING 3.9: Unrealized gain at `D`

For a position with remaining lots at `D`:

```
UG_native(D) = MV_c(D) − Σ remaining native basis      only if every remaining k_λ = c(ℓ)
UG_R(D)      = MV_R(D) − Σ remaining (u_λ × c_R,λ)
```

- States combine as in Ruling 3.8, plus the valuation's state (Ruling 1.1).
- A mixed-currency position (Southbound CNY lots on an HKD listing) has no native unrealized gain
  (`UNSUPPORTED_ASSET`, `MIXED_CURRENCY_BASIS`). Its `UG_R` is defined.
- **Percentage forms**, if shown: `UG_R / Σ remaining basis_R` and `RG_R / Σ relieved basis_R`.
  The denominator is basis (§10).

### RULING 3.9a (1.5): Remaining basis, a metric (`basis.remaining`)

- **Native view.** Per basis currency `k`, Σ `u_λ c_λ` over the position's end-of-day lot book. It
  is listed per currency and never summed across currencies. A Southbound position's CNY lots give
  a CNY amount, even on an HKD listing.
- **Reporting view.** Σ `u_λ c_R,λ` (Ruling 3.7, as restated in 3.3a).
- **States:**
  - any unknown lot: `INSUFFICIENT_DATA` + `MISSING_COST_BASIS`, detail `UNKNOWN_BASIS`, in both
    views (`ledger-replay` 6.4);
  - in `R` only: any lot whose `c_R,λ` is insufficient takes that lot's reason (for example
    `ACQUISITION_DATE_UNKNOWN`). A `LIMITED` rate gives `LIMITED`;
  - a flagged or basis-unresolved position (`ledger-replay/1.4` 0.5.9): replay's reason, in both
    views;
  - **suppression:** on any day the position's valuation is suppressed by `market-data` 6.4, 6.4a
    or 6.4c (`SOURCE_CONFLICT`), the remaining basis is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`
    in both views.
- **Why suppress the basis.** The position's units are in doubt, so any relief on such a day may
  have been apportioned in the wrong units (Ruling 3.8 (1.5) item 1). A basis presented beside a
  suppressed value also invites the subtraction that the suppression forbids. **Known cost:** a
  basis that no relief has touched since the ex-date is correct, and it is still withheld. That is
  conservative.
- **Presentation:** a derived money amount (Ruling 2.2). The unrealized gain (Ruling 3.9) already
  takes the valuation's state.

### RULING 3.10: Aggregates of realized and unrealized gain, and partly known basis

- **A position's basis with some unknown units** is unknown (`ledger-replay` 6.4). Its unrealized
  gain is `INSUFFICIENT_DATA` + `MISSING_COST_BASIS`. The known part is never presented as the
  position's basis or gain.
- **The portfolio's unrealized gain at `D`** sums the positions whose `UG_R` is available or
  limited. Then:
  - if any non-zero position is **unvalued** (no `MV_R`), the aggregate is `INSUFFICIENT_DATA`
    with that position's reason, because the excluded weight cannot be measured (Ruling 1.4);
  - otherwise, if some positions are excluded for `MISSING_COST_BASIS`, `UNRESOLVED_CONVENTION`,
    `UNSUPPORTED_ASSET` or `MISSING_FX_HISTORY` (in their basis only), the aggregate is
    **`LIMITED`**, with the reason chosen by Ruling 1.5 and the **excluded weight stated**
    beside it: Σ |MV_R of excluded positions| / Σ |MV_R of all positions with non-zero
    quantity| (HG1 round 4 §6 R1);
  - if every position is excluded, the aggregate is `INSUFFICIENT_DATA`.

  HG1 R1 names `MISSING_COST_BASIS` and `MISSING_FX_HISTORY`. **Extending the same R1 rule to
  `UNRESOLVED_CONVENTION` and `UNSUPPORTED_ASSET` in gain aggregates is a ruling made here.** The
  logic is identical: the excluded part is measurable and stated.
- **The realized gain over a window** sums the sales in `(B, E]`. Excluded sales make it
  `LIMITED`, with the excluded weight = Σ |proceeds_R of excluded sales| / Σ |proceeds_R of all
  sales in the window|. If every sale is excluded, it is `INSUFFICIENT_DATA`. If no sale is dated
  in the window, the realized gain is **0, `AVAILABLE`**: a fact, not missing data.
- **No threshold** turns a stated-weight `LIMITED` into `INSUFFICIENT_DATA`. HG1 R1 requires the
  weight to be stated, not bounded. This is a known limitation: a `LIMITED` aggregate excluding
  90 % is legal, and its stated weight carries the caveat (P3).

**(1.5) Aggregates, completed.**

1. **Realized gain over a window.** An *excluded sale* is a sale whose `RG_R` is
   `INSUFFICIENT_DATA`.
   - It makes the aggregate `LIMITED`, with the excluded weight by proceeds, when its reason is
     `MISSING_COST_BASIS`, `UNRESOLVED_CONVENTION`, `SOURCE_CONFLICT`, or `MISSING_FX_HISTORY` in a
     lot's basis. The proceeds are a recorded cash fact, so the weight is measurable.
   - It makes the aggregate `INSUFFICIENT_DATA` when its reason is `LEDGER_INCONSISTENT` or
     `NOT_RECONSTRUCTABLE`. The set of sales and lots is then itself in doubt (Ruling 1.5's
     rationale).
   - It also makes the aggregate `INSUFFICIENT_DATA` when its `proceeds_R` cannot be computed (for
     example proceeds in CNH, or a missing rate). Its weight cannot then be stated (HG1 R1).
2. **The reason of a `LIMITED` aggregate** is chosen by Ruling 1.5 among the excluded items'
   reasons.
3. **Weights** are gross, presented to the 10^−12 quantum (Ruling 2.2), and given as an exact
   fraction in the fixture.

### 3.11: Not ruled here: fractional splits

The fractional-split convention stays reserved (`ledger-replay` §7, OI-4; PD-0024 §5). CP3
consumes replay's `UNRESOLVED_CONVENTION` (split fraction) state for the quantity. Valuation and
everything downstream become `INSUFFICIENT_DATA` with that reason. The candidate recorded in
`ledger-replay` §7 (apply the ratio exactly; cash in lieu as a separate `SELL`) remains the
starting point for a later ruling. It changes user-visible quantities, so I would put it to the
owner. It is not needed for CP3's exit.

#### Example L-1: two lots, both methods, and method independence (CP1 fixture V3: A3, MSFT, USD)

Events: X4 `BUY` 5 for 2,000 on 2025-05-05 (`c` = 400). X10 `BUY` 5 for 2,100 on 2025-06-03
(`c` = 420). X11 `SELL` 4 for 1,720 on 2025-06-10.

| | Relieved | Realized | Remaining basis |
|---|---|---|---|
| Undecided (now) | n/a | `INSUFFICIENT_DATA`, `UNRESOLVED_CONVENTION`, `LOT_DEPLETION` | the same |
| FIFO | 4 × 400 = 1,600 | 1,720 − 1,600 = **120** | 1 × 400 + 5 × 420 = **2,500** |
| AVCO | 4 × 4,100/10 = 1,640 | 1,720 − 1,640 = **80** | 6 × 410 = **2,460** |

**Method independence.** For any later price `P` of the 6 remaining units:

- FIFO: realized + unrealized = 120 + (6P − 2,500) = **6P − 2,380**;
- AVCO: 80 + (6P − 2,460) = **6P − 2,380**;
- proceeds + end value − total cost = 1,720 + 6P − 4,100 = **6P − 2,380**.

The identity checked in the fixture is `RG + UG = proceeds + MV − Σ costs` (I-7).

#### Example L-2: HKD lots, USD reporting, transaction-date FX

Listing H (HKD), reporting USD. FX (hypothetical ECB):

- d1: 1.0800 / 8.4000, so `X` = 9/70;
- d2: 1.0800 / 8.4240, so `X` = 5/39;
- d3: 1.0880 / 8.5000 = **16/125** (7.8125 HKD per USD).

Events: d1 `BUY` 100 for 3,900 HKD. d2 `BUY` 100 for 4,100 HKD. d3 `SELL` 150 for 6,300 HKD.
Proceeds in USD = 6,300 × 16/125 = **4,032/5 = 806.40**.

| | Relieved, native | Relieved, USD (each lot at its own date's FX) | `RG_native` | `RG_R` (exact → presented) | Remaining |
|---|---|---|---|---|---|
| FIFO | 3,900 + 2,050 = 5,950 | 3,900 × 9/70 + 2,050 × 5/39 = 208,640/273 = 764.2490… | **350 HKD** | 4,032/5 − 208,640/273 = 57,536/1,365 → **42.15** | 50 units, 2,050 HKD, 10,250/39 → **262.82** USD |
| AVCO | 8,000 × 3/4 = 6,000 | (280,390/273) × 3/4 = 140,195/182 = 770.3021… | **300 HKD** | 32,849/910 → **36.10** | 50 units, 2,000 HKD, 140,195/546 → **256.77** USD |

Method-independence check: `RG_R` − remaining basis_R = −301,214/1,365 under both. (FIFO:
57,536/1,365 − 10,250/39 = 57,536/1,365 − 358,750/1,365 = −301,214/1,365. AVCO:
32,849/910 − 140,195/546 gives the same value over the common denominator 2,730.)

#### Example L-3: an unknown-basis lot (why FIFO preserves information)

- Day 1: external `TRANSFER_IN` of 10 U, with no `cost_basis`.
- Day 2: `BUY` 10 U for 1,000 USD.
- Day 3: `SELL` 10 for 1,200.
- At `D`, the price is 110.

| | Realized (day 3) | Remaining | Unrealized at `D` |
|---|---|---|---|
| Undecided | `UNRESOLVED_CONVENTION` (two lots; `ledger-replay` 0.4.4 (b)) | unresolved | `UNRESOLVED_CONVENTION` |
| FIFO | relieves the unknown lot: **`MISSING_COST_BASIS`** | 10 at 1,000, known | 1,100 − 1,000 = **100**, `AVAILABLE` |
| AVCO | the pool holds unknown units: **`MISSING_COST_BASIS`** | unknown | **`MISSING_COST_BASIS`**, until the position ends a day at 0 |

#### Example L-4: a fee is not capitalized, and the gain identity still holds

- Day 1: `DEPOSIT` 1,005 USD; `BUY` 100 U for 1,000; `FEE` 5 with `listing_id` U.
- The close is 10.20.

Results:

- **Basis** = 1,000 (Ruling 3.6). Unrealized gain = 1,020 − 1,000 = **20**. The fees line is
  **−5**.
- **`G`** = V₁ − V₀ − flows = 1,020 − 0 − 1,005 = **15** = 20 − 5.
- **TWR for day 1** = 1,020 / 1,005 − 1 = 15/1,005 = **1/67** = 0.014925373134…, presented
  **0.014925373134**.

---

## 4. Cash flows: classification and timing

### RULING 4.1: Classification at portfolio level

| Ledger event | Class | Enters `G` and returns as |
|---|---|---|
| `DEPOSIT`; external cash `TRANSFER_IN` | **external inflow, cash** (`I^C`) | a flow, not a gain (PRD §9.6) |
| `WITHDRAWAL`; external cash `TRANSFER_OUT` | **external outflow, cash** (`O`) | a flow |
| external security `TRANSFER_IN` | **external inflow, in kind** (`I^K`), valued `q × P(ℓ, d) × X(c(ℓ)→R, d)` | a flow (`ledger-replay` 6.1) |
| external security `TRANSFER_OUT` | **external outflow, in kind** (`O`), valued the same way | a flow |
| internal transfers, either form | **none**: neutral (`ledger-replay` 6.1) | nothing at portfolio level |
| `BUY`, `SELL` | internal exchange | price effect (trade result, §9) |
| `CURRENCY_CONVERSION` | internal exchange (`ledger-replay` 5A.5) | conversion result (§8.5) |
| `DIVIDEND`, `INTEREST` | **income** | income line (§8) |
| `FEE` | **cost** | fees line |
| `TAX` | **cost** | taxes line |
| `INTEREST_CHARGED` | **cost** (`ledger-replay` 5.3) | financing-costs line (§8.4) |
| `SPLIT` | none | nothing (value is continuous; `market-data` Example 2-A) |
| `OPENING_POSITION`, `OPENING_CASH` | **not a flow**: the snapshot origin (§8 of `ledger-replay`) | the base value `V_S` (Ruling 4.4) |
| `REVERSAL` | removes its target at every `D` (`ledger-replay` 2.1) | its target never happened |

At **account** scope (Ruling 4.5), internal transfers are flows of the account: cash legs are
`I^C`/`O`, and security legs are `I^K`/`O` valued at the close.

### RULING 4.2: Timing within the day. Cash inflows at the start; everything else at the end.

For a calendar day `D`:

- **cash inflows** (`I^C_D`) are available from the **start** of `D`;
- **cash outflows** and **all in-kind flows** (`O_D`, `I^K_D`) happen at the **end** of `D`, valued
  at `D`'s close and fixing.

**Why this asymmetry.** It is the only rule under which the two routine same-day patterns come out
right with end-of-day valuations and trade-date accounting:

- **Deposit, then buy the same day** (Example W, day 1). The money must be in the base before it is
  invested. With an end-of-day inflow, a new portfolio's first day has a base of 0, and its return
  is undefined.
- **Sell, then withdraw the same day.** The proceeds exist only after the sale. A start-of-day
  outflow takes them out of a base that never held them. With V₀ = 100, a sale for 105 and a
  withdrawal of 105, the start-of-day rule gives 0 / (100 − 105) − 1 = **−100 %**. The true day
  return is **+5 %**, which the end-of-day rule gives: (0 + 105) / 100 − 1.
- **In-kind transfers** are valued at the event date's **close** (`ledger-replay` 6.1). At the end
  of the day they carry no price movement for that day, which is consistent with a close
  valuation.

GIPS requires a consistent treatment of external flows. It does not prescribe one timing (MEMORY,
§18 item 7). This rule is consistent and written down.

**Rejected:**

- **all flows at the start of the day** (breaks sell-then-withdraw);
- **all flows at the end of the day** (breaks deposit-then-buy, and a new portfolio's first day);
- **mid-day weighting** (Modified Dietz within a day), which needs intra-day times the ledger does
  not hold.

**Known limitation:** a deposit made after the close and not invested dilutes that day's return
slightly. The ledger carries no time of day.

### RULING 4.3: Flows in a foreign currency, and in kind

- A cash flow of `a` in currency `c` dated `d` is `a × X(c→R, d)`, at the fixing `u(d)`. It is
  never translated at the user's own conversion rate (`ledger-replay` 5A.7) or at any other date's
  rate (PRD §8.3).
- An in-kind flow is `q × P(ℓ, d) × X(c(ℓ)→R, d)`.
- **States propagate.** A flow that cannot be translated (CNH, missing FX) or valued (no price)
  makes every return over a window containing it `INSUFFICIENT_DATA` with that reason. A `LIMITED`
  rate makes those returns `LIMITED`.
- **(1.3; review CP3-1) A split suppression reaches in-kind flows.** An in-kind flow dated `d` is
  `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` when its units are suppressed on `d` (`market-data`
  Rulings 6.4, 6.4a and 6.4c). That means units from a position suppressed on `d`, or units of a
  tainted lot. Its quantity and the raw price are then in different units.
  - So the TWR **and `G`** over any window containing that flow are `INSUFFICIENT_DATA`.
  - `G` reads the flows, so it cannot stay `AVAILABLE` beside a flow valued in mixed units.
  - This also applies to an internal security transfer valued as a flow at account scope.

### RULING 4.4: The snapshot origin and inception

- Opening events are not flows. A snapshot account's history starts at the end of its snapshot
  date `S`, with value `V_S`.
- **The portfolio's inception base date `I₀`** is:
  - the latest snapshot date `S` among its accounts, if any account has one. Before it the
    portfolio is not reconstructable (`ledger-replay` 8.1);
  - otherwise, the day before its earliest event, when the value is 0.
- A window `(B, E]` is valid only if `B ≥ I₀` (Ruling 5.4).

### RULING 4.5: Account scope

Every formula in §5–§9 applies to one account, with Ruling 4.1's account-level classes. The sum
of account-level gains equals the portfolio gain, because internal flows cancel. The account-level
**returns** do not combine into the portfolio return by any weighted sum. That is expected, and no
surface may imply otherwise.

---

## 5. Time-weighted return

### RULING 5.1: Definition: daily-linked, valued at the end of each calendar day

For each calendar day `D` in `(B, E]`, all values in `R` (tier E):

```
V_D  = TV_R(D)                                   (Ruling 1.4)
I^C_D = Σ cash inflows dated D           I^K_D = Σ in-kind inflows dated D       O_D = Σ outflows dated D
β_D  = V_{D−1} + I^C_D                           the day's capital base
r_D  = (V_D + O_D − I^K_D) / β_D − 1             the day's return
g_D  = V_D + O_D − I^K_D − β_D                   the day's investment gain  ( r_D = g_D / β_D )

TWR(B, E] = Π_{D=B+1}^{E} (1 + r_D) − 1
G(B, E]   = Σ_D g_D = V_E − V_B − (Σ I^C + Σ I^K − Σ O)        the absolute gain (money), exact
```

- **The grid is calendar days.** On a day when no input changes (a weekend, a holiday everywhere),
  `r_D = 0` exactly, because prices are those of `s(D)` and the fixing is `u(D)`. A calendar-day
  grid needs no "portfolio calendar" across three markets.
- **"Percentage return" in PRD §15.1 is this TWR.** No third percentage figure (such as a simple
  `G / V_B`) is defined. A simple return is wrong whenever flows occur (HG1 round 4 §7.4).
- **`G` is the absolute gain/loss** of PRD §15.1. It is the only money gain over a window. It
  includes FX, income and costs. It does not depend on the lot method. **It is never derived from
  a TWR** (HG1 round 4 §7.4).

### RULING 5.2: Which valuations the TWR actually needs (telescoping)

On a day with no external flow, `1 + r_D = V_D / V_{D−1}`. So a run of flow-free days collapses to
the ratio of its end values. With flow days `D₁ < … < D_k` in `(B, E]`:

```
1 + TWR = [V_{D₁−1} / V_B] × Π_j { (V_{D_j} + O_{D_j} − I^K_{D_j}) / (V_{D_j−1} + I^C_{D_j}) × [V_{D_{j+1}−1} / V_{D_j}] }
```

The last bracket uses `V_E` for `j = k`, and a bracket over an empty run is 1.

**(1.2) An empty run (Q4).** A run is empty when a flow day directly follows the previous boundary
(`D_{j+1} − 1 = D_j`, or `D₁ − 1 = B`). The run is then a ratio of a value to itself. By
definition it is **1, with no factor recorded and no lineage**. In particular it is **not**
`ZERO_CAPITAL_RUN`, even when that value is 0: no day passed in it. `ZERO_CAPITAL_RUN` is only for
a non-empty run, or a flow day, whose own numerator and denominator are both 0 (Ruling 5.3).

- **The TWR's inputs are exactly:** `V_B`, `V_E`, and for each flow day `D_j`, both `V_{D_j − 1}`
  and `V_{D_j}`, plus the flows themselves.
- **A valuation on any other day is not an input to the TWR.** Its being `INSUFFICIENT_DATA` (for
  example a holding's price stale for 5 or more sessions in mid-window, with no flow at either
  end) **does not affect the TWR**. It does affect the attribution, which needs every day (Ruling
  9.5).
- Engines compute the segment form. When every daily value exists, the daily product must equal
  it **exactly** (identity I-2, §11).

### RULING 5.3: A base that is zero or negative

- **`0 / 0` is 1.** A segment or day with denominator 0 and numerator 0 had no capital at risk.
  Its factor is **1**, with lineage `ZERO_CAPITAL_RUN`. For example, the days before a new
  portfolio's first deposit, or a fully withdrawn portfolio waiting for new money. The window
  stays as it is.
- **Any other denominator ≤ 0 makes the TWR `INSUFFICIENT_DATA`** for every window containing it.
  The reason is none. The detail is `NON_POSITIVE_BASE`, and lineage gives the day and the cash
  balances that made the base non-positive.

  The routine cause is a purchase recorded before its funding deposit (`ledger-replay` Example
  1-B: `BUY` on 01-08, `DEPOSIT` on 01-09). Trade-date cash is then negative, and the day's base
  is 0 or below. The MWR is unaffected (§6), and so is `G`.

- **(1.1) A negative factor makes the TWR `INSUFFICIENT_DATA` too.** A positive denominator with
  a **negative** numerator means the portfolio's value fell below zero: liabilities exceeded
  assets. The result is no reason and detail **`NEGATIVE_VALUE`**. That is leverage, which V1 does
  not model (PD-0024 §3), and in V1 it arises only from an incomplete ledger.
  - A factor of exactly **0** (a total loss) is a real result: TWR = −1, `AVAILABLE`. Annualization
    then refuses it (`TOTAL_LOSS`, Ruling 7.2).
  - So a presented TWR is never below −1. The CP3a engine's `NEGATIVE_GROWTH_FACTOR` refusal at the
    annualization step becomes unreachable.
  - **(1.2, Q7)** Keep it as a **defensive** refusal. If it is ever reached, the engine has broken
    this rule. That is an engine fault, so the result is `INSUFFICIENT_DATA` +
    **`CALCULATION_ERROR`**, detail `NEGATIVE_GROWTH_FACTOR` (HG1 R2: loud and alertable), never a
    data state.

**Why.** A return on non-positive capital is undefined. Inventing a base (for example taking the
next day's deposit early) would move a flow to a date the ledger does not give.

**Known limitation:** the segment form does not see a value that turns non-positive **inside** a
flow-free run. That needs an unfunded purchase (margin, which V1 excludes, PD-0024 §3) followed by
a price fall. The daily attribution, which values every day, does see it, and fails there.

### RULING 5.4: Windows

- **Trailing `n` months** (1M, 3M, 6M, 1Y = 12M, 3Y, 5Y), ending `E`:
  `B = sub_months(E, n)`. Year-to-date: `B` = 31 December of the previous year. Since inception:
  `B = I₀`. Custom: any `B < E`.
- **`add_months(X, m)` and `sub_months(X, m)`, the end-of-month rule:**
  - if `X` is the last day of its month, the result is the last day of the target month;
  - otherwise the same day of the month, clamped to the target month's last day.

  Examples: `sub_months(2024-02-29, 12)` = 2023-02-28; `sub_months(2025-03-31, 1)` = 2025-02-28.
- **Validity:** `B ≥ I₀` and `B < E ≤` the as-of date.
  - `B < I₀` because of a snapshot is `INSUFFICIENT_DATA` + `NOT_RECONSTRUCTABLE`.
  - `B < I₀` for a portfolio with no snapshot is `INSUFFICIENT_DATA`, with no reason and detail
    `WINDOW_BEFORE_INCEPTION`.
  - A "1Y" figure for a three-month-old portfolio would assert a year of history (P5). The
    since-inception window is the honest figure.
- **Declared with every value:** `B` (the base date), `E`, the number of days `E − B`, and the
  rule (`TRAILING_MONTHS`, `YTD`, `SINCE_INCEPTION`, `CUSTOM`). Since inception for a snapshot
  portfolio is labelled "since `S`", never "since you started investing" (PRD §9.3).
- **Charts.** A cumulative series for a window has `n + 1` points, from `B` to `E` (HG1 M1 RULING
  1(b)): `W_B = 1` and `W_D = W_{D−1}(1 + r_D)`.

### RULING 5.5: The state of a TWR

- The state of a TWR is the worst of its inputs' states: every required valuation (Ruling 5.2)
  and every flow's translation or valuation (Ruling 4.3).
- `LIMITED` inputs give `LIMITED` + `STALE_DATA`, with the stale inputs listed.
- `AVAILABLE` + `STALE_DATA` propagates.
- The reason is chosen by Ruling 1.5.
- **No minimum length.** A TWR over a valid window is a fact, whatever its length. Annualization
  has a minimum (§7).
- The freshness vector (Ruling 1.6) is the union over the required valuations.

### RULING 5.6: Reporting currency versus native currency

- The TWR is computed in **`R`**. Changing `R` recomputes everything. It is not a conversion of a
  return.
- A **native-currency TWR** is defined only for a scope whose every holding, cash balance and flow
  in the window is in one currency `c`. It is then the same formula with `X ≡ 1` in `c`. For a
  multi-currency scope there is no native return. The "local" view is the attribution's price
  effect (§9). It is not a counterfactual return.

**Rejected alternatives for §5:**

- **Modified Dietz** (monthly or per period, linked). It approximates a true TWR by assuming the
  flows earned the period's average return. This product can value any date, so the
  approximation buys nothing, and using it as a **fallback** when a flow-date valuation is missing
  would put an estimate where P5 requires suppression. GIPS 2020 requires valuation at large flows
  for composites (MEMORY, §18 item 7). Daily valuation exceeds it.
- **Requiring a valuation every day for the TWR.** It is not needed (Ruling 5.2), and it would
  suppress a TWR because of a gap that cannot affect it.
- **A monthly valuation grid.** It is coarser than the data and loses daily flow timing.

#### Example W: one portfolio, three days (USD reporting)

Hypothetical ECB fixings:

- 2025-04-01: `x_USD` 1.0800, `x_HKD` 8.4000, so `X₁(HKD→USD)` = **9/70**;
- 2025-04-02 and 04-03: `x_USD` 1.0800, `x_HKD` 8.4240, so `X₂` = **5/39**.

H@XHKG closes: 04-01 **390.00**, 04-02 **400.00**, 04-03 **400.00**. The portfolio is empty at
the end of 2025-03-31, so `B` = 2025-03-31.

| Date | Events (account A1) |
|---|---|
| 04-01 | `DEPOSIT` 10,000 USD. `CURRENCY_CONVERSION` 5,000 USD → 38,800 HKD. `BUY` H 100 for 38,000 HKD. `FEE` 10 HKD (the commission, recorded separately, `listing_id` H). |
| 04-02 | `WITHDRAWAL` 1,000 USD |
| 04-03 | `DIVIDEND` H 200 HKD (gross, with no `ex_date`, so cash basis). `TAX` H 20 HKD (withholding). |

**End-of-day holdings:**

- 04-01: USD 5,000; HKD 38,800 − 38,000 − 10 = 790; H 100.
- 04-02: USD 4,000; HKD 790; H 100.
- 04-03: USD 4,000; HKD 790 + 200 − 20 = 970; H 100.

**Values:**

- `V_0` = 0.
- `V_1` = 5,000 + (790 + 39,000) × 9/70 = 5,000 + 358,110/70 = 5,000 + 35,811/7 = **70,811/7** =
  10,115.857142…
- `V_2` = 4,000 + (790 + 40,000) × 5/39 = 4,000 + 203,950/39 = **359,950/39** = 9,229.487179…
- `V_3` = 4,000 + (970 + 40,000) × 5/39 = 4,000 + 204,850/39 = **360,850/39** = 9,252.564102…

**Days:**

| `D` | `I^C` | `O` | `β_D` | `r_D` | `g_D` |
|---|---|---|---|---|---|
| 04-01 | 10,000 | 0 | 0 + 10,000 | 70,811/70,000 − 1 = **811/70,000** | **811/7** |
| 04-02 | 0 | 1,000 | 70,811/7 | (359,950/39 + 1,000) / (70,811/7) − 1 = (398,950 × 7)/(39 × 70,811) − 1 = 2,792,650/2,761,629 − 1 = **31,021/2,761,629** | 398,950/39 − 70,811/7 = **31,021/273** |
| 04-03 | 0 | 0 | 359,950/39 | 360,850/359,950 − 1 = **18/7,199** | **900/39** = 300/13 |

**TWR**, segment form: the flow days are 04-01 (inflow) and 04-02 (outflow).

- 1 + TWR = [(V₂ + O₂) / (V₀ + I^C₁)] × [V₃ / V₂] = (398,950/39 / 10,000) × (360,850/359,950).
- (398,950/39) / 10,000 = 39,895/39,000 = 7,979/7,800.
- 360,850/359,950 = 7,217/7,199.
- Product = 7,979 × 7,217 / (7,800 × 7,199) = 57,584,443/56,152,200.
- **TWR = 1,432,243/56,152,200** = 0.025506444983…, presented **0.025506444983**.

(7,979 × 7,217 = 55,853,000 + 1,731,443 = 57,584,443. 7,800 × 7,199 = 56,152,200.) The daily
product (1 + r₁)(1 + r₂)(1 + r₃) gives the same fraction. That is identity I-2.

**`G`** = `V₃` − `V₀` − (10,000 − 1,000) = 360,850/39 − 351,000/39 = **9,850/39** = 252.5641…,
presented **252.56**. Check: Σ g_D = (811 × 39 + 31,021 + 900 × 7)/273 = 68,950/273 = 9,850/39 ✓.

---

## 6. Money-weighted return (MWR / IRR)

### RULING 6.1: Definition, on the same values, flows and timing as the TWR

For a window `(B, E]` of `n = E − B` days, the cash flows **from the investor's side** are:

| Item | Amount | Time `τ` (fraction of the window) |
|---|---|---|
| base value | `−V_B` | 0 |
| each cash inflow dated `D` | `−I^C_D` | `(D − 1 − B) / n` (the start of `D` is the end of `D − 1`) |
| each in-kind inflow dated `D` | `−I^K_D` | `(D − B) / n` |
| each outflow dated `D` | `+O_D` | `(D − B) / n` |
| end value | `+V_E` | 1 |

Amounts at the same `τ` are summed exactly first. The **period MWR** `ρ` solves

```
f(g) = Σ_i CF_i · g^(−τ_i) = 0,      g = 1 + ρ > 0
```

The annualized MWR is `g^(1/Y) − 1`, only under §7.

- **Same timing as the TWR (Ruling 4.2).** So with no external flow strictly inside the window, the
  period MWR **equals** the TWR exactly: `−V_B + V_E g^(−1) = 0` gives `g = V_E / V_B`
  (identity I-6).
- **`f(1) = Σ CF_i = G` exactly.** The sign of a unique `ρ` is the sign of the absolute gain.

### RULING 6.2: The solver (deterministic; tolerance stated)

1. Build the cash flows in tier E. Evaluate `f(g)` in `Decimal`, `prec = 50`, `ROUND_HALF_EVEN`.
   Each term is `CF_i × exp(−τ_i × ln g)`, summed in increasing `τ`.
2. **Preconditions** (Ruling 6.4): the first non-zero flow is negative, and some flow is positive.
3. **If `G = 0` exactly, `g* = 1`.** Otherwise **bracket**:
   - if `G > 0`, test `g_hi` = 2, 4, 8, … until `f(g_hi) < 0`;
   - if `G < 0`, test `g_lo` = 1/2, 1/4, … until `f(g_lo) > 0`;
   - the other end is 1;
   - give up beyond 2^64 or below 2^−64 (`IRR_OUT_OF_RANGE`).
4. **Bisect:** set `mid = (g_lo + g_hi)/2` and keep the half where `f` changes sign (`f(mid) > 0`
   moves `g_lo`). Stop when `g_hi − g_lo ≤ 10^−30 × g_hi`, or after 400 iterations. The result is
   `g* = (g_lo + g_hi)/2`.
5. **Uniqueness test** (Ruling 6.3) at `g*`.
6. `ρ̂ = g* − 1`, quantized to 10^−12 (Ruling 2.2).

**Tolerance:** `|ρ̂ − ρ*| ≤ 10^−30 × g*` from the stop rule, plus the evaluation error near 10^−45,
plus the 0.5 × 10^−12 quantization. For fixture comparisons between independent implementations,
use **10^−10**.

**(1.1) The exact variant is conformant, and preferred.** Write `τ_i = k_i / n`, with `k_i` an
integer day count. With `y = g^(1/n)`, `n` days and `Y = p/q`:

- `f` becomes `Σ CF_i y^(−k_i)`. Its sign is evaluated **exactly** in `Fraction`.
- The same bracket rule (steps 3–4, expressed in `y`) and the uniqueness test (Ruling 6.3, with
  `g*^Δτ = y*^Δk`) apply.
- The bracket is narrowed until `g = y^n` is certified away from every 10^−12 boundary (Ruling
  2.1 (a)).
- The annualized MWR is `y*^(n/Y) − 1 = y*^(nq/p) − 1`, certified the same way.

This variant has no evaluation error, so its presented value is the correctly rounded root.
Ruling 6.2's `Decimal` route remains a valid reference.

**Why bisection.** It cannot diverge, it needs no derivative, and given the bracket rule and stop
rule its result is a deterministic function of the inputs. Newton's method can jump between roots
or diverge, and Brent's method mixes in steps whose order an implementer may vary.

### RULING 6.3: Existence and uniqueness: the pure-investment test

- **Existence.** As `g → 0⁺`, `f` takes the sign of the last non-zero flow, positive (`V_E`, or
  the final withdrawal). As `g → ∞`, it takes the sign of the first non-zero flow, negative. A
  root exists by continuity.
- **Uniqueness test.** At `g*`, form the investor's running balance compounded at `g*`:
  ```
  K_0 = −CF_0,     K_j = K_{j−1} · g*^(τ_j − τ_{j−1}) − CF_j,    for j = 1 … N−1   (all but the last flow)
  ```
  **If `K_j ≥ 0` for every `j`, `g*` is the only root.** The investor never becomes a net
  borrower at that rate (the "pure investment" condition; Teichroew, Robichek and Montalbano 1965,
  MEMORY §18 item 8).
- **Proof**, so a reviewer need not take the reference on trust. Define `K_j(g)` by the same
  recursion. Then `K_N(g) = −g^(τ_N) f(g)`.
  - Take `g > g*`. Suppose `K_{j−1}(g) ≥ K_{j−1}(g*) ≥ 0`. Then
    `K_j(g) = K_{j−1}(g) g^Δ − CF_j ≥ K_{j−1}(g*) g*^Δ − CF_j = K_j(g*)`. So `K_N(g) ≥ K_N(g*) = 0`,
    strictly once a positive balance has been held over a positive time.
  - Take `g < g*`. If `K_{j−1}(g) ≥ 0`, then `K_{j−1}(g) g^Δ ≤ K_{j−1}(g*) g^Δ ≤ K_{j−1}(g*) g*^Δ`.
    If `K_{j−1}(g) < 0`, the left side is negative and the right side is not. Either way
    `K_N(g) ≤ 0`.
  - So `f` changes sign only at `g*`. ∎
- The test covers the common pattern of deposits and withdrawals interleaved (Example M-2), which
  Descartes' sign count alone would reject. When every negative flow precedes every positive flow,
  it passes automatically.

### RULING 6.4: When the MWR is "not supported" (explicit states)

| Condition | State | Detail |
|---|---|---|
| any required value or flow is `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | that input's reason |
| no capital: every flow 0, or `V_B` = 0 with no inflow | `INSUFFICIENT_DATA`, no reason | `NO_CAPITAL` |
| the first non-zero flow is positive, or no flow is positive | `INSUFFICIENT_DATA`, no reason | `IRR_NOT_DEFINED` |
| no bracket within [2^−64, 2^64] | `INSUFFICIENT_DATA`, no reason | `IRR_OUT_OF_RANGE` |
| the uniqueness test fails | `INSUFFICIENT_DATA`, no reason | `IRR_UNIQUENESS_NOT_ESTABLISHED` |
| the window is before inception | as Ruling 5.4 | |

- A `LIMITED` input makes the MWR `LIMITED`, as for the TWR.
- The MWR has no `NON_POSITIVE_BASE` condition. A day with a negative base is just a flow pattern,
  so the MWR can be `AVAILABLE` when the TWR is not.
- **Snapshot portfolios.** The since-inception MWR starts at `S`, with `V_S` as the first
  investment, and is labelled "since `S`". The investor's true lifetime MWR is not available (PRD
  §9.3), and nothing implies that it is.

#### Example W (continued): the MWR

`n` = 3. The flows:

| `τ` | Flow |
|---|---|
| 0 | −10,000. The inflow at the start of 04-01 is at `τ` = (04-01 − 1 − B)/3 = 0, and `V_B` = 0. |
| 2/3 | +1,000, the outflow at the end of 04-02 |
| 1 | `V₃` = +360,850/39 |

- `f(1)` = `G` = 9,850/39 > 0, so `g* > 1`. The bracket is [1, 2]. Bisection reaches the stop rule
  after 100 halvings.
- **`ρ̂` = 0.026119591042** (the period MWR, 3 days, not annualized: §7).
- Uniqueness: the flow signs are −, +, +, with one sign change. `K₀` = 10,000 and
  `K₁` = 10,000 × g*^(2/3) − 1,000 ≈ 9,173.38, both ≥ 0, so the root is unique.
- Reviewer check: f(1.026119591042) is approximately 0, to about 10^−7 of the flows' size.

The MWR is above the TWR (0.025506444983). The money-weighted figure weights days by the capital
invested, and after the day-2 withdrawal less capital was invested on day 3, the day with the
lowest return (18/7,199, about 0.25 %, against about 1.16 % and 1.12 % on days 1 and 2). This
describes what happened. It is not an assessment of the investor's timing.

#### Example M-2: interleaved flows, with the root still unique

Over a window, the flows are −10,000 (`τ` = 0), +2,000 (1/2), −3,000 (3/4) and +12,000 (1). There
are three sign changes, so Descartes' rule allows up to three roots.

- `G` = 1,000 > 0.
- Bisection gives **`ρ̂` = 0.102593873725**.
- `K` = 10,000; 8,500.447…; 11,710.551…. All are ≥ 0, so the root is **unique**, and the MWR is
  `AVAILABLE`.
- If the window is exactly 12 months, `Y` = 1, so the annualized MWR is the same value (§7).

#### Example M-3: three roots, so the MWR is not supported (and the TWR still is)

Over a window, the flows are −1,800 (`τ` = 0), +6,050 (1/3), −6,750 (2/3) and +2,500 (1).

- A story that produces them: start at 1,800; the value grows past 6,050, which is all withdrawn;
  6,750 is deposited; the value ends at 2,500.
- With `y = g^(−1/3)`: `f = 2,500y³ − 6,750y² + 6,050y − 1,800 = 2,500 (y − 1)(y − 9/10)(y − 4/5)`.
  So the roots are `g` = 1, (10/9)³ = 1,000/729 and (5/4)³ = 125/64, that is
  **`ρ` = 0, 0.371742… and 0.953125**.
- The solver: `G` = 0 exactly, so `g*` = 1. Uniqueness test: `K₀` = 1,800, and
  `K₁` = 1,800 × 1 − 6,050 = **−4,250 < 0**. The test fails.
- **MWR = `INSUFFICIENT_DATA`, `IRR_UNIQUENESS_NOT_ESTABLISHED`.** Each of the three rates is an
  equally valid IRR, and presenting one would be arbitrary. The TWR over the same window is
  defined and `AVAILABLE`.

---

## 7. Annualization

### RULING 7.1: Year fraction: calendar months, with a day stub

```
m = the largest integer with add_months(B, m) ≤ E              (end-of-month rule, Ruling 5.4)
r = E − add_months(B, m)    in days
Y(B, E) = m/12 + r/365                                          exact rational
```

- **Why this, and not ACT/365.**
  - Every whole-year window gets `Y` = 1, 3 or 5 exactly, including across 29 February. So
    "1Y annualized" can never differ from "1Y" by a leap-day exponent.
  - With ACT/365, a 1Y window spanning a leap day (366 days) would give
    (1 + R)^(365/366) − 1 ≠ R.
  - For an irregular window it differs from ACT/365 by at most a few days' share of a year,
    because months differ in length (a February month counts 1/12 against 28/365). It is
    monotone in `E`. Annualization applies only when `Y ≥ 1` (Ruling 7.2), where the difference
    is a small fraction of the exponent.
- Examples:
  - `B` 2023-02-28, `E` 2024-02-29: `m` = 12, `r` = 0, `Y` = **1** (366 days);
  - `B` 2024-02-29, `E` 2025-02-28: `m` = 12, `r` = 0, `Y` = **1** (365 days);
  - `B` 2024-01-31, `E` 2025-03-05: `add_months(B, 13)` = 2025-02-28 by the month-end rule, `r` = 5,
    so `Y` = 13/12 + 5/365 = **961/876** = 1.09703… (ACT/365 would give 400/365 = 1.09589…).
- **Rejected:**
  - ACT/365 Fixed, because of the leap-day inconsistency above;
  - ACT/365.25, which is never exact for whole years;
  - 30/360, a bond convention that misstates the actual days.

### RULING 7.2: Annualize only windows of at least one year; compound geometrically

```
annualized(R, Y) = (1 + R)^(1/Y) − 1          only if Y ≥ 1
```

The root is computed by Ruling 2.1 (a) (certified: with `Y = p/q`, the `p`-th root of `(1+R)^q`)
or (b) (`exp(ln(1+R)/Y)`), from the tier-E `R` or `g*`, never from a presented value.

- **`Y < 1`:** the annualized metric is `INSUFFICIENT_DATA`, with no reason and detail
  `PERIOD_SHORTER_THAN_ONE_YEAR`. The period return is the figure (P6; GIPS 2020 forbids annualizing
  periods under a year, MEMORY, §18 item 7). Raising a 3-month return to the fourth power states a
  year that did not happen.
- **Applies to:** the TWR and the MWR (`g*^(1/Y) − 1`).
- **Never annualized:** `G`, realized and unrealized gains, income, fees and taxes amounts, and any
  attribution line or Cariño component. Annualizing components separately breaks their identity
  with the total (HG1 round 4 §4.6).
- **`R = −1`** (a total loss): undefined. `INSUFFICIENT_DATA`, detail `TOTAL_LOSS`.

**Wording (P6).** An annualized return is "the constant yearly rate that would have compounded to
the same result over this window". It is a historical average, never "what you can expect each
year". The registry text must say that (§14).

#### Example A-1

- A 3-year window (`Y` = 3) with TWR = 0.331 gives (1.331)^(1/3) − 1 = **0.1** exactly, because
  1.1³ = 1.331. `Decimal` gives 0.1000…0, presented **0.100000000000**.
- A 200-day window with TWR 0.05: `Y` < 1, so annualized is `INSUFFICIENT_DATA`
  (`PERIOD_SHORTER_THAN_ONE_YEAR`), and the period figure 0.05 stands.

---

## 8. Income, fees, taxes, financing costs and conversions

### RULING 8.1: Dividends: accrued from the ex-date when the ledger records it; otherwise cash basis

- **If `DIVIDEND.ex_date` is recorded and `ex_date < event_date` (the pay date):**
  - a **dividend receivable** of `amount`, in the event currency, is part of the value at the end
    of every day `D` with `ex_date ≤ D < pay date`, valued per Ruling 1.3;
  - **income is recognized on the ex-date**, at `X(c→R, ex_date)`;
  - FX changes on the receivable afterwards are FX effect (§9);
  - on the pay date the receivable becomes cash at equal value. That is not income again.
- **If `ex_date` is absent, or equal to the pay date:** income is recognized on the pay date at
  that date's fixing (cash basis). Lineage carries `INCOME_CASH_BASIS`, with no state change.
- The receivable exists only at ledger versions `L` that contain the `DIVIDEND` event. A dividend
  recorded after its pay date changes history from the ex-date at the new `L`. That is the
  intended bitemporal behaviour (`ledger-replay` 2.1).
- **Withholding** (`TAX` dated the pay date) is recognized on its own date, as a cost. No link to
  the dividend is needed (F9).

**Why accrual when possible.** The price falls on the ex-date. Cash-basis income makes the interval
from the ex-date to the pay date show a spurious loss, then a gain. For HK and US dividends that
interval can be weeks (MEMORY). GIPS recommends accrual from the ex-date (`ledger-replay` §4).
The ledger already holds the optional `ex_date` (F5).

**Rejected:**

- taking the ex-date from the corporate-action feed for a ledger dividend. That needs a join rule
  on (listing, pay date) that `market-data` 7.1 keeps as a check only; a candidate for later
  (OI-P2);
- accruing interest. No accrual schedule is recorded (`ledger-replay` 5.3).

### RULING 8.2: Gross and net

- The income line is the `DIVIDEND` amount as recorded. That is gross when a withholding `TAX` is
  recorded beside it, and net when it is not (`ledger-replay` 4.3).
- **A net-only dividend's withholding is unknown, not zero.** The taxes line is "**known** taxes"
  (PRD §8.4) by definition, and it is labelled that way. It is not marked `LIMITED`, because no
  rule can tell a net-only dividend from one with no withholding. The registry entry states the
  limitation.

### RULING 8.3: `INTEREST`

Income on its booking date, at that date's fixing (cash basis).

### RULING 8.4: Fees, taxes and financing costs (closes the `ledger-replay` 5.3 bucket question)

| Event | Line | Notes |
|---|---|---|
| `FEE` | **fees** | Never capitalized (Ruling 3.6). A `listing_id` attributes it to that holding in per-holding views. |
| `TAX` | **known taxes** | Withholding, stamp duty and levies. Same attribution rule. |
| `INTEREST_CHARGED` | **financing costs**, its own line | In PRD §15.2's five-part grouping it sits under fees, shown as a visible sub-line. It is never netted against `INTEREST` income. |

Each is recognized on its event date at that date's fixing.

### RULING 8.5: `CURRENCY_CONVERSION`: the conversion result (closes `ledger-replay` 5A.5's question)

```
conversion result(e) = − amount × X(sold→R, d) + bought_amount × X(bought→R, d)
```

- It is usually small and negative: the dealer's spread, plus any difference between the
  execution time and the ECB fixing. It can be positive.
- It is its **own line**, labelled "currency conversion result (spread and timing against the
  reference rate)".
- **Why not "fees":** the spread cannot be separated from timing without a market reference at
  the execution time (`ledger-replay` 5A.5).
- **Why not "FX effect":** FX effect is the revaluation of holdings by a moving rate (§9). This is
  an exchange at a rate different from the fixing.
- It is never computed from or used as a rate (`ledger-replay` 5A.7).

### RULING 8.6: Income and cost metrics

- **Income amount** over `(B, E]`: the Σ of income lines in `R`. **Fees, taxes and financing**
  amounts likewise. These are money facts. They equal the corresponding money attribution lines
  (§9), by construction.
  - **(1.4 clarification) Signs.** Each amount carries the sign of its line: income positive;
    fees, taxes and financing costs negative (a fee of 2 USD is −2.00). A window with no such
    event has amount **0, `AVAILABLE`**: a fact, not missing data.
  - **(1.4 clarification) Conversion result amount.** The sum over the window of Ruling 8.5 for
    every `CURRENCY_CONVERSION` dated in `(B, E]` equals attribution line 8 (Ruling 9.3). It may
    be computed and presented on its own, by the same formula, before the attribution is built.
  - **States.** An income or cost event whose amount cannot be translated (a CNH dividend, a
    missing rate) makes that window's amount for its line `INSUFFICIENT_DATA` with that reason.
    The other lines are unaffected. The rest follows Ruling 4.3 and Ruling 1.5.
- **Income return** over `(B, E]`: the Cariño-linked income component `C_income` (§9). It is a
  contribution to the TWR, **not** a yield. No dividend yield is defined in CP3.
- **Tax boundary (PRD §15.3):** CP3 records and includes known tax flows. It computes no tax, and
  no CP3 gain is a taxable gain. The lot method, FX dates, fees and jurisdiction rules all differ.

---

## 9. Attribution: an exact decomposition, money and percentage

### RULING 9.1: The daily money decomposition

For each calendar day `D` in `(B, E]`, every `g_D` (Ruling 5.1) is split into lines that sum to it
**exactly**. Notation for a position `(a, ℓ)`:

- `σ` = `n/o` if a `SPLIT` dated `D` applies to it, else 1;
- `q⁰ = q(D−1) × σ` and `P⁰ = P(ℓ, D−1) / σ`, so that `q⁰P⁰ = q(D−1) P(ℓ, D−1)`;
- `P¹ = P(ℓ, D)`;
- `X⁰ = X(c(ℓ)→R, D−1)` and `X¹ = X(c(ℓ)→R, D)`.

| Line | Contribution on day `D` |
|---|---|
| **price** (holdings) | `q⁰ (P¹ − P⁰) X⁰`, per position |
| **price** (trade result) | `BUY`: `q_e P¹ X¹ − A_e X(c_e→R, D)`; `SELL`: `A_e X(c_e→R, D) − q_e P¹ X¹` |
| **FX** (holdings) | `q⁰ P⁰ (X¹ − X⁰)`, per position; `m⁰ (X¹_k − X⁰_k)`, per start cash balance `m⁰` in `k`; `r⁰ (X¹ − X⁰)`, per start receivable `r⁰` |
| **interaction** | `q⁰ (P¹ − P⁰)(X¹ − X⁰)`, per position |
| **income** | `DIVIDEND` (cash basis) and `INTEREST`: `amount × X¹`; accrued `DIVIDEND`: `amount × X(ex_date)` on the ex-date |
| **fees** | `−amount × X¹` per `FEE` |
| **known taxes** | `−amount × X¹` per `TAX` |
| **financing costs** | `−amount × X¹` per `INTEREST_CHARGED` |
| **conversion result** | Ruling 8.5 |

- Flows and internal movements contribute **0**:
  - a deposit's cash is offset by `I^C`;
  - an in-kind flow's value at the close is offset by `I^K` or `O`;
  - internal transfer legs cancel at portfolio level;
  - an accrued dividend's settlement moves receivable into cash at equal value.
- **Exactness:** Σ lines = `V_D + O_D − I^K_D − V_{D−1} − I^C_D = g_D`. Expanding `V_D − V_{D−1}`
  by holding, `q_D P¹X¹ − q⁰P⁰X⁰ = q⁰(P¹X¹ − P⁰X⁰) + (q_D − q⁰)P¹X¹`. The first term is the price,
  FX and interaction lines. The second term, together with the trades' cash legs, gives the trade
  results and the in-kind offsets. The three-way split is the algebraic identity
  `P¹X¹ − P⁰X⁰ = (P¹ − P⁰)X⁰ + P⁰(X¹ − X⁰) + (P¹ − P⁰)(X¹ − X⁰)`.
- **Why this split.**
  - The price effect is measured at the start-of-day rate, and the FX effect on the start-of-day
    price. The cross term is **shown, never folded** (HG1 round 4 §4.3).
  - Trade results (execution against the close) are price effect.
  - For Southbound, the CNY consideration is translated at the same day's fixing as the HKD close,
    so any gap between the exchange's settlement rate and the ECB-derived cross lands in the trade
    result. That is a stated limitation (§14).

### RULING 9.2: The lines, and PRD §15.2's grouping

The lines, in their fixed registry order (which also breaks apportionment ties, Ruling 2.4):

1. local price effect;
2. FX effect;
3. price–FX interaction;
4. income;
5. fees;
6. known taxes;
7. financing costs;
8. currency conversion result.

**(1.7) Fixed line identifiers.** Each line has one identifier. Engines, manifests, the API, the
HG2 evidence pack and the UI all use it. A rename is a convention change, made by the Quant under a
new id.

| Position | Identifier | Line |
|---|---|---|
| 1 | `attr.price` | local price effect: holdings' price moves, plus trade results against the close |
| 2 | `attr.fx` | FX effect: positions, cash balances and receivables |
| 3 | `attr.price_fx_interaction` | price–FX interaction |
| 4 | `attr.income` | income |
| 5 | `attr.fees` | fees |
| 6 | `attr.taxes` | known taxes |
| 7 | `attr.financing` | financing costs |
| 8 | `attr.conversion` | currency conversion result |

- The position stays the registry order. It breaks apportionment ties (Ruling 2.4) and orders every
  presentation of the lines.
- The same identifiers name the Cariño components `C_k` (Ruling 9.4) and the per-holding,
  per-currency and per-account breakdowns (Ruling 9.6).
- **The since-acquisition view (Ruling 9.7)** keeps its own identifiers, fixed since 1.5:
  `LOCAL_AT_ACQUISITION_FX`, `FX_ON_COST` and `INTERACTION`, in that order. They answer a different
  question and are deliberately not in the `attr.` namespace (Ruling 9.7: the two FX figures must not
  share a label).

PRD §15.2's "security movement + FX movement + income − fees − known taxes" groups them as:

- security = 1;
- FX = 2 + 3;
- income = 4;
- fees = 5 + 7;
- taxes = 6;
- with 8 shown as its own line.

PRD §8.4 and §15.2 set a minimum list. Additional lines that reconcile are allowed, and folding the
conversion result into a group it does not belong to would mislabel it.

### RULING 9.3: Money attribution over a window: exact

```
M_k(B, E] = Σ_D m_{k,D}          Σ_k M_k = G(B, E]     exactly (tier E)
```

This is the decomposition PRD §15.2 asks to reconcile. It holds with **zero** tolerance in tier E.
It is presented with largest-remainder apportionment (Ruling 2.4).

### RULING 9.4: Percentage attribution: Cariño-linked, reconciling to the TWR

```
c_{k,D} = m_{k,D} / β_D                       (so Σ_k c_{k,D} = r_D exactly)
κ_D = ln(1 + r_D) / r_D     (κ_D = 1 when r_D = 0)
κ   = ln(1 + TWR) / TWR     (κ = 1 when TWR = 0)
C_k = (1/κ) Σ_D κ_D c_{k,D}                   Σ_k C_k = TWR     (exact in real arithmetic)
```

- **Computed** with `c_{k,D}` exact and `κ` in `Decimal`, `prec` 50. The internal error of
  Σ `C_k` − TWR is below 10^−45 (Example W: 3 × 10^−51). The presented `C_k` (quantum 10^−12)
  sum to the presented TWR within (K + 1)/2 × 10^−12 for K = 8. Views apportion (Ruling 2.4).
- **Days with `β_D` = 0 and `g_D` = 0** contribute nothing. A day with `r_D` = −1, or a TWR of
  −1, has no logarithm: the result is `INSUFFICIENT_DATA`, detail `TOTAL_LOSS`.
- **Why Cariño** (Cariño 1999, MEMORY, §18 item 9).
  - It is exact.
  - It is symmetric in time: no day's weight depends on the order of days.
  - It scales each day by a single factor, so a line that is 0 every day stays exactly 0.
  - Its factors are standard and easy to audit.
- **Rejected:**
  - **arithmetic sums of daily contributions**, which do not reconcile to a compounded return;
  - **Frongello and GRAP-style recursive linking**, where an earlier period's effects are
    compounded by later returns, so the attribution of a day depends on the order of days;
  - **Menchero's optimized linking**, which is also exact but less transparent, with no gain here;
  - **counterfactual runs** (the HG1 §4.3 two-run method, discussed in Ruling 9.8).

### RULING 9.5: Requirements and states

- **The attribution needs a valuation at the end of every calendar day in `[B, E]`**, and the
  prices `P(ℓ, D−1)` and `P(ℓ, D)` for every position held at the start of `D` or traded on `D`.
- **States:**
  - any required input `INSUFFICIENT_DATA` makes the attribution `INSUFFICIENT_DATA` with that
    reason. The TWR may still be `AVAILABLE` (Ruling 5.2), and the two states are independent;
  - a `LIMITED` input gives `LIMITED` + `STALE_DATA`;
  - `β_D ≤ 0` with `g_D ≠ 0` on any day gives `INSUFFICIENT_DATA`, `NON_POSITIVE_BASE`.
- **Never annualized** (Ruling 7.2).
- **(1.9) Scope of the base and value conditions.** The money lines (Ruling 9.3) and the
  percentage lines (Ruling 9.4) are separate results with separate states.
  - **Both** take the state of the inputs (the first two bullets above). Every missing or limited
    valuation, price or rate affects both.
  - **Only the percentage lines** are suppressed by conditions on the base or the value:
    - `β_D ≤ 0` with `g_D ≠ 0` gives `NON_POSITIVE_BASE`;
    - a day with `1 + r_D < 0` gives `NEGATIVE_VALUE` (Ruling 5.3);
    - `r_D = −1`, or a TWR of −1, gives `TOTAL_LOSS` (Ruling 9.4).

    In each case the result is `INSUFFICIENT_DATA` with no reason code (PD-0036 §2).
  - The **money** lines need no base and no logarithm. They sum to `g_D` exactly on every day, and
    to `G` over the window. `G` is `AVAILABLE` in exactly these cases (part 1 P4-R1), so the money
    attribution stays `AVAILABLE`.

### RULING 9.6: Per-holding, per-currency and per-account breakdown

Every line is computed per position, per cash balance and per receivable, so it sums **exactly**
to any grouping: listing, market, currency, account. Cariño is linear in `c_{k,D}`, so the linked
components also sum. This gives HG2 its per-market FX evidence.

**(1.9) A published breakdown is a decomposition object (Ruling 2.4 items 3–4).**

1. **What it is.** A breakdown of one line (`attr.*`) over a window into parts by a grouping:
   - `listing`: positions and trade results per listing, summed over accounts;
   - `currency`: a position's listing currency, or the currency of a cash balance or receivable;
   - `account`;
   - `component`: each position, cash balance and receivable on its own.
2. **Its displayed total is the line's apportioned display value** in the money attribution of the
   same window. The parts are apportioned to that total by Ruling 2.4 item 3 (floors toward −∞; the
   shortfall goes one quantum at a time to the largest remainders). So the parts sum exactly to the
   bar they break down. Each displayed part is within one quantum of its exact value. The exact parts
   stay in lineage.
3. **Order, which also breaks ties:**
   - `component`: positions, then cash balances, then receivables. Within each: positions by
     `listing_id`, receivables by the `DIVIDEND` `event_id` (both as UUID integers), cash by
     currency code;
   - `listing` and `account`: by id as a UUID integer;
   - `currency`: by code;
   - the `none` part last.
4. **Zero parts.** A part whose exact value is 0 is omitted from the breakdown. Its component stays
   in lineage.
5. **Components without the grouping key** form **one** part keyed **`none`**. Examples: cash
   balances and receivables in a by-`listing` breakdown; a conversion result in a by-`listing`
   breakdown. So every grouping sums to the line exactly.
6. **An independently presented part** (Ruling 2.4 item 2), such as a per-holding FX metric, may
   exist as its own result. It is never shown inside the breakdown object.

**(1.10) The grouping key of every contribution.** This supersedes the examples in item 5 above
where they differ. Every contribution to a line has exactly one key in each grouping, so every
grouping still sums to the line exactly.

| Contribution (Ruling 9.1) | `listing` | `market` | `currency` | `account` | `component` |
|---|---|---|---|---|---|
| a position's price, FX or interaction term | its listing | its listing's MIC | the listing's currency | its account | `position` (`listing_id`) |
| a trade result (`BUY`, `SELL`), in `attr.price` | the traded listing | its MIC | the listing's currency | its account | `position` (the traded listing) |
| a cash balance's FX term | `none` | `none` | the cash currency | its account | `cash` (currency) |
| a receivable's FX term | **the listing its `DIVIDEND` names** | that listing's MIC | the receivable's currency | its account | `receivable` (`event_id`) |
| an income, fee, tax or financing event (`attr.income`, `attr.fees`, `attr.taxes`, `attr.financing`) | the event's `listing_id`, else `none` | that listing's MIC, else `none` | **the event currency** | its account | **`event`** (`event_id`) |
| a conversion result (`attr.conversion`) | `none` | `none` | `none` | its account | `event` (`event_id`) |

- **A receivable goes to its dividend's listing.** Until it is paid, an accrued dividend is part of
  the security's return. That is holding-level practice, and Ruling 8.1 treats the receivable as
  the dividend's value from the ex-date, recognized as that listing's income. Its FX between the
  ex-date and the pay date is therefore that holding's.
  - Once paid, it is cash, and its later FX is `none` in the listing and market groupings.
  - The 1.9 example ("receivables … in a by-`listing` breakdown" fall in `none`) was wrong, and is
    withdrawn.
- **Event lines are keyed by what the event records** (Ruling 8.4):
  - its listing, if any;
  - its currency, which is the amount translated;
  - its own `event_id`, as a new component kind, `event`, ordered after receivables by `event_id`.

  `none` is only for what the ledger does not record.
- **A conversion result has no single currency.** Its two legs, sold and bought, are not separate
  economic effects. Split, they would show two large offsetting numbers. So it is `none` in the
  currency grouping.
- **`market`** is the listing's MIC (for example XNYS, XHKG, XSHG). It is ordered by MIC code, with
  `none` last.
- **The order of item 3 is extended:** components run positions, cash, receivables, then events.
  The `market` and `currency` groupings are ordered by code. `none` comes last.

**Why.** HG1 round 4 §4.4 and Ruling 2.4 item 4 require that displayed parts sum to the displayed
whole. A drill-down whose parts do not add up to the bar it opens is the defect that rule exists to
prevent. Apportioning to the line's displayed value, rather than to its independently rounded value,
keeps the whole view consistent at every level.

### RULING 9.7: Since-acquisition decomposition of an unrealized gain (HG1 round 4 §7.3)

For a remaining lot λ (basis currency `k = c(ℓ)`) at `D`, with `V = u_λ P(ℓ, D)` and `K = u_λ c_λ`:

```
UG_R(λ) = (V − K) X_a  +  K (X_D − X_a)  +  (V − K)(X_D − X_a)
          local gain at      FX on cost      interaction
          acquisition FX
```

Here `X_a = X(k→R, a_λ)` and `X_D = X(k→R, D)`. The position's gain contains the currency effect,
which closes HG1 round 4 §7.3 (FX had cancelled). It sums over lots.

- For a Southbound lot (`k` = CNY, `c(ℓ)` = HKD), the "local gain" is expressed in CNY at
  `X_D(HKD→CNY)`, so it includes HKD/CNY moves. It is labelled "gain in the currency paid".
- **This answers a different question from §9.4.** §9.4 asks "what moved the portfolio over
  `(B, E]`"; this asks "how this lot's gain since it was bought splits". The two FX figures differ
  in general: FX on cost against FX on daily market value. Both are exact, and both are labelled.
  Example W shows both.
- **(1.5) Lines, order and states.**
  - The line names are `LOCAL_AT_ACQUISITION_FX`, `FX_ON_COST` and `INTERACTION`, in that registry
    order, which also breaks apportionment ties (Ruling 2.4 item 3).
  - The view is published as a decomposition object whose total is the lot's `UG_R(λ) = V X_D −
    K X_a`.
  - The lot is identified by its `ledger-replay/1.4` identity. A carried lot uses its origin's
    `a_λ`.
  - It needs `X_a`:
    - an `ENTRY` lot with `k ≠ R` has none, so the decomposition is `INSUFFICIENT_DATA` +
      `MISSING_COST_BASIS`, detail `ACQUISITION_DATE_UNKNOWN`;
    - an unknown lot gives `MISSING_COST_BASIS`, detail `UNKNOWN_BASIS`;
    - an `ENTRY` lot with `k = R` has `X_a = X_D = 1`, so `FX_ON_COST` and `INTERACTION` are 0.
  - The valuation's state at `D` joins.
- **(1.6) `RECORDED` lots** (Ruling 3.7a) use `X_a` at `a_λ = acquired_on`, with that rate's state.
  - A date before the FX coverage of `M` gives `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`.
  - A lot with `k = R` is `AVAILABLE` whatever the date, all local.
  - A carried `RECORDED` lot uses its origin's date.
  - For a snapshot lot with `acquired_on` before `S`, the view spans from `acquired_on`. It describes
    the lot since the user's recorded purchase, not the portfolio's history, which still starts at
    `S`.

### RULING 9.8: Relation to HG1 round 4 §4.3 (OD-P4, **DECIDED (PD-0035 §4): the exact daily split supersedes HG1 §4.3**)

> **(1.1)** The owner adopted the exact daily split. The approved waterfall's first bar is "local
> price effect", with a separate price–FX interaction line. The designer updates the design
> artifacts before CP7.

HG1 round 4 §4.3 defined the portfolio-level FX effect as `R_base − R_local`, where `R_local` is
the TWR with all FX held at the window-start rates. It deliberately avoided choosing a linking
algorithm, and it decomposed price and FX only.

`performance/1.0` §9 **supersedes that portfolio-level definition** for the attribution, for three
reasons:

1. **Five-part attribution needs per-period contributions.** Income, fees and taxes cannot be
   split out of a constant-FX counterfactual run without ordering effects. HG1 §4.3 itself named a
   linking algorithm as the alternative, and only deferred the choice.
2. **The constant-FX run mislabels conversions and Southbound trades.** At window-start rates, a
   conversion at a later market rate shows a gain or loss that is really FX movement since `B`. A
   CNY-paid HKD purchase shows CNY/HKD movement as a price effect.
3. **One FX number.** Keeping both definitions would put two "FX effect" figures, with one label,
   in one product.

HG1 §4.3's **sleeve-level** identity `(1 + R_local)(1 + R_fx) − 1`, with the interaction shown, is
kept: Rulings 9.1 and 9.7 apply it per day and per lot. Because the HG1-approved prototype's
waterfall showed "Local-market return (FX held at window-start rates)" as its first bar, and that
bar no longer exists as defined, **the owner is asked to confirm** (OD-P4, §15).

#### Example W (continued): attribution

**Day 1** (`β₁` = 10,000; no start-of-day holdings):

- conversion result = −5,000 + 38,800 × 9/70 = −35,000/7 + 34,920/7 = **−80/7**;
- trade result (`BUY` H) = (100 × 390 − 38,000) × 9/70 = 9,000/70 = **900/7**;
- fee = −10 × 9/70 = **−9/7**;
- Σ = 811/7 = `g₁` ✓.

**Day 2** (holdings H 100 at 390, HKD 790; `X` 9/70 → 5/39, so `X¹ − X⁰` = (350 − 351)/2,730 =
−1/2,730):

- price = 100 × 10 × 9/70 = **900/7**;
- FX on H = 39,000 × (−1/2,730) = **−100/7**;
- interaction = 1,000 × (−1/2,730) = **−100/273**;
- FX on HKD cash = 790 × (−1/2,730) = **−79/273**;
- the withdrawal contributes 0;
- Σ = (35,100 − 3,900 − 100 − 79)/273 = 31,021/273 = `g₂` ✓.

**Day 3** (no price or FX change):

- income = 200 × 5/39 = **1,000/39**;
- taxes = −20 × 5/39 = **−100/39**;
- Σ = 900/39 = `g₃` ✓.

**Window lines** (money, USD):

| Line | Exact | Value | Apportioned (Ruling 2.4) | Cariño `C_k` (quantum 10^−12) |
|---|---|---|---|---|
| 1 local price effect | 1,800/7 | 257.142857 | 257.14 | 0.025745124051 |
| 2 FX effect | −100/7 − 79/273 = −3,979/273 | −14.575092 | −14.57 | −0.001450980031 |
| 3 interaction | −100/273 | −0.366300 | −0.37 | −0.000036465947 |
| 4 income | 1,000/39 | 25.641026 | 25.64 | 0.002809934002 |
| 5 fees | −9/7 | −1.285714 | −1.29 | −0.000129455767 |
| 6 known taxes | −100/39 | −2.564103 | −2.56 | −0.000280993400 |
| 7 financing costs | 0 | 0 | 0.00 | 0 |
| 8 conversion result | −80/7 | −11.428571 | −11.43 | −0.001150717925 |
| **Σ** | **9,850/39 = `G`** | 252.564103 | **252.56** | **0.025506444983 = TWR** |

- Exact money check: in 273rds, 70,200 − 3,979 − 100 + 7,000 − 351 − 700 + 0 − 3,120 = 68,950,
  and 68,950/273 = 9,850/39 ✓.
- Cariño check: the eight presented `C_k` sum to 0.025506444983, which is the presented TWR. The
  internal difference was −3 × 10^−51.
- **At a 0.01 % display** (quantum 10^−4), the TWR is 2.55 %.
  - Independently rounded lines give 2.57, −0.15, −0.00, 0.28, −0.01, −0.03, 0.00 and −0.12,
    summing to 2.54.
  - Apportioned:
    - in units of 0.01 %, the floors are 257, −15, −1, 28, −2, −3, 0 and −12, summing to 252;
    - the shortfall is 3;
    - the largest remainders go to fees (.705), interaction (.635) and conversion (.493);
    - result: **2.57, −0.15, 0.00, 0.28, −0.01, −0.03, 0.00, −0.11**, summing to **2.55**.

**Since-acquisition view of H at 04-03** (Ruling 9.7; `K` = 38,000 HKD at `X_a` = 9/70;
`V` = 40,000 at `X_D` = 5/39):

- local gain at acquisition FX = 2,000 × 9/70 = **1,800/7**;
- FX on cost = 38,000 × (−1/2,730) = **−3,800/273**;
- interaction = 2,000 × (−1/2,730) = **−200/273**;
- `UG_R` = 200,000/39 − 34,200/7 = **66,200/273** = 242.49 ✓.

Its FX plus interaction, −4,000/273, equals the attribution's H FX plus interaction
(−100/7 − 100/273 = −4,000/273). The two views split that amount differently: FX on cost against
FX on the start-of-day value.

**Gain identity** (the window starts at inception):

- `UG_R(H)` + income + taxes + fees + conversion result + FX on HKD cash
- = 66,200/273 + 1,000/39 − 100/39 − 9/7 − 80/7 − 79/273
- = (66,200 + 7,000 − 700 − 351 − 3,120 − 79)/273 = 68,950/273 = **`G`** ✓.

---

## 10. Return denominators: every return, explicitly (PD-0021 §9)

| Return | Numerator | Denominator | Notes |
|---|---|---|---|
| Daily portfolio return `r_D` | `V_D + O_D − I^K_D − β_D` | **`β_D = V_{D−1} + I^C_D`** | cash inflows at the start of the day; outflows and in-kind flows at the end (Ruling 4.2) |
| TWR | — | — | the geometric link of `r_D`; segment form, Ruling 5.2 |
| MWR (period) | — | — | the root of Ruling 6.1; no explicit denominator |
| Annualized TWR or MWR | — | — | `(1+R)^(1/Y) − 1`, with `Y` from Ruling 7.1 |
| Cariño component `C_k` | `m_{k,D}` | **`β_D`** per day, then linked | Ruling 9.4 |
| Realized gain % | `RG_R` | **relieved basis in `R`** (lots at acquisition FX) | same for native |
| Unrealized gain % | `UG_R` | **remaining basis in `R`** | |
| Since-acquisition shares (Ruling 9.7) | each part | **`K X_a`** (the lot's `R` basis) | if shown as % |
| Stale or excluded weight (Rulings 1.4, 3.10) | Σ \|excluded value\| | **Σ \|all component values\|** (gross) | disclosure only |
| Security price return (CP4) | adjusted close `D` | **adjusted close `D−1`**, engine-derived (`market-data` 2.5) | not CP3; MD-OI-3 stays open for CP4 |
| FX return | `X(c→R, D)` | **`X(c→R, D−1)`** | |

**Not defined, deliberately:** a simple `G / V_B` return; a return on average capital (Modified
Dietz); a dividend yield. Concentration and exposure weights are CP5. Their denominator (holdings
only, or including cash) is the owner's open question from HG1 round 4 §9.5, and is not decided
here.

---

## 11. Reconciliation: identities, tolerances, and the CP3 golden fixture

### RULING 11.1: Identities that hold exactly in tier E (zero tolerance)

| ID | Identity |
|---|---|
| I-1 | `TV_R` = Σ of its components (Ruling 1.4) |
| I-2 | The daily product Π(1 + r_D) = the segment product (Ruling 5.2), whenever every daily value exists |
| I-3 | Σ_D g_D = `V_E − V_B − (Σ I^C + Σ I^K − Σ O)` = `G` |
| I-4 | Σ_k m_{k,D} = g_D for every day, and Σ_k M_k = `G` |
| I-5 | Lot conservation: removed + remaining = original, in native and in `R`; carried basis out = carried basis in |
| I-6 | With no flow strictly inside the window: period MWR = TWR; and `f(1)` = `G` |
| I-7 | Method independence: `RG + UG` = proceeds + `MV` − Σ costs, under every lot method (no transfer out, all bases known) |
| I-8 | Since-acquisition parts sum to `UG_R`, per lot |
| I-9 | Cash: replay balance = Σ cash effects (CP1; restated) |

**At runtime**, a failed identity is an **engine fault**. The affected metric is `INSUFFICIENT_DATA`
+ `CALCULATION_ERROR` (HG1 R2), and is never shown with a caveat.

**(1.2) When each identity must run (Q5).**

| Identity | Must run |
|---|---|
| I-1, I-5, I-8, I-9 | **In every product call that produces the values they relate.** They are cheap: one sum, or one lot's arithmetic. |
| I-4 | **In every call that computes the attribution.** |
| I-2, I-3 | **In every call that computes the attribution**, which values every day anyway, so they cost nothing extra. Also in the test suite, the golden fixture runs, and the HG2 evidence pack. **Not required in a product call that computes only a TWR or `G`**: there they would force a valuation of every day, which the TWR deliberately does not need (Ruling 5.2), and an interior gap could not change the TWR anyway. |
| I-6, I-7 | In the test suite, the fixtures and the HG2 pack. I-6 also whenever an MWR and a TWR are computed over the same window with no interior flow. |

A check that cannot run is not a pass. Example: I-2 is not computable when an interior day has no
value. Lineage records which identities ran.

**(1.4 clarification) Reproduction (§34).** A reproduction confirms a result only by comparing the
re-run's result digest with an expected digest.

- When no expected digest is supplied, the outcome is `RESULT_NOT_COMPARED` (the engine's name).
  It is **never** reported, counted or cited as `REPRODUCED`. Like an identity that could not run,
  it is not a pass.
- HG2's reconciliation evidence must therefore cite, for every reproduced result, the manifest ID
  and the expected result digest it was compared against.

### RULING 11.2: Tolerances (the "known numerical tolerances" HG2 requires)

| Comparison | Tolerance | Basis |
|---|---|---|
| Tier-E identities I-1 to I-9 | **0** | exact rationals |
| A presented money value against its exact value | ≤ ½ minor unit | Ruling 2.2 |
| Independently presented parts against their presented total | ≤ (k + 1)/2 quanta | Ruling 2.4 item 2 |
| Apportioned decomposition, displayed parts against displayed total | **0** | Ruling 2.4 item 3 |
| A presented return against its exact value | ≤ 0.5 × 10^−12 | quantum |
| Cariño Σ C_k against TWR, internal | ≤ 10^−40 | `prec` 50 |
| Presented C_k sum against presented TWR | ≤ 4.5 × 10^−12 (K = 8) | Ruling 2.4 item 2 |
| IRR `ρ̂` against the true root | ≤ 10^−30 relative + 0.5 × 10^−12 | Ruling 6.2 |
| **Fixture against engine**, exact-arithmetic outputs (money, TWR, `G`, money lines, bases, realized/unrealized) | **0** on the presented value, and the exact rational where the fixture gives one | the derivation computes the same exact rational |
| **Fixture against engine**, transcendental outputs (MWR, annualized, Cariño) | **10^−10** absolute | independent implementations may differ in late digits |

**No tolerance may be widened to make a check pass** (HG1 M1 RULING 4(ii)). A failure is a finding.

### RULING 11.3: Metamorphic checks (each a property test)

1. **Entry order.** Permuting `ledger_seq` within a day changes no output byte (Rulings 3.3 and
   3.4; `ledger-replay` 3.1).
2. **An internal transfer pair** inserted on any day changes no portfolio-level output.
3. **A split** inserted with raw prices consistent with it (the close divided by `n/o` from the
   ex-date) changes no value, return, `G` or attribution line.
4. **All in `R`:** if every holding, cash balance and flow is in `R`, the FX, interaction and
   conversion lines are 0 exactly.
5. **Lot method:** switching FIFO and AVCO changes no TWR, MWR, `G`, attribution line or value
   (I-7).
6. **Valuation-only gaps:** making an interior non-flow day's price `INSUFFICIENT` changes the
   TWR's value and state not at all, while the attribution becomes `INSUFFICIENT_DATA` (Ruling
   5.2).
7. **Determinism:** byte-identical output across runs, processes and `PYTHONHASHSEED`, as in
   CP1-D T10.

### 11.4: What "known test portfolios reconcile" means (CP3 exit, PRD §38.3)

All four of these hold:

- **(a)** every assertion of the CP3 golden fixture matches, within Ruling 11.2's fixture
  tolerances;
- **(b)** identities I-1 to I-9 hold at zero tolerance on every fixture portfolio, at every
  asserted date and window;
- **(c)** the metamorphic checks of Ruling 11.3 pass;
- **(d)** every unsupported case in the fixture returns its specified state, reason and detail,
  never a number.

The expected values come from the Quant's independent derivation, never from the engine's output.

### 11.5: The CP3 golden fixture: plan (`cp3_golden/1.0`; authored after the format is agreed)

> **(1.1) Part 1 is authored** (valuation, TWR, annualization):
> `methodology/fixtures/cp3_golden/cp3_golden_part1.json` (`cp3_golden/1.0-part1`), with
> `CP3_GOLDEN_PART1_DERIVATION.md` and the independent calculator
> `derivation/cp3_part1_calculator.py`. Its format and portfolio list supersede the sketch below
> where they differ: P1 and P2 as planned, and P3 to P6 re-cut for part 1's cases.
>
> - **Part 2:** MWR, income, fees and taxes.
> - **Part 3:** lots and gains under `FIFO/1`.
> - **Part 4:** attribution.

**Location:** `methodology/fixtures/cp3_golden/`, as for CP1 (main-session decision 2026-09-30).

**Market data** is **synthetic** throughout (`market-data` Ruling 4.8: `upstream: synthetic`, and
every result is flagged synthetic). It is delivered as files in the engine's own formats, so the
real CP2 parsers and lookups are exercised:

- price files for each listing, raw, volume > 0, piecewise constant, changing on a few dates only so
  that the hand derivation stays tractable;
- an ECB-format EUR-based FX file (USD, HKD, CNY; HKD inside 7.75–7.85);
- self-contained synthetic calendar files covering the fixture window. The fixture does not depend
  on the unregistered drafts.

**Portfolios:**

| ID | Reporting | Built from | Exercises |
|---|---|---|---|
| P1 | USD | `cp1_golden` P1 events E1–E8 and X1–X16, **unchanged**, plus prices and FX for AAPL (with raw prices consistent with E5's 4:1 split), 0700 and MSFT | valuation through the split; internal cash and security transfers (neutrality); the conversion result (X8 after the X7 reversal); `INTEREST_CHARGED`; the unknown-basis MSFT lot (E8); the two-lot MSFT case V3 keyed by method (L-1); single-lot realized gains (E7: 2,250 − 50 × 150 = **750**; X12: 2,000 − 40 × 37.5 = **500**); the carried basis X13/X14 (110 × 37.5 = 4,125); TWR, MWR and `G` since inception and on sub-windows; attribution |
| P2 | HKD | `cp1_golden` P2 (snapshot), plus prices | TWR and MWR "since `S`"; window before `S` → `NOT_RECONSTRUCTABLE`; unrealized and realized → `MISSING_COST_BASIS`; `R` = HKD, so no FX on HKD |
| P3 (new) | CNY | an A-share (XSHG); a Southbound purchase of an XHKG listing paid in CNY; USD cash | dividend with `ex_date` < pay date (accrual) and withholding `TAX`; stamp-duty `TAX`; `INTEREST`; a `WITHDRAWAL`; external in-kind `TRANSFER_IN` with and without `cost_basis` (`ACQUISITION_DATE_UNKNOWN`); `MIXED_CURRENCY_BASIS`; one window of at least 1 year (annualization); FX attribution with CNY reporting |
| P4 (new) | USD | small, one case per assertion group | each state case: a listing with no admitted source; CNH cash; price stale for 1, 3 and 5 sessions; a corroborated split missing from the ledger (`SOURCE_CONFLICT`); a calendar coverage gap; a purchase before its deposit (`NON_POSITIVE_BASE` for the TWR, with the MWR `AVAILABLE`); a window before inception; an interior gap (TWR `AVAILABLE`, attribution `INSUFFICIENT_DATA`) |
| P5 (new) | USD | flows of Examples M-2 and M-3 | the IRR uniqueness test, both outcomes |

> **(1.5) Erratum to the P1 row.** "E7: 2,250 − 50 × 150 = **750**" is wrong. E7 (2025-03-03)
> sells 50 units **after** E5's 4:1 split (ex-date 2025-02-03). The lot then holds 200 units at
> 7,500 / 200 = 37.50, so the relieved basis is 50 × 37.50 = 1,875, and the realized gain is
> 2,250 − 1,875 = **375**. This agrees with `ledger-replay` T7, whose remaining basis is 5,625 =
> 7,500 − 1,875. X12 (**500**) and the X13/X14 carried basis (**4,125**) are right as written.
> `cp3_golden` part 3 asserts 375.
>
> **(1.5) Part 3 is authored**: `cp3_golden/1.0-part3` (`cp3_golden_part3.json`,
> `CP3_GOLDEN_PART3_DERIVATION.md`, `derivation/cp3_part3_calculator.py`). It covers P1, P2 and P3
> as planned, P3 extended by ledger_seq 8–13, plus new portfolios P14 to P19.
>
> **(1.7) Part 4 is authored** (attribution, Rulings 9.1–9.6). It is `cp3_golden/1.1-part4`
> (`cp3_golden_part4.json`, `CP3_GOLDEN_PART4_DERIVATION.md`, `derivation/cp3_part4_calculator.py`),
> with 28 items, and lines identified by the Ruling 9.2 (1.7) ids. It covers:
>
> - Example W on the fixture's FX (P12, the window and its FX day);
> - P1 since inception;
> - P6, FX only;
> - P3's Southbound trade result in `attr.price`, and its stale-input window (`LIMITED`);
> - P21 (new), FX on a dividend receivable;
> - P22 (new), an interior five-session gap: TWR `AVAILABLE`, attribution `INSUFFICIENT_DATA`;
> - P14, all in `R` (11.3 #4);
> - P13, a suppressed split (`SOURCE_CONFLICT`).
>
> P7 is not used for receivable FX, because its synthetic FX is constant from ex-date to pay date.

**Assertion kinds** (to agree with the engineer):

- `total_value`, `position_value`, `cash_value`;
- `gain_absolute`, `twr`, `mwr`, `annualized_twr`, `annualized_mwr`;
- `attribution_money` (8 lines, exact plus apportioned), `attribution_return` (8 `C_k`);
- `realized_gain`, `unrealized_gain`, `remaining_basis_R`;
- `income_amount`, `fees_amount`, `taxes_amount`, `financing_amount`;
- `since_acquisition`;
- `current_mode_as_of` (a given `t` gives `D_c`).

Each assertion carries `state`, `reason`, `detail`, the presented `value`, the **exact value as a
reduced fraction string `"p/q"`** where the output is exact, and the window `(B, E]` with its rule.
Method-dependent assertions are keyed `UNDECIDED` / `FIFO` / `AVCO`.

**Format points to agree with the engineer:**

1. the market-data block, as files under the fixture directory with manifests, or inline;
2. the `"p/q"` exact-value field;
3. the window encoding;
4. the attribution line names, matching Ruling 9.2's order;
5. how lineage details are named (§16 list);
6. `FIXTURE_PINS` (item counts and a content hash, as in CP1-D).

**Derivation:**

- `CP3_GOLDEN_FIXTURE_DERIVATION.md`, by hand, with every intermediate fraction shown, as in
  Example W;
- plus an **independent calculator script** that I write from this document alone. It imports
  nothing from `src/` and uses exact `Fraction` arithmetic. It is committed beside the fixture so a
  reviewer can re-run the arithmetic, and it is never used to read the engine's output.

The CP1 rule stands: no expected value from the implementation.

### RULING 11.6 (1.8; PM ruling on OI-P11): Fixture convention policy

1. **Minimum versions.** A fixture's `convention_sets` name, per family (`performance`,
   `ledger-replay`, `market-data`, the lot method), the **minimum** version under which it was
   derived and ratified.
   - A checker accepts a manifest citing the **same family at that version or later**.
   - It refuses an earlier version, or another family.
2. **A new fixture version when anything asserted changes.** If a convention change alters any
   value, state, reason or detail a fixture asserts, the Quant issues a **new fixture version** with
   a change note and the new minimum versions. The engineer re-pins it. A fixture is never left to
   pass against a convention that changed what it asserts.
3. **Every convention change note says what it leaves alone.** Each change note of a convention
   set names, by fixture id, the fixtures the change leaves **unaffected**. A fixture it does not
   name is treated as affected until the Quant says otherwise.
4. **Wording.** Each fixture's format or notes state that its `convention_sets` are minimum versions.
   That is a wording-only change. It is made in the next version a fixture gets for another reason,
   never as a separate relabel.

**Why.** A version bump that changes nothing a fixture asserts should not force a relabel and
re-pin of every fixture. A change that does alter an assertion must never pass silently: item 2
forces the new version, and item 3 makes the judgment explicit and auditable (P9).

---

## 12. HG2 on the data that is admissible (for the owner's decision on STATUS item 17)

**What is admitted** (PD-0031 to PD-0033):

- **US prices:** Alpha Vantage free tier, the last 100 sessions only, `SINGLE_SOURCE`, split label
  `UNVERIFIABLE`.
- **FX:** the ECB, real, with full history from the ECB file.
- **CN and HK:** **no admissible price source.**
- **Corporate actions:** no real corporate-action or filing adapter exists, so F8-B has no real
  input.

| HG2 evidence item (PRD §38.4) | Synthetic multi-market portfolio | Real data: US holdings, real ECB FX, USD/HKD/CNY cash | Real CN/HK holdings |
|---|---|---|---|
| Reconstructed positions from ledger events | yes | yes | yes (ledger only) |
| Current portfolio value | yes, flagged synthetic | yes, for a portfolio holding **only** US listings and cash | **no**: `MISSING_PRICE_HISTORY` / `NO_ADMITTED_SOURCE`, so the total is `INSUFFICIENT_DATA` (Ruling 1.4) |
| Reporting and native currencies | yes | yes | native facts yes; reporting no |
| Price and FX timestamps | synthetic timestamps from synthetic calendars | **real**: US end of day, ECB fixings (once the calendars are registered; until then freshness is `UNKNOWN`, which fails closed) | no prices |
| Historical FX handling (basis at acquisition-date FX) | yes | **yes, on real ECB rates** | basis yes, gains no |
| Deposits against investment gains; internal transfers | yes | yes | ledger yes, returns no |
| Dividends (accrual, withholding) | yes | yes, within the 100-session window | ledger yes |
| Splits | yes (synthetic split with consistent raw prices) | only if a US split falls in the window; F8 detection needs corporate-action input that does not exist yet | no |
| Missing cost basis behaviour | yes | yes | yes for basis |
| TWR, MWR, realized and unrealized gain | yes | yes, over at most about 5 months | no |
| Annualized return | yes (a window of at least 1 year) | **no**: 100 sessions < 1 year, so `PERIOD_SHORTER_THAN_ONE_YEAR` | no |
| FX attribution | yes, all three currencies | **yes, with real FX**: for example a **CNY-reporting** portfolio holding US listings, or a USD portfolio with HKD/CNY cash | no |
| Reconciliation proof | **yes, against hand-derived expected values** (strongest) | identities I-1 to I-9 hold, but there are no independent expected values | — |
| Known numerical tolerances | Ruling 11.2 | Ruling 11.2 | — |

**OD-P3 (STATUS item 17). DECIDED (PD-0035 §3): option (a), "Synthetic + real US/ECB".** The HG2
package states that CN/HK price handling is shown on synthetic data only. A real CN/HK source is
revisited before CP4 or HG3. The options as put:

- **(a) Two-part HG2** (**recommended**):
  - a **synthetic multi-market demonstration portfolio** (US, CN, HK holdings; USD, HKD, CNY
    cash; full history), with hand-derived expected values, proves the accounting;
  - plus a **real-data portfolio** (US listings, USD/HKD/CNY cash, CNY reporting), which shows
    real timestamps, real ECB history, real freshness and real FX attribution.
  - **The owner approves HG2 knowing that** CN and HK real-price behaviour is unproven: real
    session calendars and suspensions, real corporate actions, and source reconciliation. That
    behaviour must be shown before private beta in any case (OQ-04b).
- **(b) Obtain a personal-use paid source for CN/HK before HG2**, for example the EODHD plan
  STATUS mentions. Its terms must be checked under PD-0031's method. This gives real CN/HK
  evidence at HG2, at the cost of a subscription and the wait.
- **(c) Written permission from a source.** Uncertain timing.

**Recommendation: (a).** HG2's question is whether the accounting and cross-currency foundation can
be trusted. Exact expected values on synthetic data answer that more strongly than real data can,
because real data has no independent expected values. The real-data portfolio covers what
synthetic data cannot: real lineage and timing.

**Note for the owner:** real CN/HK **history** matters more at HG3 (risk statistics need long real
return series) than at HG2. So option (b) may be needed by CP4 even if (a) is chosen now.

---

## 13. The two calendar items (PD-0033, PD-0034), written into `market-data/1.8`

- **HKEX default close: 16:10, and 12:10 on half days. The draft's provisional value is
  confirmed.**
  - Rule (`market-data` Ruling 5.3 item 6, new): a calendar's scheduled close is the **latest
    instant at which the session's official close can be determined**.
  - The HKEX closing auction ends at a random moment around 16:08–16:10, and an auction-eligible
    security's close is the auction price (MEMORY).
  - 16:00 is rejected: Current mode would treat a close as available ten minutes before it
    exists.
  - Per-security times are rejected: there is no eligibility list, and the gain is at most ten
    minutes.
  - Nothing in Ruling 1.2's ordering changes. This is calendar data. The owner registers it
    unchanged.
- **ECB concertation: the constant becomes 14:10 Europe/Berlin** (`market-data` Ruling 1.1 and §12
  item 1, applied as §12 item 1 already provided).
  - The ECB's own wording, "around 14:10 CET", as the main session read it for PD-0034, replaces
    my remembered 14:15.
  - Publication stays 16:00, which is the time Current mode uses.
  - The instant is a nominal label: no computation depends on the minute, and the hour figures of
    Ruling 1.2 are restated.
  - **Engineer impact:** the constant in `src/marketdata/profiles.py`, the Frankfurter and ECB
    adapters, and the calendar adapter's convention check. **Data impact:** the ECB calendar draft's
    `fixing.time` must say 14:10 (main session or owner; outside my write paths), and synthetic
    fixtures that carry 14:15 timestamps need updating.
- Also in `market-data/1.8`:
  - CNH aggregates become `INSUFFICIENT_DATA` (Ruling 1.4 here);
  - Ruling 4.7 item 3 is adopted;
  - MD-OI-1, 2 and 4 are closed;
  - MD-OI-11 becomes OD-P2.

---

## 14. Methodology registry entries (§33)

**Common to every entry below:**

- benchmark dependency: none;
- risk-free-rate dependency: none;
- frequency: valuation at the end of every calendar day (Ruling 5.1);
- lookback: the declared window `(B, E]`;
- implementation version: `performance/1.4` + `ledger-replay/1.3` + `market-data/1.10` + the lot
  method (`FIFO/1`) + the minor-unit table version;
- judgment class: Fact;
- wording: historical and descriptive only (P6).

Metric IDs are suggestions; the product contract names them.

| Metric (suggested ID) | Human definition | Formula | Annualization | Minimum data | Missing-data handling | FX treatment | Corporate actions | Known limitations |
|---|---|---|---|---|---|---|---|---|
| `value.position` | market value of a holding at the end of `D` | Rulings 1.1, 1.2 | none | a quantity and a print at or before `D` | per `market-data` states | fixing `u(D)`, exact cross | raw close and ledger splits; F8 conflict suppresses | non-simultaneous closes (disclosed instants) |
| `value.total` | total value incl. cash and receivables | Ruling 1.4 | none | every non-zero component valued | any unvalued component → `INSUFFICIENT_DATA` | as above | as above | suspended holdings (stale for 5+ sessions) suppress the total |
| `gain.absolute` | money gained over the window, excluding deposits and withdrawals | Ruling 5.1 | never | `V_B`, `V_E`, every flow | as the TWR | flows at the flow date's fixing | value-continuous | includes FX, income and costs; not a TWR in money |
| `return.twr` | time-weighted return in `R` | Rulings 5.1, 5.2 | separate metric | a valid window, required valuations | Ruling 5.5 | daily, in `R` | value-continuous | daily flow timing (Ruling 4.2); non-positive base is unsupported |
| `return.mwr` | money-weighted (internal) rate over the window | Ruling 6.1 | separate metric | as the TWR, plus a unique root | Ruling 6.4 | as the TWR | as the TWR | multiple roots are unsupported; snapshot portfolios: "since `S`" |
| `return.annualized` | constant yearly rate compounding to the window's result | Ruling 7.2 | `Y` from Ruling 7.1 | `Y ≥ 1` | `PERIOD_SHORTER_THAN_ONE_YEAR` | — | — | a historical average, not an expectation |
| `gain.realized` | proceeds minus relieved basis, per sale and over a window | Ruling 3.8 | never | relieved basis known | Ruling 3.10 | proceeds at the sale date; basis at the acquisition date | lots rescaled by splits | lot method (OD-P1); fees not capitalized; not a taxable gain |
| `gain.unrealized` | value minus remaining basis | Ruling 3.9 | never | as realized, plus valuation | Ruling 3.10 | value at `D`; basis at acquisition | as above | as above; transfer and snapshot lots need a recorded acquisition date for `R` |
| `income.amount`, `fees.amount`, `taxes.amount`, `financing.amount` | recorded income and costs over the window | §8 | never | the ledger | FX state of the event date | event-date fixing; accrued dividends at the ex-date | — | known taxes only; net-only dividends hide withholding |
| `attribution.money` / `attribution.return` | exact split of `G` / TWR into 8 lines | Rulings 9.1–9.4 | never | every day's valuation in `[B, E]` | Ruling 9.5 | daily, three-way split | split-adjusted start price | Southbound settlement rate against the ECB cross sits in the trade result; Cariño linking |
| `decomposition.since_acquisition` | how a lot's unrealized gain splits into local, FX and interaction | Ruling 9.7 | never | known basis and acquisition FX | as unrealized | acquisition date and `D` | as above | answers a different question from attribution |
| `basis.remaining` (1.5) | the cost of the units still held, by FIFO lot | Ruling 3.9a | never | every lot's basis known (`R`: and its acquisition-date FX) | Ruling 3.9a | `TRADE` lots at the acquisition date; `ENTRY` lots only if already in `R` | lots rescaled by splits; suppressed with the valuation | lot method; fees not capitalized; not a tax basis |

**(1.5)** The implementation version for every entry above is `performance/1.5` + `ledger-replay/1.4`
(`FIFO/1` mode) + `market-data/1.10` + `FIFO/1` + the minor-unit table version. The 1.4 line above
is the 1.4 record.

**(1.6)** The implementation version is now `performance/1.6` + `ledger-replay/1.5`. In the rows for
`gain.unrealized`, `basis.remaining` and `decomposition.since_acquisition`, "transfer and snapshot
lots need a recorded acquisition date for `R`" is now met by `acquired_on` (Ruling 3.7a). Without
it, those lots stay as described.

**(1.11)** The implementation version is now `performance/1.11` + `ledger-replay/1.5` (`FIFO/1`
mode) + `market-data/1.10` + `FIFO/1` + **`minor-units/1.1`**. No row's content changes.

**(1.12)** The implementation version is now `performance/1.12` + `ledger-replay/1.5` (`FIFO/1`
mode) + `market-data/1.11` + `FIFO/1` + `minor-units/1.1`. No row's content changes. The
Current-mode as-of rule (Ruling 1.7 (1.12)) is common to every row.

---

## 15. Owner decisions

**(1.1) OD-P1 to OD-P4 are decided in PD-0035, each as recommended:**

- OD-P1: FIFO, with the broker-difference caveat;
- OD-P2: a labelled "value of priced holdings" with its count, never the total (Ruling 1.4a);
- OD-P3: synthetic US/CN/HK plus a real US/ECB slice;
- OD-P4: the exact daily split supersedes HG1 §4.3.

The table below is the 1.0 record. **OD-P5 is new and open.**

### OD-P5 (1.1, open): reason codes for "zero denominator", "no sign change in the IRR flows" and "history too short"

> **(1.6) Decided (PD-0036 §2): option (a), "No new codes".** These results stay
> `INSUFFICIENT_DATA` with no reason code and the specific detail named below. `CALCULATION_ERROR`
> is never used for them. The text below is the 1.1 record.

The CP3a engineer raised this (tech plan §16.12 question 6). Under `performance/1.1` these are the
cases:

| Case | State today (Rulings 5.3, 5.4, 6.4, 7.2) | Lineage detail |
|---|---|---|
| zero or negative TWR base | `INSUFFICIENT_DATA`, no reason | `NON_POSITIVE_BASE` |
| IRR flows with no usable sign pattern | `INSUFFICIENT_DATA`, no reason | `IRR_NOT_DEFINED` (and `NO_CAPITAL`, `IRR_OUT_OF_RANGE`, `IRR_UNIQUENESS_NOT_ESTABLISHED`) |
| window before inception | `INSUFFICIENT_DATA`, no reason | `WINDOW_BEFORE_INCEPTION` |
| annualizing under one year | `INSUFFICIENT_DATA`, no reason | `PERIOD_SHORTER_THAN_ONE_YEAR` |

**The options:**

- **(a) No new codes.** Keep `INSUFFICIENT_DATA` with no reason, plus the lineage detail. The
  detail names are part of `performance/1.1`, and the design and AI layer explain them from the
  registry.
- **(b) Add one code, `INSUFFICIENT_HISTORY`**, for the two history cases (before inception;
  under one year). The other two stay detail-only.
- **(c) Add a code per case.**

**Recommendation: (a).**

- PD-0006 already makes "not enough observations" a complete answer without a code. PRD §32's own
  example ("3Y Beta — N/A. Insufficient weekly observations.") has none.
- Each case's remedy is specific, so a shared code would not tell the user more than the detail
  already does. For example: "record the deposit on the trade date"; "choose a since-inception
  window"; "the window is under one year".
- Every code added so far (PD-0025, PD-0030) named a **data or ledger condition** that crosses
  metrics. These four are properties of one method's domain.
- (b) is the fallback if the CP7 design finds it cannot render a clear explanation from the detail
  alone.

**Until decided,** (a) is in force. `CALCULATION_ERROR` is never used for these, because it is an
engine fault (HG1 R2).

| ID | Question | Options | Recommendation | Until decided |
|---|---|---|---|---|
| **OD-P1** | Lot-relief method for realized and unrealized gain (reserved to the Quant by PD-0021 §9; put to the owner because it is user-visible) | **A** FIFO portfolio-wide; **B** daily average cost portfolio-wide; **C** per-account method chosen by the user (default A) | **A**, labelled "first in, first out; may differ from your broker's statement" | multi-lot cases are `UNRESOLVED_CONVENTION` (as now); every method-independent figure is computed |
| **OD-P2** | When the total is `INSUFFICIENT_DATA` because some holdings are unvalued, should a separate "value of priced holdings" metric exist (MD-OI-11)? | **(a)** no, strict; **(b)** yes: a distinct metric with its own label, the count and list of unpriced holdings with their native quantities, never shown in the total's place, never used as a denominator | **(b)**. Without it, one suspended A-share or one CNH balance leaves the dashboard with no money figure at all. The label and placement are design work. | strict: no partial figure |
| **OD-P3** | HG2 data (STATUS item 17) | (a) synthetic multi-market plus real US/ECB portfolio; (b) a personal-use paid CN/HK source first; (c) written permission | **(a)**, knowing CN/HK real-price behaviour stays unproven until OQ-04b; revisit (b) before CP4/HG3 | nothing blocks CP3 build; synthetic fixtures carry CP3's exit |
| **OD-P4** | Confirm that §9's daily Cariño-linked attribution supersedes HG1 round 4 §4.3's portfolio-level constant-FX definition, so the HG1 prototype waterfall's first bar ("local-market return, FX held at window-start rates") becomes "local price effect" (Ruling 9.8) | **(a)** confirm; **(b)** keep the HG1 two-run FX effect, and attribute income, fees and taxes inside the constant-FX run (conversions and Southbound trades are then partly mislabelled, Ruling 9.8) | **(a)** | the engineer builds §9 as written. The design labels are CP7 work. |

**Also for the owner's awareness (no decision needed now):**

- **Suspended holdings.** The freshness rule of HG1 round 4 §5.4 (5 or more sessions gives
  `INSUFFICIENT_DATA`) means a long A-share suspension suppresses the total value, and every TWR
  whose flow dates fall in the suspension. Exchanges and funds often value suspended securities by
  a fair-value policy. Specifying one would be a new methodology ruling. Say if it is wanted
  before HG2.
- **Snapshot portfolios** never show a reporting-currency unrealized gain for foreign-currency
  holdings without a recorded acquisition date (Ruling 3.7, PF-1).

---

## 16. What the engineer must build, and must not decide

**Must build** (Write/Edit only; tech plan section to be written by the engineer):

1. **Valuation** per Rulings 1.1–1.8. This includes `D_c(t)` for Current mode, the freshness vector
   and the reason priority. **Quantity-zero positions are never priced.**
2. **Tier-E arithmetic:** `Fraction` for every money amount, quantity, rate and return. `Decimal`
   at `prec` 50, `ROUND_HALF_EVEN`, only for `ln` and `exp` (IRR, annualization, Cariño). **No
   float anywhere.** Nothing reads a tier-P value.
3. **Tier-P quantization** per Ruling 2.2. The **minor-unit table** is a versioned data file with
   status per row (Ruling 2.3), and a missing currency fails closed.
4. **Largest-remainder apportionment** for every published decomposition (Ruling 2.4), with ties
   broken in registry line order. Exact parts are kept in the Proof Packet lineage.
5. **(1.1) FIFO** (Ruling 3.3), `FIFO/1`, as a mode of the single lot fold. Its "none" mode stays
   `ledger-replay/1.3`. Average cost (Ruling 3.4) is not required. Lots belong to part 3 of the
   fixture.
5a. **(1.1) "Value of priced holdings"** (Ruling 1.4a), with its excluded count and list. It is
    emitted only when the total is suppressed by unvalued components, and is never used by
    anything else.
6. **Lot attributes:** the acquisition date, carried through internal transfers; the basis
   currency; known or unknown; and the reporting-currency unit cost at the acquisition-date fixing,
   with its state (Ruling 3.7).
7. **Realized and unrealized gain**, per sale, per position and as aggregates, with the stated
   excluded weights (Rulings 3.8–3.10).
8. **Flow classification and timing** (§4), at portfolio and account scope.
9. **TWR** in segment form, plus the daily product as a check when daily values exist (§5). Windows
   use the end-of-month rule. The window declaration travels with every value.
10. **MWR** exactly as Ruling 6.2: the bracket rule, bisection, the stop rule and the
    pure-investment test.
11. **Annualization** per §7: the calendar-month year fraction, and only for `Y ≥ 1`.
12. **Income** recognition with ex-date accrual (Ruling 8.1), and the eight lines of §8–§9.
13. **Attribution:** the daily three-way split, trade results, Cariño linking, the per-holding
    breakdown, and the since-acquisition decomposition (§9).
14. **The runtime identities of Ruling 11.1.** A failure gives `CALCULATION_ERROR`.
15. **`market-data/1.8`**: the ECB constant 14:10 everywhere it appears (profiles, adapters, the
    calendar check), and CNH aggregates as `INSUFFICIENT_DATA`.
16. **Manifests** cite `performance/1.4`, `ledger-replay/1.3`, `market-data/1.10`, the lot method
    (`FIFO/1`) and the minor-unit table version.
    - **(1.5)** They now cite `performance/1.5` and `ledger-replay/1.4` (the `FIFO/1` mode) in place
      of `performance/1.4` and `ledger-replay/1.3`.
    - Also to build in 1.5:
      - the `FIFO/1` mode of the one lot fold, as specified in `ledger-replay/1.4` Ruling 0.5 (its
        build notes are §11B there);
      - Ruling 1.1a, the lot-book taint, replacing the conservative rule;
      - Ruling 3.8 (1.5), the sale-level states;
      - Ruling 3.9a, `basis.remaining`;
      - Ruling 3.10 (1.5), the aggregates;
      - Ruling 9.7 (1.5), the line names;
      - `cp3_golden` part 3, wired as parts 1 and 2 are.
    - **(1.5) Detail and line names added:** `LOCAL_AT_ACQUISITION_FX`, `FX_ON_COST`,
      `INTERACTION`. `UNKNOWN_BASIS`, `ACQUISITION_DATE_UNKNOWN` and `MIXED_CURRENCY_BASIS` are
      confirmed for the gain and basis metrics.
    - **(1.6)** They now cite `performance/1.6` and `ledger-replay/1.5`.
    - Also to build in 1.6:
      - the date kind `RECORDED` (`ledger-replay/1.5` Ruling 0.6, build note B9);
      - Ruling 3.7a, the acquisition-date FX at `acquired_on`, with `MISSING_FX_HISTORY` before
        coverage;
      - `cp3_golden/1.1-part3`'s P20.
    - **(1.6)** The date kind values exposed are `TRADE`, `ENTRY` and `RECORDED`.
    - **(1.12)** Manifests cite `performance/1.12`, `market-data/1.11` and `minor-units/1.1`.
      - **To build:** Ruling 1.7 (1.12) item 2 in `choose_current_date`.
        - Add to the exchange set the MIC of every listing named by a live event dated `day`.
        - Set `foreign` when a live event dated `day` carries an amount, or names a listing,
          whose currency is not `R`. An unknown currency counts as foreign, as now.
        - Test Example 1.7-C, both rows (withdrawal and in-kind), as `D_c` = 2026-10-01.
      - **The calendar check:** assert for every registered calendar that its scheduled close
        (or publication) falls on the same UTC date as its local session date (Ruling 1.7 (1.12)
        item 1). A calendar that fails is a finding for the Quant, not something to absorb.
      - **The `market11.UNBUILT` item** "not built: Current mode (instant t) for prices and FX
        (Rulings 1.6, 2.2 item 6, 5.2): historical mode only":
        - **The ruling:** Current mode for market data is built when (i) `D_c(t)` is chosen by
          Ruling 1.7 (1.12), (ii) every CP2 step runs over `M_t` (Ruling 1.7 (1.2)), and (iii)
          the date-taking policies are applied at `D_c(t)`. The policies need not take `t`.
        - **Until item 2 above is built,** reword it to: "Current mode: `D_c(t)` does not yet
          test events dated `D` (`performance/1.12` Ruling 1.7 item 2)". The gap is real
          (Example 1.7-C).
        - **Then close it** (remove it), provided (ii) holds. Whether every CP2 step runs over
          `M_t` (`derived_release`) is for the reviewer to confirm. This document does not
          assert it.
        - **(1.12, folded) What the item's closure waits on.** Review §33.6 confirms (ii) for
          every step that reads a file. The source registry and the identity registry are outside
          (ii) by Ruling 1.7 (1.12) item 4, so they do not hold the item open. Close the item when
          both of these are built and tested:
          - Ruling 1.7 (1.12) item 2 (Example 1.7-C);
          - item 5 (CP4-2: a Current-mode refusal records `t`, `M` and `M_t`).
      - **(1.12, folded) `source_registry_digest`** (Ruling 1.7 (1.12) item 4), in **every**
        Computation Manifest, in both modes.
        - It is the SHA-256 of the canonical JSON of the full `SourceRecord`s, every field
          including `terms_check`, for every source with a file in the `M` read (`M_t` in Current
          mode), sorted by `source_id`.
        - `reproduce()` compares it as it compares `identity_digest`, and reports a difference.
        - This is a both-mode reproducibility requirement, not a Current-mode one. Until it is
          built, list it as a performance open item; `is_conformant` is then False.
      - **(1.12, folded) The money exponent** (Ruling 2.2 (1.12)):
        - In `numerics.present`, `PRESENT_FACT` with a currency gets exactly
          `max(minor_unit(k), d(v))` decimals, never rounding. `d(v)` is the least `n` with
          `v × 10^n` integral.
        - With a currency outside the table: the shortest exact form, plus lineage detail
          `CURRENCY_NO_MINOR_UNIT`, state unchanged.
        - Without a currency (quantities): the shortest exact form, as now.
        - `REPORTING` stays derived (`PRESENT_MONEY`), including amounts already in `R`.
        - The test `test_a_recorded_fact_is_presented_exactly` should expect `"2.50"` for a USD
          `2.5`. Add cases for `0.125` USD → `"0.125"`, JPY `5000` → `"5000"`, JPY `12.5` →
          `"12.5"`, `0` USD → `"0.00"`, and a recorded `2248.0000` → `"2248.00"`.
      - **(1.12 build note, after the round-2 implementation.)** This note changes no RULING
        text, so `performance/1.12` keeps its id. It gives the reading of two clauses the round
        implemented differently.
        - **`valuation_mode` (Ruling 1.7 (1.12) item 5).**
          - **"valuation_mode Current" means a value that names PD-0015 Part 1's Current /
            Latest mode.** It applies to **every** result of a Current-mode request, computed or
            refused. Item 5 calls a refusal "a Current-mode result" because computed ones already
            are.
          - **`HISTORICAL_AS_OF` does not meet it.** PD-0015 defines Historical as-of as a
            portfolio evaluated at "a specific historical cutoff" the caller chooses. A
            Current-mode `D` is chosen by the engine from `t`.
          - **Item 1's composition is about mechanics, not the label.** It applies the
            historical-mode **market-data rules** at `D_c(t)`. That is how the result is computed.
            The mode is what was asked.
          - **`as_of_rule` alone is not enough.** A reader of `valuation_mode` must never be
            told "historical" for a Current result (P9).
          - **`CURRENT_LIVE` stays as it is:** live or delayed inputs, refused, with no live
            source admitted. The Current mode on end-of-day data needs its own value. The
            identifier is the engineer's choice; `CURRENT_AS_OF_INSTANT` is fine.
          - **The manifest invariants:**

            | `valuation_mode` | `as_of_rule` | `instant` | `parent_release_id` |
            |---|---|---|---|
            | `HISTORICAL_AS_OF` | `CALLER` | null | null |
            | the Current value | `D_c(t)` | `t` | `M` |

            Any other combination is an engine fault.
        - **`source_registry_digest` (Ruling 1.7 (1.12) item 4).**
          - **Item 4 defines the digest as the SHA-256 of the canonical JSON of the records of
            the sources with a file in the `M` read.** So:
            - **An empty source set** (no market-data file read) has a definite digest: the
              SHA-256 of the canonical JSON of the empty list. It is never `""`.
            - **Files read, and their sources' records not all available:** the item cannot be
              met, so the computation **fails closed**. No value is presented. This includes a
              caller that omits the registry from `PostgresMarketData.read_release`, and a
              registry missing a record for a source in `M`.
              - A configuration error may raise, as a missing calendar set does today. It must
                never produce a manifest with an unpinned registry.
              - A file whose source has no record cannot be shown to have passed the terms check
                at use (`market-data` Ruling 4.7). The reviewer should confirm that the
                PostgreSQL read path applies that check, or refuses, when the registry is
                omitted.
            - **`""` never appears in a 1.12 manifest.**
          - **`reproduce()` and `""`.** No stored manifest carries `""`. If one is met, or either
            side is `""` or missing:
            - the registry check **cannot run**, and a check that cannot run is not a pass
              (Ruling 11.1 (1.2));
            - `""` against `""` is **not** a match;
            - report `SOURCE_REGISTRY_MISMATCH` with the note "registry not pinned". The outcome
              is never `REPRODUCED` or `RESULT_NOT_COMPARED`.
          - **Test doubles** that serve observations from files must supply those sources'
            records. A double that reads no file gets the empty-list digest.
        - **This does not affect `performance.is_conformant`.** The market-data set's
          `is_conformant` tests placeholders only, but the item stays visible in manifests while
          it is listed.
    - **(1.11)** Manifests cite `performance/1.11` and the minor-unit table **`minor-units/1.1`**.
      Nothing new is built.
      - **The table** (Ruling 2.3, 1.11): status `CONFIRMED` for USD, HKD, CNY, EUR, GBP, CHF,
        SGD, AUD, CAD and JPY, with the same minor units. CNH stays `DECLARED`.
      - **Keep the open-item rule:** a `MEMORY` row is an open item, and a `DECLARED` or
        `CONFIRMED` row is not. With no `MEMORY` row, the table contributes no open item. A
        currency added later as `MEMORY` re-opens it.
      - **The HG2 open item closes.** The engine lists "HG2 evidence pack: built … the gate
        decision is the owner's. Identity I-7 (method independence) runs in the test suite and the
        evidence pack only (Ruling 11.1 (1.2))". It names no unbuilt rule:
        - the evidence pack is built (§11.4, §12);
        - the gate is decided: HG2 was APPROVED WITH CONDITIONS (PD-0038);
        - I-7 runs where Ruling 11.1 (1.2) requires it (the test suite, the fixtures and the HG2
          pack), so its absence from a product call is conformant, not a gap.

        So it is **removed**, not reworded into another open item. An open item means "a rule of
        this convention is not built", and this one no longer is one. Where I-7 ran is reported in
        lineage, which records which identities ran (Ruling 11.1 (1.2)).
      - **Then this convention names no rule as unbuilt.** Whether the engine implements each
        ruling correctly is a question for review and the fixtures, not for the open-items list.
        These are not open items:
        - Ruling 3.4 (average cost): specified, and not required (item 5);
        - §3.11 (fractional splits): not ruled, and reserved (OI-P1). It fails closed through
          `ledger-replay` §7;
        - OD-P5: decided, with no new codes.
    - **(1.10)** Manifests cite `performance/1.10`. Breakdown grouping keys follow Ruling 9.6
      (1.10)'s table:
      - receivables go to their dividend's listing and market;
      - event lines go to their listing, else `none`, and to their event currency, with the
        component kind `event`;
      - conversion results are `none` except by account and component;
      - `market` is the listing's MIC.
    - **(1.9)** Manifests cite `performance/1.9`. Also to build in 1.9:
      - `last_print_date` in holding lineage (Ruling 1.1b);
      - money attribution not suppressed by base or value conditions (Ruling 9.5 (1.9));
      - breakdowns apportioned to the line's display value, with the order, zero-part and `none`
        rules (Ruling 9.6 (1.9));
      - re-wiring part 4 to `cp3_golden/1.2-part4`.
    - **(1.8)** Manifests cite `performance/1.8`. Fixture checks accept that version for any fixture
      whose minimum `performance` version is earlier (Ruling 11.6).
    - **(1.7)** Manifests cite `performance/1.7`. The attribution line identifiers are those of
      Ruling 9.2 (1.7), from `attr.price` to `attr.conversion`, and they are used in every output
      that names a line.
17. **Lineage detail names.** (1.1) These are fixed by `performance/1.1`, because the fixture
    asserts them. A rename is a convention change, made by the Quant. Also added: `NO_LIVE_LEDGER_EVENTS`,
    `PRESENTATION_TIE`, `SPLIT_NOT_APPLIED` (Example V-2a). (1.1, from the change note)
    `NEGATIVE_VALUE`, `WINDOW_NOT_POSITIVE`, `WINDOW_BEFORE_SNAPSHOT`, `NO_VALUED_COMPONENT`. (1.2)
    `STALE_SHARE_UNDEFINED`, and `NEGATIVE_GROWTH_FACTOR` (with `CALCULATION_ERROR` only).
    - `NON_POSITIVE_BASE`, `ZERO_CAPITAL_RUN`, `WINDOW_BEFORE_INCEPTION`;
    - `PERIOD_SHORTER_THAN_ONE_YEAR`, `TOTAL_LOSS`;
    - `NO_CAPITAL`, `IRR_NOT_DEFINED`, `IRR_OUT_OF_RANGE`, `IRR_UNIQUENESS_NOT_ESTABLISHED`;
    - `MIXED_CURRENCY_BASIS`, `ACQUISITION_DATE_UNKNOWN`, `INCOME_CASH_BASIS`;
    - `CURRENCY_NO_MINOR_UNIT`;
    - the existing `LOT_DEPLETION` and `UNKNOWN_BASIS`.
18. **The fixture loader and checker** for `cp3_golden`, once the format is agreed (§11.5), with
    `FIXTURE_PINS` as in CP1-D.

**Must not decide:**

- the lot-relief method (decided: FIFO, PD-0035), or any variation of it;
- fee capitalization;
- flow timing;
- window arithmetic;
- the year fraction;
- the annualization threshold;
- the solver, its bracket, stop rule or uniqueness test;
- the linking method;
- the assignment of any event to an attribution line;
- the reason priority;
- any rounding mode, quantum, minor unit or tolerance;
- any display precision;
- whether a "value of priced holdings" metric exists (OD-P2);
- design labels (OD-P4).

**And must never:**

- use a float;
- fall back to Modified Dietz or any approximation when a required valuation is missing;
- translate at a user's conversion rate, or at another date's rate;
- use a CNY rate for CNH;
- weight an unvalued holding by cost or by a stale price;
- annualize a period under one year;
- compute from a presented (tier-P) value;
- present a partial total as the total.

---

## 17. Findings and recommendations for other owners

| ID | For | Finding or recommendation |
|---|---|---|
| PF-1 | PM, engineer (ledger) | Add an **optional `acquired_on` date** to `OPENING_POSITION` and external security `TRANSFER_IN`, recorded and never inferred. Without it, a foreign-currency lot's reporting-currency basis is `MISSING_COST_BASIS` (Ruling 3.7). Like `ex_date` (F5), it cannot be truthfully backfilled into an append-only ledger later. |
| PF-2 | PM, engineer (ledger; F9) | Add an **optional `related_event_id`** on `FEE` and `TAX`, naming the trade or dividend it belongs to. That would make capitalization a possible later option (Ruling 3.6), and per-trade cost display exact. |
| PF-3 | engineer | Make the lot-relief method a **parameter of the one lot fold**, not a second lot engine in CP3. "None" reproduces `ledger-replay/1.3` exactly, and FIFO or AVCO is used by CP3 (Ruling 3.2). Each lot's acquisition date must survive internal carries. |
| PF-4 | main session, owner | ECB calendar draft: set `fixing.time` to 14:10. HKEX draft: 16:10/12:10 is confirmed (§13). |
| PF-5 | designer (CP7) | Decomposition views use the engine's apportioned values (Ruling 2.4). The HG1 waterfall labels change under OD-P4. A since-acquisition view (Ruling 9.7) and the period attribution (§9) must not share an "FX effect" label without saying which question each answers. |
| PF-6 | Quant, at CP4 (max-drawdown debt) | **Overlap only, not ruled here.** A drawdown should use CP3's window `(B, E]`, its base point `B` (HG1 M1 RULING 1(a)) and the calendar-day wealth index `W_D`. Whether the peak search includes `B` is the open debt's item 2. CP3 defines `W_D`, not drawdown. |

---

## 18. External facts from memory (to be confirmed by the human)

None of these is asserted as verified. I have no network access here.

1. **(1.11) Closed: confirmed by the owner (PD-0037).** The 1.0–1.10 text was: "ISO 4217 minor
   units: USD, HKD, CNY, EUR, GBP, CHF, SGD, AUD and CAD have 2; JPY has 0. Confirm against the SIX
   ISO 4217 list." The SIX List One published 2026-09-17 gives exactly those values. The table is
   now `minor-units/1.1` (Ruling 2.3). The number is kept so that later references to items 4 and
   5 stay valid.
2. **HKEX closing auction session:** 16:00 to a random close at about 16:08–16:10. The half-day
   session runs to about 12:10. Auction-eligible securities close at the auction price; others at
   a value derived from the last minute of continuous trading.
3. **ECB:** concertation "around 14:10 CET". This was read from the ECB page by the main session,
   not by me. Publication is around 16:00 CET.
4. **Decimal `exp` and `ln`** are correctly rounded (`ROUND_HALF_EVEN`) under the General Decimal
   Arithmetic specification, which Python's `decimal` and libmpdec implement.
5. **Euro-conversion rounding:** Council Regulation (EC) No 1103/97, Article 5, rounds a result
   exactly halfway up. It is cited as precedent for half-away-from-zero only.
6. **Broker displays:** Mainland and HK brokers typically show an average cost per holding;
   US brokers default to FIFO lot relief for stocks absent a specific-lot election.
7. **GIPS 2020:**
   - consistent treatment of external cash flows;
   - valuation at large cash flows for composites;
   - returns for periods under one year must not be annualized;
   - recommends accruing dividends from the ex-date.
8. **Teichroew, Robichek and Montalbano (1965):** a pure investment has a unique IRR. The proof in
   Ruling 6.3 does not depend on the citation.
9. **Cariño (1999),** "Combining attribution effects over time", *Journal of Performance
   Measurement*: the logarithmic linking coefficients of Ruling 9.4.

---

## 19. Open issues

- **OI-P1.** The fractional-split convention, still reserved (§3.11). It is needed before a
  non-integral split can be valued.
- **OI-P2.** Taking a ledger dividend's ex-date from the corporate-action feed, by a join on
  (listing, pay date). Later. It needs a join rule and a conflict rule.
- **OI-P3.** A fair-value rule for suspended securities (§15 note), if the owner wants one.
- **OI-P4.** Holding-level TWR (a position's own time-weighted return) is not defined in CP3.
  Per-holding contributions (Ruling 9.6) cover attribution. Holding returns from adjusted prices
  are CP4 (MD-OI-3).
- **OI-P5.** The performance cost of exact rationals over long daily windows. I expect it to be
  acceptable: a 3-year daily chain of ratios with numerators and denominators of tens of digits.
  If the engineer measures a problem, it comes back here. It is not to be solved by switching to
  floats or fixed precision unilaterally.
- **OI-P6.** Intraday or live prices (OQ-04b) would need a Current-mode rule for a session in
  progress. `D_c(t)` currently excludes it by construction.
- **OI-P7.** CNH (OQ-04b, PD-0030 §3).
- **OI-P8.** Lot-method-keyed fixture values become single-valued once OD-P1 is decided
  (`performance/1.1`).
- **OI-P9, restated in 1.6.** The relabel is now to `performance/1.6` and `ledger-replay/1.5`. Part 3
  is already relabelled (`cp3_golden/1.1-part3`). The 1.5 text follows.
- **OI-P9 (1.5).** `cp3_golden` parts 1 and 2 cite `performance/1.4` and `ledger-replay/1.3`. Once
  the engine cites `performance/1.5` and `ledger-replay/1.4`, each needs a wording-only relabel of
  `convention_sets` and a re-pin. None of their expected values depends on 1.5.
- **OI-P11 (1.8): closed** by Ruling 11.6. `convention_sets` are minimum versions. No relabel is
  needed. The 1.7 text follows.
- **OI-P11 (1.7).** No expected value in parts 1–3 depends on 1.7. Their `convention_sets` cite
  `performance/1.6`. Their S-1, S2-1 and S3-1 ("every manifest cites the ids in `convention_sets`")
  will therefore fail once the engine cites 1.7, unless they are relabelled, wording only, or the
  check accepts 1.6 for them. That is for the PM to decide. Part 4 cites 1.7.
- **OI-P10 (1.6): answered.** PD-0036 §1 adds `acquired_on`, and Ruling 3.7a and
  `ledger-replay/1.5` Ruling 0.6 specify how it is used. The 1.5 text follows.
- **OI-P10 (1.5).** PF-1, a recorded acquisition date on opening positions and external transfers
  in, now has two effects (`ledger-replay` OI-11): FIFO order, and reporting-currency basis.
