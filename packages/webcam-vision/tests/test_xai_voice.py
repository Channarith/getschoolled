"""xAI voice agent client tests (HTTP mocked at the isolated transport)."""

import pytest

from aoep_webcam_vision.xai_voice import (
    DEFAULT_REALTIME_URL,
    THEODORE_VOICE_INSTRUCTIONS,
    VoiceAgentConfig,
    XAIVoiceAgent,
    XAIVoiceError,
    voice_agent_from_app_config,
)


def make_agent(**overrides):
    config = VoiceAgentConfig(api_key="xai-test-key", **overrides)
    return XAIVoiceAgent(config)


class TestConfig:
    def test_from_env(self):
        env = {
            "XAI_API_KEY": "  key-123  ",
            "XAI_VOICE": "ara",
            "XAI_VOICE_MODEL": "grok-voice-think-fast-2.0",
        }
        config = VoiceAgentConfig.from_env(env)
        assert config.api_key == "key-123"
        assert config.voice == "ara"
        assert config.voice_model == "grok-voice-think-fast-2.0"
        # Defaults preserved for anything unset.
        assert config.base_url == "https://api.x.ai/v1"
        assert config.realtime_url == DEFAULT_REALTIME_URL

    def test_from_app_config(self):
        class StubAppConfig:
            xai_api_key = "k"
            xai_base_url = "https://api.x.ai/v1"
            xai_realtime_url = "wss://api.x.ai/v1/realtime"
            xai_voice_model = "grok-voice-latest"
            xai_text_model = "grok-3-latest"
            xai_voice = "eve"

        agent = voice_agent_from_app_config(StubAppConfig())
        assert agent.configured() is True
        assert agent.config.voice == "eve"

    def test_unconfigured_without_key(self):
        assert XAIVoiceAgent(VoiceAgentConfig()).configured() is False


class TestPayloads:
    def test_realtime_url_includes_model(self):
        agent = make_agent(voice_model="grok-voice-latest")
        assert agent.realtime_url() == (
            "wss://api.x.ai/v1/realtime?model=grok-voice-latest"
        )

    def test_session_update_payload(self):
        agent = make_agent(voice="eve")
        payload = agent.session_update_payload()
        assert payload["type"] == "session.update"
        session = payload["session"]
        assert session["voice"] == "eve"
        assert session["instructions"] == THEODORE_VOICE_INSTRUCTIONS
        assert session["turn_detection"]["type"] == "server_vad"
        assert "tools" not in session

    def test_session_update_overrides(self):
        agent = make_agent()
        payload = agent.session_update_payload(
            instructions="Be brief.", voice="ara", tools=[{"type": "web_search"}]
        )
        session = payload["session"]
        assert session["instructions"] == "Be brief."
        assert session["voice"] == "ara"
        assert session["tools"] == [{"type": "web_search"}]

    def test_text_turn_payload(self):
        events = XAIVoiceAgent.text_turn_payload("Hello, class")
        assert events[0]["type"] == "conversation.item.create"
        item = events[0]["item"]
        assert item["role"] == "user"
        assert item["content"] == [{"type": "input_text", "text": "Hello, class"}]
        assert events[1] == {"type": "response.create"}


class TestEphemeralToken:
    def test_mint_posts_to_client_secrets(self, monkeypatch):
        agent = make_agent()
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"value": "ek-abc", "expires_at": 1893456000}

        monkeypatch.setattr(agent, "_http_post", fake_post)
        token = agent.mint_ephemeral_token(expires_s=300)
        assert calls == [
            (
                "https://api.x.ai/v1/realtime/client_secrets",
                {"expires_after": {"seconds": 300}},
            )
        ]
        assert token.value == "ek-abc"
        assert token.expires_at == 1893456000.0
        assert token.subprotocol == "xai-client-secret.ek-abc"

    def test_mint_accepts_nested_client_secret_shape(self, monkeypatch):
        agent = make_agent()
        monkeypatch.setattr(
            agent,
            "_http_post",
            lambda url, payload: {"client_secret": {"value": "ek-nested"}},
        )
        assert agent.mint_ephemeral_token().value == "ek-nested"

    def test_mint_requires_key(self):
        with pytest.raises(XAIVoiceError):
            XAIVoiceAgent(VoiceAgentConfig()).mint_ephemeral_token()

    def test_mint_rejects_tokenless_response(self, monkeypatch):
        agent = make_agent()
        monkeypatch.setattr(agent, "_http_post", lambda url, payload: {})
        with pytest.raises(XAIVoiceError):
            agent.mint_ephemeral_token()


class TestTextFallback:
    def test_respond_uses_chat_completions(self, monkeypatch):
        agent = make_agent(text_model="grok-3-latest")
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"choices": [{"message": {"content": "  Hi there.  "}}]}

        monkeypatch.setattr(agent, "_http_post", fake_post)
        reply = agent.respond([{"role": "user", "content": "hello"}])
        assert reply == "Hi there."
        url, payload = calls[0]
        assert url == "https://api.x.ai/v1/chat/completions"
        assert payload["model"] == "grok-3-latest"
        assert payload["stream"] is False

    def test_respond_requires_key(self):
        with pytest.raises(XAIVoiceError):
            XAIVoiceAgent(VoiceAgentConfig()).respond([])

    def test_respond_rejects_empty_completion(self, monkeypatch):
        agent = make_agent()
        monkeypatch.setattr(agent, "_http_post", lambda url, payload: {"choices": []})
        with pytest.raises(XAIVoiceError):
            agent.respond([{"role": "user", "content": "hi"}])


class TestRealtimeConnect:
    def test_connect_requires_key(self):
        agent = XAIVoiceAgent(VoiceAgentConfig())
        with pytest.raises(NotImplementedError):
            import asyncio

            asyncio.run(agent.connect())
