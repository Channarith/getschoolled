from __future__ import annotations

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.types import ClassMode, PresenceState, WebcamSignal
from theodore_webcam_lab.vision_tuning import VisionTuning


def test_silhouette_detection_and_absence_grace():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(absence_grace_ms=1_000),
        tuning=VisionTuning(
            silhouette_foreground_threshold=0.2,
            silhouette_motion_threshold=0.05,
            silhouette_consecutive_frames=2,
        ),
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


def test_mood_and_normal_behavior_use_wall_clock_rolling_average():
    analyzer = WebcamSessionAnalyzer(
        tuning=VisionTuning(attention_min_threshold=0.7)
    )

    def evaluate(timestamp_ms: int, expression: str, attention: float):
        result = analyzer.evaluate(
            session_id="rolling-output",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=timestamp_ms,
                    face_count=1,
                    liveness_state="live",
                    foreground_ratio=0.3,
                    motion_score=0.1,
                    gaze_frontal=1.0,
                    gaze_down_score=0.0,
                    attention=attention,
                    expression_label=expression,
                    expression_confidence=0.9,
                )
            ],
        )
        return result.participants[0]

    first = evaluate(1_000, "happy", 1.0)
    noisy = evaluate(1_300, "sad", 0.0)
    assert first.dominant_expression == "happy"
    assert first.behavior_label == "focused"
    assert noisy.dominant_expression == "happy"
    assert noisy.behavior_label == "focused"
    assert noisy.attention_score > 0.55

    # The old samples have expired after 2.5 wall-clock seconds.
    settled = evaluate(4_000, "sad", 0.0)
    assert settled.dominant_expression == "sad"
    assert settled.behavior_label == "inattentive"


def test_absence_bypasses_rolling_behavior_immediately():
    analyzer = WebcamSessionAnalyzer()
    analyzer.evaluate(
        session_id="rolling-urgent",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.1,
                gaze_frontal=1.0,
                gaze_down_score=0.0,
            )
        ],
    )
    away = analyzer.evaluate(
        session_id="rolling-urgent",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_300,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    ).participants[0]
    assert away.behavior_label == "away"
    assert away.dominant_expression == "unknown"
    assert away.attention_score == 0.0


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

    # Phone must hold across consecutive frames inside the release grace —
    # a single 7s wall-clock jump is not continuous evidence.
    for ts in (2_000, 3_000, 4_000, 5_000, 6_000, 7_000, 8_000):
        second = analyzer.evaluate(
            session_id=session_id,
            mode=ClassMode.GROUP,
            signals=[
                WebcamSignal(
                    participant_id="alice",
                    timestamp_ms=ts,
                    face_count=1,
                    liveness_state="live",
                    foreground_ratio=0.3,
                    motion_score=0.2,
                ),
                WebcamSignal(
                    participant_id="carol",
                    timestamp_ms=ts,
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
        tuning=VisionTuning(
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
        policy=AnalyzerPolicy(gaze_away_grace_ms=1_000),
        tuning=VisionTuning(
            gaze_frontal_min_threshold=0.4,
            gaze_down_min_threshold=0.7,
            typing_activity_min_threshold=0.8,
        ),
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
    # Typing already trips cheating, but one frame of phone is not yet enough:
    # phone_visible has to hold for phone_visible_min_hold_ms first.
    p2 = second.participants[0]
    assert p2.eyes_away_for_ms == 1_300
    assert p2.suspected_cheating is True
    assert p2.cheating_reasons == ["eyes_away_long", "typing_activity_high"]
    assert p2.phone_visible is False
    assert p2.phone_visible_for_ms == 0
    assert second.suspected_cheating_participant_ids == ["learner"]

    # Build the phone hold with 1s steps (inside posture_release_grace_ms).
    for ts in (3_300, 4_300, 5_300, 6_300, 7_300, 8_000):
        third = analyzer.evaluate(
            session_id=session_id,
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=ts,
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
    p3 = third.participants[0]
    assert p3.phone_visible is True
    assert p3.phone_visible_for_ms == 5_700
    assert p3.cheating_reasons == [
        "eyes_away_long",
        "phone_visible",
        "typing_activity_high",
    ]


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
        policy=AnalyzerPolicy(gaze_away_grace_ms=1_000),
        tuning=VisionTuning(keyboard_typing_audio_min_threshold=0.6),
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


def test_training_pauses_when_no_learner_present_quickly():
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(pause_training_no_presence_ms=1_000)
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
                timestamp_ms=2_001,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    )
    assert second.training_paused is True
    assert second.pause_reason == "no_learner_detected"
    assert second.no_one_present_for_ms == 1_001


def test_default_policy_pauses_within_about_one_second():
    """Away-from-webcam should pause quickly (not after the old 4s / 90s windows)."""
    analyzer = WebcamSessionAnalyzer()  # product defaults
    assert analyzer.policy.pause_training_no_presence_ms <= 1_000
    assert analyzer.policy.absence_grace_ms <= 2_000
    session_id = "pause-default"
    analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
            )
        ],
    )
    gone = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=2_100,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    )
    assert gone.training_paused is True
    assert gone.participants[0].state in (
        PresenceState.ABSENT,
        PresenceState.TEMPORARILY_MISSING,
    )
    # After absence_grace (1.5s default) from last live face at t=1000 → absent by 2600.
    absent = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=2_600,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
            )
        ],
    )
    assert absent.participants[0].state is PresenceState.ABSENT
    assert "learner" in absent.absent_participant_ids


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


