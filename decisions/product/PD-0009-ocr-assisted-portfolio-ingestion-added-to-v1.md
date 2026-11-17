# PD-0009 — OCR-assisted portfolio ingestion is added to V1 scope

**Status:** accepted
**Date:** 2026-09-04
**Decided by:** the designated **human product owner**, explicitly and in their own words.
**Recorded by:** `product_manager`, worker `pm-01`, session `fin-web-12`. **Recorded, not decided.**
**Verbatim instruction:** `reviews/gates/HG1_DIRECTION_SELECTION.md` §2, item 4.
**Normative requirement:** `specs/OCR_INGESTION_ADDENDUM.md`
**Supersedes:** nothing. **Reopens:** nothing.

---

## 1. The decision

OCR-assisted portfolio ingestion — the user supplies a portfolio screenshot, a
brokerage/account screenshot, or a supported statement representation, and the system
extracts candidate holdings, transactions and account fields for human review — **is in V1
scope**, on the workflow `Upload → Extract → Resolve → Stage → Review → Confirm → Commit`.

**Why this needed a decision record rather than an interpretation.** The owner was explicit:
*"Treat this as a new human product requirement, not as an implication of the prior PRD."*
They were right to insist. `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` §27 makes
**manual entry and CSV import** Core V1 and says nothing about images or OCR. The nearest
roadmap item — *"improved onboarding/import automation"* — sits in **§5.4 / the V1.5 lane**,
not V1. So this is a genuine forward-pull of scope across a version boundary.

**Authority.** `roles/product_manager.json` lists *"Material scope change against the PRD"*
under `requires_approval`. This is one. The approval is the owner's own instruction, which is
what that clause requires — not something the PM inferred, and not something the PM could
have decided alone. §5.3's explicit out-of-V1 list was checked: OCR is **not** on it, so this
is a scope *addition*, not an override of a prohibition. That distinction matters for anyone
auditing this later.

## 2. Bounded impact analysis

Bounded as the owner directed: this analysis touches only what the addition actually reaches.
**No unrelated validated contract is reopened.** Where an impact belongs to a role that is not
the PM, it is named and left with that role rather than resolved here — inventing an
engineering or methodology answer to look complete is the failure this harness is built
against.

### 2.1 Governing PRD — `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md`

| Section | Impact |
|---|---|
| §5.2 / §5.3 V1 scope | **Additive.** OCR ingestion joins V1. §5.3's out-of-V1 list is untouched — nothing is being removed from it. |
| §5.4 V1.5 candidates | *"Improved onboarding/import automation"* is now **partially pulled forward.** Whether the remainder of that item stays in V1.5 is the owner's call; this decision pulls forward only image/statement-assisted ingestion. |
| §6 Information architecture | Additive: an ingestion/staging surface. Per the owner's objective 6 it is **inside Portfolio**, not a new primary tab. |
| §27 Manual Entry and CSV Import | **The natural home.** OCR is a third ingestion route alongside §27.1 manual and §27.3 CSV, and it inherits §27.3's existing discipline wholesale — column mapping, preview, identifier validation, ambiguous-ticker flagging, user correction, quarantine, import report. §27.3's *"Do not silently 'guess' ambiguous securities"* already governs OCR and needs no new rule. |
| §10 Security and Instrument Identity Model | **Load-bearing.** OCR produces a *string a model read off an image*, which is a materially weaker identity signal than a CSV-supplied identifier. The instrument-resolution contract must treat it as such. The absent-FIGI-fallback gap already recorded in `PM_SESSION_HANDOFF.md` §4 item 8 becomes **more** pressing, not less. |
| §21 / §33 Evidence and Proof Packet | **Extended** — see 2.5. |
| §30 Security and Privacy | **Materially affected** — see 2.6. This is the sharpest impact in this analysis. |
| §32 Data sufficiency states | **Must NOT be extended.** See 2.4. |
| §34 / NFR-001 Determinism | **Affected** — see 2.7. |

### 2.2 Acceptance criteria

`specs/FEATURE_PRD.md` is the **INC-001/CP0** increment contract, and CP0 is *product contract
and architecture proposal* — no ingestion is implemented in it. Therefore:

