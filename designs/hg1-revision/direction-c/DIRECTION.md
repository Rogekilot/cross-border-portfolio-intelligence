# Direction C — "Briefing Room"

**HG1 revision cycle 01 — direction package, one of three.** Authored cold and
independently by `designer-07` per assignment in `reviews/gates/HG1_REVISION_CYCLE_01.md`.
Sole write path: `designs/hg1-revision/direction-c/`. This package proposes a direction; it
does not select one, does not implement CP1, and does not reopen any item in that file's §3
accepted baseline. HG1 remains `awaiting_human`, unmoved by this work.

**Status:** design proposal for human selection, paired with `mockup.html` (rendered, not
browser-verified — see "Verification" at the end).

---

## Thesis, in one sentence

Overview is not a dashboard of everything; it is a small, ranked stack of large briefing
blocks — one per owner question — each leading with a plain-language conclusion and holding
everything else, including its own AI narrative, behind a disclosure ladder that starts
closed by default.

---

## 1. IA / navigation map

**Primary navigation — four surfaces, radio-tab style, always visible:**

| Primary tab | Contains |
|---|---|
| **Briefing** (home) | The Overview redesign — five ranked blocks, described in §2 |
| **Portfolio** | Secondary tabs: Holdings · Performance · Exposure · Transactions |
| **Analytics** | Risk & Analytics in full: volatility, beta, correlation/cluster, concentration & contribution-to-risk — each rendered as a conclusion-first block, described in §3 |
| **Scenario Lab** | Full surface 7, structurally isolated (see §4/P8 note below) |

**Not in primary navigation, reached contextually:**

- **AI Analyst** — a persistent "Ask" affordance docked in the global header on every
  primary surface except Scenario Lab's isolated view (see below); opens a slide-over
  conversation panel. Never a tab, because a tab implies a destination you navigate *to*;
  this direction wants AI reachable *from* wherever you already are.
- **Insights** — integrated into the Briefing's "Attention" block (top 1–2 severity items
  inline) with a "See all insights" expansion inside that same block that renders the full
  severity-grouped list surface 6 owns — a secondary view, not a tab, opened in place, not
  navigated away to.
- **Methodology & Evidence** — reached only from an Evidence control attached to a claim;
  never a menu item, because there is no scenario in this direction where a user opens it
  without a claim already in hand.
- **Portfolio Settings / Policy** — behind the account/gear icon in the header, outside all
  four primary tabs, per the owner's explicit instruction.

**All eleven D1 surfaces, placed:**

| # | D1 surface | Where it goes in Direction C |
|---|---|---|
| 1 | Overview | Primary surface, renamed "Briefing" in this direction's own vocabulary (same surface, same §26 content requirements — see §7 implications) |
| 2 | Holdings | Secondary tab under Portfolio; also a scoped drill-through target from Briefing's Block A "expandable key holdings" panel |
| 3 | Performance | Secondary tab under Portfolio; Briefing Block A is the same headline-return claim rendered at Quick depth (D1's own claim-object-inheritance argument, unchanged by this direction) |
| 4 | Exposure | Secondary tab under Portfolio; Briefing Block B is the Quick-depth rendering of the same allocation/exposure claims |
| 5 | Risk & Analytics | Primary surface "Analytics" in full; Briefing Block C is the Quick-depth risk snapshot, same underlying claims |
| 6 | Insights | Contextual — integrated into Briefing's Attention block, with "See all insights" as its full-list secondary view (not a tab) |
| 7 | Scenario Lab | Primary surface, structurally isolated (§4) |
| 8 | AI Analyst | Persistent header affordance + slide-over panel, not a tab; Briefing's AI Portfolio Brief block is its condensed, always-visible face |
| 9 | Transactions | Secondary tab under Portfolio |
| 10 | Portfolio Settings / Policy | Account/gear menu, outside primary nav |
| 11 | Methodology & Evidence | Contextual only, reached via every Evidence control; also a small persistent footer link for direct access |

Nothing is dropped. Everything not on a primary tab is one click from wherever its claim is
rendered, per D4.2's "reachable from every depth" requirement, which this direction treats as
a navigation principle as much as an evidence-access one.

---

## 2. Representative Overview screen — "Briefing"

Rendered in `mockup.html`, `#screen-briefing`.

Five blocks, stacked vertically, each large (full content width, generous internal padding),
each answering exactly one of the owner's four questions (Block E answers a fifth,
synthesizing role):

