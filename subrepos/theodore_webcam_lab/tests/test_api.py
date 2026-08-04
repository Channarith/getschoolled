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


def test_webcam_expression_api_returns_happy_summary():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-expression-1",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-a",
                    "timestamp_ms": 2_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "expression_label": "happy",
                    "expression_confidence": 0.93,
                },
                {
                    "participant_id": "learner-b",
                    "timestamp_ms": 2_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "expression_label": "neutral",
                    "expression_confidence": 0.74,
                },
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["happy_participant_ids"] == ["learner-a"]
    assert body["expression_counts"] == {"happy": 1, "neutral": 1}


def test_webcam_api_flags_long_eyes_away_phone_typing_pattern():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-cheat-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-z",
                    "timestamp_ms": 5_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                    "typing_activity_score": 0.95,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    participant = body["participants"][0]
    assert participant["suspected_cheating"] is False

    # Second frame in the same session keeps eyes away long enough to cross
    # the default sustained-away grace and should now be flagged.
    resp2 = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-cheat-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-z",
                    "timestamp_ms": 52_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                    "typing_activity_score": 0.95,
                }
            ],
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    p2 = body2["participants"][0]
    assert p2["suspected_cheating"] is True
    assert body2["suspected_cheating_participant_ids"] == ["learner-z"]
    assert p2["eyes_away_for_ms"] == 47_000


def test_webcam_api_detects_keyboard_typing_audio_pattern():
    first = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "audio-cheat-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-k",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "keyboard_typing_audio_score": 0.88,
                }
            ],
        },
    )
    assert first.status_code == 200
    assert first.json()["participants"][0]["suspected_cheating"] is False

    second = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "audio-cheat-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-k",
                    "timestamp_ms": 50_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "keyboard_typing_audio_score": 0.88,
                }
            ],
        },
    )
    assert second.status_code == 200
    body = second.json()
    participant = body["participants"][0]
    assert participant["keyboard_typing_audio_detected"] is True
    assert participant["suspected_cheating"] is True
    assert participant["cheating_reasons"] == [
        "eyes_away_long",
        "keyboard_typing_audio",
    ]
    assert body["keyboard_typing_audio_participant_ids"] == ["learner-k"]
