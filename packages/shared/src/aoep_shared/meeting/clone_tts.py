"""Voice-cloning TTS backends: Chatterbox, XTTS, ElevenLabs (HTTP APIs)."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Sequence

from .voice_profiles import VoiceProfile

CLONE_ENGINES = ("clone", "chatterbox", "xtts", "elevenlabs")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def engine_status() -> dict:
    return {
        "chatterbox_url": _chatterbox_url(),
        "xtts_url": _xtts_url(),
        "elevenlabs_configured": bool(_env("ELEVENLABS_API_KEY")),
        "elevenlabs_voice_id": _env("ELEVENLABS_VOICE_ID"),
        "clone_priority": clone_engine_priority(),
    }


def clone_engine_priority() -> List[str]:
    raw = _env("CLONE_TTS_PRIORITY", "chatterbox,xtts,elevenlabs,edge")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _chatterbox_url() -> str:
    return _env("CHATTERBOX_TTS_URL", "http://127.0.0.1:8004")


def _xtts_url() -> str:
    return _env("XTTS_TTS_URL") or _env("SPEECH_BASE_URL", "http://127.0.0.1:8100")


def _http_post_json(url: str, payload: dict, *, headers: Optional[dict] = None, timeout: int = 120) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_post_multipart(
    url: str,
    fields: dict,
    files: dict,
    *,
    headers: Optional[dict] = None,
    timeout: int = 120,
) -> bytes:
    boundary = "----aoep-voice-clone"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        parts.append(str(value).encode("utf-8"))
        parts.append(b"\r\n")
    for key, path in files.items():
        p = Path(path)
        mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{key}"; filename="{p.name}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
        parts.append(p.read_bytes())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            **(headers or {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _write_audio_blob(data: bytes, out_path: Path) -> bool:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(data) < 128:
        return False
    if data[:4] == b"RIFF" or data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        out_path.write_bytes(data)
        return True
    if data[:4] == b"fLaC":
        out_path.write_bytes(data)
        return True
    mp3 = out_path if out_path.suffix.lower() == ".mp3" else out_path.with_suffix(".mp3")
    mp3.write_bytes(data)
    return mp3.is_file() and mp3.stat().st_size > 128


def _ffmpeg_to_wav(src: Path, dest: Path) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", "22050", "-ac", "1", str(dest)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return dest.is_file()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def ensure_wav_sample(sample_path: Path, cache_dir: Path) -> Path:
    sample_path = Path(sample_path)
    if sample_path.suffix.lower() == ".wav" and sample_path.is_file():
        return sample_path
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav = cache_dir / f"{sample_path.stem}_ref.wav"
    if wav.is_file() and wav.stat().st_mtime >= sample_path.stat().st_mtime:
        return wav
    if _ffmpeg_to_wav(sample_path, wav):
        return wav
    return sample_path


def synthesize_chatterbox(
    text: str,
    sample_path: Path,
    out_path: Path,
    *,
    language: str = "en",
) -> bool:
    """Chatterbox-TTS-Server or OpenAI-compatible clone endpoint."""
    base = _chatterbox_url().rstrip("/")
    narration = (text or "").strip()
    if not narration:
        return False
    sample_path = Path(sample_path)
    headers = {}
    api_key = _env("CHATTERBOX_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    endpoints = [
        (f"{base}/v1/audio/speech", "openai"),
        (f"{base}/tts", "multipart"),
        (f"{base}/api/tts", "multipart"),
    ]
    last_err: Optional[Exception] = None
    for url, mode in endpoints:
        try:
            if mode == "openai":
                payload = {
                    "model": _env("CHATTERBOX_MODEL", "chatterbox"),
                    "input": narration,
                    "voice": _env("CHATTERBOX_VOICE", "default"),
                    "response_format": "mp3",
                }
                ref_b64 = base64.b64encode(sample_path.read_bytes()).decode("ascii")
                payload["reference_audio"] = ref_b64
                data = _http_post_json(url, payload, headers=headers)
            else:
                data = _http_post_multipart(
                    url,
                    {"text": narration, "language": language},
                    {"reference_audio": sample_path, "speaker_wav": sample_path},
                    headers=headers,
                )
            if _write_audio_blob(data, out_path):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_err = exc
            continue
    if last_err:
        return False
    return False


def synthesize_xtts(
    text: str,
    sample_path: Path,
    out_path: Path,
    *,
    language: str = "en",
) -> bool:
    """XTTS via speech gateway or standalone Coqui-style HTTP server."""
    base = _xtts_url().rstrip("/")
    narration = (text or "").strip()
    if not narration:
        return False
    sample_path = Path(sample_path)
    headers = {"Content-Type": "application/json"}
    api_key = _env("SPEECH_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    ref_b64 = base64.b64encode(sample_path.read_bytes()).decode("ascii")
    payloads = [
        {"text": narration, "language": language, "speaker_wav_b64": ref_b64},
        {"text": narration, "language": language, "speaker_wav": str(sample_path)},
    ]
    urls = [
        f"{base}/tts/synthesize",
        f"{base}/tts/xtts",
        f"{base}/v1/tts",
    ]
    for url in urls:
        for payload in payloads:
            try:
                data = _http_post_json(url, payload, headers=headers)
                if _write_audio_blob(data, out_path):
                    return True
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
                continue
    return False


def elevenlabs_add_voice(name: str, sample_path: Path) -> Optional[str]:
    api_key = _env("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    url = "https://api.elevenlabs.io/v1/voices/add"
    try:
        data = _http_post_multipart(
            url,
            {"name": name, "description": "AOEP custom presenter voice"},
            {"files": sample_path},
            headers={"xi-api-key": api_key},
        )
        parsed = json.loads(data.decode("utf-8"))
        return str(parsed.get("voice_id") or "")
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def synthesize_elevenlabs(
    text: str,
    out_path: Path,
    *,
    voice_id: str = "",
    sample_path: Optional[Path] = None,
) -> bool:
    api_key = _env("ELEVENLABS_API_KEY")
    if not api_key:
        return False
    narration = (text or "").strip()
    if not narration:
        return False
    vid = voice_id or _env("ELEVENLABS_VOICE_ID")
    if not vid and sample_path and sample_path.is_file():
        vid = elevenlabs_add_voice("aoep-clone-temp", sample_path) or ""
    if not vid:
        return False
    model = _env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    payload = {
        "text": narration,
        "model_id": model,
        "voice_settings": {
            "stability": float(_env("ELEVENLABS_STABILITY", "0.5")),
            "similarity_boost": float(_env("ELEVENLABS_SIMILARITY", "0.75")),
        },
    }
    try:
        data = _http_post_json(url, payload, headers={"xi-api-key": api_key})
        return _write_audio_blob(data, out_path)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def synthesize_cloned(
    text: str,
    out_path: Path,
    *,
    sample_path: Path,
    language: str = "en",
    engine: str = "clone",
    voice_id: str = "",
) -> tuple[bool, str]:
    """Synthesize with a cloning backend. Returns (ok, engine_used)."""
    engine = (engine or "clone").lower()
    engines: Sequence[str]
    if engine == "clone":
        engines = clone_engine_priority()
    else:
        engines = [engine]

    sample = Path(sample_path)
    for name in engines:
        if name in ("edge", "say", "neural"):
            continue
        if name == "chatterbox":
            if synthesize_chatterbox(text, sample, out_path, language=language):
                return True, "chatterbox"
        elif name == "xtts":
            if synthesize_xtts(text, sample, out_path, language=language):
                return True, "xtts"
        elif name == "elevenlabs":
            if synthesize_elevenlabs(
                text, out_path, voice_id=voice_id, sample_path=sample,
            ):
                return True, "elevenlabs"
    return False, ""


def synthesize_for_profile(
    text: str,
    out_path: Path,
    profile: VoiceProfile,
    *,
    repo_root: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
) -> tuple[bool, str]:
    sample = profile.resolved_sample(repo_root=repo_root)
    wav_dir = cache_dir or Path(out_path).parent
    ref = ensure_wav_sample(sample, wav_dir)
    return synthesize_cloned(
        text,
        out_path,
        sample_path=ref,
        language=profile.language,
        engine=profile.tts_engine,
        voice_id=profile.elevenlabs_voice_id,
    )
