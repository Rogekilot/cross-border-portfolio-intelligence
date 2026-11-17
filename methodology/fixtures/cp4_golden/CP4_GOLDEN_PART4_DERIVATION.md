# `cp4_golden/1.0-part4`: hand derivation

**Author:** `quant-analyst`, 2026-10-03. **Conventions:** `risk/1.9` (frozen for CP4 acceptance),
`performance/1.12`, `market-data/1.14`. No ruling is changed or added by this part.

Part 4 pins the two paths that run on admitted sources today and that no item of parts 1 to 3 pins
(risk §15.1, last paragraph). It is a separate file, so `cp4_golden/1.9-part3` is not re-issued.

| Path | Assertions | Items | Rulings |
|---|---|---|---|
| 1. The risk-free quote at instant `t` in Current mode | R41-C3, R41-C2, R41-C1 | 6 | 4.3, 4.4, 5.8 items 4, 5 and 7; performance 1.7 |
| 2. The default view of a benchmark-relative statistic | R41-V1, R42-V0 | 5 | 7.7 (1.2) and (1.6), 2.3, 5.2, 6.7 |

That gives 5 assertions, 11 items and 10 mutations (M-D1 to M-D10).

**Files.**

- `cp4_golden_part4.json` (the fixture);
- `derivation/cp4_part4_closed_forms.py`. It evaluates the arithmetic below and shares no code with
  the calculators;
- `derivation/cp4_part4_calculator.py`. It re-derives every item from the fixture's inputs, reusing
  the part-3 calculator.

Run, read-only, in `derivation/`:

```
python3 cp4_part4_closed_forms.py ../cp4_golden_part4.json
python3 cp4_part4_calculator.py ../cp4_golden_part4.json --check --mutations --retrieval
```

## 0. Inputs

- **SYN51** (USD, calendar SYN5_NYSE). The close is 100.00, and from Monday 2022-01-03 it alternates
  each Monday between 100.00 (even week index `j`) and 104.00 (odd `j`). `j` counts the weeks from
  2022-01-03. The close is kept Tuesday to Friday. SYN5_NYSE is Monday to Friday, with one closed
  weekday: Thursday **2025-11-27** (US Thanksgiving).
- **SYN5_BM_US_TR** (USD, gross total return, SYN5_NYSE). Each Monday from 2022-01-03 the level runs
  through 1000, 1010, 1000, 1020 in turn (by `j mod 4`).
- **SYN5_BM_YOUNG_TR** has the same cycle, with **no level before 2024-06-03**.
- **SYN5_UST13_USD** is a `SIMPLE_YIELD` on ACT/365. It quotes 3.65 % up to 2025-11-25 and
  **7.30 % from 2025-11-26**.
  - Per calendar day (Ruling 4.3): `ρ = 0.0365/365 = 1/10000`, then `2/10000`.
  - Its publication calendar SYN5_RF_USD runs Monday to Friday, closed 2025-11-27, and publishes at
    **20:00 America/New_York**. In November (EST) that is **01:00 UTC the next day**.
- **P41.** On 2024-11-01 it deposits 10,400 USD and buys 100 SYN51 at 104.00 (`j` = 147, odd), so
  `I_0` = 2024-10-31.
  - It holds no cash afterwards, so every `r_k` is SYN51's own price return.
  - It selects SYN5_BM_US_TR.
- **P42.** On 2022-01-07 it deposits 10,000 and buys 100 SYN51 at 100.00, so `I_0` = 2022-01-06. It
  selects SYN5_BM_YOUNG_TR.
- **Files** (`market_data.retrieval.files`):
  - prices and benchmarks: rows up to 11-26 retrieved 2025-11-26 22:00 UTC (the 11-26 close is
    21:00 UTC), the rest 11-28 22:00;
  - ECB: up to 11-26 retrieved 11-26 16:00 UTC (published 15:00), the rest 11-28 16:00;
  - risk-free: **RF-1**, rows up to 11-25, retrieved 11-26 02:00 (the 11-25 quote was published at
    01:00 on 11-26); **RF-2**, the 11-26 row alone, retrieved **2025-11-27 01:15** (published 01:00);
    **RF-3**, the rest, retrieved 11-29 02:00.
  - `--retrieval` verifies the after-retrieval test for all 4,558 rows. It also checks that at the
    three instants, exactly one row is due but not in `M_t`: the 11-26 quote at 01:10.

