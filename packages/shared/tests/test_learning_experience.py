"""Continuous learning experience scoring."""

from aoep_shared.adaptive import LearnerSignals
from aoep_shared.learning_experience import (
    LXComponents,
    compute_lx_score,
    lx_tick,
    update_lx_ema,
    wellness_factor,
)
from aoep_shared.learner_adaptation import LearnerAdaptation
from aoep_shared.schemas import ClassType


def test_compute_lx_score_weighted():
    c = LXComponents(engagement=0.8, mastery=0.7, clarity=0.9, pace_fit=0.8, completion=0.5)
    score = compute_lx_score(c)
    assert 60 <= score <= 90


def test_wellness_lowers_score():
    healthy = LXComponents(wellness=wellness_factor("ok"))
    unwell = LXComponents(wellness=wellness_factor("unwell"))
    assert compute_lx_score(unwell) < compute_lx_score(healthy)


def test_lx_tick_returns_strategy_and_actions():
    signals = LearnerSignals(topic_mastery=0.3, quiz_accuracy=0.4, attention_trend=0.5)
    result = lx_tick(
        signals=signals,
        slide_index=2,
        slides_total=10,
        class_type=ClassType.SOLO,
        frustration_events=1,
    )
    assert 0 <= result.lx_score <= 100
    assert result.teaching_strategy
    assert result.improve_actions


def test_lx_tick_adapts_when_below_target():
    adapt = LearnerAdaptation(lx_score_ema=80.0)
    signals = LearnerSignals(topic_mastery=0.2, quiz_accuracy=0.2)
    result = lx_tick(
        signals=signals,
        slide_index=1,
        slides_total=12,
        adaptation=adapt,
        wellness_state="stressed",
    )
    assert result.pacing.value == "slow"
    assert result.reteach is True


def test_update_lx_ema():
    assert update_lx_ema(None, 70.0) == 70.0
    ema = update_lx_ema(70.0, 80.0)
    assert 70.0 < ema < 80.0
