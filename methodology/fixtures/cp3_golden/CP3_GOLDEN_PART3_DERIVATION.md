# CP3 golden fixture, part 3: hand derivation and ratification

**Fixture:** `methodology/fixtures/cp3_golden/cp3_golden_part3.json`, ID `cp3_golden/1.2-part3`.
Version 1.2 changes only `extends`, which now names `cp3_golden/1.4-part1` and
`cp3_golden/1.2-part2`.

**1.1-part3 (PD-0036).** This version adds portfolio P20 (§10A): lots carrying `acquired_on`, under
`ledger-replay/1.5` Ruling 0.6 and `performance/1.6` Ruling 3.7a.

- `convention_sets` now reads `performance/1.6` and `ledger-replay/1.5`.
- **No value in §3–§10 changed**, because no event in P1–P19 carries `acquired_on`.
- The fixture now has 167 items, up from 141.
- The calculator gained `acquired_on` support (the kind `RECORDED`, and "no FX observation before
  2025-01-02").

**Scope:** FIFO lots and gains.

- the `FIFO/1` lot book and relief records of the one lot fold;
- realized gain per sale, unrealized gain per position, remaining basis;
- the since-acquisition split;
- realized and unrealized aggregates, including `LIMITED` with stated excluded weights;
- unknown and `ENTRY`-dated bases;
- a Southbound mixed-currency basis;
- same-day pro rata, independent of entry order;
- a partial internal transfer from two lots;
- a sale and a move on one day;
- a reversal and correction;
- the end of a carried split taint under FIFO.

Attribution is part 4.

**Conventions:** `ledger-replay/1.5` (Rulings 0.5 and 0.6, the `FIFO/1` mode), `performance/1.6`,
`market-data/1.10`, lot relief `FIFO/1`. §3–§10 were derived under `ledger-replay/1.4` and
`performance/1.5`. Every ruling they use is unchanged in the new ids. The items of kind `replay_basis` with mode `NONE` are
`ledger-replay/1.3` outputs.

**Author:** `quant-analyst` subagent, 2026-10-01.

**Calculator:** `derivation/cp3_part3_calculator.py`. It uses the standard library only and imports
nothing from `src/`. It contains a small FIFO fold that I wrote from `ledger-replay/1.4` Ruling 0.5
alone, plus a gains layer written from `performance/1.5` Rulings 3.3a and 3.7–3.10. Re-run it with
`python3 methodology/fixtures/cp3_golden/derivation/cp3_part3_calculator.py`.

## 0. Independence

- **Read, for format and vocabulary:**
  - parts 1 and 2, with their derivations and calculators;
  - `cp1_golden/1.1` (events, ids, and the basis kind);
  - `domain/ledger.py` `FIELD_RULES` and value checks. These confirm that `cost_basis` is in the
    event currency and may be 0, and that an internal `TRANSFER_IN` carries no `cost_basis`.
  - `domain/replay.py`'s lot model and day resolution, only to make Ruling 0.5 implementable (its
    §11B).
- **Not read or run:** anything that computes CP3 values, its tests, or any engine output. No
  expected value comes from code I did not write.
- **Checks run besides the calculator:**
  - a JSON load of the fixture, to check item counts, presented-against-exact rounding, units ×
    unit cost = basis, lot units = quantity, and apportioned sums;
  - a comparison of every `lot_book` and `relief` item with the calculator's fold, run on the
    fixture's own event data: 45 items, 0 mismatches.

  Neither computes an expected value. Both were run from scratch files under `$TMPDIR`.
- **Market data is synthetic.** The release is part 1's block, plus part 2's additions, plus two
  listings: SYNF (no corporate action), and SYNT with a synthetic corroborated 4:1 split dated
  2025-03-03. No earlier series, rate or calendar changes.

## 1. FX used (part 1 §1)

| Pair | Fixings to 2025-03-31 (period A) | Fixings from 2025-04-01 (period B) |
|---|---|---|
| USD per HKD | 5/39 | 16/125 |
| CNY per HKD | 12/13 | 116/125 |

Every date used is an ECB fixing day in `SYN_ECB`. Every trade date is a session of its listing's
synthetic calendar; I checked each against the calendar block.

