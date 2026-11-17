# PD-0074 — O5 enforced in Python only, accepted as an operational residual

**Status:** accepted
**Date:** 2026-10-31 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 4.2 (O5) and the R4b, R6 and R8 rows of 7.1;
- F1 increment R4b: `src/persistence/real_sidecar.py`, `real_proposal.py` and
  `real_workspace_store.py` (`RealPublisher.publish(sidecars=...)`);
- R3's `rw_publish` in `src/persistence/real_workspace_v1.sql`, which is unchanged;
- review finding TR4B-L1 (`reviews/TECH_REVIEW.md`, "F1 R4b build — independent technical review
  (2026-10-31)").

## Context

O5 requires the owner's acquisition sidecar for each real member file. R4b enforces it in Python:
- the proposal writer and verifier;
- the qualification run;
- `RealPublisher.publish(sidecars=...)`, before any statement.

The database's `rw_publish` never sees sidecar bytes and checks only O1 to O3, the shape and the
labels. So someone holding the publisher role who calls `rw_publish` by hand in SQL could publish a
REAL snapshot with no sidecars.

A SQL check could only refuse a null slot; it could not validate a sidecar. It would also change R3's
reviewed gateway SQL, after "no gateway SQL after R3".

## Decision

Question asked, verbatim:

> O5 (your acquisition sidecar for each real file) is checked only in Python, by the proposal tools and the publisher tool. Someone holding the publisher role who calls the database's publish function by hand could publish a REAL snapshot with no sidecars. How should this be handled?

Options shown, verbatim:
- **"Accept as a residual (Recommended)"**: "Record it as an operational limit like LOW-7: the product path
  cannot publish REAL without O5, and a hand SQL call by the publisher-role holder is outside it. R6
  decides who holds that role; the HG4 package states the limit. No reopening of R3."
- **"Reopen R3 for a SQL check"**: "Add a null-slot refusal to the database publish function for REAL. The
  database still cannot see sidecar bytes, so it only checks that each member names a sidecar digest, not
  that the sidecar is valid. Reopens R3's reviewed gateway SQL: a fix round and re-review before R5."

Owner's answer, verbatim: **"Accept as a residual (Recommended)"**

## What this means

- **O5 stays enforced in Python only.** The product path (the publisher tool and its CLI) cannot publish
  REAL without a valid sidecar for every member. R3's gateway SQL is not reopened.
- **The residual is stated.** A hand SQL call to `rw_publish` by whoever holds the publisher role can
  publish a REAL snapshot without sidecars. It is an operational limit, of the same kind as LOW-7 (a
  direct `write_release` call).
- **Where it is stated:**
  - R6, which decides who holds the publisher credential;
  - the HG4 gate package;
  - the design's next revision (4.2 O5).
- **R8 uses the product path for the real publish** and names it in the run record.

## What this does not do

It builds nothing and approves no gate. The two MEDIUM findings of the same review (TR4B-M1 and
TR4B-M2) are being fixed separately.
