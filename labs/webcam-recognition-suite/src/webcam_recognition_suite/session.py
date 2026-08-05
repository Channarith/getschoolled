"""Solo / group class session model for the webcam lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .presence import AbsencePolicy, PresenceFusion, PresenceVerdict
from .recognition import ClassRecognitionFrame, recognize_frame
from .teaching import TeachingMode, TeachingTurn, plan_teaching_turn


class RoomSize(int, Enum):
    SOLO = 2
    SMALL = 4
    MEDIUM = 6
    LARGE = 9


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


@dataclass
class SeatState:
    seat_id: str
    learner_name: str
    fusion: PresenceFusion = field(default_factory=PresenceFusion)
    last_verdict: Optional[PresenceVerdict] = None
    last_frame: Optional[ClassRecognitionFrame] = None

    def to_dict(self) -> dict:
        return {
            "seat_id": self.seat_id,
            "learner_name": self.learner_name,
            "last_verdict": None if self.last_verdict is None else self.last_verdict.to_dict(),
            "last_frame": None if self.last_frame is None else self.last_frame.to_dict(),
        }


@dataclass
class ClassSession:
    """In-memory solo or group class for webcam recognition experiments."""

    room_id: str
    class_mode: ClassMode
    room_size: RoomSize
    teaching_mode: TeachingMode
    slide_title: str = "Introduction"
    seats: Dict[str, SeatState] = field(default_factory=dict)
    turns: List[TeachingTurn] = field(default_factory=list)
    presence_hold: bool = False
    policy: AbsencePolicy = field(default_factory=AbsencePolicy)
    clock: float = 0.0

    @classmethod
    def open(
        cls,
        *,
        room_id: str = "lab-room",
        class_mode: ClassMode = ClassMode.SOLO,
        room_size: RoomSize = RoomSize.SOLO,
        teaching_mode: TeachingMode = TeachingMode.THEODORE_TEACH,
        learner_names: Optional[List[str]] = None,
        policy: Optional[AbsencePolicy] = None,
    ) -> "ClassSession":
        if class_mode is ClassMode.SOLO:
            room_size = RoomSize.SOLO
        learner_slots = max(1, int(room_size) - 1)  # minus Theodore / host seat
        names = list(learner_names or [])
        while len(names) < learner_slots:
            names.append(f"Learner-{len(names) + 1}")
        names = names[:learner_slots]
        policy = policy or AbsencePolicy()
        seats = {
            f"seat-{i + 1}": SeatState(
                seat_id=f"seat-{i + 1}",
                learner_name=names[i],
                fusion=PresenceFusion(policy=policy),
            )
            for i in range(learner_slots)
        }
        return cls(
            room_id=room_id,
            class_mode=class_mode,
            room_size=room_size,
            teaching_mode=teaching_mode,
            seats=seats,
            policy=policy,
        )

    def tick(
        self,
        seat_id: str,
        frame,
        *,
        dt: float = 1.0,
        learner_question: str = "",
    ) -> dict:
        """Ingest one webcam frame for a seat and plan the teaching response."""
        self.clock = round(self.clock + float(dt), 3)
        seat = self.seats.get(seat_id)
        if seat is None:
            raise KeyError(f"unknown seat {seat_id!r}")
        framed = recognize_frame(frame, seat_id=seat_id)
        verdict = seat.fusion.observe(
            face_count=framed.face_count,
            body_present=framed.silhouettes.body_present,
            silhouette_count=framed.silhouettes.person_count,
            silhouette_confidence=framed.silhouettes.confidence,
            now=self.clock,
        )
        seat.last_frame = framed
        seat.last_verdict = verdict
        if verdict.hold_recommended:
            self.presence_hold = True
        elif verdict.present and self.presence_hold:
            # Clear hold when the held learner returns (lab: any return clears).
            self.presence_hold = False

        turn = plan_teaching_turn(
            mode=self.teaching_mode,
            slide_title=self.slide_title,
            presence=verdict,
            learner_question=learner_question,
            human_host_name="Host",
        )
        self.turns.append(turn)
        return {
            "clock": self.clock,
            "seat": seat.to_dict(),
            "turn": turn.to_dict(),
            "presence_hold": self.presence_hold,
        }

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "class_mode": self.class_mode.value,
            "room_size": int(self.room_size),
            "teaching_mode": self.teaching_mode.value,
            "slide_title": self.slide_title,
            "presence_hold": self.presence_hold,
            "policy": self.policy.to_dict(),
            "seats": {k: v.to_dict() for k, v in self.seats.items()},
            "turns": [t.to_dict() for t in self.turns],
            "clock": self.clock,
        }
