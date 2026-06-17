"""The teaching brain: a provider-driven loop over the Director state machine.

This is the platform-agnostic core. It owns no media plumbing; it consumes
perception/speech signals and emits teaching actions. The LiveKit worker (and,
later, the Zoom/Teams/Meet bridges) feed it ticks and render its actions.
"""

from __future__ import annotations

from dataclasses import dataclass

from aoep_shared.factory import ProviderFactory, build_factory
from orchestrator.director import ClassContext, Director, LessonState


@dataclass
class Action:
    """A teaching action the runtime should render into the room."""

    kind: str  # "narrate" | "answer" | "quiz" | "reengage" | "end"
    state: LessonState
    detail: str = ""


_STATE_TO_KIND = {
    LessonState.TEACHING: "narrate",
    LessonState.ANSWERING: "answer",
    LessonState.QUIZZING: "quiz",
    LessonState.REENGAGING: "reengage",
    LessonState.DONE: "end",
}


class TeachingBrain:
    def __init__(self, factory: ProviderFactory | None = None) -> None:
        self._factory = factory or build_factory()
        self._director = Director()

    @property
    def factory(self) -> ProviderFactory:
        return self._factory

    def step(self, ctx: ClassContext) -> Action:
        """Advance one tick and return the action to render."""
        state = self._director.decide(ctx)
        detail = {
            LessonState.TEACHING: "narrate current slide via TTS",
            LessonState.ANSWERING: "answer pending question via RAG tutor",
            LessonState.QUIZZING: "issue a pop quiz / key-point check",
            LessonState.REENGAGING: "re-engage low-attention students",
            LessonState.DONE: "wrap up and summarize the lesson",
        }[state]
        return Action(kind=_STATE_TO_KIND[state], state=state, detail=detail)
