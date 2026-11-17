# PD-0076 — R6 install plan: the owner's choices A to E

**Status:** accepted
**Date:** 2026-11-01
**Decided by:** the designated human product owner, in this chat ("Decide A–E now").
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `implementation/CP7_F1_R6_INSTALL_PLAN.md` section 3 (A to E), sections 5, 6 and 9, and R8 step 1, which
  follows the approved plan;
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 1.2 rules 3 and 4, 3.3 items 1 and 3, 5.1, 5.3 (g), 8.1 PM
  item (vi), and the R6 and R8 rows of 7.1;
- PD-0066 decision 7 (withdraw), PD-0070 decision 1 (loader off between loads);
- `reviews/CP7_F1_R6_INVENTORY.md`.

The plan was committed at `4d7a6d1`. The options below are as shown to the owner. Each is quoted
verbatim, with its recommendation marker.

## A — cluster placement and data-directory owner

Question: "A. Where does the real database's cluster live, and which macOS user owns its data directory?"

- "Own cluster, new OS user (Recommended)": "A cluster of its own, outside the project and $TMPDIR, owned by a separate macOS user that agent sessions don't run as. You create that user and run initdb/pg_ctl/the installer as it. Strongest: agents can't edit its pg_hba.conf or restart it with trust."
- "Own cluster, your OS user": "A cluster of its own, owned by <os-user>. Simpler, but any agent session (same OS user) could read or edit its pg_hba.conf and restart it. Recorded as a limit in the HG4 package."
- "Shared dev cluster": "Put it on the Homebrew dev cluster and revoke PUBLIC CONNECT. Not recommended: that cluster trusts every role, so its pg_hba.conf would have to change and the test kits could never run there again."

**Answer, verbatim:** "Own cluster, new OS user (Recommended)"

## B — who holds the executor and loader credentials

Question: "B. Who holds the executor and loader passwords?"

- "You alone, both (Recommended)": "You type each password at the prompt of the tool you run. No agent session ever holds either."
- "You executor, agent loader": "You hold the executor. A named agent session may be given the loader password for a load window only; inside it, it can read what the loader's list allows, including the stored payload bytes."
- "Agent may hold both": "A named agent session may be given the executor password for the R8 run and the loader password inside windows. Recorded as the limit of design rule 4."

**Answer, verbatim:** "You executor, agent loader"

This is not the recommended option.

## C — loader login windows during R8

Question: "C. Loader login windows during R8: one or two?"

- "Two windows (Recommended)": "Loader is NOLOGIN after the qualification load, stays off while you review the proposal files, then LOGIN again only for the step (4a) registration, then NOLOGIN. Two extra steps for you; matches PD-0070 'off between loads'."
- "One window": "Loader keeps LOGIN from the qualification load through the step (4a) registration. Fewer steps, but the loader's reads stay open during your review."

**Answer, verbatim:** "Two windows (Recommended)"

## D — Phase 1 creates the loader `LOGIN` or `NOLOGIN`

Question: "D. Does the installer's Phase 1 create the loader able to log in?"

- "NOLOGIN + check per window (Recommended)": "Nobody can log in as the loader until you open the first window. The login-keyed checks don't cover it while it can't log in, so you run 'real_install check' inside each window after setting LOGIN and its password."
- "LOGIN, no password yet": "Created LOGIN with no password, so scram refuses it until you set one; Phase 2 covers it. Between creation and your \password it is a LOGIN role with no verifier."

**Answer, verbatim:** "NOLOGIN + check per window (Recommended)"

## E — the `withdraw` connection's `require_auth`

Question: "E. How strict is withdraw about the server's login method? (withdraw is never blocked by the preflight; this only decides whether it will send your publisher password to a server that asks for it in plain text.)"

- "Refuse plaintext (!password) (Recommended)": "withdraw refuses only a server that asks for a cleartext password, so it never sends your publisher password in the clear to an impostor on the socket. A scram-only server never asks for that, so a normal withdrawal is never stopped. Note: libpq accepts the setting; its behaviour against a server is not yet tested."
- "Require scram-sha-256": "withdraw connects only if the server uses scram. Closes the impostor case too, but is one more thing that could stop a withdrawal."
- "None (as built)": "Nothing can stop a withdrawal on authentication grounds, but it would answer a cleartext-password request from whatever is on the socket."

**Answer, verbatim:** "Refuse plaintext (!password) (Recommended)"

## Consequences

1. **A.** The real cluster's data directory, `pg_hba.conf` and socket directory belong to a dedicated macOS
   user that agent sessions do not run as. The owner creates that user and runs `initdb`, `pg_ctl`, the
   installer and the identity seed as the appropriate user. What that user's permissions leave open to
   `<os-user>` is the remaining limit, for example the socket directory. The plan states it, and R8
   step 1 checks it.
2. **B.**
   - **Executor:** the owner alone.
   - **Loader:** a named agent session may be given the loader password **for a load window only**. This is
     the recorded limit of design 1.2 rule 4 for the loader. Inside a window that session can read what the
     loader's list allows: `md_file`, `md_release`, and, through the registry's get function, the payload
     bytes of every registered context (design 3.3; for the HG4 context, the Alpha Vantage closes, the
     OpenFIGI file and the NYSE calendar file).
   - The password reaches the agent by a prompt, never by a file or the environment.
   - The HG4 package states this limit and names the session that held the loader credential in each window.
   - The vendor payloads stay internal-use (PD-0027/PD-0028); this changes nothing about the cloud. The loader
     credential never goes to a cloud session.
3. **C and D, together.**
   - Phase 1 runs `phase1 --loader-login nologin`.
   - Window 1 is the qualification load, R8 step (2). Window 2 is the step (4a) registration.
   - In each window the owner sets the loader `LOGIN`, sets a fresh password with `\password`, runs
     `real_install check` (which is read-only), and sets `NOLOGIN` after the load or registration. Window 2
     opens only after the publish.
   - `NOLOGIN` does not end a session that is already open (R2 L-3). The owner ends any open loader
     session, or waits for it to end, before relying on the window being closed.
   - With `NOLOGIN` at creation and two windows, Phase 2 never checks the loader in its login-capable state
     (R6R-L2, 5.3 (g)). The per-window `check` is the mitigation, and it is an owner procedure that no tool
     enforces.
4. **E.**
   - `real_preflight.WITHDRAW_REQUIRE_AUTH` changes from `None` to `"!password"`. That is a reviewed code
     change, and it is not made by this record.
   - Its behaviour against a server is to be shown by a test before R8:
     - a server that asks for a cleartext password is refused;
     - a scram server is not.
   - The cloud calibration environment can run such a test.
5. **Still open, not decided here:**
   - R6R-L1: no tool performs the step (4a) registration. R8's plan must name one or build one.
   - TR6R-L1: an UNKNOWN registration, which only the loader can resolve, falls inside window 2.
