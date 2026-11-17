# Requirements addendum — OCR-assisted portfolio ingestion (V1)

**Status:** normative. **In V1 scope** by human product-owner decision, 2026-09-04.
**Decision record:** `decisions/product/PD-0009-ocr-assisted-portfolio-ingestion-added-to-v1.md`
**Verbatim source instruction:** `reviews/gates/HG1_DIRECTION_SELECTION.md` §2, item 4
**Authored by:** `product_manager`, worker `pm-01`, session `fin-web-12`
**Governing PRD:** `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` — this addendum extends
§27 (Manual Entry and CSV Import) and nothing else.

> **This is a requirement, not an approval.** HG1 remains `REVISION_REQUIRED` and unapproved,
> and nothing here authorizes implementation. It exists so the requirement is written down at
> the moment it was given, rather than surviving only in a conversation.

Evidence markers follow `specs/FEATURE_PRD.md` §0: **[F]** fact, **[A]** assumption,
**[J]** PM judgment, **[E]** estimate.

---

## 1. Requirement

**[F]** V1 shall support OCR-assisted portfolio ingestion, accepting a supported:

- portfolio screenshot/image;
- brokerage/account screenshot;
- supported statement representation.

**[F]** The workflow is: **Upload → Extract → Resolve → Stage → Review → Confirm → Commit.**

**[J]** OCR is a **third ingestion route** alongside §27.1 manual entry and §27.3 CSV import,
not a replacement for either, and it inherits §27.3's existing discipline in full — column/field
mapping, preview of interpretation, identifier validation, ambiguous-ticker flagging, user
correction, quarantine of invalid rows, and an import report. §27.3's rule
*"Do not silently 'guess' ambiguous securities"* governs OCR unchanged.

## 2. Normative obligations — OCR-1 … OCR-11

Stated as the owner gave them. Each is testable; each binds the increment that implements
ingestion, not CP0.

| # | Obligation |
|---|---|
| **OCR-1** | Extract candidate holdings / transaction / account fields. |
| **OCR-2** | Preserve the source location/evidence for extracted values where feasible. |
| **OCR-3** | Assign confidence or uncertainty to extracted fields. |
| **OCR-4** | Attempt security-identity resolution. |
| **OCR-5** | Explicitly flag ambiguous identities. |
| **OCR-6** | Preserve missing fields as missing. |
| **OCR-7** | Never invent values merely to complete a row. |
| **OCR-8** | Present all candidate data in a staging/review surface. |
| **OCR-9** | Highlight low-confidence, conflicting, duplicate, or unresolved fields. |
| **OCR-10** | Allow correction before ingestion. |
| **OCR-11** | Require explicit human confirmation before anything reaches the canonical portfolio ledger. |

## 3. The invariant

**[F] OCR must never silently mutate portfolio state.**

**[J]** This is the load-bearing sentence of the whole requirement, and OCR-11 is its
mechanism. Everything else in this addendum can be satisfied imperfectly in V1 and still leave
a usable product; this one cannot. An ingestion path that writes to the ledger without an
explicit human confirmation step is not a degraded implementation of this requirement — it is
a different, unapproved product.

**[J]** It stands in the same relation to the ledger as **P8** does to the portfolio: staged
candidate data is *not yet* portfolio state, exactly as a scenario result is *not* a holding.
Implementers should reuse P8's separation mechanism rather than invent a second, weaker one.

## 4. Boundaries — what this requirement must not be read to permit

**[J]** These follow from validated contracts that this addendum does not reopen.

1. **OCR confidence is not a metric sufficiency state.** `AVAILABLE` / `LIMITED` /
   `INSUFFICIENT_DATA` (§32, P5) describe whether a *computed metric* is supported by enough
   data. OCR confidence describes how sure an extractor is that it read a character. Rendering
   a low-confidence extracted field as `LIMITED` is a category error. PD-0006 established that
   this vocabulary is layered; that discipline forbids the merge. **A separate extraction-
   confidence vocabulary is required.**
2. **OCR-6 and OCR-7 are the ingestion-layer statement of P5.** A field the extractor could
   not read stays empty and says so. It is never filled by inference, by a neighbouring row,
   by a plausible default, or by an AI completion.
3. **An extracted value is not an AI-authored fact under P1 — and it is not a deterministic
   fact either.** It is a *candidate input awaiting human confirmation*. It becomes a
   canonical fact only when a human confirms it, and its provenance must record that this is
   how it became one.
4. **Confirmed OCR-sourced entries carry their origin permanently.** Per OCR-2 and P9: that
   the value came from an extraction, from which document and region, at what confidence, and
   which human confirmed it. An ingested value whose origin is untraceable after commit does
   not satisfy P9.
5. **Determinism (P12) is preserved by the confirmation boundary, on one condition.** The
   non-deterministic extraction sits *before* the deterministic engine, as human typing does.
   This holds **only if** the persisted, replayable input is the *confirmed staged batch* — not
   the image and not the extractor. If ledger history can be reconstructed only by re-running
   OCR, determinism is broken. See PD-0009 §2.7 and OCR-OQ-5.

## 5. HG1 prototype obligation

**[F]** The HG1 design-review prototype must visually demonstrate representative OCR states:

- high-confidence successful extraction;
- low-confidence field;
- ambiguous security match;
- missing field;
- possible duplicate;
- reconciliation/correction;
- final human confirmation.

**[F]** The prototype **may simulate** OCR results. **[F]** A production OCR pipeline must
**not** be built to satisfy this HG1 design review — the owner said so explicitly.

## 6. Open questions

Carried from PD-0009 §4, unresolved and owned elsewhere: **OCR-OQ-1** evidence-schema home for
ingestion provenance (`engineer` + `harness_architect`); **OCR-OQ-2** retention/deletion/
encryption posture for uploaded images (owner + `harness_architect`); **OCR-OQ-3** credential-
bearing regions (owner); **OCR-OQ-4** third-party OCR vendor vs §31 cross-border data review
(owner); **OCR-OQ-5** replayable-input confirmation (`engineer`, CP1); **OCR-OQ-6** the rest of
§5.4's onboarding/import automation (owner); **OCR-OQ-7** identity resolution from an OCR-read
string with no FIGI fallback (`engineer` + owner).

**[A]** None of these blocks the HG1 prototype, because the prototype simulates extraction and
uploads nothing. **[J]** All of them block a production ingestion path, and none should be
closed by an agent.

## 7. Security and privacy notice

**[F]** PRD §30.1 records the MVP posture as including *"no brokerage credentials because
broker integration is out of V1."* **[J] A brokerage screenshot breaks that assumption** — one
image can carry account numbers, holder name, balances, and plausibly a session or credential
artifact, and OCR-2 means the product *stores* it. This does not block the scope addition and
does not affect the prototype, which uploads nothing. It is recorded so the owner is accepting
a known change of posture rather than an invisible one. Full analysis: PD-0009 §2.6.
