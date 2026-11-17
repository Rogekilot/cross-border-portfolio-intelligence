# `cp4_golden/1.0-part1`: hand derivation

**Author:** `quant-analyst`, 2026-10-02. **Convention set:** `risk/1.0`
(`methodology/CP4_RISK_CONVENTIONS.md`), on `performance/1.12` and `market-data/1.11`.
**Fixture:** `cp4_golden_part1.json` (24 assertions, 78 expected items).
**Calculator:** `derivation/cp4_part1_calculator.py` (standard library only; imports nothing from
`src/`).

**How the expected values were obtained.** Each value below is derived from the fixture's inputs by
the rulings cited, with the arithmetic shown. Where a series is long (P3, P4, P5, P11), it is built
from a short repeating pattern so that the sums have closed forms a reader can check on paper. The
calculator re-derives **every** item independently from the fixture's input blocks (market data,
listings, ledger events, requests), period by period, and `--closed` re-derives the P3 and P5
statistics a second way, from the closed forms in this document. **No value comes from the engine.**

**Re-run (read-only):**

```
python3 methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py \
        methodology/fixtures/cp4_golden/cp4_golden_part1.json --check --closed
python3 methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py --counts
```

The run record is §12.

---

## 1. Inputs common to every portfolio

**Grids** (Ruling 2.2). `DAILY` = every Monday–Friday; `WEEKLY` = every Friday; `MONTHLY` = the
last calendar day of each month.

**Prices.** Every listing's close is a step function: the close on a session is the latest step
dated on or before it. Steps on the long series fall on Fridays, so a Friday's valuation is that
Friday's step, and Monday to Thursday repeat the previous Friday's level.

**Calendars.** `SYN4_NYSE`, `SYN4_ECB` and `SYN4_RF_USD` list every weekday (no holidays,
deliberately, so the long series have closed forms). `SYN4_SSE` closes Monday 2025-09-29 to Friday
10-03 and Friday 10-17.

**FX** (`market-data` Ruling 1.3, `X(c→R) = x_R / x_c`). `x_USD` = 1.0800 throughout.

- HKD: 8.4000 before 2024-12-27, then alternating weekly from Friday 2024-12-27: 8.4000 (cycle index
  even) and 8.4420 (odd). So `X(HKD→USD)` = 1.08/8.4 = **9/70** or 1.08/8.442 = **60/469**, and
  (9/70)/(60/469) = 4221/4200 = **201/200**.
- CNY: 7.8000, so `X(CNY→USD)` = 1.08/7.8 = **9/65**; no quote on 2025-06-09..13 or 2025-09-11..12.

**Risk-free** (Ruling 4.3). `SIMPLE_YIELD` on ACT/365: 3.65 % gives `ρ = 0.0365/365 = 1/10,000` per
calendar day; 7.30 % (in force from 2025-07-01) gives `2/10,000`. A weekly period (7 days) therefore
earns **7/10,000** if it starts on or before Friday 2025-06-27 and **14/10,000** if it starts on or
after Friday 2025-07-04. A period's rate is the quote of the latest publication on or before the
period's **start**.

**Thresholds** (Ruling 7.1): weekly 51/155, daily 259/781, monthly 11/35. `--counts` re-counts them
over every end date 2001–2029.

**Square roots** (Ruling 3.4). For a square-root metric the fixture gives `Q` (`exact_square`) and
the sign; the presented value is `sign × √Q` rounded half-up to 12 decimals. The decimals shown here
are rounded for reading; the fixture's are exact presentations.

---

## 2. P1: monthly, 12 observations (P1-S1), and one day earlier (P1-S2)

**Window** (P1-S1, `E` = 2025-12-31). `B = sub_months(2025-12-31, 12)` = 2024-12-31 (month-end
rule). `B ≥ I₀` = 2024-12-30. `g_0` = 2024-12-31 = `B` (a month-end), `g_n` = 2025-12-31, `n` =
**12**, stubs 0 and 0.

**Value path.** 100 units, fully invested, no flow after inception, so `r_k` = the ratio of
month-end closes. A month-end on a weekend takes the Friday close (May 31 → May 30, Aug 31 → Aug 29,
Nov 30 → Nov 28); steps change on the 1st, so the month-end level is that month's step.

