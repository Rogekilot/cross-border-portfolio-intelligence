# PD-0083 — Pre-R8 decisions and GitHub preparation

**Status:** accepted
**Date:** 2026-11-14
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** the open items of the pre-R8 round (`reviews/HANDOVER_2026-11-14_PRE_R8.md` §1 and §3; install plan section 14 G2;
R8 runbook review TR8R-M-3 and TR8R-M-4).
**Bears on:** `data/marketdata/SOURCES.json`; `reviews/R8_RUNBOOK.md`; PD-0081 (clarified, not changed); the public GitHub copy.

## Questions and answers, verbatim

> R8 blocker G2: the alphavantage.us terms notes in data/marketdata/SOURCES.json are 1,687 bytes, but the registry (in Python and in
> the frozen gateway SQL) accepts at most 1,024, so the real publish would be refused. How should I resolve it?

**"Shorten notes (Recommended)"** — the 953-byte summary shown in the preview, keeping every condition, date and PD citation.

> R8 runbook, clean-tree rule: `.claude/settings.local.json` (local Claude Code permissions) is tracked by git and changes whenever an
> agent session runs here, so `git status --porcelain` is never empty and the R8 password rule can't be met. What should I do?

**"Untrack it (Recommended)"**

> PD-0081's stop rule says R8 stops if the real create's commit is refused or UNKNOWN. Does a create refused on its input before any
> lease or commit (e.g. a mistyped listing id, a validation error) also stop R8?

**"No: fix input, retry (Recommended)"**

> GitHub: the repo has no licence. Which should it carry?

**"MIT (Recommended)"**

> GitHub: upload the full repository (5,794 files; `reviews/` alone is 4,632 files and 193 MB of review records, evidence and
> handovers) or a curated public copy?

**"Curated copy (Recommended)"**

> GitHub curated copy, personal details: which of these should be removed or replaced in the public copy?

**"macOS username", "Broker names", "Your name"** (not ticked: "Your verbatim words").

> GitHub: single values from the licensed Alpha Vantage download (the AAPL close for 2026-09-30, and NAV figures derived from it)
> appear in 4 committed files. PD-0027/0028 say that data is internal use only. What goes into the public copy?

**"Redact them (Recommended)"**

> GitHub: this repo's commit metadata holds two personal emails and VPN hostnames (e.g. <user>@<host>), and its
> history is already pushed to Rogekilot/fin-web. With a curated copy, what about history?

**"Fresh history (Recommended)"**

### Second set (same day)

> Besides the Alpha Vantage values (now redacted), the public copy quotes about a dozen single sample prices from the
> AkShare/Eastmoney and Sina files of 2–8 Jan 2025 (e.g. a Moutai close, a Tencent float32 artifact), used as precision examples
> in 3 source comments, 1 test and 3 docs. SOURCES.json records those sources' terms as refused. Redact them too?

**"Redact them too (Recommended)"** — replace them in the public copy with invented values of the same shape, then re-run the
suite in the copy. (The count in the question was low: the values sit in 4 source files, 5 test files and 5 documents.)

> Where should I place the finished public copy?

**"~/Desktop/fin-web-public (Recommended)"**

> The MIT LICENSE needs a copyright holder. … "Copyright (c) 2026 Rogekilot". OK?

**"Rogekilot (Recommended)"**

## What this means

1. **G2.** The `alphavantage.us` `terms_check.notes` is the 953-byte summary. The full readings stay in PD-0028, PD-0031, PD-0032,
   PD-0064, PD-0066 decision 5 and PD-0072, and in git history. No code or SQL change.
2. **`.claude/settings.local.json`** is removed from the index (`git rm --cached`) and ignored. The file stays on disk unchanged.
   This makes the R8 clean-tree rule satisfiable (runbook precondition P9).
3. **PD-0081, clarified.** A create refused on its input before any lease or commit is not "the real commit refused". The owner
   corrects the input and retries, and the refusal and its code go into the HG4 package. A refusal or UNKNOWN at or after the
   real commit still stops R8 under PD-0081, unchanged.
4. **GitHub.**
   - Licence: MIT.
   - A curated public copy in a new repository, with a fresh first commit. This repository and its history are not rewritten,
     and `Rogekilot/fin-web` is left as it is.
   - In the public copy, the macOS username, the broker names and the owner's name are replaced with neutral text. The PDs keep
     the owner's verbatim answers.
   - The vendor values (the Alpha Vantage close for 2026-09-30, the price row quoted with it, and the figures derived from it) are
     redacted in the public copy. This repository keeps them; payload files stay git-ignored and local.
   - The owner makes the public copy's first commit, with the author name and email the owner chooses, and pushes it.

## Correction note (2026-11-14, main session)

The question on PD-0081 gave "a mistyped listing id" as an example of a refusal before any lease or commit. **That example was the
main session's error.** The independent review of the runbook (TR8R-M-5) found that a well-formed but wrong context, release or
listing id is checked after admission, inside the real branch. Only `422 REAL_REQUEST_INVALID` (a malformed request) and `404` (a
context the launcher does not serve) come before any lease or commit. The owner's answer stands as given ("No: fix input,
retry"), and it covers exactly those two responses. Every other refusal of a real create, and any UNKNOWN or 503, stops R8 under
PD-0081. The runbook says so, and asks the owner to check the ids against `P.json` and `F.json` before each create. If the owner
reads the answer differently, the owner says so and this note is amended.

## What this does not do

It approves no gate. It changes no product invariant, method or design. R8 still runs only from the reviewed, committed tree.
