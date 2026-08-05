"""Webcam monitor: fuse face observations + silhouettes into presence.

One frame carries two independent signals:

- face observations — from the platform's consent-gated YuNet+SFace pipeline
  (the perception service / VisionProvider, or an on-device embedding path).
  Identity matching stays behind the existing consent gate; this package never
  re-implements biometrics.
- silhouette detections — from :class:`SilhouetteDetector`, privacy-preserving
  "a person is here" with no identity at all.

The monitor folds both into the :class:`PresenceMonitor` state machine, so
callers get stable per-participant presence plus the engagement signals
(attention/gaze/expression) the face pipeline already produces. It serves solo
classes (one local participant) and group classes (one track per learner)
identically — the session layer decides how to react.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from .presence import PresenceEvent, PresenceMonitor, PresenceState
from .silhouette import PersonDetection, SilhouetteDetector, summarize

# A face analyzer maps (participant_id, image) -> per-face observations.
# The real wiring uses the perception VisionProvider (consent-gated); tests
# inject stubs. Each observation needs only the fields mirrored below.
FaceAnalyzer = Callable[[str, object], Sequence[object]]


@dataclass
class FrameSignals:
    """What one participant's webcam frame told us."""

    participant_id: str
    face_visible: bool
    person_visible: bool
    face_count: int = 0
    attention: float = 0.0
    gaze_frontal: float = 0.0
    expression: Optional[str] = None
    matched_student_id: Optional[str] = None
    silhouettes: List[PersonDetection] = field(default_factory=list)


@dataclass
class FrameAnalysis:
    """Signals + stable presence transitions for one ingested frame."""

    signals: FrameSignals
    state: PresenceState
    events: List[PresenceEvent] = field(default_factory=list)

    @property
    def participant_id(self) -> str:
        return self.signals.participant_id


class WebcamMonitor:
    """Analyzes webcam frames for solo and group classes.

    Parameters are dependency-injected so the monitor is fully testable
    offline: pass a real :class:`SilhouetteDetector` (or ``None`` to disable
    silhouette analysis) and a ``face_analyzer`` callable (or ``None`` when no
    face pipeline is configured — presence then runs on silhouettes alone).
    """

    def __init__(
        self,
        *,
        silhouette_detector: Optional[SilhouetteDetector] = None,
        face_analyzer: Optional[FaceAnalyzer] = None,
        presence: Optional[PresenceMonitor] = None,
    ) -> None:
        self._silhouette = silhouette_detector
        self._face_analyzer = face_analyzer
        self.presence = presence or PresenceMonitor()

    @classmethod
    def with_vision_provider(
        cls,
        vision,
        *,
        consented_student_ids: Sequence[str] = (),
        silhouette_detector: Optional[SilhouetteDetector] = None,
        presence: Optional[PresenceMonitor] = None,
    ) -> "WebcamMonitor":
        """Wire the platform's consent-gated VisionProvider as the face path.

        ``vision.analyze_image`` enforces the consent + region gates, so
        identity matching here inherits the platform's compliance behavior.
        """

        def _analyze(participant_id: str, image: object):
            try:
                return vision.analyze_image(
                    image, consented_student_ids=consented_student_ids
                )
            except NotImplementedError:
                # Vision backend unreachable in this environment: degrade to
                # silhouette-only presence rather than failing the class.
                return []

        return cls(
            silhouette_detector=silhouette_detector,
            face_analyzer=_analyze,
            presence=presence,
        )

    def analyze_frame(
        self,
        participant_id: str,
        image: object,
        *,
        at: Optional[float] = None,
    ) -> FrameAnalysis:
        """Fold one frame into presence; return signals + transition events."""
        now = time.time() if at is None else float(at)

        observations: Sequence[object] = ()
        if self._face_analyzer is not None:
            observations = self._face_analyzer(participant_id, image) or ()

        face_visible = len(observations) > 0
        attention = 0.0
        gaze = 0.0
        expression: Optional[str] = None
        matched: Optional[str] = None
        if observations:
            best = max(
                observations, key=lambda o: getattr(o, "attention_score", 0.0)
            )
            attention = float(getattr(best, "attention_score", 0.0) or 0.0)
            gaze = float(getattr(best, "gaze_frontal", 0.0) or 0.0)
            expression = getattr(best, "expression", None)
            for obs in observations:
                candidate = getattr(obs, "matched_student_id", None)
                if candidate:
                    matched = candidate
                    break

        summary = summarize(self._silhouette, image)
        person_visible = summary.person_visible or face_visible

        signals = FrameSignals(
            participant_id=participant_id,
            face_visible=face_visible,
            person_visible=person_visible,
            face_count=len(observations),
            attention=attention,
            gaze_frontal=gaze,
            expression=expression,
            matched_student_id=matched,
            silhouettes=summary.detections,
        )
        events = self.presence.observe(
            participant_id,
            face_visible=face_visible,
            person_visible=person_visible,
            at=now,
        )
        return FrameAnalysis(
            signals=signals,
            state=self.presence.state_of(participant_id),
            events=events,
        )

    def snapshot(self) -> dict:
        """Room-wide presence map (participant_id -> state) for broadcast."""
        return self.presence.snapshot()
