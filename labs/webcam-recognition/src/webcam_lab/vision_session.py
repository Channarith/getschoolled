"""Webcam frame loop: silhouette + optional face → PresenceTracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .presence import FaceObservation, PresenceReport, PresenceTracker
from .silhouette import SilhouetteDetector, SilhouetteHit


@dataclass
class FrameAnalysis:
    faces: List[FaceObservation]
    silhouettes: List[SilhouetteHit]
    report: PresenceReport


class VisionSession:
    """Analyze webcam frames for class presence (face + silhouette + absence)."""

    def __init__(
        self,
        *,
        tracker: Optional[PresenceTracker] = None,
        silhouette: Optional[SilhouetteDetector] = None,
        participant_id: str = "learner",
        face_engine=None,
    ) -> None:
        self.tracker = tracker or PresenceTracker()
        self.silhouette = silhouette or SilhouetteDetector()
        self.participant_id = participant_id
        self._face_engine = face_engine

    def analyze_frame(self, frame) -> FrameAnalysis:
        faces = self._detect_faces(frame)
        sils = self.silhouette.detect(frame)
        report = self.tracker.observe(
            faces=faces,
            silhouettes=sils,
            participant_id=self.participant_id,
        )
        return FrameAnalysis(faces=faces, silhouettes=sils, report=report)

    def analyze_detections(
        self,
        *,
        faces: Sequence[FaceObservation] = (),
        silhouettes: Sequence[SilhouetteHit] = (),
    ) -> FrameAnalysis:
        faces_l = list(faces)
        sils_l = list(silhouettes)
        report = self.tracker.observe(
            faces=faces_l,
            silhouettes=sils_l,
            participant_id=self.participant_id,
        )
        return FrameAnalysis(faces=faces_l, silhouettes=sils_l, report=report)

    def _detect_faces(self, frame) -> List[FaceObservation]:
        if frame is None:
            return []
        engine = self._face_engine
        if engine is None:
            engine = self._try_aoep_face_engine()
            self._face_engine = engine
        if engine is None:
            return []
        try:
            detected = engine.detect(frame)
        except Exception:
            return []
        out: List[FaceObservation] = []
        for face in detected:
            attention = 0.0
            gaze = 0.0
            landmarks = getattr(face, "landmarks", None) or []
            bbox = tuple(int(v) for v in face.bbox)
            frame_size = getattr(face, "frame_size", None) or (
                int(frame.shape[1]),
                int(frame.shape[0]),
            )
            if landmarks and len(landmarks) >= 5:
                try:
                    from aoep_shared.vision import estimate_engagement  # type: ignore

                    eng = estimate_engagement(landmarks, bbox, frame_size)
                    attention = float(eng.attention)
                    gaze = float(eng.gaze_frontal)
                except Exception:
                    attention = float(getattr(face, "det_score", 0.7) or 0.7)
                    gaze = attention
            else:
                attention = float(getattr(face, "det_score", 0.7) or 0.7)
                gaze = attention
            out.append(
                FaceObservation(
                    bbox=bbox,  # type: ignore[arg-type]
                    det_score=float(getattr(face, "det_score", 0.0) or 0.0),
                    attention=attention,
                    gaze_frontal=gaze,
                )
            )
        return out

    def _try_aoep_face_engine(self):
        """Optionally reuse AOEP YuNet+SFace when aoep_shared[vision] is installed."""
        try:
            from aoep_shared.vision import FaceRecognitionEngine  # type: ignore

            return FaceRecognitionEngine.from_models(allow_download=True)
        except Exception:
            return None


def synthetic_person_frame(
    width: int = 320,
    height: int = 240,
    *,
    with_body: bool = True,
    with_face_box: bool = False,
) -> Tuple[object, List[FaceObservation]]:
    """Create a simple ndarray frame for offline silhouette tests."""
    import numpy as np

    frame = np.full((height, width, 3), 220, dtype="uint8")
    faces: List[FaceObservation] = []
    if with_body:
        # Dark vertical body blob in center.
        x0, x1 = width // 3, 2 * width // 3
        y0, y1 = height // 5, 4 * height // 5
        frame[y0:y1, x0:x1] = 30
    if with_face_box:
        fx, fy, fw, fh = width // 2 - 20, height // 5, 40, 40
        frame[fy : fy + fh, fx : fx + fw] = 60
        faces.append(
            FaceObservation((fx, fy, fw, fh), det_score=0.92, attention=0.8, gaze_frontal=0.85)
        )
    return frame, faces
