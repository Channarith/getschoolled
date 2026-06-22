"""Hybrid (on-device) path, end-to-end with the REAL models.

Simulates the client device: run YuNet+SFace locally (via the same
``FaceRecognitionEngine`` the browser/mobile pipeline uses) to produce a 128-d
embedding + landmarks from a face image, then send ONLY that embedding to the
server's ``/identify-embedding`` and ``/enroll-embedding`` endpoints. The raw
image is never uploaded. This proves the server matches client-computed
embeddings identically to the server-side ``/identify`` path, and that the
consent gate still holds.

Skips cleanly when the models/dataset are unavailable (restricted network).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(models, dataset):
    from perception.main import app

    return TestClient(app)


def _embed(engine, path: str) -> dict:
    """Client-side: detect + embed the largest face, return the wire payload."""
    faces = engine.detect_faces(path)
    assert faces, f"no face detected in {path}"
    f = faces[0]
    return {
        "embedding": f.embedding,
        "landmarks": [[x, y] for (x, y) in f.landmarks],
        "bbox": list(f.bbox),
        "frame_size": list(f.frame_size),
    }


def _train(dataset, person):
    return dataset["train"][person][0]


def _test_img(dataset, name):
    return next(p for p in dataset["test"] if p.endswith(name))


def test_enroll_then_identify_embedding_with_consent(client, engine, dataset):
    # Client computes embeddings locally and enrolls them (no image upload).
    for person in ("obama", "biden"):
        payload = _embed(engine, _train(dataset, person))
        r = client.post(f"/enroll-embedding/{person}", json={"embedding": payload["embedding"]})
        assert r.status_code == 200, r.text
        assert r.json()["enrollments"] >= 1

    # Client embeds a held-out Obama photo and sends only the embedding.
    face = _embed(engine, _test_img(dataset, "obama1.jpg"))
    r = client.post(
        "/identify-embedding",
        json={"faces": [face], "consented_student_ids": ["obama", "biden"]},
    )
    assert r.status_code == 200, r.text
    faces = r.json()["faces"]
    assert len(faces) == 1
    assert faces[0]["matched_student_id"] == "obama"
    assert faces[0]["identified"] is True
    # Engagement was derived from the supplied landmarks.
    assert faces[0]["attention"] > 0.0


def test_consent_gate_blocks_identity_when_not_consented(client, engine, dataset):
    payload = _embed(engine, _train(dataset, "obama"))
    client.post("/enroll-embedding/obama", json={"embedding": payload["embedding"]})

    face = _embed(engine, _test_img(dataset, "obama1.jpg"))
    r = client.post(
        "/identify-embedding",
        json={"faces": [face], "consented_student_ids": []},
    )
    assert r.status_code == 200, r.text
    faces = r.json()["faces"]
    assert len(faces) == 1  # presence still observed
    assert faces[0]["identified"] is False
    assert faces[0]["matched_student_id"] is None


def test_model_weights_served_to_clients(client):
    # The on-device client fetches the model weights from our origin.
    r = client.get("/vision/models/face_detection_yunet_2023mar.onnx")
    assert r.status_code == 200, r.text
    assert len(r.content) > 150_000
    assert client.get("/vision/models/bogus.onnx").status_code == 404
