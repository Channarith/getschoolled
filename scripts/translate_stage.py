#!/usr/bin/env python3
"""Translate the next few courses, a stage at a time.

Picks the next N audio courses that still lack a valid translation in the
chosen languages (the demo course first), translates only those, and writes into
data/course_translations. Rerun for the next stage; finished work is skipped.

  python3 scripts/translate_stage.py --dry-run
  python3 scripts/translate_stage.py --courses 6 --language es --language fr --language km
  python3 scripts/translate_stage.py --courses 20          # next 20, default languages

Needs XAI_API_KEY, or SPEECH_BASE_URL / TRANSLATION_BASE_URL for NLLB.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

DEMO = "audio-intro-to-machine-learning"
DEFAULT_LANGUAGES = ("es", "fr", "km")


def needs_work(course_id: str, segments: int, languages: list[str], root: Path) -> list[str]:
    from aoep_shared.course_translation_library import load_translation

    missing = []
    for lang in languages:
        record = load_translation(course_id, lang, root)
        if not record or len(record.get("segments") or []) != segments:
            missing.append(lang)
    return missing


def pick(courses: int, languages: list[str], root: Path) -> list[tuple[str, list[str]]]:
    from aoep_shared.audio_courses import build_catalog

    catalog = [c for c in build_catalog("en", "en") if not c.id.startswith("lang-")]
    catalog.sort(key=lambda c: (c.id != DEMO, c.id))
    chosen = []
    for course in catalog:
        missing = needs_work(course.id, len(course.segments), languages, root)
        if missing:
            chosen.append((course.id, missing))
        if len(chosen) >= courses:
            break
    return chosen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--courses", type=int, default=6)
    ap.add_argument("--language", action="append", default=None)
    ap.add_argument("--out", default=str(ROOT / "data" / "course_translations"))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    languages = args.language or list(DEFAULT_LANGUAGES)
    root = Path(args.out)
    chosen = pick(args.courses, languages, root)
    if not chosen:
        print("nothing left to translate for these languages")
        return 0
    print(f"stage: {len(chosen)} courses x {languages}")
    for course_id, missing in chosen:
        print(f"  {course_id}: {' '.join(missing)}")
    if args.dry_run:
        return 0

    cmd = [sys.executable, str(ROOT / "scripts" / "translate_courses_batch.py"), "--audio-only", "--verbose",
           "--concurrency", str(args.concurrency)]
    for lang in languages:
        cmd += ["--language", lang]
    for course_id, _ in chosen:
        cmd += ["--course", course_id]
    env = {**os.environ, "AOEP_COURSE_TRANSLATION_DIR": str(root)}
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
