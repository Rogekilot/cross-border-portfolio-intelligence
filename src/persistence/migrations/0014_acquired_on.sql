-- PD-0036 §1 (ledger-replay/1.5 Ruling 0.6): an OPTIONAL, user-supplied `acquired_on` date on a ledger event. Allowed only on OPENING_POSITION and on an
-- EXTERNAL security TRANSFER_IN (no counterparty), and never after the event's own event_date. It is additive: no existing row has it, nothing reads it but the FIFO mode
-- of the lot fold, and the `none` replay mode ignores it (CP1 outputs stay byte-identical).
-- Delivered the sanctioned way (as 0005): a new column, then a NEW generated-replace region equal to `persistence.ledger_sql.render_replace_region()` (the per-type
-- presence rules now include `acquired_on`: FORBIDDEN except OPTIONAL on OPENING_POSITION and TRANSFER_IN), then two hand-written CHECKs that FIELD_RULES cannot state.
-- No trigger function is replaced here, so no search_path pin or rename guard is touched. Migrations 0001 to 0013 are not edited.
ALTER TABLE ledger_event ADD COLUMN acquired_on date NULL;
-- BEGIN GENERATED-REPLACE: persistence.ledger_sql.render_replace_region (do not edit)
ALTER TABLE ledger_event
    DROP CONSTRAINT ledger_event_type_valid,
    DROP CONSTRAINT ledger_event_fields_buy,
    DROP CONSTRAINT ledger_event_fields_sell,
    DROP CONSTRAINT ledger_event_fields_dividend,
    DROP CONSTRAINT ledger_event_fields_interest,
    DROP CONSTRAINT ledger_event_fields_fee,
    DROP CONSTRAINT ledger_event_fields_tax,
    DROP CONSTRAINT ledger_event_fields_deposit,
    DROP CONSTRAINT ledger_event_fields_withdrawal,
    DROP CONSTRAINT ledger_event_fields_transfer_in,
    DROP CONSTRAINT ledger_event_fields_transfer_out,
    DROP CONSTRAINT ledger_event_fields_split,
    DROP CONSTRAINT ledger_event_fields_interest_charged,
    DROP CONSTRAINT ledger_event_fields_currency_conversion,
    DROP CONSTRAINT ledger_event_fields_opening_position,
    DROP CONSTRAINT ledger_event_fields_opening_cash,
    DROP CONSTRAINT ledger_event_fields_reversal,
    DROP CONSTRAINT ledger_event_transfer_shape,
    DROP CONSTRAINT ledger_event_internal_transfer_in_no_cost_basis,
    ADD CONSTRAINT ledger_event_type_valid CHECK (event_type IN ('BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TAX', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER_IN', 'TRANSFER_OUT', 'SPLIT', 'INTEREST_CHARGED', 'CURRENCY_CONVERSION', 'OPENING_POSITION', 'OPENING_CASH', 'REVERSAL')),
    ADD CONSTRAINT ledger_event_fields_buy CHECK (event_type <> 'BUY' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_sell CHECK (event_type <> 'SELL' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_dividend CHECK (event_type <> 'DIVIDEND' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_interest CHECK (event_type <> 'INTEREST' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_fee CHECK (event_type <> 'FEE' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_tax CHECK (event_type <> 'TAX' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_deposit CHECK (event_type <> 'DEPOSIT' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_withdrawal CHECK (event_type <> 'WITHDRAWAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_transfer_in CHECK (event_type <> 'TRANSFER_IN' OR (bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_transfer_out CHECK (event_type <> 'TRANSFER_OUT' OR (cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_split CHECK (event_type <> 'SPLIT' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NOT NULL AND split_old IS NOT NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_interest_charged CHECK (event_type <> 'INTEREST_CHARGED' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_currency_conversion CHECK (event_type <> 'CURRENCY_CONVERSION' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NOT NULL AND bought_currency IS NOT NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_opening_position CHECK (event_type <> 'OPENING_POSITION' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_opening_cash CHECK (event_type <> 'OPENING_CASH' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_fields_reversal CHECK (event_type <> 'REVERSAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NOT NULL AND corrects_event_id IS NULL AND acquired_on IS NULL)),
    ADD CONSTRAINT ledger_event_transfer_shape CHECK (event_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT') OR ((listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL) OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL))),
    ADD CONSTRAINT ledger_event_internal_transfer_in_no_cost_basis CHECK (event_type <> 'TRANSFER_IN' OR counterparty_account_id IS NULL OR cost_basis IS NULL);
-- END GENERATED-REPLACE
-- The two rules a presence table cannot state (they mirror LedgerEvent._validate_values and _validate_transfer_shape):
ALTER TABLE ledger_event
    ADD CONSTRAINT ledger_event_acquired_on_not_after_event_date CHECK (acquired_on IS NULL OR acquired_on <= event_date),
    ADD CONSTRAINT ledger_event_acquired_on_external_security_in CHECK (acquired_on IS NULL OR event_type = 'OPENING_POSITION' OR (event_type = 'TRANSFER_IN' AND counterparty_account_id IS NULL AND listing_id IS NOT NULL));
