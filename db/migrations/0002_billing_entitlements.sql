-- Billing & entitlements schema.
-- Backs services/billing: plans, subscriptions, credits, metered usage, and the
-- single entitlements API canStart(classType, language, features).

CREATE TABLE IF NOT EXISTS accounts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'free',  -- free | basic | pro | premium
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    plan                TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    external_ref        TEXT,                  -- Stripe subscription id (cloud)
    current_period_end  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS credits (
    account_id  UUID PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    balance     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usage_events (
    id          BIGSERIAL PRIMARY KEY,
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,                 -- live_minutes | language | recording
    quantity    INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entitlements (
    plan        TEXT PRIMARY KEY,
    solo        BOOLEAN NOT NULL DEFAULT FALSE,
    max_langs   INTEGER NOT NULL DEFAULT 1,
    recordings  BOOLEAN NOT NULL DEFAULT FALSE,
    cross_class BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO entitlements (plan, solo, max_langs, recordings, cross_class) VALUES
    ('free',    FALSE, 1,  FALSE, FALSE),
    ('basic',   FALSE, 5,  FALSE, FALSE),
    ('pro',     TRUE,  26, TRUE,  TRUE),
    ('premium', TRUE,  26, TRUE,  TRUE)
ON CONFLICT (plan) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_usage_account ON usage_events(account_id);
