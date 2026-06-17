"""Curriculum loader for the live-class teaching loop.

Parses the plain-text lessons under ``sample-curriculum/`` into structured
lessons (slides) plus a flat list of knowledge passages used by the Tutor's RAG
retrieval. Full CMS ingestion lives in services/curriculum; this keeps the
phase-1 teaching loop self-contained.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

_SLIDE_RE = re.compile(r"^SLIDE\s+(\d+)\s*\|\s*(.+)$")


class Slide(BaseModel):
    index: int
    title: str
    body: str
    narration: str


class Lesson(BaseModel):
    lesson_id: str
    title: str
    language: str = "en"
    slides: List[Slide] = Field(default_factory=list)


def curriculum_root() -> str:
    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    # src/orchestrator -> src -> orchestrator(service) -> services -> repo root
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    return os.path.join(repo_root, "sample-curriculum")


def _parse_lesson(lesson_id: str, text: str) -> Tuple[Lesson, List[str]]:
    title = lesson_id
    language = "en"
    slides: List[Slide] = []
    passages: List[str] = []

    cur_idx: Optional[int] = None
    cur_title = ""
    cur_body: List[str] = []
    cur_narration = ""

    def flush() -> None:
        nonlocal cur_idx, cur_title, cur_body, cur_narration
        if cur_idx is not None:
            body = " ".join(" ".join(cur_body).split())
            slides.append(
                Slide(
                    index=len(slides),
                    title=cur_title,
                    body=body,
                    narration=cur_narration or body,
                )
            )
            if body:
                passages.append(f"{cur_title}: {body}")
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
        if line.startswith("FACT:"):
            passages.append(line.split(":", 1)[1].strip())
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

    return (
        Lesson(lesson_id=lesson_id, title=title, language=language, slides=slides),
        passages,
    )


class CurriculumStore:
    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or curriculum_root()
        self.lessons: dict[str, Lesson] = {}
        self.passages: dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.isdir(self.root):
            return
        for entry in sorted(os.listdir(self.root)):
            lesson_file = os.path.join(self.root, entry, "lesson.txt")
            if not os.path.isfile(lesson_file):
                continue
            with open(lesson_file, "r", encoding="utf-8") as fh:
                lesson, passages = _parse_lesson(entry, fh.read())
            self.lessons[entry] = lesson
            self.passages[entry] = passages

    def list_lessons(self) -> List[Lesson]:
        return list(self.lessons.values())

    def get(self, lesson_id: str) -> Optional[Lesson]:
        return self.lessons.get(lesson_id)

    def passages_for(self, lesson_id: str) -> List[str]:
        return self.passages.get(lesson_id, [])
