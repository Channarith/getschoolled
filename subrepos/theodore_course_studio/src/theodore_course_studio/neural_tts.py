"""Neural voices for Course Studio narration (gateway → local edge-tts → device).

Mirrors theodore_music_lab.tts so every language Theodore teaches — including
Khmer — has a Microsoft Edge neural voice even when the speech gateway is down
and the listener's OS ships no voice for that language.

Clips are cached on disk by (voice, rate, text), but caching is best-effort: an
unwritable cache directory renders uncached rather than failing. With no
edge-tts and an empty cache the API answers 501 and the page falls back to
speechSynthesis.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
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

# Hong Kong Cantonese is a spoken variant, not one of the 27 content languages,
# so it is not a VOICES key. xAI speech-to-speech has no Cantonese code.
_CANTONESE_VOICES = ("zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural")

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


def _voice_lang(language: str) -> str:
    """Map a teach-language tag onto a neural voice key.

    ``zh-HK`` must not collapse to Mandarin ``zh``. ``km-KH`` stays Khmer.
    British, Australian, and Singapore English keep their region.
    """
    raw = (language or "en").strip().lower().replace("_", "-")
    try:
        from aoep_shared.languages import english_variety
    except Exception:  # noqa: BLE001
        english_variety = None  # type: ignore
    if english_variety is not None:
        variety = english_variety(raw)
        if variety in {"en-GB", "en-AU", "en-SG"}:
            return variety
    if (
        raw in {"yue", "zh-hk", "zh-mo", "zh-yue", "cantonese"}
        or raw.startswith("yue-")
        or raw.startswith("zh-hk")
        or raw.startswith("zh-mo")
        or raw.startswith("zh-yue")
    ):
        return "yue"
    if raw == "km" or raw.startswith("km-"):
        return "km"
    if raw in {"zh-cn", "zh-hans", "zh-sg", "cmn", "mandarin"} or raw.startswith("zh-cn"):
        return "zh"
    return raw.split("-")[0] or "en"


def _voice_pair(language: str) -> tuple[str, str]:
    lang = _voice_lang(language)
    if lang == "yue":
        return _CANTONESE_VOICES
    if lang == "en-GB":
        return ("en-GB-SoniaNeural", "en-GB-RyanNeural")
    if lang == "en-AU":
        return ("en-AU-NatashaNeural", "en-AU-WilliamNeural")
    if lang == "en-SG":
        return ("en-SG-LunaNeural", "en-SG-WayneNeural")
    return VOICES.get(lang) or VOICES["en"]


def _voice_speaks(language: str, voice: str) -> bool:
    if not voice:
        return False
    try:
        from aoep_shared.voice_catalog import voice_matches_language
    except Exception:  # noqa: BLE001
        return True
    return voice_matches_language(voice, language)


def voice_for(language: str, *, gender: str = "female", voice: str = "") -> str:
    if voice and _voice_speaks(language, voice):
        return voice
    pair = _voice_pair(language)
    return pair[1] if gender == "male" else pair[0]


def voice_candidates(
    language: str, *, gender: str = "female", voice: str = ""
) -> list[str]:
    if voice and _voice_speaks(language, voice):
        return [voice]
    lang = _voice_lang(language)
    pair = _voice_pair(language)
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


def _prosody(rate: float, tone: str = "") -> tuple[str, str, str]:
    """(rate %, pitch, volume) for a request: the visitor's tone when it is a known non-neutral one, else the plain rate."""
    from aoep_shared.tone_presets import tone_prosody

    chosen = tone_prosody(tone)
    return chosen if chosen else (rate_percent(rate), "+0Hz", "+0%")


def clip_path(text: str, *, voice: str, rate: str, pitch: str = "+0Hz", volume: str = "+0%") -> Path:
    parts = [voice, rate, text]
    if (pitch, volume) != ("+0Hz", "+0%"):   # a toned clip never shares a cache entry with the plain voice; plain keys are unchanged
        parts += [pitch, volume]
    digest = hashlib.sha256(
        "\u0000".join(parts).encode("utf-8")
    ).hexdigest()[:32]
    return cache_dir() / f"{digest}.mp3"


def _render(text: str, path: Path, *, voice: str, rate: str, pitch: str = "+0Hz", volume: str = "+0%") -> None:
    from aoep_shared.edge_speech import render_edge_mp3

    async def run() -> None:
        audio = await asyncio.wait_for(
            render_edge_mp3(text, voice=voice, rate=rate, pitch=pitch, volume=volume),
            timeout=_TIMEOUT_SEC,
        )
        path.write_bytes(audio)

    asyncio.run(run())


