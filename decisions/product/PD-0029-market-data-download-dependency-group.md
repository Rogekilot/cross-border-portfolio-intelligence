# PD-0029 — Optional `marketdata-download` dependency group for the human-run download tool

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, answering a question put by the main
session in a Claude Code session on 2026-10-01.
**Recorded by:** that main session. **Recorded, not decided.**
**Builds on:** PD-0027 (free development sources; human-run download to files), the provisioning
model in `STATUS.md` open item 1 (engineer edits `pyproject.toml`, owner runs `uv lock` / `uv sync`).

---

## The decision

Question: *"The download tool you'll run needs two open-source libraries, AKShare and BaoStock.
The plan adds them as an optional dependency group (marketdata-download), installed only in a
separate .venv-download that you create, never in the product environment, which keeps psycopg as
its only dependency. Approve adding this group to pyproject.toml?"*

Owner's answer, verbatim: **"Approve the optional group (Recommended)"**

The option as presented: the engineer adds the group to `pyproject.toml`; the owner runs `uv lock`
(needs internet) and later installs it into `.venv-download` for download runs; the product's
locked environment and its checks are unaffected.

## Consequences

- `pyproject.toml` gains an optional group `marketdata-download` containing `akshare` and
  `baostock` (bounds chosen by the engineer). Core dependencies stay `psycopg[binary]` only.
- The owner runs `uv lock`; `uv.lock` is committed. The product environment (`.venv`, `uv sync`
  without the group) and the `uv sync --check --frozen --offline --no-cache` proof must stay
  unaffected; the engineer verifies that after the owner's lock.
- The group is installed only into `.venv-download` (git-ignored), used only by the human-run tool
  under `src/marketdata_tools/`, which product code never imports.
- Agents never run the download tool (PD-0027 condition 2).

## What this decision does not do

It does not attest any source's terms of use, provision any API key, or approve any purchase.
