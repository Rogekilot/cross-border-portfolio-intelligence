# Project Agent Instructions

Cross-Border Portfolio Intelligence Platform: an analytics, interpretation, and scenario
product for investors holding securities across US, Mainland China, and Hong Kong markets.

**Start every session with `STATUS.md`**: current phase, next step, open items. Then read
only the documents it and the task point to.

## Source of truth, highest first
1. system, developer and user instructions
2. law, regulation and approved policy
3. `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md`, `specs/`, and the human product
   owner's decisions in `decisions/product/PD-*.md`
4. approved design (`designs/FEATURE_DESIGN.md`), methodology (`methodology/`) and tech
   plan (`implementation/FEATURE_TECH_PLAN.md`)
5. `STATUS.md`
6. conversation history

## Product invariants

These are not style preferences. They are the conditions under which this product is
allowed to make a claim at all.

- **The deterministic engine owns financial facts; the AI layer owns explanation.**
  The AI never computes a number it presents. It reads computed values and explains
  them. (P1, §22.3)
- **No metric without sufficient data.** Every metric carries a state —
  `AVAILABLE`, `LIMITED`, `INSUFFICIENT_DATA`. Insufficient data suppresses the number;
  it does not soften it. (P5, §32)
- **Historical statistics are not forecasts.** Describe what happened; never project.
  (P6)
- **Every judgment needs a reference point** — benchmark, the user's own policy, or the
  portfolio's history. (P4)
- **Never invent a personalized constraint.** Risk tolerance, goals, and horizon come
  from the user or do not exist. (P7)
- **Hypothetical and actual portfolio states stay strictly separated.** A scenario
  result may never be presented as a holding. (P8)
- **Simplification must preserve uncertainty.** Plainer wording may drop precision; it
  may not drop a caveat that changes the conclusion. (P3)
- **Determinism.** Same inputs and as-of date, same output. Conventions — day-count,
  annualization, compounding, FX fixing — are part of the method and are written down
  in `methodology/`. (P12, NFR-001, §34)
- **Every important insight is auditable** back to its inputs and method. (P9, §21)
- V1 is not brokerage, advice, tax guidance, or execution. Keep advisory and execution
  capability separable from the analytics core. (§31)

If an instruction conflicts with one of these, stop and escalate. Do not resolve it by
weakening the invariant.

## Human gates (HG1–HG7, PRD §38.4)

- Only the designated human product owner decides a gate. Passing tests, a reviewer's
  PASS, elapsed time, a deadline and silence are never approval.
- On reaching a gate, assemble the package in `reviews/gates/HG<n>_GATE_REVIEW.md` (skill
  `human-gate-package`), present it, and stop work downstream of that gate until the owner
  decides.
- Record the decision verbatim, conditions included, in a new
  `decisions/product/PD-NNNN-*.md`, and update `STATUS.md`.
- `REVISION_REQUIRED` means rework inside the current increment, then return to the gate.

## Roles and delegation

The **main session is the PM and orchestrator**. It owns scope, sequencing, gate packages,
product decisions and `STATUS.md`. It dispatches specialists as subagents (definitions in
`.claude/agents/`):

| Subagent | Does | May write (enforced) |
|---|---|---|
| `engineer` | implementation, tests, technical plan | `src/`, `tests/product/`, `implementation/`, `pyproject.toml`, `uv.lock`, `reviews/ENGINEERING_SELF_VALIDATION.md` |
| `quant-analyst` | methods, conventions, sufficiency thresholds, hand-derived golden fixtures | `methodology/` |
| `designer` | IA and interaction design, design review | `designs/`, `reviews/DESIGN_REVIEW.md` |
| `technical-reviewer` | independent adversarial review | `reviews/TECH_REVIEW.md` |

- `.claude/hooks/guard_write.py` enforces the write column from
  `.claude/role-write-paths.json`. Built-in subagents (general-purpose, Explore, Plan) may
  not write. Use them to read and report back.
- **If a role needs a new path, the main session edits `.claude/role-write-paths.json`**
  and notes why in the relevant PD or `STATUS.md`. No separate harness session is needed.
- The main session is not path-restricted. By convention it does not write product code or
  methodology; it dispatches the owner, so work and review stay separate.
- Nobody reviews their own work. The method (quant-analyst) and its implementation
  (engineer) come from different agents. Fixture expected values are derived
  independently, never copied from the code's output.
- Subagents change files only with Write/Edit. `.claude/hooks/guard_bash.py` refuses a
  subagent's Bash command that writes outside `$TMPDIR` (redirection, `sed -i`, `tee`,
  `cp`/`mv`/`rm`/`touch`/`mkdir`, inline or heredoc code calling a file-writing API). It is a
  speed bump against agent error, not a sandbox: still check `git diff` after every dispatch.
  The main session is not restricted.

## Definition of done (every increment)

1. Artifacts are saved in their owner's paths.
2. Tests were actually run and the real result is reported. "Not run" is an acceptable
   answer; an assumed pass is not.
3. `STATUS.md` is updated: what changed, test results, open issues, next step.
4. Commit only when the human asks, naming the paths (`git commit` asks for approval).

## Environment facts (Claude Code desktop, sandboxed Bash)

- Bash runs in an OS sandbox. It can write only inside this project and `$TMPDIR`, has no
  network access, and cannot open listening sockets. The PostgreSQL Unix socket
  `/tmp/.s.PGSQL.5432` is allowed; loopback TCP is not.
- The product targets **Python 3.12 via uv**, but `python3` is 3.9.6. Run the product tests
  with `uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`
  The `--no-cache` flag is required because uv's cache directory is outside the sandbox.
- Installing packages needs network access, so it is a human provisioning step.
- **Prototype review.** Browser tools (the in-app browser and Claude in Chrome) may open only
  `designs/` or the local review server (`.claude/hooks/guard_browser.py`).
  - A `file://` page shows the static shell only; the prototype's scripts do not run.
  - To see the prototype running, start `python3 scripts/serve_prototype.py --start`. It
    must run with the Bash sandbox disabled for that one command. It serves one directory
    under `designs/` on loopback, and that origin is the only `http://` destination allowed.
  - The browser pane may report `document.hidden`. Force a paint, for example by taking a
    screenshot, before judging animation-frame behaviour.
- `.env`, `*.pem` and `id_rsa*` are never read, and secret files are never written.
  Destructive git commands (`checkout`, `switch`, `restore`, `reset`, `clean`, `stash`,
  `push`) are denied.

## History

The HEA harness pack 3.2.0 that governed this project until 2026-09-23 is archived,
read-only, under `_archive/harness-3.2.0/`; see `_archive/README.md`. Older documents that
cite `ADR-00xx`, `state/tasks/…`, `artifacts/handoffs/…`, `runtime/…` or harness scripts
refer to files there. None of it is live. Its procedures (worker registration,
`update_task_state.py`, `--on-behalf-of`, task-shard states, readiness checks) are
superseded wherever older PDs, specs or plans prescribe them. `decisions/product/PD-0022-harness-retirement.md`
lists those clauses and the product intent each one keeps.
