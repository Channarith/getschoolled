#!/usr/bin/env python3
"""Attach a short lesson clip to a course or print the clip list.

YouTube and other allowed online videos are stored as a playable reference
(video id, start, end, title, source url). Nothing is downloaded. When no
reference matches, a deterministic SVG title card is written locally.

Examples:
  python3 scripts/attach_lesson_clip.py --topic "fractions" --language en --seconds 30
  python3 scripts/attach_lesson_clip.py --topic "fractions" \\
      --url "https://www.youtube.com/watch?v=abcdefghijk" \\
      --course-json output/harvest/fractions.course.json
  python3 scripts/attach_lesson_clip.py --topic "algebra" --public
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.video_clips import apply_lesson_clips, build_lesson_clips  # noqa: E402


def _publish_reused_demo(built: dict, out_dir: Path) -> None:
    """Copy an on-disk harvest demo into the public clip folder.

    The file is one this repo already ships. It is not a download.
    """
    for clip in list(built.get("clips") or []):
        play = clip.get("play") or {}
        if not play.get("reused") or not play.get("path"):
            continue
        src = Path(play["path"])
        if not src.is_file():
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / src.name
        if dest.resolve() != src.resolve():
            shutil.copyfile(src, dest)
        parts = dest.resolve().parts
        if "public" not in parts:
            continue
        idx = len(parts) - 1 - list(reversed(parts)).index("public")
        public = "/" + "/".join(parts[idx + 1 :])
        play["url"] = public
        play["path"] = str(dest)
        clip["how"] = public
        built["trailer_url"] = public
        rest = [other for other in built["clips"] if other is not clip]
        built["clips"] = [clip, *rest]
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Attach a short lesson clip.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--url", default="", help="YouTube or Vimeo URL, or an 11-character YouTube id")
    parser.add_argument(
        "--references",
        default="",
        help="JSON file of {title, url, topics, language, start_sec, end_sec} objects",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Where a generated SVG is written (default: output/lesson-clips)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Write the SVG under apps/web/public/lesson-clips and set a /lesson-clips URL",
    )
    parser.add_argument(
        "--course-json",
        default="",
        help="Course JSON to update (trailer_url, media_format, first empty slide media_url)",
    )
    args = parser.parse_args(argv)

    references = None
    if args.references:
        ref_path = Path(args.references)
        references = json.loads(ref_path.read_text(encoding="utf-8"))
        if not isinstance(references, list):
            parser.error("--references must be a JSON list")

    if args.public:
        out_dir = _REPO / "apps" / "web" / "public" / "lesson-clips"
    elif args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = _REPO / "output" / "lesson-clips"

    built = build_lesson_clips(
        topic=args.topic,
        language=args.language,
        duration_sec=args.seconds,
        source_url=args.url,
        references=references,
        out_dir=out_dir,
        repo_root=_REPO,
    )
    if args.public:
        _publish_reused_demo(built, out_dir)
    if args.course_json:
        course_path = Path(args.course_json)
        payload = json.loads(course_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            parser.error("--course-json must contain an object")
        updated = apply_lesson_clips(payload, built)
        course_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        built["course_json"] = str(course_path)
    json.dump(built, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
