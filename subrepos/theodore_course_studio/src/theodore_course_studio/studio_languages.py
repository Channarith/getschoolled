"""Platform language coverage for Theodore Course Studio.

Mirrors ``aoep_shared.languages`` (27 codes). Falls back to an embedded copy so
the experiment lab stays importable offline without the shared package on
PYTHONPATH.
"""

from __future__ import annotations

from typing import Any

try:
    from aoep_shared.languages import (  # type: ignore
        LANGUAGE_NAMES as _SHARED_NAMES,
        SUPPORTED_LANGUAGES as _SHARED_LANGS,
        language_name as _shared_language_name,
        normalize_language as _shared_normalize,
        tts_needs_fallback as _shared_tts_needs_fallback,
    )

    SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(_SHARED_LANGS)
    LANGUAGE_NAMES: dict[str, str] = dict(_SHARED_NAMES)

    def normalize_language(language: str) -> str:
        return _shared_normalize(language) or "en"

    def language_name(language: str) -> str:
        return _shared_language_name(language) or LANGUAGE_NAMES.get(
            normalize_language(language), "English"
        )

    def tts_needs_fallback(language: str) -> bool:
        code = normalize_language(language)
        try:
            return bool(_shared_tts_needs_fallback(code))
        except Exception:  # noqa: BLE001
            return code not in {
                "en",
                "es",
                "fr",
                "de",
                "it",
                "pt",
                "nl",
                "pl",
                "ru",
                "tr",
                "ar",
                "zh",
                "ja",
                "ko",
                "hi",
                "cs",
            }

    SOURCE = "aoep_shared.languages"
except Exception:  # noqa: BLE001 — offline / missing shared package
    SUPPORTED_LANGUAGES = (
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "nl",
        "pl",
        "ru",
        "uk",
        "tr",
        "ar",
        "he",
        "hi",
        "bn",
        "ur",
        "fa",
        "zh",
        "ja",
        "ko",
        "vi",
        "th",
        "id",
        "sw",
        "el",
        "cs",
        "km",
    )
    LANGUAGE_NAMES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "pl": "Polish",
        "ru": "Russian",
        "uk": "Ukrainian",
        "tr": "Turkish",
        "ar": "Arabic",
        "he": "Hebrew",
        "hi": "Hindi",
        "bn": "Bengali",
        "ur": "Urdu",
        "fa": "Persian",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "vi": "Vietnamese",
        "th": "Thai",
        "id": "Indonesian",
        "sw": "Swahili",
        "el": "Greek",
        "cs": "Czech",
        "km": "Khmer",
    }
    _TTS_NATIVE = frozenset(
        {
            "en",
            "es",
            "fr",
            "de",
            "it",
            "pt",
            "nl",
            "pl",
            "ru",
            "tr",
            "ar",
            "zh",
            "ja",
            "ko",
            "hi",
            "cs",
        }
    )
    SOURCE = "embedded"

    def normalize_language(language: str) -> str:
        code = (language or "").strip().lower().split("-")[0]
        return code if code in SUPPORTED_LANGUAGES else "en"

    def language_name(language: str) -> str:
        return LANGUAGE_NAMES.get(normalize_language(language), "English")

    def tts_needs_fallback(language: str) -> bool:
        return normalize_language(language) not in _TTS_NATIVE


RTL_LANGUAGES = frozenset({"ar", "he", "ur", "fa"})


def list_languages() -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "name": LANGUAGE_NAMES.get(code, code),
            "rtl": code in RTL_LANGUAGES,
            "tts_needs_fallback": tts_needs_fallback(code),
        }
        for code in SUPPORTED_LANGUAGES
    ]


def language_instruction(language: str) -> str:
    raw = (language or "").strip().lower().replace("_", "-")
    if raw == "km" or raw.startswith("km-"):
        return (
            "Respond entirely in Khmer (Cambodian, km), the language of Cambodia. "
            "Do not respond in Thai. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if (
        raw in {"yue", "zh-hk", "zh-mo", "zh-yue", "cantonese"}
        or raw.startswith("yue-")
        or raw.startswith("zh-hk")
        or raw.startswith("zh-yue")
    ):
        return (
            "Respond entirely in Hong Kong Cantonese (粵語, yue), the language of "
            "Hong Kong and Guangdong. Do not respond in Mandarin. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    name = language_name(language)
    code = normalize_language(language)
    if code == "zh" or raw in {"zh", "zh-cn", "zh-hans", "cmn", "mandarin"}:
        return (
            "Respond entirely in Mandarin Chinese (普通话, zh). "
            "Do not respond in Cantonese. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if code == "en" and name == "British English":
        return (
            "Respond in British English. Use British vocabulary and pronunciation, "
            "not American English. Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if code == "en" and name == "Australian English":
        return (
            "Respond in Australian English. Use Australian vocabulary and pronunciation, "
            "not American English. Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if code == "en" and name == "Singapore English":
        return (
            "Respond in Singapore English (Singlish) with a clear teaching tone. "
            "Light particles such as lah and can are fine. Do not speak American English. "
            "Keep the tone warm, concise, and suitable for spoken tutoring."
        )
    if code == "en":
        return "Respond in clear, spoken English."
    return (
        f"Respond entirely in {name} ({code}). "
        "Keep the tone warm, concise, and suitable for spoken tutoring."
    )
