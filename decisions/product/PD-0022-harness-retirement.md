# PD-0022 — The HEA harness is retired; its procedures are superseded, product rulings are not

**Status:** accepted. The retirement itself, and (since 2026-09-30) §3 and §5 as written,
confirmed by the owner: see PD-0023 §1.
**Date:** 2026-09-29
**Decided by:** the designated **human product owner**, in direct instructions in a Claude
Code session on 2026-09-29. The owner decided the retirement and the instruction to carry
out the audit's recommendations (§1).
**Recorded by:** that session, which also carried out the cleanup. **Recorded, not decided.**
**Supersedes:** the harness-procedure clauses listed in §3, and only those.
**Reopens:** nothing. **Changes no product ruling** except the one clause the owner's
instruction directly reverses (PD-0020 §4, "harness retained"; see §3).

> **Recorded, not decided.** §1 is the owner's decision. Text marked **[Session reading]**
> is the recording session's interpretation of how that decision applies to earlier
> documents. It carries no decision authority until the owner confirms it, whether by
> committing this record as written or by amending it.

---

## 1. The decision, as given

After an audit of the harness, the owner instructed that:

- the recurring pattern of "the PM has to go back to the architect, and the architect has to
  change the harness to ensure the PM is proceeding" must stop;
- "the harness should leave the environment permanently after setup";
- the useful harness and the evidence stay in the environment, the ineffective files go to a
  separate folder, and the effect on current work is independently verified;
- the session "may proceed with your recommendations."

## 2. What was done

- The harness pack moved to `_archive/harness-3.2.0/` with its original paths preserved (see
  `_archive/README.md`). That covers policies, manifests, role contracts, the workflow DAG,
  schemas, task shards, handoffs, execution records, the worker registry, 23 scripts,
  11 hooks, the harness test suite, ADR-0001 to ADR-0035, and the harness escalation and
  certification files.
- These stayed live: product documents and code, all product decisions (PD-0001 to
  PD-0021), product review and gate evidence, the domain skills and agent definitions
  (trimmed), a rewritten `guard_write.py` driven by `.claude/role-write-paths.json`,
  `guard_browser.py`, and `scripts/serve_prototype.py`.
- `CLAUDE.md` was rewritten. `STATUS.md` replaces the task shards as the live status record.
- Independent verification found product files byte-identical and the product suite
  unchanged: 172 tests OK, 2 skipped, on Python 3.9.6 and 3.12.

## 3. Superseded clauses and the product intent kept — [Session reading]

Each clause below prescribes a mechanism that no longer exists, or the harness itself. Its
product intent is kept, restated in the right-hand column. Everything else in these
documents stands.

| Clause | Superseded | Product intent kept |
|---|---|---|
| PD-0020 §4 (H1b) | "…**harness retained for governance and review**." The owner's 2026-09-29 instruction reverses this. | **"(b) human-provisioned development environment", conditional on E0**, is unchanged. So is "the sandbox must not choose the production persistence architecture." |
| PD-0020 §6 reason ("full task-keyed provenance is wanted"), §6.1–§6.3; PD-0021 §4; `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md` §2.5 | `implement` shard lifecycle, execution-record statuses, and ADR-0033 unconcluded-stop gaps | **E0 earns no CP1 completion credit.** CP1-A to CP1-D are increments of one CP1 implementation. It goes to design review, technical review and PM acceptance only when CP1 is actually ready for downstream review. Never claim completion to tidy a record. **Attribution** is now provided by (a) a `STATUS.md` entry per increment naming the agent, the files changed and the exact test command and result, (b) the git commit of that increment, and (c) PD and gate records for human decisions. E0's evidence stays attributable through the archived records and commits `7e433ab` and `f9efdc3`. |
| PD-0021 §3.3 | Complete E0 Engineer registration (`register_worker.py`, witnessed `agent_id`, `assigned_task_id`, engagement capabilities, `--agent-definition`) before the worker writes | Dispatch the `engineer` agent defined in `.claude/agents/engineer.md` with a bounded brief. Its outcome is recorded in `STATUS.md` by the main session. |
| PD-0021 §10 ("under `implement = in_progress`") | Task-state wording | CP1 order and scope are unchanged: CP1-A, then B, then C, then D. |
| PD-0021 §6.1, §6.3 | "Do not reopen `prd`" because non-restorable revalidation would demote `ux_planning` and `tech_planning` | There is no task DAG now, so nothing can be demoted. The product intent stands: **do not re-open settled PRD scope to synchronize a closed question.** Route S1 or S2 (§6.2) remains the way to mark OQ-02 closed. Design and tech-plan updates are ordinary owner edits, recorded in `STATUS.md`. |
| PD-0020 §11 | "Harness Architect boundary." There is no Architect role any more. | If the sandbox denies both legitimate PostgreSQL routes: (1) stop; (2) preserve evidence; (3) return to the human for a provisioning or sandbox decision. **Do not work around the sandbox.** |
| `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md` §0 ("an Engineer cannot lawfully read the PDs") | Role `read_paths`, which no longer exist | The engineer may read `decisions/product/` directly. The spec remains a convenience index, and **the PDs control** where they differ. |
| `reviews/gates/PHASE_B0B_IMPLEMENTATION_PLAN.md` registration and recording steps (`register_worker`, `update_task_state`, `record_execution`, `record_handoff`, `--on-behalf-of`) and any other document's use of them | Mediated recording of worker state | Dispatch → report back → the main session updates `STATUS.md` (and a PD or gate package where a human decision is involved). |
| Any requirement to pass `validate_runtime.py` readiness or conformance, or to run a Harness Architect session before work proceeds | Runtime conformance gate | None. The human gates HG1–HG7 (PRD §38.4) remain the only approval gates. |
| ADR-0035 (archived). Status: **ACCEPTED**, owner-decided; only its preservation commit was pending. | Harness mechanics: checksum classification, Phase 2 item 1 (fixture copying) and item 4 (helper execution path), and the Phase 3 revalidation cutover | Carried into the live record: the engineer writes `pyproject.toml` and `uv.lock` (`.claude/role-write-paths.json`); uv runs `--no-cache` (`CLAUDE.md`); **the provisioning model** (the Engineer authors `pyproject.toml`, the human runs `uv lock` and `uv sync --python 3.12`, the Engineer commits the lockfile); the **Phase 2 item 2–3 proofs**; and the **temporary 3.9-compatibility floor** for new code, retired only after those proofs pass. All are in `STATUS.md` open items. |

## 4. Explicitly unchanged

- PD-0017 (HG1 APPROVED) and PD-0019.
- Every architecture, identity, environment, sequencing, deferral and scope ruling in
  PD-0020 and PD-0021, except the PD-0020 §4 "harness retained" clause in §3.
- The PRD's human-gate rules (§38): only the human product owner decides a gate.
- The roles' separation of duties: the method (quant-analyst) is separate from the
  implementation (engineer), and review is by a different agent than the producer.

## 5. How to change the working rules from now on — [Session reading]

A change to who may write where is an edit to `.claude/role-write-paths.json` by the main
session, with the reason noted in a PD or in `STATUS.md`. It needs no separate harness
session. That follows from the owner's instruction that the PM must not depend on an
Architect to proceed. A change to the hooks or settings is an ordinary, reviewable edit;
`.claude/settings.json` asks for approval before it changes.
