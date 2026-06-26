#!/usr/bin/env python3
"""End-to-end CLI: harvest a course, teach it, and present it in a meeting.

Ties the three parts together:
  Part 1 (harvester)  -> scored, tagged course (+ exported .pptx / .course.json)
  Part 2 (teaching)   -> narrated lesson (offline, or via the ppt_trainer agent)
  Part 3 (meeting)    -> presents the lesson in Google Meet / Zoom / Teams (or a
                         local mock when no credentials are configured)

Examples:
  python3 scripts/teach_and_present.py --source notes.pptx --subject chemistry
  python3 scripts/teach_and_present.py --text-file lesson.txt --subject algebra \\
      --meeting-provider zoom --teach-engine ppt_trainer
  echo "Intro\\nWelcome..." | python3 scripts/teach_and_present.py --subject demo

Offline by default (deterministic lesson + mock meeting); add --realtime to play
the presentation timeline in real wall-clock time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make aoep_shared importable when run from a clean checkout.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.harvest import CourseTags  # noqa: E402
from aoep_shared.teaching import run_end_to_end  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--source", help="input file (text/html/pdf/pptx/docx)")
    src.add_argument("--text-file", help="plain-text input file")
    ap.add_argument("--subject", default="general")
    ap.add_argument("--fmt", default="lecture")
    ap.add_argument("--out-dir", default="output/teaching")
    ap.add_argument("--teach-engine", default="fallback",
                    choices=["fallback", "ppt_trainer"])
    ap.add_argument("--audience", default="curious beginners")
    ap.add_argument("--meeting-provider", default="mock",
                    help="mock|google_meet|zoom|teams")
    ap.add_argument("--no-present", action="store_true", help="plan only; don't present")
    ap.add_argument("--realtime", action="store_true", help="present in real time")
    ap.add_argument("--start-iso", default="", help="ISO start time to schedule")
    ap.add_argument("--duration-min", type=int, default=None)
    # tags
    ap.add_argument("--access-tier", default="free")
    ap.add_argument("--price", type=float, default=0.0)
    ap.add_argument("--career-path", default=None)
    ap.add_argument("--linkedin-job", default=None)
    ap.add_argument("--core", action="store_true")
    args = ap.parse_args(argv)

    text = None
    source = args.source
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8", errors="replace")
    elif not source and not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped.strip():
            text = piped

    if not source and not text:
        ap.error("provide --source, --text-file, or piped stdin text")

    tags = CourseTags(access_tier=args.access_tier, price_usd=args.price,
                      career_path=args.career_path, linkedin_job_id=args.linkedin_job,
                      core_fundamental=args.core)

    result = run_end_to_end(
        source=source, text=text, subject=args.subject, fmt=args.fmt, tags=tags,
        out_dir=args.out_dir, teach_engine=args.teach_engine, audience=args.audience,
        meeting_provider=args.meeting_provider, present=not args.no_present,
        realtime=args.realtime, start_iso=args.start_iso, duration_min=args.duration_min,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
