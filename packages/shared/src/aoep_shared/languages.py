"""Language coverage for the platform.

ASR (Whisper) and translation (NLLB-200) cover all 26 supported languages. Open
TTS voices (XTTS) do not cover every language, so a subset is routed to a
cloud-TTS fallback. This module is the single source of truth for both sets.
"""

from __future__ import annotations

# 26 supported languages (ISO 639-1 where available). ASR + translation cover
# all of these.
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk",
    "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko",
    "vi", "th", "id", "sw", "el", "cs",
)

# Languages with solid open TTS voice coverage (XTTS-v2). The remainder use the
# cloud-TTS fallback regardless of deploy mode.
TTS_NATIVE_LANGUAGES: frozenset[str] = frozenset(
    {
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
        "tr", "ar", "zh", "ja", "ko", "hi", "cs",
    }
)


def is_supported(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES


def tts_needs_fallback(language: str) -> bool:
    """True if ``language`` must use the cloud-TTS fallback."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    return language not in TTS_NATIVE_LANGUAGES
