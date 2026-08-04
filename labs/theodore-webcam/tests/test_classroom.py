"""Solo and group class behaviour driven by real synthetic frames."""

from __future__ import annotations

import _scene

from theodore_webcam.classroom import SessionRegistry
from theodore_webcam.config import load_config
from theodore_webcam.cues import ClassMode, CueAction


def make_registry(clock, **env):
    base = {
        "WEBCAM_LAB_ARRIVE_CONFIRM_SECONDS": "1",
        "WEBCAM_LAB_RETURN_CONFIRM_SECONDS": "1",
        "WEBCAM_LAB_ABSENCE_GRACE_SECONDS": "4",
        "WEBCAM_LAB_PROLONGED_ABSENCE_SECONDS": "30",
        "WEBCAM_LAB_STALE_SECONDS": "10",
        "WEBCAM_LAB_RECAP_AFTER_ABSENCE_SECONDS": "5",
    }
    base.update(env)
    return SessionRegistry(load_config(base), clock=clock)


def drive(session, participant_id, frame, clock, *, frames=8, step=0.5):
    """Feed N frames of the same scene, advancing the clock between them."""

    result = None
    for _ in range(frames):
        clock.advance(step)
        result = session.observe_frame(participant_id, frame)
    return result


def calibrate(session, participant_id, clock, frames=12):
    drive(session, participant_id, _scene.empty_room(), clock, frames=frames)


def test_solo_session_pauses_on_absence_and_recaps_on_return(clock):
    registry = make_registry(clock)
    session = registry.create(
        mode=ClassMode.SOLO,
        lesson_title="Fractions, part 2",
        checkpoint="slide 7",
    )
    session.add_participant("learner-1", "Maya")

    calibrate(session, "learner-1", clock)
    result = drive(session, "learner-1", _scene.person_scene(), clock, frames=6)
    assert result.presence["state"] == "present"
    assert session.lesson_paused is False

    result = drive(session, "learner-1", _scene.empty_room(), clock, frames=14)
    assert result.presence["state"] == "absent"
    assert session.lesson_paused is True
    pause_cues = [c for c in session.cue_log if c["action"] == CueAction.PAUSE_LESSON.value]
    assert pause_cues, "solo absence must pause the lesson"
    # Theodore must not narrate to an empty chair.
    assert all(c["voice_turn"] is False for c in pause_cues)
    assert "slide 7" in pause_cues[0]["speech"]

    result = drive(session, "learner-1", _scene.person_scene(), clock, frames=8)
    assert result.presence["state"] == "present"
    assert session.lesson_paused is False
    recap = [c for c in session.cue_log if c["action"] == CueAction.RECAP.value]
    assert recap, "a long absence must trigger a recap on return"
    assert recap[0]["voice_turn"] is True
    assert "Maya" in recap[0]["speech"]


def test_short_absence_resumes_without_a_recap(clock):
    registry = make_registry(clock, WEBCAM_LAB_RECAP_AFTER_ABSENCE_SECONDS="600")
    session = registry.create(mode=ClassMode.SOLO, lesson_title="Fractions", checkpoint="slide 7")
    session.add_participant("learner-1", "Maya")

    calibrate(session, "learner-1", clock)
    drive(session, "learner-1", _scene.person_scene(), clock, frames=6)
    drive(session, "learner-1", _scene.empty_room(), clock, frames=14)
    drive(session, "learner-1", _scene.person_scene(), clock, frames=8)

    actions = [c["action"] for c in session.cue_log]
    assert CueAction.RECAP.value not in actions
    assert CueAction.RESUME_LESSON.value in actions


