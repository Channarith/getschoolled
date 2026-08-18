"""Regression tests for the 2026-08-17 audit (perception service).

- HIGH-1  POST /identify returned 500 whenever a face observation's expression
          was None (EU region gate, or missing landmarks/bbox/frame_size).
- MED-8   ModelsUnavailable escaped /enroll and /identify as a 500 instead of
          the documented 503.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from perception.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_vision_provider():
    """The app caches one vision provider process-wide; never leak a stub."""
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
class _FakeFace:
    embedding: list
    bbox: Optional[Tuple[int, int, int, int]]
    landmarks: List[Tuple[float, float]]
    frame_size: Optional[Tuple[int, int]]


class _FakeEngine:
    def detect_faces(self, image):
        lmk = [(40, 50), (60, 50), (50, 62), (44, 74), (56, 74)]
        return [_FakeFace(embedding=[0.1, 0.2, 0.3], bbox=(30, 30, 40, 50),
                          landmarks=lmk, frame_size=(200, 200))]


def _install_provider(region: str):
    from aoep_shared.config import AppConfig, DeployMode
    from aoep_shared.providers.vision import LocalVisionProvider

    cfg = AppConfig(deploy_mode=DeployMode.LOCAL, region=region)
    prov = LocalVisionProvider(cfg)
    prov._engine = _FakeEngine()  # no model download
    app.state.factory._cache["vision"] = prov
    return prov


def test_identify_tolerates_none_expression_eu():
    _install_provider("eu")  # emotion recognition suppressed -> expression None
    r = client.post(
        "/identify",
        files={"file": ("f.jpg", b"img", "image/jpeg")},
        data={"consented_student_ids": ""},
    )
    assert r.status_code == 200
    assert r.json()["faces"][0]["expression"] == "unknown"


def test_enroll_returns_503_when_models_unavailable():
    from aoep_shared.vision.models import ModelsUnavailable

    class _Broken:
        def enroll(self, student_id, data):
            raise ModelsUnavailable("weights missing and download blocked")

    app.state.factory._cache["vision"] = _Broken()
    r = client.post(
        "/enroll/stud-x",
        files={"file": ("f.jpg", b"img", "image/jpeg")},
    )
    assert r.status_code == 503


def test_identify_returns_503_when_models_unavailable():
    from aoep_shared.vision.models import ModelsUnavailable

    class _Broken:
        def analyze_image(self, data, *, consented_student_ids):
            raise ModelsUnavailable("weights missing and download blocked")

    app.state.factory._cache["vision"] = _Broken()
    r = client.post(
        "/identify",
        files={"file": ("f.jpg", b"img", "image/jpeg")},
        data={"consented_student_ids": ""},
    )
    assert r.status_code == 503
