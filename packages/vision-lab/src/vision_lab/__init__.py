"""Private-ready webcam recognition lab for Theodore teaching experiments."""

from .presence import (
    PresenceDecision,
    SilhouetteObservation,
    WebcamObservation,
    WebcamPresenceAnalyzer,
)
from .speech_chunks import SpeechChunker
from .xai_voice import XAIConfig, XAIVoiceAgent

__all__ = [
    "PresenceDecision",
    "SilhouetteObservation",
    "SpeechChunker",
    "WebcamObservation",
    "WebcamPresenceAnalyzer",
    "XAIConfig",
    "XAIVoiceAgent",
]
