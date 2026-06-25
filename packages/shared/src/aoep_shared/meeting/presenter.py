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

DEFAULT_WPM = 150          # spoken words-per-minute used to estimate slide timing
_MIN_STEP_SECONDS = 3.0


def estimate_seconds(text: str, *, wpm: int = DEFAULT_WPM) -> float:
    """Estimate spoken duration of ``text`` at ``wpm`` words per minute."""
    words = len(re.findall(r"\S+", text or ""))
    if words == 0:
        return _MIN_STEP_SECONDS
    return max(_MIN_STEP_SECONDS, round(words / wpm * 60.0, 2))


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

    def __init__(self, provider: MeetingProvider, *, wpm: int = DEFAULT_WPM):
        self.provider = provider
        self.wpm = wpm

    def present_lesson(
        self,
        lesson,
        *,
        topic: Optional[str] = None,
        start_iso: str = "",
        duration_min: Optional[int] = None,
        on_event: Optional[EventFn] = None,
        realtime: bool = False,
        meeting: Optional[Meeting] = None,
    ) -> PresentationResult:
        plan = build_presentation_plan(lesson, wpm=self.wpm)
        if meeting is None:
            meeting = self.provider.create_meeting(
                topic or plan.title,
                start_iso=start_iso,
                duration_min=duration_min or plan.est_minutes,
            )
        return self.provider.present(meeting, plan, on_event=on_event, realtime=realtime)
