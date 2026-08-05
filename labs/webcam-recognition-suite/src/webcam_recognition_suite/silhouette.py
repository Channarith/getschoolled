"""Body silhouette / person presence detection for webcam frames.

OpenCV HOG person detector is used when available. Offline CI and the lab
harness use a synthetic detector that reads annotated frame metadata so tests
never require model downloads or a camera.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

ImageLike = Union[bytes, bytearray, str, "object"]


@dataclass
class SilhouetteDetection:
    """One person-sized region in a webcam frame."""

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    score: float
    source: str = "synthetic"  # synthetic | hog | contour
    centered: bool = False
    frame_size: Tuple[int, int] = (0, 0)

    @property
    def area_ratio(self) -> float:
        fw, fh = self.frame_size
        if fw <= 0 or fh <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.bbox[2] * self.bbox[3]) / float(fw * fh)))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["area_ratio"] = round(self.area_ratio, 4)
        return d


@dataclass
class SilhouetteFrameResult:
    """Aggregate silhouette read for one frame."""

    person_count: int
    detections: List[SilhouetteDetection] = field(default_factory=list)
    body_present: bool = False
    confidence: float = 0.0
    engine: str = "synthetic"

    def to_dict(self) -> dict:
        return {
            "person_count": self.person_count,
            "body_present": self.body_present,
            "confidence": round(self.confidence, 4),
            "engine": self.engine,
            "detections": [d.to_dict() for d in self.detections],
        }


def estimate_body_presence(
    detections: Sequence[SilhouetteDetection],
    *,
    min_area_ratio: float = 0.02,
    min_score: float = 0.35,
) -> Tuple[bool, float]:
    """Return (body_present, confidence) from silhouette detections."""
    usable = [
        d
        for d in detections
        if d.score >= min_score and (d.area_ratio >= min_area_ratio or d.frame_size == (0, 0))
    ]
    if not usable:
        return False, 0.0
    best = max(usable, key=lambda d: d.score)
    # Prefer centered, reasonably large silhouettes.
    conf = best.score
    if best.centered:
        conf = min(1.0, conf + 0.1)
    if best.area_ratio >= 0.08:
        conf = min(1.0, conf + 0.05)
    return True, round(conf, 4)


class SilhouetteDetector:
    """Detect person silhouettes in a webcam frame.

    ``mode``:
      - ``auto``: try OpenCV HOG, else synthetic metadata
      - ``hog``: require OpenCV HOG (raises if unavailable)
      - ``synthetic``: only read SyntheticFrame annotations / empty
    """

    def __init__(self, *, mode: str = "auto", win_stride: Tuple[int, int] = (8, 8)) -> None:
        self.mode = (mode or "auto").strip().lower()
        self.win_stride = win_stride
        self._hog = None
        if self.mode in ("auto", "hog"):
            self._hog = self._try_build_hog()
            if self.mode == "hog" and self._hog is None:
                raise RuntimeError("OpenCV HOG person detector unavailable")

    @staticmethod
    def _try_build_hog():
        try:
            import cv2  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        return hog

    def detect(self, frame: ImageLike) -> SilhouetteFrameResult:
        # Annotated synthetic frames carry person boxes without needing pixels.
        if hasattr(frame, "silhouettes"):
            dets = list(getattr(frame, "silhouettes") or [])
            present, conf = estimate_body_presence(dets)
            return SilhouetteFrameResult(
                person_count=len(dets),
                detections=dets,
                body_present=present,
                confidence=conf,
                engine="synthetic",
            )

        if self._hog is not None:
            return self._detect_hog(frame)

        if self.mode == "hog":
            raise RuntimeError("OpenCV HOG person detector unavailable")

        return SilhouetteFrameResult(
            person_count=0,
            detections=[],
            body_present=False,
            confidence=0.0,
            engine="synthetic",
        )

    def _detect_hog(self, frame: ImageLike) -> SilhouetteFrameResult:
        import cv2  # type: ignore
        import numpy as np

        img = _decode_bgr(frame)
        if img is None:
            return SilhouetteFrameResult(0, [], False, 0.0, engine="hog")
        fh, fw = img.shape[:2]
        boxes, weights = self._hog.detectMultiScale(
            img, winStride=self.win_stride, padding=(8, 8), scale=1.05
        )
        dets: List[SilhouetteDetection] = []
        for box, weight in zip(boxes, weights):
            x, y, w, h = [int(v) for v in box]
            score = float(weight[0]) if hasattr(weight, "__len__") else float(weight)
            # HOG raw scores are unbounded; squash into ~0..1 for policy.
            norm = max(0.0, min(1.0, (score + 1.0) / 3.0))
            cx = (x + w / 2.0) / max(1, fw)
            centered = abs(cx - 0.5) < 0.28
            dets.append(
                SilhouetteDetection(
                    bbox=(x, y, w, h),
                    score=norm,
                    source="hog",
                    centered=centered,
                    frame_size=(fw, fh),
                )
            )
        present, conf = estimate_body_presence(dets)
        return SilhouetteFrameResult(
            person_count=len(dets),
            detections=dets,
            body_present=present,
            confidence=conf,
            engine="hog",
        )


def detect_silhouettes(frame: ImageLike, *, mode: str = "auto") -> SilhouetteFrameResult:
    """Convenience wrapper around :class:`SilhouetteDetector`."""
    return SilhouetteDetector(mode=mode).detect(frame)


def _decode_bgr(image: ImageLike):
    import cv2  # type: ignore
    import numpy as np

    if isinstance(image, (bytes, bytearray)):
        arr = np.frombuffer(bytes(image), dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if isinstance(image, str):
        return cv2.imread(image)
    return image
