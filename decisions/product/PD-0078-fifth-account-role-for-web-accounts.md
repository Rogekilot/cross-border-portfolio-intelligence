# PD-0078 — A fifth `account` role holds the real database's web accounts

**Status:** accepted
**Date:** 2026-11-07
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `implementation/CP7_F1_REAL_PATH_DESIGN.md`:
  - the R7 row of 7.1, its D-3 exit statement (conformance R2-L4, R3C-L3, R3R-L3);
  - 1.2 (install rule, roles);
- `implementation/CP7_F1_R6_INSTALL_PLAN.md` (roles, credential holders, Phase 1 and Phase 2, the per-window checks);
- [PD-0076](PD-0076-r6-install-plan-choices-a-to-e.md) and [PD-0077](PD-0077-loader-password-typed-by-owner-only.md);
- `src/persistence/real_roles.py`, `real_install.py`, `real_preflight.py` and `real_catalog_audit.py`.

## Context

At R7 the engineer reported, and `tests/product/test_postgres_real_mode.py` showed on a `TEST` install (`Ran 15 tests` / `OK`, 2026-11-07), that **the real-mode web app cannot sign in even one user over a `REAL` install.**
- A registration writes only `app_user`, `web_identity`, `web_session` and `web_auth_rate`. These are account rows, not economic rows: no portfolio, account or ledger row is written, so nothing is fenced.
- None of the installer's four roles (owner, executor, loader, publisher) may write those tables. `real_roles.EXECUTOR_TABLES` gives the executor only the economic and rooted tables (the R3 M-1 rule). The identity seed of R6 covers `issuer`, `instrument` and `listing` only.

Without a decision, two-user isolation would have become declared deviation D-3.

## Decision

Question asked, verbatim:

> Over a real install the web app can't sign in even one user: none of the four planned roles (owner, executor, loader, publisher) may write the account tables (users, logins, sessions, sign-up rate limit). None of these tables holds money or ledger data. How should the real database hold web accounts?

Options shown, verbatim:
- **"Fifth account role (Recommended)"**: "Add an 'account' role to the install plan and installer. It may write only those four tables, and nothing economic. You set its password at the prompt like the others; the safety check and the catalog audit cover it. Two users can then be shown isolated at R8. Costs a fix round in R7."
- **"Executor gets the grants"**: "No new role: the executor also writes the four account tables. Simpler, but it widens the role that runs the gateway, against the R3 rule that the executor writes only fenced, rooted tables. Not recommended."
- **"Owner only; accept D-3"**: "No sign-up in real mode: you seed your own account once, and a small role writes only sessions and the rate limit. Only one user, so two-user isolation is not shown over real data; D-3 is recorded as an accepted limit in the HG4 package."
- **"Decide before R8"**: "Finish R7 with sign-up refused over a real install, and decide this later. R8 can't start until it is decided."

**Answer, verbatim:** "Fifth account role (Recommended)"

## Consequences

1. **A fifth role, `account`.** The real installer creates it in Phase 1, next to the other four. Its grants:
   - `app_user` and `web_identity`: `SELECT` and `INSERT`;
   - `web_session` and `web_auth_rate`: `SELECT`, `INSERT`, `UPDATE` and `DELETE`;
   - `USAGE` on the schema.

   It gets nothing else: no economic or rooted table, no `md_*` table, no gateway or `md_*` function, no sequence it does not need. That is the grant set the R7 `TEST`-install tests use. The R7 fix round may narrow it, but may not widen it without a new decision.
2. **Its credential.** The owner sets its password at the tool's prompt, in the owner's own terminal, as for the executor (PD-0077's rule applies to it). No agent session holds it, and none is given it in chat. The launcher takes it from a prompt only.
3. **The checks cover it.** The install plan, the role lists, Phase 2, the preflight gate and the catalog audit cover the `account` role the same way they cover the other four. A role or grant beyond consequence 1 refuses.
4. **D-3 is not declared.** Two-user isolation is to be shown over the real install at R8. The deviation would come back only if R8 cannot show it, and that would be put to the owner again.
5. This amends the four-role statement of PD-0076 and the install plan. PD-0076 is unchanged as a record.
6. Before R8 step 1, the changed installer, plan and checks pass the R7 independent review.
