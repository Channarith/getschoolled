"""Per-language CosyVoice census against the training floor.

A language is large enough to fine-tune when it has at least 100 unique
utterances and 20 minutes of audio. Mirrored channels that point at the same
waveform count once.
"""

from __future__ import annotations

import hashlib
import wave
from pathlib import Path
from typing import Dict, List

FLOOR_UTTERANCES = 100
FLOOR_MINUTES = 20.0


def wav_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return 0.0
            return handle.getnframes() / float(rate)
    except (wave.Error, EOFError, OSError):
        return 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _language_for(recipe: Path) -> str:
    meta_path = recipe / "meta.json"
    if meta_path.is_file():
        try:
            # language is near the top; avoid loading a huge utterances array
            # when the file is enormous by reading the header only first.
            head = meta_path.read_text(encoding="utf-8")[:4000]
            marker = '"language"'
            idx = head.find(marker)
            if idx >= 0:
                snippet = head[idx : idx + 80]
                parts = snippet.split(":", 1)
                if len(parts) == 2:
                    raw = parts[1].strip().split(",", 1)[0].strip().strip('"')
                    if raw:
                        return raw.lower()
        except OSError:
            pass
    name = recipe.parent.parent.name if recipe.parent.name == "04_cosyvoice" else recipe.name
    if name.startswith("cosyvoice_"):
        return name.split("_", 2)[1] if name.count("_") >= 2 else "und"
    return "und"


def _read_wavs(recipe: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    scp = recipe / "wav.scp"
    if not scp.is_file():
        return out
    for line in scp.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            out[parts[0]] = parts[1]
    return out


def language_census(scan_root: Path) -> List[dict]:
    """Unique utterances and minutes per language under ``scan_root``.

    Skips ``*_merged`` trees so a channel and its pool merge are not both counted.
    """
    root = Path(scan_root)
    grouped: Dict[str, Dict[str, dict]] = {}
    for scp in sorted(root.glob("cosyvoice_*/04_cosyvoice/train/wav.scp")):
        channel = scp.parents[2].name
        if channel.endswith("_merged"):
            continue
        recipe = scp.parent
        language = _language_for(recipe)
        bucket = grouped.setdefault(language, {})
        for _utt, wav in _read_wavs(recipe).items():
            audio = Path(wav)
            if not audio.is_file():
                continue
            digest = _sha256(audio)
            if digest in bucket:
                continue
            bucket[digest] = {"seconds": wav_seconds(audio)}
    rows = []
    for language in sorted(grouped):
        items = grouped[language]
        utterances = len(items)
        seconds = sum(item["seconds"] for item in items.values())
        minutes = seconds / 60.0
        rows.append(
            {
                "language": language,
                "utterances": utterances,
                "minutes": round(minutes, 2),
                "seconds": round(seconds, 3),
                "meets_floor": utterances >= FLOOR_UTTERANCES and minutes >= FLOOR_MINUTES,
                "floor_utterances": FLOOR_UTTERANCES,
                "floor_minutes": FLOOR_MINUTES,
            }
        )
    return rows


def format_census(rows: List[dict]) -> str:
    lines = [
        "language  utterances  minutes  floor_100utt_20min",
    ]
    if not rows:
        lines.append("(no channel recipes)")
    for row in rows:
        flag = "yes" if row["meets_floor"] else "no"
        lines.append(
            f"{row['language']:<10} {row['utterances']:>10}  {row['minutes']:>7.2f}  {flag}"
        )
    return "\n".join(lines) + "\n"
