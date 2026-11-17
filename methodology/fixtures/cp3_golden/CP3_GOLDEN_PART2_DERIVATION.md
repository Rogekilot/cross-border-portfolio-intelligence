# CP3 golden fixture, part 2: hand derivation and ratification

**Fixture:** `methodology/fixtures/cp3_golden/cp3_golden_part2.json`, ID `cp3_golden/1.2-part2`.
Versions 1.1 and 1.2 change only `convention_sets` and `extends`. `convention_sets` is now
`performance/1.6`, `ledger-replay/1.5` (`FIFO/1` mode) and `market-data/1.10`, and `extends` names
`cp3_golden/1.4-part1`. No derivation below changed.

**Scope:**

- the MWR and annualized MWR;
- income, fees, taxes, financing and conversion-result amounts;
- dividend receivables (ex-date accrual);
- one synthetic split suppression.

**Conventions:** `performance/1.3`, `market-data/1.9`, `ledger-replay/1.3`. `FIFO/1` is not exercised
(lots are part 3).

**Author:** `quant-analyst` subagent, 2026-10-01.

**Calculator:** `derivation/cp3_part2_calculator.py`, standard library only, importing nothing from
`src/`.

- It solves every MWR **twice**: by Ruling 6.2 (`Decimal` at `prec` 60, a bracket from `g` = 1,
  then bisection) and by the exact variant (`y = g^(1/n)`, with the sign tested in `Fraction`).
- The two agree to the presented 12th decimal in every case.

## 0. Independence

- **Read for format and vocabulary:**
  - part 1;
  - tech plan §16.14 and §16.15;
  - `domain/ledger.py` `FIELD_RULES` only, to confirm the event shapes: `DIVIDEND` with optional
    `ex_date`; `INTEREST`, `FEE` and `TAX` with an optional `listing_id`.
- **Not read or run:** anything in `src/performance/` or its tests.
- **Market data** is synthetic: part 1's block plus five new listings and one synthetic
  corporate-action pair. No part-1 series, rate or calendar changes.

## 1. FX used

- `X(HKD→USD)` = 5/39 for fixings up to 2025-03-31.
- `X(HKD→USD)` = 16/125 from 2025-04-01 (part 1 §1).

## 2. MWR (Ruling 6.1): flows, times, roots

The time is `τ = k/n`, with `k` in days from `B`:

- a cash inflow dated `D` sits at `k = D − 1 − B` (the start of the day);
- an outflow or in-kind flow sits at `k = D − B`;
- `V_B` sits at 0 and `V_E` at `n`.

