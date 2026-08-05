from __future__ import annotations

from theodore_webcam_lab.models import ClassMode, ParticipantSignal, WebcamFrameInput
from theodore_webcam_lab.monitor import WebcamSessionMonitor


def _frame(
    *,
    session_id: str = "s1",
    class_mode: ClassMode = ClassMode.solo,
    expected_participants: int = 1,
    participants: list[ParticipantSignal] | None = None,
    face_count: int | None = None,
    foreground_ratio: float = 0.0,
    motion_ratio: float = 0.0,
    timestamp_ms: int = 1,
) -> WebcamFrameInput:
    return WebcamFrameInput(
        session_id=session_id,
        class_mode=class_mode,
        expected_participants=expected_participants,
        participants=participants or [],
        face_count=face_count,
        foreground_ratio=foreground_ratio,
        motion_ratio=motion_ratio,
        timestamp_ms=timestamp_ms,
    )


def test_solo_absence_triggers_after_threshold_then_recovers() -> None:
    monitor = WebcamSessionMonitor(absence_frame_threshold=2)

    first = monitor.analyze(_frame(timestamp_ms=1))
    second = monitor.analyze(_frame(timestamp_ms=2))
    third = monitor.analyze(
        _frame(
            timestamp_ms=3,
            participants=[ParticipantSignal(participant_id="learner-1", attention=0.9)],
            face_count=1,
        )
    )

    assert first.user_absent is False
    assert second.user_absent is True
    assert any(event.code == "user_absent" for event in second.events)
    assert third.user_absent is False
    assert any(event.code == "user_returned" for event in third.events)


def test_silhouette_event_requires_motion_and_foreground_without_face() -> None:
    monitor = WebcamSessionMonitor()
    decision = monitor.analyze(
        _frame(
            face_count=0,
            foreground_ratio=0.35,
            motion_ratio=0.12,
            timestamp_ms=1,
        )
    )
    assert decision.silhouette_detected is True
    assert any(event.code == "silhouette_detected" for event in decision.events)
    assert decision.user_absent is False


def test_group_understaffed_when_active_participants_below_expected() -> None:
    monitor = WebcamSessionMonitor()
    decision = monitor.analyze(
        _frame(
            session_id="group-1",
            class_mode=ClassMode.group,
            expected_participants=3,
            participants=[
                ParticipantSignal(participant_id="a", attention=0.95),
                ParticipantSignal(participant_id="b", attention=0.91),
            ],
            face_count=2,
            timestamp_ms=10,
        )
    )
    assert decision.group_understaffed is True
    assert any(event.code == "group_understaffed" for event in decision.events)
