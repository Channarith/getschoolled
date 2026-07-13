"""CosyVoice 2 text-to-speech client (self-hosted inference server).

CosyVoice 2 (FunAudioLLM) is a streaming, zero-shot, multilingual TTS model that
you host yourself (a GPU is recommended). Unlike ElevenLabs there is no public
SaaS API, so this module is a thin HTTP client: point ``COSYVOICE_URL`` at your
CosyVoice 2 inference server and the speech gateway renders narration through it,
preferred over ElevenLabs / edge-tts when configured (Drive Mode audio dictation
and live-class narration, on both web and mobile — they consume the same /tts).

Expected server contract (a small wrapper around ``CosyVoice2``):

    POST  {COSYVOICE_URL}{COSYVOICE_PATH}          (default path: /tts)
    JSON  {"text","language","speaker","instruct","mode","sample_rate"}
    ->    HTTP 200, body = audio bytes; Content-Type audio/wav or audio/mpeg

``COSYVOICE_MODE`` (or the per-request default derived below) selects the model
mode: ``instruct2`` (natural-language style control), ``zero_shot``/``sft``
(speaker id), or ``cross_lingual``. Optional bearer auth via ``COSYVOICE_API_KEY``.

Pure stdlib (``urllib``) so it adds no dependency; the HTTP call is isolated in
:func:`_http_post` so tests can mock it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional, Tuple

DEFAULT_PATH = "/tts"
DEFAULT_SAMPLE_RATE = 24000   # CosyVoice 2 native output rate


class CosyVoiceError(RuntimeError):
    """Raised when the CosyVoice 2 inference server call fails."""


def _base_url(base_url: Optional[str] = None) -> str:
    url = base_url if base_url is not None else os.environ.get("COSYVOICE_URL", "")
    return (url or "").strip().rstrip("/")


def cosyvoice_configured(base_url: Optional[str] = None) -> bool:
    """True when a CosyVoice 2 inference server URL is configured."""
    return bool(_base_url(base_url))


def _mode_for(instruct: str, speaker: str) -> str:
    """Pick a CosyVoice 2 inference mode when the operator hasn't forced one.

    - an instruction ("speak cheerfully…") -> instruct2 (natural-language control)
    - a known speaker id -> zero_shot (reference the enrolled speaker)
    - neither -> cross_lingual (default multilingual voice)
    """
    forced = os.environ.get("COSYVOICE_MODE", "").strip()
    if forced:
        return forced
    if instruct.strip():
        return "instruct2"
    if speaker.strip():
        return "zero_shot"
    return "cross_lingual"


def synthesize(
    text: str,
    *,
    base_url: Optional[str] = None,
    language: str = "en",
    speaker: str = "",
    instruct: str = "",
    mode: str = "",
    api_key: Optional[str] = None,
    path: str = "",
    timeout: float = 45.0,
) -> Tuple[bytes, str]:
    """Render ``text`` to audio via a CosyVoice 2 server. Returns (bytes, content_type).

    Raises :class:`CosyVoiceError` on any failure so the gateway can fall back to
    ElevenLabs / edge-tts / the on-device voice.
    """
    narration = (text or "").strip()
    if not narration:
        raise CosyVoiceError("empty narration")
    url = _base_url(base_url)
    if not url:
        raise CosyVoiceError("COSYVOICE_URL is not set")
    key = api_key if api_key is not None else os.environ.get("COSYVOICE_API_KEY", "")
    endpoint = url + (path or os.environ.get("COSYVOICE_PATH", "") or DEFAULT_PATH)
    body = json.dumps({
        "text": narration,
        "language": language or "en",
        "speaker": speaker or "",
        "instruct": instruct or "",
        "mode": mode or _mode_for(instruct or "", speaker or ""),
        "sample_rate": DEFAULT_SAMPLE_RATE,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "audio/wav, audio/mpeg"}
    if (key or "").strip():
        headers["Authorization"] = f"Bearer {key.strip()}"

    audio, content_type = _http_post(endpoint, data=body, headers=headers, timeout=timeout)
    if not audio or len(audio) < 256:
        raise CosyVoiceError("CosyVoice returned no audio")
    return audio, (content_type or "audio/wav")


def _http_post(url: str, *, data: bytes, headers: dict, timeout: float) -> Tuple[bytes, str]:
    """POST ``data`` and return (response body, content-type). Isolated for testing."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise CosyVoiceError(f"CosyVoice HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CosyVoiceError(f"CosyVoice unreachable: {exc.reason}") from exc
