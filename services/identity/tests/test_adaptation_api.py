"""Learner adaptation API."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="adapt@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": "Ada",
    }).json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _student_id(tok):
    students = client.get("/students", headers=_auth(tok)).json()["students"]
    return students[0]["id"]


def test_adaptation_trigger_and_pace():
    tok = _signup()["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    out = client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "trigger",
        "payload": {"trigger": "too fast", "reason": "overwhelmed"},
    }).json()
    assert out["adaptation"]["known_triggers"]
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "completion_pace",
        "payload": {"minutes": 45},
    })
    get = client.get(f"/students/{sid}/adaptation", headers=h).json()
    assert get["adaptation"]["observed_pace"] == "slow"


def test_adaptation_goals_and_strategy_failure():
    tok = _signup("goals@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "goals",
        "payload": {"goals": ["pass algebra", "study daily"], "timeline": "3 months"},
    })
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "strategy_failure",
        "payload": {"strategy": "socratic", "topic": "fractions", "reason": "too abstract"},
    })
    get = client.get(f"/students/{sid}/adaptation", headers=h).json()
    assert "pass algebra" in get["learning_goals"]
    assert get["goal_timeline"] == "3 months"
    failed = get["adaptation"]["failed_approaches"]
    assert any(f["strategy"] == "socratic" for f in failed)
    assert get["adaptation"]["strategy_losses"].get("socratic", 0) >= 1


def test_adaptation_strategy_success():
    tok = _signup("win@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "strategy_success",
        "payload": {"strategy": "worked_examples"},
    })
    get = client.get(f"/students/{sid}/adaptation", headers=h).json()
    assert get["adaptation"]["strategy_wins"].get("worked_examples", 0) >= 1


def test_adaptation_unknown_student_404():
    tok = _signup("unknown@example.com")["token"]
    r = client.post("/students/nope/adaptation", headers=_auth(tok), json={
        "event_type": "trigger",
        "payload": {"trigger": "x", "reason": "y"},
    })
    assert r.status_code == 404
