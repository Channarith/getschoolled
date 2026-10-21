"""POST /detect-landmarks returns YuNet geometry for one still (used to draw the
face contour on the phone's captured photo) without storing or exposing an
embedding."""

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

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
    bbox: tuple
    det_score: float
    embedding: list
    landmarks: list
    frame_size: tuple


class _Engine:
    def __init__(self):
        self.calls = 0

    def detect_landmarks(self, image):
        self.calls += 1
        return [_Face((30, 30, 40, 50), 0.91, [0.1, 0.2, 0.3],
                      [(40, 50), (60, 50), (50, 62), (44, 74), (56, 74)], (200, 200))]


class _Provider:
    def __init__(self):
        self._engine = _Engine()
        self.enrolled = []

    def engine(self):
        return self._engine

    def enroll(self, student_id, data):
        self.enrolled.append(student_id)
        return 1


def _post():
    return client.post(
        "/detect-landmarks",
        files={"file": ("still.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\0" * 100), "image/jpeg")},
    )


def test_detect_landmarks_returns_geometry_only():
    provider = _Provider()
    app.state.factory._cache["vision"] = provider
    r = _post()
    assert r.status_code == 200
    face = r.json()["faces"][0]
    assert face == {
        "bbox": [30, 30, 40, 50],
        "landmarks": [[40.0, 50.0], [60.0, 50.0], [50.0, 62.0], [44.0, 74.0], [56.0, 74.0]],
        "frame_size": [200, 200],
        "score": pytest.approx(0.91),
    }
    assert "embedding" not in r.text
    assert provider.enrolled == []


def test_detect_landmarks_maps_missing_models_to_503():
    from aoep_shared.vision.models import ModelsUnavailable

    class _Broken:
        def engine(self):
            raise ModelsUnavailable("weights missing")

    app.state.factory._cache["vision"] = _Broken()
    assert _post().status_code == 503


def test_detect_landmarks_requires_internal_token(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)
    assert _post().status_code in (401, 403)
