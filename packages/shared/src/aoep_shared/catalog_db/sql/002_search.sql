-- Search (v1): full text (language-neutral 'simple' config: the catalog spans 27 languages incl.
-- Khmer and Thai, so no stemming) plus trigram for prefix/typo-tolerant title lookups.
-- pg_trgm is a trusted extension on PostgreSQL 13+, so the database owner can create it.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE catalog_courses
    ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (catalog_tsv(title, preview, description, tags)) STORED;

CREATE INDEX IF NOT EXISTS ix_cc_fts ON catalog_courses USING gin (fts);
CREATE INDEX IF NOT EXISTS ix_cc_title_trgm ON catalog_courses USING gin (title gin_trgm_ops);
