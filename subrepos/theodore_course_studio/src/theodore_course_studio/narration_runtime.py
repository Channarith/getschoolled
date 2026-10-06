"""Read-only runtime index for published gapless course narration."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_URL = ""
_CACHE_SECONDS = 60.0
_lock = threading.Lock()
_cache: dict[str, Any] = {"source": "", "loaded_at": 0.0, "stamp": None, "rows": {}}


def manifest_source() -> str:
    return (
        os.environ.get("COURSE_AUDIO_MANIFEST", "").strip()
        or os.environ.get("COURSE_AUDIO_MANIFEST_URL", "").strip()
        or DEFAULT_MANIFEST_URL
    )


def clear_manifest_cache() -> None:
    with _lock:
        _cache.update(source="", loaded_at=0.0, stamp=None, rows={})


def _read_payload(source: str) -> tuple[dict[str, Any], Any]:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=4.0) as response:
            return json.loads(response.read().decode("utf-8")), None
    path = Path(source).expanduser()
    return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime_ns


def manifest_rows() -> dict[tuple[str, str, str], dict[str, Any]]:
    source = manifest_source()
    if not source:
        return {}
    now = time.monotonic()
    with _lock:
        if (
            _cache["source"] == source
            and now - float(_cache["loaded_at"]) < _CACHE_SECONDS
        ):
            return dict(_cache["rows"])
        try:
            payload, stamp = _read_payload(source)
            if not payload.get("complete"):
                return {}
            rows = {
                (
                    str(row.get("slide_key") or ""),
                    str(row.get("language") or ""),
                    str(row.get("gender") or ""),
                ): dict(row)
                for row in payload.get("records") or []
                if row.get("slide_key") and row.get("audio_url")
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            rows = dict(_cache["rows"]) if _cache["source"] == source else {}
            _cache.update(source=source, loaded_at=now, rows=rows)
            return rows
        _cache.update(source=source, loaded_at=now, stamp=stamp, rows=rows)
        return dict(rows)


def clip_hints(
    slide_key: str,
    language: str,
    gender: str,
    *,
    next_slide_key: str = "",
) -> dict[str, Any]:
    """Return public audio/timing hints, or an empty dict for dynamic TTS."""
    lang = (language or "en").split("-")[0].lower()
    voice_gender = "male" if gender == "male" else "female"
    rows = manifest_rows()
    row = rows.get((slide_key, lang, voice_gender))
    if not row:
        return {}
    hints: dict[str, Any] = {
        "audio_url": str(row["audio_url"]),
        "duration_ms": max(1, round(float(row.get("duration") or 0) * 1000)),
        "segments": list(row.get("segments") or []),
        "manifest_version": int(row.get("version") or 1),
    }
    next_row = rows.get((next_slide_key, lang, voice_gender)) if next_slide_key else None
    if next_row:
        hints["next_audio_url"] = str(next_row["audio_url"])
    return hints
