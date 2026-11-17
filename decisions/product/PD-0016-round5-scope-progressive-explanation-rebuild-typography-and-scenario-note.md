# PD-0016 — Round-5 scope: progressive-explanation rebuild authorized, typography direction set, Scenario Lab note removed

**Status:** accepted
**Date:** 2026-09-07
**Decided by:** the designated **human product owner**, in direct answer to three questions put
by the PM after the independent UX audit.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-33`. **Recorded, not decided.**
**Evidence for the questions:** `reviews/gates/HG1_ROUND5_UX_AUDIT.md` (findings S5, S8, I6, and
the PM verification in §8); `reviews/gates/HG1_FEEDBACK_LOG_2.md` (Problems 4, 6, and the
"Scenario lab is fine." note).
**Qualifies:** the Round-3 instruction recorded in `reviews/PM_ACCEPTANCE.md` §3 — see Part 1.
**Reopens:** nothing else.

> **This decision does not approve HG1.** HG1 remains **`REVISION_REQUIRED`** and
> `awaiting_human`. It does not unblock Priorities A–E. It authorizes work *within* the open
> gate, not past it.

---

# Part 1 — The progressive-explanation architecture is rebuilt in full

## 1.1 The decision

**[F] Approved: the full module-visibility rebuild.**

- **Explanation mode becomes application state**, not per-card state. One `APP.state.explanationMode`, set in Settings and by a persistent control, propagated to every surface.
- **Every module declares a `minMode`** — the lowest explanation mode at which it is visible at rest.
- **Quick becomes a genuinely different surface**, not a shorter one: one headline conclusion, one figure at hero scale, one visual, one analogy sentence. The six-statistic risk inventory, the statistics grid, the rolling chart, the exposure charts, the holdings table, the methodology caveat bodies and the reference-point lines are **hidden at rest in Quick**.
- **Nothing becomes unreachable.** A module hidden at a lower mode collapses to a named, one-click affordance. P9 auditability is preserved exactly.
- Per-card ladders survive as **local overrides** of the global mode.

## 1.2 The tension this resolves, stated plainly because a later reader will hit it

**The owner's Round-3 instruction said:** *"I do not want another major UX or product-architecture
redesign."* **That instruction stands for the product's information architecture, its four-surface
IA, and the C+B direction — none of which this decision touches.**

**It does not stand as a bar on rebuilding progressive explanation**, because Feedback Log 2
Problem 4 — written after it — reports that the feature does not work at all: *"Clicking on simple
and professional makes no difference for those overviews and conclusions."* The PM put the tension
to the owner explicitly rather than resolving it, and **the owner chose the full rebuild.**

**[J] An agent reading `PM_ACCEPTANCE.md` §3 alone would conclude this work is unauthorized. It is
authorized, by this record, by the same person who gave the Round-3 instruction.**

## 1.3 What constrains the rebuild — unchanged and binding

**PD-0012 §2 is not relaxed by this decision.** All three modes must render **the same underlying
deterministic fact set / Proof Packet**. Depth and which modules are visible may change; **the
underlying conclusion may not silently change.**

**[F] The mechanical guarantee is required, not optional:** a `selfcheck` assertion that, for every
claim id, `value`, `sufficiency`, `freshness` and the **Proof Packet entry set** are byte-identical
across Quick, Simple and Professional — **with a proven falsification**, per this project's
established discipline that an assertion is worthless until it has been shown to fail when its own
defect is reintroduced.

**[F] Analogy simplifies the interpretation; it never replaces the literal financial definition.**
The owner's own counter-example stands: beta must not be explained as *"7% less risk."* A new
deterministic `claim.analogyQuick` field is authored alongside the claim and rendered **beside**
the literal figure, never instead of it.

**[F] State chips are not decoration and are not suppressed at Quick.** Freshness pills and
comparability flags render at every mode as short tokens. Suppressing them would breach P3 and P5.

## 1.4 What this does not authorize

- **No new analytical breadth**, no new metrics, no new surfaces.
- **No change to any financial meaning.** Presentation only.
- **No Priority A–E work.**

# Part 2 — Typography direction

## 2.1 The decision

**[F] The audit's recommendation is adopted, not the literal Arial + Times New Roman pairing.**

| | |
|---|---|
| **Sans stack** | **Arial** at the front — uniform lining figures (safe for tabular data), metric-compatible with Helvetica, present on every target platform, which removes the current `-apple-system` / `Segoe UI` cross-machine metric drift |
| **Serif** | **kept, and confined to display headlines.** It is already implemented and already correct |
| **Body and data** | **no serif.** A serif at 11–13px in a dense numeric grid loses legibility |
| **CJK** | **explicit faces added** — `PingFang SC`, `Microsoft YaHei`, `Noto Sans SC` for sans; `Noto Serif SC` for serif; a CJK-capable mono. **No stack currently names a Chinese face at all** |
| **Sequencing** | **fix the chart scale defect first, then re-ask the owner** whether the fonts still look wrong |

## 2.2 Why the owner's literal suggestion was not taken at face value

**[J] The owner prefixed it *"I'm not too sure"*, and the audit found a measured cause that better
explains the complaint.** Chart text currently renders between **4.7 CSS px** and 17.8px on a
single page, because SVG text is sized in viewBox units and charts are scaled 0.469×–1.778×. Type
at 4.7px reads as "the fonts look wrong" long before the typeface does. **Changing typefaces to
answer that complaint would have treated a symptom.**

**[F] The owner retains the preference.** If, after the scale defect is fixed, they still want
Times New Roman, the safe change is to move it to the front of `--font-serif` for **headlines
only**. That option is preserved, not foreclosed.

**[F] Chart labels must not be moved to the monospace face** to make the width estimator correct.
That would paper over a measurement bug and degrade legibility.

# Part 3 — The internal note is removed from Scenario Lab

**[F] Approved: remove the developer-facing note rendered in Scenario Lab's UI.**

The string visible in the owner's `P8_2.png` and `P9.png` includes: *"…not something this
designer's presentation layer can resolve; see this designer's handoff."* A build note addressed
to another worker, rendered to the user.

**[F] This is a bounded content deletion. It is not a redesign of Scenario Lab**, which the owner
has accepted (*"Scenario lab is fine."*) and which is not otherwise touched this round.

**[F] The underlying analytical question stays open and recorded.** The scenario declares `-50%`
while the computed allocation change is roughly −15%; removing the note does not close that, and
it must not be read as closing it. It remains in the Round-4 record and in the open-items list.

**[J] Accepting a surface's design is not accepting an engineering note inside it.** The owner
confirmed this reading directly.

# 4 — What none of these parts does

- **None approves HG1.** It remains `REVISION_REQUIRED` and `awaiting_human`.
- **None authorizes Priorities A–E.**
- **None reopens** the C+B direction, the four-surface IA, the metric-state vocabulary,
  the deterministic-analytics boundary, the Proof Packet architecture, the OCR safety model,
  scenario isolation, the freshness/comparability model, the claim-traceability invariant, or the
  AI advisory boundary.
- **None adds analytical breadth.**
- **None resolves the beta-caveat P3 minimum or the SML x-domain.** Both are `quant_analyst`
  rulings, commissioned separately and outstanding at the time of writing
  (`methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md`). **Part 1's caveat-splitting work is
  contingent on the first of them.**
