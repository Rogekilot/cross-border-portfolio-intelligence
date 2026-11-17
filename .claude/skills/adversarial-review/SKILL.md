---
name: adversarial-review
description: Use when reviewing work that another agent or person produced and the review must be genuinely independent — code review, design review, PRD review, architecture review, or checking whether a claimed guarantee is actually enforced. Also use when a review has come back clean and you want to test whether it was real.
---

# Adversarial review

The failure mode this exists to prevent is not missed bugs. It is **agreement** —
a reviewer who reconstructs the producer's reasoning, finds it coherent, and
approves. Coherence is what the producer already optimized for.

## Method

**1. Read the contract before the work.**
Find what the work was supposed to satisfy — the PRD, the schema, the role
contract, the acceptance criteria — and read it first. Reading the artifact first
anchors you to its framing.

**2. Ask what would have to be true.**
For each claim the work makes, ask what must hold for it to be correct, then check
that thing directly rather than checking whether the claim sounds right.

**3. Attack the enforcement claim, not the prose.**
When work claims a rule is enforced, find the mechanism. In a Claude Code harness
that means: is there a registered hook, a `permissions.deny` entry, a sandbox
boundary, or a test? "It says so in CLAUDE.md" is the weakest rung of the
enforcement ladder (instruction < script someone runs < hook or permission rule that
actually denies), not the strongest. Mis-stated rungs are the most common
defect in harness work and the easiest to miss.

**4. Require a failure scenario.**
Every finding must name concrete inputs or state and the wrong outcome they
produce. If you cannot construct one, you have a stylistic preference. Either
label it as such or drop it.

**5. Check what is absent.**
The producer saw what they wrote. Ask what a correct solution would contain that
this one does not: the unhandled case, the untested boundary, the rule with no
enforcement, the role with no reviewer.

## Verdicts

- `PASS` — satisfies its contract; no material findings.
- `PASS_WITH_FINDINGS` — acceptable to proceed; findings are recorded and owned.
- `HOLD` — a material defect blocks acceptance. Name it and the contract it breaks.

## Before you call something broken, check the instrument

A finding is a claim about the artifact. If the probe that produced it was itself
unreliable, the finding is a claim about the probe, and filing it costs the producer a
cycle chasing a defect that does not exist.

**Known instrument hazard in this surface.** The browser pane reports
`document.hidden === true`, so `requestAnimationFrame` callbacks do not run until a paint
is forced. Any rAF-scheduled behaviour therefore looks *completely inert* to a probe that
merely waits: the property is never written, the pre-JS value reads back, and the code's
own regression check times out without its callback ever firing. A verification pass came
within one step of filing a fabricated regression on exactly this. **Force a paint (take a
screenshot) after each state change, then measure.**

This is a testing-surface characteristic, not a product defect, and the distinction is
yours to make before you write it down. When a symptom would be explained equally well by
"the code never ran" and "the observation never happened", establish which before
reporting. `CLAUDE.md` ("Environment facts") lists the hazards this surface is known to have.

## Two ways to be wrong

A review that never returns `HOLD` is compliance theater and adds nothing.
A review that manufactures findings to appear rigorous is worse: it spends the
producer's time and trains the organization to discount reviews.

Clean work reviewed honestly produces an empty findings list. That is a valid and
complete result. Report it plainly.
