# PD-0071 — The owner's dev-cluster superuser is lent to the test kit for throwaway databases

**Status:** accepted
**Date:** 2026-10-25 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** F1 increment R1 (`implementation/CP7_F1_REAL_PATH_DESIGN.md` §7.1); `tests/product/real_gateway_kit.py`
and `tests/product/guarded_pg_provision.py`; CLAUDE.md "Environment facts"; PD-0061 (shared dev PostgreSQL).

## Context

R1's 74 PostgreSQL tests create a throwaway database and roles for each run, as the existing guarded
runner does. Provisioning needs a role that is a superuser able to CREATE ROLE and CREATE DATABASE.

On the shared dev cluster (`/tmp/.s.PGSQL.5432`), the supplied role `finweb_dev` has none of these. The
only such role is the owner's own, `<os-user>`. A catalog read on 2026-10-25 showed:
- `<os-user>`: superuser, CREATEROLE, CREATEDB, LOGIN;
- `finweb_dev`: LOGIN only;
- `finweb_app`: LOGIN only.

The engineer did not use the owner's role unasked, so all 74 tests skipped.

## Decision

Question asked, verbatim:

> How should R1's 74 PostgreSQL tests get a role that can create throwaway test databases?

Options shown, verbatim:
- **"Lend my dev superuser (Recommended)"**: "The test kit runs as your role <os-user> on the shared
  dev cluster (/tmp/.s.PGSQL.5432), only to create and drop its own prefixed finweb_it_rw_* databases and
  roles. It works inside the sandbox, so the engineer and reviewer can re-run it while fixing. Agents then
  run SQL as superuser on that dev cluster, which also holds finweb_dev."
- **"Use the CP7 cluster"**: "Start the private CP7 cluster (.local/cp7-postgres), where finweb_dev is a
  superuser, as the earlier guarded-test runs did. Starting it and every test run need a sandbox exception,
  so each run by me, the engineer or the reviewer asks you to approve."

Owner's answer, verbatim: **"Lend my dev superuser (Recommended)"**

## What this means

- **Who may use it.** The main session, the engineer and the technical-reviewer may run the product
  test suites with `FINWEB_PG_ADMIN_USER=<os-user>`. It is used on the shared dev cluster at
  `/tmp/.s.PGSQL.5432`, inside the sandbox.
- **What for.** Only so that the test kits create, use and drop their own prefixed throwaway databases
  and roles, for example `finweb_it_rw_*` and `finweb_it_guarded_*`. They clean up under the kits'
  existing name-prefix refusals.
- **Not covered:**
  - interactive SQL as that role;
  - any change to `finweb_dev`'s own schemas or to other databases on the cluster;
  - any change to roles the kits did not create;
  - cluster configuration;
  - any use outside the test kits.
- **No password is involved.** The cluster trusts the owner's role over its Unix socket. Nothing is
  stored or written.
- **Not the real cluster.** This does not touch the rule that no agent may reach a superuser of the
  real cluster (PD-0066 decision 7; design 1.2). The real cluster does not exist yet, and the test
  tooling must never be pointed at it.
- **Test commands that use it:**
  - default: `uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`
  - with PostgreSQL: the same, prefixed with `FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432
    FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app
    FINWEB_PG_ADMIN_USER=<os-user>`.

## Addendum, 2026-10-25: one manual cleanup, approved separately

One of the engineer's test runs hung. Its first version of a share-lock test had a cleanup-order
bug, and the test was then fixed. The hung run kept its throwaway database `finweb_it_rw_0fbb0a46`
and four roles. The sandbox refused the engineer's `kill`.

The main session asked the owner, who answered **"Stop it and clean up (Recommended)"**. The main
session then:
- stopped the hung background task through the app (`TaskStop`);
- as `<os-user>`, by exact name only, ran `DROP DATABASE "finweb_it_rw_0fbb0a46" WITH (FORCE)` and
  dropped the roles `finweb_it_rw_0fbb0a46_wd_owner`, `_wd_executor`, `_wd_loader` and `_wd_publisher`;
- confirmed with a catalog query that no `finweb_it%` database or role was left.

This one act was outside the lending above and was approved on its own. It does not widen the
lending.

## What this does not do

It approves no gate and no other credential use. The owner may withdraw it at any time.
