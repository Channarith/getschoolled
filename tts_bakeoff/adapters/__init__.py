"""Adapter registry. Importing this module imports no heavy dependency."""
from __future__ import annotations

from importlib import import_module

from .base import Adapter, AdapterError

# adapter name -> (module, class). candidates.yaml "adapter:" values use these names.
REGISTRY = {
    "mock": ("mock", "MockAdapter"),
    "voxcpm2": ("voxcpm2", "VoxCPM2Adapter"),
    "qwen3_tts": ("qwen3_tts", "Qwen3TTSAdapter"),
    "chatterbox": ("chatterbox", "ChatterboxAdapter"),
    "kokoro": ("kokoro", "KokoroAdapter"),
    "mms_tts": ("mms_tts", "MmsTtsAdapter"),
    "cosyvoice2": ("cosyvoice2", "CosyVoice2Adapter"),
    "fish_speech15": ("fish_speech15", "FishSpeech15Adapter"),
    "azure": ("azure", "AzureAdapter"),
}


def get(name: str, **options) -> Adapter:
    if name not in REGISTRY:
        raise AdapterError(f"unknown adapter {name!r}; known: {sorted(REGISTRY)}")
    module, cls = REGISTRY[name]
    return getattr(import_module(f"{__name__}.{module}"), cls)(**options)


__all__ = ["Adapter", "AdapterError", "REGISTRY", "get"]
