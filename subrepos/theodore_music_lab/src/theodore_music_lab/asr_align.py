"""Anchor line and word timings on recognised words, not just loudness.

The centre-channel aligner in ``vocal_align.py`` can only see WHERE someone is
singing, never WHAT. That breaks whenever the recording sings something the
lyric sheet omits: every chorus of travel_words repeats "I know them too", so
energy alignment had to push each remaining line onto an earlier phrase and the
bouncing ball ran seconds ahead of the vocal by the middle of the track.

Recognising the words removes the guesswork. Each lyric word is matched to a
recognised word, so a repeat that is missing from the sheet surfaces as an
unmatched run (reported, easy to fix) instead of silently corrupting every
later line.

Needs the ``asr`` extra (faster-whisper) and ffmpeg. Only
``scripts/align_songs.py`` imports this module; serving the app reads the
committed ``data/alignment.jsonl`` and needs neither.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .timing import syllable_count

DEFAULT_MODEL = "base.en"
# Sung vowels drift off the consonant, so a recognised start is already close to
# what a listener calls the word onset. Keep a floor so a clipped word is still
# visible on screen.
MIN_WORD_SEC = 0.12
# Match/gap scores for the lyric-to-transcript alignment. Skipping a recognised
# word is cheap (the sheet legitimately omits repeats and ad-libs); skipping a
# lyric word is dear (every printed word should light up).
_SCORE_MATCH = 2.0
_SCORE_NEAR = 1.0
_SCORE_MISMATCH = -2.0
_GAP_ASR = -0.5
_GAP_LYRIC = -1.6
# A recognised word starting this soon after the previous one is the tail of a
# word the decoder split, not a new phrase. One word only: a longer run at the
# same spacing is a line the sheet omits, and that has to be reported rather
# than hidden inside the previous word.
_SPLIT_GAP_SEC = 0.35
_MAX_ABSORB_WORDS = 1
# Longer than any rest inside a sung line, so splitting here separates a word
# that latched onto a neighbouring phrase from the line it belongs to.
_OUTLIER_GAP_SEC = 1.5

_PUNCT = re.compile(r"[^a-z0-9']+")


@dataclass(frozen=True)
class ASRWord:
    """One recognised word with the time it was sung."""

    text: str
    start: float
    end: float
    probability: float = 1.0


class ASRUnavailable(RuntimeError):
    """faster-whisper is not installed."""


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def normalise(token: str) -> str:
    """Fold a lyric or recognised token to a comparable key."""
    return _PUNCT.sub("", (token or "").lower())


def transcribe_words(
    path: str,
    *,
    model: str = DEFAULT_MODEL,
    compute_type: str = "int8",
    beam_size: int = 5,
) -> list[ASRWord]:
    """Recognised words with per-word times, in sung order."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover - depends on the asr extra
        raise ASRUnavailable(
            "faster-whisper is not installed; "
            "pip install -e 'subrepos/theodore_music_lab[asr]'"
        ) from exc

    engine = WhisperModel(model, device="cpu", compute_type=compute_type)
    segments, _info = engine.transcribe(
        path,
        word_timestamps=True,
        vad_filter=False,
        beam_size=beam_size,
        # Lyrics repeat by design; letting the decoder condition on what it just
        # heard makes it collapse repeated lines into one.
        condition_on_previous_text=False,
    )
    words: list[ASRWord] = []
    for segment in segments:
        for word in segment.words or []:
            text = (word.word or "").strip()
            if not normalise(text):
                continue
            words.append(
                ASRWord(
                    text=text,
                    start=float(word.start),
                    end=max(float(word.start), float(word.end)),
                    probability=float(getattr(word, "probability", 1.0) or 0.0),
                )
            )
    words.sort(key=lambda w: (w.start, w.end))
    return words


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two short tokens."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        previous = current
    return previous[-1]


def cache_dir() -> Path:
    """Where transcripts live. Recognition costs a minute; never redo it."""
    override = os.environ.get("MUSIC_LAB_ASR_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "theodore-music-lab" / "asr"


def _cache_path(audio: Path, model: str) -> Path:
    # Size in the key so a replaced MP3 cannot reuse the old transcript.
    return cache_dir() / f"{audio.stem}-{audio.stat().st_size}-{model}.json"


def cached_words(
    audio: str | Path, *, model: str = DEFAULT_MODEL, refresh: bool = False
) -> list[ASRWord]:
    """Recognised words for a track, transcribing only on a cache miss."""
    path = Path(audio)
    cache = _cache_path(path, model)
    if cache.is_file() and not refresh:
        return [
            ASRWord(**row) for row in json.loads(cache.read_text(encoding="utf-8"))
        ]
    words = transcribe_words(str(path), model=model)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps([asdict(w) for w in words], ensure_ascii=False), encoding="utf-8"
    )
    return words


