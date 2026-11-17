# `cp4_golden/1.9-part3`: hand derivation

**1.9-part3 (re-issue, `risk/1.9`, `market-data/1.14`).**

- **R4-S4** (SYN4_BM_US_TR5, as of 2025-08-08, base 07-04).
  - Source a (`d` = 2 = `D`, bound 0) says 990.30 on 08-08. Source b (`d` = 1, bound 0.05) says 990.
  - `|0.30| > 0.05`, so a `DISAGREEMENT`, and `g_n` = 08-08 is `SOURCE_CONFLICT`.
  - M-C45 infers b's precision from its texts as 0 decimals (bound 0.5): it agrees, uses 990.30, and
    gives the active return −103/10100.
- **R4-S6** (SYN4_BM_US_TR4, as of 2026-01-02). Two sources, nothing declared, so
  `BENCHMARK_SERIES_UNAVAILABLE`. M-C44 reconciles it anyway and gives −25/2678.
- **R5-E10** (SYN35, as of 2026-02-06, base 2026-01-14: `g_0` = 01-16, phase 2 at 50.50 → `g_n` =
  02-06, phase 1 at 51.00).
  - The CNY 3.25 dividend ex Monday 02-02 has equal declared fields on both sides. Only the feed
    states the issuer's USD 0.44, which is used as stated (`market-data` Ruling 4.5 (1.14)).
  - The ECB conversion would give `3.25 × 1.08/7.80 = 0.45` (M-C41).
  - Benchmark `(51/50.50) × (50.44/50) − 1` = **1186/63125** (the price on Monday 02-02 is Friday
    01-30's phase-0 level, 50).
  - Portfolio `104/101 − 1 = 3/101`.
  - Active **689/63125**.
  - M-C43 (one-sided paid fields are a disagreement) refuses it.
- **R5-E11** (review finding CP4F-15: the FILING alone states the payment; SYN35, as of 2026-03-06,
  base 2026-02-25: `g_0` = Friday 02-27, phase 0 at 50.00 → `g_n` = 03-06, phase 1 at 51.00).
  - The CNY 3.25 dividend ex Monday 03-02 has equal declared fields on both sides. Only the
    FILING states the issuer's USD 0.43. A one-sided paid amount is used as stated, whichever side
    states it (`market-data` Ruling 4.5 (1.14)); the price on 03-02 is 02-27's level, 50.
  - Benchmark `(51/50) × (50.43/50) − 1 = 2571.93/2500 − 1 = 71.93/2500` = **7193/250000**
    (0.028772).
  - M-C46 (only the first statement's paid fields, the FEED's, are kept) drops the 0.43 and converts
    at the ex-date fixing, `3.25 × 1.08/7.80 = 0.45`: `(51/50)(50.45/50) − 1 = 1459/50000`.
  - R5-E10 alone could not separate this, because there the FEED is the side that states it and is
    listed first.
- **R5-E12** (CP4F-15: the two sides state different payments; SYN35, as of 2026-03-20, base
  2026-03-11: `g_0` = 03-13, phase 2 at 50.50 → `g_n` = 03-20, phase 3 at 49.50).
  - The CNY 3.25 dividend ex Monday 03-16: the declared fields are equal, the FEED states USD 0.46,
    the FILING USD 0.47. Both sides state paid fields, so they are compared; they differ, so the
    dividend is a `DISAGREEMENT` and the ratio spanning 03-16 is broken (risk Ruling 5.5 (1.7)).
  - The window's only ratio spans 03-16: **`INSUFFICIENT_DATA`, `SOURCE_CONFLICT`,
    `BENCHMARK_SOURCE_CONFLICT`**.
  - M-C46 uses the FEED's 0.46 silently: `(49.50/50.50)(50.96/50.50) − 1 = 2522.52/2550.25 − 1` =
    −2773/255025. M-C7 (the feed amount on a disagreement) also computes a value.
- **Bites added to earlier items.** Under M-C21 (a disputed dividend suppresses the whole proxy)
  the 03-16 disagreement suppresses SYN4_BM_ETF_PROXY_FX on every date, so R5-E9 (3 items) and
  R5-E10 (2 items) now name M-C21. Their values are unchanged.
- **R10-S1's `MAX_AVAILABLE` beta: lineage restored.** Risk Ruling 2.3 requires `max_available_start`
  on every `MAX_AVAILABLE` result. The part-2 calculator's benchmark-relative path (which part 3 reuses)
  dropped it, so 1.0-part3 to 1.8-part3 recorded the beta's window without it. The window starts at
  inception (no insufficient period: the same 57 observations as R10-S1's volatility), so the field is
  `INCEPTION`. The value, state and window are unchanged. This was my tool's defect, not a method
  change.

**1.8-part3 (the previous re-issue).**

**1.8-part3 (re-issue, `risk/1.8`; review finding CP4F-12).** SYN35 (USD, SYN31's cycle) declares
three dividends in CNY, each corroborated:

| # | Declared | Ex-date | Fixing used | Missed | In USD |
|---|---|---|---|---|---|
| a | CNY 3.60 | Mon 2025-03-03 | 03-03 (parity of 02-28, even: 7.80) | 0 | `3.60 × 1.08/7.80 = 162/325` |
| b | CNY 2.00 | Fri 2025-03-14 (the fixture's CNY gap is 03-13 and 03-14) | 03-12 (parity of 03-07, odd: 7.839) | 2 | `2.00 × 1.08/7.839 = 240/871`, `LIMITED` + `STALE_DATA` |
| c | CNY 3.30 | Tue 2025-09-02 | none: the issuer's stated payment is USD 0.46 | — | `0.46` |

**R5-E9** (selection seq 5, as of 2026-01-02). The window facts run from 01-10 (phase 1, 51) to 01-02
(phase 0, 50):

- **Factors:**
  - price `50/51`;
  - dividend a at 03-03: `(50 + 162/325)/50` (price 50, the phase-0 level of 02-28);
  - dividend b at 03-14: `(50.50 + 240/871)/50.50` (phase 2, the previous print 03-13 at 03-07's
    phase-1 51, so the ratio across 03-14 is `(50.50 + d)/51`);
  - dividend c at 09-02: `(50.50 + 0.46)/50.50`.
- **Benchmark return:** **77252531/16659508125** (calculator and hand product agree), `LIMITED` +
  `STALE_DATA` because the window spans 03-14.
- **Active return:** `−1/26 − 77252531/16659508125` = **−1436005687/33319016250**.
- **1Y beta:** `18082320782957133953359699858125/9655121498595324349788768923492`, `LIMITED` +
  `STALE_DATA`. The count is `LIMITED`, and the 03-14 period's conversion is a `LIMITED`-level
  cause with a code.
- **Mutations:**
  - M-C38 (unconverted) gives benchmark 142203/867085;
  - M-C39 (pay-date fixing) moves dividend a to the 7.839 rate and makes b fresh;
  - M-C40 drops the `STALE_DATA`;
  - M-C41 converts c at the ECB rate instead of the issuer's 0.46;
  - M-C42 (the interim refusal) withholds the proxy from 03-03.

**1.7-part3 (the previous re-issue).**

**1.7-part3 (re-issue, `risk/1.7`; tech plan §17.23 decisions 1 and 3).** SYN34 follows SYN31's
cycle. Its dividends are stated by one side each:

| Side | Amount | Ex-date | Pay date |
|---|---|---|---|
| feed | 0.50 | 2025-03-03 | 03-10 |
| filing | 0.50 | 2025-03-05 | 03-12 |
| feed | 0.40 | 2025-09-02 | 09-09 |
| filing | 0.40 | 2025-12-01 | 12-08 |

- **Matching (Ruling 5.5 (1.7)):**
  - no two statements are equal;
  - none share a date;
  - 03-03 and 03-05 are 2 sessions apart, so they are **one disputed dividend**, and the chain breaks
    at both;
  - 09-02 and 12-01 are about 64 sessions apart, so they are **two single-source dividends**, both
    applied.
- **R5-E7** (selection seq 4; 01-10 → 01-02): the window spans the break, so `INSUFFICIENT_DATA` +
  `SOURCE_CONFLICT`. Under M-C36 both 0.50s are applied, a double count, and the active return would
  be −17927683/328185000.
- **R5-E8** (base 2025-06-04, `g_0` = 06-06, phase 2, 50.50 → `g_n` = 01-02, phase 0, 50.00):
  - **Benchmark:** `(50/50.50) × (50.90/50.50) × (49.90/49.50) − 1` = **6065/1009899**.
    - The 0.40 ex Tuesday 09-02 is reinvested at Friday 08-29's level, 50.50.
    - The 0.40 ex Monday 12-01 is reinvested at Friday 11-28's level, 49.50.
  - **Portfolio:** `100/101 − 1 = −1/101`.
  - **Active:** **−16064/1009899**.
  - M-C37 (every unpaired pair disputed) refuses it, and M-C6 (corroborated only) drops both
    dividends, giving −1/101.

**1.6-part3 (the previous re-issue).**

**1.6-part3 (re-issue, `risk/1.6`; review findings CP4F-5 and CP4F-10).** Seven items and four
mutations are added. No earlier item changes.

**SYN33** follows SYN31's cycle (50, 51, 50.50, 49.50) and has no dividends. A second source
disagrees on Wednesday 2025-08-06 (50.60 against 50.50) and on Friday 2026-01-09 (51.10 against
51.00).

- **R5-E5** (selection seq 3: the SYN33 proxy, as of 2026-01-02).
  - The 08-06 print is withheld, and the chain links 08-05 → 08-07: `50.50/50.50`, the same ratio as
    with the print.
  - No grid date uses 08-06, so the proxy equals SYN33's price index everywhere it is read.
  - 1Y beta = **`16450205576673/8678726007224`** (SYN21 against a 4-cycle 50 / 51 / 50.5 / 49.5 index).
  - Window facts (01-10 → 01-02): benchmark `50/51 − 1 = −1/51`; active `−1/26 + 1/51` =
    **−25/1326**.
  - The engineer's present proxy (M-C33: every later print withheld) refuses both.
- **R5-E6** (as of 2026-01-09). `g_n` = 01-09 is the disputed print, so the window facts are
  `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`. M-C34 (treat it as missing) would use 01-08's level, one
  print stale, and give the active return 4/101.
- **R5-E4** (selection seq 2: the SYN32 proxy with its disputed 2025-06-02 dividend; as of
  2026-01-02, base 2025-06-04).
  - `g_0` = 06-06 is after the ex-date, so no ratio spans the break: `AVAILABLE`.
  - Benchmark `50/50.50 − 1 = −1/101` (no dividend after the break).
  - Portfolio `100/101 − 1 = −1/101`.
  - Active **0**.
  - M-C32 (1.2's "from the ex-date on") refuses it. R5-E2, whose windows span 06-02, stays refused
    under both rules.
- **R11-V1** (Ruling 7.7 (1.6)). The default view of the active return:
  - The 3Y request's leg `TWR(2023-01-06, 2026-01-02]` is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`
    (the uncovered split of 2025-09-08). That is a history refusal, so `fallback: true`.
  - `MAX_AVAILABLE` (base `I₀` = 2022-12-29) has its last insufficient period ending at `g_n`, so
    `NO_FULL_PERIOD` is shown.
  - M-C35 (the present service: no fallback) shows the 3Y refusal instead.

**1.5-part3 (re-issue, `risk/1.5`).** Five items and two mutations are added. No earlier item
changes.

- **R9-Z3** (Ruling 6.9 (1.5)):
  - **The 1Y active return** (`g_0` = 2025-01-03). The weeks ending 03-14, 03-21 and 03-28 held no
    capital (§10), so the result is `INSUFFICIENT_DATA`, no reason, detail `ZERO_CAPITAL_PERIOD`.
    The engine's present answer is the TWR with factor 1 over the gap: cash at 0 % to 03-05, then
    factor 1, then 100 → 100. That is 0, and the active return would be 0 − 0 = 0 (M-C30).
  - **The 1Y benchmark return** is unaffected: 1000 at 01-03 (phase 0) and 1000 at 01-02 (phase 0),
    so **0**.
  - **The active return from base 2025-04-01** (`g_0` = 04-04, `n` = 39, after the gap):
    - portfolio `10000/10400 − 1 = −1/26`;
    - benchmark `1000/1030 − 1 = −3/103`;
    - active **−25/2678**, with the decomposition view as R4-S1's.
- **R6-W0** (Ruling 7.3 (1.5)): version 0 (no selection) and 60 months on a portfolio with `I₀` =
  2022-12-29. The window is refused (`WINDOW_BEFORE_INCEPTION`, no code). No selection is a
  window-independent cause with a code, so beta and benchmark return are `INSUFFICIENT_DATA` +
  `MISSING_BENCHMARK`, details `NO_BENCHMARK_SELECTED` and `WINDOW_BEFORE_INCEPTION`. M-C31 drops
  the selection cause and gives reason none.

**1.4-part3 (re-issue, `market-data/1.13`, review finding CP4M-10).** Adds release cases RB-6 to
RB-9 and mutations M-R5 to M-R7 (§1b). No item changes.

**1.3-part3 (re-issue, `market-data/1.12`).**

- The three vintages are declared as coverage **segments** of one series (§1a), under the new
  `market-data` Ruling 0.1 (1.12).
- Release-build cases RB-1 to RB-5 are added (§1b). The calculator's `--release` checks them.
- No item changes.

**Author:** `quant-analyst`, 2026-10-02. **Convention set:** `risk/1.4`
(`methodology/CP4_RISK_CONVENTIONS.md`), on `performance/1.12` and `market-data/1.11`.
**Fixture:** `cp4_golden_part3.json`: 13 portfolios, 32 assertions, 83 expected items.

**1.2-part3 (re-issue).** Adds portfolio R13, a selection log with reversals and corrections (§12a;
risk Ruling 5.6 (1.4); review finding CP4M-4), and mutations M-C25 to M-C29. No 1.1-part3 item
changes.

**1.1-part3 (re-issue).**

- **The retrieval declaration is corrected (§1a).** 1.0's single retrieval time of 2022-11-30 came
  before every row, so `market-data` Ruling 3.1 would have contradicted every series. That was my
  error.
- **R2-L2 is added (§3a)**, together with mutation M-C24.
- **No 1.0 expected value changes.**

**Two derivations, sharing no code with each other or with `src/`:**

- `derivation/cp4_part3_calculator.py` replays each ledger and the market data day by day. It reuses
  the part-2 calculator, which reuses the part-1 calculator.
  - `--check` re-derives all 83 items.
  - `--mutations` runs the 29 mutations of §17.
  - `--closed` runs four metamorphic checks.
  - `--retrieval` (1.1) checks the declared file vintages.
- `derivation/cp4_part3_closed_forms.py` writes each portfolio's periodic returns directly from the
  four-week cycles, with the one perturbation each portfolio has, and applies the formulas of
  Rulings 3.2 and 6.7–6.11. It re-derives 25 of the long-series values (§13).

The window facts are ratios of two levels and are shown in full below. **No value comes from the
engine.**

```
cd methodology/fixtures/cp4_golden/derivation
python3 cp4_part3_calculator.py ../cp4_golden_part3.json --check --closed --mutations --retrieval
python3 cp4_part3_closed_forms.py ../cp4_golden_part3.json
```

The run record is §18.

---

## 1. Inputs

**Cycle index.** As in part 2: Friday `F` has index `j = (F − 2023-01-06)/7`, phase `j mod 4` and
parity `j mod 2`. Monday to Thursday carry the previous Friday's level. Before 2023-01-06, every
series is at its phase-0 level.

| Series | Phase 0 | 1 | 2 | 3 | Weekly returns of the periods starting at phase 0, 1, 2, 3 |
|---|---|---|---|---|---|
| SYN21 (and SYN43 before its split), USD | 100 | 104 | 101 | 98 | 1/25, −3/104, −3/101, 1/49 |
| SYN42, USD | 100 | 103 | 99 | 101 | 3/100, −4/103, 2/99, −1/101 |
| SYN31, SYN32 (ETFs), USD | 50 | 51 | 50.50 | 49.50 | 1/50, −1/102, −2/101, 1/99 |
| SYN22, HKD | 100 | 105 | 100 | 95 | 1/20, −1/21, −1/20, 1/19 |
| SYN4_BM_US_TR, both sources of SYN4_BM_US_TR2, USD | 1000 | 1030 | 1010 | 990 | 3/100, −2/103, −2/101, 1/99 |
| SYN4_BM_CN_TR, CNY | 5000 | 5100 | 5050 | 4950 | local: 1/50, −1/102, −2/101, 1/99 |
| SYN4_BM_FLAT, USD | 1000 | 1000 | 1000 | 1000 | 0 |
| SYN43 from its 2:1 split (ex 2025-09-08) | 50 | 52 | 50.50 | 49 | (half of SYN21's levels) |

**Dates used below:**

| Date | j | Phase | Parity |
|---|---|---|---|
| 2024-11-29 | 99 | 3 | odd |
| 2025-01-03 | 104 | 0 | even |
| 2025-01-10 | 105 | 1 | odd |
| 2025-01-17 | 106 | 2 | even |
| 2025-03-07 / 03-14 | 113 / 114 | 1 / 2 | odd / even |
| 2025-03-28 / 04-04 | 116 / 117 | 0 / 1 | even / odd |
| 2025-05-30 / 06-06 / 06-13 | 125 / 126 / 127 | 1 / 2 / 3 | odd / even / odd |
| 2025-08-08 / 08-15 | 135 / 136 | 3 / 0 | odd / even |
| 2025-08-29 / 09-05 / 09-12 | 138 / 139 / 140 | 2 / 3 / 0 | even / odd / even |
| 2026-01-02 / 01-09 | 156 / 157 | 0 / 1 | even / odd |

**FX** (ECB layout, units per EUR): USD 1.0800; HKD 8.4000 (even) or 8.4420 (odd); CNY 7.8000 (even)
or 7.8390 (odd). So `X(CNY→USD) = 1.08/7.80` or `1.08/7.839`, and `X(USD→HKD) = 8.40/1.08` or
`8.442/1.08`. CNY has no quote on 2025-03-13 and 2025-03-14.

**Instants (UTC, January, no daylight saving):** NYSE close 21:00; HKEX close 08:10; SSE close 07:00;
ECB fixing 13:10, published 15:00.

**Windows.** 1Y weekly to Friday 2026-01-02: `B` = 2025-01-02, `g_0` = 2025-01-03 (phase 0),
`n` = 52 = 13 cycles. 3Y: `g_0` = 2023-01-06, `n` = 156 = 39 cycles. The window facts use base
Wednesday 2025-01-08 (`g_0` = 01-10, phase 1) or Wednesday 2025-01-15 (`g_0` = 01-17, phase 2).

---

### 1a (1.1). Retrieval: the file vintages

**Two rules constrain the retrieval times.**

- **`market-data` Ruling 3.1 (the after-retrieval test).** A file may hold only rows that exist by
  its retrieval time. For a price or level row, that means its session has closed; for an FX or
  risk-free row, that the rate has been published.
- **`performance` Ruling 1.7.** A Current-mode result at `t` reads only `M_t`, the files retrieved
  at or before `t`.

**Why 1.0's declaration fails.** It put every file at 2022-11-30, which breaks the first rule for
every series. Retrieving every file once, after its last session, keeps the first rule but breaks
R7: no file is in `M_t` on 2026-01-09.

**1.1 declares three vintages per series:**

| Vintage | Rows | Retrieved at |
|---|---|---|
| V1 | to 2026-01-08 | 2026-01-09 00:00 UTC. The latest row instant is the US 13-week bill's publication of 01-08, 23:00 UTC. |
| V2 | 2026-01-09 | Each calendar's own instant on 01-09 (UTC): SSE close 07:00, HKEX close 08:10, HKD rate publication 09:00, ECB publication 15:00, NYSE close 21:00, USD rate publication 23:00. |
| V3 | from 2026-01-10 | 2026-04-01 00:00 UTC, after the last row (USD rate publication on 03-31 at 22:00 UTC, EDT). |

The corporate-action records are retrieved at 2026-01-09 00:00 UTC.

**What this gives at the two Current-mode instants:**

- **R7-C1** (`t` = 2026-01-09 09:00 UTC): `M_t` = V1 plus the SSE, HKEX and HKD-rate files of 01-09,
  which are exactly the rows due at `t`.
- **R7-C2** (`t` = 07:00 UTC): `M_t` = V1 plus the SSE file of 01-09, which is due at 07:00.
- In both, the instant rule of Ruling 5.8 and the `M_t` restriction select the same rows. So no 1.0
  value changes.

**`--retrieval` checks this.** It verifies, over all 5,214 calendar rows, that each row's file is
retrieved at or after its availability instant, and that at each `t` a row is in `M_t` exactly when
it is due. It reports 5,906 problems for 1.0's declaration and 9,736 for a single file retrieved
after the last session.

### 1b (1.3). The vintages are segments of one series; five release-build cases

Under `market-data` Ruling 0.1 (1.12), the coverage intervals of a series' files must be pairwise
disjoint. The V1/V2/V3 coverages are:

- V1: [the series' first date, 2026-01-08];
- V2: [2026-01-09, 2026-01-09];
- V3: [2026-01-10, the series' last date].

They are disjoint, so the three files are one series in `M`. The vintage is each file's retrieval
time. The anchor stays null.

The cases, all on SYN42 (RAW, synthetic; **no print on 2025-06-13**):

| Case | Files (coverage) | Outcome | Why |
|---|---|---|---|
| RB-1 | V1, V2, V3 | ADMITTED, 3 segments | disjoint coverage, one identity, RAW |
| RB-2 | + V1b [2025-06-13] holding 101.00 | REFUSED_OVERLAP 2025-06-13 | V1 covers 06-13 and holds no row there ("no print"); V1b says there was one. The points are disjoint, the dates are not. |
| RB-3 | + V3r, a re-download of V3's dates with equal rows | REFUSED_OVERLAP 2026-01-10..2026-03-31 | two vintages of the same dates; agreement is no licence |
| RB-4 | DIVIDEND_ADJUSTED / LATEST in two segments | REFUSED_NOT_SEGMENTABLE | each retrieval re-bases the history |
| RB-5 | V2 declared real among synthetic segments | REFUSED_IDENTITY | Ruling 4.8 |

The engineer's current rule (disjoint points, equal fields, the vintage label in
`adjustment_anchor`) is the points-only reading:

- **On RB-2 it gives ADMITTED.** That is mutation M-R1. Admitting it would also silently remove R2's
  2025-06-13 staleness and its LAGGED point.
- On RB-3, M-R1 still refuses, but it names the overlap by points (01-12..03-31), not by the
  coverage that actually overlaps.

The other mutations:

- M-R2 (segment an adjusted series) changes RB-4.
- M-R3 (admit an overlap whose rows agree) changes RB-3.
- M-R4 (1.11's "one file per series") changes every case.

**(1.4) The coverage refusals of Ruling 0.1 (1.13):**

| Case | Files | Outcome | Hull (M-R5) | Ignore (M-R6) |
|---|---|---|---|---|
| RB-6 | V2 declares [01-09] but also holds 101.00 on 2025-06-13 | REFUSED_ROW_OUTSIDE_COVERAGE | REFUSED_OVERLAP over a fabricated span, 2025-06-13..2026-01-08 | ADMITTED: RB-2 is back, with two readings of 06-13 |
| RB-7 | V3 declares from 01-10 but holds the 01-09 row (103.00, equal to V2's) | REFUSED_ROW_OUTSIDE_COVERAGE | REFUSED_OVERLAP 01-09 | ADMITTED, with two readings of 01-09 |
| RB-9 | V1 and V3 only (01-09 lies in a hole); V3 holds a 01-09 row | REFUSED_ROW_OUTSIDE_COVERAGE | **ADMITTED**: the stray row values 01-09 | ADMITTED |
| RB-8 | V2 states no coverage | REFUSED_COVERAGE_UNDETERMINED | — | — |

For RB-8, mutation M-R7 (infer the coverage from the rows) gives ADMITTED.

RB-9 is why the hull is wrong. It admits a row the file was not asked for whenever that row falls in
a hole.

## 2. R1: a flat benchmark (`S_bb = 0`)

`b_k = 0` for every period, so `S_bb = 0` and `S_rb = 0`:

- **beta, R², alpha:** `INSUFFICIENT_DATA`, no reason, detail `ZERO_BENCHMARK_VARIANCE`
  (Ruling 6.12), with `OBSERVATIONS_BELOW_STANDARD` (n = 52 is between N1 and N3). No number: 0/0 is
  not a slope, and showing 0 (mutation M-C14) would assert "the portfolio did not move with the
  market" when there was no market movement to measure against.
- **TE:** `a_k = r_k`, so TE is the portfolio's volatility. One SYN21 cycle has mean
  `r̄ = 23921/51469600` and `S_rr = 2470301597923/662279931040000`. Over 13 cycles the mean is the
  same and `S_rr` is 13 times as large: `2470301597923/50944610080000`. So
  `TE² = 52 × S_rr / 51 =` **`2470301597923/49964906040000`**, and TE = **0.222352722900** (equal to
  R8-K1's A1-scope volatility and to R12-X1's volatility, both SYN21's series).
- **IR:** `ā = r̄`, so `IR² = 52 r̄² / (S_rr/51) =` **`29182926291/2470301597923`**, IR = **0.108689960134**,
  sign +.
- **Comparability `FULL`:** one calendar (NYSE) on both legs, no translation, no lag.
- The window facts are omitted: against a flat index, `benchmark_return` is 0 and `active_return`
  equals the TWR, so no mutation can be made to fail them that the TWR items of part 1 do not
  already catch.

## 3. R2: a `LAGGED` grid date inside a statistic's window

SYN42 has no print on Friday 2025-06-13 (phase 3). That date is valued at Thursday 06-12's close,
the phase-2 level 99: 1 session missed, `AVAILABLE` + `STALE_DATA` (`market-data` Ruling 5.2).

- The period ending 06-13 returns 0 (not 2/99). The next one returns `100/99 − 1 = 1/99` (not
  `−1/101`). The other 154 periods are the cycle's.
- **3Y beta** = `S_rb / S_bb = (1934548885378277/42427513224360000) / (325601574377053/4714168136040000)`
  = **`1934548885378277/2930414169393477`** = **0.660162275211**. SYN42's cycle moves partly against the
  index, so beta is well below 1.
- **TE² = 52 × S_aa / 155** = **`15075484895168/493219841233185`**, TE = 0.174829765648.
- **State:** `AVAILABLE` (n = 156 ≥ 155) + `STALE_DATA` (Ruling 2.5 item 3: a period with an
  `AVAILABLE` + `STALE_DATA` end point), detail `STALE_PERIODS`.
- **Comparability `LIMITED`:** at 06-13, `Λ_P = 1` and `Λ_B = 0`. That is one lagged point of 157 grid
  dates. Both legs are on the NYSE, so there is no seam. Mutation M-C15 (the portfolio's lag ignores
  price staleness) loses the point and makes the class `FULL`.

### 3a (1.1). R2-L2: the same perturbation over 1Y, and which cause gives the reason

The window is 1Y (`g_0` = 2025-01-03, `n` = 52). 06-13 is inside it.

- **Values.** Beta = **`220626908343053/325601574377053`** = 0.677597793454.
  `TE² = 52 × S_aa / 51` = **`538639550192/18031693120353`**.
  `vol² = 52 × S_rr / 51` = **`6889874651937689/180316931203530000`**.
  The closed forms re-derive all three.
- **Causes** (risk Ruling 7.3 (1.3)):
  - the count, n = 52 from N1 = 51 to N3 = 155: (`LIMITED`, no code, `OBSERVATIONS_BELOW_STANDARD`);
  - the period ending 06-13: (`AVAILABLE`, `STALE_DATA`, `STALE_PERIODS`).
- **State** `LIMITED`.
- **Reason: none.** No cause at the `LIMITED` level has a code. The `STALE_DATA` cause is at the
  lower `AVAILABLE` level, so it stays in the details only (`STALE_PERIODS`).
- **M-C24** (the reason chosen among all levels) gives `STALE_DATA` and fails exactly these three
  items. The volatility item is single-series, so CP4c can run it now.
- **Control:** R3-X1 has a 2-fixing-stale benchmark translation, a `LIMITED` cause with a code, so its
  reason is `STALE_DATA` under both readings.

## 4. R3: stale FX on the benchmark leg only

The portfolio is SYN21 in USD and holds no foreign currency. The benchmark is the CN index, in CNY,
translated into USD at `u(g)` (Ruling 5.3).

- At Friday 2025-03-14 (index 114, even), the latest CNY quote is Wednesday 03-12's, which is the
  rate of Friday 03-07 (odd: 7.8390). That is 2 fixings missed: `LIMITED` + `STALE_DATA`. The level
  itself is current (`m_b = 0`), so the benchmark leg's lag at 03-14 is 2 against the portfolio's 0:
  `LAGGED`, 1 point of 53.
- The translated return is `b_k = (L'/L) × (rate_before / rate_after) − 1`, since `X = 1.08/rate`.
  Because 03-14 is translated at 7.839 where the cycle has 7.800, the periods ending 03-14 and 03-21
  carry no FX change (ratio 1 instead of 7.839/7.800 and 7.800/7.839). The other 50 periods are the
  cycle's.
- **1Y beta = `16983505461893140203/10251582995405240860`** = 1.656671508147. **TE² =
  `1165887100737119128679/70589548315034816760000`**. Both are `LIMITED` (n = 52). The reason is
  `STALE_DATA`. Details: only `OBSERVATIONS_BELOW_STANDARD`, because the benchmark's staleness has its
  own detail (`BENCHMARK_STALE`, carried in `market-data` lineage) and the portfolio series has no stale
  period.
- **SEAM:** `{SYN4_NYSE}` against `{SYN4_ECB, SYN4_SSE}`. At `g_n` = 2026-01-02: NYSE 21:00, SSE 07:00,
  ECB 13:10 (UTC). The largest offset is `|21:00 − 07:00|` = **840 minutes**.
- **Window facts (01-10 → 01-02).** They read `g_0` and `g_n` only (Ruling 6.9 (1.1)), neither of
  which is stale:
  - benchmark: `(5000 / 7.800) / (5100 / 7.839) − 1 = (5000 × 7.839)/(5100 × 7.800) − 1 = 39195/39780 − 1`
    = **−1/68**;
  - portfolio TWR: `100/104 − 1 = −1/26`;
  - active: `−1/26 + 1/68 = (−68 + 26)/1768` = **−21/884** = −0.023755656109.
  - The decomposition view (largest remainder) gives −0.038461538462 = −0.014705882353 +
    (−0.023755656109). No remainder adjustment is needed here.

## 5. R4: two sources for one benchmark (Ruling 5.7 (1.2))

Source `synthetic_a` (priority 1) and `synthetic_b` (priority 2) both carry the US cycle, except:

- `synthetic_a` has no level on Friday 2025-09-12;
- `synthetic_b` publishes 991.00 on Friday 2025-08-08, where `synthetic_a` has 990.00 (phase 3).

**Per calculation day:** both sources agree → the primary's level (`CORROBORATED`); one source only →
its level (`SINGLE_SOURCE`, used, not degraded: `market-data` Ruling 4.3); they differ beyond the
precision bound → no level: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, detail
`BENCHMARK_SOURCE_CONFLICT`, until a resolution record exists. Both levels are published to two
decimals, and 1.00 apart is far outside any precision bound of two 2-decimal values. (The calculator
compares for exact equality. That is sufficient here, because the fixture has no pair that differs
within the bound.)

- **R4-S1, 1Y beta and TE:** grid date 08-08 is in the window → `INSUFFICIENT_DATA` +
  `SOURCE_CONFLICT`. No comparability object (Ruling 8.3 (1.1)).
- **R4-S1, window facts (01-10 → 01-02):** read only those two dates, where the sources agree.
  Benchmark `1000/1030 − 1` = **−3/103**; active `−1/26 + 3/103 = (−103 + 78)/2678` = **−25/2678**.
  - The decomposition view is −0.038461538462 = −0.029126213592 + (−0.009335324870). The active
    part is one quantum away from the metric's own value −0.009335324869 (largest remainder,
    `performance` Ruling 2.4 item 3). Both are asserted.
- **R4-S2 (07-04 → 08-08):** `g_n` is the disputed day → `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.
- **R4-S3 (08-15 → 09-12):** the primary lacks 09-12, and the second source's level 1000 is used,
  current. Both ends are phase 0, so the benchmark return is 0, the TWR (`100/100 − 1`) is 0, and the
  active return is 0. Under M-C3 (primary only), 09-12 carries Thursday's level 990, 1 session stale,
  and the benchmark return would be −1/100.

## 6. R5: ETF proxies (Ruling 5.5 (1.2))

`TR` of the first print = that close; then on each print `TR_t = TR_prev × (P_t + d_t)/P_prev`, with
`d_t` the cash dividend whose ex-date is `t`. Used: `CORROBORATED` and `SINGLE_SOURCE` dividends.
`DISAGREEMENT`: the proxy is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` from the ex-date on, detail
`BENCHMARK_SOURCE_CONFLICT`.

**R5-E1, SYN31.**

- Dividends: 0.50 ex Monday 2025-03-03 (feed and filing agree: `CORROBORATED`), after a phase-0
  Friday (50.00); 0.40 ex Tuesday 2025-09-02 (feed only: `SINGLE_SOURCE`), after a phase-2 Friday
  (50.50). On each ex-date the price is still the previous Friday's level. So the factors are
  `(50 + 0.50)/50 = 101/100` and `(50.50 + 0.40)/50.50 = 509/505`.
- **Benchmark return (01-10 → 01-02):** price `50/51` × the two dividend factors:
  `(50/51)(101/100)(509/505) − 1 = 2570450/2575500 − 1` = **−1/510** = −0.001960784314.
- **Active:** `−1/26 + 1/510 = (−255 + 13)/6630` = **−121/3315** = −0.036500754148.
- **1Y beta** = **`21966244511636576867925/11736377537076681451991`** = 1.871637516963; **TE²** =
  `956758364571978900604247/75192552179111804456250000`. Both `LIMITED`. M-C5 (no dividends) and
  M-C6 (corroborated dividends only) each change all four items.

**R5-E2, SYN32 (selection version 2).** Its 2025-06-02 dividend is 0.30 in the feed and 0.35 in the
filing: `DISAGREEMENT`. Every level from 06-02 on is suppressed. Both the 1Y beta (grid dates after
06-02) and the window fact (`g_n` = 01-02) are `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.

**R5-E3, the same proxy to 2025-05-30.** The window ends before the ex-date, so nothing is
suppressed. Benchmark (01-17 phase 2 → 05-30 phase 1): `51/50.50 − 1` = **1/101**. Portfolio:
`104/101 − 1 = 3/101`. Active = **2/101**. M-C21 (suppress the whole series) fails it.

## 7. R6: DAILY and MONTHLY benchmark statistics; default views

The portfolio is SYN21 against the US index, so each daily or monthly return is a ratio of cycle
levels.

- **DAILY 1Y** (`B` = Thursday 2025-01-02 = `g_0`, `n` = 261 weekdays). 53 periods are non-zero: the
  Fridays 2025-01-03 … 2026-01-02, each the weekly step. The other 208 are 0. Beta = **`1294896284006483763/896294417375100016`** = 1.444722023148;
  `TE² = 260 × S_aa / 260` = **`64380066928027396019/12344274365749235910000`**. `LIMITED`: 261 is
  between N1 = 259 and N3 = 781. Beta differs from the weekly 1.442146… because the daily window
  contains 53 steps, not 52, and 208 zero returns that change the means.
- **MONTHLY 3Y** (`g_0` = 2023-01-31, `g_n` = 2025-12-31, `n` = 35, stubs 29 and 2 days). The phases
  of the 36 month-end levels, in order, are
  `3 3 0 0 0 1 1 1 2 2 2 3 3 3 0 0 1 1 1 2 2 2 3 3 0 0 0 0 1 1 1 2 2 3 3 3`.
  Each monthly return is `L(phase_k)/L(phase_{k−1}) − 1`, which is 0 when the phase repeats. Beta =
  **`1208083389532705719/837670434223085008`**; `TE² = 12 × S_aa / 34`. `AVAILABLE` (n = 35 = N3).
- **MONTHLY 1Y** (`g_0` = 2025-01-31, `n` = 11; phases `0 0 0 0 1 1 1 2 2 3 3 3`). Beta =
  **`144404762661/102847842292`**. `LIMITED` (n = 11 = N1).
- **R6-V1, default view of beta.** The 3Y weekly request is `AVAILABLE` (part 2's Q1-B2, beta
  `505685421350637/350647849329134`), so there is no fallback.
- **R6-V0, default view with no selection** (log version 0). The 3Y request is refused with
  `MISSING_BENCHMARK` (`NO_BENCHMARK_SELECTED`). That is not a refusal for history, and
  `MAX_AVAILABLE` would be refused for the same cause. So there is no fallback, and the refusal is
  what the view shows (Ruling 7.7 (1.2)).

## 8. R7: Current mode (Ruling 5.8 (1.2); `performance` Ruling 1.7 (1.12))

The portfolio reports in HKD and holds SYN22 (HKEX, HKD). It has no foreign currency, so `D_c(t)`
needs no ECB test. The benchmark is the US index, translated from USD into HKD.

**R7-C1, `t` = 2026-01-09 09:00 UTC.**

- **`D_c(t)`:** the HKEX close of 01-09 (08:10 UTC) is ≤ `t`, so `E` = **2026-01-09**.
- **Benchmark at `g_n` = 01-09:** the NYSE close of 01-09 (21:00 UTC) is after `t`, so the latest
  level available at `t` is Thursday 01-08's. That is the level of Friday 01-02: phase 0, 1000. The
  ECB publication of 01-09 (15:00 UTC) is also after `t`, so the fixing used is 01-08's, which has
  01-02's parity: even, 8.4000.
- The 01-09 session and fixing are **not yet due at `t`**. They are not counted as missed, so
  `m_b = 0` (not stale) and `Λ_B = 0` (not lagged).
- **SEAM at `g_n`:** HKEX 08:10 (01-09) against NYSE 21:00 (01-08), which is 670 minutes, and ECB
  13:10 (01-08), which is 1140 minutes. **1140** is the largest.
- **Window facts (01-17 → 01-09):**
  - benchmark `(1000 × 8.40)/(1010 × 8.40) − 1` = **−1/101** (both fixings even);
  - portfolio `105/100 − 1 = 1/20`;
  - active `1/20 + 1/101 = (101 + 20)/2020` = **121/2020**.
- **1Y statistics:** identical to the historical twin except that the last benchmark return
  (01-02 → 01-09) is **0** instead of `1030 × 8.442/(1000 × 8.40) − 1 = 703/20000`. Beta =
  **`24359718959946954940527600/12700657924679573112508601`** (closed form, §13).

**R7-H1, historical as of 2026-01-09.**

- The 01-09 close (phase 1, 1030) and fixing (odd, 8.442) are used.
- Benchmark `(1030 × 8.442)/(1010 × 8.40) − 1 = 8695.26/8484 − 1` = **503/20200**.
- Active `1/20 − 503/20200 = (1010 − 503)/20200` = **507/20200**.
- SEAM at `g_n`: HKEX 08:10 against NYSE 21:00 = **770** minutes.
- Beta = **`11931872014978823555868000/6302367486519737416854973`**.
- The two results differ: Current mode never reads a level or fixing that did not exist at `t`
  (structural assertion S3-3).

**R7-C2, `t` = 2026-01-09 07:00 UTC.** The HKEX close of 01-09 is not yet past, so `D_c(t)` =
**2026-01-08**. The last weekly grid date ≤ 01-08 is 01-02 (stub 6 days).

- Portfolio `100/100 − 1 = 0` (01-17 phase 2 → 01-02 phase 0).
- Benchmark `1000/1010 − 1` = −1/101.
- Active **1/101**.

M-C2 (`D_c(t)` = the UTC date of `t`) gives `E` = 01-09 instead, and changes both items.

## 9. R8: account scope (Ruling 0.1 (1.2))

- **A1** holds 100 SYN21.
- **A2** holds 10,100 USD until Wednesday 2025-06-11, when it transfers the cash to A1, which buys 100
  SYN21 at 101.00. (Wednesday 06-11 carries Friday 06-06's phase-2 level, 101.)

**A1 scope.** The internal transfer is a cash inflow of A1 (`performance` Ruling 4.5), at the start
of 06-11:

```
(06-06, 06-13]:  10100/10100 × 20200/(10100 + 10100) × 19600/20200 − 1 = 98/101 − 1 = −3/101
```

That is SYN21's return for the phase 2 → 3 period. Every period is SYN21's, so A1's beta, TE and
volatility equal part 2's Q1 exactly: beta **`505685421350637/350647849329134`**, volatility
0.222352722900 (S3-2). M-C10 (internal transfers not flows) makes the 06-10 → 06-11 sub-period
`20200/10100`, a +100 % return, and changes all three items.

**A2 scope.**

- The period ending 06-13 has the transfer out: `(0 + 10100)/10100 − 1 = 0`, an observation.
- The 29 periods from 06-20 to 01-02 have no capital at any time: `ZERO_CAPITAL_PERIOD`, so the 1Y
  volatility is `INSUFFICIENT_DATA` (`ZERO_CAPITAL_PERIOD`, `PERIOD_INSUFFICIENT`).
- `MAX_AVAILABLE`: the last insufficient period ends at `g_n` itself, so there is no full period after
  it: `NO_FULL_PERIOD`.
- The requested base is A2's own `I₀` = 2022-12-29.

**Portfolio scope.** The transfer and the buy are neutral. Before 06-11 the value is
`100 P + 10100`, so the diluted returns are `(P' − P)/(P + 101)`: 4/201, −3/205, −3/202, 2/199. 22
periods (01-10 … 06-06) are diluted; from 06-13 on, the returns are SYN21's (the period ending 06-13
is `19600/20200 − 1 = −3/101`). Beta = **`2807386797237209885907/2491875084131148150526`** =
1.126616183578. The benchmark is the portfolio's selection at every scope (Ruling 5.6 (1.2)).

## 10. R9: zero-capital periods (Ruling 2.4)

The portfolio deposits 10,000 USD on 2024-12-30 (`I₀` = 12-29) and withdraws it at the end of
Wednesday 2025-03-05. It deposits 10,000 again at the start of Wednesday 04-02 and buys 100 SYN21 at
100.00, the 03-28 phase-0 level.

- **The week ending 03-07** has capital on Monday to Wednesday: `(0 + 10000)/10000 − 1 = 0`. That is
  an observation, of a partial-exposure period (a stated limitation).
- **The weeks ending 03-14, 03-21 and 03-28** have no capital and no event: `INSUFFICIENT_DATA`,
  `ZERO_CAPITAL_PERIOD`. Counting them as 0 % returns (M-C9) would add three fabricated observations.
- **The week ending 04-04** has a `ZERO_CAPITAL_RUN` from 03-29 to 04-01 (factor 1), then
  `V(04-04)/(V(04-01) + 10000) = 10400/10000`, so **1/25**. It is an observation.
- **1Y volatility:** `INSUFFICIENT_DATA`, no reason (`ZERO_CAPITAL_PERIOD` has no code; Ruling 7.3).
- **`MAX_AVAILABLE`:** the base moves to **03-28**, the end of the last insufficient period. There are
  40 observations (stub 89 days from `I₀`).
  - Volatility: `INSUFFICIENT_DATA`, `INSUFFICIENT_OBSERVATIONS` (40 < 51).
  - Maximum drawdown on the path from 03-28 (Ruling 1.1): `W` = 1, then 1.04 at 04-04 (the peak), 1.01
    at 04-11, 0.98 at 04-18 (the trough), and 1.04 again at 05-02 (the recovery). The drawdown is
    `0.98/1.04 − 1` = **−3/52**.
- **Default view of volatility:** the 3Y request is refused (`WINDOW_BEFORE_INCEPTION`), so the view
  falls back to `MAX_AVAILABLE` and shows **its own state, `INSUFFICIENT_DATA`**. The fallback shows
  the true window, count and state; it does not promise a number (P5). PD-0040's "LIMITED state" is
  the typical case, not a guarantee.

## 11. R10: a snapshot portfolio

The snapshot `S` is 2024-11-29 (phase 3): 100 SYN21 and 500 USD. `I₀ = S` (`performance` Ruling
4.4).

- **3Y** (`B` = 2023-01-02 < `S`): `INSUFFICIENT_DATA` + `NOT_RECONSTRUCTABLE`, detail
  `WINDOW_BEFORE_SNAPSHOT`. M-C11 accepts the window and computes over dates the ledger cannot
  reconstruct.
- **The returns** are `(P' − P)/(P + 5)`: 4/105, −3/109, −3/106, 2/103 for periods starting at phases
  0 to 3.
- **1Y** (13 cycles from phase 0): `vol² = 52 × S_rr / 51` = **`11913536395267481/265440199653461700`**,
  `LIMITED`.
- **`MAX_AVAILABLE`** (base `S`, `max_available_start` `INCEPTION`): one period from phase 3, then 14
  cycles. That is 57 observations. `vol²` = **`39470175925365211/890005375308665700`**; beta =
  **`6646491904136442380/4829631169900600693`**. Both `LIMITED`.
- **Default view (PD-0040):** `fallback: true`. `refused` is the 3Y `NOT_RECONSTRUCTABLE` result; it
  stays in the evidence. `shown` is the `MAX_AVAILABLE` result with its window, count, state and value.

## 12. R11 and R12: a split missing from the ledger, and the same split recorded

SYN43 has a 2:1 split, ex Monday 2025-09-08, with a feed and a filing record that agree:
`CORROBORATED`.

- **R11 (no ledger SPLIT):** by `market-data` Ruling 6.4 item 2, every valuation from 09-08 on is
  `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.
  - The 1Y beta and volatility windows reach it: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`,
    `PERIOD_INSUFFICIENT`.
  - `MAX_AVAILABLE`: the last insufficient period ends at `g_n`, so `NO_FULL_PERIOD`.
  - The window fact to 09-05 (R11-X2) is before the ex-date. Portfolio `98/104 − 1 = −3/52`
    (phase 1 → 3); benchmark `990/1030 − 1 = −4/103`; active `−3/52 + 4/103 = (−309 + 208)/5356` =
    **−101/5356**.
  - The window fact to 09-12 (R11-X3) is after the ex-date: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`.
    M-C8 (no suppression) gives a −50 % phantom return instead.
- **R12 (SPLIT recorded on 09-08, applied at the start of the day):** 100 shares at 98.00 on 09-05
  become 200 shares at 49.00 on 09-08. The value is continuous (9,800).
  - The week ending 09-12 returns `200 × 50/(100 × 98) − 1` = **1/49**, which is SYN21's phase 3 → 0
    return.
  - Every period is SYN21's, so beta = part 2's Q1 (S3-2). M-C23 (the SPLIT does not change the
    quantity) halves the value from 09-08 and changes the three items.

## 12a (1.2). R13: reversals and corrections in the selection log (risk Ruling 5.6 (1.4))

The portfolio is SYN21 in USD, as R4. The `benchmark_return` items use the window 01-10 → 01-02 and
take their values from earlier sections:

| Benchmark | Benchmark return | Source |
|---|---|---|
| US index | −3/103 | §5 |
| CN index | −1/68 | §4 |
| ETF proxy | −1/510 | §6; not in force at any asserted version |
| two-source US index | −3/103 | §5 |

So each item tests only *which* benchmark is in force.

The log (positions per Ruling 5.6 (1.4) item 3.4):

| Seq | Record | Position | Live at v = 10? |
|---|---|---|---|
| 1 | SELECT US | 1 | no (reversed by 7) |
| 2 | SELECT CN | 2 | no (reversed by 3) |
| 3 | REVERSAL of 2 | — | — |
| 4 | CLEAR | 4 | no (reversed by 5) |
| 5 | REVERSAL of 4 | — | — |
| 6 | SELECT CN | 6 | no (reversed by 9) |
| 7 | REVERSAL of 1 (pair with 8) | — | — |
| 8 | SELECT ETF proxy, corrects 1 | **1** | yes |
| 9 | REVERSAL of 6 (pair with 10) | — | — |
| 10 | SELECT two-source US, corrects 6 | **6** | yes |

Resolution at each asserted version:

| v | Known live records (position) | In force | Rule |
|---|---|---|---|
| 2 | 1 (1), 2 (2) | **2, CN** | latest position |
| 3 | 1 (1) | **1, US** | 2 is void; the prior live record returns, not NONE |
| 4 | 1 (1), 4 (4) | **4, CLEARED** | a CLEAR is a record |
| 5 | 1 (1) | **1, US** | the CLEAR is void |
| 7 | — | **REFUSED** | 7 is known, its replacement 8 is not |
| 8 | 6 (6), 8 (1) | **6, CN** | the replacement sits at seq 1's position, behind 6 |
| 10 | 8 (1), 10 (6) | **10, two-source US** | the replacement of the latest record is the latest |

**Mutations:**

- **M-C25** (reversal ignored) gives CN at v3 and CLEARED at v5.
- **M-C26** (NONE after a reversal) gives NONE at v3 and v5.
- **M-C27** (cut pin accepted) gives NONE at v7.
- **M-C28** (earliest live record) gives:
  - US at v2 and v4;
  - the ETF proxy (position 1) at v8 and v10;
  - in R5, version 2, the first proxy instead of the disputed one, which changes R5-E2 and R5-E3.
- **M-C29** (a replacement ordered by its own seq) gives the ETF proxy at v8. **This is the engineer's
  current build.**

## 13. The closed forms (second derivation)

`cp4_part3_closed_forms.py` builds each series from the cycle tables of §1 with its perturbation, and
nothing else:

- R2: the missing print (3Y and, 1.1, 1Y);
- R3: the stale CNY rate;
- R5: the two dividend factors;
- R7: the last benchmark return 0 or 703/20000;
- R8: the diluted periods;
- R10: the cash.

It computes `S_rb`, `S_bb`, `S_rr` and `S_aa` directly. It re-derives 25 values:

- the TE and IR of R1;
- beta and TE of R2 (3Y), R3 and R5;
- (1.1) beta, TE and volatility of R2-L2;
- the R3 and R5 benchmark returns;
- the daily and monthly beta and TE of R6;
- the R7 Current and historical betas;
- the R8 portfolio beta and volatility;
- the R10 volatilities and beta.

All 25 agree with the fixture (§18). The calculator's `--closed` adds four metamorphic
checks:

- A1-scope beta = Q1's;
- recorded-split beta = Q1's;
- the flat-benchmark TE² and IR², from part 2's one-cycle sums.

## 14. How a fixture asserts the default view (a service-level composition)

The default view is a request rule, not a metric (PD-0040; Ruling 7.7 (1.2)). It is asserted at two
levels, so that the method and the composition are tested separately:

1. **The two underlying results are ordinary items.**
   - R10-S1 item 1 is the refused 3Y result, and item 3 is the `MAX_AVAILABLE` result.
   - R9-Z1 items 1–2 are the 1Y and `MAX_AVAILABLE` results.
   - Each reproduces on its own, from its own manifest.
2. **A `default_view` item** (kind `default_view`, with `metric`, `frequency` and `default_request`)
   asserts the composition only:
   - `fallback`: true exactly when the default request is `INSUFFICIENT_DATA` with a history detail;
   - `refused`: the summary of the default request's result when it fell back, so the 3Y refusal
     stays in the evidence; otherwise null;
   - `shown`: the summary of what the view displays, with the actual request (`MAX_AVAILABLE`), its
     effective window, observation count, state and value.

   The engine (or service) exposes the composition as one function of (metric, frequency, scope,
   `E` or `t`, selection-log version), and the fixture loader calls it. The function never relabels
   a result: `shown.request` is `MAX_AVAILABLE`, never `TRAILING_MONTHS 36`.
3. **Mutations:**
   - M-C12 (always fall back) fails R6-V1, where the 3Y result is `AVAILABLE`, and R6-V0, where the
     refusal is `MISSING_BENCHMARK`, not history;
   - M-C13 (never fall back) fails R9-Z1 and R10-S1.

Four assertions are covered:

| Case | Default 3Y result | `fallback` | Shown |
|---|---|---|---|
| R6-V1 (beta) | `AVAILABLE` | false | the 3Y result |
| R6-V0 (beta, no selection) | `MISSING_BENCHMARK` | false | the 3Y refusal |
| R9-Z1 (volatility) | `WINDOW_BEFORE_INCEPTION` | true | `MAX_AVAILABLE`, 40 obs, `INSUFFICIENT_DATA` |
| R10-S1 (volatility) | `NOT_RECONSTRUCTABLE` (`WINDOW_BEFORE_SNAPSHOT`) | true | `MAX_AVAILABLE`, 57 obs, `LIMITED`, 0.210590228707 |

## 15. Detail names asserted

These are `risk` details only (Ruling 7.4 as of 1.2):

- `OBSERVATIONS_BELOW_STANDARD`, `INSUFFICIENT_OBSERVATIONS`, `NO_FULL_PERIOD`;
- `WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`;
- `PERIOD_INSUFFICIENT`, `STALE_PERIODS`, `ZERO_CAPITAL_PERIOD`;
- `ZERO_BENCHMARK_VARIANCE`, `NO_BENCHMARK_SELECTED`;
- **`BENCHMARK_SOURCE_CONFLICT`** (new in 1.2).

`market-data` and `performance` lineage names (`SPLIT_NOT_RECORDED`, `BENCHMARK_STALE`, and so on) are
not asserted, as in parts 1 and 2.

## 16. What part 3 does not cover

- **A row due at `t` but not yet in `M_t`** (Ruling 5.8 (1.3) item 7). The 1.1 vintages make `M_t`
  exactly the due rows (§1a), so a late file is not exercised.
- **The risk-free quote at `t` in Current mode.** R7 asserts no rf-dependent metric.
- **An ETF proxy split, a proxy price gap, and a resolution record** settling a benchmark or
  dividend disagreement.
- **Two benchmark sources that agree within the precision bound but are not equal.**
- **Account scope with several currencies, and account-level money gains.** S3-4 states that
  identity; it is not an item.
- **A default view for a benchmark-relative metric that falls back.** R6-V1 and R6-V0 do not fall
  back.
- **`DAILY` in Current mode; 5Y requests.**

## 17. The mutation catalog

Each mutation is one departure from `risk/1.4`, with part 2's mutations reused where they are the same
departure. `--mutations` requires that each one changes exactly the items whose `bites` name it, and
that every item names at least one.

| Id | Departure | Items changed |
|---|---|---|
| M-C1 | Current mode reads the benchmark by date, ignoring `t` | 4 (R7-C1) |
| M-C2 | `D_c(t)` = UTC date of `t` | 2 (R7-C2) |
| M-C3 | second source ignored | 5 (R4) |
| M-C4 | primary wins a disagreement | 3 (R4-S1 β, TE; R4-S2) |
| M-C5 | proxy without dividends | 4 (R5-E1) |
| M-C6 | proxy with corroborated dividends only | 4 (R5-E1) |
| M-C7 | proxy takes the feed amount on a disagreement | 2 (R5-E2) |
| M-C8 | no split suppression | 4 (R11-X1, R11-X3) |
| M-C9 | a period without capital counted as 0 % | 7 (R8 A2, R9) |
| M-C10 | internal transfers not flows at account scope | 3 (R8 A1) |
| M-C11 | window before a snapshot accepted | 2 (R10) |
| M-C12 | default view always falls back | 2 (R6-V1, R6-V0) |
| M-C13 | default view never falls back | 2 (R9-Z1, R10-S1) |
| M-C14 | β, R², α shown as 0 when `S_bb` = 0 | 3 (R1) |
| M-C15 | portfolio lag ignores price staleness | 4 (R2-L1, R2-L2 β and TE) |
| M-C16 | benchmark lag ignores FX staleness | 2 (R3) |
| M-C17 | TE with divisor n | 11 |
| M-C18 | β = S_rb / S_rr | 14 |
| M-C19 | volatility with divisor n | 7 |
| M-C20 | benchmark not translated | 13 (R3, R7, R13 CN items) |
| M-C21 | a disputed dividend suppresses the whole proxy | 1 (R5-E3) |
| M-C22 | window-fact benchmark leg from `B` | 19 |
| M-C23 | ledger SPLIT ignored | 3 (R12) |
| M-C24 (1.1) | reason chosen among causes at every level | 3 (R2-L2) |
| M-C25 (1.2) | a REVERSAL ignored | 4 (R13-V3, R13-V5) |
| M-C26 (1.2) | NONE after a REVERSAL | 4 (R13-V3, R13-V5) |
| M-C27 (1.2) | a pin that cuts a correction pair accepted | 1 (R13-V7) |
| M-C28 (1.2) | the earliest live record in force | 11 (R13-V2, V4, V8, V10; R5-E2, R5-E3) |
| M-C29 (1.2) | a replacement ordered by its own seq | 2 (R13-V8) |
| M-C30 (1.5) | the active return over a zero-capital window takes the TWR's factor-1 value | 1 (R9-Z3) |
| M-C31 (1.5) | a refused window drops the window-independent benchmark cause | 2 (R6-W0) |
| M-C32 (1.6) | a disputed proxy dividend suppresses every level from its ex-date on | 2 (R5-E4) |
| M-C33 (1.6) | a disputed ETF print withholds every later print | 2 (R5-E5) |
| M-C34 (1.6) | a disputed ETF print treated as missing (stale) | 2 (R5-E6) |
| M-C35 (1.6) | no fallback for an active return refused by its portfolio leg | 1 (R11-V1) |
| M-C36 (1.7) | two one-sided dividend statements that share no date are two dividends however close | 1 (R5-E7) |
| M-C37 (1.7) | any two unpaired statements of the two sides are one disputed dividend | 2 (R5-E8) |
| M-C38 (1.8) | a dividend in another currency added unconverted | 3 (R5-E9) |
| M-C39 (1.8) | converted at the pay-date fixing | 3 (R5-E9) |
| M-C40 (1.8) | the conversion's freshness ignored | 3 (R5-E9) |
| M-C41 (1.8) | the issuer's stated payment ignored | 3 (R5-E9) |
| M-C42 (1.8) | the interim refusal: proxy unavailable from the ex-date | 3 (R5-E9) |
| M-C43 (1.9) | a one-sided issuer payment makes a disagreement | 2 (R5-E10) |
| M-C44 (1.9) | a multi-source benchmark reconciled without declared precision | 1 (R4-S6) |
| M-C45 (1.9) | precision inferred from the level texts | 1 (R4-S4) |
| M-C46 (1.9) | only the first (FEED) statement's paid fields kept (CP4F-15) | 2 (R5-E11, R5-E12) |

(1.9) M-C43 now changes 3 items (R5-E10, R5-E11). M-C21 now also changes R5-E9, R5-E10 and R5-E11;
M-C7 also changes R5-E12; M-C5, M-C22, M-C38, M-C41 and M-C42 also change R5-E11; M-C28 also changes
R5-E11 and R5-E12.

(1.6) M-C28 now also changes the seven new R5 items, and M-C8 and M-C13 also change R11-V1.

(1.5) M-C9 now changes 8 items (R9-Z3's 1Y active return is added).

---

## 18. Run record

Run on 2026-10-02 with the system `python3` (3.9.6), read-only, in
`methodology/fixtures/cp4_golden/derivation`. The calculator run took about 35 seconds. The output is
abbreviated where marked "…": every mutation line was `ok`.

```
$ python3 cp4_part3_calculator.py ../cp4_golden_part3.json --check --closed --mutations --retrieval
ok  R8-K1 A1-scope beta = part-2 Q1 beta = 505685421350637/350647849329134
ok  R12-X1 recorded split: beta = part-2 Q1 beta = 505685421350637/350647849329134
ok  R1-F1 flat benchmark: TE^2 = 52 s2(r) = 2470301597923/49964906040000
ok  R1-F1 flat benchmark: IR^2 = 52 rbar^2 / s2(r) = 29182926291/2470301597923
CLOSED FORMS AGREE
ok  M-C1: changes 4 item(s); fixture names 4
…
ok  M-C29: changes 2 item(s); fixture names 2
MUTATIONS AGREE
smallest distance of a square-root value from a rounding boundary: 0.058509050948 quanta ( OK ; need > 1e-18 )
CHECK PASSED - 0 difference(s)
RETRIEVAL CONSISTENT - 5214 calendar rows, 2 Current-mode instant(s), 0 problem(s)

$ python3 cp4_part3_calculator.py ../cp4_golden_part3.json --release
ok  RB-1 … ok  RB-5
ok  M-R1: changes ['RB-2', 'RB-3']; fixture names ['RB-2', 'RB-3']
ok  M-R2: changes ['RB-4']; fixture names ['RB-4']
ok  M-R3: changes ['RB-3']; fixture names ['RB-3']
ok  M-R4: changes ['RB-1', 'RB-2', 'RB-3', 'RB-4', 'RB-5']; fixture names ['RB-1', 'RB-2', 'RB-3', 'RB-4', 'RB-5']
RELEASE CASES AGREE

$ python3 cp4_part3_closed_forms.py ../cp4_golden_part3.json
ok  R1-F1[3].exact_square  TE^2 = 52 S_rr / 51 = 2470301597923/49964906040000
…   (25 lines, each ok)
CLOSED FORMS AGREE
```

(1.1) The retrieval check was also run against the two wrong declarations:

- 1.0's single time of 2022-11-30: `RETRIEVAL INCONSISTENT … 5906 problem(s)`;
- a single file per series retrieved at 2026-04-01: `RETRIEVAL INCONSISTENT … 9736 problem(s)`.

**The checker is not blind.** I changed a copy of the fixture under `$TMPDIR` in three places. Each
change was reported as a difference (`CHECK FAILED - 3 difference(s)`):

- R7-C1's active return set to the historical 507/20200;
- R9-Z2's 03-14 period state set to `AVAILABLE`;
- R10-S1's default-view `fallback` set to false.

Parts 1 and 2 were re-checked after `risk/1.2` and again after `risk/1.3`. Both report `CHECK
PASSED - 0 difference(s)`.
Part 2's `--mutations` also reported `MUTATIONS AGREE`.
