"""Song catalog: 100+ original educational tracks + import helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

# Platform languages (26+) — mirrors aoep_shared.languages when available.
MEANING_LANGUAGES: tuple[str, ...] = (
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

_LANG_LABEL = {
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


class SongLine(BaseModel):
    line_no: int
    text: str
    meaning_en: str = ""
    tts_text: str = ""


class Song(BaseModel):
    song_id: str
    language: str = "en"
    title_en: str
    topic: str = "general"
    style: str = "suno-educational-original"
    license: str = "original-salareen"
    source: str = "ai-generated-educational"
    lines: list[SongLine] = Field(default_factory=list)

    @property
    def line_count(self) -> int:
        return len(self.lines)


def _default_data_path() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent.parent / "data" / "songs.jsonl"


def load_songs(path: Optional[os.PathLike[str] | str] = None) -> list[Song]:
    p = Path(path) if path else _default_data_path()
    if not p.is_file():
        return []
    out: list[Song] = []
    with p.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            lines_raw = rec.get("lines") or rec.get("verses") or []
            lines: list[SongLine] = []
            for i, row in enumerate(lines_raw, start=1):
                if isinstance(row, str):
                    lines.append(SongLine(line_no=i, text=row, meaning_en=row, tts_text=row))
                    continue
                text = str(row.get("text") or row.get("target") or row.get("en") or "").strip()
                if not text:
                    continue
                meaning = str(row.get("meaning_en") or row.get("en") or text)
                tts = str(row.get("tts_text") or text)
                lines.append(
                    SongLine(
                        line_no=int(row.get("line_no") or row.get("verse_no") or i),
                        text=text,
                        meaning_en=meaning,
                        tts_text=tts,
                    )
                )
            if not lines:
                continue
            out.append(
                Song(
                    song_id=str(rec.get("song_id") or rec.get("id") or f"import-{len(out)+1}"),
                    language=str(rec.get("language") or "en"),
                    title_en=str(rec.get("title_en") or rec.get("title") or "Untitled"),
                    topic=str(rec.get("topic") or "general"),
                    style=str(rec.get("style") or "suno-educational-original"),
                    license=str(rec.get("license") or "original-salareen"),
                    source=str(rec.get("source") or "imported"),
                    lines=lines,
                )
            )
    return out


def import_songs(records: Iterable[dict[str, Any]]) -> list[Song]:
    """Validate and normalize imported original song packs (no copyrighted lyrics)."""
    songs: list[Song] = []
    for rec in records:
        license_ = str(rec.get("license") or "").lower()
        if license_ and "copyright" in license_ and "original" not in license_:
            raise ValueError(
                f"Refusing import of '{rec.get('song_id')}': "
                "only original/educational licenses are allowed in this lab"
            )
        lines_raw = rec.get("lines") or rec.get("verses") or []
        if not lines_raw:
            raise ValueError(f"Song '{rec.get('song_id')}' has no lines")
        songs.append(
            Song(
                song_id=str(rec["song_id"]),
                language=str(rec.get("language") or "en"),
                title_en=str(rec.get("title_en") or rec["song_id"]),
                topic=str(rec.get("topic") or "general"),
                style=str(rec.get("style") or "imported"),
                license=str(rec.get("license") or "original-salareen"),
                source=str(rec.get("source") or "import"),
                lines=[
                    SongLine(
                        line_no=int(row.get("line_no") or i),
                        text=str(row["text"]),
                        meaning_en=str(row.get("meaning_en") or row["text"]),
                        tts_text=str(row.get("tts_text") or row["text"]),
                    )
                    for i, row in enumerate(lines_raw, start=1)
                ],
            )
        )
    return songs


def meaning_for_line(line: SongLine, target_lang: str) -> dict[str, Any]:
    """Best-effort meaning/translation hint for 26+ languages (offline)."""
    code = (target_lang or "en").strip().lower()
    if code not in MEANING_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{target_lang}'. "
            f"Supported: {', '.join(MEANING_LANGUAGES)}"
        )
    en = (line.meaning_en or line.text).strip()
    label = _LANG_LABEL.get(code, code)
    if code == "en":
        text = en
        note = "English gloss"
    else:
        # Offline lab: structured gloss rather than machine translation API.
        text = f"[{label}] Meaning: {en}"
        note = (
            "Offline educational gloss — production may swap in neural MT; "
            "facts stay grounded in the English meaning."
        )
    return {
        "target_language": code,
        "target_language_name": label,
        "text": text,
        "meaning_en": en,
        "note": note,
    }


class Catalog:
    def __init__(self, songs: Optional[list[Song]] = None) -> None:
        self._songs = list(songs) if songs is not None else load_songs()
        self._by_id = {s.song_id: s for s in self._songs}

    @property
    def songs(self) -> list[Song]:
        return list(self._songs)

    def get(self, song_id: str) -> Song:
        song = self._by_id.get(song_id)
        if song is None:
            raise KeyError(song_id)
        return song

    def list(
        self, *, language: str = "", topic: str = "", limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._songs
        if language:
            code = language.strip().lower()
            rows = [s for s in rows if s.language == code]
        if topic:
            t = topic.strip().lower()
            rows = [s for s in rows if s.topic.lower() == t]
        return [
            {
                "song_id": s.song_id,
                "language": s.language,
                "title_en": s.title_en,
                "topic": s.topic,
                "style": s.style,
                "license": s.license,
                "line_count": s.line_count,
            }
            for s in rows[: max(1, limit)]
        ]

    def extend(self, songs: list[Song]) -> int:
        added = 0
        for song in songs:
            if song.song_id in self._by_id:
                continue
            self._songs.append(song)
            self._by_id[song.song_id] = song
            added += 1
        return added
