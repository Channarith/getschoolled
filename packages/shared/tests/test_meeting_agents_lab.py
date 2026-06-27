"""Offline multi-agent meeting lab."""

import pytest

from aoep_shared.meeting_agents import run_meeting_agents_lab


@pytest.mark.parametrize("platform", ["zoom", "teams", "meet"])
def test_meeting_agents_lab_offline(platform: str):
    result = run_meeting_agents_lab(platform=platform, dialect="us_ca", ticks=6)
    assert result.bridge_state == "closed"
    assert any(e["agent"] == "chat_tutor" for e in result.agent_events)
    assert any(e["agent"] == "teacher" for e in result.agent_events)
    failed = [label for label, ok in result.checks if not ok]
    assert not failed, failed


def test_lab_texan_dialect_events():
    result = run_meeting_agents_lab(platform="zoom", dialect="us_tx", ticks=5)
    text = " ".join(e["detail"] for e in result.agent_events)
    assert "y'all" in text.lower() or "howdy" in text.lower() or "alright" in text.lower()


def test_lab_trains_situational_emergency_thinking():
    result = run_meeting_agents_lab(platform="zoom", dialect="us_general", ticks=3)
    events = [
        e for e in result.agent_events
        if e["agent"] == "situational_coach"
    ]
    assert any(e["kind"] == "forecast" for e in events)
    drills = [e for e in events if e["kind"] == "critical_thinking_drill"]
    assert drills
    drill_text = " ".join(e["detail"] for e in drills).lower()
    assert "emergency landing drill" in drill_text
    assert "60 seconds" in drill_text
    assert any(e["meta"].get("domain") == "aviation" for e in drills)
