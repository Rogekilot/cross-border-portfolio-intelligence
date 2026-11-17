# HG4 — real-data usability validation (F1, one real context)

**Decided 2026-11-17: APPROVED WITH CONDITIONS (PD-0089; section 14).**

**Revision 2, 2026-11-17, main session (PM). Resubmitted for the owner's decision.** The first submission (2026-11-16) was
decided REVISION REQUIRED (PD-0087). This revision adds the supplementary run and its review, the screen fixes, the check 10.1
correction and the first attempt's ratification (PD-0088). Revision 1 is in git history at `172e5dc`. Nothing in this package is a
decision. The new decision block, section 14, is blank.

**In one paragraph.** The owner ran R8, the first real-data run, on 2026-11-16. The real create committed with `synthetic = false`.
The stored holding and NAV equal the Quant's independent figures. Isolation held, and so did revocation and renewal. The R8
review failed on evidence: four required observations were never collected. On 2026-11-17 the owner ran the supplementary run on
the same database and context. It collected:
- replay and idempotency;
- the conflict case;
- the full bodies of refused requests;
- a real PostgreSQL restart with the app around it;
- user B's 404, byte for byte;
- the screen fixes, seen after the restart.

Every answer was the expected one, and the independent review TR8SR returns **PASS WITH FINDINGS**. What remains is a set of
named limits for the owner to accept or reject (section 11), plus one new screen-label finding (8.3). The PM recommends
**APPROVED WITH CONDITIONS** (section 13).

## 1. Gate name and authority

HG4, real-data usability validation (PRD §38.4). PD-0013 moved prototype UX approval into HG1, so HG4 is about real data. HG1's
approval (PD-0017) is not HG4's. The target is the F1 slice:
- one real context: AAPL on XNAS, as of 2026-09-30, US only;
- a project-constructed, non-personal ledger: quantity 10, cash 500 USD;
- create, read, reproduce and list, in a separate real database.

Source: `implementation/CP7_F1_REAL_PATH_DESIGN.md`, sections 0 and 7.

## 2. Objective

To show, on admitted real source data and on the product's own path, that:
- the deterministic engine values a real holding;
- the screen states it with its state, caveats and claim limits in English and Chinese at three depths;
- the result is reproducible and isolated per user;
- the owner's rights over the published context can be revoked and restored.

The gate also has to record the limits the design says the package must carry (section 8.4).

## 3. Required deliverables

From the design's 7.1 R8 row, its "R8 first-run observations, by E9 item" list, and the paragraphs after it (design :2787–2874),
plus the revision PD-0087 set:

1. The real install (Phase 0, 1, 2) under the install rule, with the owner holding the passwords.
2. The real qualification, the proposal review, and the owner's publish, with its expiry evidence and `valid_until` 2027-09-01.
3. The loader's two windows, opened and closed by the owner.
4. The real run:
   - `synthetic = false` and the F8B dry run (O1, O4);
   - a real valuation, with NAV compared independently against the Quant's oracle;
   - same-transaction persistence (T06);
   - exact replay, idempotency and archive read (T08);
   - reproduce, and the list with its stored labels;
   - the 7.4 wording from the real lineage;
   - behaviour after a physical restart;
   - independent technical and design review.
5. E9's other post-run items on the real context:
   - the error digest on a refused request;
   - negative cases refused before any write: an idempotency conflict, a foreign owner's root returning 404, and two-user
     isolation;
   - revocation (withdraw, then renew).
6. The package statements the design and PDs require (listed in 8.4).
7. **Revision (PD-0087 consequence 2):**
   - the supplementary run;
   - check 10.1 corrected;
   - DR-R8-1, -3 and -4 fixed;
   - a decision record on the first attempt's stop.

## 4. Actual deliverables

