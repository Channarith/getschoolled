"""Presence and absence tracking for webcam teaching sessions.

Combines face recognition signals (from VisionProvider) with silhouette
detection (from SilhouetteDetector) into a unified presence state machine
that the teaching loop consumes.

Key concepts:

PresenceState
    The current state for a single participant slot: PRESENT, AWAY, ABSENT,
    or UNKNOWN. Transitions are governed by configurable debounce windows to
    avoid thrashing on brief occlusions (student scratched their head, etc.).

PresenceTracker
    Per-session tracker. Receives ``PresenceFrame`` events (face + silhouette
    results), updates state, and fires typed callbacks so the orchestrator /
    webcam service can react.

GroupPresenceTracker
    Aggregates per-participant ``PresenceTracker`` objects for a group class.
    Exposes roll-call and quorum checks Theodore uses to decide whether to
    pause, skip, or continue.

Events raised:
- ``PresenceEvent.AWAY``   — user likely stepped away (below presence threshold)
- ``PresenceEvent.RETURNED`` — user came back to camera
- ``PresenceEvent.ABSENT``  — confirmed absent after grace period
- ``PresenceEvent.JOINED``  — first frame with confirmed presence
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Deque, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Domain types
# --------------------------------------------------------------------------- #

class PresenceState(str, Enum):
    UNKNOWN = "unknown"
    PRESENT = "present"
    AWAY = "away"       # recently lost — within grace period
    ABSENT = "absent"   # confirmed absent after grace period


class PresenceEvent(str, Enum):
    JOINED = "joined"
    AWAY = "away"
    RETURNED = "returned"
    ABSENT = "absent"
    PARTIAL = "partial"   # silhouette only, no face (back turned / obscured)


@dataclass
class PresenceFrame:
    """Input data for one analysis tick.

    At least one of ``face_present`` or ``silhouette_present`` should be set.
    ``attention`` is from the VisionProvider face engagement (0..1); may be
    None when the face was not detected.
    """

    face_present: bool
    silhouette_present: bool
    attention: Optional[float] = None           # 0..1 from face engagement
    silhouette_absence_confidence: float = 0.0  # from SilhouetteResult
    face_absence_confidence: float = 0.0        # inferred when face not found
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def any_present(self) -> bool:
        return self.face_present or self.silhouette_present

    @property
    def combined_absence_confidence(self) -> float:
        """Merge face and silhouette absence signals (higher = more confident absent)."""
        if self.any_present:
            return 0.0
        return min(1.0, max(
            self.silhouette_absence_confidence,
            self.face_absence_confidence,
        ))


@dataclass
class PresenceStatus:
    """Point-in-time presence summary for one participant."""

    participant_id: str
    state: PresenceState
    face_present: bool
    silhouette_present: bool
    attention: float         # most recent non-None attention or 0
    away_duration_s: float   # seconds in current AWAY/ABSENT state (0 if present)
    consecutive_absent_frames: int
    last_seen_ts: float      # monotonic timestamp of last confirmed presence
    event: Optional[PresenceEvent] = None  # event that caused last transition


# --------------------------------------------------------------------------- #
# Single-participant tracker
# --------------------------------------------------------------------------- #

EventCallback = Callable[["PresenceStatus"], None]


class PresenceTracker:
    """Per-participant presence state machine.

    Parameters
    ----------
    participant_id:
        Opaque string identifying the participant.
    away_grace_s:
        Seconds of absence before transitioning from PRESENT → AWAY.
    absent_confirm_s:
        Seconds in AWAY before confirming ABSENT.
    presence_window:
        Number of recent frames to keep for rolling statistics.
    on_event:
        Optional callback invoked on every state transition.
    """

    def __init__(
        self,
        participant_id: str,
        away_grace_s: float = 5.0,
        absent_confirm_s: float = 30.0,
        presence_window: int = 30,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self.participant_id = participant_id
        self._away_grace = away_grace_s
        self._absent_confirm = absent_confirm_s
        self._window: Deque[PresenceFrame] = deque(maxlen=presence_window)
        self._on_event = on_event

        self._state: PresenceState = PresenceState.UNKNOWN
        self._last_present_ts: Optional[float] = None
        self._absent_since_ts: Optional[float] = None
        self._consecutive_absent: int = 0
        self._last_attention: float = 0.0
        self._last_event: Optional[PresenceEvent] = None

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> PresenceState:
        return self._state

    def push(self, frame: PresenceFrame) -> PresenceStatus:
        """Feed a new frame observation; returns updated status (may trigger callback)."""
        self._window.append(frame)
        if frame.attention is not None:
            self._last_attention = frame.attention

        now = frame.timestamp
        event: Optional[PresenceEvent] = None

        if frame.face_present:
            # Clear absence tracking.
            if self._state != PresenceState.PRESENT:
                event = (
                    PresenceEvent.JOINED
                    if self._state == PresenceState.UNKNOWN
                    else PresenceEvent.RETURNED
                )
            self._state = PresenceState.PRESENT
            self._last_present_ts = now
            self._absent_since_ts = None
            self._consecutive_absent = 0

        elif frame.silhouette_present:
            # Body visible but no face — partial presence.
            if self._state == PresenceState.UNKNOWN:
                event = PresenceEvent.PARTIAL
                self._state = PresenceState.PRESENT
                self._last_present_ts = now
            elif self._state in (PresenceState.AWAY, PresenceState.ABSENT):
                event = PresenceEvent.RETURNED
                self._state = PresenceState.PRESENT
                self._last_present_ts = now
            else:
                event = PresenceEvent.PARTIAL
            self._consecutive_absent = 0
            self._absent_since_ts = None

        else:
            # Neither face nor silhouette detected.
            self._consecutive_absent += 1
            if self._state == PresenceState.PRESENT:
                if (self._last_present_ts is not None
                        and now - self._last_present_ts >= self._away_grace):
                    self._state = PresenceState.AWAY
                    self._absent_since_ts = self._last_present_ts
                    event = PresenceEvent.AWAY
            elif self._state == PresenceState.AWAY:
                absent_elapsed = (
                    now - self._absent_since_ts
                    if self._absent_since_ts is not None else 0.0
                )
                if absent_elapsed >= self._absent_confirm:
                    self._state = PresenceState.ABSENT
                    event = PresenceEvent.ABSENT
            elif self._state == PresenceState.UNKNOWN:
                pass  # stay unknown until first detection

        self._last_event = event
        status = self._build_status(now, event)
        if event is not None and self._on_event is not None:
            try:
                self._on_event(status)
            except Exception:  # noqa: BLE001
                pass
        return status

    def reset(self) -> None:
        """Reset tracker (e.g. on new session or student re-join)."""
        self._state = PresenceState.UNKNOWN
        self._last_present_ts = None
        self._absent_since_ts = None
        self._consecutive_absent = 0
        self._window.clear()

    def status(self) -> PresenceStatus:
        """Return the current status without a new frame."""
        return self._build_status(time.monotonic(), None)

    # ------------------------------------------------------------------ #
    # Rolling statistics
    # ------------------------------------------------------------------ #

    def rolling_attention(self) -> float:
        """Mean attention over the recent window (only frames with face)."""
        vals = [f.attention for f in self._window if f.attention is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def presence_ratio(self) -> float:
        """Fraction of recent frames with any presence signal."""
        if not self._window:
            return 0.0
        return round(sum(1 for f in self._window if f.any_present) / len(self._window), 4)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_status(self, now: float, event: Optional[PresenceEvent]) -> PresenceStatus:
        if self._absent_since_ts is not None:
            away_dur = now - self._absent_since_ts
        elif self._state != PresenceState.PRESENT and self._last_present_ts is not None:
            away_dur = now - self._last_present_ts
        else:
            away_dur = 0.0

        return PresenceStatus(
            participant_id=self.participant_id,
            state=self._state,
            face_present=bool(self._window and self._window[-1].face_present),
            silhouette_present=bool(
                self._window and self._window[-1].silhouette_present
            ),
            attention=self.rolling_attention(),
            away_duration_s=round(max(0.0, away_dur), 2),
            consecutive_absent_frames=self._consecutive_absent,
            last_seen_ts=self._last_present_ts or 0.0,
            event=event,
        )


# --------------------------------------------------------------------------- #
# Group tracker
# --------------------------------------------------------------------------- #

@dataclass
class GroupPresenceSummary:
    """Aggregated presence state for a group class."""

    total_participants: int
    present_count: int
    away_count: int
    absent_count: int
    unknown_count: int
    quorum_met: bool           # enough participants present to continue class
    average_attention: float   # 0..1 across present participants
    absent_ids: List[str]      # participant IDs confirmed absent
    away_ids: List[str]        # participant IDs away (grace period)

    @property
    def present_ratio(self) -> float:
        if self.total_participants == 0:
            return 0.0
        return round(self.present_count / self.total_participants, 4)


class GroupPresenceTracker:
    """Tracks presence across all participants in a group class.

    Parameters
    ----------
    quorum_ratio:
        Fraction of enrolled participants that must be PRESENT for quorum.
    away_grace_s / absent_confirm_s:
        Passed to each per-participant ``PresenceTracker``.
    on_quorum_lost / on_quorum_met:
        Callbacks invoked when quorum transitions.
    """

    def __init__(
        self,
        quorum_ratio: float = 0.5,
        away_grace_s: float = 5.0,
        absent_confirm_s: float = 30.0,
        on_quorum_lost: Optional[Callable[[GroupPresenceSummary], None]] = None,
        on_quorum_met: Optional[Callable[[GroupPresenceSummary], None]] = None,
    ) -> None:
        self._quorum_ratio = quorum_ratio
        self._away_grace = away_grace_s
        self._absent_confirm = absent_confirm_s
        self._on_quorum_lost = on_quorum_lost
        self._on_quorum_met = on_quorum_met

        self._trackers: Dict[str, PresenceTracker] = {}
        self._quorum_state: Optional[bool] = None  # None = not yet established

    def ensure_participant(
        self, participant_id: str, on_event: Optional[EventCallback] = None
    ) -> PresenceTracker:
        """Get or create a tracker for ``participant_id``."""
        if participant_id not in self._trackers:
            self._trackers[participant_id] = PresenceTracker(
                participant_id,
                away_grace_s=self._away_grace,
                absent_confirm_s=self._absent_confirm,
                on_event=on_event,
            )
        return self._trackers[participant_id]

    def push(
        self, participant_id: str, frame: PresenceFrame
    ) -> PresenceStatus:
        """Feed a frame for one participant and update group quorum."""
        tracker = self.ensure_participant(participant_id)
        status = tracker.push(frame)
        self._check_quorum()
        return status

    def remove_participant(self, participant_id: str) -> None:
        self._trackers.pop(participant_id, None)

    def summary(self) -> GroupPresenceSummary:
        """Return the current group-level presence summary."""
        counts: Dict[PresenceState, int] = {s: 0 for s in PresenceState}
        attentions: List[float] = []
        absent_ids: List[str] = []
        away_ids: List[str] = []

        for pid, tracker in self._trackers.items():
            s = tracker.state
            counts[s] += 1
            if s == PresenceState.PRESENT:
                attentions.append(tracker.rolling_attention())
            elif s == PresenceState.ABSENT:
                absent_ids.append(pid)
            elif s == PresenceState.AWAY:
                away_ids.append(pid)

        total = len(self._trackers)
        present = counts[PresenceState.PRESENT]
        quorum_met = (
            present / total >= self._quorum_ratio if total > 0 else False
        )
        avg_att = round(sum(attentions) / len(attentions), 4) if attentions else 0.0

        return GroupPresenceSummary(
            total_participants=total,
            present_count=present,
            away_count=counts[PresenceState.AWAY],
            absent_count=counts[PresenceState.ABSENT],
            unknown_count=counts[PresenceState.UNKNOWN],
            quorum_met=quorum_met,
            average_attention=avg_att,
            absent_ids=absent_ids,
            away_ids=away_ids,
        )

    def all_statuses(self) -> List[PresenceStatus]:
        return [t.status() for t in self._trackers.values()]

    # ------------------------------------------------------------------ #
    # Internal quorum management
    # ------------------------------------------------------------------ #

    def _check_quorum(self) -> None:
        s = self.summary()
        was = self._quorum_state
        now = s.quorum_met
        if was is None:
            self._quorum_state = now
            return
        if now != was:
            self._quorum_state = now
            cb = self._on_quorum_met if now else self._on_quorum_lost
            if cb is not None:
                try:
                    cb(s)
                except Exception:  # noqa: BLE001
                    pass
