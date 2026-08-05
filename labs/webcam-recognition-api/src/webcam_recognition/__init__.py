"""Webcam image-recognition lab (self-contained sub-project).

A focused sandbox to build and test the camera-driven classroom features before
they graduate into the main platform services:

- Silhouette detection: find the human body outline in a frame (CPU-only OpenCV
  HOG people detector) so presence works even when the face is turned away or
  poorly lit -- ``silhouette``.
- User absence / presence: a debounced state machine that turns noisy per-frame
  signals into stable PRESENT / AWAY transitions with attendance timers --
  ``presence``.
- Solo and group classes: per-learner or per-roster presence + attendance, for
  Theodore (AI) teaching and learner self-teaching -- ``session``.
- xAI (Grok) voice agent: natural spoken responses to classroom events, with a
  graceful offline fallback so the loop always works -- ``voice_agent``.
- Teaching conductor: turns presence/engagement into teaching actions (pause on
  absence, welcome back, nudge attention) phrased by the voice agent --
  ``teaching``.

The pure logic (silhouette geometry, the presence state machine, sessions, the
agent fallback) is dependency-free and unit-tested; OpenCV and the aoep_shared
face engine are imported lazily so the package stays importable without them.
"""

from __future__ import annotations

from .config import LabConfig, load_lab_config
from .presence import (
    PresenceEvent,
    PresenceState,
    PresenceTracker,
)
from .session import (
    ClassMode,
    GroupSession,
    Participant,
    SoloSession,
    TeachingMode,
)
from .silhouette import (
    FramePerception,
    SilhouetteBox,
    analyze_mask,
    summarize_frame,
)
from .teaching import TeachingAction, TeachingConductor
from .voice_agent import VoiceReply, XAIVoiceAgent

__all__ = [
    "LabConfig",
    "load_lab_config",
    "SilhouetteBox",
    "FramePerception",
    "analyze_mask",
    "summarize_frame",
    "PresenceState",
    "PresenceEvent",
    "PresenceTracker",
    "ClassMode",
    "TeachingMode",
    "Participant",
    "SoloSession",
    "GroupSession",
    "XAIVoiceAgent",
    "VoiceReply",
    "TeachingAction",
    "TeachingConductor",
]

__version__ = "0.1.0"
