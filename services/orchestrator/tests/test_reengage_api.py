"""Tests for the re-engagement endpoint (renders the Director's REENGAGING state)."""

from fastapi.testclient import TestClient

from orchestrator.curriculum import Lesson
from orchestrator.main import app, get_sessions

client = TestClient(app)


def test_reengage_returns_slide_grounded_content():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session"]["session_id"]

    r = client.post(f"/api/sessions/{sid}/reengage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"]
    assert body["prompt"]
    assert len(body["citations"]) >= 1


def test_reengage_unknown_session_404():
    r = client.post("/api/sessions/does-not-exist/reengage")
    assert r.status_code == 404


def test_reengage_empty_slides_lesson_degrades_gracefully(monkeypatch):
    # A malformed lesson with zero slides must not 500 (IndexError) — it falls
    # back to a generic refocus beat.
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    sid = start.json()["session"]["session_id"]
    sessions = get_sessions()
    monkeypatch.setattr(
        sessions, "lesson_for",
        lambda _sid: Lesson(lesson_id="x", title="X", slides=[]),
    )
    r = client.post(f"/api/sessions/{sid}/reengage")
    assert r.status_code == 200, r.text
    assert r.json()["text"]
