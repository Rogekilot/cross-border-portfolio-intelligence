# HG1 Round 5 — two methodology rulings: the beta caveat split (P3) and the SML x-domain

**Author:** `quant_analyst`, delegated subagent, 2026-09-07.
**Requested by:** the parent orchestrator, on behalf of a blocked UX round.
**Authority:** PD-0014 §3 — `product_manager` and `designer` may not invent resolutions for
statistical sufficiency or CAPM/SML methodology. These two questions were routed here by
`reviews/gates/HG1_ROUND5_UX_AUDIT.md` (S4's flagged constraint; §5's last bullet), which
explicitly declined to rule on either.

> **This document contains no approval of anything.** HG1 remains **`REVISION_REQUIRED`** and
> `awaiting_human`. `quant_analyst` cannot approve a human gate and does not do so here. Nothing
> below may be read as clearing Priorities A–E, the prototype, or the gate.

**Method, stated so it can be discounted appropriately.** I did **not** execute the prototype.
There is no browser in this role and no network egress. Every figure quoted is either (a) read
directly from the source under review, (b) arithmetic I performed on the fixture's own declared
calendar and window, shown below so a reviewer can check it rather than trust it, or (c) taken
from `methodology/HG1_ROUND4_VERIFICATION.md`, which records values my predecessor obtained from
a live run. Where a quantity is (c) I say so. I did **not** recompute the three sleeve betas;
Ruling 2 does not depend on them.

**Ruling vs. recommendation.** Every numbered **RULING** is binding within my authority
(`roles/quant_analyst.json` → `may_decide`: methods, conventions, data-sufficiency thresholds).
Every **RECOMMENDATION** is not; it is UI or engineering judgment offered so the ruling is
actionable, and `designer` may replace it with anything that satisfies the ruling. Exact strings
are supplied because `js/shell.js`'s own `appendCaveatSlot` comment routes caveat *compression*
to this role — but the binding part is the **semantic content**, not the literal wording.

---

# Part A — Ruling 1: the beta caveat under P3

## A.0 The test I am applying, stated before I apply it

P3: *"Simplification must preserve uncertainty. Plainer wording may drop precision; it may not
drop a caveat that changes the conclusion."*

P3 therefore requires a partition of a caveat's propositions into **conclusion-changing** and
**precision**. I define the partition test as follows, and I apply it uniformly to every claim in
§A.4.

> **Conclusion-changing test.** A proposition is conclusion-changing if a reader who does not see
> it would, **from what remains visible at the same rendering unit**, form a belief about the
> metric that the full disclosure contradicts. Two sub-tests:
>
> - **(T1) Sufficiency test (P5).** Would the reader believe the figure is fully supported when
>   it is not? Any proposition that is the sole carrier of a non-`AVAILABLE` state fails T1 and is
>   conclusion-changing.
> - **(T2) Magnitude/direction test.** Would the reader take a directional or magnitude
>   conclusion from the figure that the omitted proposition forbids or reverses?
>
> Everything else is **precision**: it refines *how* the reader understands the state was reached,
> without changing *what* they conclude. P3 expressly permits dropping precision.

Two clauses of "at the same rendering unit" matter and are easy to miss:

1. `renderMetricValue` is called from **two structurally different contexts** — inside
   `renderClaim`'s ladder (where `conclusionQuick` is beside it) and inside
   `analytics.js`'s `focusableMetricCell` and table cells (where it may be nearly alone).
   The qualifier must be self-sufficient in the **weaker** context. I apply the test against the
   compact context.
2. `conclusionQuick` for beta already carries the observation count, the standard error, the 95%
   CI and the indistinguishability hedge, and `renderClaim` renders `conclusionQuick` at all three
   depths. Where a proposition is already carried there, the qualifier is not its sole carrier and
   T1/T2 are assessed accordingly.

## A.1 The caveat decomposed

`js/data.js:1260–1264`, English. Five propositions, labelled for reference:

| # | Clause (exact) | Verdict |
|---|---|---|
| **P-a** | `"252 daily observations"` | **Conclusion-changing (T1).** |
| **P-b** | `"(2025-09-17 to 2026-09-03)"` | **Precision.** |
| **P-c** | `"Cross-market default per PRD §14 is weekly (≥156 weekly [3Y] for AVAILABLE, 52–155 for LIMITED)"` | **Precision** (implementation disclosure) — **subject to §A.3's guard.** |
| **P-d** | `"this implementation uses daily instead and records that deviation here rather than silently"` | **Split.** The word *daily* is required (§A.3, and independently by PRD §14). The deviation narrative is precision. |
| **P-e** | `"≥750 daily [3Y] for AVAILABLE, 250–749 for LIMITED, <250 for INSUFFICIENT_DATA"` | **Precision.** |
| **P-f** | `"At 252 daily observations this metric is LIMITED"` | **Conclusion-changing (T1). This is the load-bearing proposition.** |
| **P-g** | `"under its own, meetable, daily threshold"` | **Precision — and specifically, reviewer-facing repair evidence, not reader-facing meaning.** |

