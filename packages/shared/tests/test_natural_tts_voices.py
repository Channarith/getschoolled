"""Edge-tts neural voice map covers every supported language (incl. Khmer)."""

from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.meeting.natural_tts import (
    DEFAULT_NEURAL_VOICE,
    neural_voice_for,
)


def test_every_supported_language_has_a_native_neural_voice():
    for code in SUPPORTED_LANGUAGES:
        voice = neural_voice_for(code)
        assert "Neural" in voice
        assert voice != DEFAULT_NEURAL_VOICE or code == "en"
        # Must not silently pick an English voice for a non-English language.
        if code != "en":
            assert not voice.startswith("en-"), f"{code} resolved to {voice}"


def test_khmer_uses_sreymom_not_english_aria():
    assert neural_voice_for("km") == "km-KH-SreymomNeural"
    assert neural_voice_for("km", gender="male") == "km-KH-PisethNeural"
    assert neural_voice_for("km-KH") == "km-KH-SreymomNeural"


def test_explicit_neural_voice_wins():
    assert neural_voice_for("km", voice="en-US-GuyNeural") == "en-US-GuyNeural"