## 1. The risk-free quote at instant `t` (R41-C3, R41-C2, R41-C1)

### 1.1 Why the publication time is 20:00, and what that says about the rule

The quote of period `k` is the latest one on or before `g_{k−1}` (Ruling 4.3). A publication date
in `(f_k, g_{k−1}]` can be "not yet due" (Ruling 5.8 item 5) only if its publication instant is
after `t`. Every such date is at or before `g_{n−1}`, and

```
g_{n−1} ≤ E − 1 day,      E = D_c(t) ≤ UTC-date(t)      (performance Ruling 1.7).
```

So the quote dated `g_{n−1}` must be published after 00:00 UTC of a later date. For a same-day
publication in New York, that means after 19:00 EST or 20:00 EDT. The `t` must also come before any
held exchange closes on `E`. That needs a weekday on which every held exchange is closed (here
Thanksgiving), with `t` shortly after 00:00 UTC.

- For SYN4_RF_USD (18:00 New York) and SYN4_RF_HKD (17:00 Hong Kong) in parts 1 to 3, the
  not-yet-due case **cannot arise**. The same holds for the Treasury daily bill rates as described in
  risk Ruling 4.6 (MEMORY): a same-day publication before 19:00 New York.
- For those series, Ruling 5.8 items 4 and 5 are never decisive for the risk-free leg. Only item 7, a
  file published but not yet retrieved, can change a result.
- **This is not a contradiction in the text.** The rule is correct, and it is simply vacuous for
  same-day publications. I report it so that nobody reads a passing item 4/5 test on real calendars
  as coverage.
- Part 4 uses a declared, synthetic 20:00 publication so that the case can be tested at all.

### 1.2 `D_c(t)`

All three instants fall on 2025-11-27 UTC: 00:30, 01:10 and 01:30, which are 19:30, 20:10 and 20:30
in New York on Wednesday 11-26. P41 holds only SYN51 and only USD.

- SYN5_NYSE has no session on 11-27, so the close condition is vacuous for that date.
- No currency other than `R` is held, so the ECB condition is vacuous too.
- So **`D_c(t)` = 2025-11-27** at all three instants (`as_of_resolved`).
- SYN51's value at 11-27 is the 11-26 close, with 0 sessions missed (11-27 is not a session). Its
  file was retrieved at 11-26 22:00, which is before `t`.

### 1.3 The quote of the last two DAILY periods (CUSTOM base 2025-11-25)

The grid is 11-25, 11-26, 11-27 (weekdays, Ruling 2.2): two periods, stubs 0. Period
`(11-25, 11-26]` takes the 11-25 quote at every instant (published 11-26 01:00, in RF-1), so
`m = 0` and `rf = 1/10000 × 1 day`.

The period `(11-26, 11-27]` needs the latest quote on or before 11-26:

| Assertion | `t` (UTC) | 11-26 quote published (01:00)? | In `M_t` (RF-2 at 01:15)? | `f` | `m` | `rf` | Rates state |
|---|---|---|---|---|---|---|---|
| R41-C3 | 00:30 | no: **not yet due** | no | 11-25 | **0** (not counted, item 5) | 1/10000 | `AVAILABLE` |
| R41-C2 | 01:10 | yes | **no**: due but late | 11-25 | **1** (missed, item 7) | 1/10000 | `AVAILABLE`, `STALE_DATA`, `RISK_FREE_STALE` |
| R41-C1 | 01:30 | yes | yes | **11-26** | 0 | 7.30 %/365 × 1 = **1/5000** | `AVAILABLE` |

