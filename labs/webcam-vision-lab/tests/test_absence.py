"""Tests for absence tracker grace + hold semantics."""

from datetime import datetime, timedelta, timezone

from webcam_vision_lab.presence.absence import (
    AbsencePolicy,
    AbsenceState,
    AbsenceTracker,
    PresenceProbe,
)


def _probe(**kwargs) -> PresenceProbe:
    base = {
        "present": False,
        "face_count": 0,
        "liveness_state": "absent",
        "reason": "no_face",
        "observed_at": datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc),
    }
    base.update(kwargs)
    return PresenceProbe(**base)


def test_live_then_grace_then_hold():
    policy = AbsencePolicy(enabled=True, grace_seconds=90, max_faces_allowed=1)
    tracker = AbsenceTracker(policy)
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    live = _probe(
        present=True,
        face_count=1,
        liveness_state="live",
        reason="verified",
        observed_at=t0,
    )
    assert tracker.update(live) == AbsenceState.LIVE

    absent = _probe(observed_at=t0 + timedelta(seconds=1))
    assert tracker.update(absent) == AbsenceState.GRACE
    assert not tracker.hold_active

    hold_time = t0 + timedelta(seconds=95)
    tracker.update(_probe(observed_at=hold_time))
    assert tracker.state_at(hold_time) == AbsenceState.HOLD
    assert tracker.hold_active


def test_hold_clears_on_return():
    policy = AbsencePolicy(enabled=True, grace_seconds=1)
    tracker = AbsenceTracker(policy)
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    tracker.update(_probe(observed_at=t0))
    tracker.update(_probe(observed_at=t0 + timedelta(seconds=2)))
    assert tracker.hold_active

    back = _probe(
        present=True,
        face_count=1,
        liveness_state="live",
        reason="verified",
        observed_at=t0 + timedelta(seconds=3),
    )
    assert tracker.update(back) == AbsenceState.LIVE
    assert not tracker.hold_active


def test_disabled_policy_always_live():
    tracker = AbsenceTracker(AbsencePolicy(enabled=False))
    assert tracker.update(_probe()) == AbsenceState.LIVE