| Case | `n` | Investor flows `(k, amount)` | Result |
|---|---|---|---|
| **P1-M1**, (2025-01-01, 06-30] | 180 | (0, −10,000) E1; (4, −100,000/39) E3, HKD 20,000 at 5/39; (68, −4,000) E8 in kind, end of 03-10; (126, −1,000) X5; (151, −5,000) X9; (180, +254,757/10) | Every investment precedes the end value: one sign change, so the root is unique. **0.182608960655** (both methods). `Y` = 5/12 + 29/365 = **2173/4380** < 1, so annualized is `PERIOD_SHORTER_THAN_ONE_YEAR`. |
| **P1-M2**, to 2026-01-31 | 395 | the same, with (395, +255,653/10) | **0.154104872920**. `Y` = 79/73, so annualized = (1.154104872920…)^(73/79) − 1 = **0.141610055620** (tolerance 1e-10). |
| **P2-M1**, (06-30, 07-31] | 31 | (0, −21,500); (31, +21,800) | `g` = 21,800/21,500, so **3/215** = 0.013953488372, the same as the TWR (I-6) |
| **P4-M1**, (01-07, 01-10] | 3 | (1, −1,000): the deposit dated 01-09 sits at `k` = 01-08 − 01-07 = 1; (3, +1,020) | `−1000 g^(−1/3) + 1020 g^(−1) = 0`, so `g^(2/3)` = 1.02 and `g` = 1.02^(3/2). **0.030149503713** (1.02 × √1.02 = 1.02 × 1.0099504938… = 1.0301495037…). The TWR is `NON_POSITIVE_BASE` (part 1 P4-R1). |
| **P5-M1**, (01-03, 01-06] | 3 | `V(01-03)` = 0 (the 1,000 left at the end of 01-03); no flow until 01-07 | every flow is 0, so **`NO_CAPITAL`**. TWR: the run 01-04..06 is 0/0, a factor of 1 with `ZERO_CAPITAL_RUN`, so TWR = 0. `G` = 0. |
| **P8-M1**, (2025-01-01, 2026-01-01] | 365 | (0, −4,000): the deposit dated 01-02 sits at `k` = 0; (365, +4,300), MSFT 10 × 430.00 (the 2025-12-31 close; NYSE closed 2026-01-01) | `g` = 4,300/4,000, so **3/40** = 0.075. The TWR is also 3/40: 4,000/(0 + 4,000) × 4,300/4,000. `Y` = 1, because `sub_months(2026-01-01, 12)` = 2025-01-01, so both annualized figures equal the period figures. |
| **P9-M1** (Example M-3), (03-03, 03-06] | 3 | (0, −1,800); (1, +6,050) withdrawn at the end of 03-04; (2, −6,750) deposited at the start of 03-06; (3, +2,500) | With `y = g^(−1/3)`, `f = 2,500(y−1)(y−9/10)(y−4/5)`, so the roots are `g` = 1, 1,000/729 and 125/64. `G` = 2,500 − 1,800 − (6,750 − 6,050) = 0, so `g*` = 1. Uniqueness: `K₀` = 1,800 and `K₁` = 1,800 − 6,050 = −4,250 < 0, so it fails: **`IRR_UNIQUENESS_NOT_ESTABLISHED`**. |
| **P10-M1** (Example M-2), (03-10, 03-14] | 4 | (0, −10,000); (2, +2,000) at the end of 03-12; (3, −3,000) at the start of 03-14; (4, +12,000) | **0.102593873725**. `K` = 10,000; 8,500.447…; 11,710.551…, all ≥ 0, so unique. |
| **P11-M1**, (01-08, 01-10] | 2 | `V_B` = 10 × 101 − 1,020 = **−10**, so (0, +10); (1, −1,020) at the start of 01-10; (2, +1,020) | The first non-zero flow is positive: **`IRR_NOT_DEFINED`**. |
| **P11-M2**, (01-07, 01-10] | 3 | (2, −1,020); (3, +1,020) | `G` = 0 exactly, so `g*` = 1 and the MWR is **0**, unique (`K` = 1,020 ≥ 0). |
| **P12-R1** (W′), (03-30, 04-02] | 3 | (0, −10,000); (2, +1,000) at the end of 04-01; (3, +231,104/25) | **0.025250703431** |
| **P7-R1**, (03-31, 06-26] | 87 | (0, −12,800): 100,000 HKD × 16/125, deposited 04-01, so `k` = 0; (87, +41,492,936/3,125) | `g` = `V_E`/12,800, so the MWR equals the TWR = **186,617/5,000,000** = 0.0373234 (I-6) |

## 3. The TWR values asserted beside the MWRs (segment form, Ruling 5.2)

**P9.** `V`: 03-03 = 1,800 (1,800 × 1.00); 03-04 = 6,300 − 6,050 = 250; 03-05 = 250; 03-06 =
250 + 6,750 − 7,000 + 2,000 × 1.25 = 2,500.

- Factors:
  - the empty run is 1;
  - day 03-04 (outflow at the end) = (250 + 6,050)/1,800 = 7/2;
  - run 03-05 = 250/250 = 1;
  - day 03-06 (inflow at the start) = 2,500/(250 + 6,750) = 5/14.
- TWR = (7/2)(5/14) − 1 = **1/4**.
- `G` = **0**.

**P10.** `V`: 03-10 = 10,000; 03-11 = 10,500; 03-12 = 800 × 11 + 200 = 9,000; 03-13 = 9,000;
03-14 = 9,000 + 3,000 = 12,000.

