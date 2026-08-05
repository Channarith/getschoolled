"""User absence tracking with grace windows (mirrors live_room.report_presence)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class AbsenceState(str, Enum):
    DISABLED = "disabled"
    LIVE = "live"
    GRACE = "grace"
    HOLD = "hold"
    STALE = "stale"


@dataclass
class PresenceProbe:
    present: bool = False
    face_count: int = 0
    liveness_state: str = "unknown"
    liveness_score: float = 0.0
    reason: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AbsencePolicy:
    """Aligned with aoep_shared.live_room.PresencePolicy defaults."""

    enabled: bool = True
    grace_seconds: int = 90
    stale_seconds: int = 20
    require_liveness: bool = True
    max_faces_allowed: int = 1


PRESENCE_LIVE = "live"
PRESENCE_ABSENT = "absent"
PRESENCE_UNKNOWN = "unknown"


class AbsenceTracker:
    """Track a single learner's visual presence across periodic webcam probes."""

    def __init__(self, policy: AbsencePolicy | None = None) -> None:
        self.policy = policy or AbsencePolicy()
        self._absent_started_at: Optional[datetime] = None
        self._last_live_at: Optional[datetime] = None
        self._hold_active = False
        self._last_observed_at: Optional[datetime] = None

    @property
    def hold_active(self) -> bool:
        return self._hold_active

    def _is_live_signal(self, probe: PresenceProbe) -> tuple[bool, str]:
        if not self.policy.enabled:
            return True, "disabled"
        if not probe.present or probe.face_count <= 0:
            return False, probe.reason or "no_face"
        if probe.face_count > self.policy.max_faces_allowed:
            return False, "too_many_faces"
        if self.policy.require_liveness and probe.liveness_state != PRESENCE_LIVE:
            return False, "liveness_not_verified"
        return True, probe.reason or "verified"

    def update(self, probe: PresenceProbe) -> AbsenceState:
        """Apply one probe and return the current absence state."""
        ref = probe.observed_at
        self._last_observed_at = ref
        live, reason = self._is_live_signal(probe)

        if live:
            self._absent_started_at = None
            self._last_live_at = ref
            if self._hold_active:
                self._hold_active = False
            return AbsenceState.LIVE

        if not self._absent_started_at:
            self._absent_started_at = ref
            return AbsenceState.GRACE

        elapsed = (ref - self._absent_started_at).total_seconds()
        if elapsed < self.policy.grace_seconds:
            return AbsenceState.GRACE

        self._hold_active = True
        return AbsenceState.HOLD

    def is_stale(self, now: Optional[datetime] = None) -> bool:
        """True when probes stopped arriving (client disconnected / tab frozen)."""
        if not self.policy.enabled or self._last_observed_at is None:
            return False
        ref = now or datetime.now(timezone.utc)
        return (ref - self._last_observed_at).total_seconds() > self.policy.stale_seconds

    def state_at(self, now: Optional[datetime] = None) -> AbsenceState:
        if not self.policy.enabled:
            return AbsenceState.DISABLED
        if self.is_stale(now):
            return AbsenceState.STALE
        if self._hold_active:
            return AbsenceState.HOLD
        if self._last_live_at and (
            self._absent_started_at is None
            or self._last_live_at >= self._absent_started_at
        ):
            return AbsenceState.LIVE
        if self._absent_started_at:
            ref = now or datetime.now(timezone.utc)
            elapsed = (ref - self._absent_started_at).total_seconds()
            if elapsed < self.policy.grace_seconds:
                return AbsenceState.GRACE
            return AbsenceState.HOLD
        return AbsenceState.LIVE

    def simulate_grace_expiry(self, seconds: float) -> AbsenceState:
        """Test helper: advance absent clock without sleeping."""
        if self._absent_started_at is None:
            self._absent_started_at = datetime.now(timezone.utc)
        self._absent_started_at -= timedelta(seconds=seconds)
        return self.state_at()
