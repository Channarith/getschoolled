"""Scan labeled corpus folders and persist a lightweight index."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .labels import (
    normalize_category,
    parse_quality_label,
    should_incorporate,
    source_id_for,
    title_guess_from_filename,
)
from .types import SourceDocument

_SUPPORTED = {".pdf", ".pptx"}


def default_corpus_root() -> Path:
    env = os.environ.get("THEODORE_COURSE_CORPUS_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # Local experiment default: the Drive download the team labeled.
    candidate = Path.home() / "Downloads" / "drive-download-20260807T154004Z-1-001"
    if candidate.is_dir():
        return candidate.resolve()
    return (Path(__file__).resolve().parents[2] / "data" / "corpus").resolve()


def default_data_dir() -> Path:
    env = os.environ.get("THEODORE_COURSE_STUDIO_DATA", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "data").resolve()


def scan_corpus(root: Path | None = None) -> list[SourceDocument]:
    root = (root or default_corpus_root()).resolve()
    if not root.is_dir():
        return []
    docs: list[SourceDocument] = []
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        category = normalize_category(category_dir.name)
        for path in sorted(category_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("~$") or path.name.startswith("."):
                continue
            ext = path.suffix.lower().lstrip(".")
            if f".{ext}" not in _SUPPORTED and path.suffix.lower() not in _SUPPORTED:
                continue
            quality = parse_quality_label(path.name)
            docs.append(
                SourceDocument(
                    source_id=source_id_for(path, category),
                    category=category,
                    category_folder=category_dir.name,
                    filename=path.name,
                    path=str(path),
                    ext=ext if ext in {"pdf", "pptx"} else path.suffix.lower().lstrip("."),
                    quality_label=quality,
                    title_guess=title_guess_from_filename(path.name),
                    incorporate=should_incorporate(quality),
                )
            )
    return docs


def write_corpus_index(docs: list[SourceDocument], data_dir: Path | None = None) -> Path:
    data_dir = data_dir or default_data_dir()
    out_dir = data_dir / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.json"
    payload = {
        "updated_at_ms": int(time.time() * 1000),
        "count": len(docs),
        "documents": [d.model_dump(mode="json") for d in docs],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def load_corpus_index(data_dir: Path | None = None) -> list[SourceDocument]:
    data_dir = data_dir or default_data_dir()
    path = data_dir / "corpus" / "index.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SourceDocument.model_validate(row) for row in raw.get("documents", [])]
