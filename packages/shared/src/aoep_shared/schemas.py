"""Cross-service pydantic schemas.

Shared request/response and domain models so services agree on shapes. Kept
storage-agnostic; persistence lives in db/migrations and the owning service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClassType(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class ConsentScope(str, Enum):
    FACE_RECOGNITION = "face_recognition"
    ATTENTION_TRACKING = "attention_tracking"
    RECORDING = "recording"
    CROSS_CLASS_MEMORY = "cross_class_memory"


class Region(str, Enum):
    """Drives the per-region compliance policy engine."""

    US = "us"          # FERPA
    EU = "eu"          # GDPR
    US_IL = "us_il"    # BIPA (written consent + retention schedule)
    OTHER = "other"


class PlanTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    PREMIUM = "premium"


class Student(BaseModel):
    id: str
    display_name: str
    region: Region = Region.OTHER
    created_at: datetime = Field(default_factory=_utcnow)


class ConsentRecord(BaseModel):
    """A single consent decision, retained for auditability."""

    student_id: str
    scope: ConsentScope
    granted: bool
    region: Region = Region.OTHER
    # BIPA requires written consent; we record the basis + retention window.
    written: bool = False
    retention_days: Optional[int] = None
    recorded_at: datetime = Field(default_factory=_utcnow)


class ClassSession(BaseModel):
    id: str
    class_type: ClassType
    title: str
    language: str = "en"
    persona: str = "friendly"
    room: str
    created_at: datetime = Field(default_factory=_utcnow)


class AgentRole(str, Enum):
    DIRECTOR = "director"
    LESSON = "lesson"
    TUTOR = "tutor"
    ASSESSMENT = "assessment"
    PERCEPTION = "perception"
    SPEECH = "speech"
    MEMORY = "memory"
    CONSENT = "consent"


class HealthStatus(BaseModel):
    service: str
    status: str = "ok"
    deploy_mode: str
    components: dict[str, str] = Field(default_factory=dict)
    version: str = "0.1.0"
