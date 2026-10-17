"""Metric distance and object blobs from a depth map.

No learned model. Two surfaces at different distances stay separate objects,
which is what answers "how far is it?" before anything has been trained.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .taxonomy import kind_for
from .types import Detection


def align_depth(depth: np.ndarray, rgb_shape: tuple[int, ...]) -> np.ndarray:
    """Nearest-neighbor resize so depth lines up with the RGB frame."""
    height, width = int(rgb_shape[0]), int(rgb_shape[1])
    if depth.shape[0] == height and depth.shape[1] == width:
        return depth
    ys = np.linspace(0, depth.shape[0] - 1, height).astype(np.int32)
    xs = np.linspace(0, depth.shape[1] - 1, width).astype(np.int32)
    return depth[ys][:, xs]


def distance_m(
    depth: np.ndarray,
    bbox: tuple[int, int, int, int],
    scale: float,
    *,
    min_pixels: int = 8,
) -> Optional[float]:
    """Median depth inside ``bbox``, in meters. Zeros are missing pixels."""
    x, y, w, h = bbox
    height, width = depth.shape[:2]
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(width, int(x + w))
    y1 = min(height, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = np.asarray(depth[y0:y1, x0:x1], dtype=np.float32)
    valid = crop[np.isfinite(crop) & (crop > 0)]
    if valid.size < min_pixels:
        return None
    return float(np.median(valid) * float(scale))


def _components(band: np.ndarray, min_cells: int) -> list[tuple[int, int, int, int]]:
    """4-connected boxes of equal nonzero band ids. Coordinates are in ``band``."""
    height, width = band.shape
    labels = np.zeros((height, width), dtype=np.int32)
    parent = [0]

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    nxt = 0
    for y in range(height):
        for x in range(width):
            value = int(band[y, x])
            if value == 0:
                continue
            left = int(labels[y, x - 1]) if x and int(band[y, x - 1]) == value else 0
            up = int(labels[y - 1, x]) if y and int(band[y - 1, x]) == value else 0
            if left and up:
                labels[y, x] = left
                ra, rb = find(left), find(up)
                if ra != rb:
                    parent[rb] = ra
            elif left or up:
                labels[y, x] = left or up
            else:
                nxt += 1
                parent.append(nxt)
                labels[y, x] = nxt

    boxes: dict[int, list[int]] = {}
    for y in range(height):
        for x in range(width):
            lab = int(labels[y, x])
            if not lab:
                continue
            root = find(lab)
            box = boxes.get(root)
            if box is None:
                boxes[root] = [x, y, x, y, 1]
            else:
                box[0] = min(box[0], x)
                box[1] = min(box[1], y)
                box[2] = max(box[2], x)
                box[3] = max(box[3], y)
                box[4] += 1

    out: list[tuple[int, int, int, int]] = []
    for minx, miny, maxx, maxy, count in boxes.values():
        if count < min_cells:
            continue
        out.append((minx, miny, maxx - minx + 1, maxy - miny + 1))
    return out


def depth_detections(
    depth: np.ndarray,
    scale: float,
    *,
    min_m: float = 0.15,
    max_m: float = 4.0,
    band_m: float = 0.4,
    max_side: int = 160,
    min_cells: int = 40,
    limit: int = 8,
) -> list[Detection]:
    """Split a depth map into nearby object boxes, nearest first."""
    if depth is None or depth.size == 0:
        return []
    height, width = depth.shape[:2]
    step = max(1, int(max(height, width) / max_side))
    small = np.asarray(depth[::step, ::step], dtype=np.float32)
    meters = small * float(scale)
    valid = np.isfinite(meters) & (meters >= min_m) & (meters <= max_m)
    band = np.zeros(meters.shape, dtype=np.int32)
    band[valid] = np.floor(meters[valid] / band_m).astype(np.int32) + 1
    found = _components(band, min_cells)
    detections: list[tuple[float, Detection]] = []
    for x, y, w, h in found:
        bbox = (
            int(x * step),
            int(y * step),
            max(1, int(w * step)),
            max(1, int(h * step)),
        )
        dist = distance_m(depth, bbox, scale)
        if dist is None:
            continue
        detections.append((dist, Detection(
            label="object",
            score=1.0,
            bbox=bbox,
            kind=kind_for("object"),
            source="depth",
        )))
    detections.sort(key=lambda item: item[0])
    return [det for _, det in detections[:limit]]
