# CP3 golden fixture, part 1: hand derivation and ratification

**Fixture:** `methodology/fixtures/cp3_golden/cp3_golden_part1.json`, ID `cp3_golden/1.4-part1`.
Versions 1.2, 1.3 and 1.4 change only `convention_sets`. They are now `performance/1.6`,
`ledger-replay/1.5` (`FIFO/1` mode) and `market-data/1.10`. No derivation below changed.

In 1.1-part1 only the wording of structural assertions S-4 and S-5 changed, and the convention
became `performance/1.2`. Every derivation below is unchanged.

**Scope:**

- valuation: holdings, cash, totals, native subtotals, and "value of priced holdings";
- the absolute gain `G`;
- the TWR and the annualized TWR.

MWR, income, lots and gains, and attribution are parts 2 to 4.

**Conventions:** `performance/1.1`, `ledger-replay/1.3`, `market-data/1.8`. Lot relief `FIFO/1` is
not exercised in part 1.

**Author:** `quant-analyst` subagent, 2026-10-01, dispatched by the main session.

**Calculator:** `derivation/cp3_part1_calculator.py`. It is standard-library only, imports nothing
from `src/`, and has holdings and prices typed in by hand. Re-run it with
`python3 methodology/fixtures/cp3_golden/derivation/cp3_part1_calculator.py`.

## 0. Independence: what I read, and what I did not

- **Read, for format only:**
  - tech plan §16, §16.8 and §16.14 (metric names `holding_value`, `cash_value`,
    `portfolio_value`; native and reporting views; `ComputedMetric.exact`; the market-data half
    through the real CP2 path);
  - `cp1_golden/1.1` (events and format).
- **Not read before every expected value below was fixed:** any file under `src/performance/`,
  `src/performance_service/`, or the CP3 tests. No engine output was run or read.
- **One tool use besides the calculator:** a JSON load of the fixture, to check item counts and
  window day counts. That computes no expected value.
- **Market data is synthetic** (`market-data` Ruling 4.8). The calendars are synthetic copies of the
  PD-0034 drafts' closure lists. Nothing here is a claim about a real price or rate.

## 1. FX crosses (exact, by hand)

| Pair | Period A (fixings 2025-01-02 .. 03-31) | Period B (from 2025-04-01) |
|---|---|---|
| USD per HKD, `x_USD/x_HKD` | 1.0400/8.1120 = 10,400/81,120 = (÷80) 130/1,014 = (÷26) **5/39** | 1.0880/8.5000 = 10,880/85,000 = **16/125** (0.128) |
| HKD per USD | **39/5** = 7.8 | **125/16** = 7.8125 |
| CNY per USD, `x_CNY/x_USD` | 7.4880/1.0400 = **36/5** = 7.2 | 7.8880/1.0880 = **29/4** = 7.25 |
| CNY per HKD | 7.4880/8.1120 = (both ÷6,240) **12/13** | 7.8880/8.5000 = 7,888/8,500 = **116/125** |
| HKD per CNY | **13/12** | 8,500/7,888 = (÷68) **125/116** |

Both HKD-per-USD values lie inside 7.75–7.85. No CNH quote exists, so every CNH amount is
untranslatable.

## 2. P1 (USD): holdings at each valuation date (from `cp1_golden` P1 events at L = 25)

The external flows are:

| Event | Date | Flow |
|---|---|---|
| E1 | 01-02 | 10,000 USD, cash in at the start of the day |
| E3 | 01-06 | 20,000 HKD, cash in at the start of the day |
| E8 | 03-10 | MSFT 10 in kind, at the end of the day |
| X5 | 05-08 | 1,000 USD, cash in at the start of the day |
| X9 | 06-02 | 5,000 USD, cash in at the start of the day |

