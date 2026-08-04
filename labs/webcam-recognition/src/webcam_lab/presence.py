"""Fuse face + silhouette signals into a present/absent verdict.

Mirrors the live-room presence policy (grace → hold) so the lab can exercise
solo and group class absence without standing up orchestrator + LiveKit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


PRESENCE_LIVE = "live"
PRESENCE_ABSENT = "absent"
PRESENCE_UNKNOWN = "unknown"


@dataclass
class AbsencePolicy:
    """Grace window before an absence triggers a class hold."""

    enabled: bool = True
    grace_seconds: float = 8.0
    require_face: bool = False  # if False, silhouette alone can keep class live
    require_silhouette: bool = False  # if False, face alone can keep class live
    min_face_count: int = 1
    min_silhouette_confidence: float = 0.35

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PresenceVerdict:
    present: bool
    liveness_state: str
    face_count: int = 0
    silhouette_count: int = 0
    silhouette_confidence: float = 0.0
    reason: str = ""
    source: str = "webcam_lab"
    hold_recommended: bool = False
    absent_for_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PresenceFusion:
    """Stateful presence tracker for one learner seat."""

    policy: AbsencePolicy = field(default_factory=AbsencePolicy)
    absent_started_at: Optional[float] = None  # monotonic lab clock seconds
    last_live_at: Optional[float] = None

    def observe(
        self,
        *,
        face_count: int,
        body_present: bool,
        silhouette_count: int = 0,
        silhouette_confidence: float = 0.0,
        now: float = 0.0,
    ) -> PresenceVerdict:
        face_ok = int(face_count or 0) >= self.policy.min_face_count
        # Detector already applied its score floor; trust body_present, but allow
        # an explicit low confidence to reject when provided.
        body_ok = bool(body_present)
        if (
            body_ok
            and float(silhouette_confidence or 0.0) > 0.0
            and float(silhouette_confidence) < self.policy.min_silhouette_confidence
        ):
            body_ok = False

        if self.policy.require_face and self.policy.require_silhouette:
            is_live = face_ok and body_ok
            reason = "" if is_live else "missing_face_or_silhouette"
        elif self.policy.require_face:
            is_live = face_ok
            reason = "" if is_live else "missing_face"
        elif self.policy.require_silhouette:
            is_live = body_ok
            reason = "" if is_live else "missing_silhouette"
        else:
            # Default classroom policy: either face OR body keeps the seat live.
            is_live = face_ok or body_ok
            if is_live:
                reason = "face" if face_ok else "silhouette"
            else:
                reason = "user_absent"

        if is_live:
            self.last_live_at = now
            self.absent_started_at = None
            return PresenceVerdict(
                present=True,
                liveness_state=PRESENCE_LIVE,
                face_count=int(face_count or 0),
                silhouette_count=int(silhouette_count or 0),
                silhouette_confidence=float(silhouette_confidence or 0.0),
                reason=reason or "present",
                hold_recommended=False,
                absent_for_seconds=0.0,
            )

        if self.absent_started_at is None:
            self.absent_started_at = now
        absent_for = max(0.0, float(now) - float(self.absent_started_at))
        hold = (
            self.policy.enabled
            and absent_for >= float(self.policy.grace_seconds)
        )
        return PresenceVerdict(
            present=False,
            liveness_state=PRESENCE_ABSENT,
            face_count=int(face_count or 0),
            silhouette_count=int(silhouette_count or 0),
            silhouette_confidence=float(silhouette_confidence or 0.0),
            reason=reason or "user_absent",
            hold_recommended=hold,
            absent_for_seconds=round(absent_for, 3),
        )


def fuse_batch(
    observations: List[dict],
    *,
    policy: Optional[AbsencePolicy] = None,
) -> List[PresenceVerdict]:
    """Run presence fusion over a list of {face_count, body_present, ...} ticks."""
    tracker = PresenceFusion(policy=policy or AbsencePolicy())
    out: List[PresenceVerdict] = []
    for i, obs in enumerate(observations):
        out.append(
            tracker.observe(
                face_count=int(obs.get("face_count", 0) or 0),
                body_present=bool(obs.get("body_present", False)),
                silhouette_count=int(obs.get("silhouette_count", 0) or 0),
                silhouette_confidence=float(obs.get("silhouette_confidence", 0.0) or 0.0),
                now=float(obs.get("now", i)),
            )
        )
    return out
