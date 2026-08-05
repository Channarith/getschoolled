"""Presence tracking: face + silhouette + absence for class sessions.

Mirrors the live-room presence-report vocabulary so lab signals can be bridged
into orchestrator ``POST /api/live-rooms/{id}/presence-report`` without remapping.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .silhouette import SilhouetteHit

PRESENCE_LIVE = "live"
PRESENCE_UNKNOWN = "unknown"
PRESENCE_SPOOF = "spoof"
PRESENCE_ABSENT = "absent"
PRESENCE_SILHOUETTE = "silhouette_only"
PRESENCE_MULTI = "multi_person"

PRESENCE_LIVENESS_STATES = frozenset(
    {
        PRESENCE_LIVE,
        PRESENCE_UNKNOWN,
        PRESENCE_SPOOF,
        PRESENCE_ABSENT,
        PRESENCE_SILHOUETTE,
        PRESENCE_MULTI,
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FaceObservation:
    bbox: Tuple[int, int, int, int]
    det_score: float = 0.0
    attention: float = 0.0
    gaze_frontal: float = 0.0


@dataclass
class PresenceReport:
    """One tick of webcam presence for a participant."""

    present: bool
    face_count: int
    silhouette_count: int
    liveness_state: str
    liveness_score: float
    reason: str
    source: str = "webcam-lab"
    participant_id: str = ""
    observed_at: str = ""
    hold_recommended: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_live_room_payload(self) -> Dict[str, Any]:
        """Shape accepted by orchestrator live-room presence-report.

        Live rooms only accept live/unknown/spoof/absent. Lab-only states
        (silhouette_only, multi_person) are mapped conservatively.
        """
        state = self.liveness_state
        if state == PRESENCE_SILHOUETTE:
            state = PRESENCE_UNKNOWN if self.present else PRESENCE_ABSENT
        elif state == PRESENCE_MULTI:
            state = PRESENCE_SPOOF
        elif state not in (PRESENCE_LIVE, PRESENCE_UNKNOWN, PRESENCE_SPOOF, PRESENCE_ABSENT):
            state = PRESENCE_UNKNOWN
        return {
            "participant_id": self.participant_id,
            "present": self.present,
            "face_count": self.face_count,
            "liveness_state": state,
            "liveness_score": self.liveness_score,
            "reason": self.reason,
            "source": self.source,
        }

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PresenceTracker:
    """Temporal presence state machine for solo/group class webcams.

    Rules (defaults tuned for seated learners):
    - face_count > max_faces -> spoof / multi_person (hold)
    - face present + optional liveness gate -> live
    - no face but silhouette -> silhouette_only (still "present" for soft hold)
    - neither for ``absent_after`` consecutive ticks -> absent (hold)
    """

    def __init__(
        self,
        *,
        max_faces_allowed: int = 1,
        require_liveness: bool = True,
        liveness_min_score: float = 0.35,
        absent_after: int = 3,
        silhouette_counts_as_present: bool = True,
        source: str = "webcam-lab",
    ) -> None:
        self.max_faces_allowed = max(1, int(max_faces_allowed))
        self.require_liveness = bool(require_liveness)
        self.liveness_min_score = float(liveness_min_score)
        self.absent_after = max(1, int(absent_after))
        self.silhouette_counts_as_present = bool(silhouette_counts_as_present)
        self.source = source
        self._miss_streak = 0
        self._last: Optional[PresenceReport] = None

    @property
    def last(self) -> Optional[PresenceReport]:
        return self._last

    def reset(self) -> None:
        self._miss_streak = 0
        self._last = None

    def observe(
        self,
        *,
        faces: Sequence[FaceObservation] = (),
        silhouettes: Sequence[SilhouetteHit] = (),
        participant_id: str = "",
        now: Optional[datetime] = None,
    ) -> PresenceReport:
        now = now or _utcnow()
        face_count = len(faces)
        sil_count = len(silhouettes)

        if face_count > self.max_faces_allowed:
            self._miss_streak = 0
            report = PresenceReport(
                present=True,
                face_count=face_count,
                silhouette_count=sil_count,
                liveness_state=PRESENCE_SPOOF,
                liveness_score=0.0,
                reason="too_many_faces",
                source=self.source,
                participant_id=participant_id,
                observed_at=now.isoformat(),
                hold_recommended=True,
                details={"max_faces_allowed": self.max_faces_allowed},
            )
            self._last = report
            return report

        if face_count > 0:
            self._miss_streak = 0
            face = faces[0]
            score = max(
                0.0,
                min(1.0, float(face.attention) * 0.55 + float(face.gaze_frontal) * 0.45),
            )
            if score <= 0.0 and face.det_score > 0:
                score = max(0.0, min(1.0, float(face.det_score)))
            if self.require_liveness and score < self.liveness_min_score:
                state, reason = PRESENCE_UNKNOWN, "liveness_low"
                hold = True
            else:
                state, reason = PRESENCE_LIVE, "verified"
                hold = False
            report = PresenceReport(
                present=True,
                face_count=face_count,
                silhouette_count=sil_count,
                liveness_state=state,
                liveness_score=round(score, 4),
                reason=reason,
                source=self.source,
                participant_id=participant_id,
                observed_at=now.isoformat(),
                hold_recommended=hold,
            )
            self._last = report
            return report

        if sil_count > 0:
            self._miss_streak = 0
            best = max(s.score for s in silhouettes)
            present = self.silhouette_counts_as_present
            report = PresenceReport(
                present=present,
                face_count=0,
                silhouette_count=sil_count,
                liveness_state=PRESENCE_SILHOUETTE,
                liveness_score=round(float(best), 4),
                reason="silhouette_only",
                source=self.source,
                participant_id=participant_id,
                observed_at=now.isoformat(),
                hold_recommended=not present,
                details={"silhouette_sources": [s.source for s in silhouettes]},
            )
            self._last = report
            return report

        self._miss_streak += 1
        absent = self._miss_streak >= self.absent_after
        report = PresenceReport(
            present=False,
            face_count=0,
            silhouette_count=0,
            liveness_state=PRESENCE_ABSENT if absent else PRESENCE_UNKNOWN,
            liveness_score=0.0,
            reason="no_face" if not absent else "user_absent",
            source=self.source,
            participant_id=participant_id,
            observed_at=now.isoformat(),
            hold_recommended=absent,
            details={"miss_streak": self._miss_streak, "absent_after": self.absent_after},
        )
        self._last = report
        return report

    def observe_counts(
        self,
        *,
        face_count: int,
        silhouette_count: int = 0,
        attention: float = 0.8,
        gaze_frontal: float = 0.8,
        participant_id: str = "",
    ) -> PresenceReport:
        """Convenience for tests / mocks that only know counts."""
        faces = [
            FaceObservation((0, 0, 40, 40), det_score=0.9, attention=attention, gaze_frontal=gaze_frontal)
            for _ in range(max(0, int(face_count)))
        ]
        sils = [
            SilhouetteHit((10, 10, 80, 160), score=0.7, source="injected")
            for _ in range(max(0, int(silhouette_count)))
        ]
        return self.observe(faces=faces, silhouettes=sils, participant_id=participant_id)
