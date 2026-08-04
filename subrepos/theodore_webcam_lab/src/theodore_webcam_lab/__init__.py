"""Theodore webcam + voice prototype package."""

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .games import WebcamLearningGameEngine
from .types import (
    AudioAnswerAssessment,
    ClassEvaluation,
    ClassMode,
    ParticipantEvaluation,
    PresenceState,
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
    "ParticipantEvaluation",
    "PresenceState",
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
