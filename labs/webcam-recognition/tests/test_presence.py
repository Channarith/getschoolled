"""Presence fusion + absence hold tests."""

from webcam_lab.presence import AbsencePolicy, PresenceFusion, fuse_batch


def test_face_or_silhouette_keeps_present():
    f = PresenceFusion(AbsencePolicy(grace_seconds=5))
    v1 = f.observe(face_count=1, body_present=False, now=0)
    assert v1.present is True
    v2 = f.observe(face_count=0, body_present=True, silhouette_count=1, silhouette_confidence=0.8, now=1)
    assert v2.present is True


def test_absence_grace_then_hold():
    f = PresenceFusion(AbsencePolicy(grace_seconds=3))
    assert f.observe(face_count=0, body_present=False, now=0).hold_recommended is False
    assert f.observe(face_count=0, body_present=False, now=2).hold_recommended is False
    hold = f.observe(face_count=0, body_present=False, now=3)
    assert hold.present is False
    assert hold.hold_recommended is True
    assert hold.liveness_state == "absent"


def test_return_clears_absent_timer():
    f = PresenceFusion(AbsencePolicy(grace_seconds=2))
    f.observe(face_count=0, body_present=False, now=0)
    f.observe(face_count=0, body_present=False, now=1)
    back = f.observe(face_count=1, body_present=True, silhouette_count=1, silhouette_confidence=0.9, now=2)
    assert back.present is True
    assert f.absent_started_at is None


def test_fuse_batch_hold():
    verdicts = fuse_batch(
        [
            {"face_count": 0, "body_present": False, "now": 0},
            {"face_count": 0, "body_present": False, "now": 1},
            {"face_count": 0, "body_present": False, "now": 2},
        ],
        policy=AbsencePolicy(grace_seconds=2),
    )
    assert verdicts[-1].hold_recommended is True


def test_require_both_face_and_silhouette():
    f = PresenceFusion(
        AbsencePolicy(require_face=True, require_silhouette=True, grace_seconds=99)
    )
    only_face = f.observe(face_count=1, body_present=False, now=0)
    assert only_face.present is False
    both = f.observe(
        face_count=1, body_present=True, silhouette_count=1, silhouette_confidence=0.7, now=1
    )
    assert both.present is True
