"""Asynchronous batch translation of course text into the 26 target languages.

Each segment is translated off the event loop. A finished course language is
written immediately, so a rerun skips work that is already in the library.
A course that stops partway keeps the segments that succeeded.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, Iterable

from .course_translation_library import (
    TARGET_LANGUAGES,
    load_translation,
    save_translation,
    translation_path,
)
from .languages import normalize_language

# One chat call stays reliable around this size. Longer narration is split.
_DEFAULT_CHUNK_WORDS = 180
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


class CourseJob:
    def __init__(self, course_id: str, title: str, category: str, segments: list[dict[str, str]]) -> None:
        self.course_id = course_id
        self.title = title
        self.category = category
        self.segments = segments


def split_translation_text(text: str, max_words: int = _DEFAULT_CHUNK_WORDS) -> list[str]:
    """Split narration into chunks a single translation call can finish."""
    clean = " ".join((text or "").split())
    if not clean:
        return []
    if max_words < 1:
        raise ValueError("max_words must be >= 1")
    if len(clean.split()) <= max_words:
        return [clean]
    pieces: list[str] = []
    for sentence in _SENTENCE_BREAK.split(clean):
        words = sentence.split()
        if not words:
            continue
        if len(words) <= max_words:
            pieces.append(sentence)
            continue
        for start in range(0, len(words), max_words):
            pieces.append(" ".join(words[start : start + max_words]))
    packed: list[str] = []
    current: list[str] = []
    count = 0
    for piece in pieces:
        words = len(piece.split())
        if current and count + words > max_words:
            packed.append(" ".join(current))
            current = [piece]
            count = words
        else:
            current.append(piece)
            count += words
    if current:
        packed.append(" ".join(current))
    return packed


def _partial_path(course_id: str, language: str, root):
    path = translation_path(course_id, language, root)
    return path.with_name(f"{path.stem}.partial.json")


def _load_partial(course_id: str, language: str, root) -> list[dict[str, str]]:
    path = _partial_path(course_id, language, root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    kept: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        heading = str(row.get("heading") or "").strip()
        text = str(row.get("text") or "").strip()
        source_heading = str(row.get("source_heading") or "").strip()
        source_text = str(row.get("source_text") or "").strip()
        if heading and text and source_heading and source_text:
            kept.append(
                {
                    "heading": heading,
                    "text": text,
                    "kind": str(row.get("kind") or "narration"),
                    "source_heading": source_heading,
                    "source_text": source_text,
                }
            )
    return kept


def _save_partial(
    course: CourseJob,
    language: str,
    segments: list[dict[str, str]],
    root,
) -> None:
    path = _partial_path(course.course_id, language, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "course_id": course.course_id,
        "language": language,
        "segments": segments,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def translate_catalog(
    courses: Iterable[CourseJob],
    languages: Iterable[str],
    translator: Callable[[str, str, str], Awaitable[str]],
    *,
    concurrency: int = 4,
    force: bool = False,
    root=None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Translate every course into each target language.

    ``translator`` takes ``(text, source, target)`` and returns the translation,
    or "" when that call should not be stored. Segments that succeed are kept
    in a partial file when a later segment fails, and the next run continues
    from that file.
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

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    async def one(course: CourseJob, language: str) -> None:
        async with semaphore:
            if not force and load_translation(course.course_id, language, root):
                counts["skipped"] += 1
                report(f"{course.course_id}\t{language}\tskipped")
                return
            saved = {} if force else {
                (row["source_heading"], row["source_text"]): row
                for row in _load_partial(course.course_id, language, root)
            }
            segments: list[dict[str, str]] = []
            stored: list[dict[str, str]] = []
            for row in course.segments:
                heading = str(row.get("heading") or "").strip()
                text = str(row.get("text") or "").strip()
                if not heading or not text:
                    continue
                kind = str(row.get("kind") or "narration")
                previous = saved.get((heading, text))
                if previous:
                    segments.append(
                        {"heading": previous["heading"], "text": previous["text"], "kind": kind}
                    )
                    stored.append(previous)
                    continue
                translated_heading = (await translator(heading, "en", language)).strip()
                translated_text = (await translator(text, "en", language)).strip()
                if not translated_heading or not translated_text:
                    if stored:
                        _save_partial(course, language, stored, root)
                    counts["failed"] += 1
                    report(f"{course.course_id}\t{language}\tfailed")
                    return
                done = {
                    "heading": translated_heading,
                    "text": translated_text,
                    "kind": kind,
                    "source_heading": heading,
                    "source_text": text,
                }
                segments.append({"heading": translated_heading, "text": translated_text, "kind": kind})
                stored.append(done)
                _save_partial(course, language, stored, root)
            if not segments:
                counts["failed"] += 1
                report(f"{course.course_id}\t{language}\tfailed")
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
            partial = _partial_path(course.course_id, language, root)
            if partial.is_file():
                partial.unlink()
            counts["written"] += 1
            report(f"{course.course_id}\t{language}\twritten")

    await asyncio.gather(*(one(course, language) for course in jobs for language in codes))
    return counts
