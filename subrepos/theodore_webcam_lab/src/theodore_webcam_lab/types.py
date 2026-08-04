from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class PresenceState(str, Enum):
    PRESENT = "present"
    TEMPORARILY_MISSING = "temporarily_missing"
    ABSENT = "absent"


class WebcamSignal(BaseModel):
    participant_id: str = Field(min_length=1)
    timestamp_ms: int = Field(ge=0)
    face_count: int = Field(default=0, ge=0)
    liveness_state: str = Field(default="unknown")
    foreground_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    motion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    attention: float | None = Field(default=None, ge=0.0, le=1.0)


class ParticipantEvaluation(BaseModel):
    participant_id: str
    state: PresenceState
    silhouette_detected: bool
    silhouette_streak: int = Field(ge=0)
    face_count: int = Field(ge=0)
    absent_for_ms: int = Field(ge=0)
    last_live_timestamp_ms: int | None = Field(default=None, ge=0)
    reason: str = ""
    alerts: list[str] = Field(default_factory=list)


class ClassEvaluation(BaseModel):
    session_id: str
    mode: ClassMode
    participants: list[ParticipantEvaluation]
    absent_participant_ids: list[str]
    silhouette_participant_ids: list[str]
    alerts: list[str]


class VoiceResponse(BaseModel):
    provider: str
    message: str
    communication_style: str
    fallback_used: bool
