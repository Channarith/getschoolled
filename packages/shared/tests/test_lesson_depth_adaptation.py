"""Deep lessons, adaptive profiling, enriched games/audio."""

from aoep_shared.lesson_depth import TARGET_MIN_MINUTES, duration_minutes, enrich_slides
from aoep_shared.learner_adaptation import (
    LearnerAdaptation,
    detect_frustration,
    merge_pacing_plan,
)
from aoep_shared.adaptive import LearnerSignals
from aoep_shared.schemas import ClassType


class _S:
    def __init__(self, title, body, kind="teach", say_aloud=""):
        self.title = title
        self.body = body
        self.narration = body
        self.kind = kind
        self.say_aloud = say_aloud


def _make(idx, title, body, narr, *, kind="teach", say_aloud=""):
    s = _S(title, body, kind=kind, say_aloud=say_aloud)
    s.narration = narr
    return s


def test_enrich_slides_reaches_target_duration():
    slides = [_S(f"Topic {i}", "Photosynthesis converts light into sugar. Plants need it to grow.")
              for i in range(5)]
    enriched, _ = enrich_slides(
        slides,
        [f"Fact {i}: definition number {i}." for i in range(10)],
        target_min=20,
        slide_factory=_make,
    )
    assert duration_minutes(enriched) >= TARGET_MIN_MINUTES
    assert len(enriched) > len(slides)


def test_enrich_slides_is_conversational_and_varied():
    """No repetitive 'Example —/Reinforcement —' scaffold; beats are varied."""
    slides = [_S(f"Topic {i}", f"Concept {i} explains an idea. It applies in the field. Detail {i} matters.")
              for i in range(4)]
    enriched, _ = enrich_slides(
        slides, [f"Fact {i}: real detail {i}." for i in range(6)],
        slide_factory=_make,
    )
    titles = [s.title for s in enriched]
    # Old formulaic titles are gone.
    assert not any(tt.startswith("Worked example") or tt.startswith("Review:") for tt in titles)
    # Consecutive added slides don't repeat the same opening words.
    firsts = [s.body.split()[0:4] for s in enriched]
    repeats = sum(1 for a, b in zip(firsts, firsts[1:]) if a == b)
    assert repeats == 0
    # Conversational: direct address / questions present across the lesson.
    joined = " ".join(s.body for s in enriched).lower()
    assert "you" in joined and "?" in " ".join(s.body for s in enriched)


def test_enrich_slides_includes_repeat_after_me_checkpoints():
    slides = [_S(f"Topic {i}", f"Concept {i} is the key idea to remember here.") for i in range(3)]
    enriched, _ = enrich_slides(slides, [], slide_factory=_make)
    say = [s for s in enriched if getattr(s, "kind", "") == "say_aloud"]
    assert say, "expected at least one repeat-after-me checkpoint"
    assert all(s.say_aloud for s in say), "checkpoints must carry a phrase to speak"


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


def test_best_strategy_avoids_failed_approaches():
    adapt = LearnerAdaptation()
    adapt.record_failed_approach("socratic", "algebra", "confused")
    adapt.record_strategy("worked_examples", success=True)
    choice = adapt.best_strategy(["socratic", "worked_examples", "drill"])
    assert choice == "worked_examples"


def test_record_completion_infers_fast_pace():
    adapt = LearnerAdaptation()
    for _ in range(3):
        adapt.record_completion(10.0)
    assert adapt.observed_pace == "fast"
    assert adapt.avg_minutes_per_lesson == 10.0


def test_sensitivity_rule_blocks_strategy():
    adapt = LearnerAdaptation()
    adapt.record_trigger("harsh tone", "student upset", severity="high")
    assert adapt.should_avoid("use harsh tone")
    assert adapt.best_strategy(["harsh tone lecture", "gentle recap"]) == "gentle recap"


def test_course_finish_tracks_pace_vs_expected():
    adapt = LearnerAdaptation()
    rec = adapt.record_course_finish("algebra-101", 40.0, expected_min=25, complexity=4)
    assert rec.pace_vs_expected == "slow"
    assert adapt.course_finishes[-1].course_id == "algebra-101"


def test_wellness_triggers_gentle_plan():
    from aoep_shared.adaptive import LearnerSignals
    from aoep_shared.schemas import ClassType

    adapt = LearnerAdaptation()
    adapt.record_wellness("unwell", "feeling sick today")
    signals = LearnerSignals(topic_mastery=0.6, quiz_accuracy=0.6)
    plan = merge_pacing_plan(
        signals, adaptation=adapt, class_type=ClassType.SOLO, course_complexity=3,
    )
    assert plan.pacing.value == "slow"
    assert plan.reteach is True
    assert any("wellness" in r for r in plan.reasons)


def test_detect_wellness_from_text():
    from aoep_shared.learner_adaptation import detect_wellness

    out = detect_wellness("I am sick today and have a headache")
    assert out and out[0] == "unwell"
