"""Select a meeting provider by name/env, with offline fallback to Mock."""

from __future__ import annotations

import os
from typing import Optional

from .base import Meeting, MeetingProvider, PresentationPlan, PresentationResult
from .providers import (
    GoogleMeetProvider,
    MockMeetingProvider,
    TeamsProvider,
    ZoomProvider,
)

_PROVIDERS = {
    "mock": MockMeetingProvider,
    "google_meet": GoogleMeetProvider,
    "googlemeet": GoogleMeetProvider,
    "meet": GoogleMeetProvider,
    "zoom": ZoomProvider,
    "teams": TeamsProvider,
    "msteams": TeamsProvider,
}


def build_meeting_provider(name: Optional[str] = None) -> MeetingProvider:
    """Build a provider by name (or ``MEETING_PROVIDER`` env; default mock)."""
    key = (name or os.environ.get("MEETING_PROVIDER", "mock")).strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"unknown meeting provider {name!r}; one of {sorted(set(_PROVIDERS))}")
    return cls()


def present_with_provider(
    lesson,
    *,
    provider: Optional[str] = None,
    topic: Optional[str] = None,
    start_iso: str = "",
    duration_min: Optional[int] = None,
    realtime: bool = False,
    fallback_to_mock: bool = True,
):
    """Schedule + present ``lesson`` with the requested provider.

    Falls back to the Mock provider when the requested real provider has no
    credentials (raises NotImplementedError) - so a demo/test always completes.
    Returns ``(provider_used, PresentationResult)``.
    """
    from .presenter import MeetingPresenter

    chosen = build_meeting_provider(provider)
    presenter = MeetingPresenter(chosen)
    try:
        result = presenter.present_lesson(
            lesson, topic=topic, start_iso=start_iso,
            duration_min=duration_min, realtime=realtime)
        return chosen.name, result
    except NotImplementedError:
        if not fallback_to_mock or isinstance(chosen, MockMeetingProvider):
            raise
        mock = MockMeetingProvider()
        result = MeetingPresenter(mock).present_lesson(
            lesson, topic=topic, start_iso=start_iso,
            duration_min=duration_min, realtime=realtime)
        return f"{chosen.name}->mock", result