1. **Block A — "How am I doing?"** Headline conclusion + total value + return, one visual
   (cumulative portfolio-vs-benchmark line chart), an "expandable key holdings" sub-panel
   (top 5 positions, opened via the block's own Investor-depth level) satisfying the owner's
   named "expandable key holdings" item without needing a sixth block.
2. **Block B — "What is driving the portfolio?"** Headline + one key number (economic-geography
   concentration) + one visual (allocation view). This is also where the listing-market vs.
   economic-geography distinction (§D1 Exposure) gets its most visible airing on Briefing,
   because the divergence between the two readings *is* the "why" behind Block A's return.
3. **Block C — "What are the main risks?"** Headline + one key number (annualized volatility
   vs. benchmark) + one visual (rolling volatility sparkline).
4. **Block D — "What deserves my attention?"** Headline = the single top-severity insight's
   one-line conclusion + a count of Attention/Warning items, expandable to the full
   severity-ranked list.
5. **Block E — AI Portfolio Brief.** A short, entirely citation-chip-grounded paragraph that
   stitches A–D together into one narrative, with an "Ask a follow-up" entry to the full AI
   Analyst panel. Detailed in §4 — this is the direction's hardest problem, not a footnote.

**Freshness strip**, a slim always-visible bar above the blocks (not folded into any one
block), naming each data axis independently and the least-fresh axis explicitly — the D5.1
"never merge axes" rule rendered as its own persistent element rather than buried in Block A.
This is the one piece of Briefing that is deliberately *not* a block: freshness is a
precondition for reading anything below it, not a fifth thing to rank against the other four.

**What is explicitly not on Briefing:** any Scenario Lab value, any correlation matrix, any
regression diagnostic — unchanged from D1's own Overview exclusions, inherited without
modification.

**Ordering.** Blocks are ranked, not alphabetical or fixed-by-category: severity/materiality
of what each block has to say determines stack order on a given day (an unusually large
drawdown could, in principle, promote Block C above Block A). The default order shown in the
mockup (A, B, C, D, E) is the *no-active-warning* baseline. See §6's third weakness for the
risk this ranking itself carries.

---

## 3. Representative Analytics screen — "Risk & Analytics"

Rendered in `mockup.html`, `#screen-analytics`. Chosen over Portfolio/Holdings because it is
the harder test of the thesis: can conclusion-first, block-structured presentation survive
contact with the product's most quantitatively dense surface without collapsing back into a
number grid? Four blocks, same visual grammar as Briefing but denser (this is the
professional-depth surface, so default depth here is Investor, not Quick):

1. **Volatility** — headline + annualized volatility (18.4%) vs. benchmark (14.1%), one
   visual (rolling 90-day volatility line).
2. **Beta** — headline + beta value, rendered `LIMITED` (24 monthly observations, below the
   36-observation preferred minimum) — this block reuses D2.3 Example 1's exact structural
   shape (direction-relative Quick wording, no "% riskier" framing).
3. **Correlation / cluster** — headline + cluster interpretation before the pairwise number,
   per §18.2's own four-step ladder composing with D2's four levels, exactly as D1 requires;
   Professional depth reveals the full sub-matrix.
4. **Concentration & contribution to risk** — headline + top-5 concentration figure, one
   visual (bar); this block also carries a second metric, Sortino ratio, rendered
   `INSUFFICIENT_DATA` (insufficient downside-observation sample) so both required D3.2 states
   appear on this screen independent of Briefing's Holdings panel.

Each block carries the same Quick→Simple→Investor→Professional radio ladder and the same
always-present Evidence control as Briefing's blocks — the interaction grammar is identical
across primary surfaces by design; only default depth and block density differ.

---

## 4. AI interaction concept — the central design problem

Direction C's Block E is not a widget bolted onto Overview; it is the direction's thesis
applied to natural language, and it is the hardest place to hold P1 because it is the one
place in this direction where the deterministic/AI boundary has to survive *inside a sentence*
rather than between two visually separate regions of a page.

**The mechanism, as designed:**

1. **Every numeral in AI-composed prose is a citation chip, never bare text.** A chip is a
   small `<details>/<summary>` control inline in the sentence (mockup: `+8.4%`, `52%`,
   `18.4%`, etc.) — clicking it opens an inline pop-out naming the deterministic source: which
   engine output, which snapshot, which period/window, plus a link into the Methodology &
   Evidence surface scoped to that claim. This is the same D4.1 affordance every other surface
   uses, rendered as a chip instead of a button because it sits inside flowing text.
2. **A rendering self-check, stated as a testable rule, parallel to D3.2's "no numeric glyph
   for `INSUFFICIENT_DATA`":** no digit may appear inside `.ai-narrative` text outside a
   citation-chip wrapper. This is the structural way this direction makes "the AI never types
   a number it presents" *visible*, not just true in the engine (T4 remains engineering's
   enforcement mechanism; this is the UI-side disclosure obligation D1 §8 already names).
