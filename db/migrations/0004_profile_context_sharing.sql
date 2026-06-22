-- Profile context sharing prep.
-- Stores per-class learner context and scoped share grants for future
-- database-backed integrations. References are TEXT to support today's opaque
-- service ids and future UUID account/profile tables without a data fork.

CREATE TABLE IF NOT EXISTS student_class_contexts (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref    TEXT NOT NULL,
    student_ref    TEXT NOT NULL,
    course_id      TEXT NOT NULL,
    class_id       TEXT,
    title          TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    skills         TEXT[] NOT NULL DEFAULT '{}',
    source         TEXT NOT NULL DEFAULT 'class',
    external_refs  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_class_contexts_student
    ON student_class_contexts (student_ref, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_class_contexts_class
    ON student_class_contexts (student_ref, class_id)
    WHERE class_id IS NOT NULL AND class_id <> '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_class_contexts_course_without_class
    ON student_class_contexts (student_ref, course_id)
    WHERE class_id IS NULL OR class_id = '';

CREATE TABLE IF NOT EXISTS profile_share_grants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_ref  TEXT NOT NULL,
    student_ref  TEXT NOT NULL,
    integration  TEXT NOT NULL DEFAULT '',
    scopes       TEXT[] NOT NULL DEFAULT '{}',
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profile_share_grants_student
    ON profile_share_grants (student_ref, expires_at DESC);

CREATE INDEX IF NOT EXISTS idx_profile_share_grants_active
    ON profile_share_grants (account_ref, student_ref, expires_at)
    WHERE revoked = FALSE;
