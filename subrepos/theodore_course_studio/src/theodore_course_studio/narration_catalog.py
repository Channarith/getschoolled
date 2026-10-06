"""Stable catalog of courses that the narration pipeline can speak.

Builtin coverage is the certification-prep catalog (16 lessons, including the
sign banks) plus the eight early-learning lessons. Persisted studio courses
are included only when a caller asks for them. Slide keys stay on the English
identity of a slide so a later translation cannot rename the audio object.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .child_i18n import SOUND_SPECIFIC_TOPICS
from .slide_keys import slide_key_for
from .studio_languages import SUPPORTED_LANGUAGES, normalize_language

CERT_COURSE_COUNT = 16
EARLY_COURSE_COUNT = 8

_KIND_CERT = "cert"
_KIND_EARLY = "early"
_KIND_PERSISTED = "persisted"


@dataclass(frozen=True)
class CatalogSlide:
    """One speakable slide in catalog order."""

    course_kind: str
    course_id: str
    course_title: str
    slide_index: int
    slide_key: str
    title: str
    body: str
    narration: str
    source_language: str = "en"
    sound_specific: bool = False
    # letter_sounds or sight_words when this slide teaches a language-specific skill.
    sound_topic: str = ""


@dataclass(frozen=True)
class CatalogCourse:
    course_kind: str
    course_id: str
    title: str
    slides: tuple[CatalogSlide, ...]


def canonical_hash(payload: dict) -> str:
    """Stable SHA-256 of a JSON object, independent of key order."""
    blob = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def safe_token(slide_key: str) -> str:
    """Filesystem-safe form of a slide key. The full key is still the identity."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", slide_key).strip("-._")
    if not cleaned:
        cleaned = "slide"
    if len(cleaned) > 160:
        digest = hashlib.sha256(slide_key.encode("utf-8")).hexdigest()[:16]
        cleaned = f"{cleaned[:140]}-{digest}"
    return cleaned


def iter_slides(
    courses: list[CatalogCourse], *, limit: int = 0
) -> list[CatalogSlide]:
    """Flatten courses in catalog order. ``limit`` keeps the first N slides."""
    slides: list[CatalogSlide] = []
    for course in courses:
        for slide in course.slides:
            slides.append(slide)
            if limit and len(slides) >= limit:
                return slides
    return slides


