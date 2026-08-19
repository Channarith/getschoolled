"""Neural voices for all 27 translation languages, rendered server side.

The player used to sing with `window.speechSynthesis`, so a language only worked
if the listener's OS shipped a voice for it. macOS has no Khmer voice at all and
Chinese/Spanish depend on which system voices were installed, so "Sing in Khmer"
simply refused. Here the server renders the line with a Microsoft Edge neural
voice (edge-tts) instead, which covers every language the lab translates into,
and the browser just plays the MP3.

Clips are cached on disk by (voice, rate, text), so a line is rendered once and
replays offline afterwards; scripts/prefetch_voices.py warms a whole song. With
no edge-tts and an empty cache the API answers 501 and the player falls back to
the device voice, exactly as before.

Microsoft's free Edge TTS endpoint is flaky under burst load: a long
prefetch can suddenly return ``No audio was received`` (or an empty error) for
a voice that worked moments earlier. Retries + alternate voices keep Polish /
Turkish / Arabic and the rest filling the cache instead of abandoning a
language on the first drop.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path

# Verified against the Microsoft neural voice catalogue: (female, male) per
# language. Every language in translations.MEANING_LANGUAGES is covered — that
# is the whole point of rendering server side.
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

# Extra voices tried after the primary pair when Microsoft returns empty audio
# mid-batch. Prefer same-locale alternates; Arabic also has Egyptian as a
# last resort because SA voices are often the first ones throttled.
VOICE_FALLBACKS: dict[str, tuple[str, ...]] = {
    "pl": ("pl-PL-ZofiaNeural",),
    "tr": (),
    "ar": ("ar-EG-SalmaNeural", "ar-EG-ShakirNeural"),
}

ENGINE = "edge-tts-neural"
MAX_CHARS = 600
_TIMEOUT_SEC = 20.0
_RENDER_ATTEMPTS = 3
_RETRY_BACKOFF_SEC = (0.6, 1.4, 2.8)
# A sung line's rate is computed from the audio duration the browser reports, so
# two visits can ask for 1.12 and 1.13. Quantising to 5% keeps the cache useful
# and is inaudible.
_RATE_STEP = 5


class TTSUnavailable(RuntimeError):
    """No engine and no cached clip — the caller should use a device voice."""


def cache_dir() -> Path:
    override = os.environ.get("MUSIC_LAB_TTS_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "theodore-music-lab" / "tts"


def enabled() -> bool:
    return os.environ.get("MUSIC_LAB_TTS", "").strip().lower() not in {"off", "0", "no"}


def engine_available() -> bool:
    if not enabled():
        return False
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


def voice_for(language: str, *, gender: str = "female", voice: str = "") -> str:
    """Neural voice id for a language code, e.g. km -> km-KH-SreymomNeural."""
    if voice:
        return voice
    lang = (language or "en").split("-")[0].lower()
    pair = VOICES.get(lang) or VOICES["en"]
    return pair[1] if gender == "male" else pair[0]


def voice_candidates(
    language: str, *, gender: str = "female", voice: str = ""
) -> list[str]:
    """Primary voice first, then same-language alternates for flaky renders."""
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
    """Speech-rate multiplier as the +/-N% string edge-tts expects."""
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
    """True for Microsoft empty-audio / network drops that often clear on retry."""
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
    """MP3 bytes for one line. Raises TTSUnavailable when nothing can render it."""
    line = (text or "").strip()[:MAX_CHARS]
    if not line:
        raise TTSUnavailable("nothing to speak")
    candidates = voice_candidates(language, gender=gender, voice=voice)
    percent = rate_percent(rate)
    # Prefer an already-cached clip from any candidate before hitting the network.
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
                # Rendering straight to the final name would publish a truncated
                # clip if the network dropped halfway through.
                if not partial.is_file() or partial.stat().st_size <= 0:
                    raise TTSUnavailable("empty audio file")
                partial.replace(path)
                return path.read_bytes()
            except Exception as exc:  # network, auth, voice retired…
                partial.unlink(missing_ok=True)
                detail = str(exc).strip() or type(exc).__name__
                errors.append(f"{chosen} attempt {attempt + 1}: {detail}")
                if attempt + 1 < _RENDER_ATTEMPTS and _transient_render_error(exc):
                    time.sleep(_RETRY_BACKOFF_SEC[min(attempt, len(_RETRY_BACKOFF_SEC) - 1)])
                    continue
                # Non-transient (or last attempt for this voice): try next voice.
                break
    raise TTSUnavailable("; ".join(errors) or "render failed")


def cached_clips() -> int:
    directory = cache_dir()
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob("*.mp3") if path.stat().st_size > 0)


def status() -> dict[str, object]:
    """What the player probes once at boot to decide server vs device voice."""
    clips = cached_clips()
    engine = engine_available()
    chain: list[str] = []
    if engine:
        chain.append(ENGINE)
    if clips and ENGINE not in chain:
        chain.append("cache")
    return {
        "available": bool(engine or clips),
        "engine": ENGINE if engine else ("cache-only" if clips else "none"),
        "engines": chain,
        "languages": len(VOICES),
        "cached_clips": clips,
        "cache_dir": str(cache_dir()),
        "voices": {code: pair[0] for code, pair in VOICES.items()},
    }