| Month | Level | `r_k` | exact | `rf_k` (days × ρ at the start) | `d_k = r_k − rf_k` |
|---|---|---|---|---|---|
| Jan | 106.00 | 106/100 − 1 | **3/50** = 0.06 | 31 × 1/10,000 = 0.0031 | 0.0569 |
| Feb | 103.88 | 0.98 × 106 / 106 − 1 | **−1/50** | 28/10,000 = 0.0028 | −0.0228 |
| Mar | 98.00 | 98/103.88 = 100/106 | **−3/53** = −0.056603… | 0.0031 | −0.059703… |
| Apr | 92.12 | 0.94 | **−3/50** | 0.0030 | −0.063 |
| May | 96.00 | 9,600/9,212 = 2,400/2,303 | **97/2,303** = 0.042118… | 0.0031 | 0.039018… |
| Jun | 100.80 | 1.05 | **1/20** | 0.0030 | 0.047 |
| Jul | 105.84 | 1.05 | **1/20** | **0.0031** (quote of 06-30: 3.65 %) | 0.0469 |
| Aug | 103.00 | 103/105.84 | **−71/2,646** = −0.026832… | 31 × 2/10,000 = 0.0062 | −0.033032… |
| Sep | 108.15 | 1.05 | **1/20** | 0.0060 (quote of Fri 08-29) | 0.044 |
| Oct | 105.00 | 105/108.15 = 100/103 | **−3/103** = −0.029126… | 0.0062 | −0.035326… |
| Nov | 110.25 | 1.05 | **1/20** | 0.0060 | 0.044 |
| Dec | 112.00 | 112/110.25 = 1.75/110.25 + 1 | **1/63** = 0.015873… | 0.0062 (quote of Fri 11-28) | 0.009673… |

`Σ rf_k` = 0.0518 = 259/5,000. **July is the start-of-period bite**: its period starts 06-30, when
3.65 % was quoted, so 31/10,000, not 31/5,000.

**Sums** (exact in the fixture; decimals to 15 places here):

- `Σ r_k` = 0.125429048541…, `r̄` = 0.010452420711…
- `Σ (r_k − r̄)²` = 0.023087254522…, `s²(r)` = that / 11 = 0.002098841320…
- `d̄` = `r̄ − 0.0518/12` = 0.006135754045…
- below the target (`d_k < 0`): Feb, Mar, Apr, Aug, Oct, five periods; `Σ min(0, d_k)²` =
  0.022800² + 0.059703…² + 0.063² + 0.033032…² + 0.035326…² = 0.010392498089…

**Statistics** (`A` = 12):

| Item | Formula | `Q` | Value |
|---|---|---|---|
| volatility | `√(12 s²)` | 0.025186095842… | **0.158701278641** |
| downside deviation | `√(12 × Σmin² / 12)` = `√Σmin²` | 0.010392498089… | **0.101943602496** |
| Sharpe | `sign(d̄) √(12 d̄² / s²)` | 0.215247207149… | **0.463947418518** |
| Sortino | `sign(d̄) √(12 d̄² × 12 / Σmin²)` | 0.521649053215… | **0.722252762691** |

**Maximum drawdown** (Ruling 1.1). `W` = level/100: 1, 1.06, 1.0388, 0.98, **0.9212**, 0.96, 1.008,
1.0584, 1.03, 1.0815, 1.05, 1.1025, 1.12. The running peak reaches 1.06 in January; the deepest
point below it is April's 0.9212: `0.9212/1.06 − 1 = −0.1388/1.06 = ` **−347/2,650**
(−0.130943396226). Peak 2025-01-31, trough 2025-04-30, recovery 2025-09-30 (1.0815 ≥ 1.06; July's
1.0584 is not). RD-1: `TWR(01-31, 04-30] = 92.12/106 − 1`, the same number.

**State.** `n` = 12: N1 = 11 ≤ 12 < N3 = 35, so the four statistics are `LIMITED` (no reason, detail
`OBSERVATIONS_BELOW_STANDARD`), with their values. The maximum drawdown has no statistical minimum:
`AVAILABLE`.

**P1-S2** (`E` = 2025-12-30). `B` = `sub_months(2025-12-30, 12)` = 2024-12-30 (not a month-end, so
the same day). `g_0` = 2024-12-31 (stub 1 day), `g_n` = 2025-11-30 (stub 30 days), `n` = **11** =
N1: still `LIMITED`. The first 11 returns above give `s²` = 0.002305520050…, volatility² =
0.027666240602…, volatility **0.166331718570**. The drawdown is unchanged (its trough and recovery
are inside both windows): −347/2,650.

