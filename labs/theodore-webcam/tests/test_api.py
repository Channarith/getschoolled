"""End-to-end HTTP behaviour of the lab service."""

from __future__ import annotations

import base64

import _scene
import cv2
import pytest
from fastapi.testclient import TestClient

from theodore_webcam.config import load_config
from theodore_webcam.main import create_app


def encode(frame) -> str:
    ok, buffer = cv2.imencode(".jpg", frame)
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode()


@pytest.fixture
def client():
    config = load_config(
        {
            "WEBCAM_LAB_ARRIVE_CONFIRM_SECONDS": "0",
            "WEBCAM_LAB_RETURN_CONFIRM_SECONDS": "0",
            "WEBCAM_LAB_ABSENCE_GRACE_SECONDS": "0",
            "WEBCAM_LAB_RECAP_AFTER_ABSENCE_SECONDS": "0",
        }
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_health_and_config(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["voice"] == "offline-fallback"

    config = client.get("/v1/config").json()
    assert "api_key" not in config["xai"]
    assert config["xai"]["configured"] is False
    assert config["presence"]["stale_seconds"] > 0


def test_solo_session_frame_loop_reports_presence_and_cues(client):
    created = client.post(
        "/v1/sessions",
        json={
            "mode": "solo",
            "lesson_title": "Fractions, part 2",
            "checkpoint": "slide 7",
            "participants": [{"participant_id": "learner-1", "display_name": "Maya"}],
        },
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    empty = encode(_scene.empty_room())
    person = encode(_scene.person_scene())

    for _ in range(12):
        client.post(
            f"/v1/sessions/{session_id}/frames",
            json={"participant_id": "learner-1", "image": empty},
        )

    body = {}
    for _ in range(4):
        body = client.post(
            f"/v1/sessions/{session_id}/frames",
            json={"participant_id": "learner-1", "image": person},
        ).json()
    assert body["observation"]["detected"] is True
    assert body["presence"]["state"] == "present"
    assert body["observation"]["silhouettes"][0]["human_score"] >= 0.45

    away_cues = []
    for _ in range(4):
        body = client.post(
            f"/v1/sessions/{session_id}/frames",
            json={"participant_id": "learner-1", "image": empty},
        ).json()
        away_cues.extend(body["cues"])
    assert body["presence"]["state"] == "absent"
    assert body["lesson_paused"] is True
    pause = [c for c in away_cues if c["action"] == "pause_lesson"]
    assert pause, "solo absence must pause the lesson"
    assert pause[0]["voice_turn"] is False
    assert "slide 7" in pause[0]["speech"]

    back_cues = []
    for _ in range(3):
        body = client.post(
            f"/v1/sessions/{session_id}/frames",
            json={"participant_id": "learner-1", "image": person},
        ).json()
        back_cues.extend(body["cues"])
    assert body["presence"]["state"] == "present"
    assert body["lesson_paused"] is False
    spoken = [c for c in back_cues if c["voice_turn"] and c["speech"]]
    assert spoken, "Theodore must speak when the learner comes back"
    assert "Maya" in spoken[0]["speech"]

    report = client.get(f"/v1/sessions/{session_id}/report").json()
    assert report["participants"][0]["absence_count"] == 1
    assert any(e["kind"] == "departed" for e in report["events"])


def test_signals_endpoint_accepts_on_device_verdicts(client):
    session_id = client.post("/v1/sessions", json={"mode": "solo"}).json()["session_id"]
    body = client.post(
        f"/v1/sessions/{session_id}/signals",
        json={"participant_id": "p1", "detected": True, "confidence": 0.9, "count": 1},
    ).json()
    assert body["presence"]["detected"] is True
    assert body["observation"]["frame_size"] == [0, 0]


def test_group_session_attendance_hold(client):
    session_id = client.post(
        "/v1/sessions",
        json={
            "mode": "group",
            "lesson_title": "Photosynthesis",
            "participants": [
                {"participant_id": "a"},
                {"participant_id": "b"},
                {"participant_id": "c"},
            ],
        },
    ).json()["session_id"]

    for pid in ("a", "b", "c"):
        client.post(
            f"/v1/sessions/{session_id}/signals",
            json={"participant_id": pid, "detected": True, "confidence": 0.9, "count": 1},
        )
    state = client.get(f"/v1/sessions/{session_id}").json()
    assert state["attendance"]["present"] == 3
    assert state["class_held"] is False

    for pid in ("b", "c"):
        body = client.post(
            f"/v1/sessions/{session_id}/signals",
            json={"participant_id": pid, "detected": False},
        ).json()
    assert body["class_held"] is True
    assert body["lesson_paused"] is False


def test_bad_frame_payload_is_rejected(client):
    session_id = client.post("/v1/sessions", json={"mode": "solo"}).json()["session_id"]
    response = client.post(
        f"/v1/sessions/{session_id}/frames",
        json={"participant_id": "p1", "image": "not-an-image"},
    )
    assert response.status_code == 400


def test_unknown_session_is_404(client):
    assert client.get("/v1/sessions/nope").status_code == 404
    assert (
        client.post(
            "/v1/sessions/nope/frames", json={"participant_id": "p", "image": "x"}
        ).status_code
        == 404
    )


def test_voice_endpoints_degrade_without_an_api_key(client):
    status = client.get("/v1/voice/status").json()
    assert status["configured"] is False
    assert "get_presence_state" in status["tools"]

    session_id = client.post(
        "/v1/sessions",
        json={"mode": "solo", "lesson_title": "Fractions", "checkpoint": "slide 7"},
    ).json()["session_id"]
    client.post(
        f"/v1/sessions/{session_id}/signals",
        json={"participant_id": "learner-1", "detected": True, "confidence": 0.9, "count": 1},
    )

    config = client.get(
        f"/v1/voice/session-config?session_id={session_id}&participant_id=learner-1"
    ).json()
    assert config["session_update"]["session"]["turn_detection"]["type"] == "server_vad"
    assert config["context"]["presence"] == "present"

    voice = client.post(
        "/v1/voice/session",
        json={"session_id": session_id, "participant_id": "learner-1"},
    ).json()
    assert voice["fallback"] is True
    assert voice["session_update"]["type"] == "session.update"
    assert voice["context"]["presence"] == "present"
    assert voice["context"]["lesson_title"] == "Fractions"

    reply = client.post(
        "/v1/voice/respond",
        json={
            "session_id": session_id,
            "participant_id": "learner-1",
            "transcript": "What is a numerator?",
        },
    ).json()
    assert reply["source"] == "fallback"
    assert reply["text"]

    tool = client.post(
        "/v1/voice/tool",
        json={"session_id": session_id, "name": "get_presence_state", "arguments": {}},
    ).json()
    assert tool["result"]["present"] is True


def test_demo_page_is_served(client):
    response = client.get("/demo/")
    assert response.status_code == 200
    assert "Theodore" in response.text
