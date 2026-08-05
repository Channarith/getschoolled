"""Human silhouette detection in webcam frames (privacy-preserving presence).

Answers one question: "is a person-shaped figure in frame?" — WITHOUT face
recognition or any biometric. This powers two teaching signals face detection
alone cannot provide:

- silhouette-only presence: the learner is at their desk but turned away,
  leaning out of the face detector's view, or has the camera partly covered;
- absence: nobody is in frame at all (the learner walked away).

Two CPU-only detectors, both fully offline (no model downloads):

- HOG people detector (``cv2.HOGDescriptor_getDefaultPeopleDetector`` ships
  inside OpenCV): finds full/half-body silhouettes. Weak on tight
  head-and-shoulders webcam framing, which is exactly where the motion
  detector below takes over.
- Motion silhouette (MOG2 background subtraction): learns the static room
  behind the learner and flags large moving regions. A seated learner is
  almost never perfectly still, so sustained motion mass at a plausible scale
  is a strong "someone is there" signal.

Frames are decoded, analyzed, and discarded — nothing is stored. Callers get
bounding boxes + confidences only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

ImageLike = Union[bytes, bytearray, str, "object"]  # bytes | path | ndarray

# Tuning defaults. A webcam learner occupies a meaningful slice of the frame;
# tiny blobs are noise (curtains, pets, shadows).
DEFAULT_MIN_AREA_RATIO = 0.03   # detection must cover >= 3% of the frame
DEFAULT_MAX_AREA_RATIO = 0.95   # whole-frame "motion" = lighting change, not a person
DEFAULT_MOTION_HISTORY = 60     # frames the background model remembers
# Slow background adaptation: a seated learner who sits still must stay
# "present" for minutes, not fade into the background within seconds. At 0.01
# the model needs ~300 frames to fully absorb a static region.
DEFAULT_MOTION_LEARNING_RATE = 0.01


@dataclass
class PersonDetection:
    """A person-shaped region in a frame. No identity, no biometrics."""

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float                # 0..1
    source: str                      # "hog" | "motion"
    frame_size: Tuple[int, int] = (0, 0)  # (w, h) of the source frame

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]

    @property
    def area_ratio(self) -> float:
        fw, fh = self.frame_size
        return self.area / float(fw * fh) if fw > 0 and fh > 0 else 0.0


def _overlap_ratio(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """Intersection-over-smaller-area for two (x, y, w, h) boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    smaller = min(aw * ah, bw * bh)
    return inter / float(smaller) if smaller > 0 else 0.0


