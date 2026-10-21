"""POST /enroll-face-images: the phone face check sends its photos in one call.

Every photo must match the first. The learner's templates are replaced only
when all of them pass, so a failed redo keeps the earlier face check.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from aoep_shared.vision.gallery import FaceGallery
from perception.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_vision_provider():
    cache = app.state.factory._cache
    sentinel = object()
    saved = cache.get("vision", sentinel)
    try:
        yield
    finally:
        if saved is sentinel:
            cache.pop("vision", None)
        else:
            cache["vision"] = saved


@dataclass
class _Face:
    embedding: list


class _Engine:
    def __init__(self, vectors):
        self._vectors = {base64.b64encode(key).decode(): value for key, value in vectors.items()}

    def detect_faces(self, image):
        vector = self._vectors.get(base64.b64encode(image).decode())
        return [_Face(vector)] if vector else []


def _provider(vectors):
    from aoep_shared.config import AppConfig
    from aoep_shared.providers.vision import LocalVisionProvider

    provider = LocalVisionProvider(AppConfig())
    provider._gallery_path = None
    provider._gallery = FaceGallery()
    provider._engine = _Engine(vectors)
    app.state.factory._cache["vision"] = provider
    return provider


def _photo(seed: int) -> bytes:
    return b"\xff\xd8\xff" + bytes([seed]) * 64


def _post(student_id, photos):
    return client.post(
        f"/enroll-face-images/{student_id}",
        json={"images_b64": [base64.b64encode(photo).decode() for photo in photos]},
    )


def test_five_matching_photos_replace_the_old_templates():
    photos = [_photo(n) for n in range(5)]
    provider = _provider({photo: [1.0, 0.02 * n, 0.0] for n, photo in enumerate(photos)})
    provider._gallery.enroll("learner", [0.0, 0.0, 1.0])
    saved = _post("learner", photos)
    assert saved.status_code == 200, saved.text
    assert saved.json()["enrollments"] == 5
    assert provider._gallery.count("learner") == 5


def test_a_different_person_keeps_the_earlier_check():
    photos = [_photo(n) for n in range(5)]
    vectors = {photo: [1.0, 0.0, 0.0] for photo in photos}
    vectors[photos[3]] = [0.0, 1.0, 0.0]
    provider = _provider(vectors)
    provider._gallery.enroll("learner", [1.0, 0.0, 0.0])
    refused = _post("learner", photos)
    assert refused.status_code == 422
    assert "photo 4" in refused.json()["detail"]
    assert provider._gallery.count("learner") == 1


def test_a_photo_without_a_face_is_named():
    photos = [_photo(n) for n in range(5)]
    vectors = {photo: [1.0, 0.0, 0.0] for photo in photos[:2]}
    _provider(vectors)
    refused = _post("learner", photos)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "no face detected in photo 3"
