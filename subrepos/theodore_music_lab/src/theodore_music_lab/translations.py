"""Per-line lyric translation for every song, every supported language.

Four tiers, best available wins, and something real is always returned:

1. ``curated``  — reviewed hand-authored line (``curated_lines.py``).
2. ``cached``   — a previous LLM translation persisted to disk (works offline).
3. ``llm``      — Grok/xAI translation of the whole song in one request
                  (only when ``XAI_API_KEY`` is set); written to the cache.
4. ``lexicon``  — real target-language words for the line's content words
                  (``lexicon.py``), so an uncurated language is still useful.

``english`` is the final floor for lines with no lexicon coverage. No tier ever
invents a fake sentence: the tier is reported alongside the text so the UI can
badge it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .catalog import _LANG_LABEL, MEANING_LANGUAGES, Song, SongLine
from .curated_lines import CURATED_LANGUAGES, curated, curated_coverage, normalize
from .lexicon import NEEDS_NATIVE_REVIEW, coverage, vocabulary_for_line

XAI_DEFAULT_MODEL = "grok-4.3"

TIER_NOTES = {
    "english": "English source line.",
    "curated": "Reviewed human translation.",
    "cached": "Machine translation, cached locally after its first run.",
    "llm": "Machine translation (Grok) — grounded in the English line.",
    "lexicon": (
        "Key-word translation from the lab lexicon: real target-language words "
        "for this line, not a full sentence."
    ),
}


def language_name(code: str) -> str:
    return _LANG_LABEL.get(code, code)


def _cache_dir() -> Path:
    override = os.getenv("MUSIC_LAB_I18N_CACHE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "i18n_cache"


def _cache_path(song_id: str, language: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in song_id)
    return _cache_dir() / f"{safe}__{language}.json"


def _load_cache(song_id: str, language: str) -> dict[str, str]:
    path = _cache_path(song_id, language)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        lines = data.get("lines")
        if isinstance(lines, dict):
            return {str(k): str(v) for k, v in lines.items() if v}
    except (OSError, ValueError):
        return {}
    return {}


def _save_cache(song_id: str, language: str, lines: dict[str, str]) -> None:
    path = _cache_path(song_id, language)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"language": language, "lines": lines}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    except OSError:
        # A read-only filesystem must not break playback; we just lose the cache.
        pass


def _xai_translate(lines: list[str], language: str) -> dict[str, str]:
    """Translate unique English lyric lines in one Grok request ({} on failure)."""
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key or not lines:
        return {}
    base = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("XAI_MODEL", XAI_DEFAULT_MODEL).strip() or XAI_DEFAULT_MODEL
    try:
        timeout = float(os.getenv("XAI_TIMEOUT_S", "40") or 40)
    except ValueError:
        timeout = 40.0
    name = language_name(language)
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You translate lyrics from simple English language-learning songs. "
                    f"Translate each line into {name}. Keep the line short and singable, "
                    "keep the teaching vocabulary obvious, and do not add commentary. "
                    'Reply with JSON only: [{"i": <index>, "t": "<translation>"}].'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    [{"i": i, "en": text} for i, text in enumerate(lines)],
                    ensure_ascii=False,
                ),
            },
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return {}
    if content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[-1] if "\n" in content else content
    try:
        rows = json.loads(content)
    except ValueError:
        return {}
    out: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("i"))
            except (TypeError, ValueError):
                continue
            text = str(row.get("t") or "").strip()
            if text and 0 <= idx < len(lines):
                out[normalize(lines[idx])] = text
    return out


def _lexicon_line(text: str, language: str) -> tuple[str, list[dict[str, str]]]:
    vocab = vocabulary_for_line(text, language)
    words = [row["target"] for row in vocab if row["target"]]
    return " · ".join(words), vocab


def validate_language(code: str) -> str:
    lang = (code or "en").strip().lower()
    if lang not in MEANING_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{code}'. Supported: {', '.join(MEANING_LANGUAGES)}"
        )
    return lang


def translate_line(
    line: SongLine, language: str, *, cache: dict[str, str] | None = None
) -> dict[str, Any]:
    """Best available translation for one lyric line (no network on its own)."""
    lang = validate_language(language)
    text = (line.text or "").strip()
    english = (line.meaning_en or text).strip()
    vocab = vocabulary_for_line(text, lang)
    if lang == "en":
        return {
            "line_no": line.line_no,
            "text": text,
            "section": line.section,
            "translation": english,
            "meaning_en": english,
            "tier": "english",
            "note": TIER_NOTES["english"],
            "vocabulary": vocab,
        }
    translation = curated(text, lang)
    tier = "curated" if translation else ""
    if not translation and cache:
        translation = cache.get(normalize(text), "")
        tier = "cached" if translation else ""
    if not translation:
        translation, vocab = _lexicon_line(text, lang)
        tier = "lexicon" if translation else "english"
        if not translation:
            translation = english
    return {
        "line_no": line.line_no,
        "text": text,
        "section": line.section,
        "translation": translation,
        "meaning_en": english,
        "tier": tier,
        "note": TIER_NOTES[tier],
        "vocabulary": vocab,
    }


def translate_song(
    song: Song, language: str, *, allow_llm: bool = True
) -> dict[str, Any]:
    """Translate every line of a song; fills gaps via Grok once, then caches."""
    lang = validate_language(language)
    cache = _load_cache(song.song_id, lang) if lang != "en" else {}
    rows = [translate_line(line, lang, cache=cache) for line in song.lines]

    if lang != "en" and allow_llm:
        missing: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if row["tier"] in {"lexicon", "english"}:
                key = normalize(row["text"])
                if key and key not in seen:
                    seen.add(key)
                    missing.append(row["text"])
        if missing:
            fresh = _xai_translate(missing, lang)
            if fresh:
                cache.update(fresh)
                _save_cache(song.song_id, lang, cache)
                for row in rows:
                    if row["tier"] in {"lexicon", "english"}:
                        got = fresh.get(normalize(row["text"]), "")
                        if got:
                            row["translation"] = got
                            row["tier"] = "llm"
                            row["note"] = TIER_NOTES["llm"]

    tiers: dict[str, int] = {}
    for row in rows:
        tiers[row["tier"]] = tiers.get(row["tier"], 0) + 1
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "language": lang,
        "language_name": language_name(lang),
        "line_count": len(rows),
        "lines": rows,
        "tiers": tiers,
        "complete": all(r["translation"] for r in rows),
        "needs_native_review": lang in NEEDS_NATIVE_REVIEW,
        "llm_available": bool(os.getenv("XAI_API_KEY", "").strip()),
    }


def language_catalog() -> list[dict[str, Any]]:
    """All supported languages with the translation quality the lab can deliver."""
    rows: list[dict[str, Any]] = []
    for code in MEANING_LANGUAGES:
        rows.append(
            {
                "code": code,
                "name": language_name(code),
                "curated": code in CURATED_LANGUAGES or code == "en",
                "curated_coverage": curated_coverage(code),
                "lexicon_coverage": coverage(code),
                "needs_native_review": code in NEEDS_NATIVE_REVIEW,
            }
        )
    return rows
