"""End-to-end answer scoring on the harness. No lab HTTP, no GPU."""

from theodore_rag_lab.eval_harness import (
    build_demo_index,
    evaluate_answers,
    load_golden,
    load_heldout_golden,
)
from theodore_rag_lab.rag_tuning import RagTuning


def test_golden_sets_stay_split():
    original = load_golden()
    heldout = load_heldout_golden()
    assert len(original) == 16
    assert len(heldout) == 6
    assert {row.topic for row in heldout} == {"heldout"}


def test_generated_answer_changes_groundedness_and_f1():
    index = build_demo_index()
    examples = [
        row
        for row in load_golden()
        if row.expected_doc_ids and row.expected_doc_ids[0] in {"photosynthesis", "gravity", "python"}
    ]
    tuning = RagTuning(top_k=3, min_score=0.0)

    def echo_expected(query, _passages):
        match = next(row for row in examples if row.query == query)
        return match.expected_answer

    good = evaluate_answers(index, examples, tuning, echo_expected, include_details=True)
    bad = evaluate_answers(
        index,
        examples,
        tuning,
        lambda _query, _passages: "purple elephants invented Tuesday",
        include_details=True,
    )
    assert good.n == len(examples) >= 1
    assert good.answer_f1 == 1.0
    assert good.groundedness > bad.groundedness
    assert good.answer_f1 > bad.answer_f1
    assert good.rag_quality >= bad.rag_quality
    assert good.details[0]["latency_ms"] >= 0.0
    assert "answer" in good.details[0]
