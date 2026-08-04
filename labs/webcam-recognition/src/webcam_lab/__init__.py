"""Private webcam recognition lab for Salareen solo/group classes.

Builds and tests: face recognition signals, body silhouette detection, user
absence, Theodore (AI) teaching vs self-teaching, and xAI Grok voice agents.
"""

from .lab import WebcamLabResult, run_webcam_lab
from .presence import AbsencePolicy, PresenceFusion, PresenceVerdict
from .recognition import ClassRecognitionFrame, recognize_frame
from .session import ClassMode, ClassSession, RoomSize
from .silhouette import SilhouetteDetection, SilhouetteDetector, detect_silhouettes
from .teaching import TeachingMode, TeachingTurn, plan_teaching_turn
from .xai_voice import MockXaiVoiceAgent, XaiVoiceConfig, XaiVoiceSession

__all__ = [
    "AbsencePolicy",
    "ClassMode",
    "ClassRecognitionFrame",
    "ClassSession",
    "MockXaiVoiceAgent",
    "PresenceFusion",
    "PresenceVerdict",
    "RoomSize",
    "SilhouetteDetection",
    "SilhouetteDetector",
    "TeachingMode",
    "TeachingTurn",
    "WebcamLabResult",
    "XaiVoiceConfig",
    "XaiVoiceSession",
    "detect_silhouettes",
    "plan_teaching_turn",
    "recognize_frame",
    "run_webcam_lab",
]
