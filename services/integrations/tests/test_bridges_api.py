"""Phases 7-9 - live-class media bridge endpoints on the integrations service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from integrations.main import app

client = TestClient(app)


def test_list_bridges_reports_capabilities_and_readiness():
    body = client.get("/bridges").json()
    platforms = {b["platform"]: b for b in body["bridges"]}
    assert set(platforms) == {"zoom", "teams", "meet"}
    assert platforms["teams"]["runtime"] == "dotnet"
    assert platforms["zoom"]["runtime"] == "python"
    # No credentials configured in tests -> not ready, with the missing list.
    assert platforms["zoom"]["ready"] is False
    assert "ZOOM_SDK_KEY" in platforms["zoom"]["missing_credentials"]


def test_bridge_info_unknown_platform_404():
    assert client.get("/bridges/webex").status_code == 404


def test_connect_without_sdk_fails_closed_503():
    r = client.post("/bridges/zoom/connect", json={
        "meeting_ref": "https://zoom.us/j/87654321012",
    })
    assert r.status_code == 503
    assert "credential" in r.json()["detail"].lower() or "sdk" in r.json()["detail"].lower()


def test_connect_bad_meeting_ref_400():
    r = client.post("/bridges/meet/connect", json={
        "meeting_ref": "https://example.com/nope", "simulate": True,
    })
    assert r.status_code == 400


def test_simulated_connect_bridges_tracks_and_supports_chat_and_disconnect():
    # Simulate runs the full lifecycle through the in-memory transport.
    r = client.post("/bridges/zoom/connect", json={
        "meeting_ref": "https://us05web.zoom.us/j/87654321012?pwd=secret",
        "livekit_room": "class-demo", "recording": True, "retention_days": 14,
        "simulate": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["simulated"] is True
    assert body["state"] == "bridging"
    assert body["meeting_id"] == "87654321012"
    assert body["room"] == "class-demo"
    directions = {(t["kind"], t["direction"]) for t in body["bridged_tracks"]}
    assert ("audio", "meeting_to_room") in directions
    assert ("audio", "room_to_meeting") in directions
    assert body["disclosure"] and "14 days" in body["disclosure"]
    sid = body["session_id"]

    # Status round-trips.
    assert client.get(f"/bridges/sessions/{sid}").json()["state"] == "bridging"

    # Meeting chat -> Tutor; answer posts back.
    chat = client.post(f"/bridges/sessions/{sid}/chat", json={
        "text": "What is inertia?", "reply": "A body resists changes in motion.",
    }).json()
    assert chat["chat_log"] == ["What is inertia?"]

    # Disconnect tears down and forgets the session.
    closed = client.post(f"/bridges/sessions/{sid}/disconnect").json()
    assert closed["state"] == "closed"
    assert client.get(f"/bridges/sessions/{sid}").status_code == 404