| Item | Where |
|---|---|
| R8's record, built by the runner from its append-only event log (no passwords) | `~/finweb-r8/R8_RECORD.md`, `~/finweb-r8/events.log` (owner's machine, mode 0600, not in git) |
| The first attempt, which stopped at Phase 0 (9.2) | `~/finweb-r8-attempt1/` |
| Proposal, seed, evidence and contexts files | `~/finweb-r8/P.json`, `F.json`, `E.json`, `E2.json`, `C.json`, `C1.json`, `C2.json` |
| **The supplementary run's record** (no passwords) | `~/finweb-r8-supplement/SUPPLEMENT_RECORD.md`, `events.log`, `state.json`, `transcript.log` (mode 0600, not in git) |
| Decision records made during R8 | [PD-0084 publish](../../decisions/product/PD-0084-r8-publish.md) (`eca287a`), [PD-0085 withdraw](../../decisions/product/PD-0085-r8-withdraw.md) (`b480fe1`), [PD-0086 renew](../../decisions/product/PD-0086-r8-renew.md) (`8cf051d`) |
| The first decision, and the revision's scope | [PD-0087](../../decisions/product/PD-0087-hg4-revision-required.md), [PD-0088](../../decisions/product/PD-0088-hg4-revision-scope-and-first-stop.md) |
| The revision's code: the loopback check tool, its runner, the screen fixes, the runbook G.7 and the corrected 10.1 | commit S8 `172e5dc` (`src/real_tools/r8_http_check.py`, `src/real_tools/r8_supplement.py`, `web/src/real-mode-session.ts` and others, [reviews/R8_RUNBOOK.md](../R8_RUNBOOK.md)); plan [CP7_F1_R8_SUPPLEMENT_PLAN.md](../../implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md) |
| Technical reviews, in [reviews/TECH_REVIEW.md](../TECH_REVIEW.md) | R8 evidence: TR8R **FAIL**. Revision: plan TR8S; build TR8S2 FAIL, then TR8S3, then TR8S4 **PASS**; screen TR8F, TR8F2, then TR8F3 **PASS**. **Supplement evidence: TR8SR, PASS WITH FINDINGS** |
| Design review of the real screen | [reviews/DESIGN_REVIEW.md](../DESIGN_REVIEW.md), "DR-R8 — real screen at R8 (2026-11-16)": **PASS WITH FINDINGS** |
| The owner's screenshots of the real screen (nine from R8, plus the list and key figures seen in this chat on 2026-11-17) | shared notes folder `…/side-session-notes/local_b1e823ca-…/r8-screens/` (they show the owner's browser bar, so they are kept out of git) |

R8 ran from P8 `32cd976`. The supplement ran from S8 `172e5dc` with a clean tree. The runner checked the tree and HEAD before
every password step.

## 5. Runnable demo and sample outputs

The real database and its stored results remain on the owner's machine:
- the cluster: `/Users/Shared/finweb-r8-pg`, port 5433, run as the macOS user `finwebpg`;
- the database: `finweb_real`;
- the context: `c6b6f499fb1b6dd35278e15bf12b096d75cd17d7e75c05489806edcda20402ee`, now at generation 3, live, `valid_until`
  2027-08-31T16:00:00Z;
- user A's three roots, as the list showed them on 2026-11-17:

  | Root | Created (UTC) | What it is |
  |---|---|---|
  | `a51651b9-26b9-520e-a0db-46f912743153` (operation `a454d861-…`) | 2026-11-16 11:52:23 | R8's first create, under generation 1 |
  | `aa08d874-4504-5e46-b925-e93e030afd74` | 2026-11-16 12:23:26 | R8's create after the renew, under generation 3. It was unrecorded at R8 and is read here from the owner's list screenshot. |
  | `36bf2846-8b29-5f97-a53a-f98414b105a4` (operation `841b0428-…`) | 2026-11-16 17:59:34 | Y, the supplement's create, under generation 3 |

The real screen, as the owner saw it (R8 screenshots 3 and 5, and again on 2026-11-17):
- **Key figures:**
  - Portfolio value (NAV), reporting view: `<NAV>` USD, state `AVAILABLE`;
  - holding value: `<holding>` USD, `AVAILABLE`;
  - cash: `500` USD, `AVAILABLE`;
  - dividend receivable: "Not in this result. That is not a stated zero."
- **May say, item 1:** "On 2026-09-30 the holding is worth 10 x p, where p is the close from Alpha Vantage free tier (US daily
  history) for the 2026-09-30 XNAS session (TIME_SERIES_DAILY); 0 sessions of that exchange lie after it…"
- **May say, item 3:** "NAV in USD on 2026-09-30: 10 x p + 500. State AVAILABLE, freshness CURRENT, delay END_OF_DAY,
  reconciliation SINGLE_SOURCE."
- **Does not claim:** seven items, matching design 7.4 C1–C7.
- **Since S8:** "Open" in the list opens the stored result; there are password and username hints; sign-out clears typed values.

To see it again, the owner restarts the launcher and Vite on `C2.json` (runbook 9.2–9.3), signs in as user A, and clicks
**Open** on any listed root.

## 6. Tests performed and results

### 6.1 R8 (2026-11-16; from `R8_RECORD.md`; times Asia/Shanghai)

