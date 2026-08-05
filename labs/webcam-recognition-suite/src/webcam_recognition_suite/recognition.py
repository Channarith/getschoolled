"""Per-frame class recognition: faces + silhouettes + engagement proxy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional, Sequence

from .silhouette import SilhouetteDetector, SilhouetteFrameResult


@dataclass
class FaceSignal:
    """Lightweight face observation (lab / hybrid path)."""

    bbox: tuple = (0, 0, 0, 0)
    score: float = 0.0
    matched_student_id: Optional[str] = None
    attention: float = 0.0
    expression: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClassRecognitionFrame:
    """One webcam tick for a seat in a solo or group class."""

    seat_id: str
    face_count: int
    faces: List[FaceSignal] = field(default_factory=list)
    silhouettes: SilhouetteFrameResult = field(
        default_factory=lambda: SilhouetteFrameResult(0, [], False, 0.0)
    )
    attention: float = 0.0
    consented: bool = True

    def to_dict(self) -> dict:
        return {
            "seat_id": self.seat_id,
            "face_count": self.face_count,
            "faces": [f.to_dict() for f in self.faces],
            "silhouettes": self.silhouettes.to_dict(),
            "attention": round(self.attention, 4),
            "consented": self.consented,
        }


def recognize_frame(
    frame: Any,
    *,
    seat_id: str = "seat-1",
    consented_student_ids: Optional[Sequence[str]] = None,
    silhouette_mode: str = "auto",
) -> ClassRecognitionFrame:
    """Analyze one webcam frame (or SyntheticFrame) for class recognition.

    Uses annotated synthetic metadata when present so CI stays offline. When a
    real image + OpenCV models are available, callers may precompute face
    signals and attach them to the SyntheticFrame.
    """
    consented = list(consented_student_ids or [])
    faces: List[FaceSignal] = []
    if hasattr(frame, "faces"):
        for raw in getattr(frame, "faces") or []:
            if isinstance(raw, FaceSignal):
                faces.append(raw)
            elif isinstance(raw, dict):
                sid = raw.get("matched_student_id")
                if sid and consented and sid not in consented:
                    sid = None
                faces.append(
                    FaceSignal(
                        bbox=tuple(raw.get("bbox", (0, 0, 0, 0))),
                        score=float(raw.get("score", 0.0) or 0.0),
                        matched_student_id=sid,
                        attention=float(raw.get("attention", 0.0) or 0.0),
                        expression=str(raw.get("expression", "unknown") or "unknown"),
                    )
                )

    sil_detector = SilhouetteDetector(mode=silhouette_mode)
    silhouettes = sil_detector.detect(frame)
    attention = 0.0
    if faces:
        attention = sum(f.attention for f in faces) / len(faces)
    elif silhouettes.body_present:
        attention = min(0.55, 0.35 + 0.2 * silhouettes.confidence)

    return ClassRecognitionFrame(
        seat_id=seat_id,
        face_count=len(faces),
        faces=faces,
        silhouettes=silhouettes,
        attention=round(attention, 4),
        consented=bool(consented) or not any(
            f.matched_student_id for f in faces
        ),
    )
