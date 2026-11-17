# CP7 F1 R8 supplementary run: plan (PD-0087 items 1 and 2; amended for TR8S and PD-0088)

Status: PLAN ONLY, revision 2. Nothing is built. Author: engineer, 2026-11-16. Inputs: PD-0087, PD-0088, `reviews/gates/HG4_GATE_REVIEW.md` (6, 8.1, 8.2, 11,
13), TR8R, TR8S, design `CP7_F1_REAL_PATH_DESIGN.md:2807-2874`, runbook G/0/9/10, the code cited. `~/finweb-r8/` was read, not written. Nothing touched the cluster.
The base commit "S8" must contain the screen fixes, including the list's `operation_id` (`service.py` `_entry_body`, read from `rw_revision`; the client's Open uses it).

## 1. Findings from the code (unchanged facts, shortened)

1. The idempotency key is the create body's `operation_id`, minted per submit by the browser (`web/src/real-mode.ts` `newOperationId`, `createBody`; `RealModeApp.tsx`
   `submit`). The root id is `root_id_for(owner, operation_id)` (`service.py:82`). The command digest covers owner, root, operation, context and the whole intent
   (`service.py:87-90`), not the generation, so every field must repeat byte for byte.
2. Server: same id and command: `REPLAY`, read-only, **HTTP 200** with `replayed: true`, otherwise the same body as the 201 (`real_workspace_v1.sql:380-388`,
   `service.py:217-220`, `real_mode_routes.py:218`). Same id, other command: `RW_IDEMPOTENCY_CONFLICT` before any insert (`:383-385`), 409, kind `CONFLICT`. It is
   observable only while the context admits `EXECUTE_CREATE` (true at generation 3).
3. The screen cannot send either: Create always mints a new id; the repeat button appears only after an unknown outcome; no body is kept after a 201.
4. R8's first create cannot be replayed from the record: its id is known, its body (the free-text name) is not. So the plan creates **Y** (new id, rule 0.3,
   approved by the owner in PD-0088) and replays it. Step 6 is a single attempt at R8's own id.
5. **"Error digest"** is defined nowhere but the phrase. Reading (PM-confirmed): the refused response equals, byte for byte, the contract's body for that code:
   `canonical_json(refusal_payload(ContractRefusal(code)))` (`real_scoped_contract.py:349-356`, `app.py:29-31`). A bare string, `refusal_payload("RW_X")`, returns the
   `REAL_UNAVAILABLE` body (TR8S M-1) and is never used. The record holds the **full body text and its SHA-256**. Auth-layer refusals use `app.refused` (another schema,
   `account_routes.py`); they are never compared to a contract body.
6. **Expected count of A's roots before Y: 2.** R8 recorded two creates (`create_a` 201, `create_c2` 201); the one create under the withdrawal was refused, and the
   gateway raises `RW_WITHDRAWN` at `real_workspace_v1.sql:368`, before the only root insert (`:393`), so the unrecorded first click wrote nothing. A count of 3 would
   mean it did.
7. Restart: `r8_guide` is finished and fully pinned; the launcher asks two passwords on every start and runs the REAL preflight (re-passed after the restart).

## 2. How a replay and a conflict are sent: the tool (option A)

Not the screen (no path; a test control does not belong in the product screen), not a browser-console snippet (hand-copied, no comparison, no record).

**`src/real_tools/r8_http_check.py`**, a child process of the runner:
- **Transport (TR8S H-1).** `http.client.HTTPConnection("127.0.0.1", 8004)` only. The port is a constant equal to `real_launcher.DEFAULT_PORT`, not an option; no
  redirect is followed; no proxy API exists. Cookies are parsed by hand for the two names `finweb_real_session` and `finweb_real_csrf` and sent in a `Cookie` header;
  the CSRF token comes from the JSON body of the session/login answer and goes in `X-Finweb-CSRF`; `Origin: http://127.0.0.1:5175`.
- **Secrets (M-4a).** The password comes only from `real_preflight.terminal_prompt`, after `prompt_route.require_genuine`, with a label that names the web account
  (L-2): `web account <username> (screen sign-in, not a database role)`. The tool never prints, logs, formats or writes the password, the cookie values, the
  CSRF token, any response header, or any raw auth body. Its stdout carries only safe fields: label, status, code, kind, ids, digests, counts, and the full text of
  a contract refusal body (fixed text, no secret).
- **Inputs it does not read itself (M-4b).** The tool calls no `input()` and reads nothing but the prompt. The runner reads, with its own `typed`, the
  acknowledgement, B's username and step 6's name, and passes them as options (`--acknowledged`, `--user-b`, `--replay-name`; none is secret).