def test_owner_face_mismatch_pauses_solo_and_flags_cheating():
    """Same participant_id, different physical face → pause + integrity alert."""
    analyzer = WebcamSessionAnalyzer()
    session_id = "owner-face-lock-1"

    enrolled = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
                owner_face_enrolled=True,
                owner_face_match=True,
                owner_match_score=0.92,
                secondary_face_count=0,
            )
        ],
    )
    assert enrolled.training_paused is False
    assert enrolled.participants[0].suspected_cheating is False

    swapped = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=2_000,
                face_count=2,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
                owner_face_enrolled=True,
                owner_face_match=False,
                owner_face_name="Alex",
                owner_match_score=0.12,
                secondary_face_count=2,
            )
        ],
    )
    assert swapped.training_paused is True
    assert swapped.pause_reason == "owner_face_mismatch"
    assert swapped.original_user_present is False
    assert "training_paused:owner_face_mismatch" in swapped.alerts
    p = swapped.participants[0]
    assert p.suspected_cheating is True
    assert "owner_face_mismatch" in p.cheating_reasons
    assert "secondary_faces_in_frame" in p.cheating_reasons
    assert any(a.startswith("solo_mode_multiple_faces:") for a in p.alerts)
    assert any(a.startswith("owner_face_mismatch:") and "Alex" in a for a in p.alerts)


def test_owner_empty_frame_is_absence_not_substitution():
    """Leaving the camera briefly must not trip owner_face_mismatch cheating."""
    analyzer = WebcamSessionAnalyzer(
        policy=AnalyzerPolicy(absence_grace_ms=5_000, pause_training_no_presence_ms=5_000),
    )
    session_id = "owner-empty-frame-1"
    analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
                owner_face_enrolled=True,
                owner_face_match=True,
                owner_match_score=0.9,
            )
        ],
    )
    away = analyzer.evaluate(
        session_id=session_id,
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1_200,
                face_count=0,
                liveness_state="missing",
                foreground_ratio=0.0,
                motion_score=0.0,
                owner_face_enrolled=True,
                owner_face_match=None,
                owner_match_score=0.0,
                secondary_face_count=0,
            )
        ],
    )
    assert away.training_paused is False
    assert away.pause_reason != "owner_face_mismatch"
    assert away.participants[0].suspected_cheating is False
    assert "owner_face_mismatch" not in away.participants[0].cheating_reasons


