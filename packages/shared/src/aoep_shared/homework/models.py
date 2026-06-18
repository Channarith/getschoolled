"""Homework subtool - shared models (Phase 6)."""

from __future__ import annotations

import enum
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from ..adaptive import Difficulty


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    SHORT = "short"
    ESSAY = "essay"


class Question(BaseModel):
    question_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: QuestionType
    topic: str = ""
    prompt: str
    options: List[str] = Field(default_factory=list)   # MCQ only
    answer_index: Optional[int] = None                 # MCQ key
    answer_key: str = ""                               # short-answer reference
    rubric: List[str] = Field(default_factory=list)    # short/essay grading criteria
    difficulty: Difficulty = Difficulty.MEDIUM


class Assignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    subject: str = "general"
    source: str = ""                # deck/course id this was generated from
    questions: List[Question] = Field(default_factory=list)