A missed count of 1 is `AVAILABLE` + `STALE_DATA` (Ruling 4.4's table). R41-C1 is the historical
value at 2025-11-27.

### 1.4 The Sharpe ratio, DAILY, `TRAILING_MONTHS 12`

**Window.** `B` = 2024-11-27, a Wednesday on the DAILY grid, so `g_0 = B` and `g_n = E` =
2025-11-27, with both stubs 0.

- The periods are the weekdays of (2024-11-28 .. 2025-11-27).
- Thursday 2024-11-28 to Wednesday 2025-11-26 is 364 days, exactly 52 weeks, so 260 weekdays. Thursday
  2025-11-27 makes **n = 261**.
- `N1 = 259 ≤ 261 < N3 = 781`, so the state is `LIMITED` with `OBSERVATIONS_BELOW_STANDARD`.

**Returns.**

- `r_k` is 0 except on the 52 Mondays 2024-12-02 .. 2025-11-24, where the close changes.
- Monday 2024-12-02 is `j` = 152 (even, 100.00). Friday 11-29 was in `j` = 151 (104.00), so
  `r = 100/104 − 1 = −1/26`.
- The Mondays then alternate, giving 26 of `−1/26` and 26 of `+1/25`.
- The holiday period `(11-26, 11-27]` has `r` = 0.

```
Σ r   = 26 (1/25 − 1/26) = 26/650 = 1/25
Σ r²  = 26 (1/625 + 1/676) = 26 × 1301/422500 = 1301/16250
s²(r) = (Σ r² − (Σ r)²/n) / (n − 1) = (1301/16250 − 1/163125) / 260 = 67907/220545000
```

**Risk-free.** `rf_k = ρ_k × (g_k − g_{k−1})`.

- The calendar days of the 261 periods sum to 2025-11-27 − 2024-11-27 = **365**. A Friday-to-Monday
  period counts 3 days.
- Every period except the last uses a 3.65 % quote dated its own start, with `m = 0`. Every `g_{k−1}`
  is a publication weekday, and all those quotes are published and retrieved by 11-26 02:00.
- So `Σ rf = 365/10000` with the last period at 1/10000 (C2, C3). With the last period at 2/10000
  (C1) it is `366/10000`.

**Mean excess**, `d̄ = (Σ r − Σ rf)/n`:

- C2, C3: `(400 − 365)/10000/261 = 35/2,610,000 = 7/522000`;
- C1: `(400 − 366)/10000/261 = 34/2,610,000 = 17/1305000`.

**Sharpe** `= sign(d̄) √(A d̄² / s²(r))`, with `A = 260` (Ruling 6.5):

| Assertion | `exact_square` | value (ROUND_HALF_UP, 12 dp) |
|---|---|---|
| R41-C3, R41-C2 | 260 (7/522000)² / (67907/220545000) = **15379/101278440** | **0.012322690673** |
| R41-C1 | 260 (17/1305000)² / (67907/220545000) = **634933/4430931750** | **0.011970613796** |

**At the publication boundary, the ratio moves by exactly 34/35.** Between 00:30 and 01:30 UTC, only
the last period's quote changes.

**States.**

- All three Sharpe items are `LIMITED` (the count), reason **none**.
- R41-C2 also carries `RISK_FREE_STALE`. That cause is `AVAILABLE`-level, so it does not supply the
  reason (Ruling 7.3 (1.3) item 4).
- So R41-C2 and R41-C3 have the same value and differ only in lineage. A late file is disclosed; a
  not-yet-due quote is not a fault.

## 2. The default view of a benchmark-relative statistic (R41-V1, R42-V0)

### 2.1 R41-V1 (P41, historical, as of Friday 2025-11-28): history refusal, so a fallback

**`X` = beta, WEEKLY, `TRAILING_MONTHS 36`.**

- `B` = 2022-11-28 < `I_0` = 2024-10-31, so the window is refused: `INSUFFICIENT_DATA`, reason none,
  `WINDOW_BEFORE_INCEPTION`, `effective_window` null.
- The selected series is admitted and total-return, so there is no window-independent cause
  (Ruling 7.3 (1.5)). The comparability is null.

`X` carries a portfolio-history detail, so the view **falls back** (Ruling 7.7 item 2 and (1.6)).

**`Y` = beta, WEEKLY, `MAX_AVAILABLE`.**

- `B = I_0` = 2024-10-31. The grid is the Fridays 2024-11-01 .. 2025-11-28: 57 points,
  **n = 56**, stubs 1 and 0.
- No period is `INSUFFICIENT_DATA`, so `max_available_start = INCEPTION` (Ruling 2.3).
- `51 ≤ 56 < 155`, so the state is `LIMITED`, `OBSERVATIONS_BELOW_STANDARD`.

**The returns.** Friday 2024-11-01 is in week `j` = 147: SYN51 at 104 and the index at
`BM[147 mod 4 = 3]` = 1020. The 56 periods are 14 whole repetitions of:

| Period ends in week | SYN51 | `r_k` | Index | `b_k` |
|---|---|---|---|---|
| `j ≡ 0 (mod 4)` | 104 → 100 | −1/26 | 1020 → 1000 | −1/51 |
| `j ≡ 1` | 100 → 104 | +1/25 | 1000 → 1010 | +1/100 |
| `j ≡ 2` | 104 → 100 | −1/26 | 1010 → 1000 | −1/101 |
| `j ≡ 3` | 100 → 104 | +1/25 | 1000 → 1020 | +1/50 |

**Per cycle:**

- `Σ r = 1/325`, so `r̄ = 1/1300`;
- `Σ b = 253/515100`, so `b̄ = 253/2060400`;
- `Σ rb = 390889/167407500`, `Σ b² = 52136801/53065602000`, `Σ r² = 1301/211250`.

**Over 14 cycles** (`S_xy = 14 (Σ_cycle xy − 4 x̄ ȳ)`):

```
S_rb = 214571/6565000      S_bb = 2432901359/176885340000      S_rr = 18207/211250
β    = S_rb / S_bb = 10736765004/4518245381 = 2.376312948639 (ROUND_HALF_UP)
v_β  = (S_rr − β S_rb) / ((n − 2) S_bb) = 702493264139944336/61243623968783505483
```

The two legs share one calendar (SYN5_NYSE) and every Friday is a session, so the comparability is
`FULL` with no lagged point (0 of 57).

**The view:** `fallback: true`. It records `refused` = `X`'s summary and `shown` = `Y`'s summary,
with its true request, window, count, state and lineage field. Items 2 and 3 are `X` and `Y` as
ordinary results.

### 2.2 R42-V0 (P42, historical, as of 2025-11-28): benchmark-side refusal, so no fallback

**`X` = beta, WEEKLY, `TRAILING_MONTHS 36`.**

- `B` = 2022-11-28 ≥ `I_0` = 2022-01-06. The window holds: `g_0` = Friday 2022-12-02,
  `g_n` = 2025-11-28, **n = 156** (1092 days = 156 weeks), stubs 4 and 0. The count is `AVAILABLE`
  (`n ≥ 155`).
- SYN5_BM_YOUNG_TR has no level on or before `g_0`: its first calculation day is 2024-06-03. Under
  Ruling 5.2 that gives `INSUFFICIENT_DATA`, `MISSING_BENCHMARK`, `BENCHMARK_NOT_COVERING_WINDOW`.
  Reason `MISSING_BENCHMARK`, value null, comparability null.

**The view.** No cause of `X` comes from the portfolio's history. A benchmark that does not cover the
window is a benchmark-side cause, which is never a trigger (Ruling 7.7 (1.6), "any benchmark-side
cause (… coverage …)"). So `fallback: false`, `refused` null, and `shown` = `X`.

- `MAX_AVAILABLE` would start at `I_0` = 2022-01-06, still before the index's launch, and be refused
  for the same cause (item 5).
- This is the benchmark-side case most easily mistaken for youth. Part 3's R6-V0, the control, is
  the "no selection" case.

## 3. Mutations

Every mutation changes exactly the items that name it (`--mutations`). For part 4, a change in an
item's own detail set counts as a change. That is because the fixture asserts `details_include`, and
M-D2 and M-D3 change a Sharpe item's lineage only.

| Id | Departure | Items changed | Why |
|---|---|---|---|
| M-D1 | the risk-free quote read by date, ignoring `t` and `M_t` | 4 (R41-C3, R41-C2) | both take the 11-26 quote (1/5000; the Sharpe ratio becomes C1's), and R41-C2 loses `RISK_FREE_STALE` |
| M-D2 | due but not in `M_t` not counted as missed | 2 (R41-C2) | `m` 1 → 0, `RISK_FREE_STALE` gone |
| M-D3 | not yet due counted as missed | 2 (R41-C3) | `m` 0 → 1, `STALE_DATA` / `RISK_FREE_STALE` appear |
| M-D4 | publication test without `M_t` | 2 (R41-C2) | the late 11-26 quote is read (1/5000) |
| M-D5 | the quote at the period's end `g_k` | 3 (R41-C1 both, R41-C2 rates) | C1: `(11-25, 11-26]` takes 11-26's 2/10000, so the Sharpe ratio uses 33/2,610,000 (0.011618536920). C2: the 11-26 quote is due, not retrieved, so it is missed for `(11-25, 11-26]` too |
| M-D6 | fall back on any `INSUFFICIENT_DATA` | 1 (R42-V0 view) | a benchmark refusal falls back, to a `MAX_AVAILABLE` refused for the same cause |
| M-D7 | no fallback for benchmark-relative statistics | 1 (R41-V1 view) | the view shows the 3Y refusal |
| M-D8 | a pre-inception base answered from inception under the 3Y label | 2 (R41-V1 view, `X`) | `X` becomes Y's number labelled 3Y (relabelling, Ruling 7.2), and the view then does not fall back |
| M-D9 | `max_available_start` omitted for benchmark-relative statistics | 2 (R41-V1 view, `Y`) | the R10-S1 defect class of part 3 (1.9) |
| M-D10 | the young benchmark back-filled with its first level | 2 (R42-V0 view, `X`) | 3Y beta 2.368153915100, `AVAILABLE`: a number from an index that did not exist |

R41-C1 is the control for the instant rule: M-D1 to M-D4 leave it unchanged.

## 4. Run record

Run on 2026-10-03 with the system `python3` (3.9.6), read-only, in
`methodology/fixtures/cp4_golden/derivation`:

```
$ python3 cp4_part4_closed_forms.py ../cp4_golden_part4.json
... 19 lines "ok" ...
CLOSED FORMS AGREE
$ python3 cp4_part4_calculator.py ../cp4_golden_part4.json --check --mutations --retrieval
ok  M-D1 ... ok  M-D10 (each: changes = fixture names)
MUTATIONS AGREE
smallest distance of a square-root value from a rounding boundary: 0.017482802909 quanta ( OK ; need > 1e-18 )
CHECK PASSED - 0 difference(s)
RETRIEVAL CONSISTENT - 4558 rows, 3 Current-mode instant(s), 1 late row(s) as declared, 0 problem(s)
```

## 5. Notes for the engineer

1. **New input format:** `market_data.retrieval.files`, one entry per file, with series, calendar,
   coverage and retrieval time, plus `late_rows`. Part 3's vintage-by-calendar form is not used here.
   Each file's coverage is its `market-data` Ruling 0.1 segment, as before.
2. **The risk-free leg in Current mode needs both tests** (publication ≤ `t` and file in `M_t`) for
   its use. Its missed count uses the publication test alone. The count includes a quote that is due
   but late (R41-C2), and excludes one not yet due (R41-C3).
3. Part 3's Current-mode items contain no risk-free metric. Part 4 is the first fixture that pins
   Ruling 5.8 item 4 for the rate.
