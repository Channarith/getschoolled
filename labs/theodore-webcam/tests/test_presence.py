"""Presence/absence state machine timing."""

from __future__ import annotations

from theodore_webcam.config import PresenceConfig
from theodore_webcam.presence import PresenceEventKind, PresenceState, PresenceTracker


def make_tracker(clock, **overrides):
    config = PresenceConfig(
        arrive_confirm_seconds=1.0,
        return_confirm_seconds=1.0,
        absence_grace_seconds=5.0,
        prolonged_absence_seconds=20.0,
        stale_seconds=8.0,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return PresenceTracker(config, clock=clock)


def feed(tracker, clock, *, detected, seconds, step=0.5):
    events = []
    elapsed = 0.0
    while elapsed < seconds:
        clock.advance(step)
        elapsed += step
        events.extend(tracker.update(detected=detected, confidence=0.9 if detected else 0.0,
                                     count=1 if detected else 0))
    return events


def test_arrival_requires_sustained_detection(clock):
    tracker = make_tracker(clock)
    events = feed(tracker, clock, detected=True, seconds=0.5)
    assert tracker.state is not PresenceState.PRESENT
    assert not [e for e in events if e.kind is PresenceEventKind.ARRIVED]

    events = feed(tracker, clock, detected=True, seconds=1.5)
    assert tracker.state is PresenceState.PRESENT
    assert [e for e in events if e.kind is PresenceEventKind.ARRIVED]


def test_brief_glance_away_does_not_fire_departure(clock):
    tracker = make_tracker(clock)
    feed(tracker, clock, detected=True, seconds=2.0)

    events = feed(tracker, clock, detected=False, seconds=3.0)
    assert tracker.state is PresenceState.DRIFTING
    assert not [e for e in events if e.kind is PresenceEventKind.DEPARTED]

    events = feed(tracker, clock, detected=True, seconds=1.5)
    assert tracker.state is PresenceState.PRESENT
    assert not [e for e in events if e.kind is PresenceEventKind.RETURNED]


def test_departure_after_grace_then_return_with_absence_duration(clock):
    tracker = make_tracker(clock)
    feed(tracker, clock, detected=True, seconds=2.0)

    events = feed(tracker, clock, detected=False, seconds=7.0)
    departed = [e for e in events if e.kind is PresenceEventKind.DEPARTED]
    assert len(departed) == 1
    assert tracker.state is PresenceState.ABSENT
    assert departed[0].absence_seconds >= 5.0

    feed(tracker, clock, detected=False, seconds=6.0)
    events = feed(tracker, clock, detected=True, seconds=1.5)
    returned = [e for e in events if e.kind is PresenceEventKind.RETURNED]
    assert len(returned) == 1
    assert returned[0].absence_seconds >= 13.0
    assert tracker.state is PresenceState.PRESENT
    assert tracker.stats.absence_count == 1
    assert tracker.stats.longest_absence_seconds >= 13.0


def test_prolonged_absence_fires_once(clock):
    tracker = make_tracker(clock)
    feed(tracker, clock, detected=True, seconds=2.0)
    events = feed(tracker, clock, detected=False, seconds=30.0)
    prolonged = [e for e in events if e.kind is PresenceEventKind.PROLONGED_ABSENCE]
    assert len(prolonged) == 1
    assert prolonged[0].absence_seconds >= 20.0

    events = feed(tracker, clock, detected=False, seconds=30.0)
    assert not [e for e in events if e.kind is PresenceEventKind.PROLONGED_ABSENCE]


def test_camera_going_dark_is_reported_as_stale(clock):
    tracker = make_tracker(clock)
    feed(tracker, clock, detected=True, seconds=2.0)

    clock.advance(9.0)
    events = tracker.tick()
    assert [e for e in events if e.kind is PresenceEventKind.STALE]
    assert tracker.state is PresenceState.STALE
    assert tracker.stats.absence_count == 1

    clock.advance(5.0)
    assert not tracker.tick()


def test_no_show_never_raises_prolonged_absence(clock):
    tracker = make_tracker(clock)
    events = feed(tracker, clock, detected=False, seconds=60.0)
    assert tracker.state is PresenceState.ABSENT
    assert not [e for e in events if e.kind is PresenceEventKind.PROLONGED_ABSENCE]
    assert not [e for e in events if e.kind is PresenceEventKind.DEPARTED]
    assert tracker.stats.first_seen_at is None


def test_stats_accumulate_present_and_absent_time(clock):
    tracker = make_tracker(clock)
    feed(tracker, clock, detected=True, seconds=10.0)
    feed(tracker, clock, detected=False, seconds=20.0)
    feed(tracker, clock, detected=True, seconds=10.0)

    stats = tracker.stats
    assert stats.present_seconds > 12.0
    assert stats.absent_seconds > 10.0
    assert 0.0 < stats.attention_ratio < 1.0
    snapshot = tracker.snapshot()
    assert snapshot.present is True
    assert snapshot.as_dict()["state"] == "present"
