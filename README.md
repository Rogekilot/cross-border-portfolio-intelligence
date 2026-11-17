# Cross-Border Portfolio Intelligence

An analytics, interpretation and scenario product for investors who hold securities across the US, Mainland China and Hong Kong
markets. It explains what a portfolio is exposed to, how it has performed and what happened in the past, in plain language,
in English and Chinese.

**Status: a personal, academic project, built end to end by AI agents under a human product owner.** It is not brokerage,
investment advice, tax guidance or execution. Nothing in it is a recommendation or a forecast.

**Real-data runs have happened, on the owner's machine.** The first install against real market data (increment R8, one US
security on one date, with a constructed non-personal ledger) and a supplementary run on the same data ran in November 2026.
The human gate after them (HG4) was approved
with conditions ([PD-0089](decisions/product/PD-0089-hg4-approved-with-conditions.md); package in
[`reviews/gates/HG4_GATE_REVIEW.md`](reviews/gates/HG4_GATE_REVIEW.md)). The licensed values from that run are redacted here.
Everything you can run from this repository runs on invented `TEST` data.

## What makes it different: the rules it is not allowed to break

These invariants, from the [PRD](Cross_Border_Portfolio_Intelligence_PRD_v1_1.md), are the conditions under which the product may
make a claim at all ([CLAUDE.md](CLAUDE.md) lists them):

- **The deterministic engine owns financial facts; the AI layer owns explanation.** No number shown to a user is computed by a
  language model.
- **No metric without sufficient data.** Every metric is `AVAILABLE`, `LIMITED` or `INSUFFICIENT_DATA`; insufficient data
  suppresses the number rather than softening it.
- **Historical statistics are not forecasts.** Every judgment has a reference point (a benchmark, the user's own policy, or the
  portfolio's history).
- **Hypothetical and actual portfolio states stay separate.** A scenario result is never presented as a holding.
- **Determinism and auditability.** Same inputs and as-of date, same output; day-count, annualization, compounding and FX fixing
  conventions are written down in [`methodology/`](methodology/), and every important insight traces back to its inputs and method.

## Architecture

| Layer | Where | What |
|---|---|---|
| Domain and ledger | `src/domain/`, `src/portfolio_import/` | Canonical transactions; positions are derived, never stored as truth; audited CSV import |
| Market data | `src/marketdata/` | Versioned files with manifests and SHA-256 identities, trading calendars, FX fixings, source attestation (`data/marketdata/SOURCES.json`) |
| Engines | `src/performance/`, `src/risk/`, `src/diversification/`, `src/insights/` | Performance (TWR, MWR, FX decomposition), risk, diversification and deterministic observations; each result carries its sufficiency state and lineage |
| Services and API | `src/*_service/`, `src/web_api/` | Versioned contracts over FastAPI; the web client receives computed values and never does financial arithmetic |
| Persistence | `src/persistence/` | PostgreSQL with a guarded gateway: row-level policies, sealed results, a provenance registry, and separate roles for owner, loader, publisher, executor and accounts |
| Real-data path | `src/real_service/`, `src/real_tools/` | The F1 path for real data: qualification, a time-limited publish with expiry evidence, withdraw and renew, and command-line tools that take passwords only at a terminal prompt |
| Web | `web/` | React 19 + TypeScript + Vite; English and Simplified Chinese; Quick, Simple and Professional depths |

Design: [`designs/FEATURE_DESIGN.md`](designs/FEATURE_DESIGN.md). Technical plans: [`implementation/`](implementation/).
Methods and hand-derived golden values: [`methodology/`](methodology/). Product decisions: [`decisions/product/`](decisions/product/).

## Running it on TEST data

Requirements: Python 3.12 via [uv](https://docs.astral.sh/uv/), Node 26+, and PostgreSQL 17 for the database-backed parts.

```bash
uv sync --frozen
FINWEB_NO_VENDOR_FILES=1 uv run --frozen python -m unittest discover -s tests/product -t .   # PostgreSQL tests skip unless enabled
cd web && npm ci --ignore-scripts && npm run typecheck && npm test      # web type check and unit tests (vitest)
```

The local synthetic web app (invented data only):

```bash
PYTHONPATH=src uv run --frozen uvicorn web_api.dev:app --host 127.0.0.1 --port 8000
cd web && npm run dev            # http://127.0.0.1:5173
```

[`web/README.md`](web/README.md) has the database-backed flows, the real-mode screen over a disposable `TEST` install, and the
Playwright end-to-end tests. Licensed market-data files are not in this repository (the providers' terms allow internal use only).
The tests that read them fail loudly when a file is missing, by design; `FINWEB_NO_VENDOR_FILES=1` (exactly `1`) declares that the
files are absent and skips exactly those tests, with the reason shown.

## How it was built

Every line was written by AI agents (Claude Code) in defined roles, under one human product owner who made every product decision
and decided every human gate (HG1 to HG7, PRD §38.4):

- **The main session** acts as product manager and orchestrator. It owns scope, sequencing, gate packages and the status record.
- **Specialist subagents** (`.claude/agents/`): an `engineer`, a `quant-analyst` (methods, conventions, independently derived
  golden fixtures), a `designer`, and an independent `technical-reviewer` that reviews adversarially, with mutants. Nobody reviews
  their own work, and the method and its implementation come from different agents.
- **Hooks enforce the roles** (`.claude/hooks/`): each agent may write only its own paths (`.claude/role-write-paths.json`), and
  shell commands that write elsewhere are refused.
- **Decisions are recorded verbatim** in `decisions/product/PD-*.md`. Passing tests, a reviewer's PASS, elapsed time and silence
  are never treated as approval.
- **Reviews:** [`reviews/TECH_REVIEW.md`](reviews/TECH_REVIEW.md) and [`reviews/DESIGN_REVIEW.md`](reviews/DESIGN_REVIEW.md), and the
  gate packages in [`reviews/gates/`](reviews/gates/). The full review archive (evidence packs, handovers, runtime logs) is not
  published.

## Limits

- Not advice, not a forecast, not a brokerage or tax tool.
- Real data covers one US security on one date (R8; HG4 approved with conditions). Values that came from licensed market data
  are redacted here, or, where a method or test needs a concrete example, replaced with invented values of the same shape (same
  decimals, float32 behaviour and range); worked examples are recomputed for them.
- **Hashes in this copy are not the private repository's.** A hash of a file that differs from its private version only by a short
  value or a name can be reversed by search. So wherever this copy cites the hash of a file it changed (sidecars, member tables,
  decision-record hashes, pins), the hash is recomputed for the file as published here; hashes of earlier private versions are
  replaced by `<private pin, PD-0083>`. The records stay self-consistent within this copy, but they will not match the hashes held
  in the owner's private registry. Some cited files are not published at all (the registered payloads and their manifests, e.g.
  a sidecar's `manifest_sha256`); their hashes are computed for the public version of the file but cannot be checked here.
- Personal details (names, usernames, broker names) are replaced with neutral text in this public copy.

## Licence

[MIT](LICENSE).
