#!/usr/bin/env python3
"""Translate every course into the 26 non-English platform languages.

The voice agent reads the finished files as its class library. A rerun skips
a course language that is already stored. Translation calls run concurrently.

  python3 scripts/translate_courses_batch.py --limit 1 --language es
  python3 scripts/translate_courses_batch.py --concurrency 6 --verbose
  python3 scripts/translate_courses_batch.py --concurrency 8 --verbose

This is batch *translation* of course text (not model training). Without
--verbose the script prints a start line, a heartbeat every 25 completions,
then a final summary. Prefer --verbose when debugging failures.

xAI at high concurrency often times out (default TRANSLATION_TIMEOUT_S=15).
This script raises the timeout to 60s when unset, retries empty/timeout
responses, and recommends concurrency around 6–8 — not 26.

NLLB via the speech gateway is preferred when SPEECH_BASE_URL /
TRANSLATION_BASE_URL is set. The gateway's default rate limit is
RATE_LIMIT=120 per RATE_LIMIT_WINDOW=60s — batch work will 429 under
concurrency ≥ ~4 unless you raise it or set RATE_LIMIT_DISABLED=1 on the
speech process (local batch only).

Set XAI_API_KEY, or SPEECH_BASE_URL / TRANSLATION_BASE_URL for the NLLB gateway.
AOEP_COURSE_TRANSLATION_DIR chooses the output folder. The default is
~/.cache/aoep/course_translations.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
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


def engine_translator(*, retries: int = 4, verbose: bool = False):
    from theodore_audio_translation_lab.providers import TranslationEngine

    # Batch segments are longer than chat utterances; 15s dies under load.
    os.environ.setdefault("TRANSLATION_TIMEOUT_S", "60")

    engine = TranslationEngine()
    if not engine.gateway_url and not engine.xai_key:
        raise SystemExit(
            "Set XAI_API_KEY or SPEECH_BASE_URL / TRANSLATION_BASE_URL before translating."
        )
    print(
        f"translator: provider={'nllb+' if engine.gateway_url else ''}"
        f"{'xai' if engine.xai_key else 'none'} "
        f"model={engine.xai_model!r} timeout_s={engine.timeout_s} retries={retries}",
        flush=True,
    )

    async def translate(text: str, source: str, target: str) -> str:
        last_warning = ""
        for attempt in range(1, retries + 1):
            result = await asyncio.to_thread(engine.translate, text, source, target)
            if getattr(result, "translated", False):
                return str(getattr(result, "text", "") or "")
            last_warning = str(getattr(result, "warning", "") or result.provider)
            if attempt < retries:
                low = last_warning.lower()
                # Speech gateway token bucket → HTTP 429. Back off hard so the
                # whole concurrency storm doesn't burn retries in <2s.
                if "429" in low or "rate limit" in low:
                    delay = min(90.0, 8.0 * (2 ** (attempt - 1)))
                else:
                    delay = min(30.0, 1.5**attempt)
                if verbose and (attempt == 1 or "429" in low):
                    print(
                        f"  retry {attempt}/{retries} {source}->{target}: "
                        f"{last_warning[:160]} (sleep {delay:.0f}s)",
                        flush=True,
                    )
                await asyncio.sleep(delay)
        if verbose:
            print(f"  give up {source}->{target}: {last_warning[:200]}", flush=True)
        return ""

    return translate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", action="append", default=None, help="Target language. Repeatable. Default: all 26.")
    parser.add_argument(
        "--course",
        action="append",
        default=None,
        help="Only these course ids (repeatable). Prefix match if value ends with '-'.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Stop after this many audio courses. 0 means all.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="Parallel course×language jobs (default 6; 26 usually times out on xAI).",
    )
    parser.add_argument("--force", action="store_true", help="Translate again even when a file exists.")
    parser.add_argument("--audio-only", action="store_true", help="Skip the Course Studio catalog.")
    parser.add_argument("--dry-run", action="store_true", help="Print the courses and languages, then stop.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print each finished course×language (written/skipped/failed) with a running tally.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retries per segment on empty/timeout (default 4).",
    )
    return parser


def _filter_courses(jobs: list[CourseJob], selectors: list[str] | None) -> list[CourseJob]:
    if not selectors:
        return jobs
    out: list[CourseJob] = []
    for job in jobs:
        for sel in selectors:
            s = (sel or "").strip()
            if not s:
                continue
            if s.endswith("-") and job.course_id.startswith(s):
                out.append(job)
                break
            if job.course_id == s:
                out.append(job)
                break
    return out


def main() -> None:
    args = build_parser().parse_args()
    languages = args.language or list(TARGET_LANGUAGES)
    jobs = audio_jobs(args.limit)
    if not args.audio_only:
        jobs.extend(studio_jobs())
    jobs = _filter_courses(jobs, args.course)
    if args.course and not jobs:
        raise SystemExit(f"no courses matched --course {args.course!r}")
    out = library_dir()
    total = len(jobs) * len(languages)
    print(f"{len(jobs)} courses x {len(languages)} languages ({total} jobs) -> {out}", flush=True)
    if args.concurrency > 12:
        print(
            f"warning: concurrency={args.concurrency} is high for xAI; "
            "expect timeouts. Prefer 6–8.",
            flush=True,
        )
    if args.dry_run:
        for job in jobs:
            print(f"{job.course_id}\t{job.category}\t{job.title}\t{len(job.segments)} segments")
        return

    def on_progress(info: dict) -> None:
        if not args.verbose:
            # Heartbeat every 25 completions so a quiet run still proves life.
            if int(info["done"]) % 25 != 0 and info["event"] != "failed":
                return
        reason = str(info.get("reason") or "")
        suffix = f" — {reason}" if reason and info["event"] == "failed" else ""
        print(
            f"[{info['done']}/{info['total']}] {info['event']:7} "
            f"{info['course_id']} -> {info['language']} "
            f"(written={info['written']} skipped={info['skipped']} failed={info['failed']})"
            f"{suffix}",
            flush=True,
        )

    started = time.time()
    counts = asyncio.run(
        translate_catalog(
            jobs,
            languages,
            engine_translator(retries=max(1, args.retries), verbose=args.verbose),
            concurrency=args.concurrency,
            force=args.force,
            progress=on_progress,
        )
    )
    elapsed = time.time() - started
    print(
        f"done: written {counts['written']}, skipped {counts['skipped']}, "
        f"failed {counts['failed']} in {elapsed/60:.1f}m -> {out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
