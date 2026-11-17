# CP1 golden fixture `cp1_golden/1.1`: hand derivation and ratification

> **1.1 (2026-09-30).** This version changes loader metadata and observability only. **No
> expected value changed.** It adds `atomic_group` "transfer-E6" on seq 6 and 7. In S1, `detail`
> is no longer asserted on three values, and `snapshot_date` is asserted. The reasoning is in §7.
> The 1.0 ratification in §6 carries over unchanged to 1.1.

**Author:** `quant-analyst` subagent, 2026-09-30, dispatched by the main session for CP1-D.
**Fixture file:** `methodology/fixtures/cp1_golden/cp1_golden_fixture.json`.
**Convention set:** `ledger-replay/1.3` (`methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md`).
**Authority:**

- PD-0011 Priority D (a permanent regression asset);
- PRD §38.6 (method and implementation come from different identities);
- PD-0021 §9 (the fixture avoids unresolved conventions);
- PD-0024 (the two new event types);
- PD-0025 (reason codes; `Decimal` values);
- PD-0026 (numeric bounds);
- B0b plan §11 and the "Package CP1-D" row.

## 0. Independence: what I read, and what I did not

- **Read, for event validity only:** `src/domain/ledger.py`, specifically the `EventType`
  names, `LedgerEvent` field names and `FIELD_RULES`.
- **Read, for vocabulary only:** the names of the `ReasonCode` members
  (`src/product_contract/vocabulary.py`) and of the `ReplayDetail` members (`src/domain/replay.py`,
  lines 180–201, the enum and its comments). I read them so the fixture uses the implementation's
  vocabulary without guessing.
  - The detail-to-reason mapping in those comments agrees with the conventions I wrote:
    - `BASIS_NOT_EXACT` maps to `UNRESOLVED_CONVENTION` (OI-8);
    - `UNKNOWN_BASIS` maps to `MISSING_COST_BASIS`;
    - `LOT_DEPLETION` maps to `UNRESOLVED_CONVENTION`;
    - `BEFORE_SNAPSHOT` maps to `NOT_RECONSTRUCTABLE`.
  - I would have ruled the same way independently.
- **Not read, and not run:** the fold and output code of `replay.py`, its tests, the replay store,
  and any replay output. **No expected value in this fixture comes from executing
  `src/`.** Every value below is derived by hand from the events.
- **One tool use.** I ran `python3 -c "json.load(...)"` on the fixture file only, to check that
  it is valid JSON with sequential `ledger_seq` and unique event IDs. That is not a computation of
  any expected value.

## 1. Scope and exclusions (PD-0021 §9)

| Reserved or unresolved item | How the fixture avoids it |
|---|---|
| Lot-depletion method | Every basis asserted after a depletion comes from a **single candidate lot** (Ruling 0.4.3 case 3, 0.4.5 (a)): T7, V4. The one multi-lot depletion (V3) is asserted **as unresolved**. |
| Fee capitalization (§0.2 note 1) | The only `FEE` (X2) has no `listing_id` and is a conversion commission. No listing-attributed `FEE` or `TAX` exists on any date. |
| Fractional-split convention (§7) | The only `SPLIT` (E5, 4:1 on 50) is integral. There are no same-day split pairs. |
| Income treatment | No `DIVIDEND`, and no `INTEREST` credit. `INTEREST_CHARGED` is asserted as a cash fact only. |
| Money rounding (OI-8) | Every asserted basis terminates exactly. |
| Return denominators and flow classification | Not asserted. Replay does not classify flows. T6's "neutral" is proven through portfolio cash only. |

**PD-0026 bounds.** Every numeric value is below 10^30 with scale at most 24.

- The largest absolute value is 20,000 (E3).
- The largest scale is 2 (X6: 3.50).
- The largest expected value is 17,500 (T3).
- Split components are 4 and 1.

## 2. The ledger

Listings:

| Listing | Venue | Currency |
|---|---|---|
| AAPL | XNYS | USD |
| 0700 | XHKG | HKD |
| MSFT | XNYS | USD |

