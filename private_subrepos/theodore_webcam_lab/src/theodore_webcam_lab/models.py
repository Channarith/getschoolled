from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClassMode(str, Enum):
    solo = "solo"
    group = "group"


class ParticipantSignal(BaseModel):
    participant_id: str
    present: bool = True
    identified: bool = True
    attention: float = Field(default=1.0, ge=0.0, le=1.0)


class WebcamFrameInput(BaseModel):
    session_id: str
    class_mode: ClassMode = ClassMode.solo
    timestamp_ms: int = Field(ge=0)
    expected_participants: int = Field(default=1, ge=1)
    participants: list[ParticipantSignal] = Field(default_factory=list)
    face_count: int | None = Field(default=None, ge=0)
    foreground_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    motion_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class MonitoringEvent(BaseModel):
    code: str
    severity: str
    message: str


class MonitoringDecision(BaseModel):
    session_id: str
    class_mode: ClassMode
    active_participants: int
    expected_participants: int
    silhouette_detected: bool
    user_absent: bool
    group_understaffed: bool
    events: list[MonitoringEvent] = Field(default_factory=list)
    teacher_prompt: str | None = None
    voice_engine: str | None = None
    voice_fallback: bool = False


class VoiceAgentRequest(BaseModel):
    session_id: str
    class_mode: ClassMode
    recent_event_codes: list[str] = Field(default_factory=list)
    student_message: str = ""


class VoiceAgentResponse(BaseModel):
    text: str
    engine: str
    used_fallback: bool
