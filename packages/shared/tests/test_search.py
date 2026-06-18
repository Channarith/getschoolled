"""SearchProvider abstraction + key-gated engine selection tests."""

from aoep_shared.config import load_config
from aoep_shared.factory import build_factory
from aoep_shared.providers.base import SearchProvider, SearchResult
from aoep_shared.providers.search import (
    BingSearchProvider,
    GoogleCSEProvider,
    MockSearchProvider,
    available_engines,
)


def test_mock_search_echoes_query():
    p = MockSearchProvider()
    results = p.search("photosynthesis releases oxygen", max_results=3)
    assert results and isinstance(results[0], SearchResult)
    assert "oxygen" in results[0].snippet
    assert results[0].engine == "mock"


def test_mock_canned_results():
    canned = {"q": [SearchResult("t", "u", "snip", "mock")]}
    p = MockSearchProvider(canned=canned)
    assert p.search("q")[0].title == "t"


def test_engines_default_to_mock_when_no_keys(monkeypatch):
    for k in ("BING_SEARCH_KEY", "GOOGLE_CSE_KEY", "BRAVE_SEARCH_KEY",
              "KAGI_API_KEY", "BAIDU_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    engines = available_engines(load_config(env={}))
    assert len(engines) == 1
    assert isinstance(engines[0], MockSearchProvider)


def test_bing_enabled_when_key_set():
    cfg = load_config(env={"BING_SEARCH_KEY": "abc"})
    engines = available_engines(cfg)
    assert any(isinstance(e, BingSearchProvider) for e in engines)
    assert not any(isinstance(e, MockSearchProvider) for e in engines)


def test_google_requires_both_key_and_cx():
    only_key = GoogleCSEProvider(load_config(env={"GOOGLE_CSE_KEY": "k"}))
    assert only_key.ready() is False
    both = GoogleCSEProvider(load_config(env={"GOOGLE_CSE_KEY": "k", "GOOGLE_CSE_CX": "cx"}))
    assert both.ready() is True


def test_unconfigured_engine_search_raises():
    import pytest

    with pytest.raises(RuntimeError):
        BingSearchProvider(load_config(env={})).search("x")


def test_factory_exposes_search_engines():
    engines = build_factory(load_config(env={})).search_engines()
    assert all(isinstance(e, SearchProvider) for e in engines)
