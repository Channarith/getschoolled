"""Audience readiness aggregation for Theodore / admins."""

from aoep_shared.audience_profile import (
    aggregate_audience,
    readiness_band,
    snapshot_from_adaptation,
    summarize_course_history,
)


def test_readiness_band():
    assert readiness_band(40) == "needs_support"
    assert readiness_band(60) == "developing"
    assert readiness_band(80) == "ready"


def test_snapshot_and_aggregate_prompt_safe():
    s1 = snapshot_from_adaptation(
        student_id="a",
        adaptation={"lx_score_ema": 82, "readiness_dimensions": {
            "engagement": 0.8, "mastery": 0.7, "clarity": 0.9,
            "pace_fit": 0.8, "completion": 0.5, "wellness": 1.0,
        }},
        primary_style="visual",
        preferred_language="es",
        enrollments=[
            {"status": "passed", "title": "Intro Chem", "updated_at": 2},
            {"status": "failed", "title": "Lab Safety", "updated_at": 1},
        ],
        physical_skill=0.8,
    )
    s2 = snapshot_from_adaptation(
        student_id="b",
        adaptation={"lx_score_ema": 50},
        primary_style="hands_on",
        preferred_language="en",
        enrollments=[{"status": "failed", "title": "Lab Safety", "updated_at": 3}],
    )
    aud = aggregate_audience([s1, s2])
    prompt = aud.to_prompt_safe()
    assert prompt["learner_count"] == 2
    assert "mean_readiness" in prompt
    assert "Lab Safety" in prompt["course_struggle_titles"]
    # No student ids in prompt-safe payload.
    assert "student_id" not in prompt
    private = s1.to_host_private()
    assert private["student_id"] == "a"
    assert "dimensions" in private


def test_course_history_summary():
    h = summarize_course_history([
        {"status": "passed", "title": "A", "updated_at": 3},
        {"status": "failed", "title": "B", "updated_at": 2},
        {"status": "needs_work", "title": "C", "updated_at": 1},
    ])
    assert h["passed"] == 1
    assert h["failed"] == 1
    assert h["needs_work"] == 1
    assert "B" in h["struggle_titles"]
