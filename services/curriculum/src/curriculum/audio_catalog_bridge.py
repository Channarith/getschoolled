"""Fallback catalog from the generated audio course library.

The in-memory CatalogStore starts empty unless CATALOG_PATH is set. Web home,
browse, and watch all read from that store, while Live Class lessons come from
the orchestrator and Drive/mobile use /audio/courses. When the store has no
courses, expose the audio library through the same /home and /courses/search
shapes so Browse and the home feed are populated out of the box.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aoep_shared.audio_courses import AudioCourse, build_catalog

from curriculum.catalog import Course, DeliveryMode


def _preview(ac: AudioCourse) -> str:
    if not ac.segments:
        return ""
    return ac.segments[0].text[:200]


def audio_to_course(ac: AudioCourse) -> Course:
    blurb = _preview(ac)
    tags = list(ac.tags)
    if "audio" not in tags:
        tags.append("audio")
    if ac.drive_safe and "drive-safe" not in tags:
        tags.append("drive-safe")
    return Course(
        course_id=ac.id,
        title=ac.title,
        subject=ac.subject or ac.category,
        language="en",
        description=blurb,
        category=ac.category,
        tags=tags,
        audio_language="en",
        media_format="audio",
        level=ac.level,
        duration_min=ac.duration_min,
        hands_on=False,
        preview=blurb[:160],
        access_tier="free",
        delivery_mode=DeliveryMode.AI,
        maturity_rating="all",
    )


def all_audio_courses(locale: str = "en") -> List[Course]:
    return [audio_to_course(c) for c in build_catalog(locale)]


def catalog_is_empty(courses: List[Course]) -> bool:
    return len(courses) == 0


def search_audio_courses(
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
    locale: str = "en",
) -> List[Course]:
    """Faceted search over the audio library (mirrors CatalogStore.search_courses)."""
    rows = all_audio_courses(locale)

    def _eq(value: str, want: Optional[str]) -> bool:
        return want is None or value.lower() == want.lower()

    out: List[Course] = []
    for c in rows:
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


def audio_home_rails(*, kids_only: bool = False, per_rail: int = 12, locale: str = "en") -> List[dict]:
    """Netflix-style rows built from the audio catalog."""
    pool = build_catalog(locale)
    if kids_only:
        pool = [
            c for c in pool
            if c.duration_min <= 15
            and (c.level == "beginner" or "language" in c.tags or "listen-and-repeat" in c.tags)
        ]

    courses = [audio_to_course(c) for c in pool]
    rails: List[dict] = []

    def rail(key: str, title: str, items: List[Course]) -> None:
        if items:
            rails.append({"key": key, "title": title, "courses": items[:per_rail]})

    rail("new", "New this week", courses)
    if len(courses) > per_rail:
        rail("trending", "Trending now", courses[per_rail : per_rail * 2])
    rail("audio", "Drive-safe audio classes", courses)
    rail("free", "Free to start", [c for c in courses if c.access_tier == "free"])

    cats: Dict[str, List[Course]] = {}
    for c in courses:
        cats.setdefault(c.category or c.subject, []).append(c)
    for cat in sorted(k for k in cats if k):
        rail(f"cat:{cat}", cat, sorted(cats[cat], key=lambda c: c.title))

    return rails


def audio_facets(locale: str = "en") -> dict:
    courses = all_audio_courses(locale)

    def _distinct(key: str) -> List[str]:
        vals = {getattr(c, key) for c in courses if getattr(c, key)}
        return sorted(str(v) for v in vals)

    tags = sorted({t for c in courses for t in c.tags})
    return {
        "categories": sorted({(c.category or c.subject) for c in courses if (c.category or c.subject)}),
        "languages": _distinct("language"),
        "audio_languages": sorted({(c.audio_language or c.language) for c in courses}),
        "media_formats": _distinct("media_format"),
        "levels": _distinct("level"),
        "tags": tags,
        "maturity_ratings": _distinct("maturity_rating"),
        "access_tiers": _distinct("access_tier"),
        "audiences": [],
    }


def get_audio_course_as_catalog(course_id: str, locale: str = "en") -> Optional[Course]:
    for c in build_catalog(locale):
        if c.id == course_id:
            return audio_to_course(c)
    return None
