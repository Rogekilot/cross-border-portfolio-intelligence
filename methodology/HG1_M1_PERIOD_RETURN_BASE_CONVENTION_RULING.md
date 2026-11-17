# HG1 defect M1 — methodology ruling: the base of a trailing-window return, and where that convention is allowed to live

**Author:** `quant_analyst`, delegated subagent, out-of-DAG advisory worker (ADR-0028 §1.5), 2026-09-10.
**Requested by:** the parent orchestrator (`pm-01`), on behalf of the frozen HG1 prototype.
**Authority:** PD-0014 §3 — a financial-truth contract is reserved to `quant_analyst`;
`product_manager` and `designer` may not invent a resolution. `roles/quant_analyst.json`
→ `may_decide`: methods, conventions, data-sufficiency thresholds.
**Subject:** `designs/hg1-prototype-v2/` — the chart-vs-engine trailing-1Y return divergence.

> **This document contains no approval of anything.** HG1 remains **`REVISION_REQUIRED`** and
> `awaiting_human`. `quant_analyst` cannot approve a human gate and does not do so here. Nothing
> below clears the prototype, the gate, or M2/M3.

**Ruling vs. recommendation.** Every numbered **RULING** is binding within my authority. Every
**RECOMMENDATION** is engineering or UI judgment, offered so the ruling is actionable, and may be
replaced by anything that satisfies the ruling.

## Method, stated so it can be discounted appropriately

I did **not** execute the prototype: this role has no browser and there is no network egress.
Instead I wrote an **independent port** of `js/data.js` sections 0–2 — the `mulberry32` PRNG, the
Box-Muller `gaussian()`, the 504-weekday calendar, the factor model, the holdings-derived sleeve
weights, the FX combination and `cumulativeIndex` — in Python, and evaluated every candidate
convention on the resulting series. The harness is
`methodology/hg1_m1_repro/reproduce_m1.py`; it is read-only, imports nothing from the prototype at
runtime, and prints every figure quoted below so a reviewer can re-run it rather than trust me.

`mulberry32` is exact 32-bit integer arithmetic and reproduces bit-for-bit. Box-Muller calls
`log`/`cos`/`sqrt`; Python and V8 both use the platform libm at double precision, so agreement is
to ~1 ulp per call — which cannot move a figure quoted to 0.01 pp. **The port is corroborated:** it
independently reproduces all four numbers the PM measured from a live run (+5.18 / +3.89 / +8.86 /
+8.99) to every digit the PM reported. Chart-side quantities are recomputed here from the *same
formulas* `js/charts.js` uses, each quoted by file:line in §2.

Hand-derived fixtures in §9 are arithmetic I performed on numbers I chose, not on the fixture, and
are checkable by a reader with no code at all. **No expected value anywhere in this document was
obtained by running the implementation and recording what it produced.**

---

# Part 0 — The question, stated before I answer it

A cumulative-performance chart is labelled with a trailing window. It plots a level series and
prints a return for that window. A deterministic engine publishes a fact
(`metric.return.1y`) that names the same metric and the same window. They disagree.

Three questions follow, and only the first two are quant questions:

1. **Why do they disagree?** (§1)
2. **Which convention is canonical?** (§3) — the reason a quant is being asked rather than a
   designer.
3. **Where is that convention allowed to live?** (§4) — a P1 question, and the one that decides
   *what code changes*.

---

# Part 1 — Reproduction, and the true cause of each gap

## 1.1 The calendar and the seam

| Quantity | Value |
|---|---|
| `DATES.length` (`TRADING_DAYS`) | 504 |
| `DATES[0]` … `DATES[503]` | 2024-09-30 … 2026-09-03 |
| `sliceRange("1Y")` → `i1y` | **252** |
| `DATES[i1y - 1]` = index 251 | **2025-09-16** ← engine's base date |
| `DATES[i1y]` = index 252 | **2025-09-17** ← chart's first plotted date |
| points the chart draws | 252 |
| portfolio return **on** 2025-09-17, `r_P[252]` | **−1.2294 %** |
| benchmark return **on** 2025-09-17, `r_B[252]` | **−1.4845 %** |

## 1.2 The four figures, reproduced

| Quantity | Chart | Engine | Δ (chart − engine) |
|---|---|---|---|
| Portfolio trailing-1Y return | **+5.1812 %** | **+3.8881 %** | **+1.2931 pp** |
| Benchmark trailing-1Y return | −3.6770 % | −5.1069 % | +1.4299 pp |
| vs. benchmark (difference) | **+8.8581 %** | **+8.9949 %** | **−0.1368 pp** |

Matches the PM's independently measured +5.18 / +3.89 / +8.86 / +8.99 exactly.

## 1.3 The cause: one cause, not two

**Both gaps are the one-trading-day base offset, in full. There is no residual.**

The engine (`js/data.js:391`) divides by `portfolioIndex[i1y − 1]`; the chart
(`js/charts.js:476`, `:496`) divides by `a[0]`, which after `js/data.js:2537`'s
`portfolioIndex.slice(i1y)` is `portfolioIndex[i1y]`. The two bases differ by exactly one
compounding factor, so:

> **R_engine = (1 + R_chart) · (1 + r[i]) − 1**, equivalently
> **R_engine − R_chart = (1 + R_chart) · r[i]**

Checked numerically, every selector period, residual to machine epsilon:

| range | `r[i]` | observed (engine − chart) | predicted `(1+R_chart)·r[i]` | residual |
|---|---|---|---|---|
| 1M | +0.3772 % | +0.3701 % | +0.3701 % | −6.2e−17 |
| 3M | +0.0347 % | +0.0349 % | +0.0349 % | −9.7e−17 |
| 6M | −1.2115 % | −1.1179 % | −1.1179 % | +1.0e−17 |
| **1Y** | **−1.2294 %** | **−1.2931 %** | **−1.2931 %** | **−2.4e−17** |
| ALL | −0.6012 % | +0.0000 % | −0.6554 % | +6.6e−03 ← see §5 |

The 1Y residual is **exactly zero to 17 significant figures**. Nothing else is happening.

## 1.4 Why the relative figure looks nearly right, and why that is the more dangerous number

The −0.1368 pp is not a smaller defect. It is the **difference of two large, same-signed errors
that nearly cancel**:

