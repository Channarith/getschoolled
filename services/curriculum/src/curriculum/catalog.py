"""Course catalog and dynamic training programs.

A persistent catalog of Programs -> Courses -> Modules (which reference the CMS
decks/scenes by id). Dynamic training programs carry adaptive rules (e.g.
prerequisite mastery) so the next course can be chosen from a learner's state.
Storage mirrors the FaceGallery pattern: in-memory with optional JSON
persistence; db/migrations/0003_catalog.sql is the schema-of-record for the
eventual Postgres backend.
"""

from __future__ import annotations

import enum
import json
import os
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class DeliveryMode(str, enum.Enum):
    """Who conducts the class: fully AI, fully human, or AI + human (hybrid)."""
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


class Module(BaseModel):
    module_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    deck_id: Optional[str] = None
    scene_id: Optional[str] = None
    order: int = 0


class Course(BaseModel):
    course_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    subject: str = "general"        # maps to the LLM routing category
    language: str = "en"
    description: str = ""
    modules: List[Module] = Field(default_factory=list)
    validation_status: str = "unvalidated"  # unvalidated | validated | flagged
    version: int = 1
    # Accountability (Trust layer): a named human signs off on the content.
    human_of_record: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None
    # Opt-in delivery track (Trust layer): AI / human / hybrid.
    delivery_mode: DeliveryMode = DeliveryMode.AI
    # Browse / search metadata (Netflix-style catalog).
    category: str = ""                  # defaults to subject; the browse facet
    tags: List[str] = Field(default_factory=list)
    audio_language: str = ""            # spoken-audio language; defaults to language
    media_format: str = "video"         # video | audio | text | interactive
    level: str = "beginner"             # beginner | intermediate | advanced
    duration_min: int = 0
    hands_on: bool = False              # requires hands-on/lab training
    preview: str = ""                   # short preview/trailer blurb
    access_tier: str = "free"           # membership tier required to enroll
    price_usd: float = 0.0
    thumbnail: Optional[str] = None     # object-store key / URL for a card image

    @model_validator(mode="after")
    def _defaults(self) -> "Course":
        if not self.category:
            self.category = self.subject
        if not self.audio_language:
            self.audio_language = self.language
        return self


class Program(BaseModel):
    program_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    audience: str = ""              # role / cohort the program targets
    description: str = ""
    course_ids: List[str] = Field(default_factory=list)
    # Adaptive rules, e.g. {"prereq_mastery": {course_id: 0.7}} - a course is
    # unlocked only once its prerequisites are mastered above the threshold.
    adaptive_rules: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    delivery_mode: DeliveryMode = DeliveryMode.AI


class CatalogStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.courses: Dict[str, Course] = {}
        self.programs: Dict[str, Program] = {}
        if path and os.path.isfile(path):
            self.load_json(path)

    # --- courses ----------------------------------------------------------- #
    def create_course(self, course: Course) -> Course:
        self.courses[course.course_id] = course
        self._autosave()
        return course

    def get_course(self, course_id: str) -> Optional[Course]:
        return self.courses.get(course_id)

    def list_courses(self) -> List[Course]:
        return list(self.courses.values())

    def search_courses(
        self,
        *,
        q: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        audio: Optional[str] = None,
        media_format: Optional[str] = None,
        level: Optional[str] = None,
        tag: Optional[str] = None,
        hands_on: Optional[bool] = None,
        delivery_mode: Optional[str] = None,
        access_tier: Optional[str] = None,
    ) -> List[Course]:
        """Faceted catalog search by name/category/language/audio/format/tag/etc."""
        def _eq(value: str, want: Optional[str]) -> bool:
            return want is None or value.lower() == want.lower()

        out: List[Course] = []
        for c in self.courses.values():
            if q:
                hay = " ".join([c.title, c.description, c.preview, " ".join(c.tags)]).lower()
                if q.lower() not in hay:
                    continue
            if not _eq(c.category or c.subject, category):
                continue
            if not _eq(c.language, language):
                continue
            if not _eq(c.audio_language or c.language, audio):
                continue
            if not _eq(c.media_format, media_format):
                continue
            if not _eq(c.level, level):
                continue
            if not _eq(c.delivery_mode.value, delivery_mode):
                continue
            if not _eq(c.access_tier, access_tier):
                continue
            if tag is not None and tag.lower() not in [t.lower() for t in c.tags]:
                continue
            if hands_on is not None and c.hands_on != hands_on:
                continue
            out.append(c)
        return out

    def delete_course(self, course_id: str) -> bool:
        existed = self.courses.pop(course_id, None) is not None
        if existed:
            self._autosave()
        return existed

    # --- programs ---------------------------------------------------------- #
    def create_program(self, program: Program) -> Program:
        self.programs[program.program_id] = program
        self._autosave()
        return program

    def get_program(self, program_id: str) -> Optional[Program]:
        return self.programs.get(program_id)

    def list_programs(self) -> List[Program]:
        return list(self.programs.values())

    def delete_program(self, program_id: str) -> bool:
        existed = self.programs.pop(program_id, None) is not None
        if existed:
            self._autosave()
        return existed

    # --- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "courses": {k: v.model_dump() for k, v in self.courses.items()},
            "programs": {k: v.model_dump() for k, v in self.programs.items()},
        }

    def save_json(self, path: Optional[str] = None) -> None:
        target = path or self.path
        if not target:
            raise ValueError("no catalog path configured")
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh)
        os.replace(tmp, target)

    def load_json(self, path: Optional[str] = None) -> None:
        target = path or self.path
        with open(target, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.courses = {k: Course(**v) for k, v in data.get("courses", {}).items()}
        self.programs = {k: Program(**v) for k, v in data.get("programs", {}).items()}

    def _autosave(self) -> None:
        if self.path:
            self.save_json(self.path)
