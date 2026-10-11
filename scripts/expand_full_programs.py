#!/usr/bin/env python3
"""Asynchronously expand short courses into full programs.

A lesson stays about a dozen slides. A full course is the program: at least
200 slides, written as lesson-sized decks under output/harvest/programs/.

The five named domains (AI, CPR, automotive, grade school, vocabulary) are
hand-outlined. Every other on-disk course family is included with --all.
Families that already publish hundreds of slides are recorded and left as
they are. Generated decks are review drafts. This script does not issue an
outside card.

Examples:
  python3 scripts/expand_full_programs.py
  python3 scripts/expand_full_programs.py --all --plan-only
  python3 scripts/expand_full_programs.py --domains cpr --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "packages" / "shared" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aoep_shared.full_programs import (  # noqa: E402
    MIN_FULL_PROGRAM_SLIDES,
    discover_programs,
    expand_programs,
    select_programs,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domains",
        default="ai,cpr,automotive,grade-school,vocabulary",
        help="Comma-separated domain or program ids. Ignored with --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Every discovered program, including course families already at the floor.",
    )
    parser.add_argument(
        "--short-only",
        action="store_true",
        help="Skip programs whose published lessons already meet the slide floor.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "output" / "harvest" / "programs",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write program.json manifests without lesson decks or pptx.",
    )
    parser.add_argument(
        "--no-pptx",
        action="store_true",
        help="Write course JSON only. The default harvest export includes pptx.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    catalog = discover_programs(ROOT / "sample-curriculum")
    if args.all:
        chosen = select_programs(catalog, only_short=args.short_only)
    else:
        domains = [part.strip() for part in args.domains.split(",")]
        chosen = select_programs(catalog, domains=domains, only_short=args.short_only)
    if not chosen:
        print("No programs matched.", file=sys.stderr)
        return 1
    print(
        f"Programs: {len(chosen)}  floor: {MIN_FULL_PROGRAM_SLIDES} slides  "
        f"out: {args.out}"
    )
    for spec in chosen:
        state = "expand" if spec.needs_expansion else "already-full"
        print(f"  {state:12} {spec.program_id}  target={spec.target_slides}")
    manifests = asyncio.run(
        expand_programs(
            chosen,
            args.out,
            write_pptx=not args.no_pptx,
            concurrency=args.concurrency,
            plan_only=args.plan_only,
        )
    )
    slides = sum(int(item.get("slide_count") or 0) for item in manifests)
    print(f"Wrote {len(manifests)} program manifests, {slides} planned slides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
