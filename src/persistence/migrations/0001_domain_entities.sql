-- CP1-B step 2, migration 1: the CP1-A entities the ledger references.
-- Mirrors src/domain/portfolio.py and src/domain/instrument.py field for field.
-- Canonical keys are immutable internal UUIDs (PD-0021 §1). FIGI, MIC, ticker and
-- exchange are ordinary attributes: no UNIQUE constraint and no key role (Option C
-- is not adopted, PD-0021 §1.3). Names are unqualified; they land in the first
-- schema on the connection's search_path.
-- No account-level currency column: currency belongs to each cash fact (domain.cash).

CREATE TABLE app_user (
    user_id uuid PRIMARY KEY
);

CREATE TABLE portfolio (
    portfolio_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app_user (user_id),
    reporting_currency text NOT NULL CHECK (reporting_currency ~ '^[A-Z]{3}$')
);

CREATE TABLE account (
    account_id uuid PRIMARY KEY,
    portfolio_id uuid NOT NULL REFERENCES portfolio (portfolio_id),
    name text NOT NULL
);

CREATE TABLE issuer (
    issuer_id uuid PRIMARY KEY,
    name text NOT NULL,
    issuer_domicile text NULL
);

CREATE TABLE instrument (
    instrument_id uuid PRIMARY KEY,
    issuer_id uuid NOT NULL REFERENCES issuer (issuer_id),
    security_type text NOT NULL CHECK (security_type IN ('COMMON_STOCK', 'ETF'))
);

CREATE TABLE listing (
    listing_id uuid PRIMARY KEY,
    instrument_id uuid NOT NULL REFERENCES instrument (instrument_id),
    mic text NOT NULL,
    exchange text NOT NULL,
    ticker text NOT NULL,
    trading_currency text NOT NULL CHECK (trading_currency ~ '^[A-Z]{3}$'),
    figi text NULL,
    is_active boolean NOT NULL
);
