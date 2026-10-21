"""Face detection + embedding engine (OpenCV YuNet + SFace).

CPU-only, no model downloads at import time. ``cv2``/``numpy`` are imported
lazily so that importing :mod:`aoep_shared` in non-vision services stays cheap
and dependency-free.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

ImageLike = Union[bytes, bytearray, str, "object"]  # bytes | path | ndarray

# OpenCV's calibrated SFace cosine for "same identity". Same-person pairs on
# the held-out set sit near 0.69 and different-person pairs near 0.08.
# This is the accept bar. Do not spend the gap below it: a lower cut raises
# false accepts, including lookalikes. Smile, blink, sneeze, and modest weight
# change are handled by keeping each capture as its own template (see
# FaceGallery.identify), not by moving this number.
SFACE_CALIBRATED_THRESHOLD = 0.363
# Headroom we deliberately do not subtract from the decision threshold.
EXPRESSION_TOLERANCE_MARGIN = 0.063
DEFAULT_MATCH_THRESHOLD = SFACE_CALIBRATED_THRESHOLD


def _env_float(name: str, default: float) -> float:
    """Read a float env override, falling back to ``default`` on any parse error."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Looser threshold used ONLY for the pose-challenge liveness check (neutral
# portrait vs. left/right/up/down captures of the SAME person). SFace is
# calibrated against frontal portraits, so an extreme head yaw/pitch cosine
# often sits in the 0.18-0.35 band for the same person. Keeping the strict
# 0.363 bar here was rejecting legitimate pose captures with a 422 "pose
# challenge face does not match portrait" error. 0.18 accepts that band.
# Identity matching stays at DEFAULT_MATCH_THRESHOLD (0.363).
#
# Override at runtime with AOEP_POSE_CHALLENGE_THRESHOLD (float). Set it to
# 0.0 to disable the pose-vs-portrait similarity gate entirely (local-dev
# escape hatch; the "frames must not be static" and "same dimensions" gates
# still apply).
POSE_CHALLENGE_THRESHOLD = _env_float(
    "AOEP_POSE_CHALLENGE_THRESHOLD",
    0.18,
)
# Neutral portrait plus left, right, up, and down. A high-assurance match
# waits until all five templates are enrolled.
LIVENESS_TEMPLATE_COUNT = 5
# Live mobile capture must work with lower-light front cameras, glasses, and
# ordinary phone compression. The pose flow still requires one centered face
# and five distinct looks before enrollment, so use a forgiving detector score
# here rather than rejecting a real learner before they can begin.
DEFAULT_DET_SCORE_THRESHOLD = 0.45


@dataclass
class DetectedFace:
    """A detected face with its embedding and 5 facial landmarks.

    landmarks order (YuNet): right eye, left eye, nose tip, right mouth corner,
    left mouth corner - each an (x, y) pixel coordinate. frame_size is (w, h) of
    the source image so landmarks/bbox can be normalized for engagement analysis.
    """

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    det_score: float
    embedding: List[float]  # 128-d SFace feature (unnormalized; use cosine)
    landmarks: List[Tuple[float, float]] = field(default_factory=list)
    frame_size: Tuple[int, int] = (0, 0)

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    return float(dot / denom) if denom else 0.0


class FaceRecognitionEngine:
    """Detect faces and compute SFace embeddings.

    The same engine serves enrollment (compute an embedding to store) and
    recognition (compute an embedding to match). Identity matching/consent live
    in :class:`~aoep_shared.vision.gallery.FaceGallery` and the VisionProvider.
    """

    def __init__(
        self,
        detector_path: str,
        recognizer_path: str,
        *,
        det_score_threshold: float = DEFAULT_DET_SCORE_THRESHOLD,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        input_size: Tuple[int, int] = (320, 320),
    ) -> None:
        import cv2  # lazy

        self._cv2 = cv2
        self.match_threshold = match_threshold
        self._detector = cv2.FaceDetectorYN.create(
            detector_path, "", input_size, det_score_threshold, 0.3, 5000
        )
        self._recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")

    @classmethod
    def from_models(
        cls, model_dir: Optional[str] = None, *, allow_download: bool = True, **kwargs
    ) -> "FaceRecognitionEngine":
        from .models import ensure_models

        detector, recognizer = ensure_models(model_dir, allow_download=allow_download)
        return cls(detector, recognizer, **kwargs)

    def _decode(self, image: ImageLike):
        cv2 = self._cv2
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

    def detect_faces(self, image: ImageLike) -> List[DetectedFace]:
        """Return all detected faces (largest first), each with an embedding."""
        img = self._decode(image)
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, raw = self._detector.detect(img)
        faces: List[DetectedFace] = []
        if raw is None:
            return faces
        for row in raw:
            aligned = self._recognizer.alignCrop(img, row)
            feat = self._recognizer.feature(aligned).flatten().astype("float32")
            x, y, bw, bh = (int(v) for v in row[:4])
            # YuNet emits 5 landmarks at indices 4..13 (x, y pairs).
            landmarks = [
                (float(row[4 + 2 * i]), float(row[5 + 2 * i])) for i in range(5)
            ]
            faces.append(
                DetectedFace(
                    bbox=(x, y, bw, bh),
                    det_score=float(row[-1]),
                    embedding=feat.tolist(),
                    landmarks=landmarks,
                    frame_size=(w, h),
                )
            )
        faces.sort(key=lambda f: f.area, reverse=True)
        return faces

    def detect_landmarks(self, image: ImageLike) -> List[DetectedFace]:
        """Return YuNet geometry without running the expensive SFace embedder.

        The native setup assistant calls this continuously while rendering its
        camera outline. It needs only the bounding box and five landmarks; doing
        recognition for each preview frame wastes CPU and makes an otherwise
        usable front-camera frame time out under load. Enrollment still uses
        :meth:`detect_faces`, which computes a real embedding for every saved
        pose image.
        """
        img = self._decode(image)
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, raw = self._detector.detect(img)
        faces: List[DetectedFace] = []
        if raw is None:
            return faces
        for row in raw:
            x, y, bw, bh = (int(v) for v in row[:4])
            landmarks = [
                (float(row[4 + 2 * i]), float(row[5 + 2 * i])) for i in range(5)
            ]
            faces.append(
                DetectedFace(
                    bbox=(x, y, bw, bh),
                    det_score=float(row[-1]),
                    embedding=[],
                    landmarks=landmarks,
                    frame_size=(w, h),
                )
            )
        faces.sort(key=lambda f: f.area, reverse=True)
        return faces

    def embed(self, image: ImageLike) -> Optional[List[float]]:
        """Embedding of the largest face, or ``None`` if no face is found."""
        faces = self.detect_faces(image)
        return faces[0].embedding if faces else None
