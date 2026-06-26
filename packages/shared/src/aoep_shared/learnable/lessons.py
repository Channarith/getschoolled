"""Load live-class lessons from sample-curriculum (shared with orchestrator)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

_SLIDE_RE = re.compile(r"^SLIDE\s+(\d+)\s*\|\s*(.+)$")


class SampleSlide(BaseModel):
    index: int
    title: str
    body: str
    narration: str


class SampleLesson(BaseModel):
    lesson_id: str
    title: str
    language: str = "en"
    slides: List[SampleSlide] = Field(default_factory=list)


def curriculum_root(explicit: Optional[str | Path] = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # packages/shared/src/aoep_shared/learnable/lessons.py -> repo root
    return here.parents[5] / "sample-curriculum"


def _parse_lesson(lesson_id: str, text: str) -> SampleLesson:
    title = lesson_id
    language = "en"
    slides: List[SampleSlide] = []
    cur_idx: Optional[int] = None
    cur_title = ""
    cur_body: List[str] = []
    cur_narration = ""

    def flush() -> None:
        nonlocal cur_idx, cur_title, cur_body, cur_narration
        if cur_idx is not None:
            body = " ".join(" ".join(cur_body).split())
            slides.append(
                SampleSlide(
                    index=len(slides),
                    title=cur_title,
                    body=body,
                    narration=cur_narration or body,
                )
            )
        cur_idx = None
        cur_title = ""
        cur_body = []
        cur_narration = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("LESSON:"):
            title = line.split(":", 1)[1].strip()
            continue
        if line.startswith("LANGUAGE:"):
            language = line.split(":", 1)[1].strip()
            continue
        if line.startswith("NARRATION:"):
            cur_narration = line.split(":", 1)[1].strip()
            continue
        m = _SLIDE_RE.match(line)
        if m:
            flush()
            cur_idx = int(m.group(1))
            cur_title = m.group(2).strip()
            continue
        if cur_idx is not None:
            cur_body.append(line)
    flush()
    return SampleLesson(lesson_id=lesson_id, title=title, language=language, slides=slides)


def load_sample_lessons(root: Optional[str | Path] = None) -> List[SampleLesson]:
    base = curriculum_root(root)
    if not base.is_dir():
        return []
    out: List[SampleLesson] = []
    for entry in sorted(base.iterdir()):
        lesson_file = entry / "lesson.txt"
        if not lesson_file.is_file():
            continue
        out.append(_parse_lesson(entry.name, lesson_file.read_text(encoding="utf-8")))
    return out


def lesson_category(lesson_id: str, title: str) -> str:
    lid = lesson_id.lower()
    if lid.startswith("python"):
        return "Technology"
    if "fraction" in lid or "fraction" in title.lower():
        return "Mathematics"
    if "photo" in lid:
        return "Science & Nature"
    return "Live Class"


from aoep_shared.lesson_depth import TEACHING_WPM, TARGET_MIN_MINUTES, duration_minutes


def lesson_duration_min(slides: List[SampleSlide]) -> int:
    return duration_minutes(slides, wpm=TEACHING_WPM)
