# `cp4_golden/1.0-part2`: hand derivation

**Author:** `quant-analyst`, 2026-10-02. **Convention set:** `risk/1.1`
(`methodology/CP4_RISK_CONVENTIONS.md`), on `performance/1.12` and `market-data/1.11`.
**Fixture:** `cp4_golden_part2.json`: 5 portfolios, 16 assertions, 61 expected items.
**Calculator:** `derivation/cp4_part2_calculator.py`. It uses the standard library only (it also uses
`zoneinfo` for close instants), imports nothing from `src/`, and reuses the part-1 calculator for
valuation.

**How the expected values were obtained.**

- Every series is built from a four-week cycle, so the statistics over 13 cycles (1Y) or 39 cycles
  (3Y) are closed forms of **one cycle's sums**. Those sums are given here, and the calculator's
  `--closed` re-derives Q1, Q2-T1 and Q4 from them.
- The window facts are ratios of two levels, shown in full.
- `--check` re-derives every one of the 61 items from the fixture's inputs.
- `--mutations` runs the 22 mutations of the catalog. Each must change **exactly** the items whose
  `bites` name it.
- **No value comes from the engine.**

```
python3 methodology/fixtures/cp4_golden/derivation/cp4_part2_calculator.py \
        methodology/fixtures/cp4_golden/cp4_golden_part2.json --check --closed --mutations
```

The run record is §11.

---

## 1. Inputs

**Cycle index.** Friday `F` has index `j = (F − 2023-01-06)/7` and phase `j mod 4`. Steps fall on
Fridays, so Monday to Thursday repeat the previous Friday's level. Before 2023-01-06, every series
is at its phase-0 level.

| Series | Phase 0 | 1 | 2 | 3 | Returns of the periods starting at phase 0, 1, 2, 3 |
|---|---|---|---|---|---|
| SYN21 (US listing, USD) | 100 | 104 | 101 | 98 | **1/25, −3/104, −3/101, 1/49** |
| SYN4_BM_US_TR / _PR / _LATE (USD) | 1000 | 1030 | 1010 | 990 | **3/100, −2/103, −2/101, 1/99** |
| SYN22 (HK listing, HKD) | 100 | 105 | 100 | 95 | local 1/20, −1/21, −1/20, 1/19 |
| SYN4_BM_HK_TR (HKD) | 20000 | 21000 | 20000 | 19000 | local: the same as SYN22 |
| SYN23 (HK listing, HKD) | 50 | 52 | 51 | 49 | 1/25, −1/52, −2/51, 1/49 |

**FX.** `X(HKD→USD)` is **9/70** at an even index and **60/469** at an odd one. The ratio across a
week is `(9/70)/(60/469) = 201/200` going odd to even, and `200/201` going even to odd.

**Risk-free rates.**

- USD: `SIMPLE_YIELD` 3.65 % on ACT/365 = `1/10,000` a day, so **7/10,000** a week, constant.
- HKD (`BANK_DISCOUNT`, ACT/360, term 91 days, Ruling 4.3): `ρ = d/(360 − 91d)`.
  - d = 0.036: `0.036/(360 − 3.276) = 0.036/356.724 =` **1/9,909** a day.
  - d = 0.054 (from 2025-07-01): `0.054/(360 − 4.914) = 0.054/355.086 =` **3/19,727** a day.

**Windows.**

- 1Y to Friday 2026-01-02: `g_0` = 2025-01-03, which has `j` = 104, phase 0. So `n` = 52 = 13
  cycles, all starting at phase 0.
- 3Y: `g_0` = 2023-01-06 (`j` = 0), `n` = 156 = 39 cycles.
- The window facts use base Wednesday 2025-01-08. Then `g_0` = Friday 2025-01-10 (`j` = 105,
  phase 1), with a 2-day stub, and `g_n` = 2026-01-02 (phase 0). The cycle is not closed, so the
  returns are not 0.

---

## 2. Q1: the US listing against the US total-return index (USD)

### 2.1 One cycle's sums

With `r` = (1/25, −3/104, −3/101, 1/49) and `b` = (3/100, −2/103, −2/101, 1/99):

| Quantity | Exact | Decimal |
|---|---|---|
| `r̄` | 23,921/51,469,600 | 0.000464759780 |
| `b̄` | 90,791/411,958,800 | 0.000220388544 |
| `S_rb` (one cycle) | 148,774,763,563/58,250,974,320,000 | 0.002554030474 |
| `S_bb` (one cycle) | 25,046,274,952,081/14,142,504,408,120,000 | 0.001770992904 |
| `S_rr` (one cycle) | 2,470,301,597,923/662,279,931,040,000 | 0.003729996157 |
| `ā` (a = r − b) | 128,254,703/524,835,511,200 | 0.000244371237 |
| `S_aa` (one cycle) | 9,019,413,160,671,125,809/22,954,359,484,713,777,120,000 | 0.000392928113 |

