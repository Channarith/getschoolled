"""Polite HTTP fetch for the 24/7 harvester.

Rules this module enforces for every request (and every redirect hop):
  * identifying User-Agent with a contact URL or address, from HARVEST_USER_AGENT.
    No contact means no crawling (fail closed): the old example.org default is gone.
  * robots.txt is always read (cached per host) and honored, including Crawl-delay.
    A robots.txt that cannot be fetched because of a server error or network failure
    blocks the host for a while; a 404 means no restrictions.
  * per-host minimum delay on top of the global requests-per-second cap.
  * hosts on the do-not-harvest list are never fetched (vetted_sources.DENYLIST).
  * login walls and paywalls (401/402/403, redirects to login pages) are refused.
  * a bounded body size.
"""

from __future__ import annotations

import os
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from .errors import FetchBlocked, HarvestConfigError
from .sources import SourceSpec
from .vetted_sources import is_denied

_LAST_FETCH = 0.0
_HOST_LAST: Dict[str, float] = {}
_ROBOTS: Dict[str, Tuple[float, Any, str]] = {}   # host -> (fetched_at, parser|None, status)
_LOCK = threading.Lock()
_ROBOTS_TTL = 24 * 3600
_ROBOTS_ERROR_TTL = 3600
MAX_BYTES = 20 * 1024 * 1024
_LOGIN_PATH = re.compile(r"/(log-?in|sign-?in|signin|sso|auth|account/login|users/sign_in|subscribe|paywall)(/|$|\?)", re.I)


def _user_agent() -> str:
    ua = (os.environ.get("HARVEST_USER_AGENT") or "").strip()
    if not ua:
        try:
            from ..config import load_config

            ua = (load_config().harvest_user_agent or "").strip()
        except Exception:
            ua = ""
    has_contact = bool(re.search(r"https?://|mailto:|@[\w.-]+\.\w+", ua))
    placeholder = bool(re.search(r"example\.(org|com)|contact@example", ua, re.I))
    if not ua or not has_contact or placeholder:
        raise HarvestConfigError(
            "HARVEST_USER_AGENT must name the crawler and a real contact, for example "
            "'SalareenHarvester/1.0 (+https://www.salareen.com/contact)'. Refusing to crawl without one."
        )
    return ua


def _robot_token(ua: str) -> str:
    return ua.split("/", 1)[0].split()[0] if ua else "*"


def _max_rps() -> float:
    try:
        from ..config import load_config

        return max(0.1, float(load_config().harvest_max_rps or 1.0))
    except Exception:
        return 1.0


def _host_delay() -> float:
    try:
        return max(0.0, float(os.environ.get("HARVEST_HOST_DELAY", "2.0")))
    except ValueError:
        return 2.0


def _sleep_for_host(host: str, crawl_delay: float) -> None:
    global _LAST_FETCH
    with _LOCK:
        now = time.monotonic()
        wait = max(
            (1.0 / _max_rps()) - (now - _LAST_FETCH),
            max(_host_delay(), crawl_delay) - (now - _HOST_LAST.get(host, 0.0)),
            0.0,
        )
    if wait > 0:
        time.sleep(wait)
    with _LOCK:
        _LAST_FETCH = _HOST_LAST[host] = time.monotonic()


def _rate_limit() -> None:
    """Back-compat global limiter (callers that predate per-host delay)."""
    _sleep_for_host("*", 0.0)


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


