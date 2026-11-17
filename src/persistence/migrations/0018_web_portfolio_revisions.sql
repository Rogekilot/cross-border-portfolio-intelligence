-- CP7-B: immutable workspace revisions. Initial CP7-B saved sandboxes are never rewritten.
CREATE SEQUENCE web_portfolio_revision_seq_seq AS bigint;
CREATE TABLE web_portfolio_revision (
    revision_seq bigint PRIMARY KEY,
    revision_id uuid NOT NULL UNIQUE,
    portfolio_id uuid NOT NULL REFERENCES web_saved_sandbox (portfolio_id),
    parent_revision_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    operation text NOT NULL CHECK (operation IN ('APPEND','CORRECT','REVERSE','ADD_ACCOUNT','PREFERENCES')),
    command_sha256 text NOT NULL CHECK (command_sha256 ~ '^[0-9a-f]{64}$'),
    as_of date NOT NULL CHECK (as_of BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
    ledger_version bigint NOT NULL CHECK (ledger_version > 0),
    selection_version bigint NOT NULL CHECK (selection_version >= 0),
    policies_json text NOT NULL CHECK (octet_length(policies_json) <= 100000),
    policies_state text NOT NULL CHECK (policies_state IN ('NOT_STATED','NONE','ACTIVE')),
    snapshot_json text NOT NULL CHECK (octet_length(snapshot_json) <= 4000000),
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL,
    UNIQUE (portfolio_id, operation_id)
);
ALTER SEQUENCE web_portfolio_revision_seq_seq OWNED BY web_portfolio_revision.revision_seq;
CREATE INDEX web_portfolio_revision_portfolio ON web_portfolio_revision(portfolio_id,revision_seq);

CREATE FUNCTION web_revision_before_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1)) IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'workspace revision schema pin is stale' USING ERRCODE='23514';
    END IF;
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'workspace revisions require READ COMMITTED' USING ERRCODE='23514';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('finweb.web_revision.portfolio:' || TG_TABLE_SCHEMA || ':' || NEW.portfolio_id::text,0));
    NEW.revision_seq := nextval('web_portfolio_revision_seq_seq');
    RETURN NEW;
END;
$$;
CREATE TRIGGER web_revision_insert BEFORE INSERT ON web_portfolio_revision
    FOR EACH ROW EXECUTE FUNCTION web_revision_before_insert();
CREATE FUNCTION web_revision_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'web_portfolio_revision is append-only: % forbidden', TG_OP USING ERRCODE='23001';
END;
$$;
CREATE TRIGGER web_revision_immutable BEFORE UPDATE OR DELETE ON web_portfolio_revision
    FOR EACH ROW EXECUTE FUNCTION web_revision_reject_mutation();
CREATE TRIGGER web_revision_no_truncate BEFORE TRUNCATE ON web_portfolio_revision
    FOR EACH STATEMENT EXECUTE FUNCTION web_revision_reject_mutation();
DO $$
DECLARE fn text;
BEGIN
    FOREACH fn IN ARRAY ARRAY['web_revision_before_insert()','web_revision_reject_mutation()'] LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SET search_path = %I, pg_temp', current_schema(),fn,current_schema());
    END LOOP;
END;
$$;
