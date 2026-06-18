"""Phase 23 - checkpoint/resume harvest loop."""

from aoep_shared.harvest import (
    CatalogUpsertStore,
    Checkpoint,
    HarvestPipeline,
    HarvestQueue,
    SourceSpec,
    harvest_loop,
)


def _fixture():
    q = HarvestQueue()
    q.enqueue(SourceSpec("https://oer.org/a", license="cc-by", meta={"body": "alpha"}))
    q.enqueue(SourceSpec("https://oer.org/b", license="cc-by", meta={"body": "beta"}))
    store = CatalogUpsertStore()
    pipe = HarvestPipeline(store)
    return q, store, pipe


def _fetch(spec):
    return spec.meta["body"]


def _extract(spec, raw):
    return {"title": spec.url, "text": raw}


def test_loop_ingests_and_records_checkpoint(tmp_path):
    q, store, pipe = _fixture()
    cp = Checkpoint.load(str(tmp_path / "cp.json"))
    m = harvest_loop(q, pipe, fetcher=_fetch, extractor=_extract, batch_id="b1", checkpoint=cp)
    assert m.ingested == 2
    assert len(store.items) == 2
    assert len(cp.done) == 2


def test_resume_skips_already_done(tmp_path):
    path = str(tmp_path / "cp.json")
    # First run drains everything.
    q1, store1, pipe1 = _fixture()
    harvest_loop(q1, pipe1, fetcher=_fetch, extractor=_extract, batch_id="b1",
                 checkpoint=Checkpoint.load(path))
    # Second run with the same seeds + persisted checkpoint -> nothing new.
    q2, store2, pipe2 = _fixture()
    m2 = harvest_loop(q2, pipe2, fetcher=_fetch, extractor=_extract, batch_id="b2",
                      checkpoint=Checkpoint.load(path))
    assert m2.ingested == 0  # all skipped via resume
    assert len(store2.items) == 0


def test_max_items_limits_batch(tmp_path):
    q, store, pipe = _fixture()
    m = harvest_loop(q, pipe, fetcher=_fetch, extractor=_extract, batch_id="b1",
                     checkpoint=Checkpoint.load(str(tmp_path / "cp.json")), max_items=1)
    assert m.ingested == 1