- **Internal, not flows:** E6 (cash A1→A3) and X13/X14 (AAPL A1→A3).
- **Not live at L = 25:** X1 (reversed by X7, replaced by X8) and X15 (reversed by X16).
- **Prices** (step series): AAPL 150 → 37.50 (02-03) → 45 (03-03) → 50 (06-16); 0700 35 → 36
  (04-01) → 37 (06-02) → 38 (07-15); MSFT 400 → 420 (06-02) → 430 (06-10).

| `D` | Holdings (account: item) | USD part | HKD part (×FX) | `V_D` exact |
|---|---|---|---|---|
| 01-01 | none (before E1) | 0 | 0 | **0** |
| 01-02, 01-05 | A1 USD 10,000 | 10,000 | 0 | **10,000** |
| 01-06 | A1 USD 2,500; A1 AAPL 50 × 150 = 7,500; A2 HKD 20,000 | 10,000 | 20,000 × 5/39 = 100,000/39 | 390,000/39 + 100,000/39 = **490,000/39** |
| 01-31, 02-03 | A1 USD 2,500, AAPL 7,500 (50 × 150; on 02-03, 200 × 37.50); A2 0700 500 × 35 = 17,500, HKD 2,500. HKEX closed 01-29..31, so 0700 is the 01-28 close, 0 missed. | 10,000 | 20,000 × 5/39 | **490,000/39** |
| 03-09 (Sun) | A1 USD 10,000 − 7,500 − 1,000 + 2,250 = 3,750; A1 AAPL 150 × 45 = 6,750; A3 USD 1,000; A2 0700 17,500 + HKD 2,500 | 11,500 | 100,000/39 | 448,500/39 + 100,000/39 = **548,500/39** |
| 03-10, 03-31 | + A1 MSFT 10 × 400 = 4,000 | 15,500 | 100,000/39 | **704,500/39** |
| 04-02 | A1 USD 3,750 − 1,000 − 2 = 2,748; A1 HKD 7,750 − 7,000 = 750; A1 0700 200 × 36; AAPL 6,750; MSFT 4,000; A3 1,000; A2 0700 500 × 36, HKD 2,500 | 2,748 + 6,750 + 4,000 + 1,000 = 14,498 | (750 + 7,200 + 18,000 + 2,500) = 28,450 × 16/125 = 3,641.6 | **18,139.6 = 90,698/5** |
| 05-07 | as 04-02, plus A3 BUY MSFT 5 for 2,000 (A3 USD −1,000; MSFT 5 × 400) | 14,498 − 2,000 + 2,000 = 14,498 | 3,641.6 | **90,698/5** |
| 05-08 | + X5 1,000 (A3 USD 0) | 15,498 | 3,641.6 | **95,698/5** = 19,139.6 |
| 06-01 (Sun) | + X6 −3.50 (A3 USD −3.50) | 15,494.5 | 3,641.6 | **191,361/10** = 19,136.1 |
| 06-02 | + X9 5,000 (A3 4,996.50); MSFT 420; 0700 37 | 2,748 + 6,750 + 4,200 + 4,996.5 + 2,100 = 20,794.5 | (750 + 7,400 + 18,500 + 2,500) = 29,150 × 16/125 = 3,731.2 | **245,257/10** = 24,525.7 |
| 06-30 | A1 USD 2,748 + 2,000 = 4,748; HKD 750; 0700 200; MSFT 10; AAPL 0 (40 sold, 110 moved). A3 USD 4,996.5 − 2,100 + 1,720 = 4,616.5; MSFT 10 − 4 = 6; AAPL 110 × 50. A2 0700 500, HKD 2,500. | 4,748 + 4,300 + 4,616.5 + 2,580 + 5,500 = 21,744.5 | 29,150 × 16/125 = 3,731.2 | **254,757/10** = 25,475.7 |
| 2026-01-31 (Sat) | as 06-30; 0700 38 (closes of 2026-01-30) | 21,744.5 | (750 + 7,600 + 19,000 + 2,500) = 29,850 × 16/125 = 3,820.8 | **255,653/10** = 25,565.3 |

