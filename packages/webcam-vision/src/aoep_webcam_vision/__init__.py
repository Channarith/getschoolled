"""aoep_webcam_vision — webcam image recognition for live teaching.

PRIVATE sub-package of the AOEP monorepo (not published). It builds and tests
the webcam image-recognition feature used by both solo classes (Theodore AI-led
and user self-teaching) and group classes (Salareen live rooms):

- :mod:`~aoep_webcam_vision.silhouette` — privacy-preserving human silhouette
  detection (person-shaped presence without face biometrics).
- :mod:`~aoep_webcam_vision.presence` — per-participant presence state machine
  (present / silhouette-only / absent) with anti-flicker grace periods.
- :mod:`~aoep_webcam_vision.monitor` — combines face observations (consent-gated
  YuNet+SFace via the perception provider) with silhouettes into frame analyses.
- :mod:`~aoep_webcam_vision.modes` — teaching policies that turn presence events
  into actions (Theodore pauses when the room is empty, welcomes learners back;
  self-teaching tracks focus time and nudges).
- :mod:`~aoep_webcam_vision.xai_voice` — xAI Grok realtime voice agent client
  (natural spoken responses), with ephemeral tokens for browser/mobile clients.
- :mod:`~aoep_webcam_vision.session` — the session harness that ties monitor +
  policy + voice together for solo and group classes.
"""

from .modes import (
    SelfTeachingPolicy,
    TeachingAction,
    TheodoreTeachingPolicy,
)
from .monitor import FrameAnalysis, FrameSignals, WebcamMonitor
from .presence import (
    PresenceEvent,
    PresenceMonitor,
    PresenceState,
    PresenceTracker,
)
from .session import SessionUpdate, WebcamTeachingSession
from .silhouette import PersonDetection, SilhouetteDetector
from .xai_voice import EphemeralToken, VoiceAgentConfig, XAIVoiceAgent

__all__ = [
    "EphemeralToken",
    "FrameAnalysis",
    "FrameSignals",
    "PersonDetection",
    "PresenceEvent",
    "PresenceMonitor",
    "PresenceState",
    "PresenceTracker",
    "SelfTeachingPolicy",
    "SessionUpdate",
    "SilhouetteDetector",
    "TeachingAction",
    "TheodoreTeachingPolicy",
    "VoiceAgentConfig",
    "WebcamMonitor",
    "WebcamTeachingSession",
    "XAIVoiceAgent",
]

__version__ = "0.1.0"
