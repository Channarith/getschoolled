"""End-to-end-ish API tests for the orchestrator teaching flow."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "orchestrator"


def test_lessons_loaded():
    r = client.get("/api/lessons")
    assert r.status_code == 200
    ids = {lesson["lesson_id"] for lesson in r.json()}
    assert "intro-to-photosynthesis" in ids


def test_teaching_flow_start_advance_ask():
    start = client.post(
        "/api/sessions",
        json={"lesson_id": "intro-to-photosynthesis", "class_type": "group"},
    )
    assert start.status_code == 200
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
    assert ask.status_code == 200
    answer = ask.json()
    assert answer["text"]
    assert len(answer["citations"]) >= 1


def test_unknown_lesson_404():
    r = client.post("/api/sessions", json={"lesson_id": "nope", "class_type": "solo"})
    assert r.status_code == 404