**Presented values** (Ruling 2.2, half up to cents):

- 490,000/39 = 12,564.102564… → **12,564.10**;
- 548,500/39 = 14,064.102564… → **14,064.10**;
- 704,500/39 = 18,064.102564… → **18,064.10**;
- the other totals terminate.

**Components** (P1-V2, V3, V5):

- HKD 20,000 × 5/39 = 100,000/39 = 2,564.102… → **2,564.10**;
- 0700 17,500 × 5/39 = 87,500/39 = 2,243.589… → **2,243.59**;
- HKD 2,500 × 5/39 = 12,500/39 = 320.512… → **320.51**.

On 04-02, A1's HKD 750 × 16/125 = **96**.

**P1-V4, split neutrality.** On the ex-date 02-03 the ledger quantity is 200 and the raw close is
37.50, so 200 × 37.50 = 7,500 = 50 × 150. The value is unchanged.

## 3. P1 TWR (Ruling 5.2 segment form) and `G`

The flow days are 01-02 (cash in), 01-06 (cash in), 03-10 (in kind), 05-08 (cash in) and 06-02
(cash in). `I^C`(01-06) = 100,000/39.

| Factor | Formula | Value |
|---|---|---|
| day 01-02 | `V(01-02)/(V(01-01) + 10,000)` | 10,000/10,000 = **1** |
| day 01-06 | `V(01-06)/(V(01-05) + 100,000/39)` | (490,000/39)/(390,000/39 + 100,000/39) = **1** |
| run 01-07..03-09 | `V(03-09)/V(01-06)` | 548,500/490,000 = **1,097/980** |
| day 03-10 | `(V(03-10) − I^K)/V(03-09)` | (704,500/39 − 4,000)/(548,500/39) = (704,500 − 156,000)/548,500 = **1** |
| run 03-11..05-07 | `V(05-07)/V(03-10)` | (90,698/5) × 39/704,500 = 3,537,222/3,522,500 = **1,768,611/1,761,250** |
| day 05-08 | `V(05-08)/(V(05-07) + 1,000)` | 19,139.6/19,139.6 = **1** |
| run 05-09..06-01 | `V(06-01)/V(05-08)` | 19,136.1/19,139.6 = **191,361/191,396** |
| day 06-02 | `V(06-02)/(V(06-01) + 5,000)` | 24,525.7/24,136.1 = **245,257/241,361** |
| run 06-03..06-30 | `V(06-30)/V(06-02)` | **254,757/245,257** |

**1 + TWR SI** (2025-01-01, 2025-06-30] = (1,097/980) × (1,768,611/1,761,250) × (191,361/191,396)
× (254,757/241,361). The 245,257 cancels.

- Exact: TWR = **14,849,541,313,483,073,959 / 79,734,639,592,304,900,000** = 0.18623701554…
- Presented: **0.186237015548**.

The multiplication of the four reduced factors was done with the calculator. Each factor above is
by hand.

**`G` SI** = `V(06-30)` − `V(01-01)` − (10,000 + 100,000/39 + 4,000 + 1,000 + 5,000)
= 25,475.7 − 20,000 − 100,000/39 = (2,135,523 − 1,000,000)/390 = **1,135,523/390** = 2,911.597…
→ **2,911.60**. Here 5,475.7 = 2,135,523/390 because 5,475.7 × 390 = 2,135,523.

**3M** (Ruling 5.4: `sub_months(2025-06-30, 3)`; 06-30 is a month-end, so 03-31; 91 days).

- `V(03-31)` = 704,500/39, the same holdings, prices and FX as 03-10.
- 1 + TWR = (1,768,611/1,761,250) × (191,361/191,396) × (254,757/241,361)
  → **4,858,889,415,394,247 / 81,361,877,135,005,000** = 0.059719485175.
