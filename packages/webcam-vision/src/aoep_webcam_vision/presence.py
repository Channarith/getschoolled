"""Per-participant presence state machine (present / silhouette / absent).

Raw per-frame detections flicker: a face detector misses a turned head for a
frame or two, a motion mask drops when the learner sits still. Teaching must
not react to that noise — Theodore pausing and resuming every few seconds
would be unusable. This module smooths frames into stable states with
independent grace periods:

- ``present``    — a face is visible (highest-confidence "attending" signal).
- ``silhouette`` — a person-shaped silhouette is in frame but no usable face:
  turned away, leaning out, camera partly covered. Entered only after the face
  has been missing for ``silhouette_grace_s`` (anti-flicker).
- ``absent``     — no person in frame at all, sustained for
  ``absence_grace_s``. The learner left; teaching should pause.

Transitions emit :class:`PresenceEvent`s the teaching policies consume:
``user_present``, ``user_silhouette``, ``user_absent``, ``user_returned``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PresenceState(str, Enum):
    PRESENT = "present"
    SILHOUETTE = "silhouette"
    ABSENT = "absent"


# Event kinds (stable strings; the web/mobile clients and tests match on them).
EVENT_PRESENT = "user_present"
EVENT_SILHOUETTE = "user_silhouette"
EVENT_ABSENT = "user_absent"
EVENT_RETURNED = "user_returned"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        return float(raw) if raw.strip() else default
    except ValueError:
        return default


# Defaults are env-tunable so deployments can tighten/loosen without a rebuild.
DEFAULT_SILHOUETTE_GRACE_S = _env_float("WEBCAM_SILHOUETTE_GRACE_S", 5.0)
DEFAULT_ABSENCE_GRACE_S = _env_float("WEBCAM_ABSENCE_GRACE_S", 10.0)


@dataclass
class PresenceEvent:
    """A stable presence transition for one participant."""

    participant_id: str
    kind: str  # EVENT_* above
    state: PresenceState
    at: float
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "kind": self.kind,
            "state": self.state.value,
            "at": self.at,
            "detail": self.detail,
        }


@dataclass
class PresenceTracker:
    """Tracks one participant's presence over a stream of observations."""

    participant_id: str
    silhouette_grace_s: float = DEFAULT_SILHOUETTE_GRACE_S
    absence_grace_s: float = DEFAULT_ABSENCE_GRACE_S
    state: PresenceState = PresenceState.ABSENT
    last_face_at: Optional[float] = None
    last_person_at: Optional[float] = None
    state_since: Optional[float] = None
    absent_since: Optional[float] = None
    _ever_seen: bool = field(default=False, repr=False)

    def observe(
        self,
        *,
        face_visible: bool,
        person_visible: bool,
        at: float,
    ) -> List[PresenceEvent]:
        """Fold one frame's signals into the state machine.

        ``face_visible`` implies ``person_visible`` (a face is a person); the
        caller may pass them independently and they are reconciled here.
        """
        person_visible = person_visible or face_visible
        if face_visible:
            self.last_face_at = at
        if person_visible:
            self.last_person_at = at

        events: List[PresenceEvent] = []
        if face_visible:
            self._transition_to(PresenceState.PRESENT, at, events)
        elif person_visible:
            # From absent, a silhouette is an immediate return; from present,
            # require the face to be gone for the grace period (anti-flicker).
            if self.state is PresenceState.ABSENT:
                self._transition_to(PresenceState.SILHOUETTE, at, events)
            elif self.state is PresenceState.PRESENT:
                face_gone_for = at - (self.last_face_at if self.last_face_at is not None else at)
                if face_gone_for >= self.silhouette_grace_s:
                    self._transition_to(PresenceState.SILHOUETTE, at, events)
            # state already SILHOUETTE: nothing to do.
        else:
            # Nobody in frame: declare absence only after a sustained gap so a
            # single dropped frame never pauses a class.
            gap = at - self.last_person_at if self.last_person_at is not None else None
            if self.state is not PresenceState.ABSENT:
                if gap is None or gap >= self.absence_grace_s:
                    self._transition_to(PresenceState.ABSENT, at, events)
            elif gap is None and not self._ever_seen:
                # Never seen anyone: stay absent silently (no event spam at
                # session start before the camera warms up).
                pass
        if person_visible:
            self._ever_seen = True
        return events

    def _transition_to(
        self,
        target: PresenceState,
        at: float,
        events: List[PresenceEvent],
    ) -> None:
        if target is self.state and self._ever_seen:
            return
        previous = self.state
        first_sighting = not self._ever_seen
        self.state = target
        self.state_since = at
        if target is PresenceState.ABSENT:
            self.absent_since = at
            if not first_sighting:
                events.append(self._event(EVENT_ABSENT, at, "no person in frame"))
            return
        self.absent_since = None
        if previous is PresenceState.ABSENT and not first_sighting:
            events.append(self._event(EVENT_RETURNED, at, "person back in frame"))
            if target is PresenceState.PRESENT:
                # A face on return is also a full "present" signal.
                events.append(self._event(EVENT_PRESENT, at, "face visible"))
            return
        if target is PresenceState.PRESENT:
            events.append(self._event(EVENT_PRESENT, at, "face visible"))
        elif target is PresenceState.SILHOUETTE:
            events.append(
                self._event(EVENT_SILHOUETTE, at, "person in frame, no face")
            )

    def _event(self, kind: str, at: float, detail: str) -> PresenceEvent:
        return PresenceEvent(
            participant_id=self.participant_id,
            kind=kind,
            state=self.state,
            at=at,
            detail=detail,
        )

    def away_duration(self, at: float) -> float:
        """Seconds the participant has been continuously absent (0 if not)."""
        if self.state is not PresenceState.ABSENT or self.absent_since is None:
            return 0.0
        return max(0.0, at - self.absent_since)

    def time_in_state(self, at: float) -> float:
        if self.state_since is None:
            return 0.0
        return max(0.0, at - self.state_since)


