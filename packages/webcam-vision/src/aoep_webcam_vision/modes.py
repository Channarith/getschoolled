"""Teaching policies: turn presence events into teaching actions.

Two modes share the :class:`TeachingAction` vocabulary:

- **Theodore (AI-led)** — Theodore is actively teaching (solo 1:1 or a group
  live room). He pauses the lesson when the room is empty (speaking to an
  empty room wastes TTS and confuses recordings), welcomes learners back with
  a where-we-left-off line, and gently nudges a learner who has been
  silhouette-only (person in frame, no face) for a long stretch.
- **Self-teaching** — the learner is working through material alone; nobody is
  narrating. The policy accumulates focus/away stats and offers a recap after
  a long absence instead of pausing anything.

Policies are pure state machines: events + ticks in, actions out. Rendering
(speak via the xAI voice agent, pause the deck, post a room system message) is
the session layer's job, which keeps these unit-testable with no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .presence import (
    EVENT_ABSENT,
    EVENT_PRESENT,
    EVENT_RETURNED,
    EVENT_SILHOUETTE,
    PresenceEvent,
    PresenceState,
)

# Teaching action kinds.
ACTION_SAY = "say"        # speak a line (voice agent / TTS)
ACTION_PAUSE = "pause"    # pause lesson flow (deck advance, narration)
ACTION_RESUME = "resume"  # resume after a pause
ACTION_NUDGE = "nudge"    # gentle engagement nudge (spoken or on-screen)
ACTION_LOG = "log"        # record-only, no user-facing output

# Theodore's voice lines live here so product can wordsmith in one place.
LINE_PAUSE_EMPTY_ROOM = "I'll pause here and wait — we'll pick up the moment you're back."
LINE_WELCOME_BACK = "Welcome back! Let's pick up right where we left off."
LINE_WELCOME_BACK_GROUP = "Welcome back, {name} — we'll catch you up as we go."
LINE_SILHOUETTE_NUDGE = (
    "I can see you're there, but I can't see your face — "
    "turn toward the camera when you can so I can tell how you're doing."
)
LINE_RECAP_OFFER = "You were away for about {minutes} minute{s}. Want a quick recap before we continue?"

# A learner in silhouette-only state this long gets one nudge per stretch.
DEFAULT_SILHOUETTE_NUDGE_AFTER_S = 45.0
# Absences shorter than this get a plain welcome-back, not a recap offer.
DEFAULT_RECAP_AFTER_S = 120.0


@dataclass
class TeachingAction:
    """One thing the teaching layer should do in response to presence."""

    kind: str  # ACTION_* above
    text: str = ""
    reason: str = ""
    participant_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text,
            "reason": self.reason,
            "participant_id": self.participant_id,
        }


class TheodoreTeachingPolicy:
    """AI-led teaching (Theodore) for solo and group classes.

    Pause semantics: Theodore pauses only when EVERY tracked learner is absent
    (a group class continues while at least one learner is present), and
    resumes on the first return.
    """

    mode = "theodore"

    def __init__(
        self,
        *,
        silhouette_nudge_after_s: float = DEFAULT_SILHOUETTE_NUDGE_AFTER_S,
        recap_after_s: float = DEFAULT_RECAP_AFTER_S,
    ) -> None:
        self.silhouette_nudge_after_s = silhouette_nudge_after_s
        self.recap_after_s = recap_after_s
        self.paused = False
        self._states: Dict[str, PresenceState] = {}
        self._silhouette_since: Dict[str, float] = {}
        self._silhouette_nudged: Dict[str, bool] = {}
        self._absent_since: Dict[str, float] = {}

    # --- event intake ------------------------------------------------------ #
    def on_event(
        self,
        event: PresenceEvent,
        *,
        participant_names: Optional[Dict[str, str]] = None,
    ) -> List[TeachingAction]:
        pid = event.participant_id
        actions: List[TeachingAction] = []

        if event.kind == EVENT_ABSENT:
            self._states[pid] = PresenceState.ABSENT
            self._absent_since[pid] = event.at
            self._silhouette_since.pop(pid, None)
            self._silhouette_nudged.pop(pid, None)
            if self._everyone_absent() and not self.paused:
                self.paused = True
                actions.append(
                    TeachingAction(ACTION_PAUSE, reason="room empty")
                )
                actions.append(
                    TeachingAction(
                        ACTION_SAY,
                        text=LINE_PAUSE_EMPTY_ROOM,
                        reason="room empty",
                    )
                )
            actions.append(
                TeachingAction(ACTION_LOG, reason="learner absent", participant_id=pid)
            )
            return actions

        if event.kind == EVENT_RETURNED:
            self._states[pid] = event.state
            away_for = event.at - self._absent_since.pop(pid, event.at)
            if self.paused:
                self.paused = False
                actions.append(TeachingAction(ACTION_RESUME, reason="learner returned"))
            name = (participant_names or {}).get(pid, "")
            if away_for >= self.recap_after_s:
                minutes = max(1, round(away_for / 60.0))
                actions.append(
                    TeachingAction(
                        ACTION_SAY,
                        text=LINE_RECAP_OFFER.format(
                            minutes=minutes, s="s" if minutes != 1 else ""
                        ),
                        reason="long absence",
                        participant_id=pid,
                    )
                )
            elif name and len(self._states) > 1:
                actions.append(
                    TeachingAction(
                        ACTION_SAY,
                        text=LINE_WELCOME_BACK_GROUP.format(name=name),
                        reason="learner returned",
                        participant_id=pid,
                    )
                )
            else:
                actions.append(
                    TeachingAction(
                        ACTION_SAY,
                        text=LINE_WELCOME_BACK,
                        reason="learner returned",
                        participant_id=pid,
                    )
                )
            return actions

        if event.kind == EVENT_SILHOUETTE:
            self._states[pid] = PresenceState.SILHOUETTE
            self._silhouette_since[pid] = event.at
            self._silhouette_nudged[pid] = False
            actions.append(
                TeachingAction(
                    ACTION_LOG, reason="silhouette only (no face)", participant_id=pid
                )
            )
            return actions

        if event.kind == EVENT_PRESENT:
            self._states[pid] = PresenceState.PRESENT
            self._silhouette_since.pop(pid, None)
            self._silhouette_nudged.pop(pid, None)
            if self.paused:
                # Defensive: a face while paused means resume even if the
                # return event was consumed elsewhere.
                self.paused = False
                actions.append(TeachingAction(ACTION_RESUME, reason="learner present"))
            return actions

        return actions

    def tick(self, *, now: float) -> List[TeachingAction]:
        """Periodic check: nudge learners stuck in silhouette-only state."""
        actions: List[TeachingAction] = []
        for pid, since in list(self._silhouette_since.items()):
            if self._states.get(pid) is not PresenceState.SILHOUETTE:
                continue
            if self._silhouette_nudged.get(pid):
                continue
            if now - since >= self.silhouette_nudge_after_s:
                self._silhouette_nudged[pid] = True
                actions.append(
                    TeachingAction(
                        ACTION_NUDGE,
                        text=LINE_SILHOUETTE_NUDGE,
                        reason="prolonged silhouette",
                        participant_id=pid,
                    )
                )
        return actions

    def _everyone_absent(self) -> bool:
        tracked = [s for s in self._states.values()]
        return bool(tracked) and all(s is PresenceState.ABSENT for s in tracked)


class SelfTeachingPolicy:
    """Self-paced learning: focus/away stats + recap offers, no pause control.

    "Focused" means face present; "in room" means face or silhouette. Away
    time accrues only while absent. ``stats()`` feeds the session summary the
    learner (and parents/guardians for kids accounts) can review.
    """

    mode = "self"

    def __init__(self, *, recap_after_s: float = DEFAULT_RECAP_AFTER_S) -> None:
        self.recap_after_s = recap_after_s
        self._focused_s = 0.0
        self._in_room_s = 0.0
        self._away_s = 0.0
        self._away_count = 0
        self._last_tick: Optional[float] = None
        self._state: PresenceState = PresenceState.ABSENT
        self._absent_since: Optional[float] = None

    def on_event(self, event: PresenceEvent) -> List[TeachingAction]:
        self._accrue(event.at)
        actions: List[TeachingAction] = []
        if event.kind == EVENT_ABSENT:
            self._state = PresenceState.ABSENT
            self._absent_since = event.at
            self._away_count += 1
            actions.append(
                TeachingAction(
                    ACTION_LOG, reason="away", participant_id=event.participant_id
                )
            )
        elif event.kind == EVENT_RETURNED:
            away_for = (
                event.at - self._absent_since if self._absent_since is not None else 0.0
            )
            self._state = event.state
            self._absent_since = None
            if away_for >= self.recap_after_s:
                minutes = max(1, round(away_for / 60.0))
                actions.append(
                    TeachingAction(
                        ACTION_NUDGE,
                        text=LINE_RECAP_OFFER.format(
                            minutes=minutes, s="s" if minutes != 1 else ""
                        ),
                        reason="long absence",
                        participant_id=event.participant_id,
                    )
                )
        elif event.kind in (EVENT_PRESENT, EVENT_SILHOUETTE):
            self._state = event.state
        return actions

    def tick(self, *, now: float) -> List[TeachingAction]:
        self._accrue(now)
        return []

    def _accrue(self, now: float) -> None:
        if self._last_tick is not None:
            delta = max(0.0, now - self._last_tick)
            if self._state is PresenceState.PRESENT:
                self._focused_s += delta
                self._in_room_s += delta
            elif self._state is PresenceState.SILHOUETTE:
                self._in_room_s += delta
            else:
                self._away_s += delta
        self._last_tick = now

    def stats(self, *, now: Optional[float] = None) -> dict:
        if now is not None:
            self._accrue(now)
        return {
            "mode": self.mode,
            "focused_s": round(self._focused_s, 3),
            "in_room_s": round(self._in_room_s, 3),
            "away_s": round(self._away_s, 3),
            "away_count": self._away_count,
            "state": self._state.value,
        }
