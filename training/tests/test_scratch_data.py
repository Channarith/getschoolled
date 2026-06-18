"""Track A.1 data pipeline + tokenizer tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratch" / "data"))

from data_pipeline import (  # noqa: E402
    WordTokenizer,
    decontaminate,
    dedup,
    quality_ok,
    run_pipeline,
    shard,
)


def test_quality_filter_drops_short_and_boilerplate():
    assert quality_ok("a" * 5, min_chars=200) is False
    assert quality_ok("All rights reserved. " * 20, min_chars=50) is False
    assert quality_ok("spam " * 100, min_chars=50) is False  # low diversity
    good = ("Photosynthesis is the process by which green plants convert sunlight, "
            "water, and carbon dioxide into glucose and oxygen, storing energy in "
            "chemical bonds that power cellular respiration across ecosystems.")
    assert quality_ok(good, min_chars=50) is True


def test_dedup_removes_near_duplicates():
    base = "the mitochondria is the powerhouse of the cell and makes atp energy " * 3
    near = base + " indeed"
    distinct = "volcanoes form where tectonic plates diverge and magma rises upward " * 3
    out = dedup([base, near, distinct], threshold=0.7)
    assert len(out) == 2  # near-dup folded into base


def test_decontamination_removes_eval_overlap():
    eval_q = "what is the capital of france it is paris the city of lights in europe"
    train = [eval_q + " and more text here", "completely unrelated biology content about cells"]
    out = decontaminate(train, [eval_q], n=6)
    assert len(out) == 1
    assert "biology" in out[0]


def test_shard_sizes():
    docs = [f"doc {i}" for i in range(10)]
    shards = shard(docs, docs_per_shard=4)
    assert [len(s) for s in shards] == [4, 4, 2]


def test_tokenizer_train_encode_decode():
    tok = WordTokenizer.train(["alpha beta gamma", "alpha beta"], vocab_size=10)
    ids = tok.encode("alpha beta zzz")
    assert ids[0] == tok.vocab["alpha"]
    assert ids[-1] == tok.vocab["<unk>"]  # unseen word
    assert tok.decode(ids[:2]) == "alpha beta"


def test_run_pipeline_end_to_end():
    docs = [
        "Photosynthesis in plants converts sunlight water and carbon dioxide into glucose. " * 4,
        "Photosynthesis in plants converts sunlight water and carbon dioxide into glucose. " * 4,  # dup
        "short",
        "The water cycle moves water through evaporation condensation and precipitation stages. " * 4,
    ]
    res = run_pipeline(docs, [], min_chars=50, docs_per_shard=10, vocab_size=100)
    assert res["in"] == 4
    assert res["kept"] == 2  # dup + short removed
    assert res["vocab_size"] > 4
