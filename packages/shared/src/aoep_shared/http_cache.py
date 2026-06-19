"""Edge-cacheable response helpers + ETag middleware.

Hot read endpoints (catalog, audio courses, language metadata, ...) almost
never change between requests, so the cheapest scaling lever is to let a
CDN / browser cache them. This module adds:

* ``apply_cache_control`` - declarative per-route Cache-Control rule
  registry. Routes register a TTL + visibility (public/private) and the
  middleware injects the right Cache-Control + Vary headers on the way
  out.
* ``etag_middleware`` - hashes the response body and serves a 304 when the
  client sends ``If-None-Match: <etag>``. Combined with Cache-Control this
  gives a CDN cheap revalidation and trims megabytes of bandwidth for
  catalog endpoints.

Both are pure FastAPI middlewares (no extra deps), they bail out cleanly
for streaming / SSE responses, and they only act on safe methods (GET /
HEAD).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Iterable, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheRule:
    max_age: int                 # seconds the client/CDN may serve from cache
    s_maxage: Optional[int] = None  # CDN-only override (defaults to max_age)
    visibility: str = "public"   # 'public' or 'private'
    stale_while_revalidate: int = 0
    vary: tuple[str, ...] = ("accept", "accept-language")

    def header(self) -> str:
        parts = [self.visibility, f"max-age={self.max_age}"]
        if self.s_maxage is not None:
            parts.append(f"s-maxage={self.s_maxage}")
        if self.stale_while_revalidate > 0:
            parts.append(f"stale-while-revalidate={self.stale_while_revalidate}")
        return ", ".join(parts)


class CacheRegistry:
    """Maps URL-path prefix -> CacheRule. The longest matching prefix wins."""

    def __init__(self) -> None:
        self._rules: list[tuple[str, CacheRule]] = []

    def register(self, prefix: str, rule: CacheRule) -> None:
        self._rules.append((prefix, rule))
        # Keep the registry sorted longest-first so .match returns the most
        # specific rule when prefixes overlap (e.g. /audio/courses/{id} beats
        # /audio).
        self._rules.sort(key=lambda r: -len(r[0]))

    def match(self, path: str) -> Optional[CacheRule]:
        for prefix, rule in self._rules:
            if path.startswith(prefix):
                return rule
        return None


def install(app, registry: CacheRegistry, *, etag: bool = True) -> None:
    """Install Cache-Control + ETag middlewares onto a FastAPI app."""
    from fastapi import Request
    from starlette.responses import Response

    @app.middleware("http")
    async def _cache_mw(request: Request, call_next):
        response: Response = await call_next(request)
        if request.method not in ("GET", "HEAD"):
            return response
        if response.status_code >= 400:
            return response
        rule = registry.match(request.url.path)
        if rule is None:
            return response
        response.headers.setdefault("Cache-Control", rule.header())
        if rule.vary:
            response.headers.setdefault("Vary", ", ".join(rule.vary))
        return response

    if not etag:
        return

    @app.middleware("http")
    async def _etag_mw(request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)
        response: Response = await call_next(request)
        if response.status_code >= 400:
            return response
        # FastAPI/Starlette wraps responses as StreamingResponse when going
        # through BaseHTTPMiddleware, so we need to drain + rebuild the
        # body. Skip pure streaming endpoints (chunked SSE, file downloads)
        # by checking the content-type.
        ct = response.headers.get("content-type", "")
        if "text/event-stream" in ct or "application/octet-stream" in ct:
            return response
        body_iter = getattr(response, "body_iterator", None)
        if body_iter is None:
            return response
        body_chunks: list[bytes] = []
        async for chunk in body_iter:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body_chunks.append(chunk)
        body = b"".join(body_chunks)
        if not body:
            return Response(content=body, status_code=response.status_code,
                            headers=dict(response.headers),
                            media_type=response.media_type)
        etag = '"' + hashlib.sha1(body).hexdigest()[:16] + '"'
        headers = dict(response.headers)
        headers["ETag"] = etag
        inm = request.headers.get("if-none-match")
        if inm and etag in (h.strip() for h in inm.split(",")):
            keep = {"etag", "cache-control", "vary", "x-request-id"}
            headers_304 = {k: v for k, v in headers.items() if k.lower() in keep}
            return Response(status_code=304, headers=headers_304)
        return Response(content=body, status_code=response.status_code,
                        headers=headers, media_type=response.media_type)


def standard_registry() -> CacheRegistry:
    """A safe default for the AOEP read-heavy endpoints.

    Catalog / audio / programs endpoints almost never change between
    deploys, so they get a short browser TTL + a longer CDN TTL with
    stale-while-revalidate so users never see a cold cache during a
    cache-key rotation.
    """
    reg = CacheRegistry()
    reg.register("/audio/categories",      CacheRule(max_age=60,  s_maxage=600,  stale_while_revalidate=300))
    reg.register("/audio/courses",         CacheRule(max_age=60,  s_maxage=300,  stale_while_revalidate=300))
    reg.register("/programs",              CacheRule(max_age=30,  s_maxage=120,  stale_while_revalidate=300))
    reg.register("/courses",               CacheRule(max_age=30,  s_maxage=120,  stale_while_revalidate=300))
    reg.register("/catalog",               CacheRule(max_age=30,  s_maxage=120,  stale_while_revalidate=300))
    reg.register("/notifications/locales", CacheRule(max_age=300, s_maxage=3600, stale_while_revalidate=3600))
    reg.register("/learn/languages",       CacheRule(max_age=300, s_maxage=3600, stale_while_revalidate=3600))
    reg.register("/version",               CacheRule(max_age=10,  s_maxage=60))
    reg.register("/__meta",                CacheRule(max_age=10,  s_maxage=60))
    return reg


def build_iter(*pairs: Iterable[tuple[str, CacheRule]]) -> CacheRegistry:
    reg = CacheRegistry()
    for prefix, rule in pairs:
        reg.register(prefix, rule)
    return reg
