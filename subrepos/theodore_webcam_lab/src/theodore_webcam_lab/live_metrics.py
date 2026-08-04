from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .types import (
    ClassEvaluation,
    LiveSessionMetricsResponse,
    ParticipantEvaluation,
    ParticipantMetricSeries,
)


@dataclass
class _MetricPoint:
    timestamp_ms: int
    distance_from_camera_m: float | None
    light_quality_score: float
    image_detection_quality_score: float
    expression_behavior_score: float
    microphone_quality_score: float | None
    noise_filter_effectiveness_score: float | None


class LiveMetricsStore:
    """Keeps rolling participant quality metrics for live charting."""

    def __init__(self, max_points: int = 120, max_sessions: int = 512) -> None:
        self._max_points = max_points
        self._max_sessions = max(1, max_sessions)
        self._history: dict[str, dict[str, deque[_MetricPoint]]] = {}
        self._last_eval: dict[str, ClassEvaluation] = {}
        self._last_updated_ms: dict[str, int] = {}

    def _evict_stale_sessions(self, session_id: str) -> None:
        """Keep the most recently updated sessions only, so memory stays bounded."""
        for store in (self._history, self._last_eval, self._last_updated_ms):
            if session_id in store:
                store[session_id] = store.pop(session_id)
        while len(self._history) > self._max_sessions:
            oldest = next(iter(self._history))
            self._history.pop(oldest, None)
            self._last_eval.pop(oldest, None)
            self._last_updated_ms.pop(oldest, None)

    def record(
        self, *, session_id: str, evaluation: ClassEvaluation, updated_at_ms: int
    ) -> None:
        participant_history = self._history.setdefault(session_id, {})
        for participant in evaluation.participants:
            bucket = participant_history.setdefault(
                participant.participant_id, deque(maxlen=self._max_points)
            )
            bucket.append(
                _MetricPoint(
                    timestamp_ms=updated_at_ms,
                    distance_from_camera_m=participant.distance_from_camera_m,
                    light_quality_score=participant.light_quality_score,
                    image_detection_quality_score=participant.image_detection_quality_score,
                    expression_behavior_score=participant.expression_behavior_score,
                    microphone_quality_score=participant.microphone_quality_score,
                    noise_filter_effectiveness_score=participant.noise_filter_effectiveness_score,
                )
            )
        self._last_eval[session_id] = evaluation
        self._last_updated_ms[session_id] = updated_at_ms
        self._evict_stale_sessions(session_id)

    @staticmethod
    def _series(values: list[float | None]) -> list[float | None]:
        """Keep one entry per recorded frame so every series lines up with timestamps_ms.

        Missing samples stay None (rendered as a gap) instead of being dropped, which
        would shift later points onto the wrong timestamp in the charts.
        """
        return [None if value is None else round(value, 4) for value in values]

    @staticmethod
    def _window_index_for(
        participant: ParticipantEvaluation, evaluation: ClassEvaluation
    ) -> int:
        for window in evaluation.group_student_windows:
            if window.participant_id == participant.participant_id:
                return window.window_index
        for idx, row in enumerate(evaluation.participants, start=1):
            if row.participant_id == participant.participant_id:
                return idx
        return 1

    def snapshot(self, session_id: str) -> LiveSessionMetricsResponse:
        if session_id not in self._last_eval:
            raise KeyError(session_id)
        evaluation = self._last_eval[session_id]
        history = self._history.get(session_id, {})
        participant_series: list[ParticipantMetricSeries] = []
        for participant in evaluation.participants:
            points = list(history.get(participant.participant_id, []))
            participant_series.append(
                ParticipantMetricSeries(
                    participant_id=participant.participant_id,
                    window_index=self._window_index_for(participant, evaluation),
                    timestamps_ms=[point.timestamp_ms for point in points],
                    distance_from_camera_m=self._series(
                        [point.distance_from_camera_m for point in points]
                    ),
                    light_quality_score=self._series(
                        [point.light_quality_score for point in points]
                    ),
                    image_detection_quality_score=self._series(
                        [point.image_detection_quality_score for point in points]
                    ),
                    expression_behavior_score=self._series(
                        [point.expression_behavior_score for point in points]
                    ),
                    microphone_quality_score=self._series(
                        [point.microphone_quality_score for point in points]
                    ),
                    noise_filter_effectiveness_score=self._series(
                        [point.noise_filter_effectiveness_score for point in points]
                    ),
                    latest=participant,
                )
            )
        return LiveSessionMetricsResponse(
            session_id=session_id,
            updated_at_ms=self._last_updated_ms.get(session_id, 0),
            mode=evaluation.mode,
            training_paused=evaluation.training_paused,
            pause_reason=evaluation.pause_reason,
            quality_summary=evaluation.quality_summary,
            lesson_alerts=evaluation.lesson_alerts,
            participants=participant_series,
        )