| Step | Result |
|---|---|
| Cluster set up as `finwebpg` (Standard user, uid 502); data dir 0700; the owner's account cannot write it | recorded |
| Phase 0 / Phase 1 (`--loader-login nologin`) / passwords / Phase 2 | exit 0 / 0 / 0 / 0 |
| Qualification: three members, O5 passes; payload and manifest hashes equal PD-0066's table | owner approved 19:38:07 |
| Window 1: LOGIN 11:38:19Z, check 0, load 0, last loader session ended 11:38:53Z, NOLOGIN, 0 rows | closed |
| Proposal review | owner approved 19:42:29 |
| Publish (PD-0084): context `c6b6f499…`, generation **1**, `valid_until` 2027-08-31T16:00:00Z | exit 0 |
| Window 2: LOGIN 11:44:42Z, check 0, `register-bound` 0, last session ended 11:45:08Z, NOLOGIN, 0 rows | closed |
| First create (user A) | **201**, no code (Network: 93 ms) |
| 10.1 NAV against ruling §9.1 | **FAIL as recorded**: close "not shown"; holding <holding>, NAV <NAV>, missed sessions 0 and state AVAILABLE all equal (see 6.2) |
| 10.2 key-figures list | PASS (owner's note: values run into the label) |
| 10.3 no-NAV notice prominence | recorded PASS, but **not observable** with a NAV stored (TR8R M-2) |
| 10.4 claim wording, EN and ZH at three depths; origin label | PASS (owner's attestation) |
| 10.5 two-user isolation: user B sees no roots; B reading A's root by id is refused | PASS / PASS (code collected in 6.2) |
| 10.6 list and reproduce A's root | PASS / PASS (`REPRODUCED`) |
| Probe control at generation 1 (direct gateway admission, not a product route) | admitted, exit 0 |
| Withdraw (PD-0085), after one mistyped-password retry | generation **2** |
| Create under the withdrawal | **409 `RW_WITHDRAWN`** (expected refusal) |
| Read and reproduce under the withdrawal; list shows "Not readable now: RW_WITHDRAWN" | PASS, as one combined result (codes not recorded: an accepted gap, PD-0088) |
| Export under the withdrawal, by direct gateway admission (probe), not a product route | refused `RW_WITHDRAWN`, exit 1 |
| Renew (PD-0086), after one mistyped-password retry; `valid_until` unchanged | generation **3** |
| After renew: read, reproduce, list | PASS, PASS, PASS |
| Second create (rights restored) | **201**, no code |
| Export probe at generation 3 | admitted, exit 0 |
| Owner's statements: held the executor's and loader's credentials, no agent session held any (PD-0077); typed every password only at a reviewed tool's prompt, psql, initdb or sudo | **yes**, **yes** |

There were no stops in R8. There was one stop in the first attempt (9.2).

### 6.2 The supplementary run (2026-11-17; from `SUPPLEMENT_RECORD.md`; times Asia/Shanghai)

The loopback tool signs in as a web user, sends HTTP requests to the real-mode API at 127.0.0.1:8004, and compares each answer
with the expected one. Refusals are compared byte for byte with the contract's canonical refusal body. It holds the session
cookie in memory only and signs out at the end.

| Step | Result |
|---|---|
| S8 frozen: `172e5dc` | 01:58:03 |
| Launcher and screen on `C2.json` | served after one retry (`LAUNCH_ACCOUNT_ROLE`, a mistyped password is the usual cause; not a latch) |
| **User B** (`user_b`), before any create | sign-in 200; list **0**; A's root by id, reproducing it, an unknown id and a malformed id: **404 `RW_NOT_FOUND`**, all four byte-identical (`cd867728…`) |
| **User A**: list before | **2** roots. So the click under the withdrawal at R8 wrote nothing (closes TR8R M-5) |
| Read R8's first root | 200; response `55fb359b…`, issued `707dfb36…` (the digests R8's screen showed) |
| **Create Y** (`R8 supplement`, quantity 10, cash 500, as of 2026-09-30) | **201**, `replayed: false`, root `36bf2846…`, response `eb33c68f…` |
| **Replay Y** (the identical command) | **200, `replayed: true`**; body equal to the create's and to the read's |
| List after the replay | **3** |
| **Conflict**: Y's operation id with another name and quantity | **409 `RW_IDEMPOTENCY_CONFLICT`** (`277799f8…`); list still 3; Y reads back unchanged |
| **Refused request**: quantity 0 | **422 `REAL_REQUEST_INVALID`** (`bd9c5656…`); full body recorded |
| **Refused request**: a context the launcher does not serve | **404 `RW_NOT_FOUND`** (`cd867728…`); list still 3 |
| Optional attempt at R8's own operation id | skipped by the owner |
| Launcher and Vite stopped | 01:59:35 |
| **PostgreSQL stopped** (`sudo -u finwebpg pg_ctl stop -m fast --wait`) | status 0 with PID 19292; stop exit 0; status exit 3; socket gone (03:19:10) |
| **PostgreSQL started** | start exit 0; status 0; new PID **39971** (03:19:11) |
| Launcher and screen started again | served after one retry (`PF_CONNECT_FAILED`; not a latch) |
| **User A after the restart** | list **3**; R8's first root reads with the **same** digests; reproduce **`REPRODUCED`** with the same issued digest; Y reads the same; Y's replay **200 `replayed: true`**, equal; conflict **409** again; list 3 |
| **Screen after the restart** (owner's answers) | the list shows A's roots and **Open shows the stored result** (DR-R8-1): PASS; Reproduce shows `REPRODUCED`: PASS; sign-up password hint (DR-R8-3): PASS; sign-out clears typed values (DR-R8-4): PASS |
| **Check 10.1 as corrected, a fresh reading after the restart** | holding <holding>, NAV <NAV>, missed sessions 0, state AVAILABLE: **PASS** |
| **Check 10.1 re-evaluation** of R8's own typed values under the corrected check | **PASS**. This is a re-evaluation, not a new observation; R8's recorded FAIL and `R8_RECORD.md` are unchanged |
| Close; surprises | record written 03:26:33; none stated |

There were no stops and no latch. Each launcher start needed one password retry. sudo refused one mistyped Mac password at
`pg_stop`.

### 6.3 Reviews

- **R8 evidence (TR8R): FAIL.** H-1, M-1 to M-5, L-1 to L-6. The reviewer recomputed every decision-record hash and evidence
  citation; all agree.
- **R8 screen (DR-R8): PASS WITH FINDINGS.** DR-R8-1 (HIGH), -2, -3, -4, -7 (MEDIUM), -5, -6, -8, -9 (LOW). No invariant is broken.
- **Revision build:**
  - plan TR8S: PASS WITH FINDINGS;
  - tool and runner: TR8S2 FAIL (H-1, M-1, M-2), TR8S3 PASS WITH FINDINGS, TR8S4 **PASS**;
  - screen fixes: TR8F, TR8F2 PASS WITH FINDINGS, TR8F3 **PASS**.
- **Supplement evidence (TR8SR): PASS WITH FINDINGS.** Every answer matches the plan. The record, events log, state and
  transcript agree with each other and with the code at S8. What the reviewer recomputed independently, with no database:
  - **The refusal bodies.** The 404, 409 and 422 bodies match the recorded hashes byte for byte.
  - **The root ids.** Both root ids derive from R8's recorded owner id and the operation ids.
  - **The digests.** They are equal before and after the restart.
  - **R8's files.** They are untouched.

  Findings: M-1, the list's generation label (8.3); L-1 to L-5, record gaps and wording (8.5).

### 6.4 Product test suites

At S8 (`172e5dc`, 2026-11-16, before the commit):
- full suite with PostgreSQL: `Ran 4504` / `OK (skipped=126)`;
- default: `Ran 4504` / `OK (skipped=920)`;
- web: `tsc` clean; vitest 318 passed;
- Playwright not run.

TR8SR re-ran the four directly relevant modules at S8 on 2026-11-17: 230 tests, OK. The supplement changed no code.

## 7. Proof of work and traceability

- **NAV oracle.** `methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` §9.1 ("Key-figure values") derives holding = 10 × p
  and NAV = holding + 500 from the price file's 2026-09-30 row, independently of the code. The runners compare numerically
  (`compare_nav`, Decimal). The stored holding and NAV equal it exactly, at R8 and after the restart. TR8R also confirmed that
  holding / 10 equals the price file's close. **That division is a check by the reviewer; the product never derives it.**
- **Decision records.**

  | Record | Commit (GIT40) | DOC64 |
  |---|---|---|
  | PD-0084 | `eca287ac9f55…` | `b1a407dd…` |
  | PD-0085 | `b480fe1a8764…` | `a4ffccd3…` |
  | PD-0086 | `8cf051da9212…` | `fe49c69e…` |

- **Evidence citations.** In both `E.json` and `E2.json`:
  - `alphavantage.us` `LEASE_TERM` cites PD-0066 (`10ce97b…`, `d8c6d6c1…`);
  - `openfigi` and `calendar.manual` `NOT_ASSESSED` cite PD-0068 (`7effcc8…`, `0428435a…`).
- **Inputs.** The context's three members, as the screen states them and as the owner checked against PD-0066:
  - QUOTE `066c65e6…b1b9d1fb`, manifest `268535dd…`;
  - IDENTITY `b2aaeb7b…889c3ccc` (`AAPL_UW.json`), manifest `7952829b…`;
  - CALENDAR `4f21b26b…3d5f72ef` (HG2-registered), manifest `b08c929a…`.

  Release `77ca2d32…`. Ledger version 2.
- **Stored digests.**
  - First root: response `55fb359b…`, issued `707dfb36…`. These are the same on R8's screen, in the supplement before the
    restart, and after it.
  - Y: response `eb33c68f…`, issued `489e6432…`. These are the same for the create, the read and the replay, before and after
    the restart.
- **Refusal bodies.** TR8SR rebuilt `canonical_json(refusal_payload(ContractRefusal(code)))` at S8:
  - `RW_NOT_FOUND` `cd867728…`;
  - `RW_IDEMPOTENCY_CONFLICT` `277799f8…`;
  - `REAL_REQUEST_INVALID` `bd9c5656…`.

  The tool emits an expected-refusal line only when the server's raw bytes equal that body (`r8_http_check.py:247-253`).
- **Where each refusal comes from** (TR8SR, from `real_mode_routes.py`):
  - the routes refuse the 404s and the 422 before any gateway call;
  - only the 409 conflict is a gateway refusal.

## 8. Known limitations and incomplete items

### 8.1 Check 10.1: corrected; R8's FAIL stays on record

The screen shows p symbolically ("10 x p"), as ruled (ruling §8 item 4), and the key-figures list has no price row. The engine stores
no price, only its date. So R8's check 10.1 asked for a figure the design deliberately does not show. That was a check-design
defect.

The check is now corrected to compare holding, NAV, missed sessions and state (runbook 10.1, PD-0087 consequence 2.2). Both the
re-evaluation of R8's typed values and the fresh reading after the restart pass.

R8's recorded FAIL is unchanged. The fresh reading cannot be tied to a root id: none was recorded, and Y has the same inputs, so it
shows the same figures (TR8SR L-5). The owner was directed to the first root, `a51651b9…`.

Whether a stored price row should be shown (DR-R8-2) is still the owner's open question. The client must never compute it (P1).

### 8.2 The design's R8 first-run observations: what is now collected, and what remains

| Observation | Status after the supplement |
|---|---|
| Exact replay and idempotency (T08) | **Collected, on Y.** The replay is 200 with `replayed: true` and the stored result, byte-equal to the create's 201 body. The design's "exact-201" means this: the replay returns the stored result with HTTP 200 (TR8S D3). It was not done on R8's own first create; the optional attempt was skipped. It was sent by the tool, not the browser. |
| Idempotency-conflict negative case | **Collected.** 409 with the contract body, before and after the restart; nothing written. |
| Error digest on a refused request | **Collected.** The full bodies and their SHA-256 for 404, 409 and 422. The 404s and the 422 are route refusals; only the 409 reaches the gateway. |
| Behaviour after a physical restart | **Collected as a clean restart.** PostgreSQL was stopped with `-m fast` and started again (new PID), and the launcher and Vite were restarted. Read, reproduce, replay, conflict and the screen all behaved as before. It was **not** a crash or kill, not a host reboot, and not a restart during a create. The browser page was reloaded; the browser process was not restarted. |
| Foreign root 404 for user B | **Collected,** through the tool: four byte-identical 404s. |
| Same-transaction persistence (T06) | **In part.** The rows read back; "same transaction" was not observed. |
| UNKNOWN-then-repeat (a create whose outcome is unknown, then repeated) | **Not exercised.** |
| Read and reproduce refusal codes under the withdrawal | **Not collected: an accepted gap** (PD-0088 consequence 2). The withdrawal itself was collected: the screen showed it, create was refused with 409 `RW_WITHDRAWN`, and export was refused at the gateway. |
| The no-NAV notice's prominence (10.3) | **Not observable** with a NAV stored (TR8R M-2). |

### 8.3 Screen findings

- **Fixed and seen by the owner after the restart:**
  - DR-R8-1 (HIGH): Open from the list now shows the stored result;
  - DR-R8-3: the password and username rules are shown;
  - DR-R8-4: sign-out clears typed values.

  These rest on the owner's pass answers. There is no screenshot of the last three.
- **New, TR8SR M-1 (MEDIUM): the list's "Generation N" is the context's *current* generation,** not the one the root was created
  under (`real_workspace_v1.sql:321`, `service.py:453-481`, `RealModeApp.tsx:134`).
  - R8's first root, created under generation 1, shows "Generation 3" next to its unchanged creation time.
  - The value is the design's (2.4 step 1), but the label invites the wrong reading: that the renew created or re-bound the
    root.
  - The read view shows no generation at all.
  - It needs a relabel, or the stored generation shown. Not fixed.
- **Still open from DR-R8:**
  - DR-R8-2 (price row; the owner's decision);
  - DR-R8-7 MEDIUM (the acknowledgement comes last);
  - LOW:
    - DR-R8-5: values run into their labels;
    - DR-R8-6: very wide raw lines;
    - DR-R8-8: bare refusal code;
    - DR-R8-9: unstyled, no navigation, depth not visible.

### 8.4 Statements the design and the PDs require this package to carry

**(a) D-1 and D-2 were not collected on the real context.** They are accepted deviations (PD-0068 answer 3).
- D-1: expiry is not observable on the real data.
- D-2: rollback after writes is not forced.

Both are shown on invented data only.

**D-3 was not declared** (PD-0078 consequence 4). Two-user isolation was collected on the real install (6.1, 6.2).

**(b) Section 7's accepted limits,** verbatim from design :2741–2767 (one sentence in the source, split here for counting).
F1 is reported closed for this target only together with these:
- "the ACK-loss limit (PD-0068 answer 2);"
- "D-1, expiry not observable on the real context, and D-2, rollback after writes not forced there (PD-0068 answer 3);"
- "the upper-bound limit of `term_end_not_after` (PD-0068 answer 4);"
- "the two disclosed limits of the commit-time deadline, the commit-processing gap and the guard-bypassing executor (PD-0068
  answer 1);"
- "the residual of the post-seal tail, if the owner accepts it (8.1 item 11);" The owner accepted it in PD-0081 (see (g)).
- "D-3, two-user isolation not collected on the real context, if R7 finds the real-mode app cannot hold a second user without an
  economic write; R8 does not start unless the owner's recorded answer to D-3 is an acceptance". Not applicable: D-3 was not
  declared.
- "and the evidence limits of the install rule (1.2 rules 5.1, 5.3 (e), 5.4 and 7: the installer's accepting side, and with it
  the first read of a REAL catalog, are first exercised at R8 step 1; a wrong refusal after Phase 1 leaves a created, unused
  install, and a Phase 1 failure leaves a partial one; grants are audited by the installer's Phase 2 and `--check` and not at
  each gated start; `withdraw` would answer a server's request for a cleartext password; R6's plan states them for the owner's
  approval)." At R8 the accepting side passed: Phase 0, 1 and 2 and both `check` runs exited 0.
- The loader's login limits, (c) below.

**(c) The loader's login limits,** in PD-0070's words as section 7 carries them (design :2761–2767): "it stops new connections
only, and whether `NOLOGIN` ends a session that is already open is not shown; the superuser and the owner role are not affected;
each later load needs the owner's `LOGIN` step. During a load window the owner opens, the loader can read what its narrowed list
allows, including the payload bytes through the registry (3.3). … The steps are the owner's procedure: no tool enforces them (E29
only prints the state; 3.3)."

