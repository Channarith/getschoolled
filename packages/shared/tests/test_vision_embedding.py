"""Hybrid (on-device) vision path: match precomputed embeddings server-side.

These tests exercise the embedding-based provider API used by the hybrid path,
where the client/edge device runs YuNet+SFace locally and sends only the 128-d
embedding. They use synthetic vectors, so they need no OpenCV model download and
always run (the real-model round-trip is covered in the perception service
tests).
"""

from __future__ import annotations

from aoep_shared.config import load_config
from aoep_shared.providers.base import EmbeddedFace
from aoep_shared.providers.vision import LocalVisionProvider

# Frontal 5-landmark set (right_eye, left_eye, nose, right_mouth, left_mouth)
# with a centered, reasonably-sized bbox -> high attention/gaze.
_LANDMARKS = [(40.0, 40.0), (60.0, 40.0), (50.0, 52.0), (42.0, 66.0), (58.0, 66.0)]
_BBOX = (30, 20, 40, 60)
_FRAME = (100, 100)


def _vec(*head: float) -> list[float]:
    """A 128-d embedding seeded by ``head`` (rest zero)."""
    v = [0.0] * 128
    for i, x in enumerate(head):
        v[i] = x
    return v


def _provider(region: str = "us") -> LocalVisionProvider:
    return LocalVisionProvider(load_config(env={"DEPLOY_MODE": "local", "REGION": region}))


def test_enroll_and_identify_embedding_with_consent():
    v = _provider()
    assert v.enroll_embedding("alice", _vec(1.0, 0.0)) == 1
    assert v.enroll_embedding("bob", _vec(0.0, 1.0)) == 1

    faces = [EmbeddedFace(embedding=_vec(0.99, 0.01))]
    obs = v.analyze_embedding(faces, consented_student_ids=["alice", "bob"])
    assert len(obs) == 1
    assert obs[0].matched_student_id == "alice"


def test_consent_gate_withholds_identity_when_not_consented():
    v = _provider()
    v.enroll_embedding("alice", _vec(1.0, 0.0))

    obs = v.analyze_embedding(
        [EmbeddedFace(embedding=_vec(0.99, 0.01))], consented_student_ids=[]
    )
    # Face is still observed, but no identity is attached (anonymous presence).
    assert len(obs) == 1
    assert obs[0].matched_student_id is None


def test_landmarks_yield_engagement_signals():
    v = _provider()
    v.enroll_embedding("alice", _vec(1.0, 0.0))
    obs = v.analyze_embedding(
        [
            EmbeddedFace(
                embedding=_vec(0.99, 0.01),
                landmarks=_LANDMARKS,
                bbox=_BBOX,
                frame_size=_FRAME,
            )
        ],
        consented_student_ids=["alice"],
    )
    assert obs[0].attention_score > 0.5
    assert obs[0].gaze_frontal > 0.5
    assert obs[0].expression is not None


def test_no_landmarks_means_identity_only_no_engagement():
    v = _provider()
    v.enroll_embedding("alice", _vec(1.0, 0.0))
    obs = v.analyze_embedding(
        [EmbeddedFace(embedding=_vec(0.99, 0.01))], consented_student_ids=["alice"]
    )
    assert obs[0].matched_student_id == "alice"
    assert obs[0].attention_score == 0.0
    assert obs[0].gaze_frontal == 0.0
    assert obs[0].expression is None


def test_eu_region_blocks_identity_and_expression():
    # EU AI Act: real-time biometric identification + emotion recognition in
    # education are prohibited, so even a consented match is withheld.
    v = _provider(region="eu")
    v.enroll_embedding("alice", _vec(1.0, 0.0))
    obs = v.analyze_embedding(
        [
            EmbeddedFace(
                embedding=_vec(0.99, 0.01),
                landmarks=_LANDMARKS,
                bbox=_BBOX,
                frame_size=_FRAME,
            )
        ],
        consented_student_ids=["alice"],
    )
    assert obs[0].matched_student_id is None  # identity withheld
    assert obs[0].expression is None  # emotion recognition suppressed
    # Attention/gaze (non-biometric engagement) are still available.
    assert obs[0].attention_score > 0.0


def test_empty_embedding_rejected():
    v = _provider()
    try:
        v.enroll_embedding("alice", [])
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty embedding")
