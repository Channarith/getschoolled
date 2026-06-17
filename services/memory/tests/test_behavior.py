"""Phase 4 - learning-behavior tracking + learner signals (memory service)."""

from fastapi.testclient import TestClient

from memory.main import app
from memory.store import MemoryStore

client = TestClient(app)


def test_store_records_behavior_and_aggregates_signals():
    store = MemoryStore()
    for correct in (True, True, False, True):
        store.record_behavior("s1", "fractions", quiz_correct=correct)
    store.record_behavior("s1", "fractions", response_latency_s=4.0, saw_slide=True)
    store.record_behavior("s1", "fractions", attention=0.4, asked_question=True, saw_slide=True)

    sig = store.learner_signals("s1", "fractions")
    assert round(sig.quiz_accuracy, 2) == 0.75
    assert sig.avg_response_latency_s == 4.0
    assert sig.attention_trend == 0.4
    assert sig.question_rate == 0.5  # 1 question / 2 slides


def test_unknown_student_returns_neutral_signals():
    store = MemoryStore()
    sig = store.learner_signals("nobody", "topic")
    assert sig.quiz_accuracy == 0.5
    assert sig.attention_trend == 1.0


def test_behavior_endpoint_then_learner_endpoint():
    client.post(
        "/behavior",
        json={"student_id": "s2", "topic": "algebra", "quiz_correct": True, "saw_slide": True},
    )
    client.post(
        "/behavior",
        json={"student_id": "s2", "topic": "algebra", "quiz_correct": False, "attention": 0.6},
    )
    body = client.get("/learner/s2/algebra").json()
    assert body["student_id"] == "s2"
    assert 0.0 <= body["quiz_accuracy"] <= 1.0
    assert "skill" in body


def test_mastery_feeds_learner_signal():
    client.post("/mastery", json={"student_id": "s3", "topic": "geo", "correct": True})
    body = client.get("/learner/s3/geo").json()
    assert body["topic_mastery"] > 0.0