**The sequence R8 followed** was two windows (PD-0076 C). The loader was created `NOLOGIN`. The owner typed the loader password
for each window. Each window closed with `NOLOGIN` and zero loader sessions:

| Window | LOGIN | Last loader session ended (UTC) |
|---|---|---|
| 1 | 11:38:19Z | 11:38:53Z |
| 2 | 11:44:42Z | 11:45:08Z |

The supplement opened no loader window.

**The owner held both the executor's and the loader's credentials. No agent session held either** (PD-0077; the owner's
statement in 6.1). In the supplement too, every password was typed by the owner at a reviewed tool's prompt or at sudo.

**(d) What a withdrawal or lapse does not cover** (design 3.3, :2039–2209), so that "all four rights refused" is not read as "no
stored data is readable":
1. "the raw files, the download tool and the legacy command-line tools (W01, W02, W12, including `real_slice.py` reading
   `FileStore`);"
2. "the purpose locks: the legacy tools do not follow them…". A stored export right governs the database export path only, not
   `evidence_pack real` or an OS copy.
3. "the staging store, if R4b's plan makes one (6.4)";
4. "the loader's reads, of the `md_*` tables and of the candidate registry". No lease reaches them. They are closed between
   loads by the owner's `NOLOGIN` and open inside a window the owner opens. For this context they include the Alpha Vantage
   closes in `AAPL_compact.csv`, the OpenFIGI file and the NYSE calendar file, with their manifests;
