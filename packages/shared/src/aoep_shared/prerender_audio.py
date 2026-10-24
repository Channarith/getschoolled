"""Pre-rendered narration audio: render once on the Spark, serve as static files.

Files are named by a hash of (language, normalized text), so a passage that
repeats across courses is rendered once. The speech gateway looks a request up
here before it asks any live TTS engine, and falls back to the live chain when
nothing is stored. Set AOEP_PRERENDER_AUDIO_DIR to enable.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Tuple

ENV_DIR = "AOEP_PRERENDER_AUDIO_DIR"
EXTENSIONS = {".wav": "audio/wav", ".mp3": "audio/mpeg"}


def narration_line(heading: str, text: str) -> str:
    """The exact string the On the Go player speaks for one segment."""
    return f"{heading}. {text}"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def audio_key(text: str, language: str = "en") -> str:
    payload = f"{(language or 'en').lower()}\n{normalize(text)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def store_dir(path: Optional[str] = None) -> Optional[Path]:
    raw = path if path is not None else os.environ.get(ENV_DIR, "")
    raw = (raw or "").strip()
    return Path(raw) if raw else None


def find(text: str, language: str = "en", directory: Optional[Path] = None) -> Optional[Path]:
    base = directory if directory is not None else store_dir()
    if base is None:
        return None
    key = audio_key(text, language)
    for ext in EXTENSIONS:
        candidate = base / f"{key}{ext}"
        if candidate.is_file() and candidate.stat().st_size > 256:
            return candidate
    return None


def lookup(text: str, language: str = "en", directory: Optional[Path] = None) -> Optional[Tuple[bytes, str]]:
    found = find(text, language, directory)
    if not found:
        return None
    try:
        return found.read_bytes(), EXTENSIONS[found.suffix]
    except OSError:
        return None
