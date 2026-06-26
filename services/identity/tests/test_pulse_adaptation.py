"""Pulse survey feeds adaptation and strategy bandit."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="pulse@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": "Pulse",
    }).json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _sid(tok):
    return client.get("/students", headers=_auth(tok)).json()["students"][0]["id"]


def test_pulse_survey_updates_lx_and_strategy():
    tok = _signup()["token"]
    h = _auth(tok)
    sid = _sid(tok)
    out = client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "pulse_survey",
        "payload": {
            "course_id": "lesson-1",
            "going_well": 5,
            "pace": "just right",
            "working_best": "examples",
            "teaching_strategy": "worked_examples",
        },
    }).json()
    adapt = out["adaptation"]
    assert adapt["lx_score_ema"] == 100.0
    assert adapt["strategy_wins"].get("worked_examples", 0) >= 1


def test_pulse_prefers_different_strategy_on_low_score():
    tok = _signup("pulse2@example.com")["token"]
    h = _auth(tok)
    sid = _sid(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "pulse_survey",
        "payload": {
            "course_id": "lesson-1",
            "going_well": 2,
            "pace": "too fast",
            "working_best": "explanations",
            "teaching_strategy": "worked_examples",
        },
    })
    adapt = client.get(f"/students/{sid}/adaptation", headers=h).json()["adaptation"]
    assert adapt["lx_score_ema"] == 40.0
    failed = adapt.get("failed_approaches") or []
    assert any(f["strategy"] == "worked_examples" for f in failed)
