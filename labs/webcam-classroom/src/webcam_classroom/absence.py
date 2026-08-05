"""User-absence tracking: a time-based presence state machine.

Consumes a stream of :class:`~webcam_classroom.silhouette.SilhouetteReading`
(plus an optional attention score) over time and produces a stable presence
state per learner, emitting an event on every transition. The class-pacing layer
(:mod:`webcam_classroom.session`) uses these transitions to pause/resume a
Theodore lecture, hold a group class, or nudge a self-teaching learner.

States (monotonically "more absent" as attention/visibility degrade):
  present        - a live silhouette is in view and (if known) attentive
  looking_away   - present but attention has been low for ``looking_away_after``
  briefly_absent - no silhouette for ``brief_absent_after`` (probably stepped out)
  absent         - no silhouette for ``absent_after`` (trigger a hold / long pause)
  unknown        - not enough signal yet

The thresholds are seconds of *sustained* condition, so a single dropped frame
never flips the state - it needs to persist. Recovery to ``present`` is immediate
on the first good reading (a returning learner shouldn't wait).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import WebcamLabConfig
from .silhouette import PRESENT, SilhouetteReading

# Presence states.
PRESENT_STATE = "present"
LOOKING_AWAY = "looking_away"
BRIEFLY_ABSENT = "briefly_absent"
ABSENT = "absent"
UNKNOWN = "unknown"

# States that mean "the learner is not effectively participating right now".
NOT_PARTICIPATING = (BRIEFLY_ABSENT, ABSENT)


@dataclass
class AbsenceEvent:
    """Emitted when a learner's presence state changes."""

    user_id: str
    previous: str
    current: str
    at: float
    reason: str = ""
    coverage: float = 0.0
    attention: Optional[float] = None

    @property
    def became_absent(self) -> bool:
        return self.current in NOT_PARTICIPATING and self.previous not in NOT_PARTICIPATING

    @property
    def returned(self) -> bool:
        # "Returned" means coming back from an away/absent state - not the initial
        # join (unknown -> present), which shouldn't trigger a "welcome back".
        return self.current == PRESENT_STATE and self.previous in (
            LOOKING_AWAY,
            BRIEFLY_ABSENT,
            ABSENT,
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "previous": self.previous,
            "current": self.current,
            "at": round(self.at, 3),
            "reason": self.reason,
            "coverage": round(self.coverage, 4),
            "attention": None if self.attention is None else round(self.attention, 4),
            "became_absent": self.became_absent,
            "returned": self.returned,
        }


@dataclass
class AbsenceConfig:
    looking_away_after: float = 4.0
    brief_absent_after: float = 6.0
    absent_after: float = 20.0
    looking_away_attention: float = 0.35

    @classmethod
    def from_lab(cls, cfg: WebcamLabConfig) -> "AbsenceConfig":
        return cls(
            looking_away_after=cfg.looking_away_after,
            brief_absent_after=cfg.brief_absent_after,
            absent_after=cfg.absent_after,
            looking_away_attention=cfg.looking_away_attention,
        )


