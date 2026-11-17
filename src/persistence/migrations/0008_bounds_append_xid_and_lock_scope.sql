-- CP1-B cleanup round (reviews/TECH_REVIEW.md §21, findings R3-1 to R3-4). 0001-0007 are
-- frozen. The insert trigger is replaced once more and re-pinned at the end (replacing a
-- function resets its SET list); it keeps the inline schema-rename guard of 0006.
--
-- R3-1  Bounded numeric values. NUMERIC admits ~131,000 integer digits and 16,383 decimals,
--   which no real quantity or amount needs and which made replay slow or crash. Every numeric
--   column now has a generous but finite bound: value < 1E30 (at most 30 integer digits) and
--   scale(value) <= 24 decimals. Reasoning: the largest realistic amounts (a JPY/CNY/HKD
--   portfolio in the trillions, a token supply of 1E15) need ~16 integer digits; 30 leaves
--   fourteen orders of magnitude of headroom. The finest realistic quantities are 18-decimal
--   crypto units (wei); 24 decimals leaves six more digits for very small unit prices and
--   fractional split arithmetic. `scale()` is the STORED scale (trailing zeros count), so a
--   value cannot smuggle thousands of digits in as trailing zeros. The bound is enforced BY THE
--   DATABASE ONLY: the domain event constructors deliberately do not reject it (replay must
--   stay able to represent and survive values from older or foreign data); domain.ledger
--   states the same limits in numeric_bounds_violation() so a test can compare them. The six
--   CHECKs are NOT VALID: enforced for every new row, never re-scanned against existing rows,
--   so a ledger that already holds an out-of-bound row (legal before 0008, for example a
--   28-decimal deposit) still upgrades, and replay stays robust for such rows (PD-0026).
--   Violations map to ledger_store.LedgerValueOutOfRangeError.
--   Known limitation: the CHECKs run before ON CONFLICT, so resubmitting a stored event whose
--   value is written at scale > 24 gets the typed out-of-range refusal, not an idempotent
--   no-op (documented in tech plan 14.2a).
-- (0008 was edited in place once, in the R4-1 round, because it had never been applied to any
--   persistent database; its CHECKSUMS line was updated with it. 0001-0007 were not touched.)
-- R3-2  Append-transaction identity. `append_xid` is the full 64-bit id (xid8) of the
--   transaction that appended the row: every row of one append transaction (including rows
--   written inside savepoints) shares it, rows of different transactions never do, it does not
--   depend on the wall clock and never repeats. `portfolio_id` is the row's portfolio,
--   denormalised by the trigger (safe because account.portfolio_id is immutable, 0004), so a
--   per-portfolio index exists. Both are set by the trigger and cannot be set by the caller,
--   as recorded_at cannot. recorded_at stays audit metadata: it is never an input to any
--   computation, including the correction-pin guard, which must use append_xid instead.
--   Rows appended BEFORE this migration cannot be back-filled (ledger_event rows are never
--   updated, and the transaction that wrote them is not recoverable), so their append_xid and
--   portfolio_id are NULL; the NOT NULL rule is a NOT VALID constraint, enforced for every new
--   row only. A NULL append_xid means "appended before 0008, in some earlier transaction".
-- R3-3  The same-transaction correction check now compares the reversal row's append_xid with
--   pg_current_xact_id(): exact, epoch-safe by construction, and it never calls
--   pg_xact_status, so a very old or frozen reversal (whose raw xmin is meaningless) gets the
--   NAMED refusal ledger_event_correction_same_transaction, never an untyped 22023. A NULL
--   append_xid (pre-0008) is by definition an earlier transaction: refused. The xmin
--   arithmetic of 0006 (ledger_full_xid) is no longer used by any trigger; it is kept
--   because 0006 is frozen and it is harmless.
-- R3-4  Lock scope. The per-portfolio advisory lock key now includes the schema name, so two
--   ledger schemas in one database (concurrent test runs, or a multi-schema host) never
--   contend on the same key.

-- ---- R3-1: numeric bounds ----------------------------------------------------------------

ALTER TABLE ledger_event
    ADD CONSTRAINT ledger_event_quantity_bounds CHECK (quantity < 1E30 AND scale(quantity) <= 24) NOT VALID,
    ADD CONSTRAINT ledger_event_amount_bounds CHECK (amount < 1E30 AND scale(amount) <= 24) NOT VALID,
    ADD CONSTRAINT ledger_event_cost_basis_bounds CHECK (cost_basis < 1E30 AND scale(cost_basis) <= 24) NOT VALID,
    ADD CONSTRAINT ledger_event_bought_amount_bounds CHECK (bought_amount < 1E30 AND scale(bought_amount) <= 24) NOT VALID,
    ADD CONSTRAINT ledger_event_split_new_bounds CHECK (split_new < 1E30 AND scale(split_new) <= 24) NOT VALID,
    ADD CONSTRAINT ledger_event_split_old_bounds CHECK (split_old < 1E30 AND scale(split_old) <= 24) NOT VALID;

-- ---- R3-2: append transaction identity and portfolio ------------------------------------------

ALTER TABLE ledger_event
    ADD COLUMN append_xid xid8 NULL,
    ADD COLUMN portfolio_id uuid NULL REFERENCES portfolio (portfolio_id);

ALTER TABLE ledger_event
    ADD CONSTRAINT ledger_event_append_identity_present
        CHECK (append_xid IS NOT NULL AND portfolio_id IS NOT NULL) NOT VALID;

COMMENT ON COLUMN ledger_event.recorded_at IS
    'Audit metadata only. Set by the insert trigger (now()); never an input to any computation. Use append_xid to group rows by append transaction.';
COMMENT ON COLUMN ledger_event.append_xid IS
    'Full xid8 of the appending transaction (trigger-set): equal for rows of one append transaction, distinct across transactions, clock-independent. NULL only for rows appended before migration 0008.';
COMMENT ON COLUMN ledger_event.portfolio_id IS
    'Portfolio of the row, set by the insert trigger from account (immutable). NULL only for rows appended before migration 0008.';

CREATE INDEX ledger_event_portfolio_seq ON ledger_event (portfolio_id, ledger_seq) INCLUDE (append_xid);

-- ---- the insert trigger, replaced (R3-2, R3-3, R3-4) ---------------------------------------

CREATE OR REPLACE FUNCTION ledger_event_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target_type text;
    own_portfolio uuid;
    counterparty_portfolio uuid;
    snapshot_date date;
    reversal_xid xid8;
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
    NEW.append_xid := pg_current_xact_id();

    SELECT portfolio_id INTO own_portfolio FROM account WHERE account_id = NEW.account_id;
    NEW.portfolio_id := own_portfolio;
    IF own_portfolio IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(
            'finweb.ledger.portfolio:' || TG_TABLE_SCHEMA || ':' || own_portfolio::text, 0));
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
        SELECT r.append_xid INTO reversal_xid FROM ledger_event r
            WHERE r.event_type = 'REVERSAL' AND r.reverses_event_id = NEW.corrects_event_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'corrects_event_id must name an event that has been reversed'
                USING ERRCODE = '23514', CONSTRAINT = 'ledger_event_corrects_reversed_event';
        END IF;
        -- F10 atomicity: the reversal must have been appended by THIS transaction. Exact
        -- comparison of full ids; a NULL (pre-0008) reversal is by definition an earlier one.
        IF reversal_xid IS DISTINCT FROM pg_current_xact_id() THEN
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

-- ---- re-pin every function in the ledger schema (see 0004, 0006) -------------------------------

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