```
relative Δ = (chart_P − engine_P) − (chart_B − engine_B)
           = (+1.2931 pp)         − (+1.4299 pp)
           = −0.1368 pp                              ← exact, reproduced
```

The cancellation is a coincidence of this fixture: both series fell on the seam day (−1.23 % and
−1.48 %), because the portfolio has β ≈ 0.99 to the benchmark and the seam day was a market-wide
down day. Had the seam day been idiosyncratic to one sleeve, the relative error would have been
of the same ~1.3 pp order as its components.

**This matters for triage.** A reviewer who ranks these defects by observed magnitude will
conclude the relative figure is "nearly right" and the return figure is the real problem. That is
backwards: **both components of the relative figure are wrong by ~1.3–1.4 pp**, and the small
visible residue is luck. Any repair that fixes the 1.29 pp and leaves the 0.14 pp as accepted
rounding would be repairing the symptom that happened to be visible.

## 1.5 Correction to the brief's premise — stated plainly, as instructed

The brief states that the one-trading-day base offset "explains the −0.14 pp on the relative
figure. It does NOT account for 1.29 pp on the portfolio return, which may involve an FX-inclusive
base rather than the slice index alone."

**That is incorrect, and the FX hypothesis is disconfirmed.** The base offset accounts for
*both* gaps completely (§1.3, residual 0). FX is not implicated, and I tested it directly by
running both conventions on the FX-inclusive *and* the local-currency index:

| | base-currency (FX-inclusive) | local-currency (FX at start) |
|---|---|---|
| chart convention | +5.1812 % | +5.7412 % |
| engine convention | +3.8881 % | +4.4453 % |
| **offset** | **+1.2931 pp** | **+1.2959 pp** |

The offset is present, and essentially identical, in a series that contains **no FX at all**.
The FX leg is a red herring; `PERIOD_RETURN` and the chart read the *same* `portfolioIndex`
(`js/data.js:2537`), so they cannot differ by an FX treatment even in principle.

The intuition behind the brief's premise — that one day cannot be worth 1.29 pp — is what fails.
The error is not bounded by a "typical" day; by §1.3 it is **the seam day's return, levered by the
gross period return**, and the seam day here was a −1.23 % day. §9's hand fixture shows a single
−10 % seam day producing an 11 pp error that flips the sign of the answer.

## 1.6 M1 is not a 1Y-only defect

| range | chart | engine | Δ pp |
|---|---|---|---|
| 1M | −1.8767 % | −1.5066 % | −0.3701 |
| 3M | +0.4253 % | +0.4602 % | −0.0349 |
| 6M | −7.7296 % | −8.8475 % | **+1.1179** |
| 1Y | +5.1812 % | +3.8881 % | **+1.2931** |
| ALL | +9.0144 % | +9.0144 % | 0.0000 (for the wrong reason — §5) |

Four of the five selector periods are wrong; the sign of the error is not even consistent. Only
1Y has an engine counterpart to be caught against, which is why only 1Y was measured. **6M is
wrong by 1.12 pp and nobody has reported it**, because no engine fact exists at 6M to contradict
it. That is the general shape of the problem: the chart is currently the *only* publisher of a
return for 1M/3M/6M/ALL, and it publishes them under a convention that is wrong at 1Y — the one
period where it can be checked.

---

# Part 2 — Trace: exact date, index and base semantics of every site

All paths relative to `designs/hg1-prototype-v2/`.

| # | Site | file:line | Index / base semantics | Dates it actually covers |
|---|---|---|---|---|
| 1 | `sliceRange(range)` | `js/data.js:374-377` | `max(0, 504 − n)`; `1Y → n=252 → 252`. Returns a **start index into a level array**, used unchanged as a start index into a **return array**. | — |
| 2 | `i1y`, `pr1y` | `js/data.js:382-384` | `pr1y = portfolioReturns.slice(252)` = the **252 daily returns** `r[252..503]`. | returns dated 2025-09-17 … 2026-09-03 |
| 3 | Declared window | `js/data.js:387-389` | `WINDOW_START_DATE = DATES[252]` = 2025-09-17; `WINDOW_END_DATE = DATES[503]` = 2026-09-03; `WINDOW_OBS_COUNT = pr1y.length` = **252**. | **252 return observations, 2025-09-17 → 2026-09-03** |
| 4 | Engine period return | `js/data.js:391-393` | `index[503] / index[i1y − 1 ≥ 0 ? i1y − 1 : 0] − 1` → base `index[251]` = close of **2025-09-16**. Equals `Π(1+r[k])−1` over `k=252..503` — **exactly the 252 observations declared at #3**. | 252 returns, matches #3 |
| 5 | Chart series slicing | `js/data.js:2534-2538` (`getPortfolioSeries`) | `DATES.slice(252)`, `portfolioIndex.slice(252)`, `benchmarkIndex.slice(252)` → 252 **level points**, first = `index[252]` = close of 2025-09-17. **No base point is emitted.** | 252 levels, 2025-09-17 … 2026-09-03 |
| 6 | Chart end labels | `js/charts.js:486-506`, formula at `:496-497` | `retAEnd = a[lastIdx] / a[0] − 1`, base = first *plotted* level = `index[252]`. Compounds only `r[253..503]` = **251 returns**. | 251 returns, **2025-09-18** … 2026-09-03 |
| 7 | Chart period-relative callout | `js/charts.js:475-484`; design rationale at `:467-473` | `retAAll = a[last]/a[0] − 1`, `retBAll = b[last]/b[0] − 1`, `relDiff = retAAll − retBAll`. Same base defect on both legs. | 251 returns each |
| 8 | Chart hover readout | `js/charts.js:549-550` | `a[idx]/a[0] − 1` — same base, so every hover value carries the same offset. | 251-return basis |
| 9 | `metric.benchmarkRelative` | `js/data.js:1246` | `PERIOD_RETURN − BENCHMARK_PERIOD_RETURN`; arithmetic difference of two simple returns, both based at index 251. | 252 returns each |
| 10 | Proof Packet window | `js/data.js:1179` (`investorDetail`), `js/data.js:2607` (`_internal.windowStart/windowEnd/windowObservationCount`) | Publishes `252 observations, 2025-09-17 to 2026-09-03`. | 252 return observations |
| 11 | Chart callers | `js/surfaces/overview.js:272-291`, `js/surfaces/analytics.js:281-290` | Pass `getPortfolioSeries({range})` straight through; `currentRange` defaults `"1Y"`. Callers add no convention of their own. | — |
| 12 | Display formatters | `js/charts.js:89-93` (`pctText`), `js/data.js:~175` (`APP_fmtPct`) | Both `(v>=0?"+":"") + (v*100).toFixed(1) + "%"` — **identical**, so equal inputs give character-identical strings. | — |

