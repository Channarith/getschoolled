"""Natural-sounding TTS for the AI presenter (neural voices, chunked prosody)."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

_IS_WINDOWS = os.name == "nt" or sys.platform.startswith("win")

# Microsoft Edge neural voices (edge-tts). Warm, non-robotic; needs network once per clip.
DEFAULT_NEURAL_VOICE = "en-US-AriaNeural"
_NEURAL_VOICES = {
    "en": "en-US-AriaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _edge_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def neural_voice_for(language: str = "en", voice: str = "") -> str:
    if voice and "Neural" in voice:
        return voice
    if voice and not voice.startswith("en-"):
        return voice
    lang = (language or "en").split("-")[0].lower()
    return _NEURAL_VOICES.get(lang, DEFAULT_NEURAL_VOICE)


def chunk_for_speech(text: str, *, max_chars: int = 320) -> List[str]:
    """Split long narration into sentence chunks for natural pacing."""
    text = (text or "").strip()
    if not text:
        return []
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return [text[:max_chars]]
    chunks: List[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= max_chars:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks


def synthesize_neural(
    text: str,
    out_path: Path,
    *,
    language: str = "en",
    voice: str = "",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bool:
    """Write MP3 using edge-tts neural voice. Returns True on success.

    ``rate`` (e.g. "-6%") and ``pitch`` (e.g. "+22Hz") let an instructor
    personality shape delivery — firmer/slower for "strict", higher/faster for
    "child" or "cartoon".
    """
    if not _edge_tts_available():
        return False
    narration = (text or "").strip()
    if not narration:
        return False
    import edge_tts

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    v = neural_voice_for(language, voice)

    async def _run() -> None:
        comm = edge_tts.Communicate(
            narration, voice=v, rate=rate or "+0%", pitch=pitch or "+0Hz",
        )
        await comm.save(str(out_path))

    try:
        asyncio.run(_run())
        return out_path.is_file() and out_path.stat().st_size > 256
    except Exception:
        return False


def _play_subprocess(cmd: list, *, timeout: int) -> bool:
    proc = None
    try:
        proc = subprocess.Popen(cmd)
        proc.wait(timeout=timeout)
        return proc.returncode == 0
    except KeyboardInterrupt:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise
    except (subprocess.TimeoutExpired, OSError):
        if proc is not None and proc.poll() is None:
            proc.terminate()
        return False


def _play_windows(path: Path) -> bool:
    """Blocking playback on Windows via the built-in .NET MediaPlayer (mp3/wav).

    No external player (afplay/ffplay) exists on a stock Windows box, so without
    this the presenter has nothing to play the edge-tts .mp3 — audio is silent
    AND the run races by, because each speak() returns instantly instead of
    blocking for the clip's duration. PowerShell + System.Windows.Media.MediaPlayer
    ships with Windows and plays mp3 natively; we block for the clip length.
    """
    # Escape single quotes for the PowerShell single-quoted string literal.
    safe = str(path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName presentationCore;"
        "$p = New-Object System.Windows.Media.MediaPlayer;"
        f"$p.Open([uri]'{safe}');"
        "$deadline = (Get-Date).AddSeconds(10);"
        "while (-not $p.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $deadline)"
        " { Start-Sleep -Milliseconds 50 };"
        "$p.Play();"
        "if ($p.NaturalDuration.HasTimeSpan)"
        " { Start-Sleep -Milliseconds ([int]$p.NaturalDuration.TimeSpan.TotalMilliseconds + 300) };"
        "$p.Stop(); $p.Close();"
    )
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return False
    return _play_subprocess(
        [exe, "-NoProfile", "-NonInteractive", "-Command", script], timeout=900,
    )


def _play_winsound_wav(path: Path) -> bool:
    """Last-resort Windows WAV playback via the stdlib winsound module."""
    if path.suffix.lower() != ".wav":
        return False
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True
    except (ImportError, RuntimeError):
        return False


def play_audio_file(path: Path) -> bool:
    """Blocking playback until the clip finishes (cross-platform)."""
    path = Path(path)
    if not path.is_file():
        return False
    if shutil.which("afplay"):
        return _play_subprocess(["afplay", str(path)], timeout=900)
    if shutil.which("ffplay"):
        return _play_subprocess(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
            timeout=900,
        )
    if _IS_WINDOWS:
        return _play_windows(path) or _play_winsound_wav(path)
    # Linux without ffplay: try common CLI players (mp3 + wav).
    for player, args in (
        ("mpg123", ["-q"]), ("cvlc", ["--play-and-exit", "--intf", "dummy"]),
        ("aplay", []), ("paplay", []),
    ):
        if shutil.which(player):
            return _play_subprocess([player, *args, str(path)], timeout=900)
    return False


def speak_natural_blocking(
    text: str,
    *,
    language: str = "en",
    voice: str = "",
    tts_engine: str = "auto",
    cache_dir: Optional[Path] = None,
    pace_multiplier: float = 1.0,
    tts_rate: str = "+0%",
    voice_sample: Optional[str | Path] = None,
    repo_root: Optional[str | Path] = None,
    elevenlabs_voice_id: str = "",
) -> bool:
    """Speak with the best available engine (clone → neural → enhanced say → espeak)."""
    from ..harvest.media import speak_live, synthesize_narration, tts_available
    from .clone_tts import CLONE_ENGINES, synthesize_cloned, synthesize_for_profile
    from .voice_profiles import get_voice_profile, parse_voice_token

    narration = (text or "").strip()
    if not narration:
        return False

    engine = (tts_engine or "auto").lower()
    root = Path(repo_root) if repo_root else None
    sample_path: Optional[Path] = Path(voice_sample) if voice_sample else None
    clone_engine = engine
    el_voice_id = elevenlabs_voice_id

    hint, profile_id = parse_voice_token(voice)
    if profile_id:
        profile = get_voice_profile(profile_id, repo_root=root)
        if profile:
            try:
                sample_path = profile.resolved_sample(repo_root=root)
            except FileNotFoundError:
                profile = None
            if profile:
                clone_engine = engine if engine in CLONE_ENGINES else profile.tts_engine
                el_voice_id = profile.elevenlabs_voice_id or el_voice_id
                if engine == "auto":
                    engine = "clone"

    use_clone = engine in CLONE_ENGINES or (engine == "auto" and sample_path is not None)
    if use_clone and sample_path and sample_path.is_file():
        root_dir = cache_dir or Path(tempfile.gettempdir()) / "aoep_presenter_tts"
        root_dir.mkdir(parents=True, exist_ok=True)
        digest = abs(hash((narration[:500], str(sample_path), clone_engine))) % 10_000_000
        mp3 = root_dir / f"clone_{digest}.mp3"
        profile = get_voice_profile(profile_id, repo_root=root) if profile_id else None
        if profile and not mp3.is_file():
            ok, _used = synthesize_for_profile(
                narration, mp3, profile, repo_root=root, cache_dir=root_dir,
            )
        elif not mp3.is_file():
            ok, _used = synthesize_cloned(
                narration,
                mp3,
                sample_path=sample_path,
                language=language,
                engine=clone_engine,
                voice_id=el_voice_id,
            )
        else:
            ok = True
        if ok and mp3.is_file():
            return play_audio_file(mp3)

    # CosyVoice 2 (self-hosted) for the default/no-persona voice: when
    # COSYVOICE_URL is set and we're on "auto"/"cosyvoice", render with it before
    # falling back to edge-tts / macOS say. (With a persona sample the clone path
    # above already tries CosyVoice first via the engine priority.)
    from .clone_tts import _cosyvoice_url, synthesize_cosyvoice

    if _cosyvoice_url() and engine in ("auto", "cosyvoice"):
        root_dir = cache_dir or Path(tempfile.gettempdir()) / "aoep_presenter_tts"
        root_dir.mkdir(parents=True, exist_ok=True)
        digest = abs(hash((narration[:500], "cosyvoice", language))) % 10_000_000
        cv = root_dir / f"cosy_{digest}.mp3"
        ref = sample_path if (sample_path and sample_path.is_file()) else None
        if cv.is_file() or synthesize_cosyvoice(narration, cv, language=language, sample_path=ref):
            if cv.is_file():
                return play_audio_file(cv)

    use_neural = engine in ("auto", "edge", "neural") and _edge_tts_available()
    if use_neural:
        root = cache_dir or Path(tempfile.gettempdir()) / "aoep_presenter_tts"
        root.mkdir(parents=True, exist_ok=True)
        digest = abs(hash((narration[:500], voice, tts_rate))) % 10_000_000
        mp3 = root / f"narr_{digest}.mp3"
        if not mp3.is_file() and not synthesize_neural(
            narration, mp3, language=language, voice=voice, rate=tts_rate,
        ):
            use_neural = False
        elif mp3.is_file():
            return play_audio_file(mp3)

    if engine in ("auto", "say") and tts_available() and shutil.which("say"):
        enhanced = _pick_macos_voice(voice)
        return speak_live(
            narration,
            language=language,
            voice=enhanced,
            pace_multiplier=pace_multiplier,
        )

    if tts_available():
        wav = (cache_dir or Path(tempfile.gettempdir())) / "aoep_fallback.aiff"
        if synthesize_narration(narration, wav, language=language):
            return play_audio_file(wav)
    return False


def _pick_macos_voice(preferred: str = "") -> str:
    """Prefer Premium/Enhanced macOS voices over legacy Samantha."""
    if preferred and preferred not in ("Samantha", "default", ""):
        return preferred
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10)
        names = [line.split()[0] for line in out.stdout.splitlines() if line.strip()]
        for hint in ("Premium", "Enhanced", "Daniel", "Karen", "Moira", "Samantha"):
            for n in names:
                if hint.lower() in n.lower():
                    return n
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass
    return preferred or "Samantha"


def tts_engine_status() -> dict:
    from .clone_tts import engine_status as clone_status

    audio_player = bool(
        shutil.which("afplay")
        or shutil.which("ffplay")
        or (_IS_WINDOWS and (shutil.which("powershell") or shutil.which("pwsh")))
        or shutil.which("mpg123")
        or shutil.which("aplay")
    )
    return {
        "edge_tts": _edge_tts_available(),
        "say": shutil.which("say") is not None,
        "afplay": shutil.which("afplay") is not None,
        "ffplay": shutil.which("ffplay") is not None,
        "windows_media_player": _IS_WINDOWS
        and bool(shutil.which("powershell") or shutil.which("pwsh")),
        "audio_player_available": audio_player,
        "default_neural_voice": DEFAULT_NEURAL_VOICE,
        **clone_status(),
    }
