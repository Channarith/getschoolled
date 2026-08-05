"""User-absence / presence tracking (debounced state machine).

Per-frame recognition is noisy: a single dropped frame, a blink of the detector,
or the learner glancing down should not read as "left the class". This turns a
stream of boolean present/absent signals plus timestamps into stable states and
crisp transition events, with attendance timers for reporting.

Pure Python, deterministic, and clock-injectable (callers pass ``now``), so the
whole thing is unit-testable without sleeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PresenceState(str, Enum):
    UNKNOWN = "unknown"     # no signal yet
    PRESENT = "present"     # confirmed in front of the camera
    ABSENT = "absent"       # confirmed away (past the grace period)


class PresenceEvent(str, Enum):
    ARRIVED = "arrived"     # first confirmed presence
    LEFT = "left"           # transitioned present -> absent (user absence!)
    RETURNED = "returned"   # transitioned absent -> present


@dataclass
class PresenceSnapshot:
    """The result of feeding one signal into a :class:`PresenceTracker`."""

    state: PresenceState
    event: Optional[PresenceEvent]
    since: float               # timestamp the current state began
    away_seconds_total: float  # cumulative confirmed-absent time
    present_seconds_total: float  # cumulative confirmed-present time


@dataclass
class PresenceTracker:
    """Debounce raw present/absent signals into stable states + events.

    ``absent_grace_s``: how long the learner must be unseen before we declare
    them ABSENT. ``present_grace_s``: how long they must be seen again before we
    declare them PRESENT. The tracker is edge-triggered: :meth:`update` returns a
    non-None ``event`` only on the frame the state actually flips.
    """

    absent_grace_s: float = 4.0
    present_grace_s: float = 1.0

    state: PresenceState = PresenceState.UNKNOWN
    _state_since: float = 0.0
    # A pending flip we're debouncing: the raw signal changed but the grace
    # window hasn't elapsed yet.
    _pending_present: Optional[bool] = None
    _pending_since: float = 0.0
    _last_now: Optional[float] = None
    away_seconds_total: float = 0.0
    present_seconds_total: float = 0.0
    events: List[PresenceEvent] = field(default_factory=list)

    def _accumulate(self, now: float) -> None:
        """Add elapsed time since the last update to the running totals."""
        if self._last_now is None:
            self._last_now = now
            return
        dt = max(0.0, now - self._last_now)
        if self.state is PresenceState.PRESENT:
            self.present_seconds_total += dt
        elif self.state is PresenceState.ABSENT:
            self.away_seconds_total += dt
        self._last_now = now

    def update(self, present: bool, now: float) -> PresenceSnapshot:
        """Feed one signal (``present``) observed at time ``now`` (seconds)."""
        self._accumulate(now)
        event: Optional[PresenceEvent] = None

        # Bootstrap: the first confirmed signal sets the state immediately.
        if self.state is PresenceState.UNKNOWN:
            if present:
                self.state = PresenceState.PRESENT
                self._state_since = now
                event = PresenceEvent.ARRIVED
            else:
                self.state = PresenceState.ABSENT
                self._state_since = now
            self._pending_present = None
            self._last_now = now
            return self._snapshot(event)

        desired = PresenceState.PRESENT if present else PresenceState.ABSENT
        if desired is self.state:
            # Signal agrees with the current state -> cancel any pending flip.
            self._pending_present = None
        else:
            grace = self.present_grace_s if present else self.absent_grace_s
            if self._pending_present is not present:
                # New pending flip starts its grace window now.
                self._pending_present = present
                self._pending_since = now
            elif now - self._pending_since >= grace:
                # Grace elapsed -> commit the flip and emit the edge event.
                self.state = desired
                self._state_since = now
                self._pending_present = None
                event = (
                    PresenceEvent.RETURNED if present else PresenceEvent.LEFT
                )
                self.events.append(event)

        return self._snapshot(event)

    def _snapshot(self, event: Optional[PresenceEvent]) -> PresenceSnapshot:
        return PresenceSnapshot(
            state=self.state,
            event=event,
            since=self._state_since,
            away_seconds_total=round(self.away_seconds_total, 3),
            present_seconds_total=round(self.present_seconds_total, 3),
        )

    @property
    def is_present(self) -> bool:
        return self.state is PresenceState.PRESENT

    @property
    def is_absent(self) -> bool:
        return self.state is PresenceState.ABSENT
