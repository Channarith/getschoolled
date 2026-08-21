#!/usr/bin/env python3
"""Check the lyric timings the app serves against the singing in the MP3.

align_songs.py writes the timings; this re-measures the audio and audits what
song_timings() actually hands the browser, so a stale alignment.jsonl, a
replaced MP3, or a bad scale shows up as a number instead of "feels off":

    python3 scripts/verify_alignment.py
    python3 scripts/verify_alignment.py --song en-travel-words-audio-v1 --report

Needs ffmpeg on PATH. Exit code is 1 when a song fails a check.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from theodore_music_lab import asr_align  # noqa: E402
from theodore_music_lab.catalog import Catalog  # noqa: E402
from theodore_music_lab.timing import (  # noqa: E402
    song_timings,
    syllable_count,
)
from theodore_music_lab.vocal_align import (  # noqa: E402
    FFmpegMissing,
    analyze_audio,
    have_ffmpeg,
)

AUDIO_DIR = ROOT / "data" / "audio"

# A singer's onset and our frame grid never agree perfectly; a quarter second is
# under the threshold where a listener hears the ball leading or trailing.
ONSET_TOLERANCE_SEC = 0.30
FIRST_LINE_TOLERANCE_SEC = 0.30
MAX_SYLLABLES_PER_SEC = 8.0


def nearest_onset(onsets: list[float], value: float) -> float:
    return min(onsets, key=lambda onset: abs(onset - value))


def word_onset_gaps(song, rows: list[dict], analysis: dict) -> list[float] | None:
    """Per-line drift between what we serve and when the line's words are sung.

    None when there is no transcript and no way to make one. Uses the same
    singing-window bounds align_songs.py does, so a deliberate clamp on the
    opening word does not read as drift.
    """
    audio = AUDIO_DIR / Path(song.audio_file).name
    if not asr_align.have_words(audio):
        return None
    heard = asr_align.cached_words(audio)
    if not heard:
        return None
    duration = float(analysis["duration_sec"])
    truth = asr_align.align_lines(
        ((line.line_no, line.text) for line in song.lines),
        heard,
        duration_sec=duration,
        sing_start=float(analysis["lead_in_sec"]),
        sing_end=duration - float(analysis["tail_sec"]),
    )
    by_no = {int(r["line_no"]): float(r["start_sec"]) for r in truth["lines"]}
    return [
        abs(float(row["start"]) - by_no[int(row["line_no"])])
        for row in rows
        if int(row["line_no"]) in by_no
    ]


def check_song(song, *, report: bool) -> list[str]:
    """Audit one song, printing what was measured. Returns failure messages."""
    audio = AUDIO_DIR / Path(song.audio_file).name
    if not audio.is_file():
        print(f"  skip: no audio at {audio}")
        return []

    analysis = analyze_audio(str(audio), line_count=song.line_count)
    spans = analysis["spans"]
    if not spans:
        return [f"{song.song_id}: no singing detected in {audio.name}"]
    onsets = [span.start for span in spans]
    vocal_start = onsets[0]

    served = song_timings(song, duration_sec=float(analysis["duration_sec"]))
    rows = sorted(served["lines"], key=lambda r: float(r["start"]))
    failures: list[str] = []

    print(
        f"  audio: duration={analysis['duration_sec']}s "
        f"first_vocal={vocal_start:.2f}s phrases={len(spans)}"
    )
    print(f"  served: source={served['source']} lead_in={served['lead_in_sec']}s")

    if served["source"] != "measured vocal alignment":
        failures.append(
            f"{song.song_id}: serving '{served['source']}' — run "
            f"scripts/align_songs.py --song {song.song_id}"
        )

    first_start = float(rows[0]["start"])
    drift = first_start - vocal_start
    print(f"  line 1 starts {first_start:.2f}s vs singing {vocal_start:.2f}s "
          f"({drift:+.2f}s)")
    if abs(drift) > FIRST_LINE_TOLERANCE_SEC:
        failures.append(
            f"{song.song_id}: line 1 starts {drift:+.2f}s off the first vocal "
            f"({first_start:.2f}s vs {vocal_start:.2f}s)"
        )

    # Early lyrics are the complaint people actually notice, so no line may open
    # before the singing does.
    early = [r["line_no"] for r in rows
             if float(r["start"]) < vocal_start - ONSET_TOLERANCE_SEC]
    if early:
        failures.append(
            f"{song.song_id}: {len(early)} line(s) start before any singing "
            f"(first: line {early[0]})"
        )

    # Audit against the words that were RECOGNISED, not against loudness. The
    # old check asked "does this line start on a measured phrase onset?", which
    # the loudness aligner passed by construction — it reported 0.00s drift
    # while the ball led the vocal by four seconds, because a phrase onset says
    # nothing about WHICH line is being sung there.
    gaps = word_onset_gaps(song, rows, analysis)
    if gaps is None:
        loud = [abs(float(r["start"]) - nearest_onset(onsets, float(r["start"])))
                for r in rows]
        print(
            f"  NOTE no transcript available; falling back to phrase onsets "
            f"(median={statistics.median(loud):.2f}s). Install the asr extra for "
            f"a real check."
        )
    else:
        worst = max(range(len(gaps)), key=gaps.__getitem__)
        print(
            f"  word onset match: median={statistics.median(gaps):.2f}s "
            f"worst={gaps[worst]:.2f}s (line {rows[worst]['line_no']})"
        )
        loose = [rows[i]["line_no"] for i, gap in enumerate(gaps)
                 if gap > ONSET_TOLERANCE_SEC]
        if loose:
            failures.append(
                f"{song.song_id}: {len(loose)} line(s) do not start when their "
                f"words are sung (worst line {rows[worst]['line_no']}, "
                f"{gaps[worst]:.2f}s off)"
            )

    by_no = {line.line_no: line for line in song.lines}
    rushed: list[tuple[int, float]] = []
    for row in rows:
        line = by_no.get(row["line_no"])
        if not line:
            continue
        span = max(0.01, float(row["end"]) - float(row["start"]))
        syllables = sum(syllable_count(word) for word in line.text.split())
        rate = syllables / span
        if rate > MAX_SYLLABLES_PER_SEC:
            rushed.append((row["line_no"], rate))
    if rushed:
        failures.append(
            f"{song.song_id}: {len(rushed)} line(s) sung faster than "
            f"{MAX_SYLLABLES_PER_SEC:g} syllables/sec: {rushed[:4]}"
        )

    if report:
        for index, row in enumerate(rows):
            line = by_no.get(row["line_no"])
            gap = (
                gaps[index]
                if gaps is not None and index < len(gaps)
                else abs(float(row["start"]) - nearest_onset(onsets, float(row["start"])))
            )
            print(
                f"    {row['line_no']:>3} {float(row['start']):>7.2f} "
                f"{float(row['end']):>7.2f}  {gap:>5.2f}s  "
                f"{line.text if line else ''}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--song", default="", help="verify one song id only")
    parser.add_argument(
        "--report", action="store_true", help="print every line with its onset gap"
    )
    args = parser.parse_args()

    if not have_ffmpeg():
        print("ffmpeg not found on PATH; install it to verify alignment",
              file=sys.stderr)
        return 2

    songs = [s for s in Catalog().featured() if not args.song or s.song_id == args.song]
    if not songs:
        print("no featured songs matched", file=sys.stderr)
        return 2

    failures: list[str] = []
    for song in songs:
        print(f"verifying {song.song_id} ({song.line_count} lines)")
        try:
            failures.extend(check_song(song, report=args.report))
        except FFmpegMissing as exc:
            print(f"  {exc}", file=sys.stderr)
            return 2

    if failures:
        print("\nOUT OF SYNC:")
        for message in failures:
            print(f"  - {message}")
        return 1
    print(f"\nin sync: {len(songs)} song(s) match their vocals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
