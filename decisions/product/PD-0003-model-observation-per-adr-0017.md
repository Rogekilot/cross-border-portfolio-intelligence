# PD-0003 — Model-observation finding resolved per ADR-0017: keep the block, escalate the choice

**Status:** resolved as far as PM authority extends; the remaining choice is escalated
**Date:** 2026-09-02
**Governing decision:** `decisions/accepted/ADR-0017.md` (accepted)

## The finding

```
ERROR: effective model observation requires unavailable runtime capability model_observation
```

`runtime-policy.json` sets `record_effective_model: true`. This surface exposes no API
reporting which model or reasoning effort a worker *actually* used after it executes, so
`platform-capabilities.json:363` records `model_observation` as `unavailable` on
observed evidence. `validate_runtime.py:102-104` fires the error whenever
`record_effective_model` is true, and there is **no escape hatch** in the validator —
`degraded_mode_approved` / `approval_reference` are consulted only on the
principal-delegation path, never here.

## Resolution applied

ADR-0017's accepted decision is **Option 1: leave the block in place**. That is what has
been done, and it is what governs any worker this session registers:

- `record_effective_model` stays `true`.
- Every `effective_model`, `effective_model_class` and `effective_reasoning_effort`
  stays `null`.
- Runtime readiness stays failing on this error, honestly.

The `pm-01` record composed in PD-0002 was built this way — `effective_*` all `null` —
before it was denied for an unrelated reason.

## What was deliberately not done

**Option 3 — declaring values — was available and was rejected.** This session knows its
own model identity from its system prompt, and could have written it into
`effective_model`. ADR-0017 anticipated exactly this and named it: writing a configured
or self-reported value into a field whose name says *effective* converts configuration
into apparent evidence (§3.10). It would replace a visible, accurate blocker with an
invisible false claim — strictly worse than red. The same reasoning that rejected it for
`architect-01` rejects it for `pm-01`; nothing about the PM's session makes self-report
into runtime observation.

Note the consequence, stated plainly rather than hidden: registering **any** worker
honestly will *add* a second error —
`worker <id> missing effective model/reasoning evidence` — because both errors share one
root cause. That is the correct, honest cost of not fabricating.

**Option 2 — setting `record_effective_model: false` — is not the PM's to take.** It is
defensible on the merits, since the capability genuinely is unavailable. But it requires
editing `runtime-policy.json` (an `harness_architect` write path, and control-plane per
`rolectx.CONTROL_PLANE`) **and** amending
`test_effective_model_evidence_required` in the regression suite so a gate stops asking a
question the doctrine wants asked. ADR-0017 says that trade "belongs to a human, not to
the bootstrap"; `roles/product_manager.json` lists harness structure as a
non-responsibility; and this session was instructed not to redesign the harness. Three
independent reasons, same answer.

Escalated to the human product owner in
`reviews/gates/PM_RUNTIME_READINESS_ESCALATION.md`, Decision 2.

## Capability record not updated

The live probe in PD-0002 proved `subagent_spawn` actually works, which would raise it
from `available_but_unverified` to observed in `platform-capabilities.json`. That file is
an `harness_architect` write path and is therefore unwritable by the PM. The evidence is
recorded here instead; the capability record still understates what has been observed.

`model_observation` itself remains correctly `unavailable`. Nothing observed this session
changes it.
