from __future__ import annotations

from dataclasses import dataclass

from .types import (
    ClassEvaluation,
    ClassMode,
    ParticipantEvaluation,
    PresenceState,
    WebcamSignal,
)

_EXPRESSION_ALIASES = {
    "happy": "happy",
    "joy": "happy",
    "joyful": "happy",
    "smile": "happy",
    "smiling": "happy",
    "neutral": "neutral",
    "calm": "neutral",
    "sad": "sad",
    "upset": "sad",
    "angry": "angry",
    "mad": "angry",
    "surprised": "surprised",
    "surprise": "surprised",
    "fearful": "fearful",
    "fear": "fearful",
    "disgusted": "disgusted",
    "disgust": "disgusted",
    "confused": "confused",
    "confusion": "confused",
    "tired": "tired",
    "sleepy": "tired",
    "drowsy": "tired",
}


@dataclass
class AnalyzerPolicy:
    absence_grace_ms: int = 90_000
    silhouette_foreground_threshold: float = 0.95
    silhouette_motion_threshold: float = 0.08
    silhouette_consecutive_frames: int = 3
    solo_max_faces: int = 1


@dataclass
class _ParticipantState:
    last_live_timestamp_ms: int | None = None
    absent_since_ms: int | None = None
    silhouette_streak: int = 0


class WebcamSessionAnalyzer:
    """Stateful analyzer for solo/group webcam teaching sessions."""

    def __init__(self, policy: AnalyzerPolicy | None = None) -> None:
        self._policy = policy or AnalyzerPolicy()
        self._state: dict[str, dict[str, _ParticipantState]] = {}

    def evaluate(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        signals: list[WebcamSignal],
        expected_participant_ids: list[str] | None = None,
    ) -> ClassEvaluation:
        expected = {p.strip() for p in (expected_participant_ids or []) if p.strip()}
        if not signals and not expected:
            return ClassEvaluation(
                session_id=session_id,
                mode=mode,
                participants=[],
                absent_participant_ids=[],
                silhouette_participant_ids=[],
                happy_participant_ids=[],
                expression_counts={},
                alerts=["no_signals_received"],
            )

        class_alerts: list[str] = []
        now_ms = max([s.timestamp_ms for s in signals], default=0)
        if mode is ClassMode.SOLO and len(signals) > 1:
            class_alerts.append("solo_mode_expected_single_signal")

        # Add synthetic missing signals for expected participants without a heartbeat.
        seen = {s.participant_id for s in signals}
        for participant_id in sorted(expected - seen):
            signals.append(
                WebcamSignal(
                    participant_id=participant_id,
                    timestamp_ms=now_ms,
                    face_count=0,
                    liveness_state="missing",
                    foreground_ratio=0.0,
                    motion_score=0.0,
                )
            )

        evaluations: list[ParticipantEvaluation] = []
        for signal in sorted(signals, key=lambda item: item.participant_id):
            evaluations.append(
                self._evaluate_signal(
                    session_id=session_id,
                    mode=mode,
                    signal=signal,
                )
            )

        absent_participant_ids = sorted(
            e.participant_id for e in evaluations if e.state is PresenceState.ABSENT
        )
        silhouette_participant_ids = sorted(
            e.participant_id for e in evaluations if e.silhouette_detected
        )
        happy_participant_ids = sorted(
            e.participant_id for e in evaluations if e.dominant_expression == "happy"
        )
        expression_counts: dict[str, int] = {}
        for participant in evaluations:
            if participant.dominant_expression == "unknown":
                continue
            expression_counts[participant.dominant_expression] = (
                expression_counts.get(participant.dominant_expression, 0) + 1
            )
        for participant in evaluations:
            class_alerts.extend(participant.alerts)

        return ClassEvaluation(
            session_id=session_id,
            mode=mode,
            participants=evaluations,
            absent_participant_ids=absent_participant_ids,
            silhouette_participant_ids=silhouette_participant_ids,
            happy_participant_ids=happy_participant_ids,
            expression_counts=expression_counts,
            alerts=class_alerts,
        )

    @staticmethod
    def _normalize_expression(raw: str) -> str:
        key = (raw or "").strip().lower()
        if not key:
            return "unknown"
        return _EXPRESSION_ALIASES.get(key, "unknown")

    def _evaluate_signal(
        self, *, session_id: str, mode: ClassMode, signal: WebcamSignal
    ) -> ParticipantEvaluation:
        room_state = self._state.setdefault(session_id, {})
        participant_state = room_state.setdefault(signal.participant_id, _ParticipantState())
        alerts: list[str] = []

        liveness = signal.liveness_state.strip().lower()
        has_live_face = signal.face_count > 0 and liveness not in {"spoof", "fake"}
        dominant_expression = self._normalize_expression(signal.expression_label)
        silhouette_candidate = (
            signal.face_count == 0
            and signal.foreground_ratio >= self._policy.silhouette_foreground_threshold
            and signal.motion_score <= self._policy.silhouette_motion_threshold
        )

        if silhouette_candidate:
            participant_state.silhouette_streak += 1
        else:
            participant_state.silhouette_streak = 0
        silhouette_detected = (
            participant_state.silhouette_streak >= self._policy.silhouette_consecutive_frames
        )

        reason = "live_face_detected"
        absent_for_ms = 0
        state = PresenceState.PRESENT
        if has_live_face:
            participant_state.last_live_timestamp_ms = signal.timestamp_ms
            participant_state.absent_since_ms = None
        else:
            reason = "no_live_face"
            if participant_state.last_live_timestamp_ms is None:
                participant_state.last_live_timestamp_ms = signal.timestamp_ms
            missing_for = max(
                0, signal.timestamp_ms - (participant_state.last_live_timestamp_ms or 0)
            )
            if missing_for >= self._policy.absence_grace_ms:
                if participant_state.absent_since_ms is None:
                    participant_state.absent_since_ms = (
                        participant_state.last_live_timestamp_ms
                        + self._policy.absence_grace_ms
                    )
                state = PresenceState.ABSENT
                absent_for_ms = max(
                    0, signal.timestamp_ms - (participant_state.absent_since_ms or 0)
                )
                reason = "absence_grace_exceeded"
            else:
                state = PresenceState.TEMPORARILY_MISSING
                reason = "missing_within_grace_period"

        if silhouette_detected:
            alerts.append(f"silhouette_detected:{signal.participant_id}")
        if mode is ClassMode.SOLO and signal.face_count > self._policy.solo_max_faces:
            alerts.append(f"solo_mode_multiple_faces:{signal.participant_id}")
        if dominant_expression != "unknown":
            alerts.append(f"expression:{signal.participant_id}:{dominant_expression}")

        return ParticipantEvaluation(
            participant_id=signal.participant_id,
            state=state,
            silhouette_detected=silhouette_detected,
            silhouette_streak=participant_state.silhouette_streak,
            face_count=signal.face_count,
            absent_for_ms=absent_for_ms,
            last_live_timestamp_ms=participant_state.last_live_timestamp_ms,
            dominant_expression=dominant_expression,
            expression_confidence=signal.expression_confidence,
            reason=reason,
            alerts=alerts,
        )
