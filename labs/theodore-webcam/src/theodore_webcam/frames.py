"""Frame decoding helpers.

Frames arrive from the browser as data URLs or bare base64 JPEG/PNG. They are
decoded into a BGR ndarray, used, and dropped: nothing is written to disk.
"""

from __future__ import annotations

import base64
import binascii
from typing import Union

import cv2
import numpy as np


class FrameDecodeError(ValueError):
    """Raised when a submitted frame cannot be decoded into an image."""


def strip_data_url(payload: str) -> str:
    if payload.startswith("data:"):
        _, _, tail = payload.partition(",")
        return tail
    return payload


def decode_frame(payload: Union[str, bytes], *, max_bytes: int = 4_000_000) -> np.ndarray:
    """Decode a base64/data-URL/raw image payload into a BGR ndarray."""

    if isinstance(payload, str):
        cleaned = strip_data_url(payload).strip()
        if not cleaned:
            raise FrameDecodeError("empty frame payload")
        if len(cleaned) > max_bytes * 2:
            raise FrameDecodeError("frame payload too large")
        try:
            raw = base64.b64decode(cleaned, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise FrameDecodeError(f"invalid base64 frame: {exc}") from exc
    else:
        raw = bytes(payload)

    if not raw:
        raise FrameDecodeError("empty frame payload")
    if len(raw) > max_bytes:
        raise FrameDecodeError("frame payload too large")

    buffer = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise FrameDecodeError("frame is not a decodable image")
    return image
