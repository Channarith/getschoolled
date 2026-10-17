"""RAG skeleton retrieval over the sample curriculum."""

from pathlib import Path

from aoep_shared.rag import Document, RagIndex

# repo_root/packages/shared/tests/test_rag.py -> repo_root
SAMPLE_CURRICULUM = Path(__file__).resolve().parents[3] / "sample-curriculum"


def test_retrieve_ranks_relevant_doc_first():
    index = RagIndex(
        [
            Document.from_text("a", "Photosynthesis", "Plants convert sunlight into energy."),
            Document.from_text("b", "Gravity", "Objects fall toward the earth due to gravity."),
        ]
    )
    results = index.retrieve("how do plants use sunlight", top_k=1)
    assert results
    assert results[0].document.doc_id == "a"


def test_empty_query_returns_nothing():
    index = RagIndex([Document.from_text("a", "t", "some text")])
    assert index.retrieve("   ") == []


def test_loads_sample_curriculum_from_disk():
    index = RagIndex.from_directory(SAMPLE_CURRICULUM)
    assert len(index) >= 1
    results = index.retrieve("variables and data types in python", top_k=2)
    assert results
    assert "python" in results[0].document.doc_id


def test_stopwords_do_not_outrank_a_long_lesson():
    index = RagIndex(
        [
            Document.from_text("short", "Note", "What is a host math deck."),
            Document.from_text(
                "intro-to-fractions/lesson.txt",
                "Fractions",
                (
                    "A fraction represents a part of a whole. "
                    "The numerator is the top number and the denominator is the bottom. "
                )
                * 30,
            ),
        ]
    )
    results = index.retrieve("what is a fraction numerator", top_k=1)
    assert results[0].document.doc_id == "intro-to-fractions/lesson.txt"


def test_rewrite_drops_function_words():
    from aoep_shared.rag import rewrite_query

    assert rewrite_query("what is gravity") == ["gravity"]
    assert rewrite_query("   ") == []
