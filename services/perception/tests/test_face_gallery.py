"""Pure unit tests for the matching/consent logic (no models/network needed)."""

import math

from aoep_shared.vision import FaceGallery
from aoep_shared.vision.engine import (
    DEFAULT_MATCH_THRESHOLD,
    EXPRESSION_TOLERANCE_MARGIN,
    SFACE_CALIBRATED_THRESHOLD,
    cosine_similarity,
)


def _vec(*xs):
    return list(xs)


def test_cosine_similarity_basics():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert round(cosine_similarity([1, 1], [1, 0]), 3) == 0.707


def test_enroll_and_prototype_is_mean():
    g = FaceGallery(match_threshold=0.5)
    assert g.enroll("alice", _vec(1.0, 0.0)) == 1
    assert g.enroll("alice", _vec(0.0, 1.0)) == 2
    assert g.count("alice") == 2
    assert g.prototype("alice") == [0.5, 0.5]


def test_identify_matches_above_threshold():
    g = FaceGallery(match_threshold=0.5)
    g.enroll("alice", _vec(1.0, 0.0, 0.0))
    g.enroll("bob", _vec(0.0, 1.0, 0.0))
    m = g.identify(_vec(0.9, 0.1, 0.0))
    assert m.matched is True and m.student_id == "alice" and m.score > 0.5


def test_identify_rejects_below_threshold_open_set():
    g = FaceGallery(match_threshold=0.8)
    g.enroll("alice", _vec(1.0, 0.0, 0.0))
    # Orthogonal-ish query -> no confident match (unknown person).
    m = g.identify(_vec(0.0, 0.0, 1.0))
    assert m.matched is False and m.student_id is None


def test_consent_allowlist_restricts_candidates():
    g = FaceGallery(match_threshold=0.5)
    g.enroll("alice", _vec(1.0, 0.0))
    g.enroll("bob", _vec(0.0, 1.0))
    # Query looks like alice, but only bob consented -> never matched to alice.
    m = g.identify(_vec(0.95, 0.05), allowed_ids=["bob"])
    assert m.student_id != "alice"
    assert m.matched is False


def _at_cosine(score: float) -> list[float]:
    return [score, math.sqrt(max(0.0, 1.0 - score * score)), 0.0]


def test_expression_margin_matches_near_duplicates_not_a_different_face():
    """Smile, blink, sneeze, and modest weight change may drop a same-person
    score under the old 0.363 cut. They still match. A different direction does not.
    """
    assert SFACE_CALIBRATED_THRESHOLD == 0.363
    assert EXPRESSION_TOLERANCE_MARGIN == 0.063
    assert abs((SFACE_CALIBRATED_THRESHOLD - EXPRESSION_TOLERANCE_MARGIN) - DEFAULT_MATCH_THRESHOLD) < 1e-9
    # Stay above the held-out different-person band (~0.08).
    assert DEFAULT_MATCH_THRESHOLD >= 0.25

    gallery = FaceGallery()
    gallery.enroll("learner", [1.0, 0.0, 0.0])
    near = gallery.identify(_at_cosine(0.97))
    assert near.matched is True and near.student_id == "learner"
    drifted = _at_cosine(0.34)
    assert cosine_similarity([1.0, 0.0, 0.0], drifted) < SFACE_CALIBRATED_THRESHOLD
    match = gallery.identify(drifted)
    assert match.matched is True and match.student_id == "learner"
    stranger = gallery.identify(_at_cosine(0.12))
    assert stranger.matched is False and stranger.student_id is None
    assert gallery.identify(_at_cosine(0.2)).matched is False
    assert gallery.identify([0.0, 1.0, 0.0]).matched is False


def test_remove_identity():
    g = FaceGallery()
    g.enroll("alice", _vec(1.0, 0.0))
    g.remove("alice")
    assert "alice" not in g.students()
