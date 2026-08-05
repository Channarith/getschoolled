"""Solo and group class sessions built on presence tracking.

- :class:`SoloSession`: one learner (self-teaching or 1:1 with Theodore). Wraps a
  single :class:`PresenceTracker` and records attention over time.
- :class:`GroupSession`: a roster of learners (group class). Each participant has
  their own tracker; the session reports live headcount, who is present/away, and
  per-participant attendance -- so Theodore knows the room, and a self-study group
  can see who stepped out.

Both consume :class:`FramePerception` objects from the recognition layer and emit
the same :class:`PresenceEvent` transitions the teaching conductor reacts to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .config import LabConfig
from .presence import PresenceEvent, PresenceState, PresenceTracker
from .silhouette import FramePerception


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class TeachingMode(str, Enum):
    # Theodore leads the lesson (AI teaching) and reacts to the room.
    THEODORE = "theodore"
    # The learner drives; the agent is a responsive tutor / study buddy.
    SELF = "self"


@dataclass
class SessionEvent:
    """A presence transition attributed to a participant."""

    participant_id: str
    event: PresenceEvent
    at: float
    state: PresenceState


@dataclass
class SoloSession:
    session_id: str
    teaching_mode: TeachingMode
    config: LabConfig
    tracker: PresenceTracker = field(init=False)
    attention_ewma: float = 0.0
    _attention_seen: bool = False
    last_event: Optional[SessionEvent] = None

    def __post_init__(self) -> None:
        self.tracker = PresenceTracker(
            absent_grace_s=self.config.absent_grace_s,
            present_grace_s=self.config.present_grace_s,
        )

    def observe(self, perception: FramePerception, now: float) -> Optional[SessionEvent]:
        snap = self.tracker.update(perception.person_present, now)
        if perception.face_count > 0:
            a = perception.attention
            self.attention_ewma = a if not self._attention_seen else (
                0.7 * self.attention_ewma + 0.3 * a
            )
            self._attention_seen = True
        if snap.event is not None:
            self.last_event = SessionEvent(
                participant_id="learner",
                event=snap.event,
                at=now,
                state=snap.state,
            )
            return self.last_event
        return None

    def status(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": ClassMode.SOLO.value,
            "teaching_mode": self.teaching_mode.value,
            "state": self.tracker.state.value,
            "present": self.tracker.is_present,
            "attention": round(self.attention_ewma, 4),
            "away_seconds_total": round(self.tracker.away_seconds_total, 3),
            "present_seconds_total": round(self.tracker.present_seconds_total, 3),
        }


@dataclass
class Participant:
    participant_id: str
    display_name: str
    tracker: PresenceTracker


@dataclass
class GroupSession:
    session_id: str
    teaching_mode: TeachingMode
    config: LabConfig
    participants: Dict[str, Participant] = field(default_factory=dict)

    def enroll(self, participant_id: str, display_name: str = "") -> Participant:
        p = self.participants.get(participant_id)
        if p is None:
            p = Participant(
                participant_id=participant_id,
                display_name=display_name or participant_id,
                tracker=PresenceTracker(
                    absent_grace_s=self.config.absent_grace_s,
                    present_grace_s=self.config.present_grace_s,
                ),
            )
            self.participants[participant_id] = p
        elif display_name:
            p.display_name = display_name
        return p

    def observe(
        self,
        present_ids: List[str],
        now: float,
        *,
        auto_enroll: bool = True,
    ) -> List[SessionEvent]:
        """Update every enrolled participant from the set seen this frame.

        ``present_ids`` is who the recognition layer matched this frame (e.g. via
        the consented face gallery). Enrolled-but-unseen participants get an
        ``absent`` signal, which is how a group class detects someone leaving.
        """
        seen = set(present_ids)
        if auto_enroll:
            for pid in seen:
                self.enroll(pid)
        events: List[SessionEvent] = []
        for pid, p in self.participants.items():
            snap = p.tracker.update(pid in seen, now)
            if snap.event is not None:
                events.append(
                    SessionEvent(
                        participant_id=pid,
                        event=snap.event,
                        at=now,
                        state=snap.state,
                    )
                )
        return events

    def headcount(self) -> int:
        return sum(1 for p in self.participants.values() if p.tracker.is_present)

    def present_ids(self) -> List[str]:
        return [
            pid for pid, p in self.participants.items() if p.tracker.is_present
        ]

    def absent_ids(self) -> List[str]:
        return [
            pid for pid, p in self.participants.items() if p.tracker.is_absent
        ]

    def status(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": ClassMode.GROUP.value,
            "teaching_mode": self.teaching_mode.value,
            "headcount": self.headcount(),
            "present_ids": self.present_ids(),
            "absent_ids": self.absent_ids(),
            "roster": [
                {
                    "participant_id": p.participant_id,
                    "display_name": p.display_name,
                    "state": p.tracker.state.value,
                    "present_seconds_total": round(
                        p.tracker.present_seconds_total, 3
                    ),
                    "away_seconds_total": round(p.tracker.away_seconds_total, 3),
                }
                for p in self.participants.values()
            ],
        }
