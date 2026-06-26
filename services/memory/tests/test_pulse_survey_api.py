"""Pulse survey API (in-lesson check-ins)."""

from aoep_shared.pulse_survey import PulseSurveyStore
from aoep_shared.survey import SurveyStore
from fastapi.testclient import TestClient

from memory.main import app

client = TestClient(app)

ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def setup_function():
    app.state.surveys = SurveyStore()
    app.state.pulse_surveys = PulseSurveyStore()
    client.put("/admin/flags/engagement.pulse_survey",
               json={"enabled": True, "value": True}, headers=ADMIN)


def test_pulse_template_enabled_by_default():
    body = client.get("/survey/pulse").json()
    assert body["enabled"] is True
    assert body["template"]["interval_slides"] == 5
    assert len(body["template"]["questions"]) == 3


def test_submit_and_summarize_pulse():
    r = client.post("/survey/pulse", json={
        "course_id": "fractions-101",
        "going_well": 4,
        "pace": "just right",
        "teaching_strategy": "worked_examples",
        "working_best": "examples",
        "slide_index": 4,
    })
    assert r.status_code == 200
    summ = client.get("/survey/pulse/summary/fractions-101").json()
    assert summ["responses"] == 1
    assert summ["avg_going_well"] == 4.0
    assert summ["avg_by_strategy"]["worked_examples"] == 4.0


def test_invalid_rating_422():
    r = client.post("/survey/pulse", json={"course_id": "x", "going_well": 9, "pace": "ok"})
    assert r.status_code == 422
