"""Tests for the silhouette geometry core (pure, no OpenCV needed)."""

from __future__ import annotations

from webcam_recognition.silhouette import (
    SilhouetteBox,
    analyze_mask,
    summarize_frame,
)


def _mask(w, h, box=None):
    rows = [[0] * w for _ in range(h)]
    if box:
        x, y, bw, bh = box
        for yy in range(y, y + bh):
            for xx in range(x, x + bw):
                rows[yy][xx] = 1
    return rows


def test_analyze_mask_finds_bounding_box():
    mask = _mask(20, 20, box=(4, 5, 8, 10))  # 80/400 = 20% coverage
    box = analyze_mask(mask, min_coverage=0.03)
    assert box is not None
    assert box.bbox == (4, 5, 8, 10)
    assert box.frame_size == (20, 20)
    assert abs(box.coverage - 0.20) < 1e-6


def test_analyze_mask_ignores_tiny_foreground():
    mask = _mask(20, 20, box=(0, 0, 1, 1))  # 0.25% coverage
    assert analyze_mask(mask, min_coverage=0.03) is None


def test_analyze_mask_empty():
    assert analyze_mask(_mask(10, 10), min_coverage=0.01) is None
    assert analyze_mask([], min_coverage=0.01) is None


def test_silhouette_box_centered_and_coverage():
    centered = SilhouetteBox(bbox=(45, 0, 10, 50), confidence=0.9, frame_size=(100, 50))
    assert centered.centered > 0.95
    edge = SilhouetteBox(bbox=(0, 0, 10, 50), confidence=0.9, frame_size=(100, 50))
    assert edge.centered < 0.15
    assert abs(centered.coverage - (10 * 50) / (100 * 50)) < 1e-6


def test_summarize_frame_present_from_body_only():
    body = SilhouetteBox(bbox=(10, 0, 40, 90), confidence=0.8, frame_size=(100, 100))
    fp = summarize_frame([body], face_count=0, min_coverage=0.03)
    assert fp.person_present is True  # body OR face
    assert fp.people_count == 1
    assert fp.largest_coverage > 0.03


def test_summarize_frame_present_from_face_only():
    fp = summarize_frame([], face_count=1, attention=0.8, min_coverage=0.03)
    assert fp.person_present is True
    assert fp.face_count == 1
    assert fp.attention == 0.8


def test_summarize_frame_absent():
    fp = summarize_frame([], face_count=0)
    assert fp.person_present is False
    assert fp.people_count == 0


def test_summarize_drops_tiny_silhouettes():
    tiny = SilhouetteBox(bbox=(0, 0, 2, 2), confidence=0.1, frame_size=(100, 100))
    fp = summarize_frame([tiny], face_count=0, min_coverage=0.03)
    assert fp.person_present is False
    assert fp.silhouettes == []


def test_frame_perception_as_dict():
    body = SilhouetteBox(bbox=(10, 0, 40, 90), confidence=0.8, frame_size=(100, 100))
    d = summarize_frame([body], face_count=1, attention=0.5).as_dict()
    assert d["person_present"] is True
    assert d["silhouettes"][0]["bbox"] == [10, 0, 40, 90]
    assert "coverage" in d["silhouettes"][0]
