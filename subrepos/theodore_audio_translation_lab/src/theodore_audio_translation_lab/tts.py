"""Server-side neural speech for Theodore, with honest degradation.

The lab could only ever speak through the browser's own ``speechSynthesis``. That
works, but the device voice for most of the 27 supported languages is robotic or
missing entirely, so a Khmer or Chinese reply either sounded wrong or stayed
silent while the UI claimed it had spoken.

Engine chain, most natural first (matching the platform's speech convention):

  speech gateway /tts  ->  ElevenLabs  ->  edge-tts neural  ->  (none)

Nothing here is required. With no gateway, no key and no edge-tts installed,
``synthesize`` raises ``ProviderUnavailable`` and the caller returns HTTP 501 so
the page falls back to the device voice instead of going quiet.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .languages import LANGUAGE_NAMES, normalize_language
from .providers import ProviderUnavailable

# edge-tts ships no voice for every language; these cover the lab's set well and
# can each be overridden with AOEP_TTS_VOICE_<LANG> (e.g. AOEP_TTS_VOICE_KM).
# Full platform 27 (plus a few extras). Missing cs/el previously fell back to
# English voices and sounded "partial" in the lab UI.
_EDGE_VOICES = {
    "en": "en-US-AriaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-ZofiaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "uk": "uk-UA-PolinaNeural",
    "tr": "tr-TR-EmelNeural",
    "ar": "ar-EG-SalmaNeural",
    "he": "he-IL-HilaNeural",
    "hi": "hi-IN-SwaraNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ta": "ta-IN-PallaviNeural",
    "ur": "ur-PK-UzmaNeural",
    "fa": "fa-IR-DilaraNeural",
    "id": "id-ID-GadisNeural",
    "ms": "ms-MY-YasminNeural",
    "th": "th-TH-PremwadeeNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "km": "km-KH-SreymomNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "sw": "sw-KE-ZuriNeural",
    "el": "el-GR-AthinaNeural",
    "cs": "cs-CZ-VlastaNeural",
}

MAX_TTS_CHARS = 1200


def _gateway_url() -> str:
    return (
        os.environ.get("TTS_BASE_URL")
        or os.environ.get("SPEECH_BASE_URL")
        or ""
    ).rstrip("/")


def _elevenlabs_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


def _edge_voice(language: str) -> str:
    override = os.environ.get(f"AOEP_TTS_VOICE_{language.upper()}", "").strip()
    return override or _EDGE_VOICES.get(language, _EDGE_VOICES["en"])


def _edge_tts_available() -> bool:
    if shutil.which("edge-tts"):
        return True
    try:
        import edge_tts  # noqa: F401
    except Exception:  # noqa: BLE001 - any import failure means unavailable
        return False
    return True


def engine_chain() -> list[str]:
    """Engines that could serve a request right now, best first."""
    chain: list[str] = []
    if _gateway_url():
        chain.append("speech-gateway")
    if _elevenlabs_key():
        chain.append("elevenlabs")
    if _edge_tts_available():
        chain.append("edge-tts")
    return chain


def tts_status() -> dict[str, object]:
    """What the client should expect before it starts a lesson.

    Probed once by the page so it does not attempt a server round-trip per reply
    when nothing is configured.
    """
    chain = engine_chain()
    platform = list(LANGUAGE_NAMES)
    return {
        "available": bool(chain),
        "engine": chain[0] if chain else "",
        "engines": chain,
        "gateway_url": _gateway_url(),
        "languages": sorted(_EDGE_VOICES),
        "platform_languages": platform,
        "platform_language_count": len(platform),
        "edge_covers_platform": all(code in _EDGE_VOICES for code in platform),
        "note": (
            f"Server neural speech via {' → '.join(chain)}."
            if chain
            else "No server TTS configured; the page uses the device voice. "
            "Set TTS_BASE_URL/SPEECH_BASE_URL, ELEVENLABS_API_KEY, or install edge-tts."
        ),
    }


def synthesize(text: str, *, language: str = "en", style: str = "warm") -> tuple[bytes, str, str]:
    """Render ``text`` to audio. Returns ``(audio_bytes, mime_type, engine)``.

    Raises ``ProviderUnavailable`` when no engine can serve the request, which the
    API surfaces as 501 so the client falls back to its own voice.
    """
    clean = (text or "").strip()
    if not clean:
        raise ValueError("tts text is empty")
    if len(clean) > MAX_TTS_CHARS:
        clean = clean[:MAX_TTS_CHARS]
    lang = normalize_language(language) or "en"

    errors: list[str] = []
    for engine in engine_chain():
        try:
            if engine == "speech-gateway":
                return (*_gateway_tts(clean, lang, style), "speech-gateway")
            if engine == "elevenlabs":
                return (*_elevenlabs_tts(clean, lang), "elevenlabs")
            if engine == "edge-tts":
                return (*_edge_tts(clean, lang), "edge-tts")
        except Exception as exc:  # noqa: BLE001 - try the next engine
            errors.append(f"{engine}: {exc}")

    detail = f" Tried: {'; '.join(errors)}" if errors else ""
    raise ProviderUnavailable(
        f"No server TTS engine could render {LANGUAGE_NAMES.get(lang, lang)}."
        f"{detail} Configure TTS_BASE_URL/SPEECH_BASE_URL, ELEVENLABS_API_KEY, "
        "or install edge-tts; the client can still use the device voice."
    )


def _gateway_tts(text: str, language: str, style: str) -> tuple[bytes, str]:
    base = _gateway_url()
    request = urllib.request.Request(
        f"{base}/tts",
        data=json.dumps({"text": text, "language": language, "style": style}).encode(),
        headers={"Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    timeout = float(os.environ.get("TTS_TIMEOUT_S", "20"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            audio = response.read()
            mime = response.headers.get("Content-Type") or "audio/mpeg"
    except urllib.error.HTTPError as exc:
        # 501 is the gateway's documented "no engine here", not a bug.
        raise ProviderUnavailable(f"gateway HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ProviderUnavailable(f"gateway unreachable: {exc.reason}") from exc
    if len(audio) < 256:
        raise ProviderUnavailable("gateway returned no audio")
    return audio, mime


def _elevenlabs_tts(text: str, language: str) -> tuple[bytes, str]:
    voice_id = (
        os.environ.get(f"ELEVENLABS_VOICE_{language.upper()}", "").strip()
        or os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
        or "EXAVITQu4vr4xnSDxMaL"  # Bella — warm, friendly, multilingual
    )
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps(
            {
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.6,
                    "similarity_boost": 0.8,
                    "style": 0.15,
                    "use_speaker_boost": True,
                },
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "xi-api-key": _elevenlabs_key(),
        },
        method="POST",
    )
    timeout = float(os.environ.get("TTS_TIMEOUT_S", "30"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            audio = response.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        raise ProviderUnavailable(f"ElevenLabs HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderUnavailable(f"ElevenLabs unreachable: {exc.reason}") from exc
    if len(audio) < 256:
        raise ProviderUnavailable("ElevenLabs returned no audio")
    return audio, "audio/mpeg"


def _last_error_line(stderr: bytes | None) -> str:
    """Summarise a subprocess failure.

    edge-tts prints a full Python traceback; the useful part is the final
    exception line. Surfacing the whole thing turns the operator-facing warning
    into an unreadable wall of aiohttp frames.
    """
    text = (stderr or b"").decode("utf-8", errors="replace").strip()
    if not text:
        return "no output"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if not line.startswith(("File \"", "Traceback", "  ", "^")):
            return line[:160]
    return lines[-1][:160]


def _edge_tts(text: str, language: str) -> tuple[bytes, str]:
    """Local neural voices via the edge-tts CLI. No key, but needs network."""
    if not shutil.which("edge-tts"):
        raise ProviderUnavailable("edge-tts CLI not on PATH")
    voice = _edge_voice(language)
    timeout = float(os.environ.get("TTS_TIMEOUT_S", "30"))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reply.mp3"
        try:
            subprocess.run(
                ["edge-tts", "--voice", voice, "--text", text, "--write-media", str(out)],
                check=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            raise ProviderUnavailable(
                f"edge-tts failed: {_last_error_line(exc.stderr)}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailable("edge-tts timed out") from exc
        if not out.is_file() or out.stat().st_size < 256:
            raise ProviderUnavailable("edge-tts wrote no audio")
        return out.read_bytes(), "audio/mpeg"
