# PD-0035 — CP3: FIFO lots; labelled partial total; HG2 on synthetic + real US/ECB data; exact daily FX waterfall

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, answering four questions put by the main
session in a Claude Code session on 2026-10-01.
**Recorded by:** that main session. **Recorded, not decided.**
**Raised by:** `quant-analyst`, `methodology/CP3_PERFORMANCE_CONVENTIONS.md` (`performance/1.0`),
items OD-P1 to OD-P4.
**Closes:** STATUS open item 17 for the purpose of HG2 (see §3).
**Supersedes:** HG1 §4.3's constant-FX attribution split, as far as §4 below states.

---

## 1. OD-P1 — Lot method: FIFO

Question: *"Which lot method should realized/unrealized gains use when a position was bought in
several lots? (Returns, TWR/MWR and attribution don't depend on it; only the realized vs
unrealized split does.)"*

Owner's answer, verbatim: **"FIFO (Recommended)"**

As presented: oldest lots sold first (pro rata within one date); matches most brokers and tax
regimes; labelled as possibly differing from the user's broker's own lot records.

Consequences: `performance/1.0` Ruling 3.3 (FIFO) is the method. Every realized/unrealized figure
carries a label that it may differ from the broker's lot records. Average cost (Ruling 3.4) stays
specified, but is not used. This is a methodology choice, not tax advice (PRD §15.3).

## 2. OD-P2 — A labelled "value of priced holdings" when the total is suppressed

Question: *"When the portfolio total is suppressed because some holding can't be valued (e.g. no
China/HK price), should a separately labelled 'value of priced holdings' be shown?"*

Owner's answer, verbatim: **"Yes, labelled, with count (Recommended)"**

As presented: it shows the sum of what can be valued, clearly labelled as partial, with the number
of unpriced holdings; the true total stays "insufficient data".

Consequences: a separate metric (not the portfolio total) with its own name and label. It is never
presented as, or summed into, the portfolio total. It states how many holdings it excludes. The
portfolio total keeps `performance/1.0` Ruling 1.4. The design label is a design task before CP7.

## 3. OD-P3 — HG2 demonstration data (STATUS item 17)

Question: *"What should the HG2 demonstration portfolio use, given there's no admissible real
China/HK price source?"*

Owner's answer, verbatim: **"Synthetic + real US/ECB (Recommended)"**

As presented: a synthetic, hand-checkable US/CN/HK portfolio (labelled synthetic), plus a real US
slice from Alpha Vantage and ECB FX. Real CN/HK price behaviour stays unproven; revisit before
CP4/HG3.

Consequences:
- The HG2 package states plainly that CN/HK price handling is shown on synthetic data only.
- Real-data evidence for HG2 covers US prices (Alpha Vantage, last 100 sessions) and ECB FX.
- A real CN/HK source is revisited before CP4 or HG3 (OQ-04b stays open for launch).
- PD-0031/PD-0032 terms stand. No Eastmoney or Sina data is admitted.

## 4. OD-P4 — FX attribution: the exact daily split

Question: *"HG1's approved design split FX attribution using a constant-FX method; the new exact
daily method makes the first bar of the approved waterfall 'local price effect' (with a separate
price–FX interaction line). Adopt the new split?"*

Owner's answer, verbatim: **"Adopt the exact daily split (Recommended)"**

Consequences: `performance/1.0` Ruling 9 (eight exact daily lines, summing exactly to the absolute
gain; Cariño-linked percentages reconciling to the TWR) supersedes HG1 §4.3's constant-FX split.
The approved waterfall's first bar is "local price effect", with a separate price–FX interaction
line. The design artifacts are updated by the designer before CP7; that is not part of this
decision.

## 5. What this decision does not do

It sets no tolerance or rounding (those are the Quant's, in `performance/1.0`), admits no data
source, and approves no gate. HG2 remains the owner's decision.