## 2. The FIFO rules applied (ledger-replay/1.4 Ruling 0.5)

- **Candidate set per position and day:** the start-of-day lots (after a split dated that day),
  plus the day's acquisitions and carried lots.
- **Relief:** by acquisition date ascending. The lots of one date are relieved pro rata.
- **Each depleting event** takes `q_e / q_dep` of every relieved portion.
- **Carried lots** keep their origin's acquisition date, date kind, currency and unit cost, and gain
  one hop.
- **Reporting-currency unit cost** (`performance` 3.3a and 3.7):
  - `TRADE` lots: at the fixing of the acquisition date;
  - `ENTRY` lots: known only if the basis is already in `R`, otherwise `ACQUISITION_DATE_UNKNOWN`;
  - unknown lots: `UNKNOWN_BASIS`.

## 3. P1 (USD reporting; `cp1_golden` P1, L = 25)

**Lots:**

- E2: AAPL, A1, 50 for 7,500, dated 01-06. After E5's 4:1 split (02-03) it holds 200 units at
  7,500 / 200 = **75/2**.
- E4: 0700, A2, 500 for 17,500 HKD, dated 01-08. `c` = 35, and `c_R` = 35 × 5/39 = 175/39.
- E8: MSFT, A1, an external in-leg with no basis, `ENTRY` 03-10, unknown.
- X3: 0700, A1, 200 for 7,000 HKD, dated 04-02. `c_R` = 35 × 16/125.
- X4: MSFT, A3, 5 for 2,000 (400), dated 05-05.
- X10: MSFT, A3, 5 for 2,100 (420), dated 06-03.

**E7, SELL 50 on 03-03 for 2,250 (P1-L1).**

- The candidate set is {E2: 200 units}.
- Relief: 50 × 75/2 = **1,875**. Realized: 2,250 − 1,875 = **375**. Remaining: 150 × 75/2 =
  **5,625**, which is `ledger-replay` T7.
- Unrealized gain at 03-04 (close 45): 6,750 − 5,625 = **1,125**.
- **The plan value 750 is wrong.** `performance/1.4` §11.5 wrote "E7: 2,250 − 50 × 150 = 750", using
  the pre-split unit cost 150 for post-split units. The sale is after the split, at a close of
  45.00, and 50 × 45 = 2,250 confirms that the 50 are post-split units. Correcting it: 50 × 37.50 =
  1,875 relieved, so **375**. This is recorded as the `performance/1.5` erratum.

**06-16: X12 SELL 40 for 2,000, and X13/X14 internal move of 110 to A3 (P1-L2).**

- The candidate set is {E2: 150}, and `q_dep` = 150, so A1 ends at 0.
- FIFO relieves the whole lot. X12 takes 40/150 of it: 40 units, **1,500**; realized 2,000 − 1,500
  = **500**.
- X13 takes 110/150: 110 units, **4,125**.
- A3 receives one lot: origin E2, dated **2025-01-06**, `TRADE`, 110 units at 75/2, **4,125**, with
  one hop (A1, out `…022`, in `…023`, 06-16). A1's book is empty.

**X11, SELL 4 on 06-10 for 1,720 (P1-L3).**

- A3's candidate set is X4 (05-05, 5) and X10 (06-03, 5).
- The oldest group is X4: relief 4 × 400 = **1,600**; realized **120**.
- Remaining: X4 1 (400) + X10 5 (2,100) = **2,500**. This is Example L-1's FIFO row.

**06-30 (P1-G1).** The closes are AAPL 50, MSFT 430, 0700 37. FX is 16/125.

| Position | MV (native) | MV_R | Remaining basis (R) | UG_R | UG native |
|---|---|---|---|---|---|
| A1 0700 (X3) | 7,400 HKD | 7,400 × 16/125 = 947.2 | 7,000 × 16/125 = 896 | **51.2** = 256/5 | **400** HKD |
| A2 0700 (E4) | 18,500 HKD | 2,368 | 17,500 × 5/39 = **87,500/39** → 2,243.59 | 2,368 − 87,500/39 = (92,352 − 87,500)/39 = **4,852/39** → 124.41 | **1,000** HKD |
| A3 AAPL (E2 carried) | 5,500 | 5,500 | **4,125** | **1,375** | same |
| A3 MSFT | 2,580 | 2,580 | **2,500** | **80** | same |
| A1 MSFT (E8) | 4,300 | 4,300 | unknown: `MISSING_COST_BASIS` (`UNKNOWN_BASIS`) | the same | the same |

