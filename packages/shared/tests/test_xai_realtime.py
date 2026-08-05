"""xAI voice agent helper tests (HTTP mocked; no network)."""

from __future__ import annotations

import json

import pytest

from aoep_shared import xai_realtime as xai_voice as xv


def test_mock_ephemeral_token_without_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    token = xv.mint_ephemeral_token(allow_mock=True, expires_seconds=120)
    assert token.mock is True
    assert token.value.startswith("mock-")
    assert "xai-client-secret." in token.websocket_protocol
    assert "grok-voice" in token.websocket_url


def test_mint_requires_key_when_mock_disallowed(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(xv.XaiVoiceError):
        xv.mint_ephemeral_token(allow_mock=False)


def test_mint_real_path_parses_response(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    def fake_post(url, *, data, headers, timeout):
        assert url.endswith("/realtime/client_secrets")
        assert headers["Authorization"] == "Bearer test-key"
        payload = json.loads(data.decode("utf-8"))
        assert payload["expires_after"]["seconds"] == 300
        return json.dumps({"value": "ephem-abc", "expires_at": 1_700_000_000}).encode()

    monkeypatch.setattr(xv, "_http_post", fake_post)
    token = xv.mint_ephemeral_token(expires_seconds=300, allow_mock=False)
    assert token.mock is False
    assert token.value == "ephem-abc"
    assert token.expires_at == 1_700_000_000


def test_build_voice_session_personas():
    solo = xv.build_voice_session("solo", lesson_context="Slide 1")
    assert solo.persona == xv.PERSONA_THEODORE
    event = solo.session_update_event()
    assert event["type"] == "session.update"
    assert "Theodore" in event["session"]["instructions"]
    assert "Slide 1" in event["session"]["instructions"]
    assert event["session"]["turn_detection"]["type"] == "server_vad"

    self_teach = xv.build_voice_session("self_teach", learner_names=["Ada"])
    assert self_teach.persona == xv.PERSONA_SELF_TEACH
    assert "Ada" in self_teach.resolved_instructions()

    group = xv.build_voice_session("group")
    assert group.persona == xv.PERSONA_GROUP_HOST


def test_presence_tool_schema():
    tool = xv.presence_tool_schema()
    assert tool["type"] == "function"
    assert tool["name"] == "get_learner_presence"


def test_xai_configured(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert xv.xai_configured() is False
    monkeypatch.setenv("XAI_API_KEY", "  sk-xai  ")
    assert xv.xai_configured() is True
