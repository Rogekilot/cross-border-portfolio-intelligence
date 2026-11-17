---
name: implementation-standards
description: Use when implementing a feature against an approved PRD and design spec, writing tests for it, or preparing implementation work for technical review. Covers what "done" means before a task may be marked complete.
---

# Implementation standards

## Before writing code

Read `STATUS.md`, the approved PRD and the design spec. If they conflict, stop and
escalate rather than choosing — resolving a contract conflict silently is a scope
decision you do not own.

## While implementing

- Match the surrounding code: its naming, its idiom, its comment density. New code
  that reads as foreign is a maintenance cost paid by everyone after you.
- Handle the states the design specified, including the unhappy paths.
- Where you make a decision the contracts did not cover, record it in the handoff.
  Undocumented judgment calls are where the next reviewer loses the thread.

## Testing

Tests must actually run, and their real result is what gets recorded.

```
suite passed          -> record passed
suite failed          -> record failed, with the output
suite not run         -> record not run, and say why
```

Never record an expected result. A test you believe would pass is not evidence, and a
harness that accepts predicted results has no test gate at all.

## Parallel work

If other workers may write the same files, stop and ask the main session to sequence the
work. Worktree isolation is not usable here: the write guard grants paths only in the
main checkout.

## Completion check

A task is not complete until:

1. code and tests are persisted;
2. required tests ran, with the real result recorded;
3. your report to the main session names completed work, files, decisions, blockers,
   and next step;
4. the main session has recorded that in `STATUS.md`.

No hook can check honesty about (2). That is on you, and it matters most.

## Boundaries

You may not redefine product scope; escalate conflicts to the PM. You may not approve
your own work; technical review is a distinct runtime identity.
