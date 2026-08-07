"""Distance-from-camera estimation.

Priority:
  1. Client-measured metres (LiDAR / depth camera / native bridge)
  2. Face size vs window frame — larger face ⇒ closer
     ``distance = reference_m * (reference_face_ratio / observed_face_ratio)``

``face_size_ratio`` is a *linear* face size relative to the frame (prefer face
height / frame height). Area ratios are converted when needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .vision_tuning import VisionTuning


@dataclass(frozen=True)
class DistanceEstimate:
    distance_m: float | None
    source: str  # lidar | face_size | none
    face_size_ratio: float | None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def face_size_ratio_from_bbox(
    *,
    box_width: float,
    box_height: float,
    frame_width: float,
    frame_height: float,
) -> float | None:
    """Linear face size = max(face_w/frame_w, face_h/frame_h). Larger ⇒ closer."""
    if frame_width <= 0 or frame_height <= 0:
        return None
    if box_width <= 0 or box_height <= 0:
        return None
    ratio = max(box_width / frame_width, box_height / frame_height)
    return _clamp(ratio, 0.02, 0.95)


def face_size_ratio_from_dark_bbox(grid: list[list[float]]) -> float | None:
    """Estimate linear face size from the dark-pixel bounding box in a luminance grid."""
    if not grid or not grid[0]:
        return None
    h = len(grid)
    w = len(grid[0])
    if h < 8 or w < 8:
        return None
    vals = [float(v) for row in grid for v in row]
    mean = sum(vals) / len(vals)
    thr = mean - 0.04
    min_x, min_y, max_x, max_y = w, h, -1, -1
    count = 0
    for y, row in enumerate(grid):
        if len(row) != w:
            continue
        for x, raw in enumerate(row):
            if float(raw) < thr:
                count += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if count < max(8, (h * w) // 80) or max_x < min_x or max_y < min_y:
        return None
    box_w = (max_x - min_x + 1) / w
    box_h = (max_y - min_y + 1) / h
    # Person bbox is taller than the face; scale torso+head bbox down toward face.
    face_like = max(box_w * 0.85, box_h * 0.55)
    return _clamp(face_like, 0.04, 0.85)


def metres_from_face_size_ratio(
    ratio: float | None, tuning: VisionTuning | None = None
) -> float | None:
    if ratio is None or ratio <= 0.0:
        return None
    tuning = tuning or VisionTuning()
    effective = max(tuning.distance_min_face_ratio, ratio)
    distance = tuning.distance_reference_metres * (
        tuning.distance_reference_face_ratio / effective
    )
    return round(
        _clamp(distance, tuning.distance_min_metres, tuning.distance_max_metres), 2
    )


def resolve_distance(
    *,
    measured_m: float | None = None,
    face_size_ratio: float | None = None,
    luminance_grid: list[list[float]] | None = None,
    tuning: VisionTuning | None = None,
) -> DistanceEstimate:
    """Prefer LiDAR/depth metres; otherwise derive from face size in the frame."""
    tuning = tuning or VisionTuning()
    if measured_m is not None and measured_m > 0.0:
        clipped = round(
            _clamp(float(measured_m), tuning.distance_min_metres, tuning.distance_max_metres),
            2,
        )
        return DistanceEstimate(
            distance_m=clipped, source="lidar", face_size_ratio=face_size_ratio
        )

    ratio = face_size_ratio
    if ratio is None and luminance_grid is not None:
        ratio = face_size_ratio_from_dark_bbox(luminance_grid)
    metres = metres_from_face_size_ratio(ratio, tuning)
    if metres is None:
        return DistanceEstimate(distance_m=None, source="none", face_size_ratio=ratio)
    return DistanceEstimate(distance_m=metres, source="face_size", face_size_ratio=ratio)
