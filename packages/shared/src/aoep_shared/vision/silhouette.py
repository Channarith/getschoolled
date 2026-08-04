"""Promote silhouette helpers into aoep_shared for production adoption.

The private webcam lab (labs/webcam-recognition) owns the full harness; this
module is the stable shared surface for person/silhouette presence used by
perception and live-room absence fusion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Sequence, Tuple


@dataclass
class SilhouetteDetection:
    """One person-sized region (bbox in pixels)."""

    bbox: Tuple[int, int, int, int]
    score: float
    source: str = "unknown"
    centered: bool = False
    frame_size: Tuple[int, int] = (0, 0)

    @property
    def area_ratio(self) -> float:
        fw, fh = self.frame_size
        if fw <= 0 or fh <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.bbox[2] * self.bbox[3]) / float(fw * fh)))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["area_ratio"] = round(self.area_ratio, 4)
        return d


@dataclass
class SilhouetteSignals:
    """Aggregate body-presence signals for one webcam frame."""

    person_count: int = 0
    body_present: bool = False
    confidence: float = 0.0
    detections: List[SilhouetteDetection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "person_count": self.person_count,
            "body_present": self.body_present,
            "confidence": round(self.confidence, 4),
            "detections": [d.to_dict() for d in self.detections],
        }


def estimate_body_presence(
    detections: Sequence[SilhouetteDetection],
    *,
    min_area_ratio: float = 0.02,
    min_score: float = 0.35,
) -> SilhouetteSignals:
    """Derive body-present / confidence from silhouette detections."""
    usable = [
        d
        for d in detections
        if d.score >= min_score
        and (d.area_ratio >= min_area_ratio or d.frame_size == (0, 0))
    ]
    if not usable:
        return SilhouetteSignals(person_count=len(list(detections)), body_present=False, confidence=0.0, detections=list(detections))
    best = max(usable, key=lambda d: d.score)
    conf = best.score
    if best.centered:
        conf = min(1.0, conf + 0.1)
    if best.area_ratio >= 0.08:
        conf = min(1.0, conf + 0.05)
    return SilhouetteSignals(
        person_count=len(list(detections)),
        body_present=True,
        confidence=round(conf, 4),
        detections=list(detections),
    )


def fuse_face_and_silhouette(
    *,
    face_count: int,
    body_present: bool,
    require_face: bool = False,
    require_silhouette: bool = False,
) -> Tuple[bool, str]:
    """Return (present, reason) using the classroom OR/AND policy.

    Default: either a face or a silhouette keeps the learner marked present
    (covers turned-away heads and tight face crops).
    """
    face_ok = int(face_count or 0) > 0
    body_ok = bool(body_present)
    if require_face and require_silhouette:
        ok = face_ok and body_ok
        return ok, ("present" if ok else "missing_face_or_silhouette")
    if require_face:
        return face_ok, ("present" if face_ok else "missing_face")
    if require_silhouette:
        return body_ok, ("present" if body_ok else "missing_silhouette")
    if face_ok or body_ok:
        return True, ("face" if face_ok else "silhouette")
    return False, "user_absent"
