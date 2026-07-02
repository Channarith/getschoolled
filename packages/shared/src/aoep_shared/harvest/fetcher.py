"""Polite HTTP fetch for the 24/7 harvester."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse

from .sources import SourceSpec

_LAST_FETCH = 0.0
_DEFAULT_UA = "AOEP-Harvester/1.0 (+https://github.com/getschoolled; OER research bot)"


def _user_agent() -> str:
    try:
        from ..config import load_config
        return load_config().harvest_user_agent or _DEFAULT_UA
    except Exception:
        return _DEFAULT_UA


def _max_rps() -> float:
    try:
        from ..config import load_config
        return max(0.1, float(load_config().harvest_max_rps or 1.0))
    except Exception:
        return 1.0


def _rate_limit() -> None:
    global _LAST_FETCH
    gap = 1.0 / _max_rps()
    now = time.monotonic()
    wait = gap - (now - _LAST_FETCH)
    if wait > 0:
        time.sleep(wait)
    _LAST_FETCH = time.monotonic()


def _infer_type(url: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    path = urlparse(url).path.lower()
    if "pdf" in ct or path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".pptx"):
        return "pptx"
    if path.endswith(".docx"):
        return "docx"
    return "html"


def fetch_url(spec: SourceSpec, *, timeout: int = 30) -> tuple[bytes, str]:
    """Fetch ``spec.url``; returns (body_bytes, detected_source_type)."""
    _rate_limit()
    req = urllib.request.Request(
        spec.url,
        headers={"User-Agent": _user_agent(), "Accept": "*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            st = spec.source_type if spec.source_type not in ("url", "") else _infer_type(spec.url, ctype)
            return data, st
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise PermissionError(f"blocked: {spec.url}") from exc
        raise


def fetch_text(spec: SourceSpec) -> str:
    """Fetch and decode as text (HTML pages)."""
    data, _ = fetch_url(spec)
    return data.decode("utf-8", errors="replace")


_HTML_LINK = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def extract_links(html: str, *, base_url: str, max_links: int = 20) -> list[str]:
    """Pull same-site educational links for shallow crawl expansion."""
    from urllib.parse import urljoin, urlparse
    base = urlparse(base_url)
    out: list[str] = []
    seen: set[str] = set()
    for m in _HTML_LINK.finditer(html or ""):
        href = m.group(1).strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        full = urljoin(base_url, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc != base.netloc and not p.netloc.endswith(".gov") and not p.netloc.endswith(".edu"):
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
        if len(out) >= max_links:
            break
    return out
