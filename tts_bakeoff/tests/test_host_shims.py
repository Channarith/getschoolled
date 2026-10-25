import sys
import types
import wave

import numpy as np
import pytest

from tts_bakeoff.adapters import host_shims


def test_onnx_shim_drops_unavailable_providers(monkeypatch):
    seen = {}

    class Session:
        def __init__(self, *a, **k):
            seen.update(k)

    fake = types.SimpleNamespace(InferenceSession=Session, get_available_providers=lambda: ["CPUExecutionProvider"])
    monkeypatch.setitem(sys.modules, "onnxruntime", fake)
    host_shims.force_available_onnx_providers()
    fake.InferenceSession("m.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    assert seen["providers"] == ["CPUExecutionProvider"]
    fake.InferenceSession("m.onnx", providers=["CUDAExecutionProvider"])
    assert seen["providers"] == ["CPUExecutionProvider"]
    host_shims.force_available_onnx_providers()  # idempotent


def test_torchaudio_load_shim_reads_wav_without_torchcodec(tmp_path, monkeypatch):
    pytest.importorskip("soundfile")
    torchaudio = pytest.importorskip("torchaudio")
    monkeypatch.setattr(torchaudio, "load", lambda *a, **k: (_ for _ in ()).throw(ImportError("TorchCodec is required")))
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.sin(np.arange(1600) / 10) * 12000).astype("<i2").tobytes())
    host_shims.patch_torchaudio_load()
    audio, rate = torchaudio.load(str(p))
    assert rate == 16000 and audio.shape == (1, 1600)
