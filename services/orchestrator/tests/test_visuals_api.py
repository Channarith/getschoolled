"""On-demand lesson visual generator API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_generate_license_compare_visual():
    r = client.post(
        "/api/visuals/generate",
        json={
            "question": "Show me the differences between California and Texas driver's licenses",
            "force": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    vis = body["visual"]
    assert vis["svg"].lower().startswith("<svg")
    assert vis["narration"]
    assert vis.get("frames")


def test_generate_short_question_422():
    r = client.post("/api/visuals/generate", json={"question": "hi"})
    assert r.status_code == 422


def test_ask_can_include_visual():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    assert start.status_code == 200, start.text
    sid = start.json()["session"]["session_id"]
    ask = client.post(
        f"/api/sessions/{sid}/ask",
        json={
            "text": "Show me a picture example of photosynthesis on the screen",
            "language": "en",
        },
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()
    assert body.get("text")
    # Visual is best-effort; when generated it must be a valid SVG payload.
    if body.get("visual"):
        assert "<svg" in body["visual"]["svg"].lower()