---

## 3. P2: the maximum-drawdown debt (M1-F6)

Friday closes (100 units bought at 100.00 on Monday 2025-12-01): 12-05 **120**, 12-12 **100**,
12-19 **110**, 12-26 **99**, 2026-01-02 **105**.

**P2-D1** (base 2025-12-12). Weekly grid points 12-12, 12-19, 12-26, 01-02; `n` = 3. Returns:
110/100 − 1 = **1/10**; 99/110 − 1 = **−1/10**; 105/99 − 1 = 6/99 = **2/33**.

| Convention | Running peak | Trough | Drawdown |
|---|---|---|---|
| **Canonical** (Ruling 1.1): within the window, base included | 1, then 1.1 | 0.99 | 0.99/1.1 − 1 = **−1/10** |
| All-history running maximum (rejected) | 1.2 (from 12-05, before the window) | 0.99 | 0.99/1.2 − 1 = −0.175 |
| Base excluded from the peak search (rejected) | 1.1 | 0.99 | −0.1 |

Peak 12-19, trough 12-26, no recovery (1.05 < 1.1). **The all-history convention disagrees here.**

The **daily** item: 15 weekdays from 12-15 to 01-02. Prices change only on Fridays, so the daily
path is the weekly path with flat stretches: the minimum drawdown is the same −1/10 (RD-4: the weekly
grid is a subset of the daily one). The level is 110 on every weekday from Friday 12-19 to Thursday
12-25, and the drop is on 12-26, so by Ruling 1.1 the peak date is the **latest** day at the
high-water mark: **2025-12-25**.

Volatility over 3 periods: `n` = 3 < 51, `INSUFFICIENT_DATA`, `INSUFFICIENT_OBSERVATIONS`.

**P2-D2** (base 2025-12-05, the all-time high). Points 12-05 … 01-02, `n` = 4; `W` = 1, 100/120,
110/120, 99/120, 105/120.

| Convention | Drawdown |
|---|---|
| **Canonical** (base included) | 99/120 − 1 = **−7/40** = −0.175 (peak = the base, 12-05; trough 12-26) |
| Base excluded (peak search from 12-12) | (99/120)/(110/120) − 1 = −0.1 |
| All-history | −0.175 |

**The base-excluded convention disagrees here.** Between them, P2-D1 and P2-D2 make every rejected
reading fail at least one assertion (Ruling 1.5).

---

## 4. P3: the long weekly cycle

**Path.** 100 units bought at 100.00 on Friday 2022-12-30 (`I₀` = 2022-12-29). The close alternates
on Fridays: index `j = (Friday − 2022-12-30)/7`; level **100** for even `j`, **104** for odd `j`.
Weekly returns are therefore `u = 104/100 − 1 =` **+1/25** (a period starting at an even index) and
`w = 100/104 − 1 =` **−1/26** (starting at an odd index).

Useful values: `u + w = 1/650`; `u − w = 51/650`; the mean of one `u` and one `w` is `1/1300`, and
each deviates from it by `±51/1300`.

### 4.1 P3-A1: 3Y weekly (the PRD default), `AVAILABLE`

**Window.** `E` = Friday 2026-01-02, `B` = Monday 2023-01-02, `g_0` = Friday 2023-01-06 (`j` = 1,
level 104), `g_n` = 2026-01-02 (`j` = 157, level 104). `n` = (1,092 days)/7 = **156** ≥ 155:
`AVAILABLE`. Stubs 4 and 0.

**Counts.** Periods start at `j` = 1 … 156: 78 odd starts (`w`) and 78 even (`u`).
Risk-free regimes by start date: `j` = 1 … 130 (2023-01-06 … 2025-06-27) at 7/10,000, of which 65 `w`
and 65 `u`; `j` = 131 … 156 (2025-07-04 … 2025-12-26) at 14/10,000, 13 `w` and 13 `u`.

- `r̄` = 1/1300; `Σ (r − r̄)²` = 156 × (51/1300)²; `s²` = (156/155)(51/1300)² = **7,803/5,037,500**.
- **Volatility** `Q` = 52 s² = 52 × 156 × 2,601 / (155 × 1,690,000) = **7,803/96,875**
  (= 0.0805471…); value **0.283808204205**.
- `d̄ = 1/1300 − (130 × 7 + 26 × 14)/(156 × 10,000) = 1,200/1,560,000 − 1,274/1,560,000 =`
  **−37/780,000**. The mean weekly return (0.000769) is below the mean weekly rate (0.000817).
