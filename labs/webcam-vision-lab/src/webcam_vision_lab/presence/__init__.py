"""Presence classification for webcam tiles (silhouette vs live vs absent)."""

from .absence import AbsenceTracker, AbsenceState
from .silhouette import PresenceVisualState, classify_visual_state

__all__ = [
    "AbsenceTracker",
    "AbsenceState",
    "PresenceVisualState",
    "classify_visual_state",
]