class AbsenceTracker:
    """Per-learner presence state machine."""

    def __init__(self, user_id: str = "learner", config: Optional[AbsenceConfig] = None) -> None:
        self.user_id = user_id
        self.config = config or AbsenceConfig()
        self.state: str = UNKNOWN
        self._last_present_at: Optional[float] = None
        self._low_attention_since: Optional[float] = None
        self._absent_since: Optional[float] = None
        self._last_coverage: float = 0.0
        self._last_attention: Optional[float] = None
        self._history: List[AbsenceEvent] = []

    # --- queries ----------------------------------------------------------- #
    def is_present(self) -> bool:
        return self.state == PRESENT_STATE

    def is_absent(self) -> bool:
        return self.state in NOT_PARTICIPATING

    def absent_seconds(self, now: Optional[float] = None) -> float:
        if self._absent_since is None:
            return 0.0
        return max(0.0, (now if now is not None else time.monotonic()) - self._absent_since)

    @property
    def events(self) -> List[AbsenceEvent]:
        return list(self._history)

    # --- update ------------------------------------------------------------ #
    def update(
        self,
        reading: SilhouetteReading,
        *,
        attention: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Optional[AbsenceEvent]:
        """Feed one observation; returns an :class:`AbsenceEvent` on a state change."""
        ts = now if now is not None else time.monotonic()
        self._last_coverage = reading.coverage
        self._last_attention = attention

        visible = reading.present and reading.state == PRESENT

        if visible:
            self._absent_since = None
            self._last_present_at = ts
            if attention is not None and attention < self.config.looking_away_attention:
                if self._low_attention_since is None:
                    self._low_attention_since = ts
                if ts - self._low_attention_since >= self.config.looking_away_after:
                    return self._transition(LOOKING_AWAY, ts, "attention_low", attention)
                # Not yet sustained: hold current state unless we were absent.
                if self.state in (UNKNOWN,) + NOT_PARTICIPATING:
                    return self._transition(PRESENT_STATE, ts, "returned", attention)
                return None
            # Attentive (or attention unknown) and visible -> present.
            self._low_attention_since = None
            if self.state != PRESENT_STATE:
                return self._transition(PRESENT_STATE, ts, "visible", attention)
            return None

        # Not visible: start/continue the absence clock.
        self._low_attention_since = None
        if self._absent_since is None:
            self._absent_since = ts
        elapsed = ts - self._absent_since
        if elapsed >= self.config.absent_after:
            target = ABSENT
        elif elapsed >= self.config.brief_absent_after:
            target = BRIEFLY_ABSENT
        else:
            # Below the brief threshold: a momentary drop. Keep the learner
            # "present" so a single lost frame doesn't pause the class, unless
            # we already were more-absent (don't recover without a good frame).
            target = self.state if self.state in NOT_PARTICIPATING else PRESENT_STATE
        if target != self.state:
            return self._transition(target, ts, reading.state or "no_silhouette", attention)
        return None

    def _transition(
        self, target: str, ts: float, reason: str, attention: Optional[float]
    ) -> AbsenceEvent:
        ev = AbsenceEvent(
            user_id=self.user_id,
            previous=self.state,
            current=target,
            at=ts,
            reason=reason,
            coverage=self._last_coverage,
            attention=attention,
        )
        self.state = target
        self._history.append(ev)
        return ev

    def snapshot(self, now: Optional[float] = None) -> dict:
        return {
            "user_id": self.user_id,
            "state": self.state,
            "present": self.is_present(),
            "absent_seconds": round(self.absent_seconds(now), 2),
            "coverage": round(self._last_coverage, 4),
            "attention": None if self._last_attention is None else round(self._last_attention, 4),
        }


@dataclass
class GroupPresence:
    """Aggregate presence across a group class (one tracker per learner)."""

    config: AbsenceConfig = field(default_factory=AbsenceConfig)
    trackers: Dict[str, AbsenceTracker] = field(default_factory=dict)

    def tracker(self, user_id: str) -> AbsenceTracker:
        t = self.trackers.get(user_id)
        if t is None:
            t = AbsenceTracker(user_id, self.config)
            self.trackers[user_id] = t
        return t

    def update(
        self,
        user_id: str,
        reading: SilhouetteReading,
        *,
        attention: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Optional[AbsenceEvent]:
        return self.tracker(user_id).update(reading, attention=attention, now=now)

    def absent_users(self) -> List[str]:
        return [uid for uid, t in self.trackers.items() if t.is_absent()]

    def present_users(self) -> List[str]:
        return [uid for uid, t in self.trackers.items() if t.is_present()]

    def any_absent(self) -> bool:
        return bool(self.absent_users())

    def all_present(self) -> bool:
        return bool(self.trackers) and all(t.is_present() for t in self.trackers.values())

    def snapshot(self, now: Optional[float] = None) -> dict:
        return {uid: t.snapshot(now) for uid, t in self.trackers.items()}