- `G` = 25,475.7 − 704,500/39 − 6,000 = (9,935,523 − 7,045,000 − 2,340,000)/390 =
  **550,523/390** → **1,411.60**.
- `Y` = 3/12 = 1/4 < 1, so the annualized figure is `INSUFFICIENT_DATA`,
  `PERIOD_SHORTER_THAN_ONE_YEAR`.

**1Y ending 2025-06-30.** `B` = 2024-06-30 is before the inception base 2025-01-01, so it is
`INSUFFICIENT_DATA`, no reason, `WINDOW_BEFORE_INCEPTION`. The same holds for `G`.

**1Y (2025-01-31, 2026-01-31], 365 days, `Y` = 1:**

- The first segment is `V(03-09)/V(01-31)` = 1,097/980, the same as the SI first run, because
  `V(01-31)` = `V(01-06)`.
- Then the same factors to 06-30, times `V(2026-01-31)/V(06-30)` = 255,653/254,757.
- TWR = **15,182,201,166,172,444,711 / 79,734,639,592,304,900,000** → **0.190409102541**.
- The annualized figure equals it **exactly** (`Y` = 1).
- `G` = 25,565.3 − 490,000/39 − (4,000 + 1,000 + 5,000) = (9,970,467 − 4,900,000 − 3,900,000)/390 =
  **1,170,467/390** → **3,001.20**.

**SI to 2026-01-31** (395 days):

- the factors are as above (the run before 01-31 is 1), so the TWR is the same fraction,
  **0.190409102541**;
- `G` = `V` − flows = 25,565.3 − (20,000 + 100,000/39) = **1,170,467/390** → **3,001.20**;
- **`Y`** (Ruling 7.1): `add_months(2025-01-01, 12)` = 2026-01-01 ≤ `E`, and 13 months gives
  2026-02-01 > `E`, so `m` = 12 and `r` = 30. `Y` = 1 + 30/365 = **79/73**;
- **annualized** = (1 + TWR)^(73/79) − 1 = **0.174754609079**. Two methods agree: `Decimal`
  `prec` 60 (`exp`/`ln`), and a certified `Fraction` bisection on `a` with
  `(1+a)^79 ≤ (1+R)^73`, of width 6 × 10^−61. Both bracket ends round to the same 12-decimal value.
  The fixture's tolerance is 10^−10.

## 4. P2 (HKD, snapshot `S` = 2025-06-30)

- `V(06-29)`: the account is not reconstructable, so the total is `NOT_RECONSTRUCTABLE`.
- `V(06-30)` = 500 × 37 + 3,000 = **21,500**. The opening position has unknown basis, which does
  not block valuation (PRD §9.3).
- `V(07-02)`: the `SELL` of 200 for 7,400 gives 300 × 37 + 10,400 = **21,500**. HKEX was closed
  07-01, and 07-02 is a session.
- `V(07-31)` = 300 × 38 + 10,400 = **21,800**.
- TWR (06-30, 07-31] = 21,800/21,500 − 1 = 300/21,500 = **3/215** → 0.013953488372. There are no
  flows.
- `G` = **300**.
- Trailing 1 month from 07-31 gives 06-30 (month-end rule), the same window.
- A custom base of 06-29, or trailing 3 months (base 04-30), starts before `S`, so
  `NOT_RECONSTRUCTABLE`.

## 5. P3 (CNY): Southbound, staleness, CNH and an unpriced listing

FX period A: CNY per HKD **12/13**; CNY per USD **36/5**. SYNA prices: 10.00 (03-03), 10.50 (03-04),
gap 03-17..19, 11.00 (03-20).

