"""Kid-safe cute confidence scoring."""

from theodore_webcam_lab.cute_score import (
    CUTE_PASS_THRESHOLD,
    CUTE_SCORE_FLOOR,
    cute_confidence_score,
    cute_encouragement,
)


def test_cute_score_has_encouraging_floor_when_face_present():
    score = cute_confidence_score(face_present=True)
    assert score >= CUTE_SCORE_FLOOR
    assert "appearance" not in cute_encouragement(score).lower()


def test_cute_score_rewards_smile_and_accessories_not_looks():
    plain = cute_confidence_score(face_present=True, smile_score=0.0, accessory_count=0)
    dressed = cute_confidence_score(
        face_present=True,
        smile_score=0.8,
        gaze_frontal=0.9,
        accessory_count=3,
        head_pose_yaw=2,
        head_pose_roll=1,
    )
    assert dressed > plain
    assert dressed >= CUTE_PASS_THRESHOLD


def test_cute_encouragement_is_always_positive_wording():
    for score in (0, 40, 65, 85, 95):
        msg = cute_encouragement(score)
        assert msg
        lowered = msg.lower()
        assert "ugly" not in lowered
        assert "fat" not in lowered
        assert "pretty enough" not in lowered
