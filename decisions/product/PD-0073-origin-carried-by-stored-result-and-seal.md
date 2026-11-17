# PD-0073 — A result's origin is carried by the stored result and the seal, not by a manifest field

**Status:** accepted
**Date:** 2026-10-26 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 1.1: the quant's condition 1 for `state_kind`, "carried
  into every manifest and result (P9)";
- `implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md` item 5.4;
- `methodology/CP2_ORIGIN_CARRIAGE_NOTE_2026-10-26.md`;
- F1 increment R3 (`src/persistence/real_fence_v1.sql`, `rw_check_artifact`), R5 and R7.

## Context

R3's independent review (H-1) found that the seal required shapes that neither service issues. In
the fix round, the engineer listed the design's seal predicates that no service output can carry. One
of them is the manifest `origin` (item 5.4): neither the performance service nor the fictional
integration states an origin object in its manifest.

The engineer proposed:
- the gateway's stored `response` carries the four origin fields;
- the seal checks them against the immutable root row.

The quant, asked whether this meets condition 1, said yes, provided four conditions hold. It
recommended its own wording, not the engineer's. It advised against adding origin to the engine
manifest.

## Decision

Question asked, verbatim:

> Where should a computed result's origin (real vs synthetic market data, whose ledger, personal holdings) be recorded for auditability (P9)?

Options shown, verbatim:
- **"Stored result + seal (Recommended)"**: "Quant's reading. The engine manifest does not get an origin
  field. Each manifest is tied to its root by portfolio_id (inside manifest_id, checked by the seal); the
  manifest and every metric state the synthetic flag; the stored result states all four origin fields and
  the seal checks them against the immutable root; no surface returns a result without them. Four
  conditions bind later services. No method, value or fixture changes; a wording clarification goes to
  the next market-data change note."
- **"Add origin to the manifest"**: "A new manifest schema (/2) stating the four origin fields, never
  defaulted. New performance, risk and diversification versions and registries; every pinned manifest_id
  and result_digest changes (metric values don't); old /1 manifests no longer reproduce; every engine call
  site must supply the fields, which conflicts with 'fictional flow unchanged' (T10). Delays R3 and R5."

Owner's answer, verbatim: **"Stored result + seal (Recommended)"**

## What this means

- **The engine manifest stays as it is.** Its schema is unchanged, no methodology version moves, and no
  manifest id, result digest or fixture changes.
- **Condition 1 is met by this chain** (quant's note §1):
  - the root's four origin columns are not null and are immutable;
  - each manifest's `portfolio_id` is inside its `manifest_id`, and the seal requires it to equal the
    root;
  - the manifest and every metric state the synthetic flag, which the seal checks;
  - the stored `response` states all four origin fields, and the seal checks them against the root
    (`rw_check_artifact`);
  - no surface returns a result without them.
- **The four conditions, which bind R3 and every later real-path service:**
  1. The root binding holds for every manifest the seal accepts, nested ones included. A manifest with a
     null `portfolio_id` is refused.
  2. The response-origin conjunct is in force on both branches.
  3. No surface returns a computed result without the four fields, taken from the stored response or the
     root. This covers reproduce and archive read now, and export later. Labels and claim text read them
     from the stored fields.
  4. Condition 3 (no crossing of baselines) keeps its own mechanism, the `SCOPE_MISMATCH` check by
     portfolio.
- **Wording.** Condition 1 is read as the quant's note §1 states it, not as "the stored result, enforced
  by the seal". The issued market-data 1.16 text is unchanged. The clarification is owed to the next
  market-data change note. The design is revised to cite this record at its next revision.
- **Limit carried from the quant's note.** `synthetic = false` holds exactly when `market_origin =
  REAL_SOURCE` only under today's two-value scope table. Admitting a third market origin reopens this.

## What this does not do

It builds nothing and approves no gate. R3 is still under its fix round and re-review.