- Cross-check: the market values sum to 15,695.2, and part 1's cash at 06-30 is 4,748 + 96 + 4,616.5
  + 320 = 9,780.5. The total is 25,475.7 = part 1's `V(06-30)`. ✓

**Aggregates (P1-G2).**

- **Unrealized.** Four positions are included: 51.2 + 4,852/39 + 1,375 + 80. Here 1,506.2 =
  7,531/5 = 293,709/195, and 4,852/39 = 24,260/195. The sum is **317,969/195** = 1,630.6102… →
  **1,630.61**. 317,969 is not divisible by 3, 5 or 13, so the fraction is reduced.
  - A1 MSFT is excluded (`MISSING_COST_BASIS`), and every position is valued, so the aggregate is
    **`LIMITED`** (Ruling 3.10).
  - Excluded weight: 4,300 / 15,695.2 = 21,500/78,476 = **5,375/19,619** → 0.273969111576.
    19,619 = 23 × 853, and 5,375 = 5³ × 43.
- **Realized since inception:** 375 + 120 + 500 = **995**. Over (03-31, 06-30]: 120 + 500 =
  **620**. Every sale is known.

**Since-acquisition split (P1-S1; Ruling 9.7).**

- **E4 at 06-30:** `V` = 18,500 and `K` = 17,500 HKD; `X_a` = 5/39 and `X_D` = 16/125. Then
  `X_D − X_a` = (624 − 625)/4,875 = −1/4,875.
  - local = 1,000 × 5/39 = **5,000/39**;
  - FX on cost = 17,500 × (−1/4,875) = **−140/39**;
  - interaction = 1,000 × (−1/4,875) = **−8/39**;
  - sum **4,852/39** = `UG_R`. ✓
  - **Apportioned** (total 124.41):
    - floors are 128.20, −3.59 and −0.21, summing to 124.40, so the shortfall is 1 quantum;
    - the remainders are .005128, .000256 and .004872, so the quantum goes to local;
    - result **128.21, −3.59, −0.21**.
- **X3 at 06-30:** `X_a` = `X_D` = 16/125, so local = 400 × 16/125 = **256/5** and FX and
  interaction are exactly **0**.

**Mode contrast (P1-N1).** In the `none` mode, A3 MSFT on 06-10 has two candidate lots and a partial
depletion. That is case 4: `UNRESOLVED_CONVENTION`, `LOT_DEPLETION`, sticky to 06-30. It agrees
with `cp1_golden` V3-unresolved. The `FIFO/1` mode emits **2,500**, which terminates.

## 4. P2 (HKD; snapshot `S` = 06-30; L = 3)

- The `OPENING_POSITION` has no `cost_basis`, so it is one `ENTRY` lot dated 06-30, 500 units,
  unknown.
- The `SELL` of 200 on 07-02 relieves 200 unknown units, so the realized gain is
  **`MISSING_COST_BASIS`** (`UNKNOWN_BASIS`).
- The remaining 300 units are unknown. The remaining basis and the unrealized gain at 07-31 are
  `MISSING_COST_BASIS`.
- **Aggregates:** every sale and every position is excluded, so each is **`INSUFFICIENT_DATA`** +
  `MISSING_COST_BASIS`, not `LIMITED` (Ruling 3.10: "if every … is excluded").

## 5. P3 (CNY; part 1's seq 1–7 plus seq 8–13; L = 13)

**The lots of 0700:**

- S1: C1, from P3-E3, 1,000 for 32,400 **CNY** (Southbound), dated 03-04, `TRADE`, `c` = 162/5. `k`
  = CNY = `R`, so `c_R` = `c`.
