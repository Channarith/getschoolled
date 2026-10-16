"""Pure unit tests for the matching/consent logic (no models/network needed)."""

import math

from aoep_shared.vision import FaceGallery
from aoep_shared.vision.engine import (
    DEFAULT_MATCH_THRESHOLD,
    EXPRESSION_TOLERANCE_MARGIN,
    LIVENESS_TEMPLATE_COUNT,
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


def test_best_template_keeps_pose_variation_without_lowering_the_cut():
    """Opposite poses cancel in a mean. Best-of still matches the enrolled
    capture. The accept bar stays at 0.363, so a 0.34 score does not match.
    """
    assert SFACE_CALIBRATED_THRESHOLD == 0.363
    assert DEFAULT_MATCH_THRESHOLD == SFACE_CALIBRATED_THRESHOLD
    assert EXPRESSION_TOLERANCE_MARGIN == 0.063
    # That margin is headroom we do not spend. Spending it would be 0.300.
    assert math.isclose(DEFAULT_MATCH_THRESHOLD - EXPRESSION_TOLERANCE_MARGIN, 0.3)
    assert LIVENESS_TEMPLATE_COUNT == 5

    gallery = FaceGallery()
    gallery.enroll("learner", [1.0, 0.0, 0.0])
    gallery.enroll("learner", [-1.0, 0.0, 0.0])
    assert gallery.prototype("learner") == [0.0, 0.0, 0.0]
    turned = gallery.identify([-1.0, 0.0, 0.0])
    assert turned.matched is True and turned.student_id == "learner"
    assert turned.score == 1.0
    near = gallery.identify(_at_cosine(0.97))
    assert near.matched is True and near.student_id == "learner"
    below_calibrated = gallery.identify(_at_cosine(0.34))
    assert cosine_similarity([1.0, 0.0, 0.0], _at_cosine(0.34)) < SFACE_CALIBRATED_THRESHOLD
    assert below_calibrated.matched is False
    assert gallery.identify(_at_cosine(0.12)).matched is False
    assert gallery.identify(_at_cosine(0.2)).matched is False
    assert gallery.identify([0.0, 1.0, 0.0]).matched is False


def test_high_assurance_waits_for_the_pose_set():
    gallery = FaceGallery()
    gallery.enroll("learner", [1.0, 0.0, 0.0])
    early = gallery.identify([1.0, 0.0, 0.0], high_assurance=True)
    assert early.matched is False
    poses = (
        [1.0, 0.0, 0.0],
        [0.96, 0.28, 0.0],
        [0.96, -0.28, 0.0],
        [0.96, 0.0, 0.28],
        [0.96, 0.0, -0.28],
    )
    assert len(poses) == LIVENESS_TEMPLATE_COUNT
    for pose in poses[1:]:
        gallery.enroll("learner", pose)
    done = gallery.identify([0.96, 0.28, 0.0], high_assurance=True)
    assert done.matched is True and done.student_id == "learner"
    assert gallery.identify([0.0, 1.0, 0.0], high_assurance=True).matched is False


def test_remove_identity():
    g = FaceGallery()
    g.enroll("alice", _vec(1.0, 0.0))
    g.remove("alice")
    assert "alice" not in g.students()
