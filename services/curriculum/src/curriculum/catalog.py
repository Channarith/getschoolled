"""Course catalog and dynamic training programs.

A persistent catalog of Programs -> Courses -> Modules (which reference the CMS
decks/scenes by id). Dynamic training programs carry adaptive rules (e.g.
prerequisite mastery) so the next course can be chosen from a learner's state.
Storage mirrors the FaceGallery pattern: in-memory with optional JSON
persistence; db/migrations/0003_catalog.sql is the schema-of-record for the
eventual Postgres backend.
"""

from __future__ import annotations

import base64
import enum
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator

from aoep_shared.catalog_db.compose import course_content_hash


class DeliveryMode(str, enum.Enum):
    """Who conducts the class: fully AI, fully human, or AI + human (hybrid)."""
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


class Module(BaseModel):
    module_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    deck_id: Optional[str] = None
    scene_id: Optional[str] = None
    order: int = 0


class Course(BaseModel):
    course_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    subject: str = "general"        # maps to the LLM routing category
    language: str = "en"
    description: str = ""
    modules: List[Module] = Field(default_factory=list)
    validation_status: str = "unvalidated"  # unvalidated | validated | flagged
    version: int = 1
    # Accountability (Trust layer): a named human signs off on the content.
    human_of_record: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None
    # Opt-in delivery track (Trust layer): AI / human / hybrid.
    delivery_mode: DeliveryMode = DeliveryMode.AI
    # Browse / search metadata (Netflix-style catalog).
    category: str = ""                  # defaults to subject; the browse facet
    tags: List[str] = Field(default_factory=list)
    audio_language: str = ""            # spoken-audio language; defaults to language
    media_format: str = "video"         # video | audio | text | interactive
    level: str = "beginner"             # beginner | intermediate | advanced
    duration_min: int = 0
    complexity: int = 0               # 0 = infer from level/maturity; else 1–5
    hands_on: bool = False              # requires hands-on/lab training
    preview: str = ""                   # short preview/trailer blurb
    access_tier: str = "free"           # membership tier required to enroll
    price_usd: float = 0.0
    thumbnail: Optional[str] = None     # object-store key / URL for a card image
    # Streaming / interchange metadata (Netflix-style, acquisition-ready).
    maturity_rating: str = "all"        # all | kids | teen | mature
    subtitle_languages: List[str] = Field(default_factory=list)
    hls_url: Optional[str] = None       # HLS manifest (.m3u8)
    dash_url: Optional[str] = None      # MPEG-DASH manifest (.mpd)
    trailer_url: Optional[str] = None
    popularity: int = 0                 # view/enroll signal for "popular" rails
    created_at: float = Field(default_factory=time.time)
    audiences: List[str] = Field(default_factory=list)   # explicit profession tags
    core_skill: bool = False                              # explicit "core skill" flag
    # Unified search metadata (populated when served from learnable index).
    source: str = ""
    deep_link: str = ""
    global_id: str = ""
    lifecycle_state: str = "published"
    source_fingerprint: str = ""

    @model_validator(mode="after")
    def _defaults(self) -> "Course":
        if not self.category:
            self.category = self.subject
        if not self.audio_language:
            self.audio_language = self.language
        return self


class Program(BaseModel):
    program_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    audience: str = ""              # role / cohort the program targets
    description: str = ""
    course_ids: List[str] = Field(default_factory=list)
    # Adaptive rules, e.g. {"prereq_mastery": {course_id: 0.7}} - a course is
    # unlocked only once its prerequisites are mastered above the threshold.
    adaptive_rules: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    delivery_mode: DeliveryMode = DeliveryMode.AI
    lifecycle_state: str = "published"
    category_slug: str = ""

    @model_validator(mode="after")
    def _course_bounds(self) -> "Program":
        if len(self.course_ids) > 60:
            raise ValueError("a program can contain at most 60 courses")
        if len(set(self.course_ids)) != len(self.course_ids):
            raise ValueError("program course_ids must be unique")
        return self


