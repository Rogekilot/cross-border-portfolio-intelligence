-- CP4b-3, migration 15 (PD-0039 D5; PRD FR-017, FR-018, UAT-03; tech plan 17.5): the user's primary-benchmark selection, per portfolio, dated and append-only.
-- 0001-0014 are frozen and untouched.
--
-- WHAT A SELECTION IS. A standing instruction of the user ("my primary benchmark is X"), not a historical fact. It is USER DATA: the system never creates a row on its own (FR-017: recommend, but require an
-- explicit selection; the recommendation itself is not built in CP4). Rows are immutable because results CITE them: a benchmark-dependent result pins the selection row and the knowledge version it used, so it
-- stays reproducible after the user changes their mind.
--
-- THREE RECORD TYPES (the CP1 shape: a correction is a reversal plus a replacement, never an edit).
--   SELECT   the user chooses benchmark `benchmark_id` (`origin`: USER_CHOSEN, or RECOMMENDATION_ACCEPTED when the user accepted a suggestion, still an explicit act);
--   CLEAR    the user removes the benchmark: the portfolio then has none (relative metrics are MISSING_BENCHMARK; nothing is guessed);
--   REVERSAL withdraws a SELECT or CLEAR recorded in error (`reverses_selection_id`); a REVERSAL cannot be reversed; a row is reversed at most once.
-- A replacement for a reversed row carries `corrects_selection_id` and must be appended in the SAME transaction as its reversal (so no committed state ever shows the withdrawal without its replacement).
--
-- ORDER AND RESOLUTION (risk/1.1 Ruling 5.6 (1.1)). The log is ordered by `selection_seq` ALONE: a pinned version is a sequence number, the records in force are those with selection_seq <= version, and the
-- selection is the LATEST of them; version 0, or a portfolio with no record, has none, and the engine never substitutes a benchmark. `selected_on` is the user's session date, passed in by the service (the
-- database never reads a clock for it): it is DATA the user sees ("you chose X on ..."), never an ordering input, so a back-dated selection is stored as it was made and does not slip behind a later one. The
-- one addition to the Quant's model is the REVERSAL: a record withdrawn as an error does not count, so the latest of the REMAINING records is in force (a withdrawn record is not "no selection"); a CLEAR is
-- itself a record, and the latest. Resolution is done in `domain.benchmark_selection.resolve_selection`; this file only stores.
--
-- SAME DISCIPLINE AS ledger_event (0003, 0004, 0006, 0008, 0011).
--   - Append-only: UPDATE, DELETE and TRUNCATE are refused for every role by trigger.
--   - ONE BEFORE INSERT trigger whose order is load-bearing: schema-rename guard; READ COMMITTED required; then the per-portfolio advisory lock (transaction scoped; the key includes the schema name, so two
--     schemas never contend); ONLY THEN the selection_seq is drawn, so within one portfolio selection_seq order equals commit order (and a pin is stable: nothing with a lower seq can commit after it was read);
--     then the cross-row checks under the lock. selection_seq has NO default for that reason, and a caller-supplied value is overwritten.
--   - `append_xid` (the full xid8 of the appending transaction) is stamped by the trigger: it ties a reversal to its replacement, and lets a read refuse a pin that cuts an atomic append (C1C-2 pattern).
--     `recorded_at` is audit metadata only, never an input to any computation.
--   - Name resolution is PINNED (the CP1B-1 / R2-3 pattern): every function gets `SET search_path = <schema>, pg_temp` (pg_temp explicitly last) and starts with the inline schema-rename guard, so a TEMP table
--     named benchmark_selection cannot shadow the real one for a role that holds the default TEMPORARY privilege, and a renamed schema fails closed. The pin block at the end must be repeated by any later
--     migration that replaces one of these functions.
--   - Bounds (text and date; there is no numeric column): benchmark_id and catalog_version are short ASCII identifiers by pattern, so no blank, no lookalike, no newline, no 10 MB string; selected_on lies
--     between 0001-01-01 and 9999-12-31 (PostgreSQL's 'infinity' and years beyond Python's range are refused, so every stored row can be read back).
-- The application role holds only SELECT and INSERT on this table and USAGE on its sequence (the grant spec is `APP_GRANTS` in tests/product/test_postgres_least_privilege.py).
-- Constraint names are load-bearing: persistence.benchmark_selection_store maps them to typed errors.
-- The benchmark id names a benchmark CATALOG entry; no catalog exists yet (the main session creates BENCHMARKS.json when risk/1.0 lands), so the database checks the FORMAT only, and `catalog_version` is NULL
-- until a catalog check exists.

