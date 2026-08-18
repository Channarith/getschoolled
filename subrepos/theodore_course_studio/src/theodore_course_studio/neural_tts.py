"""Neural voices for Course Studio narration (gateway → local edge-tts → device).

Mirrors theodore_music_lab.tts so every language Theodore teaches — including
Khmer — has a Microsoft Edge neural voice even when the speech gateway is down
and the listener's OS ships no voice for that language.

Clips are cached on disk by (voice, rate, text). With no edge-tts and an empty
cache the API answers 501 and the page falls back to speechSynthesis.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path

# Same 27-language (female, male) catalogue as the music lab / shared natural_tts.
VOICES: dict[str, tuple[str, str]] = {
    "en": ("en-US-AriaNeural", "en-US-GuyNeural"),
    "es": ("es-ES-ElviraNeural", "es-ES-AlvaroNeural"),
    "fr": ("fr-FR-DeniseNeural", "fr-FR-HenriNeural"),
    "de": ("de-DE-KatjaNeural", "de-DE-ConradNeural"),
    "it": ("it-IT-ElsaNeural", "it-IT-DiegoNeural"),
    "pt": ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"),
    "nl": ("nl-NL-FennaNeural", "nl-NL-MaartenNeural"),
    "pl": ("pl-PL-AgnieszkaNeural", "pl-PL-MarekNeural"),
    "ru": ("ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"),
    "uk": ("uk-UA-PolinaNeural", "uk-UA-OstapNeural"),
    "tr": ("tr-TR-EmelNeural", "tr-TR-AhmetNeural"),
    "ar": ("ar-SA-ZariyahNeural", "ar-SA-HamedNeural"),
    "he": ("he-IL-HilaNeural", "he-IL-AvriNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "bn": ("bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"),
    "ur": ("ur-PK-UzmaNeural", "ur-PK-AsadNeural"),
    "fa": ("fa-IR-DilaraNeural", "fa-IR-FaridNeural"),
    "zh": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"),
    "ja": ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
    "ko": ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural"),
    "vi": ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"),
    "th": ("th-TH-PremwadeeNeural", "th-TH-NiwatNeural"),
    "id": ("id-ID-GadisNeural", "id-ID-ArdiNeural"),
    "sw": ("sw-KE-ZuriNeural", "sw-KE-RafikiNeural"),
    "el": ("el-GR-AthinaNeural", "el-GR-NestorasNeural"),
    "cs": ("cs-CZ-VlastaNeural", "cs-CZ-AntoninNeural"),
    "km": ("km-KH-SreymomNeural", "km-KH-PisethNeural"),
}

VOICE_FALLBACKS: dict[str, tuple[str, ...]] = {
    "pl": ("pl-PL-ZofiaNeural",),
    "ar": ("ar-EG-SalmaNeural", "ar-EG-ShakirNeural"),
}

ENGINE = "edge-tts-neural"
MAX_CHARS = 1800
_TIMEOUT_SEC = 25.0
_RENDER_ATTEMPTS = 3
_RETRY_BACKOFF_SEC = (0.6, 1.4, 2.8)
_RATE_STEP = 5


class TTSUnavailable(RuntimeError):
    """No engine and no cached clip — the caller should use a device voice."""


def cache_dir() -> Path:
    override = os.environ.get("COURSE_STUDIO_TTS_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "theodore-course-studio" / "tts"


def enabled() -> bool:
    return os.environ.get("COURSE_STUDIO_TTS", "").strip().lower() not in {
        "off",
        "0",
        "no",
    }


def engine_available() -> bool:
    if not enabled():
        return False
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


def voice_for(language: str, *, gender: str = "female", voice: str = "") -> str:
    if voice:
        return voice
    lang = (language or "en").split("-")[0].lower()
    pair = VOICES.get(lang) or VOICES["en"]
    return pair[1] if gender == "male" else pair[0]


def voice_candidates(
    language: str, *, gender: str = "female", voice: str = ""
) -> list[str]:
    if voice:
        return [voice]
    lang = (language or "en").split("-")[0].lower()
    pair = VOICES.get(lang) or VOICES["en"]
    primary = pair[1] if gender == "male" else pair[0]
    secondary = pair[0] if gender == "male" else pair[1]
    extras = list(VOICE_FALLBACKS.get(lang, ()))
    ordered: list[str] = []
    for name in (primary, secondary, *extras):
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def rate_percent(rate: float) -> str:
    try:
        multiplier = float(rate)
    except (TypeError, ValueError):
        multiplier = 1.0
    percent = (max(0.5, min(2.0, multiplier)) - 1.0) * 100.0
    stepped = int(round(percent / _RATE_STEP) * _RATE_STEP)
    return f"{stepped:+d}%"


def clip_path(text: str, *, voice: str, rate: str) -> Path:
    digest = hashlib.sha256(
        "\u0000".join([voice, rate, text]).encode("utf-8")
    ).hexdigest()[:32]
    return cache_dir() / f"{digest}.mp3"


def _render(text: str, path: Path, *, voice: str, rate: str) -> None:
    import edge_tts

    async def run() -> None:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        await asyncio.wait_for(comm.save(str(path)), timeout=_TIMEOUT_SEC)

    asyncio.run(run())


def _transient_render_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    message = str(exc).strip().lower()
    if name in {"NoAudioReceived", "TimeoutError", "ClientConnectorError"}:
        return True
    needles = (
        "no audio was received",
        "websocket",
        "timed out",
        "temporarily",
        "connection reset",
        "server disconnected",
    )
    return any(needle in message for needle in needles) or message == ""


def synthesize(
    text: str,
    language: str,
    *,
    rate: float = 1.0,
    gender: str = "female",
    voice: str = "",
) -> bytes:
    """MP3 bytes for one narration. Raises TTSUnavailable when nothing can render it."""
    line = (text or "").strip()[:MAX_CHARS]
    if not line:
        raise TTSUnavailable("nothing to speak")
    candidates = voice_candidates(language, gender=gender, voice=voice)
    percent = rate_percent(rate)
    for chosen in candidates:
        path = clip_path(line, voice=chosen, rate=percent)
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
    if not engine_available():
        raise TTSUnavailable("no neural voice engine available")

    errors: list[str] = []
    for chosen in candidates:
        path = clip_path(line, voice=chosen, rate=percent)
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(_RENDER_ATTEMPTS):
            partial = path.with_suffix(".part")
            try:
                _render(line, partial, voice=chosen, rate=percent)
                if not partial.is_file() or partial.stat().st_size <= 0:
                    raise TTSUnavailable("empty audio file")
                partial.replace(path)
                return path.read_bytes()
            except Exception as exc:  # noqa: BLE001 — network / voice flakiness
                partial.unlink(missing_ok=True)
                detail = str(exc).strip() or type(exc).__name__
                errors.append(f"{chosen} attempt {attempt + 1}: {detail}")
                if attempt + 1 < _RENDER_ATTEMPTS and _transient_render_error(exc):
                    time.sleep(
                        _RETRY_BACKOFF_SEC[min(attempt, len(_RETRY_BACKOFF_SEC) - 1)]
                    )
                    continue
                break
    raise TTSUnavailable("; ".join(errors) or "render failed")


def cached_clips() -> int:
    directory = cache_dir()
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob("*.mp3") if path.stat().st_size > 0)


def status() -> dict[str, object]:
    clips = cached_clips()
    engine = engine_available()
    return {
        "available": bool(engine or clips),
        "engine": ENGINE if engine else ("cache-only" if clips else "none"),
        "languages": len(VOICES),
        "cached_clips": clips,
        "cache_dir": str(cache_dir()),
        "voices": {code: pair[0] for code, pair in VOICES.items()},
    }
