"""Teaching Director.

Phase1 slice of the lesson state machine: create sessions, deliver slides, and
answer questions via RAG + the LLM provider (Tutor agent). Session state is
in-memory for development; it migrates behind services/memory + Postgres later.
A full LangGraph stateful graph replaces this core without changing the API.
"""

from __future__ import annotations

import uuid
from typing import Dict, List

from eduplatform_shared.factory import ProviderFactory
from eduplatform_shared.schemas import (
    Answer,
    ChatTurn,
    ClassType,
    Lesson,
    Question,
    SessionState,
    Slide,
)

from app.curriculum import CurriculumStore
from app.rag import RagIndex


class Director:
    def __init__(self, factory: ProviderFactory, curriculum: CurriculumStore) -> None:
        self.factory = factory
        self.curriculum = curriculum
        self.llm = factory.llm()
        self.sessions: Dict[str, SessionState] = {}
        self._indexes: Dict[str, RagIndex] = {}

    def _index_for(self, lesson_id: str) -> RagIndex:
        if lesson_id not in self._indexes:
            self._indexes[lesson_id] = RagIndex(
                self.llm, self.curriculum.passages_for(lesson_id)
            )
        return self._indexes[lesson_id]

    def list_lessons(self) -> List[Lesson]:
        return self.curriculum.list_lessons()

    def start_session(self, lesson_id: str, class_type: ClassType) -> SessionState:
        lesson = self.curriculum.get(lesson_id)
        if lesson is None:
            raise KeyError(lesson_id)
        session = SessionState(
            session_id=uuid.uuid4().hex[:12],
            class_type=class_type,
            lesson_id=lesson_id,
            current_slide=0,
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionState:
        return self.sessions[session_id]

    def lesson_for_session(self, session_id: str) -> Lesson:
        session = self.sessions[session_id]
        return self.curriculum.get(session.lesson_id)  # type: ignore[return-value]

    def current_slide(self, session_id: str) -> Slide:
        session = self.sessions[session_id]
        lesson = self.curriculum.get(session.lesson_id)
        return lesson.slides[session.current_slide]  # type: ignore[union-attr]

    def advance(self, session_id: str) -> Slide:
        session = self.sessions[session_id]
        lesson = self.curriculum.get(session.lesson_id)
        last = len(lesson.slides) - 1  # type: ignore[union-attr]
        session.current_slide = min(session.current_slide + 1, last)
        return self.current_slide(session_id)

    def ask(self, session_id: str, question: Question) -> Answer:
        session = self.sessions[session_id]
        index = self._index_for(session.lesson_id)
        context = index.retrieve(question.text, k=2)
        prompt = (
            f"QUESTION: {question.text}\n"
            f"CONTEXT: {' '.join(context)}"
        )
        text = self.llm.complete(prompt, max_tokens=400)
        session.history.append(ChatTurn(role="student", text=question.text))
        session.history.append(ChatTurn(role="teacher", text=text))
        return Answer(text=text, citations=context, language=question.language)
