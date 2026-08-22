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


def _render(text: str, *, voice: str, rate: str) -> bytes:
    """MP3 bytes straight from the engine, without touching the disk.

    Rendering used to go through ``Communicate.save(path)``, which made a clip
    impossible to produce whenever the cache directory was not writable — a
    read-only home, a container, or a sandboxed shell. The endpoint then
    answered 501 for every uncached line and the player fell back to a device
    voice the OS may not have for that language, so a whole song went silent.
    The cache is an optimisation; playback must not depend on it.
    """
    import edge_tts

    async def run() -> bytes:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        audio = bytearray()

        async def pump() -> None:
            async for chunk in comm.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])

        await asyncio.wait_for(pump(), timeout=_TIMEOUT_SEC)
        return bytes(audio)

    return asyncio.run(run())


def _store(path: Path, audio: bytes) -> None:
    """Cache a rendered clip, best effort. Writing is never required to speak."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Writing straight to the final name would publish a truncated clip if
        # the process died halfway through.
        partial = path.with_suffix(".part")
        partial.write_bytes(audio)
        partial.replace(path)
    except OSError:
        pass


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
        for attempt in range(_RENDER_ATTEMPTS):
            try:
                audio = _render(line, voice=chosen, rate=percent)
                if not audio:
                    raise TTSUnavailable("empty audio")
                _store(clip_path(line, voice=chosen, rate=percent), audio)
                return audio
            except Exception as exc:  # network, auth, voice retired…
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


def tts_status() -> dict[str, object]:
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
        "voices": {code: pair[0] for code, pair in VOICES.items()},
    }


# The platform-wide name every other lab exposes (theodore_webcam_lab.tts,
# theodore_audio_translation_lab.tts, aoep_shared.lab_tts); `status` is kept so
# older in-lab callers and tests keep working.
status = tts_status

# Delivery presets for the platform-standard /api/tts, mapped onto the two knobs
# this lab actually has: which half of the language's (female, male) voice pair
# to use, and a small speech-rate nudge. Unknown styles fall back to "warm".
STYLES: dict[str, tuple[str, float]] = {
    "warm": ("female", 1.0),
    "standard": ("female", 1.0),
    "bright": ("female", 1.05),
    "cheerful": ("female", 1.1),
    "calm": ("female", 0.95),
    "soft": ("female", 0.9),
    "deep": ("male", 0.95),
    "narrator": ("male", 1.0),
    "serious": ("male", 0.9),
}


def speak(
    text: str, *, language: str = "en", style: str = "warm"
) -> tuple[bytes, str, str]:
    """`(audio, mime, engine)` for /api/tts — the shape every lab's endpoint uses.

    Raises ValueError for empty text (the endpoint answers 422) and
    TTSUnavailable when no engine and no cached clip can render it (501, the
    client's cue to use the device voice).
    """
    line = (text or "").strip()
    if not line:
        raise ValueError("tts text is empty")
    gender, rate = STYLES.get((style or "").strip().lower(), STYLES["warm"])
    audio = synthesize(line, language, rate=rate, gender=gender)
    return audio, "audio/mpeg", ENGINE if engine_available() else "cache"
