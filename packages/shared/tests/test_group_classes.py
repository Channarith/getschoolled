"""Tests for the scheduled group-class engine (aoep_shared.group_classes)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aoep_shared.group_classes import (
    BRIDGED_PLATFORMS,
    ClassFullError,
    GroupClass,
    GroupClassError,
    GroupClassStore,
    bridge_plan,
    calendar_ics,
    ensure_standard_daily_classes,
    google_meet_url,
    standard_class_id,
)


def test_standard_class_id_is_deterministic():
    a = standard_class_id("salareen", "intro-to-fractions", "2026-07-13T14:00:00+00:00")
    b = standard_class_id("salareen", "intro-to-fractions", "2026-07-13T14:00:00+00:00")
    c = standard_class_id("meet", "intro-to-fractions", "2026-07-13T14:00:00+00:00")
    assert a == b                 # same inputs -> same id
    assert a != c                 # platform differs -> different id
    assert a.startswith("std") and len(a) == 12


def test_seeded_classes_use_deterministic_ids_and_are_idempotent():
    store = GroupClassStore()
    n1 = ensure_standard_daily_classes(store)
    assert n1 > 0
    # Re-seeding creates nothing new (dedup by deterministic id).
    assert ensure_standard_daily_classes(store) == 0
    for gc in store.list(upcoming_only=False):
        assert gc.id == standard_class_id(gc.platform, gc.lesson_id, gc.start_time)


def test_two_replicas_agree_on_ids():
    """Simulate two orchestrator replicas: a class listed by one is found in the
    other (the fix for the 'unknown group class' 404 on start)."""
    replica_a = GroupClassStore()
    replica_b = GroupClassStore()
    ensure_standard_daily_classes(replica_a)
    ensure_standard_daily_classes(replica_b)
    listed = replica_a.list(upcoming_only=True)
    assert listed
    for gc in listed:
        assert replica_b.get(gc.id) is not None, f"{gc.id} missing on replica B"


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def test_schedule_normalizes_and_defaults():
    store = GroupClassStore()
    gc = store.schedule(
        title="  Photosynthesis 101  ",
        lesson_id="intro-to-photosynthesis",
        start_time=_iso(60),
    )
    assert gc.title == "Photosynthesis 101"
    assert gc.platform == "salareen"
    assert gc.room_size == 6
    assert gc.capacity == 5
    assert gc.status == "scheduled"
    assert gc.seats_left == gc.capacity
    assert gc.needs_bridge is False
    assert store.get(gc.id) is gc


def test_bridged_platform_requires_meeting_url():
    store = GroupClassStore()
    with pytest.raises(GroupClassError):
        store.schedule(
            title="Fractions live on Zoom",
            lesson_id="intro-to-fractions",
            platform="zoom",
            start_time=_iso(30),
        )
    gc = store.schedule(
        title="Fractions live on Zoom",
        lesson_id="intro-to-fractions",
        platform="zoom",
        meeting_url="https://zoom.us/j/123456789",
        start_time=_iso(30),
    )
    assert gc.needs_bridge is True
    assert gc.platform in BRIDGED_PLATFORMS


def test_invalid_inputs_rejected():
    store = GroupClassStore()
    with pytest.raises(GroupClassError):
        store.schedule(title="", lesson_id="x", start_time=_iso(10))
    with pytest.raises(GroupClassError):
        store.schedule(title="t", lesson_id="", start_time=_iso(10))
    with pytest.raises(GroupClassError):
        store.schedule(title="t", lesson_id="x", platform="webex", start_time=_iso(10))
    with pytest.raises(GroupClassError):
        store.schedule(title="t", lesson_id="x", start_time="not-a-date")
    with pytest.raises(GroupClassError):
        store.schedule(title="t", lesson_id="x", start_time=_iso(10), capacity=0)


def test_list_sorted_and_upcoming_filter():
    store = GroupClassStore()
    later = store.schedule(title="Later", lesson_id="a", start_time=_iso(120))
    soon = store.schedule(title="Soon", lesson_id="b", start_time=_iso(10))
    past = store.schedule(title="Past", lesson_id="c", start_time=_iso(-300))

    # A long-past class is auto-deleted (its allotted time is over), so it no
    # longer appears in ANY listing; the remaining classes sort soonest-first.
    ordered = store.list()
    assert [c.id for c in ordered] == [soon.id, later.id]
    assert store.get(past.id) is None

    upcoming = store.list(upcoming_only=True)
    assert past.id not in {c.id for c in upcoming}
    assert {soon.id, later.id} <= {c.id for c in upcoming}


def test_live_class_past_window_is_deleted():
    # A class started 5h ago (60-min window) must not linger as LIVE/joinable —
    # once its allotted time is over it is auto-deleted (removed entirely).
    store = GroupClassStore()
    stale = store.schedule(title="Stale", lesson_id="a", start_time=_iso(-300), duration_min=60)
    store.set_status(stale.id, "live")
    upcoming = store.list(upcoming_only=True)
    assert stale.id not in {c.id for c in upcoming}
    assert store.get(stale.id) is None


def test_purge_expired_keeps_just_ended_within_grace():
    # A class that ended only ~1 min ago stays briefly (grace) so its farewell can
    # show; it's dropped from the upcoming listing but not yet deleted.
    store = GroupClassStore()
    just = store.schedule(title="JustEnded", lesson_id="a", start_time=_iso(-61), duration_min=60)
    assert store.purge_expired() == 0
    assert store.get(just.id) is not None
    assert just.id not in {c.id for c in store.list(upcoming_only=True)}


def test_sweep_expired_leaves_current_classes_alone():
    store = GroupClassStore()
    live_now = store.schedule(title="Now", lesson_id="a", start_time=_iso(-10), duration_min=60)
    store.set_status(live_now.id, "live")   # started 10 min ago, still within the hour
    assert store.sweep_expired() == 0
    assert store.require(live_now.id).status == "live"


def test_register_capacity_and_idempotency():
    store = GroupClassStore()
    gc = store.schedule(
        title="Tiny class", lesson_id="a", start_time=_iso(10), capacity=2
    )
    store.register(gc.id, "Ada", "ada@example.com")
    store.register(gc.id, "Grace", "grace@example.com")
    assert gc.seats_left == 0
    assert gc.is_full is True
    with pytest.raises(ClassFullError):
        store.register(gc.id, "Linus", "linus@example.com")
    # Same email re-registering is idempotent (no extra seat consumed).
    again = store.register(gc.id, "Ada", "ada@example.com")
    assert again.email == "ada@example.com"
    assert len(gc.registrations) == 2


def test_register_unknown_class_raises_keyerror():
    store = GroupClassStore()
    with pytest.raises(KeyError):
        store.register("nope", "Ada")


def test_register_requires_name():
    store = GroupClassStore()
    gc = store.schedule(title="t", lesson_id="a", start_time=_iso(10))
    with pytest.raises(GroupClassError):
        store.register(gc.id, "   ")


def test_to_dict_includes_derived_fields():
    store = GroupClassStore()
    gc = store.schedule(title="t", lesson_id="a", start_time=_iso(10), capacity=5)
    store.register(gc.id, "Ada")
    d = gc.to_dict()
    assert d["seats_left"] == 4
    assert d["registered"] == 1
    assert d["needs_bridge"] is False
    assert d["id"] == gc.id


def test_salareen_room_size_caps_capacity():
    store = GroupClassStore()
    gc = store.schedule(
        title="Grid class",
        lesson_id="a",
        start_time=_iso(10),
        platform="salareen",
        room_size=9,
        capacity=200,
    )
    assert gc.room_size == 9
    assert gc.capacity == 8


def test_bridge_plan_salareen_vs_external():
    salareen = GroupClass(title="t", lesson_id="a", start_time=_iso(10))
    plan = bridge_plan(salareen)
    assert plan["needs_bridge"] is False
    assert plan["livekit_room"].startswith("class-")
    assert plan["room_size"] == 6
    assert "/live-room/" in plan["join_path"]

    zoom = GroupClass(
        title="t",
        lesson_id="a",
        platform="zoom",
        meeting_url="https://zoom.us/j/123456789",
        start_time=_iso(10),
    )
    zplan = bridge_plan(zoom)
    assert zplan["needs_bridge"] is True
    assert zplan["platform"] == "zoom"
    assert zplan["meeting_ref"] == "https://zoom.us/j/123456789"
    assert zplan["connect_endpoint"] == "/bridges/zoom/connect"


def test_set_status_and_ended_blocks_registration():
    store = GroupClassStore()
    gc = store.schedule(title="t", lesson_id="a", start_time=_iso(10))
    store.set_status(gc.id, "ended")
    with pytest.raises(GroupClassError):
        store.register(gc.id, "Ada")
    with pytest.raises(GroupClassError):
        store.set_status(gc.id, "bogus")


def test_google_meet_url_and_calendar_ics():
    store = GroupClassStore()
    gc = store.schedule(
        title="Midday class",
        lesson_id="intro-to-fractions",
        platform="meet",
        meeting_url=google_meet_url("seed"),
        start_time=_iso(120),
    )
    assert gc.meeting_url.startswith("https://meet.google.com/")
    ics = calendar_ics(gc, attendee_name="Ada", attendee_email="ada@example.com")
    assert "BEGIN:VCALENDAR" in ics
    assert "ada@example.com" in ics


def test_ensure_standard_daily_classes_idempotent():
    store = GroupClassStore()
    n1 = ensure_standard_daily_classes(store, days_ahead=3)
    n2 = ensure_standard_daily_classes(store, days_ahead=3)
    assert n1 >= 0
    assert n2 == 0
    meet_classes = [c for c in store.list() if c.platform == "meet"]
    assert meet_classes
