"""Teaching conductor: presence/engagement -> teaching action -> natural speech.

The conductor is the small brain that decides what should happen when the room
changes, then asks the xAI voice agent to phrase it. It supports both teaching
modes:

- Theodore (AI teaching): the agent leads, so it actively pauses on absence,
  welcomes learners back, and nudges when attention drops.
- Self-teaching: the learner drives, so the agent is quieter -- it still pauses
  media on absence and greets a return, and it answers when spoken to.

It is deliberately provider-agnostic: it emits a :class:`TeachingAction` (what to
do + the words to say) that a UI or the media player acts on (pause/resume/speak).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .presence import PresenceEvent
from .session import ClassMode, SessionEvent, TeachingMode
from .voice_agent import ClassroomContext, VoiceReply, XAIVoiceAgent


class ActionKind(str, Enum):
    SPEAK = "speak"                 # just say something
    PAUSE = "pause"                 # pause lesson/media (learner absent)
    RESUME = "resume"              # resume + recap (learner returned)
    GREET = "greet"                # welcome on arrival
    NUDGE_ATTENTION = "nudge"      # attention dropped -> re-engage
    ANSWER = "answer"              # respond to a learner message
    NONE = "none"                  # nothing to do this frame


@dataclass
class TeachingAction:
    kind: ActionKind
    reply: Optional[VoiceReply]
    reason: str
    participant_id: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "reason": self.reason,
            "participant_id": self.participant_id,
            "reply": self.reply.as_dict() if self.reply else None,
        }


# Below this smoothed attention we nudge (only in Theodore mode).
ATTENTION_NUDGE_THRESHOLD = 0.35


class TeachingConductor:
    def __init__(
        self,
        agent: XAIVoiceAgent,
        *,
        class_mode: ClassMode,
        teaching_mode: TeachingMode,
        topic: str = "",
    ) -> None:
        self._agent = agent
        self._class_mode = class_mode
        self._teaching_mode = teaching_mode
        self._topic = topic
        self._nudged = False

    def _ctx(self, event: str, **kw) -> ClassroomContext:
        return ClassroomContext(
            class_mode=self._class_mode.value,
            teaching_mode=self._teaching_mode.value,
            event=event,
            topic=self._topic,
            **kw,
        )

    def on_presence_event(
        self, ev: SessionEvent, *, learner_name: str = "", away_seconds: float = 0.0,
        headcount: int = 0,
    ) -> TeachingAction:
        """Map a presence transition to a teaching action with spoken words."""
        if ev.event is PresenceEvent.ARRIVED:
            ctx = self._ctx("arrived", learner_name=learner_name, headcount=headcount)
            return TeachingAction(
                ActionKind.GREET, self._agent.respond(ctx),
                reason="learner arrived", participant_id=ev.participant_id,
            )
        if ev.event is PresenceEvent.LEFT:
            self._nudged = False
            ctx = self._ctx(
                "left", learner_name=learner_name, away_seconds=away_seconds,
                headcount=headcount,
            )
            # In a solo class, an absence pauses the lesson. In a group class,
            # Theodore holds the key point but keeps the room going.
            kind = (
                ActionKind.PAUSE
                if self._class_mode is ClassMode.SOLO
                else ActionKind.SPEAK
            )
            return TeachingAction(
                kind, self._agent.respond(ctx),
                reason="learner absent", participant_id=ev.participant_id,
            )
        if ev.event is PresenceEvent.RETURNED:
            ctx = self._ctx(
                "returned", learner_name=learner_name, headcount=headcount,
            )
            return TeachingAction(
                ActionKind.RESUME, self._agent.respond(ctx),
                reason="learner returned", participant_id=ev.participant_id,
            )
        return TeachingAction(ActionKind.NONE, None, reason="no transition")

    def on_attention(self, attention: float, *, learner_name: str = "") -> TeachingAction:
        """Nudge when a present learner's attention drops (Theodore mode only)."""
        if self._teaching_mode is not TeachingMode.THEODORE:
            return TeachingAction(ActionKind.NONE, None, reason="self-teaching: no nudge")
        if attention >= ATTENTION_NUDGE_THRESHOLD:
            self._nudged = False
            return TeachingAction(ActionKind.NONE, None, reason="attention ok")
        if self._nudged:
            return TeachingAction(ActionKind.NONE, None, reason="already nudged")
        self._nudged = True
        ctx = self._ctx("attention_low", learner_name=learner_name)
        return TeachingAction(
            ActionKind.NUDGE_ATTENTION, self._agent.respond(ctx),
            reason="attention low",
        )

    def answer(self, user_message: str, *, learner_name: str = "") -> TeachingAction:
        """Respond to something the learner said (natural conversation)."""
        ctx = self._ctx("question", learner_name=learner_name)
        return TeachingAction(
            ActionKind.ANSWER,
            self._agent.respond(ctx, user_message=user_message),
            reason="learner message",
        )

    def handle_events(
        self, events: List[SessionEvent], *, away_lookup=None, name_lookup=None,
        headcount: int = 0,
    ) -> List[TeachingAction]:
        """Convenience: map a batch of session events to actions (group classes)."""
        actions: List[TeachingAction] = []
        for ev in events:
            away = away_lookup(ev.participant_id) if away_lookup else 0.0
            name = name_lookup(ev.participant_id) if name_lookup else ""
            actions.append(
                self.on_presence_event(
                    ev, learner_name=name, away_seconds=away, headcount=headcount,
                )
            )
        return actions