def encode_cursor(popularity: int, course_id: str) -> str:
    """Opaque keyset cursor: the (popularity, course_id) of the last row of a page."""
    raw = json.dumps([int(popularity), course_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> Tuple[int, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        pop, cid = json.loads(raw)
        return int(pop), str(cid)
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


def course_hash(course: "Course") -> str:
    """Content identity shared by every store: title, language, subject and ordered lessons."""
    return course_content_hash(
        course.title, course.language, course.subject,
        [{"title": m.title, "deck_id": m.deck_id, "scene_id": m.scene_id} for m in course.modules],
    )


class CatalogStore:
    """In-memory catalog with optional JSON persistence (dev, tests, and the default in production
    until CATALOG_DATABASE_URL is set). PgCatalogStore (catalog_pg.py) has the same surface."""

    paged = False  # True on stores whose list/search must go through page_courses()

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.courses: Dict[str, Course] = {}
        self.programs: Dict[str, Program] = {}
        self._lock = threading.Lock()
        if path and os.path.isfile(path):
            self.load_json(path)

    # --- courses ----------------------------------------------------------- #
    def create_course(self, course: Course, *, dedupe: bool = False) -> Course:
        """Insert or replace by course_id. With dedupe=True, identical content (same title, language,
        subject and lessons) under another id returns the existing course instead of a copy."""
        if dedupe:
            h = course_hash(course)
            for existing in self.courses.values():
                if existing.course_id != course.course_id and course_hash(existing) == h:
                    return existing
        self.courses[course.course_id] = course
        self._autosave()
        return course

    def upsert_course(self, course: Course) -> Course:
        """Create or replace a course while preserving durable-store semantics."""
        return self.create_course(course)

    def get_course(self, course_id: str) -> Optional[Course]:
        return self.courses.get(course_id)

    def list_courses(self) -> List[Course]:
        return list(self.courses.values())

    def search_courses(
        self,
        *,
        q: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        audio: Optional[str] = None,
        media_format: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        hands_on: Optional[bool] = None,
        delivery_mode: Optional[str] = None,
        access_tier: Optional[str] = None,
        maturity: Optional[str] = None,
    ) -> List[Course]:
        """Faceted catalog search by name/category/language/audio/format/tag/etc."""
        def _eq(value: str, want: Optional[str]) -> bool:
            return want is None or value.lower() == want.lower()

        out: List[Course] = []
        for c in self.courses.values():
            if q:
                hay = " ".join([c.title, c.description, c.preview, " ".join(c.tags)]).lower()
                if q.lower() not in hay:
                    continue
            if not _eq(c.category or c.subject, category):
                continue
            if not _eq(c.language, language):
                continue
            if not _eq(c.audio_language or c.language, audio):
                continue
            if not _eq(c.media_format, media_format):
                continue
            if not _eq(c.level, level):
                continue
            if not _eq(c.delivery_mode.value, delivery_mode):
                continue
            if not _eq(c.access_tier, access_tier):
                continue
            if not _eq(c.maturity_rating, maturity):
                continue
            if tag is not None and tag.lower() not in [t.lower() for t in c.tags]:
                continue
            if hands_on is not None and c.hands_on != hands_on:
                continue
            out.append(c)
        return out

    # --- paging (same contract as PgCatalogStore) -------------------------- #
    def _filtered(self, filters: Dict[str, Any]) -> List[Course]:
        known = {
            k: filters.get(k)
            for k in ("q", "category", "language", "audio", "media_format", "level", "tag",
                      "hands_on", "delivery_mode", "access_tier", "maturity")
        }
        out = self.search_courses(**known)
        if filters.get("audience"):
            want = str(filters["audience"]).lower()
            out = [c for c in out if want in [a.lower() for a in c.audiences]]
        if filters.get("core_skill") is not None:
            out = [c for c in out if c.core_skill == bool(filters["core_skill"])]
        if filters.get("source"):
            out = [c for c in out if c.source == filters["source"]]
        return [c for c in out if (c.lifecycle_state or "published") == "published"]

    def page_courses(self, *, limit: int = 50, cursor: Optional[str] = None, offset: int = 0,
                     **filters: Any) -> Tuple[List[Course], Optional[str]]:
        limit = min(max(int(limit), 1), 200)
        rows = sorted(self._filtered(filters), key=lambda c: (c.popularity, c.course_id), reverse=True)
        if cursor:
            pop, cid = decode_cursor(cursor)
            rows = [c for c in rows if (c.popularity, c.course_id) < (pop, cid)]
            offset = 0
        offset = max(int(offset), 0)
        window = rows[offset:offset + limit + 1]
        more = len(window) > limit
        window = window[:limit]
        nxt = encode_cursor(window[-1].popularity, window[-1].course_id) if (more and window) else None
        return window, nxt

    def count_courses(self, **filters: Any) -> Tuple[int, bool]:
        return len(self._filtered(filters)), False

    def facet_counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for c in self.courses.values():
            for kind, value in (("category", c.category), ("language", c.language), ("level", c.level),
                                ("media_format", c.media_format), ("quality_tier", "0")):
                if value:
                    out.setdefault(kind, {})[value] = out.setdefault(kind, {}).get(value, 0) + 1
        return out

    # --- discovery rails (Netflix-style home feed) ------------------------- #
    def bump_popularity(self, course_id: str, by: int = 1) -> Optional[Course]:
        with self._lock:
            c = self.courses.get(course_id)
            if c is None:
                return None
            c.popularity += by
            self._autosave()
            return c

    def kids_safe(self) -> List[Course]:
        """Courses for the children's platform: only kid-authored (kids-rated).

        The general all-ages catalog stays on the main home; the kids platform is
        deliberately limited to content authored for children.
        """
        return [c for c in self.courses.values() if c.maturity_rating == "kids"]

    def home_rails(self, *, kids_only: bool = False, per_rail: int = 12) -> List[dict]:
        """Build ordered carousel rows for the home feed.

        Rows: Popular now, New releases, Free to start, Hands-on, Just for kids,
        then one row per category. Empty rows are omitted.
        """
        pool = self.kids_safe() if kids_only else list(self.courses.values())
        rails: List[dict] = []

        def rail(key: str, title: str, items: List[Course]) -> None:
            if items:
                rails.append({"key": key, "title": title, "courses": items[:per_rail]})

        popular = sorted(pool, key=lambda c: (c.popularity, c.created_at), reverse=True)
        rail("popular", "Popular now", popular)
        recent = sorted(pool, key=lambda c: c.created_at, reverse=True)
        rail("new", "New releases", recent)
        rail("free", "Free to start", [c for c in pool if c.access_tier == "free"])
        rail("hands_on", "Hands-on labs", [c for c in pool if c.hands_on])
        if not kids_only:
            rail("kids", "Just for kids", [c for c in pool if c.maturity_rating == "kids"])
        # Per-category rows, ordered by category name.
        cats: Dict[str, List[Course]] = {}
        for c in pool:
            cats.setdefault(c.category or c.subject, []).append(c)
        for cat in sorted(k for k in cats if k):
            rail(f"cat:{cat}", cat, sorted(cats[cat], key=lambda c: c.popularity, reverse=True))
        return rails

    def delete_course(self, course_id: str) -> bool:
        existed = self.courses.pop(course_id, None) is not None
        if existed:
            self._autosave()
        return existed

    def patch_course(self, course_id: str, **fields: object) -> Optional[Course]:
        """Update playable media fields already on the course record."""
        allowed = {"trailer_url", "hls_url", "media_format"}
        with self._lock:
            course = self.courses.get(course_id)
            if course is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    setattr(course, key, value)
            self._autosave()
            return course

    # --- programs ---------------------------------------------------------- #
    def create_program(self, program: Program) -> Program:
        self.programs[program.program_id] = program
        self._autosave()
        return program

    def get_program(self, program_id: str) -> Optional[Program]:
        return self.programs.get(program_id)

    def list_programs(self) -> List[Program]:
        return list(self.programs.values())

    def delete_program(self, program_id: str) -> bool:
        existed = self.programs.pop(program_id, None) is not None
        if existed:
            self._autosave()
        return existed

    # --- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "courses": {k: v.model_dump() for k, v in self.courses.items()},
            "programs": {k: v.model_dump() for k, v in self.programs.items()},
        }

    def save_json(self, path: Optional[str] = None) -> None:
        target = path or self.path
        if not target:
            raise ValueError("no catalog path configured")
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = target + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh)
        os.replace(tmp, target)

    def load_json(self, path: Optional[str] = None) -> None:
        target = path or self.path
        with open(target, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.courses = {k: Course(**v) for k, v in data.get("courses", {}).items()}
        self.programs = {k: Program(**v) for k, v in data.get("programs", {}).items()}

    def _autosave(self) -> None:
        if self.path:
            self.save_json(self.path)


def make_catalog_store(path: Optional[str] = None) -> "CatalogStore":
    """The store the service uses. CATALOG_DATABASE_URL selects Postgres; unset keeps today's
    in-memory/JSON store exactly as before (so shipping this code changes nothing until the
    environment variable is set). Falls back to memory, loudly, if Postgres cannot be reached and
    CATALOG_DB_REQUIRED is not set; with CATALOG_DB_REQUIRED=1 startup fails instead of silently
    serving a diverging in-memory catalog."""
    dsn = (os.environ.get("CATALOG_DATABASE_URL") or "").strip()
    if not dsn:
        return CatalogStore(path=path)
    try:
        from .catalog_pg import PgCatalogStore

        store = PgCatalogStore(dsn)
        if not store.healthy():
            raise RuntimeError("catalog database did not answer")
        return store  # type: ignore[return-value]
    except Exception as exc:
        if os.environ.get("CATALOG_DB_REQUIRED") == "1":
            raise
        import logging

        logging.getLogger("curriculum.catalog").error(
            "CATALOG_DATABASE_URL is set but unusable (%s): serving the in-memory catalog. "
            "Replicas will diverge until this is fixed; set CATALOG_DB_REQUIRED=1 to fail fast.", exc
        )
        return CatalogStore(path=path)
