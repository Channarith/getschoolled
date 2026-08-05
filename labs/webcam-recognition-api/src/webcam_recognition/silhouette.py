"""Silhouette (human-body) detection for classroom webcams.

Faces disappear constantly in real classes -- the learner turns to write, leans
out of frame, or the room is backlit. Detecting the *silhouette* (the whole-body
outline) keeps "is a person there?" robust when face recognition alone would say
"gone".

Two layers:

- A pure, dependency-free geometry core (:func:`analyze_mask`, :func:`summarize_frame`)
  that turns detections / a foreground mask into a :class:`FramePerception`. This
  is fully unit-testable with plain Python lists and needs no camera or model.
- :class:`SilhouetteDetector`, a real CPU-only detector built on OpenCV's HOG +
  linear-SVM pedestrian model (``cv2.HOGDescriptor`` with the built-in people
  detector). ``cv2``/``numpy`` are imported lazily so importing this module stays
  cheap and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

BBox = Tuple[int, int, int, int]  # (x, y, w, h)


@dataclass
class SilhouetteBox:
    """A detected human silhouette (whole-body bounding box) in a frame."""

    bbox: BBox
    confidence: float
    frame_size: Tuple[int, int]  # (w, h)

    @property
    def area(self) -> int:
        return max(0, self.bbox[2]) * max(0, self.bbox[3])

    @property
    def coverage(self) -> float:
        """Fraction of the frame this silhouette covers (0..1)."""
        fw, fh = self.frame_size
        if fw <= 0 or fh <= 0:
            return 0.0
        return min(1.0, self.area / float(fw * fh))

    @property
    def center(self) -> Tuple[float, float]:
        x, y, w, h = self.bbox
        return (x + w / 2.0, y + h / 2.0)

    @property
    def centered(self) -> float:
        """1.0 when the silhouette is horizontally centered, ->0 at the edges."""
        fw, _ = self.frame_size
        if fw <= 0:
            return 0.0
        cx = self.center[0] / fw
        return max(0.0, 1.0 - abs(cx - 0.5) * 2.0)


@dataclass
class FramePerception:
    """A single frame's recognition summary (silhouettes + faces + presence)."""

    person_present: bool
    people_count: int
    face_count: int
    largest_coverage: float
    attention: float  # 0..1 best face attention (0 when no face geometry)
    silhouettes: List[SilhouetteBox] = field(default_factory=list)
    # Identity/engagement carried through from a face pipeline (optional).
    matched_student_ids: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "person_present": self.person_present,
            "people_count": self.people_count,
            "face_count": self.face_count,
            "largest_coverage": round(self.largest_coverage, 4),
            "attention": round(self.attention, 4),
            "silhouettes": [
                {
                    "bbox": list(s.bbox),
                    "confidence": round(s.confidence, 4),
                    "coverage": round(s.coverage, 4),
                    "centered": round(s.centered, 4),
                }
                for s in self.silhouettes
            ],
            "matched_student_ids": list(self.matched_student_ids),
        }


def analyze_mask(
    mask: Sequence[Sequence[int]],
    *,
    min_coverage: float = 0.03,
) -> Optional[SilhouetteBox]:
    """Turn a 2D binary foreground mask into a single silhouette box.

    ``mask`` is a list of rows of 0/non-zero values (e.g. from background
    subtraction). Returns the bounding box of the foreground blob, or ``None``
    when the foreground is smaller than ``min_coverage`` of the frame. Pure
    Python -- no OpenCV/numpy required, so it is trivially unit-testable.
    """
    rows = [list(r) for r in mask]
    h = len(rows)
    w = len(rows[0]) if h else 0
    if h == 0 or w == 0:
        return None

    min_x, min_y, max_x, max_y = w, h, -1, -1
    on = 0
    for y in range(h):
        row = rows[y]
        for x in range(w):
            if row[x]:
                on += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:  # nothing on
        return None

    coverage = on / float(w * h)
    if coverage < min_coverage:
        return None
    bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
    return SilhouetteBox(bbox=bbox, confidence=coverage, frame_size=(w, h))


def summarize_frame(
    silhouettes: Sequence[SilhouetteBox],
    *,
    face_count: int = 0,
    attention: float = 0.0,
    matched_student_ids: Optional[Sequence[str]] = None,
    min_coverage: float = 0.03,
) -> FramePerception:
    """Combine silhouette + face signals into a single :class:`FramePerception`.

    A person is considered present when either a face was detected OR at least one
    silhouette covers ``min_coverage`` of the frame. This "face OR body" rule is
    what makes presence robust to a learner turning away from the camera.
    """
    valid = [s for s in silhouettes if s.coverage >= min_coverage]
    largest = max((s.coverage for s in valid), default=0.0)
    person_present = face_count > 0 or bool(valid)
    return FramePerception(
        person_present=person_present,
        people_count=max(len(valid), face_count),
        face_count=face_count,
        largest_coverage=largest,
        attention=max(0.0, min(1.0, attention)),
        silhouettes=list(valid),
        matched_student_ids=list(matched_student_ids or []),
    )


class SilhouetteDetector:
    """Real CPU-only body/silhouette detector (OpenCV HOG + SVM people model).

    No model download is needed -- OpenCV ships the trained pedestrian SVM
    (``getDefaultPeopleDetector``). ``cv2``/``numpy`` are imported lazily on first
    use so the module is importable in environments without them.
    """

    def __init__(self, *, hit_threshold: float = 0.0) -> None:
        import cv2  # lazy

        self._cv2 = cv2
        self._hit_threshold = hit_threshold
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def _decode(self, image):
        cv2 = self._cv2
        import numpy as np

        if isinstance(image, (bytes, bytearray)):
            arr = np.frombuffer(bytes(image), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        elif isinstance(image, str):
            img = cv2.imread(image)
        else:
            img = image  # assume a BGR ndarray
        if img is None:
            raise ValueError("could not decode image input")
        return img

    def detect(self, image) -> List[SilhouetteBox]:
        """Detect human silhouettes in ``image`` (bytes | path | BGR ndarray)."""
        cv2 = self._cv2
        img = self._decode(image)
        h, w = img.shape[:2]
        # Downscale very large frames so HOG stays real-time; keep the scale so
        # boxes map back to the original coordinates.
        scale = 1.0
        max_w = 640
        if w > max_w:
            scale = max_w / float(w)
            img = cv2.resize(img, (max_w, int(h * scale)))
        rects, weights = self._hog.detectMultiScale(
            img, winStride=(8, 8), padding=(8, 8), scale=1.05,
            hitThreshold=self._hit_threshold,
        )
        boxes: List[SilhouetteBox] = []
        for (rx, ry, rw, rh), weight in zip(rects, weights):
            inv = 1.0 / scale
            bbox = (int(rx * inv), int(ry * inv), int(rw * inv), int(rh * inv))
            boxes.append(
                SilhouetteBox(
                    bbox=bbox,
                    confidence=float(weight),
                    frame_size=(w, h),
                )
            )
        boxes.sort(key=lambda b: b.area, reverse=True)
        return boxes
