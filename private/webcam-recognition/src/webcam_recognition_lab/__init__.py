"""Private webcam recognition lab package."""

from .absence import AbsenceState, AbsenceTracker
from .signals import (
    FaceObservation,
    ModePolicy,
    PresenceDecision,
    SilhouetteObservation,
    WebcamFrameObservation,
    evaluate_presence,
    mode_policy,
)
from .xai_voice import VoiceAgentEvent, VoiceAgentResponse, XaiVoiceAgent

__all__ = [
    "AbsenceState",
    "AbsenceTracker",
    "FaceObservation",
    "ModePolicy",
    "PresenceDecision",
    "SilhouetteObservation",
    "VoiceAgentEvent",
    "VoiceAgentResponse",
    "WebcamFrameObservation",
    "XaiVoiceAgent",
    "evaluate_presence",
    "mode_policy",
]