def have_words(audio: str | Path, *, model: str = DEFAULT_MODEL) -> bool:
    """True when word times can be had without installing anything new."""
    path = Path(audio)
    if not path.is_file():
        return False
    return _cache_path(path, model).is_file() or available()


def _pair_score(lyric: str, heard: str) -> float:
    if lyric == heard:
        return _SCORE_MATCH
    if not lyric or not heard:
        return _SCORE_MISMATCH
    # Singing blurs endings ("word"/"words") and a decoder mishears onsets
    # ("bank" as "thank"). Both must still count, or one fuzzy word derails the
    # mapping for every line after it.
    if lyric.startswith(heard) or heard.startswith(lyric):
        return _SCORE_NEAR
    stem = min(3, len(lyric), len(heard))
    if stem >= 3 and lyric[:stem] == heard[:stem]:
        return _SCORE_NEAR
    # "bank" comes back as "thank" — two edits, so a one-edit budget is too mean
    # for anything but the shortest words, where it would match everything.
    longest = max(len(lyric), len(heard))
    if longest >= 4 and _edit_distance(lyric, heard) <= (2 if longest >= 5 else 1):
        return _SCORE_NEAR
    return _SCORE_MISMATCH


def match_tokens(
    lyric_tokens: Sequence[str], heard: Sequence[ASRWord]
) -> list[int | None]:
    """Map each lyric token to a recognised word index (None when unmatched).

    Needleman-Wunsch over the two word sequences. Order is preserved, so a
    chorus the sheet prints once cannot borrow time from its repeat.
    """
    keys = [normalise(t) for t in lyric_tokens]
    heard_keys = [normalise(w.text) for w in heard]
    n, m = len(keys), len(heard_keys)
    if n == 0 or m == 0:
        return [None] * n

    # score[i][j] = best score aligning first i lyric tokens to first j heard.
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + _GAP_LYRIC
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + _GAP_ASR
    for i in range(1, n + 1):
        row, prev = score[i], score[i - 1]
        key = keys[i - 1]
        for j in range(1, m + 1):
            row[j] = max(
                prev[j - 1] + _pair_score(key, heard_keys[j - 1]),
                prev[j] + _GAP_LYRIC,
                row[j - 1] + _GAP_ASR,
            )

    out: list[int | None] = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        pair = _pair_score(keys[i - 1], heard_keys[j - 1])
        # Walking back, spending the recognised word first pushes matches toward
        # their EARLIEST occurrence. That only changes ties, which is exactly the
        # repeated-chorus case: light the word the first time it is sung and let
        # the ball rest through the repeat, rather than lagging a whole phrase.
        if score[i][j] == score[i][j - 1] + _GAP_ASR:
            j -= 1
        elif score[i][j] == score[i - 1][j - 1] + pair:
            # Only trust a real or near match; a forced mismatch is left unmatched
            # and interpolated, which beats pinning a word to the wrong note.
            if pair > 0:
                out[i - 1] = j - 1
            i -= 1
            j -= 1
        else:
            i -= 1
    return out


def drop_line_outliers(
    matched: Sequence[int | None],
    heard: Sequence[ASRWord],
    owners: Sequence[int],
    *,
    max_gap_sec: float = _OUTLIER_GAP_SEC,
) -> list[int | None]:
    """Unmatch a word that landed nowhere near the rest of its line.

    Preferring the earliest occurrence is what makes a repeated chorus land on
    the right notes, but it also lets a common word ("I") latch onto the repeat
    just before its own line. A word separated from its line-mates by more than
    a rest is wrong; drop it so the repair pass can find the real one.
    """
    out = list(matched)
    by_line: dict[int, list[int]] = {}
    for index, (owner, hit) in enumerate(zip(owners, matched)):
        if hit is not None:
            by_line.setdefault(owner, []).append(index)
    for indexes in by_line.values():
        if len(indexes) < 2:
            continue
        clusters: list[list[int]] = [[indexes[0]]]
        for earlier, later in zip(indexes, indexes[1:]):
            gap = heard[out[later]].start - heard[out[earlier]].end
            if gap > max_gap_sec:
                clusters.append([later])
            else:
                clusters[-1].append(later)
        if len(clusters) < 2:
            continue
        best = max(clusters, key=len)
        if len(best) < 2:
            continue
        for cluster in clusters:
            if cluster is best or len(cluster) >= len(best):
                continue
            for index in cluster:
                out[index] = None
    return out


