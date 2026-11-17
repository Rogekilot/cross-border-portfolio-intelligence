-- CP7-B: account credentials/sessions and explicitly synthetic saved portfolios.
-- Existing portfolio/account/append-only ledger remain the financial source of truth.
CREATE TABLE web_identity (
    user_id uuid PRIMARY KEY REFERENCES app_user (user_id),
    username text NOT NULL UNIQUE CHECK (username ~ '^[a-z][a-z0-9_.-]{2,31}$'),
    password_hash text NOT NULL CHECK (length(password_hash) BETWEEN 80 AND 256),
    created_at timestamptz NOT NULL
);
CREATE TABLE web_session (
    token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES web_identity (user_id),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at)
);
CREATE INDEX web_session_user ON web_session (user_id, created_at);
CREATE TABLE web_auth_rate (
    bucket_hash text PRIMARY KEY CHECK (bucket_hash ~ '^[0-9a-f]{64}$'),
    window_start timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 1000)
);
CREATE TABLE web_saved_sandbox (
    portfolio_id uuid PRIMARY KEY REFERENCES portfolio (portfolio_id),
    mode text NOT NULL CHECK (mode = 'LOCAL_SYNTHETIC_ACCOUNT'),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    request_json text NOT NULL CHECK (octet_length(request_json) <= 32768),
    snapshot_json text NOT NULL CHECK (octet_length(snapshot_json) <= 4000000),
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    ledger_version bigint NOT NULL CHECK (ledger_version > 0),
    created_at timestamptz NOT NULL
);
