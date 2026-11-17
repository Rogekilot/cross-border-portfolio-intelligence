# PD-0007 — `LIMITED` carries a value; only `INSUFFICIENT_DATA` suppresses one

**Status:** decided (product contract, within PM authority) — **presented to HG1 for confirmation**
**Date:** 2026-09-04
**Decided by:** `product_manager`, session `fin-web-77`, worker `pm-01`
**Corrects:** `specs/FEATURE_PRD.md` **AC-15**, which was wrong as written
**Raised by:** `designer-04`, `design_review` round 2, finding **BF-3** — correctly escalated as
a product-contract question above design authority rather than resolved locally
**Related:** [PD-0006](PD-0006-metric-state-vocabulary-is-layered.md), `designs/FEATURE_DESIGN.md` §D3.2

---

## The defect

AC-15 reads:

> A metric state carrying a non-`AVAILABLE` sufficiency state cannot also carry a
> presentable value.

`src/product_contract/metric_state.py` implements exactly that, and
`tests/product/test_metric_result.py::AC15NegativeTests::test_limited_with_value_fails`
pins it: `MetricResult(value=0.80, sufficiency_state=LIMITED)` raises.

`designs/FEATURE_DESIGN.md` §D3.2's `LIMITED` row specifies rendering *"the computed value
plus a mandatory, non-dismissible qualifier label in the same visual unit as the value."*

**Both cannot be true.** The design specifies rendering an object the contract forbids
constructing. `designer-04` found it in a row that none of the three design rework passes
touched, and confirmed it by running the suite rather than reasoning about it.

## The ruling

> **`INSUFFICIENT_DATA` ⇒ `value is None`.** `LIMITED` **may** carry a value, and normally
> does. `AVAILABLE` may carry a value.

AC-15 is corrected to this. The design is right; my acceptance criterion was wrong; the code
faithfully implemented my wrong criterion.

## Why the original wording was wrong

**1. It collapses the vocabulary.** If `LIMITED` can never carry a value it renders
identically to `INSUFFICIENT_DATA` — both suppress — and the state carries no information at
all. PD-0006 distinguishes them precisely by computability:

> `LIMITED` — **computable**, but on a basis weak enough that the caveat changes the conclusion
> `INSUFFICIENT_DATA` — **not computable** to a standard the product will stand behind

A three-state model whose middle state is operationally identical to its bottom state is a
two-state model with a redundant label. That is decisive on its own.

**2. `CLAUDE.md` P5 attributes suppression to insufficiency, not to limitation.**

> Every metric carries a state — `AVAILABLE`, `LIMITED`, `INSUFFICIENT_DATA`. **Insufficient
> data** suppresses the number; it does not soften it.

"It does not soften it" forbids offering a hedged number *instead of* suppressing — it does
not say a weak-but-real number may never be shown with a qualifier. `LIMITED` is named as a
separate state in the same sentence.

**3. Source PRD §32's worked example is an `INSUFFICIENT_DATA` example.** *"3Y Beta — N/A.
Insufficient weekly observations."* §32 offers no example of `LIMITED` rendering as `N/A`, and
its prohibition is on *"zero, blank, or fabricated fallback values that can be mistaken for
real analytics"* — a qualified real value is none of those three.

## The counter-argument, and why it does not hold

**"Permitting `LIMITED` to carry a number re-opens false precision (§41.3), and P5 is the
invariant this product exists to protect. Correcting an AC in the permissive direction, in
response to a late finding, is exactly how a guarantee gets weakened."**

That is the right thing to be suspicious of, and I have been wrong once already this
increment in precisely that direction — PD-0006's first amendment accepted a narrowing that
was too wide. So, explicitly:

- **The false-precision guard is unchanged.** A metric the product cannot stand behind still
  shows no number: `INSUFFICIENT_DATA ⇒ value is None` remains machine-enforced, and AC-15
  remains the one criterion in INC-001 a machine decides.
- **What changes is a conflation, not a threshold.** The old wording merged "weak but
  computable" with "not computable." Separating them restores a distinction the source PRD
  and PD-0006 both draw.
- **`LIMITED` is not bare.** D3.2 requires a mandatory, non-dismissible qualifier *in the same
  visual unit as the value*, never a tooltip-only footnote, and forbids a `LIMITED` value
  being visually indistinguishable from an `AVAILABLE` one at any depth including Quick.
