"""Presence tracker: face, silhouette-only, absence hold."""

from __future__ import annotations

from webcam_lab.presence import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_SILHOUETTE,
    PRESENCE_SPOOF,
    PRESENCE_UNKNOWN,
    PresenceTracker,
)


def test_verified_face_is_live():
    t = PresenceTracker(require_liveness=True, liveness_min_score=0.35)
    r = t.observe_counts(face_count=1, attention=0.9, gaze_frontal=0.9)
    assert r.present is True
    assert r.liveness_state == PRESENCE_LIVE
    assert r.reason == "verified"
    assert r.hold_recommended is False


def test_low_liveness_unknown_hold():
    t = PresenceTracker(require_liveness=True, liveness_min_score=0.35)
    r = t.observe_counts(face_count=1, attention=0.1, gaze_frontal=0.1)
    assert r.liveness_state == PRESENCE_UNKNOWN
    assert r.reason == "liveness_low"
    assert r.hold_recommended is True


def test_silhouette_only():
    t = PresenceTracker()
    r = t.observe_counts(face_count=0, silhouette_count=1)
    assert r.present is True
    assert r.liveness_state == PRESENCE_SILHOUETTE
    assert r.reason == "silhouette_only"
    payload = r.to_live_room_payload()
    assert payload["liveness_state"] == PRESENCE_UNKNOWN
    assert payload["present"] is True


def test_absence_after_streak():
    t = PresenceTracker(absent_after=3)
    r1 = t.observe_counts(face_count=0, silhouette_count=0)
    assert r1.liveness_state == PRESENCE_UNKNOWN
    assert r1.hold_recommended is False
    t.observe_counts(face_count=0, silhouette_count=0)
    r3 = t.observe_counts(face_count=0, silhouette_count=0)
    assert r3.liveness_state == PRESENCE_ABSENT
    assert r3.reason == "user_absent"
    assert r3.hold_recommended is True
    assert r3.to_live_room_payload()["liveness_state"] == PRESENCE_ABSENT


def test_too_many_faces_spoof():
    t = PresenceTracker(max_faces_allowed=1)
    r = t.observe_counts(face_count=2)
    assert r.liveness_state == PRESENCE_SPOOF
    assert r.reason == "too_many_faces"
    assert r.hold_recommended is True
