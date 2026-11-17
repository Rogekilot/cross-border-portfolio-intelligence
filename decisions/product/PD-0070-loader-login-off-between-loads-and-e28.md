# PD-0070 — The loader's login is off between loads; market-data reads narrowed to create and reproduce (E28)

**Status:** accepted (decisions 1–2)
**Date:** 2026-10-25 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0066 decisions 5 and 7; PD-0069; `implementation/CP7_F1_REAL_PATH_DESIGN.md` (uncommitted;
round 5, 3579 lines, SHA-256 `b5a7a866…ca0f`):
- §8.1 item 12 (the loader's reads; gates R2);
- 3.3, 2.6 item 6, 8.2 E28, 1.2 rule 4, the R2, R6 and R8 rows, sections 7 and 9;
- review findings R5R-M1, R5R-L1 and TR5R-M1 (`reviews/TECH_REVIEW.md`, "Reviews of 2026-10-25 F1 design
  round 5").

## Context

Round 5 reflected PD-0069. The executor now reads the `md_*` tables only through lease-checked
functions. The loader was narrowed to what loading needs:
- INSERT on the 13 `md_*` tables;
- SELECT on `md_file` and `md_release`;
- EXECUTE on the candidate registry's put and get functions.

Even narrowed, it can still read the following with no lease, whenever its role can connect, after a
lapse or withdrawal too:
- the file manifests and release definitions;
- through the registry's get function, the raw payload bytes, including the AAPL closes.

PD-0069 sent this back to the owner as a question. The design's item 12 offered options (a) to (d)
and said none of them stops the loader at a lapse. Both re-reviews found that it omitted an owner
step the engineer had identified, which does stop the loader at a lapse (R5R-M1, TR5R-M1). The main
session added that step to the question. It also asked about the engineer's specification choice
E28, which is narrower than PD-0069's "an admitted lease".

## Decision 1 (design §8.1 item 12): the loader's login is off between loads

Question asked, verbatim:

> After a lapse or withdrawal, what may the market-data loader's login still read (design §8.1 item 12)?

Options shown, verbatim:
- **"Off between loads (Recommended)"**: "You set the loader NOLOGIN right after its last R8 use, and LOGIN
  again only when you load new data. New loader connections then fail after a lapse too. Limits: stops new
  connections only (ending an open session is not shown); the superuser and owner role are not affected;
  each later load needs your LOGIN step. No new mechanism."
- **"Accept, NOLOGIN at withdrawal"**: "Option (b): accept the leftover reads as a recorded limit, and set
  the loader NOLOGIN only when you withdraw. It does nothing at a lapse, which needs no act from you."
- **"Accept as a limit"**: "Option (a): whenever it can connect, with no lease, the loader can read the
  file manifests and release definitions, and the raw payload files through the candidate registry,
  including the AAPL closes. R6 decides who holds this login, and an agent may hold it."
- **"Narrow further"**: "Option (c): the loader sees only hash columns and yes-or-no answers, and the
  registry returns digests, not bytes. More gateway SQL and a change to the registry's calls, and still no
  stop at a lapse by itself."

The main session did not offer option (d), keeping the count read-back. It would give the loader
SELECT on the quotes too, and the design does not recommend it.

Owner's answer, verbatim: **"Off between loads (Recommended)"**

What this means:
- **Owner procedure.** Right after the loader's last use in R8, the owner sets the loader role
  `NOLOGIN` in the owner's own terminal. For any later load, the owner sets `LOGIN`, loads, then sets
  `NOLOGIN` again. Each step is an owner act. The design states where in R8 the "last use" falls.
- **Effect.** Between loads, no new connection as the loader succeeds, whether the context is live,
  has lapsed or was withdrawn. So the loader's narrowed reads are not available after a lapse, except
  during a load window the owner opens.
- **The loader's list stays as round 5 narrowed it.** No further narrowing (option (c)) and no
  count read-back (option (d)).
- **Limits, as shown to the owner and accepted with this choice:**
  - It stops new connections only. Whether `NOLOGIN` ends a session that is already open is not
    shown.
  - The superuser and the owner role are not affected.
  - Each later load needs the owner's `LOGIN` step.
- **During a load window the owner opens,** the loader can read what its narrowed list allows,
  including the payload bytes through the registry. The design states this as part of the procedure.
  It does not count as an accepted limit beyond the owner's own opening of the window.
- **No new mechanism** was part of the option. Whether a tool should report the loader's login state
  is for the engineer to propose in the next revision, under the owner's instruction for these rounds
  ("Prefer narrowing claims and conforming to the decisions over adding new mechanisms"), for review.
- **R2's gate on item 12 is met** by this answer. R2 still follows the design's commit and R1.
- **R6** still decides who holds the loader credential (1.2 rule 4). Under this answer, nobody can log
  in with it outside a load window the owner opens.

## Decision 2 (design E28): only create and reproduce read the stored market data, for their own release

Question asked, verbatim:

> Design choice E28: may only create and reproduce operations read the stored market data, and only the one release their context names?

Options shown, verbatim:
- **"Accept the narrowing (Recommended)"**: "Only EXECUTE_CREATE and EXECUTE_REPRODUCE leases may call the
  md_* read functions, and only for the release the context's snapshot names. Archive read and export
  leases read stored outputs, not market data. This is stricter than PD-0069's \"an admitted lease\"."
- **"Any admitted lease"**: "Keep PD-0069 literal: any admitted lease of the context may read md_* rows,
  still bounded by its complete_by deadline."

Owner's answer, verbatim: **"Accept the narrowing (Recommended)"**

What this means:
- **Who may call the `md_*` read functions:** only leases with purpose `EXECUTE_CREATE` or
  `EXECUTE_REPRODUCE`, and only for the release the context's snapshot names. Each call is still
  bounded by `clock_timestamp() < complete_by` (PD-0069; PD-0068 answer 1).
- **Leases that may not:** `ARCHIVE_READ` and `ARCHIVE_EXPORT` leases do not read market data. They
  read stored outputs only.
- E28 is no longer only the engineer's choice; it is the owner's.

## What this does not do

It changes no file other than this record and STATUS.md, builds nothing, and approves no gate. The
design and PD-0069 stay uncommitted until the design is revised and reviewed and the owner asks for
the commit (PD-0066 decision 10).
