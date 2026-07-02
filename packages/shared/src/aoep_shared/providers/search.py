"""Web search providers for course validation.

A pluggable set of search-engine adapters. Each real engine is enabled only
when its API key is configured (``ready()``); a deterministic
``MockSearchProvider`` powers offline tests and no-key runs so the validation
logic is always exercisable. Network calls are import-guarded and live inside
``search`` so importing this module never requires ``requests``.

Engines with real APIs: Bing, Google CSE, Brave, Kagi, Baidu. Yahoo and Ecosia
have no official search API and DuckDuckGo only a limited one, so they are
best-effort/omitted here.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..config import AppConfig
from .base import ProviderInfo, SearchProvider, SearchResult


class MockSearchProvider(SearchProvider):
    """Deterministic offline search. Echoes the query as supporting evidence,
    and can be seeded with canned results for tests."""

    engine = "mock"
    impl = "mock-search"

    def __init__(
        self, config: Optional[AppConfig] = None,
        canned: Optional[Dict[str, List[SearchResult]]] = None,
    ) -> None:
        self._config = config
        self._canned = canned or {}

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability, mode="local", impl=self.impl,
            endpoint="mock://search",
        )

    def ready(self) -> bool:
        return True

    def search(self, query: str, *, max_results: int = 5) -> List[SearchResult]:
        if query in self._canned:
            return self._canned[query][:max_results]
        text = " ".join(query.split())
        return [
            SearchResult(
                title=f"Reference for: {text[:60]}",
                url=f"https://oer.example/search/{abs(hash(text)) % 100000}",
                snippet=text,
                engine=self.engine,
            )
        ][:max_results]


class _HttpSearchProvider(SearchProvider):
    """Base for real key-gated HTTP engines (network used only in search())."""

    engine = "http"
    impl = "http-search"
    endpoint = ""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability, mode="cloud", impl=self.impl,
            endpoint=self.endpoint,
        )

    def _api_key(self) -> str:
        return ""

    def ready(self) -> bool:
        return bool(self._api_key())

    def _request(self, url: str, *, params: dict, headers: dict) -> dict:
        try:
            import requests  # lazy/runtime
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("requests not installed for live search") from exc
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def search(self, query: str, *, max_results: int = 5) -> List[SearchResult]:
        if not self.ready():
            raise RuntimeError(f"{self.engine} search not configured (missing key)")
        return self._do_search(query, max_results)

    def _do_search(self, query: str, max_results: int) -> List[SearchResult]:  # pragma: no cover - needs key/network
        raise NotImplementedError


class BingSearchProvider(_HttpSearchProvider):
    engine = "bing"
    impl = "bing-search"
    endpoint = "https://api.bing.microsoft.com/v7.0/search"

    def _api_key(self) -> str:
        return self._config.bing_search_key

    def _do_search(self, query, max_results):  # pragma: no cover
        data = self._request(
            self.endpoint, params={"q": query, "count": max_results},
            headers={"Ocp-Apim-Subscription-Key": self._api_key()},
        )
        out = []
        for it in data.get("webPages", {}).get("value", [])[:max_results]:
            out.append(SearchResult(it.get("name", ""), it.get("url", ""),
                                    it.get("snippet", ""), self.engine))
        return out


class GoogleCSEProvider(_HttpSearchProvider):
    engine = "google"
    impl = "google-cse"
    endpoint = "https://www.googleapis.com/customsearch/v1"

    def _api_key(self) -> str:
        return self._config.google_cse_key

    def ready(self) -> bool:
        return bool(self._config.google_cse_key and self._config.google_cse_cx)

    def _do_search(self, query, max_results):  # pragma: no cover
        data = self._request(
            self.endpoint,
            params={"key": self._api_key(), "cx": self._config.google_cse_cx,
                    "q": query, "num": min(max_results, 10)},
            headers={},
        )
        return [SearchResult(it.get("title", ""), it.get("link", ""),
                             it.get("snippet", ""), self.engine)
                for it in data.get("items", [])[:max_results]]


class BraveSearchProvider(_HttpSearchProvider):
    engine = "brave"
    impl = "brave-search"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def _api_key(self) -> str:
        return self._config.brave_search_key

    def _do_search(self, query, max_results):  # pragma: no cover
        data = self._request(
            self.endpoint, params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": self._api_key()},
        )
        return [SearchResult(it.get("title", ""), it.get("url", ""),
                             it.get("description", ""), self.engine)
                for it in data.get("web", {}).get("results", [])[:max_results]]


class KagiSearchProvider(_HttpSearchProvider):
    engine = "kagi"
    impl = "kagi-search"
    endpoint = "https://kagi.com/api/v0/search"

    def _api_key(self) -> str:
        return self._config.kagi_api_key

    def _do_search(self, query, max_results):  # pragma: no cover
        data = self._request(
            self.endpoint, params={"q": query, "limit": max_results},
            headers={"Authorization": f"Bot {self._api_key()}"},
        )
        out = []
        for it in data.get("data", [])[:max_results]:
            if it.get("t") == 0:  # search result type
                out.append(SearchResult(it.get("title", ""), it.get("url", ""),
                                        it.get("snippet", ""), self.engine))
        return out


class BaiduSearchProvider(_HttpSearchProvider):
    engine = "baidu"
    impl = "baidu-search"
    endpoint = "https://api.baidu.com/search"  # placeholder; configure per account

    def _api_key(self) -> str:
        return self._config.baidu_api_key

    def _do_search(self, query, max_results):  # pragma: no cover
        data = self._request(
            self.endpoint, params={"q": query, "rn": max_results},
            headers={"Authorization": self._api_key()},
        )
        return [SearchResult(it.get("title", ""), it.get("url", ""),
                             it.get("abstract", ""), self.engine)
                for it in data.get("results", [])[:max_results]]


# Registry of real engines, in preference order.
ENGINE_CLASSES = [
    BingSearchProvider,
    GoogleCSEProvider,
    BraveSearchProvider,
    KagiSearchProvider,
    BaiduSearchProvider,
]


def available_engines(config: AppConfig) -> List[SearchProvider]:
    """Return every configured (ready) engine; fall back to the mock if none."""
    engines: List[SearchProvider] = []
    for cls in ENGINE_CLASSES:
        provider = cls(config)
        if provider.ready():
            engines.append(provider)
    return engines or [MockSearchProvider(config)]
