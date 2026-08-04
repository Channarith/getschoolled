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
