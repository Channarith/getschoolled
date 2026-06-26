-- Login security: audit trail, 2FA, OAuth subjects, passkeys (Postgres target).

CREATE TABLE IF NOT EXISTS login_events (
    id           BIGSERIAL PRIMARY KEY,
    account_id   TEXT NOT NULL,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    success      BOOLEAN NOT NULL DEFAULT TRUE,
    ip           TEXT NOT NULL DEFAULT '',
    user_agent   TEXT NOT NULL DEFAULT '',
    country_hint TEXT NOT NULL DEFAULT '',
    method       TEXT NOT NULL DEFAULT 'password'
);

CREATE INDEX IF NOT EXISTS idx_login_events_account ON login_events(account_id, ts DESC);

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS totp_secret TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS oauth_subject TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS passkey_credentials (
    account_id     TEXT NOT NULL,
    credential_id  TEXT NOT NULL,
    public_key     TEXT NOT NULL DEFAULT '',
    sign_count     INTEGER NOT NULL DEFAULT 0,
    label          TEXT NOT NULL DEFAULT 'Passkey',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at   TIMESTAMPTZ,
    PRIMARY KEY (account_id, credential_id)
);