- H1: C2, from seq 8, 200 for 7,200 HKD, dated 04-01, `TRADE`. `c_R` = 36 × 116/125.
- On 04-02 the whole of S1 moves C1 → C2 (seq 9/10). It is the sole depletion and covers the whole
  position, so S1 arrives intact, still dated 03-04, still in CNY, with one hop.
- T1: C2, from seq 11, an external in-leg of 100 with `cost_basis` 3,000 HKD, `ENTRY` 04-03. `k` =
  HKD ≠ CNY, so `c_R` is `ACQUISITION_DATE_UNKNOWN`.

**P3-L1, 04-01 (C1 still holds S1; close 36; X = 116/125).**

- `MV_R` = 36,000 × 116/125 = **33,408**. `UG_R` = 33,408 − 32,400 = **1,008**.
- There is no native (HKD) gain: the basis is CNY on an HKD listing, so it is `UNSUPPORTED_ASSET`,
  `MIXED_CURRENCY_BASIS` (Ruling 3.9).
- The remaining basis in `R` is **32,400**.

**P3-L2, 04-03.**

- C2's book is S1 (1,000; 32,400 CNY), H1 (200; 7,200 HKD) and T1 (100; 3,000 HKD), quantity 1,300.
- Native basis per currency: **CNY 32,400** and **HKD 10,200**, never summed.
- Basis in `R`: **`MISSING_COST_BASIS`** (`ACQUISITION_DATE_UNKNOWN`), because of T1.

**P3-L3, SELL 1,100 for 39,600 HKD on 04-10.**

- FIFO relieves S1 (03-04) whole, 32,400 CNY, then 100 of H1 (04-01), 3,600 HKD.
- **Native:** two basis currencies, so `UNSUPPORTED_ASSET`, `MIXED_CURRENCY_BASIS`.
- **R:** 39,600 × 116/125 = 36,748.8, less 32,400, less 3,600 × 116/125 = 3,340.8. The gain is
  **1,008**. Equivalently 36,000 × 0.928 − 32,400.

**P3-L4, SELL 150 for 5,400 HKD on 04-15.**

- FIFO relieves H1 100 (3,600 HKD), then 50 of T1 (1,500 HKD).
- **Native:** all portions are HKD and so is the sale, so 5,400 − 5,100 = **300** HKD.
- **R:** the T1 portion has no acquisition-date rate, so `MISSING_COST_BASIS`
  (`ACQUISITION_DATE_UNKNOWN`).

**P3-G1, 04-30.**

- C2 holds T1 50 (1,500 HKD). Native UG = 50 × 36 − 1,500 = **300**. UG in `R`:
  `ACQUISITION_DATE_UNKNOWN`.
- C1 SYNA: 2,000 × 11.00 − 20,000 = **2,000** CNY. SYNA's close on 04-30 is 11.00, current.
- **Unrealized total: `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`.** NOP1 (100, no price series) is
  unvalued, and an unvalued position makes the aggregate `INSUFFICIENT_DATA` with its reason (Ruling
  3.10, first bullet).
- **Realized total over (03-31, 04-30]:** 1,008 is included, and the 04-15 sale is excluded
  (`MISSING_COST_BASIS`), so the aggregate is **`LIMITED`**.
  - Weight = (5,400 × 116/125) / ((39,600 + 5,400) × 116/125) = 5,400/45,000 = **3/25** = 0.12.
  - The FX cancels because both dates are in period B.

## 6. P14 and P15 (USD): one date's lots pro rata, with entry order reversed

Events: L0 = `BUY` 30 for 270 (03-03). On 03-05: `SELL` 80 for 880, `BUY` L1 100 for 1,040 (`c`
52/5), `BUY` L2 50 for 580 (`c` 58/5). On 03-10: `SELL` 40 for 480. P14 enters the 03-05 sale first
and P15 last.

**03-05.** `q_dep` = 80. The groups are {L0} (03-03), then {L1, L2} (03-05, `U_g` = 150).