- `Σ min(0, d)² = 65 (1/26 + 7/10,000)² + 13 (1/26 + 14/10,000)²` = **156,444,529/1,300,000,000**
  (the `u` periods are above the rate and contribute 0).
- **Downside deviation** `Q` = 52 × Σ/156 = Σ/3 = **156,444,529/3,900,000,000**; value
  **0.200284751778**.
- **Sharpe** `Q` = 52 d̄²/s² = **42,439/561,816,000**, sign −; value **−0.008691315579**.
- **Sortino** `Q` = 52 d̄² × 156/Σ = **71,188/469,333,587**, sign −; value **−0.012315798606**.
- **Maximum drawdown**: every 104 → 100 step is −1/26 and the path never goes lower:
  **−1/26**. Earliest trough 2023-01-13 (`g_1`), peak = the base 2023-01-06, recovery 2023-01-20.

### 4.2 P3-A2: the same 3Y window at DAILY and MONTHLY (frequency invariance)

- **DAILY**: `g_0` = `B` = Monday 2023-01-02 (a weekday), `g_n` = 2026-01-02; `n` = **784** ≥ 781:
  `AVAILABLE`. Daily returns are 0 except on Fridays, where they equal the weekly returns (the path
  is flat Monday–Thursday). On this window there are 157 non-zero daily returns: the Friday
  2023-01-06 move (2022-12-30 at 100 → 104) and the 156 weekly moves. The calculator sums them:
  `Q` = **25,666/319,725**, volatility **0.283328848745** (√260 scaling of a variance spread over
  five times as many periods recovers the weekly figure to within 0.2 %).
- **MONTHLY**: `g_0` = 2023-01-31, `g_n` = 2025-12-31, `n` = **35** ≥ 35: `AVAILABLE`. A month-end's
  level is that of the latest Friday on or before it, so a monthly return is +1/25, −1/26 or 0
  according to the parity of the two Fridays. `Q` = **409,761/62,846,875**, volatility
  **0.080746455372**. (Monthly sampling of a two-week cycle cancels most of the movement: the low
  figure is aliasing, a property of the path, not of the method.)
- **The state is `AVAILABLE` at all three frequencies** (with 3Y weekly in P3-A1): Ruling 7.1's
  invariance on a full window.

### 4.3 P3-A3: 1Y, `LIMITED` at every frequency

**Weekly.** `B` = 2025-01-02, `g_0` = Friday 2025-01-03 (`j` = 105, level 104), `n` = **52**: 26
`w` and 26 `u`; rate regimes: starts `j` = 105 … 130 (26, 13/13) at 7/10,000, `j` = 131 … 156 (26,
13/13) at 14/10,000.

- `s²` = (52/51)(51/1300)² = **51/32,500**; volatility `Q` = 52 s² = **51/625**; value
  **0.285657137142**.
- `d̄` = 1/1300 − (26 × 7 + 26 × 14)/(52 × 10,000) = 1/1300 − 21/20,000 = **−73/260,000**.
- `Σ min(0, d)²` = 13 (1/26 + 7/10,000)² + 13 (1/26 + 14/10,000)² = **10,554,281/260,000,000**;
  downside `Q` = 52 Σ/52 = the same; value **0.201478009871**.
- Sharpe `Q` = 52 d̄²/s² = **5,329/2,040,000**, value **−0.051110223067**; Sortino `Q` =
  52 d̄² × 52/Σ = **277,108/52,771,405**, value **−0.072464483888**.
- Maximum drawdown −1/26 (base 01-03 at 104, trough 01-10, recovery 01-17).

**Daily** `n` = **261** (259 ≤ 261 < 781), `Q` = **346,243/4,241,250**, value **0.285721923185**.
**Monthly** `n` = **11** (= N1), `Q` = **6,183/1,161,875**, value **0.072949096889**. All `LIMITED`.

### 4.4 P3-A4: 27 observations

Base 2025-06-27 (`j` = 130, level 100) to 2026-01-02: `n` = **27** < 51. Volatility and Sharpe:
`INSUFFICIENT_DATA`, `INSUFFICIENT_OBSERVATIONS`, no value. Maximum drawdown (no minimum): the first
period rises to 104 on 07-04, the second falls back: **−1/26**, peak 07-04, trough 07-11, recovery
07-18.

