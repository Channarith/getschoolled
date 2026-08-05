"""Webcam teaching session: monitor + policy + voice, for solo and group classes.

This is the harness the feature is built and tested against. A session owns:

- a :class:`WebcamMonitor` (face + silhouette analysis per participant),
- a teaching policy (:class:`TheodoreTeachingPolicy` for AI-led classes or
  :class:`SelfTeachingPolicy` for self-paced study),
- an optional :class:`XAIVoiceAgent` for natural spoken responses.

Callers (the orchestrator's solo loop, or the live-room hub for group
classes) push webcam frames in via :meth:`WebcamTeachingSession.ingest_frame`
and get a :class:`SessionUpdate` back: the presence transitions and the
teaching actions to render (pause the deck, speak a line through the voice
agent or the platform TTS fallback, log a stat). Frames are analyzed and
discarded — nothing is persisted here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .modes import (
    ACTION_SAY,
    SelfTeachingPolicy,
    TeachingAction,
    TheodoreTeachingPolicy,
)
from .monitor import FrameAnalysis, WebcamMonitor
from .presence import PresenceEvent
from .xai_voice import XAIVoiceAgent

MODE_THEODORE = "theodore"   # AI-led (Theodore teaches; solo 1:1 or group)
MODE_SELF = "self"           # user self-teaching (study companion)


@dataclass
class SessionUpdate:
    """Everything that happened as a result of one ingested frame."""

    analysis: FrameAnalysis
    events: List[PresenceEvent] = field(default_factory=list)
    actions: List[TeachingAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "participant_id": self.analysis.participant_id,
            "state": self.analysis.state.value,
            "events": [e.to_dict() for e in self.events],
            "actions": [a.to_dict() for a in self.actions],
        }


class WebcamTeachingSession:
    """One webcam-monitored teaching session (solo or group)."""

    def __init__(
        self,
        *,
        mode: str,
        monitor: WebcamMonitor,
        policy,
        voice: Optional[XAIVoiceAgent] = None,
        participant_names: Optional[Dict[str, str]] = None,
    ) -> None:
        if mode not in (MODE_THEODORE, MODE_SELF):
            raise ValueError(f"unknown mode {mode!r}")
        self.mode = mode
        self.monitor = monitor
        self.policy = policy
        self.voice = voice
        self.participant_names = dict(participant_names or {})

    # --- constructors ------------------------------------------------------ #
    @classmethod
    def solo_theodore(
        cls,
        learner_id: str = "local",
        *,
        monitor: Optional[WebcamMonitor] = None,
        voice: Optional[XAIVoiceAgent] = None,
        learner_name: str = "",
        **policy_kwargs,
    ) -> "WebcamTeachingSession":
        """Solo 1:1 class taught by Theodore (the AI host)."""
        return cls(
            mode=MODE_THEODORE,
            monitor=monitor or WebcamMonitor(),
            policy=TheodoreTeachingPolicy(**policy_kwargs),
            voice=voice,
            participant_names={learner_id: learner_name} if learner_name else {},
        )

    @classmethod
    def group_theodore(
        cls,
        learner_ids,
        *,
        monitor: Optional[WebcamMonitor] = None,
        voice: Optional[XAIVoiceAgent] = None,
        participant_names: Optional[Dict[str, str]] = None,
        **policy_kwargs,
    ) -> "WebcamTeachingSession":
        """Group live room taught by Theodore (up to the room's seat count)."""
        session = cls(
            mode=MODE_THEODORE,
            monitor=monitor or WebcamMonitor(),
            policy=TheodoreTeachingPolicy(**policy_kwargs),
            voice=voice,
            participant_names=participant_names,
        )
        # Pre-register seats so an empty room is observable from t=0.
        for pid in learner_ids:
            session.monitor.presence.tracker(pid)
        return session

    @classmethod
    def self_teaching(
        cls,
        learner_id: str = "local",
        *,
        monitor: Optional[WebcamMonitor] = None,
        voice: Optional[XAIVoiceAgent] = None,
        **policy_kwargs,
    ) -> "WebcamTeachingSession":
        """User self-teaching: no narrator; focus tracking + recap offers."""
        return cls(
            mode=MODE_SELF,
            monitor=monitor or WebcamMonitor(),
            policy=SelfTeachingPolicy(**policy_kwargs),
            voice=voice,
        )

    # --- frame intake ------------------------------------------------------ #
    def ingest_frame(
        self,
        participant_id: str,
        image: object,
        *,
        at: Optional[float] = None,
    ) -> SessionUpdate:
        """Analyze one participant's webcam frame and react to it."""
        now = time.time() if at is None else float(at)
        analysis = self.monitor.analyze_frame(participant_id, image, at=now)
        actions: List[TeachingAction] = []
        for event in analysis.events:
            if isinstance(self.policy, TheodoreTeachingPolicy):
                actions.extend(
                    self.policy.on_event(
                        event, participant_names=self.participant_names
                    )
                )
            else:
                actions.extend(self.policy.on_event(event))
        return SessionUpdate(analysis=analysis, events=analysis.events, actions=actions)

    def tick(self, *, at: Optional[float] = None) -> List[TeachingAction]:
        """Periodic housekeeping (silhouette nudges, focus-time accrual)."""
        now = time.time() if at is None else float(at)
        return self.policy.tick(now=now)

    # --- voice ------------------------------------------------------------- #
    def voice_available(self) -> bool:
        """True when the xAI voice agent can speak (else use platform TTS)."""
        return self.voice is not None and self.voice.configured()

    def spoken_lines(self, update: SessionUpdate) -> List[str]:
        """The lines to voice from an update, in order (voice agent or TTS)."""
        return [a.text for a in update.actions if a.kind == ACTION_SAY and a.text]

    # --- state ------------------------------------------------------------- #
    def presence_snapshot(self) -> dict:
        return self.monitor.snapshot()

    def stats(self, *, at: Optional[float] = None) -> dict:
        """Session stats (self-teaching accrues focus/away; Theodore reports
        pause state + per-participant presence)."""
        if isinstance(self.policy, SelfTeachingPolicy):
            return self.policy.stats(now=time.time() if at is None else at)
        return {
            "mode": self.mode,
            "paused": self.policy.paused,
            "presence": self.presence_snapshot(),
        }
