"""Shared silhouette / body-presence helpers."""

from aoep_shared.vision import (
    SilhouetteDetection,
    estimate_body_presence,
    fuse_face_and_silhouette,
)


def test_estimate_body_presence():
    signals = estimate_body_presence(
        [
            SilhouetteDetection(
                bbox=(100, 20, 200, 400),
                score=0.75,
                centered=True,
                frame_size=(640, 480),
            )
        ]
    )
    assert signals.body_present is True
    assert signals.confidence >= 0.75
    assert signals.person_count == 1


def test_fuse_default_or_policy():
    ok, reason = fuse_face_and_silhouette(face_count=0, body_present=True)
    assert ok is True
    assert reason == "silhouette"
    ok, reason = fuse_face_and_silhouette(face_count=1, body_present=False)
    assert ok is True
    assert reason == "face"
    ok, reason = fuse_face_and_silhouette(face_count=0, body_present=False)
    assert ok is False
    assert reason == "user_absent"


def test_fuse_require_both():
    ok, _ = fuse_face_and_silhouette(
        face_count=1, body_present=False, require_face=True, require_silhouette=True
    )
    assert ok is False
