"""xAI voice agent client (offline + mocked websocket)."""

from __future__ import annotations

import json

import pytest

from webcam_lab.xai_voice import OfflineVoiceAgent, XaiVoiceAgent, build_voice_agent


@pytest.mark.asyncio
async def test_offline_voice_speaks():
    agent = OfflineVoiceAgent(instructions="You are Theodore.")
    result = await agent.speak_text("Hello class")
    assert result["backend"] == "offline"
    assert agent.spoken == ["Hello class"]
    assert agent.connected is True


def test_build_defaults_to_offline_without_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    agent = build_voice_agent(use_xai=True, instructions="hi")
    assert isinstance(agent, OfflineVoiceAgent)


def test_build_xai_when_keyed(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    agent = build_voice_agent(use_xai=True)
    assert isinstance(agent, XaiVoiceAgent)
    assert agent.api_key == "test-key"
    assert "realtime" in agent.ws_url


@pytest.mark.asyncio
async def test_xai_speak_text_collects_done(monkeypatch):
    class FakeWS:
        def __init__(self):
            self.sent = []
            self._replies = [
                json.dumps({"type": "response.output_audio.delta", "delta": "AA=="}),
                json.dumps(
                    {
                        "type": "response.output_audio_transcript.delta",
                        "delta": "Welcome",
                    }
                ),
                json.dumps({"type": "response.done"}),
            ]
            self._i = 0

        async def send(self, data):
            self.sent.append(json.loads(data))

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i >= len(self._replies):
                raise StopAsyncIteration
            item = self._replies[self._i]
            self._i += 1
            return item

        async def close(self):
            return None

    fake = FakeWS()
    agent = XaiVoiceAgent(api_key="k", instructions="You are Theodore.")

    async def _connect():
        return fake

    monkeypatch.setattr(agent, "_connect_ws", _connect)
    result = await agent.speak_text("Say hello")
    assert result["text"] == "Welcome"
    assert result["audio_chunks"] == 1
    types = [m["type"] for m in fake.sent]
    assert "session.update" in types
    assert "conversation.item.create" in types
    assert "response.create" in types
    await agent.close()
