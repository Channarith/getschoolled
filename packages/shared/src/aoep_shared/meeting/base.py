"""Meeting + presentation data models and the provider base class.

The base ``MeetingProvider`` owns the provider-agnostic *driving* of a
presentation (open slide -> speak narration -> advance) and records a transcript
+ timed event log. Concrete providers add (a) real meeting creation via their API
and (b) optional media transport by overriding ``_deliver_step``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Meeting:
    provider: str
    meeting_id: str
    topic: str
    join_url: str
    host_url: str = ""
    start_iso: str = ""
    duration_min: int = 30
    offline: bool = False          # True for the mock/simulated provider
    raw: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "provider": self.provider,
            "meeting_id": self.meeting_id,
            "topic": self.topic,
            "join_url": self.join_url,
            "host_url": self.host_url,
            "start_iso": self.start_iso,
            "duration_min": self.duration_min,
            "offline": self.offline,
        }


@dataclass
class PresentationStep:
    order: int
    kind: str                      # intro | segment | outro
    heading: str
    narration: str
    on_screen_points: List[str] = field(default_factory=list)
    est_seconds: float = 0.0
    slide_index: int = 0
    # Smart presenter (spoken script may differ from slide narration).
    spoken_narration: str = ""
    action: str = "speak"          # speak | summarize | skip | fast
    pace_multiplier: float = 1.0
    presenter_meta: str = ""

    def spoken_text(self) -> str:
        return (self.spoken_narration or self.narration or "").strip()

    def to_dict(self) -> Dict:
        d = {
            "order": self.order,
            "kind": self.kind,
            "heading": self.heading,
            "narration": self.narration,
            "on_screen_points": list(self.on_screen_points),
            "est_seconds": round(self.est_seconds, 2),
            "slide_index": self.slide_index,
        }
        if self.spoken_narration:
            d["spoken_narration"] = self.spoken_narration
        if self.action != "speak":
            d["action"] = self.action
        if self.pace_multiplier != 1.0:
            d["pace_multiplier"] = round(self.pace_multiplier, 2)
        if self.presenter_meta:
            d["presenter_meta"] = self.presenter_meta
        return d


@dataclass
class PresentationPlan:
    title: str
    steps: List[PresentationStep] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return round(sum(s.est_seconds for s in self.steps), 2)

    @property
    def est_minutes(self) -> int:
        return max(1, round(self.total_seconds / 60.0))

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "total_seconds": self.total_seconds,
            "est_minutes": self.est_minutes,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class PresentationEvent:
    t: float                       # offset (seconds) from presentation start
    action: str                    # open_slide | speak | advance | end
    step_order: int
    detail: str = ""

    def to_dict(self) -> Dict:
        return {"t": round(self.t, 2), "action": self.action,
                "step_order": self.step_order, "detail": self.detail}


@dataclass
class PresentationResult:
    meeting: Meeting
    plan_title: str
    steps_presented: int
    total_seconds: float
    transcript: str
    events: List[PresentationEvent] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "meeting": self.meeting.to_dict(),
            "plan_title": self.plan_title,
            "steps_presented": self.steps_presented,
            "total_seconds": round(self.total_seconds, 2),
            "events": [e.to_dict() for e in self.events],
            "transcript_chars": len(self.transcript),
        }


# on_event(PresentationEvent) -> None
EventFn = Callable[[PresentationEvent], None]


class MeetingProvider(abc.ABC):
    """Base class: real providers implement ``create_meeting`` (+ optional
    ``_deliver_step`` transport); the shared ``present`` drives the timeline."""

    name: str = "base"
    supports_media_transport: bool = False

    @abc.abstractmethod
    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        """Create/schedule a meeting and return its join coordinates."""

    def _deliver_step(self, meeting: Meeting, step: PresentationStep) -> None:
        """Transport one step's slide+audio into the meeting.

        Default is a no-op (the timeline/transcript is still produced). Real
        providers override this to stream via RTMP / a media bot / virtual
        devices. Kept separate from ``present`` so the driving logic is shared.
        """
        return None

    def _on_speak(self, meeting: Meeting, step: PresentationStep, spoken: str) -> None:
        """Hook after a step's narration is emitted (TTS, captions, etc.)."""
        return None

    def present(self, meeting: Meeting, plan: PresentationPlan, *,
                on_event: Optional[EventFn] = None,
                realtime: bool = False) -> PresentationResult:
        """Drive ``plan`` in ``meeting``: open each slide, speak its narration,
        advance. Emits a timed event log + transcript. ``realtime=True`` sleeps
        for each step's estimated duration (off by default for tests/CI)."""
        import time

        events: List[PresentationEvent] = []
        transcript_parts: List[str] = []
        clock = 0.0

        def emit(action: str, step_order: int, detail: str = "") -> None:
            ev = PresentationEvent(t=clock, action=action, step_order=step_order,
                                   detail=detail)
            events.append(ev)
            if on_event:
                on_event(ev)

        steps_presented = 0
        interrupted = False
        try:
            for step in plan.steps:
                spoken = step.spoken_text()
                if step.action == "skip":
                    emit("skip_slide", step.order, step.heading)
                    if spoken:
                        emit("speak", step.order, spoken[:80])
                        transcript_parts.append(spoken)
                        self._on_speak(meeting, step, spoken)
                    clock += step.est_seconds
                    steps_presented += 1
                    emit("advance", step.order)
                    continue

                emit("open_slide", step.order, step.heading)
                self._deliver_step(meeting, step)
                detail = spoken[:80]
                if step.action in ("summarize", "fast"):
                    detail = f"[{step.action}] {detail}"
                emit("speak", step.order, detail)
                transcript_parts.append(spoken)
                self._on_speak(meeting, step, spoken)
                step_seconds = step.est_seconds
                if step.pace_multiplier > 1.0:
                    step_seconds = max(1.0, step_seconds)
                if realtime and step_seconds > 0:
                    time.sleep(step_seconds / max(step.pace_multiplier, 1.0))
                clock += step_seconds
                steps_presented += 1
                emit("advance", step.order)
        except KeyboardInterrupt:
            interrupted = True
            emit("interrupted", steps_presented, "stopped by user")

        if interrupted:
            emit("end", steps_presented, "presentation stopped")
        else:
            emit("end", len(plan.steps), "presentation complete")
        return PresentationResult(
            meeting=meeting,
            plan_title=plan.title,
            steps_presented=steps_presented,
            total_seconds=clock,
            transcript="\n\n".join(transcript_parts),
            events=events,
        )