- L0 is relieved whole: 30 units, 270. The need left is 50.
- L1: 50 × 100/150 = **100/3** units; 100/3 × 52/5 = **1,040/3**.
- L2: 50 × 50/150 = **50/3** units; 50/3 × 58/5 = **580/3**.
- Relieved 270 + 1,620/3 = **810**. Realized 880 − 810 = **70**.
- Book: L1 200/3 (2,080/3) and L2 100/3 (1,160/3), so **1,080** on 100 units.
- The `none` mode has three candidate lots and a partial depletion: `LOT_DEPLETION`.

**03-10.** One group of 100 units.

- L1: 40 × (200/3)/100 = **80/3** units (832/3). L2: **40/3** (464/3).
- Relieved **432**. Realized **48**.
- Book: L1 40 (416) and L2 20 (232), so **648**.

**03-31 (close 13).** UG = 780 − 648 = **132**. Realized total **118**.

- I-7: 118 + 132 = 250 = 1,360 + 780 − 1,890. ✓
- P15 gives the same values, as only the multiset of lots and dates is read.

## 7. P16 (USD): a partial internal move from two lots, the receiver's FIFO, and a sale and a move on one day

Lots: `a` (T1, 100 at 9, 03-03); `b` (T1, 100 at 11, 03-05); `o` (T2, 100 at 56/5, 03-06; bought at
11.20 against the close of 11).

**03-07: internal move T1 → T2 of 150, the only depletion.**

- FIFO relieves `a` 100 (900), then `b` 50 (550). Carried: **1,450**.
- T1 keeps `b` 50 (550).
- T2 holds `a′` (03-03), `b′` (03-05) and `o`, so 2,570. Portfolio 3,120, unchanged.
- In the `none` mode both sides are `LOT_DEPLETION`.

**03-10: T2 `SELL`s 120 for 1,440.**

- FIFO relieves `a′` 100 (900), then `b′` 20 (220), so **1,120**. Realized **320**.
- T2 held `o` before the carried lots arrived, but they are older by acquisition date.

**03-12: T2 `SELL`s 40 for 520, and moves 50 to T1.** `q_dep` = 90.

- FIFO relieves `b′` 30 (330), then `o` 60 (672).
- The sale takes 4/9 of each: `b′` 40/3 (440/3) and `o` 80/3 (896/3), so **1,336/3**. Realized 520
  − 1,336/3 = **224/3** → 74.67.
- The move takes 5/9: `b′` 50/3 (550/3) and `o` 100/3 (1,120/3), so **1,670/3**.
- T2 keeps `o` 40 (448).
- T1's book becomes:
  - `b` 50 (550; no hop);
  - `b″` 50/3 (550/3; hops 03-07 and 03-12);
  - `o′` 100/3 (1,120/3; hop 03-12);
  - basis **3,320/3**.
- Day check: 330 + 672 = 1,002 = 1,336/3 + 1,670/3, and 1,002 + 448 = 1,450. ✓

**03-14: T1 `SELL`s 60 for 780.**

- `b` and `b″` share the date 03-05, so they form one group of 200/3 units.
- `b`: 60 × 50/(200/3) = **45** (495). `b″`: 60 × (50/3)/(200/3) = **15** (165). Relieved **660**,
  realized **120**.
- Book: `b` 5 (55), `b″` 5/3 (55/3), `o′` 100/3 (1,120/3). Basis 55 + 1,175/3 = **1,340/3** →
  446.67.

**03-31 (close 13).**

- UG T1 = 520 − 1,340/3 = **220/3** → 73.33. UG T2 = 520 − 448 = **72**.
- Realized total: 320 + 224/3 + 120 = **1,544/3** → 514.67. Unrealized total: **436/3** → 145.33.
- I-7 at portfolio level: 1,980/3 = 660 = (1,440 + 520 + 780) + 80 × 13 − 3,120. ✓

## 8. P17 (USD): a carried split taint ended by FIFO relief

**Set-up.**

- V1 `BUY`s 100 SYNT for 8,000 (02-03), in pre-split units.
- The synthetic corroborated split is 4:1 with ex-date 03-03. `W(K)` = [01-31, 03-31], and no ledger
  `SPLIT` falls in it, so the outcome is **`NOT_RECORDED`**, with the append barred (synthetic).
