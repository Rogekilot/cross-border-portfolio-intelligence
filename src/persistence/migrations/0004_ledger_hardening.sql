-- CP1-B review fixes (reviews/TECH_REVIEW.md, "CP1-B review (809d4d8)"). Migrations
-- 0001-0003 are frozen; every fix is here or in 0005. Later migrations that replace any
-- function below MUST re-run the pinning block at the end of this file for it.
--
-- CP1B-1 (HIGH)  search_path pinning. PostgreSQL searches the session's pg_temp schema
--   FIRST for relations and sequences unless pg_temp is listed explicitly in search_path,
--   and any role holding the default database TEMPORARY privilege can create TEMP tables
--   named `account` / `ledger_event` and a TEMP SEQUENCE named like ours. The plain invoker
--   trigger functions of 0003 used unqualified names, so a session could blind every
--   trigger rule. Fix chosen: give each trigger function its own
--   `SET search_path = <ledger schema>, pg_temp` (pg_temp explicitly LAST; pg_catalog is
--   implicitly first). Why not schema-qualify every reference: migrations are
--   schema-agnostic (tests apply them into disposable schemas; production's schema name is
--   not known to the file), qualification would need dynamic SQL in every statement, and a
--   pinned path also covers references added later. The schema is taken from
--   current_schema() at apply time, i.e. exactly where the tables were created. The fix does
--   NOT rely on revoking TEMPORARY (defence in depth is in the production grant spec).
-- CP1B-2 (MEDIUM) a same-key/same-content (or same event_id) resubmission is decided BEFORE
--   the snapshot and cross-event rules, so an unchanged re-import stays an idempotent no-op.
-- CP1B-3 (MEDIUM) account_id and portfolio_id are immutable.
-- CP1B-5 (LOW)   a replacement's reversal must have been inserted by the SAME transaction.
-- CP1B-7 (LOW)   blank source_reference: SQL now matches Python's str.strip() exactly.
-- CP1B-8 (LOW)   recorded_at is set by the trigger, never by the inserting role.

-- ---- CP1B-3: account identity is immutable ------------------------------------------

CREATE FUNCTION account_guard_identity() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.account_id IS DISTINCT FROM OLD.account_id
       OR NEW.portfolio_id IS DISTINCT FROM OLD.portfolio_id THEN
        RAISE EXCEPTION 'account.account_id and account.portfolio_id are immutable'
            USING ERRCODE = '23001', CONSTRAINT = 'account_identity_immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER account_identity_immutable
    BEFORE UPDATE ON account
    FOR EACH ROW EXECUTE FUNCTION account_guard_identity();

-- ---- CP1B-7: blank source_reference agrees with Python -------------------------------
-- The pattern is persistence.ledger_sql.render_blank_pattern(): exactly the code points for
-- which Python's str.isspace() is true (hex escapes; a unit test compares them).

ALTER TABLE ledger_event
    DROP CONSTRAINT ledger_event_source_reference_not_blank,
    ADD CONSTRAINT ledger_event_source_reference_not_blank CHECK (
        source_reference !~ '^[\x09-\x0d\x1c-\x20\x85\xa0\x1680\x2000-\x200a\x2028-\x2029\x202f\x205f\x3000]*$');

-- ---- CP1B-2, 3, 5, 8: the BEFORE INSERT trigger, replaced -----------------------------
-- Order inside is load-bearing (see 0003 for the lock and sequence reasoning):
--   1. READ COMMITTED required;  2. recorded_at forced;  3. per-portfolio advisory lock;
--   4. draw ledger_seq under the lock;  5. idempotency decided (skip the rules when the row
--   will conflict on event_id or (account, source_reference), which ON CONFLICT DO NOTHING
--   then drops or a plain INSERT rejects: skipping can never let a duplicate in);
--   6. the cross-event rules.

