"""POST /api/embody - teaching beat -> embodiment actions (Phase 14)."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_embody_returns_speech_and_gesture_actions():
    body = client.post("/api/embody", json={"text": "Welcome to class", "gesture": "wave"}).json()
    assert body["embodiment"] in ("screen-avatar", "mock-robot", "robot")
    modalities = [a["modality"] for a in body["actions"]]
    assert "speech" in modalities
    assert len(body["actions"]) == 2
