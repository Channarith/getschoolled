"""Person silhouette / body presence detection (face-independent).

Complements YuNet face detection: when a learner turns away or the face is
occluded, a body silhouette can still prove they are in the seat. Used by the
webcam lab and live-room presence policy to distinguish:

- face present        -> live / attentive path
- silhouette only     -> present but face not visible (turned away / looking down)
- neither             -> absent from the frame

Implementation prefers OpenCV HOG pedestrian detection when ``cv2`` is
available; otherwise a lightweight numpy energy/contrast heuristic keeps the
offline teaching loop and unit tests runnable without the vision extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

ImageLike = Union[bytes, bytearray, "object"]  # bytes | ndarray


@dataclass
class SilhouetteObservation:
    """One detected person-shaped region in a frame."""

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float  # 0..1
    source: str  # hog | energy | synthetic
    area_ratio: float = 0.0  # bbox area / frame area


@dataclass
class SilhouetteSignals:
    """Aggregate silhouette presence for a single frame."""

    person_count: int
    present: bool
    confidence: float  # max silhouette confidence (0..1)
    observations: List[SilhouetteObservation]
    frame_size: Tuple[int, int] = (0, 0)

    @property
    def primary_bbox(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.observations:
            return None
        return max(self.observations, key=lambda o: o.confidence).bbox


def _decode_bgr(frame: ImageLike):
    """Decode bytes/ndarray to BGR uint8 array. Raises if unusable."""
    import numpy as np

    if hasattr(frame, "shape") and hasattr(frame, "dtype"):
        arr = frame
        if len(arr.shape) == 2:
            return arr
        if len(arr.shape) == 3 and arr.shape[2] >= 3:
            return arr
        raise ValueError("unsupported ndarray shape for silhouette")

    data = bytes(frame) if not isinstance(frame, (bytes, bytearray)) else bytes(frame)
    try:
        import cv2

        buf = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("could not decode image bytes")
        return img
    except ImportError:
        # Without OpenCV we can only analyze pre-decoded arrays.
        raise ValueError(
            "silhouette decode of raw image bytes requires opencv "
            "(aoep-shared[vision]); pass a numpy ndarray instead"
        ) from None


def _energy_detect(
    gray,
    *,
    min_area_ratio: float = 0.04,
    threshold_ratio: float = 0.18,
) -> List[SilhouetteObservation]:
    """Contrast-energy blob heuristic (no HOG). Offline-safe.

    Looks for a contiguous mid-frame region whose local variance exceeds the
    frame mean — a standing/sitting person against a flatter background tends
    to create such a blob. Not identity-grade; good enough for presence.
    """
    import numpy as np

    h, w = gray.shape[:2]
    if h < 16 or w < 16:
        return []

    # Local absolute deviation from a downsampled mean (cheap "edge energy").
    g = gray.astype(np.float32)
    mean = float(np.mean(g))
    energy = np.abs(g - mean)
    # Soften with a box blur via strided reduce when possible.
    block = max(4, min(h, w) // 32)
    eh, ew = h // block, w // block
    if eh < 2 or ew < 2:
        return []
    reduced = energy[: eh * block, : ew * block].reshape(eh, block, ew, block).mean(axis=(1, 3))
    thr = float(np.mean(reduced)) + threshold_ratio * float(np.std(reduced) + 1e-6)
    mask = reduced > thr
    if not mask.any():
        return []

    # Largest connected component via simple flood (4-connected).
    visited = np.zeros_like(mask, dtype=bool)
    best = None
    for y in range(eh):
        for x in range(ew):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = True
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < eh and 0 <= nx < ew and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            area = len(cells)
            if best is None or area > best[0]:
                best = (area, min(ys), max(ys), min(xs), max(xs))

    if best is None:
        return []
    area, y0, y1, x0, x1 = best
    bx = int(x0 * block)
    by = int(y0 * block)
    bw = int(max(block, (x1 - x0 + 1) * block))
    bh = int(max(block, (y1 - y0 + 1) * block))
    area_ratio = (bw * bh) / float(w * h)
    if area_ratio < min_area_ratio:
        return []
    # Confidence from how dominant the blob is vs frame.
    confidence = max(0.15, min(0.85, area_ratio / 0.35))
    return [
        SilhouetteObservation(
            bbox=(bx, by, min(bw, w - bx), min(bh, h - by)),
            confidence=round(confidence, 4),
            source="energy",
            area_ratio=round(area_ratio, 4),
        )
    ]


def _hog_detect(bgr, *, hit_threshold: float = 0.4) -> List[SilhouetteObservation]:
    """OpenCV HOG pedestrian detector."""
    import cv2
    import numpy as np

    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    h, w = bgr.shape[:2]
    # Upscale tiny webcam crops so HOG has enough pixels.
    scale = 1.0
    img = bgr
    if max(h, w) < 240:
        scale = 240.0 / max(h, w)
        img = cv2.resize(bgr, (int(w * scale), int(h * scale)))
    rects, weights = hog.detectMultiScale(
        img, winStride=(8, 8), padding=(8, 8), scale=1.05, hitThreshold=hit_threshold
    )
    out: List[SilhouetteObservation] = []
    frame_area = float(w * h)
    for rect, weight in zip(rects, weights):
        x, y, rw, rh = [int(v / scale) for v in rect]
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        rw = max(1, min(rw, w - x))
        rh = max(1, min(rh, h - y))
        area_ratio = (rw * rh) / frame_area
        # HOG weights are unbounded; squash to 0..1.
        conf = float(1.0 / (1.0 + np.exp(-float(weight))))
        out.append(
            SilhouetteObservation(
                bbox=(x, y, rw, rh),
                confidence=round(max(0.05, min(0.99, conf)), 4),
                source="hog",
                area_ratio=round(area_ratio, 4),
            )
        )
    return out


def detect_silhouette(
    frame: ImageLike,
    *,
    prefer_hog: bool = True,
    min_confidence: float = 0.2,
) -> SilhouetteSignals:
    """Detect person silhouettes in ``frame``.

    Returns an empty ``SilhouetteSignals`` (present=False) when nothing is
    found. Never raises for ordinary empty/blank frames.
    """
    try:
        bgr = _decode_bgr(frame)
    except Exception:
        return SilhouetteSignals(0, False, 0.0, [], (0, 0))

    h, w = bgr.shape[:2]
    observations: List[SilhouetteObservation] = []

    if prefer_hog:
        try:
            import cv2  # noqa: F401

            observations = _hog_detect(bgr)
        except Exception:
            observations = []

    if not observations:
        # Grayscale energy fallback (works with or without OpenCV).
        if len(bgr.shape) == 3:
            try:
                import cv2

                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            except Exception:

                gray = bgr.mean(axis=2).astype("uint8") if bgr.ndim == 3 else bgr
        else:
            gray = bgr
        observations = _energy_detect(gray)

    observations = [o for o in observations if o.confidence >= min_confidence]
    if not observations:
        return SilhouetteSignals(0, False, 0.0, [], (w, h))

    conf = max(o.confidence for o in observations)
    return SilhouetteSignals(
        person_count=len(observations),
        present=True,
        confidence=round(conf, 4),
        observations=observations,
        frame_size=(w, h),
    )


def silhouette_from_counts(
    *,
    person_count: int,
    confidence: float = 0.8,
    frame_size: Tuple[int, int] = (640, 480),
    bboxes: Optional[Sequence[Tuple[int, int, int, int]]] = None,
) -> SilhouetteSignals:
    """Build synthetic silhouette signals (tests / client-reported counts)."""
    count = max(0, int(person_count))
    if count == 0:
        return SilhouetteSignals(0, False, 0.0, [], frame_size)
    obs: List[SilhouetteObservation] = []
    fw, fh = frame_size
    for i in range(count):
        if bboxes and i < len(bboxes):
            bbox = tuple(bboxes[i])  # type: ignore[assignment]
        else:
            bbox = (fw // 4, fh // 8, fw // 2, int(fh * 0.75))
        area_ratio = (bbox[2] * bbox[3]) / float(max(1, fw * fh))
        obs.append(
            SilhouetteObservation(
                bbox=bbox,  # type: ignore[arg-type]
                confidence=float(confidence),
                source="synthetic",
                area_ratio=round(area_ratio, 4),
            )
        )
    return SilhouetteSignals(
        person_count=count,
        present=True,
        confidence=round(float(confidence), 4),
        observations=obs,
        frame_size=frame_size,
    )
