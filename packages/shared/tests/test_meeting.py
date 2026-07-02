"""Part 3: meeting providers, presentation plan/driver, factory + fallback."""

import pytest

from aoep_shared.meeting import (
    GoogleMeetProvider,
    LocalPlayMeetingProvider,
    MeetingPresenter,
    MockMeetingProvider,
    TeamsProvider,
    ZoomProvider,
    build_meeting_provider,
    build_presentation_plan,
    estimate_seconds,
    present_with_provider,
)
from aoep_shared.teaching.lesson import LessonPlan, LessonStep


def _lesson():
    return LessonPlan(
        title="Algebra 101", subject="math", engine="fallback",
        steps=[
            LessonStep(0, "intro", "Welcome", "Welcome to algebra. Let's begin learning today."),
            LessonStep(1, "segment", "Solving for x",
                       "To solve for x we isolate the variable on one side.",
                       on_screen_points=["isolate x", "balance both sides"]),
            LessonStep(2, "outro", "Closing", "Great job. Go practice what you learned."),
        ],
    )


def test_estimate_and_plan():
    assert estimate_seconds("") >= 3.0
    assert estimate_seconds("one two three four five", wpm=150) > 0
    plan = build_presentation_plan(_lesson())
    assert len(plan.steps) == 3
    assert plan.total_seconds > 0
    assert plan.est_minutes >= 1
    assert plan.steps[1].slide_index == 1


def test_mock_provider_create_and_present():
    provider = MockMeetingProvider()
    meeting = provider.create_meeting("Algebra 101", duration_min=10)
    assert meeting.offline is True
    assert meeting.join_url.startswith("https://meet.local/mock/")

    plan = build_presentation_plan(_lesson())
    seen = []
    result = provider.present(meeting, plan, on_event=lambda e: seen.append(e.action))
    assert result.steps_presented == 3
    assert "open_slide" in seen and "speak" in seen and "end" in seen
    assert result.transcript.strip()
    # Mock "streamed" every step.
    assert provider.delivered == [0, 1, 2]


def test_presenter_schedules_and_presents():
    presenter = MeetingPresenter(MockMeetingProvider())
    result = presenter.present_lesson(_lesson(), topic="Algebra")
    assert result.meeting.topic == "Algebra"
    assert result.total_seconds > 0


def test_factory_and_real_providers_need_creds(monkeypatch):
    assert isinstance(build_meeting_provider("mock"), MockMeetingProvider)
    with pytest.raises(ValueError):
        build_meeting_provider("bogus")

    # Real providers raise NotImplementedError without credentials.
    for var in ("GOOGLE_ACCESS_TOKEN", "GOOGLE_MEET_ACCESS_TOKEN",
                "ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET",
                "TEAMS_ACCESS_TOKEN", "GRAPH_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(NotImplementedError):
        GoogleMeetProvider().create_meeting("x")
    with pytest.raises(NotImplementedError):
        ZoomProvider().create_meeting("x")
    with pytest.raises(NotImplementedError):
        TeamsProvider().create_meeting("x")


def test_present_with_provider_falls_back_to_mock(monkeypatch):
    for var in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    provider_used, result = present_with_provider(
        _lesson(), provider="zoom", sync_slides=False,
    )
    assert provider_used == "zoom->local"
    assert result.steps_presented == 3


def test_present_with_provider_synced_local_fallback(monkeypatch):
    for var in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    provider_used, result = present_with_provider(_lesson(), provider="zoom")
    assert provider_used == "zoom->local"
    assert result.steps_presented == 3


def test_local_play_provider_prints_and_speaks(monkeypatch, capsys):
    from aoep_shared.meeting import LocalPlayMeetingProvider

    spoken = []
    monkeypatch.setattr(
        "aoep_shared.meeting.natural_tts.speak_natural_blocking",
        lambda text, **kw: spoken.append(text) or True,
    )
    provider = LocalPlayMeetingProvider(speak=True, sync_slides=False)
    meeting = provider.create_meeting("Algebra")
    assert meeting.join_url.startswith("local://classroom/")
    plan = build_presentation_plan(_lesson())
    result = provider.present(meeting, plan)
    out = capsys.readouterr().out
    assert "SLIDE 1" in out
    assert "Presenter:" in out
    assert len(spoken) == 3
    assert result.steps_presented == 3