- **Logout** is in a `finally`, so a stop also ends the server-side session.
- **Exit codes.** 0 all as expected. 3 retryable, nothing economic sent: connection refused; login 401 `INVALID_CREDENTIALS` or 422 `INVALID_REQUEST` (a short password),
  both counted as a mistyped password (G.4: 3 retries, then a latch); 429 `AUTH_RATE_LIMITED`: wait, not counted (L-1). 5 a finding before any create: stop with a record,
  **no latch**. 2 an unexpected answer after a create-route request was sent. 4 unknown after a send. Anything else, including an uncaught exit 1: the runner **latches**.
  The login POST writes `web_session` and `web_auth_rate` rows (account rows, no economic data).
- A coded refusal of a list, read or reproduce (503 `REAL_UNAVAILABLE`, 409, a list entry with `status`), or reproduce `RESULT_DIFFERS`/`INPUT_MISMATCH`/`SOURCE_REFUSED`,
  is exit 5 before a create and exit 2 after: never retried as a typo (M-3b, c).

**Runner `src/real_tools/r8_supplement.py`:** a `Guide` subclass (own state, events and record in `~/finweb-r8-supplement/`, 0700; same seams, latch, `--reset-stop`,
`--resolve`, `--status`, clean-tree and moved-HEAD rules; S8 = HEAD at first run). It starts the tool **only** as a child, `fw("real_tools.r8_http_check", ...)`; it
never imports it (M-4c). Subclassing is kept, because the alternative is a copy of 1,800 lines; it needs two reviewed relaxations of existing guards (M-4d), stated in
section 6. It reads `~/finweb-r8/state.json`, `P.json`, `F.json`, `C2.json` read-only.

## 3. The run, in order

Checked without a password first: R8 state has `close` done, no latch, no open window; context `c6b6f499...20402ee`; `C2.json` generation 3; the socket exists. Command:
`PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_supplement` (run again to resume). The runner asks the acknowledgement at each tool phase that
sends a create-route request, **listing those requests** (L-4), and the owner types `yes`; the tool never defaults it.

