# PD-0006 — The §32 metric-state vocabulary is layered: sufficiency state + reason code

**Status:** decided (product contract, within PM authority) — **presented to HG1 for confirmation**
**Date:** 2026-09-03
**Decided by:** `product_manager`, session `fin-web-09`, worker `pm-01`
**Task:** `feature-development/prd` → binds `implement` (I1, I2) and `ux_planning` (D3)
**Closes:** OQ-01 (`specs/FEATURE_PRD.md` §9), assumption A-05 (§8)
**Related:** [PD-0005](PD-0005-v1-1-prd-is-the-governing-mandate.md), `designs/FEATURE_DESIGN.md` §D3, `implementation/FEATURE_TECH_PLAN.md` §9

---

## Why this is a PM decision and not the human owner's

`specs/FEATURE_PRD.md` OQ-01 assigned this to the human product owner. Having now read
§32 verbatim, I am reclaiming it as a product-contract decision, and I want the reasoning
visible because reassigning a question's owner is the kind of move that should never be
silent.

`Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` §32 reads:

> Every metric should return a state, not only a number.
>
> **Suggested conceptual states:**
>
> - AVAILABLE; LIMITED; INSUFFICIENT_DATA; STALE_DATA; UNSUPPORTED_ASSET;
>   MISSING_BENCHMARK; MISSING_COST_BASIS; MISSING_FX_HISTORY; CALCULATION_ERROR.

The words are **"suggested conceptual states."** The source PRD is not prescribing a wire
format; it is naming the concepts the product must be able to express and leaving the
concrete vocabulary to the product contract. That makes the shape mine to define under
`roles/product_manager.json` — *"translate the PRD into a canonical product contract:
terms…"* — rather than a gap in the mandate that only the human can fill.

What is **not** mine and stays where it is: the *thresholds* that decide when a metric is
`LIMITED` versus `INSUFFICIENT_DATA` (minimum observations, lookback, frequency) are
methodology and belong to `quant_analyst` (§33, §44.4). This decision fixes the shape of
the vocabulary, not a single threshold in it.

## Decision

The nine items in §32 are **two layers, not one list**:

**Sufficiency state** — required on every metric, exactly one of:

| State | Meaning |
|---|---|
| `AVAILABLE` | the metric is supported by sufficient data and may present a value |
| `LIMITED` | computable, but on a basis weak enough that the caveat changes the conclusion |
| `INSUFFICIENT_DATA` | not computable to a standard the product will stand behind; **no value is presented** |

