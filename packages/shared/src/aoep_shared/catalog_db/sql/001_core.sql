-- Catalog core (v1): courses (multi-lesson), modules (lessons/decks), sources, programs.
-- Metadata only. Deck bodies live in object storage as content-addressed gzip JSON
-- (courses/<aa>/<sha256>.json.gz); catalog_modules.deck_sha256 points at them.
-- Sized for 1,000,000 courses x ~8 modules (8M rows). Plain CREATE INDEX (no CONCURRENTLY)
-- because the migration runner wraps each file in a transaction; run on an empty database
-- or in a maintenance window.

CREATE OR REPLACE FUNCTION catalog_tsv(title text, preview text, description text, tags text[])
RETURNS tsvector LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT setweight(to_tsvector('simple', coalesce(title, '')), 'A')
      || setweight(to_tsvector('simple', coalesce(preview, '') || ' ' || coalesce(description, '')), 'B')
      || setweight(to_tsvector('simple', coalesce(array_to_string(tags, ' '), '')), 'C')
$$;

CREATE TABLE IF NOT EXISTS catalog_courses (
    course_id         TEXT PRIMARY KEY,
    -- sha256 of the identifying content (title, language, subject, ordered module deck refs).
    -- UNIQUE: re-posting the same course returns the existing row (idempotent upsert).
    content_hash      TEXT NOT NULL,
    title             TEXT NOT NULL,
    subject           TEXT NOT NULL DEFAULT 'general',
    category          TEXT NOT NULL DEFAULT '',
    language          TEXT NOT NULL DEFAULT 'en',
    audio_language    TEXT NOT NULL DEFAULT '',
    description       TEXT NOT NULL DEFAULT '',
    preview           TEXT NOT NULL DEFAULT '',
    level             TEXT NOT NULL DEFAULT 'beginner',
    media_format      TEXT NOT NULL DEFAULT 'video',
    delivery_mode     TEXT NOT NULL DEFAULT 'ai',
    access_tier       TEXT NOT NULL DEFAULT 'free',
    maturity_rating   TEXT NOT NULL DEFAULT 'all',
    hands_on          BOOLEAN NOT NULL DEFAULT false,
    core_skill        BOOLEAN NOT NULL DEFAULT false,
    duration_min      INTEGER NOT NULL DEFAULT 0,
    popularity        BIGINT NOT NULL DEFAULT 0,
    price_usd         NUMERIC(10, 2) NOT NULL DEFAULT 0,
    tags              TEXT[] NOT NULL DEFAULT '{}',
    audiences         TEXT[] NOT NULL DEFAULT '{}',
    -- 0 machine-generated, 1 auto-validated, 2 human-reviewed (only staff set 2)
    quality_tier      SMALLINT NOT NULL DEFAULT 0 CHECK (quality_tier IN (0, 1, 2)),
    -- product_safe: usable commercially; share_alike: only with attribution + same license
    -- (off by default until legal review); research_only / unknown never serve to customers.
    license_tier      TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (license_tier IN ('product_safe', 'share_alike', 'research_only', 'unknown', 'owned')),
    publish_state     TEXT NOT NULL DEFAULT 'published'
                      CHECK (publish_state IN ('draft', 'published', 'quarantined', 'retired')),
    validation_status TEXT NOT NULL DEFAULT 'unvalidated',
    version           INTEGER NOT NULL DEFAULT 1,
    source_fingerprint TEXT NOT NULL DEFAULT '',
    source            TEXT NOT NULL DEFAULT '',
    created_at        DOUBLE PRECISION NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The full pydantic Course dump: API responses stay backward compatible.
    data              JSONB NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_catalog_courses_content_hash ON catalog_courses (content_hash);

-- Browse paths. Every list is served by an index in the sort order it needs. Keyset pagination
-- uses (popularity, course_id) DESC for BOTH columns so a row comparison
-- (popularity, course_id) < (x, y) walks the index instead of re-scanning from the top.
-- Partial on published so retired/quarantined rows cost nothing.
CREATE INDEX IF NOT EXISTS ix_cc_pop ON catalog_courses (popularity DESC, course_id DESC)
    WHERE publish_state = 'published';
CREATE INDEX IF NOT EXISTS ix_cc_cat_pop ON catalog_courses (lower(category), popularity DESC, course_id DESC)
    WHERE publish_state = 'published';
CREATE INDEX IF NOT EXISTS ix_cc_lang_pop ON catalog_courses (language, popularity DESC, course_id DESC)
    WHERE publish_state = 'published';
CREATE INDEX IF NOT EXISTS ix_cc_source_pop ON catalog_courses (source, popularity DESC, course_id DESC)
    WHERE publish_state = 'published' AND source <> '';
CREATE INDEX IF NOT EXISTS ix_cc_new ON catalog_courses (created_at DESC, course_id DESC)
    WHERE publish_state = 'published';
CREATE INDEX IF NOT EXISTS ix_cc_kids_pop ON catalog_courses (popularity DESC, course_id DESC)
    WHERE publish_state = 'published' AND maturity_rating = 'kids';
CREATE INDEX IF NOT EXISTS ix_cc_free_pop ON catalog_courses (popularity DESC, course_id DESC)
    WHERE publish_state = 'published' AND access_tier = 'free';
CREATE INDEX IF NOT EXISTS ix_cc_handson_pop ON catalog_courses (popularity DESC, course_id DESC)
    WHERE publish_state = 'published' AND hands_on;
CREATE INDEX IF NOT EXISTS ix_cc_fingerprint ON catalog_courses (source_fingerprint)
    WHERE source_fingerprint <> '';
CREATE INDEX IF NOT EXISTS ix_cc_tags ON catalog_courses USING gin (tags);

-- Lessons/decks of a course, in order. ~8 per course.
CREATE TABLE IF NOT EXISTS catalog_modules (
    course_id   TEXT NOT NULL REFERENCES catalog_courses (course_id) ON DELETE CASCADE,
    ordering    INTEGER NOT NULL,
    module_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    deck_id     TEXT,
    scene_id    TEXT,
    deck_sha256 TEXT,          -- content address of the body in object storage
    PRIMARY KEY (course_id, ordering)
);
CREATE INDEX IF NOT EXISTS ix_cm_deck_sha ON catalog_modules (deck_sha256) WHERE deck_sha256 IS NOT NULL;

-- Provenance per lesson: where it came from and under which license. Never trust seed text:
-- license_tier is what the verified license maps to (see aoep_shared.catalog_db.compose).
CREATE TABLE IF NOT EXISTS catalog_sources (
    course_id     TEXT NOT NULL REFERENCES catalog_courses (course_id) ON DELETE CASCADE,
    deck_sha256   TEXT NOT NULL,
    source_url    TEXT NOT NULL DEFAULT '',
    canonical_url TEXT NOT NULL DEFAULT '',
    license       TEXT NOT NULL DEFAULT '',
    license_tier  TEXT NOT NULL DEFAULT 'unknown',
    attribution   JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (course_id, deck_sha256)
);

-- Translation index (bodies stay in object storage). source_sha256 ties a translation to the
-- exact English it was made from, so stale translations are detectable.
CREATE TABLE IF NOT EXISTS catalog_translations (
    course_id        TEXT NOT NULL REFERENCES catalog_courses (course_id) ON DELETE CASCADE,
    language         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'machine' CHECK (status IN ('machine', 'reviewed', 'rejected', 'stale')),
    source_sha256    TEXT NOT NULL DEFAULT '',
    pipeline_version TEXT NOT NULL DEFAULT '',
    object_key       TEXT NOT NULL DEFAULT '',
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, language)
);
CREATE INDEX IF NOT EXISTS ix_ct_lang_status ON catalog_translations (language, status);

CREATE TABLE IF NOT EXISTS catalog_programs (
    program_id TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    data       JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
