-- Consent & compliance schema (FERPA / GDPR / BIPA).
-- pgvector is enabled here for face embeddings and curriculum RAG vectors.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS students (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  TEXT NOT NULL,
    region        TEXT NOT NULL DEFAULT 'US',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    scope           TEXT NOT NULL,            -- e.g. 'biometric', 'recording'
    granted         BOOLEAN NOT NULL DEFAULT FALSE,
    policy          TEXT NOT NULL DEFAULT 'GDPR',
    retention_days  INTEGER NOT NULL DEFAULT 30,
    granted_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);

-- Face embeddings are stored encrypted and only with biometric consent.
CREATE TABLE IF NOT EXISTS face_embeddings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    embedding    vector(512),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    delete_after TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_consents_student ON consents(student_id);
