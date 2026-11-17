-- CP2c-2, migration 10: the market-data projection, part 2 (the observations a release holds). 0001-0009 frozen.
--
-- Every table is keyed by `release_id` (see 0009: a projection is the projection of a WHOLE release) and carries
-- the `file_sha256` of the file the row came from, with a composite foreign key to `md_release_file` so a row can
-- only name a file of its own release. `row_ordinal` is the position in the release's reading order: the in-memory
-- store sorts by (source precedence, source, file) and keeps insertion order among equals, so reading the rows
-- back ORDER BY row_ordinal rebuilds the exact same store.
--
-- KEYS: `listing_id` references `listing` (PD-0021 section 1). There is NO ticker, FIGI or vendor-id column on
-- any observation table. Currency pairs are keyed by their ISO codes.
--
-- NUMERIC BOUNDS (PD-0026 carried over). Every stored price, rate, volume, split ratio, dividend amount and
-- benchmark value is below 1E30 and has at most 24 decimals, by CHECK: the same bound the ledger enforces, so a
-- split ratio that F8-B copies into the ledger always fits it. ONE deliberate difference: a `precision_bound`
-- (Ruling 4.2) is a derived, exact binary fraction (half an ulp: 2^-53 has 53 decimal places), not a stored
-- quantity, so its scale limit is 100; the value limit is the same. NUMERIC keeps the scale it was given, so a
-- value read back is the value written, trailing zeros included.
--
-- LINEAGE. `lineage` is the full lineage record as plain JSON (strings, booleans and nulls only; no number can
-- lose precision in it). The queryable parts (source, file, dates, values, adjustment) are columns.

CREATE TABLE md_quote (
    release_id text NOT NULL,
    row_ordinal integer NOT NULL CHECK (row_ordinal >= 0),
    file_sha256 text NOT NULL,
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    independence_group text NOT NULL CHECK (btrim(independence_group) <> ''),
    listing_id uuid NOT NULL REFERENCES listing (listing_id),
    value_date date NOT NULL,
    price numeric NOT NULL,
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    volume numeric NULL,
    price_kind text NOT NULL CHECK (price_kind IN ('OFFICIAL_CLOSE', 'SOURCE_CLOSE')),
    recovered boolean NOT NULL,
    precision_bound numeric NOT NULL,
    observed_at timestamptz NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, row_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_quote_price_bounds CHECK (price > 0 AND price < 1E30 AND scale(price) <= 24),
    CONSTRAINT md_quote_volume_bounds CHECK (volume >= 0 AND volume < 1E30 AND scale(volume) <= 24),
    CONSTRAINT md_quote_precision_bound_bounds CHECK (
        precision_bound >= 0 AND precision_bound < 1E30 AND scale(precision_bound) <= 100),
    CONSTRAINT md_quote_recovered_has_zero_bound CHECK (NOT recovered OR precision_bound = 0),
    CONSTRAINT md_quote_unrecovered_has_a_bound CHECK (recovered OR precision_bound > 0)
);

CREATE INDEX md_quote_listing_date ON md_quote (release_id, listing_id, value_date);

CREATE TABLE md_fx_rate (
    release_id text NOT NULL,
    row_ordinal integer NOT NULL CHECK (row_ordinal >= 0),
    file_sha256 text NOT NULL,
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    independence_group text NOT NULL CHECK (btrim(independence_group) <> ''),
    base_currency text NOT NULL CHECK (base_currency ~ '^[A-Z]{3}$'),
    quote_currency text NOT NULL CHECK (quote_currency ~ '^[A-Z]{3}$'),
    value_date date NOT NULL,
    rate numeric NOT NULL,
    rate_basis text NOT NULL CHECK (btrim(rate_basis) <> ''),
    observed_at timestamptz NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, row_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_fx_rate_two_currencies CHECK (base_currency <> quote_currency),
    CONSTRAINT md_fx_rate_rate_bounds CHECK (rate > 0 AND rate < 1E30 AND scale(rate) <= 24)
);

CREATE INDEX md_fx_rate_pair_date ON md_fx_rate (release_id, base_currency, quote_currency, value_date);

