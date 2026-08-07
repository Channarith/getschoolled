"""Speech / TTS helpers for course studio (speech gateway → device fallback).

Offline-safe: probing a missing speech service simply reports unavailable and
the browser/device voice is used.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .studio_languages import normalize_language, tts_needs_fallback


def speech_base_url() -> str:
    return (
        os.environ.get("SPEECH_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_SPEECH_URL")
        or "http://127.0.0.1:8002"
    ).rstrip("/")


def tts_status(timeout_s: float = 1.5) -> dict[str, Any]:
    base = speech_base_url()
    out: dict[str, Any] = {
        "speech_base_url": base,
        "available": False,
        "engine": "device",
        "offline_fallback": "device",
    }
    try:
        req = urllib.request.Request(f"{base}/tts/status", method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        out["available"] = bool(data.get("available"))
        out["engine"] = data.get("engine") or ("speech-gateway" if out["available"] else "device")
        out["raw"] = data
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def build_tts_get_url(
    text: str,
    *,
    language: str = "en",
    voice: str = "",
    instructor: str = "kind",
) -> str:
    """Build a GET /tts URI (expo-av / <audio src> friendly)."""
    lang = normalize_language(language)
    params = {
        "text": text[:1800],
        "language": lang,
        "instructor": instructor or "kind",
    }
    if voice:
        params["voice"] = voice
    return f"{speech_base_url()}/tts?{urllib.parse.urlencode(params)}"


def tts_client_hints(language: str = "en") -> dict[str, Any]:
    lang = normalize_language(language)
    status = tts_status()
    return {
        "language": lang,
        "tts_needs_fallback": tts_needs_fallback(lang),
        "speech": status,
        "engine_chain": ["elevenlabs", "edge-tts", "device"],
        "prefer_device_when_unavailable": True,
    }
