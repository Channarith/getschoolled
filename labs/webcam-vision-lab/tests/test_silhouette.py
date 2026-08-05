"""Tests for silhouette visual state classification."""

from webcam_vision_lab.presence.silhouette import (
    PresenceVisualState,
    VisualStateInput,
    classify_visual_state,
    overlay_message,
    silhouette_pulse,
)


def test_waiting_for_join_group_no_student():
    inp = VisualStateInput(is_group_class=True, participant_joined=False)
    assert classify_visual_state(inp) == PresenceVisualState.WAITING_FOR_JOIN
    assert overlay_message(PresenceVisualState.WAITING_FOR_JOIN) == "Waiting for student to join…"


def test_silhouette_absent_when_camera_on_zero_faces():
    inp = VisualStateInput(camera_on=True, face_count=0)
    state = classify_visual_state(inp)
    assert state == PresenceVisualState.SILHOUETTE_ABSENT
    assert silhouette_pulse(state)


def test_present_single_face():
    inp = VisualStateInput(camera_on=True, face_count=1)
    assert classify_visual_state(inp) == PresenceVisualState.PRESENT


def test_too_many_faces_group_policy():
    inp = VisualStateInput(camera_on=True, face_count=2, max_faces_allowed=1)
    assert classify_visual_state(inp) == PresenceVisualState.TOO_MANY_FACES


def test_probing_before_first_probe():
    inp = VisualStateInput(camera_on=True, face_count=-1)
    assert classify_visual_state(inp) == PresenceVisualState.PROBING
