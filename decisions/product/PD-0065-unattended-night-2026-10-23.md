# PD-0065 — Unattended night run, 2026-10-23

**Status:** accepted
**Date:** 2026-10-23 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Plan:** `/Users/<os-user>/.claude/plans/wondrous-munching-pearl.md` (approved by the owner
via plan approval).

## Owner decision, verbatim

> I'm about to go to sleep, and I want you to create a night plan that you can run overnight without me auditing anything. You can leave the human gate decisions when I wake up.

Answers to the session's questions:
- Commits: **"Commit after review (Recommended)"**. Commit each piece only after its tests
  pass and the independent review passes, naming the paths. Nothing is pushed.
- Scope: **"US HG4 path + A-shares (Recommended)"**.
- Keep awake: **"Yes, keep it awake (Recommended)"**, for this session only.

## What tonight may do

Only work on the real-data path that needs no downloaded data and no human gate:
- quant rulings on US split data (single-date check) and A-share route conventions;
- the real-path F1 design (options for the owner, not chosen);
- the Alpha Vantage A-share route in code, kept **pending observation, not admitted**;
- a CN calendar check packet against official SSE/SZSE holiday notices, read from public
  pages;
- independent review, tests, and a commit per increment after it passes. That means PASS,
  or PASS_WITH_FINDINGS with only LOW findings open.

## Hard limits

- **No data:** no data-vendor API call or download; no accounts, keys or purchases.
- **Git:** no push, and no destructive git.
- **Environment:** no package installs; no edits to `.claude/`; no sandbox disabling.
- **No owner decisions:** no gate decision; no decision recorded on the owner's behalf. No
  CN price profile is admitted, no calendar is registered, and no F1 option is chosen.
- **Databases:** no SQL installed into an existing non-disposable database.
- **Failures:** two review FAILs on one item stop that item. A permission denial is never
  worked around.

## What this does not do

It approves no gate (HG4 stays open), no data acquisition, and no source admission. Morning
decisions are listed in STATUS.md at the end of the run.
