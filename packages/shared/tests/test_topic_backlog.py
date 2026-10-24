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


def test_open_seeds_are_distinct_and_never_claim_a_license_they_cannot_prove():
    from aoep_shared.harvest.licensing import HarvestPolicy
    from aoep_shared.harvest.sources import prefetch_decision

    specs = open_seed_specs("cybersecurity: threat detection certification prep for job seekers to pass a certification")
    assert len(specs) == 3
    assert len({s.url for s in specs}) == 3
    assert any("archive.org" in s.url for s in specs)
    by_host = {s.url.split("/")[2]: s for s in specs}
    # Internet Archive and OER Commons licenses are per item: nothing is asserted by the seed.
    assert by_host["archive.org"].license is None
    assert by_host["www.oercommons.org"].license is None
    for host in ("archive.org", "www.oercommons.org"):
        gate = prefetch_decision(by_host[host], HarvestPolicy(), allow_unverified=True)
        assert gate.ok and gate.needs_detection
        assert not prefetch_decision(by_host[host], HarvestPolicy()).ok
    # Wikibooks is CC BY-SA: share-alike, so off until the owner turns it on.
    wb = by_host["en.wikibooks.org"]
    assert not prefetch_decision(wb, HarvestPolicy()).ok
    assert prefetch_decision(wb, HarvestPolicy(allow_share_alike=True)).ok


def test_university_course_seeds_are_research_only_and_rejected_for_the_product():
    from pathlib import Path

    from aoep_shared.harvest.discovery import load_seeds_file
    from aoep_shared.harvest.licensing import Tier, parse_license

    root = Path(__file__).resolve().parents[3] / "seeds"
    assert not (root / "university-courses.jsonl").exists(), "NC seeds must not sit in the product seed folder"
    specs = load_seeds_file(root / "research-only" / "university-courses.jsonl")
    titles = " ".join(s.title or "" for s in specs)
    assert "Stanford CS229" in titles and "UC Berkeley CS 61A" in titles and "Data 8" in titles
    assert not any(is_allowed(s.license) for s in specs if parse_license(s.license).tier is Tier.NON_COMMERCIAL)
    assert any(parse_license(s.license).tier is Tier.NON_COMMERCIAL for s in specs)


def test_product_seed_files_only_hold_commercially_usable_verified_licenses():
    from pathlib import Path

    from aoep_shared.harvest.discovery import load_seeds_file
    from aoep_shared.harvest.sources import prefetch_decision

    root = Path(__file__).resolve().parents[3] / "seeds"
    for path in root.glob("*.jsonl"):
        for spec in load_seeds_file(path):
            assert prefetch_decision(spec).ok, (path.name, spec.url)
            assert spec.license_verified_by and spec.license_verified_at and spec.license_evidence, (path.name, spec.url)


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
