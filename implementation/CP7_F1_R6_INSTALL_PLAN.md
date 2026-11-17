# F1 R6 — written install plan for the real database

**Status:** the owner decided choices A to E on 2026-11-01 (`decisions/product/PD-0076-r6-install-plan-choices-a-to-e.md`); section 3 carries the
answers and the later sections their consequences; PD-0077 settles the loader route (the owner types the loader password at the tool's prompt in the
owner's own terminal; no agent session holds it). Nothing in this plan has been run against a real cluster. Still open, not decided by PD-0076 or
PD-0077: R6R-L1 (no tool does the step (4a) registration; any such tool must take its password from the owner's terminal prompt) and TR6R-L1 (an
UNKNOWN registration falls inside window 2), section 11. R8 step 1 follows the plan the owner approves (`implementation/CP7_F1_REAL_PATH_DESIGN.md`
1.2 rule 4, 7.1 R6 and R8; PD-0066 decision 10).

**Amended 2026-11-07 by PD-0078 (`decisions/product/PD-0078-fifth-account-role-for-web-accounts.md`): the install has FIVE roles, not four.** The fifth is
`finweb_real_account`. It holds the real-mode web app's accounts and sessions and nothing else: `SELECT`, `INSERT` on `app_user` and `web_identity`;
`SELECT`, `INSERT`, `UPDATE`, `DELETE` on `web_session` and `web_auth_rate`; `USAGE` on the schema. Phase 1 creates it `LOGIN` with no password, the owner
sets its password at the prompt of the tool that starts (the real-mode launcher's `--account-user`; PD-0077's rule), Phase 2, the preflight and the
catalog audit judge it as they judge the other four, and a role or grant beyond that list refuses. Wherever this plan says "the four roles", read "the
five roles"; the sections below are amended where the count or the credential holders matter (section 4 items 4 to 6, section 5 steps 3 and 4,
the per-window check in section 6, the holders table in section 12). PD-0076 stays unchanged as a record.

**Author:** the Engineer (R6 build). **Contracts:** design sections 1, 1.2, 2.5, 3.3, 4.2, 5.1 to 5.4, 7.1 (R6 and R8 rows), 8.1 PM item (vi),
PD-0066, PD-0069, PD-0070, PD-0075. **Inventory:** `reviews/CP7_F1_R6_INVENTORY.md` (taken by the main session on 2026-11-01 under PD-0075
decision 1).

Contents: 1 Inventory and what it forces. 2 What R6 built, and how it is run. 3 The owner's choices (DECIDED, PD-0076). 4 The install rule applied: the
cluster, `pg_hba.conf`, settings, passwords. 5 The sequence at R8 step 1. 6 The loader's login sequence. 7 Evidence limits. 8 Calibrating the
classifier in the cloud. 9 Owner procedures no tool enforces. 10 After a later migration; test tooling. 11 Carried residuals. 12 Exit checklist.
13 Engineering decisions the contracts did not cover.

---

## 1. Inventory and what it forces

The read-only inventory is `reviews/CP7_F1_R6_INVENTORY.md`. I did not read the owner's configuration files myself. Its section 7 is the part this
plan relies on:

1. **The real database cannot share the development cluster.** The shared development cluster (Homebrew `postgresql@17`, data directory
   `/opt/homebrew/var/postgresql@17`) trusts every role on its socket (mode `0777` in `/tmp`) and on loopback TCP, and the test kits need that
   trust (PD-0071, `dev_env.py`). Design 1.2 rule 1 allows only `scram-sha-256` and `reject`. Putting the real database there would mean rewriting
   the development cluster's `pg_hba.conf` and passwords, after which the superuser-driven test tooling could never run again (rule 3). **So the
   plan assumes a cluster of its own** (rule 3's preference); the shared-cluster alternative is listed in section 3 A only for completeness.
2. **The agents' OS user, `<os-user>`, owns both existing data directories** (the development cluster, and the CP7 cluster at
   `.local/cp7-postgres/data`, inside the project and not running). Every agent session runs as that OS user. Whatever the placement of a new
   cluster, if its data directory and `pg_hba.conf` are owned by that user, an agent session can read or edit them and restart the cluster.
   Design 1.2 rule 3 says this is **not claimed** to be protected. It is a limit, stated in section 3 A, unless the owner chooses a dedicated OS
   user.
3. `max_prepared_transactions = 0` and `password_encryption = scram-sha-256` hold on the development cluster as defaults. The new cluster **sets
   both explicitly** (section 4), and the preflight checks both.
4. There is **no `~/.pgpass`, no `~/.pg_service.conf`, no `pg_service.conf` under `pg_config --sysconfdir`, none in `/etc/postgresql-common`
   (the compiled-in default of the libpq that psycopg-binary bundles; the inventory's section 6 now records it)**, and no `PG*` variable in the agent
   shell. So Pass S has nothing to find today. It stays in the preflight because the owner's home can change.
   **Pass S scans every location the tools' libpq could use for a service file (TR6B-M-1):** `PGSERVICEFILE`, `~/.pg_service.conf`, `PGSYSCONFDIR`,
   `pg_config --sysconfdir` and the compiled default `/etc/postgresql-common` (the list `LIBPQ_COMPILED_SYSCONFDIRS`, pinned in code; a different
   libpq build could compile in another directory, and a change to that list is a reviewed change). **If `pg_config` is missing or fails, or a file
   that exists cannot be read, the preflight REFUSES (`PF_NOT_INSPECTED`); it does not note and pass.** So the tools need `pg_config` on the owner's
   `PATH` (it ships with the PostgreSQL server packages the owner installs for the real cluster). A passfile or service-file host that names the
   socket directory is matched by real path, so a trailing slash or a symlink in its spelling still matches (TR6B-L-4).

**HOLD from the inventory (unknown to me, listed not resolved):** whether the Homebrew launch agent is loaded and restarts the development cluster
at login; whether any development-cluster role has a stored password; whether other software on the Mac connects to the development cluster over
loopback. None bears on the real cluster as long as it is a cluster of its own, with no TCP.

## 2. What R6 built, and how it is run

| Part | File | Run by | Notes |
|---|---|---|---|
| Preflight (decision logic, probe, Pass S, classifier) | `src/persistence/real_preflight.py` | called by the tools below | pure `decide` over a `Facts` record; gathering and probing are separate |
| Real installer | `src/persistence/real_install.py` (`python -m persistence.real_install phase0 / phase1 / phase2 / check`) | **the owner, as the cluster's superuser, in the owner's own terminal** | writes install kind `REAL` and no other; takes its file list and grants only from `real_roles` through `_install_gateway_body(kind="REAL")`; never names the TEST-only part's file; takes its password from a terminal prompt (no option, file or environment variable) |
| Publisher tool gate | `src/persistence/real_workspace_store.py` | the owner | `publish` and `renew` run the gate against a REAL target and write nothing if it refuses; `withdraw` is never gated |
| Catalog audit extension (FR-L1 (b)) | `src/persistence/real_catalog_audit.py` | Phase 2 / `check`, and the TEST tests | compares the definitions of the five INSERT-path guard functions with the migrations' (Python only, no gateway SQL change) |
| Name tripwires (rule 6) | `src/persistence/connection.py`, `tests/product/guarded_pg_provision.py` | automatic | the TEST provisioner refuses a cluster holding a `finweb_real*` database; `missing_env_vars` refuses a `FINWEB_PG_DATABASE` in the reserved namespace |
| Identity seed | `src/real_tools/identity_seed.py` (`python -m real_tools.identity_seed`) | **the owner**, as the superuser (then `SET ROLE` the schema owner) | idempotent write of `issuer`, `instrument`, `listing`; refuses unless the seed's identity digest equals the verified proposal snapshot's; the executor gets no grant on these tables |

**Gate by command (design 5.1, built as such).** `publish` and `renew` run the preflight before they change anything and stop on any failure.
`withdraw` prints its own result and fixes its exit status first, then runs the preflight and prints the result beneath it; the preflight is
wrapped so that no failure, timeout or interrupt (Ctrl-C included) changes the withdrawal's lines or status (a pending withdrawal keeps its own
status 3; TR6B-L-2). The launcher and the admission probe are R7's. The decision uses two facts read from the
database, never an argument, variable or key: the install-kind row, and whether the database name starts with `finweb_real`.

| Kind row | Name | `publish` / `renew` | `withdraw` |
|---|---|---|---|
| `REAL` | reserved prefix | preflight, `require_auth=scram-sha-256` from the first connection | proceeds; preflight printed after |
| `TEST` | not reserved | no preflight (TEST scopes only) | proceeds |
| `REAL` or `TEST` | the other pairing | refused (`PF_KIND_NAME_DISAGREE`) | proceeds, nothing printed |
| none, unreadable, or more than one row | any | refused (`PF_NO_KIND_ROW`) | refused with `PF_NO_KIND_ROW`; nothing written |

