# F1 R3: disposition of the seal predicates a service output cannot carry, and the identity-table question

Design-revision note from the Engineer to the main session, written after the R3 fix round (2026-10-26) and updated the same day for the
PM's decisions and for PD-0073. Nothing in `implementation/CP7_F1_REAL_PATH_DESIGN.md` is edited.

**Status of each disposition (2026-10-26, after the PM's decisions and PD-0073).**
- 5.1 accepted and BUILT: `RW_REAL_PROJECTION_DIFFERS`, real branch only.
- 5.3 accepted (as my variant) and BUILT: `RW_REAL_REGISTRY_DIFFERS`, real branch only. R4b obligations are in "Obligations" below.
- 5.4 DECIDED by the owner (PD-0073, "Stored result + seal"): the engine manifest gets no origin field; the origin is carried by the stored
  result and the seal. BUILT: the response-origin conjunct on both branches, and the root binding of every manifest the seal accepts
  (the Quant's conditions 1 and 2; 3 and 4 are shown below).
- Re-review (PASS_WITH_FINDINGS, LOW only) closed in R3: RR-L1 root-binding rules (explicit list), RR-L2 catalog audit (function definitions and
  the full trigger set), RR-L3 tests for the real branch's schema, scope and as_of checks, RR-L4 `RW_REAL_MEMBERS_DIFFER`. RR-L5 (design 1.1
  wording) is the main session's.
- 5.2, 5.5, 5.6: drops accepted provisionally, claims narrowed as written. The independent re-review checks that no HG4 or P9 claim
  depends on them. 5.8: agreed, no in-memory O4 control.

The sections below keep the original proposals (the evidence); the "Decided and built" section at the end of part A states what the code now does.

Evidence base: the code of `performance/manifest.py`, `performance_service/service.py`, `marketdata/manifest.py`,
`persistence/real_proposal.py`, `persistence/market_data_store.py`, `financial_service_integration.py`, the migrations, and the R3 SQL.
The design text asks the real seal for O4a, O4b and the F8B policy digest from the snapshot (W11, 4.2); the other five predicates came from
my first build, which mirrored F2's `gw_check_artifact` bindings. That is why most of them are dropped or moved rather than defended.

## What the real branch's seal binds today (the base the dispositions work from)

`rw_check_artifact` + `rw_check_real` tie a real-branch output to its snapshot through: the envelope's context id = the lease's context;
the root row's context; `manifest.portfolio_id`, `ledger_version`, `as_of`, `reporting_currency` = the stored root and revision;
`manifest.release_id` (or `parent_release_id`) = `snapshot.release.release_id`; `manifest.detection_policy[0] = ["digest", snapshot.f8b_policy_digest]`;
O4a, O4b; and the origin-label row guard. Everything else the snapshot records (projection, identity, registry digests) is not compared.

## A. Dispositions

| # | Predicate | Disposition | Needs R3 SQL | Needs owner |
|---|---|---|---|---|
| 5.1 | `projection_digest` | **1. Implied**, with one small seal check that reads the database, not the manifest | yes, real branch only | no |
| 5.2 | snapshot `identity_digest` vs manifest `identity_digest` | **3. Dropped, claim narrowed** | no | no |
| 5.3 | snapshot registry digests vs `source_registry_digest` | **2 (variant). Snapshot side re-encoded by the engine's own function; the manifest field already exists** | yes, real branch only | no (yes, if the PM prefers to drop it) |
| 5.4 | manifest `origin` | **3. Dropped for the manifest; replaced by a check on the gateway's own `response`** | yes, both branches' response (see below) | **needs owner** |
| 5.5 | fictional question/binding `context_id` vs the lease's context | **3. Dropped, claim narrowed** (TEST-only) | no | no |
| 5.6 | F2 fixture hashes; capital policy vs snapshot; identity facts vs `lookup_answers` | **3. Dropped, claim narrowed** (TEST-only) | no | no |
| 5.8 | the real branch's accepted commit before R8 | **3. Not a predicate; already disclosed; keep as stated** | no | no |

### 5.1 `projection_digest`: implied (disposition 1)

*Code.*
- `md_release.projection_digest` is written once with the release row (`0009_market_data_files_and_releases.sql:42-50`).
- The row cannot change: `md_release_no_update_delete` and `md_release_no_truncate` (`0011`, lines 96-98), and `write_release` raises
  `ReleaseConflictError` for the same `release_id` with a different digest (`market_data_store.py:481-509`, "a release is never overwritten").
- `release_id` is the SHA-256 of the canonical release JSON, so one `release_id` has one `projection_digest`.
- The real branch's seal already requires `manifest.release_id = snapshot.release.release_id`.
- `read_release` recomputes the projection digest from the rows it reads and fails closed on a difference
  (`ProjectionDigestMismatchError`, `market_data_store.py:719-727`).

*So the manifest needs no projection field.* The one missing link is that the snapshot's `projection_digest` was asserted by the proposal
writer and nothing compares it with the database. The seal can: `rw_check_artifact` and `rw_check_real` run as the owner and can read
`md_release`.

*SQL to add (real branch only; `rw_check_real`).* Code `RW_REAL_PROJECTION_DIFFERS` when
`(SELECT projection_digest FROM md_release WHERE release_id = snapshot.release.release_id)` is missing or differs from `snapshot.projection_digest`.
This also makes "the snapshot's release is loaded in this database" a seal fact, which it is not today.

*Fictional branch.* Not applied: the integration's release is its own inline world and has no `md_release` row; T10 is untouched.

*What the seal then proves, and does not.* It proves the snapshot describes the projection the database holds for the release the service
named. It does not prove the service read exactly those rows; that is `read_release`'s recompute (R5, product code, fails closed).

*Test impact.* The real-branch refusal tests need a snapshot whose release is loaded (the mdread fixture shows how: `rich_release` +
`write_release` as the loader). The refusal list gains the new code when the release is not loaded.

### 5.2 snapshot vs manifest `identity_digest`: dropped (disposition 3)

*Code.* The two are different quantities. The manifest's `identity_digest` is the `RecordingResolver` digest of the identity facts the
computation asked for (trading currency, exchange MIC, security type for the listings the ledger names and whatever `D_c(t)` asked;
`performance_service/service.py:148`, `manifest.py:65`). The snapshot's is the digest of the registry the qualification run built.
A seal comparison would need the snapshot to carry the list of facts the computation will ask for, or the manifest to carry the facts
(the CP5 manifest does, `identity_facts`; the performance manifest does not). Adding a field to the performance manifest changes
`manifest_id` of every result and every golden fixture, which is a methodology change, not mine, and it is not needed for a real predicate
the design names.

*What the seal no longer proves.* That the identity facts the service asked of its resolver equal the identity the snapshot recorded.

*What still carries it.* (a) The world builder is built from the locked snapshot (N2b, design 4.2 build table), so the resolver comes
from the snapshot by construction; R5's tests show that. (b) `reproduce` rebuilds the world from the snapshot and re-runs; the engine
already has the typed cause for a difference, `IDENTITY_MISMATCH` (`performance/manifest.py:130`). (c) R8's independent oracle
`10 x p + 500` fails if the listing's currency or exchange were wrong.

*HG4 / P9.* Nothing in the design states the seal binds identity. P9 auditability is carried by the stored manifest (it holds the
digest) plus reproduce. No owner decision. The R5 claim-limit wording (7.4) should not say the seal verifies identity.

### 5.3 registry digests vs `source_registry_digest`: option 2, variant (R4b re-encodes the snapshot side; no new manifest field)

*Code.*
- The manifest already issues `source_registry_digest` = `source_registry_digest(records)`: SHA-256 of canonical JSON of
  `SourceRecord.to_obj()` for the sources with a file in the release read, sorted by `source_id` (`marketdata/manifest.py:301-305`,
  `performance/engine.py:238-247`).
- The snapshot's `registry.used_source_digest` is SHA-256 of canonical JSON of `_record_dict(...)` for the members' sources
  (`real_proposal.py:154-177`).
- Those documents differ even for the same records: `to_obj()` carries `synthetic` and a structured `terms_check`
  (`checked_by, checked_on, permits_internal_development_use, notes`) and optionally `source_priority`; the snapshot dict has neither
  `synthetic` nor `source_priority`.
- So no SQL recomputation from `snapshot.source_records` can match; the digests are not comparable as they stand.

*Why not simply drop it.* O1 and O2 are evaluated at publish on the snapshot's `source_records` (`rwp_origin_failures`). The claim "the data
the NAV used has a permitting human terms check" holds for the computation only if the registry the service digested is the snapshot's.
That is the one place the HG4 licensing claim and the seal meet; dropping it would narrow an HG4-relevant claim.

*Proposal.*
- R4b's snapshot builder computes `registry.used_source_digest` with the engine's own `source_registry_digest(...)` over the engine's
  `SourceRecord`s of the sources with a file in the release, instead of `snapshot_bytes(dicts)`. This is deterministic engine code, not gateway code.
  `real_proposal.registry_digests` and the verifier's recompute (R1) change with it: Python only, and no real context exists yet.
- R3 SQL (real branch only): `RW_REAL_REGISTRY_DIFFERS` when `manifest.source_registry_digest <> snapshot.registry.used_source_digest`.
- Precondition (settled by re-review RR-L4, see "Decided and built"): the member-source set equals the set of sources with a file in the release.
  The first version of this note left that to R4b with a possible `release_source_digest` and a further gateway change. It is now enforced
  by `RW_REAL_MEMBERS_DIFFER`, so R4b adds no gateway SQL.
- Until R4b ships the new encoding, today's snapshots list the new code on every refusal. That is harmless before R8 (refusals list every
  failed predicate) and is a visible reminder.

