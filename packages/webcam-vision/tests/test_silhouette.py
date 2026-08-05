"""Silhouette detector tests (synthetic frames; real OpenCV, no downloads).

The motion path is deterministic: MOG2 learns a static background, then a
large moving block is a person-sized silhouette. The HOG people detector does
not fire reliably on synthetic blobs, so HOG is smoke-tested for API shape and
exercised through the plausibility filter directly.
"""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2", reason="OpenCV not installed in this env")

from aoep_webcam_vision.silhouette import (  # noqa: E402
    PersonDetection,
    SilhouetteDetector,
    summarize,
)

FRAME_W, FRAME_H = 320, 240


def blank_frame() -> np.ndarray:
    return np.full((FRAME_H, FRAME_W, 3), 200, dtype=np.uint8)


def frame_with_block(x: int, y: int, w: int = 90, h: int = 150) -> np.ndarray:
    """A static room with one large dark (person-sized) block in it."""
    img = blank_frame()
    cv2.rectangle(img, (x, y), (x + w, y + h), (30, 30, 30), thickness=-1)
    return img


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


class TestMotionSilhouette:
    def test_static_room_has_no_silhouette(self):
        det = SilhouetteDetector(use_hog=False)
        for _ in range(5):
            assert det.detect(blank_frame()) == []

    def test_person_sized_motion_is_detected(self):
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())  # learn background
        # A real learner shifts slightly between frames; a few pixels of
        # movement keeps the silhouette out of the background model.
        for i in range(3):
            detections = det.detect(frame_with_block(40 + i * 4, 40))
            assert detections, "expected a moving person-sized block to register"
        best = detections[0]
        assert best.source == "motion"
        assert best.frame_size == (FRAME_W, FRAME_H)
        assert best.area_ratio >= det.min_area_ratio
        assert 0.0 < best.confidence <= 1.0

    def test_slow_adaptation_keeps_still_learner_present(self):
        # A learner sitting nearly still must not fade into the background
        # within the absence grace window.
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())
        det.detect(frame_with_block(40, 40))
        still_present = det.detect(frame_with_block(40, 40))
        assert still_present, "second frame of a new silhouette must register"

    def test_tiny_motion_is_ignored(self):
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())
        small = blank_frame()
        cv2.rectangle(small, (10, 10), (18, 18), (0, 0, 0), thickness=-1)
        for _ in range(3):
            assert det.detect(small) == []

    def test_whole_frame_flash_is_not_a_person(self):
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())
        flash = np.full((FRAME_H, FRAME_W, 3), 40, dtype=np.uint8)
        for _ in range(3):
            detections = det.detect(flash)
        assert all(d.area_ratio <= det.max_area_ratio for d in detections)

    def test_reset_motion_forgets_background(self):
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())
        det.detect(frame_with_block(40, 40))
        det.reset_motion()
        # After reset the very first frame is background learning again.
        assert det.detect(blank_frame()) == []

    def test_person_visible_helper(self):
        det = SilhouetteDetector(use_hog=False)
        det.detect(blank_frame())
        assert det.person_visible(blank_frame()) is False
        for i in range(3):
            visible = det.person_visible(frame_with_block(100 + i * 4, 30))
        assert visible is True


class TestDecodePaths:
    def test_accepts_png_bytes(self):
        det = SilhouetteDetector(use_hog=False, use_motion=False)
        assert det.detect(encode_png(blank_frame())) == []

    def test_rejects_undecodable_input(self):
        det = SilhouetteDetector(use_hog=False, use_motion=False)
        with pytest.raises(ValueError):
            det.detect(b"not an image")

    def test_summarize_swallows_decode_errors(self):
        det = SilhouetteDetector(use_hog=False)
        assert summarize(det, b"garbage").person_visible is False

    def test_summarize_without_detector_reports_absent(self):
        summary = summarize(None, blank_frame())
        assert summary.person_visible is False
        assert summary.best_confidence == 0.0


class TestHogPath:
    def test_hog_runs_and_returns_list_on_synthetic_frame(self):
        det = SilhouetteDetector(use_motion=False)
        result = det.detect(blank_frame())
        assert isinstance(result, list)
        assert all(d.source == "hog" for d in result)

    def test_plausibility_bounds(self):
        det = SilhouetteDetector(use_motion=False)
        frame_size = (FRAME_W, FRAME_H)
        # 3% of the frame is the floor.
        assert det._plausible(48, 48, frame_size) is True
        assert det._plausible(5, 5, frame_size) is False
        assert det._plausible(FRAME_W, FRAME_H, frame_size) is False
        assert det._plausible(10, 10, (0, 0)) is False

    def test_invalid_area_bounds_rejected(self):
        with pytest.raises(ValueError):
            SilhouetteDetector(min_area_ratio=0.5, max_area_ratio=0.4)


class TestDedupe:
    def test_motion_box_overlapping_hog_box_is_dropped(self):
        hog_box = PersonDetection(
            bbox=(40, 40, 90, 150), confidence=0.9, source="hog",
            frame_size=(FRAME_W, FRAME_H),
        )
        motion_box = PersonDetection(
            bbox=(45, 45, 90, 150), confidence=0.5, source="motion",
            frame_size=(FRAME_W, FRAME_H),
        )
        # Unit-level: exercise the merge rule directly.
        from aoep_webcam_vision.silhouette import _overlap_ratio

        assert _overlap_ratio(hog_box.bbox, motion_box.bbox) > 0.5
        assert _overlap_ratio(hog_box.bbox, (200, 10, 50, 80)) == 0.0