### 4.5 P3-A5: 5Y on a 3-year-old portfolio

`B` = `sub_months(2026-01-02, 60)` = 2021-01-02 < `I₀` = 2022-12-29: refused,
`WINDOW_BEFORE_INCEPTION`, no effective window, no value (Ruling 7.2).

### 4.6 P3-A6: `MAX_AVAILABLE`

`B` = `I₀` = 2022-12-29; `g_0` = Friday 2022-12-30 (`j` = 0, level 100); no insufficient period, so
`max_available_start` = `INCEPTION`; `n` = **157**: starts `j` = 0 … 156, 79 even (`u`) and 78 odd
(`w`). `r̄` = (79/25 − 78/26)/157 = (79/25 − 3)/157 = (4/25)/157 = 4/3,925.

- Volatility `Q` = **205,479/2,551,250**, value **0.283796616177**.
- Rates: starts `j` = 0 … 130 (131 periods) at 7/10,000, `j` = 131 … 156 (26) at 14/10,000;
  `d̄` = 4/3,925 − (131 × 7 + 26 × 14)/(157 × 10,000) = (1,600 − 1,281)/1,570,000 = 319/1,570,000 > 0.
  Sharpe `Q` = **223,568,917/161,301,015,000**, value **+0.037229496383**. (One extra up-week turns
  the mean excess positive: a short reminder that the sign of a Sharpe ratio over a few years is
  fragile, which is why `LIMITED` exists.)
- Maximum drawdown −1/26 (peak 2023-01-06, the first time at 104; trough 01-13; recovery 01-20).

### 4.7 P3-A7: a full year ending on a Wednesday

`E` = Wednesday 2025-12-31, `B` = 2024-12-31. `g_0` = Friday 2025-01-03 (stub **3** days), `g_n` =
Friday 2025-12-26 (stub **5** days), `n` = **51** = N1: `LIMITED`. A full year can have 51 weekly
observations; the HG1 round-4 floor of 52 would have refused it.

Periods start at `j` = 105 … 155: 26 odd (`w`) and 25 even (`u`), so `r̄ = (25/25 − 26/26)/51 = 0`
and `s² = Σ r²/50 = (25/625 + 26/676)/50 = (1/25 + 1/26)/50 = 51/32,500`. Volatility `Q` =
**51/625**, value **0.285657137142** (the same as P3-A3 by coincidence of the counts). Drawdown
−1/26.

---

## 5. P4: cash only (USD, no interest)

`r_k` = 0 for every period (10,000 USD, nothing else).

**P4-C1** (`E` = 2026-01-30). `B` = 2023-01-30, `g_0` = 2023-02-03, `n` = 156 (`AVAILABLE` count).

- Volatility: `s²` = 0, `Q` = 0, value **0.000000000000**, sign 0, `AVAILABLE`. A fact.
- Maximum drawdown: **0**, no dates.
- Sharpe and Sortino: `s²(r)` = 0 → `INSUFFICIENT_DATA`, `ZERO_VOLATILITY` (Rulings 6.5, 6.6).
- Downside deviation: every `d_k = −rf_k < 0`. Starts 2023-02-03 … 2025-06-27: **126** periods at
  7/10,000; 2025-07-04 … 2026-01-23: **30** at 14/10,000. `Σ d²` = 126 × 49/10⁸ + 30 × 196/10⁸ =
  (6,174 + 5,880)/10⁸ = 12,054/10⁸ = 6,027/50,000,000. `Q` = 52 × Σ/156 = Σ/3 =
  **2,009/50,000,000**; value **0.006338769597**: the root-mean-square weekly shortfall below the
  rate (0.000879, from weekly shortfalls of 0.07 % and 0.14 %), scaled by √52. It is a shortfall
  below the risk-free rate, not a loss (Ruling 6.3).

**P4-C2** (`E` = 2026-02-27). `g_0` = 2023-03-03, `n` = 156. Starts 2023-03-03 … 2025-06-27: **122**
at 7/10,000; 2025-07-04 … 2026-02-20: **34** at 14/10,000. The period starting Friday 2026-02-06 has
no quote on 02-05 or 02-06: the latest quote is Wednesday 02-04 (7.30 %), `m` = 2 missed
publications → `LIMITED` + `STALE_DATA` (Ruling 4.4). The rate value is the same 14/10,000.
Downside `Q` = (122 × 49 + 34 × 196)/(3 × 10⁸) = (5,978 + 6,664)/(3 × 10⁸) = **2,107/50,000,000**,
value **0.006491532947**, `LIMITED`, reason `STALE_DATA`, detail `RISK_FREE_STALE`.