| `D` | Holdings | `V_D` (CNY) |
|---|---|---|
| 03-02 | none | 0 |
| 03-03 | C1 CNY 100,000 − 20,000 = 80,000; SYNA 2,000 × 10 = 20,000 | **100,000** |
| 03-04 | C1 CNY 80,000 − 32,400 = 47,600; SYNA 2,000 × 10.50 = 21,000; 0700 1,000 × 35 = 35,000 HKD × 12/13 = 420,000/13 | 68,600 + 420,000/13 = **1,311,800/13** = 100,907.69 |
| 03-05, 03-17, 03-19 | + C2 USD 5,000 × 36/5 = 36,000; C2 HKD 10,000 × 12/13 = 120,000/13. SYNA's last print is 03-14 on 03-17..19. | 1,311,800/13 + 468,000/13 + 120,000/13 = **1,899,800/13** = 146,138.46 |
| 03-20 | SYNA 11.00, so +1,000 | **1,912,800/13** = 147,138.46 |
| 03-21 | + CNH 3,000 (untranslatable) | total `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` |
| 03-25 | C2 `BUY` NOP1 100 for 1,000 HKD: HKD 9,000 × 12/13 = 108,000/13; NOP1 unpriced | total `INSUFFICIENT_DATA`; `MISSING_PRICE_HISTORY` outranks `MISSING_FX_HISTORY` (Ruling 1.5) |

- **Staleness** (`market-data` Ruling 5.2):
  - 03-17: one missed session (03-17), so `AVAILABLE` + `STALE_DATA`;
  - 03-19: three missed sessions (03-17, 18, 19), so `LIMITED` + `STALE_DATA`;
  - the total takes the holding's state (Ruling 1.4 items 2–3).
- **Stale share** (Ruling 1.4 item 2; every component is positive, so gross equals net):
  21,000 / (1,899,800/13) = 273,000/1,899,800 = (÷1,400) **195/1,357** = 0.143699336772…
- **Value of priced holdings** (Ruling 1.4a):
  - 03-21: every component except the CNH cash, = `V(03-20)`'s components (SYNA 11.00), so
    **1,912,800/13** → **147,138.46**, excluded count **1**;
  - 03-25: 47,600 + 22,000 + 420,000/13 + 36,000 + 108,000/13 = (1,372,800 + 528,000)/13 =
    **1,900,800/13** → **146,215.38**, excluded count **2** (CNH cash; NOP1, 100 shares);
  - not emitted on 03-19 (the total is `LIMITED`, not suppressed) or 03-20 (`AVAILABLE`).
- **HKD native subtotal**:
  - 03-20: 0700 35,000 (an HKD listing, although paid in CNY) + HKD cash 10,000 = **45,000**;
  - 03-25: NOP1 has no native value, so `INSUFFICIENT_DATA` + `MISSING_PRICE_HISTORY`.
- **TWR:**
  - I^C on 03-05 = 36,000 + 120,000/13 = 588,000/13;
  - day 03-03 = 100,000/100,000 = 1;
  - run 03-04 = (1,311,800/13)/100,000 = **6,559/6,500**;
  - day 03-05 = (1,899,800/13)/(1,311,800/13 + 588,000/13) = 1;
  - run 03-06..03-20 = 1,912,800/1,899,800 = 19,128/18,998;
  - **(03-02, 03-20]** = (6,559/6,500)(19,128/18,998) − 1 = **35,242/2,205,125** → 0.015981860439;
  - **(03-02, 03-19]**: the run to 03-19 is 1, so 6,559/6,500 − 1 = **59/6,500** →
    0.009076923077, `LIMITED` + `STALE_DATA` (from `V(03-19)`);
  - **`G`** to 03-20 = 1,912,800/13 − 100,000 − 588,000/13 = **24,800/13** → 1,907.69. That is
    SYNA's +2,000 less the Southbound trade result (32,400 − 420,000/13 = 1,200/13).
  - **(03-02, 03-21]**: the CNH inflow on 03-21 is untranslatable, so `INSUFFICIENT_DATA` +
    `MISSING_FX_HISTORY` (Ruling 4.3), and the same for `G`;
  - **(03-02, 03-25]**: the end value is suppressed with both causes, so `MISSING_PRICE_HISTORY`.