def repair_unmatched(
    lyric_tokens: Sequence[str],
    matched: Sequence[int | None],
    heard: Sequence[ASRWord],
) -> list[int | None]:
    """Claim an unclaimed recognised word that exactly matches, in the right gap.

    Runs after the outlier filter, so a word that was pulled onto a repeat gets
    a second chance at the occurrence that actually belongs to its line.
    """
    out = list(matched)
    keys = [normalise(t) for t in lyric_tokens]
    heard_keys = [normalise(w.text) for w in heard]
    claimed = {hit for hit in out if hit is not None}
    for index, hit in enumerate(out):
        if hit is not None or not keys[index]:
            continue
        before = next(
            (out[k] for k in range(index - 1, -1, -1) if out[k] is not None), None
        )
        after = next(
            (out[k] for k in range(index + 1, len(out)) if out[k] is not None), None
        )
        low = heard[before].end if before is not None else 0.0
        high = heard[after].start if after is not None else float("inf")
        best: int | None = None
        for probe in range(
            (before + 1) if before is not None else 0,
            after if after is not None else len(heard),
        ):
            if probe in claimed or heard_keys[probe] != keys[index]:
                continue
            if heard[probe].start < low - 0.01 or heard[probe].end > high + 0.01:
                continue
            # Closest to the following word wins: lyrics run forwards, so the
            # occurrence just before the next matched word is the right one.
            if best is None or heard[probe].start > heard[best].start:
                best = probe
        if best is not None:
            out[index] = best
            claimed.add(best)
    return out


def absorb_splits(
    matched: Sequence[int | None], heard: Sequence[ASRWord]
) -> tuple[dict[int, float], set[int]]:
    """Let one lyric word cover a word the decoder split ("super" + "market").

    Only a recognised word that follows immediately is absorbed. A gap means a
    rest, and past a rest the leftover is a line the sheet omits — that must be
    reported, not quietly swallowed by the previous word.
    """
    claimed = {hit for hit in matched if hit is not None}
    ends: dict[int, float] = {}
    absorbed: set[int] = set()
    for index, hit in enumerate(matched):
        if hit is None:
            continue
        end = heard[hit].end
        probe = hit + 1
        taken = 0
        while (
            probe < len(heard)
            and taken < _MAX_ABSORB_WORDS
            and probe not in claimed
            and heard[probe].start - end <= _SPLIT_GAP_SEC
        ):
            end = heard[probe].end
            absorbed.add(probe)
            probe += 1
            taken += 1
        ends[index] = end
    return ends, absorbed


def _interpolate(
    lyric_tokens: Sequence[str],
    matched: Sequence[int | None],
    heard: Sequence[ASRWord],
    *,
    fallback_end: float,
    ends: dict[int, float] | None = None,
) -> list[tuple[float, float]]:
    """Give unmatched lyric words a share of the gap around them."""
    n = len(lyric_tokens)
    ends = ends or {}
    times: list[tuple[float, float] | None] = [None] * n
    for index, hit in enumerate(matched):
        if hit is not None:
            word = heard[hit]
            end = max(word.end, ends.get(index, word.end))
            times[index] = (word.start, max(word.start + MIN_WORD_SEC, end))

    anchors = [i for i, t in enumerate(times) if t is not None]
    if not anchors:
        return [(0.0, max(MIN_WORD_SEC, fallback_end))] * n

    def spread(lo: int, hi: int, start: float, end: float) -> None:
        """Fill tokens [lo, hi) across start..end, longer words holding longer."""
        weights = [float(syllable_count(lyric_tokens[k])) for k in range(lo, hi)]
        total = sum(weights) or float(hi - lo)
        span = max(end - start, MIN_WORD_SEC * (hi - lo))
        cursor = start
        for k, weight in zip(range(lo, hi), weights):
            share = span * (weight / total)
            times[k] = (cursor, cursor + share)
            cursor += share

    first, last = anchors[0], anchors[-1]
    # A word before the first or after the last anchor still has to go
    # somewhere; the recogniser routinely drops the closing phrase.
    if first > 0:
        head_end = times[first][0]
        spread(0, first, max(0.0, head_end - MIN_WORD_SEC * first), head_end)
    if last < n - 1:
        spread(last + 1, n, times[last][1], max(fallback_end, times[last][1]))

    for a, b in zip(anchors, anchors[1:]):
        if b - a > 1:
            spread(a + 1, b, times[a][1], max(times[b][0], times[a][1]))

    return [t if t is not None else (0.0, MIN_WORD_SEC) for t in times]


