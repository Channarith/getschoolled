"""Pure unit tests for the matching/consent logic (no models/network needed)."""

from aoep_shared.vision import FaceGallery
from aoep_shared.vision.engine import cosine_similarity


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


def test_remove_identity():
    g = FaceGallery()
    g.enroll("alice", _vec(1.0, 0.0))
    g.remove("alice")
    assert "alice" not in g.students()
