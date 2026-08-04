from __future__ import annotations

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.types import ClassMode, PresenceState, WebcamSignal


def test_silhouette_detection_and_absence_grace():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(
            absence_grace_ms=1_000,
            silhouette_foreground_threshold=0.2,
            silhouette_motion_threshold=0.05,
            silhouette_consecutive_frames=2,
        )
    )

    session_id = "solo-1"
    # Start present.
    present = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.5,
            )
        ],
    )
    assert present.participants[0].state is PresenceState.PRESENT

    # First silhouette frame: streak starts, still within absence grace period.
    first_silhouette = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=600,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.35,
                motion_score=0.01,
            )
        ],
    )
    p1 = first_silhouette.participants[0]
    assert p1.silhouette_detected is False
    assert p1.state is PresenceState.TEMPORARILY_MISSING

    # Second silhouette frame: silhouette alert + absent after grace period.
    second_silhouette = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_600,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.37,
                motion_score=0.02,
            )
        ],
    )
    p2 = second_silhouette.participants[0]
    assert p2.silhouette_detected is True
    assert p2.state is PresenceState.ABSENT
    assert p2.absent_for_ms == 600


def test_group_mode_marks_expected_missing_participants():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))
    session_id = "group-1"

    # Alice is present in frame.
    first = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.GROUP,
        signals=[
            WebcamSignal(
                participant_id="alice",
                timestamp_ms=1000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.21,
                motion_score=0.2,
            )
        ],
        expected_participant_ids=["alice", "bob"],
    )
    by_id = {item.participant_id: item for item in first.participants}
    assert by_id["alice"].state is PresenceState.PRESENT
    assert by_id["bob"].state is PresenceState.TEMPORARILY_MISSING

    # Bob still missing after grace -> absent.
    second = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.GROUP,
        signals=[
            WebcamSignal(
                participant_id="alice",
                timestamp_ms=1_800,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.3,
            )
        ],
        expected_participant_ids=["alice", "bob"],
    )
    assert second.absent_participant_ids == ["bob"]


def test_group_mode_builds_student_window_alerts_for_cheating_and_missing():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(absence_grace_ms=500, gaze_away_grace_ms=500)
    )
    session_id = "group-alerts-1"

    analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.GROUP,
        signals=[
            WebcamSignal(
                participant_id="alice",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
            ),
            WebcamSignal(
                participant_id="bob",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
            ),
            WebcamSignal(
                participant_id="carol",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.1,
                gaze_down_score=0.9,
                phone_visible=True,
            ),
        ],
        expected_participant_ids=["alice", "bob", "carol"],
    )

    second = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.GROUP,
        signals=[
            WebcamSignal(
                participant_id="alice",
                timestamp_ms=1_700,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
            ),
            WebcamSignal(
                participant_id="carol",
                timestamp_ms=1_700,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.1,
                gaze_down_score=0.9,
                phone_visible=True,
            ),
        ],
        expected_participant_ids=["alice", "bob", "carol"],
    )
    windows = {window.participant_id: window for window in second.group_student_windows}
    assert windows["alice"].needs_intervention is False
    assert windows["bob"].severity == "medium"
    assert windows["bob"].needs_intervention is True
    assert windows["carol"].severity == "high"
    assert windows["carol"].suspected_cheating is True

    alert_codes = {alert.code for alert in second.lesson_alerts}
    assert "group_intervention_required" in alert_codes
    assert "student_absent" in alert_codes
    assert "student_cheating_signal" in alert_codes


def test_silhouette_requires_95_percent_foreground_fill():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(
            silhouette_foreground_threshold=0.95,
            silhouette_motion_threshold=0.08,
            silhouette_consecutive_frames=1,
        )
    )

    below_threshold = analyzer.evaluate(
        session_id="solo-95",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.94,
                motion_score=0.01,
            )
        ],
    )
    assert below_threshold.participants[0].silhouette_detected is False

    at_threshold = analyzer.evaluate(
        session_id="solo-95",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_200,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.95,
                motion_score=0.01,
            )
        ],
    )
    assert at_threshold.participants[0].silhouette_detected is True


def test_expression_detection_tracks_happiness_and_summary_counts():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy())
    result = analyzer.evaluate(
        session_id="expr-1",
        mode=ClassMode.GROUP,
        signals=[
            WebcamSignal(
                participant_id="alice",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.2,
                expression_label="happy",
                expression_confidence=0.97,
            ),
            WebcamSignal(
                participant_id="bob",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.2,
                expression_label="sad",
                expression_confidence=0.85,
            ),
            WebcamSignal(
                participant_id="carol",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.2,
                expression_label="smiling",
                expression_confidence=0.88,
            ),
        ],
    )
    by_id = {item.participant_id: item for item in result.participants}
    assert by_id["alice"].dominant_expression == "happy"
    assert by_id["carol"].dominant_expression == "happy"
    assert by_id["bob"].dominant_expression == "sad"
    assert result.happy_participant_ids == ["alice", "carol"]
    assert result.suspected_cheating_participant_ids == []
    assert result.expression_counts == {"happy": 2, "sad": 1}


