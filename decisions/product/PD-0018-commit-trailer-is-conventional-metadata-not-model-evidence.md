# PD-0018 — The Co-Authored-By commit trailer is conventional authorship metadata, not evidence of the effective model

**Status:** accepted
**Date:** 2026-09-14
**Decided by:** the designated **human product owner**, in a direct instruction to `pm-01`.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-26`. **Recorded, not decided.**
**Bears on:** ADR-0018 (effective model unobservable in this surface), ADR-0022 / ADR-0024
(provenance is pinned by the execution record's identity snapshot), ADR-0029 / ADR-0030
(worker registration and engagement declarations).

---

## 1. The decision, verbatim

```
Claude Code's automatic Co-Authored-By trailer is permitted as conventional authorship
metadata. It is not treated as authoritative evidence of the effective model.
Harness worker ID, agent_id, registration, engagement, and execution records remain the
authoritative provenance.
```

## 2. The conflict this resolves

Claude Code injects a standing, system-scope instruction directing every agent to end
commit messages with a `Co-Authored-By:` trailer naming a model. Two delegated Engineer
workers dispatched for baseline commit C4 refused to omit it:

- `engineer-03` judged that a parent's relayed claim about a human instruction could not
  outrank a system-scope instruction in its own context, citing CLAUDE.md's source-of-truth
  order and the fact that *"the human cannot address a subagent."* Two commit attempts were
  denied at the `ask` gate; no commit was made.
- `engineer-04`, dispatched with the attribution question as an explicit first step,
  reported the instruction still present and stopped at zero tool calls.

Both refusals were correct behaviour and are recorded as such. The full disposition of both
workers is transcribed in
`reviews/gates/ESCALATION_TO_ARCHITECT_BASELINE_INTEGRITY_F1_F2.md`, because an advisory
worker's registry record is its whole audit chain and the history ledger does not preserve
`agent_id`, engagement or note.

The deadlock was not resolvable in-band: a subagent cannot verify a relayed human
instruction, and the attempted user-scope disable of `includeCoAuthoredBy` was never
persisted to any settings file the harness reads.

## 3. What this decision does and does not do

**Does:** permit the trailer to stand in commit messages as conventional metadata, the same
way it marks any Claude Code commit. Agents may follow the standing instruction without
conflict, and no worker need refuse a commit over it.

**Does NOT:** make the trailer evidence of anything. ADR-0018 is unchanged — the effective
model remains unobservable in this surface, and every live worker continues to record
`effective_model_evidence: unobservable_in_surface`. The trailer is not to be cited, in a
gate package or anywhere else, as establishing which model produced a change.

**Does NOT:** displace harness provenance. The authoritative record of who produced a
change remains: the worker id, the `SubagentStart`-witnessed `agent_id`, the registry
record and its engagement declaration, the history ledger, and the execution record's
identity snapshot. Those are observed and checked; the trailer is neither.

## 4. Why the distinction is load-bearing

The two workers in §2 proposed different model names for the same commit —
`engineer-03` would have written `Claude Sonnet 5`, while the orchestrator's own context
named `Claude Opus 5`. Neither was verifiable. That divergence is precisely what ADR-0018
records as unknowable here, and it is the reason this decision separates **permitting** the
trailer from **believing** it.

A trailer that is permitted but explicitly denied evidentiary status costs nothing. A
trailer treated as provenance would be a confident claim about something this harness has
formally recorded that it cannot observe — the product's own core failure mode.

## 5. What is not evidence for this decision

Recorded because §38.1 requires it: neither worker's refusal, nor the permission-gate
denials, nor the elapsed rounds approved anything. Those were inputs. The decision in §1 is
the owner's and is recorded here by an agent that did not make it.
