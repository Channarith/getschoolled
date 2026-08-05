"""API tests for the lab FastAPI app (TestClient; no camera needed)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from webcam_recognition.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["agent_persona"] == "Theodore"
    assert "silhouette_detector" in body


def test_index_serves_demo_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "Webcam Recognition Lab" in r.text


def test_agent_respond_stateless():
    r = client.post("/agent/respond", json={"event": "arrived", "learner_name": "Ada"})
    assert r.status_code == 200
    body = r.json()
    assert body["persona"] == "Theodore"
    assert "Ada" in body["text"]


def test_solo_session_lifecycle():
    sid = "test-solo"
    r = client.post("/sessions", json={
        "session_id": sid, "mode": "solo", "teaching_mode": "theodore", "topic": "math",
    })
    assert r.status_code == 200
    assert r.json()["mode"] == "solo"

    # First present frame -> ARRIVED -> a GREET action with words.
    r = client.post(f"/sessions/{sid}/frame", json={
        "person_present": True, "face_count": 1, "attention": 0.9,
    })
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert any(a["kind"] == "greet" for a in actions)

    st = client.get(f"/sessions/{sid}").json()
    assert st["present"] is True


def test_duplicate_session_conflict():
    sid = "dup-session"
    assert client.post("/sessions", json={"session_id": sid}).status_code == 200
    assert client.post("/sessions", json={"session_id": sid}).status_code == 409


def test_group_session_frame_present_ids():
    sid = "test-group"
    client.post("/sessions", json={
        "session_id": sid, "mode": "group", "teaching_mode": "theodore",
    })
    r = client.post(f"/sessions/{sid}/frame", json={"present_ids": ["alice", "bob"]})
    assert r.status_code == 200
    st = client.get(f"/sessions/{sid}").json()
    assert st["headcount"] == 2


def test_session_say():
    sid = "say-session"
    client.post("/sessions", json={"session_id": sid, "mode": "solo"})
    r = client.post(f"/sessions/{sid}/say", json={"message": "explain fractions"})
    assert r.status_code == 200
    assert r.json()["kind"] == "answer"
    assert r.json()["reply"]["text"]


def test_unknown_session_404():
    assert client.get("/sessions/nope").status_code == 404
    assert client.post("/sessions/nope/frame", json={}).status_code == 404


def test_analyze_empty_frame_422():
    r = client.post("/analyze", files={"file": ("f.jpg", b"", "image/jpeg")})
    assert r.status_code == 422


def test_analyze_frame_returns_perception():
    # A tiny invalid JPEG still returns a perception dict (silhouette detector
    # degrades gracefully; face pipeline may be unavailable). We assert shape.
    r = client.post(
        "/analyze", files={"file": ("f.jpg", b"\xff\xd8\xff\xd9notreal", "image/jpeg")}
    )
    assert r.status_code == 200
    body = r.json()
    assert "person_present" in body
    assert "people_count" in body
    assert "face_count" in body


@pytest.mark.parametrize("mode", ["solo", "group"])
def test_create_session_modes(mode):
    sid = f"modes-{mode}"
    r = client.post("/sessions", json={"session_id": sid, "mode": mode})
    assert r.status_code == 200
    assert r.json()["mode"] == mode