def _robots_parser(url: str, ua: str, timeout: int) -> Tuple[Optional[urllib.robotparser.RobotFileParser], str, float]:
    """Return (parser or None meaning disallow-all, status, crawl_delay)."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    origin = f"{p.scheme}://{p.netloc}"
    now = time.time()
    cached = _ROBOTS.get(origin)
    if cached and now - cached[0] < (_ROBOTS_TTL if cached[2] != "error" else _ROBOTS_ERROR_TTL):
        parser, status = cached[1], cached[2]
    else:
        parser, status = None, "error"
        req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": ua, "Accept": "text/plain"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (http/https only, checked by caller)
                body = resp.read(512 * 1024).decode("utf-8", errors="replace")
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(body.splitlines())
            status = "ok"
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                parser, status = urllib.robotparser.RobotFileParser(), "none"   # no robots.txt: no restrictions
                parser.parse([])
            else:
                parser, status = None, "error"
        except Exception:
            parser, status = None, "error"
        _ROBOTS[origin] = (now, parser, status)
    delay = 0.0
    if parser is not None:
        try:
            delay = float(parser.crawl_delay(_robot_token(ua)) or parser.crawl_delay("*") or 0.0)
        except Exception:
            delay = 0.0
    _ = host
    return parser, status, delay


def check_url_allowed(url: str, *, ua: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
    """Policy check for one URL. Raises FetchBlocked, otherwise returns the robots record."""
    ua = ua or _user_agent()
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchBlocked(f"unsupported URL: {url}")
    denied = is_denied(url)
    if denied is not None:
        raise FetchBlocked(f"{denied.domain} is on the do-not-harvest list: {denied.reason}")
    if _LOGIN_PATH.search(p.path or ""):
        raise FetchBlocked(f"login or paywall URL: {url}")
    parser, status, delay = _robots_parser(url, ua, timeout)
    if parser is None:
        raise FetchBlocked(f"robots.txt for {p.hostname} could not be read; skipping for now")
    if not parser.can_fetch(_robot_token(ua), url):
        raise FetchBlocked(f"robots.txt disallows {url}")
    return {"allowed": True, "robots_status": status, "crawl_delay": delay,
            "robots_url": f"{p.scheme}://{p.netloc}/robots.txt",
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


class _PoliteRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, ua: str) -> None:
        super().__init__()
        self._ua = ua

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        check_url_allowed(newurl, ua=self._ua)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass
class FetchResult:
    data: bytes
    source_type: str
    final_url: str
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    robots: Dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def info(self) -> Dict[str, Any]:
        return {"final_url": self.final_url, "status": self.status, "headers": self.headers,
                "robots": self.robots, "fetched_at": self.fetched_at}


_KEEP_HEADERS = ("content-type", "x-robots-tag", "last-modified", "etag", "link", "content-language")


def fetch_page(spec: SourceSpec, *, timeout: int = 30) -> FetchResult:
    """Fetch ``spec.url`` under the politeness rules; raises FetchBlocked/HarvestConfigError."""
    ua = _user_agent()
    robots = check_url_allowed(spec.url, ua=ua, timeout=min(timeout, 15))
    host = (urlparse(spec.url).hostname or "").lower()
    _sleep_for_host(host, float(robots.get("crawl_delay") or 0.0))
    opener = urllib.request.build_opener(_PoliteRedirect(ua))
    req = urllib.request.Request(spec.url, headers={"User-Agent": ua, "Accept": "*/*"}, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise FetchBlocked(f"response larger than {MAX_BYTES // (1024 * 1024)} MB: {spec.url}")
            final_url = resp.geturl()
            if final_url != spec.url:
                check_url_allowed(final_url, ua=ua)
            hdrs = {k.lower(): v for k, v in resp.headers.items() if k.lower() in _KEEP_HEADERS}
            ctype = hdrs.get("content-type", "")
            st = spec.source_type if spec.source_type not in ("url", "") else _infer_type(final_url, ctype)
            return FetchResult(data, st, final_url, resp.status, hdrs, robots)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 402, 403, 407, 451):
            raise FetchBlocked(f"HTTP {exc.code} (login wall, paywall or blocked): {spec.url}") from exc
        raise


def fetch_url(spec: SourceSpec, *, timeout: int = 30) -> tuple[bytes, str]:
    """Fetch ``spec.url``; returns (body_bytes, detected_source_type).

    The full FetchResult details (final URL, headers, robots record) are left on
    ``spec.fetch_info`` for the license check and provenance.
    """
    res = fetch_page(spec, timeout=timeout)
    spec.fetch_info = res.info()  # type: ignore[attr-defined]
    return res.data, res.source_type


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
        if _LOGIN_PATH.search(p.path or ""):
            continue
        if is_denied(full) is not None:
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
        if len(out) >= max_links:
            break
    return out
