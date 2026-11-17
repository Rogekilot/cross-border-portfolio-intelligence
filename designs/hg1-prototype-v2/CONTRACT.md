# Module contract — HG1 revision-2 prototype (`designs/hg1-prototype-v2/`)

**Author:** `designer`, worker `designer-09`, phase 1 of a six-worker build.
**Authority:** `reviews/gates/HG1_DIRECTION_SELECTION.md` §4 (build contract),
`reviews/gates/HG1_REVISION_CYCLE_01.md`, `designs/FEATURE_DESIGN.md` §D1–D5,
`specs/OCR_INGESTION_ADDENDUM.md`. This document re-expresses those validated contracts
for a real DOM/browser surface; it does not re-decide any of them.
**Status:** **I could not execute or render any of this.** No browser or JS runtime
exists in this sandbox. Everything below is asserted from careful reading of the code I
wrote, not from having seen it run. `pm-01` will load every route in a real browser,
read the console, and report back — see the handoff note at the end of this document
and my final message for the precise list of what that means was/was not verified.

Four designers start the moment this is delivered and will never talk to me. If
something here is ambiguous, that ambiguity becomes four incompatible surfaces. Read
this whole document before writing `js/surfaces/*`, `js/ai.js`, or `js/evidence.js`.

> **Current HG1 status (2026-09-15).** HG1 was subsequently APPROVED — see
> `decisions/product/PD-0017-hg1-approved.md`, decided by the designated human product
> owner. This directory remains a design/prototype artifact, not production
> implementation, and it is not itself an approval record. The chronological round
> sections below (Integration-pass addendum, Checkpoint A passes, Round-3, HG1
> round-4, HG1 Round 5 and later) retain the gate-status statements that were TRUE FOR
> THOSE ROUNDS at the time each was written — e.g. "HG1 remains `REVISION_REQUIRED`" —
> and must not be read as the current gate decision; they are historical record, left
> unedited by this note. See the Post-HG1 Checkpoint-A addenda near the end of this file
> for the bounded revision history.

---

## Integration-pass addendum (designer-14, phase 3)

Phase 2 is finished; nothing is concurrent. `designer-14` owns the whole directory for
this pass and made the following changes, each described in more detail at its own
location in this file or in the file it touches:

- **Closed the CSS gap.** Phase-2 authors could not write `styles/app.css` (closed to
  them per §0 above), so several surfaces — most seriously Scenario Lab, whose classes
  had *no* rules at all — rendered unstyled. Every orphaned class found by a systematic
  extract-and-diff sweep now has a rule. See `styles/app.css`'s own section comments.
- **Added `metric.totalPortfolioValue`** (§5's shared claim registry) and wired
  Overview's total-value stat to it, with its own D4 evidence control alongside
  gain/loss's, per `designs/FEATURE_DESIGN.md` §D1 surface 1's explicit requirement.
- **Closed the scenario-evidence gap.** Added `APP.data.getScenarioComparisonClaim`
  (§3 below) as the single source both `scenario.js` and `ai.js` now delegate to, and
  registered a real Proof Packet for every composite id those two files construct —
  their own "Evidence" buttons on the SCENARIO side previously resolved to nothing.
- **Refined the `checkNarrativeSafety` scanner** (§6A below) with `APP.ui.selectorHTML`,
  an explicit, auditable way to render a selector/ordinal digit (e.g. "top 5 holdings")
  inside `.ai-narrative` without it being a claim-bearing chip — resolving the tension
  `js/ai.js`'s original author flagged rather than worked around silently.
- **Fixed a caveat/computation mismatch** in `exposure.currency`'s claim text (§9 of
  `js/data.js`) — the caveat asserted an exclusion the underlying computation never
  actually performed. Reworded to describe what the computation actually does.
- **Fixed `registerEvidenceFor`'s `scenario_id` field**, which always defaulted to
  `null` regardless of the claim's own `scenarioId` — a latent bug, now using the
  claim's real value.

No item above reopens a decision `CONTRACT.md` or `designs/FEATURE_DESIGN.md` already
settled; each is either closing a phase-2-reported gap this build's own contract
anticipated ("flag it, don't route around it"), or a self-audited defect found while
doing the CSS sweep. See `designs/hg1-prototype-v2/README.md`'s "Contradictions"
section for the one item considered and *not* found to be a baseline contradiction.

---

## Checkpoint A, pass 1 of 2 — visual-polish pass (`designer-15`)

**Authority:** `reviews/PM_ACCEPTANCE.md` §1, Conditions 1 and 2 (HG1 `APPROVED WITH
CONDITIONS`). Scope is a design-system/consistency pass on this approved artifact — no
IA change, no surface redesign, no new features. A second designer follows for
Condition 3's per-chart interpretability work and builds on the system recorded here.
**I could not execute or render any of this** — same constraint as every prior phase;
see this worker's handoff for the precise verified/not-verified list.

- **Chart families (Condition 1A).** `js/charts.js` now attaches a `chart-family-*`
  class to every chart it draws (hero/analytical/compact/donut/bar/scatter/matrix — see
  `styles/tokens.css`'s "chart family DIMENSIONS" block and `styles/app.css`'s
  `.chart-family-*` rules). Each caps the chart's own `max-width` at roughly its authored
  viewBox size. This is also the mechanism behind the Condition 1B fix below — an SVG's
  `width:100%` stretches to fill whatever container it lands in, and because chart type
  lives in the same viewBox user-coordinate space as everything else in the SVG, an
  oversized stretch is what was actually inflating chart typography, most visibly on
  Overview's Major Holdings bar chart (a 320-unit-wide chart dropped into an up-to-900px
  card). SML scatter widened (480→560 default) per the owner's explicit "wider plot"
  instruction; rolling-volatility/drawdown heights unified (180/160 → 200/200) since
  they always sit side by side in Analytics.
- **Typography tokens (Condition 1B).** `styles/tokens.css` adds nine named
  `--type-*` roles (page heading, card title, metric number, chart axis, chart category
  label, chart value label, annotation, table cell, secondary metadata). Every chart text
  class in `styles/app.css` (`.chart-tick`, `.chart-bar-label/value`, `.chart-donut-
  center`, `.chart-legend-label`, `.chart-scatter-label`, `.chart-heatmap-label/value`)
  now resolves to one of these instead of a literal px value. `js/charts.js` itself sets
  no font sizes at all — it only assigns class names, so the chart "library" cannot
  independently determine type scale, structurally, not by convention.
- **Holdings-table alignment (Condition 1C).** Numeric-column `<th>` elements now carry
  the same `.num` (right-align) class as their `<td>` cells in both holdings tables
  (`js/surfaces/portfolio.js`'s full ledger view and `js/surfaces/overview.js`'s
  condensed summary) and in the Transactions table — previously every header was
  left-aligned regardless of its column's own data alignment, so a right-aligned number
  sat under a left-aligned label. `table.data-table td.num` now states
  `font-variant-numeric: tabular-nums` explicitly (previously implied only by the
  monospace font). A missing avg-cost (in-kind transfer) no longer renders a full
  sentence jammed into the right-aligned numeric column; it is a short right-aligned
  placeholder (`.num-placeholder`) with the explanation moved to a `title` attribute.
  **Documented different row type:** Overview's condensed holdings table (Position /
  Weight / Market Value / Unrealized G/L / Risk Metrics) intentionally has fewer columns
  than Portfolio's full ledger table (adds Qty / Avg Cost / Price / Freshness / Actions)
  — this is a considered summary-vs-ledger distinction, not an inconsistency to close;
  both now share the same alignment/precision/tabular-numeral conventions.
- **Semantic color system (Condition 2).** `styles/tokens.css` adds `--color-positive`/
  `--color-negative`, applied by `js/shell.js`'s `renderMetricValue` ONLY when
  `js/data.js` has marked a claim `directional: true` (portfolio return, absolute/percent
  P&L, benchmark-relative performance, FX attribution, alpha, per-holding unrealized
  gain/loss — a deliberately short, explicit list; risk/ratio characteristics and
  SCENARIO-side figures never carry this flag) and sufficiency is plain `AVAILABLE`
  (`LIMITED` keeps its own amber treatment undiluted, by design). Portfolio-vs-benchmark
  stays teal-vs-gray exactly as it already was in this build (`--color-chart-portfolio`/
  `--color-chart-benchmark`) — that was already correct going into this pass; Condition
  2's fixes were: (a) there was previously NO green/red anywhere for a genuine gain/loss,
  now added; (b) the correlation heatmap previously colored positive/negative cells with
  the same teal/red pair used for portfolio/warning, implying a "good vs. bad" polarity
  correlation sign does not have — now a neutral gold/slate-blue diverging pair
  (`--color-heatmap-pos`/`--color-heatmap-neg`); (c) `--color-fresh-stale` previously
  reused the exact hex of `--color-severity-warning`/`--color-danger`, so a merely-stale
  price print read as identical alarm-red to a policy breach — now a deeper amber,
  staying in the "neutral/amber" family the owner's own table specifies for insufficient/
  stale data. Non-color encoding: the benchmark line's dashed stroke (already present)
  and formatPercent/formatCurrency's explicit "+"/"-" sign continue to carry the same
  information as color; a new `aria-hidden` `▲`/`▼` glyph is added next to every
  directional numeral as a third, redundant cue for a reader who cannot distinguish the
  color.
- **Self-audited fix, adjacent to this scope.** `renderMetricValue`'s defensive
  "no claim object at all" branch (distinct from a claim's own `INSUFFICIENT_DATA`
  state) rendered a bare em-dash — the exact pattern finding P-1 already named once.
  This branch is rarely exercised (every real caller checks the claim exists first), but
  "rarely executed" is how the previous recurrence hid too, so it is fixed here to a
  short "not available" label rather than left as a latent third copy.

