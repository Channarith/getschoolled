"""Platform language coverage, importable standalone without aoep_shared."""

from __future__ import annotations

try:
    from aoep_shared.languages import (  # type: ignore
        LANGUAGE_NAMES as _NAMES,
        SUPPORTED_LANGUAGES as _LANGS,
        normalize_language as _normalize,
    )

    SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(_LANGS)
    LANGUAGE_NAMES: dict[str, str] = dict(_NAMES)
    SOURCE = "aoep_shared.languages"

    def normalize_language(value: str, default: str = "") -> str:
        return _normalize(value) or default

except Exception:  # noqa: BLE001 — standalone lab mode
    SUPPORTED_LANGUAGES = (
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk",
        "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko",
        "vi", "th", "id", "sw", "el", "cs", "km",
    )
    LANGUAGE_NAMES = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
        "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish", "ar": "Arabic",
        "he": "Hebrew", "hi": "Hindi", "bn": "Bengali", "ur": "Urdu",
        "fa": "Persian", "zh": "Chinese (Mandarin)", "ja": "Japanese",
        "ko": "Korean", "vi": "Vietnamese", "th": "Thai",
        "id": "Indonesian", "sw": "Swahili", "el": "Greek", "cs": "Czech",
        "km": "Khmer",
    }
    SOURCE = "embedded"

    def normalize_language(value: str, default: str = "") -> str:
        code = (value or "").strip().lower().split("-")[0]
        return code if code in SUPPORTED_LANGUAGES else default


RTL_LANGUAGES = frozenset({"ar", "he", "ur", "fa"})

# BCP-47 locales for browser/device recognizers.
BCP47: dict[str, str] = {
    "en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
    "it": "it-IT", "pt": "pt-BR", "nl": "nl-NL", "pl": "pl-PL",
    "ru": "ru-RU", "uk": "uk-UA", "tr": "tr-TR", "ar": "ar-SA",
    "he": "he-IL", "hi": "hi-IN", "bn": "bn-BD", "ur": "ur-PK",
    "fa": "fa-IR", "zh": "zh-CN", "ja": "ja-JP", "ko": "ko-KR",
    "vi": "vi-VN", "th": "th-TH", "id": "id-ID", "sw": "sw-KE",
    "el": "el-GR", "cs": "cs-CZ", "km": "km-KH",
}


def language_rows() -> list[dict]:
    return [
        {
            "code": code,
            "name": LANGUAGE_NAMES[code],
            "bcp47": BCP47[code],
            "rtl": code in RTL_LANGUAGES,
        }
        for code in SUPPORTED_LANGUAGES
    ]
