-- Course catalog and dynamic training programs (schema-of-record).
-- Programs -> Courses -> Modules; modules reference CMS decks/scenes by id.
-- The curriculum service currently uses an in-memory/JSON CatalogStore; this is
-- the contract for the eventual Postgres backend.

CREATE TABLE IF NOT EXISTS courses (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title             TEXT NOT NULL,
    subject           TEXT NOT NULL DEFAULT 'general',
    language          TEXT NOT NULL DEFAULT 'en',
    description       TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL DEFAULT 'unvalidated'
                      CHECK (validation_status IN ('unvalidated', 'validated', 'flagged')),
    version           INTEGER NOT NULL DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS modules (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id  UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    deck_id    TEXT,   -- CMS deck reference
    scene_id   TEXT,   -- AOEPLX scene reference
    ordering   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_modules_course ON modules (course_id, ordering);

CREATE TABLE IF NOT EXISTS programs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          TEXT NOT NULL,
    audience       TEXT NOT NULL DEFAULT '',
    description    TEXT NOT NULL DEFAULT '',
    adaptive_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ordered membership of courses within a program.
CREATE TABLE IF NOT EXISTS program_courses (
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    course_id  UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    ordering   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (program_id, course_id)
);

-- Optional: student progress through a program (enrollments).
CREATE TABLE IF NOT EXISTS enrollments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id  UUID NOT NULL,
    program_id  UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    progress    JSONB NOT NULL DEFAULT '{}'::jsonb,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments (student_id);