**New named refusals** (each in the decision table and tested on fake facts): `PF_SERVER_VERSION_BELOW_17`, `PF_PREPARED_TRANSACTIONS`
(`max_prepared_transactions` other than 0), `PF_LISTEN_ADDRESSES`, `PF_SESSION_REPLICATION_ROLE`, `PF_CONNECTED`, `PF_OTHER_OUTCOME`,
`PF_LOGIN_POWER_ROLE`, `PF_ESCALATION_PATH` (membership), `PF_ROLE_SETTING`, `PF_DB_ROLE_SETTING_ROW`, `PF_PARAMETER_PRIVILEGE`,
`PF_CONNECT_OUTSIDE_REAL_DATABASE`, `PF_STORED_CREDENTIAL`, `PF_NOT_INSPECTED`, `PF_PROBE_NOT_RUN`, `PF_HBA_METHOD`, `PF_HBA_NOT_LOCAL`,
`PF_HBA_ROW_ERROR`, `PF_HBA_FILE_LOADED_DIFFER`, `PF_VERIFIER_NOT_SCRAM`, `PF_PASSWORD_ENCRYPTION`, `PF_LOG_STATEMENT`,
`PF_PATH_UNDER_FORBIDDEN_ROOT`, `PF_CATALOG_AUDIT`, `PF_REAL_ROLE_MISSING`, `PF_REQUIRE_AUTH`, `PF_CONNECT_FAILED`,
`PF_REAL_ALREADY_EXISTS`, `PF_PREFLIGHT_REFUSED` (the tool's own code). A catalog or file the tool cannot read is a refusal
(`PF_NOT_INSPECTED`), never a pass.

**Outcome classes.** Every connection attempt is `CONNECTED`, `CHALLENGED`, `REJECTED` or `OTHER`. Only `CHALLENGED` and `REJECTED` pass; `OTHER`
refuses (a timeout, a missing socket, an unrecognised message, an error after authentication). A mis-calibrated pattern therefore fails closed.

**Installer exit codes:** `0` done, `2` refused (nothing changed by this step), `4` Phase 1 failed partway (what ran stays).

## 3. The owner's choices (DECIDED, PD-0076)

The owner decided A to E on 2026-11-01. The record is `decisions/product/PD-0076-r6-install-plan-choices-a-to-e.md`; each answer is quoted below
verbatim. The options and my recommendations are kept under each answer as the record of what was offered. The plan's later sections carry the
consequences. R6R-L1 and TR6R-L1 stay open (section 11).

### A. Cluster placement, the `CONNECT` option, and the data-directory owner — **DECIDED (PD-0076 A): "Own cluster, new OS user (Recommended)"**

**Consequences carried.** The real cluster is a cluster of its own, outside the project directory and `$TMPDIR`; its data directory, `pg_hba.conf`
and socket directory belong to **a dedicated macOS user that agent sessions do not run as**. The owner creates that user. Section 4 item 0 and
section 5 give the owner steps: `initdb` and `pg_ctl` run as that user; the installer (`real_install`) and the identity seed run in the owner's
terminal as the cluster's superuser (the database role) and connect over the socket; the socket directory must be reachable by the account that runs
them. **The remaining limit:** whatever that user's OS permissions leave open to `<os-user>`, the agents' user, most plainly the socket directory
(an agent can reach the socket if the directory lets it, and then meets scram and the preflight, not `trust`). R8 step 1 checks the placement: Phase 0
prints `data_directory`, `hba_file`, `ident_file` and `unix_socket_directories` and refuses any under the repository root or the system temporary
directory, and the owner confirms by listing the directory's owner and mode that `<os-user>` cannot write the data directory or `pg_hba.conf`. The
installer cannot see OS permissions (5.4); that confirmation is the owner's.

Options offered:

1. **A cluster of its own, data directory and `pg_hba.conf` outside the project directory and `$TMPDIR`, owned by the agents' OS user
   (`<os-user>`).** The installer's revoke of PUBLIC's `CONNECT` on `postgres`, `template1` and any other connectable database of that
   cluster (Phase 1) makes "the real roles get no `CONNECT` elsewhere" true. **Limit, stated plainly:** an agent session running as that OS user can
   read or edit `pg_hba.conf`, restart the cluster with `trust`, or read the data directory. The scram rule and the preflight then stop an
   *accidental* path and show a *current* state; they do not stop an agent that decides to reconfigure the cluster. Design 1.2 rule 3 does not
   claim otherwise.
2. **A cluster of its own, owned by a dedicated OS user** that agent sessions do not run as (the strong form, rule 3). The owner creates the user
   and runs `initdb`, `pg_ctl` and the installer as the appropriate users. The remaining limit is whatever the dedicated user's OS permissions
   leave open to `<os-user>` (for example the socket directory).
3. **The shared development cluster, with PUBLIC's `CONNECT` revoked** on its existing databases. Needs its own approval (PD-0066 decision 6). It
   conflicts with the inventory: the cluster trusts every role by design and the test kits need that. If chosen, the existing superuser-driven test
   tooling can never run on it again. **Not recommended; not buildable without rewriting `pg_hba.conf` of a non-disposable environment.**

**Recommendation:** option 2 if the owner is willing to create a second OS user; otherwise option 1 with its limit recorded in the HG4 package.
Either way the data directory is not under the project directory or `$TMPDIR`, and the installer refuses one that is (`PF_PATH_UNDER_FORBIDDEN_ROOT`).

### B. Who holds the executor and loader credentials — **DECIDED (PD-0076 B): "You executor, agent loader"** (not the recommended option), **narrowed by PD-0077 to the owner alone for both** (design 1.2 rule 4)

**PD-0076's answer, verbatim:** "You executor, agent loader" (offered as: "You hold the executor. A named agent session may be given the loader
password for a load window only; inside it, it can read what the loader's list allows, including the stored payload bytes."). B says "may".

**PD-0077's answer (`decisions/product/PD-0077-loader-password-typed-by-owner-only.md`), verbatim:** "I type it myself (Recommended)" (offered as: "You
type the loader password at the tool's prompt in your own terminal for each window; no agent session ever holds it. This is within B as decided (B
says 'may'), costs nothing now, and the plan makes it the only route.").

**Consequences carried.**
* **Executor: the owner alone.** Typed at the prompt of the terminal that starts the launcher or the admission probe (R7).
* **Loader: the owner alone, for each window.** The owner types the loader password at the tool's prompt in the owner's own terminal. **No agent
  session holds it, and none is given it in chat.** The only route is that prompt in the owner's terminal. An agent-held loader route would need a
  new owner decision.
* **Why chat is not a route (the reviewer's assessment, TR6C-1, replacing my earlier "open, does not contradict" wording).** An agent session's shell
  has no terminal (`/dev/tty` is not available; `getpass` reaches end of file), so the owner cannot type at a prompt into an agent session. Rule 4
  rules out the environment, a project file, a passfile and a service file. **Chat is the only channel left.** It writes the password into the
  session's transcript on disk, which every agent session of the same OS user can read, and sends it off the machine. A password given that way
  would contradict PD-0076 B ("by a prompt, never by a file") and design 1.2 rule 4 (the loader credential is not stored where an agent session can
  read it, rule 2's table), and the package could not truthfully name one session as the holder. PD-0077 removes the route.
* **Inside a window, what the loader's role can read** (design 3.3; the owner's tool run holds the credential, so the reads happen in the owner's
  terminal's process): `md_file`, `md_release`, and through the registry's get function the payload bytes of every registered context (for the HG4
  context, the Alpha Vantage closes in `AAPL_compact.csv`, the OpenFIGI file and the NYSE calendar file, with their manifests, acquisition
  envelopes and witnesses). **What it can write during a window:** `INSERT` on the thirteen `md_*` tables (append-only, with the sealed-release
  trigger bounding which releases can still take rows) and the registry's put function (the candidate bundles, bound by the snapshot's pinned
  digests). Outside a window nobody can log in as the loader (`NOLOGIN`).
* **The HG4 package states that the owner held both credentials** (the executor's and the loader's) and records, per window, the times the owner
  opened and closed it (section 6). It names no agent session as a holder.
* The vendor payloads stay internal-use (PD-0027/PD-0028). **The loader credential never goes to a cloud session**; the cloud calibration (section 8)
  uses invented credentials only.
* **Any tool for step (4a)** (R6R-L1, still open) must take its password from the owner's terminal prompt (`pf.terminal_prompt` through
  `connect_with_prompt`), like the installer and the seed.

R8 step 1 follows this answer. The credential is always typed at a prompt in the terminal that starts the tool; never an environment variable, a
project file, a passfile or a service file (Pass S and Pass B check the stores libpq would read).