5. "the proposal files that R4b writes."

The lapse is the fail-closed backstop for the four purposes and for the executor's reads of the stored market data. It is not one
for the raw files, a staging store or the proposal files. The design's proposal to move a staging store aside as well is **not
decided**.

**(e) Export was shown refused by a direct gateway admission (the admission probe), not at a product route.** All four rights
were shown:
- create, read and reproduce at the real-mode routes;
- the list with its per-root status;
- export at the gateway.

**(f) The upper-bound limit** (PD-0068 answer 4, design :1745, :1788): `valid_until` is not later than the recorded upper bound of
the term end. No lower bound of the term end is recorded, so this does not show that the lease stays inside the licence term. It
stands until the owner pins the term start and records a renewal. PD-0084 states it.

**(g) PD-0081's four items, first exercised at R8:**
1. **The real branch's seal on an accepted `synthetic = false` result.** It passed: three real creates committed with 201 (R8's
   two and Y), which needs O1 and O4 to pass, and the real-only seal checks did not refuse.
2. **The branch inventory: not captured.** `log_statement = 'none'` and there is no access log, so which deferrable constraints
   fired is unknown. None refused.
3. **The real commit's size and timing.** R8's create took 93 ms in the browser's Network panel. Nothing reached `complete_by`.
4. **A stall or fault drill: none,** as PD-0081 states. The supplement's restart was between requests, not during a commit.

