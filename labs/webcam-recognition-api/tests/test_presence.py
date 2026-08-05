"""Tests for the debounced presence / user-absence state machine."""

from __future__ import annotations

from webcam_recognition.presence import (
    PresenceEvent,
    PresenceState,
    PresenceTracker,
)


def test_first_present_signal_arrives():
    t = PresenceTracker(absent_grace_s=4, present_grace_s=1)
    snap = t.update(True, now=0.0)
    assert snap.state is PresenceState.PRESENT
    assert snap.event is PresenceEvent.ARRIVED


def test_absence_requires_grace_period():
    t = PresenceTracker(absent_grace_s=4, present_grace_s=1)
    t.update(True, now=0.0)
    # A brief blip under the grace window must NOT flip to absent.
    assert t.update(False, now=1.0).event is None
    assert t.update(False, now=3.0).event is None
    assert t.is_present is True
    # Past the grace window (>= 4s since first unseen at t=1.0) -> LEFT.
    snap = t.update(False, now=5.5)
    assert snap.event is PresenceEvent.LEFT
    assert snap.state is PresenceState.ABSENT


def test_quick_glance_away_does_not_leave():
    t = PresenceTracker(absent_grace_s=4, present_grace_s=1)
    t.update(True, now=0.0)
    t.update(False, now=1.0)     # starts pending-absent
    snap = t.update(True, now=2.0)  # came back before grace -> cancel
    assert snap.event is None
    assert t.is_present is True


def test_return_requires_present_grace():
    t = PresenceTracker(absent_grace_s=2, present_grace_s=1)
    t.update(True, now=0.0)
    t.update(False, now=3.0)  # starts pending-absent window
    t.update(False, now=6.0)  # grace elapsed -> LEFT (now absent)
    assert t.is_absent is True
    assert t.update(True, now=6.2).event is None  # under present grace
    snap = t.update(True, now=7.5)                # past present grace -> RETURNED
    assert snap.event is PresenceEvent.RETURNED
    assert snap.state is PresenceState.PRESENT


def test_away_and_present_time_accumulate():
    t = PresenceTracker(absent_grace_s=1, present_grace_s=1)
    t.update(True, now=0.0)
    t.update(True, now=10.0)   # +10s present
    t.update(False, now=11.0)  # still present (pending)
    t.update(False, now=12.5)  # LEFT (grace elapsed); accumulates present time
    t.update(False, now=20.0)  # +away time
    assert t.present_seconds_total >= 11.0
    assert t.away_seconds_total >= 7.0


def test_events_list_records_transitions():
    t = PresenceTracker(absent_grace_s=1, present_grace_s=1)
    t.update(True, now=0.0)
    t.update(False, now=2.0)
    t.update(False, now=3.5)   # LEFT
    t.update(True, now=5.0)
    t.update(True, now=6.5)    # RETURNED
    assert t.events == [PresenceEvent.LEFT, PresenceEvent.RETURNED]


def test_starts_absent_if_first_signal_absent():
    t = PresenceTracker()
    snap = t.update(False, now=0.0)
    assert snap.state is PresenceState.ABSENT
    assert snap.event is None
