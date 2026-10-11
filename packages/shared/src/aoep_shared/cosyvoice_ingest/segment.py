"""Energy-based utterance segmentation (stdlib only; no network)."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class Segment:
    """One training-sized slice in sample indices (half-open) and seconds."""

    start_sample: int
    end_sample: int
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


def _frame_rms(samples: Sequence[int], start: int, frame: int) -> float:
    end = min(len(samples), start + frame)
    if end <= start:
        return 0.0
    acc = 0.0
    n = end - start
    for i in range(start, end):
        v = samples[i] / 32768.0
        acc += v * v
    return math.sqrt(acc / n)


def segment_pcm16(
    pcm16: bytes,
    sample_rate: int,
    *,
    min_utt_sec: float = 1.0,
    max_utt_sec: float = 12.0,
    silence_db: float = -40.0,
    frame_ms: float = 30.0,
    min_silence_sec: float = 0.35,
    pad_ms: float = 40.0,
) -> List[Segment]:
    """Split mono int16 PCM into utterance windows on sustained quiet frames.

    Falls back to fixed max-length chunks when the whole clip is continuously
    loud (no silence detected). Empty / too-short audio returns ``[]``.
    """
    if sample_rate <= 0 or len(pcm16) < 4:
        return []
    n = len(pcm16) // 2
    samples = struct.unpack("<" + "h" * n, pcm16)
    duration = n / float(sample_rate)
    if duration < min_utt_sec:
        return []

    frame = max(1, int(sample_rate * (frame_ms / 1000.0)))
    silence_rms = 10 ** (silence_db / 20.0)
    min_silence_frames = max(1, int(min_silence_sec / (frame_ms / 1000.0)))
    pad = int(sample_rate * (pad_ms / 1000.0))
    min_samples = int(sample_rate * min_utt_sec)
    max_samples = int(sample_rate * max_utt_sec)

    # Frame-level speech/silence mask
    speech: List[bool] = []
    for i in range(0, n, frame):
        speech.append(_frame_rms(samples, i, frame) >= silence_rms)

    # Find speech runs separated by >= min_silence_frames of silence
    runs: List[Tuple[int, int]] = []
    in_speech = False
    run_start = 0
    silence_run = 0
    for fi, is_sp in enumerate(speech):
        if is_sp:
            if not in_speech:
                in_speech = True
                run_start = fi
            silence_run = 0
        else:
            if in_speech:
                silence_run += 1
                if silence_run >= min_silence_frames:
                    end_fi = fi - silence_run + 1
                    runs.append((run_start, max(run_start + 1, end_fi)))
                    in_speech = False
                    silence_run = 0
    if in_speech:
        runs.append((run_start, len(speech)))

    if not runs:
        # No silence: chunk the whole file into max_utt windows
        segs: List[Segment] = []
        for start in range(0, n, max_samples):
            end = min(n, start + max_samples)
            if end - start < min_samples:
                continue
            segs.append(
                Segment(
                    start_sample=start,
                    end_sample=end,
                    start_sec=start / sample_rate,
                    end_sec=end / sample_rate,
                )
            )
        return segs

    out: List[Segment] = []
    for f0, f1 in runs:
        start = max(0, f0 * frame - pad)
        end = min(n, f1 * frame + pad)
        # Split long runs
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + max_samples)
            if chunk_end - cursor < min_samples:
                break
            out.append(
                Segment(
                    start_sample=cursor,
                    end_sample=chunk_end,
                    start_sec=cursor / sample_rate,
                    end_sec=chunk_end / sample_rate,
                )
            )
            cursor = chunk_end
    return out


def slice_pcm16(pcm16: bytes, start_sample: int, end_sample: int) -> bytes:
    """Return int16 PCM bytes for ``[start_sample, end_sample)``."""
    start = max(0, int(start_sample)) * 2
    end = max(start, int(end_sample) * 2)
    return pcm16[start:end]
