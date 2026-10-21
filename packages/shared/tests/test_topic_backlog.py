"""Paid-learning topic catalog and the durable harvest backlog."""

from aoep_shared.harvest.corpus_store import HarvestCorpusStore
from aoep_shared.harvest.crawl import CrawlSession
from aoep_shared.harvest.queue_store import PersistentHarvestQueue
from aoep_shared.harvest.sources import is_allowed
from aoep_shared.harvest.topic_catalog import (
    fill_topic_backlog,
    iter_paid_topics,
    open_seed_specs,
    paid_topic_count,
)


def test_paid_catalog_exceeds_one_million_topics():
    count = paid_topic_count()
    assert count > 1_000_000
    sample = []
    for i, topic in enumerate(iter_paid_topics()):
        if i >= 3000:
            break
        sample.append(topic)
    assert len(sample) == 3000
    assert len(set(sample)) == 3000
    assert sample[0].startswith("generative AI:")
    assert " for " in sample[0] and " to " in sample[0]


def test_open_seeds_are_allowed_and_distinct():
    specs = open_seed_specs("cybersecurity: threat detection certification prep for job seekers to pass a certification")
    assert len(specs) == 3
    assert len({s.url for s in specs}) == 3
    assert all(is_allowed(s.license) for s in specs)
    assert any("archive.org" in s.url for s in specs)


def test_university_course_seeds_are_open_licensed():
    from pathlib import Path
    import json

    from aoep_shared.harvest.discovery import load_seeds_file

    path = Path(__file__).resolve().parents[3] / "seeds" / "university-courses.jsonl"
    specs = load_seeds_file(path)
    titles = " ".join(s.title or "" for s in specs)
    assert "Stanford CS229" in titles
    assert "UC Berkeley CS 61A" in titles
    assert "Data 8" in titles
    assert all(is_allowed(s.license) for s in specs)
    raw = path.read_text(encoding="utf-8").lower()
    assert "caltech" not in raw
    assert "feynman" not in raw
    assert "nd" not in json.dumps([s.license for s in specs])


def test_backlog_inserts_claims_and_promotes(tmp_path):
    store = HarvestCorpusStore(tmp_path / "corpus.db")
    inserted = fill_topic_backlog(store, limit=25)
    assert inserted == 25
    again = fill_topic_backlog(store, limit=25)
    assert again == 0
    stats = store.stats()
    assert stats["topics_total"] == 25
    assert stats["topics_pending"] == 25

    session = CrawlSession(
        corpus=store,
        queue=PersistentHarvestQueue(store),
        out_dir=tmp_path / "out",
        repo_root=tmp_path,
        with_media=False,
    )
    added = session.promote_backlog(2)
    assert added == 6
    stats = store.stats()
    assert stats["topics_pending"] == 23
    assert stats["queue_pending"] == 6
