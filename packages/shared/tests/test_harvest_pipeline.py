"""Phase 22 - gate + idempotent batch-versioned catalog upsert."""

from aoep_shared.harvest import (
    CatalogUpsertStore,
    HarvestPipeline,
    SourceSpec,
)


def _rec(title="Doc", text="content"):
    return {"title": title, "text": text}


def test_license_and_validation_gates():
    store = CatalogUpsertStore()
    pipe = HarvestPipeline(store, validator=lambda r: "good" in r["text"])
    m = pipe.run_batch([
        (SourceSpec("u1", license="cc-by"), _rec(text="good content")),
        (SourceSpec("u2", license="proprietary"), _rec(text="good content")),  # license drop
        (SourceSpec("u3", license="cc0"), _rec(text="bad content")),           # validation drop
    ], batch_id="b1")
    assert m.upserted == 1
    assert m.dropped_license == 1
    assert m.dropped_validation == 1
    assert len(store.items) == 1


def test_idempotent_upsert_no_duplicates():
    store = CatalogUpsertStore()
    pipe = HarvestPipeline(store)
    spec = SourceSpec("https://oer.org/a", license="cc-by")
    m1 = pipe.run_batch([(spec, _rec(text="v1"))], batch_id="b1")
    m2 = pipe.run_batch([(spec, _rec(text="v2"))], batch_id="b2")  # same URL again
    assert m1.upserted == 1
    assert m2.updated == 1 and m2.upserted == 0
    assert len(store.items) == 1
    # Latest content wins.
    assert list(store.items.values())[0]["text"] == "v2"


def test_batch_revert_removes_only_that_batch():
    store = CatalogUpsertStore()
    pipe = HarvestPipeline(store)
    pipe.run_batch([(SourceSpec("a", license="cc-by"), _rec())], batch_id="good")
    pipe.run_batch([(SourceSpec("b", license="cc-by"), _rec())], batch_id="bad")
    assert len(store.items) == 2
    removed = store.revert_batch("bad")
    assert removed == 1
    assert len(store.items) == 1
