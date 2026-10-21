-- Durable catalog acquisition, provenance, and review workflow.
-- PostgreSQL is the system of record; workers claim jobs with SKIP LOCKED.

CREATE TABLE IF NOT EXISTS catalog_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    parent_id UUID REFERENCES catalog_categories(id) ON DELETE SET NULL,
    blueprint JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE courses ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'published'
    CHECK (lifecycle_state IN ('staged', 'approved', 'published', 'rejected', 'superseded'));
ALTER TABLE courses ADD COLUMN IF NOT EXISTS source_fingerprint TEXT;
ALTER TABLE programs ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'published'
    CHECK (lifecycle_state IN ('staged', 'approved', 'published', 'rejected', 'superseded'));
ALTER TABLE programs ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES catalog_categories(id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_source_fingerprint
    ON courses(source_fingerprint) WHERE source_fingerprint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_courses_catalog_search
    ON courses USING GIN (to_tsvector('simple', title || ' ' || description));
CREATE INDEX IF NOT EXISTS idx_programs_category_state
    ON programs(category_id, lifecycle_state);

CREATE TABLE IF NOT EXISTS catalog_source_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_uri TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    license TEXT,
    rights_assertion TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    byte_size BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_uri, sha256)
);

CREATE TABLE IF NOT EXISTS catalog_provenance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_asset_id UUID NOT NULL REFERENCES catalog_source_assets(id) ON DELETE CASCADE,
    program_id UUID REFERENCES programs(id) ON DELETE SET NULL,
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    transformation TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    score NUMERIC,
    reviewer TEXT,
    findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS catalog_acquisition_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT NOT NULL UNIQUE,
    category_slug TEXT NOT NULL,
    source_asset_id UUID REFERENCES catalog_source_assets(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'processing', 'retry', 'completed', 'dead_letter', 'rejected')),
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_by TEXT,
    claim_expires_at TIMESTAMPTZ,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_catalog_acquisition_claim
    ON catalog_acquisition_jobs(category_slug, state, priority DESC, available_at);
