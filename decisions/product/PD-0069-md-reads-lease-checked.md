# PD-0069 — Stored market-data rows: lease-checked reads, so a lapse or withdrawal stops them

**Status:** accepted
**Date:** 2026-10-25 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0066 decision 5 ("All rights off") and decision 6; PD-0068 answer 1;
`implementation/CP7_F1_REAL_PATH_DESIGN.md` (uncommitted; round 4, 3126 lines, SHA-256 `d5c50b9b…7835`)
D3 row, 1.2 rule 4, 2.6 item 2, 3.1 (E4 row), 3.3, W05, sections 7, 8.1 and 9; review findings
R4R-M1 and TR4R-M1 (`reviews/TECH_REVIEW.md`, "Reviews of 2026-10-25 F1 design round 4").

## Context

After round 4 the design narrowed its deadline claim. The rooted tables and the archive are read
only under a lease bounded by `complete_by`. The `md_*` tables (the stored market data, including
the Alpha Vantage closes in `md_quote`) are not:
- the executor reads them by plain SELECT inside `read_release` (HEAD
  `src/persistence/market_data_store.py:18-19`, `:694-740`);
- they carry no row security;
- so a holder of the executor or loader credential can read them with no lease, after a lapse or a
  withdrawal too.

The design listed this as an accepted F1 limit. Both round-4 re-reviews found that the owner had not
accepted it (R4R-M1, TR4R-M1). PD-0066 decision 5 was "All rights off". The proposal had told the
owner that a withdrawal stops the database runtime, and left only the raw files, the download tool
and the legacy CLI uncovered.

The main session explained the two choices:
- **(a) Lease-checked reads.** A read function checked against the lease replaces the executor's
  plain SELECT on `md_*`.
  - It keeps "All rights off" literal inside the database.
  - It is gateway SQL, so R3 builds it, and it changes how W05 calls `read_release`.
  - It costs one more design item before R1.
- **(b) Accept the limit.** The limit is stated in the HG4 package, and both roles are set `NOLOGIN`
  at a withdrawal.
  - It is cheaper.
  - The raw files on disk are already outside the lease.
  - The `NOLOGIN` step does nothing for a lapse.

The main session recommended (a).

## Decision

Question asked, verbatim:

> After a lapse or withdrawal, how should the stored Alpha Vantage quotes be handled?

Owner's answer, verbatim:

> **"md_* question: ask for a lease-checked read function in place of the executor's plain SELECT on md_*, so a lapse or withdrawal stops those reads too (All rights off, kept literal). Then run the round-5 fix with re-review."**

## What this means

- **The executor's plain SELECT on the `md_*` tables is replaced** by a lease-checked read
  function.
  - A read of `md_*` rows on the executor's connection needs an admitted lease, with the same
    statement-time bound as the other reads: `clock_timestamp() < complete_by`, and
    `complete_by <= valid_until` (PD-0068 answer 1).
  - A lapse or a withdrawal therefore stops those reads, as it stops the gateway's four rights
    (PD-0066 decision 5, kept literal).
  - The executor keeps no direct SELECT on the `md_*` tables.
- **Where it lands:** the function is gateway SQL, so it is built in R3, in line with the design's
  rule that no increment after R3 adds gateway SQL. `read_release` (W05) is called through it in R5.
  The engineer states the exact grants and how the release reader's existing contract is kept, in
  the design's next revision, for review.
- **Not decided by this answer:**
  - **The loader's own reads.** The loader writes `md_*` rows and reads `md_file`
    (`market_data_store.py:283`). The engineer narrows the loader to what loading needs and states
    what remains. Anything still readable after a lapse or withdrawal goes back to the owner as a
    question; it is not an accepted limit until the owner accepts it.
  - **The proposed `NOLOGIN` step** for the roles at a withdrawal (design 3.3). It is no longer
    needed for the executor's `md_*` reads. Whether it is still wanted for the loader is part of the
    item above.
- **Unchanged:** the raw payload files on disk, the download tool and the legacy CLI stay outside the
  database and outside the lease. The owner procedure of PD-0066 decision 9 (move the raw files
  aside, do not run the legacy tools) still covers them.
- This is a mechanism the owner chose. The owner's instruction for the fix rounds ("Prefer narrowing
  claims and conforming to the decisions over adding new mechanisms") still applies to everything
  else in round 5.

## What this does not do

It changes no file other than this record and STATUS.md, builds nothing, and approves no gate. The
design stays uncommitted until it is revised, reviewed and the owner asks for the commit (PD-0066
decision 10).
