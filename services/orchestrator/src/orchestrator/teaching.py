"""Live-class teaching loop: sessions, slide delivery, and Tutor Q&A (RAG).

This is the web-facing teaching brain consumed by apps/web. Retrieval uses the
dependency-free RAG index over curriculum passages; answers come from the
configured LLMProvider, with a deterministic offline fallback (grounded in the
retrieved passages) so the live demo works without a running model server.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from aoep_shared.groundedness import guard_answer
from aoep_shared.providers.base import ChatMessage
from aoep_shared.rag import Document, RagIndex
from aoep_shared.slang import default_lexicon
from pydantic import BaseModel, Field

from .curriculum import CurriculumStore, Lesson, Slide


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
    """In-memory session manager for the live-class teaching loop."""

    def __init__(self, factory, curriculum: Optional[CurriculumStore] = None) -> None:
        self.factory = factory
        self.curriculum = curriculum or CurriculumStore()
        self.llm = factory.llm()
        self.sessions: Dict[str, SessionState] = {}
        self._indexes: Dict[str, RagIndex] = {}

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

    def start_session(self, lesson_id: str, class_type: str) -> SessionState:
        if self.curriculum.get(lesson_id) is None:
            raise KeyError(lesson_id)
        session = SessionState(
            session_id=uuid.uuid4().hex[:12],
            class_type=class_type,
            lesson_id=lesson_id,
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionState:
        return self.sessions[session_id]

    def lesson_for(self, session_id: str) -> Lesson:
        return self.curriculum.get(self.sessions[session_id].lesson_id)  # type: ignore[return-value]

    def current_slide(self, session_id: str) -> Slide:
        session = self.sessions[session_id]
        return self.lesson_for(session_id).slides[session.current_slide]

    def advance(self, session_id: str) -> Slide:
        session = self.sessions[session_id]
        last = len(self.lesson_for(session_id).slides) - 1
        session.current_slide = min(session.current_slide + 1, last)
        return self.current_slide(session_id)

    def ask(self, session_id: str, question: str, language: str = "en") -> Answer:
        session = self.sessions[session_id]
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
            "by their meaning.\n"
            f"QUESTION: {question}{gloss}\nCONTEXT: {' '.join(context)}"
        )
        try:
            text = self.llm.complete(
                [
                    ChatMessage(role="system", content="You are a helpful teacher."),
                    ChatMessage(role="user", content=prompt),
                ]
            ).text
        except NotImplementedError:
            # No model server configured -> deterministic grounded fallback.
            text = _offline_answer(question, context)
        # Hallucination guard: only serve answers grounded in the retrieved
        # context; otherwise abstain/ground to avoid showing unsupported claims.
        safe_text, report = guard_answer(text, context, question=question)
        session.history.append(ChatTurn(role="student", text=question))
        session.history.append(ChatTurn(role="teacher", text=safe_text))
        return Answer(
            text=safe_text,
            citations=context,
            language=language,
            understood=norm.glossed,
            grounded=report.grounded,
            hallucination_risk=report.hallucination_risk,
            unsupported=report.unsupported,
        )
