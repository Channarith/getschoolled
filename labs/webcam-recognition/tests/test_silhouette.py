"""Silhouette detector tests (synthetic frames, no camera)."""

from __future__ import annotations

from webcam_lab.silhouette import SilhouetteDetector
from webcam_lab.vision_session import synthetic_person_frame


def test_blob_detects_centered_body():
    frame, _ = synthetic_person_frame(with_body=True, with_face_box=False)
    det = SilhouetteDetector(use_hog=False)
    hits = det.detect(frame)
    assert len(hits) >= 1
    assert hits[0].source == "blob"
    assert hits[0].score > 0


def test_empty_frame_no_silhouette():
    frame, _ = synthetic_person_frame(with_body=False, with_face_box=False)
    det = SilhouetteDetector(use_hog=False)
    assert det.detect(frame) == []


def test_detect_from_bboxes_filters_tiny():
    det = SilhouetteDetector(min_area_ratio=0.05)
    hits = det.detect_from_bboxes(
        [(0, 0, 2, 2), (10, 10, 100, 180)],
        frame_size=(320, 240),
        scores=[0.9, 0.8],
    )
    assert len(hits) == 1
    assert hits[0].bbox == (10, 10, 100, 180)
