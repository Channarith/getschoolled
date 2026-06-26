"""Director plan merges declared pace and evolving learner adaptation."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def _plan(**overrides):
    body = {
        "class_type": "solo",
        "slides_total": 12,
        "slide_index": 4,
        "pending_questions": 0,
        "attention": 0.7,
        "slides_since_quiz": 2,
        "topic_mastery": 0.55,
        "quiz_accuracy": 0.6,
        "avg_response_latency_s": 8.0,
        "attention_trend": 0.8,
        "question_rate": 0.1,
        "declared_pace": "moderate",
        "adaptation": {},
    }
    body.update(overrides)
    return client.post("/director/plan", json=body)


def test_observed_slow_pace_overrides_normal():
    r = _plan(adaptation={"observed_pace": "slow"})
    assert r.status_code == 200
    body = r.json()
    assert body["pacing"] == "slow"
    assert any("observed_slow" in reason for reason in body["reasons"])


def test_sensitivity_rules_trigger_gentler_reteach():
    r = _plan(adaptation={
        "sensitivity_rules": [
            {"rule_id": "tr1", "trigger": "harsh tone", "reason": "upset",
             "allow_retry": False, "severity": "high"},
        ],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["reteach"] is True
    assert any("sensitivity" in reason for reason in body["reasons"])


def test_declared_slow_overrides_fast_behavior():
    r = _plan(
        declared_pace="slow",
        adaptation={"observed_pace": "fast"},
        topic_mastery=0.8,
        quiz_accuracy=0.85,
        avg_response_latency_s=4.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pacing"] != "fast"
    assert any("declared_slow" in reason for reason in body["reasons"])


def test_failed_approaches_do_not_break_plan():
    r = _plan(adaptation={
        "failed_approaches": [
            {"strategy": "socratic", "topic": "fractions", "reason": "confused"},
        ],
        "strategy_losses": {"socratic": 2},
    })
    assert r.status_code == 200
    assert "pacing" in r.json()


def test_wellness_unwell_slows_and_eases():
    r = _plan(wellness_state="unwell", course_complexity=4)
    assert r.status_code == 200
    body = r.json()
    assert body["pacing"] == "slow"
    assert body["difficulty"] == "easy"
    assert body["reteach"] is True
