-- CP2c-2, migration 11: the market-data projection, part 3 (the rules). 0001-0010 are frozen.
--
-- 1. APPEND-ONLY. Every md_* table refuses UPDATE, DELETE and TRUNCATE, for every role (the trigger fires for the
--    owner too; a role that can ALTER the table can still disable it, which is why the application role holds
--    only SELECT: see the grant spec in tech plan 15.17).
-- 2. SEALED RELEASES. md_release.append_xid is stamped by the insert trigger with the full id of the appending
--    transaction. A row of any child table (files, quotes, rates, actions, benchmarks, adjusted rows, calendars,
--    exclusions) is accepted ONLY from that same transaction: once it commits, nothing can be added to the
--    release. Same pattern and same exact comparison as the ledger's correction rule (0008): `pg_current_xact_id()`
--    is the top-level transaction's id, equal inside savepoints.
-- 3. NAME RESOLUTION IS PINNED (the CP1B-1 / R2-3 pattern, unchanged). PostgreSQL searches the session's pg_temp
--    schema FIRST for relations unless pg_temp is named in search_path, and a role holding the default database
--    TEMPORARY privilege can create a TEMP table named `md_release`. Each function therefore gets
--    `SET search_path = <schema>, pg_temp` (pg_temp explicitly last), and EVERY function starts with the inline
--    schema-rename guard: it compares its pinned (first) search_path entry with the schema of the table that fired
--    it and FAILS CLOSED before doing anything else if they differ (a renamed schema leaves the pin on the old
--    name). This does NOT rely on revoking TEMPORARY. The pin block is at the end of this file and must
--    be repeated by any later migration that replaces one of these functions.
-- Constraint names are load-bearing: persistence.market_data_store maps them to typed errors.

CREATE FUNCTION md_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'market-data trigger functions are pinned to a schema other than the one holding the table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'md_search_path_pin_stale';
    END IF;

    RAISE EXCEPTION '% is append-only: % is not permitted', TG_TABLE_NAME, TG_OP
        USING ERRCODE = '23001', CONSTRAINT = 'md_append_only';
END;
$$;

CREATE FUNCTION md_release_stamp() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'market-data trigger functions are pinned to a schema other than the one holding the table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'md_search_path_pin_stale';
    END IF;

    NEW.append_xid := pg_current_xact_id();
    RETURN NEW;
END;
$$;

CREATE FUNCTION md_require_open_release() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'market-data trigger functions are pinned to a schema other than the one holding the table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'md_search_path_pin_stale';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM md_release r
        WHERE r.release_id = NEW.release_id AND r.append_xid = pg_current_xact_id()
    ) THEN
        RAISE EXCEPTION 'market-data release % accepts rows only from the transaction that created it (it is sealed, or unknown)', NEW.release_id
            USING ERRCODE = '23514', CONSTRAINT = 'md_release_sealed';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER md_release_stamp_xid
    BEFORE INSERT ON md_release
    FOR EACH ROW EXECUTE FUNCTION md_release_stamp();

CREATE TRIGGER md_release_file_open_release BEFORE INSERT ON md_release_file
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_quote_open_release BEFORE INSERT ON md_quote
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_fx_rate_open_release BEFORE INSERT ON md_fx_rate
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_corporate_action_open_release BEFORE INSERT ON md_corporate_action
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_benchmark_open_release BEFORE INSERT ON md_benchmark
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_benchmark_point_open_release BEFORE INSERT ON md_benchmark_point
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_adjusted_quote_open_release BEFORE INSERT ON md_adjusted_quote
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_calendar_open_release BEFORE INSERT ON md_calendar
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_series_exclusion_open_release BEFORE INSERT ON md_series_exclusion
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();

CREATE TRIGGER md_file_no_update_delete BEFORE UPDATE OR DELETE ON md_file
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_file_no_truncate BEFORE TRUNCATE ON md_file
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_release_no_update_delete BEFORE UPDATE OR DELETE ON md_release
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_release_no_truncate BEFORE TRUNCATE ON md_release
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_release_file_no_update_delete BEFORE UPDATE OR DELETE ON md_release_file
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_release_file_no_truncate BEFORE TRUNCATE ON md_release_file
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_quote_no_update_delete BEFORE UPDATE OR DELETE ON md_quote
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_quote_no_truncate BEFORE TRUNCATE ON md_quote
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_fx_rate_no_update_delete BEFORE UPDATE OR DELETE ON md_fx_rate
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_fx_rate_no_truncate BEFORE TRUNCATE ON md_fx_rate
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_corporate_action_no_update_delete BEFORE UPDATE OR DELETE ON md_corporate_action
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_corporate_action_no_truncate BEFORE TRUNCATE ON md_corporate_action
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_benchmark_no_update_delete BEFORE UPDATE OR DELETE ON md_benchmark
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_benchmark_no_truncate BEFORE TRUNCATE ON md_benchmark
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_benchmark_point_no_update_delete BEFORE UPDATE OR DELETE ON md_benchmark_point
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_benchmark_point_no_truncate BEFORE TRUNCATE ON md_benchmark_point
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_adjusted_quote_no_update_delete BEFORE UPDATE OR DELETE ON md_adjusted_quote
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_adjusted_quote_no_truncate BEFORE TRUNCATE ON md_adjusted_quote
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_calendar_no_update_delete BEFORE UPDATE OR DELETE ON md_calendar
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_calendar_no_truncate BEFORE TRUNCATE ON md_calendar
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_series_exclusion_no_update_delete BEFORE UPDATE OR DELETE ON md_series_exclusion
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_series_exclusion_no_truncate BEFORE TRUNCATE ON md_series_exclusion
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();

-- ---- pin every function in the schema (see 0004, 0006, 0008) ---------------------------------------------
-- (Must run after every CREATE [OR REPLACE] FUNCTION in this file: replacing a function resets its SET list.
-- The pins of the ledger functions, which 0008 set, are untouched: this block names only the functions above.)

DO $$
DECLARE
    fn text;
BEGIN
    FOREACH fn IN ARRAY ARRAY[
        'md_reject_mutation()',
        'md_release_stamp()',
        'md_require_open_release()'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SET search_path = %I, pg_temp',
                       current_schema(), fn, current_schema());
    END LOOP;
END;
$$;
