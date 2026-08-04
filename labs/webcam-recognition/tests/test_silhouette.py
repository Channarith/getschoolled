"""Silhouette + body-presence tests (offline, no OpenCV required)."""

from webcam_lab.frames import absent_learner, body_only_learner, present_learner
from webcam_lab.silhouette import SilhouetteDetection, SilhouetteDetector, estimate_body_presence


def test_estimate_body_presence_empty():
    present, conf = estimate_body_presence([])
    assert present is False
    assert conf == 0.0


def test_estimate_body_presence_centered():
    det = SilhouetteDetection(
        bbox=(100, 20, 200, 400),
        score=0.7,
        centered=True,
        frame_size=(640, 480),
    )
    present, conf = estimate_body_presence([det])
    assert present is True
    assert conf >= 0.7


def test_synthetic_detector_present_and_absent():
    det = SilhouetteDetector(mode="synthetic")
    present = det.detect(present_learner())
    assert present.body_present is True
    assert present.person_count == 1
    absent = det.detect(absent_learner())
    assert absent.body_present is False
    assert absent.person_count == 0


def test_body_only_frame():
    result = SilhouetteDetector(mode="synthetic").detect(body_only_learner())
    assert result.body_present is True
    assert result.engine == "synthetic"
