from __future__ import annotations

from theodore_webcam_lab.types import ClassMode
from theodore_webcam_lab.voice_agents import XaiVoiceAgent


def test_local_fallback_when_no_api_key():
    agent = XaiVoiceAgent(api_key="")
    response = agent.respond(
        learner_message="I keep missing this math step.",
        class_mode=ClassMode.SOLO,
    )
    assert response.provider == "local-fallback"
    assert response.fallback_used is True
    assert "math" in response.message


def test_xai_response_when_transport_succeeds(monkeypatch):
    agent = XaiVoiceAgent(api_key="test-key", model="grok-4")

    def _fake_transport(payload: dict) -> dict:
        assert payload["model"] == "grok-4"
        return {
            "choices": [
                {"message": {"content": "Great question. Let's solve it together."}}
            ]
        }

    monkeypatch.setattr(agent, "_transport", _fake_transport)
    response = agent.respond(
        learner_message="Can you explain inertia again?",
        class_mode=ClassMode.GROUP,
        context="Physics review session",
    )
    assert response.provider == "xai"
    assert response.fallback_used is False
    assert response.message.startswith("Great question.")
