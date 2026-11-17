# HG1 revision-2 prototype — `designs/hg1-prototype-v2/`

## What this is, and what it is not

**It is** the revised feature-representative interactive prototype the human product
owner requested in `reviews/gates/HG1_DIRECTION_SELECTION.md` §2 item 11, built against
the selected Direction C ("Briefing Room") + Direction B ("Analyst Desk" visualization
graft) direction. Its purpose is to let the owner *experience* the intended end-to-end
V1 design — navigation, Overview, Portfolio construction/ingestion, Analytics breadth,
Scenario Lab, contextual AI, and the evidence/methodology/freshness/metric-state
machinery — in a real browser, so HG1 can be reconsidered on something more concrete
than 1,100+ lines of specification.

**It is not:**
- **CP1 implementation.** Nothing here is production code. There is no backend, no
  database, no brokerage connection, no authentication, no live market data, and no
  production AI model call.
- **An approval of anything, and not itself an approval record.** HG1 was subsequently
  APPROVED — see `decisions/product/PD-0017-hg1-approved.md`, the authority for the HG1
  decision, decided by the designated human product owner. This directory remains a
  design/prototype artifact, not production implementation, and it does not and cannot
  itself constitute or supersede that decision. (Historically — see
  `reviews/gates/HG1_DIRECTION_SELECTION.md` §4, "not a workflow task" — building this
  prototype was never treated as a gate decision either; that reasoning still holds, it
  is simply no longer the open question it once was.) **Do not read `pm_acceptance` in
  the DAG (`project-state.json`) as evidence of HG1's status**: `pm_acceptance =
  awaiting_human` is the project's known state-model representation gap (the task that
  formally carries HG1 remains blocked behind `implement`/`design_review`/
  `technical_review` under PD-0004's DAG resolution, independent of the gate decision
  itself — see PD-0017 §3) and does not supersede PD-0017.
- **A scope-reduction exercise.** Per the owner's own instruction (§1 of the direction
  selection): a feature absent from a screen here is not therefore out of V1 scope.
- **Certified analytics.** Every number is derived from a single seeded synthetic
  random-walk series (see "Data" below) — internally consistent, but illustrative, not a
  real portfolio's real performance.

## Data

All data is synthetic, generated deterministically from a fixed-seed PRNG in
`js/data.js` (same seed, same output, every load — see `js/data.js` §0). Returns,
volatility, beta, alpha, Sharpe, Sortino, drawdown, tracking error, VaR, correlation, and
contribution-to-risk are all computed from the same underlying return series, so numbers
that should agree across surfaces (e.g. portfolio return shown on Overview and on
Analytics) do agree, by construction — not by hand-reconciliation.

## Running it

No build step, no dependencies, no package manager. Serve the directory over plain HTTP
(opening `index.html` directly via `file://` will 404 the module scripts in some
browsers' security models — use a local server):

```bash
cd designs/hg1-prototype-v2
python3 -m http.server 8080
```

Then open **http://localhost:8080/** in a browser.

**External hosting is not available.** This harness has no network egress and no hosting
capability (`platform-capabilities.json`). If the owner needs to review this somewhere
other than a machine that can run the command above, that is a human provisioning step,
not something this prototype or its build process can supply.

## Route map

Hash-based routing, shape `#/<group>/<surfaceKey>`:

| Route | Surface | Owning file |
|---|---|---|
| `#/overview` | Overview — portfolio command center | `js/surfaces/overview.js` |
| `#/portfolio/portfolio` | Holdings & Activity (holdings, accounts/cash, transactions, manual entry) | `js/surfaces/portfolio.js` |
| `#/portfolio/ingest` | Import & Ingestion (CSV + OCR-assisted) | `js/surfaces/ingest.js` |
| `#/analytics` | Analytics (performance, risk grid, rolling/drawdown, SML/CAPM, exposure, correlation, contribution-to-risk) | `js/surfaces/analytics.js` |
| `#/scenario` | Scenario Lab | `js/surfaces/scenario.js` |

Not a route, reached contextually from anywhere:
- **AI Analyst** — header "Ask your portfolio" button, or any inline "Ask about
  this…" affordance — opens a right-side overlay (`js/ai.js`).
- **Evidence & Methodology** — any "Evidence & Methodology" control, or the footer
  "Methodology & Evidence Registry" link (browse-all) — opens a right-side overlay
  (`js/evidence.js`).
- **Portfolio Settings / Policy** — the gear icon in the header — opens an overlay
  built directly in `js/shell.js` (no phase-2 file owns it; see `CONTRACT.md` §8).
- **Focus-and-inspect dock** — the collapsible right-docked panel (Direction B graft),
  opened by clicking a chart point or a metric cell on Analytics/Portfolio.

## File / ownership map

Built in three phases; this pass (phase 3, `designer-14`) owns the entire directory,
having verified phase 2 is finished and nothing is concurrent.

