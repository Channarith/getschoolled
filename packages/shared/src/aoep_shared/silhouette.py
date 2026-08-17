"""Silhouette and body-presence detection for webcam teaching sessions.

Detects whether a person (or human-shaped silhouette) is visible in a frame
without requiring face detection. This handles cases where:
- The student has their back turned to the camera
- The face is obscured but the body is visible
- Partial presence (only head/shoulders visible)

Two detection strategies:
1. HOG + SVM person detector (OpenCV's built-in, CPU-only, no model download)
2. Frame-difference background subtraction for motion/presence (fallback)

``SilhouetteDetector`` is the public surface. ``SilhouetteResult`` carries the
detection outcome and is consumed by ``PresenceTracker`` (presence.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class PersonRegion:
    """A detected person bounding box in the frame."""

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float                # 0..1
    coverage: float                  # fraction of frame area covered


@dataclass
class SilhouetteResult:
    """Result of a single silhouette analysis."""

    present: bool                            # any person detected?
    person_count: int                        # number of persons
    regions: List[PersonRegion] = field(default_factory=list)
    largest_coverage: float = 0.0           # coverage of largest detected region
    method: str = "hog"                     # "hog" | "background_sub" | "none"
    # Soft absence confidence: 0 = definitely present, 1 = definitely absent.
    absence_confidence: float = 0.0

    @property
    def fully_absent(self) -> bool:
        """True when we are confident no person is in frame."""
        return not self.present and self.absence_confidence > 0.7

    @property
    def partially_present(self) -> bool:
        """Visible but small coverage — likely moving away or at room edge."""
        return self.present and self.largest_coverage < 0.05


class SilhouetteDetector:
    """Detect human silhouettes / body presence in a webcam frame.

    Uses OpenCV's HOG person detector when the library is available, falling
    back to a pure-Python frame-difference approach when it is not (CI/edge).
    Both paths return a ``SilhouetteResult`` with the same semantics.

    Parameters
    ----------
    min_confidence:
        Minimum HOG hit score to count as a detection. Lower = more sensitive.
    scale_factor:
        Image downscale factor before detection (speed/accuracy trade-off).
    background_history:
        Number of frames kept by the background subtractor.
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        scale_factor: float = 0.5,
        background_history: int = 200,
    ) -> None:
        self._min_conf = min_confidence
        self._scale = scale_factor
        self._bg_history = background_history
        self._hog = None
        self._bg_sub = None
        self._frame_count = 0
        self._last_gray: Optional[bytes] = None
        self._init_opencv()

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def _init_opencv(self) -> None:
        try:
            import cv2  # type: ignore

            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._bg_sub = cv2.createBackgroundSubtractorMOG2(
                history=self._bg_history, varThreshold=40, detectShadows=False
            )
            self._cv2 = cv2
        except ImportError:
            self._cv2 = None  # type: ignore

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyze(self, image: bytes) -> SilhouetteResult:
        """Analyze a JPEG/PNG frame and return a ``SilhouetteResult``.

        Falls back gracefully when OpenCV is not installed (CI / lightweight
        edges). In fallback mode the detector is always 'none' and presence
        stays undetermined (not absent).
        """
        if self._cv2 is None:
            return SilhouetteResult(
                present=True,  # conservative: assume present when cannot check
                person_count=0,
                method="none",
                absence_confidence=0.0,
            )
        return self._analyze_cv2(image)

    def reset_background(self) -> None:
        """Reset the background model (e.g. on scene change or new session)."""
        if self._cv2 is not None:
            self._bg_sub = self._cv2.createBackgroundSubtractorMOG2(
                history=self._bg_history, varThreshold=40, detectShadows=False
            )
        self._frame_count = 0
        self._last_gray = None

    # ------------------------------------------------------------------ #
    # Internal — OpenCV path
    # ------------------------------------------------------------------ #

    def _decode_frame(self, image: bytes):  # type: ignore[return]
        cv2 = self._cv2
        import numpy as np  # type: ignore

        arr = np.frombuffer(image, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, (0, 0)
        h, w = frame.shape[:2]
        return frame, (w, h)

    def _analyze_cv2(self, image: bytes) -> SilhouetteResult:
        cv2 = self._cv2
        frame, (fw, fh) = self._decode_frame(image)
        if frame is None or fw == 0 or fh == 0:
            return SilhouetteResult(present=False, person_count=0, method="hog",
                                    absence_confidence=1.0)
        self._frame_count += 1

        # ---- HOG detection (primary) ----------------------------------- #
        small_w = max(64, int(fw * self._scale))
        small_h = max(64, int(fh * self._scale))
        small = cv2.resize(frame, (small_w, small_h))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Feed background subtractor every frame (tracks scene changes).
        if self._bg_sub is not None:
            self._bg_sub.apply(gray)

        # HOG: winStride, padding, scale
        try:
            rects, weights = self._hog.detectMultiScale(
                gray,
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05,
            )
        except Exception:  # noqa: BLE001
            rects, weights = [], []

        regions: List[PersonRegion] = []
        if len(rects) > 0:
            scale_inv = 1.0 / self._scale
            for i, (x, y, w, h) in enumerate(rects):
                # Back-project to original resolution.
                bx = int(x * scale_inv)
                by = int(y * scale_inv)
                bw = int(w * scale_inv)
                bh = int(h * scale_inv)
                conf_raw = float(weights[i]) if i < len(weights) else 0.5
                conf = min(1.0, max(0.0, conf_raw))
                if conf < self._min_conf:
                    continue
                coverage = (bw * bh) / max(1, fw * fh)
                regions.append(PersonRegion(
                    bbox=(bx, by, bw, bh),
                    confidence=round(conf, 4),
                    coverage=round(coverage, 5),
                ))

        method = "hog"

        # ---- Background-subtraction fallback ----------------------------- #
        # If HOG found nothing but we have lots of foreground motion, infer
        # a partial presence (person too close or in unusual pose).
        if not regions and self._bg_sub is not None and fh > 0:
            import numpy as np  # type: ignore

            fg_mask = self._bg_sub.apply(gray, learningRate=0)
            fg_ratio = float(np.count_nonzero(fg_mask)) / max(1, gray.size)
            method = "background_sub"
            if fg_ratio > 0.05:
                # Enough foreground pixels -> someone is probably in frame.
                coverage = min(1.0, fg_ratio * 4)
                regions.append(PersonRegion(
                    bbox=(0, 0, fw, fh),
                    confidence=round(min(1.0, fg_ratio * 8), 4),
                    coverage=round(coverage, 5),
                ))

        present = len(regions) > 0
        largest_cov = max((r.coverage for r in regions), default=0.0)
        absence_conf = _compute_absence_confidence(regions, self._frame_count)

        return SilhouetteResult(
            present=present,
            person_count=len(regions),
            regions=regions,
            largest_coverage=round(largest_cov, 5),
            method=method,
            absence_confidence=round(absence_conf, 4),
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _compute_absence_confidence(
    regions: List[PersonRegion], frame_count: int
) -> float:
    """Estimate how confident we are that the frame is empty.

    Very first frames get a low absence confidence (background model is
    still warming up). Once the model has settled, a clean HOG result
    with no regions gives high confidence.
    """
    if regions:
        return 0.0
    # Warm-up grace: first 10 frames have lower confidence.
    warmup_factor = min(1.0, frame_count / 10.0)
    return round(0.85 * warmup_factor, 4)


def analyze_frames_batch(
    detector: SilhouetteDetector,
    frames: List[bytes],
) -> List[SilhouetteResult]:
    """Analyze a list of frames sequentially, maintaining background state."""
    return [detector.analyze(f) for f in frames]


def silhouette_summary(results: List[SilhouetteResult]) -> dict:
    """Aggregate a window of ``SilhouetteResult`` into a single presence summary.

    Returns a dict with:
    - ``present_ratio`` — fraction of frames with a detected person
    - ``avg_coverage``  — mean largest-region coverage
    - ``avg_absence_confidence`` — mean absence confidence
    - ``status``        — "present" | "absent" | "uncertain"
    """
    if not results:
        return {"present_ratio": 0.0, "avg_coverage": 0.0,
                "avg_absence_confidence": 0.0, "status": "uncertain"}
    n = len(results)
    present_ratio = sum(1 for r in results if r.present) / n
    avg_cov = sum(r.largest_coverage for r in results) / n
    avg_abs = sum(r.absence_confidence for r in results) / n

    if present_ratio >= 0.6:
        status = "present"
    elif avg_abs >= 0.7:
        status = "absent"
    else:
        status = "uncertain"

    return {
        "present_ratio": round(present_ratio, 4),
        "avg_coverage": round(avg_cov, 5),
        "avg_absence_confidence": round(avg_abs, 4),
        "status": status,
    }
