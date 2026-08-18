"""Speech / TTS helpers for course studio.

Engine preference (most natural first for the language being spoken):
  1. Speech gateway (ElevenLabs → edge-tts) when reachable
  2. Local edge-tts in this process (covers Khmer even without the gateway)
  3. Browser / device speechSynthesis

Offline-safe: a missing gateway simply reports unavailable; a missing edge-tts
install answers 501 from /api/studio/tts and the page falls back to the device.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import neural_tts
from .studio_languages import normalize_language, tts_needs_fallback


def speech_base_url() -> str:
    return (
        os.environ.get("SPEECH_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_SPEECH_URL")
        or "http://127.0.0.1:8002"
    ).rstrip("/")


def tts_status(timeout_s: float = 1.5) -> dict[str, Any]:
    """Probe the speech gateway. Does not include the local neural engine."""
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
        out["engine"] = data.get("engine") or (
            "speech-gateway" if out["available"] else "device"
        )
        out["raw"] = data
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def normalize_voice_gender(voice_gender: str | None) -> str:
    """Collapse arbitrary input to the two personas we ship (female|male)."""
    return "male" if str(voice_gender or "").strip().lower() == "male" else "female"


def build_local_tts_get_url(
    text: str,
    *,
    language: str = "en",
    voice_gender: str = "female",
    rate: float = 1.0,
) -> str:
    """Relative URI for the studio's own neural TTS endpoint."""
    lang = normalize_language(language)
    params = {
        "text": text[:1800],
        "language": lang,
        "gender": normalize_voice_gender(voice_gender),
        "rate": f"{float(rate):.2f}",
    }
    return f"/api/studio/tts?{urllib.parse.urlencode(params)}"


def build_tts_get_url(
    text: str,
    *,
    language: str = "en",
    voice: str = "",
    instructor: str = "kind",
    voice_gender: str = "female",
) -> str:
    """Build a GET /tts URI against the speech gateway (expo-av / <audio src>)."""
    lang = normalize_language(language)
    params = {
        "text": text[:1800],
        "language": lang,
        "instructor": instructor or "kind",
        "voice_gender": normalize_voice_gender(voice_gender),
    }
    if voice:
        params["voice"] = voice
    return f"{speech_base_url()}/tts?{urllib.parse.urlencode(params)}"


def tts_client_hints(
    language: str = "en",
    voice_gender: str = "female",
    *,
    text: str = "",
) -> dict[str, Any]:
    """Hints attached to every teach payload so the page knows which engine to use.

    Preference order reported in ``engine`` / ``get_url``:
      gateway (when up) → local neural (when engine or cache ready) → device.
    """
    lang = normalize_language(language)
    gender = normalize_voice_gender(voice_gender)
    gateway = tts_status()
    local = neural_tts.status()
    local_ready = bool(local.get("available"))

    if gateway.get("available"):
        engine = gateway.get("engine") or "speech-gateway"
        get_url = build_tts_get_url(text, language=lang, voice_gender=gender) if text else ""
        source = "gateway"
    elif local_ready:
        engine = str(local.get("engine") or "edge-tts-neural")
        get_url = (
            build_local_tts_get_url(text, language=lang, voice_gender=gender)
            if text
            else "/api/studio/tts"
        )
        source = "local-neural"
    else:
        engine = "device"
        get_url = ""
        source = "device"

    return {
        "language": lang,
        "voice_gender": gender,
        # XTTS coverage flag from aoep_shared — kept for compatibility. Local
        # edge-tts covers every supported language including Khmer, so this is
        # no longer a signal that speech will fall back to English.
        "tts_needs_fallback": tts_needs_fallback(lang),
        "speech": {
            **gateway,
            "available": bool(gateway.get("available") or local_ready),
            "engine": engine,
            "source": source,
            "local": local,
        },
        "get_url": get_url,
        "local_url": (
            build_local_tts_get_url(text, language=lang, voice_gender=gender)
            if text
            else ""
        ),
        "engine_chain": ["elevenlabs", "edge-tts", "local-neural", "device"],
        "prefer_device_when_unavailable": True,
    }
