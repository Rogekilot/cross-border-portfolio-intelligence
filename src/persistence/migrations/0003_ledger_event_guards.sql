-- CP1-B step 2, migration 3: append-only enforcement, per-portfolio append
-- serialization, and the cross-event rules that need a lookup
-- (CROSS_EVENT_RULES_DEFERRED in domain.ledger; conventions ledger-replay/1.0).
-- MIGRATION POLICY: edited in place in step 2c (never applied anywhere); from the
-- first real apply onward, changes are NEW numbered files only.
-- Triggers cannot stop a superuser or the table owner from disabling them; the
-- application role should hold only SELECT and INSERT on ledger_event, plus USAGE on
-- ledger_event_ledger_seq_seq (the trigger draws it as the invoking role; make the
-- function SECURITY DEFINER in a later migration if that is not wanted). Constraint
-- names are load-bearing: persistence.ledger_store maps them to typed errors.

CREATE FUNCTION ledger_event_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ledger_event is append-only: % is not permitted', TG_OP
        USING ERRCODE = '23001', CONSTRAINT = 'ledger_event_append_only';
END;
$$;

CREATE TRIGGER ledger_event_no_update_delete
    BEFORE UPDATE OR DELETE ON ledger_event
    FOR EACH ROW EXECUTE FUNCTION ledger_event_reject_mutation();

CREATE TRIGGER ledger_event_no_truncate
    BEFORE TRUNCATE ON ledger_event
    FOR EACH STATEMENT EXECUTE FUNCTION ledger_event_reject_mutation();

-- The single BEFORE INSERT trigger. Order inside is load-bearing:
--   1. require READ COMMITTED, so every lookup below sees rows committed by the
--      transaction that held the lock before us;
--   2. take the per-portfolio advisory lock (transaction-scoped: released at commit);
--   3. only then draw ledger_seq. A default/identity value would be drawn BEFORE this
--      trigger runs, i.e. before the lock, which is why ledger_seq has no default;
--   4. run the cross-event checks under the lock (closes their check-then-insert races).
-- Because the lock is released only after the transaction's commit is visible, and the
-- sequence value is drawn under it, within one portfolio ledger_seq order equals commit
-- order. Across portfolios nothing is promised (a global sequence; different portfolios
-- do not block each other; commit order across them may differ from ledger_seq order).
-- A hash collision between two portfolios' lock keys only serializes them needlessly.
-- BEFORE INSERT runs before the foreign-key checks, so a missing target is left to the
-- FKs (a NULL lookup below never raises by itself).
CREATE FUNCTION ledger_event_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target_type text;
    own_portfolio uuid;
    counterparty_portfolio uuid;
    snapshot_date date;
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'ledger appends require READ COMMITTED isolation'
            USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_requires_read_committed';
    END IF;

    SELECT portfolio_id INTO own_portfolio FROM account WHERE account_id = NEW.account_id;
    IF own_portfolio IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(
            hashtextextended('finweb.ledger.portfolio:' || own_portfolio::text, 0));
    END IF;

    NEW.ledger_seq := nextval('ledger_event_ledger_seq_seq');

    IF NEW.event_type = 'REVERSAL' THEN
        SELECT event_type INTO target_type FROM ledger_event
            WHERE event_id = NEW.reverses_event_id;
        IF target_type = 'REVERSAL' THEN
            RAISE EXCEPTION 'a REVERSAL cannot be reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_reversal_of_reversal';
        END IF;
    END IF;

    IF NEW.corrects_event_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM ledger_event
            WHERE event_type = 'REVERSAL' AND reverses_event_id = NEW.corrects_event_id
        ) THEN
            RAISE EXCEPTION 'corrects_event_id must name an event that has been reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_corrects_reversed_event';
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

    -- Snapshot accounts (ledger-replay/1.0 §8). "Live" = not reversed: a reversed
    -- event never happened (§2.1), so it constrains nothing.
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

CREATE TRIGGER ledger_event_before_insert
    BEFORE INSERT ON ledger_event
    FOR EACH ROW EXECUTE FUNCTION ledger_event_before_insert();

-- Internal transfer pairing (ledger-replay/1.0 §6.2). A single-row insert cannot know
-- whether its partner leg is coming, so the check is DEFERRED to commit: per matching
-- group (out-account, in-account, event_date, currency, amount or listing+quantity)
-- the number of live TRANSFER_OUT legs must equal the number of live TRANSFER_IN legs.
-- Legs appended one at a time therefore pass only if their partner is appended in the
-- same transaction (ledger_store.append_internal_transfer / append_batch). Reversing a
-- leg re-runs the check for its group, so its partner must be reversed in the same
-- transaction. The comparison is by counts, not by a pair identifier: two identical
-- transfers on one day are interchangeable, which cannot change any replayed state.
-- The commit-time check runs while this transaction still holds the portfolio lock.
CREATE FUNCTION ledger_event_check_transfer_pairing() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    leg ledger_event%ROWTYPE;
    out_account uuid;
    in_account uuid;
    n_out bigint;
    n_in bigint;
BEGIN
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

CREATE CONSTRAINT TRIGGER ledger_event_transfer_pairing
    AFTER INSERT ON ledger_event
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ledger_event_check_transfer_pairing();
