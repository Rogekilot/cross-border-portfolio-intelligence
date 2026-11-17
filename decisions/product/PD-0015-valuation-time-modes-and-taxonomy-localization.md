# PD-0015 — V1 has two valuation-time modes; taxonomy display labels are localized

**Status:** accepted
**Date:** 2026-09-06
**Decided by:** the designated **human product owner**, in the round-4 completion instruction.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Relates to:** PD-0012 (bilingual V1, canonical identifiers), PD-0014 Part 1 (session-aware
freshness), `methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md` §5.4.
**Reopens:** nothing.

---

# Part 1 — V1 supports a Current / as-of-now mode

## 1.1 The decision

**Yes. V1 supports an "as-of-now / latest available" portfolio mode in addition to dated
historical snapshots.**

Two **valuation-time modes** over one deterministic architecture:

| Mode | Definition | Freshness states |
|---|---|---|
| **Current / Latest** | portfolio evaluated against the **latest permissible** market/reference data | `LIVE`, `DELAYED`, `END_OF_DAY` etc. may all be meaningful, depending on market and provider state |
| **Historical as-of** | portfolio evaluated at a **specific historical cutoff** | **no input may post-date the cutoff**; `LIVE` must not be used merely to make the state reachable |

**[F] They are not two analytics systems.** The owner was explicit: *"Do not create two separate
analytics systems. They are two valuation-time modes over the same deterministic
architecture."*

## 1.2 The question this answers, and why it was open

`quant_analyst`'s as-of rule (§7.3) entails that a snapshot taken as of a past close cannot
contain a live input. Applied to the fixture, that correctly moved `us_equity` from `LIVE` to
`END_OF_DAY` — and left the `LIVE` state **defined but unreachable anywhere in the product**.

That was the bad outcome: a state in the vocabulary with no referent. This decision gives
`LIVE` a referent — the Current mode — rather than deleting it or reaching it by weakening the
as-of rule.

**[J] The failure this forecloses is the one worth naming:** reaching `LIVE` by relaxing the
as-of rule would have made a dated snapshot silently include post-cutoff data. That breaks P12
determinism — same inputs and as-of date must give the same output — and it is exactly the
kind of quiet correctness loss this whole round was convened to eliminate. Two modes with
different rules is the honest structure; one mode with a rule bent to fit a badge is not.

## 1.3 Implementation boundary — recorded, as the owner required

**[F]** *"If full Current-mode computation belongs in CP1 rather than HG1, HG1 only needs the
interaction/product contract represented honestly. Record the implementation boundary."*

| Scope | Where |
|---|---|
| The **interaction and product contract** — that two modes exist, how they differ, which freshness states each admits, and that no input may post-date a historical cutoff | **HG1**, represented honestly in the prototype |
| **Full Current-mode computation** — live/delayed provider feeds, per-market session state, provider freshness plumbing | **CP1 and later.** Requires the real market-data spine (Priority A), which is blocked until HG1 is approved |

**[J]** The prototype must not simulate a live feed to make `LIVE` appear. Representing the
contract honestly means showing that the mode exists and what it would admit — not
manufacturing a state the fixture cannot support. Inventing a live value to populate a badge
would be the same defect class as the four claims this round was convened to fix.

## 1.4 What this does not authorize

- No Priority A–E work. The market-data spine remains blocked until HG1 is approved.
- No second analytics stack, no parallel metric definitions, no mode-specific methodology.
- No relaxation of the as-of rule for historical snapshots.

# Part 2 — Taxonomy display labels are localized

## 2.1 The decision

**[F] Sector and asset-class taxonomy display labels are translated into the selected UI
language, while canonical internal taxonomy identifiers are preserved.**

Example given by the owner: `Information Technology` → `信息技术`.

## 2.2 The line this draws, which PD-0012 left ambiguous

PD-0012 §3 established that canonical identifiers are never translated. **A taxonomy label is
not a canonical identifier**, and the two were being conflated — which is why
`Information Technology` was left in English on an otherwise-Chinese screen.

**Never translated or mutated:**

- ticker (`0700.HK`, `600519.SS`)
- MIC (`XHKG`, `XSHG`)
- exchange
- canonical security ID
- **canonical internal taxonomy identifiers** — the code a sector maps to, as distinct from its display label

**Translated for display:**

- sector display labels (`Information Technology` → `信息技术`)
- asset-class display labels
- the presentation-layer classification labels introduced for §6.2 (pooled fund / fixed income / structured)

**[F] A security may display a localized or common name where appropriate while retaining
canonical identity** — 腾讯控股 / Tencent Holdings alongside an untouched `0700.HK`.

## 2.3 The invariant that keeps this safe

**[J]** The rule is: **translate what a human reads, never what a system joins on.** A display
label is read; an identifier is matched. If a string is ever used as a key — for a lookup, a
join, a comparison, a switch — it is an identifier and localizing it is a correctness defect,
not a localization improvement.

This matters concretely here: `classifySectorExposure()` groups holdings by their `sector`
value. If that grouping keys off the **displayed** label, translation silently changes the
grouping. The classification must key off the canonical identifier and translate only at
render. **A self-check assertion that exposure groupings are identical in both languages would
enforce this** and is worth having, since the failure is invisible on either screen alone.

# 3 — What neither part does

- Neither approves HG1. It remains `REVISION_REQUIRED` and unapproved.
- Neither authorizes Priorities A–E.
- Neither claims V1 localization is complete. Per the owner's §4: representative Overview and
  Analytics bilingual screens are **sufficient for HG1**; production-wide coverage remains a V1
  implementation requirement; and **Chinese register, fluency and glossary quality remain
  explicitly unverified by a qualified language reviewer.** That gap must not be reported as
  closed.
- Neither adds analytical breadth.
