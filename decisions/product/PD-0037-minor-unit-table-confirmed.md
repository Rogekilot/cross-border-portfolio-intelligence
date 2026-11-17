# PD-0037 — Currency minor-unit table confirmed against ISO 4217

**Status:** accepted
**Date:** 2026-10-02
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-02, adopting that session's reading.
**Recorded by:** that session. **Recorded, not decided.**
**Answers:** `performance/1.x` §18 item 1 and Ruling 2.3: the owner confirms the MEMORY rows of
`minor-units/1` against the ISO 4217 list maintained by SIX. This is HG2 package §8 item 7 and
suggested condition 2.

---

## The decision

The session presented its reading: the table (USD, HKD, CNY, EUR, GBP, CHF, SGD, AUD and CAD
with 2 minor units; JPY with 0) is correct per ISO 4217. It suggested confirming it.

Owner's answer, verbatim: **"Go with your suggestions, record them"**

**Check against the publisher:** the session read SIX's ISO 4217 List One (`list-one.xml`,
published 2026-09-17). Its `CcyMnrUnts` values are USD 2, HKD 2, CNY 2, EUR 2, GBP 2, CHF 2,
SGD 2, AUD 2, CAD 2 and JPY 0. **All ten rows match.**

## Consequences

- Every row of `minor-units/1` is **CONFIRMED** (owner, 2026-10-02, against SIX List One of
  2026-09-17). No value changes.
- **Follow-up, queued:**
  - `quant-analyst`: mark the rows CONFIRMED in `methodology/CP3_PERFORMANCE_CONVENTIONS.md`,
    with a version bump and a change note naming unaffected fixtures (Ruling 11.6);
  - then `engineer`: update the row status in `src/performance/rounding.py`, so the
    minor-unit open item no longer makes `is_conformant` False.

  This work is inside HG2's scope, not downstream of it.
- A currency added later is a new table version and needs its own confirmation.

## What this decision does not do

It does not decide HG2 or change any rounding rule.
