from __future__ import annotations

import os
import threading
from dataclasses import dataclass, fields as dc_fields

from .advanced_behavior import AdvancedBehaviorEngine
from .audio_quality import estimate_noise_filter_effectiveness
from .distance import resolve_distance
from .facial_experience import estimate_from_luminance_grid
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
    "yawn": "yawning",
    "yawning": "yawning",
    "yawns": "yawning",
}


@dataclass
class AnalyzerPolicy:
    """Timing and session-cap knobs for the webcam analyzer.

    Detection thresholds (silhouette fill, gaze, typing) live on ``VisionTuning``
    so room presets and the live monitor sliders actually change behaviour.

    Defaults favour quick away-from-webcam identification: pause + absent within
    about a second so the learner gets an on-screen pause and spoken nudge right
    away (longer boot/cheating grace windows remain separately tunable).
    """

    absence_grace_ms: int = 1_500
    solo_max_faces: int = 1
    gaze_away_grace_ms: int = 45_000
    pause_training_no_presence_ms: int = 1_000
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
    eyes_closed_started_ms: int | None = None
    yawn_started_ms: int | None = None
    inattentive_started_ms: int | None = None
    hands_on_face_started_ms: int | None = None
    hands_on_face_last_seen_ms: int | None = None
    phone_started_ms: int | None = None
    phone_last_seen_ms: int | None = None
    dozing_started_ms: int | None = None
    dozing_last_seen_ms: int | None = None
    interest_started_ms: int | None = None
    interest_last_seen_ms: int | None = None
    music_started_ms: int | None = None
    music_last_seen_ms: int | None = None
    held_object_started_ms: int | None = None
    held_object_last_seen_ms: int | None = None


