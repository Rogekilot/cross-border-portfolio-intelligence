# Direction B — "Analyst Desk"

**Author:** `designer`, worker `designer-06`, HG1 revision cycle 01, 2026-09-04
**Provenance:** `reviews/gates/HG1_REVISION_CYCLE_01.md` §4 (this file's authorization; no
task shard, no execution record, no handoff — see that file for why)
**Status:** one of three independent, cold-started direction packages for human selection.
**Does not select. Does not recommend itself.** `designer-08` writes the comparison; the
human owner decides.
**Sole write path used:** `designs/hg1-revision/direction-b/` (this file and `mockup.html`)

---

## 0. Thesis, in one sentence

The product is an institutional analytics workbench: visualization is the primary
communication mechanism, not text with charts beside it, and the interaction model is
**focus an object, read its resolution in a persistent inspector** — not "click a card,
read a paragraph, click back."

Everything below is argued honestly, including where this thesis is a poor fit. Direction
B is not a hedge; it is a specific bet, and §7 states the bet's cost in full.

---

## 1. IA / navigation map

### 1.1 Primary navigation — four surfaces, workbench framed

| Slot | Surface | What it is |
|---|---|---|
| 1 | **Overview** | Command center. Landing surface. |
| 2 | **Portfolio** | Holdings + Exposure, unified as one inspectable object graph. |
| 3 | **Analytics** | Performance + Risk & Analytics, unified as one chart-led surface. |
| 4 | **Scenario Lab** | Structurally isolated — its own visual shell (§5, §D1.7/P8). |

That is the entire top-level tab bar: four items, plus a persistent command bar (not a
nav item — see §4) and a persistent inspector dock (not a nav item — see §3.2). Nothing
else competes for primary attention.

### 1.2 Secondary / contextual navigation

- **Command bar** (top-anchored, always visible, keyboard-focusable from anywhere,
  `/` to focus): the entry point for AI Analyst as a query interface (§4) and also a
  fast object-jump ("go to Tencent," "go to Beta") — because in a focus-and-inspect
  model, *getting to* an object is as load-bearing as *reading* it.
- **Inspector dock** (right-docked panel, persistent chrome, collapsible not closable —
  it can shrink to a rail with just the focused object's name, never fully vanish while
  something is focused): resolves whatever is currently focused — a chart series, a
  holding row, a metric card, a region of a chart. This is where Insights, Methodology,
  Evidence, and AI answer cards all land. It is described fully in §3.2 and §5.
- **Transactions**: a tab inside Portfolio, not a primary destination — Portfolio's own
  local nav is Holdings / Exposure / Transactions, each a filtered view over the same
  object graph rather than a separate app section.
- **Portfolio Settings / Policy**: an icon-only affordance in the top chrome (gear icon,
  adjacent to the command bar, not inside primary nav), opening as an overlay panel, per
  the owner's instruction 2 ("Settings/Policy outside primary navigation").
- **Methodology & Evidence**: has no top-level nav entry. It is reached exclusively by
  focusing a claim and reading the inspector's Methodology tab (§5). There is one
  exception, stated plainly: a small "Registry" deep-link lives inside the inspector's
  own chrome for a reader who wants to browse methodology entries directly rather than
  arrive at one via a claim — this exists because §33's registry is legitimately
  browsable reference material, not only a per-claim destination, and hiding it entirely
  behind claims would make it undiscoverable to a reader who wants to audit the method
  before trusting any specific number. It is not a primary tab; it is a link inside a
  secondary surface.
- **AI Analyst as a destination**: does not exist as a tab. See §4 for why, and for what
  replaces "a page you go to."

### 1.3 All eleven D1 surfaces, placed explicitly

