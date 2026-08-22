"""Live, citation-backed awareness of current events.

This module deliberately keeps current-news evidence transient. It searches
configured providers, accepts only trusted public-interest sources, reads a
small bounded excerpt from each page, and returns evidence for the normal RAG
grounding guard. It never writes article text to a corpus.
"""

from __future__ import annotations

import html
import ipaddress
import copy
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Callable, Iterable, Sequence

from .providers.base import SearchProvider, SearchResult


_CACHE: dict[tuple, tuple[float, "CurrentAwarenessResult"]] = {}
_CACHE_LOCK = threading.Lock()


DEFAULT_TRUSTED_DOMAINS = (
    # International and regional public-interest reporting.
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "aljazeera.com",
    "dw.com",
    "france24.com",
    "nhk.or.jp",
    "channelnewsasia.com",
    "abc.net.au",
    # Primary public and institutional sources.
    "whitehouse.gov",
    "congress.gov",
    "state.gov",
    "usa.gov",
    "un.org",
    "who.int",
    "nato.int",
    "europa.eu",
    "fifa.com",
    "olympics.com",
)

_CURRENT_CUES = re.compile(
    r"\b("
    r"today|tonight|yesterday|this\s+(?:week|month|year)|"
    r"current(?:ly)?|latest|recent(?:ly)?|breaking|live\s+updates?|"
    r"news|headlines?|just\s+happened|what\s+(?:is|are)\s+happening|"
    r"happening\s+(?:globally|now|in\s+the\s+world)|"
    r"who\s+(?:is|are)\s+the\s+(?:current|present)|"
    r"who\s+won\s+the\s+(?:latest|last|recent)|"
    r"ongoing|right\s+now|as\s+of"
    r")\b",
    re.IGNORECASE,
)
_CURRENT_TOPICS = re.compile(
    r"\b("
    r"president|prime\s+minister|government|election|war|conflict|invasion|"
    r"ceasefire|sanctions|world\s+cup|olympics?|champion(?:ship)?|"
    r"outbreak|pandemic|earthquake|hurricane|wildfire|market|economy"
    r")\b",
    re.IGNORECASE,
)
_SENSITIVE = re.compile(
    r"\b(war|conflict|invasion|attack|casualt(?:y|ies)|killed|election|"
    r"president|prime\s+minister|ceasefire|sanctions|outbreak)\b",
    re.IGNORECASE,
)
_INSTRUCTION_LINE = re.compile(
    r"(?im)^.*(?:ignore (?:all |the )?(?:previous|prior) instructions|"
    r"system prompt|developer message|assistant:|you are chatgpt).*$"
)
_DATE_META = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:article:published_time|datePublished|"""
    r"""date)["'][^>]+content=["']([^"']+)["']""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CurrentSource:
    title: str
    url: str
    publisher: str
    snippet: str
    engine: str
    excerpt: str = ""
    published_at: str = ""
    fetched_at: str = ""

    def context_text(self) -> str:
        body = self.excerpt or self.snippet
        return (
            f"CURRENT SOURCE: {self.title}. Publisher: {self.publisher}. "
            f"URL: {self.url}. Evidence: {body}"
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CurrentAwarenessResult:
    query: str
    routed: bool
    status: str
    as_of: str
    sensitive: bool = False
    sources: list[CurrentSource] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    engines_consulted: int = 0
    message: str = ""

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    @property
    def context(self) -> list[str]:
        return [source.context_text() for source in self.sources]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "routed": self.routed,
            "status": self.status,
            "as_of": self.as_of,
            "sensitive": self.sensitive,
            "sources": [source.to_dict() for source in self.sources],
            "rejected": self.rejected,
            "engines_consulted": self.engines_consulted,
            "message": self.message,
        }


class _ArticleTextParser(HTMLParser):
    _SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


def is_current_query(question: str, *, now: datetime | None = None) -> bool:
    """Return True only when a query requests time-sensitive world knowledge."""
    text = " ".join((question or "").split())
    if not text:
        return False
    if _CURRENT_CUES.search(text):
        return True
    current_year = (now or datetime.now(timezone.utc)).year
    years = {int(value) for value in re.findall(r"\b(20\d{2})\b", text)}
    return bool(_CURRENT_TOPICS.search(text) and any(year >= current_year - 1 for year in years))


def is_sensitive_current_query(question: str) -> bool:
    return bool(_SENSITIVE.search(question or ""))


def trusted_domains(configured: str = "") -> tuple[str, ...]:
    custom = tuple(
        value.strip().lower().lstrip(".")
        for value in re.split(r"[,\s]+", configured or "")
        if value.strip()
    )
    return custom or DEFAULT_TRUSTED_DOMAINS


def _publisher(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")


def _publisher_identity(url: str, allowed: Sequence[str]) -> str:
    host = _publisher(url)
    matches = [
        domain
        for domain in allowed
        if host == domain or host.endswith(f".{domain}")
    ]
    root = max(matches, key=len) if matches else host.removeprefix("www.")
    if root in {"bbc.com", "bbc.co.uk"}:
        return "bbc"
    return root


def _trusted(url: str, allowed: Sequence[str]) -> bool:
    host = _publisher(url)
    return bool(
        host
        and any(host == domain or host.endswith(f".{domain}") for domain in allowed)
    )


def _public_host(host: str) -> bool:
    if not host or host.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for entry in addresses:
        ip = ipaddress.ip_address(entry[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _sanitize_evidence(value: str, *, limit: int = 4000) -> str:
    cleaned = _INSTRUCTION_LINE.sub("", html.unescape(value or ""))
    return " ".join(cleaned.split())[:limit]


def _extract_article(raw_html: str) -> tuple[str, str]:
    parser = _ArticleTextParser()
    parser.feed(raw_html)
    published = ""
    matched = _DATE_META.search(raw_html)
    if matched:
        published = matched.group(1).strip()
    return _sanitize_evidence(" ".join(parser.parts)), published


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_domains: Sequence[str]) -> None:
        super().__init__()
        self.allowed_domains = allowed_domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (
            parsed.scheme != "https"
            or not _trusted(newurl, self.allowed_domains)
            or not _public_host(parsed.hostname or "")
        ):
            raise urllib.error.HTTPError(
                newurl, code, "unsafe redirect refused", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_article(
    url: str,
    *,
    allowed_domains: Sequence[str],
    timeout: float = 8.0,
    max_bytes: int = 512_000,
    user_agent: str = "AOEP-Current-Awareness/1.0 (+https://getschoolled.com)",
) -> tuple[str, str]:
    """Read one trusted HTTPS article with SSRF, robots and size protections."""
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not _trusted(url, allowed_domains)
        or not _public_host(parsed.hostname or "")
    ):
        raise ValueError("untrusted or unsafe article URL")

    robots_url = urllib.parse.urlunsplit(
        ("https", parsed.netloc, "/robots.txt", "", "")
    )
    robots = urllib.robotparser.RobotFileParser()
    robots.set_url(robots_url)
    try:
        robots.read()
        if not robots.can_fetch(user_agent, url):
            raise PermissionError("robots.txt disallows article fetch")
    except PermissionError:
        raise
    except Exception:
        # An absent/unreachable robots file is not an affirmative prohibition.
        pass

    opener = urllib.request.build_opener(_SafeRedirect(allowed_domains))
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with opener.open(request, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "html" not in content_type:
            raise ValueError("article is not HTML")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("article exceeds byte limit")
        charset = response.headers.get_content_charset() or "utf-8"
    return _extract_article(body.decode(charset, errors="replace"))


def _search_results(
    query: str,
    engines: Iterable[SearchProvider],
    *,
    max_results: int,
) -> tuple[list[SearchResult], int]:
    results: list[SearchResult] = []
    consulted = 0
    live = [
        engine for engine in engines if getattr(engine, "engine", "") != "mock"
    ]

    def search(engine: SearchProvider):
        return engine.search(query, max_results=max_results)

    with ThreadPoolExecutor(max_workers=min(4, len(live) or 1)) as pool:
        futures = {pool.submit(search, engine): engine for engine in live}
        for future in as_completed(futures):
            try:
                rows = future.result()
            except Exception:
                continue
            consulted += 1
            results.extend(rows)
    return results, consulted


def research_current_topic(
    question: str,
    engines: Sequence[SearchProvider],
    *,
    config=None,
    article_fetcher: Callable[..., tuple[str, str]] = fetch_article,
    now: datetime | None = None,
) -> CurrentAwarenessResult:
    """Search and transiently read trusted sources for a current-world query."""
    stamp = now or datetime.now(timezone.utc)
    as_of = stamp.isoformat().replace("+00:00", "Z")
    routed = is_current_query(question, now=stamp)
    result = CurrentAwarenessResult(
        query=question,
        routed=routed,
        status="not_current",
        as_of=as_of,
        sensitive=is_sensitive_current_query(question),
    )
    if not routed:
        return result
    if config is not None and not getattr(config, "current_awareness_enabled", True):
        result.status = "disabled"
        result.message = "Live current-awareness search is disabled."
        return result

    allowed = trusted_domains(
        getattr(config, "current_awareness_trusted_domains", "") if config else ""
    )
    max_results = max(
        1, min(20, int(getattr(config, "current_awareness_max_results", 8)))
    )
    max_fetches = max(
        1, min(8, int(getattr(config, "current_awareness_max_fetches", 4)))
    )
    timeout = max(
        1.0, min(20.0, float(getattr(config, "current_awareness_timeout_sec", 8.0)))
    )
    cache_ttl = max(
        0, min(3600, int(getattr(config, "current_awareness_cache_ttl_sec", 300)))
    )
    cache_key = (
        question.strip().lower(),
        stamp.date().isoformat(),
        allowed,
        tuple(getattr(engine, "engine", "") for engine in engines),
    )
    if article_fetcher is fetch_article and cache_ttl:
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
            if cached and time.monotonic() - cached[0] < cache_ttl:
                return copy.deepcopy(cached[1])

    search_query = f"{question.strip()} latest verified {stamp.date().isoformat()}"
    rows, result.engines_consulted = _search_results(
        search_query, engines, max_results=max_results
    )
    if not result.engines_consulted:
        result.status = "unavailable"
        result.message = "No live search provider responded."
        return result

    seen_urls: set[str] = set()
    seen_publishers: set[str] = set()
    accepted: list[SearchResult] = []
    for row in rows:
        canonical = row.url.split("#", 1)[0].rstrip("/")
        if not _trusted(canonical, allowed):
            result.rejected.append({"url": row.url, "reason": "untrusted_domain"})
            continue
        if canonical in seen_urls:
            continue
        publisher_id = _publisher_identity(canonical, allowed)
        if publisher_id in seen_publishers:
            result.rejected.append(
                {"url": row.url, "reason": "duplicate_publisher"}
            )
            continue
        seen_urls.add(canonical)
        seen_publishers.add(publisher_id)
        accepted.append(row)

    fetched_at = as_of
    for row in accepted[:max_fetches]:
        excerpt = ""
        published = ""
        try:
            excerpt, published = article_fetcher(
                row.url, allowed_domains=allowed, timeout=timeout
            )
        except Exception as exc:
            result.rejected.append(
                {"url": row.url, "reason": f"fetch_failed:{type(exc).__name__}"}
            )
        snippet = _sanitize_evidence(row.snippet, limit=800)
        excerpt = _sanitize_evidence(excerpt, limit=4000)
        if not (snippet or excerpt):
            continue
        result.sources.append(
            CurrentSource(
                title=_sanitize_evidence(row.title, limit=240),
                url=row.url,
                publisher=_publisher(row.url),
                snippet=snippet,
                engine=row.engine,
                excerpt=excerpt,
                published_at=published,
                fetched_at=fetched_at,
            )
        )

    independent = {
        _publisher_identity(source.url, allowed) for source in result.sources
    }
    required = 2 if result.sensitive else 1
    if len(independent) >= required:
        result.status = "verified"
        result.message = (
            f"Corroborated by {len(independent)} independent trusted publisher(s)."
        )
    elif result.sources:
        result.status = "unverified"
        result.message = (
            f"Found {len(independent)} trusted publisher(s); {required} required."
        )
    else:
        result.status = "unavailable"
        result.message = "No readable evidence from trusted sources was found."
    if article_fetcher is fetch_article and cache_ttl:
        with _CACHE_LOCK:
            _CACHE[cache_key] = (time.monotonic(), copy.deepcopy(result))
            if len(_CACHE) > 256:
                oldest = min(_CACHE, key=lambda key: _CACHE[key][0])
                _CACHE.pop(oldest, None)
    return result
