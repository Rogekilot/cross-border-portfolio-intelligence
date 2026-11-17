---
name: delivery-orchestration
description: Use when dispatching work to delegated workers, deciding what can run in parallel, sequencing a feature through design and implementation and review, or deciding whether to delegate a task at all. For the role that owns the interactive session during delivery.
---

# Delivery orchestration

You own the single interactive session during delivery. Delegated workers cannot be
addressed by the human — everything they produce reaches a person through you or
through an artifact.

## Before dispatching

Check the dependency graph, not the workflow file order. Two tasks may run
concurrently when:

1. neither transitively depends on the other, **and**
2. their declared write/read/exclusive resources do not conflict.

Where concurrent workers write files, give them disjoint paths or run them one after
another. Do not use `isolation: "worktree"` here: the write guard only grants paths in
the main checkout, so a subagent in a worktree cannot write at all.

Respect the real concurrency cap. The orchestrator runs roughly `min(16, CPUs - 2)`
agents at once; excess calls queue. A design assuming twenty simultaneous workers
silently serializes while still being described as parallel.

## Writing a good brief

A delegated worker starts cold with no memory of this conversation. Its brief must
carry: objective, authoritative inputs by path, expected outputs, constraints, the
`STATUS.md` item it advances, and the paths it may write. A brief that assumes shared context produces work that
answers the wrong question.

Resume a worker with `SendMessage` when continuity matters; a fresh spawn starts cold
and re-derives everything.

## Relay is your job

A subagent's report is not shown to the human. If a worker surfaces something a person
must see — a blocker, a risk, a finding, a question — relay it or ensure it is written
to an artifact. Treating a finding as delivered because a subagent produced it is how
material information disappears.

Never state a pending worker's result before it returns. If work is still running, say
so.

## When not to delegate

Delegation costs a cold start and a relay hop. Do it for work that is bounded, benefits
from a fresh context window, or needs an independent identity for review. Do not
delegate a two-line edit; do not delegate to look busy.

## Staying inside your authority

You sequence and dispatch work. You do not rewrite a specialist's permanent authority
and you do not approve work you commissioned as if you were an independent
reviewer. Review requires a distinct runtime identity from the producer, and you are
the producer's parent, not its auditor.
