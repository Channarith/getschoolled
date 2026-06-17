from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "speech"


def test_tts_stub():
    r = client.post("/api/tts", json={"text": "hello", "language": "en"})
    assert r.status_code == 200
    assert r.json()["language"] == "en"
