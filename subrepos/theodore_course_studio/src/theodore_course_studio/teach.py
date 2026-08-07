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
from .studio_languages import normalize_language
from .tts_client import build_tts_get_url, tts_client_hints
from .types import LearnerProfileScores, StudioCourse, TeachTurn
from .voice_agent import CourseStudioVoiceAgent, get_voice_agent


@dataclass
class TeachSession:
    session_id: str
    course_id: str
    learner_id: str = "learner-demo"
    language: str = "en"
    path: list[int] = field(default_factory=list)
    path_pos: int = 0
    profile: LearnerProfileScores = field(default_factory=LearnerProfileScores)
    objectives: list[LearningObjective] = field(default_factory=list)
    knowledge: LearnerKnowledgeState | None = None
    started_at_ms: int = 0
    history: list[TeachTurn] = field(default_factory=list)
    pending_pop: QuizQuestion | None = None
    summary_quiz: GeneratedQuiz | None = None
    use_voice_agent: bool = True


class TeachEngine:
    def __init__(
        self,
        builder: CourseBuilder | None = None,
        knowledge: KnowledgeStore | None = None,
        voice: CourseStudioVoiceAgent | None = None,
    ) -> None:
        self._builder = builder or CourseBuilder()
        # Follow the builder's data dir so mastery never leaks across data roots.
        self._knowledge = knowledge or KnowledgeStore(data_dir=self._builder.data_dir)
        self._voice = voice or get_voice_agent()
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
        language: str | None = None,
        use_voice_agent: bool = True,
    ) -> dict[str, Any]:
        course = self._builder.get_course(course_id)
        if course is None:
            raise KeyError(course_id)
        if not course.slides:
            raise ValueError("course has no slides")
        lang = normalize_language(language or getattr(course, "language", None) or "en")
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
        self._voice.clear_session(session_id)
        with self._lock:
            session = TeachSession(
                session_id=session_id,
                course_id=course_id,
                learner_id=learner_id,
                language=lang,
                path=path or [0],
                path_pos=0,
                profile=profile or LearnerProfileScores(),
                objectives=objectives,
                knowledge=knowledge,
                started_at_ms=int(time.time() * 1000),
                use_voice_agent=use_voice_agent,
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

    def set_language(self, session_id: str, language: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        session.language = normalize_language(language)
        return self._turn_payload(course, session)

    def voice_respond(
        self,
        session_id: str,
        learner_message: str,
    ) -> dict[str, Any]:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        turn = self._voice.respond(
            session_id=session_id,
            learner_message=learner_message,
            language_code=session.language,
            lesson_context=f"{course.title}\n{slide.title}\n{slide.body}",
        )
        return {
            "voice": turn.model_dump(mode="json"),
            "tts": {
                **tts_client_hints(session.language),
                "get_url": build_tts_get_url(turn.message, language=session.language),
            },
            "turn": self._turn_payload(course, session),
        }

    def voice_present_current(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        adapted = adapt_slide(slide, session.profile)
        if session.use_voice_agent:
            voice = self._voice.present_slide(
                session_id=session_id,
                title=adapted.title,
                body=adapted.display_body or adapted.narration,
                language_code=session.language,
                course_title=course.title,
            )
        else:
            from .voice_agent import VoiceTurn

            voice = VoiceTurn(
                provider="slide-narration",
                message=adapted.narration,
                language_code=session.language,
                fallback_used=True,
            )
        return {
            "voice": voice.model_dump(mode="json"),
            "tts": {
                **tts_client_hints(session.language),
                "get_url": build_tts_get_url(voice.message, language=session.language),
            },
            "slide_index": session.path[session.path_pos],
            "language": session.language,
        }

    @staticmethod
    def _spoken_language(course: StudioCourse, session: TeachSession) -> str:
        """Language the slide WORDS are in — TTS must match the text, not the request.

        When a translation is unavailable the words stay English, so speaking
        them with the requested voice would mispronounce every word.
        """
        spoken = course.profile_adaptations.get("spoken_language")
        return spoken or session.language

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
        if not session.path:
            session.path = [0]
        session.path_pos = max(0, min(session.path_pos, len(session.path) - 1))
        slide_index = session.path[session.path_pos]
        slide = course.slides[slide_index]
        turn = adapt_slide(slide, session.profile)
        session.history.append(turn)
        objective = self._objective_for_slide(session, slide_index)
        media = [m.model_dump(mode="json") for m in media_suggestions_for_slide(slide)]
        knowledge = (
            session.knowledge.model_dump(mode="json") if session.knowledge else {}
        )
        voice_meta = None
        spoken = turn.narration
        # Early-learning narration is carefully written to a tiny vocabulary and
        # must not be paraphrased into harder language. xAI remains available for
        # the learner's explicit "Ask Theodore" questions.
        if session.use_voice_agent and course.audience == "general":
            # Enrich spoken line via xAI / offline fallback (text only).
            voice = self._voice.present_slide(
                session_id=session.session_id,
                title=turn.title,
                body=turn.display_body or turn.narration,
                language_code=session.language,
                course_title=course.title,
            )
            spoken = voice.message
            voice_meta = voice.model_dump(mode="json")
        speak_lang = self._spoken_language(course, session)
        if course.audience != "general":
            voice_meta = {
                "provider": "curated-child-read-aloud",
                "message": spoken,
                "language_code": speak_lang,
                "fallback_used": False,
                "translation_source": course.profile_adaptations.get(
                    "translation_source", "curated"
                ),
                "translation_note": course.profile_adaptations.get(
                    "translation_note", ""
                ),
            }
        turn_dump = turn.model_dump(mode="json")
        turn_dump["narration"] = spoken
        return {
            "turn": turn_dump,
            "slide_index": slide_index,
            "path": session.path,
            "path_pos": session.path_pos,
            "language": session.language,
            "spoken_language": speak_lang,
            "translation_source": course.profile_adaptations.get("translation_source"),
            "translation_note": course.profile_adaptations.get("translation_note", ""),
            "objective": objective.model_dump(mode="json"),
            "media": media,
            "activity_prompt": slide.activity_prompt,
            "animation": {
                "enter": "fade-up",
                "emphasis": "highlight-title",
                "duration_ms": 650,
            },
            "knowledge": knowledge,
            "voice": voice_meta,
            "tts": {
                **tts_client_hints(speak_lang),
                "get_url": build_tts_get_url(spoken, language=speak_lang),
            },
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
