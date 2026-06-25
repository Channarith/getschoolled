"""Tests for the unified learnable content index."""

from aoep_shared.learnable import (
    build_learnable_index,
    learnable_facets,
    learnable_home_rails,
    search_learnable,
)


def test_build_index_includes_all_sources():
    items = build_learnable_index()
    sources = {i.source for i in items}
    assert "audio" in sources
    assert "lesson" in sources
    assert "language" in sources
    assert "game" in sources
    assert len(items) >= 200


def test_search_finds_live_lesson_and_audio():
    items = build_learnable_index()
    photosynthesis = search_learnable(items, q="photosynthesis", limit=20)["items"]
    assert any(i.source == "lesson" for i in photosynthesis)
    audio = search_learnable(items, format="audio", limit=20)["items"]
    assert audio and all(i.format == "audio" for i in audio)


def test_home_rails_include_live_and_audio():
    rails = learnable_home_rails(build_learnable_index(), per_rail=6)
    keys = {r["key"] for r in rails}
    assert "live" in keys
    assert "audio" in keys
    assert any(r["courses"] for r in rails)


def test_facets_cover_formats_and_sources():
    facets = learnable_facets(build_learnable_index())
    assert "audio" in facets["formats"]
    assert "lesson" in facets["sources"]
    assert len(facets["categories"]) >= 5