### Portfolio P1 (reporting USD; accounts A1 US, A2 HK, A3 US)

E1–E8 are B0b §11.1 verbatim. E6 is recorded as its two legs, and E8 is explicitly external (no
counterparty), as §10 of the conventions requires. X1–X16 are additions, all dated after
2025-03-11, so they cannot move any T1–T8 value.

| seq | Label | Date | Account | Event |
|---|---|---|---|---|
| 1 | E1 | 2025-01-02 | A1 | DEPOSIT 10,000 USD |
| 2 | E2 | 2025-01-06 | A1 | BUY AAPL 50, 7,500 USD |
| 3 | E3 | 2025-01-06 | A2 | DEPOSIT 20,000 HKD |
| 4 | E4 | 2025-01-08 | A2 | BUY 0700 500, 17,500 HKD |
| 5 | E5 | 2025-02-03 | A1 | SPLIT AAPL (4, 1) |
| 6 | E6-out | 2025-02-10 | A1 | TRANSFER_OUT 1,000 USD, counterparty A3 |
| 7 | E6-in | 2025-02-10 | A3 | TRANSFER_IN 1,000 USD, counterparty A1 |
| 8 | E7 | 2025-03-03 | A1 | SELL AAPL 50, 2,250 USD |
| 9 | E8 | 2025-03-10 | A1 | TRANSFER_IN MSFT 10, no counterparty, no cost_basis |
| 10 | X1 | 2025-04-02 | A1 | CURRENCY_CONVERSION 1,000 USD → 7,780 HKD (to be corrected) |
| 11 | X2 | 2025-04-02 | A1 | FEE 2 USD (no listing) |
| 12 | X3 | 2025-04-02 | A1 | BUY 0700 200, 7,000 HKD |
| 13 | X4 | 2025-05-05 | A3 | BUY MSFT 5, 2,000 USD |
| 14 | X5 | 2025-05-08 | A3 | DEPOSIT 1,000 USD |
| 15 | X6 | 2025-05-31 | A3 | INTEREST_CHARGED 3.50 USD |
| 16 | X7 | 2025-04-10 | A1 | REVERSAL of X1 (atomic with seq 17) |
| 17 | X8 | 2025-04-02 | A1 | CURRENCY_CONVERSION 1,000 USD → 7,750 HKD, corrects X1 |
| 18 | X9 | 2025-06-02 | A3 | DEPOSIT 5,000 USD |
| 19 | X10 | 2025-06-03 | A3 | BUY MSFT 5, 2,100 USD |
| 20 | X11 | 2025-06-10 | A3 | SELL MSFT 4, 1,720 USD |
| 21 | X12 | 2025-06-16 | A1 | SELL AAPL 40, 2,000 USD |
| 22 | X13 | 2025-06-16 | A1 | TRANSFER_OUT AAPL 110, counterparty A3 |
| 23 | X14 | 2025-06-16 | A3 | TRANSFER_IN AAPL 110, counterparty A1, no cost_basis |
| 24 | X15 | 2025-06-20 | A2 | DEPOSIT 500 HKD (erroneous) |
| 25 | X16 | 2025-06-25 | A2 | REVERSAL of X15 (no replacement) |

### Portfolio P2 (reporting HKD; account B1, snapshot-only)

| seq | Label | Date | Event |
|---|---|---|---|
| 1 | S-POS | 2025-06-30 | OPENING_POSITION 0700 500, no cost_basis |
| 2 | S-CASH | 2025-06-30 | OPENING_CASH 3,000 HKD |
| 3 | S-SELL | 2025-07-02 | SELL 0700 200, 7,400 HKD |

P2 is a separate portfolio on purpose. With the snapshot account inside P1, every P1
portfolio-level total before 2025-06-30 would correctly be `NOT_RECONSTRUCTABLE`, and B0b T6
would stop testing what it is meant to test.

## 3. Hand-kept running state (P1, at `L = 25` unless stated)

Live-event set at `L = 25`: every event except X1 (reversed by X7) and X15 (reversed by X16). The
REVERSAL rows X7 and X16 contribute nothing (Ruling 2.1).

