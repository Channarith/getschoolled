"""Course catalog and dynamic training programs.

A persistent catalog of Programs -> Courses -> Modules (which reference the CMS
decks/scenes by id). Dynamic training programs carry adaptive rules (e.g.
prerequisite mastery) so the next course can be chosen from a learner's state.
Storage mirrors the FaceGallery pattern: in-memory with optional JSON
persistence; db/migrations/0003_catalog.sql is the schema-of-record for the
eventual Postgres backend.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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


class Program(BaseModel):
    program_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    audience: str = ""              # role / cohort the program targets
    description: str = ""
    course_ids: List[str] = Field(default_factory=list)
    # Adaptive rules, e.g. {"prereq_mastery": {course_id: 0.7}} - a course is
    # unlocked only once its prerequisites are mastered above the threshold.
    adaptive_rules: Dict[str, Dict[str, float]] = Field(default_factory=dict)


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