CREATE OR REPLACE FUNCTION ledger_event_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target_type text;
    own_portfolio uuid;
    counterparty_portfolio uuid;
    snapshot_date date;
    reversal_xmin text;
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'ledger appends require READ COMMITTED isolation'
            USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_requires_read_committed';
    END IF;

    NEW.recorded_at := now();

    SELECT portfolio_id INTO own_portfolio FROM account WHERE account_id = NEW.account_id;
    IF own_portfolio IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(
            hashtextextended('finweb.ledger.portfolio:' || own_portfolio::text, 0));
    END IF;

    NEW.ledger_seq := nextval('ledger_event_ledger_seq_seq');

    IF EXISTS (SELECT 1 FROM ledger_event WHERE event_id = NEW.event_id)
       OR (NEW.source_reference IS NOT NULL AND EXISTS (
            SELECT 1 FROM ledger_event
            WHERE account_id = NEW.account_id AND source_reference = NEW.source_reference)) THEN
        RETURN NEW;
    END IF;

    IF NEW.event_type = 'REVERSAL' THEN
        SELECT event_type INTO target_type FROM ledger_event
            WHERE event_id = NEW.reverses_event_id;
        IF target_type = 'REVERSAL' THEN
            RAISE EXCEPTION 'a REVERSAL cannot be reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_reversal_of_reversal';
        END IF;
    END IF;

    IF NEW.corrects_event_id IS NOT NULL THEN
        SELECT r.xmin::text INTO reversal_xmin FROM ledger_event r
            WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = NEW.corrects_event_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'corrects_event_id must name an event that has been reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_corrects_reversed_event';
        END IF;
        -- F10 atomicity: the reversal must belong to THIS transaction. A row of another
        -- transaction that is visible to us has committed; an in-progress row visible to us
        -- can only be our own (or one of our subtransactions').
        IF pg_xact_status(reversal_xmin::xid8) IS DISTINCT FROM 'in progress' THEN
            RAISE EXCEPTION 'a replacement must be appended in the same transaction as its reversal'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_correction_same_transaction';
        END IF;
    END IF;

    IF NEW.counterparty_account_id IS NOT NULL THEN
        SELECT portfolio_id INTO counterparty_portfolio FROM account
            WHERE account_id = NEW.counterparty_account_id;
        IF counterparty_portfolio IS NOT NULL
           AND own_portfolio IS DISTINCT FROM counterparty_portfolio THEN
            RAISE EXCEPTION 'counterparty account must be in the same portfolio'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_counterparty_same_portfolio';
        END IF;
    END IF;

    IF NEW.event_type IN ('OPENING_POSITION', 'OPENING_CASH') THEN
        IF EXISTS (
            SELECT 1 FROM ledger_event o
            WHERE o.account_id = NEW.account_id
              AND o.event_type IN ('OPENING_POSITION', 'OPENING_CASH')
              AND o.event_date <> NEW.event_date
              AND NOT EXISTS (SELECT 1 FROM ledger_event r
                              WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = o.event_id)
        ) THEN
            RAISE EXCEPTION 'all opening events of an account share one snapshot date'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_snapshot_single_date';
        END IF;
        IF EXISTS (
            SELECT 1 FROM ledger_event e
            WHERE e.account_id = NEW.account_id
              AND e.event_type NOT IN ('OPENING_POSITION', 'OPENING_CASH', 'REVERSAL')
              AND (e.event_date < NEW.event_date
                   OR (e.event_date = NEW.event_date AND e.event_type <> 'SPLIT'))
              AND NOT EXISTS (SELECT 1 FROM ledger_event r
                              WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = e.event_id)
        ) THEN
            RAISE EXCEPTION 'the account already has activity on or before this snapshot date'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_snapshot_precedes_activity';
        END IF;
    ELSIF NEW.event_type <> 'REVERSAL' THEN
        SELECT max(o.event_date) INTO snapshot_date FROM ledger_event o
            WHERE o.account_id = NEW.account_id
              AND o.event_type IN ('OPENING_POSITION', 'OPENING_CASH')
              AND NOT EXISTS (SELECT 1 FROM ledger_event r
                              WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = o.event_id);
        IF snapshot_date IS NOT NULL
           AND (NEW.event_date < snapshot_date
                OR (NEW.event_date = snapshot_date AND NEW.event_type <> 'SPLIT')) THEN
            RAISE EXCEPTION 'events in a snapshot account must be dated after the snapshot date'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_after_snapshot_date';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- ---- CP1B-1: pin every trigger function's name resolution ----------------------------
-- (Must run after every CREATE OR REPLACE above: replacing a function resets its SET list.)

DO $$
DECLARE
    fn text;
BEGIN
    FOREACH fn IN ARRAY ARRAY[
        'ledger_event_reject_mutation()',
        'ledger_event_before_insert()',
        'ledger_event_check_transfer_pairing()',
        'account_guard_identity()'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SET search_path = %I, pg_temp',
                       current_schema(), fn, current_schema());
    END LOOP;
END;
$$;
