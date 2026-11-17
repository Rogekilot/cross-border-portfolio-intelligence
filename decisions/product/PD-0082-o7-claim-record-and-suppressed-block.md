# PD-0082 — O-7 and O-6: the claim record lives in the stored response; the block over a suppressed real NAV is the withheld variant

**Status:** accepted
**Date:** 2026-11-10
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** Q1 to Q4 of `methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` §10 (Q4 is O-6).
**Bears on:**
- `src/marketdata/claim_render.py`, `src/marketdata/claim_limits.py`, `src/real_service/`, `src/web_api/real_mode_routes.py`, `src/web_api/real_launcher.py`;
- the real-mode client strings;
- design 7.4;
- `implementation/CP7_F1_O7_LINEAGE_EXTRACTION_PLAN.md`;
- the R8 runbook and the HG4 package.

## Context

O-7 is the extraction of the claim-limit lineage for a real root. The engineer's survey found the following:
- only 7 of the 19 lineage fields are stored as plain text where the read path can reach them;
- three fields are stored nowhere: `documentation_reading_date`, `reconciliation_status` and `v1_statement`;
- the engine does not yet state label status and source, E(d_p, R) or the V1 statement. That is market-data/1.16 Ruling 3.2 item 5, listed in `UNBUILT_1_16`.

The Quant's ruling fixes a source and an exact text form for each field. It splits the shared `session_date` into a valuation date and a price-session date. It rules that Ruling 3.2 item 5 is not a precondition for R8, provided the block says something narrower (§3.5, §5). It defines a withheld variant for a suppressed NAV (§6). Four choices were left to the owner.

## Decision

The PM's summary shown before the questions: of the 21 fields, the ruling fixes the source and exact text of each. Ruling 3.2 item 5 need not block R8 if the claim block says something narrower: "The lineage states…" becomes wording that copies the stored ingest facts.

Questions asked, options shown and answers, verbatim:

**Q1.** "O-7 Q1: a real create must store a 'claim record' of facts the claim block needs that the stored result lacks today (vendor call, source name, label status and source, reconciliation status, file hashes, retrieval time). It is written at create, sealed with the root, and rebuilt and compared on reproduce. Where should it live?"
- **"In the stored response (Recommended)"**: "An object in the result's stored response, copied from the values the computation used. No SQL or installer change; PD-0073 chose 'stored result + seal' for the same kind of fact. Having the engine state these facts (Ruling 3.2 item 5) stays an open item for later and in the HG4 package."
- **"In the envelope"**: "An object in the stored envelope. The real seal checks the envelope's exact key set, so the SQL and the installer artifacts change before R8, with their review."
- **"Engine states them first"**: "Build market-data/1.16 Ruling 3.2 item 5 in the engine first, plus a reconciliation status in the holding lineage. The block keeps 'The lineage states'. A market-data and performance increment with new digests; it delays R8 the most."

**Answer:** "In the stored response (Recommended)"

**Q2.** "O-7 Q2: the claim sentence C-1 says Alpha Vantage's adjustment declaration was read by you on a date (2026-10-24), but that date is stored nowhere as data, only in a code comment and PD-0066. What should C-1 say?"
- **"Cite the record (Recommended)"**: "C-1 says 'as the owner read it (PD-0066 decision 3)'. The record holds the date, so it stays auditable. It drops precision, not a caveat. No digest change."
- **"Store the date"**: "Add the reading date to the source profile as data and keep 'on 2026-10-24' in the sentence. Changes the profile digest and its tests; must be done before the real publish at R8 step 4."

**Answer:** "Cite the record (Recommended)"

**Q3.** "O-7 Q3: if a real create's claim record cannot be built (a precondition fails, for example a corporate-action file in the inputs, or a field is missing), what happens?"
- **"Refuse before the seal (Recommended)"**: "The create is refused and rolled back whole, with a new refusal code the contract and client know. Nothing is stored. Under PD-0081 R8 then stops until a reviewed fix."
- **"Commit it anyway"**: "The result is stored, but can never be shown, because no real result is shown without its claim block. Every read and repeat of that root answers UNKNOWN for ever."

**Answer:** "Refuse before the seal (Recommended)"

**Q4 (O-6).** "O-6 (Q4): what does the claim block say over a real NAV that is INSUFFICIENT_DATA (the number suppressed)?"
- **"Withheld variant (Recommended)"**: "The same twelve items, reworded: the price items say nothing is stated about a price that was not used, S3 gives the state, cause, freshness and delay, and the other caveats stay as they are. The partial figure PD-0035 requires can then be shown with its block."
- **"No block, unreadable"**: "A suppressed real root has no block, so it cannot be shown at all. The partial figure PD-0035 section 2 requires is never shown on a real root."
- **"A different item set"**: "A separate block with its own items for the suppressed case. Changes the client's reader and the contract's item check, so a larger change and a new wording check."

**Answer:** "Withheld variant (Recommended)"

## Consequences

1. **The claim record (K) is an object in the stored response.**
   - It is built in the create transaction from the values the computation used.
   - It is sealed with the root and immutable.
   - Reproduce rebuilds it and compares it byte for byte; a difference is `RESULT_DIFFERS`.
   - No SQL, migration or installer artifact changes for it.
   - Ruling 3.2 item 5 stays an open item in the engine's manifest and in the HG4 package, with the ruling's narrower wording as the disclosure.
2. **C-1 cites `PD-0066 decision 3`** in place of the reading date. The date is never a template constant (P9), and the profile digest is unchanged.
3. **An unbuildable claim record refuses the create before the seal.** The refusal rolls back whole, with a new refusal code that the contract and the client know. Under PD-0081 this stops R8 until a reviewed fix.
4. **Over an `INSUFFICIENT_DATA` real NAV the block is the withheld variant** of the ruling's §6, with the same twelve item ids. Over `AVAILABLE` and `LIMITED` the block is the normal block, with the dates split. An unknown state or two NAV rows refuses.
5. **Sequencing (PM, not an owner decision).** The ruling's Q5 slot renames land in one change with the re-worded client strings. That change is followed by a fresh Quant wording check of the client strings. Keeping the old names with new meanings is not done.
6. **Not decided here:**
   - the new refusal code's name, which is the engineer's proposal, judged by review;
   - the client wording, which goes to the Quant's check;
   - building Ruling 3.2 item 5, which is later work.
