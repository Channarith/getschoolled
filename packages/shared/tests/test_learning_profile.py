"""Onboarding learning profile survey + learner categorization."""

import pytest

from aoep_shared.learning_profile import (
    derive_learning_profile,
    onboarding_template,
    validate_onboarding_answers,
)


def _full_answers(**over):
    base = {
        "primary_style": "Visual — diagrams, video, demonstrations",
        "pace": "Moderate and steady",
        "structure": "Step-by-step in order",
        "session_length": "About 20–30 minutes",
        "group_preference": "Either works for me",
        "reading_level": "Intermediate",
        "motivation": "Career / job skills",
    }
    base.update(over)
    return base


def test_onboarding_template_has_required_questions():
    t = onboarding_template()
    assert t["title"]
    assert any(q["id"] == "primary_style" and q["required"] for q in t["questions"])
    assert "categories" in t


def test_validate_requires_primary_style():
    with pytest.raises(ValueError, match="primary_style"):
        validate_onboarding_answers({})


def test_derive_visual_step_by_step_category():
    p = derive_learning_profile(_full_answers())
    assert p.primary_style == "visual"
    assert p.learner_category == "visual_step_by_step"
    assert p.pace == "moderate"


def test_accessibility_routes_to_supported_category():
    p = derive_learning_profile(_full_answers(needs_captions=True))
    assert p.learner_category == "accessibility_supported"
    assert p.accessibility["needs_captions"] is True


def test_hands_on_practice_category():
    p = derive_learning_profile(_full_answers(
        primary_style="Hands-on — practice, labs, doing it yourself",
        structure="Short bursts with frequent practice",
    ))
    assert p.primary_style == "hands_on"
    assert p.learner_category == "hands_on_practice"


def test_adaptive_cold_start_from_profile():
    from aoep_shared.adaptive import Pacing, pacing_from_declared_profile

    plan = pacing_from_declared_profile(pace="slow", reading_level="beginner")
    assert plan.pacing == Pacing.SLOW
    assert "onboarding_profile" in plan.reasons

