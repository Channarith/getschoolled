"""Webcam presence and silhouette policy for the private AOEP lab.

The production perception stack can own model execution. This module owns the
small, testable policy layer that turns model/client observations into a live-room
presence-report payload and Theodore teaching action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Sequence

ClassMode = Literal["solo_ai_teaching", "solo_self_teaching", "group_class"]
LivenessState = Literal["live", "unknown", "spoof", "absent"]
TeacherAction = Literal[
    "continue",
    "reengage",
    "ask_camera_adjustment",
    "pause_until_return",
]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str:
    return (dt or _utc_now()).astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ModePolicy:
    mode: ClassMode
    require_liveness: bool
    pause_on_absence: bool
    max_faces_allowed: int
    absence_grace_seconds: int = 90
    low_attention_threshold: float = 0.35
    silhouette_threshold: float = 0.55


def mode_policy(mode: ClassMode) -> ModePolicy:
    if mode == "solo_self_teaching":
        return ModePolicy(
            mode=mode,
            require_liveness=False,
            pause_on_absence=False,
            max_faces_allowed=1,
            absence_grace_seconds=180,
        )
    if mode == "group_class":
        return ModePolicy(
            mode=mode,
            require_liveness=True,
            pause_on_absence=True,
            max_faces_allowed=1,
            absence_grace_seconds=90,
        )
    return ModePolicy(
        mode=mode,
        require_liveness=True,
        pause_on_absence=True,
        max_faces_allowed=1,
        absence_grace_seconds=90,
    )


@dataclass(frozen=True)
class FaceObservation:
    track_id: str
    attention: float = 1.0
    gaze_frontal: float = 1.0
    identified: bool = False
    matched_student_id: str | None = None

    def __post_init__(self) -> None:
        if not self.track_id.strip():
            raise ValueError("face track_id is required")
        object.__setattr__(self, "attention", _clamp(self.attention))
        object.__setattr__(self, "gaze_frontal", _clamp(self.gaze_frontal))


@dataclass(frozen=True)
class SilhouetteObservation:
    track_id: str
    bbox: tuple[int, int, int, int]
    frame_size: tuple[int, int]
    confidence: float = 0.0
    motion_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.track_id.strip():
            raise ValueError("silhouette track_id is required")
        if len(self.bbox) != 4 or len(self.frame_size) != 2:
            raise ValueError("bbox must be x,y,w,h and frame_size must be w,h")
        if self.frame_size[0] <= 0 or self.frame_size[1] <= 0:
            raise ValueError("frame_size must be positive")
        object.__setattr__(self, "confidence", _clamp(self.confidence))
        object.__setattr__(self, "motion_score", _clamp(self.motion_score))

    @property
    def area_ratio(self) -> float:
        _, _, width, height = self.bbox
        frame_w, frame_h = self.frame_size
        return _clamp((max(0, width) * max(0, height)) / float(frame_w * frame_h))

    @property
    def person_shape_score(self) -> float:
        _, _, width, height = self.bbox
        if width <= 0 or height <= 0:
            return 0.0
        aspect = height / float(width)
        aspect_score = 1.0 - min(1.0, abs(aspect - 2.2) / 2.2)
        size_score = min(1.0, self.area_ratio / 0.12)
        return _clamp(0.55 * aspect_score + 0.45 * size_score)

    @property
    def presence_score(self) -> float:
        return round(
            _clamp(
                0.5 * self.confidence
                + 0.3 * self.person_shape_score
                + 0.2 * self.motion_score
            ),
            4,
        )


@dataclass(frozen=True)
class WebcamFrameObservation:
    participant_id: str
    faces: Sequence[FaceObservation] = field(default_factory=tuple)
    silhouettes: Sequence[SilhouetteObservation] = field(default_factory=tuple)
    observed_at: datetime | None = None
    source: str = "webcam-recognition-lab"

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("participant_id is required")


@dataclass(frozen=True)
class PresenceDecision:
    participant_id: str
    present: bool
    face_count: int
    silhouette_count: int
    liveness_state: LivenessState
    liveness_score: float
    attention: float
    reason: str
    source: str
    observed_at: str
    teacher_action: TeacherAction
    should_pause: bool = False

    def to_presence_report(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "present": self.present,
            "face_count": self.face_count,
            "liveness_state": self.liveness_state,
            "liveness_score": self.liveness_score,
            "reason": self.reason,
            "source": self.source,
            "observed_at": self.observed_at,
        }


def evaluate_presence(
    frame: WebcamFrameObservation,
    *,
    mode: ClassMode,
    policy: ModePolicy | None = None,
) -> PresenceDecision:
    active_policy = policy or mode_policy(mode)
    faces = list(frame.faces)
    silhouettes = list(frame.silhouettes)
    face_count = len(faces)
    best_attention = max((f.attention for f in faces), default=0.0)
    best_gaze = max((f.gaze_frontal for f in faces), default=0.0)
    best_silhouette = max((s.presence_score for s in silhouettes), default=0.0)
    observed_at = _iso(frame.observed_at)

    if face_count > active_policy.max_faces_allowed:
        return PresenceDecision(
            participant_id=frame.participant_id,
            present=False,
            face_count=face_count,
            silhouette_count=len(silhouettes),
            liveness_state="spoof",
            liveness_score=0.0,
            attention=best_attention,
            reason="too_many_faces",
            source=frame.source,
            observed_at=observed_at,
            teacher_action="pause_until_return",
            should_pause=active_policy.pause_on_absence,
        )

    if face_count == 1:
        low_attention = best_attention < active_policy.low_attention_threshold
        return PresenceDecision(
            participant_id=frame.participant_id,
            present=True,
            face_count=face_count,
            silhouette_count=len(silhouettes),
            liveness_state="live",
            liveness_score=round(_clamp(0.6 * best_gaze + 0.4 * best_attention), 4),
            attention=round(best_attention, 4),
            reason="low_attention" if low_attention else "verified_face",
            source=frame.source,
            observed_at=observed_at,
            teacher_action="reengage" if low_attention else "continue",
            should_pause=False,
        )

    if best_silhouette >= active_policy.silhouette_threshold:
        return PresenceDecision(
            participant_id=frame.participant_id,
            present=True,
            face_count=0,
            silhouette_count=len(silhouettes),
            liveness_state="unknown" if active_policy.require_liveness else "live",
            liveness_score=best_silhouette,
            attention=0.0,
            reason="silhouette_only",
            source=frame.source,
            observed_at=observed_at,
            teacher_action="ask_camera_adjustment",
            should_pause=active_policy.require_liveness and active_policy.pause_on_absence,
        )

    return PresenceDecision(
        participant_id=frame.participant_id,
        present=False,
        face_count=0,
        silhouette_count=len(silhouettes),
        liveness_state="absent",
        liveness_score=0.0,
        attention=0.0,
        reason="absent",
        source=frame.source,
        observed_at=observed_at,
        teacher_action="pause_until_return" if active_policy.pause_on_absence else "reengage",
        should_pause=active_policy.pause_on_absence,
    )