- Factors:
  - run 03-11 = 10,500/10,000;
  - day 03-12 = (9,000 + 2,000)/10,500;
  - run 03-13 = 1;
  - day 03-14 = 12,000/12,000.
- TWR = 11,000/10,000 − 1 = **1/10**.
- `G` = 12,000 − 10,000 − (3,000 − 2,000) = **1,000**.

**P11.** `V`: 01-07 = 0; 01-08 = 01-09 = −10 (NYSE closed 01-09); 01-10 = 1,020.

- (01-08, 01-10]: run 01-09 = −10/−10, a negative denominator, so **`NON_POSITIVE_BASE`**.
- Since inception: run 01-08..01-09 = −10/0, so **`NON_POSITIVE_BASE`**.
- `G` (custom) = 1,020 − (−10) − 1,020 = **10**. `G` since inception = **0**.

**P12 (W′).**

- `V(03-31)` = 5,000 + (790 + 39,000) × 5/39 = 5,000 + 198,950/39 = **393,950/39** = 10,101.28.
- `V(04-01)` = 4,000 + 40,790 × 16/125 = 4,000 + 5,221.12 = **9,221.12** = 230,528/25.
- `V(04-02)` = 4,000 + 40,970 × 16/125 = **9,244.16** = 231,104/25.
- TWR = (393,950/39 / 10,000) × ((230,528/25 + 1,000)/(393,950/39)) × (231,104/230,528) − 1. The first
  two factors telescope to (255,528/25)/10,000. The result is **2,776,451/112,562,500** →
  0.024665861188.
- `G` = 9,244.16 − 9,000 = **244.16**.

**P8.** TWR = **3/40** (§2).

**P7.** TWR = (12,789.76/12,800) × (13,277.73952/12,789.76) − 1 = 103,732.34/100,000 − 1 =
**186,617/5,000,000**. The HKD figures are 99,920 → 103,732.34 on a 100,000 base.

## 4. Income and cost amounts (Ruling 8.6, with the 1.4 clarification on signs)

**P1, (2025-01-01, 2025-06-30]** at L = 25:

| Line | Value |
|---|---|
| fees | X2 `FEE` 2 USD → **−2** |
| financing | X6 `INTEREST_CHARGED` 3.50 → **−7/2** |
| taxes | **0** |
| income | **0** |
| conversion result | X8 (the live replacement of the reversed X1) on 04-02: −1,000 + 7,750 × 16/125 = −1,000 + 992 = **−8** |

**P12, (03-30, 04-02]:**

| Line | Value |
|---|---|
| income | 200 HKD × 16/125 = **128/5** = 25.60 (dated 04-02, no `ex_date`, so cash basis) |
| taxes | −20 × 16/125 = **−64/25** = −2.56 |
| fees | −10 HKD × 5/39 (03-31) = **−50/39** → −1.28 |
| financing | **0** |
| conversion | −5,000 + 38,800 × 5/39 = (−195,000 + 194,000)/39 = **−1,000/39** → −25.64 |

**P7** (SYNP: 50.00 from 04-01, 52.00 from 05-02, 50.00 from 05-06, 51.00 from 06-02):

- HKD cash after 04-01: 100,000 − 50,000 − 50 (stamp duty `TAX`) − 30 (`FEE`) = 49,920. The fee and
  the stamp duty are not in any basis (Ruling 3.6).
- **Values:**

  | `D` | Composition (HKD) | Total (USD) |
  |---|---|---|
  | 05-05 | 49,920 + 1,000 × 52 (the 05-02 close; HKEX closed 05-01 and 05-05) = 101,920 | × 16/125 = **13,045.76** |
  | 05-06 | 49,920 + 50,000 + receivable 2,000 = 101,920 | **13,045.76**: the ex-date drop is offset exactly by the receivable |
  | 05-19 | the same | **13,045.76** |
  | 05-20 | cash 49,920 + 2,000 − 200 = 51,720, + 50,000 = 101,720 | **13,020.16** |
  | 06-26 | 51,720 + 1,000 + 12.34 = 52,732.34 cash, + 51,000 = 103,732.34 | **41,492,936/3,125** = 13,277.74 |

