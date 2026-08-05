"""End-to-end webcam lab harness tests."""

import pytest

from webcam_recognition_suite.frames import present_learner
from webcam_recognition_suite.lab import run_webcam_recognition_suite
from webcam_recognition_suite.session import ClassMode, ClassSession, RoomSize
from webcam_recognition_suite.teaching import TeachingMode

LAB_MODES = [
    ("solo", "theodore_teach", 2),
    ("solo", "self_teach", 2),
    ("group", "theodore_teach", 6),
    ("group", "self_teach", 4),
]


@pytest.mark.parametrize("class_mode,teaching_mode,size", LAB_MODES)
def test_lab_modes(class_mode, teaching_mode, size):
    result = run_webcam_recognition_suite(
        class_mode=class_mode,
        teaching_mode=teaching_mode,
        room_size=size,
        grace_seconds=2.0,
    )
    failed = [label for label, ok in result.checks if not ok]
    assert not failed, f"{class_mode}/{teaching_mode}: {failed}"
    assert result.presence_hold_seen is True


def test_group_session_seat_count():
    session = ClassSession.open(
        class_mode=ClassMode.GROUP,
        room_size=RoomSize.MEDIUM,
        teaching_mode=TeachingMode.THEODORE_TEACH,
    )
    # 6 seats total => 5 learners + Theodore host seat outside seats map
    assert len(session.seats) == 5
    out = session.tick("seat-1", present_learner())
    assert out["seat"]["last_verdict"]["present"] is True
