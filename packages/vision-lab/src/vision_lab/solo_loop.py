"""Solo/self-teaching webcam recognition loop primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .presence import PresenceDecision, WebcamObservation, WebcamPresenceAnalyzer
from .xai_voice import (
    XAIVoiceAgent,
    build_presence_voice_messages,
)


@dataclass(frozen=True)
class SoloTeachingTurn:
    decision: PresenceDecision
    messages: list[dict[str, str]]
    speakable_chunks: list[str] = field(default_factory=list)

    def fallback_line(self) -> str:
        if self.decision.reason == "silhouette_without_face":
            return (
                "I can see you are there, but I cannot see your face clearly. "
                "Please adjust the camera or lighting, then we will continue."
            )
        if not self.decision.present:
            return "I do not see you right now. I will pause until you return."
        if not self.decision.verified_live:
            return "Checking in with you. Give me a quick thumbs up when you are ready."
        return "Great, you are with me. Let us keep going."


class SoloWebcamTeachingLoop:
    """Build Theodore voice turns from solo webcam observations."""

    def __init__(
        self,
        *,
        analyzer: WebcamPresenceAnalyzer | None = None,
        voice_agent: XAIVoiceAgent | None = None,
    ) -> None:
        self.analyzer = analyzer or WebcamPresenceAnalyzer()
        self.voice_agent = voice_agent

    def handle_observation(
        self,
        observation: WebcamObservation,
        *,
        lesson_context: str = "",
        learner_name: str = "learner",
    ) -> SoloTeachingTurn:
        decision = self.analyzer.analyze(observation)
        messages = build_presence_voice_messages(
            decision,
            lesson_context=lesson_context,
            learner_name=learner_name,
        )
        chunks: Iterable[str] = ()
        if self.voice_agent and self.voice_agent.configured:
            chunks = self.voice_agent.stream_speakable_chunks(messages)
        turn = SoloTeachingTurn(
            decision=decision,
            messages=messages,
            speakable_chunks=list(chunks),
        )
        if not turn.speakable_chunks:
            return SoloTeachingTurn(
                decision=decision,
                messages=messages,
                speakable_chunks=[turn.fallback_line()],
            )
        return turn