CREATE TABLE md_corporate_action (
    release_id text NOT NULL,
    row_ordinal integer NOT NULL CHECK (row_ordinal >= 0),
    file_sha256 text NOT NULL,
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    independence_group text NOT NULL CHECK (btrim(independence_group) <> ''),
    listing_id uuid NOT NULL REFERENCES listing (listing_id),
    action_type text NOT NULL CHECK (action_type IN ('SPLIT', 'CASH_DIVIDEND', 'SYMBOL_CHANGE', 'UNSUPPORTED')),
    effective_date date NOT NULL,
    split_new numeric NULL,
    split_old numeric NULL,
    amount_per_unit numeric NULL,
    amount_currency text NULL CHECK (amount_currency ~ '^[A-Z]{3}$'),
    pay_date date NULL,
    record_date date NULL,
    detail jsonb NOT NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, row_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_corporate_action_split_bounds CHECK (
        split_new > 0 AND split_new < 1E30 AND scale(split_new) <= 24
        AND split_old > 0 AND split_old < 1E30 AND scale(split_old) <= 24),
    CONSTRAINT md_corporate_action_amount_bounds CHECK (
        amount_per_unit > 0 AND amount_per_unit < 1E30 AND scale(amount_per_unit) <= 24),
    CONSTRAINT md_corporate_action_shape CHECK (
        (action_type = 'SPLIT' AND split_new IS NOT NULL AND split_old IS NOT NULL
            AND amount_per_unit IS NULL AND amount_currency IS NULL AND pay_date IS NULL)
        OR (action_type = 'CASH_DIVIDEND' AND split_new IS NULL AND split_old IS NULL
            AND amount_per_unit IS NOT NULL AND amount_currency IS NOT NULL AND pay_date IS NOT NULL)
        OR (action_type IN ('SYMBOL_CHANGE', 'UNSUPPORTED') AND split_new IS NULL AND split_old IS NULL
            AND amount_per_unit IS NULL AND amount_currency IS NULL AND pay_date IS NULL))
);

COMMENT ON COLUMN md_corporate_action.effective_date IS
    'The EX-DATE for SPLIT and CASH_DIVIDEND (market-data Ruling 7.1); the effective date of a SYMBOL_CHANGE.';
COMMENT ON COLUMN md_corporate_action.detail IS
    'Attributes of the action that are not keys and not compared: paid currency, issuer FX rate (canonical decimal text), the old and new ticker of a SYMBOL_CHANGE, the label of an UNSUPPORTED action.';

CREATE INDEX md_corporate_action_listing_date ON md_corporate_action (release_id, listing_id, effective_date);

CREATE TABLE md_benchmark (
    release_id text NOT NULL,
    benchmark_ordinal integer NOT NULL CHECK (benchmark_ordinal >= 0),
    file_sha256 text NOT NULL,
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    independence_group text NOT NULL CHECK (btrim(independence_group) <> ''),
    benchmark_id text NOT NULL CHECK (btrim(benchmark_id) <> ''),
    provider text NOT NULL CHECK (btrim(provider) <> ''),
    value_kind text NOT NULL CHECK (value_kind IN ('LEVEL', 'RETURN')),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    license_status text NOT NULL CHECK (license_status IN ('INTERNAL_DEVELOPMENT_ONLY', 'SYNTHETIC_TEST', 'LICENSED')),
    display_permitted boolean NOT NULL,
    terms_ref text NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, benchmark_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_benchmark_display_needs_license CHECK (NOT display_permitted OR license_status = 'LICENSED')
);

CREATE TABLE md_benchmark_point (
    release_id text NOT NULL,
    benchmark_ordinal integer NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal >= 0),
    value_date date NOT NULL,
    value numeric NOT NULL,
    PRIMARY KEY (release_id, benchmark_ordinal, point_ordinal),
    FOREIGN KEY (release_id, benchmark_ordinal) REFERENCES md_benchmark (release_id, benchmark_ordinal),
    CONSTRAINT md_benchmark_point_value_bounds CHECK (abs(value) < 1E30 AND scale(value) <= 24)
);

