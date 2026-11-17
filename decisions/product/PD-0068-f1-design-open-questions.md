# PD-0068 — Decided F1 design: the owner's answers to its open questions (§8.1 items 7–10)

**Status:** accepted (answers 1–4)
**Date:** 2026-10-24 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:** PD-0066 decisions 5–10; `implementation/CP7_F1_REAL_PATH_DESIGN.md` (uncommitted, decided
version) §3.1, §4.4, §7.1, §8.1; `reviews/CP7_E10_EVIDENCE/protocol-author/F1_AUTHORITY_EXPIRY_COMMIT_PROTOCOL_V1.md`
§5; FF1-C06.

## Context

The decided F1 design (two review rounds, 2026-10-24) left four questions that only the owner can
answer, wanted before increment R1 is built. The owner asked to go through them one at a time.

## Answer 1 (design §8.1 item 7): no in-flight completion after `valid_until`

The main session explained:
- every operation (create, read, export, reproduce) is checked against the lease when it starts;
- option (a) lets an operation admitted before `valid_until` finish within a window `W` (proposed
  10 minutes) after it;
- option (b) caps every operation's deadline at `valid_until`;
- under either, the database cannot promise that nothing at all commits after the deadline (the
  commit-processing gap, and an executor that fires the guard early).

Question asked, verbatim:

> Open item 7: may an operation admitted before valid_until finish after it?

Owner's answer, verbatim: **"(b) No, cap at the end (Recommended)"**

What this means:
- `complete_by = LEAST(admitted_at + W, valid_until)` for every lease. `W` stays an install constant;
  the real install's value is the engineer's proposal of 10 minutes, and it only shortens deadlines.
- No economic write, seal or guarded load of an operation succeeds after `valid_until`. On the
  product path, a commit whose processing starts after `complete_by` is refused by the deadline guard.
- **Not claimed:** that nothing commits after `valid_until`. The commit-processing gap and a
  guard-bypassing executor remain disclosed limits (design §3.1, E4; E10 §5; X2 stays UNSUPPORTED).
- The E10 §5 condition for in-flight completion (terms and a product decision that permit it) is not
  met and is not needed: the terms are silent, and the owner chose no completion past the end.
- The design's margin rule (`valid_until + W <= min(term_end_not_after)`) was written for option (a).
  Whether it can be relaxed under the cap is for the engineer to state in the design's next revision,
  for review. The open conformance finding R2-M1 on that rule stays open until then.

## Answer 2 (design §8.1 item 8): the ACK-loss limit is accepted

The main session explained:
- the case: an accepted create commits, the acknowledgement is lost, and the product must report
  UNKNOWN, reconcile and never retry blindly;
- PD-0059 proved it for fictional data, and PD-0066 decision 6 accepted that it must be proven again
  for the real gateway;
- before R8 no create can commit an accepted NAV, because the service refuses synthetic data and
  invented data stays synthetic (PD-0066 decision 8);
- before R8, R3 can show "UNKNOWN, no retry" on a crafted commit, and R5 can show reconciliation
  against that crafted committed state;
- (ii), a rehearsal in a throwaway real install, would create the first `synthetic = false` records
  outside the owner's database.

Question asked, verbatim:

> Open item 8: the full lost-acknowledgement sequence cannot be exercised before the real run. What do you choose?

Owner's answer, verbatim: **"(i) Accept the limit (Recommended)"**

What this means:
- **Accepted limit:** the end-to-end ordering "accepted create commits, acknowledgement lost, product
  reconciles" is not re-proven before R8. It is first exercised at the real run, if it occurs there.
- R3's and R5's exits claim only what they show: UNKNOWN with no automatic retry on a crafted commit
  (R3), and correct classification of committed, rolled-back and UNKNOWN states by the reconciliation
  code (R5). Neither claims a re-proof of the ordering.
- No rehearsal install is planned. The first `synthetic = false` records stay reserved for the real
  run (PD-0066 decision 8).

## Answer 3 (design §8.1 item 9): deviations D-1 and D-2 accepted; withdrawal tested on the real context

Questions asked, verbatim, with the owner's answers:

> Open item 9: do you accept D-1 (expiry not observable on real data) and D-2 (rollback after writes not forced) as declared deviations?

**"Accept both"**

> Should withdrawal be exercised on the real context as the last step of R8 (withdraw, see all rights refused, then renew)?

**"Yes, test it (Recommended)"**

What this means (design §7.1):
- **D-1 (expiry) and D-2 (rollback after writes) are accepted deviations** from E9's post-run list.
  - Expiry and lapse are shown on invented data only (R1), because `valid_until` is 2027-09-01 and
    the clock has no test hook (E3).
  - Rollback after writes is shown on invented data and crafted bundles only (R1, R3, R5).
  - The HG4 package states both as not collected on the real context.
- **Revocation is exercised on the real context as the last step of R8.** The owner:
  1. withdraws, so that all four rights are shown refused;
  2. renews, so that the context is live again.

  Each step is a publisher act by the owner, citing its own decision record (PD-0066 decision 7). It
  costs two real generations.
- The other E9 post-run items collectible on the real context are collected there: the correct
  error digest on a refused request, and negative cases refused before any write, including
  two-user isolation if the real-mode app can hold a second user without an economic write.

## Answer 4 (design §8.1 item 10): the expiry basis per source for the first HG4 publish

Questions asked, verbatim, with the owner's answers:

> Open item 10: the expiry basis per source for the first HG4 publish?

**"As proposed (Recommended)"**

> Do you want to pin the Alpha Vantage term start from your signup email?

**"Keep 2027-09-01"**

What this means:
- The first HG4 publish record states exactly one basis entry per member source (design §3.1, E14):

  | Source | Basis | Detail |
  |---|---|---|
  | `alphavantage.us` | `LEASE_TERM` | PD-0066 decision 5; `term_end_not_after` 2027-10-01T00:00:00Z |
  | `openfigi` | `NOT_ASSESSED` | no term evidence is recorded; an acknowledgement, evidence neither of a term nor of its absence |
  | `calendar.manual` | `NOT_ASSESSED` | the owner's own file built from public exchange notices; no licence reading |

  The context's kind is `LEASE`; `NONE` stays unreachable. The whole context lapses at `valid_until`.
- **`valid_until` stays 2027-09-01** (00:00 Asia/Shanghai). The term start is not pinned from the
  signup date.
- **Disclosed limit.** `term_end_not_after` is an upper bound. The owner's key existed by
  2026-10-01, but the exact signup date is not recorded. If the term began earlier than about
  2026-09-01, it would end before `valid_until`, and the lease would run past the licence term.
  The owner accepted the 2027-09-01 date knowing this. Pinning the signup date later, from the
  owner's Alpha Vantage account, would remove the limit. Conformance finding R2-M1 (the margin rule
  compares against an upper bound) is answered by this disclosure; the engineer states it in the
  design's next revision.

## What this does not do

It changes no file other than this record, builds nothing, and approves no gate. The decided design
stays uncommitted. Its open review findings (conformance R2-M1, R2-M2; technical TR2-M1..M4) still
need a design revision and review before R1. This record supplies the owner answers that the
revision must reflect.
