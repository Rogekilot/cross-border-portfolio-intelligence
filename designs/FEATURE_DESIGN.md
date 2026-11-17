# Feature Design — Increment 1: Product Contract and Architecture Proposal (CP0)

**Increment ID:** `INC-001`
**Task:** `feature-development/ux_planning`
**Human Approval Gate:** HG1 (does not approve this document; this document is input to it)
**Authored by:** `designer`, worker `designer-01`, 2026-09-03
**Amended by:** `designer`, worker `designer-03`, 2026-09-04, three passes — (1) rework
pass closing `reviews/DESIGN_REVIEW.md` (reviewer `designer-02`) blocking findings BF-1
and BF-2, and non-blocking findings NF-1, NF-2, NF-3; (2) follow-up pass, at the
coordinator's request, closing the residual AC-07 open item pass (1) had left in
Overview, Holdings, and Exposure — each resolved per-surface (explicit D4 line where a
surface originates or terminates its own claims; an argued claim-object-inheritance
case where a surface only re-renders another surface's claim at a different depth);
(3) final pass, at the coordinator's request, examining the three D1 surfaces
`design_review`'s BF-2 table never checked (Transactions, Portfolio Settings/Policy,
Methodology & Evidence) and disposing of each explicitly — one needed a narrowly-scoped
D4 line (Transactions), two display no claim in D2.2's sense and are outside AC-07's
scope by reasoned exclusion, not omission (Portfolio Settings/Policy, Methodology &
Evidence). Amendments are marked inline at each edited location; original structure,
evidence markers, and unaffected sections are preserved. (4) `designer`, worker
`designer-33`, 2026-09-15, Post-HG1 Checkpoint A bounded revision — four amendments only
(§2 Holdings + §D3.2 for D1; §2 Holdings' depth paragraph + a short D2 note; §7 Scenario
Lab for D3; a D1 cross-cutting note for S1), each marked inline; no broader
reconciliation of this document's pre-HG1 content was attempted (see Stage-0 baseline §7,
a Phase-B entry item owned by `pm-01`).
**Authoritative inputs:** `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` (v1.1, governing
per `decisions/product/PD-0005-v1-1-prd-is-the-governing-mandate.md`); `specs/FEATURE_PRD.md`
§3.1 (D1–D5), §6 (AC-04…AC-08), §5, §11; for this rework pass, additionally
`decisions/product/PD-0006-metric-state-vocabulary-is-layered.md` (both amendments) and
`reviews/DESIGN_REVIEW.md`.
**Status:** authored, rework pass applied — not re-reviewed, not approved. Input to HG1,
not itself gated.

> This document specifies information architecture and interaction contracts. It
> presents **no computed financial number**, by design (source PRD §3.1 scope boundary).
> Visual design, component library, typography, color, and copywriting are explicitly
> out of scope for this deliverable.

Evidence markers, per the `prd-authoring` convention used in `specs/FEATURE_PRD.md`:

| Marker | Meaning |
|---|---|
| **[F]** | Fact — stated in the source PRD or `specs/FEATURE_PRD.md` |
| **[A]** | Assumption — believed, not verified |
| **[J]** | Judgment — a design decision made within designer authority |

Unmarked prose is connective tissue.

---

## 0. Reading order and dependency on OQ-01

**[F]** `specs/FEATURE_PRD.md` §9 OQ-01 is open: whether source PRD §32's nine listed
states are a single flat vocabulary or, as `specs/FEATURE_PRD.md` assumption A-05 reads
them, three *sufficiency* states (`AVAILABLE`, `LIMITED`, `INSUFFICIENT_DATA`) plus six
*reason* codes that explain a non-`AVAILABLE` sufficiency state.

**[J]** This document designs to A-05's reading, because it is the only reading under
which a UI component can be specified at all — a flat nine-state enumeration with no
structural relationship still needs *some* rendering rule, and A-05 supplies one. Every
place this document depends on A-05 is marked **[A-05]** inline. §D3.5 below states
precisely what changes if the human product owner resolves OQ-01 the other way. This is
not a silent choice: the human owner decides it, at or before HG1, per
`specs/FEATURE_PRD.md`.

---

## D1. Information architecture — the eleven surfaces

**[F]** Source PRD §6 names eleven primary surfaces and states progressive disclosure
replaces separate retail/professional products. **[A]** Per assumption A-02 in
`specs/FEATURE_PRD.md`, this list is read as the complete, authoritative V1 surface set —
not illustrative, not open to addition or removal by this document.

For each surface: **purpose**, **primary question(s) it answers**, **information
hierarchy** (what appears first vs. progressively), and **depth-model applicability**
(whether §D2's four-level ladder applies to content on this surface, since some surfaces
are navigation/configuration rather than claims-bearing).

### 1. Overview

**Purpose.** The single-glance answer to "where do I stand." **[F]** Source PRD §26
fixes the four questions in order: *How much do I have? How am I doing? Where am I
exposed? What should I pay attention to?* and a recommended hierarchy: total value in
reporting currency → gain/loss → performance chart → period selector → allocation/exposure
summaries → risk snapshot → top Insights → Portfolio Brief → Ask Your Portfolio entry
point → visible data freshness. **[F]** §26 explicitly forbids dense covariance matrices
or regression diagnostics here — that is Risk & Analytics territory.

