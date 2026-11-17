# PD-0034 — Calendar files: drafted by the session, checked by the owner

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, answering a question put by the main
session in a Claude Code session on 2026-10-01.
**Recorded by:** that session. **Recorded, not decided.**
**Answers:** the item left open by PD-0033 ("who makes the calendar files").

---

## The decision

Question: *"Who should make the four calendar files (US, China, Hong Kong, ECB), covering
2025-01-01 to 2026-12-31?"* The options were: the session drafts and the owner checks
(recommended); the owner makes them; wait.

Owner's answer, verbatim: **"Claude drafts, I check (Recommended)"**

## What was done

- **Four drafts** are in `data/marketdata/calendars/drafts/`: `NYSE_SESSIONS`,
  `CN_A_SESSIONS`, `HKEX_SESSIONS` and `ECB`, with a review sheet `REVIEW.md`.
- **Sources:** each closure list comes from the publisher's own notice:
  - NYSE's holiday calendar, plus ICE's 2025-01-09 closure notice;
  - SSE's 2025 and 2026 notices and its 2026 Mid-Autumn/National Day announcement, with SZSE's
    matching notice;
  - the HKEX Stock Connect calendars 2025 and 2026;
  - the ECB reference-rate and working-hours pages (TARGET closing days).
- **No price or rate file was used** (Ruling 5.3). A scratch script expanded each notice into
  the explicit date list. Its closure lists are transcribed in each file's `evidence` and in
  `REVIEW.md`.
- **Verification:** all four parse with the project's `CalendarFileAdapter`, and together form a
  valid `CalendarSet`. The session counts match the published annual totals where known: NYSE
  2025 = 250, A-shares 2025 = 243.
- **`prepared_by`** names the session as drafter and the owner as checker. `version` is
  `draft-1 (unchecked)`. The calendar.manual attestation (PD-0033) requires this.

## Consequences

- The drafts are **not registered**, so nothing reads them yet, and freshness stays UNKNOWN
  until they are. The owner checks each against `REVIEW.md`, finalises `version` and
  `prepared_by`, then registers it with the download tool.
- Corrections are made by regenerating, not by hand-editing date lists.
- **The HKEX close time is provisional:** 16:10, and 12:10 on half days, the conservative end of
  HKEX's random closing-auction window. It is pending the `quant-analyst` (STATUS).
- **For the Quant, noted only:** the ECB describes its concertation as "around 14:10 CET".
  The convention constant is 14:15.

## What this decision does not do

It registers no file, changes no convention, and approves no gate.
