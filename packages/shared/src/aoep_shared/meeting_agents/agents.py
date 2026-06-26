"""Specialized agents for a live video teaching session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from aoep_shared.dialect import get_dialect, humanize_narration, tutor_tone_hint
from aoep_shared.slang import default_lexicon

from .simulation import AgentEvent, InboundChat, VideoFrameEvent


class AgentRole(str, Enum):
    TEACHER = "teacher"
    CHAT_TUTOR = "chat_tutor"
    PERCEPTION = "perception"
    INTERRUPT_HOST = "interrupt_host"
    MODERATOR = "moderator"


class _LessonState(str, Enum):
    TEACHING = "teaching"
    ANSWERING = "answering"
    QUIZZING = "quizzing"
    REENGAGING = "reengaging"
    DONE = "done"


def _decide_next(
    *,
    slide_index: int,
    slides_total: int,
    pending_questions: int,
    attention: float,
    quiz_every: int = 4,
    attention_floor: float = 0.5,
) -> _LessonState:
    if slide_index >= slides_total and pending_questions == 0:
        return _LessonState.DONE
    if pending_questions > 0:
        return _LessonState.ANSWERING
    if attention < attention_floor:
        return _LessonState.REENGAGING
    return _LessonState.TEACHING


@dataclass
class SharedSessionState:
    """Blackboard all agents read/write during a lab tick."""

    slide_index: int = 0
    slides_total: int = 5
    pending_questions: List[str] = field(default_factory=list)
    attention: float = 0.85
    hands_raised: int = 0
    teaching_paused: bool = False
    dialect: str = "us_general"
    language: str = "en"
    subject: str = "general"
    lesson_snippet: str = ""
    chat_answered: List[str] = field(default_factory=list)
    events: List[AgentEvent] = field(default_factory=list)


def _log(state: SharedSessionState, agent: AgentRole, kind: str, detail: str, **meta) -> None:
    state.events.append(AgentEvent(agent=agent.value, kind=kind, detail=detail, meta=meta))


@dataclass
class TeacherAgent:
    """Narrates slides when the Director is in TEACHING mode."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if state.teaching_paused or state.pending_questions:
            return None
        lesson_state = _decide_next(
            slide_index=state.slide_index,
            slides_total=state.slides_total,
            pending_questions=len(state.pending_questions),
            attention=state.attention,
        )
        if lesson_state is not _LessonState.TEACHING:
            return None
        line = state.lesson_snippet or f"Slide {state.slide_index + 1} of {state.slides_total}."
        spoken = humanize_narration(line, state.dialect, language=state.language)
        _log(state, AgentRole.TEACHER, "narrate", spoken, slide=state.slide_index)
        return spoken


@dataclass
class ChatTutorAgent:
    """Reads meeting chat and posts answers without interrupting the slide deck."""

    lexicon: object = field(default_factory=default_lexicon)

    def on_chat(self, state: SharedSessionState, msg: InboundChat) -> Optional[str]:
        prof = get_dialect(state.dialect, language=state.language)
        norm = self.lexicon.normalize(msg.text, language=state.language, region=prof.region)
        gloss = "; ".join(norm.glossed) if norm.glossed else ""
        q = norm.plain
        answer = self._answer(q, state, via="chat")
        if gloss:
            answer = f"{answer} (got your slang: {gloss})"
        state.chat_answered.append(q)
        _log(state, AgentRole.CHAT_TUTOR, "chat_reply", answer, question=q, author=msg.author)
        return answer

    def _answer(self, question: str, state: SharedSessionState, *, via: str) -> str:
        tone = tutor_tone_hint(state.dialect, language=state.language)
        base = (
            f"On {state.subject}: {question} — here's the short version from today's lesson. "
            f"{state.lesson_snippet[:120]}..."
            if state.lesson_snippet else
            f"Good question about {state.subject}. Let me break it down simply."
        )
        reply = humanize_narration(base, state.dialect, language=state.language)
        _log(state, AgentRole.CHAT_TUTOR, "grounded", reply, tone=tone, via=via)
        return reply


@dataclass
class PerceptionAgent:
    """Observes synthetic video frames and updates attention / hand-raise signals."""

    def on_video(self, state: SharedSessionState, frame: VideoFrameEvent) -> None:
        state.attention = max(0.0, min(1.0, frame.attention))
        if frame.hand_raised:
            state.hands_raised += 1
            state.pending_questions.append(f"[hand raise] {frame.student_id}")
        _log(
            state, AgentRole.PERCEPTION, "observe",
            f"attention={frame.attention:.2f} hand={frame.hand_raised}",
            student=frame.student_id,
        )


@dataclass
class InterruptHostAgent:
    """Pauses teaching and answers spoken/live questions (voice or urgent chat)."""

    def tick(self, state: SharedSessionState, chat_tutor: ChatTutorAgent) -> Optional[str]:
        if not state.pending_questions:
            state.teaching_paused = False
            return None
        state.teaching_paused = True
        lesson_state = _decide_next(
            slide_index=state.slide_index,
            slides_total=state.slides_total,
            pending_questions=len(state.pending_questions),
            attention=state.attention,
        )
        if lesson_state is not _LessonState.ANSWERING:
            return None
        question = state.pending_questions.pop(0)
        answer = chat_tutor._answer(question, state, via="interrupt")
        spoken = humanize_narration(
            f"Hold up — great question. {answer}",
            state.dialect, language=state.language,
        )
        _log(state, AgentRole.INTERRUPT_HOST, "interrupt_answer", spoken, question=question)
        if not state.pending_questions:
            state.teaching_paused = False
        return spoken


@dataclass
class ModeratorAgent:
    """Disclosure, pacing nudges, and re-engage when attention drops."""

    attention_floor: float = 0.45

    def tick(self, state: SharedSessionState) -> Optional[str]:
        lesson_state = _decide_next(
            slide_index=state.slide_index,
            slides_total=state.slides_total,
            pending_questions=len(state.pending_questions),
            attention=state.attention,
            attention_floor=self.attention_floor,
        )
        if lesson_state is _LessonState.REENGAGING and state.attention < self.attention_floor:
            line = humanize_narration(
                "Hey — checking in. Still with me? Give me a thumbs up or drop a question in chat.",
                state.dialect, language=state.language,
            )
            _log(state, AgentRole.MODERATOR, "reengage", line, attention=state.attention)
            state.attention = min(1.0, state.attention + 0.15)
            return line
        return None
