# HG4 condition 2: the root's generation on the real screen (implementation note, 2026-11-17)

Implements `designs/FEATURE_DESIGN.md`, "HG4 condition 2: the root's generation on the real screen" (PD-0089 condition 2, TR8SR M-1).

- Read contract `finweb.cp7.real_scoped_read/1` -> `/2`: required integer `created_under_generation` >= 1 (`web_api/real_scoped_contract.py::read_payload`).
  The route (`web_api/real_mode_routes.py::committed`) fills it from `json.loads(archive.envelope)["generation"]`, the sealed envelope the read already
  loads. A missing, non-integer or < 1 value is a `REAL_UNAVAILABLE` refusal, never a guess. No second read, no second admission.
- No SQL, grant, migration, list-schema (`/2`) or create-result change. The read path runs as the executor role, whose function list
  (`persistence/real_roles.py::EXECUTOR_FUNCTIONS`) already contains `rw_archive(uuid,uuid)`.
- Web: `real-mode.ts` parser (exact key set; `Number.isSafeInteger`, >= 1; `created_under_generation` optional on `RealRoot` because a create result has none),
  `RootEntries` (note once above a non-empty list; "Context now at generation N"), `RootDetail` ("Created under generation N" after the ledger pin, read results only),
  `real-mode-i18n.ts` (retired key `generation`; added `contextGenerationNow`, `createdUnderGeneration`, `generationNote`, both locales).
- Evidence tool: `real_tools/r8_http_check.py::view` also drops `created_under_generation`, because `replay_equals_read` compares a create replay with a read
  and only the read carries the field. Its whole-source pin in `test_real_preflight_static.HttpToolTests.PIN` moves `677d20c8fda752f7fa89` -> `75a9b40922300de3b3dd`.
  The tool reads the schema through `contract.READ_SCHEMA`, so the version bump needs no other change there.
- The create route's `Created` outcome still builds a create result, which has no `created_under_generation` (the design leaves that schema unchanged).

## TR-G2 L-1 follow-up: one PostgreSQL test for the two numbers

`tests/product/test_postgres_real_mode.py::AppOverTheRealServiceTests::test_the_list_generation_is_the_contexts_current_one_and_the_read_names_the_creation_generation_HG4_condition_2`
(skips unless `FINWEB_PG_INTEGRATION`; disposable `finweb_it_rw_*` database, `SYNTHETIC_TEST`). A root is created at generation 1 through the route; the context is renewed
twice through the product tool (head 3). The list entry's `generation` is 3 and the read's `created_under_generation` is 1, both from the real service and installed SQL
(`rw_list_roots`, the admission, the stored sealed envelope); the envelope's own `generation` is also checked directly. Head 3 (not 2) so the list value is neither the
creation generation nor "head minus one". Verified by two in-memory mutants (not in the tree): `list_entry` given the artifact's generation, and `read_payload` given the
head; each fails the test. No product code changed.
