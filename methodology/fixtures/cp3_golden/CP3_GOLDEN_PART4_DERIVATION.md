# CP3 golden fixture, part 4: hand derivation and ratification (attribution)

**Fixture:** `methodology/fixtures/cp3_golden/cp3_golden_part4.json`, ID `cp3_golden/1.2-part4`.
It extends `cp3_golden/1.4-part1`, `1.2-part2` and `1.2-part3`. Its `convention_sets` are minimum
versions (Ruling 11.6).

**1.2-part4 (`performance/1.9`; answers to the CP3e build, each re-derived).**

- **P22-V1.** Part 1's `format` defines `price_date_used` as the session whose close **values** the
  holding. At 5 missed sessions `market-data` 5.2 withholds the value, so no close is used.
  - 1.1-part4's `2025-03-07` in that field was **my error**; the engine was right.
  - The date of the last print is still the audit fact the user needs ("last priced 2025-03-07"),
    so it is now a separate lineage field, `last_print_date` (Ruling 1.1b). It counts back from
    03-14 over the five sessions 03-10 to 03-14, to the 03-07 print.
  - P22-V1 now asserts `price_date_used`: null, `last_print_date`: 2025-03-07, and `missed_sessions`
    5. The state and reason are unchanged.
- **Breakdowns** are decomposition objects (Ruling 9.6 (1.9)). Their parts are apportioned to the
  line's apportioned display value, in the 9.6 order: positions, then cash by currency code, then
  receivables.
  - **P6, line `attr.fx`** (displayed 6.75): the exact parts are 45/8 = 5.625, −500/87 = −5.747126 and
    55/8 = 6.875. Their floors are 5.62, −5.75 and 6.87, summing to 6.74, so the shortfall is 1. The
    remainders are .005, .002874 and .005. That is a tie between the position and USD cash, broken by
    the 9.6 order: the position comes first. Result **5.63, −5.75, 6.87** = 6.75. 1.1-part4 showed the
    independently rounded 5.63 + 6.88 − 5.75 = 6.76.
  - **P21, line `attr.fx`** (displayed −8.62): floors −7.18, −1.03 and −0.42, summing to −8.63;
    shortfall 1. The largest remainder is the receivable's (.009744), so the result is **−7.18, −1.03,
    −0.41**. This is the same as before.
  - **P3, line `attr.price`** (displayed 907.69): floors −92.31 and 1,000.00 sum to the line, so the
    shortfall is 0. **−92.31, 1,000.00**, the same as before.
- **Ruling 9.5 (1.9)** confirms the engine: a non-positive base, a negative value or a total loss
  suppresses only the percentage lines. No part-4 item exercises that case. Every money and Cariño
  value below is unchanged.

**1.1-part4.** It cites `performance/1.7`, whose Ruling 9.2 (1.7) fixes the line identifiers:
`attr.price`, `attr.fx`, `attr.price_fx_interaction`, `attr.income`, `attr.fees`, `attr.taxes`,
`attr.financing` and `attr.conversion`. Every line entry carries its `id`, and keeps its position
and label. No value below changed. "Choice 1" in §1 is resolved by the PM's ruling. It is kept below
as the 1.0 record.

**Scope:** `performance` Rulings 9.1–9.6. That covers:

