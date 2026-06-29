"""Generic content-pack loader — the data-driven growth backbone.

Every large content dimension of the platform (knowledge facts, slang/idioms,
training scenarios, courses, presentation techniques) can be grown by orders of
magnitude purely by dropping JSON / JSONL *packs* into a packs directory — no
code changes required. Built-in Python content remains the baseline; packs are
merged on top.

Pack discovery roots (searched in order, all merged):
1. The packaged baseline dir shipped with the library
   (``aoep_shared/data/content_packs/<kind>/``).
2. Extra roots from the ``AOEP_CONTENT_PACKS`` env var (os.pathsep-separated),
   each containing ``<kind>/`` subdirectories.

Each ``<kind>/`` dir may contain any number of ``*.json`` (a list of records, or
an object with a ``records``/``<kind>`` list) or ``*.jsonl`` (one record per
line) files. Records are plain dicts whose schema is defined by each consumer.

Pure/stdlib-only and safe: malformed files are skipped rather than raising, so a
bad pack can never take the platform down.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

KNOWN_KINDS = ("knowledge", "slang", "scenarios", "courses", "presentation")


def _packaged_root() -> Path:
    return Path(__file__).resolve().parent / "data" / "content_packs"


def pack_roots() -> List[Path]:
    roots = [_packaged_root()]
    env = os.environ.get("AOEP_CONTENT_PACKS", "")
    for part in env.split(os.pathsep):
        part = part.strip()
        if part:
            roots.append(Path(part))
    return roots


def _pack_files(kind: str) -> List[Path]:
    files: List[Path] = []
    for root in pack_roots():
        d = root / kind
        if not d.is_dir():
            continue
        files.extend(sorted(d.glob("*.json")))
        files.extend(sorted(d.glob("*.jsonl")))
    return files


def _read_records(path: Path, kind: str) -> List[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: List[dict] = []
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
        return out
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        records = data.get("records") or data.get(kind) or []
    elif isinstance(data, list):
        records = data
    else:
        records = []
    return [r for r in records if isinstance(r, dict)]


def load_records(kind: str) -> List[dict]:
    """Return all records for ``kind`` merged across every pack root/file."""
    fp = _fingerprint(kind)
    return list(_load_cached(kind, fp))


@lru_cache(maxsize=None)
def _load_cached(kind: str, fingerprint: str) -> tuple:
    records: List[dict] = []
    for path in _pack_files(kind):
        records.extend(_read_records(path, kind))
    return tuple(records)


def _fingerprint(kind: str) -> str:
    h = hashlib.sha256()
    n = 0
    for path in _pack_files(kind):
        try:
            st = path.stat()
        except OSError:
            continue
        h.update(path.name.encode("utf-8"))
        h.update(str(st.st_size).encode("utf-8"))
        h.update(str(int(st.st_mtime)).encode("utf-8"))
        n += 1
    return f"{n}:{h.hexdigest()[:12]}"


def pack_fingerprint(kind: str) -> str:
    """Stable signature of the packs for ``kind`` (for cache invalidation)."""
    return _fingerprint(kind)


def pack_file_count(kind: str) -> int:
    return len(_pack_files(kind))


def pack_record_count(kind: str) -> int:
    return len(load_records(kind))


def pack_summary() -> Dict[str, dict]:
    return {
        kind: {
            "files": pack_file_count(kind),
            "records": pack_record_count(kind),
            "fingerprint": pack_fingerprint(kind),
        }
        for kind in KNOWN_KINDS
    }
