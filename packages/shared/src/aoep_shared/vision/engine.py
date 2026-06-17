"""Face detection + embedding engine (OpenCV YuNet + SFace).

CPU-only, no model downloads at import time. ``cv2``/``numpy`` are imported
lazily so that importing :mod:`aoep_shared` in non-vision services stays cheap
and dependency-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

ImageLike = Union[bytes, bytearray, str, "object"]  # bytes | path | ndarray

# SFace's recommended cosine decision threshold: scores above this are the same
# identity. Calibrated by OpenCV; validated on our test set (same-person ~0.69,
# different-person ~0.08), so 0.363 separates them with wide margin.
DEFAULT_MATCH_THRESHOLD = 0.363
DEFAULT_DET_SCORE_THRESHOLD = 0.7


@dataclass
class DetectedFace:
    """A detected face with its embedding."""

    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    det_score: float
    embedding: List[float]  # 128-d SFace feature (unnormalized; use cosine)

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
            faces.append(
                DetectedFace(
                    bbox=(x, y, bw, bh),
                    det_score=float(row[-1]),
                    embedding=feat.tolist(),
                )
            )
        faces.sort(key=lambda f: f.area, reverse=True)
        return faces

    def embed(self, image: ImageLike) -> Optional[List[float]]:
        """Embedding of the largest face, or ``None`` if no face is found."""
        faces = self.detect_faces(image)
        return faces[0].embedding if faces else None