3. **Non-chip words are visually distinct from chip words** (different weight/color in the
   mockup) so a reader can tell, at a glance, which parts of the sentence are the AI's own
   connective framing ("driven mainly by," "the most important thing to review is") and which
   are grounded facts — the same PD-0008 distinction the rejected prototype already
   established (selector language vs. falsifiable claim), carried into a narrative
   presentation instead of a Q&A one.
4. **A caveat that would apply to a chip's value must appear inline, not only inside the
   chip's pop-out.** If a chip's underlying claim carries `LIMITED`, `INSUFFICIENT_DATA`, or a
   threshold-triggered `STALE_DATA` state, the sentence around it must carry a short qualifier
   in the visible text itself (mockup: "...volatility of 18.4% (short sample window)..."). This
   is D2.2's caveat-slot guarantee re-expressed for a narrative context: the caveat must
   survive into the headline the reader actually reads, not just into a click-to-reveal panel
   — which is precisely what the owner's instruction to this direction demanded ("a caveat
   must survive into the headline rather than being left behind in the detail").
5. **"Ask a follow-up" opens the full AI Analyst panel**, same citation-chip mechanism, same
   Quick/Simple/Investor/Professional per-message depth selection §22.7 already specifies —
   Block E is a compressed, always-on face of the same surface, not a separate mechanism.

**Why this is genuinely the hardest part of this direction, named plainly:** every other
direction can put AI in a bounded region (a card, a panel, a chat thread) where the
deterministic/AI boundary is a *spatial* boundary — inside this box, values are numbers with
buttons; outside it, prose. Direction C's central move — a paragraph *is* the primary
Overview content for one full question — means the boundary has to be a *typographic* one
inside continuous text, which is a categorically harder thing to get right and a categorically
easier thing to get subtly wrong (a rendering bug that drops one chip wrapper is invisible
until someone reads carefully). This is not a flaw the mockup can design away; it is named
again in §6 as this direction's most serious weakness.

---

## 5. Evidence / methodology interaction

One interaction pattern, reused everywhere in this direction (Briefing blocks, Analytics
blocks, AI narrative chips):

1. **Conclusion** — the block's headline, always visible.
2. **Number** — the key figure, always visible, carrying its D3 state and D5 freshness inline
   per §D3.2/§D5.2's rules, unmodified by this direction.
3. **Explain** — the Quick→Simple→Investor radio ladder within the block; moving right adds
   plain-English meaning, then reference point/values/comparison, per D2.1/D2.2, unmodified.
4. **Evidence** — a small "Evidence" control, present at every depth level per D4.2 (not
   gated behind Professional), opening an inline drawer (`<details>` in the mockup) showing
   the Proof Packet summary fields (claim, judgment class, snapshot id, comparison basis,
   benchmark, period, freshness, limitations) — chosen as an inline drawer rather than full
   navigation-away, because this direction's whole premise is that going deeper should not
   cost the reader their place in the briefing.
