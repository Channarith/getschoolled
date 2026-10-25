"""Workarounds for this Spark's package set, shared by the CosyVoice 2 adapter (same fixes as scripts/spark_cosyvoice_khmer_eval.py).

torchaudio.load needs TorchCodec on the newer torchaudio and it is not installed; onnxruntime has no CUDA provider but CosyVoice
still asks for one. Both are process-wide and idempotent, and they do nothing on a host where the originals work.
"""
from __future__ import annotations


def patch_torchaudio_load() -> None:
    from io import BytesIO

    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio

    if getattr(torchaudio.load, "_aoep_sf", False):
        return

    def load(source, *args, **kwargs):
        del args, kwargs
        if isinstance(source, (bytes, bytearray, memoryview)):
            source = BytesIO(bytes(source))
        data, sample_rate = sf.read(source, dtype="float32", always_2d=True)
        return torch.from_numpy(np.ascontiguousarray(data.T)), int(sample_rate)

    load._aoep_sf = True  # type: ignore[attr-defined]
    torchaudio.load = load


def force_available_onnx_providers() -> None:
    import onnxruntime as ort

    if getattr(ort, "_aoep_cpu_only", False):
        return
    real = ort.InferenceSession
    available = set(ort.get_available_providers())

    def session(*args, **kwargs):
        providers = kwargs.get("providers")
        if providers:
            kept = [item for item in providers if item in available]
            kwargs["providers"] = kept or ["CPUExecutionProvider"]
        return real(*args, **kwargs)

    ort.InferenceSession = session
    ort._aoep_cpu_only = True


def install() -> None:
    for fn in (patch_torchaudio_load, force_available_onnx_providers):
        try:
            fn()
        except ImportError:  # the package is absent here: nothing to patch
            pass
