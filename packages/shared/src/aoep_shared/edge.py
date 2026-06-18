"""Edge / local-first profile conformance (Phase 13).

The edge profile runs the whole teaching brain on-device with NO cloud calls -
the foundation of the embodiment/humanoid path. These helpers assert that a
configured factory resolves every capability to a local (offline) implementation,
so a regression that sneaks a cloud dependency into the edge build is caught.

On-device model story (documented; wired in Phase 15): quantized local models -
GGUF via llama.cpp for the LLM, ONNX for ASR/TTS/vision - so inference needs no
network or datacenter GPU.
"""

from __future__ import annotations

from typing import Dict, List

from .config import AppConfig, DeployMode

# Capabilities that must be local for an offline/edge deployment.
EDGE_REQUIRED_LOCAL = ("llm", "speech", "vision", "media", "object_store", "ocr")


def edge_report(factory) -> Dict[str, str]:
    """Map each required capability to its resolved 'mode:impl'."""
    report: Dict[str, str] = {}
    getters = {
        "llm": factory.llm, "speech": factory.speech, "vision": factory.vision,
        "media": factory.media, "object_store": factory.object_store, "ocr": factory.ocr,
    }
    for cap in EDGE_REQUIRED_LOCAL:
        info = getters[cap]().info()
        report[cap] = f"{info.mode}:{info.impl}"
    return report


def offline_violations(factory) -> List[str]:
    """Capabilities NOT resolving to a local impl (should be empty on edge)."""
    return [f"{cap}={mode_impl}" for cap, mode_impl in edge_report(factory).items()
            if not mode_impl.startswith("local")]


def assert_offline(factory) -> None:
    """Raise if any required capability would make a cloud/network call."""
    bad = offline_violations(factory)
    if bad:
        raise RuntimeError(f"edge profile is not fully offline: {bad}")


def edge_config(**overrides) -> AppConfig:
    """Convenience: an AppConfig pinned to the edge (all-local) profile."""
    return AppConfig(deploy_mode=DeployMode.EDGE, **overrides)


def edge_smoke(factory) -> Dict[str, object]:
    """On-device boot smoke (Phase 15): assert fully offline, then produce one
    teaching beat - proves the packaged edge runtime can teach with no network.

    The beat is rendered through the always-available screen avatar (the
    embodiment-agnostic output stream); the configured embodiment TARGET (e.g. a
    robot, whose hardware provider is wired on-device) is reported separately."""
    assert_offline(factory)
    from .providers.embodiment import ScreenAvatarProvider, narrate

    target = factory.embodiment().info().impl
    actions = narrate(ScreenAvatarProvider(factory.config),
                      "Edge teaching turn: today we learn fractions.", gesture="wave")
    return {
        "offline": True,
        "embodiment_target": target,
        "actions": len(actions),
        "first_modality": actions[0].modality,
    }
