# PD-0023 — CP1-B entry: PD-0022 mapping confirmed, Chrome page actions removed, migrations as plain SQL under `src/`

**Status:** accepted
**Date:** 2026-09-30
**Decided by:** the designated **human product owner**, answering three questions put by the
main session in a Claude Code session on 2026-09-30.
**Recorded by:** that main session. **Recorded, not decided.**
**Closes:** `STATUS.md` open items 0, 4 and 8 (as of 2026-09-29).
**Reopens:** nothing. **Supersedes:** nothing.

---

## 1. PD-0022 §3 and §5 — confirmed

Question: *"PD-0022 §3 and §5 map the harness retirement onto earlier PDs. It was committed
in f55c490. Do you confirm that mapping as written, so I can close STATUS item 0?"*

Owner's answer, verbatim: **"Confirm as written (Recommended)"**

Effect: PD-0022 §3 and §5 carry decision authority as written. No amendment.

## 2. Claude in Chrome tab containment — page actions removed

Question: *"Claude in Chrome tab containment (STATUS item 8): the designer and
technical-reviewer can act on any tab in your real Chrome, and only their instructions stop
them. How should this be handled?"*

Owner's answer, verbatim: **"Remove Chrome page actions (Recommended)"**

The option as presented: take the Chrome click/type/read tools off both agents; they review
the prototype with the in-app browser, which is isolated from the owner's signed-in Chrome.

Carried out in the same session:
- `.claude/agents/designer.md` and `.claude/agents/technical-reviewer.md`: every
  `mcp__claude-in-chrome__*` tool removed and replaced by the in-app browser equivalent
  (`mcp__Claude_Browser__*`), keeping each agent's previous capability set (the designer
  stays read-only; the reviewer keeps click/type, resize and console).
- The in-app browser is already covered by `.claude/hooks/guard_browser.py` (matcher
  `mcp__Claude_Browser__.*`), so navigation stays confined to `designs/` and the verified
  review server.
- **Remaining gap, stated plainly:** the in-app pane is shared with the owner, and a call
  that names a `tabId` is still not checked. The agents are told to act only on tabs they
  opened. The exposure no longer includes the owner's real Chrome sessions.
- **Not yet verified:** that a subagent can actually call the `mcp__Claude_Browser__*`
  tools. The first design or UI review will show it; a failure there is to be reported, not
  worked around.

Claude in Chrome remains available to the main session.

## 3. Database migrations — plain SQL under `src/`

Question: *"Database migrations (STATUS item 4): where should they live, and with what
tooling?"*

Owner's answer, verbatim: **"src/…/migrations, plain SQL (Recommended)"**

The option as presented: numbered `.sql` files under a product path in `src/`, applied by a
small runner in the repository; the only new package is the psycopg 3 driver for E0b; the
engineer already has write access to `src/`, so no write-path change is needed.

Consequences:
- No SQLAlchemy and no Alembic for CP1-B.
- The exact directory under `src/` is chosen by the engineer in CP1-B step 2 and recorded in
  `STATUS.md`.
- `.claude/role-write-paths.json` is unchanged.

## 4. What this decision does not do

It does not approve any gate, does not select a frontend framework, market-data vendor or
deployment intent, and does not change any product invariant or earlier product ruling.