**Reason code** — zero or one of: `STALE_DATA`, `UNSUPPORTED_ASSET`, `MISSING_BENCHMARK`,
`MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, `CALCULATION_ERROR`. Its usual job is to explain
a non-`AVAILABLE` sufficiency state.

A reason code is **optional even when the state is not `AVAILABLE`** — "not enough
observations" is a complete answer and does not need a code from this list.

> **Amended 2026-09-03, after `implement`.** This section originally read "**Reason code** —
> explains a non-`AVAILABLE` sufficiency state, …". `engineer-02` correctly pointed out that
> the sentence, read on its own, implies a structural rule — *`reason_code` present ⇒ state ≠
> `AVAILABLE`* — that the very next section of this document goes on to reject for
> `STALE_DATA`. The engineer did not build that coupling, which was the right call, and
> flagged the wording so a later reader would not assume the coupling had simply been
> forgotten. The wording is corrected above: explaining a non-`AVAILABLE` state is what a
> reason code is *for*, not an invariant it satisfies. **`AVAILABLE` + `STALE_DATA` remains a
> valid, expected combination.**

### Why layered rather than flat

The nine items are not parallel in kind, and a flat enum would assert that they are.
`AVAILABLE` / `LIMITED` / `INSUFFICIENT_DATA` answer *"is there enough data to stand
behind this?"* The other six answer *"why not?"* Flattening them forces a consumer that
only needs the first question to enumerate nine cases to get a three-way answer, and it
makes `CALCULATION_ERROR` — which is not a statement about data sufficiency at all —
sit as a peer of `AVAILABLE`. `CLAUDE.md` already states the invariant in the three-state
form, and P5 is a statement about sufficiency, not about causes.

## The gap this decision has to close, which neither planning worker caught

**`STALE_DATA` is not shaped like the other five reason codes.** The other five describe
a condition under which a metric *cannot* be properly computed. Staleness does not: a
metric can be perfectly computable, fully supported, and simply priced off data that is
not current. So the natural case `AVAILABLE` + stale inputs is **unrepresentable** under
a strict reading of "a reason code explains a non-`AVAILABLE` state" — and the alternative,
demoting every stale metric to `LIMITED`, would fire constantly and by design: source PRD
P10 and NFR-008 establish that cross-market prices are *never* simultaneously real-time.
A state that is almost always on carries no information.

**Ruling:** freshness is a **separate, orthogonal axis** from sufficiency, and
`designs/FEATURE_DESIGN.md` §D5 already models it that way — as two independent freshness
axes (per-market price, and FX) with their own disclosure pattern. Therefore:

- `STALE_DATA` is retained as a reason code **only** for the case where data is stale
  *enough* that the metric drops to `LIMITED` or `INSUFFICIENT_DATA` on those grounds.
  Where that threshold sits is `quant_analyst`'s, not mine, and it is not set here.
- Ordinary, expected staleness is **not** a sufficiency reason code. It is carried by the
  D5 freshness disclosure and does not disturb `AVAILABLE`.
- `implement` (I2) must therefore not encode "reason code implies not `AVAILABLE`" as a
  hard structural rule for `STALE_DATA` without also making the freshness axis
  representable. If the two cannot be reconciled cleanly in I2's scope, the correct
  outcome is to **narrow I2 and log it**, not to force one of the two into the other.

## What this binds

- **I1 / I2 (`implement`)** build this shape. AC-15's structural rule is unchanged and
  unweakened: a metric whose sufficiency state is not `AVAILABLE` cannot also carry a
  presentable value.
- **D3 (`designs/FEATURE_DESIGN.md`)** ~~was authored to exactly this reading and needs no
  rework.~~ **RETRACTED 2026-09-03 — this claim was false when written.** See the second
  amendment below. D3 *does* need rework, because this decision created a state
  (`AVAILABLE` + `STALE_DATA`) that D3.2 explicitly says cannot occur.
- **T3 / T4 Control 2 (`implementation/FEATURE_TECH_PLAN.md`)** proposed
  `sufficiency_state` + nullable `reason_code`, which is this shape. Confirmed.

## What this does not settle

- **Any threshold.** `quant_analyst` owns every boundary between `AVAILABLE`, `LIMITED`,
  and `INSUFFICIENT_DATA`, including the staleness threshold referenced above. None is
  set here and none may be inferred from this document.
- **HG1.** This is a PM decision presented to the human product owner for confirmation,
  not a gate approval and not a substitute for one. The owner may overturn it.

## Cost if the owner overturns it at HG1

Recorded honestly, because the two planning workers assessed it differently and both were
right about their own layer:

- **Technical cost: low.** `implementation/FEATURE_TECH_PLAN.md` §9 argues it is a
  field-shape migration inside one entity (`MetricResult`), touching no module boundary
  and no other T1–T8 decision. The engineer flagged that as its own claim for
  `technical_review` to check rather than self-certifying it.
- **Design cost: high.** `designs/FEATURE_DESIGN.md` §D3.5 states D3 would need rework
  rather than relabeling — a flat reading gives no structural basis for treating
  `MISSING_BENCHMARK` as a species of `INSUFFICIENT_DATA`, so the rendering table could
  expand from three renderings plus six attachable reasons to nine independent
  renderings, each needing its own non-numeric treatment rule.
- **Implementation cost: real but bounded**, and it grows the longer the confirmation is
  deferred, because I2 and its tests encode the shape directly.

---

## Second amendment, 2026-09-03 — after `design_review` and `technical_review`

Both reviews found this decision had done real damage, in two different directions. Both
were right. Recorded here rather than quietly patched, because a decision record whose
errors are edited out is worse than no decision record.

### 1. Only `STALE_DATA` is exempt from the coupling. The other five are not.

The first amendment above accepted `engineer-02`'s blanket narrowing — *no* structural
coupling between `reason_code` and `sufficiency_state`. `review-01` demonstrated that the
engineer's stated reason for going blanket does not survive contact with this document.
The engineer argued that coupling "would require inventing which reason codes are exempt."
**This document already supplies that list, verbatim, in the section above:**

> `STALE_DATA` is not shaped like the other five reason codes. The other five describe a
> condition under which a metric *cannot* be properly computed.

So the exemption list is exactly `{STALE_DATA}`, it needed no invention, and it needed no
`quant_analyst` threshold. The blanket narrowing left a hole that has nothing to do with
staleness. Constructible today, and accepted by the shipped tests:

```python
MetricResult(value=1.30, sufficiency_state=AVAILABLE, reason_code=MISSING_BENCHMARK)
MetricResult(value=1.30, sufficiency_state=AVAILABLE, reason_code=CALCULATION_ERROR)
```

Rendered under D3.2, the first is a CP4 beta whose benchmark is missing, displayed as a
bare `1.30`: a judgment presented with no reference point (**P4**), and a number the
product cannot justify (**§41.3, false precision**) — the exact failure this product
exists to avoid.

**Ruling.** The coupling is **required for the five**, and forbidden for `STALE_DATA`:

> `reason_code ∈ {UNSUPPORTED_ASSET, MISSING_BENCHMARK, MISSING_COST_BASIS,
> MISSING_FX_HISTORY, CALCULATION_ERROR}` ⇒ `sufficiency_state ≠ AVAILABLE`.
> `STALE_DATA` carries no such implication and is valid alongside `AVAILABLE`.

This is derivable entirely from this document's own text and sets no threshold, so it is
inside PM authority and does not wait on `quant_analyst`.

**My error, stated plainly:** I was offered a narrowing, I checked that its *premise* was
sound (`AVAILABLE` + `STALE_DATA` must stay representable — correct), and I did not check
that its *scope* was minimal. Accepting the widest narrowing that shares a correct premise
is how a structural guarantee gets hollowed out one reasonable-sounding step at a time.
P5 is enforced by construction or it is enforced by everyone remembering.

### 2. The "D3 needs no rework" claim was false, and is retracted above.

`designs/FEATURE_DESIGN.md` §D3.2 states verbatim: *"a reason code never modifies
`AVAILABLE`, since if there were a live blocking reason the metric could not be fully
available."* That was correct under assumption A-05, which governed when the design was
written. This decision then made `AVAILABLE` + `STALE_DATA` valid **and asserted in the
same breath that D3 needed no rework.** Both cannot be true. `design_review` caught it
independently of `technical_review`.

The design is not at fault: `designer-01` followed the governing assumption faithfully. I
changed the product contract underneath a finished artifact and did not propagate the
change. D3.2 requires a rendering rule for `AVAILABLE` + `STALE_DATA`, and that rework is
dispatched.

## Known limitations of this decision

- It is made without the human owner's confirmation, on the strength of the word
  "suggested" in §32. If the owner intended §32 as prescriptive, I have read a mandate
  more loosely than intended and this decision is the error.
- The `STALE_DATA` ruling above reconciles a genuine modeling conflict, but it does so by
  pushing the hard part — where "stale enough to matter" sits — onto a methodology owner
  who has not yet been engaged in this increment. Until `quant_analyst` sets it, that
  boundary is undefined, and any code that appears to define it is overreaching.