| # | D1 surface | Where it lives in Direction B | Why |
|---|---|---|---|
| 1 | Overview | Primary surface 1 | Command center, per objective 1. |
| 2 | Holdings | Tab inside **Portfolio** | Same object graph as Exposure; a focused holding drives the same inspector. |
| 3 | Performance | Tab inside **Analytics**, default tab | Performance chart is Analytics' primary chart; see §3. |
| 4 | Exposure | Tab inside **Portfolio** | Allocation is a property of what you hold, not a separate department. |
| 5 | Risk & Analytics | Tab inside **Analytics** | Beta, Sharpe, drawdown, correlation share Analytics' chart-and-inspect model with Performance; they are the same kind of object (a metric with a method), not a different kind of surface. |
| 6 | Insights | **Not a tab. A stream inside the inspector**, plus a compact severity-ranked rail on Overview (objective 1 requires "top portfolio insights" on Overview at a glance). Full severity-grouped list is one inspector tab away ("All Insights") from any surface, not a separate destination. | Insights are properties of the objects they're about (a position, a metric, the portfolio total) — attaching them to the inspector keeps them next to what they explain instead of stranding them in their own list divorced from the chart that would make them legible. |
| 7 | Scenario Lab | Primary surface 4, isolated shell | Per P8 — see §5.4. |
| 8 | AI Analyst | **Not a destination. The command bar + inspector answer cards.** | See §4. |
| 9 | Transactions | Sub-tab inside **Portfolio** | Ledger input, adjacent to what it produces. |
| 10 | Portfolio Settings / Policy | Gear-icon overlay, outside primary nav | Per objective 2's explicit instruction. |
| 11 | Methodology & Evidence | Inspector's Methodology/Evidence tab, reached from any claim; browsable via a "Registry" link inside the inspector | Per D4 — the affordance follows the claim; a standing destination would fragment exactly what objective 5 asks to keep contextual. |

Every surface is accounted for: four are primary tabs, three are sub-tabs of Portfolio,
two live inside the inspector rather than as destinations, one is chrome (Settings), one
(Methodology & Evidence) is inspector-reached with one deliberate secondary deep-link.
Nothing is dropped; several are relocated, per the owner's explicit license to relocate.

### 1.3.1 The inspector is not a twelfth surface

It is worth naming precisely, because it does a great deal of IA work: the inspector is
not a page and not a modal. It is docked chrome, always present in some state (empty,
collapsed-rail, or resolving a focused object), that renders **the same claim object**
(per D2.2) at whatever depth the user has set, with tabs for **Value / Explain / Why? /
Evidence / Methodology** when the focused object is a claim, or **Insights / Answer**
when the focused object is a portfolio-wide context rather than one claim. This is the
literal mechanism for objective 4's progressive-disclosure ladder: visual/conclusion is
on the canvas (the chart or card itself), and everything from "key number" through
"methodology" is inspector depth levels on the same panel, not five different pages.

---

## 2. Representative Overview screen

**Composition, top to bottom / left to right (see `mockup.html` for the rendered
version):**

1. **Top chrome**: logo mark, four-item primary nav, command bar (center-anchored,
   wide, always visible), freshness summary pill (top-right, per-axis detail on
   hover/focus — see §5.5), gear icon (Settings/Policy), profile.
2. **Hero row (full width, ~55% of viewport height)**: a single dominant SVG chart —
   **portfolio cumulative return vs. benchmark (MSCI ACWI), 1-year, indexed to 100** —
   with real axis ticks (dates on x, indexed value on y), a shaded drawdown band beneath
   the line pair, a period selector (1M/3M/6M/1Y/3Y/ALL) as chart-native segmented
   control (not a separate settings row), and the portfolio line rendered noticeably
   heavier/higher-contrast than the benchmark line, which is dashed — establishing at a
   glance which line is "you." This is the objective-1 "portfolio vs benchmark
   performance visualization," made literally the largest thing on the screen, not one
   card among several.
