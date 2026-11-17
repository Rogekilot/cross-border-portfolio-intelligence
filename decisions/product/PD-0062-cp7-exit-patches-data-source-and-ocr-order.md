# PD-0062 — CP7 exit: handover patches, data-source check, OCR after HG4

**Status:** accepted
**Date:** 2026-10-22 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Decision material:** [CP7 exit inventory](../../reviews/CP7_EXIT_INVENTORY.md) §3 and §7.

## Owner decision, verbatim

> Approve: merge CSV R1 (with the N-1 test), retire N4, park the provenance patches. For the data source, verify Alpha Vantage terms and coverage first. OCR after HG4.

## What this means

1. **Merge CSV R1.** The patch
   `reviews/CP7_F3_CSV_R1_EVIDENCE/handover/source-snapshot-v1/review.patch` adds the
   report-only commit for a repeated CSV import, plus its UI.
   - The engineer rebases it onto the current code and adds the N-1 test
     (`build_profile` refuses a wrong `context_id`).
   - The main session runs the full Python suite (including the CP7-cluster web database
     tests), vitest and Playwright. Then an independent review.
   - Its new SQL is installed into new or disposable test schemas only. Nothing is
     installed into any existing database without a further decision.
2. **Retire N4.** The diagnostics package stays under `reviews/` as evidence and is not
   merged. The unreproduced `F3_STORAGE_UNAVAILABLE` stays an open item.
3. **Park the provenance patches** (N2a, N2b, N3, PD-0059, PD-0060). They are not merged
   now. Their fate is decided when the real-data path's write-authority (F1) design is
   reviewed.
4. **Data source.** First check whether Alpha Vantage, already admitted for internal
   development under PD-0031/PD-0032, also covers what the HG4 UAT needs:
   - its terms, for the planned local display, archive, export and reproduction;
   - its coverage: 2026-09-30 end-of-day prices, split/corporate-action data, and the
     identity fields.
   This check reads public documentation and terms only. It is not authority to call
   Alpha Vantage's data API, create an account or key, pay, or admit a new source. Those
   remain separate owner decisions.
5. **OCR after HG4.** OCR (PD-0009, `specs/OCR_INGESTION_ADDENDUM.md`) is scheduled as its
   own increment after the HG4 decision. It remains a V1 obligation. The HG4 UAT states
   its absence explicitly.
