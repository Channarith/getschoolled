"""Silhouette and body-presence detection via OpenCV background subtraction.

Uses MOG2 (Mixture of Gaussians v2) background modelling plus contour analysis to
detect a human-sized blob in a webcam frame without a separate pose or person
model. The same opencv-contrib-python-headless that the perception service already
uses is the only dependency.

Primary use cases (vision_agent service):
- Detect user presence even when no face is visible (user is looking away, or
  partially off-camera) so that Theodore can distinguish "user is here but
  distracted" from "user left the session".
- Power the absence-detection policy: face_missing AND silhouette_missing ->
  ABSENT; face_missing but silhouette_present -> PRESENT_SILHOUETTE.
- Provide a normalized silhouette mask as a lightweight privacy screen that
  downstream analytics can consume without exposing the raw frame.

Algorithm
---------
1. Decode the JPEG/PNG frame into a numpy array via OpenCV.
2. Resize to a fixed analysis size (320x240) for speed.
3. Apply the per-session MOG2 background subtractor to produce a foreground mask.
4. Morphological open/close to remove noise, then find contours.
5. Keep contours whose bounding box satisfies the human-silhouette heuristics
   (area ≥ min_area, aspect ratio in reasonable range, vertically elongated).
6. Optionally return the mask (as PNG bytes) for client overlays.

Statefulness
------------
``SilhouetteDetector`` is stateful — it holds the MOG2 model which learns the
scene background over several frames. One instance per webcam session. The
``PresenceSignal`` dataclass is the serialisation-friendly output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Presence signal (returned per-frame; JSON-serialisable)
# ---------------------------------------------------------------------------

@dataclass
class SilhouetteResult:
    """Per-frame result from the silhouette detector."""
    silhouette_present: bool
    num_blobs: int
    largest_blob_area: float   # fraction of frame area, 0..1
    largest_blob_bbox: Optional[Tuple[int, int, int, int]]  # x, y, w, h in analysis coords
    confidence: float          # 0..1 — how certain we are that a person is present
    mask_png: Optional[bytes] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Heuristic thresholds (tuned for a standard webcam at ~320x240 analysis size)
# ---------------------------------------------------------------------------
_ANALYSIS_W = 320
_ANALYSIS_H = 240
_ANALYSIS_SIZE = (_ANALYSIS_W, _ANALYSIS_H)

# Minimum foreground area to count as a meaningful blob (fraction of frame).
_MIN_BLOB_FRACTION = 0.04      # ~4 % of analysis frame = ~3 000 px at 320x240
# Maximum blob fraction (avoids a fully-lit/all-motion frame as "person").
_MAX_BLOB_FRACTION = 0.85
# Aspect ratio (h/w) range for a plausible human silhouette standing or seated.
_MIN_ASPECT = 0.5              # very wide (lying down or arms spread)
_MAX_ASPECT = 4.5              # very tall column


def _import_cv2():
    try:
        import cv2  # type: ignore[import-untyped]
        return cv2
    except ImportError as exc:
        raise ImportError(
            "opencv-contrib-python-headless is required for silhouette detection. "
            "Install it: pip install opencv-contrib-python-headless==4.10.0.84"
        ) from exc


def _import_numpy():
    try:
        import numpy as np  # type: ignore[import-untyped]
        return np
    except ImportError as exc:
        raise ImportError(
            "numpy is required for silhouette detection. "
            "Install it: pip install numpy==1.26.4"
        ) from exc


# ---------------------------------------------------------------------------
# Main detector (one instance per session)
# ---------------------------------------------------------------------------

class SilhouetteDetector:
    """Stateful per-session silhouette detector backed by OpenCV MOG2.

    Create one instance when a webcam session begins and call ``process_frame``
    for each frame.  The background model improves over the first ~30 frames.

    Parameters
    ----------
    min_blob_fraction:
        Override for the minimum foreground blob area threshold (fraction of frame
        area 0..1). Raise for stable scenes; lower for dim/noisy cameras.
    return_mask:
        When True, ``SilhouetteResult.mask_png`` is populated with a PNG-encoded
        foreground mask for client-side overlays. Adds ~2 ms per frame on CPU.
    """

    def __init__(
        self,
        *,
        min_blob_fraction: float = _MIN_BLOB_FRACTION,
        return_mask: bool = False,
    ) -> None:
        cv2 = _import_cv2()
        self._cv2 = cv2
        self._np = _import_numpy()
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=100,
            varThreshold=30,
            detectShadows=False,
        )
        self._min_area = min_blob_fraction * _ANALYSIS_W * _ANALYSIS_H
        self._return_mask = return_mask
        self._frames_seen: int = 0
        # Morphological kernels (pre-built once).
        self._kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    def process_frame(self, image_bytes: bytes) -> SilhouetteResult:
        """Detect human silhouette in a JPEG or PNG frame.

        Parameters
        ----------
        image_bytes:
            Raw bytes of a JPEG or PNG image (from a webcam capture).

        Returns
        -------
        SilhouetteResult
            Per-frame result; inspect ``silhouette_present`` and ``confidence``.
        """
        cv2 = self._cv2
        np = self._np

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        # Count undecodable frames too — otherwise a client streaming garbage
        # keeps _frames_seen at 0 and the warm-up gate never ends (the session
        # would sit in WARMING_UP forever with no presence detection).
        self._frames_seen += 1
        if frame is None:
            return SilhouetteResult(
                silhouette_present=False,
                num_blobs=0,
                largest_blob_area=0.0,
                largest_blob_bbox=None,
                confidence=0.0,
            )

        small = cv2.resize(frame, _ANALYSIS_SIZE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Warm up the background model for the first 10 frames without signalling.
        # (_frames_seen was already incremented above, before the decode check.)
        learning_rate = 0.05 if self._frames_seen <= 10 else -1

        fg_mask = self._bg_sub.apply(gray, learningRate=learning_rate)

        # Remove small noise via open, then fill gaps via close.
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel_open)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel_close)

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        total_px = _ANALYSIS_W * _ANALYSIS_H
        human_blobs: List[Tuple[int, int, int, int, float]] = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < self._min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            aspect = h / max(w, 1)
            blob_frac = area / total_px
            if blob_frac > _MAX_BLOB_FRACTION:
                continue
            if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT):
                continue
            human_blobs.append((x, y, w, h, area))

        num_blobs = len(human_blobs)
        if num_blobs == 0:
            mask_png = _encode_mask(cv2, fg_mask) if self._return_mask else None
            return SilhouetteResult(
                silhouette_present=False,
                num_blobs=0,
                largest_blob_area=0.0,
                largest_blob_bbox=None,
                confidence=0.0,
                mask_png=mask_png,
            )

        # Largest qualifying blob.
        largest = max(human_blobs, key=lambda b: b[4])
        lx, ly, lw, lh, la = largest
        blob_frac = la / total_px
        # Confidence: grows with blob size (up to 1.0 around 30 % of frame).
        confidence = min(1.0, math.sqrt(blob_frac / 0.30))
        # Reduce confidence during warm-up (background model not yet stable).
        if self._frames_seen < 15:
            confidence *= self._frames_seen / 15.0

        mask_png = _encode_mask(cv2, fg_mask) if self._return_mask else None
        return SilhouetteResult(
            silhouette_present=True,
            num_blobs=num_blobs,
            largest_blob_area=round(blob_frac, 4),
            largest_blob_bbox=(lx, ly, lw, lh),
            confidence=round(confidence, 4),
            mask_png=mask_png,
        )

    def reset(self) -> None:
        """Reset the background model (e.g. after a scene cut / background change)."""
        cv2 = self._cv2
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=100, varThreshold=30, detectShadows=False
        )
        self._frames_seen = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_mask(cv2, mask) -> bytes:
    """Encode a uint8 foreground mask as PNG bytes."""
    ok, buf = cv2.imencode(".png", mask)
    if not ok:
        return b""
    return buf.tobytes()


# ---------------------------------------------------------------------------
# Stateless helper: fast presence check from raw numpy array (for unit tests)
# ---------------------------------------------------------------------------

def estimate_silhouette_from_fraction(blob_area_fraction: float) -> bool:
    """Return True if the blob area fraction suggests a person is present.

    A convenience function for tests and the offline fallback path that cannot
    run the full OpenCV pipeline.
    """
    return (
        _MIN_BLOB_FRACTION <= blob_area_fraction <= _MAX_BLOB_FRACTION
    )
