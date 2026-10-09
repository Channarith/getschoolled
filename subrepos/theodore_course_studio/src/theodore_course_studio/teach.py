"""Theodore teach/present session with gap-focused pathing + durable resume."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from aoep_shared.course_studio_access import (
    SAMPLE_ENDED,
    SAMPLE_MINUTES,
    SAMPLE_PREVIEW,
)

from .avatar_director import avatar_script_for_slide
from .lesson_photos import photo_plate
from .question_slide import (
    SourceLookup,
    build_question_slide,
    lookup_question_sources,
    official_sources,
    question_fits_course,
)
from .topic_cover import (
    completion_percent,
    example_card_svg,
    example_lines,
    match_slide,
    slide_has_art,
)
from .assessment import (
    GeneratedQuiz,
    QuizQuestion,
    QuizResult,
    build_pop_quiz_for_slide,
    build_summary_quiz,
    grade_quiz,
)
from .cert_multimodal import preferred_modalities
from .certification_prep import track_training_text
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
    build_order_steps_game,
    grade_game,
    media_suggestions_for_slide,
    pick_game_for_slide,
    pick_visual_game_for_slide,
)
from .presentation_director import presentation_for_slide, timeline_for_client
from .presentation_styles import sentences_for
from .generate import CourseBuilder
from .knowledge import (
    KnowledgeStore,
    LearningObjective,
    LearnerKnowledgeState,
    next_slide_indexes,
    objectives_from_slides,
)
from .lesson_locale import localize_lesson, localize_quiz
from .narration_runtime import clip_hints
from .profile_adapt import adapt_slide
from .quality_telemetry import StudioTelemetryStore, get_telemetry
from .studio_languages import normalize_language
from .tts_client import normalize_voice_gender, tts_client_hints
from .types import CourseSlide, LearnerProfileScores, StudioCourse, TeachTurn
from .voice_agent import (
    CourseStudioVoiceAgent,
    VoiceTurn,
    course_context_for,
    get_voice_agent,
)


def _voice_turn_language(voice: VoiceTurn, slide_language: str) -> str:
    """Language the agent's words are really in.

    The offline fallback emits an English holding line whatever language was
    asked for, so trusting its ``language_code`` makes TTS read English aloud in
    a foreign voice.
    """
    if voice.fallback_used:
        return "en"
    return voice.language_code or slide_language


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
    # Persona drives BOTH the on-screen avatar model and the TTS voice so a
    # female voice is always paired with the female presenter (and vice versa).
    voice_gender: str = "female"
    history: list[TeachTurn] = field(default_factory=list)
    pending_pop: QuizQuestion | None = None
    summary_quiz: GeneratedQuiz | None = None
    use_voice_agent: bool = True
    soft_limit_minutes: int = DEFAULT_SOFT_LIMIT_MINUTES
    soft_limit_slides: int = DEFAULT_SOFT_LIMIT_SLIDES
    checkpoint_ack: bool = False
    completed_slide_indexes: list[int] = field(default_factory=list)
    resumed_from_checkpoint: bool = False
    game_rotation: int = 0
    # Lesson-end games ignore a curated spec so each lesson can use a different check.
    forced_game_kind: str = ""
    # Sales-demo sessions stop at SAMPLE_MINUTES and cannot be extended.
    sample_only: bool = False


# One style per slide, in order, so a lesson shows animation, comparison, steps,
# and a challenge instead of the same photographic plate.
_SHOWCASE_STYLES = (
    "picture-storyboard-steps",
    "text-comparison",
    "narrative-cause-effect",
    "picture-compare",
    "text-steps",
    "challenge-choice-grid",
    "picture-example-callouts",
    "narrative-timeline",
)

_LESSON_QUIZ_STYLES = ("summary_quiz", "order_steps", "match_term", "compare")


def _stable_bucket(text: str, count: int) -> int:
    total = 0
    for char in text or "lesson":
        total = (total * 33 + ord(char)) & 0xFFFFFFFF
    return total % max(1, count)


def lesson_quiz_style(lesson_id: str) -> str:
    """Rotate the end-of-lesson check across the certification catalog.

    Neighboring lessons land on a different style: questions, ordering,
    matching, then a side-by-side comparison. Other courses use a stable hash.
    """
    from .certification_prep import list_cert_courses

    ids = [option.lesson_id for option in list_cert_courses()]
    if lesson_id in ids:
        return _LESSON_QUIZ_STYLES[ids.index(lesson_id) % len(_LESSON_QUIZ_STYLES)]
    return _LESSON_QUIZ_STYLES[_stable_bucket(lesson_id, len(_LESSON_QUIZ_STYLES))]


def _visual_timeline(slide: CourseSlide, index: int, spoken: str) -> dict[str, Any]:
    """Sections for this slide, captioned with the words actually being said."""
    shown = _showcase_slide(slide, index)
    return timeline_for_client(
        presentation_for_slide(shown, narration=spoken),
        sentences_for(shown, spoken),
    )


def _showcase_slide(slide: CourseSlide, index: int) -> CourseSlide:
    if (slide.presentation_style or "").strip():
        return slide
    style_id = _SHOWCASE_STYLES[index % len(_SHOWCASE_STYLES)]
    return slide.model_copy(update={"presentation_style": style_id})


def _compare_check(slide: CourseSlide, course_id: str) -> dict[str, Any]:
    """Two ideas side by side. The matching idea is not always on the left."""
    spec = slide.quiz_spec if isinstance(slide.quiz_spec, dict) else {}
    choices = [str(item).strip() for item in (spec.get("choices") or []) if str(item).strip()]
    prompt = str(spec.get("prompt") or f"Which idea matches {slide.title}?").strip()
    if len(choices) >= 2:
        correct = int(spec.get("correct_index") or 0)
        if correct < 0 or correct >= len(choices):
            correct = 0
        wrong = next((i for i in range(len(choices)) if i != correct), 0)
        left, right, side = choices[correct], choices[wrong], "left"
    else:
        lines = example_lines(slide)
        left = lines[0] if lines else (slide.title or "The lesson idea")
        right = lines[1] if len(lines) > 1 else "A rule from a different topic"
        side = "left"
    if _stable_bucket(f"{course_id}:{slide.slide_key or slide.title}", 2):
        left, right = right, left
        side = "right" if side == "left" else "left"
    return {"prompt": prompt, "left": left, "right": right, "correct_side": side}


class TeachEngine:
    def __init__(
        self,
        builder: CourseBuilder | None = None,
        knowledge: KnowledgeStore | None = None,
        voice: CourseStudioVoiceAgent | None = None,
        checkpoints: CheckpointStore | None = None,
        telemetry: StudioTelemetryStore | None = None,
        source_lookup: SourceLookup | None = None,
    ) -> None:
        self._builder = builder or CourseBuilder()
        self._source_lookup = source_lookup or lookup_question_sources
        # Follow the builder's data dir so mastery never leaks across data roots.
        self._knowledge = knowledge or KnowledgeStore(data_dir=self._builder.data_dir)
        self._voice = voice or get_voice_agent()
        self._checkpoints = checkpoints or CheckpointStore(data_dir=self._builder.data_dir)
        self._telemetry = telemetry or get_telemetry()
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
        voice_gender: str = "female",
        access: str = "full",
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
        sample_only = access == "sample"
        if sample_only:
            # The sales sample is a clock, not a slide count, and it wins over
            # the longer kid and trial windows.
            soft_minutes = SAMPLE_MINUTES
            soft_slides = max(soft_slides, len(path) + 1)

        existing = self._checkpoints.load(learner_id, course_id)
        path_pos = 0
        completed: list[int] = []
        resumed = False
        started_at = int(time.time() * 1000)
        # in_progress covers a closed tab. paused covers "Come back later".
        # The language and profile on this request stay in effect; the checkpoint
        # restores the slide.
        if resume and existing and existing.status in {"paused", "in_progress"} and existing.path:
            path = existing.path
            path_pos = min(existing.path_pos, max(0, len(path) - 1))
            completed = list(existing.completed_slide_indexes)
            resumed = True
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
                voice_gender=normalize_voice_gender(voice_gender),
                soft_limit_minutes=soft_minutes,
                soft_limit_slides=soft_slides,
                completed_slide_indexes=completed,
                resumed_from_checkpoint=resumed,
                checkpoint_ack=False,
                sample_only=sample_only,
            )
            self._sessions[session_id] = session
            self._persist_live(session, status="in_progress")
            payload = self._turn_payload(course, session)
            if resumed:
                payload["resumed"] = True
                payload["learner_id"] = session.learner_id
                if existing and existing.status == "paused":
                    place = " Your place was saved when you chose Come back later."
                else:
                    place = " Picking up where this account or profile left off."
                payload["resume_message"] = (
                    f"Resumed at slide {session.path_pos + 1} of {len(session.path)}."
                    f"{place}"
                )
            elif existing and existing.status in {"paused", "in_progress"}:
                payload["bookmark_available"] = True
                payload["bookmark"] = existing.model_dump(mode="json")
            return payload

    def current(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        return self._turn_payload(course, session)

    def advance(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        if self._sample_expired(session):
            return self._turn_payload(course, session)
        # Mark current slide completed before moving on.
        if session.path:
            cur = session.path[session.path_pos]
            if cur not in session.completed_slide_indexes:
                session.completed_slide_indexes.append(cur)
        if session.path_pos < len(session.path) - 1:
            session.path_pos += 1
            session.checkpoint_ack = False
        self._persist_live(session, status="in_progress")
        self._telemetry.record_slide_taught()
        return self._turn_payload(course, session)

    def _question_sources(self, course: Any, text: str) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        try:
            found = list(self._source_lookup(course, text) or [])
        except Exception:
            found = []
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in [*found, *official_sources(course)]:
            url = str(row.get("url") or "")
            if not url.startswith("https://") or url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "title": str(row.get("title") or url)[:120],
                    "url": url,
                    "snippet": str(row.get("snippet") or "")[:280],
                }
            )
            if len(rows) == 3:
                break
        return rows

    def _apply_question_card(self, payload: dict[str, Any], card: dict[str, Any]) -> None:
        turn = payload.get("turn") or {}
        turn["title"] = card["title"]
        turn["display_body"] = card["body"]
        turn["narration"] = card["body"]
        payload["turn"] = turn
        payload["examples"] = list(card["examples"])
        payload["topic_examples"] = list(card["examples"])
        payload["show_examples"] = True
        payload["topic_jump"] = True
        payload["matched"] = True
        payload["dynamic"] = True
        payload["sources"] = list(card["sources"])
        payload["example_svg"] = card["example_svg"]
        payload["storyboard_svg"] = ""
        payload["storyboard_concept"] = ""
        payload["photo_url"] = ""
        payload["activity_prompt"] = (
            "Open a source below, then say what the rule asks you to do."
        )

    def cover_topic(self, session_id: str, text: str) -> dict[str, Any]:
        """Open the slide that matches what the live conversation is about."""
        course, session = self._require(session_id)
        if self._sample_expired(session):
            payload = self._turn_payload(course, session)
            payload["matched"] = False
            return payload
        slide_index = match_slide(course, text)
        if slide_index is None:
            payload = self._turn_payload(course, session)
            if not question_fits_course(course, text):
                payload["matched"] = False
                return payload
            card = build_question_slide(course, text, self._question_sources(course, text))
            if card is None:
                payload["matched"] = False
                return payload
            self._apply_question_card(payload, card)
            return payload
        if slide_index not in session.path:
            session.path.append(slide_index)
        session.path_pos = session.path.index(slide_index)
        if slide_index not in session.completed_slide_indexes:
            session.completed_slide_indexes.append(slide_index)
        self._persist_live(session, status="in_progress")
        payload = self._topic_payload(course, session, slide_index)
        payload["matched"] = True
        payload["topic_jump"] = True
        return payload

    def resume_uncovered(self, session_id: str) -> dict[str, Any]:
        """Move to the next course slide the learner has not covered yet."""
        course, session = self._require(session_id)
        if self._sample_expired(session):
            payload = self._turn_payload(course, session)
            payload["course_complete"] = False
            return payload
        covered = set(session.completed_slide_indexes)
        order = session.path or [slide.index for slide in course.slides]
        chosen: int | None = None
        if order and order[session.path_pos] not in covered:
            chosen = session.path_pos
        else:
            for step in range(1, len(order)):
                pos = (session.path_pos + step) % len(order)
                if order[pos] not in covered:
                    chosen = pos
                    break
        if chosen is None:
            payload = self._turn_payload(course, session)
            payload["course_complete"] = True
            payload["show_examples"] = False
            return payload
        session.path_pos = chosen
        self._persist_live(session, status="in_progress")
        slide_index = session.path[session.path_pos]
        payload = self._topic_payload(course, session, slide_index)
        payload["matched"] = True
        payload["course_complete"] = False
        payload["resumed_uncovered"] = True
        return payload

    def _topic_payload(
        self, course: Any, session: TeachSession, slide_index: int
    ) -> dict[str, Any]:
        payload = self._turn_payload(course, session)
        slide = course.slides[slide_index]
        lines = example_lines(slide)
        payload["show_examples"] = bool(lines)
        payload["topic_examples"] = lines
        if lines and not slide_has_art(slide):
            payload["example_svg"] = example_card_svg(slide.title, lines)
        else:
            payload["example_svg"] = ""
        return payload

    def continue_past_checkpoint(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        if session.sample_only:
            # A sample cannot be extended into the rest of the class.
            return self._turn_payload(course, session)
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
        # Do NOT mark the current slide completed — it isn't finished. Resume
        # re-teaches the same slide (path_pos is unchanged), so counting it here
        # double-counted progress.
        checkpoint = self._persist_live(session, status="paused")
        self._telemetry.record_checkpoint_pause()
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
        self._telemetry.record_quiz(
            kind="pop", score=1.0 if result.passed else 0.0, passed=result.passed
        )
        selected_choice = (
            q.choices[selected_index]
            if 0 <= selected_index < len(q.choices)
            else ""
        )
        correct_choice = (
            q.choices[q.correct_index]
            if 0 <= q.correct_index < len(q.choices)
            else ""
        )
        correction = {
            "correct": result.passed,
            "selected_index": selected_index,
            "selected_choice": selected_choice,
            "correct_index": q.correct_index,
            "correct_choice": correct_choice,
            "explanation": q.explanation
            or f"The key learning point is: {correct_choice}",
        }
        session.pending_pop = None
        session.path = next_slide_indexes(session.objectives, session.knowledge)
        session.path_pos = min(session.path_pos, max(0, len(session.path) - 1))
        self._persist_live(session, status="in_progress")
        return {
            "result": result.model_dump(mode="json"),
            "correction": correction,
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
        localize_quiz(quiz, session.language)
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
        score = result.correct / max(1, result.total)
        self._telemetry.record_quiz(kind="summary", score=score, passed=result.passed)
        self._persist_live(session, status="in_progress")
        return result

    def game_for_current(self, session_id: str, *, prefer_visual: bool = False) -> GameChallenge:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        objective = self._objective_for_slide(session, slide.index)
        # Checkpoint play prefers a labeled picture challenge. Slides with an
        # authored game spec keep that spec, and the plain rotation is unchanged
        # when the caller does not ask for a picture challenge.
        forced = session.forced_game_kind
        session.forced_game_kind = ""
        if forced == "order_steps":
            session.game_rotation += 1
            return build_order_steps_game(slide, objective.objective_id)
        if forced == "match_term":
            session.game_rotation += 1
            return build_match_term_game(slide, objective.objective_id)
        authored = isinstance(slide.game_spec, dict) and bool(slide.game_spec)
        if prefer_visual and not authored:
            visual = pick_visual_game_for_slide(
                slide, objective.objective_id, rotate_index=session.game_rotation
            )
            if visual is not None:
                session.game_rotation += 1
                return visual
        game = pick_game_for_slide(
            slide, objective.objective_id, rotate_index=session.game_rotation
        )
        session.game_rotation += 1
        return game

    def grade_game_response(
        self,
        session_id: str,
        challenge: dict[str, Any],
        response: dict[str, Any],
    ) -> GameAttemptResult:
        _, session = self._require(session_id)
        game = GameChallenge.model_validate(challenge)
        result = grade_game(game, response)
        self._telemetry.record_game(
            kind=game.kind.value, score=result.score, passed=result.passed
        )
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
        self._telemetry.record_language_switch()
        self._persist_live(session, status="in_progress")
        return self._turn_payload(course, session)

    def voice_respond(
        self,
        session_id: str,
        learner_message: str,
    ) -> dict[str, Any]:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        context = course_context_for(
            course.title,
            [(s.title, s.body) for s in course.slides],
            slide.title,
            slide.body,
        )
        track = str((course.profile_adaptations or {}).get("track") or "")
        if track:
            extra = track_training_text(track)
            if extra:
                context = f"{context}\n\nRest of this course:\n{extra}"
        turn = self._voice.respond(
            session_id=session_id,
            learner_message=learner_message,
            language_code=session.language,
            lesson_context=context,
            scope_to_course=True,
        )
        self._telemetry.record_voice_turn(tts=True)
        reply_lang = _voice_turn_language(turn, session.language)
        # Q&A only. The full lesson payload would re-present the slide, grow
        # history, and hand the page a second narration clip. Talk stays
        # on-demand: hints describe the reply, they do not bake an audio URL.
        spoken = turn.message
        avatar = avatar_script_for_slide(slide, narration=spoken)
        return {
            "voice": turn.model_dump(mode="json"),
            "voice_gender": session.voice_gender,
            "tts": {
                **tts_client_hints(
                    reply_lang, session.voice_gender, text=spoken
                ),
            },
            "spoken_language": reply_lang,
            "slide_index": session.path[session.path_pos],
            "avatar": avatar.model_dump(mode="json"),
        }

    def voice_present_current(self, session_id: str) -> dict[str, Any]:
        course, session = self._require(session_id)
        slide = course.slides[session.path[session.path_pos]]
        adapted = adapt_slide(slide, session.profile)
        slide_lang = self._spoken_language(course, session, slide)
        if session.use_voice_agent:
            voice = self._voice.present_slide(
                session_id=session_id,
                title=adapted.title,
                body=adapted.display_body or adapted.narration,
                language_code=session.language,
                course_title=course.title,
            )
            speak_lang = _voice_turn_language(voice, slide_lang)
        else:
            # Reading the slide verbatim, so the words are in the slide's language.
            voice = VoiceTurn(
                provider="slide-narration",
                message=adapted.narration,
                language_code=slide_lang,
                fallback_used=True,
            )
            speak_lang = slide_lang
        self._telemetry.record_voice_turn(tts=True)
        return {
            "voice": voice.model_dump(mode="json"),
            "voice_gender": session.voice_gender,
            "tts": {
                **tts_client_hints(
                    speak_lang, session.voice_gender, text=voice.message
                ),
            },
            "slide_index": session.path[session.path_pos],
            "language": session.language,
            "spoken_language": speak_lang,
            "avatar": avatar_script_for_slide(
                slide, narration=voice.message
            ).model_dump(mode="json"),
        }

    @staticmethod
    def _spoken_language(
        course: StudioCourse,
        session: TeachSession,
        slide: CourseSlide | None = None,
    ) -> str:
        """Language the slide WORDS are in — TTS must match the text, not the request.

        When a translation is unavailable the words stay English, so speaking
        them with the requested voice would mispronounce every word. Coverage is
        per-slide: a course can be curated for a third of its slides, so the
        slide's own language wins over the course-level summary.
        """
        if slide is not None and slide.spoken_language:
            return slide.spoken_language
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
        # Only record a turn when the slide actually changes — current() polls
        # and profile/language re-reads call this payload too, and appending
        # every time grew history unboundedly with duplicates.
        if not session.history or session.history[-1].slide_index != turn.slide_index:
            session.history.append(turn)
        objective = self._objective_for_slide(session, slide_index)
        media = [m.model_dump(mode="json") for m in media_suggestions_for_slide(slide)]
        knowledge = (
            session.knowledge.model_dump(mode="json") if session.knowledge else {}
        )
        voice_meta = None
        spoken = turn.narration
        speak_lang = self._spoken_language(course, session, slide)
        translation_source = course.profile_adaptations.get("translation_source")
        translation_note = course.profile_adaptations.get("translation_note", "")
        # Early-learning narration is carefully written to a tiny vocabulary and
        # must not be paraphrased into harder language. xAI remains available for
        # the learner's explicit "Ask Theodore" questions.
        # Only rewrite English slides in English. A failed voice call used to
        # replace Khmer (and every other language) with an English holding line.
        if (
            session.use_voice_agent
            and course.audience == "general"
            and session.language == "en"
            and speak_lang == "en"
        ):
            voice = self._voice.present_slide(
                session_id=session.session_id,
                title=turn.title,
                body=turn.display_body or turn.narration,
                language_code=session.language,
                course_title=course.title,
            )
            spoken = voice.message
            speak_lang = _voice_turn_language(voice, speak_lang)
            voice_meta = voice.model_dump(mode="json")
        localized = localize_lesson(
            title=turn.title,
            body=turn.display_body or spoken,
            narration=spoken,
            activity=slide.activity_prompt or "",
            examples=list(slide.examples or []),
            source_language=speak_lang,
            target_language=session.language,
        )
        activity_prompt = slide.activity_prompt or ""
        examples = list(slide.examples or [])
        if localized.applied:
            spoken = localized.narration
            speak_lang = session.language
            turn.title = localized.title or turn.title
            turn.display_body = localized.body or spoken
            turn.narration = spoken
            turn.spoken_language = speak_lang
            activity_prompt = localized.activity or activity_prompt
            examples = localized.examples or examples
            translation_source = localized.provider or "translated"
            translation_note = f"Spoken in the selected language ({speak_lang})."
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
        avatar = avatar_script_for_slide(slide, narration=spoken)
        next_key = ""
        if session.path_pos + 1 < len(session.path):
            next_slide = course.slides[session.path[session.path_pos + 1]]
            next_key = next_slide.slide_key
        recorded = {}
        if spoken == (slide.narration or slide.body):
            recorded = clip_hints(
                slide.slide_key,
                speak_lang,
                session.voice_gender,
                next_slide_key=next_key,
            )
        is_lesson_end = session.path_pos == len(session.path) - 1
        is_section_end = "section_end" in slide.tags or "checkpoint" in slide.tags
        has_quiz_bank = any(
            course.slides[i].quiz_spec for i in session.path[: session.path_pos + 1]
        )
        sample_complete = self._sample_expired(session, now)
        quiz_style = ""
        compare_check: dict[str, Any] | None = None
        session.forced_game_kind = ""
        if is_lesson_end and has_quiz_bank:
            lesson_key = str(
                (course.profile_adaptations or {}).get("lesson_id") or course.course_id
            )
            quiz_style = lesson_quiz_style(lesson_key)
            if quiz_style == "summary_quiz":
                checkpoint_activity = "quiz"
                checkpoint_kind = "summary_quiz"
            elif quiz_style == "compare":
                checkpoint_activity = "compare"
                checkpoint_kind = "compare"
                compare_check = _compare_check(slide, course.course_id)
            else:
                checkpoint_activity = "game"
                checkpoint_kind = quiz_style
                session.forced_game_kind = quiz_style
        elif is_lesson_end or is_section_end:
            checkpoint_activity = "game"
            checkpoint_kind = "reflection"
        else:
            checkpoint_activity = "reflection"
            checkpoint_kind = "reflection"
        lesson_prompts = {
            "summary_quiz": "End of the lesson. Answer the questions.",
            "order_steps": "End of the lesson. Put the steps in order.",
            "match_term": "End of the lesson. Match the idea to the right meaning.",
            "compare": "End of the lesson. Compare the two ideas and pick the one that fits.",
        }
        if quiz_style and speak_lang == "en":
            checkpoint_prompt_text = lesson_prompts[quiz_style]
        elif is_section_end and not is_lesson_end and speak_lang == "en":
            checkpoint_prompt_text = "Now that this section is complete, check what you remember."
        elif speak_lang == "en":
            checkpoint_prompt_text = "Before finishing the lesson, check what you remember."
        else:
            checkpoint_prompt_text = str(activity_prompt or turn.title)
        activity_checkpoint = {
            "due": bool(is_lesson_end or is_section_end),
            "scope": "lesson" if is_lesson_end else "section",
            "activity": checkpoint_activity,
            "kind": checkpoint_kind,
            "quiz_style": quiz_style,
            "prompt": checkpoint_prompt_text,
        }
        if compare_check is not None:
            activity_checkpoint["compare"] = compare_check
        # A finished lesson still gets its check. The sample clock only blocks
        # checks that would appear before the lesson ends.
        if sample_complete and not is_lesson_end:
            activity_checkpoint["due"] = False
        plate = photo_plate(
            title=turn.title or slide.title,
            body=turn.display_body or slide.body or "",
            category=str(getattr(course.category, "value", course.category)),
            index=slide.index,
        )
        return {
            "turn": turn_dump,
            "slide_index": slide_index,
            "path": session.path,
            "path_pos": session.path_pos,
            "language": session.language,
            "spoken_language": speak_lang,
            "translation_source": translation_source,
            "translation_note": translation_note,
            "disclaimer": course.profile_adaptations.get("disclaimer", ""),
            "jurisdiction": course.profile_adaptations.get("jurisdiction", ""),
            "objective": objective.model_dump(mode="json"),
            "media": media,
            "storyboard_svg": slide.storyboard_svg or "",
            "storyboard_concept": slide.storyboard_concept or "",
            "storyboard_scene_id": slide.storyboard_scene_id or "",
            "activity_prompt": activity_prompt,
            "examples": examples,
            "modalities": list(slide.modalities or []),
            "learning_kit": {
                "modalities": list(slide.modalities or []),
                "preferred": preferred_modalities(session.profile.model_dump()),
                "has_picture": bool(slide.picture_url),
                "has_storyboard": bool(slide.storyboard_svg),
                "has_video": bool(slide.video_url),
                "has_examples": bool(slide.examples),
                "has_quiz": bool(slide.quiz_spec),
                "has_game": bool(slide.game_spec),
                "has_activity": bool(slide.activity_prompt),
                "quiz_ready": bool(slide.quiz_spec),
                "game_ready": bool(slide.game_spec),
            },
            "animation": {
                "enter": "fade-up",
                "emphasis": "highlight-title",
                "duration_ms": 650,
            },
            "visual_timeline": _visual_timeline(slide, session.path_pos, spoken),
            "photo_url": plate["url"],
            "photo_transition": plate["transition"],
            "avatar": avatar.model_dump(mode="json"),
            "voice_gender": session.voice_gender,
            "knowledge": knowledge,
            "voice": voice_meta,
            "tts": {
                **tts_client_hints(
                    speak_lang, session.voice_gender, text=spoken
                ),
                **recorded,
            },
            "progress": {
                "known": len(session.knowledge.known_objective_ids) if session.knowledge else 0,
                "gaps": len(session.knowledge.gap_objective_ids) if session.knowledge else 0,
                "total_objectives": len(session.objectives),
                "completed_slides": len(session.completed_slide_indexes),
                "path_length": len(session.path),
                "completion_percent": completion_percent(
                    course, session.completed_slide_indexes
                ),
            },
            "checkpoint": checkpoint_block,
            "activity_checkpoint": activity_checkpoint,
            "access_mode": "sample" if session.sample_only else "full",
            "sample": {
                "minutes": SAMPLE_MINUTES if session.sample_only else 0,
                "complete": sample_complete,
                "continue_allowed": not sample_complete,
                "message": (
                    SAMPLE_ENDED
                    if sample_complete
                    else SAMPLE_PREVIEW
                    if session.sample_only
                    else ""
                ),
            },
            "session": {
                "session_id": session.session_id,
                "learner_id": session.learner_id,
                "course_id": session.course_id,
                "started_at_ms": session.started_at_ms,
                "elapsed_ms": elapsed_ms,
                "resumed": session.resumed_from_checkpoint,
            },
        }

    def _sample_expired(self, session: TeachSession, now_ms: int | None = None) -> bool:
        if not session.sample_only:
            return False
        now = int(time.time() * 1000) if now_ms is None else now_ms
        return (now - session.started_at_ms) >= session.soft_limit_minutes * 60_000

    def _require(self, session_id: str) -> tuple[StudioCourse, TeachSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            course = self._builder.get_course(session.course_id)
            if course is None:
                raise KeyError(session.course_id)
            return course, session
