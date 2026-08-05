"""Silhouette detection: present / partial / absent on synthetic frames."""

from __future__ import annotations

import numpy as np
import pytest

from webcam_classroom.silhouette import (
    ABSENT,
    PARTIAL,
    PRESENT,
    SilhouetteConfig,
    SilhouetteReading,
    detect_silhouette,
    silhouette_from_faces,
)


def _frame(bg: int = 200) -> np.ndarray:
    return np.full((240, 320, 3), bg, dtype=np.uint8)


def _with_block(bg: int, fg: int, frac_w: float, frac_h: float) -> np.ndarray:
    """A background frame with a centred dark block of the given size fraction."""
    img = _frame(bg)
    h, w = img.shape[:2]
    bw, bh = int(w * frac_w), int(h * frac_h)
    x0 = (w - bw) // 2
    y0 = (h - bh) // 2
    img[y0:y0 + bh, x0:x0 + bw, :] = fg
    return img


def test_empty_frame_is_absent():
    r = detect_silhouette(_frame(200))
    assert isinstance(r, SilhouetteReading)
    assert r.state == ABSENT
    assert r.present is False
    assert r.coverage < 0.03


def test_large_centered_block_is_present():
    # A big dark subject filling ~45% width x 70% height of the frame.
    r = detect_silhouette(_with_block(210, 40, 0.45, 0.70))
    assert r.state == PRESENT
    assert r.present is True
    assert r.coverage >= 0.10
    # Centred subject -> centroid near the middle.
    assert abs(r.centroid[0] - 0.5) < 0.2
    assert abs(r.centroid[1] - 0.5) < 0.2
    assert r.regions >= 1


def test_small_block_is_partial():
    # A small subject that clears the partial threshold but not present.
    cfg = SilhouetteConfig(present_coverage=0.25, partial_coverage=0.02)
    r = detect_silhouette(_with_block(210, 40, 0.18, 0.18), cfg)
    assert r.state == PARTIAL
    assert r.present is False


def test_pure_grid_path_needs_no_numpy():
    # A hand-built luminance grid: bright border, dark centre block.
    grid = [[0.85] * 10 for _ in range(10)]
    for r in range(3, 7):
        for c in range(3, 7):
            grid[r][c] = 0.1
    reading = detect_silhouette(grid, SilhouetteConfig(present_coverage=0.10, grid=10))
    assert reading.present is True
    assert reading.state == PRESENT
    assert reading.coverage >= 0.10


def test_undecodable_bytes_raise():
    from webcam_classroom.silhouette import SilhouetteUnavailable

    with pytest.raises(SilhouetteUnavailable):
        detect_silhouette(b"not-an-image")


class _FakeFace:
    def __init__(self, bbox, frame_size):
        self.bbox = bbox
        self.frame_size = frame_size


def test_silhouette_from_faces_present_and_absent():
    # One reasonably sized face -> present silhouette.
    face = _FakeFace(bbox=(120, 60, 90, 110), frame_size=(320, 240))
    present = silhouette_from_faces([face])
    assert present.present is True
    assert present.source == "faces"
    assert present.regions == 1

    # No faces -> absent.
    empty = silhouette_from_faces([])
    assert empty.present is False
    assert empty.state == ABSENT
