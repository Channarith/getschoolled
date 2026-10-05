"""Kid-safe 'cute confidence' scoring for the Am I Cute Enough game.

Scores reward visible face presence, warm expressions, fun accessories, and
steady frontal pose — never appearance, body shape, or skin tone. Every child
with a face in frame gets an encouraging floor score.
"""

from __future__ import annotations

CUTE_SCORE_FLOOR = 45
CUTE_PASS_THRESHOLD = 60


def pose_frontal_score(
    *,
    head_pose_yaw: float | None = None,
    head_pose_roll: float | None = None,
) -> float:
    """0..1 — reward looking toward the camera, not a beauty metric."""
    yaw = abs(float(head_pose_yaw or 0.0))
    roll = abs(float(head_pose_roll or 0.0))
    return max(0.0, min(1.0, 1.0 - (yaw / 45.0) * 0.55 - (roll / 35.0) * 0.35))


def cute_confidence_score(
    *,
    face_present: bool,
    smile_score: float = 0.0,
    gaze_frontal: float = 0.5,
    accessory_count: int = 0,
    head_pose_yaw: float | None = None,
    head_pose_roll: float | None = None,
) -> int:
    """Return 0..100 confidence vibe score (kid-safe, never appearance-shaming)."""
    if not face_present:
        return 0
    pose = pose_frontal_score(head_pose_yaw=head_pose_yaw, head_pose_roll=head_pose_roll)
    smile_boost = min(25.0, max(0.0, float(smile_score)) * 28.0)
    gaze_boost = min(15.0, max(0.0, float(gaze_frontal)) * 18.0)
    accessory_boost = min(15.0, min(max(0, int(accessory_count)), 6) * 3.0)
    pose_boost = min(10.0, pose * 10.0)
    total = CUTE_SCORE_FLOOR + smile_boost + gaze_boost + accessory_boost + pose_boost
    return min(100, int(round(total)))


def cute_encouragement(score: int) -> str:
    """Always positive wording — describes energy, never looks."""
    if score >= 92:
        return "Sparkle superstar energy! Your confident vibe lights up the room."
    if score >= 80:
        return "Amazing confident vibe! Love how you showed up for the camera."
    if score >= 68:
        return "Great energy! Your smile and style really shine."
    if score >= CUTE_PASS_THRESHOLD:
        return "You look ready to shine — wonderful playful confidence!"
    if score >= 40:
        return "Nice start! Add a smile or fun accessory and try again."
    return "Step into the camera so we can cheer you on!"


def accessory_count_from_ids(*accessory_ids: str | None) -> int:
    """Count non-empty accessory slots (costume + props)."""
    return sum(1 for item in accessory_ids if item and item != "none")