**A1 USD cash:**

| After | Event | Balance |
|---|---|---|
| 2025-01-02 | E1 +10,000 | 10,000 |
| 2025-01-06 | E2 −7,500 | 2,500 |
| 2025-02-10 | E6-out −1,000 | 1,500 |
| 2025-03-03 | E7 +2,250 | 3,750 |
| 2025-04-02 | X8 (the live conversion) −1,000, X2 −2 | 3,750 − 1,000 − 2 = **2,748** |
| 2025-06-16 | X12 +2,000 | **4,748** |

At `L = 15`, X1 replaces X8 on 2025-04-02. Its sold side is the same 1,000, so USD is also 2,748.

**A1 HKD cash** (on 2025-04-02):

- At `L ≥ 17`: X8 +7,750, X3 −7,000, giving **750**.
- At `L = 15`: X1 +7,780, X3 −7,000, giving **780**.
- Before 2025-04-02: 0.

**A2 HKD cash:**

| After | Event | Balance |
|---|---|---|
| 2025-01-06 | E3 | 20,000 |
| 2025-01-08 | E4 −17,500 | **2,500** |

At `L = 24` from 2025-06-20, X15 +500 gives **3,000**. At `L = 25`, X15 is reversed and the balance
is **2,500** at every `D`.

**A3 USD cash:**

| After | Event | Balance |
|---|---|---|
| 2025-02-10 | E6-in +1,000 | 1,000 |
| 2025-05-05 | X4 −2,000 | **−1,000** |
| 2025-05-08 | X5 +1,000 | **0** |
| 2025-05-31 | X6 −3.50 | **−3.50** |
| 2025-06-02 | X9 +5,000 | 4,996.50 |
| 2025-06-03 | X10 −2,100 | **2,896.50** |
| 2025-06-10 | X11 +1,720 | **4,616.50** |

X13 and X14 are security-form transfers and move no cash.

**Positions and lots:**

- **A1 AAPL** is one lot, from E2: `u` = 50, `c` = 7,500/50 = 150.
  - E5 (4:1), start of 2025-02-03: `u` = 50 × 4/1 = 200, `c` = 150 × 1/4 = 37.5. Basis
    37.5 × 200 = 7,500, unchanged.
  - E7 on 2025-03-03: the candidate set is one lot, with no same-day acquisition. `u` = 150,
    basis 37.5 × 150 = **5,625**.
  - 2025-06-16: the candidate set is still that one lot, and there is no AAPL acquisition in A1
    that day. `U` = 150. X12 sells 40 and X13 moves 110, so `q_dep` = 150 = `U` and A1 ends at 0
    (0.4.3 case 2). By 0.4.5 (a) the out-leg carries 110 × 37.5 = **4,125** to A3.
- **A2 0700** is one lot, from E4: 500 units, basis 17,500 HKD.
- **A1 0700** is one lot, from X3: 200 units, basis **7,000 HKD**, which is the event currency
  (§0.3, 5A-A).
- **A1 MSFT** is one lot, from E8: 10 units, **unknown** basis (external, no cost_basis; §6.4).
- **A3 MSFT:**
  - lot 1 from X4: 5 units at `c` 400 (2,000);
  - lot 2 from X10: 5 units at `c` 420 (2,100);
  - total before any sale: **4,100**;
  - X11 sells 4 on 2025-06-10, from a candidate set of two lots, so the basis is **unresolved**
    (0.4.3 case 4). Quantity 10 − 4 = **6**.
- **A3 AAPL:** the carried lot from X14 is 110 units at `c` 37.5, basis 4,125.

**Portfolio quantities:**

- 0700 = A1 200 + A2 500 = **700** (from 2025-04-02).
- MSFT on 2025-06-10 = A1 10 + A3 6 = **16**.
- AAPL on 2025-06-16 = A1 0 + A3 110 = **110**.

## 4. Derivation of every asserted value

