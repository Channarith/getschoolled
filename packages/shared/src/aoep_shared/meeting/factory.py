"""Select a meeting provider by name/env, with offline fallback to Mock."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import MeetingProvider
from .providers import (
    GoogleMeetProvider,
    LocalPlayMeetingProvider,
    MockMeetingProvider,
    SyncedHybridMeetingProvider,
    TeamsProvider,
    ZoomProvider,
)

_PROVIDERS = {
    "mock": MockMeetingProvider,
    "local": LocalPlayMeetingProvider,
    "play": LocalPlayMeetingProvider,
    "google_meet": GoogleMeetProvider,
    "googlemeet": GoogleMeetProvider,
    "meet": GoogleMeetProvider,
    "zoom": ZoomProvider,
    "teams": TeamsProvider,
    "msteams": TeamsProvider,
}

_REAL_PROVIDERS = frozenset({"google_meet", "googlemeet", "meet", "zoom", "teams", "msteams"})


def build_meeting_provider(name: Optional[str] = None, **kwargs) -> MeetingProvider:
    """Build a provider by name (or ``MEETING_PROVIDER`` env; default mock)."""
    key = (name or os.environ.get("MEETING_PROVIDER", "mock")).strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"unknown meeting provider {name!r}; one of {sorted(set(_PROVIDERS))}")
    if cls is LocalPlayMeetingProvider and kwargs:
        return cls(**kwargs)
    return cls()


def present_with_provider(
    lesson,
    *,
    provider: Optional[str] = None,
    topic: Optional[str] = None,
    start_iso: str = "",
    duration_min: Optional[int] = None,
    elapsed_min: float = 0.0,
    realtime: bool = False,
    smart: bool = True,
    fallback_to_mock: bool = True,
    presentation_mode=None,
    speak: bool = True,
    voice: str = "",
    tts_engine: str = "auto",
    sync_slides: bool = True,
    open_meeting: bool = False,
    slide_dir=None,
    course_title: str = "",
    course_slides=None,
    language: str = "en",
    plan=None,
    persona=None,
    slide_source=None,
    theme=None,
    course_dir=None,
    repo_root=None,
    voice_sample=None,
):
    """Schedule + present ``lesson`` with the requested provider.

    Falls back to the Mock provider when the requested real provider has no
    credentials (raises NotImplementedError) - so a demo/test always completes.
    Returns ``(provider_used, PresentationResult)``.
    """
    from .presenter import MeetingPresenter
    from .presentation_matrix import PresentationProfile
    from .presenter_personas import resolve_persona

    persona_obj = resolve_persona(persona, repo_root=repo_root) if persona else None
    if persona_obj and presentation_mode is None and persona_obj.present_mode:
        presentation_mode = persona_obj.present_mode
    profile = PresentationProfile.resolve(presentation_mode) if presentation_mode is not None else None
    voice_resolved = voice or (persona_obj.voice if persona_obj else "")
    language_resolved = language
    tts_rate = "+0%"
    wpm = 150
    voice_sample_path: Optional[Path] = Path(voice_sample) if voice_sample else None
    elevenlabs_voice_id = ""
    if persona_obj:
        if not voice:
            voice_resolved = persona_obj.voice
        language_resolved = persona_obj.language or language
        tts_rate = persona_obj.tts_rate
        wpm = max(80, int(150 * persona_obj.wpm_factor))
        from .voice_profiles import get_voice_profile, parse_voice_token

        _hint, pid = parse_voice_token(persona_obj.voice)
        if pid:
            vprof = get_voice_profile(pid, repo_root=Path(repo_root) if repo_root else None)
            if vprof:
                if voice_sample_path is None:
                    try:
                        voice_sample_path = vprof.resolved_sample(
                            repo_root=Path(repo_root) if repo_root else None,
                        )
                    except FileNotFoundError:
                        pass
                elevenlabs_voice_id = vprof.elevenlabs_voice_id or ""
    provider_name = (provider or os.environ.get("MEETING_PROVIDER", "local")).strip().lower()
    local_kw = dict(
        speak=speak,
        voice=voice_resolved,
        wpm=wpm,
        language=language_resolved,
        tts_engine=tts_engine,
        sync_slides=sync_slides,
        open_slides=True,
        slide_dir=slide_dir,
        course_title=course_title,
        course_slides=course_slides or [],
        plan=plan,
        open_meeting=open_meeting,
        slide_source=slide_source,
        tts_rate=tts_rate,
        theme=theme,
        course_dir=course_dir,
        repo_root=repo_root,
        voice_sample=voice_sample_path,
        elevenlabs_voice_id=elevenlabs_voice_id,
    )

    use_hybrid = sync_slides and provider_name in _REAL_PROVIDERS
    if use_hybrid:
        inner = build_meeting_provider(provider_name)
        chosen = SyncedHybridMeetingProvider(inner, **local_kw)
    elif provider_name in ("local", "play"):
        chosen = LocalPlayMeetingProvider(**local_kw)
    else:
        chosen = build_meeting_provider(provider_name)
    presenter = MeetingPresenter(chosen)
    try:
        result = presenter.present_lesson(
            lesson, topic=topic, start_iso=start_iso,
            duration_min=duration_min, elapsed_min=elapsed_min,
            realtime=realtime, smart=smart, profile=profile,
            plan=plan,
        )
        return chosen.name, result
    except NotImplementedError:
        if not fallback_to_mock or isinstance(chosen, MockMeetingProvider):
            raise
        mock = LocalPlayMeetingProvider(**local_kw) if sync_slides else MockMeetingProvider()
        result = MeetingPresenter(mock).present_lesson(
            lesson, topic=topic, start_iso=start_iso,
            duration_min=duration_min, elapsed_min=elapsed_min,
            realtime=realtime, smart=smart, profile=profile,
            plan=plan,
        )
        return f"{provider_name}->local", result
