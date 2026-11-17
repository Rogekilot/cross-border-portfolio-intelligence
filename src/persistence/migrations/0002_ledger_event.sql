-- CP1-B step 2, migration 2: the append-only ledger_event table.
-- Mirrors src/domain/ledger.py. Storage assigns ledger_seq and recorded_at; the
-- domain event carries neither. recorded_at is audit metadata only: it is never an
-- input to any computation (no wall-clock value affects results).
-- MIGRATION POLICY: 0001-0003 were edited in place in CP1-B steps 2c and 2d because they
-- had never been applied to any database. From the first real apply onward, every change
-- is a NEW numbered file; applied files are immutable (the runner refuses a changed
-- checksum).
-- ledger_seq is NOT a default/identity column: the BEFORE INSERT trigger in 0003 draws
-- it from the sequence below while holding the per-portfolio append lock, so that
-- within a portfolio ledger_seq order equals commit order (ledger-replay/1.1 §2.3).
-- Quantities and amounts are NUMERIC with no precision or scale (exact Decimal).
-- amount and cost_basis are in `currency`. CURRENCY_CONVERSION (ledger-replay/1.1 §5A)
-- is the one exception: `currency`/`amount` are the SOLD side and the BOUGHT side is
-- bought_amount + bought_currency (always a different currency). There is NO rate column
-- and none may be added: the ratio of the two amounts is never stored (§5A.7).
-- No reporting-currency column, no price, no lot, no position, no balance, no
-- ticker/FIGI/MIC (PD-0021 §1, §9).
-- The generated block is checked against domain.ledger.FIELD_RULES by a unit test.

CREATE SEQUENCE ledger_event_ledger_seq_seq AS bigint;

