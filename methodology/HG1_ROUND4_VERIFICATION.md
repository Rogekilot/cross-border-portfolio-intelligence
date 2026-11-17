# HG1 round 4 — independent verification of the analytical-truth corrections

**Author:** `quant_analyst`, worker `quant-01`.
**Date:** 2026-09-06.
**Under:** PD-0014 §3 — the producer does not certify its own correction.
**Object:** `designs/hg1-prototype-v2/js/data.js` (rewritten by designer-19),
`designs/hg1-prototype-v2/js/selfcheck.js` (new), and
`designs/hg1-prototype-v2/js/surfaces/analytics.js` (which I checked because my Q2 and Q4
specifications land there, and which the coordinator's message did not list).
**Prior artifact:** `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md`.

**Gate state: HG1 is `REVISION_REQUIRED`, ACTIVE, UNAPPROVED.** Nothing here is an approval.
I changed nothing outside `methodology/`.

**Headline.** The data layer is a faithful and in places better-than-specified implementation
of my findings. **Three things are not right and one of them is my own fault:**

1. **The Analytics surface was not updated.** Q2's central defect — the chart annotating its
   own vertical distance with the regression alpha — is still live, and the error it produces
   is now **3.6× larger** than before the correction.
2. **`metric.correlation`'s local-currency basis is not defensible as implemented**, though not
   for the reason it looks like: the numbers barely move, but the matrix's benchmark row is a
   USD series inside a matrix the product labels "local-currency".
3. **A new unsupportable claim was introduced**, and the specification gap that let it through
   is mine: beta is now **0.994 ± 0.042**, and the surface asserts the portfolio "moved less
   than the market" on a **0.143-standard-error** difference from 1.0.

---

## 0. Method, and the cross-check that licenses the rest

I re-derived the corrected chain independently in
`methodology/verification/hg1_round4_postfix_replication.py`. The pre-correction harness
(`hg1_round4_replication.py`) is untouched, so the two together show what moved.

The PRNG consumption order is genuinely unchanged (`marketFactor` → four sleeves → `fxHKD` →
`fxCNY`); `HOLDINGS` moved earlier in the file but draws no random numbers, so P12 determinism
is preserved. I confirmed this by reproducing the same series.

My replication reproduces the corrected build:

| Quantity | My replication | Reported live |
|---|---|---|
| Sleeve weights us/hk/cn/bond | `0.481901 / 0.352443 / 0.103550 / 0.062106` | 48.19 / 35.24 / 10.35 / 6.21 |
| `BETA` | `0.994004` | 0.994 |
| Window | 252 obs, `2025-09-17` → `2026-09-03` | 252 obs, 2025-09-17 to 2026-09-03 |

Everything below is from that harness. **Every headline number has moved**, which is correct
and expected — the portfolio being measured genuinely changed:

| | Pre-correction | Corrected |
|---|---|---|
| Portfolio return (1Y) | +7.53% | **+3.89%** |
| — of which local-market | (not computed) | **+4.45%** |
| — of which FX effect | (wrong sign, −0.29%) | **−0.56%** |
| Beta | 0.931 | **0.994** |
| Jensen's alpha | +12.09% | **+9.33%** |
| SML vertical distance | +11.98% (uncomputed) | **+8.94%** |
| Annualized volatility | 13.99% | **14.91%** |
| Sharpe | 0.267 | **0.029** |
| Tracking error | 7.85% | **8.28%** |
| VaR₉₅ magnitude | 1.34% | **1.62%** |
| Max drawdown | −13.07% | **−15.20%** |
| vs. benchmark | +12.64% | **+8.99%** |

---

## 1. Fidelity to each specification

| Spec | Where | Verdict |
|---|---|---|
| **Q1** — true observation count, dated window, meetable threshold, §14 deviation recorded | `data.js` beta caveat | **Implemented, and better than specified.** The caveat reads the *same* `WINDOW_OBS_COUNT` variable the Proof Packet's `observations` field reads, so D1.1's two-numbers-on-one-screen defect is closed structurally, not by matching two literals. |
| **Q1** — compounding basis stated where arithmetic and geometric quantities share a unit | `metric.sml`, `metric.alpha` | **Implemented in the claim text.** Not implemented in the chart subtitle — see §2. |
| **Q2** — concept 4 computed and exposed | `SML_VERTICAL_DISTANCE`, `getSMLPoints().verticalDistance` | **Implemented in data.** **Not consumed by the chart** — see §2. |
| **Q2** — ex-post labelling, P6 wording | `metric.sml`, `metric.alpha` | **Implemented in claim text.** "predict" and "'should' have returned" are both gone; the replacements are the ones I specified. **Chart title unchanged** — see §2. |
| **Q3** — VaR convention | `metric.var95`, `methodology.var` | **Implemented exactly**, including the `q ≥ 0` edge case, the unsigned magnitude formatter, `directional: false`, the realized exceedance count, and the full 15-field registry entry. |
| **Q4** — exact geometric identity, period-start FX, no residual | `data.js` §6 | **Implemented exactly.** Verified numerically in §3 below. |
| **Q5** — comparability wording, session-aware staleness | `BENCHMARK_RELATIVE_COMPARABILITY_NOTE`, `FRESHNESS_AXES` | **Implemented, with a correct consequence I had not spelled out**: because the CN axis is now `END_OF_DAY` rather than `STALE`, the `STALE_DATA` reason code was correctly *removed* from `metric.benchmarkRelative` while the comparability disclosure was retained. That is precisely the sufficiency/comparability separation §5.2 asked for, applied without being told. |
| **§7.5** Sortino ÷N | `downsideDeviation()` | **Implemented.** Denominator is now the full sample. |
| **§7.7** Euler exactness | `methodology.contributionToRisk` | **Implemented**, including the labelled-remainder disclosure. One wording error — see §5.3. |
| **§7.1** derived conclusions | `betaDirectionConclusion` etc. | **Implemented**, and the insights are derived too. But see §6 — the derivation introduced a new problem. |

### 1.1 Deviations from my specification that are nonetheless correct

- **`metric.sortino`'s caveat.** I specified only the ÷N fix. The implementer noticed that I had
  never set a minimum-downside-observation threshold and therefore refused to assert one,
  writing instead that the metric is withheld to demonstrate the render path and that *"this is
  not a claim that the current sample (127 downside days out of 252) is actually insufficient."*
  That is the right call: inventing my threshold would have been exactly the overreach my role
  exists to prevent. The gap is mine and I note it in §8.
- **`metric.pl.absolute`.** I did not ask for a caveat; one was added disclosing the
  TWR-to-currency conversion. Correct instinct, insufficient remedy — see §7.2.
- **Refusing to invent a correlation strength threshold** (`correlationConclusion` uses purely
  rank-based language). Correct, and I close that gap in §5.2.

---

## 2. The Analytics surface was not updated, and Q2's defect is still live

`designs/hg1-prototype-v2/js/surfaces/analytics.js` is unchanged in every place my Q2 and Q4
specifications targeted. `data.js` says so in its own comments, attributing this to write-path
scope. That is an honest handoff, but it means **the gate is being asked to look at a screen
that still contains the defect.**

**2.1 — `analytics.js:458` passes `metric.alpha.value` into `alphaCallout`.**

```js
alphaCallout: (portfolioPoint && alphaClaimForChart && typeof alphaClaimForChart.value === "number")
  ? { beta: portfolioPoint.beta, ret: portfolioPoint.ret, alpha: alphaClaimForChart.value }
```

The chart draws the vertical distance from the portfolio point to the line and labels it with
the **regression alpha**. The two quantities are:

- true vertical distance (concept 4): **+8.9373%**
- regression Jensen's alpha (concept 3): **+9.3346%**
- **difference: 0.397 pp**

Pre-correction this gap was 0.11 pp. It is now **3.6× larger**, because beta moved from 0.931 to
0.994 and the arithmetic-vs-geometric wedge widened. `data.js` computed and exposed
`verticalDistance` precisely so this could be fixed, and nothing reads it. **The surface still
labels one quantity with another's number, and the labelling error grew.**

**2.2 — `analytics.js:425` still reads `blockHeader("Portfolio vs. Market (SML / CAPM)")`.** My
§2.4 required `Realized return vs. beta — ex-post market line (trailing 1Y)`, and required that
"Security Market Line" never appear unqualified as a title. Not applied.

**2.3 — `analytics.js:457` windowLabel is still `"Trailing 1Y · Daily returns"`.** No
observation count, no dated window, no compounding basis, no §13.3 disclosure set. The corrected
strings exist in `data.js`'s claims; the chart does not read them.

**2.4 — `analytics.js:252` still derives the local leg by subtraction.**

```js
var localVal = retClaim.value - fxClaim.value;
```

This is now **numerically exact** — since `FX_ATTRIBUTION_PCT = PERIOD_RETURN −
PERIOD_RETURN_LOCAL`, subtracting it back recovers the local return to floating-point equality,
and `selfcheck.js`'s `fxAttribution.portfolioIdentityExact` verifies that against the
independently tracked value rather than tautologically. So this is not producing a wrong number.

But §4.4 item 1 said the local bar "may **never** be derived by subtraction from the total." The
reason stands: the moment anyone changes how the FX leg is defined, this line silently produces
a plausible wrong number again, and the identity that currently rescues it is not visible at the
call site. It should read `getFxAttributionDetail().portfolio.local`. **Low severity, real.**

Also still absent from the waterfall: the third bar, the per-sleeve breakdown, and the
exclusions statement (§4.4 items 3–5). The accessor `getFxAttributionDetail()` now supplies
everything needed and no surface consumes it. The stale comment at `analytics.js:251` still says
*"no per-sleeve (HK vs. CN) local/FX split is exposed by data.js"* — no longer true.

**Ruling: 2.1 is an HG1 blocker.** It is the specific finding that sent this to methodology in
the first place, the fix is a one-line change to read a field that already exists, and the error
is larger now than when it was found.

---

## 3. Is the FX correction right? Yes — verified four ways

This was the largest change and the one most likely to introduce a new error. It did not.

**3.1 — Sleeve identity is exact.** For both foreign sleeves,
`(1+R_local)(1+R_fx) − 1 − R_base = 0.000e+00` at full double precision:

| Sleeve | Local | FX | Interaction | Base | Weight |
|---|---|---|---|---|---|
| HK | +17.2564% | −1.9302% | **−33.31 bp** | +14.9931% | 0.3524 |
| CN | +27.8779% | +1.4576% | **+40.63 bp** | +29.7418% | 0.1035 |

The interaction terms are unchanged from my §4.2 table (they depend only on the sleeve and FX
series, which did not change) and are now **reported** rather than absorbed, via
`getFxAttributionDetail()`.

**3.2 — Portfolio identity is exact by construction.**
`PERIOD_RETURN_LOCAL + FX_ATTRIBUTION_PCT − PERIOD_RETURN = 0.000e+00`.
Local **+4.4453%**, FX effect **−0.5572%**, base **+3.8881%**. `metric.performanceAttribution`'s
claim that "the two legs shown sum exactly to Portfolio Return (1Y) by construction — no
residual" is literally true.

**3.3 — The portfolio FX effect is correctly *not* the weighted sum of sleeve FX returns.**
This is the part most likely to have been fudged, and it was not:

- weighted sleeve FX sum: **−0.5293%**
- exact portfolio FX effect: **−0.5572%**
- difference: **2.79 bp**

The old code used the first (and mislabelled it). The new code uses the second. The 2.79 bp is
the compounding interaction plus the daily-blend path, and it correctly lives inside the FX leg,
exactly as §4.3 specified, with `professionalDetail` saying so.

**3.4 — Downstream propagation is correct and complete.** Volatility, beta, alpha, Sharpe,
Sortino, drawdown, tracking error, VaR and portfolio-benchmark correlation all read `pr1y`,
which is the FX-inclusive series. I reproduced each from the corrected series and every one
matches. §7.11 (VaR excluded currency risk) is closed as a consequence.

**3.5 — One convention now needs recording, created by this fix.**

`SLEEVE_WEIGHTS` are derived from market values **as of 2026-09-03** and then applied to the
**entire trailing window**, with daily rebalancing to those fixed weights. Two things follow
that the registry must state and currently does not:

- It is a **daily-rebalanced constant-weight blend**, not a buy-and-hold portfolio. The Euler
  exactness in §5.1 depends on this.
- Today's weights are applied **retroactively** across a window in which some positions did not
  exist (`600519.SS` transferred in 2026-07-02; `2800.HK` bought 2025-11-04). That is a
  look-ahead in the strict sense.

This is a *better* state than before — previously the weights disagreed with the exposure
surfaces entirely — and for a synthetic prototype it is defensible. But `methodology.portfolioReturn`
must say it, and the return must not be described as "the portfolio's actual return." **CP1
work, plus a one-line registry addition now.**

---

## 4. Ruling on the basis split: two of three are right, one is not

The implementer split the series basis three ways. The coordinator is right that this is either
principled or an inconsistency. It is both, in different places.

**4.1 — Contribution-to-Risk on base series: REQUIRED. Correct.**
The Euler identity `Σ wᵢσᵢρᵢₚ = σₚ` holds only when the components are the same series the
portfolio is built from. My harness confirms it to twelve decimal places:
`Σ = 0.1491032071`, `σₚ = 0.1491032071`, ratio `1.000000000000`. Using local sleeves here would
have silently broken exactness. **This was not a stylistic choice; it was forced, and correctly.**

**4.2 — SML sleeve points on base series: REQUIRED. Correct.**
The Y axis is realized USD return and the portfolio point is in USD. Plotting HK/CN sleeve
points in local currency on that axis would compare incomparable quantities, and their betas
against a USD benchmark would mix currencies. Correct.

**4.3 — Sleeve Correlation Matrix on local series: NOT defensible as implemented.**

The stated rationale — "asset-level co-movement, a different analytical question" — is a real
and legitimate question. It does not survive contact with this particular matrix, for three
reasons, none of which is about the numbers:

1. **The matrix's fifth row is the benchmark, which is a USD series.** Everywhere else in the
   file `benchmarkReturns` is treated as reporting-currency (beta, tracking error and
   `CORR_PORT_BENCH` are all computed against it in USD terms). So the matrix is four
   local-currency series plus one USD series, and `metric.correlation.referencePoint` describes
   all five as *"local-currency sleeve returns."* That description is false for row five, and
   ρ(CN local, ACWI USD) is a cross-currency correlation with the currency stripped from one
   side only. **This is not "a different question" — it is two questions in one table.**
2. **It is inconsistent with the same page.** `CORR_PORT_BENCH` (0.8317) is computed on the base
   series. A user comparing the portfolio's correlation to the benchmark against the sleeves'
   correlations to the benchmark is comparing two bases.
3. **The conclusion drawn from it is a reporting-currency question.** §18.2's correlation UX
   exists to tell a user how diversified *their portfolio* is; diversification is realized in
   the reporting currency. `insight.correlation.hkCluster` is presented as a portfolio
   diversification statement.

**How much does it matter numerically? Almost not at all, and I want that on the record:**

| | Local basis | Base basis |
|---|---|---|
| ρ(US,HK) | 0.479 | 0.481 |
| ρ(US,CN) | 0.371 | 0.377 |
| ρ(HK,CN) | 0.203 | 0.211 |
| ρ(HK,Bond) | 0.197 | 0.196 |
| ρ(CN,Bond) | 0.187 | 0.184 |

**Maximum absolute difference across the whole matrix: 0.0088.** The equity-pair *ranking* is
identical in both bases (US/HK > US/CN > HK/CN), so **every currently displayed conclusion is
unchanged** by the basis choice.

**Ruling.** This is a **consistency and labelling defect, not a numerical error**. Fix by moving
the matrix to the base (reporting-currency) basis, which makes all five rows one basis and
matches every other statistic on the surface. If the local-currency view is wanted as a genuine
second analysis, it must be a *separate* table, without the benchmark row, explicitly labelled
as excluding currency effects — but I would not add that in V1.

Because the numbers barely move and no conclusion changes, this is **CP1 work with an HG1
labelling fix**: at minimum, `metric.correlation.referencePoint` must stop describing the
benchmark row as a local-currency sleeve return. **`methodology.correlation` is still an empty
registry entry** — the one place §33 requires the basis to be recorded is blank, which is how
this became ambiguous.

---

## 5. `selfcheck.js`

**5.1 — Assessment: this is a genuinely good control, and better designed than it needed to be.**

Twenty-one assertions, each with a paired `injectDefect` negative test, each running in its own
try/catch, with `selfTest()` refusing to credit any assertion that has no demonstrated negative
test. Three design choices are worth naming because they are the ones that usually go wrong:

- **Field-independent checking.** `binding1` classifies `conclusionQuick` and
  `explanationSimple` separately rather than concatenating them, so a correct field cannot mask
  a defective one.
- **Sentence-scoped claim matching.** `binding3` and `binding2` locate the *specific sentence*
  making a claim rather than regex-ing the whole blob, which is what makes them able to fail.
- **Non-tautological cross-checks.** `fxAttribution.portfolioIdentityExact` compares
  analytics.js's subtraction against the independently tracked `PERIOD_RETURN_LOCAL` from a
  second accessor; the file's own header records that an earlier version of this check was
  tautological and could never fail. Recording a defect in one's own control is the behaviour
  that makes the rest of the file credible.

The assertions encode my methodology correctly, with two exceptions, one of them mine (§6).

**5.2 — The correlation classification rule, which the implementer correctly declined to invent**

They were right not to invent it, and right that rank-based language needs no threshold. Here is
the rule, so the assertion can enforce it.

**Bands are derived from realized diversification benefit, not asserted.** For two equal-weight,
equal-volatility assets, portfolio volatility is `σ·√((1+ρ)/2)`, so the volatility reduction
from combining them is `1 − √((1+ρ)/2)`. That is the thing the product actually wants to tell a
user, so the bands are cut on it:

| ρ | Permitted label | Volatility reduction for an equal-weight pair |
|---|---|---|
| ρ ≥ 0.80 | "move almost identically — little diversification benefit between them" | < 5.1% |
| 0.60 ≤ ρ < 0.80 | "strongly co-moving" | 5.1 – 10.6% |
| 0.35 ≤ ρ < 0.60 | "moderately co-moving" | 10.6 – 17.8% |
| 0.15 ≤ ρ < 0.35 | "weakly co-moving" | 17.8 – 24.2% |
| ρ < 0.15 | "largely independent in this sample" | > 24.2% |

Each boundary is checkable: `1 − √((1+0.80)/2) = 5.13%`, `0.60 → 10.56%`, `0.35 → 17.84%`,
`0.15 → 24.17%`.

**Precision guard, which is the part that matters.** An absolute label may be asserted **only
if the nearest band boundary is at least one standard error away**, with
`se(ρ) ≈ (1 − ρ²)/√(n−1)`. Otherwise the product uses rank language only — which is what the
implementation already does, so this rule does not force a rewrite, it authorizes an addition.

Applied to this data: ρ(HK,CN) = 0.203, `se = 0.048`, nearest boundary 0.15 is 0.053 away =
**1.1 se**. So "weakly co-moving" is assertable here, barely. The rule is not vacuous on this
dataset, which is the test of whether a threshold is real.

**Basis:** classification applies to the **base (reporting-currency)** matrix, per §4.3.

**Assertion to add:** any sentence carrying a band label must match the band the value falls in,
**and** the precision guard must hold; otherwise fail. This is a strict addition to `binding3`,
which should keep its rank check unchanged.

**5.3 — One methodology wording error to correct**

`methodology.contributionToRisk.knownLimitations` says the displayed gap *"equals the withheld
segment's own **weight-implied** share."* It does not. The gap is the withheld segment's
**risk-contribution** share:

- CN risk-contribution share: **7.81%** (= 100% − 92.19% displayed)
- CN **capital weight**: **10.35%**

Distinguishing capital weight from risk contribution is the entire point of §18.3, so conflating
them in this metric's own limitations field is the wrong place for it. The `caveat` on the claim
itself is correct (it states 92.2% and calls it a labelled remainder); only the registry
sentence is wrong. **One-line fix.**

**5.4 — What the self-check structurally cannot see**

`selfcheck.js` reads only `window.APP.data` accessors. It never inspects the DOM or the surface
modules. **Every defect in §2 is invisible to it** — the chart annotation, the chart title, the
window label, the subtraction-derived bar. A green self-check therefore says nothing about
whether the screen is right, and it should not be reported at the gate as if it did. That is a
scope statement, not a criticism; but it needs saying, because a 21/21 pass is exactly the kind
of thing that gets mistaken for approval (`CLAUDE.md`, human gates).

---

## 6. A new unsupportable claim, and the specification gap is mine

`betaDirectionConclusion(BETA)` now renders, derived from the value:

> "Your portfolio has historically moved less than the market (beta 0.99, below 1)."

Beta is **0.994004**. From the same 252 daily observations:

- residual daily s.d. = `0.005235`
- **se(β̂) = 0.041961**
- `|β̂ − 1| = 0.005996` = **0.143 standard errors**
- 95% CI: **[0.9118, 1.0762]** — 1.0 sits comfortably inside

**The sample cannot distinguish this portfolio's beta from 1.0.** Asserting a direction on a
0.143-sigma difference is a false-precision claim (§41.3), and it is now asserted more
confidently than before, because it is *derived* and therefore carries the authority of having
been computed.

**This is my error, not the implementer's.** §7.1 of my findings required comparative prose to
be derived from the value and never hand-asserted. It was. `binding1` in `selfcheck.js` enforces
exactly that, using a hard `value < 1` boundary — and would now *fail* the correct, hedged
sentence, because I gave it a rule with no tolerance band. I own thresholds under PD-0006 and
PD-0007 and I did not set one for directional comparisons.

**Threshold I now set — applies to every derived directional comparison, not just beta:**

> A directional claim about an estimated quantity relative to a reference point may be asserted
> only when the estimate differs from that reference by **more than one standard error of the
> estimate**. Below that, the claim is stated as indistinguishable, and the margin is disclosed.

For beta specifically, the required rendering at 0.994:

> `Your portfolio has moved broadly in line with the market (beta 0.99). At 252 daily`
> `observations the estimate's margin of error (±0.04) spans 1.0, so this sample does not`
> `distinguish it from moving with the market.`

`se(β̂)` must be exposed in the Proof Packet alongside the observation count §13.3 already
requires. `binding1` must be amended to enforce the band rather than the bare inequality.

**Where the band does and does not bind on this data** — I checked the other derived comparisons
rather than assuming:

| Derived claim | Values | Verdict |
|---|---|---|
| Volatility "varied more" | 14.91% vs 12.48%, **19.5% relative** | Safe. Well outside any plausible band. |
| Drawdown "deeper" | −15.20% vs −13.78% | Safe as a statement about realized history — a drawdown is a realized extremum, not an estimate, so no standard error applies. Keep. |
| Risk contribution "US and Hong Kong contribute the most" | 46.36% vs 45.10% vs CN 7.81% vs bonds 0.74% | Safe **because the sentence names the top two as a set**; the US/HK gap of 1.26 pp would not support naming a single leader. Worth a comment in the code so a later edit does not reduce it to one name. |
| Correlation rank claims | 0.479 / 0.371 / 0.203, se ≈ 0.049 | Safe: strongest-vs-second gap is 2.2 se, second-vs-weakest 3.1 se. |
| Concentration "majority" | 75.11% vs 50% boundary | Safe. |

So beta is the only one that trips, but it trips hard.

---

## 7. Still-open §7 items — blocker or CP1

HG1 is Product & Architecture (CP0) per §38.5. My test is therefore: **does this prevent the
owner from making the HG1 decision, or is it build work the decision can precede?** Where the
item is a *definition* the architecture depends on, it is a gate item even when the code fix is
CP1.

### 7.1 §7.3 — per-position FX cancelling in cost basis → **CP1, with an HG1 commitment**

The fix genuinely requires a dated historical FX series the prototype's single-snapshot model
does not carry, and the implementer was right to flag rather than invent it. But the *domain
model* question — must cost basis be translated at transaction date and carried in reporting
currency? — is a CP0 architecture question, and §8.3 already answers it. **Record it as an HG1
architectural commitment; implement in CP1.** If the domain model ships without dated FX, the
defect becomes structural and every position-level P&L in the product is a local-currency return
mislabelled.

### 7.2 §7.4 — TWR converted to a currency P&L → **HG1 BLOCKER, and cheap**

A caveat was added. It is honest, and it is not sufficient: it tells the user the number is not
what its label says. `Gain / Loss (1Y, USD)` reads **$9,877.53**, implying a starting value of
$254,047.57, in a window containing **$120,480** of contributions (CNY 800,000 ≈ $112,480 on
2025-09-09, plus $3,000 and $5,000). The number is not a gain or a loss.

§32 forbids values "that can be mistaken for real analytics," and a correctly-computed number
under a wrong label is the purest form of that. The fix does not require the money-weighted
engine: **rename the metric to what the number is** ("Value change implied by the 1Y
time-weighted return"), or suppress it until the ledger-based figure exists. A label change is
hours of work, so treating it as a blocker costs almost nothing.

### 7.3 §7.6 — as-of date does not bound its inputs → **HG1 BLOCKER as a definition; trivial prototype fix**

`meta.asOf` and `portfolio_snapshot_id` remain `2026-09-03` while three freshness axes are dated
`2026-09-04`, one of them a US *intraday* quote. §34 requires a calculation to be reproducible
from a stated snapshot and market-data timestamps; an as-of date that does not bound its inputs
does not identify a state.

This is a CP0 question because it is the definition of "as of" in a three-timezone product, and
the owner should approve it. My recommendation, unchanged: **the as-of date is the latest instant
at or before which every required input has a print** — here, the 2026-09-03 close, which would
exclude the 09-04 US intraday quote. In the prototype this is a three-timestamp edit.

Note this interacts with Q5: under the session-aware rule the CN print is *current*, and under a
correctly-bounded as-of date the comparability seam is between market close times, not between
calendar days. Both disclosures stay; the as-of fix makes them coherent.

### 7.4 Scenario scaling factors → **HG1 BLOCKER, but not for the reason given**

The hardcoded multipliers (`ANNUAL_VOL * 0.91`, `BETA * 0.93`, `SHARPE * 1.04`, and the
concentration and allocation factors) are acceptable in a synthetic prototype *if labelled as
illustrative*. P8 separation is honored throughout — `stateType: "SCENARIO"` and the "not a
holding" conclusion are correct.

The problem is elsewhere and is worse: **each scenario comparison claim carries a `methodologyId`
pointing at the real metric's registry entry.** A scenario volatility figure produced by
`ANNUAL_VOL * 0.91` resolves its Proof Packet to `methodology.volatility`, which says the value
came from `stdev(daily returns) × √252`. It did not. P9 requires every important insight to be
auditable back to its inputs and method; here the audit trail is not missing, it is **wrong**,
which is the more dangerous state because it looks complete.

**Fix, and it is small:** either point these claims at a new
`methodology.scenarioImpactModel` entry whose text honestly says "illustrative fixed multiplier;
no impact model is implemented in this prototype," or set `methodologyId: null` so the evidence
overlay renders "not yet published" — a state the file already demonstrates deliberately
elsewhere. **Pointing at the wrong method is worse than pointing at nothing.**

### 7.5 Items from §7 not raised by the coordinator, still open

- **§7.8 denominator inconsistencies** — unchanged. Top-5 is 75.11% of holdings and 60.56% of
  total portfolio value; `EXPOSURE.currency` still uses a holdings+cash denominator while every
  other exposure dimension uses holdings-only. **CP1**, but §9.5 of my findings flagged the
  concentration denominator as a *product decision* and it still has no answer.
- **§7.10 range pills** — unchanged; the 1M/3M/6M pills still re-render only the chart while the
  metric strip stays 1Y. **CP1.**
- **§7.9 conventions** — the daily-rebalanced constant-weight and retroactive-weight conventions
  from §3.5 are new and join this list. **Registry additions, now.**
- **One small factual error introduced this pass:** `insight.freshness.cnStale` says the CN print
  is *"one calendar day behind the US/HK prints."* It is one day behind HK (2026-09-03) and
  **two** behind US (2026-09-04). Still hand-asserted prose rather than derived — the same class
  the pass was closing. **Trivial fix.**

---

## 8. My own outstanding gaps

Recorded because a verification that only finds other people's errors is not a verification.

1. **No tolerance band for directional claims** (§6). Directly caused a live unsupportable claim.
   Set above.
2. **No minimum-downside-observation threshold for Sortino.** The implementer correctly refused
   to invent it and the metric now says so on screen. Still mine to set; not set here, because it
   needs the same treatment as the VaR tail-count rule and I would rather do it with the full
   registry than in a margin.
3. **`methodology.correlation` still empty**, which is why §4.3's basis ambiguity had nowhere to
   be resolved.
4. **`methodology/METHODOLOGY_REGISTRY.md` and `DATA_SUFFICIENCY.md` still do not exist**, and no
   golden fixtures exist for the engine in `src/`. Unchanged from my findings' closing statement.

---

## 9. Runtime expressions, for the values I could not execute

I have no browser. My replication reproduces the three anchors the coordinator already
confirmed live (weights, beta 0.994, window dates), which is strong evidence it is faithful —
but the following would close the loop. Please run and return verbatim.

**E1 — full cross-check against my replication.**

```js
(function () {
  var d = window.APP.data, v = function (i) { var c = d.getMetric(i); return c && c.value; };
  return JSON.stringify({
    weights: d._internal.sleeveWeights,
    obs: d._internal.windowObservationCount,
    start: d._internal.windowStart, end: d._internal.windowEnd,
    ret: v("metric.return.1y"), benchRel: v("metric.benchmarkRelative"),
    fx: v("metric.fxAttribution"), beta: v("metric.beta"), alpha: v("metric.alpha"),
    vol: v("metric.volatility"), sharpe: v("metric.sharpe"), te: v("metric.trackingError"),
    var95: v("metric.var95"), mdd: v("metric.maxDrawdown"), conc: v("metric.concentration"),
    verticalDistance: d.getSMLPoints().verticalDistance,
    fxDetail: d.getFxAttributionDetail(),
    contrib: d.getContributionToRisk().segments.map(function (s) { return [s.label, s.weight, s.value]; }),
    corr: d.getCorrelationMatrix().matrix,
    downsideDays: d._internal.downsideDayCount, sortino: d._internal.sortino
  }, null, 1);
})()
```

Expected, from my replication — **any mismatch means my harness is wrong and the rest of this
document must be re-checked before it is relied on**:

`weights` `{us:0.481901, hk:0.352443, cn:0.103550, bond:0.062106}`; `obs` 252;
`start` `"2025-09-17"`; `end` `"2026-09-03"`; `ret` `0.038881`; `benchRel` `0.089949`;
`fx` `-0.005572`; `beta` `0.994004`; `alpha` `0.093346`; `vol` `0.149103`; `sharpe` `0.028534`;
`te` `0.082779`; `var95` `-0.016164`; `mdd` `-0.151994`; `conc` `≈0.7511`;
`verticalDistance` `0.089373`; `fxDetail.portfolio` `{local:0.044453, fxEffect:-0.005572, base:0.038881}`;
`fxDetail.sleeves.hk` `{local:0.172564, fx:-0.019302, interaction:-0.00333078, base:0.149931}`;
`fxDetail.sleeves.cn` `{local:0.278779, fx:0.014576, interaction:0.00406337, base:0.297418}`;
`contrib` shares `US 0.463595`, `HK 0.450951`, `CN null`, `Bonds 0.007377`;
`corr` row HK = `[0.48, 1, 0.20, 0.20, 0.59]`; `downsideDays` 127; `sortino` `≈0.0411`.

**E2 — confirm the §2.1 chart defect is live on screen.**

```js
(function () {
  var d = window.APP.data;
  var a = d.getMetric("metric.alpha").value, vd = d.getSMLPoints().verticalDistance;
  var h = document.querySelector(".analytics-sml .block-header, .analytics-sml h3, .analytics-sml h2");
  return { chartAnnotationValue: a, trueVerticalDistance: vd,
           differencePP: (a - vd) * 100, chartTitle: h && h.textContent,
           calloutText: (document.querySelector(".chart-alpha-callout, [class*='alpha-callout']") || {}).textContent };
})()
```

Expected: `chartAnnotationValue 0.093346`, `trueVerticalDistance 0.089373`,
`differencePP ≈ 0.397`, `chartTitle "Portfolio vs. Market (SML / CAPM)"`. If `calloutText`
renders `+9.3%` as the distance from the line, §2.1 is confirmed on screen.

**E3 — beta precision, to confirm §6 from the live series.**

```js
(function () {
  var _ = window.APP.data._internal, n = 252,
      pr = _.portfolioReturns.slice(-n), br = _.benchmarkReturns.slice(-n),
      mean = function (a) { return a.reduce(function (x, y) { return x + y; }, 0) / a.length; },
      mp = mean(pr), mb = mean(br),
      cov = pr.reduce(function (s, x, i) { return s + (x - mp) * (br[i] - mb); }, 0) / n,
      vb = br.reduce(function (s, x) { return s + (x - mb) * (x - mb); }, 0) / n,
      b = cov / vb,
      sse = pr.reduce(function (s, x, i) { var e = x - (mp + b * (br[i] - mb)); return s + e * e; }, 0),
      se = Math.sqrt(sse / (n - 2)) / (Math.sqrt(vb) * Math.sqrt(n));
  return { beta: b, seBeta: se, sigmasFromOne: Math.abs(b - 1) / se,
           ci95: [b - 1.96 * se, b + 1.96 * se] };
})()
```

Expected: `beta 0.994004`, `seBeta 0.041961`, `sigmasFromOne 0.143`, `ci95 [0.9118, 1.0762]`.

**E4 — I cannot verify the base-basis correlation matrix at runtime.** No accessor exposes the
base sleeve series (`_internal` carries only `portfolioReturns` and `benchmarkReturns`). My
§4.3 comparison is replication-only. It is indirectly supported: if E1's `corr` matches my local
matrix exactly, my sleeve series are faithful, and the base matrix follows from them by the same
arithmetic. If you want it directly, `_internal` would need to expose the four base sleeve
slices — a change I am not asking for on its own account.

---

## 10. What I verified and what I did not

**Verified:** the full corrected computation chain by independent re-implementation; all four FX
identities to floating-point equality; Euler exactness to twelve decimal places; the local-vs-base
correlation divergence; beta's standard error and confidence interval; boundary proximity for
every derived comparative claim; all 21 `selfcheck.js` assertion definitions and their negative
tests by reading them; the four new methodology registry entries against §33's fifteen fields;
`analytics.js` line by line against my Q2 and Q4 specifications.

**Not verified:**

- **I did not execute anything.** No browser, no JS runtime. Every runtime claim rests on the
  replication, whose fidelity is evidenced but not proven — hence §9.
- **I did not re-run `selfTest()`** or reproduce the coordinator's injection results. I am
  relying on their statement that `binding1` and `binding2` catch injected defects and state
  restores cleanly. I read the mechanism and it is sound; I did not observe it.
- **I did not review** `shell.js`, `charts.js`, `evidence.js`, `scenario.js` or `ai.js`. In
  particular `charts.js` renders the `alphaCallout` and I have not seen how it draws it, and
  `shell.js`'s `renderMetricValue` has no branch for the new `freshness.comparability` field —
  `data.js` flags this itself, meaning the Q5 comparability disclosure currently reaches the user
  **only** through `claim.caveat`. I could not confirm that path renders.
- **I did not verify the CSV/OCR fixtures, the policy surface, or scenario internals** beyond the
  `methodologyId` pointer in §7.4.

---

## 11. Summary of what must happen before HG1 can be decided

**Blockers (all small):**

1. `analytics.js` — wire `alphaCallout` to `getSMLPoints().verticalDistance`; retitle the SML
   block; carry the observation count and compounding basis in the chart label. (§2)
2. `metric.pl.absolute` — rename or suppress. (§7.2)
3. As-of date — decide the definition; align the three 2026-09-04 timestamps. (§7.3)
4. Scenario claims — repoint or null the `methodologyId`. (§7.4)
5. `betaDirectionConclusion` — apply the one-standard-error band; amend `binding1`. (§6)

**Corrections, not blockers:** the `weight-implied share` wording (§5.3); the
`insight.freshness.cnStale` calendar-day count (§7.5); `metric.correlation.referencePoint`'s
description of the benchmark row (§4.3); the stale `analytics.js:251` comment (§2.4).

**CP1:** correlation basis migration; per-position dated-FX cost basis; local bar read from the
accessor; three-bar waterfall and per-sleeve breakdown; denominator consistency; range-pill
scoping; registry completion.

**HG1 remains `REVISION_REQUIRED` and unapproved. I am not approving it and this document is not
an approval.** The corrections are real and substantial, and the data layer is now materially
more honest than it was. The screen is not yet.

---
---

# Part 2 — verification of the blocker fixes (round 4, final technical pass)

**Date:** 2026-09-06. Same author, same boundaries. **Still not an approval.**

**My harness is now validated.** The coordinator ran E1/E2/E3 live and every value matched my
replication exactly, including the full `fxDetail` tree and both interaction terms. That closes
the one caveat Part 1 carried: the numbers in this document are confirmed against the running
app, not only against my restatement of it.

**Verdict on the nine changes: eight are faithful. One is faithful to a specification of mine
that turns out to be arithmetically wrong**, and it is emitting a live claim because of it.
**Three of the four items below originate in my own text, not the implementer's work.**

---

## 12. What I checked, and what is right

| # | Change | Verdict |
|---|---|---|
| 1 | Beta band | Formula reproduced **verbatim**, not re-derived (`data.js:416–428`); English wording is mine verbatim; `se`, CI and σ-distance all exposed in `investorDetail`, `professionalDetail` and the Evidence packet (`standard_error`, `confidence_interval_95`, `sigmas_from_reference`). `binding1` rebuilt around the band and reads `se` from Evidence rather than recomputing. **Correct.** One wording defect, §13.2. |
| 2 | Scenario `methodologyId` | `methodology.scenarioImpactModel` is exemplary — it states plainly that the multiplier has no causal link to the scenario's own modification and that *"the scenario's stated modification is NOT an input to this multiplier."* That is a harder thing to write than to fix. Allocation claims correctly keep `methodology.exposure`, since those genuinely are recomputed exposures. **Correct.** |
| 3 | Gain/Loss rename | Label is now *"Value Change Implied by 1Y Time-Weighted Return (USD)"*; the contribution total is computed from the ledger (`TRAILING_YEAR_CONTRIBUTIONS_USD`) rather than hand-typed, so the caveat stays true if the ledger changes. **Correct, and better than I asked** — I only required rename-or-suppress. |
| 4 | As-of bounding | All three post-as-of timestamps corrected; `meta.asOfDefinition` records my recommendation **explicitly marked pending owner confirmation** rather than as decided. That is the right handling of a CP0 decision. **Correct** — with a consequence the owner must be told, §13.5. |
| 5 | Correlation labelling | `referencePoint` now names the benchmark row as a USD series; `methodology.correlation` populated, and its `fxTreatment` field says *"MIXED BASIS — a known, flagged inconsistency"* and cites the 0.0088 divergence. Recording a known inconsistency in the registry field that exists for exactly that purpose is the correct disposition. **Correct.** |
| 6 | `contributionToRisk` wording | Now *"the withheld segment's own RISK-CONTRIBUTION share (not its capital weight — those are different quantities, per §18.3)."* **Correct.** |
| 7 | Correlation bands | Five bands and the precision guard implemented verbatim, evaluated on a new full-precision `CORR_MATRIX_BASE` (not the 2dp displayed matrix — the right call, since a standard-error comparison cannot run on rounded input), left non-displayed so no CP1 basis migration is smuggled in. **Faithful. But see §13.1 — the specification it faithfully implements is wrong.** |
| 8 | Formatter split | Sound. `APP_fmtPct` (change) / `APP_fmtMagnitudePct` (magnitude) / `APP_fmtLevelPct` (level), all three throwing on null. I audited all 26 remaining call sites: the four corrections are right (benchmark volatility ×2, `RF_ANNUAL` ×2, top-5 concentration), and drawdown/alpha/line-distance/FX correctly stay signed. **One latent defect, §13.4.** |
| 9 | Bilingual | Careful and, on the statistics, faithful. Detailed verdict in §14. |

---

## 13. Four problems, three of them mine

### 13.1 — My §5.2 standard error was wrong, and it concealed a knife-edge. **BLOCKER.**

In Part 1 §5.2 I wrote: *"ρ(HK,CN) = 0.203, se = 0.048, nearest boundary 0.15 is 0.053 away =
1.1 se. So 'weakly co-moving' is assertable here, barely."*

**`se = 0.048` is the US/HK standard error. I carried the wrong row.** With
`se(ρ) = (1−ρ²)/√(n−1)` at ρ = 0.2026 and n = 252, the correct value is **0.0605**.

Recomputed properly, on both bases:

| Basis | ρ(HK,CN) | se | Distance to 0.15 | Ratio | Verdict |
|---|---|---|---|---|---|
| Local (displayed) | 0.202595 | 0.060529 | 0.052595 | **0.869 se** | **rank-only** |
| Base (classification basis) | 0.211391 | 0.060299 | 0.061391 | **1.018 se** | assertable |

Two things follow, and both are bad:

1. **The verdict flips depending on the basis** — the one thing §4.3 already flagged as
   unresolved. My guard made a CP1 open question load-bearing for a live sentence.
2. **On the basis I mandated, it clears the bar by 0.0011 in ρ units — 1.8% of one standard
   error.** A guard whose output turns on the third decimal place of a correlation is not
   performing the function I designed it for.

So the surface now renders, live: *"On the reporting-currency basis this pair is classified as
weakly co-moving (ρ=0.21), clearing the nearest classification boundary by more than one standard
error."* Every word is true, and the claim is hollow.

The rest of the matrix shows the rule is otherwise doing real work — **5 of 6 pairs are
correctly rank-only**, and only US/HK clears comfortably at 2.45 se. The rule is not vacuous;
the threshold is just set one notch too loose.

**Correction to my rule.** Require the **95% interval**, not the 68% one:

> A band label may be asserted only if the 95% confidence interval for ρ lies entirely within a
> single band — i.e. the nearest boundary is **≥ 1.96 se** away. Otherwise rank language only.

Under this, across both bases: **US/HK (2.45 se) qualifies; every other pair, including HK/CN on
either basis, does not.** The basis-sensitivity disappears (0.869 and 1.018 are both far below
1.96), and the HK/CN band sentence self-suppresses — which also resolves §13.3 at no extra cost.

I checked whether the simpler large-sample `se` is adequate here rather than assuming: Fisher's
z-transform gives a 95% CI for ρ(HK,CN) of `[0.0902, 0.3266]` against the naive `[0.0932,
0.3296]`. Close enough at n = 252 that the simple formula stands; both straddle the 0.15
boundary, confirming rank-only. No change needed to the `se` formula itself.

**This is my error. The implementation is correct against what I wrote.**

### 13.2 — "margin of error (±0.04)" mislabels one standard error. **BLOCKER (both languages).**

My §6 specified, and the implementation renders verbatim:

> "At 252 daily observations the estimate's **margin of error (±0.04)** spans 1.0…"

`±0.04` is **one** standard error — roughly a 68% interval. "Margin of error" is read by
essentially every lay reader as the 95% figure, which here is **±0.082**. So a claim whose entire
purpose is to convey imprecision **understates that imprecision by half**.

The conclusion is unharmed — the hedge points the conservative way either number — but a
precision statement that is itself imprecise about its precision is not acceptable in the one
sentence on the surface whose job is that. Required wording, both languages:

> `…the standard error of the estimate is ±0.04, and the 95% confidence interval [0.91, 1.08]`
> `spans 1.0, so this sample does not distinguish it from moving with the market.`

`BETA_CI95` already exists and is already rendered in `investorDetail`; this only promotes it
into the sentence that needs it. **Mine, not the implementer's.**

### 13.3 — The band sentence quotes a ρ the user cannot see. **BLOCKER, unless §13.1 lands.**

The band sentence quotes **ρ = 0.21** (base basis). The matrix rendered directly above it shows
**0.20** (local basis, 2dp). Two different numbers for the same cell, on one screen, with the
reconciliation available only by opening the methodology entry.

This is precisely the defect class this entire pass was convened to close — a claim whose numeral
disagrees with the adjacent displayed numeral. The `"On the reporting-currency basis"` prefix is
a partial hedge, but it does not tell a reader that the matrix they are looking at is on a
*different* basis.

**Adopting §13.1 removes this automatically**, because the sentence stops being emitted. If the
1-se threshold were kept instead, the numeral would have to be dropped from the sentence.

### 13.4 — Risk-contribution shares use the sign-stripping formatter. **Latent; one-word fix.**

`data.js:641` and `:650` format contribution shares with `APP_fmtMagnitudePct`, which applies
`Math.abs()`. Same at `:1284`/`:1291` for `CONTRIB_AVAILABLE_SUM`.

A risk contribution can legitimately be **negative**: `MCTR_i = w_i·σ_i·ρ_{i,P}`, and `ρ_{i,P} < 0`
whenever a sleeve is negatively correlated with the portfolio — a genuine hedge, which is exactly
the case where the sign carries the entire meaning. `Math.abs()` would render a −8% hedging
contribution as "8%", reversing it.

All four values are positive in this dataset (US 46.4%, HK 45.1%, bonds 0.7%), so nothing is
wrong on screen today. But this is the formatter split's own logic: a share is a **level**, and
`APP_fmtLevelPct` preserves sign while still suppressing the spurious `+`. **Change these four
sites to `APP_fmtLevelPct`.** The exceedance-rate sites (`:1220`, `:1228`) are also levels but
are non-negative by construction, so they are cosmetic only.

### 13.5 — A consequence of my as-of rule the owner must be told. **Not a defect.**

Item 4 correctly moved `us_equity` from `LIVE` to `END_OF_DAY 2026-09-03 16:00 ET`. That is
entailed by my §7.3 definition: **under "the as-of date is the latest instant at or before which
every required input has a print," a snapshot as of a past close can never contain a LIVE input.**

Consequence: **the prototype no longer exercises the `LIVE` freshness state anywhere.** That will
look like a regression in demo coverage at the gate, and it is not — it is the rule working. But
it should be said out loud in the gate package, together with the corollary: `LIVE` is meaningful
only in an "as of now" view, which is a different product mode from a dated snapshot, and V1
needs to decide whether it has both. That is a product decision, not mine.

---

## 14. The Chinese — statistical fidelity

I checked the claims where a translation could shift a statistical commitment. The general
approach is right: the derivation functions take `lang` and derive both languages from the **same
values**, so a Chinese claim cannot go stale against a number the way a hand-translated snapshot
would. That is the correct architecture and it is what makes the rest checkable.

### 14.1 The beta hedge — **confirmed equivalent. No overstatement or understatement.**

> 您投资组合的贝塔(β)与市场大体一致(β=0.99)。基于252个交易日的观测,该估计值的误差范围(±0.04)覆盖了1.0,因此本样本无法将其与「与市场同步波动」区分开。

Clause by clause against the English:

| Chinese | Back-translation | English | Match |
|---|---|---|---|
| 与市场大体一致 | broadly in line with the market | "moved broadly in line with the market" | ✓ |
| 基于252个交易日的观测 | based on 252 trading days of observations | "At 252 daily observations" | ✓ |
| 误差范围(±0.04)覆盖了1.0 | margin of error (±0.04) covers 1.0 | "margin of error (±0.04) spans 1.0" | ✓ (both carry §13.2's defect identically) |
| 本样本无法将其与「与市场同步波动」区分开 | this sample is unable to distinguish it from "moving in sync with the market" | "this sample does not distinguish it from moving with the market" | ✓ |

Terminology is correct throughout: 标准误 (standard error), 置信区间 (confidence interval),
标准误差 not confused with 标准差. The non-hedged branches carry 且差异超过一个标准误 ("and the
difference exceeds one standard error"), symmetric with the English.

Two deliberate judgments, both of which I accept:

- **无法 ("is unable to") is marginally stronger than "does not."** Statistically this is the
  *better* framing — it locates the failure in the sample's power rather than in the test — and
  it is the standard Chinese phrasing for failing to reject. It does not claim β *is* 1. **Not an
  overstatement.**
- **The Chinese subject is the estimate (贝塔), the English subject is the portfolio.** The
  Chinese is arguably tighter, since the uncertainty attaches to the estimate. **Fine.**

**Verdict: the Chinese makes the same statistical claim as the English.** The one flaw is shared,
inherited from my specification, and must be fixed in both (§13.2) — it is not a translation
defect.

The correlation band Chinese is likewise faithful: 超出最近的分类边界一个标准误以上 = "exceeding
the nearest classification boundary by more than one standard error," matching the English
exactly. (It should stop being emitted under §13.1, but the translation is correct.)

### 14.2 One real translation defect — a P6 word I vetoed in English returns in Chinese. **BLOCKER-lite.**

`metric.sml`'s Chinese `explanationSimple` reads:

> 该直线显示的是:在本区间内,处于各贝塔水平的投资组合**本应取得**多少收益,才能与基准…相匹配。

**本应取得 means "ought to have obtained."** My §2.3 specifically vetoed *"what a portfolio with
this beta 'should' have returned"* in English, on the grounds that a reader carries "should"
forward as an expectation, and the English was duly changed to *"the return a portfolio at each
beta **would have needed**… to match."* The Chinese reintroduces exactly the normative modal that
was removed.

The trailing 才能…相匹配 ("in order to match") does supply conditional framing and softens it, so
this is a lesser instance than the original English — but 本应 carries counterfactual obligation
on its own, and P6 is one of the invariants that does not have a "lesser instance" tier.

**Required:** 需要取得 or 需达到多少收益率 ("would need to obtain / would need to reach"), which
is the neutral conditional and matches the English commitment exactly.

I checked the other P6-sensitive Chinese strings and they are clean: 均非预测(P6),
并非对未来损失的限定, 并非对未来位置的预测, and the downward-slope note
(不应被「修正」为常规的向上倾斜) are all faithful.

### 14.3 Not checked

I verified statistical and P6-sensitive wording only. **I did not assess register, fluency,
terminology consistency against a glossary, or whether 简体 is right for the intended market.**
None of that is mine. If nobody has reviewed the Chinese for anything other than statistics, that
gap should be recorded rather than assumed closed by this section.

---

## 15. Did anything break?

**No numeric regression, by inspection.** None of items 1–9 touches the generation chain:
sleeve weights, the four sleeve series, the FX series, the base combination, or any statistic
derived from them. The changes are a new `BETA_SE` block (additive), a non-displayed
`CORR_MATRIX_BASE` (additive), freshness *timestamps* (no numeric consumer), display formatters,
labels, `methodologyId` pointers, and `i18n`. `metric.pl.absolute`'s **value expression is
unchanged** — only its label and caveat moved.

I re-ran my harness against the corrected chain and every Part 1 figure reproduces unchanged:
return `+3.8881%`, local `+4.4453%`, FX `−0.5572%`, beta `0.994004`, alpha `+9.3346%`,
vertical distance `+8.9373%`, vol `14.9103%`, Sharpe `0.028534`, TE `8.2779%`, VaR `−0.016164`,
MDD `−15.1994%`, contribution shares `46.36 / 45.10 / withheld / 0.74`.

**But I am asserting this from source reading, not execution.** E5 below closes it.

One thing I could not rule out by inspection: `APP_fmtPct` and friends now **throw** on null.
That is the right design, but it converts a class of silent defect into a page-load exception,
and the blast radius depends on call sites in `shell.js`, `charts.js`, `evidence.js` and
`scenario.js` — none of which I have read. If any of those passes a null through a claim's
`formatted` field on a code path the current fixture does not exercise, the throw is now fatal
where it was previously an em-dash. `selfcheck.run()` at 23/23 does not cover that, since it
exercises the data layer only (Part 1 §5.4). **Worth one deliberate click-through of every
surface before the gate package, including the INSUFFICIENT_DATA and scenario paths.**

---

## 16. Runtime expressions

**E5 — confirm no numeric regression and capture the band state.**

```js
(function () {
  var d = window.APP.data, v = function (i) { var c = d.getMetric(i); return c && c.value; };
  var cm = d.getCorrelationMatrix();
  return JSON.stringify({
    ret: v("metric.return.1y"), fx: v("metric.fxAttribution"), beta: v("metric.beta"),
    alpha: v("metric.alpha"), vol: v("metric.volatility"), sharpe: v("metric.sharpe"),
    te: v("metric.trackingError"), var95: v("metric.var95"), mdd: v("metric.maxDrawdown"),
    vd: d.getSMLPoints().verticalDistance,
    contrib: d.getContributionToRisk().segments.map(function (s) { return [s.label, s.value]; }),
    plValue: v("metric.pl.absolute"), plLabel: d.getMetric("metric.pl.absolute").label,
    bandInfo: d._internal && d._internal.correlationBandInfo,
    displayedHkCn: cm.matrix[cm.labels.indexOf("HK Equity Sleeve")][cm.labels.indexOf("CN Equity Sleeve")],
    corrConclusion: cm.claim.conclusionQuick
  }, null, 1);
})()
```

Expected: every numeric field identical to Part 1 §9's E1 values; `plLabel` the new string;
`bandInfo.hkCn.rhoBase ≈ 0.211391`, `bandInfo.hkCn.se ≈ 0.060299`,
`bandInfo.hkCn.assertable === true`;
`displayedHkCn === 0.2`; and `corrConclusion` **containing** the band sentence with `ρ=0.21`.
**That last pair — 0.21 in the sentence, 0.2 in the matrix — is §13.3 on screen.**

**E6 — confirm the beta band and its Chinese render from the same values.**

```js
(function () {
  var m = window.APP.data.getMetric("metric.beta"),
      ev = window.APP.data.getEvidence("metric.beta");
  return { en: m.conclusionQuick, zh: m.i18n && m.i18n.zh && m.i18n.zh.conclusionQuick,
           se: ev && ev.standard_error, ci: ev && ev.confidence_interval_95,
           sigmas: ev && ev.sigmas_from_reference };
})()
```

Expected: both strings carry the hedge; `se ≈ 0.041961`; `ci ≈ [0.9118, 1.0762]`;
`sigmas ≈ 0.143`.

**E7 — the null-throw blast radius, which is the one thing I genuinely cannot see.** Please
click through Analytics, Overview, Holdings, Transactions, Scenario Lab and the Methodology
overlay, open the Evidence panel on `metric.sortino` (INSUFFICIENT_DATA), the CN
contribution segment (withheld), `600519.SS` (missing cost basis) and `tx-0029` (missing FX),
and report **any** console exception. A thrown formatter is now fatal, not cosmetic.

---

## 17. Final blocker list

**Blockers — four, all small, three of them corrections to my own specification:**

1. **Tighten the correlation band guard from 1 se to 1.96 se** (§13.1). *Mine.* Also resolves
   §13.3 with no further change. `binding3`'s companion assertion updates with it.
2. **Replace "margin of error (±0.04)" with the standard error plus the 95% CI**, English and
   Chinese (§13.2). *Mine.* `BETA_CI95` already exists.
3. **Chinese `metric.sml.explanationSimple`: 本应取得 → 需要取得** (§14.2). *Mine, in the sense
   that I vetoed the English and did not think to check the translation of the same idea.*
4. **Risk-contribution shares: `APP_fmtMagnitudePct` → `APP_fmtLevelPct`** at `data.js:641`,
   `:650`, `:1284`, `:1291` (§13.4). Latent, one word each.

**Must be in the gate package, not fixed:** the `LIVE` consequence of the as-of definition
(§13.5), flagged as entailed-by-the-rule rather than as a regression, with the "as of now vs
dated snapshot" question named as an open product decision.

**Recommended before the package is assembled:** the E7 click-through (§15).

**Still CP1, unchanged from Part 1 §11:** correlation basis migration; per-position dated-FX
cost basis; the local bar read from `getFxAttributionDetail()` rather than by subtraction; the
three-bar waterfall and per-sleeve breakdown; denominator consistency; range-pill scoping;
registry completion.

**Cleared since Part 1:** all five Part 1 blockers. I re-read `analytics.js` to check this rather
than taking it on report, since the coordinator's list of nine changes did not mention that file:

- `analytics.js:533` now passes `distanceCallout: { …, distance: smlData.verticalDistance }` —
  concept 4, the field `data.js` exposed for exactly this. The `alphaCallout` misuse is gone.
- `analytics.js:453` renders `an.realizedReturnVsBeta` = *"Realized return vs. beta — ex-post
  market line (trailing 1Y)"*, my §2.4 wording verbatim, with a matching Chinese key.
- `analytics.js:528` builds the window label from the observation count and the dated window;
  `xAxisTitle` and `yAxisTitle` are both present and name their bases.
- The ex-post line annotation is mounted above the chart as a permanent paragraph rendering
  `metric.sml.professionalDetail`, which carries the line equation, the realized benchmark
  return, Rf, the downward-slope explanation and the concept-3/concept-4 distinction.

**One correction to my own summary:** `analytics.js:262` still computes
`localVal = retClaim.value - fxClaim.value`. That is Part 1 §2.4, which I ruled **CP1, not a
blocker** — the number is exact under the current identity. It is unchanged and correctly so; I
should not have implied the attribution block was rewired.

---

## 18. What I verified and what I did not, this round

**Verified:** the `BETA_SE` formula character by character against mine; the band boundaries and
precision guard against my §5.2; the guard's actual verdict on all six sleeve pairs on both
bases, at full precision, which is how I found my own error; all 26 formatter call sites and
their signed/magnitude/level classification; the four new and corrected registry entries against
§33; the Chinese for every statistically or P6-loaded claim; the freshness timestamps against the
as-of definition.

**Not verified:**

- **I executed nothing this round either.** §15's "no regression" is source reading; E5 closes it.
- **I did not re-run `selfcheck.run()` or `selfTest()`**, and I have not read the two new
  assertions' negative tests, only the assertion bodies. 23/23 is the coordinator's observation,
  not mine.
- **I did not read `shell.js`, `charts.js`, `evidence.js` or `scenario.js`** — hence E7. The
  null-throw change specifically raises the cost of that gap.
- **I assessed the Chinese for statistical and P6 fidelity only** (§14.3). Register, fluency and
  glossary consistency are unreviewed by anyone as far as I know.
- **No golden fixtures for the engine in `src/` exist**, and `methodology/METHODOLOGY_REGISTRY.md`
  and `DATA_SUFFICIENCY.md` still do not. Unchanged and still open.

**HG1 remains `REVISION_REQUIRED` and unapproved.** I am not approving it, this document is not
an approval, and the four items in §17 are open. Three of them are mine to have gotten right the
first time.

---
---

# Part 3 — sign-off on the four blockers

**Date:** 2026-09-06. Short by design; this is not a re-verification of the chain.
**Still not an approval. HG1 remains `REVISION_REQUIRED`.**

I checked all four in source rather than accepting the report, since that is the whole reason
this role is separate from the one that implemented them.

## 19. The four blockers — all correctly resolved

| # | Check | Evidence |
|---|---|---|
| 1 | Band guard | `data.js:582` — `correlationBandNearestBoundaryDistance(rho) >= 1.96 * correlationBandStandardError(rho, n)`. My rule exactly. HK/CN sits at **0.869 se (local)** and **1.018 se (base)**, both far below 1.96, so the clause is dormant on **either** basis — the basis-sensitivity is eliminated, not narrowed, as you say. The `ρ=0.21` numeral disappears with it, closing §13.3 as predicted. The clause text itself was also updated to say 1.96 / 95% in both languages (`data.js:962`, `:965`) — correct for the dormant path, which is the right kind of care. |
| 2 | Beta wording | `data.js` `betaDirectionConclusion` now takes `ci95` and both branches render standard error **and** the 95% CI. `BETA_CI95` threaded from `data.js:423`, never recomputed. Confirmed both call sites (`:1130`, `:1151`) pass it. |
| 3 | P6 modal | `data.js:1367` reads 需要取得多少收益. The normative 本应 is gone. |
| 4 | Contribution sign | `APP_fmtLevelPct` at all four sites (`:669`, `:678`, `:1328`, `:1335`), including the Chinese remainder string. A hedging sleeve will now render its minus sign. |

## 20. The Chinese beta hedge — confirmed equivalent

> 基于252个交易日的观测,**标准误为±0.04,95%置信区间为 [0.91, 1.08],覆盖了1.0**,因此本样本无法将其与「与市场同步波动」区分开。

Both quantities are present, with the correct technical terms and the same force:

- **标准误** is precisely *standard error* — not 标准差 (standard deviation), and no longer
  误差范围 (*margin of error*), which was the §13.2 defect. **The defect is gone in Chinese too.**
- **置信区间** is the standard term for *confidence interval*, correctly qualified 95%.
- **Attachment is correct, and this is the part that could have gone wrong invisibly.**
  覆盖了1.0 follows immediately after the CI clause, so it attaches to the interval, not to the
  standard error — matching the English, where "spans 1.0" attaches to the CI. Had it attached to
  ±0.04 it would be a different claim about a different interval.
- The closing hedge is unchanged and was confirmed equivalent in Part 1 §14.1.

**Confirmed: same two quantities, same force, same attachment.**

## 21. One residual inconsistency — mine, latent, not blocking

Tightening the correlation guard to 1.96 se left **the beta directional guard at 1 se**
(`Math.abs(beta - 1) <= se`). Those are now two different thresholds for the same class of
judgment — "may I assert which side of a boundary an estimate falls on" — with nothing recording
why they differ.

They should not differ. A directional claim at 1 se carries roughly a **1-in-6 chance of pointing
the wrong way**, which is not a standard worth defending in a product whose purpose is to
suppress claims it cannot support. My §6 wording ("more than one standard error") was the looser
half of my own rule and I should have harmonised it when I tightened the other half.

**This changes nothing on screen today** — beta is at 0.143 se, so the hedge fires under either
threshold, which is why it is not a blocker. But two things follow for the record:

1. Harmonise both guards to **1.96 se (95%)** as the single documented threshold for asserting a
   categorical claim about an estimate's position relative to a reference point or boundary.
2. When harmonised, the currently-unreachable non-hedged branches must have their text updated:
   *"by more than one standard error"* / *"且差异超过一个标准误"* would both become wrong the
   first time beta moves far enough to reach them.

I am flagging this rather than adding it to the blocker list: it is dormant, it is a
specification tidy-up rather than a live defect, and it belongs in the registry alongside the
rest of the threshold set. **If you would rather carry a fifth item than ship a documented
inconsistency, that is a defensible call and I would not argue against it** — but I am not
asserting it is required.

## 22. Your two recorded-as-open items — both correct

**`LIVE` freshness.** Correct, and framed correctly. It is entailed by the as-of rule, not a
defect and not a demo regression to be undone. One sharpening for the package: the question to
put to the owner is not "should `LIVE` come back" but **"does V1 have an 'as of now' mode at
all, distinct from a dated snapshot?"** If yes, `LIVE` is meaningful in that mode and the as-of
bounding rule applies only to dated snapshots; if no, `LIVE` has no referent in V1 and should be
removed from the vocabulary rather than left unexercised. Either answer is clean; leaving the
state defined but unreachable is the only bad outcome.

**Chinese review gap.** Correct to record. Two precisions so the record is neither over- nor
under-stated:

- What I checked was **not** all 24 claims. I checked the Chinese for the claims where a
  translation could shift a statistical or P6 commitment: `metric.beta`, the correlation
  conclusion and band clause, `metric.var95`, `metric.sml`, and the contribution remainder
  string. Statistical semantics and modal force only.
- The gap is therefore: **register, fluency, terminology consistency against a glossary, and the
  ~19 claims I did not read at all, are unreviewed by anyone.** It is also worth recording that
  no reviewer with that competence has been engaged on this project, so this is an unstaffed gap
  rather than a pending task.

## 23. Sign-off

The four blockers from §17 are **correctly resolved**. I need no further runtime evidence: the
band clause's disappearance follows deterministically from `data.js:582` and the two σ-distances
I computed independently, and you have separately observed the rendered strings.

If you want one belt-and-braces confirmation for the package, this is the pivot of blocker 1 and
costs nothing:

```js
window.APP.data._internal.correlationBandInfo.hkCn
```

Expected: `rhoBase ≈ 0.211391`, `se ≈ 0.060299`, **`assertable === false`**.

**What remains open at this gate, from my side:** nothing blocking. §21 is a dormant
specification inconsistency; §22's two items are correctly recorded as open; and the CP1 list in
§17 is unchanged. The standing gaps in my own deliverables — no
`methodology/METHODOLOGY_REGISTRY.md`, no `DATA_SUFFICIENCY.md`, no golden fixtures for the
engine in `src/` — are unchanged and are not HG1 items.

**HG1 remains `REVISION_REQUIRED`, ACTIVE and UNAPPROVED. Only the human product owner can change
that, and nothing in this document or in a 23/23 self-check does.**