def _posture_signal(timestamp_ms: int, **overrides) -> WebcamSignal:
    base = dict(
        participant_id="learner",
        timestamp_ms=timestamp_ms,
        face_count=1,
        liveness_state="live",
        foreground_ratio=0.3,
        motion_score=0.1,
        gaze_frontal=0.9,
    )
    base.update(overrides)
    return WebcamSignal(**base)


def _posture_frames(analyzer, session_id, stamps, **overrides):
    return [
        analyzer.evaluate(
            session_id=session_id,
            mode=ClassMode.SOLO,
            signals=[_posture_signal(ts, **overrides)],
        ).participants[0]
        for ts in stamps
    ]


def test_hands_on_face_needs_five_seconds_before_it_is_reported():
    analyzer = WebcamSessionAnalyzer()
    frames = _posture_frames(
        analyzer,
        "hands-hold",
        [0, 1_000, 2_000, 3_000, 4_000, 5_000, 6_000],
        hands_on_face_score=0.9,
    )
    # Below the 5s hold the streak is tracked but the behaviour is not claimed.
    assert [p.hands_on_face_for_ms for p in frames[:5]] == [0, 1_000, 2_000, 3_000, 4_000]
    assert all(p.behavior_label != "hands_on_face" for p in frames[:5])
    assert frames[5].hands_on_face_for_ms == 5_000
    assert frames[5].behavior_label == "hands_on_face"
    assert frames[6].behavior_label == "hands_on_face"
    # Telemetry only: do not treat resting a hand on the face as distraction
    # or inattention (those paths drive spoken coaching).
    assert frames[5].distraction_score < 0.55
    assert frames[5].inattentive_for_ms == 0


def test_single_frame_of_hands_on_face_is_ignored():
    analyzer = WebcamSessionAnalyzer()
    frames = [
        _posture_frames(analyzer, "hands-blip", [0], hands_on_face_score=0.9)[0],
        _posture_frames(analyzer, "hands-blip", [2_000], hands_on_face_score=0.0)[0],
        _posture_frames(analyzer, "hands-blip", [3_000], hands_on_face_score=0.9)[0],
    ]
    assert all(p.behavior_label != "hands_on_face" for p in frames)
    # The gap exceeded the release grace, so the streak restarted from zero.
    assert frames[2].hands_on_face_for_ms == 0


def test_brief_detector_flicker_does_not_restart_the_hold():
    analyzer = WebcamSessionAnalyzer()
    session_id = "hands-flicker"
    _posture_frames(analyzer, session_id, [0, 1_000, 2_000], hands_on_face_score=0.9)
    # One dropped frame inside posture_release_grace_ms keeps the streak alive.
    dropped = _posture_frames(analyzer, session_id, [2_800], hands_on_face_score=0.0)[0]
    assert dropped.hands_on_face_for_ms == 2_000
    # Resume within grace of last_seen (2000); then keep steps inside grace.
    resumed = _posture_frames(
        analyzer, session_id, [3_000, 4_000, 5_200], hands_on_face_score=0.9
    )
    assert resumed[-1].hands_on_face_for_ms == 5_200
    assert resumed[-1].behavior_label == "hands_on_face"


def test_active_frame_after_a_long_gap_does_not_credit_the_whole_gap():
    """Unobserved time past the grace must not fully accrue toward the hold."""
    analyzer = WebcamSessionAnalyzer()
    session_id = "hands-gap"
    _posture_frames(analyzer, session_id, [0, 1_000, 2_000], hands_on_face_score=0.9)
    # 8s silent gap, then active again: credit at most posture_release_grace_ms.
    resumed = _posture_frames(analyzer, session_id, [10_000], hands_on_face_score=0.9)[0]
    grace = int(VisionTuning().posture_release_grace_ms)
    assert resumed.hands_on_face_for_ms == 2_000 + grace
    assert resumed.behavior_label != "hands_on_face"


