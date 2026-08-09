"""Theodore teach/present session with gap-focused pathing + durable resume."""

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
from .checkpoints import (
    DEFAULT_SOFT_LIMIT_MINUTES,
    DEFAULT_SOFT_LIMIT_SLIDES,
    CheckpointStore,
    TeachCheckpoint,
    checkpoint_prompt,
    soft_checkpoint_due,
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
    soft_limit_minutes: int = DEFAULT_SOFT_LIMIT_MINUTES
    soft_limit_slides: int = DEFAULT_SOFT_LIMIT_SLIDES
    checkpoint_ack: bool = False
    completed_slide_indexes: list[int] = field(default_factory=list)
    resumed_from_checkpoint: bool = False


class TeachEngine:
    def __init__(
        self,
        builder: CourseBuilder | None = None,
        knowledge: KnowledgeStore | None = None,
        voice: CourseStudioVoiceAgent | None = None,
        checkpoints: CheckpointStore | None = None,
    ) -> None:
        self._builder = builder or CourseBuilder()
        # Follow the builder's data dir so mastery never leaks across data roots.
        self._knowledge = knowledge or KnowledgeStore(data_dir=self._builder.data_dir)
        self._voice = voice or get_voice_agent()
        self._checkpoints = checkpoints or CheckpointStore(data_dir=self._builder.data_dir)
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
        resume: bool = False,
        soft_limit_minutes: int | None = None,
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
        soft_minutes = soft_limit_minutes
        if soft_minutes is None:
            soft_minutes = int(
                (course.profile_adaptations or {}).get(
                    "session_soft_minutes", DEFAULT_SOFT_LIMIT_MINUTES
                )
            )
        soft_slides = max(
            1,
            min(DEFAULT_SOFT_LIMIT_SLIDES, max(1, len(path) or 1)),
        )
        if course.audience not in {"general", "adult_cert_prep", "corporate"}:
            # Kids lessons stay short; do not force adult soft-stop UI.
            soft_minutes = max(soft_minutes, 60)
            soft_slides = max(soft_slides, len(path) + 1)

        existing = self._checkpoints.load(learner_id, course_id)
        path_pos = 0
        completed: list[int] = []
        resumed = False
        started_at = int(time.time() * 1000)
        if resume and existing and existing.status == "paused" and existing.path:
            path = existing.path
            path_pos = min(existing.path_pos, max(0, len(path) - 1))
            completed = list(existing.completed_slide_indexes)
            resumed = True
            if existing.profile:
                profile = existing.profile
            if existing.language:
                lang = normalize_language(existing.language)
            started_at = existing.started_at_ms or started_at

        self._voice.clear_session(session_id)
        with self._lock:
            session = TeachSession(
                session_id=session_id,
                course_id=course_id,
                learner_id=learner_id,
                language=lang,
                path=path or [0],
                path_pos=path_pos,
                profile=profile or LearnerProfileScores(),
                objectives=objectives,
                knowledge=knowledge,
                started_at_ms=started_at,
                use_voice_agent=use_voice_agent,
                soft_limit_minutes=soft_minutes,
                soft_limit_slides=soft_slides,
                completed_slide_indexes=completed,
                resumed_from_checkpoint=resumed,
                checkpoint_ack=False,
            )
            self._sessions[session_id] = session
            self._persist_live(session, status="in_progress")
            payload = self._turn_payload(course, session)
            if resumed:
                payload["resumed"] = True
                payload["resume_message"] = (
                    f"Resumed at slide {session.path_pos + 1} of {len(session.path)}. "
                    "Your place was saved when you chose Come back later."
                )
            elif existing and existing.status == "paused":
                payload["bookmark_available"] = True
                payload["bookmark"] = existing.model_dump(mode="json")
            return payload

    def current(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        return self._turn_payload(course, session)

    def advance(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        # Mark current slide completed before moving on.
        if session.path:
            cur = session.path[session.path_pos]
            if cur not in session.completed_slide_indexes:
                session.completed_slide_indexes.append(cur)
        if session.path_pos < len(session.path) - 1:
            session.path_pos += 1
            session.checkpoint_ack = False
        self._persist_live(session, status="in_progress")
        return self._turn_payload(course, session)

    def continue_past_checkpoint(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        session.checkpoint_ack = True
        # Extend soft window so the learner can finish this block.
        session.soft_limit_minutes = max(
            session.soft_limit_minutes,
            int((time.time() * 1000 - session.started_at_ms) / 60_000) + 10,
        )
        session.soft_limit_slides = max(
            session.soft_limit_slides, session.path_pos + 1 + DEFAULT_SOFT_LIMIT_SLIDES
        )
        self._persist_live(session, status="in_progress")
        payload = self._turn_payload(course, session)
        payload["checkpoint"] = {"due": False, "acknowledged": True}
        return payload

    def come_back_later(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        if session.path:
            cur = session.path[session.path_pos]
            if cur not in session.completed_slide_indexes:
                session.completed_slide_indexes.append(cur)
        checkpoint = self._persist_live(session, status="paused")
        with self._lock:
            self._sessions.pop(session_id, None)
        return {
            "status": "paused",
            "message": (
                f"Saved your place in “{course.title}” at slide "
                f"{checkpoint.path_pos + 1}. Come back anytime to resume."
            ),
            "checkpoint": checkpoint.model_dump(mode="json"),
        }

    def get_checkpoint(self, learner_id: str, course_id: str) -> TeachCheckpoint | None:
        return self._checkpoints.load(learner_id, course_id)

    def list_checkpoints(self, learner_id: str) -> list[TeachCheckpoint]:
        return self._checkpoints.list_for_learner(learner_id)

    def set_profile(self, session_id: str, profile: LearnerProfileScores) -> dict[str, Any]:
        course, session = self._require(session_id)
        session.profile = profile
        self._persist_live(session, status="in_progress")
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
        self._persist_live(session, status="in_progress")
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
        self._persist_live(session, status="in_progress")
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
            self._persist_live(session, status="in_progress")
        return result

    def course_for(self, session_id: str) -> StudioCourse:
        course, _ = self._require(session_id)
        return course

    def set_language(self, session_id: str, language: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        session.language = normalize_language(language)
        self._persist_live(session, status="in_progress")
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

    def _persist_live(self, session: TeachSession, *, status: str) -> TeachCheckpoint:
        now = int(time.time() * 1000)
        knowledge = session.knowledge
        checkpoint = TeachCheckpoint(
            learner_id=session.learner_id,
            course_id=session.course_id,
            session_id=session.session_id,
            path=list(session.path),
            path_pos=session.path_pos,
            language=session.language,
            profile=session.profile,
            known_objective_ids=list(knowledge.known_objective_ids) if knowledge else [],
            gap_objective_ids=list(knowledge.gap_objective_ids) if knowledge else [],
            completed_slide_indexes=list(session.completed_slide_indexes),
            started_at_ms=session.started_at_ms,
            updated_at_ms=now,
            elapsed_ms=max(0, now - session.started_at_ms),
            soft_limit_minutes=session.soft_limit_minutes,
            status=status,
            message="" if status != "paused" else "Come back later bookmark",
        )
        return self._checkpoints.save(checkpoint)

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
                "provider": (
                    "curated-child-read-aloud"
                    if course.audience
                    not in {"adult_cert_prep", "corporate"}
                    else "certification-prep-read-aloud"
                ),
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
        now = int(time.time() * 1000)
        elapsed_ms = max(0, now - session.started_at_ms)
        due = (not session.checkpoint_ack) and soft_checkpoint_due(
            started_at_ms=session.started_at_ms,
            path_pos=session.path_pos,
            soft_limit_minutes=session.soft_limit_minutes,
            soft_limit_slides=session.soft_limit_slides,
            now_ms=now,
            audience=course.audience,
        )
        checkpoint_block: dict[str, Any]
        if due:
            checkpoint_block = checkpoint_prompt(elapsed_ms, session.soft_limit_minutes)
        else:
            checkpoint_block = {
                "due": False,
                "elapsed_minutes": max(0, round(elapsed_ms / 60_000)),
                "soft_limit_minutes": session.soft_limit_minutes,
            }
        return {
            "turn": turn_dump,
            "slide_index": slide_index,
            "path": session.path,
            "path_pos": session.path_pos,
            "language": session.language,
            "spoken_language": speak_lang,
            "translation_source": course.profile_adaptations.get("translation_source"),
            "translation_note": course.profile_adaptations.get("translation_note", ""),
            "disclaimer": course.profile_adaptations.get("disclaimer", ""),
            "jurisdiction": course.profile_adaptations.get("jurisdiction", ""),
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
                "completed_slides": len(session.completed_slide_indexes),
                "path_length": len(session.path),
            },
            "checkpoint": checkpoint_block,
            "session": {
                "session_id": session.session_id,
                "learner_id": session.learner_id,
                "course_id": session.course_id,
                "started_at_ms": session.started_at_ms,
                "elapsed_ms": elapsed_ms,
                "resumed": session.resumed_from_checkpoint,
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
