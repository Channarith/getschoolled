#!/usr/bin/env python3
"""Curriculum depth review + gate.

Reports per-lesson slide count, word count, and facts for every lesson in
sample-curriculum/, and flags lessons that are below "textbook" depth (stubs).
Use to track which lessons still need to be expanded to comprehensive,
textbook-chapter depth (not toy examples).

Usage:
  python3 scripts/check_curriculum_depth.py                 # report
  python3 scripts/check_curriculum_depth.py --min-words 1500 --min-slides 15 --fail
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "sample-curriculum"


def analyze(text: str) -> dict:
    slides = len(re.findall(r"^SLIDE\s+\d+\s*\|", text, re.M))
    facts = len(re.findall(r"^FACT:", text, re.M))
    # Word count of body content (exclude the structural markers).
    body = re.sub(r"^(LESSON|LANGUAGE|NARRATION|FACT):.*$", "", text, flags=re.M)
    body = re.sub(r"^SLIDE\s+\d+\s*\|.*$", "", body, flags=re.M)
    words = len(body.split())
    return {"slides": slides, "facts": facts, "words": words}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-words", type=int, default=1500)
    ap.add_argument("--min-slides", type=int, default=15)
    ap.add_argument("--fail", action="store_true", help="exit 1 if any lesson is below depth")
    args = ap.parse_args()

    rows = []
    for lesson in sorted(CURRICULUM.glob("*/lesson.txt")):
        stats = analyze(lesson.read_text(encoding="utf-8", errors="ignore"))
        stats["name"] = lesson.parent.name
        rows.append(stats)

    if not rows:
        print("No lessons found.")
        return 0

    total_words = sum(r["words"] for r in rows)
    print(f"{'lesson':40s} {'slides':>6} {'words':>7} {'facts':>6}  depth")
    below = []
    for r in sorted(rows, key=lambda x: x["words"], reverse=True):
        ok = r["words"] >= args.min_words and r["slides"] >= args.min_slides
        mark = "OK" if ok else "stub"
        if not ok:
            below.append(r["name"])
        print(f"{r['name']:40s} {r['slides']:>6} {r['words']:>7} {r['facts']:>6}  {mark}")
    pages = total_words / 450  # ~450 words per textbook page
    print(f"\nTotal: {len(rows)} lessons, {total_words} words "
          f"(~{pages:.0f} textbook pages at 450 words/page).")
    print(f"Textbook-depth (>= {args.min_words} words & >= {args.min_slides} slides): "
          f"{len(rows) - len(below)}/{len(rows)}.")
    if below:
        print("Below depth (expand toward textbook depth):")
        for n in below:
            print(f"  - {n}")
    if args.fail and below:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