*Fictional branch.* Unchanged. The integration validates its own registry digest against its own context at issue
(`financial_service_integration.py:332`).

*If the PM prefers to drop it.* The HG4 licensing claim narrows to "the snapshot's records satisfy O1 and O2", and the link between those
records and the computation rests on R5's builder and on reproduce alone. **That would be a "needs owner" item.** I do not choose it.

### 5.4 manifest `origin`: dropped for the manifest, replaced on the response (disposition 3). DECIDED: PD-0073 (original proposal text kept)

*Code.* Neither service issues an origin object. The performance manifest has no origin field, and adding one changes every `manifest_id`
(methodology and engine fixtures; not mine to decide). What binds origin today: the root row's four labels = `rw_origin_expected(scope)`
(row guard); the envelope's `scope` = the snapshot's scope; the envelope's, the response's and every `synthetic` flag the service issues =
the scope's axis; no `REAL_SOURCE` string under a test scope; no test wording under `REAL`.

*Why this needs the owner.* Design 1.1, condition 1 of the Quant's `state_kind` confirmation (market-data/1.16 item 9), says the origin fields
are "written once on the root and carried into every manifest and result that reads it (P9)". The manifest part cannot be met without an
engine change; the result part can. Dropping the manifest part narrows a P9 condition the Quant attached.