3. **Metric strip, directly beneath the hero chart, tightly coupled to it (not a
   separate card grid further down the page)**: five compact stat cells sharing one
   horizontal rule with the chart above — Total Value (reporting currency, USD) with its
   freshness pill inline; Period Return; vs. Benchmark (the delta, signed); Sharpe
   (Investor-depth number, click focuses it in the inspector); Beta (same). Each cell is
   focusable — clicking any one highlights the corresponding chart annotation if
   relevant and opens it in the inspector at Quick depth by default. This strip is the
   literal "key number" rung of the progressive-disclosure ladder sitting directly under
   the "visual/conclusion" rung above it — the two rungs are adjacent on the canvas, not
   separated by scrolling.
4. **Three-column row below the fold**: **Top Holdings** (5 largest positions,
   compact bars sized by weight, expandable inline to the full Holdings tab),
   **Allocation** (a small compact donut — asset class — with a "view full exposure"
   focus-link, since Exposure's dual listing/economic-geography view per §D1 item 1
   needs more room than a donut can honestly give it, and objective 3 explicitly warns
   against decorative charts: a donut earns its place here only as a *summary*
   entry-point, not as the place the listing-vs-economic distinction gets made),
   **Risk Snapshot** (3 core metrics: Volatility, Max Drawdown, VaR — each with metric
   state per §D3.2, each focusable).
5. **Insights rail**, full width, beneath the three-column row: severity-ranked,
   top-3 shown (Warning first per §20.1), each a single line with a severity glyph and
   judgment-class tag, each focusable — clicking opens the full insight (claim +
   reference point + caveat + D4 control) in the inspector, never inline-expanding the
   row itself, which is the mechanism that keeps Overview's persistent text density low
   per objective 5.
6. **AI Portfolio Brief entry**, compact, docked at the bottom of the Insights rail
   rather than as its own separate card block — a single generated summary line plus a
   "Ask about this" affordance that focuses the command bar. This is deliberately
   subordinate chrome, not a chat window on the page — see §4 for why.
7. **Freshness footer strip**: per-axis summary (US equity / HK equity / CN equity /
   USD-HKD FX / USD-CNY FX), least-fresh-first, per D5.4 — never collapsed to one
   timestamp.

**What answers the owner's four fixed Overview questions, explicitly:**
*How am I doing?* — hero chart + metric strip, first thing seen.
*Why?* — the metric strip's Sharpe/Beta cells plus the Insights rail's top item, one
focus-click from an inspector explanation.
*What is driving the portfolio?* — Top Holdings + Allocation columns, immediately below
the fold, no scroll past one screen height on a standard laptop viewport.
*What deserves my attention?* — Insights rail, severity-ordered, impossible to miss
because it sits directly under the three-column row rather than requiring navigation to
a separate Insights destination.

---

## 3. Representative Portfolio/Analytics screen

I built **Analytics** (Performance + Risk & Analytics unified) as the second screen,
because it is the surface that most directly tests the thesis: can a chart-first,
inspector-driven model carry the density of a professional risk surface without
regressing to a wall of numbers?

### 3.1 Composition

1. **Local sub-nav**: Performance | Risk | (Correlation as a Risk sub-tab). Mockup
   renders Performance, the default tab.
