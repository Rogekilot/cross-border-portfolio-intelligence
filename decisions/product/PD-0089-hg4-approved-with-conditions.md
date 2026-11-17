# PD-0089 — HG4: approved with conditions

**Status:** accepted
**Date:** 2026-11-17 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** the HG4 gate package, revision 2, [reviews/gates/HG4_GATE_REVIEW.md](../../reviews/gates/HG4_GATE_REVIEW.md)
(2026-11-17).
**Follows:** PD-0087 (revision required) and PD-0088 (the revision's scope).
**Bears on:** HG4; F1's real-data claim; the real-mode screen; the public copy.

## Context

The owner ran the supplementary run on 2026-11-17 (`~/finweb-r8-supplement/SUPPLEMENT_RECORD.md`). It ran with no stops, and every
answer was the expected one. The independent evidence review TR8SR (`reviews/TECH_REVIEW.md`) returned **PASS WITH FINDINGS**.

The package reported:
- all four of PD-0087's revision items done;
- six remaining limits (package 11.1);
- one new screen-label finding, TR8SR M-1.

The PM recommended APPROVED WITH CONDITIONS and proposed four conditions (package section 13).

## Decision

The question in the next-step box, verbatim: "What is your HG4 decision?"

Buttons offered: "Approve with conditions", "Revision required".

**Answer, verbatim:** "Approve with conditions"

The confirming question, verbatim:

> HG4: you chose 'Approve with conditions'. Are the conditions exactly the four in package section 13: (1) accept the six limits in
> 11.1 as deviations; (2) fix the list's generation label, with design and technical review, before real results are shown to
> anyone but you; (3) redact vendor values in the public copy before the next public push; (4) track DR-R8-2, DR-R8-7, the LOW
> findings and TR8SR L-1 to L-4 as follow-up work?

Options: "Yes, those four (Recommended)"; "Change them".

**Answer, verbatim:** "Yes, those four (Recommended)"

## Conditions (binding, as worded in the confirming question)

1. **"accept the six limits in 11.1 as deviations".** These are package 11.1's six limits, now accepted deviations. HG4's
   "real-data usable" claim carries them:
   1. same-transaction persistence (T06) collected only in part;
   2. the restart was a clean PostgreSQL stop and start, not a crash, kill or host reboot, and not during a create;
   3. replay, conflict and user B's 404 were sent by the loopback tool at the real-mode routes, not from the browser;
   4. the UNKNOWN-then-repeat path was not exercised;
   5. replay was shown on the supplement's create Y, not on R8's own first create;
   6. check 10.3 (the no-NAV notice's prominence) was not observable with a NAV stored.

   Accepted earlier and unchanged: the read and reproduce refusal codes under a withdrawal (PD-0088 consequence 2), and D-1 and
   D-2 (PD-0068 answer 3).
2. **"fix the list's generation label, with design and technical review, before real results are shown to anyone but you".** This
   is TR8SR M-1: the list's "Generation N" is the context's current generation, not the one the root was created under.
   - The fix is an engineer increment, with a designer's and an independent technical review.
   - Until it passes, real-mode results are shown to no one but the owner.
3. **"redact vendor values in the public copy before the next public push".** This covers the vendor values in the HG4 package, in
   DR-R8, and in `src/real_tools/r8_guide.py` and its test (PD-0083's redaction, extended to these files). The owner does not push
   the public copy until it is done.
4. **"track DR-R8-2, DR-R8-7, the LOW findings and TR8SR L-1 to L-4 as follow-up work".** These are tracked in `STATUS.md` as open
   follow-ups. None of them is decided here:
   - DR-R8-2 (whether a stored price row is shown) is still the owner's product question;
   - DR-R8-7;
   - DR-R8-5, -6, -8 and -9;
   - TR8SR L-1 to L-4 (and L-5 as context).

## Consequences

1. **HG4 is passed, within these conditions.** The F1 slice is validated on one real context: AAPL on XNAS, as of 2026-09-30,
   with a constructed, non-personal ledger. The limits it carries are in package section 8.4 and condition 1.
2. **Work past HG4 may start,** within the conditions. Condition 2 limits showing real results to anyone other than the owner;
   condition 3 limits public pushes.
3. **Not decided here:**
   - the upper-bound limit, which stands (PD-0068 answer 4; package 8.4 f);
   - the cluster's live rights until 2027-09-01: withdrawal stays the owner's act;
   - CN and HK real data, OCR, scenarios and AI explanation, which stay outside F1 (PD-0041);
   - which work comes next after HG4.
