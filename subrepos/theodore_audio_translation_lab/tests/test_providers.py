from __future__ import annotations

import json
from io import BytesIO

import pytest

from theodore_audio_translation_lab.providers import ASREngine, ProviderUnavailable, TranslationEngine


class _Resp:
    def __init__(self, payload: dict) -> None:
        self.buf = BytesIO(json.dumps(payload).encode())

    def read(self):
        return self.buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _clear(monkeypatch):
    for key in ("TRANSLATION_BASE_URL", "SPEECH_BASE_URL", "XAI_API_KEY", "ASR_BASE_URL", "ASR_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_identity_translation(monkeypatch):
    _clear(monkeypatch)
    result = TranslationEngine().translate("Hello", "en", "en")
    assert result.text == "Hello"
    assert result.provider == "identity"
    assert result.translated is False


def test_offline_phrasebook(monkeypatch):
    _clear(monkeypatch)
    result = TranslationEngine().translate("I need help", "en", "km")
    assert result.text == "ខ្ញុំត្រូវការជំនួយ"
    assert result.provider == "offline-phrasebook"
    assert result.translated is True


def test_unavailable_translation_is_honest(monkeypatch):
    _clear(monkeypatch)
    result = TranslationEngine().translate("Open-ended sentence", "en", "fr")
    assert result.text == "Open-ended sentence"
    assert result.provider == "source-fallback"
    assert result.translated is False
    assert "Translation unavailable" in result.warning


def test_gateway_nllb_translation(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TRANSLATION_BASE_URL", "http://speech:8002")
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Resp({"source": "es", "target": "en", "text": "Good morning"})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = TranslationEngine().translate("Buenos días", "es", "en")
    assert result.text == "Good morning"
    assert result.provider == "speech-gateway-nllb"
    assert captured["url"] == "http://speech:8002/translate"
    assert captured["body"] == {"text": "Buenos días", "source": "es", "target": "en"}


def test_xai_translation_and_cache(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    calls = {"n": 0}
    captured = {}

    def fake(req, timeout=None):
        calls["n"] += 1
        captured["auth"] = req.headers["Authorization"]
        captured["body"] = json.loads(req.data.decode())
        return _Resp({"choices": [{"message": {"content": "Bonjour"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    engine = TranslationEngine()
    first = engine.translate("Hello", "en", "fr")
    second = engine.translate("Hello", "en", "fr")
    assert first.provider == "xai"
    assert second.provider == "xai:cache"
    assert first.text == second.text == "Bonjour"
    assert calls["n"] == 1
    assert captured["auth"] == "Bearer test-key"
    assert "French" in captured["body"]["messages"][0]["content"]


def test_asr_requires_real_endpoint(monkeypatch):
    _clear(monkeypatch)
    with pytest.raises(ProviderUnavailable, match="ASR_BASE_URL"):
        ASREngine().transcribe(b"audio", filename="x.webm", content_type="audio/webm", language="en")


def test_openai_compatible_whisper_upload(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ASR_BASE_URL", "http://whisper:9000")
    monkeypatch.setenv("ASR_API_KEY", "secret")
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["auth"] = req.headers["Authorization"]
        captured["content_type"] = req.headers["Content-type"]
        captured["body"] = req.data
        return _Resp({"text": "សួស្តី", "language": "km", "confidence": 0.91})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = ASREngine().transcribe(
        b"fake-webm-bytes", filename="chunk.webm", content_type="audio/webm", language="km"
    )
    assert result.text == "សួស្តី"
    assert result.language == "km"
    assert result.provider == "openai-compatible:whisper-large-v3"
    assert captured["url"] == "http://whisper:9000/v1/audio/transcriptions"
    assert captured["auth"] == "Bearer secret"
    assert b"fake-webm-bytes" in captured["body"]
    assert b"whisper-large-v3" in captured["body"]
    assert b'name="language"' in captured["body"]
    assert b"km" in captured["body"]
