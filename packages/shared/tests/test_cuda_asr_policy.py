"""The ingest's ASR follows the device policy: no silent CPU default."""
from __future__ import annotations

import pytest

from aoep_shared.cosyvoice_ingest import transcribe
from aoep_shared.devices import DevicePolicyError


@pytest.fixture
def wav(tmp_path, monkeypatch):
    for name in ("AOEP_ASR_DEVICE", "AOEP_ASR_ENGINE", "AOEP_ASR_COMPUTE_TYPE", "AOEP_ASR_KM_ENGINE", "AOEP_ASR_DETECT_LANGUAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(transcribe, "asr_available", lambda: True)
    monkeypatch.setattr(transcribe, "_memory_blocked", lambda *a, **k: False)
    path = tmp_path / "a.wav"
    path.write_bytes(b"RIFF")
    return path


def test_device_comes_from_the_policy_not_a_cpu_default(wav, monkeypatch):
    seen = {}
    monkeypatch.setattr(transcribe, "pick_device", lambda component, requested=None, torch_module=None: seen.update(c=component, r=requested) or "cuda")

    def fake_faster(w, *, language, model_name, device, compute_type):
        seen.update(device=device, compute=compute_type)
        return transcribe.TranscriptResult("hi", language, "faster", True, "ok")

    monkeypatch.setattr(transcribe, "_transcribe_faster", fake_faster)
    out = transcribe.transcribe_wav(wav, language="en")
    assert out.ok and seen["device"] == "cuda" and seen["compute"] == "float16"
    assert seen["c"] == "asr" and seen["r"] is None  # no AOEP_ASR_DEVICE set: the old default was "cpu"


def test_explicit_device_is_passed_to_the_policy(wav, monkeypatch):
    monkeypatch.setenv("AOEP_ASR_DEVICE", "cpu")
    seen = {}
    monkeypatch.setattr(transcribe, "pick_device", lambda component, requested=None, torch_module=None: seen.update(r=requested) or "cpu")
    monkeypatch.setattr(
        transcribe, "_transcribe_faster",
        lambda w, *, language, model_name, device, compute_type: transcribe.TranscriptResult("x", language, "f", True, "ok"),
    )
    transcribe.transcribe_wav(wav, language="en")
    assert seen["r"] == "cpu"


def test_policy_failure_propagates(wav, monkeypatch):
    def boom(component, requested=None, torch_module=None):
        raise DevicePolicyError("CUDA is required")

    monkeypatch.setattr(transcribe, "pick_device", boom)
    with pytest.raises(DevicePolicyError):
        transcribe.transcribe_wav(wav, language="en")


def test_language_detection_does_not_swallow_a_policy_failure(wav, monkeypatch):
    def boom(component, requested=None, torch_module=None):
        raise DevicePolicyError("CUDA is required")

    monkeypatch.setattr(transcribe, "pick_device", boom)
    with pytest.raises(DevicePolicyError):
        transcribe._detect_language_whisper(wav, "large-v3")
