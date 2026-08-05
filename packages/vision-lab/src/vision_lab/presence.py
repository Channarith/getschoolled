"""Privacy-safe presence and silhouette heuristics for webcam experiments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from aoep_shared.live_room import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_SPOOF,
    PRESENCE_UNKNOWN,
)


def _bounded(value: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value or 0.0)))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SilhouetteObservation:
    """Body/silhouette signal from an on-device detector.

    The lab stores only summary metadata. A detector can derive these values from
    segmentation, pose, background subtraction, or a simple contour pass without
    passing raw pixels to the backend.
    """

    confidence: float = 0.0
    area_ratio: float = 0.0
    motion_score: float = 0.0
    centeredness: float = 0.0

    def detected(
        self,
        *,
        min_confidence: float = 0.45,
        min_area_ratio: float = 0.06,
    ) -> bool:
        return (
            _bounded(self.confidence) >= min_confidence
            and _bounded(self.area_ratio) >= min_area_ratio
        )


@dataclass(frozen=True)
class WebcamObservation:
    """One privacy-safe webcam tick for a learner."""

    participant_id: str
    participant_name: str = ""
    face_count: int = 0
    attention_score: float = 0.0
    gaze_frontal: float = 0.0
    silhouette: Optional[SilhouetteObservation] = None
    observed_at: str = ""
    source: str = "vision-lab"


@dataclass(frozen=True)
class PresenceDecision:
    """Decision sent to the live-room presence endpoint plus lab-only metadata."""

    participant_id: str
    present: bool
    face_count: int
    liveness_state: str
    liveness_score: float
    reason: str
    source: str
    observed_at: str
    silhouette_state: str = "not_detected"
    attention_score: float = 0.0

    @property
    def verified_live(self) -> bool:
        return self.present and self.liveness_state == PRESENCE_LIVE

    def to_presence_payload(self) -> dict:
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

    def to_lab_record(self) -> dict:
        payload = self.to_presence_payload()
        payload.update(
            {
                "silhouette_state": self.silhouette_state,
                "attention_score": self.attention_score,
                "verified_live": self.verified_live,
            }
        )
        return payload


class WebcamPresenceAnalyzer:
    """Convert face/silhouette detector output into live-room presence signals."""

    def __init__(
        self,
        *,
        max_faces_allowed: int = 1,
        require_liveness: bool = True,
        liveness_floor: float = 0.35,
        silhouette_min_confidence: float = 0.45,
        silhouette_min_area_ratio: float = 0.06,
    ) -> None:
        self.max_faces_allowed = max(1, int(max_faces_allowed or 1))
        self.require_liveness = bool(require_liveness)
        self.liveness_floor = _bounded(liveness_floor)
        self.silhouette_min_confidence = _bounded(silhouette_min_confidence)
        self.silhouette_min_area_ratio = _bounded(silhouette_min_area_ratio)

    def analyze(self, observation: WebcamObservation) -> PresenceDecision:
        participant_id = observation.participant_id.strip()
        if not participant_id:
            raise ValueError("participant_id is required")

        face_count = max(0, int(observation.face_count or 0))
        attention = _bounded(observation.attention_score)
        gaze = _bounded(observation.gaze_frontal)
        observed_at = observation.observed_at.strip() or _iso_now()
        silhouette = observation.silhouette
        silhouette_detected = bool(
            silhouette
            and silhouette.detected(
                min_confidence=self.silhouette_min_confidence,
                min_area_ratio=self.silhouette_min_area_ratio,
            )
        )

        if face_count > self.max_faces_allowed:
            return PresenceDecision(
                participant_id=participant_id,
                present=True,
                face_count=face_count,
                liveness_state=PRESENCE_SPOOF,
                liveness_score=0.0,
                reason="too_many_faces",
                source=observation.source,
                observed_at=observed_at,
                silhouette_state="person_with_multiple_faces"
                if silhouette_detected else "multiple_faces",
                attention_score=attention,
            )

        if face_count > 0:
            score = _bounded(attention * 0.55 + gaze * 0.45)
            live = (not self.require_liveness) or score >= self.liveness_floor
            return PresenceDecision(
                participant_id=participant_id,
                present=True,
                face_count=face_count,
                liveness_state=PRESENCE_LIVE if live else PRESENCE_UNKNOWN,
                liveness_score=score,
                reason="verified" if live else "liveness_low",
                source=observation.source,
                observed_at=observed_at,
                silhouette_state="person_with_face"
                if silhouette_detected else "face_only",
                attention_score=attention,
            )

        if silhouette_detected:
            confidence = _bounded(
                (silhouette.confidence * 0.6)
                + (silhouette.centeredness * 0.25)
                + (silhouette.motion_score * 0.15)
            )
            return PresenceDecision(
                participant_id=participant_id,
                present=True,
                face_count=0,
                liveness_state=PRESENCE_UNKNOWN,
                liveness_score=confidence,
                reason="silhouette_without_face",
                source=observation.source,
                observed_at=observed_at,
                silhouette_state="person_without_face",
                attention_score=0.0,
            )

        return PresenceDecision(
            participant_id=participant_id,
            present=False,
            face_count=0,
            liveness_state=PRESENCE_ABSENT,
            liveness_score=0.0,
            reason="no_person",
            source=observation.source,
            observed_at=observed_at,
            silhouette_state="not_detected",
            attention_score=0.0,
        )
