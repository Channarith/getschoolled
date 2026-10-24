"""Tests for harvest corpus, discovery, themes, and crawl scaffolding."""

from aoep_shared.harvest.corpus_store import HarvestCorpusStore, chunk_text
from aoep_shared.harvest.discovery import discover_topic, portal_specs, topic_search_queries
from aoep_shared.harvest.themes import resolve_slide_theme


def test_chunk_text_splits_long_prose():
    text = "One. " * 200
    chunks = chunk_text(text, max_chars=100)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)


def test_corpus_index_and_search(tmp_path):
    db = tmp_path / "corpus.db"
    store = HarvestCorpusStore(db)
    store.upsert_source(url="https://example.edu/algebra", license="cc-by", subject="math")
    n = store.index_document(
        url="https://example.edu/algebra",
        title="Algebra Basics",
        text="Linear equations have one variable. Solve by isolating x.",
        subject="mathematics",
    )
    assert n >= 1
    hits = store.search("linear equations", top_k=3)
    assert hits
    assert "linear" in hits[0].body.lower()
    stats = store.stats()
    assert stats["sources"] == 1
    assert stats["chunks"] >= 1


def test_discover_topic_offline():
    specs = discover_topic("algebra", include_portals=False)
    assert specs
    assert all(s.url for s in specs)


def test_portal_specs_curated():
    from aoep_shared.harvest.sources import is_allowed
    from aoep_shared.harvest.vetted_sources import is_denied

    portals = portal_specs()
    assert len(portals) >= 6
    assert not any(is_denied(p.url) for p in portals), "no do-not-harvest host may be a portal"
    # A portal either declares a commercially usable license or leaves it to the page (per-item hosts).
    assert all(p.license is None or is_allowed(p.license) for p in portals)
    assert {"oercommons.org", "open.umn.edu"} <= {p.url.split("/")[2].removeprefix("www.") for p in portals}


def test_topic_search_queries():
    qs = topic_search_queries("machine learning")
    assert any("oercommons" in q for q in qs)
    assert any(".gov" in q for q in qs)


def test_resolve_slide_theme():
    theme = resolve_slide_theme(title="Introduction to Algebra", subject="mathematics")
    assert theme.poster_url.startswith("https://")
    assert theme.wallpaper_url.startswith("https://")
    assert theme.accent_hex.startswith("#")
    assert theme.template == "title_body"
