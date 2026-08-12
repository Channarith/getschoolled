"""Profile, duration, and device-aware unified catalog selection."""

from aoep_shared.catalog_selection import (
    resolve_session_budget,
    select_learnable,
)
from aoep_shared.learnable.models import LearnableItem


def _items():
    return [
        LearnableItem(
            id="audio:short",
            source="audio",
            source_id="short",
            title="Short Audio",
            format="audio",
            language="en",
            duration_min=10,
            drive_safe=True,
        ),
        LearnableItem(
            id="lesson:visual",
            source="lesson",
            source_id="visual",
            title="Visual Live Lesson",
            format="live_class",
            language="es",
            duration_min=30,
        ),
        LearnableItem(
            id="video:long",
            source="catalog",
            source_id="long",
            title="Long Video",
            format="video",
            language="en",
            duration_min=45,
        ),
    ]


def test_session_budget_uses_survey_and_observed_pace():
    assert resolve_session_budget("short") == 10
    assert resolve_session_budget("medium", observed_pace="fast") == 13
    assert resolve_session_budget("long", explicit_minutes=120) == 90


def test_drive_mode_only_returns_drive_safe_audio():
    result = select_learnable(_items(), device_mode="drive", session_length="short")
    assert [row["item"]["id"] for row in result["items"]] == ["audio:short"]
    assert result["privacy"]["mac_address_used"] is False


def test_profile_score_drives_style_group_and_duration_ranking():
    # visual, moderate, step-by-step, short, group, intermediate, career, no access
    result = select_learnable(
        _items(),
        profile_score="15115510",
        language="es",
        device_mode="class",
    )
    assert result["session_budget_min"] == 10
    assert result["items"][0]["item"]["id"] == "lesson:visual"
    assert "group_preference" in result["items"][0]["reasons"]
    assert "adaptive_duration" in result["items"][0]["reasons"]


def test_offline_mode_excludes_live_classes():
    result = select_learnable(_items(), device_mode="offline")
    assert all(row["item"]["format"] != "live_class" for row in result["items"])
