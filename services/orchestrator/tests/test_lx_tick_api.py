"""Director LX tick API."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_lx_tick_returns_score_and_strategy():
    r = client.post("/director/lx-tick", json={
        "class_type": "solo",
        "slides_total": 10,
        "slide_index": 3,
        "topic_mastery": 0.4,
        "quiz_accuracy": 0.5,
        "wellness_state": "ok",
        "frustration_events": 0,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "lx_score" in body
    assert body["teaching_strategy"]
    assert body["lx_target"] == 75.0
    assert body["improve_actions"]


def test_lx_tick_wellness_eases_session():
    body = client.post("/director/lx-tick", json={
        "class_type": "solo",
        "slides_total": 8,
        "slide_index": 2,
        "wellness_state": "unwell",
        "topic_mastery": 0.6,
        "quiz_accuracy": 0.6,
    }).json()
    assert body["pacing"] == "slow"
    assert body["difficulty"] == "easy"
    assert body["reteach"] is True