def cacheable_path(path: Path) -> Path | None:
    """`path` if the clip can be cached there, else None to render uncached.

    A read-only or sandboxed HOME must never break narration; the clip simply
    stops being reused by later requests.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path if os.access(path.parent, os.W_OK) else None


def _render_bytes(text: str, *, voice: str, rate: str, target: Path | None, pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
    """MP3 bytes for one clip, cached at `target` when one is writable."""
    extra = {} if (pitch, volume) == ("+0Hz", "+0%") else {"pitch": pitch, "volume": volume}   # plain voice: _render is called as before
    if target is None:
        with tempfile.TemporaryDirectory() as scratch:
            clip = Path(scratch) / "clip.mp3"
            _render(text, clip, voice=voice, rate=rate, **extra)
            if not clip.is_file() or clip.stat().st_size <= 0:
                raise TTSUnavailable("empty audio file")
            return clip.read_bytes()
    partial = target.with_suffix(".part")
    try:
        _render(text, partial, voice=voice, rate=rate, **extra)
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise TTSUnavailable("empty audio file")
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return target.read_bytes()


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


def split_for_speech(text: str, limit: int = 1400) -> list[str]:
    """Sentence-sized pieces of one narration, all spoken by the same voice."""
    line = re.sub(r"\s+", " ", (text or "").strip())
    if not line:
        return []
    if len(line) <= limit:
        return [line]
    parts: list[str] = []
    buf = ""
    for sentence in re.split(r"(?<=[.!?。！？؟។])\s*", line):
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            split_at = sentence.rfind(" ", 0, limit + 1)
            if split_at < limit // 2:
                split_at = limit
            parts.append(sentence[:split_at].rstrip())
            sentence = sentence[split_at:].strip()
        if not sentence:
            continue
        if buf and len(buf) + 1 + len(sentence) > limit:
            parts.append(buf)
            buf = sentence
        else:
            separator = "" if buf.endswith(("。", "！", "？", "។")) else " "
            buf = f"{buf}{separator}{sentence}".strip()
    if buf:
        parts.append(buf)
    return parts


def stitch_mp3_chunks(chunks: list[bytes]) -> bytes:
    """Decode and re-encode chunks as one continuous, browser-safe MP3."""
    if not chunks:
        raise TTSUnavailable("no audio chunks to stitch")
    if len(chunks) == 1:
        return chunks[0]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TTSUnavailable("ffmpeg is required to stitch long narration")
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        inputs: list[str] = []
        for index, data in enumerate(chunks):
            path = root / f"chunk-{index:04d}.mp3"
            path.write_bytes(data)
            inputs.extend(["-i", str(path)])
        output = root / "narration.mp3"
        filters = "".join(f"[{index}:a]" for index in range(len(chunks)))
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            f"{filters}concat=n={len(chunks)}:v=0:a=1[out]",
            "-map",
            "[out]",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "3",
            "-write_xing",
            "1",
            str(output),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
            detail = (proc.stderr or proc.stdout or "unknown ffmpeg error").strip()
            raise TTSUnavailable(f"could not stitch narration: {detail}")
        return output.read_bytes()


_EDGE_VOICE_ID = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)+Neural$")


def valid_voice_id(voice: str | None) -> str:
    """The voice id if it looks like an edge neural voice name (en-US-AriaNeural), else ''."""
    name = (voice or "").strip()
    return name if len(name) <= 64 and _EDGE_VOICE_ID.match(name) else ""


def synthesize_course(
    text: str,
    language: str,
    *,
    rate: float = 1.0,
    gender: str = "female",
    voice: str = "",
    tone: str = "",
) -> bytes:
    """One MP3 for a whole page, always in the locked course voice.

    Long pages are split and joined. A later page never switches to another
    speaker just because the line is longer or a request needs a retry.
    `voice` is the visitor's own pick (an edge voice id from the voice menu); '' keeps the course voice.
    `tone` is the visitor's tone pick (aoep_shared.tone_presets id); '' / neutral / unknown keep the plain voice.
    """
    voice = voice_for(language, gender=gender, voice=valid_voice_id(voice))
    chunks = split_for_speech(text)
    if not chunks:
        raise TTSUnavailable("nothing to speak")
    percent, pitch, volume = _prosody(rate, tone)
    combined_path = clip_path(text, voice=f"course:{voice}", rate=percent, pitch=pitch, volume=volume)
    try:
        if combined_path.is_file() and combined_path.stat().st_size > 0:
            return combined_path.read_bytes()
    except OSError:
        pass
    rendered = [
        synthesize(chunk, language, rate=rate, gender=gender, voice=voice, **({"tone": tone} if tone else {}))
        for chunk in chunks
    ]
    audio = stitch_mp3_chunks(rendered)
    target = cacheable_path(combined_path)
    if target is not None:
        partial = target.with_suffix(".part")
        try:
            partial.write_bytes(audio)
            partial.replace(target)
        except OSError:
            partial.unlink(missing_ok=True)
    return audio


def synthesize(
    text: str,
    language: str,
    *,
    rate: float = 1.0,
    gender: str = "female",
    voice: str = "",
    tone: str = "",
) -> bytes:
    """MP3 bytes for one narration. Raises TTSUnavailable when nothing can render it."""
    line = (text or "").strip()[:MAX_CHARS]
    if not line:
        raise TTSUnavailable("nothing to speak")
    candidates = voice_candidates(language, gender=gender, voice=voice)
    percent, pitch, volume = _prosody(rate, tone)
    for chosen in candidates:
        path = clip_path(line, voice=chosen, rate=percent, pitch=pitch, volume=volume)
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path.read_bytes()
        except OSError:
            continue
    if not engine_available():
        raise TTSUnavailable("no neural voice engine available")

    errors: list[str] = []
    for chosen in candidates:
        target = cacheable_path(clip_path(line, voice=chosen, rate=percent, pitch=pitch, volume=volume))
        for attempt in range(_RENDER_ATTEMPTS):
            try:
                return _render_bytes(line, voice=chosen, rate=percent, target=target, pitch=pitch, volume=volume)
            except Exception as exc:  # noqa: BLE001 — network / voice flakiness
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
    try:
        if not directory.is_dir():
            return 0
        return sum(1 for path in directory.glob("*.mp3") if path.stat().st_size > 0)
    except OSError:
        return 0


def status() -> dict[str, object]:
    clips = cached_clips()
    engine = engine_available()
    return {
        "available": bool(engine or clips),
        "engine": ENGINE if engine else ("cache-only" if clips else "none"),
        "languages": len(VOICES),
        "cached_clips": clips,
        "cache_dir": str(cache_dir()),
        "gapless_stitch": bool(shutil.which("ffmpeg")),
        "voices": {code: pair[0] for code, pair in VOICES.items()},
    }
