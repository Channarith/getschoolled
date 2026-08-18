"""Measure where the singing actually happens in a featured MP3.

The featured tracks are real sung recordings, so a syllable-weighted guess that
spreads every line evenly from 0.0s to the last sample always drifts: it ignores
the instrumental intro, the rests between sections, and the outro.

This module derives the sung spans from the audio itself. Vocals sit in the
centre of the stereo image while the backing is spread wide, so the centre
estimate ``mid - side`` inside the vocal band is high while someone is singing
and near zero during an instrumental bar. Lines are then handed out across the
sung spans only (weighted by syllables), which keeps a line from being smeared
across an instrumental break and stops error from accumulating over the track.

Decoding needs ffmpeg, so alignment runs offline via ``scripts/align_songs.py``
and the result is committed to ``data/alignment.jsonl``. Serving never shells
out: ``timing.py`` just reads that file.
"""

from __future__ import annotations

import array
import math
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

SAMPLE_RATE = 16000
FRAME_SEC = 0.02
VOCAL_BAND_HZ = (300, 3500)
# Breaths inside one sung line are shorter than the rest between two lines.
_SMOOTH_SEC = 0.10
_MIN_SPAN_SEC = 0.25
_MERGE_GAP_SEC = 0.35
# A phrase boundary a line start may snap onto.
_SNAP_WINDOW_SEC = 0.45
_MIN_LINE_SEC = 0.35
# How strongly the segmentation prefers to break where the singer rested.
_GAP_BONUS = 0.35
# Phrase detection is retried finer until there is room for every line.
_DETECTION_STEPS: tuple[tuple[float, float], ...] = (
    (_MERGE_GAP_SEC, _MIN_SPAN_SEC),
    (0.25, 0.18),
    (0.18, 0.14),
    (0.14, 0.12),
)
_SPANS_PER_LINE_TARGET = 1.6
# Nobody sings faster than this, so a shorter slot means the mapping slipped.
_MAX_SYLLABLES_PER_SEC = 7.0
_RUSH_PENALTY = 10.0


class FFmpegMissing(RuntimeError):
    """ffmpeg is required to analyse audio (offline alignment step only)."""


@dataclass(frozen=True)
class VocalSpan:
    start: float
    end: float

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def decode_band_limited(
    path: str,
    *,
    sample_rate: int = SAMPLE_RATE,
    band: tuple[int, int] = VOCAL_BAND_HZ,
) -> array.array:
    """Interleaved stereo 16-bit PCM of ``path``, band-limited to the voice."""
    if not have_ffmpeg():
        raise FFmpegMissing("ffmpeg not found on PATH")
    low, high = band
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-ac", "2", "-ar", str(sample_rate),
            "-af", f"highpass=f={low},lowpass=f={high}",
            "-f", "s16le", "-",
        ],
        capture_output=True,
        check=True,
    )
    raw = proc.stdout
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) // 2 * 2])
    return pcm


def centre_envelope(
    pcm: array.array,
    *,
    sample_rate: int = SAMPLE_RATE,
    frame_sec: float = FRAME_SEC,
) -> list[float]:
    """Per-frame centre-panned energy: high while a voice is in the middle."""
    step = max(1, int(sample_rate * frame_sec))
    pairs = len(pcm) // 2
    out: list[float] = []
    for base in range(0, pairs - step + 1, step):
        mid_sq = 0.0
        side_sq = 0.0
        for i in range(base, base + step):
            left = pcm[2 * i]
            right = pcm[2 * i + 1]
            mid = (left + right) * 0.5
            side = (left - right) * 0.5
            mid_sq += mid * mid
            side_sq += side * side
        mid_rms = math.sqrt(mid_sq / step) / 32768.0
        side_rms = math.sqrt(side_sq / step) / 32768.0
        out.append(max(0.0, mid_rms - side_rms))
    return out


