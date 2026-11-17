# CP7 F1 R8: the guided runner

**Status:** built 2026-11-15 (engineer), not yet independently reviewed. Source: `src/real_tools/r8_guide.py`. Tests: `tests/product/test_r8_guide.py` and
`OrchestratorTests` in `tests/product/test_real_preflight_static.py`. Procedure: `reviews/R8_RUNBOOK.md` (it wins on any detail). Nothing here has been run
against a real cluster.

Run from the repository root: `PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_guide`. One command; run it again to resume.
Options: `--status`, `--close-window`, `--reset-stop PD-NNNN`, `--resolve STEP retry|done`; and on the first run only `--cluster-user`, `--base`, `--port`,
`--superuser`, `--release-name`.

## 1. What it is and is not

It does the runbook's mechanics: runs the reviewed tools with the runbook's command lines, copies values from one step's output to the next, runs the loader
windows' psql sessions, and records every time and exit status. The owner still types every password, approves the qualification and the proposal, writes and
commits the decision records, and clicks through the screen. It decides nothing, computes no financial figure, and has no database connection.

## 2. Stages to runbook sections

| Step ids | Runbook | Notes |
|---|---|---|
| (start) | 2 | clean tree; first run records HEAD as P8; no `PG*` variable, no `~/.pgpass`, no `~/.pg_service.conf` (refused, never unset); later HEAD may move only by commits touching `decisions/product/` alone |
| `cluster_user` .. `cluster_verify` | 3.1 and the owner guide, block B | fixed argument lists, no shell; verify before create; refuse where not idempotent |
| `phase0`, `phase1`, `passwords`, `phase2` | 3.2 to 3.5 | phase 1 with `--loader-login nologin`; the three `\password` in one psql session |
| `qualify`, `qualify_approve` | 4 | `P.json`, `F.json` in `~/finweb-r8/`; explicit `approve` |
| `seed`, `w1_open`, `w1_check`, `w1_load`, `w1_close` | 5 | exit 4: the printed reconcile, then the identical load; 5: again; 2: stop (and close the window) |
| `proposal_review` | 6 | key fields of `P.json`; explicit `approve` |
| `pub_pd`, `pub_evidence`, `publish` | 7 | GIT40 and DOC64 from `git log -1` and `git show`; E.json; context hash cross-checked against `P.json` |
| `w2_*` | 8 | `register-bound` with the same handling |
| `contexts`, `create` | 9 | launcher (two prompts) and Vite; form values with their source; create classified by rule 0.3 |
| `check_*` | 10 | NAV compared as Decimal against ruling 9.1; the others are the owner's pass/fail with a note |
| `probe_ids` .. `probe_n2` | 11 | owner id by a read-only query (never `password_hash`) |
| `close` | 12 | `~/finweb-r8/R8_RECORD.md` |

## 3. Prompts and captured output (the hard constraint)

**No password passes through the runner.** It has no `getpass`, asks no password question, and its own prompts (`enter`, `typed`) are for Enter, `quit`, and
short non-secret answers, and say so.

The reviewed prompts read the controlling terminal, not stdin and not stdout:
- the tools' `real_preflight.terminal_prompt` is `getpass.getpass`, which opens `/dev/tty`;
- psql's `\password`, `initdb --pwprompt` and `sudo` read `/dev/tty` too.

So a child's stdout and stderr are piped to the runner (and echoed to the screen as they arrive) while stdin is inherited (the terminal) and the prompt still
reaches the owner. The prompt-route check is about the identity of the tool's own prompt and connect functions in its process; capturing stdout does not touch
it. `PYTHONUNBUFFERED=1` makes the tools' output appear at once. `stdin` is a pipe only for the three cluster writes that feed a file (`tee`), never for a
prompt. Vite alone is started with stdin `/dev/null`: its dev server reads keystrokes from a terminal stdin (`q` quits it) and would race the runner's own
prompts. The launcher keeps the terminal (its prompts are `/dev/tty`) and reads nothing else.

