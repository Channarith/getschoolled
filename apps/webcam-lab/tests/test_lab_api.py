"""API tests for the private webcam lab."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from webcam_lab.main import STORE, app
from webcam_lab.session import LabSessionStore


@pytest.fixture()
def client(monkeypatch):
    # Fresh store per test.
    fresh = LabSessionStore()
    monkeypatch.setattr("webcam_lab.main.STORE", fresh)
    # Also patch module-level reference used by handlers via closure — handlers
    # import STORE from main at call time through the module global.
    import webcam_lab.main as main_mod

    monkeypatch.setattr(main_mod, "STORE", fresh)
    with TestClient(main_mod.app) as c:
        yield c, fresh


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "webcam-lab"
    assert body["private"] is True
    assert "silhouette_detection" in body["capabilities"]
    assert "self_teach" in body["modes"]


def test_solo_session_presence_and_absence_hold(client):
    c, store = client
    r = c.post(
        "/sessions",
        json={"mode": "solo", "host_name": "Ada", "lesson_context": "Fractions"},
    )
    assert r.status_code == 200
    session = r.json()
    assert session["mode"] == "solo"
    assert session["voice"]["persona"] == "theodore"
    pid = session["participants"][0]["participant_id"]
    sid = session["session_id"]

    # Present with face.
    r = c.post(
        f"/sessions/{sid}/participants/{pid}/presence",
        json={"face_count": 1, "attention": 0.8, "silhouette_present": True},
    )
    assert r.status_code == 200
    assert r.json()["decision"]["state"] == "live"
    assert r.json()["session_hold"] is False

    # Leave frame — need grace to elapse. Drive tracker with explicit timestamps.
    t0 = datetime.now(timezone.utc)
    store.report_presence(
        sid, pid, face_count=0, silhouette_present=False, now=t0
    )
    d = store.report_presence(
        sid,
        pid,
        face_count=0,
        silhouette_present=False,
        now=t0 + timedelta(seconds=10),
    )
    assert d.state == "absent"
    assert d.hold is True


def test_silhouette_only_reengage(client):
    c, _ = client
    r = c.post("/sessions", json={"mode": "self_teach", "host_name": "Bea"})
    session = r.json()
    assert session["voice"]["persona"] == "self_teach"
    pid = session["participants"][0]["participant_id"]
    sid = session["session_id"]
    r = c.post(
        f"/sessions/{sid}/participants/{pid}/presence",
        json={"face_count": 0, "silhouette_present": True, "silhouette_confidence": 0.7},
    )
    body = r.json()["decision"]
    assert body["state"] == "silhouette_only"
    assert body["present"] is True
    assert body["should_reengage"] is True


def test_group_add_participant(client):
    c, _ = client
    r = c.post("/sessions", json={"mode": "group", "host_name": "Host"})
    sid = r.json()["session_id"]
    r = c.post(f"/sessions/{sid}/participants", json={"display_name": "Chris"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Chris"


def test_voice_token_mock(client):
    c, _ = client
    r = c.post(
        "/voice/token",
        json={"mode": "theodore_group", "lesson_context": "Algebra warm-up"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"]["mock"] is True
    assert "websocket_url" in body["token"]
    assert body["session_update"]["type"] == "session.update"
    assert "Theodore" in body["session_update"]["session"]["instructions"]


def test_analyze_report(client):
    c, _ = client
    r = c.post(
        "/analyze/report",
        json={
            "face_count": 1,
            "attention": 0.6,
            "silhouette_present": True,
            "expression": "smiling",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["face_count"] == 1
    assert body["silhouette"]["present"] is True
    assert body["engine"] == "hybrid_report"


def test_demo_page(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "Webcam Lab" in r.text
