"""Build and search a merged index of all learnable content."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from aoep_shared.audio_courses import AudioCourse, build_catalog
from aoep_shared.games import GAME_SUBJECTS
from aoep_shared.language_learning import language_list

from .lessons import lesson_category, lesson_duration_min, load_sample_lessons
from .models import LearnableItem


def _preview_audio(ac: AudioCourse) -> str:
    if not ac.segments:
        return ""
    return ac.segments[0].text[:200]


def _from_catalog_course(c: Any) -> LearnableItem:
    if hasattr(c, "course_id"):
        course_id = c.course_id
        title = c.title
        category = c.category or c.subject
        media = c.media_format
        subject = c.subject
        level = c.level
        language = c.language
        audio_language = getattr(c, "audio_language", "") or language
        duration_min = int(c.duration_min or 0)
        tags = list(c.tags or [])
        maturity_rating = c.maturity_rating
        audiences = list(c.audiences or [])
        hands_on = bool(c.hands_on)
        access_tier = c.access_tier
        preview = (c.preview or c.description or "")[:200]
        popularity = int(c.popularity or 0)
    else:
        course_id = c["course_id"]
        title = c.get("title", "")
        category = c.get("category", "") or c.get("subject", "")
        media = c.get("media_format", "video")
        subject = c.get("subject", "")
        level = c.get("level", "beginner")
        language = c.get("language", "en")
        audio_language = c.get("audio_language", "") or language
        duration_min = int(c.get("duration_min", 0) or 0)
        tags = list(c.get("tags", []) or [])
        maturity_rating = c.get("maturity_rating", "all")
        audiences = list(c.get("audiences", []) or [])
        hands_on = bool(c.get("hands_on", False))
        access_tier = c.get("access_tier", "free")
        preview = (c.get("preview", "") or c.get("description", ""))[:200]
        popularity = int(c.get("popularity", 0) or 0)
    fmt = "audio" if media == "audio" else media
    deep = f"/drive?course={course_id}" if fmt == "audio" else f"/watch?course={course_id}"
    return LearnableItem(
        id=f"catalog:{course_id}",
        source="catalog",
        source_id=course_id,
        title=title,
        subtitle=subject,
        category=category,
        subject=subject,
        format=fmt,
        level=level,
        language=language,
        audio_language=audio_language,
        duration_min=duration_min,
        tags=tags,
        maturity_rating=maturity_rating,
        audiences=audiences,
        hands_on=hands_on,
        drive_safe=fmt == "audio",
        access_tier=access_tier,
        preview=preview,
        deep_link=deep,
        popularity=popularity,
    )


def _from_audio(ac: AudioCourse) -> LearnableItem:
    blurb = _preview_audio(ac)
    tags = list(ac.tags)
    for t in ("audio", "drive-safe"):
        if t not in tags:
            tags.append(t)
    return LearnableItem(
        id=f"audio:{ac.id}",
        source="audio",
        source_id=ac.id,
        title=ac.title,
        subtitle=ac.subject or ac.category,
        category=ac.category,
        subject=ac.subject or ac.category,
        format="audio",
        level=ac.level,
        language="en",
        audio_language="en",
        duration_min=ac.duration_min,
        tags=tags,
        drive_safe=ac.drive_safe,
        preview=blurb[:160],
        deep_link=f"/drive?course={ac.id}",
    )


def _from_lesson(lesson: Any) -> LearnableItem:
    if hasattr(lesson, "slides"):
        slides = lesson.slides
        lesson_id = lesson.lesson_id
        title = lesson.title
        language = getattr(lesson, "language", "en")
    else:
        slides = lesson.get("slides", [])
        lesson_id = lesson["lesson_id"]
        title = lesson["title"]
        language = lesson.get("language", "en")
    category = lesson_category(lesson_id, title)
    duration = lesson_duration_min(slides)
    preview = slides[0].body[:160] if slides else ""
    tags = ["live-class"]
    if lesson_id.startswith("python"):
        tags.append("python")
    return LearnableItem(
        id=f"lesson:{lesson_id}",
        source="lesson",
        source_id=lesson_id,
        title=title,
        subtitle=f"{len(slides)} slides",
        category=category,
        subject=category,
        format="live_class",
        level="beginner" if lesson_id.startswith("intro") else "intermediate",
        language=language,
        duration_min=duration,
        tags=tags,
        preview=preview,
        deep_link=f"/class?lesson={lesson_id}",
        popularity=10,
    )


def _from_language(lang: dict) -> LearnableItem:
    code = lang["code"]
    title = f"{lang['name']} ({lang['native']})"
    tier = lang.get("tier", "starter")
    return LearnableItem(
        id=f"language:{code}",
        source="language",
        source_id=code,
        title=title,
        subtitle="Interactive language course",
        category="Languages",
        subject=lang["name"],
        format="interactive",
        level="beginner",
        language=code,
        audio_language=code,
        duration_min=30,
        tags=["language", tier, code],
        preview=f"Practice {lang['name']} with pronunciation, vocabulary, and phrases.",
        deep_link=f"/languages?code={code}",
        popularity=5,
    )


def _from_program(p: Any) -> LearnableItem:
    if hasattr(p, "program_id"):
        program_id = p.program_id
        title = p.title
        audience = p.audience
        course_ids = list(p.course_ids or [])
        description = p.description or ""
    else:
        program_id = p["program_id"]
        title = p.get("title", "")
        audience = p.get("audience", "")
        course_ids = list(p.get("course_ids", []) or [])
        description = p.get("description", "")
    return LearnableItem(
        id=f"program:{program_id}",
        source="program",
        source_id=program_id,
        title=title,
        subtitle=f"{len(course_ids)} courses",
        category=audience or "Programs",
        subject=audience or "program",
        format="program",
        level="beginner",
        tags=["program", audience] if audience else ["program"],
        preview=description[:160],
        deep_link="/corporate",
        popularity=3,
    )


def _from_game_subject(subject: str) -> LearnableItem:
    label = subject.replace("_", " ").title()
    return LearnableItem(
        id=f"game:{subject}",
        source="game",
        source_id=subject,
        title=f"{label} Arcade",
        subtitle="Quiz, speed round, and match games",
        category="Games",
        subject=subject,
        format="game",
        level="beginner",
        tags=["arcade", "game", subject],
        preview=f"Practice {label} with quick arcade drills.",
        deep_link=f"/arcade?subject={subject}",
        popularity=2,
    )


def build_learnable_index(
    *,
    catalog_courses: Sequence[Any] = (),
    catalog_programs: Sequence[Any] = (),
    locale: str = "en",
    curriculum_dir: Optional[str] = None,
) -> List[LearnableItem]:
    """Merge catalog, audio, live lessons, languages, programs, and arcade subjects."""
    items: List[LearnableItem] = []
    catalog_ids: set[str] = set()

    for c in catalog_courses:
        item = _from_catalog_course(c)
        items.append(item)
        catalog_ids.add(item.source_id)

    for ac in build_catalog(locale):
        if ac.id in catalog_ids:
            continue
        items.append(_from_audio(ac))

    for lesson in load_sample_lessons(curriculum_dir):
        items.append(_from_lesson(lesson))

    for lang in language_list():
        items.append(_from_language(lang))

    for program in catalog_programs:
        items.append(_from_program(program))

    for subject in GAME_SUBJECTS:
        items.append(_from_game_subject(subject))

    return items


def _matches_eq(value: str, want: Optional[str]) -> bool:
    return want is None or value.lower() == want.lower()


def search_learnable(
    items: Sequence[LearnableItem],
    *,
    q: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    format: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
    audio_language: Optional[str] = None,
    maturity: Optional[str] = None,
    hands_on: Optional[bool] = None,
    audience: Optional[str] = None,
    core_skill: Optional[bool] = None,
    tag: Optional[str] = None,
    kids_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    rows: List[LearnableItem] = list(items)

    if kids_only:
        rows = [
            c for c in rows
            if c.maturity_rating == "kids"
            or c.format in ("live_class", "game", "interactive")
            or (c.format == "audio" and c.duration_min <= 15)
        ]

    if audience or core_skill is not None:
        from aoep_shared.skills_taxonomy import course_relevance

        filtered: List[LearnableItem] = []
        for c in rows:
            rel = course_relevance({
                "title": c.title, "subject": c.subject, "category": c.category,
                "tags": c.tags, "audiences": c.audiences, "core_skill": "core_skill" in c.tags,
            })
            if audience and audience.lower() not in rel["audiences"]:
                continue
            if core_skill is not None and rel["core_skill"] != core_skill:
                continue
            filtered.append(c)
        rows = filtered

    def passes_filters(c: LearnableItem) -> bool:
        if not _matches_eq(c.category or c.subject, category):
            return False
        if not _matches_eq(c.source, source):
            return False
        if format and not _matches_eq(c.format, format):
            return False
        if not _matches_eq(c.level, level):
            return False
        if not _matches_eq(c.language, language):
            return False
        if audio_language is not None and not _matches_eq(
            c.audio_language or c.language, audio_language
        ):
            return False
        if not _matches_eq(c.maturity_rating, maturity):
            return False
        if hands_on is not None and c.hands_on != hands_on:
            return False
        if tag is not None and tag.lower() not in [t.lower() for t in c.tags]:
            return False
        return True

    rows = [c for c in rows if passes_filters(c)]

    if q:
        ql = q.lower()
        scored: List[tuple[int, LearnableItem]] = []
        for c in rows:
            hay = " ".join([
                c.title, c.subtitle, c.category, c.subject, c.preview, " ".join(c.tags),
            ]).lower()
            if ql not in hay:
                continue
            score = 0
            if c.title.lower() == ql:
                score += 200
            elif c.title.lower().startswith(ql):
                score += 120
            elif ql in c.title.lower():
                score += 80
            else:
                score += 40
            score += c.popularity
            scored.append((score, c))
        scored.sort(key=lambda pair: (-pair[0], pair[1].title.lower()))
        rows = [c for _, c in scored]
    else:
        rows = sorted(rows, key=lambda c: (-c.popularity, c.title.lower()))

    total = len(rows)
    page = rows[max(0, offset): max(0, offset) + max(1, min(limit, 200))]
    return {
        "total": total,
        "offset": max(0, offset),
        "limit": max(1, min(limit, 200)),
        "items": page,
    }


def learnable_facets(items: Sequence[LearnableItem]) -> dict:
    def distinct(attr: str) -> List[str]:
        vals = {getattr(c, attr) for c in items if getattr(c, attr)}
        return sorted(str(v) for v in vals)

    tags = sorted({t for c in items for t in c.tags})
    sources = distinct("source")
    formats = distinct("format")
    return {
        "categories": sorted({(c.category or c.subject) for c in items if (c.category or c.subject)}),
        "languages": distinct("language"),
        "audio_languages": sorted(
            {(c.audio_language or c.language) for c in items if (c.audio_language or c.language)}
        ),
        "media_formats": formats,
        "formats": formats,
        "sources": sources,
        "levels": distinct("level"),
        "tags": tags,
        "maturity_ratings": distinct("maturity_rating"),
        "access_tiers": distinct("access_tier"),
        "audiences": _audience_facet(items),
    }


def _audience_facet(items: Sequence[LearnableItem]) -> List[dict]:
    from aoep_shared.skills_taxonomy import PROFESSIONS, course_relevance

    seen: set[str] = set()
    for c in items:
        rel = course_relevance({
            "title": c.title, "subject": c.subject, "category": c.category,
            "tags": c.tags, "audiences": c.audiences,
            "core_skill": "core_skill" in c.tags,
        })
        seen |= set(rel["audiences"])
    return sorted(
        ({"slug": s, "label": PROFESSIONS.get(s, s.title())} for s in seen),
        key=lambda x: x["label"],
    )


def learnable_home_rails(
    items: Sequence[LearnableItem],
    *,
    kids_only: bool = False,
    per_rail: int = 12,
) -> List[dict]:
    if kids_only:
        pool = search_learnable(items, kids_only=True, limit=500)["items"]
    else:
        pool = list(items)

    rails: List[dict] = []

    def rail(key: str, title: str, subset: Iterable[LearnableItem]) -> None:
        rows = list(subset)
        if rows:
            rails.append({
                "key": key,
                "title": title,
                "courses": [_item_as_catalog_dict(c) for c in rows[:per_rail]],
            })

    live = [c for c in pool if c.format == "live_class"]
    audio = [c for c in pool if c.format == "audio"]
    languages = [c for c in pool if c.source == "language"]
    games = [c for c in pool if c.format == "game"]

    rail("live", "Live interactive classes", sorted(live, key=lambda c: c.title))
    rail("new", "New this week", sorted(audio, key=lambda c: c.title))
    rail("audio", "Drive-safe audio classes", audio[:per_rail * 2])
    rail("languages", "Language learning", languages)
    rail("games", "Arcade practice", games)

    popular = sorted(pool, key=lambda c: (-c.popularity, c.title))
    rail("popular", "Popular now", popular)
    if len(popular) > per_rail:
        rail("trending", "Trending now", popular[per_rail : per_rail * 2])

    cats: Dict[str, List[LearnableItem]] = defaultdict(list)
    for c in pool:
        if c.format in ("program",):
            continue
        cats[c.category or c.subject].append(c)
    for cat in sorted(k for k in cats if k):
        rail(f"cat:{cat}", cat, sorted(cats[cat], key=lambda c: c.title))

    return rails


def _item_as_catalog_dict(item: LearnableItem) -> dict:
    return {
        "course_id": item.source_id,
        "title": item.title,
        "subject": item.subject,
        "category": item.category,
        "language": item.language,
        "audio_language": item.audio_language or item.language,
        "media_format": item.catalog_media_format(),
        "level": item.level,
        "duration_min": item.duration_min,
        "hands_on": item.hands_on,
        "preview": item.preview,
        "description": item.preview,
        "tags": item.tags,
        "access_tier": item.access_tier,
        "delivery_mode": "ai",
        "maturity_rating": item.maturity_rating,
        "popularity": item.popularity,
        "source": item.source,
        "format": item.format,
        "deep_link": item.deep_link,
        "global_id": item.id,
    }


def item_to_course_dict(item: LearnableItem) -> dict:
    """Backward-compatible Course-shaped dict for /courses/search."""
    return _item_as_catalog_dict(item)


def learnable_catalog_dicts(items: Sequence[LearnableItem]) -> List[dict]:
    return [
        {"course_id": c.source_id, "title": c.title, "subject": c.subject,
         "category": c.category, "tags": c.tags}
        for c in items
        if c.source in ("catalog", "audio", "lesson")
    ]
