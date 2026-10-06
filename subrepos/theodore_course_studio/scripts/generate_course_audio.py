#!/usr/bin/env python3
"""Generate translated course narration and publish an audio manifest.

Stages
  translate  fill missing title/body/narration through configured xAI
  render     neural_tts.synthesize_course, then ffprobe the clip
  upload     aoep_shared ProviderFactory object store, then publish

Re-running a stage skips slides already cached, rendered, or uploaded.
manifest.json is replaced only when every selected slide, language, and
gender has a valid uploaded record.

Usage
  python3 scripts/generate_course_audio.py translate --language es --limit 2
  python3 scripts/generate_course_audio.py render --language es --gender female
  python3 scripts/generate_course_audio.py upload --language es --gender female
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SHARED = ROOT.parents[1] / "packages" / "shared" / "src"
if SHARED.is_dir() and str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from theodore_course_studio.narration_catalog import (  # noqa: E402
    enumerate_courses,
    iter_slides,
)
from theodore_course_studio.narration_manifest import (  # noqa: E402
    GENDERS,
    AudioPipelineError,
    IncompleteManifest,
    build_record,
    open_object_store,
    publish_manifest,
    read_sidecar,
    render_audio,
    require_translations,
    upload_audio,
    upload_manifest,
)
from theodore_course_studio.narration_translate import (  # noqa: E402
    TranslationError,
    canonical_language,
    translate_slides,
)
from theodore_course_studio.studio_languages import SUPPORTED_LANGUAGES  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate, render, and upload the course narration manifest."
    )
    parser.add_argument(
        "stage",
        choices=("translate", "render", "upload"),
        help="pipeline stage to run",
    )
    parser.add_argument(
        "--language",
        action="append",
        default=None,
        help="language code to process (repeatable; default: all 27)",
    )
    parser.add_argument(
        "--gender",
        action="append",
        choices=GENDERS,
        default=None,
        help="voice to render or upload (repeatable; default: female and male)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process only the first N catalog slides (0 means all)",
    )
    parser.add_argument(
        "--include-persisted",
        action="store_true",
        help="add courses saved in the studio data directory",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="studio data directory used when --include-persisted is set",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="resume directory (default: COURSE_AUDIO_WORK_DIR or the user cache)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="maximum slides per xAI translation request",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="parallel render workers",
    )
    return parser


def work_dir_for(args: argparse.Namespace) -> Path:
    if args.work_dir is not None:
        return args.work_dir.expanduser()
    override = os.environ.get("COURSE_AUDIO_WORK_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "theodore-course-studio" / "course-audio"


def selected_languages(values: list[str] | None) -> list[str]:
    if not values:
        return list(SUPPORTED_LANGUAGES)
    chosen: list[str] = []
    for value in values:
        code = canonical_language(value)
        if code not in chosen:
            chosen.append(code)
    return chosen


def selected_genders(values: list[str] | None) -> list[str]:
    if not values:
        return list(GENDERS)
    chosen: list[str] = []
    for value in values:
        if value not in chosen:
            chosen.append(value)
    return chosen


def selected_slides(args: argparse.Namespace):
    if args.limit < 0:
        raise ValueError("limit must be >= 0")
    courses = enumerate_courses(
        include_persisted=bool(args.include_persisted),
        data_dir=args.data_dir,
        limit=args.limit,
    )
    return iter_slides(courses, limit=args.limit)


def translations_dir(work_dir: Path) -> Path:
    return work_dir / "translations"


def cmd_translate(args: argparse.Namespace) -> int:
    languages = selected_languages(args.language)
    slides = selected_slides(args)
    texts = translate_slides(
        slides,
        languages,
        cache_dir=translations_dir(work_dir_for(args)),
        batch_size=args.batch_size,
    )
    print(
        f"translated={len(texts)} slides={len(slides)} "
        f"languages={','.join(languages)}"
    )
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    work_dir = work_dir_for(args)
    languages = selected_languages(args.language)
    genders = selected_genders(args.gender)
    slides = selected_slides(args)
    texts = require_translations(translations_dir(work_dir), slides, languages)
    clips = render_audio(
        texts,
        genders=genders,
        work_dir=work_dir,
        workers=args.workers,
    )
    print(f"rendered={len(clips)} workers={args.workers}")
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    work_dir = work_dir_for(args)
    languages = selected_languages(args.language)
    genders = selected_genders(args.gender)
    slides = selected_slides(args)
    texts = require_translations(translations_dir(work_dir), slides, languages)
    clips = []
    for text in texts:
        for gender in genders:
            expected = build_record(text, gender)
            clip = read_sidecar(work_dir, text.slide_key, text.language, gender)
            if (
                clip is not None
                and clip.record.hash == expected.hash
                and clip.record.duration > 0
            ):
                clips.append(clip)
    store = open_object_store()
    records = upload_audio(clips, work_dir=work_dir, store=store) if clips else []
    expected_ids = {
        (text.slide_key, text.language, gender)
        for text in texts
        for gender in genders
    }
    manifest = work_dir / "manifest.json"
    try:
        publish_manifest(manifest, records, expected=expected_ids)
    except IncompleteManifest as exc:
        print(f"published=no {exc}")
        return 1
    manifest_url = upload_manifest(manifest, store=store)
    print(
        f"published=yes records={len(records)} path={manifest} "
        f"url={manifest_url}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None or code == 0:
            return 0
        return code if isinstance(code, int) else 2
    try:
        if args.stage == "translate":
            return cmd_translate(args)
        if args.stage == "render":
            return cmd_render(args)
        if args.stage == "upload":
            return cmd_upload(args)
    except (TranslationError, AudioPipelineError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"error: unknown stage {args.stage}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