### RULING 1(a) — which propositions are conclusion-changing

**Conclusion-changing, and therefore required in the always-visible unit at every depth
including Quick:**

1. **`"this metric is LIMITED"`** (P-f). Sole carrier of the sufficiency state at the compact
   rendering unit. Fails T1 outright. Independently mandatory under `designs/FEATURE_DESIGN.md`
   §D3.2's `LIMITED` row ("mandatory, non-dismissible qualifier in the same visual unit as the
   value… must never be visually indistinguishable from an `AVAILABLE` one at any depth level,
   including Quick").
2. **`"252 daily observations"`** (P-a), as the **category and reference of the limitation**.
   §D3.2 requires the qualifier to name *"the specific limitation (short window, thin sample,
   degraded data quality)"* — a bare `LIMITED` does not satisfy that. Additionally: `LIMITED` is
   itself a **judgment**, and P4 requires every judgment to carry a reference point. The reference
   point for this judgment is the sufficiency threshold, i.e. the 3-year standard. Therefore the
   qualifier must name **both** the sample the judgment was made on **and** the standard it was
   judged against. *(This requirement was not identified by the UX auditor and I am adding it.)*
3. **The actual frequency, `"daily"`** (the first half of P-d). This is required **not by P3** —
   see §A.3 — but unconditionally by PRD §14: *"Every metric must state the actual window/frequency
   used."* It costs one word and I will not trade it.

**Not conclusion-changing (precision; may move to `caveatFull`):** P-b, P-c, P-e, P-g, and the
"records that deviation rather than silently" half of P-d.

### RULING 1(a-ii) — on the UX auditor's provisional reading: **confirmed in direction, corrected in extent**

The auditor read the load-bearing clause as *"At 252 daily observations this metric is LIMITED
under its own, meetable, daily threshold,"* with the PRD §14 threshold table being implementation
disclosure.

- **Confirmed:** the threshold tables (P-c, P-e) are implementation disclosure and are not
  conclusion-changing — *subject to the guard in §A.3, which is not optional.*
- **Corrected — the auditor's clause is over-broad.** `"under its own, meetable, daily threshold"`
  (P-g) is **not** load-bearing. It is an artefact of the round-4 repair: my predecessor's finding
  D1.4 established that the previous threshold ("36 monthly-equivalent observations" against a 1Y
  daily window) was **unmeetable by construction**, and the word *meetable* is addressed to the
  reviewer who found that, not to the investor. Nobody's conclusion about β = 0.99 turns on whether
  the threshold that classified it is attainable. Spending scarce always-visible budget on it would
  be spending it on the audit trail rather than on the reader.
- **Corrected — the auditor's clause is also under-inclusive in one respect.** It contains no
  reference point for the `LIMITED` judgment. Under P4 the qualifier must name what the sample
  fell short of, not only that it fell short.

### RULING 1(b) — the required content of `qualifierShort`, and proposed exact strings

**BINDING — semantic content.** `qualifierShort` must carry exactly four things, and nothing more:

| Slot | Content | Source of obligation |
|---|---|---|
| 1 | the sufficiency state token | §D3.2 `LIMITED` row; P5 |
| 2 | the observation count | §D3.2 ("specific limitation"); §13.3 |
| 3 | the return frequency actually used | PRD §14, unconditional |
| 4 | the standard the sample fell short of | P4 (a judgment needs a reference point) |

**Two further binding constraints on slot 2:**

- **B1.** The count must be **read from the same evidence object the Proof Packet exposes**
  (`WINDOW_OBS_COUNT` / `pr1y.length`, which is what `EVIDENCE["metric.beta"].observations`
  reads). PD-0014 §2.3 binding example 4, and §2.4 — the Proof Packet must not be able to refute
  the sentence that links to it. A hardcoded literal here re-creates the original 24-vs-252 defect
  in a new field.
- **B2.** `selfcheck.js`'s `binding4.beta.observationCountMatchesEvidence` currently extracts
  `/(\d+)\s*daily/i` from `m.caveat` only. It **must be extended to assert the same equality on
  `qualifierShort`.** A newly-visible string that no assertion guards is precisely the
  parallel-truth failure PD-0014 §2.5 forbids.

**RECOMMENDATION — exact strings satisfying the above.** These may be adopted verbatim; the
binding part is the table above.

```
qualifierShort (en): limited · 252 daily obs · 3Y standard not met
qualifierShort (zh): 有限 · 252个日频观测 · 未达3年标准
```

- English: **45 characters** (≤ 48, three characters of headroom). `·` is U+00B7, one JS char.
  The count is at most three digits inside the `LIMITED` band (250–749), so the length is stable.
