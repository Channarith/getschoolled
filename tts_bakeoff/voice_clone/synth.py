"""Consent-gated synthesis: the only way the cloning adapters are built. No consent record, no adapter."""
from __future__ import annotations

from pathlib import Path

from tts_bakeoff import adapters

from . import registry

CLONE_MODELS = ("voxcpm2", "cosyvoice2")


def require_gpu(component: str) -> str:
    """CUDA-required policy (aoep_shared.devices): raises DevicePolicyError on a host that must use CUDA but has none."""
    from aoep_shared.devices import pick_device

    return pick_device(component)


def build_adapter(model: str, speaker: str, base: Path | None = None, gpu: bool = True, **extra):
    """Return an adapter that speaks in ``speaker``'s voice, after verifying consent, scope and sample integrity."""
    if model not in CLONE_MODELS and model != "mock":
        raise registry.ConsentError(f"{model!r} is not a cloning model here; use one of {CLONE_MODELS}")
    wav, transcript, lang = registry.primary_sample(speaker, base)
    if gpu and model != "mock":
        require_gpu(f"voice-clone:{model}")
    return adapters.get(model, reference_wav=str(wav), reference_text=transcript, prompt_wav=str(wav),
                        prompt_text=transcript, prompt_lang=lang, **extra)
