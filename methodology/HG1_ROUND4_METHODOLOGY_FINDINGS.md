# HG1 round 4 — methodology findings and specifications

**Author:** `quant_analyst`, worker `quant-01` (first engagement of this role in the project).
**Date:** 2026-09-06.
**Scope:** the five questions escalated by `reviews/gates/HG1_ROUND4_VERIFICATION.md` §6 and §7.1,
plus the long-open N-17/NF-5 reason-code question, plus anything else quantitative I found while
reading code that has never had a quantitative reviewer.
**Object under review:** `designs/hg1-prototype-v2/js/data.js` and
`designs/hg1-prototype-v2/js/surfaces/analytics.js` — a **design prototype with synthetic data**.
I judge the *method it embodies and the claims it makes on screen*, not its production-readiness.

**Gate state: HG1 is `REVISION_REQUIRED`, ACTIVE, UNAPPROVED.** Nothing in this document is an
approval, and nothing in it may be read as one. I do not approve methodology at a human gate
(`roles/quant_analyst.json`, `non_responsibilities`).

**I changed nothing in the prototype.** `src/`, `tests/` and `designs/` are outside my write
authority. Every fix below is a specification for `designer` to implement.

---

## 0. How the numbers in this document were derived

No JavaScript runtime is available in this environment, and reading a value off the
implementation would not be evidence about the method in any case. I re-implemented `data.js`'s
PRNG (`mulberry32`, seed `20260904`) and its entire return-generation chain independently in
Python: `methodology/verification/hg1_round4_replication.py`.

Run it with `python3 methodology/verification/hg1_round4_replication.py`. It reproduces every
value currently on the Analytics surface exactly:

| Quantity | Replication | On screen |
|---|---|---|
| `PERIOD_RETURN` | `0.075325` | `+7.5%` |
| `BENCHMARK_PERIOD_RETURN` | `-0.051069` | `−5.11%` |
| `BETA` | `0.931085` | `0.93` |
| `ALPHA_ANNUAL` | `0.120868` | `+12.1%` |
| `VAR_95` | `-0.013424` | `-1.3%` |

That agreement is what licenses the rest of this document. **It is verification tooling, not a
golden fixture** — it derives values from a second restatement of the same generator, which
proves only that the two restatements agree. It must not be promoted to `methodology/fixtures/`.
Independent hand-derived fixtures for the production engine are a separate deliverable and do not
exist yet.

---

## 1. Q1 — SML/CAPM window and frequency coherence

### 1.1 What the code actually computes

| Quantity | Source | Window | Frequency | Estimator | Compounding |
|---|---|---|---|---|---|
| `BETA` | `data.js:163` | trailing 252 trading days (`i1y = 504−252`) | **daily** | `covariance(pr1y, br1y) / variance(br1y)` — population moments (÷N, `data.js:38-53`) | n/a (dimensionless) |
| `ALPHA_ANNUAL` | `data.js:164-165` | **same** 252 daily observations | **daily** | `(mean(pr) − rf_d) − β·(mean(br) − rf_d)`, then `× 252` | **arithmetic** |
| `PERIOD_RETURN` | `data.js:159` | **same** 252-day window | **daily** inputs | index ratio `I_T / I_{t0}` | **geometric** |

**So the estimation *window* and *frequency* are in fact homogeneous.** All three are trailing 252
daily observations. The chart subtitle `Trailing 1Y · Daily returns`
(`analytics.js:287, 317, 373`) is an accurate description of the estimator. The PM's §6.1
observation was correct that something is wrong, but the defect is not the one it looked like.

### 1.2 Ruling — three defects, in descending severity

**D1.1 — The beta caveat's observation count is false, and contradicts the Proof Packet on the
same screen. CONFIRMED DEFECT.**

`data.js:474` reads: *"24 monthly-equivalent observations in the current window (36 preferred
minimum)."* The window contains 252 daily observations. In monthly-equivalent terms that is
**12**, not 24. Twenty-four monthly-equivalents is the size of the **full 504-day generated
dataset**, which is a window no displayed statistic uses.

Meanwhile the Proof Packet built for the same claim (`data.js:767`) records
`period: "Trailing 1Y"`, `frequency: "Daily"`, `observations: pr1y.length` — i.e. **252**. Both
strings are reachable from the same beta cell. The interface states two different observation
counts for one estimate. Under §13.3, observation count is a *required* disclosure for every
benchmark-dependent calculation; here it is required, present twice, and inconsistent.

**D1.2 — The compounding basis is genuinely not homogeneous, and this is the real "two bases
presented as one" problem. CONFIRMED DEFECT.**

`ALPHA_ANNUAL` is an **arithmetic** daily mean scaled by 252. `PERIOD_RETURN` is a **geometric**
compounded return. They are presented adjacent in `metric.sml.formatted` (`data.js:565`) as
`β 0.93 · Return +7.5% · α +12.1%`, which reads as one coherent set. The size of the gap between
the two conventions, on this data:

- portfolio: arithmetic `mean(pr1y) × 252 = +8.2415%` vs geometric `+7.5325%` — **71 bp of
  variance drag**;
- benchmark: arithmetic `−4.4629%` vs geometric `−5.1069%` — **64 bp**.

This is not a rounding artefact; it is a different definition of "the return over the year." A
professional reader who takes `+12.1%` as the vertical distance between `+7.5%` and the line will
not reproduce it (see §2.2 — it is off by 11 bp for exactly this reason).

**D1.3 — Daily frequency for cross-market beta and correlation is contrary to PRD §14, and the
deviation is nowhere recorded. CONFIRMED DEFECT (method, not just labelling).**

§14 is explicit:

> Default professional analytical setting: lookback: 3 years; frequency: weekly …
> **Weekly should be the default for cross-market covariance/correlation/beta to reduce
> non-synchronous market-close noise.**
> **Every metric must state the actual window/frequency used.**

The prototype uses 1Y daily for beta, correlation, tracking error and risk contribution. US,
Hong Kong and Mainland China sessions do not overlap; a "daily return" for a US holding and a
"daily return" for an A-share on the same calendar date are measured over disjoint intervals.
Sampling covariance at a frequency shorter than the non-synchronicity interval biases estimated
covariances toward zero — the Epps effect — which biases **beta downward** and **cross-market
correlations downward** for exactly the sleeve pairs this product exists to analyse.

**This is why §14 names weekly, and it is the one methodology default in the PRD that is
specifically about being cross-border.** Deviating from it is permissible, but only as a recorded
decision with a stated reason, not silently.

A separate and important honesty point: **the synthetic generator cannot exhibit this bias.**
`data.js:99-113` builds all four sleeves from a single contemporaneous `marketFactor[i]` on the
same index. The dataset assumes perfectly synchronous cross-market closes — precisely the
assumption P10/NFR-008 and §11.2 say is false. So the daily estimator looks well-behaved here and
will not on real data. A prototype whose data removes the product's hardest problem should not be
used as evidence that the method handles it.

### 1.3 What the surface must state

For **every** benchmark-dependent figure (beta, alpha, tracking error, benchmark-relative return,
the SML chart), §13.3 requires all seven of these, and they must be identical wherever the same
estimate appears:

1. benchmark (name and, once selectable, the user's selection);
2. calculation window, as explicit start and end dates — not "Trailing 1Y";
3. return frequency;
4. **observation count, as one number in the frequency actually used**;
5. reporting-currency treatment;
6. calculation timestamp;
7. methodology version.

Required literal changes:

- **Delete** `"24 monthly-equivalent observations in the current window (36 preferred minimum)"`.
  Replace with the true count and the true minimum in the same unit, e.g.
  `"252 daily observations (2025-09-04 to 2026-09-03). Minimum for this metric: 104 weekly / 500 daily."`
  A count and a threshold expressed in different units is not a disclosure.
- **The subtitle must carry the compounding basis, not only the frequency.** Where an
  arithmetic-annualized quantity and a geometric period return appear in one unit, say so:
  `Trailing 1Y · daily returns · return compounded geometrically · alpha annualized arithmetically (×252)`.
  If that is too long for the chart, the two quantities may not share one subtitle line — split
  the unit.
- **Beta and alpha must not be estimated at a frequency the product has not justified.** Either
  re-estimate at §14's weekly default, or record a decision that daily is used and state the
  non-synchronicity limitation on the metric itself. `designer` cannot choose this; see §9.

### 1.4 Data sufficiency for beta — the declared threshold is unmeetable by construction

`methodology.beta` (`data.js:662`) declares `minimumObservations: "36 monthly-equivalent
observations preferred"` while declaring `frequency: "Daily"` and `lookback: "Trailing 1 year"`.
A trailing 1-year window contains at most 12 monthly-equivalents. **Under its own declared
threshold this metric can never leave `LIMITED`.** A threshold that cannot be met is not a
threshold; it is a permanent caveat, and a caveat that is always on carries no information —
the same argument PD-0006 makes for `STALE_DATA`.

Threshold I set (this is mine to set under PD-0006 and PD-0007, both of which explicitly reserve
thresholds to this role):

| Metric | Frequency | `AVAILABLE` | `LIMITED` | `INSUFFICIENT_DATA` |
|---|---|---|---|---|
| Beta, correlation, tracking error (cross-market) | weekly (§14 default) | ≥ 156 weekly obs (3Y) | 52–155 weekly obs | < 52 weekly obs |
| Beta, correlation, tracking error | daily (if a deviation is recorded) | ≥ 750 daily obs (3Y) | 250–749 daily obs | < 250 daily obs |

Derivation, so a reviewer can check rather than trust it: §14 sets the professional default at
3Y/weekly, which is 156 observations; a one-year weekly sample (52) is the shortest window over
which an OLS slope against a benchmark is conventionally quoted at all, and below one year the
standard error of beta on weekly data exceeds a range that would change the conclusion — which is
PD-0006's own definition of `LIMITED`. The daily row is the same calendar spans at daily
frequency. Under this table the prototype's 252 daily observations are `LIMITED` — the state it
already shows — but for a stated, meetable reason.

---

## 2. Q2 — which concept the SML chart actually shows

### 2.1 What the code actually implements

`data.js:344` — `SML_LINE = { slope: BENCHMARK_PERIOD_RETURN − RF_ANNUAL, intercept: RF_ANNUAL }`.

The line is therefore `y(β) = R_f + β · (R_b,realized − R_f)`, built from the **realized**
benchmark return over the window (−5.11%), not from any expectation. The points
(`data.js:337-343`) are `(β_i, R_i,realized)` using realized geometric 1Y returns.

Against the owner's four-way distinction:

| Concept | Implemented? |
|---|---|
| 1. Theoretical CAPM expected return | **No** — and it must never be. It would be a forecast (P6). |
| 2. Historical / ex-post CAPM comparison (realized market line) | **Yes. This is what the chart is.** |
| 3. Regression Jensen's alpha | Yes, separately, as `ALPHA_ANNUAL` — and it is the number the chart *annotates itself with*. |
| 4. Realized return minus CAPM-implied return | **Computed nowhere.** It is the chart's own vertical distance and no code produces it. |

### 2.2 Ruling — the chart annotates its vertical distance with a number that is not that distance. CONFIRMED DEFECT.

At `BETA = 0.931085`, the ex-post line implies `0.045 + 0.931085 × (−0.096069) = −0.044448`.

- The true vertical distance from the portfolio point to the line: `0.075325 − (−0.044448) =` **`+0.119773` (+11.98%)** — concept 4.
- The number `analytics.js:369-377` passes into `alphaCallout`, and that `data.js:565-568`
  interpolates into the SML claim's own text as *"the vertical distance from the SML line"*:
  `ALPHA_ANNUAL =` **`+0.120868` (+12.09%)** — concept 3.

**They differ by 11.0 bp**, because concept 3 is an arithmetic-mean estimator scaled by 252 and
concept 4 is a difference of geometric returns (§1.2, D1.2). The chart therefore labels a
geometric distance with an arithmetic quantity and calls them the same thing. Both numbers are
individually defensible; asserting they are the same number is not.

For the record, the same gap for the sleeve points, none of which is displayed anywhere:
US `−4.35%`, HK `+23.11%`, CN `+31.09%`.

### 2.3 Ruling on labelling — this is a P6 problem, not a wording preference

Two strings are currently outside what P6 permits, and I am exercising the veto in
`roles/quant_analyst.json` (*"a statistic presented as a forecast rather than a historical
description"*):

- `data.js:485` (`metric.alpha.conclusionQuick`): *"returns were below what the benchmark
  relationship **would predict**."* "Predict" is forecasting language for a quantity that
  describes a closed historical window. **Must be replaced.**
- `data.js:568` (`metric.sml.explanationSimple`): *"what a portfolio with this beta **'should'
  have returned**."* Scare quotes do not remove the normative claim, and a reader carries
  "should" forward as an expectation.

Note the existing `metric.sml.caveat` (`data.js:570`) is already correct and should be kept.

### 2.4 Exact wording the surface must adopt

- **Chart title** — replace `"Portfolio vs. Market (SML / CAPM)"` (`analytics.js:342`) with:
  **`Realized return vs. beta — ex-post market line (trailing 1Y)`**
  The phrase "Security Market Line" alone may not be used as a title. If it is retained anywhere
  it must be qualified as *ex-post* in the same visual unit.
- **X axis:** `Beta vs. MSCI ACWI — trailing 1Y, daily returns, 252 observations`
- **Y axis:** `Realized total return, trailing 1Y, USD, compounded`
- **Line annotation (required, adjacent to the line, not in a tooltip):**
  `Ex-post market line: R_f + β × (realized benchmark return − R_f). R_f = 4.5% p.a.; realized`
  `benchmark return = −5.11%. The line slopes down because the benchmark returned less than the`
  `risk-free rate over this window. This describes what happened in this window; it is not an`
  `expected return and not a forecast.`
- **Vertical-distance annotation:** it must display **concept 4** — `+11.98%` — labelled
  `realized return minus ex-post market-line return`. The regression Jensen's alpha
  (`+12.09%`) moves to the side panel as its own claim with its own stated basis
  (`OLS on 252 daily excess returns, annualized arithmetically ×252`). **One number may not
  annotate the other.**
- **Replacement for `metric.alpha.conclusionQuick`:**
  `Over this window, the portfolio returned more than the benchmark relationship at this beta`
  `accounts for.` (drop "predict")
- **Replacement for `metric.sml.explanationSimple`'s first clause:**
  `The line shows the return a portfolio at each beta would have needed, over this window, to`
  `match what the benchmark actually delivered relative to the risk-free rate.` (drop "should")

### 2.5 One thing the code gets right, recorded so it is not "fixed"

The downward slope is correct and must not be changed. It follows from a realized market premium
of `−5.11% − 4.5% = −9.61%`. Presenting an ex-post market line with a negative realized premium as
downward-sloping is the *honest* rendering; forcing it upward would be the defect. The sleeve
betas at `data.js:340-342` use `ρ·σ_i/σ_b`, which is algebraically identical to `cov/var` — correct,
not an approximation. And `BETA` computed on raw rather than excess returns is correct here
because `R_f` is a constant series and therefore drops out of the slope.

---

## 3. Q3 — VaR sign convention

### 3.1 What the code actually computes

`data.js:170` — `VAR_95 = percentile(pr1y, 0.05)`, where `percentile` (`data.js:59-63`) is
`sorted[floor(p·(n−1))]` — a **lower-order-statistic estimator with no interpolation**.

At `n = 252`: `floor(0.05 × 251) = 12` → the **13th smallest** of 252 daily returns =
`−0.013424`. Neighbours: `srt[11] = −0.015444`, `srt[13] = −0.012923`.

Three facts a registry entry has to pin down and none of which is currently written anywhere:

- **Realized exceedance is 13/252 = 5.16%, not 5.00%.** The estimator's chosen order statistic is
  itself part of the answer.
- A linearly interpolated (Hyndman–Fan type 7) 5% quantile would be `−0.013148` — **2.8 bp
  different**. Which one is used is a convention, and P12 makes the convention part of the method.
- `data.js:170` feeds this from `portfolioReturns`, which contains **no FX** (see §4.1). A VaR for
  a cross-border portfolio that excludes currency risk is not this portfolio's VaR.

### 3.2 Ruling — I choose the positive loss-magnitude convention for display

Both conventions are defensible; the product must hold exactly one, and the label already commits
it. "VaR" is a loss noun; every mainstream quotation of it ("VaR is 1.3% of portfolio value") is a
positive magnitude. Rendering `-1.3%` under the label `1-Day 95% VaR`, in a strip beside `+7.5%`
and `−5.11%` which *are* returns, invites the reader to parse it as a return. That is the ambiguity
the question exists to close.

**Ruling:**

- **The registry quantity is the signed return quantile**, `q_{0.05}`, and stays signed and
  negative internally. It must stay signed because it is a quantile of the return distribution and
  must remain composable with the return series and with expected shortfall.
- **The displayed quantity is `VaR_{95,1d} = −q_{0.05}`, a non-negative magnitude**, rendered with
  **no sign character and no directional colour** (`directional` stays `false` on this claim —
  the prototype already gets that right, `data.js:528`).
- **The Proof Packet shows both, each named**, so the two never have to be inferred from each
  other.

### 3.3 Exact on-screen rendering

```
1-day 95% VaR          1.3%
                       of portfolio value
Historical simulation, 252 daily returns (2025-09-04 to 2026-09-03).
On 5% of days in this sample the one-day change was worse than −1.3%;
13 of 252 days (5.2%) were at or below it. Describes this sample, not a
limit on future loss.
```

Rules that go with it:

- The words "loss" or "of portfolio value" must appear in the same visual unit as the number.
  A bare `1.3%` under a "VaR" label is as ambiguous as `-1.3%` was.
- The realized exceedance count must be shown at Investor depth or deeper. It is the one number
  that makes the estimator legible.
- **No `−` and no red.** VaR is a risk characteristic, not a directional result.
- Never render VaR as a currency figure without also showing the percentage and the portfolio
  value it was applied to.

### 3.4 Edge case that must be specified, because the convention creates it

If `q_{0.05} ≥ 0` — possible in a strongly trending window — then `−q_{0.05} ≤ 0` and a "loss
magnitude" is negative or zero. Rendering `0.0%` would be a fabricated fallback and is forbidden
by §32 outright. **Required behavior:** suppress the magnitude and state
`No one-day loss threshold at 95% confidence in this sample — the worst 5% of days in this window
were not losses.` Sufficiency stays `AVAILABLE` (the metric computed fine); this is a rendering
branch, not a state.

### 3.5 Registry entry — `methodology.var` (currently empty, AC-17)

| §33 field | Value |
|---|---|
| metric name | 1-day Value at Risk, 95% confidence |
| human definition | The one-day loss magnitude that was exceeded on 5% of days in the observation window. |
| formula | `q = sorted(r)[floor(0.05·(n−1))]`; `VaR₉₅ = −q`, reported for `q < 0`. |
| annualization convention | **None. VaR is not annualized.** Scaling by √h is forbidden for this metric in V1 — it assumes i.i.d. returns the cross-border series do not satisfy. |
| data inputs | Daily reporting-currency portfolio returns **including FX translation** (see §4). |
| minimum observations | Tail count `k = floor((1−c)·n) ≥ 10` ⇒ `AVAILABLE`; `5 ≤ k < 10` ⇒ `LIMITED`; `k < 5` ⇒ `INSUFFICIENT_DATA`. At `c = 95%`: `n ≥ 200`, `100 ≤ n < 200`, `n < 100`. Derivation: an empirical quantile is a single order statistic; below ~10 observations beyond it, its sampling error exceeds the difference between adjacent confidence levels, so the number stops distinguishing 95% from 90%. |
| frequency | Daily |
| lookback | Trailing 252 trading days |
| benchmark dependency | None |
| risk-free rate dependency | None |
| missing-data handling | A day missing a price on **any** constituent market is excluded from the sample entirely; it is never carried forward, because a zero return on a closed market is a fabricated observation that shrinks the tail. Excluded-day count is a required disclosure. |
| FX treatment | Returns are reporting-currency returns; FX moves are inside the distribution, not stripped out. |
| corporate-action treatment | Adjusted at ex-date |
| known limitations | Historical simulation reproduces only losses that occurred in the window. It has no view on losses larger than the worst observed. It is not a loss limit, not a maximum, and not a forecast. With 252 observations the estimate rests on ~13 tail points and moves visibly when one of them rolls out of the window. |
| implementation version | *(engine's, at implementation time)* |

**Recommend, do not require:** show expected shortfall (mean of the 13 worst = `−0.017892`,
i.e. `1.8%`) beside VaR. It is materially more stable at this sample size. Whether to add a metric
is product scope, not mine — §9.

---

## 4. Q4 — FX attribution, arithmetic vs geometric

### 4.1 The finding the arithmetic/geometric framing does not capture, and it is the larger one

**`PERIOD_RETURN` contains no FX at all.** `data.js:117-122` builds `portfolioReturns` as the
weighted sum of the four **sleeve** series. `fxHKD` and `fxCNY` (`data.js:124-125`) are generated
afterwards and **are never applied to it**. The FX series enter exactly one place:
`FX_ATTRIBUTION_PCT` (`data.js:352`).

So `PERIOD_RETURN` is a **local-currency** blend return. But:

- `metric.return.1y.explanationSimple` (`data.js:407`) says it is *"the total change in your
  portfolio's reporting-currency value … including price moves **and FX effects**."* False.
- `analytics.js:194` then derives the local leg as `retClaim.value − fxClaim.value`, i.e. it
  *subtracts* an FX effect from a total that never contained one.

Quantified at the actual values:

| Quantity | Value |
|---|---|
| True local-currency blend return (what `PERIOD_RETURN` is) | **+7.5325%** |
| True reporting-currency return (FX applied daily, then compounded) | **+7.2212%** |
| True total FX effect | **−31.13 bp** |
| Prototype's displayed "total return" | +7.5325% — **overstated by 31 bp**, and mislabelled |
| Prototype's `FX Attribution` figure | −28.75 bp — **approximately right** |
| Prototype's derived "local-market" leg | **+7.8201% — overstated by 28.8 bp** |

**The sign of the correction is inverted.** The FX drag was subtracted from a figure that was
already the local return, which pushed the local leg *up* by the size of the drag, instead of
pushing the total *down*. Both legs of the waterfall are wrong; the FX bar is the only correct
one. This is not an approximation error — it is an identity error, and it is ~16× the size of the
arithmetic/geometric residual the question asked about.

### 4.2 The residual the question asked about, quantified

Cross-currency returns compound: `R_base = (1+R_local)(1+R_fx) − 1 = R_local + R_fx + R_local·R_fx`.
The third term is the interaction. Arithmetic subtraction absorbs it silently.

At the actual values in `data.js`:

| Sleeve | Local | FX | Arithmetic sum | Exact geometric | **Interaction** | Weighted by sleeve weight |
|---|---|---|---|---|---|---|
| HK (w = 0.30) | +17.2564% | −1.9302% | +15.3262% | +14.9931% | **−33.31 bp** | −9.99 bp |
| CN (w = 0.20) | +27.8779% | +1.4576% | +29.3355% | +29.7418% | **+40.63 bp** | +8.13 bp |
| **Portfolio total** | | | | | | **−1.87 bp** |

**The honest reading, and the owner should have it in this exact form:** at the portfolio level the
residual is **1.87 bp — immaterial**. But that is not because the term is small. It is **33 bp and
41 bp at the sleeve level**, and the portfolio number is small only because the two sleeves' terms
have opposite signs and nearly cancel. **That cancellation is a property of this synthetic
dataset, not of the method.** A one-off dataset in which an error nets out is the weakest possible
evidence that the error is safe to keep.

At realistic cross-border magnitudes, from the same script:

| Local return | FX move | Interaction |
|---|---|---|
| +10% | +2% | 20 bp |
| +20% | +5% | 100 bp |
| +30% | +8% | **240 bp** |
| −25% | +10% | **−250 bp** |
| +15% | −7% | −105 bp |

A CNY or HKD sleeve with a 25–30% local move and a 7–10% currency move — entirely ordinary over a
multi-year window — produces an interaction term of **2 to 2.5 percentage points**. Absorbing that
into the local-market bar would mean telling a user their securities did 2.4 points better or
worse than they did. **The term must be represented explicitly, not absorbed.**

### 4.3 Ruling — geometric/exact, with the interaction shown, never arithmetic subtraction

**Sleeve level (this is the definition; it is exact and needs no smoothing):**

For sleeve `i` over `[t₀, t₁]`, with `S` quoted as reporting-currency units per unit of local
currency:

```
R_local,i = (P_i(t₁) + income_i) / P_i(t₀) − 1        (local currency, income reinvested, §8.4)
R_fx,i    = S_i(t₁) / S_i(t₀) − 1
R_base,i  = (1 + R_local,i)(1 + R_fx,i) − 1           EXACT — this is the definition
          = R_local,i + R_fx,i + R_local,i · R_fx,i
```

The third term is the **currency/market interaction**. It is named, it is displayed, it is never
folded into either of the first two.

**Portfolio level.** Do **not** aggregate the sleeve identity by weighted sum: over a multi-period
window `Σ wᵢ·R_base,i ≠ R_base,P` compounded, and closing that gap requires a named linking
algorithm (Cariño, Menchero, Frongello). Choosing one is a real decision that V1 should not make
implicitly. Instead:

```
R_local,P = compounded return of the ledger valued at each date's LOCAL prices,
            translated at the FIXED t₀ FX rate                       (FX held constant)
R_base,P  = compounded return of the ledger valued at each date's local prices,
            translated at EACH DATE's FX rate                        (§8.3)
FX effect = R_base,P − R_local,P                                     (exact by construction)
```

Both legs are computable from the ledger alone. The FX effect defined this way is exact and leaves
**no residual**, because the compounding interaction is inside it by construction. That is the
correct trade: rather than a residual bar nobody can interpret, the FX bar carries an honest name.

**§8.3 compliance is not optional here:** *"never retroactively apply today's FX rate to historical
portfolio values."* The `R_local,P` leg holds FX at the **period-start** rate, not today's. Holding
it at today's rate would be the violation.

### 4.4 What the waterfall must contain to be arithmetically honest

The owner asked for `local-market return → FX impact → reporting-currency return`. Minimum
contents:

1. **Bar 1 — Local-market return.** Label must name the FX basis:
   `Local-market return (FX held at 2025-09-04 rates)`. It may **never** be derived by subtraction
   from the total. It is computed from the ledger.
2. **Bar 2 — FX effect.** `FX effect (currency translation, incl. compounding interaction)`.
   The parenthetical is required — without it the bar makes a claim of purity it cannot support.
3. **Bar 3 — Reporting-currency return.** The number the rest of the product calls "the return."
   Bars 1 + 2 must equal Bar 3 **exactly**, to full displayed precision. If they do not, the
   surface has a defect, not a rounding issue.
4. **A stated per-sleeve breakdown at Investor depth or deeper**, showing for HK and CN separately:
   local, FX, interaction, base. The interaction is 33–41 bp per sleeve here and is invisible at
   portfolio level. Hiding it is how a user concludes their currency exposure is smaller than it is.
   `analytics.js:193` currently notes no per-sleeve split is exposed by `data.js` — that is the gap
   to close.
5. **An explicit statement of what is NOT in the decomposition.** §8.4 names five components:
   local security-price effect, FX effect, income/dividends, fees, taxes. V1 shows two. The other
   three must be named as excluded, or a user reading a two-bar waterfall will believe it is
   complete. Dividends in particular exist in this very ledger (`TRANSACTIONS`, seven `DIVIDEND`
   rows) and are in no bar.
6. **Weights basis.** State that sleeve weights are beginning-of-period, in reporting currency.

### 4.5 Also wrong, in the same area

`metric.fxAttribution.professionalDetail` (`data.js:459`) reads: *"Computed as weighted
local-currency sleeve return **minus** weighted reporting-currency sleeve return."* The code
(`data.js:352`) computes `Σ wᵢ · R_fx,i`, which approximates **reporting minus local**. The
documented formula is the **negative** of the implemented one. A reader reconciling the sign would
conclude currency *added* 29 bp when the product means it removed it.

### 4.6 Registry entry — `methodology.fxAttribution` (currently empty)

Key fields, in §33 order, abbreviated to what differs from the pattern above:

- **formula:** sleeve level `R_base = (1+R_local)(1+R_fx) − 1`, interaction reported as
  `R_local · R_fx`; portfolio level `FX effect = R_base,P − R_local,P` with `R_local,P` translated
  at the period-start rate.
- **annualization convention:** none — the decomposition is reported over the stated window and is
  never annualized, because annualizing the three legs separately breaks the identity.
- **minimum observations:** requires a complete FX series over the window. Any date missing an FX
  print ⇒ that date is excluded and the exclusion count disclosed; > 5% of dates missing ⇒
  `LIMITED`; > 20% ⇒ `INSUFFICIENT_DATA` with `MISSING_FX_HISTORY`.
- **FX treatment:** the WM/Reuters-equivalent daily fixing for the reporting currency pair,
  **one fixing time for all three markets**, stated on the metric. Which fixing time is a decision
  I flag in §9 — it interacts with the non-overlapping-session problem and it is not a free choice.
- **known limitations:** decomposes price and currency only. Income, fees and taxes (§8.4) are not
  attributed in V1. The interaction term is real and is reported inside the FX leg at portfolio
  level and separately at sleeve level.

---

## 5. Q5 — "not degraded"

### 5.1 What the code says

`data.js:450`, `metric.benchmarkRelative.caveat`, verbatim:

> "One input market (Mainland China A-shares) is priced as of a stale print; the comparison
> remains computable and **is not degraded** — see the freshness indicator."

### 5.2 Ruling — this is a comparability question, not a sufficiency question, and the two claims must be split

**First, the part that is right, and must not be broken while fixing the rest.** The sufficiency
state is correct. `AVAILABLE` + `STALE_DATA` is exactly what PD-0006 established, for exactly the
right reason: cross-market prices are never simultaneously real-time (P10/NFR-008), so demoting
every stale metric to `LIMITED` would fire on nearly everything and stop carrying information.
**I am not reopening PD-0006 or PD-0007, and no new sufficiency state is needed or permitted here.**

**Second, "remains computable" is true.** Keep it.

**Third, "is not degraded" is not defensible for this metric, and I am ruling it out.**

The reasoning a reviewer can check: `metric.benchmarkRelative` is a **two-leg difference**,
`R_portfolio − R_benchmark`. The claim it makes is that the difference is attributable to the
portfolio. That claim requires both legs to be measured over the **same interval**. Here the
portfolio's A-share leg stops at 2026-09-02 15:00 CST while the benchmark and the other legs run
to 2026-09-03. Whatever A-share-correlated market movement occurred in the interval between them
is in the benchmark leg and not in the portfolio leg. The number therefore contains a component
that is not portfolio performance — that is a degradation, and it is a degradation of a property
that has no representation anywhere in the current model.

**The distinction is between metric classes, and that is what makes it a real dimension rather
than a wording tweak:**

| Metric class | Effect of one stale input leg |
|---|---|
| Single-leg level or return (total value, portfolio return, exposure, concentration) | Computable, undegraded, timing disclosed. **D3.2's rule holds as written.** |
| **Two-leg comparison** (benchmark-relative return, tracking error, beta, correlation, excess return, any scenario-vs-actual delta) | Computable, but the difference includes a timing gap that is not a portfolio effect. **Temporal comparability is limited.** |

**Naming:** the dimension is **temporal comparability**. It is a property of *comparison* metrics.
It is **not** a fourth sufficiency state, it is **not** a new reason code, and it must not be added
to either enum. It belongs on the D5 freshness axis, which is already orthogonal to sufficiency by
PD-0006's own ruling — this is the axis doing one more job it is already shaped for.

### 5.3 Exact wording

Replace `data.js:450` with:

> `Calculation available. One input market (Mainland China A-shares) is priced at its most recent`
> `available close, 2026-09-02 15:00 CST, which is behind this comparison's as-of date. The`
> `portfolio and benchmark legs are therefore not measured at the same instant, and the difference`
> `shown includes that timing gap. See the freshness indicator.`

Every clause is checkable: "calculation available" restates the sufficiency state; "most recent
available close" is a stronger and more accurate claim than "stale print" (see §5.4); "not measured
at the same instant" is the fact; "includes that timing gap" is what follows from it. The phrase
"is not degraded" does not appear, and neither does any word implying the number is wrong — it is
not wrong, it is measured across a seam.

### 5.4 A related correction the owner's finding did not reach

`data.js:361` records the CN A-share axis as `STALE` with the note *"Shanghai/Shenzhen closed for a
local holiday on 2026-09-03; no newer print exists yet."*

**By a session-based definition this input is not stale at all.** Zero A-share trading sessions have
elapsed since that print. It is the latest close that exists, and it is the correct price. A
clock-based staleness rule labels a market "stale" for being on holiday, which will fire on every
Mainland China holiday period — a state that is on by calendar and off by nothing is noise.

**Threshold I set (this is the staleness threshold PD-0006 explicitly deferred to this role, and
its "Known limitations" section flags as undefined):** staleness is measured in **local trading
sessions of the market that priced the input**, never in wall-clock time.

| Sessions of that market elapsed since the input's print | Freshness | Sufficiency effect |
|---|---|---|
| 0 (latest available close; market has not traded since) | `CURRENT_CLOSE` | none — `AVAILABLE`, no `STALE_DATA` |
| 1 | `STALE` | none — `AVAILABLE` + `STALE_DATA` |
| 2–4 | `STALE` | `LIMITED` + `STALE_DATA` |
| ≥ 5 | `STALE` | `INSUFFICIENT_DATA` + `STALE_DATA` |

Under this rule the prototype's CN A-share input is `CURRENT_CLOSE`, and the temporal-comparability
disclosure in §5.3 is still required, because comparability depends on the **instants**, not on
whether the market had an opportunity to trade. **These two things are independent and that is the
whole point of the question.** A benchmark-relative figure can be built from perfectly fresh inputs
and still be measured across a seam, whenever the markets close at different times — which,
between New York, Hong Kong and Shanghai, is always.

### 5.5 Contradiction with an accepted contract — escalated, not resolved

`designs/FEATURE_DESIGN.md` §D3.2, `AVAILABLE` + `STALE_DATA` row, states:

> "This state must be **visually indistinguishable from plain `AVAILABLE` at the value's rendering
> unit, because it is not degraded** — the number is exactly as computable and exactly as
> trustworthy as any other `AVAILABLE` value; only its input timing differs…"

That is **correct for single-leg metrics and wrong for two-leg comparisons**, per §5.2. `data.js:450`
is not an invention by the designer; it is a faithful application of D3.2's own justification.

I am **not** amending D3.2. The narrowest correct change is to scope its justification clause to
non-comparative metrics and add a comparability disclosure for comparison metrics on the D5 axis.
Whether D5's existing shape can carry that, or whether the claim object needs a new field, is a
design and product-contract decision belonging to `designer` and `product_manager`. **Flagged, and
I stop here** — this is the one place in this document where correct methodology and an accepted
artifact genuinely disagree.

---

## 6. N-17 / NF-5 — which reason codes may pair with which sufficiency states

Both independent reviewers raised this and it has never been answered. PD-0006's second amendment
already fixes the outer rule and I am not reopening it: the five non-`STALE_DATA` codes imply a
non-`AVAILABLE` state; `STALE_DATA` does not. What was left open is the finer pairing, which is a
methodology question because it turns on what each code says about *sufficiency*.

| Reason code | `AVAILABLE` | `LIMITED` | `INSUFFICIENT_DATA` | Reasoning |
|---|---|---|---|---|
| `STALE_DATA` | **yes** (routine) | yes, at 2–4 sessions (§5.4) | yes, at ≥5 sessions | Only code whose severity is a continuum. Threshold in §5.4. |
| `UNSUPPORTED_ASSET` | no (PD-0006) | **no** | **yes, only** | An instrument is inside a method's domain or it is not. There is no weak version of "the factor model does not cover this." |
| `MISSING_BENCHMARK` | no (PD-0006) | **no** | **yes, only** | A benchmark-dependent metric with no benchmark is undefined, not weak. P4 independently forbids the judgment without a reference point. |
| `MISSING_COST_BASIS` | no (PD-0006) | **yes, aggregates only** | **yes, at the level the input is absent** | Undefined for the position; an aggregate over the priced remainder is genuinely computable. |
| `MISSING_FX_HISTORY` | no (PD-0006) | **yes, aggregates only** | **yes, at the level the rate is absent** | Same shape as cost basis. |
| `CALCULATION_ERROR` | no (PD-0006) | **no** | **yes, only** | Not a statement about data at all. A value from a computation that errored may not be shown at any confidence. |

**Two rules that go with the table, and they are the part that actually binds:**

**R1 — the aggregate-`LIMITED` rule.** `MISSING_COST_BASIS` and `MISSING_FX_HISTORY` may accompany
`LIMITED` on an aggregate **only if the affected weight is stated as a number in the same visual
unit as the value.** "Some positions are excluded" is not a disclosure; "positions representing
4.8% of invested value are excluded" is. Without the weight, a reader cannot tell a rounding
difference from a hole. `exposure.currency` (`data.js:581`) currently uses `LIMITED` +
`MISSING_FX_HISTORY` and describes the result as *"directionally illustrative"* with no weight —
legitimate state, insufficient disclosure.

Same rule for `UNSUPPORTED_ASSET`: when part of a portfolio is unsupported but the aggregate is
computable on the remainder, the aggregate is `LIMITED` with **no** `UNSUPPORTED_ASSET` code and a
stated excluded weight; the code sits on the excluded instrument's own claim.
`2800.HK` is handled correctly in kind (`data.js:625`) and is 0.46% of holdings — but no aggregate
anywhere states that 0.46% is excluded from its risk figures.

**R2 — `CALCULATION_ERROR` is an engine fault, not a UI state.** It means the deterministic engine
failed. It should be observable and alertable, and it should be rare. `CONTRIBUTION_TO_RISK`'s CN
segment (`data.js:331-333`) uses it to model a demo withholding with the invented explanation
*"residual reconciliation failed for this segment during the last recompute."* In a prototype that
is a demonstration; if that pattern reaches production it teaches users that a computation failure
is a normal thing to see. `MISSING_FX_HISTORY` or a sufficiency-only `INSUFFICIENT_DATA` would
demonstrate the same rendering without asserting an engine fault.

---

## 7. Findings nobody asked about

The feedback log is a floor, not a ceiling. These are ordered by severity. Every one is verifiable
from the replication script.

### 7.1 SEVERE — four hardcoded conclusion strings contradict the numbers they sit beside

This is the P1 boundary failing in the direction P1 exists to prevent: the explanation layer is
asserting conclusions rather than reading computed values, and in four cases the assertion is the
**opposite** of what the deterministic number says.

| Location | String | Computed value | Verdict |
|---|---|---|---|
| `data.js:475` `metric.beta.conclusionQuick` | *"Your portfolio has historically moved **more** than the market."* | `BETA = 0.9311` | **FALSE.** Beta < 1: it moved *less*. The word "more" sits directly above the numeral `0.93`. |
| `data.js:724` `insight.drawdown.deeper` | *"maximum drawdown this period (−13.1%) was **deeper** than the benchmark's (−13.8%)"* | portfolio `−0.1307`, benchmark `−0.1378` | **FALSE.** The portfolio's drawdown was **shallower**. The sentence interpolates both numbers and contradicts itself in one line. Classed `judgmentClass: "Fact"`. |
| `data.js:729` `insight.correlation.hkCluster` and `data.js:544` `metric.correlation.conclusionQuick` | *"HK and Mainland China sleeves show **high** historical correlation, reducing the diversification benefit"* / *"move together strongly"* | `ρ(HK,CN) = 0.203` | **FALSE, and backwards.** 0.20 is the **lowest** equity-pair correlation in the matrix (US–HK 0.48, US–CN 0.37). The claim that "bonds diversify both" is also unsupported: HK–bond 0.20, CN–bond 0.19 — indistinguishable from HK–CN itself. |
| `data.js:551` `metric.contributionToRisk.conclusionQuick` | *"Hong Kong and Mainland China sleeves contribute **the most** to overall portfolio risk"* | US 40.0%, HK 38.6%, CN 20.0%, bonds 1.3% | **Unsupported.** The single largest contributor is the **US** sleeve. |

The full 1Y daily correlation matrix, for the record:

```
        US     HK     CN    BOND   BENCH
US     1.00   0.48   0.37   0.31   0.81
HK     0.48   1.00   0.20   0.20   0.59
CN     0.37   0.20   1.00   0.19   0.44
BOND   0.31   0.20   0.19   1.00   0.41
BENCH  0.81   0.59   0.44   0.41   1.00
```

**Why this matters more than the individual errors:** the prototype's file header claims its
numbers are *"internally consistent with each other … true by construction rather than by careful
hand-editing."* For the computed values that is accurate. For the prose it is not — the prose was
hand-written to describe a portfolio the generator did not produce, and nothing checks it.
A production engine must derive every comparative conclusion from the values, and any
comparative string that cannot be derived must not exist. **I recommend a check that no
`conclusionQuick` containing a comparative word survives without being generated from the
comparison it asserts.**

### 7.2 SEVERE — the risk and return statistics describe a different portfolio than the exposure charts

`SLEEVE_WEIGHTS = { us: 0.40, hk: 0.30, cn: 0.20, bond: 0.10 }` (`data.js:116`) drives
`portfolioReturns`, and therefore every return, volatility, beta, alpha, Sharpe, drawdown,
tracking error, VaR, correlation and risk-contribution figure on the surface. The actual holdings
weigh:

| Sleeve | `SLEEVE_WEIGHTS` | Actual market weight of holdings |
|---|---|---|
| US equity (ex-TLT) | 0.40 | **0.4819** |
| Hong Kong | 0.30 | **0.3524** |
| **Mainland China** | **0.20** | **0.1035** |
| Bonds (TLT) | 0.10 | **0.0621** |

The Mainland China sleeve carries **twice** the weight in every risk statistic that it has in the
portfolio the exposure charts describe. `data.js:114-115` promises these are *"checked against
actual computed weights in a self-consistency comment near HOLDINGS."* **No such comment exists.**
I searched the file.

This is prototype-only in the sense that a real engine would derive weights from the ledger. It is
not prototype-only in what it does to the gate: the exposure charts and the risk charts on the same
screen are describing different portfolios, and the CN sleeve — the product's differentiator — is
the one most misstated.

### 7.3 SEVERE — position-level USD gain/loss cancels FX exactly, contrary to §8.3

`data.js:602`: `costBasisUSD = h.avgCost * h.quantity * FX_RATES[h.currency]`, and market value is
`h.quantity * h.price * FX_RATES[h.currency]`. The gain/loss percentage is therefore

```
glPct = (q·P·fx) / (q·C·fx) − 1 = P/C − 1
```

**The FX rate cancels identically.** Every per-position "unrealized gain/loss" is a pure
local-currency price return with the currency effect removed, for a product whose stated
differentiator is showing the currency effect. Applying one snapshot rate to a historical cost is
also the specific thing §8.3 forbids: *"never retroactively apply today's FX rate to historical
portfolio values."*

Correct method: cost basis is translated at the **transaction-date** FX rate and carried in
reporting currency thereafter; the position's reporting-currency return then genuinely contains the
currency effect, and it decomposes by the §4.3 identity.

### 7.4 SEVERE — `Gain / Loss (1Y, USD)` is a time-weighted return converted into a currency amount

`data.js:422`: `TOTAL_PORTFOLIO_VALUE * PERIOD_RETURN / (1 + PERIOD_RETURN)` = **$18,487** on a
total of $263,925. This implies a starting value of ~$245,438.

But the trailing year contains large contributions in the very ledger this file ships:
`tx-0016` CNY 800,000 (≈ **$112,480**) on 2025-09-09, `tx-0030` $3,000, `tx-0028` $5,000. A
portfolio that received ~$120k of new money in the window did not start at $245k.

A time-weighted return is deliberately insensitive to cash flows — that is what it is for — and it
therefore **cannot be converted into a money amount by multiplying by a portfolio value.** A
currency P&L is a money-weighted quantity and must be computed from the ledger as
`V_end − V_start − Σ contributions + Σ withdrawals`. `metric.pl.absolute.explanationSimple` half
acknowledges this (*"before this period's contributions/withdrawals are separated out"*), but a
figure labelled `Gain / Loss (1Y, USD)` that contains contributions is not a gain or a loss.

### 7.5 MAJOR — Sortino's downside deviation uses the wrong denominator

`data.js:54-58` divides the sum of squared downside deviations by the **count of downside
observations**. The Sortino/Satchell target semideviation divides by the **full sample N**;
downside days contribute zero, they do not shrink the denominator.

At the actual data: 130 of 252 days are below the daily risk-free rate.

| | Downside deviation (daily) | Annualized | Resulting Sortino |
|---|---|---|---|
| `data.js` (÷ n_downside) | 0.008379 | 13.30% | **0.2813** |
| Standard (÷ N) | 0.006018 | 9.55% | **0.3916** |

The `data.js` denominator inflates downside deviation by **39%** and understates Sortino by 28%.
The metric currently renders `INSUFFICIENT_DATA` so no wrong number reaches the screen — but the
formula would ship, and the error is exactly the "internally consistent but wrong" shape §38.6
names.

Separately, `metric.sortino.caveat` (`data.js:509`) asserts *"Fewer than the minimum required
downside-return observations in the current window."* There are **130**. The state is a legitimate
demonstration; the stated fact is false against the data in the same file.

### 7.6 MAJOR — the as-of date does not bound its inputs (§34, P12)

`APP.data.meta.asOf` and `portfolio_snapshot_id` are `2026-09-03`. But `FRESHNESS_AXES`
(`data.js:358-363`) dates three inputs **after** it:

- `us_equity` — 2026-09-04 10:32 ET (an *intraday* price, not a close)
- `usd_hkd_fx` — 2026-09-04 09:15 ET
- `usd_cny_fx` — 2026-09-04 09:50 ET

So a snapshot declared as-of 2026-09-03 is priced from a 2026-09-04 US intraday quote, a 2026-09-03
HK close, and a 2026-09-02 CN close. §34 requires that a calculation be reproducible from a stated
snapshot version and market-data timestamps. **An as-of date that does not bound its inputs does
not identify a state, and the calculation is not reproducible from it.** P12 requires the same.

This is also the concrete form of the cross-border problem the product is for: three markets, three
timestamps, one label. Either the as-of date bounds every input, or the metric declares a
per-market as-of set and there is no single portfolio as-of date. That choice is methodology and
I flag it as needing a decision; I would specify **the as-of date is the latest instant at or before
which every required input has a print**, which here would be 2026-09-03 close and would exclude
the 09-04 US intraday quote.

### 7.7 MAJOR — the risk-contribution method is *understated*, and its displayed shares do not sum to 100%

`data.js:305-327` calls itself a *"simplified illustrative risk-contribution approximation … NOT a
certified risk-decomposition engine."*

It is not an approximation. `w_i · σ_i · ρ_{iP}` is the exact marginal contribution to portfolio
volatility (`MCTR_i = w_i · cov(r_i, r_P)/σ_P = w_i σ_i ρ_iP`), and Euler's theorem gives
`Σ_i w_i σ_i ρ_iP = σ_P` exactly for a linear portfolio. The replication confirms it to ten decimal
places: `Σ = 0.13993663`, `σ_P = 0.13993663`, ratio `1.0000000000`. The `√252` cancels in the
normalization.

**Under-claiming a method is a registry error in the same family as over-claiming one** — it tells a
reviewer not to check something that is in fact load-bearing, and it invites a future
implementation to "improve" an exact decomposition into an approximate one. §18.3 asks precisely
for this comparison ("*capital weight vs estimated risk contribution*") and the code already
delivers it correctly.

What *is* genuinely limited, and should be the caveat instead: it decomposes **volatility only**,
it excludes **FX risk** entirely (the sleeves carry no FX — §4.1), and it excludes **cash**
(19.4% of portfolio value).

Second, presentational but material: the three displayed segments sum to **79.97%**, because the
withheld CN segment's 20.03% is still in the normalization denominator. That is the *right*
arithmetic — renormalizing over three would inflate them — but a reader sees three percentages and
assumes they complete. The withheld share must be shown as a labelled remainder, not left as a
silent gap.

### 7.8 MODERATE — denominator inconsistencies across the exposure and concentration surfaces

| Figure | Denominator | Value |
|---|---|---|
| `metric.totalPortfolioValue` | holdings **+ cash** | $263,925.10 |
| `metric.concentration` (top 5) | **holdings only** | 75.11% |
| the same top 5, of total portfolio value | holdings + cash | **60.56%** |
| `HHI` / `Effective N` | holdings only | 0.1330 / 7.52 |
| `EXPOSURE.sector`, `.assetClass`, `.listingMarket`, `.economicGeography` | holdings only | — |
| **`EXPOSURE.currency`** (`data.js:281`) | **holdings + cash** | — |

Two distinct problems. First, cash is **19.38%** of this portfolio and is excluded from every
concentration figure; "your top five holdings make up a majority of invested value" is true at
75%, but a user reading it against the total-value figure directly above will take it as 75% of
$263,925. §18.1 lists top-5 and HHI without specifying a denominator, so this must be chosen and
stated — and stated *on the metric*, not only in a registry. Second, **currency exposure uses a
different denominator than every other exposure dimension**, so the bars are not comparable across
the tabs a user flips between.

### 7.9 MODERATE — conventions in use that are nowhere written down

Each of these is a legitimate choice; P12/§34 make the choice part of the method, and none is
recorded:

- **Risk-free de-annualization.** `RF_DAILY = 0.045/252` (`data.js:97`) — simple division.
  Compounded would be `(1.045)^(1/252) − 1 = 0.00017476` vs `0.00017857`. Small, but it changes
  Sharpe and alpha in the last displayed digit and must be fixed by convention, not by whichever
  was typed first.
- **A single USD risk-free rate** applied to a portfolio with CNY and HKD legs. Defensible for a
  USD-reporting portfolio and standard; must be *stated* as the reporting-currency risk-free rate.
- **Population (÷N) rather than sample (÷N−1) moments** throughout (`data.js:38-53`). At n=252 the
  effect on volatility is ~0.2%; it cancels exactly in beta. Immaterial, still a convention.
- **Sharpe is arithmetic-annualized** (`mean/stdev × √252`) while the return displayed beside it is
  geometric — the same mismatch as §1.2.
- **Max drawdown window.** `MAX_DRAWDOWN` (`data.js:168`) slices a drawdown series whose running
  peak is computed from index 0 of the **full 504-day history**, so a "1Y" drawdown may be measured
  from a peak outside the 1Y window. **In this dataset it happens to make no difference** — both
  conventions give `−0.130693` — so this is a **latent** defect, not an observed error. It must
  still be specified: I would fix the peak at the window start, so that "Max Drawdown (1Y)" means
  what it says.
- **Correlation values are rounded to 2 d.p. inside `data.js:297`**, before any display layer sees
  them. A display convention baked into the data layer cannot be changed by the display layer, and
  it silently defines the precision of every downstream comparison.

### 7.10 MODERATE — the range selector desynchronizes the chart from the numbers below it

`analytics.js:158-169`: the 1M/3M/6M/1Y/ALL pills call `renderHero(r)`, which re-renders **only the
chart**. The metric strip beneath it (`analytics.js:172-177`: return, benchmark-relative, FX
attribution) is fixed at trailing 1Y and neither updates nor re-labels. A user selecting `3M` sees
a three-month chart above a set of one-year numbers with nothing saying so.

§14's closing line — *"Every metric must state the actual window/frequency used"* — is the direct
requirement. Either the strip recomputes with the range, or the range selector is scoped visibly to
the chart alone.

### 7.11 MINOR — VaR excludes currency risk

Consequence of §4.1, recorded separately because it lands on a risk metric: `VAR_95` is computed
from `pr1y`, which contains no FX. For a portfolio with 50%+ non-USD assets, a VaR that omits
currency risk understates the risk it names. Fixed automatically once §4.3's `R_base,P` series
exists.

---

## 8. Registry entries required before this can be built

`data.js:649-696` populates 5 of the 19 `methodologyId`s in use. §33 requires all 15 fields for
every metric. Missing entirely, and in priority order for the questions above:

1. **`methodology.var`** — specified in full in §3.5 above. Was empty (AC-17); is now specified.
2. **`methodology.fxAttribution`** — specified in §4.6. This one blocks the waterfall.
3. **`methodology.sml`** — must record that it is an **ex-post** market line, that the line's slope
   uses the realized benchmark return, that the vertical distance is concept 4 not concept 3, and
   the compounding basis of each.
4. **`methodology.benchmarkRelative`** — must record the two-leg comparability requirement (§5.2)
   and the §13.3 disclosure set.
5. **`methodology.sortino`** — must record the ÷N denominator (§7.5) explicitly, because the
   ÷n_downside variant exists in the wild and the difference is 39%.
6. **`methodology.contributionToRisk`** — must record that it is the exact Euler decomposition of
   volatility, what it excludes, and that displayed shares may not sum to 100% when a segment is
   withheld.
7. **`methodology.drawdown`, `.trackingError`, `.correlation`, `.sharpe`, `.exposure`,
   `.unrealizedGainLoss`, `.fxConversion`, `.portfolioGainLoss`, `.totalPortfolioValue`** — all
   empty. Two of them (`unrealizedGainLoss`, `portfolioGainLoss`) carry the defects in §7.3 and
   §7.4 and cannot be written down as currently implemented.

Corrections to the entries that **are** populated:

- `methodology.beta.minimumObservations` — "36 monthly-equivalent" against a 1Y daily window is
  unmeetable (§1.4). Replace with the §1.4 table.
- `methodology.beta.frequency` — reconcile with §14 or record the deviation (§1.3, D1.3).
- `methodology.portfolioReturn.fxTreatment` says *"Spot conversion at each valuation date's FX
  fix"*. The prototype does not do this (§4.1) and does not name a fix. The field is right; the
  implementation and the fixing time are not.

The full `methodology/METHODOLOGY_REGISTRY.md` and `methodology/DATA_SUFFICIENCY.md` are my role's
standing outputs and do not yet exist. They are a separate deliverable from this task and I have
not created them here.

---

## 9. Product decisions I am handing back rather than deciding

These are not methodology facts. Deciding them here would be the same overreach the PM correctly
refused in §6 of the verification.

1. **Estimation frequency for cross-market beta/correlation.** §14 says weekly by default and gives
   the reason. Daily is defensible if recorded. But moving to weekly changes beta, correlation and
   tracking error on a prototype the owner has already reviewed three times, so *when* to change it
   is a scope call. **Mine to specify, theirs to schedule.**
2. **Which FX fixing time.** §4.6 requires one fixing time for all three markets, but which one is
   a genuine choice with consequences: a London/WM 16:00 fix is the market standard and is after the
   Asian close but before the US close; a US-close fix aligns with the reporting currency's own
   market but re-times every Asian position. There is no answer that makes all three markets
   simultaneous — that is the product's founding constraint. **This needs a recorded product
   decision, and it must be the same fix for the portfolio leg and the benchmark leg or §5.2's
   comparability problem is permanent.**
3. **Which price for a dual-listed or ADR position.** §10.3/§10.4 distinguish listing market from
   economic geography and the data model already carries both, but nothing states which listing's
   close is used for valuation when both exist. Not raised by anyone; it will bite at CP1.
4. **Whether to add expected shortfall** beside VaR (§3.5). Better statistic at this sample size;
   adding a metric is scope.
5. **The concentration denominator** (§7.8) — holdings-only or including cash. Both are used in
   practice. It changes the headline number from 75.1% to 60.6%, which is a product-meaning
   decision, not a formula.
6. **ETF look-through.** §18.4 keeps it out of V1, correctly. My only methodology note: while VOO
   is treated as one security, it is the **largest single position** in this portfolio at 20.5% of
   holdings, so HHI and Effective N (7.52) describe a concentration that a look-through would
   materially change. That limitation belongs in the concentration registry entry, and the number
   should not be presented as diversification without it.

---

## 10. Contradiction with an accepted contract

One, and I stop at flagging it: **`designs/FEATURE_DESIGN.md` §D3.2's justification that
`AVAILABLE` + `STALE_DATA` "is not degraded"** is correct for single-leg metrics and incorrect for
two-leg comparisons (§5.5). I am not amending it. The fix is a scoping clause plus a comparability
disclosure on the D5 axis, and it belongs to `designer` and `product_manager`.

No contradiction found with P1, P8, P9, PD-0006 or PD-0007. §7.1 is a *violation* of P1 in the
prototype, not a contradiction of it — the principle is right and the prototype departs from it.

---

## 11. What I verified, and what I could not

**Verified:**

- Every numeric claim in this document, by independent re-implementation
  (`methodology/verification/hg1_round4_replication.py`), which reproduces the five values visible
  on the surface exactly. Anyone can re-run it.
- Formulas, windows, frequencies, estimators, denominators and sign conventions, by reading
  `data.js` line by line. Every finding cites its line.
- The §14, §32, §33, §34, §13.3, §8.3, §8.4, §18.1, §18.3, §18.4 and §20.2 requirements against
  the PRD text directly, not from summaries.
- PD-0006 and PD-0007 in full, including their amendments, to make sure §5 and §6 sit inside them
  rather than reopening them.

**Not verified, and it matters:**

- **I did not execute the prototype.** No JavaScript runtime is available here. My values come from
  a restatement of the generator, not from the running page. The five-value agreement in §0 is
  strong evidence the restatement is faithful, but a rendering-layer transformation between
  `data.js` and the pixels — rounding, sign handling in `shell.js`'s `renderMetricValue`,
  `formatPercent` — is outside what I checked. **§7.1's four contradicting strings and §1.2's
  compounding mismatch are claims about the source, and I have not seen them on screen.**
- **I did not review `shell.js`, `charts.js`, `evidence.js`, `scenario.js`, `ai.js` or the other
  surfaces.** My grant was the Analytics surface and the data layer. `charts.js` in particular
  draws the SML line and the `alphaCallout` and may transform them further; §2's specification
  assumes it plots what it is handed.
- **I did not check scenario methodology (P8).** The scenario comparisons in `data.js:787-841` use
  hardcoded multipliers (`ANNUAL_VOL * 0.91`, `BETA * 0.93`, `SHARPE * 1.04`) with no stated model.
  For a synthetic prototype that is defensible; **a scenario engine that multiplies a risk figure
  by a constant is not, and nobody has specified what it should do instead.** That is a real open
  methodology gap and it is not in this task's five questions.
- **No market data and no network.** Every benchmark, FX and price figure discussed is synthetic. I
  cannot check MSCI ACWI's actual methodology metadata (§13.3) or any real fixing convention.
- **No golden fixtures exist for the production engine**, and this task did not produce any. The
  engine in `src/` therefore still has no independent expected values to compare against, which is
  the specific gap `roles/quant_analyst.json` exists to close. **That remains open.**

---

**HG1 remains `REVISION_REQUIRED` and unapproved. Nothing here changes that, and nothing here is
an approval of any kind.**
