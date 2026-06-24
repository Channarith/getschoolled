"""Onboarding survey API (flag-gated template + analytics)."""

from aoep_shared.flags import FlagStore
from aoep_shared.learning_profile import OnboardingSurveyStore
from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)

ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def _answers():
    return {
        "primary_style": "Reading & writing — notes, text, written steps",
        "pace": "Slower with more review",
        "structure": "Step-by-step in order",
        "session_length": "About 10 minutes",
        "group_preference": "Mostly on my own",
        "reading_level": "Beginner — keep language simple",
        "motivation": "School or certification",
    }


def _reset():
    app.state.flags = FlagStore()
    app.state.onboarding_surveys = OnboardingSurveyStore()


def test_onboarding_template_enabled_by_default():
    _reset()
    body = client.get("/survey/onboarding").json()
    assert body["enabled"] is True
    assert any(q["id"] == "primary_style" for q in body["template"]["questions"])


def test_submit_onboarding_survey():
    _reset()
    r = client.post("/survey/onboarding", json={
        "account_id": "a1", "student_id": "s1", "answers": _answers(),
    })
    assert r.status_code == 200
    data = r.json()
    assert data["recorded"] is True
    assert data["learner_category"] == "slow_paced_learner"
    summ = client.get("/admin/survey/onboarding/summary", headers=ADMIN).json()
    assert summ["responses"] == 1


def test_submit_rejects_missing_required():
    _reset()
    r = client.post("/survey/onboarding", json={"account_id": "a1", "student_id": "s1", "answers": {}})
    assert r.status_code == 422
