"""Class sessions: one silhouette pipeline per participant camera.

A solo session has a single learner teaching themselves with Theodore; a group
session has a roster, an attendance quorum, and a class-wide hold. Both share
the same per-camera pipeline (detector -> presence tracker -> cue policy) so
behaviour is identical and only the policy differs.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from .config import LabConfig, load_config
from .cues import ClassMode, Cue, CueAction, CuePolicy
from .presence import PresenceEvent, PresenceTracker
from .silhouette import SilhouetteDetector, SilhouetteObservation


class SessionNotFound(KeyError):
    pass


class ParticipantNotFound(KeyError):
    pass


@dataclass
class Participant:
    participant_id: str
    display_name: str
    role: str = "learner"
    detector: SilhouetteDetector = field(repr=False, default=None)  # type: ignore[assignment]
    tracker: PresenceTracker = field(repr=False, default=None)  # type: ignore[assignment]

    def as_dict(self, now: Optional[float] = None) -> dict:
        return {
            "participant_id": self.participant_id,
            "display_name": self.display_name,
            "role": self.role,
            "presence": self.tracker.snapshot(now).as_dict(),
        }


@dataclass
class ObservationResult:
    participant_id: str
    observation: SilhouetteObservation
    events: List[PresenceEvent]
    cues: List[Cue]
    lesson_paused: bool
    class_held: bool
    presence: dict

    def as_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "observation": self.observation.as_dict(),
            "presence": self.presence,
            "events": [e.as_dict() for e in self.events],
            "cues": [c.as_dict() for c in self.cues],
            "lesson_paused": self.lesson_paused,
            "class_held": self.class_held,
        }


class ClassSession:
    """One live class (solo or group) being watched through webcams."""

    def __init__(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        config: LabConfig,
        class_id: str = "",
        lesson_id: str = "",
        lesson_title: str = "",
        checkpoint: str = "",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session_id = session_id
        self.mode = mode
        self.config = config
        self.class_id = class_id
        self.lesson_id = lesson_id
        self.lesson_title = lesson_title
        self.checkpoint = checkpoint
        self._clock = clock
        self.created_at = clock()
        self.participants: Dict[str, Participant] = {}
        self.lesson_paused = False
        self.class_held = False
        self.cue_log: List[dict] = []
        self.event_log: List[dict] = []
        self._policy = CuePolicy(
            recap_after_absence_seconds=config.classroom.recap_after_absence_seconds
        )

    # -- roster --------------------------------------------------------

    def add_participant(
        self, participant_id: str, display_name: str = "", role: str = "learner"
    ) -> Participant:
        existing = self.participants.get(participant_id)
        if existing is not None:
            return existing
        participant = Participant(
            participant_id=participant_id,
            display_name=display_name or participant_id,
            role=role,
            detector=SilhouetteDetector(self.config.silhouette),
            tracker=PresenceTracker(self.config.presence, clock=self._clock),
        )
        self.participants[participant_id] = participant
        return participant

    def participant(self, participant_id: str) -> Participant:
        try:
            return self.participants[participant_id]
        except KeyError as exc:
            raise ParticipantNotFound(participant_id) from exc

    def learners(self) -> List[Participant]:
        return [p for p in self.participants.values() if p.role == "learner"]

    def recalibrate(self, participant_id: Optional[str] = None) -> int:
        targets = (
            [self.participant(participant_id)]
            if participant_id
            else list(self.participants.values())
        )
        for participant in targets:
            participant.detector.reset()
        return len(targets)

    # -- observation ---------------------------------------------------

    def observe_frame(self, participant_id: str, frame: np.ndarray) -> ObservationResult:
        participant = self.participant(participant_id)
        observation = participant.detector.observe(frame)
        return self._apply(participant, observation)

    def observe_signals(
        self,
        participant_id: str,
        *,
        detected: bool,
        confidence: float = 0.0,
        count: int = 0,
        coverage: float = 0.0,
        calibrating: bool = False,
    ) -> ObservationResult:
        """Privacy path: the client already ran detection on-device."""

        participant = self.participant(participant_id)
        observation = SilhouetteObservation(
            calibrating=calibrating,
            silhouettes=[],
            coverage=coverage,
            motion=0.0,
            frame_size=(0, 0),
        )
        return self._apply(
            participant,
            observation,
            detected_override=detected,
            confidence_override=confidence,
            count_override=count,
        )

    def _apply(
        self,
        participant: Participant,
        observation: SilhouetteObservation,
        *,
        detected_override: Optional[bool] = None,
        confidence_override: Optional[float] = None,
        count_override: Optional[int] = None,
    ) -> ObservationResult:
        now = self._clock()
        detected = (
            observation.detected if detected_override is None else detected_override
        )
        confidence = (
            observation.confidence
            if confidence_override is None
            else confidence_override
        )
        count = observation.count if count_override is None else count_override

        events = participant.tracker.update(
            detected=detected,
            confidence=confidence,
            count=count,
            calibrating=observation.calibrating,
            now=now,
        )
        cues = self._cues_for(participant, events)
        cues.extend(self._quorum_cues())
        return ObservationResult(
            participant_id=participant.participant_id,
            observation=observation,
            events=events,
            cues=cues,
            lesson_paused=self.lesson_paused,
            class_held=self.class_held,
            presence=participant.tracker.snapshot(now).as_dict(),
        )

    def tick(self) -> List[Cue]:
        """Advance every tracker without new frames (grace/staleness expiry)."""

        cues: List[Cue] = []
        for participant in list(self.participants.values()):
            events = participant.tracker.tick()
            cues.extend(self._cues_for(participant, events))
        cues.extend(self._quorum_cues())
        return cues

    # -- policy --------------------------------------------------------

    def _cues_for(
        self, participant: Participant, events: List[PresenceEvent]
    ) -> List[Cue]:
        cues: List[Cue] = []
        for event in events:
            self.event_log.append(
                {"participant_id": participant.participant_id, **event.as_dict()}
            )
            for cue in self._policy.for_event(
                event,
                mode=self.mode,
                participant_id=participant.participant_id,
                display_name=participant.display_name,
                lesson_title=self.lesson_title,
                checkpoint=self.checkpoint,
            ):
                cues.append(cue)
        for cue in cues:
            self._apply_action(cue)
            self.cue_log.append(cue.as_dict())
        return cues

    def _apply_action(self, cue: Cue) -> None:
        if cue.action is CueAction.PAUSE_LESSON:
            if self.mode is ClassMode.SOLO and self.config.classroom.solo_pause_on_absence:
                self.lesson_paused = True
        elif cue.action in (CueAction.RESUME_LESSON, CueAction.RECAP):
            self.lesson_paused = False
        elif cue.action is CueAction.HOLD_CLASS:
            self.class_held = True
        elif cue.action is CueAction.RELEASE_HOLD:
            self.class_held = False

    def _quorum_cues(self) -> List[Cue]:
        if self.mode is not ClassMode.GROUP:
            return []
        learners = self.learners()
        if not learners:
            return []
        present = sum(1 for p in learners if p.tracker.snapshot().present)
        ratio = present / float(len(learners))
        should_hold = ratio < self.config.classroom.group_min_present_ratio
        if should_hold == self.class_held:
            return []
        cue = self._policy.for_quorum_change(
            held=should_hold,
            present=present,
            total=len(learners),
            lesson_title=self.lesson_title,
            checkpoint=self.checkpoint,
        )
        if cue is None:
            return []
        self._apply_action(cue)
        self.cue_log.append(cue.as_dict())
        return [cue]

    # -- reporting -----------------------------------------------------

    def attendance(self) -> dict:
        learners = self.learners()
        present = sum(1 for p in learners if p.tracker.snapshot().present)
        total = len(learners)
        return {
            "present": present,
            "total": total,
            "ratio": round(present / total, 4) if total else 0.0,
            "quorum": self.config.classroom.group_min_present_ratio,
            "held": self.class_held,
        }

    def state(self) -> dict:
        now = self._clock()
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "class_id": self.class_id,
            "lesson_id": self.lesson_id,
            "lesson_title": self.lesson_title,
            "checkpoint": self.checkpoint,
            "lesson_paused": self.lesson_paused,
            "class_held": self.class_held,
            "uptime_seconds": round(now - self.created_at, 2),
            "attendance": self.attendance(),
            "participants": [p.as_dict(now) for p in self.participants.values()],
        }

    def report(self) -> dict:
        rows = []
        for participant in self.participants.values():
            stats = participant.tracker.stats
            rows.append(
                {
                    "participant_id": participant.participant_id,
                    "display_name": participant.display_name,
                    "role": participant.role,
                    "state": participant.tracker.state.value,
                    "no_show": stats.first_seen_at is None,
                    **stats.as_dict(),
                }
            )
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "lesson_title": self.lesson_title,
            "attendance": self.attendance(),
            "participants": rows,
            "events": list(self.event_log),
            "cues": list(self.cue_log),
        }


class SessionRegistry:
    """In-memory session store. The lab keeps no database on purpose."""

    def __init__(
        self,
        config: Optional[LabConfig] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or load_config()
        self._clock = clock
        self._sessions: Dict[str, ClassSession] = {}

    def create(
        self,
        *,
        mode: ClassMode,
        class_id: str = "",
        lesson_id: str = "",
        lesson_title: str = "",
        checkpoint: str = "",
        session_id: str = "",
    ) -> ClassSession:
        sid = session_id or uuid.uuid4().hex[:12]
        session = ClassSession(
            session_id=sid,
            mode=mode,
            config=self.config,
            class_id=class_id,
            lesson_id=lesson_id,
            lesson_title=lesson_title,
            checkpoint=checkpoint,
            clock=self._clock,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> ClassSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFound(session_id) from exc

    def delete(self, session_id: str) -> dict:
        session = self.get(session_id)
        report = session.report()
        del self._sessions[session_id]
        return report

    def list(self) -> List[dict]:
        return [s.state() for s in self._sessions.values()]

    def tick_all(self) -> Dict[str, List[Cue]]:
        return {sid: s.tick() for sid, s in self._sessions.items()}
