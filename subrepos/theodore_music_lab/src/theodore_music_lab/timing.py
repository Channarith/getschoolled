"""Line and word timings for karaoke highlighting and the bouncing ball.

Featured tracks are aligned against their own audio: ``scripts/align_songs.py``
measures where the singing actually is and commits the result to
``data/alignment.jsonl``, which is what the player gets. That keeps the intro,
the rests between sections and the outro out of the lyrics.

Anything without measured alignment falls back to syllable weight: a line with
more syllables holds the spotlight longer, and each word inside a line gets its
share of that line's slice.

Precedence is hand-tuned song data, then measured alignment, then the estimate.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .catalog import Song, SongLine

# A breath between lines and a longer rest when the section changes.
_LINE_PAUSE_WEIGHT = 0.6
_SECTION_PAUSE_WEIGHT = 1.4
_MIN_WORD_SEC = 0.12
# Karaoke lights the vowel, not the consonant attack. A short holdback on each
# word start keeps the ball from looking early when the singer is still on the
# previous syllable. Capped so a 0.12s word does not vanish.
_WORD_ONSET_LAG_SEC = 0.08

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")
_WORD_CHARS = re.compile(r"[^a-z']+")

# Playback duration this far from the aligned reference means a different
# encode; the measured timings are stretched to fit rather than thrown away.
_DURATION_TOLERANCE_SEC = 0.5


def _alignment_path() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent.parent / "data" / "alignment.jsonl"


@lru_cache(maxsize=1)
def _alignments() -> dict[str, dict[str, Any]]:
    """Measured per-line timings keyed by song id (empty when never aligned)."""
    path = _alignment_path()
    if not path.is_file():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        song_id = str(rec.get("song_id") or "")
        if song_id:
            rows[song_id] = rec
    return rows


def alignment_for(song_id: str) -> dict[str, Any] | None:
    return _alignments().get(song_id)


def _audio_matches(record: dict[str, Any]) -> bool:
    """False when the MP3 was replaced after alignment was measured."""
    expected = record.get("audio_bytes")
    name = str(record.get("audio_file") or "")
    if not expected or not name:
        return True
    audio = _alignment_path().parent / "audio" / name
    if not audio.is_file():
        return False
    return audio.stat().st_size == int(expected)


def syllable_count(word: str) -> int:
    """Rough English syllable count; never returns less than 1 for a real word."""
    plain = _WORD_CHARS.sub("", word.lower())
    if not plain:
        return 1
    groups = _VOWEL_GROUPS.findall(plain)
    count = len(groups)
    # Silent trailing 'e' ("shine"), but keep "the", "she", and "tiptoe".
    if (
        plain.endswith("e")
        and count > 1
        and not plain.endswith(("le", "ee", "ye", "oe", "ue"))
    ):
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
        if span > 0 and len(words) * _MIN_WORD_SEC <= span:
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
    return _apply_onset_lag(out)


def _apply_onset_lag(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nudge each word's start later so highlighting waits for the vowel."""
    for word in words:
        span = max(0.0, float(word["end"]) - float(word["start"]))
        if span <= 0:
            continue
        lag = min(_WORD_ONSET_LAG_SEC, span * 0.25)
        start = round(float(word["start"]) + lag, 3)
        if start >= float(word["end"]):
            start = round(float(word["end"]) - min(0.04, span), 3)
        word["start"] = start
    return words


def _words_from_alignment(
    text: str, start: float, end: float, measured: dict[str, Any], scale: float
) -> list[dict[str, Any]]:
    """Prefer per-word energy cuts written by align_songs.py when they match."""
    raw = measured.get("words")
    tokens = _words(text)
    if not isinstance(raw, list) or len(raw) != len(tokens):
        return word_timings(text, start, end)
    out: list[dict[str, Any]] = []
    for index, (token, row) in enumerate(zip(tokens, raw)):
        w_start = float(row.get("start_sec", start)) * scale
        w_end = float(row.get("end_sec", end)) * scale
        w_start = max(start, min(end, w_start))
        w_end = max(w_start, min(end, w_end))
        out.append(
            {
                "index": index,
                "text": token,
                "syllables": syllable_count(token),
                "start": round(w_start, 3),
                "end": round(w_end, 3),
            }
        )
    if out:
        out[0]["start"] = round(start, 3)
        out[-1]["end"] = round(end, 3)
    return _apply_onset_lag(out)


def _aligned_timings(
    song: Song, *, duration_sec: float | None = None
) -> dict[str, Any] | None:
    """Measured timings for a featured song, stretched to the played encode."""
    record = alignment_for(song.song_id)
    if not record or not _audio_matches(record):
        return None
    by_line = {
        int(row["line_no"]): row
        for row in record.get("lines", [])
        if row.get("line_no") is not None
    }
    if not all(line.line_no in by_line for line in song.lines):
        return None

    reference = float(record.get("duration_sec") or 0.0)
    played = float(duration_sec or 0.0) or reference
    scale = 1.0
    if reference > 0 and played > 0 and abs(played - reference) > _DURATION_TOLERANCE_SEC:
        scale = played / reference

    rows: list[dict[str, Any]] = []
    for line in song.lines:
        measured = by_line[line.line_no]
        start = float(measured["start_sec"]) * scale
        end = float(measured["end_sec"]) * scale
        # Hand-tuned song data still wins over the measurement.
        if line.start_sec is not None:
            start = float(line.start_sec) * scale
        if line.end_sec is not None:
            end = float(line.end_sec) * scale
        end = max(start + _MIN_WORD_SEC, end)
        rows.append(
            {
                "line_no": line.line_no,
                "text": line.text,
                "section": line.section,
                "start": round(start, 3),
                "end": round(end, 3),
                "words": _words_from_alignment(
                    line.text, start, end, measured, scale
                ),
            }
        )
    duration = played or (rows[-1]["end"] if rows else 0.0)
    for index, row in enumerate(rows):
        syllables = sum(syllable_count(word) for word in row["text"].split())
        need = syllables / 8.0
        cap = rows[index + 1]["start"] if index + 1 < len(rows) else duration
        widened = min(cap, max(row["end"], row["start"] + need))
        if widened > row["end"]:
            row["end"] = round(widened, 3)
            if row["words"]:
                row["words"][-1]["end"] = row["end"]
    return {
        "song_id": song.song_id,
        "duration_sec": round(duration, 3),
        "lead_in_sec": round(float(record.get("lead_in_sec") or 0.0) * scale, 3),
        "line_count": len(rows),
        "word_count": sum(len(r["words"]) for r in rows),
        "source": "measured vocal alignment",
        "aligned": True,
        "lines": rows,
    }


def song_timings(
    song: Song,
    *,
    duration_sec: float | None = None,
    lead_in_sec: float | None = None,
) -> dict[str, Any]:
    """Per-line + per-word timings covering the whole song."""
    lines = song.lines
    aligned = _aligned_timings(song, duration_sec=duration_sec)
    if aligned is not None:
        return aligned
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
        "aligned": False,
        "lines": rows,
    }


def line_at(timings: dict[str, Any], position_sec: float) -> dict[str, Any] | None:
    """Line active at a playback position (used by clips and by tests)."""
    for row in timings.get("lines", []):
        if row["start"] <= position_sec < row["end"]:
            return row
    return None