## 6. P4, P5, P6

**P4 (USD), a purchase recorded before its deposit.** The inception base is 01-07. SYNU is 101.00,
then 102.00 from 01-10. NYSE was closed 01-09.

- `V(01-07)` = 0.
- `V(01-08)` = 10 × 101 − 1,000 = **10**.
- `V(01-09)` = 1,010, using the 01-08 close with 0 missed sessions.
- `V(01-10)` = 1,020.
- **SI TWR:** the first segment is `V(01-08)/V(01-07)` = 10/0, a non-positive base with a non-zero
  numerator. `INSUFFICIENT_DATA`, no reason, `NON_POSITIVE_BASE` (Ruling 5.3).
- `G` = 1,020 − 0 − 1,000 = **20**.
- **(01-08, 01-10]:** 1,010/(10 + 1,000) × 1,020/1,010 = 1,020/1,010, so the TWR is **1/101** →
  0.009900990099.

**P5 (USD), fully withdrawn and then re-funded:**

| Day or run | Factor |
|---|---|
| 01-02 | 1,000/(0 + 1,000) = 1 |
| 01-03 (outflow at the end of the day) | (0 + 1,000)/1,000 = 1 |
| run 01-04..06 | 0/0 = 1, `ZERO_CAPITAL_RUN` |
| 01-07 | 500/(0 + 500) = 1 |
| run 01-08..10 | 1 |

- The TWR is **0**, `AVAILABLE`.
- `G` = 500 − (1,000 − 1,000 + 500) = **0**.
- `V(01-05)` = **0**, `AVAILABLE`.

**P6 (HKD):** USD 550 and AAPL 10 at 45 (450 USD), plus CNY 1,000.

- **Period A** (HKD per USD 39/5; HKD per CNY 13/12):
  - 550 × 39/5 = **4,290**;
  - 450 × 39/5 = **3,510**;
  - 1,000 × 13/12 = **3,250/3** → 1,083.33;
  - total **26,650/3** → 8,883.33.
- **Period B** (125/16; 125/116):
  - 550 × 125/16 = **34,375/8** = 4,296.875 → **4,296.88** (an exact tie, rounded half away from
    zero);
  - 450 × 125/16 = **28,125/8** = 3,515.625 → **3,515.63** (a tie);
  - 1,000 × 125/116 = **31,250/29** = 1,077.586… → 1,077.59;
  - total 7,812.5 + 31,250/29 = **515,625/58** = 8,890.086… → **8,890.09**;
  - the independently presented parts sum to 8,890.10. That is within the (3 + 1)/2-cent bound of
    Ruling 2.4 item 2, and is deliberately not forced to sum.
- **TWR (03-02, 04-30]:**
  - day 03-03 = (26,650/3)/(7,800 + 3,250/3) = 1;
  - run to 04-30 = (515,625/58)/(26,650/3) = 1,546,875/1,545,700;
  - TWR = 1,175/1,545,700 = **47/61,828** → 0.000760173384.
  - `G` = 515,625/58 − 26,650/3 = (1,546,875 − 1,545,700)/174 = **1,175/174** → 6.75. This is pure
    FX, since AAPL is unchanged.

## 7. Ratification

- **Ratified:** all 93 expected items were derived independently of the engine. They use only
  `performance/1.1`, `market-data/1.8` and `ledger-replay/1.3` rulings, and decide nothing reserved:
  - no lot relief, fee capitalization, income timing or attribution is asserted;
  - FIFO is not exercised.
- **Not ratified:** that the engine passes; the loader's expansion of the compact market data into
  CP2 file layouts (that is the engineer's, and it must introduce no number); and the determinism
  and structural assertions S-1 to S-6, which need an engine run.
- **If the engine disagrees with a value,** that is a finding for the Quant, not a value to adjust.
