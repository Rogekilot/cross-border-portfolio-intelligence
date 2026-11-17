# PD-0075 — R6: go-ahead for the read-only inventory; classifier calibration in the Fin-Web cloud

**Status:** accepted
**Date:** 2026-11-01
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.1 R6 row ("the read-only inventory of the owner's
  environment needs the owner's go-ahead"; the throwaway scram-only cluster "only if the owner grants
  the sandbox exception"), 1.2 rule 7, and section 13 TR3-L2 / section 14 TR3R-M2;
- F1 increment R6 (started 2026-11-01 at the owner's word "Start R6").

## Decision 1 — the inventory

Question asked, verbatim:

> R6's design needs your go-ahead for a read-only inventory of your PostgreSQL setup. I would read pg_hba.conf, check which OS user owns the data directory, and list only the host/database names (never passwords) in any ~/.pgpass or pg_service.conf entries. Go ahead?

Options shown, verbatim:
- **"Yes, read-only (Recommended)"**: "I read those files, record what I find in the install plan, and change nothing. Reading ~/.pgpass and the Homebrew data directory may prompt you for a sandbox exception."
- **"Skip ~/.pgpass"**: "I read pg_hba.conf and data-directory ownership only. You check ~/.pgpass and service files yourself and tell me whether the real cluster has an entry."
- **"Not now"**: "The inventory stays a placeholder in the plan. R8 cannot start until it is done."

**Answer, verbatim:** "Yes, read-only (Recommended)"

Terms: read only; nothing is changed; from `~/.pgpass` and service files only host, port, database and
user names are recorded, never a password field.

## Decision 2 — where the classifier is calibrated

Question asked, verbatim:

> The preflight's CHALLENGED/REJECTED classifier can be calibrated against a real password-only (scram) PostgreSQL before R8. Where should that run?

Options shown, verbatim:
- **"Fin-Web cloud (Recommended)"**: "A cloud session creates a throwaway scram-only cluster there and runs only the opt-in calibration test. Needs no sandbox exception on your Mac. It calibrates only: no real tool, no real data."
- **"Mac, sandbox exception"**: "As the design describes: a throwaway cluster under $TMPDIR on your Mac. Needs you to approve running it with the sandbox off."
- **"Defer to R8"**: "Not calibrated before R8. A mis-calibration fails closed at R8 step 1 and blocks that step until fixed."

**Answer, verbatim:** "Fin-Web cloud (Recommended)"

Terms and consequences:
- This replaces the design's "throwaway cluster under `$TMPDIR` with the sandbox exception" route with the
  owner's `Fin-Web` cloud environment (PostgreSQL 17.11, environment test PASS 2026-11-01). The limits of
  the design's route are unchanged: calibration only, no gateway, no REAL-scope content, no real tool run;
  the installer's accepting side is first exercised at R8 step 1 (design 1.2 rule 7, TR3R-M2).
- The calibration test is opt-in and skips by default. It can run in the cloud only after R6's code is
  committed and pushed, since a cloud session clones from GitHub.
- No real credential goes to the cloud; the throwaway cluster's roles and passwords are invented there.
