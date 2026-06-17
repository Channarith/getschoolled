"""Live-class teaching loop API tests (lessons/sessions/slides/ask)."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_lessons_loaded_from_curriculum():
    r = client.get("/api/lessons")
    assert r.status_code == 200
    ids = {lsn["lesson_id"] for lsn in r.json()}
    assert "intro-to-photosynthesis" in ids


def test_start_advance_ask_flow():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    assert start.status_code == 200, start.text
    view = start.json()
    sid = view["session"]["session_id"]
    assert view["slide"]["index"] == 0

    adv = client.post(f"/api/sessions/{sid}/advance")
    assert adv.status_code == 200
    assert adv.json()["index"] == 1

    ask = client.post(
        f"/api/sessions/{sid}/ask",
        json={"text": "What gas do plants release?", "language": "en"},
    )
    assert ask.status_code == 200, ask.text
    answer = ask.json()
    assert answer["text"]
    assert len(answer["citations"]) >= 1


def test_unknown_lesson_404():
    r = client.post("/api/sessions", json={"lesson_id": "nope", "class_type": "solo"})
    assert r.status_code == 404
