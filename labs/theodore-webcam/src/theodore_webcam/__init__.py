"""Theodore webcam lab: silhouette presence recognition + xAI Grok voice agents."""

from __future__ import annotations

__version__ = "0.1.0"

from .classroom import ClassSession, SessionRegistry
from .config import LabConfig, load_config
from .cues import ClassMode, Cue, CueAction, CuePolicy
from .presence import PresenceEvent, PresenceEventKind, PresenceState, PresenceTracker
from .silhouette import Silhouette, SilhouetteDetector, SilhouetteObservation
from .xai_voice import XaiUnavailable, XaiVoiceAgent

__all__ = [
    "ClassMode",
    "ClassSession",
    "Cue",
    "CueAction",
    "CuePolicy",
    "LabConfig",
    "PresenceEvent",
    "PresenceEventKind",
    "PresenceState",
    "PresenceTracker",
    "SessionRegistry",
    "Silhouette",
    "SilhouetteDetector",
    "SilhouetteObservation",
    "XaiUnavailable",
    "XaiVoiceAgent",
    "load_config",
    "__version__",
]
