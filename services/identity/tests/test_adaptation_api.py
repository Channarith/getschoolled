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


def test_adaptation_trigger_and_pace():
    tok = _signup()["token"]
    h = _auth(tok)
    students = client.get("/students", headers=h).json()["students"]
    sid = students[0]["id"]
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
