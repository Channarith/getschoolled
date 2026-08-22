#!/usr/bin/env python3
"""Import the user-provided MP3/RTF pairs into the featured karaoke pack."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path.home() / "Downloads"
FEATURED = ROOT / "data" / "featured_songs.jsonl"
AUDIO = ROOT / "data" / "audio"

PACK = (
    {
        "song_id": "en-love-solid-ground-audio-v1",
        "title": "Love on Solid Ground",
        "topic": "friendship",
        "animation": "pulse",
        "rtf": "love on solid ground.rtf",
        "mp3": "Love on Solid Ground.mp3",
        "audio": "love_on_solid_ground.mp3",
    },
    {
        "song_id": "en-love-me-too-audio-v1",
        "title": "Do You Love Me Too?",
        "topic": "feelings",
        "animation": "pulse",
        "rtf": "do you love me too.rtf",
        "mp3": "Do You Love Me Too_.mp3",
        "audio": "do_you_love_me_too.mp3",
    },
    {
        "song_id": "en-do-the-chicken-audio-v1",
        "title": "Do the Chicken",
        "topic": "movement",
        "animation": "words",
        "rtf": "do the chicken.rtf",
        "mp3": "Do the Chicken.mp3",
        "audio": "do_the_chicken.mp3",
    },
    {
        "song_id": "en-bop-bop-bounce-audio-v1",
        "title": "Bop Bop Bounce",
        "topic": "movement",
        "animation": "words",
        "rtf": "bop bop bounce.rtf",
        "mp3": "Bop Bop Bounce.mp3",
        "audio": "bop_bop_bounce.mp3",
    },
    {
        "song_id": "en-first-word-audio-v1",
        "title": "First Word",
        "topic": "market vocabulary",
        "animation": "travel",
        "rtf": "first word.rtf",
        "mp3": "first word.mp3",
        "audio": "first_word.mp3",
    },
    {
        "song_id": "en-sorting-game-audio-v1",
        "title": "Sorting Game",
        "topic": "grammar and ordering",
        "animation": "words",
        "rtf": "sorting_game.rtf",
        "mp3": "Sorting Game.mp3",
        "audio": "sorting_game.mp3",
    },
    {
        "song_id": "en-be-your-spiderman-audio-v1",
        "title": "Be Your Spider-Man",
        "topic": "courage and care",
        "animation": "pulse",
        "rtf": "be your spiderman.rtf",
        "mp3": "Be Your Spider-Man.mp3",
        "audio": "be_your_spiderman.mp3",
    },
)


def plain_text(path: Path) -> str:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.replace("’", "'").replace("“", '"').replace("”", '"')


def lyric_lines(text: str) -> list[dict[str, object]]:
    section = "verse"
    rows: list[dict[str, object]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = (
                line[1:-1]
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )
            continue
        rows.append(
            {
                "line_no": len(rows) + 1,
                "text": line,
                "meaning_en": line,
                "tts_text": line,
                "section": section,
            }
        )
    if not rows:
        raise ValueError("lyrics contain no lines")
    return rows


def duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()), 3)


def main() -> int:
    existing: dict[str, dict[str, object]] = {}
    if FEATURED.is_file():
        for raw in FEATURED.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                row = json.loads(raw)
                existing[str(row["song_id"])] = row

    AUDIO.mkdir(parents=True, exist_ok=True)
    for item in PACK:
        source_audio = DOWNLOADS / item["mp3"]
        source_lyrics = DOWNLOADS / item["rtf"]
        if not source_audio.is_file() or not source_lyrics.is_file():
            raise FileNotFoundError(f"missing {source_audio} or {source_lyrics}")
        target_audio = AUDIO / item["audio"]
        shutil.copy2(source_audio, target_audio)
        rows = lyric_lines(plain_text(source_lyrics))
        # The aligner found a short breath after this phrase and clipped it to
        # 0.52s. Let it use the following 0.30s rest so the bouncing ball and
        # translated voice stay at a human speaking rate.
        if item["song_id"] == "en-sorting-game-audio-v1":
            rows[5]["end_sec"] = 17.14
        existing[item["song_id"]] = {
            "song_id": item["song_id"],
            "language": "en",
            "title_en": item["title"],
            "topic": item["topic"],
            "style": "educational-mp3",
            "license": "original-salareen",
            "source": "user-provided-original-pack",
            "audio_file": item["audio"],
            "animation": item["animation"],
            "featured": True,
            "duration_hint_sec": duration(source_audio),
            "lines": rows,
        }
        print(f"{item['title']}: {len(rows)} lines -> {target_audio.name}")

    FEATURED.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in existing.values()),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