class WebcamSessionAnalyzer:
    """Stateful analyzer for solo/group webcam teaching sessions."""

    def __init__(
        self,
        policy: AnalyzerPolicy | None = None,
        tuning: VisionTuning | None = None,
    ) -> None:
        self._policy = policy or AnalyzerPolicy()
        self._tuning = tuning or VisionTuning()
        self._lock = threading.RLock()
        self._state: dict[str, dict[str, _ParticipantState]] = {}
        self._no_presence_started_ms: dict[str, int | None] = {}
        self._last_eval_ms: dict[str, int] = {}
        self._original_participant_id: dict[str, str] = {}
        self._booted_participants: dict[str, set[str]] = {}
        self._behavior_engine = AdvancedBehaviorEngine()

    @property
    def tuning(self) -> VisionTuning:
        return self._tuning

    @tuning.setter
    def tuning(self, value: VisionTuning) -> None:
        self._tuning = value

    @property
    def policy(self) -> AnalyzerPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: AnalyzerPolicy) -> None:
        self._policy = value

    def boot_participant(self, *, session_id: str, participant_id: str) -> None:
        """Remove a participant from the session permanently.

        Future signals from them are ignored so they cannot re-enter.
        """
        with self._lock:
            self._booted_participants.setdefault(session_id, set()).add(participant_id)
            self._state.get(session_id, {}).pop(participant_id, None)
            self._behavior_engine.boot_participant(
                session_id=session_id, participant_id=participant_id
            )
            # Clear the original-participant lock so a legitimate new user is not
            # permanently blocked in SOLO mode (Fix: stale original_participant_id).
            if self._original_participant_id.get(session_id) == participant_id:
                self._original_participant_id.pop(session_id, None)

    def _touch_session(self, session_id: str) -> None:
        """Mark a session as most-recently used and evict the oldest ones past the cap."""
        for store in (
            self._state,
            self._no_presence_started_ms,
            self._last_eval_ms,
            self._original_participant_id,
        ):
            if session_id in store:
                store[session_id] = store.pop(session_id)
        limit = max(1, self._policy.max_tracked_sessions)
        while len(self._state) > limit:
            oldest = next(iter(self._state))
            self._state.pop(oldest, None)
            self._no_presence_started_ms.pop(oldest, None)
            self._last_eval_ms.pop(oldest, None)
            self._original_participant_id.pop(oldest, None)
            self._booted_participants.pop(oldest, None)

    @staticmethod
    def _clamp01(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _sustained_for_ms(
        *,
        active: bool,
        timestamp_ms: int,
        started_ms: int | None,
        last_seen_ms: int | None,
        release_grace_ms: float,
    ) -> tuple[int, int | None, int | None]:
        """Track how long a per-frame posture has held across consecutive frames.

        Returns ``(held_for_ms, started_ms, last_seen_ms)``. A gap shorter than
        ``release_grace_ms`` is treated as detector flicker and keeps the streak
        alive; anything longer restarts it.
        """
        if active:
            if started_ms is None:
                started_ms = timestamp_ms
            elif last_seen_ms is not None:
                gap = timestamp_ms - last_seen_ms
                if gap > release_grace_ms:
                    # Do not credit a long unobserved stretch as continuous hold
                    # (failed POSTs / paused sampling). Bridge at most one grace
                    # window so demos that jump wall-clock still make progress
                    # without a single 10s leap counting as 10s of evidence.
                    held_before = max(0, last_seen_ms - started_ms)
                    started_ms = timestamp_ms - held_before - int(release_grace_ms)
            return max(0, timestamp_ms - started_ms), started_ms, timestamp_ms
        if (
            started_ms is not None
            and last_seen_ms is not None
            and timestamp_ms - last_seen_ms <= release_grace_ms
        ):
            return max(0, last_seen_ms - started_ms), started_ms, last_seen_ms
        return 0, None, None

    def _snr_to_quality(self, snr_db: float | None) -> float | None:
        if snr_db is None:
            return None
        tuning = self._tuning
        span = tuning.audio_snr_span_db
        if span <= 0:
            return None
        return self._clamp01((snr_db - tuning.audio_snr_floor_db) / span)

    def _noise_db_to_quality(self, noise_db: float | None) -> float | None:
        if noise_db is None:
            return None
        tuning = self._tuning
        span = tuning.audio_noise_loud_db - tuning.audio_noise_clean_db
        if span <= 0:
            return None
        return self._clamp01((tuning.audio_noise_loud_db - noise_db) / span)

    def _estimate_distance_from_face_ratio(self, ratio: float | None) -> float | None:
        """Convert an observed face-box ratio to metres using the calibration knobs."""
        return resolve_distance(face_size_ratio=ratio, tuning=self._tuning).distance_m

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
        with self._lock:
            return self._evaluate_locked(
                session_id=session_id,
                mode=mode,
                signals=signals,
                expected_participant_ids=expected_participant_ids,
            )

    def _evaluate_locked(
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
        # Drop signals from booted participants so they cannot re-enter the session.
        booted = self._booted_participants.get(session_id, set())
        if booted:
            signals = [s for s in signals if s.participant_id not in booted]
            expected -= booted
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
                # Count from the previous eval time when we just lost presence, so the
                # first away frame after a live face can trip the quick pause window.
                prev = self._last_eval_ms.get(session_id)
                started = prev if prev is not None else now_ms
                self._no_presence_started_ms[session_id] = started
            no_one_present_for_ms = max(0, now_ms - started)
        training_paused = no_one_present_for_ms >= self._policy.pause_training_no_presence_ms
        pause_reason = "no_learner_detected" if training_paused else ""
        if training_paused:
            class_alerts.append("training_paused:no_learner_detected")
        self._last_eval_ms[session_id] = now_ms

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
        # Same participant_id can still be a different physical person on one webcam.
        # Only when a live face is present — an empty frame is absence, not substitution.
        owner_face_mismatch = any(
            bool(s.owner_face_enrolled)
            and s.owner_face_match is False
            and int(s.face_count or 0) > 0
            for s in signals
        )
        if mode is ClassMode.SOLO and owner_face_mismatch:
            training_paused = True
            pause_reason = "owner_face_mismatch"
            original_user_present = False
            class_alerts.append("training_paused:owner_face_mismatch")

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
                elif participant.silhouette_detected:
                    severity = "medium"
                    needs_intervention = True
                    message = (
                        "Silhouette without a live face; confirm the learner is present."
                    )
                    lesson_alerts.append(
                        LessonAlert(
                            level="medium",
                            code="student_silhouette",
                            participant_id=participant.participant_id,
                            message=(
                                f"Silhouette detected for {participant.participant_id} "
                                "(no live face)."
                            ),
                            action="review_silhouette_and_confirm_presence",
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
                        action="review_group_interventions",
                    ),
                )
                class_alerts.append(
                    f"group_intervention_required:{intervention_count}_window(s)"
                )
        for participant in evaluations:
            class_alerts.extend(participant.alerts)
            # Facial-experience lesson alerts (solo + group). Soft eyes-away fires
            # after a few seconds so the dashboard reacts before the long grace.
            conf = participant.expression_confidence or 0.0
            if (
                participant.dominant_expression == "sad"
                and conf >= 0.45
            ):
                lesson_alerts.append(
                    LessonAlert(
                        level="low",
                        code="learner_mood_sad",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} looks sad/upset "
                            f"(confidence {conf:.0%})."
                        ),
                        action="check_in_privately_and_offer_support",
                    )
                )
            if (
                participant.dominant_expression == "happy"
                and conf >= 0.55
            ):
                lesson_alerts.append(
                    LessonAlert(
                        level="info",
                        code="learner_mood_happy",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} looks happy/engaged "
                            f"(confidence {conf:.0%})."
                        ),
                        action="acknowledge_positive_engagement",
                    )
                )
            if participant.eyes_away_for_ms >= 1_500:
                lesson_alerts.append(
                    LessonAlert(
                        level="medium" if participant.eyes_away_for_ms >= 10_000 else "low",
                        code="learner_eyes_away",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} eyes away from webcam "
                            f"for {participant.eyes_away_for_ms / 1000:.1f}s."
                        ),
                        action="prompt_learner_to_refocus",
                    )
                )
            if participant.eyes_closed_for_ms >= 1_500:
                lesson_alerts.append(
                    LessonAlert(
                        level="medium" if participant.eyes_closed_for_ms >= 10_000 else "low",
                        code="learner_eyes_closed",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} eyes closed "
                            f"for {participant.eyes_closed_for_ms / 1000:.1f}s."
                        ),
                        action="prompt_learner_to_open_eyes_and_refocus",
                    )
                )
            if participant.yawn_for_ms >= 1_500:
                lesson_alerts.append(
                    LessonAlert(
                        level="low",
                        code="learner_yawning",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} appears to be yawning "
                            f"({participant.yawn_for_ms / 1000:.1f}s)."
                        ),
                        action="acknowledge_fatigue_and_offer_break",
                    )
                )
            if (
                participant.phone_visible
                and participant.eyes_away_for_ms >= 2_000
            ):
                lesson_alerts.append(
                    LessonAlert(
                        level="high" if participant.eyes_away_for_ms >= 15_000 else "medium",
                        code="learner_phone_distraction",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} appears to be looking at a phone "
                            f"({participant.eyes_away_for_ms / 1000:.1f}s)."
                        ),
                        action="notify_student_privately_and_reinforce_integrity",
                    )
                )
            if (
                participant.distraction_score >= 0.55
                and participant.eyes_away_for_ms >= 2_500
                and not participant.phone_visible
            ):
                lesson_alerts.append(
                    LessonAlert(
                        level="medium" if participant.eyes_away_for_ms >= 12_000 else "low",
                        code="learner_distracted",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} looks distracted "
                            f"(score {participant.distraction_score:.0%}, "
                            f"{participant.eyes_away_for_ms / 1000:.1f}s)."
                        ),
                        action="prompt_learner_to_refocus",
                    )
                )
            if participant.inattentive_for_ms >= 4_000:
                lesson_alerts.append(
                    LessonAlert(
                        level="medium" if participant.inattentive_for_ms >= 15_000 else "low",
                        code="learner_inattentive",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} is not paying attention "
                            f"(attention {participant.attention_score:.0%} for "
                            f"{participant.inattentive_for_ms / 1000:.1f}s)."
                        ),
                        action="prompt_learner_to_refocus",
                    )
                )
            adv = participant.advanced_behavior or {}
            if float(adv.get("boredom_score") or 0) >= 0.62:
                lesson_alerts.append(
                    LessonAlert(
                        level="low",
                        code="learner_bored",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} shows boredom / zoning-out "
                            f"(score {float(adv.get('boredom_score') or 0):.0%})."
                        ),
                        action="prompt_learner_to_refocus",
                    )
                )
            if float(adv.get("fatigue_score") or 0) >= 0.62 and participant.yawn_for_ms < 1_500:
                lesson_alerts.append(
                    LessonAlert(
                        level="low",
                        code="learner_fatigued",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} shows fatigue signals "
                            f"(score {float(adv.get('fatigue_score') or 0):.0%})."
                        ),
                        action="acknowledge_fatigue_and_offer_break",
                    )
                )
            if float(adv.get("engagement_index") or 0) >= 0.78:
                lesson_alerts.append(
                    LessonAlert(
                        level="info",
                        code="learner_highly_engaged",
                        participant_id=participant.participant_id,
                        message=(
                            f"{participant.participant_id} is highly engaged "
                            f"(index {float(adv.get('engagement_index') or 0):.0%})."
                        ),
                        action="acknowledge_positive_engagement",
                    )
                )
            if participant.state is PresenceState.ABSENT:
                if not any(
                    a.code == "student_absent"
                    and a.participant_id == participant.participant_id
                    for a in lesson_alerts
                ):
                    lesson_alerts.append(
                        LessonAlert(
                            level="medium",
                            code="student_absent",
                            participant_id=participant.participant_id,
                            message=(
                                f"{participant.participant_id} is away from the webcam."
                            ),
                            action="alert_lesson_and_request_student_rejoin",
                        )
                    )
            elif participant.state is PresenceState.TEMPORARILY_MISSING:
                if not any(
                    a.code == "student_temporarily_missing"
                    and a.participant_id == participant.participant_id
                    for a in lesson_alerts
                ):
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
        tuning = self._tuning
        face_count = signal.face_count
        expression_label = signal.expression_label
        expression_confidence = signal.expression_confidence
        gaze_down_score = signal.gaze_down_score
        gaze_frontal = signal.gaze_frontal
        face_size_ratio = signal.face_size_ratio

        # What the reporting client could actually see. A luminance heuristic has
        # no eyelids, pupils or mouth corners, so it may report presence and
        # framing but never eye/gaze/expression state. Clients that omit the
        # field (thin clients, older builds, tests) stay trusted as before.
        detector = (signal.detector_source or "").strip().lower()
        landmark_detector = detector in {"", "face_mesh"}
        face_localised = landmark_detector or detector == "face_detector"

        # Thin clients (browser camera) often omit mood/gaze. Derive them from the
        # luminance grid so happiness / sadness / away-from-webcam actually move.
        estimate = (
            estimate_from_luminance_grid(signal.luminance_grid)
            if signal.luminance_grid
            else None
        )
        if estimate is not None:
            if landmark_detector and self._normalize_expression(expression_label) == "unknown":
                expression_label = estimate.expression_label
                if expression_confidence is None:
                    expression_confidence = estimate.expression_confidence
            if landmark_detector and gaze_frontal is None:
                gaze_frontal = estimate.gaze_frontal
            if landmark_detector and gaze_down_score is None:
                gaze_down_score = estimate.gaze_down_score
            if face_localised and face_size_ratio is None:
                face_size_ratio = estimate.face_size_ratio
            if landmark_detector and signal.yawn_score is None and estimate.yawn_score > 0:
                # Thin clients: promote grid yawn into the signal path below.
                signal = signal.model_copy(update={"yawn_score": estimate.yawn_score})
                if (
                    estimate.expression_label == "yawning"
                    and self._normalize_expression(expression_label) in {"unknown", "neutral"}
                ):
                    expression_label = "yawning"
                    if expression_confidence is None:
                        expression_confidence = estimate.expression_confidence
            if (
                not estimate.face_present
                and self._normalize_expression(signal.expression_label) == "unknown"
                and signal.gaze_frontal is None
                and signal.gaze_down_score is None
                and face_count > 0
            ):
                # Client claimed a face but the frame looks empty (stepped away).
                face_count = 0

        has_live_face = face_count > 0 and liveness not in {"spoof", "fake"}
        dominant_expression = self._normalize_expression(expression_label)
        # Detection thresholds live on VisionTuning so room presets (high_accuracy,
        # noisy_room, …) actually change behaviour. AnalyzerPolicy still owns
        # timing/session caps (grace windows, max faces, eviction).
        silhouette_candidate = (
            face_count == 0
            and signal.foreground_ratio >= tuning.silhouette_foreground_threshold
            and signal.motion_score <= tuning.silhouette_motion_threshold
        )
        gaze_down_score = gaze_down_score if gaze_down_score is not None else 0.0
        gaze_frontal = gaze_frontal if gaze_frontal is not None else 1.0
        eyes_closed_score = (
            float(signal.eyes_closed_score)
            if signal.eyes_closed_score is not None
            else 0.0
        )
        # Eyes/mouth/gaze claims are only meaningful when a face is actually being
        # tracked by a detector that can see those features. Without this guard the
        # dashboard reported "eyes closed for 39s" on a frame it scored as absent.
        eyes_closed = (
            has_live_face
            and landmark_detector
            and eyes_closed_score >= tuning.eyes_closed_min_threshold
        )
        yawn_score = float(signal.yawn_score) if signal.yawn_score is not None else 0.0
        if dominant_expression == "yawning" and yawn_score < tuning.yawn_min_threshold:
            yawn_score = max(yawn_score, 0.62)
        yawning = (
            has_live_face
            and landmark_detector
            and (yawn_score >= tuning.yawn_min_threshold or dominant_expression == "yawning")
        )
        if yawning and dominant_expression in {"unknown", "neutral", "surprised"}:
            dominant_expression = "yawning"
        eyes_away = (
            face_count > 0
            and landmark_detector
            and (
                eyes_closed
                or gaze_down_score >= tuning.gaze_down_min_threshold
                or gaze_frontal < tuning.gaze_frontal_min_threshold
            )
        )
        if eyes_away:
            if participant_state.gaze_away_started_ms is None:
                participant_state.gaze_away_started_ms = signal.timestamp_ms
        else:
            participant_state.gaze_away_started_ms = None

        if eyes_closed:
            if participant_state.eyes_closed_started_ms is None:
                participant_state.eyes_closed_started_ms = signal.timestamp_ms
        else:
            participant_state.eyes_closed_started_ms = None

        if yawning and has_live_face:
            if participant_state.yawn_started_ms is None:
                participant_state.yawn_started_ms = signal.timestamp_ms
        else:
            participant_state.yawn_started_ms = None

        eyes_away_for_ms = 0
        if participant_state.gaze_away_started_ms is not None:
            eyes_away_for_ms = max(
                0, signal.timestamp_ms - participant_state.gaze_away_started_ms
            )
        eyes_closed_for_ms = 0
        if participant_state.eyes_closed_started_ms is not None:
            eyes_closed_for_ms = max(
                0, signal.timestamp_ms - participant_state.eyes_closed_started_ms
            )
        yawn_for_ms = 0
        if participant_state.yawn_started_ms is not None:
            yawn_for_ms = max(
                0, signal.timestamp_ms - participant_state.yawn_started_ms
            )

        hands_on_face_score = (
            float(signal.hands_on_face_score)
            if signal.hands_on_face_score is not None
            else 0.0
        )
        # Both postures below are reported only once they have held for their
        # configured window. A hand brushing past the face, or one glance down at
        # a desk, is not "hands on face" / "on their phone".
        (
            hands_on_face_for_ms,
            participant_state.hands_on_face_started_ms,
            participant_state.hands_on_face_last_seen_ms,
        ) = self._sustained_for_ms(
            active=(
                has_live_face
                and hands_on_face_score >= tuning.hands_on_face_min_threshold
            ),
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.hands_on_face_started_ms,
            last_seen_ms=participant_state.hands_on_face_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )
        hands_on_face = (
            participant_state.hands_on_face_started_ms is not None
            and hands_on_face_for_ms >= tuning.hands_on_face_min_hold_ms
        )

        (
            phone_visible_for_ms,
            participant_state.phone_started_ms,
            participant_state.phone_last_seen_ms,
        ) = self._sustained_for_ms(
            active=bool(signal.phone_visible),
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.phone_started_ms,
            last_seen_ms=participant_state.phone_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )
        phone_visible = (
            participant_state.phone_started_ms is not None
            and phone_visible_for_ms >= tuning.phone_visible_min_hold_ms
        )

        excitement_raw = float(signal.excitement_score or 0.0)
        interest_raw = float(signal.interest_score or 0.0)
        dozing_raw = float(signal.dozing_score or 0.0)
        music_raw = float(signal.external_music_score or 0.0)
        held_raw = max(
            float(signal.held_object_score or 0.0),
            float(signal.phone_in_hand_score or 0.0),
        )

        (
            dozing_for_ms,
            participant_state.dozing_started_ms,
            participant_state.dozing_last_seen_ms,
        ) = self._sustained_for_ms(
            active=has_live_face and dozing_raw >= tuning.dozing_min_threshold,
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.dozing_started_ms,
            last_seen_ms=participant_state.dozing_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )
        dozing_held = (
            participant_state.dozing_started_ms is not None
            and dozing_for_ms >= tuning.dozing_min_hold_ms
        )

        (
            interest_for_ms,
            participant_state.interest_started_ms,
            participant_state.interest_last_seen_ms,
        ) = self._sustained_for_ms(
            active=has_live_face and interest_raw >= tuning.interest_min_threshold,
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.interest_started_ms,
            last_seen_ms=participant_state.interest_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )

        (
            external_music_for_ms,
            participant_state.music_started_ms,
            participant_state.music_last_seen_ms,
        ) = self._sustained_for_ms(
            active=music_raw >= tuning.external_music_min_threshold,
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.music_started_ms,
            last_seen_ms=participant_state.music_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )
        external_music_detected = (
            participant_state.music_started_ms is not None
            and external_music_for_ms >= tuning.external_music_min_hold_ms
        )

        (
            held_object_for_ms,
            participant_state.held_object_started_ms,
            participant_state.held_object_last_seen_ms,
        ) = self._sustained_for_ms(
            active=held_raw >= tuning.held_object_min_threshold,
            timestamp_ms=signal.timestamp_ms,
            started_ms=participant_state.held_object_started_ms,
            last_seen_ms=participant_state.held_object_last_seen_ms,
            release_grace_ms=tuning.posture_release_grace_ms,
        )
        held_object_detected = (
            participant_state.held_object_started_ms is not None
            and held_object_for_ms >= tuning.held_object_min_hold_ms
        )

        distraction_score = 0.0
        if has_live_face:
            # Hands-on-face, external music, and held-object telemetry must not
            # inflate distraction (that would cascade into spoken coaching).
            # Excitement motion is also excluded — it is engagement, not distraction.
            distraction_score = max(
                distraction_score,
                gaze_down_score,
                max(0.0, 1.0 - gaze_frontal),
                0.85 if phone_visible else 0.0,
                0.70 if eyes_closed else 0.0,
                0.55 if yawning else 0.0,
                float(signal.typing_activity_score or 0.0) * 0.8,
            )
            if eyes_away:
                distraction_score = max(distraction_score, 0.50)

        attention_score = 0.0
        if has_live_face:
            attention_score = self._clamp01(
                gaze_frontal * (1.0 - gaze_down_score * 0.75)
            )
            if eyes_closed:
                attention_score = min(attention_score, 0.12)
            elif eyes_away:
                attention_score = min(attention_score, 0.32)
            if yawning:
                attention_score = min(attention_score, 0.45)
            if phone_visible:
                attention_score = min(attention_score, 0.20)
            if signal.attention is not None:
                attention_score = self._clamp01(
                    0.55 * attention_score + 0.45 * float(signal.attention)
                )
            # Soft boosts from trajectory — cannot override eyes-closed / phone caps.
            if not eyes_closed and not eyes_away and not phone_visible:
                if excitement_raw >= tuning.excitement_min_threshold:
                    attention_score = self._clamp01(
                        attention_score + tuning.excitement_attention_boost * excitement_raw
                    )
                if interest_for_ms >= tuning.interest_min_hold_ms:
                    attention_score = self._clamp01(
                        attention_score + tuning.interest_attention_boost * interest_raw
                    )
            if dozing_held:
                attention_score = min(attention_score, 0.28)

        inattentive_now = has_live_face and (
            attention_score < tuning.attention_min_threshold
            or distraction_score >= tuning.distraction_min_threshold
            or eyes_away
            or yawning
            or eyes_closed
            or dozing_held
        )
        if inattentive_now:
            if participant_state.inattentive_started_ms is None:
                participant_state.inattentive_started_ms = signal.timestamp_ms
        else:
            participant_state.inattentive_started_ms = None
        inattentive_for_ms = 0
        if participant_state.inattentive_started_ms is not None:
            inattentive_for_ms = max(
                0, signal.timestamp_ms - participant_state.inattentive_started_ms
            )

        if not has_live_face:
            behavior_label = "away"
        elif eyes_closed or dozing_held:
            behavior_label = "drowsy"
        elif yawning:
            behavior_label = "yawning"
        elif hands_on_face:
            behavior_label = "hands_on_face"
        elif phone_visible or (
            distraction_score >= tuning.distraction_min_threshold and eyes_away
        ):
            behavior_label = "distracted"
        elif attention_score < tuning.attention_min_threshold:
            behavior_label = "inattentive"
        else:
            behavior_label = "focused"

        # Trip integrity/cheating faster when a phone is also visible.
        cheat_grace_ms = self._policy.gaze_away_grace_ms
        if phone_visible:
            cheat_grace_ms = min(cheat_grace_ms, 8_000)
        long_eyes_away = eyes_away_for_ms >= cheat_grace_ms
        keyboard_typing_audio_detected = (
            signal.keyboard_typing_audio_score is not None
            and signal.keyboard_typing_audio_score
            >= tuning.keyboard_typing_audio_min_threshold
        )
        typing_activity_high = (
            signal.typing_activity_score is not None
            and signal.typing_activity_score >= tuning.typing_activity_min_threshold
        )
        typing_active = typing_activity_high or keyboard_typing_audio_detected
        owner_mismatch = bool(
            signal.owner_face_enrolled
            and signal.owner_face_match is False
            and face_count > 0
        )
        secondary_faces = max(0, int(signal.secondary_face_count or 0))
        suspected_cheating = (
            (long_eyes_away and (phone_visible or typing_active)) or owner_mismatch
        )
        cheating_reasons: list[str] = []
        if long_eyes_away:
            cheating_reasons.append("eyes_away_long")
        if phone_visible:
            cheating_reasons.append("phone_visible")
        if typing_activity_high:
            cheating_reasons.append("typing_activity_high")
        if keyboard_typing_audio_detected:
            cheating_reasons.append("keyboard_typing_audio")
        if owner_mismatch:
            cheating_reasons.append("owner_face_mismatch")
        if secondary_faces > 0 and (mode is ClassMode.SOLO or owner_mismatch):
            cheating_reasons.append("secondary_faces_in_frame")

        # A dark-pixel bounding box is a person-or-furniture blob, not a face, so
        # deriving metres from it without a localised face reports a bogus "0.30 m
        # / too close". Measured depth (LiDAR) needs no face and is still honoured.
        face_sized = has_live_face and face_localised
        distance_est = resolve_distance(
            measured_m=signal.distance_from_camera_m,
            face_size_ratio=face_size_ratio if face_sized else None,
            luminance_grid=signal.luminance_grid if face_sized else None,
            tuning=tuning,
        )
        distance_from_camera_m = distance_est.distance_m
        distance_source = distance_est.source
        if face_size_ratio is None and distance_est.face_size_ratio is not None:
            face_size_ratio = distance_est.face_size_ratio
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
        elif dominant_expression == "yawning":
            expression_component = tuning.behavior_unknown_expression_weight * 0.5
        elif dominant_expression != "unknown":
            expression_component = tuning.behavior_known_expression_weight
        else:
            expression_component = tuning.behavior_unknown_expression_weight
        expression_behavior_score = self._clamp01(
            expression_component
            + (tuning.behavior_focus_weight if not long_eyes_away and not yawning else 0.0)
            + (tuning.behavior_integrity_weight if not suspected_cheating else 0.0)
            + (0.15 * attention_score)
            - (0.20 * distraction_score)
        )
        noise_filter_effectiveness_score = estimate_noise_filter_effectiveness(
            noise_filter_effectiveness_score=signal.noise_filter_effectiveness_score,
            audio_noise_level_db=signal.audio_noise_level_db,
            audio_snr_db=signal.audio_snr_db,
            tuning=tuning,
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
            participant_state.silhouette_streak >= tuning.silhouette_consecutive_frames
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
        if mode is ClassMode.SOLO and face_count > self._policy.solo_max_faces:
            alerts.append(f"solo_mode_multiple_faces:{signal.participant_id}")
        if owner_mismatch:
            alerts.append(f"owner_face_mismatch:{signal.participant_id}")
        if secondary_faces > 0:
            alerts.append(
                f"secondary_faces:{signal.participant_id}:{secondary_faces}"
            )
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

        advanced = self._behavior_engine.evaluate(
            session_id=session_id,
            signal=signal,
            attention_score=attention_score,
            distraction_score=distraction_score,
            behavior_label=behavior_label,
            eyes_away_for_ms=eyes_away_for_ms,
            eyes_closed_for_ms=eyes_closed_for_ms,
            yawn_for_ms=yawn_for_ms,
            inattentive_for_ms=inattentive_for_ms,
            dominant_expression=dominant_expression,
            expression_confidence=expression_confidence,
            suspected_cheating=suspected_cheating,
            tuning=tuning,
            phone_visible=phone_visible,
        )

        return ParticipantEvaluation(
            participant_id=signal.participant_id,
            state=state,
            silhouette_detected=silhouette_detected,
            silhouette_streak=participant_state.silhouette_streak,
            face_count=face_count,
            distance_from_camera_m=distance_from_camera_m,
            distance_source=distance_source,
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
            eyes_closed_for_ms=eyes_closed_for_ms,
            eyes_closed_score=eyes_closed_score if eyes_closed_score > 0 else None,
            yawn_score=yawn_score if yawn_score > 0 else None,
            yawn_for_ms=yawn_for_ms,
            hands_on_face_score=hands_on_face_score if hands_on_face_score > 0 else None,
            hands_on_face_for_ms=hands_on_face_for_ms,
            attention_score=attention_score,
            distraction_score=distraction_score,
            inattentive_for_ms=inattentive_for_ms,
            behavior_label=behavior_label,
            advanced_behavior=advanced.as_dict(),
            phone_visible=phone_visible,
            phone_visible_for_ms=phone_visible_for_ms,
            last_live_timestamp_ms=participant_state.last_live_timestamp_ms,
            dominant_expression=dominant_expression,
            expression_confidence=expression_confidence,
            keyboard_typing_audio_detected=keyboard_typing_audio_detected,
            suspected_cheating=suspected_cheating,
            cheating_reasons=sorted(cheating_reasons),
            excitement_score=excitement_raw if excitement_raw > 0 else None,
            interest_score=interest_raw if interest_raw > 0 else None,
            dozing_score=dozing_raw if dozing_raw > 0 else None,
            dozing_for_ms=dozing_for_ms,
            interest_for_ms=interest_for_ms,
            external_music_score=music_raw if music_raw > 0 else None,
            external_music_for_ms=external_music_for_ms,
            external_music_detected=external_music_detected,
            phone_in_hand_score=(
                float(signal.phone_in_hand_score)
                if signal.phone_in_hand_score
                else None
            ),
            held_object_score=held_raw if held_raw > 0 else None,
            held_object_for_ms=held_object_for_ms,
            held_object_detected=held_object_detected,
            reason=reason,
            alerts=alerts,
        )
