from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_webcam_lab.api import create_app
from theodore_webcam_lab.models import ClassMode, VoiceAgentRequest, VoiceAgentResponse
from theodore_webcam_lab.monitor import WebcamSessionMonitor


class _MockVoiceAgent:
    def __init__(self) -> None:
        self.requests: list[VoiceAgentRequest] = []

    def respond(self, request: VoiceAgentRequest) -> VoiceAgentResponse:
        self.requests.append(request)
        return VoiceAgentResponse(
            text="Please return to your learning seat and face the camera.",
            engine="xai-mock",
            used_fallback=False,
        )


def test_analyze_session_includes_teacher_prompt_when_events_exist() -> None:
    voice = _MockVoiceAgent()
    monitor = WebcamSessionMonitor(absence_frame_threshold=1)
    app = create_app(monitor=monitor, voice_agent=voice)
    client = TestClient(app)

    response = client.post(
        "/lab/session/analyze",
        json={
            "session_id": "solo-1",
            "class_mode": "solo",
            "timestamp_ms": 1000,
            "expected_participants": 1,
            "participants": [],
            "face_count": 0,
            "foreground_ratio": 0.0,
            "motion_ratio": 0.0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_absent"] is True
    assert body["teacher_prompt"].startswith("Please return")
    assert body["voice_engine"] == "xai-mock"
    assert voice.requests and "user_absent" in voice.requests[0].recent_event_codes


def test_voice_respond_endpoint_uses_voice_agent() -> None:
    voice = _MockVoiceAgent()
    app = create_app(voice_agent=voice)
    client = TestClient(app)

    response = client.post(
        "/lab/voice/respond",
        json={
            "session_id": "group-1",
            "class_mode": ClassMode.group.value,
            "recent_event_codes": ["group_understaffed"],
            "student_message": "Can we recap while we wait?",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "xai-mock"
    assert body["used_fallback"] is False