def enumerate_courses(
    *,
    include_persisted: bool = False,
    data_dir: Path | None = None,
    limit: int = 0,
) -> list[CatalogCourse]:
    """Return cert courses, then early courses, then persisted courses.

    ``limit`` stops once that many slides have been collected. A limit of 0
    returns the full selection. Persisted courses are read from the studio
    course store under ``data_dir`` (the default studio data dir when omitted).
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")
    courses: list[CatalogCourse] = []
    used: set[str] = set()
    remaining = limit
    for course in _builtin_courses(used):
        kept, remaining = _take(course, remaining, limit)
        if kept.slides:
            courses.append(kept)
            used.update(slide.slide_key for slide in kept.slides)
        if limit and remaining <= 0:
            return courses
    if include_persisted and (not limit or remaining > 0):
        for course in _persisted_courses(data_dir, used):
            kept, remaining = _take(course, remaining, limit)
            if kept.slides:
                courses.append(kept)
            if limit and remaining <= 0:
                break
    return courses


def _take(
    course: CatalogCourse, remaining: int, limit: int
) -> tuple[CatalogCourse, int]:
    if not limit:
        return course, remaining
    if remaining <= 0:
        return CatalogCourse(course.course_kind, course.course_id, course.title, ()), 0
    if len(course.slides) <= remaining:
        return course, remaining - len(course.slides)
    return (
        CatalogCourse(
            course.course_kind,
            course.course_id,
            course.title,
            course.slides[:remaining],
        ),
        0,
    )


def _builtin_courses(used: set[str]):
    yield from _cert_courses(used)
    yield from _early_courses(used)


def _claim(base: str, used: set[str]) -> str:
    key = base or "slide"
    if key not in used:
        used.add(key)
        return key
    n = 2
    while f"{key}-{n}" in used:
        n += 1
    claimed = f"{key}-{n}"
    used.add(claimed)
    return claimed


def _cert_courses(used: set[str]):
    from .certification_prep import build_cert_course, list_cert_courses

    for option in list_cert_courses():
        course = build_cert_course(lesson_id=option.lesson_id, language="en")
        slides: list[CatalogSlide] = []
        for slide in course.slides:
            base = (slide.slide_key or "").strip() or slide_key_for(
                slide.title, lesson_id=option.lesson_id
            )
            slides.append(
                CatalogSlide(
                    course_kind=_KIND_CERT,
                    course_id=option.lesson_id,
                    course_title=option.title,
                    slide_index=slide.index,
                    slide_key=_claim(base, used),
                    title=slide.title.strip(),
                    body=slide.body.strip(),
                    narration=(slide.narration or slide.body).strip(),
                    source_language="en",
                )
            )
        yield CatalogCourse(_KIND_CERT, option.lesson_id, option.title, tuple(slides))


def _early_courses(used: set[str]):
    from .early_learning import build_early_course, list_early_courses

    for option in list_early_courses():
        course = build_early_course(
            level=option.level,
            topic_id=option.topic_id,
            language="en",
            allow_xai_translation=False,
        )
        topic = option.topic_id if option.topic_id in SOUND_SPECIFIC_TOPICS else ""
        slides: list[CatalogSlide] = []
        for slide in course.slides:
            base = (slide.slide_key or "").strip() or slide_key_for(
                slide.title, lesson_id=option.topic_id
            )
            slides.append(
                CatalogSlide(
                    course_kind=_KIND_EARLY,
                    course_id=option.topic_id,
                    course_title=option.title,
                    slide_index=slide.index,
                    slide_key=_claim(base, used),
                    title=slide.title.strip(),
                    body=slide.body.strip(),
                    narration=(slide.narration or slide.body).strip(),
                    source_language="en",
                    sound_specific=bool(topic),
                    sound_topic=topic,
                )
            )
        yield CatalogCourse(_KIND_EARLY, option.topic_id, option.title, tuple(slides))


def _canonical_source_language(language: str) -> str:
    code = (language or "").strip().lower().replace("_", "-").split("-")[0]
    if code in SUPPORTED_LANGUAGES:
        return code
    return normalize_language(code)


def _persisted_sound_topic(course_id: str, tags: list[str]) -> str:
    if course_id in SOUND_SPECIFIC_TOPICS:
        return course_id
    for tag in tags:
        if tag in SOUND_SPECIFIC_TOPICS:
            return tag
    return ""


def _persisted_courses(data_dir: Path | None, used: set[str]):
    from .generate import CourseBuilder

    builder = CourseBuilder(data_dir=data_dir)
    for course in builder.list_courses():
        source_language = _canonical_source_language(course.language)
        slides: list[CatalogSlide] = []
        for slide in course.slides:
            title = (slide.title or "").strip()
            body = (slide.body or "").strip()
            narration = (slide.narration or body).strip()
            if not title and not body and not narration:
                continue
            spoken = (slide.spoken_language or "").strip()
            slide_language = (
                _canonical_source_language(spoken) if spoken else source_language
            )
            raw = (slide.slide_key or "").strip() or slide_key_for(
                title or narration or "slide", lesson_id=course.course_id
            )
            if raw in used:
                raw = f"persisted.{course.course_id}.{raw}"
            topic = _persisted_sound_topic(course.course_id, list(slide.tags))
            slides.append(
                CatalogSlide(
                    course_kind=_KIND_PERSISTED,
                    course_id=course.course_id,
                    course_title=course.title,
                    slide_index=slide.index,
                    slide_key=_claim(raw, used),
                    title=title or narration,
                    body=body or narration,
                    narration=narration or body or title,
                    source_language=slide_language,
                    sound_specific=bool(topic),
                    sound_topic=topic,
                )
            )
        if slides:
            yield CatalogCourse(
                _KIND_PERSISTED, course.course_id, course.title, tuple(slides)
            )
