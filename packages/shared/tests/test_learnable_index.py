"""Tests for the unified learnable content index."""

from aoep_shared.learnable import (
    build_learnable_index,
    learnable_facets,
    learnable_home_rails,
    search_learnable,
)
from aoep_shared.learnable.models import LearnableItem


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


def test_kids_filter_requires_explicit_kids_rating_but_keeps_games():
    items = [
        LearnableItem(
            id="catalog:quantum", source="catalog", source_id="quantum",
            title="Quantum Physics for Beginners", category="Science & Nature",
            subject="physics", maturity_rating="all",
        ),
        LearnableItem(
            id="audio:history", source="audio", source_id="history",
            title="History for Beginners", category="History", subject="history",
            maturity_rating="all", tags=["children"],
        ),
        LearnableItem(
            id="catalog:abc", source="catalog", source_id="abc",
            title="ABC Adventures", category="Early Learning", subject="alphabet",
            maturity_rating="kids", format="interactive",
        ),
        LearnableItem(
            id="game:geometry", source="game", source_id="geometry",
            title="Geometry Arcade", category="Games", subject="geometry",
            maturity_rating="all", format="game",
        ),
    ]

    result = search_learnable(items, kids_only=True, limit=20)["items"]
    assert {item.source_id for item in result} == {"abc", "geometry"}


def test_kids_home_contains_only_curated_learning_and_games():
    rails = learnable_home_rails(build_learnable_index(), kids_only=True, per_rail=50)
    assert [rail["key"] for rail in rails] == ["kids-learning", "games"]
    courses = [course for rail in rails for course in rail["courses"]]
    assert courses
    assert all(
        course["format"] == "game" or course["maturity_rating"] == "kids"
        for course in courses
    )

    learning = next(rail for rail in rails if rail["key"] == "kids-learning")["courses"]
    titles = {course["title"] for course in learning}
    assert {
        "ABC Adventures",
        "Read My First Words",
        "Write Letters & Numbers",
        "Tell Time with Ticky the Clock",
        "Meet the Animal Friends",
        "What Is That? Everyday Objects",
        "Connect the Dots & Discover",
        "Shapes & Colors Parade",
    } <= titles
    assert all(course["deep_link"].startswith("/kids/learn?course=") for course in learning)
