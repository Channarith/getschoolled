"""Presence and user-absence tracking.

Raw per-frame detection is jittery: a learner leaning out of frame to grab a
notebook must not read as "left the class". This module debounces detection
into a small state machine and accounts for time spent present vs absent, so
Theodore reacts to a *departure*, not to a flicker.

States
------
calibrating -> learning the empty background, no verdict yet
present     -> a silhouette has been held for arrive_confirm_seconds
drifting    -> not detected, but still inside the absence grace window
absent      -> grace expired; the learner is gone
stale       -> no frames are arriving at all (camera off, tab closed)

The clock is injectable so tests drive time instead of sleeping.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from .config import PresenceConfig


class PresenceState(str, Enum):
    CALIBRATING = "calibrating"
    PRESENT = "present"
    DRIFTING = "drifting"
    ABSENT = "absent"
    STALE = "stale"


ABSENT_STATES = {PresenceState.ABSENT, PresenceState.STALE}


class PresenceEventKind(str, Enum):
    CALIBRATED = "calibrated"
    ARRIVED = "arrived"
    DEPARTED = "departed"
    PROLONGED_ABSENCE = "prolonged_absence"
    RETURNED = "returned"
    STALE = "stale"


@dataclass(frozen=True)
class PresenceEvent:
    kind: PresenceEventKind
    state: PresenceState
    at: float
    detail: str = ""
    absence_seconds: float = 0.0

    def as_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "state": self.state.value,
            "at": round(self.at, 3),
            "detail": self.detail,
            "absence_seconds": round(self.absence_seconds, 2),
        }


@dataclass
class PresenceStats:
    present_seconds: float = 0.0
    absent_seconds: float = 0.0
    absence_count: int = 0
    longest_absence_seconds: float = 0.0
    frames_observed: int = 0
    first_seen_at: Optional[float] = None
    last_seen_at: Optional[float] = None

    @property
    def attention_ratio(self) -> float:
        total = self.present_seconds + self.absent_seconds
        if total <= 0:
            return 1.0
        return self.present_seconds / total

    def as_dict(self) -> dict:
        return {
            "present_seconds": round(self.present_seconds, 2),
            "absent_seconds": round(self.absent_seconds, 2),
            "absence_count": self.absence_count,
            "longest_absence_seconds": round(self.longest_absence_seconds, 2),
            "frames_observed": self.frames_observed,
            "attention_ratio": round(self.attention_ratio, 4),
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
        }


@dataclass
class PresenceSnapshot:
    state: PresenceState
    detected: bool
    confidence: float
    silhouette_count: int
    seconds_in_state: float
    absent_seconds: float
    stats: PresenceStats = field(default_factory=PresenceStats)

    @property
    def present(self) -> bool:
        return self.state is PresenceState.PRESENT

    def as_dict(self) -> dict:
        return {
            "state": self.state.value,
            "present": self.present,
            "detected": self.detected,
            "confidence": round(self.confidence, 4),
            "silhouette_count": self.silhouette_count,
            "seconds_in_state": round(self.seconds_in_state, 2),
            "absent_seconds": round(self.absent_seconds, 2),
            "stats": self.stats.as_dict(),
        }


class PresenceTracker:
    """Debounced presence/absence for one participant's camera."""

    def __init__(
        self,
        config: Optional[PresenceConfig] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or PresenceConfig()
        self._clock = clock
        self.state = PresenceState.CALIBRATING
        self.stats = PresenceStats()
        self._detected = False
        self._confidence = 0.0
        self._count = 0
        now = self._clock()
        self._state_since = now
        self._accounted_at = now
        self._last_update = now
        self._candidate_since: Optional[float] = None
        self._left_at: Optional[float] = None
        self._prolonged_emitted = False
        self._calibration_done = False
        self._ever_present = False

    # -- public API ----------------------------------------------------

    def update(
        self,
        *,
        detected: bool,
        confidence: float = 0.0,
        count: int = 0,
        calibrating: bool = False,
        now: Optional[float] = None,
    ) -> List[PresenceEvent]:
        """Feed one observation. Returns the events it caused."""

        now = self._clock() if now is None else now
        events: List[PresenceEvent] = []
        self._accrue(now)
        self._last_update = now
        self.stats.frames_observed += 1
        self._detected = bool(detected) and not calibrating
        self._confidence = float(confidence)
        self._count = int(count)

        if calibrating:
            return events

        if self.state is PresenceState.CALIBRATING and not self._calibration_done:
            self._calibration_done = True
            events.append(
                self._event(PresenceEventKind.CALIBRATED, now, "background learned")
            )

        if self._detected:
            self.stats.last_seen_at = now
            if self.stats.first_seen_at is None:
                self.stats.first_seen_at = now
            events.extend(self._on_detected(now))
        else:
            events.extend(self._on_not_detected(now))
        return events

    def tick(self, now: Optional[float] = None) -> List[PresenceEvent]:
        """Advance time without a new frame (grace expiry, staleness)."""

        now = self._clock() if now is None else now
        events: List[PresenceEvent] = []
        self._accrue(now)

        silence = now - self._last_update
        if (
            silence >= self.config.stale_seconds
            and self.state not in (PresenceState.STALE, PresenceState.CALIBRATING)
        ):
            if self._left_at is None:
                self._left_at = self._last_update
            if self.state is not PresenceState.ABSENT:
                self.stats.absence_count += 1
            self._transition(PresenceState.STALE, now)
            events.append(
                self._event(
                    PresenceEventKind.STALE,
                    now,
                    "no camera frames received",
                    absence_seconds=now - self._left_at,
                )
            )
            return events

        if self.state is PresenceState.DRIFTING:
            events.extend(self._maybe_depart(now))
        elif self.state in ABSENT_STATES:
            events.extend(self._maybe_prolonged(now))
        return events

    def snapshot(self, now: Optional[float] = None) -> PresenceSnapshot:
        now = self._clock() if now is None else now
        return PresenceSnapshot(
            state=self.state,
            detected=self._detected,
            confidence=self._confidence,
            silhouette_count=self._count,
            seconds_in_state=now - self._state_since,
            absent_seconds=self.absent_seconds(now),
            stats=self.stats,
        )

    def absent_seconds(self, now: Optional[float] = None) -> float:
        if self.state not in ABSENT_STATES and self.state is not PresenceState.DRIFTING:
            return 0.0
        if self._left_at is None:
            return 0.0
        now = self._clock() if now is None else now
        return max(0.0, now - self._left_at)

    # -- internals -----------------------------------------------------

    def _on_detected(self, now: float) -> List[PresenceEvent]:
        events: List[PresenceEvent] = []
        if self.state is PresenceState.PRESENT:
            self._candidate_since = None
            return events

        if self._candidate_since is None:
            self._candidate_since = now

        returning = self.state in ABSENT_STATES and self._ever_present
        needed = (
            self.config.return_confirm_seconds
            if returning
            else self.config.arrive_confirm_seconds
        )
        if now - self._candidate_since < needed:
            return events

        absence = 0.0
        if self._left_at is not None:
            absence = max(0.0, now - self._left_at)
        self._candidate_since = None
        self._left_at = None
        self._prolonged_emitted = False
        previous = self.state
        self._transition(PresenceState.PRESENT, now)
        self._ever_present = True

        if returning:
            self.stats.longest_absence_seconds = max(
                self.stats.longest_absence_seconds, absence
            )
            events.append(
                self._event(
                    PresenceEventKind.RETURNED,
                    now,
                    f"learner returned after {absence:.0f}s",
                    absence_seconds=absence,
                )
            )
        elif previous is not PresenceState.DRIFTING:
            events.append(self._event(PresenceEventKind.ARRIVED, now, "learner in frame"))
        return events

    def _on_not_detected(self, now: float) -> List[PresenceEvent]:
        self._candidate_since = None
        if self.state is PresenceState.PRESENT:
            self._left_at = now
            self._transition(PresenceState.DRIFTING, now)
            return []
        if self.state is PresenceState.CALIBRATING:
            # Calibration finished with an empty chair: absent, but nobody
            # departed, so this is a silent transition.
            if self._left_at is None:
                self._left_at = now
            self._transition(PresenceState.ABSENT, now)
            return []
        if self.state is PresenceState.DRIFTING:
            return self._maybe_depart(now)
        if self.state in ABSENT_STATES:
            return self._maybe_prolonged(now)
        return []

    def _maybe_depart(self, now: float) -> List[PresenceEvent]:
        if self._left_at is None:
            self._left_at = now
        gone = now - self._left_at
        if gone < self.config.absence_grace_seconds:
            return []
        self.stats.absence_count += 1
        self._transition(PresenceState.ABSENT, now)
        return [
            self._event(
                PresenceEventKind.DEPARTED,
                now,
                f"no silhouette for {gone:.0f}s",
                absence_seconds=gone,
            )
        ]

    def _maybe_prolonged(self, now: float) -> List[PresenceEvent]:
        if self._prolonged_emitted or self._left_at is None:
            return []
        if not self._ever_present:
            # Never showed up in the first place; that is a no-show, not an
            # absence, and the class report covers it.
            return []
        gone = now - self._left_at
        if gone < self.config.prolonged_absence_seconds:
            return []
        self._prolonged_emitted = True
        return [
            self._event(
                PresenceEventKind.PROLONGED_ABSENCE,
                now,
                f"absent for {gone:.0f}s",
                absence_seconds=gone,
            )
        ]

    def _transition(self, state: PresenceState, now: float) -> None:
        if state is not self.state:
            self.state = state
            self._state_since = now

    def _accrue(self, now: float) -> None:
        elapsed = max(0.0, now - self._accounted_at)
        self._accounted_at = now
        if not elapsed:
            return
        if self.state is PresenceState.PRESENT:
            self.stats.present_seconds += elapsed
        elif self.state in ABSENT_STATES:
            self.stats.absent_seconds += elapsed
            if self._left_at is not None:
                self.stats.longest_absence_seconds = max(
                    self.stats.longest_absence_seconds, now - self._left_at
                )

    def _event(
        self,
        kind: PresenceEventKind,
        now: float,
        detail: str,
        *,
        absence_seconds: float = 0.0,
    ) -> PresenceEvent:
        return PresenceEvent(
            kind=kind,
            state=self.state,
            at=now,
            detail=detail,
            absence_seconds=absence_seconds,
        )
