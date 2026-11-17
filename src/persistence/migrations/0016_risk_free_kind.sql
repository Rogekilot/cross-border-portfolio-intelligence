-- CP4b-2, migration 16 (PD-0039 D2; `risk/1.0` section 4; tech plan 17.4.2, 17.15): the RISK_FREE market-data kind, the market-data projection part 4. 0001-0015 are frozen and untouched.
--
-- WHAT THIS ADDS. A risk-free rate series in one currency is a market-data kind of its own (not a benchmark: a rate is not a reference portfolio, and the two must not be confusable). It is loaded exactly as every other
-- kind: the FILES are the evidence of record, these tables hold what the adapters made of them, a release is a sealed unit, every table is append-only, and the application role holds SELECT only (the grant spec is `MD_TABLES`
-- in tests/product/test_postgres_least_privilege.py and in `persistence.market_data_store`). Nothing is a source of truth: dropping the schema and re-projecting the same release gives the same `projection_digest`.
--
-- 1. `md_file.data_kind` admits 'RISK_FREE', and `md_calendar.kind` admits 'RATE_PUBLICATIONS' (risk/1.0 Ruling 4.5: the publication calendar of a risk-free series). Both are column CHECKs written without a name in 0009 and
--    0010; PostgreSQL named them `md_file_data_kind_check` and `md_calendar_kind_check` (read from the catalog, not assumed). They are dropped and added again with the wider list; every existing row satisfies the
--    wider list, so nothing is re-scanned in a way that can fail.
-- 2. `md_risk_free` (one row per series, the risk/1.0 Ruling 4.6 checklist as columns) and `md_risk_free_point` (one row per published quote). Bounds as elsewhere: a rate is below 1E30 with at most 24 decimals (the same
--    bound the ledger and `md_benchmark_point` enforce), a term is a positive number of days, `decimals_published` is 0 to 12, and the enumerated columns are CHECKed against the contract's enums.
-- 3. The same two triggers as every md_* table, reusing the functions of 0011 (so no function is replaced and no pin is reset): UPDATE, DELETE and TRUNCATE are refused for every role (`md_append_only`), and a row is accepted
--    only from the transaction that created its release (`md_release_sealed`). Both functions start with the schema-rename guard and are pinned (0011).
--
-- COMPATIBILITY. The projection digest of every release written before this migration is byte-identical: the new tables are empty for them and `persistence.market_data_store.projection_obj` adds a "risk_free" key only
-- when a release holds a risk-free series. A test asserts it.

ALTER TABLE md_file DROP CONSTRAINT md_file_data_kind_check;
ALTER TABLE md_file ADD CONSTRAINT md_file_data_kind_check CHECK (data_kind IN
    ('QUOTE', 'FX', 'CORPORATE_ACTION', 'BENCHMARK', 'RISK_FREE', 'IDENTITY', 'CALENDAR', 'RESOLUTION_RECORD'));

ALTER TABLE md_calendar DROP CONSTRAINT md_calendar_kind_check;
ALTER TABLE md_calendar ADD CONSTRAINT md_calendar_kind_check CHECK (kind IN ('EXCHANGE_SESSIONS', 'ECB_FIXINGS', 'RATE_PUBLICATIONS'));

CREATE TABLE md_risk_free (
    release_id text NOT NULL,
    risk_free_ordinal integer NOT NULL CHECK (risk_free_ordinal >= 0),
    file_sha256 text NOT NULL,
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    independence_group text NOT NULL CHECK (btrim(independence_group) <> ''),
    series_id text NOT NULL CHECK (btrim(series_id) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    provider text NOT NULL CHECK (btrim(provider) <> ''),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    instrument text NOT NULL CHECK (btrim(instrument) <> ''),
    tenor_weeks integer NOT NULL CHECK (tenor_weeks > 0),
    quote_type text NOT NULL CHECK (quote_type IN ('SIMPLE_YIELD', 'BANK_DISCOUNT')),
    day_count_basis integer NOT NULL CHECK (day_count_basis IN (360, 365)),
    unit text NOT NULL CHECK (unit IN ('PERCENT', 'DECIMAL')),
    decimals_published integer NOT NULL CHECK (decimals_published BETWEEN 0 AND 12),
    date_semantics text NOT NULL CHECK (btrim(date_semantics) <> ''),
    calendar_id text NOT NULL CHECK (btrim(calendar_id) <> ''),
    revision_policy text NOT NULL CHECK (revision_policy IN ('NOT_REVISED', 'REVISED', 'UNKNOWN')),
    license_status text NOT NULL CHECK (license_status IN ('INTERNAL_DEVELOPMENT_ONLY', 'SYNTHETIC_TEST', 'LICENSED')),
    display_permitted boolean NOT NULL,
    terms_ref text NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, risk_free_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_risk_free_display_needs_license CHECK (NOT display_permitted OR license_status = 'LICENSED'),
    CONSTRAINT md_risk_free_discount_is_act360 CHECK (quote_type <> 'BANK_DISCOUNT' OR day_count_basis = 360)
);

CREATE TABLE md_risk_free_point (
    release_id text NOT NULL,
    risk_free_ordinal integer NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal >= 0),
    value_date date NOT NULL,
    rate numeric NOT NULL,
    term_days integer NULL CHECK (term_days > 0),
    PRIMARY KEY (release_id, risk_free_ordinal, point_ordinal),
    FOREIGN KEY (release_id, risk_free_ordinal) REFERENCES md_risk_free (release_id, risk_free_ordinal),
    CONSTRAINT md_risk_free_point_value_bounds CHECK (abs(rate) < 1E30 AND scale(rate) <= 24),
    CONSTRAINT md_risk_free_point_date_bounds CHECK (value_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31')
);

COMMENT ON TABLE md_risk_free IS
    'One risk-free rate series per row (risk/1.0 Ruling 4.6 checklist as columns). Append-only; part of a sealed release.';
COMMENT ON TABLE md_risk_free_point IS
    'The published quotes of a risk-free series: the date each is FOR, the rate as published (unit and quote type are the series'') and, for a BANK_DISCOUNT quote, its term in days.';

CREATE TRIGGER md_risk_free_open_release BEFORE INSERT ON md_risk_free
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();
CREATE TRIGGER md_risk_free_point_open_release BEFORE INSERT ON md_risk_free_point
    FOR EACH ROW EXECUTE FUNCTION md_require_open_release();

CREATE TRIGGER md_risk_free_no_update_delete BEFORE UPDATE OR DELETE ON md_risk_free
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_risk_free_no_truncate BEFORE TRUNCATE ON md_risk_free
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_risk_free_point_no_update_delete BEFORE UPDATE OR DELETE ON md_risk_free_point
    FOR EACH ROW EXECUTE FUNCTION md_reject_mutation();
CREATE TRIGGER md_risk_free_point_no_truncate BEFORE TRUNCATE ON md_risk_free_point
    FOR EACH STATEMENT EXECUTE FUNCTION md_reject_mutation();
