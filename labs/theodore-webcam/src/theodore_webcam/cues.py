"""Teaching cues: what Theodore does when presence changes.

A cue pairs a lesson-control action with the line Theodore should actually say.
The important rule encoded here is that Theodore does not narrate to an empty
chair: cues raised while the learner is gone carry ``voice_turn=False``, so the
voice agent stays silent and the recap is delivered on return instead.

Solo self-teaching and group classes diverge deliberately. Solo pauses the
lesson for one learner; a group class keeps running for everyone else and only
holds when attendance drops under quorum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .presence import PresenceEvent, PresenceEventKind


class ClassMode(str, Enum):
    SOLO = "solo"
    GROUP = "group"


class CueAction(str, Enum):
    CONTINUE = "continue"
    PAUSE_LESSON = "pause_lesson"
    RESUME_LESSON = "resume_lesson"
    RECAP = "recap"
    NUDGE = "nudge"
    HOLD_CLASS = "hold_class"
    RELEASE_HOLD = "release_hold"
    MARK_NO_SHOW = "mark_no_show"


@dataclass(frozen=True)
class Cue:
    action: CueAction
    kind: str
    headline: str
    speech: str
    participant_id: str
    severity: str = "info"
    voice_turn: bool = False
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "action": self.action.value,
            "kind": self.kind,
            "headline": self.headline,
            "speech": self.speech,
            "participant_id": self.participant_id,
            "severity": self.severity,
            "voice_turn": self.voice_turn,
            "meta": dict(self.meta),
        }


def _humanize(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{int(round(seconds))} seconds"
    minutes = seconds / 60.0
    if minutes < 2:
        return "about a minute"
    return f"about {int(round(minutes))} minutes"


class CuePolicy:
    """Turns presence events into lesson actions plus Theodore's spoken line."""

    def __init__(self, *, recap_after_absence_seconds: float = 20.0) -> None:
        self.recap_after_absence_seconds = recap_after_absence_seconds

    def for_event(
        self,
        event: PresenceEvent,
        *,
        mode: ClassMode,
        participant_id: str,
        display_name: str,
        lesson_title: str,
        checkpoint: str = "",
    ) -> List[Cue]:
        who = display_name or participant_id
        spot = checkpoint or lesson_title or "where we left off"

        if event.kind is PresenceEventKind.ARRIVED:
            if mode is ClassMode.SOLO:
                return [
                    Cue(
                        action=CueAction.RESUME_LESSON,
                        kind="arrived",
                        headline=f"{who} is at the camera",
                        speech=(
                            f"Good to see you, {who}. Let's pick up "
                            f"{lesson_title or 'the lesson'}."
                        ),
                        participant_id=participant_id,
                        voice_turn=True,
                    )
                ]
            return [
                Cue(
                    action=CueAction.CONTINUE,
                    kind="arrived",
                    headline=f"{who} joined on camera",
                    speech=f"Welcome in, {who}.",
                    participant_id=participant_id,
                    voice_turn=True,
                )
            ]

        if event.kind is PresenceEventKind.DEPARTED:
            if mode is ClassMode.SOLO:
                return [
                    Cue(
                        action=CueAction.PAUSE_LESSON,
                        kind="departed",
                        headline=f"{who} stepped away — lesson paused",
                        speech=(
                            f"I've paused at {spot}. Take your time, "
                            "I'll wait right here."
                        ),
                        participant_id=participant_id,
                        severity="warn",
                        voice_turn=False,
                        meta={"checkpoint": spot},
                    )
                ]
            return [
                Cue(
                    action=CueAction.NUDGE,
                    kind="departed",
                    headline=f"{who} stepped away — class continues",
                    speech=(
                        f"{who}, I'll catch you up on {spot} when you're back."
                    ),
                    participant_id=participant_id,
                    severity="warn",
                    voice_turn=False,
                    meta={"checkpoint": spot},
                )
            ]

        if event.kind is PresenceEventKind.PROLONGED_ABSENCE:
            away = _humanize(event.absence_seconds)
            action = (
                CueAction.PAUSE_LESSON if mode is ClassMode.SOLO else CueAction.NUDGE
            )
            return [
                Cue(
                    action=action,
                    kind="prolonged_absence",
                    headline=f"{who} away {away} — bookmarked at {spot}",
                    speech=(
                        f"Still holding your place at {spot}. Nothing is lost."
                    ),
                    participant_id=participant_id,
                    severity="warn",
                    voice_turn=False,
                    meta={"checkpoint": spot, "absence_seconds": event.absence_seconds},
                )
            ]

        if event.kind is PresenceEventKind.STALE:
            return [
                Cue(
                    action=(
                        CueAction.PAUSE_LESSON
                        if mode is ClassMode.SOLO
                        else CueAction.NUDGE
                    ),
                    kind="camera_off",
                    headline=f"No camera signal from {who}",
                    speech=(
                        "Your camera stopped sending. I'll hold here until it's back."
                    ),
                    participant_id=participant_id,
                    severity="warn",
                    voice_turn=False,
                )
            ]

        if event.kind is PresenceEventKind.RETURNED:
            away = _humanize(event.absence_seconds)
            wants_recap = event.absence_seconds >= self.recap_after_absence_seconds
            if wants_recap:
                return [
                    Cue(
                        action=CueAction.RECAP,
                        kind="returned",
                        headline=f"{who} is back after {away} — recapping",
                        speech=(
                            f"Welcome back, {who}. You were away {away}. "
                            f"Quick recap of {spot}, then we carry on."
                        ),
                        participant_id=participant_id,
                        voice_turn=True,
                        meta={
                            "checkpoint": spot,
                            "absence_seconds": event.absence_seconds,
                        },
                    ),
                    Cue(
                        action=CueAction.RESUME_LESSON,
                        kind="returned",
                        headline="Lesson resumed",
                        speech="",
                        participant_id=participant_id,
                    ),
                ]
            return [
                Cue(
                    action=CueAction.RESUME_LESSON,
                    kind="returned",
                    headline=f"{who} is back — resuming",
                    speech=f"There you are. Carrying on from {spot}.",
                    participant_id=participant_id,
                    voice_turn=True,
                    meta={"checkpoint": spot},
                )
            ]

        return []

    def for_quorum_change(
        self,
        *,
        held: bool,
        present: int,
        total: int,
        lesson_title: str,
        checkpoint: str = "",
    ) -> Optional[Cue]:
        spot = checkpoint or lesson_title or "this point"
        if held:
            return Cue(
                action=CueAction.HOLD_CLASS,
                kind="attendance_hold",
                headline=f"Attendance hold — {present}/{total} on camera",
                speech=(
                    f"Let's hold at {spot} for a moment while people come back."
                ),
                participant_id="",
                severity="warn",
                voice_turn=True,
                meta={"present": present, "total": total},
            )
        return Cue(
            action=CueAction.RELEASE_HOLD,
            kind="attendance_release",
            headline=f"Quorum restored — {present}/{total} on camera",
            speech="Everyone's back with us. Continuing.",
            participant_id="",
            voice_turn=True,
            meta={"present": present, "total": total},
        )
