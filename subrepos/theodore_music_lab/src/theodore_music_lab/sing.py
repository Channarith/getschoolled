"""Sing-along in the learner's language.

The featured MP3s are sung in English. This builds a "sing plan": for every
lyric line, the translated text plus the exact window it has to be spoken in,
the BCP-47 voice tag a browser/OS speech engine needs, and a speaking rate that
makes the sentence fit that window. The player speaks each line at its start
with the English track ducked to a backing-track level, so the same recording
carries any of the 27 languages.

Rate fitting is deliberately simple: every language has a rough
characters-per-second budget at rate 1.0 (Chinese/Japanese pack far more meaning
per character than Spanish), so rate = chars / (cps * seconds), clamped to a
range that still sounds like speech instead of a chipmunk.
"""

from __future__ import annotations

import re
from typing import Any

from .catalog import Song
from . import timing
from .translations import language_name, translate_song, validate_language

# What a neutral voice gets through in one second at rate 1.0.
_CHARS_PER_SECOND: dict[str, float] = {
    "zh": 5.0,
    "ja": 6.0,
    "ko": 7.0,
    "th": 9.0,
    "km": 9.0,
    "hi": 11.0,
    "bn": 11.0,
    "ar": 12.0,
    "he": 12.0,
    "fa": 12.0,
    "ur": 12.0,
    "ru": 13.0,
    "uk": 13.0,
    "el": 13.0,
    "pl": 13.0,
    "cs": 13.0,
}
_DEFAULT_CHARS_PER_SECOND = 14.0

# Speech engines pick a voice from a full locale tag, not a bare language code.
VOICE_TAGS: dict[str, str] = {
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-BR",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "ru": "ru-RU",
    "uk": "uk-UA",
    "tr": "tr-TR",
    "ar": "ar-SA",
    "he": "he-IL",
    "hi": "hi-IN",
    "bn": "bn-IN",
    "ur": "ur-PK",
    "fa": "fa-IR",
    "zh": "zh-CN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "vi": "vi-VN",
    "th": "th-TH",
    "id": "id-ID",
    "sw": "sw-KE",
    "el": "el-GR",
    "cs": "cs-CZ",
    "km": "km-KH",
}

# Below ~0.85 a voice drones; a short line simply finishes early instead.
MIN_RATE = 0.85
MAX_RATE = 1.8

_ROMANIZATION = re.compile(r"\s*\([^()]*\)")


def voice_tag(language: str) -> str:
    return VOICE_TAGS.get(language, language)


def speakable(text: str) -> str:
    """Drop the romanization hints a lexicon gloss shows on screen.

    "你好 (nǐ hǎo) · 朋友 (péngyou)" reads well but a Chinese voice would also
    pronounce the pinyin, so speech gets "你好, 朋友".
    """
    without_hints = _ROMANIZATION.sub("", text or "")
    parts = [part.strip() for part in without_hints.split("\u00b7")]
    return ", ".join(part for part in parts if part).strip()


def chars_per_second(language: str) -> float:
    return _CHARS_PER_SECOND.get(language, _DEFAULT_CHARS_PER_SECOND)


def speech_rate(text: str, seconds: float, language: str = "en") -> float:
    """Rate that makes ``text`` fit ``seconds`` for a rate-1.0 voice."""
    chars = len((text or "").strip())
    if chars <= 0 or seconds <= 0:
        return 1.0
    natural = chars / chars_per_second(language)
    rate = natural / seconds
    return round(min(MAX_RATE, max(MIN_RATE, rate)), 2)


def sing_plan(
    song: Song,
    language: str,
    *,
    duration_sec: float | None = None,
    allow_llm: bool = True,
    backing_volume: float = 0.22,
) -> dict[str, Any]:
    """Per-line text, window, voice tag and rate for singing in ``language``."""
    lang = validate_language(language)
    timings = timing.song_timings(song, duration_sec=duration_sec)
    rows = {row["line_no"]: row for row in timings["lines"]}
    translation = translate_song(song, lang, allow_llm=allow_llm)

    lines: list[dict[str, Any]] = []
    crowded = 0
    for row in translation["lines"]:
        window = rows.get(row["line_no"])
        if not window:
            continue
        seconds = max(0.0, float(window["end"]) - float(window["start"]))
        text = (row["translation"] or row["text"]).strip()
        spoken = speakable(text) or row["text"].strip()
        rate = speech_rate(spoken, seconds, lang)
        # At MAX_RATE the sentence still overruns its line; the player lets it
        # finish over the next line instead of cutting a word in half.
        natural = len(spoken) / chars_per_second(lang) if spoken else 0.0
        fits = natural <= seconds * MAX_RATE
        if not fits:
            crowded += 1
        lines.append(
            {
                "line_no": row["line_no"],
                "section": row.get("section", ""),
                "start": round(float(window["start"]), 3),
                "end": round(float(window["end"]), 3),
                "seconds": round(seconds, 3),
                "text": row["text"],
                "sing": text,
                "speak": spoken,
                "tier": row.get("tier", ""),
                "rate": rate,
                "fits": fits,
            }
        )
    return {
        "song_id": song.song_id,
        "title": song.title_en,
        "language": lang,
        "language_name": language_name(lang),
        "voice_tag": voice_tag(lang),
        "chars_per_second": chars_per_second(lang),
        "duration_sec": timings["duration_sec"],
        "line_count": len(lines),
        "crowded_lines": crowded,
        "backing_volume": round(max(0.0, min(1.0, backing_volume)), 2),
        "word_by_word": all(row["tier"] == "lexicon" for row in lines) if lines else False,
        "lines": lines,
    }
