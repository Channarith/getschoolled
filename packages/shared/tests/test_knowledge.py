"""Bayesian Knowledge Tracing + SkillGraph tests."""

from aoep_shared.knowledge import (
    BayesianKnowledgeTracing,
    BKTParams,
    SkillGraph,
)


def test_bkt_correct_increases_incorrect_decreases():
    bkt = BayesianKnowledgeTracing()
    p = 0.5
    up = bkt.update(p, correct=True)
    down = bkt.update(p, correct=False)
    assert up > p
    assert down < p


def test_bkt_sequence_converges_with_repeated_correct():
    bkt = BayesianKnowledgeTracing()
    p = bkt.sequence([True, True, True, True, True])
    assert p > 0.9


def test_bkt_forgetting_reduces():
    no_forget = BayesianKnowledgeTracing(BKTParams(p_forget=0.0)).update(0.9, True)
    forget = BayesianKnowledgeTracing(BKTParams(p_forget=0.3)).update(0.9, True)
    assert forget < no_forget


def test_bkt_p_correct_monotonic():
    bkt = BayesianKnowledgeTracing()
    assert bkt.p_correct(0.9) > bkt.p_correct(0.1)


def test_skillgraph_gates_by_prereq():
    g = SkillGraph()
    g.add_prereq("fractions", "division")
    # Strong fractions but weak division -> gated down.
    out = g.propagate({"division": 0.2, "fractions": 0.9})
    assert out["fractions"] < 0.9
    assert out["division"] == 0.2


def test_skillgraph_ready():
    g = SkillGraph()
    g.add_prereq("calculus", "algebra")
    assert g.ready("calculus", {"algebra": 0.8}) is True
    assert g.ready("calculus", {"algebra": 0.5}) is False
    assert g.ready("algebra", {}) is True  # no prereqs
