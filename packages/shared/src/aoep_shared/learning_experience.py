"""Continuous learning experience (LX) scoring and adaptation loop.

Measures session quality on a 0–100 scale from engagement, mastery, clarity,
pace fit, and progress; selects teaching strategies via a lightweight bandit to
raise the score over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .adaptive import Difficulty, LearnerSignals, Pacing, PacingPlan
from .bandit import ContentBandit
from .learner_adaptation import LearnerAdaptation, merge_pacing_plan
from .schemas import ClassType

TEACHING_STRATEGIES: Tuple[str, ...] = (
    "worked_examples",
    "gentle_recap",
    "socratic",
    "drill",
    "visual_analogy",
)

LX_TARGET = 75.0
LX_EMA_ALPHA = 0.25

WELLNESS_FACTORS = {
    "ok": 1.0,
    "low_energy": 0.85,
    "stressed": 0.75,
    "unwell": 0.65,
}


@dataclass
class LXComponents:
  engagement: float = 0.7
  mastery: float = 0.5
  clarity: float = 0.9
  pace_fit: float = 0.7
  completion: float = 0.0
  wellness: float = 1.0

  def as_dict(self) -> dict:
      return {
          "engagement": round(self.engagement, 3),
          "mastery": round(self.mastery, 3),
          "clarity": round(self.clarity, 3),
          "pace_fit": round(self.pace_fit, 3),
          "completion": round(self.completion, 3),
          "wellness": round(self.wellness, 3),
      }


@dataclass
class LXTickResult:
    lx_score: float
    components: LXComponents
    pacing: Pacing
    difficulty: Difficulty
    reteach: bool
    teaching_strategy: str
    reasons: List[str] = field(default_factory=list)
    improve_actions: List[str] = field(default_factory=list)


def compute_lx_score(components: LXComponents) -> float:
    """Composite learning experience score (0–100)."""
    raw = (
        0.22 * _clamp01(components.engagement)
        + 0.28 * _clamp01(components.mastery)
        + 0.22 * _clamp01(components.clarity)
        + 0.18 * _clamp01(components.pace_fit)
        + 0.10 * _clamp01(components.completion)
    ) * _clamp01(components.wellness)
    return round(max(0.0, min(100.0, raw * 100.0)), 1)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def wellness_factor(state: str) -> float:
    return WELLNESS_FACTORS.get((state or "ok").lower(), 1.0)


def bandit_from_dict(raw: Optional[dict]) -> ContentBandit:
    bandit = ContentBandit()
    for arm in TEACHING_STRATEGIES:
        bandit.add_arm(arm)
    if raw:
        for arm, pair in raw.items():
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                bandit.arms[arm] = [float(pair[0]), float(pair[1])]
    return bandit


def bandit_to_dict(bandit: ContentBandit) -> dict:
    return {arm: list(vals) for arm, vals in bandit.arms.items()}


def components_from_session(
    *,
    signals: LearnerSignals,
    slide_index: int,
    slides_total: int,
    frustration_events: int = 0,
    wellness_state: str = "ok",
    declared_pace: str = "moderate",
    observed_pace: str = "moderate",
) -> LXComponents:
    """Estimate LX components from live session signals."""
    completion = slide_index / max(1, slides_total)
    engagement = _clamp01(
        0.5 * signals.attention_trend
        + 0.3 * min(1.0, signals.question_rate * 2)
        + 0.2 * (1.0 - min(1.0, signals.avg_response_latency_s / 20.0))
    )
    mastery = signals.skill()
    clarity = _clamp01(1.0 - frustration_events * 0.15)
    pace_fit = 0.75
    if declared_pace == observed_pace:
        pace_fit = 0.9
    elif declared_pace == "slow" and observed_pace == "fast":
        pace_fit = 0.45
    elif declared_pace == "fast" and observed_pace == "slow":
        pace_fit = 0.5
    return LXComponents(
        engagement=engagement,
        mastery=mastery,
        clarity=clarity,
        pace_fit=pace_fit,
        completion=completion,
        wellness=wellness_factor(wellness_state),
    )


def strategy_for_components(components: LXComponents, bandit: ContentBandit) -> str:
    """Pick a teaching strategy to raise the weakest LX dimension."""
    weakest = min(
        ("mastery", components.mastery),
        ("clarity", components.clarity),
        ("engagement", components.engagement),
        ("pace_fit", components.pace_fit),
        key=lambda x: x[1],
    )[0]
    heuristic = {
        "mastery": "worked_examples",
        "clarity": "gentle_recap",
        "engagement": "visual_analogy",
        "pace_fit": "gentle_recap",
    }.get(weakest, "worked_examples")
    selected = bandit.select()
    if selected and bandit.estimate(selected) >= bandit.estimate(heuristic):
        return selected
    return heuristic


def improve_actions_for(
    score: float,
    components: LXComponents,
    plan: PacingPlan,
    strategy: str,
) -> List[str]:
    actions: List[str] = []
    if score < LX_TARGET:
        actions.append(f"raise_lx_toward_{int(LX_TARGET)}")
    if components.mastery < 0.5:
        actions.append("add_worked_examples")
    if components.clarity < 0.7:
        actions.append("slow_explanations")
    if components.engagement < 0.6:
        actions.append("more_interactive_checks")
    if plan.reteach:
        actions.append("reteach_current_topic")
    if plan.pacing is Pacing.SLOW:
        actions.append("extend_review_time")
    actions.append(f"use_strategy:{strategy}")
    return actions


def lx_tick(
    *,
    signals: LearnerSignals,
    slide_index: int,
    slides_total: int,
    class_type: ClassType = ClassType.GROUP,
    declared_pace: str = "moderate",
    adaptation: Optional[LearnerAdaptation] = None,
    wellness_state: str = "ok",
    course_complexity: int = 3,
    frustration_events: int = 0,
    strategy_bandit: Optional[dict] = None,
) -> LXTickResult:
    """One measurement + adaptation step for the live teaching loop."""
    observed = adaptation.observed_pace if adaptation else "moderate"
    components = components_from_session(
        signals=signals,
        slide_index=slide_index,
        slides_total=slides_total,
        frustration_events=frustration_events,
        wellness_state=wellness_state,
        declared_pace=declared_pace,
        observed_pace=observed,
    )
    score = compute_lx_score(components)
    plan = merge_pacing_plan(
        signals,
        declared_pace=declared_pace,
        adaptation=adaptation,
        class_type=class_type,
        course_complexity=course_complexity,
        wellness_state=wellness_state,
    )
    bandit = bandit_from_dict(strategy_bandit)
    strategy = strategy_for_components(components, bandit)
    reasons = list(plan.reasons)
    if score < LX_TARGET:
        reasons.append(f"lx_below_target_{score}<_{LX_TARGET}")
    if adaptation and adaptation.lx_score_ema and score < adaptation.lx_score_ema:
        reasons.append("lx_below_personal_ema")
    actions = improve_actions_for(score, components, plan, strategy)
    return LXTickResult(
        lx_score=score,
        components=components,
        pacing=plan.pacing,
        difficulty=plan.difficulty,
        reteach=plan.reteach,
        teaching_strategy=strategy,
        reasons=reasons,
        improve_actions=actions,
    )


def update_lx_ema(current_ema: Optional[float], sample: float) -> float:
    if current_ema is None:
        return sample
    return round((1 - LX_EMA_ALPHA) * current_ema + LX_EMA_ALPHA * sample, 1)


def record_strategy_outcome(bandit: ContentBandit, strategy: str, *, success: bool) -> None:
    bandit.add_arm(strategy)
    bandit.record(strategy, success)
