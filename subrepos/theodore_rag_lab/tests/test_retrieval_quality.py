"""Original golden set and a held-out set drawn from other lessons."""

from theodore_rag_lab.eval_harness import (
    evaluate_index,
    load_curriculum_index,
    load_golden,
    load_heldout_golden,
)
from theodore_rag_lab.rag_tuning import RagTuning


def test_original_and_heldout_sets():
    index = load_curriculum_index()
    original = load_golden()
    heldout = load_heldout_golden()
    assert len(original) == 16
    assert len(heldout) == 6
    assert {row.topic for row in heldout} == {"heldout"}

    tuning = RagTuning()
    base = evaluate_index(index, original, tuning)
    extra = evaluate_index(index, heldout, tuning)
    assert base.recall_at_k >= 0.8
    assert base.mrr >= 0.8
    assert base.rag_quality >= 0.8
    assert base.latency_ms_avg < 100
    assert extra.hits == extra.n
    assert extra.rag_quality >= 0.9
    assert extra.latency_ms_avg < 100