def test_group_class_keeps_teaching_until_quorum_breaks(clock):
    registry = make_registry(clock, WEBCAM_LAB_GROUP_MIN_PRESENT_RATIO="0.6")
    session = registry.create(
        mode=ClassMode.GROUP,
        lesson_title="Photosynthesis",
        checkpoint="slide 3",
    )
    for pid, name in [("a", "Ana"), ("b", "Ben"), ("c", "Cy")]:
        session.add_participant(pid, name)

    for pid in ("a", "b", "c"):
        calibrate(session, pid, clock)
        drive(session, pid, _scene.person_scene(), clock, frames=6)
    assert session.attendance()["present"] == 3
    assert session.class_held is False

    # One learner leaves: 2/3 present is still above the 0.6 quorum.
    drive(session, "c", _scene.empty_room(), clock, frames=14)
    assert session.class_held is False
    nudges = [c for c in session.cue_log if c["action"] == CueAction.NUDGE.value]
    assert nudges, "a group absence should nudge, not pause the class"
    assert session.lesson_paused is False

    # A second learner leaves: 1/3 breaks quorum and the class holds.
    drive(session, "b", _scene.empty_room(), clock, frames=14)
    assert session.class_held is True
    holds = [c for c in session.cue_log if c["action"] == CueAction.HOLD_CLASS.value]
    assert holds

    # Both come back and the hold releases.
    for pid in ("b", "c"):
        drive(session, pid, _scene.person_scene(), clock, frames=8)
    assert session.class_held is False
    assert [c for c in session.cue_log if c["action"] == CueAction.RELEASE_HOLD.value]


def test_class_does_not_hold_while_the_room_is_still_filling_up(clock):
    """No attendance hold before the class has gathered.

    Otherwise every group class opens by announcing a hold at 0/3 and telling
    an empty room to wait for people to come back.
    """

    registry = make_registry(clock, WEBCAM_LAB_GROUP_MIN_PRESENT_RATIO="0.6")
    session = registry.create(mode=ClassMode.GROUP, lesson_title="Photosynthesis")
    for pid in ("a", "b", "c"):
        session.add_participant(pid, pid.upper())

    # Learners trickle in one at a time.
    for pid in ("a", "b"):
        for _ in range(4):
            clock.advance(0.5)
            session.observe_signals(pid, detected=True, confidence=0.9, count=1)
        assert session.class_held is False

    actions = [c["action"] for c in session.cue_log]
    assert CueAction.HOLD_CLASS.value not in actions
    assert CueAction.RELEASE_HOLD.value not in actions
    assert session.class_started is True

    # Now that class has gathered, dropping under quorum does hold it.
    for _ in range(16):
        clock.advance(0.5)
        session.observe_signals("a", detected=False)
        session.observe_signals("b", detected=False)
    assert session.class_held is True


def test_on_device_signal_path_matches_frame_path(clock):
    registry = make_registry(clock)
    session = registry.create(mode=ClassMode.SOLO, lesson_title="Algebra")
    session.add_participant("learner-1", "Sam")

    for _ in range(6):
        clock.advance(0.5)
        session.observe_signals("learner-1", detected=True, confidence=0.8, count=1)
    assert session.participant("learner-1").tracker.snapshot().present is True

    result = None
    for _ in range(16):
        clock.advance(0.5)
        result = session.observe_signals("learner-1", detected=False)
    assert result.presence["state"] == "absent"
    assert session.lesson_paused is True


def test_report_captures_absence_accounting(clock):
    registry = make_registry(clock)
    session = registry.create(mode=ClassMode.SOLO, lesson_title="Algebra")
    session.add_participant("learner-1", "Sam")

    calibrate(session, "learner-1", clock)
    drive(session, "learner-1", _scene.person_scene(), clock, frames=10)
    drive(session, "learner-1", _scene.empty_room(), clock, frames=20)
    drive(session, "learner-1", _scene.person_scene(), clock, frames=10)

    report = registry.delete(session.session_id)
    row = report["participants"][0]
    assert row["absence_count"] == 1
    assert row["present_seconds"] > 0
    assert row["absent_seconds"] > 0
    assert row["no_show"] is False
    assert 0.0 < row["attention_ratio"] < 1.0
    assert any(e["kind"] == "departed" for e in report["events"])
    assert any(e["kind"] == "returned" for e in report["events"])


def test_recalibrate_clears_learned_background(clock):
    registry = make_registry(clock)
    session = registry.create(mode=ClassMode.SOLO)
    session.add_participant("learner-1")
    calibrate(session, "learner-1", clock)

    assert session.participant("learner-1").detector.calibrating is False
    assert session.recalibrate("learner-1") == 1
    assert session.participant("learner-1").detector.calibrating is True
