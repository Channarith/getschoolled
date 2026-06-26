#!/usr/bin/env python3
"""Generate a corporate lesson.txt from a plain-text/JSON outline.

The orchestrator teaches lessons that live at
``sample-curriculum/<slug>/lesson.txt`` in a simple line-based format:

    LESSON: <title>
    LANGUAGE: en
    AUDIENCE: corporate
    TRACK / LEVEL / ROLE / DELIVERY / FIT / SUMMARY   (optional catalog metadata)

    SLIDE 1 | <slide title>
    <body ...>
    NARRATION: <one-line spoken summary>

    FACT: <grounding fact for the AI teacher's retrieval>

This script writes that file from an outline so you can scale content from
openly-licensed sources (e.g. the UK apprenticeship-standard KSBs published under
the Open Government Licence, vendor docs under CC BY, NIST/EU AI frameworks).
Author the *teaching prose yourself* from those sources -- do not paste
proprietary course material (Multiverse, Coursera, Udemy) verbatim.

Outline format (JSON)::

    {
      "title": "Data & Insights for Business Decisions",
      "language": "en",            # optional, default "en"
      "audience": "corporate",     # optional, default "corporate"
      "slug": "data-insights",     # optional, derived from title if omitted
      "track": "Data",             # AI | Data | Engineering (groups the card)
      "level": "Level 3 Apprenticeship",
      "role": "Data Technician",
      "delivery": "13 month delivery",
      "fit": "Anyone eager to boost data confidence.",
      "summary": "Short marketing blurb shown on the catalog card.",
      "slides": [
        {"title": "What This Course Is About",
         "body": "Full paragraph(s) of teaching prose ...",
         "narration": "Optional one-line spoken summary."}
      ],
      "facts": ["Optional explicit grounding facts ..."]
    }

If ``narration`` is omitted it defaults to the first sentence of the body.
If ``facts`` is omitted, one fact per slide is derived from the first sentence.

Usage::

    python3 scripts/make_corporate_lesson.py outline.json
    python3 scripts/make_corporate_lesson.py outline.json --out-dir sample-curriculum
    python3 scripts/make_corporate_lesson.py outline.json --print   # stdout only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from typing import Any, Dict, List

WRAP_WIDTH = 78
META_KEYS = ("track", "level", "role", "delivery", "fit", "summary")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "lesson"


def first_sentence(text: str) -> str:
    text = " ".join(text.split())
    m = re.search(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text).strip()


def wrap(text: str) -> str:
    # Collapse whitespace, then wrap to match the existing hand-authored lessons.
    collapsed = " ".join(text.split())
    return "\n".join(textwrap.wrap(collapsed, width=WRAP_WIDTH)) or collapsed


def render(outline: Dict[str, Any]) -> str:
    title = outline.get("title")
    if not title:
        raise ValueError("outline must include a 'title'")
    slides = outline.get("slides") or []
    if not slides:
        raise ValueError("outline must include at least one slide in 'slides'")

    lines: List[str] = []
    lines.append(f"LESSON: {title}")
    lines.append(f"LANGUAGE: {outline.get('language', 'en')}")
    lines.append(f"AUDIENCE: {outline.get('audience', 'corporate')}")
    for key in META_KEYS:
        val = str(outline.get(key, "")).strip()
        if val:
            lines.append(f"{key.upper()}: {val}")
    lines.append("")

    derived_facts: List[str] = []
    for i, slide in enumerate(slides, start=1):
        s_title = str(slide.get("title", f"Slide {i}")).strip()
        body = str(slide.get("body", "")).strip()
        narration = str(slide.get("narration", "")).strip() or first_sentence(body)
        lines.append(f"SLIDE {i} | {s_title}")
        if body:
            lines.append(wrap(body))
        if narration:
            lines.append(f"NARRATION: {narration}")
        lines.append("")
        if body:
            derived_facts.append(first_sentence(body))

    facts = outline.get("facts") or derived_facts
    for fact in facts:
        fact = " ".join(str(fact).split())
        if fact:
            lines.append(f"FACT: {fact}")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("outline", help="Path to the JSON outline file")
    parser.add_argument(
        "--out-dir",
        default="sample-curriculum",
        help="Curriculum root to write into (default: sample-curriculum)",
    )
    parser.add_argument("--print", action="store_true", help="Print to stdout instead of writing a file")
    args = parser.parse_args(argv)

    with open(args.outline, "r", encoding="utf-8") as fh:
        outline = json.load(fh)

    content = render(outline)

    if args.print:
        sys.stdout.write(content)
        return 0

    slug = str(outline.get("slug") or slugify(str(outline["title"]))).strip()
    dest_dir = os.path.join(args.out_dir, slug)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "lesson.txt")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"Wrote {dest} ({content.count('SLIDE ')} slides, {content.count('FACT:')} facts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
