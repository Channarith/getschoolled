from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "curriculum"


def test_decks_listed():
    r = client.get("/api/decks")
    assert r.status_code == 200
    assert "intro-to-fractions" in r.json()
