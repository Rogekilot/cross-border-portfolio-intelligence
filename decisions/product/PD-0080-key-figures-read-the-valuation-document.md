# PD-0080 — The key figures read the valuation document, proved on an engine-made fixture

**Status:** accepted
**Date:** 2026-11-09
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- [PD-0079](PD-0079-real-mode-result-display.md), including a correction to its Context;
- [PD-0035](PD-0035-cp3-lot-method-partial-total-hg2-data-fx-waterfall.md) section 2;
- `methodology/CP7_F1_PD0079_FIGURES_WORDING_CHECK_2026-11-09.md` (F-1, F-2, F-3);
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.4 (the never-stored fixture pattern) and the R8 row of 7.1.

## Context

The browser run of the PD-0079 view showed every listed figure as absent over a genuine stored result. The engineer stopped and reported the real shape, and the main session confirmed it in `src/real_service/service.py`:
- **A `TEST` create** (`_stage_fictional`) stores the CP5 diversification result, selector `CP5_DIVERSIFICATION`. It holds no NAV and no valuation figure. Its only money amounts are `manifest.buckets[]`.
- **A `REAL` create** (`_stage_real`, `performance_service.compute_for_portfolio`) will store the performance valuation, which holds `portfolio_value`, `stale_weight_presented`, `breakdown` and `portfolio_value_priced_holdings`. It is not wired until R8, so no stored instance of it exists.

**Correction to PD-0079's Context.** It says the result's figures, NAV included, appear only in the collapsed raw block. That holds only for the `REAL` path, which has never stored a result. The main session said this to the owner without having checked the `TEST` document. The owner was told of the correction before this decision.

## Decision

Question asked, verbatim:

> A test create stores a diversification result with no NAV; only a real create will store the valuation, and that isn't connected until R8. How should the key-figures list be built and proved before R8?

Options shown, verbatim:
- **"Real document only (Recommended)"**: "Build the list for the valuation document, with the Quant's F-1 to F-3. Prove it on a fixture produced by the real performance engine from invented inputs, held in memory and never stored or served, with a test that fails if the engine's shape moves. This is how the claim-limit text is already tested. Over test data the screen says that document holds no valuation. A real result with no NAV gets a prominent notice. No server change. Limit: you first see filled figures on screen at R8."
- **"Test create also stores valuation"**: "Change the test path so it also issues a valuation, so a filled list can be seen in the browser now, marked as invented data. Earlier proof on screen, but it changes the server's reviewed test path, the seal and the stored document, needs its own review, and delays R8."
- **"Read the test document"**: "Show the diversification figures that a test create holds. Something fills in now, but those aren't the figures you need at R8, NAV still wouldn't appear, and the list would need rebuilding for real data. Not recommended."
- **"Drop the list for now"**: "Keep only the labelled raw document and leave the list out of R7. Nothing more to build, but at R8 you read NAV from JSON, the outcome PD-0079 chose to avoid, and the partial figure PD-0035 requires stays collapsed. Not recommended."

**Answer, verbatim:** "Real document only (Recommended)"

## Consequences

1. **The list reads the valuation document.** The Quant's F-1, F-2 and F-3 apply to it as ruled: the stale weight beside a `LIMITED` NAV, the separate partial-figure block when the total has no number, and the parts from the stored `breakdown`.
2. **The proof before R8** is a fixture produced by the real performance engine from invented inputs, held in memory and never stored or served. A test fails if the engine's output shape moves away from the fixture.
3. **Over `TEST` data** the screen says that this document holds no valuation, with the invented-data mark. No figure is derived from `manifest.buckets[]`.
4. **Over a `REAL_SOURCE` root, a result with no NAV** gets a prominent notice, distinct from the neutral absent line, because a real single-date create without a NAV is a defect of the document.
5. **No server change.** The stored document, the `TEST` path and the reviewed contract are unchanged.
6. **The recorded limit.** The owner first sees filled figures on screen at R8. That first rendering from a real stored result is an R8 check, like the 7.4 wording and the real origin label.
7. New wording goes to the Quant for a check before it is accepted.
