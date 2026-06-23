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
)


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

    ordered = store.list()
    assert [c.id for c in ordered] == [past.id, soon.id, later.id]

    upcoming = store.list(upcoming_only=True)
    assert past.id not in {c.id for c in upcoming}
    assert {soon.id, later.id} <= {c.id for c in upcoming}


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


def test_bridge_plan_salareen_vs_external():
    salareen = GroupClass(title="t", lesson_id="a", start_time=_iso(10))
    plan = bridge_plan(salareen)
    assert plan["needs_bridge"] is False
    assert plan["livekit_room"].startswith("class-")

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
