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
    assert tts._benched("speech-gateway")

    calls.clear()
    _a, _m, engine2 = tts.synthesize("Again", language="en")
    assert engine2 == "elevenlabs"
    assert not any("speech:8002" in u for u in calls)


def test_a_benched_engine_comes_back_after_its_cooldown(monkeypatch):
    """A single blip must not kill neural speech for the life of the process.

    The bench exists so a dead gateway is not re-waited on for every line, but
    it used to be permanent: a lab started before the network was up answered
    501 forever, reporting available=false with no way back but a restart.
    """
    tts.reset_disabled_engines()
    monkeypatch.setattr(tts, "ENGINE_COOLDOWN_SEC", 30.0)
    now = [1000.0]
    monkeypatch.setattr(tts.time, "monotonic", lambda: now[0])

    tts._bench_engine("edge-tts")
    assert tts._benched("edge-tts") is True

    now[0] += 29.0
    assert tts._benched("edge-tts") is True, "should still be cooling off"

    now[0] += 2.0
    assert tts._benched("edge-tts") is False, "should be retried after cooldown"
