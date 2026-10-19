"""Licensed public speech corpora that are not YouTube or Vimeo URLs.

FLEURS Khmer (google/fleurs, CC-BY-4.0) ships a TSV of gold transcripts beside
the audio tarballs. Those lines are not valid yt-dlp URLs, so they stay out of
``urls/cosyvoice_*_all.txt``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List


def parse_fleurs_tsv(path: Path | str) -> List[dict]:
    """Parse a FLEURS ``{split}.tsv`` (no header).

    Columns used: sentence id, wav filename, raw text, normalized text.
    Later columns (character tokenization, sample count) are ignored.
    The normalized column is the training text. Speaker ids are not in this
    file; callers label the corpus, not a person.
    """
    rows: List[dict] = []
    text = Path(path).read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        filename = Path(parts[1].strip()).name
        if not filename:
            continue
        raw = parts[2].strip()
        normalized = parts[3].strip() or raw
        rows.append(
            {
                "line": lineno,
                "sentence_id": parts[0].strip(),
                "filename": filename,
                "raw_text": raw,
                "text": normalized,
            }
        )
    return rows


def index_wavs(root: Path | str) -> Dict[str, Path]:
    """Map wav filename to path. The first path wins when names collide."""
    found: Dict[str, Path] = {}
    base = Path(root)
    if not base.exists():
        return found
    for path in base.rglob("*.wav"):
        found.setdefault(path.name, path)
    return found


def pair_fleurs_rows(rows: Iterable[dict], wavs: Dict[str, Path]) -> tuple[list[dict], int]:
    """Attach audio paths. Returns (paired, missing_audio)."""
    paired: List[dict] = []
    missing = 0
    for row in rows:
        audio = wavs.get(row["filename"])
        if audio is None:
            missing += 1
            continue
        item = dict(row)
        item["wav"] = audio
        paired.append(item)
    return paired, missing
