"""Curriculum loader.

Parses the plain-text lessons under ``sample-curriculum/`` into structured
``Lesson`` objects plus a flat list of knowledge passages used by the RAG
retriever. Real curriculum/CMS ingestion lands in services/curriculum later;
this keeps phase1 self-contained.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from eduplatform_shared.schemas import Lesson, Slide

_SLIDE_RE = re.compile(r"^SLIDE\s+(\d+)\s*\|\s*(.+)$")


def _curriculum_root() -> str:
    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return env
    # repo_root/sample-curriculum  (this file is services/orchestrator/app/curriculum.py)
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(repo_root, "sample-curriculum")


def _parse_lesson(lesson_id: str, text: str) -> Tuple[Lesson, List[str]]:
    title = lesson_id
    language = "en"
    slides: List[Slide] = []
    passages: List[str] = []

    cur_idx = None
    cur_title = ""
    cur_body: List[str] = []
    cur_narration = ""

    def flush():
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

    return Lesson(lesson_id=lesson_id, title=title, language=language, slides=slides), passages


class CurriculumStore:
    """Loads all lessons once and exposes lookups + passages for RAG."""

    def __init__(self, root: str | None = None) -> None:
        self.root = root or _curriculum_root()
        self.lessons: Dict[str, Lesson] = {}
        self.passages: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.isdir(self.root):
            return
        for entry in sorted(os.listdir(self.root)):
            lesson_dir = os.path.join(self.root, entry)
            lesson_file = os.path.join(lesson_dir, "lesson.txt")
            if not os.path.isfile(lesson_file):
                continue
            with open(lesson_file, "r", encoding="utf-8") as fh:
                lesson, passages = _parse_lesson(entry, fh.read())
            self.lessons[entry] = lesson
            self.passages[entry] = passages

    def list_lessons(self) -> List[Lesson]:
        return list(self.lessons.values())

    def get(self, lesson_id: str) -> Lesson | None:
        return self.lessons.get(lesson_id)

    def passages_for(self, lesson_id: str) -> List[str]:
        return self.passages.get(lesson_id, [])