| # | Step | Action | Recorded | Expected | Closes |
|---|---|---|---|---|---|
| 1 | `start_1` | launcher on `C2.json` (two prompts), Vite | preflight lines | ready | |
| 2 | `http_b` | tool `--phase b`, **before any create** (M-2). B's username typed at the runner, B's password at the tool's prompt. B lists; B reads A's first root (id from the runner state), reproduces it, reads an unknown id and a malformed id (no `/`) | status, code, body text and SHA-256 of each; B's list | B's list has none of A's roots; **four** answers 404 `RW_NOT_FOUND`, identical bytes, equal to the contract body | B's 404 (10.5, L-6); error digest |
| 3 | `http_pre` | tool `--phase pre`, A's password. A lists. **If the count is not 2 (or 3 with Y already in the list, resume): stop, exit 5, nothing created.** Reads A's first root through the list's `operation_id` (cross-checked against `a454d861`); then **creates Y** (new id saved by the runner first; name `R8 supplement`; as-of, quantity, cash, ids as R8's); **replays Y**; lists | each request: label, status, code, `replayed`, ids, digests, count | n0 = 2 (M-5); create 201; replay 200, `replayed: true`, equal to the 201 body in every field but `replayed`; count 3 before and after the replay | T08 on a new real commit; TR8R M-5 count |
| 4 | (same) | **conflict:** Y's id, other name and quantity | status, code, body text, SHA-256, count | 409 `RW_IDEMPOTENCY_CONFLICT` equal to the contract body; count 3; Y reads as before | idempotency conflict; error digest |
| 5 | (same) | **error digests:** (a) quantity `0`, fresh id; (b) an unserved well-formed context, fresh id | as above | (a) 422 `REAL_REQUEST_INVALID`; (b) 404 `RW_NOT_FOUND`; contract bodies; count 3 | error digest (before any database use) |
| 6 | (same, optional) | **one attempt** at R8's own id with the name the owner remembers (typed at the runner) | status, code | 200 `replayed: true` with the first read's digests, or 409 (the name differs): nothing is recorded either way. **A 201 latches** | T08 on R8's own commit, if it matches |
| 7 | `stop_1` | stop Vite and the launcher | | | |
| 8 | `pg_stop` | `sudo -u finwebpg <pg_ctl> -D <data> status`, `stop -m fast -w`, `status`; socket gone | PID before; exits | 0, 0, 3 | clean restart |
| 9 | `pg_start` | `... -l <log>/server.log start`, wait for the socket, `status` | PID after | PID differs | clean restart |
| 10 | `start_2` | launcher (two prompts; preflight again), Vite | preflight lines | ready; a refusal latches (rule 0.4) | restart |
| 11 | `http_post` | tool `--phase post`, A's password. List (3 roots); read the first root (digests equal step 3's); **reproduce** it; read Y (equal); **replay Y** (200); **conflict on Y** (409); counts unchanged | as step 3 | as stated | restart: read, reproduce, list; idempotency record survives |
| 12 | `screen` | owner at `http://127.0.0.1:5175/real.html`, as A: Open from the list (DR-R8-1), reproduce `REPRODUCED`, the password hint (DR-R8-3), sign-out clears typed values (DR-R8-4). **Optional, one minute:** read R8's first root again and type holding, NAV, missed sessions, state; the runner runs them through the corrected comparator (a fresh observation, labelled as such) | typed verdicts | pass | browser after restart; DR-R8 fixes |
| 13 | `reeval_101` | no typing. Re-evaluate the last attempt (`attempts[-1]`, the one R8's verdict used) of R8's check 10.1 with the corrected comparator | result | PASS. Labelled "re-evaluation of R8's typed values under corrected check 10.1, not a new observation". **R8's own 10.1 FAIL and `R8_RECORD.md` are never rewritten** | PD-0087 item 2 |
| 14 | `close` | stop services; write `~/finweb-r8-supplement/SUPPLEMENT_RECORD.md` (`O_EXCL`) | | | |

**Resume (M-2).** The runner saves Y's id before step 3. A rerun of phase `pre` is passed `--resume`: the tool lists (Y present, count 3), records "Y already created", sends
the identical Y command expecting **200 `replayed: true`** (201 is accepted if the earlier run died before sending, and said so), and compares with the first read. A rerun does not
latch on the expected 200. B's phase is separate, so a mistyped B password retries only B. Phase `post` is read/replay only and is safely repeatable.

**Not collected (PD-0088 item 2):** the read and reproduce refusal codes under a withdrawal. No withdraw or renew in this run.

## 4. Stop rules

- **Rule 0.3 for every create-route request** (Y, its replays, the conflicts, the two error requests, step 6). The tool holds one expected (status, code) per label. **Expected
  refusals, written next to rule 0.3 in the runbook text (the PM writes it; TR8R L-4 precedent):** 409 `RW_IDEMPOTENCY_CONFLICT` for the conflict requests only; 422
  `REAL_REQUEST_INVALID` and 404 `RW_NOT_FOUND` for the two error requests only; 200 `replayed: true` for replays. Anything else (another code, 5xx, 503, UNKNOWN, a 201 where none
  is expected, a body that is not the contract body for its code, a count that changed after a refusal): **latch**.
- **A's count before Y is not 2:** stop with a record, no latch, Y not created (the PM takes it as a rule-0.3 finding about R8).
- A coded refusal of list/read/reproduce, `RESULT_DIFFERS` and the other reproduce statuses, any digest difference (replay or post-restart against the first read; B's four bodies
  not identical): finding. Before a create: exit 5, record, no latch. After one: latch. No second attempt.
- Not stops: connection refused and login typos (retry gate, 3, G.4), 429 (wait).
- Any exit other than 0, 3, 5 latches. `pg_ctl` failing, or the socket not returning: stop without latch; the cluster stays as it is. Launcher refusal after the restart: latch.
- Dirty tree or HEAD moved beyond decision records: refused before every password step.

## 5. Check 10.1 (PD-0087 item 2)

- Runner: `QUANT_NUMBERS` loses `close`; `compare_nav(holding, nav, missed, state)` returns four booleans; `s_check_nav` stops asking for the close and says why (the screen shows `10 x p`
  and no price, ruling §8 item 4, DR-R8-2; the client never derives p). Tests change with it (`test_r8_guide.py:837-855`). The comparator change cannot rewrite R8's record.
- Runbook 10.1 (PM): "holding value, NAV, missed sessions and state, compared numerically with ruling `CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` §9.1 (Key-figure values). The screen does
  not show the close, by design (ruling §8 item 4); it is not compared. A stored price row is a separate product decision (DR-R8-2)." Plus a G.7 "Supplementary run" pointer to this plan.

## 6. What I propose to build, tests, guards

| File | Change |
|---|---|
| `src/real_tools/r8_http_check.py` (new) | the tool; options `--phase b\|pre\|post`, `--resume`, `--operation-id`, `--context`, `--release`, `--listing`, `--root`, `--root-operation`, `--user-a`, `--user-b`, `--acknowledged`, `--replay-name`; seam `send(method, path, body)` |
| `src/real_tools/r8_supplement.py` (new) | the runner |
| `src/real_tools/r8_guide.py` | behaviour-neutral class attributes for directory and file names; check 10.1 (section 5) |
| `tests/product/test_r8_http_check.py`, `test_r8_supplement.py` (new), `test_r8_guide.py`, `test_real_preflight_static.py` | below |
| `implementation/CP7_F1_R8_GUIDED_RUNNER.md` | a short section |

**Tests (no connection, no network):**
- Tool with a fake `send`: create then replay equal; conflict; 422; 404; B's four identical 404s; every unexpected response (wrong code, 500, 503, non-JSON, changed digest, changed count,
  `RESULT_DIFFERS`) gives exit 2, 4 or 5 and **no further request**; n0 ≠ 2 sends no create; resume expects 200 and does not fail on it; login 401/422 give exit 3 and 429 does not count; logout runs
  after a stop (`finally`).
