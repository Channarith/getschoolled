"""Self-hosted face recognition + attention for the perception service.

Biometrics stay inside the configured boundary (compliance lever). The engine is
backed by OpenCV's YuNet (detection) + SFace (128-d embeddings), runs on CPU, and
needs no GPU. Model weights are downloaded at runtime and kept out of the repo.

Public surface:
- ``FaceRecognitionEngine`` - detect faces and compute embeddings.
- ``FaceGallery``           - enroll embeddings and match (1:N) with a threshold.
- ``DetectedFace``          - a detected face (bbox, score, embedding).
- ``detect_silhouette`` / ``AbsenceTracker`` - body presence + user absence.
- model helpers in ``aoep_shared.vision.models``.
"""

from .absence import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_SILHOUETTE,
    PRESENCE_SPOOF,
    PRESENCE_STATES,
    PRESENCE_UNKNOWN,
    AbsenceDecision,
    AbsencePolicy,
    AbsenceTracker,
    FramePresenceInput,
)
from .engagement import EngagementSignals, GestureRecognizer, estimate_engagement
from .engine import DetectedFace, FaceRecognitionEngine
from .gallery import FaceGallery, Match
from .silhouette import (
    SilhouetteObservation,
    SilhouetteSignals,
    detect_silhouette,
    silhouette_from_counts,
)

__all__ = [
    "DetectedFace",
    "FaceRecognitionEngine",
    "FaceGallery",
    "Match",
    "EngagementSignals",
    "GestureRecognizer",
    "estimate_engagement",
    "SilhouetteObservation",
    "SilhouetteSignals",
    "detect_silhouette",
    "silhouette_from_counts",
    "AbsenceTracker",
    "AbsencePolicy",
    "AbsenceDecision",
    "FramePresenceInput",
    "PRESENCE_LIVE",
    "PRESENCE_SILHOUETTE",
    "PRESENCE_ABSENT",
    "PRESENCE_UNKNOWN",
    "PRESENCE_SPOOF",
    "PRESENCE_STATES",
]