**What I did not do, on purpose.** `metric.performanceAttribution` (a composite
formatted string, "Local X / FX Y") is not marked directional — coloring parts of a
pre-formatted string safely was judged out of proportion to this pass's scope; flagged
for whoever next touches that claim. Condition 3 (per-chart interpretability — SML axis
labeling, CAPM line legend, drawdown-as-underwater-chart, capital-weight-vs-risk-
contribution, correlation heatmap's AI conclusion) is explicitly the next designer's
work, not reopened here beyond the dimension/typography/color mechanics above.

---

## Checkpoint A, pass 2 of 2 — chart-interpretability pass (`designer-16`)

**Authority:** `reviews/PM_ACCEPTANCE.md` §1, Condition 3 (HG1 `APPROVED WITH
CONDITIONS`, decided 2026-09-05). Scope is per-chart interpretability on the system
`designer-15` already landed (chart families, typography tokens, holdings alignment,
semantic color) — no IA change, no new charts unless a named item required one, no new
features. **I could not execute or render any of this** — same constraint as every prior
phase; see this worker's handoff for the precise verified/not-verified list. Write path
was the whole `designs/hg1-prototype-v2/` directory (no other worker concurrent), so
unlike the phase-2 per-file ownership split above, this pass touched `js/charts.js`,
`js/data.js`, `js/surfaces/analytics.js`, `js/surfaces/overview.js`, `js/shell.js`, and
`styles/app.css` directly, all in service of the six named improvements.

- **Portfolio vs. benchmark (Overview hero + Analytics' identical Performance chart).**
  `APP.charts.lineCompare` now draws direct end labels (each series' period return),
  a persistent relative-performance callout, and a hover crosshair (mousemove on an
  invisible hit-rect finds the nearest date and shows both series' period-to-date return
  and their difference) — all computed from the exact arrays already passed in, nothing
  fetched separately. **Drawdown shading was removed from both callers** (`showDrawdown`
  is no longer passed) — a considered judgment, not a default-on assumption: it mixed two
  y-axes into one chart competing with the single question this chart answers ("who's
  ahead"), and a dedicated underwater chart already exists for "how deep did it fall."
  The parameter itself remains functional in `charts.js` for a future caller who judges
  differently.
- **SML / CAPM** (`APP.charts.scatter`) — the pass's single highest-value item per the
  owner's own framing. Added: explicit x/y axis titles ("Beta ...", "Historical
  annualized return"), a window/frequency subtitle ("Trailing 1Y · Daily returns"), a
  legend naming portfolio/benchmark/sleeve colors AND the Security Market Line, and a
  dashed alpha-connector + label drawing historical Jensen alpha as the literal vertical
  distance from the portfolio's point to the line — passed in from the SAME
  `metric.alpha` claim `js/data.js` already computes, never recomputed in the chart.
  `metric.sml`'s own `formatted` field — literally "See scatter" — is replaced with a
  real composed summary (β / Return / α), and its `caveat` states the P6 historical-only
  hedge explicitly.
- **Exposure** — `APP.charts.bar` gained an `item.displayValue` override and
  `APP.ui.formatExposureSegment(seg)` (shell.js) is now the one shared convention
  (percent-of-portfolio first, dollar second) both Overview's and Analytics' country/
  currency/sector/asset-class bars read through — previously Overview showed dollar only
  and Analytics showed percent only for the identical segment shape.
- **Risk contribution** — `CONTRIBUTION_TO_RISK` (`js/data.js`) now carries each
  segment's real capital `weight` (from the already-computed `SLEEVE_WEIGHTS`, previously
  never attached to this list). A new primitive, `APP.charts.pairedBar`, draws capital
  weight vs. risk contribution as aligned grouped bars per segment; the withheld
  (Mainland China) segment still shows its real weight with no fabricated
  risk-contribution bar (a dashed placeholder + "insufficient data" label instead — P5
  applied to a chart, not just a numeral). `APP.charts.bar` also gained `item.insufficient`
  support for the same reason.
- **Correlation** — the heatmap (Professional-depth, inside the inspector) is unchanged;
  Analytics' correlation block now also renders a plain `.ai-narrative` paragraph naming
  the strongest and weakest pairwise relationships in the SAME matrix already fetched,
  each numeral inside a provenance chip pointing at `metric.correlation`'s Evidence
  record (P1).
- **Drawdown** — `APP.charts.drawdown` (already a proper zero-at-top underwater chart)
  gained an optional benchmark reference line (P4), an explicit trough marker + label,
  and a legend; Analytics' Rolling & Drawdown block now passes the benchmark series it
  was already fetching but never plotting.

New shared primitives this pass added to the system (rather than hand-rolling around
it): `APP.charts.pairedBar`, `item.displayValue`/`item.insufficient` on `APP.charts.bar`,
`benchmarkValues` on `APP.charts.drawdown`, `windowLabel`/`alphaCallout` on
`APP.charts.scatter`, `showEndLabels`/`showHover` on `APP.charts.lineCompare`, and
`APP.ui.formatExposureSegment` in `shell.js`.

---

## Round-3 bounded visual-polish pass (`designer-17`)

**Authority:** `reviews/PM_ACCEPTANCE.md` §3 (round 3, `REVISION_REQUIRED` — "one bounded
visual-polish pass only"), the three remaining items its §4 names as outstanding after
Checkpoint A's two prior passes. **HG1 is not approved; this pass does not change that.**
No IA change, no new prototype functionality, no chart-count increase — this closes the
three named gaps on the system the two prior passes already built. **I could not execute
or render any of this** — same sandbox constraint as every prior phase; see this worker's
handoff for the precise verified/not-verified list. Write path was the whole
`designs/hg1-prototype-v2/` directory (no other worker concurrent).

- **Rolling-analytics shared grammar** (owner: *"Rolling analytics should share a
  coherent visual grammar rather than looking like unrelated charts placed in separate
  cards"*). `js/charts.js`'s `rollingLine` (90-day rolling volatility — used on both
  Analytics' Rolling Analytics & Drawdown block and Overview's risk snapshot, same
  primitive) and `drawdown` (the underwater chart) now read through one shared internal
  frame (`ROLLING_MARGIN` + `rollingSubtitle`/`rollingLegend`/`rollingYTicks`/
  `rollingXTicks`/`mountRollingHover`) instead of each hand-rolling its own margins,
  ticks, legend, and hover: identical margins and plot height (224px total, unified from
  200/160 with different top margins each); identical x-axis tick cadence
  (`pickDateTicks(dates, 4)`); a new shared y-axis gridline+percent-tick treatment
  (`drawdown` previously drew none at all); a `windowLabel` subtitle in the same class,
  position, and phrasing convention as the SML scatter's own window/frequency line
  (both rolling charts' callers now pass a string beginning "Trailing 1Y · Daily
  returns..."); a legend in the same position on both (`rollingLine` previously had none
  at all); and a generalized hover crosshair + per-date readout box
  (`mountRollingHover`, 1-or-2-series) on both, matching the hero chart's interaction
  model without reusing its hero-specific relative-performance-diff line, which has no
  meaning for a single-series rolling-volatility read. New family class
  `chart-family-rolling` (`styles/tokens.css`'s `--chart-rolling-max-width`,
  `styles/app.css`) gives this pair its own explicit identity, distinct from
  `chart-family-analytical` (still used by the local/FX attribution stacked bar, which
  is not a rolling time-series read). Both surface call sites
  (`js/surfaces/analytics.js`, `js/surfaces/overview.js`) updated to pass a
  `windowLabel`; the block-level `<h4>` captions were trimmed to drop the window/
  frequency phrasing now stated once, consistently, on the chart itself, rather than
  duplicated (and previously inconsistently worded) in prose above it.
- **Account/cash table strict grid** (owner: *"holdings/account tables"* — only Holdings
  received Condition 1C's treatment in Checkpoint A). `js/surfaces/portfolio.js`'s
  Accounts & Cash table now follows the identical pattern already used for Holdings: an
  `ACCOUNTS_COLS` array names which of its own columns are numeric so the `<th>` carries
  the same `.num` class as its `<td>`s; the Cash Balance(s) column is now right-aligned
  with tabular numerals via the same shared `ctx.ui.formatCurrency` convention every
  other monetary cell in this build uses (2 decimals, currency-code/symbol prefix,
  regardless of whether the row is USD, HKD, or CNY — checked specifically because the
  owner named multi-currency cash as the likely trouble spot: `acct-cash-1`, "Multi-
  Currency Cash Sweep," carries all three in one row and now renders through the exact
  same structure as a single-currency account); an account with no cash on file gets the
  same right-aligned cell with Holdings' existing `num-placeholder` treatment (short
  italic label, not a bare em-dash — P5 applied to a raw ledger field) rather than a
  left-aligned sentence breaking the column's rhythm. Every account row — one currency
  or three, taxable/retirement/cash type, US/HK/CN/GLOBAL market — now produces the
  identical five-cell structure; only the Cash Balance(s) cell's *content* varies.
- **Documented different row type, Holdings surface (unchanged behavior, now recorded
  rather than left implicit).** `js/surfaces/portfolio.js`'s `renderHoldingsBlock`
  renders a full ledger table per account only when that account has at least one
  holding; `acct-cash-1` (the multi-currency cash sweep) has cash but zero holdings, so
  its section on the Holdings surface is title + a "Cash: ..." summary line only, with
  no table at all — a different structural shape from every other account's section,
  which gets a table plus the same cash line beneath it. This is a deliberate
  consequence of what the account actually contains (there is nothing to tabulate in a
  ledger for an account with no positions), not an inconsistency to close: it is the
  same "no table where there is nothing to show a table of" reasoning already applied
  elsewhere in this build, now named explicitly per the owner's instruction to document
  any row type that legitimately differs. The Accounts & Cash table above (which this
  account DOES appear in as an ordinary row) is where its cash is shown in strict-grid
  form; this Holdings-surface omission is about the ledger table specifically, not about
  hiding the account or its cash balance.
- **Transactions table — checked, not substantially changed.** Quantity and Price/Amount
  were already right-aligned with tabular numerals (Checkpoint A). The
  "Reporting-Currency Conversion" column is deliberately NOT part of the strict numeric
  grid: for all but one transaction (`tx-0029`) it renders a plain sentence ("No
  conversion claim recorded..."), and for that one row a claim-shaped value via
  `renderMetricValue` alongside its own Evidence button — this is a narrative/claim
  column, not a numeric-magnitude column comparable across every row the way Quantity or
  Price/Amount are, so right-aligning it would isolate one numeral inside a column that
  is prose everywhere else rather than improve scannability. Left as-is; flagged here so
  it reads as a considered decision rather than an unexamined gap.
- **Stale gate-state claims** — checked `README.md`, `HUMAN_REVIEW_CHECKLIST.md`,
  `SIMULATED_VS_IMPLEMENTED.md`, and `index.html`'s banner. **None asserted or implied
  HG1 approval.** `README.md` already states "HG1 remains `REVISION_REQUIRED` and
  `AWAITING_HUMAN_REVIEW`"; `index.html`'s banner already states "HG1 remains
  REVISION_REQUIRED" (left unchanged, per instruction); `SIMULATED_VS_IMPLEMENTED.md`
  does not reference gate status at all. No correction was needed or made to any of
  these four files.

### Follow-up fix within this same pass, after `pm-01`'s first browser check

`pm-01` verified the three items above clean in a real browser (rolling grammar,
Accounts & Cash, zero console errors, zero em-dash-only nodes) but found one remaining
alignment defect squarely on the owner's own named judging criterion 3 ("holdings/table
alignment"): Holdings' **Unrealized G/L** column — the one numeric cell built from a
claim (`APP.ui.renderMetricValue`'s directional glyph + numeral path) rather than a
plain formatted string — carried no `.num` class on its `<td>` at all (`text-align:
start`, `font-variant-numeric: normal`), disagreeing with its own correctly-`.num`
header, while every other numeric column in the same table was correct.

- **Fix:** `js/surfaces/portfolio.js` — a new local helper, `claimNumCell(ctx, claim)`,
  builds the `<td className="num">` and calls `renderMetricValue` into it, replacing the
  bare `el("td", {})` the G/L cell was previously built with. Deliberately fixed at this
  cell-construction level (a reusable local constructor), not by adding a class at the
  one call site — `renderMetricValue` itself (`js/shell.js`) is reused in many
  non-tabular contexts (metric-strip cells, claim cards) where forcing right-alignment
  would be wrong, so the fix belongs in this table's own cell-construction step, not in
  the shared renderer. The directional glyph and numeral do not need visual separation
  to land in a strict right-aligned track: `renderMetricValue`'s wrap is a single
  inline-flex unit with the numeral trailing, so the numeral's edge — not the glyph's —
  is what text-align:right positions against the column's right edge, same as every
  other right-aligned cell in this table.
- **Related second defect, found by the same inspection and fixed the same way:** a
  claim's numeral (`.metric-number`) carries `--type-metric-number` (this build's
  largest numeral size, authored for stat cards) with no awareness of being mounted
  inside a dense table row, so it was rendering visibly larger than every plain-
  formatted numeral beside it in the same row — a second, independent violation of
  Condition 1B's "do not allow [a component] to invent its own type hierarchy," this
  time in the shared claim renderer rather than in `charts.js`. Fixed with one scoped
  rule, `table.data-table .metric-number { font-size: var(--type-table-cell); font-
  weight: 600; }` (`styles/app.css`), which also corrects Transactions' rare
  claim-rendered conversion figure (`tx-0029`) to the same table-appropriate scale.
- **Both fixes above were subsequently browser-verified by `pm-01`** — all 13 ledger
  rows now render Unrealized G/L at `class="num"`, right-aligned, tabular-nums, correct
  13px scale, and the `INSUFFICIENT_DATA` case renders correctly with no bare em-dash.
  Zero console errors.

### Second follow-up: cross-account column-grid drift

`pm-01`'s same browser pass found one more, smaller defect: Holdings renders one
`<table>` per account, and a browser's default (auto) table-layout sizes each table's
columns from its own content only — so although every column now aligned perfectly
*within* each account's table (the fix above), the four account tables did not share the
same column widths as EACH OTHER. Measured: a 17px spread on the G/L column's right edge
between the widest and narrowest account section.

- **Fix:** `js/surfaces/portfolio.js` — `HOLDINGS_COLS` entries now carry an explicit
  `width` (percentage, summing to 100), consumed by a new `holdingsColgroup()` helper
  that builds one `<colgroup>` per table; `styles/app.css` adds `table-layout: fixed` on
  a new class, `.holdings-ledger-table`, applied only to these per-account ledger tables
  (not `table.data-table` generally — Accounts & Cash and Transactions are single
  tables with a different column count and never had this cross-table problem; leaving
  them on normal auto layout is correct). Every account's table now resolves to the same
  track widths regardless of its own content, so the grid is continuous down the whole
  page, not just self-consistent within each account's own section.
- **Scope check performed before making this change, per the coordinator's explicit
  instruction to stop and report rather than let the pass expand if the fix turned out
  not to be small:** confirmed it was a single `<colgroup>`/CSS-class addition, isolated
  to the one file already being edited in this pass, with no change to `renderMetricValue`,
  `claimNumCell`, or any other surface — judged small enough to proceed rather than
  escalate.
- **Residual risk, not fully eliminated:** `table-layout: fixed` makes the browser honor
  the declared percentage widths instead of expanding a column to fit its longest
  content, so a column whose real content is wider than its assigned percentage (the
  Security column's longest name, or the Freshness pill's `white-space: nowrap` text) at
  a narrow enough viewport could wrap or visually crowd its neighbor rather than expand.
  This was not observed by hand-tracing but was not (and could not be) rendered in this
  sandbox to confirm at every viewport width — flagged for `pm-01`'s check, per
  `CHANGELOG_VISUAL_POLISH.md`.
- **Subsequently browser-verified by `pm-01`** — the Unrealized G/L column resolves to
  one right edge (1010px) across all 13 rows in all 4 tables, where it previously
  stepped between 978/991/993/995px. Zero console errors.

### Third follow-up: Freshness/column-width rebalance

The residual risk named above materialized exactly as flagged: Freshness's original
10% (95px) was 27px narrower than its own pill (114px) needed once `table-layout: fixed`
stopped letting the column expand to fit it, so the pill visibly spilled 27px into the
Actions column. `overflow` was `visible`, so nothing was clipped or hidden (no P10
breach — freshness stayed fully readable), but a column overlapping its neighbor is a
worse table defect than the 17px cross-table variance the fixed layout was introduced to
remove.

- **Decision: rebalance, not revert.** The coordinator offered both as acceptable
  outcomes. Rebalancing was chosen because the two donor columns below could be checked
  against this build's own actual dataset (`js/data.js`) rather than assumed safe,
  giving a specific, checkable basis for confidence rather than a guess.
- **Fix:** `HOLDINGS_COLS` (`js/surfaces/portfolio.js`) rebalanced — Freshness 10 → 13.5
  (~128px at this table's ~950px measured width, at/above the 122-125px `pm-01` measured
  as needed, with a few px of margin rather than an exact fit). Donors:
  - **Qty 7 → 6** — every quantity in `HOLDINGS` is ≤ 4 digits ("2000" is the longest);
    checked directly against the data, not assumed.
  - **Market Value (USD) 13 → 10.5** — the largest of all 13 holdings' computed
    `marketValueUSD` is VOO's $43,545.50 (10 characters, "$43,545.50"), always USD so
    never carrying a currency-code prefix; checked as the specific worst case, not
    assumed from "it's a numeric column."
  - **Avg Cost, Price, % of Portfolio deliberately left untouched**, even though the
    coordinator named all four as candidate donors: checking the actual data showed
    Avg Cost's and Price's own worst-case values carry a currency-code prefix for
    non-USD holdings (e.g. Price on `600519.SS` formats to "CNY 1,542.00", 12
    characters) that already runs closer to their column's assigned width than Qty's or
    Market Value's worst case does — shrinking them further was judged the higher-risk
    move, not a safe one just because the column is numeric.
  - **Security checked, left unchanged** — its longest value, "iShares 20+ Year
    Treasury Bond ETF," wraps onto a second line by design (no `nowrap` anywhere on
    that cell) rather than forcing an unbroken run past its column, so it was never
    actually exposed to the hard `scrollWidth > clientWidth` failure this fix is judged
    against, regardless of its assigned width.
  - **Unrealized G/L left unchanged** — it was the column already independently
    browser-verified correct in the prior follow-up; touching it here would trade a
    verified-good result for an unverified one for no reason.
- **Subsequently browser-verified by `pm-01`, partially.** Overflowing cells went from
  14 to 4; the single shared right edge held across all four tables and all 13 rows
  (measured at 977px); zero console errors. The donor analysis for Qty and Market Value
  was confirmed sound — neither gave up more than it could spare. The remaining 4 cells
  (see next section) were a worst-case-selection error in the WIDTH TARGET this worker
  chose for Freshness and Unrealized G/L, not a flaw in the donor/mechanism reasoning
  itself.

### Fourth follow-up: second rebalance — sizing against the wrong worst case

Real-browser measurement found 4 cells still over, with exact figures:

| Cell | needs | had | short by |
|---|---|---|---|
| `CN A-share · Stale` (Freshness) ×3 | 140px | 128px | 12px |
| `insufficient data` + reason (Unrealized G/L, `600519.SS`) ×1 | 138px | 114px | 24px |

**The lesson, stated plainly because it is worth keeping for whoever sizes a column
like this next:** both misses were a worst-case-SELECTION error, not an arithmetic one.

- Freshness (13.5%, ~128px) was sized against this dataset's two HEALTHY-state
  freshness pills ("US equity · Live" 122px, "HK equity · EOD" 125px) — the values that
  happened to come to mind, not the widest value actually present. The real worst case,
  "CN A-share · Stale" at 140px, is both the longest label AND the only stale axis in
  this dataset — a degraded freshness state adds words ("· Stale") that a healthy state
  doesn't need. **In a cross-border, multi-freshness-axis product, the widest value in
  a freshness/state column will tend to be the degraded case, not the healthy one.**
  Sizing that kind of column against its healthy-state value will under-size it every
  time; size against the worst state actually present in the data.
- Unrealized G/L (12%, ~114px) was sized against a plain directional numeral
  ("▲ +56.2%" and similar) — this column's common case, not its own worst case. D3.2's
  own rule is that `INSUFFICIENT_DATA` renders a labeled component (the "insufficient
  data" text plus its reason), not a numeral — structurally wider than anything the
  common case renders, by construction. A numeric-looking column whose values are
  claim-rendered (this pass's own earlier fix, `claimNumCell`) must be sized against its
  own non-numeral states too, not just the numeral it usually shows.

- **Fix:** both widened against the REAL worst case this time (140px, 138px), with a
  deliberate margin rather than an exact fit — Freshness 13.5 → 16 (~152px, ~12px
  margin over 140), Unrealized G/L 12 → 16 (~152px, ~14px margin over 138). Donor:
  **Security 22 → 15.5**, taking the full +6.5 points needed for both. Security was
  named explicitly (again) as the correct donor because it is the one column
  structurally immune to this failure (established twice now: it wraps by design, no
  `nowrap` anywhere on that cell), so it can absorb whatever either of the other two
  still needs without itself becoming a new hard-overflow risk. Qty, Avg Cost, Price,
  Market Value, and % of Portfolio are untouched from the prior rebalance — none were
  reported as still short, and re-touching an already-verified-sufficient column risks
  reopening a defect that is not actually present.
- **Alternative considered and not taken:** letting the `insufficient data` label wrap
  onto two lines instead of spending column width on Unrealized G/L. Not chosen because
  the width-based mechanism is already the established, twice-verified lever for this
  exact problem, and reusing it keeps the fix's mechanism uniform (one lever, reasoned
  about the same way each time) rather than introducing a second, unverified variable
  (a wrap behavior change) alongside it. Recorded here so it is not silently lost as an
  option if a future width-only pass ever runs out of donor room.
- **Not yet browser-verified** — this second rebalance was made after `pm-01`'s fourth
  browser pass, in response to it. The stated test is unchanged: no cell's `scrollWidth`
  exceeds its `clientWidth` in any of the four tables, with the single shared right edge
  preserved.

No item above reopens a decision this file, `designs/FEATURE_DESIGN.md`, or
`reviews/PM_ACCEPTANCE.md` already settled. See this worker's handoff for the full
verified/not-verified account.

---

## HG1 round-4 addendum — analytical-truth correction pass (designer-19)

**Authority:** `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md` (`quant_analyst`, worker
`quant-01`) and `decisions/product/PD-0014-comparability-contract-and-claim-traceability-
invariant.md`. **HG1 remains `REVISION_REQUIRED`, ACTIVE, UNAPPROVED** — nothing below is
an approval or implies one, and corrected outputs still require independent
`quant_analyst` re-verification before this gate can return (PD-0014 §3). Write path for
this pass was exactly `js/data.js`, `js/selfcheck.js` (new), and this addendum — `styles/`,
`js/charts.js`, `js/shell.js`, and `js/surfaces/*.js` were concurrently owned by a sibling
designer and are **not** touched by this entry.

### What changed, and why

The first `quant_analyst` ever engaged on this project found that this prototype's own
prose contradicted its own numbers in at least four places (beta "moved more" at β<1;
"HK and Mainland China contribute the most" when US was largest and CN was withheld;
"HK and CN move together strongly" when that pair was the *weakest* equity correlation
in the matrix; a beta observation-count caveat that disagreed with the same claim's own
Proof Packet), and that the prototype maintained parallel truths (a hardcoded 40/30/20/10
sleeve-weight mix for every risk statistic, vs. the ~48/35/10/6 the exposure surfaces
actually computed from holdings). `js/data.js` is rebuilt around one canonical portfolio
state and the class of defect the four findings exemplify; `js/selfcheck.js` is new and
implements PD-0014 §2.2's claim-traceability invariant as a set of assertions that run at
page load. Full detail — every correction, its quant specification, and what remains
open — is in this worker's handoff to `pm-01`; this addendum records the **contract-level**
facts a future reader of this file needs, not the full narrative.

### One canonical portfolio state (PD-0014 §2.5)

`SLEEVE_WEIGHTS` in `js/data.js` is now **derived from `HOLDINGS`' actual market values**
(via a `sleeveKeyForHolding(h)` classifier — bond by `assetClass`, else by
`listingMarket`), not a hardcoded literal. `ACCOUNTS`/`CASH_BALANCES`/`FX_RATES`/
`HOLDINGS`/`marketValueUSD` moved earlier in the file (new §1.5) so this derivation can
happen before the return series are generated. This changed every risk/return figure on
the Analytics surface — expected and required, not a regression. The portfolio return
series (`portfolioReturns`, the one every accessor now reads) also **genuinely applies
FX** to the Hong Kong and Mainland China sleeves for the first time (it previously
contained none at all); a separate `portfolioReturnsLocal` series (FX held at the
period-start rate) exists only to support the FX-attribution decomposition below. The
Sleeve Correlation Matrix (`metric.correlation`) deliberately keeps the **local-currency**
sleeve series — a different, legitimate analytical question that `quant_analyst`
validated against and did not ask to change.

### Accessor changes (additive, backward-compatible)

- **`APP.data.getSMLPoints()`** now also returns `verticalDistance` — the SML chart's
  actual vertical distance from the portfolio's point to the ex-post line (concept 4 in
  the methodology findings' terminology), computed as `PERIOD_RETURN −
  (SML_LINE.intercept + BETA×SML_LINE.slope)`. **This is a different quantity from
  `metric.alpha.value`** (concept 3 — an OLS regression estimate, arithmetic-annualized).
  `js/surfaces/analytics.js:371-378` currently wires `alphaClaimForChart.value`
  (`metric.alpha`, concept 3) into `APP.charts.scatter`'s `alphaCallout`, which draws it
  as the line's literal vertical distance — this is the exact defect
  `HG1_ROUND4_METHODOLOGY_FINDINGS.md` §2.2 names. **Needed change, outside this
  designer's write path:** that call site should read `smlData.verticalDistance` instead.
  The regression alpha remains available as its own claim (`metric.beta`'s sibling
  `metric.alpha`) for a side-panel display with its own stated basis.
- **`APP.data.getFxAttributionDetail()`** — new accessor. Returns
  `{ portfolio: {local, fxEffect, base}, sleeves: { hk: {local, fx, interaction, base,
  weight}, cn: {…} }, excludes, fixingTimeNote }`, the per-sleeve local/FX/compounding-
  interaction/base breakdown `HG1_ROUND4_METHODOLOGY_FINDINGS.md` §4.4 item 4 requires at
  Investor depth or deeper. **Not yet consumed by any surface** — `js/surfaces/
  analytics.js`'s FX waterfall block currently only shows the portfolio-level two-bar
  split. Its existing `localVal = retClaim.value − fxClaim.value` computation is
  **no longer wrong** — it now reconstructs `PERIOD_RETURN_LOCAL` exactly, because
  `metric.fxAttribution.value` is defined as `PERIOD_RETURN − PERIOD_RETURN_LOCAL` (exact
  by construction) — but the sleeve-level breakdown itself needs a new call site.
- **`claim.freshness.comparability`** — new optional sub-field, `{ limited: boolean, note:
  string }`, on `metric.benchmarkRelative`'s `freshness` object (PD-0014 Part 1 §1.2 point
  2: comparability is a disclosure dimension alongside freshness, not a new sufficiency
  state or reason code). **`js/shell.js`'s `renderMetricValue` has no rendering branch for
  this field** — today the disclosure reaches the user only through `claim.caveat`
  (which `renderClaim`'s ladder always renders, per this file's own §6A), not through the
  compact `renderMetricValue` path `analytics.js`'s metric strip uses. A structural
  rendering unit for this (parallel to the existing `STALE_DATA` freshness pill) would
  close that gap; not built here, since `shell.js` is outside this designer's write path.
- **`APP.data._internal`** gained `sleeveWeights`, `downsideDayCount`, `sortino`,
  `downsideDeviationAnnualized`, `windowStart`, `windowEnd`, `windowObservationCount` —
  debug-only, used by `js/selfcheck.js`'s assertions; not part of the guaranteed contract
  in §3 above, same status as the fields already there.

### `js/selfcheck.js` (new file)

Implements PD-0014 §2.2's claim-traceability invariant: `window.APP.selfcheck.run()`
recomputes each hardcoded conclusion/caveat/insight string in `js/data.js` against the
structured values it describes and returns `[{ id, description, pass, detail }, …]`. Runs
automatically once at page load (deferred to the `load` event, falling back to an
immediate run if the document is already complete). Reads **only** `window.APP.data` —
never `APP.ui`/`APP.charts` — and creates its own namespace defensively
(`APP.selfcheck = APP.selfcheck || {}`) rather than assuming any other namespace is ready,
per the coordinator's explicit instruction while a sibling fix to a `shell.js`/`APP.ui`
initialization bug was concurrently in flight. Every assertion runs inside its own
try/catch; a thrown error is recorded as a failed assertion, never an uncaught exception.

**`index.html` has no `<script>` tag for `js/selfcheck.js`, and `index.html` is outside
this designer's write path.** `js/data.js` loads it via a dynamic `document.createElement
("script")` injection at the very end of its own IIFE (§15 in that file) rather than
requiring an `index.html` edit. This works — `data.js` is already in the fixed load order
— but a static `<script src="js/selfcheck.js"></script>` tag placed after `js/data.js`'s
own tag in `index.html` would be the cleaner, conventional mechanism. **Recommended
follow-up, not a defect:** whoever owns `index.html` next should add that tag and this
designer's dynamic-injection block in `data.js` §15 can then be deleted.

### Boundaries respected in this pass

No new sufficiency state or reason code was added (PD-0006/PD-0007 stay closed). No
CAPM/Jensen-alpha methodology, FX attribution mathematics, VaR convention, Sortino
methodology, or statistical-sufficiency threshold was invented independently of
`HG1_ROUND4_METHODOLOGY_FINDINGS.md` — where that document did not cover something (e.g.
an absolute correlation strong/weak classification rule, a scenario-impact model, the FX
fixing-time choice, per-position cost-basis FX timing), it is reported in this worker's
handoff and left, not resolved here. The ex-post SML's downward slope was **not**
"corrected" toward a conventional upward one — it is a faithful description of a negative
realized market premium in this window and is recorded as such in `methodology.sml`'s
`knownLimitations`.

### Revision — `js/selfcheck.js`'s binding assertions had to be rebuilt after a real
### false-pass was demonstrated live

pm-01 reintroduced the ORIGINAL beta-direction defect into the live claim object and
`selfcheck.run()` still reported `pass: true`. Root cause: the assertion tested
`conclusionQuick + " " + explanationSimple` concatenated into one string;
`explanationSimple` is generated dynamically from `BETA` and is therefore always
correct, so when only `conclusionQuick` was mutated to the false text, the untouched,
correct field's wording masked the defect. The same shape of bug was present in the
beta-observation-count assertion (the defect text doesn't contain the word "daily" at
all, so the check silently matched the correct count in the untouched `investorDetail`
field) and in the SML alpha/distance check, and one assertion
(`fxAttribution.portfolioIdentityExact`) was outright tautological (`x = (a−b)+b` can
never fail). **Every assertion in `js/selfcheck.js` now tests each field independently
— never concatenates two fields that could each be correct in isolation — and the file
adds `window.APP.selfcheck.selfTest()`,** which mechanically reintroduces each
assertion's own named defect, confirms the assertion fails, and restores the original
value, so a green `selfTest()` is evidence the controls have teeth rather than an
assurance taken on the author's word. See `js/selfcheck.js`'s own module doc for the
full account; this is recorded here because it changes what "verified" means for this
file — treat only a `selfTest()` result, not a `run()` result alone, as confirmation
that an assertion is a working control.

### Scenario-modification/comparison reconciliation (found by the visual-track designer,
### narrowed live by pm-01)

`SCENARIOS[0]` (`scenario.reduceCnExposure`) declared `amount: "-50%"` against a
`target` string that mixed two exposure dimensions
(`"economicGeography:China (CN-listed only)"`), and its computed allocation used a flat
`0.85` multiplier that reconciled with **neither** a 50%-of-China-economic-geography
reading nor a 50%-of-CN-listed-sleeve reading — the dollar amount implied by the
computation matched no coherent base at all. Fixed: the removed dollar amount is now
derived from one, plainly-named dimension (the CN-listed "A-share" sleeve — matching
this scenario's own `name`/`description`), applied exactly to the `economicGeography`
total that sleeve feeds, with the relationship between the two dimensions stated
explicitly in `description` rather than left for a reader to reverse-engineer (`target`
now reads `"listingMarket:CN (Mainland China A-share sleeve)"` — one dimension, named
plainly, per the coordinator's instruction). The same sweep found `scenario.shiftHkToUs`
used a rounded `1.06` US-side multiplier where the exact reconciling figure is `1.0648`
(a ~$554 discrepancy); both sides now derive from the same computed `HK_SHIFT_REMOVAL`
dollar amount. `scenario.addTreasuryCash` already reconciled exactly and needed no
change. **`js/selfcheck.js` gained three new assertions** —
`scenario.reduceCnExposure.reconciles`, `scenario.addTreasuryCash.reconciles`,
`scenario.shiftHkToUs.reconciles` — each independently recomputing the dollar amount a
scenario's `modifications` entry claims and checking it against the actual
`comparison.allocation` delta, extending PD-0014 §2.2's claim-traceability invariant
from claims-about-metrics to claims-about-scenarios (P8-adjacent: a scenario whose
stated action does not match its own output undermines the actual-vs-hypothetical
separation). **Not touched, and flagged again so it is not mistaken for resolved:** the
`concentration`/`volatility`/`beta`/`sharpe` figures in all three scenarios remain
hardcoded scaling factors with no stated impact model (methodology findings §11) — a
separate, already-flagged methodology gap reserved to `quant_analyst`, not something a
reconciliation pass over the allocation numbers can or should invent a fix for.

### Independent `quant_analyst` verification (HG1_ROUND4_VERIFICATION.md) — six blockers,
### all addressed in this file's write path

`quant_analyst` independently re-derived the corrected chain (every value matched live,
~25-quantity cross-check) and found the corrections "a faithful and in places
better-than-specified implementation," with six items requiring further fixes. Five are
in `js/data.js`; one (`analytics.js`'s SML chart still wiring the regression alpha into
the vertical-distance annotation, `getSMLPoints().verticalDistance` unread) is **outside
this designer's write path** and is not fixed here — flagged again for whoever owns
`js/surfaces/analytics.js`/`js/charts.js`, since the quant verification found the error
it produces is now **3.6× larger** than before this round's correction (beta moved from
0.931 to 0.994, widening the arithmetic/geometric gap).

**Fixed in this file:**

1. **Beta directional claim — statistically unsupportable.** At beta=0.994 (se=0.042,
   a 0.143-standard-error difference from 1.0), asserting a direction was a
   false-precision claim the sample cannot support — and it was now MORE confidently
   wrong than the original hardcoded defect, because it was *derived*. `BETA_SE` (exact
   formula specified and verified by `quant_analyst`), `BETA_CI95`, and
   `BETA_WITHIN_ONE_SE_OF_ONE` are now computed; `betaDirectionConclusion` requires
   >1 standard error of separation before asserting a direction at all, using the
   quant's own required rendering verbatim below the threshold. `se(β̂)` is exposed on
   `metric.beta`'s Evidence object (`getEvidence("metric.beta").standard_error`) so the
   Proof Packet carries the same number the claim was judged against. `js/selfcheck.js`'s
   `binding1` is rebuilt around this tolerance band (a bare `value<1` check would have
   *failed* the correct, hedged sentence) — see that file's own revision-3 note.
2. **Scenario `methodologyId` pointed at the wrong Proof Packet.** Every scenario
   comparison figure produced by a fixed illustrative multiplier (e.g.
   `ANNUAL_VOL * 0.91`) pointed `methodologyId` at the REAL metric's registry entry
   (`methodology.volatility`, etc.) — a wrong audit trail, which P9 makes more dangerous
   than a missing one. `SCENARIO_COMPARISON_META`'s four `methodologyId` fields
   (volatility/beta/concentration/sharpe) now point at a new
   `methodology.scenarioImpactModel` entry that honestly states this is an illustrative
   multiplier with no impact model. The scenario ALLOCATION claims are unaffected
   (those are exact dollar reconciliations against the real ledger, not multipliers, so
   `methodology.exposure` remains correct for them).
3. **`Gain / Loss (1Y, USD)` label misdescribed the number.** Renamed to
   `"Value Change Implied by 1Y Time-Weighted Return (USD)"`; `conclusionQuick`/
   `explanationSimple`/`caveat` rewritten to state plainly that this is not a realized,
   money-weighted gain/loss — the window contains real external contributions
   (computed from the ledger, not hand-typed: `TRAILING_YEAR_CONTRIBUTIONS_USD`) that
   are not netted out. Per the quant's ruling: "a caveat cannot rescue a label that
   misdescribes the number."
4. **As-of date did not bound its inputs.** Three `FRESHNESS_AXES` timestamps (one an
   intraday US quote) were dated after `meta.asOf`/`portfolio_snapshot_id`
   (2026-09-03), which means the snapshot was not reproducible from its own stated
   date (§34/P12). All three now read at-or-before 2026-09-03, per `quant_analyst`'s
   recommended rule ("the as-of date is the latest instant at or before which every
   required input has a print"). **This rule itself is a CP0 question the human owner
   should confirm** — recorded as such in the new `meta.asOfDefinition` field, not
   presented as a settled decision.
5. **Correlation matrix labelling.** `metric.correlation.referencePoint`/`.caveat`
   previously described all five matrix rows as "local-currency sleeve returns," which
   is false for the fifth (the benchmark, a USD series) — a real labelling defect, not
   a numerical one (max basis difference across the whole matrix: 0.0088; equity-pair
   ranking identical either way, per the quant's own check). Fixed the label; the
   underlying DISPLAYED matrix stays on the local-currency basis (migrating it is CP1,
   per the quant's ruling). Added the previously-empty `methodology.correlation`
   registry entry recording this basis inconsistency explicitly, which is "the one
   place §33 requires the basis to be recorded" and whose absence let the ambiguity
   exist in the first place.
6. **`methodology.contributionToRisk` wording error.** "The gap equals the withheld
   segment's own weight-implied share" was wrong — it is the withheld segment's
   RISK-CONTRIBUTION share (7.81%), not its capital weight (10.35%); conflating them is
   exactly the distinction §18.3 exists to draw. One-line fix; the claim's own caveat
   was already correct.

**Also implemented — the correlation classification rule this designer correctly
declined to invent, now specified by `quant_analyst`** (`HG1_ROUND4_VERIFICATION.md`
§5.2): five bands (≥0.80 "move almost identically"; 0.60–0.80 "strongly co-moving";
0.35–0.60 "moderately co-moving"; 0.15–0.35 "weakly co-moving"; <0.15 "largely
independent"), each derived from realized diversification benefit for an equal-weight
pair, plus a precision guard (a label may be asserted only if the nearest boundary is
≥1 standard error away, `se(ρ) ≈ (1-ρ²)/√(n-1)`). Implemented as `correlationBand()`/
`correlationBandAssertable()` in `js/data.js`, evaluated on a NEW, non-displayed
`CORR_MATRIX_BASE` (reporting-currency basis, per the quant's instruction that
"classification applies to the base matrix") — the DISPLAYED matrix stays local-
currency (item 5 above; full migration is CP1). `correlationConclusion` now appends the
band label for the HK/CN pair only when the precision guard holds (it does, barely:
~1 standard error, "the test of whether a threshold is real" per the quant). A new
`js/selfcheck.js` assertion, `correlation.bandClassificationPrecision`, enforces this as
a strict addition alongside (not a replacement for) `binding3`'s existing rank-based
check, per the quant's explicit instruction to keep that check unchanged.

**Recorded, not fixed here (per the quant's own CP1/blocker triage):** the risk-
contribution "safe only because it names the top two as a set" property (US 46.36% vs.
HK 45.10%, a 1.26pp gap that would not support naming a single leader) is preserved by
`contributionRiskConclusion`'s existing logic and now has an explicit code comment
warning against ever reducing it to one name.

### `js/selfcheck.js`'s scope limitation, recorded per the quant's explicit instruction

`js/selfcheck.js` reads only `window.APP.data` and never the DOM or any surface module.
**Every defect that lives in a chart, a title, or a window label is therefore invisible
to it** — concretely, item 1 of the quant's still-open blocker list above (the SML
chart's alpha annotation) is fully outside what this file can detect, because
`getSMLPoints().verticalDistance` is correct in `data.js` and simply unread by the
chart. A full `run()`/`selfTest()` pass is evidence the prose this file can read is
internally consistent — **it is not evidence the screen is correct, and must never be
presented at HG1 as if it covered the screen.** This limitation is now stated in
`js/selfcheck.js`'s own file header as well, so it travels with the file rather than
only with this addendum.

### Bilingual gap — `claim.i18n.zh`, populated for Overview and Analytics only

The visual-track designer wired `APP.ui.localizeClaimField(claim, field)` across every
claim-narrative read site (`shell.js`, `analytics.js`, `overview.js`, `ai.js`), reading
`claim.i18n[lang][field]` and falling back to English per-field when absent. This
addendum records what `js/data.js` now populates against that interface.

**Covered: every claim in the `METRICS` object (24 entries) — both `metric.*` and
`exposure.*` — which is the complete claim surface Overview and Analytics actually
render.** Each has `i18n.zh` populated for whichever of `conclusionQuick`,
`explanationSimple`, `caveat`, `investorDetail`, `professionalDetail`, and
`referencePoint` exist on it in English.

**Not covered, and left in English on purpose (deferred, per the owner's "leave
Portfolio, Ingest and Scenario for later" instruction):** `HOLDING_CLAIMS`,
`INSTRUMENT_RISK_CLAIMS`, and `TRANSACTION_FX_CLAIMS` (all Portfolio-surface claims),
and `SCENARIO_CLAIMS` (Scenario Lab). None of these carry an `i18n` field yet — they
fall back to English exactly as the localization hook is designed to do, so nothing
breaks, but a Portfolio or Scenario Lab screen viewed in Chinese will show English
analysis prose until a later pass covers them. **Also not covered:** the plain-string
`INSIGHTS` array (`insight.*` claims) — these are a different, non-`claim` structure
(a bare `.claim` string field, not an object with an `i18n` slot) and were outside the
localization hook's wired call sites as described to this designer; flagged rather than
silently left ambiguous.

**Derived claims are derived in both languages, from the same values — not
hand-translated from a snapshot.** `betaDirectionConclusion`, `volatilityConclusion`,
`drawdownConclusion`, `correlationConclusion`, and `contributionRiskConclusion` all take
a trailing `lang` parameter; the CONDITION that selects which sentence fires (e.g.
`Math.abs(beta - 1) <= se`, or which sleeve ranks first) is identical in both branches,
only the output template differs by language. `BENCHMARK_RELATIVE_COMPARABILITY_NOTE_ZH`
is likewise built from the same `CN_FRESHNESS_AXIS.asOf`/`END_DATE` values as its English
counterpart, not translated from it. This means a future change to any underlying number
updates both languages identically and neither can silently drift from the other — the
exact property this whole round-4 cycle exists to protect, now extended to Chinese.

**Canonical identifiers are never translated (PD-0012 §3).** Tickers (`0700.HK`,
`600519.SS`, `TLT`), currency codes (`USD`, `HKD`, `CNY`), the index name (`MSCI ACWI`),
and every metric id are reproduced verbatim inside the Chinese strings. What IS
translated: prose, and the plain-English sleeve/asset-class NAMES used in narrative
("US"/"HK"/"CN"/"Bonds"/"Hong Kong"/"Mainland China" → 美股/港股/A股/债券, via a small
`sleeveNameZh()` map) — the same category as translating a security's name (Tencent
Holdings / 腾讯控股) while its ticker never changes. Professional terminology stays
professional in both languages (贝塔/β, 夏普比率, 风险价值, etc.) — the interface
language, the financial terminology, and the security identifiers are kept as three
separate layers throughout, per the coordinator's explicit instruction.

**`js/selfcheck.js`'s `binding1` (beta direction) now also checks `claim.i18n.zh`**
when present, using a bilingual classifier (the same tested logic, with Chinese phrase
alternatives added) — a Chinese sentence contradicting its own number is the same
defect in a different language, and would otherwise be invisible to a file that only
ever read English fields. **Honestly scoped, not claimed as complete:** `binding2`
(risk-contribution ranking), `binding3`/`correlation.bandClassificationPrecision`, and
`binding4` (observation count) were NOT extended to check Chinese in this pass — a
partial claim honestly scoped is fine, a partial one presented as complete is not.
Also honestly scoped: `binding1`'s Chinese check has not been separately negative-tested
(the existing injector mutates only the English field) — it reuses already-tested
machinery, but a dedicated Chinese-language injection has not been run.

**Layout:** translations were written to stay reasonably tight rather than expansive,
per the coordinator's warning that this round's tables/charts were sized against
English worst cases (including some strings this round's own corrections made longer)
and that Chinese financial terms are often shorter while some regulatory phrasing runs
longer — the layout re-verification itself belongs to the visual-track designer /
`pm-01`, not to this designer.

### Sign convention for static levels (owner's §6.3) — a parallel-truth in the
### formatting layer

pm-01 found `data.js`'s own `APP_fmtPct` unconditionally prefixing "+" on any
non-negative value, including STATIC LEVELS where §6.3 forbids a sign (a top-5
concentration share rendered as "+75.1%"). This is exactly PD-0014 §2.5's "parallel
truths" defect class, one layer down: the visual-track designer had fixed `shell.js`'s
`formatPercent`/`formatNumber` and reported §6.3 closed, but `data.js` carries its own
independent formatter that was never touched, so the defect read as fixed on some
surfaces and not others.

**Fix:** the formatter family now has three members, not two — `APP_fmtPct` (signed;
gains/losses, returns, alpha, distances/deltas, weight changes, signed contributions,
scenario deltas), `APP_fmtMagnitudePct` (unsigned magnitude, already existed for VaR),
and new `APP_fmtLevelPct` (unsigned level: volatility, a risk-free-rate assumption, a
concentration share). All 28 call sites (not 20 — the actual count once English/
Chinese pairs and multi-call lines are counted individually) were audited and
reclassified; **four were wrong and are now fixed**: `metric.volatility.referencePoint`
(en+zh), `metric.sml.professionalDetail`'s risk-free-rate mention (en+zh — note the
literal formula text `"Rf + β×(...)"` in the same string is NOT a sign defect and was
left untouched), `insight.concentration.top5`, and `insight.fx.drag` (switched from
`APP_fmtPct(Math.abs(...))` to `APP_fmtMagnitudePct(...)` directly, since the number
there is a magnitude following "reduced/added to... by roughly," not a signed change —
the same shape of error VaR's original convention fix already closed once). All other
24 call sites were confirmed already correct (drawdown figures signed as declines;
returns, alpha, FX legs, and the SML line-distance signed as changes; VaR and
contribution-share magnitudes already using `APP_fmtMagnitudePct`).

**Also fixed, same function family:** `APP_fmtPct` and `APP_fmtMagnitudePct` both
returned a bare `"—"` for `null`/`undefined` — §D3.2's forbidden em-dash-as-numeric-
placeholder pattern, a **third** recurrence of a mistake this project has already made
twice. None of these three formatters is the claim-value renderer (that is `shell.js`'s
`renderMetricValue`, which correctly implements `INSUFFICIENT_DATA`); they build
hand-authored prose inside `data.js`, so a null reaching one of them means a caller
embedded an unchecked value directly into prose without a sufficiency gate. All three
now **throw** on null/undefined instead of silently degrading — verified safe today
(every one of the 28 call sites always passes a real number by inspection) and a real
guard against the next accidental instance, per the instruction to fail loudly rather
than emit a placeholder glyph.

**`js/selfcheck.js` gained `levelFormatting.noSuperfluousSign`**, checking the three
concrete sites this defect was found at (`metric.volatility.referencePoint`,
`metric.sml.professionalDetail`, `insight.concentration.top5`), each anchored to its
own preceding phrase (e.g. `"volatility:\s*\+"`, `"Rf = \+"`) so the legitimate `"+"` in
`metric.sml.professionalDetail`'s own formula text is never mistaken for the defect.
Its injector reproduces the exact live string pm-01 found ("represent +75.1%").

### Final `quant_analyst` re-verification — four fixes (three of them the quant's own errors)

`quant_analyst` re-verified this pass live and confirmed eight of nine changes faithful
(including the beta band, the scenario-methodology repointing, the as-of bounding, the
correlation labelling, and the sign-convention split), and confirmed the Chinese beta
hedge is statistically equivalent to the English. `pm-01` separately clicked through
210 buttons across all five routes and confirmed **zero exceptions** — the throw-on-null
guard added earlier this pass is confirmed safe; nothing live reaches it. Four blockers
remained, addressed here:

1. **Correlation band precision guard tightened from 1 se to 1.96 se.**
   `quant_analyst`'s own original §5.2 rule quoted `se(HK/CN)=0.048` — actually the
   US/HK row's standard error; the correct figure (~0.060) let the 1-se guard's
   verdict flip depending on whether the local (0.869 se, rank-only) or base (1.018 se,
   assertable) basis was used to evaluate the identical HK/CN pair. At 1.96 se (95%
   confidence) HK/CN no longer clears on either basis — only US/HK does (~2.45 se) —
   so the basis-sensitivity is gone rather than merely narrowed, and the rule still
   does real work (5 of 6 pairs correctly rank-only). This also closes, as a direct
   consequence, a second defect: the band sentence previously quoted ρ=0.21 (base
   basis) immediately beside the displayed matrix's own ρ=0.20 (local basis) for the
   same cell — two numbers for one number. Since the band clause no longer fires for
   HK/CN under the tightened guard, that mismatch cannot recur for this pair.
   `correlationBandAssertable` in `js/data.js` and `js/selfcheck.js`'s
   `correlation.bandClassificationPrecision` (description, detail messages, injector
   comment) all updated to 1.96 se; the CHECK LOGIC itself needed no change since it
   already reads the (now-tightened) `assertable` boolean `data.js` computes.
2. **"Margin of error" understated imprecision by half — fixed in both languages.**
   The within-band beta sentence said "the estimate's margin of error (±0.04) spans
   1.0"; a lay reader takes "margin of error" to mean the 95% interval (±0.082), not
   one standard error, so the sentence whose entire job is conveying imprecision
   understated it by half. `betaDirectionConclusion` now takes `ci95` as an explicit
   parameter (threaded from the same `BETA_CI95` already exposed on the Evidence
   object, never recomputed) and states both numbers: "standard error ±0.04, and the
   95% CI [0.91, 1.08] spans 1.0" — in English and in the parallel Chinese branch,
   since the Chinese inherited the identical flaw from the same spec, not from
   translation. The same ambiguous phrase also appeared in the beyond-band
   `explanationSimple` branch (not explicitly named by the coordinator, but the same
   defect class); replaced "the estimate's own margin of error" / 误差范围 with the
   unambiguous "one standard error of the estimate" / 一个标准误 there too.
3. **One real translation defect (P6).** `metric.sml`'s Chinese `explanationSimple`
   read 本应取得多少收益 ("how much return it **ought to have** obtained") — 本应 carries
   counterfactual obligation on its own, the same modal the quant vetoed in the
   English at §2.3, and P6 has no lesser-instance tier for a softening clause
   elsewhere in the sentence. Changed to 需要取得 ("would need to obtain"), matching the
   English's "would have needed... to match" without the obligation modal.
4. **Risk-contribution shares must preserve sign.** `MCTR_i = w_i·σ_i·ρ_{i,P}` is
   genuinely negative when a sleeve is negatively correlated with the portfolio (a
   hedge — the one case where the sign carries all the meaning), but
   `contributionRiskConclusion`'s per-segment formatting and
   `metric.contributionToRisk.caveat`'s available-segments-sum (4 call sites, en+zh
   pairs) used `APP_fmtMagnitudePct`, which applies `Math.abs()` and would silently
   turn a −8% hedging contribution into "8%". All four values are positive in this
   dataset today, so nothing was wrong on screen, but by the formatter split's own
   logic a share is a LEVEL — switched all four to `APP_fmtLevelPct`, which preserves
   whatever sign the value actually has while still suppressing the superfluous "+"
   on an ordinary positive contribution.

**Recorded, not fixed — a product consequence, not a defect:** the as-of-bounding fix
(prior round) moved `us_equity`'s freshness axis from `LIVE` to `END_OF_DAY`, which is
*entailed* by the as-of rule (a snapshot as of a past close cannot contain a live
input) — the prototype no longer exercises the `LIVE` state anywhere. `quant_analyst`
is recording this for the human owner as a product question (whether V1 needs an
"as of now" mode at all), not asking for it to be undone, and neither designer is
resolving it.

### Fifth item — harmonizing the beta and correlation directional-claim thresholds

`quant_analyst` signed off on all four fixes above (verified against source), and
separately flagged a fifth item as its own error without calling it a blocker;
`pm-01` asked for it to be carried anyway. Tightening the correlation classification-
band guard to 1.96 se (see the fourth-item entry above) left `metric.beta`'s own
directional-claim guard at a bare 1 se — two different thresholds for the identical
class of judgment ("may a directional/classification claim be asserted about which
side of a boundary an estimate falls on"), with nothing recording why they differed.
A directional claim gated at only 1 se carries roughly a 1-in-6 chance of pointing the
wrong way. **Both now read one constant, `DIRECTIONAL_CLAIM_SE_MULTIPLIER = 1.96`**,
defined once in `js/data.js` alongside `BETA_SE`/`BETA_CI95` and referenced by both
`betaDirectionConclusion` (renamed `BETA_WITHIN_ONE_SE_OF_ONE` → `BETA_WITHIN_TOLERANCE_
BAND`, since the name could no longer say "one") and `correlationBandAssertable` — no
locally re-typed "1.96" in the correlation function anymore, one source for both
judgments. Exposed on `_internal.directionalClaimSeMultiplier` so `js/selfcheck.js`'s
`binding1` reads the identical constant rather than a separately hardcoded number that
could silently drift from it.

**Why this was carried rather than accepted as dormant/cosmetic:** it changes nothing
on screen today (beta sits at 0.143 se, well within the tolerance band under either
threshold), but the currently-unreachable "beyond the band" branches said "by more
than one standard error" / 差异超过一个标准误 in both languages — both updated to name
1.96 standard errors (95% confidence) explicitly, in English and Chinese, in both the
`conclusionQuick`-generating function and the separately-written `explanationSimple`
branches. `quant_analyst` specifically praised this update to a path nobody can
currently see ("the right kind of care for a path nobody currently sees") — the same
shape as two defects already fixed earlier this pass while dormant: the em-dash null
path nothing reached, and the `Math.abs()` on risk-contribution shares where every
value happened to be positive. Being unreachable today was never a property to rely on.

**`binding1`'s injector verified to still have teeth after the threshold change:** at
1.96 se the tolerance band widens (0.042 → 0.082), so beta (|diff|=0.006) sits even
more comfortably within it than before — the injector's premise (asserting a
directional claim when the correct answer is "broadly in line") remains valid and the
assertion still fails exactly as designed when the defect is reintroduced.

### Sixth item — `getFreshness().leastFreshAxis` was a claim, and no assertion covered it

The visual designer found, and `pm-01` confirmed live, that `leastFreshAxis` returned
`us_equity` — the axis with the **most recent** print — while two FX axes sat in a
strictly worse (`DELAYED`) state. Root cause was in `shell.js`'s severity table
(`FRESHNESS_SEVERITY` ranked `END_OF_DAY` worse than `DELAYED`, backwards: a
completed, authoritative end-of-day close is not worse than an incomplete, lagging
mid-session feed), which then broke the resulting three-way `END_OF_DAY` tie by array
position rather than by any freshness-relevant criterion. **Fixed in `shell.js`**
(outside this designer's write path); `js/selfcheck.js` gains the control that would
have caught it: `freshness.leastFreshAxisCorrect`, checking two properties against the
full axis set rather than re-implementing `rankLeastFresh` — (1) no axis present has
strictly worse severity than the named one, and (2) among axes tied on severity, none
has a larger `delayMinutes` than the named one. The severity order used to evaluate
this (`STALE` > `DELAYED` > `END_OF_DAY` > `LIVE`) is reasoned independently from what
each state means, not copied from `shell.js`'s table — the point of the property-based
approach is that two implementations of the same (possibly wrong) ranking would agree
with each other and prove nothing. The injector reproduces the actual shipped
regression (forcing `leastFreshAxis` to an `END_OF_DAY` axis while `DELAYED` axes
remain present) rather than a hypothetical defect.

**The generalization, worth recording because it will recur:** chrome is not exempt
from the claim-traceability invariant (PD-0014 §2.2). A freshness strip, a "least
fresh: X" summary, an "N items need attention" count, or any other derived label is a
material claim about the data the moment it asserts something checkable — no
different in kind from a metric's `conclusionQuick`, even though it renders as status
chrome rather than a claim card. Three of the four original round-4 defects were
metric conclusions, so every assertion built since then was built around a metric
claim's own fields (`conclusionQuick`, `caveat`, etc.); `leastFreshAxis` was none of
those, lives on a different accessor (`getFreshness()`, not `getMetric()`), and slipped
straight through the net as a result. `pm-01`'s own words: "everyone treated the
freshness strip as chrome rather than as an assertion... my verification checked that
freshness *rendered*, never that its summary was *true*." The next derived, non-metric
label on this surface (a count, a ranking, a "worst of" selection) should be checked
against this same standard before being assumed safe by visual inspection alone.

**Also recorded here, from the visual track, because the reasoning currently lives only
in a `shell.js` comment** (outside the contract where the next person will look): *the
worst case for a state/status column is the degraded state, in the widest-rendering
language present, not the healthy state in whichever language was checked first.*
Adding a second language re-opens every fixed-width layout decision already closed
against the first — a column's true worst case is the union of (every state a column
can show) × (every language it renders in), and this column specifically (Holdings'
Freshness column, per the round-3 visual-polish pass's own worst-case-sizing lesson)
has now been the binding layout constraint three separate times for exactly this
reason.

### Seventh item — the SSE holiday assumption was false; the calendar is now data, not prose

The human product owner challenged, and correctly falsified, the assumption behind
the session-aware freshness fix from earlier this round: `FRESHNESS_AXES`'s `cn_equity`
axis and `data.js`'s own comments asserted "Shanghai/Shenzhen closed for a local
holiday on 2026-09-03." **That is false.** 2026-09-03 is a Thursday (deterministically
verified, not a weekend) and is not a standing PRC public holiday — September 3
(Victory Day, a commemorative date) was made a one-off public holiday only in 2015
(70th anniversary) and 2025 (80th anniversary) by specific State Council announcement
each time; 2026 is the 81st anniversary, outside that pattern. No other PRC holiday
falls near the date. **SSE/SZSE traded normally on 2026-09-03.**

**Stated explicitly, per the owner's instruction:** this harness has no network
egress. The weekday determination is deterministic (day-of-week arithmetic on a plain
calendar date) and reliable. The holiday list is reasoned from established PRC
public-holiday practice, **not from a fetched, authoritative SSE/SZSE trading
calendar** — that confirmation remains an outstanding human/network step this fixture
cannot close on its own. This is recorded in `js/data.js`'s own comments at the
calendar definition, not only here.

**The fix is to the reference data, not the session-aware principle** — the owner was
explicit about this, and it is why the architecture from earlier this round is
preserved intact, not reverted. The root cause was a calendar fact asserted in prose
(a comment, a freshness-axis `note`, an insight string) instead of being modelled as
data the code derives a classification from — three independent places that could
(and did) drift from the truth. **`js/data.js` now carries an explicit SSE
trading-session calendar as data:** `SSE_HOLIDAYS_2026` (an array of specific holiday
dates with names), `sseSessionInfo(date)` (classifies one date as TRADING_DAY/WEEKEND/
HOLIDAY), and `sseSessionsElapsed(fromDate, toDate)` (counts completed sessions
between two dates, correctly excluding weekends/holidays from the count rather than
counting calendar days). The classification is computed from this in exactly one
place and read everywhere else, rather than restated.

**What changed as a direct, worked-through consequence (nothing preserved for visual
continuity):**

- `cn_equity`'s freshness state: `END_OF_DAY` → **`STALE`** (`sseSessionsElapsed
  ("2026-09-02", "2026-09-03")` computes to 1 — one completed trading session with no
  update — not 0).
- `getFreshness().leastFreshAxis` now resolves to `cn_equity` (severity `STALE` >
  `DELAYED`, under the severity order `shell.js` already corrected two items ago) —
  outranking both FX `DELAYED` axes, which it did not before. No `shell.js` change was
  needed for this: the ranking function was already correct, it simply was never
  handed a genuinely `STALE` axis under the false calendar assumption.
- `metric.benchmarkRelative`: `sufficiency`/`reasonCode` are now **derived** from
  `sseSufficiencyForSessions(CN_SESSIONS_ELAPSED)`, not hardcoded either way. At 1
  session elapsed this lands on `AVAILABLE` + `STALE_DATA` — the SAME combination the
  claim carried before the (wrong) session-current conclusion removed it, but arrived
  at by re-derivation from the corrected calendar, not by reverting because "it used to
  be there." This is precisely PD-0006's "routine, expected staleness" case the
  `STALE_DATA`+`AVAILABLE` combination was built for. The temporal-comparability
  disclosure (a separate PD-0014 Part 1 dimension) is unchanged — the two legs were
  never measured at the same instant either way; only the REASON for the gap changed,
  from an (incorrect) market-holiday explanation to genuine staleness.
- `insight.freshness.cnStale`: rewritten to state what is actually true (genuine
  staleness, the session count, the real print/as-of dates), severity raised from
  `OBSERVATION` to `ATTENTION` to match how this file treats other genuine data-quality
  conditions.
- The file's own top-of-file summary comment, corrected to match.

**Not changed, and deliberately so:** the 252-day return-generation series (`DATES`,
the sleeve return arrays) still excludes only weekends, not PRC holidays — a
pre-existing, separate simplification of the synthetic historical series, not part of
what the owner asked to be fixed here (which was the CURRENT freshness/staleness
classification, a snapshot concept, not the historical return model).

**`js/selfcheck.js` — the old `freshness.cnSessionAware` assertion is REMOVED**, not
left inert: its premise ("must reflect zero elapsed sessions... a market holiday") is
now known false, and a control asserting a falsified premise is worse than no control,
the same standard applied throughout this file. **Five new assertions
(`sseCalendar.normalWeekday`, `.weekend`, `.officialHoliday`,
`.normallyCompletedSession`, `.previousSessionCarriedIntoNewTradingDay`)** replace and
extend it — the exact five cases the owner specified, each calling `data.js`'s own
calendar functions (exposed on `_internal`) against independently verifiable reference
facts (day-of-week arithmetic, explicit holiday-list membership) rather than
re-implementing the calendar to check it, each with a working injector (one reproduces
the actual shipped defect: the axis claiming `END_OF_DAY` while the — unmutated,
correctly-computed — calendar says one session has elapsed). `freshness.
leastFreshAxisCorrect` (added two items ago) needed no code change — it is fully
property-based and validates correctly against whichever axis is genuinely worst,
which is now `cn_equity` as a natural consequence of the calendar fix, not because the
assertion itself was touched.

**Generalization worth keeping:** this is the same claim-traceability failure named in
the immediately preceding item (chrome is not exempt), one layer deeper — the false
claim here did not originate in a rendered sentence but in a **reference fact**
(a calendar) three separate sentences each independently trusted. A fact asserted in
prose in more than one place is a parallel-truths risk even when every copy currently
agrees; modelling it as data with one derivation point, as done here, is the structural
fix, not a one-time correction of the specific date.

### Eighth item — the sector-classification language invariant (PD-0015 §2.3), handed
### over from the visual-designer track

The visual designer built `APP.ui.classifySectorExposure(holdings, totalValue)` and
`APP.ui.verifySectorClassificationLanguageInvariant(holdings, totalValue)` in
`js/shell.js` (out of this designer's write path) and explicitly asked this file to
own the *asserted* version, since `js/selfcheck.js` is the only thing that runs
automatically. **The rule this generalizes, worth recording on its own: a grouping
key must never be a localized string.** `classifySectorExposure()` groups holdings by
sector; if that grouping ever keyed off the CURRENT-LANGUAGE DISPLAY label instead of
a canonical key, switching language would silently change which holdings bucket
together, and every screen would still look internally consistent in whichever
language it happened to render — invisible from either language alone. This is the
same claim-traceability failure named twice already this round (chrome is not exempt;
a reference fact must be modelled as data, not restated), applied to a THIRD kind of
artifact: not a rendered sentence, not a calendar fact, but a **grouping/bucketing
key** — and it generalizes past sectors to any future taxonomy this product localizes.

**New assertion: `sectorClassification.languageInvariant`.** Calls the visual
designer's utility and compares canonical `(key, value, pct)` fingerprints — never
display labels, which are expected to differ — failing (not silently passing) if
`APP.ui` or the utility itself is unavailable when this file runs, since `APP.ui` may
not exist yet depending on load order. **The injector reproduces the exact regression
PD-0015 §2.3 warns about** — a classifier keyed off the display label rather than the
canonical key — via a temporary RUNTIME monkey-patch of the live
`APP.ui.classifySectorExposure` function (an object-property reassignment for the
duration of one test, restored immediately after; the same technique already used
throughout this file for `APP.data`'s own accessors, not a file edit to `shell.js`).

**The stated limitation, encoded in the assertion's own description, not only here:**
`verifySectorClassificationLanguageInvariant` switches language twice and restores the
original, but its own restore is not wrapped in a `try`/`finally` in `shell.js` — if
`classifySectorExposure` ever throws mid-comparison, the app can be stranded in the
wrong language. This designer cannot fix that inside `shell.js`, so the assertion
instead wraps its OWN call: on a throw, it attempts a best-effort recovery via the
PUBLIC, non-quiet `APP.i18n.setLang(originalLang)` — which does trigger one visible
re-render, unlike the quiet restore the utility itself was supposed to guarantee, but
is the only recovery path available from outside `shell.js` (`APP.ui.setLangQuiet` is
not exported publicly). A throw during the check is still always reported as a FAILED
assertion, never converted to a pass.

---

## 0. What you own vs. what this file owns

You own exactly: `js/surfaces/overview.js` (designer-10); `js/surfaces/portfolio.js`,
`js/surfaces/ingest.js` (designer-11); `js/surfaces/analytics.js` (designer-12);
`js/surfaces/scenario.js`, `js/ai.js`, `js/evidence.js` (designer-13). Nothing else.

This file, `index.html`, `styles/tokens.css`, `styles/app.css`, `js/shell.js`, and
`js/data.js`/`js/charts.js` are **closed** to you in this phase — `designer-14` owns
final integration across all of it, after phase 2 finishes. If something in this
contract is actually wrong (not just inconvenient), **do not patch around it in your own
file** — a workaround in your surface that compensates for a shell bug will look like a
second, incompatible contract to the next reader. Say so in your own handoff instead.

---

## 1. Load order (already wired in `index.html`, do not reorder)

```
1. js/shell.js     — defines window.APP, the registration API, the router, all shared
                      UI primitives. Nothing else may load before this.
2. js/data.js       — attaches window.APP.data.
3. js/charts.js     — attaches window.APP.charts.
4. js/surfaces/*    — each calls APP.registerSurface(key, config) at load time
                      (synchronously, not inside a DOMContentLoaded handler — see §2).
5. js/ai.js         — calls APP.registerAI(handler).
6. js/evidence.js   — calls APP.registerEvidence(handler).
```

Plain `<script src="...">` tags, no bundler, no ES modules, no `import`/`export`. Attach
everything to the global `window.APP` namespace. `index.html` already contains a
`<script>` tag for every file above, including yours — if your file does not exist yet,
that tag 404s harmlessly and the shell renders a "not yet built" panel for your surface.
You do not need to (and must not) edit `index.html` to "add" your script tag; it is
already there.

**Register at the top level of your file, not inside a `DOMContentLoaded` listener.**
`APP.registerSurface`/`registerAI`/`registerEvidence` are safe to call synchronously
during script evaluation — they take effect immediately, and if the app has already
booted (e.g. hot-reload during your own testing) a late registration still re-renders
the current route automatically.

**Namespace-initialization rule — the actual guarantee, not just the intent.**
Every file that does *incremental* property assignment onto its own namespace
(`APP.ui.foo = ...`, `APP.charts.foo = ...`, i.e. more than one separate assignment onto
the same object) **must create that namespace itself**, defensively
(`APP.x = APP.x || {}`), at the top of its own IIFE, regardless of what any other file
does. `shell.js` does this for `APP.ui` (`APP.ui = APP.ui || {}`, immediately before its
first `APP.ui.*` write) and `charts.js` does it for `APP.charts` the same way — **this
was missing from `charts.js` in an earlier revision of this file and threw
`Cannot set properties of undefined` on the very first chart function's assignment,
aborting the whole IIFE and leaving `APP.charts` undefined for every caller.** It is
fixed now; the rule above is why it will not recur silently in a fourth file. A single
*whole-object* assignment (`js/data.js`'s `APP.data = { getHoldings: ..., ... }`, written
once at the end of the file rather than as many separate `APP.data.foo = ...` lines) does
not have this failure mode at all, because it never requires `APP.data` to already exist
— only `APP` itself. Prefer that pattern in your own file if you are assigning many
properties onto a namespace only you create.

**One real, order-dependent coupling exists and is stated here rather than left
implicit behind a guard.** `js/data.js`'s `getFreshness()` calls
`window.APP.ui.rankLeastFresh(...)` — a genuine dependency on `shell.js` having already
run, guarded with a truthiness check and a hardcoded fallback (`"cn_equity"`) purely as a
defensive fallback, **not as evidence load order is safe to violate.** The fixed order
above (`shell.js` before `data.js`) guarantees this guard's fallback branch is never
actually exercised; if you ever need to reorder these two files for any reason, this is
the one place that would silently start returning a wrong answer instead of throwing, and
you should know that before doing it.

---

## 2. Surface registration

```js
window.APP.registerSurface(key, {
  group: "overview" | "portfolio" | "analytics" | "scenario",
  render(mountEl, ctx) { /* ... */ }
});
```

- **`key`** is fixed per assignment — you do not choose it:

  | Your file | `key` | `group` |
  |---|---|---|
  | `js/surfaces/overview.js` | `"overview"` | `"overview"` |
  | `js/surfaces/portfolio.js` | `"portfolio"` | `"portfolio"` |
  | `js/surfaces/ingest.js` | `"ingest"` | `"portfolio"` |
  | `js/surfaces/analytics.js` | `"analytics"` | `"analytics"` |
  | `js/surfaces/scenario.js` | `"scenario"` | `"scenario"` |

- **`render(mountEl, ctx)`** is called every time the router activates your surface
  (on navigation to it, and once at boot if it is the initial route). `mountEl` is an
  empty `<div class="surface-mount">` — clear it yourself if you re-render on an
  internal state change (`mountEl.innerHTML = ""` is fine; nothing else depends on its
  prior contents). **Do not memoize DOM across calls** — treat each call as a fresh
  render into an empty container; the shell does not guarantee it reuses the same
  element instance across navigations away and back.
- **`config.label` is not part of this contract.** Primary and secondary nav labels are
  fixed centrally in `shell.js`'s `GROUPS` map (see §8, "Navigation and IA") so that four
  authors cannot each pick a slightly different label for the same tab. If you believe a
  label is wrong, say so in your handoff; do not set your own.
- A `render` that throws is caught by the shell and shown as a labeled "RENDER ERROR"
  panel instead of a blank screen or a silent console-only failure — you will get useful
  feedback even from a mistake, but you should still not rely on this as your own error
  handling.

### `ctx` — guaranteed shape, every call, no exceptions

```js
{
  group: string,        // the active group key, e.g. "portfolio"
  key: string,           // the active surface key, e.g. "ingest"
  params: object,        // parsed from the hash's query string, e.g. #/portfolio/portfolio?focus=AAPL
                         //   -> { focus: "AAPL" }. Always an object, never undefined.
  navigateTo(hashPath),  // === window.APP.navigateTo. Pass a path like "portfolio/ingest"
                         //   (no leading "#/", it's added for you).
  data: window.APP.data, // convenience alias, identical object every call
  charts: window.APP.charts,
  ui: window.APP.ui
}
```

Nothing on `ctx` is ever `undefined` or `null` at call time (assuming `data.js`/
`charts.js` loaded, which the fixed load order guarantees). You may use `ctx.data`/
`ctx.charts`/`ctx.ui` or the `window.APP.*` globals interchangeably — they are the same
objects.

### Two-surface groups (Portfolio) and the secondary nav strip

`group: "portfolio"` has two registered surfaces (`portfolio`, `ingest`). The shell
renders a secondary tab strip automatically whenever a group has more than one
registered surface — **you do not build this navigation yourself**, and you do not need
a "back to Holdings" link inside `ingest.js` or vice versa; switching surfaces is the
shell's job. Route directly via `ctx.navigateTo("portfolio/ingest")` from anywhere (e.g.
an "Import a statement" button inside `portfolio.js`, or a "View in Holdings" link from
`ingest.js` after a confirm) rather than trying to render the other surface's content
inline.

---

## 3. Data access API (`window.APP.data`, from `js/data.js`)

Data + pure accessors only. Nothing here renders. Every number is derived from a single
seeded random-walk return series (fixed seed — same output every load), so return,
volatility, beta, alpha, Sharpe, Sortino, drawdown, tracking error, VaR, correlation, and
contribution-to-risk are computed from the same underlying arrays and agree with each
other and with what a chart of the same series would show. **Do not recompute or
second-guess these numbers in your own file — read them from the accessors below.**

```
APP.data.meta                              // { asOf, reportingCurrency: "USD", portfolioId }

APP.data.getAccounts()                     // [{ id, name, currency, type, market }, ...]
APP.data.getCashBalances()                 // [{ accountId, currency, amount }, ...]
APP.data.getTotalPortfolioValue()          // number, USD

APP.data.getHoldings()                     // [{ id, name, accountId, listingMarket,
                                            //    economicGeography, currency, sector,
                                            //    assetClass, quantity, avgCost, price,
                                            //    marketValueUSD, pctOfPortfolio,
                                            //    analyticsSupport?, thinlyTraded?,
                                            //    costBasisState?, costBasisReason?,
                                            //    addedDate? }, ...]
APP.data.getHolding(id)                    // one holding or null
APP.data.getHoldingClaim(id)                // claim object: per-position cost-basis /
                                            //   unrealized-gain-loss (D1 Holdings item 3)
APP.data.getInstrumentRiskClaim(id)        // claim object, only for instruments carrying
                                            //   analyticsSupport: "UNSUPPORTED_ASSET"
                                            //   (currently just "2800.HK")

APP.data.getTransactions(filter?)          // filter: { accountId?, type?, from?, to? }
APP.data.getTransactionFxClaim(id)         // claim object for a transaction's reporting-
                                            //   currency FX conversion, only where one
                                            //   exists (currently just "tx-0029")

APP.data.getPortfolioSeries({range?})      // range: "1M"|"3M"|"6M"|"1Y"|"ALL", default "1Y"
                                            //   -> { dates, portfolio, benchmark, window }
                                            //   (cumulative index, base 100)
                                            //   HG1 M1 fix (methodology/HG1_M1_PERIOD_
                                            //   RETURN_BASE_CONVENTION_RULING.md, RULING 2)
                                            //   — arrays are BASE-ANCHORED: sliced from
                                            //   periodWindow(range).baseIndex, one element
                                            //   EARLIER than the window's first return
                                            //   observation, so a[last]/a[0]-1 (charts.js,
                                            //   unchanged) reconciles with the engine's own
                                            //   period-return fact for the SAME window.
                                            //   `window` is new/additive: { range,
                                            //   firstReturnIndex, baseIndex, baseDate,
                                            //   windowStart, windowEnd, observationCount,
                                            //   baseRule: "PRIOR_CLOSE"|"FIRST_AVAILABLE_
                                            //   CLOSE" }. The declared windowStart/windowEnd/
                                            //   observationCount do NOT change — the extra
                                            //   leading point is the anchor, not a new
                                            //   observation (RULING 1(c)).
APP.data.getDrawdownSeries({range?})       // -> { dates, portfolio, benchmark } (fractional, e.g. -0.09)
                                            //   NOT base-anchored (RULING 1(d), scope limit):
                                            //   a drawdown is a level read off the axis, not
                                            //   a ratio between two endpoints, so it carries
                                            //   no base and is unchanged by the M1 fix. Its
                                            //   x-domain therefore starts one trading day
                                            //   LATER than getPortfolioSeries's for the same
                                            //   range selector — that asymmetry is correct
                                            //   and required, not a bug (M1-F7).
APP.data.getRollingVolatilitySeries({range?}) // -> { dates, portfolio, benchmark }
                                            //   (annualized, 90-day trailing; first 89
                                            //   entries in the FULL series are null before
                                            //   slicing — a sliced "1Y" range you request
                                            //   may still start with nulls if you ask for
                                            //   a range near the start of the data; check
                                            //   for null before charting)

APP.data.getMetric(id)                     // one claim object, or null — see §5 for shape
APP.data.getMetrics([ids])                 // array, missing ids silently dropped
APP.data.listMetricIds()                   // all known metric ids (for the Methodology
                                            //   registry browse-all view)

APP.data.getExposure(dimension)            // dimension: "assetClass" | "sector" |
                                            //   "listingMarket" | "economicGeography" |
                                            //   "country" (alias of economicGeography) |
                                            //   "currency"
                                            // -> { dimension, segments: [{label,value,pct}],
                                            //      claim }  (claim may carry a non-AVAILABLE
                                            //      state — currency exposure does, see §6)
APP.data.getConcentration()                // -> { topPositions: [{id,name,value}], hhi,
                                            //      effectiveN, claim }
APP.data.getCorrelationMatrix()            // -> { labels: [...5 series...], matrix: [[...]], claim }
APP.data.getContributionToRisk()           // -> { segments: [{label,value,reasonCode?,
                                            //      sufficiency?,caveat?}], claim }
                                            //   (one segment is deliberately INSUFFICIENT_DATA
                                            //   with reasonCode CALCULATION_ERROR — render it
                                            //   through renderMetricValue like any other)
APP.data.getSMLPoints()                    // -> { points: [{label,beta,ret,group}],
                                            //      line: {slope,intercept}, claim }

APP.data.getInsights({severity?})          // severity: "WARNING"|"ATTENTION"|"OBSERVATION"
                                            // -> [{ id, severity, judgmentClass, claim,
                                            //        relatedClaimId }, ...]
APP.data.getInsight(id)

APP.data.getEvidence(claimId)              // Proof-Packet-shaped object — see §7
APP.data.getMethodology(id)                // 15-field registry entry, or null
                                            //   ("not yet published" — this is a real,
                                            //   expected state, not a bug; see §7)

APP.data.getScenarios()                    // [{ id, name, description, modifications,
                                            //    comparison, warnings }, ...]
APP.data.getScenario(id)
                                            // `comparison` is a map of metric-name keys
                                            // (allocation, concentration, volatility, beta,
                                            // sharpe) to { current, scenario }. `current`
                                            // is always a plain value or segment array.
                                            // `scenario` is USUALLY a plain value too, but
                                            // is NOT ALWAYS — scenario.reduceCnExposure's
                                            // `sharpe` entry instead carries { current,
                                            // scenario: null, sufficiency:
                                            // "INSUFFICIENT_DATA", reasonCode:
                                            // "MISSING_BENCHMARK", caveat } deliberately
                                            // (D3 applies to scenario outputs too, per
                                            // `designs/FEATURE_DESIGN.md` §D1 surface 7
                                            // item 4). Check for a `.sufficiency` field
                                            // before treating `.scenario` as a bare
                                            // number, and where present, render THAT
                                            // side through `renderMetricValue` like any
                                            // other claim-shaped value.
APP.data.getScenarioComparisonClaim(claimId) // Added during integration (designer-14).
                                            // `claimId` is a composite id of the exact
                                            // shape scenario.js/ai.js build for a SCENARIO-
                                            // side comparison figure: `scenarioId + "." +
                                            // key` (key one of volatility/beta/
                                            // concentration/sharpe) or `scenarioId +
                                            // ".allocation." + dimension`. Returns a full
                                            // claim object (stateType "SCENARIO") or null.
                                            // Closes a real gap: those two files each used
                                            // to build this object locally with no EVIDENCE
                                            // record behind its id, so their own "Evidence"
                                            // buttons on the SCENARIO side resolved to
                                            // nothing. Both files now delegate to this
                                            // accessor first (see each file for the fallback
                                            // kept for defensiveness), and evidence.js calls
                                            // it too so the Evidence overlay can show a real
                                            // Proof Packet and the "key number" step for
                                            // these ids, not just Explanation onward.

APP.data.getFreshness()                    // -> { axes: [{axis,label,state,asOf,
                                            //      delayMinutes?,note?}], leastFreshAxis }
APP.data.getPolicy()                       // -> { reportingCurrency, singlePositionCapPct,
                                            //      sectorCapPct, riskTolerance }
                                            //   (all three cap/tolerance fields are null in
                                            //   this dataset — see §9, P7)

APP.data.getIngestionFixtures()            // -> { csv: {...}, ocr: {...} } — see §10
```

**Currency note:** all monetary figures in accessor output are USD unless the field name
says otherwise (e.g. `Holding.price` and `.avgCost` are in the holding's own `currency`;
`marketValueUSD` is always USD). `APP.data.meta.reportingCurrency` is `"USD"` for this
dataset — do not hardcode `"$"` in your own formatting; use `APP.ui.formatCurrency`.

---

## 4. Chart API (`window.APP.charts`, from `js/charts.js`)

Every function returns an `SVGSVGElement`. **None of them append themselves anywhere.**
You mount the result:

```js
mountEl.appendChild(APP.charts.lineCompare({ dates, series: {...} }));
```

Colors are read live from `tokens.css` custom properties at draw time — you do not pass
colors in; theming stays centralized.

```
APP.charts.lineCompare({ dates, series:{portfolio,benchmark}, width?, height?,
                          showDrawdown?, drawdown:{portfolio}, labelA?, labelB? })
  // The hero chart. Cumulative performance, portfolio vs benchmark, optional shaded
  // drawdown band beneath. width/height default 720x320.

APP.charts.drawdown({ dates, values, width?, height? })
  // Standalone area chart, e.g. Analytics' own drawdown block.

APP.charts.rollingLine({ dates, series:{portfolio,benchmark?}, width?, height? })
  // Rolling analytics, e.g. 90-day rolling volatility. Filters out null leading values
  // itself — pass the raw output of getRollingVolatilitySeries() directly.

APP.charts.sparkline({ values, width?, height? })
  // Small inline trend indicator, e.g. inside a compact metric-strip cell.

APP.charts.donut({ segments:[{label,value}], size?, centerLabel? })
  // Allocation summary. Segment color cycles through --chart-donut-seg-0..5 tokens.

APP.charts.bar({ items:[{label,value}], width?, valueFormat?(v) })
  // Horizontal bar — concentration, top holdings, exposure breakdowns.

APP.charts.stackedBar({ categories:[label...], series:[{label,values:[...]}], width?, height? })
  // Signed stacked bars — e.g. FX vs local-return attribution. Positive and negative
  // values in the same series both stack correctly off a zero baseline.

APP.charts.scatter({ points:[{beta,ret,label,group}], line:{slope,intercept}, width?, height? })
  // SML/CAPM. `group` drives color: "portfolio" | "benchmark" | "sleeve" | anything else.
  // Pass APP.data.getSMLPoints()'s .points and .line directly.

APP.charts.heatmap({ labels:[...], matrix:[[...]], cell?, labelWidth? })
  // Correlation matrix. Cell opacity scales with |value|; sign drives color
  // (positive = accent green, negative = warning red).
```

If you need a chart type not listed here, **do not hand-roll raw SVG inside your
surface file** — that is exactly the "four authors, four visual languages" failure mode
this contract exists to prevent. Flag the gap in your own handoff instead; a future pass
(`designer-14`'s integration, or a follow-up) can add the primitive here.

---

## 5. The claim object — the shared unit every claim-bearing render is built on

Every metric, exposure breakdown, insight, and holding-level figure in `data.js` is
shaped like this (per `designs/FEATURE_DESIGN.md` §D2.2, extended with the two fields
that document explicitly left unresolved and that this build now names — see §11):

```js
{
  id: "metric.beta",                 // stable id; used for evidence lookup and chip resolution
  label: "Beta (vs. Benchmark)",
  stateType: "ACTUAL" | "SCENARIO",  // P8 — never mix these in one rendering unit
  sufficiency: "AVAILABLE" | "LIMITED" | "INSUFFICIENT_DATA",   // D3.1
  reasonCode: null | "STALE_DATA" | "UNSUPPORTED_ASSET" | "MISSING_BENCHMARK" |
              "MISSING_COST_BASIS" | "MISSING_FX_HISTORY" | "CALCULATION_ERROR",
  value: number | null,              // null whenever sufficiency === "INSUFFICIENT_DATA"
  unit: "currency" | "percent" | "ratio" | "number" | "bps",
  formatted: string | undefined,     // pre-formatted override (used for composite
                                      // claims like Performance Attribution, Correlation,
                                      // SML — anything not a single scalar)
  referencePoint: string,            // P4 — benchmark/policy/history the conclusion is judged against
  conclusionQuick: string,           // Quick depth
  explanationSimple: string,         // Simple depth
  investorDetail: string,            // Investor depth
  professionalDetail: string,        // Professional depth
  caveat: string,                    // D2.2's caveat slot — see rendering rule in §6
  freshness: { axis, label, state, asOf, delayMinutes? } | null,   // D5 slot — see §11
  methodologyId: string | null,      // D4 — points into APP.data.getMethodology()
  proofPacketId: string | null,      // unused in this dataset (methodologyId covers it);
                                      // reserved for a future purely-generated (non-metric)
                                      // AI claim that has no registry entry at all
  scenarioId: string | null          // populated when stateType === "SCENARIO"
}
```

**You never construct one of these yourself with invented values.** Every claim object
your surface renders must come from a `getMetric`/`getHoldingClaim`/`getExposure`/etc.
accessor. If you need a claim that doesn't exist yet in `data.js`, that is a gap to
report, not a local literal to fabricate — a hand-authored claim bypasses the one place
this dataset's internal consistency is enforced.

---

## 6. The metric-state renderer — one renderer, no exceptions

**`APP.ui.renderMetricValue(container, claim)`** is the *only* sanctioned way any surface
renders a number that carries a sufficiency state. Do not write your own
if/else on `claim.sufficiency` anywhere in `js/surfaces/*`. This exists specifically
because the em-dash-as-`INSUFFICIENT_DATA`-placeholder mistake (finding P-1,
`reviews/gates/HG1_PROTOTYPE_INSPECTION.md`) recurred independently in a cold-started
Direction A mockup (`designs/hg1-revision/COMPARISON.md` §4) — twice by accident is a
pattern, and the fix is structural, not another reminder.

The exact rule this function implements, per `designs/FEATURE_DESIGN.md` §D3.2 (as
amended for `AVAILABLE`+`STALE_DATA`):

| `sufficiency` | Renders | What you get if you call `renderMetricValue` |
|---|---|---|
| `AVAILABLE`, no `reasonCode` | Plain numeral, normal format | `.metric-number`, no badge attached at this unit |
| `AVAILABLE` + `reasonCode: "STALE_DATA"` | **Identical numeral** to plain `AVAILABLE` | `.metric-number` **plus** a `.freshness-pill` naming the specific stale axis — never a D3-style qualifier, because the value is not degraded |
| `LIMITED` | Numeral **plus mandatory qualifier in the same visual unit** | `.metric-number` + `.metric-qualifier` (non-dismissible, never a tooltip) |
| `INSUFFICIENT_DATA` | **No numeric glyph of any kind** — not `0`, not an em-dash | `.metric-insufficient-label` ("insufficient data") + `.metric-reason`, a structurally distinct component |

**Why plain `AVAILABLE` gets no inline freshness badge, and why that is not a contradiction
of D5.2's "freshness indicator required next to the value it qualifies":** D3.2's
corrected table is explicit that the plain-`AVAILABLE` row attaches nothing extra "at the
value's own rendering unit," while `AVAILABLE`+`STALE_DATA` and `LIMITED` both do. D5.2's
broader requirement — a freshness indicator visible near a value derived from mixed-market
inputs — is satisfied at the *surface* level (the global freshness strip, a per-position
freshness column on Holdings) independent of whether any single value's own rendering
unit carries an inline badge. The two requirements operate at different granularities and
neither one is optional; `renderMetricValue` handles the value-unit granularity only.

**The freshness ranking never compares raw clock times across axes.**
`APP.ui.rankLeastFresh(axes)` ranks by a fixed categorical severity order
(`STALE` > `END_OF_DAY` > `DELAYED` > `LIVE`), not by parsing and comparing timestamp
strings. This is a deliberate mitigation of the exact bug found in Direction A
(`COMPARISON.md` §4, finding 2): comparing "16:08 HKT" against "15:00 CST" by clock value
alone gets the wrong axis when the two timezones share an offset but the exchanges close
at different local times. Do not write your own freshness comparison — call
`rankLeastFresh` or read `APP.data.getFreshness().leastFreshAxis`, which already used it.

---

## 6A. Shared UI primitives — complete reference

Every function `js/shell.js` exposes on `window.APP.ui`, in one place, so nothing here
has to be reverse-engineered from behavior. **If a primitive you need isn't listed here,
it doesn't exist yet — flag the gap in your handoff; don't hand-roll the equivalent.**

```
// Metric-state rendering (D3.2) — see §6 above for the full rule table.
APP.ui.renderMetricValue(container, claim)
  // Renders ONLY the value+state unit (no ladder, no label). Use this for compact
  // contexts — a table cell, a metric-strip stat, an inline figure — where a full
  // claim card would be too heavy.

// Progressive-disclosure ladder (D2) — conclusion -> key number -> explanation ->
// evidence -> methodology, closed by default.
//
// HG1 M3 fix — READ §17 BEFORE ASSUMING THIS IS THE WHOLE PROGRESSIVE-DISCLOSURE
// STORY. This four-rung ladder is a PER-CARD, LOCAL mechanism. Since HG1 Round 5's
// module-visibility rebuild (PD-0016 Part 1), whether a card carrying this ladder is
// reachable AT ALL is governed by a SEPARATE, global, THREE-rung
// APP.state.explanationMode ("quick"|"simple"|"professional") and each module's own
// declared minMode, via ctx.ui.renderModule — §17 documents that mechanism, which had
// no entry anywhere in this file before this fix. A card's own `depth` here answers
// "how much of THIS card is showing"; `minMode`/`explanationMode` answers "is this
// card's module on the page at all." The two ladders do not share a rung count and
// are not the same axis — do not conflate them.
APP.ui.renderClaim(container, claim, { depth?, showLadder? })
  // depth: "quick"|"simple"|"investor"|"professional", default "quick".
  // showLadder: false suppresses the Quick/Simple/Investor/Professional selector and
  // renders only the given depth, statically (e.g. for a compact preview card that
  // shouldn't invite expansion). Internally calls renderMetricValue for the value —
  // never duplicates its state logic. Always renders the caveat slot when
  // claim.caveat is non-empty or claim.sufficiency !== "AVAILABLE" (D2.2's guarantee:
  // the slot exists structurally, it is never a rendering rule's decision to omit it).
  // Always renders an "Evidence & Methodology" control regardless of depth (D4.2:
  // reachable at every depth level, not gated behind Professional).

// Freshness (D5) — two axes never merge; see §6 above for the ranking rule.
APP.ui.renderFreshnessStrip(container, freshnessData)
  // freshnessData: APP.data.getFreshness()'s return shape, { axes, leastFreshAxis }.
  // Renders one pill per axis plus a "Least fresh: <axis>" callout. Never collapses to
  // a single timestamp.
APP.ui.renderFreshnessPill(container, axisEntry)
  // Single-axis compact pill, e.g. for a per-position freshness column on Holdings.
APP.ui.rankLeastFresh(axes) -> axisKey | null
  // Categorical severity ranking, documented in §6.

// ACTUAL vs SCENARIO (P8) and STAGED vs COMMITTED (ingestion, addendum §3) — two
// structurally parallel but NEVER-merged badge vocabularies.
APP.ui.renderActualScenarioBadge(container, stateType)   // stateType: "ACTUAL"|"SCENARIO"
APP.ui.renderStagedBadge(container, status)              // status: "STAGED"|"COMMITTED"

// OCR confidence — a vocabulary DISTINCT from metric sufficiency. See §7 below.
APP.ui.renderConfidencePill(container, field)
  // `field` is a fixture object taken DIRECTLY from
  // APP.data.getIngestionFixtures() — no translation step. Works for either shape:
  //   an OCR field:  { confidence: "HIGH"|"LOW"|null, status: "OK"|"LOW_CONFIDENCE"|
  //                    "MISSING_FIELD"|"AMBIGUOUS_SECURITY"|"POSSIBLE_DUPLICATE"|
  //                    "CORRECTED"|"CONFIRMED", ... }
  //   a CSV row:     { status: "STAGED"|"AMBIGUOUS_SECURITY"|"MISSING_FIELD"|
  //                    "POSSIBLE_DUPLICATE", ... }
  // `status` (if recognized) wins over `confidence` for label/color; `confidence`
  // alone (HIGH/LOW) is the fallback when `status` is "OK" or absent.

// Provenance chip (P1) — the ONLY sanctioned way a numeral appears inside AI-authored
// prose. This is the mechanism Direction C's own author named as this rebuild's
// highest structural risk (COMPARISON.md §3, criterion 7) — it is centralized here so
// there is exactly one implementation to audit, not one per AI narrative template.
APP.ui.chipHTML(claim, displayText?) -> string
  // Returns an HTML STRING (not a DOM node) — designed for template-literal
  // composition when building a sentence: `"Volatility was " + APP.ui.chipHTML(claim)
  // + " this period."`. `claim` may be a full claim object (preferred — displayText
  // defaults to its formatted value) or a bare claim-id string (then you MUST pass
  // displayText explicitly, or the chip renders "—"). Clicking a chip opens the
  // Evidence overlay for that claim id automatically — the click handler is wired
  // ONCE, globally, by shell.js; you do not attach your own listener.
  // RULE FOR js/ai.js, REFINED during integration (designer-14, see below):
  // every digit appearing in any `.ai-narrative`-classed block must be inside a
  // `.chip` produced by this function, UNLESS it is a pure selector/ordinal digit
  // (PD-0008's test: "does the number assert something about the portfolio that
  // could be false?" — if no, e.g. "top 5 holdings" only names which segment is
  // being discussed, it is not a claim), in which case it goes through
  // `APP.ui.selectorHTML` instead (below). Connective words ("driven mainly by,"
  // "the most important thing to review is") remain ordinary plain text either way.
APP.ui.selectorHTML(text) -> string
  // Added during integration (designer-14). Returns an HTML STRING wrapping `text`
  // in `<span class="numeral-selector">`, for the ONE other case a digit may appear
  // inside `.ai-narrative`: a selector/ordinal that asserts nothing falsifiable about
  // the portfolio (PD-0008). This exists because js/ai.js's original phase-2 author
  // found a genuine gap and named it rather than routing around it silently: the
  // `checkNarrativeSafety` scanner (below) is a blunt digit-regex and cannot itself
  // distinguish a selector digit ("top 3 holdings") from a claim digit — so that
  // author's original choice was to avoid literal digits in selector phrases
  // entirely, rather than risk a false-positive console warning `pm-01` would have
  // to second-guess. `selectorHTML` replaces that avoidance with an explicit,
  // greppable exception: every use is a real span in the DOM, auditable by a
  // reviewer, not a scanner silently guessing from regex context. It renders as
  // plain inline text (no chip affordance, not clickable) — a reader is never
  // invited to click it expecting a Proof Packet, because it isn't one.
APP.ui.checkNarrativeSafety(containerEl)
  // Dev-time QA helper: scans containerEl for `.ai-narrative` blocks, strips `.chip`
  // AND `.numeral-selector` elements (the refinement above), and console.warns if
  // any digit remains in what's left. Call this after rendering AI prose in
  // development; it does not run automatically and does not block anything at
  // runtime — it is a safety net for YOU to catch a missed chip/selector wrapper
  // before pm-01 does.

// Contextual AI affordance — invoked FROM a chart/metric/section, never a top-level
// nav destination (owner's explicit instruction, §8 below).
APP.ui.aiAffordance(container, context) -> HTMLButtonElement
  // context is a free-form object YOU define the shape of (e.g. { label, contextLabel,
  // contextClaims: [ids], prompt }) — shell only reads context.label for the button's
  // visible text (falls back to "Ask about this") and passes context through
  // unchanged to whatever opens. Renders one button, wired to APP.ui.openAI(context).
APP.ui.openAI(context)
  // Opens the AI slide-over. If js/ai.js has called APP.registerAI(handler), calls
  // handler.renderPanel(mountEl, context). If not, renders a clearly-marked "not yet
  // built" panel — deliberately NOT a synthesized placeholder narrative, because
  // authoring grounded AI text is js/ai.js's job, not shell's (see §7 below for why
  // this differs from Evidence's fallback).
APP.registerAI({ renderPanel(mountEl, context) })
  // js/ai.js's one required export.

// Evidence / Methodology overlay (D4, P9) — see §7 below for the fallback-rendering
// rationale and the two-vocabulary rule.
APP.ui.openEvidence(claimId | null)
APP.registerEvidence({ open(claimId, mountEl) })

// Focus-and-inspect (Direction B graft, "where useful" — optional per surface).
APP.ui.inspector.focus({ title, render(mountEl) })
  // Opens the right-docked panel, sets its title, and calls render(mountEl) once.
  // Nothing else manages this panel's content for you — re-call focus() yourself if
  // the underlying data changes while it's open.
APP.ui.inspector.clear()
  // Empties and visually collapses the panel back to its slim rail state.

// Shared insight rendering (D1 surface 6 — "integrated into relevant surfaces," no
// dedicated phase-2 file owns this).
APP.ui.renderInsightsList(container, insights, { mode? })
  // mode: "compact" (default) | "full". insights: APP.data.getInsights()'s return
  // shape. Each row gets a severity glyph, the claim text, its judgment-class tag, and
  // an "Evidence" button wired to APP.ui.openEvidence(insight.id).

// "Not yet built" placeholder — reusable outside the router itself if your own
// surface wants to render a sub-panel for something it intentionally defers.
APP.ui.notBuilt(container, { label?, owner?, detail? })

// Formatting — do not reimplement currency/percent/number formatting per surface.
APP.ui.formatCurrency(value, currency?)   // default currency "USD"
APP.ui.formatPercent(value, digits?)      // default digits 1; prefixes "+" for positive
                                           // values, negative values keep their own "-"
APP.ui.formatNumber(value, { unit?, currency?, digits? })
  // unit: "currency"|"percent"|"ratio"|"bps"|other. Dispatches to the two functions
  // above for "currency"/"percent"; "ratio" fixed to `digits` (default 2); "bps"
  // multiplies by 10000 and appends " bps"; anything else rounds to 2 decimals.
```

---

## 7. Evidence, Methodology, and the two-vocabulary rule

**`APP.ui.openEvidence(claimId)`** opens the evidence overlay. Pass `null` for the
"browse the whole registry" view (used by the footer's "Methodology & Evidence Registry"
link). If `js/evidence.js` has registered a handler, it takes over rendering completely.
**Until then, the shell renders a real, if basic, fallback** — pulling the same
`getEvidence`/`getMethodology` fields directly and listing them — clearly labeled as a
default that `evidence.js` will replace. This is different from the AI fallback (below)
on purpose: formatting already-structured fields is safe for the shell to do; authoring
new narrative is not.

**Two registry entries in this dataset are deliberately left unpopulated**
(`getMethodology()` returns `null` for them) so the "not yet published" empty state
(`designs/FEATURE_DESIGN.md` §D1, surface 11) is demonstrated alongside populated ones,
not asserted only in prose. This is a considered choice, not an oversight: five metrics
(`portfolioReturn`, `beta`, `alpha`, `volatility`, `concentration`) carry full illustrative
15-field entries; the rest resolve to the empty state. If your surface needs a specific
metric's methodology populated for a screen to look complete, either use one of the five
above for your worked example, or note the gap in your handoff — do not invent registry
content in your own file.

**OCR confidence is a separate vocabulary from metric sufficiency — never render one
through the other's component.** Per `specs/OCR_INGESTION_ADDENDUM.md` §4.1: `AVAILABLE`/
`LIMITED`/`INSUFFICIENT_DATA` describe whether a *computed metric* has enough data.
`HIGH`/`LOW`/`AMBIGUOUS_SECURITY`/`MISSING_FIELD`/`POSSIBLE_DUPLICATE`/`CORRECTED`/
`CONFIRMED` describe how sure an OCR extraction is and what state a staged field is in.
`renderMetricValue` renders the first; `APP.ui.renderConfidencePill(container, field)`
(§6A — pass an OCR/CSV fixture object straight through, no translation) renders the
second. They are visually distinct (different token families —
`--color-limited*` vs. `--color-confidence-*`) and structurally separate functions on
purpose. `js/surfaces/ingest.js`: do not pass an OCR field through `renderMetricValue`,
and do not pass a claim through `renderConfidencePill`.

---

## 8. Navigation and IA

**No deviation from the owner's four-primary-surface hypothesis** (Overview / Portfolio
/ Analytics / Scenario Lab) — it is implemented exactly as named. What this build adds,
within that hypothesis, is how the eleven `designs/FEATURE_DESIGN.md` §D1 surfaces map
onto it:

| D1 surface | Where it lives here | Why |
|---|---|---|
| 1. Overview | Primary tab `overview`, group `overview` | Direct |
| 2. Holdings | Inside `portfolio` surface (secondary content, not a shell-level tab) | Owner: "Transactions contained within Portfolio where appropriate" — extended to Holdings, which is the same object graph |
| 3. Performance | Inside `analytics` surface | The owner's §5 lists Performance content (return, benchmark comparison, FX/performance attribution) as *Analytics* breadth, not Portfolio's |
| 4. Exposure | Inside `analytics` surface | Same reasoning — country/currency/sector/asset exposure, concentration, correlation are named together in the owner's Analytics list |
| 5. Risk & Analytics | Inside `analytics` surface | Direct |
| 6. Insights | **No dedicated file.** Shared `APP.ui.renderInsightsList` primitive (shell.js), embedded wherever a surface wants it — Overview's Attention block is the primary home | Owner: "Insights integrated into relevant surfaces," not a tab |
| 7. Scenario Lab | Primary tab `scenario`, group `scenario` | Direct |
| 8. AI Analyst | Global header "Ask your portfolio" + per-context `APP.ui.aiAffordance()` buttons + slide-over overlay (`js/ai.js` renders the panel content) | Owner: "AI as contextual/persistent rather than a dedicated top-level destination" |
| 9. Transactions | Inside `portfolio` surface | Owner's explicit instruction |
| 10. Portfolio Settings / Policy | Gear icon, outside primary nav, **built directly in `shell.js`** | No phase-2 file owns it; §D1 surface 10 renders no D2.2 claim (per `FEATURE_DESIGN.md`'s own disposition), so it needed no accessor-heavy interaction design a phase-2 designer would otherwise own |
| 11. Methodology & Evidence | Evidence overlay + footer link, reached contextually only | Owner's explicit instruction; matches all three accepted directions |

**Why Portfolio hosts two registered surfaces instead of one.** `portfolio.js` (Holdings,
Exposure-adjacent detail, Transactions, Accounts) and `ingest.js` (CSV import, OCR
staging/review) are different enough in interaction model — one is "browse the ledger,"
the other is "review and confirm a multi-step staged batch" — that splitting them into
two files with a shared secondary nav (which the shell renders for you) keeps either
file's job legible on its own, while still satisfying "reduce navigation" at the primary
level: Import is one click from Holdings, not a fifth primary tab.

**Why Performance and Exposure moved from "under Portfolio" (as Direction C originally
placed them) to "inside Analytics."** The owner's §5 instruction to this specific build
("Analytics — demonstrate the real breadth of V1") explicitly lists FX attribution,
performance attribution, SML/CAPM, and country/currency/sector exposure/concentration/
correlation together as what Analytics must show. Direction C's own document placed
Performance and Exposure as secondary tabs under Portfolio; this build re-groups them
under Analytics instead, because the owner's item-5 instruction for *this specific
prototype* is more specific than Direction C's original mapping and this build is
required to satisfy it. This is a considered re-grouping of *navigation slot*, not a
change to any D1 surface's own content requirements — nothing is dropped, nothing is
renamed, only which primary tab hosts it.

---

## 9. Portfolio Policy (P7) is deliberately unset

`APP.data.getPolicy()` returns `singlePositionCapPct: null`, `sectorCapPct: null`,
`riskTolerance: null`. This is not a placeholder to fill in — it is the honest default
state, and the Settings overlay (built in `shell.js`) already renders the required P7
disclosure ("no cap is set; insights use comparative language, not a personal
threshold"). If your surface renders an insight or claim that would only be meaningful
against a personal policy value (the concentration insight,
`insight.policy.noCapSet`, already demonstrates the correct handling), **do not invent a
threshold** — read `getPolicy()` and branch on `null` the same way the existing insight
does.

---

## 10. Ingestion fixtures — CSV and OCR, all seven required states

`APP.data.getIngestionFixtures()` returns `{ csv, ocr }`.

`csv.rows[]` each carry `{ raw, mapped, status, issues }`, `status` one of `STAGED` /
`AMBIGUOUS_SECURITY` / `MISSING_FIELD` / `POSSIBLE_DUPLICATE`.

`ocr.documents[]` each carry `{ id, sourceType, filename, uploadedAt, overallStatus,
fields[] }`. Across the three documents, every field-level state the owner's instruction
requires is present at least once: high-confidence extraction (`ocr-doc-1`/`f1`,`f2`),
low-confidence field (`f3`), ambiguous security match (`f4`, with `candidates[]`), missing
field (`f5`), possible duplicate (`f6`), reconciliation/correction (`ocr-doc-2`/`g1`, with
`correctedValue`/`correctedBy`/`correctedAt`), and final human confirmation
(`ocr-doc-3`/`h1`, with `confirmedBy`/`confirmedAt`). Each field's `region` object
(`{page,x,y,w,h}`) is the OCR-2 source-location/evidence pointer — render it as at least a
"page N, region" citation if your design shows it at all; this build does not specify
that a literal image crop must be shown (no actual uploaded image exists in this
prototype — the fixtures simulate extraction results, per
`specs/OCR_INGESTION_ADDENDUM.md` §5, which explicitly permits this).

**STAGED vs. COMMITTED is P8's mechanism, reused, not reinvented.**
`APP.ui.renderStagedBadge(container, status)` renders the non-dismissible "STAGED — NOT
YET IN YOUR PORTFOLIO" / "COMMITTED" treatment. Every row/field in the ingest surface that
has not passed through an explicit confirm action must carry the `STAGED` badge; nothing
reaches Holdings/Transactions data as if committed without it. `ingest.js` owns the actual
confirm-flow interaction (OCR-11); this badge is the shared visual vocabulary for it.

---

## 11. Decisions this build makes that `designs/FEATURE_DESIGN.md` left open

Per the owner's own instruction ("do not reopen these contracts unless the redesign
exposes a genuine contradiction"), the following are **re-expressions in the D2.2/D5
sense the document itself invited**, not new decisions about product logic:

- **The D5 freshness field now has a named home on the claim object** (`claim.freshness`,
  §5 above). `designs/FEATURE_DESIGN.md`'s own Known Limitations section flagged this gap
  explicitly and said it was waiting for "whoever next revises D2.2's object model with a
  real surface to design against" — this is that revision. It adds a field; it does not
  change what D2.2 requires the other four fields to mean.
- **The freshness-severity ranking function** (`rankLeastFresh`, §6) is a UI/interaction
  decision (how to compare states for display purposes), not a change to D5's two-axis
  model itself.

No other item in `designs/FEATURE_DESIGN.md` §D1–D5 is reopened by this build. If your
own phase-2 work surfaces something that looks like a genuine contradiction (not just an
inconvenience), **record it in your handoff; do not resolve it yourself** — same rule
this whole cycle has followed since the direction-selection stage.

---

## 12. Naming and CSS conventions

- **Class names:** kebab-case, feature-prefixed. `.claim-*` (claim card internals),
  `.metric-*` (value rendering), `.chart-*` (SVG structural classes, styled in
  `app.css`, colored via CSS custom properties read at draw time), `.state-badge` +
  `.badge-actual`/`.badge-scenario`/`.badge-staged`/`.badge-committed`, `.confidence-pill`
  + `.confidence-*`, `.chip` (provenance), `.block`/`.card` (container), `.insight-*`,
  `.freshness-*`. **Add to this list, don't fork it** — if you need a new visual
  category, name it consistently with the existing prefixes.
- **Tokens:** every color, spacing value, radius, and shadow used anywhere must come
  from a `--color-*`/`--space-*`/`--radius-*`/`--shadow-*` custom property in
  `styles/tokens.css`. Do not write a literal hex value or pixel size in your own file's
  markup or inline styles. If a token you need is missing, that is a gap to flag, not a
  license to hardcode.
- **Analytical surfaces** (Analytics screen, the inspector dock) use the
  `.analytical-surface` wrapper class, which switches card background to
  `--color-analytical-surface` and numerals to tabular monospace — this is the Direction
  B graft. Do not apply `.analytical-surface` to Overview or Scenario Lab; it is scoped
  to where B's denser, analyst-desk register was explicitly invited in.
- **Depth ladder values** are always the literal strings `"quick"`, `"simple"`,
  `"investor"`, `"professional"` (lowercase), matching `renderClaim`'s `opts.depth`.
  **Do not confuse this with `APP.state.explanationMode`**, a separate, global,
  three-rung value (`"quick"`|`"simple"`|`"professional"`) — see §17.
- **Focus-and-inspect ("where useful"):** call `APP.ui.inspector.focus({ title, render(mountEl) })`
  from a chart click handler or a table row's click handler when your surface wants
  Direction B's "focus an object, read its resolution in a docked panel" behavior — this
  is optional per surface, not mandatory. `APP.ui.inspector.clear()` empties it. Overview
  is not expected to use this; Analytics is the natural fit (e.g., focusing a correlation
  cell or a metric card).

---

## 13. Worked example — a complete, minimal surface module

This is illustrative only (do not create this file — it is not real, it is a teaching
example inside this document). It demonstrates: `registerSurface`, the metric-state
renderer via `renderClaim`, a chart, the disclosure ladder, and a contextual AI
affordance, all through the primitives above and nothing hand-rolled.

```js
// EXAMPLE ONLY — not a real file in this build.
(function () {
  "use strict";
  window.APP.registerSurface("example", {
    group: "analytics", // any valid group for illustration
    render: function (mountEl, ctx) {
      mountEl.innerHTML = "";

      var block = document.createElement("div");
      block.className = "block";
      var header = document.createElement("div");
      header.className = "block-header";
      var kicker = document.createElement("span");
      kicker.className = "block-kicker";
      kicker.textContent = "Risk";
      header.appendChild(kicker);
      block.appendChild(header);

      // 1. The claim, rendered through the ladder — never hand-rolled.
      var claimMount = document.createElement("div");
      block.appendChild(claimMount);
      var volClaim = ctx.data.getMetric("metric.volatility");
      ctx.ui.renderClaim(claimMount, volClaim, { depth: "quick" });

      // 2. A chart, mounted from a pure chart function.
      var chartMount = document.createElement("div");
      chartMount.style.marginTop = "12px";
      var series = ctx.data.getRollingVolatilitySeries({ range: "1Y" });
      chartMount.appendChild(ctx.charts.rollingLine({ dates: series.dates, series: series }));
      block.appendChild(chartMount);

      // 3. A contextual AI affordance — never a top-level destination.
      var aiMount = document.createElement("div");
      aiMount.style.marginTop = "8px";
      ctx.ui.aiAffordance(aiMount, {
        label: "Ask about this volatility",
        contextLabel: "metric.volatility",
        contextClaims: ["metric.volatility", "metric.benchmarkRelative"]
      });
      block.appendChild(aiMount);

      mountEl.appendChild(block);
    }
  });
})();
```

Note what this example does **not** do: it does not check `volClaim.sufficiency` itself
(that's `renderClaim`'s/`renderMetricValue`'s job); it does not draw its own SVG axis; it
does not open a chat window inline; it does not invent a number. Pattern-match on this
shape, not on any particular block's visual content.

---

## 14. What I could not verify

I have no browser or JS runtime in this sandbox. I re-read every file above after
writing it, checked brace/paren balance and every `getElementById` call against the
corresponding `id` in `index.html` by hand, and traced every cross-file reference
(`APP.ui.*`, `APP.data.*`, `APP.charts.*`) against its actual definition — but none of
that is the same as having loaded the page. **`pm-01` (or whoever serves this over
`python3 -m http.server`) should verify, before relying on any of it:**

- the app boots at all and the four primary tabs render;
- the Portfolio secondary nav (Holdings & Activity / Import & Ingestion) appears and
  switches correctly;
- every route not yet built by phase 2 renders the labeled "not yet built" panel rather
  than a blank screen or a console error that stops the page;
- the freshness strip in the header renders without throwing (it is the one shell
  feature that runs immediately at boot, before any surface is registered);
- the Settings overlay, Evidence overlay (browse-all via the footer link), and AI overlay
  (fallback "not yet built" state, since `ai.js` doesn't exist yet) each open and close;
- no console errors originate from `shell.js`, `data.js`, or `charts.js` themselves
  (404s for not-yet-created `js/surfaces/*.js`, `js/ai.js`, `js/evidence.js` are expected
  and fine at this stage).

---

## 15. HG1 Round 5 micro-pass addendum — `js/i18n-selfcheck.js` (new file)

Added a static `<script src="js/i18n-selfcheck.js"></script>` tag to `index.html`,
directly after `js/selfcheck.js`'s own tag and before `js/charts.js`'s — this designer's
write scope this round covers the whole `designs/hg1-prototype-v2/` tree, so (unlike
`js/selfcheck.js`'s own history immediately above) no dynamic-injection workaround was
needed.

**Namespace: `window.APP.i18nCheck`, not `window.APP.selfcheck`.** A deliberate sibling,
not an addition to `js/selfcheck.js` — that file reads **only** `window.APP.data`, by its
own stated design; this file's four assertions are entirely about the i18n/classifier
layer (`window.APP.i18n`, `window.APP.ui`), a different boundary, and blurring the two
would violate `js/selfcheck.js`'s own "never `APP.ui`/`APP.charts`" rule rather than
extend it. `APP.i18nCheck.run()` returns `{ allPass, allProvenToFail, results: [...] }`;
each of the four `results` entries follows this codebase's own established
before-injection/during-injection/after-restore `provenToFail` shape (see `js/shell.js`'s
`APP.uicheck` mutation tests) — a defect is deliberately introduced into either the
classifier function itself or one dictionary entry, the check is shown to fail, then
everything is restored and shown to pass again. Not run automatically at load (unlike
`js/selfcheck.js`); call `APP.i18nCheck.run()` from the console.

Three small diagnostic hooks were added to `APP.i18n` in `js/shell.js` for this file to
use, following the exact same "expose the minimum a read-only verification pass needs,
never used by product code" precedent `APP.state.setExplanationModeQuiet` and this file's
own pre-existing `setLangQuiet` already set: `APP.i18n.setLangQuiet` (now also public, it
already existed privately), `APP.i18n._allKeys()`, and `APP.i18n._testSetKey(lang, key,
value)` (the last used only to construct and then fully clean up an injected defect —
never leaves a test key behind in the real dictionary).

**I have no browser or JS runtime in this sandbox**, same limitation as §14 above,
unchanged this round. Verified by re-reading, brace/paren-balance checking, and tracing
every `APP.i18n.*`/`APP.ui.*`/`APP.data.*` reference against its definition — not by
running it. `pm-01` should run `APP.i18nCheck.run()` in the console and confirm
`allPass: true` and `allProvenToFail: true` before relying on it.

## 16. HG1 Round 5 SECOND micro-pass addendum — three named defects, precisely scoped

Per `reviews/gates/HG1_ROUND5_MICROPASS_VERIFICATION.md`. Cold-start worker, this
designer's write scope covers the whole `designs/hg1-prototype-v2/` tree; three defects
only, nothing else touched.

**Defect 1 — sticky-clearance lifecycle staleness (`js/shell.js`, `styles/tokens.css`).**
Diagnosed against every hypothesis the brief named, from reading the code (no browser
available — see §14/§15's same disclosed limitation): `header.app-header` is static
markup, never replaced or recreated by any render in this app, so "observing a node a
later render replaces" is ruled out; the observer was created exactly once and never
disconnected, so "recreated incorrectly" is also ruled out. What could not be
independently confirmed or ruled out without a live browser is whether the shipped
`ResizeObserver` instance itself actually failed to fire on a real cross-breakpoint
resize. Rather than bet the fix on one unverifiable guess, the single point of failure
is removed: a `window` `resize` listener is added as a second, independent trigger for
the same `scheduleHeaderRemeasure` seam the ResizeObserver now also calls (instead of
calling `measureHeaderClearance` directly), the ResizeObserver is given an explicit
`{ box: "border-box" }` observation matching what is actually measured/written, and
every trigger (boot, language switch, explanation-mode change, resize, ResizeObserver
notification) is coalesced through one `requestAnimationFrame`-deferred read — fixing
1b (the pre-settlement synchronous read, measured at 95.75px vs. a 122px settled height)
at the same seam. A new async regression check, `APP.uicheck.checkHeaderClearanceAfterResize`
/ `.selfTestHeaderClearance`, forces the header taller, dispatches a real `resize` event,
and asserts the property tracks the new height within 1px — written to the same
before/during/after mutation-test discipline as every other check in this file, with the
defect injection being a no-op'd `measureHeaderClearance`. **Not executed** — no
browser/JS runtime available; structurally sound and traced against the real production
call paths, but its actual pass/fail in a live browser is unverified by me.
`table.sticky-head thead th` / `.table-scroll-wrap` were not touched.

**Defect 2 — composed `Name (TICKER)` classifier gap (`js/shell.js`,
`APP.i18n.isAllowlistedCanonical`).** Added one structural rule after the existing
live-derived security/account-name checks: parse a trailing `(...)` group off the
string, require the parenthesized part to match `patterns.tickerLike`, then require a
holding exist whose `id` equals that ticker AND whose `name` equals the text before the
parenthesis — same record, not independently-matching halves. No literal company names
added. Three tests added to `js/i18n-selfcheck.js` (`testComposedCanonicalExempt`,
`testComposedCanonicalNotExempt`), matching this pass's own required cases: a live
canonical `Name (TICKER)` exempts; a sentence ending in a real ticker-shaped token
("...(ACWI)") that is not any holding's id does not; a real ticker paired with the wrong
name ("Fake Company (AAPL)") does not, proving the same-record requirement rather than
shape-only matching.

**Defect 3 — remaining genuine gaps.** The footer's lowercase synthetic-data sentence
(distinct from the already-canonical uppercase banner) now has a stable DOM hook
(`#app-footer-synthetic-note` in `index.html`) and an i18n key
(`common.syntheticFooterNote`), localized by `localizeStaticChrome()` on all five routes.
The one Portfolio holding caveat ("Transferred in-kind from a legacy custodian on
2026-…", `js/data.js`'s `HOLDING_CLAIMS` for the INSUFFICIENT_DATA cost-basis case) now
carries `claim.i18n.zh.caveat` — the SAME structural hook every other translated claim
field already uses (`APP.ui.localizeClaimField`), populated for the first time on this
one claim rather than a new mechanism; `h.addedDate` is concatenated identically into
both language strings, unchanged. Full caveat content preserved, not shortened (F4's
caveat/qualifierShort split is untouched — this claim carries no `qualifierShort`).

**Verification honesty, unchanged from §14/§15:** no browser, no JS runtime, no
`node --check` in this environment. Every change above was traced by re-reading source
and following every reference to its definition, not by execution. See this designer's
handoff report for the full priority-ordered verification list handed to the PM.

---

## 17. HG1 M3 fix — `explanationMode`, `minMode`, `renderModule`: the current three-rung architecture, documented (this was previously undocumented)

**Why this section exists.** A grep for `minMode|renderModule|explanationMode` across
this entire file returned **zero matches** before this fix, while §6A/§12 (above)
described the four-rung *per-card* ladder (`renderClaim`'s `depth`:
`"quick"|"simple"|"investor"|"professional"`) as though it were the complete
progressive-disclosure story. It was, once — PD-0016 Part 1's module-visibility rebuild
(HG1 Round 5, Phase 2) layered a second, global mechanism on top of it, and no prior
addendum ever wrote that mechanism down here. This section is that missing
documentation. **Nothing about the four-rung ladder is wrong or removed** — §5/§6/§6A/
§12 above remain accurate for what they describe. What was missing is the fact that a
card carrying that ladder is only reachable at all if its enclosing *module* is visible,
and module visibility is a *different* system with a *different* rung count.

### 17.1 Two ladders, not one — the distinction that matters

| | Per-card ladder (§5/§6A, unchanged) | Global explanation mode (this section, new) |
|---|---|---|
| Values | `"quick"` \| `"simple"` \| `"investor"` \| `"professional"` (four) | `"quick"` \| `"simple"` \| `"professional"` (three — no `"investor"` rung) |
| Governs | how much of ONE already-visible claim card is expanded (`renderClaim`'s `opts.depth`) | whether an entire MODULE is on the page at all (`ctx.ui.renderModule`'s `opts.minMode`) |
| Scope | local — set per call site, or by the card's own ladder-selector control | global app state — `APP.state.explanationMode`, one value for the whole session |
| Where it lives | `js/shell.js`'s `renderClaim`/`renderLadderControl` | `js/shell.js`'s `APP.state` + `APP.ui.renderModule` |
| Per PD-0016 Part 1 | "Per-card ladders **survive** as **local overrides** of the global mode" | the new, primary axis |

A module that IS visible under the global mode may still contain a claim card whose OWN
`depth` is `"quick"` — the two are independent knobs. A module that is NOT visible under
the global mode is unreachable at rest regardless of what `depth` its (unrendered) cards
would use — it collapses to a named, one-click `<details>` affordance instead (§17.3).

### 17.2 `APP.state.explanationMode` — application state, not per-card state

```
APP.state.getExplanationMode() -> "quick" | "simple" | "professional"
APP.state.setExplanationMode(mode)        // triggers a full re-render of the current route
APP.state.setExplanationModeQuiet(mode)   // sets without re-rendering — used only by
                                           // APP.uicheck's off-screen comparison renders
                                           // (§ uicheck, this file's own round-5 addendum)
                                           // so a diagnostic probe never causes visible
                                           // flicker on the live page.
APP.state.explanationModeAtLeast(mode) -> boolean
  // rung order: "quick" < "simple" < "professional". Used by renderModule (below) and
  // safe to call directly if a surface needs an inline conditional instead of a full
  // module gate.
```

Set via the persistent explanation-mode control in the global header (every route) and
via Settings; propagates to every surface because every surface's `render()` reads
`APP.state.getExplanationMode()` (directly, or indirectly through `renderModule`) on
every call, and a mode change triggers `renderRoute()` again from scratch.

### 17.3 `ctx.ui.renderModule(container, opts)` — the module-visibility primitive

```
APP.ui.renderModule(container, opts) -> HTMLElement
  opts: {
    minMode: "quick" | "simple" | "professional",   // default "quick"
    id?: string,      // stable module identity for APP.uicheck's cross-mode comparison
                       // (diagnostic only — no CSS rule or runtime behavior depends on
                       // it). Falls back to `label` if omitted. Pass an EXPLICIT `id`
                       // whenever `label` is (or might become) generic/shared UI copy
                       // rather than a unique module name — see the M3 fix note below.
    label?: string,    // the COLLAPSED AFFORDANCE'S visible text (the <summary>).
                        // Falls back to APP.i18n.t("depth." + minMode) if omitted.
    build: function(mountEl) { ... }   // lazy — runs once, the first time the module
                                        // actually becomes visible (already at/above
                                        // minMode, or opened by a click)
  }
```

- If `APP.state.explanationModeAtLeast(opts.minMode)` is true: renders a plain
  `<div class="module-gate module-gate-open">`, calls `opts.build(mount)` immediately,
  and returns it. This is ordinary, always-reachable content — no CSS treats it as a
  distinct "card."
- Otherwise: renders a native `<details class="module-gate module-gate-collapsed">`
  with a `<summary>` (`opts.label`), lazily calling `opts.build` on first open (so a
  collapsed module costs nothing until a reader clicks it). Real keyboard/touch/mouse
  affordance, one click, per PD-0016 Part 1's "nothing becomes unreachable" / P9
  auditability requirement. Styled in `styles/app.css` under `.module-gate*` (HG1 M3
  fix — previously **no rule existed for any of these three classes anywhere in
  `styles/`**; a collapsed module rendered as a bare, unstyled native disclosure
  triangle and underlined link inside its enclosing `.block`'s full card chrome).

**HG1 M3 fix — `label` must not restate the heading already above it.** Confirmed
defect: four Overview modules (`js/surfaces/overview.js`, Blocks B/C/D/E) passed the
SAME string to both the persistent `.block-kicker` header immediately above the gate
AND to `renderModule`'s own `label` — producing an exact-duplicate heading/`<summary>`
pair when collapsed. Fixed by giving these four calls a generic, shared affordance
label (`common.showSectionDetail`, "Show details") instead, while passing the
block's own (still-unique, still-stable) name as `opts.id` explicitly, so
`APP.uicheck`'s cross-mode module-identity tracking is unaffected — only the
**visible** text changed. A module whose collapsed affordance genuinely needs its own
distinct name (e.g. Block A's "Gain / Loss (1Y)" gate, which has no duplicate sibling
heading) is unaffected by this fix and should keep naming itself specifically; the
generic label exists for the "this module's name is already the heading right above
it" case only — don't reach for it by default.

### 17.4 Relationship to PD-0012 §2 / D2 (unchanged)

PD-0012 §2's requirement — all three explanation modes render the same underlying
deterministic fact set; depth may change, the conclusion may not — is about the
GLOBAL `explanationMode` axis this section documents, not the per-card ladder. A module
hidden at Quick and a module shown at Quick are describing the SAME claim objects either
way; `renderModule` only ever decides whether the DOM for a module exists yet, never
which facts back it.

---

<!-- Post-HG1 Checkpoint A correction round 3 (F-3, designer-35): this addendum is
     RELOCATED, verbatim, from its original position (immediately after §17.1, where it
     interrupted §17's own §17.1→17.2→17.3→17.4 sequence) to here — the chronological
     Post-HG1 Checkpoint-A addenda area at the end of the file, immediately before the
     designer-34 addendum that followed it in time. This is a structural relocation of
     preserved historical content, not provenance laundering: wording, content,
     attribution (designer-33), round identity, and historical meaning are unchanged.
     Git will show this as a deletion at the old location and an insertion here; that is
     the expected shape of a pure relocation. No other edit was made to this block. -->

## Post-HG1 Checkpoint A addendum (designer-33, 2026-09-15)

**Authority:** `reviews/gates/POST_HG1_CHECKPOINT_A_STAGE0_BASELINE.md` (Stage-0 baseline
and owner decisions H1–H5, recorded by `pm-01`), `decisions/product/PD-0017-hg1-approved.md`.
Write path: `styles/app.css`, `js/data.js`, `js/selfcheck.js`, `js/surfaces/scenario.js`,
`js/shell.js`, `js/i18n-selfcheck.js`, `index.html`, this file, `README.md`,
`designs/FEATURE_DESIGN.md`. New record, appended here — no round section above this one
is rewritten.

- **D1 — Holdings caveat discoverability.** `styles/app.css`: one narrowly-scoped rule
  (`table.data-table td.num .metric-reason`) restores normal wrapping for a claim's
  sentence-length INSUFFICIENT_DATA/LIMITED reason when it is mounted inside a dense
  table's numeric cell, without touching `td.num`'s own nowrap rule (short numerals/
  fallback labels are unaffected), column widths, the shared `<colgroup>`, or
  `renderMetricValue` itself. Desktop-scoped, wrap-only, per owner decision H2.
- **D2 — Holding-inspector Professional depth.** `js/data.js`: every `HOLDING_CLAIMS`
  entry (both the INSUFFICIENT_DATA branch and the normal branch, including the
  thinlyTraded/LIMITED and UNSUPPORTED_ASSET cases) now carries `professionalDetail` and
  `i18n.zh.professionalDetail`, bounded to position inputs from the holding record, the
  claim's own existing reference basis and sufficiency/reason state, and a truthful
  methodology-availability statement — no FX/currency-conversion content, no new
  analysis, no populated `methodology.unrealizedGainLoss` entry (owner decision H3).
  `js/selfcheck.js` gained three new assertions (data-only boundary, `window.APP.data`),
  each with its own `injectDefect`.
- **D3 — Scenario Lab human-readable machine values.** `js/surfaces/scenario.js` now
  presents a modification's `action` code and any `"<dimension>:<CODE> (<gloss>)"`
  `target` as human-readable bilingual text
  (`presentActionValue`/`presentTargetValue`/`presentModificationLine`, exposed on
  `APP.scenarioPresentation`) while `modifications[]` data (`js/data.js`) stays
  completely untouched; the raw canonical values remain available via
  `data-canonical-action`/`data-canonical-target` on the rendered line. New
  `scenario.action.<CODE>` I18N keys in `js/shell.js` (both locales). `js/shell.js`'s
  `APP.i18n.isAllowlistedCanonical` no longer exempts a live scenario action value from
  the `canonicalEnumToken` pattern (reason-code/ingestion-status keys are unaffected).
  `js/i18n-selfcheck.js` gained two new manual-only regression checks, registered in
  `APP.i18nCheck.run()`. Supersedes the HG1 Round-5 micro-pass judgment that these action
  codes were intended, exempt, visible content — the comments this file, `js/data.js`,
  and `js/shell.js` had recording that judgment are corrected, not deleted.
- **S1 — Active HG1 approval/gate-state claims.** Removed or surgically corrected every
  active present-tense claim that HG1 is unapproved/undecided/blocked
  (`index.html`'s `<title>` and persistent banner; `common.syntheticFooterNote` in both
  locales, `js/shell.js` and `index.html`'s pre-boot fallback, kept in sync;
  `valuationMode.currentNotComputed` in both locales; one `js/shell.js` source comment;
  `README.md`; a new dated status note in this file, above). Every round-scoped/
  historical gate-status statement (Round-3 §, the banner-left-unchanged record, the
  HG1 round-4 addendum's own status line, `CHANGELOG_VISUAL_POLISH.md`'s header, and
  every HG1 scope/round label Stage-0 §5.4 names) is preserved verbatim, unedited.

**Not run by this worker:** any browser, any JavaScript engine, any test runner. Every
change above is hand-traced against the files it edits and the accessors/helpers it
calls, following this file's own established discipline (§14) — not the same as having
loaded the page. See `designer-33`'s final report for the full account.

---

## Post-HG1 Checkpoint A correction round addendum (designer-34, 2026-09-15)

**Authority:** `reviews/gates/POST_HG1_CHECKPOINT_A_PM_VERIFICATION.md` §4 (findings
F1–F7 against `ux_planning` revision 27, `designer-33`), `reviews/gates/
POST_HG1_CHECKPOINT_A_STAGE0_BASELINE.md`. **Scope:** a bounded correction round, limited
to exactly F1–F7 against the `designer-33` round above. No other file, region, data
value, computation, or canonical value was touched; no round section above this one
(including the `designer-33` addendum immediately preceding this one) was edited. Write
path this round: `js/data.js` (only the `HOLDING_CLAIMS` professional-detail
helpers/constants and assignments), `js/selfcheck.js` (only the three
`holding.professionalDetail.*` assertions), `js/shell.js` (only the Chinese value of
`scenario.action.ADD_HYPOTHETICAL_INSTRUMENT`), `designs/FEATURE_DESIGN.md` (the S1
cross-cutting note and the D2 amendment text), this file (this addendum only).

- **F1 (D2, blocking).** `js/data.js`'s `professionalPositionLineEn`/
  `professionalPositionLineZh` no longer characterize a holding's `quantity` as
  "shares"/"股" (the record's `quantity` is unitless, and `2800.HK` is a warrant-linked
  structured note, not an equity share count). Both now render a neutral, ledger-matching
  label: EN "Quantity: `<n>`", ZH "数量:`<n>`", `<n>` interpolated from `h.quantity`.
- **F2 (D3, blocking).** `js/shell.js`'s Chinese value for
  `scenario.action.ADD_HYPOTHETICAL_INSTRUMENT` changed from "添加假设持仓" ("add
  hypothetical HOLDING" — not equivalent to the English "Add hypothetical instrument,"
  and a holding-word inside a scenario-action label sits badly with P8) to "添加假设标的"
  ("add hypothetical instrument/underlying target"), semantically parallel to the
  English value, which is unchanged.
- **F3 (D2).** `js/data.js`'s `PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_ZH` changed
  "逐笔持仓" (reads as per-lot/per-trade) to "单一持仓层面" (per-position), matching the
  English "per-position methodology registry entry" it translates.
- **F4 (D2).**
  (a) Removed the "Measurement basis: …" / "计量基础:…" sentence from
  `professionalDetail`/`i18n.zh.professionalDetail` in every `HOLDING_CLAIMS` branch
  (INSUFFICIENT_DATA, base/available, thinlyTraded/LIMITED) — the claim's own Reference
  line already renders directly above it at Simple and Professional, so restating it a
  second time only duplicated it. The `referencePoint` field itself is untouched.
  (b) `js/data.js`'s `fmtNativeAmount` now mirrors `js/shell.js`'s
  `APP.ui.formatCurrency` OUTPUT FORMAT exactly ("$1,234.56" for USD, "CODE 1,234.56" for
  every other currency), implemented locally (this module still never calls `APP.ui`).
- **F5 (D2, EN).** `js/data.js`'s `professionalPositionLineEn` replaced "listed on
  `<market>`" with "listing market: `<market>`". The Chinese "上市地:`<market>`" wording
  was already correct and is unchanged.
- **F6 (D2 regression).** `js/selfcheck.js`'s
  `holding.professionalDetail.numeralsReconcileWithRecord` now matches quantity as the
  exact labelled fragment "Quantity: `<n>`" (en) / "数量:`<n>`" (zh) rather than a bare
  substring, and reconciles the current price in BOTH `professionalDetail` and
  `i18n.zh.professionalDetail` against the canonical `window.APP.ui.formatCurrency(h.price,
  h.currency)` — a third, independent source, not a second hand-typed copy of the same
  formatting rule `js/data.js`'s own `fmtNativeAmount` implements. `injectDefect` now
  mutates MSFT's quantity to 999999 and price to $1.00 in both `professionalDetail` and
  `i18n.zh.professionalDetail`; hand-traced before=pass, during=fail (both languages,
  both numerals), after=restored — see this worker's final report for the full trace.
  The other two `holding.professionalDetail.*` assertions
  (`presentAndDistinctFromEnglish`, `insufficientDataHasNoPercentage`) were re-read
  against F1/F4/F5 and found unaffected by those changes; left unmodified.
- **F7 (S1 durable record).** `designs/FEATURE_DESIGN.md`'s S1 cross-cutting note no
  longer says a gate's current state belongs in "the workflow's task shards/state." A
  gate's current decision is recorded in the governing decision record (e.g. a
  `decisions/product/PD-*` file); a generic task shard may not represent that decision at
  all — this project's own `pm_acceptance` shard is a known representation gap — so UI
  copy must not mirror either as live gate state.

**Not run by this worker:** any browser, any JavaScript engine, any test runner —
this worker's engagement is `filesystem` only. Every change above is hand-traced against
the files it edits and the accessors/helpers it calls, following this file's own
established discipline (§14) — not the same as having loaded the page. See
`designer-34`'s final report for the full account, including the rendered EN/ZH strings
for `AAPL`, `601318.SS`, `600519.SS`, `2800.HK`, and the new ZH scenario-action label.

---

## Post-HG1 Checkpoint A correction round 3 addendum (designer-35, 2026-09-22)

**Authority:** independent advisory review `review-10` (CLEAR WITH MINOR DEBT against
`ux_planning` revision 29, `designer-34`), findings F-1 through F-3. **Scope:** a bounded
correction round, limited to exactly F-1–F-3. No other file, region, data value,
computation, canonical value, or historical gate-status statement was touched. Write
path this round: `styles/app.css` (one new rule only), `js/data.js` (one string only),
`js/selfcheck.js` (one fixture string only), this file (this addendum, the §17
relocation below, and the current-status pointer near the top).

- **F-1 (D1, LIMITED-qualifier overflow).** `styles/app.css`: one new narrowly-scoped
  rule, `table.data-table td.num .metric-qualifier`, gives the LIMITED-state qualifier
  pill (`.metric-qualifier`, js/shell.js's `renderMetricValue`) `white-space: normal`,
  `overflow-wrap: break-word`, `word-break: normal`, `min-width: 0`, `max-width: 100%` —
  siblings of the round-1 `.metric-reason` fix immediately above it in the file, applied
  to a different element for a different reason. Deliberately NOT `flex-basis: 100%`:
  the qualifier is a compact pill that must stay visually part of the same unit as its
  numeral, not a full-width detached block, so this fix lets it wrap internally and
  shrink to the available space instead of stretching to fill the row. Does not touch
  `td.num`'s own nowrap rule, column widths, the shared `<colgroup>`, sticky-column
  behavior, responsive architecture, or `renderMetricValue` itself; does not shorten,
  truncate, or hide any qualifier text. `js/shell.js` was not touched — the smallest safe
  fix was reachable in CSS alone. See `styles/app.css`'s own comment at this rule for the
  full reasoning. Because this fix makes `designs/FEATURE_DESIGN.md`'s existing D1 claim
  (both LIMITED and INSUFFICIENT_DATA states are covered) true rather than narrowing it,
  `designs/FEATURE_DESIGN.md` itself was not edited.
- **F-2 (canonical ZH sufficiency vocabulary).** `js/data.js`'s and `js/selfcheck.js`'s
  AVAILABLE-branch Professional-detail string changed "充足" to this application's
  canonical AVAILABLE term, "可用" (confirmed against `js/shell.js`'s existing
  `common.limited`/`common.insufficientData` zh values and `js/data.js`'s own
  pre-existing "「可用」"/"「有限」"/"数据不足" methodology prose). Exactly these two
  occurrences existed in the Round 1–2 Professional holding copy; both moved together. A
  bounded check of the rest of the newly introduced Professional holding copy
  (`professionalDetail`/`i18n.zh.professionalDetail` across every `HOLDING_CLAIMS`
  branch) against the confirmed canonical set found no further drift: the LIMITED branch
  already used "有限" and the INSUFFICIENT_DATA branch already used "数据不足" correctly.
  No English meaning, AVAILABLE value, metric state, reason code, or sufficiency logic
  changed.
- **F-3 (CONTRACT.md structure).** Relocated the `designer-33` Post-HG1 Checkpoint A
  addendum, verbatim, from its original position (interrupting §17 between §17.1 and
  §17.2) to the chronological Post-HG1 Checkpoint-A addenda area at the end of this file,
  immediately before this addendum's own immediate predecessor, the `designer-34`
  correction-round addendum — so the addenda now read designer-33 → designer-34 →
  (this addendum) in chronological order, and §17 reads contiguously
  (§17 → §17.1 → §17.2 → §17.3 → §17.4). A comment at the relocated block's new location
  states explicitly that this is a structural relocation of preserved historical content,
  not provenance laundering. `designer-33`'s wording, content, attribution, round
  identity, and historical meaning are unedited; no path/pointer inside that block needed
  contextualizing, since it contains no relative reference that the relocation affected.
  `designer-34`'s own phrase "the `designer-33` addendum immediately preceding this one"
  was FALSE before this relocation (designer-33's addendum was mid-§17, not immediately
  preceding designer-34's) and is TRUE after it; confirmed directly rather than assumed,
  and left unedited per instruction. Also replaced this file's near-top current-status
  pointer (previously naming one specific designer's addendum as being "at the end,"
  which was already wrong before this round and would have become fragile again after
  any future round) with durable wording that names the addenda area, not any one
  round's addendum, as the pointer target. Every round-scoped/historical gate-status
  statement elsewhere in this file (Round-3 §, the HG1 round-4 addendum's own status
  line, `CHANGELOG_VISUAL_POLISH.md`'s header, and every HG1 scope/round label named
  elsewhere) is unedited.

**Not run by this worker:** any browser, any JavaScript engine, any test runner — this
worker's engagement is `filesystem` only, and no `browser` capability reached this
dispatch. F-1's containment reasoning (that the new `.metric-qualifier` rule keeps the
pill inside its cell without detaching it from its numeral) is static analysis of the CSS
cascade, the flex-item sizing algorithm (`min-width: auto` vs. `min-width: 0`, shrink-to-
fit under `flex-wrap: wrap`), and CJK/Latin line-breaking rules — not a rendered
observation; the page was never loaded, at any width, in any browser. F-2's and F-3's
edits are hand-traced string/structure comparisons against the confirmed canonical
vocabulary and the file's own section headings, not a mechanical diff or test run. See
this worker's final report (to `pm-01`) for the complete account of what was and was not
verified.
