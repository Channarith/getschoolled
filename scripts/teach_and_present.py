#!/usr/bin/env python3
"""End-to-end CLI: harvest a course, teach it, and present it in a meeting.

Ties the three parts together:
  Part 1 (harvester)  -> scored, tagged course (+ exported .pptx / .course.json)
  Part 2 (teaching)   -> narrated lesson (offline, or via the ppt_trainer agent)
  Part 3 (meeting)    -> presents the lesson in Google Meet / Zoom / Teams (or a
                         local mock when no credentials are configured)

Examples:
  python3 scripts/teach_and_present.py --source notes.pptx --subject chemistry
  python3 scripts/teach_and_present.py --text-file sample-curriculum/intro-physics/lesson.txt \\
      --subject physics --present-mode lewin --meeting-provider local
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
    src.add_argument("--text-file", "--generate", dest="text_file",
                     help="plain-text input file (--generate is an alias)")
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
    ap.add_argument("--elapsed-min", type=float, default=0.0,
                    help="minutes already used (smart time-aware pacing)")
    ap.add_argument("--no-smart-present", action="store_true",
                    help="verbatim narration (disable smart presenter)")
    ap.add_argument("--present-mode", default=None,
                    help="presentation matrix mode (lecture/workshop/drill/lewin/… or pipe string)")
    ap.add_argument("--persona", default=None,
                    help="presenter personality (aria, davis, guy, sonia, …)")
    ap.add_argument("--slide-source", default=None,
                    help="use this .pdf/.pptx for on-screen slides (native pages, not HTML bullets)")
    ap.add_argument("--native-slides", action="store_true",
                    help="with --source: use the source .pdf/.pptx as the slide deck")
    ap.add_argument("--with-media", action="store_true",
                    help="export per-slide demo videos + themed backgrounds")
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
        text_path = Path(args.text_file)
        if not text_path.is_file():
            samples = [
                _REPO / "sample-curriculum/intro-physics/lesson.txt",
                _REPO / "output/harvest/algebra.txt",
            ]
            hints = [str(p) for p in samples if p.is_file()]
            msg = f"input file not found: {text_path}"
            if hints:
                msg += "\nTry one of these bundled samples:\n  " + "\n  ".join(hints)
            ap.error(msg)
        text = text_path.read_text(encoding="utf-8", errors="replace")
    elif not source and not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped.strip():
            text = piped

    if not source and not text:
        ap.error("provide --source, --text-file, or piped stdin text")

    slide_source = args.slide_source
    if args.native_slides and source:
        slide_source = slide_source or source

    tags = CourseTags(access_tier=args.access_tier, price_usd=args.price,
                      career_path=args.career_path, linkedin_job_id=args.linkedin_job,
                      core_fundamental=args.core)

    result = run_end_to_end(
        source=source, text=text, subject=args.subject, fmt=args.fmt, tags=tags,
        out_dir=args.out_dir, teach_engine=args.teach_engine, audience=args.audience,
        meeting_provider=args.meeting_provider, present=not args.no_present,
        realtime=args.realtime, start_iso=args.start_iso, duration_min=args.duration_min,
        elapsed_min=args.elapsed_min, smart_present=not args.no_smart_present,
        presentation_mode=args.present_mode,
        persona=args.persona,
        slide_source=slide_source,
        with_media=args.with_media,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
