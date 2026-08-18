"""Line and word timings for karaoke highlighting and the bouncing ball.

The featured MP3s ship without a forced-alignment track, so timings are derived
from syllable weight: a line with more syllables holds the spotlight longer, and
each word inside a line gets its share of that line's slice. That is accurate
enough for a follow-the-ball reading aid, and the player exposes a live sync
nudge so a listener can trim any residual drift.

Hand-tuned values always win: a line with ``start_sec``/``end_sec`` in the song
data is used verbatim, and a song can declare ``lead_in_sec`` for its intro.
"""

from __future__ import annotations

import re
from typing import Any

from .catalog import Song, SongLine

# A breath between lines and a longer rest when the section changes.
_LINE_PAUSE_WEIGHT = 0.6
_SECTION_PAUSE_WEIGHT = 1.4
_MIN_WORD_SEC = 0.12

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")
_WORD_CHARS = re.compile(r"[^a-z']+")


def syllable_count(word: str) -> int:
    """Rough English syllable count; never returns less than 1 for a real word."""
    plain = _WORD_CHARS.sub("", word.lower())
    if not plain:
        return 1
    groups = _VOWEL_GROUPS.findall(plain)
    count = len(groups)
    # Silent trailing 'e' ("shine"), but keep "the" and "she" at one syllable.
    if plain.endswith("e") and count > 1 and not plain.endswith(("le", "ee", "ye")):
        count -= 1
    return max(1, count)


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", (text or "").strip()) if w]


def line_weight(line: SongLine) -> float:
    words = _words(line.text)
    return float(sum(syllable_count(w) for w in words)) or 1.0


def word_timings(text: str, start: float, end: float) -> list[dict[str, Any]]:
    """Split a line's time slice across its words, proportional to syllables."""
    words = _words(text)
    if not words:
        return []
    span = max(0.0, end - start)
    weights = [float(syllable_count(w)) for w in words]
    total = sum(weights) or float(len(words))
    out: list[dict[str, Any]] = []
    cursor = start
    for index, (word, weight) in enumerate(zip(words, weights)):
        share = span * (weight / total)
        if span > 0:
            share = max(_MIN_WORD_SEC, share)
        w_end = min(end, cursor + share) if span > 0 else cursor
        out.append(
            {
                "index": index,
                "text": word,
                "syllables": int(weight),
                "start": round(cursor, 3),
                "end": round(max(cursor, w_end), 3),
            }
        )
        cursor = w_end
    if out and span > 0:
        out[-1]["end"] = round(end, 3)
    return out


def song_timings(
    song: Song,
    *,
    duration_sec: float | None = None,
    lead_in_sec: float | None = None,
) -> dict[str, Any]:
    """Per-line + per-word timings covering the whole song."""
    lines = song.lines
    duration = float(duration_sec or song.duration_hint_sec or 0.0)
    if duration <= 0.0:
        duration = 3.0 * max(1, len(lines))
    lead = lead_in_sec if lead_in_sec is not None else float(song.lead_in_sec or 0.0)
    lead = max(0.0, min(lead, duration * 0.5))
    tail = max(0.0, float(song.tail_sec or 0.0))
    singable = max(1.0, duration - lead - tail)

    weights: list[float] = []
    previous_section = ""
    for line in lines:
        pause = _LINE_PAUSE_WEIGHT
        if previous_section and line.section and line.section != previous_section:
            pause = _SECTION_PAUSE_WEIGHT
        weights.append(line_weight(line) + pause)
        previous_section = line.section

    def _pinned(line: SongLine) -> bool:
        return line.start_sec is not None and line.end_sec is not None

    # Hand-timed lines are placed verbatim, so their spans come OUT of the
    # budget — the old code distributed the whole singable span across all
    # lines, and a pinned line's share was never subtracted, so estimated lines
    # overran the declared duration.
    pinned_span = sum(
        float(line.end_sec) - float(line.start_sec) for line in lines if _pinned(line)
    )
    unpinned_weight = sum(w for line, w in zip(lines, weights) if not _pinned(line))
    budget = max(0.0, singable - pinned_span)

    rows: list[dict[str, Any]] = []
    cursor = lead
    for line, weight in zip(lines, weights):
        share = budget * (weight / unpinned_weight) if unpinned_weight else 0.0
        start = float(line.start_sec) if line.start_sec is not None else cursor
        end = float(line.end_sec) if line.end_sec is not None else start + share
        end = max(start + _MIN_WORD_SEC, end)
        rows.append(
            {
                "line_no": line.line_no,
                "text": line.text,
                "section": line.section,
                "start": round(start, 3),
                "end": round(end, 3),
                "words": word_timings(line.text, start, end),
            }
        )
        cursor = end
    return {
        "song_id": song.song_id,
        "duration_sec": round(duration, 3),
        "lead_in_sec": round(lead, 3),
        "line_count": len(rows),
        "word_count": sum(len(r["words"]) for r in rows),
        "source": "syllable-weighted estimate",
        "lines": rows,
    }


def line_at(timings: dict[str, Any], position_sec: float) -> dict[str, Any] | None:
    """Line active at a playback position (used by clips and by tests)."""
    for row in timings.get("lines", []):
        if row["start"] <= position_sec < row["end"]:
            return row
    return None
