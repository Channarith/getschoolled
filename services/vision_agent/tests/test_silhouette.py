"""Tests for aoep_shared.vision.silhouette (SilhouetteDetector).

Tests run without OpenCV by checking the pure-logic helpers; the OpenCV-dependent
``SilhouetteDetector`` tests are skipped when cv2 is not available.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Pure-logic (no OpenCV)
# ---------------------------------------------------------------------------

def test_estimate_silhouette_from_fraction_present():
    from aoep_shared.vision.silhouette import estimate_silhouette_from_fraction
    assert estimate_silhouette_from_fraction(0.10) is True   # 10% — clear person
    assert estimate_silhouette_from_fraction(0.04) is True   # 4% — minimum


def test_estimate_silhouette_from_fraction_absent():
    from aoep_shared.vision.silhouette import estimate_silhouette_from_fraction
    assert estimate_silhouette_from_fraction(0.01) is False  # too small
    assert estimate_silhouette_from_fraction(0.90) is False  # whole frame moving


def test_silhouette_result_defaults():
    from aoep_shared.vision.silhouette import SilhouetteResult
    r = SilhouetteResult(
        silhouette_present=False,
        num_blobs=0,
        largest_blob_area=0.0,
        largest_blob_bbox=None,
        confidence=0.0,
    )
    assert r.silhouette_present is False
    assert r.confidence == 0.0
    assert r.mask_png is None


# ---------------------------------------------------------------------------
# OpenCV-dependent tests (skipped when cv2 not installed)
# ---------------------------------------------------------------------------

cv2 = pytest.importorskip("cv2", reason="opencv not installed")
np = pytest.importorskip("numpy", reason="numpy not installed")


def _make_blank_frame(w=320, h=240, color=(50, 50, 50)) -> bytes:
    """Create a solid-colour PNG frame for testing."""
    img = np.full((h, w, 3), color, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _make_frame_with_blob(
    w=320, h=240, bg_color=(50, 50, 50), blob_color=(200, 200, 200)
) -> bytes:
    """Create a frame with a large bright rectangle (simulates a person)."""
    img = np.full((h, w, 3), bg_color, dtype=np.uint8)
    # Rectangle covering ~25% of frame (well above min threshold).
    cv2.rectangle(img, (80, 40), (240, 200), blob_color, thickness=-1)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_detector_blank_frame_no_silhouette():
    from aoep_shared.vision.silhouette import SilhouetteDetector
    det = SilhouetteDetector()
    frame = _make_blank_frame()
    # First frames: background model warms up; no signal yet.
    for _ in range(16):
        result = det.process_frame(frame)
    # All identical frames -> no foreground.
    assert not result.silhouette_present


def test_detector_moving_blob_detected():
    from aoep_shared.vision.silhouette import SilhouetteDetector
    det = SilhouetteDetector()
    bg = _make_blank_frame()
    # Seed background with blank frames.
    for _ in range(20):
        det.process_frame(bg)
    # Now introduce a large bright blob -> should be detected as foreground.
    fg = _make_frame_with_blob()
    result = det.process_frame(fg)
    # Silhouette should be detected.
    assert result.silhouette_present
    assert result.num_blobs >= 1
    assert result.largest_blob_area > 0.0
    assert result.confidence > 0.0


def test_detector_invalid_bytes_safe():
    from aoep_shared.vision.silhouette import SilhouetteDetector
    det = SilhouetteDetector()
    result = det.process_frame(b"not an image")
    assert not result.silhouette_present
    assert result.confidence == 0.0


def test_detector_mask_returned_when_requested():
    from aoep_shared.vision.silhouette import SilhouetteDetector
    det = SilhouetteDetector(return_mask=True)
    bg = _make_blank_frame()
    for _ in range(20):
        det.process_frame(bg)
    fg = _make_frame_with_blob()
    result = det.process_frame(fg)
    # Mask PNG bytes returned (may be empty if no foreground, but not None).
    assert result.mask_png is not None


def test_detector_reset_clears_background_model():
    from aoep_shared.vision.silhouette import SilhouetteDetector
    det = SilhouetteDetector()
    bg = _make_blank_frame()
    for _ in range(20):
        det.process_frame(bg)
    det.reset()
    assert det._frames_seen == 0
