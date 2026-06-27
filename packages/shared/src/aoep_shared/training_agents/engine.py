"""Training session engine: drives a scenario through the cognitive agents.

A :class:`TrainingSession` walks a learner through a :class:`Scenario` one phase
at a time. For each phase it can produce a *brief* (situational picture +
pre-mortem) and grade a *decision* (quality + speed + reasoning), then adapt the
next phase to the learner's behavior. Deterministic and offline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aoep_shared.schemas import ClassType

from .agents import (
    BehaviorAdaptation,
    CriticalThinkingAgent,
    ForecastingAgent,
    LearningBehaviorAgent,
    PreMortem,
    RapidDecisionAgent,
    RapidDecisionResult,
    ReasoningReview,
    SituationalAwarenessAgent,
    SituationPicture,
)
from .scenario import Scenario, ScenarioPhase


@dataclass
class PhaseBrief:
    phase_id: str
    title: str
    situation: str
    prompt: str
    options: List[dict]
    decision_window_s: float
    situation_picture: SituationPicture
    premortem: PreMortem
    skills: List[str]

    def as_dict(self) -> dict:
        return {
            "phase_id": self.phase_id,
            "title": self.title,
            "situation": self.situation,
            "prompt": self.prompt,
            "options": list(self.options),
            "decision_window_s": round(self.decision_window_s, 2),
            "situation_picture": self.situation_picture.as_dict(),
            "premortem": self.premortem.as_dict(),
            "skills": list(self.skills),
        }


@dataclass
class DecisionOutcome:
    phase_id: str
    chosen_option_id: str
    correct: bool
    quality: float
    score: float
    consequence: str
    feedback: str
    recommended: str
    rapid: RapidDecisionResult
    reasoning: ReasoningReview
    behavior: BehaviorAdaptation
    next_phase_id: Optional[str]
    done: bool

    def as_dict(self) -> dict:
        return {
            "phase_id": self.phase_id,
            "chosen_option_id": self.chosen_option_id,
            "correct": self.correct,
            "quality": round(self.quality, 3),
            "score": round(self.score, 3),
            "consequence": self.consequence,
            "feedback": self.feedback,
            "recommended": self.recommended,
            "rapid": self.rapid.as_dict(),
            "reasoning": self.reasoning.as_dict(),
            "behavior": self.behavior.as_dict(),
            "next_phase_id": self.next_phase_id,
            "done": self.done,
        }


@dataclass
class TrainingSession:
    scenario: Scenario
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    class_type: ClassType = ClassType.SOLO
    current_phase_id: str = ""
    done: bool = False
    outcomes: List[DecisionOutcome] = field(default_factory=list)

    # Agents (shared, stateless across phases).
    sa: SituationalAwarenessAgent = field(default_factory=SituationalAwarenessAgent)
    forecaster: ForecastingAgent = field(default_factory=ForecastingAgent)
    rapid: RapidDecisionAgent = field(default_factory=RapidDecisionAgent)
    critic: CriticalThinkingAgent = field(default_factory=CriticalThinkingAgent)
    coach: LearningBehaviorAgent = field(default_factory=LearningBehaviorAgent)

    # Rolling behavior signals.
    _scores: List[float] = field(default_factory=list)
    _timeliness: List[float] = field(default_factory=list)
    _reasoning: List[float] = field(default_factory=list)
    _emotional: List[int] = field(default_factory=list)
    _window_scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.current_phase_id:
            self.current_phase_id = self.scenario.first_phase().id

    # -- briefs ----------------------------------------------------------- #
    def _phase(self, phase_id: str) -> ScenarioPhase:
        ph = self.scenario.phase(phase_id)
        if ph is None:
            raise KeyError(phase_id)
        return ph

    def current_phase(self) -> ScenarioPhase:
        return self._phase(self.current_phase_id)

    def brief(self, noticed: Optional[List[str]] = None) -> PhaseBrief:
        """Situational picture + pre-mortem for the current phase.

        The decision window reflects the LearningBehaviorAgent's ``window_scale``
        so a struggling learner gets more time and a strong one gets less.
        """
        ph = self.current_phase()
        window = round(max(1.0, ph.decision_window_s * self._window_scale), 1)
        return PhaseBrief(
            phase_id=ph.id,
            title=ph.title,
            situation=ph.situation,
            prompt=ph.prompt,
            options=[{"id": o.id, "text": o.text} for o in ph.options],
            decision_window_s=window,
            situation_picture=self.sa.assess(ph, noticed=noticed),
            premortem=self.forecaster.premortem(ph),
            skills=list(ph.skills),
        )

    # -- decisions -------------------------------------------------------- #
    def decide(
        self, option_id: str, *, elapsed_s: float, rationale: str = ""
    ) -> DecisionOutcome:
        if self.done:
            raise ValueError("session already complete")
        ph = self.current_phase()
        option = ph.option(option_id)
        if option is None:
            raise KeyError(option_id)

        scaled_window = max(1.0, ph.decision_window_s * self._window_scale)
        timed_phase = ScenarioPhase(
            id=ph.id, title=ph.title, situation=ph.situation, prompt=ph.prompt,
            options=ph.options, cues=ph.cues, threats=ph.threats,
            decision_window_s=scaled_window, skills=ph.skills, recommended=ph.recommended,
        )
        rapid = self.rapid.score(timed_phase, option, elapsed_s)
        reasoning = self.critic.evaluate(ph, option, rationale)

        # Accumulate behavior signals, then adapt for the NEXT phase.
        self._scores.append(rapid.score)
        self._timeliness.append(rapid.timeliness)
        self._reasoning.append(reasoning.reasoning_score)
        self._emotional.append(reasoning.emotional_markers)
        behavior = self.coach.adapt(
            scores=self._scores,
            timeliness=self._timeliness,
            reasoning_scores=self._reasoning,
            # Window the frustration signal so a recovering learner de-escalates.
            frustration_markers=sum(self._emotional[-3:]),
            class_type=self.class_type,
        )
        self._window_scale = behavior.window_scale

        # Branch (option override) or fall through to linear order.
        next_id = option.next_phase or self.scenario.next_phase_id(ph.id)
        done = next_id is None
        outcome = DecisionOutcome(
            phase_id=ph.id,
            chosen_option_id=option.id,
            correct=option.is_correct,
            quality=rapid.quality,
            score=rapid.score,
            consequence=option.consequence,
            feedback=option.feedback,
            recommended=ph.recommended,
            rapid=rapid,
            reasoning=reasoning,
            behavior=behavior,
            next_phase_id=next_id,
            done=done,
        )
        self.outcomes.append(outcome)
        if done:
            self.done = True
        else:
            self.current_phase_id = next_id  # type: ignore[assignment]
        return outcome

    # -- debrief ---------------------------------------------------------- #
    def summary(self) -> dict:
        n = len(self.outcomes)
        overall = round(_mean([o.score for o in self.outcomes]), 3)
        avg_quality = round(_mean([o.quality for o in self.outcomes]), 3)
        avg_timeliness = round(_mean([o.rapid.timeliness for o in self.outcomes]), 3)
        avg_reasoning = round(_mean([o.reasoning.reasoning_score for o in self.outcomes]), 3)
        passed = overall >= self.scenario.pass_threshold and self.done

        # Per-skill scoring: average each decision's score across its phase skills.
        skill_scores: Dict[str, List[float]] = {}
        for o in self.outcomes:
            ph = self.scenario.phase(o.phase_id)
            for sk in (ph.skills if ph else []):
                skill_scores.setdefault(sk, []).append(o.score)
        per_skill = {sk: round(_mean(v), 3) for sk, v in skill_scores.items()}

        strengths = [sk for sk, v in per_skill.items() if v >= 0.7]
        growth = [sk for sk, v in per_skill.items() if v < 0.5]

        debrief = self._debrief_text(overall, passed, growth)
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario.id,
            "scenario_title": self.scenario.title,
            "decisions": n,
            "completed": self.done,
            "passed": passed,
            "overall_score": overall,
            "avg_quality": avg_quality,
            "avg_timeliness": avg_timeliness,
            "avg_reasoning": avg_reasoning,
            "per_skill": per_skill,
            "strengths": strengths,
            "growth_areas": growth,
            "debrief": debrief,
        }

    def _debrief_text(self, overall: float, passed: bool, growth: List[str]) -> str:
        head = (
            "Outcome: you handled it." if passed
            else "Outcome: not a clean save - but that's why we drill."
        )
        if growth:
            focus = ", ".join(g.replace("_", " ") for g in growth)
            tail = f" Next rep, focus on: {focus}."
        else:
            tail = " Across the board your reads and timing held up - tighten the clock next time."
        return f"{head} Overall {round(overall * 100)}%.{tail}"


def _mean(xs: List[float], default: float = 0.0) -> float:
    return (sum(xs) / len(xs)) if xs else default