Sharpe: `INSUFFICIENT_DATA` (`ZERO_VOLATILITY`) with **no reason**: the only cause carrying a code
(`STALE_DATA`) is at the `LIMITED` level and does not compete (`performance` Ruling 1.5 (1.1)).
Volatility: 0, `AVAILABLE` (no risk-free dependency).

**P4-C3** (`E` = 2026-03-27). The period starting Friday 2026-03-06 finds no quote from Monday 03-02
to Friday 03-06; the latest is Friday 02-27, `m` = 5 → `INSUFFICIENT_DATA` + `STALE_DATA`. The
downside deviation is suppressed; volatility is 0, `AVAILABLE`.

---

## 6. P5: HKD cash in a USD portfolio (multi-currency)

84,000 HKD deposited 2024-12-30. `V(g)` = 84,000 × `X(HKD→USD, u(g))`. At Friday `g`, the cycle
index is `(g − 2024-12-27)/7`; even → 8.4000 → 9/70 (`V` = 10,800); odd → 8.4420 → 60/469
(`V` = 5,040,000/469 = 10,746.27…).

**P5-M1** (1Y to 2026-01-02). `g_0` = 2025-01-03 (index 1, odd: low value), `n` = 52. Returns
alternate, starting with a rise: low → high = (9/70)/(60/469) − 1 = **+1/200**; high → low =
**−1/201**. 26 of each; each rate regime holds 13 of each.

- `r̄` = (1/200 − 1/201)/2 = **1/80,400**; deviations ±(1/200 + 1/201)/2 = ±401/80,400.
- `s²` = (52/51)(401/80,400)²; volatility `Q` = 52 s² = **27,175,369/20,604,510,000**; value
  **0.036316716806**.
- `d̄` = 1/80,400 − 21/20,000 = **−4,171/4,020,000**.
- `Σ min(0, d)²` = 13 (1/201 + 7/10,000)² + 13 (1/201 + 14/10,000)² (the rises exceed both rates);
  downside `Q` = 52 Σ/52 = **765,227,437/808,020,000,000**; value **0.030774018556**.
- Sharpe `Q` = **887,259,291/402,002,500**, value **−1.485630821718**; Sortino `Q` =
  **69,588,964/22,639,865**, value **−1.753207295085**.
- Maximum drawdown: the first fall (high → low) is −1/201 and nothing is deeper: **−1/201**; peak
  01-10 (the first high), trough 01-17, recovery 01-24.

`LIMITED` (52 < 155) throughout, except the drawdown (`AVAILABLE`).

---

## 7. P6 and P9: two metamorphic equalities

**P6** receives 100 SYN3 units by external in-kind transfer on 2022-12-30, with no cost basis.
`performance` Ruling 4.1–4.2: the in-kind inflow is valued at the 12-30 close (100 × 100.00) at the
end of the day, so `V(12-30)` = 10,000, exactly as P3 after its purchase. Every later valuation is
100 × the close, as in P3. So every periodic return, and every statistic, equals P3's: **P6-B1 =
P3-A1** (volatility, Sharpe, drawdown). No risk statistic reads cost basis, so `MISSING_COST_BASIS`
cannot appear (Ruling 7.5).

**P9** is P3 plus, on Wednesday 2025-06-11, a deposit of 10,400 USD and a purchase of 100 more units
at that day's close, 104.00 (the level of Friday 06-06, `j` = 127, odd). The week (06-06, 06-13] in
segment form (`performance` Ruling 5.2), with the flow day 06-11:

- run (06-06, 06-10]: `V` stays 10,400 → factor 1;
- flow day 06-11: (`V(06-11)` + 0 − 0) / (`V(06-10)` + 10,400) = 20,800/20,800 = 1;
- run (06-11, 06-13]: 200 × 100 / (200 × 104) = 25/26.

Factor 25/26, so `r` = **−1/26**, as in P3 (P9-W0 shows the three weeks around it). Every statistic
over the 3Y window equals P3-A1's (**P9-W1**).

---

## 8. P7: missing FX

78,000 CNY deposited 2024-12-30; with every quote present, `V` = 78,000 × 9/65 = 10,800 and every
return is 0.

