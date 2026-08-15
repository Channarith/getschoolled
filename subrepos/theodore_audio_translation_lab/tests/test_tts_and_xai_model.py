"""Theodore must be audible, and an xAI failure must say why.

Two real outages motivated these tests:

1. Translation and Theodore replies both died with a bare
   "HTTP Error 400: Bad Request" on a valid API key, because the default model
   was ``grok-2-1212`` — retired from the xAI API in January 2026. urllib drops
   the response body, so xAI's own explanation never reached the operator.
2. Theodore only ever spoke through the browser's ``speechSynthesis``, which has
   no usable voice for most of the lab's 27 languages, so replies were silent or
   robotic with nothing in the UI admitting it.
"""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from theodore_audio_translation_lab import tts
from theodore_audio_translation_lab.main import app
from theodore_audio_translation_lab.providers import (
    XAI_DEFAULT_MODEL,
    ProviderUnavailable,
    TranslationEngine,
    xai_chat,
)
from theodore_audio_translation_lab.theodore import TheodoreReplyEngine

client = TestClient(app)

_TTS_ENV = (
    "TTS_BASE_URL",
    "SPEECH_BASE_URL",
    "ELEVENLABS_API_KEY",
    "TRANSLATION_BASE_URL",
    "XAI_API_KEY",
    "XAI_MODEL",
)


def _clear(monkeypatch):
    for key in _TTS_ENV:
        monkeypatch.delenv(key, raising=False)


class _Resp:
    def __init__(self, payload: dict) -> None:
        self.buf = BytesIO(json.dumps(payload).encode())

    def read(self):
        return self.buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


# --------------------------------------------------------------- retired model
def test_default_model_is_not_the_retired_grok_2(monkeypatch):
    """grok-2-1212 was removed from the xAI API; defaulting to it 400s on a
    perfectly valid key."""
    _clear(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    assert XAI_DEFAULT_MODEL != "grok-2-1212"
    assert not XAI_DEFAULT_MODEL.startswith("grok-2")
    assert TranslationEngine().xai_model == XAI_DEFAULT_MODEL
    assert TheodoreReplyEngine().model == XAI_DEFAULT_MODEL


def test_blank_xai_model_env_does_not_defeat_the_default(monkeypatch):
    """An exported-but-empty XAI_MODEL used to win over the default and send an
    empty model string."""
    _clear(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("XAI_MODEL", "   ")
    assert TranslationEngine().xai_model == XAI_DEFAULT_MODEL


def test_xai_http_error_reports_the_response_body_and_model(monkeypatch):
    """The 400 body is the only place xAI explains itself, so it must survive."""

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error":"The model grok-2-1212 does not exist"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(ProviderUnavailable) as caught:
        xai_chat(
            base_url="https://api.x.ai/v1",
            api_key="test-key",
            model="grok-2-1212",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.1,
            max_tokens=10,
            timeout_s=5,
        )
    message = str(caught.value)
    assert "does not exist" in message, "xAI's explanation was swallowed"
    assert "grok-2-1212" in message, "the failing model must be named"
    assert XAI_DEFAULT_MODEL in message, "the fix should be suggested inline"


def test_translation_warning_names_the_model_problem(monkeypatch):
    """End to end: the user-visible warning must carry the real cause."""
    _clear(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {},
            BytesIO(b'{"error":"model not found"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = TranslationEngine().translate("Open-ended sentence", "en", "fr")
    assert result.translated is False
    assert "model not found" in result.warning
    assert "HTTP Error 400: Bad Request" not in result.warning


def test_successful_translation_uses_the_current_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    captured = {}

    def fake(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _Resp({"choices": [{"message": {"content": "Bonjour"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = TranslationEngine().translate("Hello there friend", "en", "fr")
    assert result.text == "Bonjour"
    assert captured["body"]["model"] == XAI_DEFAULT_MODEL


# ------------------------------------------------------------------ Theodore audio
def test_tts_status_is_honest_when_nothing_is_configured(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr(tts, "_edge_tts_available", lambda: False)
    status = tts.tts_status()
    assert status["available"] is False
    assert status["engines"] == []
    assert "device voice" in status["note"]


def test_tts_prefers_the_speech_gateway(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SPEECH_BASE_URL", "http://speech:8002")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    captured = {}

    class _Audio:
        headers = {"Content-Type": "audio/mpeg"}

        def read(self):
            return b"ID3" + b"\0" * 400

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Audio()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    audio, mime, engine = tts.synthesize("Hello class", language="en")
    assert engine == "speech-gateway"
    assert mime == "audio/mpeg"
    assert len(audio) > 256
    assert captured["url"] == "http://speech:8002/tts"
    assert captured["body"]["language"] == "en"


def test_tts_falls_through_to_the_next_engine(monkeypatch):
    """A dead gateway must not stop ElevenLabs from being tried."""
    _clear(monkeypatch)
    monkeypatch.setenv("SPEECH_BASE_URL", "http://speech:8002")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    calls = []

    class _Audio:
        def read(self):
            return b"ID3" + b"\0" * 400

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake(req, timeout=None):
        calls.append(req.full_url)
        if "speech:8002" in req.full_url:
            raise urllib.error.URLError("connection refused")
        return _Audio()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    _audio, _mime, engine = tts.synthesize("Hello class", language="km")
    assert engine == "elevenlabs"
    assert any("elevenlabs.io" in url for url in calls)


def test_tts_endpoint_returns_501_so_the_client_can_fall_back(monkeypatch):
    """501, not 500: the page needs to tell "speak it yourself" from a crash."""
    _clear(monkeypatch)
    monkeypatch.setattr(tts, "_edge_tts_available", lambda: False)
    res = client.get("/api/tts", params={"text": "Hello", "language": "en"})
    assert res.status_code == 501
    assert "device voice" in res.json()["detail"] or "TTS_BASE_URL" in res.json()["detail"]


def test_tts_endpoint_serves_audio_with_the_engine_named(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr(
        tts, "synthesize", lambda *a, **k: (b"ID3" + b"\0" * 400, "audio/mpeg", "edge-tts")
    )
    res = client.get("/api/tts", params={"text": "Hello", "language": "en"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("audio/mpeg")
    assert res.headers["X-TTS-Engine"] == "edge-tts"
    assert len(res.content) > 256


def test_empty_tts_text_is_rejected(monkeypatch):
    _clear(monkeypatch)
    assert client.get("/api/tts", params={"text": "  "}).status_code == 422


def test_theodore_status_names_the_model_and_voice(monkeypatch):
    """The operator cannot read XAI_MODEL from a browser, so status must show it."""
    body = client.get("/api/theodore/status").json()
    assert body["xai_model"]
    assert not body["xai_model"].startswith("grok-2")
    assert "speech" in body and "available" in body["speech"]


def test_page_prefers_server_audio_then_device_voice():
    page = client.get("/lab").text
    assert "/api/tts/status" in page
    assert "loadTtsStatus" in page
    # Server audio first, device voice only as the fallback.
    assert "if(serverTts.available)" in page
    assert "SpeechSynthesisUtterance" in page
    assert "device voice" in page
    # 501 must downgrade rather than throw.
    assert "res.status===501" in page
    # Replay + stop, and auto-reply on by default so Theodore actually talks.
    assert 'id="replay-theodore"' in page
    assert 'id="stop-theodore-audio"' in page
    assert 'id="theodore-auto" type="checkbox" checked' in page