### 8.5 Other incomplete items

- **The supplement's record (TR8SR L-1 to L-4):**
  - L-1: its "Create outcomes" section is empty. Y's 201 and the other create-route requests appear only under Records.
  - L-2: "Commands and exit statuses" shows `-> running` for the two launcher starts that in fact exited 2.
  - L-3: the cause of either failed launcher attempt cannot be known from the record. The counter runs across both starts, so
    "failed attempt 2" is the first failure after the restart.
  - L-4: no preflight lines were recorded for the two launchers that served. That the preflight passed after the restart is
    inferred from the code: the launcher serves only after its start gate passes.
- **R8's L findings:**
  - L-3: the record's create time is when the owner typed the answer (19:53:56), while the stored create time is 19:52:23;
  - L-4: rule 0.3 and 0.4 wording did not name the expected 409 or the probe's exit 1. Rule 0.3 now has the expected answers;
    0.4 is unchanged.
- **Not recorded at R8:** the refused sign-up and the browser console errors. The second root's id is now known from the list (5).
- **CN and HK markets, OCR, scenarios and AI explanation** are outside F1. US-only real validation is the interim scope that
  PD-0041 decided.

## 9. Deviations

### 9.1 From the PRD and the design

These remaining items are deviations from the design's R8 list that **no PD accepts yet** (8.2). They are put to the owner in
section 11:
- T06 in part;
- the restart clean only;
- replay, conflict and B's 404 through the tool, not the browser;
- UNKNOWN-then-repeat not exercised;
- replay on Y rather than R8's own commit;
- 10.3 not observable.

