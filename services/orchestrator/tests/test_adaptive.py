"""Phase 4 - adaptive policy unit tests."""

from aoep_shared.adaptive import (
    AdaptivePolicy,
    Difficulty,
    LearnerSignals,
    Pacing,
    signals_from_events,
)
from aoep_shared.schemas import ClassType


def test_high_skill_engaged_speeds_up_and_hardens_solo():
    s = LearnerSignals(
        topic_mastery=0.9,
        quiz_accuracy=0.9,
        avg_response_latency_s=3.0,
        attention_trend=0.95,
    )
    plan = AdaptivePolicy().plan(s, class_type=ClassType.SOLO)
    assert plan.difficulty is Difficulty.HARD
    assert plan.pacing is Pacing.FAST
    assert plan.reteach is False


def test_low_skill_slows_down_eases_and_reteaches():
    s = LearnerSignals(
        topic_mastery=0.2,
        quiz_accuracy=0.3,
        avg_response_latency_s=20.0,
        attention_trend=0.3,
    )
    plan = AdaptivePolicy().plan(s, class_type=ClassType.SOLO)
    assert plan.difficulty is Difficulty.EASY
    assert plan.pacing is Pacing.SLOW
    assert plan.reteach is True
    assert plan.reasons


def test_group_caps_difficulty_when_skill_not_clearly_high():
    # skill ~0.78 -> would be HARD solo, but group caps to MEDIUM.
    s = LearnerSignals(topic_mastery=0.78, quiz_accuracy=0.78, attention_trend=0.9,
                       avg_response_latency_s=4.0)
    solo = AdaptivePolicy().plan(s, class_type=ClassType.SOLO)
    group = AdaptivePolicy().plan(s, class_type=ClassType.GROUP)
    assert solo.difficulty is Difficulty.HARD
    assert group.difficulty is Difficulty.MEDIUM


def test_medium_when_mixed():
    s = LearnerSignals(topic_mastery=0.55, quiz_accuracy=0.55, attention_trend=0.7,
                       avg_response_latency_s=8.0)
    plan = AdaptivePolicy().plan(s, class_type=ClassType.GROUP)
    assert plan.difficulty is Difficulty.MEDIUM
    assert plan.pacing is Pacing.NORMAL


def test_signals_from_events_aggregation():
    s = signals_from_events(
        quiz_outcomes=[True, True, False, True],
        response_latencies_s=[2.0, 4.0],
        attention_samples=[0.8, 1.0],
        questions_asked=3,
        slides_seen=6,
        topic_mastery=0.7,
    )
    assert round(s.quiz_accuracy, 2) == 0.75
    assert s.avg_response_latency_s == 3.0
    assert s.attention_trend == 0.9
    assert s.question_rate == 0.5
    assert round(s.skill(), 3) == round(0.5 * 0.7 + 0.5 * 0.75, 3)


def test_attention_drop_forces_slow_even_if_skilled():
    s = LearnerSignals(topic_mastery=0.9, quiz_accuracy=0.9, attention_trend=0.2,
                       avg_response_latency_s=3.0)
    plan = AdaptivePolicy().plan(s, class_type=ClassType.SOLO)
    assert plan.pacing is Pacing.SLOW
