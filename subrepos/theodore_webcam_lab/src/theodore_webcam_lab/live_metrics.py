from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from .types import (
    ClassEvaluation,
    ClassMode,
    LiveSessionMetricsResponse,
    ParticipantEvaluation,
    ParticipantMetricSeries,
    WebcamSignal,
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


@dataclass
class StoredFrameBatch:
    """Last evaluate inputs for a session — enough to re-score after a tuning change."""

    mode: ClassMode
    signals: list[WebcamSignal]
    expected_participant_ids: list[str]
    updated_at_ms: int


class LiveMetricsStore:
    """Keeps rolling participant quality metrics for live charting."""

    def __init__(self, max_points: int = 120, max_sessions: int = 512) -> None:
        self._max_points = max_points
        self._max_sessions = max(1, max_sessions)
        self._lock = threading.RLock()
        self._history: dict[str, dict[str, deque[_MetricPoint]]] = {}
        self._last_eval: dict[str, ClassEvaluation] = {}
        self._last_updated_ms: dict[str, int] = {}
        self._acknowledged: dict[str, set[str]] = {}
        self._last_inputs: dict[str, StoredFrameBatch] = {}

    @staticmethod
    def alert_key(code: str, participant_id: str = "") -> str:
        return f"{code}:{participant_id or '-'}"

    def boot_participant(self, *, session_id: str, participant_id: str) -> None:
        """Remove a participant from live metrics so they vanish from the dashboard."""
        with self._lock:
            participant_history = self._history.get(session_id, {})
            participant_history.pop(participant_id, None)
            last_eval = self._last_eval.get(session_id)
            if last_eval is not None:
                def _drop(ids: list[str]) -> list[str]:
                    return [i for i in ids if i != participant_id]
                self._last_eval[session_id] = last_eval.model_copy(update={
                    "participants": [p for p in last_eval.participants if p.participant_id != participant_id],
                    "absent_participant_ids": _drop(last_eval.absent_participant_ids),
                    "silhouette_participant_ids": _drop(last_eval.silhouette_participant_ids),
                    "suspected_cheating_participant_ids": _drop(last_eval.suspected_cheating_participant_ids),
                    "happy_participant_ids": _drop(last_eval.happy_participant_ids),
                    "keyboard_typing_audio_participant_ids": _drop(last_eval.keyboard_typing_audio_participant_ids),
                })
            last_inputs = self._last_inputs.get(session_id)
            if last_inputs is not None:
                self._last_inputs[session_id] = StoredFrameBatch(
                    mode=last_inputs.mode,
                    signals=[s for s in last_inputs.signals if s.participant_id != participant_id],
                    expected_participant_ids=[
                        p for p in last_inputs.expected_participant_ids if p != participant_id
                    ],
                    updated_at_ms=last_inputs.updated_at_ms,
                )
            # Drop stale acknowledged alert keys so a new user with the same ID
            # is not pre-silenced by the previous occupant's acknowledged alerts.
            acked = self._acknowledged.get(session_id)
            if acked:
                stale = {k for k in acked if k.endswith(f":{participant_id}")}
                if stale:
                    self._acknowledged[session_id] = acked - stale

    def acknowledge_alert(
        self, *, session_id: str, code: str, participant_id: str = ""
    ) -> list[str]:
        with self._lock:
            keys = self._acknowledged.setdefault(session_id, set())
            keys.add(self.alert_key(code, participant_id))
            return sorted(keys)

    def remember_inputs(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        signals: list[WebcamSignal],
        expected_participant_ids: list[str] | None = None,
        updated_at_ms: int = 0,
    ) -> None:
        """Cache the last frame batch for tuning re-score without rewriting charts."""
        self._last_inputs[session_id] = StoredFrameBatch(
            mode=mode,
            signals=[item.model_copy(deep=True) for item in signals],
            expected_participant_ids=list(expected_participant_ids or []),
            updated_at_ms=updated_at_ms,
        )
        # Touch LRU order without requiring a full evaluation history entry.
        if session_id in self._last_inputs:
            self._last_inputs[session_id] = self._last_inputs.pop(session_id)

    def stored_inputs(self, session_id: str) -> StoredFrameBatch | None:
        return self._last_inputs.get(session_id)

    def sessions_with_inputs(self) -> list[str]:
        return list(self._last_inputs.keys())

    def has_evaluation(self, session_id: str) -> bool:
        return session_id in self._last_eval

    def _evict_stale_sessions(self, session_id: str) -> None:
        """Keep the most recently updated sessions only, so memory stays bounded."""
        for store in (
            self._history,
            self._last_eval,
            self._last_updated_ms,
            self._acknowledged,
            self._last_inputs,
        ):
            if session_id in store:
                store[session_id] = store.pop(session_id)
        while len(self._history) > self._max_sessions:
            oldest = next(iter(self._history))
            self._history.pop(oldest, None)
            self._last_eval.pop(oldest, None)
            self._last_updated_ms.pop(oldest, None)
            self._acknowledged.pop(oldest, None)
            self._last_inputs.pop(oldest, None)

    def record(
        self,
        *,
        session_id: str,
        evaluation: ClassEvaluation,
        updated_at_ms: int,
        mode: ClassMode | None = None,
        signals: list[WebcamSignal] | None = None,
        expected_participant_ids: list[str] | None = None,
        replace_latest: bool = False,
    ) -> None:
        with self._lock:
            self._record_locked(
                session_id=session_id,
                evaluation=evaluation,
                updated_at_ms=updated_at_ms,
                mode=mode,
                signals=signals,
                expected_participant_ids=expected_participant_ids,
                replace_latest=replace_latest,
            )

    def _record_locked(
        self,
        *,
        session_id: str,
        evaluation: ClassEvaluation,
        updated_at_ms: int,
        mode: ClassMode | None = None,
        signals: list[WebcamSignal] | None = None,
        expected_participant_ids: list[str] | None = None,
        replace_latest: bool = False,
    ) -> None:
        participant_history = self._history.setdefault(session_id, {})
        for participant in evaluation.participants:
            bucket = participant_history.setdefault(
                participant.participant_id, deque(maxlen=self._max_points)
            )
            if replace_latest and bucket:
                bucket.pop()
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
        if signals is not None and mode is not None:
            self._last_inputs[session_id] = StoredFrameBatch(
                mode=mode,
                signals=[item.model_copy(deep=True) for item in signals],
                expected_participant_ids=list(expected_participant_ids or []),
                updated_at_ms=updated_at_ms,
            )
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
        with self._lock:
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
            group_student_windows=list(evaluation.group_student_windows),
            silhouette_participant_ids=list(evaluation.silhouette_participant_ids),
            suspected_cheating_participant_ids=list(
                evaluation.suspected_cheating_participant_ids
            ),
            acknowledged_alert_keys=sorted(self._acknowledged.get(session_id, set())),
            absent_participant_ids=list(evaluation.absent_participant_ids),
            happy_participant_ids=list(evaluation.happy_participant_ids),
            keyboard_typing_audio_participant_ids=list(
                evaluation.keyboard_typing_audio_participant_ids
            ),
            expression_counts=dict(evaluation.expression_counts),
            class_alerts=list(evaluation.alerts),
            no_one_present_for_ms=evaluation.no_one_present_for_ms,
            original_participant_id=evaluation.original_participant_id,
            unexpected_participant_ids=list(evaluation.unexpected_participant_ids),
        )
