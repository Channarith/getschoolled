"""Recognition accuracy tests on a real multi-image-per-person dataset.

Exercises the actual OpenCV YuNet + SFace pipeline end to end: detection,
embedding separation (same vs different person), 1:N identification accuracy,
and open-set rejection of an un-enrolled identity. Skips if models/dataset are
unavailable (restricted network).
"""

from __future__ import annotations

import itertools

import pytest

from aoep_shared.vision import FaceGallery
from aoep_shared.vision.engine import cosine_similarity

# Which identity each held-out test image should resolve to (or None = absent).
EXPECTED = {
    "alex_lacamoire1.jpg": "alex_lacamoire",
    "obama1.jpg": "obama",
    "johnsnow_test1.jpg": "kit_harington",
    "kit_with_rose.jpg": "kit_harington",   # multi-face; kit must be present
    "obama_and_biden.jpg": "obama",         # multi-face; obama must be present
}


def test_every_training_image_has_a_detectable_face(engine, dataset):
    for person, paths in dataset["train"].items():
        for path in paths:
            faces = engine.detect_faces(path)
            assert faces, f"no face detected in {person}:{path}"
            assert len(faces[0].embedding) == 128


def test_same_person_scores_higher_than_different_person(engine, dataset):
    protos = {}
    embeds = {}
    for person, paths in dataset["train"].items():
        vecs = [engine.embed(p) for p in paths]
        vecs = [v for v in vecs if v is not None]
        embeds[person] = vecs
        protos[person] = vecs

    within = [
        cosine_similarity(a, b)
        for vecs in embeds.values()
        for a, b in itertools.combinations(vecs, 2)
    ]
    across = [
        cosine_similarity(embeds[p1][0], embeds[p2][0])
        for p1, p2 in itertools.combinations(embeds, 2)
    ]
    # Clear separation: same-person similarity well above different-person.
    assert within, "need at least one same-person pair"
    assert min(within) > max(across)
    assert min(within) > 0.363  # SFace cosine threshold


def test_one_to_many_identification_accuracy(engine, dataset):
    gallery = FaceGallery()
    for person, paths in dataset["train"].items():
        for path in paths:
            emb = engine.embed(path)
            if emb is not None:
                gallery.enroll(person, emb)

    correct = 0
    for path in dataset["test"]:
        name = path.rsplit("/", 1)[-1]
        if name not in EXPECTED:
            continue
        # For multi-face images, accept a correct identity among detected faces.
        ids = set()
        for face in engine.detect_faces(path):
            m = gallery.identify(face.embedding)
            if m.matched:
                ids.add(m.student_id)
        assert EXPECTED[name] in ids, f"{name}: expected {EXPECTED[name]}, got {ids}"
        correct += 1
    assert correct >= 5


def test_open_set_rejects_unenrolled_identity(engine, dataset):
    # Enroll everyone EXCEPT obama, then obama must come back unknown.
    gallery = FaceGallery()
    for person, paths in dataset["train"].items():
        if person == "obama":
            continue
        for path in paths:
            emb = engine.embed(path)
            if emb is not None:
                gallery.enroll(person, emb)

    obama_test = next(p for p in dataset["test"] if p.endswith("obama1.jpg"))
    emb = engine.embed(obama_test)
    assert emb is not None
    m = gallery.identify(emb)
    assert m.matched is False, f"obama wrongly matched to {m.student_id} ({m.score})"


def test_multi_face_frame_detects_two_faces(engine, dataset):
    both = next(p for p in dataset["test"] if p.endswith("obama_and_biden.jpg"))
    faces = engine.detect_faces(both)
    assert len(faces) >= 2
