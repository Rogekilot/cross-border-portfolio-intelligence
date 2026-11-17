# HG1 Revision Cycle 01 — Comparison of Three UX/IA Directions

**Author:** `designer`, worker `designer-08`, a distinct worker from all three direction
authors (`designer-05`/A, `designer-06`/B, `designer-07`/C), per
`reviews/gates/HG1_REVISION_CYCLE_01.md` §4. Sole write path used: this file.

**What this is.** An independent comparison and recommendation for the human product
owner, who reserved the selection explicitly ("recommend one direction, but do not select
it on my behalf"). This document recommends; it does not decide.

**What I read.** `reviews/gates/HG1_REVISION_CYCLE_01.md` in full; `DIRECTION.md` and the
complete `mockup.html` for all three directions (line-by-line, not sampled);
`designs/FEATURE_DESIGN.md` §D1–D5 and its Known Limitations section;
`reviews/gates/HG1_PROTOTYPE_INSPECTION.md`. I did not read any provenance the three
authors did not have access to, and I did not run or render the mockups — see
"What I verified and did not" at the end.

**HG1 status.** `pm_acceptance` = `awaiting_human`. Unmoved by this document. See the
closing section.

---

## 1. Comparison matrix — the seven named dimensions

| Dimension | A — Command Deck | B — Analyst Desk | C — Briefing Room |
|---|---|---|---|
| **Information hierarchy** | Flat and simultaneous: 8–9 tiles visible at once on Overview, ranked by position/size, not by sequential disclosure. Everything the owner's objective 1 lists is on-screen together. | Layered but chart-dominant: one hero visual (~55% of viewport height) anchors the page, a tightly-coupled metric strip sits directly under it, then a three-column row, then an insights rail — a designed reading order, not a flat grid. | Explicitly sequential: five large blocks, one per owner question, each closed to a one-line conclusion by default. The steepest, most enforced progressive-disclosure gradient of the three. |
| **Navigation model** | Four tabs (Overview/Portfolio/Analytics/Scenario Lab) + a permanent, non-tab AI rail docked right on every primary surface. | Four tabs (same four labels) + a top-anchored command bar (AI entry + object jump) + a persistent right-docked inspector that is not a nav item but does heavy IA work (three of eleven D1 surfaces resolve through it). | Four tabs, "Overview" renamed "Briefing" in vocabulary only + a header "Ask your portfolio" affordance opening a slide-over, structurally similar in kind to A's bell/gear icons. |
| **Overview composition** | 12-column tile grid: hero value, perf-vs-benchmark chart, key holdings (expand-in-place), allocation, risk snapshot, top insights — plus the AI rail as an adjacent, not-Overview-owned, eighth region. | Hero chart → metric strip → three-column row (holdings/allocation/risk) → insights rail → AI brief docked at the rail's bottom, in that fixed reading order. | Five ranked blocks (How am I doing? / What's driving it? / Main risks? / What needs attention? / AI Brief), each independently reorderable by materiality — the only direction where block order is itself a designed, data-dependent variable. |
| **Visualization strategy** | Dense: performance line, donut + stacked geography bar, per-tile SVGs, all visible together; charts are numerous but individually small. | Concentrated: one large, high-contrast hero chart carries most of the visual weight; a second chart (FX-attribution stacked band) is used specifically because prose cannot show two overlapping contributions as legibly. | Restrained: exactly one small visual per block, chosen only where the owner's objective 3 already requires one; explicitly argues against manufacturing visual interest for its own sake. |
| **Treatment of AI** | Permanent, always-visible chat-shaped rail; AI Portfolio Brief is the rail's first message, not a separate tile. | No persistent panel at all: a command bar plus transient answer cards that land in the shared inspector; AI has no standing screen real estate outside the one required Overview brief line. | AI composes a connective narrative that *is* Overview's primary synthesizing content (Block E), plus a header-level "Ask" affordance elsewhere — the only direction where AI prose, not a chart or card, is asked to carry an Overview-level communication job. |
| **Treatment of evidence/methodology** | Per-number anchored popover, in place, with a footer link to a right-edge slide-over for full registry/Proof-Packet content. Shortest single-lookup path. | A standing, persistent docked inspector: focusing a claim *is* opening its evidence; near-zero marginal cost for sequential lookups, at the cost of one shared, contested panel. | Inline `<details>` drawer at every block, with a link out to the full registry page only when the reader wants the denser destination — a middle path between A's popover and B's standing panel. |
| **Density / progressive disclosure** | Default-dense: most tiles show their Quick-equivalent content permanently; explicit expand-in-place and a full four-level ladder exist but are opt-in, demonstrated on one worked example (Beta). | Split default: Quick-ish on Overview, Investor-as-default on Analytics — a stated, deliberate difference by surface ("the workbench assumes a returning analyst, not a first glance"). | Uniformly closed-by-default everywhere, including Analytics, which is unusual — even the professional surface opens at Investor by explicit choice, not Quick, but nothing renders beyond a headline+number without a click anywhere in the product. |

