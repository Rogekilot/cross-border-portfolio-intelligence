-- CP1-B follow-up (ledger-replay/1.3, Ruling 3.4 and finding F12). 0001-0006 are frozen.
-- Data-entry rule: ONE live SPLIT per position (account_id, listing_id) per ex-date
-- (event_date), carrying the combined ratio of that date's distribution (for example an
-- A-share "10送3转增2" is (15, 10)). Two same-day splits are ambiguous (duplicate entry,
-- components that add, or successive actions that multiply), so storage refuses the second
-- one at append time instead of guessing; replay's LEDGER_INCONSISTENT flag stays as the
-- defence for anything stored before this migration.
--
-- Mechanism: the check lives in ledger_event_before_insert, AFTER the per-portfolio advisory
-- lock is taken and AFTER the idempotency early return, so it cannot race another append to
-- the same portfolio and an unchanged resubmission of the stored split stays a no-op.
-- "Live" means not reversed (a reversed split never happened, ledger-replay §2.1), so
-- append_correction (reversal of the old split, then the combined replacement, one
-- transaction) works: the reversal row is already visible to the replacement's check.
-- The function keeps its inline schema-rename guard (0006) and is re-pinned below
-- (replacing a function resets its SET list).

CREATE OR REPLACE FUNCTION ledger_event_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target_type text;
    own_portfolio uuid;
    counterparty_portfolio uuid;
    snapshot_date date;
    reversal_xmin text;
    reversal_full_xid numeric;
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'ledger trigger functions are pinned to a schema other than the one holding the ledger table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_search_path_pin_stale';
    END IF;

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
        -- F10 atomicity, epoch-safe (see 0006).
        reversal_full_xid := ledger_full_xid(
            reversal_xmin, pg_current_xact_id()::text::numeric);
        IF reversal_full_xid IS NULL
           OR pg_xact_status(reversal_full_xid::text::xid8) IS DISTINCT FROM 'in progress' THEN
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

    -- F12 / Ruling 3.4: one live SPLIT per (account, listing, event_date).
    IF NEW.event_type = 'SPLIT' THEN
        IF EXISTS (
            SELECT 1 FROM ledger_event s
            WHERE s.event_type = 'SPLIT'
              AND s.account_id = NEW.account_id
              AND s.listing_id = NEW.listing_id
              AND s.event_date = NEW.event_date
              AND NOT EXISTS (SELECT 1 FROM ledger_event r
                              WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = s.event_id)
        ) THEN
            RAISE EXCEPTION 'a live SPLIT already exists for this account, listing and date: reverse it and append ONE split carrying the combined ratio'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_split_once_per_day';
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

-- ---- re-pin every function in the ledger schema (see 0004 and 0006) --------------------

DO $$
DECLARE
    fn text;
BEGIN
    FOREACH fn IN ARRAY ARRAY[
        'ledger_event_reject_mutation()',
        'ledger_event_before_insert()',
        'ledger_event_check_transfer_pairing()',
        'account_guard_identity()',
        'ledger_full_xid(text,numeric)'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SET search_path = %I, pg_temp',
                       current_schema(), fn, current_schema());
    END LOOP;
END;
$$;