Never on argv or in the environment. psql is run with `-X -v ON_ERROR_STOP=1 -v HISTFILE=/dev/null` and a script file of constants (the `\password` lines); the
one value passed with `-v` is a username. Every child gets the environment with each `PG*` variable removed, `PYTHONPATH=src`, `PSQL_HISTORY=/dev/null`.

Unverified by this build: that `sysadminctl -password -` reads the new user's password from the terminal rather than stdin (a sandbox could not run it). The
owner guide offers System Settings instead; the runner's only reaction to a failure there is a stop with the cause shown.

## 4. The stop latch

Rule 0.3 (create: only `422 REAL_REQUEST_INVALID` and `404` retry; PD-0083) and rule 0.4 (an installer refusal, any exit status the runbook does not cover,
a launcher that will not start, a publish whose hash differs from `P.json`, an unexpected probe exit, a refused `check`, an unexpected response under the
withdrawal) write `latch` into `~/finweb-r8/state.json` before the runner exits. While it is set, every run (except `--status` and `--close-window`) prints it
and exits 3. `--reset-stop PD-NNNN` lifts it only if: the owner's decision record is committed under `decisions/product/`; HEAD is a descendant of, and different
from, the HEAD at the stop (a reviewed fix is committed); the tree is clean; and the owner types `RESET R8 STOP`. The new HEAD becomes the new P8; the old P8,
the latch, and who lifted it stay in the state and in `R8_RECORD.md`. A recorded create outcome that stops R8 re-latches by itself if the latch is missing (an
interrupt between the two writes). Not latched: Phase 0 (the runbook says resolve and re-run), a dirty tree, a moved HEAD, and anything that refused before a
step started.

A create is never lost: the state marks `create_pending` from the moment a create is offered until an outcome is recorded; if a run quits or is interrupted
in between, the next run says so and asks whether Create was clicked, and if yes, asks for its outcome first.

## 4a. Mistyped passwords (PM decision 2026-11-15; refines section 4)

A mistyped password must not cost a committed fix. `exec_pw` retries the identical command, by the owner's answer to "Retry after a mistyped password? [y/N]",
at most 3 times per step; the next failure latches (`PASSWORD_RETRIES_EXHAUSTED`); answering no stops without a latch. Each failed attempt is recorded
(`failed attempt N at STEP`, with time and a label, nothing typed: the runner never sees it). The tree is re-checked before each retry. Recognised, and nothing else:
- **sudo:** exit 1 and "incorrect password attempt" (sudo's own text after "Sorry, try again" three times; nothing ran).
- **psql login:** exit 2 and "password authentication failed".
- **psql `\password` mismatch:** exit 3 (a failed command under `ON_ERROR_STOP`) and "Passwords didn't match." The whole session is re-run; `ALTER ROLE ... LOGIN` and
  `\password` are safe to repeat.
These texts and exit codes come from the programs' source and documentation; the runner could not run them here (no cluster, no terminal).
**The reviewed tools (PM decision, same day: the tools are not changed).** None prints the server's text, so the basis is not "the password was wrong" but "the
tool says its own connection failed and nothing was sent", which makes a retry harmless whatever the cause. `own_connection_failure` accepts exit status 2 and a
whole line (not a substring) of the tool's own text, read from each tool's source (the connect precedes any send; the line is printed only in that handler):
`REFUSED LOADER_CONNECT_FAILED PF_.. . Nothing was sent.` (loader: load, register-bound, reconcile), `REFUSED PROBE_CONNECT_FAILED ...` (probe),
`REFUSED LAUNCH_CONNECT_FAILED. Nothing was started ...` plus the PF code line (launcher, executor connect; not if "real-mode app:" appears),
`refused: RW_CONNECT_FAILED  (PF_.. X)` plus `nothing was recorded` (publish, withdraw, renew, status), and `REFUSED PF_CONNECT_FAILED (X): the
installer's own connection failed; nothing was changed by this step` for `real_install` phase0, phase2 and check only. The question says what happened
("The tool could not connect (CODE); nothing was sent. A mistyped password is the usual cause."). Same machinery: asked each time, 3 retries per step (count kept
in the state, cleared by a reset), then the latch (and, at a loader-window step, the window is closed first); each failed attempt recorded with its code; tree
re-checked before each retry.
**Review changes (TR8G-M-3, L-1).** Only `PF_CONNECT_FAILED` is retried: `PF_REQUIRE_AUTH` means the server did not complete SCRAM (a cluster configuration
refusal, not a typo) and latches. Two more cases are retried, each confirmed in the source: `identity_seed` (`apply_seed` is one transaction, `ON CONFLICT DO NOTHING`,
an equal row is left alone, so a re-run after any outcome changes nothing or completes the same rows; its line covers a statement failure too, so the question says
"failed and was rolled back", never "nothing was sent"), and the launcher's `LAUNCH_ACCOUNT_ROLE` followed by a line that is exactly `OperationalError` (printed
before anything is served; the account store's connect only reads `pg_roles` and sets session settings; `UNSAFE_DATABASE_ROLE` and any other code still latch; a
`require_auth` refusal at that second prompt prints the same words and cannot be told apart, a limit). `real_install` phase1 latches on any failure.

