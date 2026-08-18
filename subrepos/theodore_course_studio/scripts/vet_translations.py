#!/usr/bin/env python3
"""Vet curated cert-slide translations against English kits.

Loads English courses via build_cert_course, then for each language in
cert_i18n.CURATED (default --lang km) checks:

  - every English slide_key has a curated translation
  - Khmer Unicode appears in non-empty display/spoken fields (language=km)
  - translated titles differ from English titles
  - quiz_choices / game_options / game_steps lengths match the English kit

Exit 0 if all checks pass, 1 otherwise. Optionally seeds review status under
~/.cache/theodore-course-studio/translation_review.json (or COURSE_STUDIO_DATA)
without overwriting existing entries.

Usage:
  python3 scripts/vet_translations.py [--lang km]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from theodore_course_studio.cert_i18n import (  # noqa: E402
    CURATED,
    NEEDS_NATIVE_REVIEW,
    CertSlideTranslation,
    translate_cert_slide,
)
from theodore_course_studio.certification_prep import (  # noqa: E402
    build_cert_course,
    list_cert_courses,
)

KHMER_RE = re.compile(r"[\u1780-\u17ff]")
# Pure measurements / BAC limits stay English numerals by design (0.08%, 165°F).
_MEASUREMENT_RE = re.compile(
    r"^[\d\s.,:+\-/%]*"
    r"(?:%|°\s*[FfCc]|[FfCc]\b|mph|bac)?"
    r"[\d\s.,:+\-/%°]*$",
    re.IGNORECASE,
)


def _review_path() -> Path:
    override = os.environ.get("COURSE_STUDIO_DATA", "").strip()
    if override:
        return Path(override).expanduser() / "translation_review.json"
    return Path.home() / ".cache" / "theodore-course-studio" / "translation_review.json"


def _has_khmer(text: str) -> bool:
    return bool(KHMER_RE.search(text or ""))


def _measurement_only(text: str) -> bool:
    cleaned = (text or "").strip()
    return bool(cleaned) and bool(_MEASUREMENT_RE.match(cleaned))


def _english_slide_index() -> dict[str, dict[str, Any]]:
    """slide_key -> English title + kit list lengths from built courses."""
    index: dict[str, dict[str, Any]] = {}
    for option in list_cert_courses():
        course = build_cert_course(lesson_id=option.lesson_id, language="en")
        for slide in course.slides:
            key = slide.slide_key
            if not key:
                continue
            quiz = slide.quiz_spec or {}
            game = slide.game_spec or {}
            index[key] = {
                "title": slide.title,
                "quiz_choices": len(quiz.get("choices") or []),
                "game_options": len(game.get("options") or []),
                "game_steps": len(game.get("steps") or []),
                "lesson_id": option.lesson_id,
            }
    return index


def _khmer_fields(tr: CertSlideTranslation) -> list[tuple[str, str]]:
    """Named non-empty strings that must contain Khmer when language is km."""
    rows: list[tuple[str, str]] = [
        ("title", tr.title),
        ("body", tr.body),
        ("say", tr.say),
        ("activity", tr.activity),
        ("quiz_prompt", tr.quiz_prompt),
        ("quiz_explanation", tr.quiz_explanation),
        ("game_prompt", tr.game_prompt),
    ]
    for i, ex in enumerate(tr.examples):
        rows.append((f"examples[{i}]", ex))
    for i, choice in enumerate(tr.quiz_choices):
        rows.append((f"quiz_choices[{i}]", choice))
    for i, opt in enumerate(tr.game_options):
        rows.append((f"game_options[{i}]", opt))
    for i, step in enumerate(tr.game_steps):
        rows.append((f"game_steps[{i}]", step))
    return [(name, value) for name, value in rows if (value or "").strip()]


def _check_slide(
    *,
    slide_key: str,
    language: str,
    english: dict[str, Any],
    tr: CertSlideTranslation | None,
) -> list[str]:
    fails: list[str] = []
    if tr is None:
        fails.append("missing translation")
        return fails

    if tr.title.strip() == (english.get("title") or "").strip():
        fails.append("title equals English title")

    if language == "km":
        for name, value in _khmer_fields(tr):
            if _measurement_only(value):
                continue
            if not _has_khmer(value):
                fails.append(f"{name} lacks Khmer Unicode")

    if len(tr.quiz_choices) != english["quiz_choices"]:
        fails.append(
            f"quiz_choices length {len(tr.quiz_choices)} != English {english['quiz_choices']}"
        )
    if len(tr.game_options) != english["game_options"]:
        fails.append(
            f"game_options length {len(tr.game_options)} != English {english['game_options']}"
        )
    if len(tr.game_steps) != english["game_steps"]:
        fails.append(
            f"game_steps length {len(tr.game_steps)} != English {english['game_steps']}"
        )
    return fails


def _load_review(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, row in raw.items():
        if isinstance(row, dict) and "status" in row:
            out[str(key)] = {
                "status": str(row.get("status") or "needs_review"),
                "notes": str(row.get("notes") or ""),
            }
    return out


def _persist_review(
    path: Path,
    *,
    language: str,
    results: dict[str, list[str]],
) -> None:
    existing = _load_review(path)
    changed = False
    for slide_key, fails in results.items():
        if slide_key in existing:
            continue
        if fails:
            status = "fail"
        elif language in NEEDS_NATIVE_REVIEW or language.startswith("km"):
            status = "needs_review"
        else:
            status = "ok"
        existing[slide_key] = {"status": status, "notes": ""}
        changed = True
    if not changed and path.is_file():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        # Vetting still succeeds if review persistence is blocked (sandbox /
        # read-only home). Operators can set COURSE_STUDIO_DATA to a writable dir.
        print(f"WARN: could not persist review status to {path}: {exc}", file=sys.stderr)


def vet_language(language: str) -> int:
    lang = (language or "km").strip().lower().replace("_", "-")
    if lang.startswith("km"):
        lang = "km"
    if lang not in CURATED:
        print(f"FAIL: language {lang!r} not in cert_i18n.CURATED "
              f"(known: {', '.join(sorted(CURATED)) or 'none'})")
        return 1

    english = _english_slide_index()
    results: dict[str, list[str]] = {}
    passed = 0
    failed = 0

    print(f"Vetting language={lang} against {len(english)} English cert slides")
    print("-" * 72)

    for slide_key in sorted(english):
        tr = translate_cert_slide(slide_key, lang)
        fails = _check_slide(
            slide_key=slide_key,
            language=lang,
            english=english[slide_key],
            tr=tr,
        )
        results[slide_key] = fails
        if fails:
            failed += 1
            print(f"FAIL  {slide_key}")
            for msg in fails:
                print(f"        - {msg}")
        else:
            passed += 1
            print(f"PASS  {slide_key}")

    # Orphan curated keys (present in CURATED but not in any English course)
    orphans = sorted(set(CURATED[lang]) - set(english))
    if orphans:
        print("-" * 72)
        print(f"NOTE  {len(orphans)} curated key(s) not in English courses:")
        for key in orphans:
            print(f"        - {key}")

    review_path = _review_path()
    _persist_review(review_path, language=lang, results=results)

    print("-" * 72)
    print(f"Summary: {passed} pass, {failed} fail (of {len(english)})")
    print(f"Review status: {review_path}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Vet cert_i18n curated translations")
    parser.add_argument(
        "--lang",
        default="km",
        help="Language code in cert_i18n.CURATED (default: km)",
    )
    args = parser.parse_args()
    return vet_language(args.lang)


if __name__ == "__main__":
    raise SystemExit(main())