*Proposal (for the owner/Quant to accept or refuse).* (i) The engine manifest does not carry origin. (ii) The gateway's own `response`
(the persisted snapshot the create builds and stores in `rw_root` and `rw_revision`) carries the four origin fields, and the seal requires
`response.origin = (market_origin, ledger_origin, personal_holdings, synthetic)` of the root row. R3 SQL: one added conjunct in
`rw_check_artifact` (both branches, because the response is the gateway's document). R5's output and claim-limit tests (7.4) then show the
origin on the stored result. (iii) The wording "carried into every manifest" becomes "carried into the stored result and enforced by the
seal on the root, the envelope and every issued flag".

*What the seal does not prove after (ii):* that the engine's manifest itself states the origin. An auditor finds the origin on the root
row, the response and the archive envelope, not inside `manifest_id`.

### 5.5 fictional `context_id` vs the lease's context: dropped (disposition 3)

*Code.* The integration's question and binding carry `context_id` = SHA-256 of its own fingerprint snapshot
(`fingerprint_context_inputs`, hashed in `real_service_producers._addressed` exactly as the integration's tests do). It is a function of
the integration's inputs, not of the S2 snapshot's bytes, and no issued field relates the two. The fictional integration must be sealed
unchanged (T10), so option 2 is unavailable: the integration's output has no such field.

*What the seal no longer proves.* That the integration ran on a world derived from this lease's snapshot. What it does prove: Result,
question and binding are mutually consistent and consistent with the gateway's own identifiers (owner, root, revision, operation, pin,
generation, as_of, currency), `synthetic = true` everywhere, no terms check, and release and F8B policy equal the snapshot's.
TEST-only; no HG4 or P9 claim depends on it (a fictional result is never a real claim). No owner decision.

### 5.6 F2 fixture hashes; capital policy vs snapshot; identity facts vs `lookup_answers`: dropped (disposition 3)

*Code.* F2 compared the output with the hashes of ONE fixed fictional fixture and a snapshot that held `lookup_answers` and a capital
policy. The S2 snapshot holds neither (`real_proposal.py` snapshot keys), and the integration is called with inputs re-addressed per root, so
no fixed hash applies. What stays: capital-policy origin `SYNTHETIC_CANDIDATE`, scope `PORTFOLIO`, `portfolio_id` = the root;
the identity-facts digest equals the digest of the facts listed, each fact of a permitted kind (`rw_check_fictional`).
The integration re-validates itself against its own context at issue and at `reproduce_local_service`.

*What the seal no longer proves.* That the capital policy and identity facts in the fictional result are those of the snapshot. TEST-only.
No HG4 or P9 dependence. No owner decision.

### 5.8 the real branch's accepted commit before R8: not a predicate; keep as stated

The service refuses invented data, so its only pre-R8 output states `synthetic = true`; an accepted real-branch commit needs a
`synthetic = false` result of invented data, which is forbidden (4.2, FF1-C08). Design 4.2 already says O1 and O4 have "no control before R8".
R3's evidence for the real branch is therefore: the refusal list on the service's own bytes, the two bindings shown to pass when the manifest
carries the snapshot's release and policy, and the mutants that make each predicate too lenient. It cannot show a predicate too strict.
That is the stated limit. (A pure-function call of `rw_check_real` on an in-memory document with `synthetic = false` would follow the O2
"in-memory control" pattern, but 4.2 says O4 has no control before R8; I did not do it.) No new claim and no owner decision.

### Decided and built (2026-10-26)

**R3 SQL now in `src/persistence/real_fence_v1.sql`** (each with a failing-case test and a mutant that the test kills; the mutation
tables are in `reviews/ENGINEERING_SELF_VALIDATION.md`):
1. `RW_REAL_PROJECTION_DIFFERS` (5.1), `rw_check_real`: `md_release.projection_digest` for `snapshot.release.release_id` is read from the
   database and compared with `snapshot.projection_digest`. A missing `md_release` row yields NULL, which is distinct, so it refuses.
2. `RW_REAL_REGISTRY_DIFFERS` (5.3), `rw_check_real`: `manifest.source_registry_digest` vs `snapshot.registry.used_source_digest`.
   **Today's refusal test shows the code on the service's own bytes, and the test pins it**: the snapshot side still uses
   `snapshot_bytes(dicts)`, so the two digests differ until R4b re-encodes. A passing-binding helper sets the manifest field equal to the
   snapshot's to show the predicate does not fire when they agree.
3. Response-origin conjunct (5.4, PD-0073), `rw_check_artifact`, both branches: `response.origin` must equal
   `{market_origin, ledger_origin, personal_holdings, synthetic}` built from the immutable root row. Missing, extra or changed fields refuse.
   The kept conjunct is in the origin-label row guard, beside the `response.synthetic` term, so it fires before either branch's checks.
4. Root binding (the Quant's condition 1), `rw_check_artifact`, generic over both branches, **as revised by re-review RR-L1** (a naming pattern
   decided what was scanned, so `finweb.cp6_manifest/1`, `finweb.Risk_manifest/1`, `finweb.risk-manifest/1` and an object with no `schema` key
   escaped). Three rules over every object anywhere in the issued bytes (nested `valuation_manifest`, anything injected): (1) an object that
   carries a `portfolio_id` key names the root, whatever its schema or none; (2) an object whose schema is on the explicit list of the manifest
   schemas the services issue today (`finweb.computation_manifest/1`, `diversification_manifest/1`, `drift_manifest/1`, `insight_manifest/1`,
   `risk_manifest/1`, read from `src/`) must carry `portfolio_id` = the root; (3) an object whose `schema` contains "manifest" in any case and is on
   neither list is refused. The market-data file manifests (`finweb.marketdata.file_manifest/1` and `/2`) are listed apart: they describe a
   file, have no `portfolio_id`, and may be cited in a result; they need no key and are not refused (if one carries the key, rule (1) applies).
   NULL or absent is refused (`IS DISTINCT FROM`). Code `RW_MANIFEST_DIFFERS`. **A later service with a new manifest schema is added to the list
   by a reviewed change; it is never accepted by spelling.**
5. `RW_REAL_MEMBERS_DIFFER` (RR-L4, below), `rw_check_real`.

**5.4 wording (the Quant's section 1 of `methodology/CP2_ORIGIN_CARRIAGE_NOTE_2026-10-26.md`).** The origin is written once on the root and
stored with the result; the manifest ties the result to its root by `portfolio_id`, which is inside `manifest_id`; the response restates the
four fields and the seal checks them against the immutable root. The engine manifest does not carry origin, and no claim says it does.
An auditor finds the origin on the root row, in the stored response and on the archive envelope.

**The Quant's four conditions.**
1. Root binding: built (item 4). Tests: portfolio_id null, a different portfolio, a nested `valuation_manifest` with another portfolio, an
   injected manifest-shaped object, the reviewer's four escapes, a numeric `portfolio_id`, an unlisted manifest schema, a listed schema with the key
   absent and a file manifest carrying another portfolio; both branches; controls (a nested manifest naming the root, both file-manifest
   versions without the key, an object naming the root with no schema) pass the rule. Mutants: see the self-validation (rule 1, rule 2, rule 3
   and the file-manifest exemption each killed).
2. Response-origin conjunct on both branches: built (item 3). Tests: origin missing; one mutant per origin field (four), each killed.
3. The four fields in every result: `rw_archive` (R3's SQL read surface) returns the stored `response` and the root's four columns, and it
   re-runs `rw_check_artifact` at each read, so a stored result whose origin is missing or different from the root is refused at read. The
   test `ReplayAndArchiveTests` shows the archive read returns all four fields from the stored response and from the root, and refuses a
   crafted stored response without them (a mutant removing the conjunct fails it). Reproduce, export and the read tail are R5's code: see the
   R5 obligation lines.
4. `SCOPE_MISMATCH` by portfolio is untouched: grep of `src/persistence/real_*` finds no `SCOPE_MISMATCH`, no `history_problem` and no baseline
   code in R3, so nothing in R3 bypasses that check.

### Re-review RR-L4 settled: can the snapshot's member sources differ from the sources with a file in the release? Yes, so the predicate is built now

*Code and design.* The manifest's `source_registry_digest` covers the sources of ALL files of the release the port serves:
`read_release` takes `source_ids` from `md_release_file` joined to `md_file` (`market_data_store.py`, the `source_scopes` query), and
`registry_digest_of` digests those records. The snapshot's `used_source_digest` covers its members' sources. For HG4 the design says the release
is built from exactly the three members of `M` (design 2.1, 6.1, 7.1a: price `alphavantage.us`, identity `openfigi`, calendar
`calendar.manual`), and the R4b qualification run lists every member of the release against the 6.3 table. So by intention the sets agree.
They are not forced to: the snapshot carries `members` and the release id but nothing connected the two, and the md rows are written by the
loader before any context exists. Nothing in the snapshot, the proposal verifier or the seal compared them. A release that holds one more file
(of a new source, or of a member's source), a member whose hash is not a release file, or a file stored under another `source_id` than the
member's all leave R4b's builder and the md rows free to disagree.

*What I built (R3 SQL, real branch only, `RW_REAL_MEMBERS_DIFFER`).* The seal reads the `(file_sha256, source_id)` pairs of the snapshot's release
from the database (`md_release_file` joined to `md_file`) and the `(payload_sha256, source_id)` pairs of `snapshot.members` and requires the two
sorted lists to be equal; a release the database does not hold gives the empty list and differs. This is stronger than the `release_source_digest`
I was asked to consider: the SQL can read both sides, so no new snapshot field, no new digest and no SQL-side canonical encoding is needed, and
a snapshot that is already published keeps its bytes. Together with `RW_REAL_REGISTRY_DIFFERS` the chain is closed: the manifest digests the
records of the release's sources; the members equal the release's files; the snapshot's digest is over the members' sources.

*What R4b computes (no gateway SQL):* see the first R4b line above. Tests: `O4AndLabelTests.test_the_real_branch_binds_the_snapshots_members_to_the_releases_files`
(control plus the failing cases listed in the self-validation); mutants: predicate disabled (killed), sources-only comparison (killed by the two
cases that keep the source set but change the files).

**Limit stated by PD-0073 and kept.** `synthetic=false` iff `REAL_SOURCE` is a rule on the root labels and the issued flags; the origin
fields do not by themselves prove the data is real. Real data provenance rests on the loader, the registry and O1/O2/O4, which have no
control before R8.

### Obligations carried to later increments
**R4b (snapshot builder and world builder).**
- Compute `registry.used_source_digest` with the engine's own `source_registry_digest(...)` over the engine's `SourceRecord`s of the sources
  with a file in the release, not `snapshot_bytes(dicts)`. Until then `RW_REAL_REGISTRY_DIFFERS` is listed on every real-branch refusal.
  `real_proposal.registry_digests` and the R1 verifier's recompute change with it.
- Members are the release's files, and R4b adds NO gateway SQL for it (re-review RR-L4, settled below): build `members` from the release's own
  rows, one member per `md_release_file` row of the snapshot's release, with `payload_sha256 = md_file.file_sha256` and
  `source_id = md_file.source_id` (calendar and identity files included; every `data_kind` is a file of the release). The seal now compares exactly
  those pairs (`RW_REAL_MEMBERS_DIFFER`). Then `used_source_digest` is the engine's `source_registry_digest(...)` over the `SourceRecord`s of the
  sources of those members, which is the set the manifest digests (`read_release` takes `source_ids` from the same join).
- Real identity seeding (see B): an owner-run step before the load. Open item for R6/R8.

**R5 (create path, reproduce, read tail, labels).**
- The gateway's `response` carries the four origin fields, taken from the root row (the R3 conjunct enforces equality; R5 produces it).
- Reproduce, archive read, export and the read tail return the four fields from the stored response or the root via `rw_archive`; they do
  not recompute or default them.
- Labels and claim text read the stored fields, not the scope alone.
- Any later real-path service that produces a manifest must carry `portfolio_id` equal to the root in every manifest-shaped object, or the
  seal refuses it (root binding); and its manifest schema must be on the explicit list in `rw_check_artifact` (a reviewed gateway change,
  made before R5 needs it), or the seal refuses any schema containing "manifest".
- The claim-limit wording does not say the seal verifies identity (5.2), the fictional context (5.5), or the engine manifest's origin (5.4).

## B. Does R5 need the executor to read or write `issuer`, `instrument` or `listing`?

**No. I add no gateway function, and the grants stay removed.** Evidence:

*Reads: none needed.*
- The resolver is built from the locked snapshot in memory (N2b, 4.2 build table; `market_data_store.py:19-21` says the store needs
  "no grant on `listing`"). `read_release` needs SELECT on the `md_*` tables only, and the executor gets those through the thirteen
  lease-checked functions.
- No migration trigger the executor fires reads an identity table: `ledger_event_before_insert`, the split guards (`0007`, `0008`),
  `account_identity_immutable`, `benchmark_selection_before_insert` and the pairing trigger read `ledger_event`, `account` and the
  benchmark tables only (checked by reading the migrations).

*Writes of the create: the rows must EXIST, the executor need not write them.*
- `ledger_event.listing_id` and `md_quote.listing_id` reference `listing` (`0002:30`, `0010:28`). The foreign-key check runs as the owner of
  the referenced table, so the executor needs no privilege for it.
- New R3 test `IdentityRowsTests.test_a_create_writes_a_position_that_names_a_listing_it_holds_no_privilege_on`: under an open create lease the
  executor inserts an `OPENING_POSITION` naming an existing listing (seeded by the owner, E11), the same insert for a listing that does not
  exist is a `ForeignKeyViolation`, a SELECT on `listing` is refused, and the whole create then seals and commits. A second test shows the
  executor's own INSERT into each of the three tables is refused.

*Why a lease-checked identity-writer function is the wrong fix.*
- Identity rows are global, not rooted. The fence and the journal attribute every write to a root; an identity write has none, so
  "behind the fence" would only mean "any create lease may add global rows".
- The only identity writer in the code base is `WebAccountStore._identities` (`web_account_store.py:148-164`), part of the fictional
  `create_portfolio` that the design says the real create does not reuse (fact 3). It inserts `ON CONFLICT DO NOTHING`; a lease holder could
  therefore pre-seed a listing id with wrong currency or MIC, and nothing in a lease could check the row against the snapshot, which holds
  only `identity_digest`.
- The order is wrong for the real database. The loader writes `md_*` rows (which reference `listing`) before any context or lease exists
  (design lines 785 and 2050: "its `md_*` rows are written before any context exists"). So the real identity rows must exist before R4b's
  load, which no lease holder can supply.

**Open item for the main session (not an executor question; no gateway SQL can fix it).** Nothing in the design says who writes
the `issuer`, `instrument` and `listing` rows in the real database before R4b's load. Tests seed them as the owner (E11:
`pk.insert_identity`; the tech plan, 15.17 item 8, says "no identity writer exists"). The real path needs an owner-run, idempotent,
verified seed step: R6's install plan or an R4b/R8 step, from the identity registry the proposal pins, checked against the snapshot's
`identity_digest`. The `SYNTHETIC_TEST` product-path create in R5 needs the same seeding done by its test fixture (as the owner). I
recommend naming the step in R6/R8 now.
