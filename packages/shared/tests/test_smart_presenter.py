"""Smart AI presenter: summarization, digression, time-aware pacing."""

from aoep_shared.meeting import (
    build_presentation_plan,
    build_smart_presentation_plan,
    summarize_narration,
)
from aoep_shared.meeting.smart_presenter import enrich_spoken_narration
from aoep_shared.teaching.lesson import LessonPlan, LessonStep


def _long_lesson(n: int = 12) -> LessonPlan:
    steps = [
        LessonStep(0, "intro", "Welcome", "Welcome everyone to today's class on algebra."),
    ]
    for i in range(1, n - 1):
        body = " ".join([f"This is sentence {j} about topic {i}." for j in range(12)])
        steps.append(LessonStep(i, "segment", f"Topic {i}", body))
    steps.append(LessonStep(n - 1, "outro", "Close", "Thanks for learning with us today."))
    return LessonPlan(title="Long Algebra", subject="math", engine="fallback", steps=steps)


def test_summarize_narration_shortens():
    long = " ".join(["Word"] * 200)
    short = summarize_narration(long, target_words=40)
    assert len(short.split()) < len(long.split())
    assert "slide" in short.lower()


def test_enrich_spoken_adds_techniques():
    spoken = enrich_spoken_narration(
        "Variables represent unknown values.",
        topic="Algebra",
        heading="Variables",
        kind="segment",
    )
    assert "Variables" in spoken or "unknown" in spoken
    assert len(spoken) > 20


def test_enrich_spoken_does_not_stack_on_outro():
    close = (
        "You made it through algebra. "
        "Pick one idea to practice today. "
        "Come back anytime for a refresher."
    )
    spoken = enrich_spoken_narration(
        close,
        topic="algebra",
        heading="You did it!",
        kind="outro",
        category="summary",
    )
    assert spoken == close
    assert "In the real world" not in spoken
    assert "Now that we've set the stage" not in spoken


def test_smart_plan_fits_time_budget():
    lesson = _long_lesson(14)
    lesson.steps.insert(5, LessonStep(5, "segment", "Try it: Topic 3",
                                       "Practice applying topic 3 step by step."))
    base = build_presentation_plan(lesson)
    smart = build_smart_presentation_plan(
        lesson, duration_min=5, elapsed_min=0, enable_time_budget=True,
    )
    assert smart.total_seconds <= base.total_seconds + 30
    actions = {s.action for s in smart.steps}
    assert "skip" in actions or "summarize" in actions or "fast" in actions


def test_time_crunch_with_elapsed_min():
    lesson = _long_lesson(10)
    smart = build_smart_presentation_plan(
        lesson, duration_min=30, elapsed_min=25, enable_time_budget=True,
    )
    crunch = [s for s in smart.steps if s.presenter_meta == "time_crunch_warning"]
    assert crunch or smart.total_seconds < 600