---

## 2. Are the three genuinely different, or cosmetic variants?

**Verdict: genuinely different on six of the seven named dimensions; materially
convergent on the seventh — the primary navigation model's top level.**

All three landed on an *identical* four-item primary tab bar: Overview/Briefing,
Portfolio, Analytics, Scenario Lab — the exact labels the owner offered "for example" in
objective 2. This is not a coincidence produced by cross-contamination (each author
states, and I have no reason to doubt, that they worked cold and did not read the
siblings); it is a coincidence produced by three independent designers converging on the
owner's own suggested structure, which the owner explicitly flagged as "directional, not
mandatory." The owner asked for navigation-model difference as one of seven required axes
of differentiation, and on the *primary tab-bar* reading of "navigation model," none of
the three actually diverges from it. I am reporting this rather than letting six strong
differentiations paper over it.

That said, "navigation model" is bigger than the tab bar, and everything *besides* the
top-level labels differs substantially: what sits outside the tabs (a permanent rail vs.
a command bar vs. a header affordance), how deep surfaces are reached (in-place expansion
vs. a shared inspector vs. sub-tabs plus drill-through), and what does the IA work for the
eleven D1 surfaces that aren't primary tabs (rail-adjacent vs. inspector-hosted vs.
block-embedded) are all substantively different. On balance, the three are not "three
color themes" — the owner's specific worry does not hold here. Overview composition,
visualization strategy, AI treatment, evidence treatment, and density are each argued and
executed in genuinely incompatible ways; a reader could not mistake one mockup for
another with the labels swapped. But the navigation-model convergence is real, and I am
not going to describe it as differentiated when it isn't.

---

## 3. Success criteria — direction by direction

### 1. Understand overall portfolio status primarily from Overview
All three meet this. **C's is the most deliberate fit** — its whole thesis is built
around exactly this criterion, and its own §6 states so plainly. B's Overview is also
strong (hero chart + strip + three-column row all above one scroll at reference width),
but B is explicit that this strength does not extend past Overview into the rest of the
product (see criterion-1-adjacent risk below). A meets it by density rather than by
sequencing — everything is present, but nothing tells a first-time reader what order to
read it in.

### 2. Compare portfolio vs. benchmark visually without opening another section
All three meet this literally (the chart is on Overview in each). **B is strongest** —
the hero chart is ~55% of viewport height and the single largest element on the page, the
most literal execution of "primary communication mechanism" for this specific
requirement. A and C both include the same chart but at tile/block scale, not
page-dominant scale.

### 3. Identify biggest holdings/exposures/risks quickly
**A is strongest** — Key Holdings, Allocation, and Risk Snapshot are simultaneously
visible with no click required. B is close behind (three-column row, one scroll down). **C
is the weakest of the three here, by its own admission** — a complete ranked list requires
drill-through past the top-5 shown in Block A; for a portfolio with many small positions,
Briefing alone does not satisfy this criterion, only Portfolio/Analytics do.

