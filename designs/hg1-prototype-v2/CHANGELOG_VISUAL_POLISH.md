# Change log — visual-polish pass (Checkpoint A, all sub-passes)

**HG1 status: `REVISION_REQUIRED`, not approved.** This log accompanies one revised
prototype returned per `reviews/PM_ACCEPTANCE.md` §3's "Required immediate next action."
It is a reviewer's aid, not a transcript — concise per the owner's own word. Full detail
for any item lives in `CONTRACT.md`'s addenda (chronological, each headed by its pass and
worker) or this worker's own handoff.

Three workers built this across four sub-passes: `designer-15` (chart families,
typography, holdings alignment, semantic color), `designer-16` (per-chart
interpretability), and `designer-17` (rolling-analytics grammar, account tables, this
log). Nothing below was executed in a browser by any of them — `pm-01` verified
Checkpoint A passes 1–2 directly; this pass's three items are new and **not yet
browser-verified** — see this worker's handoff for the precise list.

## Chart dimensions and the family system

A shared `chart-family-*` class (`js/charts.js`'s `familyClass()`) is now attached to
every chart, capping its own max-width at roughly its authored size — `styles/
tokens.css`'s `--chart-*-max-width` tokens. This is the actual fix for "charts get huge
for no reason" and "chart labels are disproportionately large": an SVG's `width:100%`
was stretching to fill an oversized card, and because chart type lives in the same
viewBox coordinate space as everything else in the SVG, the stretch was scaling text up
with it (most visibly, a 320-unit bar chart filling a ~900px Overview card).

Seven families existed after Checkpoint A: hero, analytical, compact, donut, bar,
scatter, matrix. This pass adds an eighth, **rolling** (`chart-family-rolling`), splitting
the rolling-volatility and drawdown charts out of `analytical` (still used by the
local/FX attribution stacked bar, a different kind of chart) into their own identity — see
"Rolling-analytics grammar" below.

## Visualization typography

Nine named `--type-*` role tokens (`styles/tokens.css`): page heading, card title, metric
number, chart axis, chart category label, chart value label, annotation, table cell,
secondary metadata. Every chart text class in `styles/app.css` resolves to one of these;
`js/charts.js` itself sets no font sizes — it only assigns class names, so the chart
"library" cannot invent its own type scale independently of the design system.

## Holdings and account table grids

**Holdings** (Checkpoint A): numeric `<th>`s now carry the same `.num` (right-align,
tabular-nums) class as their `<td>`s — previously every header was left-aligned
regardless of its column's own alignment. A missing avg-cost (in-kind transfer) renders
as a short right-aligned placeholder with the explanation moved to a `title` attribute,
instead of a full sentence breaking the column's rhythm.

**Holdings — Unrealized G/L, fixed (this pass, found in `pm-01`'s browser pass on the
first cut of this pass).** This is the one numeric column built from a claim (via
`APP.ui.renderMetricValue`'s directional ▲/▼ glyph + numeral path, Condition 2) rather
than a plain formatted string, and it disagreed with its own header: the `<td>` carried
no class at all (`text-align: start`, `font-variant-numeric: normal`) while its header
correctly said `.num`. Fixed by routing this cell through a new shared local
constructor, `claimNumCell(ctx, claim)` (`js/surfaces/portfolio.js`), instead of a
one-off class added at the single call site, so any future claim-rendered numeric
column in this ledger is built the same way rather than repeating the omission. The
glyph and numeral did not need to be visually separated to land in the strict
right-aligned track — `renderMetricValue`'s own wrap is a single inline unit with the
numeral trailing, so it lands flush right regardless of the glyph's width, same as
every other right-aligned cell here. A related, second defect surfaced by the same
inspection — a table-mounted claim's numeral was rendering at `--type-metric-number`
(this build's largest numeral size, meant for stat cards), visibly out of scale with
the plain `--type-table-cell`-sized numerals beside it in the same row — is fixed with
one scoped rule (`table.data-table .metric-number` in `styles/app.css`), which also
brings Transactions' rare claim-rendered conversion figure back to the table's own
scale.

**Holdings — cross-account column drift, fixed (this pass, found in `pm-01`'s second
browser pass, after the G/L fix above verified clean).** Every account's holdings render
as a separate `<table>`, and a browser's default table-layout sizes each table's columns
from its own content only — so although every column now aligned perfectly *within* each
account's table, the four tables did not share the same track widths as each other (a
measured 17px spread on the G/L column's right edge between the widest and narrowest
account section). Fixed with a shared `<colgroup>` (`HOLDINGS_COLS`' new `width`
percentages, `holdingsColgroup()` in `js/surfaces/portfolio.js`) plus `table-layout:
fixed` on a new scoped class, `.holdings-ledger-table` (`styles/app.css`) — applied only
to these per-account ledger tables, not to Accounts & Cash or Transactions (single
tables with different column counts that never had this cross-table problem). Every
account's table — one holding or five, US/HK/CN listing — now resolves to the identical
column widths, so the grid lines up continuously down the page, not just within each
account's own section.

**Holdings — Freshness/column-width rebalance (this pass, found in `pm-01`'s third
browser pass).** The width percentages that fixed the cross-table drift above cost the
Freshness column its own fit: `table-layout: fixed` overrides content width, and
Freshness's original 10% (95px) was 27px narrower than its own freshness pill (114px)
needed, so the pill visibly spilled into the Actions column (overflow was `visible`, so
nothing was clipped or hidden — no P10 breach — but two columns visually overlapped,
which is a worse defect than the cross-table variance this colgroup exists to remove).
**Rebalanced, not reverted:** Freshness gains 3.5 points (10 → 13.5), taken from two
columns checked against this build's own actual data rather than assumed safe —
Quantity (-1: every quantity in the dataset is ≤4 digits) and Market Value in USD
(-2.5: the largest of all 13 holdings' computed values, VOO's $43,545.50, is always
USD-prefixed and 10 characters, with clear margin at the new width). Avg Cost, Price,
and % of Portfolio — also short/right-aligned, and named as candidate donors — were
deliberately left untouched: their own worst-case values include a currency-code prefix
for non-USD holdings (e.g. "CNY 1,542.00" for Price) that already runs closer to the
column's width, so shrinking them further was judged the higher-risk move. Security was
checked against its own longest value ("iShares 20+ Year Treasury Bond ETF") and left
unchanged because it wraps by design rather than forcing an unbroken run past its
column. Unrealized G/L was left unchanged because it was the column already
independently browser-verified correct in the prior follow-up.

**Holdings — second rebalance, sizing against the wrong worst case (this pass, found in
`pm-01`'s fourth browser pass).** The first rebalance above took overflowing cells from
14 to 4 and held the shared right edge across all four tables — but the remaining 4
cells were a WORST-CASE SELECTION mistake, not an arithmetic one: Freshness (13.5%,
~128px) was sized against this dataset's two *healthy*-state pills ("US equity · Live,"
"HK equity · EOD"), not its real worst case, "CN A-share · Stale" at 140px — the only
stale axis and the longest label, because a degraded state adds words a healthy one
doesn't need. Unrealized G/L (12%, ~114px) was sized against a plain directional
numeral, not this column's own worst case: the `INSUFFICIENT_DATA` row (Kweichow
Moutai, `600519.SS`), whose cell carries the "insufficient data" label plus its reason
text — structurally wider than any numeral, by D3.2's own design. **Lesson recorded in
`CONTRACT.md` for the next person sizing a column like this:** in a cross-border,
multi-freshness-axis product, the widest freshness/state value will tend to be the
degraded case, not the healthy one — size against the worst state actually present in
the data, not the one that comes to mind first. Fixed by widening both against their
real worst case with a deliberate margin (Freshness 13.5 → 16, Unrealized G/L 12 → 16),
taking the full amount from Security (22 → 15.5) — the one column established twice now
as structurally immune to this failure (wraps by design). Qty, Avg Cost, Price, Market
Value, and % of Portfolio are untouched — none were reported as still short.

**Accounts & Cash** (this pass — round 3 said *"holdings/account tables"*; only Holdings
had received the fix). Same pattern: an `ACCOUNTS_COLS` array marks the Cash Balance(s)
column numeric, so its header and cells are now right-aligned with tabular numerals
through the same `formatCurrency` convention every other monetary figure in this build
uses — checked specifically against the owner's named risk case, a multi-currency
account (`acct-cash-1`, holding USD/HKD/CNY cash simultaneously): it now renders through
the identical five-column structure as every single-currency account, with no structural
drift. An account with no cash on file gets the same right-aligned cell, reusing Holdings'
existing "short italic placeholder, never a bare em-dash" convention rather than a
left-aligned sentence.

**Documented different row type:** `acct-cash-1` has cash but zero holdings, so its
section on the Holdings surface (a different surface from Accounts & Cash) is a title +
cash summary line with no ledger table at all — there is nothing to tabulate. This is a
deliberate consequence of the account's actual contents, not an inconsistency; recorded
in `CONTRACT.md` per the owner's instruction to name any row type that legitimately
differs, the same way the earlier pass documented Overview's condensed holdings table
versus Portfolio's full ledger.

**Transactions:** checked, left substantially as-is. Quantity/Price-Amount were already
right-aligned with tabular numerals. The Reporting-Currency Conversion column is
deliberately excluded from the strict numeric grid — it is prose for all but one
transaction, with a single claim-shaped exception — right-aligning one numeral inside an
otherwise-narrative column would not improve scannability; recorded as a considered
decision in `CONTRACT.md`.

## Semantic color

`--color-positive`/`--color-negative` now exist and apply only to claims `js/data.js`
marks `directional: true` (return, P&L, benchmark-relative, FX attribution, alpha,
per-holding gain/loss) — a deliberately short list; risk/ratio characteristics and
SCENARIO-side figures never carry this. Portfolio-vs-benchmark stays teal-vs-gray, not
green-vs-red, everywhere (the benchmark is a reference, not a negative outcome). The
correlation heatmap's positive/negative cells moved off the same teal/red pair used for
portfolio/warning (a correlation sign is not a financial verdict) to a neutral
gold/slate-blue diverging pair. Stale-but-available data no longer shares its exact color
with a policy-breach warning. Non-color encoding accompanies every color-only distinction:
the benchmark line stays dashed where portfolio is solid, directional numerals carry an
`aria-hidden` ▲/▼ glyph alongside their explicit sign, and every SML/scatter group also
carries its own text label.

## Per-chart interpretability improvements

- **Hero chart** (portfolio-vs-benchmark, Overview + Analytics): direct end labels with
  each series' period return, a persistent relative-performance callout, and a hover
  crosshair with a per-date readout — all computed from the same arrays already drawn.
- **SML/CAPM**: explicit axis titles (beta / historical annualized return), a
  window/frequency subtitle, a legend naming portfolio/benchmark/sleeve and the Security
  Market Line, and historical Jensen alpha drawn as a labeled vertical distance from the
  portfolio's point to the line — replacing the chart's own summary field, which
  previously just said "See scatter."
- **Exposure**: one shared horizontal-bar convention (percent-of-portfolio, then dollar)
  now used by both Overview's and Analytics' country/currency/sector/asset-class bars,
  which previously showed the two figures inconsistently (dollar-only vs. percent-only)
  for the identical segment shape.
- **Risk contribution**: a new paired-bar primitive shows capital weight against
  contribution to portfolio risk per segment, instead of two isolated figures a reader
  had to reconcile by eye; the one segment withheld for insufficient data still shows its
  real capital weight with no fabricated risk-contribution bar.
- **Correlation**: a plain-language conclusion naming the strongest/weakest pairwise
  relationship in the same matrix already fetched, each figure inside a provenance chip.
- **Drawdown**: gained a benchmark reference line, an explicit trough marker + label, and
  (this pass) the shared rolling-family grammar below.

## Rolling-analytics grammar (this pass — new in round 3)

The rolling-volatility chart and the underwater drawdown chart previously read as two
unrelated charts that happened to sit side by side. Both now share one frame in
`js/charts.js`: identical margins and total plot height; identical x-axis tick cadence;
a new shared y-axis gridline+percent-tick treatment (drawdown previously had none); a
window/frequency subtitle in the same class, position, and phrasing convention as the SML
scatter's own ("Trailing 1Y · Daily returns..."); a legend in the same position on both
(rolling-volatility previously had none); and a generalized hover crosshair + readout box
matching the hero chart's interaction model. The rolling-volatility chart is reused
unchanged (same primitive, same new grammar) on Overview's risk snapshot, so the
consistency extends beyond Analytics to everywhere this chart type appears. A new
dedicated `chart-family-rolling` gives this pair its own identity separate from the
general "analytical" family.

## What was deliberately NOT changed, and why

- **Drawdown shading on the hero chart** was removed, not added back, in Checkpoint A —
  a considered judgment, not an oversight. The owner's own condition was a hedge ("use
  drawdown shading only if it improves interpretation"). Bundling a portfolio-only
  drawdown band into the hero chart would mix two y-axes (cumulative index vs. drawdown
  percent) competing with the single question that chart exists to answer ("who's
  ahead"); the dedicated underwater chart already answers "how deep did it fall" on its
  own axis, and this pass strengthens that chart further rather than duplicating its job
  inside the hero. The parameter (`showDrawdown`) remains functional in `charts.js` for a
  future caller who judges differently.
- **`metric.performanceAttribution`** (a composite pre-formatted string, "Local X / FX
  Y") was not marked `directional` for coloring — coloring parts of a pre-formatted
  string safely was judged out of proportion to the pass that considered it; flagged for
  whoever next touches that claim.
- **The Reporting-Currency Conversion column** on Transactions was left out of the
  strict right-aligned numeric grid (see above) — it is prose, not a magnitude column.
- **The correlation heatmap itself** (Professional-depth, inside the inspector) was not
  changed this pass; only the plain-language conclusion beside it (added in Checkpoint A)
  and its embedding in the Analytics surface were touched.
- **Holdings sections for cash-only accounts** were left without a ledger table (see
  "Documented different row type" above) rather than given an empty table shell — there
  is nothing to tabulate, and an empty table would be a fabricated structure, not a
  genuine one.

## What was and was not verified

**Not executed in any browser or JS runtime** by this worker (`designer-17`) — no such
environment exists in this sandbox; every change in this pass was hand-traced (brace/
paren balance, cross-file reference lookup against actual function signatures) but not
rendered. Checkpoint A's prior two passes (chart families/typography/holdings alignment/
semantic color; per-chart interpretability) **were** verified by `pm-01` in a real
browser, per `reviews/PM_ACCEPTANCE.md` §4, and this pass's first two items — the
rolling-analytics grammar and the Accounts & Cash table — have now **also** been
browser-verified by `pm-01`: both rolling charts render at an identical `viewBox`
(`0 0 640 224`) and rendered size, both carry gridlines/percent ticks and the same
window-label phrasing, and the Accounts & Cash table's multi-currency row renders
right-aligned with tabular numerals structurally identical to single-currency rows.
Zero console errors and zero em-dash-only text nodes were confirmed on every route.

The Unrealized G/L cell-construction fix and its accompanying `table.data-table
.metric-number` font-size correction were **also** subsequently browser-verified by
`pm-01`: all 13 ledger rows render the cell with `class="num"`, right-aligned, tabular
numerals, at the same 13px scale as the rest of the row, and the `INSUFFICIENT_DATA`
case (Kweichow Moutai, `600519.SS`) renders "insufficient data" in the same cell
structure with no bare em-dash. Zero console errors.

The cross-account column-grid fix (shared `<colgroup>` + `table-layout: fixed` on
`.holdings-ledger-table`) was **also** subsequently browser-verified by `pm-01`: the
Unrealized G/L column resolves to one right edge (1010px) across all 13 rows in all 4
account tables, where it previously stepped between 978/991/993/995px. Zero console
errors. That same verification pass found the predicted trade-off had materialized —
`table-layout: fixed` overriding content width had left the Freshness column 27px too
narrow for its own pill, which spilled visibly into the Actions column (`overflow:
visible`, so nothing was clipped or hidden — no P10 breach — but a visible column
overlap).

That first rebalance (Freshness 10 → 13.5, Qty 7 → 6, Market Value 13 → 10.5) was
**also** subsequently browser-verified by `pm-01`, partially: overflowing cells went
from 14 to 4, and the single shared right edge held (977px) across all four tables and
all 13 rows. Zero console errors. The Qty/Market Value donor analysis was confirmed
sound. The remaining 4 cells were a worst-case-selection mistake in the width TARGET
chosen for Freshness and Unrealized G/L (see the second rebalance entry above), not a
flaw in the donor reasoning itself.

**Not yet browser-verified:** the second rebalance (Freshness 13.5 → 16, Unrealized
G/L 12 → 16, Security 22 → 15.5) made in response to that finding. `pm-01`'s stated test
is unchanged and is the whole bar: no cell's `scrollWidth` exceeds its `clientWidth` in
any of the four tables, while the single shared right edge is preserved. If this is
still insufficient, this file's next entry should record whichever specific cell still
overflows and by how much, the same way the last two rounds did, rather than assuming
the reasoning above was correct.