- **The direction of the error matters.** Over-suppression is the safer error, which is why
  it survived three rework passes and two review rounds unnoticed. Safer is still wrong: a
  product that suppresses computable numbers teaches users the states are noise.

**Where the boundary sits between `LIMITED` and `INSUFFICIENT_DATA` is not set here.** That is
a methodology threshold — minimum observations, lookback, frequency — owned by
`quant_analyst` (§33, §44.4). This decision fixes only what each state may *carry*.

## What this binds

- **`implement` (I2):** the invariant becomes `INSUFFICIENT_DATA ⇒ value is None`.
  `test_limited_with_value_fails` inverts into a positive test. The PD-0006 second-amendment
  coupling (five reason codes ⇒ non-`AVAILABLE`) is **unchanged**, as is the `STALE_DATA`
  exemption.
- **`designs/FEATURE_DESIGN.md` §D3.2:** already correct. No design rework required — the
  first time in this increment the design was right and something else moved.
- **AC-06:** returns to satisfiable once the code matches.

---

## Amendment, 2026-09-04 — the rule is made total (`design_review` round 3, BF-4)

`designer-04` accepted the core ruling and rejected the hedge, correctly:

> "permitted, not required" was adopted without checking whether D3.2 covers the branch it
> keeps open. It doesn't, and that gap is exactly BF-4.

`MetricResult(value=None, sufficiency_state=LIMITED)` was still legal, and §D3.2's `LIMITED`
row is written entirely in terms of *"the computed value"* — it has no branch that applies
when there is none. Same defect shape as BF-1 and BF-3: the contract permitting a state the
design cannot render.

### Amended ruling — total

> **`value is None` ⇔ `sufficiency_state is INSUFFICIENT_DATA`.**
> `AVAILABLE` and `LIMITED` both **require** a value. `INSUFFICIENT_DATA` forbids one.

This is semantically forced, not a patch. `LIMITED` means *computable on a weak basis* — if
a value could not be produced, the state is `INSUFFICIENT_DATA` by definition, so a
value-less `LIMITED` describes nothing. The same argument applies to `AVAILABLE`, which was
equally unconstrained and equally incoherent: a metric that is "available" and absent is not
a state this product should be able to express.

Making the rule an equivalence closes the whole gap class rather than the one instance BF-4
named, and it restores a total, machine-decidable rule — AC-15 remains the one criterion in
INC-001 a machine decides.

### The pattern this is the third instance of, and it should be visible at HG1

| Finding | The design said | The contract/code said | Who was right |
|---|---|---|---|
| BF-1 | `AVAILABLE` + `STALE_DATA` needs a rendering | — (PD-0006 created the state without telling the design) | design, after the fact |
| BF-3 | `LIMITED` renders "the computed value plus a qualifier" | AC-15 forbade `LIMITED` carrying a value | **design** |
| BF-4 | `LIMITED` always has a value to render | PD-0007 permitted `LIMITED` without one | **design** |

`designs/FEATURE_DESIGN.md` §D3.2, authored by `designer-01` directly from source PRD §32
before any of these decisions existed, encoded the total rule from the start. Three separate
contract decisions of mine have drifted from it and been corrected back toward it. **The
design was the more faithful reading of §32 than my acceptance criterion was**, and that is
worth the human owner knowing when weighing how much of this contract to trust.

### On over-tightening, since I have now moved this rule three times

The mirror risk of PD-0007's original error is over-correcting under pressure from a finding.
The case I checked for: is there a legitimate `AVAILABLE`-or-`LIMITED` metric with no value?
A zero value is `0.0`, not `None`, and is explicitly tested. A not-yet-computed metric is not
a `MetricResult` — that type is the envelope a *computed* value travels in. I found no
genuine case and am recording that I looked. If one exists, this amendment is the error.

## Known limitations of this decision

- It is a **contract change made after the code shipped and after two review rounds**, at the
  end of the increment. The reviews that examined the old invariant did so correctly against
  a criterion that was wrong, so their AC-15 verdicts certify conformance to a defective
  specification. Re-verification is required and is dispatched.
- `LIMITED` is left **permitted** to carry a value rather than **required** to. If a
  `LIMITED` with no value is meaningless in practice, that is a tightening a later increment
  may make; I am not inventing the stronger rule without evidence it is needed.
- I did not catch this myself across authoring, reconciliation, and three rework dispatches.
  It took a fourth independent designer identity running the test suite against the document.
  That is an argument for the review structure, not for my drafting.
