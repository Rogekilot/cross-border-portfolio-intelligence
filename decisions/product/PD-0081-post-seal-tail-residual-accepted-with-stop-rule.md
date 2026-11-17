# PD-0081 — The post-seal tail residual before R8 is accepted, with a stop rule on failure

**Status:** accepted
**Date:** 2026-11-10
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** `implementation/CP7_F1_REAL_PATH_DESIGN.md` 8.1 item 11 (technical review TR2-M1). This is the record R8 cites.
**Bears on:**
- the design's 7.1 R8 row and 4.4 Step 2;
- the R8 runbook, which does not exist yet;
- the HG4 package.

## Context

Design 8.1 item 11 asks the owner to accept a residual in a record that R8 cites, or to say that R8 does not start. PD-0068 answer 2 does not cover it: that answer accepted the ACK-loss limit, which is about end-to-end ordering.

R5 ran the shared create and read tails on an accepted `SYNTHETIC_TEST` create (PD-0066 decision 8). Nothing was marked `synthetic = false` and no refusal was bypassed. Four things remain unshown before R8, and the real commit exercises them first (4.4 Step 2):
1. the real branch's seal on an accepted `synthetic = false` result: the passing sides of O1 and O4, and of the real-only seal checks `RW_REAL_PROJECTION_DIFFERS` and `RW_REAL_REGISTRY_DIFFERS`, which have been shown refusing only;
2. any deferrable constraint, write path or row that only the real branch has, fired by name for the first time;
3. the real commit's size and timing against `complete_by`;
4. a stall or fault drill on the real commit. None is proposed, because the real run commits once and a rehearsal install was declined.

The classification already fails closed: an unclassified outcome is UNKNOWN, and nothing is retried.

## Decision

Question asked, verbatim:

> Design 8.1 item 11: the real branch's seal, its real-only checks, and the real commit's size and timing are first exercised by the real commit at R8, with no rehearsal. How do you decide?

The PM's summary shown just before it named the four items above and the fail-closed classification.

Options shown, verbatim:
- **"Accept, stop on failure (Recommended)"**: "Accept the residual in a record R8 cites. The R8 runbook adds a stop rule: if the real commit is refused or UNKNOWN, stop. Nothing is re-run until the cause is found and a reviewed fix is committed, and the outcome goes in the HG4 package as a first-run observation. No extra build; R8 can start once the other pre-R8 items are done."
- **"Rehearse on a throwaway install"**: "Before R8, build a disposable REAL-kind install and load the same real files into it, so the real branch commits once before the real one. This reverses the earlier 'no rehearsal install' choice, needs a design change and review, and adds a second install with your passwords typed into it. It closes items 1-3, not 4. Costs at least one increment."
- **"Accept as written"**: "Accept the residual exactly as item 11 states it, in a record R8 cites, with no added stop rule. The fail-closed classification still applies, but what happens after a refused or UNKNOWN real commit is left to R8's plan."
- **"R8 does not start"**: "Decline the residual. R8 does not start, so no real data is committed and HG4 cannot be requested. The real path stays where it is until you decide otherwise."

**Answer, verbatim:** "Accept, stop on failure (Recommended)"

## Consequences

1. **The residual is accepted.** Items 1 to 4 of design 8.1 item 11 are first exercised by the real commit at R8. This record is the one R8 cites, and 8.1 item 11 no longer blocks R8.
2. **The stop rule, for the R8 runbook.** If the real commit at R8 step (5) is refused, or its outcome is UNKNOWN:
   - R8 stops at that point;
   - nothing is re-run, by hand or by a tool, until the cause is found and a reviewed fix is committed;
   - the outcome, its code and what was observed go in the HG4 package as a first-run observation.

   The runbook must state this rule in these terms.
3. **No rehearsal install** is built. The earlier choice stands, and PD-0066 decision 8 is unchanged.
4. **The HG4 package records:**
   - the four items as first exercised at R8;
   - what each showed;
   - the branch inventory that R8 actually fired. Item 2 may turn out to be empty, or it may name the difference.
5. **Not decided here:** the other pre-R8 items are still open: O-7, O-6, R6R-L1 and TR6R-L1, the password rule in the runbook, and TR7F3-L-1. So are the conditions R8 already depends on: the downloads, sidecars, `SOURCES.json` and `valid_until`.
6. Passing tests, a review verdict and this record are not approval of HG4. Only the owner decides that gate.
