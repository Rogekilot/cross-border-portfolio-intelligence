# Direction A — "Command Deck"

**HG1 revision cycle 01** (`reviews/gates/HG1_REVISION_CYCLE_01.md`) — one of three
independent, materially-different UX/IA directions produced for human selection.
**Not** a complete implementation; **not** an approval of anything; HG1 remains
`awaiting_human` throughout.

**Author:** `designer`, worker `designer-05`, 2026-09-04, cold-started against this
direction's assigned thesis only, without reading sibling directions B or C.
**Sole write path used:** `designs/hg1-revision/direction-a/`.
**Inputs:** `reviews/gates/HG1_REVISION_CYCLE_01.md`, `designs/FEATURE_DESIGN.md` (all of
D1–D5 plus cross-cutting P8 mechanism and known limitations), `specs/FEATURE_PRD.md`,
`reviews/gates/HG1_PROTOTYPE_INSPECTION.md`, and a structural read of the rejected
`designs/hg1-prototype/` (not extended, not reused).

**What is not reopened.** Financial contracts, the three-state metric-sufficiency model
(`AVAILABLE`/`LIMITED`/`INSUFFICIENT_DATA`) and its six reason codes, the deterministic/AI
boundary (P1), the Proof Packet/evidence architecture (P9), scenario isolation (P8),
AI-grounding, the freshness contract (P10), and caveat preservation (P3) are treated as
fixed. This document only re-expresses *how* they are presented.

---

## Thesis, in one sentence

A single command deck the user rarely leaves: the whole portfolio state presented at
once, at disciplined density, with depth reached in place (expanding tiles, anchored
popovers, slide-over panels) rather than by navigating away — because navigating away is
the failure mode this direction is designed to eliminate.

---

## 1. IA / navigation map

**Primary navigation — four tabs**, matching the owner's example directly:

`Overview` (home/default) · `Portfolio` · `Analytics` · `Scenario Lab`

**Persistent, non-tab zone:** a docked AI rail, always visible on the right edge of every
primary surface — not a fifth tab, because tab semantics imply "somewhere else you go,"
and the entire thesis is that the AI stays exactly where the deck is.

**Reached outside primary navigation:**
- Settings/Policy — gear icon, top-right of the shell, opens a slide-over over the deck.
- Methodology & Evidence — no nav entry at all; reached exclusively through an inline
  evidence popover anchored to the specific number, whose footer link opens a deeper
  slide-over for full registry/Proof-Packet content.
- Insights — no nav entry; a bell icon in the top bar opens the full severity-grouped
  list as a slide-over; the Overview deck also carries a "Top Insights" tile with the top
  three, and any tile whose underlying claim has an active insight carries an inline
  severity badge wherever that tile lives.

**All eleven `designs/FEATURE_DESIGN.md` §D1 surfaces, placed explicitly:**

