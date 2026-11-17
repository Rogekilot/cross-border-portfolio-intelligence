# PD-0079 — The real-mode screen shows key figures, with the raw document labelled below

**Status:** accepted
**Date:** 2026-11-09
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `web/src/RealModeApp.tsx`, `real-mode.ts`, `real-mode-i18n.ts` and `e2e/real-mode-flow.spec.ts`;
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 1.1, 7.4 and the R7 and R8 rows of 7.1;
- review "F1 R7 build — independent technical review (2026-11-07)" in `reviews/TECH_REVIEW.md`, item 7:
  "The stored result shown as raw JSON: acceptable for R7, but needs an owner or design decision before R8."

## Context

> **Correction, 2026-11-09, see [PD-0080](PD-0080-key-figures-read-the-valuation-document.md):** the NAV statement below holds only for the `REAL` path, which has not stored a result yet. A `TEST` create stores a diversification result with no NAV. The owner's answer below is unchanged.

As committed at `13413a8`, the real-mode screen shows the origin label, identifiers, digests and the claim limits. The result's figures, NAV included, appear only in a collapsed raw JSON block, `JSON.stringify(root.result, null, 2)`. So:
- at R8 the owner would read NAV out of JSON to check it against the Quant's oracle;
- the engine's English notes reach the screen unexplained and untranslated, outside the 7.4 framing.

## Decision

Question asked, verbatim:

> How should the real-mode screen show the stored result once real data is in it?

Options shown, verbatim:
- **"Label the raw JSON only"**: "Keep the collapsed raw JSON and add a label in EN and zh: this is the engine's document exactly as issued, its notes are in English and not interpreted, and the claim limits above govern it. Smallest change. Nothing is hidden, but you still read NAV out of JSON at R8, which is a weak test of usability."
- **"Key figures + labelled raw (Recommended)"**: "Add a read-only list of the stored figures: value, state and reason exactly as stored, in EN and zh, with the number suppressed when the state is INSUFFICIENT_DATA. The client computes and interprets nothing. The labelled raw JSON stays below for audit. NAV is readable at R8. Costs a small increment: the build, a Quant check of new labels, review and a browser run."
- **"Hide the document"**: "Show only the origin label, claim limits and digests. No unexplained notes reach the screen, but no result figure appears in the app, so you couldn't check NAV there, and the audit view goes. Not recommended."
- **"Full explained view"**: "Every figure and every engine note presented in EN and zh at all three depths, with notes explained in plain wording. The most usable, but also the largest: all that new wording needs the Quant's ruling, and it delays R8 for more than the single-date check needs. Better after HG4."

**Answer, verbatim:** "Key figures + labelled raw (Recommended)"

## Consequences

1. **A read-only key-figures list** on the result screen shows each stored figure with its value, state and reason as stored. The client computes nothing, derives nothing and interprets nothing (P1). The labels are EN and zh.
2. **`INSUFFICIENT_DATA` suppresses the number** (P5). A figure in that state shows its state and reason and no value.
3. **The raw document stays**, for audit (P9), collapsed below the list. It carries a label in EN and zh saying it is the engine's document exactly as issued, that its notes are in English and are not interpreted, and that the claim limits above govern it.
4. **Origin rules are unchanged.** Over `TEST` data the invented-data mark shows, and no 7.4 sentence or real-origin label appears. Figures over `TEST` data must not read as real figures.
5. **New wording** goes to the Quant for a check before it is accepted. The claim-limit text is not changed by this decision.
6. **Not decided here:**
   - which figures make up the list, beyond NAV being readable: the engineer proposes, and the independent review judges against this record;
   - whether the existing `AnalyticalMetric` component fits the stored result's shape: not yet confirmed.
7. **A full explained view** of every figure and engine note is left for after HG4, if the owner wants it then.
8. This is a pre-R8 item. The increment needs its build, the Quant's check, the suites, a browser run and independent review.
