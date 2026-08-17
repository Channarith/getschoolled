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
    section: str = ""  # verse / chorus / bridge / …
    # Hand-tuned karaoke timings; when unset they are estimated in timing.py.
    start_sec: float | None = None
    end_sec: float | None = None


class Song(BaseModel):
    song_id: str
    language: str = "en"
    title_en: str
    topic: str = "general"
    style: str = "suno-educational-original"
    license: str = "original-salareen"
    source: str = "ai-generated-educational"
    lines: list[SongLine] = Field(default_factory=list)
    # Optional MP3 + motion theme for the player UI (featured pack).
    audio_file: str = ""
    animation: str = "pulse"  # travel | bus | words | pulse
    featured: bool = False
    duration_hint_sec: float | None = None
    # Instrumental intro before the first sung line, and trailing outro.
    lead_in_sec: float = 0.0
    tail_sec: float = 0.0

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def audio_url(self) -> str:
        if not self.audio_file:
            return ""
        name = Path(self.audio_file).name
        return f"/api/music/audio/{name}"



def _default_data_path() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent.parent / "data" / "songs.jsonl"


def _featured_data_path() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent.parent / "data" / "featured_songs.jsonl"


def _audio_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent.parent / "data" / "audio"


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _song_from_record(rec: dict[str, Any], *, fallback_id: str) -> Song | None:
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
                section=str(row.get("section") or ""),
                start_sec=_opt_float(row.get("start_sec")),
                end_sec=_opt_float(row.get("end_sec")),
            )
        )
    if not lines:
        return None
    return Song(
        song_id=str(rec.get("song_id") or rec.get("id") or fallback_id),
        language=str(rec.get("language") or "en"),
        title_en=str(rec.get("title_en") or rec.get("title") or "Untitled"),
        topic=str(rec.get("topic") or "general"),
        style=str(rec.get("style") or "suno-educational-original"),
        license=str(rec.get("license") or "original-salareen"),
        source=str(rec.get("source") or "imported"),
        lines=lines,
        audio_file=str(rec.get("audio_file") or ""),
        animation=str(rec.get("animation") or "pulse"),
        featured=bool(rec.get("featured") or False),
        duration_hint_sec=_opt_float(rec.get("duration_hint_sec")),
        lead_in_sec=_opt_float(rec.get("lead_in_sec")) or 0.0,
        tail_sec=_opt_float(rec.get("tail_sec")) or 0.0,
    )


def load_songs(path: Optional[os.PathLike[str] | str] = None) -> list[Song]:
    p = Path(path) if path else _default_data_path()
    out: list[Song] = []
    if p.is_file():
        with p.open(encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue  # one corrupt line must not kill the whole catalog
                song = _song_from_record(rec, fallback_id=f"import-{len(out)+1}")
                if song:
                    out.append(song)
    # Featured MP3 pack (player UI) — prepend so they show first.
    featured_path = _featured_data_path()
    if featured_path.is_file():
        featured: list[Song] = []
        with featured_path.open(encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                rec["featured"] = True
                song = _song_from_record(rec, fallback_id=f"featured-{len(featured)+1}")
                if song:
                    featured.append(song)
        # Prefer featured ids; drop duplicates from the big catalog.
        featured_ids = {s.song_id for s in featured}
        out = featured + [s for s in out if s.song_id not in featured_ids]
    return out


def import_songs(records: Iterable[dict[str, Any]]) -> list[Song]:
    """Validate and normalize imported original song packs (no copyrighted lyrics)."""
    songs: list[Song] = []
    for i, rec in enumerate(records):
        license_ = str(rec.get("license") or "").lower()
        if license_ and "copyright" in license_ and "original" not in license_:
            raise ValueError(
                f"Refusing import of '{rec.get('song_id')}': "
                "only original/educational licenses are allowed in this lab"
            )
        song = _song_from_record(rec, fallback_id=f"import-{i + 1}")
        if song is None:
            raise ValueError(f"Song '{rec.get('song_id')}' has no lines")
        songs.append(song)
    return songs


def meaning_for_line(line: SongLine, target_lang: str) -> dict[str, Any]:
    """Real per-line translation for 26+ languages (see translations.py tiers)."""
    from .translations import translate_line  # local import: translations needs Song

    code = (target_lang or "en").strip().lower()
    if code not in MEANING_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{target_lang}'. "
            f"Supported: {', '.join(MEANING_LANGUAGES)}"
        )
    row = translate_line(line, code)
    return {
        "target_language": code,
        "target_language_name": _LANG_LABEL.get(code, code),
        "text": row["translation"],
        "meaning_en": row["meaning_en"],
        "tier": row["tier"],
        "note": row["note"],
        "vocabulary": row["vocabulary"],
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
                "featured": s.featured,
                "audio_url": s.audio_url,
                "audio_file": s.audio_file,
                "animation": s.animation,
                "duration_hint_sec": s.duration_hint_sec,
            }
            for s in rows[: max(0, limit)]
        ]

    def featured(self) -> list[Song]:
        return [s for s in self._songs if s.featured and s.audio_file]

    def extend(self, songs: list[Song]) -> int:
        added = 0
        for song in songs:
            if song.song_id in self._by_id:
                continue
            self._songs.append(song)
            self._by_id[song.song_id] = song
            added += 1
        return added
