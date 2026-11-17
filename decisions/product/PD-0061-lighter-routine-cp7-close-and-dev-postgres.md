# PD-0061 — Return to the CLAUDE.md routine; close CP7 and prepare HG4; start dev PostgreSQL

**Status:** accepted
**Date:** 2026-10-22 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM), a new session that took over on 2026-10-22.
Recorded, not decided.
**Decision material:** the takeover report in this chat, which asked three questions:
(1) keep the fine-grained proof regime of PD-0045 to PD-0060 or return to the lighter
`CLAUDE.md` routine; (2) the next direction: (a) close CP7 and prepare the HG4 decision,
(b) start CP8 scenarios, (c) settle the real-data source question; (3) whether to start the
shared dev PostgreSQL.

## Owner decision, verbatim

> 1. Go back to the lighter routine in CLAUDE.md: brief, build, re-run tests, independent review, update STATUS.md
> 2. Go for (a)
> 3. start the shared dev PostgreSQL

## What this means

1. **Working routine.** Each increment follows `CLAUDE.md` and `HANDOFF.md` §6: brief the
   owning agent, it builds, the main session checks `git diff` and re-runs the tests,
   an independent reviewer reviews, and `STATUS.md` records what changed, the real test
   result, open issues and the next step.

   The following practices from PD-0045 to PD-0060 are **no longer required**:
   - per-run SHA pin sets and seal receipts;
   - private copied candidate trees under `/private/tmp`;
   - "root" executor and runtime-control receipts;
   - one-off approval records for individual test runs, and the rule against re-running
     suites that already passed.

   The default is now the opposite: re-run the full product suite.

   **Product rules and authority limits are unchanged:**
   - the `CLAUDE.md` invariants and human gates;
   - fictional or synthetic data only, unless a new decision covers real data;
   - no new real-data requests or source admission, no personal files, no new paid
     dependencies, no overnight automation;
   - commits only when the owner asks.
2. **Direction (a).** Next work closes CP7 and prepares the HG4 decision package
   (`reviews/gates/HG4_GATE_REVIEW.md`). Only the owner decides HG4. CP8 scenarios and the
   real-data source question wait.
3. **Shared dev PostgreSQL.** Started by the main session on 2026-10-22 with `pg_ctl`.
   - It is a one-off start, not a launchd service.
   - The first attempt failed with the known macOS "postmaster became multithreaded"
     error. It started with `LANG=C LC_ALL=C`.
   - Data directory `/opt/homebrew/var/postgresql@17`, socket `/tmp/.s.PGSQL.5432`,
     database and role `finweb_dev` (STATUS.md open item 9).
   - It will not restart on its own after a reboot.

## Context recorded at takeover

- The Mac rebooted on 2026-10-22 at 14:56. That cleared `/private/tmp`, so every candidate
  tree, private PostgreSQL instance and test server from the 2026-10-19/20 rounds is gone.
- The code from those rounds was never merged into `src/`. It survives only as handover
  patch packages under `reviews/*/handover/`. Whether to merge or retire it is part of
  closing CP7.
- The trial environments and the old "UNKNOWN" operation that PD-0051 to PD-0060 protected
  no longer exist as running systems. No action on them is needed or possible.
- The default product suite at takeover ran 2777 tests with 1 failure, a new boundary
  regression: `src/persistence/guarded_http_store.py` imports `performance.ledger_view`.
