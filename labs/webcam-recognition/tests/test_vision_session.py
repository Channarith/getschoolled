"""Vision session synthetic pipeline."""

from __future__ import annotations

from webcam_lab.presence import PRESENCE_ABSENT, PRESENCE_SILHOUETTE
from webcam_lab.vision_session import VisionSession, synthetic_person_frame


def test_body_frame_yields_silhouette_presence():
    vision = VisionSession(participant_id="p1")
    frame, _ = synthetic_person_frame(with_body=True, with_face_box=False)
    # Force blob path (HOG may or may not fire on synthetic rectangles).
    vision.silhouette._hog = None
    analysis = vision.analyze_frame(frame)
    assert analysis.report.silhouette_count >= 1
    assert analysis.report.liveness_state == PRESENCE_SILHOUETTE


def test_empty_frames_become_absent():
    vision = VisionSession(participant_id="p1")
    vision.tracker.absent_after = 2
    frame, _ = synthetic_person_frame(with_body=False)
    vision.analyze_frame(frame)
    r = vision.analyze_frame(frame).report
    assert r.liveness_state == PRESENCE_ABSENT
    assert r.reason == "user_absent"


def test_injected_face_path():
    vision = VisionSession(participant_id="p1")
    frame, faces = synthetic_person_frame(with_body=True, with_face_box=True)
    analysis = vision.analyze_detections(faces=faces, silhouettes=[])
    assert analysis.report.present is True
    assert analysis.report.face_count == 1
