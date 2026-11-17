# Where the origin fields must be carried for P9 (F1 R3, disposition 5.4), 2026-10-26

Author: quant-analyst. Status: a reading of `market-data/1.16` Ruling 6.5 item 9, condition 1, and a
recommendation. It edits no issued text. It does not move a convention id, a registry, a fixture or a
profile counter. **The owner decides whether to accept disposition 5.4. This note is only the
method's answer to the coordinator's three questions.**

**The question.** Condition 1 of my `state_kind` confirmation (`CP2_MARKET_DATA_CONVENTIONS.md`
Ruling 6.5 item 9, line 3684; carried into design `implementation/CP7_F1_REAL_PATH_DESIGN.md` §1.1)
says the origin fields are "written once on the root, and carried into every manifest and result
that reads it (P9)".

The engineer's proposal, `implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md` §5.4:

1. The engine manifest carries no origin.
2. The gateway's stored `response` carries the four fields, and the seal requires them to equal
   the root row's.
3. Reproduce and the archive read return that stored response.

I read the code and did not edit it:

- `src/performance/manifest.py`;
- `src/persistence/real_fence_v1.sql`: the `rw_root` columns at lines 45–56, the manifest binding
  at line 323, and the origin-label row guard at lines 397–413;
- `src/persistence/real_workspace_v1.sql` lines 160–166 (`rw_origin_expected`) and line 282
  (`rw_immutable`).

---

## 0. What P9 asks of origin, and what origin is to the computation

P9 / §21 requires every important insight to be auditable back to **its inputs and method**. The
four origin fields are `market_origin`, `ledger_origin`, `personal_holdings` and `synthetic`. They
fall into two different kinds.

- **`market_origin` and `synthetic` describe an input**, the market data `M`.
  - `market_origin = REAL_SOURCE` holds only if `M` holds no synthetic file (Ruling 4.8 item 2).
  - Under the scope table (`rw_origin_expected`), `synthetic = false` holds exactly when
    `market_origin = REAL_SOURCE`.
  - The engine already states this fact about its input: `manifest.synthetic` and every
    `metrics[].synthetic`, derived from the port's `contains_synthetic` (`performance/engine.py`
    lines 173 and 271). It does not take it from the caller.
- **`ledger_origin` and `personal_holdings` describe the subject**, meaning whose ledger it is.
  - Item 9 states that they are not inputs to the method: "The rulings that compute the value do not
    depend on who entered the ledger."
  - By condition 2 they are independent of `synthetic`.
  - The engine cannot know them. Only the root, written once by the gateway, can state them.

So condition 1 asks for two different things, depending on the kind. For the input facts, the
manifest must state them. For the subject facts, every result must be **bound to the one immutable
record that states them**, and must be shown with them.

---

## 1. Does the proposal meet the intent of condition 1? Yes, on four conditions

**What condition 1 was for.** It was written so that:

- no result that reads a root can be read, reproduced or shown apart from that root's origin;
- the origin cannot change after it is written;
- the origin is never defaulted.

It did not require that the engine's `manifest_id` hash the subject labels. P9 is met by an
**auditable chain**. Every link in it must be immutable and checked; that is what is required, not
a copy of the labels inside every document.

**The chain under the proposal.** Each link is shown with the code that establishes it.

1. **The manifest identifies its root, and `manifest_id` covers that.**
   - `manifest.portfolio_id` is inside `manifest_id` (`to_obj`).
   - The real seal refuses unless `manifest.portfolio_id = root_id` (`real_fence_v1.sql:323`).
   - Hence a given `manifest_id` belongs to exactly one root. It cannot be re-attached to a root of
     another origin without changing the id.
2. **The root states the origin, immutably and never defaulted.**
   - The four `rw_root` columns are `NOT NULL` (lines 49–52).
   - `rw_immutable` refuses `UPDATE` and `DELETE` on the rooted tables (`real_workspace_v1.sql:282`).
   - The row guard requires the four fields to equal the scope's expected labels (lines 408–413).
3. **The input part is also inside `manifest_id`.** `manifest.synthetic` and each metric's flag must
   equal the scope's axis, wherever the issued bytes state them (`flags_bad`, lines 399–405).
4. **The stored result states the origin.** The proposed conjunct `response.origin = origin_row`
   ensures that the document a reader receives carries the four fields, and that they are the
   root's.

With 1–4, an auditor can start from any `manifest_id`, any `result_digest` or any stored response
and reach the four origin fields, by immutable and seal-checked links. That meets P9 for this
quantity.

**Putting the subject labels inside the engine manifest would add no audit strength.** The engine
would copy them from its caller, and the seal would still have to compare that copy with the root.
The root stays the authority either way. It would also make two questions that are identical in
every input and method differ by a label the method does not read. That blurs what `manifest_id`
identifies: the question, not its owner.

**The four conditions on which this holds.** If any one fails, the intent of condition 1 is not met.

- **(i) The binding stays.** The seal keeps `manifest.portfolio_id = root_id` for every manifest it
  seals. That includes any nested manifest, for example a CP5 `valuation_manifest`, if a real-path
  result ever carries one.
  - A manifest with a null `portfolio_id` cannot be bound and must be refused. Diversification's
    engine defaults to `portfolio_id=None` (`src/diversification/engine.py:29`).
  - Today the real branch seals only the performance service. Any later real-path service (risk,
    diversification, insights) is held to (i)–(iv) before it is sealed.
- **(ii) The stored-result conjunct is in force** on both branches, as proposed:
  `response.origin` equals the root's four fields.
