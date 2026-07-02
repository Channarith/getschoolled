"""Presentation phrasing sanity checks."""

from aoep_shared.presentation_skills import apply_technique, enrich_narration, sanitize_point


def test_sanitize_point_replaces_generic_heading():
    assert sanitize_point("Introduction", topic="Physics") == "Physics"
    assert sanitize_point("Welcome: Physics", topic="Physics") == "Physics"


def test_hook_question_uses_topic_not_intro_heading():
    line = apply_technique("hook_question", topic="Physics", point="Introduction")
    assert "Introduction" not in line
    assert "Physics" in line


def test_opener_enrichment_reads_naturally():
    body = "Welcome to our course on algebra. You will learn equations and graphs."
    spoken = enrich_narration(
        body,
        topic="algebra",
        point="Introduction",
        techniques=["agenda_signpost"],
    )
    assert "Welcome to our course" in spoken
    assert "wondered Introduction" not in spoken
