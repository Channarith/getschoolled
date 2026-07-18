"""Tests for live-room social features (gifts, reactions, follows)."""

from __future__ import annotations

import pytest

from aoep_shared.live_room import LiveRoomStore
from aoep_shared.live_room_social import LiveRoomGiftLedger, REACTION_TYPES


def _open_room(store: LiveRoomStore) -> str:
    room = store.open_room(
        room_id="social-test",
        class_id="c1",
        session_id="s1",
        lesson_id="l1",
        title="Social test",
        room_size=6,
    )
    return room.room_id


def test_gift_catalog_and_send():
    ledger = LiveRoomGiftLedger(default_balance=1000)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Ada", identity="ada-1")
    before = store.gift_balance("ada-1")
    gift, balance = store.send_gift(room_id, sender.id, gift_id="rose")
    assert gift.emoji == "🌹"
    assert gift.cost_points == 10
    assert balance == before - 10
    room = store.require(room_id)
    assert len(room.gift_feed) == 1
    assert any("🌹" in m.text for m in room.chat)


def test_gift_can_target_another_student():
    ledger = LiveRoomGiftLedger(default_balance=1000)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Ada", identity="ada-target")
    recipient = store.join(room_id, "Grace", identity="grace-target")
    gift, _ = store.send_gift(
        room_id,
        sender.id,
        gift_id="star",
        recipient_participant_id=recipient.id,
    )
    assert gift.recipient_participant_id == recipient.id
    assert gift.recipient_name == "Grace"
    assert "to Grace" in store.require(room_id).chat[-1].text


def test_gift_insufficient_points():
    ledger = LiveRoomGiftLedger(default_balance=5)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Broke", identity="broke-1")
    with pytest.raises(Exception, match="insufficient"):
        store.send_gift(room_id, sender.id, gift_id="rose")


def test_reaction_broadcast_buffer():
    store = LiveRoomStore()
    room_id = _open_room(store)
    p = store.join(room_id, "Grace", identity="g1")
    for emoji in REACTION_TYPES[:3]:
        store.send_reaction(room_id, p.id, emoji=emoji)
    room = store.require(room_id)
    assert len(room.reactions) == 3
    with pytest.raises(Exception):
        store.send_reaction(room_id, p.id, emoji="invalid")


def test_follow_host():
    store = LiveRoomStore()
    room_id = _open_room(store)
    following, count = store.follow_host(room_id, "viewer-1")
    assert following is True
    assert count == 1
    following2, count2 = store.follow_host(room_id, "viewer-1")
    assert following2 is True
    assert count2 == 1
    following3, count3 = store.follow_host(room_id, "viewer-1", unfollow=True)
    assert following3 is False
    assert count3 == 0