## 5. Other design points

- **State:** `~/finweb-r8/` is 0700; every file 0600 (state, transcript, scripts, `R8_RECORD.md`). Every file the tools write there (P, F, E, C) is theirs and
  is never overwritten. The state file itself is updated by write-and-rename (it must be); scripts are written exclusively and re-used only if identical.
  The runner writes nothing in the repository. The children may write ignored caches only (Python's `__pycache__` is suppressed with
  `PYTHONDONTWRITEBYTECODE=1`; Vite may write `web/node_modules/.vite`); `git status --porcelain` stays empty.
- **Events log (TR8G-L-2c):** `~/finweb-r8/events.log`, 0600, opened for append only. Every record, command, create (and every `redo`), latch, lift, done step and window
  reopen is appended before the state changes; `R8_RECORD.md` is built from it, not from `state.json`. A run refuses when the state's latch and the log disagree
  (log latched, state not: the latch is restored and the run exits 3; state latched, log not: exit 3), and when the log is missing.
- **Latch first (H-1):** `handle_stop` saves the latch before anything else, then closes the window; an interrupt or EOF in the close leaves the latch saved.
- **Window state (M-1, M-2):** `window.open` is set when the open step starts (conservatively: the LOGIN may be set even if the rest fails) and cleared only when a close
  confirms zero sessions. A stop or status shows it, with the exact `--close-window` command. A step that needs the loader LOGIN (`w*_check`, `w*_load`, `w*_register`)
  that finds the window closed goes back to `w*_open` (a fresh LOGIN and `\password`) first.
- **Decision records (M-4):** the publish, withdraw and renew records must each be a file ADDED by a commit in `first P8..HEAD` (`git log --diff-filter=A`), a different
  file each time; the reset record must be added after the HEAD recorded at the stop.
- **Withdrawn create (L-2a):** passes only as a 4xx refusal with `RW_WITHDRAWN`; anything else, a 2xx included, latches. A "no" at the qualification or the proposal
  is recorded and latches.
- **Vite (L-2d):** `web/node_modules/.bin/vite` directly; missing: refused before the launcher starts; never `npx`.
- **Steps:** each is a function plus a definition (gated: waits for Enter; password: re-checks the clean tree and HEAD; safe: may be re-run if its end was not
  recorded). An unsafe step whose end was not recorded is not re-run: `--resolve STEP retry|done` is the owner's statement.
