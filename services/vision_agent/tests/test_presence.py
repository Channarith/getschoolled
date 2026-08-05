"""Tests for aoep_shared.vision.webcam_presence (WebcamPresenceTracker).

All tests are pure-Python, no OpenCV required.
"""

from __future__ import annotations

import time


def test_initial_state_warming_up():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker()
    assert t.state == PresenceState.WARMING_UP


def test_warming_up_frame_does_not_advance_state():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker()
    pf = t.update(face_count=1, silhouette_confidence=0.8, warming_up=True)
    assert pf.state == PresenceState.WARMING_UP
    assert t.state == PresenceState.WARMING_UP


def test_face_detected_transitions_to_present_face():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=2.0)
    pf = t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert pf.state == PresenceState.PRESENT_FACE
    assert t.state == PresenceState.PRESENT_FACE


def test_silhouette_only_transitions_to_present_silhouette():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=2.0)
    pf = t.update(face_count=0, silhouette_confidence=0.8, warming_up=False)
    assert pf.state == PresenceState.PRESENT_SILHOUETTE


def test_silhouette_below_threshold_is_absent():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=0.001)
    time.sleep(0.01)
    pf = t.update(face_count=0, silhouette_confidence=0.10, warming_up=False)
    assert pf.state == PresenceState.ABSENT


def test_absence_event_fires_after_threshold():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    fired = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.01,
        on_absent=lambda m: fired.append(m.absence_events),
    )
    # Establish presence.
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    time.sleep(0.05)
    # Now no face + no silhouette -> should fire after threshold.
    t.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
    assert len(fired) == 1
    assert fired[0] == 1


def test_return_event_fires_after_absence():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    returned = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.01,
        return_threshold_s=0.0,   # fire immediately on first presence frame
        on_return=lambda m: returned.append(m.return_events),
    )
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    time.sleep(0.05)
    t.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
    assert t.state == PresenceState.ABSENT
    # One face-detected frame should transition back and fire on_return.
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert t.state == PresenceState.PRESENT_FACE
    assert len(returned) >= 1


def test_metrics_accumulate_correctly():
    from aoep_shared.vision.webcam_presence import WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=100.0)
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    t.update(face_count=0, silhouette_confidence=0.9, warming_up=False)
    t.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
    m = t.metrics
    assert m.total_frames == 4
    assert m.frames_face == 2
    assert m.frames_silhouette == 1
    assert m.frames_absent == 1
    assert round(m.engagement_fraction, 2) == 0.50
    assert round(m.presence_fraction, 2) == 0.75


def test_history_capped_at_60():
    from aoep_shared.vision.webcam_presence import WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=100.0)
    for _ in range(80):
        t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert len(t.history) <= 60


def test_reset_clears_state():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker
    t = WebcamPresenceTracker(absence_threshold_s=100.0)
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    t.reset()
    assert t.state == PresenceState.WARMING_UP
    assert t.metrics.total_frames == 0
    assert t.history == []


def test_presence_frame_dataclass_fields():
    from aoep_shared.vision.webcam_presence import PresenceFrame, PresenceState
    pf = PresenceFrame(
        state=PresenceState.PRESENT_FACE,
        face_count=2,
        silhouette_confidence=0.7,
        attention=0.85,
        expression="smiling",
    )
    assert pf.state == PresenceState.PRESENT_FACE
    assert pf.face_count == 2
    assert pf.attention == 0.85
