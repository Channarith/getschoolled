"""Teaching session harness: solo/group × Theodore/self-teach + presence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .presence import PresenceReport, PresenceTracker
from .prompts import instructions_for, presence_nudge
from .xai_voice import OfflineVoiceAgent, VoiceAgent, build_voice_agent


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class TeachingMode(str, Enum):
    THEODORE = "theodore"
    SELF_TEACH = "self_teach"


@dataclass
class ParticipantSeat:
    participant_id: str
    name: str
    tracker: PresenceTracker
    last_report: Optional[PresenceReport] = None
    required: bool = True


@dataclass
class TeachingSession:
    """In-memory lab session for webcam presence + voice teaching."""

    class_mode: ClassMode
    teaching_mode: TeachingMode
    topic: str = "general study"
    seats: Dict[str, ParticipantSeat] = field(default_factory=dict)
    voice: VoiceAgent = field(default_factory=OfflineVoiceAgent)
    events: List[Dict[str, Any]] = field(default_factory=list)
    hold_active: bool = False
    hold_reason: str = ""
    hold_participant_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        class_mode: str = "solo",
        teaching_mode: str = "theodore",
        topic: str = "general study",
        voice: Optional[VoiceAgent] = None,
        max_faces_allowed: int = 1,
        require_liveness: bool = True,
        use_xai: bool = False,
    ) -> "TeachingSession":
        cm = ClassMode(class_mode.lower())
        tm = TeachingMode.SELF_TEACH if teaching_mode.lower() in ("self", "self_teach", "self-teach") else TeachingMode.THEODORE
        agent = voice or build_voice_agent(
            use_xai=use_xai,
            instructions=instructions_for(tm.value, cm.value),
        )
        return cls(class_mode=cm, teaching_mode=tm, topic=topic, voice=agent)

    @property
    def system_instructions(self) -> str:
        return instructions_for(self.teaching_mode.value, self.class_mode.value)

    def add_participant(
        self,
        participant_id: str,
        name: str,
        *,
        required: bool = True,
        max_faces_allowed: int = 1,
        require_liveness: bool = True,
    ) -> ParticipantSeat:
        if self.class_mode == ClassMode.SOLO and self.seats and participant_id not in self.seats:
            raise ValueError("solo class allows only one learner seat")
        seat = ParticipantSeat(
            participant_id=participant_id,
            name=name,
            tracker=PresenceTracker(
                max_faces_allowed=max_faces_allowed,
                require_liveness=require_liveness,
            ),
            required=required,
        )
        self.seats[participant_id] = seat
        return seat

    def report_presence(
        self,
        participant_id: str,
        *,
        face_count: int,
        silhouette_count: int = 0,
        attention: float = 0.8,
        gaze_frontal: float = 0.8,
    ) -> PresenceReport:
        seat = self.seats[participant_id]
        report = seat.tracker.observe_counts(
            face_count=face_count,
            silhouette_count=silhouette_count,
            attention=attention,
            gaze_frontal=gaze_frontal,
            participant_id=participant_id,
        )
        seat.last_report = report
        self._apply_hold(seat, report)
        nudge = presence_nudge(report.reason, learner_name=seat.name)
        self.events.append(
            {
                "type": "presence",
                "participant_id": participant_id,
                "report": report.as_dict(),
                "nudge": nudge,
                "hold_active": self.hold_active,
            }
        )
        return report

    def _apply_hold(self, seat: ParticipantSeat, report: PresenceReport) -> None:
        if not seat.required:
            return
        if report.hold_recommended:
            self.hold_active = True
            self.hold_reason = report.reason
            self.hold_participant_id = seat.participant_id
            return
        # Clear hold only when the held participant recovers (or no hold).
        if self.hold_active and self.hold_participant_id == seat.participant_id:
            self.hold_active = False
            self.hold_reason = ""
            self.hold_participant_id = ""

    def should_pause_teaching(self) -> bool:
        return bool(self.hold_active)

    async def say(self, text: str) -> Dict[str, Any]:
        """Ask the voice agent to speak (Theodore or self-teach coach)."""
        if self.hold_active and self.teaching_mode == TeachingMode.THEODORE:
            # Theodore still may speak a presence nudge, but not lesson content.
            pass
        result = await self.voice.speak_text(text)
        self.events.append({"type": "voice", "text": text, "result": result})
        return result

    async def handle_presence_voice(self, participant_id: str) -> Optional[str]:
        """Optionally speak a nudge for the latest presence event."""
        seat = self.seats.get(participant_id)
        if not seat or not seat.last_report:
            return None
        line = presence_nudge(seat.last_report.reason, learner_name=seat.name)
        if not line:
            return None
        await self.say(line)
        return line

    def snapshot(self) -> Dict[str, Any]:
        return {
            "class_mode": self.class_mode.value,
            "teaching_mode": self.teaching_mode.value,
            "topic": self.topic,
            "hold_active": self.hold_active,
            "hold_reason": self.hold_reason,
            "hold_participant_id": self.hold_participant_id,
            "instructions": self.system_instructions,
            "participants": [
                {
                    "participant_id": s.participant_id,
                    "name": s.name,
                    "required": s.required,
                    "last_report": s.last_report.as_dict() if s.last_report else None,
                }
                for s in self.seats.values()
            ],
            "voice_backend": getattr(self.voice, "backend_name", type(self.voice).__name__),
        }
