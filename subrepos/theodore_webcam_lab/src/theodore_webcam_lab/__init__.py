"""Theodore webcam + voice prototype package."""

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .games import WebcamLearningGameEngine
from .imaging import ImagingAnalysis, analyze_luminance_grid
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
from .vision_tuning import PRESETS, VisionTuning
from .voice_agents import SUPPORTED_LANGUAGES, XaiVoiceAgent

__all__ = [
    "AnalyzerPolicy",
    "AudioAnswerAssessment",
    "ClassEvaluation",
    "ClassMode",
    "GroupStudentWindowStatus",
    "ImagingAnalysis",
    "LiveSessionMetricsResponse",
    "LessonAlert",
    "LiveMetricsStore",
    "ParticipantEvaluation",
    "ParticipantMetricSeries",
    "PRESETS",
    "PresenceState",
    "QualitySummary",
    "SUPPORTED_LANGUAGES",
    "SupportedLanguage",
    "VoiceQuestion",
    "WebcamGameResult",
    "WebcamGameType",
    "WebcamLearningChallenge",
    "WebcamLearningGameEngine",
    "VisionTuning",
    "VoiceResponse",
    "WebcamSessionAnalyzer",
    "WebcamSignal",
    "XaiVoiceAgent",
    "analyze_luminance_grid",
]