| File | Phase / owner | Notes |
|---|---|---|
| `index.html` | 1 — `designer-09` | Script load order is the contract; do not reorder (`CONTRACT.md` §1). |
| `styles/tokens.css` | 1 — `designer-09` | Design tokens; every color/spacing/radius/shadow used anywhere must come from here. |
| `styles/app.css` | 1 — `designer-09`, **extended 3 — `designer-14`** | See "What changed in this integration pass" below — most of the CSS gap this pass closed lives here. |
| `js/shell.js` | 1 — `designer-09`, **extended 3 — `designer-14`** | Router, shared UI primitives (`APP.ui.*`), metric-state renderer, evidence/AI overlay plumbing. Added `APP.ui.selectorHTML` this pass. |
| `js/data.js` | 1 — `designer-09`, **extended 3 — `designer-14`** | Synthetic dataset + accessors (`APP.data.*`). Added `metric.totalPortfolioValue`, the scenario-comparison claim registry, and two small fixes this pass — see below. |
| `js/charts.js` | 1 — `designer-09` | Hand-authored SVG chart primitives (`APP.charts.*`). Unchanged this pass. |
| `js/surfaces/overview.js` | 2 — `designer-10`, **edited 3 — `designer-14`** | Total-value wiring + evidence controls added this pass; everything else unchanged. |
| `js/surfaces/portfolio.js` | 2 — `designer-11` | Unchanged this pass. |
| `js/surfaces/ingest.js` | 2 — `designer-11` | Unchanged this pass. |
| `js/surfaces/analytics.js` | 2 — `designer-12` | Unchanged this pass (its CSS gap was closed in `styles/app.css`, not here). |
| `js/surfaces/scenario.js` | 2 — `designer-13`, **edited 3 — `designer-14`** | `scenarioSideClaim` now delegates to the new shared accessor; everything else unchanged. |
| `js/ai.js` | 2 — `designer-13`, **edited 3 — `designer-14`** | Same delegation fix, plus one worked example of the new selector-digit mechanism. |
| `js/evidence.js` | 2 — `designer-13`, **edited 3 — `designer-14`** | Now also resolves a scenario-comparison claim for the "key number" step. |
| `CONTRACT.md` | 1 — `designer-09`, **extended 3 — `designer-14`** | The module contract phase-2 authors built against; this pass's addendum is at its top. |
| `README.md`, `HUMAN_REVIEW_CHECKLIST.md`, `SIMULATED_VS_IMPLEMENTED.md` | 3 — `designer-14` | New this pass. |

## What changed in this integration pass (summary — see handoff for the full account)

1. **CSS gap closed.** A systematic extract-and-diff sweep (every class name any surface
   file assigns, diffed against what `styles/app.css` defined) found roughly 90 orphaned
   class names, concentrated in `js/surfaces/scenario.js` (which had **zero** rules —
   Scenario Lab rendered as unstyled stacked text before this pass), `js/ai.js`, and
   `js/evidence.js`, plus the class names `analytics.js`'s own author had already flagged.
   All now have rules, in the established token-based visual language.
2. **`metric.totalPortfolioValue` added** and wired to Overview, with its own D4 evidence
   control — closing the gap `designs/FEATURE_DESIGN.md` §D1 surface 1 names explicitly.
3. **Scenario-side evidence gap closed** — every composite claim id `scenario.js`/`ai.js`
   construct for a SCENARIO-side comparison figure now has a real registered Proof
   Packet, via a new shared accessor (`APP.data.getScenarioComparisonClaim`) both files
   delegate to instead of each building the object locally.
4. **`checkNarrativeSafety` scanner refined** with `APP.ui.selectorHTML`, resolving the
   digit/selector tension `js/ai.js`'s author flagged rather than worked around silently.
5. Two small self-audited fixes: a caveat/computation mismatch in `exposure.currency`
   (the caveat claimed an exclusion the computation never performed — reworded to match
   reality), and a latent bug in `registerEvidenceFor` where `scenario_id` always
   defaulted to `null` regardless of the claim's own value.

## Contradictions against the accepted baseline

Per `reviews/gates/HG1_REVISION_CYCLE_01.md` §3, the accepted baseline (financial
contracts/functional coverage, metric-state rules, the P1 deterministic boundary, Proof
Packet architecture, P8 scenario isolation, AI-grounding principles, the P10 freshness
contract, P3 caveat preservation) is closed to this build, as it was to every worker in
this cycle. **Recording, not resolving**, per that section's own instruction:

- **No new contradiction against that baseline was found during this integration
  pass.** The two items closest to looking like one turned out, on inspection, not to
  be baseline contradictions:
  - The tension between `CONTRACT.md` §6A's original absolute wording ("every digit...
    must be inside a `.chip`") and PD-0008's own carve-out for a selector digit as plain
    text is a mismatch inside this build's *own* contract document, not a conflict with
    an accepted-baseline document — PD-0008 itself already permitted the selector case.
    Resolved by refining `CONTRACT.md`'s wording and the scanner to match PD-0008
    exactly (see "What changed" above), not escalated.
  - The `exposure.currency` caveat/computation mismatch (above) is a self-authored
    data-integrity slip inside this prototype's own synthetic dataset, not a conflict
    with `designs/FEATURE_DESIGN.md`'s D3/D5 rules themselves. Fixed by correcting the
    claim's own text, not escalated.
- **Everything else audited during this pass** (the metric-state rendering table, the
  freshness two-axis-never-merge rule, the P8 ACTUAL/SCENARIO separation, the P1
  provenance-chip mechanism, the Proof Packet's AC-17 empty-registry-by-design state)
  was found consistent with the baseline documents it derives from.

## What was and was not verified

**Not run: any browser, any JavaScript engine.** No browser or JS runtime exists in this
worker's sandbox (`designer-14`). Every change above was hand-traced against
`CONTRACT.md`'s accessor list and the actual definitions in the files it references —
brace/paren balance was checked mechanically; cross-file references (`APP.ui.*`,
`APP.data.*`, `APP.charts.*`) were traced by hand against their definitions — but none of
that is the same as having loaded the page. `pm-01` (or whoever serves this) should
verify, before relying on any of it, at minimum: every route above still renders with
zero console errors after these edits; the newly-styled Scenario Lab, AI panel, and
Evidence overlay render as intended (not just without error); the new
`metric.totalPortfolioValue` claim renders correctly on Overview with a working Evidence
control; and a scenario's own "Evidence" button (on either comparison side) now opens a
real Proof Packet instead of the fallback message it used to.