- **At Friday 2025-06-13** the latest CNY quote is Friday 06-06; 5 fixing days (06-09 … 06-13) are
  missed: `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY` (`market-data` Ruling 1.6). Both periods that use
  `V(06-13)`, (06-06, 06-13] and (06-13, 06-20], are `INSUFFICIENT_DATA` with that reason.
- **At Friday 2025-09-12** two fixings (09-11, 09-12) are missed: `LIMITED` + `STALE_DATA`. The
  periods (09-05, 09-12] and (09-12, 09-19] are `LIMITED`. The interior day 09-11 is not an input
  (Ruling 2.1), whatever its own state.

**P7-F1** (1Y): the window contains the insufficient periods, so volatility and drawdown are
`INSUFFICIENT_DATA`, reason **`MISSING_FX_HISTORY`** (the code at the `INSUFFICIENT` level),
details `PERIOD_INSUFFICIENT` and `STALE_PERIODS` (2 stale periods); volatility also carries
`OBSERVATIONS_BELOW_STANDARD` (52 < 155), a `LIMITED`-level cause that does not set the reason.

**P7-F2** (`MAX_AVAILABLE`): the last insufficient period ends 2025-06-20, so the base is **06-20**
(`AFTER_INSUFFICIENT_PERIOD`); `n` = (2026-01-02 − 2025-06-20)/7 = **28**; stub 173 days from `I₀`.

- Volatility: 28 < 51 → `INSUFFICIENT_DATA`, **no reason** (the count cause has no code; the stale
  periods are `LIMITED`-level and do not compete); details `INSUFFICIENT_OBSERVATIONS`,
  `STALE_PERIODS`.
- Maximum drawdown: every return is 0 → **0**; two of 28 periods are `LIMITED` → `LIMITED` +
  `STALE_DATA`, `stale_period_count` = 2.

---

## 9. P8: a recently listed security, held alone

First print Monday 2025-10-06 at 100.00; 100 units bought then (`I₀` = Sunday 10-05).