def smooth(values: Sequence[float], radius: int) -> list[float]:
    if radius <= 0:
        return list(values)
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - radius)
        hi = min(len(values), i + radius + 1)
        window = values[lo:hi]
        out.append(sum(window) / len(window))
    return out


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def vocal_spans(
    envelope: Sequence[float],
    *,
    frame_sec: float = FRAME_SEC,
    min_span_sec: float = _MIN_SPAN_SEC,
    merge_gap_sec: float = _MERGE_GAP_SEC,
) -> list[VocalSpan]:
    """Contiguous stretches of singing, with breaths inside a line merged."""
    if not envelope:
        return []
    floor = _percentile(envelope, 0.35)
    ceiling = _percentile(envelope, 0.90)
    threshold = floor + 0.30 * max(0.0, ceiling - floor)
    raw: list[list[float]] = []
    start_idx: int | None = None
    for i, value in enumerate(envelope):
        if value > threshold and start_idx is None:
            start_idx = i
        elif value <= threshold and start_idx is not None:
            raw.append([start_idx * frame_sec, i * frame_sec])
            start_idx = None
    if start_idx is not None:
        raw.append([start_idx * frame_sec, len(envelope) * frame_sec])

    merged: list[list[float]] = []
    for span in raw:
        if merged and span[0] - merged[-1][1] < merge_gap_sec:
            merged[-1][1] = span[1]
        else:
            merged.append(span)
    return [
        VocalSpan(round(s, 3), round(e, 3))
        for s, e in merged
        if e - s >= min_span_sec
    ]


def align_weights_to_spans(
    weights: Sequence[float],
    spans: Sequence[VocalSpan],
    *,
    snap_window_sec: float = _SNAP_WINDOW_SEC,
) -> list[tuple[float, float]]:
    """Hand out one (start, end) per weight across the sung spans only.

    Time is consumed in "sung seconds": a line never spans an instrumental
    break, and each break re-anchors the run so drift cannot accumulate. Line
    starts snap onto a nearby phrase onset so highlighting lands on the beat of
    the vocal rather than a fraction of a second before it.

    This is the fallback for when there are fewer detected phrases than lines;
    ``align_lines_to_spans`` is the preferred path.
    """
    if not weights:
        return []
    usable = [s for s in spans if s.length > 0]
    if not usable:
        return []
    total_sung = sum(s.length for s in usable)
    total_weight = float(sum(weights)) or float(len(weights))

    boundaries = [s.start for s in usable]

    def at_sung_time(offset: float) -> float:
        """Wall-clock position after consuming ``offset`` sung seconds."""
        remaining = offset
        for span in usable:
            if remaining <= span.length:
                return span.start + remaining
            remaining -= span.length
        return usable[-1].end

    def snap(value: float) -> float:
        best = value
        best_gap = snap_window_sec
        for boundary in boundaries:
            gap = abs(boundary - value)
            if gap < best_gap:
                best = boundary
                best_gap = gap
        return best

    out: list[tuple[float, float]] = []
    consumed = 0.0
    previous_end = usable[0].start
    for index, weight in enumerate(weights):
        share = total_sung * (float(weight) / total_weight)
        start = snap(at_sung_time(consumed)) if index else usable[0].start
        start = max(start, previous_end)
        consumed += share
        is_last = index == len(weights) - 1
        end = usable[-1].end if is_last else snap(at_sung_time(consumed))
        end = max(end, start + _MIN_LINE_SEC)
        out.append((round(start, 3), round(end, 3)))
        previous_end = end
    return out


