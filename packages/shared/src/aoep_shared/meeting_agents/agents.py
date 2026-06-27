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
    ADAPTIVE_COACH = "adaptive_coach"
    CRITICAL_THINKING_COACH = "critical_thinking_coach"
    SITUATIONAL_ANALYST = "situational_analyst"
    RAPID_RESPONSE_COACH = "rapid_response_coach"
    FORECASTING_MENTOR = "forecasting_mentor"
    EMERGENCY_SIM_COACH = "emergency_sim_coach"


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
    active_scenario: str = "general_classroom"
    scenario_risk: float = 0.2
    stress_level: float = 0.2
    forecast_horizon_min: int = 15
    adaptations_issued: int = 0
    critical_prompts_issued: int = 0
    situational_briefs_issued: int = 0
    rapid_drills_issued: int = 0
    forecast_notes_issued: int = 0
    emergency_drills_issued: int = 0
    drill_history: List[str] = field(default_factory=list)
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
        state.stress_level = min(1.0, max(0.0, 1.0 - state.attention))
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


@dataclass
class AdaptiveCoachAgent:
    """Adjusts pace based on learning behavior, stress, and engagement."""

    stress_floor: float = 0.55

    def tick(self, state: SharedSessionState) -> Optional[str]:
        should_adapt = (
            state.attention < 0.65
            or state.stress_level > self.stress_floor
            or len(state.pending_questions) >= 2
            or (state.scenario_risk >= 0.5 and state.adaptations_issued == 0)
        )
        if not should_adapt:
            return None
        pace = "slowing down"
        if state.attention > 0.8 and state.stress_level < 0.3:
            pace = "speeding up"
        line = humanize_narration(
            f"Adapting pace now: {pace}. I will use shorter beats and check understanding each step.",
            state.dialect, language=state.language,
        )
        state.adaptations_issued += 1
        state.attention = min(1.0, state.attention + 0.1)
        _log(
            state,
            AgentRole.ADAPTIVE_COACH,
            "adapt_pacing",
            line,
            pace=pace,
            stress=round(state.stress_level, 3),
            attention=round(state.attention, 3),
        )
        return line


@dataclass
class CriticalThinkingCoachAgent:
    """Issues short prompts that force evidence-based reasoning."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if state.critical_prompts_issued >= 2:
            return None
        if state.slide_index % 2 != 0 and state.scenario_risk < 0.45:
            return None
        prompt = humanize_narration(
            "Critical check: what evidence supports your first instinct, and what evidence contradicts it?",
            state.dialect, language=state.language,
        )
        state.critical_prompts_issued += 1
        _log(
            state,
            AgentRole.CRITICAL_THINKING_COACH,
            "critical_prompt",
            prompt,
            scenario=state.active_scenario,
            risk=round(state.scenario_risk, 3),
        )
        return prompt


@dataclass
class SituationalAnalystAgent:
    """Summarizes key situational cues before the learner acts."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if state.scenario_risk < 0.35:
            return None
        if state.situational_briefs_issued >= 2:
            return None
        detail = (
            f"Situation brief: scenario={state.active_scenario}, "
            f"risk={state.scenario_risk:.2f}, stress={state.stress_level:.2f}. "
            "Prioritize aviate, navigate, communicate."
        )
        spoken = humanize_narration(detail, state.dialect, language=state.language)
        state.situational_briefs_issued += 1
        _log(
            state,
            AgentRole.SITUATIONAL_ANALYST,
            "situational_brief",
            spoken,
            scenario=state.active_scenario,
        )
        return spoken


@dataclass
class RapidResponseCoachAgent:
    """Runs split-second decision drills under pressure."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if state.rapid_drills_issued >= 2:
            return None
        if state.scenario_risk < 0.5 and state.stress_level < 0.5:
            return None
        drill = humanize_narration(
            "Rapid drill: 30-second decision. Say your immediate action, backup action, and abort trigger.",
            state.dialect, language=state.language,
        )
        state.rapid_drills_issued += 1
        state.drill_history.append("rapid_response")
        _log(
            state,
            AgentRole.RAPID_RESPONSE_COACH,
            "split_second_drill",
            drill,
            scenario=state.active_scenario,
            drills=state.rapid_drills_issued,
        )
        return drill


@dataclass
class ForecastingMentorAgent:
    """Forecasts near-term scenario shifts to train anticipation."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if state.forecast_notes_issued >= 2:
            return None
        if state.scenario_risk < 0.4:
            return None
        trend = "stable"
        if state.stress_level > 0.55 or state.attention < 0.5:
            trend = "worsening"
        note = humanize_narration(
            f"Forecast for next {state.forecast_horizon_min} minutes: {trend} risk path. "
            "Pre-brief your mitigation now before the issue compounds.",
            state.dialect, language=state.language,
        )
        state.forecast_notes_issued += 1
        _log(
            state,
            AgentRole.FORECASTING_MENTOR,
            "forecast",
            note,
            trend=trend,
            horizon_min=state.forecast_horizon_min,
        )
        return note


@dataclass
class EmergencySimulationCoachAgent:
    """Runs high-stakes emergency drills such as flight emergency landings."""

    def tick(self, state: SharedSessionState) -> Optional[str]:
        if "aviation" not in state.active_scenario and "landing" not in state.active_scenario:
            return None
        if state.emergency_drills_issued >= 2:
            return None
        runbook = humanize_narration(
            "Emergency landing drill: pitch for best glide, pick a landing zone, run engine-failure "
            "checks, then transmit mayday and commit to final approach.",
            state.dialect, language=state.language,
        )
        state.emergency_drills_issued += 1
        state.drill_history.append("emergency_landing")
        _log(
            state,
            AgentRole.EMERGENCY_SIM_COACH,
            "emergency_drill",
            runbook,
            scenario=state.active_scenario,
        )
        return runbook
