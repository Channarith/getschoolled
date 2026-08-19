"""Short lyric clips and curated external lyric-video links.

A *clip* is a line range of a featured song: the player seeks the MP3 to the
clip window and stops at the end, so a learner can drill one chorus with its
translation instead of the whole track. Timings come from ``timing.song_timings``
so clips inherit any hand-tuned or nudged sync.

*Video links* are curated pointers to real lyric videos and channels. Search
links are deliberate: they never rot, and YouTube's caption auto-translate gives
the learner lyrics in their own language.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .catalog import Song
from .embeds import embed_url
from .timing import song_timings
from .translations import translate_line, validate_language


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict):
                rows.append(rec)
    return rows


def load_clips(path: Optional[Path] = None) -> list[dict[str, Any]]:
    return _load_jsonl(path or _data_dir() / "clips.jsonl")


def _youtube_id_from_embed(url: str) -> str:
    text = (url or "").strip()
    marker = "/embed/"
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].split("?", 1)[0].split("&", 1)[0].strip()


def _public_video_embed(row: dict[str, Any]) -> dict[str, Any]:
    """Serve lyric-video embeds from www.youtube.com (never youtube-nocookie)."""
    raw = str(row.get("embed_url") or "")
    yt = _youtube_id_from_embed(raw)
    if not yt:
        return row
    out = dict(row)
    out["embed_url"] = embed_url(yt, jsapi=False)
    return out


def load_videos(path: Optional[Path] = None) -> list[dict[str, Any]]:
    return [_public_video_embed(row) for row in _load_jsonl(path or _data_dir() / "video_links.jsonl")]


def resolve_clip(
    song: Song,
    clip: dict[str, Any],
    language: str = "en",
    *,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    """Attach the audio window, lyrics and translations to a clip definition."""
    lang = validate_language(language)
    start_line = int(clip.get("start_line") or 1)
    end_line = int(clip.get("end_line") or start_line)
    timings = song_timings(song, duration_sec=duration_sec)
    rows = [
        row for row in timings["lines"] if start_line <= row["line_no"] <= end_line
    ]
    by_no = {line.line_no: line for line in song.lines}
    lines: list[dict[str, Any]] = []
    for row in rows:
        line = by_no.get(row["line_no"])
        if line is None:
            continue
        translated = translate_line(line, lang)
        lines.append(
            {
                "line_no": row["line_no"],
                "text": row["text"],
                "section": row["section"],
                "start": row["start"],
                "end": row["end"],
                "words": row["words"],
                "translation": translated["translation"],
                "tier": translated["tier"],
                "vocabulary": translated["vocabulary"],
            }
        )
    start = rows[0]["start"] if rows else 0.0
    end = rows[-1]["end"] if rows else 0.0
    return {
        "clip_id": str(clip.get("clip_id") or ""),
        "song_id": song.song_id,
        "song_title_en": song.title_en,
        "title": str(clip.get("title") or ""),
        "focus": str(clip.get("focus") or ""),
        "animation": song.animation,
        "audio_url": song.audio_url,
        "start_sec": round(start, 3),
        "end_sec": round(end, 3),
        "duration_sec": round(max(0.0, end - start), 3),
        "language": lang,
        "line_count": len(lines),
        "lines": lines,
    }


def videos_for(song_id: str = "") -> list[dict[str, Any]]:
    """Curated lyric videos: song-specific first, then general channels."""
    rows = load_videos()
    if not song_id:
        return rows
    matched = [r for r in rows if str(r.get("song_id") or "") == song_id]
    general = [r for r in rows if not str(r.get("song_id") or "")]
    return matched + general
