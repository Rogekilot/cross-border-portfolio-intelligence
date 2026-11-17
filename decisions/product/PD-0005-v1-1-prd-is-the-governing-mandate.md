# PD-0005 — `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` is the governing product mandate

**Status:** decided — **by the human product owner**, recorded by `product_manager`
**Date:** 2026-09-03
**Decided by:** the designated human product owner (recorded verbatim below)
**Recorded by:** `product_manager`, session `fin-web-09`, worker `pm-01`
**Task:** `feature-development/prd` (post-completion amendment; no scope change)
**Closes:** OQ-03 (`specs/FEATURE_PRD.md` §9), assumption A-01 (§8)
**Related:** [PD-0001](PD-0001-prd-reset.md), [PD-0004](PD-0004-increment-1-scope-and-hg1-ordering.md)

---

## The decision, as given

> "Human product-owner decision: `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` is the
> authoritative governing product mandate for this project unless I explicitly supersede
> it. Record that decision and close OQ-03."

## What it settles

`specs/FEATURE_PRD.md` §9 recorded OQ-03:

> Is the draft status of source PRD v1.1 (A-01) intentional? Is a newer version pending?

and §8 recorded the matching assumption:

> **[A] A-01.** Source PRD v1.1 dated 2026-09-02 is current and approved as the product
> mandate. It is marked "Draft v1.1" in its own header — I am treating a draft as the
> mandate because it is the only mandate that exists.

Both are now closed. `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` is authoritative.
The "Draft v1.1" string in that file's own header is **not** a limit on its authority;
the owner's decision supersedes the label. A-01 ceases to be an assumption and becomes a
recorded fact with a named decider.

## What it does not settle

- **It is not an approval of HG1, or of any other gate.** HG1 approves the CP0 product
  contract and architecture proposal. This decision only fixes *which source document*
  that proposal must be faithful to. Source PRD §38.1 is unchanged: no agent may treat
  this, or anything else short of an explicit gate decision, as gate approval.
- **It does not approve `specs/FEATURE_PRD.md`.** That document remains
  *authored — not approved*.
- **It does not close OQ-01, OQ-02, OQ-04, or OQ-05.** OQ-01 in particular (the §32
  metric-state vocabulary) is still open and is still needed before `implement` builds I2.
- **It does not freeze the mandate.** The owner reserved explicit supersession. A newer
  version, when the owner declares one, replaces v1.1 and invalidates work that depended
  on the difference.

## Consequences

1. The source-of-truth order in `CLAUDE.md` rung 4 now resolves without qualification:
   v1.1 is the approved specification for this project.
2. `ux_planning` and `tech_planning` may proceed against v1.1 without carrying A-01 as
   an open exposure. Their briefs cite this decision.
3. Where an increment artifact disagrees with v1.1, **v1.1 wins and the disagreement is a
   defect in the increment artifact** — to be reported, not resolved locally
   (`specs/FEATURE_PRD.md` §0).
4. Any future claim that a different document governs must cite an explicit supersession
   by the human product owner, recorded as a decision in `decisions/product/`.

## Known limitations of this record

- The decision was given in-session and is transcribed here verbatim. This file is the
  durable record; the conversation is not.
- No checksum of `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` is pinned by this
  decision, so a later silent edit of that file would not be detected by this record
  alone. `PACK_CHECKSUMS.sha256` is the repository-level mechanism for that and is not
  extended here.
