"""Silhouette detector: does a body read as a body, and nothing else?"""

from __future__ import annotations

import _scene
import pytest

from theodore_webcam.config import SilhouetteConfig
from theodore_webcam.silhouette import SilhouetteDetector, human_score


def calibrated_detector(config=None, frames: int = 12) -> SilhouetteDetector:
    detector = SilhouetteDetector(config or SilhouetteConfig())
    for _ in range(frames):
        detector.observe(_scene.empty_room())
    assert not detector.calibrating
    return detector


def test_calibrates_then_reports_empty_room():
    detector = SilhouetteDetector()
    first = detector.observe(_scene.empty_room())
    assert first.calibrating is True

    detector = calibrated_detector()
    observation = detector.observe(_scene.empty_room())
    assert observation.calibrating is False
    assert observation.detected is False
    assert observation.count == 0


def test_detects_a_person_silhouette():
    detector = calibrated_detector()
    observation = detector.observe(_scene.person_scene())

    assert observation.detected is True
    assert observation.count == 1
    primary = observation.primary
    assert primary is not None
    assert primary.human_score >= 0.45
    # Head band narrower than the widest (shoulder) band.
    assert primary.head_shoulder_ratio < 0.9
    assert 0.5 < primary.aspect_ratio < 5.0
    x, y, w, h = primary.bbox
    assert w > 0 and h > 0
    assert x + w <= observation.frame_size[0] + 2


def test_person_who_sits_perfectly_still_is_not_absorbed_into_background():
    """The classic background-subtraction failure this detector must not have."""

    detector = calibrated_detector()
    frame = _scene.person_scene()
    scores = []
    for _ in range(150):
        observation = detector.observe(frame)
        scores.append(observation.confidence)

    assert observation.detected is True, "still learner was absorbed into background"
    assert min(scores) >= 0.45


def test_learner_leaving_frame_stops_detection():
    detector = calibrated_detector()
    for _ in range(10):
        detector.observe(_scene.person_scene())
    assert detector.observe(_scene.person_scene()).detected is True

    for _ in range(6):
        observation = detector.observe(_scene.empty_room())
    assert observation.detected is False
    assert observation.count == 0


def test_bad_calibration_does_not_invert_the_sensor():
    """Calibrating while the learner is already seated must self-correct.

    People sit down and then start the class, so the reference regularly gets
    bootstrapped with a body in it. Left uncorrected that inverts everything:
    sitting there reads as absent, and standing up leaves a person-shaped
    ghost that reads as present for the rest of the lesson.
    """

    detector = SilhouetteDetector()
    seated = _scene.person_scene()
    for _ in range(14):
        detector.observe(seated)

    # The learner leaves. The hole they left must not be reported as a person.
    for _ in range(14):
        observation = detector.observe(_scene.empty_room())
        assert observation.count == 0, "stale background reported as a learner"

    # And the healed reference must detect them again when they sit back down.
    for _ in range(6):
        observation = detector.observe(seated)
    assert observation.detected is True
    assert observation.confidence >= 0.45


def test_lighting_change_is_not_a_person():
    detector = calibrated_detector()
    observation = detector.observe(_scene.empty_room(brightness=60))
    assert observation.detected is False


def test_moved_furniture_is_not_a_person():
    detector = calibrated_detector()
    observation = detector.observe(_scene.moved_chair())
    assert observation.detected is False


def test_two_learners_are_counted_separately():
    detector = calibrated_detector()
    frame = _scene.person_scene(center_x=0.26, body_width=0.16)
    frame = _scene.person_scene(center_x=0.74, body_width=0.16, base=frame)
    observation = detector.observe(frame)
    assert observation.count == 2


def test_reset_forces_recalibration():
    detector = calibrated_detector()
    detector.reset()
    assert detector.calibrating is True
    assert detector.observe(_scene.person_scene()).calibrating is True


@pytest.mark.parametrize(
    "kwargs, expect_high",
    [
        (dict(fill_ratio=0.55, aspect_ratio=1.8, head_shoulder_ratio=0.45, area_ratio=0.12), True),
        (dict(fill_ratio=1.0, aspect_ratio=0.3, head_shoulder_ratio=1.0, area_ratio=0.95), False),
    ],
)
def test_human_score_separates_bodies_from_blobs(kwargs, expect_high):
    score = human_score(**kwargs)
    assert (score >= 0.45) is expect_high
