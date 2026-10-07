"""edge-tts retries a direct connection when the process proxy refuses speech."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from aoep_shared import edge_speech
from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.lab_tts import _EDGE_VOICES
from aoep_shared.meeting.natural_tts import neural_voice_for


def _patch_communicate(monkeypatch, comm_cls) -> None:
    """Install a fake edge_tts so the retry tests do not need the package.

    CI installs aoep-shared[test,harvest]. edge-tts is the presenter extra, so
    monkeypatch.setattr("edge_tts.Communicate", ...) fails with ModuleNotFoundError.
    """
    module = types.ModuleType("edge_tts")
    module.Communicate = comm_cls
    monkeypatch.setitem(sys.modules, "edge_tts", module)


def test_every_language_has_a_non_english_lab_voice():
    for code in SUPPORTED_LANGUAGES:
        voice = _EDGE_VOICES[code]
        assert voice.endswith("Neural")
        if code != "en":
            assert not voice.startswith("en-"), code


def test_render_retries_direct_when_the_proxy_refuses(monkeypatch):
    calls: list[str | None] = []

    class FakeComm:
        def __init__(self, text, voice, *, rate, pitch, volume, proxy):
            calls.append(proxy)
            self.proxy = proxy

        async def stream(self):
            if self.proxy:
                raise RuntimeError("403 Forbidden tunnel")
            yield {"type": "audio", "data": b"ID3khmer"}

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    _patch_communicate(monkeypatch, FakeComm)
    audio = asyncio.run(
        edge_speech.render_edge_mp3("សួស្តី", voice="km-KH-SreymomNeural")
    )
    assert audio == b"ID3khmer"
    assert calls == ["http://127.0.0.1:9", None]


def test_render_does_not_retry_when_no_proxy_is_configured(monkeypatch):
    for key in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(key, raising=False)
    calls: list[str | None] = []

    class FakeComm:
        def __init__(self, text, voice, *, rate, pitch, volume, proxy):
            calls.append(proxy)

        async def stream(self):
            if self:
                raise RuntimeError("dns failed")
            yield {"type": "audio", "data": b""}

    _patch_communicate(monkeypatch, FakeComm)
    with pytest.raises(RuntimeError, match="dns failed"):
        asyncio.run(edge_speech.render_edge_mp3("hello", voice="en-US-AriaNeural"))
    assert calls == [None]


def test_male_and_female_neural_voices_stay_in_language():
    for code in SUPPORTED_LANGUAGES:
        female = neural_voice_for(code, gender="female")
        male = neural_voice_for(code, gender="male")
        assert female.endswith("Neural")
        assert male.endswith("Neural")
        if code != "en":
            assert not female.startswith("en-")
            assert not male.startswith("en-")