- **No existing AC (AC-01…AC-20) is invalidated, weakened, or reopened.** OCR does not touch
  what CP0 asserted. AC-15's twice-corrected equivalence, AC-10's P1 mechanism, AC-16/17's
  registry rules all stand exactly as accepted.
- **New acceptance criteria belong to the increment that implements ingestion**, not to CP0
  retroactively. `specs/OCR_INGESTION_ADDENDUM.md` states them as requirement-level
  obligations (OCR-1 … OCR-11) so the future increment inherits them rather than re-deriving
  them.
- **One CP0-adjacent consequence:** the §38.5 checkpoint sequence (CP1 = ledger, positions,
  cash, point-in-time reconstruction) now has a downstream consumer it did not have. The
  ledger's write path must be able to accept a *human-confirmed staged batch* as a first-class
  origin. That is a CP1 input, and it is flagged for whoever authors CP1's PRD — **it is not a
  reason to reopen CP0.**

### 2.3 UX design — `designs/FEATURE_DESIGN.md`

Additive and confined to §D1's Holdings/Transactions area. The eleven-surface IA gains an
ingestion/staging experience inside Portfolio. §D2 (four-level depth), §D3 (metric states),
§D4 (evidence), §D5 (freshness) are **re-expressed, never re-decided** — that is the standing
rule of this whole revision cycle.

One genuinely new UX obligation with no precedent in the current design: **a staging surface
that is visibly not the portfolio.** The nearest existing analogue is §D1.7 / P8's
ACTUAL-vs-SCENARIO separation, and the same reasoning applies — staged candidate data is *not
yet* portfolio state, exactly as a scenario result is *not* a holding. The designer building
this should reuse that mechanism's logic rather than inventing a second, weaker one. **This is
a design recommendation from the PM, not a design ruling; the mechanism is the designer's.**

### 2.4 Metric-state contract — the one place this could do real damage

**OCR field confidence and metric sufficiency state are different vocabularies and must never
be merged.** `AVAILABLE` / `LIMITED` / `INSUFFICIENT_DATA` describe *whether a computed metric
is supported by enough data to be presented* (§32, P5). OCR confidence describes *how sure an
extractor is that it read a character correctly*. Rendering a low-confidence OCR field as
`LIMITED` would be a category error that quietly corrupts a validated contract — and PD-0006
already established that this vocabulary is **layered**, which is precisely the discipline that
forbids this.

`INSUFFICIENT_DATA`'s rule does carry over by analogy, and the owner independently arrived at
the same principle: **a missing field stays missing.** Item 6 and item 7 of the owner's
instruction — *"preserve missing fields as missing"*, *"never invent values merely to complete
a row"* — are the ingestion-layer statement of P5. That parallel is worth stating; the
vocabularies still stay separate.

### 2.5 Evidence model

**Extends the model in a direction it was built for.** §21/P9 requires an important insight to
be auditable back to its inputs and method. OCR adds a new *kind* of input whose provenance is
an image region.

- The owner's item 2 — *"preserve the source location/evidence for extracted values where
  feasible"* — is a Proof-Packet-shaped requirement. A confirmed OCR-sourced position should
  carry, for the life of that ledger entry, that its origin was an extraction, from which
  document, from which region, at what confidence, and **which human confirmed it**.
- **The unresolved question, and it is a real one:** the current Proof Packet is defined for
  *computed* claims. An ingested *input* is a different object. Whether ingestion provenance
  belongs in the Proof Packet schema, in the ledger entry, or in a separate lineage record is
  an **architecture decision belonging to `engineer` and `harness_architect`** — flagged, not
  answered here.

### 2.6 Security and privacy — the largest impact, and it contradicts a current assumption

PRD §30.1 records the MVP baseline as including *"no brokerage credentials because broker
integration is out of V1."* That assumption held while every ingestion route was typed or
CSV-supplied. **A brokerage screenshot breaks it.** A user photographing their broker's
interface can capture, in one image: account numbers, account holder name, full position and
cash balances, and — plausibly — a logged-in session, a partially masked credential, or an
MFA artifact. The product would then be *storing* that image, because item 2 requires
preserving source location as evidence.

