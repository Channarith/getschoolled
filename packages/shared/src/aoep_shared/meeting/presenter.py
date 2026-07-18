"""Turn a LessonPlan into a timed PresentationPlan and present it in a meeting."""

from __future__ import annotations

import re
from typing import Optional

from .base import (
    EventFn,
    Meeting,
    MeetingProvider,
    PresentationPlan,
    PresentationResult,
    PresentationStep,
)

DEFAULT_WPM = 125          # human teaching pace (not broadcast-news speed)
DEFAULT_TTS_RATE = "-12%"  # slightly slower neural delivery; feels conversational
_MIN_STEP_SECONDS = 4.0
_PAUSE_PER_SENTENCE_S = 0.55
_PAUSE_PER_COMMA_S = 0.12
_BREATH_EVERY_N_WORDS = 28
_BREATH_SECONDS = 0.35


def estimate_seconds(text: str, *, wpm: int = DEFAULT_WPM) -> float:
    """Estimate spoken duration at a human teaching pace, including idea pauses."""
    raw = text or ""
    words = len(re.findall(r"\S+", raw))
    if words == 0:
        return _MIN_STEP_SECONDS
    speech = words / max(wpm, 60) * 60.0
    sentences = max(1, len(re.findall(r"[.!?]+", raw)))
    commas = len(re.findall(r"[,;:]", raw))
    breaths = words // _BREATH_EVERY_N_WORDS
    pauses = (
        (sentences - 1) * _PAUSE_PER_SENTENCE_S
        + commas * _PAUSE_PER_COMMA_S
        + breaths * _BREATH_SECONDS
    )
    return max(_MIN_STEP_SECONDS, round(speech + pauses, 2))


def build_presentation_plan(lesson, *, wpm: int = DEFAULT_WPM) -> PresentationPlan:
    """Build a timed PresentationPlan from a teaching ``LessonPlan``.

    Duck-typed: ``lesson`` needs ``.title`` and ``.steps`` (each with order,
    kind, title, narration, on_screen_points). Each lesson step becomes one
    presentation slide with an estimated spoken duration.
    """
    steps = []
    for i, ls in enumerate(getattr(lesson, "steps", [])):
        narration = getattr(ls, "narration", "") or ""
        steps.append(PresentationStep(
            order=i,
            kind=getattr(ls, "kind", "segment"),
            heading=getattr(ls, "title", "") or f"Slide {i + 1}",
            narration=narration,
            on_screen_points=list(getattr(ls, "on_screen_points", []) or []),
            est_seconds=estimate_seconds(narration, wpm=wpm),
            slide_index=i,
        ))
    return PresentationPlan(title=getattr(lesson, "title", "Lesson"), steps=steps)


class MeetingPresenter:
    """Convenience: schedule a meeting and present a lesson end-to-end."""

    def __init__(self, provider: MeetingProvider, *, wpm: Optional[int] = None):
        self.provider = provider
        # Prefer the provider's teaching WPM (local/persona) when the caller
        # does not override — otherwise default to a human lecture pace.
        provider_wpm = getattr(provider, "wpm", None)
        self.wpm = int(wpm if wpm is not None else (provider_wpm or DEFAULT_WPM))

    def present_lesson(
        self,
        lesson,
        *,
        topic: Optional[str] = None,
        start_iso: str = "",
        duration_min: Optional[int] = None,
        elapsed_min: float = 0.0,
        on_event: Optional[EventFn] = None,
        realtime: bool = False,
        meeting: Optional[Meeting] = None,
        smart: bool = True,
        rag_search=None,
        profile=None,
        plan: Optional[PresentationPlan] = None,
    ) -> PresentationResult:
        if plan is None:
            if smart:
                from .smart_presenter import build_smart_presentation_plan, corpus_rag_search
                from .presentation_matrix import PresentationProfile
                prof = profile or PresentationProfile.resolve()
                plan = build_smart_presentation_plan(
                    lesson,
                    duration_min=duration_min,
                    elapsed_min=elapsed_min,
                    wpm=self.wpm,
                    rag_search=rag_search or corpus_rag_search,
                    profile=prof,
                )
            else:
                plan = build_presentation_plan(lesson, wpm=self.wpm)
        if meeting is None:
            meeting = self.provider.create_meeting(
                topic or plan.title,
                start_iso=start_iso,
                duration_min=duration_min or plan.est_minutes,
            )
        return self.provider.present(meeting, plan, on_event=on_event, realtime=realtime)
