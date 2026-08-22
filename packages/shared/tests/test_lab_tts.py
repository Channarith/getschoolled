"""Shared lab TTS: engine chain + fail-fast disable after a dead gateway."""

from __future__ import annotations

import urllib.error

import pytest

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


def test_reading_status_while_a_cooldown_lapses_does_not_explode(monkeypatch):
    """`_benched` prunes what it finds expired, so callers must not iterate live.

    Reading the bench dict directly while calling `_benched` raised
    "dictionary changed size during iteration" the moment a cooldown lapsed
    between the bench and the read — a status endpoint 500 that only appeared
    once real time had passed, which is why it survived local runs.
    """
    tts.reset_disabled_engines()
    monkeypatch.setattr(tts, "ENGINE_COOLDOWN_SEC", 10.0)
    now = [500.0]
    monkeypatch.setattr(tts.time, "monotonic", lambda: now[0])

    for engine in ("edge-tts", "elevenlabs", "speech-gateway"):
        tts._bench_engine(engine, "boom")
    assert tts.benched_engines() == ["edge-tts", "elevenlabs", "speech-gateway"]

    # Every cooldown lapses at once: the prune must not disturb the iteration.
    now[0] += 11.0
    assert tts.benched_engines() == []
    status = tts.tts_status()
    assert status["disabled"] == []
    assert status["retry_in_sec"] == 0


def test_a_benched_engine_still_reports_why_it_failed(monkeypatch):
    """Every 501 must name the real fault, not advise an install already done.

    Only the first failure could name a cause: benching the engine emptied the
    chain, so later calls attempted nothing, had no errors to report, and fell
    back to "install edge-tts" — while edge-tts was installed and the actual
    fault was that the process could not resolve the voice host. That message
    sent debugging in the wrong direction for three rounds.
    """
    tts.reset_disabled_engines()
    monkeypatch.setattr(tts, "gateway_url", lambda: "")
    monkeypatch.setattr(tts, "_elevenlabs_key", lambda: "")
    monkeypatch.setattr(tts, "_edge_tts_available", lambda: True)

    dns = "Cannot connect to host speech.platform.bing.com:443"

    def boom(*_args, **_kwargs):
        raise RuntimeError(dns)

    monkeypatch.setattr(tts, "_edge_tts", boom)

    with pytest.raises(tts.ProviderUnavailable) as first:
        tts.synthesize("hello", language="en")
    assert dns in str(first.value)

    # The engine is now benched, so this call tries nothing at all.
    with pytest.raises(tts.ProviderUnavailable) as later:
        tts.synthesize("hello again", language="en")
    message = str(later.value)
    assert dns in message, "the cause must survive the bench"
    assert "cooling off" in message
    assert "install edge-tts" not in message, "misleading when it is installed"
    assert "reach the voice service" in message