This is not a reason to refuse the scope addition. The owner may well accept every bit of this
risk, and §30 explicitly deprioritizes security engineering until analytical value is
validated. **It is a reason to record plainly that §30.1's stated posture no longer describes
the product**, so the owner is accepting a known change rather than an invisible one:

1. **Uploaded images are a new class of sensitive artifact.** Retention, deletion, and
   encryption-at-rest for them are §30.2 "deferred hardening" items today; an image store may
   deserve promotion out of "deferred."
2. **A production OCR engine may be a third party.** If extraction runs off-device, portfolio
   and account data crosses a vendor boundary — which touches §31's cross-border data review
   for Mainland China users directly. No network egress exists in this harness today and no
   vendor is provisioned, so this is a future-provisioning question, not a present one.
3. **Credential capture is foreseeable.** Whether the product must detect and refuse or redact
   credential-bearing regions is a product-policy question the PM cannot settle alone.
4. **The prototype is unaffected.** It simulates OCR with synthetic fixtures and uploads
   nothing. None of the above is a blocker for HG1.

**Escalated, not resolved.** Items 1–3 need the owner and `harness_architect`. They are
recorded here so they cannot be lost.

### 2.7 Determinism (P12, NFR-001, §34)

A model-based extractor is **not** deterministic: the same image may not yield identical
candidate fields across versions. This does **not** breach P12, and the reason is structural
rather than convenient: **P12 binds the analytics computed from the committed ledger**, and
nothing reaches the ledger without explicit human confirmation (item 11). The non-deterministic
step sits *before* the deterministic boundary, exactly as a human typing a position does.

**The condition that makes that argument true, which must be written down before it is
relied on:** the *confirmed staged batch* — not the image, not the extractor — must be the
persisted, replayable input. If the ledger's history can only be reconstructed by re-running
OCR, determinism is broken. Whether that is satisfied is `engineer`'s to answer at CP1;
`quant_analyst` has no stake here, because no metric methodology changes.

### 2.8 Technical plan — `implementation/FEATURE_TECH_PLAN.md`

Untouched by this decision. The plan covers CP0; ingestion is CP1-and-later. The two
CP1 preconditions already recorded (N-6, the undelivered JSON Schema; N-3, methodology
registry key/version discipline) are **unchanged in priority**. Two new CP1 inputs are added
to the record: the ledger must accept a confirmed staged batch as an origin (2.2), and
ingestion provenance needs a home (2.5).

## 3. What this decision does NOT do

- It does not approve HG1. HG1 remains `REVISION_REQUIRED` and unapproved.
- It does not authorize CP1 or any implementation.
- It does not reopen the metric-state contract, the deterministic-analytics boundary, the
  Proof Packet architecture, benchmark handling, freshness, scenario isolation, AI grounding,
  or the accepted analytical coverage.
- It does not require a production OCR pipeline for HG1. The prototype simulates extraction,
  by the owner's explicit instruction.
- It does not resolve the security/privacy questions in 2.6, the evidence-schema question in
  2.5, or the determinism condition in 2.7. Those are flagged for their owners.

## 4. Open items this decision creates

| # | Item | Owner |
|---|---|---|
| OCR-OQ-1 | Does ingestion provenance live in the Proof Packet, the ledger entry, or a separate lineage record? | `engineer` + `harness_architect` |
| OCR-OQ-2 | Retention, deletion and encryption posture for uploaded source images — does it stay in §30.2 "deferred"? | human owner + `harness_architect` |
| OCR-OQ-3 | Must the product detect and refuse or redact credential-bearing regions of an uploaded image? | human owner |
| OCR-OQ-4 | Is a third-party OCR vendor acceptable, given §31 cross-border data review for Mainland China users? | human owner |
| OCR-OQ-5 | Confirmation that the persisted, replayable ledger input is the confirmed staged batch, not the image | `engineer`, at CP1 |
| OCR-OQ-6 | Does the rest of §5.4's "improved onboarding/import automation" stay in V1.5? | human owner |
| OCR-OQ-7 | Instrument identity resolution from an OCR-read string, given there is still no FIGI fallback | `engineer` + human owner |
