-- Facet counts without scanning 1M rows per request: a small table refreshed by
-- catalog_refresh_facets() (called at the end of every import and by an hourly job).

CREATE TABLE IF NOT EXISTS catalog_facets (
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    n     BIGINT NOT NULL,
    PRIMARY KEY (kind, value)
);

CREATE OR REPLACE FUNCTION catalog_refresh_facets() RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM catalog_facets;
    INSERT INTO catalog_facets SELECT 'category', category, count(*) FROM catalog_courses
        WHERE publish_state = 'published' AND category <> '' GROUP BY category;
    INSERT INTO catalog_facets SELECT 'language', language, count(*) FROM catalog_courses
        WHERE publish_state = 'published' GROUP BY language;
    INSERT INTO catalog_facets SELECT 'level', level, count(*) FROM catalog_courses
        WHERE publish_state = 'published' GROUP BY level;
    INSERT INTO catalog_facets SELECT 'media_format', media_format, count(*) FROM catalog_courses
        WHERE publish_state = 'published' GROUP BY media_format;
    INSERT INTO catalog_facets SELECT 'quality_tier', quality_tier::text, count(*) FROM catalog_courses
        WHERE publish_state = 'published' GROUP BY quality_tier;
END $$;