- Secrets: the fake `send` returns **sentinel** cookie, CSRF token and headers, and the test searches the whole stdout for the sentinel password, cookie, token and header values.
- Expected bodies are built by `canonical_json(refusal_payload(ContractRefusal(code)))`; a test asserts each expected body's `error.code` equals its label's code, so the `REAL_UNAVAILABLE` trap cannot pass.
- The acknowledgement sentence equals the TS string in `web/src/real-mode-i18n.ts` (read as text). One in-process test against the real-mode app and its kit for the cookie and CSRF handshake, if the kit
  runs without PostgreSQL; otherwise PG-gated, in the PG leg. The tool's `http.client` path against the live launcher is first exercised live; its first requests are read-only.
- Runner, fake seams: order; state, resume, `--resolve`; each latch of section 4; nothing is written under `~/finweb-r8/`; refuses an unfinished or latched R8 state; `pg_ctl` via
  `sudo -u finwebpg` with the frozen path; the PID comparison; it starts the tool only through `fw(...)`; step 13 uses `attempts[-1]`, gives PASS on R8's values and FAIL on a mutated NAV, and writes nothing to R8's files.

**Static guard (`test_real_preflight_static.py`), each a reviewed change:**
- New `HTTP_TOOLS` class for `r8_http_check.py` (in `DiscoveryTests`, `PARSERS`, `ALLOWED_OPTIONS`; not a `TOOLS` entry, whose rule limits a password to a connection string). Rules: imports only
  `argparse`, `json`, `hashlib`, `http.client`, `sys` and the reviewed project modules; **bans `urllib`, `requests`, `httpx`, `urlopen`, `build_opener`, `ProxyHandler`, `set_tunnel`,
  `http.cookiejar`, `socket`, `subprocess`, `os`, `input`**; the only host literal is `127.0.0.1`, the port a constant; no file or environment access; the only credential route is
  `terminal_prompt` after `require_genuine`; **taint tracking** of the password, the login body, the cookie, the CSRF token, `getheader(s)`, `.msg` and raw auth bodies: none reaches `print`, a
  logger, `format`, an f-string that is printed, or an exception message; full-source pin. Mutants: a `urlopen` of the loopback URL; a second host; `print(resp.getheaders())`; a printed cookie;
  an `input()`; a different prompt; a file write.
- `ORCHESTRATORS` gains `r8 supplement` and its pin; the `r8_guide.py` pin is recomputed. **Two existing rules are relaxed on purpose, with the subclass as the only allowed case:**
  `test_nothing_else_imports_or_names_the_runner` (`:1436-1440`) and `ORCHESTRATOR_IMPORTS` excluding `real_tools` (`:1358`). Reason: the supplement reuses the runner's state, latch, retry and services
  code by subclassing instead of copying it. A new rule forbids any import of `r8_http_check` by anything.

**Sequence:** this plan is reviewed (done, TR8S); build; the built tool and runner get their own review; the PM writes the runbook text and commits S8 (with the screen fixes); the owner runs.

## 7. What stays unverifiable

- Replay, conflict and B's 404 go from the tool directly to the launcher, not through Vite and not clicked on the screen; labelled so in the record and the package.
- T06 (same transaction) is not observable from outside; collected in part.
- The restart is a clean postmaster stop and start, not a crash (no WAL recovery) and not a host reboot. The UNKNOWN-then-repeat path cannot be forced and is not exercised.
- The first click under the withdrawal (M-5 of TR8R): no server trace; only the count (step 3) says whether anything was written.
- 10.3 (no-NAV notice), D-1, D-2, DR-R8-2 and the withdrawal-time read/reproduce codes stay as decided.
- The tool's live handshake is first used live (the sandbox cannot open sockets).

## 8. Time for the owner

About 40 to 50 minutes: sudo twice; the launcher's two prompts twice; A's password twice; B's once; about 10 minutes for the screen check.

## 9. Left for the owner or PM

- **PD for the residual limits (TR8S M-5/D9):** T06 in part; clean restart only; tool not browser; UNKNOWN path not exercised. PD-0088 item 5 defers these to the gate.
- **Runbook text (PM):** the expected refusals next to rule 0.3; 10.1; G.7. The package must show the owner the "exact stored result replayed, HTTP 200" wording and its code basis (TR8S D3).
- **The built tool and runner get their own review** (PM D7, TR8S).
- **S8 must be committed with the screen fixes** before the owner runs.
