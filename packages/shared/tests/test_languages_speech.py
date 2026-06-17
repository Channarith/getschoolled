"""26-language coverage and TTS fallback routing."""

import pytest

from aoep_shared.config import load_config
from aoep_shared.factory import build_factory
from aoep_shared.languages import (
    SUPPORTED_LANGUAGES,
    is_supported,
    tts_needs_fallback,
)


def test_exactly_26_supported_languages():
    assert len(SUPPORTED_LANGUAGES) == 26
    assert len(set(SUPPORTED_LANGUAGES)) == 26


def test_english_is_native_tts():
    assert is_supported("en")
    assert tts_needs_fallback("en") is False


def test_some_languages_use_fallback():
    # Swahili has weak open-voice coverage -> cloud fallback.
    assert tts_needs_fallback("sw") is True


def test_unsupported_language_raises():
    with pytest.raises(ValueError):
        tts_needs_fallback("xx")


def test_speech_provider_picks_engine_without_models():
    speech = build_factory(load_config(env={})).speech()
    assert speech.tts_engine("en") == "xtts"
    assert speech.tts_engine("sw") == "cloud-tts-fallback"
