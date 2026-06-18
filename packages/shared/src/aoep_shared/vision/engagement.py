"""Engagement signals from face geometry (attention/gaze + expression proxy).

Computed from the 5 facial landmarks the detector already provides, so it needs
no extra model and runs on CPU in real time:

- attention/gaze: how frontally the face is oriented (a turned-away head scores
  low) combined with how present the face is in frame -> a 0..1 attention score
  the Director/adaptive policy consumes.
- expression: a coarse proxy (neutral / smiling / surprised) from mouth-width and
  vertical openness relative to inter-ocular distance.

These are deliberately transparent heuristics. A dedicated expression model
(e.g. FER) and a gesture model (MediaPipe Hands/Pose) plug in behind the same
``EngagementSignals`` shape later (see ``GestureRecognizer``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass
class EngagementSignals:
    attention: float        # 0..1 (gaze frontal-ness * presence)
    gaze_frontal: float     # 0..1 (1 = looking straight at camera)
    expression: str         # neutral | smiling | surprised | unknown
    expression_score: float  # 0..1 confidence of the non-neutral expression


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def estimate_engagement(
    landmarks: Sequence[Tuple[float, float]],
    bbox: Tuple[int, int, int, int],
    frame_size: Tuple[int, int],
) -> EngagementSignals:
    """Derive engagement signals from landmarks (right_eye, left_eye, nose,
    right_mouth, left_mouth), the face bbox, and the frame size."""
    if len(landmarks) < 5 or frame_size[0] <= 0 or frame_size[1] <= 0:
        return EngagementSignals(0.0, 0.0, "unknown", 0.0)

    right_eye, left_eye, nose, right_mouth, left_mouth = landmarks[:5]
    inter_ocular = _dist(right_eye, left_eye) or 1.0

    # Gaze/frontal-ness: nose should sit horizontally between the eyes. The more
    # it deviates toward one eye, the more the head is turned away.
    eye_mid_x = (right_eye[0] + left_eye[0]) / 2.0
    horiz_offset = abs(nose[0] - eye_mid_x) / inter_ocular  # 0 frontal, grows turned
    gaze_frontal = max(0.0, 1.0 - horiz_offset * 1.6)

    # Presence: a reasonably sized, in-frame face is "present". Tiny/edge faces
    # (looked away / left) score lower.
    fw, fh = frame_size
    face_w = bbox[2] / fw
    cx = (bbox[0] + bbox[2] / 2.0) / fw
    centered = max(0.0, 1.0 - abs(cx - 0.5) * 1.2)
    size_presence = min(1.0, face_w / 0.12)  # ~12% frame width = fully present
    presence = 0.5 * centered + 0.5 * size_presence

    attention = max(0.0, min(1.0, 0.7 * gaze_frontal + 0.3 * presence))

    # Expression proxy.
    mouth_w = _dist(right_mouth, left_mouth) / inter_ocular
    mouth_mid = ((right_mouth[0] + left_mouth[0]) / 2.0,
                 (right_mouth[1] + left_mouth[1]) / 2.0)
    nose_to_mouth = _dist(nose, mouth_mid) / inter_ocular
    expression, expr_score = "neutral", 0.0
    if mouth_w > 1.05:
        expression, expr_score = "smiling", min(1.0, (mouth_w - 1.05) / 0.5)
    if nose_to_mouth > 1.15:
        # Elongated lower face -> open mouth / surprised; takes precedence.
        expression, expr_score = "surprised", min(1.0, (nose_to_mouth - 1.15) / 0.5)

    return EngagementSignals(
        attention=round(attention, 4),
        gaze_frontal=round(gaze_frontal, 4),
        expression=expression,
        expression_score=round(expr_score, 4),
    )


class GestureRecognizer:
    """Interface for hand/body gesture recognition (scaffold).

    A real implementation wraps MediaPipe Hands/Pose (raise-hand, thumbs-up,
    nodding/shaking) and returns a label per frame. Not available in this
    environment (needs the MediaPipe runtime + models), so this scaffold raises
    until configured; the Director can already consume the labels it will emit.
    """

    KNOWN_GESTURES = ("raise_hand", "thumbs_up", "thumbs_down", "wave", "nod", "shake")

    def recognize(self, frame: bytes) -> Optional[str]:
        raise NotImplementedError(
            "Gesture recognition requires the MediaPipe Hands/Pose runtime, "
            "which is not installed in this environment."
        )
