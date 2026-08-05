from __future__ import annotations

import json

import pytest

from vision_lab.speech_chunks import SpeechChunker
from vision_lab.xai_voice import XAIConfig, XAIVoiceAgent, XAIVoiceError


class _FakeResp:
    def __init__(self, *, body: bytes = b"", lines=None):
        self._body = body
        self._lines = lines or []
        self.status = 200

    def read(self):
        return self._body

    def __iter__(self):
        return iter(self._lines)


def _patch_urlopen(monkeypatch, *, capture: dict, resp: _FakeResp):
    from vision_lab import xai_voice

    def fake_urlopen(req, timeout=None):
        capture["url"] = req.full_url
        capture["headers"] = dict(req.headers)
        capture["body"] = json.loads(req.data.decode("utf-8"))
        capture["timeout"] = timeout
        return resp

    monkeypatch.setattr(xai_voice.urllib.request, "urlopen", fake_urlopen)


def test_complete_posts_xai_openai_compatible_shape(monkeypatch):
    capture = {}
    body = json.dumps(
        {"choices": [{"message": {"content": "  Please adjust your camera. "}}]}
    ).encode()
    _patch_urlopen(monkeypatch, capture=capture, resp=_FakeResp(body=body))

    agent = XAIVoiceAgent(
        XAIConfig(
            api_key="xai-test",
            model="grok-test",
            base_url="https://xai.local/v1",
            timeout_seconds=12,
        )
    )
    text = agent.complete([{"role": "user", "content": "hello"}])

    assert text == "Please adjust your camera."
    assert capture["url"] == "https://xai.local/v1/chat/completions"
    assert capture["headers"]["Authorization"] == "Bearer xai-test"
    assert capture["body"]["model"] == "grok-test"
    assert capture["body"]["stream"] is False
    assert capture["timeout"] == 12


def test_stream_speakable_chunks_yields_low_latency_phrases(monkeypatch):
    capture = {}
    lines = [
        b'data: {"choices":[{"delta":{"content":"I can"}}]}\n',
        b'data: {"choices":[{"delta":{"content":" see you"}}]}\n',
        b'data: {"choices":[{"delta":{"content":", but adjust"}}]}\n',
        b'data: {"choices":[{"delta":{"content":" the camera please."}}]}\n',
        b"data: [DONE]\n",
    ]
    _patch_urlopen(monkeypatch, capture=capture, resp=_FakeResp(lines=lines))
    agent = XAIVoiceAgent(XAIConfig(api_key="xai-test", model="grok-test"))

    chunks = list(
        agent.stream_speakable_chunks(
            [{"role": "user", "content": "camera"}],
            chunker=SpeechChunker(),
        )
    )

    assert capture["body"]["stream"] is True
    assert chunks[0] == "I can see"
    assert chunks[-1].endswith("please.")


def test_missing_api_key_fails_before_network():
    agent = XAIVoiceAgent(XAIConfig(api_key=""))
    with pytest.raises(XAIVoiceError):
        agent.complete([{"role": "user", "content": "hello"}])
