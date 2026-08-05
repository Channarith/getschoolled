"""xAI Grok voice agent client tests (offline mock)."""

import pytest

from webcam_recognition_suite.xai_voice import (
    MockXaiVoiceAgent,
    XaiVoiceConfig,
    build_session_update,
    build_text_turn,
    build_theodore_tools,
    try_live_session,
)


def test_session_update_shape():
    cfg = XaiVoiceConfig(voice="eve", instructions="You are Theodore.")
    evt = build_session_update(cfg, tools=build_theodore_tools())
    assert evt["type"] == "session.update"
    assert evt["session"]["voice"] == "eve"
    assert evt["session"]["turn_detection"]["type"] == "server_vad"
    assert any(t["name"] == "report_presence_hold" for t in evt["session"]["tools"])


def test_text_turn_events():
    evts = build_text_turn("Hello class")
    assert evts[0]["type"] == "conversation.item.create"
    assert evts[1]["type"] == "response.create"


def test_mock_voice_agent_speaks():
    agent = MockXaiVoiceAgent(XaiVoiceConfig())
    session = agent.connect()
    assert session.connected is True
    agent.speak("Welcome everyone.")
    assert any(e.get("type") == "response.done" for e in session.events_received)


def test_config_from_env():
    cfg = XaiVoiceConfig.from_env(
        {
            "XAI_API_KEY": "secret",
            "XAI_VOICE_MODEL": "grok-voice-think-fast-2.0",
            "XAI_VOICE_NAME": "ara",
        }
    )
    assert cfg.api_key == "secret"
    assert "2.0" in cfg.model
    assert cfg.voice == "ara"
    assert "model=" in cfg.realtime_url


def test_try_live_requires_key():
    with pytest.raises(RuntimeError, match="XAI_API_KEY"):
        try_live_session(XaiVoiceConfig(api_key=""))
