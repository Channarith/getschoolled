"""End-to-end API tests for enrollment + consent-gated identification."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(models, dataset):
    # Import after conftest set VISION_MODEL_DIR and models/dataset are ensured.
    from perception.main import app

    return TestClient(app)


def _img(path: str):
    with open(path, "rb") as fh:
        return (os.path.basename(path), fh.read(), "image/jpeg")


def _train(dataset, person):
    return dataset["train"][person][0]


def _test_img(dataset, name):
    return next(p for p in dataset["test"] if p.endswith(name))


def test_enroll_then_identify_with_consent(client, dataset):
    # Enroll two students.
    for person in ("obama", "biden"):
        r = client.post(f"/enroll/{person}", files={"file": _img(_train(dataset, person))})
        assert r.status_code == 200, r.text
        assert r.json()["enrollments"] >= 1

    # Identify a held-out Obama photo with both students consented.
    r = client.post(
        "/identify",
        files={"file": _img(_test_img(dataset, "obama1.jpg"))},
        data={"consented_student_ids": "obama,biden"},
    )
    assert r.status_code == 200, r.text
    matched = {f["matched_student_id"] for f in r.json()["faces"] if f["identified"]}
    assert "obama" in matched


def test_consent_gate_blocks_identity_when_not_consented(client, dataset):
    client.post("/enroll/obama", files={"file": _img(_train(dataset, "obama"))})

    # Same Obama photo, but nobody consented -> face detected, identity withheld.
    r = client.post(
        "/identify",
        files={"file": _img(_test_img(dataset, "obama1.jpg"))},
        data={"consented_student_ids": ""},
    )
    assert r.status_code == 200, r.text
    faces = r.json()["faces"]
    assert len(faces) >= 1  # face still detected (anonymous presence)
    assert all(f["identified"] is False for f in faces)
    assert all(f["matched_student_id"] is None for f in faces)


def test_gallery_lists_enrolled_students(client, dataset):
    client.post("/enroll/obama", files={"file": _img(_train(dataset, "obama"))})
    r = client.get("/gallery")
    assert r.status_code == 200
    assert "obama" in r.json()["students"]
