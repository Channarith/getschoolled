"""Theodore webcam + voice prototype package."""

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .games import WebcamLearningGameEngine
from .live_metrics import LiveMetricsStore
from .types import (
    AudioAnswerAssessment,
    ClassEvaluation,
    ClassMode,
    GroupStudentWindowStatus,
    LiveSessionMetricsResponse,
    LessonAlert,
    ParticipantEvaluation,
    ParticipantMetricSeries,
    PresenceState,
    QualitySummary,
    SupportedLanguage,
    VoiceQuestion,
    WebcamGameResult,
    WebcamGameType,
    WebcamLearningChallenge,
    VoiceResponse,
    WebcamSignal,
)
from .voice_agents import SUPPORTED_LANGUAGES, XaiVoiceAgent

__all__ = [
    "AnalyzerPolicy",
    "AudioAnswerAssessment",
    "ClassEvaluation",
    "ClassMode",
    "GroupStudentWindowStatus",
    "LiveSessionMetricsResponse",
    "LessonAlert",
    "LiveMetricsStore",
    "ParticipantEvaluation",
    "ParticipantMetricSeries",
    "PresenceState",
    "QualitySummary",
    "SUPPORTED_LANGUAGES",
    "SupportedLanguage",
    "VoiceQuestion",
    "WebcamGameResult",
    "WebcamGameType",
    "WebcamLearningChallenge",
    "WebcamLearningGameEngine",
    "VoiceResponse",
    "WebcamSessionAnalyzer",
    "WebcamSignal",
    "XaiVoiceAgent",
]
