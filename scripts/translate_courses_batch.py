#!/usr/bin/env python3
"""Translate every course into the 26 non-English platform languages.

The voice agent reads the finished files as its class library. A rerun skips
a course language that is already stored. Translation calls run concurrently.

  python3 scripts/translate_courses_batch.py --limit 1 --language es
  python3 scripts/translate_courses_batch.py --concurrency 6

Set XAI_API_KEY, or SPEECH_BASE_URL / TRANSLATION_BASE_URL for the NLLB gateway.
AOEP_COURSE_TRANSLATION_DIR chooses the output folder. The default is
~/.cache/aoep/course_translations.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
for extra in (
    ROOT / "subrepos" / "theodore_audio_translation_lab" / "src",
    ROOT / "subrepos" / "theodore_course_studio" / "src",
):
    if extra.is_dir():
        sys.path.insert(0, str(extra))

from aoep_shared.audio_courses import build_catalog  # noqa: E402
from aoep_shared.course_translation_batch import CourseJob, translate_catalog  # noqa: E402
from aoep_shared.course_translation_library import TARGET_LANGUAGES, library_dir  # noqa: E402


def audio_jobs(limit: int) -> list[CourseJob]:
    catalog = build_catalog("en", "en")
    jobs: list[CourseJob] = []
    for course in catalog:
        if course.id.startswith("lang-"):
            continue
        jobs.append(
            CourseJob(
                course.id,
                course.title.replace(" (audio)", "").strip(),
                course.category,
                [
                    {"heading": segment.heading, "text": segment.text, "kind": segment.kind}
                    for segment in course.segments
                    if segment.heading and segment.text
                ],
            )
        )
        if limit and len(jobs) >= limit:
            break
    return jobs


def studio_jobs() -> list[CourseJob]:
    try:
        from theodore_course_studio.narration_catalog import enumerate_courses
    except Exception as exc:  # noqa: BLE001
        print(f"studio catalog skipped: {exc}", file=sys.stderr)
        return []
    jobs: list[CourseJob] = []
    for course in enumerate_courses():
        segments = []
        for slide in course.slides:
            text = (slide.narration or slide.body or "").strip()
            heading = (slide.title or "").strip()
            if heading and text:
                segments.append({"heading": heading, "text": text, "kind": "narration"})
        if not segments:
            continue
        jobs.append(
            CourseJob(
                course.course_id,
                course.title,
                course.course_kind,
                segments,
            )
        )
    return jobs


def engine_translator():
    from theodore_audio_translation_lab.providers import TranslationEngine

    engine = TranslationEngine()
    if not engine.gateway_url and not engine.xai_key:
        raise SystemExit(
            "Set XAI_API_KEY or SPEECH_BASE_URL / TRANSLATION_BASE_URL before translating."
        )

    async def translate(text: str, source: str, target: str) -> str:
        result = await asyncio.to_thread(engine.translate, text, source, target)
        if not getattr(result, "translated", False):
            return ""
        return str(getattr(result, "text", "") or "")

    return translate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", action="append", default=None, help="Target language. Repeatable. Default: all 26.")
    parser.add_argument("--limit", type=int, default=0, help="Stop after this many audio courses. 0 means all.")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--force", action="store_true", help="Translate again even when a file exists.")
    parser.add_argument("--audio-only", action="store_true", help="Skip the Course Studio catalog.")
    parser.add_argument("--dry-run", action="store_true", help="Print the courses and languages, then stop.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    languages = args.language or list(TARGET_LANGUAGES)
    jobs = audio_jobs(args.limit)
    if not args.audio_only:
        jobs.extend(studio_jobs())
    print(f"{len(jobs)} courses x {len(languages)} languages -> {library_dir()}")
    if args.dry_run:
        for job in jobs:
            print(f"{job.course_id}\t{job.category}\t{job.title}\t{len(job.segments)} segments")
        return
    counts = asyncio.run(
        translate_catalog(
            jobs,
            languages,
            engine_translator(),
            concurrency=args.concurrency,
            force=args.force,
        )
    )
    print(
        f"written {counts['written']}, skipped {counts['skipped']}, failed {counts['failed']}"
    )


if __name__ == "__main__":
    main()
