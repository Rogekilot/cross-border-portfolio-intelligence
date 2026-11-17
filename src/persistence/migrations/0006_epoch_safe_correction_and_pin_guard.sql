-- CP1-B fix round 2 (reviews/TECH_REVIEW.md, "CP1-B re-review (fix round)"). 0001-0005 are
-- frozen. Every function below is (re)pinned at the end of this file; any later migration
-- that replaces one of them must repeat the pin, and the integration test that reads
-- pg_proc.proconfig (R2-2) fails the suite if it does not.
--
-- R2-1 (MEDIUM) epoch-safe same-transaction check. 0004 turned the reversal row's 32-bit
--   `xmin` into an xid8 by text cast, which drops the transaction-ID epoch, so on a cluster
--   past its first 2^32 transactions every correction was refused. The check now rebuilds the
--   FULL 64-bit id from the current transaction's own full xid (`pg_current_xact_id()`, which
--   has the epoch) by circular difference: for a visible row's 32-bit xmin `x` and the anchor
--   `A` (64-bit), the true id is the unique X == x (mod 2^32) with |X - A| < 2^31.
--   Why that is sound, including across a wraparound: PostgreSQL guarantees every unfrozen
--   xid that can still be seen in a heap tuple lies within 2^31 of the next xid (autovacuum
--   freezes older ones and the server stops assigning xids before the gap reaches 2^31), and
--   our own transaction's xid is always live, so it is within that window of every such
--   tuple; a subtransaction's xid is allocated after the top-level xid, a few ids away. The
--   reduction of (x - low32(A)) into [-2^31, 2^31) then lands on X in either epoch: for
--   A = 2^32 + 3 and x = 2^32 - 6 it yields A - 9 = 2^32 - 6 (previous epoch), and for
--   A = 5 * 2^32 + 10 and x = 20 it yields 5 * 2^32 + 20. Frozen, bootstrap and invalid xmin
--   values (< 3) are never in progress and are refused. `ledger_full_xid` is a pure function
--   so the boundary arithmetic is tested directly (epoch 0 is all a test cluster can show).
-- R2-3 (LOW) rename guard. The pin names a schema; renaming the schema left the functions
--   pinned to the OLD name, so unqualified names resolved through pg_temp again. Each trigger
--   function that touches ledger tables now starts by comparing its pinned (first)
--   search_path entry with TG_TABLE_SCHEMA, the schema the firing table actually lives in,
--   and FAILS CLOSED before touching any table if they differ. The check is inline and uses
--   only pg_catalog functions, because a helper function would itself be resolved through the
--   stale pinned path. After a rename the owner must re-run the pin block for the new name
--   (the raised error says so); until then appends fail, and no shadow attack can succeed.

CREATE FUNCTION ledger_full_xid(xmin_text text, anchor numeric) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    x numeric := xmin_text::numeric;
    diff numeric;
    full_id numeric;
BEGIN
    IF x < 3 THEN
        RETURN NULL;
    END IF;
    diff := x - (anchor % 4294967296);
    IF diff > 2147483647 THEN
        diff := diff - 4294967296;
    ELSIF diff < -2147483648 THEN
        diff := diff + 4294967296;
    END IF;
    full_id := anchor + diff;
    IF full_id < 3 THEN
        RETURN NULL;
    END IF;
    RETURN full_id;
END;
$$;

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
    -- R2-3 rename guard, INLINE (a helper function would itself be looked up through the
    -- stale pinned path and never be reached): only pg_catalog functions are used here.
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
        -- F10 atomicity: the reversal must belong to THIS transaction. Any row of another
        -- transaction that is visible to us has committed; an in-progress row visible to us
        -- can only be our own (or one of our subtransactions'). Epoch-safe (see header).
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

CREATE OR REPLACE FUNCTION ledger_event_check_transfer_pairing() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    leg ledger_event%ROWTYPE;
    out_account uuid;
    in_account uuid;
    n_out bigint;
    n_in bigint;
BEGIN
    IF trim(both '"' from split_part(current_setting('search_path'), ',', 1))
       IS DISTINCT FROM TG_TABLE_SCHEMA THEN
        RAISE EXCEPTION 'ledger trigger functions are pinned to a schema other than the one holding the ledger table (schema renamed or pin lost): re-run the search_path pin for "%"', TG_TABLE_SCHEMA
            USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_search_path_pin_stale';
    END IF;

    IF NEW.event_type = 'REVERSAL' THEN
        SELECT * INTO leg FROM ledger_event WHERE event_id = NEW.reverses_event_id;
    ELSE
        leg := NEW;
    END IF;
    IF leg.event_type IS NULL
       OR leg.event_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
       OR leg.counterparty_account_id IS NULL THEN
        RETURN NULL;
    END IF;

    IF leg.event_type = 'TRANSFER_OUT' THEN
        out_account := leg.account_id;
        in_account := leg.counterparty_account_id;
    ELSE
        out_account := leg.counterparty_account_id;
        in_account := leg.account_id;
    END IF;

    SELECT count(*) FILTER (WHERE e.event_type = 'TRANSFER_OUT'),
           count(*) FILTER (WHERE e.event_type = 'TRANSFER_IN')
      INTO n_out, n_in
      FROM ledger_event e
     WHERE e.event_type IN ('TRANSFER_OUT', 'TRANSFER_IN')
       AND e.event_date = leg.event_date
       AND e.currency = leg.currency
       AND e.amount IS NOT DISTINCT FROM leg.amount
       AND e.listing_id IS NOT DISTINCT FROM leg.listing_id
       AND e.quantity IS NOT DISTINCT FROM leg.quantity
       AND ((e.event_type = 'TRANSFER_OUT' AND e.account_id = out_account
             AND e.counterparty_account_id = in_account)
            OR (e.event_type = 'TRANSFER_IN' AND e.account_id = in_account
                AND e.counterparty_account_id = out_account))
       AND NOT EXISTS (SELECT 1 FROM ledger_event r
                       WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = e.event_id);

    IF n_out <> n_in THEN
        RAISE EXCEPTION 'internal transfer legs do not match (% out, % in): both legs must be appended (or reversed) in one transaction with the same date, currency and amount or listing and quantity', n_out, n_in
            USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_transfer_pairing';
    END IF;
    RETURN NULL;
END;
$$;

-- ---- pin every function in the ledger schema (see 0004) -------------------------------
-- Replacing a function resets its SET list, so this block must come after every
-- CREATE OR REPLACE FUNCTION above and be repeated by any later migration that replaces one.

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