**Information hierarchy (top to bottom, per §26's fixed order):**
1. Total portfolio value (reporting currency) + freshness indicator (D5) adjacent, not
   implied. **Evidence affordance (D4) attached directly — see below.**
2. Gain/loss, with its reference period stated (P4 — a number with no period is not a
   judgment). **Evidence affordance (D4) attached directly — see below.**
3. Performance chart + period selector.
4. Allocation/exposure summary (top-level only; full detail lives on Exposure).
5. Risk snapshot (top-level only; full detail lives on Risk & Analytics).
6. Top Insights (severity-ordered per §20.1; Insights surface owns the full list).
7. Portfolio Brief entry (AI-authored narrative — links to AI Analyst).
8. "Ask Your Portfolio" entry point (routes to AI Analyst).
9. Freshness disclosure, portfolio-wide summary form (D5 §3).

**D4 evidence-affordance reachability, stated explicitly (added 2026-09-04, closing the
residual portion of `design_review` BF-2/AC-07 left open after the prior rework pass).**
Overview's claim-bearing items split into two groups, and they do not get the same
treatment, because they are not in the same position:

- **Items 3–7 render the same underlying claim objects that Performance, Exposure, Risk
  & Analytics, and Insights render at greater depth or in full — they are not separately
  computed aggregates.** This is already stated for item 5 in Risk & Analytics's own
  §D1 text ("subset also feeds Overview §26's 'risk snapshot' line — same underlying
  facts, per §6, rendered at Quick depth"). The same relationship holds for item 3 (the
  headline-return claim D4.3 fully traces for Performance, rendered here at Quick depth
  via the period selector — same claim, not a second one), item 4 (Exposure's own
  exposure/allocation claims, rendered here at "top-level only," i.e. Quick, depth; full
  depth on Exposure), item 6 (the identical Insight objects Insights "owns the full list"
  of, filtered here to top severity — not re-derived), and item 7 (not even a duplicate
  rendering: a navigation entry to AI Analyst, where the claim is rendered exactly once).
  **Why this is enough, and not just an assertion:** D2.2 mandates one shared claim
  object per fact, rendered at whichever depth a given surface calls for; D4.1 attaches
  the evidence-affordance control **to the claim object itself, at every depth level it
  is rendered at** — not to the surface that happens to display it. A claim rendered at
  Quick depth on Overview and at Professional depth on its home surface is the *same*
  object carrying the *same* methodology pointer, so the control that works on the home
  surface works here too, by construction, without this document needing to re-specify
  it per surface. This is the argument option (b) requires, written down rather than
  left to the cross-cutting note's implication.
- **Items 1–2 do not have this property, and get their own explicit control instead.**
  No other surface renders a total-portfolio-value claim or a portfolio-level gain/loss
  claim as its own primary content: Holdings shows market value and unrealized
  gain/loss **per position** (its own §D1, item 2–3), not a portfolio total, and summing
  positions into a single reporting-currency value is a distinct computation — currency
  consolidation, corporate-action and cash-flow reconciliation across the whole
  portfolio — with its own methodology, not a re-rendering of any position-level claim.
  These two are aggregation-only claims that originate on Overview and exist nowhere
  else to delegate to. **Overview therefore carries its own D4 control on items 1 and
  2 directly**, matching the pattern Risk & Analytics/Insights/AI Analyst/Scenario Lab
  already use rather than borrowing theirs — each opens its own methodology-registry
  entry (§33; portfolio valuation methodology, portfolio gain/loss methodology) scoped
  to the current portfolio snapshot.

**Depth model applies:** yes, to every claim-bearing element (value, gain/loss, risk
snapshot, insights). Overview defaults to **Quick**; deeper levels are reachable per D2
but not pre-expanded, to preserve the "single glance" purpose.

**What must NOT appear here [F, §26]:** covariance matrices, regression diagnostics, any
Scenario Lab hypothetical state (P8 — see D1.7).

### 2. Holdings

**Purpose.** The ledger-derived truth of what is actually held, at position granularity.
**[A]** Not explicitly detailed in source PRD beyond the portfolio hierarchy in §7.2
(`User → Portfolios → Accounts → Ledger Events → Derived Positions`); this surface is the
UI's window onto derived positions.

**Information hierarchy:**
1. Account-container grouping (§7.3 — US Broker, Futu HK, China Brokerage, Cash Account,
   etc.) as the organizing structure, since accounts are explicit accounting objects.
2. Per-position: instrument identity (§10.1's canonical identity, not just ticker —
   listing market must be visible since the same economic exposure can list in multiple
   markets), quantity, market value in native currency, market value in reporting
   currency, unweighted % of portfolio.
3. Per-position cost basis and unrealized gain/loss **only where §9.3 cost-basis
   sufficiency allows** — this is a D3 metric-state surface, not a guaranteed number.
4. Freshness indicator per position (D5 §1 — per-market, not portfolio-wide).
5. **[Added 2026-09-04, closing the residual portion of `design_review` BF-2/AC-07.]**
   Evidence affordance (D4), attached directly to item 3's per-position cost-basis and
   unrealized-gain/loss claims. **Holdings is the originating surface for these claims —
   there is no other surface to delegate to.** No other surface in this document renders
   cost basis or unrealized gain/loss at position granularity (Performance and Risk &
   Analytics operate at the portfolio level; Overview's item 2 is a portfolio-level
   gain/loss, a distinct aggregate claim per Overview's own §D1 text, not a re-rendering
   of Holdings' per-position figures). The control opens the cost-basis/valuation
   methodology registry entry (§33) scoped to that specific position and lot. Item 2's
   market-value figures are facts sourced from ledger quantity and current price, not
   judgments in the P9 sense, so they do not require this control — only item 3 does.

**Depth model applies:** partially. Position identity and quantity are facts, not
judgments — no depth ladder needed. Gain/loss and any derived commentary ("this position
grew faster than your average") does carry the ladder.

**[Amended 2026-09-15, Post-HG1 Checkpoint A — D1, `designer-33`.]** A sufficiency reason
rendered inline beside item 3's compact value (a Quick-depth render, inside a dense
ledger table cell) must wrap **within its own cell** and must never be horizontally
displaced from its row's security identity (item 2) — a reader must never have to choose
between reading a caveat and seeing which position it belongs to. Caveats are never
hidden, truncated, or shortened to fit; only their line-wrapping behavior changes. See
§D3.2's own note, added alongside this one, for the corresponding rendering-rule
correction.

**[Amended 2026-09-15, Post-HG1 Checkpoint A — D2, `designer-33`; corrected 2026-09-15,
Post-HG1 Checkpoint A correction round — F1/F4/F5, `designer-34`.]** Per §D2's own three
current rungs (PD-0012 — Quick/Simple/Professional; this document's own D2 title below
still reads "four-level," a broader staleness this bounded pass does not correct, see
Stage-0 baseline §7), item 3's per-position claims carry a genuine Professional rung: a
short position-input recap (quantity — labeled with the neutral "Quantity: `<n>`" token
the ledger's own column header uses, never characterized as "shares," since the record's
`quantity` field is unitless and not every holding is an equity with a share count;
cost/price in native currency, formatted exactly as the ledger's own currency
formatting; currency; listing market, labeled "listing market: `<code>`" — all sourced
from the ledger record, never invented), the claim's own existing sufficiency state and
reason restated in plain words (never a new judgment), and a plain statement of whether
this figure's own methodology registry entry is published. The claim's own existing
reference basis is **not** separately restated in this Professional text — the claim's
Reference line already renders directly above it at Simple and Professional, and an
earlier version of this pass restated it a second time, which only duplicated that line.
This is a rendering completeness fix, not a new analytical claim: no FX,
currency-conversion, or reporting-currency content is authored at this layer (that
remains a `quant_analyst` question — methodology findings §7.3, Stage-0 baseline §6 item
1).

**P8 boundary:** Holdings shows only the actual ledger-derived state. It is one of the
two surfaces (with Overview) where a Scenario Lab value must **never** appear, even
temporarily, even labeled — see D1.7 and the P8 mechanism in §D2.4.

### 3. Performance

**Purpose.** Historical return, decomposed by source. **[F]** §15.1 core metrics and
§8.4 FX attribution are the underlying content; §15.2 attribution and §15.3 tax boundary
bound what Performance may claim (no tax-effected performance, out of scope per §5.3/§4).

**Information hierarchy:**
1. Headline return over the selected period, reporting currency, with period and
   benchmark reference visible (P4).
2. Local-currency vs. FX-attributed decomposition (§8.4) — this is the product's
   differentiated claim ("how much of your return was the security vs. the exchange
   rate") and belongs near the top, not buried.
3. Return chart vs. benchmark.
4. Detailed period-by-period / drawdown table (Investor/Professional depth only).

**Depth model applies:** yes, fully — this is the canonical surface for the P3 worked
examples in D2 (alpha in particular).

### 4. Exposure

**Purpose.** Where risk actually sits, separated from where securities are listed.
**[F]** §10.3 (listing vs. issuer) and §10.4 (economic geography) are the load-bearing
distinction: a US-listed ADR of a China-domiciled company is not "US exposure."

**Information hierarchy:**
1. Toggle or explicit dual view: **listing-market exposure** vs. **economic-geography
   exposure** (§10.4) — these must never be merged into one number, because doing so
   would conflate two different facts (rule §44.12 in the source PRD's engineering
   instructions, referenced via `specs/FEATURE_PRD.md` T3).
2. Sector exposure, currency exposure, asset-class exposure (§18.1).
3. Concentration summary (largest position, top-5, HHI, effective N) — quick conclusion
   first, per §18.2's correlation-UX pattern generalized to concentration.
4. Correlation UX (§18.2's own four-step ladder: quick conclusion → cluster
   interpretation → important pairs → optional full matrix — this is itself a
   miniature depth model local to this surface, and it composes with, but does not
   replace, D2's four levels).
5. **[Added 2026-09-04, closing the residual portion of `design_review` BF-2/AC-07.]**
   Evidence affordance (D4) on every claim in items 1–4 (the listing/economic-geography
   split, sector/currency/asset-class exposure, concentration summary, correlation UX).
   **Exposure is the terminal surface for these claims, not a pass-through one.**
   Overview's own item 4 ("full detail lives on Exposure") explicitly delegates its
   summary rendering back to this surface per Overview's §D1 argument above — which
   means the delegation has to resolve somewhere, and this is where it resolves. Each
   claim's control opens the corresponding methodology-registry entry (§33) — e.g., the
   HHI/effective-N methodology for concentration, the correlation-window/frequency
   methodology for item 4 — matching the pattern already stated for Risk & Analytics's
   metric cards.

**Depth model applies:** yes. The full correlation matrix and risk-contribution detail
(§18.3) are Professional-only content, never surfaced by default at Quick/Simple.

### 5. Risk & Analytics

**Purpose.** The professional risk metric surface — volatility, beta, drawdown, Sharpe,
Sortino, and (Advanced V1, §16.2) tracking error, VaR, rolling metrics. **[F]** §16.3:
every metric here must trace to a methodology registry entry; the UI must never invent a
threshold or sample minimum locally.

**Information hierarchy:**
1. Quick-conclusion risk snapshot (subset also feeds Overview §26's "risk snapshot"
   line — same underlying facts, per §6, rendered at Quick depth).
2. Core V1 metrics (§16.1) at Investor depth by default.
3. Advanced V1 metrics (§16.2) reachable but not default-visible — this is the
   "dense covariance matrix" content §26 excludes from Overview, and it is also not
   default-visible here to avoid overwhelming Investor-depth readers; Professional
   depth surfaces it.
4. Methodology link (D4) on every metric card — this is the surface where the
   evidence-inspection affordance is most heavily used, since these are the metrics
   §16.3 requires a registry entry for.

**Depth model applies:** yes, fully. This is the surface where P3's beta and negative
alpha worked examples live most naturally alongside Performance's alpha example.

### 6. Insights

**Purpose.** The system's proactively generated, severity-ranked observations.
**[F]** §20.1 fixes three severity levels (Observation, Attention, Warning) and §20.2 a
judgment taxonomy (Fact, Interpretation, Preference-dependent judgment); §20.3 gives user
policy precedence over generic thresholds.

**Information hierarchy:**
1. Severity-grouped list, Warning-first, but **[J]** without implying urgency beyond
   what §20.1's definitions support — "Warning" here is a taxonomy label, not an
   asserted emergency, and copy that would editorialize that framing is out of scope
   (copywriting is excluded from this deliverable, but the structural constraint — that
   severity grouping must not be relabeled into alarm language — is an IA decision and
   belongs here).
2. Per insight: the claim (one line), its judgment class (§20.2 — is this a fact,
   an interpretation, or a preference-dependent judgment that requires a user policy to
   even be meaningful — §20.3, §20.4), and an evidence affordance (D4) to the Proof
   Packet.
3. Drift-specific insights (§19) are a distinguishable subtype, since they compare two
   points in time rather than one snapshot to a benchmark.

**Depth model applies:** yes — an Insight is exactly the kind of claim D2's Quick/Simple/
Investor/Professional ladder exists for, and every insight is also a P9 auditability
target (D4).

### 7. Scenario Lab

**Purpose.** Hypothetical portfolio modification and comparison, **[F]** §24: never
mutates the actual ledger (§24.4, FR-030) unless the user performs an explicit, separate
portfolio-edit action.

**Information hierarchy:**
1. **Persistent, structural visual/labeling separation between the Current portfolio and
   the Scenario** — this is not a copy note, it is this surface's entire reason to exist
   safely under P8. See §D1.7 for the cross-surface mechanism.
2. Scenario construction controls (§24.2: reduce weight, remove position, add
   hypothetical instrument, increase cash, shift exposure, enforce a constraint).
3. Current-vs-Scenario comparison, side by side, for exactly the metric set §24.3 lists
   (allocation, sector/country/currency exposure, concentration, historical volatility,
   beta, drawdown, correlations, risk contribution, benchmark-relative metrics where
   valid) — same metric definitions and registry entries as the live surfaces, since
   §32/§33 do not have a separate "scenario" methodology.
4. Every scenario output still carries a metric state (D3) — a scenario does not exempt
   a metric from insufficient-data suppression.
5. **[Added 2026-09-04, closing `design_review` BF-2/R-D2.]** Evidence affordance (D4)
   on every metric in the Current-vs-Scenario comparison (item 3), on **both** columns —
   this surface does not get a weaker version of D4 than Risk & Analytics, Insights, or
   AI Analyst. See the dedicated discussion below for what the affordance opens for a
   `SCENARIO`-typed claim, and how it stays inside P8.

**Depth model applies:** yes, to the comparison output. **[F]** §24.4: AI-created
scenarios must be labeled hypothetical analysis, never a recommended trade — this is a
copy/AI-behavior constraint outside this document's scope, but the structural
precondition (permanent visual separation, not a dismissible banner) is an IA decision
and is specified here.

**[Amended 2026-09-15, Post-HG1 Checkpoint A — D3, `designer-33`.]** Item 2's scenario
construction controls are machine-defined by a small set of canonical action codes and,
where applicable, a `dimension:code` target — these stay canonical internally (never
translated, matching every other enum/ticker/currency-code identifier this document's
D1/D2 treat as canonical per PD-0012 §3) but **must reach a reader as human-readable,
bilingual presentation**, not as the raw code. A reader-facing surface displaying a raw
machine token as if it were prose is a presentation defect, not a canonical-content
exemption — the underlying data value's canonical status and its rendered presentation
are two different questions, and this document's own D1 cross-cutting notes (below) now
state that distinction as a general rule, not just a Scenario Lab-specific fix. Any
automated regression check for "canonical content stays untranslated" must be built to
recognize this distinction too: certifying a raw machine value as intended, exempt,
visible content is itself the defect this amendment closes.

**Evidence affordance for a hypothetical claim (item 5), stated in full because it needs
more care than "same as everywhere else."** The concern raised by `design_review`
(BF-2) is not just that the affordance was missing from this surface's own text — it is
that adding it carelessly could let it become a P8 back door: an evidence view is a
detail view, and a detail view that shows raw inputs without the same persistent
labeling the summary view carries could make a hypothetical input look like an actual
one to a reader who drilled in expecting more precision, not less separation.

- **The methodology is real, not hypothetical, and D4 opens the same destination it
  opens everywhere else.** §24.3 states Scenario Lab's comparison metrics use "the same
  metric definitions and registry entries as the live surfaces" — there is no separate
  "scenario" methodology. So the affordance's Methodology-view branch (D4.1 item 1)
  behaves identically for a Scenario column metric as for the Current column: it opens
  the same registry entry, because the *calculation* is the same calculation.
- **What is hypothetical is the input, not the method — and the evidence view must say
  so, not obscure it.** Where a metric in the comparison is best modeled as a generated
  claim about the scenario (e.g., "this scenario's beta would be X") rather than a bare
  registry-traced number, D4's Proof-Packet branch applies instead, and it has
  somewhere to carry this already: source PRD §21's Proof Packet schema names
  `scenario_id if applicable` as one of its own fields, independent of this document's
  own additions. **[J]** This document specifies that a Proof Packet opened from a
  Scenario-column claim **must** populate `scenario_id`, and the packet's own claim
  object (per D2.2) carries the same `state_type: SCENARIO` field the cross-cutting P8
  mechanism (below) requires everywhere else — the evidence view is a rendering surface
  like any other, and the P8 mechanism's rule ("every rendering surface that can display
  a claim is keyed to render `ACTUAL` and `SCENARIO` claims with permanently distinct,
  non-user-dismissible visual treatment") applies to it without exception. Opening the
  evidence view must never be a way to see a `SCENARIO` claim's inputs presented without
  that marking — if anything, the deeper view should make explicit *which specific
  inputs* were user-modified (the scenario construction actions, §24.2) versus
  carried over unchanged from the actual portfolio, since that is information a
  Professional-depth reader auditing a scenario would need and that the summary
  comparison table does not have room to show.
- **What this does not do:** it does not create a second Proof Packet schema or a
  scenario-specific Methodology view — both destinations are the ones D4.1 already
  specifies, reached the same way, on Methodology & Evidence (surface 11). Nothing here
  expands D4's scope beyond "structure only," consistent with the rest of D4.

### 8. AI Analyst

**Purpose.** Conversational access to the same deterministic facts, at user-selected
depth. **[F]** §22.1–22.8: mission, controlled tool access, numerical-claim grounding
(P1), insufficient-evidence handling, advice boundary, causal-language restriction,
explanation depth (§22.7, the same four levels as D2), audit record (§22.8).

**Information hierarchy:**
1. Conversational thread, primarily Investor-depth by default **[J]**, since this
   surface is the one place a user actively asks a question and Quick-only would
   under-serve that intent; Quick/Simple/Professional are still user-selectable per
   turn.
2. Every AI-stated numerical claim visibly traces to a tool call output (§22.2's
   controlled tools) — this is the P1 boundary made visible in the UI, not just
   enforced in the engine (T4 is the engineer's structural mechanism; this is the UI's
   corresponding disclosure obligation).
3. Evidence affordance (D4) on every material claim, consistent with §22.8's audit
   record.
4. An explicit, undismissable difference in presentation when the AI is discussing a
   Scenario Lab hypothetical vs. the actual portfolio (P8 again — AI Analyst is the
   second place, after Scenario Lab itself, where this conflation risk is highest,
   because natural language flattens context that a table would preserve).

**Depth model applies:** yes — this is the surface §22.7 names directly, and it uses the
same four levels as D2, not a fifth AI-specific ladder.

### 9. Transactions

**Purpose.** The ledger input surface — where manual positions, transactions, and CSV
imports are entered (§27.1–27.3) and exported (§27.4, FR-034).

**Information hierarchy:**
1. Transaction list, chronological, per account container.
2. Entry/import affordances (manual, CSV) — **[J]** these are data-entry forms, which are
   out of this document's visual-design scope; only their presence and position in the
   IA are specified here.
3. Minimum transaction taxonomy fields (§9.5) must be structurally required at entry,
   not optional-then-silently-missing, because §9.3's missing-cost-basis handling and
   §32's metric-state suppression both depend on knowing what is actually missing versus
   what was never captured.
4. **[Added 2026-09-04, third rework pass, closing the AC-07 gap for surface 9.]**
   Evidence affordance (D4) — option **(a)**, scoped narrowly. Most of what this surface
   shows is not a claim in D2.2's sense: the raw ledger fields a user enters or imports
   (date, ticker, quantity, price in native currency, account) are source facts, not
   computed judgments, and carry no methodology to point to — there is nothing for D4 to
   open for them, which is why item 1's transaction list itself needs no D4 control.
   But this surface's own text already names a computed, methodology-dependent value
   that *is* rendered here: the reporting-currency-converted amount for a transaction,
   which requires an FX rate as of the transaction's date and can carry a §32 state
   (§9.5/§32 note above — "a transaction missing FX history for its date"). That
   conversion is a metric with a registry entry (FX treatment, §33/§34) exactly like
   Holdings' per-position values, not a raw fact, so it gets its own D4 control, opening
   the FX-conversion methodology entry scoped to that transaction's date — independent
   of whether D2's depth ladder applies, since D4/P9 auditability does not require D2's
   ladder to apply (Holdings' item 3 is the precedent: D2 is only partial there too).

**Depth model applies:** no — transactions are facts, not interpretations. §32 metric
states can still apply here (e.g., a transaction missing FX history for its date), so D3
applies even though D2 does not. D4 applies narrowly, to that same computed value, per
item 4 above — this is not a contradiction of "no depth model": D4's affordance is not
a depth level, it is an audit path, and P9 does not require D2 to apply before it binds.

### 10. Portfolio Settings / Policy

**Purpose.** Reporting currency, account container management, and **[F]** §25 Portfolio
Policy — optional user-defined constraints/objectives that §20.3 gives precedence over
generic thresholds, and which P7 requires: the AI may not invent a personalized
constraint that the user did not set here.

**Information hierarchy:**
1. Reporting currency selection (§8.1).
2. Account container management (§7.3).
3. Portfolio Policy definition (§25) — **[J]** this section must make explicit, at the
   point of entry, that leaving a policy field unset means the product will use
   comparative/educational language rather than a fabricated personal threshold (P7) —
   this is a structural disclosure obligation on this surface specifically, since it is
   the only place a user can close that gap.

**[Added 2026-09-04, third rework pass, resolving the AC-07 question for surface 10.]**
**Evidence affordance (D4) — option (c): this surface displays no claims in D2.2's
sense, so AC-07 does not bind it.** All three items are either the product recording a
user's own choice (reporting currency, account containers) or a user *authoring* an
input the rest of the product will later use as a reference point (Portfolio Policy,
per P4/P7) — none of them is the product asserting a conclusion, interpretation, or
judgment about the portfolio that would need a methodology pointer or an audit trail
back to a computation. There is no computed value, no metric state, and no
sufficiency question anywhere on this surface (contrast with Transactions, surface 9,
which looks similar — also configuration-adjacent — but does contain one computed,
methodology-dependent value). Item 3's P7 disclosure is a structural requirement about
*what the product must say elsewhere* when a policy field is unset; it is not itself a
rendered claim on this surface. If a future increment adds a rendered summary here of
*how* the user's policy is currently being applied (e.g., "your policy currently caps
single-position weight at X%, unset for sector"), that summary would need to be
assessed on its own terms at that time — it is not part of this document's surface 10
as specified.

**Depth model applies:** no — these are configuration facts and user-authored inputs,
not interpretations of portfolio data. D4 does not apply either, for the same reason.

### 11. Methodology & Evidence

**Purpose.** **[F]** The destination of the evidence-inspection affordance (D4, P9,
FR-032) and the human-readable face of the methodology registry (§33). This is not a
help page; it is the audit trail's UI.

**Information hierarchy:**
1. Per-metric methodology entries, structured per §33's fifteen required fields
   (definition, formula, annualization convention, data inputs, minimum observations,
   frequency, lookback, benchmark dependency, risk-free-rate dependency, missing-data
   handling, FX treatment, corporate-action treatment, known limitations,
   implementation version, plus metric name — **[J]** counted as fifteen distinct fields
   including metric name itself, consistent with `specs/FEATURE_PRD.md` AC-16's framing).
2. Proof Packet viewer for a specific claim, reached via D4, showing the fields listed
   in source PRD §21 (insight_id, insight_type, severity, claim, judgment_class,
   metrics_used, portfolio_snapshot_id, scenario_id if applicable, comparison_basis,
   benchmark, period, frequency, observations, thresholds/limits if used, source data
   timestamps, methodology versions, data freshness, confidence/availability state,
   limitations, permitted suggested explorations).
3. **[J]** No metric registry *entries* exist yet in this increment (`implement`'s I3
   ships schema and validator with zero entries, per `specs/FEATURE_PRD.md` §3.3). This
   surface's structure is specified now; its content is empty until CP1+ populates the
   registry. This document does not design placeholder/empty-state copy (copywriting is
   out of scope) but does require that an empty registry render as an explicit "not yet
   published" state, not as if the metric does not exist — consistent with D3's
   no-fabricated-fallback rule extended to methodology content.

**[Added 2026-09-04, third rework pass, resolving the AC-07 question for surface 11 —
the coordinator's flagged case.]** **Evidence affordance (D4) — option (c): this surface
is the destination the affordance points to, and does not need a second affordance
pointing at itself.** Two distinct reasons, not one:

- **Item 1, methodology entries, document *method*, not a portfolio-specific
  interpretive claim.** A formula, an annualization convention, a minimum-observation
  count, a known-limitations note — these describe how a metric is computed in general,
  the same way for every user and every portfolio snapshot. D2.2's claim object (one
  conclusion, one reference point, one caveat set, one methodology pointer) exists to
  carry a *judgment about this portfolio's data*; a methodology entry is what the
  methodology pointer *points to*, not a fourth thing that itself needs a pointer.
  Requiring D4 here would not terminate: the methodology entry for "the methodology
  entry's own methodology" is not a coherent object, and P9's auditability requirement
  (traceable to snapshot, inputs, methodology, benchmark, timestamps, limitations) is
  satisfied *by arriving here* — this is the trace's terminus, not another claim to
  further trace.
- **Item 2, the Proof Packet viewer, is the rendering of evidence for a claim that
  lives elsewhere** (the claim's own surface — Insights, Performance, Scenario Lab,
  etc.). Opening a Proof Packet is not itself asserting a new, separate claim about the
  portfolio; it is showing the already-specified fields (§21) behind one. There is
  nothing on this surface for a reader to disbelieve or need to further audit that is
  not already covered by the Proof Packet's own contents.

This is a genuinely different answer from Transactions' (a) and Portfolio Settings'
(c) reasoning, not the same conclusion reached carelessly: Transactions has one hidden
computed value that needed surfacing; Portfolio Settings has no computed content at
all; Methodology & Evidence has computed-adjacent content by the boxful, and the reason
it still doesn't need D4 is structural (it is the trace's end, not a new start), not an
absence of content the way Portfolio Settings is. **This document does not add a D4
control to surface 11**, and this is a considered decision, not an oversight — see the
coordinator's own framing of this as "a real question with a real answer."

**Depth model applies:** no — Methodology & Evidence *is* the Professional/Methodology
level's destination, not a surface that itself has four depths. D4 does not apply
either, and for a related but distinct reason — see above.

### D1 cross-cutting notes

- **[J]** Surfaces 2, 3, 4, 5, 6, 9 are the primary claim-bearing surfaces where D2, D3,
  and D4 all apply concurrently. Surfaces 1 and 8 aggregate claims from the others.
  Surfaces 7, 10, 11 have distinct roles (hypothetical, configuration, audit) that this
  document treats individually above rather than forcing a single template across all
  eleven.
- **AC-04 self-check:** eleven surfaces enumerated above; each states purpose and
  information hierarchy; zero unnamed.
- **[Added 2026-09-15, Post-HG1 Checkpoint A — S1/D3, `designer-33`; corrected 2026-09-15,
  Post-HG1 Checkpoint A correction round — F7, `designer-34`.]** Product and
  prototype chrome (banners, footers, status notes, and any comparable persistent
  surface) must never carry a **mutable** gate/approval-state string — a claim that can
  go stale the moment a human gate decision changes. Only **durable** artifact-status
  language belongs there (e.g. "synthetic data," "design-review prototype," "not a
  production implementation") — facts about what the artifact structurally *is*, which
  do not change when a gate is decided. A gate's current decision is recorded in the
  governing decision record (e.g. a `decisions/product/PD-*` file) — never
  hand-duplicated into UI copy that has no mechanism to stay in sync with it. A generic
  workflow task shard is **not** an equivalent place to look: it may not represent that
  decision at all — this project's own `pm_acceptance` shard is a known representation
  gap (it reads `awaiting_human` while the governing decision record shows HG1
  approved) — so UI copy must not mirror a task shard's status as gate state either, any
  more than it may mirror the decision record's content directly. The same distinction —
  a canonical/raw value is not automatically correct *content to display* — is what
  closes the Scenario Lab machine-value defect under D3 above; both are instances of one
  rule: durability and canonicality are properties of what a string means, not license
  for where or how it may be shown to a reader.

---

## D2. Interaction contract — the four-level depth model

**[F]** Source PRD §6 and §22.7 both specify **Quick → Simple → Investor →
Professional/Methodology**, and §6 states "all layers must use the same underlying
facts." §22.7 gives the canonical one-line definition of each:

- **Quick** — one-sentence conclusion.
- **Simple** — plain-English meaning and implication.
- **Investor** — metric values, comparisons, and context.
- **Professional** — methodology, regression/statistical detail, assumptions,
  limitations.

### D2.1 Movement contract

**[J]** Movement between levels is:

1. **Single-axis and reversible.** One control per claim (not per page) that cycles or
   expands Quick → Simple → Investor → Professional, and any level can return to any
   other directly — it is not a forced linear wizard. This matches §18.2's local
   correlation-UX pattern (quick conclusion → cluster → pairs → matrix → methodology),
   generalized: that pattern is a specialization of D2 for one metric family, not a
   competing model.
2. **Scoped to the claim, not the page.** A user may view one metric at Professional
   depth while the rest of the surface stays at Investor depth. Depth is a per-claim
   reader preference, not a global page mode — this follows from progressive disclosure
   replacing separate retail/professional *products* (§6): if depth were global, the
   product would effectively still be two products toggled by a switch.
3. **A session-level default is allowed** (e.g., "start everything at Simple") but must
   never be the *only* rendering — every claim must remain individually expandable to
   Professional, because P9 auditability and D4's evidence affordance require that path
   to exist from *every* surface that displays a claim, not just from an opt-in expert
   mode.

### D2.2 What is guaranteed preserved across a level change — the structural mechanism

**[F]** P3: simplification may drop precision; it must never drop a caveat that changes
the conclusion. **[J]** The brief for this document requires stating the *mechanism*,
not a reminder to designers. The mechanism specified here:

**All four levels render from one shared claim object, not four independently authored
strings.** Concretely:

- A claim has exactly one **conclusion** (the fact/interpretation/judgment being
  asserted), one **reference point** (P4 — benchmark, policy, or history), one **set of
  caveats** (data-sufficiency state per D3, sample-size/methodology limitations,
  historical-not-forecast labeling per P6), and one **methodology pointer** (D4).
- Quick renders the conclusion alone. Simple renders the conclusion plus plain-English
  caveat. Investor renders conclusion + reference point + values + caveat. Professional
  renders all fields plus the methodology detail.
- **The caveat field is never optional and never dropped by a rendering rule** — a
  rendering may *compress its wording* going from Professional to Quick, but it may not
  *omit* a caveat that would change what the conclusion means. This is enforced by
  making caveat-compression a **wording transform on a fixed field**, not a per-level
  content-selection decision: there is one caveat, and each level has a maximum
  word-budget for expressing it, never a rule that says "Quick has no caveat field."
  **[J]** This is the structural guarantee the brief asks for: a caveat cannot be
  "forgotten" at Quick because Quick's template has a caveat slot, even if compact — it
  is a template contract, not an authoring discipline. Enforcing that the *content* of
  the compressed caveat still changes the reader's conclusion correctly (i.e., the
  compression itself is not misleading) is a wording/methodology judgment reserved to
  `quant_analyst` per this role's `non_responsibilities` — this document specifies that
  the slot must exist and be non-empty whenever the underlying caveat is non-empty; it
  does not author the compressed wording.
- A claim carrying a non-`AVAILABLE` metric state (D3) is not simplified — it renders
  its D3 state at every level, because there is no simpler version of "insufficient
  data" that is not itself a false precision violation.

### D2.3 Worked examples (AC-05)

Per `specs/FEATURE_PRD.md` AC-05, three worked examples drawn from P3, showing what each
depth level says, with no simpler rendering violating what P3 forbids.

**[J]** These are structural content specifications (what each level must and must not
assert), not final copy — copywriting is out of scope for this deliverable. Bracketed
values are illustrative placeholders, not asserted numbers.

#### Example 1 — Beta 1.30

| Level | Must say (structurally) | Must NOT say |
|---|---|---|
| Quick | A one-sentence conclusion naming the direction and magnitude *relative to the market*, e.g. "Your portfolio has historically moved more than the market." | "30% riskier" (P3's own named violation — conflates a linear-regression sensitivity with a percentage risk increase) |
| Simple | Plain-English meaning: moves in the same direction as the benchmark, and historically amplifies benchmark moves by the beta factor — stated as a *tendency observed in the sample period*, not a risk percentage. | Any rewording that reintroduces a percentage-risk framing, or drops "historically"/period-scoping. |
| Investor | The beta value (1.30), the benchmark it is measured against (P4 reference point), the sample window/frequency, and a comparison to the portfolio's own history or a stated threshold if the user has one (P4). | Presenting beta without naming the benchmark or window — a beta with no reference point is exactly what P4 forbids. |
| Professional | Regression methodology, R², sample window and frequency, observation count, data/FX treatment, known limitations — per §17.2's Jensen's-alpha disclosure list, which enumerates the equivalent fields for beta's companion statistic. | Omitting sample size or limitations — that is a P9 auditability failure at the level whose entire purpose is auditability. |

#### Example 2 — Correlation 0.80

**[Amended 2026-09-04, closing `design_review` NF-2.]** The reviewer flagged the original
Quick wording, "these holdings have historically moved together most of the time," as
risking a smaller-magnitude version of the same P3 failure family the example exists to
avoid: correlation measures the strength of a linear co-movement relationship, not a
frequency ("how often"), and "most of the time" is a common informal gloss for a
positive correlation that a reader could reasonably take as a frequency claim (e.g.,
same-sign returns in most periods) rather than what 0.80 actually asserts. **I agree with
this finding and am correcting the wording**, rather than arguing it is acceptable as
illustrative-only content: the document's own scope note (worked examples are
"structural content specifications," not final copy) gives real cover for *exact*
phrasing, but "most of the time" is not a placeholder that happens to be imprecise — it
is a specific, plausible-sounding claim that asserts something the number does not, and
leaving a P3-risking phrase sitting in a document whose entire purpose is demonstrating
P3 compliance would undercut the example's own point even under an illustrative-content
reading.

| Level | Must say | Must NOT say |
|---|---|---|
| Quick | A conclusion about *degree of co-movement in the sample*, e.g. "These holdings have historically moved in the same direction, strongly, over this period." | "Always moves together" — P3's own named violation; 0.80 is not 1.00 and the word "always" asserts certainty the number does not support. **Also must not say** "moved together most of the time" or any other frequency-shaped gloss — correlation measures strength of linear co-movement, not how often returns share direction, and a frequency-shaped phrase asserts a statistic the number does not report. |
| Simple | Plain-English: strong but not perfect co-movement, historically; diversification benefit is reduced but not eliminated. | Dropping "historically" or implying the relationship is guaranteed to continue (P6 — historical statistics are not forecasts). |
| Investor | The coefficient (0.80), the pair/cluster it applies to, the window, and — per §18.2's own required ladder — a cluster interpretation before the raw pairwise number, not instead of it. | Presenting the coefficient with no window or no indication of which two things are correlated. |
| Professional | Full correlation matrix or relevant sub-matrix (§18.2 step 4), calculation window, frequency, missing-data handling. | Suppressing the matrix's limitations (e.g., short window, few observations) at the one level whose job is exactly that disclosure. |

#### Example 3 — Negative Jensen's alpha

| Level | Must say | Must NOT say |
|---|---|---|
| Quick | A one-sentence, valence-neutral conclusion about historical performance relative to what the benchmark and risk (beta) would predict, e.g. "Over this period, returns were below what the benchmark relationship would predict." | "Bad portfolio" — P3's and §17.2's own named violation. Alpha is not a moral or competence judgment. |
| Simple | Plain-English meaning: after adjusting for how much market risk was taken (beta), the actual return fell short of the model-implied return, in this specific historical window. | Any language implying manager skill, fault, or a recommendation to sell — §17.2 explicitly forbids "sell" language being auto-generated from negative alpha. |
| Investor | The alpha value, the benchmark, beta, and the period — matching §17.2's required exposed fields at Investor granularity. | Presenting alpha without beta and benchmark simultaneously — alpha is only interpretable relative to both. |
| Professional | Full §17.2 disclosure set: benchmark, risk-free-rate assumption, beta, alpha, R², sample window, frequency, observation count, and explicit "historical/model-based, not a universal measure of skill" labeling (§17.2's own required label). | Omitting the risk-free-rate assumption or R² — both are named required disclosures in §17.2 and their absence would make the number unauditable (P9). |

### D2.4 Interaction with P1 and P8

- **[J] P1 note.** Every level above renders values sourced from the deterministic
  engine; the depth ladder changes *how much of the engine's own output* is shown and
  *how it is worded*, never *what value* is shown. No level may show a number the AI
  layer computed itself — Quick/Simple wording is generated narration over an engine
  value, not a new estimate. This document does not design the enforcement mechanism
  (that is engineering's T4); it constrains the UI contract so that mechanism has
  something consistent to enforce against.
- **[J] P8 note.** The depth ladder applies identically inside Scenario Lab, but every
  rendering at every level must carry the persistent hypothetical marker described in
  §D1.7 — depth and actual/hypothetical status are orthogonal axes, and collapsing them
  (e.g., only marking hypothetical state at Professional depth, where the text has room)
  would violate P8 for every Quick/Simple reader.

---

## D3. Presentation contract for metric states (§32, P5, FR-028)

### D3.1 States in scope, and the OQ-01 dependency

**[A-05]** Per `specs/FEATURE_PRD.md` assumption A-05, this document treats §32's nine
listed items as:

- **Three sufficiency states:** `AVAILABLE`, `LIMITED`, `INSUFFICIENT_DATA`.
- **Six reason codes**, of which five (`UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`,
  `MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`) explain *why* a metric
  is not `AVAILABLE`, and one (`STALE_DATA`) does not have that shape at all.

**[Amended 2026-09-04, closing `design_review` BF-1.]** `STALE_DATA` is not a peer of the
other five. The other five describe a condition under which a metric *cannot* be
properly computed; `STALE_DATA` describes a metric that computes perfectly well off
inputs that are simply not current — a routine, expected condition given P10/NFR-008
(cross-market prices are never simultaneously real-time), not an exceptional one.
`decisions/product/PD-0006-metric-state-vocabulary-is-layered.md` (as amended) rules
`AVAILABLE` + `STALE_DATA` a valid, required-to-be-representable combination, and couples
the other five to a non-`AVAILABLE` state as a structural rule. §D3.2 below is corrected
to match; this section's dependency on OQ-01/A-05 for the three-vs-nine sufficiency
question (§D3.5) is otherwise unaffected — that question was decided the way A-05
assumed, and remains a three-state sufficiency model. What changed is narrower: which
reason codes may accompany `AVAILABLE`.

A metric's rendering is therefore driven by its sufficiency state, with the reason code
supplying the explanatory text component required by §32's own example ("3Y Beta — N/A.
Insufficient weekly observations.") for the five reason codes that behave that way, and
supplying a freshness-scoped explanatory note (not a sufficiency qualifier) for
`STALE_DATA` when it accompanies `AVAILABLE` — see §D3.2's dedicated row.

### D3.2 Rendering rule per sufficiency state

**[F]** §32 forbids zero, blank, or fabricated fallback values for any non-`AVAILABLE`
state. **[J]** The structural rule that makes a state un-mistakable for a number:

**[Amended 2026-09-04, rework pass, `designer-03`, closing `design_review` BF-1.]** The
original last row of this table (reproduced and struck below) was authored against
assumption A-05 as it stood at the time, which held that a reason code could only ever
modify a non-`AVAILABLE` state. `decisions/product/PD-0006-metric-state-vocabulary-is-layered.md`
(both its first and second amendments) has since decided otherwise, in two different
directions for two different subsets of the six reason codes, and the table below is
corrected to match exactly:

- **Five of the six reason codes** (`UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`,
  `MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`) describe a condition
  under which a metric *cannot* be properly computed. For these, the struck sentence's
  conclusion was right even though its stated reasoning ("a reason code never modifies
  `AVAILABLE`") is now stated as a general rule PD-0006 rejects: PD-0006's second
  amendment makes the coupling explicit and required —
  `reason_code ∈ {those five}` ⇒ `sufficiency_state ≠ AVAILABLE`. This document already
  rendered these five correctly (attached to `LIMITED`/`INSUFFICIENT_DATA` only); nothing
  in their rendering rule changes here.
- **`STALE_DATA` is the one exception**, and it is the one the struck sentence got wrong.
  PD-0006 rules `AVAILABLE` + `STALE_DATA` a valid, expected combination — not an edge
  case, but the routine case, since P10/NFR-008 establish cross-market prices are never
  simultaneously real-time. A new row below specifies its rendering.

This correction is precise, not a retreat to "reason codes are unrelated to sufficiency":
the coupling PD-0006 requires for the five is real and this table still enforces it; only
`STALE_DATA` is carved out, and it is carved out because PD-0006 says so by name, not
because this document is loosening the rule generally.

| Sufficiency state | Renders as | Structural anti-confusion rule |
|---|---|---|
| `AVAILABLE`, no reason code | The computed value, in its normal numeric format, with reference point (P4) and freshness (D5) attached. | **[Corrected 2026-09-04, closing `review-01` round 5 R-D4 — the prior wording ("the only state permitted to render a number at all") is contradicted by rows 2 and 3 below and is struck.]** This is the plain, unqualified numeric render: no D3-level qualifier and no D5 freshness caveat attached at the value's own rendering unit, unlike the next two rows (`AVAILABLE`+`STALE_DATA` attaches a D5 freshness indicator; `LIMITED` attaches a mandatory D3 qualifier). `INSUFFICIENT_DATA` (below) remains the only state that renders **no numeric glyph of any kind** — that guarantee is unchanged. This row and the next two all render a number; what distinguishes them is what non-numeric information accompanies it, not whether a number appears at all. |
| `AVAILABLE` + `STALE_DATA` | **[J]** The identical numeric render to the plain `AVAILABLE` row above — same format, same reference point (P4) — **plus the D5 freshness indicator showing the specific stale axis** (per-market price or FX) in its ordinary D5 rendering, not a D3-style qualifier. No additional label, badge, or qualifier clause is attached at the value's own rendering unit. | This state must be **visually indistinguishable from plain `AVAILABLE` at the value's rendering unit**, because it is not degraded — the number is exactly as computable and exactly as trustworthy as any other `AVAILABLE` value; only its input timing differs, and that is D5's job to disclose, not D3's. The two failure modes this guards against, symmetrically: (a) rendering it identically to `LIMITED` would assert a data-sufficiency problem that does not exist — PD-0006 is explicit that ordinary staleness must not degrade to `LIMITED`'s treatment, since that state would then fire on nearly every cross-market metric and stop carrying information; (b) rendering it with **no** freshness indicator at all would let a reader mistake priced-off-yesterday's-close data for current data, which is exactly what P10/D5 exist to prevent. The reader must be able to tell, from the freshness indicator alone, that this specific value's inputs are not all current — without that indicator ever looking like a sufficiency qualifier. |
| `LIMITED` | The computed value **plus a mandatory, non-dismissible qualifier label in the same visual unit as the value** (not a tooltip-only footnote) naming the specific limitation (short window, thin sample, degraded data quality) and its reason code. | The qualifier is part of the value's rendering unit, not a separate element a layout can drop. A `LIMITED` value must never be visually indistinguishable from an `AVAILABLE` one (with or without `STALE_DATA`) at any depth level, including Quick. |
| `INSUFFICIENT_DATA` | **No numeric glyph of any kind** — not "0", not "0.00", not an em-dash used elsewhere as a numeric placeholder, not a blank cell. Renders as an explicit textual state, e.g. the metric label plus "— insufficient data" plus the reason code's explanation, matching §32's own worked example format. | The rendering unit for this state must be typographically and structurally distinct from the numeric rendering unit — **[J]** specified here as a categorical requirement (distinct component, not a number-shaped field with substituted text), left to visual design to implement, since typography itself is out of this deliverable's scope. |
| The five non-`STALE_DATA` reason codes (`UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`, `MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`) | Attaches as the explanatory clause on whichever sufficiency state it modifies (per D3.1 and PD-0006's second amendment, always `LIMITED` or `INSUFFICIENT_DATA` — **these five reason codes are structurally required to imply a non-`AVAILABLE` state; `AVAILABLE` may never carry one of them**). | A reason code alone, with no sufficiency state, is not a valid render target — the rendering contract is always keyed on sufficiency state first. If an implementer ever encounters one of these five attached to `AVAILABLE`, that is a defect to reject at construction (per AC-15's intent extended to this subset), not a state to render. |

**[Added 2026-09-04.]** The `AVAILABLE` and `LIMITED` rows above have now survived three
separate product-contract challenges unchanged — see
`decisions/product/PD-0007-limited-carries-a-value.md`, whose own amendment records that
this table was "the more faithful reading of §32" than the acceptance criteria that
drifted from it.

**[Amended 2026-09-15, Post-HG1 Checkpoint A — D1, `designer-33`.]** For the `LIMITED`
and `INSUFFICIENT_DATA` rows specifically: when the attached reason text is rendered
inside a dense table cell (Holdings' Unrealized G/L column is the concrete case — §2
item 3), "the same visual unit as the value" must still wrap within that cell rather
than overflow it — a table's own fixed column layout is not license to force a
sentence-length reason onto one unbroken line. This corrects the premise a prior
Holdings implementation pass read into this table (a numeric cell always holds exactly
one short token), which held for a formatted number or short fallback label but not for
a sufficiency reason. The caveat's content and its non-dismissible presence are
unchanged; only its line-wrapping is.

~~Each reason code (`STALE_DATA`, `UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`,
`MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`) attaches as the
explanatory clause on whichever sufficiency state it modifies (per D3.1, always `LIMITED`
or `INSUFFICIENT_DATA` — a reason code never modifies `AVAILABLE`, since if there were a
live blocking reason the metric could not be fully available).~~ **Struck 2026-09-04 —
false for `STALE_DATA` per PD-0006; see the corrected table above.**

### D3.3 Cross-depth-level behavior

Per D2.2's rule that a non-`AVAILABLE` claim is not simplified: `LIMITED` and
`INSUFFICIENT_DATA` renderings are **depth-invariant in kind** (same component, same
non-numeric or qualified-numeric treatment) across Quick/Simple/Investor/Professional.
What changes across depth is only how much explanatory detail accompanies the state
(Quick: label + reason category; Professional: label + reason code + minimum-observation
requirement from the methodology registry, per §33).

### D3.4 Cross-surface consistency

**[J]** The same metric, in the same state, must render with the same non-numeric
treatment on every surface it appears on (e.g., a `LIMITED` beta on Overview's risk
snapshot and on Risk & Analytics' detail view use the same visual/structural pattern,
not surface-specific variants) — this is required for the state to be reliably
recognizable, which is the entire point of §32.

### D3.5 What changes if OQ-01 resolves the other way

**[A-05 dependency, stated per the task brief's requirement.]** If the human product
owner instead reads §32's nine items as a single flat vocabulary with no
sufficiency/reason hierarchy:

- D3.2's table collapses from "3 sufficiency renderings + 6 attachable reasons" to
  potentially **9 independent renderings**, each needing its own non-numeric treatment
  rule, because a flat reading provides no structural basis for treating (say)
  `MISSING_BENCHMARK` as a special case of `INSUFFICIENT_DATA` rather than a state in
  its own right with potentially different UI treatment (e.g., should `MISSING_BENCHMARK`
  still show the *unbenchmarked* raw historical values, since P4 forbids judgment without
  a reference point but does not forbid showing a bare historical fact?).
- The §16.3/§33 "minimum observations" field, which this document attaches to
  `INSUFFICIENT_DATA` specifically, would need re-attaching across whichever of the nine
  states plausibly relate to sample size.
- D3.3's depth-invariance rule would need to be re-derived per state rather than per the
  two-state group used here.
- **This document's D3 section would need rework**, not just relabeling — this is
  flagged as the direct, load-bearing consequence of OQ-01 that the task brief asked to
  be stated plainly.

### D3.6 AC-06 self-check

**[Amended 2026-09-04, closing `design_review` BF-1.]** Every state enumerated (3
sufficiency states, 6 reason codes under A-05, **plus the `AVAILABLE` + `STALE_DATA`
combination that PD-0006 requires to be representable and that the original self-check
did not name**) has a specified rendering; none renders as zero, blank, or a fallback
value; `INSUFFICIENT_DATA` and `LIMITED` are both structurally distinct from a numeric
render; `AVAILABLE` + `STALE_DATA` is structurally *identical* to plain `AVAILABLE` at
the value's own rendering unit, by design, with the distinguishing information carried
by D5's freshness indicator instead — this is deliberate, not an oversight, and is
argued in §D3.2's `AVAILABLE` + `STALE_DATA` row.

---

## D4. Evidence-inspection affordance (P9, FR-032)

### D4.1 The structural path

**[F]** P9: every important insight/numerical claim must be traceable to its snapshot,
inputs, methodology, benchmark, timestamps, limitations. **[F]** §21's Proof Packet
schema is the target content (contents are a later increment; this document specifies
structure only).

**[J]** The affordance is a single, consistently-placed control attached to **every
claim-bearing element**, at every depth level (not only Professional — see below), that
does one of two things depending on claim type:

1. For a metric with a registry entry (§33): opens a **Methodology view**, scoped to
   that metric, showing the registry's fifteen fields (D1's Methodology & Evidence
   surface, §11).
2. For a generated insight (§20) or AI claim (§22): opens a **Proof Packet view**,
   scoped to that specific claim, showing §21's schema fields.

Both destinations live on the Methodology & Evidence surface (surface 11); the
affordance is the *entry point*, reachable from wherever the claim is displayed, not a
duplicate copy of the content embedded on every surface.

### D4.2 Reachability requirement

**[J]** The control is present at **every depth level**, not gated behind Professional.
Rationale: P9 requires auditability of "every important insight," and restricting the
evidence path to Professional depth would make a Quick-depth reader's claim
un-auditable by construction *for that reader* — which the brief's "reachable from
every surface that displays a claim" language forecloses. Professional depth is where
the methodology *detail* is already inline (per D2.2's shared-claim-object model); the
evidence affordance is the same control at every depth, and at Professional it may
simply feel redundant with content already visible, which is acceptable (redundant
access is not a defect; missing access is).

### D4.3 Traced example (AC-07)

**Trace for the Performance surface, headline return claim, at Investor depth:**

1. Performance surface renders "Portfolio return, reporting currency, [period]: [value]"
   with a benchmark comparison (P4) and an evidence-affordance control adjacent to the
   value.
2. User activates the control.
3. Product opens the Methodology & Evidence surface, scoped to the "Portfolio Return"
   registry entry: definition, formula (e.g., time-weighted vs. money-weighted —
   **[J]** which convention is used is a `quant_analyst` methodology decision, not
   specified here), data inputs, FX treatment, corporate-action treatment, known
   limitations, implementation version (§33's fields).
4. If the claim were instead a generated Insight rather than a raw metric (e.g.,
   "your portfolio's concentration increased" from §19 drift detection), the same
   control instead opens the Proof Packet view scoped to that `insight_id`, showing
   §21's fields including `portfolio_snapshot_id`, `comparison_basis`, and
   `source data timestamps` — the mechanism is identical; the destination content
   differs by claim type per D4.1.
5. **Known gap, stated honestly:** because no registry entries exist yet in this
   increment (`implement`'s I3 ships schema only, per `specs/FEATURE_PRD.md` §3.3), this
   trace describes the structural path; the actual content at step 3 is empty until
   CP1+. See D1's Methodology & Evidence "not yet published" requirement.

### D4.4 AC-07 self-check

**[Amended 2026-09-04, closing `design_review` BF-2/R-D2, in three passes.]** The path
(claim → affordance → Methodology view or Proof Packet view, scoped to the claim) is
fully traced for one surface (D4.3, Performance). The three passes below progressively
closed the reachability question this self-check makes, surface by surface, rather than
re-asserting the original document's "structurally present on every claim-bearing
surface" line without support.

**Every one of the eleven D1 surfaces has now been examined. Disposition of each:**

| Surface | Disposition | Reasoning |
|---|---|---|
| 1. Overview | **(a)** for items 1–2; **(b)** for items 3–7 | Items 1–2 (total portfolio value, portfolio-level gain/loss) are aggregation-only claims with no originating surface elsewhere — explicit D4 control. Items 3–7 render the same claim objects their home surfaces render at greater depth; D4.1 attaches the control to the claim object, not the surface, so they inherit it — argued explicitly in §D1. |
| 2. Holdings | **(a)** for item 3; N/A for items 1–2, 4 | Item 3 (per-position cost basis/unrealized gain-loss) is the only claim originating here with nowhere to delegate to — explicit D4 control (item 5). Items 1, 2, 4 are facts or a D5 freshness indicator, not D2.2 claims. |
| 3. Performance | **(a)**, fully traced | D4.3 traces the headline-return claim completely; this is AC-07's literal test. |
| 4. Exposure | **(a)** for items 1–4 | Exposure is the terminal surface for its own exposure/concentration/correlation claims — Overview's item 4 delegates back here, so the delegation must resolve on this surface. Explicit D4 control (item 5). |
| 5. Risk & Analytics | **(a)**, stated from authoring | "Methodology link (D4) on every metric card," per its own §D1 text; unchanged. |
| 6. Insights | **(a)**, stated from authoring | "An evidence affordance (D4) to the Proof Packet," per its own §D1 text; unchanged. |
| 7. Scenario Lab | **(a)** and **(b)**, added pass one | Item 5's evidence affordance on both comparison columns, with the dedicated hypothetical-claim discussion establishing how a `SCENARIO`-typed claim's Proof Packet stays inside P8. |
| 8. AI Analyst | **(a)**, stated from authoring | "Evidence affordance (D4) on every material claim," per its own §D1 text; unchanged. |
| 9. Transactions | **(a)**, narrowly scoped — added pass three | Raw entered/imported ledger fields are facts, not claims, and get no D4 control. But the surface's own text already names a computed, methodology-dependent value rendered here — the reporting-currency FX conversion, which can carry a §32 state when FX history is missing — and that value gets an explicit D4 control (item 4), independent of D2's ladder not applying. |
| 10. Portfolio Settings / Policy | **(c)** — added pass three | Every item is either the product recording a user's own choice or the user authoring a future reference point (P4/P7); nothing here is the product asserting a conclusion or interpretation about the portfolio. No computed value, no metric state, nothing for D4 to open. AC-07 does not bind this surface. |
| 11. Methodology & Evidence | **(c)** — added pass three | This is the destination D4 points *to*, not a claim origin. Methodology entries document method in general, not a portfolio-specific judgment (the methodology pointer's target, not a fourth field needing its own pointer); the Proof Packet viewer renders evidence for a claim that lives on another surface. Requiring D4 to point at itself would not terminate the trace P9 requires — arriving here *is* the termination. Considered and rejected, not skipped. |

**AC-07 is now believed fully satisfied across all eleven D1 surfaces**, on the reading
that the acceptance criterion binds only surfaces that display a claim in D2.2's sense
(P9's "important insight or numerical claim") — surfaces 10 and 11 display none, for
the stated reasons, and are correctly outside AC-07's scope rather than an unexamined
gap in it. Nothing in this table is asserted without the reasoning that produced it
being written down somewhere in this document (§D1, per surface).

---

## D5. Freshness disclosure pattern (P10, FR-033, NFR-008)

### D5.1 The two freshness axes that must never merge

**[F]** §11.2: every market datum exposes source time, freshness state, and
delayed/EOD/live status where known; a universal "live portfolio" label is forbidden
unless every required component legitimately satisfies that condition. **[F]** NFR-008:
trading currency, market identity, calendars, FX, and data freshness must not be
conflated. **[F]** P10: latest-available prices and live FX may have different
freshness states.

**[J]** The structural consequence: freshness is disclosed **per axis**, never
aggregated into one indicator, with at minimum:

1. **Per-market security-price freshness** — one freshness state per listing market
   represented in the portfolio (e.g., US, Mainland China, Hong Kong each carry their
   own state, because their market hours, holidays, and vendor latency differ and §11.2
   requires source time/status per datum).
2. **FX freshness** — a separate state for the FX rate(s) used to convert into reporting
   currency, since FX freshness follows its own vendor/market cycle independent of any
   equity market's.

A single portfolio-level rollup freshness indicator is **not permitted** to replace
these — it may exist *in addition*, but only if it can never legitimately claim "live"
for the whole portfolio when any one component is not (§11.2's explicit prohibition).
**[J]** Given how rarely all axes would be simultaneously live across a US+CN+HK
portfolio, this document treats a portfolio-level "all live" state as achievable only
when every displayed axis independently qualifies — the UI must not shortcut this by
defaulting to an optimistic aggregate.

### D5.2 Where freshness appears

Per D1: a freshness indicator is required next to the value it qualifies, on Overview
(portfolio-level summary of per-axis states, not a single blended state), Holdings
(per-position, since a position's market determines its price-freshness axis),
Performance and Risk & Analytics (as of the timestamps used for the calculation, which
is a distinct concept from *current* freshness — see D5.4), and anywhere Exposure or
Insights displays a value derived from mixed-market inputs.

### D5.3 Rendering states

**[J]** Minimum distinguishable states per axis, consistent with §11.2's
delayed/EOD/live vocabulary: `LIVE`, `DELAYED` (with delay magnitude if known),
`END_OF_DAY`, `STALE` (beyond expected refresh window).

**[Amended 2026-09-04, closing `design_review` BF-1 fallout.]** This axis's relationship
to §32's `STALE_DATA` reason code is now two-cased, not one, per
`decisions/product/PD-0006-metric-state-vocabulary-is-layered.md`:

1. **The routine case:** a `STALE`-axis price feeds a metric that remains `AVAILABLE`.
   §32's `STALE_DATA` reason code attaches to that `AVAILABLE` metric (§D3.2's dedicated
   row), and the D5 freshness indicator is the only visible signal of the staleness —
   no D3-style qualifier appears, because the metric is not degraded.
2. **The threshold case:** a `quant_analyst`-set threshold (not specified in this
   document or by this decision) judges the staleness severe enough that the metric
   drops to `LIMITED` or `INSUFFICIENT_DATA` on those grounds — only *here* does
   `STALE_DATA` behave like §D3.2's other five reason codes and attach to a degraded
   sufficiency state.

In both cases, the freshness indicator itself remains a data-provenance display, not a
metric-state render, and the two components must not be collapsed into one — that
requirement is unchanged. What changed is that case 1 is now understood to be the common
case, not an excluded one: this section's original text assumed `STALE_DATA` only ever
co-occurred with a demoted metric, which PD-0006 has superseded.

### D5.4 Worked mixed-freshness cross-market case (AC-08)

**Portfolio:** holds a US-listed stock, a Hong Kong-listed stock, and cash in CNY, with
reporting currency USD.

**Structural disclosure requirement, per axis:**

| Axis | Example state (illustrative, not asserted data) | Why it can legitimately differ |
|---|---|---|
| US equity price | `LIVE` (during US market hours) or `END_OF_DAY` (after close) | Follows US market hours/calendar (NFR-008). |
| Hong Kong equity price | `END_OF_DAY` (HK market closed while US is open, given the time-zone offset) | Follows HK market hours/calendar — independently of the US axis's state. |
| USD/HKD FX | Its own state, e.g. `DELAYED` by a vendor-specific interval | FX vendors and equity vendors are independent data sources (§11.1's separate `FXRate` contract) and must not inherit either equity axis's freshness. |
| USD/CNY FX | Its own state, independently of USD/HKD | Two different currency pairs are two different data points, not one "FX freshness" blob. |

**What the Overview/portfolio-level summary must show:** a compact representation that
**names the least-fresh axis among those in use** (so a reader is never more confident
than the weakest link) **and does not merge the per-axis states into a single "as of"
timestamp** that would erase which axis is behind. **[J]** The specific compact
visual/copy form is out of scope (visual design/copywriting); the requirement is that
the underlying data model and IA make per-axis detail reachable from that summary (this
is itself an instance of D4's evidence-affordance pattern applied to freshness rather
than to a financial claim).

**What must never happen:** a single "Live" or single timestamp label applied to the
whole portfolio view when the US equity is live but the HK equity is necessarily
end-of-day relative to it — this is precisely the case §11.2 names as forbidden.

### D5.5 AC-08 self-check

Per-market price freshness and FX freshness are specified as distinct, independently
rendered axes; the worked case shows at least two equity markets and two FX pairs with
plausibly different states; no rendering implies uniform real-time data.

---

## Cross-cutting: P8 mechanism across surfaces (D1.7 reference)

**[J]** Because P8 recurs across Overview, Holdings, Scenario Lab, and AI Analyst, the
mechanism is stated once, here, rather than four times:

- **Actual portfolio state and Scenario Lab hypothetical state are never rendered inside
  the same claim object.** A claim (per D2.2's shared-object model) carries a
  `state_type` field with exactly two values, `ACTUAL` or `SCENARIO`, and every
  rendering surface (component) that can display a claim is keyed to render `ACTUAL` and
  `SCENARIO` claims with permanently distinct, non-user-dismissible visual treatment —
  never a toggle that silently replaces one with the other without the distinguishing
  treatment persisting.
- Overview and Holdings render `ACTUAL` claims exclusively — **[J]** they structurally
  cannot render a `SCENARIO`-typed claim at all; there is no code path, per this IA, by
  which a Scenario Lab result reaches those two surfaces. This is stronger than "labeled
  clearly" and is the direct answer to P8's "strictly separated."
  the Scenario Lab surface and AI Analyst render both types, always with the
  distinguishing treatment attached at the claim level (not the page level), so a
  scrolled or partially-rendered view cannot lose the marker.

---

## Known limitations and unresolved items

- **OQ-01 dependency (§32 vocabulary).** D3 is authored against A-05's sufficiency +
  reason-code reading. §D3.5 states the rework required if the human owner resolves it
  the other way. This is the single largest open risk to this document's D3 section
  surviving HG1 unchanged.
- **No visual design.** Every "renders as," "distinct component," and "non-dismissible"
  requirement in this document is a structural/behavioral constraint, not a mockup.
  Typography, color, iconography, and exact copy are unspecified by design (out of
  scope for this increment) and will need a follow-on visual-design pass before
  engineering can build against this document directly.
- **No copywriting.** Worked examples in D2.3 specify what each level must and must not
  assert structurally; they are not final user-facing strings. A wording pass by
  whoever owns copy (unassigned in this increment) is required before implementation,
  and per this role's non-responsibilities, any wording that changes what a statistic
  asserts is `quant_analyst`'s call, not this document's.
- **Methodology & Evidence surface has no content yet.** Its structure is specified;
  the registry it displays ships empty in this increment (`specs/FEATURE_PRD.md` §3.3,
  I3). The "not yet published" empty-state requirement (D1, surface 11) is specified
  but not designed in detail (that would be visual/copy work).
- **Per-claim vs. per-page depth state persistence is unspecified.** D2.1 requires depth
  to be a per-claim property, but this document does not specify whether a user's chosen
  depth for one claim persists across a session, a page reload, or transfers to
  "similar" claims elsewhere. This is an interaction-detail gap that the next design
  pass (post-HG1, once there is a real surface to design against) should close.
- **Scenario Lab's `SCENARIO`-typed claims and D3 metric states interact untested.**
  §D1 surface 7 states that scenario outputs still carry metric states, and the P8
  mechanism states `SCENARIO` claims never reach Overview/Holdings — but this document
  does not work through, e.g., what an `INSUFFICIENT_DATA` scenario metric looks like
  next to an `AVAILABLE` actual metric in the same comparison table. Flagged, not
  resolved.
- **AC-16's "fifteen fields" count.** §33 lists fourteen bulleted items in addition to
  "metric name" appearing in the lead sentence ("For every metric, store/version:" —
  metric name, then fourteen bulleted fields) which this document reads as fifteen total
  fields per `specs/FEATURE_PRD.md` AC-16's own framing. **[A]** Flagging this as a
  literal-count assumption rather than re-deriving it, since the registry schema itself
  is `tech_planning`/`implement` authority, not this document's.
- **No accessibility review performed.** This role holds a veto over implementation that
  "materially violates approved design/accessibility requirements" per
  `roles/designer.json`, but no accessibility standard is cited in the source PRD or
  `specs/FEATURE_PRD.md` for this increment, and none is asserted here. This is a gap to
  raise, not an assumption to fill silently.
- **Cross-surface consistency (D3.4, D5's per-axis model) is stated as a requirement but
  not validated against any concrete component inventory**, because no component
  library exists yet (explicitly out of scope). Validation is deferred to whichever
  increment builds the actual UI (CP7, per `specs/FEATURE_PRD.md`'s deferred-items
  table).
- **[Added 2026-09-04, closing `design_review` NF-1/AC-21.]** **D2.2's caveat mechanism
  guarantees the caveat slot is non-empty; it does not guarantee the compressed wording
  still means what the full caveat means.** The structural guarantee (a caveat cannot be
  "forgotten" because every level's template has a caveat slot) is real and is enforced
  by this document. What it does not do, and cannot do from within this role's authority,
  is guarantee that a specific compression — say, Professional's full sample-size caveat
  compressed to Quick's word budget — still changes the reader's conclusion the same way
  the full caveat does. §D2.2 correctly routes "wording that changes what a statistic
  asserts" to `quant_analyst`, consistent with this role's own non-responsibilities, but
  no checkpoint currently requires that review to happen before a compressed caveat
  ships. **What would close this gap:** a named review step — `quant_analyst`
  certification of each level's compressed caveat wording against its full-caveat
  meaning, at or before the point copywriting is done (itself unassigned in this
  increment, see above) — added to the workflow that eventually authors real copy. That
  role and gate are unassigned in this increment; naming them is a workflow/PM decision,
  not one this document can make unilaterally, so it is recorded here rather than
  invented.
- **[Added 2026-09-04, closing `design_review` NF-3/AC-21.]** **The shared claim object
  (D2.2) has no named slot for D5 freshness data.** D2.2 defines a claim as carrying
  exactly one conclusion, one reference point, one caveat set, and one methodology
  pointer — four fields, and the enumeration reads as exhaustive. D5.2 requires a
  freshness indicator next to the value it qualifies, and D5.3 requires it to stay a
  distinct component from a D3 metric-state render, but neither D2 nor D5 says whether
  freshness is a fifth field on the same claim object, a sibling object keyed to the
  same claim, or something else — the object model this document specifies simply does
  not name where it attaches. This is the design-side half of the gap
  `reviews/gates/CP0_RECONCILIATION.md` §3.1 discloses from the tech-plan side
  (`MetricResult` carries no freshness field either). **This gap is not closed here, by
  design** — `CP0_RECONCILIATION.md` §3.1 already routes it to `technical_review`/HG1 as
  a visible open item, and `technical_review` has since found that the technical carrier
  for this data already exists (the Computation Manifest pins per-market and FX
  references separately), which narrows the remaining question to *where the design's
  own claim object names it*, not whether the data is obtainable. Recording it honestly
  here, rather than silently filling it, is the correct move for a decision that belongs
  to whoever next revises D2.2's object model with a real surface to design against.
- **[Added 2026-09-04, first rework pass; closed 2026-09-04, second rework pass.]**
  D4's evidence-affordance reachability was initially left unstated, in their own §D1
  sections, for Overview, Holdings, and Exposure — recorded here as an open item rather
  than asserted without support. It is now closed per-surface: Holdings and Exposure
  each carry an explicit D4 line (§D1, Holdings item 5, Exposure item 5) because each is
  the originating or terminal surface for its own claims with nowhere else to delegate
  to; Overview's items 1–2 (portfolio value, portfolio gain/loss) carry their own
  explicit line for the same reason, and items 3–7 are argued, in Overview's own §D1
  text, to inherit their home surfaces' D4 control via D2.2/D4.1's claim-object
  mechanism rather than needing a restated one. See §D4.4's self-check for the full
  accounting. This bullet is retained, marked closed, rather than deleted, so the record
  of what was open and how it closed is not lost.
- **[Noticed 2026-09-04, second rework pass; resolved 2026-09-04, third rework pass.]**
  §D1's own cross-cutting notes name Transactions (surface 9) as one of the surfaces
  "where D2, D3, and D4 all apply concurrently," but Transactions' own §D1 section
  originally named only D3 and not D4 — the same shape of gap the second pass had just
  closed for Overview/Holdings/Exposure. `design_review`'s BF-2 table did not check
  Transactions, Portfolio Settings/Policy, or Methodology & Evidence, so this was
  genuinely unexamined territory rather than a re-litigated finding. The third pass
  examined all three: Transactions now has an explicit, narrowly-scoped D4 line (§D1
  item 4, on its one computed FX-conversion value only); Portfolio Settings/Policy and
  Methodology & Evidence were each found, on their own terms, to display no claim in
  D2.2's sense that AC-07 binds — recorded as such in their own §D1 sections and in
  §D4.4's self-check table, not silently assumed. All eleven D1 surfaces have now been
  examined at least once for this question; see §D4.4 for the per-surface disposition.

---

## Traceability back to `specs/FEATURE_PRD.md` §3.1 / §11

| Deliverable | Section | Acceptance criterion | Status |
|---|---|---|---|
| D1 | information architecture, §D1 | AC-04 | Believed satisfied — eleven surfaces, each with purpose + hierarchy |
| D2 | depth-model interaction contract, §D2 | AC-05 | Believed satisfied — mechanism stated, three worked examples provided |
| D3 | metric-state presentation, §D3 | AC-06 | **Amended 2026-09-04.** `AVAILABLE` + `STALE_DATA` now has a specified rendering (§D3.2); the five non-`STALE_DATA` reason codes' required coupling to non-`AVAILABLE` is stated explicitly. Believed satisfied under A-05; OQ-01 risk (flat-vs-layered vocabulary) stated in §D3.5 remains open pending HG1 confirmation of PD-0006. |
| D4 | evidence affordance, §D4 | AC-07 | **Amended 2026-09-04, three passes.** Path traced fully for one surface (Performance, §D4.3). All eleven D1 surfaces have now been examined and disposed of explicitly (§D4.4's table): nine display at least one claim and are covered by an explicit D4 line or an argued claim-object-inheritance case (Overview, Holdings, Performance, Exposure, Risk & Analytics, Insights, Scenario Lab, AI Analyst, and Transactions — the last narrowly, for its one computed FX-conversion value only); two (Portfolio Settings/Policy, Methodology & Evidence) display no claim in D2.2's sense and are correctly outside AC-07's scope, with the reasoning stated in their own §D1 sections rather than asserted by omission. **Believed fully satisfied across all eleven surfaces.** |
| D5 | freshness disclosure, §D5 | AC-08 | Believed satisfied — two-axis model, worked mixed-market case provided. §D5.3 amended 2026-09-04 to state the routine `AVAILABLE`+`STALE_DATA` case correctly (previously assumed staleness only co-occurred with a demoted metric). |
| — | Known limitations, this section | AC-21 | Satisfied — non-empty, honest; two additional gaps (caveat-compression verification checkpoint, D5 freshness field's home in the claim object) added 2026-09-04 per `design_review` NF-1/NF-3. |

---

## HG4 condition 2: the root's generation on the real screen (2026-11-17)

Status: design for review. Source: PD-0089 condition 2 ("fix the list's generation label, with design and technical review, before
real results are shown to anyone but you"); TR8SR finding M-1; `reviews/gates/HG4_GATE_REVIEW.md` 8.3. This file has no earlier
real-mode (CP7 F1) area, so the section is appended here. Designer wrote this; the Engineer implements; the technical reviewer
verifies. Wording below asserts nothing the stored data does not.

### G1. What the code already holds (read-only findings)

| Question | Finding | Where |
|---|---|---|
| What is the list's "Generation N"? | The context's CURRENT head generation. `rw_list_roots` joins `rw_head` on the context and returns `h.generation`. | `src/persistence/real_workspace_v1.sql:317-321` |
| Is it also what the entry is admitted at? | Yes. The list passes that head generation to `store.admit(... ARCHIVE_READ ...)`, and the entry is built with the same value. So a readable entry's N is the current generation by construction. | `src/real_service/service.py:453-454, 467-468, 480` |
| Is the root's own bound generation stored? | Yes. It is written at create from the create lease into `rw_artifact` and `rw_operation` (`l.generation`) and into the sealed envelope (`"generation": lease.generation`). The root link (`rw_root_link`) and `rw_root` hold only `context_id`, never a generation. `rw_revision` holds none. | `src/persistence/real_fence_v1.sql:530-531`; `service.py:485-490`; `real_workspace_v1.sql:110-116`; `real_fence_v1.sql:46-87` |
| Is the stored value checked? | Yes. `rw_check_*` requires the envelope's `generation` to equal the artifact's, and `rw_archive` requires the operation row's generation to equal the artifact's. | `real_fence_v1.sql:394`, `:550` |
| Can the server already read it with no new SQL or grants? | Yes. `rw_archive` returns the envelope bytes, and the read route already calls it (`archive_read` -> `self._archive`, which becomes `Archive.envelope`). `json.loads(archive.envelope)["generation"]` is the bound generation. The fictional reproduce already does this (`envelope["generation"]`). No new function, table or grant. (I found no per-role GRANT text for `rw_archive` in `src/`; the app role already executes it for every read, so reusing the same call needs none. The Engineer confirms against the installed grants without opening the cluster.) | `service.py:211-212, 373-379, 398-410` |
| Does the real reproduce use the bound generation? | No. Only the fictional branch does. `_reproduce_real` rebuilds from the snapshot under the CURRENT lease. This is harmless: `context_id` is the SHA-256 of the snapshot (`rw_snapshot` check, `real_workspace_v1.sql:60`), so the data under a context never changes across generations. A generation is a permission epoch, not a data version. | `service.py:415-438` |
| What does the list's per-root status convey? | Only the refusal code of the admission at the current generation (for example `RW_WITHDRAWN`: "The context has been withdrawn"). A refused entry carries no generation, no creation time and no origin, by contract. So it says "cannot be read now", never "created under". | `service.py:457-460`; `real_scoped_contract.py:330-340`, `:73` |
| Does the opened result show any generation? | No. `RootDetail` shows root, operation, revision, ledger pin and digests only; `READ_SCHEMA` `finweb.cp7.real_scoped_read/1` has no generation field. | `web/src/RealModeApp.tsx:149-156`; `real_scoped_contract.py:303-318` |

Conclusion: the screen's single number is true but mislabelled, and the number the owner expects (the root's own) is available
without SQL or grant changes, in the read path that already holds the envelope.

### G2. Decision

Two numbers exist, with two different meanings; the screen must never show one under the other's name.

1. **List: relabel only.** The list keeps showing the context's current generation, named as such. No server change, no schema
   change. (Chosen over "show the stored generation in the list": that would require one extra stored-bundle read and
   a `rw_check_artifact` per root on every list refresh, and a failure there would turn a readable entry into a refused one.
   The list is an index; the root's own binding belongs on the root.)
2. **Opened result: add the root's own generation, "created under".** One new read-contract field, taken from the envelope the
   read already loaded.
3. **One explanatory note** under the list heading, so a renew or withdraw is not misread as acting on a root.

### G3. Exact text (`web/src/real-mode-i18n.ts`)

The key `generation` is retired from the list (do not reuse the bare word "Generation" next to a root anywhere on this screen).
New keys:

| Key | English | Chinese (zh-CN) |
|---|---|---|
| `contextGenerationNow` | `Context now at generation` | `上下文当前代次` |
| `createdUnderGeneration` | `Created under generation` | `创建时所在代次` |
| `generationNote` | `Generation is the context's permission version, not a property of a root. A renew or a withdrawal changes the generation shown for every root in that context. It does not create, re-bind or change a stored root. The generation a root was created under is shown when you open it.` | `代次是上下文的授权版本，不是根的属性。续期或撤回会改变该上下文下每个根所显示的代次，但不会创建、重新绑定或更改已保存的根。每个根创建时所在的代次在打开后显示。` |

Placement:

- **List entry** (`RootEntries`, `RealModeApp.tsx:134`): `{contextGenerationNow} {N} · {createdAt} {time} · {origin tag} [Open]`.
  English example: `Context now at generation 3 · Created 2026-11-16T... · Real source`.
  Chinese example: `上下文当前代次 3 · 创建时间 2026-11-16T... · 真实来源`.
  `generationNote` appears once, as a small paragraph between the "Your roots" heading and the list (not per row, not a tooltip,
  because a tooltip is invisible on touch and to a reader who does not hover).
- **Refused entry**: unchanged ("Not readable now: RW_WITHDRAWN"). It shows no generation, by contract. Do not add one.
- **Opened result** (`RootDetail` `<dl>`, after Ledger pin): `<dt>{createdUnderGeneration}</dt><dd>{N}</dd>`.
  Visible at every depth level (it is an identifier, like the ledger pin, not an explanation).
- **Reproduce result**: no generation shown (it does not depend on one, see G1).

What the reader should understand: the number beside a root in the list is where the context stands now; the number inside the
opened root is where the root began; they can differ, and a difference is a permission event on the context (renew or
withdraw), not a change to the root. The page does not say the root is "valid", "approved" or "current", and does not predict
that a later generation will or will not be readable.

### G4. Contract change (the only one)

- `READ_SCHEMA`: `finweb.cp7.real_scoped_read/1` -> `finweb.cp7.real_scoped_read/2`. One new required field,
  `created_under_generation` (integer, >= 1), in `read_payload` (`real_scoped_contract.py:303`), filled in the read route from
  `json.loads(archive.envelope)["generation"]` (already loaded; no second read, no second admission).
- `web/src/real-mode.ts`: add the field to the read parser's exact key set (reject missing, non-integer or < 1) and to the
  `RealRoot` type; render it in `RootDetail`.
- `LIST_SCHEMA` `real_scoped_list/2`: unchanged shape. The wire field `generation` keeps its name, and the contract docstring
  (`list_entry`, :330) states it is the context's current generation. If the reviewer prefers renaming to `current_generation`,
  that is a `/3` bump and a larger blast radius; this design does not require it.
- Installed SQL: no change. Grants: no change. Migrations: none. Nothing here needs the owner's approval for a database change.
  The contract bump is a code-only change inside the Engineer's paths and goes through technical review.
- Create-result (`CREATE_RESULT_SCHEMA`): unchanged.

### G5. Acceptance checks

Engineer (tests actually run, results reported):

1. Web, list rendering: an entry `generation: 3` renders `Context now at generation 3` (en) and `上下文当前代次 3` (zh-CN), and the
   rendered list contains no `Generation` word adjacent to a root other than inside `generationNote`. The existing check at
   `real-mode.test.ts:420` is updated to the new text.
2. Web, note: `generationNote` renders once above the list when there is at least one root, in both locales, and is absent in the empty state.
3. Web, refused entry: `RW_WITHDRAWN` entry still renders `Not readable now: RW_WITHDRAWN` and no generation.
4. Web, opened result: `created_under_generation: 1` renders `Created under generation 1` / `创建时所在代次 1`; the parser rejects
   a missing field, `0`, `1.5`, a string and a value above the safe-integer range.
5. Server, read payload: for a root created at generation 1 whose context head is 3, `archive_read` at generation 3 yields
   `created_under_generation == 1`, equal to the envelope's `generation`, while the list entry for the same root carries `generation == 3`.
   (Use the existing renew/withdraw test fixtures; no real cluster.)
6. Server, no extra surface: the diff touches no `.sql` file, no grant script and no migration; the list route issues no
   additional query (same count as before).
7. The contract docstring names the list `generation` as the context's current generation.

Reviewer (independent):

1. R8 case, by reading and by fixture: root created at generation 1, withdraw to 2, renew to 3. List shows `Context now at
   generation 3` beside the unchanged creation time, with the note visible. Opened result shows `Created under generation 1`.
   Neither screen implies the renew created or re-bound the root. (The live R8 confirmation on the owner's real root is the
   main session's step, after deployment; this design did not open the cluster.)
2. Mid-withdrawal view (head at 2): the entry is refused with `RW_WITHDRAWN`, shows no generation, and the page claims nothing about why.
3. Confirm `created_under_generation` is read from the stored envelope (cross-checked by `real_fence_v1.sql:394`/`:550`), not from
   `rw_head`, the lease, or a constant.
4. Confirm no wording says valid, approved, current-for-the-root or predicts future readability (P6), and that the note keeps the
   caveat that a generation change is a context event (P3).
5. Both locales reviewed for the same assertion (no English-only caveat).

### G6. Assumed and open

- Assumed: the app role may already execute `rw_archive` and the read route's envelope is available after the existing `_archive_of`
  parse; if the Engineer finds otherwise, stop and report to the main session before any grant change (owner approval needed).
- Assumed: showing the root's own generation only after it is opened is acceptable. If the owner wants it in the list too, that
  costs one stored-bundle read per root per refresh and a new list schema; it is a scope decision for the PM, not required by condition 2.
- Open for the Quant/PM: whether the opened result should also show the current admission generation (the guarded archive
  panel does, `guarded-i18n.ts:29`). Not needed to fix M-1, so not specified here.
- Open: the same-session check on the owner's real R8 root after the change (main session, post-deploy).