| Assertion | (D, L) | Value | Derivation |
|---|---|---|---|
| T1 | 2025-01-05, 25 | A1 USD 10,000; A1 AAPL 0; A2 RECONSTRUCTED with HKD 0 | Only E1 is dated on or before D. A2's events all fall after D, and A2 has no snapshot, so it is empty and not unknown (Ruling 8.1). |
| T2 | 2025-01-07, 25 | AAPL 50, basis 7,500 USD; A1 USD 2,500 | E1 and E2: 10,000 − 7,500. Basis = gross consideration (§0.2). |
| T3 | 2025-01-09, 25 | A2 0700 500, basis 17,500 HKD; A2 HKD 2,500; A1 USD 2,500 | 20,000 − 17,500. Cash is kept per (account, currency). |
| T4 | 2025-02-02, 25 | AAPL 50, basis 7,500 | E5 is dated after D. |
| T5 | 2025-02-03, 25 | AAPL 200, basis 7,500. Derived unit basis 37.5 | E5 applies at the start of its date (Ruling 3.2), and D is inclusive: 50 × 4/1 = 200. Split preserves total basis. 7,500/200 = 37.5 exactly. |
| T6-before | 2025-02-09, 25 | A1 2,500; A3 0; portfolio USD 2,500 | Before E6. |
| T6 | 2025-02-11, 25 | A1 1,500; A3 1,000; portfolio USD 2,500 | 2,500 − 1,000 and 0 + 1,000. The portfolio total is 1,500 + 1,000 = 2,500, unchanged. |
| T7 | 2025-03-04, 25 | AAPL 150, basis 5,625 USD; A1 USD 3,750 | Single lot: 37.5 × 150 = 5,625 (= 7,500 × 150/200). Cash 1,500 + 2,250. |
| T8 | 2025-03-11, 25 | MSFT 10; basis `INSUFFICIENT_DATA`, `MISSING_COST_BASIS`, [`UNKNOWN_BASIS`] | E8 is external with no cost_basis. The basis is never 0 and never market value (§6.4, PRD §9.3). |
| T9 | 2025-04-02, 25 | A1 USD 2,748 and HKD 750 as two entries; A2 HKD 2,500; A3 USD 1,000; portfolio USD 3,748 and HKD 3,250; A1 0700 200, basis 7,000 HKD; portfolio 0700 700 | USD: 2,748 + 0 + 1,000 = 3,748. HKD: 750 + 2,500 + 0 = 3,250. There is no USD+HKD figure anywhere (§0.1). |
| V1-before | 2025-04-02, 15 | A1 USD 2,748; A1 HKD 780; 0700 200, basis 7,000 HKD | X1 is live: 7,780 − 7,000 = 780. USD 3,750 − 1,000 − 2. |
| V1-after | 2025-04-02, 17 | A1 USD 2,748; A1 HKD 750 | X1 is excluded, both legs together (Ruling 5A.6). X8: 7,750 − 7,000. |
| V1-day-before | 2025-04-01, 17 | A1 USD 3,750; A1 HKD 0 | The conversion enters on its trade date 2025-04-02 (5A.3). X7's own date (04-10) is irrelevant. |
| V2-shortfall | 2025-05-05, 25 | A3 USD −1,000; A3 MSFT 5, basis 2,000 | 1,000 − 2,000. Negative trade-date cash is valid (Ruling 1.3). |
| V2-funded | 2025-05-08, 25 | A3 USD 0 | −1,000 + 1,000. |
| V2-interest | 2025-05-31, 25 | A3 USD −3.50 | 0 − 3.50 (Ruling 5.3). |
| V3-two-lots | 2025-06-05, 25 | A3 MSFT 10, basis 4,100; A3 USD 2,896.50 | No depletion yet (case 1): 2,000 + 2,100. Cash per §3. |
| V3-unresolved | 2025-06-10, 25 | MSFT 6; basis `INSUFFICIENT_DATA`, `UNRESOLVED_CONVENTION`, [`LOT_DEPLETION`]; A3 USD 4,616.50; portfolio MSFT 16 | Methods disagree (see below), so the value is suppressed. 2,896.50 + 1,720. Portfolio 10 + 6. |
| V4-before | 2025-06-15, 25 | A1 AAPL 150, basis 5,625 | Unchanged since T7. |
| V4 | 2025-06-16, 25 | A1 AAPL 0; A3 AAPL 110, basis 4,125 USD; portfolio AAPL 110; A1 USD 4,748; A3 USD 4,616.50 | Single candidate lot: 110 × 37.5. Every method assigns 37.5 to each moved unit. 2,748 + 2,000. |
| T13-L23 | 2025-06-30, 23 | A2 HKD 2,500 | X15 is not yet in the ledger. |
| T13-L24 | 2025-06-30, 24 | A2 HKD 3,000 | 2,500 + 500. |
| T13-L25 | 2025-06-30, 25 | A2 HKD 2,500 | X15 is reversed and nets to zero. |
| T13-retro | 2025-06-22, 25 | A2 HKD 2,500 | The reversal is retroactive (Ruling 2.1). X16's own date, 06-25, plays no part. |
| S1 | 2025-06-29, 3 | B1 `NOT_RECONSTRUCTABLE`, with snapshot_date 2025-06-30; quantity, cash and portfolio HKD all `INSUFFICIENT_DATA`, `NOT_RECONSTRUCTABLE` (detail not asserted from 1.1; see §7) | D is before the snapshot date S = 2025-06-30. This is not an empty state (Ruling 8.1). The portfolio total is unknown because its only account is unknown. |
| S2 | 2025-06-30, 3 | 0700 500; basis `MISSING_COST_BASIS` [`UNKNOWN_BASIS`]; HKD 3,000 | The snapshot is the end-of-day state on S. The opening basis is absent, so it is unknown. |
| S3 | 2025-07-02, 3 | 0700 300; basis `MISSING_COST_BASIS` [`UNKNOWN_BASIS`] only; HKD 10,400 | 500 − 200 and 3,000 + 7,400. A single unknown lot stays unknown after a sale, and **no** `LOT_DEPLETION` detail applies (0.4.4 (b′)). |

