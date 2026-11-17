# Simulated vs. implemented — a precise, unflattering account

The owner's instruction (§2 item 11 of `reviews/gates/HG1_DIRECTION_SELECTION.md`)
requires this explicitly: *"explicitly identify which interactions are simulated versus
actually implemented."* This document does that, surface by surface. Two words are used
with a specific meaning throughout:

- **Computed** — a real number, deterministically derived at render time from the fixed
  synthetic dataset in `js/data.js`. The *data* is fake (synthetic prototype fixtures);
  the *computation* over it is real, not scripted or hand-typed per screen.
- **Simulated** — an interaction that *behaves* as if it did something durable (added a
  position, committed an import, changed a setting) but discards the result the moment
  you navigate away or reload. Nothing in this codebase writes to `js/data.js`'s
  in-memory dataset; there is no write accessor to write to, by design (`CONTRACT.md`
  §3: "Data + pure accessors only").

## Portfolio — manual entry, transactions, accounts, cash, reconciliation

**All of it is simulated persistence.** Every one of these opens a real, working form
with real client-side validation, a real "Review & Stage" preview step, and a real
"Confirm" action — but the confirm handler's entire effect is to swap the card's own
`STAGED` badge for `COMMITTED` and print a sentence saying so. **Reload the page, or
just navigate to another tab and back, and the form is gone and the Holdings/Transactions/
Accounts tables are exactly as they were before you touched anything.**

| Interaction | What's real | What's simulated |
|---|---|---|
| Manual position entry | Form validation (quantity/security required before staging), the security-resolution demo (below) | The "Confirm & Add" action; nothing is added to Holdings |
| Manual transaction entry | Same validation pattern, type-dependent field visibility (security field hidden for DEPOSIT/WITHDRAWAL/FX) | Same — nothing is added to Transactions |
| Add account | Form + preview | Nothing is added to the Accounts table |
| Add cash balance | Form + preview, currency-aware formatting | Nothing is added to Accounts & Cash |
| Holdings row edit (reconciliation) | Inline form pre-filled with the row's real current values | "Save (simulated)" prints an acknowledgment; the Holdings table row is unchanged |
| Security resolution | Genuinely searches the real `getHoldings()`/`getHolding()` data for a match; one hardcoded query (`"TSMC"`) triggers a genuine forced-choice UI between two candidates, matching PRD §27.3's "never silently guess" | The candidate pair for the ambiguous case is hand-authored, not a real security-master lookup; there is no general instrument-search accessor in `js/data.js` (a real gap, not papered over — see `js/surfaces/portfolio.js`'s own comment) |

## Portfolio — Import & Ingestion (CSV and OCR)

**The extraction is entirely canned; the review/resolution workflow on top of it is
genuinely interactive; the commit is simulated.**

