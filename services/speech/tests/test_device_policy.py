"""CUDA policy at the speech gateway: /device readiness and a required-CUDA failure is a 503, never a silent passthrough."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aoep_shared import devices, nllb
from aoep_shared.devices import DevicePolicyError
from speech_gw.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    for name in ("AOEP_HOST_ROLE", "AOEP_REQUIRE_CUDA", "AOEP_ALLOW_CPU", "CUDA_VISIBLE_DEVICES"):
        monkeypatch.delenv(name, raising=False)
    devices._reset_for_tests()
    monkeypatch.setattr(nllb, "_model", None)
    yield
    devices._reset_for_tests()


def test_translate_returns_503_when_cuda_is_required_but_broken(monkeypatch):
    def boom():
        raise DevicePolicyError("CUDA is required on this host (role=spark) but is not usable for 'nllb'")

    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    monkeypatch.setattr(nllb, "_get_model", boom)
    r = client.post("/translate", json={"text": "hello there", "source": "en", "target": "km"})
    assert r.status_code == 503
    assert "GPU required" in r.json()["detail"]


def test_translate_without_the_policy_still_degrades_gracefully(monkeypatch):
    # a normal host with no NLLB: the old behaviour (phrasebook / passthrough) must not change
    monkeypatch.setenv("AOEP_HOST_ROLE", "other")
    monkeypatch.setattr(nllb, "_get_model", lambda: (_ for _ in ()).throw(RuntimeError("no model here")))
    r = client.post("/translate", json={"text": "zzz unlikely phrase zzz", "source": "en", "target": "km"})
    assert r.status_code == 200
    assert r.json()["degraded"] is True


def test_device_endpoint_ok_when_cuda_not_required(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "other")
    r = client.get("/device")
    assert r.status_code == 200
    body = r.json()
    assert body["cuda_required"] is False and body["model_loaded"] is False


def test_device_endpoint_503_when_cuda_required_and_unusable(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    monkeypatch.setattr(devices, "cuda_smoke", lambda torch=None: (False, "torch.cuda.is_available() is False"))
    r = client.get("/device")
    assert r.status_code == 503
    assert "CUDA required but unusable" in str(r.json())