2. **Primary chart, large, ~45% of viewport height**: cumulative return, portfolio vs.
   benchmark, same visual grammar as Overview's hero chart (consistency is deliberate —
   a reader should recognize "this is the same kind of object at greater depth," which
   is literally D2's model applied to chart composition, not just to text) — but here
   with an added **FX-attribution split band** beneath it (local-currency return vs.
   FX-attributed return, stacked area, per §D1 Performance item 2 — "the product's
   differentiated claim... belongs near the top, not buried"). This is the chart that
   earns the added complexity: FX attribution is exactly the kind of thing objective 3
   says charts should exist for, because a paragraph cannot show two overlapping
   contributions to one number nearly as legibly as a stacked band can.
3. **Metric card grid, beneath the chart**: Core V1 metrics (Volatility, Beta, Sharpe,
   Sortino, Max Drawdown, Tracking Error) as a dense 3x2 grid of compact cards, each
   showing its Quick-depth conclusion by default with the numeric value visible (this is
   Investor-depth-as-default per Analytics' professional character, distinct from
   Overview's Quick default — a deliberate, stated difference: the workbench assumes a
   returning analyst, not a first glance). Each card is focusable; focusing opens the
   full D2 ladder in the inspector.
4. **SML/CAPM scatter**, smaller, beside the metric grid: portfolio and benchmark
   plotted on a security-market-line scatter, beta on x, return on y — directly
   answering objective 3's named example, and chosen specifically because it is the one
   visualization in the owner's list that a text description genuinely cannot replace
   (a scatter position relative to a line is a spatial relationship).
5. **Correlation strip**: a compact cluster-summary strip (not the full matrix by
   default, per §18.2's own four-step ladder and D2's Professional-only default for the
   full matrix) with a "view full matrix" focus-link that opens the complete heatmap in
   the inspector at Professional depth.

### 3.2 The inspector, shown resolving a focused object (Beta card)

The mockup's inspector panel, docked right, shows Beta focused at **Investor** depth:
value (1.30), reference point (benchmark: MSCI ACWI, 3Y weekly), a depth selector
(Quick/Simple/Investor/Professional pills), the caveat slot (always present, per D2.2,
non-empty here: "3-year weekly sample, 156 observations"), and an Evidence/Methodology
tab beneath. Switching the depth pill re-renders the same object's fields per D2.2 — the
mockup shows this as a static illustration of Investor depth with the other three pills
visibly present and inert (documented as non-interactive in the mockup — see §"what is
and is not interactive" below), because building a full four-state re-render is
implementation, not a representative mockup.

---

## 4. AI interaction concept

**AI Analyst is not a page. It is the command bar, plus answer cards that land in the
inspector.**

This is the direction's most aggressive bet on the "gets out of the way" instruction.
Concretely:

- The command bar (§1.2) accepts a typed or (mocked, non-functional) voice query —
  "How did FX affect my return this year?", "What's my HK exposure?", "Explain the
  Tencent beta."
- A query returns a **compact answer card** docked into the inspector, not a growing
  chat transcript taking over a page. The card's prose is short (Simple-depth by
  default) and **every numerical claim in it is a citation chip**, matching the accepted
  baseline's P1 mechanism (`designs/hg1-prototype/`'s AI Analyst pattern, which this
  direction keeps as the *mechanism* while rejecting the *chat-page* container it lived
  in there). Clicking a chip re-focuses the inspector on the underlying claim object —
  the same Value/Evidence/Methodology tabs a chart-focused claim would show. This is the
  literal, visible statement of P1: **the AI's answer card has no numbers of its own; it
  only has chips that point at objects the deterministic engine already rendered
  elsewhere on the canvas.** If the AI needs to state a number that has no
  corresponding on-canvas object yet, the chip still resolves to a tool-call output in
  the inspector's Evidence tab (§22.2/§22.8's audit record) — it never resolves to
  "the AI typed this."
- There is no persistent chat history rail. A prior answer card can be recalled from a
  small "recent" affordance in the command bar's dropdown, but the workbench does not
  reserve permanent screen real estate for a conversation log, because the thesis is
  that the charts and inspector *are* the persistent surface, and AI is a temporary
  overlay on top of them, not a parallel destination competing for the same attention
  budget.
