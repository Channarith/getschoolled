import pytest

from aoep_shared.memory_teaching import (
    MEMORY_STRATEGIES,
    build_memory_aid,
    requires_memory_support,
)


def test_builds_multiple_memory_paths_and_retrieval_check():
    aid = build_memory_aid(
        "Mercury, Venus, Earth, Mars",
        topic="the inner planets",
    )
    assert aid["recommended_strategy"] == "acrostic"
    assert aid["aids"]["acronym"] == "MVEM"
    assert len(aid["aids"]["memory_palace"]) == 4
    assert aid["check"]["answer"] == ["Mercury", "Venus", "Earth", "Mars"]
    assert "repeat" not in " ".join(aid["teaching_sequence"]).lower()


def test_preferred_strategy_and_recall_detection():
    aid = build_memory_aid(
        "Encode, Store, Retrieve",
        topic="memory",
        preferred="retrieval_brainteaser",
    )
    assert aid["recommended_strategy"] == "retrieval_brainteaser"
    assert requires_memory_support("How can I remember these steps?")
    assert len(MEMORY_STRATEGIES) >= 8


def test_empty_content_is_rejected():
    with pytest.raises(ValueError):
        build_memory_aid(" ")