def test_phone_hold_window_is_tunable():
    analyzer = WebcamSessionAnalyzer(
        tuning=VisionTuning(phone_visible_min_hold_ms=1_000)
    )
    frames = _posture_frames(
        analyzer, "phone-tuned", [0, 500, 1_200], phone_visible=True
    )
    assert [p.phone_visible for p in frames] == [False, False, True]


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


def _dark_room_grid() -> list[list[float]]:
    """A person-shaped dark blob: enough contrast for the coarse heuristic to
    latch onto, which is exactly what used to fabricate eye/distance readings."""
    grid: list[list[float]] = []
    for y in range(16):
        row = []
        for x in range(16):
            row.append(0.18 if 3 <= y <= 13 and 4 <= x <= 12 else 0.62)
        grid.append(row)
    return grid


def test_no_live_face_never_reports_eyes_closed():
    """Regression: the live monitor showed 'absent' and 'eyes closed for 39.9s'
    at the same time, because eye state was thresholded without a tracked face."""
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))
    session_id = "no-face-eyes"

    for index, timestamp in enumerate((0, 1_000, 2_000)):
        result = analyzer.evaluate(
            session_id=session_id,
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=timestamp,
                    face_count=0,
                    liveness_state="unknown",
                    foreground_ratio=0.40,
                    motion_score=0.20,
                    # A coarse client keeps insisting the lids are down.
                    eyes_closed_score=0.95,
                    yawn_score=0.90,
                    luminance_grid=_dark_room_grid(),
                )
            ],
        )
        p = result.participants[0]
        assert p.eyes_closed_for_ms == 0, f"frame {index} claimed closed eyes with no face"
        assert p.yawn_for_ms == 0
        assert p.behavior_label == "away"


def test_no_live_face_does_not_invent_a_distance():
    """Regression: a dark blob bounding box produced a bogus 0.30 m 'too close'
    reading (and a failed quality gate) while nobody was in frame."""
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))
    result = analyzer.evaluate(
        session_id="no-face-distance",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=0,
                liveness_state="unknown",
                foreground_ratio=0.40,
                motion_score=0.20,
                luminance_grid=_dark_room_grid(),
            )
        ],
    )
    p = result.participants[0]
    assert p.distance_from_camera_m is None
    assert p.distance_source == "none"


def test_measured_depth_still_reported_without_a_face():
    """LiDAR/depth does not need a tracked face, so it must survive the guard."""
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))
    result = analyzer.evaluate(
        session_id="no-face-lidar",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=0,
                liveness_state="unknown",
                foreground_ratio=0.40,
                motion_score=0.20,
                distance_from_camera_m=1.4,
                distance_source="lidar",
            )
        ],
    )
    p = result.participants[0]
    assert p.distance_from_camera_m == 1.4
    assert p.distance_source == "lidar"


def test_coarse_detector_may_not_claim_closed_eyes():
    """Only real landmarks may assert eye state; a luminance heuristic may not,
    even when it is confident and a face is present."""
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))

    def evaluate(detector_source: str | None):
        return analyzer.evaluate(
            session_id=f"detector-{detector_source}",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=0,
                    face_count=1,
                    liveness_state="live",
                    foreground_ratio=0.30,
                    motion_score=0.30,
                    eyes_closed_score=0.95,
                    detector_source=detector_source,
                )
            ],
        ).participants[0]

    assert evaluate("coarse").behavior_label != "drowsy"
    assert evaluate("face_detector").behavior_label != "drowsy"
    # Real landmarks are still trusted, as are older clients that omit the field.
    assert evaluate("face_mesh").behavior_label == "drowsy"
    assert evaluate(None).behavior_label == "drowsy"


def _face_like_grid() -> list[list[float]]:
    """A grid the luminance heuristic happily reads as a face: on its own it
    yields face_present, a ~0.30 size ratio (=> a distance) and a 'neutral' mood."""
    return [
        [0.22 if (5 <= y <= 13 and 7 <= x <= 13) else 0.68 for x in range(20)]
        for y in range(20)
    ]


