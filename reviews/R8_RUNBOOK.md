# R8 runbook: the first real install and run (owner's procedure)

**Status:** draft for review, 2026-11-14. Written by the main session (PM) from `implementation/CP7_F1_REAL_PATH_DESIGN.md`
(7.1 R8 row, 1.2, 3.3, 6.1), `implementation/CP7_F1_R6_INSTALL_PLAN.md` (sections 4 to 9 and the command inventory, section 14),
PD-0068, PD-0076 to PD-0078 and PD-0081. Where this runbook and those documents disagree, they win; tell the main session.

**Who does what.** You (the owner) run every step in your own terminal. No agent runs an R8 step, holds a real password, or is
told one. The main session may record your decisions verbatim (the PD files below), compute a file's SHA-256 for you, and
assemble the HG4 package afterwards. Nothing here has been run against a real cluster.

**Amended 2026-11-15 (owner's choice "Build option 1"):** section G, the guided runner, is now the way to run R8. Sections 0 to 12
stay as the reference: the runner follows them step by step, and they say what each step does. Do a step by hand only if the main
session tells you to after a stop.

---

## G. The guided path (use this)

The runner `real_tools.r8_guide` (design note `implementation/CP7_F1_R8_GUIDED_RUNNER.md`) does the mechanics:
- runs the reviewed tools with the command lines of sections 3 to 11;
- carries values from step to step (context hash, generations, ids, evidence citations);
- runs the `sudo` cluster setup and the loader windows' psql sessions;
- starts and stops the launcher and Vite;
- compares the NAV with the Quant's figure;
- writes every [record] item to `~/finweb-r8/`.

It never sees a password. Every password is typed at the prompt of the program that needs it: `sudo`, `initdb`, `psql`, or a reviewed
tool.

**What you still do:**
- type passwords when a prompt asks;
- approve the qualification listing and the proposal;
- write and commit your three decision records when it pauses for them (publish, withdraw, renew), or ask the main session to
  record your words and commit them;
- fill in and click Create in the browser, then type in what the screen shows;
- answer its check questions.

### G.1 Once, before the first run

```bash
cd ~/Desktop/"Fin Web"
git status --porcelain          # must print nothing
git log -1 --format='%H %s'     # R8 runs from this commit; the runner records it as P8
unset $(env | grep -o '^PG[A-Z_]*') 2>/dev/null
env | grep '^PG'                # must print nothing
ls ~/.pgpass ~/.pg_service.conf 2>/dev/null   # must list nothing
```

Keep agent sessions from editing this repository while R8 runs. A dirty tree makes the runner refuse before every password step.

### G.2 The one command (run it again to resume)

```bash
PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_guide
```

**Do not edit, move or delete** `~/finweb-r8/state.json` or `~/finweb-r8/events.log`. **Do not upgrade PostgreSQL**
(`brew upgrade`) during R8: the runner records the versioned path of the PostgreSQL programs on its first run. The full output of
every tool goes to `~/finweb-r8/transcript.log`.

On the first run it uses these values, then freezes them:
- macOS user `finwebpg`;
- base directory `/Users/Shared/finweb-r8-pg`;
- port `5433`;
- superuser `finweb_su`;
- release name `hg4-aapl-2026-09-30`. This one becomes part of the release id permanently.

To change any of them, pass `--cluster-user`, `--base`, `--port`, `--superuser` or `--release-name` on the first run only.

The runner explains each step and waits for Enter before anything that writes, asks for a password, or uses `sudo`. You can stop
at any of those pauses (type `quit`), or between sittings, and continue later with the same command.

**What creating the cluster user does.** It runs `sysadminctl -addUser`, which asks for the new user's password. That prompt is
the one step the build could not test. If it misbehaves, create the user yourself in System Settings → Users & Groups → Add User…,
type **Standard**, name `finwebpg`, and re-run the runner. It verifies an existing user rather than creating it.

**The create (section 9 item 4).**
- The runner prints the four form values and the file each comes from. Check them before you click Create.
- Then type the status and code the screen shows. Only `422 REAL_REQUEST_INVALID` and `404` let you correct and retry.
- Any other refusal, UNKNOWN or 503 stops R8 (rule 0.3).

### G.3 Options

| Option | Use |
|---|---|
| `--status` | where the run stands, any stop, and whether a loader window is open |
| `--close-window` | closes an open loader window (works even after a stop; the runner prints this when a window is open) |
| `--resolve STEP retry\|done` | your statement about a step that was interrupted before its end was recorded, when the runner asks for it |
| `--reset-stop PD-NNNN` | lifts a stop, only after the main session's reviewed fix is committed and your decision record about it is committed after the stop; you then type `RESET R8 STOP`. The new commit becomes P8; the old one stays in the record |

### G.4 Mistyped passwords (clarifies rule 0.4)

A login that failed before the tool did anything is not a refusal. The runner says what happened (for a tool: "The tool could not
connect (CODE); nothing was sent. A mistyped password is the usual cause.") and asks "Retry after a mistyped password? [y/N]",
allowing at most 3 retries per step; one more failure is a stop. Answering no ends the run without a stop; run the command again
when ready. Each failed attempt is recorded with its time, never with what you typed.

This applies:
- at `sudo` and `psql` (a failed login, or a `\password` mismatch);
- at the reviewed tools' own connect failure, which says nothing was sent;
- at `identity_seed`, whose transaction is rolled back;
- at the launcher's account-role prompt.

`real_install phase1` stops on any failure. A server that did not complete SCRAM (`PF_REQUIRE_AUTH`) is a refusal, not a typo.

### G.5 When it stops

There are two kinds of ending that are not success.

**A refusal without a stop (exit 2).** Examples: a dirty tree, a moved HEAD, a Phase 0 refusal, or a missing file. The runner
says what to fix. Fix it and run the same command again.

**A stop (exit 3).** This is rule 0.3 or 0.4.
- The runner writes the stop into its state and its append-only log, prints what happened, and refuses to continue on a plain
  re-run.
- If a loader window is open, the runner first tries to close it. That close asks at once for the superuser password, with no
  Enter pause, so expect the prompt.
- If the window is still open afterwards, the runner says so. Run the `--close-window` command it prints.
- Then give the main session the stop's code and output, from `~/finweb-r8/events.log` or `--status`. Never include a password.

**If the runner refuses with `STATE_MISSING`,** `state.json` has been lost and the runner will not start afresh, not even
`--close-window`. Do two things:
1. Close any loader window by hand with the psql statements of section 5.5 (the superuser `psql` of section 2).
2. Tell the main session. It will work out from `events.log` where the run stood, and agree with you, under a decision record,
   how to continue.

### G.6 At the end

The runner writes `~/finweb-r8/R8_RECORD.md`: every [record] item with its time zone, exit statuses, codes, the context hash,
generations, the check results and the create outcomes. Give the main session that file and anything that surprised you (section
12). Keep `~/finweb-r8/` (mode 0700) until HG4 is decided.

To stop the cluster afterwards:
`sudo -u finwebpg /opt/homebrew/bin/pg_ctl -D /Users/Shared/finweb-r8-pg/data stop`.

### G.7 The supplementary run (PD-0087, PD-0088)

The owner returned HG4 as revision required (PD-0087). This run collects, on R8's database and context, what R8 did not:
- replay and idempotency;
- the conflict case;
- the error digest;
- a restart, then read and reproduce;
- user B's 404.

It also re-evaluates check 10.1 under the corrected check.

**Before you start.** The commit S8 must hold the tool, the runner and the screen fixes, and be reviewed. The working tree must be
clean, with no `PG*` variables and no passfiles (as in G.1). The cluster must be running. Leave `~/finweb-r8/` alone: the
supplement never writes there. Its own state and record are in `~/finweb-r8-supplement/`.

**The one command**, from the repository root (run it again to resume):
`PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_supplement`

`--status`, `--resolve STEP retry|done` and `--reset-stop PD-NNNN` work as in G.3.

It installs nothing, publishes nothing and loads nothing. It uses context `c6b6f499…` at generation 3.

**The prompts, as printed:**
- **sudo:** your macOS password, at sudo's own prompt.
- **The launcher:** the executor password, then the account password, each time it starts. It starts twice.
- **The tool:** `Password for role web account <name> (screen sign-in, not a database role):`. Type the **screen** password of
  user B (once), or of user A (once before the restart, once after). **Never type a database password there.**
  - A refused sign-in asks `Retry after a mistyped password? [y/N]`, at most 3 retries per step.
  - On a retry for B, the runner asks `User B's username again (Enter to keep <name>):`.
  - If the sign-in is rate limited, it prints `The sign-in is rate limited. Nothing is counted; wait a few minutes.` and waits
    for Enter.
- **The runner:**
  - `User B's username (the existing account; its password is asked by the tool):`.
  - Before each phase that sends create-route requests, it lists the requests, prints "I understand the ledger is constructed by
    the project for testing and is not my holding." and asks `Do you make that statement for all of them? (yes / no):`.
  - `Optional: the name you remember typing for R8's first create (Enter to skip; one attempt, a conflict writes nothing):`.
  - `Optional, one minute: read R8's first root on the screen once more and type its figures? (yes / skip):`. If you answer
    `yes`, it asks for each figure the screen shows.
  - At the end: `Anything that surprised you? (free text, no passwords; Enter for none):`.
  - Also, as in R8 (G.2):
    - on the first run, the prompt that freezes the reviewed commit S8;
    - an Enter gate before each step that writes, asks for a password, or uses sudo;
    - at the screen step, a `pass` / `fail` question and an optional note for each thing it asks you to look at.

**The order.** There are two sittings, around the restart:
1. **Start:** the launcher on `C2.json` and Vite.
2. **User B, read-only, before any create:**
   1. B signs in, and B's list must be empty.
   2. Four requests, each of which must be the same 404 `RW_NOT_FOUND`, byte for byte: A's first root (read and reproduce), an
      unknown id, and a malformed id.
3. **User A:**
   1. A's list must hold exactly 2 roots.
   2. Read A's first root, keeping its digests.
   3. Create Y (rule 0.3: 201), then read Y, keeping its digests.
   4. Replay Y (200, `replayed: true`).
   5. A conflicting reuse of Y's operation id (409).
   6. A quantity-0 request (422) and a request naming a context the launcher does not serve (404).
   7. The list must now hold 3.
   8. Optionally, one attempt at R8's own operation id with the name you remember.
4. **Stop the launcher and Vite.**
5. **Stop PostgreSQL** (refused while port 8004 or 5175 is open), then **start it**. The new server PID must differ.
6. **Start the launcher and Vite again.**
7. **User A again:**
   1. The list must hold 3, including Y.
   2. Read A's first root, and compare its digests with the kept ones.
   3. Reproduce it: `REPRODUCED`, with the same `issued_sha256`.
   4. Read Y, compare its digests, replay Y (200), and send the conflict again (409).
8. **Look at the screen.** For each item the runner names, answer `pass` or `fail`:
   - Open from the list;
   - the password hint;
   - reproduce shows `REPRODUCED`;
   - typed values clear on sign-out.

   Optionally, re-read R8's first root and its Key figures.
9. **Check 10.1** is re-evaluated, then the record `~/finweb-r8-supplement/SUPPLEMENT_RECORD.md` is written.

**How it ends.** **Read the last lines, not only the exit code.**

- **Done:** exit `0`.
- **Paused:** exit `1`. You quit or pressed Ctrl-C. Run the same command again.
- **Stopped, with a latch:** exit `2`, and the last lines say **"Tell the main session: R8 stopped at step … with … The runner now
  refuses every later run until a reviewed fix is committed and --reset-stop is used."**
  - Do not re-run anything. Copy those lines to the main session.
  - It happens on anything unexpected after a create was sent: an unexpected answer, a create whose outcome is unknown, a refused
    connection, or an uncaught error. It also happens when the password retries are used up (`PASSWORD_RETRIES_EXHAUSTED`), on a
    launcher refusal, and when the kept digests are missing (`HTTP_PRE_DIGESTS…`).
  - A later run of the command refuses with exit `3`.
- **Stopped, with no latch:** exit `2`, and the last line says **"(No latch: fix the cause and run again.)"**. The `STOP [CODE]`
  line above it says why:
  - **`ACK_NOT_GIVEN`** (you answered "no"), a declined retry, or **`LAUNCHER_NOT_ANSWERING`**: nothing was sent. Run the same
    command again when ready.
  - **`HTTP_<STEP>_FINDING`**: the tool found something unexpected **before any create**, for example B's list not empty or one of
    A's roots in B's list. The tool's own lines just above say which. Nothing was created. Do not retry. Tell the main session.
  - **`HTTP_<STEP>_USAGE`**: a build fault, and nothing was sent. Tell the main session.
  - **`STEP_INTERRUPTED`** at the A step before the restart: that step may have started its creates. Look at
    `~/finweb-r8-supplement/transcript.log`, then run with `--resolve http_pre retry`. The rerun resumes with Y's saved id.
    `--resolve http_pre done` is refused.
  - **`CLUSTER_STOP_FAILED`**: the cluster's state is unknown. Run the same command again; the stop step checks `pg_ctl status`
    and resumes.
  - **Any other code**, such as `SERVICES_RUNNING`: follow the message. If it is unclear, tell the main session before you run
    again.

**Expected answers.** They are listed under rule 0.3.

**Labels for the HG4 package:**
- Replay, conflict and B's 404 are sent by the tool directly to the launcher on loopback. They are not clicked on the screen.
- The restart is a clean postmaster stop and start, not a crash or a host reboot.

---

## 0. Rules for the whole run

1. **Passwords.** Type a password only at the prompt of a tool run from the reviewed, committed tree, with a clean working tree
   (`git status --porcelain` prints nothing), in your own terminal. Never on a command line, in an environment variable, a file, a
   passfile, a service file, or a chat message. Set role passwords only with psql's `\password <role>`, never a literal
   `PASSWORD '...'`.
2. **The prompt-route check is not the preflight.** Every tool that connects runs the prompt-route check before it asks for a
   password, `withdraw` included. It checks that the tool's own prompt and connection functions are the reviewed ones. The REAL
   preflight gate is a different thing; it runs only at the start of `publish`, `renew`, the launcher (`serve`) and the admission
   probe (`admit`). `withdraw` and the loader window are not gated (design 1.2 rule 5.1; the loader window was decided by the PM on
   2026-11-14: each window has its own `real_install check`).
3. **PD-0081's stop rule.** If the real commit of the create (section 9 item 4; design R8 step (5)) is refused or its outcome is
   UNKNOWN: R8 stops at that point; nothing is re-run, by hand or by a tool, until the cause is found and a reviewed fix is
   committed; the outcome, its code and what was observed go in the HG4 package as a first-run observation.
   **Clarified by PD-0083 (with its correction note):** only two responses come before any lease or commit: `422
   REAL_REQUEST_INVALID` (a malformed request) and `404` (a context the launcher does not serve). On those two, correct the input
   and retry, and record the refusal and its code for the HG4 package. **Every other refusal, and any UNKNOWN or 503, stops R8.**
   A well-formed but wrong context, release or listing id is checked after admission, inside the real branch, so it stops R8:
   compare the three ids with `P.json` and `F.json` (section 9 item 4) before you click Create. This applies to every real create
   in this runbook, including the one in section 11.6.

   **Expected answers in the supplementary run only** (section G.7; PD-0087, PD-0088). These exact answers are expected there
   and do not stop the run:
   - `200` with `replayed: true`, for a replay of Y;
   - `409 RW_IDEMPOTENCY_CONFLICT`, for the conflicting reuse of Y's operation id. It also covers the optional single attempt at
     R8's own operation id when the name differs; that writes nothing;
   - `422 REAL_REQUEST_INVALID`, for the quantity-0 request;
   - `404 RW_NOT_FOUND`, for the request naming a context the launcher does not serve, and for user B's requests for A's root.

   Each refused body must equal the contract's refusal body for its code, byte for byte. The count of A's roots must not change
   after a refusal.

   **After a create has been sent**, anything else stops the run and **latches**:
   - a different code;
   - a 5xx, 503 or UNKNOWN;
   - a 201 where none is expected;
   - a differing body, digest or count;
   - a reproduce status other than `REPRODUCED`;
   - a refused connection.

   **Before any create**, the same answers stop the run **without** a latch (`HTTP_<STEP>_FINDING`), because nothing was written.
   That includes the case where A does not have exactly 2 roots before Y: then Y is not created, and the main session takes it up
   as a rule-0.3 matter for R8.
4. **Other stops.** Stop on any installer refusal (Phase 1 or 2, `check`): a refused install stays unused until a reviewed fix
   (design 1.2 rule 7; install plan section 7). A Phase 0 refusal is resolved and Phase 0 re-run (it writes nothing; section 3.2).
   A login that failed before the tool did anything is not a refusal (section G.4). Stop on any tool exit status other than 0 that this runbook does not tell you how
   to handle. Exit statuses: `0` done, `2` refused, `3` not yet effective (`withdraw` only, section 11), `4` unknown, `5` lock
   timeout.
5. **Record times.** Note the time (with zone) of every step marked **[record]**; the HG4 package needs them.

## 1. Preconditions (design 7.1 R8 row). All must hold before step 1

| # | Precondition | Where it stands (2026-11-14) |
|---|---|---|
| P1 | R5 to R7 built; the pre-R8 items closed | This round: see STATUS.md "Pre-R8 session, 2026-11-14" |
| P2 | `SOURCES.json` updated (R4a) | Done; `alphavantage.us` notes shortened to fit the registry, owner decision 2026-11-14 |
| P3 | One valid sidecar per member, three (R4b, 6.1) | Written by the main session, `data/marketdata/sidecars/` (see step 4) |
| P4 | `valid_until` not past | `2027-08-31T16:00:00Z` (= 2027-09-01 00:00 Asia/Shanghai, PD-0068 answer 4, PD-0072) |
| P5 | The owner's answer to design 8.1 item 11 is an acceptance | PD-0081, "Accept, stop on failure" |
| P6 | R7's exit statement on two-user isolation; D-3 not declared | STATUS.md, R7: "D-3 is not declared" |
| P7 | The cloud `!password` run (install plan section 5 precondition) | Passed 2026-11-02, 13/13 (STATUS.md, "Cloud `!password` run") |
| P8 | Everything above **committed**, and you run from that commit | You choose the commit; record its hash **[record]** |
| P9 | `.claude/settings.local.json` is not tracked | Untracked and ignored (PD-0083); holds once that change is committed |

## 2. Before you start

```bash
cd ~/Desktop/"Fin Web"
git status --porcelain          # must print nothing
git log -1 --format='%H %s'     # the reviewed commit; record it
unset $(env | grep -o '^PG[A-Z_]*') 2>/dev/null # every PG* variable (PGPASSWORD, PGOPTIONS, PGHOST, ...)
env | grep '^PG'                                # must print nothing
ls ~/.pgpass ~/.pg_service.conf 2>/dev/null   # must list nothing
export PYTHONPATH=src
mkdir -m 700 ~/finweb-r8        # R8 working files live OUTSIDE the repository, so the tree stays clean
```

In what follows, `fw` stands for `uv run --no-sync --frozen --offline python -m` (run from the repository root). Placeholders:
`<SOCKDIR>` and `<PORT>` (the real cluster's socket directory and port; `<SOCK>` = `<SOCKDIR>/.s.PGSQL.<PORT>`), `<SU>` (the
superuser name), `<NAME>` (the release name: your choice, it enters the release id and so the context, permanently; for example
`hg4-aapl-2026-09-30`). `psql` below means `psql -h <SOCKDIR> -p <PORT> -U <SU> -d finweb_real` (it prompts for the superuser
password).

The three members (design 6.1) and their sidecars:

| Member | Payload SHA-256 | Sidecar |
|---|---|---|
| `alphavantage.us/quote/2026-10-01/AAPL_compact.csv` | `066c65e6…b1b9d1fb` | `data/marketdata/sidecars/alphavantage.us/quote/2026-10-01/AAPL_compact.csv.sidecar.json` (S1) |
| `openfigi/identity/2026-10-23/AAPL_UW.json` | `b2aaeb7b…889c3ccc` | `data/marketdata/sidecars/openfigi/identity/2026-10-23/AAPL_UW.json.sidecar.json` (S2) |
| `calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json` | `4f21b26b…3d5f72ef` | `data/marketdata/sidecars/calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json.sidecar.json` (S3) |

`INPUTS` below stands for the same input arguments every time (the tools rebuild the qualification from them and refuse unless the
result equals the reviewed proposal `P`):

```
--store-root data/marketdata --release-name <NAME> \
--file 066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb \
--file b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc \
--file 4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef \
--sidecar <S1> --sidecar <S2> --sidecar <S3> \
--registered-check 4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef
```

## 3. Step (1): the cluster and the install (install plan sections 3 A, 4 and 5)

1. **macOS user and cluster** (install plan section 4 items 0 to 3). Create a dedicated standard macOS user for the cluster (not
   your everyday account that agent sessions run as, not an administrator). As that user (`sudo -u <cluster-user> ...` from your
   terminal), create the data directory (mode `0700`) and the socket directory outside the project and `$TMPDIR`. The socket
   directory's mode must let your own account reach the socket (not `0700`, or Phase 0 cannot connect); that mode is also what it
   leaves open to agent sessions. Then:
   ```bash
   sudo -u <cluster-user> initdb -D <DATADIR> --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwprompt -U <SU> -E UTF8 --locale=C
   ```
   Edit `pg_hba.conf` to hold only `local   all   all   scram-sha-256` (plus optional `local all <role> reject` lines; no `host`,
   no `trust`/`peer`/`ident`, no replication line). In `postgresql.conf`: `listen_addresses = ''`,
   `unix_socket_directories = '<SOCKDIR>'`, `password_encryption = scram-sha-256`, `max_prepared_transactions = 0`,
   `log_statement = 'none'`, `log_min_duration_statement = -1`. Start it as that user with `pg_ctl`. **[record]** the owners and
   modes of the data and socket directories, and that your everyday account cannot write `pg_hba.conf` or the data directory.
2. **Phase 0** (writes nothing): `fw persistence.real_install phase0 --socket <SOCK> --user <SU>`. Resolve any refusal before going on.
3. **Phase 1:** `fw persistence.real_install phase1 --socket <SOCK> --user <SU> --loader-login nologin`. Not one transaction; on
   failure it exits `4` and what ran stays (stop; rule 0.4). **[record]**
4. **Passwords** (PD-0077, PD-0078), in `psql`: `\password finweb_real_publisher`, `\password finweb_real_executor`,
   `\password finweb_real_account`. The loader gets its password per window (steps 5 and 8), not here.
5. **Phase 2** (read-only; the first read of a REAL catalog): `fw persistence.real_install phase2 --socket <SOCK> --user <SU>`. A
   refusal here: stop; the install stays unused until a reviewed fix. **[record]**

## 4. Step (2) a: the offline qualification (no connection, no password)

```bash
fw real_tools.qualify_run INPUTS --proposal-out ~/finweb-r8/P.json --seed-out ~/finweb-r8/F.json
```

It writes two new files and never overwrites. Read its listing now: the three payload and manifest hashes against PD-0066's table,
O5 passing for all three members, and no "needs review" line (the calendar is `--registered-check`ed, so it should not show
`NOT_CONFIRMED`).

## 5. Step (2) b to e: the identity seed, then loader window 1

1. **Identity seed** (must come before the load: the observation tables reference `listing`):
   `fw real_tools.identity_seed --socket <SOCK> --user <SU> --seed-file ~/finweb-r8/F.json --proposal ~/finweb-r8/P.json`
2. **Open window 1** (install plan section 6), in `psql`: `ALTER ROLE finweb_real_loader LOGIN;` then `\password finweb_real_loader`
   (a fresh password for this window). **[record]** the time `LOGIN` was set.
3. `fw persistence.real_install check --socket <SOCK> --user <SU>`. A refusal stops the window before anything is loaded.
4. **The load:**
   `fw real_tools.loader_window load --socket <SOCK> --database finweb_real --user finweb_real_loader --schema finweb INPUTS --proposal ~/finweb-r8/P.json`
   (type the loader password at its prompt). It loads the release into the `md_*` tables and registers the UNBOUND candidate.
   - Exit `0`: go on. An identical re-run says "already loaded" and adds nothing.
   - Exit `4` (UNKNOWN): **the window stays open.** Run the command the tool prints (for a registration, `... reconcile
     --candidate unbound ...` with the same arguments; for a load whose own outcome is unknown, the identical `load` again). If
     `reconcile` finds nothing, re-run the identical `load`, which is idempotent. Close the window only once the answer is definite.
   - Exit `5` (lock timeout): re-run the identical command; it is safe.
   - Exit `2`: stop; note the code.
5. **Close window 1**, in `psql`: `ALTER ROLE finweb_real_loader NOLOGIN;` then end any open loader session (R2 L-3; `NOLOGIN` does
   not end one):
   ```sql
   SELECT pid, backend_start FROM pg_stat_activity WHERE usename = 'finweb_real_loader';
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'finweb_real_loader';
   ```
   Repeat the first query until it returns no row. **[record]** the time the last loader session ended.

## 6. Step (3): review the proposal

Read `~/finweb-r8/P.json` and the qualify listing. You may ask the main session to walk you through it by pasting parts into the
chat (the file holds hashes and identifiers, not passwords). Do not copy it into the project: that would dirty the tree. If anything is wrong,
stop: a re-run of (2) after a fix is a later load (design 7.1 R8 row (4a), last sentence).

## 7. Step (4): the publish

1. **The publish decision record.** Write (or ask the main session to record your words verbatim) `decisions/product/PD-NNNN-r8-publish.md`
   with your decision to publish this release, `valid_until` 2027-09-01 00:00 Asia/Shanghai, and the disclosed upper-bound limit
   (PD-0068 answer 4: `term_end_not_after` is an upper bound). Commit it. Then:
   ```bash
   git log -1 --format=%H -- decisions/product/PD-NNNN-r8-publish.md        # GIT40
   git show <GIT40>:decisions/product/PD-NNNN-r8-publish.md | shasum -a 256 # DOC64
   git status --porcelain                                                     # still nothing
   git diff --stat <P8> HEAD                                                  # only decisions/product/ files
   ```
   Do the same two checks after every later PD commit (sections 11.3 and 11.5).
2. **The expiry-evidence file** (offline). Citations: `alphavantage.us` `LEASE_TERM` cites **PD-0066** (decision 5); `openfigi` and
   `calendar.manual` `NOT_ASSESSED` cite **PD-0068** (answer 4 decided both). For each, the commit is
   `git log -1 --format=%H -- <the PD file>` and the SHA is `git show <commit>:<the PD file> | shasum -a 256`.
   ```bash
   fw real_tools.r8_files evidence \
     --alphavantage-pd PD-0066 --alphavantage-commit <C66> --alphavantage-sha <S66> \
     --openfigi-pd PD-0068 --openfigi-commit <C68> --openfigi-sha <S68> \
     --calendar-pd PD-0068 --calendar-commit <C68> --calendar-sha <S68> \
     --out ~/finweb-r8/E.json
   ```
3. **Publish** (gated; the publisher password):
   ```bash
   fw persistence.real_workspace_store --socket <SOCK> --database finweb_real --user finweb_real_publisher --schema finweb \
     publish --proposal ~/finweb-r8/P.json --sidecar <S1> --sidecar <S2> --sidecar <S3> \
     --valid-until 2027-08-31T16:00:00Z --evidence-file ~/finweb-r8/E.json \
     --actor "designated human product owner" --pd PD-NNNN --commit <GIT40> --sha <DOC64>
   ```
   `--valid-until` is UTC: `2027-08-31T16:00:00Z` is 2027-09-01 00:00 Asia/Shanghai. Do not type `2027-09-01T00:00:00Z` (8 hours
   late; fixing it would take a date correction). **[record]** the context hash and the generation `N` it prints.

## 8. Step (4a): loader window 2, the bound registration

1. Open window 2 exactly as in step 5.2 and 5.3 (`LOGIN`, a fresh `\password`, `real_install check`). **[record]**
2. `fw real_tools.loader_window register-bound --socket <SOCK> --database finweb_real --user finweb_real_loader --schema finweb INPUTS --proposal ~/finweb-r8/P.json`
   - Exit `0`: done. An identical re-run reconciles.
   - Exit `4`: the window stays open; run `... reconcile --candidate bound ...` (same arguments) until it answers; if it finds
     nothing, re-run the identical `register-bound`.
   - Exit `2`: stop. (`RW_PROV_INPUT_MISSING` means no publish was found.)
3. Close window 2 exactly as in step 5.5. **[record]** This is the loader's last use in R8.

## 9. Step (5): the real run

1. **The contexts file** (offline):
   `fw real_tools.r8_files contexts INPUTS --proposal ~/finweb-r8/P.json --generation <N> --out ~/finweb-r8/C.json`
2. **The launcher** (gated, `serve`; two prompts: the executor password, then the account password):
   `fw web_api.real_launcher --socket <SOCK> --database finweb_real --user finweb_real_executor --schema finweb --account-user finweb_real_account --contexts-file ~/finweb-r8/C.json --port 8004`
3. **The screen**, in a second terminal: `cd ~/Desktop/"Fin Web"/web && npx vite --config vite.real.config.ts`, then open
   `http://127.0.0.1:5175/real.html`.
4. **The create.** Sign up a first account (user A). Fill the "Create a root" form:
   - **Context ID:** the context id the publish printed (it equals `context_id` in `P.json`);
   - **Release ID:** `snapshot.release.release_id` in `P.json`;
   - **Listing ID:** the first element of `listings[0]` in `F.json`, expected `8dc364a1-67c8-5d46-8654-cff17ebe25de` (a fixed
     `uuid5`, not vendor data); or read it in `psql`: `SELECT listing_id, ticker, mic FROM finweb.listing;`;
   - **Name:** free text, for example `R8 AAPL`;
   - **As-of date:** `2026-09-30`; **Quantity:** `10`; **Opening cash:** `500` (USD, the reporting currency).

   These are the Quant's HG4 case (`methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` §9.1). Tick the acknowledgement,
   then Create. **[record]** the time and the response status. **If the real commit is refused or UNKNOWN: stop (rule 0.3).**

## 10. Checks at R8 (record each result)

1. **NAV against the Quant's figure, compared numerically** (the screen shows stored text without trailing zeros or grouping):
   the holding value and NAV in ruling `CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` §9.1 ("Key-figure values"), **0** missed
   sessions, state **`AVAILABLE`**. (The vendor values are not repeated here; see the GitHub decision on vendor values.)
   **Corrected 2026-11-16 (PD-0087; TR8R M-1, DR-R8-2):**
   - the screen does not show the close, by design (ruling §8 item 4), so it is not compared;
   - whether to show a stored price row is a separate product decision (DR-R8-2);
   - R8's recorded 10.1 FAIL stays as recorded. The supplementary run (G.7) re-evaluates R8's last typed figures under this
     corrected check, and labels the result a re-evaluation, not a new observation.
2. **The filled key-figures list** in the browser (first seen at R8; PD-0080).
3. **The no-NAV notice's prominence** (bold text only; first seen at R8).
4. **The 7.4 claim-limit wording rendered from the real lineage**, in English and Chinese at all three depths; the real root's
   origin label.
5. **Two-user isolation:** sign up user B; B sees none of A's roots and cannot open A's root by its id.
6. **Reproduce and list** A's root.

## 11. Step (6): the revocation test, withdraw then renew

1. **Owner and root ids for the probe.** The root id is the one the create returned (shown in A's list). The owner id is A's web
   user id, read in `psql` (read-only; never select `password_hash`):
   `SELECT user_id, username FROM finweb.web_identity WHERE username = '<user A>';`
2. **Export before the withdraw (control):**
   `fw real_tools.admission_probe --socket <SOCK> --database finweb_real --user finweb_real_executor --schema finweb --purpose ARCHIVE_EXPORT --owner-id <UUID> --root-id <ROOT> --context <HASH> --generation <N>`
   (gated, `admit`; it rolls back and writes nothing). **[record]**
3. **Withdraw** (not gated). First **stop the launcher** (Ctrl-C), so no screen request holds a lease. Commit a decision record
   `PD-NNNN-r8-withdraw.md` (as in 7.1, with the two git checks), then
   `fw persistence.real_workspace_store --socket <SOCK> --database finweb_real --user finweb_real_publisher --schema finweb withdraw --context <HASH> --generation <N> --actor "designated human product owner" --pd <PD> --commit <GIT40> --sha <DOC64>`.
   - Exit `0`: done. **[record]** the new generation `N'` it prints.
   - Exit `3` (not yet effective: a lease was still in flight): re-run the identical `withdraw`, which completes a pending
     withdrawal.
   - At any point, `fw persistence.real_workspace_store --socket <SOCK> --database finweb_real --user finweb_real_publisher --schema finweb status --context <HASH>`
     shows the head generation and any pending mark, so you need not rely on copied output.
4. **All four rights refused**, each recorded, each showing the withdrawal (not "the context changed"):
   - **create:** write `r8_files contexts INPUTS --proposal ~/finweb-r8/P.json --generation <N'> --out ~/finweb-r8/C1.json`, start the
     launcher on `C1.json`, and try a create. Expect "The context has been withdrawn" (`RW_WITHDRAWN`).
   - **read and reproduce** A's root at the screen;
   - **the list**, with its per-root status;
   - **export**, by direct gateway admission through the admission probe (label it so): the command of 11.2 with
     `--generation <N'>`.
   Then stop the launcher again.
5. **Renew** (gated): commit `PD-NNNN-r8-renew.md` (with the two git checks); write a fresh evidence file
   (`r8_files evidence ... --out ~/finweb-r8/E2.json`, same citations; it never overwrites); then
   `fw persistence.real_workspace_store --socket <SOCK> --database finweb_real --user finweb_real_publisher --schema finweb renew --context <HASH> --generation <N'> --valid-until 2027-08-31T16:00:00Z --evidence-file ~/finweb-r8/E2.json --actor "designated human product owner" --pd <PD> --commit <GIT40> --sha <DOC64>`
   (an equal `valid_until` restores the rights without extending the lease). **[record]** the new generation `N''`.
6. **Rights restored:** write `r8_files contexts ... --generation <N''> --out ~/finweb-r8/C2.json`, start the launcher on
   `C2.json`, and check that A can read, reproduce, list and create again (this create is a real commit too: rule 0.3 applies); rerun the probe of 11.2 with `--generation <N''>` to
   show export restored. **[record]**

## 12. Close, and the HG4 package inputs (step 7)

Stop the launcher and Vite (Ctrl-C). Keep `~/finweb-r8/` (mode 0700) until HG4 is decided. Give the main session (no passwords):

- the reviewed commit hash (P8) and every **[record]** above: the install times, the directory owners and modes, both loader
  windows' `LOGIN` time and last-session-ended time, and the statement that you held the executor's and the loader's credentials
  (PD-0077; no agent session held any);
- the tool outputs (exit statuses, codes, context hash, generations), with anything secret-looking removed;
- the R8 check results (section 10) and the revocation results (section 11);
- the outcome of the real commit (PD-0081: a first-run observation);
- anything that surprised you.

The main session then assembles `reviews/gates/HG4_GATE_REVIEW.md`. It states D-1 and D-2 as not collected on the real context
(PD-0068 answer 3), takes every limit of design section 7 and 3.3's list of what a withdrawal does not cover, and records the
loader-login sequence followed (two windows, PD-0076 C).
