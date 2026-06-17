-- AOEP initial schema (phase0).
-- Covers identity, classes, consent/compliance, and billing/entitlements.
-- pgvector is enabled for embeddings used by RAG and the mastery/profile store.
-- Runs identically against local Postgres and managed cloud Postgres.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  TEXT NOT NULL,
    region        TEXT NOT NULL DEFAULT 'other'
                  CHECK (region IN ('us', 'eu', 'us_il', 'other')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Classes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS class_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_type  TEXT NOT NULL CHECK (class_type IN ('solo', 'group')),
    title       TEXT NOT NULL,
    language    TEXT NOT NULL DEFAULT 'en',
    persona     TEXT NOT NULL DEFAULT 'friendly',
    room        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Consent / compliance (FERPA / GDPR / BIPA)
-- Biometric features are gated behind explicit, auditable consent. Face
-- embeddings are stored encrypted and are deletable on request.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consent_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    scope           TEXT NOT NULL CHECK (scope IN (
                        'face_recognition', 'attention_tracking',
                        'recording', 'cross_class_memory')),
    granted         BOOLEAN NOT NULL,
    region          TEXT NOT NULL DEFAULT 'other',
    written         BOOLEAN NOT NULL DEFAULT FALSE,   -- BIPA written-consent basis
    retention_days  INTEGER,                          -- retention schedule
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_consent_student_scope
    ON consent_records (student_id, scope, recorded_at DESC);

-- Encrypted face embeddings, opt-in, never leave the configured boundary.
CREATE TABLE IF NOT EXISTS face_embeddings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    -- Encrypted at rest; the raw vector is decrypted only inside the boundary.
    embedding    BYTEA NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    delete_after TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Mastery / learning-behavior signals (drives adaptive pacing)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mastery (
    student_id  UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    score       REAL NOT NULL DEFAULT 0 CHECK (score >= 0 AND score <= 1),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, topic)
);

-- Curriculum chunks + embeddings for pgvector RAG retrieval.
CREATE TABLE IF NOT EXISTS curriculum_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id      TEXT NOT NULL,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(768)
);
CREATE INDEX IF NOT EXISTS idx_curriculum_doc ON curriculum_chunks (doc_id);

-- ---------------------------------------------------------------------------
-- Billing / entitlements
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id            UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    tier                  TEXT NOT NULL DEFAULT 'free'
                          CHECK (tier IN ('free', 'basic', 'pro', 'premium')),
    status                TEXT NOT NULL DEFAULT 'active',
    provider              TEXT NOT NULL DEFAULT 'sandbox',  -- 'stripe' | 'sandbox'
    provider_customer_id  TEXT,
    current_period_end    TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_student ON subscriptions (student_id);

CREATE TABLE IF NOT EXISTS credits (
    student_id  UUID PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    balance     INTEGER NOT NULL DEFAULT 0
);

-- Metered usage for GPU-heavy live minutes, extra languages, recordings, etc.
CREATE TABLE IF NOT EXISTS usage_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id  UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,
    quantity    NUMERIC NOT NULL DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_student_metric
    ON usage_events (student_id, metric, recorded_at DESC);
