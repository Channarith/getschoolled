#!/usr/bin/env python3
"""Validation: prove the harvest -> teach -> present flow works end to end.

Runs the full offline pipeline (deterministic lesson + mock meeting) on a small
built-in sample and asserts every stage produced what the next stage needs:

  Part 1  a scored, tagged course + exported .pptx / .course.json
  Part 2  a narrated lesson (intro + one segment per slide + outro)
  Part 3  a meeting + a presentation that covered every lesson step

Exit code 0 = the whole chain is wired correctly. Use this as a smoke check in
CI or after changing any part. No network, keys, or ffmpeg required.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.harvest import CourseTags  # noqa: E402
from aoep_shared.teaching import run_end_to_end  # noqa: E402

SAMPLE = (
    "Introduction\nWelcome to Chemistry 101; here are today's objectives.\n\n"
    "History\nAlchemy slowly became modern chemistry over centuries.\n\n"
    "Example 1\nBalancing a simple chemical equation step by step.\n\n"
    "Exercise\nPractice: balance the equation on your own.\n\n"
    "Q&A\nCommon questions and answers about atoms and molecules.\n\n"
    "Summary\nIn summary, matter is built from atoms.\n"
)

CHECKS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    CHECKS.append((label, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aoep_validate_") as tmp:
        out = Path(tmp) / "run"
        result = run_end_to_end(
            text=SAMPLE, subject="chemistry",
            tags=CourseTags(access_tier="free", core_fundamental=True,
                            career_path="chemist"),
            out_dir=out, teach_engine="fallback",
            meeting_provider="zoom",   # no creds -> must fall back to mock
            present=True,
        )
        d = result.to_dict()

        # Part 1 - harvest
        check("Part1: course has slides", len(result.course.slides) >= 5)
        check("Part1: composition score in 0..999",
              0 <= d["course"]["composition_score"] < 1000)
        check("Part1: course.json written",
              Path(result.artifacts.get("course_json", "x")).exists())
        check("Part1: pptx exported (Part 2 input)",
              "pptx" in result.artifacts and Path(result.artifacts["pptx"]).exists())
        check("Part1: tags carried", "core-fundamental" in d["course"]["tags"])

        # Part 2 - teach
        check("Part2: lesson has intro", result.lesson.steps[0].kind == "intro")
        check("Part2: lesson has outro", result.lesson.steps[-1].kind == "outro")
        check("Part2: one segment per slide",
              len(result.lesson.segments) == len(result.course.slides))
        check("Part2: lesson script written",
              Path(result.artifacts.get("lesson_script", "x")).exists())

        # Part 3 - present
        check("Part3: fell back to mock without creds",
              d["meeting"]["provider_used"] == "zoom->mock")
        check("Part3: got a join URL", bool(d["meeting"]["join_url"]))
        check("Part3: presented every lesson step",
              d["presentation"]["steps_presented"] == len(result.lesson.steps))
        check("Part3: manifest written",
              Path(result.artifacts.get("manifest", "x")).exists())

    passed = sum(1 for _, ok in CHECKS if ok)
    total = len(CHECKS)
    print(f"\n{passed}/{total} checks passed.")
    if passed != total:
        print("VALIDATION FAILED", file=sys.stderr)
        return 1
    print("VALIDATION OK - harvest -> teach -> present is wired correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
