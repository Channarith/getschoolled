from __future__ import annotations

from theodore_webcam_lab.models import ClassMode, VoiceAgentRequest
from theodore_webcam_lab.voice import XaiVoiceAgent, XaiVoiceConfig


def test_xai_voice_agent_uses_transport_and_returns_model_text() -> None:
    captured: dict = {}

    def transport(url: str, payload: dict, headers: dict, timeout: float) -> dict:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "Welcome back, let's continue."}}]}

    agent = XaiVoiceAgent(
        XaiVoiceConfig(api_key="test-key", base_url="https://api.x.ai/v1", model="grok-2-latest"),
        transport=transport,
    )
    response = agent.respond(
        VoiceAgentRequest(
            session_id="s1",
            class_mode=ClassMode.solo,
            recent_event_codes=["user_returned"],
            student_message="I am back.",
        )
    )

    assert response.used_fallback is False
    assert response.engine == "xai"
    assert "continue" in response.text.lower()
    assert captured["url"] == "https://api.x.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "grok-2-latest"


def test_voice_agent_falls_back_without_api_key() -> None:
    agent = XaiVoiceAgent(XaiVoiceConfig(api_key=""))
    response = agent.respond(
        VoiceAgentRequest(
            session_id="s2",
            class_mode=ClassMode.solo,
            recent_event_codes=["silhouette_detected"],
            student_message="",
        )
    )

    assert response.used_fallback is True
    assert response.engine == "fallback"
    assert "camera" in response.text.lower()


def test_voice_agent_falls_back_on_transport_error() -> None:
    def broken_transport(url: str, payload: dict, headers: dict, timeout: float) -> dict:
        raise RuntimeError("network down")

    agent = XaiVoiceAgent(
        XaiVoiceConfig(api_key="test-key"),
        transport=broken_transport,
    )
    response = agent.respond(
        VoiceAgentRequest(
            session_id="s3",
            class_mode=ClassMode.group,
            recent_event_codes=["group_understaffed"],
            student_message="",
        )
    )

    assert response.used_fallback is True
    assert response.engine == "fallback"
    assert "classmates" in response.text.lower()