Accepted already: the read and reproduce refusal codes under the withdrawal (PD-0088 consequence 2).

### 9.2 From the runbook's stop procedure: the first attempt (ratified, PD-0088)

- **The first attempt stopped at Phase 0.** It began at 00:41 on 2026-11-16 under the same P8. Phase 0 is read-only. It failed four
  times with `PF_CONNECT_FAILED`, and at 19:32:42 the runner latched `PASSWORD_RETRIES_EXHAUSTED`.
- **The rebuild.** On the main session's instruction, which was the PM's error, the owner rebuilt the cluster and moved the
  state folder to `~/finweb-r8-attempt1` instead of using `--reset-stop`. Nothing had been written.
- **The owner ratified the rebuild:** "Ratify the rebuild (Recommended)" (PD-0088 consequence 3). The R8 run stands. The ratification
  covers this one event and does not change the stop procedure.

## 10. New assumptions since the previous gate

- **Two-user isolation on the real install rests on the fifth role** (PD-0078), so the web account store is separate from the
  executor.
- **The owner's attestations stand in for screenshots** for the Chinese text, the Quick and Simple depths, and the three screen
  fixes.
- **Holding / 10 = close is a reviewer's cross-check,** not a product claim.
- **The loopback tool is evidence of the API, not the browser.** The supplement's replay, conflict, error and B checks went through
  `r8_http_check` at the real-mode routes. That is the same server path the screen uses, but not the screen.

## 11. Open risks and unresolved decisions (the owner's)

1. **The remaining limits (9.1).** Accept them as deviations, or ask for more work. Each one, and what closing it would take:
   - **T06 only in part:** closing it needs a server-side trace of the create's transaction. It cannot be read on the screen or
     at the API.
   - **A clean restart only:** closing it needs a kill or crash drill on the real cluster during or after a write. That is
     riskier, and PD-0081 already declines drills.
   - **Through the tool, not the browser:** closing it needs the same requests replayed from the screen. The screen offers no
     replay or conflict button, by design.
   - **UNKNOWN-then-repeat not exercised:** closing it needs a fault injected during a real create.
   - **Replay on Y, not R8's own commit:** closing it needs one more tool run with R8's original name.
   - **10.3 not observable:** this is only observable on a result without a NAV.
