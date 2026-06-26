"""Live-class teaching loop: sessions, slide delivery, and Tutor Q&A (RAG).

This is the web-facing teaching brain consumed by apps/web. Retrieval uses the
dependency-free RAG index over curriculum passages; answers come from the
configured LLMProvider, with a deterministic offline fallback (grounded in the
retrieved passages) so the live demo works without a running model server.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from aoep_shared.groundedness import guard_answer
from aoep_shared.providers.base import ChatMessage
from aoep_shared.rag import Document, RagIndex
from aoep_shared.slang import default_lexicon
from aoep_shared.dialect import humanize_narration, tutor_tone_hint
from pydantic import BaseModel, Field

from .curriculum import CurriculumStore, Lesson, Slide
from .director import Director
from .memory_client import MemoryClient
from .sessions import SessionStore, build_session_store


class ChatTurn(BaseModel):
    role: str  # "student" | "teacher"
    text: str


class SessionState(BaseModel):
    session_id: str
    class_type: str
    lesson_id: str
    current_slide: int = 0
    history: List[ChatTurn] = Field(default_factory=list)


class Answer(BaseModel):
    text: str
    citations: List[str] = Field(default_factory=list)
    language: str = "en"
    # Slang/idioms recognized in the question (e.g. "piece of cake = very easy").
    understood: List[str] = Field(default_factory=list)
    # Hallucination guard: whether the answer is grounded in the retrieved
    # context, the risk score, and any unsupported claims that were caught.
    grounded: bool = True
    hallucination_risk: float = 0.0
    unsupported: List[str] = Field(default_factory=list)
    # Human-in-the-loop (Phase 11): set when the answer is held/flagged for human
    # review before/after delivery.
    pending_review: bool = False
    review_id: Optional[str] = None
    # AI-agent reward: when the teacher decides to award points (e.g. for a
    # substantive, on-topic question), this carries a signed grant voucher the
    # learner's client redeems at identity /rewards/grant. {points, reason,
    # grant_token}. None when no reward is granted.
    reward: Optional[dict] = None


class SessionView(BaseModel):
    session: SessionState
    lesson: Lesson
    slide: Slide


class Reengagement(BaseModel):
    """A re-engagement beat: a short recap to pull a drifting learner back in."""

    text: str
    prompt: Optional[str] = None
    citations: List[str] = Field(default_factory=list)


@dataclass
class SessionCounters:
    """Per-session learning state the Director and memory loop accumulate.

    Kept off the Pydantic ``SessionState`` (which is serialized into responses)
    so the API shape is unchanged; lives in-process alongside the session.
    """

    student_id: Optional[str] = None
    slides_seen: int = 0
    slides_since_quiz: int = 0
    questions_asked: int = 0
    quiz_total: int = 0
    quiz_correct: int = 0
    last_attention: float = 1.0


def _offline_answer(question: str, context: List[str]) -> str:
    if context:
        snippet = " ".join(" ".join(context).split())[:400]
        return (
            f"Great question. Based on the lesson material: {snippet} "
            f"In short, this addresses '{question.strip()}'."
        )
    return (
        f"Let's think about '{question.strip()}'. I'll explain it using what we "
        f"covered in this lesson."
    )


class TeachingSessions:
    """Session manager for the live-class teaching loop.

    Session state is kept in a :class:`SessionStore` (in-memory by default, Redis
    when ``REDIS_URL`` is configured) so it is shared across orchestrator
    replicas - a follow-up ``advance``/``ask`` served by a different pod still
    finds the session instead of 404ing. The per-lesson RAG indexes are a
    deterministic, rebuildable cache and stay per-process.
    """

    def __init__(
        self,
        factory,
        curriculum: Optional[CurriculumStore] = None,
        memory_base_url: Optional[str] = None,
        store: Optional[SessionStore] = None,
    ) -> None:
        self.factory = factory
        self.curriculum = curriculum or CurriculumStore()
        self.llm = factory.llm()
        self.store = store or build_session_store(SessionState)
        self._indexes: Dict[str, RagIndex] = {}
        # Per-session Director + counters persist across slide/quiz/ask ticks so
        # adaptive decisions accumulate for the same learner during a class.
        self._directors: Dict[str, Director] = {}
        self._counters: Dict[str, SessionCounters] = {}
        # Best-effort memory client (neutral/no-op when MEMORY_URL is unset).
        self.memory = MemoryClient(memory_base_url)

    def _require(self, session_id: str) -> SessionState:
        session = self.store.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session  # type: ignore[return-value]

    def _index_for(self, lesson_id: str) -> RagIndex:
        if lesson_id not in self._indexes:
            index = RagIndex()
            for i, passage in enumerate(self.curriculum.passages_for(lesson_id)):
                title = passage.split(":", 1)[0] if ":" in passage else lesson_id
                index.add(Document.from_text(f"{lesson_id}-{i}", title, passage))
            self._indexes[lesson_id] = index
        return self._indexes[lesson_id]

    def list_lessons(self) -> List[Lesson]:
        return self.curriculum.list_lessons()

    def start_session(
        self, lesson_id: str, class_type: str, student_id: Optional[str] = None
    ) -> SessionState:
        if self.curriculum.get(lesson_id) is None:
            raise KeyError(lesson_id)
        session = SessionState(
            session_id=uuid.uuid4().hex[:12],
            class_type=class_type,
            lesson_id=lesson_id,
        )
        self.store.save(session)
        # One persistent Director + counters per session (the live loop's state).
        self._directors[session.session_id] = Director()
        self._counters[session.session_id] = SessionCounters(student_id=student_id)
        return session

    def get_session(self, session_id: str) -> SessionState:
        return self._require(session_id)

    def director_for(self, session_id: str) -> Director:
        """The persistent Director for this session (created on demand for
        sessions that predate Director wiring)."""
        if self.store.get(session_id) is None:
            raise KeyError(session_id)
        return self._directors.setdefault(session_id, Director())

    def counters_for(self, session_id: str) -> SessionCounters:
        if self.store.get(session_id) is None:
            raise KeyError(session_id)
        return self._counters.setdefault(session_id, SessionCounters())

    def lesson_for(self, session_id: str) -> Lesson:
        return self.curriculum.get(self._require(session_id).lesson_id)  # type: ignore[return-value]

    def current_slide(self, session_id: str) -> Slide:
        session = self._require(session_id)
        return self.lesson_for(session_id).slides[session.current_slide]

    def advance(self, session_id: str) -> Slide:
        session = self._require(session_id)
        lesson = self.curriculum.get(session.lesson_id)
        last = len(lesson.slides) - 1  # type: ignore[union-attr]
        session.current_slide = min(session.current_slide + 1, last)
        self.store.save(session)
        counters = self.counters_for(session_id)
        counters.slides_seen += 1
        counters.slides_since_quiz += 1
        if counters.student_id:
            # Behavior here is keyed by lesson_id; the quiz/grade loop keys by its
            # request topic, so callers must pass topic == lesson_id for the two
            # signal streams to merge for the same learner+topic.
            self.memory.record_behavior(
                counters.student_id, session.lesson_id, saw_slide=True
            )
        return self.current_slide(session_id)

    def ask(self, session_id: str, question: str, language: str = "en",
            dialect: str | None = None) -> Answer:
        session = self._require(session_id)
        tone = tutor_tone_hint(dialect, language=language)
        # Understand culture-specific slang/idioms before retrieval/answering, so
        # "it's a piece of cake" is treated as "very easy".
        norm = default_lexicon().normalize(question, language=language)
        retrieval_query = norm.plain
        retrieved = self._index_for(session.lesson_id).retrieve(retrieval_query, top_k=2)
        context = [r.document.text for r in retrieved]
        gloss = (
            f"\nSTUDENT_SLANG: {'; '.join(norm.glossed)}" if norm.detections else ""
        )
        prompt = (
            "You are a patient teacher. Answer the student's question using only "
            "the lesson context. If the student used slang/idioms, interpret them "
            "by their meaning. Speak in a natural, colloquial register: "
            f"{tone}\n"
            f"QUESTION: {question}{gloss}\nCONTEXT: {' '.join(context)}"
        )
        try:
            text = self.llm.complete(
                [
                    ChatMessage(role="system",
                                content=f"You are a helpful teacher. {tone}"),
                    ChatMessage(role="user", content=prompt),
                ]
            ).text
        except NotImplementedError:
            # No model server configured -> deterministic grounded fallback.
            text = humanize_narration(
                _offline_answer(question, context), dialect, language=language,
            )
        # Hallucination guard: only serve answers grounded in the retrieved
        # context; otherwise abstain/ground to avoid showing unsupported claims.
        safe_text, report = guard_answer(text, context, question=question)
        session.history.append(ChatTurn(role="student", text=question))
        session.history.append(ChatTurn(role="teacher", text=safe_text))
        self.store.save(session)
        counters = self.counters_for(session_id)
        counters.questions_asked += 1
        if counters.student_id:
            self.memory.record_behavior(
                counters.student_id, session.lesson_id, asked_question=True
            )
        return Answer(
            text=safe_text,
            citations=context,
            language=language,
            understood=norm.glossed,
            grounded=report.grounded,
            hallucination_risk=report.hallucination_risk,
            unsupported=report.unsupported,
        )

    def reengage(self, session_id: str) -> Reengagement:
        """A deterministic, slide-grounded re-engagement beat (the REENGAGING
        action a low-attention learner gets), rendered without a model server so
        the offline demo and tests stay stable.
        """
        lesson = self.lesson_for(session_id)  # raises KeyError on unknown session
        if not lesson.slides:
            return Reengagement(
                text="Let's refocus. Take a breath and let's pick up the lesson.",
                prompt="What would you like to revisit?",
            )
        slide = self.current_slide(session_id)
        # Fall back to the title so the recap/citation is never blank.
        recap = " ".join((slide.narration or slide.body or slide.title).split())[:300]
        text = (
            f"Let's take a quick breath and refocus. Remember, we're on "
            f'"{slide.title}": {recap}'
        ).strip()
        prompt = f'In your own words, what\'s the main idea of "{slide.title}"?'
        return Reengagement(text=text, prompt=prompt, citations=[f"{slide.title}: {recap}"])