- V1 is suppressed from 03-03, open-ended.
- V2 holds nothing at 03-03. It `BUY`s `v`, 100 for 1,950, on 03-04 (post-split units; close 20).
- On 03-05 an internal move of 40 goes V1 → V2. V1's relief is `s` 40 (3,200). V2 receives `s′`
  (40 at 80, dated 02-03, hop V1 → V2 on 03-05). It is **tainted**, because V1 was suppressed on
  03-05.

**Results.**

- **03-07:** V2's end-of-day book is {`s′`, `v`}, so it holds a tainted lot. The holding is
  `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` (`SPLIT_SUPPRESSION_CARRIED`), and so is its remaining
  basis (Ruling 3.9a). Its ledger quantity is 140; 140 × 20 = 2,800 would mix units.
- **03-10:** V2 `SELL`s 40 for 800. FIFO relieves `s′` whole, because 02-03 is older than 03-04.
  - The relief record holds a tainted portion, so the realized gain is **`SOURCE_CONFLICT`**
    (Ruling 3.8 (1.5)). Its value 800 − 3,200 = −2,400 would read 40 ledger units as pre-split; as
    post-split units the basis would be 800 and the gain 0.
  - V2's end-of-day book is {`v`}, with no tainted lot. The holding is 100 × 20.00 = **2,000.00**,
    `AVAILABLE` (Ruling 1.1a).
