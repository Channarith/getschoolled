"""ElevenLabs TTS client: voice resolution + request shaping (HTTP mocked)."""

from __future__ import annotations

import json

import pytest

from aoep_shared import elevenlabs_tts as el


def test_configured_reads_key():
    assert el.elevenlabs_configured("sk-abc") is True
    assert el.elevenlabs_configured("") is False
    assert el.elevenlabs_configured("   ") is False


def test_voice_id_precedence(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_WARM", raising=False)
    # Built-in style map.
    assert el.voice_id_for("standard") == el._STYLE_VOICES["standard"]
    assert el.voice_id_for("warm") == el._STYLE_VOICES["warm"]
    # Unknown style -> default.
    assert el.voice_id_for("nope") == el.DEFAULT_VOICE_ID
    # Global env override.
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "global-voice")
    assert el.voice_id_for("standard") == "global-voice"
    # Per-style env beats global.
    monkeypatch.setenv("ELEVENLABS_VOICE_WARM", "warm-voice")
    assert el.voice_id_for("warm") == "warm-voice"
    # Explicit override beats everything.
    assert el.voice_id_for("warm", override="explicit") == "explicit"


def test_synthesize_shapes_request_and_returns_audio(monkeypatch):
    captured = {}

    def fake_post(url, *, data, headers, timeout):
        captured["url"] = url
        captured["data"] = json.loads(data.decode("utf-8"))
        captured["headers"] = headers
        return b"\xff\xfb" + b"0" * 4000  # fake mp3 bytes

    monkeypatch.setattr(el, "_http_post", fake_post)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    audio = el.synthesize("Hello world", api_key="sk-xyz", language="es", style="warm")
    assert audio.startswith(b"\xff\xfb") and len(audio) > 256
    # Voice id in the URL path.
    assert captured["url"].endswith(f"/{el._STYLE_VOICES['warm']}")
    # Auth + accept headers.
    assert captured["headers"]["xi-api-key"] == "sk-xyz"
    assert captured["headers"]["Accept"] == "audio/mpeg"
    # Body: text + multilingual model + voice settings.
    assert captured["data"]["text"] == "Hello world"
    assert captured["data"]["model_id"] == el.DEFAULT_MODEL
    assert "voice_settings" in captured["data"]


def test_synthesize_requires_text_and_key(monkeypatch):
    monkeypatch.setattr(el, "_http_post", lambda *a, **k: b"x" * 4000)
    with pytest.raises(el.ElevenLabsError):
        el.synthesize("", api_key="sk-xyz")
    with pytest.raises(el.ElevenLabsError):
        el.synthesize("hi", api_key="")


def test_synthesize_rejects_empty_audio(monkeypatch):
    monkeypatch.setattr(el, "_http_post", lambda *a, **k: b"")
    with pytest.raises(el.ElevenLabsError):
        el.synthesize("hi", api_key="sk-xyz")
