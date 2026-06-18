"""Harvester: license gate, queue dedup, worker pipeline + stats."""

from aoep_shared.harvest import (
    HarvestQueue,
    HarvestWorker,
    SourceSpec,
    is_allowed,
)


def test_license_gate():
    assert is_allowed("CC-BY") is True
    assert is_allowed("public domain") is True
    assert is_allowed("All Rights Reserved") is False
    assert is_allowed(None) is False


def test_queue_dedups_urls():
    q = HarvestQueue()
    assert q.enqueue(SourceSpec(url="https://x.org/a", license="cc-by")) is True
    assert q.enqueue(SourceSpec(url="https://x.org/a", license="cc-by")) is False
    assert len(q) == 1


def _worker(out):
    return HarvestWorker(
        fetcher=lambda s: s.meta["body"],
        extractor=lambda s, raw: {"title": s.title or "doc", "text": raw},
        sink=out.append,
    )


def test_worker_ingests_allowed_skips_disallowed_and_dups():
    out = []
    w = _worker(out)
    assert w.process(SourceSpec("u1", license="cc-by", meta={"body": "alpha"})) == "ingested"
    # Disallowed license -> never fetched.
    assert w.process(SourceSpec("u2", license="proprietary", meta={"body": "beta"})) == "skipped_license"
    # Duplicate content -> skipped.
    assert w.process(SourceSpec("u3", license="cc0", meta={"body": "alpha"})) == "skipped_dup"
    assert len(out) == 1
    assert w.stats.ingested == 1
    assert w.stats.skipped_license == 1
    assert w.stats.skipped_dup == 1


def test_worker_runs_queue():
    out = []
    w = _worker(out)
    q = HarvestQueue()
    q.enqueue(SourceSpec("a", license="cc-by", meta={"body": "one"}))
    q.enqueue(SourceSpec("b", license="cc-by", meta={"body": "two"}))
    q.enqueue(SourceSpec("c", license="noncommercial-noderivs-allrights", meta={"body": "three"}))
    stats = w.run(q)
    assert stats.ingested == 2
    assert stats.skipped_license == 1
    assert len(out) == 2