- **03-11:** V2's holding is **2,000.00**, its UG 2,000 − 1,950 = **50**, and its remaining basis
  **1,950**.
  - V1 (60 units) is still suppressed by its own `NOT_RECORDED` outcome, so the portfolio total is
    `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.
- **Contrast:** under the conservative rule (no lot identity), V2 never ends a day at 0, so it would
  stay suppressed on 03-10, 03-11 and after.

## 9. P18 (USD): snapshot with recorded opening bases (`S` = 03-31)

**Opening lots.**

- O-s: SYNF 50, basis 400 USD, `ENTRY` 03-31, `k` = USD = `R`, so known in `R`, `c` = 8.
- O-h: 0700 1,000, basis 30,000 HKD, `ENTRY` 03-31, `k` = HKD, so `ACQUISITION_DATE_UNKNOWN` in
  `R`.

**Trades.**

- **04-02:** `BUY` B, 50 SYNF for 650 (13).
- **04-03:** `SELL` 60 SYNF for 780.
  - FIFO relieves O-s 50 (400), then B 10 (130), so 530.
  - Realized **250**, `AVAILABLE` in `R`.
- **04-07:** `SELL` 400 0700 for 14,400 HKD.
  - FIFO relieves O-h 400, so 12,000 HKD.
  - Native: **2,400** HKD. `R`: `MISSING_COST_BASIS` (`ACQUISITION_DATE_UNKNOWN`). The event-date
    or snapshot-date rate is never used (Ruling 3.7).

**04-30.** The closes are SYNF 12.50 and 0700 36. X = 16/125.

- SYNF: B 40 left (520). UG 500 − 520 = **−20**. Remaining basis **520**.
- 0700: O-h 600 left (18,000 HKD). `MV_R` = 21,600 × 16/125 = **13,824/5** = 2,764.8.
  - Native UG: 21,600 − 18,000 = **3,600** HKD.
  - `R`: excluded (`ACQUISITION_DATE_UNKNOWN`). Its since-acquisition split is `INSUFFICIENT_DATA`
    likewise (Ruling 9.7 (1.5)).
- **Unrealized total: `LIMITED`, −20.** Weight 2,764.8 / (2,764.8 + 500) = 27,648/32,648 =
  **3,456/4,081** → 0.846851261946. Here 4,081 = 7 × 11 × 53, and 3,456 = 2⁷ × 3³.
- **Realized total over (03-31, 04-30]: `LIMITED`, 250.** The 04-07 sale is excluded.
  - Its proceeds_R are 14,400 × 16/125 = 1,843.2.
  - Weight 1,843.2 / (780 + 1,843.2) = 18,432/26,232 = **768/1,093** → 0.702653247941. 1,093 is
    prime.

## 10. P19 (USD): a reversal and correction re-orders FIFO

- seq 2: A, 100 for 900, dated 03-03.
- seq 3: B, 100 for 1,100, dated 03-05.
- seq 4: `SELL` 100 for 1,200 on 03-10.
- seq 5 and 6 (atomic): a `REVERSAL` of seq 2, and A′, 100 for 1,120, dated 03-06, correcting seq 2.

| `(D, L)` | Book | Relief of seq 4 | Realized | UG at 03-31 (close 13) |
|---|---|---|---|---|
| (03-05, 4) | A 900, B 1,100 | — | — | — |
| (03-05, 6) | B 1,100. A never existed, and A′ is dated after `D` | — | — | — |
| (03-31, 4) | B 1,100 | A, 900 | **300** | 1,300 − 1,100 = **200** |
| (03-31, 6) | A′ 1,120 | B, 1,100 | **100** | 1,300 − 1,120 = **180** |

I-7 holds at both `L`: 300 + 200 = 500 = 1,200 + 1,300 − 2,000, and 100 + 180 = 280 = 1,200 + 1,300 −
2,220. ✓

## 10A. P20 (USD): snapshot lots with recorded acquisition dates (1.1-part3; PD-0036)

**Set-up.** Q1 has a snapshot `S` = 2025-03-31. Q2 has no snapshot; its first event is 04-15. The
portfolio's inception base is `S`. The synthetic `M`'s first FX observation is 2025-01-02, and
`SYN_ECB` covers 2025-01-01 onward.

| Lot | Event | Units | Basis | `acquired_on` | `a`, kind | `c_R` (USD per unit) |
|---|---|---|---|---|---|---|
| O1 | seq 1 | 400 | 14,000 HKD (35) | 2025-01-04 (Sat) | 01-04, `RECORDED` | the fixing on or before 01-04 is 01-03, `m` = 0, so 35 × 5/39 = **175/39** |
| O2 | seq 2 | 600 | 18,000 HKD (30) | 2025-01-08 | 01-08, `RECORDED` | 30 × 5/39 = **50/13** |
| O3 | seq 3 | 200 | 7,600 HKD (38) | — | 03-31, `ENTRY` | `ACQUISITION_DATE_UNKNOWN` |
| O4 | seq 4 | 100 | 3,200 HKD (32) | 2024-12-16 | 2024-12-16, `RECORDED` | no observation on or before that date: **`MISSING_FX_HISTORY`** (the calendar does not cover it either: `CALENDAR_COVERAGE_GAP` in lineage) |
| O5 | seq 5 (SYNF) | 50 | 400 USD (8) | 2024-11-01 | 2024-11-01, `RECORDED` | `k` = `R`: **8**, with no rate needed |

- **P20-V1:** at 03-30 the portfolio is `NOT_RECONSTRUCTABLE`. `acquired_on` adds no history (0.6.3).
- **P20-L1:** the FIFO order of the 0700 lots is O4 (2024-12-16), O1, O2, O3, the reverse of the
  entry order of O1 and O4.
- **P20-L2, at 04-01:**
  - O4's since-acquisition view is `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`, not
    `ACQUISITION_DATE_UNKNOWN`. The date is known; the rate is missing (Ruling 3.7a item 3).
  - The position's basis in USD has causes from O3 (`MISSING_COST_BASIS`) and O4
    (`MISSING_FX_HISTORY`). Ruling 1.5 picks **`MISSING_COST_BASIS`**.
- **P20-L3, `SELL` 450 for 16,200 HKD on 04-07:**
  - FIFO relieves O4 100 (3,200) and O1 350 (12,250).
  - Native: 16,200 − 15,450 = **750** HKD.
  - USD: the O4 portion has no rate, so `MISSING_FX_HISTORY`.
- **P20-L4, `SELL` 250 for 9,000 HKD on 04-10:**
  - FIFO relieves O1 50 (1,750) and O2 200 (6,000).
  - Native: **1,250**.
  - USD: 9,000 × 16/125 = 1,152, less (1,750 + 6,000) × 5/39 = 38,750/39. That is (44,928 − 38,750)/39
    = **6,178/39** → 158.41.
  - Without the recorded dates, both lots would be `ENTRY` with an HKD basis, and this would be
    `ACQUISITION_DATE_UNKNOWN`.
- **P20-L5, an internal move of 100 Q1 → Q2 on 04-15:**
  - Q1's oldest remaining lot is O2 (01-08), so it relieves O2 100 (3,000).
  - Q2 receives O2′: `a` 2025-01-08, `RECORDED`, one hop.
  - Q1 keeps O2 300 (9,000) and O3 200 (7,600).

**P20-G1, at 04-30** (0700 36.00, SYNF 12.50, USD per HKD 16/125; `X_D − X_a` = 16/125 − 5/39 =
−1/4,875):

- **Q2, O2′:**
  - basis 3,000 × 5/39 = **5,000/13** → 384.62;
  - `MV_R` 3,600 × 16/125 = 2,304/5;
  - UG = 2,304/5 − 5,000/13 = (29,952 − 25,000)/65 = **4,952/65** → 76.18;
  - native UG 3,600 − 3,000 = **600**.
  - Since-acquisition: local 600 × 5/39 = **1,000/13**; FX on cost 3,000 × (−1/4,875) = **−8/13**;
    interaction 600 × (−1/4,875) = **−8/65**. The sum is (5,000 − 40 − 8)/65 = 4,952/65. ✓
  - Apportioned: floors 76.92, −0.62, −0.13 (sum 76.17), shortfall 1. The largest remainder is the
    interaction's (.0069), so the result is **76.92, −0.62, −0.12**.
- **Q1, O2 (300):**
  - `V` 10,800, `K` 9,000;
  - local 1,800 × 5/39 = **3,000/13**; FX 9,000 × (−1/4,875) = **−24/13**; interaction 1,800 ×
    (−1/4,875) = **−24/65**;
  - total (15,000 − 120 − 24)/65 = **14,856/65** → 228.55.
  - Apportioned: floors 230.76, −1.85, −0.37 (sum 228.54), shortfall 1, which goes to local (.0092):
    **230.77, −1.85, −0.37**.
- **Q1 0700:**
  - native UG 500 × 36 − (9,000 + 7,600) = **1,400** HKD;
  - USD: O3 is `ENTRY`, so `MISSING_COST_BASIS` (`ACQUISITION_DATE_UNKNOWN`).
- **Q1 SYNF, O5:**
  - UG 50 × 12.50 − 400 = **225**;
  - since-acquisition 225, 0, 0, because `k` = `R` (no rate needed, although the date precedes
    coverage);
  - remaining basis **400**.
- **Realized total over (03-31, 04-30]: `LIMITED`, reason `MISSING_FX_HISTORY`, value 6,178/39 →
  158.41.**
  - The 04-07 sale is excluded, with a lot-basis FX cause (Ruling 3.10 (1.5)).
  - Weight = 16,200 / (16,200 + 9,000) = **9/14** → 0.642857142857. The rate 16/125 cancels.
- **Unrealized total: `LIMITED`, reason `MISSING_COST_BASIS`, value 4,952/65 + 225 = 19,577/65 →
  301.18.**
  - Q1 0700 is excluded.
  - Weight = 2,304 / (2,304 + 460.8 + 625) = 23,040/33,898 = **11,520/16,949** → 0.679686117175.
    16,949 = 17 × 997.

## 11. Ratification

- **Ratified:** all **167** expected items (141 in 1.0-part3, plus 26 in P20) were derived by hand
  under `ledger-replay/1.5` Rulings 0.5 and 0.6 and `performance/1.6`, and agree with the
  independent calculator.
  - The lot-book and relief comparison now covers 52 items, with 0 mismatches.
  - The only reserved convention, the fractional split, is not exercised.
  - The one same-day transfer cycle case of 0.5.9 (c) is not exercised.
- **Not ratified:**
  - that the engine passes;
  - the loader's expansion of the market-data additions (it must add no number);
  - structural assertions S3-1 to S3-7, which need an engine run.
- **A finding, not a value to adjust:** the `performance/1.4` plan's E7 = 750 is wrong; the value
  is 375 (§3). If the engine disagrees with any value here, that is a finding for the Quant.
