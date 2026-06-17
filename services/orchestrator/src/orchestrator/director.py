"""Teaching Director: the lesson state machine.

The Director balances teaching vs answering vs quizzing vs re-engaging. In the
full system this is a LangGraph stateful graph driving the LiveKit agent; here it
is a dependency-free state machine that encodes the same policy and is fully
unit-testable. The agent-runtime worker drives it tick-by-tick.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aoep_shared.schemas import ClassType


class LessonState(str, Enum):
    TEACHING = "teaching"
    ANSWERING = "answering"
    QUIZZING = "quizzing"
    REENGAGING = "reengaging"
    DONE = "done"


@dataclass
class ClassContext:
    """Live signals the Director reacts to on each tick."""

    class_type: ClassType = ClassType.GROUP
    slides_total: int = 1
    slide_index: int = 0
    pending_questions: int = 0
    # Mean attention across recognized students, 0..1 (from Perception Agent).
    attention: float = 1.0
    slides_since_quiz: int = 0


@dataclass
class Director:
    """Decides the next teaching action from the current context."""

    state: LessonState = LessonState.TEACHING
    # Solo classes quiz more aggressively for tighter personalization.
    quiz_every_n_slides: int = 4
    reengage_attention_threshold: float = 0.5
    history: list[LessonState] = field(default_factory=list)

    def _quiz_cadence(self, ctx: ClassContext) -> int:
        return 2 if ctx.class_type is ClassType.SOLO else self.quiz_every_n_slides

    def decide(self, ctx: ClassContext) -> LessonState:
        """Return the next state, highest-priority concern first."""
        if ctx.slide_index >= ctx.slides_total and ctx.pending_questions == 0:
            nxt = LessonState.DONE
        elif ctx.pending_questions > 0:
            # Always clear questions before moving on.
            nxt = LessonState.ANSWERING
        elif ctx.attention < self.reengage_attention_threshold:
            nxt = LessonState.REENGAGING
        elif ctx.slides_since_quiz >= self._quiz_cadence(ctx):
            nxt = LessonState.QUIZZING
        else:
            nxt = LessonState.TEACHING
        self.state = nxt
        self.history.append(nxt)
        return nxt
