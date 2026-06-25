"""Numpy course composition matrix: nodes/sub-nodes, score, quality, ledger."""

import numpy as np

from aoep_shared.harvest import (
    NUM_CATEGORIES,
    CompositionOutcomeLedger,
    CourseComposition,
    classify_section,
)


def test_classify_section_keywords():
    assert classify_section("Introduction") == "introduction"
    assert classify_section("A brief History of jazz") == "history"
    assert classify_section("Example 2: titration") == "example"
    assert classify_section("Watch this video") == "video"
    assert classify_section("Q&A") == "qanda"
    assert classify_section("Summary and takeaways") == "summary"
    # Unknown topic falls back to a concept node.
    assert classify_section("Photosynthesis") == "concept"


def test_matrix_shape_and_node_vector():
    comp = CourseComposition(subject="chemistry")
    comp.add_node("introduction", "Welcome")
    comp.add_node("example", "Example 1")
    comp.add_node("example", "Example 2")
    assert comp.matrix.shape == (NUM_CATEGORIES, comp.max_subnodes)
    assert isinstance(comp.matrix, np.ndarray)
    # Two distinct example sub-nodes -> example category total weight 2.
    vec = comp.node_vector()
    assert vec.sum() == 3
    assert comp.total_nodes() == 3
    counts = comp.subnode_counts()
    from aoep_shared.harvest import CATEGORY_INDEX
    assert counts[CATEGORY_INDEX["example"]] == 2


def test_repeated_labelled_subnode_accrues_weight():
    comp = CourseComposition()
    comp.add_node("history", "music", weight=1.0)
    comp.add_node("history", "music", weight=2.0)  # same subtopic -> same slot
    from aoep_shared.harvest import CATEGORY_INDEX
    i = CATEGORY_INDEX["history"]
    assert comp.subnode_counts()[i] == 1
    assert comp.node_vector()[i] == 3.0


def test_pcs_matches_published_worked_example():
    # README "Course Composition Score" worked example: {intro x1, example x2}.
    # intro(p=2): a0=4 -> 8 ; example(p=11): a4=1*4+2*4=12 -> 132 ; R=140
    # R' = 140 + 101*N(3) + 103*K(2) = 649 ; PCS = 649 mod 1000 = 649.
    comp = CourseComposition(subject="chemistry")
    comp.add_node("introduction", "Welcome")
    comp.add_node("example", "Example 1")
    comp.add_node("example", "Example 2")
    assert comp.composition_score(modulus=0) == 649  # raw R'
    assert comp.composition_score() == 649           # PCS (mod 1000)


def test_composition_score_is_deterministic_and_bounded():
    a = CourseComposition().add_node("introduction", "x").add_node("example", "y")
    b = CourseComposition().add_node("introduction", "x").add_node("example", "y")
    assert a.composition_score() == b.composition_score()
    assert 0 <= a.composition_score() < 1000
    # Different recipe -> (almost certainly) different score + signature.
    c = CourseComposition().add_node("video", "z").add_node("quiz", "w")
    assert a.composition_signature() != c.composition_signature()


def test_quality_metrics_and_index():
    comp = CourseComposition()
    for cat in ("introduction", "concept", "example", "quiz", "qanda", "summary"):
        comp.add_node(cat, f"{cat}-1")
    m = comp.quality_metrics()
    assert 0.0 < m["coverage"] <= 1.0
    assert 0.0 <= m["balance"] <= 1.0
    assert m["interactivity"] > 0  # example/quiz/qanda are interactive
    assert 0.0 <= comp.quality_index() <= 100.0


def test_to_from_dict_roundtrip_preserves_score():
    comp = CourseComposition(subject="bio").add_node("history", "music")
    comp.add_node("example", "cells")
    data = comp.to_dict()
    again = CourseComposition.from_dict(data)
    assert again.composition_score() == comp.composition_score()
    assert again.composition_signature() == comp.composition_signature()
    assert again.subject == "bio"


def test_outcome_ledger_compares_recipes():
    ledger = CompositionOutcomeLedger()
    # Recipe 247 made students happier than recipe 148 in chemistry.
    for h in (5, 4, 5):
        ledger.record(composition_score=247, happiness=h, subject="chemistry", course_id="c1")
    for h in (3, 2, 3):
        ledger.record(composition_score=148, happiness=h, subject="chemistry", course_id="c2")
    cmp = ledger.compare(247, 148, subject="chemistry")
    assert cmp["winner"] == 247
    assert cmp["a"]["avg_happiness"] > cmp["b"]["avg_happiness"]
    best = ledger.best_scores("chemistry", top_n=1)
    assert best and best[0]["composition_score"] == 247