class SilhouetteDetector:
    """Detect human silhouettes in webcam frames (OpenCV, CPU, offline).

    ``cv2``/``numpy`` are imported lazily so the package imports cleanly in
    services that never touch a camera. Construct once per camera stream —
    the motion model learns that stream's background.
    """

    def __init__(
        self,
        *,
        min_area_ratio: float = DEFAULT_MIN_AREA_RATIO,
        max_area_ratio: float = DEFAULT_MAX_AREA_RATIO,
        use_hog: bool = True,
        use_motion: bool = True,
        motion_history: int = DEFAULT_MOTION_HISTORY,
        motion_learning_rate: float = DEFAULT_MOTION_LEARNING_RATE,
    ) -> None:
        if not 0.0 < min_area_ratio < max_area_ratio <= 1.0:
            raise ValueError("require 0 < min_area_ratio < max_area_ratio <= 1")
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.use_hog = use_hog
        self.use_motion = use_motion
        self._motion_learning_rate = motion_learning_rate
        self._hog = None
        self._subtractor = None
        self._motion_history = motion_history
        self._frames_seen = 0

    # --- lazy OpenCV pieces ------------------------------------------------ #
    @staticmethod
    def _cv2():
        import cv2  # lazy: keeps non-camera services dependency-free

        return cv2

    def _hog_detector(self):
        if self._hog is None:
            cv2 = self._cv2()
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        return self._hog

    def _motion_subtractor(self):
        if self._subtractor is None:
            cv2 = self._cv2()
            self._subtractor = cv2.createBackgroundSubtractorMOG2(
                history=self._motion_history, varThreshold=32, detectShadows=False
            )
        return self._subtractor

    def reset_motion(self) -> None:
        """Forget the learned background (camera moved / new stream)."""
        self._subtractor = None
        self._frames_seen = 0

    # --- decoding (mirrors the face engine's accepted inputs) -------------- #
    def _decode(self, image: ImageLike):
        cv2 = self._cv2()
        import numpy as np

        if isinstance(image, (bytes, bytearray)):
            arr = np.frombuffer(bytes(image), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        elif isinstance(image, str):
            img = cv2.imread(image)
        else:
            img = image  # assume an ndarray (BGR)
        if img is None:
            raise ValueError("could not decode image input")
        return img

    def _plausible(self, w: int, h: int, frame_size: Tuple[int, int]) -> bool:
        fw, fh = frame_size
        if fw <= 0 or fh <= 0:
            return False
        ratio = (w * h) / float(fw * fh)
        return self.min_area_ratio <= ratio <= self.max_area_ratio

    # --- detectors --------------------------------------------------------- #
    def _detect_hog(self, img, frame_size: Tuple[int, int]) -> List[PersonDetection]:
        hog = self._hog_detector()
        # winStride (8,8) + scale 1.05 is the standard CPU accuracy/speed point.
        rects, weights = hog.detectMultiScale(
            img, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        out: List[PersonDetection] = []
        for (x, y, w, h), weight in zip(rects, weights):
            if not self._plausible(int(w), int(h), frame_size):
                continue
            out.append(
                PersonDetection(
                    bbox=(int(x), int(y), int(w), int(h)),
                    confidence=max(0.0, min(1.0, float(weight) / 2.0)),
                    source="hog",
                    frame_size=frame_size,
                )
            )
        return out

    def _detect_motion(self, img, frame_size: Tuple[int, int]) -> List[PersonDetection]:
        cv2 = self._cv2()
        import numpy as np

        subtractor = self._motion_subtractor()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        # First frame is pure background learning: it cannot yield a silhouette.
        learning = 1.0 if self._frames_seen == 0 else self._motion_learning_rate
        mask = subtractor.apply(gray, learningRate=learning)
        self._frames_seen += 1
        if self._frames_seen < 2:
            return []
        _, thresh = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), dtype=np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        out: List[PersonDetection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not self._plausible(w, h, frame_size):
                continue
            area_ratio = (w * h) / float(frame_size[0] * frame_size[1])
            # Confidence scales with how much of the frame the silhouette fills,
            # saturating at ~40% occupancy.
            confidence = min(1.0, area_ratio / 0.40)
            out.append(
                PersonDetection(
                    bbox=(int(x), int(y), int(w), int(h)),
                    confidence=round(confidence, 4),
                    source="motion",
                    frame_size=frame_size,
                )
            )
        return out

    # --- public API -------------------------------------------------------- #
    def detect(self, image: ImageLike) -> List[PersonDetection]:
        """Return person silhouettes in the frame (largest first).

        HOG hits are authoritative; motion boxes that substantially overlap a
        HOG box are dropped as duplicates, the rest are kept so a seated,
        mostly-still learner HOG misses still registers as present.
        """
        img = self._decode(image)
        h, w = img.shape[:2]
        frame_size = (w, h)
        detections: List[PersonDetection] = []
        if self.use_hog:
            detections.extend(self._detect_hog(img, frame_size))
        if self.use_motion:
            for det in self._detect_motion(img, frame_size):
                if any(
                    _overlap_ratio(det.bbox, hog.bbox) > 0.5
                    for hog in detections
                    if hog.source == "hog"
                ):
                    continue
                detections.append(det)
        detections.sort(key=lambda d: d.area, reverse=True)
        return detections

    def person_visible(self, image: ImageLike) -> bool:
        """Convenience: True when at least one plausible silhouette is found."""
        return bool(self.detect(image))


@dataclass
class SilhouetteSummary:
    """Roll-up of one frame for the presence state machine."""

    person_visible: bool
    detections: List[PersonDetection] = field(default_factory=list)

    @property
    def best_confidence(self) -> float:
        return max((d.confidence for d in self.detections), default=0.0)


def summarize(detector: Optional[SilhouetteDetector], image: ImageLike) -> SilhouetteSummary:
    """Run ``detector`` over ``image`` tolerantly.

    A ``None`` detector (camera analysis disabled) yields "no person"; decode
    errors are treated the same — a broken frame must never crash a class.
    """
    if detector is None:
        return SilhouetteSummary(person_visible=False)
    try:
        detections = detector.detect(image)
    except ValueError:
        return SilhouetteSummary(person_visible=False)
    return SilhouetteSummary(person_visible=bool(detections), detections=detections)
