"""Specialized agents for a live video teaching session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from aoep_shared.cognitive_trainer import (
    BehaviorAdaptationAgent,
    CognitiveLearnerProfile,
    CognitiveTrainer,
)
from aoep_shared.dialect import get_dialect, humanize_narration, tutor_tone_hint
from aoep_shared.mental_readiness import ReadinessExercise
from aoep_shared.slang import default_lexicon

from .simulation import AgentEvent, InboundChat, VideoFrameEvent


class AgentRole(str, Enum):
    TEACHER = "teacher"
    CHAT_TUTOR = "chat_tutor"
    PERCEPTION = "perception"
    INTERRUPT_HOST = "interrupt_host"
    MODERATOR = "moderator"
    # Cognitive training agents
    COGNITIVE_COACH = "cognitive_coach"
    CRITICAL_THINKING_TRAINER = "critical_thinking_trainer"
    SITUATIONAL_AWARENESS_TRAINER = "situational_awareness_trainer"
    RAPID_DECISION_TRAINER = "rapid_decision_trainer"
    EMERGENCY_SCENARIO_TRAINER = "emergency_scenario_trainer"
    MENTAL_READINESS_TRAINER = "mental_readiness_trainer"


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


# ---------------------------------------------------------------------------
# Cognitive training agents (new)
# ---------------------------------------------------------------------------

@dataclass
class CognitiveCoachAgent:
    """Master cognitive training coordinator for a live session.

    Monitors learner wellness, selects the appropriate cognitive training
    mode, and delegates to specialist trainers.  Acts as the 'air traffic
    controller' for all cognitive-training agent activity.
    """

    trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)
    behavior_agent: BehaviorAdaptationAgent = field(default_factory=BehaviorAdaptationAgent)

    def tick(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
    ) -> Optional[str]:
        """Suggest the next cognitive training activity given current session state."""
        if state.attention < 0.4:
            return None  # Moderator handles re-engagement first

        rec = self.trainer.recommend_next_session(profile)
        wellness_gate = rec.get("wellness_gate", "approved")

        if wellness_gate != "approved":
            msg = humanize_narration(
                f"Let's take it easy — {wellness_gate}. Starting with a grounding exercise.",
                state.dialect, language=state.language,
            )
            _log(state, AgentRole.COGNITIVE_COACH, "wellness_gate", msg,
                 gate=wellness_gate)
            return msg

        exercise = rec.get("approved_exercise", "critical_thinking")
        bloom = rec.get("bloom_level", "understand")
        pressure = rec.get("cognitive_pressure", "moderate")

        msg = humanize_narration(
            f"Ready for a {exercise.replace('_', ' ')} exercise? "
            f"We'll work at {bloom} level with {pressure} cognitive pressure. "
            f"This builds on your current progress.",
            state.dialect, language=state.language,
        )
        _log(state, AgentRole.COGNITIVE_COACH, "recommend_exercise", msg,
             exercise=exercise, bloom=bloom, pressure=pressure)
        return msg

    def on_wellness_update(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        stress_level: int,
        focus_level: int,
    ) -> Optional[str]:
        """Process a wellness check-in and return a coaching response."""
        check_in = self.trainer.check_in(profile, stress_level, focus_level)
        msg = humanize_narration(
            check_in.readiness_note + " " + check_in.breath_cue,
            state.dialect, language=state.language,
        )
        _log(state, AgentRole.COGNITIVE_COACH, "wellness_checkin", msg,
             stress=stress_level, focus=focus_level,
             recommended=check_in.recommended_exercise.value)
        return msg


@dataclass
class CriticalThinkingTrainerAgent:
    """Live session agent that poses Socratic questions on the current lesson content."""

    _trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)

    def ask_question(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        term: str,
        passage: str,
    ) -> Optional[str]:
        question = self._trainer.critical_thinking_question(
            profile, term, passage, scenario=state.subject
        )
        msg = humanize_narration(
            f"[Critical Thinking] {question.text}",
            state.dialect, language=state.language,
        )
        _log(state, AgentRole.CRITICAL_THINKING_TRAINER, "socratic_question", msg,
             bloom=question.bloom_level.value, question_id=question.question_id)
        return msg

    def evaluate_answer(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        question,
        learner_answer: str,
    ) -> Optional[str]:
        result = self._trainer.critical_thinking_evaluate(profile, question, learner_answer)
        msg = humanize_narration(result.feedback, state.dialect, language=state.language)
        _log(state, AgentRole.CRITICAL_THINKING_TRAINER, "evaluate_answer", msg,
             score=result.score, bloom=result.bloom_level.value,
             gap=result.reasoning_gap)
        return msg


@dataclass
class SituationalAwarenessTrainerAgent:
    """Introduces OODA/DECIDE scenario exercises mid-session."""

    _trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)

    def introduce_scenario(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        scenario_id: str,
    ) -> Optional[str]:
        scenario = self._trainer.situational.get_scenario(scenario_id)
        if not scenario:
            return None
        intro = (
            f"[Situational Awareness] {scenario.title}: {scenario.description[:200]}"
            "\n\nUsing the OODA loop — what do you OBSERVE first?"
        )
        msg = humanize_narration(intro, state.dialect, language=state.language)
        _log(state, AgentRole.SITUATIONAL_AWARENESS_TRAINER, "scenario_intro", msg,
             scenario_id=scenario_id)
        return msg


@dataclass
class RapidDecisionTrainerAgent:
    """Delivers timed decision drills mid-session."""

    _trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)

    def deliver_drill(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        drill_id: str,
        pressure_level,
    ) -> Optional[str]:
        drill = self._trainer.rapid_decision.get_drill(drill_id)
        if not drill:
            return None
        allowed = self._trainer.rapid_decision.allowed_time(
            drill, pressure_level, wellness_state=profile.wellness_state
        )
        prompt = (
            f"[Rapid Decision — {allowed}s] {drill.situation}\n\n"
            + "\n".join(f"  {o.label}: {o.text}" for o in drill.options)
        )
        msg = humanize_narration(prompt, state.dialect, language=state.language)
        _log(state, AgentRole.RAPID_DECISION_TRAINER, "drill_delivered", msg,
             drill_id=drill_id, allowed_s=allowed)
        return msg


@dataclass
class EmergencyScenarioTrainerAgent:
    """Runs emergency simulation scenarios in-session with live AAR debrief."""

    _trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)

    def introduce_scenario(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        scenario_id: str,
    ) -> Optional[str]:
        if profile.wellness_state in ("stressed", "unwell"):
            msg = humanize_narration(
                "Emergency simulation is paused — let's do a mental readiness check first.",
                state.dialect, language=state.language,
            )
            _log(state, AgentRole.EMERGENCY_SCENARIO_TRAINER, "wellness_gate", msg)
            return msg
        scenario = self._trainer.emergency.get_scenario(scenario_id)
        if not scenario:
            return None
        intro = (
            f"[Emergency Scenario] {scenario.title}\n\n"
            f"{scenario.description}\n\n"
            f"Learning objectives: {'; '.join(scenario.learning_objectives[:3])}"
        )
        msg = humanize_narration(intro, state.dialect, language=state.language)
        _log(state, AgentRole.EMERGENCY_SCENARIO_TRAINER, "scenario_intro", msg,
             scenario_id=scenario_id, domain=scenario.domain.value)
        return msg


@dataclass
class MentalReadinessTrainerAgent:
    """Delivers pre-mortem, rehearsal, and TEM exercises in-session."""

    _trainer: CognitiveTrainer = field(default_factory=CognitiveTrainer)

    def deliver_rehearsal(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        rehearsal_key: str,
    ) -> Optional[str]:
        prompt = self._trainer.readiness_rehearsal(profile, rehearsal_key)
        msg = humanize_narration(prompt[:500], state.dialect, language=state.language)
        _log(state, AgentRole.MENTAL_READINESS_TRAINER, "mental_rehearsal", msg,
             key=rehearsal_key)
        return msg

    def deliver_pre_mortem(
        self,
        state: SharedSessionState,
        profile: CognitiveLearnerProfile,
        plan: str,
        failure_modes: List[str],
    ) -> Optional[str]:
        result = self._trainer.readiness_pre_mortem(profile, plan, failure_modes)
        mitigations_text = "; ".join(result.mitigations[:3])
        msg = humanize_narration(
            f"Pre-mortem complete. Top mitigations: {mitigations_text}",
            state.dialect, language=state.language,
        )
        _log(state, AgentRole.MENTAL_READINESS_TRAINER, "pre_mortem", msg,
             failure_modes_count=len(failure_modes))
        return msg