- Chinese: **22 characters.**
- **The 48-character cap is a Latin-script proxy for a rendered-width cap, and the two are not
  the same constraint.** At `font-size: 11.5px` a Latin glyph averages ≈ 6.0px — this is
  `charts.js`'s own `labelCharPx` constant — while a CJK glyph is a full em, ≈ 11.5px. 48 Latin
  characters ≈ 288px; 48 CJK characters ≈ 550px, which cannot fit two line-boxes in a 180px track
  in any layout. The Chinese string above is ≈ 184px by that estimate and the English ≈ 264px, so
  both land inside two line-boxes at 180px. **This width arithmetic is a RECOMMENDATION, not a
  ruling** — it is the same script-blind measurement problem the audit raised as S2, and it must
  be confirmed in a browser. If AC-S4.1 is restated as a rendered-width bound rather than a
  character count, that would be the more honest acceptance criterion.
- **Vocabulary.** The app's own state vocabulary is lowercase plain language
  (`"insufficient data"` / `数据不足`, `"not available"` / `不可用`), not uppercase enum tokens;
  `shell.js:911` already falls back to the literal `"limited data"`. The state token in the string
  above follows that register. `"limited data"` (12 chars) instead of `"limited"` pushes the
  English string to 50 and breaches the cap, which is why the shorter token is used.
  **A new i18n key `common.limited` (en `limited`, zh `有限`) must be the single source for it** —
  a second, forked name for a metric state is exactly PD-0014 §2.5's "parallel truths."
  `有限` is the token `js/data.js`'s existing Chinese caveat already uses (`判定为「有限」`);
  do not introduce a second Chinese name for the state.
- **Alternate English wording**, if "not met" reads as reproach: `limited · 252 daily obs · below
  the 3Y standard` — **47 characters measured**, inside the cap but with one character of
  headroom. I prefer the 45-character form for that reason.

### RULING 1(b-ii) — one thing `qualifierShort` must NOT be asked to carry

The **window** (start/end dates, or "trailing 1Y") is not in the four slots. It is P-b and it is
precision. But note the consequence and do not paper over it: in the compact
`focusableMetricCell` context, `referencePoint` ("MSCI ACWI, trailing 1Y daily") does not render
at all, so after the split the window length is stated at that unit only implicitly, via the
count. **This is a pre-existing §13.3/P4 gap, it is not created by the split, and it is not
resolved by it.** Recorded here so it is not later attributed to this ruling. The correct fix is
to render `referencePoint` at the compact cell, not to lengthen the qualifier.

## A.2 What `caveatFull` must retain, and the highest-risk part of this change

### RULING 1(c-i) — do not rename `caveat`; add `qualifierShort` beside it

**BINDING.** The split must be implemented as **an added field**, with `claim.caveat` retaining
the full text unchanged. `caveatFull` is then `caveat` and no consumer needs re-pointing.

The reason is specific and it is the single highest-risk part of this change:
`registerEvidenceFor` (`data.js:1881, 1885`) builds the Proof Packet's
`thresholds_limits_if_used` and `limitations` fields as `c.caveat ? c.caveat : …`. **If `caveat`
is shortened in place, the Proof Packet silently loses the entire threshold disclosure and
`limitations` degrades toward `"None recorded."`** That is a direct P9 breach and it would be
invisible to every check in the current suite — the packet would simply stop refuting anything,
which is not the same as being correct. `selfcheck.js`'s `binding4` would also stop finding a
count to check, because it reads `m.caveat`.

Adding a field rather than renaming one makes both regressions impossible by construction.

## A.3 The PRD §14 deviation disclosure — and a fixture defect that constrains this answer

### The question

May the weekly-vs-daily deviation disclosure move out of the always-visible qualifier into
`caveatFull` and the Proof Packet, given that the implementation records the deviation
*deliberately rather than silently*? Is the recording obligation satisfied by presence in the
Proof Packet?

### RULING 1(c) — yes, the recording obligation is satisfied without an always-visible pill; but the demotion is conditional, and the condition currently fails

**Part 1 — the recording obligation is already discharged three times over, none of them in the
qualifier.**

The obligation is a §33/§34 methodology-registry obligation, not a §D3 rendering obligation. It is
discharged by:

1. `methodology.beta.minimumObservations` — carries **both** threshold tables verbatim;
2. `methodology.beta.knownLimitations` — carries the deviation, its reason (Epps effect,
   non-synchronous closes), the direction of the resulting bias (toward zero), and the open
   product decision;
3. the Proof Packet's `thresholds_limits_if_used` / `limitations` — provided §A.2's ruling holds.

