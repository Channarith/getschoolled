"""Synthetic webcam frames for offline lab tests (no camera / no OpenCV)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .recognition import FaceSignal
from .silhouette import SilhouetteDetection


@dataclass
class SyntheticFrame:
    """Annotated stand-in for a webcam image.

    Recognition and silhouette detectors read ``faces`` / ``silhouettes``
    directly so CI never needs pixels or model weights.
    """

    width: int = 640
    height: int = 480
    faces: List[FaceSignal] = field(default_factory=list)
    silhouettes: List[SilhouetteDetection] = field(default_factory=list)
    label: str = ""


def present_learner(
    *,
    student_id: str = "alice",
    attention: float = 0.85,
    with_face: bool = True,
    with_body: bool = True,
) -> SyntheticFrame:
    faces: List[FaceSignal] = []
    silhouettes: List[SilhouetteDetection] = []
    if with_face:
        faces.append(
            FaceSignal(
                bbox=(220, 80, 160, 200),
                score=0.95,
                matched_student_id=student_id,
                attention=attention,
                expression="neutral",
            )
        )
    if with_body:
        silhouettes.append(
            SilhouetteDetection(
                bbox=(180, 40, 240, 400),
                score=0.8,
                source="synthetic",
                centered=True,
                frame_size=(640, 480),
            )
        )
    return SyntheticFrame(faces=faces, silhouettes=silhouettes, label="present")


def absent_learner() -> SyntheticFrame:
    return SyntheticFrame(faces=[], silhouettes=[], label="absent")


def body_only_learner() -> SyntheticFrame:
    """Silhouette visible but face not detectable (turned away / mask edge)."""
    return SyntheticFrame(
        faces=[],
        silhouettes=[
            SilhouetteDetection(
                bbox=(200, 60, 220, 380),
                score=0.72,
                source="synthetic",
                centered=True,
                frame_size=(640, 480),
            )
        ],
        label="body_only",
    )


def face_only_learner(student_id: str = "alice") -> SyntheticFrame:
    """Face visible but no full-body silhouette (tight crop / seated close)."""
    return SyntheticFrame(
        faces=[
            FaceSignal(
                bbox=(240, 120, 140, 180),
                score=0.9,
                matched_student_id=student_id,
                attention=0.7,
                expression="neutral",
            )
        ],
        silhouettes=[],
        label="face_only",
    )
