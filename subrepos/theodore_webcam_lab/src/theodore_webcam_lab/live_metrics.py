from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

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
    engagement_index: float | None = None
    fatigue_score: float | None = None
    confusion_score: float | None = None
    multitask_score: float | None = None
    flow_score: float | None = None
    boredom_score: float | None = None
    eval_latency_ms: float | None = None


@dataclass
class StoredFrameBatch:
    """Last evaluate inputs for a session — enough to re-score after a tuning change."""

    mode: ClassMode
    signals: list[WebcamSignal]
    expected_participant_ids: list[str]
    updated_at_ms: int


def _adv_float(adv: dict[str, Any] | None, key: str) -> float | None:
    if not adv:
        return None
    raw = adv.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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
        self._eval_latency_ms: dict[str, float] = {}
        self._frame_count: dict[str, int] = {}
        self._last_record_wall_ms: dict[str, float] = {}

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
            self._eval_latency_ms,
            self._frame_count,
            self._last_record_wall_ms,
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
            self._eval_latency_ms.pop(oldest, None)
            self._frame_count.pop(oldest, None)
            self._last_record_wall_ms.pop(oldest, None)

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
        wall_now = time.time() * 1000.0
        prev_wall = self._last_record_wall_ms.get(session_id)
        if prev_wall is not None:
            self._eval_latency_ms[session_id] = max(0.0, wall_now - prev_wall)
        self._last_record_wall_ms[session_id] = wall_now
        self._frame_count[session_id] = self._frame_count.get(session_id, 0) + 1

        participant_history = self._history.setdefault(session_id, {})
        for participant in evaluation.participants:
            bucket = participant_history.setdefault(
                participant.participant_id, deque(maxlen=self._max_points)
            )
            if replace_latest and bucket:
                bucket.pop()
            adv = participant.advanced_behavior if isinstance(
                participant.advanced_behavior, dict
            ) else None
            bucket.append(
                _MetricPoint(
                    timestamp_ms=updated_at_ms,
                    distance_from_camera_m=participant.distance_from_camera_m,
                    light_quality_score=participant.light_quality_score,
                    image_detection_quality_score=participant.image_detection_quality_score,
                    expression_behavior_score=participant.expression_behavior_score,
                    microphone_quality_score=participant.microphone_quality_score,
                    noise_filter_effectiveness_score=participant.noise_filter_effectiveness_score,
                    engagement_index=_adv_float(adv, "engagement_index"),
                    fatigue_score=_adv_float(adv, "fatigue_score"),
                    confusion_score=_adv_float(adv, "confusion_score"),
                    multitask_score=_adv_float(adv, "multitask_score"),
                    flow_score=_adv_float(adv, "flow_score"),
                    boredom_score=_adv_float(adv, "boredom_score"),
                    eval_latency_ms=self._eval_latency_ms.get(session_id),
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

    def build_observatory_summary(self, session_id: str) -> dict[str, object]:
        """Emit ≥20 named telemetry keys for dashboards / promotion gates."""
        evaluation = self._last_eval.get(session_id)
        if evaluation is None:
            return {}
        qs = evaluation.quality_summary
        history = self._history.get(session_id, {})
        points_total = sum(len(bucket) for bucket in history.values())
        eng: list[float] = []
        fat: list[float] = []
        conf: list[float] = []
        multi: list[float] = []
        flow: list[float] = []
        labels: dict[str, int] = {}
        for participant in evaluation.participants:
            adv = participant.advanced_behavior if isinstance(
                participant.advanced_behavior, dict
            ) else {}
            for key, bucket in (
                ("engagement_index", eng),
                ("fatigue_score", fat),
                ("confusion_score", conf),
                ("multitask_score", multi),
                ("flow_score", flow),
            ):
                val = _adv_float(adv, key)
                if val is not None:
                    bucket.append(val)
            label = str(adv.get("observatory_label") or participant.behavior_label or "unknown")
            labels[label] = labels.get(label, 0) + 1

        def _avg(vals: list[float]) -> float | None:
            return round(sum(vals) / len(vals), 4) if vals else None

        latency = self._eval_latency_ms.get(session_id)
        frames = self._frame_count.get(session_id, 0)
        composite_parts = [
            qs.avg_light_quality_score,
            qs.avg_image_detection_quality_score,
            qs.avg_expression_behavior_score,
            qs.avg_recognition_confidence,
        ]
        if qs.avg_microphone_quality_score is not None:
            composite_parts.append(qs.avg_microphone_quality_score)
        composite = round(sum(composite_parts) / max(len(composite_parts), 1), 4)

        return {
            "participants_count": qs.participants_count,
            "frames_recorded": frames,
            "series_points_total": points_total,
            "avg_light_quality_score": qs.avg_light_quality_score,
            "avg_image_detection_quality_score": qs.avg_image_detection_quality_score,
            "avg_expression_behavior_score": qs.avg_expression_behavior_score,
            "avg_microphone_quality_score": qs.avg_microphone_quality_score,
            "avg_noise_filter_effectiveness_score": qs.avg_noise_filter_effectiveness_score,
            "avg_recognition_confidence": qs.avg_recognition_confidence,
            "avg_distance_from_camera_m": qs.avg_distance_from_camera_m,
            "avg_engagement_index": _avg(eng),
            "avg_fatigue_score": _avg(fat),
            "avg_confusion_score": _avg(conf),
            "avg_multitask_score": _avg(multi),
            "avg_flow_score": _avg(flow),
            "absent_count": len(evaluation.absent_participant_ids),
            "silhouette_count": len(evaluation.silhouette_participant_ids),
            "suspected_cheating_count": len(evaluation.suspected_cheating_participant_ids),
            "happy_count": len(evaluation.happy_participant_ids),
            "lesson_alert_count": len(evaluation.lesson_alerts),
            "class_alert_count": len(evaluation.alerts),
            "training_paused": evaluation.training_paused,
            "no_one_present_for_ms": evaluation.no_one_present_for_ms,
            "eval_interval_ms": round(latency, 2) if latency is not None else None,
            "composite_quality_score": composite,
            "quality_flag_counts": dict(qs.quality_flag_counts),
            "observatory_label_counts": labels,
            "expression_counts": dict(evaluation.expression_counts),
            "acknowledged_alert_count": len(self._acknowledged.get(session_id, set())),
            "mode": evaluation.mode.value if hasattr(evaluation.mode, "value") else str(evaluation.mode),
        }

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
            observatory = self.build_observatory_summary(session_id)
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
                    engagement_index=self._series(
                        [point.engagement_index for point in points]
                    ),
                    fatigue_score=self._series(
                        [point.fatigue_score for point in points]
                    ),
                    confusion_score=self._series(
                        [point.confusion_score for point in points]
                    ),
                    multitask_score=self._series(
                        [point.multitask_score for point in points]
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
            observatory_summary=observatory,
        )