class PresenceMonitor:
    """Tracks presence for every participant of a solo or group class."""

    def __init__(
        self,
        *,
        silhouette_grace_s: float = DEFAULT_SILHOUETTE_GRACE_S,
        absence_grace_s: float = DEFAULT_ABSENCE_GRACE_S,
    ) -> None:
        self._silhouette_grace_s = silhouette_grace_s
        self._absence_grace_s = absence_grace_s
        self._trackers: Dict[str, PresenceTracker] = {}

    def tracker(self, participant_id: str) -> PresenceTracker:
        tracker = self._trackers.get(participant_id)
        if tracker is None:
            tracker = PresenceTracker(
                participant_id=participant_id,
                silhouette_grace_s=self._silhouette_grace_s,
                absence_grace_s=self._absence_grace_s,
            )
            self._trackers[participant_id] = tracker
        return tracker

    def observe(
        self,
        participant_id: str,
        *,
        face_visible: bool,
        person_visible: bool,
        at: float,
    ) -> List[PresenceEvent]:
        return self.tracker(participant_id).observe(
            face_visible=face_visible, person_visible=person_visible, at=at
        )

    def state_of(self, participant_id: str) -> PresenceState:
        tracker = self._trackers.get(participant_id)
        return tracker.state if tracker else PresenceState.ABSENT

    def snapshot(self) -> Dict[str, str]:
        """participant_id -> state value, for room-state broadcast."""
        return {pid: t.state.value for pid, t in self._trackers.items()}

    def participants(self) -> List[str]:
        return list(self._trackers)

    def absent_participants(self) -> List[str]:
        return [
            pid for pid, t in self._trackers.items() if t.state is PresenceState.ABSENT
        ]

    def all_absent(self) -> bool:
        """True when every tracked participant is absent (empty room)."""
        return bool(self._trackers) and all(
            t.state is PresenceState.ABSENT for t in self._trackers.values()
        )

    def remove(self, participant_id: str) -> None:
        self._trackers.pop(participant_id, None)
