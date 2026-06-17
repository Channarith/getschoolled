from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "memory"


def test_profile_roundtrip():
    client.put("/api/profiles/s1", json={"student_id": "s1", "display_name": "Ada"})
    r = client.get("/api/profiles/s1")
    assert r.json()["display_name"] == "Ada"