### 4. Understand what requires attention without long paragraphs
**C is strongest** — Block D's default state is a single sentence, structurally, not by
convention. B is close (one-line insight rows, full text one click into the inspector). **A
is the direction most at risk on this criterion**, and says so itself: eight-plus
simultaneous tiles is a density argument that could reproduce the rejected prototype's
"wall of numbers" complaint in denser disguise if hierarchy execution is not disciplined.

### 5. Access explanation, evidence, methodology when desired
All three satisfy D4.2's reachability requirement. **B has the strongest structural
argument** — evidence access has near-zero marginal cost once any claim is open, which
matters specifically for the audience P9 exists to serve (an auditing reader working
through several related claims). **A has the shortest single-lookup path** (one click,
anchored, no navigation). C sits in the middle — an inline drawer at every depth, with a
second click out to the full registry page only when wanted.

### 6. Clearly distinguish actual portfolio state from Scenario Lab
All three meet this equally well, structurally. Each keeps Scenario Lab as its own
primary surface with a non-dismissible, structurally distinct visual treatment (badge,
amber-bordered band, or dedicated column styling), and each explicitly checked that no
`SCENARIO`-typed claim reaches Overview/Holdings. No meaningful difference among the
three on this criterion.

### 7. Use AI without AI-generated prose becoming the source of deterministic facts
This is the criterion tied to a product invariant (P1), and per the owner's own framing
it must be weighed more heavily than an aesthetic difference. **A and B are structurally
stronger than C here, and this is the most consequential single finding in this
comparison.** A and B both keep AI prose inside a bounded, visually distinct container (a
docked rail; a command-bar answer card) where "is this a chip or plain text" is a local,
spatially-scoped question. C's Block E asks a single flowing paragraph to carry the
Overview-level synthesis job, which means the deterministic/AI boundary has to hold
*inside a sentence*, continuously, rather than at a container's edge. C's own §4 and §7
name this as the direction's hardest problem and highest-risk criterion, not as a
strength — I independently agree with that self-assessment; it is honestly the correct
one, not a place where the author underclaimed a risk to look thorough. The mitigating
mechanism C proposes (no digit outside a `.chip` wrapper, as a testable rendering rule) is
real and checkable, but it is a rule a future implementation must actively defend, not a
property that falls out of the layout the way Scenario Lab's separate-tab treatment does
in all three directions.

---

## 4. Risk assessment per direction — taste questions vs. invariant threats

**Direction A — Command Deck**
- *Taste risk:* whether eight-plus simultaneous tiles reads as "disciplined density" or
  "a wall of numbers" is a real, unresolved question a static mockup cannot settle; A says
  this about itself and I agree it is the right thing to worry about. Not an invariant
  question — a first-time-user comprehension question.
