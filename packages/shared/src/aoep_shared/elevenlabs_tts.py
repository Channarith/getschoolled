"""ElevenLabs text-to-speech client for natural, cultural narration.

ElevenLabs' ``eleven_multilingual_v2`` model produces the most natural,
human-sounding, culturally-accented voices we can offer. The speech gateway
renders Drive Mode / live-class narration with it when ``ELEVENLABS_API_KEY`` is
set, and otherwise falls back to edge-tts neural voices and finally to the
browser's on-device voice.

Pure stdlib (``urllib``) so it works everywhere without adding a dependency, and
the HTTP call is isolated in :func:`_http_post` so tests can mock it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Dict, Optional

API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL = "eleven_multilingual_v2"

# Premade ElevenLabs voice IDs (public catalog). The multilingual model speaks
# every supported language with the same voice, adopting the right accent, so we
# map by narration *style* rather than per-language. Override any of these with
# ELEVENLABS_VOICE_ID (single global voice) or ELEVENLABS_VOICE_<STYLE>.
_STYLE_VOICES: Dict[str, str] = {
    "standard": "21m00Tcm4TlvDq8ikWAM",   # Rachel  - calm, clear narrator
    "warm": "EXAVITQu4vr4xnSDxMaL",        # Bella   - warm, friendly
    "energetic": "pNInz6obpgDQGcFmaJgB",   # Adam    - upbeat, engaging
    "calm": "oWAxZDx7w5VEj9dCyTzz",        # Grace   - soft, soothing
    "storyteller": "ErXwobaYiN019PkySvjV", # Antoni  - expressive
}
DEFAULT_VOICE_ID = _STYLE_VOICES["standard"]


class ElevenLabsError(RuntimeError):
    """Raised when the ElevenLabs API call fails."""


def elevenlabs_configured(api_key: Optional[str] = None) -> bool:
    key = api_key if api_key is not None else os.environ.get("ELEVENLABS_API_KEY", "")
    return bool((key or "").strip())


def voice_id_for(style: str = "standard", *, override: str = "") -> str:
    """Resolve the ElevenLabs voice id for a narration style.

    Precedence: explicit ``override`` > ELEVENLABS_VOICE_<STYLE> env >
    ELEVENLABS_VOICE_ID env (global) > built-in style map > default.
    """
    if override and override.strip():
        return override.strip()
    style_key = (style or "standard").strip().lower()
    env_style = os.environ.get(f"ELEVENLABS_VOICE_{style_key.upper()}", "").strip()
    if env_style:
        return env_style
    env_global = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if env_global:
        return env_global
    return _STYLE_VOICES.get(style_key, DEFAULT_VOICE_ID)


def _voice_settings(style: str) -> Dict[str, float]:
    """Per-style stability/similarity so delivery matches the requested tone."""
    style_key = (style or "standard").strip().lower()
    presets = {
        "standard": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
        "warm": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.15},
        "energetic": {"stability": 0.35, "similarity_boost": 0.7, "style": 0.45},
        "calm": {"stability": 0.75, "similarity_boost": 0.75, "style": 0.0},
        "storyteller": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.5},
    }
    settings = presets.get(style_key, presets["standard"])
    return {**settings, "use_speaker_boost": True}


def _http_post(url: str, *, data: bytes, headers: Dict[str, str], timeout: float) -> bytes:
    """POST ``data`` and return the raw response body. Isolated for testing."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise ElevenLabsError(f"ElevenLabs HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ElevenLabsError(f"ElevenLabs unreachable: {exc.reason}") from exc
    except Exception as exc:
        # Read timeouts (TimeoutError), IncompleteRead, RemoteDisconnected and
        # friends must not escape the documented ElevenLabsError contract —
        # callers build their fallback chain on it.
        raise ElevenLabsError(f"ElevenLabs request failed: {exc}") from exc


def synthesize(
    text: str,
    *,
    api_key: str,
    language: str = "en",
    style: str = "standard",
    voice_id: str = "",
    model: str = DEFAULT_MODEL,
    timeout: float = 30.0,
) -> bytes:
    """Render ``text`` to MP3 bytes via ElevenLabs. Raises ElevenLabsError.

    ``language`` is accepted for a consistent interface (the multilingual model
    auto-detects language); it is not sent as a hard constraint so mixed-script
    narration still reads correctly.
    """
    narration = (text or "").strip()
    if not narration:
        raise ElevenLabsError("empty narration")
    if not (api_key or "").strip():
        raise ElevenLabsError("ELEVENLABS_API_KEY is not set")
    vid = voice_id_for(style, override=voice_id)
    body = json.dumps({
        "text": narration,
        "model_id": model or DEFAULT_MODEL,
        "voice_settings": _voice_settings(style),
    }).encode("utf-8")
    headers = {
        "xi-api-key": api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    audio = _http_post(
        f"{API_BASE}/{vid}", data=body, headers=headers, timeout=timeout,
    )
    if not audio or len(audio) < 256:
        raise ElevenLabsError("ElevenLabs returned no audio")
    return audio
