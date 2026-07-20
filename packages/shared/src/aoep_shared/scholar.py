"""Google Scholar publication search via RapidAPI.

Provides ``ScholarProvider.search_publications(query, max_results)`` for
enriching course content with cited academic sources.

Requires ``RAPIDAPI_KEY`` in the environment. Results are cached for 1 hour
to limit API usage and improve response times.
"""

from __future__ import annotations

import json as _json
import os
import time as _time
import urllib.request as _urlreq
from typing import Optional

_HTTP_TIMEOUT = float(os.environ.get("SCHOLAR_HTTP_TIMEOUT", "10"))
_CACHE_TTL = 3600  # 1 hour
_USER_AGENT = "SalareenScholar/1.0 (+https://salareen.com)"

# TTL cache: key -> (expires_at, results)
_CACHE: dict[str, tuple] = {}


def _cache_get(key: str) -> Optional[list]:
    hit = _CACHE.get(key)
    if hit and hit[0] > _time.time():
        return hit[1]
    return None


def _cache_put(key: str, results: list) -> None:
    _CACHE[key] = (_time.time() + _CACHE_TTL, results)


def _parse_pub(p: dict) -> dict:
    """Normalize a raw publication dict into the simplified schema."""
    authors_raw = p.get("authors") or p.get("author") or []
    if isinstance(authors_raw, list):
        authors = [
            (a.get("name") or a.get("author_name") or str(a))
            if isinstance(a, dict) else str(a)
            for a in authors_raw
        ]
    else:
        authors = [str(authors_raw)] if authors_raw else []

    year = (p.get("year") or p.get("pub_year") or p.get("publication_year") or "")
    citations_raw = (p.get("cited_by") or p.get("citations")
                     or p.get("citation_count") or 0)
    try:
        citations = int(citations_raw)
    except (ValueError, TypeError):
        citations = 0

    url = p.get("url") or p.get("pub_url") or p.get("link") or ""
    abstract = (p.get("abstract") or p.get("description") or p.get("snippet") or "")
    title = p.get("title") or p.get("pub_title") or ""

    return {
        "title": str(title),
        "authors": authors,
        "year": str(year) if year else "",
        "abstract": str(abstract)[:500],
        "url": str(url),
        "citations": citations,
    }


class ScholarProvider:
    """Search Google Scholar via RapidAPI (google-scholar1.p.rapidapi.com).

    Requires ``RAPIDAPI_KEY``. Results are cached for 1 hour to limit API
    usage. On any network or parse failure, returns an empty list so callers
    degrade gracefully.

    Usage::

        provider = ScholarProvider(os.environ["RAPIDAPI_KEY"])
        pubs = provider.search_publications("machine learning education", max_results=5)
        # [{"title": ..., "authors": [...], "year": ...,
        #   "abstract": ..., "url": ..., "citations": ...}, ...]
    """

    def __init__(self, rapidapi_key: str) -> None:
        self.rapidapi_key = rapidapi_key

    def search_publications(self, query: str, max_results: int = 5) -> list[dict]:
        """Search Google Scholar and return simplified publication dicts.

        Args:
            query: The search query (e.g. a course topic or concept).
            max_results: Maximum number of publications to return (capped at 20).

        Returns:
            List of dicts with keys: title, authors, year, abstract, url, citations.
            Returns ``[]`` if the key is missing, the API is unavailable, or no
            results were found.
        """
        if not self.rapidapi_key or not query:
            return []

        max_results = max(1, min(max_results, 20))
        cache_key = f"scholar|{query}|{max_results}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        from urllib.parse import urlencode
        params = urlencode({
            "query": query,
            "max_results": max_results,
            "patents": "false",
            "citations": "true",
            "sort_by": "relevance",
            "include_last_year": "abstracts",
            "start_index": "0",
        })
        url = f"https://google-scholar1.p.rapidapi.com/search_pubs?{params}"
        req = _urlreq.Request(url, headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "x-rapidapi-host": "google-scholar1.p.rapidapi.com",
            "x-rapidapi-key": self.rapidapi_key,
        })
        try:
            with _urlreq.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                data = _json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 — network/parse failure -> empty
            return []

        # Normalize the response: try common keys for the publication list.
        pubs: list = []
        if isinstance(data, list):
            pubs = data
        elif isinstance(data, dict):
            for key in ("publications", "results", "data", "articles", "papers"):
                if isinstance(data.get(key), list):
                    pubs = data[key]
                    break

        results = [_parse_pub(p) for p in pubs[:max_results]
                   if isinstance(p, dict)]
        results = [r for r in results if r.get("title")]
        _cache_put(cache_key, results)
        return results


def get_scholar_provider() -> Optional[ScholarProvider]:
    """Return a ``ScholarProvider`` if ``RAPIDAPI_KEY`` is set, else ``None``."""
    key = os.environ.get("RAPIDAPI_KEY", "")
    if not key:
        return None
    return ScholarProvider(key)
