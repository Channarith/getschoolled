"""Course validation (claim extraction + multi-engine corroboration) tests."""

from aoep_shared.providers.base import SearchResult
from aoep_shared.providers.search import MockSearchProvider
from aoep_shared.validation import (
    extract_claims,
    validate_claim,
    validate_course,
)


def test_extract_claims_splits_substantive_sentences():
    text = "Photosynthesis converts light into sugars. Hi. Plants release oxygen as a byproduct."
    claims = extract_claims(text)
    assert len(claims) == 2  # "Hi." dropped (too short)


def test_supported_when_snippet_corroborates():
    # MockSearchProvider echoes the query as the snippet -> full overlap.
    v = validate_claim("plants release oxygen during photosynthesis", [MockSearchProvider()])
    assert v.status == "supported"
    assert v.confidence > 0.5
    assert v.citations and v.engines_consulted == 1


def test_unverified_when_no_overlap():
    canned = {"the mitochondria is the powerhouse":
              [SearchResult("t", "u", "completely unrelated cooking recipe", "mock")]}
    eng = MockSearchProvider(canned=canned)
    v = validate_claim("the mitochondria is the powerhouse", [eng])
    assert v.status == "unverified"


def test_contradicted_heuristic():
    canned = {"the earth is flat":
              [SearchResult("t", "u", "the earth is flat is false and debunked", "mock")]}
    eng = MockSearchProvider(canned=canned)
    v = validate_claim("the earth is flat", [eng])
    assert v.status == "contradicted"


def test_validate_course_aggregates():
    claims = extract_claims(
        "Plants release oxygen during photosynthesis. Water boils at one hundred degrees."
    )
    report = validate_course(claims, [MockSearchProvider()])
    assert report.total == 2
    assert report.supported == 2
    assert report.flagged == []


def test_multi_engine_consulted_count():
    v = validate_claim("oxygen is released by plants", [MockSearchProvider(), MockSearchProvider()])
    assert v.engines_consulted == 2