- **Receivable** (`ex_date` 05-06 ≤ `D` < pay date 05-20): 2,000 HKD → **256.00** USD on 05-06..05-19.
  None on 05-05 or 05-20.
- **Income (03-31, 06-26]:**
  - the accrued dividend is recognized on 05-06: 2,000;
  - the cash-basis net-only dividend on 06-10: 1,000;
  - interest on 06-20: 12.34;
  - total 3,012.34 HKD × 16/125 = **1,204,936/3,125** = 385.57952 → **385.58**.
- **Taxes:** −(50 + 200) × 16/125 = **−32**. **Fees:** −30 × 16/125 = **−96/25** = −3.84.
  **Financing:** 0.
- **Cross-check `G`:** +1,000 (price, 50 → 51 on 1,000 shares) + 3,012.34 (income) − 30 − 250 =
  3,732.34 HKD × 16/125 = 477.73952 = **1,492,936/3,125** ✓. FX is constant in period B.
- **Accrual windows:**
  - (05-05, 05-31] contains the ex-date: income **256**, taxes −200 × 16/125 = **−128/5**;
  - (05-06, 05-31]: the ex-date is the base, so income **0**, although the 2,000 HKD was credited on
    05-20, inside the window, because the pay-date credit is not income again. Taxes **−128/5**.
- **(03-31, 06-30]:** the CNH dividend of 06-27 has no rate.
  - Income is `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`.
  - The CNH cash also makes `V(06-30)`, `G` and the MWR `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`.
  - Fees (**−96/25**) and taxes (**−32**) are unaffected.

## 5. P13: a synthetic corroborated split missing from the ledger

- **Set-up:** `DEPOSIT` 10,000 and `BUY` 100 SYNS for 8,000 on 2025-02-03. SYNS RAW: 80.00, then 20.00
  from 2025-03-03. A synthetic feed record and a synthetic filing record agree on `SPLIT` (4, 1)
  ex 2025-03-03.
- **Corroboration** is within the synthetic world (`market-data` Ruling 4.8 item 4 (a)).
  - `W(K)` is 20 NYSE sessions either side. Before: 31 Jan plus February's 19 sessions (17 Feb
    closed) gives 2025-01-31. After: March's sessions to 2025-03-31 (no closure).
  - No ledger `SPLIT` falls in the window, so the outcome is `NOT_RECORDED`, with the append barred
    (item 4 (b)). The ledger stays at L = 2.
- **Values:**
  - **02-28:** 2,000 + 100 × 80 = **10,000**.
  - **From 03-03:** 100 pre-split units × 20.00 post-split would be 2,000, which is wrong (the
    truth is 8,000). The holding is therefore `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, natively and
    in `R`, and so is the total.
  - **Value of priced holdings:** the cash, **2,000**, excluding 1 (the SYNS position, 100 units,
    `SOURCE_CONFLICT`).
- **Window (02-28, 03-04]:** the TWR, MWR and `G` all need `V(03-04)`, so each is
  `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.

## 6. Ratification

- **Ratified:** all 78 expected items were derived independently of the engine. They use only
  `performance/1.3` and `market-data/1.9` rulings, and decide nothing reserved: no lot relief, no
  attribution linking.
- **Not ratified:**
  - that the engine passes;
  - the loader's expansion of the additions and of the corporate-action pair into CP2 layouts
    (that is the engineer's, and must add no number);
  - structural assertions S2-1 to S2-5.
- **Example W′:** the conventions document's Example W uses FX 9/70 → 5/39 on dates that conflict
  with part 1's ECB steps. W′ keeps its shape (deposit, conversion, buy, fee, withdrawal, dividend
  and withholding) on the fixture's own FX. So its numbers differ from Example W: MWR
  0.025250703431, against W's 0.026119591042 in the conventions document. Both are correct for their
  own inputs.