PRD §13.3 uses the word **"expose"** for benchmark-relative disclosure, and the Proof Packet is
the product's exposure mechanism (P9, §21). `designs/FEATURE_DESIGN.md` §D3.3 is more specific
still and settles the depth question directly: *"Quick: label + reason category; Professional:
label + reason code + **minimum-observation requirement from the methodology registry**, per
§33."* **Demoting the threshold tables to Professional is not a concession to layout; it is what
the accepted design contract already specifies.** The current rendering — the whole registry
extract in an inline pill at Quick — is the deviation from §D3.3, not the proposed fix.

**Part 2 — the condition, and why it is not a formality.**

The threshold tables can be treated as precision only while the **sufficiency state is invariant
to the frequency choice**. If the state a reader sees depends on which convention was picked, then
the convention pick is not derivation — it is the conclusion, and T1 catches it.

> **BINDING — frequency-invariance condition.** The PRD §14 deviation disclosure may be demoted
> out of `qualifierShort` **only while the sufficiency state computed under the daily table equals
> the sufficiency state computed under the weekly table applied to the weekly-equivalent
> observation count over the same window.** This must be **computed and asserted**, not assumed —
> a new `selfcheck.js` assertion, suggested id `beta.frequencyInvariantSufficiency`, with a proven
> falsification, in the style of the existing `binding1`–`binding4`.

**Part 3 — on today's fixture the condition FAILS, and the cause is a fixture defect.**

Derivation, so it can be checked rather than trusted. All inputs are read from
`designs/hg1-prototype-v2/js/data.js`:

1. `TRADING_DAYS = 504`; `END_DATE = 2026-09-03`; the `DATES` generator (`data.js:199–208`) walks
   backwards accepting any day where `getUTCDay()` is not 0 or 6 — i.e. **weekdays only, with no
   market holidays modelled at all**.
2. The 1Y slice is `i1y = 504 − 252`, so the window is the last **252** weekdays:
   `WINDOW_START_DATE = 2025-09-17`, `WINDOW_END_DATE = 2026-09-03` (both as rendered in the
   caveat under review).
3. 2025-09-17 is a **Wednesday** (2025-01-01 was a Wednesday; day-of-year 260; (260−1) mod 7 = 0).
   2026-09-03 is a **Thursday** (2026-01-01 was a Thursday; day-of-year 246; (246−1) mod 7 = 0).
4. Inclusive span = **352 calendar days** = 50 weeks + 2 days. Weekday check: 50 × 5 = 250, plus
   the trailing Wednesday and Thursday = **252**. This reconciles with `WINDOW_OBS_COUNT = 252`
   and confirms the span.
5. **Weekly resample of the same 352-day span:** on a Wednesday anchor, 2025-09-17 … 2026-09-02 =
   51 price points = **50 weekly returns**. On a Friday anchor, 2025-09-19 … 2026-08-28 = 50 price
   points = **49 weekly returns**. So the weekly-equivalent count is **49–50, under any weekday
   anchor.**
6. Apply the two tables from `HG1_ROUND4_METHODOLOGY_FINDINGS.md` §1.4:
   - **daily:** 252 ∈ [250, 749] → **`LIMITED`**
   - **weekly:** 49–50 < 52 → **`INSUFFICIENT_DATA`**

**The two conventions disagree, and they disagree across the line that separates "a number with a
qualifier" from "no number at all."** Under P5, `INSUFFICIENT_DATA` suppresses the value; it does
not soften it.

**Root cause, and what it is not.** This is **not** a defect in the threshold table. My
predecessor built the two rows to describe *"the same calendar spans at daily frequency"* (§1.4),
and on a realistic calendar they do: ~252 real trading days ≈ 365 calendar days ≈ 52 weeks, and
both rows return `LIMITED`. The disagreement here is entirely an artefact of the fixture's
**holiday-free weekday calendar**, under which 252 "trading days" span 352 days — 11.6 months, not
twelve.

Three consequences, all recorded as findings:

