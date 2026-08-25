"""Shared neural TTS for Theodore labs (gateway → ElevenLabs → edge-tts).

Matches the platform speech convention used by web/mobile and the speech
gateway. Labs call ``synthesize`` from ``/api/tts``; browser pages play the
MP3 via ``Audio`` and only fall back to ``speechSynthesis`` when the server
returns 501.

Latency rule: once an engine fails (dead gateway, bad key), it is disabled for
the process so later turns do not wait on a timeout — that was the classic
"hiccup" when ``SPEECH_BASE_URL`` pointed at a stopped speech service.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from aoep_shared.languages import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, normalize_language

# edge-tts voices covering the platform language set (override with
# AOEP_TTS_VOICE_<LANG>).
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

# How long a failed engine stays benched. The point of benching one is to avoid
# re-waiting on a timeout for every line; a permanent bench was worse, because a
# single blip (a lab started before the network was up, a momentary DNS failure)
# killed neural speech until someone restarted the process — and the lab then
# reported "available: false" forever with no way back.
ENGINE_COOLDOWN_SEC = float(os.environ.get("TTS_ENGINE_COOLDOWN_S", "60"))

# engine name -> monotonic time it may be retried.
_engine_retry_at: dict[str, float] = {}

# engine name -> why it was benched. Only the FIRST failure could name a cause,
# because once an engine is benched the chain is empty and there is nothing left
# to report; every later 501 then fell back to the generic "install edge-tts"
# advice even though edge-tts was installed and the real fault was that this
# process could not resolve the voice host. Keeping the reason makes each
# response say what actually broke.
_engine_error: dict[str, str] = {}


class ProviderUnavailable(RuntimeError):
    """No configured TTS engine could render audio."""


def _bench_engine(engine: str, reason: str = "") -> None:
    _engine_retry_at[engine] = time.monotonic() + ENGINE_COOLDOWN_SEC
    if reason:
        _engine_error[engine] = reason


def _benched(engine: str) -> bool:
    """True while ``engine`` is still inside its cooldown.

    Must not mutate ``_engine_retry_at``. The status endpoint iterates that
    dict; deleting expired keys from the predicate crashed CI (and the live
    ``/api/tts/status`` handler) with "dictionary changed size during iteration"
    the moment a bench aged out.
    """
    until = _engine_retry_at.get(engine)
    return until is not None and time.monotonic() < until


def _sweep_expired_benches() -> None:
    now = time.monotonic()
    for engine, until in list(_engine_retry_at.items()):
        if now >= until:
            _engine_retry_at.pop(engine, None)
            _engine_error.pop(engine, None)


def _benched_names() -> list[str]:
    _sweep_expired_benches()
    return sorted(_engine_retry_at)


def reset_disabled_engines() -> None:
    """Test helper — clear the fail-fast bench."""
    _engine_retry_at.clear()
    _engine_error.clear()


def gateway_url() -> str:
    """Speech gateway base URL.

    Empty when unset or explicitly disabled (``0`` / ``off`` / ``none`` /
    ``false``). Set ``SPEECH_BASE_URL`` (or ``TTS_BASE_URL``) in
    ``config/local.env`` — the example points at ``http://127.0.0.1:8002``.
    """
    raw = (
        os.environ.get("TTS_BASE_URL")
        or os.environ.get("SPEECH_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_SPEECH_URL")
        or ""
    ).strip()
    if raw.lower() in {"0", "off", "none", "false"}:
        return ""
    return raw.rstrip("/")


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
    except Exception:  # noqa: BLE001
        return False
    return True


def configured_engines() -> list[str]:
    """Engines that *could* serve a request (before fail-fast disables)."""
    chain: list[str] = []
    if gateway_url():
        chain.append("speech-gateway")
    if _elevenlabs_key():
        chain.append("elevenlabs")
    if _edge_tts_available():
        chain.append("edge-tts")
    return chain


def engine_chain() -> list[str]:
    """Live engines, best first, excluding ones cooling off after a failure."""
    return [e for e in configured_engines() if not _benched(e)]


def _status_note(chain: list[str]) -> str:
    if chain:
        return f"Server neural speech via {' → '.join(chain)}."
    benched = _benched_names()
    if benched:
        # Telling someone to "install edge-tts" when it is installed and simply
        # could not reach its voice service sent this diagnosis the wrong way.
        return (
            f"{', '.join(benched)} is installed but its last render failed, so it "
            "is cooling off; the page uses the device voice until it is retried. "
            "Check that this process can reach the voice service."
        )
    return (
        "No server TTS configured; the page uses the device voice. "
        "Set SPEECH_BASE_URL/TTS_BASE_URL, ELEVENLABS_API_KEY, or install edge-tts."
    )


def tts_status() -> dict[str, object]:
    chain = engine_chain()
    disabled = _benched_names()
    now = time.monotonic()
    return {
        "available": bool(chain),
        "engine": chain[0] if chain else "",
        "engines": chain,
        "disabled": disabled,
        "retry_in_sec": max(
            (round(until - now) for until in _engine_retry_at.values() if until > now),
            default=0,
        ),
        "gateway_url": gateway_url(),
        "elevenlabs_configured": bool(_elevenlabs_key()),
        "xai_configured": bool(os.environ.get("XAI_API_KEY", "").strip()),
        "languages": sorted(set(_EDGE_VOICES) | set(SUPPORTED_LANGUAGES)),
        "note": _status_note(chain),
    }


def synthesize(text: str, *, language: str = "en", style: str = "warm") -> tuple[bytes, str, str]:
    """Render ``text`` to audio. Returns ``(audio_bytes, mime_type, engine)``."""
    clean = (text or "").strip()
    if not clean:
        raise ValueError("tts text is empty")
    if len(clean) > MAX_TTS_CHARS:
        clean = clean[:MAX_TTS_CHARS]
    lang = normalize_language(language) or "en"

    errors: list[str] = []
    for engine in list(engine_chain()):
        try:
            if engine == "speech-gateway":
                return (*_gateway_tts(clean, lang, style), "speech-gateway")
            if engine == "elevenlabs":
                return (*_elevenlabs_tts(clean, lang), "elevenlabs")
            if engine == "edge-tts":
                return (*_edge_tts(clean, lang), "edge-tts")
        except Exception as exc:  # noqa: BLE001 — try next; bench flaky engines
            errors.append(f"{engine}: {exc}")
            _bench_engine(engine, str(exc))

    if not errors:
        # Nothing was even attempted. Say whether that is because an engine is
        # cooling off (and why it failed) or because none is configured at all,
        # instead of advising an install that is already done.
        errors = [
            f"{engine} (cooling off {round(until - time.monotonic())}s): "
            f"{_engine_error.get(engine, 'render failed')}"
            for engine, until in sorted(_engine_retry_at.items())
            if _benched(engine)
        ]
    detail = f" Tried: {'; '.join(errors)}" if errors else ""
    advice = (
        "Check that this process can reach the voice service"
        if any(_benched(engine) for engine in _engine_retry_at)
        else "Configure SPEECH_BASE_URL/TTS_BASE_URL, ELEVENLABS_API_KEY, or install edge-tts"
    )
    raise ProviderUnavailable(
        f"No server TTS engine could render {LANGUAGE_NAMES.get(lang, lang)}."
        f"{detail} {advice}; the client can still use the device voice."
    )


def _gateway_tts(text: str, language: str, style: str) -> tuple[bytes, str]:
    base = gateway_url()
    request = urllib.request.Request(
        f"{base}/tts",
        data=json.dumps({"text": text, "language": language, "style": style}).encode(),
        headers={"Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    # Short timeout — fail fast into ElevenLabs/edge rather than stalling speech.
    timeout = float(os.environ.get("TTS_GATEWAY_TIMEOUT_S", os.environ.get("TTS_TIMEOUT_S", "4")))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            audio = response.read()
            mime = response.headers.get("Content-Type") or "audio/mpeg"
    except urllib.error.HTTPError as exc:
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
        or "EXAVITQu4vr4xnSDxMaL"
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
    text = (stderr or b"").decode("utf-8", errors="replace").strip()
    if not text:
        return "no output"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if not line.startswith(("File \"", "Traceback", "  ", "^")):
            return line[:160]
    return lines[-1][:160]


def _edge_tts(text: str, language: str) -> tuple[bytes, str]:
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
