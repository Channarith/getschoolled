"""Download operator-supplied YouTube/Vimeo URLs via yt-dlp (optional dep)."""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import urlparse

from .errors import classify_download_error, sanitize_process_text


# Pinned in packages/shared[cosyvoice-ingest] (yt-dlp==2026.8.19).
# Override the binary with YT_DLP_BIN. Upgrade with:
#   pip install -e 'packages/shared[cosyvoice-ingest]'
DEFAULT_YT_DLP = "yt-dlp"
# Whole-process retries after yt-dlp exits. Private videos are not retried.
_RETRYABLE = {"bot_check", "http_403", "unavailable", "other"}


class DownloadError(RuntimeError):
    """yt-dlp / ffmpeg download failed or dependency missing."""

    def __init__(self, message: str, *, category: str = "other", stderr: str = "") -> None:
        super().__init__(message)
        self.category = category or "other"
        self.stderr = stderr or ""


@dataclass
class DownloadedMedia:
    url: str
    media_id: str
    audio_path: Path
    title: str = ""
    skipped: bool = False
    reason: str = ""


def _media_id_for_url(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"src_{digest}"


def _is_playlist_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    qs = (parsed.query or "").lower()
    return "list=" in qs or "/playlist" in path or "/playlists/" in path


def yt_dlp_bin() -> str:
    return os.environ.get("YT_DLP_BIN", DEFAULT_YT_DLP)


def yt_dlp_available() -> bool:
    return shutil.which(yt_dlp_bin()) is not None


def cookies_file() -> Optional[Path]:
    """Optional Netscape cookies path. Never creates or reads the file here.

    ``YT_DLP_COOKIES`` or ``COSYVOICE_COOKIES_FILE``. Unset means no cookies.
    A set path that is not a file is reported by the caller; contents are never logged.
    """
    raw = (os.environ.get("YT_DLP_COOKIES") or os.environ.get("COSYVOICE_COOKIES_FILE") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_file():
        return path
    return None


def cookies_requested() -> bool:
    return bool((os.environ.get("YT_DLP_COOKIES") or os.environ.get("COSYVOICE_COOKIES_FILE") or "").strip())


def build_yt_dlp_command(
    url: str,
    dest_dir: Path,
    media_id: str,
    *,
    sample_rate: int,
    cookies: Optional[Path],
) -> list[str]:
    cmd = [
        yt_dlp_bin(),
        "--yes-playlist" if _is_playlist_url(url) else "--no-playlist",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args",
        f"ffmpeg:-ar {sample_rate} -ac 1 -sample_fmt s16",
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "linear=1::2",
        "-o", str(dest_dir / f"{media_id}.%(ext)s"),
        "--write-info-json",
        "--no-warnings",
    ]
    if cookies is not None:
        cmd.extend(["--cookies", str(cookies)])
    sleep_requests = os.environ.get("YT_DLP_SLEEP_REQUESTS", "1")
    if sleep_requests and sleep_requests != "0":
        cmd.extend(["--sleep-requests", sleep_requests])
    cmd.append(url)
    return cmd


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def _pace(sleep: Callable[[float], None], rng: random.Random) -> None:
    base = _env_float("YT_DLP_MIN_INTERVAL", 1.0)
    if base <= 0:
        return
    sleep(base + rng.random() * min(base, 1.0))


def _backoff(attempt: int, sleep: Callable[[float], None], rng: random.Random) -> None:
    base = _env_float("YT_DLP_BACKOFF", 2.0)
    if base <= 0:
        return
    # attempt is 1 on the first retry.
    sleep(base * (2 ** (attempt - 1)) + rng.random() * base)


def _raise_download_error(url: str, text: str) -> None:
    clean = sanitize_process_text(text)
    category = classify_download_error(clean or text)
    short = clean.replace("\n", " ")[:400]
    raise DownloadError(
        f"yt-dlp failed for {url}: {short}",
        category=category,
        stderr=clean,
    )


def download_url(
    url: str,
    dest_dir: Path,
    *,
    sample_rate: int = 24000,
    sleep: Callable[[float], None] = time.sleep,
    rng: Optional[random.Random] = None,
) -> DownloadedMedia:
    """Download one URL to mono PCM WAV under ``dest_dir``.

    Requires ``yt-dlp`` (and usually ``ffmpeg``). Playlist extraction runs only
    when the operator URL itself is a playlist.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    media_id = _media_id_for_url(url)
    out_wav = dest_dir / f"{media_id}.wav"
    if out_wav.is_file() and out_wav.stat().st_size > 64:
        return DownloadedMedia(
            url=url, media_id=media_id, audio_path=out_wav, skipped=True, reason="cached"
        )

    if not yt_dlp_available():
        raise DownloadError(
            f"{yt_dlp_bin()} not on PATH; "
            "pip install -e 'packages/shared[cosyvoice-ingest]' "
            "or set YT_DLP_BIN. The extra pins yt-dlp==2026.8.19.",
            category="other",
        )
    if cookies_requested() and cookies_file() is None:
        raise DownloadError(
            "YT_DLP_COOKIES or COSYVOICE_COOKIES_FILE is set but the file is not readable",
            category="other",
        )

    clock = rng or random.Random()
    attempts = max(1, int(_env_float("YT_DLP_RETRIES", 3)))
    cookies = cookies_file()
    last_error: Optional[DownloadError] = None
    for attempt in range(attempts):
        if attempt == 0:
            _pace(sleep, clock)
        else:
            _backoff(attempt, sleep, clock)
        cmd = build_yt_dlp_command(
            url, dest_dir, media_id, sample_rate=sample_rate, cookies=cookies
        )
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=3600, text=True)
            last_error = None
            break
        except FileNotFoundError as exc:
            raise DownloadError(f"{yt_dlp_bin()} not found", category="other") from exc
        except subprocess.TimeoutExpired as exc:
            last_error = DownloadError(
                f"download timed out for {url}",
                category="other",
                stderr=sanitize_process_text((exc.stderr or "") if isinstance(exc.stderr, str) else ""),
            )
        except subprocess.CalledProcessError as exc:
            blob = exc.stderr or exc.stdout or ""
            try:
                _raise_download_error(url, blob)
            except DownloadError as err:
                last_error = err
        if last_error is None or last_error.category not in _RETRYABLE:
            break
    if last_error is not None:
        raise last_error

    if not out_wav.is_file():
        wavs = sorted(
            dest_dir.glob(f"{media_id}*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not wavs:
            raise DownloadError(f"no wav produced for {url}", category="no_segments")
        if wavs[0] != out_wav:
            wavs[0].replace(out_wav)

    title = ""
    for cand in dest_dir.glob(f"{media_id}*.info.json"):
        try:
            meta = json.loads(cand.read_text(encoding="utf-8"))
            title = str(meta.get("title") or "")[:200]
            break
        except (OSError, json.JSONDecodeError):
            continue

    return DownloadedMedia(url=url, media_id=media_id, audio_path=out_wav, title=title)


def download_urls(
    urls: List[str], dest_dir: Path, *, sample_rate: int = 24000
) -> List[DownloadedMedia]:
    return [download_url(u, dest_dir, sample_rate=sample_rate) for u in urls]


def copy_local_media(media_dir: Path, dest_dir: Path) -> List[DownloadedMedia]:
    """Stage local audio/video files as if downloaded (skip network)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not media_dir.is_dir():
        raise FileNotFoundError(f"media dir not found: {media_dir}")
    out: List[DownloadedMedia] = []
    exts = {".wav", ".mp3", ".flac", ".m4a", ".mp4", ".webm", ".mkv", ".ogg"}
    for src in sorted(media_dir.iterdir()):
        if not src.is_file() or src.suffix.lower() not in exts:
            continue
        media_id = f"local_{src.stem}"[:64]
        dest = dest_dir / f"{media_id}{src.suffix.lower()}"
        if not dest.exists():
            shutil.copy2(src, dest)
        wav = dest_dir / f"{media_id}.wav"
        if dest.suffix.lower() != ".wav":
            if shutil.which("ffmpeg"):
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", str(dest),
                        "-ar", "24000", "-ac", "1", "-sample_fmt", "s16",
                        str(wav),
                    ],
                    check=False,
                    capture_output=True,
                    timeout=600,
                )
            if not wav.is_file():
                continue
        else:
            if dest.resolve() != wav.resolve():
                shutil.copy2(dest, wav)
        out.append(
            DownloadedMedia(
                url=f"file://{src.resolve()}",
                media_id=media_id,
                audio_path=wav,
                title=src.stem,
                skipped=True,
                reason="local",
            )
        )
    return out