def test_coarse_detector_is_presence_only():
    """A luminance heuristic has no eyelids or mouth corners. It may report that
    somebody is in frame, but must not drive gaze/mood/distance conclusions."""
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=500))

    def evaluate(detector_source: str | None):
        return analyzer.evaluate(
            session_id=f"presence-only-{detector_source}",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=0,
                    face_count=1,
                    liveness_state="live",
                    foreground_ratio=0.30,
                    motion_score=0.30,
                    detector_source=detector_source,
                    luminance_grid=_face_like_grid(),
                )
            ],
        ).participants[0]

    coarse = evaluate("coarse")
    assert coarse.state is PresenceState.PRESENT
    assert coarse.eyes_away_for_ms == 0
    assert coarse.eyes_closed_for_ms == 0
    assert coarse.yawn_for_ms == 0
    assert coarse.distance_from_camera_m is None
    assert coarse.dominant_expression == "unknown"

    # The same frame from a thin client that never declares a detector keeps the
    # existing grid-derived behaviour, so this guard is opt-in and not a regression.
    legacy = evaluate(None)
    assert legacy.dominant_expression == "neutral"
    assert legacy.distance_from_camera_m is not None


def test_excitement_boosts_attention_without_raising_distraction():
    analyzer = WebcamSessionAnalyzer()
    base = analyzer.evaluate(
        session_id="traj-excite-base",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=1,
                liveness_state="live",
                detector_source="face_mesh",
                gaze_frontal=0.70,
                gaze_down_score=0.10,
                motion_score=0.15,
            )
        ],
    ).participants[0]
    boosted = analyzer.evaluate(
        session_id="traj-excite-hot",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=1,
                liveness_state="live",
                detector_source="face_mesh",
                gaze_frontal=0.70,
                gaze_down_score=0.10,
                motion_score=0.15,
                excitement_score=0.85,
            )
        ],
    ).participants[0]
    assert boosted.attention_score > base.attention_score
    assert boosted.distraction_score <= base.distraction_score + 0.01
    assert boosted.behavior_label != "distracted"


def test_dozing_hold_marks_drowsy_without_eyes_fully_closed():
    analyzer = WebcamSessionAnalyzer(
        tuning=VisionTuning(dozing_min_hold_ms=2_000, dozing_min_threshold=0.48)
    )
    frames = []
    for t in (0, 1_000, 2_000, 2_500):
        frames.append(
            analyzer.evaluate(
                session_id="traj-doze",
                mode=ClassMode.SOLO,
                signals=[
                    WebcamSignal(
                        participant_id="learner",
                        timestamp_ms=t,
                        face_count=1,
                        liveness_state="live",
                        detector_source="face_mesh",
                        gaze_frontal=0.60,
                        gaze_down_score=0.15,
                        eyes_closed_score=0.20,
                        dozing_score=0.75,
                    )
                ],
            ).participants[0]
        )
    assert frames[-1].dozing_for_ms >= 2_000
    assert frames[-1].behavior_label == "drowsy"


def test_external_music_and_held_object_are_record_only():
    """Music and held-object telemetry must not trip cheating or distraction."""
    analyzer = WebcamSessionAnalyzer(
        tuning=VisionTuning(
            external_music_min_hold_ms=2_000,
            held_object_min_hold_ms=2_000,
        )
    )
    last = None
    for t in (0, 1_000, 2_000, 3_000):
        last = analyzer.evaluate(
            session_id="record-only",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=t,
                    face_count=1,
                    liveness_state="live",
                    detector_source="face_mesh",
                    gaze_frontal=0.80,
                    gaze_down_score=0.05,
                    external_music_score=0.90,
                    held_object_score=0.85,
                    phone_in_hand_score=0.80,
                    phone_visible=False,
                )
            ],
        ).participants[0]
    assert last is not None
    assert last.external_music_detected is True
    assert last.held_object_detected is True
    assert last.suspected_cheating is False
    assert last.distraction_score < 0.55
    assert last.behavior_label == "focused"
