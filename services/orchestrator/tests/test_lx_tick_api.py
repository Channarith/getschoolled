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
    assert body["learner_line_key"].startswith("adapt.")


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
    assert body["learner_line_key"] == "adapt.reteach"


class _StoredBehavior:
    """Memory stand-in: a learner whose camera attention and speech are weak."""

    def __init__(self):
        self.calls = []

    def learner_snapshot(self, student_id, topic):
        from aoep_shared.adaptive import LearnerSignals
        from orchestrator.memory_client import LearnerSnapshot

        self.calls.append((student_id, topic))
        return LearnerSnapshot(
            signals=LearnerSignals(
                topic_mastery=0.2, quiz_accuracy=0.2, attention_trend=0.2,
                avg_response_latency_s=20.0,
            ),
            attention_samples=6,
            pronunciation_samples=4,
            pronunciation_mean=0.1,
        )


def _with_memory(fake):
    from orchestrator import main as orchestrator_main

    sessions = orchestrator_main.get_sessions()
    original = sessions.memory
    sessions.memory = fake
    return sessions, original


def test_signals_fill_from_memory_when_the_client_did_not_measure():
    from orchestrator.main import PlanRequest, _signals_with_memory

    fake = _StoredBehavior()
    sessions, original = _with_memory(fake)
    try:
        signals = _signals_with_memory(PlanRequest(
            student_id="stu-1", topic="Fractions", slides_total=8, slide_index=2,
        ))
    finally:
        sessions.memory = original
    assert fake.calls == [("stu-1", "Fractions")]
    assert signals.attention_trend == 0.2
    assert signals.quiz_accuracy == 0.2
    assert signals.avg_response_latency_s == 20.0


def test_live_readings_win_and_pronunciation_blends_into_accuracy():
    from orchestrator.main import PlanRequest, _signals_with_memory

    sessions, original = _with_memory(_StoredBehavior())
    try:
        signals = _signals_with_memory(PlanRequest(
            student_id="stu-1", topic="Fractions",
            attention_trend=0.9, quiz_accuracy=1.0,
        ))
    finally:
        sessions.memory = original
    assert signals.attention_trend == 0.9
    assert round(signals.quiz_accuracy, 2) == round(0.7 * 1.0 + 0.3 * 0.1, 2)


def test_stored_weak_behavior_slows_the_lx_tick():
    sessions, original = _with_memory(_StoredBehavior())
    try:
        body = client.post("/director/lx-tick", json={
            "class_type": "solo", "slides_total": 10, "slide_index": 3,
            "student_id": "stu-1", "topic": "Fractions",
        }).json()
        neutral = client.post("/director/lx-tick", json={
            "class_type": "solo", "slides_total": 10, "slide_index": 3,
        }).json()
    finally:
        sessions.memory = original
    assert body["lx_score"] < neutral["lx_score"]
    assert body["difficulty"] == "easy"


def test_missing_learner_id_from_mobile_is_accepted():
    r = client.post("/director/lx-tick", json={
        "class_type": "solo", "slides_total": 4, "slide_index": 1,
        "student_id": None, "topic": "Intro",
    })
    assert r.status_code == 200, r.text
