# CP7 F1 on the real-data path: decided design

2026-10-24, engineer. This revises the 2026-10-23 proposal into the design the owner decided. A first
fix round on the same day applied the findings of two independent reviews of the first version
(section 10). A second round applied the findings of their two re-reviews (section 11). **A third round
(section 12) applies the owner's answers in PD-0068 to the questions of section 8.1 and the
open MEDIUM and LOW findings of the two round-2 reviews. A fix round of round 3 (section 13) applies the
findings of the two round-3 reviews (R3C-M1, R3C-L1 to R3C-L7, TR3-M1 to TR3-M4, TR3-L1 to TR3-L8). A
round 4 (section 14) applies the findings of the two re-reviews of that fix round (R3R-M1,
R3R-L1 to R3R-L3, TR3R-M1, TR3R-M2, TR3R-L1 to TR3R-L4), and its second fix round (14.1) applies the
findings of the re-reviews of round 4 (TR4-M1, TR4-M2, R4C-L1 to R4C-L4, TR4-L1, TR4-L2). A round 5 (section
15, at the end) applies PD-0069 (the owner's lease-checked read function for the stored market data) and the
findings of the two re-reviews of the second fix round (R4R-M1, R4R-L1, TR4R-M1, TR4R-M2, TR4R-L1 to TR4R-L3 and
their observations), and its second fix round (15.1) applies the findings of the reviews of that version
(TR5-M1, R5C-L1, R5C-L2, TR5-L1 to TR5-L4). A round 6 (section 16, at the end) applies PD-0070 (the owner's
answers that the loader's login is off between loads and that only create and reproduce read the stored market
data) and the findings of the two re-reviews of round 5's second fix round (R5R-M1, R5R-L1, TR5R-M1, TR5R-L1,
TR5R-L2 and their observations). Where sections 12 to 16 differ, section 16 and the body govern.**

Status: **DECIDED** per PD-0066 decisions 5 to 10
(`decisions/product/PD-0066-hg4-single-date-check-morning-decisions.md`), PD-0067
(`decisions/product/PD-0067-cn-a-share-decisions-2026-10-24.md`), PD-0068
(`decisions/product/PD-0068-f1-design-open-questions.md`, the owner's answers to the former 8.1 items 7 to 10),
PD-0069 (`decisions/product/PD-0069-md-reads-lease-checked.md`, the owner's answer that the stored market
data is read through a lease-checked function; uncommitted, like this file) and PD-0070
(`decisions/product/PD-0070-loader-login-off-between-loads-and-e28.md`, the owner's answers that the loader's
login is off between loads and that only create and reproduce read the stored market data; uncommitted).

- "Decided" covers the owner's choices D1 to D7. The mechanisms that carry them are my design and
  stay design claims until built, tested and independently reviewed. Mechanisms the PDs and
  contracts do not cover are tagged **[E1]** to **[E29]** and listed in section 8.2.
- **Review status.** The reviews of the first version, and the re-reviews of the fix-round version, are
  recorded verbatim in `reviews/TECH_REVIEW.md` (committed at `ae6dfdc`) after the heading "Reviews of
  2026-10-24 build round 1 — recording note" (`:15153`): decision conformance `:15157` and its re-review
  `:15298`; technical review `:15426` and its re-review `:15635`. The round-2 reviews of the decided
  design follow the heading "Reviews of 2026-10-24 build round 2 — recording note" (`:16753`): decision
  conformance `:16757` (open R2-M1, R2-M2, R2-L1 to R2-L7) and technical review `:16911` (open TR2-M1 to
  TR2-M4, TR2-L1 to TR2-L4). Section 10 maps the findings of the first reviews; section 11 maps the
  findings of the re-reviews; **section 12 (round 3) maps PD-0068 and the round-2 findings; section 13 (the
  round-3 fix round) maps the round-3 review findings; section 14 (round 4) maps the findings of their
  re-reviews; section 15 (round 5) maps PD-0069 and the findings of the re-reviews of round 4's second fix
  round; section 16 (round 6) maps PD-0070 and the findings of the re-reviews of round 5's second fix
  round**. The round-3 reviews and their re-reviews (R3C-*, TR3-*, R3R-*, TR3R-*) are recorded verbatim
  at the end of `reviews/TECH_REVIEW.md`, under "Reviews of 2026-10-24/25 F1 design round 3 — recording
  note", the round-4 reviews and re-reviews (R4C-*, TR4-*, R4R-*, TR4R-*) under "Reviews of 2026-10-25 F1
  design round 4 — recording note", and the round-5 reviews and re-reviews (R5C-*, TR5-*, R5R-*, TR5R-*)
  under "Reviews of 2026-10-25 F1 design round 5 — recording note". **This version has not been re-checked
  after round 6 (section 16).** PD-0066 decision 10 requires, before R1: this revision, the technical-reviewer's
  check of it, **and that it is committed when the owner asks** (`PD-0066:376-386`). The design file is
  uncommitted; the owner decides when it is committed, and R1 does not start before then (7.1).
- The proposal is preserved verbatim, 556 lines, SHA-256
  `9c0f221a106686a87e38eea487c2926270798958d6f49e138a9d99965cbd9c79` (recomputed on 2026-10-24 with
  `shasum -a 256`, and again in round 3, in the fix round and in round 5: unchanged; the file is committed at `ae6dfdc`), at `implementation/CP7_F1_REAL_PATH_DESIGN_PROPOSAL_2026-10-23.md` ("proposal :N"
  below; every "proposal :N" is a line of that file, never of the gateway object called a snapshot). It
  holds the full option tables and the review history. The three review rounds in
  `reviews/TECH_REVIEW.md` ("Real-path F1 design (2026-10-23)" `:13723`, "re-review" `:14010`, "final
  check" `:14183`) cite it by line number. This file keeps a short "options considered" note per
  decision.
- Nothing here approves a gate, a data download, a source admission, a publish, or a change to a
  protected file.

What this is: the design for closing F1 ("every writer under one database authority, with
revocation, expiry and commit/rollback") for a **real-data** path, scoped to the smallest target HG4
needs (`reviews/CP7_E9_REAL_SOURCE_AND_UAT_PACKET.md`): one project-constructed, non-personal US
account, 10 AAPL plus USD 500, valued as of 2026-09-30, from Alpha Vantage and OpenFIGI files the
owner downloaded by hand (PD-0063, PD-0064, PD-0066).

How this was checked:

- I re-read STATUS.md items 9 to 11, PD-0066, PD-0067, the proposal, the final-check round of the
  review, and the sources named below. I re-checked every code citation against the tree at HEAD
  `703519c` (first pass; the round-3 re-checks are in the last bullet of this list). Where a line moved since the proposal (the A-share commit `f42efa0` changed
  `ingest.py`, `profiles.py`, `download.py`, `market_data_store.py`), I updated it. Section "Changes
  from the proposal" lists the corrections.
- I ran no test and no build. My runs were read-only: `shasum -a 256` over eight stored files;
  `FileStore(data/marketdata).index()` (fact 13); greps of `src/` (facts 3, 6, 11).
- Fix round, also read-only: `shasum -a 256` of the proposal (the first report misquoted it); `git show
  HEAD:methodology/CP2_MARKET_DATA_CONVENTIONS.md` into a temporary file under `$TMPDIR`, to read Ruling
  6.5 item 6 and Ruling 4.8; greps of `web/src/` and `src/`; the key set of each `SOURCES.json` record.
- I read the structure of `data/marketdata/SOURCES.json` and the terms-check records of three
  sources (fact 15). I read no payload's contents.
- Two parallel tracks were running while I worked (the Quant's `market-data/1.16`, and the engineer
  moving the code label). I did not read or touch their files. At the start of the first pass, `src/`
  was unchanged. In the fix round `git status` shows four `src/marketdata/` files modified by the label
  track. I read `git diff --stat` and grepped their label lines to check two citations (fact 14). I did
  not read the diff.
- Round 2, read-only, 2026-10-24:
  - `git rev-parse` (HEAD `703519c`); `shasum -a 256` of the two files the owner moved (both equal
    PD-0066 decision 9) and of `AAPL_UW.json` and its manifest; `FileStore(data/marketdata).index()`
    (15 entries, no error; fact 13);
  - reads of `guarded_workspace_v1.sql`, `guarded_workspace_store.py`, `guarded_workspace_context.py`,
    `test_postgres_guarded_workspace.py`, `guarded_pg_provision.py`, `guarded_pg_runner.py` and
    `dev_env.py`;
  - the installed PostgreSQL 17.11 manual pages `SET_CONSTRAINTS.7` and `CREATE_TRIGGER.7`
    (`/opt/homebrew/share/man/man7`), read as documentation;
  - `ls -la` of the two PostgreSQL sockets and `id -un` (no connection was made); greps of `web/src`
    and `src/` for display wording (fact 11).
  - **I connected to no PostgreSQL server, ran no SQL and ran no test.** Where a PostgreSQL behaviour is
    stated, fact 17 says whether a HEAD test shows it, the manual says it, or neither does.
- Round 3, read-only, 2026-10-24 (HEAD `7effcc8`, which holds PD-0068 and the label commit `ae6dfdc`):
  - `git log`, `git status`, `git diff --stat 703519c 7effcc8` and a `git diff -U0` of `profiles.py` (to
    move the citations that the label commit shifted); greps of `src/` and `tests/product` for the
    environment-driven PostgreSQL modules, `SET CONSTRAINTS` and `_after_commit_ack`;
  - reads of PD-0066 decisions 5 to 10, PD-0068, the round-2 reviews (`reviews/TECH_REVIEW.md:16753-17121`),
    STATUS.md (the entries on the CP7 cluster, the sandbox exception and items 9 to 11), `methodology/CP2_MARKET_DATA_CONVENTIONS.md` (the 1.16
    change note and item 9, `:3655-3705`), and at HEAD `guarded_pg_provision.py`, `guarded_pg_runner.py`,
    `dev_env.py`, `connection.py`, `guarded_workspace_store.py`, `guarded_workspace_context.py`,
    `guarded_workspace_v1.sql`, `0003_ledger_event_guards.sql`, `test_postgres_guarded_workspace.py` and
    `contracts.py`;
  - the installed PostgreSQL 17.11 manual, as HTML under `/opt/homebrew/share/doc/postgresql@17/html`, read
    as text: `auth-pg-hba-conf`, `auth-trust`, `auth-peer`, `auth-password`, `role-attributes`,
    `predefined-roles`, `catalog-pg-authid`, `catalog-pg-auth-members`, `catalog-pg-database`,
    `view-pg-roles`, `view-pg-hba-file-rules`, `functions-info` (`has_database_privilege`, `pg_has_role`),
    `libpq-connect` (`require_auth`, `passfile`, `service`, `replication`, `connect_timeout`), `libpq-envars`,
    `libpq-pgpass`, `libpq-pgservice`, `app-psql`, `app-initdb`, `sql-alterrole`, `sql-set-constraints`,
    `runtime-config-logging`. I did not read the owner's `pg_hba.conf` or any file of the development
    clusters (the inventory of the owner's environment needs the owner's go-ahead, R6).
  - **I connected to no PostgreSQL server, ran no SQL, ran no test and ran no build in this round.** Where
    a PostgreSQL behaviour is stated below, it says whether a HEAD test shows it, the installed manual says
    it, or neither does ("not shown").
- Round 3 fix round, read-only, 2026-10-25 (HEAD `7effcc8`; `git status` shows this file and
  `.claude/settings.local.json` only):
  - `git log`, `git status`; `shasum -a 256` of the proposal; reads of `PD-0066:170-200` and `:370-392`,
    PD-0068, and `methodology/CP2_MARKET_DATA_CONVENTIONS.md:50-60`; a read-only count of the columns of
    every table in this file (standard output only);
  - at HEAD, reads and greps of `guarded_workspace_v1.sql` (`:286-366`, `:420-445`),
    `guarded_workspace_store.py` (`:266-282`, `:340-360`), `web_workspace_store.py` (`:325-340`),
    `guarded_pg_provision.py` (`:40`, `:64-76`) and `dev_env.py` (`:5-20`, `:60-70`);
  - the installed PostgreSQL 17.11 manual, as text: `libpq-pgpass`, `libpq-pgservice`, `libpq-envars`,
    `predefined-roles`, `functions-info` (`pg_has_role`), `runtime-config-connection` (`listen_addresses`),
    `ddl-priv`, `catalog-pg-database`, `auth-pg-hba-conf`;
  - **I connected to no PostgreSQL server, ran no SQL, ran no test and ran no build.** Where a PostgreSQL
    behaviour is stated, the text says whether a HEAD test or the manual shows it, or that it is "not shown".
- Round 4, read-only, 2026-10-25 (HEAD `7effcc8`): the re-review sections of `reviews/TECH_REVIEW.md`;
  PD-0066 decisions 5 to 8, PD-0068; at HEAD `guarded_workspace_v1.sql` (`:396-425`) and
  `guarded_workspace_store.py` (`:308-372`); the 17.11 manual as text (`catalog-pg-db-role-setting`,
  `functions-info`, `runtime-config-client`, `view-pg-roles`, `role-membership`, `app-initdb`); `echo $TMPDIR`.
  **I connected to no server, ran no SQL and no build, and did not run the product tests: design-only.**
- Round 4, second fix round, read-only (HEAD `7effcc8`): at HEAD `market_data_store.py` (`:10-30`,
  `:517-540`, `:694-745`), migration `0010` and a `git grep` of `src/persistence/migrations` for `ROW LEVEL
  SECURITY` and `CREATE POLICY` (no match); PD-0068; the 17.11 manual as text (`sql-grant`, `functions-info`,
  `sql-altersystem`, `runtime-config-client`). **No server, no SQL, no build, and the product tests were not
  run: design-only.**
- Round 5, read-only, 2026-10-25 (HEAD `7effcc8`; the design and PD-0069 uncommitted):
  - PD-0069; the four round-4 review sections of `reviews/TECH_REVIEW.md` (`:18243-18861`), the open findings in
    the reviewers' own words; `shasum -a 256` and `wc -l` of this file and of the proposal;
  - at HEAD, `git show` and `git grep` of `src/persistence/market_data_store.py` (`:70-76`, `:273-290`, `:404-415`,
    `:446-490`, `:501-616`, `:695-774`), of `FileManifest` and `MarketDataRelease` (`manifest.py:82-110`, `:378-390`)
    for their field lists, of every caller of `read_release` and of `MD_TABLES` in `src/` and `tests/`, and of
    `guarded_workspace_v1.sql` for its definer-function, `search_path`, `REVOKE` and `GRANT` pattern (`:87-450`);
    the tests `test_postgres_least_privilege.py` (`:55-135`), `test_postgres_market_data_store.py` (`:172-194`),
    `test_postgres_cp2_fix_round.py` (`:25-125`) and the two tripwire tests that patch `read_release`;
  - the 17.11 manual as text: `functions-info` (`has_table_privilege`, `has_any_column_privilege`,
    `has_function_privilege`), `sql-createfunction` (SECURITY DEFINER), `sql-insert` (privileges), `libpq-connect`
    (`require_auth`), `sql-createdatabase`, `catalog-pg-db-role-setting`; STATUS.md by quoted text.
  - **I connected to no server, ran no SQL and no build, and did not run the product tests: design-only.**
- Round 5, second fix round, read-only, 2026-10-25 (HEAD `7effcc8`): the findings TR5-M1, R5C-L1, R5C-L2 and
  TR5-L1 to TR5-L4 as the main session gave them; the N2a handover `synthetic_provenance_v1.sql` (`:1-8`, `:56-64`,
  `:148-176`, `:198-250`, `:282-287`) and `synthetic_provenance_store.py` (`:120-150`, `:193-207`, `:225-310`);
  at HEAD the migrations `0009`, `0011` (`:49-91`) and `0016` (`:66-77`), a `git grep` of the migrations for every
  function and for `GRANT`, `REVOKE`, `ALTER DEFAULT PRIVILEGES` and `SECURITY DEFINER`, `guarded_workspace_v1.sql`
  (`:384-450`), `market_data_store.py` (`:273-290`, `:440-495`) and `test_postgres_guarded_workspace.py`
  (`:357-392`); STATUS.md by quoted text (its E25 bullet); the 17.11 manual as text: `functions-info`, `sql-lock`,
  `explicit-locking`, `ddl-priv`, `sql-createtrigger`, `sql-grant`, `sql-revoke`. **I connected to no server, ran
  no SQL and no build, and did not run the product tests: design-only.**
- Round 6, read-only, 2026-10-25 (HEAD `7effcc8`; the design, PD-0069 and PD-0070 uncommitted): PD-0070 in full;
  the four round-5 review sections of `reviews/TECH_REVIEW.md` (R5C-*, TR5-*, R5R-*, TR5R-*), in the reviewers'
  own words; `wc -l` and `shasum -a 256` of this file; STATUS.md by quoted text (its round-5 entry and its "Next"
  list). At HEAD, by `git show` and `git grep`: `market_data_store.py` (`:132-148`, `:497-518`, `:733-738`),
  `guarded_workspace_v1.sql` (`:197-198`, `:384-385`), the migrations for `SECURITY DEFINER`, `CREATE PROCEDURE`
  and every function (`0003_ledger_event_guards.sql:5-12`); the N2a handover `synthetic_provenance_store.py`
  (`:228-302`) and `synthetic_provenance_v1.sql` (`:246-250`, `:281-287`). The 17.11 manual as text:
  `role-attributes`, `sql-createrole` and `sql-alterrole` (`LOGIN`, `NOLOGIN`), `sql-grant` and `sql-revoke`
  (`ALL ROUTINES`, PUBLIC), `functions-info` (the privilege inquiry functions), `queries-table-expressions`
  (table functions), `ddl-rowsecurity`. **I connected to no server, ran no SQL and no build, and did not run the
  product tests: design-only.**
- "Verified" means read in source or recomputed today. Everything else comes from the cited records
  and is as reliable as they are.

## 0. Decisions

| # | Decided | Where | Options considered (full tables in the proposal) |
|---|---|---|---|
| D1 | **B**: separate real namespace, in a **separate database**; storage **S2** (`rw_root`, `rw_revision`); origin fields of 1.1; `state_kind` stays `ACTUAL` (confirmed by the Quant, `market-data/1.16` item 9, committed `ae6dfdc`) | PD-0066 d6 | A, shared canonical tables plus a mandatory link: had run evidence under PD-0059 but needs protected-file edits (proposal :118-128). Own schema versus own database. S1, a relaxing migration `0020` (:146-152) |
| D2 | **R-GW** authority in the gateway; context = **content hash**; a **new scoped contract version** replaces the closed E5 contract for this slice, built in R5, reviewed before use, installed in R7; the **owner is sole publisher** | PD-0066 d7 | R-SPLIT, R-MD (rejected) (:207-214). Logical-id contexts with rebinding (:216-226). Editing E5 in place, or leaving it closed |
| D3 | **X1 lease**: `valid_until` 2027-09-01, renewal recorded by a human, lapse fails closed, all four rights off on end (the gateway's four purposes). **No economic write, seal or guarded load of an operation succeeds at or after `valid_until`, which is what the owner decided (PD-0068 answer 1, "What this means", `:35`): `complete_by = LEAST(admitted_at + W, valid_until)` for every lease. The design adds the same bound for reads of the rooted tables and of the archive (3.1), and, by the owner's PD-0069, for the executor's reads of the stored market data, which go through a lease-checked read function in place of a SELECT on the `md_*` tables (2.6 item 6). Not claimed: that nothing commits after it (3.1). The loader has no lease. The owner decided that its login is off between loads (PD-0070 decision 1; 3.3), so outside a load window the owner opens, no connection as the loader succeeds, at a lapse too; the limits are in section 7.** `NONE` is reachable only with a recorded human non-expiry reading for every member source, so it is unreachable for this source. Expiry bases for HG4: PD-0068 answer 4 | PD-0066 d5; PD-0068 | HOLD (the default until a live-terms reading, :275-294), X2 strict physical expiry (unsupported), X3 non-expiring (not reachable on this reading) (:269-308) |
| D4 | N2a and N2b generalised; N3 re-targeted after N2b; PD-0060's pattern reused; PD-0059's F2 edits retired. Pre-real test path **(a)**: invented data stays `synthetic = true`, a reviewed test-only switch (built in R1) drives the real branch. **One parameterised product module** | PD-0066 d6, d8 | Per patch: adopt, generalise, retire (:334-344). Test path (b), a scoped exception that sets `synthetic = false` on invented data, and (c), leave the real branch to the real run (`reviews/TECH_REVIEW.md` :14209-14250). Scope in test code only |
| D5 | Writer classes confirmed: 7 participate, 2 separate, 6 refused; legacy CLI exports outside the HG4 runtime; owner procedure on withdrawal | PD-0066 d9 | Classes were proposed, not optioned (:353-373) |
| D6 | **`fetch` route**; a canonical **sidecar acquisition record per file** (role, not name); the **owner's digest confirmation** is PD-0066 decision 9; the files already on disk are used; `AAPL_UW.json` is the one OpenFIGI manifest | PD-0066 d9 | Browser download plus `register-file`; a name field in v1; human manifest v2 (:381-418) |
| D7 | R0 is PD-0066 (decision 10: "R0 is this record"; PD-0067 records the CN and label decisions, not D1 to D7), then R1 to R8 in dependency order, updated below | PD-0066 d10 | Order and branch deltas (:441-492) |

R0's last confirmation, the Quant's and not the owner's, is now in: the Quant confirmed that the
constructed AAPL ledger keeps `state_kind = ACTUAL`, marked by its origin fields, in `market-data/1.16`
item 9 (`methodology/CP2_MARKET_DATA_CONVENTIONS.md:3655`, committed `ae6dfdc`), on five conditions that
section 1.1 and 7.4 now carry (round 3). For this purpose I read 1.16's change note and item 9 only.

## 0.1 Facts this design stands on

Verified in source at HEAD `703519c` in the first two rounds, and re-checked in round 3 at HEAD `7effcc8`
where a fact or a citation says so (between the two, the label commit changed only the `marketdata`, `risk`,
`diversification`, `product_contract` and `web_api/analytics_composer.py` sources, `.gitignore` and
STATUS.md; none of `src/persistence`, the F2 SQL, the provisioner, the runner or `dev_env.py`, by `git diff
--stat 703519c 7effcc8` over those paths) on 2026-10-24. Numbers 1 to 11 keep the proposal's
numbering; 12 to 19 are new (16 to 18 were added in the first fix round, 19 in the second; 13, 17 and 18
were rewritten or extended in the second).

1. **The F2 gateway is fictional by construction.** `src/persistence/guarded_workspace_v1.sql`:
   - `:3-7` `gw_snapshot`, with `context_id = sha256(snapshot)`; `:8-13` `gw_head` (generation, rights,
     expiry); `:14-20` `gw_history`, which holds no issuer, decision reference or time;
   - `:21` `gw_mode` allows only `FICTIONAL_ONLY` or `CLOSED`; `:12` the expiry enum is
     `NONE|FINITE|UNKNOWN`;
   - `:141-142` `gw_admit` refuses any other mode; `:145` refuses any expiry other than `NONE`;
     `:146` requires both `ARCHIVE_READ` and the purpose right;
   - `:289-335` `gw_check_artifact` requires `synthetic = true`, the fictional envelope schema,
     source records with `terms_check = null`, capital policy origin `SYNTHETIC_CANDIDATE`, and the
     fixed CP5 question, binding and fixture hashes; `:318` pins `state_kind = ACTUAL`; `:398`
     `gw_seal` repeats `synthetic`;
   - the file never calls `now()` or `clock_timestamp()` (grep), so F2 has no `valid_until` and no
     clock (also FF1-C06 in `reviews/CP7_CLOSEOUT_PREPARATION_2026-10-20/FULL_F1_CASE_MATRIX_V1.json`).

   A real gateway needs all of these predicates replaced.
2. **Writers choose their schema by `search_path`.** `ledger_store.py:72-79`,
   `web_account_store.py:73`; `migrator.py:19` ("Migration SQL must use unqualified names") and `:15`
   ("a change is a new file"). A store runs unchanged on any connection that holds the grants. This
   is why the real namespace is a database with its own roles, not only a schema.
3. **Real root storage is blocked by synthetic labels.**
   - `migrations/0017_web_accounts_and_saved_sandboxes.sql:23`: `mode CHECK (mode =
     'LOCAL_SYNTHETIC_ACCOUNT')` on `web_saved_sandbox`; `0018_web_portfolio_revisions.sql:6` and
     `0019_web_csv_import.sql:4, :16` reference `web_saved_sandbox`, and nothing else does (grep today),
     so a real root with no sandbox row violates no constraint.
   - `web_account_store.py:23` `MODE = "LOCAL_SYNTHETIC_ACCOUNT"`; `:192` account name "Explicit
     fictional sandbox"; `:197` source reference "CP7 saved synthetic opening".
   - The 19 migrations, `CHECKSUMS` and the F2 files are protected.
4. **F2's provenance link is optional.** An ordinary valid F2 lease can commit with no link (case B06;
   `reviews/FULL_F1_REMAINING_2026-10-20/inventory/C02_C03_DECISION_DESIGN_V2.md` section 1; FF1-C02).
   The real seal must make the link mandatory.
5. **Protected-file coupling.** F2 `_stage` runs `SET CONSTRAINTS ALL IMMEDIATE` before N2b attaches its
   link (FF1-C02 `protected_item_conflict`). Under D1 = B no F2 file is edited, so this no longer
   binds.
6. **Manifest acquirers.**
   - `manifest.py:123-124` accepts `human` or `synthetic` only.
   - `manifest_v2.py:81-83` accepts only `agent` with `INTERNAL_DEVELOPMENT_ONLY` at version 2.
   - E1's gate `real_source_contexts.py:210` accepts only `human` and must stay limited
     (`reviews/CP7_E10_EVIDENCE/protocol-author/TRUTHFUL_ACQUISITION_COMPATIBILITY_V1.md:11`).
   - Re-labelling agent bytes as human does not make them human (same file, `:68`).
   - No other module under `src/` imports `marketdata.manifest_v2` (grep today).
7. **Mutable authority today.**
   - `files.py:55-61` reads `SOURCES.json` on demand.
   - `ingest.py:268-274` is the defence-in-depth terms gate in `ingest_file`; it exempts synthetic
     sources (`manifest.py:281-284`, `terms_attested`). The build path calls
     `registry.require_attested` at `ingest.py:869`.
   - The runtime reader `read_release(conn, release_id, ..., *, registry)` takes the registry as a
     required argument (`market_data_store.py:695-699`), so the snapshot's registry copy can be
     passed to it.
8. **A legacy real path exists outside the database.** `src/performance_tools/real_slice.py:59-65` reads
   `FileStore` and the registry directly.
9. **Local real files** (gitignored; names listed, contents not read). Hashes recomputed today
   equal PD-0066 decision 9:
   - Alpha Vantage `AAPL_compact.csv` (2026-10-01), human download confirmed by the owner;
   - OpenFIGI `AAPL_UW.json` (2026-10-23 UTC) is the one file of that lookup in the store. Its
     byte-identical twin `AAPL_XNGS.json`, with its manifest, was moved out of the store unchanged by the
     owner's approval on 2026-10-24, to `data/marketdata/observations/openfigi/identity/2026-10-23/`
     (git-ignored by `.gitignore:43` since `ae6dfdc`; `git check-ignore -v` confirms it today), and is kept
     as evidence (fact 13);
   - the NYSE calendar (2026-10-02) and the CN calendar (2026-10-23, registered under PD-0067
     decision 1);
   - older: the 2026-10-01 OpenFIGI observations, ECB calendar, Frankfurter FX, and AKShare, Sina and
     HK files that this slice does not use.

   No split file is present, and none is wanted (PD-0066 decision 2). Not verified: that the
   2026-09-30 row of `AAPL_compact.csv` is an admissible print (volume, close). Qualification decides
   that (R4b).
10. **Two axes, not one (P8).** `state_kind` is the actual-versus-scenario axis:
    `financial_service_integration.py:327-329` requires `ACTUAL`; `insights/engine.py:126` treats a
    non-`ACTUAL` state or a `scenario_id` as `SCENARIO_UNSUPPORTED`. Fictional versus real *market
    data* is a different axis. F2's fictional portfolios are already `ACTUAL` (`v1.sql:318`). E1 names
    the HG4 ledger `PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED` with `personal_holdings=False`
    (`real_source_contexts.py:322-323`) and a mode string `LOCAL_REAL_SOURCE_TEST_ACCOUNT` (`:17`).
11. **Hard-coded synthetic readers and labels.** A grep of `src` for `LOCAL_SYNTHETIC_ACCOUNT`,
    `synthetic=True`, `"synthetic": True`, `allow_synthetic=True`, `SYNTHETIC_ONLY` matches 18 files
    today: migration `0017` and 17 Python files. R3 audits them (D1, S2). (Both round-2 reviews
    count the same terms over the tracked files of `src/` at 27, once the SQL files, `CHECKSUMS` and the
    fixture JSON are included; the audit uses the terms, not the count.)
    - `persistence/web_account_store.py` (`list_portfolios` `:136-144` returns `MODE` and
      `synthetic: True` without reading the stored mode; capacity count `:186`; create `:192, :197`);
    - `web_workspace_store.py` (`_initial` `:59-65`; `:135` `allow_synthetic=True`; `:216`);
    - `web_csv_store.py` (`:323, :509, :544`);
    - `guarded_http_store.py` (`:150, :326-461`, listing `:374`);
    - `guarded_csv_report_store.py`, `guarded_workspace_store.py`;
    - `web_api/account_routes.py` (`:42`, `:204`, `:214`), `guarded_routes.py` (`:22`),
      `analytics_composer.py` (`:17`), `app.py`, `synthetic.py`, `account_dev.py`, `guarded_dev.py`;
    - the service layer: `financial_service_integration.py`, `performance_service/service.py`,
      `risk_service/service.py`, `performance/engine.py`.

    The web client is outside that `src/` grep. A grep of `web/src` for `LOCAL_SYNTHETIC_ACCOUNT`,
    `synthetic: true`, `synthetic saved` and `synthetic portfolio` matches 16 files, 7 of them not tests
    (`account.ts`, `account-i18n.ts`, `analytics.ts`, `i18n.ts`, `transport.ts`, `guarded.ts`,
    `guarded-csv-report.ts`). Two matter for a real root:
    - `web/src/account.ts:18` types every saved portfolio as `mode: 'LOCAL_SYNTHETIC_ACCOUNT'`,
      `synthetic: true`; `:181` rejects any other value in the list response; `:189` sends the fixed mode;
    - `web/src/account-i18n.ts:10-17` labels the list "Your saved synthetic portfolios" and the
      notice "fictional sandbox only".

    R3's audit covers `web/src` as well (item 6 of section 1). I did not read every one in full.

    **The search terms above miss display wording** (technical re-review L-5). A case-insensitive
    grep for `fictional|sandbox` over non-test files matches 13 files of `web/src` (`App.tsx`,
    `account-i18n.ts`, `account.ts`, `analytics-i18n.ts`, `csv-file.ts`, `csv-i18n.ts`,
    `guarded-csv-report.ts`, `guarded-i18n.ts`, `guarded.ts`, `i18n.ts`, `real-source-i18n.ts`,
    `transport.ts`, `workspace-i18n.ts`) and 18 files of `src/` (my count today; the list overlaps the
    one above only in part and includes `web_api/analytics_context.py`, `analytics_requests.py` and
    `csv_requests.py`). Example: `analytics-i18n.ts:16`, "Read-only analysis of this exact saved
    fictional revision". R3's audit uses the widened terms (section 1 item 6; R3 and R7 rows).
12. **New: synthetic data cannot produce a service-accepted valuation.**
    - `performance_service/service.py:8-9, :172-176, :211-224`: "a USER portfolio is never computed
      from a market-data version that holds a synthetic file". These entries refuse with
      `SYNTHETIC_MARKET_DATA_REFUSED` and give no number. Tests call the engine directly.
    - `financial_service_integration.py` pins `synthetic is True` throughout (`:137, :152, :174, :330,
      :357, :376`). It is a fictional-only integration.
    - FF1-C08 `proposed_minimum.never`: do not flip `synthetic=False`, call a bare engine as a
      substitute, or turn a service refusal into an accepted result. It sets the pre-real evidence at
      "invented preflight and real-service refusal". The first accepted real NAV is the real run's.
    - Consequence for D4 option (a): section 4.4.
13. **Resolved on 2026-10-24: two manifests for one payload had broken the whole store.** The OpenFIGI
    `XNGS` and `UW` payloads are byte-identical (SHA-256 `b2aaeb7b…3ccc`), and each had its own manifest.
    - `FileStore.index()` (`files.py:76-84`; the raise is at `:82`) raises `ManifestError("two manifests
      claim file …")` for such a pair. `build_in_memory_market_data` calls it before it looks at any
      release file (`ingest.py:850`). I reproduced the raise read-only before the move, and so did the
      technical reviewers.
    - `md_file` keeps one manifest per payload and raises `FileRegistrationConflictError` on a different
      one (`market_data_store.py:273-287`; the raise is at `:285`).
    - **The owner approved moving the duplicate out of the store on 2026-10-24.** `AAPL_XNGS.json` and
      `AAPL_XNGS.json.manifest.json` now sit, unchanged, in
      `data/marketdata/observations/openfigi/identity/2026-10-23/`. I recomputed both hashes there
      today: payload `b2aaeb7b…3ccc`, manifest `cb4d862d…3c8d`, both equal to PD-0066 decision 9. The
      store keeps `files/openfigi/identity/2026-10-23/AAPL_UW.json` and its manifest
      (`7952829b…a738`). I ran `FileStore(data/marketdata).index()` read-only today: it returns 15
      entries and does not raise. `observations/` is outside `files/`, so the manifest scan
      (`manifest_paths`, `files.py:72-74`) does not see it, and no release can name it.
    - STATUS.md now records the move (item 11, "Owner-approved data move"). No PD records it; the move came from the
      owner's approval relayed to me in round 2. Whether the main session wants a PD for it is its call.
    - The class of defect remains: any future second manifest for one payload under `files/` stops every
      build, because `index()` is global (section 6.4).
14. **Changed since 2026-10-23.**
    - The A-share route and the listing-market gate are committed (`f42efa0`). `alphavantage.cn` is
      `TO_OBSERVE` (`profiles.py:275` at HEAD `7effcc8`); `PRIMARY_ORDER["CN"] = ()` (`profiles.py:299-300`
      at HEAD); the download tool refuses non-US symbol forms under `alphavantage.us`
      (`download.py:118-126`, applied at `:506-508`).
    - `market-data/1.15` is committed (`44a40e8`).
    - The CN A-share calendar is checked and registered (PD-0067 decision 1).
    - **The code label (round 3: now committed).**
      - Commit `ae6dfdc` moved the code label to `market-data/1.15`. At HEAD `7effcc8`:
        `manifest.py:25` `CONVENTION_SET_ID`, `profiles.py:24` `CONVENTION_SET`, `profiles.py:29`
        `PROFILE_SET_VERSION = "market-data/1.15#profiles/4"` (read today). The same commit re-issued the
        registries (`risk/1.10`, the performance appendix 1.1 and `diversification/1.1`, per STATUS.md item
        11) and committed `market-data/1.16` in `methodology/`. Applying 1.16 to code (label source
        `DECLARED`, A.6 `UW`, then the label to 1.16) is a later increment (R4a).
      - The label commit shifted the `profiles.py` citations of this file by +2 (the `call_adjustment`
        docstring `:83-85`→`:85-87`, the field `:98`→`:100`, its use for `alphavantage.us` `:267`→`:269`,
        the `alphavantage.cn` status line `:273`→`:275`, `PRIMARY_ORDER` `:297-298`→`:299-300`, the MEMORY
        comment `:258`→`:260`). I updated each of them to HEAD `7effcc8`; each names its symbol. Of the other `src/` files that commit changed, the
        only one this file cites is `analytics_composer.py` (fact 11, `:17`); its first hunk starts at
        `:37` (`git diff -U0`), so the citation did not move. `market11.py`, `reconciliation.py`, the
        registries and `risk/` are cited nowhere in this file.
    - **`market-data/1.16` is committed** (`ae6dfdc`). I read its change note and item 9 for round 3
      (`CP2_MARKET_DATA_CONVENTIONS.md:3655-3705`); I have not read the rest, and its method review is
      PASS_WITH_FINDINGS with LOW findings open (STATUS.md item 11).
15. **Source records** (`data/marketdata/SOURCES.json`).
    - `alphavantage.us` (`:91`): `checked_on` 2026-10-01, notes through PD-0064. It does **not** yet
      record the PD-0066 decision 5 reading.
    - `openfigi` (`:156`): notes say MIT licence, no restrictions.
    - `calendar.manual` (`:143`): no third-party terms.
    - Every one of the 13 records holds exactly `source_id`, `name`, `upstream_provider`,
      `independence_group`, `terms_url` and `terms_check` (read today). E1's validator fixes the key set
      and rejects any other key (`real_source_contexts.py:48-50, :146-148, :158`).

    So the only member source with a licence term is Alpha Vantage. A registry record has **no field**
    that says a source is lease-governed or has no time expiry, and E1 would reject one. The
    absence of a recorded term for OpenFIGI and `calendar.manual` is silence, not evidence of
    non-expiry (FF1-C06). The expiry basis therefore cannot be read from the registry; it travels as
    evidence in the publish command (section 3.1).
16. **New: role-level timeouts are not a bound.**
    - The repo sets timeouts on the client side: `web_account_store.py:74` (`SET statement_timeout TO
      '15000ms'`), `guarded_dev.py:112` (connection options `-c statement_timeout=15000 -c
      lock_timeout=3000`), `guarded_pg_provision.py:29` (`SESSION_OPTIONS`).
    - PostgreSQL lets a session set `statement_timeout` and `idle_in_transaction_session_timeout` (and
      `transaction_timeout` where the server has it) with `SET` or a connection option, and that replaces
      a role default. The installed manual says it for role defaults ("You can still alter this setting
      during the session; it will only be the default", `role-attributes`); I did not run it here.
    - So a role-level default cannot be the bound on admitted work. Section 3.1 uses a deadline stored in
      the lease and checked at statement time by the write fence, the seal and the guarded loads, which no
      session setting changes, and again by a deadline guard that PostgreSQL fires inside COMMIT
      processing. Fact 17 says what that guard does and does not bound.
17. **What F2 already has for a deadline check, and what PostgreSQL does with a deferred guard**
    (rewritten in round 2; technical re-review M-1). HEAD citations. "The manual" is the installed
    PostgreSQL 17.11 documentation, read as text; no server was contacted.
    - `guarded_workspace_v1.sql:29-41`: the lease row is keyed `(backend_pid, xid)` and holds no
      timestamp. `gw_admit` inserts it at `:161-162`.
    - `:241-246`: the journal trigger reads the lease on each write by the executor, **but only for a root
      that is in `gw_root`** (`:240` returns first for any other root; fact 19). A deadline check fits in
      the fence (`:197-232`) and the journal at statement time.
    - `:387-389`: `gw_bundle_guard` calls `gw_validate`, and `CREATE CONSTRAINT TRIGGER gw_bundle_complete
      AFTER INSERT ON gw_lease DEFERRABLE INITIALLY DEFERRED` queues one event when `gw_admit` inserts the
      lease. `gw_validate` refuses an unsealed (`OPEN`) lease with `F2_UNSEALED` (`:356`). `gw_seal` also
      ends with its own `PERFORM gw_validate(...)` (`:405`), so the seal checks the bundle at statement time
      and the deferred trigger is a second check.
    - `guarded_workspace_store.py:249-250`: `_stage` calls `gw_seal`, then `SET CONSTRAINTS ALL IMMEDIATE`.
      `execute()` then reads the archive and leaves the transaction block (`:260-264`), so no deferred check
      is pending at that COMMIT. F2 does this so that its checks fail before COMMIT and a failing COMMIT is
      classified UNKNOWN (`:271-272`).
    - `guarded_workspace_context.py:79-102`: `validate_domain_constraints` moves deferrable constraints
      early **by name** (`SET CONSTRAINTS <schema>.<name> IMMEDIATE`, `:100`) from an allowed list of two,
      refuses an unknown deferrable constraint (`F2_UNKNOWN_CONSTRAINT`) or a changed inventory
      (`F2_CONSTRAINT_INVENTORY_DIFFERS`), and **excludes** `gw_root_portfolio_fkey` and `gw_bundle_complete`
      from that list (`:90-91`). **Round 3 correction (conformance R2-L7):** the first of the two allowed
      names, `ledger_event_transfer_pairing` (`:88`, fired by name at `:100`), is itself a deferrable
      **constraint trigger** (`CREATE CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED`,
      `0003_ledger_event_guards.sql:203-205`; contype `t`, which the query at `:84-87` reads from
      `pg_constraint`). So F2 already has the by-name pattern, an inventory check keyed by `(name, table,
      kind)`, and the named form on a constraint trigger. The earlier text said it had not.
    - The manual's Notes (`sql-set-constraints`): constraint names are unique only per table, and "In this
      case SET CONSTRAINTS will act on all matches." A name that two constraints share fires both. The
      deadline guard's name must therefore be unique among the schema's constraints, or naming some other
      constraint could fire the guard early (3.1, 3.2).

    What is shown, and how:

    | Claim | How it is shown | State |
    |---|---|---|
    | A pending deferred constraint-trigger event fires inside COMMIT when nothing moved it, and a refusal there leaves no rows | `test_c13` (`test_postgres_guarded_workspace.py:381-389`): an admit and an `account` insert with no seal; leaving the transaction block raises `F2_UNSEALED` and the `account` count is unchanged. STATUS.md ("runner on the CP7 cluster: workspace 24, http 8 and report 6 all PASS") records the workspace module (24 tests) passing | HEAD test read; **not re-run by me** |
    | `SET CONSTRAINTS ALL IMMEDIATE` fires the pending event at once, also on an unsealed lease | `test_c14`, first half (`:391-399`), expects it to raise on an `OPEN` lease. It asserts only `psycopg.Error`; the bundle guard is the one deferrable check that can fail there, because `validate_domain_constraints` ran just before (my reading). Manual: "any outstanding data modifications that would have been checked at the end of the transaction are instead checked during the execution of the SET CONSTRAINTS command" | test and manual read; **not re-run** |
    | After the event has fired it is not queued again, so a stall after that point is not checked at COMMIT | The manual's word "instead", and E10 section 5 (a final trigger cannot on its own prove validity at the commit). No HEAD test shows it | documented; **not shown by a test** |
    | `SET CONSTRAINTS <trigger name>` fires one constraint trigger and leaves the others pending | `CREATE_TRIGGER.7`: for a constraint trigger the name "is also the name to use when modifying the trigger's behavior using SET CONSTRAINTS". HEAD code names a constraint trigger this way (`ledger_event_transfer_pairing`, `guarded_workspace_context.py:100`), and `test_c14`'s first half (`:391-399`) then expects `SET CONSTRAINTS ALL IMMEDIATE` to raise, which fits the bundle guard having stayed pending after the named firing (my reading; the assertion is `psycopg.Error` only) | documented, and used at HEAD; a test fits it but does not isolate it; **R1 must show it for the deadline guard** |
    | A name shared by two constraints fires both | `sql-set-constraints` Notes: "SET CONSTRAINTS will act on all matches" | documented; **R1 asserts the guard's name is unique** (3.2) |
    | An error raised by a deferred trigger during COMMIT aborts the transaction before the commit is durable | `test_c13` (rows absent after the refusal) for the sibling guard. The order of steps inside PostgreSQL's commit is not in the pages I read | shown for one case; the rest **not run** |

    So the limit stands, and it is this: nothing a client does after its last pending event has fired is
    checked at COMMIT. F2's `_stage` fires everything with `SET CONSTRAINTS ALL IMMEDIATE` after the seal,
    so F2's commit has no pending check. A deadline guard at COMMIT therefore needs its own constraint
    trigger and a create path that fires the other constraints by name (section 3.1, [E4]).
18. **New: how the in-repo provisioner treats connection and passwords.**
    - `guarded_pg_provision.py:91` revokes `CREATE, TEMPORARY` on the new database from PUBLIC. It does
      not revoke `CONNECT`.
    - `:31-32` and `:101`: a role may be created `LOGIN` without a password, "trusted over the private
      Unix socket"; `:174` (`provision_f3`) creates its `_app` role that way. `:104` generates a random
      password (`secrets.token_hex(16)`) inside the installing process.
    - The sandbox allows the PostgreSQL Unix socket (CLAUDE.md), and agent Bash runs as the owner's OS
      user. A socket-trusted role is therefore usable by an agent session. Section 2.5 and R6 depend on
      this.
    - **The test tooling needs a socket-trusted superuser by design** (technical re-review M-3).
      `guarded_pg_provision.py:67-74` refuses to run unless the admin role is a superuser that can
      `CREATE ROLE` and `CREATE DATABASE`; `FINWEB_IT_ADMIN_PASSWORD` is read at `:40` and is needed only
      "if the cluster does not trust the admin role over the socket" (`guarded_pg_runner.py:5-15`;
      `dev_env.py:11`). `dev_env.py:11-13` and `:68` create the executor and account roles with no
      password, "trusted over its private Unix socket". STATUS.md ("Main-session runs: ... runner on the
      CP7 cluster") records that the main session, an agent, ran this runner against the CP7 cluster and
      the modules passed.
    - On 2026-10-24 I saw (by `ls -la`, not by connecting) the shared development socket
      `/tmp/.s.PGSQL.5432`, owned by the same OS user I run as (`id -un`). Reaching a PostgreSQL socket
      is therefore not an owner-only capability in this environment; section 1.2 states what the real
      cluster must not rely on.
    - **Round 3 additions** (conformance R2-M2; technical TR2-M2, TR2-L2):
      - The provisioner's own connections already ignore the user's password file and carry a short
        timeout: `Provisioner.dsn` adds `passfile=/dev/null ... connect_timeout=5`
        (`guarded_pg_provision.py:52-59`). The product helper says the opposite for everything else:
        "libpq reads `PGPASSWORD` / `~/.pgpass` itself" (`connection.py:3-4`), and an env-driven test
        documents "libpq's PGPASSWORD or ~/.pgpass" as its password route
        (`test_postgres_ledger_integration.py:13`). So PostgreSQL's ordinary password stores are part of
        how this repository's tests connect, and an owner who follows them for the real cluster would
        leave a credential an agent session can read (section 1.2 rule 2).
      - Nine test modules reach a server through `connection.conninfo_from_env` or `connection.connect`
        (list in 1.2), not three, and all gate on `connection.missing_env_vars` (`connection.py:55-69`) or
        their own variables. `connection.connect` (`:82-87`) is also called by product code
        (`web_account_store.py:67`).
      - Only the shared development socket is on the harness's allowlist (CLAUDE.md `:102`). The CP7
        cluster's socket "needs a sandbox exception" (STATUS.md, "Main-session runs"). **Corrected in round 5**
        (technical TR4R observation; the earlier text gave both quotations to the CP7 cluster): the other
        quotation, "via a human-approved sandbox exception", is STATUS.md's E0 transport-preflight row on the
        shared socket `/tmp/.s.PGSQL.5432`. That is harness configuration, outside this repository;
        section 1.2 uses it as the weakest of five separations and relies on none of it.

19. **New (round 2): F2's fence and row guard let lease-less writes through for any root that is not
    registered** (technical re-review M-2).
    - `gw_row_allowed` returns `true` when the root is not in `gw_root` (`guarded_workspace_v1.sql:192`).
      `gw_write_fence` sets `selected` from `gw_root` (`:205`) and returns `NEW` for an unselected root
      (`:222-224`). `gw_journal_after` returns before it reads the lease (`:240`). The policies
      `gw_baseline` and `gw_selected_guard` (`:430-431`) apply to the executor and the legacy role.
    - Why F2 can do that: its schema also holds legacy, unselected portfolios, so "not registered" means
      "not governed". Under B (a separate database) there is no such data; the whole database is the
      namespace (section 2.6).
    - FF1-C02 requires "no insert-first/register-later bypass"
      (`FULL_F1_CASE_MATRIX_V1.json`, `cases[1].independent_observables[0]`: "Every selected
      root/account/canonical entity is fenced before any unguarded insertion, including pre-membership ID
      collision; no insert-first/register-later bypass").

## 1. D1: separate real database, storage S2

**Decided** (PD-0066 decision 6): B; a separate database; S2.

What it means for the build:

1. **Real gateway as a fork.** The real database is built from the same 19-migration chain
   (`CHECKSUMS` shared). Only a real-only gateway is installed there (PD-0066 decision 6): a new
   `real_workspace_v1.sql`, forked from the F2 design. No `guarded_workspace_*` file is edited. PD-0059's
   three F2 edits are retired (section 4). **"Real-only" is literal** (conformance R3R-M1): the fork is two
   SQL parts. The real installer runs the first, the authority core and the real branch. The fictional
   branch's seal and validation (4.4) are a second, **TEST-only** part (prospective
   `real_workspace_fictional_v1.sql`; functions only, no table, trigger or constraint) that only the TEST
   provisioner runs, so the real installer never applies it. The executor's table grants are one list in
   both installs (4.2). "One product module" (PD-0066 decision 8) is the Python module that holds every scope;
   the SQL that each install kind holds is not one module. How the core reaches the TEST-only part in a TEST
   install is R3's design and a reviewed item.

   **What shows that a REAL database holds none of it, and when** (technical TR4-M2; conformance R4C-L1). No
   REAL database exists before R8 step 1 (1.2 rule 7), so no test reads a REAL catalog earlier. *R3* shows
   the split, on lists and on TEST installs: the part is its own file, the file and grant lists per install
   kind come from functions of the shared installer code, and a test on them shows that REAL's file list omits
   the part (4.2). *R6's static test* shows that the real installer takes its lists only from those functions
   and never names the part's file. *The installer's Phase 2 and every `--check`* run the catalog audit (R3's
   function: product code under `src/persistence/` that T03 and the installer both import, 1.2 rule 5.3 (e))
   against the REAL database and refuse if a function of the part exists: the first and only read of a REAL
   catalog, at R8 step 1. Until then "a REAL database holds no function of the part" is a design claim resting
   on the first two, not an observation. **Likewise the core without the part is first installed, as a whole,
   by Phase 1 at R8 step 1** (technical TR4R-L3): R3's tests read the lists and TEST installs, not an install of
   REAL's file list, and 1.2 rule 7 says what a Phase 1 failure leaves. The install-kind guard (4.2) stays as a
   second barrier.
2. **Connection is a barrier as well as grants.** Roles are cluster-level objects. The real roles
   (owner NOLOGIN, executor, loader, publisher) get `CONNECT` on the real database, and `CONNECT` on it
   is revoked from PUBLIC and withheld from every legacy and fictional role. Two limits (fact 18):
   - the in-repo provisioner revokes `CREATE, TEMPORARY` from PUBLIC but **not** `CONNECT`
     (`guarded_pg_provision.py:91`), so the installer must add that revoke explicitly;
   - PUBLIC holds `CONNECT` on every **existing** database by default. The manual lists `CONNECT` and
     `TEMPORARY` among the default privileges granted to PUBLIC on databases (`ddl-priv`); that the
     `postgres` and `template1` databases of a fresh `initdb` cluster carry it is my reading, not shown.
     `template0` is protected by `datallowconn` false (`catalog-pg-database`). **A cluster of its own does
     not by itself make "the real roles get no `CONNECT` elsewhere" true** (technical TR3-L3): its
     `postgres` and `template1` are connectable by PUBLIC too. The claim is true only when PUBLIC's
     `CONNECT` is revoked on every other connectable database of the cluster. In a cluster of its own the
     real installer does that itself in Phase 1 (1.2 rule 3) and the preflight refuses if any real role
     still holds `CONNECT` outside the real database (1.2 rule 5.3 (c)). On a shared cluster the same
     revoke on each existing database is an ACL change in an existing non-disposable database and needs its
     own approval (PD-0066 decision 6).

   R6's plan states which of the two applies (1.2 rule 3 prefers a cluster of its own; a shared cluster
   also needs 1.2 rule 1 to hold for all its roles). If neither does, the claim is weaker: "the real
   roles can connect elsewhere but hold no privilege there beyond PUBLIC's defaults", and the catalog
   audit checks that; the preflight would then refuse, so that case is a change to the rule that the owner
   would have to approve. This is a design claim until the catalog audit proves what holds (default
   privileges, role membership, definer functions): on TEST installs in T03, and for the REAL database in the
   installer's Phase 2, first at R8 step 1 (item 1 above).
3. **Placement and credentials.** Which PostgreSQL cluster hosts the real database, and who holds the
   executor and loader credentials, are not in the PDs. They are decided at R6 with the owner's
   go-ahead; R6's plan also states the publisher's authentication (section 2.5). Creating the database
   and roles and installing the gateway is an install step that needs the owner's approval of an exact
   plan, and it follows **the install rule of section 1.2** (every role on the real cluster
   authenticates with a password, no socket-trusted or agent-reachable superuser, a preflight that
   guards REAL installs and refuses them otherwise). It happens after R6 and **before the qualification
   run and the publish in R8**, because the qualification run loads candidates through the loader role
   into the real database **[E8]**. R1 to R7 run only in disposable `TEST` databases on the development
   clusters, built with `tests/product/guarded_pg_provision.py`, which already creates one database per
   run (`:87-89`). That tool, `guarded_pg_runner.py` and `dev_env.py` use a socket-trusted superuser, are
   outside the scope of the 1.2 preflight, and must never be pointed at the real cluster; 1.2 says what
   keeps them apart.
4. **Migrations.** Each future migration is applied to both databases. No SQL goes into an existing
   non-disposable database without its own approval (PD-0066 decision 6).
5. **Accepted cost** (stated to the owner before the choice): B has **no run evidence**. Every ordering
   the PD-0059 prototype proved under A must be proven again for the real gateway: publication races,
   rollback, ACK loss, and the refusal of an ordinary lease without the link (case B06). **Section 4.4
   maps each of the four to the evidence level it can reach before R8. Three can be re-proven on the
   product path or by the real gateway's own refusals. ACK loss on an accepted commit of the real
   branch cannot, and the owner has accepted that limit (PD-0068 answer 2); this design does not claim
   it.** Inside the
   real executor role, isolation still rests on lease triggers, row guards and the seal, not on
   missing grants (section 2.6 says what the fence and the row guard must refuse, registered root or
   not): the stores issue canonical SQL on the executor's connection, so it needs DML on
   `portfolio`, `account`, `ledger_event`, the other canonical ledger tables the stores write (R1's
   role plan lists them) and the `rw_*` tables, and EXECUTE on the lease-checked `md_*` read functions for
   `read_release` (W05; 2.6 item 6, PD-0069). It gets **no privilege** on any `md_*` table, on
   `web_saved_sandbox`, `web_portfolio_revision` or `web_csv_*`: under S2 no real path writes the last
   three (W07, W08). That is a design claim; T03 and R3's audit check it.
6. **Storage S2.**
   - Real roots and revisions live in add-on tables `rw_root` and `rw_revision`, installed beside the
     gateway. They need no migration.
   - They are never stored in `web_saved_sandbox` or `web_portfolio_revision`.
   - `portfolio`, `account` and `ledger_event` stay canonical.
   - New real create code is required; `WebAccountStore.create_portfolio` has fixed synthetic labels
     (fact 3).
   - R3 audits every reader of the shared canonical tables, starting from fact 11, so that none
     stamps a real portfolio synthetic (P9). A reader that starts from `web_saved_sandbox` never
     enumerates a real root. **The audit covers `web/src` too** (fact 11): the client types every
     saved portfolio as synthetic and rejects any other value, so a real-mode list needs its own
     client type and labels, derived from the stored origin fields. R7 does not reuse `AccountPanel`'s
     list as it stands. **The audit's terms include the display wording** `fictional`, `sandbox`,
     `synthetic` and `invented` (case-insensitive; fact 11 gives today's counts), not only the mode
     strings, and its exit lists every hit that can reach a real root's output with its disposition:
     removed, or made to depend on the stored origin fields. A pure render test on an in-memory row
     labelled `REAL_SOURCE` (never stored) checks that none of that wording appears in any string the
     real root's output or UI uses (R3 for server-built strings, R7 for the client).

### 1.1 Origin of a root

Origin labels follow the **origin axis** of the scope (section 4.2), not the branch **[E16]**. A root
that runs the real branch on invented data (`TEST_SWITCH`) is labelled as invented.

- **`REAL` scope.** The root records, immutably, in its policy row and in every output: `market_origin =
  REAL_SOURCE`, `ledger_origin = PROJECT_CONSTRUCTED_NONPERSONAL_UAT`, `personal_holdings = false`,
  and account and opening labels that say so. The UI shows the portfolio as a project-constructed test
  account, never as the owner's holding.
- **`SYNTHETIC_TEST` and `TEST_SWITCH` scopes.** The root records `market_origin = SYNTHETIC_TEST`,
  `ledger_origin = INVENTED_TEST_LEDGER` (prospective names), `personal_holdings = false`, `synthetic =
  true`, and account and opening labels that say the data is invented. `REAL_SOURCE` never appears in a
  stored row or an output of a test scope.
- A row guard in the seal refuses a root whose origin labels do not match its scope: `REAL_SOURCE` only
  under `REAL`, `SYNTHETIC_TEST` only under the two test scopes.

`state_kind` is not the place for this (fact 10). The financial service requires `ACTUAL`, and a
constructed ledger is not a scenario. So `state_kind` stays `ACTUAL` and "not the owner's holding" is
carried by the origin fields. **Confirmed by the Quant** in `market-data/1.16` item 9
(`CP2_MARKET_DATA_CONVENTIONS.md:3655`, committed `ae6dfdc`; the open item of PD-0066 decision 10), on
five conditions, which this design carries (round 3; the conformance review of round 2 asked that they
be picked up, as an observation):

1. **Mandatory and immutable.** The origin fields are written once on the root and carried into every
   manifest and result that reads it (P9). `personal_holdings` is stated explicitly, `true` or `false`; if
   it is missing the computation is refused. It is **never defaulted**, either way. The real seal's row
   guard (above) refuses a root with a missing origin field.
2. **Independent of `synthetic`.** `market_origin` describes the market data: `REAL_SOURCE` only if `M`
   holds no synthetic file (Ruling 4.8 item 2). The ledger carries no real/synthetic flag, and a
   constructed ledger does not make a result synthetic.
3. **No crossing of baselines.** A constructed root's results never serve as a baseline or comparison for
   a personal root, nor the reverse (P4). 1.16 notes that CP6's `history_problem` scope check already
   refuses a baseline whose portfolio, account, state or scenario differs (`SCOPE_MISMATCH`). The real
   gateway adds no code that compares history across roots; any later component that does must keep that
   scope check or carry the portfolio, account, `ledger_origin` and `personal_holdings` in its key.
4. **The axes are orthogonal.** A scenario run on the constructed ledger later is `HYPOTHETICAL` with the
   same origin fields (Scenario Lab is not designed here, section 9).
5. **Claims.** Claim N-8 of 1.16 item 6 applies: the quantity is the project's ledger fact, never "your
   holding". 7.4 (C6) carries it; how it is worded on screen is the designer's.

### 1.2 Install rule for the real cluster [E8, E20, E24]

**Amended 2026-11-07 by PD-0078 (`decisions/product/PD-0078-fifth-account-role-for-web-accounts.md`): the real install has FIVE roles.** Wherever
this section says "the four real roles", "the four roles" or lists "owner, executor, loader, publisher", read **owner, executor, loader, publisher and
`account`**. The fifth role, `finweb_real_account`, is created by Phase 1 `LOGIN` with no password; it holds `SELECT` and `INSERT` on `app_user` and
`web_identity`, `SELECT`, `INSERT`, `UPDATE` and `DELETE` on `web_session` and `web_auth_rate`, and `USAGE` on the schema, and nothing else (no
economic or rooted table, no `md_*` table, no gateway function, no sequence). It joins every check that meets the real roles (the connection barrier,
no membership, the probe, the verifiers, the login-state print) and the catalog audit's comparison in rule 5.3 (e) (iii), where it is a fourth
principal beside the executor, the loader and the publisher. Its password is the owner's alone, typed at the real-mode launcher's prompt in the owner's
own terminal (PD-0077's rule); no agent session holds it. The text below is otherwise unchanged; the build is `real_roles.ACCOUNT_TABLES`, `real_install`,
`real_preflight.REAL_ROLES` and `real_catalog_audit.audit(account_role=...)`.

Technical re-review M-3, redesigned in round 3 (conformance R2-M2; technical TR2-M2, TR2-M3, TR2-M4,
TR2-L1, TR2-L2) and amended in the round-3 fix round (technical TR3-M1 to TR3-M3, TR3-L1 to TR3-L5; the
amendments are marked where they stand and listed in section 13). This is a rule that R6's plan and R8 step 1 must satisfy. It is an **owner-approved
environment step**: nothing in this design installs, reconfigures or connects to anything, and the owner
approves the exact plan at R6 (PD-0066 decision 10).

**Why a rule is needed.** E19 puts the password control on the publisher role. A superuser can `SET ROLE`
to the publisher, or insert history and head rows directly, with any issuer and decision reference it
chooses to write; the owner's publisher password is then never used. In this environment an agent
session can reach a PostgreSQL socket as the owner's OS user, and the repo's own test tooling runs
against a socket-trusted superuser (fact 18). If the real database sat in a cluster that trusts a
superuser, or any member of the publisher or owner role, over the socket, PD-0066 decision 7
("never to agent sessions") would be false in practice.

**Scope: what the rule and its preflight guard, and what they do not** (conformance R2-M2; technical
TR2-M4). They guard a **REAL install** and nothing else: a database whose install kind (E6) is `REAL`, and
the cluster that hosts it. They do **not** cover, and say nothing about:

- TEST installs: the disposable databases that R1 to R7 build on the development clusters;
- the two development clusters themselves (the shared one on `/tmp/.s.PGSQL.5432` and the CP7 cluster),
  which trust their superuser over the socket by design (fact 18);
- the test tooling `guarded_pg_provision.py`, `guarded_pg_runner.py` and `dev_env.py`, which keep their
  socket-trusted superuser and password-less roles;
- the environment-driven PostgreSQL tests. Nine modules under `tests/product` reach a server through
  `connection.conninfo_from_env` or `connection.connect` (a grep today: `pg_market_kit.py`,
  `test_cp1_reconstruction.py`, `test_marketdata_cp2c2_exit.py`, `test_postgres_e0b_smoke.py`,
  `test_postgres_least_privilege.py`, `test_postgres_ledger_integration.py`,
  `test_postgres_replay_integration.py`, `test_postgres_risk_free.py`, `test_postgres_web_auth.py`), and
  `test_postgres_connectivity_preflight.py` reads variables of its own.

No tool of those groups is given the preflight, so none can fail it and none needs a bypass: R1 to R7 run on
TEST installs and never meet it. R1's publisher-tool tests, R7's Playwright run through the real-mode
launcher, and the existing runner all work as they do today. **What keeps those groups apart from the real
cluster** is a set of means other than the preflight, listed from strongest to weakest:

a. **A cluster of its own** for the real database (rule 3): no shared role namespace and no shared socket.
b. **The install kind in both directions** (4.2): a TEST database refuses `REAL` snapshots and a REAL database
   refuses test scopes, at publish and at admit, so a test run that reaches the wrong database can neither
   publish nor admit content of the other kind there.
c. **The real tools take their target from the database itself** (rule 5): a REAL database always gets the
   preflight and a TEST database never meets it, whatever the caller passes.
d. **Name tripwires** (rule 6): the provisioner and the environment-driven tests refuse a database or cluster
   in the real install's reserved namespace.
e. **The sandbox's socket allowlist.** Agent Bash may reach `/tmp/.s.PGSQL.5432` (CLAUDE.md `:102`); the CP7
   cluster's socket "needs a sandbox exception" (STATUS.md). A real-cluster socket outside the
   allowlist is therefore not reachable from an agent's Bash without an approved exception. **This is the
   weakest of the five and is not relied on**: it is harness configuration outside this repository, an
   exception can be approved, and an agent outside that sandbox is not covered.

1. **A password for every role; no trust.**
   - Every role that can connect to the real cluster authenticates with `scram-sha-256`
     (`password_encryption = scram-sha-256`) over the Unix socket. The only methods that may appear in
     `pg_hba.conf` are `scram-sha-256` and `reject`.
   - `pg_hba.conf` has no `trust`, `peer` or `ident` line for **any** role of the cluster, privileged or not
     (technical TR2-L1; E20 and the round-2 row said "privileged" and are corrected). `peer` accepts the
     connecting OS user by name, and agent Bash runs as that user, so `peer` for any role is as open as
     `trust`: for the executor it would hand the product's own admitted paths to every agent session (rule 4).
     The manual says of `trust` that PostgreSQL "assumes that anyone who can connect to the server is
     authorized to access the database with whatever database user name they specify (even superuser
     names)" (`auth-trust`).
   - `listen_addresses` is empty (no TCP), and `pg_hba.conf` holds `local` lines only.
   - Socket mode `0700` (the CP7 cluster is started with `unix_socket_permissions=0700`, STATUS.md
     "Running services") is **not** a control against an agent that runs as the owner's OS user.
   - **The cluster is created so that no trust line ever exists.** The manual says `initdb` makes `trust`
     the default "for ease of installation" (`app-initdb`, `--auth`), so the owner runs `initdb
     --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwprompt` (all three options are in the
     manual) and deletes the `host` lines it writes, since this cluster has no TCP. Not `--pwfile`, which
     keeps the bootstrap superuser's password in a file. This is an owner procedure that I have not run;
     the installer's Phase 0 (rule 5) checks the result.
2. **The superuser password and the publisher password are the owner's alone, and are kept only where no
   agent session can read them.** The owner sets each in their own terminal with psql's `\password`, which
   the manual says "encrypts it, and sends it to the server as an ALTER ROLE command. This makes sure that
   the new password does not appear in cleartext in the command history, the server log, or elsewhere"
   (`app-psql`); the manual's caution on `ALTER ROLE` says the same of a literal password: it "might also be
   logged in the client's command history or the server log" (`sql-alterrole`). Neither password is ever in
   a project file, in the environment of a process an agent starts, passed to an installer or test tool that
   an agent runs, or generated by one. No agent session is given either. The publisher role is created
   without a password; the manual says "if no password has been set up for a user, the stored password is
   null and password authentication will always fail for that user" (`auth-password`), so it cannot log in
   until the owner sets one (2.5). This is an operational control and a record, not proof of identity.

   **What is a checkable rule and what is an owner procedure** (technical TR2-M2). PostgreSQL's ordinary
   password stores are readable by the owner's OS user, and agent Bash runs as that user (fact 18). The
   repository's own helper and a test name two of them as the route (`connection.py:3-4`,
   `test_postgres_ledger_integration.py:13`).

   | Store or path | Rule | Kind | What checks it, and how far |
   |---|---|---|---|
   | libpq's default credential sources: `PGPASSWORD`, `PGPASSFILE` / `~/.pgpass`, `PGSERVICE` / `~/.pg_service.conf`, `PGSERVICEFILE`, `PGSYSCONFDIR` (`libpq-envars`, `libpq-pgpass`, `libpq-pgservice`) | no credential for any LOGIN role of the real cluster is held there; `PGPASSWORD` is unset | **Checkable: by the static scan (Pass S, rule 5.3 (d)). Pass B is a backstop only** (technical TR3-M1) | **Pass S** reads the caller's environment, the files it names **and the default locations too**, without connecting. It refuses on any entry that could address the real cluster, **whatever the file's mode and whether or not any service is named**, and on any line or section whose user field names a LOGIN role of the real cluster, **whatever its host or port** (technical TR3R-L1); it prints no password. **Pass B**'s connection attempts show only that a credential libpq *would use* works. They cannot show that none is stored: the manual says a passfile with group or world access "will be ignored", and a service file is used only when a service name is given (`libpq-pgpass`, `libpq-pgservice`), so every attempt can end `CHALLENGED` while the credential sits in a file an agent can `cat`. The scan sees only those stores (its limits are in 5.3 (d)) |
   | `~/.psql_history`, or the file `PSQL_HISTORY` / `HISTFILE` names (`app-psql`) | no literal `PASSWORD '...'` statement for these roles was ever typed | **Owner procedure** (use `\password`); a heuristic count is optional | The owner-run installer may count history lines that match `PASSWORD '` and print only the count; a zero proves nothing about other editors or shells |
   | Shell history, terminal scrollback, editor buffers, clipboard, screenshots, password-manager exports, notes, backups | no copy of the superuser or publisher password | **Owner procedure** | Nothing checks them, and nothing in the database can |
   | The server log: `log_statement` `ddl`, `mod` or `all` logs `ALTER ROLE`, and the manual warns that logged statements "might reveal sensitive data and even contain plaintext passwords" (`runtime-config-logging`); `log_min_duration_statement` and `log_min_error_statement` can log statement text too | the installer sets no password; the owner sets them with `\password`; the log setting is `none` while passwords are set | **Checkable setting; owner procedure for the file** | The installer reads `log_statement`, `log_min_duration_statement` and `log_min_error_statement` before and after the owner sets passwords, and refuses while `log_statement` is not `none`. A setting read now says nothing about earlier logging; the log file's own permissions are the owner's |
   | Where the cluster lives: `data_directory`, `hba_file`, `ident_file`, `unix_socket_directories`, and the OS permissions of those paths and of `postgresql.conf` | not under the repository root or the system temporary directory; not writable by an agent session | **Partly checkable; owner procedure** | The installer prints those settings and refuses if any lies under the repository root or the system temporary directory. The full list of the sandbox's write paths is harness configuration that neither the database nor the tool can read, so the check is partial. OS permissions are invisible to the database; a dedicated OS user for the cluster is the strong form and the owner's call |
   | The credentials of the executor and the loader (rule 4) | not in the environment, a project file, a passfile or a service file | **Checkable (Pass S, then Pass B); owner procedure for the rest** | As for the first row; every real tool takes its own credential from a prompt in the terminal that starts it (R6's plan may name another route, never an environment variable, a project file, a passfile or a service file). Who holds each credential is R6's approved plan (rule 4); R8 step 1 follows it |

   **What cannot be enforced from inside the database, said plainly.** The database can show roles and their
   attributes; to a superuser only, the password verifiers and the rows of `pg_hba.conf`; and, from the
   vantage of whatever process makes an attempt, whether a connection succeeds. It cannot show how a password
   was typed or where else it was kept, what a process running as the owner's OS user can read, the
   permissions of the data directory and its configuration files, or a credential that an agent obtains from
   outside the cluster. A preflight that finds no credential-free path shows only that none exists, from where
   it ran, now. It does not show that no agent holds a password. For the superuser and publisher passwords the
   owner's procedure is the control and the design adds nothing to it.

   **What the static scan adds and what it cannot see** (technical TR3-M1; stated again in 5.4). It reads the
   environment variable `PGPASSWORD` and the passfile and service files that libpq could read. It cannot see a
   password in any other file under the owner's home (a notes file, a shell profile that exports
   `PGPASSWORD` for a later shell, a `.env` file), in another process's environment, in an application's own
   configuration, or in a service file at a path that only a connection string elsewhere names. The rule
   for those is the one the table states: the superuser password and every real-role password are
   **not stored where an agent session can read them**. The scan checks the stores libpq itself would
   use, and the rest is the owner's procedure.
3. **Placement.**
   - Preferred: a cluster of its own, so that rule 1 covers every role there. With the installer's own
     revoke of PUBLIC's `CONNECT` on `postgres`, `template1` and any other connectable database of that
     cluster (Phase 1; the real installer, run by the owner as the superuser), the claim "the real roles
     get no `CONNECT` elsewhere" (section 1 item 2) becomes true, and the preflight checks it (5.3 (c)). A
     cluster of its own does not make it true without the revoke (technical TR3-L3).
   - A shared cluster is acceptable only if rule 1 holds for every role of that cluster. That rewrites
     the existing development cluster's `pg_hba.conf` and passwords. It is a change to a non-disposable
     environment and needs its own approval (PD-0066 decision 6). **Its consequence, stated plainly**
     (technical TR3-L5): the existing superuser-driven test tooling could **never run again** on that
     cluster. `guarded_pg_provision.py:73-74` refuses unless the admin role is a superuser that can
     `CREATE ROLE` and `CREATE DATABASE`; rule 2 forbids giving an agent-run tool a superuser password; and
     5.3 (a) allows one LOGIN superuser and refuses every other LOGIN role with a power attribute, and
     5.3 (b) refuses a LOGIN role's membership in any other role. **Neither has an exemption list**
     (technical TR3R-M1), so no list can put the test tooling's roles back, and every other LOGIN role of
     that cluster must pass 5.3 as written, memberships included. The earlier wording, that the tests
     "would stop working until each is given credentials", is withdrawn: giving them credentials is not
     available. The owner would have to move the test tooling to another cluster, which is close to the
     preferred option, so the shared option is exceptional and is kept only for completeness.
   - Either way, the data directory and `pg_hba.conf` should be outside the project directory and
     `$TMPDIR`, which are the sandbox's write paths (STATUS.md records the CP7 development cluster as
     `-D .local/cp7-postgres/data`, a relative path). A dedicated OS user for the cluster is the strong
     form and the owner's call. **Not claimed:** protection against an agent that can read or write the
     data directory or `pg_hba.conf` as the owner's OS user. R6's inventory states which of these holds.
4. **Executor and loader credentials** are passwords too, and R6's plan names who holds each. An agent
   session that holds the executor credential can run the product's own admitted paths (create, read,
   reproduce) while the context is live. The lease, the fence, the read bound of 2.6 item 2 (the rooted
   tables and the archive) and the deadline still bound that, and so does the lease check of the `md_*` read
   functions (2.6 item 6): the executor holds no privilege on any `md_*` table, so a lapse or a withdrawal stops
   its reads of the stored market data as well (PD-0069). It is still the product's authority and not the
   publisher's, and it is recorded as a limit. **The loader's reads are the part that no lease reaches**: it
   has no lease (its `md_*` rows are written before any context exists, W04; under N2a's binding it also
   registers the context-bound candidates after the publish, 3.3 item 1), it is narrowed to `INSERT` on the
   `md_*` tables, `SELECT` on `md_file` and `md_release`, and `EXECUTE` on the candidate registry's put and get
   functions (3.3), and the get function returns the payload bytes, prices included (technical TR5-M1). **The
   owner decided that the loader's login is off between loads** (PD-0070 decision 1; 8.1 item 12): the owner
   sets the loader role `NOLOGIN` right after its last use in R8 (3.3 item 1 says where that falls) and
   `LOGIN` again only for a later load.
   So **outside a load window the owner opens, nobody can log in as the loader, whoever holds its
   credential**; inside a window the holder R6's plan names, an agent session included, can read what the
   list allows (3.3). The limits are in section 7. The launcher, the admission probe and the publisher tool take their
   own credential from a prompt in the terminal that starts them, never from the environment, a project
   file, a passfile or a service file (the table under rule 2); R6's plan may name another route that avoids
   those. **R8 step 1 follows R6's approved plan for who holds the executor and loader credentials**
   (conformance R3C-L4); it does not decide that itself.
5. **A preflight for REAL installs only, with no switch** (conformance R2-M2; technical TR2-M3, TR2-M4).

   **5.1 Who runs it, and from where.** Each runs the checks its own vantage can make, and only against a
   REAL target (5.2).

   | Runner | When | Vantage | What it does |
   |---|---|---|---|
   | **The real installer** (prospective `real_install.py`, built in R6; run only by the owner, in the owner's terminal, as the cluster's superuser typing its password at a prompt) | Phase 0 before it creates anything; Phase 2 after the owner has set the passwords; and on demand in a read-only `--check` mode that the owner re-runs after any change to `pg_hba.conf`, roles or grants | superuser | The inventory and the probe of 5.3, plus the superuser-only checks of 5.3 (e), which include the catalog audit. Refuses on any failure; Phase 0, Phase 2 and `--check` write nothing, but what Phase 1 created stays (rule 7: a refusal after Phase 1 leaves a created install). It writes install kind `REAL` and no other, and has no TEST mode. It connects with `require_auth=scram-sha-256` and never takes a password from the environment, a file or an argument |
   | **The publisher tool, commands `publish` and `renew`** (a renewal includes a date correction, 3.1 / E25) | each invocation, before it changes anything | the publisher role (a non-superuser) | **The gate**: the self-check, the probe of 5.3 (a) to (d) (Passes A, S and B) and the `listen_addresses` check of 5.4, only when the target is REAL. Refuses, and writes nothing, on any failure. These commands can widen rights, so they are gated even when one renewal only shortens `valid_until`: the command decides, not its content. An owner who needs a shorter life at once withdraws (next row) |
   | **The publisher tool, command `withdraw`** (and re-running a pending withdrawal) | **never gated** | the publisher role | **Not gated** (technical TR3-M3). It reads the facts of 5.2 only to learn whether the target is REAL; it connects without the `require_auth` demand (so it would answer a server's request for a cleartext password; not narrowed, because that needs an impostor on the socket path, which is inside rule 7's boundary, and a `require_auth` refusal would be one more thing that can stop a withdrawal. **A third option for the owner, not taken here** (technical TR4R observation; 8.1 PM list (v)): the negated demand `require_auth=!password`. The manual says of a negated method that "the server must not attempt the listed method; any other method is accepted" (`libpq-connect`), so it refuses only a request for a cleartext password. Under rule 1 the real server never makes one, so it would stop a withdrawal only where an `hba` line that rule 1 forbids exists, or an impostor answers); it **commits the drain mark first**, then waits and appends the generation as 3.1 says, and **then** runs the self-check and the probe and prints the result beside the withdrawal's own. A failing, timed-out or refusing preflight changes nothing about the withdrawal, and its exit status is the withdrawal's own (done, or the status of its own for "not yet effective"). A withdrawal only narrows (all four rights false), so a damaged environment is a reason to report and not to refuse. The result is printed, not stored in a database column; the owner may paste it into the withdrawal's decision record |
   | **The real-mode launcher** | at start | the executor role (a non-superuser) | The gate, as for `publish` |
   | **The admission probe** (prospective, built in R7; E27) | at start | the executor role (a non-superuser) | The gate, as for `publish`. It is how R8 shows the export right refused (7.1) |

   *Note (PD-0076 E):* the owner chose the negated demand for `withdraw`, so its connection is made with `require_auth=!password` (the "connects without the `require_auth` demand" wording above and in 7.1 is superseded by this).

   The installer does not check that "the role it runs as is NOSUPERUSER" (round 2 said so, and no installer
   could pass that): it runs as the superuser and instead checks **every other path and every role it
   creates**, and its own connection must complete SCRAM. The runtime tools check that they themselves
   are not powerful. **The rule is keyed to the command, not to a flag**: no argument, variable or key
   moves a command from one row to another, and nothing asks `publish` to behave like `withdraw`.

   The TEST provisioner (R1 extends `guarded_pg_provision.py` to install the real gateway in
   disposable databases) writes install kind `TEST` and no other, and refuses a cluster that holds a
   `finweb_real*` database (rule 6). Each installer cannot write the other's kind.

   **5.2 What is a REAL target, and why no bypass is needed or possible [E24].** A tool decides from two
   facts that it reads, never from an argument, environment variable or configuration key:

   | Install-kind row of the database | Database name | Decision |
   |---|---|---|
   | `REAL` | starts with the reserved prefix `finweb_real` (prospective) | **REAL**: connect with `require_auth=scram-sha-256` from the first connection, run the preflight, refuse on any failure |
   | `TEST` | does not start with it | **TEST**: no preflight; TEST scopes only (4.2) |
   | `REAL` | anything else | refuse (kind and name disagree) |
   | `TEST` | starts with the reserved prefix | refuse (kind and name disagree) |
   | missing, unreadable or more than one row | any | refuse (not an install of the real gateway) |

   `require_auth` is a libpq connection parameter (`libpq-connect`): if the server does not use the required
   method, "the connection will fail", and by default "the server is free to skip authentication
   altogether". So a trust or peer line for the tool's own role fails on the client side, with no catalog
   read. A name that starts with the reserved prefix gets `require_auth` from the first connection; any
   other name is connected as today (the development clusters), and the tool then reads the kind row and
   refuses on a disagreement. **This table decides the gated commands of 5.1** (`publish`, `renew`, the
   launcher, the admission probe). For `withdraw` (technical TR3-M3) it decides only whether the
   preflight result is printed: a name and kind that disagree, or a `TEST` kind, never stop a withdrawal
   (it only narrows). A missing, unreadable or duplicated kind row means there is no real gateway to
   withdraw from, and the tool says so and writes nothing.

   Consequences for R2-M2 and TR2-M4: there is **no flag, environment variable or configuration key** that
   selects, skips or relaxes the preflight, so there is nothing to invent outside review. A REAL database
   always gets it. A TEST database never meets it, which is why R1's publisher-tool exit-status tests and
   R7's launcher run on the development clusters unchanged. An argument cannot lower a REAL target to TEST,
   because the kind comes from the database. Someone who can rewrite the kind row and rename the database
   already owns the database or the cluster: that is the trusted-operator boundary (rule 7), and the
   preflight is a tripwire for the cases before it. **Tests.** *R6*: a static test lists the option names and
   the environment reads of the tools that exist at R6 (the installer, built there, and the publisher tool,
   built in R1, to which R6 adds the gate) and shows that none reaches the decision of 5.2 or the arguments of the preflight, and (technical TR3-L2) that **none
   offers a credential option (password, password file, passfile) and none reads a credential from the
   environment**: the prompt is the only route, in the tests too (rule 7). The preflight's entry point takes
   only facts read from the server and from the process's own stores; a test for each row of the table above
   and for each command of 5.1 that exists at R6 (`publish`, `renew`, `withdraw`). *R7* extends the same
   static test and the by-command tests to the launcher and the admission probe when it builds them
   (technical TR3R-L3: an R6 test cannot list the options of a tool that does not exist yet). The gate is a
   **separate item in R6's independent review** for the installer and the publisher tool, as the test switch
   is in R1's, and a separate item in R7's for the launcher and the probe.

   **5.3 What the probe inspects and tries.** Every attempt is read-only: no statement is sent, and a
   successful connection is closed at once. The functions and views are as the installed manual documents
   them; none was run (rule 7).

   a. *Roles* (`pg_roles`, "a publicly readable view" of `pg_authid`, `view-pg-roles`): every role with
      `rolcanlogin`; every role with any **power attribute**: `rolsuper`, `rolcreaterole`, `rolcreatedb`,
      `rolreplication` or `rolbypassrls`; and `rolvaliduntil` and `rolconfig`.
      - **At most one LOGIN role has a power attribute, and it is a superuser** (the one the owner runs the
        installer as). No list names it (technical TR3R-M1): any other LOGIN role with a power attribute, and
        a second LOGIN superuser, refuse.
      - **No real role has a role-level setting** (technical TR3R-L2, the smallest check that closes it):
        `rolconfig` of every real role is empty, no `pg_db_role_setting` row names a real role or the real
        database (a row that names neither, as `ALTER ROLE ALL SET` writes it with `setrole` and
        `setdatabase` both 0, `catalog-pg-db-role-setting`, is **not refused**: technical TR4R observation;
        refusing it would add a rule, so the claim is narrowed to the real roles and the real database, and the
        `SHOW` below sees the one setting that matters), and
        `has_parameter_privilege(role, 'session_replication_role', 'SET')` **and**
        `has_parameter_privilege(role, 'session_replication_role', 'ALTER SYSTEM')` are false for **every
        LOGIN role other than the one LOGIN superuser, and for `public`** (technical TR4-L2: the manual lists
        `ALTER SYSTEM` as the second parameter privilege, `sql-grant` and `functions-info`; technical TR4R-L1:
        `ALTER SYSTEM` writes a value for the whole cluster, so the question is asked of every LOGIN role and
        not only of the real ones; the manual's preface to these functions says that a user named `public` is
        checked as the PUBLIC pseudo-role), and the tool's own session reads `SHOW
        session_replication_role` and refuses unless it is `origin` (which also covers a cluster-wide default;
        5.4). The manual says that with `session_replication_role =
        replica` triggers "that have not been altered from their default configuration" do not fire, and that
        "only superusers and users with the appropriate SET privilege can change this setting"
        (`runtime-config-client`); a value written by `ALTER SYSTEM` is "effective after the next server
        configuration reload", and only a superuser or a role granted `ALTER SYSTEM` on that parameter can
        write it (`sql-altersystem`). The gateway's fence, journal, bundle guard and deadline guard are such
        triggers (row-level security is unaffected: the reviewer's reading, **not shown**). The design
        therefore sets no role-level setting; the timeouts of 3.1 are connection options. That a
        non-superuser may read `pg_db_role_setting` or call `has_parameter_privilege` for another role is
        **not shown**; a tool that cannot read it refuses. **The limit that stays:** the `SHOW` runs at each
        gated start and not during a run, so a value that the superuser writes with `ALTER SYSTEM` and
        reloads is seen at the next gated start, and whether a reload changes a session that is already
        running is the reviewer's reading, **not shown**. With both privileges false for every LOGIN role and
        for `public`, only the superuser can do it among the roles that can connect, which is the
        trusted-operator boundary (rule 7). Grants on the authority objects are not re-read at a gated start:
        the stated limit of 5.4.
   b. *Escalation paths* (`pg_has_role(role, X, 'MEMBER' | 'USAGE' | 'SET')`, `functions-info`; the manual
      defines `MEMBER` as "direct or indirect membership", so a path through an intermediate NOLOGIN role is
      covered). For every LOGIN role `U` other than the one LOGIN superuser and every role `X` other than `U`
      itself (a role counts as a member of itself; my reading, not shown), **the preflight refuses if `U` has
      `MEMBER`, `USAGE` or `SET` in `X`, whatever `X` is** (technical TR3R-M1). There is no allowed-pairs list
      and no exemption row to write or protect; the four real roles are created with no membership at all
      (R6's plan). The one LOGIN superuser is excluded because a superuser is trivially a member of every
      role (my reading; not shown), and it is the trusted-operator boundary anyway. Why `X` is not limited to
      a list of dangerous roles: the manual says `SUPERUSER`, `CREATEDB` and `CREATEROLE` "are never inherited
      as ordinary privileges on database objects are. You must actually SET ROLE to a specific role having one
      of these attributes" (`role-membership`), so a check of `U`'s own attributes passes a LOGIN role with
      `SET` on a NOLOGIN role that has one; a `CREATEROLE` user with `ADMIN OPTION` can grant the role back to
      themselves and change its password (`role-attributes`); and the predefined roles act beyond grants:
      `pg_write_all_data` acts "as if having INSERT, UPDATE, and DELETE rights" without `BYPASSRLS`, and in
      F2's pattern the authority tables rely on `REVOKE ALL FROM PUBLIC` (`guarded_workspace_v1.sql:441`),
      with immutability triggers on six of them and not the head (`:436-438`), so a member could publish,
      renew or admit without the publisher (a design claim until built); `pg_read_all_data` reads archived
      bytes after a withdrawal or a lapse; `pg_execute_server_program`, `pg_read_server_files` and
      `pg_write_server_files` "could be used to gain superuser-level access"; `pg_signal_backend` would let
      the publisher end backends, which 3.1 says it cannot. A `pg_*` role is one such `X`, so a role that a
      later server version adds is covered without an enumeration, and `pg_database_owner` (the database
      owner is its implicit member) flags a LOGIN role that owns the real database. Each has its own test case
      (rule 7).
   c. *Databases* (`pg_database`, shared by the whole cluster, `catalog-pg-database`): every database with
      `datallowconn`, and for each of the four real roles `has_database_privilege(role, db, 'CONNECT')` on
      every database other than the real one. **Decision** (technical TR3-L3): the preflight **refuses on
      any `CONNECT` that a real role holds outside the real database**, PUBLIC's default included (it shows
      up here; `ddl-priv` lists `CONNECT` among PUBLIC's defaults on databases). It can pass only after the
      installer has revoked PUBLIC's `CONNECT` on `postgres`, `template1` and every other connectable
      database of its cluster (rule 3), so section 1 item 2's claim that the real roles get no `CONNECT`
      elsewhere is checked, not assumed. `template0` is not connectable (`datallowconn` false,
      `catalog-pg-database`). That a non-superuser may read `pg_database`, `pg_auth_members` and call these
      functions for another role is **not shown**: the manual says only that the catalogs are cluster-wide
      and that `pg_roles` is public. If a runtime tool cannot read something it needs, it refuses ("not
      inspected" is a failure), and the installer, which is a superuser, always can.
   d. *The probe.* For every LOGIN role of (a) and one random never-created role name, and for every
      `datallowconn` database of (c), one connection attempt over the Unix socket, serially, with a short
      `connect_timeout`, in a child process; and a `replication=1` attempt for every role with `rolsuper` or
      `rolreplication` (`libpq-connect`, `replication`; `pg_hba.conf` matches the keyword `replication` for
      physical replication connections, `auth-pg-hba-conf`; the keyword `all` does not match it, so a
      cluster with no `replication` line denies the attempt: "If no record matches, access is denied").
      Three passes, A and B with connection attempts and S without:
      - **Pass A, no credentials at all.** A scrubbed environment (a minimal one, `HOME` an empty temporary
        directory, `passfile=/dev/null`, no `service`). A success means a path is open to anyone who can
        reach the socket. This is the check on `trust`, `peer` and `ident` for any role and on a `local all
        all trust` line that the owner kept "so that the existing tests still work", whatever database the
        line names (TR2-M3, scenario 1);
      - **Pass S, the static scan of stored credentials** (technical TR3-M1). It makes no connection and runs
        in the tool's own process, with the caller's real environment and `HOME`. It reads **both** the files
        that environment names and **the default locations** (`~/.pgpass`, `~/.pg_service.conf`, and
        `pg_service.conf` in the installation's etc directory), because an agent shell without those variables
        uses the defaults (technical TR3R-L1: a terminal that exports `PGPASSFILE=~/.pgpass_dev` would
        otherwise hide `~/.pgpass`). libpq uses a stored credential only when a condition holds (a passfile
        with group or world access "will be ignored"; a service file is used only when a service name "is
        specified in a libpq connection string" or in `PGSERVICE`; `libpq-pgpass`, `libpq-pgservice`), but an
        agent session as the same OS user can read the file whatever libpq does. So Pass S reads the files
        and does not wait for libpq to use them. It refuses when:
        1. `PGPASSWORD` is set in the environment, to anything: empty, wrong or right (the manual: it "behaves
           the same as the password connection parameter", `libpq-envars`);
        2. a passfile (either location) has **any line** whose host field is the real cluster's socket
           directory, `localhost` or `*`, and whose port field is the real cluster's port or `*`. The line
           format is `hostname:port:database:username:password`; `*` matches anything; `:` and
           `\` are escaped with `\`; the host field is matched to the `host` parameter, which for a Unix socket
           is the socket directory, and `localhost` is also searched when the host matches libpq's default
           socket directory (`libpq-pgpass`). The database and username fields are not used to excuse a line.
           **Whatever the file's mode**: a `0644` file made by `echo >>` under `umask 022`, which libpq ignores,
           refuses all the same. **A line whose username field names a LOGIN role of the real cluster refuses
           whatever its host and port** (for example a leftover `127.0.0.1:5433:finweb_real:finweb_real_publisher:…`).
           The role names are those of 5.3 (a) plus the four real role names, which the installer's Phase 0
           knows before they exist; a `*` username names no role and is judged by host and port as before;
        3. a service file has a section with a `password` parameter whose `host` is absent (it then falls back
           to defaults) or is the real cluster's socket directory or `localhost`, and whose `port` is absent or
           the real cluster's, **or whose `user` names a LOGIN role of the real cluster, whatever its `host`
           and `port`**. The files are the one `PGSERVICEFILE` names and `~/.pg_service.conf`, and
           `pg_service.conf` in the directory `PGSYSCONFDIR` names and in the installation's etc directory
           (`libpq-pgservice`). Every section is read, **whether or not a service is named anywhere**. A
           section's `passfile` parameter sends the scan to that file too (2.);
        4. a file named above exists and cannot be read: "not inspected" is a failure.
        For each refusal the scan prints the store, the file, the line number or section name and the fields
        before the password, **and never a password**. A passing scan shows that none of those stores holds an
        entry for this cluster now; its limits are in 5.4 and rule 2.
      - **Pass B, the caller's own default sources, by connection attempt.** The caller's environment and
        `HOME`, so that libpq reads `PGPASSWORD`, `PGPASSFILE` / `~/.pgpass` and `PGSERVICE` /
        `~/.pg_service.conf` as the manual lists them. A success means a credential for a real-cluster role
        sits where libpq uses it and an agent session as the same OS user can read it (TR2-M2). **Pass B is a
        backstop for Pass S, not the check on stored credentials** (TR3-M1): an attempt cannot succeed
        through a file libpq skips, so an all-`CHALLENGED` Pass B proves nothing about such a file.
   e. *Superuser-only checks, the installer's Phase 0 and Phase 2:*
      - `pg_hba_file_rules`, which "can be read only by superusers" by default (`view-pg-hba-file-rules`):
        every row. Only `local` rows with `scram-sha-256` or `reject` are allowed; `trust`, `peer`, `ident`,
        any `host*` row and any unlisted method refuses. The manual says the first matching record decides
        and there is no fall-through, so the rows are evaluated in order for each (role, database) pair; a
        later `trust` row shadowed by an earlier `scram` row still refuses, because the rule is about the
        file. The view "reports on the current contents of the file, not on what was last loaded by the
        server": the probe of (d) is what shows the loaded rules, and a difference between the two refuses
        with "edited but not reloaded". A `REJECTED` outcome of (f) passes in the installer only if the rows,
        evaluated in order for that (role, database, replication) tuple, predict a `reject` or no match at all
        ("If no record matches, access is denied", `auth-pg-hba-conf`); a `REJECTED` the rows do not predict
        is a file/loaded disagreement and refuses;
      - `pg_authid.rolpassword` (superuser only): every LOGIN role has a verifier that begins `SCRAM-SHA-256$`
        (`catalog-pg-authid`); `md5…` or null refuses in Phase 2, after the owner has set the passwords (a
        null verifier cannot authenticate, `auth-password`, but rule 1 says a password for every role);
      - `SHOW`: `listen_addresses` is empty; `session_replication_role` is `origin`; `password_encryption` is `scram-sha-256` before the owner sets
        passwords; `log_statement`, `log_min_duration_statement` and `log_min_error_statement` (the table
        under rule 2); `data_directory`, `hba_file`, `ident_file` and `unix_socket_directories` are printed,
        and refuse under the repository root or the system temporary directory;
      - **the catalog audit**, in Phase 2 and `--check` only (technical TR4-M2; conformance R4C-L1): the
        function that R3 builds for T03, called against the REAL database as `REAL`. It is product code under
        `src/persistence/` (prospective `real_catalog_audit.py`) that T03 and the installer both import, so
        that "the same audit" is one function (technical TR4R observation). It reads the function, ownership
        and privilege catalogs, which no other check of this rule reads, and refuses if (i) a function of the
        TEST-only part (section 1 item 1) exists; (ii) a runtime role (the executor, the loader or the
        publisher) owns an object; (iii) **the privileges of any runtime role, or of `public`, differ from that
        role's own list** (technical TR4R-M2); or (iv) another assertion of T03 fails (the authority tables and
        the install-kind row, 2.1). **How (iii) compares.** For each of the executor, the loader, the publisher
        and `public`, and for every table and every function of the gateway schema, not only those a list
        names, it asks whether the role holds the privilege and refuses on any difference from the list:
        `has_table_privilege` for `DELETE`, `TRUNCATE`, `TRIGGER` and `MAINTAIN`, `has_any_column_privilege` for
        `SELECT`, `INSERT`, `UPDATE` and `REFERENCES` (it "succeeds either if the privilege is held for the whole
        table, or if there is a column-level grant", so a column-level grant is seen) and `has_function_privilege`
        for `EXECUTE` (`functions-info`). **No list names columns** (technical TR5R-L1): the one option that
        did, option (c) of the former item 12, was not taken (PD-0070 decision 1), so every list is compared at
        table level, which is what `has_any_column_privilege` answers. Where a list gives a role no privilege on
        a table, a column-level grant is a difference and is seen. A list that named columns would need
        `has_column_privilege` per column (`functions-info`) and would reopen this comparison.
        **`MAINTAIN`** (technical TR5-L1) is the eighth table privilege the
        manual lists for `has_table_privilege` (`functions-info`), so with it all eight are compared. It matters
        because "if the user has MAINTAIN, UPDATE, DELETE, or TRUNCATE privileges on the table, any lockmode is
        permitted" (`sql-lock`), and `ACCESS EXCLUSIVE` conflicts with every mode, the `ROW EXCLUSIVE` of an
        `INSERT` included (`explicit-locking`): a role that held it on the drain-mark table could hold that
        lock and stop the owner's withdrawal from committing its mark (3.1). The lists are those of the shared
        installer code: the executor's (4.2: no privilege on any `md_*` table, on `web_saved_sandbox`,
        `web_portfolio_revision` or `web_csv_*`; `EXECUTE` on the `md_*` read functions of 2.6 item 6), the loader's (3.3, fixed in R2: `INSERT` on the thirteen
        `md_*` tables, `SELECT` on `md_file` and `md_release`, `EXECUTE` on the candidate registry's put and get
        functions), the publisher's (2.5, R1), and for `public` none. **"None" for `public` is true only
        because the installer makes it so** (technical TR5-L2). The HEAD migrations create twelve functions
        (`ledger_event_reject_mutation`, `ledger_event_before_insert`, `ledger_event_check_transfer_pairing`,
        `account_guard_identity`, `ledger_full_xid`, `md_reject_mutation`, `md_release_stamp`,
        `md_require_open_release`, `benchmark_selection_reject_mutation`, `benchmark_selection_before_insert`,
        `web_revision_before_insert` and `web_revision_reject_mutation`, in migrations `0003`, `0004`, `0006`,
        `0011`, `0015` and `0018`), `git grep` of the migrations finds no `GRANT` or `REVOKE`, and the manual lists
        `EXECUTE` among PUBLIC's defaults for functions (`ddl-priv`), so PUBLIC, and through it every role,
        holds `EXECUTE` on them. The shared installer code therefore revokes PUBLIC's `EXECUTE` on every routine
        of the schema (the `ALL ROUTINES IN SCHEMA` form of `REVOKE`, `sql-revoke`; `ALL FUNCTIONS` leaves
        procedures out and `ALL ROUTINES` includes them, `sql-grant`; the HEAD migrations create no procedure,
        `git grep` finds no `CREATE PROCEDURE`), after the last file that creates one and before the grants by
        name. F2 does the same for its own `gw_%` functions, by a loop (`guarded_workspace_v1.sql:443-447`);
        this is one statement of the installer code, with the lists (R3), and no gateway object. **Two
        consequences** (technical TR5R observations). Before R3 builds that statement, PUBLIC's default
        `EXECUTE` is on the twelve functions, so R2's catalog assertion on the loader cannot say "no other
        function" and does not (7.1, R2); R3's audit is the first to. And a migration applied later to an
        installed database (section 1 item 4) creates its routines with PUBLIC's default `EXECUTE`: the
        statement has to be re-run after it, and until then `--check`'s audit refuses (fail-closed); R6's plan
        states that step. That a trigger fires for a role with no `EXECUTE` on its function: the
        manual says `EXECUTE` on the trigger function is needed to create the trigger (`sql-createtrigger`) and
        I read nothing there about firing. HEAD's `test_c13_partial_and_unsealed_commit`
        (`test_postgres_guarded_workspace.py:381`) has the executor role's connection meet F2's fence and, at
        COMMIT, its bundle guard, whose call of `gw_validate` raises `F2_UNSEALED` (`:356`); both trigger
        functions carry that revoke and no grant to the executor (`guarded_workspace_v1.sql:443-449`). **That
        covers `SECURITY DEFINER` trigger functions only** (technical TR5R observation): `gw_write_fence` and
        `gw_bundle_guard` are definer functions (`:197-198`, `:384-385`), and the migration trigger functions are
        not (`git grep` of the migrations finds `SECURITY DEFINER` only in a comment, which says the trigger
        draws the sequence "as the invoking role", `0003_ledger_event_guards.sql:8-9`). R3's T03 shows it for the real
        gateway's own trigger functions. **The migration triggers (technical TR6-L2): eleven trigger
        functions, two shown by R3, up to three more first fired in R5, the rest not shown.** The loader's
        inserts fire two, `md_release_stamp` (`0011:69-71`) and `md_require_open_release` (`0011:73-90`,
        `0016:74-77`), so **R3's re-run of R2's loader write with the revoke in place is the evidence for
        those two and for nothing else**. The other nine fire on `ledger_event` (`0003:20`, `:24`, `:136`,
        `:203`), on an UPDATE of `account` (`0004:39`), on `benchmark_selection` (`0015:113`, `:117`, `:178`),
        on `web_portfolio_revision` and the `web_csv_*` tables (`0018:37`, `:44`, `:46`; `0019:29-35`) and on an
        UPDATE, DELETE or TRUNCATE of the `md_*` tables (`0011:92-134`, `0016:79-85`); no loader insert reaches
        any of them. The executor's accepted writes fire the insert triggers of `ledger_event`
        (`ledger_event_before_insert` and the constraint trigger `ledger_event_check_transfer_pairing`) and, if a
        create writes a `benchmark_selection` row, `benchmark_selection_before_insert` (2.6 item 1 names the
        tables the executor writes; I did not check whether the `SYNTHETIC_TEST` create writes that row). Those
        are **first fired without PUBLIC's `EXECUTE` by the executor's accepted writes on a `TEST` install: R5's
        `SYNTHETIC_TEST` create** (the shared installer code applies the revoke to `TEST` installs, 7.1 R3), and
        R5's exit states which of them it fired. The mutation-refusal triggers (`ledger_event_reject_mutation`,
        `md_reject_mutation`, `benchmark_selection_reject_mutation`, `web_revision_reject_mutation`) and
        `account_guard_identity` fire on a statement that updates, deletes or truncates; `git grep -i` of `src/`
        at HEAD finds no `UPDATE account`, `UPDATE benchmark_selection` or `UPDATE ledger_event`, so no accepted
        path I know of reaches them, and no run in R3 or R5 shows them firing for a role without `EXECUTE`. I
        claim nothing about them under the revoke. `web_revision_before_insert` fires on a table the executor's
        list excludes (4.2), so no runtime role's accepted path fires it.
        Examples the audit catches: the executor or the loader holding `EXECUTE` on a publisher
        function or on a function of the TEST-only part; the loader holding `INSERT` or `UPDATE` on an
        authority table, which would be a publish without the publisher (PD-0066 decision 7); the executor
        holding `SELECT` on any `md_*` table. The manual says a user named `public` is checked as the PUBLIC
        pseudo-role (`functions-info`) and that a role has "the sum of privileges granted directly to it,
        privileges granted to any role it is presently a member of, and privileges granted to PUBLIC"
        (`sql-grant`). That the `has_*_privilege` answer for a named role reports that sum is my reading of
        "does user have privilege" (`functions-info`), **not shown by a page that says it**, which is why
        `public` is asked as well. **Not compared:** privileges on
        sequences and schemas. Without the audit Phase 2 would pass a defect in the REAL branch of the shared
        installer code. It runs at install and at each `--check`, not at a gated start (5.4). Only the
        installer, a superuser, runs it. Not run here.
   f. *Outcome classes.* Each attempt ends in one of: `CONNECTED`; `CHALLENGED`, a **positively recognised**
      authentication refusal (a password was demanded or the password failed); `REJECTED`, a **positively
      recognised** refusal by the access rules and not by authentication (a `reject` record matched, or no
      record matched); or `OTHER`, which is every other result: a server error after authentication (the
      technical review notes that an attempt ending in `3D000`, "database does not exist", has already
      authenticated; **not shown** by the manual or a test, so the classifier does not depend on it), a
      timeout, a missing socket, an unrecognised message. **`CHALLENGED` and `REJECTED` pass. `CONNECTED` and
      `OTHER` refuse** (technical TR3-L1: rule 1 allows `reject` lines, and a cluster with no `replication`
      line denies the replication attempt, so a closed door must not be read as a failure; before this
      change a hardened file such as `local all all reject` made the preflight refuse a configuration
      that rule 1 allows). A runtime tool cannot read the rows, so for it `REJECTED` means only that the
      door was closed at that attempt; whether the file predicts it is the installer's check (5.3 (e)). The
      server's message texts for these classes are not quoted in the manual pages I read, so which
      messages count as `CHALLENGED` and `REJECTED` is calibrated at R6 only if the owner grants the sandbox
      exception, else first at R8 step 1 (rule 7), and is changed only by a reviewed change, never by a switch.
   g. *Output.* The preflight prints every attempt and its class, the roles and databases it found, and what
      it did not inspect. **It also prints, for each of the four real roles, whether it can log in**
      (`rolcanlogin`, a column of `pg_roles` that (a) already reads for every role, from any vantage: **E29**,
      my proposal under PD-0070 decision 1, for review). It is a print and not a check. No value of any role's
      login state refuses a command: the owner opens and closes the loader's load windows (3.3), and no tool
      can know whether a window is meant. Nothing is stored, and a printed value says nothing about a moment
      after the print. It is there because the checks of (a), (b) and (d) and the verifier check of (e) are
      keyed to LOGIN roles and so cover the loader as one only while it can log in: the line tells a reader
      whether a run covered it. The owner may paste it into the record of the step (as 5.1 allows for `withdraw`'s
      result). If a reviewer judges it a mechanism, deleting it changes no other claim: the attempt lines
      already name each LOGIN role.

   **5.4 What it can and cannot see.** From a runtime tool's vantage (a non-superuser): the role catalogue,
   membership and `CONNECT` through the functions of (b) and (c), and connection outcomes. It cannot read
   `pg_hba_file_rules` or `pg_authid`, so it cannot tell whether a role has a password or what the file says;
   `pg_roles.rolpassword` "always reads as ********" (`view-pg-roles`). From the installer's vantage
   (a superuser): additionally the hba rows, the verifiers and the settings. Neither can see the items under
   "cannot be enforced" in rule 2. A passing preflight is a tripwire from the vantage of the process that ran
   it, at that moment.

   **Grants are not re-read** (technical TR3R-L2; a stated limit). Neither vantage re-reads the grants of the
   four real roles at a gated start: the preflight holds no matrix of expected grants. They are audited by
   the installer's catalog audit (5.3 (e)) in Phase 2, first on a REAL catalog at R8 step 1, and again in each
   `--check` the owner runs, so a later `GRANT` by the superuser, for example `EXECUTE` on the publish
   function to the executor, is not seen until the owner runs `--check`. The settings and the two
   parameter privileges of 5.3 (a) are read at every start because they are cheap and are what would
   switch the gateway's triggers off. Not claimed: that the grants are unchanged since the last `--check`.

   **The runtime vantage and TCP** (technical TR3-L4). The runtime probe tries the Unix socket only. A
   loopback TCP attempt from a sandboxed process fails for a reason that says nothing about the server
   (CLAUDE.md: loopback TCP is not available in the sandbox), so none is made. Instead every runtime tool
   reads `SHOW listen_addresses` and `SHOW session_replication_role` and **refuses unless the first is empty
   and the second is `origin`** (the second is TR3R-L2, 5.3 (a)). The manual says `listen_addresses` "can
   only be set at server start", so the running server's value is the value it was started with, and that
   with an empty list "only Unix-domain sockets can be used to connect to it" (`runtime-config-connection`).
   That closes the case where, after R8, `listen_addresses` is set to `localhost` and a `host ... trust` line
   is added for a GUI client and the server restarted: the gated commands then refuse, whatever the file
   says. Whether a non-superuser may read `SHOW listen_addresses` or `SHOW session_replication_role` is **not
   shown** (the manual pages do not say, and I did not run them); a tool that cannot read one refuses. What the check does not see is the hba
   rows, which only a superuser can read. `withdraw` reports the same check and is not stopped by it (5.1).
6. **The existing test tooling and the environment-driven tests must not point at the real cluster**
   (technical TR2-L2). They are outside the preflight (scope above), so they get tripwires of their own,
   which are not fences:
   - `Provisioner.preflight` (`guarded_pg_provision.py:67`) gains a refusal: it stops if the target cluster
     holds a database whose name starts with the reserved prefix (prospective: `finweb_real`;
     `pg_database` is cluster-wide, `catalog-pg-database`). `guarded_pg_runner.py` calls it (`:163`) and
     `dev_env.py up` calls it (`:256`);
   - the environment-driven modules gate on `connection.missing_env_vars` (`connection.py:55-69`), which
     builds no connection. It gains a name-level refusal: `FINWEB_PG_DATABASE` starting with the reserved
     prefix is reported as not usable. One change covers the nine modules and
     `test_postgres_connectivity_preflight.py` through its own variables if it adopts the same helper;
   - the residual, said plainly: an environment pointed at the real cluster with a database named
     otherwise (for example `postgres`) passes the name check. What stops those tests there is the
     credential rule: they run `CREATE SCHEMA`, which needs a role with `CREATE` on the database, and the
     real cluster has none but the owner's superuser, whose password agents do not hold (rule 2, and
     Passes S and B).
7. **Evidence and limits.**
   - **R6 tests** (the R6 row of 7.1): the decision table of 5.2 and the by-command rule of 5.1 for the
     commands that exist at R6; every case of the list below on fake facts (decision logic, including Pass S
     over files under a temporary `HOME`); the static no-bypass test over the installer and the publisher
     tool (R7 adds the launcher and the probe, technical TR3R-L3), which also fails if the real installer names
     the TEST-only part's file or takes a file list or a grant list from anything but the functions that R3
     tests (section 1 item 1); and the probe and its classifier against
     **disposable roles on a development cluster**, which can show the **refusal side only** (technical
     TR3-L2). Those clusters trust their roles over the socket by design (fact 18; `dev_env.py:13`: "the
     cluster must trust them over its private Unix socket"). The manual says `trust` makes PostgreSQL assume
     that anyone who can connect "is authorized to access the database with whatever database user name they
     specify" (`auth-trust`), so a password-protected role on such a cluster connects without a challenge (my
     inference; I did not read the cluster's `pg_hba.conf`). The probe sees `CONNECTED` there and must
     refuse. **No attempt on a development cluster can be `CHALLENGED` or `REJECTED`, so those two classes
     cannot be calibrated there.**
   - **The accepting side is first exercised at R8 step 1, on every path** (technical TR3R-M2): the
     installer's Phase 0 and Phase 2 (which includes the catalog audit, so the first and only read of a REAL
     catalog is there too) passing on a clean REAL cluster and, after it, the runtime gate passing
     at each tool's first gated start. Only the real installer writes `REAL` (5.1), and it refuses a data
     directory or socket directory under the repository root or the system temporary directory (5.3 (e));
     the sandbox lets an agent write only the project and `$TMPDIR` (`/tmp/claude-503` here), so no cluster
     an agent builds can pass its Phase 0. I add no test-only placement relaxation and no crafted `REAL`
     install: either is the bypass 5.2 rules out.
   - **A wrong refusal is fixed by a reviewed change, never by a switch; when it shows decides what exists**
     (technical TR4-L1; conformance R4C-L2). A refusal in **Phase 0** comes before the installer has created
     anything, because Phase 0 writes nothing; it probes only the roles and databases that exist before the
     installer. The checks that meet the four real roles and the gateway first run in **Phase 2**: membership
     (5.3 (b)), `CONNECT` after the Phase 1 revoke (5.3 (c)), the probe's attempts as those roles, the
     verifiers and the `REJECTED` prediction (5.3 (e)), and the catalog audit. A wrong refusal in Phase 2, or
     at a tool's first gated start, therefore comes **after** the real database, the four roles, the gateway
     and the owner's passwords exist. They hold no market data, snapshot or record then (qualification is
     step 2). **That nothing is used until the refusal is resolved holds because the owner follows R8's step
     order** (technical TR4R observation; conformance R4R observation): the runtime gate does not read
     Phase 2's result and grants are not re-read at a gated start (5.4), so it is an owner procedure and not
     something a tool enforces. The owner waits for a reviewed change to the
     preflight and re-runs `--check`. If the change would touch Phase 1, the owner chooses between dropping
     the real database and roles, which hold no content, and re-running the installer, or approving SQL in the
     existing database (PD-0066 decision 6). The PM list (8.1) tells the owner before R6's plan is approved.
   - **A Phase 1 failure at R8 step 1** (technical TR4R-L3). Phase 1 is a sequence of statements and not one
     transaction (`CREATE DATABASE` cannot be executed inside a transaction block, `sql-createdatabase`), and
     the four roles are cluster-level objects, so a failure partway leaves what had run: the real database,
     some or all of the four roles, part of the gateway and the revokes of PUBLIC's `CONNECT` done so far. It
     holds no market data, snapshot or record. Every pre-R8 install, one built on a crafted `REAL`-kind row
     included, holds the TEST-only part, and R3's tests read the lists and not an install of REAL's file list
     (section 1 item 1). So a defect that only the REAL composition shows (for example a core function that
     names a function of the TEST-only part, and fails where it is created or first called; my reading, not
     shown) first shows here. The tools refuse a database with no single kind row (5.2, last row), and that
     does not make a partial install safe to use (technical TR5-L4): 2.1 says only that the installer writes
     the kind row once, and nothing puts that write last in Phase 1, so a failed Phase 1 may already hold a
     single `REAL` kind row. `publish` would then take the database for REAL and run a gate that reads no
     gateway catalog and re-reads no grants (5.4). That a partial install is not used is the owner's
     procedure, as for a Phase 2 refusal above, and no tool enforces it. **The owner's options** are those of a Phase 2
     refusal: wait for a reviewed change to the installer, then drop the real database and the roles, which
     hold no content, and re-run it; or approve SQL in the existing database (PD-0066 decision 6). That
     Phase 1 can be re-run over a partial install is not claimed. R6's exit and the PM list (8.1) tell the
     owner before the plan is approved. The reviewer's optional test, R3 applying REAL's file list to a
     disposable database of kind `TEST`, is **not taken**: it adds a provisioner path, and the narrower
     statement stands.
   - **A throwaway cluster, only if the owner grants the sandbox exception the CP7 cluster needed**
     (STATUS.md, "its socket needs a sandbox exception"), **calibrates the classifier of `CHALLENGED` and
     `REJECTED` against real server refusals, and nothing else.** The test runs `initdb
     --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwprompt` under `$TMPDIR`, typing a password it
     generated into the prompt through a **pseudo-terminal** (Python's `pty` module; not run; that `initdb`
     can be driven this way in the sandbox is **not shown**), deletes the `host` lines, and starts the
     cluster with `listen_addresses` empty. Without `--auth-host` the `host` lines are `trust` ("the default
     for ease of installation") and without a password the superuser cannot log in over `scram-sha-256`
     ("you won't be able to use password authentication until you have a password set up"; both
     `app-initdb`). The test makes its own connection attempts, edits `pg_hba.conf` and reloads for the
     `reject` and no-record cases, and passes the real refusals to the classifier. It runs no real tool, so
     none gains a password, file or credential option (the static test of 5.2 fails if one does). **That
     cluster holds no gateway, no snapshot, no `REAL`-scope content and no record marked `synthetic =
     false`: it is not the rehearsal install that PD-0068 answer 2 declined, and it is discarded after the
     test.** No `REAL` kind row is crafted, so it does not exercise the runtime gate over a `REAL` target.
     **If the exception is not granted**, `CHALLENGED` and `REJECTED` are calibrated first at R8 step 1 too;
     a mis-calibration fails closed (an unrecognised message is `OTHER`, which refuses) and blocks R8 step 1.
     The exception buys the classifier's calibration and no way to find a Phase 2 refusal before the real
     install exists (the bullet above).
   - **Cases for the decision logic** (technical TR2-M3: "R6's tests of the decision logic cover each
     case"; extended in the round-3 fix round). Each is a fact set in, a decision out, and the output is
     checked never to contain a password string.
     - *Connection paths:* a trust line for the superuser; `local all all trust` on another database (shared
       cluster); a `peer` or `ident` line for any role; a trust line for the publisher, for the executor; an
       error after authentication; a timeout and a missing socket (both `OTHER`); every attempt `CHALLENGED`
       (passes); **a `reject` line for a role and database, and no `replication` line (both `REJECTED`, pass;
       the installer additionally checks that the rows predict them, and refuses a `REJECTED` they do not
       predict); a role that is a member of itself (not a finding)**.
     - *Escalation* (5.3 (a), (b); technical TR3R-M1): a trusted `CREATEROLE` role with `ADMIN` on the
       publisher; **a LOGIN role with `SET` (and no `INHERIT`) in a NOLOGIN role that has `SUPERUSER`, one that
       has `CREATEROLE` and one that has `BYPASSRLS` (each its own case, each refuses); a LOGIN role with
       membership only (no `INHERIT`, no `SET`) in any role (refuses); a LOGIN role that is a member of the
       one LOGIN superuser, and the executor granted the superuser (each refuses); a LOGIN role that is a
       member of each of `pg_write_all_data`, `pg_read_all_data`, `pg_execute_server_program`,
       `pg_read_server_files`, `pg_write_server_files` and `pg_signal_backend` (each its own case), once
       directly and once through an intermediate NOLOGIN role; a `pg_*` role added to the fake catalog under
       an unlisted name (refuses with no enumeration); a LOGIN role that owns the real database
       (`pg_database_owner`; refuses); a second LOGIN superuser, and a LOGIN role with `CREATEROLE` (each
       refuses). Controls, which pass: the one LOGIN superuser alone (excluded from the membership check); a NOLOGIN
       role with a power attribute and no member; a LOGIN role with no membership. No exemption exists to
       add to: a catalog test asserts that the install-kind row has no column that names roles, so a role
       granted `pg_write_all_data` cannot change what the next start accepts**.
     - *Settings* (5.3 (a); technical TR3R-L2): **a non-empty `rolconfig` on the executor, the loader and the
       publisher (each refuses); a `pg_db_role_setting` row for the real database, and one for a real role
       (each refuses); `GRANT SET ON PARAMETER session_replication_role` to a real LOGIN role (refuses), and
       the same with `ALTER SYSTEM` (refuses; technical TR4-L2), and each of the two to a LOGIN role that is
       not one of the four, and to `public` (each refuses; technical TR4R-L1); a `pg_db_role_setting` row with
       `setrole` and `setdatabase` both 0 (passes, the narrowed claim of 5.3 (a)); a session whose `SHOW
       session_replication_role` is `replica`, for example from a cluster default
       (refuses); none of these (passes); a tool that cannot read `pg_db_role_setting` or that setting
       (refuses)**.
     - *Catalog audit* (5.3 (e); technical TR4-M2), on fake catalog facts in R6 (the audit's own behaviour on
       real TEST catalogs is R3's, section 1 item 1): **a function of the TEST-only part present (refuses);
       the executor owning a table (refuses); `EXECUTE` on a publisher function granted to the executor, and
       the same for the loader (each refuses); `EXECUTE` on a function of the TEST-only part granted to the
       executor (refuses); a privilege on `web_saved_sandbox` for the executor (refuses); the lists as the
       installer applies them (passes); a catalog the audit cannot read (refuses, "not inspected")**. **The
       loader and `public` cases of the comparison in (iii)** (technical TR4R-M2, TR5-L1, TR5-L2): **the loader
       holding `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` or `MAINTAIN` on the history, head or drain-mark table
       (each refuses); the executor holding `MAINTAIN` on the drain-mark table (refuses); the loader
       holding `SELECT` on `md_quote`, and on any `md_*` table other than the two of its list (each refuses); a
       column-level `UPDATE` grant on an authority table to the loader and to the executor (each refuses);
       the executor holding any privilege on a `md_*` table, `SELECT` included (refuses); `EXECUTE` on an
       `md_*` read function granted to the loader, and to `public` (each refuses); the loader holding `EXECUTE`
       on the registry's load function (the executor's), and missing `EXECUTE` on its put or get function (each
       refuses); any privilege on a gateway table or function held by `public` (refuses), `EXECUTE` on a
       migration's trigger function such as `md_require_open_release` included (the HEAD migrations leave that
       default, so the installer's revoke of 5.3 (e) is what lets the audit pass); the publisher holding a
       direct write privilege on an
       authority table that its list (R1) does not give it, and the executor missing `EXECUTE` on an `md_*`
       read function (each a difference from the role's list: refuses); the loader's list as the installer
       applies it, registry functions included (passes)**.
     - *Databases* (5.3 (c)): **`CONNECT` held by the executor, the publisher or the loader on `postgres` or
       `template1` (refuses), and the same with the installer's revoke done (passes)**.
     - *Stored credentials* (Pass S): **`PGPASSWORD` set to a right value, a wrong value and the empty string
       (each refuses); a `0644` passfile with an entry for the cluster's socket directory and port (refuses,
       though libpq would ignore the file); the same at `0600` (refuses); a line with host `*` and port `*`
       (refuses); an entry for another host or port (passes); a service file with a `password` section that no
       service names (refuses); a section whose `passfile` parameter leads to such an entry (refuses); a
       service file whose sections hold no `password` (passes); a file that exists and cannot be read
       (refuses, "not inspected")**; **an entry in `~/.pgpass` while `PGPASSFILE` names another file
       (refuses); a line with host `127.0.0.1` and username `finweb_real_publisher`, whatever its port
       (refuses); a service-file section with a `password` and a `user` naming a real role, with a host
       elsewhere (refuses); a `*` username with an unrelated host (passes)**; Pass B succeeding through
       `.pgpass`, through `PGPASSWORD` and through a service entry.
     - *Accounts and file:* a verifier that is `md5`, or null, in Phase 2; an `hba` row that is `host`, `md5`
       or unlisted; a file/loaded disagreement; `log_statement` not `none`; `data_directory` under the
       repository root; kind and name disagreeing; no kind row.
     - *TCP:* **`listen_addresses` not empty (refuses, at the installer and at a runtime tool); a runtime
       tool that cannot read it (refuses)**.
     - *Login state* (5.3 (g); E29): **the loader `NOLOGIN` and the loader `LOGIN`, each with the other facts
       clean: the printed line shows `false` and `true` respectively, and the decision is the same (passes) in
       both, and the line of each of the four real roles carries that role's own value**. A tool that refuses
       on a login state fails the test.
     - *By command* (5.1): **the same failing facts (each of the above, a probe that times out, a missing
       socket) make `publish` and `renew` refuse and write nothing, and make `withdraw` proceed, print the
       result and exit with the withdrawal's own status; re-running a pending withdrawal proceeds
       likewise** (R6). That the launcher and the admission probe refuse to start on the same facts is R7's
       test (technical TR3R-L3).
   - **The trusted-operator boundary** remains: the server clock, the OS, the data directory (rule 3) and the
     owner's own sessions. An agent that obtains a password from a place the owner left it is not stopped,
     and no check here can know that.
   - **Not run.** I connected to no cluster while writing this. That `scram-sha-256`, `peer`, `trust`,
     `pg_roles`, `pg_hba_file_rules`, `has_database_privilege`, `has_parameter_privilege`, `pg_has_role`,
     `require_auth` and `\password` behave as the installed 17.11 manual documents them is the manual's word;
     I ran none of them, and the classification of real server messages, a non-superuser's ability to read
     the catalogs of 5.3 (c), `pg_db_role_setting`, `SHOW listen_addresses` and `SHOW session_replication_role`
     (5.4), a non-superuser's call
     of `has_parameter_privilege` for another role, and whether `pg_has_role` counts a superuser or a role
     itself as a member (5.3 (b)), are not shown.

## 2. D2: one authority in the gateway, content-hash contexts, a new scoped contract, one publisher

**Decided** (PD-0066 decision 7).

### 2.1 Authority objects (R-GW)

The real gateway holds its own objects. Names are prospective.

- **Snapshot.** Immutable, one per context.
  - Content: ordered members `(payload_sha256, manifest_sha256, source_id, acquisition-record digest,
    adapter id and version)`, where `source_id` is taken from the member's manifest; release id and
    digest; projection digest; the full-registry digest **and** the used-source digest; identity,
    calendar, convention, profile and F8B confirmation-policy digests; the origin fields of 1.1; and
    **the source records the snapshot was published with**, with their terms checks.
  - Digests and metadata only, not raw payload bytes. This is the snapshot. The candidate registry (R2; 4.1)
    does hold the payload bytes, and the loader can read them back while its login is on, in a load window (3.3; technical TR5-M1).
  - The **member sources** (`alphavantage.us`, `openfigi`, `calendar.manual` for HG4) are read from the
    members' manifests, whose digests the publisher verifies, and are stored in the hashed member tuples.
    They are not declared by the publisher, and a history row cannot change them: admit takes the set
    from the stored snapshot (technical re-review L-8).
    Nothing in the snapshot says whether a source is lease-governed: the registry has no such field
    (fact 15), and a publisher-supplied list would let an omission permit `NONE`. The expiry evidence
    is rights state, not content (next item).
- **History.** One immutable row per `(context, generation)`: rights, the expiry kind, `valid_until`,
  the **expiry basis entries** (exactly one per member source: section 3.1), the issuer actor, the
  decision reference, the time, and, for a withdrawal or a renewal that ends one, the drain mark it
  names. F2's `gw_history` holds no issuer, decision reference or time, and F2 has no `valid_until` or
  basis entries (fact 1).
- **Head.** One stable, never-deleted row per context.
- **Drain mark (a withdrawal request)** **[E18]**. One insert-only row per request. Its columns are
  the context, the generation it stops, the issuer actor, the decision-reference triple (PD id, git
  commit, SHA-256 at that commit), the server time `clock_timestamp()` and the database-recorded
  `session_user`. Every column is `NOT NULL` with a format check, so **a drain mark cannot exist without
  its issuer, its reference and its time** (technical re-review M-4; conformance re-review DC-M1).
  - It is written only by the publisher's withdrawal function, which applies the same refusal rules as
    publish (2.5), in a short transaction of its own that commits **before** the withdrawal waits for
    in-flight work (section 3.1). The executor, the loader and the publisher role cannot insert, update
    or delete it directly.
  - While a mark exists for the head's current generation, every admission is refused with the code
    `RW_WITHDRAWAL_PENDING`, a code of its own, distinct from the lapse code and from the code for a
    completed withdrawal, so a refusal says why.
  - Its state is derived and never edited. **Pending**: no history row names it. **Effective**: the
    withdrawal's generation row names it. **Superseded**: a renewal names it (3.1). A status view lists
    the pending marks with their age. A timed-out withdrawal is therefore a database fact, not only a
    message to the owner.
- **Mode.** One row: `CLOSED`, `DB_SNAPSHOT_V1` or `MAINTENANCE_HOLD`.
- **Install kind.** A value `TEST` or `REAL`, written once by the installer (section 4.2). The real
  installer writes `REAL` and the TEST provisioner writes `TEST`; neither can write the other (1.2 rule 5.1).
  The row holds the kind and `W` and **no role name and no exemption** (technical TR3R-M1): no runtime role
  has a privilege on it (the catalog audit asserts that: T03 on TEST installs, the installer's Phase 2 on the
  REAL one, 1.2 rule 5.3 (e)), and the membership rule of 1.2 rule 5.3 (b) is
  what keeps a membership from giving one. The tools of 1.2 read this row to decide whether the preflight
  applies (1.2 rule 5.2).

One authority and one lock order. Consumers take **mode shared, then head shared**, in the caller's
outer transaction, and read only the locked tuple. The issuer and revoker take mode shared and head
exclusive in the same order; maintenance takes mode exclusive (E10 section 4). A withdrawal stops new
admissions at once through its drain mark, then waits for in-flight work, and is effective for that
work after its own commit. Nothing falls back to the latest file, `FileStore`, `SOURCES.json` or a
default registry at runtime. `registry.require_attested` runs on the snapshot's copy.

### 2.2 Context identity is the content hash

As in F2 (`context_id = sha256(snapshot)`, `v1.sql:3-7`):

- different content is a different context;
- **generation** counts only changes of rights or validity of one context, and withdrawals;
- the HG4 root stays bound to its original context, so reproduction keeps working;
- A-shares later mean a new snapshot, a new context and a new root;
- logical-name rebinding is out of the slice.

`valid_until` and the expiry basis entries are **not** part of the hashed content **[E2]**. They sit in
the head and history rows as part of the rights state, so a renewal is a new generation of the same
context. If they were hashed, a renewal would create a new context and strand the HG4 root.

### 2.3 Lifecycle

1. **Generate.** A qualification run (R4b) produces proposal files and loads candidates through the
   loader role (W04). Files and candidates are inputs only.
2. **Publish.** One publisher command, one transaction. It verifies the exact bytes and digests
   against the proposal, appends history generation 1, inserts the head, and sets the mode.
   Re-running with identical input returns the original. It refuses without a decision reference
   (2.5) and refuses an expiry kind that its evidence does not support (3.1). **R1 defines the
   proposal format (prospective schema `finweb.real_proposal/1`) with a pure writer and a verifier, as
   product code.** R1's tests build proposals from invented members with that writer; R4b's qualification
   run calls the same writer, and R4b's exit requires its output to pass R1's verifier (technical
   re-review L-1). Until R2 wires the origin validators, publish refuses a `REAL`-scope snapshot.
3. **Lock.** Mode shared, then head shared; no lower layer releases a lock; the lock function returns
   no bearer token.
4. **Renew or withdraw.** A new generation, in one transaction. A renewal's `valid_until` may be later
   than, equal to, or earlier than the current one; an earlier one is a date correction (3.1, E25). A
   withdrawal first commits its drain
   mark (issuer, reference, time; 2.1), then waits for in-flight work and appends the generation that
   names the mark (section 3.1). A renewal while a mark is pending is refused unless it names that mark.
5. **Edit a proposal file.** Changes nothing live. An edited export is a new candidate.

### 2.4 The new scoped contract replaces E5 for this slice

The E5 contract is permanently closed: `real_workspace_contract.py` ends `refuse_intent` with an
unconditional `REAL_CONTEXT_NOT_QUALIFIED` (`:211-224`); the routes' docstring says "Permanent
authenticated contract/refusal routes; no real workspace store" (`real_workspace_routes.py:1`); the
dev app installs them (`account_routes.py:242-243`).

Decided: a **new, scoped contract version** covers only this slice's real routes (create, read,
reproduce on the one context), **and an owner-scoped list route** (technical re-review L-6) **[E22]**.
R7 builds a real-mode list type and R8 expects "the real root listed", so the list is a route of the
R5-reviewed contract and not an addition made in R7. It returns, for the caller's own real roots only,
each root id, the stored origin fields of 1.1 (read from the stored row, never hard-coded), the context
id, the generation and the creation time, and no financial number. It is admitted under `ARCHIVE_READ`
for each root's context, so a withdrawn or lapsed context returns the refusal code and not an empty
list that reads as "no portfolio". Its wire shape is part of R5's contract tests and review, and R7's
list type conforms to it.

**Admission model of the list route** (technical TR2-L4). A plain `SELECT` on `rw_root` would return no
rows for a live root: the row policy is false without a lease (2.6 item 2), and a restrictive policy filters
a read silently (F2's `gw_selected_guard` is restrictive, `guarded_workspace_v1.sql:431`; the manual's example
of a restrictive policy shows a role that "will not see any records", `ddl-rowsecurity`; no HEAD test shows it
for this policy). And admit, a fork of F2's, mints one
lease per transaction for one root (`F2_SINGLE_SCOPE`, `:140`; `gw_admit` takes one root id, `:134-162`). So
the list is two steps:

1. A definer function `rw_list_roots(owner_id)`, built in **R1** beside the root-link table, returns
   **identifiers only** for the owner's own roots: `root_id`, `context_id` and the head's current
   `generation`. It reads the root-link table and the head, needs no lease, and returns no origin field, no
   number and nothing from `rw_root` or `rw_revision`. Like F2's `gw_root_metadata` (`:127-133`) it takes the
   owner id as a parameter.
2. For each returned root, one short read transaction with its own `ARCHIVE_READ` admission at that
   generation reads the stored origin fields and the creation time. If the admission is refused, the
   entry for that root is `{root_id, context_id, status}` with the refusal code in `status` (the lapse code,
   the completed-withdrawal code, `RW_WITHDRAWAL_PENDING`, or the generation-mismatch refusal when a renewal
   landed between the two steps, which the client may repeat), and none of the stored fields.

   **Note, 2026-11-16 (HG4 revision, PD-0087; DR-R8-1; reviewed in TR8F).** A READABLE entry now also carries the root's stored
   `operation_id`, so that a listed root can be reopened by the read route. It is read from `rw_revision` (`SELECT operation_id ...
   ORDER BY revision_seq LIMIT 1`) inside the same `ARCHIVE_READ` admission transaction as the stored origin fields
   (`real_service/service.py` `_entry_body`); the executor already holds SELECT on `rw_revision` and no installed SQL changed. A
   refused entry still carries no stored field, the operation id included. The list schema is now `finweb.cp7.real_scoped_list/2`
   (`real_scoped_contract.LIST_SCHEMA`). The web client's reader (`web/src/real-mode.ts`) is strict about it, and the commands the
   screen sends are in `web/src/real-mode-session.ts`.

So a withdrawn or lapsed context is listed with its refusal code, and the list is empty only when the owner
has no real root. Enumerating the owner's root ids without a lease shows the owner that a root exists and
nothing else. With one root (HG4) the cost is one extra transaction. The per-entry `status` is part of the
wire shape that R5's contract tests and review cover.

- It is a new module with a new schema version. E5's module, its routes, its tests and its
  installation in the dev app stay as they are. The old contract is the historical record, and T10
  checks it is unchanged.
- It is installed only in the real-mode app. One URL is never answered by both contracts in one app.
- **Where it is built.** In **R5**: the module, its schema version, route table, wire shapes and refusal
  codes, with contract tests that run without any route installed. Its shapes depend on the
  service output and the archive and reproduce results, which exist only after R3 and R5.
- It is **independently reviewed before use**: the review is an item of R5's independent review, and
  R7 installs the reviewed module in the real-mode app. R7 does not install it earlier, and R7 may not
  change its wire shapes without a new review.
- E1 and its `MetadataProvider`, which reads a `SOURCE_REGISTRY` file from disk, stay limited and
  closed (`real_source_contexts.py:142-164, :218-245`). Real mode uses a snapshot-based provider.

### 2.5 The owner is the sole publisher

- Issuer and revoker credentials are provisioned only to the owner's own sessions, never to agent
  sessions. **How [E19]:**
  - The publisher role authenticates with a password the owner sets in their own terminal. It is
    never created password-less, never trusted over the Unix socket, never written to a project
    file, and never generated or seen by an installer that an agent runs. Fact 18 is why: agent
    Bash runs as the owner's OS user and the sandbox allows the socket, so a socket-trusted role is
    usable by an agent, and the in-repo provisioner supports both password-less roles (`:101`) and
    passwords generated inside the installing process (`:104`).
  - The installer creates the publisher role so that it cannot log in until the owner sets the
    password. **A publisher password alone does not keep an agent out**: a socket-trusted superuser, or
    any member of the publisher role, can `SET ROLE` to it or write the history rows directly. Section 1.2
    states the cluster-wide rule that makes this true (a password for every role, no trust, the
    superuser password held only by the owner) and the preflight that checks it for REAL installs; R6's
    plan states the `pg_hba` lines.
  - Not claimed: separation from the owner's OS user. An agent that can read a secret the owner keeps
    in a shell environment or a file it can open could use it, so the owner keeps the secret where
    no agent session reads. This is an operational control.
- **Every publish, renewal and withdrawal records the issuer actor and a decision reference.** The
  reference is the PD id, the git commit that holds it, and the SHA-256 of that file at that commit
  **[E13]**. A PD can be amended in place (PD-0067 was committed at `260ec08` and extended at
  `703519c`), which changes the file's hash but not the committed blob the reference names. The tool
  records all three and refuses a command that lacks one. It does not check them against git; the
  check is by hand (`git show <commit>:<path> | shasum -a 256`). It does not judge which PD fits.
- This is an operational control and a record, not proof of identity.
- PD-0066 is the R0 record (PD-0067 adds the CN and label decisions); neither publishes anything or
  authorises a publish. The first publish needs its own PD, the owner's publish decision, recorded by the
  main session. That PD is its decision reference, and it states the expiry basis for every member source.
  The owner decided the three entries for HG4 (PD-0068 answer 4; 3.1), so the publish PD repeats them and
  the tool checks that it carries exactly one per member source.
- **A withdrawal on notice or termination needs no new PD.** PD-0066 decision 5 is the owner's standing
  instruction to withdraw on notice or termination (section 3.1), so its triple is a valid reference for
  that withdrawal. Other withdrawals, and renewals, name their own record: that includes the withdrawal
  and the renewal that end R8 (PD-0068 answer 3; 7.1), each a publisher act of the owner citing its own
  decision record.
- **The drain mark carries the same record** (2.1): issuer, the triple and the server time, refused
  without them. A withdrawal that stops admissions and then times out has therefore still recorded who
  stopped them, under which decision, and when.

Files affected: `real_workspace_v1.sql`; publisher tooling in `real_workspace_store.py`; tests T01,
T02, T04, T05.

### 2.6 The real fence and row guard refuse lease-less writes to any root [E21]; the stored market data is read through lease-checked functions [E28]

Technical re-review M-2 (items 1 to 5); PD-0069 and PD-0070 decision 2 (item 6). F2 passes writes to a root that is not registered (fact 19). The real gateway
is a fork of F2's design and must not copy that. Under B the real database holds only real-namespace
data, so **the whole database is the namespace**: there is no "unselected" root to leave alone.

1. **Write fence** (`BEFORE INSERT OR UPDATE OR DELETE`, per row, on every table the executor can
   write: `portfolio`, `account`, `ledger_event`, `benchmark_selection`, the other canonical ledger
   tables the stores write, `rw_root` and `rw_revision`). It has no `selected` test. A write is allowed
   only if a lease row exists for the current `(backend_pid, xid)` with purpose `EXECUTE_CREATE`, phase
   `OPEN`, the write's own target root as its `root_id`, that root registered, and `clock_timestamp() <
   complete_by` (strict; 3.1, E4). Otherwise `RW_WRITE_REFUSED`. Target-root resolution fails closed, as
   `gw_target_root` does for an unknown table (`guarded_workspace_v1.sql:180`). `TRUNCATE` stays
   refused for everyone (`:434`). Tables with no root (the identity table) are not economic tables; the
   executor's privileges on them are a separate decision in R1's role plan.
2. **Row policy** (`rw_row_allowed`, for the executor and legacy roles, restrictive like
   `gw_selected_guard`, `:431`). Its first test is the lease, not the registry: no lease for the
   target root means `false`, for a registered root and an unregistered one alike. A read needs a lease for
   that root **with `clock_timestamp() < complete_by`** (technical TR3R-L4; the archive read function checks
   the same, 3.1), so a `SELECT` at or after the deadline returns no row (a restrictive policy filters
   silently: the manual's example shows an administrator who "will not see any records, due to the
   restrictive policy", `ddl-rowsecurity`; no HEAD test shows it for this policy) and the archive read refuses; a write
   needs the open create lease. **Scope of the read bound** (technical TR4-M1; PD-0069): the row policy
   covers the tables of item 1, and the archive read function covers the archive. The `md_*` tables are
   covered by neither: they hold no root, and no migration enables row security on them (`git grep` of
   `src/persistence/migrations` at HEAD finds no `ROW LEVEL SECURITY` or `CREATE POLICY`). At HEAD the
   application role reads them by plain SELECT, which `read_release` needs (`market_data_store.py:517-540`,
   `:694-740`; "The application role is granted SELECT on the md_* tables only ..., which is all
   `read_release` needs", `:18-19`). **The owner has decided that the real executor does not** (PD-0069): it
   holds no privilege on any `md_*` table and reads their rows only through the lease-checked functions of
   item 6, which carry the same `clock_timestamp() < complete_by` bound.
3. **Journal** (`AFTER` row trigger). Where F2 returns early for an unregistered root (`:240`), the real
   journal raises `RW_WRITE_REFUSED`. It is defence in depth: a write that reaches it for an unregistered
   root means the fence was disabled.
4. **Registration comes first, only through admit.** The root registry is a root-link table (prospective
   `rw_root_link`, the analog of `gw_root`; it is not the S2 table `rw_root`). Only `rw_admit(new_root =
   true)` registers a root, inside the lease transaction and before the portfolio row exists. The
   executor has no `INSERT` on the root-link table or the lease table. `new_root = true` is refused when
   the portfolio row already exists (F2 does: `gw_admit`, `:156`), and a deferred foreign key from the
   root-link table to `portfolio` makes a registered root without a portfolio fail by COMMIT (F2's
   `gw_root_portfolio_fkey`, `:27`; the real create code fires it by name, 3.1). So "insert first,
   register later" fails at the insert, and "register without a portfolio" fails at COMMIT.
5. **Tests (T03, R3; each barrier alone, in a disposable database, as the owner disables the others).**
   On the real executor connection with no admit:
   - `INSERT INTO portfolio` with a new uuid that is registered nowhere is refused with
     `RW_WRITE_REFUSED`; then the same for `account`, `ledger_event` (with an existing account of
     another root and with a new one), `benchmark_selection`, `rw_root`, `rw_revision`;
   - with a read-only lease (phase `READONLY`), the same inserts are refused; with an open create lease
     for root A, an insert for an unregistered root B and one for registered root C are refused
     (`RW_ROOT_DIFFERS`);
   - insert first, register later: the executor's `INSERT INTO portfolio` for B is refused (above). With B
     inserted by the owner role in the disposable database, `rw_admit(new_root = true)` for B is refused
     because B exists. With the fence disabled by the owner, the row policy alone still refuses the
     executor's insert; the executor cannot insert into the root-link table or the lease table at all;
   - with only the row policy disabled the fence refuses; with only the fence disabled the row policy
     refuses; with both disabled the journal raises;
   - the executor cannot disable any of them: `ALTER TABLE ... DISABLE TRIGGER`, setting
     `session_replication_role` and `SET ROLE` to the owner all fail (catalog audit of the executor's
     privileges);
   - at COMMIT, a registered root with no portfolio row fails (the deferred foreign key).
6. **The stored market data is read through lease-checked functions, not by SELECT [E28]** (PD-0069, the
   owner's answer to R4R-M1 and TR4R-M1: "ask for a lease-checked read function in place of the executor's
   plain SELECT on md_*, so a lapse or withdrawal stops those reads too (All rights off, kept literal)". The
   mechanism is the owner's, and so is who may call the functions ("Which leases read which rows" below;
   PD-0070 decision 2). The rest of the specification is mine, for the reviewer.)
   - **The functions.** One definer function per `md_*` table, thirteen: the tuple `MD_TABLES`
     (`market_data_store.py:72-76`; `md_file` to `md_risk_free_point`), prospective names
     `rw_md_<table>(release_id text)`. Each `RETURNS SETOF` its table's row type, so a caller's column list,
     `WHERE`, `ORDER BY` and row handling stay what they are today. They are installed in the schema that holds
     the `md_*` tables, so `pinned_schema` finds them as it finds the tables (`:501-514`), and are owned by the
     install owner role, which holds the table privileges. Each is `SECURITY DEFINER` with the fixed
     `search_path=pg_catalog,<schema>,pg_temp` of F2's definer functions (`guarded_workspace_v1.sql:94`, and
     the others to `:408`). The manual (`sql-createfunction`) says a definer function runs "with the privileges
     of the user that owns it", that `search_path` should be set with `pg_temp` last so that a temporary
     table cannot mask a table, and that `EXECUTE` is granted to PUBLIC by default, so it must be revoked and
     granted by name, as F2 does (`:445-450`). A catalog test compares the functions with the `md_*` tables of
     the schema, so a table that a later migration adds without a function is a finding (and the gateway
     change then reopens R3, 7.1).
   - **What each call checks, in this order; any failure refuses and never filters**, with a code of its own
     (prospective `RW_MD_READ_REFUSED`): (a) a lease row exists for the current `(backend_pid, xid)`, the
     lookup the write fence makes (item 1); (b) its purpose is `EXECUTE_CREATE` or `EXECUTE_REPRODUCE`; (c)
     `clock_timestamp() < complete_by`, strict, at statement time on every call, with `complete_by <=
     valid_until` by the table check (3.1); (d) the `release_id` argument equals the release id in the
     snapshot of the lease's context (2.1). (b) and (d) are the owner's (PD-0070 decision 2), and (c) is
     the bound of PD-0069 and PD-0068 answer 1. `md_file`, which has no release column, returns the files that
     `md_release_file` lists for that release. **The refusal's SQLSTATE is outside class 23 and is not
     `22003`** (technical TR5R observation): `translate_error` maps `22003` and every class-23 code to a
     typed store error (for a class-23 code that no named constraint claims, `MarketDataRuleRejectedError`, a
     write-rule error; `market_data_store.py:132-148`), and `read_release` re-raises any other error unchanged
     (`:734-738`). A class-23 code would therefore be reported as a write-rule rejection; any other reaches
     the caller as the driver's error with its SQLSTATE and message code. R3 fixes the value. R5's real-mode
     read path classifies the refusal by its message code, as 3.1 does for `RW_DEADLINE`: a typed refusal with
     whole rollback of the read, neither a write-rule error nor UNKNOWN. T-m asserts it (4.4).
   - **Which leases read which rows** (the owner's: PD-0070 decision 2, "Accept the narrowing (Recommended)";
     PD-0069 says "an admitted lease" and the owner narrowed it). Only the two purposes whose code runs
     `read_release`: `EXECUTE_CREATE`, where the world builder reads before the seal (W05, W11), and
     `EXECUTE_REPRODUCE`, which rebuilds the world from the same snapshot (7.1, R5; that code does not exist
     yet, and if R5 finds it needs no stored market data, the cost is one purpose that can read its context's
     own release). `ARCHIVE_READ` and `ARCHIVE_EXPORT` read the archive and the `rw_*` rows, never `md_*`, and
     get none. And only the rows of the one release that the context's snapshot names: not the loader's
     unreferenced candidates, not another context's release.
   - **A lapse and a withdrawal** (PD-0069: "All rights off, kept literal"). The function keeps no state of its
     own; it reads the lease. At or after `valid_until` every admission is refused, and a lease admitted
     earlier has `complete_by <= valid_until`, so its reads stop then at the latest. A pending drain mark and a
     completed withdrawal refuse every new admission, so a connection with no lease is refused by (a). An
     operation admitted before the mark may finish until its own `complete_by`, as for every other statement:
     "Withdrawal does not cancel admitted work" (3.1, Cancellation). That is the same bound as the other
     reads, which is what PD-0069 asks for.
   - **Grants.** `EXECUTE` on the thirteen functions to the executor, from the shared installer code's list
     (4.2), with `REVOKE ALL ... FROM PUBLIC`, and to no other role: not the loader, not the publisher (the
     executor's `USAGE` on the schema, which it needs to reach any object, is unchanged). **The
     executor holds no privilege on any `md_*` table**, column-level privileges included; the catalog audit
     compares the executor with exactly that (1.2 rule 5.3 (e) (iii)). The legacy application role's SELECT on
     these tables (`APP_GRANTS`, `test_postgres_least_privilege.py:87`, asserted at
     `test_postgres_market_data_store.py:178-184`) belongs to the legacy installs and is not touched; the REAL
     database has no legacy role (W07).
   - **How `read_release`'s contract and callers are kept.** `read_release(conn, release_id,
     exchange_of=None, *, registry)` (`market_data_store.py:695-699`) keeps its signature, its return type
     (`PostgresMarketData`), its typed errors, the `pinned_schema` step with schema-qualified names (`:501-514`,
     the C2-5 defence against temporary tables), the registry gate and the digest check (`:772-774`). R5 adds
     **one keyword-only parameter** (prospective `lease_checked: bool = False`). With the default the SQL is
     today's. With `True`, each `FROM {qs}.md_x` reads `FROM {qs}.rw_md_x(%s)`, and the `md_file` join reads
     `{qs}.rw_md_file(%s)`; the column lists, the `ORDER BY`s, the row-to-object code and the digest check are
     unchanged, so the object returned is the one a direct read returns. The real-mode code passes `True`. A
     caller on the executor's connection that keeps the default gets its first SELECT refused by the database
     (`42501`, the code that `test_postgres_market_data_store.py:174-176` shows for a SELECT with no grant), so
     nothing reads around the function.
   - **Callers** (`git grep` at HEAD): none in `src/` outside `market_data_store.py` itself. Fifteen test
     files contain 38 lines with `read_release(`: `test_cp3_golden_part1.py` to `part4.py`, `test_market_data_segments.py`,
     `test_marketdata_cp2c2_exit.py`, `test_marketdata_listing_market_gate.py`, `test_performance_cp3a.py`,
     `test_performance_cp4_part_a3.py`, `test_performance_cp4_part_a4.py`,
     `test_postgres_corporate_actions_service.py`, `test_postgres_cp2_fix_round.py`,
     `test_postgres_cp4_golden.py`, `test_postgres_market_data_store.py`, `test_postgres_risk_free.py`. Two
     tripwire tests patch it by name (`test_web_real_source_gate.py:291`,
     `test_web_real_workspace_contract.py:322`); a docstring (`marketdata_cp2c1_kit.py:102`) and a comment
     (`test_postgres_least_privilege.py:72`) mention it.
   - **What HEAD tests would need to change** (none is changed here): **none, if the default stays.** All fifteen
     call `(conn, release_id, [exchange_of], registry=...)` on the roles of the legacy installs; the two
     tripwires keep their meaning because the name stays; the least-privilege assertions describe the legacy
     role. If the default were flipped, all fifteen would fail on those roles. What is added and not changed:
     sibling tests for the function path (3.2): a temporary-table sibling of the shadow probe at
     `test_postgres_cp2_fix_round.py:86-102`, and a digest-parity test.
   - **Where it lands.** R3 builds the thirteen functions, their grants and the audit comparison. R5 adds the
     keyword and the call, and no SQL, so "after R3 no increment adds gateway SQL" stays true.
   - **Not claimed, and not shown.** That a function bounds what was already read: rows returned before
     `complete_by` are the holder's, as for the archive. That a holder of the executor credential cannot run the
     product's own admitted paths while the context is live (rule 4 of 1.2). The raw files, the download tool
     and the legacy CLI stay outside (3.3). **Shown by the manual, not run** (technical TR5 and TR5R
     observations): a function returning `SETOF` a table's row type is used in `FROM` like a table, its
     columns usable in `SELECT`, `JOIN` and `WHERE` and named as the table's attributes
     (`queries-table-expressions`, "Table Functions"), and a definer function runs with its owner's privileges
     (`sql-createfunction`). **Not shown by a manual page or a HEAD test:** the two together, called by a
     role with no privilege on the table, and that psycopg and `pinned_schema` work unchanged on a function
     call there. R3's function tests and R5's parity test are the first to show them.

## 3. D3: expiry is an X1 lease

**Decided** (PD-0066 decision 5). The owner opened `https://www.alphavantage.co/terms_of_service/` on
2026-10-24 and saved it as a PDF outside the project (156,583 bytes, 4 pages).

PD-0066 keeps the owner's words and the main session's notes apart, and so does this file.

**The owner's words** (verbatim answers, PD-0066 decision 5 `:137-152`; quoted in part):

- (1) date or version: "None";
- (2) "one (1) year terms thereafter ("Renewal Term") until and unless either Party provides the other
  Party with thirty (30) days prior written notice to the end of the Annual License Term or the
  Renewal Term";
- (3) "Upon termination, User's access to the Alpha Vantage Platform shall be deactivated. ... The
  following Section survive termination of this Agreement: Indemnity.";
- (4) "User shall retain all right, title and interest to the intellectual property rights to its data,
  and any other Content developed by User".

**The owner's choices** (verbatim, `:172-184`): "X1 lease (Recommended)"; "All rights off
(Recommended)"; "On or near 2026-10-01".

**The main session's notes** (PD-0066 `:157-168`; **not the owner's words, not legal advice**): an
annual term that renews automatically for one-year terms unless either party gives 30 days' notice;
on termination only the indemnity survives; sentence (4) is section 5b, the user's rights in the
user's own data and content, while section 5a reserves Alpha Vantage's rights, including its "database
and files"; the terms do not say what happens to Alpha Vantage data already downloaded; no date or
version is shown, so the reading is of what the site served on 2026-10-24. This file does not
treat sentence (4) as a statement about Alpha Vantage data after termination, and it does not
attribute that reading to the owner. The audience is the owner and the project's agents (PD-0028,
PD-0064); nothing is displayed or exported to anyone else.

**The recorder's description of X1** (PD-0066 `:187-189`): "Admission is refused after it, and an
operation admitted before it may complete." That sentence is the recorder's gloss on the option, not a
quote of the owner. **The owner has since answered the question it left open (PD-0068 answer 1): "(b) No,
cap at the end (Recommended)".** An operation admitted before `valid_until` may not complete after it, so
the gloss is superseded and section 3.1 states the rule.

From the owner's answers: the term began on or near 2026-10-01. The key existed by the first download
(2026-10-01T04:53:50Z), so the current term ends on or before 2027-10-01. `valid_until` is **2027-09-01**:
the main session proposed it as conservative, and the owner kept it and chose not to pin the term start
from the signup date (PD-0068 answer 4, "Keep 2027-09-01"). The limit that follows is disclosed in 3.1.

### 3.1 The lease

| Element | Rule |
|---|---|
| Expiry kind **[E14]** | `LEASE`, `NONE` or `UNKNOWN`, **derived from evidence, never defaulted and never inferred from silence** (FF1-C06; E10 section 5: "distinguish known explicit no-time-expiry terms from absent evidence"). F2's `FINITE` becomes `LEASE`, the only finite meaning supported. Evidence is per **member source**. The member sources are the `source_id`s of the members' manifests, stored in the hashed member tuples (2.1): publish takes them from the manifests whose digests it verifies, and admit takes them from the stored snapshot, so the publisher cannot omit a source and a crafted history row cannot shrink the set. A basis entry is `(source_id, basis, decision reference)`, where `basis` is `LEASE_TERM` (a recorded reading that shows a term, notice or termination; the entry also carries `term_end_not_after`, a UTC instant that is the latest the source's current term can end), `NO_EXPIRY_READING` (a recorded human reading that shows explicit no-time-expiry terms for this use) or `NOT_ASSESSED` (the cited decision states that no term evidence is recorded for this source; it is an acknowledgement and is evidence neither of a term nor of its absence). A source with no entry has no evidence, and there is no default. |
| Which kind the evidence allows | **Every member source needs exactly one entry, and no entry may name a non-member**; a missing or extra entry makes the kind `UNKNOWN` (technical re-review L-9: a `LEASE` may no longer leave a member source without an entry, because a source whose term ends before `valid_until` would then never be noticed). `LEASE` needs at least one `LEASE_TERM` entry, a `valid_until`, and `valid_until <= min(term_end_not_after)` over the `LEASE_TERM` entries (**the plausibility rule**, below). **Why the rule is relaxed from the round-2 form `valid_until + W <= min(term_end_not_after)`** (PD-0068 answer 1, which left this to the engineer for review): that form was written for the in-flight option (a) of PD-0068 answer 1 (not D4's option (a) of 4.2), where an operation admitted before `valid_until` could finish up to `W` after it. Under the owner's cap no economic write, seal or guarded load succeeds at or after `valid_until` (E4 row), so `W` has no part in the margin. **What the rule is, honestly** (conformance R2-M1; PD-0068 answer 4): `term_end_not_after` is an **upper bound** of the term end, "the latest the source's current term can end", not an instant up to which the term is known to run. From "the term ends no later than X" and "`valid_until` is no later than X" nothing follows about whether `valid_until` is before the real end. So the rule only refuses a `valid_until` that lies after the latest the term could possibly end. **It does not show that the lease stays inside the licence term**, and it is not a safety margin. Publish and the status view print its result as "`valid_until` is not later than the recorded upper bound of the term end; no lower bound of the term end is recorded", and never as "within the term". The limit is stated in the publish record and the HG4 package (the HG4 entries, below). Only a lower bound would remove it. PD-0068 answer 4 names the way: the owner pins the term start from the Alpha Vantage account. The owner then records a **renewal** (a new generation of the same context, with its own decision record) that carries a `term_end_not_after` derived from that start and a `valid_until` not later than it. If that `valid_until` is earlier than the current one, the renewal is a **date correction** (the Renewal row and E25), which is the act that makes the remedy work; the first form of E25 forbade it and is withdrawn (conformance R3C-M1; technical TR3-M4). **What the pin remedy requires**, stated so that nobody reads it as free: (a) a new `valid_until` must be later than the server clock when the correction is recorded, because a correction at or before the clock is refused. **If the pinned term has already ended and no notice of non-renewal or termination was given, the licence has renewed** (it continues in one-year Renewal Terms "until and unless either Party provides" thirty days' prior written notice: PD-0066 decision 5, the owner's reading (2)), so the pin shows the end of a term that is over and not of the current one. The owner then pins the start of the Renewal Term and records a renewal, at an equal or a corrected date, whose entry carries that term's end as `term_end_not_after`. **That is a renewal and not a withdrawal**: a withdrawal is for notice or termination, which is when the licence in fact ends (PD-0066 decision 5), and this design adds no obligation to withdraw. If notice or termination was given, the withdrawal on notice applies as the Notice row says (conformance R3R-L2); (b) the correction takes the head exclusive lock like any generation change, so it is appended only when no lease is in flight, and a stream of overlapping admissions can delay it as it could a withdrawal (not run; section 9), in which case it waits (the owner may withdraw instead if the rights should end first; that is the owner's choice and not a step of the remedy); (c) until the owner pins and records, the limit stands. The rule's text does not change, its strength does. This design adds no lower-bound field. `NONE` needs a `NO_EXPIRY_READING` for **every** member source and no `LEASE_TERM` or `NOT_ASSESSED` entry. A source with no recorded licence term is not a `NO_EXPIRY_READING` (OpenFIGI and `calendar.manual` have none that qualifies, fact 15: the existing `terms_check` notes are not one, and none is asked for in this slice). Anything else is `UNKNOWN`: publish refuses it, and admit never accepts it. Admit **re-derives** the kind from the stored snapshot's member sources and the generation's stored entries, and refuses if the result differs from the stored kind, so a tooling default, a republish that copies F2's `NONE`, or a crafted row cannot admit. **For HG4 the owner decided the entries** (PD-0068 answer 4): the three entries, the context's kind and the disclosed limit are stated in "HG4 expiry basis entries and the disclosed limit", below this table. |
| `valid_until` | In the head and in every history row, as a UTC instant, with the decision reference that set it and the basis entries it rests on. First value: first refused instant 2027-09-01 00:00 Asia/Shanghai, which is 2027-08-31T16:00:00Z **[E1]**. Admission needs `now < valid_until`. |
| Trusted clock | The database server's `clock_timestamp()`, sampled once inside the admit function **[E3]**, in this order: take the mode and head locks; **read `latest`**, the greatest instant among the committed history times, drain-mark times and lease `admitted_at` values (indexed); **then sample `now`**; refuse as a clock regression if `now < latest`. Reading before sampling removes the race of overlapping admissions (technical re-review L-2): a row that was committed before the read has a sample time earlier than the read, which is earlier than `now`, and an admission that has not committed is not visible and cannot refuse this one. Only a real regression of the server clock trips it. No parameter, setting or test hook overrides the clock in any install. **Policy for jumps** (FF1-C06 and E10 T07 name jump and outage): a forward jump cannot be told from time passing, so it fails closed (the lapse and `complete_by` arrive sooner); a backward jump is refused only when `now` falls below `latest`, and a jump back farther than that, or in a period with no recent instant, is not detected, which is the trusted-operator boundary (section 9); an outage means no database and so no admission. |
| Admission under lock | Mode shared, head shared (as F2's `gw_admit`, `v1.sql:141-143`); generation equals the lease's; no drain mark for that generation (refused with `RW_WITHDRAWAL_PENDING`); the expiry kind re-derived (above); read `latest`, sample the clock (above); require `now < valid_until`, the purpose right and `ARCHIVE_READ` (as `v1.sql:146`). The lease row records the sampled instant (`admitted_at`), the `valid_until` it was admitted under, and `complete_by` (next row). Create, read, export and reproduce are separate admissions, each with its own check. |
| An admitted operation is bounded by its lease deadline, never later than `valid_until` **[E4]** | After admission nothing compares the clock with `valid_until` again, **because the lease's own deadline cannot be later than it**: `complete_by = LEAST(admitted_at + W, valid_until)` for every lease, with `valid_until` the value the lease was admitted under (PD-0068 answer 1, "(b) No, cap at the end (Recommended)"). Option (a), completion up to `W` after `valid_until`, is not a live path and has no switch. `W` is one constant written once by the installer with the install kind: a test install sets seconds, and the engineer's proposal for the real install is 10 minutes (PD-0068: the value stays an install constant and **only shortens** deadlines). It is an operational limit, not a financial convention, and the owner may change it. The lease table carries `CHECK (complete_by <= valid_until AND complete_by > admitted_at)`, so a lease with a later deadline cannot be stored. A lease admitted just before `valid_until` gets a deadline just after its admission and can do almost nothing: that is a consequence of the cap, not a defect. **Four database checks of `clock_timestamp() < complete_by`**, strict, so that the first refused instant of a capped lease is `valid_until` itself, as E1 says (technical re-review M-1): (1) the write fence, on every economic write by the executor (R3; the journal trigger already reads the lease on each write, `v1.sql:241-246`, fact 17); (2) the seal (R3); (3) the guarded loads (R2) **and the read side of the rooted tables, of the archive and of the stored market data (R3; technical TR3R-L4; PD-0069): the row policy's read branch (2.6 item 2), the archive read function and the `md_*` read functions (2.6 item 6)**; (4) the **deadline guard** (R1): a constraint trigger of its own on the lease table, `DEFERRABLE INITIALLY DEFERRED`, queued by the admit insert and fired by PostgreSQL inside COMMIT processing. It is a different trigger from the bundle guard (the fork of `gw_bundle_complete`, `v1.sql:389`) on purpose, so that product code can fire the bundle guard and every other deferrable constraint early **by name** and leave the deadline guard pending until COMMIT. (1) to (3) run at statement time; no session setting, connection option or client library changes them (fact 16). **What each bounds.** (1) to (3): no economic write, seal or guarded load of an operation, and no read of a rooted table, of the archive or of a stored market-data row, succeeds at or after `complete_by`, so none succeeds at or after `valid_until`. PD-0068 answer 1 names the first three (`:35`); the read bound of the rooted tables and the archive is the design's addition (TR3R-L4), kept so that these reads are not the one thing the cap leaves open until COMMIT, and the read bound of the stored market data is the owner's (PD-0069). `rw_list_roots` returns identifiers only and needs no lease (2.4), so no deadline applies to it. **A stored market-data row (`md_quote` and the other `md_*` tables) is read only through the lease-checked functions of 2.6 item 6.** `read_release` calls them on the executor's connection under the held locks (W05); a holder past `complete_by`, or one that has set its timeouts to 0 and stalled, is refused at its next call, and the executor holds no privilege on the tables, so there is no other route. A read's value is also returned only after its COMMIT, which the pending deadline guard (4) refuses. What a function does not bound is a row already read before `complete_by` (2.6 item 6). The loader's own reads are not in (3): it has no lease; the owner decided that its login is off between loads, and the limits are in section 7 (3.3; PD-0070 decision 1). (4): if it is still pending at COMMIT, a commit whose pre-commit processing starts at or after `complete_by` is refused and the transaction rolls back wholly. **Where it is pending.** The shared create tail (E23) never issues `SET CONSTRAINTS ALL` in any mode and never names the deadline guard. This replaces the first fix round's rule, that the create code issues `SET CONSTRAINTS ... IMMEDIATE` only before the seal, which could not work: before the seal the lease is `OPEN`, so firing the bundle guard refuses every create with `F2_UNSEALED` (`v1.sql:356`; F2's `test_c14` first half expects exactly that), and F2's own `_stage` fires everything after the seal with `SET CONSTRAINTS ALL IMMEDIATE` (`guarded_workspace_store.py:250`), which would consume the deadline guard before any stall. The real create code instead moves the bundle guard, the root foreign key and the other deferrable constraints early by name after the seal, as F2's `validate_domain_constraints` does for its two (`guarded_workspace_context.py:79-102`), checks the inventory of deferrable constraints, keyed by `(name, table, kind)` as F2's is, so that an unknown one is refused, and excludes only the deadline guard. The guard's name is unique among the schema's constraints, because `SET CONSTRAINTS <name>` acts on every match of a name (fact 17); an R1 catalog test asserts it, so that naming another constraint cannot fire the guard early. **Not claimed, and kept as disclosed limits under the cap (PD-0068 answer 1).** That nothing commits after `complete_by` or after `valid_until`. Two limits remain. (i) **The commit-processing gap:** the guard samples the clock before the commit is durable, so a commit can become durable a short processing gap later. (ii) **A guard-bypassing executor:** a session that fires the guard early (`SET CONSTRAINTS ALL IMMEDIATE`, or the guard's name) and then stalls commits unchecked; that is a hostile or faulty executor, outside what this check defends against. The executor cannot bypass the statement-time triggers that way (an unprivileged `SET CONSTRAINTS` reaches only deferrable constraints), so this is a limit of this deferred guard alone (technical round-2 observation; section 9). It is kept as a characterisation test (3.2). E10 section 5 says a final trigger cannot on its own prove absolute validity at the physical commit (FF1-C06: "a second check or buffer is not treated as proof"; X2 stays UNSUPPORTED). So under the cap: no economic write, seal or guarded load of an operation admitted before `valid_until`, and no read of a rooted table, of the archive or of a stored market-data row, succeeds at or after it, and on the product path its commit is refused if its processing starts at or after `complete_by`. This is validity at admission plus statement-time bounds, **not** commit-time validity. For read, export and reproduce leases there are no economic writes: the read bounds of (3) (rooted tables, archive and stored market data) and the deadline guard apply, and a read's value is returned only after its COMMIT succeeds, as F2's `_read_operation` does (`guarded_workspace_store.py:316-329`: the value is returned after the transaction block). F2's `gw_archive` checks the lease and the identity but no time (`guarded_workspace_v1.sql:407-420`), so the real fork adds the time check; without it a holder who keeps the transaction open past `complete_by` could still read, and only the COMMIT-time guard would stand between the holder and the data. **These read-side paths need the guard pending as much as the create does** (technical TR3-L7): read, reproduce and each list entry call one shared read tail (E23), and have their own non-vacuous recorder, static audit and stall test (3.2, T-f and T-g). **How a COMMIT-time refusal is classified.** F2 returns UNKNOWN for an `OperationalError` or `InterfaceError` (`guarded_workspace_store.py:271-272`) and moves its other checks before the COMMIT, so that a failing COMMIT means an infrastructure fault. The real create code keeps that rule with one exception: an error whose server message carries the deadline guard's code `RW_DEADLINE`, with the connection back at `IDLE`, is a **definite refusal**. The server raised it while processing the COMMIT and the transaction was rolled back: `test_c13` shows that for the sibling bundle guard (the refusal leaves no row), and R5's test, which runs the shared create tail (E23) on the `SYNTHETIC_TEST` create (4.4), must show it for this guard (fact 17). It is reported as a typed refusal with no numeric diagnostic and nothing addressable. Any other error at COMMIT, or no answer, is UNKNOWN: read-only reconciliation on a new connection, no automatic retry, and the operation id is not treated as unused (E10 section 6). **Reconciliation is itself an `ARCHIVE_READ` admission** (F2's `reconcile` calls `archive_read` and re-raises every refusal except `F2_NOT_FOUND`, `guarded_workspace_store.py:352-368`), so under the cap it is refused after `valid_until`, during a pending drain mark and after a completed withdrawal. The shared tail maps such a refusal to UNKNOWN (no retry, no guess of rollback), and the operation stays unreconciled until a renewal restores the right (test T-e, 4.4). The generalised `np_guard` (n2a `:190-191` re-checks the head's rights and expiry after admission) tests the **lease's** `complete_by`, the stored rights and the re-derived expiry kind. It needs no separate `now < valid_until` test, because the lease's `complete_by` is never later than `valid_until`. (Under the round-2 in-flight option (a) such a test would have refused an operation admitted before `valid_until` at its first guarded load after it; the cap removes that conflict.) |
| Lapse | Computed on every admission; no row is written. Effective rights = stored rights AND `now < valid_until` **[E5]**. At or after `valid_until` all four purposes are refused with a lapse code, even if the stored rights are true. An operation already admitted is governed by `complete_by`, which is never later than `valid_until` (E4), not by lapse. |
| Renewal | A human act only. The publisher records a new generation of the same context with a `valid_until` **strictly later than the server clock at the record** **[E25, amended in the round-3 fix round]**, fresh basis entries (one per member source, the plausibility rule above, applied to the new date) and a decision reference. The new `valid_until` may be **later** than the current one (extends the lease), **equal** (restores the rights after a withdrawal without extending it, which is what the last step of R8 does, 7.1) or **earlier**. **An earlier one is a date correction** (conformance R3C-M1; technical TR3-M4): the owner's remedy when the term end is found to fall before `valid_until`, which PD-0066 decision 5 gives the owner ("The owner can correct it from the signup date") and PD-0068 answer 4 relies on ("Pinning the signup date later ... would remove the limit"). Round 3's first form of E25, which refused an earlier date, blocked that remedy in the one case where it matters, and is withdrawn. A correction needs what any renewal needs: its own decision record (which names the corrected date and the reading it rests on), fresh basis entries whose `term_end_not_after` come from that reading, the plausibility rule against the new date, and the head exclusive lock, so it is appended only when no lease is in flight and no lease admitted under the longer date outlives it. The publisher tool prints "`valid_until` moved earlier: `<old>` to `<new>`", and the history keeps both generations. A `valid_until` at or before the clock is refused (it would end the lease at once; a withdrawal does that, and says so). A correction is gated by the preflight like any renewal (1.2 rule 5.1); an owner who must shorten the life at once, with the environment unrepaired, withdraws. Executor and loader roles cannot renew. Without the record the context lapses and admissions fail closed. While a drain mark is pending, a renewal is refused unless it names that mark; naming it is a recorded decision with its own reference, and the mark becomes superseded and stays readable. R1 builds no other precondition for a renewal; in particular it does not check that the terms were re-read (7.2 recommends it, and nothing enforces it). |
| Notice or termination | If either party gives notice of non-renewal or termination, the owner withdraws the context: a new generation with all four rights false. The decision reference is PD-0066 decision 5 (2.5), so the withdrawal does not wait for a new PD. **The install preflight never blocks it** (technical TR3-M3): `withdraw` is not a gated command, it commits the drain mark before it does anything slow, and it prints the preflight result beside its own (1.2 rule 5.1). |
| Stalled work | A stalled admitted worker cannot extend rights (above), but it keeps its mode and head share locks, and with them it can hold a withdrawal at "not yet effective". The product's connections set statement, idle-in-transaction and (where the server has it) transaction timeouts as connection options, as HEAD's stores do (fact 16). They end ordinary stalls but a session can override them, so they are **not** the bound. **The design sets no role-level setting, and the preflight refuses one on a real role or on the real database** (1.2 rule 5.3 (a), technical TR3R-L2). A row for all roles and all databases (`ALTER ROLE ALL SET`, `setrole` and `setdatabase` both 0) is not refused, and nothing here relies on its absence: the timeouts are not the bound, and the preflight's `SHOW` sees the one setting that matters (technical TR4R and TR5R observations). The lease records `backend_pid` (F2 does: `v1.sql:30`). A withdrawal that cannot proceed names the blocking leases and their `complete_by`. A lease past `complete_by` can no longer write or seal, and on the product path its commit is refused by the deadline guard (which the product create path leaves pending). So the owner, as the server's trusted operator, can end its backend (`pg_terminate_backend`) without losing a commit that was still valid. The publisher role itself has no right to terminate backends. |
| Cancellation | Withdrawal does not cancel admitted work. It (1) commits its drain mark in a transaction of its own (issuer, decision-reference triple and server time, refused without them: 2.1), so no new admission starts, including under overlapping share locks, where a new share locker may overtake a waiting exclusive locker (my reading of PostgreSQL; not run; section 9) **[E18]**; (2) waits for in-flight work under a `lock_timeout` the tool sets on its own connection; (3) appends the new generation, which names the mark. **A timed-out withdrawal is explicit, in the database and to the owner** (conformance re-review DC-M1; technical re-review M-4). If the wait expires: the mark stays, with its issuer, reference and time; no generation is appended; admissions are refused with `RW_WITHDRAWAL_PENDING`; the status view lists the mark as pending with its age; and the tool exits with a status of its own, not success, printing "not yet effective for in-flight work; new admissions refused since `<recorded time>`" with the blocking leases and their `complete_by`. It never prints "done". A pending mark ends in only two ways: re-running the withdrawal finds it and continues from step (2), or a renewal names it and supersedes it. A cancelled or timed-out operation rolls back wholly. |

**HG4 expiry basis entries and the disclosed limit** (PD-0068 answer 4: "As proposed (Recommended)" and
"Keep 2027-09-01"). The first HG4 publish record states exactly one basis entry per member source:

| Source | Basis | Detail |
|---|---|---|
| `alphavantage.us` | `LEASE_TERM` | PD-0066 decision 5, the only reading there is; `term_end_not_after` 2027-10-01T00:00:00Z |
| `openfigi` | `NOT_ASSESSED` | no term evidence is recorded; an acknowledgement, evidence neither of a term nor of its absence |
| `calendar.manual` | `NOT_ASSESSED` | the owner's own file built from public exchange notices; no licence reading |

- The context's kind is `LEASE`. `NONE` stays unreachable. The whole context lapses at `valid_until`.
- `valid_until` stays 2027-09-01 00:00 Asia/Shanghai (2027-08-31T16:00:00Z). The term start is not pinned
  from the signup date. The plausibility rule is met by this value: `valid_until`
  (2027-08-31T16:00:00Z) is not later than the recorded upper bound (2027-10-01T00:00:00Z), which is all the
  rule says. **It is not a margin and not a month of buffer before the licence ends** (conformance R3C-L1):
  no lower bound of the term end is recorded, and the term may already end before `valid_until` (the
  disclosed limit, below). The publish record is drafted from this wording and from the limit below, and
  the main session should not paraphrase either into a margin.
- PD-0066 words the term end as "on or before 2027-10-01" without a time zone. `2027-10-01T00:00:00Z`
  is the value PD-0068 states. It is the later of the two readings (Shanghai midnight would be
  2027-09-30T16:00:00Z), and for an upper bound the later reading is the weaker one. This design records
  the value as the owner decided it and no longer calls it "the earlier reading" (conformance R2-M1).
  Nothing in HG4 depends on the difference; the main session may ask the owner whether the earlier
  instant is preferred.
- **The disclosed limit, as the owner accepted it.** `term_end_not_after` is an upper bound. The owner's
  key existed by 2026-10-01, but the exact signup date is not recorded. If the term began earlier than
  about 2026-09-01, it would end before `valid_until` (2027-09-01), and the lease would run past the
  licence term. The owner accepted the 2027-09-01 date knowing this. Pinning the signup date later, from
  the owner's Alpha Vantage account, would remove the limit (PD-0068 answer 4). **In this design that is
  done by a renewal that is a date correction** (the Renewal row, E25), a publisher act of the owner whose
  decision record states the pinned reading. It moves `valid_until` earlier only to a date still ahead of the
  server clock. If the pin shows that the pinned term has already ended and no notice was given, the licence
  has renewed and the owner records a renewal for the Renewal Term, not a withdrawal (the kind row of the
  table above, (a); R3R-L2). Until the owner pins and records, the limit stands. The first publish record and the HG4 package
  state this limit; the rule's wording above is written so that no screen or record can read as a
  guarantee.

**What E10 section 5 required, and what the owner decided.** E10 section 5 lets X1 move toward GO with
in-flight completion only when "actual license/purpose terms and product decision explicitly permit
in-flight completion", with bounded resources and cancellation tests, and says a developer cannot
manufacture that rights extension. The record showed:

- the terms reading (PD-0066 decision 5, four answers) says nothing about operations that run across
  the end of a term;
- the owner's own words for the choice were "X1 lease (Recommended)"; the sentence "an operation
  admitted before it may complete" was the recorder's gloss on X1 (section 3, `:187-189`);
- so the explicit permission E10 asks for was **not established by the owner's words**.

The round-2 design therefore bounded the extension at `W` and put the question to the owner as open item
7. **The owner answered (PD-0068 answer 1): "(b) No, cap at the end (Recommended)".** The E10 section 5
condition for in-flight completion (terms and a product decision that permit it) is not met and is not
needed: the terms are silent, and the owner chose no completion past the end. The formula is
`complete_by = LEAST(admitted_at + W, valid_until)` for every lease; the in-flight option (a) is not a live path. **What
this gives, stated plainly** (technical re-review M-1): no economic write, seal or guarded load of an
operation succeeds at or after `valid_until`, and on the product path a commit whose processing starts at
or after it is refused by the deadline guard. It does **not** give "nothing commits after `valid_until`":
the commit-processing gap remains, and so does a session that fires the guard early (a guard-bypassing
executor). E10 section 5 and FF1-C06 call validity at the physical commit unsupported (X2 stays
UNSUPPORTED). No document, screen or test claims otherwise.

On termination or lapse **all four rights go false** (create, read, export, reproduce). Keeping past
reports readable would need its own explicit decision. PD-0064's storage, archive, export and
reproduction reading applies only while the licence is in force.

### 3.2 X1 design and tests, marked by increment

The tests (T07 and FF1-C06, with the E10 section 5 X1 conditions). **Each item says which increment can
contain it** (conformance re-review DC-L3):

- **R1**: read-only-phase leases (phase `READONLY`). They take the locks and carry the deadline, but write
  nothing economic. R1 has no seal and no create (7.1), so no R1 item needs an economic write;
- **R2**: adds the guarded load;
- **R3 (E11)**: the seal and the fence exist; create-phase items run on crafted bundles and are
  **crafted probes, not product evidence** (4.4);
- **R5**: the product create path: the real branch up to the service's refusal, and the shared create
  tail run through the `SYNTHETIC_TEST` create (4.4, E23).

**R1's root fixture** (conformance R2-L2 (i); technical TR2-L3 (a)). Every lease is on a registered root:
the lease table references the root-link table, as F2's references `gw_root` (`guarded_workspace_v1.sql:33`),
and a registered root needs a portfolio row by COMMIT, through a deferred foreign key like F2's
`gw_root_portfolio_fkey` (`:27`). Only `rw_admit(new_root = true)` under `EXECUTE_CREATE` registers a root
(2.6 item 4), and R1 has no create, fence or seal. So R1's tests start from a **crafted (E11) fixture**: in a
disposable `TEST` database the owner role writes one `app_user`, one `portfolio` row and one root-link row in
a single transaction. It is labelled in the test as a crafted fixture and is never product evidence. It
keeps working when R3 adds the fence: the fixture helper disables user triggers on those tables for its own
inserts and enables them again (the `ALTER TABLE ... DISABLE TRIGGER` statement that 2.6 item 5 uses; R3
must show it works), so R3 extends this one helper and no R1 test is reopened. Not run.

Admission and lapse (R1):

- admit before `valid_until` succeeds; at or after it is refused, for each of the four purposes;
- the lease records the sampled instant, the `valid_until` used and `complete_by`, and
  `complete_by = LEAST(admitted_at + W, valid_until)`; a crafted lease row with a later `complete_by` is
  refused by the table check; a lease admitted within `W` of `valid_until` gets `complete_by = valid_until`;
- clock regression is refused. The test moves a stored instant ahead in a disposable database;
- overlapping admissions do not refuse each other as a regression (technical re-review L-2): two
  connections admit in a tight loop for a few seconds with the real clock, and none is refused as a
  regression; the test fails if `latest` is read after the sample;
- a forward jump has no hook and cannot be injected; its policy (fails closed) is covered by the lapse
  test, and an outage by T09's database-unavailable case;
- renewal without a decision reference, or by the executor or loader role, is refused; a valid
  renewal restores admission and a root bound to the original context (the crafted fixture above) still
  resolves to it; an equal `valid_until` restores the rights after a withdrawal without extending the lease
  (E25). **Date correction** (E25, amended; conformance R3C-M1; technical TR3-M4): a renewal with a
  `valid_until` earlier than the current one but later than the clock, with a decision reference and fresh
  entries, is accepted; the head's `valid_until` is the new one, both generations stay in the history, the
  tool prints the "moved earlier" line, admission at or after the new date is refused, and a lease admitted
  after the correction has `complete_by <= ` the new `valid_until`; the same renewal with a `valid_until`
  at or before the clock, without a reference, without the entries, or later than the earliest
  `term_end_not_after` of its own entries, is refused; a correction started while a read lease is in flight
  waits for it (head exclusive) and, if its `lock_timeout` expires, appends nothing and exits with a status
  of its own; a root bound to the original context still resolves after it. A fixture on invented data
  walks the pin scenario: publish with `valid_until` V and bound U (V <= U), then correct to V' < V with
  entries whose `term_end_not_after` is U' >= V'; the old V no longer admits. A second fixture walks the pin
  that shows a term already over with no notice given (conformance R3R-L2): a renewal at the equal date whose
  entry carries the Renewal Term's end as `term_end_not_after` is accepted, the context stays live, and no
  withdrawal is made.

The bound under the cap (the tests use the real clock, `valid_until` a few seconds ahead, and a test
install with `W` of a few seconds; there is no clock hook):

- an operation that finishes before its `complete_by` completes (the positive control). An operation
  admitted before `valid_until` and paused past `valid_until` is refused at its next checked statement
  **even when `admitted_at + W` is later**, because the cap decides the deadline; a new admission after
  `valid_until` is refused. Both orders of the `LEAST` are tested: `W` shorter than the time left (the
  deadline is `admitted_at + W`) and `W` longer (the deadline is `valid_until`). The pause point is: before
  the COMMIT (**R1**, read-only phase); before the guarded load (**R2**); before the seal (**R3**, crafted
  bundle; **R5**, through the shared create tail on the `SYNTHETIC_TEST` create);
- an operation paused to or past `complete_by` is refused, and rolls back wholly, at the first statement it
  then issues that a check covers:
  - **R1**: a read-phase lease paused after its last statement and past `complete_by` is refused **at
    COMMIT** by the deadline guard (no value is delivered, no lease row remains);
  - **R2**: refused at its guarded load;
  - **R3 (E11)**: refused at its next economic write and at the seal; one paused between the seal and the
    COMMIT, with the bundle guard and the other deferrable constraints fired by name, is refused at COMMIT
    by the deadline guard;
  - **R5**: the same on the **shared create tail** (E23), run through the `SYNTHETIC_TEST` create, which
    is the only create that can reach a COMMIT before R8 (4.4; the real branch's create is refused by
    the service first). It uses the tail's own pre-commit seam (a private injection point like F2's
    `_after_commit_ack`, `guarded_workspace_store.py:278-281`, or `_before_commit`,
    `guarded_csv_report_store.py:152`). The refusal is classified a definite refusal (`RW_DEADLINE`,
    connection `IDLE`), not UNKNOWN; no economic row, lease or operation row remains. A connection killed
    at the seam is classified UNKNOWN. This shows the tail on product code with an accepted commit; it
    does **not** show the real branch's own commit (4.4, item 11);
  - in all of these the session sets `statement_timeout`, `idle_in_transaction_session_timeout` (and
    `transaction_timeout` where it exists) to 0, to show that the connection's own timeouts are not the bound;
- **the read bound** (**R3**, on a crafted committed root, E11; technical TR3R-L4): with a read-phase lease
  whose transaction is kept open past `complete_by` (the session sets its timeouts to 0), a `SELECT` of the
  root's ledger rows returns no row and the archive read refuses; the same statements before `complete_by`
  return the rows and the archive (the positive control). The product path of the same bound is T-g (4.4).
  The stored market data has its own tests, next;
- **the `md_*` read functions** (**R3**; PD-0069; this replaces the characterisation test of the old limit).
  They run in a `TEST` install on the rows of an invented release that the loader role's `write_release` (R2;
  technical TR5R observation: the guarded load reads the registry and writes no `md_*` row), or the owner role
  as a crafted fixture (E11), wrote, and each result is marked "E11 crafted probe, not product evidence".
  *Positive control:* with an open `EXECUTE_CREATE` lease and with a read-phase `EXECUTE_REPRODUCE` lease of a
  context whose snapshot names the release, each function returns that release's rows. *Refused, each with the
  function's code and no row returned:*
  - no lease; a lease of `ARCHIVE_READ`, and one of `ARCHIVE_EXPORT`; a release id that is not the snapshot's
    (another release, an unreferenced candidate);
  - **after `complete_by`**: a lease whose transaction is kept open past it (the session sets its timeouts to
    0), is refused at its next call, with `W` shorter than the time left and with `W` longer (both orders of
    the `LEAST`);
  - **after a lapse**: a new admission at or after `valid_until` is refused, so there is no lease to call
    from, and a lease admitted just before `valid_until` is refused at `valid_until` at the latest;
  - **during a pending drain mark**: a new admission is refused with `RW_WITHDRAWAL_PENDING`, so a call from
    that connection has no lease and is refused; a lease admitted before the mark still reads until its own
    `complete_by` (the positive side of "withdrawal does not cancel admitted work", 3.1) and is refused after
    it;
  - **after a completed withdrawal**: as for the pending mark, and a renewal restores the reads of a new
    lease;
  - **the executor has no direct SELECT on any `md_*` table**: for each of the thirteen, a `SELECT` is refused
    with `42501`, with a lease and without one, and the catalog audit finds no privilege of the executor or of
    `public` on any of them, column-level included (1.2 rule 5.3 (e) (iii));
  - a temporary table named like an `md_*` table in the executor's session changes nothing a function returns
    (the sibling of the shadow probe at `test_postgres_cp2_fix_round.py:86-102`);
  - the thirteen functions match the `md_*` tables of the schema, and `EXECUTE` on them is held by the executor
    only. R5 adds the test of `read_release` through the functions (4.4, T-m);
- the deadline guard is its own trigger and the named form works (**R1**; fact 17 marks it "R1 must
  show"). The constraint named is the **root-link-to-portfolio foreign key**, new in R1 with the
  root-link table and deferrable and initially deferred like F2's `gw_root_portfolio_fkey` (`:27`)
  (conformance R2-L2 (ii); technical TR2-L3 (b)). The lease-to-root-link key is `NOT DEFERRABLE` (F2:
  `:33`), and the manual says every name given to `SET CONSTRAINTS` "must all be deferrable"
  (`sql-set-constraints`), so it is not named. The root-link key has a pending event only when the same
  transaction writes a root-link row, so the test uses the crafted fixture path: in one transaction the
  owner role writes the root-link row (and portfolio row) of a second crafted root and calls the
  read-phase admit on the first. `SET CONSTRAINTS <that key> IMMEDIATE` then fires that event only and
  leaves the deadline guard pending, which fires at COMMIT (a stall past `complete_by` makes the COMMIT
  fail with `RW_DEADLINE`); naming the guard fires it at once. A catalog test asserts that the guard's
  name appears once among the schema's constraints (fact 17: `SET CONSTRAINTS` acts on all matches);
- a characterisation test records the limit of the COMMIT-time check (**R1**): a session that fires the
  guard early (`SET CONSTRAINTS ALL IMMEDIATE`, or by name) and then stalls past `complete_by` is **not**
  refused at COMMIT by that trigger. The test documents the residual (section 9); it is not a
  requirement;
- the shared create tail never fires the guard early (**R5**, through the `SYNTHETIC_TEST` create): a
  statement recorder on the connection shows that it issues no `SET CONSTRAINTS ALL` in any mode and
  never names the deadline guard; every `SET CONSTRAINTS` it issues names a constraint of the allowed
  inventory; the inventory check refuses an unknown deferrable constraint (the F2 pattern,
  `guarded_workspace_context.py:79-102`). **The recorder must not pass vacuously** (technical TR2-M1): the
  test asserts that it saw at least one named `SET CONSTRAINTS`, and fails if it saw none. A static source
  audit shows that neither branch's create contains its own `COMMIT`, `SET CONSTRAINTS` or outcome
  classification, so the function under test is the function the real branch will run. The audit also
  lists the `SET CONSTRAINTS ALL` sites that exist at HEAD (`guarded_workspace_store.py:250`,
  `web_workspace_store.py:335`, `guarded_csv_report_store.py:279` and `web_csv_store.py:214`, which is `ALL
  DEFERRED`; a grep of `src/`) and shows that the real create path reaches none of them (technical round-2
  observation);
- **the same for the read, reproduce and list paths** (**R5**; technical TR3-L7). The deadline
  guard bounds a read, a reproduce or a list entry only if the guard is still pending at its COMMIT, and the
  value is returned only after that COMMIT (F2's `_read_operation` returns after the transaction block,
  `guarded_workspace_store.py:321-329`). A shared helper that issues `SET CONSTRAINTS ALL IMMEDIATE` would
  consume the guard and no create test would notice: HEAD's `web_workspace_store.py:334-335` does exactly
  that when it has no execution scope. So these paths get the same three protections as the create:
  (i) **one shared read tail** (E23, extended): admit, read under the held locks, leave the guard pending,
  COMMIT, return the value only after the COMMIT succeeded, classify a COMMIT-time error as the create tail
  does; read, reproduce and each list entry's per-root read all call it, for both branches; (ii) the static
  audit lists the same `SET CONSTRAINTS ALL` sites and shows that **none of these paths reaches any of
  them**, and that none contains its own `COMMIT` or `SET CONSTRAINTS`; (iii) a **non-vacuous recorder** on
  each path: it must record the path's own admit and load statements (the test fails if it saw none, so a
  recorder wired to the wrong connection cannot pass), and records **zero** `SET CONSTRAINTS` of any form. And
  the stall test: a read, a reproduce and a list entry paused after the last statement and past
  `complete_by` are refused at COMMIT with `RW_DEADLINE`, and **no value is delivered** (the
  `SYNTHETIC_TEST` branch, on a root the test's own shared-tail create committed; the real branch's reads
  have no real root to read before R8, so its own reads are first run at R8, 4.4);
- the capped deadline claims only what it shows: no further checked statement of the operation (an economic
  write, the seal, a guarded load, a read of a rooted table, of the archive or of a stored market-data row
  through the functions of 2.6 item 6) succeeds at or
  after `valid_until`, and the pending guard refuses a COMMIT that starts at or after it (**R1** for reads,
  **R3** for writes on crafted bundles and for the `md_*` functions, **R5** for the shared tail). It is
  **not** tested, and not claimed,
  as "nothing commits after `valid_until`"; the two disclosed limits (the commit-processing gap and the
  guard-bypassing executor) have the characterisation test above.

Expiry evidence (E14; all **R1**, in a `TEST` install, with invented fixture references that test the
rule and not any real reading):

- `NONE` with no basis entry is refused at publish;
- `NONE` with a `NO_EXPIRY_READING` for some member sources but not all is refused, including when the
  omitted member is the one that carries a licence term;
- `NONE` with any `LEASE_TERM` or `NOT_ASSESSED` entry is refused;
- `NONE` with a `NO_EXPIRY_READING` for every member source is accepted;
- `LEASE` without a `LEASE_TERM` entry or without `valid_until` is refused;
- `LEASE` with a member source that has no entry is refused, and so is an entry that names a
  non-member (L-9);
- `LEASE` whose `valid_until` is later than the earliest `term_end_not_after` is refused, and an equal one
  is accepted; `W` plays no part in the test. The HG4 shape (one `LEASE_TERM`, two `NOT_ASSESSED`,
  `valid_until` earlier than the upper bound; this is a fixture shape and not a margin, R3C-L1) is
  accepted. The publish output and the status view print
  the upper-bound wording of the plausibility rule (3.1); a test compares the text and fails if it says or
  implies that the lease is "within" the term (conformance R2-M1);
- the publish command has no input that names lease-governed sources, and a publish whose members
  include a source with no entry cannot yield `NONE`;
- admit takes the member sources from the stored snapshot (L-8): a crafted history row in a disposable
  database with kind `NONE` and `NO_EXPIRY_READING` entries for only some of the snapshot's member
  sources is refused at admit, as is a stored kind that differs from the re-derived kind; `UNKNOWN` is
  never admitted.

Withdrawal and cancellation. **The in-flight work in the R1 items is a read-phase lease.** The
create-phase counterparts need an economic write or an in-flight create, so they are **R3 (E11, crafted
bundle)** and **R5 (the shared create tail through the `SYNTHETIC_TEST` create, E23; the real branch's
create stops at the service's refusal)**:

- **R1** withdrawal during an in-flight read lease: the drain mark commits first, with issuer, the
  decision-reference triple and the server time, and a new admission is refused at once with
  `RW_WITHDRAWAL_PENDING`; the withdrawal then waits and applies once the read ends, and its generation
  row names the mark;
- **R1** an expired `lock_timeout` (conformance re-review DC-M1; technical re-review M-4): read back
  from the database, the mark exists with issuer, triple and time, and no new generation exists; the
  status view lists it as pending; a new admission is refused with the pending code; the tool exits with
  a non-success status and prints "not yet effective for in-flight work; new admissions refused since
  `<time>`", never "done"; re-running after the read ends completes it, and the generation row names it;
- **R1** the mark's record: a mark without an issuer, without any one part of the triple, or with a
  malformed hash is refused; the executor, loader and publisher roles cannot insert, update or delete a
  mark directly; a renewal while a mark is pending is refused unless it names the mark, and naming it
  supersedes the mark, which stays readable;
- **R1** two connections admit read operations in an overlapping loop while a withdrawal runs: new
  admissions stop and the withdrawal completes or reports "not yet effective" (pending, as above). This
  is the check on the starvation reading (section 9);
- **R1** (read lease) and **R3** (crafted create-phase lease), a stalled worker past `complete_by`: the
  withdrawal names the blocking lease; the publisher role cannot terminate the backend; after the owner
  role ends it, the withdrawal proceeds and no economic rows or leaked lease remain;
- **R1** (read lease), **R3** and **R5** (create, R5 through the shared tail), an operation over its
  connection's statement timeout rolls back wholly and releases its locks, then withdrawal proceeds; a cancelled backend leaves no economic
  rows and no leaked lease.

### 3.3 What withdrawal and lapse do not cover

They stop the **database runtime**. These are not covered, and can still be read and exported after a
withdrawal or lapse:

- the raw files, the download tool and the legacy command-line tools (W01, W02, W12, including
  `real_slice.py` reading `FileStore`);
- **the purpose locks**: the legacy tools do not follow them (conformance re-review DC-L1). The database
  keeps four separate purposes (`ARCHIVE_READ`, `ARCHIVE_EXPORT`, `EXECUTE_CREATE`, `EXECUTE_REPRODUCE`;
  `guarded_workspace_v1.sql:38`). If the owner records a generation with export `false` and read `true`,
  the database refuses a database export, but `python -m performance_tools.evidence_pack real --out DIR`
  (`evidence_pack.py:4`, `:6`) still builds a pack from the admitted files on disk, and a pack holds "the
  inputs, the manifests" (`pack.py:3`), while the context is live. So a stored export right governs the
  database export path only, not the legacy command line or an OS copy, and the owner procedure below
  applies to an export-only change as well;
- the **staging store**, if R4b's plan makes one (6.4). It would hold copies of the selected payloads and
  manifests, so `FileStore(staging).index()` would still build from it;
- **the loader's reads, of the `md_*` tables and of the candidate registry** (PD-0069; technical TR4-M1 and
  TR5-M1, conformance R4C-L3). No lease reaches them, and **the owner decided that the loader's login is off
  between loads** (PD-0070 decision 1, "Off between loads (Recommended)"; the procedure is the last bullet
  below, the limits are in section 7). The executor's reads are no longer here: it reads the stored market
  data only through the lease-checked functions of 2.6 item 6, so a lapse and a withdrawal stop them. The
  loader writes the rows, which are append-only (W04), and has no lease: its `md_*` rows are written before
  any context exists (R8 step 2 comes before the publish), and under N2a's binding it also registers the
  context-bound candidates after the publish (the procedure below, item 1). Its writes (`INSERT`, the
  registry's put) need no lease either (conformance R5C observation) and fall under the same login-off.
  - *What loading needs, at HEAD* (`market_data_store.py`): `INSERT` on the thirteen `md_*` tables
    (`_insert_files` `:273-287`, `_insert_release_rows` `:289-402`); `SELECT` on `md_file`, because the insert
    is `ON CONFLICT (file_sha256) DO NOTHING RETURNING file_sha256` (`:279`; the manual, `sql-insert`: `ON
    CONFLICT` and `RETURNING` need `SELECT` on the columns they name) and a conflict re-reads the stored
    `manifest` (`:283`); and `SELECT` on `md_release`, for the idempotence check (`:460`, `:472`) **and for
    the sealed-release trigger** (technical TR5-L3). `md_require_open_release` has no `SECURITY DEFINER`
    (`0011_market_data_append_only_and_sealed_releases.sql:49-67`), so before every insert into the eleven
    child tables (`0011:73-90`, `0016_risk_free_kind.sql:74-77`) it runs `SELECT 1 FROM md_release r WHERE
    r.release_id = NEW.release_id AND r.append_xid = pg_current_xact_id()` (`0011:58-61`) with the inserting
    role's own privileges. It reads `md_release.release_id` and `md_release.append_xid`
    (`0009_market_data_files_and_releases.sql:49`). Whether the foreign-key
    checks of `md_release_file` need any further privilege is not shown; R2's test, which loads as the loader,
    shows whether the list suffices.
    `write_release` also calls `row_counts` (`:404-415`) at `:480`, and through `_already_projected` at
    `:488`, which counts the rows of the other eleven tables for the result's `row_counts` field. That
    read-back is not loading.
  - *What loading also uses: the candidate registry* (technical TR5-M1). The loader registers candidates
    through the generalised N2a registry (R2; 4.1), so its list holds `EXECUTE` on the registry's put and get
    functions. In the N2a handover (the files named in 4.1) both are granted to the loader
    (`synthetic_provenance_v1.sql:286`), N2a's own install check requires it (`synthetic_provenance_store.py:143`),
    and its register, load_context and reconcile calls use the get function (`:243`, `:263`, `:302`). R2
    generalises N2a's scope and its gateway coupling (4.1), and nothing in this design removes its payload
    table, so the real registry stores the raw payload bytes of each member (N2a: `np_payload`,
    `payload bytea NOT NULL`, `:2-8`). N2a's get function checks only the caller's role (`np_caller`,
    `:56-64`, `:246-249`) and returns `np_collect_context`, which aggregates `np_payload.payload` (`:160`)
    with the manifests, acquisition envelopes and witnesses. The registry code rebuilds the bundle from the
    returned bytes and re-validates it (`_loaded`, `synthetic_provenance_store.py:193-207`), so that
    read-back is how those calls work, not an extra. All of this is read from the N2a handover; the real
    registry does not exist before R2, and R2's test of what the get function returns shows it.
  - *The narrowing.* The loader's list is `INSERT` on the thirteen tables, `SELECT` on `md_file` and
    `md_release`, and `EXECUTE` on the registry's put and get functions, and nothing on the other eleven
    tables or any other function. R2 gives `write_release` one keyword-only parameter
    (prospective `count_rows: bool = True`) that skips the read-back; with the default the behaviour is
    today's, so its callers and the tests of `row_counts` (`test_postgres_market_data_store.py:196-210`,
    `test_postgres_risk_free.py:68`, `:200`) run as they do. The real loader passes `False`, and its
    `ProjectionResult.row_counts` is empty. The loader's list is fixed in R2, one list in the shared installer
    code, and the catalog audit compares the loader with it (1.2 rule 5.3 (e)). The list stays as round 5
    narrowed it (PD-0070 decision 1). The registry's get function is not narrowed: that would change N2a's
    contract, because its calls re-validate from the returned bytes (above), and the owner did not take that
    option.
  - *What the loader credential can read whenever its role can connect*, with no lease to check, after a
    lapse or a withdrawal too, **under the list above**:
    1. every row of `md_file` (file manifests: hash, size, file name and format, source,
       kind, retrieval time, retrieved-by, declared adjustment, usage scope, market, the request whitelist,
       source identifiers, script names and hash, libraries, coverage; the field list of `FileManifest`,
       `manifest.py:82-110`) and every row of `md_release` (the release definition: name, file hashes, source
       precedence, conventions, created-for, convention set, from `MarketDataRelease`, `manifest.py:378-390`;
       with the projection digest, `contains_synthetic` and `append_xid`). I did not read the stored bytes of
       any manifest;
    2. **through the registry's get function, the raw payload bytes of every registered context, which are
       the files themselves. For the HG4 context these are the Alpha Vantage closes in `AAPL_compact.csv`,
       the OpenFIGI file and the NYSE calendar file, with their manifests, acquisition envelopes and
       witnesses.** The caller supplies a context digest or a registration's operation id; the design does
       not treat a digest as a secret (the proposal files carry digests, 2.3). **The prices are therefore
       readable by this credential, in the registry and not in `md_quote`.**
    Under the list above the loader reads no `md_quote` row or other observation row of the other eleven
    tables. A read-back of the quotes' counts, which would give it `SELECT` on them, was not offered to the
    owner and the list does not include it (PD-0070).
  - *The owner's decision and procedure* (PD-0070 decision 1, "Off between loads (Recommended)"; no new
    mechanism). The loader role is `NOLOGIN` between loads. Each step below is an owner act, run in the owner's
    own terminal as the superuser (`ALTER ROLE ... NOLOGIN` or `ALTER ROLE ... LOGIN`, `sql-alterrole`). No
    tool runs, records or enforces it (E29 only prints the loader's login state: 1.2 rule 5.3 (g)), and no
    agent session holds the superuser password (1.2 rule 2).
    1. *Where the loader's last use falls in R8* (conformance R6C-M1). Step (2), the real qualification run,
       uses the loader for the `md_*` rows (R4b; W04; E17) and to register the unbound candidates through the
       registry (2.3 item 1). **That is not its last use under N2a's binding**, which 4.1 re-targets to the real
       gateway's objects and does not drop. In N2a a registration is bound to a financial context:
       `np_context.financial_context_sha256` is a foreign key to `gw_snapshot(context_id)`
       (`synthetic_provenance_v1.sql:27`), a violation is raised as `NP_INPUT_MISSING` (`:244`), and the
       executor's guarded load refuses unless the registration's financial context equals the lease's context
       (`np_load_context`, `:258-261`; `load_guarded`, `synthetic_provenance_store.py:283`, `NP_CONTEXT_DIFFERS`;
       a digest with no registration returns no row and `NP_INPUT_MISSING`, `:194-195`). So the loader registers
       the context-bound bundle **after the publish**, once the snapshot row exists. N2a's own test does so: it
       publishes (`test_postgres_synthetic_provenance.py:149`), registers the bound fixture through `save`, which
       calls the loader-connected store's `register` (`:37-40`; the store, `:31-32`), and then runs the
       guarded load (`:166`). N2b (`test_postgres_synthetic_provenance_link.py:35-51`) and N3
       (`test_postgres_synthetic_provenance_link_n3.py:180-192`) follow the same order: register, `load_context`
       as the loader, `gw_publish`, register the bound bundle as the loader. In N2a `register`,
       `load_context` and `reconcile` require the loader role (`synthetic_provenance_store.py:238`, `:261`,
       `:300`) and the runtime read, `load_guarded`, the executor role (`:279`).
       **Under that binding the loader's last use in R8 falls between the publish (4) and the real run (5)**:
       the registration of the context-bound candidates. **The owner sets the loader `NOLOGIN` right after it:
       step (4a) of R8 (7.1).** If the real registry binds otherwise, the last use is the end of step (2) and
       the step follows it. The real registry does not exist before R2: R2's exit states which holds (7.1), and
       R6's plan states the sequence for the owner's approval. The design names no tool that writes the
       registration after the publish; R2's exit states how the real registry binds, and R4b's or R6's plan
       names the tool. I add none here. Two sequences keep to PD-0070's procedure under the binding, and R6's
       plan chooses between them. *One window:* the loader keeps `LOGIN` from step (2) to (4a), so the window
       spans the owner's review at (3) and the publish at (4). *Two windows:* the owner sets `NOLOGIN` right
       after (2), sets `LOGIN` again before the registration, and sets `NOLOGIN` right after it (two more
       owner acts). In the one window the loader can read what its list allows, the payload bytes included, for
       the whole span; in the two windows it cannot between the first `NOLOGIN` and the second `LOGIN`. The
       context is live in the second window, and in the later part of the one window. The HG4 package records
       the sequence that was followed.
    2. *Later loads.* For any later load the owner sets `LOGIN`, the load runs, and the owner sets `NOLOGIN`
       again. That includes a re-run of step (2), once the loader is `NOLOGIN` again, that the review at (3) or
       the publish at (4) calls for (an edited export is a new candidate, 2.3 item 5), and a load for a later
       context (7.3).
    3. *Before the first load: how Phase 1 creates the loader* (conformance R6C-L1; technical TR6-L1).
       Whether Phase 1 creates the loader role with `LOGIN` or with `NOLOGIN` is decided neither by PD-0070
       nor here: R6's plan states it (7.1), **after R2's exit states what the real registry's checks need.**
       N2a's install function requires the loader to have `LOGIN` and refuses with `NP_INSTALL_REFUSED`
       otherwise (`synthetic_provenance_store.py:112-116`: `for role, login in ((loader_role, True),
       (executor_role, True))`), and each of its calls refuses a caller whose role cannot log in (`np_caller`,
       `synthetic_provenance_v1.sql:62`, called at `:202` and `:249`). The N2a runtime script I read creates every
       role but the owner with `LOGIN` (`n2a-runtime/runtime_n2a_reviewed_v3.py:123`), so nothing in N2a's
       evidence shows the install with a loader that cannot log in. If R2 keeps these checks and R6's plan picks `NOLOGIN` at creation, the registry
       install in Phase 1 refuses at R8 step 1 and leaves a partial install (1.2 rule 7). So under `NOLOGIN`
       at creation, either R2's install check accepts a loader that cannot log in, or Phase 1 installs the
       registry before the role is made `NOLOGIN` (an ordering inside the installer, which R6's plan would
       have to design, and an installer act where PD-0070 names an owner act). Under `LOGIN` at creation the
       owner's first `NOLOGIN` is the step of item 1. While the loader is `NOLOGIN`, the checks of 5.3 (a), (b)
       and (d) and the verifier check of (e), which are keyed to LOGIN roles, do not cover it, in Phase 2 or
       at a gated start (5.3 (g)). The first load window runs from the moment the loader can log in (at
       creation, or by the owner's `LOGIN` if Phase 1 creates it `NOLOGIN`) to the owner's first `NOLOGIN` of
       item 1. The `md_*` tables and the registry hold nothing until step (2) (1.2 rule 7), so the loader has
       nothing to read before it.
    4. *Effect.* Between loads no new connection as the loader succeeds ("Only roles that have the LOGIN
       attribute can be used as the initial role name for a database connection", `role-attributes`), whether
       the context is live, has lapsed or was withdrawn. **Outside a load window the owner opens, nobody can
       log in as the loader, whoever holds its credential** (conformance R5R-L1; 1.2 rule 4).
    5. *During a load window the owner opens,* the loader can read what its narrowed list allows (the two
       reads listed above), the payload bytes through the registry's get function included, the Alpha Vantage
       closes among them, whether the context is live, lapsed or withdrawn. The holder is whoever R6's plan names, and an
       agent session may be named (rule 4). This is part of the procedure; it does not count as an accepted
       limit beyond the owner's own opening of the window (PD-0070).
    6. *Limits, as shown to the owner and accepted with the choice* (PD-0070 decision 1):
       - It stops new connections only. Whether `NOLOGIN` ends a session that is already open is not shown.
       - The superuser and the owner role are not affected.
       - Each later load needs the owner's `LOGIN` step.

       Section 7 lists the same three, and the HG4 package takes them (7.1, R8).
    7. *Not taken:* accepting the reads as a limit; `NOLOGIN` at a withdrawal only, which does nothing at a
       lapse; narrowing the list further, with a digest-only registry call. PD-0070 records the option texts.
- the proposal files that R4b writes.

The owner procedure on withdrawal (PD-0066 decision 9): move the raw files aside and do not run the legacy
tools. One addition follows from any staging store. It is my proposal, **not decided**: move a staging store
aside as well. The `NOLOGIN` step that an earlier round proposed for the executor is dropped (PD-0069: the
lease-checked functions stop its reads). The loader's `NOLOGIN` is a different step, taken after its last use
in R8 (step (4a) under N2a's binding, item 1 above) and not at a withdrawal.
A re-read cadence is not proposed, and a reminder must not become an automatic expiry. The lapse is the
fail-closed backstop for the four purposes and for the executor's reads of the stored market data, not for the
raw files, a staging store or the proposal files; the loader's reads are closed between loads by the owner's
`NOLOGIN` step and not by the lapse. The HG4 package takes this list (7.1, R8).

Not claimed: a provider changing its terms before the application learns of it (E10 section 5); that
the terms reading is current after 2026-10-24.

Files affected: `real_workspace_v1.sql` (`valid_until`, expiry basis entries, drain mark, `complete_by`,
the deadline guard, the fence and row policy of 2.6, decision reference, issuer, clock);
`real_workspace_store.py`; tests T07.

## 4. D4: the five parked patches and the pre-real test path

**Decided** (PD-0066 decisions 6 and 8). Locations: `reviews/CP7_EXIT_INVENTORY.md` section 3. CSV R1
is already merged (`df5b43b`, PD-0062) and is not part of this table.

### 4.1 The patches

N2a hard-codes the fictional scope (`reviews/OVERNIGHT_EXECUTION_2026-10-20/n2a-handover/source-a2/src/persistence/synthetic_provenance_v1.sql`
`:86, :93, :135, :185`), and its guarded load `np_guard` reads `gw_mode`, `gw_lease`, `gw_head`,
`gw_root`, `gw_rights_valid` (`:178-195`). N2b subclasses `GuardedWorkspaceStore`
(`n2b-handover/source-a2/src/persistence/synthetic_provenance_link_store.py:130`). So "generalise"
includes re-targeting this coupling to the real gateway's objects, which exist only after R1.

| Patch | Fate | What it becomes |
|---|---|---|
| **N2a** candidate registry | **Generalise** the scope and the gateway coupling; re-target to the real gateway's objects. **Built in R2**, on the scope core that R1 builds | One parameterised provenance module (4.2). The real scope refuses `v2`/agent members and mixing with other scopes. N2a's own tests become the `SYNTHETIC_TEST` regression. **The loader's list names the registry's put and get functions, and the get function returns the payload bytes to the loader; the owner did not take the narrower option, and the loader's login is off between loads (3.3; PD-0070 decision 1; technical TR5-M1)** |
| **N2b** link to the financial service | **Generalise**. The seal, archive and link objects are built in **R3**; the world builder and the service call in **R5** | A real world builder: registry, resolver, port, calendars, conventions and policy are built **from the locked snapshot**, then the real service is called. Subclass target is the real store |
| **N3** concurrency and restart tests | **Re-target after N2b**, so after R5 | New real tests derived from `reviews/OVERNIGHT_EXECUTION_2026-10-20/n3-handover/source-a2/tests/product/test_postgres_synthetic_provenance_link_n3.py`. Its probe script under `reviews/` stays as evidence only |
| **PD-0059** required provenance | **Retire the three F2 edits** (decision 6). Keep the obligation design: policy row, row guard, bundle guard | They become the real seal's design (R3). No `guarded_workspace_*` file is touched |
| **PD-0060** write-refusal test | **Defer; reuse the pattern** | The all-writer matrix T03 in the real database (R3) |

### 4.2 The pre-real test path: option (a)

**Rule.** Invented data is **never** marked `synthetic = false`. The first `synthetic = false` record
is reserved for the real run (R8); this keeps FF1-C08 and E9-F01.

**One module, three scopes.** One parameterised product module holds every scope, so all of them
share identical rules and cannot be mixed. A scope is a pair **(branch, origin axis)** **[E7]**:

| Scope | Branch | Origin axis | Where it can exist |
|---|---|---|---|
| `SYNTHETIC_TEST` | fictional (F2-equivalent) | synthetic | TEST installs |
| `TEST_SWITCH` | **real** | **synthetic** | TEST installs only |
| `REAL` | real | real | REAL installs only |

Identifiers are fixed in R1's plan, because R1 builds the scope core (below).

- **Branch** selects the structure: envelope and snapshot shape, lease, admit, X1, journal, seal,
  archive.
- **Origin axis** selects the checks that tie data to a real origin **and the origin labels** (1.1)
  **[E16]**. Labels follow the axis, not the branch: a `TEST_SWITCH` root runs the real branch and
  carries synthetic labels.
- **The origin predicates** are separate functions of the scope and of their own inputs, with no
  writes **[E15]**:
  - O1, a source must **not** be synthetic;
  - O2, a permitting human terms check. In the real scope O2 reads the source's `terms_check`
    directly. It does **not** use `terms_attested` (`manifest.py:281-284`), which is true for any
    synthetic source;
  - O3, the member's acquirer is `human` and its usage scope is `INTERNAL_DEVELOPMENT_ONLY`. In the real
    scope O3 reads the member's own fields. It does not reuse ingest's tie of a file's usage scope to
    its source's synthetic flag (`ingest.py:266-267`);
  - O4, the service result is `synthetic = false` (O4a) with F8B dry run (O4b). O4 is a **seal**
    predicate: it checks the result the service issued, not a candidate;
  - O5, the member has a valid **sidecar acquisition record** (6.1): present, schema-valid, its payload
    and manifest digests equal the member's, its approver role is the designated human product owner,
    and its decision-reference triple is present. The explicit legacy null of the E10 provenance slot is
    accepted under the two test scopes and **refused in the `REAL` scope** (technical re-review L-7). The
    sidecar schema and reader are built in R4b, so O5 is built there.
- **Candidate validation evaluates O1 to O3, and O5 once R4b adds it, independently and reports every
  predicate that fails.** It does not stop at the first. `ingest_file` stops at its first failure
  (`ingest.py:266-274`: the synthetic tie, then the terms gate); the validator is a different function
  and does not call it. Publish evaluates the same list plus the install-kind check and reports them
  together.
- **Invariants.**
  - I1, under `SYNTHETIC_TEST` and `TEST_SWITCH` every source, member, lineage, result **and origin
    label** is synthetic: `synthetic = true`, `market_origin = SYNTHETIC_TEST`. No `REAL_SOURCE` string
    appears in a stored row or an output of a test scope;
  - I2, synthetic and real origins never mix in one snapshot (Ruling 4.8 items 1 and 2; auditability,
    P9). P8 does not govern this axis (`reviews/TECH_REVIEW.md` :13830-13844, finding 4). `TEST_SWITCH` is
    not a mixture: it is the real branch on the synthetic axis throughout;
  - I3, a `TEST_SWITCH` output is never labelled `synthetic = false` or with a real-origin label. A
    consumer takes both from the stored row; none hard-codes either (R3's label test).

**Where the scope machinery is built.**

| Piece | Built in | Why there |
|---|---|---|
| Scope definitions, the factory, the reviewed switch, the install kind and its guard at publish and admit | **R1** | R1's tests must use snapshots of both test scopes made by product code. A snapshot made by a test helper would test a path the product cannot reach |
| Authority core: snapshot, history, head, drain mark, lease, admit, X1, the deadline guard, the proposal format with its writer and verifier | **R1** | It is branch-independent: admit tests rights and clock, not the branch. So R1 needs no branch-specific seal, and its tests run on snapshots of both test scopes. The proposal format is needed by R1's publish and conformed to by R4b |
| O1 to O3 candidate validators, the generalised N2a module, the guarded load | **R2** | They need R1's objects and scope core |
| The seal **for both branches** (the real branch's acceptance predicates, with O4 and the origin-label row guard; and the fictional branch's acceptance and validation, an F2-equivalent **fork** of `gw_check_artifact` and `gw_validate`, never an edit of an F2 file, in the **TEST-only SQL part** that the real installer does not run: section 1 item 1), the write fence and row policy of 2.6, journal, archive, the S2 tables, the mandatory link, the bundle guard, **and the thirteen lease-checked `md_*` read functions of 2.6 item 6 (PD-0069)**. **Validation and storage of both branches read and write `rw_root` and `rw_revision`, never `web_saved_sandbox` or `web_portfolio_revision`.** The table-grant and function-grant list of **each runtime role** (the executor's, built here; the loader's, fixed in R2; the publisher's, R1) is one list in the shared installer code, used by the TEST provisioner and the real installer alike, together with one statement that revokes PUBLIC's `EXECUTE` on every function of the schema (the HEAD migrations leave that default on twelve functions; 1.2 rule 5.3 (e), technical TR5-L2). **After R3 no increment adds gateway SQL** (technical TR3-L6): a later gateway change reopens R3's review and re-runs the catalog audit (R3's function, run by R6's installer) | **R3** | They need no service call. F2's checks read `web_saved_sandbox` and `web_portfolio_revision` (`guarded_workspace_v1.sql:256-257, :297, :300, :362, :368`), on which the real executor has no privilege (section 1 item 5). A fork that kept those reads would force a grant on `web_saved_sandbox` in the TEST install and make T03's catalog audit pass on a role plan that is not REAL's; R3's tests assert, on the file and grant lists that the shared installer code returns for each kind (a REAL install exists only at R8, so no test can read a REAL catalog before it), that **for every runtime role (executor, loader, publisher; technical TR4R-M2)** the two kinds' table-grant lists are identical, that neither kind's executor list includes any `md_*` table, `web_saved_sandbox`, `web_portfolio_revision` or `web_csv_*`, that REAL's file list omits the TEST-only part, and that REAL's function-grant list differs from TEST's by that part's functions only. R3 also builds the catalog audit as a function and shows on a TEST install that it passes as `TEST` and reports the part's functions as `REAL`; the installer's Phase 2 runs it on the REAL catalog (1.2 rule 5.3 (e); section 1 item 1) |
| The sidecar schema and reader, and the O5 validator | **R4b** | The sidecar is an input of qualification and of publish (6.1) |
| World builder, service call, create, read, reproduce and list, the scoped contract module | **R5** | They need R4b's release and R3's seal |
| **The shared create tail, the shared read tail and the `SYNTHETIC_TEST` create (E23).** The create tail is one function: by-name firing of the deferrable constraints from the inventory, the inventory check, the pre-commit seam, COMMIT, classification of a COMMIT-time error, and the read-only reconciliation. The **read tail** is one function: admit, read under the held locks, leave the guard pending, COMMIT, return the value only after the COMMIT, classify a COMMIT-time error (3.2). Both branches' creates call the create tail, and both branches' read, reproduce and list code call the read tail. The `SYNTHETIC_TEST` create is the fictional branch's world builder and service call: **Python in R5 that calls the existing fictional integration** (`financial_service_integration.py` pins `synthetic is True`, fact 12) **unchanged**, stores through the S2 tables, and seals and validates through R3's fictional-branch functions. It adds no gateway SQL | **R5** | The real branch's create cannot reach a COMMIT before R8 (the service refuses invented data, fact 12). The `SYNTHETIC_TEST` create can: its fictional service accepts, with synthetic-labelled invented rows in a `TEST` install. So the tails run on product code with an accepted commit before R8 (4.4). **Not verified:** that the existing fictional integration runs over the S2 tables without an edit; I read only the lines of fact 12. R5's first task checks it. If it cannot run unchanged, R5 writes a thin adapter in new code, still without gateway SQL and without editing a protected file; if no accepted synthetic result can be had that way, E23's proof does not exist and 8.1 item 11 widens to the whole tail, which the PM must put to the owner |

**The test-only switch.** The switch is the only way to reach `TEST_SWITCH`. It is a reviewed,
explicit argument of the scope factory; no environment variable, command-line flag or HTTP field
reaches it, and the real-mode launcher has no code path that passes it (R7 checks that on the launcher
module).

- It is **refused outside a test schema**: the factory reads the install kind of the connected
  database, written once by the installer **[E6]**, and raises unless it is `TEST`. A `REAL` install
  refuses `SYNTHETIC_TEST` and `TEST_SWITCH` snapshots at publish and admit. A `TEST` install refuses
  `REAL` snapshots at publish and admit, so real content never enters a test database.
- The predicates O1 to O5 do not read the install kind, so a negative test calls them in a `TEST`
  install and the install-kind guard cannot mask the code under test.
- The marker is a convention plus a refuse-on-mismatch check, not proof against someone who owns the
  database.

**Separate tests for the checks the switch bypasses.** The switch bypasses five checks (O1 to O5). Each
gets its own test, written without marking invented data `synthetic = false`. A test builds an
invented candidate, varies **only the input of the predicate under test**, and asserts that the
predicate's code is in the full failure list. Where a control is possible, a second case differing only
in that input asserts the code is absent.

**The controls are in-memory validator inputs only** (technical re-review L-4). An invented permitting
terms check (O2), an invented human acquisition for internal development (O3) and an invented sidecar
(O5) are invented human attestations. They are built inside the test, passed as arguments, and **never
written** as a manifest file, a candidate row, a sidecar file or a snapshot, in any scope: stored in a
database they would differ from a real acquisition only by the source's synthetic flag. The R2 and R4b
contract tests assert that the validator functions take such inputs by value and write nothing.

| Predicate | Failing case (code must be listed) | Control (code must be absent) |
|---|---|---|
| O1 | a `synthetic = true` source | none before R8: the passing side needs a `synthetic = false` source, which first exists at R8 |
| O2 | a synthetic source with no terms check, or a negative one (O1 is listed too) | the same source with a permitting terms check (O1 still listed) |
| O3 | a member with acquirer `agent`, a v2 manifest, or a usage scope other than `INTERNAL_DEVELOPMENT_ONLY` | a member with acquirer `human` and `INTERNAL_DEVELOPMENT_ONLY` (the fixture says it is invented) |
| O4 | a crafted result with `synthetic = true` (O4a); an F8B mode that is not a dry run (O4b) | none before R8, for the same reason as O1 |
| O5 (R4b) | in the `REAL` scope: a member with the legacy null slot, a sidecar whose payload or manifest digest differs, whose approver role is not the owner's, or whose decision triple is missing | a member with an in-memory sidecar that is valid in every respect (the fixture says it is invented), in the `REAL` scope with synthetic sources, so O1 and O2 are still listed |

Further tests: a `TEST_SWITCH` stored root and output carry `synthetic = true` and synthetic origin
labels, and no real-origin string (I1, I3); the switch factory raises outside a `TEST` install. The
switch is a separate item in **R1's** independent review. A test passes only if it sees the specific
code, so a regression that removes O2, O3 or O5 fails a test before R8, and the passing side of O1 and
O4 is first exercised by the real records at R8.

**The install-kind guard in both directions, and how each test is built without a real label on invented
data** (technical re-review L-3). The guard is tested at publish and at admit, in each direction:

- *A `TEST` install refuses a `REAL`-scope snapshot.*
  - At publish: the test builds an **in-memory** snapshot whose scope field alone is `REAL`, with
    synthetic sources and synthetic origin labels and no `REAL_SOURCE` string anywhere. Publish refuses
    it with the install-kind code. **Which codes the test asserts grows with the increments** (conformance
    R2-L2 (iii); technical TR2-L3 (c)): R1 builds publish and the install-kind guard and asserts the
    install-kind code only (and that publish refuses every `REAL`-scope snapshot until R2); R2 adds O1 to
    the listed codes when it wires the validators; R3 adds the origin-label mismatch when the seal's row
    guard exists. The product factory's real path is not used and nothing is stored.
  - At admit: an **E11 crafted row**. The owner role of a disposable `TEST` database writes a snapshot
    row of that same shape (scope field `REAL`, synthetic content and labels, no real-origin string), and
    admit refuses it. It is marked as a crafted probe, not product evidence, and it is invented data
    labelled synthetic.
- *A `REAL` install refuses a `SYNTHETIC_TEST` or `TEST_SWITCH` snapshot.* The test uses a disposable
  database whose install kind is written `REAL` and which receives no real content. The TEST provisioner
  cannot write `REAL` (1.2 rule 5.1), so the kind row is written by the owner role of the disposable
  database as an **E11 crafted fixture**. The factory refuses to make a test-scope snapshot there (it
  raises unless the install is `TEST`), so the snapshot is made in a `TEST` database and carried as bytes
  (a snapshot is content-addressed). Publish refuses the bytes; admit refuses a crafted row of the same
  bytes. That database is built by the TEST provisioner and so holds the TEST-only SQL part (section 1 item
  1): it shows the guard. It says nothing about what a real REAL install holds; that is shown by R3's list
  tests and R6's static test, and read from the REAL catalog by the installer's Phase 2, first at R8 step 1
  (section 1 item 1), not by this test.
- *These tests call the gateway's SQL functions (publish, admit) through a test connection. They do not
  use the real publisher tool or launcher.* Those tools decide REAL or TEST from the kind row and the
  database name together (1.2 rule 5.2) and would refuse a `REAL`-kind database whose name is outside the
  reserved prefix. A disposable database must not take the reserved prefix either, because the TEST
  provisioner and the environment-driven tests refuse a cluster or name in that namespace (1.2 rule 6).

### 4.3 What the test scopes may never be used for

The owner's database; any UAT or HG4 evidence; expected values of the real run; any statement about a
real source, price or licence; display in the product as real data. A UI shown over a `TEST` install
carries a visible "invented test data" mark, and the real-source sentences of 7.4 are not rendered
there.

One narrow case is **not** a use of a test scope: a **pure render test** may feed the claim-limit
renderer (7.4) an in-memory lineage fixture with `market_origin = REAL_SOURCE`. The fixture is built
inside the test, never stored, never served, never passed to a store or a route, and carries placeholder
slot values and no market number; the renderer is a pure function with no connection argument. The test
compares text against the template and displays nothing. It exists so that the P3 caveats are tested
before R8 (conformance re-review DC-M3).

**The fixture states its `synthetic` value** (conformance round-2 observation). `Lineage.is_synthetic` is
derived, not stored: it is true exactly when `usage_scope` is `SYNTHETIC_TEST` (`contracts.py:259-262`;
the `UsageScope` members are `INTERNAL_DEVELOPMENT_ONLY`, `SYNTHETIC_TEST` and `LICENSED_DISPLAY`, `:104-110`).
So the `REAL_SOURCE` render fixture sets `usage_scope` to a member other than `SYNTHETIC_TEST` and its
`is_synthetic` is false; the `SYNTHETIC_TEST` fixture sets `SYNTHETIC_TEST` and its `is_synthetic` is true;
and the test asserts both values before it renders. The field's default is `INTERNAL_DEVELOPMENT_ONLY`
(`contracts.py:227`), which is non-synthetic, so a `SYNTHETIC_TEST` fixture that omitted the scope would be
real-shaped without anyone having said so; the assertion catches it. That `is_synthetic` is false on this fixture does not make it a
stored record: nothing marks stored invented data `synthetic = false` (4.2).

### 4.4 Consequence of option (a), found while revising

The performance service refuses to value a portfolio from synthetic market data (fact 12). So on
`TEST_SWITCH` data the real branch's service step returns `SYNTHETIC_MARKET_DATA_REFUSED` and no
accepted NAV can exist. FF1-C08 forbids turning that refusal into an accepted result or
substituting a bare engine. I do not bypass or parameterise the service's refusal anywhere in
product code.

What runs **before** R8, by increment:

- **R1**: admission (X1), lease, locks, the completion bound and the deadline guard at COMMIT,
  withdrawal and the drain mark, on product code and invented data, on read-only-phase leases;
- **R3**: the fence and row policy of 2.6, the seal's acceptance predicates and the atomic commit,
  probed at SQL level in a `TEST` install with crafted, synthetic-labelled inputs. The lease-less and
  unregistered-root refusals are the real gateway's own enforcement and need no accepted NAV; the sealed
  bundle is crafted and is **not a product path [E11]**. **R3 has no create code and no commit-outcome
  code** (technical TR2-M1 (b)): it shows SQL-level facts only, for example that a crafted commit is
  durable and visible from a new connection after the client connection is dropped, and that a refused
  COMMIT leaves no row. It does not show a product behaviour such as "the product returns UNKNOWN";
- **R5, the real branch**: the staged root and ledger through the real create code, provenance link
  checks, journal, and the actual service call to its refusal, with **whole rollback and nothing
  addressable** (FF1-C08). Its create cannot reach a seal, a by-name firing or a COMMIT on invented data;
- **R5, the shared create tail** (E23), run through the `SYNTHETIC_TEST` create, which the real service's
  refusal does not stop: the by-name firing, the deadline guard refusing a stalled create at COMMIT, the
  classification of a COMMIT-time error, and the reconciliation code, on product code with an accepted
  commit (next subsection). These are **product-path tests of the shared tail**, labelled as that, and not
  of the real branch's own commit;
- the engine-level arithmetic fixtures that already exist.

What first runs at **R8**: service-accepted NAV, then the real branch's seal, commit, archive and
reproduce, against the Quant's independent oracle.

**The post-seal tail before R8** (technical TR2-M1; PD-0068 answer 2 does **not** cover this, and it is a
new question for the owner: 8.1 item 11). The round-2 text listed, as "product path before R8", a stalled
create refused at COMMIT (T07), the classification of a COMMIT-time refusal, a connection killed during the
COMMIT, a statement recorder showing that the create code never fires the guard early, and a reconciliation
run "against the committed state R3's crafted commit made". The review showed that none of them can run
as written:

- on `TEST_SWITCH` data the actual service refuses (fact 12) and the whole transaction rolls back before
  any seal; the seal's O4 needs `synthetic = false`, which this design forbids on invented data (4.2) and
  which FF1-C08 forbids anyone to bypass. So the real branch never reaches its by-name firing, its
  pre-commit seam or its COMMIT, and a statement recorder that sees no `SET CONSTRAINTS` at all would pass
  without testing anything;
- R3 has no commit-outcome code, and every run drops its disposable database (the runner's cleanup,
  `guarded_pg_runner.py` docstring, "Always, in `finally`: ... drops the database"), so no committed state
  of R3 is left for R5's reconciliation to read.

**Step 1: a pre-R8 product-path proof inside PD-0066 decision 8 [E23].** The tail is one shared function
(by-name firing from the inventory with its inventory check, the pre-commit seam, COMMIT, classification of
a COMMIT-time error, and the read-only reconciliation), and **both branches' creates call it**: the real
branch's create, and the `SYNTHETIC_TEST` create, which is the fictional branch of the one parameterised
module (decision 8: one module holds every scope so that they share identical rules). The `SYNTHETIC_TEST`
service accepts: F2's fictional integration pins `synthetic is True` throughout (fact 12), so a
`SYNTHETIC_TEST` create commits in a `TEST` install, with synthetic-labelled invented rows. Nothing is
marked `synthetic = false`, no refusal of the real service is bypassed or parameterised, and FF1-C08 is
untouched. A static source audit shows that neither branch's create has its own `COMMIT`, `SET CONSTRAINTS`
or outcome classification, so the function the tests exercise is the function R8 will run.

**What the `SYNTHETIC_TEST` create is made of, and who builds each part** (technical TR3-L6; it was only
named "F2-equivalent" before). Nothing below is an edit of an F2 file, and none of it touches
`web_saved_sandbox`.

| Part | What it is | Built in |
|---|---|---|
| Storage | the S2 tables `rw_root` and `rw_revision`, the same as the real branch's; a root and a revision are stored there, labelled `SYNTHETIC_TEST` (1.1) | R3 |
| Seal and validation | the fictional branch's acceptance in R3's seal, a fork of F2's `gw_check_artifact` and `gw_validate` (fictional envelope, `synthetic = true`, source records with no terms check, the fixed fictional bindings), reading the S2 tables where F2 read `web_saved_sandbox` and `web_portfolio_revision` (`guarded_workspace_v1.sql:297, :300, :362, :368`). These functions are the **TEST-only SQL part** (section 1 item 1): the real installer does not run it (PD-0066 decision 6, "only a real-only gateway"): R3's list tests and R6's static test show that about the installer, and Phase 2 reads the REAL catalog for it, first at R8 step 1 (section 1 item 1). The install-kind guard (4.2) still refuses test-scope snapshots at publish and admit in a REAL install, as a second barrier | R3 (SQL; no gateway SQL after R3) |
| Role plan | each runtime role's table and function grants are the same list in a TEST and a REAL install; the executor has no privilege on any `md_*` table, `web_saved_sandbox`, `web_portfolio_revision` or `web_csv_*`, and `EXECUTE` on the `md_*` read functions (2.6 item 6). T03's audit therefore audits the lists that REAL's role plan applies, and Phase 2 runs the same audit on the REAL catalog (1.2 rule 5.3 (e)) | R3 (the lists and the test) |
| World builder and service call | Python that builds the invented world from the locked snapshot and calls the existing fictional integration unchanged (unverified that it can; R5's first task) | R5 |
| The create and the read code | the create calls the shared create tail; read, reproduce and list call the shared read tail | R5 |

R5's tail tests, each marked "product path, shared tail on `SYNTHETIC_TEST`":

- **T-a**: the statement recorder sees at least one named `SET CONSTRAINTS`, never `ALL`, never the
  deadline guard's name; the inventory check refuses an unknown deferrable constraint;
- **T-b**: a create stalled between the seal and the COMMIT past `complete_by` (the session sets the
  timeouts to 0) is refused at COMMIT with `RW_DEADLINE` and the connection `IDLE`: a definite refusal,
  with no economic, lease or operation row left;
- **T-c**: an accepted `SYNTHETIC_TEST` commit, then the acknowledgement loss **simulated as F2's was**:
  the commit is real and the loss is injected after it (`_after_commit_ack` patched to raise
  `OperationalError`, F2's `test_c20`, `test_postgres_guarded_workspace.py:458-473`, which at HEAD asserts
  for the fictional gateway: UNKNOWN after the injected loss, one operation row, reconciliation of the
  operation reporting committed, and reconciliation of an absent operation staying UNKNOWN; not re-run by
  me). The product returns UNKNOWN, retries nothing, and reconciliation on a new connection finds the
  operation committed;
- **T-d**: the connection killed at the pre-commit seam by another connection: UNKNOWN; reconciliation
  finds the state absent and does not report a rollback from absence alone (F2's rule, `test_c20`'s last
  assertion; "absent is not by itself proof of rollback");
- **T-e** (crafted, E11): partial or conflicting state written by the owner role in the test's own
  disposable database: reconciliation reports UNKNOWN. **The same for a refused reconciliation** (3.1): with
  the context lapsed, a drain mark pending or a withdrawal completed, the reconciliation's own
  `ARCHIVE_READ` admission is refused, the tail returns UNKNOWN and not the refusal, and after a renewal the
  same reconciliation reports committed. A "rolled back" result is reported only by a
  create call's own definite refusal (T-b), never by reconciliation from absence. This is F2's rule
  (`guarded_workspace_store.py:352-357`: "absence remains UNKNOWN");
- **T-f** (technical TR3-L7): the shared read tail's recorder and static audit for read, reproduce and list
  (3.2): the recorder must record the path's own statements and zero `SET CONSTRAINTS` of any form, and no
  helper that issues `SET CONSTRAINTS ALL` is reachable from those paths;
- **T-g**: a read, a reproduce and a list entry stalled after the last statement and past `complete_by` are
  refused at COMMIT with `RW_DEADLINE`, and no value is delivered;
- **T-m** (PD-0069; not a test of the shared tails, so it is outside "T-a to T-g"; product path): through the
  product's own create path on an invented release of a `TEST` install, `read_release` called with
  `lease_checked=True` on the executor's connection, under an admitted `EXECUTE_CREATE` lease of the real
  branch (`TEST_SWITCH`, which reads its release before the service refuses) and, if the `SYNTHETIC_TEST`
  create reads a stored release (not verified: it calls the existing fictional integration, whose market-data
  source I have not read), under that one too, returns a `PostgresMarketData` whose
  `projection_digest()` and `export()` equal those of a direct read of the same release by the owner role
  (parity), and the same call after `complete_by` is refused with the function's code, classified as a typed
  refusal with whole rollback and not as a write-rule error (2.6 item 6). A recorder on the connection sees
  `rw_md_*` calls and no statement that reads an `md_*` table. **The recorder must not pass vacuously**
  (technical TR5R observation): `read_release` writes every table name schema-qualified with a quoted schema
  (`FROM "s".md_quote`: `pinned_schema` and `_quoted`, `market_data_store.py:497-518`, `:709`), so a matcher on a literal `FROM md_` would pass even
  with `lease_checked=False`. The matcher strips the schema qualifier and the quotes before it compares the
  names of `MD_TABLES`; the test asserts that the recorder saw at least one `rw_md_*` call; and a control runs
  `read_release` with the default keyword as the owner role on the same recorder and must see the `md_*`
  reads, so a matcher that cannot see a qualified name fails. **Also here, as a static audit:** it lists the
  call sites of `read_release` under `src/` (at HEAD there are none outside `market_data_store.py`) and shows
  that each one on the real-mode path passes `lease_checked=True`; the database's refusal (`42501`) is the
  barrier if one does not. The real branch's own reads of a REAL release first run at R8.

The reconciliation tests make their own committed state inside the test, so nothing depends on another
increment's database.

**Step 2: what this does not show, and the residual.** The tail is shown on the `SYNTHETIC_TEST` branch.
It is not the real branch's commit, and **this narrows the limit PD-0068 answer 2 accepted; it does not
replace it**, and R5's exit claims exactly this and nothing more. Not shown before R8, for the owner to see
(8.1 item 11):

1. the real branch's seal on an accepted `synthetic = false` result (the passing sides of O1 and O4);
2. any deferrable constraint, write path or row that **only the real branch** has, fired by name for the
   first time at R8. **Corrected** (technical TR3-L6): the S2 tables and the root-link foreign key are built
   in R1 and R3 for every scope and are fired in the `SYNTHETIC_TEST` create too, so they are not
   real-branch-only. What is left is whatever the real branch's deferrable-constraint inventory holds that
   the `SYNTHETIC_TEST` create's does not. R3's exit **lists the inventory of each branch, keyed by
   `(name, table, kind)`**, and R5's static test compares them; I expect the difference to be empty, and the
   exit then says so. If it is not empty, this item names the difference. The inventory check refuses an
   unknown constraint in both branches, but whether the real branch's inventory fires cleanly is shown only
   at R8;
3. the real commit's size and timing against `complete_by`;
4. a stall drill or a fault drill on the real commit: none is proposed, because the real run commits once
   and a rehearsal install was declined (PD-0068 answer 2). If the tail misbehaves at R8, the failure is
   the real run's. The classification is fail-closed: an error reply to COMMIT means the transaction
   rolled back (the technical review's reading; the order of steps inside PostgreSQL's commit is not in
   the pages I read and no HEAD test isolates it, so it is **not shown**), and any other outcome is UNKNOWN,
   which retries nothing.

Within PD-0066 decision 8 and PD-0068 answer 2 there is no further route to show more before R8. The owner
either accepts this residual (a record in a PD, which R8 then cites) or R8 does not start.

**What each proof can show before R8.** This answers open item 5. Each increment's exit marks every
test below as **product path**, **E11 crafted probe (not product evidence)** or **first run at R8**.
It must not report a crafted commit as product evidence.

| Test | Product path before R8 | E11 crafted SQL probe (not product evidence) | First run at R8 |
|---|---|---|---|
| T06 service and atomic archive; FF1-C08 | R5, real branch: real create code, staging, the actual service call, `SYNTHETIC_MARKET_DATA_REFUSED`, whole rollback, nothing addressable. R5, **shared tail on the `SYNTHETIC_TEST` create**: one atomic commit of root, revision, artifact and operation with an accepted (synthetic) result | R3: seal acceptance and one atomic commit of root, revision, artifact and operation on crafted synthetic-labelled inputs | the real branch's service-accepted NAV (O1 and O4 pass), seal, commit, archive bytes |
| T07 expiry and clock | R1: admission, lapse, bound, the deadline guard at COMMIT, withdrawal and the drain mark, on read-only-phase leases (empty bundles). R5, **shared tails on the `SYNTHETIC_TEST` create (T-a, T-b, T-f, T-g)**: a create, a read, a reproduce or a list entry that stalls past `complete_by` is refused at COMMIT | R3: create-phase completion and COMMIT-time refusal with a crafted bundle | none on the real context: expiry cannot be observed there (7.1, D-1, accepted in PD-0068 answer 3). The real branch's own COMMIT-time refusal is first exercised there only if it occurs (item 11) |
| T08 replay and access | R1 and R5: each of the four purposes refused independently at admission | R3: exact-201 replay, `IDEMPOTENCY_CONFLICT`, poisoned foreign JSON, on crafted commits | exact-201 replay and archive read of the real commit; reproduce |
| T09 failure | R1 and R5: deadlock, timeouts, service refusal, savepoint versus whole rollback, process kill before commit, no automatic retry. R5, **shared tail on the `SYNTHETIC_TEST` create (T-c, T-d)**: simulated acknowledgement loss after an accepted commit is UNKNOWN with no retry and reconciliation finds it committed; a killed connection is UNKNOWN | R3: SQL-level durability of a crafted commit after the connection drops (no product behaviour). R5, crafted (T-e): partial or conflicting state is UNKNOWN | read-only reconciliation of the real commit. A fault drill on the real commit is not proposed |

**The four orderings PD-0066 decision 6 says must be proven again for the real gateway** (conformance
re-review DC-M2). The accepted cost is restated in section 1 item 5. This table says what each can reach
before R8, and what it cannot.

| d6 ordering | Reachable before R8 | Not re-proven before R8 |
|---|---|---|
| Publication races (publish, renew, withdraw against admit and against each other; the lock order) | **R1, product path**: publisher commands and admits on separate connections (T01, T02), on invented data of both test scopes. None needs a seal | nothing material; the real publish at R8 is a single act with nothing to race |
| Rollback (whole rollback; nothing addressable) | **R1** read-lease rollback and cancelled workers; **R5, product path**: the real branch's create to the service's refusal, deadlock, timeout, process kill before commit, all rolling back wholly; and, **through the shared tail on the `SYNTHETIC_TEST` create (T-b)**, the rollback of a sealed bundle refused at COMMIT | rollback of a **sealed bundle of the real branch** on the product path. R3 shows it on crafted bundles only (E11); the real run commits once (item 11) |
| ACK loss (the commit succeeded, the acknowledgement was lost) | **R3 (E11)**: SQL level only; a crafted commit is durable and visible from a new connection after the client connection drops (R3 has no outcome code, so it shows no product behaviour). **R5, product path of the shared tail on the `SYNTHETIC_TEST` create (T-c, T-d)**: the product returns UNKNOWN and does not retry; the product's reconciliation code (new connection, exact owner, operation and command, current authority and integrity checks, E10 section 6) run in the same test against the state that commit made: bytes match gives committed; partial or conflicting (T-e, crafted) gives UNKNOWN; absent is not by itself proof of rollback | **the end-to-end ordering for the real branch: a product create commits an accepted real NAV, the acknowledgement is lost, the product reconciles.** No real-branch create can commit before R8, because the service refuses synthetic data (fact 12). PD-0059 proved this ordering with accepted commits (`reviews/FULL_F1_REQUIRED_2026-10-20/PM_ACCEPTANCE_V1.md:23`). **The owner accepted this limit (PD-0068 answer 2: "(i) Accept the limit (Recommended)") and declined a rehearsal install. The design does not claim it is re-proven; the first exercise of that ordering is the real run, if it occurs there.** The shared-tail tests narrow the gap and replace nothing; their own residual is item 11 |
| B06: an ordinary lease without the link cannot commit | **R3, the real gateway's own refusal**: an executor-role create lease that writes and then seals without the link, or never seals, is refused (the seal's link requirement; the bundle guard at COMMIT). The refusal side needs no accepted NAV. R5 adds the product path to the refusal | the accepted side of the seal (a bundle with the link and an accepted NAV) first runs at R8 |

FF1-C08's pre-run minimum is "invented preflight and real-service refusal"; E9 item 6 (`:103-107`)
likewise sets the admission evidence as implemented code paths plus invented or preflight checks, and
puts the first accepted real NAV after admission. Both match the first and second columns. E9
`:111-115` lists post-run evidence that only a real commit supplies; R8 (7.1) lists it by item.

**The reviewers' answer to open item 5** (technical re-review "What holds"; conformance re-review "Reply
to open item 5"). The classification is honest and is enough for the exits of R3 and R5 **as
refusal-and-rollback and binding evidence**. It does **not** support a PD-0066 decision 6 re-proof of ACK
loss, or of any accepted-path ordering, for the real branch, and **R3's and R5's exits must not claim
one**. The first-run risk is covered by the negative tests, review, and rollback on any failure. The
owner accepted the residual (PD-0068 answer 2) and declined the one way to get an end-to-end ACK-loss
drill without touching the owner's database, a rehearsal inside R8 in a disposable `REAL` install, which
would have produced the first `synthetic = false` records outside the owner's database. **No rehearsal
install is planned**, and the first `synthetic = false` records stay reserved for the real run (PD-0066
decision 8).

**What each exit may claim, exactly** (PD-0068 answer 2: "R3's and R5's exits claim only what they show").
R3: the SQL-level facts above, each marked "E11 crafted probe, not product evidence". R5: the correct
classification of UNKNOWN, committed and the definite refusal by the shared tail on the `SYNTHETIC_TEST`
create (T-a to T-g), and the real branch's refusal and rollback at the service. Neither claims a re-proof
of the ordering for the real branch. This differs from the main session's summary in PD-0068 in two
places; the owner's answer, an accepted limit, is unaffected by either:

- PD-0068 says R3 can show "UNKNOWN, no retry" on a crafted commit. R3 has no outcome code, so that test
  is R5's (TR2-M1 (b)).
- **New in the fix round (conformance R3C-L5).** PD-0068 says R5 shows "correct classification of
  committed, rolled-back and UNKNOWN states by the reconciliation code". **The reconciliation code does
  not classify a rolled-back state, and must not.** A "rolled back" result is reported only by a create
  call's own definite refusal (T-b), never by reconciliation from absence: E10 section 6 and F2 agree
  (`guarded_workspace_store.py:352-357`: "absence remains UNKNOWN"; "callers needing it retain UNKNOWN
  instead of guessing rollback"). So R5's exit claims: reconciliation classifies **committed** and
  **UNKNOWN** (T-c, T-d, T-e); the create call reports the **definite refusal** (T-b). A reviewer who
  checks R5's exit against PD-0068's words and asks for a reconciliation path that yields "rolled back"
  is asking for the inference E10 section 6 forbids. The PM may wish to correct PD-0068's summary; the
  owner's answer does not depend on it.

## 5. D5: writer classes

**Confirmed** (PD-0066 decision 9). Numbering: E10/N1
(`reviews/CP7_E10_EVIDENCE/protocol-author/F1_AUTHORITY_EXPIRY_COMMIT_PROTOCOL_V1.md` section 1; matrix
`writer_boundaries`). Classes: **P** participates; **S** proven separate by a test; **R** refused (not
wired, or denied). Scope: the HG4 slice (create, read, reproduce on one context), in the real
database.

| ID | Writer / reader | Class | How, and the proof needed |
|---|---|---|---|
| W01 | `FileStore.load_registry` / `SOURCES.json` (`files.py:55-61`) | **R as authority**; stays for historical and fictional tools | No positive real service loads it. Its content enters only as a proposal the publisher imports. T01: edit the file, nothing live changes |
| W02 | Download tool (`download.py`: `run_fetch :810`, `run_register :793`, `run_probe :726`) | **S** | Writes only files and manifests; cannot publish or reach the database. `require_human` is not a security control (`:177-183`). A file is not live until published |
| W03 | Ingest and build (`ingest_file :255`, `build_in_memory_market_data :836`) | **P, offline only** | Runs at qualification before publication, with the terms gate. **R at runtime**: no ingest from `FileStore` |
| W04 | `md_*` storage (`market_data_store.py:273-287`) | **P** | The loader writes immutable unreferenced rows; publication makes them reachable. One manifest per payload SHA (section 6.4). Its own reads are narrowed to `md_file`, `md_release` and the registry's get function, which returns the payload bytes (3.3), and its login is off between loads (PD-0070 decision 1; 8.1 item 12; 3.3) |
| W05 | Readers (`read_release`, `:695`) | **P** | Called on the same outer connection under the held locks, with the snapshot's registry; its internal transaction is a savepoint. **On the executor's connection it reads the `md_*` rows through the lease-checked functions** (PD-0069; 2.6 item 6): R5 adds the keyword-only `lease_checked` parameter, whose default keeps today's SELECTs (`market_data_store.py:517-616`, `:695-774`) for the legacy roles and their tests. The executor holds no SELECT on any `md_*` table, so a lapse or a withdrawal stops the reads, and a credential holder cannot read the rows with no operation |
| W06 | Resolver and derived views | **P by freezing**; mutators **R** | Identity, calendar, conventions and profile come from the locked snapshot. `add_vendor_id`, `change_ticker`, `apply_identity_assertions` and the live derived view are unreachable |
| W07 | Root create (`WebAccountStore.create_portfolio`) | **S** | The legacy role has no grants in the real database. Real create is the new code of section 1. **The proof also covers the executor connection**, where a reused route could call it. The call reads `web_saved_sandbox` first (the capacity count, `web_account_store.py:186`) and the executor has no privilege on it (section 1, item 5), so it is refused before any insert. If that privilege were ever granted, the real write fence and row policy (2.6), which refuse a lease-less write to **any** root, registered or not, are the second barrier. No `LOCAL_SYNTHETIC_ACCOUNT` row can appear. T03 includes the attempt and, in a disposable database, tests each barrier on its own |
| W08 | Workspace and ledger (`WorkspaceStore.command`) | **R** | Legacy roles: no grants. **On the executor role**: refused by the lease requirement of 2.6 (a write needs a current-transaction create lease for its own root, so an unregistered root is refused too) and the seal's shape check, not by missing grants. T03 includes executor-role attempts, among them the lease-less insert into an unregistered root |
| W09 | CSV (`CsvImportStore`) | **R** | Not in the slice. The merged R1 report-only protocol creates no financial provenance (FF1-C11). Real CSV commit deferred |
| W10 | Generic ledger, system events, selection, direct SQL | **R** | Same as W08, including the lease-less write to an unregistered root (FF1-C02: "no insert-first/register-later bypass"). An ordinary lease without the link cannot complete the seal. T03 covers every FF1-C02 entry class |
| W11 | Financial service (`compute_for_portfolio`) | **P** | Same connection, staged ledger pin, F8B policy digest from the snapshot. The result must be `synthetic = false` (O4a), F8B dry run (O4b), accepted NAV, else whole rollback. Built in R5; before R8 this step is exercised only to its refusal (4.4) |
| W12 | Legacy CLI and OS exports (`pack.py`, `evidence_pack.py`, `real_slice.py`) | **R for the HG4 runtime** | They read files, not the database authority, and are unaffected by withdrawal (3.3). **They also do not follow the purpose locks** (DC-L1): with export `false` and read `true` in the database, `evidence_pack real` still builds a pack from the files on disk, so the stored export right governs the database export path only. They are never the source of expected values. **Owner procedure on withdrawal** (PD-0066 decision 9): move the raw files aside and do not run the legacy tools. A staging store, if R4b makes one, is a further uncovered copy (3.3); one extra step is proposed there and not decided. The loader's reads (`md_file`, `md_release` and, through the registry, the payload bytes) are closed between loads by the owner's `NOLOGIN` step and open inside a load window (3.3; PD-0070 decision 1) |
| W13 | Installer and migrator | **P** under maintenance | NOLOGIN owner distinct from runtime, publisher and loader; mode `MAINTENANCE_HOLD` first. Superuser and OS change is a declared trusted boundary **only if no agent-usable superuser path exists**: that is what the install rule and its preflight check (1.2). The real cluster has its own installer, run by the owner as the superuser (1.2 rule 5.1), which checks every other path and every role it creates. The existing installers (`guarded_pg_provision.py`, `dev_env.py`) are not W13 for the real cluster, are outside the preflight's scope, and must never be pointed at it |
| W14 | Launchers and roles | **P** | Separate real-mode launcher and credentials, no owner fallback, startup refusal on mismatched database, role or object pins, **and the preflight of 1.2, run when the database's own install kind is `REAL` and never selected, skipped or relaxed by an argument, variable or key (1.2 rule 5.2); it gates `publish`, `renew`, the launcher and the admission probe (E27), and never `withdraw` (1.2 rule 5.1)**. The launcher over a `TEST` install, as R7's browser tests use it, meets no preflight. The launcher has no code path to the test switch. The publisher authenticates by a password the owner sets, never socket-trusted (2.5). The environment inventory is a separate read-only step (FF1-C09) |
| W15 | Real routes (`real_workspace_routes.py`, `real_source_contexts.py`) | **R until R7**, then **P** for create, read, reproduce and list | E1 stays limited and closed. Real mode uses the new scoped contract (2.4: authored in R5, reviewed, installed in R7, with the owner-scoped list route) and a snapshot-based provider |

Count: P 7 (W03 offline, W04, W05, W06, W11, W13, W14); S 2 (W02, W07); R 6 (W01, W08, W09, W10, W12,
W15; W15 becomes P at R7). This is a summary of intent, not proof of completeness: unknown reachable
actors stay HOLD (matrix closure predicate 2).

## 6. D6: acquisition records

**Decided** (PD-0066 decision 9).

### 6.1 Route and records

- **Route.** The download tool's `fetch` for prices (`run_fetch`, `download.py:810-843`; Alpha Vantage
  `fetch_alphavantage :505`, OpenFIGI `fetch_openfigi :599`), run by the owner in their own terminal.
  The manifest records function, symbol, `outputsize`, tool name and hash, and the retrieval time of
  the call. The v1 manifest is unchanged, `retrieved_by: human`.
- **The AAPL manifest stays `UNDECLARED`** (PD-0066 decision 1). `fetch_alphavantage` writes
  `UNDECLARED` with the anchor "label unverified" (`download.py:520-521`). The RAW reading comes from
  the profile's `call_adjustment` (`profiles.py:85-87, :269` at HEAD `7effcc8`) and is recorded as the
  label source (7.1, R4a; open item 2).
- **Sidecar acquisition record, one per file.** A canonical-JSON record holding:
  - the payload SHA-256 and the manifest SHA-256;
  - the approving decision record (PD id, commit and SHA-256 at that commit, as in 2.5);
  - the role "designated human product owner", **not the personal name**. The person is named in the
    PD and in `SOURCES.json`, and extra names in metadata that a model may see add exposure without
    proof;
  - the request as approved, the tool, and the terms-check reference.

  It is carried in the snapshot member tuple as the E10 provenance slot (by digest). The main session
  writes the records. They live **outside** `data/marketdata/files/`, whose `*.manifest.json` scan
  (`files.py:72-74`) must not change **[E10]**.
- **Who builds it, and what it gates** (technical re-review L-7). **R4b** builds the sidecar schema and
  its reader, and the O5 validator (4.2). In the `REAL` scope a member whose slot is the explicit legacy
  null is refused, so the D6 requirement cannot lapse silently. **R4b's exit and R8's needs require one
  valid sidecar per member.** For HG4 the members of `M` are exactly three files (conformance R2-L1
  (ii)): `alphavantage.us/quote/2026-10-01/AAPL_compact.csv`,
  `openfigi/identity/2026-10-23/AAPL_UW.json` and
  `calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json`. That is **three sidecars**. The third file of
  the 6.3 table, `AAPL_XNGS.json`, is not a member, is kept as evidence only, and has no sidecar. The NYSE
  calendar is outside the 6.3 table because it needs no new digest confirmation (PD-0066 decision 9), but
  O5 asks for a valid sidecar for every member, so it needs a record too, citing the decision record
  that registered it (HG2 condition 4); the main session names that record when it writes the sidecar. If
  the owner means the calendar to have no sidecar, O5 must exempt a calendar member explicitly, which
  changes the decided design (PD-0066 decision 9: "a sidecar record per file"); that would be the owner's
  call. The records are written by the main session before the real qualification run.
- **Agent files.** Agent manifests (v2) are refused in the real scope (R2). A v2 loader for
  agent-acquired files is later work (proposal :420-430).

### 6.2 Never downgrade agent to human: what is enforceable

A human can run `register-file` on agent-fetched bytes and the tool writes `human`. That does not
make the acquisition human (fact 6). The controls that can fire now:

1. **The owner's digest confirmation** (6.3). It is the binding control and an attestation; it does
   not authenticate who fetched the bytes.
2. **Agent manifests are refused in the real scope.** This catches files that declare an agent, not
   relabelled ones.

Not claimed: a "seen under both" collision check or a `register-file` refusal for known agent
payloads. They cannot fire today: v2 is refused in the scope, `md_file` holds one manifest per
payload, and there is no index of agent-acquired hashes.

### 6.3 The owner's digest confirmation

Recorded in PD-0066 decision 9, using the files already on disk; **no new download**. I recomputed all
six hashes earlier today and they equal the record; in round 2 I recomputed the four OpenFIGI hashes
again after the move below, and they still equal it. Paths are relative to `data/marketdata/files/`
unless stated.

| File | Payload SHA-256 | Manifest SHA-256 |
|---|---|---|
| `alphavantage.us/quote/2026-10-01/AAPL_compact.csv` | `066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb` | `268535ddc8b6284a144cbe810668a3586a9e574f257b438794bbe08c1f0efb82` |
| `openfigi/identity/2026-10-23/AAPL_UW.json` (in the store; the one OpenFIGI file of a release) | `b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc` | `7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738` |
| `AAPL_XNGS.json` (**moved out of the store** on 2026-10-24 to `data/marketdata/observations/openfigi/identity/2026-10-23/`, unchanged; evidence only, never a member) | the same payload hash (identical bytes) | `cb4d862d37e628b31c7a009f53d461188583e2090934de2bb080c08e21963c8d` |

The NYSE calendar (`calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json`, payload
`4f21b26b…72ef`) is the owner-checked calendar registered under HG2 condition 4 and needs no new
confirmation. **Any other file that enters the data version `M` needs its own confirmation or
registered check before it counts**; the 2026-10-01 OpenFIGI observations are not covered by this
table.

### 6.4 One OpenFIGI manifest per release, and what the owner's move changed

Only **`AAPL_UW.json`** (the manifest whose request names the exchange code directly) enters a release
(PD-0066 decision 9). The original reasons were fact 13: `md_file` keeps one manifest per payload, and
`FileStore.index()` raised while both manifests sat under `files/`.

**The owner has since moved the duplicate out of the store** (fact 13; owner-approved 2026-10-24).
`AAPL_XNGS.json` and its manifest sit, unchanged, in
`data/marketdata/observations/openfigi/identity/2026-10-23/`. The store keeps `AAPL_UW.json` only, and
`FileStore(data/marketdata).index()` returns 15 entries (run read-only today), so a build over the store
no longer raises. This is the alternative the first version of this section left to the owner ("the
owner moving one manifest aside"), and it is the owner's act, not mine.

**Consequence for E9 (the staging store).** I had chosen a staging store because building from the store
as it stood would raise. That reason is gone. What remains is that `index()` is global: the build loads
only the files the release names (`ingest.py:864-867`), but a future second manifest for one payload, or
an unreadable manifest, anywhere under `files/` would stop qualification again (fail-closed, not
silent). R4b's plan chooses between:

- (a) read `data/marketdata` directly: no extra copy for 3.3 to disclose, and a clear error if the store
  is broken. **I propose (a)**; it is my choice **[E9]**, not a decision;
- (b) a staging store of exactly the selected members: it isolates qualification from the rest of
  `files/` and adds one more copy that withdrawal does not cover (3.3).

Either way R4b's run lists every member of the release against the 6.3 table and the rule under it.
Making `FileStore.index()` tolerate duplicates is rejected: its refusal is deliberate. Runtime never
uses `FileStore` at all (section 2.1).

## 7. D7: build order

**Decided** (PD-0066 decision 10). F1 closes **for this named target only**: one context, create plus
read plus reproduce, one real namespace. It does not close full F1, real UAT or HG4. **F1 is reported
closed for that target only together with its accepted limits**, so that none can drop out of a summary
(conformance R2-L3): the ACK-loss limit (PD-0068 answer 2); D-1, expiry not observable on the real
context, and D-2, rollback after writes not forced there (PD-0068 answer 3); the upper-bound limit of
`term_end_not_after` (PD-0068 answer 4); the two disclosed limits of the commit-time deadline, the
commit-processing gap and the guard-bypassing executor (PD-0068 answer 1); the residual of the
post-seal tail, if the owner accepts it (8.1 item 11); **D-3, two-user isolation not collected on the real
context, if R7 finds the real-mode app cannot hold a second user without an economic write; R8 does not
start unless the owner's recorded answer to D-3 is an acceptance** (conformance R3C-L3 and R3R-L3: a
recorded refusal stops R8 as item 11's does, so isolation cannot drop out; R8's Needs, below); **and the
evidence limits of the install rule** (1.2 rules 5.1, 5.3 (e), 5.4 and 7: the installer's accepting side,
and with it the first read of a REAL catalog, are first exercised at R8 step 1; a wrong refusal after Phase 1
leaves a created, unused install, and a Phase 1 failure leaves a partial one; grants are audited by the
installer's Phase 2 and `--check` and not at each gated start; `withdraw` would answer a server's request for
a cleartext password; R6's plan states them for the owner's approval). **The loader's login limits are in
this list too** (PD-0070 decision 1, "Off between loads (Recommended)"; 3.3 has the procedure). The owner sets
the loader `NOLOGIN` right after its last use in R8 and `LOGIN` again only for a later load. Under N2a's
binding that last use is the loader's registration of the context-bound candidates after the publish, step
(4a), and not the end of the qualification run (3.3 item 1); R6's plan states the sequence (one window or two)
and the HG4 package records the one that was followed. As shown to the owner and accepted with the choice: it
stops new connections only, and whether `NOLOGIN` ends a
session that is already open is not shown; the superuser and the owner role are not affected; each later load
needs the owner's `LOGIN` step. During a load window the owner opens, the loader can read what its narrowed
list allows, including the payload bytes through the registry (3.3). That is part of the procedure and not a
limit beyond the owner's own opening of the window. The steps are the owner's procedure: no tool enforces them
(E29 only prints the state; 3.3). Each
increment:
the engineer builds and tests, an independent technical review follows, the main session records, and
it is committed when the owner asks. Tests: T01 to T10 are E10 section 7; FF1-Cnn are matrix cases;
all are proposals and none has run. Provisioning uses `tests/product/guarded_pg_provision.py` and
`dev_env.py` on disposable `TEST` databases on the development clusters.

### 7.1 Increments (order fixed by dependency)

| # | Increment | Needs | Tests it carries | Exit |
|---|---|---|---|---|
| **R0** | **PD-0066** records every owner decision D1 to D7 (its decision 10: "R0 is this record"). PD-0067 records the CN and label decisions that this design carries (facts 9 and 14); it records none of D1 to D7. PD-0068 records the owner's answers to the former 8.1 items 7 to 10. The Quant's `state_kind` confirmation is in (`market-data/1.16` item 9, committed `ae6dfdc`; 1.1) | owner | none | Done |
| **R1** | Real authority core **and scope core**. Authority: snapshot (member tuples with `source_id`), history (with the expiry basis entries, one per member source), head, **drain mark with issuer, reference and time**, mode, install kind (with `W`); roles (owner, executor, loader, publisher; the loader holds no table privilege until R2 gives it its list, 3.3); the lease and root-link tables with the admit function (clock read before sample), `complete_by = LEAST(admitted_at + W, valid_until)` with its table check, the root-link-to-portfolio deferred foreign key, the owner-scoped enumeration function `rw_list_roots` (2.4), and **the deadline guard as a constraint trigger of its own, with a unique name**; the proposal format with its pure writer and verifier; publisher commands (publish, renew, withdraw; a renewal may carry an earlier `valid_until`, the date correction of 3.1 / E25) with the mandatory decision reference and the expiry evidence (the plausibility rule of 3.1, with its upper-bound wording). Scope core: the scope definitions, the factory, the **reviewed switch** and the install-kind guard (4.2). **Gains the X1 design and tests (3.1, 3.2)**: `valid_until`, trusted clock, admission under lock, the capped deadline and its bound, cancellation. R1 builds no fence, no seal and no guarded load (R3, R2): its in-flight work is a read-only-phase lease on a crafted root fixture (3.2) | R0; this design revised and reviewed after the round-3 fix round, **and committed when the owner asks** (PD-0066 decision 10, "Before R1", steps 1 to 3: a review that passes does not start R1 by itself, conformance R3C-L7); PD-0068 answer 1 (the cap, which fixes the `complete_by` formula) | T01, T02 (two connections, blocking-pid causality), T04, T07 (3.2: the R1 items), FF1-C03, FF1-C04, FF1-C06, reduced FF1-C12 (idempotent re-run of an interrupted publish); the scope tests of 4.2 (switch refused outside a `TEST` install, install-kind guard in both directions, built as 4.2 describes, asserting the install-kind code only; R2 adds O1, R3 the label code). Snapshots of `SYNTHETIC_TEST` and `TEST_SWITCH` come from the product factory, never a test helper. The named `SET CONSTRAINTS` form (on the root-link foreign key) and the deadline guard's COMMIT-time refusal are shown here (fact 17). Publish refuses a `REAL`-scope snapshot until R2 wires the validators. R1's publisher-tool tests (exit statuses, 3.2) run on `TEST` installs on the development clusters and meet no preflight (1.2) | Publish, renew, withdraw, lapse, re-publish; a lease minted, bounded and refused on invented data of both test scopes; a timed-out withdrawal that leaves a recorded, pending drain mark; the switch reviewed as its own item |
| **R4a** | Inputs and policy for `M`; **no split or corporate-action file in `M`**. Details in 7.1a | R0, `market-data/1.16` (committed `ae6dfdc`; its method review is PASS_WITH_FINDINGS with LOW findings open, STATUS.md item 11), the `SOURCES.json` update of 7.1a item 5 | Adapter and profile tests with re-recorded pins and a stated reason for each; policy digest recorded | Inputs defined; the code states the method it runs; the `alphavantage.us` record carries the PD-0066 decision 5 reading, written and reviewed (it enters the snapshot, so a later edit means a new context) |
| **R2** | Real-scope provenance candidates (generalised N2a): the O1 to O3 validators and the provenance module of 4.2, on R1's scope core, with publish wired to run them; guarded load bound to R1's mode, head, lease and root; **the loader's grant list** (one list in the shared installer code: `INSERT` on the thirteen `md_*` tables, `SELECT` on `md_file` and `md_release`, `EXECUTE` on the registry's put and get functions, nothing else, 3.3; PD-0070 decision 1 keeps this list, with no further narrowing) **and the keyword-only `count_rows` parameter of `write_release`** | R1; **the owner's answer to 8.1 item 12 (PD-0070 decision 1) meets R2's gate on the loader**: R2 fixes the loader's grants, R3's audit and R4b's run consume them, and the list stays as 3.3 has it. R2 still follows this design's commit and R1 | Contract tests per the table in 4.2: O1, O2 and O3 each listed independently with controls where possible, missing or negative terms check, agent or v2 member, mixed scopes, publish reporting every failed predicate; the validators take invented attestations by value and write nothing (4.2). PG: N2a regression under `SYNTHETIC_TEST`; `TEST_SWITCH` guarded load with a real-branch lease; the guarded load refuses at or past `complete_by`, and the pause-before-the-guarded-load test of 3.2 (technical re-review L-1: this point moved here from R1); the loader cannot publish; **the loader holds exactly its table privileges and its two registry functions (a catalog assertion; PUBLIC's default `EXECUTE` on the twelve migration functions is revoked by R3's statement, so "no other function" is first asserted by R3's audit, 1.2 rule 5.3 (e)), `write_release(..., count_rows=False)` loads an invented release as the loader, the loader's `SELECT` of `md_quote` is refused (`42501`) under the list above, and the loader's call of the registry's get function returns what 3.3 says it returns (the payload bytes), so that each read the list allows is asserted present and every other absent**; **a test of the generalised registry's binding and of its install with a loader that cannot log in (3.3 items 1 and 3): whether a context-bound registration is refused before the publish and accepted after it, or the registry binds otherwise, and whether its install and per-call checks accept a loader without `LOGIN`**; the install-kind test of R1 gains O1 in its listed codes (4.2) | Candidates immutable and unreferenced; guarded load exercised in both test scopes; each validator's code seen by its own test; publish's `REAL` branch enabled behind the validators; **the exit states, from that test, whether the real registry has the loader register a context-bound bundle after the publish (so the loader's last use in R8 is step (4a), 3.3 item 1) and whether its install check requires the loader to have `LOGIN` (3.3 item 3), because R6's plan and R8's sequence take both** |
| **R3** | Real root storage S2 (`rw_root`, `rw_revision`) with the fact-11 reader audit (`src/` and `web/src`, with the display-wording terms); **the write fence, row policy and journal of 2.6 (whole database is the namespace; the deadline checks at statement time, reads of the rooted tables and the archive included: 2.6 item 2), and the thirteen lease-checked `md_*` read functions with the executor's grants (EXECUTE on them, no privilege on any `md_*` table: 2.6 item 6, PD-0069)**; the gateway seal **for both branches** (the real branch's, with O4 and the origin-label row guard, and the fictional branch's, a fork of F2's `gw_check_artifact` and `gw_validate` that reads the S2 tables, in the TEST-only SQL part that a REAL install does not hold, section 1 item 1; 4.2 build table), archive, the bundle guard and the mandatory link (PD-0059's obligation design; N2b's seal-side objects); **each runtime role's table-grant and function-grant list (the executor's, the loader's from R2, the publisher's from R1) as one list for TEST and REAL installs, with the installer's schema-wide revoke of PUBLIC's `EXECUTE` on every function (1.2 rule 5.3 (e); technical TR5-L2) and a re-run of R2's loader write with it in place (the evidence for the two `md_*` insert trigger functions the loader fires, and for no other migration trigger: the executor-fired ones are first fired under the revoke by R5's `SYNTHETIC_TEST` create, 1.2 rule 5.3 (e); technical TR6-L2), and with a test on the lists that the shared installer code returns for each kind (4.2) that, for every one of the three roles, the two table-grant lists are identical, that the executor's grants none of `web_saved_sandbox`, `web_portfolio_revision`, `web_csv_*` or any `md_*` table, that REAL's file list omits the TEST-only part and that REAL's function grants differ from TEST's by that part's functions only; the catalog audit as a function (T03; product code under `src/persistence/`, 1.2 rule 5.3 (e)), shown on a TEST install to pass as `TEST`, to report the TEST-only part's functions as `REAL`, and to report each crafted drift of any runtime role or of `public` (the executor granted a publisher function, the executor owning a table, the loader granted a write on an authority table, the executor granted a `SELECT` on `md_quote`, a column-level grant, the loader or the executor granted `MAINTAIN` on the drain-mark table, `public` holding `EXECUTE` on a function; E11); the deferrable-constraint inventory of each branch, listed in the exit (4.4 Step 2, item 2)**. **No service call: the create, read and reproduce application code is R5. After R3 no increment adds gateway SQL** | R1, R2 (PD-0069 is decided; the loader's grants are R2's) | T03 all-writer matrix incl. executor-role attempts (every FF1-C02 class, including `WebAccountStore.create_portfolio` on the executor connection; **the lease-less insert into a registered-nowhere root, each barrier alone: 2.6 item 5**; ordinary lease without the link refused; PD-0060's pattern); fictional flow unchanged (T10); FF1-C01, C02; O4 tests (4.2); the seal's acceptance, the atomic commit and the crafted parts of T06 to T09, **each marked "E11 crafted probe, not product evidence"** (4.4); the create-phase items, the read bound and **the `md_*` read-function tests (refused after `complete_by`, after a lapse, during a pending drain mark and after a withdrawal; the executor has no direct SELECT on any `md_*` table)** of 3.2 marked R3; the install-kind test gains the origin-label code (4.2); R1's crafted root fixture extended for the fence (3.2); label tests: the row-to-label mapping is a pure function of the stored row, tested on in-memory rows of both origin values and never stored; a `TEST_SWITCH` root and output carry no real-origin string; a source audit, with the widened terms of fact 11, that no reader of `rw_*` hard-codes `synthetic`, a mode string or display wording, and a pure render test on an in-memory `REAL_SOURCE`-labelled row (never stored) that none of that wording reaches a server-built string for the real root | Catalog and behaviour assertions on TEST installs; every test marked product path, E11 or first run at R8. **R3 claims SQL-level facts only about commits** (a crafted commit is durable after the connection drops; a refused COMMIT leaves no row): it has no outcome code and shows no "UNKNOWN, no retry" (4.4). **R3 does not claim that a REAL database holds no fictional-branch function or that REAL's grants are right**: it shows the file split, the lists and that the audit can see (section 1 item 1); the REAL catalog is first read by Phase 2 at R8 step 1. **Nor does it claim anything about the loader's reads, which the owner's procedure of PD-0070 decision 1 governs** (3.3) |
| **R4b** | The qualification run: reads `data/marketdata` directly or a staging store of the selected members (6.4, [E9]), calls R1's proposal writer, and the publisher imports the registry into the snapshot; its loads use the loader role with R2's list and `count_rows=False` (3.3). **Builds the sidecar schema, its reader and the O5 validator (6.1, 4.2)** | R1, R2, R4a | Reproducible run; the digests in the proposal match; the output passes R1's proposal verifier; a proposal edit changes nothing live; O5 failing and control cases (4.2), all with **in-memory sidecars only**: the reader parses a sidecar given as bytes and writes nothing, and **no sidecar file is written for an invented payload** (4.2: stored, it would differ from a real acquisition only by the source's synthetic flag; conformance R2-L1 (i)). Under `TEST_SWITCH` O5 is bypassed, so the invented release needs no sidecar. Runs on invented `TEST_SWITCH` data in tests | Proposal files exist for the invented release; the sidecar reader and O5 exist, and the `REAL` scope refuses a member without a valid sidecar. The three real sidecars (6.1) are R8's need, written by the main session, not R4b's exit |
| **R5** | Real consumption: the world builder from the locked snapshot (N2b), load a release, read under the held lock with the snapshot registry **through the lease-checked `md_*` read functions (`read_release(..., lease_checked=True)`, 2.6 item 6, PD-0069; R5 adds the keyword and no SQL)**, call the real F8B service; the real create, archive read, reproduce and **list** code; the **new scoped contract module** (2.4, with the owner-scoped list route), not installed anywhere. **The shared create tail (E23, 4.4)**: one function that fires the other deferrable constraints by name and never issues `SET CONSTRAINTS ALL`, leaves the deadline guard pending (3.1), commits, classifies a COMMIT-time error as 3.1 says, and reconciles on a new connection (committed, UNKNOWN; **it never classifies a rolled-back state**; a definite refusal is reported by the create call itself, 4.4, R3C-L5). **Both branches' creates call it; the `SYNTHETIC_TEST` create (the fictional branch, `TEST` installs only; Python over R3's fictional-branch seal and the S2 tables, calling the existing fictional integration unchanged; 4.2 build table) is built here so that the tail runs on product code with an accepted commit before R8.** **The shared read tail (E23, 3.2)**: admit, read under the held locks, deadline guard left pending, COMMIT, value returned only after the COMMIT; read, reproduce and each list entry call it. **R5 adds no gateway SQL.** Output carries the claim limits (7.4) | R2, R3, R4b | FF1-C05; FF1-C08: the actual service **refuses** `TEST_SWITCH` data and everything rolls back, nothing addressable (4.4); the product-path parts of T06, T08, T09 (4.4); **the tail tests T-a to T-g of 4.4, each marked "product path, shared tail on `SYNTHETIC_TEST`" or "crafted (E11)"**, and **T-m, `read_release` through the lease-checked functions: digest parity with a direct read, refusal after `complete_by`, no `FROM md_*` statement on the executor's connection (4.4)**, including the R5 items of 3.2 (the stalled create, read, reproduce and list entry refused at COMMIT with no value delivered; the non-vacuous statement recorders on the create and on the read paths; a killed connection is UNKNOWN) and the reconciliation tests, which make their own committed state inside the test; the static audit that neither branch's create, nor its read, reproduce or list code, has its own `COMMIT`, `SET CONSTRAINTS` or classification and that none reaches a `SET CONSTRAINTS ALL` site (3.2); **no end-to-end ACK-loss re-proof for the real branch is claimed** (PD-0068 answer 2); N3-derived concurrency and restart tests; an ambiguous commit is UNKNOWN; contract tests of the scoped contract with no route installed. **Claim-limit tests (7.4):** pure render tests of the R5 output over an in-memory `REAL_SOURCE` lineage fixture (never stored or served) that every C-item and every S-slot is present, and over a `SYNTHETIC_TEST` fixture that the invented-data mark shows and no real-source sentence does. **The independent NAV oracle `10 x p + 500`, derived by the Quant, not from the engine or the adapter, is applied at R8** | Binding checks and refusal path proven for the real branch; the shared tail proven on the `SYNTHETIC_TEST` create and nowhere else; no accepted real NAV before R8; the scoped contract reviewed as an item of this increment's independent review; every ACK-loss and sealed-rollback item labelled "shared tail on `SYNTHETIC_TEST`", crafted (E11) or first run at R8, none labelled re-proven for the real branch; the residual of 4.4 (8.1 item 11) stated in the exit; **the exit also states which executor-fired migration triggers the `SYNTHETIC_TEST` create fired on an install with the installer's revoke in place (the `ledger_event` insert triggers, and `benchmark_selection_before_insert` if the create writes that row), the first firing of any of them without PUBLIC's `EXECUTE` (1.2 rule 5.3 (e); technical TR6-L2)** |
| **R6** | Deployment audit and one restart delta. The read-only inventory of the owner's environment **needs the owner's go-ahead**. The written install plan for the real database: cluster (its own, or the separately approved revoke of PUBLIC `CONNECT` on existing databases, section 1 item 2), roles, credential holders (**who holds the executor and loader credentials is decided here, with the owner's approval; R8 step 1 follows it**, conformance R3C-L4; **under PD-0070 decision 1 nobody can log in as the loader outside a load window the owner opens, and inside one the holder named here, an agent session included (1.2 rule 4), can read what the loader's list allows, the payload bytes through the registry among them: 3.3; conformance R5R-L1**), **the install rule of 1.2: a password for every role and no trust, who holds the superuser password (the owner alone), the `pg_hba` lines, the data-directory placement, the installer's revoke of PUBLIC `CONNECT` on `postgres`, `template1` and any other connectable database of the cluster, the membership rule of 5.3 (b) (the four real roles hold no membership; there is no allowed-pairs or approved-power list), the owner procedures of the table under rule 2 (`\password`, no passfile or service entry, no literal `PASSWORD` statement, `log_statement`), and the publisher's authentication (2.5)**. **Builds the real installer and the preflight of 1.2** (REAL installs only; no switch; the gate applies to `publish`, `renew`, the launcher and the admission probe, and never to `withdraw`; the installer's Phase 2 and `--check` call R3's catalog audit on the REAL database, 5.3 (e)) | R1, R3 | FF1-C09; FF1-C10; the catalog audit (section 1, item 2); **the preflight tests of 1.2 rule 7: the decision table of rule 5.2, the by-command rule of 5.1 and every listed case on fake facts (including the membership and settings cases, the `CONNECT` case, the catalog-audit cases, Pass S over files under a temporary `HOME`, `REJECTED`, `listen_addresses`, and withdraw not gated); the static no-bypass test over the installer and the publisher tool (R7 extends it to the launcher and the probe), which also fails if any gains a credential option or a credential environment read, and fails if the real installer names the TEST-only part's file or takes a file or grant list from anything but the functions R3 tests; the probe against disposable roles on a development cluster, **which shows the refusal side only and cannot calibrate `CHALLENGED` or `REJECTED`**; and, only if the owner grants the sandbox exception, the classifier against the real refusals of a throwaway scram-only cluster under `$TMPDIR` (**calibration only: no gateway, no REAL-scope content, no real tool run; the installer's accepting side is first exercised at R8 step 1 on every path**, 1.2 rule 7). **Without the exception, `CHALLENGED` and `REJECTED` are first calibrated at R8 step 1 too.** The TEST provisioner writes `TEST` only and the real installer `REAL` only. The refusal in `Provisioner.preflight` for a cluster holding a `finweb_real*` database and the name-level refusal in `connection.missing_env_vars`, each with its test (rule 6)** | Inventory written, including the actual `pg_hba.conf`, the superuser/trust paths found, whether `~/.pgpass` or a service file has an entry for the real cluster (names only, never passwords), and which OS user owns the data directory; unknown actors listed HOLD; install plan ready for the owner, stating the publisher's authentication, the superuser-password holder, which `CONNECT` option applies, the owner procedures, **the loader's holder and the loader's reads that holder gets inside a load window; R8's sequence for the loader's login, one window or two (3.3 item 1; conformance R6C-M1), chosen after R2's exit states whether the real registry has the loader register a context-bound bundle after the publish and R4b's or R6's plan names the tool that does it; whether Phase 1 creates the loader with `LOGIN` or with `NOLOGIN`, chosen after R2's exit states whether the real registry's install and per-call checks require `LOGIN` as N2a's do (3.3 item 3; conformance R6C-L1, technical TR6-L1), and, if `NOLOGIN`, that the LOGIN-keyed checks of 5.3 do not cover the loader while it cannot log in (5.3 (g)); the owner's `NOLOGIN` and `LOGIN` steps of 3.3 (PD-0070 decision 1; conformance R5R-L1); and the re-run of the revoke after a later migration (1.2 rule 5.3 (e); technical TR5R observation)**, and that the existing test tooling and the environment-driven tests are outside the preflight and are not used on the real cluster (on a shared cluster, the superuser-driven test tooling could never run again, 1.2 rule 3). The install plan also states, for the owner's approval, the evidence limits of 1.2 rules 5.1, 5.3 (e), 5.4 and 7: the installer's accepting side, and the first read of a REAL catalog by Phase 2's audit, are first exercised at R8 step 1; **a wrong refusal in Phase 2 or at a tool's first gated start comes after Phase 1 has created the database, the roles and the gateway (no content yet), and the owner then waits for a reviewed fix and either re-runs `--check`, or drops and reinstalls, or approves SQL in the existing database (rule 7); that nothing is used until the refusal is resolved is the owner's procedure, which no tool enforces; and a Phase 1 failure at R8 step 1 leaves a partial install with no content, with the same owner options (technical TR4R-L3; rule 7)**; grants of every runtime role are audited by Phase 2 and `--check` and not at each gated start; **`withdraw` connects without `require_auth` and so would answer a server's request for a cleartext password, which sends the publisher's password to whatever answers on the socket path (an impostor inside rule 7's trusted-operator boundary; the alternatives are a `require_auth=scram-sha-256` demand, one more thing that can stop a withdrawal, and the negated `require_auth=!password`, which refuses only a request for a cleartext password; this bears on PD-0066 decision 7, and the plan states which of the three the owner prefers)**. **The preflight gate is a separate item in R6's independent review** (for the installer and the publisher tool; R7's review has its own item for the launcher and the probe), as the switch is in R1's |
| **R7** | Web real mode: a launcher, create, read and reproduce routes that install **the scoped contract reviewed at R5** (2.4), and the UI with origin labels read from the stored fields (1.1) and the claim-limit slots (7.4), EN/zh, three depths; a real-mode list type in the client conforming to the contract's list route (fact 11, 2.4), not `AccountPanel`'s synthetic list. E5's closed contract is not answered in the same app. Closed refusal elsewhere; two-user isolation. **The admission probe (E27; conformance R3C-L2, technical TR3-L8)**: a one-shot command beside the launcher that opens a transaction on the executor connection, calls the gateway's admit for one purpose (`ARCHIVE_READ`, `ARCHIVE_EXPORT` or `EXECUTE_REPRODUCE`; never `EXECUTE_CREATE`, whose admission can register a root) on one context, prints the outcome or the refusal code, and rolls back. It writes nothing and leaves no lease. It is not a route, and its output says "direct gateway admission, not a product route". It exists because the scoped contract has no export route (2.4; a real export purpose is later work, 7.3), so the export right can only be shown refused at the gateway. Over a `REAL` install it runs the gate of 1.2. **The launcher over a `TEST` install runs no preflight; over a `REAL` install it runs the preflight of 1.2 (the decision comes from the database, 1.2 rule 5.2), so R7's browser tests need no bypass** | **R3, R5, R6**; the contract reviewed | API contract tests; Playwright over `TEST` install data; **R7's exit states whether the real-mode app can hold a second user without an economic write (a registration writes no portfolio, account or ledger row, so none is fenced); if it cannot, two-user isolation becomes a third declared deviation, D-3, put to the owner through the PM before R8 (conformance R2-L4)**; foreign root returns a generic 404 before decode; FF1-C11 sentinels (raw not in model-visible fields); closed routes still closed; the launcher module has no path to the switch (static check); UI tests: the claim-limit slots exist and are filled from lineage fields; over `TEST` data the invented-data mark shows and the real-source sentences of 7.4 never render; no real-origin label appears. **Claim-limit text tests (7.4): the pure render of the R7 component over an in-memory `REAL_SOURCE` lineage fixture, never stored or served, in EN and zh at all three depths, asserting that every C-item is present, including "dividend component `UNVERIFIABLE`" and the single-source, no-comparison caveat, and that each S-slot is filled from its lineage field.** A widened-wording test on the client strings (fact 11). **Admission-probe tests on `TEST` installs:** the export purpose is admitted while the right is on, and refused with its code when the right is off, after a withdrawal and after a lapse (the other two purposes likewise); no lease row remains after any run; the probe has no option that selects `EXECUTE_CREATE`, and no path to the switch or the preflight decision (the static check of 1.2 rule 5.2, extended to these two tools here, covers it). **The preflight tests for these two tools** (technical TR3R-L3; R6 could not write them, the tools did not exist): the static no-bypass test over their options and environment reads, and the same failing facts as R6's case list on fake facts, which make each refuse to start and write nothing | UI runs on invented data marked as such. The claim-limit text is tested before R8 on a never-stored fixture; the real 7.4 wording rendered from the real lineage, and the real root's label, are first checked at R8. **The gate as the launcher and the probe use it is a separate item in R7's independent review** |
| **R8** | The owner's step, in this order. (1) Install the real database and roles from R6's approved plan (section 1, item 3) **under the install rule of 1.2: the owner runs the real installer as the superuser in their own terminal (Phase 0, the checks before it creates anything, then Phase 1, then the owner sets the passwords of the superuser, publisher, executor and loader with `\password`, then Phase 2). The superuser and publisher passwords are given to no agent session. The executor and loader credentials are held as R6's approved plan names (1.2 rule 4): this step does not decide that, and an agent that holds one is the recorded limit of rule 4, reached by a prompt and never by a file or the environment. The installer's checks must pass, the catalog audit of Phase 2 included (the first read of a REAL catalog); a refusal in Phase 2 leaves the created install unused until a reviewed fix (1.2 rule 7)**; from here `publish`, `renew`, the launcher and the admission probe run the runtime preflight at each start, and `withdraw` does not (1.2 rule 5.1). (2) The real qualification run on the confirmed files, through the loader role into the real database (the `md_*` rows and the unbound candidates). **In the two-window sequence of 3.3 item 1 the owner sets the loader role `NOLOGIN` right after it, in the owner's own terminal, and `LOGIN` again before (4a); in the one-window sequence the loader keeps `LOGIN` from here to (4a). R6's plan states which.** (3) Review of its proposal files. (4) The **owner's publish** with a decision reference, the expiry evidence (one entry per member source, as the owner decided in PD-0068 answer 4: `LEASE_TERM` for `alphavantage.us` with `term_end_not_after` 2027-10-01T00:00:00Z, `NOT_ASSESSED` for `openfigi` and for `calendar.manual`) and `valid_until` 2027-09-01, with the upper-bound limit stated in the publish record. **(4a) The loader's last use in R8, under N2a's binding (3.3 item 1): the loader registers the context-bound candidates, which needs the snapshot row that the publish wrote. Right after it, the owner sets the loader role `NOLOGIN`, in the owner's own terminal (PD-0070 decision 1; 3.3). If R2's exit says the real registry binds otherwise, the last use is the end of (2) and the step follows it. A re-run of (2) that (3) or (4) calls for, once the loader is `NOLOGIN`, is a later load: the owner sets `LOGIN`, the run loads, and the owner sets `NOLOGIN` again.** (5) The real run. (6) UAT per E9, within the limits listed below: it collects the items that can be collected on the real context and ends with the revocation test, **withdraw (all four rights shown refused), then renew**, each a separate publisher act by the owner citing its own decision record (PD-0068 answer 3). The withdrawal is never gated by the preflight; the renewal is. How the four rights are shown refused is stated after the observations list below: create, read and reproduce at the real-mode routes, the list with its per-root status, and **export by a direct gateway admission through the admission probe, labelled as that**. (7) The HG4 package, which states D-1 and D-2 as not collected on the real context (PD-0068 answer 3), states D-3 the same way if R7 declared it (R8 started only on the owner's acceptance), and takes every limit of section 7 (whose list includes D-3) and 3.3's list of what a withdrawal does not cover, and records the loader-login sequence that R8 followed (3.3 item 1) | R5 to R7; owner approvals; the `SOURCES.json` update (R4a); **one valid sidecar per member, three (R4b, 6.1)**; `valid_until` not past; **the owner's recorded answer to 8.1 item 11 (if it is not an acceptance, R8 does not start)**; **R7's exit statement on two-user isolation and, if it declares D-3, the owner's recorded answer to D-3, which must be an acceptance (a silence is not an answer; with no answer, or an answer that is not an acceptance, R8 does not start: conformance R3C-L3 and R3R-L3, the narrower of the reviewer's two fixes, which treats D-3 as item 11 is treated)** | The accepted NAV against the Quant's oracle; the first `synthetic = false` records; the first-run observations listed below | Not an F1 deliverable; listed for sequence |

Dependency order, re-checked against what each increment uses: R0; then R1 and R4a (R4a needs R0,
`market-data/1.16`, now committed, and the `SOURCES.json` update); then R2 (needs R1); then R3 (needs R1, R2) and
R4b (needs R1, R2, R4a); then R5 (needs R2, R3, R4b); R6 (needs R1, R3); then R7 (needs R3, R5, R6 and
the contract reviewed with R5); then R8. Nothing in R1 uses an object built later (the scope core and
the switch are in R1; the proposal format and its writer are in R1 and R4b conforms; R1's in-flight work
is a read-only-phase lease, so it needs neither the guarded load of R2 nor the fence and seal of R3).
R3 makes no service call (R5 does). The sidecar reader and O5 are built in R4b. The scoped contract is
authored in R5 and installed in R7. R8 installs the database before it qualifies, because qualification
writes `md_*` rows through the loader role **[E17]**. **R6 needs R1 and R3 only because all gateway SQL
is built by R3** (R1 the authority core, R2 the guarded load and the loader's grants, R3 the seal, fence, row
policy, validation and storage, the lease-checked `md_*` read functions of PD-0069, and the TEST-only
fictional-branch part, which a REAL install does not hold); R4a, R4b, R5 and R7 add none (technical TR3-L6;
R5's `lease_checked` keyword is Python). A gateway change after R3
reopens R3's review and re-runs the catalog audit (R3's function, run by R6's installer) before R8. The
admission probe (R7) calls the gateway's existing admit and adds no SQL. **R2's gate on 8.1 item 12 is met**
by the owner's answer (PD-0070 decision 1): the loader's list stays as 3.3 has it, and R2 fixes it. R2 still
follows this design's commit and R1.

**R8 first-run observations, by E9 item** (E9 `:111-115`, post-run acceptance evidence; the translation
is mine). These need a service-accepted commit, so no increment before R8 supplies them on the product
path:

- the actual service's `synthetic = false` and F8B dry run with full binding (the passing sides of O1
  and O4; T06);
- a real non-zero security valuation and the complete reporting NAV, and the independent exact
  comparison with the Quant's oracle;
- same-transaction persistence of the real root, revision, artifact and operation (T06);
- exact-201 replay, idempotency and archive read on the real commit (T08), and reproduce;
- the real root listed with its stored labels and not as synthetic (R3, R7), and the 7.4 wording
  rendered from the real lineage (R7);
- behaviour of the real root after a physical restart, and the PG, API and browser run;
- the independent technical and design review and the PM conclusion.

**E9's other post-run evidence, and what R8 collects on the real context** (conformance re-review
DC-L2; **the owner's answers are PD-0068 answer 3**). E9 `:111-115` also lists two-user isolation, negative
and rollback cases, revocation and expiry, and the correct error digest, and requires them to be collected
after the run. R1, R5 and R7 exercise them on invented data. On the real context:

- **collected there, writing nothing economic:** the correct error digest on a refused request; negative
  cases that are refused before any write (an idempotency conflict; a request for a foreign owner's root,
  which returns the generic 404, including **two-user isolation if the real-mode app can hold a second
  user without an economic write**; R7's exit states whether it can, and if it cannot, isolation is a
  third declared deviation, D-3, which is put to the owner through the PM before R8: conformance R2-L4.
  **D-3 gates R8** (conformance R3C-L3, R3R-L3): R8's Needs (7.1) include the owner's recorded answer to it,
  and R8 does not start unless that answer is an acceptance, so isolation cannot drop out; 7 lists it among
  the accepted limits, so the HG4 package cannot omit it);
- **collected there, as the last step of the run: revocation (decided: "Yes, test it (Recommended)").**
  The owner (1) **withdraws**, so that all four rights (create, read, export, reproduce) are shown refused,
  then (2) **renews**, so that the context is live again. Each is a separate publisher act of the owner
  citing its own decision record (PD-0066 decision 7). It costs two real generations. The renewal keeps
  `valid_until` at 2027-09-01 (an equal date, 3.1 / E25) and carries one basis entry per member source (the
  three of 3.1). It comes last because nothing can be read or exported while the context is withdrawn. The
  withdrawal is not gated by the preflight; the renewal is (1.2 rule 5.1).
  **How "all four rights refused" is shown, and by what** (conformance R3C-L2; technical TR3-L8). The scoped
  contract covers create, read, reproduce and the list (2.4), and a real export purpose is later work
  (7.3), so export has no route to try. After the withdrawal:
  - **create, read and reproduce** are each requested at the real-mode routes and each shows its refusal
    code; the **list** shows the root with its per-root refusal status (2.4);
  - **export** is shown refused by a **direct gateway admission**: the admission probe (R7, E27) is run
    for `ARCHIVE_EXPORT` on the HG4 context through the executor connection, prints the refusal code, and
    rolls back. The R8 plan includes it, the credential holder is the one R6's plan names (1.2 rule 4), and
    the probe's output and the HG4 package label it "direct gateway admission, not a product route". Run
    before the withdrawal it shows the right admitted (the positive control), also rolled back;
  - **`evidence_pack real` is not the export check.** It builds a pack from the files on disk and is
    unaffected by a withdrawal (3.3, W12); its success must not be read as the withdrawal having failed, and
    it is not used as an observation of the export right in either direction;
- **D-1, an accepted deviation: expiry is not observable on the real data.** `valid_until` is 2027-09-01 and
  the clock has no test hook (E3), so expiry and lapse are shown on invented data only (R1);
- **D-2, an accepted deviation: rollback after writes is not forced.** The real run commits once. Rollback
  is shown on invented data and crafted bundles only (R1, R3, R5; 4.4).

**D-1 and D-2 are accepted deviations from E9's post-run list** (PD-0068 answer 3: "Accept both"). **The
HG4 package states both as not collected on the real context**, and nobody should assemble it as if they
were. **The package also takes every limit of section 7, as that section lists them** (conformance R4R-L1 and
technical TR4R-L2: no list is repeated here, so that none can drop out of a copy of one; the earlier
parenthetical list omitted a limit), **and 3.3's list of what a withdrawal or lapse does not cover**, so that
"all four rights shown refused" is not read as "no stored data is readable": the raw files, the download tool,
the legacy tools, a staging store and the proposal files stay readable, and the loader's reads are open inside
a load window the owner opens (3.3). Section 7 carries the loader's login limits in PD-0070's words, so the
package takes them from there; it records the sequence R8 followed for the loader's `NOLOGIN` and `LOGIN`
(3.3 item 1) and states that it is an owner procedure that no tool enforces (E29 only prints the state, 1.2
rule 5.3 (g)). The package also states that the export right was shown
refused by a direct gateway admission and not at a route. PD-0068 requires the statement for D-1 and D-2;
section 7 makes the whole list a rule for the F1 closure statement, and the package carries the same list
(conformance R3R observation: the earlier wording called this a recommendation). The main session assembles
the package.

### 7.1a R4a in detail

1. **`M` holds no corporate-action file.** PD-0066 decision 2 (Ruling 6.5, OP-2 a); the split
   downloads are deferred (PD-0067 decision 5, OP-3). The F8B confirmation-policy digest is still
   carried: the policy must be valid whenever it is configured, whatever `M` holds (Ruling 6.5 item 3
   and 6.4d item 1). Example 6-E leaves the real policy ids to "the engineer and PM"; R4a's plan
   proposes them and the PM decides.
2. **Identity.** The exchange-level FIGI `BBG000B9Y5X2` for AAPL on XNAS, observed via `exchCode UW`
   (PD-0066 decision 4). The same record carries composite `BBG000B9XRY4` and share-class
   `BBG001S5N8V8`. **The Quant's A.6 update is done** (conformance R3C-L6): `market-data/1.16`, committed
   `ae6dfdc`, moves `UW` / XNGS from `MEMORY` to `OBSERVED` (`methodology/CP2_MARKET_DATA_CONVENTIONS.md:56`,
   read today). **What is pending is the engineer's code change, in R4a:** `exchange_codes.py:82` still has
   `UW` as `MEMORY`, and only `OBSERVED` or `CONFIRMED` entries attach a FIGI (`:28`), so nothing is attached
   today. The PM need not dispatch the Quant for it. Ruling 7.3 governs how the listing is bound; I do not
   restate it.
3. **Calendar.** The NYSE calendar file (6.3).
4. **Label source.** `DECLARED`, by the owner's reading of the live Alpha Vantage documentation
   (PD-0066 decision 3). The Quant recorded it in `market-data/1.16` (committed `ae6dfdc`; its change note
   lists the owner's readings of 2026-10-24, PD-0066 decisions 2 to 4); the engineer then updates the
   source profile and the label string, and both are reviewed (open item 2). The manifest stays
   `UNDECLARED` (6.1).
5. **Records outside the engineer's paths.** The `alphavantage.us` terms-check update in
   `SOURCES.json` for the PD-0066 decision 5 reading, and the sidecar records (6.1; R4b builds their
   reader and O5, and R8 needs one valid record per member). The main session writes both.
   **The `SOURCES.json` update gates R4a's exit and R8.** The snapshot freezes the source
   records it was published with (2.1), and different content is a different context (2.2). If the
   qualification run imported the 2026-10-01 record without the reading, correcting it later would
   change the content hash and strand the HG4 root on a new context. The registry has no field for the
   expiry basis (fact 15), so that evidence travels in the publish command and not in this record.
6. **The code label.** It is `market-data/1.15` at HEAD (fact 14). After the 1.16 changes land in code,
   the label names 1.16, before any real release is built (open item 3).

### 7.2 What reopens or stops the slice

- Notice of non-renewal or termination, or a lapse: the owner withdraws (3.1).
- A change in Alpha Vantage's terms: the reading is of 2026-10-24 with no version shown. **Recommendation
  only, not a rule:** the owner may wish to re-read the terms when recording a renewal. PD-0066
  decision 5 requires only that a human records the renewal, and nothing in R1 checks that a re-read
  happened or refuses a renewal for lack of one.
- A reviewer finding on this revision or on any increment.
- The owner reopening any of D1 to D7: the decision, not this file, changes first.

### 7.3 What can follow later

- **A-shares** (PD-0063, PD-0067). The CN calendar is registered; no A-share price is admitted.
  `alphavantage.cn` is `TO_OBSERVE` and `PRIMARY_ORDER["CN"] = ()` (`profiles.py:275, :299-300` at
  HEAD `7effcc8`, fact 14). The
  intended order is Alpha Vantage alone (OP-1 b). Admission needs the Ruling 7A.3 (c) observations
  from the approved plan (OP-4), whose listings and requests the owner names later, and then a final
  owner decision in a reviewed increment. An A-share `fetch` route in the download tool is a separate
  engineer increment (the tool refuses non-US forms today, `download.py:118-126`). A-shares mean a new
  snapshot, context and root (2.2).
- **Filing sources** (cninfo, SEC EDGAR; OP-6): registration after the owner's terms readings; agent
  drafts of filing records from owner-supplied text, confirmed by the owner. **Split downloads** (OP-3)
  are deferred.
- Real CSV import (W09); ledger append and correction on real roots (W08, W10).
- More than one context or head (FF1-C07).
- Agent-acquired v2 wiring (proposal :420-430); a real export purpose and the legacy CLI (W12);
  restore and maintenance drills; full publication fault injection.
- Hong Kong: dropped from the personal-use plan (PD-0063 addendum); still a V1 obligation.

### 7.4 Claim limits carried into the R5 output and the R7 UI

From Ruling 6.5 items 5 and 6 (`methodology/CP2_MARKET_DATA_CONVENTIONS.md`, `market-data/1.15` as
committed at `44a40e8`: I read it with `git show HEAD:` in the earlier rounds), with the review finding
F-2 closed. **`market-data/1.16` is now committed (`ae6dfdc`) and I did not re-read Ruling 6.5 in it in
round 3**; R5, before it builds the claim text, compares items 5 and 6 of Ruling 6.5 between 1.15 and
1.16, and this list changes with any difference. Item 9 of 1.16 adds claim N-8 (C6 below).

**Where the text is rendered.** The list below is a template with slots filled from the lineage
fields. The real-source sentences (Alpha Vantage, the XNAS session close, the owner's reading) are
produced **only when `market_origin = REAL_SOURCE`**. Under a test scope the same slots render the
invented-data mark ("invented test data; no claim about any real source"), and the real sentences never
appear, because 4.3 forbids any statement about a real source over invented data. R5's and R7's
tests check the slots, the mapping from lineage and the absence of the real sentences over test data.
**They also test the claim-limit text itself before R8** (conformance re-review DC-M3), on a pure render
over an in-memory `REAL_SOURCE` fixture that is never stored or served (4.3, last paragraph; "Tests of
the claim-limit text" below). The real wording rendered from the real lineage is first checked at R8.

The result **may say** (slots S1 to S5):

**Corrected by O-7 (2026-11-10; the Quant's ruling `methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md`, owner's answers PD-0082).** The bullets below are the text as built; where
they differ from the first version of this section, the ruling and the built text win. What changed and why:

- the **valuation date and the price session are two fields**: they are different whenever a session is missed, so one field made C-1 or C-2 false (the ruling, section 4);
- the **reading date of the vendor's documentation is not stored as data**, so C-1 cites the record that holds it, `PD-0066 decision 3` (PD-0082 Q2), and never a date;
- the engine's lineage does **not** state the label status, the label source, the exposure window or the V1 statement (`market-data/1.16` Ruling 3.2 item 5 is not built; `UNBUILT_1_16`
  in the manifest's open items), so S5 names the **stored record of the result**, not "the lineage", and gives the window by its two arguments, not as a session list;
- S4 names **every file of `M`** (the snapshot's members, with kind and source), not only the files consumed, and **both convention sets**;
- the stored amount of cash is text without trailing zeros (`500`), so S3 renders `10 x p + 500`, not `500.00` (Ruling 2.2 (1.12) item 7: the same assertion).

**Where the fields come from (the ruling's section 1).** Every field is copied, never computed, from one of three stored homes: **(I)** the issued document, **(R)** the stored response, and
**(K)** the **claim record**, an object `claim_record` inside the stored response that the REAL create builds from the values the computation used (the snapshot, the release's files read
through the lease-checked `rw_md_file`, the lookup of the one holding on the world's port, the profile table) and that the seal stores with the root (PD-0082 Q1; no SQL, migration or
installer change). A reproduce rebuilds (K) from the same inputs and compares it byte for byte with the stored one (`RESULT_DIFFERS`, "claim record differs"). The extractor is
`marketdata.claim_record.lineage_of(archive)`; no field value is read from a code constant, a clock or a default; the preconditions compare stored values with the method's constants, and P-5 also checks,
at every read, that the engine still has Test V4 unbuilt (C-1 and C2 say in the present tense that no V4 record exists).

**Preconditions of the fixed text (the ruling's 3.4; checked in the extractor, so before any text renders).** The sentences are true only under these: P-1 the label status is `UNVERIFIABLE`;
P-2 the label source ends `:DECLARED` and the profile's status for the call is `DECLARED`; P-3 the reconciliation status is `SINGLE_SOURCE`; P-4 no member of `M` is a `CORPORATE_ACTION` file
(then the V1 statement "no V1 event in `M`" holds by definition, Ruling 3.2 item 5 case 3; a corporate-action file refuses the block, because cases 1 and 2 need item 5 built and the by-hand
check of item 6 made); P-5 (by the marker `Ruling 3.3, Test V4`, not the line's exact text) the stored manifest holds exactly one `market_data: ` open item with the marker and the engine's `UNBUILT_1_16` holds exactly one line with it;
P-6 `market_data.convention_set` is `market-data/1.16`; P-7 a real-source root with one position and one
cash balance; P-8 the NAV state is one of the three; P-9 the holding's `NATIVE` row trades in the reporting currency (no FX leg; both variants); P-10 (withheld variant only) the claim record holds no
valuing reading and no holding row has a `price_date_used`. **A failed precondition, a missing, malformed or ambiguous field, or two NAV rows refuses**: the REAL create is refused **before the
seal** with `RW_CLAIM_RECORD_REFUSED` and rolls back whole (PD-0082 Q3), and a stored root that cannot render its block is read as `REAL_UNAVAILABLE`; no number is ever shown without its
block (P3).

**The withheld variant (O-6; PD-0082 Q4).** Over a real NAV in state `INSUFFICIENT_DATA` no close values the holding, so C-1, C-2, C-4 and C-6 would each say something false. The block has the **same
twelve ids** and a different text for S1, S2, S3, S5, C1, C2 and C3 (claim ids `C-1X`, `C-2X`, `C-6X`, `N-1X`, `N-4X`, `N-5X`): S1 says no holding value is stated; S2 that no label source is stated; S3 gives the
state, the cause (the NAV's reason code, or its details), freshness and delay and no NAV; S5 that no label status, exposure window or V1 statement is stated; C1 to C3 say that no price series
is verified, that no close was used, and that no close was compared. S4 and C4 to C7 are the normal text. Only P-6 to P-10 apply (not P-1 to P-5). The partial figure PD-0035 requires is then shown with its block.
`AVAILABLE` and `LIMITED` (2 to 4 missed sessions) show the normal block with the split dates. Any other state refuses.

- (S1) the holding value on the **valuation date** is `10 x p`, where `p` is the close that the vendor's call (`TIME_SERIES_DAILY`; the source's name and the call are
  copied from the snapshot's source record and the file's manifest) delivered for the **price session** (for example the 2026-09-30 XNAS session), with the **number of sessions of
  that exchange missed** after that close up to the valuation date, read as as-traded (`RAW`) on the vendor's documentation of the call, as the owner read it (`PD-0066 decision 3`);
- (S2) the label source as the stored record states it: the whole string, `PROFILE_CALL_ADJUSTMENT:<source>:<function>:DECLARED` for the HG4 case, which ends `DECLARED`. It is
  the owner's reading of the live documentation (PD-0066 decision 3), a vendor declaration, not a check against the exchange (Test V4) or a filing (V1). It is copied from the
  reading's own ingest lineage, never hard-coded, and a stored result that cites 1.15 or earlier says `MEMORY` (and then P-2 refuses this block, which needs different wording);
- (S3) the NAV on the valuation date is `10 x p + 500` USD; state, freshness and delay as the NAV row states them (`AVAILABLE`, `CURRENT`, `END_OF_DAY` for the HG4 case);
  reconciliation `SINGLE_SOURCE`, copied from the lookup that valued the holding;
- (S4) the inputs are named: **every file of `M`** (`<kind> <source> <sha256>`, in the snapshot's member order), `L` (the ledger version, as digits) and **the two convention sets**
  (`market-data/1.16, performance/1.12`);
- (S5) the stored record of the result states the label status and the label source of the reading used, the exposure window `E(<price session>, <R>)`, where `R` is the file's
  retrieval time exactly as its manifest writes it, and "no V1 event in `M`" (V1 is the split-day jump test, Test V1) (Ruling 6.5 item 6; Ruling 3.2 item 3). The session list of the window
  is not stated (item 5 is not built). A reader can then tell which method produced the output and what was left unchecked.

It **must not claim** (items C1 to C7):

- (C1) that the series is verified as-traded. Its **split label is `UNVERIFIABLE` and its dividend
  component is `UNVERIFIABLE`** (Ruling 6.5 item 6; A.3);
- (C2) that `p` is Nasdaq's official closing-cross price;
- (C3) a comparison with any other source;
- (C4) that the listing had no split, or that split history is complete or verified, in any period;
- (C5) anything about a `SPLITS` response, because no corporate-action file is in `M`;
- (C6) that the quantity 10 is verified (it is the ledger fact), and the output never calls it the user's
  holding: it is the project-constructed ledger's quantity (claim N-8, `market-data/1.16` item 9
  condition 5; the portfolio is a project-constructed, non-personal test account, 1.1);
- (C7) anything about another date, a return, performance or risk.

Dropping these caveats changes the conclusion (P3).

**Tests of the claim-limit text before R8** (conformance re-review DC-M3; they replace the proposal's
"UI test that the claim limits are shown", proposal :453, which the final check relied on,
`reviews/TECH_REVIEW.md:14203`). The renderer is a pure function of the lineage fields, the locale and
the depth: no connection, no network, no clock. Each test feeds it an **in-memory lineage fixture** with
`market_origin = REAL_SOURCE`, built inside the test, never stored, never served, never passed to a
store or a route, with placeholder slot values and no market number (4.3).

- **R5**: the claim-limit block of the output (identifiers and slots) is complete for the `REAL_SOURCE`
  fixture: every C-item C1 to C7 is present and every S-slot S1 to S5 is filled from its lineage field.
  The test removes each item in turn and fails each time. Over a `SYNTHETIC_TEST` fixture the block carries
  the invented-data mark and no real-source sentence;
- **R7**: for EN and zh, at each of the three depths, the rendered text for the `REAL_SOURCE` fixture
  contains every C-item, **including C1's "dividend component `UNVERIFIABLE`" and the single-source,
  no-comparison caveat (C3 with S3's `SINGLE_SOURCE`)**. A table lists the phrase set each C-item needs in
  each locale (reviewed with the zh strings); a depth may shorten wording, and the test fails if any
  required phrase is absent (P3). Over a `SYNTHETIC_TEST` fixture no real-source sentence is emitted;
- **O-7 (built 2026-11-10)**: `tests/product/test_claim_record.py` proves the extractor and the claim record on **engine-made, never-stored** inputs (`performance.engine.compute` over
  `performance_kit` worlds, the product's own `response_of` and `build_claim_record`), with the Quant's hand values as the expected values (the ruling's 9.2: `AVAILABLE` as of 2025-03-28,
  `LIMITED` as of 2025-04-02 with 3 missed sessions, the withheld case); every precondition failing alone; the reproduce comparison; the route end to end. PostgreSQL: the refusal rolls back
  with nothing stored, the file read is lease-checked, and a response carrying `claim_record` seals unchanged. The client's English professional templates are held equal to the server's text
  for both variants (`ClientTextAgreesWithTheServerTests`);
- what these tests do not show: the text rendered from the real lineage in the real UI, the real `md_file` manifest and `md_quote` lineage values, the real source record and the real pin.
  That is first checked at R8.

## 8. Open items

### 8.1 Genuinely open

1. **Answered: the Quant's `state_kind` confirmation** that `ACTUAL` plus the origin fields is the
   intended encoding (1.1). The Quant confirmed it in `market-data/1.16` item 9 (`CP2:3655`), with five
   conditions that 1.1 now carries. R0 has no open piece left.
2. **The `market-data/1.16` code follow-ups.** 1.16 is committed (`ae6dfdc`). Its three follow-ups
   (PD-0066 decision 10) are not yet applied to code:
   - the label source `MEMORY` to `DECLARED` (decision 3);
   - A.6 `UW`/`XNGS` `MEMORY` to `OBSERVED` (decision 4);
   - "dividend component UNVERIFIABLE" among the Ruling 6.5 claim limits. The committed 1.15 already
     says it in the item 6 table; 7.4 carries it.

   Applying them is an engineer increment after review (R4a). At HEAD `7effcc8` the label string ends
   `:MEMORY` at `adapters/daily_csv.py:155-156`, the `MEMORY` comment is at `profiles.py:260`,
   `exchange_codes.py:82` maps `UW` with `MEMORY` and `TABLE_VERSION` is at `:22` (`market-data/1.5#a6/1`).
   The label string enters the canonical lineage (`canonical.py:111`), so it can change digests; I did not
   check how far. Until applied, the code says `MEMORY` and `UW` does not attach.
3. **The code version label.** It is `market-data/1.15` at HEAD `7effcc8` (`profiles.py:24`; fact 14).
   1.16 is committed in the methodology, but no code names it. No real release may be built before the
   1.16 changes of item 2 land and the label names the method the code runs (P12, NFR-001; PD-0067
   decision 6) **[E12]**. I still have not seen the label track's own diff or tests.
4. **Answered: `valid_until` stays 2027-09-01** (PD-0068 answer 4: "Keep 2027-09-01"; PD-0066 decision
   5). The owner did not pin the term start from the signup email. The consequence is the disclosed
   upper-bound limit in the HG4 block of 3.1, which the owner accepted knowingly. Pinning the signup date
   later, from the Alpha Vantage account, would remove the limit; it is an option, not a task. **What the
   pin remedy requires** (conformance R3C-M1; technical TR3-M4): the owner records a renewal that carries
   the pinned term end and a `valid_until` not later than it. If that `valid_until` is earlier than
   2027-09-01 the renewal is a **date correction**, which E25 allows (the first form of E25 forbade an
   earlier date and would have blocked it in the one case where it matters; it is withdrawn). A new
   `valid_until` must be ahead of the server clock. If the pin shows a term that has already ended and no
   notice was given, the licence has renewed (PD-0066 decision 5, reading (2)), and the owner records a
   renewal for the Renewal Term, not a withdrawal (3.1, R3R-L2). The owner's premise in PD-0068 answer 4
   ("would remove the limit") therefore holds, with that condition. The owner is told that E25 changed (the
   PM list below).
5. **The pre-R8 evidence limit of option (a)** (4.4): no service-accepted NAV, and so no end-to-end
   accepted seal, commit, archive or reproduce **of the real branch**, can run before the real run. The
   owner's choice stands. 4.4 marks each of T06 to T09 as product path, E11 crafted probe or first run at
   R8, and R8 lists the deferred observations by E9 item. **Answered by both re-reviews:** enough for R3's
   and R5's exits as refusal-and-rollback and binding evidence; not a re-proof of the ACK-loss ordering
   or of any accepted-path ordering, which R3's and R5's exits must not claim (4.4). The ACK-loss limit
   was accepted in PD-0068 answer 2. Round 3 narrows the part of the limit that is the post-seal tail
   (4.4, "Step 1"), and what remains of it is item 11.
6. **Placement and credentials of the real database**, under the install rule of 1.2: which cluster
   (its own, preferred, or a shared one where every role authenticates by password, which needs its own
   approval), who holds the executor and loader credentials, that the owner alone holds the superuser
   password and sets the publisher's (2.5), the `pg_hba` lines (1.2 rule 1: no `trust`, `peer` or
   `ident` for any role), where the data directory lives, whether the owner accepts the checkable-versus-
   procedure split of the password stores (1.2 rule 2, which says what the database cannot enforce), and
   the exact install plan. Decided at R6 with the owner's go-ahead. **This is an owner-approved
   environment step; the existing test tooling must never be pointed at the real cluster, and the
   preflight (1.2 rule 5) guards REAL installs only.**

**Answered by the owner in PD-0068 (2026-10-24), formerly items 7 to 10.** The decided design's open
questions are no longer open. The text reflects the answers as the owner gave them (verbatim words are in
`decisions/product/PD-0068-f1-design-open-questions.md`):

| Former item | Owner's answer (PD-0068) | Reflected in |
|---|---|---|
| 7: may an admitted operation finish after `valid_until`? | Answer 1: **"(b) No, cap at the end (Recommended)"**. `complete_by = LEAST(admitted_at + W, valid_until)` for every lease; `W` stays an install constant. Not claimed: that nothing commits after `valid_until` (the commit-processing gap and a guard-bypassing executor stay disclosed limits; X2 stays UNSUPPORTED) | 3 intro; 3.1 (in-flight, lapse, margin and renewal rows); 3.2; fact 17; E4, E25; 7.1 (R1); section 9 |
| 8: the full lost-acknowledgement sequence cannot be exercised before the real run | Answer 2: **"(i) Accept the limit (Recommended)"**. The end-to-end ordering is not re-proven before R8; it is first exercised at the real run, if it occurs there. No rehearsal install. R3's and R5's exits claim only what they show | 1 (item 5); 4.4 (table and "What each exit may claim"); 7.1 (R3, R5, R8); section 9 |
| 9: D-1 and D-2 as declared deviations; revocation on the real context | Answer 3: **"Accept both"**; **"Yes, test it (Recommended)"**. D-1 (expiry not observable) and D-2 (rollback after writes not forced) are accepted deviations. R8's last step is withdraw (all four rights shown refused) and then renew, each an owner publisher act citing its own decision record; the other collectible E9 items are collected on the real context | 7.1 (R8 and the block after it); 2.5 |
| 10: the expiry basis per source for the first HG4 publish | Answer 4: **"As proposed (Recommended)"**; **"Keep 2027-09-01"**. `alphavantage.us` `LEASE_TERM` (`term_end_not_after` 2027-10-01T00:00:00Z), `openfigi` `NOT_ASSESSED`, `calendar.manual` `NOT_ASSESSED`; kind `LEASE`; `valid_until` 2027-09-01. The upper-bound limit is disclosed as PD-0068 states it | 3.1 (HG4 block); 2.5; 7.1 (R8); E14 |

11. **New, for the owner: the residual of the post-seal tail before R8** (technical review TR2-M1).
    PD-0068 does **not** cover this; answer 2 accepted the ACK-loss limit, which is about the end-to-end
    ordering, not about whether the real branch's seal, by-name firing, COMMIT and classification have
    run before the real commit. Round 3 gets most of the tail through a proof inside PD-0066 decision 8:
    the tail is one function shared by the real create and the `SYNTHETIC_TEST` create, and R5 runs it on
    an accepted `SYNTHETIC_TEST` create (4.4 Step 1, tests T-a to T-g, the last two for the read,
    reproduce and list paths). Nothing is marked
    `synthetic = false` and no refusal is bypassed. What stays unshown before R8, and so would be first
    exercised by the real commit (4.4 Step 2), is:
    1. the real branch's seal on an accepted `synthetic = false` result (the passing sides of O1 and O4);
    2. any deferrable constraint, write path or row that only the real branch has, fired by name for the
       first time at R8 (expected to be none: R3's exit lists each branch's inventory, 4.4 Step 2, so
       the item may turn out empty or name the difference);
    3. the real commit's size and timing against `complete_by`;
    4. a stall drill or a fault drill on the real commit: none is proposed, because the real run commits
       once and a rehearsal install was declined.

    The real run is the first time the real branch meets its own COMMIT. If it misbehaves, the failure is
    the real run's: the classification is fail-closed (an unclassified outcome is UNKNOWN and nothing is
    retried), but the real commit is not rehearsed. **Please either accept this residual, in a record
    that R8 cites, or say that R8 does not start.** Within PD-0066 decision 8 and PD-0068 answer 2 the
    design has no further route to show more before R8.
12. **Answered by the owner in PD-0070 decision 1 (2026-10-25), formerly "what the loader credential may
    still read after a lapse or a withdrawal"** (PD-0069, "Not decided by this answer"). The question was
    "After a lapse or withdrawal, what may the market-data loader's login still read (design §8.1 item 12)?";
    the owner's answer was **"Off between loads (Recommended)"**. PD-0070 records the option texts. What it
    means in this design (3.3 has the procedure and the reads; section 7 has the limits in PD-0070's words):
    - The owner sets the loader role `NOLOGIN` right after its last use in R8, and `LOGIN` again only for a
      later load. Each is an owner act in the owner's own terminal, and no tool enforces it. Where the last use
      falls (3.3 item 1; conformance R6C-M1): under N2a's binding the loader registers the context-bound
      candidates after the publish, so it falls between the publish (4) and the real run (5), step (4a) of 7.1,
      and not at the end of the qualification run. R2's exit states whether the real registry binds so, and
      R6's plan states the sequence, one window or two.
    - Between loads no new connection as the loader succeeds, whether the context is live, has lapsed or was
      withdrawn. **Outside a load window the owner opens, nobody can log in as the loader, whoever holds its
      credential** (conformance R5R-L1). Inside a window the holder R6's plan names (1.2 rule 4 allows an agent
      session) can read what the loader's narrowed list allows: the file manifests and the release definitions,
      and, through the registry's get function, the raw payload bytes, the Alpha Vantage closes included (3.3).
    - The loader's list stays as round 5 narrowed it. The owner did not take option (c), and the count
      read-back (d) was not offered.
    - The limits, as shown to the owner and accepted with the choice: it stops new connections only, and
      whether `NOLOGIN` ends a session that is already open is not shown; the superuser and the owner role are
      not affected; each later load needs the owner's `LOGIN` step.
    - R2's gate on this item is met. R2 still follows this design's commit and R1.
    - Whether a tool reports the loader's login state is my proposal E29 (5.3 (g)), a print and nothing more,
      for review.

Pending reviews, which are gates and not questions: the technical-reviewer's check of this round-6
revision before R1 (PD-0066 decision 10, followed by the commit the owner asks for;
the findings to re-check are those named in section 16); the switch as
its own item in R1's review (it is built in R1); the `md_*` read functions and the audit's per-role
comparison (2.6 item 6, 1.2 rule 5.3 (e)) as their own item in R3's review; the new scoped contract, with its list route, as an item
of R5's review, before R7 installs it; the install rule of 1.2 and its preflight, including the probe's
test cases (1.2 rule 7), as their own item at R6, and the gate as the launcher and the probe use it as an
item of R7's review; each increment before it is committed.

**For the PM to record** (not decided here):
- the owner-approved move of the OpenFIGI duplicate (fact 13) is recorded in STATUS.md (item 11,
  "Owner-approved data move") but in no PD that I found;
- PD-0068's summary of R3 ("R3 can show UNKNOWN, no retry on a crafted commit") needs a small correction:
  R3 has no outcome code, so that test is R5's (4.4, "What each exit may claim"). The owner's answer is
  unaffected;
- PD-0068's summary of R5 ("correct classification of committed, rolled-back and UNKNOWN states by the
  reconciliation code") needs the same kind of correction: reconciliation classifies committed and UNKNOWN
  only; a rolled-back result comes from a create call's own definite refusal, never from absence (4.4,
  conformance R3C-L5). The owner's answer is unaffected;
- **E25 changed, and the owner is to be told.** A renewal may now carry an earlier `valid_until` (a date
  correction), so that the pin remedy PD-0066 decision 5 and PD-0068 answer 4 describe works. This is my
  mechanism and no PD says it; it narrows a lease with the same record a renewal needs. An owner who would
  rather have the first form (no earlier date) must say so, knowing that the lease then cannot be moved
  earlier: the lapse stays at the old date unless the owner withdraws (all four rights off; a withdrawal is
  for notice or termination, PD-0066 decision 5) or uses a new context, which strands the HG4 root (2.2)
  (3.1, 8.2 E25) (R3R-L2; STATUS.md's E25 bullet already carries the corrected wording, so nothing is left to
  correct there: R5C-L2);
- **a fourth real tool, the admission probe (E27, R7).** It is how R8 shows the export right refused,
  because the scoped contract has no export route. If the owner prefers that export not be shown at the
  gateway, the HG4 package must say that only three of the four rights were shown refused (7.1);
- **D-3 gates R8** (7.1, R8's Needs): if R7 declares it, the PM puts it to the owner and R8 waits for the
  recorded answer; an answer that is not an acceptance stops R8, as item 11's does (R3R-L3);
- **PD-0070 decision 1 (the loader's login) is reflected as the owner decided it** and puts owner acts into
  R6's plan, which item (vi) below lists. E29, the print of the real roles' `rolcanlogin` in the preflight
  output (5.3 (g)), is my proposal for the reviewer: a print and nothing more, no refusal rests on it, and
  deleting it changes no other claim;
- **for the owner's reading of R6's install plan** (item (v) asks the owner's preference; the rest is for
  reading): (i) the real installer does not
  apply the fictional-branch functions (PD-0066 decision 6, "only a real-only gateway", kept literally;
  R3R-M1). R3 and R6 show that about the installer's lists; **nothing reads a REAL catalog before R8 step 1**,
  where the installer's Phase 2 runs a catalog audit that refuses if such a function is present or if the
  table or function privileges of the executor, the loader, the publisher or `public` differ from that
  role's own list, `MAINTAIN` included (TR4-M2, TR4R-M2, TR5-L1; a mechanism of mine, 14.1, widened in section
  15; it compares at table level, since no list names columns, and a column-level grant is seen where the list
  gives the role no privilege on that table: TR5R-L1; it does not compare privileges on sequences or
  schemas); the installer revokes PUBLIC's `EXECUTE` on every routine of the schema, because the HEAD
  migrations leave it on twelve functions (TR5-L2), and a migration applied later to an installed database
  needs that statement re-run (5.3 (e)); (ii) the preflight has no exemption lists: a LOGIN role's
  membership in any role refuses, so a shared cluster whose other roles hold memberships fails it (TR3R-M1);
  (iii) the sandbox exception asked for at R6 buys the classifier's calibration and nothing else. **A wrong
  refusal in Phase 0 stops R8 step 1 before anything is created; a wrong refusal in Phase 2, or at a tool's
  first gated start, comes after the real database, the four roles, the gateway and the passwords exist**
  (no content yet): the owner waits for a reviewed fix and re-runs `--check`, or drops and reinstalls, or
  approves SQL in the existing database (TR4-L1; 1.2 rule 7); **a Phase 1 failure leaves a partial install
  with no content, with the same owner options** (TR4R-L3), **and that nothing is used until a refusal is
  resolved is the owner's procedure: no tool enforces it** (1.2 rule 7); (iv) grants are audited by Phase 2
  and `--check` and not at each gated start; no real role has a role-level setting, and no LOGIN role of the
  cluster, nor `public`, may `SET` or `ALTER SYSTEM` `session_replication_role` (TR3R-L2, TR4-L2, TR4R-L1);
  (v) `withdraw` connects without
  `require_auth`, so it would answer a server's request for a cleartext password and send the publisher's
  password to whatever answers on the socket path (an impostor inside the trusted-operator boundary). **The
  owner's preference is asked, among three:** no demand (as designed); `require_auth=scram-sha-256`, one more
  thing that can stop a withdrawal; or the negated `require_auth=!password`, which refuses only a request for
  a cleartext password and so would stop a withdrawal only where an `hba` line that rule 1 forbids exists or an
  impostor answers (`libpq-connect`; 1.2 rule 5.1). It bears on PD-0066 decision 7, and R6's plan states which
  the owner prefers (R4C-L4); (vi) the loader's login is off between loads (PD-0070 decision 1; 3.3). The owner
  sets `NOLOGIN` right after the loader's last use in R8, and `LOGIN`, then `NOLOGIN` again, for any later
  load, each in the owner's own terminal; no tool enforces it, and the limits are section 7's. **Where the last
  use falls depends on the real registry** (conformance R6C-M1): under N2a's binding the loader registers the
  context-bound candidates after the publish, so it is step (4a), between the publish and the real run, and not
  the end of the qualification run. R6's plan states for the owner's approval, after R2's exit says how the real
  registry binds: (1) the sequence, one window (the loader keeps `LOGIN` from the qualification run to (4a),
  across the review and the publish) or two (`NOLOGIN` after the qualification run, `LOGIN` again before (4a),
  `NOLOGIN` after it); (2) whether Phase 1 creates the loader role with `LOGIN` or with `NOLOGIN`, knowing that
  N2a's install check refuses a loader that cannot log in, so `NOLOGIN` at creation needs R2's check to accept
  it, or an installer ordering that R6's plan would have to design (3.3 item 3; conformance R6C-L1,
  technical TR6-L1); (3) who holds the loader credential during a load
  window (an agent session may: rule 4). The design names no tool that writes the registration after the
  publish: R4b's or R6's plan names it (3.3 item 1);
- the HG4 publish decision must repeat PD-0068's three basis entries and the upper-bound limit (3.1, 2.5);
- the calendar sidecar's reference (6.1) is for the main session to name;
- PD-0068 states `term_end_not_after` as `2027-10-01T00:00:00Z`, the later of the two readings of PD-0066's
  "on or before 2027-10-01" and, for an upper bound, the weaker one. The design records it as decided and
  nothing in HG4 depends on the difference; the main session may ask the owner whether the earlier instant
  (2027-09-30T16:00:00Z) is preferred (3.1, HG4 block).

### 8.2 Engineer's choices the PDs and contracts do not cover

For the reviewer, and the owner if they want to change any. Section references show where each is used.

| Tag | Choice | Where |
|---|---|---|
| E1 | The first refused instant is 2027-09-01 00:00 Asia/Shanghai, stored as a UTC instant; admission needs a strict `now < valid_until`. The earlier of two readings, so the more conservative | 3.1 |
| E2 | `valid_until` and the expiry basis entries live in the head and history, not in the hashed snapshot; a renewal is a new generation of the same context | 2.1, 2.2, 3.1 |
| E3 | The trusted clock is the database server's `clock_timestamp()` inside admit, with no override in any install. Admit reads the latest committed instant **before** it samples, and refuses a clock regression only if the sample is earlier. A forward jump fails closed; a backward jump is detected only below the latest instant | 3.1, 3.2 |
| E4 | **Amended in round 3 (PD-0068 answer 1).** An admitted operation may complete only until its lease deadline `complete_by = LEAST(admitted_at + W, valid_until)` for every lease, with a table `CHECK` (`W` written once by the installer; the real install's value is my proposal of 10 minutes, and it only shortens deadlines). The write fence, the seal, the guarded loads and, since round 4 (TR3R-L4), the read side of the rooted tables, the archive and the stored market data (the row policy's read branch, the archive read function and, by PD-0069, the `md_*` read functions of 2.6 item 6) enforce it at statement time with a strict `clock_timestamp() < complete_by`, so no session setting changes it. The **deadline guard** is a constraint trigger of its own, deferred, which the product create path leaves pending (it fires the other deferrable constraints by name and never issues `SET CONSTRAINTS ALL`), so it fires inside COMMIT; a client that fires it early defeats it (fact 17). An error at COMMIT carrying `RW_DEADLINE` with the connection `IDLE` is a definite refusal; any other error at COMMIT is UNKNOWN. **Not claimed: that nothing commits after `complete_by` or `valid_until`**; the disclosed limits are the commit-processing gap and a guard-bypassing executor, and X2 stays UNSUPPORTED. The design sets no role-level setting (the preflight refuses one on a real role or on the real database; an all-roles row is not refused, 5.3 (a)); the connection's timeouts are not the bound. A stalled holder is named by the withdrawal and ended by the owner role. The option with completion after `valid_until` is not a live path | 3.1, 3.2, fact 17 |
| E5 | Lapse is computed at each admission and writes no row | 3.1 |
| E6 | An install kind `TEST` or `REAL`, written once by the installer, gates the scopes in both directions | 2.1, 4.2 |
| E7 | A scope is (branch, origin axis); the switch changes only the axis, and `TEST_SWITCH` output stays synthetic | 4.2 |
| E8 | Creating the real database and roles is an owner-approved install step between R6 and R8, and R8 does it before the qualification run, under the install rule of 1.2 (E20, E24). **Amended in round 3:** the owner runs the real installer in their own terminal as the cluster's superuser, typing the password at a prompt; the TEST provisioner is a different tool and writes install kind `TEST` only | 1, 1.2, R6, R8 |
| E9 | With the OpenFIGI duplicate moved out of the store, the staging store is no longer required. I propose that qualification reads `data/marketdata` directly; R4b's plan may instead use a staging store of exactly the selected members, whose extra copy 3.3 then discloses | 6.4, R4b |
| E10 | Sidecar records live outside `files/` and are written by the main session | 6.1 |
| E11 | Before R8 the seal's acceptance is probed at SQL level with crafted synthetic-labelled inputs, and each such result is marked as a crafted probe, not product evidence. **Amended in round 3, corrected in round 4 (R3R-L1):** R1 also needs a crafted fixture for the root-link foreign key: in a disposable `TEST` database the owner role writes the `app_user`, `portfolio` and root-link rows directly (3.2, "R1's root fixture"); R1 has no fence, bundle guard or create, so `rw_admit(new_root = true)` is not used, and the fixture is marked the same way; R3 has no outcome code, so the product-behaviour half of the ACK-loss test is R5's (E23) | 3.2, 4.4, R1, R3 |
| E12 | The 1.16 label-source and A.6 changes land before any real release is built, and the code label then names 1.16 | 8.1 item 3, R4a |
| E13 | The decision reference is the PD id, the git commit holding it and the SHA-256 of the file at that commit; publish, renewal and withdrawal are refused without all three. The tool does not check them against git. PD-0066 decision 5 is a valid reference for a withdrawal on notice or termination | 2.5 |
| E14 | The expiry kind is derived from basis entries, **exactly one per member source** (`LEASE_TERM` with `term_end_not_after`, `NO_EXPIRY_READING`, or `NOT_ASSESSED`), whose source set is read from the members' manifests and stored in the hashed member tuples. `LEASE` needs a `LEASE_TERM`, a `valid_until` and **`valid_until <= min(term_end_not_after)`** (amended in round 3: relaxed from `valid_until + W <=`, which was written for the in-flight option (a); under the cap `W` has no part in the margin). The rule is a **plausibility refusal against an upper bound, not a safety margin**, and every record and screen words it so; the HG4 limit is disclosed in 3.1 (conformance R2-M1; PD-0068 answer 4), and the remedy PD-0068 names, pinning the term start, is carried out by a renewal that is a date correction (E25). `NONE` needs a human no-expiry reading for every member source. Anything else is `UNKNOWN`. Admit re-derives the kind from the stored snapshot and entries | 2.1, 3.1, 3.2 |
| E15 | The origin predicates O1 to O3 and O5 are independent functions that report every failed predicate, and take invented attestations by value only. In the real scope O2 does not exempt synthetic sources and O3 reads the member's own fields. O4 is a seal predicate; O5 (sidecar) is built in R4b | 4.2 |
| E16 | Origin labels follow the origin axis, not the branch. A test scope never carries `REAL_SOURCE` or a real-origin string, and a seal row guard refuses a mismatch | 1.1, 4.2 |
| E17 | Build order: the scope core, the switch, the deadline guard and the proposal format (writer and verifier) are built in R1; the guarded load in R2; the fence, seal and bundle guard in R3, with no service call; the sidecar reader and O5 in R4b; the world builder, service call and scoped contract module (with the list route) in R5; the contract is installed in R7; R8 installs before it qualifies | 4.2, 7.1 |
| E18 | A withdrawal first commits a drain mark, a row that carries the issuer, the decision-reference triple and the server time and cannot exist without them, which stops new admissions with `RW_WITHDRAWAL_PENDING`; then it waits for in-flight work. A timed-out withdrawal leaves the mark visibly pending and exits with a status of its own. Only completion or a renewal that names the mark ends it | 2.1, 3.1 |
| E19 | The publisher authenticates by a password the owner sets, never password-less or socket-trusted, never in a project file. A publisher password alone does not keep an agent out; see E20 | 2.5 |
| E20 | **Install rule for the real cluster. Amended in round 3:** a password (`scram-sha-256`) for every role; **no `trust`, `peer` or `ident` line for any role** (the round-2 wording said "no `peer` for a privileged role"; TR2-L1); `local` lines only; the cluster created with `initdb --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwprompt`; the superuser and publisher passwords the owner's alone, with a table that separates what the preflight can check from what is an owner procedure and says plainly what no check inside the database can enforce (TR2-M2); the data directory outside the sandbox's write paths; a REAL-only preflight (E24); the existing test tooling and the environment-driven tests never pointed at the real cluster, with name tripwires for a `finweb_real` namespace and the residual stated. Preferred placement is a cluster of its own. **Amended in the round-3 fix round:** the real installer revokes PUBLIC `CONNECT` on `postgres`, `template1` and any other connectable database of its cluster, and the preflight refuses on any `CONNECT` a real role holds elsewhere (TR3-L3); on a shared cluster the superuser-driven test tooling could never run again (TR3-L5), and **round 4** removes the approved lists (5.3 has no exemption; TR3R-M1); the static credential scan and the membership rule are E26; `CHALLENGED` and `REJECTED` are calibrated at R6 against real refusals only if the owner grants the sandbox exception, and otherwise first at R8 step 1, and the accepting side is first exercised at R8 step 1 on every path (TR3-L2, TR3R-M2). **Second fix round (TR4-M2, TR4-L1):** the installer's Phase 2 and `--check` also run the catalog audit (R3's function) on the REAL database, the only read of a REAL catalog; a wrong refusal after Phase 1 leaves a created, unused install (rule 7). **Round 5 (TR4R-M2, TR4R-L1, TR4R-L3):** the audit compares the table and function privileges of every runtime role, and of `public`, with that role's own list (the extension of an existing comparison, not a new object); it is product code under `src/persistence/` that T03 and the installer both import; the parameter-privilege check covers every LOGIN role; a Phase 1 failure leaves a partial install (rule 7). **Round 5, second fix round (TR5-L1, TR5-L2):** the comparison includes `MAINTAIN`, and the shared installer code revokes PUBLIC's `EXECUTE` on every function of the schema, because the HEAD migrations leave that default on twelve functions | 1.2, R6, R8 |
| E21 | The real write fence, row policy and journal refuse every economic write without a current-transaction create lease for the write's own root, registered or not: the whole database is the namespace | 2.6, R3 |
| E22 | The scoped contract includes an owner-scoped list route (stored origin fields, no number). **Amended in round 3 (technical TR2-L4):** the route's admission model is stated: `rw_list_roots(owner_id)` returns root ids only, the route then admits one `ARCHIVE_READ` per root and carries a per-entry `status`, so one lapsed context does not hide the list | 2.4, R5, R7 |
| E23 | **New in round 3 (technical TR2-M1).** The post-seal tail (by-name firing from the inventory with its inventory check, the pre-commit seam, COMMIT, classification of a COMMIT-time error, and read-only reconciliation) is one function shared by the real create and the `SYNTHETIC_TEST` create, so R5 shows it on an accepted `SYNTHETIC_TEST` commit (tests T-a to T-g) without marking any invented data `synthetic = false` and without bypassing a refusal of the real service. A static source audit shows neither branch has its own `COMMIT`, `SET CONSTRAINTS` or outcome classification. The residual (item 11) is for the owner. **Amended in the round-3 fix round (TR3-L6, TR3-L7):** the `SYNTHETIC_TEST` create is made of named parts (4.4 Step 1): S2 storage, a fictional-branch seal and validation forked from F2's and reading the S2 tables, built in R3 as a **TEST-only SQL part** that the real installer does not run (round 4, R3R-M1; section 1 item 1), with the executor's table-grant list shared by TEST and REAL, and Python in R5 that calls the existing fictional integration; R5 adds no gateway SQL. The same sharing applies to a **read tail** used by read, reproduce and each list entry, with its own recorder, static audit and stall test (T-f, T-g) | 3.2, 4.2, 4.4, R3, R5 |
| E24 | **New in round 3 (conformance R2-M2; technical TR2-M3, TR2-M4).** The preflight is keyed to the database's own install kind and name (a decision table, no flag, environment variable or configuration key), runs from several places each with its own vantage (the real installer as the superuser; the publisher tool, the launcher and, since the fix round, the admission probe as non-superusers), connects with `require_auth=scram-sha-256` (except `withdraw`, below), and probes in two passes with connection attempts (scrubbed environment; the caller's default credential sources) and, since the fix round, a static scan (E26), with outcome classes where only `CHALLENGED` passes (and, since the fix round, `REJECTED`). There are two installers, each able to write only its own kind. **Amended in the round-3 fix round (TR3-M3, TR3-L1, TR3-L4):** the gate is keyed to the **command**: `publish`, `renew`, the launcher and the admission probe are gated; `withdraw` (and re-running a pending one) is never gated, commits its drain mark first, and prints the preflight result beside its own, with its own exit status. A third outcome class, `REJECTED` (a `reject` record, or no record), passes with `CHALLENGED`; the installer checks that the rows predict it; self-membership is not a finding. Runtime tools refuse unless `SHOW listen_addresses` is empty, instead of trying TCP | 1.2, R6, R8 |
| E25 | **New in round 3; amended in the round-3 fix round (conformance R3C-M1; technical TR3-M4).** A renewal's `valid_until` must be strictly later than the server clock at the record; it may be later than, equal to, or **earlier than** the current generation's. An earlier one is a **date correction**: the owner's remedy when the term end is found before `valid_until`, which PD-0066 decision 5 ("The owner can correct it from the signup date") and PD-0068 answer 4 give the owner. It needs a decision record naming the corrected date and its reading, fresh basis entries, the plausibility rule against the new date, and the head exclusive lock (so it is appended only when no lease is in flight); the tool prints "moved earlier"; the preflight gates it like any renewal, and an urgent shortening is a withdrawal. Round 3's first form (not earlier than the current) blocked that remedy in the one case where it matters and is withdrawn. Equal still restores the same date after a withdrawal, which R8's last step uses. No PD or contract says this mechanism; it is mine, for the reviewer and the owner to change | 3.1, 3.2, 7.1 |
| E26 | **New in the round-3 fix round (technical TR3-M1, TR3-M2).** (i) A **static credential scan**, Pass S, in every real tool's own process: refuses when `PGPASSWORD` is set, on any passfile line that could address the real cluster whatever the file's mode, and on any service-file section with a `password` that could address it whether or not a service is named; it prints no password. Pass B stays a backstop. **Round 4 (TR3R-L1):** Pass S also scans the default locations and refuses any line or section whose user field names a LOGIN role of the real cluster, whatever its host or port. (ii) **Membership, with no exemption list** (round 4, TR3R-M1; the round-3 form was an allow-list for `pg_*` roles with an allowed-pairs list in the install-kind row): a LOGIN role's `MEMBER`, `USAGE` or `SET` in any other role refuses, and at most one LOGIN role (a superuser, identified by attribute and not by a stored name) has a power attribute. Both lists are gone, and with them the row that had no write protection. (iii) **Settings** (TR3R-L2): no real role has a role-level setting, no LOGIN role of the cluster, nor `public`, may `SET` or `ALTER SYSTEM` `session_replication_role` (TR4-L2; every LOGIN role since round 5, TR4R-L1), and each tool's own session reads it as `origin`. The owner's procedures for the stores the scan cannot see stay procedures (1.2 rule 2) | 1.2, R6 |
| E27 | **New in the round-3 fix round (conformance R3C-L2; technical TR3-L8).** The **admission probe**: a one-shot command built in R7 beside the launcher that calls the gateway's admit for one read-phase purpose on the executor connection and rolls back. It is how R8 shows the export right refused, labelled "direct gateway admission, not a product route". Never `EXECUTE_CREATE`; gated like the launcher | 7.1 (R7, R8) |
| E28 | **New in round 5 (PD-0069); the owner's since round 6 for who may read (PD-0070 decision 2, "Accept the narrowing (Recommended)").** The lease-checked `md_*` read functions. **The mechanism is the owner's, and so is the narrowing**: only `EXECUTE_CREATE` and `EXECUTE_REPRODUCE` leases may call them, only for the release the context's snapshot names, each call bounded by `clock_timestamp() < complete_by`; `ARCHIVE_READ` and `ARCHIVE_EXPORT` leases read stored outputs and no market data. It is no longer an open engineer choice. What PD-0069 left to me, for the reviewer: thirteen per-table definer functions named from `MD_TABLES`, each returning `SETOF` its table's row type; the order of the checks (a lease for the current `(backend_pid, xid)`, purpose, `complete_by`, release); that a failed check **refuses and never filters**, with a SQLSTATE outside class 23; `EXECUTE` for the executor only, and no privilege of the executor on any `md_*` table; R5's keyword-only `lease_checked` on `read_release` and R2's keyword-only `count_rows` on `write_release`, both with defaults that keep today's behaviour; the loader narrowed to `INSERT` on the thirteen tables, `SELECT` on `md_file` and `md_release`, and `EXECUTE` on the candidate registry's put and get functions (the get function returns the payload bytes). The loader's login is off between loads (PD-0070 decision 1) | 2.6 item 6, 3.3, 7.1 (R2, R3, R5), W04, W05 |
| E29 | **New in round 6 (PD-0070 decision 1), my proposal for the reviewer.** The preflight's output (5.3 (g)) prints each of the four real roles' `rolcanlogin`, which 5.3 (a) already reads from `pg_roles`. A print and nothing more: no value refuses a command (the owner opens and closes the loader's load windows, and no tool can know whether a window is meant), nothing is stored, and it says nothing about a moment after the print. Deleting it changes no other claim | 1.2 (5.3 (g), rule 7), 3.3 |

## 9. Risks and what I did not verify

- No code was run. Every SQL claim (lock order, trigger timing, savepoint behaviour, the real seal,
  the clock check, the lease deadline, connection timeouts) is a design claim until the R1 and R3 tests and the
  review.
- Claims taken from PostgreSQL's documented behaviour and **not run here** (I contacted no server in
  any round):
  - that a session or connection option replaces a role-level timeout (fact 16);
  - that a deferred constraint-trigger event fires once and is not queued again after `SET CONSTRAINTS`
    fires it, so a stall after that point is unchecked at COMMIT; that the named form works on a
    constraint trigger; and that an error from a deferred trigger during COMMIT aborts the transaction
    before it is durable (fact 17 gives, claim by claim, what a HEAD test or the installed manual shows,
    and what only an R1 or R5 test will show);
  - that a new `FOR SHARE` locker may overtake a waiting `FOR UPDATE` locker on the same row, which
    would let overlapping readers starve a withdrawal. The drain mark (E18) is built so that the design
    does not depend on this claim; the overlap test in 3.2 checks it;
  - that `scram-sha-256`, `trust`, `peer`, `pg_roles`, `pg_hba_file_rules`, `pg_has_role`,
    `has_database_privilege`, `require_auth` and a password-less connection attempt behave as PostgreSQL's
    installed 17.11 manual documents them (1.2). The preflight's accepting side is first seen at R8 step 1
    on every path; a throwaway cluster under `$TMPDIR`, if the owner grants the sandbox exception, only
    calibrates the classifier (1.2 rule 7);
  - **not shown by the manual or any HEAD test, and the design does not depend on it** (round 3, marked
    "not shown" where used): that a non-superuser may read `pg_database`, `pg_auth_members` and call
    `pg_has_role` and `has_database_privilege` for another role (1.2 rule 5.3 (c); a runtime tool that
    cannot read what it needs refuses); which server messages a refused attempt produces, so the
    `CHALLENGED` and `REJECTED` classifier is calibrated at R6 only on a throwaway cluster, if the owner
    grants the exception, else first at R8 step 1, and an unrecognised message is `OTHER`, which refuses; that an attempt ending in `3D000` has already authenticated (a reviewer's
    reading); that an error reply to COMMIT means the transaction rolled back, and the order of steps
    inside PostgreSQL's commit (4.4 Step 2: the classification is fail-closed, so anything unclassified is
    UNKNOWN); **added in the round-3 fix round:** that a non-superuser may read `SHOW listen_addresses`
    (1.2 rule 5.4); that `pg_has_role` counts a superuser, or a role itself, as a member (5.3 (b)); that
    `postgres` and `template1` of a fresh `initdb` cluster carry PUBLIC's `CONNECT` (section 1 item 2; the
    manual says the default for databases, not which databases); that a password-protected role on a
    cluster that trusts it connects without a challenge (rule 7: an inference from `auth-trust`); that
    `initdb --pwprompt` can be driven through a pseudo-terminal in the sandbox (rule 7); that the existing
    fictional integration runs over the S2 tables unchanged (4.2 build table); **added in round 4:** that
    a non-superuser may read `pg_db_role_setting` or `SHOW session_replication_role` and call
    `has_parameter_privilege` for another role (5.3 (a)); that row-level security is unaffected by
    `session_replication_role = replica` (5.3 (a)); **added in round 5:** that a `SECURITY DEFINER` function
    returning `SETOF` a table's row type, read in a `FROM` clause, works for a caller with no privilege on the
    table (the manual shows each part, `queries-table-expressions` and `sql-createfunction`, and not the two
    together), and that psycopg and `pinned_schema` work unchanged on such a call (2.6 item 6; R3's function
    tests and R5's T-m are the first to show it); that the `has_table_privilege`, `has_any_column_privilege`
    and `has_function_privilege` answer for a named role reports the sum of direct, membership and PUBLIC
    privileges that `sql-grant` describes (5.3 (e); the audit asks `public` as well); that Phase 1 can be
    re-run over a partial install (1.2 rule 7: not claimed); **added in the second fix round:** that a trigger
    fires for a role that holds no `EXECUTE` on its function (5.3 (e): the manual says only that `EXECUTE` is
    needed to create the trigger; HEAD's F2 test covers definer trigger functions only, R3's re-run of R2's
    loader write covers two of the eleven migration trigger functions, and R5's `SYNTHETIC_TEST` create is
    the first firing of the executor-fired ones under the revoke, technical TR6-L2); that the real
    registry's get function returns what N2a's returns to the loader, that it binds a registration to the
    published context after the publish, and that its install and per-call checks require the loader to have
    `LOGIN`, as N2a's do (3.3 items 1 and 3: read from the N2a handover, and the real registry does not exist
    before R2; R2's exit states them); that the foreign-key checks of the `md_*` inserts need no privilege beyond the
    loader's list (3.3); **added in round 6:** whether `NOLOGIN` ends a session that is already open as that
    role (3.3; PD-0070 records it as not shown; the manual says what the attribute decides for a new
    connection, `role-attributes` and `sql-createrole`, and says nothing about an open session);
  - **harness configuration outside this repository:** that an agent's Bash cannot reach a real-cluster
    socket outside the allowlist (CLAUDE.md `:102`; STATUS.md, "its socket needs a sandbox exception"). The design lists it as the weakest of
    five separating means and does not rely on it (1.2 scope, item e).
- "No session setting changes the statement-time deadline checks" assumes the executor cannot disable
  triggers or change `session_replication_role`. Both are owner-level or superuser-only by default; the
  catalog audit (T03 on TEST installs, the installer's Phase 2 on the REAL one), 2.6 item 5 and an R1 test
  check the executor's privileges at install, and the
  preflight refuses a role-level setting, or a `SET` or `ALTER SYSTEM` privilege on
  `session_replication_role`, at each gated start (1.2 rule 5.3 (a)). Other grants are **not** re-read at a
  gated start (1.2 rule 5.4): a later grant by the superuser is not seen until the owner runs `--check`
  (technical TR3R-L2). The superuser's own `ALTER SYSTEM` and reload is the trusted-operator boundary, and
  the `SHOW` check sees it at the next gated start only (5.3 (a); whether a reload reaches a running session
  is not shown).
- **A REAL catalog is read for the first time at R8 step 1** (1.2 rule 5.3 (e); section 1 item 1). Before it,
  "a REAL database holds no fictional-branch function" and "every runtime role's grants are right" are claims
  about the installer's lists, shown by R3's list tests and R6's static test. A wrong refusal after Phase 1
  leaves a created, unused install, and a Phase 1 failure a partial one (1.2 rule 7); that nothing is used
  until a refusal is resolved is the owner's procedure, which no tool enforces.
- **Commit-time validity is not provided** and is not claimed (3.1, E4): the deadline guard bounds the
  product path inside COMMIT processing, and a session that fires it early, or the commit-processing
  gap, remain. The owner's cap (PD-0068 answer 1) means no economic write, seal or guarded load, and (the
  design's addition, and the owner's for the stored market data, PD-0069) no read of a rooted table, of the
  archive or of a stored market-data row through the lease-checked functions, succeeds at or
  after `valid_until`; it does not mean nothing commits after it, and a row already read before `complete_by`
  is not recalled. The loader's reads (`md_file`, `md_release` and the registry's payload bytes) are not bounded
  by it: they are closed between loads by the owner's `NOLOGIN` step (3.3; PD-0070 decision 1), with the limits
  of section 7. FF1-C06 and E10 section 5 call validity at the physical commit unsupported.
- **The HG4 expiry bound is an upper bound** (3.1; PD-0068 answer 4): `term_end_not_after` is the latest
  the term can end, and the signup date is not recorded. If the term began before about 2026-09-01 the
  lease could run past the licence term. The owner accepted `valid_until` 2027-09-01 knowing this; the
  publish record and the HG4 package state it. The plausibility rule is not a safety margin. The remedy the
  owner named, pinning the term start, is a renewal that is a date correction (E25), or, when the pinned
  term has already ended without notice, a renewal for the Renewal Term (3.1); until the owner records it
  the limit stands.
- **Accepted limits (the owner's):** the end-to-end ACK-loss ordering is not re-proven before R8
  (PD-0068 answer 2; 4.4); D-1 (expiry) and D-2 (rollback after writes) are not collected on the real
  context (PD-0068 answer 3; 7.1); **the loader's login limits** (PD-0070 decision 1, in its words: `NOLOGIN`
  stops new connections only, and whether it ends a session that is already open is not shown; the
  superuser and the owner role are not affected; each later load needs the owner's `LOGIN` step; section 7;
  the steps are an owner procedure that no tool enforces).
  **Conditional, not yet the owner's:** D-3, two-user isolation not
  collected on the real context, if R7 declares it (7.1); it gates R8, and an answer that is not an
  acceptance stops R8 (R3R-L3).
- **Not yet accepted, for the owner (item 11):** the residual of the post-seal tail. The shared tail is
  shown on the `SYNTHETIC_TEST` create (E23); the real branch's seal on an accepted result, any constraint
  only it has, the real commit's timing, and a stall or fault drill on the real commit are first exercised
  by the real commit (4.4 Step 2). R8 does not start until the owner accepts this in a recorded decision.
- **Password stores are an owner procedure** (1.2 rule 2): the static scan (Pass S) can show that the
  environment, the passfiles and the service files at the locations libpq reads (the named ones and the
  defaults) hold no entry for the real cluster
  from where it ran, now, whatever their mode. It cannot show where else the owner or an agent kept a
  password (a notes file, a shell profile, a `.env` file, another process's environment), what a process
  running as the owner's OS user can read, or the permissions of the data directory. The superuser password
  and every real-role password must not be stored where an agent session can read them; the database cannot
  enforce that, and the design adds no control it cannot enforce.
- **A withdrawal is never blocked by the install preflight** (1.2 rule 5.1), but it still needs a
  connection: a `require_auth` demand is not made for `withdraw`, yet a server that is down or a role that
  cannot log in stops it, and the lapse at `valid_until` is the backstop for those. A date correction is
  gated like a renewal.
- Under B the real gateway is a fork of F2's design. Drift between the two is a maintenance cost.
- "Legacy roles have no privilege" must hold for default privileges, role membership and definer
  functions elsewhere (catalog audit, T03 and R6). Not run.
- Database locks serialise recorded state only. A provider changing terms is outside them (E10
  section 5). A trusted-operator boundary (superuser, OS, server clock, the cluster's data directory)
  remains, and the superuser is a trusted boundary **only if no agent-usable superuser path exists**
  (1.2). Until the real cluster exists, that is unverified: the development clusters trust their
  superuser over the socket.
- Scenario Lab (CP8) needs a read path from the separate real database. Not designed here.
- Not verified: the Quant's `market-data/1.16` beyond item 9 and the 1.16 note (committed `ae6dfdc`; I
  did not re-diff Ruling 6.5 or the A.6 text against it in round 3, and the code follow-ups of 8.1 item 2
  are not applied); the parallel version-label track's own diff or tests (HEAD `7effcc8` carries label
  1.15); that the 2026-09-30 row of
  `AAPL_compact.csv` is admissible; the contents of any payload; the live Alpha Vantage terms (I used the
  owner's reading as recorded in PD-0066, and I did not see the PDF); whether `PostgreSQL`
  `transaction_timeout` exists on the cluster that will host the real database; how far the lineage
  label string reaches into digests; the full text of the 18 `src/` files in fact 11 and the 16 `web/src`
  files (and of the files the widened wording matches); which `pg_hba` rule the host cluster has; who
  owns the data directory of the development and the future real cluster; whether `unix_socket_permissions`
  and the sandbox's socket exception are the only things between an agent and the real cluster today.
- The round-1 findings reached me through the main session. Where a finding gave a file and line, I
  read it before changing the text. They matched, with one difference: E9's post-run paragraph is at
  `:111-115`, not `:110-113`. I corrected the proposal hash from a recomputation. In round 2 the findings
  are in `reviews/TECH_REVIEW.md` (header), and I read the cited F2 lines, tests and tooling again before
  changing the text; M-1's scenario (the guard fires on an unsealed lease when moved early) is what
  `test_c14`'s first half expects, and M-2's lines (`:192`, `:205`, `:222-224`, `:240`) are as cited. I did
  not test the reviewers' reasoning beyond reading. In round 3 I read the round-2 reviews at
  `reviews/TECH_REVIEW.md:16753-17121` and re-read the lines they cite before changing the text: the
  by-name firing in `guarded_workspace_context.py:88, :100` and `0003_ledger_event_guards.sql:203-205`
  (conformance R2-L7), the provisioner's `dsn` (`passfile=/dev/null`, `connection.py:3-4`), and the nine
  environment-driven modules (a grep). Where a reviewer's claim rests on PostgreSQL behaviour that neither
  a HEAD test nor the installed manual shows, I kept it as the reviewer's reading and marked it "not shown".
- I did not run the test suite and ran no SQL. This revision changed no code.

## 10. Changes after review (fix round, 2026-10-24)

Two independent reviews of the first version of this revision returned 7 MEDIUM and 16 LOW findings.
Both used the ids M-1, M-2 and L-1 onward, so they are named **A** (its M-1 and M-2, L-1 to L-9, in the
order relayed) and **B** (its M-1 to M-5, L-1 to L-7) here. Every finding is addressed in the text; none
is left open. Each change is a design claim until built, tested and re-reviewed.

**Read this section and section 11 with round 3 in mind (2026-10-24).** Their text records what each round
said at the time and is not rewritten, except for the two in-place corrections marked "corrected in round
3" in section 11. References here and in section 11 and the change log to "open item 7", "8", "9" or "10"
are to the four questions that PD-0068 answered (8.1, the table after item 6); the wording of the **B M-5** row
(`complete_by = admitted_at + W`) and of the **L-9** row of section 11 (`valid_until + W <= ...`) is superseded
by the cap and the relaxed rule (3.1, E4, E14). Section 12 maps
the round-2 findings and PD-0068 to the current text.

| Finding | What it said | What changed | Where |
|---|---|---|---|
| **A M-1**, **B M-4** (MEDIUM) | `NONE` was refused only for a context whose snapshot declared a lease-governed source, so a publisher omission, or sources with no recorded term, permitted `NONE` | The snapshot carries no lease-governed list. The expiry kind is derived from per-member-source basis entries; member sources are read from the manifests. `NONE` needs a recorded human no-expiry reading for every member source and no lease term. Anything else is `UNKNOWN`, which publish refuses and admit never accepts; admit re-derives the kind. The "`NONE` only with evidence" case is back in T07, with the omission cases | fact 15; 2.1, 2.2, 2.3; 3.1 (two rows); 3.2; E2, E14 |
| **A M-2**, **B M-3** (MEDIUM) | The REAL-scope tests for O2 to O4 could not be built without marking invented data `synthetic = false`; O4 is a seal check a `TEST` install never reaches; the R3 label test and the R7 claim-text test could not run before R8 | O1 to O3 are independent functions that report every failed predicate; in the real scope O2 does not exempt synthetic sources and O3 reads the member's own fields; O4 is a seal predicate with two codes. Each predicate has a failing case and, where possible, a control, none marking invented data `synthetic = false`. The passing sides of O1 and O4 are first exercised at R8. R3 tests the label mapping on in-memory rows and audits that no reader hard-codes `synthetic`. The 7.4 sentences render only when `market_origin = REAL_SOURCE` | 4.2 (new table), R2, R3, R7; 7.4; E15 |
| **B M-1** (MEDIUM) | Build order used things before the increment that builds them | The scope core and the reviewed switch moved into R1. R3 makes no service call; the world builder, the service call and the create, read and reproduce code moved to R5. The scoped contract module is authored in R5 (reviewed there) and installed in R7. R8 installs the database before it qualifies. The dependency paragraph is re-checked against what each increment uses | 2.4; 4.1; 4.2 (build table); 7.1 (R1, R2, R3, R5, R6, R7, R8); E17 |
| **B M-2** (MEDIUM) | Origin labels followed the branch, so a `TEST_SWITCH` root carried `REAL_SOURCE` on invented data | Labels follow the origin axis. Test scopes carry `SYNTHETIC_TEST` and `INVENTED_TEST_LEDGER`, never a real-origin string; a seal row guard refuses a mismatch; I1 and I3 cover labels | 1.1; 4.2; E16 |
| **B M-5** (MEDIUM) | The in-flight window after `valid_until` had no database-enforced bound, and the E10 section 5 basis was not shown | The lease carries `complete_by = admitted_at + W`, checked at the write fence and the seal at statement time and again by a commit-time trigger. Role-level timeouts are demoted to defaults (fact 16). The limit of a deferred trigger is disclosed (fact 17) and has a characterisation test. The E10 section 5 basis is stated plainly: the owner's words do not establish permission for in-flight completion; open item 7 asks the owner; the strict variant is defined. Stalled holders and the withdrawal are handled | facts 16, 17; section 3 intro; 3.1; 3.2; 8.1 item 7; 9; E4 |
| **A L-1** | R3's test list did not separate what option (a) can run before R8 | 4.4 marks T06 to T09 as product path, E11 crafted probe (not product evidence) or first run at R8; R3's exit requires the marking; R8 lists the deferred observations by E9 item | 4.4; R3 and R8 rows; list after 7.1; 8.1 item 5 |
| **A L-2** | "The owner's reading" included the main session's interpretation | Section 3 now separates the owner's verbatim words, the owner's choices, the main session's notes (not the owner's, not legal advice) and the recorder's gloss on X1 | section 3 intro |
| **A L-3** | A new, untagged owner obligation: re-read the terms before a renewal | Reworded as a recommendation. R1 builds no such precondition | 3.1 (Renewal); 7.2 |
| **A L-4** | A withdrawal needed a decision reference, but none was named for a notice or termination | PD-0066 decision 5 is a valid reference for that withdrawal | 2.5; 3.1 (Notice or termination); E13 |
| **A L-5** | No mechanism for two owner conditions in the install step | (a) The publisher authenticates by a password the owner sets, never password-less or socket-trusted; R6's plan states the `pg_hba` rule. (b) The "no `CONNECT` elsewhere" claim is restated: the provisioner does not revoke `CONNECT`, and PUBLIC holds it on existing databases, so R6 chooses between its own cluster and a separately approved ACL change | fact 18; 1 (items 2, 3); 2.5; R6; 8.1 item 6; E19 |
| **A L-6** | I2 cited P8 for the origin axis and read literally forbade `TEST_SWITCH` | I2 now reads "synthetic and real origins never mix in one snapshot (Ruling 4.8 items 1 and 2; P9)" and says `TEST_SWITCH` is not a mixture | 4.2 |
| **A L-7** | The `SOURCES.json` update did not gate qualification or publish | It gates R4a's exit and R8, with the reason (a later edit changes the hash) | 7.1a item 5; R4a, R8 |
| **A L-8** | 7.4 left out two lineage items of Ruling 6.5 item 6 | Added: the inputs named (files with hashes, `L`, convention id), the exposure window and "no V1 event in `M`" | 7.4 |
| **A L-9**, **B L-7** | Stale or ambiguous references; the proposal hash was misquoted | "snapshot :420-430" is now "proposal :420-430"; the full SHA-256 of the proposal is recorded, recomputed; the label statement names HEAD and the working tree | header; 6.1; 7.3; fact 14 |
| **B L-1** | A PD file's SHA-256 changes when the PD is amended | The reference is PD id, git commit and the SHA-256 at that commit | 2.5; 6.1; E13 |
| **B L-2** | The withdrawal limits omitted the staging copies and the `md_*` rows | Added, with two proposed (not decided) extra owner steps | 3.3; 6.4; W12 |
| **B L-3** | Withdrawal starvation by overlapping share locks (not run); the generalised `np_guard`'s use of the clock | A drain mark stops new admissions first; `np_guard` tests the lease deadline and not `now < valid_until`; tests added; the lock-queue reading stays marked unverified | 2.1; 3.1; 3.2; 9; E18 |
| **B L-4** | The executor's DML exceeded what S2 needs; W07's proof covered only legacy roles | No executor privilege on `web_saved_sandbox`, `web_portfolio_revision`, `web_csv_*`; W07's proof and T03 include `WebAccountStore.create_portfolio` on the executor connection | 1 (item 5); W07; R3 |
| **B L-5** | The S2 reader audit stopped at `src/`; the web client hard-codes synthetic | Fact 11 and the audit cover `web/src`; R7 builds a real-mode list type and does not reuse the synthetic one | fact 11; 1 (item 6); R3, R7 |
| **B L-6** | Fact 14, 8.1 item 3 and the `profiles.py` citations go stale when the label lands | Fact 14 states HEAD and working-tree labels and the +2 shift; citations are HEAD lines that name their symbol | fact 14; 7.3; 8.1 items 2, 3 |

## 11. Round 2 changes (2026-10-24)

The two re-reviews of the fix-round version returned 4 MEDIUM and 9 LOW findings (technical re-review,
`reviews/TECH_REVIEW.md:15635`) and 3 MEDIUM and 3 LOW findings (decision-conformance re-review,
`:15298`). Their
ids repeat section 10's ("M-1", "L-1"), so the **Review** column says which re-review: **TR** is the
technical re-review (ids M-1 to M-4, L-1 to L-9) and **DC** is the conformance re-review (DC-M1 to
DC-L3). Every finding is addressed in the text; none is left open as a finding. Some fixes left an
owner decision open, 8.1 items 7 to 10 of that version, which the owner answered in PD-0068 (round 3). Each change is a design claim until built, tested and
re-reviewed; I ran no SQL and no test (the "How this was checked" list at the top of this file).

New fact this round (not a finding): the owner moved the byte-identical OpenFIGI duplicate
(`AAPL_XNGS.json` and its manifest) out of the store, unchanged, to
`data/marketdata/observations/openfigi/identity/2026-10-23/`. The store keeps `AAPL_UW.json` only. It is
reflected in facts 9 and 13, 6.3 and 6.4, W04, E9, and the staging store is no longer required.

| Finding | Review | What it said | What changed | Where |
|---|---|---|---|---|
| **M-1** (MEDIUM) | TR | The commit-time deadline guard could not run at COMMIT on the product create path: moved before the seal it refuses every create (`F2_UNSEALED`); moved after (F2's place) it is consumed before the stall; so "refused at commit" and "nothing commits after `valid_until`" were not what the product enforces | The deadline guard is a constraint trigger of its own, separate from the bundle guard. The product create code leaves it pending: it fires the bundle guard, the root foreign key and the other deferrable constraints early **by name** (F2's `validate_domain_constraints` pattern, with an inventory check), never `SET CONSTRAINTS ALL`, never the guard. A COMMIT-time error carrying `RW_DEADLINE` with the connection `IDLE` is a definite refusal; any other COMMIT error is UNKNOWN. Stated plainly: the bound is statement-time checks plus a guard that fires inside COMMIT for the product path; **no claim that nothing commits after `valid_until`** (E10 section 5, FF1-C06). Open item 7 and the E4 row corrected. Fact 17 rewritten with what a HEAD test, the installed manual, or neither shows. Tests marked by increment | fact 17; 3.1 (in-flight row); 3.2; open item 7; E4; section 9 |
| **M-2** (MEDIUM) | TR | The real fence and row guard were forked from F2's, which let lease-less writes to unregistered roots through (`v1.sql:192, :205, :222-224, :240`); no statement that the real one refuses them | New fact 19 and **2.6** (E21): the whole database is the namespace. The fence, the row policy and the journal refuse every economic write without a current-transaction create lease for the write's own root, registered or not; only `rw_admit(new_root = true)` registers a root, before the portfolio row exists; the executor cannot insert into `rw_root_link` or the lease table (**corrected in round 3, conformance R2-L6**: the round-2 row said "cannot insert into `rw_root`", but 2.6 lets the executor write `rw_root` and `rw_revision` under a create lease; the registry the executor cannot write is `rw_root_link`). **Test:** T03, R3: the lease-less insert into a registered-nowhere root on the executor connection, for every economic table, each barrier alone, plus the register-later variant and the disable attempts. W07, W08, W10 restated | fact 19; 2.6; W07, W08, W10; R3 row; E21 |
| **M-3** (MEDIUM) | TR | Agent sessions can reach a socket-trusted superuser, which bypasses E19's publisher control | New **1.2** (E8, E20), an install rule for R6 and R8 step 1: a `scram-sha-256` password for every role, no `trust`, no `peer` for a privileged role (**corrected in round 3, conformance R2-L5 and technical TR2-L1: no `trust`, `peer` or `ident` for any role**; 1.2 rule 1 always said so, and the preflight of this row was redesigned: 1.2 rule 5, E24), the superuser password held by the owner alone, the data directory outside the sandbox's write paths, a preflight in the installer, the publisher tool and the launcher that refuses to run if an agent-reachable superuser path exists. **The existing test tooling (`guarded_pg_runner.py`, `guarded_pg_provision.py`, `dev_env.py`) uses a socket-trusted superuser and must never be pointed at the real cluster**; R6 adds a refusal for a `finweb_real` database. This is an owner-approved environment step. E19 corrected: a publisher password alone does not keep an agent out. Fact 18 extended | 1.2; fact 18; 2.5; W13, W14; R6 and R8 rows; open item 6; E8, E19, E20; section 9 |
| **M-4** (MEDIUM) and **DC-M1** (MEDIUM) | TR, DC | A withdrawal's drain mark stopped all admissions without recording issuer, decision reference or time; a timed-out withdrawal left no record | The drain mark is a row with issuer, the decision-reference triple, the server time and the database-recorded role, all `NOT NULL` with format checks, written only by the withdrawal function; it cannot exist without them. Admission refused with `RW_WITHDRAWAL_PENDING`. State is derived: pending, effective, superseded. A timed-out withdrawal leaves a pending mark, a status view, and a non-success tool exit with explicit text. A renewal cannot silently supersede a pending mark. **Tests (R1, read-lease):** the record read back after a timeout; refusal without any field; no direct writes; renewal while pending | 2.1; 2.3; 3.1 (renewal, cancellation rows); 3.2; E18 |
| **DC-M2** (MEDIUM) | DC | The d6 re-proof of ACK loss was only a crafted probe, and the reviewer was asked to accept that | 4.4 maps each of the four d6 orderings to what it reaches before R8. ACK loss: R3 (E11) drops the connection after a crafted commit and the product returns UNKNOWN; R5 runs the product's reconciliation code against that crafted committed state. **The end-to-end ordering is not re-proven before R8** (no product create can commit before then); R3's and R5's exits must not claim it. Recorded as an accepted limit for the owner (open item 8), with the option of a rehearsal inside R8 in a disposable `REAL` install | section 1 item 5; 4.4 (new table and answer); R5 row; open items 5 and 8; section 9 |
| **DC-M3** (MEDIUM) | DC | The claim-limit (P3) text had no test before R8 | 7.4 labels the slots S1 to S5 and the caveats C1 to C7 and adds pure render tests: R5 over the output block, R7 in EN and zh at all three depths, each over an in-memory `REAL_SOURCE` fixture that is never stored or served, asserting that every C-item is present, including "dividend component `UNVERIFIABLE`" and the single-source, no-comparison caveat. 4.3 states that this pure render is not a use of a test scope | 7.4; 4.3; R5 and R7 rows |
| **DC-L1** (LOW) | DC | The W12 limit "not claimed to follow purpose locks" was dropped | Restored in 3.3 and W12: with export `false` and read `true`, `evidence_pack real` still builds a pack from the files on disk | 3.3; W12 |
| **DC-L2** (LOW) | DC | E9's required post-run evidence was made optional on the real context | 7.1 says what R8 can collect (error digest; refusals that write nothing; two-user isolation if feasible), what is collectible only at the owner's choice (revocation, last step), and the two **explicit deviations**: D-1 expiry cannot be observed on the real context, D-2 rollback after writes is not forced. Put to the owner as open item 9 | 7.1 (after the R8 observations); T07 row of 4.4; open item 9 |
| **DC-L3** (LOW) | DC | Cancellation tests that need a create were listed under "X1 tests live in R1" | 3.2 is retitled and every item is marked R1 (read-only-phase lease), R2, R3 (E11 crafted bundle) or R5 (product create up to the service's refusal). R1 builds no seal and no create | 3.2 |
| **L-1** (LOW) | TR | R1 used two things built later: the pause before the guarded load (R2) and the proposal files (R4b) | The guarded-load pause moves to R2. R1 defines the proposal format with a pure writer and verifier; R4b calls the writer and its output must pass R1's verifier. Publish refuses a `REAL`-scope snapshot until R2 wires the validators | 2.3; 3.2; 4.2 (build table); R1, R2, R4b rows; E17 |
| **L-2** (LOW) | TR | The clock-regression check raced under overlapping admissions | Admit reads the latest committed instant before it samples the clock. The policy for jumps is stated (forward fails closed; backward detected only below the latest instant; outage means no admission). Overlap test added | 3.1 (clock row); 3.2; E3 |
| **L-3** (LOW) | TR | The REAL-direction install-kind test had no construction that avoids real labels on invented data | An in-memory snapshot whose scope field alone is `REAL`, with synthetic sources and labels, refused at publish with O1 also listed; at admit an E11 crafted row of the same shape; the `REAL`-install direction uses bytes made in a `TEST` database | 4.2 (install-kind paragraph) |
| **L-4** (LOW) | TR | The O2 and O3 controls were invented human attestations that a test might store | The controls are in-memory validator inputs only, never a manifest file, candidate row, sidecar file or snapshot; the contract tests assert the validators take them by value and write nothing | 4.2; R2 row; E15 |
| **L-5** (LOW) | TR | The reader audit's search terms missed hard-coded "fictional" and "sandbox" wording | Fact 11 and section 1 item 6: the audit terms include the display wording; today's counts (13 `web/src` and 18 `src/` files); the exit lists each hit's disposition; a pure render test on an in-memory `REAL_SOURCE` row (R3 server strings, R7 client strings) | fact 11; section 1 item 6; R3, R7 rows |
| **L-6** (LOW) | TR | The scoped contract defined no list route, yet R7 and R8 need one | The R5 contract includes an owner-scoped list route (stored origin fields, no number, `ARCHIVE_READ` per context); R7's list type conforms | 2.4; W15; R5, R7 rows; E22 |
| **L-7** (LOW) | TR | The sidecar acquisition records had no building increment and gated nothing | R4b builds the sidecar schema, reader and the O5 validator; the `REAL` scope refuses the legacy null; R4b's exit and R8's needs require one valid sidecar per member | 6.1; 4.2 (O5, tables); R4b and R8 rows |
| **L-8** (LOW) | TR | Admit's re-derivation of `NONE` needed the member-source set, which the member tuple did not carry | The member tuple carries each member's `source_id` from its manifest; admit takes the set from the stored snapshot, so a crafted history row cannot shrink it. Test added | 2.1; 3.1 (two rows); 3.2; E14 |
| **L-9** (LOW) | TR | `LEASE` treated member sources with no entry as valid until `valid_until` | `LEASE` requires exactly one entry per member source (new basis `NOT_ASSESSED` for a source with no recorded term), takes the earliest `term_end_not_after`, and publish refuses `valid_until + W` beyond it (the margin the round-1 conformance review asked to be stated). For HG4 the publish record states two `NOT_ASSESSED` entries (open item 10) | 3.1 (kind rows); 3.2; open item 10; E14 |

Also corrected in this round, without a finding: R0 is PD-0066, not "PD-0066 plus PD-0067" (PD-0066
decision 10 says "R0 is this record"; PD-0067 records none of D1 to D7; noted by the conformance
re-review), in section 0, the R0 row and the change log below.

## Changes from the proposal (2026-10-24)

Mapping each decision to the sections it changed.

| Decision | Sections changed |
|---|---|
| **D1** (PD-0066 d6): B, separate database, S2 | Status; section 0 (D1 row); facts 2, 3, 5 (retired by B); **section 1 rewritten** (A/B and S1/S2 tables collapsed to the decision; role closure, placement, migrations, accepted cost, S2 storage); 1.1 keeps the real-scope content, `state_kind` still pending; section 5 (W07, W08, W10 now refer to the real database only); section 7 (R1, R3, R6, R8; the branch-delta table dropped); section 8. **Fix round:** the `CONNECT` limits and the executor's privileges (1 items 2, 3, 5), the `web/src` audit (1 item 6), origin labels per scope (1.1), facts 11 and 18 |
| **D2** (PD-0066 d7): R-GW, content hash, new scoped contract, owner sole publisher | **Section 2 rewritten**: authority objects, hashed content versus `valid_until`, lifecycle, 2.4 (the E5 successor with `real_workspace_contract.py:211-224` and `real_workspace_routes.py:1`), 2.5 (publisher, renewal, decision reference); section 5 (W15); section 7 (R1, R7); section 8 (E2, E13). **Fix round:** the contract module is built in R5 and installed in R7 (2.4); the drain mark in the authority objects (2.1); the publisher's authentication and the amended decision reference (2.5; E13, E19) |
| **D3** (PD-0066 d5): X1 lease | **Section 3 rewritten**: HOLD and X3 removed as live paths; the owner's reading; the lease table; the X1 tests moved into R1; withdrawal scope and the owner procedure; fact 1 (no clock in F2) and fact 15 (source records); section 5 (W12); section 7 (R1, R4a, R8; 7.2); section 8 (E1 to E5). **Fix round:** the owner's words separated from the notes (section 3 intro); the expiry kind derived from per-source evidence (3.1; E14); the `complete_by` deadline in place of role timeouts (3.1; facts 16, 17; E4); the E10 section 5 basis and open item 7; the drain mark (E18); the withdrawal limits widened (3.3); more X1 tests (3.2) |
| **D4** (PD-0066 d6, d8): patches, option (a), one module | **Section 4 rewritten**: patch fates; 4.2 scopes, the switch and the separate O1 test; 4.3; 4.4 (new consequence); fact 12 added. **The made-up real-shaped context `INVENTED_REAL_SHAPED_TEST` is withdrawn entirely** (proposal :282-294, :342-344, :446, :450-451, :477, :504, :549): nothing marks invented data `synthetic = false` any more. This resolves review finding F-1 (MEDIUM, `reviews/TECH_REVIEW.md` :14209). Sections 7 (R1 to R5, R7) and 8 (E6, E7, E11). **Fix round:** 4.2 rewritten again: origin labels follow the axis, independent origin predicates that report every failure, a failing case and a control per predicate, a build table for the scope machinery (E15, E16, E17); 4.1 and 4.4 state which increment builds and runs what, with the pre-R8 classification table |
| **D5** (PD-0066 d9): writer classes | **Section 5**: classes unchanged; W12 gains the owner procedure; code citations moved (`download.py`, `market_data_store.py`); W11 notes the pre-R8 limit. **Fix round:** W07's proof covers the executor connection; W12 names the staging and `md_*` copies; W14 and W15 updated |
| **D6** (PD-0066 d9): fetch, sidecar, digest confirmation | **Section 6 rewritten**: 6.1 route and sidecar content; 6.3 the confirmation table, hashes recomputed; 6.4 one manifest (`AAPL_UW.json`) and the staging store; fact 13 added; fact 9 updated; section 8 (E9, E10). **Fix round:** the sidecar's decision reference (6.1), "proposal :420-430" (6.1), the staging store's withdrawal limit (6.4). **Round 2:** the owner's move of the OpenFIGI duplicate out of the store (facts 9 and 13, 6.3, 6.4, E9); the sidecar's building increment (R4b) and the O5 validator (6.1, 4.2) |
| **D7** (PD-0066 d10): build order | **Section 7**: R0 is PD-0066 (corrected in round 2; the first version said "plus PD-0067"); R1 gains X1 and the install kind; R4a has no split file in `M` and takes the identity, the DECLARED label source and the code-label rule; R5 claim limits (7.4) plus the dividend component, the oracle at R8 and the pre-R8 refusal evidence; R6 needs the owner's go-ahead; R7 uses the new scoped contract; R8 spelled out; old 7.2 branch deltas replaced by 7.2 stop conditions; 7.3 updated. **Fix round:** R1 holds the scope core and the switch; R3 makes no service call; R5 holds the world builder, the service call, the create, read and reproduce code and the contract module; R7 installs the reviewed contract; R8 installs before it qualifies and lists its first-run observations by E9 item; R4a and R8 need the `SOURCES.json` update (7.1, 7.1a) |
| PD-0066 d1 to d4 (data side) | Fact 9 (files, hashes); 6.3; R4a (identity, label source); 7.4 |
| PD-0067 (A-shares, OP-1/3/4/6, L-2) | Fact 14; 7.3; R4a and item 3 of 8.1 (the version label) |
| Review finding F-2 (LOW) | 7.4 now includes "dividend component `UNVERIFIABLE`" |
| Corrections to the proposal's citations | `financial_service_integration.py:327` is `:327-329` (the `ACTUAL` test is at `:329`); `ingest.py:264-270` is `:268-274`, `:844` is `:869`, and the synthetic-iff check is `:266-267`; `market_data_store.py:665` is `:695`; `download.py:153` is `:177`, `:476` is `run_fetch :810`, `:761` is `run_register :793`; `profiles.py:242` is `:297-298`. Fact 11's "18 files" is clarified as 17 Python files plus migration `0017` |
| Facts added | 12 (synthetic refusal), 13 (two manifests for one payload, found by a read-only run), 14 (changes since 10-23), 15 (source records); fact 1 gains the F2 history columns and the absence of a clock. Fix round: 16 (role timeouts are not a bound), 17 (what F2 already has for a deadline check, and the deferred-trigger limit), 18 (the provisioner and the socket); facts 11, 14 and 15 extended. Round 2: 19 (F2's fence passes unregistered roots); 13 rewritten as resolved; 17 rewritten with what a test, the manual or neither shows; 18 and 11 extended |
| Fix round (two independent reviews) | Section 10 maps the 7 MEDIUM and 16 LOW findings to the changes. New tags E14 to E19; E2, E4, E8, E11 and E13 amended in 8.2. New open item 7 (8.1) |
| Round 2 (two re-reviews) | Section 11 maps the 7 MEDIUM and 12 LOW findings (technical 4 + 9, conformance 3 + 3) to the changes. New sections 1.2 (install rule) and 2.6 (fence for any root). New tags E20 to E22; E3, E4, E8, E9, E14, E15, E17, E18 and E19 amended in 8.2. New open items 8 to 10 and a corrected item 7 (8.1) |
| Round 3 (PD-0068 and the open round-2 findings) | Section 12 maps PD-0068 answers 1 to 4 and the findings R2-M1, R2-M2, R2-L1 to R2-L7, TR2-M1 to TR2-M4 and TR2-L1 to TR2-L4 (and the reviewers' observations) to the changes. 3.1 and 3.2 (the cap, the relaxed plausibility rule, the HG4 entries and the disclosed limit, renewal, the unique guard name); 1.2 rewritten (scope, password stores, probe, who runs it); 4.4 (the shared post-seal tail and its residual); 7.1 (R1, R3 to R8, D-3, revocation as R8's last step); 8.1 (items 7 to 10 answered and tabled, new item 11); 2.4, 4.3, 6.1, facts 9, 11, 13, 14, 16, 17, 18. New tags E23 to E25; E4, E8, E11, E14, E20 and E22 amended in 8.2. In-place corrections in section 11 (M-2 and M-3 rows) |
| Round 3 fix round (two round-3 reviews) | Section 13 maps R3C-M1, R3C-L1 to R3C-L7, TR3-M1 to TR3-M4 and TR3-L1 to TR3-L8 to the changes. 1.2 (rule 2 table and scan note; rule 3 placement and the shared-cluster consequence; rule 4; rule 5.1 table by command; 5.2 by command; 5.3 (a) to (f) and 5.4: Pass S, the `pg_*` allow-list, the `CONNECT` decision, `REJECTED`, `listen_addresses`; rule 7: dev-cluster limits, pty, case list); section 1 item 2; 3.1 (kind row, renewal row, notice row, HG4 block); 3.2 (date-correction tests, the read tail); 4.2 (build table), 4.4 (what the `SYNTHETIC_TEST` create is made of, T-f, T-g, Step 2 item 2, what each exit may claim); 7 (D-3), 7.1 (R1 to R8 rows, the export check), 7.1a item 2; 8.1 (items 4, 11, the PM list); 8.2 (E14, E20, E23 to E25 amended; E26, E27 new); 9; D1 row of section 0; header. In-place marks in section 12 |
| Round 4 (two re-reviews of the round-3 fix round) | Section 14 maps R3R-M1, R3R-L1 to R3R-L3, TR3R-M1, TR3R-M2 and TR3R-L1 to TR3R-L4 (and the observations) to the changes. Section 1 item 1; 1.2 (rules 2, 3, 5.2, 5.3 (a), (b), (d), 5.4, 7); 2.1, 2.6; 3.1, 3.2; 4.2, 4.4; 7, 7.1 (R3, R6, R7, R8); 8.1; 8.2 (E4, E11, E20, E23, E26 amended); 9; header. In-place marks in section 13 |
| Removed | The A versus B comparison, the S1/S2 file lists, the D3 HOLD default, the branch deltas, and the owner questions of old section 8: all are decided, and old questions 8 (F2 add-on in the owner's database) and 9 (who sees this first) no longer apply. The proposal's two "Changes after review" tables stay in the snapshot |

## 12. Round 3 changes (2026-10-24)

Round 3 does two things. It reflects the owner's answers in PD-0068 exactly (invents nothing beyond them),
and it answers the findings the two round-2 reviews left open: conformance (`reviews/TECH_REVIEW.md:16757`:
0 HIGH, 2 MEDIUM, 7 LOW) and technical (`:16911`: 0 HIGH, 4 MEDIUM, 4 LOW), plus their observations. Their
ids are R2-M1, R2-M2, R2-L1 to R2-L7 (conformance) and TR2-M1 to TR2-M4, TR2-L1 to TR2-L4 (technical).
References to "open item 7" to "10" in sections 10 and 11 and in the change log above are to the four
questions PD-0068 answered. Every change is a design claim until built, tested and re-reviewed. **I ran no
SQL, no test and no build, and connected to no server** (the "How this was checked" list, Round 3). Code
facts cite HEAD `7effcc8`; where PostgreSQL behaviour is stated, the text says whether a HEAD test or the
installed 17.11 manual shows it, or that it is "not shown". **Sections 13 and 14 amend several round-3
mechanisms** (E23, E24, E25, and the preflight's placement, probe and password-store rules in 1.2). The rows
below record what round 3 said at the time; where they differ from section 13, section 14 or the body, the
later section and the body govern.

### 12.1 PD-0068, answer by answer

| PD-0068 | What the owner decided (verbatim answer) | What changed | Where |
|---|---|---|---|
| **Answer 1** (former 8.1 item 7) | "(b) No, cap at the end (Recommended)" | `complete_by = LEAST(admitted_at + W, valid_until)` for every lease, with a table `CHECK` and a strict `clock_timestamp() < complete_by` at the four checks (write fence, seal, guarded loads, the COMMIT-time deadline guard). Option (a) is removed as a live path. `W` stays an install constant, my proposal of 10 minutes, which only shortens deadlines. The two disclosed limits stay, and the text never says that nothing commits after `valid_until`. Item 7 is gone from 8.1 | 0 (D3 row); 3 intro; 3.1 (in-flight, lapse, renewal and kind rows, "What E10 section 5 required"); 3.2 (`LEAST` tests in both orders, the `CHECK`, capped-bound tests); fact 17; 2.6; 7.1 (R1); 8.1 table; E4; section 9 |
| Answer 1, the margin rule (left to the engineer "for review") | n/a | **Relaxed:** `valid_until <= min(term_end_not_after)` over the `LEASE_TERM` entries, in place of `valid_until + W <=`. **Why it can be relaxed:** `W` was in the rule for option (a), where an admitted operation could finish up to `W` after `valid_until`; under the cap no write, seal or guarded load succeeds at or after `valid_until`, so `W` has no part in what the database refuses. **What the relaxation does not do** (my reasoning, no test shows it): it does not cover the two disclosed limits. A stalled commit or a guard-bypassing session is not bounded by any fixed margin, so keeping `+ W` would not have covered them either. The rule is a plausibility refusal against an upper bound and is worded so (R2-M1 below) | 3.1 (kind row; the margin test); 3.2; E14 |
| **Answer 2** (former item 8) | "(i) Accept the limit (Recommended)" | The end-to-end ACK-loss ordering is first exercised at the real run, if it occurs there; no rehearsal install. R3's and R5's exits claim only what they show (R3: SQL-level durability of a crafted commit, no outcome code; R5: the shared tail's classification on a `SYNTHETIC_TEST` commit, and the real branch's refusal and rollback). **A correction to PD-0068's summary** (the owner's answer is unaffected): PD-0068 says R3 can show "UNKNOWN, no retry" on a crafted commit; R3 has no outcome code, so that test is R5's | 1 (item 5); 4.4 (the d6 table, "The reviewers' answer", "What each exit may claim"); 7.1 (R3, R5, R8); 8.1 table; section 9 |
| **Answer 3** (former item 9) | "Accept both"; "Yes, test it (Recommended)" | D-1 (expiry not observable on real data) and D-2 (rollback after writes not forced) are accepted deviations, stated in the HG4 package as not collected. R8's last step is **withdraw (all four rights shown refused), then renew**, two separate owner publisher acts, each citing its own decision record; the renewal carries the same `valid_until` and the three basis entries. The other collectible E9 items are collected on the real context. Two-user isolation stays conditional (R2-L4 below) | 7.1 (R8 and the block "E9's other post-run evidence"); 7.1 (R7); 2.5; 3.1 (renewal); E25; 8.1 table |
| **Answer 4** (former item 10) | "As proposed (Recommended)"; "Keep 2027-09-01" | The first HG4 publish record states one entry per member source: `alphavantage.us` `LEASE_TERM` (`term_end_not_after` 2027-10-01T00:00:00Z), `openfigi` `NOT_ASSESSED`, `calendar.manual` `NOT_ASSESSED`; kind `LEASE`, `NONE` unreachable; `valid_until` 2027-09-01. The upper-bound limit is disclosed as PD-0068 states it, in the publish record and the HG4 package | 3.1 (HG4 block); 2.5; 7.1 (R8); 8.1 table; E14 |
| Former 8.1 items 7 to 10 | n/a | Removed as open questions; a table in 8.1 cites PD-0068 and says where each answer is reflected | 8.1 |

### 12.2 The round-2 findings

"Fixed" means fixed in the text of this design; nothing is built or run. "Partly" says what stays.

| Finding | What it said (short) | Status | What changed | Where |
|---|---|---|---|---|
| **R2-M1** (MEDIUM) | The margin rule compares `valid_until + W` against an upper bound of the term end, and the HG4 value was called "the earlier reading" | **Fixed in wording; the limit remains and the owner accepted it** | The rule is relaxed (12.1) and is worded as what it is: a refusal of a `valid_until` later than the latest the term could end; "it does not show that the lease stays inside the licence term". Publish and the status view print that sentence, never "within the term". The HG4 limit is disclosed as PD-0068 states it (a term that began before about 2026-09-01 would end before `valid_until`; pinning the signup date would remove it). `2027-10-01T00:00:00Z` is recorded as the owner decided it and called the later, weaker reading of PD-0066's "on or before 2027-10-01"; the earlier instant is 2027-09-30T16:00:00Z. A test asserts the wording | 3.1 (kind row, HG4 block); 3.2 (margin test and the wording test); E14; section 9 |
| **R2-M2** (MEDIUM), **TR2-M4** (MEDIUM) | The preflight refuses wherever the plan runs it: the installer, R1's publisher-tool tests and R7's launcher cannot pass it on any cluster that exists before R8; a skip flag would then be invented outside review | **Fixed** | The preflight is for **REAL installs only**. A tool decides from the database's install-kind row and its name (reserved prefix `finweb_real`), by the decision table of 1.2 rule 5.2; there is no flag, environment variable or configuration key. TEST installs and the development clusters never meet it; five other means keep them apart (own cluster, the install kind in both directions, name tripwires, the real tools' own target decision, and the sandbox allowlist, the weakest and not relied on). The installer runs as the superuser in the owner's terminal and checks every other path and every role it creates, instead of checking its own role. Two installers, each able to write only its own kind. A static no-bypass test; the gate is a separate item in R6's review | 1.2 (scope; rule 5.1 to 5.4); E24; 7.1 (R6, R7, R8); W13, W14; 4.2 |
| **TR2-M2** (MEDIUM) | The install rule leaves PostgreSQL's ordinary password stores (`~/.pgpass`, `pg_service.conf`, `~/.psql_history`, the server log) open, and the preflight, which uses `passfile=/dev/null`, cannot see them | **Partly: checkable parts checked, the rest an owner procedure, said plainly** | Rule 2 has a table that separates, store by store, what is a **checkable rule** (libpq's default credential sources, through the probe's Pass B; the logging settings; the cluster's paths, partly) from an **owner procedure** (`\password` instead of a literal statement, shell history, scrollback, editors, backups). It says plainly what **cannot be enforced from inside the database**: how a password was typed or kept, what a process running as the owner's OS user can read, the permissions of the data directory. A passing preflight shows only that no credential-free path exists from where it ran, now | 1.2 (rule 2, rule 5.3 (d), 5.4); fact 18; 7.1 (R6) |
| **TR2-M3** (MEDIUM) | The preflight tries only superuser names against one database | **Fixed in text; the classifier and some catalog reads are "not shown"** | The probe specifies what it inspects and tries: every LOGIN role (and one never-created name) against every `datallowconn` database over the socket; a `replication` attempt for the super and replication roles; escalation paths through `pg_has_role` and the predefined roles; two passes (A: scrubbed environment; B: the caller's default credential sources); outcome classes where **only `CHALLENGED` passes** and an error after authentication, a timeout and anything unrecognised refuse; superuser-only checks of `pg_hba_file_rules`, `pg_authid` and `SHOW` in the installer. It says what a runtime tool (a non-superuser) can and cannot see (5.4). The decision logic has a case list. **Not shown:** that a non-superuser may read `pg_database`, `pg_auth_members` and call the functions for another role; which server messages a refused attempt produces (calibrated at R6); that `3D000` has already authenticated | 1.2 (rule 5.3, 5.4, rule 7); section 9; 7.1 (R6) |
| **TR2-M1** (MEDIUM) | The product-path proofs of the COMMIT-time deadline guard and the commit-outcome classification cannot run before R8 (the real branch never reaches its seal, its by-name firing or its COMMIT; the recorder would pass vacuously; R3 has no outcome code and its database is dropped) | **Partly: most of the tail is now shown before R8; a residual is a new question for the owner** | **A pre-R8 product-path proof inside PD-0066 decision 8:** the post-seal tail is one function shared by the real create and the `SYNTHETIC_TEST` create (E23). The `SYNTHETIC_TEST` service accepts, so R5 runs the tail on an accepted commit (T-a to T-e: the recorder sees a named `SET CONSTRAINTS` and fails if it saw none; a stall past `complete_by` is refused at COMMIT; simulated acknowledgement loss as F2's `test_c20` does it; a killed connection; crafted partial state), with no `synthetic = false` and no bypass. The reconciliation tests make their own committed state. R3 claims SQL-level facts only. **What stays unshown before R8:** the real branch's seal on an accepted result, any constraint only it has, the real commit's timing, and any stall or fault drill on the real commit. **PD-0068 does not cover this; it is the new owner question, 8.1 item 11** | 4.4 (Step 1, Step 2); 3.2 (the R5 shared-tail bullets); 7.1 (R3, R5, R8); 8.1 item 11; E11, E23; section 9 |
| **R2-L1** (LOW) | (i) R4b required a sidecar per invented member, though 4.2 forbids storing one; (ii) the member list (three files of 6.3) is ambiguous and the calendar has no sidecar | **Fixed, except the calendar sidecar's reference** | (i) R4b's tests use in-memory sidecars; no sidecar file is written for an invented payload; under `TEST_SWITCH` O5 is bypassed. (ii) The members of `M` are three files (`AAPL_compact.csv`, `AAPL_UW.json`, the NYSE calendar) giving three sidecars, and the XNGS pair is not a member. **Left for the main session:** the calendar sidecar's decision reference | 6.1; 7.1 (R4b, R8) |
| **R2-L2** (LOW) | R1 items need objects R1 does not build: (i) a registered root, (ii) the named-form test's foreign key, (iii) the O1 and label codes in the install-kind test | **Fixed** | (i) R1's read-lease tests use a crafted root fixture (E11). (ii) The named-form test fires the new root-link-to-portfolio foreign key, which is deferrable; F2's lease-to-root key is not. (iii) R1 asserts the install-kind code only; R2 adds O1, R3 the label code | 3.2; 4.2 (staged assertions); 7.1 (R1 to R3) |
| **R2-L3** (LOW) | The owner's answer to the ACK-loss item gated nothing | **Fixed** | PD-0068 answer 2 accepted the limit. The design recommends that the HG4 package list it among the accepted limits (PD-0068 requires the statement only for D-1 and D-2; the main session decides); the residual of the tail (item 11) gates R8 | 7.1 (R8; after the observations list); 8.1 item 11 |
| **R2-L4** (LOW) | Two-user isolation can drop out without a declared deviation | **Fixed** | R7's exit states whether the real-mode app can hold a second user without an economic write; if not, isolation is a third declared deviation, D-3, put to the owner through the PM before R8 | 7.1 (R7; the E9 block) |
| **R2-L5** (LOW), **TR2-L1** (LOW) | E20 and the section 11 M-3 row say "no `peer` for a privileged role"; rule 1 says any role | **Fixed** | E20 and the section 11 row say no `trust`, `peer` or `ident` for any role; rule 1 gives the reason (agent Bash runs as the owner's OS user) and the `initdb` options that avoid ever writing a trust line | 1.2 (rule 1); E20; section 11 (marked) |
| **R2-L6** (LOW) | The section 11 M-2 row says the executor "cannot insert into `rw_root`" while 2.6 lists `rw_root` among its writes | **Fixed** | The row is corrected in place and marked: the executor cannot insert into `rw_root_link` (the registry) or the lease table, and writes `rw_root` and `rw_revision` only under a create lease | section 11 (marked); 2.6 |
| **R2-L7** (LOW) | Fact 17 says F2 never names a constraint trigger | **Fixed** | F2 already fires `ledger_event_transfer_pairing` by name (`guarded_workspace_context.py:88, :100`; `0003_ledger_event_guards.sql:203-205`). Fact 17 says so, and notes the manual's "will act on all matches": the deadline guard's name is unique in the schema, a catalog test asserts it, and the recorder test names it as a thing never to appear | fact 17; 3.1 (in-flight row); 3.2 |
| **TR2-L2** (LOW) | The tripwire covers three tools; the environment-driven PostgreSQL tests are not covered | **Partly: tripwires, with the residual stated** | `Provisioner.preflight` refuses a cluster that holds a `finweb_real*` database; `connection.missing_env_vars` refuses a database name with that prefix, which covers the nine modules; the residual (an environment pointed at the real cluster with another database name) is said plainly, and stopped by the credential rule | 1.2 (scope; rule 6); 7.1 (R6) |
| **TR2-L3** (LOW) | R1 tests need pieces later increments build | **Fixed** | Same fixes as R2-L2 (i) to (iii) | as R2-L2 |
| **TR2-L4** (LOW) | The list route (E22) has no admission model R1's admit can serve | **Fixed** | A definer enumeration function `rw_list_roots(owner_id)` returns ids only; the route then admits one `ARCHIVE_READ` per root and returns a per-entry `status`, so a lapsed or withdrawn context is listed as such and a list is never an empty array that reads as "no portfolio" | 2.4 (citing `v1.sql:140`, `:134-162`, `:127-133`, `:431`); 7.1 (R1, R5); E22 |
| Observation: `observations/` not ignored | | Fixed upstream | `.gitignore:43` ignores `data/marketdata/observations/` (committed `ae6dfdc`) | fact 9 |
| Observation: 1.16 item 9 conditions | | Reflected | The five conditions of `market-data/1.16` item 9 are in 1.1 and in 7.4 (C6, claim N-8); 8.1 item 1 is answered | 1.1; 7.4; 8.1 |
| Observation: fact 11 counts `.py` files | | Reflected | The note that 27 tracked files match, including the F2 SQL | fact 11 |
| Observation: 4.3's render fixture | | Fixed | The fixture states its `synthetic` value through `usage_scope`; the test asserts it (`contracts.py:259-262`, default `:227`) | 4.3 |
| Observation: other `SET CONSTRAINTS ALL` sites | | Reflected | The static audit lists the four sites at HEAD and shows the real create path reaches none | 3.2 |
| Observation: "as for the other lease triggers" is loose | | Fixed | Reworded: the limit is of the deferred guard alone | 3.1 (in-flight row) |

### 12.3 What is left

- **8.1 item 11, a new question for the owner** (TR2-M1): the residual of the post-seal tail. PD-0068 does
  not answer it.
- **The HG4 expiry limit** (R2-M1) stays, as the owner accepted it. Only the owner's signup date would
  remove it.
- **Password stores** (TR2-M2) stay an owner procedure; the design adds no control it cannot enforce.
- **Not shown** (section 9): a non-superuser's catalog reads, the refusal messages the classifier will see,
  `3D000`, the order of steps inside PostgreSQL's commit, and the sandbox's socket allowlist as a control.
- **For the main session:** the calendar sidecar's reference (R2-L1 (ii)); STATUS.md is not updated by me;
  PD-0068's summary of R3 needs the small correction above; the later of two readings of the term end
  (2027-10-01T00:00:00Z) is the owner's recorded value, and the main session may ask whether the earlier
  instant is preferred.
- **Choices of mine that no PD or contract covers** (8.2): E23 (the shared tail and the `SYNTHETIC_TEST`
  create), E24 (the preflight keyed to the install kind and name), E25 (a renewal's `valid_until` is not
  earlier than the current one; **superseded in the fix round, section 13: an earlier date is a date
  correction**), the relaxed plausibility rule, the `finweb_real` reserved prefix, and the
  rule that the installer may run as the superuser. Each is for the technical-reviewer and the owner to
  change.
- **The re-check required before R1** (PD-0066 decision 10): the technical-reviewer's check of this
  version. Ruling 6.5 and the A.6 text were not re-diffed against 1.16 in this round (I read the 1.16 change
  note and item 9 only).
- **The file is uncommitted**; the owner decides when it is committed.

## 13. Round 3 fix round (2026-10-25)

The two reviews of the round-3 revision found 5 MEDIUM and 15 LOW findings: decision conformance R3C-M1 and
R3C-L1 to R3C-L7, and technical TR3-M1 to TR3-M4 and TR3-L1 to TR3-L8 (one MEDIUM, R3C-M1, and the technical
TR3-M4 describe the same defect). I had them from the main session's relay; they are now recorded in
`reviews/TECH_REVIEW.md` and round 4 read them there. Every change is a design claim
until built, tested and re-reviewed. **I ran no SQL, no test and no build, and connected to no server**
(the "How this was checked" list, fix round). Code facts cite HEAD `7effcc8`; for PostgreSQL behaviour the
text says whether a HEAD test or the installed 17.11 manual shows it, or that it is "not shown". I changed
this file only. Nothing here approves a gate, a download, a publish or a change to a protected file.

### 13.1 The findings, one by one

"Fixed" means fixed in the text of this design. "Re-scoped" says what is stated instead of removed.

| Finding | What it said (short) | Status | What changed | Where |
|---|---|---|---|---|
| **R3C-M1** (MEDIUM), **TR3-M4** (MEDIUM) | E25 refused a renewal with an earlier `valid_until`, so the date correction that PD-0066 decision 5 ("The owner can correct it from the signup date") and PD-0068 answer 4 ("would remove the limit") give the owner was blocked in the one case where it matters, while 3.1 still said the correction removes the limit | **Fixed: the first of the reviewers' options** | **E25 is amended.** A renewal's `valid_until` must be strictly later than the server clock at the record and may be later than, equal to, or earlier than the current one. An earlier one is a **date correction**: its own decision record naming the corrected date and reading, fresh basis entries from that reading, the plausibility rule against the new date, the head exclusive lock (so it is appended only when no lease is in flight and no lease admitted under the longer date outlives it); the tool prints "moved earlier". 3.1, 8.1 item 4 and section 9 now state **what the pin remedy requires**: the term end derived from the pin must still be in the future (else the remedy is a withdrawal), a correction can be delayed by overlapping admissions (the owner then withdraws; not run), and until the owner records it the limit stands. **[Round 4, R3R-L2: corrected. A new `valid_until` must be ahead of the clock; a pinned term already over with no notice is met by a renewal for the Renewal Term, not a withdrawal; a delayed correction waits, and withdrawing is the owner's choice (3.1).]** Tests: the date-correction cases and a pin-scenario fixture. The second option (keep E25 and put it to the owner) is not taken; the PM is told that E25 changed (8.1, "For the PM") | 3.1 (kind row, Renewal row, HG4 block); 2.3 item 4; 3.2 (renewal tests); 7.1 (R1, R8); 8.1 item 4; 8.2 E14, E25; section 9 |
| **TR3-M1** (MEDIUM) | Pass B cannot see a service-file entry unless a service is named, a passfile libpq skips, or a set `PGPASSWORD`; the design listed these stores as checked by Pass B | **Fixed in text; the scan's limits are stated** | A new **Pass S, a static scan** without connection, in each real tool's own process: refuses when `PGPASSWORD` is set (any value); on **any** passfile line (the `PGPASSFILE` file, else `~/.pgpass`) whose host is the cluster's socket directory, `localhost` or `*` and whose port is the cluster's or `*`, **whatever the file's mode**; on any service-file section (the `PGSERVICEFILE` file, else `~/.pg_service.conf`, and `pg_service.conf` in `PGSYSCONFDIR`) with a `password` that could address the cluster, **whether or not a service is named**; follows a section's `passfile`; an existing unreadable file refuses. It prints the store, file, line or section and the fields before the password, never a password. Pass B stays as a backstop and the text says why it cannot be the check (the manual: a passfile with group or world access "will be ignored"; a service file is used only when a service is given). The rule-2 table and the case list changed accordingly (a `0644` passfile, an unnamed service section, a wrong `PGPASSWORD`, a `passfile` chain). **What it cannot see** (a notes file, a shell profile, a `.env` file, another process's environment, an application's configuration) is stated in rule 2, 5.4 and section 9 | 1.2 (rule 2 table and note; 5.3 (d); 5.4; rule 7); E26; section 9 |
| **TR3-M2** (MEDIUM) | The escalation check omitted `pg_write_all_data` and `pg_read_all_data`, which give DML and reads on the grant-protected authority tables | **Fixed in text** | 5.3 (b) is an **allow-list**: any LOGIN role that is a member of **any** `pg_*` predefined role (enumerated from `pg_roles` at run time, so later versions are covered) refuses unless the pair is on the allowed-pairs list, which the installer writes once, empty by default, naming only pairs whose credentials no agent holds. It also covers membership, direct or through an intermediate role, in the owner, publisher, executor and loader roles. The reasons are from the manual (`pg_write_all_data` acts "as if having INSERT, UPDATE, and DELETE rights", without `BYPASSRLS`) and from F2's pattern (row security on the eight economic tables only, `guarded_workspace_v1.sql:426-431`; authority tables `REVOKE`d, `:441`; immutability triggers on six tables, not the head, `:436-438`). Each of `pg_write_all_data`, `pg_read_all_data`, `pg_execute_server_program`, `pg_read_server_files`, `pg_write_server_files` and `pg_signal_backend`, direct and through an intermediate role, an unknown `pg_*` name, an allowed pair and the excluded superuser has its own test case. **[Round 4, TR3R-M1: the allowed-pairs list and the run-time `pg_*` enumeration are gone; a LOGIN role's membership in any other role refuses, with no exemption (1.2 5.3 (b)).]** | 1.2 (5.3 (b); rule 7 cases); E26 |
| **TR3-M3** (MEDIUM) | The publisher tool ran the preflight on every invocation, and a timeout or a missing socket counted as a refusal, so a failing preflight blocked the owner's withdrawal on notice | **Fixed** | **The gate is keyed to the command.** `publish` and `renew` (a date correction is a renewal), the launcher and the admission probe are gated. **`withdraw`, and re-running a pending one, is never gated**: it reads the install facts only to learn whether the target is REAL, makes no `require_auth` demand, commits the drain mark first, appends the generation, and then runs the self-check and the probe and prints the result beside its own, with the withdrawal's own exit status. The result is printed, not stored. The case list has the same failing facts (including a probe timeout and a missing socket) refuse `publish` and `renew` and not `withdraw`. An owner who must shorten the life at once, with the environment unrepaired, withdraws. A server that is down or a role that cannot log in still stops a withdrawal; the lapse is the backstop (section 9) | 1.2 (5.1 table, 5.2, rule 7); 3.1 (Notice or termination, Renewal); E24; W14; section 9 |
| **TR3-L1** (LOW) | The outcome classes refused what rule 1 allows: a `reject` line, a missing `replication` line, a role checked against itself | **Fixed** | A third passing class, `REJECTED` (a `reject` record matched, or no record matched; "If no record matches, access is denied", `auth-pg-hba-conf`; the keyword `all` does not match `replication`). The installer also checks that the rows predict it. No `replication` line is required. A role is not checked against itself in 5.3 (b). Case-list entries added. The server message texts are not in the manual pages I read, so the classes are calibrated at R6 or first at R8 step 1 | 1.2 (5.3 (b), (e), (f); rule 7) |
| **TR3-L2** (LOW) | R6 cannot calibrate `CHALLENGED` on the development cluster, and the accepting-side test conflicts with the prompt-only credential rule | **Fixed; the limit is stated** | The development clusters trust their roles by design (`dev_env.py:13`), so a password-protected role there connects without a challenge (my inference from `auth-trust`; their `pg_hba.conf` not read): R6 shows the **refusal side only** there. `CHALLENGED` and `REJECTED` are calibrated on a throwaway cluster under `$TMPDIR` **only if the owner grants the sandbox exception**, with the tools' prompts driven through a pseudo-terminal, so no tool gains a credential option; the static no-bypass test fails if any tool gains a password option, a password file or a credential environment read. **Without the exception they are first calibrated at R8 step 1**, and a mis-calibration fails closed (`OTHER` refuses) and blocks that step. **[Round 4, TR3R-M2: the throwaway cluster only calibrates the classifier; it runs no real tool and cannot show the accepting side, which is first exercised at R8 step 1 on every path (1.2 rule 7).]** | 1.2 (5.2 tests, rule 7); 7.1 (R6) |
| **TR3-L3** (LOW) | 5.3 (c) checked `CONNECT` elsewhere but defined no decision, and a cluster of its own does not make the claim true | **Fixed** | Decision: the preflight refuses on any `CONNECT` a real role holds outside the real database, PUBLIC's default included (the manual lists `CONNECT` among PUBLIC's defaults on databases; that `postgres` and `template1` carry it is my reading, not shown). The real installer therefore revokes PUBLIC's `CONNECT` on `postgres`, `template1` and any other connectable database of its cluster in Phase 1. Section 1 item 2 and rule 3 now say a cluster of its own does not by itself make the claim true | section 1 item 2; 1.2 (rule 3, 5.3 (c)); 7.1 (R6) |
| **TR3-L4** (LOW) | The runtime probe tried only the Unix socket, so TCP drift after install was invisible | **Fixed, with a stated limit** | A loopback TCP attempt from a sandboxed process says nothing about the server (CLAUDE.md), so none is made. Every runtime tool instead reads `SHOW listen_addresses` and refuses unless it is empty; the manual says the setting "can only be set at server start" and that an empty list means only Unix-domain sockets. Whether a non-superuser may read it is **not shown**; a tool that cannot read it refuses. 5.4 says the runtime vantage cannot see the hba rows | 1.2 (5.4, 5.3 (e), rule 7 case list) |
| **TR3-L5** (LOW) | Rule 3's shared-cluster option implied the existing test tooling could be given credentials again | **Fixed** | Rule 3 says that on a shared cluster the superuser-driven test tooling **could never run again** (`guarded_pg_provision.py:73-74` needs a superuser that can create roles and databases; rule 2 forbids an agent-run tool that password; 5.3 (a) refuses other LOGIN roles with a power attribute) and that the approved lists may name only roles whose credentials no agent holds. The option is kept as exceptional. **[Round 4, TR3R-M1: the approved lists are removed; 5.3 has no exemption.]** | 1.2 (rule 3, 5.3 (a), (b)); 7.1 (R6) |
| **TR3-L6** (LOW) | The `SYNTHETIC_TEST` create (E23) had no named seal, validation, storage or building increment, and Step 2 item 2 counted the root-link key as real-branch-only | **Fixed; one assumption is unverified** | 4.4 Step 1 has a table of the parts: S2 storage (R3); **a fictional-branch seal and validation forked from F2's `gw_check_artifact` and `gw_validate`, reading `rw_root` and `rw_revision` where F2 read `web_saved_sandbox` and `web_portfolio_revision`** (`guarded_workspace_v1.sql:256-257, :297, :300, :362, :368`) (R3, SQL); the executor's grant list is one list for TEST and REAL, with a catalog test that the two are identical and exclude `web_saved_sandbox`, `web_portfolio_revision` and `web_csv_*`, so T03 audits REAL's role plan; Python in R5 that calls the existing fictional integration. **After R3 no increment adds gateway SQL**, so R6's audit covers it. Step 2 item 2 is corrected: the S2 tables and the root-link key are shared by both branches; R3's exit lists each branch's deferrable-constraint inventory and R5 compares them, expecting an empty difference. **Not verified:** that the existing fictional integration runs over the S2 tables unchanged (I read only the lines of fact 12). R5's first task checks it, with a thin adapter as the fallback; if no accepted synthetic result can be had, 8.1 item 11 widens. **[Round 4, R3R-M1: the fictional-branch seal and validation are a TEST-only SQL part that a REAL install does not hold (section 1 item 1).]** | 4.2 (build table); 4.4 (Step 1 table, Step 2); 7.1 (R3, R5; dependency paragraph); E23; section 9 |
| **TR3-L7** (LOW) | Reads, export, reproduce and the list also rely on the deadline guard staying pending until COMMIT, but the audit and the recorder covered only the create | **Fixed** | A **shared read tail** (E23 extended) used by read, reproduce and each list entry for both branches; the static audit extends to those paths and to the same `SET CONSTRAINTS ALL` sites (HEAD `web_workspace_store.py:334-335` is one); a **non-vacuous recorder** on each (it must record the path's own statements, and zero `SET CONSTRAINTS` of any form); a stall test for each (T-f, T-g): refused at COMMIT with `RW_DEADLINE` and no value delivered. The real branch's own reads have no real root before R8, so they are first run there. The export check is the probe, not a commit path | 3.1 (in-flight row); 3.2; 4.2 (build table); 4.4 (T-f, T-g, the test table); 7.1 (R5) |
| **R3C-L2** (LOW), **TR3-L8** (LOW) | R8's last step must show all four rights refused, but the slice has no export route | **Fixed** | The scoped contract has no export route and a real export purpose is later work, so the design names the check: **the admission probe** (E27, built in R7), a one-shot command on the executor connection that calls the gateway's admit for `ARCHIVE_EXPORT` (or the other read-phase purposes; never `EXECUTE_CREATE`), prints the outcome or refusal code, and rolls back. It is run before the withdrawal (admitted, the positive control) and after (refused), labelled "direct gateway admission, not a product route" in its output and in the HG4 package. Create, read and reproduce are shown refused at the real-mode routes, and the list shows the per-root status. `evidence_pack real` is **not** the export check (it builds a pack from files on disk and is unaffected by a withdrawal) and the text says so. The HG4 package states that export was shown at the gateway and not at a route | 7.1 (R7, R8, the E9 block); 5.1 table; E27 |
| **R3C-L1** (LOW) | The HG4 block still read the plausibility rule as a safety margin ("a month to spare") | **Fixed** | Replaced by the exact statement: `valid_until` (2027-08-31T16:00:00Z) is not later than the recorded upper bound (2027-10-01T00:00:00Z), "which is all the rule says"; "not a margin and not a month of buffer"; the term may already end before `valid_until`. The R1 fixture description no longer says "a month before" | 3.1 (HG4 block); 3.2 (expiry evidence) |
| **R3C-L3** (LOW) | D-3 was put to the owner but gated nothing, and the HG4 limits list omitted it | **Fixed** | 7's list of accepted limits includes D-3 (conditional on R7 declaring it and the owner accepting it). **R8's Needs include R7's exit statement on two-user isolation and, if it declares D-3, the owner's recorded answer** (silence is not an answer; R8 does not start without it). The HG4 package states D-3 as it states D-1 and D-2. **[Round 4, R3R-L3: an answer that is not an acceptance also stops R8.]** | 7 (intro); 7.1 (R8, the E9 block); section 9; 8.1 ("For the PM") |
| **R3C-L4** (LOW) | R8 step 1 decided who holds the executor and loader credentials, a choice the design leaves to R6 | **Fixed** | R8 step 1 now says the superuser and publisher passwords go to no agent session and that the executor and loader credentials are held **as R6's approved plan names** (1.2 rule 4); an agent holder is the recorded limit of rule 4, reached by a prompt and never a file or the environment. R6's row says it decides this with the owner's approval | 7.1 (R6, R8); 1.2 (rule 2 table, rule 4) |
| **R3C-L5** (LOW) | The design corrected PD-0068's R3 summary but not its R5 summary ("committed, rolled-back and UNKNOWN states by the reconciliation code") | **Fixed** | 4.4 says the reconciliation code classifies **committed** and **UNKNOWN** only; a rolled-back result comes from a create call's own definite refusal (T-b), never from absence (E10 section 6; `guarded_workspace_store.py:352-357`: "absence remains UNKNOWN"). R5's exit says so, and the "For the PM" list flags the second correction of PD-0068's summary (the owner's answer is unaffected) | 4.4 ("What each exit may claim"); 7.1 (R5); 8.1 ("For the PM") |
| **R3C-L6** (LOW) | Two stale "pending the Quant" statements after `market-data/1.16` was committed | **Fixed** | Section 0's D1 row now says the `state_kind` confirmation is in (1.16 item 9). 7.1a item 2 says the A.6 `UW` / XNGS update is committed (`methodology/CP2_MARKET_DATA_CONVENTIONS.md:56`, read today) and that what is pending is the engineer's change to `exchange_codes.py:82` (still `MEMORY`, read today), so the PM need not dispatch the Quant for it. A search for other "pending the Quant" wording found none | section 0 (D1); 7.1a item 2 |
| **R3C-L7** (LOW) | R1's Needs omitted PD-0066 decision 10's third pre-R1 condition (committed when the owner asks) | **Fixed** | R1's Needs now read: this design revised and reviewed after the fix round, **and committed when the owner asks** (`PD-0066:376-386`, "Before R1", steps 1 to 3); the header says R1 does not start before then | header; 7.1 (R1) |

### 13.2 What is left

**[Round 4: this list is the state at the end of round 3; section 14 says what changed.]**

- **The design has not been re-checked.** PD-0066 decision 10 requires the technical-reviewer's check of this
  revision, and then the commit the owner asks for, before R1.
- **Mechanisms of mine that no PD or contract covers, and that changed or are new** (8.2): E25 (amended: a
  renewal may carry an earlier `valid_until`), E26 (the static credential scan and the `pg_*` allow-list)
  and E27 (the admission probe), plus the amendments of E20, E23 and E24. The PM tells the owner that E25
  changed (8.1, "For the PM"), because the first form narrowed a correction path that PD-0066 decision 5
  and PD-0068 answer 4 record; no PD or contract says the new form either.
- **Not shown** (section 9, extended): a non-superuser's reads of `pg_database`, `pg_auth_members`,
  `pg_has_role` and `SHOW listen_addresses`; whether `pg_has_role` counts a superuser or a role itself as a
  member; the server's message texts for `CHALLENGED` and `REJECTED`; that `postgres` and `template1` carry
  PUBLIC's `CONNECT`; that a password-protected role on a trusting cluster connects without a challenge;
  that a pseudo-terminal can drive the prompts in the sandbox; and that the existing fictional integration
  runs over the S2 tables unchanged.
- **Pass S can refuse a legitimate file.** A wildcard line (`*:*:*:user:password`) that the owner keeps for
  another cluster also matches the real cluster and refuses. The owner narrows it to the other cluster's host
  and port. This is intended (a wildcard line could address the real cluster) and is the price of not
  trusting libpq to skip it.
- **The static scan and everything in rule 2 that stays an owner procedure** cannot show where else a
  password was kept; the design adds no control it cannot enforce.
- **Noticed, not changed:** R8 step 2, the qualification run, connects as the loader role and is not one of
  the four gated tools. The loader writes only unreferenced `md_*` rows (W04), so I left it outside the
  gate; a reviewer may want it gated, and the cost would be one more row in 5.1.
- **For the main session:** record the round-3 reviews and this fix round; decide whether to correct
  PD-0068's R3 and R5 summaries; name the calendar sidecar's reference (6.1); STATUS.md is not updated by
  me.

## 14. Round 4 changes (2026-10-25)

The two re-reviews of the round-3 fix round (the sections headed "... re-review" in `reviews/TECH_REVIEW.md`)
found 3 MEDIUM and 7 LOW findings (conformance R3R-M1, R3R-L1 to R3R-L3; technical TR3R-M1, TR3R-M2, TR3R-L1
to TR3R-L4) and some observations. The owner's instruction for the round: prefer narrowing claims and
conforming to the decisions over adding mechanisms. Every change is a design claim until built, tested and
re-reviewed. **I ran no SQL and no build, connected to no server, and did not run the product tests: the
change is design-only.** Where this section differs from sections 10 to 13, this section and the body govern.
The file had 2819 lines (SHA-256 `f362a822…0a96`) at the start of the round.

| Finding | Fix | Where |
|---|---|---|
| **R3R-M1** (MEDIUM) | Conformed to PD-0066 decision 6 ("only a real-only gateway"), the reviewer's option (a): the fictional branch's seal and validation are a TEST-only SQL part that only the TEST provisioner runs, so the real installer never applies it (14.1, TR4-M2, says what shows that a REAL database holds none of it, and when). The executor's table grants stay one list in both installs. Every "one gateway SQL serves both kinds" sentence is replaced. Option (b), a new owner reading, is not taken | 1 item 1; 4.2; 4.4; 7.1 (R3); E23 |
| **TR3R-M1** (MEDIUM) | Narrowed what is allowed. Nothing the owner decided needs an allowed-pairs or approved-power list, so both are removed, with the role names in the install-kind row. A LOGIN role's `MEMBER`, `USAGE` or `SET` in any other role refuses; at most one LOGIN role, a superuser found by attribute, has a power attribute. The reviewer's cases are added | 1.2 (rule 3, 5.3 (a), (b), rule 7); 2.1; E20, E26; 7.1 (R6) |
| **TR3R-M2** (MEDIUM) | Narrowed. The installer's accepting side is first exercised at R8 step 1 on every path. The throwaway cluster (only with the owner's sandbox exception) calibrates the classifier of `CHALLENGED` and `REJECTED` and nothing else; its recipe is corrected; it holds no gateway and no REAL-scope content, so it is not the rehearsal install PD-0068 answer 2 declined. The crafted `REAL`-row gate test is dropped | 1.2 (rule 7, 5.3 (f)); 7.1 (R6); E20; 9 |
| **R3R-L1** | E11 names the owner-written crafted fixture of 3.2 | E11 |
| **R3R-L2** | A pinned term already over with no notice given means the licence renewed (PD-0066 decision 5): the remedy is a renewal for the Renewal Term, not a withdrawal. Withdrawal stays for notice or termination. A fixture is added; "the owner withdraws" is removed from the delayed-correction case | 3.1; 3.2; 8.1 item 4; 9 |
| **R3R-L3** | The narrower fix: an answer on D-3 that is not an acceptance stops R8, as item 11's does. No new package rule | 7; 7.1 (R8); 8.1; 9 |
| **TR3R-L1** | Pass S also scans the default locations and refuses any passfile line, or service section with a `password`, whose user names a real LOGIN role, whatever its host or port | 1.2 (rule 2 table, 5.3 (d), rule 7); E26 |
| **TR3R-L2** | The smallest check, and a stated limit. No real role has a role-level setting (`rolconfig` empty, no `pg_db_role_setting` row) or the `SET` privilege on `session_replication_role`, and the session's own value is `origin`; the executor's timeouts are connection options. Grants are not re-read at a gated start; they are audited at install (14.1: by Phase 2 and `--check`; the privilege check also covers `ALTER SYSTEM`) | 1.2 (5.3 (a), 5.4, rule 7); 3.1; 3.2; E4; 9 |
| **TR3R-L3** | The launcher and probe tests, and their gate review item, moved to R7, where those tools are built | 1.2 (5.2, rule 7); 7.1 (R6, R7) |
| **TR3R-L4** | Bounded the reads of the rooted tables and the archive: the row policy's read branch and the archive read function check `clock_timestamp() < complete_by`; an R3 test is added. **The `md_*` rows are not covered (14.1, TR4-M1).** The D3 row claims no more than that | section 0; 1.2 rule 4; 2.6; 3.1; 3.2; E4; 7.1 (R3) |
| Observations | A refused reconciliation maps to UNKNOWN (3.1, T-e). STATUS.md is cited by quoted text, and the `--admin-user finweb_dev` parenthetical is dropped (STATUS.md has no such text). The throwaway cluster holds no REAL content. Listing the other limits is a rule (7.1). E25 is to be told to the owner (8.1). `withdraw` without `require_auth` is unchanged, its limit stated in 5.1, because a `require_auth` refusal would be one more thing that can stop a withdrawal | as listed |

**Mechanisms added** (the smallest that keeps a decision or an invariant intact):
- the TEST-only SQL part (R3R-M1). PD-0066 decision 6 says "only a real-only gateway"; the alternative,
  putting a new reading of decision 6 to the owner, is not taken in this round. The part splits functions
  that R3 builds anyway;
- one time check on the read side of the rooted tables and the archive (TR3R-L4): the owner capped "every
  operation's deadline" at `valid_until` (PD-0068 answer 1, as the question put it). 14.1 narrows what it
  claims: the `md_*` reads are outside it;
- three refusal rules in the existing preflight (user names in Pass S; settings; the membership rule that
  replaces two lists). They add no object and narrow what passes. The settings rule reads
  `pg_db_role_setting` and `has_parameter_privilege`, which a non-superuser may not be able to read (not
  shown); a tool that cannot read them refuses.

**Claims narrowed or removed.** The allowed-pairs and approved-power lists and the `pg_*` run-time
enumeration. The throwaway cluster's claim to show the accepting side, and the crafted `REAL` row. The
executor's role-level timeouts. The pin remedy as a withdrawal. The D3 row's "no operation completes after
`valid_until`". The shared-cluster option (no exemption). The R6 tests of tools that R7 builds. The
preflight's re-reading of grants (a stated limit).

### 14.1 Second fix round (2026-10-25)

The two re-reviews of round 4 found 2 MEDIUM and 6 LOW findings (conformance R4C-L1 to R4C-L4; technical
TR4-M1, TR4-M2, TR4-L1, TR4-L2). The same instruction applies: narrow and conform before adding. I ran no SQL
and no build, connected to no server, and did not run the product tests: design-only. The file had 2976 lines
(SHA-256 `bc7e055e…9eca`) at the start of this round and has 3126 now.

| Finding | Fix | Where |
|---|---|---|
| **TR4-M1** (MEDIUM), **R4C-L3** | Narrowed; no mechanism. The `md_*` tables carry no row security (`git grep` of the migrations at HEAD: none) and `read_release` needs plain SELECT on them (`market_data_store.py:18-19`, `:694-740`), so the cap bounds what PD-0068 answer 1 names (economic write, seal, guarded load) plus the design's own read bound of the rooted tables and the archive, and nothing more. D3, E4, rule 4 and section 9 say so. 3.3 names the executor as an `md_*` reader and drops "so that no process reads"; its undecided `NOLOGIN` step names both roles and its extent. An R3 characterisation test records the limit; section 7 lists it for the HG4 package; the PM list gives the owner the choice. Not taken: a lease-checked read function in place of the executor's SELECT (a new mechanism that changes W05). **[Round 5: superseded. The owner asked for exactly that function (PD-0069); the narrowing above is replaced by 2.6 item 6, and section 15 maps the change.]** | 0 (D3); 1.2 rule 4; 2.6 item 2; 3.1 (E4 row); 3.2; 3.3; W05; 7; 8.1; E4; 9 |
| **TR4-M2** (MEDIUM), **R4C-L1** | Narrowed to what each increment can show, plus one call. R3 shows the file split, the lists and that the catalog audit sees the TEST-only part; R6's static test shows the real installer takes its lists only from those functions; the installer's Phase 2 and `--check` run the same audit on the REAL database. "R3's catalog test shows no function in any REAL install" and "audited at install" are corrected: the first read of a REAL catalog is at R8 step 1 | 1 items 1, 2; 1.2 (5.3 (e), 5.4, rule 7); 2.1; 4.2; 4.4; 7; 7.1 (R3, R6, R8); 8.1; E20; 9 |
| **R4C-L2** (LOW), **TR4-L1** (LOW) | Narrowed. "Before anything is created" holds for Phase 0 only. Rule 7 says which checks first meet the real roles (Phase 2), that a refusal there or at a first gated start comes after Phase 1 with no content yet held, and what the owner then does. R6's exit and the PM list say so; the 5.1 installer row no longer says every refusal writes nothing | 1.2 (5.1, rule 7); 7.1 (R6, R8); 8.1 |
| **R4C-L4** (LOW) | The `withdraw` cleartext limit of 5.1 is in the R6 exit and in the PM list, where the owner approves the plan | 7.1 (R6); 8.1 |
| **TR4-L2** (LOW) | The parameter-privilege check covers `ALTER SYSTEM` as well as `SET` (`sql-grant`, `functions-info`, `sql-altersystem`). The limit that stays is stated: the `SHOW` runs at each gated start, and a superuser's `ALTER SYSTEM` and reload is the trusted-operator boundary (whether a reload reaches a running session: not shown) | 1.2 (5.3 (a), 5.4, rule 7); E26; 9 |

**Mechanism added.** One: the installer's Phase 2 and `--check` call R3's catalog audit on the REAL database
(1.2 rule 5.3 (e)). It calls a function T03 needs anyway and adds no object. A narrower claim would not keep
the invariant: PD-0066 decision 7 ("never to agent sessions") fails if a defect in the REAL branch of the shared
installer code grants the executor a publisher function, and rule 4 lets an agent hold the executor credential.
R3's tests and R6's static test read lists and TEST catalogs, and no REAL database exists before R8, so without
this call nothing would ever read the catalog that matters, and the claim could only be withdrawn.

**Claims narrowed.** D3, E4, rule 4 and section 9: the bound covers the rooted tables and the archive, not the
`md_*` rows. "R3's catalog test shows no function in a REAL install" and "audited at install" become the list
tests plus Phase 2's first read at R8 step 1. "A wrong refusal comes before anything is created" holds for
Phase 0 only. "No process reads the `md_*` rows" after the loader's `NOLOGIN` is withdrawn. **[Round 5: the
first sentence of this paragraph, on the `md_*` rows, is superseded by PD-0069 (section 15).]**

## 15. Round 5 changes (2026-10-25)

The owner decided the `md_*` question (PD-0069): the executor's plain SELECT on the `md_*` tables is replaced
by lease-checked read functions, "so a lapse or withdrawal stops those reads too (All rights off, kept
literal)", and the loader's remaining reads go back to the owner as a question. The two re-reviews of round
4's second fix round left 3 MEDIUM and 4 LOW findings open (conformance R4R-M1, R4R-L1; technical TR4R-M1,
TR4R-M2, TR4R-L1 to TR4R-L3), where R4R-M1 and TR4R-M1 are one issue, which PD-0069 answers, and R4R-L1 and
TR4R-L2 are one issue; and nine observations. The owner's instruction stands: prefer narrowing claims and
conforming to the decisions over adding mechanisms. **I ran no SQL and no build, connected to no server, and did not run the
product tests: the change is design-only.** The file had 3126 lines (SHA-256 `d5c50b9b…7835`) at the start of
the round, 3440 after the round's first revision, and has 3579 after its second fix round (15.1). Where
this section differs from sections 10 to 14, this section and the body govern.

| Finding or point | Fix | Where |
|---|---|---|
| **PD-0069, point 1** (the executor's SELECT replaced; same bound; a lapse or withdrawal stops the reads) | Thirteen definer functions, one per `md_*` table; each call needs a live lease with `clock_timestamp() < complete_by` (`complete_by <= valid_until`), refuses and never filters | 2.6 item 6; 3.1 (E4 row); D3 row |
| **PD-0069, point 2** (the executor keeps no direct SELECT on any `md_*` table) | The executor's list has no privilege on any `md_*` table, column-level included; the audit compares it with exactly that; an R3 test | 1 item 5; 2.6 items 2, 6; 3.2; 4.4 role plan; 1.2 rule 5.3 (e) |
| **PD-0069, point 3** (gateway SQL built in R3; `read_release` called through it in R5) | R3 builds the functions and grants; R5 adds one Python keyword and no SQL, so "after R3 no increment adds gateway SQL" holds. R5 test T-m | 2.6 item 6; 4.2 build table; 4.4 (T-m); 7.1 (R3, R5) |
| **PD-0069, point 4** (exact grants; `read_release`'s contract and callers; which purposes read which rows; HEAD tests) | `EXECUTE` for the executor only; contract kept by a keyword-only `lease_checked` whose default is today's SQL; callers found by `git grep` (none in `src/`, 15 test files, 2 tripwires); no HEAD test needs to change; only `EXECUTE_CREATE` and `EXECUTE_REPRODUCE` leases, only the context's own release **[Round 6: the owner's, PD-0070 decision 2; no longer an engineer's choice]** | 2.6 item 6; W05; E28 |
| **PD-0069, point 5** (the loader narrowed; what it can still read goes to the owner, not an accepted limit) | Loader list: `INSERT` on thirteen tables, `SELECT` on `md_file` and `md_release`, `EXECUTE` on the candidate registry's put and get functions (HEAD and N2a lines cited), via R2's `count_rows` keyword; what it can still read is stated exactly, **the payload bytes included (15.1)**; owner question 12 with options; R2 does not start without an answer that names the reads it accepts **[Round 6: superseded. The owner answered, PD-0070 decision 1: the loader's login is off between loads; R2's gate is met; section 16]** | 3.3; 8.1 item 12 and PM list; 7.1 (R2); section 7; section 9 |
| **PD-0069, point 6** (`NOLOGIN` dropped for the executor, kept only in the loader question) | Dropped; it is option (b) of item 12 only **[Round 6: superseded. The loader's `NOLOGIN` is the owner's step after R8 step 2, not option (b); section 16]** | 3.3; 8.1 |
| **PD-0069, unchanged** (raw files, download tool, legacy CLI) | Still outside, still the owner procedure of PD-0066 decision 9; 3.3 lists them; the HG4 package takes the list | 3.3; 7.1 (R8) |
| **PD-0069, text corrected** | Every sentence that said the `md_*` rows are read with no lease: D3 row, 1.2 rule 4, 2.6 item 2, E4 row, 3.2, 3.3, W05, W12, sections 7, 8.1, 9, E4 | as listed; the accepted-limit entries of sections 7 and 9 are removed |
| **R4R-M1**, **TR4R-M1** (MEDIUM) | Answered by PD-0069 for the executor. For the loader: not listed as accepted, gated at R2 **[Round 6: answered by PD-0070 decision 1; section 16]** | as PD-0069, points 1 to 6 |
| **TR4R-M2** (MEDIUM) | The reviewer's first fix, by extending the existing comparison: the audit compares each runtime role's and `public`'s table and function privileges with that role's list (`has_table_privilege`, `has_any_column_privilege`, `has_function_privilege`); R3's parity test covers every role; loader and `public` cases join the R6 list; PM item (i) now says what is checked (15.1 adds `MAINTAIN` and the revoke of PUBLIC's `EXECUTE`) | 1.2 rule 5.3 (e), rule 7; 4.2; 7.1 (R3); 8.1 (i) |
| **R4R-L1**, **TR4R-L2** | The R8 paragraph says "every limit of section 7, as that section lists them" and adds 3.3's list; no list is repeated | 7.1 (R8 and the block after it) |
| **TR4R-L1** | The parameter-privilege check covers every LOGIN role other than the superuser and `public`, so "only the superuser" holds among roles that can connect | 1.2 rule 5.3 (a), rule 7; 8.1 (iv) |
| **TR4R-L3** | Rule 7 and R6's exit say what a Phase 1 failure leaves and the owner's options. The optional R3 test (REAL's file list in a TEST-kind database) is **not taken** | 1 item 1; 1.2 rule 7; 7; 7.1 (R6); 8.1 (iii); 9 |
| Observations, taken | Phase 2's result is an owner procedure (1.2 rule 7; 9); the audit is product code under `src/persistence/` that T03 and the installer import (5.3 (e); item 1); fact 18's quotation re-attributed; PM-list heading no longer says "no new owner decision"; "R6's catalog audit" reworded (4.2; 7.1); `require_auth=!password` named as a third option (5.1; 7.1 (R6); 8.1 (v)); the `ALTER ROLE ALL` row claim narrowed (5.3 (a)) | as listed |
| Observations, not taken | Refusing `pg_db_role_setting` rows with `setrole` 0 (it adds a refusal rule; the claim is narrowed instead) | 5.3 (a) |

**Mechanisms added.** One, and it is the owner's: the lease-checked `md_*` read functions (PD-0069), with the
choices that PD-0069 left to me listed as E28. Two Python keywords (`lease_checked` on `read_release`,
`count_rows` on `write_release`), each with a default that keeps today's behaviour. The audit's comparison is
the widening of an existing check to more roles; it adds no object.

**Claims narrowed or removed.** The `md_*` entry of section 7's accepted limits and of section 9's; "the
executor reads the `md_*` rows by plain SELECT with no lease" (D3, 1.2 rule 4, 2.6 item 2, 3.1, 3.3, W05,
W12); the characterisation test of that limit; the proposed `NOLOGIN` step on the executor; "audited at
install" for the loader's grants (now compared, not assumed); "only the superuser can write
`session_replication_role`" (now about every LOGIN role); "nothing is used until the refusal is resolved" (now
an owner procedure); the `ALTER ROLE ALL` row (a stated limit).

### 15.1 Second fix round (2026-10-25)

The reviews of the version above found one MEDIUM (technical TR5-M1) and six LOW findings (conformance
R5C-L1, R5C-L2; technical TR5-L1 to TR5-L4). Same instruction: narrow and conform before adding mechanisms;
PD-0069 exactly. **I ran no SQL and no build, connected to no
server, and did not run the product tests: design-only.** This fix round started at 3440 lines (SHA-256
`a300bdb7…8695`) and ends at 3579 lines.

| Finding | Checked against | Fix | Where |
|---|---|---|---|
| **TR5-M1** (MEDIUM) | Confirmed in the N2a handover: `np_payload.payload` stores the bytes (`:2-8`); `np_get_context` checks only the caller's role and returns `np_collect_context`, which aggregates the payloads (`:160`, `:246-249`); granted to the loader (`:286`), required by N2a's own install check (`store.py:143`), called at `:243`, `:263`, `:302`; `_loaded` re-validates from the returned bytes (`:193-207`) | The reviewer's narrower fix, on the claim and not on the registry. The loader's list now names the registry's put and get functions; 3.3, item 12, rule 4, section 9, D3, W04, E28, 4.1 and 2.1 list the payload bytes, prices included, among what the loader can read; "Not a price" and "no price" are gone. R2's test shows what the get function returns; the R6 audit cases include the registry functions. Narrowing the get function is option (c), not done unasked: it changes N2a's contract | 3.3; 8.1 item 12 and PM list; 1.2 rule 4, 5.3 (e), rule 7 cases; 2.1; 4.1; 7.1 (R2); W04; E28; D3; 9 |
| **R5C-L1** | 3.3 said "Nothing here stops the loader at a lapse", while sections 7 and 9 and item 12 let only an acceptance add reads, and R2's gate opened on any answer | Item 12 says every option leaves a read with no lease after a lapse, so the recorded answer must name the reads it accepts, and an answer that names none does not open R2's gate. R2's Needs, the dependency paragraph, section 7, section 9 and the R8 paragraph take that wording; 3.3 says "no `md_quote` row" holds under the proposed list and not under (d) **[Round 6: superseded. The owner's answer is recorded, PD-0070 decision 1, and R2's gate is met; section 16]** | 8.1 item 12; 3.3; 7.1 (R2, R8, dependency paragraph); 7; 9 |
| **R5C-L2** | `grep` of the STATUS.md working copy and of HEAD: neither holds "withdrawal by hand" or "pinned date"; the E25 bullet reads "... Wording corrected in round 4 (R3R-L2)." | Sentence deleted from the PM list and replaced by a note that nothing is left to correct; the same claim removed from the table above | 8.1 PM list; 15 |
| **TR5-L1** | `functions-info` lists `MAINTAIN` among the `has_table_privilege` types; `sql-lock`: with `MAINTAIN` "any lockmode is permitted"; `explicit-locking`: `ACCESS EXCLUSIVE` conflicts with every mode | `MAINTAIN` joins the `has_table_privilege` set (all eight table privileges are compared); R6 cases for the loader and the executor on the drain-mark table; R3's drift list | 1.2 rule 5.3 (e), rule 7; 7.1 (R3) |
| **TR5-L2** | `git grep` of the migrations at HEAD: twelve functions, no `GRANT` or `REVOKE`; `ddl-priv`: `EXECUTE` is PUBLIC's default | The shared installer code revokes PUBLIC's `EXECUTE` on every function of the schema, one statement after the last function-creating file and before the grants by name, as F2 does for its `gw_%` functions (`guarded_workspace_v1.sql:443-447`). The other fix, putting the twelve on every list, would give every role `EXECUTE` on them. That a trigger fires for a role with no `EXECUTE` on it: the manual is silent; HEAD's `test_c13` and R3's T03, with R2's loader write re-run, are the evidence **[16.1, TR6-L2: the loader write covers two of the eleven migration trigger functions]**. R6 case added | 1.2 rule 5.3 (e), rule 7; 4.2 build table; 7.1 (R3); E20 |
| **TR5-L3** | `0011:49-67`, `:58-61`, `:73-90`, `0016:74-77`, `0009:49`: the trigger has no `SECURITY DEFINER` and reads `md_release.release_id` and `append_xid` with the inserting role's privileges | 3.3 names the trigger's read in "what loading needs"; option (c) adds `SELECT` on `md_release.append_xid` **[Round 6: option (c) was not taken, so no list names columns]**; the foreign-key checks: not shown, and R2's loader test shows whether the list suffices | 3.3; 8.1 item 12; 9 |
| **TR5-L4** | 2.1 says only that the installer writes the kind row once; no text puts that write last in Phase 1 | The narrower fix: the sentence now says the tools refuse a database with no single kind row, that this does not make a partial install safe (it may hold one `REAL` row), and that not using it is the owner's procedure | 1.2 rule 7 |

**Mechanisms added.** None new. One statement of the shared installer code (TR5-L2, the revoke), one privilege
name in an existing comparison (TR5-L1), and tests (R2 on what the registry's get function returns; R3's
re-run of R2's loader write; R6 cases). **Not added:** a narrowing of the registry's get function (option (c)
of item 12, the owner's); writing the kind row last in Phase 1 (R6's plan may; no claim rests on it);
`NOLOGIN` on the loader after the qualification run (not offered; item 12 keeps the owner's options as they
were, apart from the registry) **[Round 6: superseded. The main session put it to the owner and the owner took it,
PD-0070 decision 1; section 16]**.

**Claims narrowed or removed.** "Not a price", "no price" and "nothing else" for the loader; "a partial
install is not mistaken for a usable one"; "for `public` none" (now true by the revoke, and said so); "refuses
on any difference from the list" (the list of privileges asked now includes `MAINTAIN`); "an acceptance, once
recorded, adds them" (now: the answer names the reads; **[Round 6: now section 7 holds PD-0070's words]**); "STATUS.md item 12 describes ..." (deleted).

## 16. Round 6 changes (2026-10-25)

The owner answered the two questions put after round 5 (PD-0070 decisions 1 and 2). The two re-reviews of round
5's second fix round left 1 MEDIUM (conformance R5R-M1 and technical TR5R-M1, one issue) and 3 LOW findings (R5R-L1,
TR5R-L1, TR5R-L2), and observations. The owner's instruction stands: prefer narrowing claims and conforming to the
decisions over adding mechanisms. **I ran no SQL and no build, connected to no server, and did not run the product
tests: the change is design-only.** The file had 3579 lines (SHA-256 `b5a7a866…ca0f`) at the start of the round and
had 3725 lines after the first pass and has 3826 after the second fix round (16.1). Where this section differs
from sections 10 to 15, this section and the body govern.

| Finding or point | Fix | Where |
|---|---|---|
| **PD-0070 decision 1**, procedure | The loader's login is off between loads: the owner sets the loader `NOLOGIN` right after its last use in R8 and `LOGIN` again only for a later load, each an owner act in the owner's own terminal. Item 12 is now an answered item citing PD-0070, as the PD-0068 items are | 3.3 (last bullet); 8.1 item 12; 1.2 rule 4; 7.1 (R8) |
| **PD-0070 decision 1**, where in R8 | **[Corrected in 16.1, R6C-M1: the first form put the last use at the end of step (2), which N2a's binding contradicts.]** Under N2a's binding the loader registers the context-bound candidates after the publish, so its last use is between the publish (4) and the real run (5), and the `NOLOGIN` step is R8 step (4a). If the real registry binds otherwise the step follows (2). R2's exit states which; R6's plan states the sequence, one window or two. A re-run that (3) or (4) calls for is a later load | 3.3 item 1; 7.1 (R8) |
| **PD-0070 decision 1**, limits | Worded as PD-0070 records them: new connections only, and an open session is not shown; the superuser and the owner role are not affected; each later load needs the owner's `LOGIN` step. In section 7, in section 9's accepted limits, in 3.3 and in item 12; each says the steps are an owner procedure that no tool enforces; the HG4 package takes section 7 and 3.3 | 3.3; 7; 8.1 item 12; 9; 7.1 (R8 block) |
| **PD-0070 decision 1**, window | During a load window the owner opens, the loader reads what its narrowed list allows, the payload bytes included; part of the procedure, not a limit beyond the owner's opening of the window. The list is unchanged (no option (c), no count read-back). The loader's writes need no lease either (R5C observation) | 3.3; 8.1 item 12 |
| **PD-0070 decision 1**, stale sentences | Every sentence that said no option stops the loader at a lapse, that the loader's reads are an open question, or that R2 waits for an answer is replaced or deleted; the section 15 and 15.1 rows carry a "Round 6" marker | D3 row; 1.2 rule 4; 2.1; 3.1 (E4 row); 3.3; 4.1; W04, W12; 7; 7.1 (R2, R3, R6, R8, dependency paragraph); 8.1; 9; 15, 15.1 |
| **PD-0070 decision 1**, a tool's report of the login state | The smallest thing, **E29**: the preflight output (5.3 (g)) prints each real role's `rolcanlogin`, which 5.3 (a) already reads. A print only: no refusal on any value (a refusal would have to know whether a load window is meant, and no tool can), nothing stored. It tells a reader whether a run covered the loader, because the LOGIN-keyed checks do not. A fake-facts case is added. Deleting it changes no other claim | 5.3 (g); rule 7 cases; 8.2 E29 |
| **PD-0070 decision 2** (E28) | Marked the owner's, not an engineer's choice: who may call the `md_*` read functions (`EXECUTE_CREATE` and `EXECUTE_REPRODUCE` leases, the context's own release, each call bounded by `complete_by`). Removed from the PM list. The details PD-0069 left to me stay mine, for the reviewer | 2.6 item 6; 8.2 E28; 8.1 PM list; 15 |
| **R5R-M1 = TR5R-M1** (MEDIUM) | The omitted owner step is the owner's answer. "Every option leaves a read after a lapse", "the loader as designed cannot load" and "an answer that names none is not an answer" are gone | 3.3; 8.1 item 12; 7; 7.1 (R2) |
| **R5R-L1** (LOW) | Item 12, rule 4 and R6 (the credential cell and the exit) say: outside an owner-opened load window nobody can log in as the loader; inside one the holder R6 names, an agent session included, reads what the list allows | 8.1 item 12; 1.2 rule 4; 7.1 (R6) |
| **TR5R-L1** (LOW) | The narrower fix: no list names columns now that option (c) is not taken, so every list is compared at table level, and a column-level grant is seen where a list gives the role no privilege on that table. A list naming columns would need `has_column_privilege` per column. PM item (i) no longer says column-level grants are compared in general | 1.2 rule 5.3 (e); 8.1 PM (i) |
| **TR5R-L2** (LOW) | Moot: option (c) is not taken. Its ordering text (the equality functions in R3, a second change to `write_release`, "may narrow it") is deleted | 3.3; 8.1 item 12; 7.1 (R2) |
| R5R observations | R2's Needs cell and "may narrow it": rewritten. W12 now names all the loader's reads. Writing the kind row last in Phase 1 (a technical option): **not taken**, it adds an installer ordering | 7.1 (R2); W12 |
| TR5R observations, taken | "No role-level setting exists" narrowed to real roles and the real database (`setrole` 0 rows are not refused); the trigger-firing evidence limited to definer functions, with R3's re-run of R2's loader write as the evidence for the migration triggers **[corrected in 16.1, TR6-L2: that run covers two of the eleven migration trigger functions]**; the revoke is `ALL ROUTINES IN SCHEMA` (`ALL FUNCTIONS` leaves procedures out; HEAD has none); R2's assertion no longer says "no other function" before R3's revoke, and a migration applied later needs the revoke re-run; 3.2 names the loader's `write_release` as the writer; T-m's recorder strips schema qualifiers, must see an `rw_md_*` call and has a control; `RW_MD_READ_REFUSED` takes a SQLSTATE outside class 23 and not `22003`, and R5 classifies it by message code | 3.1; E4; 1.2 rule 5.3 (e); 7.1 (R2, R6); 3.2; 4.4 (T-m); 2.6 item 6 |
| TR5R observation, "not shown" marks | **Cited** where the manual says it: a role holds the sum including PUBLIC (`sql-grant`); a table function in `FROM` has the table's attribute names (`queries-table-expressions`); a restrictive policy hides rows without an error (`ddl-rowsecurity`). **Kept "not shown":** that the `has_*_privilege` answer for a named role reports that sum (`functions-info` says only "does user have privilege"); the definer and `SETOF` parts together for a role with no table privilege; psycopg and `pinned_schema` on such a call | 1.2 rule 5.3 (e); 2.4; 2.6 items 2, 6; 9 |

**Mechanism added.** One, and droppable: the E29 print. Everything else narrows or states. The revoke's keyword
(`ALL ROUTINES`) replaces `ALL FUNCTIONS` in a statement the design already had.

**Claims narrowed or removed.** "Every option leaves some read with no lease after a lapse"; "the loader's reads are
an open question"; "nothing here stops the loader at a lapse"; "no role-level setting exists" (now: for a real role
or the real database); "column-level grants compared" (now: at table level, since no list names columns); R2's
"exactly its list" for functions before R3's revoke; the evidence for trigger firing (definer functions only).

### 16.1 Second fix round (2026-10-25)

The reviewers of the first round-6 revision left one MEDIUM and three LOW findings, all introduced by it. **I ran
no SQL and no build, connected to no server, and did not run the product tests: the change is design-only.** I
read the N2a handover's source and tests, which I did not run, and `git show` and `git grep` at HEAD, before each
fix. The file had 3725 lines at the start of this fix round and has 3826 now. Where this subsection differs
from the table above, this subsection and the body govern.

| Finding | Fix | Where |
|---|---|---|
| **R6C-M1** (MEDIUM) | Confirmed in the source: the registration's financial context is a foreign key to the snapshot (`synthetic_provenance_v1.sql:27`, `:244`), the guarded load refuses without a registration bound to the lease's context (`:258-261`; `synthetic_provenance_store.py:283`), and N2a, N2b and N3 register the bound bundle through the loader after `gw_publish`. The last use is no longer placed at the end of step (2). Under N2a's binding it falls between the publish (4) and the real run (5): the `NOLOGIN` step is a new step (4a), and step (2a) is gone. The hedge "if its design had the loader used later" is replaced by the cited source. Which sequence R8 uses, one window or two, is R6's plan's choice, after R2's exit says how the real registry binds; R2 gains a test line and an exit statement for it. The design names no tool that writes the registration after the publish: R4b's or R6's plan names it, and I add none. The HG4 package records the sequence followed. "It loads before any context exists" now says: its `md_*` rows | 3.3 (the loader bullet, items 1 and 2, closing paragraph); 1.2 rule 4; 7; 7.1 (R2, R6, R8 steps (2), (4a), (7), the observations paragraph); 8.1 item 12 and PM (vi); 9; row "where in R8" above |
| **R6C-L1 = TR6-L1** (LOW) | N2a's install function refuses a loader without `LOGIN` (`synthetic_provenance_store.py:112-116`), `np_caller` refuses a caller that cannot log in (`synthetic_provenance_v1.sql:62`), and the N2a runtime script creates its roles `LOGIN` (`runtime_n2a_reviewed_v3.py:123`), so no N2a test shows the refusal. Item 3 now says: if R2 keeps the checks, `NOLOGIN` at creation refuses at R8 step 1 and leaves a partial install; so either R2's check accepts a loader that cannot log in, or the installer would install the registry before the role is made `NOLOGIN` (an installer ordering and an installer act where PD-0070 names an owner act; I do not propose it). R2's exit states whether the check is kept; R6's plan chooses after that. The LOGIN-keyed checks of 5.3 do not cover a `NOLOGIN` loader (5.3 (g)) | 3.3 item 3; 7.1 (R2, R6); 8.1 PM (vi); 9 |
| **TR6-L2** (LOW) | Of the eleven migration trigger functions the loader's inserts fire two, `md_release_stamp` and `md_require_open_release`. R3's re-run is the evidence for those two only. The `ledger_event` insert triggers (and the `benchmark_selection` one if the create writes that row) are first fired without PUBLIC's `EXECUTE` by R5's `SYNTHETIC_TEST` create, and R5's exit states which. The mutation-refusal triggers and `account_guard_identity` fire on an update, delete or truncate, and `git grep` finds no `UPDATE` of `account`, `benchmark_selection` or `ledger_event` in `src/` at HEAD, so no run shows them without `EXECUTE`; I claim nothing about them. I did not check whether the `SYNTHETIC_TEST` create writes a `benchmark_selection` row | 1.2 rule 5.3 (e); 7.1 (R3, R5); 9; the TR5R row above |

**Mechanism added.** None. R2's test line and the exits of R2 and R5 state what a test shows, and the two-window
sequence adds owner acts and no tool. **Claims narrowed or removed.** "The loader's last use is the end of step
(2)" and "`NOLOGIN` at step (2a)"; "the loader is used nowhere later in R8"; "it loads before any context exists"
(now: its `md_*` rows); "R3's re-run is the evidence for the migration triggers" (now: two of the eleven); "R6 may
create the loader `LOGIN` or `NOLOGIN`" with no constraint (now: constrained by N2a's checks if R2 keeps them).
Not verified: whether the real publish writes a snapshot row that a registry foreign key can reference, and how the
real registry binds (R2's); whether an open loader session survives `NOLOGIN` (not shown, PD-0070).
