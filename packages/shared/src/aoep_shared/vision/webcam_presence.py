"""Webcam presence and absence tracking for teaching sessions.

Combines face-detection results (from the perception vision provider) with
silhouette detection (``SilhouetteDetector``) to produce a stable,
human-readable presence signal per frame.  The tracker handles:

- **Debouncing** — a single missed frame does not emit an absence event; the
  signal must stay consistently absent for ``absence_threshold_s`` seconds before
  ``on_absent`` fires.
- **Session metrics** — time present, time absent, engagement fraction.
- **Event callbacks** — ``on_absent`` and ``on_return`` fire once per
  transition so the Director / XAI voice agent can respond appropriately.

Presence states
---------------
PRESENT_FACE         face detected (full engagement tracking available)
PRESENT_SILHOUETTE   body blob visible but no face (user looked away or far from camera)
ABSENT               neither face nor silhouette detected for >= absence_threshold_s
WARMING_UP           background model not yet stable (first ~15 frames)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class PresenceState(str, Enum):
    WARMING_UP = "warming_up"
    PRESENT_FACE = "present_face"
    PRESENT_SILHOUETTE = "present_silhouette"
    ABSENT = "absent"


@dataclass
class PresenceFrame:
    """Processed result for a single webcam frame."""
    state: PresenceState
    face_count: int
    silhouette_confidence: float    # 0..1
    attention: float                # 0..1  (face-based; 0.0 when no face)
    expression: Optional[str]       # face-based expression or None
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class PresenceMetrics:
    """Cumulative session metrics."""
    total_frames: int = 0
    frames_face: int = 0
    frames_silhouette: int = 0
    frames_absent: int = 0
    absence_events: int = 0
    return_events: int = 0
    session_start: float = field(default_factory=time.monotonic)
    last_state_change: float = field(default_factory=time.monotonic)

    @property
    def engagement_fraction(self) -> float:
        """Fraction of processed frames where the user's face was visible."""
        if self.total_frames == 0:
            return 0.0
        return self.frames_face / self.total_frames

    @property
    def presence_fraction(self) -> float:
        """Fraction of frames where the user was present (face or silhouette)."""
        if self.total_frames == 0:
            return 0.0
        return (self.frames_face + self.frames_silhouette) / self.total_frames

    @property
    def session_duration_s(self) -> float:
        return time.monotonic() - self.session_start


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class WebcamPresenceTracker:
    """Stateful per-session presence/absence tracker.

    Parameters
    ----------
    absence_threshold_s:
        Seconds without face or silhouette before ``on_absent`` fires.
        Default 5 s (short enough to catch a student stepping away, long enough
        to survive momentary camera noise).
    return_threshold_s:
        Seconds of presence required to confirm the user has returned.
        Default 1 s (one confident frame is enough after a clean return).
    on_absent:
        Callback fired when the user transitions to ABSENT.  Receives the
        ``PresenceMetrics`` snapshot.
    on_return:
        Callback fired when the user returns from ABSENT.  Receives the
        ``PresenceMetrics`` snapshot.
    """

    def __init__(
        self,
        *,
        absence_threshold_s: float = 5.0,
        return_threshold_s: float = 1.0,
        on_absent: Optional[Callable[[PresenceMetrics], None]] = None,
        on_return: Optional[Callable[[PresenceMetrics], None]] = None,
    ) -> None:
        self._absence_threshold = absence_threshold_s
        self._return_threshold = return_threshold_s
        self._on_absent = on_absent
        self._on_return = on_return

        self._state: PresenceState = PresenceState.WARMING_UP
        self._metrics = PresenceMetrics()
        self._last_seen: float = time.monotonic()
        self._absent_since: Optional[float] = None
        self._returned_at: Optional[float] = None
        self._history: List[PresenceFrame] = []

    @property
    def state(self) -> PresenceState:
        return self._state

    @property
    def metrics(self) -> PresenceMetrics:
        return self._metrics

    @property
    def history(self) -> List[PresenceFrame]:
        """Recent frames (last 60 kept)."""
        return self._history

    def update(
        self,
        *,
        face_count: int,
        silhouette_confidence: float,
        attention: float = 0.0,
        expression: Optional[str] = None,
        warming_up: bool = False,
    ) -> PresenceFrame:
        """Integrate a new frame observation into the presence model.

        Parameters
        ----------
        face_count:
            Number of faces detected in the frame by the vision provider.
        silhouette_confidence:
            Confidence score (0..1) from ``SilhouetteDetector``.
        attention:
            Average attention score across detected faces (0 when no face).
        expression:
            Most common expression string from detected faces (or None).
        warming_up:
            True during the first ~15 frames while the background model stabilises.
        """
        now = time.monotonic()
        self._metrics.total_frames += 1

        if warming_up:
            pf = PresenceFrame(
                state=PresenceState.WARMING_UP,
                face_count=face_count,
                silhouette_confidence=silhouette_confidence,
                attention=attention,
                expression=expression,
                timestamp=now,
            )
            self._state = PresenceState.WARMING_UP
            self._append(pf)
            return pf

        has_face = face_count > 0
        # Treat silhouette as meaningful only above a modest threshold.
        has_silhouette = silhouette_confidence >= 0.25

        if has_face:
            raw_state = PresenceState.PRESENT_FACE
            self._metrics.frames_face += 1
        elif has_silhouette:
            raw_state = PresenceState.PRESENT_SILHOUETTE
            self._metrics.frames_silhouette += 1
        else:
            raw_state = PresenceState.ABSENT
            self._metrics.frames_absent += 1

        # ---- Debounced state machine ----
        if raw_state != PresenceState.ABSENT:
            # User appears present.
            self._last_seen = now
            if self._state == PresenceState.ABSENT:
                # Transition immediately on the first confident presence frame.
                # The return_threshold controls how long the state must have been
                # absent before we fire the on_return callback (avoids noise
                # from very brief absence blips).
                self._absent_since = None
                self._state = raw_state
                if self._returned_at is None:
                    self._returned_at = now
                if now - self._returned_at >= self._return_threshold:
                    self._metrics.return_events += 1
                    self._metrics.last_state_change = now
                    self._returned_at = None
                    if self._on_return:
                        self._on_return(self._metrics)
            else:
                self._state = raw_state
                self._absent_since = None
                self._returned_at = None
        else:
            # User appears absent.
            self._returned_at = None
            elapsed_absent = now - self._last_seen
            if elapsed_absent >= self._absence_threshold:
                if self._state != PresenceState.ABSENT:
                    self._absent_since = self._last_seen
                    self._metrics.absence_events += 1
                    self._metrics.last_state_change = now
                    self._state = PresenceState.ABSENT
                    if self._on_absent:
                        self._on_absent(self._metrics)

        pf = PresenceFrame(
            state=self._state,
            face_count=face_count,
            silhouette_confidence=silhouette_confidence,
            attention=attention,
            expression=expression,
            timestamp=now,
        )
        self._append(pf)
        return pf

    def _append(self, pf: PresenceFrame) -> None:
        self._history.append(pf)
        if len(self._history) > 60:
            self._history = self._history[-60:]

    def reset(self) -> None:
        """Reset state (call when session restarts or student re-enrolls)."""
        self._state = PresenceState.WARMING_UP
        self._metrics = PresenceMetrics()
        self._last_seen = time.monotonic()
        self._absent_since = None
        self._returned_at = None
        self._history = []
