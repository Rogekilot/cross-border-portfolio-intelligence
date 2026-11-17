# PD-0019 — Post-HG1 Checkpoint A closure

**Status:** accepted
**Date:** 2026-09-22
**Decided by:** the designated **human product owner**, in a direct instruction to `pm-01`.
**Recorded by:** `product_manager`, worker `pm-01`, session `14e5c769`. **Recorded, not decided.**
**Evidence package:** `reviews/gates/POST_HG1_CHECKPOINT_A_EVIDENCE_PACKAGE.md`
**Verification record:** `reviews/gates/POST_HG1_CHECKPOINT_A_PM_VERIFICATION.md`
**Baseline:** `reviews/gates/POST_HG1_CHECKPOINT_A_STAGE0_BASELINE.md`

---

> **This closure is BOUNDED.** It closes the Post-HG1 Checkpoint-A work on the surfaces, states,
> locales and scenarios explicitly named in §4 and in the evidence package §E. It does **not** assert
> complete prototype verification, verified responsive behaviour, universal localization
> correctness, resolution of the deferred debt in §8, or any change to HG1 itself.
>
> The limitations in §7 remain **unverified** and the items in §8 remain **open**. Closure does not
> convert any of them to PASS.

---

## 1. The decision, verbatim

```
Post-HG1 Checkpoint A: APPROVED FOR CLOSURE
```

The human product owner approved closure of the bounded Post-HG1 Checkpoint-A work on the committed
and independently reviewed state through the Round-2 and Round-3 preservation commits named in §6,
with the limitations in §7 and the deferred items in §8 carried forward explicitly and unresolved.

No additional implementation round was authorized or required. `ux_planning` is not reopened.

## 2. Relationship to prior decisions

1. **`PD-0017` remains unchanged and authoritative.** HG1 = APPROVED, decided by the human product
   owner on 2026-09-13, no conditions attached. This decision does not amend, qualify, reinterpret or
   supersede it.
2. **HG1 was never reopened.** Post-HG1 Checkpoint A was a **bounded cleanup of accepted post-HG1
   debt** — the residual items carried in `PD-0017`'s own approval basis — and not a re-litigation of
   the gate.
3. `PD-0018` is unaffected.
4. The `pm_acceptance = awaiting_human` shard state is a **known representation gap in the generic
   workflow DAG**, already recorded at Stage-0 §1. It does not mean HG1 is unapproved. Gate decisions
   live in decision records; the generic task has no representation for "decided elsewhere". **It was
   deliberately not mutated** to make the DAG cosmetically agree with `PD-0017`, because forcing the
   shard would fabricate a lifecycle event that never occurred.

## 3. Scope addressed

Four packages: **D1**, **D2**, **D3**, **S1**. Three bounded corrective rounds
(`designer-33` → `designer-34` → `designer-35`), each under the same lawful `ux_planning` lifecycle
with a fresh Designer, each followed by PM verification, with Rounds 2 and 3 additionally subjected to
independent advisory review.

## 4. Findings per package

**Every statement below is bounded to the surfaces and locales named in the evidence package §E. All
rendered verification was desktop-only, at a reported 1512×771 CSS px viewport.**

### D1 — Holdings caveat discoverability

**CLOSED on the verified desktop surfaces**:

- the long INSUFFICIENT_DATA explanation for `600519.SS` remains inside its intended cell and wraps
  rather than overflowing;
- the LIMITED qualifier for `601318.SS` is **also contained** after Round 3, in both locales, and no
  longer spills into the FRESHNESS column;
- row identity remains usable alongside the wrapped text, and no sideways table scrolling was
  reintroduced;
- no column width, `<colgroup>`, table information architecture, sticky-column or responsive
  architecture was changed, and no qualifier text was shortened, truncated or hidden.

