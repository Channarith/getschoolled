"""Turn one camera frame into identified observations."""

from __future__ import annotations

import numpy as np

from .depth import align_depth, distance_m
from .detect import detect
from .embed import embed_rgb
from .gallery import ObjectGallery
from .sensors import apply_sensors
from .types import Frame, Observation


def crop_rgb(rgb: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox
    height, width = rgb.shape[:2]
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(width, int(x + w))
    y1 = min(height, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return rgb
    return rgb[y0:y1, x0:x1]


def observe(
    frame: Frame,
    gallery: ObjectGallery,
    *,
    detector: str = "auto",
    identify_threshold: float = 0.75,
) -> list[Observation]:
    """Detect, measure distance, and match the training gallery."""
    depth = None
    if frame.depth is not None:
        depth = align_depth(frame.depth, frame.rgb.shape)
    observations: list[Observation] = []
    for det in detect(frame, detector):
        dist = distance_m(depth, det.bbox, frame.depth_scale) if depth is not None else None
        crop = crop_rgb(frame.rgb, det.bbox)
        hit = gallery.match(embed_rgb(crop), threshold=identify_threshold)
        observations.append(Observation(
            label=det.label,
            score=round(float(det.score), 3),
            bbox=det.bbox,
            distance_m=dist,
            kind=hit.kind if hit and hit.kind else det.kind,
            camera=frame.camera,
            source=det.source,
            identified=hit.label if hit else None,
            identify_score=round(hit.score, 3) if hit else 0.0,
            maker=hit.maker if hit else "",
            year=hit.year if hit else None,
            heat_c=hit.heat_c if hit else None,
            heat_source="trained" if hit and hit.heat_c is not None else "",
            smell=hit.smell if hit else "",
            smell_intensity=hit.smell_intensity if hit else None,
            smell_source="trained" if hit and hit.smell else "",
            texture=hit.texture if hit else "",
            force_n=hit.force_n if hit else None,
            touch_source="trained" if hit and (hit.texture or hit.force_n is not None) else "",
        ))
    observations.sort(key=lambda obs: obs.distance_m if obs.distance_m is not None else 1e9)
    apply_sensors(observations, frame.sensors, frame.rgb.shape)
    return observations