### 2.1 The single sentence this table reduces to

**A series of N level points contains only N − 1 inter-point returns.**

The engine treats the 252 dates as **252 return observations** and correctly reaches *outside* the
plotted range for its base. The chart treats the same 252 dates as **252 level points**, silently
demotes the first to an origin contributing no return, and therefore publishes a **251-observation
return under a 252-observation window label**.

Both are internally coherent. They are answers to different questions. What is not permitted is
that they carry the same label.

### 2.2 The PD-0014 breach, precisely located

`js/data.js:1179`/`:2607` declare the window of `metric.return.1y` as *252 observations,
2025-09-17 to 2026-09-03*. That declaration is **correct** — it describes #4 exactly. The chart
drawn beside it prints +5.2 % under axis ticks that begin 2025-09-17. The Proof Packet therefore
names precisely the window the chart draws and reports a different return for it. PD-0014 §2.4:
*"The Proof Packet must not be able to refute the sentence that links to it."* Here it can, and
the sentence it refutes is a rendered number rather than a prose claim — which is why every
existing claim-traceability control missed it (§7.1).

---

# Part 3 — RULING 1: the canonical convention

## RULING 1(a) — The base of a trailing-window return is the last observation **strictly before** the window. The engine's convention is canonical; the chart's is wrong.

> A return is a property of the **interval between two valuation points**, not a property of a set
> of valuation points. A window containing **N** return observations is bounded by **N + 1**
> valuation points: one **base** — the close immediately preceding the first in-window return —
> and N in-window closes.
>
> Therefore, for a window `W = [d₁ … d_N]` of N dated return observations on a level series `L`
> indexed by trading day, with `d₁` at index `i`:
>
> **R(W) = L[i + N − 1] / L[i − 1] − 1 = Π_{k=i}^{i+N−1} (1 + r[k]) − 1**
>
> The dates that name the window name the **return observations**, not the level points. `L[i−1]`
> is the base; it is dated `d₀`, one trading day before `d₁`, and it is **not** a member of the
> window.

**Standing of this convention.** This is the ordinary industry method, not a choice I am making.
GIPS 2020 provisions 2.A.1–2.A.2 require period returns to be time-weighted and geometrically
linked *from the period's beginning value*, where the beginning value is the value at the **end of
the prior period** — the prior close, not the first close inside the period. CFA Institute's
time-weighted-return chaining is the same construction: each sub-period return is measured from
the previous sub-period's ending value. A trailing 1-year total return on a daily price series is
universally `P_t / P_{t−252} − 1`, in which both endpoints are closes and the 252 return
observations lie strictly *after* the denominator's date.

**Consequences, all four of which the engine already satisfies and the chart does not:**

1. The 252 return observations used by `PERIOD_RETURN` are the same 252 used by `ANNUAL_VOL`,
   `BETA`, `VAR_95`, `TRACKING_ERROR`, `CORR_PORT_BENCH` and `MAX_DRAWDOWN` (`js/data.js:394-415`,
   all on `pr1y`). One window, one observation count, one declaration.
2. `WINDOW_OBS_COUNT = pr1y.length = 252` is therefore true of the return, not only of the risk
   statistics.
3. The FX identity `FX_ATTRIBUTION_PCT = PERIOD_RETURN − PERIOD_RETURN_LOCAL`
   (`js/data.js:759`) is an identity over a single, shared window.
4. The Proof Packet's `windowStart / windowEnd / windowObservationCount` describe the number
   actually published.

## RULING 1(b) — Corollary, and the operationally load-bearing half: a cumulative-performance chart labelled with a trailing window must **plot N + 1 points**.

> The base point is part of the picture of what happened over the window. A chart that plots only
> the N in-window closes has drawn a line whose left edge is not the point the return is measured
> from, and it is therefore **impossible** for that line's own endpoints to reproduce the window's
> return. Excluding the base from the drawing is what forces the drawing to disagree with the
> number.

This is also the ordinary rendering: a "growth of $10,000 over the trailing year" chart always
begins at the base date, for exactly this reason. Ruling 1(b) is not a compromise to make the
arithmetic work; it is the convention that makes the visual and the number the **same object**.

## RULING 1(c) — The window **label** does not change.

> With the base point plotted, the chart's leftmost x value becomes 2025-09-16. The declared
> window remains **252 observations, 2025-09-17 → 2026-09-03**. The leftmost point is the
> **anchor** from which those 252 returns are measured; it is not a 253rd observation.

Stated because the obvious next error is to "fix" the label to 2025-09-16 to match the new axis,
which would put the chart back into contradiction with `js/data.js:387-389`, `:1179` and `:2607`
— the same defect, mirrored.