**No responsive or narrow-width claim is made.** Any characterization of the final state as *improved
versus the pre-fix rendered baseline* is **inference**, not direct observation: no lawful route exists
to render the pre-fix commit, so neither `pm-01` nor `review-11` ever observed the defect.

### D2 — Holding-inspector Professional depth

**CLOSED on the tested states and locales**:

- the Quick → Simple → Professional three-rung ladder is preserved;
- Professional now meaningfully deepens the **holding-specific** explanation rather than restating
  the Simple text;
- **no FX or currency-conversion analysis was invented**, and `methodology.unrealizedGainLoss`
  remains deliberately unpopulated, per owner decision H3;
- the canonical Chinese sufficiency vocabulary is corrected — AVAILABLE now reads `可用`, with the
  synchronized selfcheck expectation moved in the same round, and LIMITED `有限` /
  INSUFFICIENT_DATA `数据不足` / UNSUPPORTED confirmed canonical;
- no underlying value, metric state, reason code or sufficiency logic was changed, and no English
  meaning moved.

### D3 — Scenario Lab human-readable machine values

**CLOSED on the tested scenarios and locales**:

- canonical machine enums remain internal and no raw `action` code or `dimension:CODE` token reaches
  the user;
- user-facing scenario labels are readable and bilingual, with the raw canonical values still
  available via data attributes for traceability;
- **calculations and canonical values are unchanged**; `modifications[]` data was not touched;
- the ACTUAL / SCENARIO — HYPOTHETICAL separation (P8) and the historical-replay statement (P6) are
  present.

### S1 — Active HG1 approval / gate-state claims

**CLOSED for the active artifact surfaces tested**:

- stale present-tense claims that HG1 is unapproved, undecided or blocked are removed or surgically
  corrected across title, persistent banner, EN/ZH runtime footer and static pre-boot fallback, and
  the Valuation Mode note;
- `README.md` defers HG1 status to `PD-0017`;
- `CONTRACT.md` carries a dated current-status note, and its Checkpoint-A addenda are now
  structurally correct — §17.1–§17.4 contiguous, addenda chronological, the pointer durable;
- **historical and round-scoped gate-status records are preserved unedited**, and the superseded
  prototype trees `designs/hg1-prototype/` and `designs/hg1-revision/` are unchanged.

The relocation of `designer-33`'s addendum preserved its content, attribution, round identity and
historical meaning. **The digest/boundary evidence demonstrates the resulting artifact state; it does
not and cannot prove the absence of intermediate edits** during `designer-35`'s work.

## 5. Independent review

- **`review-10`** (advisory, fresh) returned **`CLEAR WITH MINOR DEBT`** against the Round-2 state it
  reviewed, and raised **F-1, F-2 and F-3**. Its verdict covers that state only and does not certify
  Round 3.
- **F-1, F-2 and F-3 were corrected in Round 3** by `designer-35`, bounded strictly to those three
  findings.
- **`review-11`** (advisory, fresh, independent of all three Designers and of `review-10`) returned
  **`CLEAR`** on Round 3, having independently validated the F-3 block boundaries rather than relying
  on `pm-01`'s digest, structurally verified the F-1 overflow path and the `data-table` blast radius,
  and corrected one overbroad statement in `pm-01`'s own record.
- One rendered-coverage gap identified by `review-11` (Import & Ingestion) was **subsequently closed
  by `pm-01`**, not by `review-11`.

**F-1, F-2 and F-3 are recorded as CORRECTED BEFORE CLOSURE and are NOT carried forward as accepted
residual Checkpoint-A debt.**

## 6. Provenance of the three rounds — not equivalent

| Round | Executor | Original execution record / handoff |
|---|---|---|
| 1 | `designer-33` | Overwritten before any Git snapshot. Survives **only** as a verbatim transcription in the PM verification record §6. **Transcription-based evidence.** |
| 2 | `designer-34` | Recoverable from `aa24390348b7c43f6b593ccbd6c8f7e6ac3eb1e7`. **Git-recoverable originals.** |
| 3 | `designer-35` | Recoverable from `f5c8bdc5cb1c4fc327f5c60ff609bf7f5363a268`. **Git-recoverable originals.** |

