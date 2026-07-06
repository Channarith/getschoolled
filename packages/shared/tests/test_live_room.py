"""Tests for Salareen live rooms (aoep_shared.live_room)."""

from __future__ import annotations

import pytest

from aoep_shared.live_room import (
    AI_HOST_ID,
    BannedError,
    LiveRoomError,
    LiveRoomStore,
    RoomFullError,
    learner_capacity,
)


def test_open_room_has_theodore_host_and_welcome():
    store = LiveRoomStore()
    room = store.open_room(
        room_id="class-abc",
        class_id="abc",
        session_id="sess1",
        lesson_id="intro-to-fractions",
        title="Fractions live",
        room_size=6,
        slide_title="What is a fraction?",
    )
    assert room.room_size == 6
    assert room.seats_left == 5
    assert room.host().id == AI_HOST_ID
    assert "Theodore" in room.host().name
    assert room.chat


def test_join_respects_room_capacity():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-tiny",
        class_id="tiny",
        session_id="s1",
        lesson_id="lesson",
        title="Tiny",
        room_size=4,
    )
    assert learner_capacity(4) == 3
    store.join("class-tiny", "Ada", identity="ada-1")
    store.join("class-tiny", "Grace")
    store.join("class-tiny", "Linus")
    with pytest.raises(RoomFullError):
        store.join("class-tiny", "Alan")
    again = store.join("class-tiny", "Ada again", identity="ada-1")
    assert again.name == "Ada"


def test_raise_hand_mute_and_chat():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-1",
        class_id="1",
        session_id="s1",
        lesson_id="lesson",
        title="Class",
        room_size=6,
    )
    learner = store.join("class-1", "Student")
    store.toggle_hand("class-1", learner.id)
    assert store.require("class-1").get_participant(learner.id).hand_raised is True
    store.set_mute("class-1", learner.id, muted=True, by_host=True, actor_id=AI_HOST_ID)
    with pytest.raises(LiveRoomError):
        store.post_chat("class-1", learner.id, "hello while muted")
    store.set_mute("class-1", learner.id, muted=False)
    msg = store.post_chat("class-1", learner.id, "Now I can speak")
    assert msg.text == "Now I can speak"


def test_recording_lifecycle():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-rec",
        class_id="rec",
        session_id="s1",
        lesson_id="lesson",
        title="Recorded",
        room_size=9,
    )
    rec = store.start_recording("class-rec")
    assert rec.status == "recording"
    stopped = store.stop_recording("class-rec")
    assert stopped.status == "stopped"
    assert stopped.recording_id


def test_end_room_dismisses():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-end",
        class_id="end",
        session_id="s1",
        lesson_id="lesson",
        title="End",
        room_size=6,
    )
    ended = store.end_room("class-end")
    assert ended.status == "ended"
    assert any("dismissed" in m.text.lower() for m in ended.chat)


def test_ban_blocks_rejoin_and_unban_restores():
    store = LiveRoomStore()
    room = store.open_room(
        room_id="class-ban",
        class_id="ban",
        session_id="s1",
        lesson_id="lesson",
        title="Ban test",
        room_size=6,
    )
    mod = room.moderator_key
    trouble = store.join("class-ban", "Trouble", identity="trouble-1")
    store.ban_participant("class-ban", trouble.id, moderator_key=mod, reason="Spam")
    assert room.is_banned("trouble-1")
    with pytest.raises(BannedError):
        store.join("class-ban", "Trouble again", identity="trouble-1")
    store.unban("class-ban", "trouble-1", moderator_key=mod)
    again = store.join("class-ban", "Trouble again", identity="trouble-1")
    assert again.name == "Trouble again"


def test_ban_requires_moderator_key():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-mod",
        class_id="mod",
        session_id="s1",
        lesson_id="lesson",
        title="Mod",
        room_size=6,
    )
    p = store.join("class-mod", "Ada")
    with pytest.raises(LiveRoomError):
        store.ban_participant("class-mod", p.id, moderator_key="wrong-key")
