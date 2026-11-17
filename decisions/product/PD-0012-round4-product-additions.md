# PD-0012 — Round-4 human-approved product additions: reporting currency, explanation modes, bilingual V1, colour convention

**Status:** accepted
**Date:** 2026-09-06
**Decided by:** the designated **human product owner**, in the round-4 HG1 feedback log and in
direct answer to an escalated question.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Source:** `~/Desktop/HG1_Feedback_Log_Revision_Required.md` §§10, 11, 12, 13.
**Reopens:** nothing. **Supersedes:** the four-level explanation-mode model in
`designs/FEATURE_DESIGN.md` §D2 (see §2 below).

---

## 1. Reporting Currency — USD | CNY (feedback log §10)

**[F] Approved as a product capability, not a display format.** The owner was explicit:
*"Record this as **Reporting Currency**, not mere display formatting."*

**[F] The production contract must make reporting-currency switching consistently affect:**
current portfolio value; P&L; the historical portfolio series; benchmark-relative comparisons
where applicable; FX attribution; reporting-currency-dependent risk series where applicable;
Proof Packet / evidence values; and formatting.

**[F] Native security currency remains distinct from reporting currency.**

**[F] Historical reporting-currency performance must ultimately use *historical* FX, not the
current rate applied retrospectively.**

**[J] That last requirement is the load-bearing one and the most likely to be got wrong.**
Applying today's FX rate to a historical series is the single most common way a cross-border
product produces a number that is reproducible, confidently displayed, and wrong — it silently
restates history every time the rate moves, which also breaks P12 determinism (same inputs and
as-of date must give the same output). It belongs in `methodology/` before implementation, and
it is a `quant_analyst` + `engineer` obligation at CP1, not a UI concern.

**[F] The HG1 prototype may simulate the switch.** It is a design artifact; a real
historical-FX restatement is Priority D work and is blocked until HG1 is approved.

## 2. Explanation modes — Quick | Simple | Professional (feedback log §11)

**[F] The four-level model is replaced by three.** **`Investor` is removed.**

| Mode | Answers |
|---|---|
| **Quick** | *What happened?* — conclusion, essential facts, minimal supporting detail |
| **Simple** | *What happened and why does it matter?* — same professional analytics, plain language, useful analogy, interpretation, no loss of underlying truth |
| **Professional** | what happened; how it was measured; assumptions; benchmark; window/frequency; methodology; limitations; decomposition; evidence; portfolio implications |

**[F] Analogy must simplify the interpretation, not replace the literal financial definition.**
The owner's own example: beta must not be explained as simply *"7% less risk."*

**[F] The three modes must be renderings of the same underlying deterministic fact set / Proof
Packet** — `deterministic facts → interpretation → Quick / Simple / Professional` — **not three
independent AI conclusions.** Depth may change; the underlying conclusion must not silently
change unless new evidence is introduced.

**[F] Professional mode is not forecasting mode.** It may use rigorous frameworks and scenario
analysis; it must not become forward prediction, personalised trade instruction, guaranteed
outcome, or unsupported optimisation advice. Any optimisation framing must expose assumptions,
constraints and objective function.

**[J] This supersedes `designs/FEATURE_DESIGN.md` §D2's four-level depth model**, which is
otherwise accepted baseline. It is a genuine change to an accepted contract, made by the owner
who owns it — and it is narrow: the *ladder mechanism*, its caveat-preservation guarantee (P3)
and the evidence path (§D4) are untouched. Only the number and naming of the rungs change.

**[J] The "same fact set" rule is the strongest constraint here and the one to design against**
— it is P1 applied to explanation depth. Three modes that reach three different conclusions
would mean the prose, not the engine, is deciding what is true.

## 3. Bilingual V1 — English | 简体中文 (feedback log §12)

**[F] Approved as a V1 addition.** Localisation must cover navigation, core UI, explanations,
warnings, Evidence & Methodology, OCR review, Scenario Lab, contextual AI responses, Settings,
and metric names.

**[F] Canonical identifiers remain independent of localisation.** The owner's example:
腾讯控股 / Tencent Holdings, `0700.HK`, `XHKG`, `HKD`.

**[F] Three layers stay separate:** interface language; professional financial terminology;
canonical security identity. **Translation must never alter security identity.**

**[F] Representative full screens must exist in both languages.** *"Do not prove localization
only by translating the Settings panel."*

**[J] Layout is the real risk, not translation.** Chinese financial terms are frequently much
shorter than their English equivalents while some regulatory phrases are far longer — which
means every fixed-width decision made during the Checkpoint A polish pass (the chart families,
the holdings column-width grid, the freshness pills) is now under test in a second language.
The column grid was sized against `CN A-share · Stale` as its worst case; a Chinese rendering
changes that worst case. §12.2's demand for full screens in both languages is exactly right
and must not be reduced to a token translation.

**[A] Scope assumption, stated rather than assumed silently:** this is interface localisation.
It does not imply localised market data, localised regulatory disclosures, or a Mainland China
compliance review — §31 already requires specialist review before commercial launch there, and
this decision does not discharge it.

## 4. Gain/loss colour convention — user-selectable, defaulting to green-up (feedback log §13)

**[F] Decided by the owner on escalation: a user-selectable convention, defaulting to
green-up / red-down.**

The ambiguity is genuine and cultural: green-up/red-down is the common international
convention, red-up/green-down the common Mainland China one. §13 forbade resolving it
silently, and the PM did not.

**[F] Regardless of the setting: direction must also be carried by sign, arrow or text.
Colour must never be the sole encoding.** This is already implemented — the ▲/▼ glyphs and
explicit signs added in the Checkpoint A polish pass — and it is what makes a user-selectable
convention safe rather than confusing: a reader who has the *other* convention in mind still
reads the direction correctly from the glyph and the sign.

**[J] The default matters less than the redundancy.** With colour as the sole encoding, a
wrong-convention default would invert meaning for a whole audience. With glyph and sign
carrying direction, the colour setting is a familiarity preference, not a correctness one.

**[J] It sits with the other two user preferences** — reporting currency and language — which
is coherent: all three are the same kind of setting, a cross-border product adapting to where
its user sits. §13 cautioned against adding a selectable convention automatically; it was not
added automatically, it was escalated and chosen.

## 5. What these additions do not authorise

- **No new analytical breadth.** Feedback log §26 is explicit: no factor models, no ETF
  look-through, no stock-picking recommendations, no forward expected-return prediction, no
  automated rebalancing, no tax advice, no derivatives analytics, no institutional analytics,
  no trading or execution.
- **No Priority A–E work.** §27 keeps all five blocked until HG1 is explicitly approved.
- **No HG1 approval.** HG1 remains `REVISION_REQUIRED` and human-controlled.
- **No reopening** of the C+B direction, the four-surface IA, the metric-state model, the
  deterministic-analytics boundary, the Proof Packet architecture, the OCR safety model,
  scenario isolation, or the AI-grounding principles.
