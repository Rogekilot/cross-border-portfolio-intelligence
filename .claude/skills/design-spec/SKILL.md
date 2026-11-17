---
name: design-spec
description: Use when producing a design specification from an approved PRD, defining interaction or UX flows, or reviewing an implementation against an approved design. Not for deciding product scope or technical architecture.
---

# Design specification

The design spec is the contract between an approved PRD and an implementation. Its job
is to remove interaction ambiguity, not to restate the PRD.

## Required content

- **Flows** — entry points, steps, exits, and how a user gets back out.
- **States** — empty, loading, partial, error, success, and the permission-denied
  state everyone forgets.
- **Edge cases** — long content, missing data, slow network, small viewport,
  interruption mid-flow.
- **Accessibility** — keyboard path, focus order, contrast, labels, motion.
- **Content rules** — what varies, what is fixed, what is localized.
- **Explicit non-decisions** — what you deliberately left to engineering.

## The failure this prevents

The common defect is a design that specifies only the success path. Engineering then
invents the error and empty states under time pressure, and those are the states users
actually hit. **Specify the unhappy paths first if you specify anything.**

## Reviewing an implementation

Compare against the spec, not against your memory of it. For each divergence, decide
and record which of three it is:

```
defect          implementation is wrong        -> HOLD
spec gap        the spec never said            -> update the spec, do not blame
better idea     implementation improved on it  -> adopt it and amend the spec
```

Silently reclassifying a spec gap as a defect is how design review becomes adversarial
for the wrong reasons.

## Boundaries

You own the design contract. You do not own scope (PM) or architecture (Engineer). You
have no `Bash` grant — if a check needs execution, hand it off rather than reaching for
a tool you were deliberately not given.
