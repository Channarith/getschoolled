"""Silhouette / person-shape detection for webcam frames.

Uses OpenCV HOG person detector when available. Falls back to a foreground
blob heuristic (motion + contiguous mid-frame mass) so the lab still runs in
CPU-only / headless environments without person models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SilhouetteHit:
    """A detected person-shaped region in frame coordinates."""

    bbox: Tuple[int, int, int, int]  # x, y, w, h
    score: float
    source: str  # hog | blob | injected


class SilhouetteDetector:
    """Detect learner silhouettes (body shape) without requiring a face.

    Parameters
    ----------
    min_area_ratio:
        Minimum bbox area as a fraction of the frame (filters noise).
    blob_threshold:
        Grayscale intensity threshold for the blob fallback (0..255).
    """

    def __init__(
        self,
        *,
        min_area_ratio: float = 0.02,
        blob_threshold: int = 40,
        use_hog: bool = True,
    ) -> None:
        self.min_area_ratio = max(0.0, float(min_area_ratio))
        self.blob_threshold = max(0, min(255, int(blob_threshold)))
        self._hog = None
        self._cv2 = None
        self._np = None
        if use_hog:
            self._try_init_hog()

    def _try_init_hog(self) -> None:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            return
        self._cv2 = cv2
        self._np = np
        try:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        except Exception:
            self._hog = None

    def detect(self, frame) -> List[SilhouetteHit]:
        """Return silhouette hits for a BGR/gray ndarray (or None)."""
        if frame is None:
            return []
        hits = self._detect_hog(frame)
        if hits:
            return hits
        return self._detect_blob(frame)

    def detect_from_bboxes(
        self,
        bboxes: Sequence[Tuple[int, int, int, int]],
        *,
        frame_size: Tuple[int, int],
        scores: Optional[Sequence[float]] = None,
        source: str = "injected",
    ) -> List[SilhouetteHit]:
        """Build hits from precomputed boxes (tests / external detectors)."""
        fw, fh = frame_size
        area = max(1, fw * fh)
        out: List[SilhouetteHit] = []
        for i, bbox in enumerate(bboxes):
            x, y, w, h = (int(v) for v in bbox)
            if w <= 0 or h <= 0:
                continue
            if (w * h) / area < self.min_area_ratio:
                continue
            score = float(scores[i]) if scores and i < len(scores) else 0.7
            out.append(SilhouetteHit((x, y, w, h), score=score, source=source))
        return out

    def _frame_wh(self, frame) -> Tuple[int, int]:
        h, w = frame.shape[:2]
        return int(w), int(h)

    def _detect_hog(self, frame) -> List[SilhouetteHit]:
        if self._hog is None or self._cv2 is None:
            return []
        cv2 = self._cv2
        try:
            gray = frame
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects, weights = self._hog.detectMultiScale(
                gray, winStride=(8, 8), padding=(8, 8), scale=1.05
            )
        except Exception:
            return []
        fw, fh = self._frame_wh(frame)
        area = max(1, fw * fh)
        hits: List[SilhouetteHit] = []
        for i, (x, y, w, h) in enumerate(rects):
            if (w * h) / area < self.min_area_ratio:
                continue
            score = float(weights[i][0]) if hasattr(weights[i], "__len__") else float(weights[i])
            # HOG SVM scores are unbounded; squash into 0..1-ish for callers.
            norm = max(0.0, min(1.0, 0.5 + score / 4.0))
            hits.append(SilhouetteHit((int(x), int(y), int(w), int(h)), norm, "hog"))
        return hits

    def _detect_blob(self, frame) -> List[SilhouetteHit]:
        """Foreground mass heuristic: a large contiguous mid-frame region counts
        as a silhouette when HOG is unavailable (headless / no person model)."""
        try:
            import numpy as np  # type: ignore
        except ImportError:
            return []
        arr = frame
        if hasattr(arr, "ndim") and arr.ndim == 3:
            # Average channels without requiring cv2.
            gray = arr.mean(axis=2).astype("uint8")
        else:
            gray = arr
        fw, fh = int(gray.shape[1]), int(gray.shape[0])
        area = max(1, fw * fh)

        # Invert so darker subjects on brighter backgrounds light up; also
        # accept brighter subjects via absolute deviation from border mean.
        border = np.concatenate(
            [
                gray[0, :].ravel(),
                gray[-1, :].ravel(),
                gray[:, 0].ravel(),
                gray[:, -1].ravel(),
            ]
        )
        bg = float(border.mean()) if border.size else 128.0
        mask = (np.abs(gray.astype("float32") - bg) > self.blob_threshold).astype("uint8")

        # Keep center band (typical seated learner framing).
        y0, y1 = int(fh * 0.15), int(fh * 0.95)
        x0, x1 = int(fw * 0.1), int(fw * 0.9)
        roi = mask[y0:y1, x0:x1]
        if roi.size == 0 or int(roi.sum()) / area < self.min_area_ratio:
            return []

        ys, xs = np.where(roi > 0)
        if len(xs) == 0:
            return []
        bx0, bx1 = int(xs.min()) + x0, int(xs.max()) + x0
        by0, by1 = int(ys.min()) + y0, int(ys.max()) + y0
        bw, bh = max(1, bx1 - bx0 + 1), max(1, by1 - by0 + 1)
        if (bw * bh) / area < self.min_area_ratio:
            return []
        coverage = float(roi.sum()) / float(max(1, bw * bh))
        score = max(0.0, min(1.0, 0.35 + coverage * 0.65))
        return [SilhouetteHit((bx0, by0, bw, bh), score, "blob")]
