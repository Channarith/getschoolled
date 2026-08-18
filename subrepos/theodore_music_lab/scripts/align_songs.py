#!/usr/bin/env python3
"""Align the featured lyrics to the sung vocals and write data/alignment.jsonl.

Run this after adding or replacing a featured MP3:

    python3 scripts/align_songs.py            # all featured songs
    python3 scripts/align_songs.py --song en-wheels-bus-audio-v1
    python3 scripts/align_songs.py --report   # print the timings, write nothing

Needs ffmpeg on PATH. Serving the app does not: the committed alignment.jsonl is
what timing.py reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from theodore_music_lab.catalog import Catalog  # noqa: E402
from theodore_music_lab.timing import line_weight  # noqa: E402
from theodore_music_lab.vocal_align import (  # noqa: E402
    FFmpegMissing,
    align_song_lines,
    have_ffmpeg,
)

ALIGNMENT_PATH = ROOT / "data" / "alignment.jsonl"
AUDIO_DIR = ROOT / "data" / "audio"


def align_song(song) -> dict[str, object] | None:
    audio = AUDIO_DIR / Path(song.audio_file).name
    if not audio.is_file():
        print(f"  skip {song.song_id}: no audio at {audio}")
        return None
    weights = [line_weight(line) for line in song.lines]
    placed, analysis = align_song_lines(str(audio), weights)
    if len(placed) != len(song.lines):
        print(f"  skip {song.song_id}: no vocal spans detected")
        return None
    spans = analysis["spans"]
    return {
        "song_id": song.song_id,
        "audio_file": Path(song.audio_file).name,
        # Timings belong to this exact encode; timing.py checks the size so a
        # replaced MP3 falls back to the estimate instead of drifting silently.
        "audio_bytes": audio.stat().st_size,
        "duration_sec": analysis["duration_sec"],
        "lead_in_sec": analysis["lead_in_sec"],
        "tail_sec": analysis["tail_sec"],
        "source": "vocal-centre-channel-alignment",
        "method": analysis["method"],
        "vocal_span_count": len(spans),
        "lines": [
            {"line_no": line.line_no, "start_sec": start, "end_sec": end}
            for line, (start, end) in zip(song.lines, placed)
        ],
    }


def syllable_rates(song, placed) -> list[tuple[int, float]]:
    """Syllables per second per line — a sanity check on a suspicious mapping."""
    from theodore_music_lab.timing import syllable_count

    rates: list[tuple[int, float]] = []
    for line, (start, end) in zip(song.lines, placed):
        span = max(0.01, end - start)
        syllables = sum(syllable_count(w) for w in line.text.split())
        rates.append((line.line_no, syllables / span))
    return rates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--song", default="", help="align one song id only")
    parser.add_argument(
        "--report", action="store_true", help="print per-line timings, write nothing"
    )
    args = parser.parse_args()

    if not have_ffmpeg():
        print("ffmpeg not found on PATH; install it to run alignment", file=sys.stderr)
        return 2

    songs = [s for s in Catalog().featured() if not args.song or s.song_id == args.song]
    if not songs:
        print("no featured songs matched", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    for song in songs:
        print(f"aligning {song.song_id} ({song.line_count} lines)")
        try:
            row = align_song(song)
        except FFmpegMissing as exc:
            print(f"  {exc}", file=sys.stderr)
            return 2
        if not row:
            continue
        rows.append(row)
        print(
            f"  duration={row['duration_sec']}s lead_in={row['lead_in_sec']}s "
            f"tail={row['tail_sec']}s spans={row['vocal_span_count']} "
            f"method={row['method']}"
        )
        placed = [(r["start_sec"], r["end_sec"]) for r in row["lines"]]
        rates = syllable_rates(song, placed)
        hot = [(no, rate) for no, rate in rates if rate > 8.0]
        if hot:
            print(f"  WARNING implausibly fast lines (>8 syll/s): {hot}")
        if args.report:
            for line, timed in zip(song.lines, row["lines"]):
                print(
                    f"    {line.line_no:>3} {timed['start_sec']:>7.2f} "
                    f"{timed['end_sec']:>7.2f}  [{line.section}] {line.text}"
                )

    if args.report:
        return 0

    existing: dict[str, dict[str, object]] = {}
    if ALIGNMENT_PATH.is_file():
        for raw in ALIGNMENT_PATH.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                rec = json.loads(raw)
                existing[str(rec.get("song_id"))] = rec
    for row in rows:
        existing[str(row["song_id"])] = row
    ALIGNMENT_PATH.write_text(
        "".join(
            json.dumps(existing[key], ensure_ascii=False) + "\n"
            for key in sorted(existing)
        ),
        encoding="utf-8",
    )
    print(f"wrote {ALIGNMENT_PATH} ({len(existing)} songs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