| | Executor (create, read, reproduce while the context is live) | Loader (during a window the owner opens) |
|---|---|---|
| Option 1 | **The owner alone**, typed into the terminal that starts the launcher or the probe | **The owner alone**, typed into the terminal that runs the load |
| Option 2 | The owner gives a named agent session the credential for the R8 run (the recorded limit of rule 4): that session can run the product's own admitted paths while the context is live | The owner gives a named agent session the credential **for the window only**; inside the window that session can read what the loader's list allows: `md_file`, `md_release`, and through the registry's get function the payload bytes of every registered context (for the HG4 context, the Alpha Vantage closes, the OpenFIGI file and the NYSE calendar file) |

**Recommendation:** option 1 for both. The executor's reads and writes are bounded by the lease, the fence and the deadline; the loader's reads are
not bounded by any lease (3.3), which is why PD-0070 decision 1 puts its login off between loads. Option 2 for the executor is a smaller step than
option 2 for the loader.

### C. One loader window or two — **DECIDED (PD-0076 C): "Two windows (Recommended)"** (design 3.3 item 1; PM item (vi); conformance R6C-M1)

**Consequence carried (with D):** section 6 gives the two-window sequence. Window 1 is the qualification load (R8 step (2)); window 2 is the step (4a)
registration and opens only after the publish.

The loader's last use is R8 **step (4a)**, the post-publish registration of the context-bound candidate (R2's exit, STATUS: "the loader's last R8
use is step (4a)"; every registry call checks `LOGIN`). It first appears at step (2), the qualification load. The owner reviews the proposal files
between them (step 3).

* **One window:** the loader keeps `LOGIN` from step (2) to the end of step (4a). Fewer owner steps; the loader's reads (including the payload
  bytes) are open for the whole review.
* **Two windows:** `NOLOGIN` right after step (2); `LOGIN` again before step (4a); `NOLOGIN` after it. Two more owner steps; the loader's reads are
  closed during the review. Existing sessions are not ended by `NOLOGIN` (R2 L-3, section 11): the owner ends them, or waits.

**Recommendation:** two windows, since PD-0070 decision 1 says "off between loads" and the review is not a load. The owner sets the password with
`\password` at the start of each window, so each window has a fresh credential.

### D. Phase 1 creates the loader `LOGIN` or `NOLOGIN` — **DECIDED (PD-0076 D): "NOLOGIN + check per window (Recommended)"** (design 3.3 item 3; conformance R6C-L1; technical TR6-L1)

**Consequences carried.** Phase 1 runs `real_install phase1 --loader-login nologin`. In each window the owner sets `LOGIN`, sets a fresh password with
`\password`, runs `real_install check` (read-only), lets the load or registration run, and sets `NOLOGIN`. **With `NOLOGIN` at creation and two
windows, Phase 2 never checks the loader in its login-capable state (R6R-L2, 5.3 (g)); the per-window `check` is the mitigation, and it is an owner
procedure that no tool enforces.**

R2's exit (b): the install accepts a `NOLOGIN` loader and every registry call checks `LOGIN`. The installer takes the choice as a required
option, `phase1 --loader-login {login,nologin}`; it has no default.

* **`nologin`:** nobody can log in as the loader until the owner opens the first window. **Consequence the owner must accept (5.3 (g); conformance
  R6R-L2):** the checks keyed to `LOGIN` (the probe's attempts, the verifier check, the login-power check) **do not cover the loader while it
  cannot log in**. With two windows and `nologin` at creation, Phase 2 never checks the loader in the state in which it can log in. The mitigation
  is the owner's: run `real_install check` **inside each window, after the loader is set `LOGIN` and given its password**. `check` is read-only.
* **`login`:** the loader exists with `LOGIN` but with no password, so scram refuses it until the owner sets one (`auth-password`), and Phase 2
  covers it. The cost: between creation and the first `\password` the role is `LOGIN` with no verifier, which the verifier check treats as
  "not scram" if the owner left it that way.

**Recommendation:** `nologin`, with `check` run inside each window (the mitigation above). E29 prints each real role's login state in every
preflight output (it prints; it never refuses).

### E. The `withdraw` connection's `require_auth` — **DECIDED (PD-0076 E): "Refuse plaintext (!password) (Recommended)"** (design 5.1; PD-0066 decision 7)

**Consequences carried.**
* **Code:** `real_preflight.WITHDRAW_REQUIRE_AUTH = "!password"` (reviewed change, this follow-up). `withdraw`'s connection to a REAL target now carries
  `require_auth='!password'`; `publish`, `renew`, the installer and the seed keep `scram-sha-256`. `withdraw` is **still never gated by the
  preflight**: only its own connection changed. A unit test shows the connection string each command builds
  (`test_the_connection_parameters_of_each_command_carry_the_require_auth_of_pd_0076`), and the static and by-command tests no longer pin `None`.
* **What `!password` does and does not do** (libpq 18.0.6 in psycopg 3.3.6; the negation is libpq 16+). It refuses only a server that asks for a
  **cleartext** password, so the publisher's password is not sent in clear to whatever answers on the socket. It **allows** an md5 exchange (an MD5
  digest, not the password) and a trust server (nothing asked). So it is weaker than `scram-sha-256` against an impostor that asks for md5. The
  owner accepted that trade for a withdrawal that a normal scram-only server never stops.
* **Server test (opt-in, not run on the Mac, not run by me):** section 8 lists five tests that show, against a throwaway cluster in the cloud, that a
  `password` (cleartext) server is refused and no PasswordMessage is sent (also shown on the wire by a stand-in server), that a scram server with the
  right invented password connects, and, as recorded contrast, that md5 and trust servers are allowed by `!password` and stopped by
  `scram-sha-256`. Until that test has been run in the cloud, `!password`'s behaviour against a server is shown only by libpq's documentation and the
  connection-string unit test.

Offered text (before the decision): `withdraw` connects without the demand that the server use scram, so it would answer a server's request for a cleartext password and send the
publisher's password to whatever answers on the socket path (an impostor inside rule 7's trusted-operator boundary). Options:

1. **None** (the build before PD-0076; `real_preflight.WITHDRAW_REQUIRE_AUTH = None`). Nothing can stop a withdrawal on authentication grounds.
2. **`scram-sha-256`.** Closes the impostor case, and is one more thing that can stop a withdrawal.
3. **`!password`** (negated). libpq then refuses only a server that asks for a cleartext password. libpq in the installed psycopg accepts the keyword
   (psycopg 3.3.6 bundles libpq 18.0.6; the negation is libpq 16+; I confirmed only that the connection string is accepted, not its behaviour against
   a server). A scram-only server never asks for a cleartext password, so it stops a withdrawal only in the case it is meant to stop.

