"""CosyVoice 2 TTS client (aoep_shared.cosyvoice_tts)."""

from __future__ import annotations

import json

import pytest

from aoep_shared import cosyvoice_tts


def test_configured_reflects_url(monkeypatch):
    monkeypatch.delenv("COSYVOICE_URL", raising=False)
    assert cosyvoice_tts.cosyvoice_configured() is False
    assert cosyvoice_tts.cosyvoice_configured("http://cosy:9880") is True
    monkeypatch.setenv("COSYVOICE_URL", "http://cosy:9880")
    assert cosyvoice_tts.cosyvoice_configured() is True


def test_synthesize_shapes_request_and_returns_audio(monkeypatch):
    captured = {}

    def fake_post(url, *, data, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(data.decode("utf-8"))
        return b"RIFF" + b"x" * 5000, "audio/wav"

    monkeypatch.setattr(cosyvoice_tts, "_http_post", fake_post)
    audio, ctype = cosyvoice_tts.synthesize(
        "Hello class", base_url="http://cosy:9880/", language="es",
        speaker="maria", instruct="Speak warmly and slowly.", api_key="k",
    )
    assert audio.startswith(b"RIFF") and ctype == "audio/wav"
    assert captured["url"] == "http://cosy:9880/tts"           # default path, trailing slash stripped
    assert captured["headers"]["Authorization"] == "Bearer k"
    body = captured["body"]
    assert body["text"] == "Hello class"
    assert body["language"] == "es"
    assert body["speaker"] == "maria"
    assert body["mode"] == "instruct2"                          # instruction -> instruct2 mode


def test_mode_defaults_by_inputs(monkeypatch):
    monkeypatch.delenv("COSYVOICE_MODE", raising=False)
    assert cosyvoice_tts._mode_for("say it cheerfully", "") == "instruct2"
    assert cosyvoice_tts._mode_for("", "maria") == "zero_shot"
    assert cosyvoice_tts._mode_for("", "") == "cross_lingual"
    monkeypatch.setenv("COSYVOICE_MODE", "sft")
    assert cosyvoice_tts._mode_for("anything", "maria") == "sft"   # env override wins


def test_synthesize_requires_text_and_url():
    with pytest.raises(cosyvoice_tts.CosyVoiceError):
        cosyvoice_tts.synthesize("   ", base_url="http://cosy:9880")
    with pytest.raises(cosyvoice_tts.CosyVoiceError):
        cosyvoice_tts.synthesize("hi", base_url="")


def test_synthesize_rejects_too_short_audio(monkeypatch):
    monkeypatch.setattr(cosyvoice_tts, "_http_post", lambda *a, **k: (b"tiny", "audio/wav"))
    with pytest.raises(cosyvoice_tts.CosyVoiceError):
        cosyvoice_tts.synthesize("hello", base_url="http://cosy:9880")
