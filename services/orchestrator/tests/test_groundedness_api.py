"""Hallucination guard: endpoint + Tutor integration."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)

CONTEXT = ["Oxygen is a byproduct of photosynthesis released into the air."]


def test_groundedness_endpoint_flags_hallucination():
    r = client.post("/api/groundedness/check", json={
        "answer": "Plants emit pure helium during digestion.", "context": CONTEXT})
    assert r.status_code == 200, r.text
    assert r.json()["grounded"] is False
    assert r.json()["hallucination_risk"] > 0.5


def test_groundedness_endpoint_passes_grounded():
    r = client.post("/api/groundedness/check", json={
        "answer": "Oxygen is a byproduct of photosynthesis.", "context": CONTEXT})
    assert r.json()["grounded"] is True


def test_tutor_answer_exposes_grounding_fields():
    sid = client.post("/api/sessions", json={
        "lesson_id": "intro-to-photosynthesis", "class_type": "group"}).json()["session"]["session_id"]
    ans = client.post(f"/api/sessions/{sid}/ask",
                      json={"text": "What gas do plants release?"}).json()
    assert "grounded" in ans and "hallucination_risk" in ans and "unsupported" in ans
    assert 0.0 <= ans["hallucination_risk"] <= 1.0
    # The served answer is always safe: either grounded, or replaced by the
    # context-faithful fallback (never raw ungrounded content).
    assert ans["grounded"] is True or "lesson" in ans["text"].lower()
