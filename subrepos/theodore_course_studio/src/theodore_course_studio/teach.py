"""In-memory Theodore teach/present session with gap-focused pathing."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .assessment import (
    GeneratedQuiz,
    QuizQuestion,
    QuizResult,
    build_pop_quiz_for_slide,
    build_summary_quiz,
    grade_quiz,
)
from .engagement import (
    GameAttemptResult,
    GameChallenge,
    build_match_term_game,
    grade_game,
    media_suggestions_for_slide,
)
from .generate import CourseBuilder
from .knowledge import (
    KnowledgeStore,
    LearningObjective,
    LearnerKnowledgeState,
    next_slide_indexes,
    objectives_from_slides,
)
from .profile_adapt import adapt_slide
from .types import LearnerProfileScores, StudioCourse, TeachTurn


@dataclass
class TeachSession:
    session_id: str
    course_id: str
    learner_id: str = "learner-demo"
    path: list[int] = field(default_factory=list)
    path_pos: int = 0
    profile: LearnerProfileScores = field(default_factory=LearnerProfileScores)
    objectives: list[LearningObjective] = field(default_factory=list)
    knowledge: LearnerKnowledgeState | None = None
    started_at_ms: int = 0
    history: list[TeachTurn] = field(default_factory=list)
    pending_pop: QuizQuestion | None = None
    summary_quiz: GeneratedQuiz | None = None


class TeachEngine:
    def __init__(
        self,
        builder: CourseBuilder | None = None,
        knowledge: KnowledgeStore | None = None,
    ) -> None:
        self._builder = builder or CourseBuilder()
        self._knowledge = knowledge or KnowledgeStore()
        self._lock = threading.RLock()
        self._sessions: dict[str, TeachSession] = {}

    def start(
        self,
        *,
        session_id: str,
        course_id: str,
        profile: LearnerProfileScores | None = None,
        learner_id: str = "learner-demo",
        known_objective_ids: list[str] | None = None,
        focus_gaps: bool = True,
    ) -> dict[str, Any]:
        course = self._builder.get_course(course_id)
        if course is None:
            raise KeyError(course_id)
        if not course.slides:
            raise ValueError("course has no slides")
        objectives = objectives_from_slides(course_id, course.slides)
        knowledge = self._knowledge.assess_prior_knowledge(
            learner_id=learner_id,
            course_id=course_id,
            objectives=objectives,
            self_reported_known=known_objective_ids,
        )
        if focus_gaps:
            path = next_slide_indexes(objectives, knowledge)
        else:
            path = [s.index for s in course.slides]
        with self._lock:
            session = TeachSession(
                session_id=session_id,
                course_id=course_id,
                learner_id=learner_id,
                path=path or [0],
                path_pos=0,
                profile=profile or LearnerProfileScores(),
                objectives=objectives,
                knowledge=knowledge,
                started_at_ms=int(time.time() * 1000),
            )
            self._sessions[session_id] = session
            return self._turn_payload(course, session)

    def current(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        return self._turn_payload(course, session)

    def advance(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        if session.path_pos < len(session.path) - 1:
            session.path_pos += 1
        return self._turn_payload(course, session)

    def set_profile(self, session_id: str, profile: LearnerProfileScores) -> dict[str, Any]:
        course, session = self._require(session_id)
        session.profile = profile
        return self._turn_payload(course, session)

    def pop_quiz(self, session_id: str) -> QuizQuestion:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        objective = self._objective_for_slide(session, slide.index)
        q = build_pop_quiz_for_slide(slide, objective)
        session.pending_pop = q
        return q

    def answer_pop(self, session_id: str, selected_index: int) -> dict[str, Any]:
        course, session = self._require(session_id)
        q = session.pending_pop
        if q is None:
            raise ValueError("no pending pop quiz")
        result = grade_quiz(
            quiz_id=q.question_id,
            kind="pop",
            questions=[q],
            answers={q.question_id: selected_index},
            pass_threshold=1.0,
        )
        self._knowledge.record_outcome(
            learner_id=session.learner_id,
            course_id=session.course_id,
            objective_id=q.objective_id,
            correct=bool(result.attempts and result.attempts[0].correct),
        )
        session.knowledge = self._knowledge.load(session.learner_id, session.course_id)
        session.pending_pop = None
        session.path = next_slide_indexes(session.objectives, session.knowledge)
        session.path_pos = min(session.path_pos, max(0, len(session.path) - 1))
        return {
            "result": result.model_dump(mode="json"),
            "knowledge": session.knowledge.model_dump(mode="json"),
            "turn": self._turn_payload(course, session),
        }

    def summary_quiz(self, session_id: str, max_questions: int = 8) -> GeneratedQuiz:
        _, session = self._require(session_id)
        gap_ids = set(session.knowledge.gap_objective_ids if session.knowledge else [])
        gap_objs = [o for o in session.objectives if o.objective_id in gap_ids] or list(
            session.objectives
        )
        course, _ = self._require(session_id)
        quiz = build_summary_quiz(course.slides, gap_objs, max_questions=max_questions)
        session.summary_quiz = quiz
        return quiz

    def grade_summary(self, session_id: str, answers: dict[str, int]) -> QuizResult:
        _, session = self._require(session_id)
        quiz = session.summary_quiz
        if quiz is None:
            raise ValueError("no summary quiz")
        result = grade_quiz(
            quiz_id=quiz.quiz_id,
            kind="summary",
            questions=quiz.questions,
            answers=answers,
        )
        for attempt in result.attempts:
            if attempt.objective_id:
                self._knowledge.record_outcome(
                    learner_id=session.learner_id,
                    course_id=session.course_id,
                    objective_id=attempt.objective_id,
                    correct=attempt.correct,
                )
        session.knowledge = self._knowledge.load(session.learner_id, session.course_id)
        return result

    def game_for_current(self, session_id: str) -> GameChallenge:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        objective = self._objective_for_slide(session, slide.index)
        return build_match_term_game(slide, objective.objective_id)

    def grade_game_response(
        self,
        session_id: str,
        challenge: dict[str, Any],
        response: dict[str, Any],
    ) -> GameAttemptResult:
        _, session = self._require(session_id)
        game = GameChallenge.model_validate(challenge)
        result = grade_game(game, response)
        if result.objective_id:
            self._knowledge.record_outcome(
                learner_id=session.learner_id,
                course_id=session.course_id,
                objective_id=result.objective_id,
                correct=result.passed,
            )
            session.knowledge = self._knowledge.load(session.learner_id, session.course_id)
        return result

    def course_for(self, session_id: str) -> StudioCourse:
        course, _ = self._require(session_id)
        return course

    def _objective_for_slide(self, session: TeachSession, slide_index: int) -> LearningObjective:
        for obj in session.objectives:
            if slide_index in obj.slide_indexes:
                return obj
        return LearningObjective(
            objective_id=f"{session.course_id}::obj-{slide_index:03d}",
            course_id=session.course_id,
            title=f"Point {slide_index + 1}",
            slide_indexes=[slide_index],
        )

    def _turn_payload(self, course: StudioCourse, session: TeachSession) -> dict[str, Any]:
        slide_index = session.path[session.path_pos]
        slide = course.slides[slide_index]
        turn = adapt_slide(slide, session.profile)
        session.history.append(turn)
        objective = self._objective_for_slide(session, slide_index)
        media = [m.model_dump(mode="json") for m in media_suggestions_for_slide(slide)]
        knowledge = (
            session.knowledge.model_dump(mode="json") if session.knowledge else {}
        )
        return {
            "turn": turn.model_dump(mode="json"),
            "slide_index": slide_index,
            "path": session.path,
            "path_pos": session.path_pos,
            "objective": objective.model_dump(mode="json"),
            "media": media,
            "animation": {
                "enter": "fade-up",
                "emphasis": "highlight-title",
                "duration_ms": 650,
            },
            "knowledge": knowledge,
            "progress": {
                "known": len(session.knowledge.known_objective_ids) if session.knowledge else 0,
                "gaps": len(session.knowledge.gap_objective_ids) if session.knowledge else 0,
                "total_objectives": len(session.objectives),
            },
        }

    def _require(self, session_id: str) -> tuple[StudioCourse, TeachSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            course = self._builder.get_course(session.course_id)
            if course is None:
                raise KeyError(session.course_id)
            return course, session