- **Portfolio Brief** (Overview's required entry, objective 1) is the one place AI
  prose is pre-rendered rather than query-invoked — a single always-visible generated
  paragraph, itself carrying citation chips, docked at the bottom of the Insights rail.
  This is a deliberate exception to "AI only on invocation": the owner's objective 1
  explicitly requires the brief to be visible on Overview without navigating away, so it
  cannot be invoke-only there.
- **Scenario Lab and AI**: when the command bar is focused while Scenario Lab is the
  active primary surface, any answer card the AI returns about scenario output is
  rendered with the same non-dismissible `SCENARIO` badge and border treatment the
  Scenario Lab canvas itself uses (§5.4) — the inspector does not get a P8 exemption
  just because it is shared chrome across surfaces.

**Where P1 is visibly held, stated plainly for the owner's benefit:** every number the
AI's answer card shows is a chip, never plain text; a chip's only two possible
destinations are (a) an existing on-canvas claim object it points at, and (b) a
tool-call output shown in the inspector's Evidence tab. There is no third path by which
the answer card can display a number with no resolvable source. The mockup renders one
answer card with two chips, one of each kind, to make this concrete rather than
asserted.

---

## 5. Evidence / methodology interaction

**The inspector is the evidence path, not a popover.** This is the direction's other
major bet, and it directly implements §D4.1–D4.4: the affordance is not summoned per
number and dismissed after reading — it is a standing panel that already exists, and
focusing a claim is *the same act* as opening its evidence, at whatever depth the panel
is currently set to.

### 5.1 The path, concretely, traced once (mirroring D4.3's own trace)

1. Analytics surface renders the Beta card (a claim, per D2.2).
2. User clicks/focuses the card (a single action — not "click," then "find the evidence
   button," then "click that too").
3. The inspector resolves to that claim, at whatever depth the panel was last set to
   (session default, per D2.1.3) — Investor, say.
4. The inspector's own **Evidence** and **Methodology** tabs are one click deeper within
   the same panel, not a navigation to a different page — this is the literal
   implementation of D4.2's "reachable at every depth level," because the same docked
   panel is present at Quick depth too; only its content differs.
5. Methodology tab shows the registry entry's structural fields per §33 (empty content
   in this mockup, per the accepted baseline — the registry ships empty until CP1+, and
   the mockup renders the "not yet published" state explicitly rather than fabricating
   entries).
6. For a generated Insight or AI claim, the same panel instead shows the Proof Packet
   fields (§21) — same mechanism, different destination content, exactly as D4.1
   specifies.

### 5.2 Why a docked panel rather than a popover, argued

A popover is dismissed by design — that is what makes it a popover. This direction's bet
is that evidence access should have zero marginal cost once one claim's evidence is
already open: moving focus from Beta to Sharpe should not require re-opening a control,
because the inspector is already there, already at the right tab if the user stays on
Methodology while moving between claims. This is a genuine interaction-cost reduction
over a per-number popover model, and it is also the direction's most surface-hungry
choice — see §7's weaknesses.

### 5.3 Metric-state rendering under this visual language (§D3.2)

The mockup's Holdings tab (visible via the Portfolio primary surface, not separately
screenshotted per the two-screen limit, but present in the mockup file) shows:

- An `AVAILABLE` + `STALE_DATA` position (a US-listed holding priced end-of-day) —
  numerals styled identically to plain `AVAILABLE`, distinguished only by the freshness
  pill, per §D3.2's explicit rule.
- A `LIMITED` position (a thinly-traded HK-listed holding) — value plus a
  non-dismissible qualifier chip in the same visual unit as the number, never a
  tooltip-only footnote.
- An `INSUFFICIENT_DATA` position (a recently-added Mainland China A-share with no cost
  basis on file) — no numeral at all, an explicit "— insufficient data" text state with
  reason code, typographically distinct component (not a number-shaped field with
  substituted text).

All three carry the workbench's dense, monospace-numeral, high-information visual
language, but the `INSUFFICIENT_DATA` row uses a visibly different cell shape (no
right-aligned numeral column at all — the text state spans where the numeral would sit)
so it cannot be skimmed as a number even at a glance, addressing the P-1 em-dash finding
directly: this direction does not use a bare em-dash anywhere as a numeric placeholder;
`INSUFFICIENT_DATA` cells use the words "insufficient data," never a dash alone, and
ordinary "no value in this column" cells (e.g., an N/A quantity field) use a distinct
lighter-weight center-dot glyph instead of an em-dash, precisely to avoid the collision
the owner's P-1 finding flagged in the rejected prototype.

