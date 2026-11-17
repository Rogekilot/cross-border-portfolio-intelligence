-- CP2c-2, migration 9: the market-data projection, part 1 (files and releases). 0001-0008 are frozen.
--
-- WHAT THIS IS (tech plan 15.5, 15.17). The market-data store is an APPEND-ONLY, REBUILDABLE PROJECTION of a
-- market-data release. The files are the evidence of record (immutable, SHA-256 hashed, kept outside the
-- database); these tables hold what the adapters and the file-level checks made of them, so a lookup does not
-- re-parse files. Nothing here is a source of truth: dropping the schema and re-projecting the same release from
-- the same files gives the same `projection_digest` (that comparison is the rebuild check).
--
-- KEYS. `listing_id` (PD-0021 section 1) is the only identity key on any observation table (next migration).
-- A ticker or FIGI is never a column of an observation table: the one place a ticker appears is the `detail`
-- JSON of a SYMBOL_CHANGE observation, which is the fact being recorded, not a key.
--
-- LINEAGE. `md_file` registers every file by `file_sha256` (the exact bytes' identity) with its manifest.
-- A release names its files (`md_release_file`) and the convention-set id it was cut under. Every observation
-- row (next migration) carries `release_id`, `file_sha256` and a full lineage record.
--
-- A RELEASE IS A SEALED UNIT. A projection depends on the WHOLE release (the calendars, the other files'
-- provenance verdicts, the V0 admissions), so observation rows belong to a release, not to a file. The release
-- row stamps `append_xid` (the full id of the appending transaction, as the ledger does since 0008) and every
-- child row may be inserted ONLY by that same transaction (migration 0011): once the transaction commits, nobody
-- can add a row to the release, so "the same release gives the same output" cannot be broken by a later insert.
-- All tables refuse UPDATE, DELETE and TRUNCATE (migration 0011). Supersession is a NEW release, never an edit.
--
-- Names are unqualified; they land in the first schema on the connection's search_path.

CREATE TABLE md_file (
    file_sha256 text PRIMARY KEY CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    data_kind text NOT NULL CHECK (data_kind IN
        ('QUOTE', 'FX', 'CORPORATE_ACTION', 'BENCHMARK', 'IDENTITY', 'CALENDAR', 'RESOLUTION_RECORD')),
    usage_scope text NOT NULL CHECK (usage_scope IN
        ('INTERNAL_DEVELOPMENT_ONLY', 'SYNTHETIC_TEST', 'LICENSED_DISPLAY')),
    retrieval_time timestamptz NOT NULL,
    declared_adjustment text NOT NULL CHECK (btrim(declared_adjustment) <> ''),
    market text NULL,
    manifest jsonb NOT NULL
);

COMMENT ON TABLE md_file IS
    'One row per registered source file, keyed by the SHA-256 of its exact bytes. The manifest column is the file manifest as written by the download tool. Append-only.';

CREATE TABLE md_release (
    release_id text PRIMARY KEY CHECK (release_id ~ '^[0-9a-f]{64}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    convention_set_id text NOT NULL CHECK (btrim(convention_set_id) <> ''),
    release_content jsonb NOT NULL,
    contains_synthetic boolean NOT NULL,
    projection_digest text NOT NULL CHECK (projection_digest ~ '^[0-9a-f]{64}$'),
    append_xid xid8 NOT NULL
);

COMMENT ON TABLE md_release IS
    'A market-data release (the pin): release_content is the canonical release JSON whose SHA-256 is release_id; convention_set_id is the convention set it was cut under; projection_digest is the SHA-256 of the canonical projection of every row below, recomputed on read and on rebuild. append_xid is set by the insert trigger; child rows are accepted only from the same transaction.';

CREATE TABLE md_release_file (
    release_id text NOT NULL REFERENCES md_release (release_id),
    file_sha256 text NOT NULL REFERENCES md_file (file_sha256),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    has_fx_window boolean NOT NULL,
    fx_window_start date NULL,
    fx_window_end date NULL,
    PRIMARY KEY (release_id, file_sha256),
    UNIQUE (release_id, ordinal),
    CONSTRAINT md_release_file_window_only_for_fx CHECK (
        has_fx_window OR (fx_window_start IS NULL AND fx_window_end IS NULL))
);

COMMENT ON TABLE md_release_file IS
    'The files of a release, in the release''s order. For an FX file the coverage window of market-data/1.3 Ruling 1.1a item 5, as computed at ingest from the manifest request and retrieval time (start NULL: a full-history file; end NULL: could not be determined).';