def _monotonic(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Force non-overlapping, forward-only word spans."""
    cursor = 0.0
    for word in words:
        start = max(cursor, float(word["start_sec"]))
        end = max(start + MIN_WORD_SEC, float(word["end_sec"]))
        word["start_sec"] = round(start, 3)
        word["end_sec"] = round(end, 3)
        cursor = start
    for earlier, later in zip(words, words[1:]):
        if earlier["end_sec"] > later["start_sec"]:
            earlier["end_sec"] = round(
                max(earlier["start_sec"] + 0.04, later["start_sec"]), 3
            )
    return words


def unmatched_runs(
    matched: Sequence[int | None],
    heard: Sequence[ASRWord],
    *,
    min_run: int = 2,
    absorbed: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Recognised stretches no lyric word claimed — usually an omitted repeat."""
    claimed = {hit for hit in matched if hit is not None} | (absorbed or set())
    runs: list[dict[str, Any]] = []
    current: list[int] = []
    for index in range(len(heard)):
        if index in claimed:
            if len(current) >= min_run:
                runs.append(
                    {
                        "start_sec": round(heard[current[0]].start, 2),
                        "end_sec": round(heard[current[-1]].end, 2),
                        "text": " ".join(heard[k].text for k in current),
                        "word_count": len(current),
                    }
                )
            current = []
        else:
            current.append(index)
    if len(current) >= min_run:
        runs.append(
            {
                "start_sec": round(heard[current[0]].start, 2),
                "end_sec": round(heard[current[-1]].end, 2),
                "text": " ".join(heard[k].text for k in current),
                "word_count": len(current),
            }
        )
    return runs


def align_lines(
    lines: Iterable[tuple[int, str]],
    heard: Sequence[ASRWord],
    *,
    duration_sec: float,
    sing_start: float = 0.0,
    sing_end: float | None = None,
) -> dict[str, Any]:
    """Per-line and per-word times for a lyric sheet against recognised words.

    ``lines`` is ``(line_no, text)`` in sung order. Returns the rows
    ``align_songs.py`` writes plus a report of what the sheet is missing.

    ``sing_start`` and ``sing_end`` are the loudness-detected edges of the
    singing. Recognition is precise in the middle of a track and sloppy at both
    ends — it pads the opening word ahead of the first note and can stop early
    before the last phrase — so the energy envelope decides the edges while the
    recogniser decides which line goes where.
    """
    rows_in = [(int(no), str(text)) for no, text in lines]
    tokens: list[str] = []
    owners: list[int] = []
    for position, (_no, text) in enumerate(rows_in):
        for token in text.split():
            if normalise(token):
                tokens.append(token)
                owners.append(position)
            else:
                tokens.append(token)
                owners.append(position)

    matched = match_tokens(tokens, heard)
    matched = drop_line_outliers(matched, heard, owners)
    matched = repair_unmatched(tokens, matched, heard)
    ends, absorbed = absorb_splits(matched, heard)
    last_sung = sing_end if sing_end is not None else duration_sec
    spans = _interpolate(
        tokens, matched, heard, fallback_end=last_sung, ends=ends
    )

    grouped: list[list[dict[str, Any]]] = [[] for _ in rows_in]
    for token, owner, (start, end) in zip(tokens, owners, spans):
        grouped[owner].append(
            {"text": token, "start_sec": round(start, 3), "end_sec": round(end, 3)}
        )

    # Hold the opening word back to the first note, or line one lights up over
    # the intro. Never push it past its own end.
    for words in grouped:
        if not words:
            continue
        head = words[0]
        if sing_start > head["start_sec"]:
            head["start_sec"] = round(
                min(sing_start, head["end_sec"] - MIN_WORD_SEC), 3
            )
        break

    lines_out: list[dict[str, Any]] = []
    matched_words = sum(1 for hit in matched if hit is not None)
    cursor = 0.0
    for (line_no, _text), words in zip(rows_in, grouped):
        words = _monotonic(words)
        start = max(cursor, words[0]["start_sec"] if words else cursor)
        end = max(start + MIN_WORD_SEC, words[-1]["end_sec"] if words else start)
        lines_out.append(
            {
                "line_no": line_no,
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "words": words,
            }
        )
        cursor = end
    return {
        "lines": lines_out,
        "heard_word_count": len(heard),
        "lyric_word_count": len(tokens),
        "matched_word_count": matched_words,
        "match_ratio": round(matched_words / len(tokens), 3) if tokens else 0.0,
        "unmatched_heard": unmatched_runs(matched, heard, absorbed=absorbed),
    }