5. **Methodology** — a link inside that same drawer to the full Methodology & Evidence
   surface (surface 11), scoped to that metric's registry entry — full navigation, because
   the registry view is genuinely a different, denser surface (§33's fifteen fields), not
   something that fits in a drawer.

For a Scenario Lab claim, the same drawer opens, but per D1 surface 7's existing rule, the
Proof Packet's `scenario_id` field is populated and the drawer additionally lists which
specific inputs were user-modified versus carried over unchanged — this direction adds no new
mechanism here, it reuses the one D1 already specifies for Scenario Lab's evidence affordance.

---

## 6. Strengths

- **Strongest fit to the owner's stated first-use complaint.** "Fragmented across too many
  top-level destinations, no strong portfolio understanding on first use" is answered
  directly: five large answers to four fixed questions, all above the fold or one scroll away,
  nothing requiring navigation.
- **Progressive disclosure is structurally enforced, not just encouraged.** Nothing beyond a
  headline and one number renders by default anywhere in this direction — the radio-ladder
  mechanism makes "closed by default" the only way the markup can render, not a design
  guideline a future implementer could quietly ignore.
- **The AI narrative reduces redundant reading rather than adding to it.** Block E does not
  repeat Blocks A–D's numbers in a new form; it is the connective sentence between them,
  which is the product's actual differentiator (interpretation across sources) done in the
  place a first-time reader is most likely to read something end-to-end.
- **A single interaction grammar reused everywhere** (conclusion → number → explain →
  evidence → methodology, identically shaped on every block, on every primary surface) lowers
  the learning cost of the whole product to "learn this pattern once."
- **Visual quiet reads as premium by default.** Low block count and generous whitespace do
  the "institutional, not internal-tool" work the owner asked for without needing decorative
  charts to manufacture visual interest — this direction adds a chart only where §26/owner
  objective 3 already requires one (performance line, volatility line, allocation view,
  concentration bar).

## 7. Weaknesses — named honestly

- **Experienced users who want numbers immediately are underserved by the default state.**
  Reaching a correlation coefficient or a specific position's cost basis costs at least two
  disclosures (open the block's Investor level, then Evidence) even though the number existed
  on the old prototype's first paint. This is a direct, acknowledged tension with success
  criterion 3 ("identify... quickly") for a power user, not just a hypothetical one — this
  direction trades their speed for a first-time user's comprehension, and does not pretend
  otherwise.
- **This direction carries the highest P1 risk of the three, by construction, not by
  accident.** Because Block E's whole value is a fluent paragraph rather than a bounded panel,
  the deterministic/AI boundary has to hold *inside a sentence*. A single missed chip-wrapper
  in one narrative template is a harder defect to notice than a stray number appearing outside
  a clearly-labeled AI box would be in a more conventional layout. §4 names the mitigating
  mechanism; it does not eliminate the risk, only makes it checkable.
- **Block ranking is itself a judgment this document cannot fully specify or guarantee is
  neutral.** "Order by what matters most right now" requires a materiality function across
  four heterogeneous domains (return, exposure, risk, insights) that this document sources
  from Insights' existing severity taxonomy (§20.1) rather than inventing a new one — but a
  careless implementation could let the *AI* (rather than the deterministic severity ranking)
  choose emphasis, which would start to look like advice the product is not authorized to give
  (P7's spirit, even though ranking is not literally a personalized constraint). This document
  states the ranking must be deterministic-severity-sourced; it cannot enforce that beyond
  saying so.
- **Tabular comparison is structurally worse here than in a table-first layout.** Comparing
  many holdings or many metrics side by side is not what a stack of large blocks is good at.
  Direction C pushes that need to Portfolio/Analytics's secondary tabs, which is correct per
  the owner's own instruction to keep Overview from becoming a grid of everything — but it
  means Briefing alone cannot satisfy "identify the biggest holdings quickly" for a portfolio
  with, say, thirty small positions beyond the top five shown in Block A's panel.
  design cannot make five one-sentence headlines mandatory; it only makes the *slot* for one
  sentence mandatory. If whoever writes the actual copy defaults to a paragraph in the Quick
  slot, the "reduce text density" objective silently fails even though the structure is
  correct — this is the same limitation D2.2 already names for caveat-compression wording,
  recurring here for headline copy specifically.
- **"AI composes the narrative structure" is one clause away from "AI decides what matters,"**
  and this direction leans on that clause harder than a more conventional layout would need
  to. The boundary drawn in §4/§6's third bullet is the correct one, but it is a boundary this
  design draws and a future build must actively defend, not a property that falls out of the
  layout automatically the way, say, "Scenario Lab is a separate tab" structurally prevents
  cross-contamination almost by accident.

## 8. Implications for the validated CP0 design

Re-expression only — nothing here proposes changing what any surface must contain or assert:

- **D2.2's claim object needs a documented "inline/narrative" rendering mode.** The four-level
  ladder and the caveat-slot guarantee already generalize to a citation-chip rendering (§4),
  but `designs/FEATURE_DESIGN.md` does not currently name this rendering form; if Direction C
  is selected, D2.2 should gain a short paragraph stating that a claim object may render as an
  inline citation chip inside AI-authored prose, subject to the same caveat-non-optional rule,
  rather than only as a card/row/line-item.
- **Overview's fixed nine-item §26 hierarchy needs re-expressing as five blocks, not
  re-ordering.** Items 1–2 (value, gain/loss) and 3 (chart) become Block A; item 4 becomes
  Block B; item 5 becomes Block C; item 6 becomes Block D; items 7–8 (Brief, Ask) become Block
  E; item 9 (freshness) becomes the persistent strip. The informational content and the
  §26-required order within each block's Quick state is unchanged — only the grouping into
  blocks, which is new, needs writing down if this direction is chosen.
- **The freshness-field gap `designs/FEATURE_DESIGN.md`'s own Known Limitations section
  already flags (no named slot for D5 data on the claim object) becomes more load-bearing
  under this direction**, because the Briefing strip and every narrative chip need to know a
  claim's freshness state to decide whether to show a qualifier. This direction does not
  resolve that gap (it is out of this role's authority per the same document); it makes the
  existing gap more visible and slightly raises the priority of closing it before
  implementation.
- **No change to D1's per-surface purpose or information-hierarchy text is implied.** Only the
  primary/secondary navigation slot each surface sits in (§1's table) changes; D1's own
  content requirements per surface are inherited unmodified.

## 9. Genuine contradiction discovered

**None found.** Three near-misses were considered and resolved without reopening the
baseline, recorded here so the reasoning is visible rather than the absence of a finding being
mistaken for an unexamined gap:

- **AI narrative synthesis vs. P1.** Not a contradiction — a hard design problem with a
  workable mechanism (§4), not a case where the UX cannot represent the validated logic.
- **"Insights integrated into relevant surfaces" (owner objective 2) vs. Insights being
  specified as its own primary claim-bearing surface that "owns the full list" (D1 surface 6).**
  Not a contradiction — Direction C's Attention block integrates the top items while the "See
  all insights" expansion still lets surface 6 own the full list, satisfying both without
  either instruction giving way.
- **Briefing's "the deeper surface opens already scoped to what you clicked" navigation model
  vs. P8's requirement that Overview never render a `SCENARIO`-typed claim.** Not a
  contradiction, but worth stating explicitly: no Briefing block in this direction contains a
  "preview this as a scenario" shortcut that would compute or display a hypothetical value
  inline. Any such affordance, if ever proposed, must route to Scenario Lab itself rather than
  rendering a scenario value on Briefing — this direction's block-drill-through model is
  compatible with the inherited P8 mechanism only because it is designed not to create that
  shortcut, not because the mechanism prevents it automatically.

---

## Success criteria — how Direction C meets or risks each one

| # | Criterion | Direction C |
|---|---|---|
| 1 | Understand overall status primarily from Overview | **Met.** Five blocks, each answering a fixed question, headline visible with zero clicks. |
| 2 | Compare portfolio vs. benchmark visually without opening another section | **Met.** Block A's one visual is exactly this chart, on Briefing by default. |
| 3 | Identify biggest holdings/exposures/risks quickly | **Partially at risk.** Top items are visible at a glance (Block A's top-5 panel, Block B's key number, Block C's key number); a *complete* ranked list requires drill-through into Portfolio/Analytics. Named as a weakness (§7). |
| 4 | Understand what requires attention without reading long paragraphs | **Met, and this direction's strongest ground.** Block D's default state is a single sentence by construction. |
| 5 | Access explanation, evidence, methodology when desired | **Met.** One reused ladder + drawer pattern, present at every depth level, on every block. |
| 6 | Distinguish actual vs. Scenario Lab | **Met.** Scenario Lab is a fully separate primary surface; the inherited cross-cutting P8 mechanism (Overview/Holdings structurally cannot render a `SCENARIO` claim) is unmodified by this direction. |
| 7 | Use AI without AI prose becoming the source of facts | **Met, but this is the direction's highest-risk criterion.** The citation-chip + inline-qualifier mechanism (§4) is a genuine, checkable answer, and it is also the design surface with the least margin for a rendering defect of any of this direction's blocks — named plainly, not minimized. |

---

## Verification — what was and was not done

I authored `mockup.html` as static HTML/CSS only — **zero JavaScript**, by deliberate choice,
using the native `<details>/<summary>` element for every progressive-disclosure interaction
(citation-chip pop-outs, Evidence drawers) and the CSS `:checked` radio-sibling technique for
tab switching (primary nav, per-block depth ladders). This was chosen specifically because I
have no JavaScript runtime and no browser available to test in, and a markup/CSS-only
mechanism removes an entire class of untestable failure (a JS syntax or logic error) that I
could not have caught by inspection alone.

**I did not load or render this file in a browser.** I hand-checked tag balance, `id`/`for`
pairing for every radio and label, and `:checked ~` selector scoping by re-reading the file
after writing it, but I did not execute it. `pm-01` (or whoever serves it) should verify it
opens correctly over `http://localhost` before it is shown to the human owner.
