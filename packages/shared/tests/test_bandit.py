"""Content bandit (Thompson sampling) + model->policy signal wiring tests."""

import random

from aoep_shared.adaptive import AdaptivePolicy, Difficulty, signals_from_models
from aoep_shared.bandit import ContentBandit
from aoep_shared.schemas import ClassType


def test_bandit_estimate_tracks_success_rate():
    b = ContentBandit()
    for _ in range(8):
        b.record("video", True)
    for _ in range(8):
        b.record("text", False)
    assert b.estimate("video") > b.estimate("text")


def test_bandit_selects_better_arm_over_trials():
    b = ContentBandit()
    # "good" succeeds 90%, "bad" 10%.
    for i in range(50):
        b.record("good", i % 10 != 0)
        b.record("bad", i % 10 == 0)
    rng = random.Random(0)
    picks = [b.select(rng) for _ in range(200)]
    assert picks.count("good") > picks.count("bad")


def test_select_empty_bandit_is_none():
    assert ContentBandit().select() is None


def test_signals_from_models_feeds_policy():
    # High BKT mastery + high ability -> harder difficulty via the policy.
    s = signals_from_models(topic_mastery=0.9, quiz_accuracy=0.9, ability=2.0,
                            attention_trend=0.95, avg_response_latency_s=3.0)
    plan = AdaptivePolicy().plan(s, class_type=ClassType.SOLO)
    assert plan.difficulty is Difficulty.HARD

    low = signals_from_models(topic_mastery=0.2, quiz_accuracy=0.3, ability=-2.0,
                              attention_trend=0.3, avg_response_latency_s=20.0)
    assert AdaptivePolicy().plan(low, class_type=ClassType.SOLO).difficulty is Difficulty.EASY