2. **TR8SR M-1, the list's generation label.** Relabel it ("current generation") or show the stored generation. This is an engineer
   increment with design and technical review.
3. **DR-R8-2:** whether a stored price row should be shown.
4. **DR-R8-7 and the LOW findings** (8.3), and the record findings TR8SR L-1 to L-4 (8.5).
5. **The upper-bound limit (8.4 f).** It stands until the owner pins the Alpha Vantage term start.
6. **The cluster.** It is still running on the owner's machine, with live real rights until 2027-09-01. Withdrawal (runbook 11.3)
   is the owner's act if the rights should end sooner.
7. **The public copy.**
   - The vendor values appear in this package, in DR-R8, and in `r8_guide.py` and its test.
   - The public-copy build script must redact them before the next public push (PD-0083).

## 12. Reproduction and inspection

1. Read `~/finweb-r8/R8_RECORD.md` and `~/finweb-r8-supplement/SUPPLEMENT_RECORD.md`. Cross-check any line against the matching
   `events.log` (JSON lines, append-only).
2. Recompute the decision records:
   ```bash
   git show eca287a:decisions/product/PD-0084-r8-publish.md | shasum -a 256
   ```
   Do the same for `b480fe1` (PD-0085) and `8cf051d` (PD-0086).
3. Recompute the refusal bodies at S8, with no database:
   ```bash
   PYTHONPATH=src uv run --no-cache --no-sync --frozen --offline python -c "import hashlib; from marketdata.canonical import canonical_json; import web_api.real_scoped_contract as k; [print(c, hashlib.sha256(canonical_json(k.refusal_payload(k.ContractRefusal(c))).encode()).hexdigest()) for c in ('RW_NOT_FOUND','RW_IDEMPOTENCY_CONFLICT','REAL_REQUEST_INVALID')]"
   ```
   Compare the output with the `body_sha256` values in the supplement's record. The PM ran it on 2026-11-17 and got `cd867728…`,
   `277799f8…` and `bd9c5656…`, which equal the record.
4. Compare holding and NAV in 6.1 and 6.2 with ruling §9.1.
5. Read TR8R, TR8S to TR8S4, TR8F to TR8F3 and TR8SR in `reviews/TECH_REVIEW.md`, and DR-R8 in `reviews/DESIGN_REVIEW.md`.
6. To see the screen:
   - follow runbook 9.2–9.3 with `~/finweb-r8/C2.json`; the launcher asks for the executor password, then the account
     password;
   - sign in as user A;
   - click **Open** on a listed root.
7. Do not run R8 or the supplement again, and do not create a `finweb_real*` database.

## 13. Agent recommendation

**APPROVED WITH CONDITIONS.**

Why not REVISION REQUIRED again:
- Every item PD-0087 asked for is done. The supplement collected replay, idempotency, the conflict, the error digest, a real
  restart and B's 404. Check 10.1 is corrected and passes. DR-R8-1, -3 and -4 are fixed and seen. The first stop is ratified.
- An independent review found every answer matching the expected one, with no observation in question.
- What remains is either not collectable without a fault drill or a server trace, which PD-0081 already declines, or is
  low-value repetition (replay on R8's own commit).

Why not APPROVED as is:
- The remaining limits (11.1) are deviations no PD accepts yet. They need the owner's words.
- TR8SR M-1 is a real-screen label that can mislead about which data a result is bound to (P9, auditability).

The conditions the PM would propose, to be recorded verbatim if the owner adopts them:
1. **Accept the remaining limits** listed in 11.1 as deviations, so that HG4's "real-data usable" claim carries them.
2. **Fix TR8SR M-1** (the generation label) in an engineer increment, with design and technical review, before real-mode results
   are shown to anyone other than the owner.
3. **Redact the vendor values** in the public copy before the next public push (PD-0083; 11.7).
4. **Track DR-R8-2, DR-R8-7, the LOW findings and TR8SR L-1 to L-4** as follow-up work. None of them is decided here.

The owner may also choose REVISION REQUIRED (naming what to collect or fix first), APPROVED (accepting 11.1 with no conditions),
or REJECTED.

## 14. Human decision block

Revision 2:

```text
[ ] APPROVED
[x] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Human comments: "Approve with conditions" (verbatim); conditions confirmed: "Yes, those four (Recommended)",
answering whether the conditions are exactly section 13's four (PD-0089)

Decision date: 2026-11-17
Approver: the designated human product owner
```

Recorded in [PD-0089](../../decisions/product/PD-0089-hg4-approved-with-conditions.md), with the four conditions in the words
of the confirming question.

Revision 1 (2026-11-16): `[x] REVISION REQUIRED`. Human comments: "Revision required" (verbatim; PD-0087). Approver: the
designated human product owner.
