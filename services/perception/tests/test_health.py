from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "perception"


def test_attention_requires_consent():
    denied = client.post("/api/attention", json={"student_id": "s1", "consent": False})
    assert denied.status_code == 403
    ok = client.post("/api/attention", json={"student_id": "s1", "consent": True})
    assert ok.status_code == 200
