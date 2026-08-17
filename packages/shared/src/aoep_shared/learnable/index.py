"""Build and search a merged index of all learnable content."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from aoep_shared.audio_courses import AudioCourse, build_catalog
from aoep_shared.course_artwork import resolve_course_poster_from_mapping
from aoep_shared.games import GAME_SUBJECTS
from aoep_shared.language_learning import language_list

from .lessons import lesson_category, lesson_duration_min, load_sample_lessons

from .models import LearnableItem

_BEGINNER_LESSONS: frozenset = frozenset({
    "arithmetic", "intro-to-fractions", "intro-to-photosynthesis", "intro-physics",
    "intro-python", "intro-science", "drivers-permit-test", "ca-dmv-permit-basics",
    "ca-dmv-permit-signs", "ca-dmv-permit-sharing", "cpr-first-aid-certification",
    "food-handler-safety", "ca-alameda-food-handler-hygiene",
    "ca-alameda-food-handler-temps", "ca-alameda-food-handler-contamination",
    "sexual-harassment-prevention", "fire-safety-training",
    "workplace-ethics", "diversity-equity-inclusion",
    "workplace-violence-prevention", "social-media-at-work", "security-policies-awareness",
    "data-privacy-workplace", "anti-bribery-corruption", "lab-safety-fundamentals",
    "automotive-safety-awareness", "liquid-cooling-thermal-materials",
    "trade-compliance-basics",
})
_ADVANCED_LESSONS: frozenset = frozenset({
    "calculus-2", "differential-equations", "linear-algebra", "math-olympiad",
    "comptia-a-plus", "ase-automotive-certification", "pharmacy-technician-certification",
    "real-estate-license-prep",
})

CERTIFIABLE_LESSONS = {
    "sexual-harassment-prevention": ("Salareen", 1.0),
    "osha-general-safety": ("OSHA", 2.0),
    "fire-safety-training": ("Salareen", 0.5),
    "hipaa-privacy-security": ("HHS", 2.0),
    "food-handler-safety": ("CA Food Handler Card (prep)", 1.0),
    "ca-alameda-food-handler-hygiene": ("CA Food Handler Card (prep)", 0.5),
    "ca-alameda-food-handler-temps": ("CA Food Handler Card (prep)", 0.5),
    "ca-alameda-food-handler-contamination": ("CA Food Handler Card (prep)", 0.5),
    "diversity-equity-inclusion": ("Salareen", 1.0),
    "workplace-ethics": ("Salareen", 1.0),
    "osha-forklift-safety": ("OSHA", 1.0),
    "cybersecurity": ("Salareen", 1.5),
    "devops": ("Salareen", 2.0),
    "workplace-violence-prevention": ("Salareen", 1.0),
    "security-policies-awareness": ("Salareen", 0.5),
    "trade-compliance-basics": ("Salareen", 1.0),
    "social-media-at-work": ("Salareen", 0.5),
    "export-control-us-regulations": ("Salareen", 1.5),
    "liquid-cooling-thermal-materials": ("Salareen", 1.0),
    "data-privacy-workplace": ("Salareen", 1.0),
    "anti-bribery-corruption": ("Salareen", 1.0),
    "lab-safety-fundamentals": ("Salareen", 1.0),
    "automotive-safety-awareness": ("Salareen", 0.5),
    # Professional certification prep courses
    "comptia-a-plus": ("CompTIA", 3.0),
    "hvac-epa-certification": ("EPA", 2.5),
    "drivers-permit-test": ("CA DMV (prep)", 1.0),
    "ca-dmv-permit-basics": ("CA DMV (prep)", 0.5),
    "ca-dmv-permit-signs": ("CA DMV (prep)", 0.5),
    "ca-dmv-permit-sharing": ("CA DMV (prep)", 0.5),
    "ase-automotive-certification": ("ASE", 3.0),
    "pharmacy-technician-certification": ("PTCE", 3.0),
    "real-estate-license-prep": ("NAR", 3.0),
    "cpr-first-aid-certification": ("AHA", 0.5),
    "security-guard-certification": ("Salareen", 2.0),
}


def _load_course_packs() -> List[dict]:
    """Course records merged from content packs (kind=courses)."""
    try:
        from aoep_shared.content_packs import load_records

        return load_records("courses")
    except Exception:  # pragma: no cover - defensive
        return []


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
        custom_deep_link = getattr(c, "deep_link", "") or ""
        core_skill = bool(getattr(c, "core_skill", False))
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
        custom_deep_link = c.get("deep_link", "") or ""
        core_skill = bool(c.get("core_skill", False))
    fmt = "audio" if media == "audio" else media
    deep = custom_deep_link or (
        f"/drive?course={course_id}" if fmt == "audio" else f"/watch?course={course_id}"
    )
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
        core_skill=core_skill,
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
        audience = getattr(lesson, "audience", "general") or "general"
    else:
        slides = lesson.get("slides", [])
        lesson_id = lesson["lesson_id"]
        title = lesson["title"]
        language = lesson.get("language", "en")
        audience = lesson.get("audience", "general") or "general"
    category = lesson_category(lesson_id, title)
    duration = lesson_duration_min(slides)
    preview = slides[0].body[:160] if slides else ""
    tags = ["live-class"]
    if lesson_id.startswith("python"):
        tags.append("python")
    audiences = [audience] if audience and audience != "general" else []
    if audience == "corporate":
        tags.append("corporate")
    certifiable = False
    certification_body = ""
    ceu_credits = 0.0
    if lesson_id in CERTIFIABLE_LESSONS:
        certification_body, ceu_credits = CERTIFIABLE_LESSONS[lesson_id]
        certifiable = True
    if certifiable:
        tags.append("certifiable")
        if certification_body:
            tags.append(certification_body.lower())
    deep = (
        f"/corporate/learn?lesson={lesson_id}"
        if audience == "corporate"
        else f"/class?lesson={lesson_id}"
    )
    return LearnableItem(
        id=f"lesson:{lesson_id}",
        source="lesson",
        source_id=lesson_id,
        title=title,
        subtitle=f"{len(slides)} slides",
        category=category,
        subject=category,
        format="live_class",
        level="beginner" if (lesson_id.startswith("intro") or lesson_id in _BEGINNER_LESSONS)
        else "advanced" if lesson_id in _ADVANCED_LESSONS
        else "intermediate",
        language=language,
        duration_min=duration,
        tags=tags,
        audiences=audiences,
        preview=preview,
        deep_link=deep,
        popularity=10,
        certifiable=certifiable,
        certification_body=certification_body,
        ceu_credits=ceu_credits,
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
        deep_link=f"/corporate?program={program_id}",
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

    # Data-driven course packs (drop-in JSON growth; no code changes needed).
    for c in _load_course_packs():
        cid = c.get("course_id")
        if not cid or cid in catalog_ids:
            continue
        try:
            item = _from_catalog_course(c)
        except (KeyError, TypeError):
            continue
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
    access_tier: Optional[str] = None,
    kids_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    rows: List[LearnableItem] = list(items)

    if kids_only:
        def _is_kids_safe(c: "LearnableItem") -> bool:
            # Kids Academy is deliberately curator-gated. Broad categories such
            # as science, history, languages, or "beginner" are not evidence that
            # material was authored for young children. Games remain available,
            # while every non-game item must be explicitly rated for kids.
            return c.format == "game" or c.maturity_rating == "kids"

        rows = [c for c in rows if _is_kids_safe(c)]

    if audience or core_skill is not None:
        from aoep_shared.skills_taxonomy import course_relevance

        filtered: List[LearnableItem] = []
        for c in rows:
            rel = course_relevance({
                "title": c.title, "subject": c.subject, "category": c.category,
                "tags": c.tags, "audiences": c.audiences,
                # The explicit catalog flag wins; the literal tag is a fallback
                # for sources that never set the field.
                "core_skill": c.core_skill or "core_skill" in c.tags,
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
        # Accept both the raw format and the mapped legacy vocabulary the
        # result cards display (catalog_media_format) — a UI round-tripping
        # the badge it renders ("interactive", "text") used to get zero rows.
        if format and not (
            _matches_eq(c.format, format) or _matches_eq(c.catalog_media_format(), format)
        ):
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
        if not _matches_eq(c.access_tier, access_tier):
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
            "core_skill": c.core_skill or "core_skill" in c.tags,
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
        pool = search_learnable(items, kids_only=True, limit=2000)["items"]
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

    games = [c for c in pool if c.format == "game"]
    if kids_only:
        learning = [c for c in pool if c.format != "game"]
        rail(
            "kids-learning",
            "Picture, video & animation learning",
            sorted(learning, key=lambda c: (-c.popularity, c.title)),
        )
        rail("games", "Learning games", sorted(games, key=lambda c: c.title))
        return rails

    live = [c for c in pool if c.format == "live_class"]
    audio = [c for c in pool if c.format == "audio"]
    languages = [c for c in pool if c.source == "language"]
    rail("live", "Live interactive classes", sorted(live, key=lambda c: c.title))
    rail("new", "New this week", audio)
    rail("audio", "Drive-safe audio classes", sorted(audio, key=lambda c: -c.popularity))
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
    base = {
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
        "certifiable": item.certifiable,
        "certification_body": item.certification_body,
        "ceu_credits": item.ceu_credits,
    }
    base["thumbnail"] = resolve_course_poster_from_mapping({**base, "format": item.format})
    return base


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
