import math

import pytest

from aoep_shared.vision.engine import DetectedFace, FaceRecognitionEngine
from aoep_shared.vision.enrollment import Candidate, EnrollmentRefused, choose_templates


def _c(index, vec, **kw):
    return Candidate(index=index, embedding=vec, **kw)


def test_five_photos_must_all_match_the_first():
    same = [_c(n + 1, [1.0, 0.01 * n, 0.0]) for n in range(5)]
    assert [c.index for c in choose_templates(same)] == [1, 2, 3, 4, 5]
    odd = same[:3] + [_c(4, [0.0, 1.0, 0.0])] + same[4:]
    with pytest.raises(EnrollmentRefused, match="photo 4"):
        choose_templates(odd)


def test_extra_photos_pick_the_typical_face_as_reference():
    items = [_c(1, [0.0, 1.0, 0.0])] + [_c(n, [1.0, 0.02 * n, 0.0]) for n in range(2, 8)]
    chosen = choose_templates(items)
    assert len(chosen) == 5
    assert 1 not in [c.index for c in chosen]
    assert chosen[0].index != 1


def test_blurred_photos_lose_when_enough_sharp_ones_remain():
    items = [_c(n, [1.0, 0.01 * n, 0.0], sharpness=80.0) for n in range(1, 6)]
    items += [_c(6, [1.0, 0.0, 0.0], sharpness=2.0), _c(7, [1.0, 0.0, 0.0], sharpness=3.0)]
    assert {c.index for c in choose_templates(items)} == {1, 2, 3, 4, 5}


def test_blur_does_not_decide_when_it_would_leave_too_few():
    items = [_c(n, [1.0, 0.01 * n, 0.0], sharpness=2.0) for n in range(1, 8)]
    assert len(choose_templates(items)) == 5


def test_roll_is_read_from_the_eye_line():
    level = DetectedFace(bbox=(0, 0, 10, 10), det_score=1, embedding=[], landmarks=[(10, 50), (60, 50)])
    tilted = DetectedFace(bbox=(0, 0, 10, 10), det_score=1, embedding=[], landmarks=[(10, 50), (60, 80)])
    assert level.roll_degrees == pytest.approx(0.0)
    assert tilted.roll_degrees == pytest.approx(math.degrees(math.atan2(30, 50)))


cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


class _Detector:
    """Finds a face only when the picture is taller than wide (turned upright)."""

    def setInputSize(self, size):
        self.size = size

    def detect(self, img):
        h, w = img.shape[:2]
        if h > w:
            row = np.array([10, 10, 40, 40, 20, 25, 40, 25, 30, 35, 22, 45, 38, 45, 0.9], dtype="float32")
            return None, np.array([row])
        return None, None


class _Recognizer:
    def alignCrop(self, img, row):
        return img

    def feature(self, img):
        return np.ones((1, 4), dtype="float32")


def _engine():
    engine = FaceRecognitionEngine.__new__(FaceRecognitionEngine)
    engine._cv2 = cv2
    engine._detector = _Detector()
    engine._recognizer = _Recognizer()
    return engine


def test_a_sideways_picture_is_turned_before_giving_up():
    sideways = np.random.default_rng(1).integers(0, 255, (60, 100, 3), dtype="uint8")
    assert _engine().detect_faces(sideways) == []
    faces = _engine().detect_faces(sideways, any_rotation=True)
    assert len(faces) == 1


def test_a_blurred_face_scores_lower_than_a_sharp_one():
    rng = np.random.default_rng(2)
    sharp = rng.integers(0, 255, (100, 60, 3), dtype="uint8")
    blurred = cv2.GaussianBlur(sharp, (15, 15), 5)
    engine = _engine()
    assert engine.detect_faces(sharp)[0].sharpness > 5 * engine.detect_faces(blurred)[0].sharpness
