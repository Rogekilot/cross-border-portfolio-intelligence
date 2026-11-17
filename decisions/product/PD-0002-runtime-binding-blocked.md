# PD-0002 — The PM cannot register itself; runtime binding is structurally blocked

**Status:** blocked — escalated to the human product owner
**Date:** 2026-09-02
**Raised by:** `product_manager` (unregistered)
**Stop condition:** `roles/product_manager.json` → `"Required runtime worker cannot be bound."`

## What was attempted

Per the Architect's handoff (`docs/harness/HANDOFF_TO_PM.md` §3b), the PM was to
register its own interactive session as the first delivery worker. A complete,
schema-valid `pm-01` record was composed — `runtime_identity: "session:fin-web-9d"`,
observed via `ListAgents`; `effective_*` left `null` per ADR-0017 — and written to
`runtime/agent-registry.json`.

## Observed result — denied

```
BLOCKED (HEA §3.13): `runtime/agent-registry.json` is outside every role's declared write paths.
  Acting role could not be resolved (unresolved), so the union of non-infrastructure role grants
  was enforced and per-role narrowing was NOT applied.
Set HEA_ACTIVE_ROLE to get role-specific enforcement, or add the path to the owning role in
security-policy.json if it is genuinely needed.
```

## This is not a permissions accident — it is a bootstrap paradox

`runtime/agent-registry.json` is granted in `security-policy.json` to exactly one role:
`harness_architect`. That role is `infrastructure_principal`
(`roles/harness_architect.json:65`), and `guard_write.py` deliberately **excludes
infrastructure grants from the unresolved-role fallback union** — correctly, so an
unidentified actor cannot edit the boundary that constrains it.

So the registry is writable only by the Architect. The Architect has been **retired**.
And `runtime-policy.json` sets `fail_closed_on_missing_worker: true`.

The three exits, and why each is closed:

| Route | Outcome |
|---|---|
| Write as unresolved role | **Denied** (observed above) — infrastructure grants excluded from fallback |
| Set `HEA_ACTIVE_ROLE=product_manager` | **Would still deny.** PM's `write_paths` are `specs/`, `decisions/product/`, `reviews/gates/`, `reviews/PM_ACCEPTANCE.md`. The registry is not among them — role narrowing makes this *stricter*, not looser. |
| Set `HEA_ACTIVE_ROLE=harness_architect` | **Refused, not attempted.** Impersonating an infrastructure role to reach a denied write is precisely the move CLAUDE.md forbids: *"A denial is a boundary, not an obstacle. Do not look for another route to the same write."* |

**No non-infrastructure role can ever bind a runtime worker.** The delivery registry the
handoff asks the PM to build is unwritable by the PM, and by every other delivery role.

## Cascade

`scripts/_authority.py → verify_worker()` refuses provenance for a role with no
registered worker: *"no worker is registered against role X, so no provenance may be
recorded for its tasks."* Therefore **no task in the workflow can be completed with
provenance**, and `runtime_readiness_required: true` means operational work must not
begin at all.

## Related structural defect — the Designer cannot finish any task

Independent of the above, and confirmed **live** by resuming the spawned `designer`
subagent and asking it to enumerate its own tool surface:

- Designer tools are exactly `Read, Edit, Write, Grep, Glob`. **No Bash.**
  (`.claude/agents/designer.md:4` — it is the only agent of the four without it;
  `engineer`, `technical-reviewer` and `quant-analyst` all have Bash.)
- Its own definition, lines 23–25, instructs it to *"persist the design spec, update
  your shard, and emit a handoff"*, and CLAUDE.md's Finish contract requires the shard
  be updated *"atomically via `scripts/update_task_state.py`"* — a script, which needs a
  shell.
- `state/tasks/` and `artifacts/handoffs/` are mediated-only; a direct `Write` is
  blocked by design.
- The PM cannot do it on the Designer's behalf: `_authority.py` requires acting role ==
  task owner.

In its own words: *"without the PM ... performing the shard update on my behalf, I have
no legitimate path to complete that half of the Finish contract myself"* — and that
route is itself closed. **`ux_planning` and `design_review` cannot be completed by any
actor in this harness as configured.**

## Verified good news — role resolution genuinely works here

The Architect flagged per-role narrowing for subagents as *unverified in this surface*
(handoff §6) and asked for a live probe. It was run. `HEA_ACTIVE_ROLE` was left unset
throughout.

- **Granted path succeeded.** The `designer` subagent wrote `designs/FEATURE_DESIGN.md`.
- **Ungranted path was denied**, verbatim:

```
BLOCKED (HEA §3.13): role `designer` may not write `src/probe_should_be_denied.ts`.
  Declared write paths: designs/, reviews/DESIGN_REVIEW.md
  Role resolved from: payload.agent_type
Hand this off to the role that owns the path rather than writing it yourself; crossing a
path boundary is crossing an authority boundary.
```

Independently verified on disk by the PM, not taken on the subagent's word:
`designs/FEATURE_DESIGN.md` exists with exactly the probe-marker content, and `src/`
**does not exist at all** — the write was blocked before the directory was created.

**Conclusion:** the hook payload carries agent identity in this surface
(`payload.agent_type`), `_agent_name_to_role()` resolves it, and per-role narrowing
applies to delegated subagents. Controls resting on it hold at the stated rung. This
does **not** extend to the PM's own interactive session, which still resolves as
`unresolved` and falls back to the non-infrastructure union — the documented limit in
`rolectx.py`, not a defect.

`designs/FEATURE_DESIGN.md` currently holds a probe marker that states in its own text
that it is not a design artifact. It must be overwritten when `ux_planning` is
legitimately dispatched.

## Two further defects found, reported not fixed

1. **The checksum gate cannot survive normal operation.** `PACK_CHECKSUMS.sha256`
   checksums the *mutable* state layer — `project-state.json` and all seven
   `state/tasks/*.json` (lines 149, 207–213) — and `verify_pack_checksums.py` has no
   ignore mechanism. The single legitimate task-state update in PD-0001 broke it:

   ```
   ERROR: checksum mismatch: project-state.json
   ERROR: checksum mismatch: state/tasks/prd.json
   FAIL: pack checksum verification: 2 error(s)
   ```

   Every other stage of `scripts/self_test.py` still passes. This generalizes the
   Architect's `.DS_Store` finding (handoff §8.3): the real problem is that the manifest
   conflates immutable pack content with live state. And only `harness_architect` may
   write `PACK_CHECKSUMS.sha256`, so **no operational role can restore the gate after
   doing its job.** The gate now fails permanently.

2. **`hook_enforced_boundaries` is decorative.** `validate_runtime.py` never reads the
   field — grep returns no matches. It documents a claim nothing checks. Any assertion
   that a worker's boundaries are hook-enforced rests on the certification run
   (`LIVE_CERTIFICATION.md`), never on this field.

Neither is fixed here: both live in `harness_architect` write paths, both are harness
structure rather than product scope, and the PM was instructed not to redesign the
harness.

## Also blocked

`decisions/index.json` is an `harness_architect` write path, so this record and PD-0001
**cannot be indexed** by the PM. They exist under `decisions/product/` and are
unreferenced by the index.
