"""Regression tests for Salareen Live Room chat + Q&A turn-taking.

Exercises the full multi-user teaching-room loop that ships with group classes:
schedule -> start -> join -> speaking queue -> call next -> ask/chat -> finish
turn -> ban/block. Complements unit tests in packages/shared and orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _lesson_id() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _open_salareen_room(*, room_size: int = 6) -> dict:
    """Schedule, start, and return handles for a live Salareen room."""
    lid = _lesson_id()
    cid = client.post(
        "/api/group-classes",
        json={
            "title": "QA regression live room",
            "lesson_id": lid,
            "platform": "salareen",
            "room_size": room_size,
            "capacity": room_size - 1,
            "start_time": _iso(10),
        },
    ).json()["id"]
    started = client.post(f"/api/group-classes/{cid}/start").json()
    bridge = started["bridge"]
    return {
        "class_id": cid,
        "room_id": bridge["livekit_room"],
        "moderator_key": bridge["moderator_key"],
        "started": started,
    }


def _join(room_id: str, name: str, identity: str) -> dict:
    res = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": name, "identity": identity},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_live_room_qa_queue_turn_taking_regression():
    """Golden path: two learners queue, take turns, Theodore answers, floor releases."""
    info = _open_salareen_room(room_size=6)
    room_id = info["room_id"]
    mod = info["moderator_key"]

    a = _join(room_id, "Ada", "regression-ada")
    b = _join(room_id, "Grace", "regression-grace")
    aid, bid = a["participant"]["id"], b["participant"]["id"]

    q1 = client.post(
        f"/api/live-rooms/{room_id}/queue/join",
        json={"participant_id": aid, "question": "What is photosynthesis?"},
    )
    assert q1.status_code == 200, q1.text
    assert q1.json()["entry"]["position"] == 1

    q2 = client.post(
        f"/api/live-rooms/{room_id}/queue/join",
        json={"participant_id": bid, "question": "Why do plants need sun?"},
    )
    assert q2.status_code == 200, q2.text
    assert q2.json()["entry"]["position"] == 2

    state = client.get(f"/api/live-rooms/{room_id}").json()
    assert len(state["speaking_queue"]) == 2
    assert state["floor_participant_id"] == ""

    called = client.post(
        f"/api/live-rooms/{room_id}/queue/call-next",
        json={"moderator_key": mod},
    )
    assert called.status_code == 200, called.text
    assert called.json()["speaker"]["id"] == aid

    # Second person cannot chat while Ada has the floor.
    blocked_chat = client.post(
        f"/api/live-rooms/{room_id}/chat",
        json={"participant_id": bid, "text": "interrupting!"},
    )
    assert blocked_chat.status_code == 400

    asked = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": aid, "question": "What is photosynthesis?"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["queued"] is False
    assert asked.json()["answer"]["text"]
    # Ask answers via Theodore and auto-releases the floor.
    assert asked.json()["room"]["floor_participant_id"] == ""

    # Ask while still waiting in queue (Grace) -> enqueued, not answered immediately.
    queued = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": bid, "question": "Can I go next?"},
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["queued"] is True
    assert queued.json()["queue_position"] >= 1

    called2 = client.post(
        f"/api/live-rooms/{room_id}/queue/call-next",
        json={"moderator_key": mod},
    )
    assert called2.status_code == 200, called2.text
    assert called2.json()["speaker"]["id"] == bid


def test_live_room_raise_hand_toggles_queue():
    info = _open_salareen_room()
    room_id = info["room_id"]
    pid = _join(room_id, "Learner", "regression-toggle")["participant"]["id"]

    on = client.post(
        f"/api/live-rooms/{room_id}/raise-hand",
        json={"participant_id": pid, "question": "Quick question"},
    )
    assert on.status_code == 200, on.text
    assert on.json()["queue_position"] == 1

    off = client.post(
        f"/api/live-rooms/{room_id}/raise-hand",
        json={"participant_id": pid},
    )
    assert off.status_code == 200, off.text
    room = client.get(f"/api/live-rooms/{room_id}").json()
    assert room["speaking_queue"] == []


def test_live_room_ban_removes_queued_learner():
    info = _open_salareen_room()
    room_id = info["room_id"]
    mod = info["moderator_key"]
    joined = _join(room_id, "Trouble", "regression-ban")
    pid = joined["participant"]["id"]

    client.post(
        f"/api/live-rooms/{room_id}/queue/join",
        json={"participant_id": pid, "question": "spam"},
    )
    banned = client.post(
        f"/api/live-rooms/{room_id}/ban",
        json={"participant_id": pid, "moderator_key": mod, "reason": "disruptive"},
    )
    assert banned.status_code == 200, banned.text

    room = client.get(f"/api/live-rooms/{room_id}").json()
    assert all(e["participant_id"] != pid for e in room["speaking_queue"])

    blocked = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Trouble", "identity": "regression-ban"},
    )
    assert blocked.status_code == 403
