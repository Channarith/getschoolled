"""Private webcam recognition lab for Salareen / Theodore classes.

Build-and-test surface for:
- silhouette + face presence / absence detection
- solo and group class session modes
- Theodore (AI) teaching and learner self-teaching
- xAI Grok Voice Agents for natural spoken replies
"""

from .presence import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_MULTI,
    PRESENCE_SILHOUETTE,
    PRESENCE_UNKNOWN,
    PresenceReport,
    PresenceTracker,
)
from .silhouette import SilhouetteDetector, SilhouetteHit
from .teaching import ClassMode, TeachingMode, TeachingSession
from .xai_voice import OfflineVoiceAgent, XaiVoiceAgent, VoiceAgent

__all__ = [
    "PRESENCE_ABSENT",
    "PRESENCE_LIVE",
    "PRESENCE_MULTI",
    "PRESENCE_SILHOUETTE",
    "PRESENCE_UNKNOWN",
    "PresenceReport",
    "PresenceTracker",
    "SilhouetteDetector",
    "SilhouetteHit",
    "ClassMode",
    "TeachingMode",
    "TeachingSession",
    "OfflineVoiceAgent",
    "XaiVoiceAgent",
    "VoiceAgent",
]

__version__ = "0.1.0"
