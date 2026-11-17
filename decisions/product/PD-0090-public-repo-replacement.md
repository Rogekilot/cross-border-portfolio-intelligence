# PD-0090 — Replace the public repository (the owner's name was recoverable from published hashes)

**Status:** accepted
**Date:** 2026-11-17 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Answers:** the independent review TR-PC2 (`reviews/TECH_REVIEW.md`, its confirmations); HG4 condition 3 (PD-0089).
**Bears on:** PD-0083 section 4 (the curated public copy); the public repository `Rogekilot/cross-border-portfolio-intelligence`.

## Context

While checking the redaction of the new public copy (PD-0089 condition 3), the independent reviewer found that the copy already
published (commit `3fa1481`) lets anyone recover the owner's full name on a laptop in seconds. Some files in the copy differ from
their private versions only by the owner's name, and the copy publishes the private versions' SHA-256 hashes. That breaks PD-0083
section 4 ("the owner's name … replaced with neutral text"). The macOS username can be confirmed by guessing the same way, but not
found blind. No practical vendor-value exposure was found in `3fa1481`.

The new copy re-derives or blanks every such hash. Its build fails if any part of a private digest remains. The third confirmation
of TR-PC2 is PASS WITH FINDINGS: no attack recovers the close, the name or the username.

## Decision

The question, verbatim:

> The public GitHub copy you pushed earlier (commit 3fa1481) lets anyone recover your full name in seconds from two file hashes.
> Pushing the fixed copy on top leaves that commit in history. How do you want to replace it?

Options:
- "Delete and recreate (Recommended)": "You delete the GitHub repository and create a new one with the same name, then push the
  fixed copy as a single fresh commit. This removes the old commit from GitHub, but any existing clones or forks keep it."
- "Force-push fresh history"
- "Push on top"

**Answer, verbatim:** "Delete and recreate (Recommended)"

## Consequences

1. **The owner deletes the GitHub repository** `Rogekilot/cross-border-portfolio-intelligence` and creates a new, empty one with
   the same name. The owner then pushes the new copy as a single fresh commit, with the same author name and GitHub no-reply email
   as before. Agents do not push, delete or create repositories.
2. **The new copy** is the build in the session notes folder, `public-copy-2026-11-17/`, made from this repository's tree that
   includes TR-PC2. Its build tool and checks stay outside this repository.
3. **Limits stated plainly:**
   - clones or forks made while `3fa1481` was public keep it;
   - so may third-party caches or archives;
   - deleting the repository does not reach them.
4. **Not decided here:** whether to ask GitHub or any archive to purge cached copies.