- **F1 (this ruling's blocker condition).** The frequency-invariance assertion fails as the
  fixture stands.
- **F2 (§34 / P12).** `investorDetail` and `referencePoint` label this window *"trailing 1Y"* /
  *"trailing 1 year"* while it is 352 days (0.964 y). The stated convention is not what is
  computed. Small, but §34 exists for exactly this.
- **F3 (cross-border realism).** `data.js` models the **SSE holiday calendar** for the freshness
  axis (`SSE_HOLIDAY_DATES`, `sseSessionsElapsed`) and then generates every return series on a
  calendar with no holidays in any market. That is two calendars in one file, and it is the same
  class of problem my predecessor recorded at §1.2 D1.3 for `marketFactor`: *"a prototype whose
  data removes the product's hardest problem should not be used as evidence that the method
  handles it."* In a product whose premise is that US, Mainland China and Hong Kong calendars
  differ, a holiday-free return calendar is a substantive fixture defect, not a cosmetic one.

**Part 4 — what this means for the blocked UX round. It does not block it.**

The correct remedy is **F1's cause, not the qualifier's length**: add market holidays to the
fixture calendar so a 252-observation trailing-1Y window spans ~365 days and yields ≥ 52 weekly
observations. Both tables then return `LIMITED`, the invariance assertion passes, and the
demotion in Ruling 1(c) is unconditionally safe. That is a fixture change, it is independently
required by F3, and it is not a methodology change.

**Until the fixture is corrected**, `qualifierShort` must additionally disclose the disagreement.
The following interim string satisfies the ruling and fits the cap, so the UX can proceed
immediately without waiting on the data fix:

```
interim qualifierShort (en): limited (daily) · weekly default withholds
interim qualifierShort (zh): 有限(日频) · 周频默认将不予显示
```

English **42 characters**; Chinese **18 characters** (both measured, not hand-counted — see
§A.5). The longer form `limited (daily) · weekly default would withhold` also fits at **47**, but
with one character of headroom, which is not enough margin to be safe against a wording tweak.

**What I am explicitly NOT ruling.** I am **not** ruling that the daily deviation must be
reversed, nor that beta must be re-estimated weekly. That remains the open product/scheduling
decision my predecessor handed back at findings §9.1, and it is not mine to close. I am ruling
only on **where a disclosure must render**, and reporting F1–F3 as findings rather than resolving
them inside a rendering ruling.

## A.4 RULING 1(d) — every other claim whose caveat lands in a bounded slot

I swept every claim in `js/data.js` that reaches `renderMetricValue`. Two slots are affected:
`.metric-qualifier` (the `LIMITED` branch, `shell.js:908–912`) and `.metric-reason` (the
`INSUFFICIENT_DATA` branch, `shell.js:867–873`). The audit scoped S4 to the first; the second has
the identical unbounded-text property and I rule on it too rather than force a second round-trip.

### Verdict summary

**The split is safe for every `LIMITED` claim, with exactly one genuine exception, one placement
exception, and one item that should be deleted rather than compressed.**

### `LIMITED` — renders into `.metric-qualifier`

| Claim | Current caveat | Verdict |
|---|---|---|
| `metric.beta` | ~430 ch | **Safe**, under §A.1–A.3. |
| `exposure.currency` (`MISSING_FX_HISTORY`) | ~285 ch | **Safe on length; EXCEPTION on placement.** See below. |
| `holding.601318.SS.unrealizedGL` (Ping An, `thinlyTraded: true`) | ~108 ch | **Safe.** |
| `metric.benchmarkRelative` — **latent**, at 2–4 SSE sessions elapsed | ~330 ch | **GENUINE EXCEPTION — longer irreducible minimum.** See below. |

**`exposure.currency` — safe to shorten, but the placement is the real requirement.**
Its conclusion-changing proposition is that **the conversions below were made at a single fixed
illustrative snapshot rate and are not reconciled to any rate date** — a reader who does not see
it believes the CNY column is a real dated conversion (T2). That compresses fine. What does *not*
compress is where it must appear: the parent claim renders `"See breakdown"` and carries no
number, while the **misleading figures are the child segments**. A qualifier on the parent does
not discharge the disclosure for a reader looking at a CNY bar.

> **BINDING.** The illustrative-FX disclosure must be present at **every rendering unit that
> displays a CNY-converted amount derived from the snapshot rate**, not only on the parent
> `exposure.currency` claim. This is an exception in *placement*, not in *length*.

```
qualifierShort (en): limited · one illustrative FX snapshot rate     (43 ch)
qualifierShort (zh): 有限 · 统一示例性汇率快照                          (14 ch)
```

**Ping An unrealized G/L — safe, with one wording correction.**

```
qualifierShort (en): limited · thinly traded; price prints sparse    (44 ch)
qualifierShort (zh): 有限 · 交易稀少,价格数据零散                      (16 ch)
```

Separately: the existing caveat says the sparse prints are *"widening the effective confidence
band on this figure."* **No confidence band is computed for a per-position unrealized gain/loss.**
That is a statistical term applied where no interval exists, and it should be reworded in
`caveatFull` as well as omitted from the short form. Minor, but it is the claim-traceability
class PD-0014 §2.2 covers.

**`metric.benchmarkRelative` — the one genuine exception.**

Today this claim is `AVAILABLE` + `STALE_DATA` (`CN_SESSIONS_ELAPSED = 1`), so it takes the
freshness-pill branch, not the qualifier branch. **At 2–4 SSE sessions elapsed
`sseSufficiencyForSessions` returns `LIMITED` + `STALE_DATA`**, and its ~330-character
comparability note lands in `.metric-qualifier`. Its irreducible content is **two distinct
propositions, not one**:

1. the **sufficiency** limitation — inputs are N sessions stale; and
2. the **temporal-comparability** limitation — the two legs are not measured at the same instant
   and the difference shown includes that timing gap. PD-0014 Part 1 §1.2 point 2 makes this
   mandatory for the two-leg class and forbids "not degraded" as a claim about it. It is a
   **separate disclosure dimension**, not a sufficiency qualifier, and it does not compete for the
   qualifier's budget: it already has its own bounded pill,
   `common.comparabilityFlag` (`Limited comparability` / `可比性受限`).

So the length is not the problem. **The problem the split would create is this:**
`renderComparabilityFlagEl` (`shell.js:1314–1323`) puts the pill's explanatory note **only in a
`title=` attribute**. Today that is masked, because `appendCaveatSlot` renders the same note as
`claim.caveat` at every depth. **Demote the caveat to Simple/Professional and, at Quick, the
content of a PD-0014-mandated disclosure exists solely in a hover tooltip** — not keyboard
reachable, not touch reachable, and precisely what §D3.2 rules out ("not a tooltip-only
footnote"). That is a P3 regression manufactured by the fix.

> **BINDING.** The split is safe for `metric.benchmarkRelative` **only if** the comparability note
> gains a non-tooltip rendering reachable at Quick — a pill that is a button opening the note
> satisfies both this and AC-S5.5's one-click rule. Until then, its caveat may not be demoted.

```
qualifierShort (en), LIMITED case: limited · A-share leg 3 sessions stale   (38 ch)
qualifierShort (zh), LIMITED case: 有限 · A股端已滞后3个交易日                 (16 ch)
```
(session count interpolated from `CN_SESSIONS_ELAPSED`, never hardcoded — B1 applies.)

### `INSUFFICIENT_DATA` — renders into `.metric-reason` (outside S4's stated scope; ruled anyway)

| Claim | Current caveat | Verdict |
|---|---|---|
| `metric.sortino` | ~330 ch | **Delete, do not compress.** See below. |
| `metric.contributionToRisk` — Mainland China Sleeve segment | ~123 ch | Safe. Irreducible: the figure is *withheld pending recalculation*, and the displayed shares therefore do not sum to 100%. |
| `holding.*.unrealizedGL` (`MISSING_COST_BASIS`) | ~110 ch | Safe. |
| `holding.2800.HK.riskMetrics` (`UNSUPPORTED_ASSET`) | ~84 ch | Safe. |
| `transaction.tx-0029.fxConversion` (`MISSING_FX_HISTORY`) | ~90 ch | Safe. Irreducible: **"withheld, not estimated."** That clause must survive any compression — it is the whole P5 content. |
| `metric.benchmarkRelative` — latent, at ≥5 SSE sessions | ~330 ch | Same exception as its `LIMITED` case above. |
| scenario Sharpe (`MISSING_BENCHMARK`, `data.js:1965`) | ~110 ch | Safe. |

**`metric.sortino` — a recommendation, not a ruling.** Its caveat is *prototype scaffolding*: the
metric is withheld "to demonstrate the `INSUFFICIENT_DATA` rendering path," and the caveat then
has to spend most of its length un-saying the implication ("this is not a claim that the current
sample is actually insufficient") — which is genuinely conclusion-changing under T1 and therefore
cannot simply be dropped. Compressing scaffolding is the wrong repair. **RECOMMENDATION:** remove
the demonstration claim before V1 and demonstrate the render path with a metric that is genuinely
insufficient, or set the downside-observation threshold (still open; `methodology.sortino`
records no minimum). Interim string if it must ship as-is:

```
metric-reason (en): withheld to demo this state; no threshold set   (45 ch)
metric-reason (zh): 为演示该状态而隐去;尚未设定阈值                    (16 ch)
```

## A.5 How the character counts above were obtained

Every count in this document was **measured**, not hand-counted:
`printf '%s' "<string>" | wc -m` under `LC_ALL=en_US.UTF-8`, which counts characters rather than
bytes and therefore matches JavaScript `String.length` for every character used here (all are in
the BMP; none is a surrogate pair). Three of my initial hand-counts were wrong by 1–2 characters —
all in the conservative direction, none breaching the cap, and all corrected above. Recording this
because a length cap that is enforced by a build guard (AC-S4.1) must be specified against a
measurement, not an estimate.

**The alternate English form for beta**, `limited · 252 daily obs · below the 3Y standard`,
measures **47** — inside the cap but with one character of headroom. The 45-character primary form
is preferred for that reason as well as on wording.

---

# Part B — Ruling 2: the SML x-domain

## B.1 The question

`charts.js:968` sets `xMin = Math.min(0, min(betas)) − 0.1`, forcing β = 0 into view; the audit
measures the consequence as points crowding into the right ~35% of the plot with ~65% empty. Must
β = 0 remain visible **because the line's intercept there is the risk-free rate**, or may the
domain be data-driven?

## RULING 2 — β = 0 is **not** required to remain visible. The domain may be data-driven.

**The empty area is not a correctness requirement.** It may be removed. It should not be recorded
as an accepted defect, because it is not defending anything.

### Why

1. **What the chart must let a reader do, and none of it needs β = 0.** Three things: locate each
   point's (β, realized return); read each point's **vertical distance to the line** — the
   annotated quantity, concept 4 per `HG1_ROUND4_METHODOLOGY_FINDINGS.md` §2.2, which is a
   *local* property at each point's own β; and see the sign of the line's slope. A slope is
   readable from any two points on a labelled linear axis; it does not require the intercept.

2. **The intercept at β = 0 is a parameter of the line, not an observation from it.** The line is
   defined as `y(β) = R_f + β·(R_b,realized − R_f)` with `R_f` an input constant (4.5% p.a.). It
   is *stipulated*, not estimated. A reader does not — and must not — read `R_f` off the chart;
   they read it from the required line annotation. Findings §2.4 already mandates that annotation
   **adjacent to the line and not in a tooltip**, stating `R_f = 4.5% p.a.` and
   `realized benchmark return = −5.11%` in words. **That annotation is the disclosure mechanism;
   the visual intercept is redundant with it.** Under P9 the obligation is satisfied by a stated
   parameter with an audit path, which this has.

3. **The chart already excludes its own y-origin** — `yMin = min(ys) − 0.05` — and no one has
   argued that breaks the reading. Demanding zero-inclusion on one axis of a scatter while the
   other is data-driven is not a convention; it is an inconsistency. Zero-inclusion is a
   requirement for **length-encoded** marks (bars), where the mark's extent *is* the value. This
   is **position-encoded**, with labelled ticks. Truncation is standard and legitimate here.

4. **The anchor that is actually load-bearing is β = 1, not β = 0.** By construction
   `y(1) = R_f + 1·(R_b − R_f) = R_b`: the line passes exactly through the plotted benchmark
   point. That is the construction fact a reader can verify on-screen, and β = 1 is additionally
   the **reference point (P4)** against which every plotted beta is read. Forcing β = 0 into view
   costs ~65% of the plot to display a point where no asset exists and an intercept already given
   in text, while offering nothing that β = 1 does not already offer better.

### Binding conditions on a data-driven domain

Removing the zero-anchor introduces two real distortions. Both are guarded, not waved through.

> **RULING 2(i) — β = 1 must always be inside the domain, with a labelled tick.** It is the
> benchmark's own beta, the point the line passes through by construction, and the P4 reference
> point. Losing it would breach P4. Today's `niceTicks(xMin, xMax, 4)` happens to place a tick at
> 1.0; that must become a requirement rather than an accident.

> **RULING 2(ii) — minimum domain width, to prevent cluster magnification.** These betas are
> tightly clustered (portfolio 0.994, benchmark 1.000 exactly — the first from
> `HG1_ROUND4_VERIFICATION.md` §9, the second by construction). A domain fitted tightly to a
> cluster would render beta differences **smaller than the estimate's own standard error** as
> large horizontal separations — visually asserting a distinction the data does not support. That
> is the same error class the 1.96 se directional threshold exists to prevent, appearing in
> geometry instead of prose.
>
> **The rendered x-domain width must be at least `4 × (CI95_upper − CI95_lower)` for the portfolio
> beta, and never less than 0.5 beta units.**
>
> On this data: CI95 = [0.9118, 1.0762] (`HG1_ROUND4_VERIFICATION.md` §9), width **0.1644**;
> 4 × 0.1644 = **0.658**. So the domain must span ≥ 0.658.
>
> **The multiplier 4 is a convention I am setting, not a derived result, and I say so plainly.**
> Its rationale: at 4× the CI width the 95% interval occupies one quarter of the plot, so a beta
> difference that is not statistically distinguishable cannot become the dominant horizontal
> feature of the chart. The 0.5 floor is the fallback where no standard error exists — the three
> sleeve points carry none. Both constants are revisable by this role; neither may be changed by
> `designer` or `product_manager` (PD-0014 §3).

> **RULING 2(iii) — zero must not be *implied*.** No zero baseline, no axis break, no origin
> marker, no length-encoded mark on this axis. The axis must remain a labelled linear scale with
> **at least three labelled ticks**, so the domain is legible from the axis itself and the
> leftmost gridline cannot be misread as β = 0.

> **RULING 2(iv) — the line annotation stays.** Because the reader loses the visual read of `R_f`,
> the annotation required by findings §2.4 — naming `R_f` and the realized benchmark return, in
> words, adjacent to the line — must render **at every depth at which the chart itself renders**.
> If Analytics gains a Quick mode under audit finding S5, the chart and this annotation rise and
> fall together. A chart whose defining parameters are not shown is not auditable (P9).

### RECOMMENDATION — a deterministic domain rule satisfying (i)–(iii)

Not binding as to form; binding only in that whatever is implemented must satisfy the four
rulings and must be deterministic under NFR-001/P12.

```
βlo = min(min(plotted betas), 1.0)
βhi = max(max(plotted betas), 1.0)                  # Ruling 2(i)
pad = max(0.05, 0.08 × (βhi − βlo))
lo  = βlo − pad ;  hi = βhi + pad
wmin = max(0.5, 4 × (BETA_CI95[1] − BETA_CI95[0]))  # Ruling 2(ii); = 0.658 today
if (hi − lo) < wmin: expand symmetrically about (lo+hi)/2 until (hi − lo) = wmin
```

Every input is a value already computed in `data.js`; no new estimation, no new convention beyond
the two constants named in 2(ii). **I did not recompute the three sleeve betas and therefore do
not state the resulting numeric domain** — it is whatever the rule yields, and the rule holds for
any sleeve beta set.

### What Ruling 2 does not touch

The line's mathematics is untouched. **The ex-post market line slopes downward because the
realized market premium over this window is negative** (`R_b = −5.11%`, `R_f = +4.5%`, premium
`−9.61%`), and that is correct, settled, and must not be "fixed" — PD-0014 §3's one explicit
prohibition, and findings §2.5. Also untouched: the intercept's value, the vertical-distance
quantity (concept 4) and its distinctness from regression alpha, the y-domain, and the point set.
Changing the x-domain changes the rendered angle of the line but not its slope, which is stated
numerically in the annotation Ruling 2(iv) preserves.

---

# Part C — What I did not determine, and what would settle it

- **The three sleeve betas.** Not recomputed; I did not execute the implementation. Ruling 2 is
  written to be independent of them. Settled by a live run, or by an independent recomputation
  from `pearson(sleeve, benchmark) × σ_sleeve / σ_benchmark` on the same window.
- **Rendered pixel widths.** My width estimates use `charts.js`'s own 6.0px-per-Latin-glyph
  constant and 1 em for CJK. These are estimates, flagged as a recommendation, and are exactly the
  script-blind measurement the audit raised as S2. Settled by a browser probe at 1440×900 in both
  languages — the same probe AC-S4.1 requires.
- **The magnitude of the Epps bias on this beta.** Not determinable in this harness. There is no
  network egress and no market-data vendor access, and — as my predecessor recorded at §1.2 D1.3 —
  the synthetic generator builds every sleeve from a single contemporaneous `marketFactor`, so the
  fixture **cannot** exhibit non-synchronous-close bias at all. The *direction* of the bias (toward
  zero, hence beta downward) is established in the literature and is already recorded in
  `methodology.beta.knownLimitations`; the *magnitude* on this portfolio is not determinable here
  and I have not asserted one. It would be settled only by real multi-market price data.
- **Whether the daily deviation should be reversed.** Out of scope by design; open at findings
  §9.1 as a product/scheduling decision.

# Part D — Findings raised by this work, for the parent to route

| id | Finding | Class |
|---|---|---|
| **F1** | Beta's sufficiency state is **not** invariant to the §14 frequency choice on this fixture: daily 252 → `LIMITED`; weekly-equivalent 49–50 → `INSUFFICIENT_DATA`. Blocks the unconditional form of Ruling 1(c); interim string supplied. | methodology / fixture |
| **F2** | The window labelled "trailing 1Y" is 352 calendar days (0.964 y). Stated convention ≠ computed convention (§34, P12). | fixture |
| **F3** | `data.js` models the SSE holiday calendar for freshness and generates every return series on a holiday-free weekday calendar. Two calendars in one file, in a product whose premise is that the three markets' calendars differ. | fixture |
| **F4** | Shortening `claim.caveat` **in place** would silently strip the Proof Packet's `thresholds_limits_if_used` / `limitations` and break `binding4`. Add `qualifierShort`; do not rename `caveat`. | engineering, high risk |
| **F5** | `renderComparabilityFlagEl` carries its note only in `title=`. After the split this becomes a tooltip-only disclosure at Quick, breaching §D3.2 and P3. | design / engineering |
| **F6** | `binding4.beta.observationCountMatchesEvidence` must be extended to `qualifierShort`, else the newly-visible count is an unguarded parallel truth (PD-0014 §2.5). | engineering |
| **F7** | Ping An's caveat asserts a "confidence band" where no interval is computed. | claim traceability |
| **F8** | `metric.sortino`'s caveat is prototype scaffolding whose irreducible content is a self-negation; delete rather than compress. | product |
| **F9** | `referencePoint` does not render at the compact `focusableMetricCell` unit, so window/frequency are not stated there (§13.3, P4). Pre-existing; **not** created or resolved by this split. | design |

---

**Restated, because it is the thing most easily lost in a long document:** none of the above is an
approval. HG1 is `REVISION_REQUIRED` and `awaiting_human`, and only the designated human product
owner can change that.
