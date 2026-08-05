"""xAI voice agent config tests (no network)."""

import json

from webcam_vision_lab.voice.xai_voice_agent import (
    XaiVoiceAgentConfig,
    build_session_update,
    ephemeral_token_request_payload,
)
from webcam_vision_lab.scenarios.solo_class import solo_theodore_instructions


def test_session_update_shape():
    config = XaiVoiceAgentConfig(
        api_key="test-key",
        instructions=solo_theodore_instructions(),
        voice="ara",
    )
    msg = build_session_update(config)
    assert msg["type"] == "session.update"
    session = msg["session"]
    assert session["voice"] == "ara"
    assert "Theodore" in session["instructions"]
    assert session["turn_detection"]["type"] == "server_vad"


def test_realtime_url_contains_model():
    config = XaiVoiceAgentConfig(model="grok-voice-latest")
    assert "grok-voice-latest" in config.realtime_url()


def test_ephemeral_payload_serializable():
    config = XaiVoiceAgentConfig(instructions="hello")
    payload = ephemeral_token_request_payload(config)
    json.dumps(payload)
