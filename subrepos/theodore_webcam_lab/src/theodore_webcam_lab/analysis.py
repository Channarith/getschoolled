from __future__ import annotations

import os
from dataclasses import dataclass, fields as dc_fields

from .imaging import analyze_luminance_grid
from .vision_tuning import VisionTuning
from .types import (
    ClassEvaluation,
    ClassMode,
    GroupStudentWindowStatus,
    LessonAlert,
    ParticipantEvaluation,
    PresenceState,
    QualitySummary,
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
    gaze_away_grace_ms: int = 45_000
    gaze_frontal_min_threshold: float = 0.35
    gaze_down_min_threshold: float = 0.6
    typing_activity_min_threshold: float = 0.7
    keyboard_typing_audio_min_threshold: float = 0.65
    pause_training_no_presence_ms: int = 4_000
    # Caps retained per-session state so a long-lived server cannot grow without bound.
    max_tracked_sessions: int = 512

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> AnalyzerPolicy:
        """Load timing/session knobs from AOEP_VISION_* environment variables."""
        env = os.environ if environ is None else environ
        overrides: dict[str, object] = {}
        for field_def in dc_fields(cls):
            raw = env.get("AOEP_VISION_" + field_def.name.upper())
            if raw is None or not str(raw).strip():
                continue
            try:
                overrides[field_def.name] = (
                    int(raw) if field_def.type in (int, "int") else float(raw)
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_def.name} must be numeric (got {raw!r})") from exc
        return cls(**overrides)  # type: ignore[arg-type]


@dataclass
class _ParticipantState:
    last_live_timestamp_ms: int | None = None
    absent_since_ms: int | None = None
    silhouette_streak: int = 0
    gaze_away_started_ms: int | None = None


class WebcamSessionAnalyzer:
    """Stateful analyzer for solo/group webcam teaching sessions."""

    def __init__(
        self,
        policy: AnalyzerPolicy | None = None,
        tuning: VisionTuning | None = None,
    ) -> None:
        self._policy = policy or AnalyzerPolicy()
        self._tuning = tuning or VisionTuning()
        self._state: dict[str, dict[str, _ParticipantState]] = {}
        self._no_presence_started_ms: dict[str, int | None] = {}
        self._original_participant_id: dict[str, str] = {}

    @property
    def tuning(self) -> VisionTuning:
        return self._tuning

    @tuning.setter
    def tuning(self, value: VisionTuning) -> None:
        self._tuning = value

    @property
    def policy(self) -> AnalyzerPolicy:
        return self._policy

    def _touch_session(self, session_id: str) -> None:
        """Mark a session as most-recently used and evict the oldest ones past the cap."""
        for store in (self._state, self._no_presence_started_ms, self._original_participant_id):
            if session_id in store:
                store[session_id] = store.pop(session_id)
        limit = max(1, self._policy.max_tracked_sessions)
        while len(self._state) > limit:
            oldest = next(iter(self._state))
            self._state.pop(oldest, None)
            self._no_presence_started_ms.pop(oldest, None)
            self._original_participant_id.pop(oldest, None)

    @staticmethod
    def _clamp01(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _snr_to_quality(self, snr_db: float | None) -> float | None:
        if snr_db is None:
            return None
        tuning = self._tuning
        return self._clamp01((snr_db - tuning.audio_snr_floor_db) / tuning.audio_snr_span_db)

    def _noise_db_to_quality(self, noise_db: float | None) -> float | None:
        if noise_db is None:
            return None
        tuning = self._tuning
        span = tuning.audio_noise_loud_db - tuning.audio_noise_clean_db
        return self._clamp01((tuning.audio_noise_loud_db - noise_db) / span)

    def _estimate_distance_from_face_ratio(self, ratio: float | None) -> float | None:
        """Convert an observed face-box ratio to metres using the calibration knobs."""
        if ratio is None or ratio <= 0.0:
            return None
        tuning = self._tuning
        effective_ratio = max(tuning.distance_min_face_ratio, ratio)
        distance = tuning.distance_reference_metres * (
            tuning.distance_reference_face_ratio / effective_ratio
        )
        distance = min(tuning.distance_max_metres, max(tuning.distance_min_metres, distance))
        return round(distance, 2)

    @staticmethod
    def _avg(values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _avg_optional(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    def evaluate(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        signals: list[WebcamSignal],
        expected_participant_ids: list[str] | None = None,
    ) -> ClassEvaluation:
        expected = {p.strip() for p in (expected_participant_ids or []) if p.strip()}
        # Never mutate the caller's list: synthetic "missing" heartbeats are appended below,
        # and callers legitimately reuse the same list across evaluate() calls.
        signals = list(signals)
        if not signals and not expected:
            return ClassEvaluation(
                session_id=session_id,
                mode=mode,
                participants=[],
                absent_participant_ids=[],
                silhouette_participant_ids=[],
                happy_participant_ids=[],
                keyboard_typing_audio_participant_ids=[],
                suspected_cheating_participant_ids=[],
                no_one_present_for_ms=0,
                training_paused=False,
                pause_reason="",
                original_participant_id="",
                original_user_present=False,
                unexpected_participant_ids=[],
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

        any_live_face_in_frame = any(
            s.face_count > 0 and s.liveness_state.strip().lower() not in {"spoof", "fake"}
            for s in signals
        )
        if any_live_face_in_frame:
            self._no_presence_started_ms[session_id] = None
            no_one_present_for_ms = 0
        else:
            started = self._no_presence_started_ms.get(session_id)
            if started is None:
                started = now_ms
                self._no_presence_started_ms[session_id] = started
            no_one_present_for_ms = max(0, now_ms - started)
        training_paused = no_one_present_for_ms > self._policy.pause_training_no_presence_ms
        pause_reason = "no_learner_detected_over_4s" if training_paused else ""
        if training_paused:
            class_alerts.append("training_paused:no_learner_detected_over_4s")

        live_present_ids = sorted(
            {
                s.participant_id
                for s in signals
                if s.face_count > 0 and s.liveness_state.strip().lower() not in {"spoof", "fake"}
            }
        )
        # The original-learner lock is a solo-session concept. In a group class every
        # enrolled classmate is legitimate, so locking onto the first face seen would
        # wrongly report the rest of the class as unexpected intruders.
        if mode is ClassMode.SOLO:
            original_participant_id = self._original_participant_id.get(session_id, "")
            if not original_participant_id and live_present_ids:
                original_participant_id = live_present_ids[0]
                self._original_participant_id[session_id] = original_participant_id
            original_user_present = bool(
                original_participant_id and original_participant_id in live_present_ids
            )
            unexpected_participant_ids = sorted(
                pid for pid in live_present_ids if pid != original_participant_id
            )
        else:
            original_participant_id = ""
            original_user_present = bool(live_present_ids)
            # Only a roster (expected_participant_ids) can define who is unexpected here.
            unexpected_participant_ids = (
                sorted(pid for pid in live_present_ids if pid not in expected)
                if expected
                else []
            )
        if (
            mode is ClassMode.SOLO
            and original_participant_id
            and live_present_ids
            and not original_user_present
        ):
            training_paused = True
            pause_reason = "original_user_not_present"
            class_alerts.append("training_paused:original_user_not_present")
            if unexpected_participant_ids:
                class_alerts.append(
                    "unexpected_user_present:" + ",".join(unexpected_participant_ids)
                )

        self._state.setdefault(session_id, {})
        self._touch_session(session_id)

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
        keyboard_typing_audio_participant_ids = sorted(
            e.participant_id for e in evaluations if e.keyboard_typing_audio_detected
        )
        suspected_cheating_participant_ids = sorted(
            e.participant_id for e in evaluations if e.suspected_cheating
        )
        distance_values = [
            p.distance_from_camera_m
            for p in evaluations
            if p.distance_from_camera_m is not None
        ]
        mic_quality_values = [
            p.microphone_quality_score
            for p in evaluations
            if p.microphone_quality_score is not None
        ]
        noise_filter_values = [
            p.noise_filter_effectiveness_score
            for p in evaluations
            if p.noise_filter_effectiveness_score is not None
        ]
        quality_flag_counts: dict[str, int] = {}
        for participant in evaluations:
            for flag in participant.quality_flags:
                quality_flag_counts[flag] = quality_flag_counts.get(flag, 0) + 1
        expression_counts: dict[str, int] = {}
        for participant in evaluations:
            if participant.dominant_expression == "unknown":
                continue
            expression_counts[participant.dominant_expression] = (
                expression_counts.get(participant.dominant_expression, 0) + 1
            )
        quality_summary = QualitySummary(
            participants_count=len(evaluations),
            avg_distance_from_camera_m=self._avg_optional(distance_values),
            avg_light_quality_score=self._avg(
                [p.light_quality_score for p in evaluations]
            ),
            avg_image_detection_quality_score=self._avg(
                [p.image_detection_quality_score for p in evaluations]
            ),
            avg_expression_behavior_score=self._avg(
                [p.expression_behavior_score for p in evaluations]
            ),
            avg_microphone_quality_score=self._avg_optional(mic_quality_values),
            avg_noise_filter_effectiveness_score=self._avg_optional(noise_filter_values),
            avg_recognition_confidence=self._avg(
                [p.recognition_confidence for p in evaluations]
            ),
            quality_flag_counts=quality_flag_counts,
        )
        group_student_windows: list[GroupStudentWindowStatus] = []
        lesson_alerts: list[LessonAlert] = []
        if mode is ClassMode.GROUP:
            for index, participant in enumerate(evaluations, start=1):
                severity = "none"
                message = "Student window looks healthy."
                needs_intervention = False
                if participant.suspected_cheating:
                    severity = "high"
                    needs_intervention = True
                    message = (
                        "Possible cheating signals detected; privately message this learner."
                    )
                    lesson_alerts.append(
                        LessonAlert(
                            level="high",
                            code="student_cheating_signal",
                            participant_id=participant.participant_id,
                            message=(
                                f"Possible cheating signals for {participant.participant_id}."
                            ),
                            action="notify_student_privately_and_reinforce_integrity",
                        )
                    )
                elif participant.state is PresenceState.ABSENT:
                    severity = "medium"
                    needs_intervention = True
                    message = "Student appears absent; alert lesson and request rejoin."
                    lesson_alerts.append(
                        LessonAlert(
                            level="medium",
                            code="student_absent",
                            participant_id=participant.participant_id,
                            message=f"{participant.participant_id} is absent from the webcam.",
                            action="alert_lesson_and_request_student_rejoin",
                        )
                    )
                elif participant.state is PresenceState.TEMPORARILY_MISSING:
                    severity = "low"
                    needs_intervention = True
                    message = "Student temporarily missing; watch this window."
                    lesson_alerts.append(
                        LessonAlert(
                            level="low",
                            code="student_temporarily_missing",
                            participant_id=participant.participant_id,
                            message=(
                                f"{participant.participant_id} may have stepped away briefly."
                            ),
                            action="monitor_and_prompt_if_state_persists",
                        )
                    )
                group_student_windows.append(
                    GroupStudentWindowStatus(
                        participant_id=participant.participant_id,
                        window_index=index,
                        state=participant.state,
                        suspected_cheating=participant.suspected_cheating,
                        needs_intervention=needs_intervention,
                        severity=severity,
                        message=message,
                    )
                )
            intervention_count = sum(
                1 for window in group_student_windows if window.needs_intervention
            )
            if intervention_count > 0:
                lesson_alerts.insert(
                    0,
                    LessonAlert(
                        level="medium",
                        code="group_intervention_required",
                        message=(
                            f"{intervention_count} student window(s) need intervention."
                        ),
                        action="review_flagged_windows",
                    ),
                )
                class_alerts.append(
                    f"group_intervention_required:{intervention_count}_window(s)"
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
            keyboard_typing_audio_participant_ids=keyboard_typing_audio_participant_ids,
            suspected_cheating_participant_ids=suspected_cheating_participant_ids,
            no_one_present_for_ms=no_one_present_for_ms,
            training_paused=training_paused,
            pause_reason=pause_reason,
            original_participant_id=original_participant_id,
            original_user_present=original_user_present,
            unexpected_participant_ids=unexpected_participant_ids,
            group_student_windows=group_student_windows,
            lesson_alerts=lesson_alerts,
            quality_summary=quality_summary,
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
        tuning = self._tuning
        gaze_down_score = signal.gaze_down_score if signal.gaze_down_score is not None else 0.0
        gaze_frontal = signal.gaze_frontal if signal.gaze_frontal is not None else 1.0
        eyes_away = (
            signal.face_count > 0
            and (
                gaze_down_score >= self._policy.gaze_down_min_threshold
                or gaze_frontal < self._policy.gaze_frontal_min_threshold
            )
        )
        if eyes_away:
            if participant_state.gaze_away_started_ms is None:
                participant_state.gaze_away_started_ms = signal.timestamp_ms
        else:
            participant_state.gaze_away_started_ms = None

        eyes_away_for_ms = 0
        if participant_state.gaze_away_started_ms is not None:
            eyes_away_for_ms = max(
                0, signal.timestamp_ms - participant_state.gaze_away_started_ms
            )
        long_eyes_away = eyes_away_for_ms >= self._policy.gaze_away_grace_ms
        keyboard_typing_audio_detected = (
            signal.keyboard_typing_audio_score is not None
            and signal.keyboard_typing_audio_score
            >= self._policy.keyboard_typing_audio_min_threshold
        )
        typing_activity_high = (
            signal.typing_activity_score is not None
            and signal.typing_activity_score >= self._policy.typing_activity_min_threshold
        )
        typing_active = typing_activity_high or keyboard_typing_audio_detected
        suspected_cheating = long_eyes_away and (signal.phone_visible or typing_active)
        cheating_reasons: list[str] = []
        if long_eyes_away:
            cheating_reasons.append("eyes_away_long")
        if signal.phone_visible:
            cheating_reasons.append("phone_visible")
        if typing_activity_high:
            cheating_reasons.append("typing_activity_high")
        if keyboard_typing_audio_detected:
            cheating_reasons.append("keyboard_typing_audio")

        distance_from_camera_m = self._estimate_distance_from_face_ratio(
            signal.face_size_ratio
        )
        light_quality_score = (
            signal.light_quality_score
            if signal.light_quality_score is not None
            else tuning.light_default_quality
        )
        detection_confidence = (
            signal.image_detection_confidence
            if signal.image_detection_confidence is not None
            else (
                tuning.image_default_confidence_with_face
                if has_live_face
                else tuning.image_default_confidence_no_face
            )
        )
        image_detection_quality_score = self._clamp01(
            tuning.image_detection_confidence_weight * detection_confidence
            + tuning.image_liveness_weight
            * (1.0 if has_live_face else tuning.image_no_face_penalty)
        )
        if dominant_expression == "happy":
            expression_component = tuning.behavior_happy_weight
        elif dominant_expression != "unknown":
            expression_component = tuning.behavior_known_expression_weight
        else:
            expression_component = tuning.behavior_unknown_expression_weight
        expression_behavior_score = self._clamp01(
            expression_component
            + (tuning.behavior_focus_weight if not long_eyes_away else 0.0)
            + (tuning.behavior_integrity_weight if not suspected_cheating else 0.0)
        )
        noise_filter_effectiveness_score = (
            signal.noise_filter_effectiveness_score
            if signal.noise_filter_effectiveness_score is not None
            else None
        )
        noise_quality = self._noise_db_to_quality(signal.audio_noise_level_db)
        snr_quality = self._snr_to_quality(signal.audio_snr_db)
        clipping_quality = (
            None
            if signal.mic_clipping_ratio is None
            else self._clamp01(1.0 - signal.mic_clipping_ratio * tuning.audio_clipping_penalty)
        )
        mic_level_quality = signal.microphone_input_level_score
        mic_parts = [
            value
            for value in [
                noise_quality,
                snr_quality,
                clipping_quality,
                mic_level_quality,
                noise_filter_effectiveness_score,
            ]
            if value is not None
        ]
        microphone_quality_score = self._avg(mic_parts) if mic_parts else None

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
        if long_eyes_away:
            alerts.append(f"eyes_away_long:{signal.participant_id}")
        if keyboard_typing_audio_detected:
            alerts.append(f"keyboard_typing_audio:{signal.participant_id}")
        if suspected_cheating:
            alerts.append(
                "potential_cheating:"
                f"{signal.participant_id}:{'+'.join(sorted(cheating_reasons))}"
            )

        # --- tuning-driven quality gates -----------------------------------
        sharpness_score = signal.sharpness_score
        edge_density = signal.edge_density
        mean_luminance = signal.mean_luminance
        underexposed_ratio = signal.underexposed_ratio
        overexposed_ratio = signal.overexposed_ratio
        quality_flags: list[str] = []

        if signal.luminance_grid:
            # Client sent raw pixels: derive Sobel/exposure readings server-side so a
            # thin client still benefits from the active calibration.
            imaging = analyze_luminance_grid(signal.luminance_grid, tuning=tuning)
            sharpness_score = (
                imaging.sharpness_score if sharpness_score is None else sharpness_score
            )
            edge_density = imaging.edge_density if edge_density is None else edge_density
            mean_luminance = (
                imaging.mean_luminance if mean_luminance is None else mean_luminance
            )
            underexposed_ratio = (
                imaging.underexposed_ratio
                if underexposed_ratio is None
                else underexposed_ratio
            )
            overexposed_ratio = (
                imaging.overexposed_ratio if overexposed_ratio is None else overexposed_ratio
            )
            if signal.light_quality_score is None:
                light_quality_score = imaging.light_quality_score

        if light_quality_score < tuning.light_min_quality:
            quality_flags.append("lighting_below_min_quality")
        if mean_luminance is not None:
            if mean_luminance <= tuning.light_underexposed_luma:
                quality_flags.append("lighting_underexposed")
            elif mean_luminance >= tuning.light_overexposed_luma:
                quality_flags.append("lighting_overexposed")
        if (
            underexposed_ratio is not None
            and underexposed_ratio > tuning.light_max_clipped_black_ratio
        ):
            quality_flags.append("shadow_clipping")
        if (
            overexposed_ratio is not None
            and overexposed_ratio > tuning.light_max_clipped_white_ratio
        ):
            quality_flags.append("highlight_clipping")
        if sharpness_score is not None and sharpness_score < tuning.sharpness_min_quality:
            quality_flags.append("image_blurry")
        if edge_density is not None and edge_density < tuning.sobel_min_edge_density:
            quality_flags.append("low_edge_detail")
        if image_detection_quality_score < tuning.image_min_quality:
            quality_flags.append("detection_quality_low")
        if distance_from_camera_m is not None:
            if distance_from_camera_m < tuning.distance_too_close_m:
                quality_flags.append("too_close_to_camera")
            elif distance_from_camera_m > tuning.distance_too_far_m:
                quality_flags.append("too_far_from_camera")
        if (
            microphone_quality_score is not None
            and microphone_quality_score < tuning.audio_min_mic_quality
        ):
            quality_flags.append("microphone_quality_low")
        if (
            noise_filter_effectiveness_score is not None
            and noise_filter_effectiveness_score < tuning.audio_min_noise_filter_effectiveness
        ):
            quality_flags.append("noise_filter_weak")
        if (
            signal.audio_noise_level_db is not None
            and signal.audio_noise_level_db > tuning.audio_max_noise_level_db
        ):
            quality_flags.append("high_background_noise")
        if signal.audio_snr_db is not None and signal.audio_snr_db < tuning.audio_min_snr_db:
            quality_flags.append("low_audio_snr")

        # Recognition confidence blends the visual gates that actually govern whether
        # a frame is usable, then penalises each failed gate.
        confidence_parts = [image_detection_quality_score, light_quality_score]
        if sharpness_score is not None:
            confidence_parts.append(sharpness_score)
        recognition_confidence = self._clamp01(
            self._avg(confidence_parts) * (1.0 - 0.1 * len(quality_flags))
        )
        for flag in quality_flags:
            alerts.append(f"{flag}:{signal.participant_id}")

        return ParticipantEvaluation(
            participant_id=signal.participant_id,
            state=state,
            silhouette_detected=silhouette_detected,
            silhouette_streak=participant_state.silhouette_streak,
            face_count=signal.face_count,
            distance_from_camera_m=distance_from_camera_m,
            light_quality_score=light_quality_score,
            image_detection_quality_score=image_detection_quality_score,
            expression_behavior_score=expression_behavior_score,
            audio_noise_level_db=signal.audio_noise_level_db,
            audio_snr_db=signal.audio_snr_db,
            microphone_quality_score=microphone_quality_score,
            noise_filter_effectiveness_score=noise_filter_effectiveness_score,
            sharpness_score=sharpness_score,
            edge_density=edge_density,
            quality_flags=quality_flags,
            recognition_confidence=recognition_confidence,
            absent_for_ms=absent_for_ms,
            eyes_away_for_ms=eyes_away_for_ms,
            last_live_timestamp_ms=participant_state.last_live_timestamp_ms,
            dominant_expression=dominant_expression,
            expression_confidence=signal.expression_confidence,
            keyboard_typing_audio_detected=keyboard_typing_audio_detected,
            suspected_cheating=suspected_cheating,
            cheating_reasons=sorted(cheating_reasons),
            reason=reason,
            alerts=alerts,
        )
