"""Curriculum loader for the live-class teaching loop.

Parses the plain-text lessons under ``sample-curriculum/`` into structured
lessons (slides) plus a flat list of knowledge passages used by the Tutor's RAG
retrieval. Full CMS ingestion lives in services/curriculum; this keeps the
phase-1 teaching loop self-contained.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

_SLIDE_RE = re.compile(r"^SLIDE\s+(\d+)\s*\|\s*(.+)$")

_KIND_LABEL = {"K": "Knowledge", "S": "Skill", "B": "Behaviour"}


class Slide(BaseModel):
    index: int
    title: str
    body: str
    narration: str


class KSBItem(BaseModel):
    """A single Knowledge (K), Skill (S) or Behaviour (B) statement."""

    code: str
    kind: str  # "K", "S" or "B"
    statement: str


class Duty(BaseModel):
    """An occupation duty and the KSB codes it maps to."""

    code: str
    statement: str
    ksbs: List[str] = Field(default_factory=list)


class CourseKSB(BaseModel):
    """A course's occupational standard, mirroring the UK apprenticeship format."""

    course_id: str
    title: str
    level: str = ""
    role: str = ""
    source: str = ""
    knowledge: List[KSBItem] = Field(default_factory=list)
    skills: List[KSBItem] = Field(default_factory=list)
    behaviours: List[KSBItem] = Field(default_factory=list)
    duties: List[Duty] = Field(default_factory=list)


class Lesson(BaseModel):
    lesson_id: str
    title: str
    language: str = "en"
    # Which catalog this lesson belongs to. "general" lessons show in the Live
    # Class picker; "corporate" lessons are surfaced under Corporate training.
    audience: str = "general"
    # Optional catalog metadata used to render programme cards (e.g. the
    # Corporate training catalog). All blank by default so existing lessons and
    # the live teaching loop are unaffected.
    track: str = ""        # family for grouping, e.g. "AI", "Data", "Engineering"
    level: str = ""        # e.g. "Level 3 Apprenticeship"
    role: str = ""         # target role/badge, e.g. "Data Technician"
    delivery: str = ""     # e.g. "13 month delivery"
    fit: str = ""          # "Who's it for" one-liner
    summary: str = ""      # short marketing blurb for the card
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
    audience = "general"
    meta = {"track": "", "level": "", "role": "", "delivery": "", "fit": "", "summary": ""}
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
        if line.startswith("AUDIENCE:"):
            audience = line.split(":", 1)[1].strip().lower() or "general"
            continue
        matched_meta = False
        for key in meta:
            tag = f"{key.upper()}:"
            if line.startswith(tag):
                meta[key] = line.split(":", 1)[1].strip()
                matched_meta = True
                break
        if matched_meta:
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
        Lesson(
            lesson_id=lesson_id,
            title=title,
            language=language,
            audience=audience,
            slides=slides,
            **meta,
        ),
        passages,
    )


def _parse_ksb(course_id: str, raw: str) -> Tuple[CourseKSB, List[str]]:
    """Parse a course's ksb.json into a CourseKSB plus retrievable passages.

    The passages let the Tutor's RAG retrieval ground answers in the course's
    duties and KSBs, so the AI teacher can reference what the programme covers.
    """
    data = json.loads(raw)

    def _items(mapping: dict, kind: str) -> List[KSBItem]:
        return [
            KSBItem(code=code, kind=kind, statement=str(stmt))
            for code, stmt in (mapping or {}).items()
        ]

    duties = [
        Duty(
            code=code,
            statement=str(body.get("statement", "")),
            ksbs=list(body.get("ksbs", [])),
        )
        for code, body in (data.get("duties") or {}).items()
    ]
    ksb = CourseKSB(
        course_id=data.get("course_id", course_id),
        title=data.get("title", course_id),
        level=data.get("level", ""),
        role=data.get("role", ""),
        source=data.get("source", ""),
        knowledge=_items(data.get("knowledge"), "K"),
        skills=_items(data.get("skills"), "S"),
        behaviours=_items(data.get("behaviours"), "B"),
        duties=duties,
    )

    passages: List[str] = []
    for duty in ksb.duties:
        if duty.statement:
            passages.append(f"{duty.code}: {duty.statement}")
    for item in (*ksb.knowledge, *ksb.skills, *ksb.behaviours):
        label = _KIND_LABEL.get(item.kind, "")
        passages.append(f"{label} {item.code}: {item.statement}")
    return ksb, passages


class CurriculumStore:
    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or curriculum_root()
        self.lessons: dict[str, Lesson] = {}
        self.passages: dict[str, List[str]] = {}
        self.ksb: Dict[str, CourseKSB] = {}
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
            from aoep_shared.lesson_depth import enrich_slides

            def _slide_factory(idx: int, title: str, body: str, narration: str) -> Slide:
                return Slide(index=idx, title=title, body=body, narration=narration)

            enriched, extra_passages = enrich_slides(
                lesson.slides, passages, slide_factory=_slide_factory,
            )
            lesson.slides = enriched
            passages = passages + extra_passages
            self.lessons[entry] = lesson
            self.passages[entry] = passages
            self._load_ksb(entry, passages)

    def _load_ksb(self, entry: str, passages: List[str]) -> None:
        ksb_file = os.path.join(self.root, entry, "ksb.json")
        if not os.path.isfile(ksb_file):
            return
        try:
            with open(ksb_file, "r", encoding="utf-8") as fh:
                ksb, ksb_passages = _parse_ksb(entry, fh.read())
        except (ValueError, KeyError):
            # A malformed ksb.json must not break lesson loading.
            return
        self.ksb[entry] = ksb
        # Surface duties/KSBs to RAG so the teacher can reference what the
        # programme covers when relevant.
        passages.extend(ksb_passages)

    def list_lessons(self) -> List[Lesson]:
        return list(self.lessons.values())

    def get(self, lesson_id: str) -> Optional[Lesson]:
        return self.lessons.get(lesson_id)

    def passages_for(self, lesson_id: str) -> List[str]:
        return self.passages.get(lesson_id, [])

    def ksb_for(self, lesson_id: str) -> Optional[CourseKSB]:
        return self.ksb.get(lesson_id)
