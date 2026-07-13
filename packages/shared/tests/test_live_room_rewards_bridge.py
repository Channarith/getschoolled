"""Tests for live-room gift ↔ identity rewards bridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from aoep_shared.live_room import LiveRoomStore
from aoep_shared.live_room_social import LiveRoomGiftLedger


def _open_room(store: LiveRoomStore) -> str:
    room = store.open_room(
        room_id="rewards-bridge",
        class_id="c1",
        session_id="s1",
        lesson_id="l1",
        title="Rewards bridge",
        room_size=6,
    )
    return room.room_id


def test_gift_balance_prefers_identity_when_linked():
    ledger = LiveRoomGiftLedger(default_balance=999)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Ada", identity="ada-1", account_id="acct-1")
    with patch(
        "aoep_shared.live_room_rewards.rewards_balance_from_auth",
        return_value=42,
    ):
        assert store.gift_balance_for(sender, "Bearer tok") == 42
    assert store.gift_balance_for(sender, "") == 999


def test_send_gift_spends_identity_ledger():
    ledger = LiveRoomGiftLedger(default_balance=1000)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Ada", identity="ada-1", account_id="acct-1")
    with patch(
        "aoep_shared.live_room_rewards.spend_rewards_via_auth",
        return_value=90,
    ) as spend:
        gift, balance = store.send_gift(
            room_id,
            sender.id,
            gift_id="rose",
            authorization="Bearer tok",
        )
    spend.assert_called_once()
    assert gift.cost_points == 10
    assert balance == 90
    assert ledger.balance("ada-1") == 1000


def test_send_gift_identity_insufficient_raises():
    from aoep_shared.live_room import LiveRoomError
    from aoep_shared.live_room_rewards import LiveRoomRewardsError

    ledger = LiveRoomGiftLedger(default_balance=1000)
    store = LiveRoomStore(gift_ledger=ledger)
    room_id = _open_room(store)
    sender = store.join(room_id, "Broke", identity="broke-1", account_id="acct-2")
    with patch(
        "aoep_shared.live_room_rewards.spend_rewards_via_auth",
        side_effect=LiveRoomRewardsError("insufficient points"),
    ):
        with pytest.raises(LiveRoomError, match="insufficient"):
            store.send_gift(
                room_id,
                sender.id,
                gift_id="rose",
                authorization="Bearer tok",
            )
