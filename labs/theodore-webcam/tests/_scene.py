"""Synthetic webcam scenes.

The lab must be testable and demonstrable on a machine with no camera, so the
tests render a deterministic "room" and draw a human silhouette into it. The
shapes match what the detector keys on (head narrower than shoulders, a body
that does not fill its bounding box), which is what makes these frames a fair
exercise of the detector rather than a rubber stamp.
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

WIDTH = 480
HEIGHT = 360


def empty_room(
    width: int = WIDTH, height: int = HEIGHT, *, brightness: int = 0
) -> np.ndarray:
    """A static room: wall gradient, a window, a desk edge, fixed noise."""

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    column = np.linspace(70, 130, width, dtype=np.float32)
    frame[:, :, 0] = column
    frame[:, :, 1] = column * 0.95
    frame[:, :, 2] = column * 0.88

    cv2.rectangle(frame, (int(width * 0.62), int(height * 0.08)),
                  (int(width * 0.94), int(height * 0.45)), (185, 180, 165), -1)
    cv2.rectangle(frame, (0, int(height * 0.82)), (width, height), (58, 60, 66), -1)
    cv2.rectangle(frame, (int(width * 0.05), int(height * 0.16)),
                  (int(width * 0.30), int(height * 0.42)), (96, 104, 118), -1)

    rng = np.random.default_rng(7)
    noise = rng.integers(-4, 5, size=(height, width, 1), dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise + int(brightness), 0, 255).astype(np.uint8)
    return frame


def person_scene(
    width: int = WIDTH,
    height: int = HEIGHT,
    *,
    center_x: float = 0.5,
    body_height: float = 0.62,
    body_width: float = 0.22,
    shade: Tuple[int, int, int] = (34, 36, 44),
    base: Optional[np.ndarray] = None,
) -> np.ndarray:
    """The same room with a person-shaped body in front of the camera."""

    frame = empty_room(width, height) if base is None else base.copy()
    cx = int(width * center_x)
    body_h = int(height * body_height)
    body_w = int(width * body_width)
    top = height - body_h
    bottom = height

    head_ry = int(body_w * 0.34)
    head_rx = int(body_w * 0.28)
    head_cy = top + head_ry
    cv2.ellipse(frame, (cx, head_cy), (head_rx, head_ry), 0, 0, 360, shade, -1)

    shoulder_y = head_cy + int(head_ry * 1.25)
    torso = np.array(
        [
            [cx - body_w // 2, shoulder_y + int(body_h * 0.06)],
            [cx - int(body_w * 0.34), shoulder_y],
            [cx + int(body_w * 0.34), shoulder_y],
            [cx + body_w // 2, shoulder_y + int(body_h * 0.06)],
            [cx + int(body_w * 0.40), bottom],
            [cx - int(body_w * 0.40), bottom],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [torso], shade)
    return frame


def moved_chair(width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """A wide low box: furniture moved, definitely not a learner."""

    frame = empty_room(width, height)
    cv2.rectangle(
        frame,
        (int(width * 0.12), int(height * 0.60)),
        (int(width * 0.42), int(height * 0.76)),
        (28, 30, 36),
        -1,
    )
    return frame