**RECOMMENDATION (not binding, `designer`'s to replace).** Distinguish the anchor visually so a
reader does not mistake it for an observation: render the segment from the anchor to `d₁` in a
lighter weight, or mark the anchor with a small tick labelled *"base"*, or annotate the axis
`base 2025-09-16 · 252 observations 2025-09-17 → 2026-09-03`. Any treatment satisfying 1(c)
is acceptable; I am not deciding which.

## RULING 1(d) — Scope: this applies to **cumulative wealth-index** series only.

> The anchor requirement applies to a series from which a *return* is derived by taking a ratio of
> two levels — `portfolioIndex`, `benchmarkIndex`. It does **not** apply to **state series** whose
> first plotted point is itself an observation and implies no base: `getDrawdownSeries`
> (`js/data.js:2539-2543`) and `getRollingVolatilitySeries` (`js/data.js:2544-2548`). Drawdown
> and rolling volatility are levels read directly off the axis, not ratios between endpoints;
> prepending an anchor to them would be wrong.

**Consequence the designer must be told about, since it will look like a bug:** after this change
the cumulative chart's x-domain will start one trading day earlier than the drawdown and
rolling-volatility charts' for the same selector setting. That asymmetry is **correct and
required** — it reflects a real difference in what those series are. The *declared* window on all
three must remain identical (252 observations, 2025-09-17 → 2026-09-03).

---

# Part 4 — RULING 2: where the convention lives, and the exact implementation change

## 4.1 The P1 analysis

`CLAUDE.md` P1: *the deterministic engine owns financial facts; presentation explains them.*

`js/charts.js:476` computing `a[last]/a[0] − 1` is **not** the violation. It is the only thing a
chart *can* do with an array of levels, and it is correct given a correctly-based array. The
violation is at `js/data.js:2537`: **the accessor decides where the base is by choosing where to
slice, and it chooses wrongly, and the chart has no way to know.** The presentation layer is
currently choosing the financial convention by inheriting an under-specified array.

The repair must therefore move the convention *into* the data layer and leave the chart's formula
untouched. That is both the correct P1 placement and — not coincidentally — the only placement
under which the regression contract of §7 can be written non-tautologically (§7.3).

## RULING 2 — `getPortfolioSeries` must emit the **base-anchored** array. `js/charts.js` must not change its return formula.

> **BINDING:**
>
> **(i)** Introduce a single named function that owns the convention, replacing the inline
> `i1y - 1 >= 0 ? i1y - 1 : 0` clamp at `js/data.js:391-393` and the bare `sliceRange` at
> `js/data.js:2536`. It must return **both** the base index **and** the declared window metadata,
> so the convention exists in exactly one place and is forced to state which rule it applied:
>
> ```
> periodWindow(range) -> {
>   range,                      // "1M" | "3M" | "6M" | "1Y" | "ALL"
>   firstReturnIndex,           // i   — index of d₁, the first in-window return
>   baseIndex,                  // i-1 for i>0; 0 for ALL (see RULING 3)
>   baseDate,                   // DATES[baseIndex]
>   windowStart,                // DATES[firstReturnIndex]
>   windowEnd,                  // DATES[last]
>   observationCount,           // number of RETURN observations = last - firstReturnIndex + 1
>   baseRule                    // "PRIOR_CLOSE" | "FIRST_AVAILABLE_CLOSE"  ← must be explicit
> }
> ```
>
> **(ii)** `getPortfolioSeries` returns the arrays sliced from `baseIndex`, plus the window
> metadata:
>
> ```
> getPortfolioSeries({range}) -> {
>   dates:      DATES.slice(w.baseIndex),
>   portfolio:  portfolioIndex.slice(w.baseIndex),
>   benchmark:  benchmarkIndex.slice(w.baseIndex),
>   window:     w                                  // ← new, required
> }
> ```
> Arrays gain exactly one leading element for 1M/3M/6M/1Y and are unchanged for ALL.
>
> **(iii)** `PERIOD_RETURN`, `PERIOD_RETURN_LOCAL` and `BENCHMARK_PERIOD_RETURN`
> (`js/data.js:391-393`) read `periodWindow("1Y").baseIndex`. **Their published values do not
> change** — 1Y's base index is 251 before and after. This is a refactor of where the convention
> is written down, not a change to any engine fact.
>
> **(iv)** `js/charts.js` **must not** be given a new return formula. Lines `:476`, `:496-497` and
> `:549-550` stay exactly as they are. They become correct because their input became correct.
>
> **(v)** `WINDOW_START_DATE`, `WINDOW_END_DATE`, `WINDOW_OBS_COUNT` (`js/data.js:387-389`) are
> re-derived from `periodWindow("1Y")` rather than computed separately. Their values do not
> change. This removes the second, parallel definition of the same window.

**What changes on screen:** the chart's leftmost point and first x-tick move back one trading day
(2025-09-17 → 2025-09-16); the portfolio end label moves +5.2 % → +3.9 %; the benchmark end label
−3.7 % → −5.1 %; the callout +8.9 % → +9.0 %; every hover readout shifts by its series' own
offset. **No engine metric changes value.** `returnAnalogyQuick` (`js/data.js:1123-1138`) is
already driven by `PERIOD_RETURN` and already selects the `< 5` bucket correctly; after this
change the chart stops contradicting it.

**What does not change:** `js/charts.js:467-473`'s design constraint is upheld verbatim. The
callout stays period-relative, stays computed from *the exact arrays this call already received*,
and continues to say *"This period"* rather than impersonating the fixed-1Y
`metric.benchmarkRelative`. The selector keeps working because `periodWindow` answers for all five
ranges. **I have verified that the selector survives:** post-fix, chart and engine returns are
**bit-identical doubles** for 1M, 3M, 6M, 1Y and ALL (§6.2).

---

# Part 5 — RULING 3: the `ALL` boundary, and the clamp that hides it

## 5.1 The finding

At `range = "ALL"`, `sliceRange` returns 0, so `i − 1` is −1 and the clamp
`i1y - 1 >= 0 ? i1y - 1 : 0` silently substitutes index 0. That is **a different convention** from
the one it applies at every other range, applied without saying so — precisely what §34/P12
forbid. Two consequences:

- Both the engine and the chart drop `r[0]` — the return dated 2024-09-30, **−0.6012 %**, worth
  **0.6554 pp** on the ALL figure (+9.0144 % as computed vs. +8.3590 % over all 504 returns from
  the notional 100 origin that `cumulativeIndex`'s `.slice(1)` at `js/data.js:353-358` discards).
- ALL is the one range where chart and engine currently **agree** — for the wrong reason. Both are
  wrong in the same way, so a reconciliation check run only at ALL would pass. Coincidental
  agreement is not reconciliation.

## RULING 3 — `ALL` is defined as: base = the first available close; window = every return strictly after it. The rule must be **declared**, not clamped.

> **`baseRule = "FIRST_AVAILABLE_CLOSE"`.** For `ALL`: `baseIndex = 0`, `firstReturnIndex = 1`,
> `baseDate = 2024-09-30`, `windowStart = 2024-10-01`, `windowEnd = 2026-09-03`,
> `observationCount = 503`.
>
> This is the only convention available when no prior close exists. **The published ALL value does
> not change** (+9.0144 %); what changes is that the convention stops being implicit and the
> observation count stops being unstated.
>
> **ALL is the one range where the base point *is* the first plotted point.** That is correct and
> is not an exception to RULING 1(b): the base is genuinely inside the plotted range there,
> because there is nowhere earlier to stand.

## RULING 3(a) — A synthetic origin date is forbidden.

> `cumulativeIndex` (`js/data.js:353-358`) sets a notional level of 100 and discards it with
> `.slice(1)`. That 100 sits at "the day before `DATES[0]`" — a date with no market session behind
> it. **Do not fabricate a calendar entry for it**, and do not report ALL as a 504-observation
> return. Under §34 a date in a return window asserts a session that produced a close; inventing
> one to make an array length come out round is a fixture lie, and it would additionally publish a
> return whose first observation has no observable base.

---

# Part 6 — RULING 4: reconciliation tolerance

## 6.1 Why the tolerance may not be a display tolerance

Both formatters (`js/charts.js:89-93` and `APP_fmtPct`) render `(v*100).toFixed(1)`. It is
tempting to declare two figures reconciled when they render the same string — i.e. |Δ| ≲ 0.05 pp.
**That is wrong, and M1 itself is the proof.**

`returnAnalogyQuick` (`js/data.js:1123-1138`) branches at `pct >= 5`. The values **4.999 %** and
**5.001 %** both render `+5.0 %` and differ by 0.002 pp — well inside any display tolerance — yet
select **different semantic buckets** ("flat, close-to-breakeven" vs. "an average year"). A display
tolerance is blind to exactly the failure mode that makes M1 a truth contract rather than a
rounding matter.

## RULING 4 — Two quantities that must be identical by construction reconcile at numerical identity, not at display precision.

> **(i) `τ = 1e-9`, absolute, on a decimal return.** Under RULING 2 the chart and the engine
> perform the *same division on the same two doubles*, so exact equality holds; τ = 1e-9 is
> margin, not slack. I have confirmed bit-identity for all five ranges (§6.2).
>
> **(ii) The tolerance may never be widened to accommodate an observed disagreement.** If a
> reconciliation check fails, the finding is the disagreement, not the tolerance. A tolerance
> calibrated from observed error is not a control; it is a record of the defect.
>
> **(iii) Display rounding is applied *after* reconciliation, identically on both sides.** Because
> `pctText(v, 1)` and `APP_fmtPct(v)` are character-for-character the same function, the rendered
> **strings** must also be equal, and §7's RC-2 tests string equality — a strictly stronger check
> than numeric equality, and one that additionally catches a side that rounds a pre-rounded input.
>
> **(iv) Where two figures are legitimately produced by *different* routes** (not the case here,
> but it will be), the reconciliation tolerance must be **derived from and stated with** the
> method that makes them differ. It is a declared part of the method under §34, not a constant
> chosen to make a test pass.

## 6.2 Post-fix reconciliation, verified

`chart_after = portfolioIndex.slice(baseIndex)` → `last/first − 1`, versus the engine's period
return:

| range | chart after fix | engine | identical? |
|---|---|---|---|
| 1M | −0.015065990426738063 | −0.015065990426738063 | **True** |
| 3M | +0.0046021655693595509 | +0.0046021655693595509 | **True** |
| 6M | −0.088475301649573179 | −0.088475301649573179 | **True** |
| 1Y | +0.038880644395016706 | +0.038880644395016706 | **True** |
| ALL | +0.090144300841179303 | +0.090144300841179303 | **True** |

Relative callout at 1Y after the fix: `0.089949352677533012`; engine
`metric.benchmarkRelative`: `0.089949352677533012` — **identical**.

---

# Part 7 — RULING 5: the regression contract

## 7.1 Why 33/33 stayed green

`js/selfcheck.js` reads only `window.APP.data` and never the DOM (its sole `document` reference is
`document.readyState` at `:1454`, for boot timing). Every one of its assertions compares an engine
fact to another engine fact, or to a hand-authored string *inside `data.js`*. M1 lives in the gap
between `APP.data` and the pixels: **no rendered quantity was ever an input to any control.** The
suite could not have caught this, and its greenness was never evidence about it.

## RULING 5(a) — the invariant

> **RC — Rendered-Fact Reconciliation.**
>
> No rendered financial quantity may be produced by arithmetic that the deterministic engine does
> not also perform, on the same inputs, over the same window.
>
> Wherever a rendering unit displays a quantity whose label asserts the **same metric over the
> same window** as a published engine fact, there must exist an automated assertion that:
>
> - **(a)** obtains the rendered quantity **by reading it back from the rendered output** — never
>   by re-executing the renderer's own formula;
> - **(b)** obtains the engine fact from its **published accessor**, independently;
> - **(c)** **fails** unless the two are equal within the metric's declared reconciliation
>   tolerance (RULING 4);
> - **(d)** is demonstrated to fail under a mutation of the base index, the window bound, or the
>   compounding convention on **either** side (RULING 6).
>
> **An assertion that reads only the engine's own inputs is not an instance of RC.** Clause (a) is
> what distinguishes a control from a restatement.

## RULING 5(b) — RC-1, data layer. BINDING.

Add to `ASSERTIONS` (`js/selfcheck.js:206`). Needs no DOM; runs at page load with `run()`.

```
id: "periodWindow.seriesReconcilesWithEngine"
```

For **each** `range ∈ {1M, 3M, 6M, 1Y, ALL}`, let `s = data.getPortfolioSeries({range})`:

| # | Assertion | Rationale |
|---|---|---|
| RC-1.1 | `\|s.portfolio[last]/s.portfolio[0] − 1 − enginePeriodReturn(range)\| ≤ 1e-9` | the M1 arithmetic itself |
| RC-1.2 | same for `s.benchmark` | the 1.43 pp leg nobody measured |
| RC-1.3 | at `1Y`: `\|(portfolio ret − benchmark ret) − getMetric("metric.benchmarkRelative").value\| ≤ 1e-9` | the −0.14 pp leg |
| RC-1.4 | `s.dates.length === s.portfolio.length === s.benchmark.length` | anchor added to all three or none |
| RC-1.5 | `s.window.baseDate === s.dates[0]` **and** `s.window.windowStart === s.dates[1]` for `baseRule="PRIOR_CLOSE"`; `=== s.dates[0]` for `"FIRST_AVAILABLE_CLOSE"` | forces the rule to be declared and true |
| RC-1.6 | `s.window.observationCount === s.dates.length − 1` | *N levels ⇒ N−1 returns* — §2.1 made mechanical |
| RC-1.7 | at `1Y`: `s.window.observationCount === _internal.windowObservationCount` (252), `s.window.windowStart === _internal.windowStart`, `s.window.windowEnd === _internal.windowEnd` | binds the chart's array to the **Proof Packet** window (`js/data.js:2607`) |

RC-1.7 is the one that catches M1 *from the other direction*: the Proof Packet says 252
observations over 2025-09-17→2026-09-03, so the array handed to the chart must contain exactly
**253** points whose 2nd through 253rd dates are those.

Every required input already exists: `getPortfolioSeries`, `getMetric`, and `_internal.DATES /
portfolioReturns / benchmarkReturns / windowStart / windowEnd / windowObservationCount`
(`js/data.js:2603-2607`). `enginePeriodReturn(range)` must be published for all five ranges —
today only 1Y exists, which is why 6M's 1.12 pp error is invisible (§1.6).

## RULING 5(c) — RC-2, render layer. BINDING in form.

```
id: "chart.renderedReturnReconcilesWithEngine"
```

1. Build `s = data.getPortfolioSeries({range: "1Y"})`.
2. Call `APP.charts.lineCompare({dates: s.dates, series: {portfolio: s.portfolio, benchmark: s.benchmark}})`
   into a **detached** node. This is viable: `measureTextWidth` (`js/charts.js:207-219`) falls back
   to `estimateTextWidthHeuristic` when no measure node is available, and text content is set
   regardless of measurement.
3. Read back `textContent` of `.chart-end-label-portfolio`, `.chart-end-label-benchmark`,
   `.chart-relative-callout`.
4. Extract the percentage substring from each.
5. Assert **character equality** with the engine side formatted by the same convention:
   `pctText(getMetric("metric.return.1y").value, 1)`,
   `pctText(engineBenchmarkPeriodReturn, 1)`,
   `pctText(getMetric("metric.benchmarkRelative").value, 1)`.

String equality, not numeric — RULING 4(iii). This is the tier that closes the `APP.data`-only gap
named in §7.1, and it is the only tier that satisfies RC clause (a).

## 7.3 Why RC-1 works only under RULING 2's placement

Under RULING 2 the accessor emits the base-anchored array, so RC-1.1 compares the engine's fact
against **the array the chart actually consumes**. Had the repair instead been "change the formula
inside `charts.js`", RC-1 would be inspecting an array that no longer determines the rendered
number, and would be blind again — passing while the chart printed something else. **The
convention's placement and the checkability of the control are the same decision.** This is an
independent argument for RULING 2 and against alternative R3 (§8).

---

# Part 8 — RULING 6: falsification / mutation cases

`js/selfcheck.js`'s `selfTest()` (`:1391-1428`) already enforces the right acceptance bar:
*confirm the assertion passes; inject its own named defect; confirm it now fails; restore in a
`finally`.* An assertion with no `injectDefect` is auto-failed with *"NO NEGATIVE TEST DEFINED."*
The mutations below are `injectDefect` implementations meeting that bar. This file's own revision-2
history — a control that passed while its exact defect was reintroduced, because two fields were
concatenated and only one was mutated — is why M6.3 and M6.5 below are mandatory rather than
thorough.

## RULING 6 — the following mutations are required, and each must be demonstrated to flip its assertion pass → fail.

| id | Mutation | Target | Must fail because |
|---|---|---|---|
| **M6.1** | **The M1 defect itself.** Patch `getPortfolioSeries` to drop the leading element of `dates`, `portfolio`, `benchmark` — i.e. restore `js/data.js:2537`'s pre-fix `.slice(i)`. | RC-1.1, RC-1.2, RC-1.3, RC-1.6, RC-1.7 | reproduces M1 exactly. RC-1.1 detail must read **+5.1812 % vs +3.8881 %** at 1Y — the harness's own reproduced numbers. |
| **M6.2** | **The convention, not the array.** Patch `periodWindow(range).baseIndex` to return `firstReturnIndex` instead of `firstReturnIndex − 1`. | RC-1.1, RC-1.5, RC-1.6 | catches the defect at its source; proves the check tests the *rule*, not one array's length. |
| **M6.3** | **Non-vacuity, portfolio leg.** Patch only the **portfolio** series' base (leave benchmark correct). | RC-1.1 alone | RC-1.1 must fail while RC-1.2 still passes. Guards against a combined check passing on the untouched leg — the revision-2 failure shape. |
| **M6.4** | **Non-vacuity, benchmark leg.** Mirror of M6.3, benchmark only. | RC-1.2 alone | as above, mirrored. Note it must **also** trip RC-1.3, since a one-sided base shift moves the relative figure. |
| **M6.5** | **Readback is real.** Wrap `APP.charts.lineCompare` so that after the SVG is built, `.chart-end-label-portfolio`'s `textContent` is rewritten to a value **0.5 pp** off, leaving arrays and every engine fact untouched. | **RC-2 only** | RC-1 must still pass and RC-2 must fail. This is the proof that RC-2 reads the **DOM** and not the array — the single most important negative test here, because a "render check" that quietly recomputes `a[last]/a[0]−1` is testing its own formula and is worthless. |
| **M6.6** | **Declaration drift.** Patch `s.window.observationCount` to `s.dates.length` (i.e. N instead of N−1), changing no number. | RC-1.6, RC-1.7 | proves the window *declaration* is under control independently of the value, which is what PD-0014 claim traceability actually protects. |
| **M6.7** | **`ALL` is not exempt.** Patch `baseRule` for ALL to `"PRIOR_CLOSE"` while leaving `baseIndex = 0`. | RC-1.5 | ALL currently reconciles by coincidence (§5.1); this proves the check distinguishes *declared* from *accidental* agreement. |

## RULING 6(a) — a tolerance-calibration guard

> **M6.3's disagreement at 3M is only −0.0349 pp.** Any reconciliation tolerance looser than
> ~0.03 pp would let the M1 defect pass at 3M while failing at 1Y — a partially-blind control that
> would be recorded as "detects its defect." At `τ = 1e-9` (RULING 4) this cannot occur, and
> **M6.1 must therefore be demonstrated to fail at every one of 1M, 3M, 6M and 1Y**, not merely at
> 1Y. If any range passes under M6.1, the tolerance is wrong — not the range.

## RULING 6(b) — restoration

> Every mutation restores in a `finally`, per `selfTest`'s existing contract (`:1420-1424`). M6.5
> patches a **function on `APP.charts`**, not a claim object; its restore must reinstate the
> original function reference, and the assertion must be written so that a failure to restore is
> itself detectable by the *next* run rather than silently persisting.

---

# Part 9 — Hand-derived fixtures

Derived by arithmetic on numbers I chose. No implementation was run to produce any expected value;
each is checkable with a calculator.

## F-A — the base convention, on a 4-point series

**Input.** Level series `L = [100, 110, 99, 108.9]` on trading days `D0, D1, D2, D3`.
**As-of:** `D3`. **Selector:** a window of **2 return observations** (so `firstReturnIndex = 2`).

**Derivation.**

- Window returns: `r[2] = 99/110 − 1 = −0.10`; `r[3] = 108.9/99 − 1 = +0.10`.
- Base is `L[1] = 110` (the close **before** `D2`).
- **Canonical (RULING 1):** `R = 108.9 / 110 − 1 = −0.01` = **−1.00 %**.
  Cross-check by compounding: `(1 − 0.10)(1 + 0.10) − 1 = 0.99 − 1 = −0.01` ✓
- **Chart's current convention:** `R = 108.9 / 99 − 1 = +0.10` = **+10.00 %**.
- **Error:** 11.00 pp — from a single seam day. Predicted by §1.3's identity:
  `(1 + R_chart)·r[i] = 1.10 × (−0.10) = −0.11` and `R_engine − R_chart = −0.01 − 0.10 = −0.11` ✓

**Expected outputs.**

| Field | Expected |
|---|---|
| `baseIndex` | 1 |
| `baseDate` | `D1` |
| `windowStart` / `windowEnd` | `D2` / `D3` |
| `observationCount` | **2** |
| `baseRule` | `PRIOR_CLOSE` |
| series length returned | **3** (`L[1..3]`) |
| period return | **−0.01** exactly |
| chart end label under RULING 2 | `−1.0%` |

**Why this fixture.** It **flips the sign** of the answer, not merely its magnitude — a stronger
demonstration than M1's bucket flip, and it shows the error is unbounded in the seam day's return
rather than "about a day's worth."

## F-B — the `ALL` boundary

**Input.** Same `L = [100, 110, 99, 108.9]`, `range = ALL`, `firstReturnIndex = 0`.

**Derivation.** No close exists before `D0`. Under RULING 3, base = `L[0] = 100`, window = returns
dated `D1, D2, D3`. `R = 108.9/100 − 1 = +0.089` = **+8.90 %**.
Cross-check: `(1.10)(0.90)(1.10) − 1 = 1.089 − 1 = 0.089` ✓

**Expected outputs.**

| Field | Expected |
|---|---|
| `baseIndex` | 0 |
| `baseDate` | `D0` |
| `windowStart` / `windowEnd` | `D1` / `D3` |
| `observationCount` | **3** — *not* 4 |
| `baseRule` | `FIRST_AVAILABLE_CLOSE` |
| series length returned | **4** (unchanged) |
| period return | **+0.089** exactly |

The value is what the current clamp already produces. **The defect being repaired here is the
undeclared convention, not the number** — which is why M6.7 tests the declaration and not the
value.

## F-C — the tolerance boundary (justifies RULING 4)

**Input.** Engine value `0.04999`; rendered value `0.05001`. Δ = 0.002 pp.

**Derivation.** `(0.04999 × 100).toFixed(1) = "5.0"`; `(0.05001 × 100).toFixed(1) = "5.0"`.
Identical strings. But `returnAnalogyQuick` (`js/data.js:1123-1138`) branches at `pct >= 5`:
`4.999 < 5` → *"roughly the size of a flat, close-to-breakeven year"*; `5.001 >= 5` → *"roughly
the size of an average year for a globally diversified stock portfolio."*

**Expected outcome.** A display-precision reconciliation tolerance **passes** this pair. `τ = 1e-9`
**fails** it. The pair is therefore a discriminating test of the tolerance rule itself, and RULING
4(i) is the only one of the two that survives it.

## F-D — rounding, on the live fixture

| | double | rendered |
|---|---|---|
| engine `PERIOD_RETURN` | `0.038880644395016706` | `+3.9%` |
| chart end label, post-fix | `0.038880644395016706` | `+3.9%` |
| chart end label, **pre-fix** | `0.051812…` | `+5.2%` |

Post-fix the two are the same double, so RC-2's character-equality assertion is satisfiable
exactly, not approximately.

---

# Part 10 — Alternatives considered and rejected

### R1 — Move the **engine** to the chart's base (`i` instead of `i − 1`). **Rejected.**

It would publish a **251-observation return under a 252-observation declaration**
(`WINDOW_OBS_COUNT = pr1y.length = 252`, `js/data.js:389`), inverting the defect rather than fixing
it. Worse, it desynchronizes the return from every other 1Y statistic: `ANNUAL_VOL`, `BETA`,
`VAR_95`, `TRACKING_ERROR`, `CORR_PORT_BENCH`, `MAX_DRAWDOWN` all consume `pr1y` — 252 returns
(`js/data.js:394-415`). The metric strip would show a return over 251 days beside a volatility over
252, under one window label. It also breaks the window shared by the FX identity at
`js/data.js:759`. **And it is simply the wrong convention** (RULING 1(a)): it is not a choice
between two defensible methods.

### R2 — Have `charts.js` read `metric.return.1y`. **Rejected**, on three independent grounds.

1. **It breaks the selector.** No engine fact exists for 1M/3M/6M/ALL, so four of five periods
   would fall back to the chart's own arithmetic — two conventions in one control, which is the
   defect again.
2. **It decouples the number from the line drawn.** A future slicing change would move the line
   without moving the number, and nothing would notice. The current failure at least *manifests*.
3. **It contradicts a decision that is correct.** `js/charts.js:467-473` records that the callout
   is deliberately period-relative and deliberately labelled *"This period"* so it never
   impersonates the fixed-1Y `metric.benchmarkRelative`; `CONTRACT.md`'s chart API states
   `charts.js` never calls back into `APP`. **I am upholding that decision, not overriding it.**

### R3 — Pass `opts.baseValue` into `charts.js`. **Rejected as the primary fix.**

Not wrong arithmetically, and it does keep the convention in the data layer. But it leaves the
drawn line **starting somewhere other than its own base**, so the visual distance from left edge to
right edge is still not the reported return — the picture and the number remain different objects,
and RULING 1(b) is unmet. It also weakens the regression contract: RC-1 would have to reconcile
against a scalar option rather than against the array the chart consumes (§7.3).

> **Conditional permission.** If a hard rendering constraint I have not foreseen makes the leading
> point undrawable, R3 is acceptable **only** with all of: (i) the base value comes from
> `periodWindow(range)`, never computed in presentation code; (ii) RC-1 and RC-2 are implemented
> against the `baseValue` path with equal rigour; (iii) the chart annotates its base date
> explicitly, since it is then off-canvas. Escalate to this role before taking it; do not adopt it
> silently.

### R4 — Widen the reconciliation tolerance and record M1 as accepted rounding. **Rejected.**

1.29 pp is not rounding, the −0.14 pp is a near-cancellation of two ~1.3 pp errors (§1.4), and F-C
shows that even 0.002 pp can flip a semantic bucket. This is the option RULING 4(ii) exists to
forbid.

---

# Part 11 — What I did not establish, named rather than guessed

- **I did not execute the prototype.** No browser, no network. Every figure is from my independent
  port (`methodology/hg1_m1_repro/reproduce_m1.py`), corroborated against the PM's four live
  measurements. Anything depending on actual DOM rendering — that RC-2's detached `lineCompare`
  call really produces the expected `textContent`, that `measureTextWidth`'s fallback path behaves
  as I read it to — is **inferred from source and must be confirmed by whoever implements it.**
  If step 2 of RULING 5(c) proves infeasible in a detached node, that is a finding to bring back
  to me, not a licence to weaken RC-2 to a data-layer check.
- **Whether other surfaces render returns not covered here.** I traced `getPortfolioSeries`'s two
  callers (`overview.js:272`, `analytics.js:281`) and the three DOM-writing sites inside
  `lineCompare`. I did **not** exhaustively audit `shell.js` (250 KB) or the other surface files
  for further rendered quantities that assert an engine window. **RC (RULING 5(a)) is stated as a
  general invariant precisely because I cannot certify that inventory.** Someone should run it.
- **The 1.29 pp is exact for *this fixture*.** The convention ruling is fixture-independent; the
  magnitudes are not. With real, non-synchronous multi-market closes, the seam day is where the
  three calendars disagree most, so the error would if anything be larger and less predictable.
- **Whether `enginePeriodReturn` should be published for 1M/3M/6M/ALL.** RC-1 needs it (§7.2), and
  §1.6 shows 6M is currently wrong by 1.12 pp with nothing to catch it. But publishing four new
  period returns is a **product scope decision** — each would need its own sufficiency state,
  reference point (P4) and Proof Packet. I flag the need; I do not decide the scope. If they are
  not published, RC-1 must still be implemented against an **internal** per-range period return
  exposed on `_internal`, so the control exists even where the metric does not.

---

# Part 12 — Findings raised by this work, for the parent to route

| id | Finding | Class |
|---|---|---|
| **M1-F1** | The brief's premise is wrong: the one-trading-day base offset accounts for **both** gaps in full (residual 0 to 17 s.f.). The FX-inclusive-base hypothesis is disconfirmed — the same offset appears in the FX-free local series. | methodology, corrects the brief |
| **M1-F2** | M1 is **not** 1Y-only. 6M is wrong by **+1.12 pp**, 1M by −0.37 pp, 3M by −0.03 pp. Unreported because no engine fact exists at those ranges to contradict them. | defect, wider than filed |
| **M1-F3** | The −0.14 pp relative gap is a **near-cancellation of two ~1.3 pp errors**, not a small defect. Must not be triaged by observed magnitude. | methodology |
| **M1-F4** | `i1y - 1 >= 0 ? i1y - 1 : 0` (`js/data.js:391-393`) is an **undeclared convention switch** at the ALL boundary (§34/P12). ALL silently drops `r[0]` = −0.60 %, worth 0.66 pp, under both conventions — so ALL agrees **by coincidence**, and a reconciliation check run only at ALL would pass. | methodology, latent |
| **M1-F5** | `js/selfcheck.js` cannot, by construction, catch any rendering defect: it reads only `window.APP.data` (sole `document` use is `readyState` at `:1454`). **33/33 green was never evidence about M1.** RC-2 (RULING 5(c)) is the structural repair. | control gap |
| **M1-F6** | **Raised, not ruled — adjacent, do not fold into M1.** `MAX_DRAWDOWN` (`js/data.js:408`) slices a drawdown series whose running max spans **all** history, so the 1Y figure is *drawdown-from-all-time-high restricted to the window*, not *peak-to-trough within the window*. Two different conventions, neither declared. On this fixture they **coincide at −15.1994 %** — the running max at window start was attained 2025-09-16, outside the window, and a later in-window peak dominates the trough. So the defect is **latent, not live**: same shape as M1-F4, agreement by accident. Needs its own ruling. | methodology, latent |
| **M1-F7** | After RULING 1(b) the cumulative chart's x-domain starts one trading day earlier than the drawdown and rolling-volatility charts' for the same selector. This is **correct** (RULING 1(d)) and will look like a bug. Route to `designer` with RULING 1(c) so the label is not "corrected" into a fresh contradiction. | design, expected consequence |
| **M1-F8** | RC-1 requires a per-range engine period return. Publishing four new metrics is product scope, not quant scope — see Part 11. Interim: expose them on `_internal` so the control can exist without a new claim. | product / engineering |
| **M1-F9** | The 351-calendar-day "trailing 1Y" fixture defect (already open as F2 in `methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md` Part D) is **out of bounds for this ruling and is not touched by it**. Recorded only so the next reader does not think it was folded in. This ruling is correct under either calendar: it concerns where the base sits relative to the window, not how long the window is. | fixture, explicitly deferred |

---

**Restated, because it is the thing most easily lost in a long document:** none of the above is an
approval. HG1 is `REVISION_REQUIRED` and `awaiting_human`, and only the designated human product
owner can change that. M2 and M3 remain frozen; this ruling settles the truth convention they were
waiting on and nothing more.

**Artefacts written by this ruling** (the whole of my write authority — `methodology/`):

- `methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md` — this document.
- `methodology/hg1_m1_repro/reproduce_m1.py` — the independent reproduction harness. Read-only;
  run with `python3 methodology/hg1_m1_repro/reproduce_m1.py`.
