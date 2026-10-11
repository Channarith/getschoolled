"""Download operator-supplied YouTube/Vimeo URLs via yt-dlp (optional dep)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse


# Pinned in packages/shared[cosyvoice-ingest]; override with YT_DLP_BIN.
DEFAULT_YT_DLP = "yt-dlp"


class DownloadError(RuntimeError):
    """yt-dlp / ffmpeg download failed or dependency missing."""


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


def download_url(
    url: str,
    dest_dir: Path,
    *,
    sample_rate: int = 24000,
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
            "or set YT_DLP_BIN"
        )

    cmd = [
        yt_dlp_bin(),
        "--yes-playlist" if _is_playlist_url(url) else "--no-playlist",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args",
        f"ffmpeg:-ar {sample_rate} -ac 1 -sample_fmt s16",
        "-o", str(dest_dir / f"{media_id}.%(ext)s"),
        "--write-info-json",
        "--no-warnings",
        url,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600, text=True)
    except FileNotFoundError as exc:
        raise DownloadError(f"{yt_dlp_bin()} not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise DownloadError(f"download timed out for {url}") from exc
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or "")[-800:]
        raise DownloadError(f"yt-dlp failed for {url}: {err}") from exc

    if not out_wav.is_file():
        wavs = sorted(
            dest_dir.glob(f"{media_id}*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not wavs:
            raise DownloadError(f"no wav produced for {url}")
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
