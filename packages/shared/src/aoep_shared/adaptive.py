"""Phase 4 - adaptive learning policy.

Turns per-student learning-behavior signals (mastery, quiz accuracy, response
latency, attention trend, question rate) into a concrete teaching adjustment:
pacing (slow/normal/fast), difficulty (easy/medium/hard), and whether to
re-teach the current topic. Solo classes personalize aggressively; group classes
optimize for the cohort and damp extreme per-individual swings.

Pure, dependency-free, and fully unit-testable. The Director consults this on
each tick; the Memory service supplies the signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from .schemas import ClassType


class Pacing(str, Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class LearnerSignals:
    """Learning-behavior features for one student on the current topic."""

    topic_mastery: float = 0.5          # 0..1, EMA over quiz outcomes
    quiz_accuracy: float = 0.5          # 0..1, rolling accuracy
    avg_response_latency_s: float = 5.0  # mean time to answer
    attention_trend: float = 1.0        # 0..1, recent mean attention
    question_rate: float = 0.0          # questions asked per slide

    def skill(self) -> float:
        """Blended competence on the current topic."""
        return 0.5 * _clamp01(self.topic_mastery) + 0.5 * _clamp01(self.quiz_accuracy)


@dataclass
class PacingPlan:
    pacing: Pacing
    difficulty: Difficulty
    reteach: bool
    reasons: List[str] = field(default_factory=list)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class AdaptivePolicy:
    def __init__(
        self,
        *,
        mastery_low: float = 0.4,
        mastery_high: float = 0.75,
        attention_low: float = 0.5,
        latency_high_s: float = 12.0,
    ) -> None:
        self.mastery_low = mastery_low
        self.mastery_high = mastery_high
        self.attention_low = attention_low
        self.latency_high_s = latency_high_s

    def plan(
        self, signals: LearnerSignals, *, class_type: ClassType = ClassType.GROUP
    ) -> PacingPlan:
        reasons: List[str] = []
        skill = signals.skill()

        # Difficulty from blended skill.
        if skill >= self.mastery_high:
            difficulty = Difficulty.HARD
            reasons.append("high mastery/accuracy -> increase difficulty")
        elif skill <= self.mastery_low:
            difficulty = Difficulty.EASY
            reasons.append("low mastery/accuracy -> reduce difficulty")
        else:
            difficulty = Difficulty.MEDIUM

        # Pacing from engagement + speed + skill.
        slow = (
            signals.attention_trend < self.attention_low
            or signals.avg_response_latency_s > self.latency_high_s
            or skill <= self.mastery_low
        )
        fast = (
            signals.attention_trend >= 0.8
            and skill >= self.mastery_high
            and signals.avg_response_latency_s < self.latency_high_s * 0.5
        )
        if slow:
            pacing = Pacing.SLOW
            reasons.append("low attention / slow responses / low skill -> slow down")
        elif fast:
            pacing = Pacing.FAST
            reasons.append("engaged + high skill + quick answers -> speed up")
        else:
            pacing = Pacing.NORMAL

        reteach = signals.topic_mastery < self.mastery_low
        if reteach:
            reasons.append("topic mastery below threshold -> re-teach topic")

        # Group classes optimize for the cohort: avoid over-personalizing to one
        # learner. Cap difficulty unless skill is clearly high.
        if class_type is ClassType.GROUP and difficulty is Difficulty.HARD and skill < 0.85:
            difficulty = Difficulty.MEDIUM
            reasons.append("group cohort -> cap difficulty at medium")

        return PacingPlan(
            pacing=pacing, difficulty=difficulty, reteach=reteach, reasons=reasons
        )


def signals_from_events(
    *,
    quiz_outcomes: List[bool] | None = None,
    response_latencies_s: List[float] | None = None,
    attention_samples: List[float] | None = None,
    questions_asked: int = 0,
    slides_seen: int = 1,
    topic_mastery: float = 0.5,
    accuracy_window: int = 10,
) -> LearnerSignals:
    """Aggregate raw behavior events into :class:`LearnerSignals`."""
    outcomes = (quiz_outcomes or [])[-accuracy_window:]
    accuracy = (sum(1 for o in outcomes if o) / len(outcomes)) if outcomes else 0.5
    latencies = response_latencies_s or []
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 5.0
    attention = attention_samples or []
    attn_trend = (sum(attention) / len(attention)) if attention else 1.0
    rate = questions_asked / max(1, slides_seen)
    return LearnerSignals(
        topic_mastery=_clamp01(topic_mastery),
        quiz_accuracy=_clamp01(accuracy),
        avg_response_latency_s=avg_latency,
        attention_trend=_clamp01(attn_trend),
        question_rate=rate,
    )
