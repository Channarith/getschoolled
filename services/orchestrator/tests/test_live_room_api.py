"""Live room HTTP endpoints (/api/live-rooms)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _first_lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _start_salareen_class(room_size: int = 6) -> dict:
    lid = _first_lesson()
    cid = client.post(
        "/api/group-classes",
        json={
            "title": "Salareen live",
            "lesson_id": lid,
            "start_time": _iso(5),
            "platform": "salareen",
            "room_size": room_size,
            "capacity": room_size - 1,
        },
    ).json()["id"]
    started = client.post(f"/api/group-classes/{cid}/start").json()
    room_id = started["bridge"]["livekit_room"]
    return {"class_id": cid, "room_id": room_id, "started": started}


def test_start_salareen_opens_live_room():
    info = _start_salareen_class(6)
    room = client.get(f"/api/live-rooms/{info['room_id']}")
    assert room.status_code == 200, room.text
    body = room.json()
    assert body["room_size"] == 6
    assert body["host"]["name"].startswith("Theodore")
    assert body["slide"]["title"]


def test_join_chat_raise_hand_flow():
    info = _start_salareen_class(4)
    joined = client.post(
        f"/api/live-rooms/{info['room_id']}/join",
        json={"name": "Ada", "identity": "ada-web"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    assert joined.json()["media"]["token"]

    chat = client.post(
        f"/api/live-rooms/{info['room_id']}/chat",
        json={"participant_id": pid, "text": "Hello Theodore!"},
    )
    assert chat.status_code == 200, chat.text

    hand = client.post(
        f"/api/live-rooms/{info['room_id']}/raise-hand",
        json={"participant_id": pid},
    )
    assert hand.status_code == 200, hand.text
    assert hand.json()["participant"]["hand_raised"] is True


def test_join_full_room_returns_409():
    info = _start_salareen_class(4)
    room_id = info["room_id"]
    for i in range(3):
        res = client.post(
            f"/api/live-rooms/{room_id}/join",
            json={"name": f"Learner {i}", "identity": f"id-{i}"},
        )
        assert res.status_code == 200, res.text
    full = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "One too many", "identity": "overflow"},
    )
    assert full.status_code == 409


def test_advance_and_ask_in_room():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Student", "identity": "student-1"},
    ).json()["participant"]["id"]

    advanced = client.post(f"/api/live-rooms/{room_id}/advance")
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["slide"]["title"]

    asked = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": pid, "question": "What is this lesson about?"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["answer"]["text"]
    assert asked.json()["host_message"]["from_name"].startswith("Theodore")


def test_recording_endpoints():
    info = _start_salareen_class()
    room_id = info["room_id"]
    start = client.post(f"/api/live-rooms/{room_id}/record/start")
    assert start.status_code == 200, start.text
    assert start.json()["recording"]["status"] == "recording"
    stop = client.post(f"/api/live-rooms/{room_id}/record/stop")
    assert stop.status_code == 200, stop.text
    assert stop.json()["recording"]["status"] == "stopped"


def test_ban_and_unban_flow():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    assert mod

    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]

    banned = client.post(
        f"/api/live-rooms/{room_id}/ban",
        json={"participant_id": pid, "moderator_key": mod, "reason": "Spam"},
    )
    assert banned.status_code == 200, banned.text
    assert banned.json()["banned"]["identity"] == "spam-1"

    blocked = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert blocked.status_code == 403

    unbanned = client.post(
        f"/api/live-rooms/{room_id}/unban",
        json={"identity": "spam-1", "moderator_key": mod},
    )
    assert unbanned.status_code == 200, unbanned.text

    rejoin = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert rejoin.status_code == 200, rejoin.text
