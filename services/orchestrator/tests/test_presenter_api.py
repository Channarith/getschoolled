"""Theodore AI-presenter endpoints + Tutor integration."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_presenter_profile_is_theodore():
    body = client.get("/api/presenter").json()
    assert body["name"] == "Theodore"
    assert body["strategy_count"] >= 20
    ids = {s["id"] for s in body["strategies"]}
    assert {"first_principles", "story_lens", "everyday_relevance"} <= ids
    # Strategies attribute their source instructor/origin.
    assert all(s["source"] for s in body["strategies"])


def test_presenter_profile_filter_by_source():
    body = client.get("/api/presenter", params={"source": "Elon Musk - First Principles"}).json()
    ids = {s["id"] for s in body["strategies"]}
    assert "first_principles" in ids
    assert "story_lens" not in ids


def test_presenter_rehearse_improves_score():
    r = client.post("/api/presenter/rehearse",
                    json={"narration": "A variable stores a value.", "topic": "variables"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score_after"] > body["score_before"]
    assert body["improved"] is True
    assert "A variable stores a value." in body["rehearsed"]


def test_presenter_playbook_and_attention():
    pb = client.post("/api/presenter/playbook",
                     json={"segment_kind": "intro", "topic": "loops"}).json()
    assert pb["segment_kind"] == "intro"
    assert any(step["id"] == "curiosity_gap" for step in pb["steps"])

    att = client.get("/api/presenter/attention", params={"score": 0.2, "topic": "loops"}).json()
    assert att["intensity"] == "high"


def test_tutor_answer_carries_theodore_touch_offline():
    sid = client.post("/api/sessions", json={
        "lesson_id": "intro-to-photosynthesis", "class_type": "group"}).json()["session"]["session_id"]
    ans = client.post(f"/api/sessions/{sid}/ask",
                      json={"text": "What gas do plants release?"}).json()
    # Grounded offline answers get a single Theodore comprehension-check closer.
    assert ans["grounded"] is True
    assert "your own words" in ans["text"].lower()
