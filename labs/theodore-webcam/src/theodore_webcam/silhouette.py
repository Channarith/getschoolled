"""Silhouette detection: is a human-shaped body in front of this webcam?

This is deliberately *not* face recognition. Identity lives in the platform's
perception service; here we only answer "is someone there, and are they shaped
like a person" so a learner can be tracked without their face ever being
matched, and so a learner facing away or lit from behind still counts as
present.

Approach
--------
A per-pixel adaptive reference frame ("the empty room") is differenced against
the live frame. The reference only learns fast where the current mask says
nothing is happening, and learns *very* slowly underneath a detected body. That
single rule fixes the classic background-subtraction failure where a learner
who sits still for a minute gets absorbed into the background and is reported
absent while they are staring straight at the camera.

Blobs are then scored for human-likeness from four shape cues (bbox fill,
aspect, head-over-shoulders narrowing, and size), so a lamp switching on or a
chair being moved does not read as a student.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .config import SilhouetteConfig


@dataclass(frozen=True)
class Silhouette:
    """One human-shaped foreground blob, in original-frame coordinates."""

    bbox: Tuple[int, int, int, int]
    area_ratio: float
    fill_ratio: float
    aspect_ratio: float
    head_shoulder_ratio: float
    centroid: Tuple[float, float]
    human_score: float

    def as_dict(self) -> dict:
        data = asdict(self)
        data["bbox"] = list(self.bbox)
        data["centroid"] = list(self.centroid)
        return data


@dataclass(frozen=True)
class SilhouetteObservation:
    """Everything the detector learned from a single frame."""

    calibrating: bool
    silhouettes: List[Silhouette] = field(default_factory=list)
    coverage: float = 0.0
    motion: float = 0.0
    frame_size: Tuple[int, int] = (0, 0)

    @property
    def count(self) -> int:
        return len(self.silhouettes)

    @property
    def detected(self) -> bool:
        return bool(self.silhouettes)

    @property
    def primary(self) -> Optional[Silhouette]:
        return self.silhouettes[0] if self.silhouettes else None

    @property
    def confidence(self) -> float:
        primary = self.primary
        return primary.human_score if primary else 0.0

    def as_dict(self) -> dict:
        return {
            "calibrating": self.calibrating,
            "detected": self.detected,
            "count": self.count,
            "confidence": round(self.confidence, 4),
            "coverage": round(self.coverage, 4),
            "motion": round(self.motion, 4),
            "frame_size": list(self.frame_size),
            "silhouettes": [s.as_dict() for s in self.silhouettes],
        }


def _ramp(value: float, zero_lo: float, one_lo: float, one_hi: float, zero_hi: float) -> float:
    """Trapezoidal membership: 0 outside [zero_lo, zero_hi], 1 on [one_lo, one_hi]."""

    if value <= zero_lo or value >= zero_hi:
        return 0.0
    if one_lo <= value <= one_hi:
        return 1.0
    if value < one_lo:
        return (value - zero_lo) / max(one_lo - zero_lo, 1e-6)
    return (zero_hi - value) / max(zero_hi - one_hi, 1e-6)


def human_score(
    *,
    fill_ratio: float,
    aspect_ratio: float,
    head_shoulder_ratio: float,
    area_ratio: float,
) -> float:
    """Blend four shape cues into a 0..1 "this looks like a person" score."""

    # A body leaves gaps inside its bounding box; a lighting change fills it.
    fill = _ramp(fill_ratio, 0.14, 0.32, 0.82, 0.97)
    # Seated upper body through to a standing figure.
    aspect = _ramp(aspect_ratio, 0.45, 0.85, 3.2, 5.2)
    # Head band narrower than the widest (shoulder) band.
    head = _ramp(head_shoulder_ratio, 0.03, 0.15, 0.85, 1.02)
    # Big enough to be a learner, small enough not to be the whole frame.
    size = _ramp(area_ratio, 0.008, 0.03, 0.60, 0.93)
    return 0.34 * fill + 0.26 * aspect + 0.22 * head + 0.18 * size


def _head_shoulder_ratio(mask_crop: np.ndarray) -> float:
    """Width of the top 15% of the blob divided by its widest band."""

    height = mask_crop.shape[0]
    if height == 0:
        return 1.0
    band = max(1, int(round(height * 0.15)))
    columns_any = mask_crop > 0
    widths = []
    step = max(1, height // 24)
    for start in range(0, height, step):
        rows = columns_any[start : start + step]
        if not rows.size:
            continue
        cols = np.any(rows, axis=0)
        widths.append(int(cols.sum()))
    widest = max(widths) if widths else 0
    if widest <= 0:
        return 1.0
    top_cols = np.any(columns_any[:band], axis=0)
    top_width = int(top_cols.sum())
    return float(top_width) / float(widest)


class SilhouetteDetector:
    """Stateful per-camera silhouette detector. Not thread-safe by design."""

    def __init__(self, config: Optional[SilhouetteConfig] = None) -> None:
        self.config = config or SilhouetteConfig()
        self._reference: Optional[np.ndarray] = None
        self._previous_gray: Optional[np.ndarray] = None
        self.frames_seen = 0

    def reset(self) -> None:
        """Forget the learned background (used by the recalibrate endpoint)."""

        self._reference = None
        self._previous_gray = None
        self.frames_seen = 0

    @property
    def calibrating(self) -> bool:
        return self.frames_seen < self.config.warmup_frames

    def observe(self, frame: np.ndarray) -> SilhouetteObservation:
        if frame is None or frame.size == 0:
            raise ValueError("empty frame")
        cfg = self.config
        original_h, original_w = frame.shape[:2]

        scale = min(1.0, cfg.work_width / float(original_w)) if original_w else 1.0
        if scale < 1.0:
            work = cv2.resize(
                frame,
                (max(1, int(original_w * scale)), max(1, int(original_h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = frame

        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gray_f = gray.astype(np.float32)

        motion = 0.0
        if self._previous_gray is not None and self._previous_gray.shape == gray_f.shape:
            motion = float(np.mean(np.abs(gray_f - self._previous_gray)) / 255.0)
        self._previous_gray = gray_f

        if self._reference is None or self._reference.shape != gray_f.shape:
            self._reference = gray_f.copy()
            self.frames_seen = 1
            return SilhouetteObservation(
                calibrating=True,
                motion=motion,
                frame_size=(original_w, original_h),
            )

        diff = cv2.absdiff(gray_f, self._reference)
        _, mask = cv2.threshold(diff, float(cfg.diff_threshold), 255, cv2.THRESH_BINARY)
        mask = mask.astype(np.uint8)

        open_k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cfg.open_kernel, cfg.open_kernel)
        )
        close_k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cfg.close_kernel, cfg.close_kernel)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_k)

        self.frames_seen += 1
        calibrating = self.calibrating

        work_h, work_w = mask.shape[:2]
        frame_area = float(work_h * work_w) or 1.0
        coverage = float(np.count_nonzero(mask)) / frame_area

        silhouettes: List[Silhouette] = []
        if not calibrating:
            silhouettes = self._score_blobs(mask, work_w, work_h, frame_area, scale)

        self._update_reference(gray_f, mask, calibrating)

        return SilhouetteObservation(
            calibrating=calibrating,
            silhouettes=silhouettes,
            coverage=coverage,
            motion=motion,
            frame_size=(original_w, original_h),
        )

    def _score_blobs(
        self,
        mask: np.ndarray,
        work_w: int,
        work_h: int,
        frame_area: float,
        scale: float,
    ) -> List[Silhouette]:
        cfg = self.config
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found: List[Silhouette] = []
        for contour in contours:
            blob_area = float(cv2.contourArea(contour))
            area_ratio = blob_area / frame_area
            if area_ratio < cfg.min_area_ratio or area_ratio > cfg.max_area_ratio:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w <= 1 or h <= 1:
                continue
            fill_ratio = blob_area / float(w * h)
            aspect_ratio = float(h) / float(w)
            crop = mask[y : y + h, x : x + w]
            head_ratio = _head_shoulder_ratio(crop)
            score = human_score(
                fill_ratio=fill_ratio,
                aspect_ratio=aspect_ratio,
                head_shoulder_ratio=head_ratio,
                area_ratio=area_ratio,
            )
            if score < cfg.human_score_threshold:
                continue
            inv = 1.0 / scale if scale > 0 else 1.0
            found.append(
                Silhouette(
                    bbox=(
                        int(round(x * inv)),
                        int(round(y * inv)),
                        int(round(w * inv)),
                        int(round(h * inv)),
                    ),
                    area_ratio=round(area_ratio, 4),
                    fill_ratio=round(fill_ratio, 4),
                    aspect_ratio=round(aspect_ratio, 4),
                    head_shoulder_ratio=round(head_ratio, 4),
                    centroid=(
                        round((x + w / 2.0) / max(work_w, 1), 4),
                        round((y + h / 2.0) / max(work_h, 1), 4),
                    ),
                    human_score=round(score, 4),
                )
            )
        found.sort(key=lambda s: (s.human_score, s.area_ratio), reverse=True)
        return found[: cfg.max_silhouettes]

    def _update_reference(
        self, gray_f: np.ndarray, mask: np.ndarray, calibrating: bool
    ) -> None:
        """Learn the empty room fast, and what is under a body almost never."""

        cfg = self.config
        assert self._reference is not None
        if calibrating:
            cv2.accumulateWeighted(gray_f, self._reference, 0.35)
            return
        alpha = np.full(gray_f.shape, cfg.background_alpha, dtype=np.float32)
        alpha[mask > 0] = cfg.occluded_alpha
        self._reference += (gray_f - self._reference) * alpha