- **(iii) No result is returned apart from its origin.**
  - Every surface that returns a computed value takes the four fields from the stored response or
    the root row. Today these are reproduce and the archive read, and later an export.
  - No surface returns the bare engine result alone.
  - The list route returns no number, so it is unaffected.
  - The claim-limit and label text (§7.4; claim N-8) reads them from the stored fields, as the
    design already says.
- **(iv) Condition 3 (no crossing of baselines) keeps its own mechanism.**
  - CP6's `history_problem` refuses a baseline of another portfolio (`SCOPE_MISMATCH`). That rests
    on `portfolio_id`, the same link as (i).
  - Any later cross-root comparison must keep that check, or must carry `ledger_origin` and
    `personal_holdings` in its key, exactly as item 9 condition 3 already says.

**Wording.** I would not narrow condition 1 to "the stored result, enforced by the seal". That drops
the manifest's part, which is real: link 1 and the input flags. The reading I give condition 1, and
recommend the design use, is:

> The origin fields are written once on the root, never defaulted. They are carried **by reference**
> into every manifest that reads the root: `manifest.portfolio_id` = the root, inside
> `manifest_id`, checked by the seal. The input part (`synthetic`) is stated by the manifest and
> every metric. **All four** are stated in every stored result, and the seal checks them against
> the root. No result is returned without them.

- The issued 1.16 text is not edited (one id, one text).
- This clarification is owed to the next market-data version's change note, beside item 9. It
  changes no method and no value. It sits with the list in
  `CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25.md` Addendum B and
  `CP2_F8B_POLICY_DIGEST_NOTE_2026-10-26.md` §1.

---

## 2. If origin had to be in the manifest: what it would take

**My recommendation is not to do this. This section is so the owner can see the cost.**

1. **A new manifest schema and a new performance version.**
   - The schema would become `finweb.computation_manifest/2`.
   - A performance ruling would say "the manifest states the subject's origin fields, supplied by
     the caller, never defaulted, refused if missing". It would sit beside performance/1.12
     Ruling 1.7 item 4, which added `source_registry_digest` the same way.
   - So: a new `performance/` version, an `ENGINE_ID` bump, and a re-issued CP3 appendix
     (performance-registry/1.3).
2. **Risk and diversification.** Their manifests are built on the performance service's
   (`detection_policy`, valuation manifests). Each would need the same ruling: risk/1.12 and
   diversification/1.3, with their registries re-issued. INSIGHTS would change only if its evidence
   records cite manifest ids. I have not checked that, and would before issuing.
3. **Fixtures.**
   - No expected metric value changes, because origin is not an input to any formula.
   - Every pinned `manifest_id` changes. Every pinned `result_digest` also changes, because each
     metric is stamped with its manifest id (`seal` → `with_manifest`) before the digest is taken.
   - Those pins would be re-derived and re-issued as new fixture versions.
   - Reproducing a `/1` manifest under `/2` code would be refused, as now for a convention change.
4. **Every engine call site** (tests, tools, both services, the fictional integration) would have to
   supply the four fields, because condition 1 forbids a default.
   - That conflicts with T10, "fictional flow unchanged", wherever the integration nests a
     performance manifest.
   - It is a scope question for the PM.
5. **The seal would still compare the copy with the root.** The audit chain would be the same as
   under §1, with one more field to keep consistent.

---

## 3. Do `manifest.synthetic`, `metrics[].synthetic` and the root row carry what P9 needs?

**Together, yes. The synthetic flags alone, no.**

- **The flags carry the input part.**
  - `manifest.synthetic` and each `metrics[].synthetic` are derived by the engine from the data it
    read, and lie inside `manifest_id` and `result_digest`.
  - Under the scope table and Ruling 4.8 item 2, `synthetic = false` holds if and only if
    `market_origin = REAL_SOURCE`, and the seal enforces this (`flags_bad`; the row guard).
  - That equivalence is a property of today's two-value scope table. If a later version admits a
    third market origin, the flag would no longer determine `market_origin`. The root row would
    then be its only carrier, which (i)–(iv) already cover.
- **The flags do not carry `ledger_origin` or `personal_holdings`.**
  - Condition 2 makes them independent of `synthetic`: a constructed or personal ledger on real
    market data is `synthetic = false` either way.
  - They come only from the root row, reached through link 1.
- **So the part P9 needs is carried, as long as:**
  - the binding (i) holds;
  - the root row is immutable and has no nulls (link 2, both in place);
  - the stored result restates all four (ii, iii), so that a reader never has to join tables to
    see them.

---

## 4. Recommendation (the owner decides)

**Accept disposition 5.4 with conditions (i) to (iv) of §1, and with the reading of condition 1 in
§1 instead of the proposed narrowing.**

- Do not add origin to the engine manifest. It would re-issue three registries and every pinned
  `manifest_id` and `result_digest`, for no gain in auditability.
- The engineer should add tests that:
  - refuse a manifest whose `portfolio_id` is null or differs from the root (exists for the
    performance branch; extend it to any later branch);
  - refuse a response whose `origin` is missing or differs in any one of the four fields, with one
    mutant per field;
  - show that reproduce and the archive read return the four fields from the stored response.

**A fact for the coordinator.** The working tree's `real_fence_v1.sql` already contains the
conjunct, at line 411: `OR response_obj->'origin' IS DISTINCT FROM origin_row`, with the comment
"disposition note 5.4". The disposition's summary said this would be built "only after the
owner/Quant answers". This note is the Quant's answer. The owner's decision is still open.
