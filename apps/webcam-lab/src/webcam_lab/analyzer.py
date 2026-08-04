"""Frame analyzer for the webcam lab (face engagement + silhouette)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aoep_shared.vision.absence import FramePresenceInput
from aoep_shared.vision.engagement import estimate_engagement
from aoep_shared.vision.silhouette import SilhouetteSignals, detect_silhouette


@dataclass
class FrameAnalysis:
    face_count: int
    attention: float
    gaze_frontal: float
    expression: str
    silhouette: SilhouetteSignals
    faces: List[Dict[str, Any]]
    engine: str  # hybrid_report | on_device | opencv | synthetic

    def to_presence_input(self, *, liveness_ok: bool = True, reason: str = "") -> FramePresenceInput:
        return FramePresenceInput(
            face_count=self.face_count,
            attention=self.attention,
            gaze_frontal=self.gaze_frontal,
            silhouette=self.silhouette,
            liveness_ok=liveness_ok,
            reason=reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_count": self.face_count,
            "attention": self.attention,
            "gaze_frontal": self.gaze_frontal,
            "expression": self.expression,
            "silhouette": {
                "present": self.silhouette.present,
                "person_count": self.silhouette.person_count,
                "confidence": self.silhouette.confidence,
                "observations": [
                    {
                        "bbox": list(o.bbox),
                        "confidence": o.confidence,
                        "source": o.source,
                        "area_ratio": o.area_ratio,
                    }
                    for o in self.silhouette.observations
                ],
            },
            "faces": self.faces,
            "engine": self.engine,
        }


def analyze_reported(
    *,
    face_count: int = 0,
    attention: float = 0.0,
    gaze_frontal: float = 0.0,
    expression: str = "unknown",
    silhouette_present: bool = False,
    silhouette_confidence: float = 0.8,
    faces: Optional[List[Dict[str, Any]]] = None,
) -> FrameAnalysis:
    """Build analysis from client-reported hybrid signals (no raw frame)."""
    from aoep_shared.vision.silhouette import silhouette_from_counts

    sil = silhouette_from_counts(
        person_count=1 if silhouette_present else 0,
        confidence=silhouette_confidence,
    )
    return FrameAnalysis(
        face_count=max(0, int(face_count)),
        attention=max(0.0, min(1.0, float(attention))),
        gaze_frontal=max(0.0, min(1.0, float(gaze_frontal))),
        expression=expression or "unknown",
        silhouette=sil,
        faces=list(faces or []),
        engine="hybrid_report",
    )


def analyze_frame_bytes(image_bytes: bytes) -> FrameAnalysis:
    """Analyze a webcam JPEG/PNG frame.

    Tries OpenCV YuNet face path when models are available; always runs
    silhouette detection (HOG or energy fallback).
    """
    silhouette = detect_silhouette(image_bytes)
    faces_out: List[Dict[str, Any]] = []
    attention = 0.0
    gaze = 0.0
    expression = "unknown"
    engine = "silhouette_only"

    try:
        import os

        from aoep_shared.vision.models import ensure_models

        model_dir = os.environ.get("VISION_MODEL_DIR", "")
        detector_path, recognizer_path = ensure_models(model_dir or None)
        from aoep_shared.vision.engine import FaceRecognitionEngine

        engine_impl = FaceRecognitionEngine(detector_path, recognizer_path)
        detected = engine_impl.detect_faces(image_bytes)
        for face in detected:
            eng = estimate_engagement(face.landmarks, face.bbox, face.frame_size)
            faces_out.append(
                {
                    "bbox": list(face.bbox),
                    "det_score": face.det_score,
                    "attention": eng.attention,
                    "gaze_frontal": eng.gaze_frontal,
                    "expression": eng.expression,
                }
            )
            attention = max(attention, eng.attention)
            gaze = max(gaze, eng.gaze_frontal)
            if eng.expression != "unknown":
                expression = eng.expression
        engine = "opencv"
    except Exception:
        # Models/network/opencv unavailable — silhouette path still useful.
        engine = "silhouette_only"

    return FrameAnalysis(
        face_count=len(faces_out),
        attention=round(attention, 4),
        gaze_frontal=round(gaze, 4),
        expression=expression,
        silhouette=silhouette,
        faces=faces_out,
        engine=engine,
    )
