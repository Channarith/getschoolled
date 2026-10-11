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
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, int]:
    """Translate every course into each target language.

    ``translator`` takes ``(text, source, target)`` and returns the translation,
    or "" when that call should not be stored.

    ``progress``, when set, is called after each course×language finishes with
    ``{event, course_id, language, done, total, written, skipped, failed, reason}``.
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
    total = max(1, len(jobs) * len(codes))
    done = 0
    lock = asyncio.Lock()

    def _emit(event: str, course_id: str, language: str, reason: str = "") -> None:
        if progress is None:
            return
        progress(
            {
                "event": event,
                "course_id": course_id,
                "language": language,
                "done": done,
                "total": total,
                "written": counts["written"],
                "skipped": counts["skipped"],
                "failed": counts["failed"],
                "reason": reason,
            }
        )

    async def one(course: CourseJob, language: str) -> None:
        nonlocal done
        async with semaphore:
            event = "written"
            try:
                if not force and load_translation(course.course_id, language, root):
                    async with lock:
                        counts["skipped"] += 1
                        done += 1
                        event = "skipped"
                    _emit(event, course.course_id, language)
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
                        async with lock:
                            counts["failed"] += 1
                            done += 1
                            event = "failed"
                        _emit(
                            event,
                            course.course_id,
                            language,
                            reason="empty translation (timeout/rate-limit/provider error)",
                        )
                        return
                    segments.append(
                        {
                            "heading": translated_heading,
                            "text": translated_text,
                            "kind": str(row.get("kind") or "narration"),
                        }
                    )
                if not segments:
                    async with lock:
                        counts["failed"] += 1
                        done += 1
                        event = "failed"
                    _emit(event, course.course_id, language, reason="no translatable segments")
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
                async with lock:
                    counts["written"] += 1
                    done += 1
                    event = "written"
                _emit(event, course.course_id, language)
            except Exception as exc:  # noqa: BLE001 — count and keep the batch going
                async with lock:
                    counts["failed"] += 1
                    done += 1
                    event = "failed"
                _emit(event, course.course_id, language, reason=f"{type(exc).__name__}: {exc}")

    await asyncio.gather(*(one(course, language) for course in jobs for language in codes))
    return counts