-- Vendor-ADJUSTED rows are VERIFICATION-ONLY (market-data Ruling 2.5): they are stored so that Test V2 and the
-- label results can be reproduced, they are never a price, and the analytics port has no read of this table.
CREATE TABLE md_adjusted_quote (
    release_id text NOT NULL,
    row_ordinal integer NOT NULL CHECK (row_ordinal >= 0),
    file_sha256 text NOT NULL,
    listing_id uuid NOT NULL REFERENCES listing (listing_id),
    value_date date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    adjustment_status text NOT NULL CHECK (adjustment_status IN
        ('RAW', 'SPLIT_ADJUSTED', 'DIVIDEND_ADJUSTED', 'TOTAL_RETURN_ADJUSTED', 'UNDECLARED')),
    adjustment_method text NOT NULL CHECK (adjustment_method IN ('PROPORTIONAL', 'SUBTRACTIVE', 'UNKNOWN')),
    anchor text NULL CHECK (anchor IN ('LATEST', 'EARLIEST')),
    vintage timestamptz NOT NULL,
    precision_bound numeric NOT NULL,
    open_bound numeric NULL,
    high_bound numeric NULL,
    low_bound numeric NULL,
    source_time timestamptz NULL,
    delay_status text NOT NULL CHECK (delay_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'UNKNOWN')),
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, row_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_adjusted_quote_value_bounds CHECK (
        abs(open) < 1E30 AND scale(open) <= 24 AND abs(high) < 1E30 AND scale(high) <= 24
        AND abs(low) < 1E30 AND scale(low) <= 24 AND abs(close) < 1E30 AND scale(close) <= 24),
    CONSTRAINT md_adjusted_quote_precision_bound_bounds CHECK (
        precision_bound >= 0 AND precision_bound < 1E30 AND scale(precision_bound) <= 100
        AND (open_bound IS NULL OR (open_bound >= 0 AND open_bound < 1E30 AND scale(open_bound) <= 100))
        AND (high_bound IS NULL OR (high_bound >= 0 AND high_bound < 1E30 AND scale(high_bound) <= 100))
        AND (low_bound IS NULL OR (low_bound >= 0 AND low_bound < 1E30 AND scale(low_bound) <= 100))),
    CONSTRAINT md_adjusted_quote_field_bounds_together CHECK (
        (open_bound IS NULL AND high_bound IS NULL AND low_bound IS NULL)
        OR (open_bound IS NOT NULL AND high_bound IS NOT NULL AND low_bound IS NOT NULL))
);

CREATE INDEX md_adjusted_quote_listing_date ON md_adjusted_quote (release_id, listing_id, value_date);

-- Reference calendars (Ruling 5.3): part of the market-data version, never derived from a price or rate file.
CREATE TABLE md_calendar (
    release_id text NOT NULL,
    file_sha256 text NOT NULL,
    calendar_id text NOT NULL CHECK (btrim(calendar_id) <> ''),
    kind text NOT NULL CHECK (kind IN ('EXCHANGE_SESSIONS', 'ECB_FIXINGS')),
    applies_to text[] NOT NULL CHECK (cardinality(applies_to) > 0),
    timezone text NOT NULL CHECK (btrim(timezone) <> ''),
    covers_from date NOT NULL,
    covers_to date NOT NULL,
    dates date[] NOT NULL CHECK (cardinality(dates) > 0),
    actual_through date NOT NULL,
    evidence text NOT NULL,
    prepared_by text NOT NULL,
    prepared_on date NOT NULL,
    version_label text NOT NULL,
    default_close time NULL,
    early_closes jsonb NOT NULL,
    fixing_time time NULL,
    publication_time time NULL,
    lineage jsonb NOT NULL,
    PRIMARY KEY (release_id, calendar_id),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256),
    CONSTRAINT md_calendar_coverage CHECK (covers_from <= covers_to AND actual_through BETWEEN covers_from AND covers_to)
);

-- A series NOT admitted (Ruling 3.1 consequences, 1.3): it supplies no readings, its file stays in the release,
-- and the failure stays in lineage.
CREATE TABLE md_series_exclusion (
    release_id text NOT NULL,
    exclusion_ordinal integer NOT NULL CHECK (exclusion_ordinal >= 0),
    listing_id uuid NOT NULL REFERENCES listing (listing_id),
    file_sha256 text NOT NULL,
    test text NOT NULL CHECK (btrim(test) <> ''),
    reason text NOT NULL,
    PRIMARY KEY (release_id, exclusion_ordinal),
    FOREIGN KEY (release_id, file_sha256) REFERENCES md_release_file (release_id, file_sha256)
);
