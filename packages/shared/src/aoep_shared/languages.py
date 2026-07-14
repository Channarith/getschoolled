"""Language coverage for the platform.

ASR (Whisper) and translation (NLLB-200) cover all 26 supported languages. Open
TTS voices (XTTS) do not cover every language, so a subset is routed to a
cloud-TTS fallback. This module is the single source of truth for both sets.
"""

from __future__ import annotations

# 27 supported languages (ISO 639-1 where available). ASR + translation cover
# all of these. Khmer (km) added because the brand "Salareen" derives from the
# Khmer word for school (sala-rian), so first-class Khmer support is a brand
# requirement, not a stretch goal.
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk",
    "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko",
    "vi", "th", "id", "sw", "el", "cs", "km",
)

# Languages with solid open TTS voice coverage (XTTS-v2). The remainder use the
# cloud-TTS fallback regardless of deploy mode. Khmer is not in XTTS-v2 voice
# coverage as of 2026 - it routes to the cloud-TTS fallback (Azure / Google /
# Polly all have native Khmer voices).
TTS_NATIVE_LANGUAGES: frozenset[str] = frozenset(
    {
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
        "tr", "ar", "zh", "ja", "ko", "hi", "cs",
    }
)


# Human-readable English names for each supported code, used to instruct the
# tutor LLM ("Respond entirely in Spanish.") and for logs/UI. Single source of
# truth so backend prompts and clients agree on what a code means.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish", "ar": "Arabic",
    "he": "Hebrew", "hi": "Hindi", "bn": "Bengali", "ur": "Urdu",
    "fa": "Persian", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "sw": "Swahili",
    "el": "Greek", "cs": "Czech", "km": "Khmer",
}


def is_supported(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES


def normalize_language(language: str) -> str:
    """Coerce a client locale (e.g. 'es-419', 'ES') to a supported base code,
    or '' when unsupported/blank. Keeps language handling forgiving of the
    varied locale strings web/mobile devices report."""
    code = (language or "").strip().lower().split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else ""


def language_name(language: str) -> str:
    """English display name for a code (e.g. 'es' -> 'Spanish'); '' if unknown."""
    return LANGUAGE_NAMES.get(normalize_language(language), "")


def tts_needs_fallback(language: str) -> bool:
    """True if ``language`` must use the cloud-TTS fallback."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    return language not in TTS_NATIVE_LANGUAGES
