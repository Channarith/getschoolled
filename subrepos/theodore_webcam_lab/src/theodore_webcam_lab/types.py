from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class WebcamGameType(str, Enum):
    FOCUS_STREAK = "focus_streak"
    CONFIDENCE_SMILE = "confidence_smile"
    INTEGRITY_GUARD = "integrity_guard"


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
    expression_label: str = Field(default="unknown")
    expression_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    gaze_frontal: float | None = Field(default=None, ge=0.0, le=1.0)
    gaze_down_score: float | None = Field(default=None, ge=0.0, le=1.0)
    phone_visible: bool = False
    typing_activity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    keyboard_typing_audio_score: float | None = Field(default=None, ge=0.0, le=1.0)


class ParticipantEvaluation(BaseModel):
    participant_id: str
    state: PresenceState
    silhouette_detected: bool
    silhouette_streak: int = Field(ge=0)
    face_count: int = Field(ge=0)
    absent_for_ms: int = Field(ge=0)
    eyes_away_for_ms: int = Field(ge=0)
    last_live_timestamp_ms: int | None = Field(default=None, ge=0)
    dominant_expression: str = "unknown"
    expression_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    keyboard_typing_audio_detected: bool = False
    suspected_cheating: bool = False
    cheating_reasons: list[str] = Field(default_factory=list)
    reason: str = ""
    alerts: list[str] = Field(default_factory=list)


class ClassEvaluation(BaseModel):
    session_id: str
    mode: ClassMode
    participants: list[ParticipantEvaluation]
    absent_participant_ids: list[str]
    silhouette_participant_ids: list[str]
    happy_participant_ids: list[str]
    keyboard_typing_audio_participant_ids: list[str]
    suspected_cheating_participant_ids: list[str]
    no_one_present_for_ms: int = Field(default=0, ge=0)
    training_paused: bool = False
    pause_reason: str = ""
    original_participant_id: str = ""
    original_user_present: bool = False
    unexpected_participant_ids: list[str] = Field(default_factory=list)
    expression_counts: dict[str, int]
    alerts: list[str]


class VoiceResponse(BaseModel):
    provider: str
    message: str
    communication_style: str
    fallback_used: bool


class WebcamLearningChallenge(BaseModel):
    challenge_id: str
    session_id: str
    mode: ClassMode
    game_type: WebcamGameType
    title: str
    instruction: str
    learning_prompt: str
    target_duration_ms: int = Field(ge=0)
    participant_ids: list[str] = Field(default_factory=list)


class WebcamGameResult(BaseModel):
    challenge_id: str
    passed: bool
    score_delta: int
    total_score: int
    streak: int
    feedback: str
    evaluation: ClassEvaluation
