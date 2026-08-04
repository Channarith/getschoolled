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
    face_size_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    light_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    image_detection_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    noise_filter_effectiveness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    microphone_input_level_score: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_noise_level_db: float | None = None
    audio_snr_db: float | None = None
    mic_clipping_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class ParticipantEvaluation(BaseModel):
    participant_id: str
    state: PresenceState
    silhouette_detected: bool
    silhouette_streak: int = Field(ge=0)
    face_count: int = Field(ge=0)
    distance_from_camera_m: float | None = Field(default=None, ge=0.0)
    light_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    image_detection_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    expression_behavior_score: float = Field(default=0.0, ge=0.0, le=1.0)
    audio_noise_level_db: float | None = None
    audio_snr_db: float | None = None
    microphone_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    noise_filter_effectiveness_score: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
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


class GroupStudentWindowStatus(BaseModel):
    participant_id: str
    window_index: int = Field(ge=1)
    state: PresenceState
    suspected_cheating: bool = False
    needs_intervention: bool = False
    severity: str = "none"
    message: str = ""


class LessonAlert(BaseModel):
    level: str
    code: str
    message: str
    participant_id: str = ""
    action: str = ""


class QualitySummary(BaseModel):
    participants_count: int = 0
    avg_distance_from_camera_m: float | None = Field(default=None, ge=0.0)
    avg_light_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_image_detection_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_expression_behavior_score: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_microphone_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    avg_noise_filter_effectiveness_score: float | None = Field(
        default=None, ge=0.0, le=1.0
    )


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
    group_student_windows: list[GroupStudentWindowStatus] = Field(default_factory=list)
    lesson_alerts: list[LessonAlert] = Field(default_factory=list)
    quality_summary: QualitySummary = Field(default_factory=QualitySummary)
    expression_counts: dict[str, int]
    alerts: list[str]


class ParticipantMetricSeries(BaseModel):
    participant_id: str
    window_index: int = Field(ge=1)
    # Every series is index-aligned with timestamps_ms; None marks a missing sample.
    timestamps_ms: list[int] = Field(default_factory=list)
    distance_from_camera_m: list[float | None] = Field(default_factory=list)
    light_quality_score: list[float | None] = Field(default_factory=list)
    image_detection_quality_score: list[float | None] = Field(default_factory=list)
    expression_behavior_score: list[float | None] = Field(default_factory=list)
    microphone_quality_score: list[float | None] = Field(default_factory=list)
    noise_filter_effectiveness_score: list[float | None] = Field(default_factory=list)
    latest: ParticipantEvaluation


class LiveSessionMetricsResponse(BaseModel):
    session_id: str
    updated_at_ms: int = Field(ge=0)
    mode: ClassMode
    training_paused: bool = False
    pause_reason: str = ""
    quality_summary: QualitySummary = Field(default_factory=QualitySummary)
    lesson_alerts: list[LessonAlert] = Field(default_factory=list)
    participants: list[ParticipantMetricSeries] = Field(default_factory=list)


class VoiceResponse(BaseModel):
    provider: str
    message: str
    communication_style: str
    fallback_used: bool
    latency_ms: int = Field(default=0, ge=0)
    cache_hit: bool = False
    tts_voice_style: str = "warm_clear"
    tts_engine_chain: list[str] = Field(
        default_factory=lambda: ["elevenlabs", "edge-tts", "device"]
    )
    should_stream_audio: bool = True


class SupportedLanguage(BaseModel):
    code: str
    name: str


class VoiceQuestion(BaseModel):
    provider: str
    language_code: str
    language_name: str
    question: str
    hint: str
    fallback_used: bool
    latency_ms: int = Field(default=0, ge=0)


class AudioAnswerAssessment(BaseModel):
    provider: str
    language_code: str
    language_name: str
    absorbed_transcript: str
    understood: bool
    understanding_confidence: float = Field(ge=0.0, le=1.0)
    correctness_score: float = Field(ge=0.0, le=1.0)
    feedback_message: str
    follow_up_question: str
    fallback_used: bool
    latency_ms: int = Field(default=0, ge=0)


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
