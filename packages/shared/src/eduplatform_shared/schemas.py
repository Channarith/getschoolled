"""Shared pydantic schemas used across services and the web API."""

from __future__ import annotations

import enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ClassType(str, enum.Enum):
    SOLO = "solo"
    GROUP = "group"


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


class ChatTurn(BaseModel):
    role: str  # "student" | "teacher"
    text: str


class Question(BaseModel):
    text: str
    language: str = "en"
    student_id: Optional[str] = None


class Answer(BaseModel):
    text: str
    citations: List[str] = Field(default_factory=list)
    language: str = "en"


class SessionState(BaseModel):
    session_id: str
    class_type: ClassType
    lesson_id: str
    current_slide: int = 0
    history: List[ChatTurn] = Field(default_factory=list)


class Entitlement(BaseModel):
    allowed: bool
    reason: str = ""
    plan: str = "free"


class HealthStatus(BaseModel):
    status: str = "ok"
    service: str
    deploy_mode: str
