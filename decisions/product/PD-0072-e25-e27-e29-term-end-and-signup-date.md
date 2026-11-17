# PD-0072 — E25 and E27 accepted, E29 kept, term-end instant kept, Alpha Vantage signup date pinned

**Status:** accepted (answers 1–5)
**Date:** 2026-10-25 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0066 decision 5; PD-0068 answer 4; `implementation/CP7_F1_REAL_PATH_DESIGN.md` (committed
`8cf9066`):
- 3.1, including its HG4 block;
- 8.1 item 4 and the "For the PM" list;
- 8.2 E25, E27 and E29;
- 7.1 rows R1, R7 and R8.

It also bears on `data/marketdata/SOURCES.json` (`alphavantage.us`).

## Context

The owner asked for a progress report and a list of pending questions. The main session listed five
that could be answered at any time:

| # | Question as listed |
|---|---|
| 1 | **E25, date correction.** A renewal may set an earlier `valid_until`. This is what makes your "pin the signup date later" option work. Accept it, or keep the first form, in which the date can never move earlier. *My pick: accept.* |
| 2 | **E27, admission probe.** R8 shows the export right refused through a direct test of the gateway. Accept it, or the HG4 package says only three of the four rights were shown refused. *My pick: accept.* |
| 3 | **E29, optional.** Keep or drop the line in the superuser-check output that shows whether each real role can log in. *My pick: keep; it is a print only.* |
| 4 | **Optional: which licence term-end instant.** Keep `2027-10-01T00:00Z` as decided, or take the earlier `2027-09-30T16:00Z`. Nothing in HG4 depends on the difference. |
| 5 | **Optional: pin your Alpha Vantage signup date** from your account. That would remove the disclosed limit that the term end is only an upper bound. |

## Answers, verbatim

> 1. Accept
> 2. Accept
> 3. Keep
> 4. Keep 2027-10-01T00:00Z
> 5. 2026-10-01

## What this means

1. **E25 is the owner's.** A renewal may carry an earlier `valid_until`, a date correction, with the
   record a renewal needs. Built in R1 (`11c804a`).
2. **E27 is the owner's.** R8 shows the export right refused through the admission probe. The probe
   is built in R7 and labelled "direct gateway admission, not a product route" in its output and in
   the HG4 package.
3. **E29 is kept.** The preflight output prints each real role's `rolcanlogin`. It is a print only
   and never refuses.
4. **`term_end_not_after` stays `2027-10-01T00:00:00Z`**, as PD-0068 answer 4 recorded it.
5. **The Alpha Vantage term start is pinned at 2026-10-01** (the owner's signup date).
   - The Annual License Term therefore ends on 2027-10-01. It then renews for one-year terms unless
     either party gives 30 days' prior written notice (PD-0066 decision 5, the owner's reading 2).
   - The owner gave the date and no time zone. Read either way (UTC or Asia/Shanghai), the term ends
     no earlier than 2027-09-30T16:00:00Z. That is after `valid_until` (2027-09-01 00:00
     Asia/Shanghai = 2027-08-31T16:00:00Z). So the lease cannot run past the first term.
   - **The disclosed limit of PD-0068 answer 4 is answered.** That limit said that if the term began
     earlier than about 2026-09-01, the lease would run past the licence term. It no longer applies,
     because the start is pinned and is later than 2026-09-01. `valid_until` stays 2027-09-01. No
     date correction (E25) is needed.
   - The basis entry stays `LEASE_TERM`, with `term_end_not_after` `2027-10-01T00:00:00Z` (answer 4).
     The HG4 publish record may now cite this record for the pinned start. The design's HG4-block
     wording ("an upper bound… no lower bound is recorded") is to be revised to cite this pin, in the
     next design revision, for review.
   - The main session records the pin and the PD-0066 decision 5 reading in the `alphavantage.us`
     terms check of `data/marketdata/SOURCES.json` (design 7.1a item 5, which gates R4a's exit and R8).

## What this does not do

It builds nothing and approves no gate. The design is not edited by this record. Its next revision
cites it.