CREATE TABLE ledger_event (
    ledger_seq bigint PRIMARY KEY,
    event_id uuid NOT NULL,
    account_id uuid NOT NULL REFERENCES account (account_id),
    event_type text NOT NULL,
    event_date date NOT NULL,
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    listing_id uuid NULL REFERENCES listing (listing_id),
    quantity numeric NULL,
    amount numeric NULL,
    cost_basis numeric NULL,
    bought_amount numeric NULL,
    bought_currency text NULL CHECK (bought_currency ~ '^[A-Z]{3}$'),
    split_new numeric NULL,
    split_old numeric NULL,
    counterparty_account_id uuid NULL REFERENCES account (account_id),
    settlement_date date NULL,
    ex_date date NULL,
    reverses_event_id uuid NULL,
    corrects_event_id uuid NULL,
    source_reference text NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ledger_event_event_id_key UNIQUE (event_id),
    CONSTRAINT ledger_event_idempotency_key UNIQUE (account_id, source_reference),
    CONSTRAINT ledger_event_reversal_target_key UNIQUE (event_id, account_id, currency),
    CONSTRAINT ledger_event_correction_target_key UNIQUE (event_id, account_id),
    -- A reversal must target an existing event in the same account and currency (for a
    -- conversion: the sold currency). MATCH SIMPLE: skipped when reverses_event_id IS
    -- NULL (account_id and currency are NOT NULL, so it is checked whenever the
    -- reference is present).
    CONSTRAINT ledger_event_reversal_target_fk FOREIGN KEY (reverses_event_id, account_id, currency)
        REFERENCES ledger_event (event_id, account_id, currency),
    -- A replacement must correct an existing event in the same account (currency may
    -- differ: a correction may fix the currency itself).
    CONSTRAINT ledger_event_correction_target_fk FOREIGN KEY (corrects_event_id, account_id)
        REFERENCES ledger_event (event_id, account_id),
-- BEGIN GENERATED: persistence.ledger_sql.render_generated_region (do not edit)
    CONSTRAINT ledger_event_type_valid CHECK (event_type IN ('BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TAX', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER_IN', 'TRANSFER_OUT', 'SPLIT', 'INTEREST_CHARGED', 'CURRENCY_CONVERSION', 'OPENING_POSITION', 'OPENING_CASH', 'REVERSAL')),
    CONSTRAINT ledger_event_fields_buy CHECK (event_type <> 'BUY' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_sell CHECK (event_type <> 'SELL' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_dividend CHECK (event_type <> 'DIVIDEND' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_interest CHECK (event_type <> 'INTEREST' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_fee CHECK (event_type <> 'FEE' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_tax CHECK (event_type <> 'TAX' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_deposit CHECK (event_type <> 'DEPOSIT' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_withdrawal CHECK (event_type <> 'WITHDRAWAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_transfer_in CHECK (event_type <> 'TRANSFER_IN' OR (bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_transfer_out CHECK (event_type <> 'TRANSFER_OUT' OR (cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_split CHECK (event_type <> 'SPLIT' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NOT NULL AND split_old IS NOT NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_interest_charged CHECK (event_type <> 'INTEREST_CHARGED' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_currency_conversion CHECK (event_type <> 'CURRENCY_CONVERSION' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NOT NULL AND bought_currency IS NOT NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_opening_position CHECK (event_type <> 'OPENING_POSITION' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND corrects_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_opening_cash CHECK (event_type <> 'OPENING_CASH' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND corrects_event_id IS NULL)),
    CONSTRAINT ledger_event_fields_reversal CHECK (event_type <> 'REVERSAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NOT NULL AND corrects_event_id IS NULL)),
    CONSTRAINT ledger_event_transfer_shape CHECK (event_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT') OR ((listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL) OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL))),
    CONSTRAINT ledger_event_internal_transfer_in_no_cost_basis CHECK (event_type <> 'TRANSFER_IN' OR counterparty_account_id IS NULL OR cost_basis IS NULL),
-- END GENERATED
    -- Value rules (mirror LedgerEvent._validate_values). `< 'Infinity'` also rejects
    -- NaN, which PostgreSQL orders above every number.
    CONSTRAINT ledger_event_quantity_positive CHECK (quantity > 0 AND quantity < 'Infinity'::numeric),
    CONSTRAINT ledger_event_amount_positive CHECK (amount > 0 AND amount < 'Infinity'::numeric),
    CONSTRAINT ledger_event_cost_basis_nonnegative CHECK (cost_basis >= 0 AND cost_basis < 'Infinity'::numeric),
    CONSTRAINT ledger_event_bought_amount_positive CHECK (bought_amount > 0 AND bought_amount < 'Infinity'::numeric),
    CONSTRAINT ledger_event_bought_currency_differs CHECK (bought_currency <> currency),
    CONSTRAINT ledger_event_bought_pair CHECK ((bought_amount IS NULL) = (bought_currency IS NULL)),
    CONSTRAINT ledger_event_split_ratio_positive CHECK (
        split_new > 0 AND split_new < 'Infinity'::numeric
        AND split_old > 0 AND split_old < 'Infinity'::numeric),
    CONSTRAINT ledger_event_settlement_not_before_event CHECK (settlement_date >= event_date),
    CONSTRAINT ledger_event_ex_date_not_after_event CHECK (ex_date <= event_date),
    CONSTRAINT ledger_event_counterparty_not_self CHECK (counterparty_account_id <> account_id),
    CONSTRAINT ledger_event_no_self_reversal CHECK (reverses_event_id <> event_id),
    CONSTRAINT ledger_event_no_self_correction CHECK (corrects_event_id <> event_id),
    CONSTRAINT ledger_event_source_reference_not_blank CHECK (btrim(source_reference) <> '')
);

ALTER SEQUENCE ledger_event_ledger_seq_seq OWNED BY ledger_event.ledger_seq;

-- An event may be reversed at most once.
CREATE UNIQUE INDEX ledger_event_reversed_once ON ledger_event (reverses_event_id)
    WHERE reverses_event_id IS NOT NULL;

-- An event may be corrected (replaced) at most once.
CREATE UNIQUE INDEX ledger_event_corrected_once ON ledger_event (corrects_event_id)
    WHERE corrects_event_id IS NOT NULL;

CREATE INDEX ledger_event_account_event_date ON ledger_event (account_id, event_date);
CREATE INDEX ledger_event_listing ON ledger_event (listing_id) WHERE listing_id IS NOT NULL;