- **Frozen values:** first run only; a different value later is refused (`FROZEN_CHANGED`). The PostgreSQL binaries are resolved once from `psql` and recorded
  as absolute paths (`initdb` and `pg_ctl` are taken from `psql`'s directory and not checked for existence).
- **Loader windows:** a definite answer closes the window in one psql session with `\watch i=1 c=30 min_rows=1` until zero rows remain (psql 17 or later, checked
  at the first run); an unknown answer leaves it open as the runbook says. `--close-window` closes it even through a latch.
- **Seams:** `Seams(run, spawn, ask, say, now, sleep, port_open, environ, which, realpath, stat, can_write, can_read, exists)`. Tests use only mocks.
- **Static guard:** the runner is not in `TOOLS` (it opens no connection, has no credential route, and must read the environment to strip it and start children,
  all of which the TOOLS rules forbid). It is in `ORCHESTRATORS` in `test_real_preflight_static.py`: held to its own rules (import list; a child only in named
  functions and never through a shell; the environment read in `real_seams` only; files created in four named functions; no credential switch string; no
  `getpass`, `terminal_prompt`, `connect_with_prompt`) AND pinned in full (`ORCHESTRATOR_PINS`), so any edit is a deliberate, reviewed pin change. No other module
  may name it.

## 6. Limits

- Not run against anything real. The tools' output formats are matched by regular expressions copied from their source (`published context ... at generation`,
  `done: generation ... names drain mark`, `renewed context ...`, `REFUSED RW_... purpose=`, `reconcile --candidate`); a change in those texts stops the run
  at that step with the output shown, not silently.
- A mistyped password may be retried at sudo, psql and the tools' own-connection failures (section 4a). It latches at `real_install` phase1, on `PF_REQUIRE_AUTH`, and
  at the launcher's account-role prompt unless the refusal is a bare `OperationalError`.
- The two statements in the record (the owner held the credentials; passwords only at prompts) are the owner's typed answers, not facts the runner can check.
- The "last loader session ended" time is the server's UTC time of the first count of zero, not the backend's own end time.
- A second terminal on the same account could still edit the repository between a check and a prompt; the tree is re-checked before every password step, not
  continuously.
- Closing the macOS user's session, `sudo` timeouts and Vite's behaviour on a closed port are not modelled.

## 7. The supplementary-run runner (PD-0087, PD-0088; plan `CP7_F1_R8_SUPPLEMENT_PLAN.md` revision 2)

`real_tools.r8_supplement` is a second, separate runner for the supplementary run on R8's live context. It is a `Guide` subclass: the same seams, state, append-only
events log, stop latch (`--reset-stop`), `--resolve`, `--status`, clean-tree and moved-HEAD rules, retry gate for mistyped passwords, and launcher and Vite handling.
`Guide` gained two behaviour-neutral class attributes, `DIR_NAME` and `SCHEMA`; the R8 runner's behaviour and tests are unchanged apart from check 10.1 (below).

- **Folder.** `~/finweb-r8-supplement/` (0700): `state.json`, `events.log`, `transcript.log`, `SUPPLEMENT_RECORD.md` (created once, `O_EXCL`). It reads `~/finweb-r8/state.json`,
  `events.log`, `P.json`, `F.json` and `C2.json` and writes nothing there. Its own base commit "S8" is the HEAD at its first run.
- **Preconditions (no password).** R8's state is finished (`close` done), unlatched, no loader window open, the published context is `c6b6f499...20402ee`, the renewed generation is 3,
  `C2.json` carries exactly that context at generation 3, and the cluster's socket exists (unless the run itself has stopped it).
- **Steps.** `start_1` (launcher on `C2.json`, two prompts, and Vite), `http_b`, `http_pre`, `stop_1`, `pg_stop`, `pg_start`, `start_2`, `http_post`, `screen`, `reeval_101`, `close`.
  `pg_stop` is `sudo -u <cluster user> <pg_ctl> -D <data> status`, `stop -m fast --wait`, `status` (3) and the socket gone; `pg_start` is the R8 runner's own start step and a new PID is
  required. The PIDs are recorded.
- **The tool.** `real_tools.r8_http_check` is started ONLY as a child (`fw(TOOL, ...)`), never imported. The runner reads the acknowledgement (the screen's sentence, once per phase
  that sends a create-route request, listing the requests), user B's username and the optional name, and passes them as options. The tool prints `S8 {json}` lines of safe fields; the
  runner records each line as a record.
