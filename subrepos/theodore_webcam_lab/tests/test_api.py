from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_webcam_lab.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "theodore-webcam-lab"


def test_webcam_evaluation_api_returns_solo_multiple_face_alert():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "solo-api-1",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner",
                    "timestamp_ms": 1_000,
                    "face_count": 2,
                    "liveness_state": "live",
                    "foreground_ratio": 0.3,
                    "motion_score": 0.2,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "solo_mode_multiple_faces:learner" in body["alerts"]


def test_voice_endpoint_falls_back_without_xai_key():
    resp = client.post(
        "/api/theodore/voice/respond",
        json={
            "class_mode": "group",
            "learner_message": "Can I get help with this biology topic?",
            "context": "Group revision",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local-fallback"
    assert body["fallback_used"] is True
