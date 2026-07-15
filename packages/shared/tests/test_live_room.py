"""Tests for Salareen live rooms (aoep_shared.live_room)."""

from __future__ import annotations

import pytest

from aoep_shared.live_room import (
    AI_HOST_ID,
    ASK_RATE_MAX,
    BannedError,
    CHAT_MAX_CHARS,
    CHAT_RATE_MAX,
    LiveRoomError,
    LiveRoomStore,
    RateLimitedError,
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
    store.join_queue("class-1", learner.id, question="Why?")
    assert store.require("class-1").get_participant(learner.id).hand_raised is True
    assert store.require("class-1").queue_position(learner.id) == 1
    store.set_mute("class-1", learner.id, muted=True, by_host=True, actor_id=AI_HOST_ID)
    with pytest.raises(LiveRoomError):
        store.post_chat("class-1", learner.id, "hello while muted")
    store.set_mute("class-1", learner.id, muted=False)
    msg = store.post_chat("class-1", learner.id, "Now I can speak")
    assert msg.text == "Now I can speak"


def _spam_store() -> tuple[LiveRoomStore, str]:
    store = LiveRoomStore()
    store.open_room(
        room_id="class-spam",
        class_id="s",
        session_id="s1",
        lesson_id="lesson",
        title="Spam",
        room_size=6,
    )
    learner = store.join("class-spam", "Spammer")
    return store, learner.id


def test_chat_rate_limit_blocks_flood():
    store, pid = _spam_store()
    for i in range(CHAT_RATE_MAX):
        store.post_chat("class-spam", pid, f"msg {i}")
    with pytest.raises(RateLimitedError):
        store.post_chat("class-spam", pid, "one too many")


def test_chat_rejects_overlong_message():
    store, pid = _spam_store()
    with pytest.raises(LiveRoomError):
        store.post_chat("class-spam", pid, "x" * (CHAT_MAX_CHARS + 1))


def test_ask_rate_limit_blocks_flood():
    store, pid = _spam_store()
    for i in range(ASK_RATE_MAX):
        store.ask_when_ready("class-spam", pid, f"question {i}?")
    with pytest.raises(RateLimitedError):
        store.ask_when_ready("class-spam", pid, "spammy question?")


def test_rate_limit_is_per_participant():
    store, pid = _spam_store()
    other = store.join("class-spam", "Calm")
    for i in range(CHAT_RATE_MAX):
        store.post_chat("class-spam", pid, f"msg {i}")
    # A different participant is unaffected by the spammer's window.
    msg = store.post_chat("class-spam", other.id, "hi there")
    assert msg.text == "hi there"


def test_leaving_clears_rate_window():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-lc",
        class_id="lc",
        session_id="s1",
        lesson_id="lesson",
        title="LC",
        room_size=6,
    )
    p = store.join("class-lc", "Spammer", identity="spammer-1")
    for i in range(CHAT_RATE_MAX):
        store.post_chat("class-lc", p.id, f"msg {i}")
    with pytest.raises(RateLimitedError):
        store.post_chat("class-lc", p.id, "blocked")
    store.leave("class-lc", p.id)
    rejoined = store.join("class-lc", "Spammer", identity="spammer-1")
    # Fresh window after rejoining (leave cleared the bookkeeping).
    assert store.post_chat("class-lc", rejoined.id, "back").text == "back"


def test_reserved_and_overlong_display_names_rejected():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-names", class_id="n", session_id="s1",
        lesson_id="lesson", title="Names", room_size=6,
    )
    for bad in ("Theodore", "administrator", "AI Host", "Salareen AI", "System"):
        with pytest.raises(LiveRoomError):
            store.join("class-names", bad)
    with pytest.raises(LiveRoomError):
        store.join("class-names", "x" * 41)
    # A normal name still works.
    assert store.join("class-names", "Theodora B.").name == "Theodora B."


def test_self_gift_is_blocked():
    store = LiveRoomStore()
    store.open_room(
        room_id="class-gift", class_id="g", session_id="s1",
        lesson_id="lesson", title="Gift", room_size=6,
    )
    p = store.join("class-gift", "Giver")
    with pytest.raises(LiveRoomError):
        store.send_gift("class-gift", p.id, gift_id="rose", recipient_participant_id=p.id)


def test_reaction_rate_limit():
    store, pid = _spam_store()
    from aoep_shared.live_room import REACT_RATE_MAX

    for _ in range(REACT_RATE_MAX):
        store.send_reaction("class-spam", pid, emoji="👍")
    with pytest.raises(RateLimitedError):
        store.send_reaction("class-spam", pid, emoji="👍")


def test_report_rate_limit():
    store, reporter = _spam_store()
    target = store.join("class-spam", "Target").id
    from aoep_shared.live_room import REPORT_RATE_MAX

    # Rate is checked before dedup, so repeated reports of the same target count.
    for _ in range(REPORT_RATE_MAX):
        store.report_participant("class-spam", reporter, target, reason="bad", category="spam")
    with pytest.raises(RateLimitedError):
        store.report_participant("class-spam", reporter, target, reason="bad", category="spam")


def test_queue_join_rate_limit():
    store, pid = _spam_store()
    from aoep_shared.live_room import QUEUE_RATE_MAX

    # Toggle join/leave to make each a NEW join (idempotent re-join wouldn't count).
    for _ in range(QUEUE_RATE_MAX):
        store.join_queue("class-spam", pid, question="?")
        store.leave_queue("class-spam", pid)
    with pytest.raises(RateLimitedError):
        store.join_queue("class-spam", pid, question="?")


def test_speaking_queue_turn_taking():
    store = LiveRoomStore()
    room = store.open_room(
        room_id="class-q",
        class_id="q",
        session_id="s1",
        lesson_id="lesson",
        title="Queue",
        room_size=6,
    )
    mod = room.moderator_key
    a = store.join("class-q", "Ada")
    b = store.join("class-q", "Grace")
    store.join_queue("class-q", a.id, question="First?")
    store.join_queue("class-q", b.id, question="Second?")
    assert store.require("class-q").queue_position(b.id) == 2
    speaker = store.call_next("class-q", moderator_key=mod)
    assert speaker.id == a.id
    assert store.require("class-q").floor_participant_id == a.id
    with pytest.raises(LiveRoomError):
        store.call_next("class-q", moderator_key=mod)
    store.finish_turn("class-q", a.id)
    assert store.require("class-q").floor_participant_id == ""
    speaker2 = store.call_next("class-q", moderator_key=mod)
    assert speaker2.id == b.id
    mode, entry = store.ask_when_ready("class-q", b.id, "What is a fraction?")
    assert mode == "answered"
    store.finish_turn("class-q", b.id)


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


def test_report_participant_and_moderator_dismiss():
    store = LiveRoomStore()
    room = store.open_room(
        room_id="class-report",
        class_id="rep",
        session_id="s1",
        lesson_id="lesson",
        title="Reports",
        room_size=6,
    )
    mod = room.moderator_key
    a = store.join("class-report", "Ada", identity="ada-r")
    b = store.join("class-report", "Bob", identity="bob-r")
    report = store.report_participant(
        "class-report",
        a.id,
        b.id,
        reason="Spam in chat",
        category="spam",
    )
    assert report.reported_name == "Bob"
    loaded = store.require("class-report")
    assert len(loaded.open_reports()) == 1
    with pytest.raises(LiveRoomError):
        store.report_participant("class-report", a.id, a.id, reason="nope", category="other")
    store.dismiss_report("class-report", report.id, moderator_key=mod)
    assert store.require("class-report").open_reports() == []
