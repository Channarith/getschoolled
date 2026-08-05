"""Grace-window absence tracking for webcam presence decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .signals import (
    ClassMode,
    PresenceDecision,
    WebcamFrameObservation,
    evaluate_presence,
    mode_policy,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AbsenceState:
    participant_id: str
    absent_since: datetime | None = None
    last_present_at: datetime | None = None
    hold_active: bool = False
    hold_started_at: datetime | None = None
    reason: str = ""


@dataclass
class AbsenceTracker:
    """Stateful helper that mirrors live-room presence holds in a private lab."""

    mode: ClassMode
    states: dict[str, AbsenceState] = field(default_factory=dict)

    def update(self, frame: WebcamFrameObservation) -> tuple[PresenceDecision, AbsenceState]:
        policy = mode_policy(self.mode)
        decision = evaluate_presence(frame, mode=self.mode, policy=policy)
        observed_at = frame.observed_at or _now()
        state = self.states.get(frame.participant_id)
        if state is None:
            state = AbsenceState(participant_id=frame.participant_id)
            self.states[frame.participant_id] = state

        if decision.liveness_state == "live" and decision.present:
            state.last_present_at = observed_at
            state.absent_since = None
            state.hold_active = False
            state.hold_started_at = None
            state.reason = decision.reason
            return decision, state

        if state.absent_since is None:
            state.absent_since = observed_at
        state.reason = decision.reason

        grace = timedelta(seconds=policy.absence_grace_seconds)
        if (
            policy.pause_on_absence
            and observed_at - state.absent_since >= grace
        ):
            state.hold_active = True
            if state.hold_started_at is None:
                state.hold_started_at = observed_at
        return decision, state

    def should_hold(self, participant_id: str) -> bool:
        state = self.states.get(participant_id)
        return bool(state and state.hold_active)
