"""Choose already-downloaded Khmer raw wavs for a voice-data batch.

The YouTube queue is not contacted. Callers pass a directory that already
holds ``cosyvoice_km_*/01_raw/*.wav`` from an earlier operator download.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, List, Optional


# Lesson-style channels first. Mirror directory names share a media stem, so
# the longer file is kept and the duplicate directory is not ingested again.
LESSON_CHANNELS = (
    "cosyvoice_km_easykhmer",
    "cosyvoice_km_easykhmerofficial",
    "cosyvoice_km_danychhe",
    "cosyvoice_km_cutieaianimation",
    "cosyvoice_km_cutie_ai_animation",
    "cosyvoice_km_dara",
    "cosyvoice_km_languagelearningproject",
    "cosyvoice_km_language_learning_project",
)

# Long narration. Callers clip ``take_sec`` from the start instead of
# denoising a multi-hour file in one Python buffer.
NARRATION_CHANNELS = (
    "cosyvoice_km_buddhist_stories_playlist",
    "cosyvoice_km_playlist_PL_keyel3BP9monFH05ExcwuqPTrqrlECt",
)


def wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate() or 1
            return handle.getnframes() / float(rate)
    except (wave.Error, OSError, EOFError):
        return 0.0


def _channel_rank(name: str, order: tuple[str, ...]) -> int:
    try:
        return order.index(name)
    except ValueError:
        return len(order)


def select_local_khmer(
    scan_root: Path | str,
    *,
    lesson_budget_sec: float = 20 * 60,
    lesson_max_file_sec: float = 20 * 60,
    narration_head_sec: float = 8 * 60,
    narration_files: int = 2,
) -> List[dict]:
    """Return raw files to stage, unique by wav stem.

    Each item is ``channel``, ``stem``, ``path``, ``duration_sec``, ``take_sec``.
    ``take_sec`` is None when the whole file should be used.
    """
    root = Path(scan_root)
    best: Dict[str, tuple] = {}
    for channel_dir in sorted(root.glob("cosyvoice_km*")):
        if not channel_dir.is_dir() or channel_dir.name.endswith("_merged"):
            continue
        raw = channel_dir / "01_raw"
        if not raw.is_dir():
            continue
        lesson = channel_dir.name in LESSON_CHANNELS
        narration = channel_dir.name in NARRATION_CHANNELS
        if not lesson and not narration:
            continue
        for wav in raw.glob("*.wav"):
            duration = wav_duration_seconds(wav)
            if duration <= 0:
                continue
            rank = _channel_rank(
                channel_dir.name, LESSON_CHANNELS if lesson else NARRATION_CHANNELS
            )
            prev = best.get(wav.stem)
            # Prefer the longer copy, then the earlier channel in the priority list.
            if prev is not None and (prev[0] > duration or (prev[0] == duration and prev[1] <= rank)):
                continue
            best[wav.stem] = (duration, rank, channel_dir.name, wav, "lesson" if lesson else "narration")

    chosen: List[dict] = []
    lesson_left = float(lesson_budget_sec)
    lessons = [item for item in best.values() if item[4] == "lesson"]
    lessons.sort(key=lambda item: (item[1], -item[0]))
    for duration, _rank, channel, wav, _kind in lessons:
        if lesson_left <= 0:
            break
        if duration > lesson_max_file_sec:
            continue
        chosen.append(
            {
                "channel": channel,
                "stem": wav.stem,
                "path": wav,
                "duration_sec": duration,
                "take_sec": None,
                "kind": "lesson",
            }
        )
        lesson_left -= duration

    narrations = [item for item in best.values() if item[4] == "narration"]
    narrations.sort(key=lambda item: (item[1], item[0]))
    seen_channel_files = 0
    for duration, _rank, channel, wav, _kind in narrations:
        if seen_channel_files >= narration_files:
            break
        # One stem can appear in both playlist mirrors; best{} already deduped.
        chosen.append(
            {
                "channel": channel,
                "stem": wav.stem,
                "path": wav,
                "duration_sec": duration,
                "take_sec": float(narration_head_sec) if duration > narration_head_sec else None,
                "kind": "narration",
            }
        )
        seen_channel_files += 1
    return chosen


def empty_reason(scan_root: Optional[Path], rows: List[dict]) -> str:
    if rows:
        return ""
    if scan_root is None or not Path(scan_root).is_dir():
        return "no_local_raw_root"
    return "no_matching_raw_wavs"
