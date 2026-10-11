"""Parse operator-supplied URL / playlist lists (no scraping)."""

from __future__ import annotations

from pathlib import Path
from typing import List
from urllib.parse import urlparse


_ALLOWED_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "vimeo.com",
    "player.vimeo.com",
)


def is_allowed_media_url(url: str) -> bool:
    """True for YouTube / Vimeo http(s) URLs the operator may supply."""
    raw = (url or "").strip()
    if not raw or raw.startswith("#"):
        return False
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return any(host == s or host.endswith("." + s) for s in _ALLOWED_HOST_SUFFIXES)


def load_url_list(path: Path | str) -> List[str]:
    """Load one URL per line; blank lines and ``#`` comments ignored.

    Raises ``ValueError`` if a non-comment line is not an allowed YouTube/Vimeo URL.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"URL list not found: {p}")
    out: List[str] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if not is_allowed_media_url(text):
            raise ValueError(
                f"{p}:{lineno}: only operator-supplied YouTube/Vimeo http(s) URLs "
                f"are accepted (got {text!r})"
            )
        out.append(text)
    return out
