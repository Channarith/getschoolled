"""Live room HTTP endpoints (/api/live-rooms)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from aoep_shared.group_classes import GroupClassStore, ensure_standard_daily_classes
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


def _schedule_salareen_class(room_size: int = 6) -> str:
    """Schedule a Salareen class WITHOUT starting it (no live room yet)."""
    return client.post(
        "/api/group-classes",
        json={
            "title": "Unstarted Salareen",
            "lesson_id": _first_lesson(),
            "start_time": _iso(5),
            "platform": "salareen",
            "room_size": room_size,
            "capacity": room_size - 1,
        },
    ).json()["id"]


def test_get_room_lazy_opens_for_unstarted_class():
    # Selecting a scheduled-but-not-started Salareen class used to 404.
    cid = _schedule_salareen_class(6)
    room = client.get(f"/api/live-rooms/class-{cid}")
    assert room.status_code == 200, room.text
    body = room.json()
    assert body["room_size"] == 6
    assert body["slide"]["title"]  # session was started on demand


def test_get_room_lazy_opens_when_group_store_is_cold():
    # A class id listed by another replica should still open/join on this worker.
    probe = GroupClassStore()
    ensure_standard_daily_classes(probe)
    salareen = [gc for gc in probe.list(upcoming_only=True) if gc.platform == "salareen"]
    assert salareen, "expected seeded salareen classes"
    class_id = salareen[0].id
    prev_store = app.state.group_classes
    app.state.group_classes = GroupClassStore()
    try:
        joined = client.post(
            f"/api/live-rooms/class-{class_id}/join",
            json={"name": "Replica learner", "identity": "replica-1"},
        )
        assert joined.status_code == 200, joined.text
        assert joined.json()["media"]["token"].count(".") == 2
        room = client.get(f"/api/live-rooms/class-{class_id}")
        assert room.status_code == 200, room.text
    finally:
        app.state.group_classes = prev_store


def test_join_lazy_opens_and_issues_livekit_token():
    cid = _schedule_salareen_class(4)
    joined = client.post(
        f"/api/live-rooms/class-{cid}/join",
        json={"name": "Ada", "identity": "ada-web"},
    )
    assert joined.status_code == 200, joined.text
    body = joined.json()
    # Real videochat: a LiveKit join token + url are issued for the participant.
    assert body["media"]["token"].count(".") == 2  # JWT header.payload.signature
    assert body["media"]["room"] == f"class-{cid}"
    assert body["media"]["url"]


def test_unknown_room_still_404s():
    r = client.get("/api/live-rooms/class-does-not-exist")
    assert r.status_code == 404
    r2 = client.get("/api/live-rooms/random-room-xyz")
    assert r2.status_code == 404


def test_join_chat_and_queue_flow():
    info = _start_salareen_class(4)
    joined = client.post(
        f"/api/live-rooms/{info['room_id']}/join",
        json={"name": "Ada", "identity": "ada-web"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    assert joined.json()["media"]["token"]

    hand = client.post(
        f"/api/live-rooms/{info['room_id']}/queue/join",
        json={"participant_id": pid, "question": "Can you explain?"},
    )
    assert hand.status_code == 200, hand.text
    assert hand.json()["entry"]["position"] == 1

    mod = info["started"]["bridge"]["moderator_key"]
    called = client.post(
        f"/api/live-rooms/{info['room_id']}/queue/call-next",
        json={"moderator_key": mod},
    )
    assert called.status_code == 200, called.text
    assert called.json()["speaker"]["id"] == pid


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


def test_ask_queues_when_someone_else_speaking():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    a = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "a1"},
    ).json()["participant"]["id"]
    b = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Grace", "identity": "b1"},
    ).json()["participant"]["id"]
    client.post(f"/api/live-rooms/{room_id}/queue/join", json={"participant_id": a, "question": "Q1"})
    client.post(f"/api/live-rooms/{room_id}/queue/call-next", json={"moderator_key": mod})
    queued = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": b, "question": "My turn?"},
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["queued"] is True
    assert queued.json()["queue_position"] == 1


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
    assert asked.json()["queued"] is False
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


def test_report_and_moderator_review():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    reporter = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "reporter-1"},
    ).json()["participant"]
    target = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Bob", "identity": "target-1"},
    ).json()["participant"]
    reported = client.post(
        f"/api/live-rooms/{room_id}/report",
        json={
            "reporter_participant_id": reporter["id"],
            "reported_participant_id": target["id"],
            "reason": "Harassing messages",
            "category": "harassment",
        },
    )
    assert reported.status_code == 200, reported.text

    mod_view = client.get(
        f"/api/live-rooms/{room_id}",
        params={"moderator_key": mod},
    )
    assert mod_view.status_code == 200, mod_view.text
    reports = mod_view.json().get("reports") or []
    assert len(reports) == 1
    assert reports[0]["reported_name"] == "Bob"

    dismissed = client.post(
        f"/api/live-rooms/{room_id}/reports/dismiss",
        json={"report_id": reports[0]["id"], "moderator_key": mod},
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["room"].get("reports") == []


def test_gift_catalog_and_send():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Gifter", "identity": "gift-1"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    assert joined.json()["gift_balance"] >= 10

    catalog = client.get("/api/live-rooms/gifts/catalog")
    assert catalog.status_code == 200
    gifts = catalog.json()["gifts"]
    assert any(g["id"] == "rose" for g in gifts)

    sent = client.post(
        f"/api/live-rooms/{room_id}/gifts/send",
        json={"participant_id": pid, "gift_id": "rose"},
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["gift"]["emoji"] == "🌹"
    assert body["sender_balance"] == joined.json()["gift_balance"] - 10
    assert any("🌹" in m["text"] for m in body["room"]["chat"])


def test_reaction_endpoint():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Fan", "identity": "fan-1"},
    ).json()["participant"]["id"]
    reacted = client.post(
        f"/api/live-rooms/{room_id}/reactions",
        json={"participant_id": pid, "emoji": "❤️"},
    )
    assert reacted.status_code == 200, reacted.text
    assert reacted.json()["reaction"]["emoji"] == "❤️"


def test_follow_host_endpoint():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    follow = client.post(
        f"/api/live-rooms/{room_id}/follow",
        json={"identity": "follower-1"},
    )
    assert follow.status_code == 200, follow.text
    assert follow.json()["following"] is True
    assert follow.json()["follower_count"] == 1
    status = client.get(
        f"/api/live-rooms/{room_id}/follow",
        params={"identity": "follower-1"},
    )
    assert status.status_code == 200
    assert status.json()["following"] is True


def test_live_room_websocket_snapshot():
    info = _start_salareen_class(4)
    room_id = info["room_id"]
    with client.websocket_connect(f"/api/live-rooms/{room_id}/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "room"
        assert msg["payload"]["room"]["room_id"] == room_id


def test_list_live_rooms_after_start():
    info = _start_salareen_class(6)
    listed = client.get("/api/live-rooms")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    ids = {r["room_id"] for r in body["rooms"]}
    assert info["room_id"] in ids
    assert body.get("groups")


def test_create_user_live_room_with_geo():
    created = client.post(
        "/api/live-rooms",
        json={
            "title": "Study hall SF",
            "creator_name": "Ada",
            "room_size": 6,
            "location": {
                "country": "United States",
                "state": "California",
                "city": "San Francisco",
                "latitude": 37.77,
                "longitude": -122.42,
            },
        },
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["listing"]["room_id"]
    assert created.json()["listing"]["city"] == "San Francisco"

    nearby = client.get("/api/live-rooms", params={"lat": 37.78, "lng": -122.41, "radius_km": 50})
    assert nearby.status_code == 200
    ids = {r["room_id"] for r in nearby.json()["rooms"]}
    assert room_id in ids

    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Bob", "identity": "bob-1"},
    )
    assert joined.status_code == 200, joined.text
