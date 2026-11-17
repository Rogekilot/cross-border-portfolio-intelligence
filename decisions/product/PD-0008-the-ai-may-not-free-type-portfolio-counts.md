# PD-0008 — The AI may not free-type a count of the user's own portfolio

**Status:** decided (product contract, within PM authority) — **presented to HG1 for confirmation**
**Date:** 2026-09-04
**Decided by:** `product_manager`, session `fin-web-77`, worker `pm-01`
**Raised by:** `review-01`, `technical_review` round 3, finding **N-16** — routed to the
product owner rather than to the engineer, because it "settles a product question inside a
grammatical rule." That routing was correct.
**Binds:** `implementation/FEATURE_TECH_PLAN.md` §4.3a, non-claim form 3

---

## The finding

§4.3a's allowlist exempts a small set of "structural ordinal/count phrases" from the
no-digit rule. `review-01` observed that its six permitted nouns **are all portfolio nouns**,
so these pass the scan and reach the user as AI free text:

> "You hold **7 positions**."   "**5 accounts**."

## Why this is a product decision and not a grammar fix

A count of the user's own holdings is **a fact about the portfolio**. It is derived from the
ledger, it is exactly the class of thing P1 reserves to the deterministic engine, and it is
wrong in precisely the way §41.3 describes if the model miscounts — it looks authoritative
and there is nothing to check it against. That the AI arrived at it by counting rather than
by arithmetic is irrelevant to P1, which is about **who originates a presented number**, not
about which operation produced it.

The exemption was reasonable-looking as grammar and wrong as product contract. That is
exactly the shape of defect a purely technical review would be entitled to miss, and
`review-01` did not miss it — it declined to resolve it, which is better.

## The ruling

**Split form 3. The two cases are not alike:**

| Phrase | Disposition | Why |
|---|---|---|
| "top **3** holdings", "bottom **5** performers" | **Exempt — stays allowed** | The digit is a *selection parameter* — it describes which slice is being discussed. It asserts nothing about the portfolio that could be true or false. |
| "you hold **7** positions", "**5** accounts", "**12** holdings" | **NOT exempt — must come through a slot** | The digit is a *claim*. It states a fact about the user's portfolio and can be wrong. |

The operative test is not the noun. It is: **does the number assert something about the
portfolio that could be false?** If yes, it is a claim and belongs in a `{{slot: ...}}`
resolved against a logged Tool Gateway call, like every other portfolio fact. If it merely
selects or orders what is being discussed, it is not a claim.

Counts of the user's holdings, positions, accounts, or transactions are **claims**. They
travel through slots.

## What this does not decide

- **The remaining exemption leaks are the engineer's**, not mine: form 1's missing adjacency
  guard (`250BP`, `12M`, `3X`, `8K`), form 2's bare four-digit year range admitting an index
  level ("closed at **1950**"), and whether matching is whole-token or substring. Those are
  mechanical defects in a rule, not product questions, and they are dispatched as such.
- **Whether a slot-delivered count needs its own methodology entry.** A position count is
  not a metric in §33's sense. Out of scope here.

## Known limitations of this decision

- It makes the allowlist slightly more restrictive and therefore slightly more prone to false
  rejection — the model must now request a count rather than state one. `review-01`
  established that this is the safe direction: under an allowlist, reducing false rejections
  means *adding to a reviewable enumeration*, never turning a tolerance dial.
- I am ruling on the boundary between "selects" and "asserts" without an exhaustive
  enumeration of phrases on either side. The test above is stated in product terms and will
  need concrete pattern work at CP9; a phrase that is genuinely ambiguous should fail closed
  and be surfaced, not guessed.
