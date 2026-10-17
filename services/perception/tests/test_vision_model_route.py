"""One face-model file must not 503 because the other file cannot be downloaded."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_ensure_model_does_not_require_the_other_file(tmp_path, monkeypatch):
    from aoep_shared.vision import models as vision_models

    detector = tmp_path / vision_models.DETECTOR_NAME
    detector.write_bytes(b"z" * vision_models._DETECTOR_MIN_BYTES)

    def blocked(url, dest):
        raise OSError("github blocked")

    monkeypatch.setattr(vision_models, "_download", blocked)
    path = vision_models.ensure_model(vision_models.DETECTOR_NAME, str(tmp_path))
    assert path == str(detector)
    with pytest.raises(vision_models.ModelsUnavailable, match="face_recognition_sface"):
        vision_models.ensure_model(vision_models.RECOGNIZER_NAME, str(tmp_path))
    with pytest.raises(vision_models.ModelsUnavailable):
        vision_models.ensure_models(str(tmp_path))
    ready = vision_models.preload_models(str(tmp_path))
    assert ready[vision_models.DETECTOR_NAME] == str(detector)
    assert ready[vision_models.RECOGNIZER_NAME] is None


def test_route_serves_yunet_when_sface_cannot_download(tmp_path, monkeypatch):
    from aoep_shared.vision import models as vision_models
    from perception.main import app

    detector = tmp_path / vision_models.DETECTOR_NAME
    payload = b"z" * vision_models._DETECTOR_MIN_BYTES
    detector.write_bytes(payload)
    def blocked(url, dest):
        raise OSError("blocked")

    monkeypatch.setattr(vision_models, "_download", blocked)
    previous = app.state.factory.config.vision_model_dir
    app.state.factory.config.vision_model_dir = str(tmp_path)
    try:
        client = TestClient(app)
        ok = client.get(f"/vision/models/{vision_models.DETECTOR_NAME}")
        assert ok.status_code == 200, ok.text
        assert ok.content == payload
        missing = client.get(f"/vision/models/{vision_models.RECOGNIZER_NAME}")
        assert missing.status_code == 503
        assert "face_recognition_sface" in missing.json()["detail"]
        assert "github" not in missing.json()["detail"].lower()
        assert client.get("/vision/models/bogus.onnx").status_code == 404
    finally:
        app.state.factory.config.vision_model_dir = previous
