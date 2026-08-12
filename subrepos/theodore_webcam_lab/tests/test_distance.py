from __future__ import annotations

from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
from theodore_webcam_lab.distance import (
    face_size_ratio_from_bbox,
    face_size_ratio_from_dark_bbox,
    metres_from_face_size_ratio,
    resolve_distance,
)
from theodore_webcam_lab.types import ClassMode, WebcamSignal
from theodore_webcam_lab.vision_tuning import VisionTuning


def test_larger_face_means_closer_distance():
    close = metres_from_face_size_ratio(0.40)
    far = metres_from_face_size_ratio(0.10)
    assert close is not None and far is not None
    assert close < far


def test_bbox_linear_ratio_not_area():
    # 320x240 face in 1280x720 frame → height ratio 240/720=0.333, not area ~0.083
    ratio = face_size_ratio_from_bbox(
        box_width=320, box_height=240, frame_width=1280, frame_height=720
    )
    assert ratio is not None
    assert 0.30 <= ratio <= 0.35


def test_lidar_measurement_preferred_over_face_size():
    est = resolve_distance(measured_m=0.82, face_size_ratio=0.20)
    assert est.source == "lidar"
    assert est.distance_m == 0.82


def test_dark_bbox_yields_face_size_and_metres():
    h, w = 36, 64
    grid = [[0.7 for _ in range(w)] for _ in range(h)]
    for y in range(8, 28):
        for x in range(20, 44):
            grid[y][x] = 0.15
    ratio = face_size_ratio_from_dark_bbox(grid)
    assert ratio is not None and ratio > 0.1
    est = resolve_distance(luminance_grid=grid)
    assert est.source == "face_size"
    assert est.distance_m is not None


def test_analyzer_uses_lidar_signal_metres():
    result = WebcamSessionAnalyzer().evaluate(
        session_id="lidar-1",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1,
                face_count=1,
                liveness_state="live",
                face_size_ratio=0.2,
                distance_from_camera_m=0.91,
                distance_source="lidar",
            )
        ],
    )
    p = result.participants[0]
    assert p.distance_from_camera_m == 0.91
    assert p.distance_source == "lidar"


def test_analyzer_estimates_distance_from_grid_alone():
    h, w = 36, 64
    grid = [[0.65 for _ in range(w)] for _ in range(h)]
    for y in range(6, 30):
        for x in range(18, 46):
            grid[y][x] = 0.12
    result = WebcamSessionAnalyzer(tuning=VisionTuning()).evaluate(
        session_id="grid-dist",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1,
                face_count=1,
                liveness_state="live",
                luminance_grid=grid,
            )
        ],
    )
    p = result.participants[0]
    assert p.distance_from_camera_m is not None
    assert p.distance_source == "face_size"
    assert 0.3 <= p.distance_from_camera_m <= 4.0
