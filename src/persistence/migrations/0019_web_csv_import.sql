-- CP7-C immutable, owned import reports and successful financial source identities.
CREATE TABLE web_csv_report (
    report_id uuid PRIMARY KEY,
    portfolio_id uuid NOT NULL REFERENCES web_saved_sandbox(portfolio_id),
    operation_id uuid NOT NULL,
    proposal_sha256 text NOT NULL CHECK(proposal_sha256 ~ '^[0-9a-f]{64}$'),
    report_json text NOT NULL CHECK(octet_length(report_json)<=2000000),
    report_sha256 text NOT NULL CHECK(report_sha256 ~ '^[0-9a-f]{64}$'),
    revision_id uuid NULL,
    status text NOT NULL CHECK(status IN ('COMMITTED','REPORT_ONLY','ALREADY_IMPORTED')),
    created_at timestamptz NOT NULL,
    UNIQUE(portfolio_id,operation_id)
);
CREATE TABLE web_csv_source_key (
    source_key text PRIMARY KEY CHECK(source_key ~ '^[0-9a-f]{64}$'),
    portfolio_id uuid NOT NULL REFERENCES web_saved_sandbox(portfolio_id),
    identity_json text NOT NULL CHECK(octet_length(identity_json)<=4096),
    content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
    source_kind text NOT NULL CHECK(source_kind IN ('EVENT','SNAPSHOT')),
    report_id uuid NOT NULL REFERENCES web_csv_report(report_id) DEFERRABLE INITIALLY DEFERRED,
    row_number integer NOT NULL CHECK(row_number BETWEEN 0 AND 128),
    account_id uuid NOT NULL REFERENCES account(account_id),
    event_id uuid NULL REFERENCES ledger_event(event_id),
    CHECK((source_kind='EVENT' AND row_number>0 AND event_id IS NOT NULL) OR
          (source_kind='SNAPSHOT' AND row_number=0 AND event_id IS NULL))
);
CREATE INDEX web_csv_report_portfolio ON web_csv_report(portfolio_id,created_at,report_id);
CREATE INDEX web_csv_source_portfolio ON web_csv_source_key(portfolio_id,report_id);
CREATE TRIGGER web_csv_report_immutable BEFORE UPDATE OR DELETE ON web_csv_report
    FOR EACH ROW EXECUTE FUNCTION web_revision_reject_mutation();
CREATE TRIGGER web_csv_report_no_truncate BEFORE TRUNCATE ON web_csv_report
    FOR EACH STATEMENT EXECUTE FUNCTION web_revision_reject_mutation();
CREATE TRIGGER web_csv_source_immutable BEFORE UPDATE OR DELETE ON web_csv_source_key
    FOR EACH ROW EXECUTE FUNCTION web_revision_reject_mutation();
CREATE TRIGGER web_csv_source_no_truncate BEFORE TRUNCATE ON web_csv_source_key
    FOR EACH STATEMENT EXECUTE FUNCTION web_revision_reject_mutation();
