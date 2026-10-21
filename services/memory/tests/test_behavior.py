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


def test_pronunciation_score_is_stored_and_blended():
    store = MemoryStore()
    store.record_behavior("s4", "spanish", pronunciation_score=80)
    store.record_behavior("s4", "spanish", pronunciation_score=0.6)
    sig = store.learner_signals("s4", "spanish")
    assert round(sig.quiz_accuracy, 3) == round((0.8 + 0.6) / 2, 3)


def test_pronunciation_endpoint_records():
    client.post(
        "/behavior",
        json={"student_id": "s5", "topic": "french", "pronunciation_score": 90},
    )
    body = client.get("/learner/s5/french").json()
    assert round(body["quiz_accuracy"], 2) == 0.9


def test_learner_endpoint_reports_camera_and_pronunciation_evidence():
    client.post("/behavior", json={"student_id": "s6", "topic": "german", "attention": 0.3})
    client.post("/behavior", json={"student_id": "s6", "topic": "german", "pronunciation_score": 70})
    body = client.get("/learner/s6/german").json()
    assert body["attention_samples"] == 1
    assert body["pronunciation_samples"] == 1
    assert round(body["pronunciation_mean"], 2) == 0.7
    empty = client.get("/learner/nobody-here/german").json()
    assert empty["attention_samples"] == 0
    assert empty["pronunciation_mean"] is None


def test_mastery_feeds_learner_signal():
    client.post("/mastery", json={"student_id": "s3", "topic": "geo", "correct": True})
    body = client.get("/learner/s3/geo").json()
    assert body["topic_mastery"] > 0.0