- **CSV import.** The "uploaded file" (`usbroker_export_2026-09.csv`) is a fixed fixture
  in `js/data.js` — no file is actually read, no file picker exists. The four rows'
  statuses (`STAGED`, `AMBIGUOUS_SECURITY`, `MISSING_FIELD`, `POSSIBLE_DUPLICATE`) are
  hand-authored, not derived from parsing anything. **On top of that fixed data, the
  resolution UI is real**: the ambiguous-security radio choice, the missing-field text
  input, and the accept/skip duplicate buttons all genuinely gate the "Confirm Import"
  button (it refuses to proceed until every flagged row is resolved or explicitly
  skipped). "Confirm Import" itself is simulated: it flips a local `confirmed` flag and
  every row's status pill to `CONFIRMED`, and says plainly that the Transactions table
  elsewhere on the page is unchanged. **Navigating away from Import & Ingestion and back
  resets all of this** — the local resolution state lives in a closure that is rebuilt
  from scratch every time the surface re-renders (`CONTRACT.md` §2: "treat each call as a
  fresh render").
- **OCR-assisted ingestion.** All three "uploaded documents" and every field's
  extraction result (`HIGH`/`LOW` confidence, the ambiguous-security candidates, the
  missing field, the possible-duplicate flag, the correction, the final confirmation)
  are fixed fixtures in `js/data.js` (`specs/OCR_INGESTION_ADDENDUM.md` §5 explicitly
  permits this — no production OCR pipeline is being demonstrated or claimed). No image
  is actually uploaded or processed; there is no file picker here either. The same
  honest split as CSV applies: the resolution UI (radio/candidate selection, correction
  input with an explicit quarantine checkbox, accept/skip for the duplicate) is real and
  gates "Confirm & Commit," which is itself simulated — it flips the document's badge to
  `COMMITTED` and states plainly that Holdings/Transactions elsewhere are unchanged.
  Same reset-on-navigation caveat applies.

## Evidence & Methodology

**Genuinely computed, not simulated**, with one honest, deliberate exception.

- Every Proof Packet field (scope, data-quality/limitations, source timestamps,
  methodology version, freshness) is assembled from the real claim object and the real
  `getFreshness()` output at open time — not scripted per claim.
- **The methodology registry is empty by design for most metrics (AC-17), not a bug and
  not a simulation of "coming soon."** Five metrics (`portfolioReturn`, `beta`, `alpha`,
  `volatility`, `concentration`) carry a full illustrative 15-field entry; the rest
  render an explicit "not yet published" state. This is demonstrating a real, expected
  product state (a schema-validated but not-yet-authored registry), not withholding
  content that exists elsewhere.
- Scenario-comparison claims (`scenario.X.volatility`, etc.) now resolve to a real
  registered Proof Packet as of this integration pass (previously they did not — see
  `README.md`'s "What changed" section); their content is computed from the same
  scenario data every other rendering of that scenario uses, not separately authored.

## AI Analyst

**Entirely canned, deterministic template selection — not a model call of any kind.**
This is stated in `js/ai.js`'s own file header and is worth restating here plainly: there
is no LLM, no API call, no network request anywhere in this file (the harness has no
network egress regardless). What *is* real:

- Every numeral the "AI" states is read live from the same `APP.data` accessors every
  other surface uses (via the citation-chip mechanism) — it does not fabricate a number,
  and clicking a chip opens the same real Evidence overlay described above.
- The handful of "follow-up" answers (position count, performance explanation, "what
  changed," exposure summary, risk explanation) are a **fixed menu of pre-written
  templates**, not a response to open-ended free text — there is no text input for the
  user to type an arbitrary question into. Selecting a template re-runs a fixed function
  against the current dataset; it does not "understand" anything.
- The conversation thread is simulated in the sense that closing the AI overlay and
  reopening it (or navigating to another route and back) **loses the entire thread** —
  nothing is persisted across opens.

## Scenario Lab

**The three scenarios are fixed, pre-computed enumerations, not an interactive
what-if model.** There is no slider, no free-form "reduce China exposure by X%" input,
and no way to define a new scenario. Selecting one of the three named scenarios swaps in
a comparison object that was computed once, at `js/data.js` load time, using fixed
multipliers (e.g. "volatility × 0.91") against the real underlying dataset — the
ACTUAL-side numbers are the same real computed metrics every other surface shows; the
SCENARIO-side numbers are a fixed, illustrative hypothetical adjustment to them, not a
live recomputation of a changed portfolio. This is consistent with the owner's own
framing ("model a hypothetical change... compare it against your actual, current
holdings") but should not be mistaken for a general-purpose scenario engine.

## Settings / Policy

**Display-only; there is no edit capability implemented.** The gear-icon overlay shows
the real `getPolicy()` values (reporting currency, and the P7 "no cap is set" disclosure
when `singlePositionCapPct`/`sectorCapPct` are `null`, which they are in this dataset)
and the real list of accounts — but there is no form anywhere on this screen to actually
set a policy value. `designs/FEATURE_DESIGN.md`'s own disposition for this surface (added
2026-09-04, resolving AC-07) says it carries no D2.2 claim and needed no accessor-heavy
interaction design — display-only is consistent with that, but is worth naming plainly
rather than leaving a reader to assume a settings form exists somewhere unclicked.

## What is NOT simulated — genuinely implemented, working interaction

For contrast, so the above list isn't mistaken for "nothing here works":

- **Navigation and routing** (primary tabs, Portfolio's secondary tabs, hash-based
  deep-linking) is real client-side routing, not a mockup of tab-switching.
- **The metric-state rendering system** (`AVAILABLE`/`LIMITED`/`INSUFFICIENT_DATA`,
  the freshness pill, the `STALE_DATA` treatment) is real logic operating on real claim
  objects — every instance of each state in this prototype is a genuine claim object
  carrying that state, not a hand-styled mockup image of what the state would look like.
- **The depth ladder** (Quick/Simple/Investor/Professional) genuinely re-renders the
  same claim object at a different depth on click — it is not four separate hard-coded
  screenshots.
- **The focus-and-inspect dock** genuinely opens/closes and mounts real content per
  click (a metric cell, a correlation cell, a chart point, a Holdings row).
- **All charts** are real SVG rendered from the real underlying data series at render
  time (including the period selector re-querying `getPortfolioSeries({range})`), not
  static images.
- **The freshness strip's ranking** (`rankLeastFresh`) genuinely computes the least-fresh
  axis by categorical severity from the real freshness data, every render.
