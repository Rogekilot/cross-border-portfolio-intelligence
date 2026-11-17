# PD-0087 — HG4: revision required

**Status:** accepted
**Date:** 2026-11-16 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** the HG4 gate package, [reviews/gates/HG4_GATE_REVIEW.md](../../reviews/gates/HG4_GATE_REVIEW.md) (2026-11-16).
**Bears on:** HG4; the R8 runbook; the real-mode screen; the R8 record.

## Context

The owner ran R8 on 2026-11-16. The package reported:
- the run's mechanics, numbers, isolation and revocation as sound;
- the independent technical review TR8R as **FAIL** on evidence: four of the design's first-run observations were neither collected
  nor declared;
- the design review DR-R8 as **PASS WITH FINDINGS**, with one HIGH and four MEDIUM findings;
- check 10.1 as FAIL: the close is not shown on the screen by design;
- the first attempt's latched stop as bypassed on the main session's instruction.

The PM recommended REVISION REQUIRED, scoped to four items (package section 13). The owner then asked whether that needs another
round of tests. The PM answered:
- yes, one supplementary run by the owner on the same real database and context, of about 20–30 minutes, after an engineer adds the
  steps to the runbook and a reviewer checks them;
- the screen fixes are tested by the agents and seen by the owner during that same run;
- the check 10.1 correction and the first-stop decision record are paperwork only.

## Decision

The question in the next-step box, verbatim: "What is your HG4 decision?"

Buttons offered: "Revision required", "Approve with conditions".

**Answer, verbatim:** "Revision required"

## Consequences

1. **HG4 is not passed.** The project stays at the gate. Work downstream of HG4 does not start.
2. **The revision, as recommended in package section 13:**
   1. **A supplementary run on the same context.** An engineer designs it as a runbook addition and an independent reviewer checks
      it; then the owner runs it. It collects:
      - exact-201 replay and idempotency;
      - the idempotency-conflict case;
      - the error digest on a refused request;
      - a physical restart of the database, launcher and screen, then read and reproduce;
      - the codes left unrecorded: B's 404, and the read and reproduce refusals under a withdrawal, if a withdrawal is part of
        it.

      No new install, publish or loader window.
   2. **Check 10.1 is corrected** to compare the figures the screen states.
   3. **DR-R8-1, DR-R8-3 and DR-R8-4 are fixed** in the screen (reopen from the list, the password-length hint, clearing typed
      values on sign-out), with tests and independent review.
   4. **A decision record on the first attempt's bypassed stop.** The owner decides it separately (package 9.2).
3. **The package returns to the owner** with the supplementary run's results added and the findings closed or accepted.
4. **Not decided here:**
   - whether a stored price row should be shown (DR-R8-2);
   - DR-R8-7 and the LOW findings;
   - the upper-bound limit;
   - the public-copy redaction follow-up.