def test_long_gaze_away_with_phone_or_typing_flags_suspected_cheating():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(
            gaze_away_grace_ms=1_000,
            gaze_frontal_min_threshold=0.4,
            gaze_down_min_threshold=0.7,
            typing_activity_min_threshold=0.8,
        )
    )
    session_id = "cheat-1"
    first = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.5,
                motion_score=0.2,
                gaze_frontal=0.2,
                gaze_down_score=0.85,
                phone_visible=False,
                typing_activity_score=0.2,
            )
        ],
    )
    p1 = first.participants[0]
    assert p1.eyes_away_for_ms == 0
    assert p1.suspected_cheating is False

    second = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=2_300,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.5,
                motion_score=0.2,
                gaze_frontal=0.15,
                gaze_down_score=0.9,
                phone_visible=True,
                typing_activity_score=0.85,
            )
        ],
    )
    p2 = second.participants[0]
    assert p2.eyes_away_for_ms == 1_300
    assert p2.suspected_cheating is True
    assert p2.cheating_reasons == [
        "eyes_away_long",
        "phone_visible",
        "typing_activity_high",
    ]
    assert second.suspected_cheating_participant_ids == ["learner"]


def test_gaze_away_timer_resets_when_learner_refocuses_on_screen():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(gaze_away_grace_ms=500))
    session_id = "cheat-reset"
    analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=100,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.3,
                gaze_frontal=0.1,
                gaze_down_score=0.9,
            )
        ],
    )
    focused = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.3,
                gaze_frontal=0.9,
                gaze_down_score=0.0,
            )
        ],
    )
    p = focused.participants[0]
    assert p.eyes_away_for_ms == 0
    assert p.suspected_cheating is False


def test_keyboard_typing_audio_detection_flags_cheating_after_long_eyes_away():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(
            gaze_away_grace_ms=1_000,
            keyboard_typing_audio_min_threshold=0.6,
        )
    )
    session_id = "audio-cheat-1"
    analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=10_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.4,
                motion_score=0.3,
                gaze_frontal=0.1,
                gaze_down_score=0.8,
                keyboard_typing_audio_score=0.8,
                phone_visible=False,
                typing_activity_score=0.1,
            )
        ],
    )

    second = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=11_500,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.4,
                motion_score=0.3,
                gaze_frontal=0.1,
                gaze_down_score=0.85,
                keyboard_typing_audio_score=0.8,
                phone_visible=False,
                typing_activity_score=0.1,
            )
        ],
    )
    p = second.participants[0]
    assert p.keyboard_typing_audio_detected is True
    assert p.suspected_cheating is True
    assert p.cheating_reasons == ["eyes_away_long", "keyboard_typing_audio"]
    assert second.keyboard_typing_audio_participant_ids == ["learner"]
    assert second.suspected_cheating_participant_ids == ["learner"]


def test_training_pauses_when_no_learner_present_for_over_4_seconds():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(pause_training_no_presence_ms=4_000)
    )
    session_id = "pause-1"
    first = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    )
    assert first.training_paused is False
    assert first.no_one_present_for_ms == 0

    second = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=5_001,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    )
    assert second.training_paused is True
    assert second.pause_reason == "no_learner_detected_over_4s"
    assert second.no_one_present_for_ms == 4_001


def test_training_pauses_if_different_user_replaces_original_user():
    analyzer = WebcamSessionAnalyzer()
    session_id = "original-user-lock-1"

    baseline = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner-original",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
            )
        ],
    )
    assert baseline.training_paused is False
    assert baseline.original_participant_id == "learner-original"
    assert baseline.original_user_present is True

    replaced = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner-other",
                timestamp_ms=2_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
            )
        ],
    )
    assert replaced.training_paused is True
    assert replaced.pause_reason == "original_user_not_present"
    assert replaced.original_participant_id == "learner-original"
    assert replaced.original_user_present is False
    assert replaced.unexpected_participant_ids == ["learner-other"]

    resumed = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner-original",
                timestamp_ms=3_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
            )
        ],
    )
    assert resumed.training_paused is False
    assert resumed.original_user_present is True


def test_quality_metrics_include_distance_light_image_and_audio():
    analyzer = WebcamSessionAnalyzer()
    result = analyzer.evaluate(
        session_id="quality-1",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=10_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.1,
                face_size_ratio=0.20,
                light_quality_score=0.82,
                image_detection_confidence=0.91,
                expression_label="happy",
                audio_noise_level_db=36.0,
                audio_snr_db=24.0,
                noise_filter_effectiveness_score=0.88,
                microphone_input_level_score=0.78,
                mic_clipping_ratio=0.02,
            )
        ],
    )
    p = result.participants[0]
    assert p.distance_from_camera_m is not None
    assert 0.8 <= p.distance_from_camera_m <= 1.2
    assert p.light_quality_score == 0.82
    assert p.image_detection_quality_score > 0.8
    assert p.expression_behavior_score > 0.6
    assert p.microphone_quality_score is not None
    assert p.microphone_quality_score > 0.6
    assert p.noise_filter_effectiveness_score == 0.88
    summary = result.quality_summary
    assert summary.participants_count == 1
    assert summary.avg_light_quality_score == 0.82
    assert summary.avg_image_detection_quality_score > 0.8
