"""Deep lessons, adaptive profiling, enriched games/audio."""

from aoep_shared.lesson_depth import TARGET_MIN_MINUTES, duration_minutes, enrich_slides
from aoep_shared.learner_adaptation import (
    LearnerAdaptation,
    detect_frustration,
    merge_pacing_plan,
)
from aoep_shared.adaptive import LearnerSignals
from aoep_shared.schemas import ClassType


def test_enrich_slides_reaches_target_duration():
    class S:
        def __init__(self, title, body):
            self.title = title
            self.body = body
            self.narration = body

    slides = [S(f"Topic {i}", "word " * 40) for i in range(5)]
    enriched, _ = enrich_slides(
        slides,
        [f"Fact {i}: definition number {i}." for i in range(10)],
        target_min=20,
        slide_factory=lambda idx, title, body, narr: S(title, body),
    )
    assert duration_minutes(enriched) >= TARGET_MIN_MINUTES
    assert len(enriched) > len(slides)


def test_frustration_detection():
    assert detect_frustration("this is stupid I hate this") == "this is stupid"


def test_adaptation_trigger_and_avoid():
    adapt = LearnerAdaptation()
    adapt.record_trigger("harsh tone", "student upset")
    assert adapt.should_avoid("harsh tone")


def test_merge_pacing_observed_slow():
    signals = LearnerSignals(topic_mastery=0.6, quiz_accuracy=0.6)
    adapt = LearnerAdaptation(observed_pace="slow")
    plan = merge_pacing_plan(signals, adaptation=adapt, class_type=ClassType.GROUP)
    assert plan.pacing.value == "slow"