| # | D1 surface | Placement | Where, exactly |
|---|---|---|---|
| 1 | Overview | **Primary** | The command deck itself — default landing tab |
| 2 | Holdings | Secondary, nested in `Portfolio` tab; summarized on the deck | "Key Holdings" tile on Overview (top positions, expands in place to the full position table); full ledger view lives under `Portfolio` |
| 3 | Performance | Secondary, nested in `Portfolio` tab; summarized on the deck | "Performance vs Benchmark" tile on Overview; full return decomposition (local vs FX-attributed) under `Portfolio` |
| 4 | Exposure | Secondary, nested in `Analytics` tab; summarized on the deck | "Allocation & Exposure" tile on Overview (top-level only, per §D1's own rule); full listing-vs-economic-geography toggle, sector/currency/asset-class breakdown, and concentration summary under `Analytics` — **built out in this mockup** |
| 5 | Risk & Analytics | Secondary, nested in `Analytics` tab; summarized on the deck | "Risk Snapshot" tile on Overview; full metric cards, SML/CAPM, correlation heatmap, contribution-to-risk under `Analytics` — **built out in this mockup** |
| 6 | Insights | **Contextual**, no primary nav entry | "Top Insights" tile on Overview (severity-ordered, top 3); inline severity badges on any affected tile wherever it lives; bell icon → full list slide-over |
| 7 | Scenario Lab | **Primary** (4th tab) | Own tab, permanently distinct visual language (never the deck's tile grammar). Not built out in this mockup, per the owner's explicit instruction not to fully implement all three directions — shell/nav presence only |
| 8 | AI Analyst | **Primary**, but rail-form, not tab-form | Docked persistent rail alongside every primary surface; an "expand to full conversation" affordance is described, not built, since the rail already carries the representative content |
| 9 | Transactions | Secondary, nested under `Portfolio` tab | A segmented control inside `Portfolio` ("Holdings / Performance / Transactions"), or a "View transactions" affordance from an expanded position row |
| 10 | Portfolio Settings/Policy | **Outside primary navigation** | Gear icon, top-right → slide-over panel over the deck — **built out in this mockup** |
| 11 | Methodology & Evidence | **Contextual only**, no nav entry | Exclusively via an evidence popover's "Open full methodology" link → slide-over deep panel — **built out in this mockup**, content representative since the registry ships empty per §D1 surface 11 |

This is a placement map, not a scope change: every surface D1 names still exists;
nothing is dropped, only relocated, exactly as the cycle's boundary requires.

---

## 2. Representative Overview screen (rendered in `mockup.html`, `#screen-overview`)

A 12-column tile grid to the left of the AI rail. Top of the deck carries a compact,
per-axis freshness strip (never a single blended "as of" label, per §D5.1) and identifies
the least-fresh axis in use.

**Tiles, in the order the owner's objective 1 lists them:**

1. **Total Value** (hero tile) — total portfolio value in reporting currency, gain/loss
   with its period stated, evidence popover on each. Rendered `AVAILABLE` + `STALE_DATA`
   — identical numerals to plain `AVAILABLE`, distinguished only by the adjacent
   freshness pill, per §D3.2's dedicated row.
2. **Performance vs Benchmark** — cumulative line chart, portfolio vs. MSCI ACWI, with a
   period selector.
3. **Key Holdings** — top positions by weight, sorted, each row showing market value,
   % of portfolio, and (where sufficient) cost basis/unrealized gain/loss. One row
   (Kweichow Moutai, `600519.SS`) renders `INSUFFICIENT_DATA` for cost basis — no
   numeral, explicit reason code (`MISSING_COST_BASIS`). Expands in place (native
   disclosure) to the full position table without navigating to `Portfolio`.
4. **Allocation & Exposure** — top-level donut (asset class) + geography bar, evidence
   popover, "full breakdown on Analytics" affordance.
5. **Risk Snapshot** — Beta, Volatility, Sharpe, Max Drawdown as compact metric cards;
   Beta carries its `LIMITED` qualifier inline (short sample window); Max Drawdown
   carries `AVAILABLE`+`STALE_DATA`.
6. **Top Insights** — three severity-tagged items (Warning/Attention/Observation), each
   with an evidence affordance.
7. **AI Portfolio Brief** — the top card of the persistent rail, not a duplicate tile —
   see §4 below for why this satisfies the objective without re-rendering the same
   narrative twice.
8. **"Ask Your Portfolio"** — a contextual quick-prompt row inside the rail, always
   present beneath the Brief.
9. **Freshness disclosure** — the top-of-deck strip described above, plus each tile's own
   local freshness/evidence marks.

## 3. Representative Analytics screen (rendered in `mockup.html`, `#screen-analytics`)

Chosen over Portfolio because it best stress-tests this thesis: the highest density of
genuinely load-bearing visualizations (§D1 Exposure + Risk & Analytics), and the surface
where "in-place depth" has the most work to do.

**Tiles:**

1. **Exposure** — a CSS-radio toggle (no JavaScript) switching between **listing-market**
   and **economic-geography** views of the same stacked bar, so the two are never
   presented as one merged number (§D1 Exposure item 1's explicit rule). The toggle makes
   the difference vivid: Tencent and Alibaba are Hong-Kong-*listed* but China-*domiciled*
   megacaps, so Mainland-China economic exposure is materially larger than Mainland-China
   *listing* exposure once the toggle flips — a concrete instance of the rule the PRD
   names abstractly (US-listed ADR of a China company is not "US exposure").
2. **Concentration** — top position, top-5, HHI, effective N, quick-conclusion first.
3. **Risk metrics** — Volatility, Sharpe, Sortino (`AVAILABLE`), Max Drawdown
   (`AVAILABLE`+`STALE_DATA`), Tracking Error (`INSUFFICIENT_DATA`, reason
   `MISSING_BENCHMARK`), and **Beta with the full Quick→Simple→Investor→Professional
   depth ladder built out** (CSS-radio tabs, one metric, chosen as the canonical worked
   example already specified in §D2.3 of `designs/FEATURE_DESIGN.md`) — the `LIMITED`
   qualifier is present and worded consistently at all four levels, per §D3.3's
   depth-invariance rule.
4. **SML/CAPM positioning** — hand-authored SVG scatter, portfolio and benchmark plotted
   against the security-market line.
5. **Correlation heatmap** — a 5×5 cluster of core holdings, one cell carrying `LIMITED`
   (Moutai's short price history), evidence popover on that cell specifically.
6. **Contribution to risk** — horizontal bar chart per holding.

Every metric on this screen carries an evidence popover; Beta's is wired to the full
Quick→Popover→Methodology-slide-over path end to end (§5), the one fully traced example
this document provides, mirroring how `designs/FEATURE_DESIGN.md` §D4.3 traces one
surface fully rather than asserting the pattern eleven times.

---

## 4. AI interaction concept

**Placement.** A docked rail, fixed width, right edge, present and identical in
structure on every primary surface (Overview and Analytics both show it in the mockup).
It is not a modal, not a separate destination, and never closes — that permanence is the
thesis's central bet on AI treatment.

**Content, top to bottom:** (a) the AI Portfolio Brief as the first message in the
thread — this is how objective 1's "AI Portfolio Brief" requirement is met without a
duplicate Overview tile re-rendering the same narrative a second time in a different
box; (b) a row of contextual quick-prompts that change with whichever tile is currently
expanded (described, not dynamically wired, since that is state management out of this
mockup's scope); (c) a conversation thread below.

**How P1 is held, visibly.** Every numerical assertion in AI prose is rendered as a
citation chip — an inline `<details>` element identical in mechanism to the evidence
popovers used everywhere else on the deck, not a separate AI-specific affordance. Plain
descriptive language ("your top holdings") stays plain text; a falsifiable number or
named claim about the portfolio ("up **+8.4%** year-to-date," "**NVDA (16.8%)**") is
always a chip. A `LIMITED` metric quoted inside AI prose (Beta, in the mockup) keeps its
qualifier — the caveat survives translation into conversational language, per P3, because
the chip opens the *same* claim object the Analytics tile's card renders, not a
re-derived AI-generated number.

**How P8 is held in the rail.** Because the rail is spatially adjacent to Overview's
`ACTUAL`-only tiles, this is the one place in this thesis where a reader could plausibly
conflate rail content with deck content if the two surfaces shared visual grammar. They
do not: any AI message that grounds itself in a hypothetical (the mockup includes one
example — a user asking "what if I sold half my Tencent position") renders with a
persistent, non-dismissible `SCENARIO PREVIEW` badge in a structurally distinct color
from the rail's normal `ACTUAL`-grounded messages, plus an explicit redirect to build the
scenario out properly in `Scenario Lab`. This is the same `state_type: ACTUAL |
SCENARIO` mechanism `designs/FEATURE_DESIGN.md`'s cross-cutting P8 section already
specifies for AI Analyst — re-expressed here as a rail-message treatment rather than a
full-page one, not a new mechanism.

---

## 5. Evidence / methodology interaction

The shortest path of the three directions, by construction: **evidence lives at the
number, not behind a destination.**

1. Every claim-bearing value carries a small inline evidence glyph immediately adjacent
   to it (never a separate row, never Professional-depth-only, per §D4.2's reachability
   requirement).
2. Activating it opens an anchored popover, in place, over the deck — no navigation, no
   page change, the deck stays exactly where it was. The popover shows: the claim's
   conclusion recap, its reference point (P4), its current D3/D5 state, and a compressed
   methodology summary.
3. The popover's footer carries "Open full methodology →," which opens a right-edge
   slide-over — the deck remains visible and scrolled to the same position behind it —
   showing the full methodology-registry fields (§33) or Proof Packet (§21) fields,
   exactly per D4.1's two destination types. This is the one path this mockup builds end
   to end (Beta, on the Analytics screen).
4. Because the registry ships empty in this increment (`implement`'s I3), the slide-over
   in the mockup renders the "not yet published" state D1's Methodology & Evidence
   section requires, rather than fabricated content.

**A deliberate anti-ambiguity choice.** The prior rejected prototype's own inspection
record (`reviews/gates/HG1_PROTOTYPE_INSPECTION.md`, finding P-1) flagged that a bare
em-dash used as a generic "no value" placeholder elsewhere on a page can visually
collide with the em-dash inside an `INSUFFICIENT_DATA` render. This mockup avoids the
ambiguity outright: nowhere does it use a bare dash as a blank-cell placeholder for
anything; `INSUFFICIENT_DATA` cells always pair explicit text and a reason code, and
every other "nothing here" case uses a written word, not a dash.

---

## 6. Strengths

- **Fewer actions to reach any single high-priority fact.** Nearly everything objective
  1 lists sits on one screen; there is no "go check Risk & Analytics, then come back"
  loop for the common case.
- **AI stays in context by construction**, not by a "recently viewed" heuristic — because
  it is spatially co-resident with the deck the user is already looking at, a quick-prompt
  can reference whatever is currently expanded without any extra machinery to track "what
  the user was looking at."
- **The shortest evidence path of any plausible direction.** One click, anchored,
  in place. Because friction to check a claim is minimal, this direction structurally
  raises the odds a P9-conscious user actually does check it, rather than merely
  providing the path.
- **Cross-market freshness is naturally well-served by density**, not fought by it — a
  single top-of-deck strip can show all axes (US/HK/China equities, both FX pairs)
  simultaneously without the disclosure feeling buried, which is exactly what §D5.1
  requires and what a page-per-surface layout would need a dedicated widget for.
- **Depth is genuinely per-claim, not per-page**, matching §D2.1 precisely: a
  Professional-depth reader can go deep on one Beta card while every other tile on the
  same screen stays at Quick — no mode switch, no separate "advanced view."

## 7. Weaknesses — real ones

- **Density directly threatens success criterion 4** ("understand what requires
  attention without reading long paragraphs"). A deck with eight-plus simultaneous tiles
  risks becoming a wall of numbers — the same "visually sparse, fragmented" complaint the
  owner made about the rejected prototype, in a denser disguise, if typographic hierarchy
  and severity-coded visual weight are not executed with real discipline. A static
  mockup can only partially demonstrate that this hierarchy actually reads correctly to a
  first-time eye; it cannot prove it the way a usability session would.
- **In-place expansion causes reflow, which has its own disorientation cost.** Expanding
  one tile pushes the tiles below it down the page; collapsing it later requires the user
  to re-find their place. This thesis relocates the "getting lost" risk from navigation
  to scroll position — it does not eliminate it.
- **The persistent AI rail is expensive real estate**, permanently consuming roughly a
  quarter to a third of horizontal width on every surface. On a narrower laptop viewport
  this forces an uncomfortable choice: shrink the deck (undermining the density argument
  that is the thesis's whole point) or make the rail collapsible (which breaks "always
  visible, always co-resident," the thesis's other central claim). This mockup does not
  resolve that tension; it assumes a wide desktop canvas throughout.
- **This thesis is a weaker fit for a genuine first-time user than its "at a glance"
  framing suggests.** A reader who has never seen the product before, presented with
  eight simultaneous tiles, must build their own scan order; there is no sequencing to
  lean on. A narrative-first or guided direction would do more of that work for them.
  This is a direct, structural tension with objective 1 for exactly the audience that
  objective is written for, not a cosmetic concern.
- **The "shorter path" argument partially breaks down for the heaviest audit use case.**
  A Professional-depth reader auditing several related claims in sequence (say, three
  risk metrics in a row) opens and closes several popovers and slide-overs in turn — this
  is not meaningfully fewer interactions than a dedicated methodology destination page
  would have required for the same task, even though any single lookup is faster.
- **No responsive/narrow-viewport treatment.** Nothing in the owner's instruction
  requires one, but a dense multi-column grid with a fixed-width persistent rail is an
  explicitly desktop-canvas thesis; it is not clear this direction degrades gracefully,
  and this document does not attempt to show that it does.

## 8. Implications for the validated CP0 design

Re-expressions only — nothing here proposes changing what any surface asserts.

- `designs/FEATURE_DESIGN.md` §D1's per-surface "information hierarchy" lists (numbered,
  top-to-bottom item lists for Overview, Holdings, etc.) would need re-expression as
  **tile compositions within a grid** rather than vertical page sections — same content,
  same order of primacy, different spatial arrangement.
- §D2.1's "one control per claim... cycles Quick → Simple → Investor → Professional"
  needs re-expression for the tile idiom: the control becomes the tile's own
  expand-in-place affordance plus the evidence popover's "Open full methodology" link,
  rather than an accordion control on a dedicated page.
- §D4.1's "single, consistently-placed control attached to every claim-bearing element"
  is honored exactly as specified; only its rendering form is re-expressed, as an
  anchored inline popover rather than, e.g., a link to a separate destination page.
- §D1's implicit "primary surface" framing (eleven surfaces, several described as
  top-level) needs re-expression to match the four-tab model in §1 above, with Insights,
  Methodology & Evidence, Transactions, and Settings/Policy re-expressed as
  contextual/secondary — this changes how "primary" is operationalized in the nav model
  only, consistent with the owner's objective 2 being explicitly directional ("for
  example," not mandatory), and does not remove or rename any of the eleven surfaces
  themselves.
- §D5.2's "freshness indicator required next to the value it qualifies... portfolio-level
  summary of per-axis states" is re-expressed as the persistent top-of-deck strip,
  always visible, rather than a summary line living at the bottom of a page.
- **Nothing in §D3** (the metric-state rendering rules table) needs re-expression. The
  rules bind regardless of layout, and this mockup renders them unchanged — `AVAILABLE`,
  `AVAILABLE`+`STALE_DATA`, `LIMITED`, and `INSUFFICIENT_DATA` all appear exactly per
  §D3.2's table.

## 9. Genuine contradiction discovered

**None found**, after specifically checking the one candidate this thesis raises on its
own: does placing the AI rail spatially adjacent to Overview's tiles put pressure on
`designs/FEATURE_DESIGN.md`'s cross-cutting P8 rule that "Overview and Holdings render
`ACTUAL` claims exclusively... there is no code path by which a Scenario Lab result
reaches those two surfaces"? It does not. The rule is scoped to *rendering surfaces
(components)*, and the AI rail is its own component — the same "AI Analyst" surface
(§D1, surface 8) that the source document already permits to render both `ACTUAL` and
`SCENARIO` claims with distinguishing treatment — merely docked next to Overview rather
than reached by navigating to it. A `SCENARIO`-tagged AI message appearing in the rail
while every Overview tile beside it stays `ACTUAL`-only is exactly what the existing
mechanism describes as acceptable, not a violation of it. No other candidate
contradiction was found in the course of this redesign.

---

## Success criteria — how this direction meets each, or where it is at risk

| # | Criterion | Assessment |
|---|---|---|
| 1 | Understand overall status primarily from Overview | **Met, this thesis's strongest fit** — the deck is designed as exactly one glance covering objective 1's full list. |
| 2 | Compare portfolio vs. benchmark visually without opening another section | **Met** — the Performance vs Benchmark chart is a first-class Overview tile, not a link elsewhere. |
| 3 | Identify biggest holdings/exposures/risks quickly | **Met** — Key Holdings, Allocation & Exposure, and Risk Snapshot tiles are simultaneously visible and each sorted/ranked. |
| 4 | Understand what requires attention without long paragraphs | **At risk** — see Weaknesses. This is the criterion density most directly threatens if visual hierarchy execution is not disciplined; the mockup demonstrates the intent (severity-coded Insights tile, badges) but cannot prove it holds up for a genuine first-time reader. |
| 5 | Access explanation, evidence, methodology when desired | **Met, strongest fit of the three named dimensions** — the inline-anchored-popover path is the shortest reachable path to provenance by construction. |
| 6 | Clearly distinguish actual vs. Scenario Lab | **Met, structurally** — separate tab, permanently distinct visual language, and the rail's `SCENARIO PREVIEW` badge mechanism, though Scenario Lab itself is not built out in this mockup (documented, not demonstrated at full depth), per instruction. |
| 7 | Use AI without AI prose becoming the source of fact | **Met** — citation-chip mechanism is the identical D4 popover pattern reused, not an AI-specific shortcut; grounding is visible, not asserted. |

---

## What I did and did not verify

I authored `mockup.html` with **zero JavaScript by deliberate design**, specifically
because I have no JavaScript runtime or browser in this sandbox to hand-verify script
correctness, and the harness requires me to say plainly what I did not test rather than
claim an unperformed verification. All interactivity (holdings expand-in-place, evidence
popovers, the Beta depth ladder, the Exposure listing/economic toggle, the Settings and
Methodology slide-overs) is implemented with native `<details>`/`<summary>` and the CSS
radio/checkbox-plus-sibling-selector techniques, deliberately avoiding any dependency on
`:has()` or other very-recent CSS for broader compatibility. **I did not load or render
this file in a browser** — that is not available to me. I hand-checked tag closure,
`id`/`for`/`name` pairing for every radio group and checkbox-drawer, and selector syntax,
but a hand check is not a substitute for rendering it, and I am stating that plainly
rather than implying otherwise.