**Recommendation:** option 3 (the owner's answer). Changing it is a one-constant edit in `real_preflight.py` and a reviewed change; the tool reads no flag for it.

## 4. The install rule applied (design 1.2 rules 1 to 3)

All of this is an **owner procedure**; nothing in R6 runs it. `initdb` is not run by any tool of ours.

0. **The dedicated macOS user (choice A).** The owner creates a macOS user for the cluster (a standard account, not an administrator, with no login
   shell use by agent sessions; the account `<os-user>` that agent sessions run as is not it). The owner creates, as that user, the data directory
   and the socket directory outside the project directory and `$TMPDIR`, with mode `0700` on the data directory. `initdb` and `pg_ctl` are run **as
   that user** (for example `sudo -u <cluster-user> ...` from the owner's terminal). The installer and the identity seed are run in the owner's
   terminal, connecting as the database superuser over the socket with the password typed at the prompt; the socket directory's mode must let the
   account that runs them reach it (and that same mode is the limit: what it leaves open to `<os-user>`). **The owner checks and records,** before
   Phase 1: the owner and mode of the data directory, `pg_hba.conf` and the socket directory, and that `<os-user>` cannot write the first two.
   The superuser's password is the owner's alone and is never given to a session of `<os-user>`.
1. **Create the cluster so that no trust line ever exists:**
   `initdb -D <DATADIR> --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwprompt -U <SUPERUSER> -E UTF8 --locale=C`
   (not `--pwfile`, which keeps the superuser's password in a file). `<DATADIR>` is outside the project directory and `$TMPDIR` (section 3 A).
2. **`pg_hba.conf`:** delete the `host` lines `initdb` wrote, and the `local replication` line if present. The file then holds, at most:
   ```
   local   all   all   scram-sha-256
   ```
   (optionally preceded by `local all <role> reject` lines). Methods allowed are `scram-sha-256` and `reject`; no `trust`, `peer` or `ident`; `local`
   lines only. Replication attempts then match no row and are `REJECTED`. Keep to plain role and database names: a regular expression (`/...`),
   `samerole`, `samegroup`, a `+group` or an `@file` token in a `local` row cannot be predicted by the installer, so the check that the file and
   the loaded rules agree refuses (`PF_HBA_FILE_LOADED_DIFFER`, "unpredictable") (TR6B-L-3).
3. **`postgresql.conf`:** `listen_addresses = ''`, `unix_socket_directories` in a directory outside the project and `$TMPDIR`,
   `password_encryption = scram-sha-256`, `max_prepared_transactions = 0`, `log_statement = 'none'` while passwords are set,
   `log_min_duration_statement = -1`. The installer reads `log_statement` and refuses while it is not `none`; it **prints** `log_min_duration_statement`
   and `log_min_error_statement` (both can log statement text) and does not refuse on them, so keeping them from logging a `\password` ALTER ROLE
   is the owner's setting. Socket mode `0700` is **not** a control against an agent running as the data-directory owner.
4. **Passwords.** The **superuser password is the owner's alone**, set with `--pwprompt` above and never given to an agent session, a project file or
   a tool an agent runs. The installer creates the five roles (PD-0078) **without a password**; the owner sets each with psql's `\password <role>`, never a
   literal `PASSWORD '...'` statement. The publisher's authentication (2.5): password with `scram-sha-256` over the Unix socket, the owner's
   alone, typed at the prompt of the tool that starts. Whose hands hold the executor and loader passwords is section 3 B. **The account role's
   password (PD-0078 consequence 2) is the owner's alone, set with `\password finweb_real_account` and typed at the real-mode launcher's prompt in the
   owner's own terminal; no agent session holds it and none is given it in chat (PD-0077's rule).**
5. **Roles.** `finweb_real_owner` `NOLOGIN`; `finweb_real_executor`, `finweb_real_publisher` and `finweb_real_account` `LOGIN`; `finweb_real_loader` as section 3 D decides.
   All `NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`. **The five hold no membership in any role** (5.3 (b)); there is no
   allowed-pairs or approved-power list. **The account role's grants are exactly `real_roles.ACCOUNT_TABLES` plus `USAGE` on the schema** (PD-0078
   consequence 1): no economic or rooted table, no `md_*` table, no gateway or `md_*` function, no sequence. The catalog audit compares it with that
   list as it compares the executor, the loader and the publisher with theirs; a missing role, an extra grant or an economic grant is a finding.
6. **Database.** `finweb_real`; encoding `UTF8`, `LC_COLLATE 'C'`, `LC_CTYPE 'C'`, template `template0`; `REVOKE ALL ON DATABASE finweb_real FROM PUBLIC`;
   `GRANT CONNECT` to the five roles; **`REVOKE CONNECT ON DATABASE <each other connectable database> FROM PUBLIC`** for `postgres`, `template1` and
   any other connectable database (rule 3). The gateway is installed in schema `finweb`, owned by `finweb_real_owner`, with the CORE file list and the
   REAL role lists, and the install-kind row `REAL` is written last, in the gateway's transaction.
7. **No content.** Phase 1 creates no market data, snapshot or record.

## 5. The sequence at R8 step 1

The owner, in the owner's own terminal. Every command prompts for a password; none takes one on its command line.

**Precondition (PD-0076 consequence 4; TR6C-2).** Before step 1, the five `!password` server tests of `test_preflight_calibration.py` (section 8) have
**passed in the Fin-Web cloud**, and STATUS.md records that run. Until then `withdraw`'s `require_auth=!password` rests on libpq's documentation and
a connection-string unit test, and R8 step 1 does not start.

1. Create the dedicated macOS user and the cluster as that user (section 4 items 0 to 3: `initdb` and `pg_ctl` run as the cluster's user) and start
   it. Confirm `listen_addresses` is empty, and record the owners and modes of the data and socket directories (choice A).
2. `python -m persistence.real_install phase0 --socket <DIR>/.s.PGSQL.<PORT> --user <SUPERUSER>` — in the owner's terminal; writes nothing. Resolve any
   refusal before continuing. (Phase 1 runs Phase 0 itself and creates nothing if it refuses.)
3. `python -m persistence.real_install phase1 --socket ... --user ... --loader-login nologin` (choice D; the option has no default) — creates the roles, the database, the revokes,
   the schema, the migrations, the gateway and the `REAL` row. **It is a sequence of statements, not one transaction** (`CREATE DATABASE` cannot run
   in a transaction block). If it fails partway it says so and exits `4`; what ran stays (rule 7).
4. In psql, as the superuser: `\password finweb_real_publisher`, `\password finweb_real_executor` and `\password finweb_real_account` (PD-0078). The
   loader was created `NOLOGIN` and gets its password when each window opens (section 6), not here. The publisher, executor and account passwords
   are the owner's alone (choice B; PD-0078 consequence 2).
5. `python -m persistence.real_install phase2 --socket ... --user ...` — read-only: every check, including the verifiers and the catalog audit as
   REAL (the **first and only read of a REAL catalog**).
6. **The identity seed**, after the proposal files exist (the seed is checked against the proposal snapshot's `identity_digest`, so it comes after
   the qualification run and the review of its proposal, steps (2) and (3), and before the first real create):
   `python -m real_tools.identity_seed --socket ... --user <SUPERUSER> --seed-file <F> --proposal <P>`. **No tool yet writes the seed file from the
   qualification registry**: `identity_seed.seed_bytes(resolver)` is the library function; R8's plan names who calls it. The seed is idempotent and
   one transaction. **Update 2026-11-14:** `python -m real_tools.qualify_run` (offline) writes the proposal and this seed file in one run. **Ordering
   correction (section 14, G6):** the observation tables reference `listing`, so the seed must run BEFORE window 1's load, not only before the first
   real create.
7. Later steps (qualification load, review, publish, the step (4a) registration, withdraw and renew) are R8's. `publish` and `renew` run the
   preflight at each start; `withdraw` does not.

## 6. The loader's login sequence (PD-0070 decision 1)

Decided (sections 3 B, C, D; PD-0076, PD-0077): **two windows, the loader created `NOLOGIN`, and the owner alone types the loader password, at the
tool's prompt in the owner's own terminal, for each window; no agent session holds it.** Window 1 is the qualification load (R8 step (2)). Window 2 is the step (4a) registration and **opens only after the publish**. The owner's
steps, in the owner's own terminal, **in each window**:

1. `ALTER ROLE finweb_real_loader LOGIN`.
2. `\password finweb_real_loader` — a fresh password for this window (the previous window's is dead).
3. `python -m persistence.real_install check --socket ... --user ...` — read-only. This is the only run that sees the loader in its login-capable
   state (R6R-L2, 5.3 (g)); a refusal stops the window before anything is loaded or registered. The same run judges the account role
   (PD-0078): a grant beyond its list, a missing role or a membership refuses in every window.
4. **The owner runs the load (window 1, `load_qualified`) or the registration (window 2, `RealProvenanceStore.register`, with `reconcile` if it
   reports UNKNOWN) in the owner's own terminal, and types the loader password at that tool's prompt.** The owner's terminal prompt is the only route
   for the loader credential (PD-0077): no environment variable, file, passfile, service entry, argument, or chat message, and no agent session.
   The tool must therefore be one that prompts (`pf.terminal_prompt` through `connect_with_prompt`); none of the two exists as a command-line tool in
   R6 (`load_qualified` and `RealProvenanceStore` are library calls that take an open connection), so R8's plan names or builds them, and a tool
   built that takes its password any other way is refused by the same static test that covers the installer, the seed, the publisher tool, the
   real-mode launcher and the admission probe (`tests/product/test_real_preflight_static.py`). **Update 2026-11-14:** the tool now exists,
   `real_tools/loader_window.py` (`load` for window 1, `register-bound` and `reconcile` for window 2, `check` print-only), with the offline
   `real_tools/qualify_run.py`; commands and what each reads and writes are in section 14. *Correction at R7 (technical TR6C-3):* the test
   previously covered only the tools it listed by name; since R7 it DISCOVERS every command-line program (an `ArgumentParser`, `sys.argv`, a
   `__main__` guard or a `main` function) in `src/real_tools/`, `src/persistence/real_*.py`, `src/web_api/real_*.py` and `src/web_api/*launcher*.py`,
   and fails until that program is listed in the test's `TOOLS`, `ALLOWED_OPTIONS` and `PARSERS` tables, where it then meets every check. A tool built
   outside those places is not found by location: R8's plan should put the loader's window tools there. The residual spellings of technical
   TR6B-R-1 are closed in the same test for the listed tools (aliased or mapped `execute`, `getattr` on a non-literal or dangerous name,
   `sys.modules`, `netrc`, `linecache`, `fileinput`, and a `%` statement that substitutes anything but a validated name); no static test is complete.
5. `ALTER ROLE finweb_real_loader NOLOGIN`.
6. **Before treating the window as closed, end any open loader session** (R2 L-3): `NOLOGIN` does not end a session that is already open, and an
   open loader session still reads `md_file` and `md_release` and holds `INSERT`. The owner lists loader sessions (`pg_stat_activity` where
   `usename = 'finweb_real_loader'`) and ends them with `pg_terminate_backend`, or waits until none remains, and records that in the HG4 package.
   **This is an owner procedure that no tool enforces.**
7. The HG4 package records, for the window: the time `LOGIN` was set and the time the last loader session ended, and states that the owner held both
   the executor's and the loader's credentials (PD-0077). It names no agent session as a holder.

Outside a window nobody can log in as the loader, whoever knows its last password. Between window 1 and window 2 the owner reviews the proposal
files, publishes, and starts no loader session.

**Which tool does the step (4a) registration (R6R-L1): none exists today.** The library call is `RealProvenanceStore.register(...)`
(`src/persistence/real_provenance_store.py`), with `reconcile` for a registration that reports UNKNOWN. R4b's qualification run opens no
connection, `real_tools/qualification.py:load_qualified` is the step (2) load, and R6 builds no command-line tool for step (4a). **R8's plan must name
a tool or R7/R8 builds one**; I flag it and do not choose. **TR6R-L1 (open):** an UNKNOWN registration can only be resolved by the loader, so a
window must stay open (or be reopened) until `reconcile` returns a definite answer. **Update 2026-11-14:** `loader_window` is that tool. Every UNKNOWN it
reports (a registration, a reconcile that finds nothing, a load whose outcome is not known) prints "THE LOADER WINDOW STAYS OPEN" and the `reconcile`
command to run; it retries nothing and closes nothing. Closing the window stays the owner's procedure (steps 5 to 7).

## 7. Evidence limits (design 1.2 rules 5.1, 5.3 (e), 5.4 and 7), for the owner's approval

* **The accepting side is first exercised at R8 step 1, on every path.** Phase 0 and Phase 2 passing on a clean REAL cluster, the first read of a
  REAL catalog by Phase 2's audit, and the runtime gate passing at each tool's first gated start, are not shown before. No cluster an agent builds
  can pass Phase 0: it refuses a data directory or socket directory under the repository root or the system temporary directory. I added no
  test-only relaxation of the preflight and **no REAL install in the reserved namespace**. The test kit does hold crafted `REAL`-kind installs (R3's
  kit fixture, and R6's `InstallerOnTestInstallTests`, which runs the installer's own `install_in_database` on a disposable database); their
  database names are outside the reserved namespace, so every tool refuses them as "kind and name disagree" (5.2), and they are not a bypass.
* **The development-cluster probe shows the refusal side only.** The cluster trusts its roles, so every attempt is `CONNECTED`; `CHALLENGED` and
  `REJECTED` are **not calibrated** there. They are calibrated by the opt-in test of section 8 if the owner runs it, otherwise at R8 step 1.
* **A wrong refusal comes after Phase 1.** A refusal in Phase 2, or at a tool's first gated start, comes after the database, the five roles and the
  gateway exist (they hold no content). The owner then waits for a reviewed fix and re-runs `check`, **or** drops and reinstalls, **or** approves SQL
  in the existing database (rule 7). **A wrong refusal is fixed by a reviewed change, never by a switch.** That nothing is used until the refusal
  is resolved is the owner's procedure; no tool enforces it. A Phase 1 failure leaves a partial install with no content and the same options.
  Re-running Phase 1 over a partial install is not claimed.
* **Grants are not re-read at a gated start** (5.4). Phase 2 and `check` audit them; a later `GRANT` by the superuser is not seen until the owner
  runs `check`. The settings and the two parameter privileges are read at every start.
* **What a runtime tool cannot see:** `pg_hba_file_rules` and `pg_authid` (so not whether a role has a password or what the file says), the hba
  rows, a password kept elsewhere under the owner's home, another process's environment, OS permissions. A passing preflight is a tripwire from the
  vantage of the process that ran it, at that moment. It does not show that no agent holds a password.
* **Whether a non-superuser may read what the runtime gate reads** (`pg_db_role_setting`, `has_parameter_privilege` for other roles and `public`,
  `SHOW listen_addresses`, `SHOW session_replication_role`) is now shown on the development cluster's PostgreSQL 17.11 by
  `test_postgres_real_preflight.FactsOfRuntimeToolTests` (the publisher role reads every catalog the gate needs). It is not shown on the real
  cluster; a tool that cannot read one refuses.
* **The loader while it cannot log in** is not covered by the LOGIN-keyed checks (section 3 D).
* **The existing test tooling and the environment-driven tests are outside the preflight and are not used on the real cluster.** On a shared cluster
  the superuser-driven test tooling could never run again (rule 3). Name tripwires (rule 6) refuse a cluster holding a `finweb_real*` database and a
  `FINWEB_PG_DATABASE` in the reserved namespace; the residual is a database named otherwise on the real cluster, which the credential rule stops.

## 8. Calibrating the classifier in the Fin-Web cloud (PD-0075 decision 2)

`tests/product/test_preflight_calibration.py` is **opt-in and skipped by default**. It is not run by the default suite or the PostgreSQL run, and I did
not run it. It runs in the owner's Fin-Web cloud environment (PostgreSQL 17.11, root), **after the R6 code is committed and pushed there**. It creates
its **own throwaway cluster** in a temporary directory under `/tmp`, with invented roles and passwords and no TCP, writes its own scram `pg_hba.conf`,
reads what libpq and the server say, and removes the cluster. It **calibrates only**: no gateway, no real tool, no REAL-scope content. **No real
credential goes to the cloud. Nothing on the Mac is needed.**

Run (in the cloud, repository checked out, `uv` available):

```
FINWEB_PREFLIGHT_CALIBRATION=1 \
FINWEB_CAL_PG_BIN=<directory holding initdb and pg_ctl>   `# optional; default: pg_config --bindir, else PATH` \
FINWEB_CAL_OS_USER=postgres                                `# optional; used only when running as root` \
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_preflight_calibration -v
```

(The `uv` flags are those of the Mac; in the cloud use whichever invocation runs the project's tests there.) PostgreSQL refuses to run as root, so
as root the test runs `initdb` and `pg_ctl` as `FINWEB_CAL_OS_USER` through `runuser` and hands it the temporary directory. It prints each message
it observed to standard error. It asserts: no password supplied is `CHALLENGED` for a role with a password, a role with none and a role never
created, in Pass A and Pass B; a `reject` row and a missing `replication` row are `REJECTED`; a wrong password is `CHALLENGED`; a missing socket is
`OTHER`; every required attempt of 5.3 (d) is `CHALLENGED` or `REJECTED`; Pass B sees a `PGPASSWORD` the caller holds (`CONNECTED`) and Pass A does
not; a trust server fails the tool's `require_auth=scram-sha-256` connection with `PF_REQUIRE_AUTH`. **If any message differs from the patterns the
test fails and prints it; the patterns are then corrected by a reviewed change, never by loosening the test.** A pass shows the classifier against
PostgreSQL 17.11's wording on that platform; it does not exercise the installer's accepting side. **The owner's cloud run of the first eight tests
passed (8/8; STATUS.md, "Cloud calibration").**

**The `withdraw` `!password` tests (PD-0076 E; added after that run).** Five more tests in the same module, under the same variable, with the same
command above (the module now has 13 tests; the first eight are unchanged). They use the same throwaway cluster and invented roles and passwords
only (one more invented role, `cal_md5`, created and dropped by the test). **I have not run them; they are skipped without
`FINWEB_PREFLIGHT_CALIBRATION=1` and so do not run in the Mac suites.** To run only the new ones in the cloud:

```
FINWEB_PREFLIGHT_CALIBRATION=1 [FINWEB_CAL_PG_BIN=...] [FINWEB_CAL_OS_USER=postgres] \
uv run ... python -m unittest -v \
  tests.product.test_preflight_calibration.ScramOnlyCalibration.test_withdraw_demand_is_the_negated_cleartext_password_method \
  tests.product.test_preflight_calibration.ScramOnlyCalibration.test_withdraw_refuses_a_cleartext_password_server_and_the_password_is_not_sent \
  tests.product.test_preflight_calibration.ScramOnlyCalibration.test_the_withdraw_connection_sends_no_password_message_to_a_server_that_asks_for_cleartext \
  tests.product.test_preflight_calibration.ScramOnlyCalibration.test_withdraw_connects_to_a_scram_server_with_the_right_password \
  tests.product.test_preflight_calibration.ScramOnlyCalibration.test_contrast_md5_and_trust_what_the_negated_demand_allows_and_what_the_scram_demand_would_stop
```

They show: (1) with `pg_hba.conf` using `password`, the withdraw connection is refused by libpq (`PF_REQUIRE_AUTH`), the invented password is not in the
error, and a stand-in server on a Unix socket in the temporary directory, which asks for a cleartext password and records every byte that follows,
receives **no PasswordMessage** (at most a Terminate), while the control with no demand does send one; (2) against a scram server the withdraw
connection with the right invented password connects, and a wrong password is refused by the server (`CHALLENGED`) and not by the demand; (3) as
recorded contrast, against an md5 server (a role with an MD5 verifier) `!password` **allows** the connection, `scram-sha-256` refuses it, and against a
trust server `!password` allows it (nothing is asked, so nothing is sent), `scram-sha-256` refuses it. Part (3) is the evidence of what `!password`
does not stop. The test prints each observed message to standard error. If libpq's behaviour differs from these assertions the test fails and the
difference is reported; the constant is then reconsidered by the owner, not adjusted here.

## 9. Owner procedures no tool enforces

* Set passwords with psql's `\password`, never a literal `PASSWORD '...'` statement (a literal can reach the client history and the server log).
* Keep no passfile or service entry for any real role, and unset `PGPASSWORD`. Pass S and Pass B check the stores libpq reads; they cannot see a
  password in another file, another process's environment, shell history, scrollback, a password manager export or a backup.
* Keep `log_statement = 'none'` while passwords are set. The installer reads it and refuses otherwise; a setting read now says nothing about the
  past, and the log file's own permissions are the owner's.
* Optionally count `PASSWORD '` lines in `~/.psql_history`; a zero proves nothing about other editors.
* Hold the superuser password alone; give it to no agent session and no tool an agent runs. The same for the publisher and executor passwords
  (choice B).
* The owner types the loader password at the tool's prompt in the owner's own terminal, for each window (PD-0077); it goes to no agent session, not
  in chat, and never to a cloud session. At each window's close: set `NOLOGIN`, end every open loader session, record the times in the HG4 package,
  which states that the owner held both credentials (section 6).
* Run `initdb` and `pg_ctl` as the dedicated macOS user, and record the owners and modes of the data and socket directories before Phase 1
  (section 4 item 0).
* Do not use the real database, publish, or start a tool against it between a Phase 2 refusal and its resolution.

## 10. After a later migration; test tooling

* **Re-run the revoke after any later migration.** A new routine gets PUBLIC's default `EXECUTE`. The audit then reports `RW_AUDIT_PRIVILEGE_DIFFERS`
  until `REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA "finweb" FROM PUBLIC` is re-run (the first statement of `real_roles.grant_statements`). FF1-C10
  shows this on a disposable TEST install: the audit refuses the new routine, and is clean after the revoke. The owner runs `real_install check`
  after the migration and the revoke.
* **A change to the gateway SQL after R3 reopens R3's review** and re-runs the catalog audit before R8. R6 changed no gateway SQL.
* **The test tooling is never pointed at the real cluster** (`guarded_pg_provision.py`, `guarded_pg_runner.py`, `dev_env.py`, the
  environment-driven tests). The tripwires of rule 6 are fences against error, not controls against intent.

## 11. Carried residuals

* **PD-0074 O5-in-Python.** O5 (the sidecar check) runs in Python at publish; no SQL equivalent. Carried as R4b left it.
* **R2 L-3.** An open loader session after `NOLOGIN` stays connected. The registry refuses it, but the session still reads `md_file` and
  `md_release` and holds `INSERT`. The owner ends it (`pg_terminate_backend`) as part of each window's close (section 6); no tool does.
* **TR6R-L1 (still open, neither PD-0076 nor PD-0077 decides it).** An UNKNOWN step (4a) registration can only be resolved by the loader, so it falls inside
  window 2 (section 6): window 2 stays open, or is reopened, until `reconcile` returns a definite answer.
* **R6R-L1 (still open, neither PD-0076 nor PD-0077 decides it).** No tool does the step (4a) registration (section 6). R8's plan must name one or
  build one, and **that tool must take its password from the owner's terminal prompt** (PD-0077). The same holds for a tool for the step (2) load.
* **The route of the loader password** is settled by PD-0077: the owner's terminal prompt, for each window; no agent session holds it. An
  agent-held route would need a new owner decision (it would also contradict PD-0076 B and design 1.2 rule 4 as the only available channel is chat,
  section 3 B).
* **R6R-L2.** With `nologin` at creation and two windows, no run checks the loader while it can log in unless the owner runs `check` inside the
  window (section 3 D).
* **Identity seed.** No tool writes the seed file from the qualification registry (section 5 item 6). *Update 2026-11-14: `real_tools.qualify_run` does; R6R-L1 and
  TR6R-L1 above are answered by `real_tools.loader_window` (section 14), whose gaps G1 to G10 are open.*
* **Loopback TCP.** The runtime probe tries the Unix socket only; the gate reads `SHOW listen_addresses` and refuses unless it is empty.

## 12. Exit checklist (design 7.1, R6 row)

| Exit item | Where |
|---|---|
| Inventory written (actual `pg_hba.conf`, superuser/trust paths, `~/.pgpass`/service names only, data-directory owner; unknown actors HOLD) | `reviews/CP7_F1_R6_INVENTORY.md`; section 1 |
| Install plan ready for the owner | this file |
| The publisher's authentication | section 4 item 4 (2.5) |
| The superuser-password holder | section 4 item 4: the owner alone |
| The account role (PD-0078): its grants, its password holder, the checks that cover it | status paragraph; section 4 items 4 to 6 (exactly `real_roles.ACCOUNT_TABLES` plus schema `USAGE`; the owner alone types the password at the launcher's prompt); Phase 2, the gate and the catalog audit judge it like the other four |
| Which `CONNECT` option applies | section 3 A (DECIDED: own cluster, dedicated macOS user; the installer's revoke of PUBLIC's `CONNECT`) |
| The owner procedures | sections 4, 9 |
| The loader's holder and the reads and writes that holder gets inside a window | section 3 B (DECIDED, PD-0076 B narrowed by PD-0077: the owner alone types the loader password at the tool's prompt, for each window; the HG4 package states that the owner held both credentials) |
| R8's loader sequence, one window or two | sections 3 C, 6 (DECIDED: two windows) |
| Phase 1 `LOGIN` or `NOLOGIN`; the LOGIN-keyed checks do not cover a `NOLOGIN` loader | section 3 D (DECIDED: `nologin`, `check` per window) |
| The owner's `NOLOGIN` and `LOGIN` steps | section 6 |
| The revoke re-run after a later migration | section 10 |
| Existing test tooling outside the preflight and not used on the real cluster | sections 7, 10 |
| Evidence limits of rules 5.1, 5.3 (e), 5.4, 7 | section 7 |
| Wrong refusal after Phase 1; the owner's three options; partial Phase 1 | section 7 |
| Grants audited by Phase 2 and `--check`, not at each gated start | section 7 |
| `withdraw` and `require_auth`: the three options and the preference | section 3 E (DECIDED: `!password`; code changed; server test in section 8) |
| The five `!password` server tests have passed in the Fin-Web cloud before R8 step 1 (PD-0076 consequence 4; TR6C-2) | section 5 precondition; section 8; STATUS.md records the run |
| The preflight gate is a separate item in R6's independent review | the review brief should list it separately |

## 13. Engineering decisions the contracts did not cover

1. `withdraw` against a database with no readable install-kind row refuses and writes nothing (`PF_NO_KIND_ROW`): there is no real gateway to
   withdraw from. A name and kind that disagree do not stop a withdrawal, since `withdraw` only narrows.
2. The `Facts` record, and a field that is `None` meaning "not inspected": the decision refuses where the field is required. A coverage check
   (`PF_PROBE_NOT_RUN`) refuses if the prober skipped any required attempt.
3. The outcome patterns: `REJECTED` = `pg_hba.conf rejects ... connection` or `no pg_hba.conf entry for ... host`; `CHALLENGED` =
   `password authentication failed for user`, `no password supplied` or `SASL authentication failed`. Anything else is `OTHER`. These are libpq and
   server wording, not quoted in the manual pages the design cites; section 8 calibrates them.
4. The identity seed lives in `real_tools` (the persistence layer may not import adapters), is checked against the proposal's digest before a
   connection is opened. Because the identity tables lack the share-class FIGI, composite FIGI and identifier columns that the digest covers, those
   cannot be read back from the database. After the writes the tool reads back every row of the seed, in the same transaction, and requires it to
   equal the seed's row **on the stored columns**; a difference rolls the seed back (`RW_SEED_CONFLICT`). The columns the tables lack are held to the
   proposal's digest only through the seed file.
5. `_install_gateway_body` refuses a database in the reserved namespace only when installing a TEST gateway, so the same shared function serves
   the REAL installer. The reserved prefix literal is defined once, in `connection.py`.
6. The probe's child process sends no statement: it opens a libpq connection with `psycopg.pq.PGconn.connect` and closes it.
7. Installer connections use `require_auth=scram-sha-256`, as do the publish/renew and seed connections to a REAL target.

## 14. R8 command inventory (added 2026-11-14, before R8 starts)

Every step of the design 7.1 R8 row (1) to (7) and of section 5 items 1 to 7 above, with the exact command, who runs it and with which credential, what it
reads and writes, and whether the REAL preflight gate runs at its start. Written from the code at this commit; **nothing here has been run against a
real cluster**. Run each Python command from the repository root as `PYTHONPATH=src <python 3.12 of the project environment> -m <module> ...`; `DIR/.s.PGSQL.PORT`
is the real cluster's socket. "Prompt" means the password is typed at `real_preflight.terminal_prompt` (PD-0077); no tool has any other route. "Gate" is the
runtime preflight of design 1.2 rule 5.1 (`publish`, `renew`, `serve`, `admit`; never `withdraw`); every tool that connects (`loader_window`, `identity_seed`, `publish`, `renew`, `withdraw`, the launcher, the probe) also runs the prompt-route
check first, `withdraw` included; the offline tools `qualify_run` and `r8_files` open no connection and ask no password, so they run neither.

| Step | Command (owner, own terminal) | Role and credential | Reads | Writes | Gate |
|---|---|---|---|---|---|
| **(1)** = 5.1 | `initdb ...`, `pg_ctl ...` as the cluster's macOS user (section 4 items 0 to 3) | OS user of the cluster; superuser password set by `--pwprompt` | nothing of ours | the cluster, `pg_hba.conf`, `postgresql.conf` | no tool of ours |
| (1) = 5.2 | `python -m persistence.real_install phase0 --socket DIR/.s.PGSQL.PORT --user SUPERUSER` | superuser; prompt | catalogs, `pg_hba`, settings, stored-credential scan | nothing | the installer's own checks (Phase 0) |
| (1) = 5.3 | `python -m persistence.real_install phase1 --socket ... --user SUPERUSER --loader-login nologin` | superuser; prompt | as Phase 0 | the database, five roles (no passwords), schema, migrations, gateway, kind row `REAL` | Phase 0 first |
| (1) = 5.4 | psql as superuser: `\password finweb_real_publisher`, `\password finweb_real_executor`, `\password finweb_real_account` | superuser | | the three passwords | no tool of ours |
| (1) = 5.5 | `python -m persistence.real_install phase2 --socket ... --user SUPERUSER` | superuser; prompt | every check, catalog audit as REAL | nothing | the installer's own checks |
| **(2) a** | `python -m real_tools.qualify_run --store-root data/marketdata --release-name NAME --file 066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb --file b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc --file 4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef --sidecar S1 --sidecar S2 --sidecar S3 --registered-check 4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef --proposal-out P --seed-out F` | none: no connection, no prompt | the store's three files and manifests, `SOURCES.json`, the three sidecars | two NEW files, `P` (proposal) and `F` (identity seed); never overwrites | none |
| (2) b = 5.6 | `python -m real_tools.identity_seed --socket ... --user SUPERUSER --seed-file F --proposal P` | superuser; prompt | `F`, `P` | `issuer`, `instrument`, `listing` rows, as the schema owner, one transaction | prompt-route check only. **Must precede window 1's load** (G6) |
| (2) c | owner: `ALTER ROLE finweb_real_loader LOGIN`; `\password finweb_real_loader`; `python -m persistence.real_install check --socket ... --user SUPERUSER` (section 6 steps 1 to 3) | superuser; prompt | catalogs | the login state and a fresh loader password | installer checks |
| (2) d | `python -m real_tools.loader_window load --socket DIR/.s.PGSQL.PORT --database finweb_real --user finweb_real_loader --schema finweb --store-root data/marketdata --release-name NAME --file ... (as in a) --sidecar S1 --sidecar S2 --sidecar S3 --registered-check ... --proposal P` | **loader**; prompt (the owner types it, window 1) | the store, sidecars, `P` | the 13 `md_*` tables (release, 3 files, rows) and the UNBOUND candidate in the registry | **no** (see "Gate question") |
| (2) e | owner: `ALTER ROLE finweb_real_loader NOLOGIN`; end loader sessions; record the times (section 6 steps 5 to 7) | superuser | `pg_stat_activity` | | no tool |
| **(3)** | the owner reads `P` and the qualify listing (the 6.3 table, O5, "needs review" lines) | none | `P` | nothing | no tool; reading is the step |
| (4) pre | `python -m real_tools.r8_files evidence --alphavantage-pd PD-NNNN --alphavantage-commit GIT40 --alphavantage-sha DOC64 --openfigi-pd ... --openfigi-commit ... --openfigi-sha ... --calendar-pd ... --calendar-commit ... --calendar-sha ... --out E` (one triple per entry; see "Evidence citations") | none: no connection, no prompt | nothing | one NEW file `E` | none |
| **(4)** | `python -m persistence.real_workspace_store --socket ... --database finweb_real --user finweb_real_publisher --schema finweb publish --proposal P --sidecar S1 --sidecar S2 --sidecar S3 --valid-until 2027-08-31T16:00:00Z --evidence-file E --actor ACTOR --pd PD-NNNN --commit GIT40 --sha DOC64` | **publisher**; prompt | `P`, sidecars, `E` | the snapshot, history and head rows (one transaction) | **gated** (`publish`) |
| **(4a)** | owner: `ALTER ROLE ... LOGIN`, `\password`, `real_install check` (window 2); then `python -m real_tools.loader_window register-bound` with the same arguments as (2) d; if it exits 4: `... reconcile --candidate bound ...` in the same window until it answers; then `NOLOGIN`, end sessions, record times | **loader**; prompt | the store, sidecars, `P` | the BOUND candidate (registry) | **no** |
| (5) pre | `python -m real_tools.r8_files contexts --store-root data/marketdata --release-name NAME --file ... --sidecar ... --registered-check ... --proposal P --generation N --out C` (`N` from the publish output) | none: no connection, no prompt | the store, sidecars, `P` | one NEW file `C`, mode 0600 | none |
| **(5)** | `python -m web_api.real_launcher --socket ... --database finweb_real --user finweb_real_executor --schema finweb --account-user finweb_real_account --contexts-file C [--port 8004]`, then the real-mode web screen | executor and account; two prompts | `C`; the lease-checked reads | the roots a create makes | **gated** (`serve`) |
| **(6)** | admission probe: `python -m real_tools.admission_probe --socket ... --database finweb_real --user finweb_real_executor --schema finweb --purpose ARCHIVE_EXPORT --owner-id UUID (from psql, G11) --root-id UUID --context HASH --generation N`. Withdraw: `... real_workspace_store ... --user finweb_real_publisher ... withdraw --context HASH --generation N --actor ACTOR --pd PD-NNNN --commit GIT40 --sha DOC64`. Renew: `... renew --context HASH --generation N --valid-until ... --evidence-file E --actor ... --pd ... --commit ... --sha ...` | executor (probe); publisher (withdraw, renew); prompt each | the root and context named | probe: nothing (rolls back); withdraw, renew: a new generation | probe **gated** (`admit`); renew **gated**; withdraw **not gated** |
| **(7)** | the HG4 package (skill `human-gate-package`) | none | all of the above | `reviews/gates/HG4_GATE_REVIEW.md` | no tool |

**`loader_window` subcommands.** All four take `--socket --database --user --schema --store-root --release-name --file (repeat) [--sidecar (repeat)]
[--registered-check (repeat)] --proposal [--lock-timeout-ms N]`; `reconcile` also takes `--candidate {unbound,bound}`. `load` projects the release and
registers the UNBOUND candidate (idempotent: an identical re-run says "already loaded" and adds nothing). `register-bound` registers the candidate bound to
the published context: refused before a publish (`RW_PROV_INPUT_MISSING`), done after, and an identical re-run reconciles. `reconcile` settles an UNKNOWN
registration by its operation id (the operation id is a function of the context bytes). `check` prints the session's role facts, whether the release is
loaded and whether each candidate is registered, and writes nothing. Exit status is the publisher tool's: 0 done, 2 refused, 4 unknown, 5 lock timeout.
**The loader loads only what was reviewed**: each command rebuilds the qualification from its inputs and refuses unless the proposal bytes equal `P`.

**The gate question: decided by the PM 2026-11-14. The loader window runs NO preflight gate.** The design enumerates the gated commands: 1.2 rule 5.1's table
lists five runners (installer, `publish`/`renew`, `withdraw`, launcher, probe); 7.1's R6 row says the gate "applies to `publish`, `renew`, the launcher and the
admission probe, and never to `withdraw`"; its R8 row repeats the four; 3.3 item 1 and section 6 above give the loader's window its own check, the owner's
`real_install check` inside each window (R6R-L2, 5.3 (g)). Rule 5.2's by-command table leaves an unlisted command ungated (`real_preflight.command_plan`
returns a proceed plan with no preflight), and `real_tool_gate.start_gate` could not serve the loader in any case: it reads `rw_install_info()`, on which the
loader holds no `EXECUTE` (3.3, the narrowing). The tool therefore runs the prompt-route check, uses `scram-sha-256` from the first connection for a
real name, refuses a real name unless the user is `finweb_real_loader` and the proposal's scope is `REAL` (and the reverse for any other name), and refuses a
session that is not the named role logged in as itself or that is a superuser. The absence of a gate is a static record, pinned in
`test_real_preflight_static` (the loader tool is in `TOOLS` and `LOADER_STATEMENTS`, and no gate call appears in it).

**Round 2 (2026-11-14), the code-side blockers.** Two more offline tools, both opening no connection and taking no password, writing one NEW file by exclusive
create (an existing file is never overwritten; refused before anything is built):

* `python -m real_tools.r8_files evidence --alphavantage-pd ... --alphavantage-commit ... --alphavantage-sha ... --openfigi-pd ... (and -commit, -sha)
  --calendar-pd ... (and -commit, -sha) --out E` writes the publish's expiry-evidence file (G9): `LEASE_TERM` `alphavantage.us` `term_end_not_after`
  2027-10-01T00:00:00Z; `NOT_ASSESSED` `openfigi` and `calendar.manual`; **each entry cites its own decision** (TR8T-M-2). **The publish's own `--pd --commit --sha`
  are a different record** (the decision to publish) and go to `real_workspace_store publish`, not here.
* **Evidence citations (design 3.1 "HG4 expiry basis entries", E14).** `alphavantage.us` `LEASE_TERM`: the design's table says "PD-0066 decision 5, the only reading
  there is" (the term reading; PD-0068 answer 4 adopted the entry and its date, and PD-0072 adds only that the publish may cite its record for the pinned start). `openfigi`
  and `calendar.manual` `NOT_ASSESSED`: E14 says the cited decision "states that no term evidence is recorded for this source"; the design names **no record** for
  these two (its table gives a description only). **Decided by the PM 2026-11-14: both cite PD-0068** (answer 4 is the owner's decision that made them `NOT_ASSESSED`, stating no term evidence or reading
  for either; the reviewer confirmed this meets E14). The tool takes all three triples and chooses none; the owner supplies the commit and
  the file's SHA-256 at it.
* **`valid_until` of step (4)** is **2027-08-31T16:00:00Z, which is 2027-09-01 00:00 Asia/Shanghai** (PD-0068 answer 4 "Keep 2027-09-01"; design 3.1; PD-0072 item 5).
  `publish --valid-until` reads the value as UTC (`parse_utc`), so the Shanghai instant is written out in UTC; `2027-09-01T00:00:00Z` would be eight hours late.
* `python -m real_tools.r8_files contexts --store-root data/marketdata --release-name NAME --file ... (as in (2) a) --sidecar S1 --sidecar S2 --sidecar S3
  --registered-check ... --proposal P --generation N --out C` writes the launcher's contexts file (G7), mode 0600, no password in it. It rebuilds the
  qualification and refuses unless its proposal bytes equal `P`. **`--generation N` is the one argument that comes from the publish output**: the number in
  "published context ... at generation N", copied by the owner. Run after (4), before (5).
* Step (2) b order, corrected: (2) b needs `F` and `P` (both from (2) a) and must be done after (2) a and before (2) d, the first load (G6). It does not depend on
  (2) c, which only opens window 1.

**Gaps found, with their status after round 2.**

* **G1. The three sidecars. CLOSED 2026-11-14:** written by the main session under `data/marketdata/sidecars/` (AV and OpenFIGI cite PD-0066 at `10ce97b`, the NYSE
  calendar cites PD-0038 at `b336aa2`; reviewer-confirmed). The original note follows. (Call, fields and where they live: the engineer's round-2 report.) `real_sidecar.encode_sidecar` is a library function; design 6.1 says "the main session writes the
  records" before the qualification run, outside `data/marketdata/files/`. Each needs a decision-record triple (PD id, commit, doc SHA-256 at that commit); the
  NYSE calendar's must cite the record that registered it (HG2 condition 4). Nothing is written and no command exists. `qualify_run` and `loader_window` (REAL)
  refuse (`RW_O5_FAILED`) until all three exist.
* **G2. `SOURCES.json` notes. RESOLVED by the owner ("Shorten notes").** The `alphavantage.us` notes were 1687 bytes against the registry's 1024 (Python
  `real_provenance._terms_check_shape`; SQL `real_provenance_v1.sql` line 193 inside `rwp_validate_bundle`); the main session shortened them to 953 bytes. Re-checked
  2026-11-14: an offline dry run (the three real files, in-memory invented sidecar bytes, nothing written) gives the unbound and the bound candidate, each with three
  members, and `real_provenance.validate_bundle` accepts both. In SQL, `test_postgres_real_provenance.RealSourceRecordsFitTheRegistryTests` reads the three tracked
  `SOURCES.json` terms checks, builds REAL-scope candidates from them and calls `rwp_validate_bundle` by value (a READ ONLY transaction on a TEST install, nothing stored):
  no shape error and no failed code; the same records with 1025-byte notes are refused `RW_PROV_SHAPE` by both. Not run: a registration of the real candidate in a REAL install.
* **G3. The release files are on disk and agree with the 6.3 table.** The payload hashes of `AAPL_compact.csv` and `AAPL_UW.json` and their manifest hashes equal the
  table; the NYSE payload is `4f21b26b...72ef` (manifest `b08c929a...0177`); `FileStore.index()` has 15 entries; the engine builds the three-member release with no issue and no
  exception (an offline dry run, with invented sidecar bytes held in memory only and nothing written or stored). There is **no release definition file**:
  the release is cut at qualification from the `--file` list and `--release-name`, and the name enters the release id and so the context (an owner choice).
* **G4. The registry refused all three real manifests. FIXED in code (PM: a registry defect).** The registry read a v1 manifest with the strict v2 reader, which refused
  the three on-disk manifests (`RW_PROV_SHAPE`): their request keys (`outputsize`; `idType`, `idValue`, `exchCode`, `marketSecDes`; `origin`) are not in
  `acquisition.PUBLIC_PARAMETER_KEYS` and the Alpha Vantage `adjustment_anchor` ("TIME_SERIES_DAILY as returned; label unverified") is not an identifier. Now
  `manifest_v2.read_registry_manifest_metadata` (called by `real_provenance`) accepts a v1 manifest whose request keys are in `V1_REQUEST_KEYS` or in `PUBLIC_PARAMETER_KEYS` (what the strict reader already accepted; `V1_REQUEST_KEYS` is 20 keys, derived from
  every `Fetched(request=...)` and `register-file` in `marketdata_tools.download`), once each, with printable text values, and a free-text anchor; any key outside the
  list (`apikey`, `token`, anything new), any value or anchor that looks like a key, token, password, credential, query string (`?` `&` `#` `;` then `name=`), a `...key...=` pair or URL
  userinfo (`user:pw@host`), and everything else of the v2 shape stays refused (TR8T-L-4; a pattern, not a proof: the 15 manifests still pass). `PUBLIC_PARAMETER_KEYS` is NOT widened and no manifest byte changed. All 15 manifests in the store were read (read-only) and are accepted; the test
  (`test_real_r8_inputs`) uses invented v1 manifests because the real ones are vendor-folder files a test may not read without the vendor gate. The SQL checks the key set only.
* **G5. The NYSE calendar needs `--registered-check`.** Without it the listing marks it `NOT_CONFIRMED` and the run says "needs review" (information, no gate).
* **G6. Ordering: the identity seed precedes the load.** The observation tables reference `listing`; section 5 item 6 said "before the first real create".
* **G7. The launcher's contexts file `C`. DONE:** `r8_files contexts` (above). The generation is copied by the owner from the publish output.
* **G8. The launcher's `world_inputs`. DONE.** The identity (AAPL on XNAS, USD; `uuid5` ids in registration order), the market conventions (now a function of the
  release's calendars: `worlds.market_conventions_for`) and option B's policy live in `real_service/real_identity.py`, imported by both `real_tools.real_inputs` and
  `real_launcher.build` (`world_inputs=real_world_inputs()`). `test_real_r8_inputs` shows the proposal's identity digest equals the digest of the launcher's
  resolver, and the convention digest of the function form equals that of the conventions built from the same calendars. The test scopes' creates are unchanged.
  Not shown: a full REAL-scope create (no real cluster, no real password).
* **G9. The publish inputs. PARTLY DONE:** `r8_files evidence` writes `E`. The decision record for the publish itself and the issuer `ACTOR` remain the owner's
  inputs to `publish` (`--actor --pd --commit --sha`); no file exists for them and none is needed.
* **G11. The probe's `--owner-id` (TR8T-L-5). Decided by the PM 2026-11-14:** the owner reads it in psql as the superuser, read-only:
  `SELECT user_id, username FROM finweb.web_identity WHERE username = '<the account>';` (never `password_hash`); reviewer-confirmed as the id `owner_of` returns. The original note follows. The owner id is the web account's user id (the id `owner_of` resolves from the session, and the
  `owner` in the create command); the real-mode routes and `web/` expose no owner id, and no tool prints it. The `--root-id` is the id of a root the create returned
  (listed per owner). Options: the superuser reads the user id from the account table in the owner's own terminal, or a read-only print is added to a tool. Neither is
  done here; the PM decides.
* **G10. A test-scope name takes any named role** (the install kind cannot be read as the loader); only a real name pins `finweb_real_loader`. The database's own grants
  stop any other role, which the PG test shows.
