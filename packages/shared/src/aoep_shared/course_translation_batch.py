"""Asynchronous batch translation of course text into the 26 target languages.

Each segment is translated off the event loop. A finished course language is
written immediately, so a rerun skips work that is already in the library.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable

from .course_translation_library import TARGET_LANGUAGES, load_translation, save_translation
from .languages import normalize_language


class CourseJob:
    def __init__(self, course_id: str, title: str, category: str, segments: list[dict[str, str]]) -> None:
        self.course_id = course_id
        self.title = title
        self.category = category
        self.segments = segments


async def translate_catalog(
    courses: Iterable[CourseJob],
    languages: Iterable[str],
    translator: Callable[[str, str, str], Awaitable[str]],
    *,
    concurrency: int = 4,
    force: bool = False,
    root=None,
) -> dict[str, int]:
    """Translate every course into each target language.

    ``translator`` takes ``(text, source, target)`` and returns the translation,
    or "" when that call should not be stored.
    """
    codes = []
    for language in languages:
        code = normalize_language(language)
        if code not in TARGET_LANGUAGES:
            raise ValueError(f"unsupported target language: {language}")
        if code not in codes:
            codes.append(code)
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    jobs = list(courses)
    counts = {"written": 0, "skipped": 0, "failed": 0}
    semaphore = asyncio.Semaphore(concurrency)

    async def one(course: CourseJob, language: str) -> None:
        async with semaphore:
            if not force and load_translation(course.course_id, language, root):
                counts["skipped"] += 1
                return
            segments: list[dict[str, str]] = []
            for row in course.segments:
                heading = str(row.get("heading") or "").strip()
                text = str(row.get("text") or "").strip()
                if not heading or not text:
                    continue
                translated_heading = (await translator(heading, "en", language)).strip()
                translated_text = (await translator(text, "en", language)).strip()
                if not translated_heading or not translated_text:
                    counts["failed"] += 1
                    return
                segments.append(
                    {
                        "heading": translated_heading,
                        "text": translated_text,
                        "kind": str(row.get("kind") or "narration"),
                    }
                )
            if not segments:
                counts["failed"] += 1
                return
            title = (await translator(course.title, "en", language)).strip() or course.title
            save_translation(
                {
                    "course_id": course.course_id,
                    "title": title,
                    "category": course.category,
                    "language": language,
                    "source": "batch",
                    "segments": segments,
                },
                root,
            )
            counts["written"] += 1

    await asyncio.gather(*(one(course, language) for course in jobs for language in codes))
    return counts