CREATE SEQUENCE benchmark_selection_seq_seq AS bigint;

CREATE TABLE benchmark_selection (
    selection_seq bigint PRIMARY KEY,
    selection_id uuid NOT NULL,
    portfolio_id uuid NOT NULL REFERENCES portfolio (portfolio_id),
    record_type text NOT NULL,
    benchmark_id text NULL,
    catalog_version text NULL,
    origin text NULL,
    selected_on date NOT NULL,
    reverses_selection_id uuid NULL,
    corrects_selection_id uuid NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    append_xid xid8 NOT NULL,
    CONSTRAINT benchmark_selection_id_key UNIQUE (selection_id),
    -- a reversal or a replacement must name a row of the SAME portfolio
    CONSTRAINT benchmark_selection_target_key UNIQUE (selection_id, portfolio_id),
    CONSTRAINT benchmark_selection_reversal_target_fk FOREIGN KEY (reverses_selection_id, portfolio_id)
        REFERENCES benchmark_selection (selection_id, portfolio_id),
    CONSTRAINT benchmark_selection_correction_target_fk FOREIGN KEY (corrects_selection_id, portfolio_id)
        REFERENCES benchmark_selection (selection_id, portfolio_id),
    CONSTRAINT benchmark_selection_record_type_valid CHECK (record_type IN ('SELECT', 'CLEAR', 'REVERSAL')),
    CONSTRAINT benchmark_selection_origin_valid CHECK (origin IN ('USER_CHOSEN', 'RECOMMENDATION_ACCEPTED')),
    -- field presence per record type (mirrors domain.benchmark_selection.FIELD_RULES; a differential test feeds every combination to both)
    CONSTRAINT benchmark_selection_fields_select CHECK (record_type <> 'SELECT' OR (
        benchmark_id IS NOT NULL AND origin IS NOT NULL AND reverses_selection_id IS NULL)),
    CONSTRAINT benchmark_selection_fields_clear CHECK (record_type <> 'CLEAR' OR (
        benchmark_id IS NULL AND catalog_version IS NULL AND origin IS NULL AND reverses_selection_id IS NULL)),
    CONSTRAINT benchmark_selection_fields_reversal CHECK (record_type <> 'REVERSAL' OR (
        benchmark_id IS NULL AND catalog_version IS NULL AND origin IS NULL
        AND reverses_selection_id IS NOT NULL AND corrects_selection_id IS NULL)),
    -- value rules (mirror the domain patterns; PostgreSQL's '$' matches only at the end of the string, so a trailing newline is refused)
    CONSTRAINT benchmark_selection_benchmark_id_format CHECK (benchmark_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$'),
    CONSTRAINT benchmark_selection_catalog_version_format CHECK (catalog_version ~ '^[A-Za-z0-9][A-Za-z0-9._:+-]{0,63}$'),
    CONSTRAINT benchmark_selection_selected_on_bounds CHECK (selected_on BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
    CONSTRAINT benchmark_selection_no_self_reversal CHECK (reverses_selection_id <> selection_id),
    CONSTRAINT benchmark_selection_no_self_correction CHECK (corrects_selection_id <> selection_id)
);

ALTER SEQUENCE benchmark_selection_seq_seq OWNED BY benchmark_selection.selection_seq;

-- A row may be reversed at most once, and corrected (replaced) at most once.
CREATE UNIQUE INDEX benchmark_selection_reversed_once ON benchmark_selection (reverses_selection_id)
    WHERE reverses_selection_id IS NOT NULL;
CREATE UNIQUE INDEX benchmark_selection_corrected_once ON benchmark_selection (corrects_selection_id)
    WHERE corrects_selection_id IS NOT NULL;

-- the per-portfolio read and the pin-boundary probes (adjacent rows, with their transaction id)
CREATE INDEX benchmark_selection_portfolio_seq ON benchmark_selection (portfolio_id, selection_seq) INCLUDE (append_xid);

COMMENT ON TABLE benchmark_selection IS
    'The user''s primary-benchmark selection per portfolio: append-only, dated (selected_on), ordered (selection_seq), corrected by reversal plus replacement. User data; the system never writes a row on its own.';
COMMENT ON COLUMN benchmark_selection.selected_on IS
    'The date of the choice, passed in by the service (never read from a clock here). Data the user sees; NOT an ordering input: the log is ordered by selection_seq alone (risk/1.1 Ruling 5.6 (1.1)).';
COMMENT ON COLUMN benchmark_selection.recorded_at IS
    'Audit metadata only. Set by the insert trigger (now()); never an input to any computation.';
COMMENT ON COLUMN benchmark_selection.append_xid IS
    'Full xid8 of the appending transaction (trigger-set): ties a reversal to its replacement and lets a read refuse a pin that cuts an atomic append.';
COMMENT ON COLUMN benchmark_selection.catalog_version IS
    'The benchmark catalog version the id was checked against; NULL until a catalog exists (the id is checked for format only).';

CREATE FUNCTION benchmark_selection_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'benchmark-selection trigger functions are pinned to a schema other than the one holding the table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_search_path_pin_stale';
    END IF;

    RAISE EXCEPTION 'benchmark_selection is append-only: % is not permitted', TG_OP
        USING ERRCODE = '23001', CONSTRAINT = 'benchmark_selection_append_only';
END;
$$;

CREATE TRIGGER benchmark_selection_no_update_delete
    BEFORE UPDATE OR DELETE ON benchmark_selection
    FOR EACH ROW EXECUTE FUNCTION benchmark_selection_reject_mutation();

CREATE TRIGGER benchmark_selection_no_truncate
    BEFORE TRUNCATE ON benchmark_selection
    FOR EACH STATEMENT EXECUTE FUNCTION benchmark_selection_reject_mutation();

CREATE FUNCTION benchmark_selection_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target_type text;
    reversal_xid xid8;
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'benchmark-selection trigger functions are pinned to a schema other than the one holding the table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_search_path_pin_stale';
    END IF;

    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'benchmark-selection appends require READ COMMITTED isolation'
            USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_requires_read_committed';
    END IF;

    NEW.recorded_at := now();
    NEW.append_xid := pg_current_xact_id();

    -- the per-portfolio lock, THEN the sequence (so seq order is commit order within a portfolio), THEN the checks
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'finweb.benchmark_selection.portfolio:' || TG_TABLE_SCHEMA || ':' || NEW.portfolio_id::text, 0));

    NEW.selection_seq := nextval('benchmark_selection_seq_seq');

    -- an idempotent resubmission (the same selection_id): the INSERT's ON CONFLICT DO NOTHING absorbs it; no other rule applies to a row that will not be written
    IF EXISTS (SELECT 1 FROM benchmark_selection WHERE selection_id = NEW.selection_id) THEN
        RETURN NEW;
    END IF;

    IF NEW.record_type = 'REVERSAL' THEN
        SELECT record_type INTO target_type FROM benchmark_selection WHERE selection_id = NEW.reverses_selection_id;
        IF target_type = 'REVERSAL' THEN
            RAISE EXCEPTION 'a REVERSAL cannot be reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_reversal_of_reversal';
        END IF;
    END IF;

    IF NEW.corrects_selection_id IS NOT NULL THEN
        SELECT r.append_xid INTO reversal_xid FROM benchmark_selection r
            WHERE r.record_type = 'REVERSAL' AND r.reverses_selection_id = NEW.corrects_selection_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'corrects_selection_id must name a selection that has been reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_corrects_reversed';
        END IF;
        -- atomicity: the reversal must have been appended by THIS transaction (exact comparison of full ids)
        IF reversal_xid IS DISTINCT FROM pg_current_xact_id() THEN
            RAISE EXCEPTION 'a replacement must be appended in the same transaction as its reversal'
                USING ERRCODE = '23514', CONSTRAINT = 'benchmark_selection_correction_same_transaction';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER benchmark_selection_before_insert
    BEFORE INSERT ON benchmark_selection
    FOR EACH ROW EXECUTE FUNCTION benchmark_selection_before_insert();

-- ---- pin every function of this migration (see 0004, 0008, 0011) --------------------------------------------------------------------------------------------

DO $$
DECLARE
    fn text;
BEGIN
    FOREACH fn IN ARRAY ARRAY[
        'benchmark_selection_reject_mutation()',
        'benchmark_selection_before_insert()'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SET search_path = %I, pg_temp',
                       current_schema(), fn, current_schema());
    END LOOP;
END;
$$;
