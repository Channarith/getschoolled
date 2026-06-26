-- Login audit + billing profile (Postgres target schema; identity hydrates when wired).

CREATE TABLE IF NOT EXISTS login_events (
    id          BIGSERIAL PRIMARY KEY,
    account_id  TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    success     BOOLEAN NOT NULL DEFAULT TRUE,
    ip          TEXT NOT NULL DEFAULT '',
    user_agent  TEXT NOT NULL DEFAULT '',
    country_hint TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_login_events_account ON login_events(account_id, ts DESC);

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS membership_class TEXT NOT NULL DEFAULT 'standard';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS card_last4 TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS billing_validated_at TIMESTAMPTZ;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS login_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS billing_addresses (
    account_id  TEXT PRIMARY KEY,
    line1       TEXT NOT NULL,
    line2       TEXT NOT NULL DEFAULT '',
    city        TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL,
    country     CHAR(2) NOT NULL DEFAULT 'US',
    phone       TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
