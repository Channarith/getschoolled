"""PostgreSQL implementation of the course catalog (selected by CATALOG_DATABASE_URL).

Why it exists: the in-memory CatalogStore keeps every course in each replica's RAM and rewrites a
whole JSON file per write, so replicas diverge and the ceiling is tens of thousands of courses.
This store keeps metadata in Postgres (shared by all replicas), serves every list through an
index (keyset pagination), and never loads the whole catalog:

  * list_courses()      -> a bounded "hot set" (CATALOG_LIST_CAP, default 2000) for the older
                           code paths that wanted everything; real browsing uses page_courses().
  * page_courses()      -> keyset pagination on (popularity, course_id) DESC; text search uses
                           ranked offset pages (capped).
  * create_course()     -> idempotent: the same content returns the existing course.
  * reads are cached for a few seconds per replica; a write drops the local entry, and other
    replicas converge within the TTL (the database is always the truth, never diverging).

The public surface matches curriculum.catalog.CatalogStore so main.py needs no branching beyond
the paged endpoints. psycopg is imported lazily: without CATALOG_DATABASE_URL nothing here runs.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from aoep_shared.catalog_db.compose import SERVABLE_TIERS, deck_sha_from_deck_id

from .catalog import Course, Program, course_hash, decode_cursor, encode_cursor

HOT_CAP_DEFAULT = 2000
COUNT_CAP_DEFAULT = 10_000
MAX_PAGE = 200
MAX_SEARCH_OFFSET = 5_000


def _lower(value: Optional[str]) -> str:
    return (value or "").strip().lower()


class PgCatalogStore:
    paged = True  # main.py switches to the paged endpoints when this is true

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 6,
        hot_cap: Optional[int] = None,
        count_cap: Optional[int] = None,
        cache_ttl: Optional[float] = None,
        allow_share_alike: Optional[bool] = None,
        pool: Any = None,
    ) -> None:
        self.dsn = dsn
        self.hot_cap = hot_cap or int(os.environ.get("CATALOG_LIST_CAP", HOT_CAP_DEFAULT))
        self.count_cap = count_cap or int(os.environ.get("CATALOG_COUNT_CAP", COUNT_CAP_DEFAULT))
        self.cache_ttl = float(os.environ.get("CATALOG_CACHE_TTL", "10")) if cache_ttl is None else cache_ttl
        self.search_candidates = int(os.environ.get("CATALOG_SEARCH_CANDIDATES", "500"))
        self.rails_ttl = float(os.environ.get("CATALOG_RAILS_TTL", "60")) if cache_ttl is None else cache_ttl * 6
        self._rails: Dict[Tuple[bool, int], Tuple[float, List[dict]]] = {}
        self.allow_share_alike = (
            os.environ.get("CATALOG_ALLOW_SHARE_ALIKE", "0") == "1" if allow_share_alike is None else allow_share_alike
        )
        self._cache: Dict[str, Tuple[float, Optional[Course]]] = {}
        self._cache_lock = threading.Lock()
        if pool is not None:
            self.pool = pool
        else:
            try:
                from psycopg_pool import ConnectionPool
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("psycopg_pool is not installed: pip install 'psycopg[binary,pool]'") from exc
            self.pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True, timeout=10)

    # ------------------------------------------------------------------ helpers
    def close(self) -> None:
        self.pool.close()

    def _cached(self, course_id: str) -> Tuple[bool, Optional[Course]]:
        if self.cache_ttl <= 0:
            return False, None
        with self._cache_lock:
            hit = self._cache.get(course_id)
            if hit and hit[0] > time.monotonic():
                return True, hit[1]
        return False, None

    def _remember(self, course_id: str, course: Optional[Course]) -> None:
        if self.cache_ttl <= 0:
            return
        with self._cache_lock:
            if len(self._cache) > 5000:
                self._cache.clear()
            self._cache[course_id] = (time.monotonic() + self.cache_ttl, course)

    def _forget(self, course_id: str) -> None:
        with self._cache_lock:
            self._cache.pop(course_id, None)

    @staticmethod
    def _course(row_data: Any) -> Course:
        data = row_data if isinstance(row_data, dict) else json.loads(row_data)
        return Course(**data)

    @staticmethod
    def _tag_value(tags: List[str], prefix: str) -> Optional[str]:
        for t in tags:
            if t.startswith(prefix):
                return t[len(prefix):]
        return None

    def _license_and_state(self, course: Course) -> Tuple[str, int, str]:
        """(license_tier, quality_tier, publish_state). Non-servable licenses are quarantined here,
        so even a buggy importer cannot make a non-commercial lesson visible to customers."""
        tier = self._tag_value(course.tags, "license:") or "owned"
        quality = 0
        q = self._tag_value(course.tags, "tier:")
        if q is not None and q.isdigit() and int(q) in (0, 1, 2):
            quality = int(q)
        servable = tier in SERVABLE_TIERS or (self.allow_share_alike and tier == "share_alike")
        state = {"draft": "draft", "retired": "retired", "quarantined": "quarantined"}.get(
            (course.lifecycle_state or "published").lower(), "published"
        )
        if not servable:
            state = "quarantined"
        return tier if tier in {"owned", "product_safe", "share_alike", "research_only", "unknown"} else "unknown", quality, state

    @staticmethod
    def _content_hash(course: Course) -> str:
        return course_hash(course)

    # ------------------------------------------------------------------ courses
    def _row(self, course: Course) -> Dict[str, Any]:
        """The catalog_courses column values for a course (also used by bulk_insert)."""
        h = self._content_hash(course)
        tier, quality, state = self._license_and_state(course)
        data = course.model_dump(mode="json")
        return {
            "course_id": course.course_id, "content_hash": h, "title": course.title,
            "subject": course.subject, "category": course.category, "language": _lower(course.language) or "en",
            "audio_language": _lower(course.audio_language), "description": course.description,
            "preview": course.preview, "level": _lower(course.level), "media_format": _lower(course.media_format),
            "delivery_mode": _lower(course.delivery_mode.value), "access_tier": _lower(course.access_tier),
            "maturity_rating": _lower(course.maturity_rating), "hands_on": course.hands_on,
            "core_skill": course.core_skill, "duration_min": course.duration_min,
            "popularity": course.popularity, "price_usd": course.price_usd,
            "tags": [t.lower() for t in course.tags],
            "audiences": [a.lower() for a in course.audiences], "quality_tier": quality,
            "license_tier": tier, "publish_state": state, "validation_status": course.validation_status,
            "version": course.version, "source_fingerprint": course.source_fingerprint,
            "source": course.source, "created_at": course.created_at, "data": json.dumps(data),
        }

    @staticmethod
    def _module_rows(course: Course) -> List[tuple]:
        return [
            (course.course_id, i, m.module_id, m.title, m.deck_id, m.scene_id, deck_sha_from_deck_id(m.deck_id))
            for i, m in enumerate(sorted(course.modules, key=lambda m: m.order))
        ]

    def create_course(self, course: Course, *, dedupe: bool = True) -> Course:
        """Insert or replace by course_id; identical content (same hash) returns the existing course."""
        row = self._row(course)
        h = row["content_hash"]
        cols = list(row)
        placeholders = ", ".join(f"%({c})s::jsonb" if c == "data" else f"%({c})s" for c in cols)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("course_id", "created_at"))
        with self.pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (h,))
                    cur.execute("SELECT course_id, data FROM catalog_courses WHERE content_hash = %s", (h,))
                    hit = cur.fetchone()
                    if hit and hit[0] != course.course_id:
                        return self._course(hit[1])  # same content under another id: idempotent
                    cur.execute(
                        f"INSERT INTO catalog_courses ({', '.join(cols)}, updated_at) "
                        f"VALUES ({placeholders}, now()) "
                        f"ON CONFLICT (course_id) DO UPDATE SET {updates}, updated_at = now()",
                        row,
                    )
                    cur.execute("DELETE FROM catalog_modules WHERE course_id = %s", (course.course_id,))
                    if course.modules:
                        cur.executemany(
                            "INSERT INTO catalog_modules (course_id, ordering, module_id, title, deck_id, scene_id, deck_sha256) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            self._module_rows(course),
                        )
        self._forget(course.course_id)
        return course

    def known_deck_shas(self, shas) -> set:
        """Which of these lesson bodies already belong to a catalog course."""
        wanted = list(dict.fromkeys(shas))
        known: set = set()
        with self.pool.connection() as conn, conn.cursor() as cur:
            for i in range(0, len(wanted), 5000):
                cur.execute(
                    "SELECT deck_sha256 FROM catalog_modules WHERE deck_sha256 = ANY(%s)", (wanted[i:i + 5000],)
                )
                known.update(r[0] for r in cur.fetchall())
        return known

    def upsert_course(self, course: Course) -> Course:
        return self.create_course(course)

    def get_course(self, course_id: str, *, include_hidden: bool = False) -> Optional[Course]:
        """A course by id. Quarantined courses (a license that cannot serve in the product) are
        invisible unless include_hidden=True (admin tooling)."""
        if not include_hidden:
            found, cached = self._cached(course_id)
            if found:
                return cached
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data, publish_state FROM catalog_courses WHERE course_id = %s", (course_id,))
            row = cur.fetchone()
        if row and row[1] == "quarantined" and not include_hidden:
            row = None
        course = self._course(row[0]) if row else None
        if not include_hidden:
            self._remember(course_id, course)
        return course

    def bulk_insert(self, courses: List[Course], sources: Optional[Dict[str, List[dict]]] = None) -> Tuple[int, int]:
        """Fast, idempotent import via COPY. Existing courses (same id OR same content) are left
        untouched. Returns (inserted, skipped). Quarantine rules apply exactly as in create_course.
        sources maps course_id -> [{deck_sha256, source_url, canonical_url, license, license_tier,
        attribution, fetched_at}] for the provenance table."""
        if not courses:
            return 0, 0
        rows = [self._row(c) for c in courses]
        cols = list(rows[0])
        by_id = {c.course_id: c for c in courses}
        with self.pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "CREATE TEMP TABLE _stage_courses (LIKE catalog_courses INCLUDING DEFAULTS) ON COMMIT DROP"
                    )
                    with cur.copy(f"COPY _stage_courses ({', '.join(cols)}) FROM STDIN") as cp:
                        for r in rows:
                            cp.write_row([r[c] for c in cols])
                    cur.execute(
                        f"INSERT INTO catalog_courses ({', '.join(cols)}) SELECT {', '.join(cols)} FROM _stage_courses "
                        "ON CONFLICT DO NOTHING RETURNING course_id"
                    )
                    inserted = {r[0] for r in cur.fetchall()}
                    if inserted:
                        with cur.copy(
                            "COPY catalog_modules (course_id, ordering, module_id, title, deck_id, scene_id, deck_sha256) FROM STDIN"
                        ) as cp:
                            for cid in inserted:
                                for mrow in self._module_rows(by_id[cid]):
                                    cp.write_row(mrow)
                        if sources:
                            with cur.copy(
                                "COPY catalog_sources (course_id, deck_sha256, source_url, canonical_url, license, "
                                "license_tier, attribution, fetched_at) FROM STDIN"
                            ) as cp:
                                for cid in inserted:
                                    for s in sources.get(cid, []):
                                        cp.write_row([
                                            cid, s.get("deck_sha256", ""), s.get("source_url", ""),
                                            s.get("canonical_url", ""), s.get("license", ""),
                                            s.get("license_tier", "unknown"),
                                            json.dumps(s.get("attribution") or {}), s.get("fetched_at", ""),
                                        ])
        return len(inserted), len(rows) - len(inserted)

    def upsert_course(self, course: Course) -> Course:
        return self.create_course(course)

    def get_course(self, course_id: str, *, include_hidden: bool = False) -> Optional[Course]:
        """A course by id. Quarantined courses (a license that cannot serve in the product) are
        invisible unless include_hidden=True (admin tooling)."""
        if not include_hidden:
            found, cached = self._cached(course_id)
            if found:
                return cached
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data, publish_state FROM catalog_courses WHERE course_id = %s", (course_id,))
            row = cur.fetchone()
        if row and row[1] == "quarantined" and not include_hidden:
            row = None
        course = self._course(row[0]) if row else None
        if not include_hidden:
            self._remember(course_id, course)
        return course

    def bulk_insert(self, courses: List[Course], sources: Optional[Dict[str, List[dict]]] = None) -> Tuple[int, int]:
        """Fast, idempotent import via COPY. Existing courses (same id OR same content) are left
        untouched. Returns (inserted, skipped). Quarantine rules apply exactly as in create_course.
        sources maps course_id -> [{deck_sha256, source_url, canonical_url, license, license_tier,
        attribution, fetched_at}] for the provenance table."""
        if not courses:
            return 0, 0
        rows = [self._row(c) for c in courses]
        cols = list(rows[0])
        by_id = {c.course_id: c for c in courses}
        with self.pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "CREATE TEMP TABLE _stage_courses (LIKE catalog_courses INCLUDING DEFAULTS) ON COMMIT DROP"
                    )
                    with cur.copy(f"COPY _stage_courses ({', '.join(cols)}) FROM STDIN") as cp:
                        for r in rows:
                            cp.write_row([r[c] for c in cols])
                    cur.execute(
                        f"INSERT INTO catalog_courses ({', '.join(cols)}) SELECT {', '.join(cols)} FROM _stage_courses "
                        "ON CONFLICT DO NOTHING RETURNING course_id"
                    )
                    inserted = {r[0] for r in cur.fetchall()}
                    if inserted:
                        with cur.copy(
                            "COPY catalog_modules (course_id, ordering, module_id, title, deck_id, scene_id, deck_sha256) FROM STDIN"
                        ) as cp:
                            for cid in inserted:
                                for mrow in self._module_rows(by_id[cid]):
                                    cp.write_row(mrow)
                        if sources:
                            with cur.copy(
                                "COPY catalog_sources (course_id, deck_sha256, source_url, canonical_url, license, "
                                "license_tier, attribution, fetched_at) FROM STDIN"
                            ) as cp:
                                for cid in inserted:
                                    for s in sources.get(cid, []):
                                        cp.write_row([
                                            cid, s.get("deck_sha256", ""), s.get("source_url", ""),
                                            s.get("canonical_url", ""), s.get("license", ""),
                                            s.get("license_tier", "unknown"),
                                            json.dumps(s.get("attribution") or {}), s.get("fetched_at", ""),
                                        ])
        return len(inserted), len(rows) - len(inserted)

    @staticmethod
    def _has_fts(cur: Any) -> bool:
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = '_stage_courses' AND column_name = 'fts' "
            "AND table_schema LIKE 'pg_temp%'"
        )
        return cur.fetchone() is not None

    def delete_course(self, course_id: str) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM catalog_courses WHERE course_id = %s", (course_id,))
            existed = cur.rowcount > 0
        self._forget(course_id)
        return existed

    def patch_course(self, course_id: str, **fields: object) -> Optional[Course]:
        allowed = {"trailer_url", "hls_url", "media_format"}
        patch = {k: v for k, v in fields.items() if k in allowed}
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE catalog_courses SET data = data || %s::jsonb, "
                "media_format = coalesce(%s, media_format), updated_at = now() "
                "WHERE course_id = %s RETURNING data",
                (json.dumps(patch), _lower(str(patch["media_format"])) if "media_format" in patch else None, course_id),
            )
            row = cur.fetchone()
        self._forget(course_id)
        return self._course(row[0]) if row else None

    def bump_popularity(self, course_id: str, by: int = 1) -> Optional[Course]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE catalog_courses SET popularity = popularity + %s, "
                "data = jsonb_set(data, '{popularity}', to_jsonb(popularity + %s)), updated_at = now() "
                "WHERE course_id = %s RETURNING data",
                (by, by, course_id),
            )
            row = cur.fetchone()
        self._forget(course_id)
        return self._course(row[0]) if row else None

    # ------------------------------------------------------------------ queries
    def _where(self, f: Dict[str, Any]) -> Tuple[str, List[Any], Optional[str]]:
        """Build the WHERE clause. Returns (sql, params, rank_expr_sql_or_None)."""
        clauses = ["publish_state = 'published'"]
        params: List[Any] = []

        def eq(col: str, value: Optional[str], *, wrap: str = "{c}") -> None:
            if value is not None and value != "":
                clauses.append(f"{wrap.format(c=col)} = %s")
                params.append(_lower(value))

        eq("category", f.get("category"), wrap="lower({c})")
        eq("language", f.get("language"))
        eq("audio_language", f.get("audio"))
        eq("media_format", f.get("media_format"))
        eq("level", f.get("level"))
        eq("delivery_mode", f.get("delivery_mode"))
        eq("access_tier", f.get("access_tier"))
        eq("maturity_rating", f.get("maturity"))
        if f.get("source"):
            clauses.append("source = %s")
            params.append(f["source"])
        if f.get("tag"):
            clauses.append("tags @> ARRAY[%s]::text[]")
            params.append(_lower(f["tag"]))
        if f.get("audience"):
            clauses.append("audiences @> ARRAY[%s]::text[]")
            params.append(_lower(f["audience"]))
        if f.get("hands_on") is not None:
            clauses.append("hands_on = %s")
            params.append(bool(f["hands_on"]))
        if f.get("core_skill") is not None:
            clauses.append("core_skill = %s")
            params.append(bool(f["core_skill"]))
        rank = None
        q = (f.get("q") or "").strip()
        if q:
            clauses.append("(fts @@ websearch_to_tsquery('simple', %s) OR title ILIKE %s)")
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            params.extend([q, like])
            rank = "ts_rank_cd(fts, websearch_to_tsquery('simple', %s))"
        return " AND ".join(clauses), params, rank

    def page_courses(
        self,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
        offset: int = 0,
        **filters: Any,
    ) -> Tuple[List[Course], Optional[str]]:
        """One page + the cursor for the next. Browse lists use keyset pagination (fast at any depth);
        text search returns relevance-ranked pages via offset (capped at MAX_SEARCH_OFFSET)."""
        limit = min(max(int(limit), 1), MAX_PAGE)
        where, params, rank = self._where(filters)
        sql_params = list(params)
        if rank is not None:
            # Rank only the most popular matches. Ranking every hit of a common word (13k rows in the
            # load test) cost 60-200 ms; taking the top search_candidates by popularity first and
            # ranking those keeps a bounded cost and still puts title matches first.
            offset = min(max(int(offset), 0), MAX_SEARCH_OFFSET)
            sql = (
                f"WITH cand AS (SELECT data, fts, popularity, course_id FROM catalog_courses WHERE {where} "
                f"ORDER BY popularity DESC, course_id DESC LIMIT %s) "
                f"SELECT data FROM cand ORDER BY {rank} DESC, popularity DESC, course_id DESC LIMIT %s OFFSET %s"
            )
            sql_params = sql_params + [self.search_candidates, filters["q"].strip()] + [limit, offset]
            with self.pool.connection() as conn, conn.cursor() as cur:
                cur.execute(sql, sql_params)
                rows = cur.fetchall()
            return [self._course(r[0]) for r in rows], None
        if cursor:
            pop, cid = decode_cursor(cursor)
            where += " AND (popularity, course_id) < (%s, %s)"
            sql_params += [pop, cid]
            offset = 0
        offset = min(max(int(offset), 0), MAX_SEARCH_OFFSET)
        sql = (
            f"SELECT data, popularity, course_id FROM catalog_courses WHERE {where} "
            f"ORDER BY popularity DESC, course_id DESC LIMIT %s OFFSET %s"
        )
        sql_params += [limit + 1, offset]
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        items = [self._course(r[0]) for r in rows]
        nxt = encode_cursor(rows[-1][1], rows[-1][2]) if (more and rows) else None
        return items, nxt

    def count_courses(self, **filters: Any) -> Tuple[int, bool]:
        """(count, capped). Exact up to count_cap; beyond that it stops counting and says so."""
        where, params, _ = self._where(filters)
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM (SELECT 1 FROM catalog_courses WHERE {where} LIMIT %s) t",
                params + [self.count_cap + 1],
            )
            n = int(cur.fetchone()[0])
        return min(n, self.count_cap), n > self.count_cap

    def list_courses(self) -> List[Course]:
        """The hot set: top hot_cap published courses by popularity. NOT the whole catalog."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM catalog_courses WHERE publish_state = 'published' "
                "ORDER BY popularity DESC, course_id DESC LIMIT %s", (self.hot_cap,)
            )
            return [self._course(r[0]) for r in cur.fetchall()]

    def search_courses(self, **filters: Any) -> List[Course]:
        items, _ = self.page_courses(limit=MAX_PAGE, **filters)
        return items

    def kids_safe(self) -> List[Course]:
        items, _ = self.page_courses(limit=MAX_PAGE, maturity="kids")
        return items

    def facet_counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT kind, value, n FROM catalog_facets")
            rows = cur.fetchall()
            if not rows:
                cur.execute("SELECT catalog_refresh_facets()")
                cur.execute("SELECT kind, value, n FROM catalog_facets")
                rows = cur.fetchall()
        for kind, value, n in rows:
            out.setdefault(kind, {})[value] = int(n)
        return out

    def home_rails(self, *, kids_only: bool = False, per_rail: int = 12) -> List[dict]:
        """Home feed rows. ~25 index queries, so the result is cached for rails_ttl seconds per replica."""
        key = (kids_only, per_rail)
        hit = self._rails.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        rails = self._build_rails(kids_only=kids_only, per_rail=per_rail)
        if self.rails_ttl > 0:
            self._rails[key] = (time.monotonic() + self.rails_ttl, rails)
        return rails

    def _build_rails(self, *, kids_only: bool, per_rail: int) -> List[dict]:
        base = {"maturity": "kids"} if kids_only else {}
        rails: List[dict] = []

        def rail(key: str, title: str, items: List[Course]) -> None:
            if items:
                rails.append({"key": key, "title": title, "courses": items})

        def top(order: str = "popularity DESC, course_id DESC", extra: str = "", params: Optional[list] = None) -> List[Course]:
            where, p, _ = self._where(dict(base))
            with self.pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM catalog_courses WHERE {where}{extra} ORDER BY {order} LIMIT %s",
                    p + (params or []) + [per_rail],
                )
                return [self._course(r[0]) for r in cur.fetchall()]

        rail("popular", "Popular now", top())
        rail("new", "New releases", top("created_at DESC, course_id DESC"))
        rail("free", "Free to start", top(extra=" AND access_tier = 'free'"))
        rail("hands_on", "Hands-on labs", top(extra=" AND hands_on"))
        if not kids_only:
            rail("kids", "Just for kids", top(extra=" AND maturity_rating = 'kids'"))
        cats = self.facet_counts().get("category", {})
        for cat in sorted(sorted(cats, key=lambda c: -cats[c])[:20]):
            rail(f"cat:{cat}", cat, top(extra=" AND lower(category) = %s", params=[cat.lower()]))
        return rails

    # ------------------------------------------------------------------ programs
    def create_program(self, program: Program) -> Program:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog_programs (program_id, title, data, updated_at) VALUES (%s, %s, %s::jsonb, now()) "
                "ON CONFLICT (program_id) DO UPDATE SET title = EXCLUDED.title, data = EXCLUDED.data, updated_at = now()",
                (program.program_id, program.title, json.dumps(program.model_dump(mode="json"))),
            )
        return program

    def get_program(self, program_id: str) -> Optional[Program]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM catalog_programs WHERE program_id = %s", (program_id,))
            row = cur.fetchone()
        return Program(**(row[0] if isinstance(row[0], dict) else json.loads(row[0]))) if row else None

    def list_programs(self) -> List[Program]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM catalog_programs ORDER BY title, program_id LIMIT 1000")
            rows = cur.fetchall()
        return [Program(**(r[0] if isinstance(r[0], dict) else json.loads(r[0]))) for r in rows]

    def delete_program(self, program_id: str) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM catalog_programs WHERE program_id = %s", (program_id,))
            return cur.rowcount > 0

    # --------------------------------------------------------------- health
    def healthy(self) -> bool:
        try:
            with self.pool.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
        except Exception:
            return False
