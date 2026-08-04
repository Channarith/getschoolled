"""Temporal user-absence tracker for webcam teaching sessions.

Combines face observations (YuNet/SFace engagement) with silhouette presence
to decide whether a learner is:

- ``live``            — face visible and liveness/attention ok
- ``silhouette_only`` — body in frame, face not visible (turned away)
- ``absent``          — neither face nor silhouette for longer than grace
- ``unknown``         — no recent signal / stale
- ``spoof``           — too many faces or liveness failed (optional)

Designed for solo class, group live rooms, Theodore teaching, and self-teach
modes in ``apps/webcam-lab``. Pure logic — no OpenCV import required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .silhouette import SilhouetteSignals

PRESENCE_LIVE = "live"
PRESENCE_SILHOUETTE = "silhouette_only"
PRESENCE_ABSENT = "absent"
PRESENCE_UNKNOWN = "unknown"
PRESENCE_SPOOF = "spoof"

PRESENCE_STATES = (
    PRESENCE_LIVE,
    PRESENCE_SILHOUETTE,
    PRESENCE_ABSENT,
    PRESENCE_UNKNOWN,
    PRESENCE_SPOOF,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AbsencePolicy:
    """Tunables for absence / presence-hold decisions."""

    grace_seconds: float = 8.0  # how long silhouette_only/absent before hold
    stale_seconds: float = 20.0  # no signal for this long -> unknown/absent
    require_face_for_live: bool = True
    max_faces_allowed: int = 1
    min_attention_for_live: float = 0.15
    min_silhouette_confidence: float = 0.2

    def __post_init__(self) -> None:
        self.grace_seconds = max(1.0, min(300.0, float(self.grace_seconds)))
        self.stale_seconds = max(2.0, min(120.0, float(self.stale_seconds)))
        self.max_faces_allowed = max(1, min(8, int(self.max_faces_allowed)))
        self.min_attention_for_live = max(0.0, min(1.0, float(self.min_attention_for_live)))
        self.min_silhouette_confidence = max(
            0.0, min(1.0, float(self.min_silhouette_confidence))
        )


@dataclass
class FramePresenceInput:
    """One observation tick from webcam analysis or a client report."""

    face_count: int = 0
    attention: float = 0.0
    gaze_frontal: float = 0.0
    silhouette: Optional[SilhouetteSignals] = None
    liveness_ok: bool = True
    reason: str = ""


@dataclass
class AbsenceDecision:
    """Result of updating the tracker with one frame."""

    state: str
    present: bool  # True when live or silhouette_only
    hold: bool  # True when teaching should pause (absent past grace)
    face_count: int
    silhouette_present: bool
    attention: float
    absent_for_seconds: float
    reason: str
    should_reengage: bool = False  # hint for Theodore / Director


@dataclass
class AbsenceTracker:
    """Per-participant absence state machine."""

    participant_id: str
    policy: AbsencePolicy = field(default_factory=AbsencePolicy)
    state: str = PRESENCE_UNKNOWN
    last_seen_at: Optional[datetime] = None
    absent_since: Optional[datetime] = None
    last_face_at: Optional[datetime] = None
    last_silhouette_at: Optional[datetime] = None
    last_attention: float = 0.0
    last_face_count: int = 0
    last_reason: str = ""

    def update(
        self,
        observation: FramePresenceInput,
        *,
        now: Optional[datetime] = None,
    ) -> AbsenceDecision:
        ref = now or _utcnow()
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        face_count = max(0, int(observation.face_count))
        attention = max(0.0, min(1.0, float(observation.attention or 0.0)))
        sil = observation.silhouette
        sil_present = bool(
            sil
            and sil.present
            and sil.confidence >= self.policy.min_silhouette_confidence
        )

        reason = (observation.reason or "").strip()
        state = PRESENCE_UNKNOWN

        if face_count > self.policy.max_faces_allowed:
            state = PRESENCE_SPOOF
            reason = reason or "too_many_faces"
        elif face_count > 0:
            if not observation.liveness_ok:
                state = PRESENCE_SPOOF
                reason = reason or "liveness_failed"
            elif (
                self.policy.require_face_for_live
                and attention < self.policy.min_attention_for_live
                and not sil_present
            ):
                # Face detected but attention collapsed and no body backup —
                # treat as weak presence (silhouette path if body known).
                state = PRESENCE_SILHOUETTE if sil_present else PRESENCE_LIVE
                reason = reason or "low_attention"
            else:
                state = PRESENCE_LIVE
                reason = reason or "face_visible"
            self.last_face_at = ref
            if sil_present:
                self.last_silhouette_at = ref
        elif sil_present:
            state = PRESENCE_SILHOUETTE
            reason = reason or "silhouette_only"
            self.last_silhouette_at = ref
        else:
            state = PRESENCE_ABSENT
            reason = reason or "no_face_no_silhouette"

        self.last_seen_at = ref
        self.last_attention = attention
        self.last_face_count = face_count
        self.last_reason = reason
        self.state = state

        present = state in (PRESENCE_LIVE, PRESENCE_SILHOUETTE)
        if present:
            self.absent_since = None
            absent_for = 0.0
            hold = False
        else:
            if self.absent_since is None:
                self.absent_since = ref
            absent_for = (ref - self.absent_since).total_seconds()
            hold = absent_for >= self.policy.grace_seconds

        # Stale: if caller stops reporting, mark unknown after stale_seconds.
        # (Caller can also call ``mark_stale``.)
        should_reengage = state == PRESENCE_SILHOUETTE or (
            state == PRESENCE_ABSENT and absent_for >= self.policy.grace_seconds * 0.5
        )

        return AbsenceDecision(
            state=state,
            present=present,
            hold=hold,
            face_count=face_count,
            silhouette_present=sil_present,
            attention=attention,
            absent_for_seconds=round(absent_for, 3),
            reason=reason,
            should_reengage=should_reengage,
        )

    def mark_stale(self, *, now: Optional[datetime] = None) -> AbsenceDecision:
        """Apply stale timeout when no frame has arrived recently."""
        ref = now or _utcnow()
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if self.last_seen_at is None:
            self.state = PRESENCE_UNKNOWN
            return AbsenceDecision(
                state=PRESENCE_UNKNOWN,
                present=False,
                hold=False,
                face_count=0,
                silhouette_present=False,
                attention=0.0,
                absent_for_seconds=0.0,
                reason="no_signal",
                should_reengage=False,
            )
        gap = (ref - self.last_seen_at).total_seconds()
        if gap < self.policy.stale_seconds:
            present = self.state in (PRESENCE_LIVE, PRESENCE_SILHOUETTE)
            absent_for = 0.0
            if self.absent_since is not None:
                absent_for = (ref - self.absent_since).total_seconds()
            return AbsenceDecision(
                state=self.state,
                present=present,
                hold=(not present) and absent_for >= self.policy.grace_seconds,
                face_count=self.last_face_count,
                silhouette_present=self.state == PRESENCE_SILHOUETTE,
                attention=self.last_attention,
                absent_for_seconds=round(absent_for, 3),
                reason=self.last_reason or "ok",
                should_reengage=self.state == PRESENCE_SILHOUETTE,
            )
        self.state = PRESENCE_ABSENT
        if self.absent_since is None:
            self.absent_since = self.last_seen_at
        absent_for = (ref - self.absent_since).total_seconds()
        return AbsenceDecision(
            state=PRESENCE_ABSENT,
            present=False,
            hold=absent_for >= self.policy.grace_seconds,
            face_count=0,
            silhouette_present=False,
            attention=0.0,
            absent_for_seconds=round(absent_for, 3),
            reason="stale_signal",
            should_reengage=True,
        )
