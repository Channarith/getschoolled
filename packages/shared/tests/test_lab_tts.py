"""Shared lab TTS: engine chain + fail-fast disable after a dead gateway."""

from __future__ import annotations

import urllib.error

from aoep_shared import lab_tts as tts


def _clear(monkeypatch):
    for key in (
        "TTS_BASE_URL",
        "SPEECH_BASE_URL",
        "NEXT_PUBLIC_SPEECH_URL",
        "ELEVENLABS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    tts.reset_disabled_engines()


def test_status_honest_when_nothing_configured(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr(tts, "_edge_tts_available", lambda: False)
    status = tts.tts_status()
    assert status["available"] is False
    assert status["engines"] == []


def test_dead_gateway_is_disabled_so_retry_skips_timeout(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SPEECH_BASE_URL", "http://speech:8002")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    calls = []

    class _Audio:
        headers = {"Content-Type": "audio/mpeg"}

        def read(self):
            return b"ID3" + b"\0" * 400

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def fake(req, timeout=None):
        calls.append(req.full_url)
        if "speech:8002" in req.full_url:
            raise urllib.error.URLError("connection refused")
        return _Audio()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    _a, _m, engine = tts.synthesize("Hello", language="en")
    assert engine == "elevenlabs"
    assert "speech-gateway" in tts._disabled_engines

    calls.clear()
    _a, _m, engine2 = tts.synthesize("Again", language="en")
    assert engine2 == "elevenlabs"
    assert not any("speech:8002" in u for u in calls)