- the eight exact daily money lines over a window, summing exactly to `G`;
- their largest-remainder display (Ruling 2.4);
- the Cariño-linked percentage lines, reconciling to the TWR;
- per-listing and per-component breakdowns (9.6);
- the conversion result (8.5), and FX on a dividend receivable (8.1);
- the Southbound trade result in the price line;
- the all-in-`R` metamorphic check (11.3 #4);
- an interior valuation gap (11.3 #6);
- stale inputs, and a suppressed split.

PD-0035 §4 applies: the exact daily split supersedes HG1 §4.3, and line 1 is the local price effect.
The since-acquisition view (9.7) is asserted in part 3 and is not repeated.

**Conventions:** `performance/1.6`, `ledger-replay/1.5`, `market-data/1.10`. No ruling was changed
for this part.

**Author:** `quant-analyst` subagent, 2026-10-01.

**Calculator:** `derivation/cp3_part4_calculator.py`. It uses the standard library only and imports
nothing from `src/`. It implements Ruling 9.1 day by day, from each portfolio's events, over **every
calendar day** of the window. On every day it asserts **I-4** (Σ lines = `g_D`). Per window it
asserts **I-3** (Σ `g_D` = `G`) and **I-2**: the daily product equals the segment TWR already asserted
in parts 1–3. It links with Cariño in `Decimal` at `prec` 50. Every one of those assertions passes.
Re-run it with `python3 methodology/fixtures/cp3_golden/derivation/cp3_part4_calculator.py`.

## 0. Independence

- **Read:**
  - `performance` §5, §8 and §9, and Example W;
  - `market-data` 1.6 and 5.2;
  - parts 1–3 and their derivations.
- **Not read or run:** any engine code or output.
- **Checks besides the calculator:** a JSON check of the fixture against the calculator's results.
  It compares item counts, exact lines, apportioned values and their sums, `C_k`, breakdown sums, and
  presented-against-exact rounding. **It found no mismatch.** It computes no expected value.
- **Market data:** synthetic. The release is parts 1–3's market data plus one listing, SYNG, with a
  five-session gap. Nothing earlier changes.

## 1. The method applied (Ruling 9.1), and two choices I had to make

**Notation.** For each position on day `D`:

- `σ` is the split ratio dated `D` (else 1);
- `q⁰ = q(D−1)σ`, `P⁰ = P(D−1)/σ`, `P¹ = P(D)`;
- `X⁰ = X(c(ℓ)→R, D−1)` and `X¹ = X(c(ℓ)→R, D)`.

**The lines:**

- price: `q⁰(P¹ − P⁰)X⁰`, plus each trade's result against the close;
- FX: `q⁰P⁰(X¹ − X⁰)` on positions, `m⁰(X¹ − X⁰)` on start cash, and `r⁰(X¹ − X⁰)` on start
  receivables;
- interaction: `q⁰(P¹ − P⁰)(X¹ − X⁰)`;
- income, fees, taxes and financing at the day's fixing; an accrued dividend's income at the ex-date;
- the conversion result (8.5).

Flows, in-kind offsets, internal transfers and the settlement of a receivable contribute 0.

**Choice 1: how lines are identified.** Ruling 9.2 fixes the **order** of the eight lines. No
ruling fixes their identifier names; the fixture plan lists that as a format point still open. So
the fixture identifies each line by its Ruling 9.2 **position** (1–8), with an informative name. A
rename on either side then never invalidates the fixture.

**Choice 2: P7 is replaced, for FX on a receivable.** Part 2's P7 has its dividend ex-date
(05-06) and pay date (05-20) in synthetic FX period B, where the rate is constant, so its receivable
FX is exactly 0. A new portfolio, P21, puts the ex-date (03-28) before the 04-01 FX step and the pay
date (04-03) after it.

**Rates used:**

| Pair | Before 04-01 | From 04-01 | Change |
|---|---|---|---|
| USD per HKD | 5/39 | 16/125 | 16/125 − 5/39 = **−1/4,875** |
| HKD per USD | 39/5 | 125/16 | **+1/80** |
| HKD per CNY | 13/12 | 125/116 | **−1/174** |
| CNY per HKD | 12/13 | 116/125 | — |

## 2. P12, Example W on the fixture's FX (W′; L = 7)

**03-31** (`β` = 10,000):

- trade result (100 × 390 − 38,000) × 5/39 = **5,000/39**;
- fee −10 × 5/39 = **−50/39**;
- conversion −5,000 + 38,800 × 5/39 = **−1,000/39**;
- `g` = 3,950/39 ✓ (`V` = 393,950/39).

**04-01** (5/39 → 16/125; SYNH 390 → 400; `β` = 393,950/39; the withdrawal of 1,000 contributes 0):

- price 100 × 10 × 5/39 = **5,000/39**;
- FX on SYNH 39,000 × (−1/4,875) = **−8**, and on HKD cash 790 × (−1/4,875) = **−158/975**;
- interaction 1,000 × (−1/4,875) = **−8/39**;
- `g` = 116,842/975 ✓. In 975ths: 125,000 − 7,800 − 158 − 200 = 116,842.

**04-02:** income 200 × 16/125 = **128/5**, taxes −20 × 16/125 = **−64/25**; `g` = 576/25 ✓.

**Window lines:**

- price **10,000/39**;
- FX −8 − 158/975 = **−7,958/975**;
- interaction **−8/39**;
- income **128/5**, fees **−50/39**, taxes **−64/25**, financing **0**, conversion **−1,000/39**.

The sum, in 975ths: 250,000 − 7,958 − 200 + 24,960 − 1,250 − 2,496 − 25,000 = 238,056, and 238,056/975
= **6,104/25** = 244.16 = part 2's `G` ✓.

**Apportioned** (total 244.16):

- floors 256.41, −8.17, −0.21, 25.60, −1.29, −2.56, 0.00, −25.65, summing to 244.13, so the shortfall
  is 3;
- the largest remainders are conversion (.00897), then FX and fees (.00795 each, an exact tie
  broken in line order), so conversion gets −25.64, FX −8.16 and fees −1.28;
- result: **256.41, −8.16, −0.21, 25.60, −1.28, −2.56, 0.00, −25.64** = 244.16.

**Cariño.** The days have `r` = 79/7,800, 58,421/4,924,375 and 9/3,602. The TWR is 2,776,451/112,562,500
(part 2) ✓. The `C_k` are in the fixture, computed by the calculator. The internal sum differs from
the TWR by −3 × 10⁻⁵¹.

**P12-A2, the FX day alone, (03-31, 04-01].** With one day, `κ_D = κ`, so `C_k = m_k / β` exactly:

- `C_1` = (5,000/39)/(393,950/39) = **100/7,879** = 0.012691965986;
- `C_2` = (−7,958/975)/(393,950/39) = **−3,979/4,924,375** = −0.000808021323;
- `C_3` = **−4/196,975** = −0.000020307146;
- TWR = `r_D` = **58,421/4,924,375** = 0.011863637517.

## 3. P1 since inception (L = 25)

Only seven days have non-zero lines. Every other day has no price or FX change, and every trade on
it is at the close.

| Day | `β_D` | Lines |
|---|---|---|
| 03-03 | 490,000/39 | price: AAPL 37.50 → 45 on 200 = **1,500**. E7 sells at the close: 0 |
| 04-01 | 704,500/39 | price: 0700 35 → 36 on 500 at 5/39 = **2,500/39**. FX: 0700 17,500 × (−1/4,875) = −140/39, plus HKD 2,500 × (−1/4,875) = −20/39, so **−160/39**. Interaction: 500 × (−1/4,875) = **−4/39** |
| 04-02 | 18,124 | X3 trade result (7,200 − 7,000) × 16/125 = **128/5**; fee **−2**; conversion X8 −1,000 + 7,750 × 16/125 = **−8** |
| 05-31 | 95,698/5 | financing **−7/2** |
| 06-02 | 241,361/10 | MSFT 400 → 420 on 15 = 300, plus 0700 36 → 37 on 700 at 16/125 = 448/5, so **1,948/5** |
| 06-10 | 245,257/10 | MSFT 420 → 430 on 20 = **200**. X11 sells at the close |
| 06-16 | 247,257/10 | AAPL 45 → 50 on 150 = **750**. X12 sells at the close; X13 is internal |

- **Neutral days:** 02-03 is the split day (`σ` = 4, so `P⁰` = 37.50 = `P¹`). E8's in-kind inflow on
  03-10 is offset. The deposits contribute 0.
- **Window lines:**
  - price 1,500 + 2,500/39 + 128/5 + 1,948/5 + 200 + 750 = **571,214/195**;
  - FX **−160/39**; interaction **−4/39**; fees **−2**; financing **−7/2**; conversion **−8**;
  - income and taxes 0.
- **Sum:** **1,135,523/390** = 2,911.60 = part 1's `G` ✓.
- **I-2:** the daily product equals part 1's TWR fraction exactly.

## 4. P6, FX only (HKD reporting)

The only non-zero day is 04-01, with `β` = 26,650/3.

| Component | FX on 04-01 (HKD) |
|---|---|
| AAPL position | 450 × 1/80 = **45/8** |
| USD cash | 550 × 1/80 = **55/8** |
| CNY cash | 1,000 × (−1/174) = **−500/87** |

- The total is 25/2 − 500/87 = **1,175/174** = `G` ✓.
- One non-zero day means `C_2` = TWR = **47/61,828**, and the other seven lines are exactly 0.
- The component breakdown sums to line 2 (Ruling 9.6).

## 5. P3, the Southbound trade result (CNY reporting; L = 7)

**(03-02, 03-16].** Everything happens on 03-04, with `β` = 100,000:

- **0700 (Southbound):** 1,000 × 35 HKD × 12/13 − 32,400 CNY = 420,000/13 − 421,200/13 =
  **−1,200/13**. That is the gap between the CNY actually paid and the ECB cross, in the **price**
  line (Ruling 9.1);
- **SYNA:** 2,000 × (10.50 − 10.00) = **1,000**.
- Line 1 = **11,800/13** = `G`.
- `C_1` = TWR = **59/6,500**.

**(03-02, 03-20]** adds 03-20: SYNA 10.50 → 11.00 on 2,000 = 1,000, against the 10.50 carried over the
gap, with `β` = 1,899,800/13.

- Line 1 = **24,800/13** = part 1's `G` ✓, and `C_1` = TWR = **35,242/2,205,125** = part 1's ✓.
- **State: `LIMITED` + `STALE_DATA`.** SYNA is two and three sessions stale on 03-18 and 03-19, and
  the attribution needs every day (Ruling 9.5).
- Part 1 asserts the TWR over the same window as `AVAILABLE`, because it needs no interior day.

## 6. P21, FX on a dividend receivable (USD reporting; new)

**Events:**

- 03-26: `DEPOSIT` 40,000 HKD; `BUY` 1,000 × 0700 for 35,000 HKD at the 35.00 close (trade result 0).
- `DIVIDEND` 2,000 HKD, ex-date 03-28, pay date 04-03.
- 04-03: `TAX` 200 HKD.

**Days:**

| Day | `β_D` | `g_D` | Lines |
|---|---|---|---|
| 03-28 (ex-date) | 200,000/39 | 10,000/39 (`r` = 1/20) | income 2,000 × 5/39 = **10,000/39**. A receivable of 2,000 HKD appears |
| 04-01 | 70,000/13 | 1,552/13 | price 1,000 × 1 × 5/39 = **5,000/39**. FX on the position 35,000 × (−1/4,875) = −280/39, on the cash 5,000 × (−1/4,875) = −40/39, **on the receivable 2,000 × (−1/4,875) = −16/39**; FX total **−336/39 = −112/13**. Interaction **−8/39** |
| 04-03 (pay date) | 5,504 | — | the receivable becomes cash at equal value (0); taxes −200 × 16/125 = **−128/5** |

- **Values:** `V(04-01)` = 43,000 HKD × 16/125 = 5,504. `V(04-03)` = (36,000 + 6,800) × 16/125 =
  5,478.4.
- **`G`** = 5,478.4 − 200,000/39 = **68,288/195** = 350.19. The lines sum: 14,656/39 − 128/5 =
  (73,280 − 4,992)/195 ✓.
- **TWR:** one inflow at the base, so 1 + TWR = 5,478.4 / (200,000/39), and TWR = **1,067/15,625** =
  0.068288.

## 7. P22, an interior five-session gap (USD; new)

**Set-up.** 03-03: `DEPOSIT` 1,000; `BUY` 100 × SYNG at 10.00. SYNG has no print on 03-10 to 03-14,
then 11.00 from 03-17.

- On 03-14, the last print is 03-07, with 5 missed sessions. The holding is `INSUFFICIENT_DATA` +
  `STALE_DATA` (`market-data` 5.2), and so is `V` on 03-14, 03-15 and 03-16.
- **TWR:** the only flow day is 03-03. The TWR reads `V(03-02)` = 0, `V(03-03)` = 1,000 and
  `V(03-31)` = 1,100, so it is **1/10**, `AVAILABLE` (Ruling 5.2). `G` = **100**.
- **Attribution:** it needs every day, so it is **`INSUFFICIENT_DATA` + `STALE_DATA`** (Rulings 9.5
  and 1.5). This is metamorphic check 11.3 #6 made concrete.

## 8. P14, everything in `R` (USD; part 3's events)

| Day | `β_D` | Price line |
|---|---|---|
| 03-05 | 10,000 | holding 30 × (11 − 9) = 60; trade results: the 100 bought at 10.40 against an 11.00 close, +60; the 50 at 11.60, −30; the sale at the close, 0. Total **90** |
| 03-10 | 10,090 | **100**, on 100 units |
| 03-12 | 10,190 | **60**, on 60 units |

- Line 1 = **250** = `G` (part 3's I-7 total).
- Lines 2, 3 and 8 are **exactly 0** (11.3 #4), and income, fees, taxes and financing are 0 here.
- `C_1` = TWR = **1/40**.

## 9. P13, a suppressed split position (part 2)

From the ex-date 03-03, SYNS is `SOURCE_CONFLICT` (part 2 P13-V2). Over (02-28, 03-04], `V(03-03)`,
`V(03-04)` and the position's `P⁰`/`P¹` are unavailable, so both attribution metrics are
**`INSUFFICIENT_DATA` + `SOURCE_CONFLICT`**, as the TWR and `G` are in part 2 (P13-R1).

## 10. Ratification

- **Ratified:** all **28** expected items were derived by hand, and agree with the calculator.
  - I-4 holds on every calendar day of every available window.
  - I-2 and I-3 hold against parts 1–3.
  - Every apportioned set sums to its total.
  - Every Cariño set reconciles to its TWR within 10⁻⁴⁹ internally.
- **Not ratified:**
  - that the engine passes;
  - the loader's expansion of SYNG (it must add no number);
  - structural assertions S4-1 to S4-8, which need an engine run.
- **For the PM:**
  - **Line identifiers.** The line identifiers are keyed by Ruling 9.2 position. If the engineer
    wants fixed names, the Quant would add them in a later convention id. They are not needed now.
  - **Next wiring step.** `cp3_golden/1.0-part4` is ready to wire once the engine computes
    attribution (CP3e).