- *Invariant-adjacent, but not a violation:* A's own DIRECTION.md §5 claims "nowhere does
  it use a bare em-dash... every other 'nothing here' case uses a written word, not a
  dash" — directly addressing finding P-1 from `HG1_PROTOTYPE_INSPECTION.md`. This is true
  on the Overview screen (Moutai's `INSUFFICIENT_DATA` cell reads "insufficient data,"
  plain text, no leading glyph). It is **not** true on the Analytics screen: the Tracking
  Error tile renders `&mdash; insufficient data` (`mockup.html` line 954) — the identical
  em-dash-prefixed pattern P-1 flagged in the rejected prototype's Moutai row. This is not
  a P5/§32 violation (the state is still paired with explicit text and a reason code, per
  P-1's own careful non-finding), but it is a direct contradiction between what A's
  DIRECTION.md asserts about its own mockup and what the mockup's second screen actually
  renders. I flag it because it is exactly the kind of thing "read the mockup, not only
  the prose" is supposed to catch.
- *A second, smaller inconsistency, same category:* A's Overview freshness strip states
  "HK equities · EOD Sep 3, 16:08 HKT" and "CN A-shares · EOD Sep 3, 15:00 CST," then its
  own least-fresh-axis note (line 549) declares Hong Kong equities the least-fresh axis in
  use. Hong Kong Time and China Standard Time share the same UTC+8 offset; 16:08 is later
  than 15:00, so by A's own displayed timestamps the Mainland China print is the older
  (less fresh) one, not Hong Kong's. This is a self-contained execution slip, not a design
  flaw, but it is a concrete illustration of the real risk under this thesis's density: a
  "single top-of-deck strip showing all axes simultaneously" (A's own stated strength) is
  only as trustworthy as the freshness-comparison logic behind it, and that logic is
  nontrivial across timezones/markets and easy to get quietly wrong.

**Direction B — Analyst Desk**
- *Taste risk, named honestly by the author and the one I most agree with:* this is an
  analyst's tool, and the rest of the product past Overview assumes a user willing to
  focus an object and read a docked panel. That is a real cost for a first-time or
  occasional user, and it sits in direct tension with the owner's stated audience for
  objective 1 (though not with Overview specifically, which B argues, correctly, is
  strong on its own).
- *Minor, not invariant-threatening:* B's Overview insight text asserts "above your policy
  cap of 12%" (`mockup.html` line 428) — a specific numeric personalized threshold. This
  is legitimate only if Settings/Policy (D1 surface 10) actually holds a user-set 12% cap;
  nothing in the mechanism *guarantees* that, and Direction A's own Settings drawer
  explicitly renders the opposite assumption ("No single-position weight cap set. No
  sector cap set."). This is not a P7 violation in either mockup — both are internally
  consistent with their own synthetic data — but it is worth the owner's attention as a
  reminder that a "policy-dependent" insight is only ever as safe as the policy actually
  being on file, and the two mockups made opposite assumptions about that without either
  one being wrong to do so.
- *Documentation vs. mockup gap:* DIRECTION.md §5.3 claims the mockup demonstrates a
  "distinct lighter-weight center-dot glyph" for ordinary no-value cells, disambiguated
  from the em-dash used for `INSUFFICIENT_DATA`. I did not find such a cell anywhere in
  `mockup.html` — the Holdings fragment shown has only an `AVAILABLE`, a `LIMITED`, and an
  `INSUFFICIENT_DATA` row, no ordinary N/A example. The distinction is asserted in prose,
  not demonstrated in the artifact. A smaller gap than A's contradiction above (nothing in
  the mockup actually violates the rule; it simply doesn't show the case the prose claims
  it shows), but the same category of finding.

**Direction C — Briefing Room**
- *Invariant-adjacent risk, and the one to weigh most heavily per the owner's own
  instruction:* see §3, criterion 7 above. This is real, named honestly by the author, and
  not manufactured by me — I am agreeing with C's own self-assessment, not discovering a
  hidden flaw the author missed.
- *Taste risk:* power-user speed. Reaching a specific number costs at least two
  disclosures under this thesis even when the same number was one glance away in the
  rejected prototype; C names this and does not minimize it.
- *A genuine, if narrower, invariant-adjacent risk C names about itself:* block ranking
  ("order by what matters most right now") needs a materiality function, and a careless
  implementation could let AI rather than deterministic severity choose emphasis — which
  would start to look like advice the product is not authorized to give. C states the rule
  must be deterministic-severity-sourced but correctly notes the document cannot enforce
  that beyond saying so.

---

## 5. Contradictions — checked independently

All three authors reported finding none, having each specifically tested one or more
candidate friction points against the accepted baseline. I re-checked with the benefit of
seeing all three together, specifically looking for two directions resolving the same
tension in incompatible ways (which would be evidence the tension is real and
unresolved), and did not find one. I did find three findings worth the owner's attention,
none of which rises to a contradiction of a baseline contract:

1. **Direction A's DIRECTION.md vs. its own mockup.html disagree about whether a bare
   em-dash appears anywhere as an `INSUFFICIENT_DATA` prefix.** Detailed in §4 above. This
   is a documentation-accuracy finding about one direction, not a cross-direction
   contradiction, and not a P5/§32 violation on its own terms.
2. **Directions A and B make opposite, but individually consistent, assumptions about
   whether a portfolio policy (single-position cap) is on file.** Not a contradiction of
   the product contract — Settings/Policy legitimately can be either state — but worth
   naming because it shows the "policy-dependent insight" class is exercised differently
   by two of the three mockups without either being wrong, and a future implementation
   should not assume either state by default.
3. **All three converged on the same primary navigation labels**, discussed fully in §2.
   Not a contradiction of the baseline; a finding about whether objective 7's
   navigation-model differentiation requirement was actually met.

I looked specifically for, and did not find, any case where two directions resolved the
same P1/P8/P9/D2–D5 tension in genuinely incompatible ways. Each direction's own
"contradiction discovered: none" holds up under independent review.

---

## 6. Implications for the validated CP0 design — consolidated across all three

All three directions agree, independently, on where `designs/FEATURE_DESIGN.md` needs
*re-expression* (not re-decision) if a direction is selected:

- **D2.2's claim object needs a documented rendering container.** D2 was written
  container-agnostic (conclusion/reference/caveat/methodology pointer, no assumed home).
  Each direction gives it a different physical home — A: tile + anchored popover; B: the
  persistent inspector panel; C: the block itself plus an inline drawer, and (only for C)
  a new "inline citation chip inside continuous prose" rendering mode that D2.2 does not
  currently name. Whichever direction is chosen, D2.2 should gain a short paragraph
  stating its actual rendering form(s).
- **D4.1's "single, consistently-placed control attached to every claim" needs
  re-expression as a concrete interaction**, and the three proposals are materially
  different commitments, not just different visuals: an icon-adjacent popover (A), the
  claim itself as the control via a focus gesture (B, which is honestly flagged as a
  bigger interaction commitment than D4.1's text alone implies), or an inline "Evidence"
  link at every depth (C).
- **D1's per-surface information-hierarchy lists (numbered, linear) need re-expression as
  actual layout**, not reordering — all three preserve every item's content and relative
  priority; none drops or renames a D1 surface.
- **The D5-freshness-has-no-named-slot-on-the-claim-object gap** (already flagged in
  `designs/FEATURE_DESIGN.md`'s own Known Limitations section, and in
  `CP0_RECONCILIATION.md` §3.1 from the tech-plan side) becomes more load-bearing under
  any of the three, because each direction's freshness treatment (top strip, footer
  strip, or inline pill) needs to know a claim's freshness state to decide what to render.
  None of the three resolves this gap — correctly, since it is out of design authority —
  but all three make it more visible and slightly raise the priority of closing it before
  implementation.
- **Only if C is selected:** D2.2 additionally needs a stated rule that a claim may render
  as an inline citation chip inside AI-authored prose, subject to the same
  caveat-non-optional guarantee, and this rule should be paired with an explicit
  implementation/testing requirement (not just a design note) given the P1 risk in §3/§4
  above.

---

## 7. Recommendation

**I recommend Direction C, "Briefing Room," as the primary direction**, with one specific,
narrow element considered from Direction B.

**Why.** The owner's own diagnosis of the rejected baseline was fragmentation and weak
first-use comprehension ("too text-heavy, visually sparse, fragmented across too many
top-level destinations, and does not provide a strong portfolio understanding on first
use"). Of the three, C is the direction built most directly against that diagnosis: it is
the strongest on success criteria 1 and 4 (the two criteria closest to "first-time
comprehension without reading long paragraphs"), and its weaknesses are concentrated in
places that cost speed for a returning power user (criterion 3, criterion 5's extra click)
rather than in places that reproduce the rejected prototype's specific failure mode. A
risks reproducing that failure mode in denser disguise, by its own admission. B is
strongest on criterion 2 and criterion 5, but is explicit that its whole-product paradigm
underserves exactly the first-time/casual audience the owner's diagnosis centers on.

**The specific hybrid element.** If the owner wants to strengthen C's Block A beyond what
this package shows, B's single dominant hero-chart treatment (the same portfolio-vs.-
benchmark SVG all three already use, sized to be the visually largest element on the page)
is a low-risk graft onto C's Block A: it does not touch IA, evidence mechanism, or AI
treatment — only the size and visual weight of a chart C already includes — so the seam
does not cross any of the structural choices that make C's Overview coherent.

**The strongest argument against this recommendation, stated plainly.** Criterion 7 is
tied to a product invariant (P1), and I have already argued that criterion should be
weighed more heavily than an aesthetic one. By that same logic, C is also the direction
that names the highest self-assessed P1 risk of the three, and it is not a risk I can
argue away — a paragraph is a categorically harder place to enforce "no untagged number"
than a bounded card or panel is, and the defect that breaks it (one missed chip wrapper in
one narrative template) is the hardest of the three directions' failure modes to catch by
casual reading. If the owner weighs P1 auditability as a harder constraint than first-use
polish — which is a defensible reading of "the deterministic engine owns financial facts;
the AI layer owns explanation" as a near-absolute rather than a balanced concern — then A
or B should be preferred over C, and between those two I would lean toward B on the
strength of its evidence-marginal-cost argument (criterion 5) and its more literal
execution of "make visualization a primary communication mechanism" (criterion 2),
accepting B's own named cost to first-time users as the price of that choice.

**What would change my mind.** A concrete demonstration, even a small one, that the
"no digit outside a chip wrapper" rule in C's Block E is hard to enforce reliably in
practice (for instance, if `engineer` or `quant_analyst` reports that AI-generated prose
templates make this rule brittle at the point copy is actually authored) would move my
recommendation to B. A finding that first-time-user comprehension testing favors B's
Overview as strongly as B's own document expects would also weaken the case for C
specifically on the criterion I am weighting most heavily in its favor.

---

## Selection belongs to the human product owner

This document is a recommendation, not a decision. **HG1 remains `awaiting_human`,
unmoved.** No agent, including this one, may select a direction on the owner's behalf. The
next action after this document is nothing, until the owner names a direction.

---

## What I verified and what I did not

**Verified, directly:** I read all three `DIRECTION.md` files and all three `mockup.html`
files in full (not sampled), line by line, including every screen, table, and inline
state each renders — not only the prose describing them. The em-dash finding in §4 and
the freshness-timestamp finding in §4 were both found by reading `mockup.html` source
directly against its own `DIRECTION.md` claims, not by taking either author's
self-report at face value. I read `designs/FEATURE_DESIGN.md` §D1–D5 and its Known
Limitations section, and `reviews/gates/HG1_PROTOTYPE_INSPECTION.md` in full, including
finding P-1, which I traced into each direction's specific handling.

**Not verified:** I did not render any of the three `mockup.html` files in a browser — no
JavaScript runtime or browser is available to me either, the same limitation all three
authors disclosed. My reading is a careful hand-trace of the markup/CSS, not a rendered
visual inspection; `pm-01` or the owner should still confirm each renders correctly before
relying on visual judgment beyond what is checkable from source. I did not evaluate
subjective visual quality (color, typography, spacing) beyond what each document itself
claims, consistent with `designs/FEATURE_DESIGN.md`'s own "no visual design" scope note —
that judgment belongs to the owner, not to a structural comparison. I did not attempt to
resolve, or take a position on, OQ-01 or any other open question outside this cycle's
scope; none of the three directions reopens it, and neither do I.