Over `k` whole cycles, every mean is unchanged and every sum `S` is `k` times the cycle's sum.

### 2.2 Q1-B1 (1Y, k = 13, n = 52, `LIMITED`) and Q1-B2 (3Y, k = 39, n = 156, `AVAILABLE`)

- **β** = `S_rb/S_bb` (the k's cancel) = **505,685,421,350,637/350,647,849,329,134** =
  **1.442146079944**, the same in both windows.
- **R²** = `S_rb²/(S_bb S_rr)` = **0.987476898343**, the same in both.
- **α** = 52 × ((r̄ − c) − β(b̄ − c)), with c = 7/10,000 =
  **436,925,701,011,604,733/18,409,012,089,779,535,000** = **0.023734337230**.
  - The same in both windows: it uses only the means and β.
  - With a constant rate it equals the intercept of the excess-return regression (metamorphic #7).
    Mutation M-B3 therefore changes no Q1 item (S2-4).
- **TE²** = 52 × k × S_aa/(n − 1):
  - 1Y: 52 × 13 S_aa/51 = 0.005208223617, so TE = **0.072168023510**;
  - 3Y: 52 × 39 S_aa/155, so TE = **0.071700911653**.
- **IR²** = 52 ā²/(k S_aa/(n − 1)), sign of ā (+):
  - 1Y: IR² = 0.031003965039, IR = **0.176079428211**;
  - 3Y: IR = **0.177226537595**.
- **v_β** = (S_rr − β S_rb)/((n − 2) S_bb), computed with the k-cycle sums. It is in the fixture
  exactly.
- **Comparability FULL.** Both legs are on SYN4_NYSE and there is no translation (USD into USD). No
  input is stale on any grid date. `lagged.of` is 53 (1Y) or 157 (3Y) for the statistics, and 2 for
  an active return.

### 2.3 Q1's window facts

| Item | Window | Portfolio TWR | Benchmark return | Active return |
|---|---|---|---|---|
| Q1-B1 | (2025-01-10, 2026-01-02], phase 1 → 0 | 100/104 − 1 = **−1/26** | 1000/1030 − 1 = **−3/103** | −1/26 + 3/103 = (−103 + 78)/2,678 = **−25/2,678** |
| Q1-B3 | (2026-01-02, 2026-01-16] | 101/100 − 1 = **1/100** | 01-16 has no level (gap 01-15, 01-16); the latest calculation day is Wed 01-14, at Friday 01-09's level 1030: 1030/1000 − 1 = **3/100** | **−1/50** |
| Q1-B4 | (2026-01-02, 2026-01-23] | 98/100 − 1 = **−1/50** | 990/1000 − 1 = **−1/100** | **−1/100** |
| Q1-U5 (third item) | (2025-07-11, 2026-01-02], phase 3 → 0 | 100/98 − 1 = **1/49** | 1000/990 − 1 = **1/99** | (99 − 49)/4,851 = **50/4,851** |

**The decomposition view of Q1-B1** (Ruling 6.9 (1.1)):

- The total is the TWR rounded half-up: **−0.038461538462**.
- The parts floored toward −∞: −0.029126213593 and −0.009335324870.
- Their sum, −0.038461538463, is one quantum short. That quantum goes to the larger remainder,
  the benchmark's (0.767 against 0.695 quanta).
- Displayed: **−0.029126213592** and **−0.009335324870**.
- The active return's own `value` is −0.009335324869 (−25/2,678 = −0.0093353248693…). The view and
  the value differ by one quantum, as Ruling 6.9 (1.1) says they may.

**Q1-B3 state.** At `g_n` = 01-16 the benchmark level has missed 2 calculation days (01-15, 01-16):

- the state is `LIMITED` + `STALE_DATA`, with detail `BENCHMARK_STALE` (Ruling 5.2);
- the portfolio's lag there is 0 and the benchmark's is 2, so comparability is **LAGGED**: 1 of 2
  dates, the point (2026-01-16, 0, 2).

**Q1-B4.** The same gap is now at an **interior** grid date. A window fact reads only `g_0` and
`g_n` (Ruling 6.9 (1.1)), so the result is `AVAILABLE` and `FULL`. Mutation M-B7 (read every grid
date) makes it `LIMITED`.

**Q1-B5.** At `g_n` = 02-27 the latest level is Friday 02-20, with 5 calculation days missed:
`INSUFFICIENT_DATA` + `STALE_DATA`, no value and no comparability object.

### 2.4 The unavailable benchmark (HG3), on Q1's selection log

| Assertion | Version in force | Record | Result for every benchmark-dependent item |
|---|---|---|---|
| Q4-C0 | 0 (none) | none | `MISSING_BENCHMARK`, `NO_BENCHMARK_SELECTED` (**form 1a**) |
| Q1-U2 | 2 | benchmark cleared (null) | `MISSING_BENCHMARK`, `NO_BENCHMARK_SELECTED` (**form 1b**) |
| Q1-U3 | 3 | `SYN4_BM_ABSENT`, not in `M` | `MISSING_BENCHMARK`, `BENCHMARK_SERIES_UNAVAILABLE` (**form 2**) |
| Q1-U4 | 4 | `SYN4_BM_US_PR`, `PRICE_RETURN` | `MISSING_BENCHMARK`, `BENCHMARK_NOT_TOTAL_RETURN` (**form 3**), with the same levels as the total-return index |
| Q1-U5 | 5 | `SYN4_BM_US_TR_LATE`, first level 2025-07-04 | 1Y: no level at or before 2025-01-03, so `MISSING_BENCHMARK`, `BENCHMARK_NOT_COVERING_WINDOW` (**form 4**). A window from 2025-07-11 is covered: 50/4,851 |

- Each lineage names the record in force (`benchmark_expected`).
- Q1-U2's volatility, which does not depend on the benchmark, is unaffected: `LIMITED`, with the value
  of part-1 Ruling 6.2 on Q1's returns. Q = 52 × 13 S_rr/51 = 2,470,301,597,923/49,964,906,040,000,
  giving **0.222352722900**.
- The beta items also list `OBSERVATIONS_BELOW_STANDARD` (52 < 155). It is a `LIMITED`-level cause
  with no code, so it does not set the reason. `MISSING_BENCHMARK` is the code at the
  `INSUFFICIENT` level.

---

## 3. Q2: an HK listing in a USD portfolio; the HK index, then the US index

**USD returns of SYN22** for a period starting at phase p (the FX index parity is the cycle index
parity):

| p | local | FX ratio | USD return |
|---|---|---|---|
| 0 (even → odd) | 1/20 | 200/201 | (21/20)(200/201) − 1 = **3/67** |
| 1 (odd → even) | −1/21 | 201/200 | (20/21)(201/200) − 1 = **−3/70** |
| 2 | −1/20 | 200/201 | **−11/201** |
| 3 | 1/19 | 201/200 | **11/190** |

**Q2-T1 (selection 1: the HK index, HKD, net total return).**

- Its local returns equal SYN22's, and it is translated at **the same fixing `u(g)`** (Ruling 5.3).
  So `b_k = r_k` for every period: β = **1**, R² = **1**, α = **0**, TE = **0** (Q = 0, sign 0),
  IR undefined (`ZERO_TRACKING_ERROR`), v_β = 0 (metamorphic #6).
- Both legs are {SYN4_ECB, SYN4_HKEX}: comparability **FULL**.
- Window facts (phase 1 → 0): both legs are (100 × 9/70)/(105 × 60/469) − 1 =
  (20/21)(201/200) − 1 = **−3/70**, so the active return is **0**.
- **Mutation M-B1** (no translation) makes the benchmark's returns local, so β, R², α and TE move
  off 1, 1, 0 and 0. **M-B2** (the previous day's fixing) shifts the FX by a day: the HKD rate
  changes on Fridays, so every Friday ratio is wrong. Both bite all seven items.

**Q2-T2 (selection 2: the US index).** The same portfolio, window and as-of date.

- β = **2.169870750000**, R² = **0.818943549868**, α = **0.083851621233**, TE = **0.237828539284**,
  IR = **0.229893703529**. Exact values are in the fixture; the cycle sums are those of §1 with the
  USD returns above.
- Active return = −3/70 − (−3/103) = (−309 + 210)/7,210 = **−99/7,210**.
- **SEAM:** {SYN4_ECB, SYN4_HKEX} against {SYN4_NYSE}. At 2026-01-02 (winter):
  - HKEX close 16:10 HKT = **08:10 UTC**;
  - ECB fixing 14:10 CET = **13:10 UTC**;
  - NYSE close 16:00 EST = **21:00 UTC**.

  The largest offset is 21:00 − 08:10 = **770 minutes**.
- Every result names selection 2 (S2-5: recompute on change). Under M-B10 (the first record wins)
  every Q2-T2 item takes the HK index's values.

---

## 4. Q4: cash only, against the US index

`r_k` = 0, so `S_rr` = 0 and `S_rb` = 0:

- **β = 0**, v_β = 0.
- **R²** is 0/0: `INSUFFICIENT_DATA`, `ZERO_PORTFOLIO_VARIANCE`. M-B21 would report 0 instead.
- **α** = 52 × (−c − 0) = 52 × (−7/10,000) = **−91/2,500** = −0.0364.
- **TE²** = 52 × 13 S_bb/51 = 0.023474337316, TE = **0.153213371858**: the benchmark's own
  volatility.
- **IR** = sign(−b̄) √(52 b̄²/(13 S_bb/51)) = **−0.074798982190**.
- Active return (phase 1 → 0) = 0 − (−3/103) = **3/103**. Benchmark return **−3/103**.
- **Comparability FULL.** The portfolio leg holds no listing and no foreign currency, so its instant
  set is empty, and by Ruling 8.2 (1.1) there is no seam. M-B13 (an empty set counts as a seam)
  bites every two-leg item that carries an object.

---

## 5. Q5: HKD reporting, an HK listing, the HK index, a bank-discount rate

- No FX; both legs on SYN4_HKEX: **FULL**.
- Statistics (1Y): β = **0.592958647199** (exact 112,687,993/190,043,595), R² = **0.899013551826**,
  TE = **0.165171032499**, IR = **−0.240119019587**.
- **α = −0.031878904341** uses each period's HKD rate:
  - 26 periods start before 2025-07-01 (starts 2025-01-03 … 06-27), at 7/9,909;
  - 26 start after (07-04 … 12-26), at 21/19,727.

  With a varying rate the excess-return slope differs from β, so M-B3 bites β, R² and α here, unlike
  in Q1. M-B9 (discount read as a simple ACT/360 yield: 0.036/360 = 1/10,000) and M-B17 (the USD
  rate) also bite α.
- **Q5-H2:** the four rates of Ruling 4.3.

  | Period start | Quote (latest publication ≤ start) | rf_k |
  |---|---|---|
  | 06-20, 06-27 | 3.60 % | 7 × 1/9,909 = **7/9,909** |
  | 07-04, 07-11 | 5.40 % | 7 × 3/19,727 = **21/19,727** |

- Window facts (phase 1 → 0): portfolio 50/52 − 1 = **−1/26**; benchmark 20,000/21,000 − 1 =
  **−1/21**; active = −1/26 + 1/21 = (−21 + 26)/546 = **5/546**.
  - The decomposition view shows 0.009157509157 against the value 0.009157509158. The benchmark part
    took the shortfall quantum.

---

## 6. Q6: the US listing plus HKD cash, against the US index

- `V` = 100 × SYN21 + 42,000 × `X(HKD→USD)`.
- Both legs' exchange calendar is SYN4_NYSE, but the portfolio leg is also valued at the ECB fixing.
  So the instant sets are {SYN4_ECB, SYN4_NYSE} and {SYN4_NYSE}: a **SEAM through the fixing
  alone**, 21:00 − 13:10 = **470 minutes**. M-B11 (calendars only) removes it.
- Window facts:
  - `V(2025-01-10)` = 10,400 + 42,000 × 60/469 = 10,400 + 2,520,000/469;
  - `V(2026-01-02)` = 10,000 + 42,000 × 9/70 = 15,400;
  - the TWR is the ratio minus 1 (no flow in the window) = **−0.023656320969**;
  - active = TWR − (−3/103) = **2,977/544,252**.
- β = **0.921274014687**, TE = **0.028873200905**.

---

## 7. Comparability, summarised

| Item | Portfolio instants | Benchmark instants | Seam (minutes) | Lagged |
|---|---|---|---|---|
| Q1 (all) | {NYSE} | {NYSE} | none | none, except Q1-B3: 2026-01-16 (0 against 2) |
| Q2-T1 | {ECB, HKEX} | {ECB, HKEX} | none | none |
| Q2-T2 | {ECB, HKEX} | {NYSE} | 770 | none |
| Q4-C1 | {} | {NYSE} | none (empty set) | none |
| Q5-H1 | {HKEX} | {HKEX} | none | none |
| Q6-S1 | {ECB, NYSE} | {NYSE} | 470 | none |

---

## 8. Detail names asserted

`OBSERVATIONS_BELOW_STANDARD` (every 1Y statistic), `NO_BENCHMARK_SELECTED`,
`BENCHMARK_SERIES_UNAVAILABLE`, `BENCHMARK_NOT_TOTAL_RETURN`, `BENCHMARK_NOT_COVERING_WINDOW`,
`BENCHMARK_STALE`, `ZERO_TRACKING_ERROR`, `ZERO_PORTFOLIO_VARIANCE` (Ruling 7.4). `details_include`
is compared as a set, restricted to the `risk` detail names.

---

## 9. What the fixture does not cover (part 3 or later)

`ZERO_BENCHMARK_VARIANCE` (a flat benchmark), a LAGGED point inside a statistic's window, a stale
benchmark translation (FX gap on the benchmark leg only), two sources for one benchmark (Ruling 5.7),
an ETF proxy (Ruling 5.5), daily and monthly benchmark statistics, Current mode.

---

## 10. The mutation catalog

Each mutation is one departure from `risk/1.1`. `--mutations` requires that it changes exactly the
items whose `bites` name it.

| Id | Departure | Items changed |
|---|---|---|
| M-B1 | no translation of the benchmark | 7 (Q2-T1) |
| M-B2 | benchmark at the previous day's fixing | 7 (Q2-T1) |
| M-B3 | excess-return regression for β, R² | 3 (Q5-H1 β, R², α; none in Q1) |
| M-B4 | geometric active return | 8 |
| M-B5 | TE with divisor n | 11 |
| M-B6 | price return accepted | 3 (Q1-U4) |
| M-B7 | window facts read every grid date | 9 |
| M-B8 | IR = window active return / TE | 5 |
| M-B9 | discount read as a simple yield | 2 (Q5-H1 α, Q5-H2) |
| M-B10 | first selection record wins | 17 |
| M-B11 | seam ignores the ECB fixing | 9 (Q2-T2, Q6-S1) |
| M-B12 | no LAGGED test | 1 (Q1-B3 active) |
| M-B13 | empty instant set is a seam | 5 (Q4-C1) |
| M-B14 | β = S_rb/S_rr | 9 |
| M-B15 | adjusted R² | 4 |
| M-B16 | α as the market-model intercept | 5 |
| M-B17 | USD rate for any currency | 1 (Q5-H1 α) |
| M-B19 | staleness does not degrade | 3 (Q1-B3, Q1-B5) |
| M-B20 | missing benchmark suppresses everything | 1 (Q1-U2 volatility) |
| M-B21 | R² = 0 when undefined | 1 (Q4-C1 R²) |
| M-B22 | default benchmark when none is selected | 4 (Q4-C0, Q1-U2) |
| M-B23 | benchmark leg from the requested base B | 11 |

(There is no M-B18: the id was withdrawn before issue and is not reused.)

---

## 11. Run record

Run on 2026-10-02 with the system `python3` (3.9.6), read-only, from the repository root. The
output below is abbreviated where marked "…"; the full output lists every closed form and every
mutation line, each `ok`.

```
$ python3 methodology/fixtures/cp4_golden/derivation/cp4_part2_calculator.py \
          methodology/fixtures/cp4_golden/cp4_golden_part2.json --check --closed --mutations
ok  Q1-B1[0] beta = 505685421350637/350647849329134
ok  Q1-B1[1] r_squared = 7969177243156046994765143/8070241700366674507060143
ok  Q1-B1[2] alpha_jensen = 436925701011604733/18409012089779535000
ok  Q1-B2[0..2] (equal to Q1-B1)          ok  Q2-T1 beta 1, r_squared 1, alpha 0
ok  Q4-C1 beta 0, alpha -91/2500          ok  tracking_error^2 for Q1-B1, Q1-B2, Q4-C1
CLOSED FORMS AGREE
ok  M-B1 … ok  M-B23   (every mutation changes exactly the items that name it)
MUTATIONS AGREE
smallest distance of a square-root value from a rounding boundary: 0.021710193266 quanta ( OK ; need > 1e-18 )
CHECK PASSED - 0 difference(s)
```

**The checker is not blind.** I changed the fixture in memory only, one field at a time. Each change
was reported as a difference:

- Q2-T2's selection id set to selection 1: 7 differences;
- the 770-minute offset set to 769: 1 difference;
- Q1-B1's decomposition view set equal to the value: 1 difference;
- a `v_beta` changed: 1 difference.

`cp4_golden/1.0-part1` was re-checked after `risk/1.1` was issued: `CHECK PASSED - 0 difference(s)`.