These three must not be presented as equal in evidentiary strength. Both preservation commits were
made by the **human repository owner**; `pm-01` prepared the explicit-path manifests and executed
neither.

## 7. Limitations retained — explicitly NOT resolved

Carried forward unresolved. These are the boundary of what was exercised.

1. Responsive / narrow-window behaviour below ~1500 CSS px.
2. Native HTML `<select>` popup interaction.
3. `APP.i18nCheck.run()`.
4. Manual-only negative and fault-injection directions (`selfTest()`, `injectDefect`, `APP.uicheck`).
5. Substantive correctness of all 51 assertions beyond the directions actually exercised or
   inspected — `all 51 passed` was observed; the assertions themselves were not read.
6. The previously identified S1 panel sweep not directly reviewed (Analytics panels beyond the risk
   cards, AI panels).
7. Direct rendered pre-fix baseline comparison, for which no lawful baseline render exists.
8. Transactions ledger and Accounts & Cash, seen incidentally but not systematically swept.
9. The validator results in the evidence package were not independently re-run by `review-11`.
10. Print stylesheets, other browsers and operating systems, zoom levels, forced-colors, reduced
    motion, and keyboard / screen-reader behaviour of the wrapped qualifier.

## 8. Deferred and pre-existing items — carried forward separately

**Not Checkpoint-A-created debt; must not be relabelled as failures of D1–D3/S1.**

1. No-data chip touching the FRESHNESS pill with the inspector open.
2. Repeated no-data reason / caveat presentation.
3. Holding Proof Packets exposing portfolio-level defaults.
4. `2800.HK` Simple/Professional risk-metrics equivalence.
5. Per-position unrealized gain/loss FX treatment and the unpublished per-position methodology entry.
6. Scenario impact multiplier gap.
7. **Broader `designs/FEATURE_DESIGN.md` staleness — a Phase-B entry requirement** (§9).
8. ADR-0033 document/code discrepancy.
9. Cross-role Git preservation requiring the established human commit route.
10. Delegated-reviewer browser-preflight renewal limitation — operational, not a product defect.

## 9. Phase-B entry requirement

**Broader `designs/FEATURE_DESIGN.md` reconciliation remains a Phase-B entry requirement.**

`implement` reads `designs/FEATURE_DESIGN.md`, not the prototype. Checkpoint A amended only the
sections needed to record D1, D2, D3 and S1. **Phase B must not treat the broader document as fully
current merely because those bounded amendments exist.** Before Phase B implementation materially
relies on it, `pm-01` returns a bounded recommendation — targeted reconciliation, explicit
supersession notes, or another minimal mechanism.

## 10. What this decision does NOT claim

It does not claim universal UX correctness, complete prototype verification, verified responsive
behaviour, that all localization tests passed, or that all regression paths were executed. It records
closure **only on the explicitly tested surfaces** named in §4 and the evidence package §E, with §7 as
the stated boundary.

## 11. What this decision does

**Does:** closes the bounded Post-HG1 Checkpoint-A work. `implement` (ready, rev 32) becomes the next
eligible work under the existing DAG, subject to the Phase-B entry requirement in §9.

**Does not:** amend `PD-0017`, reopen HG1, authorize a further correction round, clear any item in
§7, or resolve any item in §8.

**On the generic DAG.** After this decision the shards may remain as they stand —
`ux_planning` complete rev 31, `implement` ready rev 32, `pm_acceptance` awaiting_human rev 24.
`pm_acceptance` is **deliberately not mutated** so the DAG visually agrees with this decision.
`PD-0017` and `PD-0019` are the authoritative human product decisions; the shard state is a known
representation gap in the generic workflow and remains a separate workflow limitation (§2.4).
