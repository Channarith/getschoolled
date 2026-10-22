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
from .guard import (
    clear_download_limit,
    cooldown_remaining,
    limit_backoff_seconds,
    note_download_limit,
)


# Pinned in packages/shared[cosyvoice-ingest] (yt-dlp==2026.8.19).
# Override the binary with YT_DLP_BIN. Upgrade with:
#   pip install -e 'packages/shared[cosyvoice-ingest]'
DEFAULT_YT_DLP = "yt-dlp"
# Whole-process retries after yt-dlp exits. Private videos are not retried.
# rate_limit and bot_check use a longer pause than a generic network blip.
_RETRYABLE = {"bot_check", "http_403", "unavailable", "rate_limit", "oom", "other"}
_LIMIT_CATEGORIES = {"bot_check", "rate_limit"}


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


def yt_dlp_auth_args(*, include_client: bool = True) -> List[str]:
    """Operator auth / pacing options from env (never hard-coded cookies).

    YouTube rate-limits anonymous bulk downloads. A signed-in browser profile
    is the working route on the Spark:

      YT_DLP_COOKIES_FROM_BROWSER=chromium:/path/to/chromium/profile
      YT_DLP_COOKIES=/path/to/cookies.txt
      YT_DLP_PLAYER_CLIENT=web_safari
      YT_DLP_SLEEP_REQUESTS=3
    """
    args: List[str] = []
    browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", "").strip()
    cookies = os.environ.get("YT_DLP_COOKIES", "").strip() or os.environ.get("COSYVOICE_COOKIES_FILE", "").strip()
    if browser:
        args.extend(["--cookies-from-browser", browser])
    elif cookies:
        args.extend(["--cookies", cookies])
    client = os.environ.get("YT_DLP_PLAYER_CLIENT", "").strip()
    if client and include_client:
        args.extend(["--extractor-args", f"youtube:player_client={client}"])
    sleep = os.environ.get("YT_DLP_SLEEP_REQUESTS", "").strip()
    if sleep and sleep != "0":
        args.extend(["--sleep-requests", sleep])
    return args


def captions_requested() -> bool:
    """Captions are fetched when asked, or whenever download auth is configured."""
    flag = os.environ.get("AOEP_YT_CAPTIONS", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    if flag in ("1", "true", "yes"):
        return True
    return bool(
        os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", "").strip()
        or os.environ.get("YT_DLP_COOKIES", "").strip()
        or os.environ.get("COSYVOICE_COOKIES_FILE", "").strip()
    )


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
    browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        cmd.extend(["--cookies-from-browser", browser])
    elif cookies is not None:
        cmd.extend(["--cookies", str(cookies)])
    client = os.environ.get("YT_DLP_PLAYER_CLIENT", "").strip()
    if client:
        cmd.extend(["--extractor-args", f"youtube:player_client={client}"])
    if "--sleep-requests" not in cmd:
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


def _limit_pause(attempt: int, sleep: Callable[[float], None], rng: random.Random) -> None:
    """Longer pause after YouTube rate limits and bot checks."""
    pause = limit_backoff_seconds(attempt)
    if pause <= 0:
        return
    sleep(pause + rng.random() * min(pause, 1.0))


def _wait_cooldown(sleep: Callable[[float], None]) -> None:
    remaining = cooldown_remaining()
    if remaining > 0:
        sleep(remaining)


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
    _wait_cooldown(sleep)
    for attempt in range(attempts):
        if attempt == 0:
            _pace(sleep, clock)
        elif last_error is not None and last_error.category in _LIMIT_CATEGORIES:
            _limit_pause(attempt, sleep, clock)
        else:
            _backoff(attempt, sleep, clock)
        cmd = build_yt_dlp_command(
            url, dest_dir, media_id, sample_rate=sample_rate, cookies=cookies
        )
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=3600, text=True)
            last_error = None
            clear_download_limit()
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
        if last_error is not None:
            note_download_limit(last_error.category)
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


def download_captions(
    url: str,
    dest_dir: Path,
    *,
    languages: Optional[List[str]] = None,
) -> List[Path]:
    """Fetch a video's own captions (manual or auto) as VTT files.

    Captions are timed ground truth. Failure must not fail an audio download.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    media_id = _media_id_for_url(url)
    wanted = languages or ["km.*", "en.*"]
    prefixes = tuple(w.rstrip("*").rstrip(".") for w in wanted)
    existing = [
        p
        for p in sorted(dest_dir.glob(f"{media_id}.*.vtt"))
        if any(f".{prefix}" in p.name for prefix in prefixes if prefix)
    ]
    if existing:
        return existing
    if not yt_dlp_available():
        return []
    _wait_cooldown(time.sleep)
    cmd = [
        yt_dlp_bin(),
        *yt_dlp_auth_args(),
        "--no-playlist",
        "-f", "sb0/best",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", ",".join(wanted),
        "--sub-format", "vtt",
        "--no-warnings",
        "-o", str(dest_dir / f"{media_id}.%(ext)s"),
        url,
    ]
    try:
        finished = subprocess.run(cmd, capture_output=True, timeout=300, text=True)
    except Exception:  # noqa: BLE001 — captions are best-effort
        return []
    blob = (finished.stderr or "") + "\n" + (finished.stdout or "")
    if finished.returncode:
        note_download_limit(classify_download_error(blob))
    return sorted(dest_dir.glob(f"{media_id}.*.vtt"))


def parse_vtt(path: Path) -> list[tuple[float, float, str]]:
    """Parse a VTT file into (start_s, end_s, text) rows, de-duplicated."""
    import re

    rows: list[tuple[float, float, str]] = []
    stamp = re.compile(
        r"(\d+):(\d+):(\d+)[.,](\d+)\s*-->\s*(\d+):(\d+):(\d+)[.,](\d+)"
    )
    prev = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    start = end = None
    for line in lines:
        match = stamp.search(line)
        if match:
            g = [int(x) for x in match.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
            continue
        text = re.sub(r"<[^>]+>", "", line).strip()
        if not text or start is None or text == prev:
            continue
        if text.startswith(prev) and prev:
            text = text[len(prev):].strip()
            if not text:
                continue
        rows.append((start, end or start, text))
        prev = re.sub(r"<[^>]+>", "", line).strip()
    return rows


def caption_text_for_window(
    captions: list[tuple[float, float, str]], start_s: float, end_s: float
) -> str:
    """Join caption text whose cues overlap ``[start_s, end_s]``."""
    picked: list[str] = []
    for cue_start, cue_end, text in captions:
        if cue_end >= start_s and cue_start <= end_s and text not in picked:
            picked.append(text)
    return " ".join(picked).strip()


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