**Why V3 must be suppressed.** These are hand-computed remaining bases under each admissible
method, for lots (5 at 400) and (5 at 420), after selling 4:

- **FIFO:** 1 × 400 + 5 × 420 = **2,500**.
- **LIFO:** 5 × 400 + 1 × 420 = **2,420**.
- **Average cost:** 4,100 × 6/10 = **2,460**.
- **Specific identification:** anything from 2,420 to 2,500.

The methods disagree, so no number is determinate, and presenting any of them would decide the
reserved convention.

**Why V4 and T7 are not suppressed.** There is one candidate lot with unit cost 37.5. Every
method assigns 37.5 to every unit, whichever units a sale or move takes. So 5,625 (T7) and
4,125 (V4) are the same under FIFO, LIFO, highest-cost-first, average cost and specific
identification.

## 5. T10–T13 (behaviour, not values)

- **T10.** The same `(events, D, L)` gives byte-identical canonical output across two runs, and
  under a reversed or shuffled input list with `ledger_seq` preserved. No expected bytes are
  specified. The test is equality of the two outputs.
- **T11.** `UPDATE` and `DELETE` on a stored event are refused by the database. Stored rows are
  unchanged.
- **T12.** Re-submitting seq 1–9 with the same `(account, source_reference)` and content inserts
  nothing, and the max committed seq stays 25. The same key with different content (`P1-E1` at
  10,001 USD) is refused as a conflict.
- **T13.**
  - A reversed event's row stays stored. The pure reversal X15/X16 nets to zero (T13-L24 against
    T13-L25).
  - For the atomic correction X7/X8, a pin at `L = 16` is refused, because it was never a
    committed version (Ruling 2.3). This is the fix the review asked for in C1C-2. Pins 15 and 17
    give V1-before and V1-after.

## 6. Ratification statement

I ratify fixture `cp1_golden/1.0` under convention set `ledger-replay/1.3`, on these terms:

1. **Every expected value in the fixture was derived by hand**, from the events listed, under the
   written conventions. It was **not** obtained by running or reading the implementation's
   output. The derivations are in §3 and §4, so a reviewer can check the arithmetic rather than
   trust it.
2. **The fixture decides nothing reserved.** It contains no multi-lot basis as a number, no
   listing-attributed fee, no fractional or same-day split pair, no income event, and no
   non-terminating value. The one multi-lot depletion is asserted as suppressed, which is correct
   under every method.
3. **It covers:**
   - the B0b portfolio E1–E8 and T1–T8, including the T5 and T7 values ruled in 1.2;
   - T9 as a per-currency exposure rule;
   - T10–T13 as behaviour;
   - both PD-0024 types, including a correction at a later ledger version;
   - one ledger-version pair at the same D (V1-before/after), plus the T13 triplet;
   - one snapshot horizon (S1–S3);
   - one explicit unresolved state (V3);
   - the review-driven single-lot sale-plus-move case (V4, C1C-1).

**What I do not ratify:**

- **That the implementation passes.** I have not run it. Whether replay reproduces these values
  is for the engineer's test run and the reviewer to establish. A mismatch is a finding against
  the code or against this derivation, to be resolved by re-checking the arithmetic. It must never
  be resolved by editing an expected value to match the output.
- **Storage behaviours T11–T13.** They are specified, not verified. They need a database run.
- **Exact byte content for T10.** Only equality between runs is specified.
- **Flow classification** (deposits as external, internal transfers neutral for *return*
  purposes) is not a replay output. T6 proves neutrality of *holdings and cash* only. Return
  neutrality becomes testable at CP3.
- **The accessor and loader mapping.** The fixture's `kind` names (`cash`, `portfolio_cash`, and
  so on) describe what must be observable. Mapping them to the replay API is the engineer's
  choice. If an assertion's value cannot be observed through the API, report it; do not drop the
  assertion.

## 7. Changes in 1.1, and the S1 detail decision

**7.1 `atomic_group` "transfer-E6" on seq 6 and 7.** Storage refuses a lone internal-transfer leg
at commit (CP1-B F1; Ruling 6.2). The pair must therefore be appended in one transaction, as X13
and X14 already were. This is a loader instruction. It changes no event and no value.

**7.2 S1: the detail for the three values built without a position is redundant.** I choose
option (a), expressed as `"detail": null`, meaning **not asserted**, rather than `[]`.

**Why the detail is redundant here.** Two facts make it so:

- In the vocabulary, `NOT_RECONSTRUCTABLE` has exactly **one** cause, `BEFORE_SNAPSHOT`
  (Ruling 8.1). Given that reason code, the detail can only be that one value.
- The information an auditor needs is **where history starts**. That is the account's snapshot
  date, which the account state already exposes.

So the reason code plus `account_status` and `snapshot_date` carry everything the detail would
(P9). S1's `account_status` assertion therefore now also checks `snapshot_date` = 2025-06-30,
which follows directly from S-POS and S-CASH.

**Why not `[]`.** An empty list would assert that there is *no* cause. That is false, and it
would fail the day the API starts emitting the detail. "Not asserted" is exact: this fixture
does not constrain it.

**Why not (b).** A gap in the API would matter only if a reason code could have **more than one**
cause. Then the detail would be the only way to tell which remedy applies. That is the case for
`UNRESOLVED_CONVENTION` (lot depletion, split fraction or basis not exact) and for
`LEDGER_INCONSISTENT` (negative quantity or multiple same-day splits). Everywhere those codes
appear in this fixture (T8, V3, S2, S3), the detail **is** asserted, and it is observable because
those values belong to a position.

**Condition attached.** If a later vocabulary gives `NOT_RECONSTRUCTABLE` a second cause, the
detail becomes necessary on every value that carries that reason. The API must then expose it.
This decision would be reversed in a new fixture version.

**Ratification is unaffected.** No expected state, value or reason changed. The 1.0 statement in
§6 applies to 1.1 unchanged. The engineer's report of no mismatches, on both the pure path and the
database path, is consistent with the derivation. It is the implementation's evidence, not an
input to these values.
