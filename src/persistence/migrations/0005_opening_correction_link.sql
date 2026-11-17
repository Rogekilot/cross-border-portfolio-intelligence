-- CP1B-6: OPENING_POSITION and OPENING_CASH may now carry corrects_event_id, so a corrected
-- snapshot keeps its audit link (P9). This is a FIELD_RULES change, delivered the sanctioned
-- way: a NEW migration that replaces the generated per-type constraints. Migration 0002 is
-- frozen and is NOT edited; the drift test compares FIELD_RULES with the region of the
-- latest migration that has one (this file), so the next rule change is another new file.
-- Re-adding the constraints validates every existing row against them.
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
    ADD CONSTRAINT ledger_event_fields_buy CHECK (event_type <> 'BUY' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_sell CHECK (event_type <> 'SELL' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_dividend CHECK (event_type <> 'DIVIDEND' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_interest CHECK (event_type <> 'INTEREST' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_fee CHECK (event_type <> 'FEE' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_tax CHECK (event_type <> 'TAX' OR (quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_deposit CHECK (event_type <> 'DEPOSIT' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_withdrawal CHECK (event_type <> 'WITHDRAWAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_transfer_in CHECK (event_type <> 'TRANSFER_IN' OR (bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_transfer_out CHECK (event_type <> 'TRANSFER_OUT' OR (cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_split CHECK (event_type <> 'SPLIT' OR (listing_id IS NOT NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NOT NULL AND split_old IS NOT NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_interest_charged CHECK (event_type <> 'INTEREST_CHARGED' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_currency_conversion CHECK (event_type <> 'CURRENCY_CONVERSION' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NOT NULL AND bought_currency IS NOT NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_opening_position CHECK (event_type <> 'OPENING_POSITION' OR (listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_opening_cash CHECK (event_type <> 'OPENING_CASH' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_fields_reversal CHECK (event_type <> 'REVERSAL' OR (listing_id IS NULL AND quantity IS NULL AND amount IS NULL AND cost_basis IS NULL AND bought_amount IS NULL AND bought_currency IS NULL AND split_new IS NULL AND split_old IS NULL AND counterparty_account_id IS NULL AND settlement_date IS NULL AND ex_date IS NULL AND reverses_event_id IS NOT NULL AND corrects_event_id IS NULL)),
    ADD CONSTRAINT ledger_event_transfer_shape CHECK (event_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT') OR ((listing_id IS NOT NULL AND quantity IS NOT NULL AND amount IS NULL) OR (listing_id IS NULL AND quantity IS NULL AND amount IS NOT NULL AND cost_basis IS NULL))),
    ADD CONSTRAINT ledger_event_internal_transfer_in_no_cost_basis CHECK (event_type <> 'TRANSFER_IN' OR counterparty_account_id IS NULL OR cost_basis IS NULL);
-- END GENERATED-REPLACE