- **P8-L1**: 1Y requested, `B` = 2025-01-02 < `I₀`: `WINDOW_BEFORE_INCEPTION`.
- **P8-L2** (`MAX_AVAILABLE`): `g_0` = the first Friday on or after 10-05 = **10-10** (stub 5 days:
  the first week's +3 % is not an observation), `n` = **12**. Friday levels from the base: 103, 101,
  98, 105, 104, 99, 95, 100, 102, 97, 101, 106, 108. Returns: **−2/103, −3/101, 1/14, −1/105,
  −5/104, −4/99, 1/19, 1/50, −5/102, 4/97, 5/101, 1/53** (each the ratio of consecutive levels).
- Volatility: 12 < 51, `INSUFFICIENT_DATA`, `INSUFFICIENT_OBSERVATIONS`.
- Maximum drawdown: running peak 103, then 105 (10-31); deepest below it 95 (11-21):
  95/105 − 1 = **−2/21** (the earlier dip 98/103 − 1 = −5/103 is shallower). Recovery 12-26 (106 ≥
  105).

---

## 10. P10: the Shanghai holidays (CNY reporting, no CNY risk-free series)

1,000 shares bought at 10.00 on Friday 2025-09-19 (`R` = CNY, so no FX). Steps: 09-26 **10.50**;
Monday 10-06 (the first session after the closed week) **11.55**; Thursday 10-16 **11.00**. SSE is
closed 09-29 … 10-03 and Friday 10-17.

**Weekly** (base 09-19): valuations at Fridays 09-19 (10.00), 09-26 (10.50), 10-03 (latest session
≤ 10-03 is 09-26: **10.50**, 0 sessions missed, `CURRENT`), 10-10 (11.55), 10-17 (closed: Thursday's
**11.00**, 0 missed). Returns **1/20**, **0** (the closed week, kept), **1/10** (11.55/10.50),
**−1/21** (11/11.55 = 20/21).

**Daily** (base 09-19, 20 weekdays): 0 on every day without a new close; **1/20** on 09-26; **0** on
each closed day 09-29 … 10-03 (each valued at 09-26's close); **1/10** on Monday 10-06 (from 10.50:
the whole closed week's move lands on the first session); **−1/21** on 10-16; **0** on the closed
Friday 10-17.

**Maximum drawdown** (weekly): `W` = 1, 1.05, 1.05, 1.155, 1.1 → **−1/21** (peak 10-10, trough
10-17).

**Sharpe and downside deviation:** no CNY risk-free series in `M` → `NO_RISK_FREE_SOURCE`; and
`n` = 4 < 51 → `INSUFFICIENT_OBSERVATIONS`. Both causes are `INSUFFICIENT`-level with no code:
**no reason**, both details listed.

---

## 11. P11: a recently listed security inside an established portfolio

20,000 USD and 100 SYN3 at 100.00 on 2022-12-30 (10,000 cash left); on Monday 2025-10-06, 100 SYN8 at
its first print, 100.00, from the cash.

- Before 10-06: `V` = 100 × SYN3 + 10,000, alternating 20,000 and 20,400, so the weekly returns are
  **+1/50** and **−1/51**. SYN8's price is never needed before 10-06 (quantity 0; Ruling 0.2).
- The week (10-03, 10-10] contains the purchase (an internal exchange, not a flow). Friday 10-03
  is `j` = 144 (even), so SYN3 is at 100.00 and `V(10-03)` = 100 × 100 + 10,000 = 20,000. Friday
  10-10 is `j` = 145 (odd): `V(10-10)` = 100 × 104 + 100 × 103 = 20,700, so `r` =
  20,700/20,000 − 1 = **+7/200**.
- After: `V` = 100 × (SYN3 + SYN8).
- 3Y window (`n` = 156): `AVAILABLE`. The calculator gives volatility **0.148577273401** and Sharpe
  **−0.125657359028** (their `Q`s are in the fixture; the sums are long but every term is a ratio of
  the levels above).
- **Maximum drawdown −11/208**: at 2025-11-07, `V` = 100 × 104 + 100 × 104 = 20,800 (the running
  peak); at 12-12, `V` = 100 × 100 + 100 × 97 = 19,700; 19,700/20,800 − 1 = −1,100/20,800 =
  **−11/208**. Nothing earlier is deeper (the pre-October path dips by at most 1/51; 11-21 gives
  19,900/20,800 − 1 = −9/208). Recovery 2026-01-02: 100 × 104 + 100 × 108 = 21,200 ≥ 20,800.

---

## 12. Run record

Run on 2026-10-02 with the system `python3` (3.9.6), read-only, from the repository root:

```
$ python3 methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py \
          methodology/fixtures/cp4_golden/cp4_golden_part1.json --check --closed
ok  P3-A1 volatility^2 7803/96875
ok  P3-A1 downside^2 156444529/3900000000
ok  P3-A1 sharpe^2 42439/561816000
ok  P3-A1 sortino^2 71188/469333587
ok  P3-A3 volatility^2 51/625
ok  P3-A3 downside^2 10554281/260000000
ok  P3-A3 sharpe^2 5329/2040000
ok  P3-A3 sortino^2 277108/52771405
ok  P5-M1 volatility^2 27175369/20604510000
ok  P5-M1 downside^2 765227437/808020000000
ok  P5-M1 sharpe^2 887259291/402002500
ok  P5-M1 sortino^2 69588964/22639865
CLOSED FORMS AGREE
smallest distance of a square-root value from a rounding boundary: 0.010682301740 quanta ( OK ; need > 1e-18 )
CHECK PASSED - 0 difference(s)

$ python3 methodology/fixtures/cp4_golden/derivation/cp4_part1_calculator.py --counts
… 12 WEEKLY 51 52 … 36 WEEKLY 155 156 … (all nine rows as risk/1.0 Ruling 7.1)
N1 and N3 AGREE with the full-window minima
```

**The check is not blind.** Patched in memory (no file changed), the calculator's own `--check`
fails under each of these mutations, in the items the fixture's structural assertions name:

| Mutation | Differences | Items |
|---|---|---|
| peak search excludes the base (M-DD2) | 2 | P2-D2 |
| peak date = earliest at the high-water mark (M-DD4) | 1 | P2-D1 (daily) |
| variance ÷ n instead of n − 1 | 44 | every non-zero volatility and every Sharpe |
| daily annualization 252 instead of 260 | 4 | P3-A2, P3-A3 (daily) |
| weekly thresholds 52/156 (HG1 round 4) | 46 | thresholds everywhere; P3-A7's state |
| risk-free quote at the period's end | 33 | P1-S1 rates (July) and every rf-dependent value |

M-DD1 (all-history running peak) cannot be expressed in a calculator that, by Ruling 1.3, only ever
sees the window's own series; its expected effect (−0.175 against −0.1 in P2-D1) is stated in the
fixture's `counter_conventions` and §3.