- **Exit statuses of the tool and what the runner does.** 0 done. 3 retry gate (a mistyped sign-in counts, at most 3, and B's username is asked again; a rate limit waits and is not
  counted; a refused connection, `NO_CONNECT`, is a stop without a count or a latch: nothing was sent and the launcher did not answer). 5 a finding before any create-route request: a
  stop with a record, no latch. 7 an unusable command line or prompt route: a stop, no latch, nothing sent. Everything else (1, 2, 4, anything unknown): a LATCH.
- **Resuming (TR8S2 H-1, M-1, L-4).** Every step that signs in has `services="C2.json"`, so a rerun that resumes at `http_b` starts the launcher before the tool (it had none before). A
  stop that sent nothing (acknowledgement declined, exit 7, a declined retry, `NO_CONNECT`) clears the step's `started` mark, so the rerun starts it again without `--resolve`.
  `pg_stop` is resumable: once `pid_before` is recorded the socket is not required at the start, `pg_ctl status` decides (running: stop; down: continue), and a non-zero `pg_stop`
  exit says the state is UNKNOWN and asks for the same command again. It refuses while port 8004 or 5175 is open. `--resolve http_pre done` is refused (the digests exist only if the
  tool finished); `http_post` without them stops with `HTTP_PRE_DIGESTS_MISSING`, no latch.
- **Y and resume.** The runner saves Y's operation id in its state (and an event) before the run and marks `sent` before it starts the tool. A later run of `http_pre` (after
  `--resolve http_pre retry`) passes `--resume`, so Y already existing is expected and a replay 200 is not a stop. `http_pre` is marked unsafe: an interrupted run needs `--resolve`.
- **Step `reeval_101`.** It evaluates `attempts[-1]` (the attempt R8's own verdict used) of R8's recorded check 10.1 with the corrected comparator, labels it a re-evaluation, and
  writes only to the supplement's own log. R8's recorded FAIL and `R8_RECORD.md` are never rewritten.
- **Check 10.1 (R8 runner).** `QUANT_NUMBERS` no longer holds the close; `compare_nav(holding, nav, missed, state)`; `s_check_nav` does not ask the close and says why.
- **Guards.** `test_real_preflight_static` pins both runners' whole source, relaxes two rules for the supplement alone (it may import `real_tools.r8_guide`, and name `r8_guide`; the
  module object may be used only as `base.<Guide name>` or the few listed attributes, and `__import__` and `importlib` are banned, so it is not a side door to `subprocess` or `os`) and
  holds the tool to its own class (`HttpToolTests`: `http.client` to 127.0.0.1:8004 only, no urllib/proxy API and no connection attributes, one prompt route, the password only as a
  direct argument inside the login `json.dumps` passed straight to the send, one `print`, and taint tracking). The ten leak mutants and five runner mutants of TR8S2 and the nine of TR8S3 are
  in the tests and fail the rules, not only the pin.
- **What the taint rules do and do not enforce (TR8S3 N-L2).** They are INTRAPROCEDURAL. Within one function they follow a secret (password, cookie, token, header, raw or parsed body,
  the Set-Cookie list, the text of ANY caught exception except the tool's own `Retry`, `Finding` and `Unknown`) through assignments, comprehensions, and into a local container, to an
  `emit`, `print`, raised or retry argument. They also reject a secret stored in an attribute that is not itself a source (`ctx.note = ...`, a class attribute) and a secret put into a
  container that is not a local (a module-level list or dict). They do NOT follow a value that is returned and emitted by the caller, a `global` rebinding, or an object method that
  stores its argument. For the runner: the module object may be used only for the listed attributes, `real_seams` may be named only in `main` and never as the object of an attribute or
  call, and no dunder attribute (`__globals__`, `__class__`, ...) is read. The whole-source pin is the backstop for everything these rules do not see: any edit to either file changes it
  and needs a reviewed, deliberate re-pin.
- **Not run for real.** Neither the tool nor the runner has talked to a launcher, sudo or `pg_ctl`; the tests use a fake launcher and the R8 runner's mocked world.