### 5.4 Scenario Lab isolation (P8)

Scenario Lab is not a tab of Portfolio or Analytics — it is its own primary surface with
a **structurally different chrome**: a persistent, full-width amber-bordered header band
reading "HYPOTHETICAL — SCENARIO ANALYSIS, NOT YOUR ACTUAL PORTFOLIO" that cannot be
dismissed or scrolled past (it is fixed, not sticky-on-scroll — it never leaves the
viewport while Scenario Lab is active), a two-column ACTUAL | SCENARIO comparison layout
where the ACTUAL column reuses Portfolio/Analytics' normal visual language exactly and
the SCENARIO column uses a distinct desaturated-amber card treatment throughout,
including inside the inspector when a Scenario-column claim is focused (§5.3 of D1's own
Scenario Lab text, carried through here). The inspector's badge for a `SCENARIO`-typed
claim is the same non-dismissible marker at every depth, per the cross-cutting P8
mechanism.

### 5.5 Freshness (D5)

Per-axis, never merged: the top-chrome freshness pill on every primary surface expands
(on click, into the inspector) to the full per-axis table (US equity / HK equity / CN
equity / USD-HKD FX / USD-CNY FX), each independently stated, least-fresh-first — never
a single "as of" timestamp. The mockup's Overview footer strip renders this expanded
form directly rather than requiring the click, since Overview is the one surface where
objective 1 requires freshness visible without navigating anywhere.

---

## 6. Strengths

1. **Progressive disclosure is structurally enforced, not just documented.** Because
   Quick/Simple/Investor/Professional are literally rendering modes of one docked panel
   rather than four different page templates, it is hard to build a version of this UI
   that *accidentally* skips a depth level for one claim but not another — the component
   is shared by construction, which is a stronger guarantee than a style-guide
   convention four different card templates would need to independently honor.
2. **Evidence access has near-zero marginal cost**, once any claim is open. This is a
   genuine, measurable interaction-design win for exactly the audience (advanced/
   Professional-depth readers, and any reader auditing multiple metrics in one session)
   the accepted P9 architecture cares most about.
3. **Visualization genuinely carries meaning, not decoration.** The FX-attribution
   stacked band and the SML scatter are both chosen because a sentence cannot do what
   they do — this satisfies objective 3's explicit warning against decorative charts by
   being selective, not by being maximal.
4. **AI is structurally prevented from feeling like the primary interface**, which
   directly serves success criterion 7 (AI must never become the de facto source of
   facts) — because it has no home page of its own to accumulate authority in the user's
   mental model; it is always visibly a query over the same canvas the user is already
   looking at.
5. **Consistent object model across surfaces.** The same "focus → inspector resolves"
   gesture works identically whether the object is a chart series, a holding row, a
   metric card, or an AI citation chip — one interaction grammar to learn, not one per
   surface.

## 7. Weaknesses — real ones

1. **This is an analyst's tool, and it will underserve a first-time or casual user.**
   Success criterion 1 asks whether a first-time user can understand portfolio status
   "primarily from Overview." Overview here is genuinely strong on that criterion. But
   the *rest* of the product assumes a user willing to click to focus, read a docked
   panel, and hold state about what's currently focused in their head — that is exactly
   the "institutional analytics workbench" register the thesis asks for, and it is a
   real cost for a retail-leaning or occasional user who wants the answer to just be on
   the page, not one interaction away. I am not going to soften this: a workbench
   optimized for a returning analyst is not the friendliest design for someone opening
   the product twice a year.
