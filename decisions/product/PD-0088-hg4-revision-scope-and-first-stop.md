# PD-0088 — HG4 revision: the supplementary run's scope, the withdrawal codes, and the first attempt's stop

**Status:** accepted
**Date:** 2026-11-16 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:**
- PD-0087 consequence 2.4, the first attempt's stop;
- the independent review of the supplementary-run plan (`reviews/TECH_REVIEW.md`, TR8S), findings M-5 and the missing decision
  points D8 to D10;
- the plan's D1.

**Bears on:** HG4; `implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md`; the HG4 package, sections 8.2, 8.5 and 9.2.

## Questions and answers, verbatim

> The supplementary run has grown since you chose 'Revision required'. It now needs a new small tool (code, tested and reviewed),
> one new real create, and about 40–50 minutes of your time in two sittings, instead of 20–30 minutes and a runbook addition. How do
> you want to go on?

Options:
- "Proceed with it (Recommended)": "The engineer amends the plan for the reviewer's findings, builds the tool, it is reviewed, then
  you run it. HG4 then gets the replay, conflict, error and restart evidence on real data."
- "Accept the gaps instead": "Skip the supplementary run. You accept the four missing observations as deviations in a decision
  record, which moves HG4 toward 'approved with conditions'. The screen fixes and the check 10.1 correction still go ahead."

**Answer:** "Proceed with it (Recommended)"

> R8 didn't record separate refusal codes for reading and reproducing while the context was withdrawn. Collecting them means another
> withdraw and renew: two more decision records, generations 4 and 5, and about 25 minutes more. What do you want?

Options:
- "Accept as a gap (Recommended)": "Record in a decision that these two codes were not collected. The screen did show the
  withdrawal, and the create and export refusals were recorded with their codes."
- "Collect them": "Add a withdraw and renew to the supplementary run, with two more decision records."

**Answer:** "Accept as a gap (Recommended)"

> Your first attempt locked a stop after four failed superuser logins at Phase 0, which is read-only. On my instruction you rebuilt
> the cluster and moved the folder aside instead of clearing the stop the reviewed way. Nothing had been written to any database. How
> do you decide?

Options:
- "Ratify the rebuild (Recommended)": "Record that the rebuild is accepted in place of a reviewed reset, because nothing had been
  written. The R8 run stands."
- "Reject it": "The bypass is not accepted. You'll say what you want instead, which may put the R8 run in question."

**Answer:** "Ratify the rebuild (Recommended)"

> The supplementary run signs in as user B again to record B's refusal when opening A's result. Do you still have user B's password?

Options: "Yes, I have it"; "No".

**Answer:** "Yes, I have it"

## Consequences

1. **The supplementary run goes ahead at its larger scope.** That scope is a new loopback tool and runner, one new real create
   (call it Y; rule 0.3 applies to it), and two sittings around a clean restart.
   - The order: the engineer amends the plan for TR8S's findings (H-1, M-1 to M-4, L-1 to L-5); then builds; then the build is
     independently reviewed; then the owner runs it.
   - The owner approves the real create Y by this answer (TR8S D8).
2. **The read and reproduce refusal codes under a withdrawal are an accepted gap.** They are not collected, and the HG4 package
   states this.
   - The withdrawal itself is collected: the screen showed it; create was refused 409 `RW_WITHDRAWN`; export was refused
     `RW_WITHDRAWN` at the gateway.
3. **The first attempt's rebuild is ratified in place of a `--reset-stop`.** The R8 run of 2026-11-16 stands.
   - The facts: the latch `PASSWORD_RETRIES_EXHAUSTED` at Phase 0, which is read-only; no database created; the cluster deleted and
     built fresh; the state folder kept at `~/finweb-r8-attempt1`.
   - This ratifies this one event. It does not change the runbook's stop procedure for any future run.
4. **User B is the existing account.**
5. **Not decided here:** the other limits TR8S M-5 lists. They are put to the owner when the run's results return to the gate:
   - T06 only in part;
   - the restart being a clean postmaster restart, not a crash or reboot;
   - replay through the tool, not the browser;
   - the UNKNOWN-then-repeat path not exercised.
