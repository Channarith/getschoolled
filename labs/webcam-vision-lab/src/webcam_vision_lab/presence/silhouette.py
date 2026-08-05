"""Map face-detection probes to the live-room silhouette / presence UI states.

Mirrors the semantics used in apps/web/app/live-room/[roomId]/page.tsx:
  - waiting_for_join   group class, no student yet (large silhouette placeholder)
  - silhouette_absent  camera on, probed, zero faces (pulsing silhouette overlay)
  - probing            camera on, not yet probed (dim silhouette)
  - present            face_count > 0 within policy
  - too_many_faces     group policy violation
  - camera_off         no local video track
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PresenceVisualState(str, Enum):
    WAITING_FOR_JOIN = "waiting_for_join"
    CAMERA_OFF = "camera_off"
    PROBING = "probing"
    SILHOUETTE_ABSENT = "silhouette_absent"
    PRESENT = "present"
    TOO_MANY_FACES = "too_many_faces"


@dataclass(frozen=True)
class VisualStateInput:
    """Inputs for a single participant tile."""

    camera_on: bool = False
    # -1 = not probed yet (matches live-room presenceFaceCount default)
    face_count: int = -1
    participant_joined: bool = True
    is_group_class: bool = False
    max_faces_allowed: int = 1
    show_waiting_placeholder: bool = False


def classify_visual_state(inp: VisualStateInput) -> PresenceVisualState:
    """Classify which silhouette / presence overlay to show."""
    if inp.show_waiting_placeholder or (
        inp.is_group_class and not inp.participant_joined
    ):
        return PresenceVisualState.WAITING_FOR_JOIN

    if not inp.camera_on:
        return PresenceVisualState.CAMERA_OFF

    if inp.face_count < 0:
        return PresenceVisualState.PROBING

    max_allowed = max(1, int(inp.max_faces_allowed or 1))
    if inp.face_count > max_allowed:
        return PresenceVisualState.TOO_MANY_FACES

    if inp.face_count <= 0:
        return PresenceVisualState.SILHOUETTE_ABSENT

    return PresenceVisualState.PRESENT


def silhouette_opacity(state: PresenceVisualState) -> float:
    """Opacity for the SVG silhouette overlay (matches live-room styling)."""
    if state == PresenceVisualState.PRESENT:
        return 0.35
    if state == PresenceVisualState.PROBING:
        return 0.75
    if state == PresenceVisualState.SILHOUETTE_ABSENT:
        return 0.75
    return 0.0


def silhouette_pulse(state: PresenceVisualState) -> bool:
    """Whether the silhouette should pulse (absent but camera on)."""
    return state == PresenceVisualState.SILHOUETTE_ABSENT


def overlay_message(state: PresenceVisualState) -> Optional[str]:
    if state == PresenceVisualState.WAITING_FOR_JOIN:
        return "Waiting for student to join…"
    if state == PresenceVisualState.SILHOUETTE_ABSENT:
        return "Keep your face in view"
    if state == PresenceVisualState.TOO_MANY_FACES:
        return "Only one learner should be visible"
    return None