2. **The inspector is a scarce, shared resource, and only one thing can be focused at a
   time.** Comparing two metrics side by side (e.g., "is Beta or Volatility more
   affected by this period?") requires either memorizing the first before focusing the
   second, or a compare mode this direction does not specify. A dashboard-of-cards model
   (Direction A-shaped, by the naming convention, though I have not read it) would let a
   user's eyes do that comparison for free; this direction trades that off for
   evidence-access efficiency.
3. **Density risk on smaller viewports.** The dominant hero chart plus a tightly coupled
   metric strip plus a three-column row plus an Insights rail is a lot of vertical
   content for one "single glance" surface on anything narrower than a wide desktop
   monitor; the mockup is authored at a ~1440px reference width and I have not designed
   or tested a narrower breakpoint. This is a real, unresolved gap, not a hedge.
4. **The command-bar-as-AI-entry model asks users to know what to ask.** A destination
   page (a chat tab) has a lower activation cost for a user who does not yet know a
   query is possible — a visible "type a question" affordance helps, and the mockup
   includes one, but a command palette is a familiar pattern to power users and a less
   familiar one to a first-time retail-adjacent user, which compounds weakness 1 rather
   than offsetting it.
5. **Hand-authored SVG charts do not scale to arbitrary real data without real
   engineering investment.** The mockup's charts are hand-plotted synthetic points; a
   production version needs an actual charting approach (library or generated SVG from a
   data pipeline) with real axis-scaling logic, which is a bigger engineering lift than
   a simpler direction's charts would require. This is a named implication for §8, not
   just a mockup-authoring note.
6. **The reduced-primary-nav model (four tabs) still creates a real sub-navigation
   burden inside Portfolio and Analytics** — Holdings/Exposure/Transactions inside one
   tab, Performance/Risk/Correlation inside another. Objective 2 is satisfied at the
   *primary* nav level, honestly, but the owner should not read "four tabs" as "four
   places to look" — it is four places to look plus meaningful sub-navigation within two
   of them, and I am naming that rather than letting "four primary surfaces" imply
   simplicity the full IA does not fully deliver.

## 8. Implications for the validated CP0 design

Nothing here proposes to change what `designs/FEATURE_DESIGN.md` asserts; everything
below is a *re-expression* of an already-decided structure, listed because the owner's
deliverable 8 asks for it explicitly.

- **D2.2's shared claim object gains a natural physical home.** D2's four-level depth
  model was specified as a per-claim rendering contract with no assumed container; this
  direction gives it one (the inspector panel). This does not change D2.2's fields
  (conclusion, reference point, caveat, methodology pointer) — it proposes where they
  render, which was explicitly out of CP0's scope ("no visual design").
- **D4.1's "single, consistently-placed control attached to every claim-bearing
  element"** would be re-expressed, if this direction is selected, as "focusing the
  element" rather than "a separate button next to it" — i.e., the *element itself* is
  the control, and the inspector opens on focus rather than on an adjacent icon click.
  This is a stronger reading of D4.2's reachability requirement (the control is not just
  present at every depth, it is the same gesture as viewing the claim at all), not a
  weaker one, but it is a materially different interaction pattern than "a small icon
  next to each number," which is what most readers of D4.1's text would likely picture.
  Worth the owner's attention specifically because it is a bigger interaction commitment
  than the CP0 text implies on its own.
- **D1's per-surface "information hierarchy" lists** (Overview items 1–9, Performance
  items 1–4, etc.) would need re-numbering to match this direction's actual layout
  (e.g., Overview's item ordering here interleaves the metric strip and hero chart
  rather than a strict linear list) — the *content* named in each list is unchanged and
  fully present; only the enumerated order/grouping would need updating to match a real
  layout instead of a linear spec list.
