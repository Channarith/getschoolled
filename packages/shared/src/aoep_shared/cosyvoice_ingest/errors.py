"""Classify ingest failures without keeping secrets from tool stderr."""

from __future__ import annotations

import re
from typing import Mapping

from .guard import is_memory_error, is_rate_limit_text

# Categories the queue and channel report both record.
ERROR_CATEGORIES = (
    "rate_limit",
    "bot_check",
    "http_403",
    "private",
    "unavailable",
    "no_segments",
    "denoise_reject",
    "oom",
    "other",
)

_SECRET_LINE = re.compile(
    r"(cookie|authorization|sapisid|visitor_info|api[_-]?key|passwd|password)",
    re.IGNORECASE,
)


def sanitize_process_text(text: str, limit: int = 1200) -> str:
    """Keep a short tool log and drop lines that look like credentials."""
    kept = []
    for line in (text or "").splitlines():
        if _SECRET_LINE.search(line):
            continue
        kept.append(line)
    out = "\n".join(kept).strip()
    if len(out) > limit:
        out = out[-limit:]
    return out


def classify_download_error(text: str) -> str:
    """Map yt-dlp/ffmpeg download text onto one error category."""
    low = (text or "").lower()
    if is_memory_error(text or ""):
        return "oom"
    if is_rate_limit_text(text or ""):
        return "rate_limit"
    if (
        "sign in to confirm" in low
        or "not a bot" in low
        or "captcha" in low
        or "bot check" in low
    ):
        return "bot_check"
    if "private video" in low or "video is private" in low or "this video is private" in low:
        return "private"
    if "http error 403" in low or "403:" in low or "403 forbidden" in low or "forbidden" in low:
        return "http_403"
    if (
        "unavailable" in low
        or "has been removed" in low
        or "video unavailable" in low
        or "account associated with this video has been terminated" in low
    ):
        return "unavailable"
    if "no wav" in low or "no video formats" in low or "requested format is not available" in low:
        return "no_segments"
    return "other"


def classify_qc_reason(reason: str) -> str:
    """Audio QC failures are denoise_reject. Empty segment lists are no_segments."""
    low = (reason or "").strip().lower()
    if low in {"too_short", "low_snr", "near_silent", "clipping", "clean_failed", "silent_source"}:
        return "denoise_reject"
    if low.startswith("read_failed") or low.startswith("denoise"):
        return "denoise_reject"
    if "segment" in low:
        return "no_segments"
    return "other"


def summarize_counts(counts: Mapping[str, int]) -> str:
    parts = [f"{name}:{int(counts[name])}" for name in ERROR_CATEGORIES if int(counts.get(name) or 0)]
    extra = [
        f"{name}:{int(counts[name])}"
        for name in sorted(counts)
        if name not in ERROR_CATEGORIES and int(counts[name] or 0)
    ]
    return ",".join(parts + extra)