def align_lines_to_spans(
    weights: Sequence[float],
    spans: Sequence[VocalSpan],
    *,
    gap_bonus: float = _GAP_BONUS,
    max_syllables_per_sec: float = _MAX_SYLLABLES_PER_SEC,
) -> list[tuple[float, float]]:
    """Assign each line a run of consecutive sung phrases (best total fit).

    A sung line is one or more detected phrases — a breath mid-line splits it in
    two — so the alignment is a segmentation of the phrase sequence into one run
    per line, chosen to keep each run close to the line's syllable share while
    preferring to break where the singer actually rested. Because every boundary
    lands on a measured onset, the highlight cannot drift away from the vocal.

    ``weights`` are syllable counts, which also bound how fast a line can
    physically be sung: a run too short for its syllables is penalised, so the
    segmentation cannot squeeze a long line into a one-word phrase.

    Returns ``[]`` when there are fewer phrases than lines; callers fall back to
    ``align_weights_to_spans``.
    """
    usable = [s for s in spans if s.length > 0]
    n_lines = len(weights)
    n_spans = len(usable)
    if not n_lines or n_spans < n_lines:
        return []

    lengths = [s.length for s in usable]
    total_sung = sum(lengths)
    total_weight = float(sum(weights)) or float(n_lines)
    targets = [total_sung * (float(w) / total_weight) for w in weights]

    gaps = [0.0] + [
        max(0.0, usable[i].start - usable[i - 1].end) for i in range(1, n_spans)
    ]
    widest_gap = max(gaps) or 1.0

    prefix = [0.0] * (n_spans + 1)
    for i, length in enumerate(lengths):
        prefix[i + 1] = prefix[i] + length

    inf = float("inf")
    cost = [[inf] * (n_spans + 1) for _ in range(n_lines + 1)]
    back = [[-1] * (n_spans + 1) for _ in range(n_lines + 1)]
    cost[0][0] = 0.0
    for line_idx in range(1, n_lines + 1):
        target = targets[line_idx - 1]
        # Leave at least one phrase for each remaining line.
        for end_span in range(line_idx, n_spans - (n_lines - line_idx) + 1):
            for start_span in range(line_idx - 1, end_span):
                previous = cost[line_idx - 1][start_span]
                if previous == inf:
                    continue
                held = prefix[end_span] - prefix[start_span]
                fit = ((held - target) / max(target, _MIN_LINE_SEC)) ** 2
                rest = gap_bonus * (gaps[start_span] / widest_gap)
                extent = usable[end_span - 1].end - usable[start_span].start
                floor_sec = float(weights[line_idx - 1]) / max(
                    1.0, max_syllables_per_sec
                )
                rushed = 0.0
                if extent < floor_sec:
                    rushed = _RUSH_PENALTY * ((floor_sec - extent) / floor_sec) ** 2
                total = previous + fit - rest + rushed
                if total < cost[line_idx][end_span]:
                    cost[line_idx][end_span] = total
                    back[line_idx][end_span] = start_span

    if cost[n_lines][n_spans] == inf:
        return []
    runs: list[tuple[int, int]] = []
    end_span = n_spans
    for line_idx in range(n_lines, 0, -1):
        start_span = back[line_idx][end_span]
        if start_span < 0:
            return []
        runs.append((start_span, end_span - 1))
        end_span = start_span
    runs.reverse()
    return [
        (round(usable[first].start, 3), round(usable[last].end, 3))
        for first, last in runs
    ]


def analyze_audio(path: str, *, line_count: int = 0) -> dict[str, object]:
    """Duration plus the sung spans of an MP3 (needs ffmpeg).

    When ``line_count`` is given, phrase detection is retried at finer settings
    until there are comfortably more phrases than lines, so the segmentation in
    ``align_lines_to_spans`` has somewhere to put every line.
    """
    pcm = decode_band_limited(path)
    envelope = smooth(
        centre_envelope(pcm), radius=max(1, int(_SMOOTH_SEC / FRAME_SEC))
    )
    duration = (len(pcm) // 2) / float(SAMPLE_RATE)
    wanted = line_count * _SPANS_PER_LINE_TARGET
    spans: list[VocalSpan] = []
    for merge_gap, min_span in _DETECTION_STEPS:
        spans = vocal_spans(
            envelope, merge_gap_sec=merge_gap, min_span_sec=min_span
        )
        if len(spans) >= wanted:
            break
    return {
        "duration_sec": round(duration, 3),
        "lead_in_sec": round(spans[0].start, 3) if spans else 0.0,
        "tail_sec": round(max(0.0, duration - spans[-1].end), 3) if spans else 0.0,
        "spans": spans,
    }


def align_song_lines(
    path: str, weights: Sequence[float]
) -> tuple[list[tuple[float, float]], dict[str, object]]:
    """Per-line (start, end) for an MP3, with the analysis that produced them."""
    analysis = analyze_audio(path, line_count=len(weights))
    spans = analysis["spans"]
    assert isinstance(spans, list)
    placed = align_lines_to_spans(weights, spans)
    method = "phrase-segmentation"
    if not placed:
        placed = align_weights_to_spans(weights, spans)
        method = "sung-time-share"
    analysis["method"] = method
    return placed, analysis