- **D1's surface count language** ("the eleven surfaces") would need a companion note
  that the *navigable* surface count and the *specified* surface count now diverge on
  purpose (four primary + sub-tabs + inspector-hosted, per §1.3's table) — D1 itself
  does not mandate one tab per surface, but a reader moving from D1 straight to
  implementation could reasonably assume that mapping, and this direction is the
  concrete evidence that assumption does not hold.
- **The Methodology & Evidence surface (D1 surface 11)'s "not yet published" empty state
  (§D1 item 3, §D4.3 step 5)** needs no change in *meaning* but would render inside the
  inspector's Methodology tab rather than as a standalone page — the mockup shows this
  exact state for the Beta card's methodology entry.

## 9. Genuine contradiction discovered

**None found.** I looked specifically at three candidate friction points before
concluding this:

- Whether an inspector-as-single-shared-panel could violate D2.1.2's "depth is a
  per-claim reader preference, not a global page mode" — it does not, because the
  inspector's depth setting applies only to whatever is *currently* focused; two claims
  are never forced to share a depth state simultaneously, they are just not
  *simultaneously visible* (which is §7 weakness 2, an interaction-design cost, not a
  contract violation — D2.1.2 constrains what happens when a claim is shown, not how
  many can be shown at once).
- Whether collapsing AI Analyst from a destination page into command-bar-plus-cards
  could weaken §22.7's "this surface" language for explanation depth — it does not,
  because §22.7 specifies depth *behavior* (the same four levels, user-selectable per
  turn), and the answer card still offers that; "surface" in the CP0 document is not
  used in a way that requires a dedicated page, only a place the behavior is exposed.
- Whether the inspector rendering both `ACTUAL` and `SCENARIO` claims (as shared chrome
  across primary surfaces) could create exactly the P8 back door D1's own Scenario Lab
  section warns about for evidence views — I resolved this by design (§5.4: the
  inspector inherits the SCENARIO badge/border treatment identically to the canvas, with
  no exemption), not by discovering an unresolvable conflict; recorded here because it
  was the closest candidate to a real contradiction and is worth the owner knowing I
  checked it specifically rather than missing it.

No baseline contract needed reopening to make this direction cohere.

---

## 10. Success criteria — stated against this direction

| # | Criterion | Assessment |
|---|---|---|
| 1 | Understand portfolio status primarily from Overview | **Met.** Hero chart + metric strip + three-column row + Insights rail all fit one screen at the reference width (§7 risk 3 notwithstanding on narrower viewports). |
| 2 | Compare portfolio vs. benchmark visually without opening another section | **Met, strongly.** This is Overview's largest single element by design. |
| 3 | Identify biggest holdings/exposures/risks quickly | **Met.** Top Holdings, Allocation, and Risk Snapshot are all in the three-column row, one screen down. |
| 4 | Understand what requires attention without long paragraphs | **Met.** Insights rail is one line per item with severity glyphs; full text is one focus-click into the inspector, never inline on Overview. |
| 5 | Access explanation, evidence, methodology when desired | **Met, and this is the direction's strongest claim** — see §5's marginal-cost argument. At risk only insofar as a user must learn the focus gesture at all (§7 weakness 4's activation-cost point). |
| 6 | Clearly distinguish actual vs. Scenario Lab | **Met.** Structural chrome difference (§5.4), not a dismissible banner, extended into the shared inspector rather than exempted from it. |
| 7 | Use AI without it becoming the source of facts | **Met.** Citation-chip mechanism is unchanged from the accepted baseline's proven pattern; the command-bar container makes it structurally *harder*, not easier, for AI prose to feel authoritative, since it never occupies a persistent full-page chat surface. |

---

## What I did not do

I did not read `designs/hg1-revision/direction-a/` or `direction-c/` — independence was
the instruction, and I have not looked. I did not extend or reuse code from
`designs/hg1-prototype/`; I re-derived this direction's mockup from the D1–D5 contract
directly, reusing only the *mechanism* the prototype already proved out for P1 citation
chips (named explicitly in §4) because that mechanism belongs to the accepted baseline,
not to the rejected prototype's layout.
