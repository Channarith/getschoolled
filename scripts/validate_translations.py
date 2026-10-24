#!/usr/bin/env python3
"""Validate a translation library before it ships (read-only on the library).

  python3 scripts/validate_translations.py ~/getschoolled/data/_incoming_kalel
  python3 scripts/validate_translations.py DIR --languages km,vi,th --out output/validation/kalel
  python3 scripts/validate_translations.py DIR --no-catalog      # skip the English-source checks

Writes report.json, summary.txt and shippable.json (the conservative manifest of
files that passed every check) into --out. Exit code is 0 unless --strict is set
and anything was held or rejected.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "shared" / "src"))
from aoep_shared.translation_validate import render_text, validate_library  # noqa: E402


def catalog_sources() -> dict:
    from aoep_shared.audio_courses import build_catalog

    out = {}
    for course in build_catalog("en", "en"):
        if course.id.startswith("lang-"):
            continue
        out[course.id] = [{"heading": s.heading, "text": s.text} for s in course.segments]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="library directory: <root>/<course_id>/<lang>.json")
    ap.add_argument("--out", type=Path, default=Path("output/validation/translations"))
    ap.add_argument("--languages", default="", help="comma list, default all")
    ap.add_argument("--no-catalog", action="store_true", help="do not load English text from the audio catalog")
    ap.add_argument("--langid", action="store_true", help="also use langdetect if installed")
    ap.add_argument("--limit", type=int, default=0, help="only the first N files (quick look)")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    root = args.root.expanduser()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    sources = None if args.no_catalog else catalog_sources()
    report = validate_library(
        root,
        sources=sources,
        languages=[x for x in args.languages.split(",") if x] or None,
        langid=args.langid,
        limit=args.limit or None,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "shippable.json").write_text(json.dumps(report["shippable"], ensure_ascii=False, indent=1), encoding="utf-8")
    text = render_text(report)
    (args.out / "summary.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nwrote {args.out}/report.json, summary.txt, shippable.json ({len(report['shippable'])} files)")
    v = report["verdicts"]
    return 1 if args.strict and (v.get("hold") or v.get("reject")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
