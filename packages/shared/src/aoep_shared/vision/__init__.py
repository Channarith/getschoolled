"""Self-hosted face recognition + attention for the perception service.

Biometrics stay inside the configured boundary (compliance lever). The engine is
backed by OpenCV's YuNet (detection) + SFace (128-d embeddings), runs on CPU, and
needs no GPU. Model weights are downloaded at runtime and kept out of the repo.

Public surface:
- ``FaceRecognitionEngine`` - detect faces and compute embeddings.
- ``FaceGallery``           - enroll embeddings and match (1:N) with a threshold.
- ``DetectedFace``          - a detected face (bbox, score, embedding).
- ``SilhouetteDetector``    - body presence via MOG2 background subtraction.
- ``WebcamPresenceTracker`` - debounced absence/presence tracking per session.
- model helpers in ``aoep_shared.vision.models``.
"""

from .engagement import EngagementSignals, GestureRecognizer, estimate_engagement
from .engine import DetectedFace, FaceRecognitionEngine
from .gallery import FaceGallery, Match
from .silhouette import SilhouetteDetector, SilhouetteResult, estimate_silhouette_from_fraction
from .webcam_presence import PresenceFrame, PresenceMetrics, PresenceState, WebcamPresenceTracker

__all__ = [
    "DetectedFace",
    "FaceRecognitionEngine",
    "FaceGallery",
    "Match",
    "EngagementSignals",
    "GestureRecognizer",
    "estimate_engagement",
    "SilhouetteDetector",
    "SilhouetteResult",
    "estimate_silhouette_from_fraction",
    "PresenceFrame",
    "PresenceMetrics",
    "PresenceState",
    "WebcamPresenceTracker",
]
